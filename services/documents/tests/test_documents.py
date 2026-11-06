import shutil

import pytest
from fastapi.testclient import TestClient

from firstlook_documents.parse import UnsupportedFormat, detect_format, parse
from firstlook_fixtures.documents import (
    PDF,
    PPTX,
    XLSX,
    chama_deck_pptx,
    kilimo_deck_pdf,
    kilimo_model_xlsx,
    text_pdf,
)


class FakeOcr:
    available = True

    def __init__(self, text: str = "Scanned page: ARR $1.2M"):
        self.text = text
        self.calls = 0

    def image_to_text(self, data: bytes, suffix: str = ".png") -> str:
        self.calls += 1
        return self.text


class NoOcr:
    available = False

    def image_to_text(self, data: bytes, suffix: str = ".png") -> str:
        raise AssertionError("must not be called")


def test_detect_format_sniffs_bytes_not_names():
    assert detect_format(kilimo_deck_pdf(), "deck.bin", "application/octet-stream") == "pdf"
    assert detect_format(chama_deck_pptx(), "x.pdf", PDF) == "pptx"
    assert detect_format(kilimo_model_xlsx(), None, None) == "xlsx"
    assert detect_format(b"hello", "notes.txt", "text/plain") == "text"
    assert detect_format(b"\xff\xfe\x00binary", "x.txt", "text/plain") is None
    assert detect_format(b"MZ\x90\x00", "deck.pdf", PDF) is None  # an executable named .pdf
    assert detect_format(b"PK\x03\x04garbage", "x.pptx", PPTX) is None


def test_pdf_pages_and_text():
    doc = parse(kilimo_deck_pdf(), "deck.pdf", PDF, NoOcr())
    assert doc.format == "pdf" and len(doc.pages) == 6
    assert doc.pages[2].text.startswith("Traction")
    assert "$38k MRR from two lender partners" in doc.pages[2].text
    assert doc.ocr_pages == 0 and doc.warnings == []


def test_scanned_pdf_page_without_ocr_is_flagged():
    doc = parse(text_pdf([["Cover page with enough text to count"], []]), "scan.pdf", PDF, NoOcr())
    assert doc.pages[1].text == ""
    assert any("no text layer" in w for w in doc.warnings)


@pytest.mark.skipif(shutil.which("pdftoppm") is None, reason="pdftoppm (poppler) not installed")
def test_scanned_pdf_page_is_ocrd():
    ocr = FakeOcr()
    doc = parse(text_pdf([["Cover page with enough text to count"], []]), "scan.pdf", PDF, ocr)
    assert ocr.calls == 1
    assert doc.pages[1].text == "Scanned page: ARR $1.2M" and doc.pages[1].ocr
    assert doc.ocr_pages == 1


def test_pptx_slides_tables_and_notes():
    doc = parse(chama_deck_pptx(), "chama.pptx", PPTX, NoOcr())
    assert [p.kind for p in doc.pages] == ["slide"] * 5
    traction = doc.pages[2]
    assert traction.title == "Traction"
    assert "Active groups\t1,200" in traction.text
    assert "Speaker notes: Default rate on group-backed loans is 1.8%." in traction.text


def test_xlsx_sheets_use_cached_values():
    doc = parse(kilimo_model_xlsx(), "model.xlsx", XLSX, NoOcr())
    assert [p.title for p in doc.pages] == ["Summary", "Monthly"]
    assert "Current MRR (Aug 2026)\t36500" in doc.pages[0].text
    assert doc.pages[1].text.splitlines()[-1] == "Aug 2026\t41800\t36500\t55000"


def test_unsupported_and_corrupt_files():
    with pytest.raises(UnsupportedFormat):
        parse(b"MZ\x90\x00", "virus.exe", "application/octet-stream", NoOcr())
    with pytest.raises(UnsupportedFormat):
        parse(b"%PDF-1.4\n garbage", "broken.pdf", PDF, NoOcr())


# -- database --------------------------------------------------------------------


