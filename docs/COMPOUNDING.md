# Develop winners instead of recycling posts

In external or OpenAI-compatible mode, `compound <content-id>` now requests a
shared compound-skill task. It consumes the published parent, a frozen measured
comparison, creator brain and feedback, existing follow-ups and bounded source
excerpts. The current host can execute it without another API subscription.
Typefully remains optional.

The task returns an assessment and specific opportunities. Each names the new
context, proof, story, format, argument or utility it would add, along with a
native platform/format/job, exact references and any missing evidence. It can
return fewer opportunities or none. New hooks alone do not qualify. A format
change may keep the original topic: the native container and added value distinguish
the derivative, and its parent relationship stays explicit.

```text
Measured winner → source-backed analysis → follow-up idea
                                            │
                          ┌─────────────────┴────────────────┐
                          │                                  │
                    ready evidence                    missing evidence
                          │                                  │
                    plan or select                capture → cite resolution
                          │                                  │
                          └──────────────→ native draft ←────┘
                                                │
                                          creator review
```

## In the creator's AI

Use `$contentmaxxing compound <content-id>` or ask it to develop a measured
winner. The host handles task JSON and persistence. It should show the observed
performance separately from its hypothesis about why the content worked, then
separate ready opportunities from capture questions. Drafting still requires a
selection or a requested editorial workflow; analysis never publishes.

The CLI equivalent is:

```sh
contentmaxxing --workspace ./my-creator --provider external compound <content-id>
contentmaxxing --workspace ./my-creator tasks show <task-id>
# Execute that frozen compound skill/contract in the current AI.
contentmaxxing --workspace ./my-creator tasks complete <task-id> ./my-creator/data/task-results/compound.json
```

Repeat `compound` to resume or retrieve saved results. `--new` requests another
analysis using current measurements and sources while retaining past work.
`--query "backup owner handoff"` refines the related-source search for a new pass.
A pending task must be completed first. Provider failures remain available for
external completion; ordinary resume does not retry paid calls.

An uncommitted pending compound task can receive explicitly retrieved evidence:

```sh
contentmaxxing --workspace ./my-creator tasks cite <task-id> --source <source-id> --start-line 3 --end-line 5 --quote "Exact captured passage"
contentmaxxing --workspace ./my-creator tasks show <task-id>
```

The operation retains every earlier excerpt and the frozen parent, performance,
creator context and existing-follow-up snapshot. It merges overlapping ranges
and adds nearby context within the task's original combined source budget.
Duplicate attachment is idempotent. Invalid or oversized evidence leaves the
saved task unchanged; result preparation, completion or cancellation closes this
operation. Reading a file separately does not add it to the task. This does not
resolve a future idea's missing facts or certify that a quote supports a claim.

To abandon a pending analysis, use `tasks cancel <task-id> --reason "..."`.
Any already committed ideas remain. A fully committed import is reconciled;
otherwise its uncommitted remainder is cancelled. Winner watch records the
explicit skip instead of restarting it. Use `--new` to revisit that parent later.

## Resolve a missing fact

Questions live in the idea's optional `development.gaps`; readiness is derived
from whether those questions have resolutions. The existing BACKLOG/SELECTED
statuses remain intact. Drafting and weekly selection reject unresolved gaps.
`progress` exposes capture requests even while other work is available.

Capture the creator's real answer or retrieve existing evidence, then import:

```json
{
  "resolutions": [{
    "gap": 1,
    "note": "This passage supplies the event and preserves the unmeasured outcome.",
    "source_reference": [{
      "source_id": "src_REPLACE_WITH_ID",
      "start_line": 1,
      "end_line": 1,
      "quote": "Exact wording from the captured source"
    }]
  }]
}
```

```sh
contentmaxxing --workspace ./my-creator ideas resolve <idea-id> --file resolution.json
```

Every resolution is preflighted before writing. It adds evidence to the same
idea and retains the question, note and timestamp. Partial resolutions stay
blocked; repeating an identical resolution is safe. Attaching a quote with
`ideas cite` alone does not assert that the missing question was answered.
Existing resolutions are preserved. Resolving a gap is an editorial assertion;
valid quotations alone cannot prove that the assertion is correct.

## Files, limits and recovery

- `data/tasks/`: frozen evidence, contract, assessment and preallocated result IDs.
- `data/ideas/`: parent link, proposed Topic + Format + Job, new value and gaps.
- `data/reports/compound/`: readable assessments, opportunities and capture status.
- `data/creator/LEARNINGS.md`: the dated measured observation, labeled tentative.

The import validates the entire response before writing ideas, rejects duplicate
angles and unseen/fabricated quotes, and recovers stable IDs after interruption.
Recovery preserves later creator edits and resolved gaps. Export/move preserves
all of this. Older schema snapshots receive validation support for the known
optional `development` field without rewriting their files or replacing existing
field constraints. The explicit extractive mode retains its labeled three-template
heuristic for offline demonstration and legacy compatibility.

Defaults: at most six opportunities, the normal cited-source budget (16,000
characters), plus up to 8,000 characters of related lexical retrieval. Configure
`compound.max_opportunities` and `compound.related_source_chars` in `config.yaml`.
All mandatory parent/claim references fit or the task fails explicitly. These
are source budgets, not total token or cost limits. Related search is lexical;
it can miss useful evidence. Matched cumulative metrics may have unequal ages.
No automated check establishes causality, semantic novelty, voice or factual
entailment. The creator still reviews the work.

## Try and evaluate it

```sh
python examples/compound_loop.py --workspace /tmp/contentmaxxing-compound-demo
contentmaxxing evals prepare --output ./eval-runs/compound --label current-host --suite contentmaxxing/evals/compounding-v1.json
```

The demo uses disclosed fictional source answers, metrics and scripted responses.
The separate evaluation case seeds a measured winner through real lifecycle and
analytics functions, then asks the AI to develop it. Run its packet in the host,
submit the response, and have a person grade the focused rubric. Mechanical
passes remain NEEDS_HUMAN_REVIEW. The six existing editorial cases are unchanged.
