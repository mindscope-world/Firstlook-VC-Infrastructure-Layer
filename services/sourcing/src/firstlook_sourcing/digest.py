"""Weekly sourcing digest: the top companies per active thesis, flagging the
ones that are new to the list this week. Sent by email to the investment
team and posted to the Slack deal channel when one is configured."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import httpx
import psycopg

from firstlook_core import audit
from firstlook_core.adapters.mailer import Mailer, get_mailer
from firstlook_core.config import get_settings

log = logging.getLogger("firstlook.sourcing.digest")
DIGEST_ROLES = ("admin", "partner", "associate")


@dataclass
class DigestItem:
    company_id: Any
    name: str
    rank: int
    score: float
    rationale: str | None
    new: bool


def build(
    conn: psycopg.Connection, now: datetime | None = None, top: int = 10
) -> dict[str, list[DigestItem]]:
    now = now or datetime.now(UTC)
    week_ago = now - timedelta(days=7)
    out: dict[str, list[DigestItem]] = {}
    for t in conn.execute("SELECT id, name FROM current_thesis_versions WHERE active").fetchall():
        run = conn.execute(
            "SELECT id FROM score_runs WHERE thesis_version_id IN (SELECT id FROM thesis_versions WHERE thesis_id ="
            " (SELECT thesis_id FROM thesis_versions WHERE id = %s)) AND status = 'done'"
            " ORDER BY started_at DESC LIMIT 1",
            (t["id"],),
        ).fetchone()
        if not run:
            continue
        rows = conn.execute(
            """SELECT s.company_id, c.name, s.rank, s.final_score, s.rationale,
                      NOT EXISTS (SELECT 1 FROM company_scores p JOIN score_runs r ON r.id = p.run_id
                                   WHERE p.company_id = s.company_id AND p.rank <= %(top)s
                                     AND r.started_at < %(week_ago)s) AS new
                 FROM company_scores s JOIN companies c ON c.id = s.company_id
                WHERE s.run_id = %(run)s ORDER BY s.rank LIMIT %(top)s""",
            {"run": run["id"], "top": top, "week_ago": week_ago},
        ).fetchall()
        out[t["name"]] = [
            DigestItem(r["company_id"], r["name"], r["rank"], r["final_score"], r["rationale"], r["new"])
            for r in rows
        ]
    return out


def render_text(tenant_name: str, digest: dict[str, list[DigestItem]], web_url: str) -> str:
    lines = [f"Firstlook sourcing digest for {tenant_name}", ""]
    for thesis, items in digest.items():
        lines.append(f"== {thesis} ==")
        for i in items:
            flag = " [new]" if i.new else ""
            lines.append(f"{i.rank}. {i.name}{flag} (score {i.score:.2f})")
            if i.rationale:
                lines.append(f"   {i.rationale}")
            lines.append(f"   {web_url}/companies/{i.company_id}")
        lines.append("")
    lines.append(f"Open the feed: {web_url}/sourcing")
    return "\n".join(lines)


def send(
    conn: psycopg.Connection,
    tenant_id: UUID | str,
    *,
    mailer: Mailer | None = None,
    http: httpx.Client | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    digest = build(conn, now)
    if not any(digest.values()):
        return {"sent": 0, "slack": False}
    tenant = conn.execute("SELECT name FROM tenants WHERE id = %s", (str(tenant_id),)).fetchone()
    web = get_settings().web_url
    text = render_text(tenant["name"], digest, web)
    recipients = [
        r["email"]
        for r in conn.execute(
            "SELECT email::text AS email FROM users WHERE role::text = ANY(%s)", (list(DIGEST_ROLES),)
        ).fetchall()
    ]
    mailer = mailer or get_mailer()
    if recipients:
        mailer.send(recipients, f"Sourcing digest: {sum(len(v) for v in digest.values())} companies", text)

    slack_posted = False
    try:
        from firstlook_ingest.slack import bot_token

        installed = bot_token(conn, UUID(str(tenant_id)))
    except ImportError:
        installed = None
    if installed and installed[1]:
        token, channel = installed
        new_items = [i for items in digest.values() for i in items if i.new][:10]
        summary = "\n".join(
            f"• <{web}/companies/{i.company_id}|{i.name}> (score {i.score:.2f})" for i in new_items
        )
        body = (
            (http or httpx.Client(timeout=15))
            .post(
                "https://slack.com/api/chat.postMessage",
                headers={"Authorization": f"Bearer {token}"},
                json={
                    "channel": channel,
                    "text": f":mag: *Weekly sourcing digest*: {len(new_items)} new this week\n"
                    f"{summary or 'No new companies.'}\n<{web}/sourcing|Open the feed>",
                },
            )
            .json()
        )
        slack_posted = bool(body.get("ok"))
    audit.record(
        conn,
        tenant_id,
        "sourcing.digest_sent",
        "digest",
        None,
        actor_type="service",
        details={"recipients": len(recipients), "slack": slack_posted},
    )
    return {"sent": len(recipients), "slack": slack_posted}
