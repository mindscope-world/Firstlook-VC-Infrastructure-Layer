"""Ingest HTTP service: connecting accounts, sync control, CRM imports, Slack install.

Served behind the web app at /api/ingest/* (Next.js rewrite). Callers are
authenticated with the session JWT issued by services/api (cookie fl_session
or Authorization: Bearer).
"""

from __future__ import annotations

import hashlib
import logging
import secrets
import time
from typing import Annotated, Any
from uuid import UUID

import jwt
from fastapi import Cookie, Depends, FastAPI, File, Form, Header, HTTPException, Query, UploadFile
from fastapi.responses import RedirectResponse
from psycopg.types.json import Jsonb
from pydantic import BaseModel, Field

from firstlook_core import audit
from firstlook_core.auth import Principal, verify_session
from firstlook_core.config import get_settings
from firstlook_core.crypto import seal
from firstlook_core.db import tenant_tx

from . import slack, temporal
from .accounts import fresh_tokens, save_account, sync_once
from .connectors.base import AuthError, RawItem, get_connector
from .crm import import_records, parse_csv
from .crm.model import VENDORS
from .raw import land

log = logging.getLogger("firstlook.ingest")
app = FastAPI(title="Firstlook ingest")

MAX_CSV_BYTES = 20 * 1024 * 1024
MANAGE_IMPORT_ROLES = {"admin", "partner", "platform"}


def principal(
    fl_session: Annotated[str | None, Cookie()] = None,
    authorization: Annotated[str | None, Header()] = None,
) -> Principal:
    token = fl_session or (authorization.removeprefix("Bearer ") if authorization else None)
    if not token:
        raise HTTPException(401, "not signed in")
    try:
        return verify_session(token)
    except jwt.PyJWTError as e:
        raise HTTPException(401, "invalid session") from e


User = Annotated[Principal, Depends(principal)]


def _redirect_uri(provider: str) -> str:
    return f"{get_settings().ingest_public_url}/connectors/{provider}/callback"


def _state(p: Principal, purpose: str) -> str:
    return jwt.encode(
        {
            "uid": str(p.user_id),
            "tid": str(p.tenant_id),
            "role": p.role,
            "purpose": purpose,
            "nonce": secrets.token_urlsafe(8),
            "exp": int(time.time()) + 600,
        },
        get_settings().session_secret,
        algorithm="HS256",
    )


def _verify_state(state: str, purpose: str, p: Principal) -> None:
    try:
        claims = jwt.decode(state, get_settings().session_secret, algorithms=["HS256"])
    except jwt.PyJWTError as e:
        raise HTTPException(400, "invalid or expired OAuth state") from e
    if claims["purpose"] != purpose or claims["uid"] != str(p.user_id) or claims["tid"] != str(p.tenant_id):
        raise HTTPException(400, "OAuth state does not match the signed-in user")


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


# -- connectors -----------------------------------------------------------------


@app.get("/connectors")
def list_accounts(p: User) -> list[dict[str, Any]]:
    with tenant_tx(p.tenant_id, p.user_id, p.role) as conn:
        rows = conn.execute(
            "SELECT id, provider, account_email::text AS account_email, status, last_error, last_synced_at, settings,"
            " created_at, (SELECT count(*) FROM sources s WHERE s.connector_account_id = ca.id) AS items"
            " FROM connector_accounts ca WHERE user_id = %s AND provider <> 'fixture' ORDER BY created_at",
            (str(p.user_id),),
        ).fetchall()
    return rows


@app.get("/connectors/providers")
def providers() -> list[dict[str, Any]]:
    s = get_settings()
    return [
        {"provider": "google", "label": "Gmail + Google Calendar", "configured": bool(s.google_client_id)},
        {
            "provider": "microsoft",
            "label": "Outlook + Microsoft 365 Calendar",
            "configured": bool(s.microsoft_client_id),
        },
        {"provider": "zoom", "label": "Zoom transcripts", "configured": bool(s.zoom_client_id)},
        {
            "provider": "google_meet",
            "label": "Google Meet transcripts",
            "configured": bool(s.google_client_id),
        },
    ]


@app.get("/connectors/{provider}/start")
def start_connect(provider: str, p: User) -> RedirectResponse:
    try:
        url = get_connector(provider).authorization_url(
            _state(p, f"connect:{provider}"), _redirect_uri(provider)
        )
    except KeyError as e:
        raise HTTPException(404, str(e)) from e
    except AuthError as e:
        raise HTTPException(503, f"{provider} is not configured: {e}") from e
    return RedirectResponse(url)


