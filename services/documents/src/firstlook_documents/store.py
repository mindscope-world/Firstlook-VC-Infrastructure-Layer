"""Storing documents and parsing them into pages.

Flow (each step is a separate bus event, so a slow parse or OCR never blocks
ingestion, and every step can be retried on its own):

    upload / email attachment -> store_document -> documents.stored
    documents.stored          -> parse_document -> documents.parsed
    documents.parsed          -> fact-sheet extraction (services/ai)
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import UUID

import psycopg

from firstlook_core import audit, outbox
from firstlook_core.adapters.ocr import OcrEngine
from firstlook_core.objects import TenantObjects

from .parse import UnsupportedFormat, detect_format, parse

log = logging.getLogger("firstlook.documents")

MAX_DOCUMENT_BYTES = 50 * 1024 * 1024
_SUFFIX = {"pdf": ".pdf", "pptx": ".pptx", "xlsx": ".xlsx", "image": "", "text": ".txt"}


@dataclass
class Stored:
    document_id: UUID
    created: bool


def store_document(
    conn: psycopg.Connection,
    tenant_id: UUID | str,
    data: bytes,
    *,
    filename: str,
    content_type: str | None,
    origin: str,
    uploaded_by: UUID | str | None = None,
    company_id: UUID | str | None = None,
    deal_id: UUID | str | None = None,
    interaction_id: UUID | str | None = None,
    attachment_id: UUID | str | None = None,
    owner_user_id: UUID | str | None = None,
    visibility: str = "team",
    objects: TenantObjects | None = None,
) -> Stored:
    """Store a document once per tenant (by content hash) and queue it for
    parsing. Re-storing identical bytes returns the existing document."""
    if len(data) > MAX_DOCUMENT_BYTES:
        raise ValueError(f"document larger than {MAX_DOCUMENT_BYTES // (1024 * 1024)} MB")
    sha = hashlib.sha256(data).hexdigest()
    existing = conn.execute("SELECT id FROM documents WHERE sha256 = %s", (sha,)).fetchone()
    if existing:
        return Stored(existing["id"], False)

    fmt = detect_format(data, filename, content_type)
    objects = objects or TenantObjects(conn, tenant_id)
    uri = objects.put(
        "documents", data, content_type or "application/octet-stream", _SUFFIX.get(fmt or "", "")
    )
    row = conn.execute(
        "INSERT INTO documents (tenant_id, origin, interaction_id, attachment_id, company_id, deal_id, filename,"
        " content_type, format, size_bytes, sha256, object_uri, status, owner_user_id, visibility, uploaded_by)"
        " VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
        " ON CONFLICT (tenant_id, sha256) DO NOTHING RETURNING id",
        (
            str(tenant_id),
            origin,
            _s(interaction_id),
            _s(attachment_id),
            _s(company_id),
            _s(deal_id),
            Path(filename).name[:255] or "document",
            content_type or "application/octet-stream",
            fmt,
            len(data),
            sha,
            uri,
            "pending" if fmt else "unsupported",
            _s(owner_user_id),
            visibility,
            _s(uploaded_by),
        ),
    ).fetchone()
    if row is None:
        # Same bytes already stored: either a concurrent insert won, or the
        # existing document is one the caller can't see (private or on a
        # restricted deal), in which case it must not be revealed.
        existing = conn.execute("SELECT id FROM documents WHERE sha256 = %s", (sha,)).fetchone()
        if existing is None:
            raise LookupError("this file has already been uploaded to the fund by someone else")
        return Stored(existing["id"], False)

    audit.record(
        conn,
        tenant_id,
        "document.stored",
        "document",
        row["id"],
        actor_type="user" if uploaded_by else "service",
        actor_id=uploaded_by,
        details={"origin": origin, "filename": filename, "format": fmt, "size_bytes": len(data)},
    )
    if fmt:
        outbox.enqueue(
            conn,
            tenant_id,
            outbox.Topics.DOCUMENT_STORED,
            {"document_id": str(row["id"])},
            key=str(row["id"]),
        )
    return Stored(row["id"], True)


def _s(v: Any) -> str | None:
    return str(v) if v else None


def documents_from_interaction(
    conn: psycopg.Connection, tenant_id: UUID | str, interaction_id: UUID | str
) -> list[UUID]:
    """Promote an interaction's document-like attachments (decks, models) to
    documents. The company is the external sender's, when known."""
    rows = conn.execute(
        "SELECT a.id, a.filename, a.content_type, a.object_uri, i.owner_user_id, i.visibility, i.deal_id,"
        " (SELECT p.company_id FROM interaction_participants ip JOIN people p ON p.id = ip.person_id"
        "   WHERE ip.interaction_id = i.id AND ip.role = 'from' AND NOT p.is_internal LIMIT 1) AS company_id"
        " FROM attachments a JOIN interactions i ON i.id = a.interaction_id"
        " WHERE a.interaction_id = %s AND NOT EXISTS (SELECT 1 FROM documents d WHERE d.attachment_id = a.id)",
        (str(interaction_id),),
    ).fetchall()
    objects = TenantObjects(conn, tenant_id)
    ids: list[UUID] = []
    for a in rows:
        data = objects.get(a["object_uri"])
        if detect_format(data, a["filename"], a["content_type"]) not in ("pdf", "pptx", "xlsx"):
            continue  # signatures, logos and calendar files are not diligence documents
        stored = store_document(
            conn,
            tenant_id,
            data,
            filename=a["filename"] or "attachment",
            content_type=a["content_type"],
            origin="email_attachment",
            company_id=a["company_id"],
            deal_id=a["deal_id"],
            interaction_id=interaction_id,
            attachment_id=a["id"],
            owner_user_id=a["owner_user_id"],
            visibility=a["visibility"],
            objects=objects,
        )
        if stored.created:
            ids.append(stored.document_id)
    return ids


