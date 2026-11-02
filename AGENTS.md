# AgentForge platform

Build from the company discovery-service PRD. This repository is proprietary,
including its website. Never apply the skill repository's Apache license here.

`app.py` owns the Pixeltable models, embedding index, and Cloud service routes.
Keep search logic in the backend. The Vercel gateway forwards the public search
contract and protects the service key. Only its fixed search and catalog routes
are public. The refresh route requires a separate secret unavailable to Vercel.

Do not execute indexed skills. Preserve source revisions, original metadata,
and the distinction between inferred compatibility and demonstrated support.
Never commit `.audit`, source snapshots, credentials, `.env` files, or `.vercel`.
Use supported Pixeltable operations for schema and services. Keep the database
isolated from other applications and avoid destructive schema changes.

After implementation changes, run `npm run check`, `npm test`, `npm run build`,
and `python -m pytest -q`. Include the populated-catalog regression when changing
publication or retrieval. Verify the actual HTTP route and browser flow before
claiming a deployment works. No paid add-ons or plan upgrades without approval.

## Product identity

| Rule | Shared owner |
| --- | --- |
| Preserve the founder's tagline when changing layout or metadata. | `src/lib/brand.ts`; the hero and social metadata import the same copy. |

<!-- BEGIN:nextjs-agent-rules -->

## This is NOT the Next.js you know

This version has breaking changes — APIs, conventions, and file structure may all differ from your training data. Read the relevant guide in `node_modules/next/dist/docs/` (resolved from this file's directory; in monorepos the `next` package may not be visible from the repo root) before writing any code. Heed deprecation notices.

This block is written and re-added by `next dev` — verify at `node_modules/next/dist/server/lib/generate-agent-files.js`. Removing it from a diff only re-creates the uncommitted change; committing it with your work keeps the tree clean.

<!-- END:nextjs-agent-rules -->
