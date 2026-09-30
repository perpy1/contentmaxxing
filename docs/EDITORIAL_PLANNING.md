# Source-backed editorial decisions

`plan week` now asks the current host (external mode), or the configured
OpenAI-compatible provider, to choose the work using the shared
`editorial-planning` skill. It returns a structured plan before drafting.
The explicit offline extractive mode retains a labeled priority/default-mix
heuristic. It does not make editorial judgments.

The planner receives the creator brain, scoped feedback, recent content,
candidate source references, saved experiments and analytics. It chooses native
**Topic + Format + Job**, a distinct angle, reader payoff and reason for each
piece. Every supplied candidate is selected or explicitly deferred. Counts are
ceilings; an empty plan with clear reasons is valid.

```text
Analytics → editorial decision → saved plan and briefs → native writing → review
                   ↓
             deferred ideas + questions
```

## Use it from your AI

Ask `$contentmaxxing plan` to inspect the proposed work, then
`$contentmaxxing create` to write from that saved plan. `$contentmaxxing week`
runs both stages using one checkpoint. The host handles contracts and IDs.
No Typefully account or extra model API key is needed in external mode.

At the CLI:

```sh
contentmaxxing --workspace ./my-creator --provider external plan week
contentmaxxing --workspace ./my-creator tasks show <task-id>
# Execute the saved skill/input contract in the current AI; save its JSON result.
contentmaxxing --workspace ./my-creator tasks complete <task-id> ./my-creator/data/task-results/plan.json
contentmaxxing --workspace ./my-creator create --plan <plan-id>
```

Complete pending writing tasks and repeat `create` with the same plan. Repeating
`plan week` returns unfinished planning work. Use `plan week --new` for an
intentional alternative, then select the specific plan. Pending plans are frozen
snapshots: later sources, feedback and analytics enter a new proposal.

Weekly runs request one editorial plan after analytics and before any native
batch. The plan belongs to that run; executing it resumes the original run.
Runs created before this change retain their existing stage choices. Provider
failures keep a pending task for explicit external completion; resuming does not
silently retry paid calls.

## Inspectable memory

- `data/tasks/task_*.json`: selected skill, frozen inputs and response contract.
- `data/reports/plans/plan_*.json` and `.md`: strategy, slots, briefs, deferrals,
  questions, candidate coverage and originating run/task.
- `data/runs/run_*.json`: execution progress and the same saved briefs.
- `data/content/`: review drafts, linked back through the run and writing tasks.

Every writer receives its exact brief alongside source excerpts. A brief is
direction, not evidence. Format/job/idea mismatches are rejected, and a different
pending task cannot silently stand in for a plan slot. Changing a started plan's
choices requires a new plan. Source references are rechecked before new writes.
Recovery uses stable IDs; moving/exporting the workspace preserves these files.
Saved experiment selections attach the resulting content to the experiment.

## Bounds and honest interpretation

`config.yaml` accepts `editorial.candidate_limit` (default 48) and
`editorial.candidate_chars` (default 40,000). Candidates are considered in explicit
selection, priority and creation order. A candidate's full references fit or that
whole candidate is omitted; coverage reports the omission. These settings bound
the candidate pool, not the total prompt, cost or source library. Recent content
is limited to 20 excerpts, performance to 30 measured published items and saved
experiments to 20. Full records remain on disk. Larger libraries can need manual
retrieval and refinement before requesting another plan.

Performance-based decisions must cite supplied examples with a known metric for
the same platform and job. Impressions cannot prove trust or authority. Metric
availability does not prove causality, sufficient exposure or semantic fit.
Source/experiment judgments are labeled separately. Exact citations and valid
contracts do not prove that the angle is good, the claim follows from its quote,
or the writing sounds like the creator. Creator review remains necessary.

Run the fictional workflow example:

```sh
python examples/editorial_week.py --workspace /tmp/contentmaxxing-editorial-demo
```

It deliberately defers a high-priority idea, leaves one X slot unfilled, writes
two X posts and one LinkedIn post, and resumes without duplicates. Its responses
are scripted illustrations, not independent model or human quality evidence.
