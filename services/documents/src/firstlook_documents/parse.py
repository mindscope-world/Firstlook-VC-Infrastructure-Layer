"""Turn document bytes into pages of text.

    PDF   one page per PDF page. Pages with no text layer (scans, image-only
          slides exported to PDF) are rasterised with pdftoppm and OCR'd.
    PPTX  one page per slide: title, text frames, tables, grouped shapes, and
          speaker notes.
    XLSX  one page per sheet: non-empty rows as tab-separated cells (cached
          values, not formulas).
    Image one page, OCR'd.
    Text  one page.

Everything here is pure (bytes in, pages out) so it can be tested without a
database, and treats the file as untrusted: sizes are capped, macros and
external links are never evaluated, and parse errors become a failed status
rather than an exception that would block the queue.
"""

from __future__ import annotations

import io
import re
import shutil
import subprocess
import tempfile
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

from firstlook_core.adapters.ocr import OcrEngine, get_ocr

MAX_PAGES = 300
MAX_SHEET_ROWS = 2000
MAX_SHEET_COLS = 40
MAX_PAGE_CHARS = 40_000
MIN_TEXT_CHARS = 25  # below this a PDF page is treated as scanned

FORMATS = {
    "application/pdf": "pdf",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": "pptx",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "xlsx",
    "image/png": "image",
    "image/jpeg": "image",
    "text/plain": "text",
    "text/csv": "text",
    "text/markdown": "text",
}
_EXTENSIONS = {
    ".pdf": "pdf",
    ".pptx": "pptx",
    ".xlsx": "xlsx",
    ".png": "image",
    ".jpg": "image",
    ".jpeg": "image",
    ".txt": "text",
    ".csv": "text",
    ".md": "text",
}


class UnsupportedFormat(ValueError):
    pass


@dataclass
class Page:
    no: int
    kind: str  # page, slide, sheet, image, text
    text: str
    title: str | None = None
    ocr: bool = False


@dataclass
class ParsedDocument:
    format: str
    pages: list[Page] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ocr_pages(self) -> int:
        return sum(p.ocr for p in self.pages)

    @property
    def text_chars(self) -> int:
        return sum(len(p.text) for p in self.pages)


def detect_format(data: bytes, filename: str | None = None, content_type: str | None = None) -> str | None:
    """Sniff the bytes first; the declared type and extension are only hints
    (mail clients often send decks as application/octet-stream)."""
    if data[:5] == b"%PDF-":
        return "pdf"
    if data[:8] == b"\x89PNG\r\n\x1a\n" or data[:3] == b"\xff\xd8\xff":
        return "image"
    if data[:4] == b"PK\x03\x04":
        try:
            names = set(zipfile.ZipFile(io.BytesIO(data)).namelist())
        except zipfile.BadZipFile:
            return None
        if any(n.startswith("ppt/") for n in names):
            return "pptx"
        if any(n.startswith("xl/") for n in names):
            return "xlsx"
        return None
    fmt = FORMATS.get((content_type or "").split(";")[0].strip().lower())
    if fmt is None and filename:
        fmt = _EXTENSIONS.get(Path(filename).suffix.lower())
    if fmt == "text":
        try:
            data[:4096].decode("utf-8")
        except UnicodeDecodeError:
            return None
        return "text"
    return None


def _clean(text: str) -> str:
    text = text.replace("\x00", "").replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()[:MAX_PAGE_CHARS]


# -- PDF -------------------------------------------------------------------------


def _rasterise(pdf: bytes, page_no: int, dpi: int = 200) -> bytes | None:
    binary = shutil.which("pdftoppm")
    if not binary:
        return None
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / "in.pdf"
        src.write_bytes(pdf)
        out = Path(tmp) / "page"
        subprocess.run(
            [
                binary,
                "-f",
                str(page_no),
                "-l",
                str(page_no),
                "-r",
                str(dpi),
                "-png",
                "-singlefile",
                str(src),
                str(out),
            ],
            capture_output=True,
            check=True,
            timeout=120,
        )
        png = out.with_suffix(".png")
        return png.read_bytes() if png.exists() else None


def parse_pdf(data: bytes, ocr: OcrEngine) -> ParsedDocument:
    from pypdf import PdfReader
    from pypdf.errors import PdfReadError

    doc = ParsedDocument("pdf")
    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted and not reader.decrypt(""):
            raise UnsupportedFormat("the PDF is password-protected")
        pages = reader.pages
    except PdfReadError as e:
        raise UnsupportedFormat(f"not a readable PDF: {e}") from e
    if len(pages) > MAX_PAGES:
        doc.warnings.append(f"only the first {MAX_PAGES} of {len(pages)} pages were read")
    scanned_without_ocr = 0
    for i, page in enumerate(list(pages)[:MAX_PAGES], start=1):
        try:
            text = _clean(page.extract_text() or "")
        except Exception:  # noqa: BLE001 - a broken page shouldn't fail the document
            text = ""
            doc.warnings.append(f"page {i}: text layer could not be read")
        used_ocr = False
        if len(text) < MIN_TEXT_CHARS:
            if ocr.available and (png := _rasterise(data, i)):
                ocr_text = _clean(ocr.image_to_text(png, ".png"))
                if len(ocr_text) > len(text):
                    text, used_ocr = ocr_text, True
            elif not text:
                scanned_without_ocr += 1
        doc.pages.append(Page(i, "page", text, None, used_ocr))
    if scanned_without_ocr:
        doc.warnings.append(
            f"{scanned_without_ocr} page(s) have no text layer and OCR is not available (install tesseract)"
        )
    return doc


