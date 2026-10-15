# English Textbooks MCP implementation plan

## Goal

Create a simple, read-only, model-independent textbook tutor MCP inspired by
[xuexi-keben](https://github.com/iodize6399/xuexi-keben), initially covering
W. Stannard Allen's *Living English Structure*, with a catalog that supports more books.

## Agreed scope

- Use Mistral's latest OCR model for ingestion; retain the actual returned model.
- Prepare and test a Cloudflare Worker with a Streamable HTTP `/mcp` endpoint.
- Publish to the user's verified Cloudflare account through Wrangler and push the
  source to the configured GitHub repository. Leave client configurations untouched.
- Do not require model credentials, a database, or student accounts at runtime.
- Preserve the original PDF and keep credentials outside the repository.

## Implementation

1. Inspect the scans and split two-page spreads into individual reading pages.
2. Run resumable OCR with raw responses, page/block confidence, source fingerprints,
   image assets, and explicit PDF-page/printed-page/side provenance.
3. Build book manifests, a reviewed chapter index, human-readable chapter files,
   and retrieval chunks. Preserve exercises without filling blanks or fabricating answers.
4. Implement catalog, lesson retrieval, page retrieval, ranked search, guided study,
   and quiz preparation through the official MCP SDK. Return source citations and
   uncertainty with retrieved material. Keep quiz answers out of the initial student prompt.
5. Supply MCP resources and study/quiz prompts, connection information, health metadata,
   and a small setup page.
6. Document quick start, Cloudflare deployment, adding books, and resuming ingestion.
7. Check corpus coverage and chapter boundaries, spot-check OCR against source scans,
   test retrieval and MCP protocol operations, type-check, and dry-run the Worker build.

## Structure

- `books/<book-id>/book.json`: book metadata and reviewed chapter/page map.
- `books/<book-id>/ocr/`: resumable raw OCR checkpoints and provenance.
- `books/<book-id>/pages/`, `lessons/`, `chunks.jsonl`: canonical readable corpus.
- `scripts/`: ingestion, corpus generation, validation, and protocol checks.
- `src/`: retrieval logic, MCP server, and Cloudflare Worker.
- `src/generated/`: generated runtime corpus, rebuilt when books change.

## Decisions

- Local PDF: 175 scanned landscape spreads, no existing text layer.
- Separate half-page scans are needed to preserve left-to-right page order.
- Official Mistral docs currently identify OCR 4.1 as the latest OCR service;
  use `mistral-ocr-latest` and record the returned model and request settings.
- The user subsequently authorized publishing and signed into Wrangler/GitHub directly.
  Use the verified Cloudflare account; do not use the connected plugin.

## Completed

- OCR saved for all 350 reading pages; 58 sections and 728 retrieval chunks built.
- Raw responses, scan-density audit, model catalog, source fingerprints, usage,
  source-reviewed corrections, page Markdown, and chapter Markdown retained.
- Seven read-only tools, catalog/page resources, study/quiz prompts, HTTP transport,
  local stdio transport, setup page, and deployment configuration implemented.
- Registration and resumable ingestion support additional books without server edits.
- All 12 integrity/retrieval tests pass; type checking, corpus validation, real HTTP
  and stdio client checks, 2025 protocol compatibility, and deployment dry run pass.
- Temporary credential removed; credential scan found no key in project files.
- Source committed and pushed to `iodize6399/english-textbooks-mcp` on `main`;
  GitHub CI passes. The PDF and credentials are excluded.
- Published through Wrangler to the verified Cloudflare account at
  `https://lingo.555420.xyz/mcp`.
- All seven tools, resources, prompts, and HTTP/protocol checks pass against the
  public deployment. No client configurations changed.
- The public hostname is `lingo.555420.xyz`; custom-domain routing and explicit MCP
  hostname/Origin checks are configured. The personal-name `workers.dev` endpoint
  and preview URLs are disabled for this Worker.
- Automatic GitHub deployment needs the Cloudflare Builds dashboard connection;
  the CLI's OAuth credential receives HTTP 403 from the Builds API. The required
  one-time dashboard setup is documented in `docs/deployment.md`.
