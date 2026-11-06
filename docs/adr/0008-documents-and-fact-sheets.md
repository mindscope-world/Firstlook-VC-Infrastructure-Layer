# 0008. Diligence documents and fact sheets

Status: accepted · 2026-11-06

**Context.** Phase 1c turns a founder's deck or financial model into a fact sheet an analyst can trust. Decks arrive as email attachments and uploads. Google Drive, Dropbox and DocSend connectors come later. Every number in a fact sheet must be traceable to the page it came from.

**Decision.**
- **Documents are stored once per tenant**, keyed by content hash, encrypted with the tenant key like every raw object (`documents`). A document keeps the visibility of the interaction it arrived with, and respects the restricted-deal policy. Pages and fact sheets are visible exactly when their document is.
- **Separate service** (`services/documents`) so the parsing dependencies (pypdf, python-pptx, openpyxl, poppler, tesseract) stay out of the resolver and the API. Each step is its own bus event, so a slow parse or OCR job never blocks email ingestion:
  `interactions.resolved` (attachments) or upload → `documents.stored` → parse → `documents.parsed` → fact sheet → `fact_sheets.created`.
- **Parsing** detects the format from the bytes, not the declared type or the file extension. Output is one page per PDF page, slide (with tables and speaker notes) or sheet (cached values, never formulas). PDF pages without a text layer are rasterised with `pdftoppm` and run through the OCR adapter. Corrupt and unsupported files get a status, not a stuck queue.
- **Fact sheets** use a fixed schema: company, team, metrics from a fixed vocabulary, and round terms. Every value carries a verbatim quote and a page number. Validation finds the quote, falling back to other pages if the model named the wrong one, and stores character offsets. Values with no quote are dropped. For numbers, the value must be readable from its quote ("$1.5M" = 1,500,000). Otherwise it is kept, flagged and capped at low confidence, and the UI highlights it. Document text is passed as data, and page delimiters inside it are neutralised.
- **Human in the loop (ADR 0006).** Fact sheets are proposals. Accepting one makes it the company's current fact sheet and fills only empty profile fields. It never overwrites a value another source or a person has set.
- **Uploads and downloads** go through the ingest service. Downloads are always `Content-Disposition: attachment` with `nosniff`, and anything not on a short allowlist is served as `application/octet-stream`, so an uploaded HTML or SVG file can never run in the app's origin.

**Consequences.** Fact-sheet quality is measured by `packages/evals` (`factsheet` suite). Consistency checks (deck vs model), memo drafting and the inbound-deck workflow build on these tables. The fixtures already include a model whose MRR disagrees with the deck. Document text is not yet indexed into `chunks` for search.
