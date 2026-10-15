# Living English Structure: ingestion and quality report

Prepared on 2026-10-15. This is an OCR-derived corpus with targeted source review,
not a claim that every word has been independently proofread.

- Source: W. Stannard Allen, *Living English Structure*, 5th edition, Longman.
  The copyright page identifies ISBN `0-582-52506-3`; the input filename gives a
  different ISBN, so the manifest uses the printed ISBN.
- Input: 175 landscape PDF pages. Each spread was split into separate left and
  right PDF pages before OCR, giving 350 reading-page checkpoints.
- Model requested and returned: `mistral-ocr-latest`. The account's model catalog
  lists `mistral-ocr-4-1` and `mistral-ocr-4` as aliases of this model. The response
  retains the alias rather than an immutable version ID; the raw records do not
  claim a more specific returned version. See `ocr/model-catalog.json`.
- OCR settings: block extraction, block/page confidence, image extraction, and
  separate header/footer fields. Extracted textual footers are included in retrieval.
- Saved usage records total 350 processed reading pages. Rate-limited batches were
  resumed from saved checkpoints with reduced concurrency.
- Organization: 58 chapter boundaries from the two contents pages, checked against
  OCR headings; 728 retrieval chunks. Exercise headings are recognized across
  plain, heading, parenthesized, and bold OCR formatting.
- A scan-density audit of all 350 reading pages isolated five nearly empty halves,
  all reviewed against the PDF. The build rejects unreviewed OCR text on such pages.
- Printed pages: 1–338, including the blank position at 328. Introduction/contents
  labels v–ix are mapped separately. The blank half before page 1 is unnumbered;
  the contents' Note to the Fifth Edition, listed on x, is missing from this scan.

The following were checked against rendered source scans:

- Cover, title/copyright information, both contents pages, and split-page ordering.
- Blank halves at PDF 1 left, 2 left, 6 left, 170 left, and 175 right. Two blank
  halves produced unrelated Chinese OCR hallucinations; these responses remain
  in the raw archive but their text is excluded from pages/chunks served by MCP.
- Countable/uncountable grammar notes and article blanks (printed pages 1–3),
  pronoun exercises (12–13), and negative-answer practice (26).
- A damaged marginal exercise label on printed page 153. Raw OCR reads `11.11`;
  the source, chapter context, and index identify `31.11`. This is logged in
  `corrections.json` and the serving text carries a correction flag.
- Shared-page boundaries, including sections 8, 9, and 10 on printed page 19.

Mechanical cleanup removes duplicated Markdown list markers such as `1. 1` while
preserving the original question text and order. It is flagged on affected pages.
Raw responses are never edited by the build.

Confidence fields are model estimates. Most pages contain at least one token
below the minimum-confidence threshold, so `low_confidence_tokens` is common.
Use the average and minimum scores together; a high average does not establish
transcription accuracy. Three front-matter pages have average confidence below
0.95. Images remain in local artifacts; visual exercises require the original PDF.

The scan contains grammar explanations and solved examples but no separate
published answer key. Tutor answers must be identified as inferred. Some examples
and usage advice reflect the edition's age.

Automated validation verifies all reading-page checkpoints, source fingerprints,
unique chunk IDs, chapter coverage, exact text coverage after documented cleanup,
and matching page citations. Tests also check book isolation, exercise continuation,
shared-page chapter isolation, pagination, blank-page exclusion, retrieval ranking,
and MCP tools/resources/prompts through official clients.
