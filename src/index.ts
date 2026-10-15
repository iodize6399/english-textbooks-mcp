import { createMcpHandler } from "agents/mcp/server";
import { localhostAllowedHostnames } from "@modelcontextprotocol/server";
import { corpus } from "./corpus.ts";
import { landingPage, llmsText, serverCard } from "./landing.ts";
import { createTextbookServer } from "./server.ts";

// The factory creates a fresh SDK server for each request. Only the immutable
// textbook corpus/search index is shared; no learner or session state is held.
const allowedHostnames = ["lingo.555420.xyz", ...localhostAllowedHostnames()];
const mcp = createMcpHandler(createTextbookServer, {
  route: "/mcp", responseMode: "json", allowedHostnames,
  allowedOriginHostnames: allowedHostnames,
});

function response(body: string | null, type: string, status = 200, extra: Record<string, string> = {}): Response {
  return new Response(body, { status, headers: {
    "Content-Type": `${type}; charset=utf-8`, "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer", "X-Frame-Options": "DENY",
    "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; frame-ancestors 'none'; base-uri 'none'",
    ...extra,
  } });
}

export default {
  async fetch(request: Request, env: Env, ctx: ExecutionContext): Promise<Response> {
    const url = new URL(request.url);
    if (url.pathname === "/mcp") return mcp(request, env, ctx);
    if (request.method !== "GET" && request.method !== "HEAD") return response("Method not allowed", "text/plain", 405, { Allow: "GET, HEAD" });
    const head = request.method === "HEAD";
    switch (url.pathname) {
      case "/": return response(head ? null : landingPage(url.origin), "text/html");
      case "/llms.txt": return response(head ? null : llmsText(url.origin), "text/plain");
      case "/.well-known/mcp/server-card.json":
        return response(head ? null : JSON.stringify(serverCard(url.origin)), "application/json", 200, { "Access-Control-Allow-Origin": "*" });
      case "/health":
        return response(head ? null : JSON.stringify({ status: "ok", name: "english-textbooks", version: "1.0.0",
          books: corpus.data.books.length, lessons: corpus.data.lessons.length, pages: corpus.data.pages.length,
          chunks: corpus.data.chunks.length, corpus_sha256: corpus.data.corpus_sha256 }), "application/json", 200, { "Cache-Control": "no-store" });
      default: return response("Not found", "text/plain", 404);
    }
  },
} satisfies ExportedHandler<Env>;
