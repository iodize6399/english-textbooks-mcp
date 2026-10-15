import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";
import { Client } from "@modelcontextprotocol/client";
import { StdioClientTransport } from "@modelcontextprotocol/client/stdio";

const client = new Client({ name: "english-textbooks-stdio-smoke", version: "1.0.0" }, { capabilities: {} });
const transport = new StdioClientTransport({ command: process.execPath,
  args: ["--experimental-strip-types", fileURLToPath(new URL("../src/stdio.ts", import.meta.url))],
  stderr: "inherit" });
try {
  await client.connect(transport);
  const tools = await client.listTools();
  assert.equal(tools.tools.length, 7);
  const result = await client.callTool({ name: "get_lesson", arguments: { book_id: "living-english-structure", lesson_number: 1, section_id: "1.3" } });
  assert.notEqual(result.isError, true);
  const material = result.structuredContent ?? JSON.parse(result.content[0].text);
  assert(material.chunks.length > 0 && material.chunks.every((c) => c.section_id === "1.3"));
  console.log("Local stdio MCP: connection, tool discovery, and exercise retrieval passed.");
} finally {
  await client.close();
}
