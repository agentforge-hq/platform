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