@pytest.mark.db
def test_store_parse_and_visibility(make_tenant, llm):
    from firstlook_core.db import tenant_tx
    from firstlook_core.tenants import create_user
    from firstlook_documents.store import parse_document, store_document

    t, [(admin, _)] = make_tenant("Docs Fund")
    with tenant_tx(t) as conn:
        other, _ = create_user(conn, t, "other@docs.vc", "Other", "associate")
        first = store_document(
            conn, t, kilimo_deck_pdf(), filename="deck.pdf", content_type=PDF, origin="upload"
        )
        again = store_document(
            conn, t, kilimo_deck_pdf(), filename="copy.pdf", content_type=PDF, origin="upload"
        )
        assert first.created and not again.created and again.document_id == first.document_id
        private = store_document(
            conn,
            t,
            kilimo_model_xlsx(),
            filename="model.xlsx",
            content_type=XLSX,
            origin="email_attachment",
            owner_user_id=admin,
            visibility="private",
        )
        assert parse_document(conn, t, first.document_id, NoOcr()) == "parsed"
        assert parse_document(conn, t, first.document_id, NoOcr()) == "parsed"  # idempotent
        assert parse_document(conn, t, private.document_id, NoOcr()) == "parsed"
        row = conn.execute(
            "SELECT status, page_count, format FROM documents WHERE id = %s", (first.document_id,)
        ).fetchone()
        assert row == {"status": "parsed", "page_count": 6, "format": "pdf"}
        topics = [
            r["topic"]
            for r in conn.execute(
                "SELECT topic FROM outbox WHERE key = %s ORDER BY id", (str(first.document_id),)
            )
        ]
        assert topics == ["documents.stored", "documents.parsed"]

    # The private document and its pages are invisible to other users.
    with tenant_tx(t, other, "associate") as conn:
        ids = {r["id"] for r in conn.execute("SELECT id FROM documents")}
        assert ids == {first.document_id}
        assert (
            conn.execute(
                "SELECT count(*) AS n FROM document_pages WHERE document_id = %s", (private.document_id,)
            ).fetchone()["n"]
            == 0
        )
        # Re-uploading the same bytes doesn't reveal the private document.
        with pytest.raises(LookupError):
            store_document(
                conn, t, kilimo_model_xlsx(), filename="m.xlsx", content_type=XLSX, origin="upload"
            )
    with tenant_tx(t, admin, "admin") as conn:
        assert conn.execute("SELECT count(*) AS n FROM document_pages").fetchone()["n"] == 8

    # Another tenant sees nothing.
    t2, _ = make_tenant("Other Docs Fund")
    with tenant_tx(t2) as conn:
        assert conn.execute("SELECT count(*) AS n FROM documents").fetchone()["n"] == 0


@pytest.mark.db
def test_unsupported_document_is_marked_not_parsed(make_tenant, llm):
    from firstlook_core.db import tenant_tx
    from firstlook_documents.store import store_document

    t, _ = make_tenant("Odd Files Fund")
    with tenant_tx(t) as conn:
        s = store_document(conn, t, b"MZ\x90\x00", filename="tool.exe", content_type=None, origin="upload")
        row = conn.execute("SELECT status, format FROM documents WHERE id = %s", (s.document_id,)).fetchone()
        assert row == {"status": "unsupported", "format": None}
        assert (
            conn.execute("SELECT count(*) AS n FROM outbox WHERE key = %s", (str(s.document_id),)).fetchone()[
                "n"
            ]
            == 0
        )


@pytest.mark.db
def test_upload_and_download_endpoints(make_tenant, llm):
    from firstlook_core.auth import Principal, issue_session
    from firstlook_core.db import tenant_tx
    from firstlook_core.tenants import create_user
    from firstlook_ingest.app import app

    t, [(admin, _)] = make_tenant("Upload Fund")
    other_tenant, _ = make_tenant("Elsewhere Fund")
    with tenant_tx(t) as conn:
        viewer, _ = create_user(conn, t, "viewer@upload.vc", "Viewer", "viewer")
        company = conn.execute(
            "INSERT INTO entities (tenant_id, type, canonical_name) VALUES (%s, 'company', 'Chama Pay') RETURNING id",
            (t,),
        ).fetchone()["id"]
        conn.execute("INSERT INTO companies (id, tenant_id, name) VALUES (%s, %s, 'Chama Pay')", (company, t))
    with tenant_tx(other_tenant) as conn:
        foreign = conn.execute(
            "INSERT INTO entities (tenant_id, type, canonical_name) VALUES (%s, 'company', 'X') RETURNING id",
            (other_tenant,),
        ).fetchone()["id"]
        conn.execute(
            "INSERT INTO companies (id, tenant_id, name) VALUES (%s, %s, 'X')", (foreign, other_tenant)
        )

    client = TestClient(app)
    auth = {"Authorization": f"Bearer {issue_session(Principal(admin, t, 'admin', 'admin@x'))}"}
    deck = ("Chama Pay.pptx", chama_deck_pptx(), PPTX)

    r = client.post(
        "/documents",
        files={"file": deck},
        headers={"Authorization": f"Bearer {issue_session(Principal(viewer, t, 'viewer', 'v@x'))}"},
    )
    assert r.status_code == 403
    r = client.post("/documents", files={"file": deck}, data={"company_id": str(foreign)}, headers=auth)
    assert r.status_code == 404  # another tenant's company can't be linked

    r = client.post("/documents", files={"file": deck}, data={"company_id": str(company)}, headers=auth)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["created"] and body["format"] == "pptx" and body["status"] == "pending"
    assert body["company_id"] == str(company)
    again = client.post("/documents", files={"file": deck}, headers=auth).json()
    assert again["id"] == body["id"] and not again["created"]

    r = client.get(f"/documents/{body['id']}/file", headers=auth)
    assert r.status_code == 200 and r.content == chama_deck_pptx()
    assert r.headers["content-disposition"] == 'attachment; filename="Chama Pay.pptx"'
    assert r.headers["x-content-type-options"] == "nosniff"

    # An HTML upload is stored but never served as HTML.
    html = client.post(
        "/documents", files={"file": ("x.html", b"<script>alert(1)</script>", "text/html")}, headers=auth
    )
    assert html.json()["status"] == "unsupported"
    r = client.get(f"/documents/{html.json()['id']}/file", headers=auth)
    assert r.headers["content-type"] == "application/octet-stream"

    other_auth = {
        "Authorization": f"Bearer {issue_session(Principal(admin, other_tenant, 'admin', 'admin@x'))}"
    }
    assert client.get(f"/documents/{body['id']}/file", headers=other_auth).status_code == 404