def parse_document(
    conn: psycopg.Connection, tenant_id: UUID | str, document_id: UUID | str, ocr: OcrEngine | None = None
) -> str:
    """Parse a stored document into document_pages. Returns the new status.
    Idempotent: documents that are no longer pending are left alone."""
    doc = conn.execute(
        "SELECT id, filename, content_type, object_uri, status FROM documents WHERE id = %s FOR UPDATE",
        (str(document_id),),
    ).fetchone()
    if doc is None or doc["status"] != "pending":
        return doc["status"] if doc else "missing"
    data = TenantObjects(conn, tenant_id).get(doc["object_uri"])
    try:
        parsed = parse(data, doc["filename"], doc["content_type"], ocr)
    except UnsupportedFormat as e:
        conn.execute(
            "UPDATE documents SET status = 'unsupported', error = %s, parsed_at = now() WHERE id = %s",
            (str(e), doc["id"]),
        )
        return "unsupported"
    except Exception as e:  # noqa: BLE001 - corrupt files must not wedge the consumer
        log.warning("parse failed for document %s: %s", doc["id"], e)
        conn.execute(
            "UPDATE documents SET status = 'failed', error = %s, parsed_at = now() WHERE id = %s",
            (f"{type(e).__name__}: {e}"[:500], doc["id"]),
        )
        return "failed"

    conn.execute("DELETE FROM document_pages WHERE document_id = %s", (doc["id"],))
    with conn.cursor() as cur:
        cur.executemany(
            "INSERT INTO document_pages (tenant_id, document_id, page_no, kind, title, text, ocr)"
            " VALUES (%s, %s, %s, %s, %s, %s, %s)",
            [(str(tenant_id), doc["id"], p.no, p.kind, p.title, p.text, p.ocr) for p in parsed.pages],
        )
    conn.execute(
        "UPDATE documents SET status = 'parsed', format = %s, page_count = %s, ocr_pages = %s, warnings = %s,"
        " error = NULL, parsed_at = now() WHERE id = %s",
        (parsed.format, len(parsed.pages), parsed.ocr_pages, parsed.warnings, doc["id"]),
    )
    if parsed.text_chars:
        outbox.enqueue(
            conn,
            tenant_id,
            outbox.Topics.DOCUMENT_PARSED,
            {"document_id": str(doc["id"]), "format": parsed.format},
            key=str(doc["id"]),
        )
    return "parsed"
