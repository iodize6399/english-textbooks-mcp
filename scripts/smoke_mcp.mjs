import assert from "node:assert/strict";
import { Client, StreamableHTTPClientTransport } from "@modelcontextprotocol/client";

const endpoint = new URL(process.argv[2] ?? "http://127.0.0.1:8787/mcp");
const origin = endpoint.origin;
const client = new Client({ name: "english-textbooks-smoke", version: "1.0.0" }, { capabilities: {} });
const transport = new StreamableHTTPClientTransport(endpoint);

function content(result) {
  assert.notEqual(result.isError, true, JSON.stringify(result.content));
  return result.structuredContent ?? JSON.parse(result.content.find((c) => c.type === "text").text);
}

try {
  const health = await fetch(`${origin}/health`).then((r) => r.json());
  assert.equal(health.status, "ok");
  assert(health.books >= 1 && health.lessons >= 58);
  await client.connect(transport);
  const tools = await client.listTools();
  assert.equal(tools.tools.length, 7);
  assert(tools.tools.every((tool) => tool.annotations?.readOnlyHint));
  const catalog = content(await client.callTool({ name: "list_books", arguments: {} }));
  const book = catalog.books.find((book) => book.id === "living-english-structure");
  assert(book);
  const args = { book_id: book.id };
  const lessons = content(await client.callTool({ name: "list_lessons", arguments: args }));
  assert.equal(lessons.lessons.length, 58);
  const lesson = content(await client.callTool({ name: "get_lesson", arguments: { ...args, lesson_number: 1, section_id: "1.3", limit: 1 } }));
  assert.equal(lesson.chunks.length, 1);
  assert.equal(lesson.chunks[0].section_id, "1.3");
  assert.match(lesson.chunks[0].citation, /PDF p\./);
  const page = content(await client.callTool({ name: "get_page", arguments: { ...args, page: "19" } }));
  assert.equal(page.id, "pdf-015-right");
  const search = content(await client.callTool({ name: "search_textbook", arguments: { ...args, query: "present perfect", lesson_number: 23 } }));
  assert(search.results.length > 0 && search.results.every((c) => c.lesson_number === 23));
  const study = content(await client.callTool({ name: "start_study_session", arguments: { ...args, lesson_number: 9 } }));
  assert(study.teaching_protocol.length > 0 && study.chunks.every((c) => c.lesson_number === 9));
  const quiz = content(await client.callTool({ name: "prepare_quiz", arguments: { ...args, lesson_number: 10, question_count: 3 } }));
  assert.equal(quiz.question_count, 3);
  assert.equal(quiz.book.has_answer_key, false);
  assert(quiz.quiz_protocol.some((rule) => rule.includes("exactly one question")));
  const missing = await client.callTool({ name: "get_lesson", arguments: { ...args, lesson_number: 999 } });
  assert.equal(missing.isError, true);
  const resources = await client.listResources();
  assert(resources.resources.some((resource) => resource.uri === "textbook://catalog"));
  const resource = await client.readResource({ uri: lesson.chunks[0].source_uri });
  assert.equal(JSON.parse(resource.contents[0].text).printed_page, lesson.chunks[0].printed_page);
  const templates = await client.listResourceTemplates();
  assert.equal(templates.resourceTemplates.length, 1);
  const prompts = await client.listPrompts();
  assert.equal(prompts.prompts.length, 2);
  for (const name of ["study_lesson", "quiz_lesson"]) {
    const prompt = await client.getPrompt({ name, arguments: { ...args, lesson_number: "1" } });
    assert(prompt.messages[0].content.text.includes("SOURCE MATERIAL"));
  }
  console.log("MCP client: all 7 tools, resources, page template, and both prompts passed.");

  // Stateless compatibility for clients on the established 2025 protocol.
  for (const version of ["2025-03-26", "2025-11-25"]) {
    const response = await fetch(endpoint, { method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json, text/event-stream", "MCP-Protocol-Version": version },
      body: JSON.stringify({ jsonrpc: "2.0", id: 1, method: "initialize", params: {
        protocolVersion: version, capabilities: {}, clientInfo: { name: "legacy-smoke", version: "1.0.0" },
      } }),
    });
    assert(response.ok, `Legacy initialization failed: ${version} (${response.status})`);
    const body = await response.text();
    const data = response.headers.get("content-type")?.includes("text/event-stream")
      ? JSON.parse(body.split("\n").find((line) => line.startsWith("data: ")).slice(6))
      : JSON.parse(body);
    assert(data.result.serverInfo.name === "english-textbooks");
  }
  const browserRequest = await fetch(endpoint, { method: "POST",
    headers: { Origin: origin, "Content-Type": "application/json", Accept: "application/json, text/event-stream", "MCP-Protocol-Version": "2025-11-25" },
    body: JSON.stringify({ jsonrpc: "2.0", id: 2, method: "initialize", params: {
      protocolVersion: "2025-11-25", capabilities: {}, clientInfo: { name: "browser-smoke", version: "1.0.0" },
    } }),
  });
  assert(browserRequest.ok, `Same-origin MCP request rejected (${browserRequest.status})`);
  await browserRequest.text();
  const denied = await fetch(endpoint, { method: "POST", headers: { Origin: "https://untrusted.invalid", "Content-Type": "application/json" }, body: "{}" });
  assert.equal(denied.status, 403);
  for (const route of ["/", "/llms.txt", "/health", "/.well-known/mcp/server-card.json"]) {
    assert.equal((await fetch(`${origin}${route}`)).status, 200);
    assert.equal((await fetch(`${origin}${route}`, { method: "HEAD" })).status, 200);
  }
  assert.equal((await fetch(`${origin}/missing`)).status, 404);
  assert.equal((await fetch(`${origin}/health`, { method: "POST" })).status, 405);
  const card = await fetch(`${origin}/.well-known/mcp/server-card.json`).then((r) => r.json());
  assert.equal(card.endpoint, endpoint.href);
  console.log("HTTP: 2025 protocol compatibility, same/foreign Origin validation, setup/metadata routes, endpoint URL, HEAD and error responses passed.");
} finally {
  await client.close();
}
