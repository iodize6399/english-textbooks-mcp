# Book manifest guide

Register a PDF with `uv run scripts/add_book.py` and run ingestion as described in
the README. Then edit that book's `book.json` using its actual contents pages.
The existing Living English Structure manifest is a complete example.

```json
{
  "id": "new-book",
  "title": "New Book",
  "author": "Author Name",
  "language": "en",
  "source_file": "new-book.pdf",
  "layout": "single-page",
  "expected_pdf_pages": 120,
  "has_answer_key": false,
  "printed_page_ranges": [
    { "reading_start": 3, "reading_end": 6, "first_page": 5, "style": "roman" },
    { "reading_start": 7, "reading_end": 120, "first_page": 1, "style": "arabic" }
  ],
  "lessons": [
    { "number": 1, "title": "Nouns", "start_page": 1 },
    { "number": 2, "title": "Verbs", "start_page": 8 }
  ],
  "index_start_page": 110,
  "notes": "Edition information and any source limitations."
}
```

`reading_start` and `reading_end` are inclusive, **one-based reading order**.
For a single-page PDF, reading order equals the original PDF page. For two-page
spreads, PDF page 1 left is reading page 1, right is 2; PDF page 2 left is 3,
right is 4. Covers and blank halves still count. Omit printed-page mappings for
unnumbered pages. Roman numbers and Arabic numbers form separate ranges.

List chapters in order, using their printed Arabic start pages. The builder finds
the chapter heading on that page and keeps earlier text with the previous chapter.
Two chapters may start on the same page. If a heading is shorter than the contents
entry, add `"heading": "Verbs"` to that lesson. If a damaged heading cannot be
matched, review the page and supply `start_offset`, a zero-based character offset
in the normalized page text. Prefer a reviewed text correction when appropriate.

`index_start_page` is optional. It separates reference material from the last
lesson. Pages before the first chapter are preserved as front matter. Each book
must have at least one reviewed lesson. This layout assumes numbered chapters
and Arabic chapter pages; adapt the builder if a future book uses another scheme.

`has_answer_key` means the ingested PDF actually includes a published answer key.
Keep it false when only solved examples are present. If adding a key later,
separate its retrieval policy before setting this flag so quiz answers are not
returned in the initial student material.

Corrections are optional and recorded separately:

```json
{
  "pdf-001-left": {
    "blank": true,
    "reason": "Visually reviewed against the original PDF: empty cover half."
  },
  "pdf-020-right": {
    "replacements": [
      { "before": "11.11\nAdvanced", "after": "31.11\nAdvanced" }
    ],
    "reason": "The scan and chapter context establish the correct exercise ID."
  }
}
```

The build fails if a replacement no longer matches the raw OCR. This prevents a
re-OCR run from silently applying a stale correction. A blank override suppresses
retrieval text but preserves the raw response and source-page record.

Ingestion also audits scan density and records `ocr/scan-audit.json`. If a nearly
empty scan produces OCR text, the builder stops for source review. Mark a confirmed
blank with `"blank": true`; for a sparse page that really contains the returned
text, use `"source_reviewed": true` with a reason. The audit is a review aid and
does not decide automatically whether a page is blank.

Run `npm run check` before reviewing the chapter/page Markdown and search results.
The builder discovers all manifests automatically and refuses incomplete OCR.
