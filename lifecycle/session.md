# Discovery and source-inspection walk

## Who, and the job

The [job card](job.md) follows the person implied by the live page. This is an agent walkthrough with synthetic input, not a recorded human session. The task is to decide whether a skill could help turn release-delay notes into a customer update.

## What I checked

- Watched the live website on November 1. The main action is `Find a skill` beneath `What are you trying to do?`.
- Captured ten separate development searches and checked current catalog metadata. See [the task review](task-review.md). No held-out prompt or label is exposed, and no indexed package runs.
- Read `src/components/discovery.tsx`. The original `Copy review prompt` template contains the pinned source and integrity checks, but no submitted task. A real copy and paste into the search field, without submitting, confirmed that omission.

## The session

### The person tries to find help for a customer delay update

1. **Entry.** The page says `Describe what you’re trying to do. Discover useful skills`. They enter the release-delay request and choose `Find a skill`. The catalog receives focus and shows `Finding relevant skills.` and `Matching your task to useful capabilities…`.
2. **Decision.** The shortlist shows `Avoid Ai Writing`, `Changelog Automation`, and `Before You Build`. Its `Why this could help` text repeats declared source purpose. The agent review cannot establish a direct fit for authoring the customer update. First success remains unestablished.
3. **Inspection.** `Explore avoid-ai-writing` reveals `Before you use it`, `Harness compatibility: unknown`, a revision, `View source`, and `Copy review prompt`. This supplies provenance and leaves compatibility uncertainty visible. Extracted text also contains `Rewrite mode:**` and the awkward generated example `Help me with asked to remove AI-isms`.
4. **Handoff.** `Copy review prompt` changes to `Prompt copied`, followed by `Paste the review prompt into your agent.` Pasting the actual clipboard into the existing search field shows a source-review request without the customer-update task. A new agent conversation would need that missing context supplied again. The pasted prompt was not submitted as a search.
5. **Trouble, empty input.** An empty submission focuses the search field. No error or instruction is added. The field reports no browser validation message. This is a copy issue to review, not a network-failure claim.
6. **Trouble, unsupported work.** A request to arrange physical garage-door repair returns `No useful match this time.` and `Explore the catalog`. This is one observed abstention, not calibrated no-match reliability.
7. **Leaving.** The pinned source can be inspected and a review prompt copied. No skill was installed or activated. The release-update job has not reached a proven useful recommendation, so successful task completion and problems arising after success remain unmeasured.

## Where the job broke

| # | Moment | What they needed | What the product did | Change | Size |
| --- | --- | --- | --- | --- | --- |
| 1 | 2 | A capability that addresses the requested output | Related writing and product terms led to adjacent workflows. | Review operation/object matching and weak shortlist filling on the ten development cases. Keep human ratings pending and the frozen ranker intact. | Check first |
| 2 | 4 | The original task carried into the agent | The actual copied text omitted it. | Include the submitted search task in `Copy review prompt`, preserving the pinned source, integrity checks, package review and activation limits. | Flow |
| 3 | 3 | Readable extracted guidance | Markdown fragments and a malformed generated example appeared. | Clean the extraction in a separately versioned candidate; preserve original author text as evidence. | Small |
| 4 | 5 | A cue after submitting nothing | Focus moved to the field without an explanation. | Review a concise inline instruction beside `What are you trying to do?`. | Small |

Only row 2 is in the current implementation change. It follows the already-authorized task-to-agent journey. Ranking, extraction and validation changes remain review candidates. The ten-task judgments are not a human relevance sign-off.

## Handoff verification after the change

The November 1 local production build includes the submitted search task in the copied review prompt. In a browser, I searched for the customer-update task, edited the input without submitting that edit, and copied the first result's prompt. A native paste into the existing field retained the original submitted task and excluded the unsent draft. The source URL, revision, manifest checksum, package review, adoption permission, installation preservation, and activation limits remained present. The pasted text was never submitted as a search.

After clearing the search, a catalog result's copied prompt asks for task context only if the receiving conversation lacks it. It contains neither an invented task nor the previous search. This verifies the website handoff, not that another agent accepts or applies the skill.

The single-line search field strips line breaks during paste. The first newline-sensitive assertion was therefore unsuitable for that browser check and is retained with the private evidence. The corrected check verifies the task content after input sanitization. Unit tests separately verify the formatter's line breaks and multiline task preservation.

Type checking, nine frontend tests, and the production build passed. Backend checks passed 91 tests with two integration checks skipped. The design detector reported no findings for the changed component. The initial local server lacked a backend configuration; the verified build used the existing public gateway with a dummy local key. No private service credential was needed.

The same application revision, [d168166](https://github.com/agentforge-hq/platform/commit/d168166ddfd5b9cf62a40033fc4df2272788fdc8), was deployed to the existing MoS Vercel project. `lordoftheskill.com` and its www alias point to that ready production deployment. A fresh browser search and native copy-and-paste check on the custom domain again preserved the submitted task and excluded an unsent draft. The confirmation was visible at desktop and phone widths, with no horizontal overflow at the checked phone width. Temporary viewport settings were reset.
