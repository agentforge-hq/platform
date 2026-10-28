# AgentForge platform

Find useful agent skills from an ordinary task description. This repository
contains the Pixeltable Cloud catalog, source collector, hybrid search service,
and a single-page website with a shared public query endpoint.

Live pilot: [lordoftheskill.com](https://lordoftheskill.com).
The original Vercel address remains available.

The website and native client use `POST /api/v1/search`. The website also uses
`GET /api/v1/catalog` for browsing. Vercel keeps the Cloud service credential on
the server. The public gateway cannot forward arbitrary paths or ingest data.

## Discovery pilot

Search returns a short list with quotes from pinned source instructions, extracted
outputs and applicability, known tool/account requirements, and explicit unknown
harness support. Optional request constraints describe tool names and setup/account
preferences; the client never needs to upload an installed-skill inventory.
The website initially shows three results, with details and source evidence on
request. Browse filters and pages the canonical catalog before returning a page.

Profiles retain bounded original author metadata and distinguish declarations
from deterministic inferences. New immutable IDs cover the source revision,
extracted profile, supporting-file hashes, and body. Refresh dates do not change
the content identity. Registry discoveries resolve to the upstream GitHub
directory; generated harness copies do not inflate coverage.

The native discovery preview can prepare an exact selected result in external
quarantine. Promotion binds the reviewed bytes, destination, harness and recovery
state. It preserves an existing install and requires a separate deliberate apply.
Neither provenance nor installation establishes safety, activation or task lift.

## Runtime

- Next.js 16, React, TypeScript, and Zod serve the website and public gateway.
- Pixeltable 0.7.20 declares the source pointers, immutable skill versions,
  computed search text, and embedding index in `app.py`.
- FastEmbed runs BAAI's small English embedding model on the backend. No paid
  model API key or separate vector database is required.
- Public GitHub manifests are read without executing downloaded scripts.
  The bounded source policy uses direct repositories and registry discovery,
  excluding generated harness copies and fixtures. See [source collection](ingest/README.md).

## Run locally

Use Node.js 24 and Python 3.11. Install `requirements.txt` in a virtual environment,
then install the Node dependencies with `npm ci`.

Apply the schema with `pxt schema update app.py agentforge_dev -f`. Start its
HTTP service with `pxt service update app.py agentforge_dev -f`, then obtain the
assigned URL with `pxt service list agentforge_dev --json`.

Run `python -m ingest.catalog collect`, then
`python -m ingest.catalog publish --target agentforge_dev`. These commands save
raw source material under the ignored `.audit` directory. Repeating publication
preserves immutable versions and does not insert an unchanged version again.

Copy `.env.example` to `.env.local`, set the local service URL, and use a dummy
service key for a local backend. Run `npm run dev`. Hosted keys stay out of all
`NEXT_PUBLIC_` variables and source files.

## Deploy

The dedicated Cloud target is configured in `pixeltable.toml`. Its runtime,
schema, and HTTP service are separate operations: `pxt db update`,
`pxt schema update app.py`, and `pxt service update app.py`, all with the Cloud
target. Do not reuse a database containing an unrelated application's project.

Vercel hosts only the frontend and public gateway. Set `PIXELTABLE_SERVICE_URL`
and `PIXELTABLE_SERVICE_KEY` as encrypted deployment variables. The Cloud key
must be scoped to the AgentForge app service. `.vercelignore` excludes backend
files, local environments, credentials, source snapshots, and audit artifacts.
The selected workspace is MoS. No plan upgrade or paid add-on is required by
this implementation. Existing provider usage limits and billing still apply.

## Refresh

`Refresh skill index` runs daily and supports manual dispatch. It collects public
manifests before publication, refuses incomplete collections, and calls the
private refresh route with two separate credentials. The Cloud service key is
scoped to this app. `AGENTFORGE_INDEX_TOKEN` is an additional operator secret
that the public Vercel gateway does not receive.

The refresh job requires these GitHub Actions secrets:

- `AGENTFORGE_REFRESH_URL`: the Cloud app's `/internal/refresh` route.
- `AGENTFORGE_REFRESH_SERVICE_KEY`: its scoped runtime key.
- `AGENTFORGE_INDEX_TOKEN`: the additional refresh credential.

The public search key alone cannot refresh the index. A source revision becomes
active after its rows and embeddings succeed. Complete source checks can
withdraw absent listings. Historical versions remain stored. A failed source
collection preserves the current published catalog.
Collection refuses sources above their policy limits and preserves the last
complete snapshot when any source fails. An explicit `--repo` uses a conservative
100-directory limit; the reviewed default policy permits larger sources.

## Verify

Run `npm run check`, `npm test`, and `npm run build`. Run `python -m pytest -q`
for backend unit and HTTP validation tests. Set `AGENTFORGE_TEST_TARGET` to an
isolated populated development catalog to include the real pointer-selection
regression. `scripts/export_contract.py` generates the public OpenAPI contract.

Native client tests and six-platform builds live in the separate
[AgentForge skill repository](https://github.com/agentforge-hq/agentforge).
The website links the experimental discovery preview bundles and their source.

## Current limits

This is an initial catalog, not an index of every skill. Search uses metadata
keyword scoring plus semantic retrieval and reciprocal rank fusion. Keyword
scoring currently reads the bounded pilot catalog; scale and relevance require
further evaluation. The initial profile-hybrid-v2 ranker weights semantic ranks
at 1 and keyword ranks at 0.1, with a 0.62 semantic floor. These are development
settings awaiting representative human-reviewed evaluation. Old and profiled
embedding indexes coexist during the additive rollout for rollback.
Compatibility is unknown unless declared or independently established; an
author's claim is never presented as an independent test.
A source checksum is provenance, not a security review. An installed skill's
implicit invocation depends on its harness.

The public gateway has a best-effort per-instance request limit. It is not a
shared global quota or a billing guarantee. Search outages are explicit errors;
semantic failures can yield labeled keyword-only results. Query bodies are not
intentionally persisted by the application, but infrastructure processes its
normal technical request logs.

See [evaluation](evaluation/README.md) for the frozen candidate set and bounded
retrieval/operating tools. Candidate scoring, fresh-session discovery, accepted
activation, task improvement, and 48 elapsed hours are separate evidence gates.

## License

Original platform code, tests, documents, and design are proprietary. All rights
reserved under [LICENSE](LICENSE). Public visibility grants no open-source reuse
license. The separate AgentForge skill and CLI are Apache-2.0. Upstream skills
and dependencies retain their own licenses.
