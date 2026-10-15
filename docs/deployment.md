# Deployment

The MCP is hosted in the verified Cloudflare account, deployed through the
local Wrangler CLI. The connected Cloudflare plugin was not used.

| Item | Value |
| --- | --- |
| MCP endpoint | `https://lingo.555420.xyz/mcp` |
| Setup page | `https://lingo.555420.xyz/` |
| Transport / authentication | Streamable HTTP / None |
| Worker name | `english-textbooks-mcp` |
| GitHub repository | `iodize6399/english-textbooks-mcp` |
| Production branch | `main` |
| Custom domain | `lingo.555420.xyz` (Cloudflare-managed DNS and HTTPS) |
| `workers.dev` / preview URLs | Disabled for this Worker |
| Initial deployment date | 2026-10-15 |
| Initial deployed source commit | `1c29972f29b527333c9ad05577ecbb3fd32caba4` |
| Initial Worker version | `77ae1977-0df9-4a30-bcff-b91480739aa0` |

The initial release passed all 12 tests, corpus validation, type checks, the local
stdio smoke test, GitHub CI, and the public HTTP smoke test. The public test covers
all seven tools, resources and the page template, both prompts, 2025 protocol
compatibility, Origin validation, health metadata, and setup routes.

## Update directly with Wrangler

From the repository directory, using Node.js 24+ and Python 3.11+:

```sh
npm ci
npx wrangler login
npm run deploy
npm run smoke -- https://lingo.555420.xyz/mcp
```

`wrangler.jsonc` pins the verified Cloudflare account ID. Change it before deploying
a fork to another account. The serving Worker has no Mistral key or other runtime
secrets. The original scan remains local; the OCR corpus is committed to GitHub.

The public hostname is configured as a Worker custom domain in `wrangler.jsonc`.
The MCP HTTP handler allows that hostname and localhost for development; browser
Origins are checked against the same allowlist. A fork must update both the
Wrangler route and the handler's hostname before deploying to a different domain.

## Enable automatic deployments from GitHub

**Status: the initial release is live; the Cloudflare Builds connection still needs
to be completed in the account dashboard.** The authorized Wrangler OAuth login
can deploy Workers but receives HTTP 403 from the Builds API. Browser authorization
of the Cloudflare GitHub integration is a separate, one-time account action.

1. Open [Workers & Pages in this account](https://dash.cloudflare.com/e021878ea8b277c3ef28c01963a60482/workers-and-pages).
2. Select `english-textbooks-mcp`, then **Settings → Builds → Connect**.
3. Choose GitHub and authorize the Cloudflare Workers and Pages app for
   `iodize6399/english-textbooks-mcp`.
4. Use these build settings:

   | Setting | Value |
   | --- | --- |
   | Repository | `iodize6399/english-textbooks-mcp` |
   | Production branch | `main` |
   | Root directory | Repository root (`/`) |
   | Build command | `npm run check` |
   | Deploy command | `npx wrangler deploy` |
   | Build environment variable | `NODE_VERSION=24` |

5. Save the connection and allow the first build to finish. Cloudflare may ask to
   create or select its managed build token; this is configured in the dashboard
   and does not belong in GitHub source or this chat.
6. Verify the build succeeds and run the public smoke test above. Later pushes to
   `main` should trigger Cloudflare builds and production deployments.

The existing GitHub Actions workflow validates commits and pull requests. Cloudflare
Builds performs the deployment after the repository connection is enabled.

Official instructions: [connect an existing Worker](https://developers.cloudflare.com/workers/ci-cd/builds/#connect-an-existing-worker),
[GitHub integration](https://developers.cloudflare.com/workers/ci-cd/builds/git-integration/github-integration/),
and [Builds API prerequisites](https://developers.cloudflare.com/workers/ci-cd/builds/api-reference/#prerequisites).
