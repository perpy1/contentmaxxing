# Native creator trial — 2026-09-30

Three fresh Codex CLI 0.159.1 sessions exercised the installed agent kit with a
fictional bookbinding creator. They learned from samples, mined a workshop note,
wrote platform drafts, applied a scoped correction and reopened the saved work.
The model wrote the responses during each session; they were not prewritten task
results. All sessions finished with `turn.completed` and process exit 0.

This is post-onboarding acceptance. The profile was seeded through the engine;
the interview and file-dump flows were tested separately in
[earlier Codex acceptance](CODEX_ACCEPTANCE.md). The trial does not constitute a
real creator's approval of voice or usefulness.

## Setup

- Fictional input fixtures: `tests/fixtures/voice-creator.json` and
  `tests/fixtures/voice-source.txt`.
- Persona: Leah Demo, book repair and small-run bookbinding. Three writing samples
  use sentence case, concrete physical details and occasional object-based humor.
- One manual VOICE.md preference: keep a dry joke only when it grows from the
  actual object; do not turn every repair into a life lesson.
- The workshop note includes an unverified visitor sales claim, two ordinary
  practice notebooks, visible hinge differences, repair notes and an unfilmed
  video idea. Those distinctions test attribution and missing-media handling.
- Noneditable installed wheel, external-agent provider, native project skills,
  existing Codex sign-in and default configured model. No additional model key,
  Typefully connection or publishing authorization.
- Each run used `codex exec --ephemeral --json --sandbox workspace-write` in an
  isolated fictional workspace. The outer sandbox initially prevented app-server
  startup; the approved retry retained the child session's workspace sandbox.

The prompts invoked `$contentmaxxing-voice`, `$contentmaxxing-review`, then
`$contentmaxxing-progress`. The review direction was a scripted test instruction,
not feedback from a real creator. The active pilot workspace was not modified.

## Observed results

| Check | Result |
| --- | --- |
| Voice learning | Six sample-backed observations; recurring and tentative distinguished; writing evidence not presented as observed speech |
| Manual voice | Existing editing preference preserved verbatim |
| Mining | Five cited topics; visitor's business result kept distinct from creator proof |
| First batch | One X observation, one LinkedIn repair-log post, one TikTok demonstration script |
| Missing footage | TikTok explicitly says all footage still needs filming; no finished asset claimed |
| Revision | Original X ID retained, revision 1 → 2, rejected ending removed |
| Future preference | X-only rule enters the new X draft task; item-specific correction does not |
| Preservation | LinkedIn/TikTok JSON and Markdown and all creator documents byte-identical across the review run |
| Fresh navigation | Four drafts recovered; REVIEW next; all 40 data files byte-identical |
| Review boundary | Four final records NEEDS_REVIEW; no approval, schedule, publication or remote delivery |

The first X draft ended with “A tidy cover can be quite unhelpful.” The review
prompt asked to remove that appended joke and end on the actual visible detail.
The saved revision reads:

> I photographed two notebook repairs halfway through, with the old cloth exposed. Those photos show what is harder to see in the finished covers: the different positions of the hinges.

The next X draft uses the unused practice-material topic:

> Scrap materials and ordinary notebooks first. That was my answer when a participant wanted to start on an old family book.

The LinkedIn draft gives the three fields—what moves, what catches, what I tried—
and explains what belongs in the record. The TikTok script opens the two books
side by side, shows hinge movement and ends on the note. It supplies shot and
on-screen-text instructions instead of reading the text posts into camera.
These are inspectable editorial observations, not human ratings or evidence of
audience performance.

## Failure found and fixed

The first writing run had two rejected task imports. Its LinkedIn and TikTok
responses cited real lines the host had read from the source file, but those
lines were missing from the frozen task excerpts. The citation checker correctly
rejected the imports. The host recovered by attaching the evidence with
`tasks cite`, re-reading the tasks and completing them.

The source was only 1,256 normalized characters, well within the 16,000-character
budget. Retrieval had unnecessarily clipped it; attached overlapping excerpts
could even exceed the length of the original. The engine now reserves all
mandatory evidence first, keeps referenced sources of at most 2,400 characters
whole when they fit, and coalesces overlapping ranges. The command procedure also
explains that a separate source read does not expand a frozen task snapshot.

Three regression cases cover the workshop note, overlapping context and preserving
other mandatory citations under a tight budget. The first two failed before the
fix. All 19 retrieval/feedback tests pass afterward. Both tasks created in the
second native session contain the complete 1,256-character note and pass import
without evidence repair. Older pending snapshots remain unchanged.

The host also encountered recoverable command-discovery errors before using the
saved runtime interpreter; the first run tried a nonexistent quality directory.
These traces are retained. This report does not describe the first session as a
zero-error run.

## Evidence and reproduction

Local workspace: `local-qa/voice-native`.
Local evidence: `local-qa/voice-native-evidence`.
These directories are QA artifacts outside the distributable repository.

- `create-live.events.jsonl`, `review.events.jsonl`, `resume.events.jsonl`: full
  host traces; respectively 90, 61 and 17 events.
- Corresponding `*.prompt.txt` and `*.reply.md`: supplied directions and replies.
  The generation prompt is `create.prompt.txt`.
- `create-state/`, `review-state/`: snapshots; `before-resume.json` and
  `after-resume.json`: matching file hashes.
- `review-checks.json`, `resume-checks.json`: mechanical verification results.
- `trace-summary.json`: terminal events, recoverable command errors and host
  usage counters. Token counters are cumulative host reports, not a per-call
  context measurement or a dollar-cost estimate.

Record IDs: voice `voice_2247364e2de7`; source `src_13e664028ad8`; original X
`post_f29b8b678266`; LinkedIn `post_77df1e677c6f`; TikTok `post_4684b0940fa7`;
new X `post_bfb593ad0dcc`. The revision and new draft tasks are
`task_c07ba0ac9737` and `task_5978e5662b9b`.

For a new trial, initialize a separate fictional workspace, onboard the supplied
profile, preserve a manual voice preference and provide the workshop note. Use
three fresh host sessions for voice/mining/writing, a platform-scoped revision,
and a read-only status recap. Do not reuse expected text as the model response.
Keep first failures, compare saved records and verify citations before assessing
writing. A fresh model run may choose different topics or wording.

The full suite passes 207 tests on Python 3.11. Python 3.9 passes 206 with one
expected `tomllib` skip; this compatibility run used the source checkout. A
separately installed candidate wheel passed the offline smoke outside the
checkout. Artifact paths and final verification are in `VERIFICATION.json`.

Remaining: real creator review, matched quality comparisons, repeated full
onboarding with the newer voice step, other live hosts, desktop image rendering
and public distribution. Typefully live certification remains separate and
optional. No public release or real publishing occurred.