@app.get("/connectors/{provider}/callback")
async def connect_callback(
    provider: str, p: User, code: str | None = None, state: str = "", error: str | None = None
) -> RedirectResponse:
    web = get_settings().web_url
    if error or not code:
        return RedirectResponse(f"{web}/connections?error={error or 'missing_code'}")
    _verify_state(state, f"connect:{provider}", p)
    connector = get_connector(provider)
    try:
        tokens, email = connector.exchange_code(code, _redirect_uri(provider))
    except AuthError as e:
        log.warning("oauth exchange failed for %s: %s", provider, e)
        return RedirectResponse(f"{web}/connections?error=exchange_failed")
    with tenant_tx(p.tenant_id, p.user_id, p.role) as conn:
        account_id = save_account(conn, p.tenant_id, p.user_id, provider, email, tokens, connector.scopes)
    await temporal.start_account_sync(str(p.tenant_id), str(account_id))
    return RedirectResponse(f"{web}/connections?connected={provider}")


def _own_account(conn: Any, p: Principal, account_id: UUID) -> dict[str, Any]:
    row = conn.execute(
        "SELECT * FROM connector_accounts WHERE id = %s AND user_id = %s", (str(account_id), str(p.user_id))
    ).fetchone()
    if row is None:
        raise HTTPException(404, "connector account not found")
    return row


@app.get("/connectors/{account_id}/labels")
def account_labels(account_id: UUID, p: User) -> list[dict[str, str]]:
    """Gmail labels or Outlook folders, for choosing what to sync."""
    with tenant_tx(p.tenant_id, p.user_id, p.role) as conn:
        account = _own_account(conn, p, account_id)
        tokens = fresh_tokens(conn, p.tenant_id, account)
    connector = get_connector(account["provider"])
    if hasattr(connector, "list_labels") and account["provider"] == "google":
        return connector.list_labels(tokens)
    if hasattr(connector, "list_folders"):
        return connector.list_folders(tokens)
    return []


class AccountSettings(BaseModel):
    labels: list[str] | None = None
    folders: list[str] | None = None
    exclude_personal: bool | None = None
    personal_labels: list[str] | None = None
    personal_categories: list[str] | None = None
    default_visibility: str | None = Field(default=None, pattern="^(team|private)$")
    status: str | None = Field(default=None, pattern="^(active|paused)$")


@app.patch("/connectors/{account_id}")
async def update_account(account_id: UUID, body: AccountSettings, p: User) -> dict[str, Any]:
    changes = body.model_dump(exclude_none=True)
    status = changes.pop("status", None)
    with tenant_tx(p.tenant_id, p.user_id, p.role) as conn:
        account = _own_account(conn, p, account_id)
        settings = {**account["settings"], **changes}
        # Changing what is synced restarts the backfill with the new scope.
        scope_changed = any(k in changes for k in ("labels", "folders"))
        conn.execute(
            "UPDATE connector_accounts SET settings = %s, status = coalesce(%s, status),"
            " sync_cursor = CASE WHEN %s THEN '{}'::jsonb ELSE sync_cursor END WHERE id = %s",
            (Jsonb(settings), status, scope_changed, str(account_id)),
        )
        audit.record(
            conn,
            p.tenant_id,
            "connector.settings_changed",
            "connector_account",
            account_id,
            actor_type="user",
            actor_id=p.user_id,
            details={"changes": changes, "status": status},
        )
    if status == "active":
        await temporal.start_account_sync(str(p.tenant_id), str(account_id))
    return {"id": str(account_id), "settings": settings, "status": status or account["status"]}


@app.post("/connectors/{account_id}/sync")
async def sync_now(account_id: UUID, p: User, inline: bool = Query(False)) -> dict[str, Any]:
    """Kick the sync workflow, or with ?inline=true fetch one page right here
    (handy in development when the Temporal worker isn't running)."""
    with tenant_tx(p.tenant_id, p.user_id, p.role) as conn:
        _own_account(conn, p, account_id)
    if inline:
        try:
            stats = sync_once(p.tenant_id, account_id)
        except AuthError as e:
            raise HTTPException(409, f"reconnect required: {e}") from e
        return {"mode": "inline", **stats.__dict__}
    workflow_id = await temporal.start_account_sync(str(p.tenant_id), str(account_id))
    if workflow_id is None:
        raise HTTPException(503, "workflow engine unavailable; retry with ?inline=true")
    return {"mode": "workflow", "workflow_id": workflow_id}


@app.delete("/connectors/{account_id}")
def disconnect(account_id: UUID, p: User) -> dict[str, str]:
    with tenant_tx(p.tenant_id, p.user_id, p.role) as conn:
        _own_account(conn, p, account_id)
        conn.execute(
            "UPDATE connector_accounts SET status = 'revoked', encrypted_tokens = NULL WHERE id = %s",
            (str(account_id),),
        )
        audit.record(
            conn,
            p.tenant_id,
            "connector.revoked",
            "connector_account",
            account_id,
            actor_type="user",
            actor_id=p.user_id,
        )
    return {"status": "revoked"}


