import { StdioServerTransport } from "@modelcontextprotocol/server/stdio";
import { createTextbookServer } from "./server.ts";

// Keep stdout exclusively for MCP messages so local clients can launch directly.
await createTextbookServer().connect(new StdioServerTransport());
