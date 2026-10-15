# English Textbook Tutor MCP

Read, search, study, and practise English textbooks with the AI assistant you already
use. Inspired by [xuexi-keben](https://github.com/iodize6399/xuexi-keben).

The initial library contains **Living English Structure** by W. Stannard Allen,
5th edition: **58 sections**, **175 scanned PDF spreads**, and **338 numbered page
positions**. OCR was performed with Mistral's latest OCR service. The corpus includes
the introduction and index; blank pages remain traceable but contain no retrieved text.

The MCP is read-only and model-independent. It needs **no API key, database, embeddings,
or student account at runtime**. Your chosen AI model gives explanations and creates
quizzes using the returned textbook material. Student progress stays in the conversation.

**Live MCP URL:**

```text
https://english-textbooks-mcp.hardik-nagar.workers.dev/mcp
```

Add it as a remote **Streamable HTTP** MCP server with authentication **None**.
No installation is needed to use the hosted server. See the
[setup page](https://english-textbooks-mcp.hardik-nagar.workers.dev/).

The source is published at [iodize6399/english-textbooks-mcp](https://github.com/iodize6399/english-textbooks-mcp).
Public MCP tools, resources, prompts, and protocol compatibility have been tested.
See [deployment details](docs/deployment.md) for updates and GitHub integration.

## Use locally

Install [Node.js 24 or newer](https://nodejs.org/) and Python 3.11 or newer, then:

```sh
npm ci
npm start
```

Add a remote **Streamable HTTP** MCP server in your AI client's settings:

```text
http://127.0.0.1:8787/mcp
```

Choose authentication **None**. Open `http://127.0.0.1:8787/` for setup information.
Your client must support custom MCP servers. A cloud-hosted AI app cannot reach
your machine's loopback address; use the published Cloudflare URL with those clients.

For desktop/terminal clients that launch local MCP servers, use stdio instead:

```json
{
  "mcpServers": {
    "english-textbooks": {
      "command": "node",
      "args": ["--experimental-strip-types", "/absolute/path/to/english-textbooks-mcp/src/stdio.ts"]
    }
  }
}
```

Replace the absolute path with your checkout path. Run `npm ci` first. The stdio
server works from any working directory and opens no network port.

Once connected, try:

> Teach me section 1 from Living English Structure. Then quiz me one question at a time.

> Help me practise exercise 31.10 and explain my mistakes using the book.

> Find the explanations of present perfect and compare them with past simple.

## Publish once, share one URL

When ready to publish, review the book corpus and the Worker name in `wrangler.jsonc`:

```sh
npm run deploy:check
npx wrangler login
npm run deploy
```

Use the `workers.dev` URL printed by Wrangler, followed by `/mcp`. That is the URL
to share with users; they do not need this repository or your Mistral key. The
deployment has no server-side model calls. Normal Cloudflare plan limits apply.
The public endpoint uses no authentication.

Test it before sharing:

```sh
npm run smoke -- https://YOUR-WORKER.YOUR-ACCOUNT.workers.dev/mcp
```

The deployed root page contains connection instructions, `/llms.txt` gives agents
setup guidance, `/health` reports corpus coverage, and
`/.well-known/mcp/server-card.json` describes the endpoint. Client configurations
are managed by the user. The initial deployment was published directly with Wrangler.

For automatic deployments on GitHub pushes, complete the one-time Cloudflare
Builds connection described in [deployment details](docs/deployment.md).

## What the MCP provides

| Tool | Purpose |
| --- | --- |
| `list_books` | Discover books, coverage, quality flags, and answer-key availability |
| `list_lessons` | Browse textbook sections and exercise IDs in order |
| `get_lesson` | Read a section or exercise, with pagination and citations |
| `get_page` | Read a printed page or PDF-page/side reference |
| `search_textbook` | Ranked keyword/phrase search, optionally restricted to a book/section |
| `start_study_session` | Get source material and a teaching brief for the chat model |
| `prepare_quiz` | Get source material and a one-question-at-a-time quiz protocol |

With one book, `book_id` is optional. With more books, lesson and page tools require
an explicit book ID; search can cover the whole library. Section numbers refer to
chapters (e.g. `31`); `section_id` selects a numbered exercise (e.g. `31.10`).

Lesson retrieval defaults to 12 chunks, with a maximum of 30. Follow `next_offset`
until it is `null` for the entire section. Search returns full source chunks, ranked
using BM25-style token weighting, phrase matches, and chapter titles. It is lexical
search, so use words from the book when a broad paraphrase finds no results.

Resources include `textbook://catalog`, `textbook://BOOK-ID/lessons`, and
`textbook://BOOK-ID/pages/PAGE-ID`. Reusable prompts: `study_lesson`, `quiz_lesson`.
All tools carry read-only annotations and return actionable errors for invalid IDs.

## Add another book

The serving code automatically discovers every `books/*/book.json` at build time.
You do not edit the MCP server to add books. OCR tooling needs
[uv](https://docs.astral.sh/uv/getting-started/installation/) in addition to Node.js.

1. Place the PDF in this workspace and register it:

   ```sh
   uv run scripts/add_book.py path/to/new-book.pdf \
     --id new-book --title "New Book" --author "Author Name" --layout single-page
   ```

   Use `--layout two-page` for scanned spreads. The original PDF is preserved and
   ignored by Git. Registering a book makes no API calls.

2. OCR it using a Mistral key supplied through the environment or a private file:

   ```sh
   uv run scripts/ingest.py --book new-book --key-file /path/to/private-key-file
   ```

   The file should contain only the key and have permissions `0600`. Alternatively,
   set `MISTRAL_API_KEY` in your shell and omit `--key-file`. Keep keys outside this
   repository. OCR is the only step that needs credentials and incurs model usage.

3. Review the contents and fill in `books/new-book/book.json`. See
   [the manifest guide](docs/adding-books.md) for the small page/chapter mapping format.
   Check blank pages and uncertain text against the PDF; record corrections in
   `corrections.json` rather than changing raw OCR responses.

4. Rebuild and check:

   ```sh
   npm run check
   npm run deploy:check
   ```

   Once reviewed, deploy the updated corpus using `npm run deploy`.

For the existing book, this resumes only pages missing from its saved checkpoints:

```sh
uv run scripts/ingest.py --book living-english-structure --key-file /path/to/private-key-file
```

The default model is `mistral-ocr-latest`. Raw results retain model identifiers,
page/block confidence, settings, timestamps, PDF fingerprints, and batch usage.
`--pdf-pages 2-4,175` selects original PDF pages for a targeted run; `--force`
reprocesses those pages and incurs new usage. One worker and eight reading pages
per request are the defaults. Interrupted runs retain completed pages.

## Source quality

Each chunk has a stable ID, book/section/exercise identifiers, printed page,
original PDF page and side, confidence, and quality flags. Splitting spreads
prevents the OCR from mixing text from facing pages. Footnotes are retained.

The original PDF has been preserved. Raw OCR, page Markdown, chapter Markdown,
extracted assets, a correction log, and the generated runtime corpus are included.
The runtime returns text; consult the PDF for visual layout and any image-dependent
exercise. The scan does **not** include the separate published answer key, so a
tutor must identify its proposed answers as inferred and allow valid alternatives.

OCR is not a proofread transcription. Reviewed blank-page hallucinations were
removed from the serving corpus, duplicated list markers were normalized, and a
damaged exercise ID was corrected against the scan. The contents list an edition
note that is missing from this scan. See [the quality report](docs/quality.md).

## Development and checks

```sh
npm run check           # Rebuild, validate complete coverage, type-check, run tests
npm run smoke:stdio     # Test a real local MCP client/server connection
npm start               # Start the local HTTP server
# In another terminal:
npm run smoke           # Test all HTTP tools, resources, prompts, compatibility, routes
npm run deploy:check    # Check and build the Worker without publishing
```

`npm ci` and the serving commands need no Mistral credentials. The checked-in OCR
corpus is enough to rebuild the server. `uv.lock` and `package-lock.json` pin
dependencies. After changing Wrangler configuration, run `npx wrangler types`.

```text
books/<book-id>/book.json       Metadata, chapter starts, page-number map
books/<book-id>/ocr/            Raw OCR pages and resumable provenance/usage records
books/<book-id>/corrections.json Reviewed changes; raw responses remain intact
books/<book-id>/pages/          Human-readable source pages
books/<book-id>/lessons/        Human-readable chapters
books/<book-id>/chunks.jsonl    Canonical retrieval chunks
src/generated/corpus.json      Rebuilt Worker corpus
src/                           Retrieval, MCP capabilities, HTTP/stdio entry points
scripts/                       Registration, OCR, building, validation, smoke tests
tests/                         Retrieval and ingestion integrity tests
```