# -- CRM import -----------------------------------------------------------------


def _require_import_role(p: Principal) -> None:
    if p.role not in MANAGE_IMPORT_ROLES:
        raise HTTPException(403, "only admins, partners and platform staff can import CRM data")


@app.post("/imports/csv")
async def import_csv(
    p: User,
    vendor: Annotated[str, Form()],
    file: Annotated[UploadFile, File()],
    object_type: Annotated[str | None, Form()] = None,
) -> dict[str, Any]:
    _require_import_role(p)
    if vendor not in VENDORS:
        raise HTTPException(400, f"vendor must be one of {VENDORS}")
    data = await file.read(MAX_CSV_BYTES + 1)
    if len(data) > MAX_CSV_BYTES:
        raise HTTPException(413, "CSV larger than 20 MB; split it or use the API import")
    try:
        records = parse_csv(data, vendor, object_type or None)
    except (UnicodeDecodeError, ValueError) as e:
        raise HTTPException(400, f"could not parse CSV: {e}") from e
    with tenant_tx(p.tenant_id, p.user_id, "service") as conn:
        source_id = land(
            conn,
            p.tenant_id,
            f"crm_{vendor}",
            RawItem(
                "crm_export",
                f"csv:{hashlib.sha256(data).hexdigest()}",
                data,
                "text/csv",
                {"filename": file.filename, "object_type": object_type},
            ),
        )
        if source_id is None:
            raise HTTPException(409, "this exact file has already been imported")
        result = import_records(conn, p.tenant_id, vendor, records, source_id=source_id, actor_id=p.user_id)
    return {"source_id": str(source_id), **result.__dict__}


class ApiImport(BaseModel):
    vendor: str
    credentials: dict[str, Any]


@app.post("/imports/api")
async def import_api(body: ApiImport, p: User) -> dict[str, str]:
    _require_import_role(p)
    if body.vendor not in VENDORS:
        raise HTTPException(400, f"vendor must be one of {VENDORS}")
    with tenant_tx(p.tenant_id, p.user_id, p.role) as conn:
        sealed = seal(conn, p.tenant_id, body.credentials)
    try:
        workflow_id = await temporal.start_crm_import(str(p.tenant_id), str(p.user_id), body.vendor, sealed)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(503, f"workflow engine unavailable: {e}") from e
    return {"workflow_id": workflow_id}


# -- Slack ----------------------------------------------------------------------


@app.get("/slack/install")
def slack_install(p: User) -> RedirectResponse:
    if p.role != "admin":
        raise HTTPException(403, "only admins can install the Slack app")
    try:
        return RedirectResponse(
            slack.install_url(_state(p, "slack"), f"{get_settings().ingest_public_url}/slack/callback")
        )
    except RuntimeError as e:
        raise HTTPException(503, str(e)) from e


@app.get("/slack/callback")
def slack_callback(
    p: User, code: str | None = None, state: str = "", error: str | None = None
) -> RedirectResponse:
    web = get_settings().web_url
    if error or not code:
        return RedirectResponse(f"{web}/settings?slack_error={error or 'missing_code'}")
    _verify_state(state, "slack", p)
    with tenant_tx(p.tenant_id, p.user_id, p.role) as conn:
        slack.complete_install(
            conn, p.tenant_id, p.user_id, code, f"{get_settings().ingest_public_url}/slack/callback"
        )
    return RedirectResponse(f"{web}/settings?slack=installed")


class SlackSettings(BaseModel):
    deal_channel_id: str = Field(pattern=r"^[CG][A-Z0-9]{6,}$")


@app.get("/slack")
def slack_status(p: User) -> dict[str, Any]:
    with tenant_tx(p.tenant_id, p.user_id, p.role) as conn:
        row = conn.execute(
            "SELECT team_id, team_name, deal_channel_id, created_at FROM slack_installations"
        ).fetchone()
    return {"installed": row is not None, **(row or {})}


@app.patch("/slack")
def slack_settings(body: SlackSettings, p: User) -> dict[str, str]:
    if p.role != "admin":
        raise HTTPException(403, "only admins can change Slack settings")
    with tenant_tx(p.tenant_id, p.user_id, p.role) as conn:
        updated = conn.execute(
            "UPDATE slack_installations SET deal_channel_id = %s RETURNING team_id", (body.deal_channel_id,)
        ).fetchone()
        if updated is None:
            raise HTTPException(404, "Slack is not installed")
        audit.record(
            conn,
            p.tenant_id,
            "slack.settings_changed",
            "slack_installation",
            updated["team_id"],
            actor_type="user",
            actor_id=p.user_id,
            details={"deal_channel_id": body.deal_channel_id},
        )
    return {"deal_channel_id": body.deal_channel_id}
