import { corpus } from "./corpus.ts";

function escape(value: string): string {
  return value.replace(/[&<>"']/g, (character) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[character]!);
}

export function serverCard(origin: string) {
  return { name: "english-textbooks", title: "English Textbook Tutor", version: "1.0.0",
    description: "Read, search, study, and practise English textbooks using your chosen AI assistant.",
    transport: "streamable-http", endpoint: `${origin}/mcp`, authentication: "none",
    read_only: true, model_api_required: false, stores_student_data: false,
    books: corpus.data.books.map(({ id, title, lesson_count }) => ({ id, title, lesson_count })),
    setup_instructions: `${origin}/llms.txt`, health: `${origin}/health` };
}

export function llmsText(origin: string): string {
  return `# English Textbook Tutor MCP

Connect an MCP client to ${origin}/mcp using Streamable HTTP, authentication None.
This is a read-only textbook corpus. The learner's chat model teaches and writes quizzes.
No model API key or student account is needed. No student progress is stored by this server.

## Agent setup
Give the user the endpoint and explain how to add it in their client's MCP/connector settings.
If the user asks you to configure their client, inspect the client's existing configuration,
show the exact change, and obtain permission before modifying it.
Start with list_books, then list_lessons. Use start_study_session for guided study,
prepare_quiz for one-question-at-a-time practice, get_lesson for paginated material,
get_page for original OCR pages, and search_textbook for ranked keyword search.
Resources: textbook://catalog, textbook://{book-id}/lessons,
textbook://{book-id}/pages/{source-page-id}. Prompts: study_lesson, quiz_lesson.

## Example request
Teach me section 1 from Living English Structure, then quiz me one question at a time.

## Sources and limitations
${corpus.data.books.map((b) => `- ${b.title}: ${b.lesson_count} sections, ${b.pdf_pages} scanned PDF pages; answer key available: ${b.has_answer_key}.`).join("\n")}
Follow next_offset until null for complete sections. Cite printed pages and PDF-page/side.
Flag uncertain OCR. Do not invent source passages or official answer keys.
Page images remain in the local book artifacts; consult the original PDF for visual exercises.

Server metadata: ${origin}/.well-known/mcp/server-card.json
Health: ${origin}/health
`;
}

export function landingPage(origin: string): string {
  const endpoint = escape(`${origin}/mcp`);
  return `<!doctype html>
<html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>English Textbook Tutor</title>
<style>
:root{color-scheme:light dark;font:17px/1.65 system-ui,sans-serif;background:#f6f5f1;color:#202d28}
body{max-width:760px;margin:0 auto;padding:64px 24px}h1{font-size:clamp(2.1rem,6vw,3.2rem);line-height:1.12;letter-spacing:-.04em;margin:12px 0 24px}
h2{font-size:1.1rem;margin-top:36px}.tag{font-size:.75rem;text-transform:uppercase;letter-spacing:.12em;color:#48634f}
code{font: .9rem/1.6 ui-monospace,monospace;overflow-wrap:anywhere}.endpoint{display:block;padding:18px;border:1px solid #9fb0a2;border-radius:8px;background:#fff;user-select:all}
a{color:#315d40}li{margin:10px 0}.book{border-top:1px solid #cbd3cb;padding:14px 0}.muted,footer{color:#536359;font-size:.9rem}footer{margin-top:48px}
@media(prefers-color-scheme:dark){:root{background:#14201a;color:#edf2ed}.endpoint{background:#1e3025;border-color:#4c6653}a,.tag{color:#add5b7}.muted,footer{color:#a4b5a8}.book{border-color:#405047}}
</style>
<main><span class="tag">English textbooks · MCP</span><h1>Your textbook.<br>Your AI tutor.</h1>
<p>Study the original explanations, practise the exercises, and work through mistakes with the AI assistant you already use.</p>
<h2>Connect in three steps</h2><ol>
<li>Open your AI app’s settings for MCP servers, apps, or connectors.</li>
<li>Add a remote <strong>Streamable HTTP</strong> server with <strong>no authentication</strong>, using this URL:</li></ol>
<code class="endpoint">${endpoint}</code>
<ol start="3"><li>Enable the textbook tools in a chat and try:</li></ol>
<blockquote>Teach me section 1 from Living English Structure. Then quiz me one question at a time and explain my mistakes.</blockquote>
<p class="muted">Your client must support remote MCP and allow custom servers. Your chosen AI model does the teaching; this server provides the textbook sources.</p>
<h2>On the bookshelf</h2>
${corpus.data.books.map((book) => `<div class="book"><strong>${escape(book.title)}</strong><br><span class="muted">${escape(book.author ?? "")} · ${book.lesson_count} sections · ${book.pdf_pages} scanned PDF pages</span></div>`).join("")}
<p class="muted">Source pages and OCR confidence accompany the material. The assistant should flag unclear text and distinguish inferred answers from published keys. Your study progress stays in your conversation.</p>
</main><footer><a href="/llms.txt">Agent setup instructions</a> · <a href="/.well-known/mcp/server-card.json">Server details</a> · <a href="/health">Health</a></footer></html>`;
}
