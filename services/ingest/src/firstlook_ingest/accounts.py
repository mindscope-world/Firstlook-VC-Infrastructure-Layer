"""Connector accounts: encrypted token storage and one sync step."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any
from uuid import UUID

import psycopg
from psycopg.types.json import Jsonb

from firstlook_core import audit
from firstlook_core.crypto import tenant_cipher
from firstlook_core.db import tenant_tx
from firstlook_core.objects import TenantObjects

from .connectors.base import AuthError, OAuthTokens, get_connector
from .raw import land

log = logging.getLogger("firstlook.ingest")


@dataclass
class SyncStats:
    stored: int
    duplicates: int
    skipped: int
    done: bool


def save_account(
    conn: psycopg.Connection,
    tenant_id: UUID,
    user_id: UUID,
    provider: str,
    email: str,
    tokens: OAuthTokens,
    scopes: list[str],
) -> UUID:
    cipher = tenant_cipher(conn, tenant_id)
    row = conn.execute(
        """
        INSERT INTO connector_accounts (tenant_id, user_id, provider, account_email, scopes, encrypted_tokens, status)
        VALUES (%s, %s, %s, %s, %s, %s, 'active')
        ON CONFLICT (tenant_id, provider, account_email) DO UPDATE
            SET encrypted_tokens = EXCLUDED.encrypted_tokens, scopes = EXCLUDED.scopes, status = 'active',
                last_error = NULL, user_id = EXCLUDED.user_id
        RETURNING id
        """,
        (str(tenant_id), str(user_id), provider, email, scopes, cipher.encrypt_json(tokens.to_dict())),
    ).fetchone()
    audit.record(
        conn,
        tenant_id,
        "connector.connected",
        "connector_account",
        row["id"],
        actor_type="user",
        actor_id=user_id,
        details={"provider": provider, "account": email, "scopes": scopes},
    )
    return row["id"]


def load_tokens(conn: psycopg.Connection, tenant_id: UUID, account: dict[str, Any]) -> OAuthTokens:
    if account["encrypted_tokens"] is None:
        raise AuthError("account has no stored credentials")
    return OAuthTokens.from_dict(
        tenant_cipher(conn, tenant_id).decrypt_json(bytes(account["encrypted_tokens"]))
    )


def fresh_tokens(conn: psycopg.Connection, tenant_id: UUID, account: dict[str, Any]) -> OAuthTokens:
    tokens = load_tokens(conn, tenant_id, account)
    if tokens.expired:
        tokens = get_connector(account["provider"]).refresh(tokens)
        conn.execute(
            "UPDATE connector_accounts SET encrypted_tokens = %s WHERE id = %s",
            (tenant_cipher(conn, tenant_id).encrypt_json(tokens.to_dict()), account["id"]),
        )
    return tokens


def sync_once(tenant_id: UUID | str, account_id: UUID | str) -> SyncStats:
    """Fetch and land one page for an account. Raises AuthError (not retryable)
    or RateLimited (retry later); the cursor only advances after the page's
    items are stored, so a crash mid-page re-fetches rather than loses data."""
    tenant_id = UUID(str(tenant_id))
    with tenant_tx(tenant_id) as conn:
        account = conn.execute(
            "SELECT * FROM connector_accounts WHERE id = %s", (str(account_id),)
        ).fetchone()
        if account is None:
            raise LookupError(f"connector account {account_id} not found")
        if account["status"] in ("paused", "revoked"):
            return SyncStats(0, 0, 0, True)
        try:
            tokens = fresh_tokens(conn, tenant_id, account)
        except AuthError as e:
            conn.execute(
                "UPDATE connector_accounts SET status = 'error', last_error = %s WHERE id = %s",
                (str(e), account["id"]),
            )
            raise
        cursor, settings, provider = account["sync_cursor"], account["settings"], account["provider"]

    connector = get_connector(provider)
    try:
        page = connector.sync(tokens, settings, cursor)
    except AuthError as e:
        with tenant_tx(tenant_id) as conn:
            conn.execute(
                "UPDATE connector_accounts SET status = 'error', last_error = %s WHERE id = %s",
                (str(e), str(account_id)),
            )
        raise

    stored = dup = 0
    with tenant_tx(tenant_id) as conn:
        objects = TenantObjects(conn, tenant_id)
        for item in page.items:
            if land(conn, tenant_id, provider, item, account_id=account_id, objects=objects):
                stored += 1
            else:
                dup += 1
        conn.execute(
            "UPDATE connector_accounts SET sync_cursor = %s, last_synced_at = now(), status = 'active',"
            " last_error = NULL WHERE id = %s",
            (Jsonb(page.cursor), str(account_id)),
        )
    log.info(
        "sync %s/%s: stored=%d dup=%d skipped=%d done=%s",
        provider,
        account_id,
        stored,
        dup,
        page.skipped,
        page.done,
    )
    return SyncStats(stored, dup, page.skipped, page.done)
