"""Slack app v1: workspace install (OAuth v2) and deal-channel notifications.

The /firstlook slash command is served by services/api (it reads the graph);
this module owns the bot token and posts notifications from bus events.
"""

from __future__ import annotations

import logging
import urllib.parse
from typing import Any
from uuid import UUID

import httpx
import psycopg

from firstlook_core import audit
from firstlook_core.adapters.bus import Event, run_consumer
from firstlook_core.config import get_settings
from firstlook_core.crypto import tenant_cipher
from firstlook_core.db import tenant_tx
from firstlook_core.outbox import Topics

log = logging.getLogger("firstlook.slack")

BOT_SCOPES = ["commands", "chat:write", "channels:read", "groups:read"]
STAGE_LABELS = {
    "sourced": "Sourced",
    "screening": "Screening",
    "diligence": "Diligence",
    "ic": "IC",
    "term_sheet": "Term sheet",
    "invested": "Invested",
    "passed": "Passed",
}


def install_url(state: str, redirect_uri: str) -> str:
    s = get_settings()
    if not s.slack_client_id:
        raise RuntimeError("SLACK_CLIENT_ID is not configured")
    return "https://slack.com/oauth/v2/authorize?" + urllib.parse.urlencode(
        {
            "client_id": s.slack_client_id,
            "scope": ",".join(BOT_SCOPES),
            "redirect_uri": redirect_uri,
            "state": state,
        }
    )


def complete_install(
    conn: psycopg.Connection,
    tenant_id: UUID,
    user_id: UUID,
    code: str,
    redirect_uri: str,
    http: httpx.Client | None = None,
) -> dict[str, Any]:
    s = get_settings()
    http = http or httpx.Client(timeout=30)
    body = http.post(
        "https://slack.com/api/oauth.v2.access",
        data={
            "code": code,
            "redirect_uri": redirect_uri,
            "client_id": s.slack_client_id,
            "client_secret": s.slack_client_secret,
        },
    ).json()
    if not body.get("ok"):
        raise RuntimeError(f"slack install failed: {body.get('error')}")
    team = body["team"]
    conn.execute(
        """
        INSERT INTO slack_installations (tenant_id, team_id, team_name, encrypted_bot_token, installed_by)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (tenant_id) DO UPDATE SET team_id = EXCLUDED.team_id, team_name = EXCLUDED.team_name,
            encrypted_bot_token = EXCLUDED.encrypted_bot_token, installed_by = EXCLUDED.installed_by
        """,
        (
            str(tenant_id),
            team["id"],
            team.get("name"),
            tenant_cipher(conn, tenant_id).encrypt(body["access_token"].encode()),
            str(user_id),
        ),
    )
    audit.record(
        conn,
        tenant_id,
        "slack.installed",
        "slack_installation",
        team["id"],
        actor_type="user",
        actor_id=user_id,
    )
    return {"team_id": team["id"], "team_name": team.get("name")}


def bot_token(conn: psycopg.Connection, tenant_id: UUID) -> tuple[str, str | None] | None:
    row = conn.execute(
        "SELECT encrypted_bot_token, deal_channel_id FROM slack_installations WHERE tenant_id = %s",
        (str(tenant_id),),
    ).fetchone()
    if row is None:
        return None
    return tenant_cipher(conn, tenant_id).decrypt(bytes(row["encrypted_bot_token"])).decode(), row[
        "deal_channel_id"
    ]


def deal_message(event: dict[str, Any], web_url: str) -> dict[str, Any]:
    kind = event.get("type")
    name = event.get("name", "A deal")
    link = f"{web_url}/deals/{event['deal_id']}"
    if kind == "deal.created":
        text = f":seedling: *{name}* added to the pipeline"
    elif kind == "deal.stage_changed":
        text = (
            f":arrow_right: *{name}* moved from {STAGE_LABELS.get(event.get('from_stage'), event.get('from_stage'))}"
            f" to *{STAGE_LABELS.get(event.get('stage'), event.get('stage'))}*"
        )
    else:
        text = f"*{name}* updated"
    if event.get("actor_name"):
        text += f" by {event['actor_name']}"
    return {
        "text": text,
        "blocks": [
            {"type": "section", "text": {"type": "mrkdwn", "text": text}},
            {"type": "context", "elements": [{"type": "mrkdwn", "text": f"<{link}|Open in Firstlook>"}]},
        ],
    }


def handle_deal_event(event: Event, http: httpx.Client | None = None) -> bool:
    p = event.payload
    tenant_id = UUID(p["tenant_id"])
    with tenant_tx(tenant_id) as conn:
        restricted = conn.execute("SELECT restricted FROM deals WHERE id = %s", (p["deal_id"],)).fetchone()
        installed = bot_token(conn, tenant_id)
    if installed is None or installed[1] is None:
        return False
    if restricted and restricted["restricted"]:
        return False  # restricted deals never leave the deal team
    token, channel = installed
    http = http or httpx.Client(timeout=15)
    body = http.post(
        "https://slack.com/api/chat.postMessage",
        headers={"Authorization": f"Bearer {token}"},
        json={"channel": channel, **deal_message(p, get_settings().web_url)},
    ).json()
    if not body.get("ok"):
        raise RuntimeError(f"slack post failed: {body.get('error')}")
    return True


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    run_consumer([Topics.DEAL_EVENTS], "slack-notifier", handle_deal_event)


if __name__ == "__main__":
    main()
