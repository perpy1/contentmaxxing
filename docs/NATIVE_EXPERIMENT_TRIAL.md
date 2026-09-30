# Native experiment learning trial — 2026-09-30

One fresh Codex CLI session used the installed `contentmaxxing-analytics` command
to review a saved fictional experiment and record its result, learning and next
action. This tests the creator journey beyond a scripted transport response.
It is not a real creator pilot or an independent human editorial grade.

## Setup

`examples/experiment_demo.py` seeded fictional creator Morgan and six literal
source-excerpt X posts. Simulated publication URLs use example.com. The experiment
asks whether checklists earn more bookmarks per 1,000 impressions than short posts.
All interpretations initially were null; the prompt contained no expected answer.

The three short posts have values 8, 10 and 12 at 96 hours after publication. Two
checklists have values 15 and 21 at 24 hours; the third has unknown bookmarks.
All observations have 1,000 impressions. Topics and publication dates also differ.

The user-style prompt asked whether checklists were working better as of
2026-09-25T00:00:00Z, what to do next, and to save that interpretation to the existing
experiment. It allowed no new drafts, publication or changed observations.

The session used Codex CLI 0.159.1 with existing sign-in/default model configuration,
an ephemeral session, approval policy `never` and a child `workspace-write` sandbox.
The outer launch needed the same approved app-server initialization escape used
in earlier QA. No Typefully account or internal model API key was involved.

## Observed behavior

The host loaded the native wrapper, shared command procedure and analytics skill.
It inspected original records and called `experiments measure` with the requested
cutoff. It also produced a weekly report and inspected winner nominations. A PATH
lookup failed once; the installed runtime manifest provided the working Python
invocation. The original failed command remains in the trace.

The final reply reported checklist median 18 (two of three measured) versus short
post median 10 (three measured), with ages 24 versus 96 hours. It described the 80%
observed difference as descriptive, excluded the missing value, and distinguished
saves from actual process reuse. Its proposed next test used topic-matched pairs,
balanced posting slots and a common 96-hour measurement point. It treated that
small follow-up as exploratory. This is assistant inspection of this one answer,
not a numerical quality score or evidence that all experiment interpretations are
reliable.

The host saved all three interpretation fields through `experiments save`. Only
the existing experiment JSON and LEARNINGS.md changed among pre-existing data
files; the weekly report was new. Creator identity, source files, content,
publication status, metric observations and membership were preserved. Repeating
the save changed no data. The original cutoff reproduces the same calculated
measurements after the interpretation is saved.

## Evidence and reproduction

Local workspace: `local-qa/experiment-native`.
Experiment: `exp_ab6ccf464969`.

Evidence: `local-qa/experiment-native-evidence/`:

- `review.prompt.txt`, `review.events.jsonl`, `review.stderr.log`, `review.reply.md`.
- `before.json` records original data hashes; `checks.json` records structural checks.
- The 34-event trace ends with `turn.completed`; one recoverable command failed.
- Cumulative usage: 318,229 input tokens, 286,720 cached input, 4,074 output,
  1,117 reasoning output. These are across calls, not context-window size or cost.

The seed script and `scripts/check_experiment_trial.py` are in the source package.
The checker requires a completed trace, preserves initial failures, compares
original data hashes and measurement provenance, rejects new content/observations,
and verifies repeat-save idempotence. It does not grade the explanation:
`human_grades: 0`, `editorial_status: NEEDS_HUMAN_REVIEW`.

The trial ran the candidate wheel in `dist/experiment-candidate/`. The final
increment manifest compares its runtime payload with `dist/experiment-increment/`.
Later changes only documented the evidence and strengthened the local checker;
the runtime used by the native session was not silently replaced during that run.

Related verification: 248 Python 3.11 tests; 247 Python 3.9 passes and one expected
skip; both modified skills validate; the installed offline workflow covers
experiment measurements, idempotence and export/restore. Fixed-age causal
analysis, real creator grading and public release remain outstanding.
