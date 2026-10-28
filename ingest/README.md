# Source collection and capability profiles

Run `python -m ingest.catalog collect --snapshot .audit/catalog-source.json` from
this repository. Collection reads public manifests as data. It does not install
packages, run upstream code, or call a model provider. GitHub API authentication
uses an explicit `GH_TOKEN`/`GITHUB_TOKEN` or the local GitHub CLI credential;
credentials are never saved in the snapshot. The command makes no cloud writes.

The versioned [source policy](source-policy.json) specifies direct repositories,
allowed directory roots, exclusions, a registry query, and collection bounds.
The default policy permits at most 12 repositories, 1,000 skill directories, and
200 supporting files per directory. An explicit `--repo owner/repo` bypasses
registry discovery and keeps the conservative 100-directory limit per source.
Overflow refuses the collection instead of silently truncating it.

The default roots select original skill directories and exclude test fixtures,
examples, generated distribution trees, and vendored packages. Impeccable uses
only `.agents/skills/`, so its generated harness copies do not become separate
listings. Two explicit package exclusions, OpenAI's `cloudflare-deploy` and
Microsoft's `microsoft-foundry`, currently exceed the 200-file public contract.
They are omitted by policy instead of publishing an incomplete file manifest.
Nested `SKILL.md` files inside a listed skill are supporting package resources,
not additional directory listings.
Changes to these exclusions require source review.

## Registry discovery

The connector implements the protocol used by Vercel's first-party
[`searchSkillsAPI()`](https://github.com/vercel-labs/skills/blob/d8eca76d5dbe47df2d146d036e32534b74ece57a/src/find.ts):
`GET https://skills.sh/api/search?q=workflow&limit=20&owner=wshobson`.
The [CLI reference](https://github.com/vercel-labs/skills/blob/d8eca76d5dbe47df2d146d036e32534b74ece57a/docs/commands.md)
describes skill discovery and GitHub source forms. This is an HTTP read of the
same endpoint; AgentForge does not run the registry CLI or send its telemetry.

The response's `skills[].source` supplies an upstream GitHub repository. Only
repositories explicitly allowed in the policy are accepted. The connector then
enumerates actual `SKILL.md` directories from that repository's pinned GitHub
commit. The registry discovers the repository; it does not provide package
content, canonical directory names, or compatibility claims. The current query
discovers `wshobson/agents`. This bounded pilot connector does not claim exhaustive
coverage of skills.sh or automatic approval of new repositories.

Repeated registry results and direct registrations merge by case-normalized
GitHub repository and exact directory path. Their `discovered_via` URLs remain
on the one upstream listing. Distinct forks retain distinct upstream identities.
The collector does not infer that two different repositories have the same
maintainer or collapse them solely because their content happens to match.

## Pinned source and extraction

The collector resolves each source's default branch to a commit, requests its
complete recursive Git tree, and verifies the fetched manifest against its Git
blob SHA-1. Truncated trees, file-count overflow, symlinks, submodules, and unsafe
package paths fail collection. Supporting files are recorded with package-relative
paths and Git blob hashes. Supporting content is fetched only during the separate
inspection and adoption path.

The ignored snapshot includes each immutable version row and its public payload.
Its `.sources/` directory retains fetched manifests and registry responses.
A later collection can reuse cached manifests only after verifying them against
the freshly resolved commit and Git tree. The
summary records source commits, policy checksum, counts by task family and source
kind, collection time, and explicit failures. Task families are simple descriptive
groups, not evaluation labels. Source kinds may overlap when a directory has both
direct and registry discovery provenance; the skill count always uses unique
canonical directories.

Original frontmatter lives in `author_metadata`. YAML dates become ISO strings;
unsupported YAML types, recursive aliases, and metadata exceeding the public
contract are rejected. `name` and `summary` retain the author's declaration.
The `sections-v1` profile extractor reads explicit frontmatter and body sections
for appropriate tasks, exclusions, outputs, examples, prerequisites, required
tools, credentials, and declared harness support. Every extracted value has a
bounded source quote and location. Description-derived task/output phrases and
fallback task examples are marked inferred. Example text and ordinary procedure
negations do not become exclusions. Author `allowed-tools` permissions remain
metadata; they do not establish that every permitted tool is a prerequisite.

Missing outputs, tools, accounts, or harness declarations stay unknown. An empty
list means the extractor found no declaration; it does not prove no setup is
needed. Author compatibility claims are declared, including claims of testing.
Only independent execution evidence could establish tested support, and this
collector never assigns it. No source checksum or static profile is a safety
review. Profiles are intentionally bounded and will miss declarations in
unrecognized sections, tables, code blocks, or external references.

## Immutable publication and refresh

`version_id_for(skill, body)` in `agentforge_backend.publish` returns
`skill_id@source_revision#sha256` for extracted profiles. The digest covers the
canonical public payload and exact body, including extractor version and package
file hashes. Source/harness last-check times and search-specific `fit` do not
create new versions. Legacy profiles retain `skill_id@source_revision` validation.

`VersionInput` verifies the ID, profile revision, and exact agreement between
search fields and payload before publication. Reusing an immutable ID with
different content fails before pointer updates. Rechecks update source pointers'
last-check times while preserving stored version rows. Publish requests permit
at most 2,000 rows and 100 complete repositories; HTTP applies a separate 32 MiB
private-refresh limit.

A successful collection writes the requested snapshot and summary. A failed run
writes `.failed.json` and `.failed.summary.json`, preserves the previous complete
snapshot, and never marks repositories complete. Both local publication and
`refresh-http` refuse a failed collection. A snapshot checksum binds the completion
summary to its exact file, so an interrupted write cannot reuse an older summary. Publication activates source pointers
only after all new versions and embeddings insert successfully; only explicitly
complete repositories can withdraw absent directories. Historical rows remain.

The existing refresh workflow uses the default source policy. Run
`python -m ingest.catalog refresh-http --snapshot .audit/catalog-source.json` only
with the private refresh URL and credentials configured. This is an operator
write; collection and verification do not require it.
