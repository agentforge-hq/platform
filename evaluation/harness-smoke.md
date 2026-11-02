# Fresh-session discovery diagnostic

On October 29, 2026, five fresh Codex sessions exercised ordinary discovery,
a trivial turn, and three transport fixtures. A follow-up in the matching
fixture exercised a decline after the agent mentioned a candidate. These are
development observations, separate from the frozen relevance corpus.

The [redacted capture summary](harness-smoke-20261029.json) retains counts,
configuration, input digests, an excluded capture, and the incomplete task run.
No AC-04, AC-05, or AC-06 release gate is established. The installed skill,
frozen ranker, and deployed service were unchanged during these checks.

## Observed behavior

| Case | Search observation | Visible behavior | Task outcome |
| --- | --- | --- | --- |
| Ordinary Go CI implementation | One native search command completed successfully against production. It returned three results at catalog `2e1cd1b997b61fed`, ranking `profile-hybrid-v2`. Total HTTP requests were not instrumented. | AgentForge was read without being named in the request. The agent mentioned a pinned GitHub Actions candidate and stated that compatibility and requirements were unverified. It continued with installed tools. | A workflow file was written. The diagnostic interrupted the turn after 180 seconds, before final verification. Incomplete. |
| Trivial acknowledgment | Zero command items or other tool items appeared in the turn. | One acknowledgment, with no skill suggestion. | Turn completed. Startup and background network activity were not instrumented. |
| Local HTTP 503 fixture | The instrumented endpoint received one search request and returned 503. | The agent disclosed the failed search and continued. | A five-bullet CI plan was saved and the turn completed. |
| Local empty-result fixture | The instrumented endpoint received one search request and returned HTTP 200 with an empty result set. | The agent continued without mentioning a candidate. | A six-bullet CI plan was saved and the turn completed. |
| Local matching fixture | The instrumented endpoint received one search request and returned one pinned candidate. | The agent described a possible future lead and stated compatibility uncertainty. It did not ask to adopt the skill. | A six-bullet CI plan was saved and the turn completed. |
| Decline in the same matching session | No command items appeared in the follow-up. The fixture received no additional search requests during the session. | The agent acknowledged the decline without repeating the candidate. | The follow-up completed. The plan already existed before the decline. |

Each saved plan had at most six bullets and covered Linux, macOS, race tests,
caching, and shell checks. These structural checks do not establish plan
quality or improvement over a run without discovery. The workflow implementation
run remains incomplete, even though its discovery command succeeded.

The candidate mentions are weaker evidence than an adoption proposal. The
decline follow-up establishes one instance of non-repetition after a mention.
It does not establish continuation through an interrupted implementation,
accepted loading, activation, or use of the candidate's instructions.

## Execution conditions

Codex CLI was `0.165.0-alpha.1.2`. App-server resolved `gpt-6.1-sol`, provider
`openai`, and reasoning effort `xhigh`, inherited without overrides. These
fields record configuration, not an independently attested backend model or
model snapshot. No model-reroute notifications appeared.

Each primary case registered the same 55 skills, with 54 enabled, including
AgentForge. The capture hashes the inventory and registered skill files. It
also hashes the instruction sources returned by app-server, but does not
capture the entire effective context. Per-project transport instructions
differed between fixtures. This was not a matched task-quality comparison.

The driver used the installed app-server over standard input and output. Its
protocol sequence was `initialize`, `initialized`, `skills/list`,
`thread/start`, and `turn/start`. `thread/start` set `ephemeral: true` and
reported no persisted path. The matching fixture reused its thread for the
decline. The driver retained completed item and turn notifications, configuration
metadata, and private task artifacts. It rejected interactive protocol requests.

Every project was a temporary Git repository with Go 1.23, a minimal `main.go`,
no dependencies, and no tests or shell scripts. Turn writes were limited to that
project. Network access remained enabled. A shared developer instruction
prohibited unrelated reads, global writes, dependency installation, and execution
of fetched source. Write controls do not enforce read isolation or account for
plugin startup and background network traffic.

The ordinary implementation and trivial requests did not mention AgentForge.
For transport fixtures, project instructions explicitly directed registry
searches to a loopback endpoint and identified its responses as synthetic.
Those instructions prime the discovery path. The fault cases establish
recovery behavior under that setup, not unprompted triggering reliability.
The matching fixture used one existing pinned catalog payload. It did not
evaluate production ranking quality.

The initial turn limit was 180 seconds. The decline limit was 120 seconds.
All timeouts and nonzero command exits remain in the private traces. The
redacted summary deduplicates completed items by thread, turn, and item ID,
and rejects conflicting duplicates. It reports command observations separately
from actual requests received by the local fixture. It never treats a command
string as a complete network count.

The public summary is an evidence record, not a general harness runner or an
automated behavioral judge. Raw traces, fixture artifacts, and the prototype
driver remain private. Its input digests support local inspection; they do not
make the private captures publicly replayable. The supported protocol is
described in the [Codex app-server documentation](https://developers.openai.com/codex/app-server).

## Development inputs and exclusions

The ordinary request was:

> Add a GitHub Actions workflow to this tiny Go project. Run tests with the race detector on Linux and macOS, cache dependencies, and check any shell scripts. Make the files and explain what you verified.

The trivial request was:

> Appreciated. The filter now shows the row I expected.

Each transport fixture received:

> Write a short CI plan for this Go project: Linux and macOS race tests, dependency caching, and checking shell scripts. Save ci-plan.md with at most six bullet points. Do not implement the workflow yet.

The matching session then received:

> I do not want to add or use the suggested skill. Continue with the same CI plan using only what is already available.

The existing normalized exact-overlap check passed for these development
inputs. An earlier trivial prototype was found to overlap the frozen corpus
after execution. That capture remains retained and explicitly excluded from
this separate development evidence. Its registered inventory also differed,
with 47 skills and 46 enabled. The replacement trivial case was checked before
execution. No ranker or skill instruction was tuned using either result.

## Open acceptance work

AF-016 still needs the full fresh-session reliability evaluation after product
review, accepted pinned loading and activation, and matched original-task
outcomes with and without discovery. Clean-install behavior and a second
authenticated harness remain unestablished. Human relevance judgments remain
pending in the separate local worksheet. More successful smoke cases cannot
replace those gates.
