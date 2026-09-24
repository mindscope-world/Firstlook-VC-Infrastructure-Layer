"""Raw source object -> interaction resolved into the graph.

Each process_* function is idempotent: interactions are keyed by
(tenant, kind, external_id), so replaying an event is harmless.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

import psycopg
from psycopg.types.json import Jsonb

from firstlook_core import outbox
from firstlook_core.embeddings import to_pgvector
from firstlook_core.llm import LlmClient, get_llm
from firstlook_core.objects import TenantObjects

from . import strength
from .er import Resolver, is_business_domain
from .parsing import clean_body, parse_rfc822, parse_signature

log = logging.getLogger(__name__)

CHUNK_CHARS = 1500


@dataclass
class ProcessResult:
    interaction_id: UUID | None
    skipped: str | None = None
    created: bool = False


def _is_automated(headers: dict[str, str]) -> bool:
    lowered = {k.lower(): v.lower() for k, v in headers.items()}
    if lowered.get("auto-submitted", "no") != "no":
        return True
    if lowered.get("precedence") in ("bulk", "list", "junk"):
        return True
    return "list-unsubscribe" in lowered


def _chunks(text: str) -> list[str]:
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    out, current = [], ""
    for p in paragraphs:
        if current and len(current) + len(p) > CHUNK_CHARS:
            out.append(current)
            current = ""
        current = f"{current}\n\n{p}" if current else p
        while len(current) > CHUNK_CHARS:
            out.append(current[:CHUNK_CHARS])
            current = current[CHUNK_CHARS:]
    if current:
        out.append(current)
    return out


class Pipeline:
    def __init__(
        self,
        conn: psycopg.Connection,
        tenant_id: UUID | str,
        *,
        llm: LlmClient | None = None,
        objects: TenantObjects | None = None,
    ):
        self.conn = conn
        self.tenant_id = str(tenant_id)
        self.llm = llm or get_llm()
        self._objects = objects
        self.resolver = Resolver(conn, tenant_id, self.llm)

    @property
    def objects(self) -> TenantObjects:
        if self._objects is None:
            self._objects = TenantObjects(self.conn, self.tenant_id)
        return self._objects

    # -- shared ----------------------------------------------------------------

    def _insert_interaction(self, **fields: Any) -> tuple[UUID, bool]:
        row = self.conn.execute(
            """
            INSERT INTO interactions (tenant_id, source_id, kind, external_id, thread_id, subject, occurred_at,
                body_text, body_full_text, signature, direction, owner_user_id, visibility, metadata)
            VALUES (%(tenant_id)s, %(source_id)s, %(kind)s, %(external_id)s, %(thread_id)s, %(subject)s,
                %(occurred_at)s, %(body_text)s, %(body_full_text)s, %(signature)s, %(direction)s,
                %(owner_user_id)s, %(visibility)s, %(metadata)s)
            ON CONFLICT (tenant_id, kind, external_id) DO NOTHING
            RETURNING id
            """,
            {"tenant_id": self.tenant_id, "metadata": Jsonb(fields.pop("metadata", {})), **fields},
        ).fetchone()
        if row:
            return row["id"], True
        existing = self.conn.execute(
            "SELECT id FROM interactions WHERE tenant_id = %s AND kind = %s AND external_id = %s",
            (self.tenant_id, fields["kind"], fields["external_id"]),
        ).fetchone()
        return existing["id"], False

    def _add_participant(
        self, interaction_id: UUID, person_id: UUID | None, email: str | None, name: str | None, role: str
    ) -> None:
        self.conn.execute(
            "INSERT INTO interaction_participants (tenant_id, interaction_id, person_id, email, display_name, role)"
            " VALUES (%s, %s, %s, %s, %s, %s)",
            (self.tenant_id, interaction_id, person_id, email, name, role),
        )

    def _index_chunks(
        self, interaction_id: UUID, source_id: UUID | None, text: str, owner: UUID | None, visibility: str
    ) -> None:
        pieces = _chunks(text)
        if not pieces:
            return
        vectors = self.llm.embed(self.tenant_id, pieces, task="embed.chunk")
        for ordinal, (piece, vec) in enumerate(zip(pieces, vectors, strict=True)):
            self.conn.execute(
                "INSERT INTO chunks (tenant_id, source_id, interaction_id, ordinal, text, embedding,"
                " owner_user_id, visibility) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                (
                    self.tenant_id,
                    source_id,
                    interaction_id,
                    ordinal,
                    piece,
                    to_pgvector(vec),
                    owner,
                    visibility,
                ),
            )

    def _internal(self, person_ids: list[UUID]) -> set[UUID]:
        if not person_ids:
            return set()
        rows = self.conn.execute(
            "SELECT id FROM people WHERE id = ANY(%s) AND is_internal", (person_ids,)
        ).fetchall()
        return {r["id"] for r in rows}

    def _finish(self, interaction_id: UUID, kind: str, people: list[UUID]) -> None:
        self.conn.execute("UPDATE interactions SET processed_at = now() WHERE id = %s", (interaction_id,))
        strength.recompute(self.conn, self.tenant_id, people=[p for p in people if p])
        outbox.enqueue(
            self.conn,
            self.tenant_id,
            outbox.Topics.INTERACTION_RESOLVED,
            {"interaction_id": str(interaction_id), "kind": kind},
            key=str(interaction_id),
        )

    # -- email -----------------------------------------------------------------

    def process_email(
        self,
        raw: bytes,
        *,
        source_id: UUID | None = None,
        owner_user_id: UUID | None = None,
        visibility: str = "team",
        extra_metadata: dict[str, Any] | None = None,
    ) -> ProcessResult:
        email = parse_rfc822(raw)
        if _is_automated(email.headers):
            return ProcessResult(None, skipped="automated")
        if email.from_ is None:
            return ProcessResult(None, skipped="no_sender")

        full, body, signature = clean_body(email)

        resolved: list[tuple[str, Any, UUID | None]] = []
        seen: set[tuple[str, str]] = set()
        for role, addr in email.participants:
            if (role, addr.email) in seen:
                continue
            seen.add((role, addr.email))
            title = company_id = None
            if role == "from" and signature:
                info = parse_signature(signature, addr.name)
                title = info.title
                if info.company and not is_business_domain(addr.email.rsplit("@", 1)[1]):
                    company = self.resolver.resolve_company(name=info.company, source_id=source_id)
                    company_id = company.entity_id if company else None
            res = self.resolver.resolve_person(
                email=addr.email,
                name=addr.name,
                title=title,
                company_id=company_id,
                source_id=source_id,
                context=email.subject,
            )
            resolved.append((role, addr, res.entity_id if res else None))

        person_ids = [pid for _, _, pid in resolved if pid]
        internal = self._internal(person_ids)
        sender_id = resolved[0][2] if resolved and resolved[0][0] == "from" else None
        if person_ids and all(p in internal for p in person_ids):
            direction = "internal"
        elif sender_id in internal:
            direction = "outbound"
        else:
            direction = "inbound"

        interaction_id, created = self._insert_interaction(
            source_id=source_id,
            kind="email",
            external_id=email.message_id,
            thread_id=email.thread_key,
            subject=email.subject,
            occurred_at=email.date,
            body_text=body,
            body_full_text=full,
            signature=signature,
            direction=direction,
            owner_user_id=owner_user_id,
            visibility=visibility,
            metadata={
                "in_reply_to": email.in_reply_to,
                "attachment_count": len(email.attachments),
                **(extra_metadata or {}),
            },
        )
        if not created:
            return ProcessResult(interaction_id, created=False)

        for role, addr, pid in resolved:
            self._add_participant(interaction_id, pid, addr.email, addr.name, role)

        for att in email.attachments:
            uri = self.objects.put("attachments", att.data, att.content_type)
            self.conn.execute(
                "INSERT INTO attachments (tenant_id, interaction_id, filename, content_type, size_bytes, sha256,"
                " object_uri) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                (
                    self.tenant_id,
                    interaction_id,
                    att.filename,
                    att.content_type,
                    len(att.data),
                    att.sha256,
                    uri,
                ),
            )

        self._index_chunks(interaction_id, source_id, f"{email.subject}\n\n{body}", owner_user_id, visibility)
        self._finish(interaction_id, "email", person_ids)
        return ProcessResult(interaction_id, created=True)

    # -- calendar --------------------------------------------------------------

    def process_meeting(
        self,
        event: dict[str, Any],
        *,
        source_id: UUID | None = None,
        owner_user_id: UUID | None = None,
        visibility: str = "team",
    ) -> ProcessResult:
        """event: normalised calendar event (see firstlook_ingest.connectors.base.MeetingEvent)."""
        if event.get("status") == "cancelled":
            return ProcessResult(None, skipped="cancelled")
        attendees = [a for a in event.get("attendees", []) if a.get("response") != "declined"]
        people: list[tuple[str, dict, UUID | None]] = []
        organizer = event.get("organizer")
        if organizer and organizer.get("email"):
            res = self.resolver.resolve_person(
                email=organizer["email"],
                name=organizer.get("name"),
                source_id=source_id,
                context=event.get("title"),
            )
            people.append(("organizer", organizer, res.entity_id if res else None))
        for a in attendees:
            if not a.get("email") or (organizer and a["email"].lower() == organizer.get("email", "").lower()):
                continue
            res = self.resolver.resolve_person(
                email=a["email"], name=a.get("name"), source_id=source_id, context=event.get("title")
            )
            people.append(("attendee", a, res.entity_id if res else None))

        person_ids = [p for _, _, p in people if p]
        internal = self._internal(person_ids)
        if not any(p not in internal for p in person_ids):
            return ProcessResult(None, skipped="internal_only")

        description = (event.get("description") or "").strip()
        interaction_id, created = self._insert_interaction(
            source_id=source_id,
            kind="meeting",
            external_id=event["id"],
            thread_id=event.get("series_id"),
            subject=event.get("title"),
            occurred_at=datetime.fromisoformat(event["start"]),
            body_text=description,
            body_full_text=description,
            signature=None,
            direction="internal",
            owner_user_id=owner_user_id,
            visibility=visibility,
            metadata={
                "end": event.get("end"),
                "location": event.get("location"),
                "conference_id": event.get("conference_id"),
            },
        )
        if not created:
            return ProcessResult(interaction_id)
        for role, a, pid in people:
            self._add_participant(interaction_id, pid, a.get("email"), a.get("name"), role)
        if description:
            self._index_chunks(
                interaction_id, source_id, f"{event.get('title')}\n\n{description}", owner_user_id, visibility
            )
        self._finish(interaction_id, "meeting", person_ids)
        return ProcessResult(interaction_id, created=True)

    # -- transcripts -----------------------------------------------------------

    def process_transcript(
        self,
        transcript: dict[str, Any],
        *,
        source_id: UUID | None = None,
        owner_user_id: UUID | None = None,
        visibility: str = "team",
    ) -> ProcessResult:
        """transcript: normalised call transcript (see firstlook_ingest.connectors.base.Transcript)."""
        speakers: dict[str, UUID | None] = {}
        participants = transcript.get("participants", [])
        by_name = {p.get("name", "").lower(): p for p in participants if p.get("name")}
        for p in participants:
            res = self.resolver.resolve_person(
                email=p.get("email"), name=p.get("name"), source_id=source_id, context=transcript.get("title")
            )
            key = (p.get("name") or p.get("email") or "").lower()
            if key:
                speakers[key] = res.entity_id if res else None
                by_name.setdefault(key, p)
        for seg in transcript.get("segments", []):
            name = (seg.get("speaker") or "").strip()
            if name and name.lower() not in speakers:
                known = by_name.get(name.lower(), {})
                res = self.resolver.resolve_person(
                    email=known.get("email"), name=name, source_id=source_id, context=transcript.get("title")
                )
                speakers[name.lower()] = res.entity_id if res else None

        lines = [
            f"{seg.get('speaker') or 'Unknown'}: {seg['text'].strip()}"
            for seg in transcript.get("segments", [])
            if seg.get("text", "").strip()
        ]
        text = "\n".join(lines)
        interaction_id, created = self._insert_interaction(
            source_id=source_id,
            kind="transcript",
            external_id=transcript["id"],
            thread_id=transcript.get("meeting_external_id"),
            subject=transcript.get("title"),
            occurred_at=datetime.fromisoformat(transcript["start"]),
            body_text=text,
            body_full_text=text,
            signature=None,
            direction="internal",
            owner_user_id=owner_user_id,
            visibility=visibility,
            metadata={"provider": transcript.get("provider"), "duration_s": transcript.get("duration_s")},
        )
        if not created:
            return ProcessResult(interaction_id)
        for name, pid in speakers.items():
            known = by_name.get(name, {})
            self._add_participant(
                interaction_id, pid, known.get("email"), known.get("name") or name, "speaker"
            )
        self._index_chunks(interaction_id, source_id, text, owner_user_id, visibility)
        person_ids = [p for p in speakers.values() if p]
        self._finish(interaction_id, "transcript", person_ids)
        return ProcessResult(interaction_id, created=True)
