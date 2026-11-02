# Retrieval diagnosis and rejected admission candidate

The November 2 development experiment rejects `semantic-admission-dev-v1` for production. Requiring a semantic match before admitting a result removes keyword-only entries, but retains important task mismatches and also removes plausible alternatives. No production ranker, index, public contract, or held-out judgment changed.

## Evidence and scope

The [ten synthetic development tasks](task-review.md) were replayed against the existing populated local Pixeltable catalog. Its revision is `2e1cd1b997b61fed`, with 570 published packages. This is an earlier snapshot than the November 1 production capture at `e70f4831fc1368c3`. The local baseline reproduces the ordered upstream identities of all thirty production recommendations. That agreement does not make the source revisions or profiles identical.

The frozen baseline remains `profile-hybrid-v2`. The diagnostic retains up to fifty candidates per retrieval channel, their scores and original order, the pinned catalog metadata, the retrieval implementation digest, and the development prompt digest. The recorded pools replay exactly without database or model calls. Human decisions remain blank. The experiment is not a relevance evaluation, a calibrated abstention test, or a release gate.

Of thirty baseline slots, eleven came from the keyword channel without an above-floor semantic match. The existing semantic floor is 0.62. Some questionable recommendations came directly from semantic retrieval, including both Azure cost tools for the pricing-page task and transcription for existing interview transcripts. Keyword admission alone therefore cannot explain or fix those misses.

## Candidate behavior

`semantic-admission-dev-v1` admits only candidates already above the existing semantic floor. Keyword rank still contributes among those candidates. The candidate is applied to successful semantic captures only; it defines no outage or fallback behavior and is not available in the public service.

| Case | Candidate result | Interpretation to review |
| --- | --- | --- |
| W1 | No results | Removes the adjacent writing workflows, without finding a customer-update capability. |
| W2 | Same three results | Leaves the follow-up-question suggestion alongside the two writing skills. |
| D1 | Same three results | Retains both Azure cost tools for a pricing-page request. |
| D2 | Screen-reader testing only | Removes the unrelated Azure result, but also removes accessibility compliance. |
| E1 | Same three results | Retains the unstated Python assumption. |
| E2 | Same three results | Retains the PostgreSQL and Spark assumptions. |
| R1 | Transcription and data storytelling | Removes the session-diagnosis result but retains the workflow mismatch. |
| R2 | No results | Does not find a general evidence-based product comparison. |
| O1 | On-call handoff only | Removes Figma, but also removes incident runbook templates. |
| O2 | Same three results | Retains the technical-decision and Notion assumptions. |

These are agent interpretations of declared metadata. Accessibility compliance and incident runbooks are plausible losses, not human-approved answers. Two empty candidate responses are not two proven correct abstentions. The candidate is rejected because it leaves the targeted semantic mismatches unresolved while losing plausible alternatives. It is not presented as a measured relevance regression or improvement.

## Reproduction

The CLI accepts one to twenty separate development tasks, verifies the held-out overlap guard, and refuses an existing output directory. A capture uses only reads against an existing local catalog. It does not apply a schema, republish sources, update a service, execute indexed packages, or call a hosted model. The local embedding model must already be available. Keep task files, complete catalog snapshots, and diagnostic output private under `.audit`.

```sh
PXT_PORT=22183 HF_HUB_OFFLINE=1 .venv/bin/python scripts/diagnose_search.py \
  --prompts /path/to/development-prompts.json \
  --target agentforge_dev --output .audit/new-search-capture

.venv/bin/python scripts/diagnose_search.py \
  --prompts /path/to/development-prompts.json \
  --replay .audit/new-search-capture/report.json --output .audit/new-search-replay
```

The prompt file contains a `prompts` list with `id` and `text` per task. An optional `domain` field is descriptive only. Requests use Codex and a result limit of three. The comparison exports source identities and counts, not an invented human score. Complete output contains `report.json`; `progress.jsonl` retains completed cases and an error type if a later case fails.

The first diagnostic attempt rejected near ties because it assumed projected vector scores were strictly sorted. The corrected diagnostic preserves the backend order. A later replay recomputed keyword scores with last-decimal differences from floating-point summation order. Replay now uses both captured pools. Both earlier attempts remain in private evidence; neither is rewritten as an exact successful replay.

## Next decision

Human review still needs to distinguish useful, conditional, and unsuitable capabilities. A future candidate must address the requested operation and output, rather than suppressing an entire retrieval channel or adding exceptions for these ten tasks. It needs a separate version and development evidence before any release evaluation. The original ranker and all previous failures remain preserved.