# -- PPTX ------------------------------------------------------------------------


def _shape_text(shape) -> list[str]:
    from pptx.enum.shapes import MSO_SHAPE_TYPE

    out: list[str] = []
    if shape.shape_type == MSO_SHAPE_TYPE.GROUP:
        for s in shape.shapes:
            out += _shape_text(s)
        return out
    if getattr(shape, "has_text_frame", False) and shape.has_text_frame:
        t = shape.text_frame.text.strip()
        if t:
            out.append(t)
    if getattr(shape, "has_table", False) and shape.has_table:
        for row in shape.table.rows:
            cells = [c.text.strip() for c in row.cells]
            if any(cells):
                out.append("\t".join(cells))
    return out


def parse_pptx(data: bytes) -> ParsedDocument:
    from pptx import Presentation

    doc = ParsedDocument("pptx")
    prs = Presentation(io.BytesIO(data))
    for i, slide in enumerate(prs.slides, start=1):
        if i > MAX_PAGES:
            doc.warnings.append(f"only the first {MAX_PAGES} slides were read")
            break
        title_shape = slide.shapes.title
        title = title_shape.text.strip() if title_shape is not None and title_shape.has_text_frame else None
        parts: list[str] = []
        for shape in slide.shapes:
            parts += _shape_text(shape)
        if slide.has_notes_slide:
            notes = (
                slide.notes_slide.notes_text_frame.text.strip() if slide.notes_slide.notes_text_frame else ""
            )
            if notes:
                parts.append(f"Speaker notes: {notes}")
        doc.pages.append(Page(i, "slide", _clean("\n".join(parts)), title or None))
    return doc


# -- XLSX ------------------------------------------------------------------------


def _cell(v) -> str:
    if v is None:
        return ""
    if isinstance(v, float):
        return f"{v:.6g}" if abs(v) < 1e15 else str(v)
    return str(v).strip()


def parse_xlsx(data: bytes) -> ParsedDocument:
    from openpyxl import load_workbook

    doc = ParsedDocument("xlsx")
    # data_only: cached values, never formulas; read_only streams rows.
    wb = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    try:
        for i, ws in enumerate(wb.worksheets, start=1):
            lines: list[str] = []
            truncated = False
            for r, row in enumerate(ws.iter_rows(values_only=True)):
                if r >= MAX_SHEET_ROWS:
                    truncated = True
                    break
                cells = [_cell(v) for v in row[:MAX_SHEET_COLS]]
                while cells and not cells[-1]:
                    cells.pop()
                if any(cells):
                    lines.append("\t".join(cells))
            if truncated:
                doc.warnings.append(f"sheet {ws.title!r}: only the first {MAX_SHEET_ROWS} rows were read")
            if not lines:
                continue
            doc.pages.append(Page(len(doc.pages) + 1, "sheet", _clean("\n".join(lines)), ws.title))
            if i >= MAX_PAGES:
                break
    finally:
        wb.close()
    return doc


# -- entry point -----------------------------------------------------------------


def parse(
    data: bytes, filename: str | None = None, content_type: str | None = None, ocr: OcrEngine | None = None
) -> ParsedDocument:
    fmt = detect_format(data, filename, content_type)
    if fmt is None:
        raise UnsupportedFormat(
            f"unsupported file type ({content_type or 'unknown'}, {filename or 'no name'})"
        )
    ocr = ocr or get_ocr()
    if fmt == "pdf":
        doc = parse_pdf(data, ocr)
    elif fmt == "pptx":
        doc = parse_pptx(data)
    elif fmt == "xlsx":
        doc = parse_xlsx(data)
    elif fmt == "image":
        doc = ParsedDocument("image")
        if not ocr.available:
            doc.warnings.append("image documents need OCR, which is not available (install tesseract)")
            text = ""
        else:
            suffix = ".png" if data[:4] == b"\x89PNG" else ".jpg"
            text = _clean(ocr.image_to_text(data, suffix))
        doc.pages.append(Page(1, "image", text, None, ocr.available))
    else:
        doc = ParsedDocument("text", [Page(1, "text", _clean(data.decode("utf-8", errors="replace")))])
    if doc.text_chars == 0:
        doc.warnings.append("no text could be extracted")
    return doc
