# Discovery pilot evaluation

The frozen corpus contains 100 synthetic candidate requests. It has 50 relevant
requests, 25 substantive requests with no approved baseline match, and 25 trivial
turns. Each of writing, design, engineering, research, and operations has ten
relevant requests. The set was authored from the 90-skill baseline before final
tuning. No retrieval outcomes or later enrichment informed its labels.

These are machine-authored candidates awaiting product review. The AC-03
human-review gate has not passed. No-match judgments refer to the recorded
baseline, so a human must check them against the final evaluated catalog.

`prompts.json` contains only IDs and task text. `labels.json` contains strata,
approved identities, rationales, and pinned source evidence. Give a tested
harness only its selected task text. Keep labels, this guide, the freeze
manifest, and evaluation reports outside that harness's context. Do not tune on
held-out prompts or outcomes. The tooling owner should return aggregate status
to the ranking owner without sharing held-out case details during tuning.

`freeze.json` records exact file digests, the combined corpus digest, source
revision provenance, and the pending human-review status. Changing a frozen
prompt or label invalidates the digest. A reviewed successor must receive a
new freeze and be recorded separately. Do not rewrite the candidate freeze to
make an evaluated outcome look better.

## Data and scoring

`evaluation/core.py` validates frozen input, handles bounded HTTP attempts, and
scores direct retrieval. Captures retain case IDs, status, attempt counts,
elapsed time, result identities, source revisions, retrieval mode, catalog
revision, and ranking version. Reports omit task text, raw response bodies,
error bodies, headers, credentials, and transcripts.

An approved identity anywhere in the first three results counts once for a
relevant request. HTTP failures and timeouts remain errors, including on
no-match cases. They are never counted as successful abstentions. No-match
false positives are any returned candidates on a labeled no-match case.
The report gives the successful denominator beside that rate. Trivial
retrieval matches are separate from harness behavior.

A full run requires every frozen case to have a valid response and a single
catalog revision and ranking version. The candidate AC-03 threshold is at
least 40 approved top-three results among 50 relevant requests. The report
always marks release gates unestablished and human review pending.

Direct HTTP retrieval does not measure AC-04. Fresh-session records must count
network searches separately from visible suggestions. They must record the
harness version, model, settings and installed-instruction digests, rejection,
accepted loading, and activation limits. Matched task-quality comparisons must
use the same inputs and settings with and without discovery. Neither a
retrieval result nor an installation proves task improvement or superiority
to another discovery service.

The [October 29 fresh-session diagnostic](harness-smoke.md) records a bounded
development check of ordinary triggering, a trivial turn, transport recovery,
and a decline follow-up. It preserves the incomplete task and excluded capture.
It does not establish the full reliability or adoption gates.

## Commands

Run from the platform checkout with its existing Python environment. No extra
runtime package is needed by the tools.

```sh
.venv/bin/python -m pytest -q tests/test_evaluation.py
.venv/bin/python scripts/evaluate.py --help
.venv/bin/python scripts/observe.py --help
```

## Local human review

`scripts/review.py` prepares a standalone worksheet containing the task text
and full pinned catalog. It omits the candidate labels, approved identities,
rationales, and retrieval outputs. Tasks have a deterministic shuffled order;
the catalog is alphabetical. Filtering the catalog is a local text filter,
not the production ranker. Source instructions render as text and never run.

Prepare a worksheet from the exact immutable-row snapshot being evaluated:

```sh
mkdir -p .audit/relevance-review
.venv/bin/python scripts/review.py prepare \
  --catalog .audit/pilot-final-catalog.json \
  --output .audit/relevance-review/worksheet.html
.venv/bin/python scripts/review.py serve .audit/relevance-review/worksheet.html
```

Preparation uses the website's installed Geist font and embeds its license.
Run `npm ci` first if the website dependencies are absent. The worksheet has
no network dependencies. Serving binds only to `127.0.0.1`, prints its actual
URL, and serves only that one file. It cannot read neighboring audit files.
The HTML can also be opened directly without the local server.

The reviewer can revise task wording, classify the task, choose useful skills,
inspect pinned evidence, and record a reason. Browser storage retains drafts
when available. **Save review file** exports a portable JSON draft, and **Load
review file** restores one. Keep exports private because they include task text
and reviewer notes. A draft may be incomplete; finalization refuses it.

After personally completing every task, the named reviewer can record an
attestation. Finalize into a new directory with the same corpus and snapshot:

```sh
.venv/bin/python scripts/review.py finalize \
  --catalog .audit/pilot-final-catalog.json \
  --annotations /absolute/path/to/exported-review.json \
  --output .audit/relevance-review/reviewed-successor
```

Finalization validates all identities, timestamps, reasons, distinct task text,
the 50/25/25 split, and ten relevant tasks per family. It binds the export to
both input digests and retains the selected immutable version evidence. It
refuses an existing output directory. The original prompts, labels, freeze,
and measured failures remain unchanged.

The successor records `attested_not_independently_verified`. This tool cannot
authenticate a human or retroactively satisfy a pre-tuning review gate. A
product owner must accept the review and freeze any successor before future
ranking work. Existing evaluation reports continue to leave release gates
unestablished. The worksheet alone does not improve the 37/50 candidate result.

Use `prepare --demo` to test the interface with five separate synthetic tasks.
An overlap check keeps those tasks distinct from the held-out corpus. The demo
is labeled and has a different packet identity; its export cannot finalize the
real corpus. Visual and implementation reviewers should inspect only this demo,
not the actual held-out worksheet.

A live run defaults to five cases. Requests contain only a synthetic task,
harness identifier, and a result limit of three. The default four-second gap
stays below the public gateway's 20-per-minute allowance. Retries share the
same total request budget. A 429 honors a bounded `Retry-After`. A requested
wait above 30 seconds ends the case as rate-limited instead of retrying early.
Timeout, HTTP error, invalid JSON, invalid response, and exhausted request
budget have distinct outcomes. Never launch the full batch while tuning.

```sh
.venv/bin/python scripts/evaluate.py \
  --endpoint https://agentforge-five-sandy.vercel.app/api/v1/search \
  --limit-cases 5 --max-requests 8 --output .audit/evaluation/smoke.json
```

After product review and ranking freeze, an evaluator can explicitly run all
100 cases against the fixed endpoint. Use one catalog revision, stop tuning,
and preserve the resulting capture. A changing revision invalidates comparison.

```sh
.venv/bin/python scripts/evaluate.py \
  --endpoint https://agentforge-five-sandy.vercel.app/api/v1/search \
  --limit-cases 100 --max-requests 120 \
  --harness codex --harness-version VERSION --model MODEL \
  --settings-sha256 SETTINGS_DIGEST --instructions-sha256 INSTRUCTIONS_DIGEST \
  --output .audit/evaluation/final.json
```

The capture is `final.cases.json`. Replay it without network requests:

```sh
.venv/bin/python scripts/evaluate.py \
  --responses .audit/evaluation/final.cases.json \
  --output .audit/evaluation/replay.json
```

A capture has `corpus_sha256` and a `cases` array. Each case has `id`, `outcome`,
`http_status`, `attempts`, and `elapsed_ms`. Successful cases can contain either
the normalized `rows` and `meta` produced by the runner or the public response
under `response`. Raw input captures are evaluator-controlled and may contain
unexpected fields. The runner writes only the normalized allowlist.

Pass `--development-prompts FILE` to reject normalized exact overlap with a
separate development set using the same `prompts` array format. Exit code 0
means a complete consistent run, 2 means incomplete or mixed-revision evidence,
and 1 means invalid input or an execution error. None establishes a release gate.
The sibling `.failed.json` report uses IDs and identities, not prompt text.

## Operating observation

The collector appends public page availability, a catalog sample, source-check
freshness, and one fixed synthetic search probe to JSONL. It does not retain
page bodies, skill descriptions, source URLs, task text, or error bodies. It
reports the public count separately from the number of rows whose freshness
was sampled. Unknown timestamps do not count as fresh. A publication timestamp
is not a successful source check.

Run one sample first:

```sh
.venv/bin/python scripts/observe.py \
  --origin https://agentforge-five-sandy.vercel.app \
  --samples 1 --max-requests 6 --output .audit/observation/public.jsonl
```

An operator can keep the collector process running for 49 hourly samples to
span at least 48 elapsed hours. The request budget includes every retry.
This command does not create a scheduled job.

```sh
.venv/bin/python scripts/observe.py \
  --origin https://agentforge-five-sandy.vercel.app \
  --samples 49 --interval-seconds 3600 --max-requests 300 \
  --output .audit/observation/public.jsonl
```

Public probes cannot establish private refresh-job failures or provider spend.
Those fields remain unavailable and need separately recorded operations
reports with an owner and resolution for failures. Every record leaves
`observation_48h_complete` false. An operator must review the actual timestamp
span, gaps, freshness, job evidence, and spend before accepting AC-12. The
presence of a collector or 49 requested samples is not completed observation.

The implementation uses Model the Domain to keep case outcomes explicit,
Boundary Discipline to validate captured and network data before scoring,
and Build the Lever to make the evidence reproducible. Local HTTP fixtures
and metric fixtures verify behavior without querying the public service.
