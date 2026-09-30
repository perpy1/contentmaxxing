# Find the evidence. Remember the correction.

Creators can ask their current AI: “Find my story about handoff ownership,” or
“On X, stop ending my posts with generic agreement questions.” The idea-bank
and creator-feedback skills handle retrieval and persistence through the shared
engine. There is no new provider, connector, model key or vector database.

## Search the creator's real work

```sh
contentmaxxing --workspace ./my-creator sources search "backup owner"
contentmaxxing --workspace ./my-creator sources search "handoff" --kind "work log" --limit 4 --max-chars 6000
contentmaxxing --workspace ./my-creator sources read <source-id> --start-line 14 --end-line 20
contentmaxxing --workspace ./my-creator ideas cite <idea-id> --source <source-id> --start-line 17 --end-line 17 --quote "An exact source quote."
```

Search scans captured source files locally. It ranks lexical matches using term
rarity and query coverage, returns exact excerpts with original line numbers,
and preserves consent metadata. Passage IDs include source identity, hash and
character offsets; moving a workspace preserves them. No search writes an index
or creator state. Changed originals are reported as errors rather than silently
re-indexed: capture a new revision.

A matching passage is a candidate, not proof. Inspect speaker and surrounding
qualifiers. Try the creator's own phrasing and related terms when recall is low;
lexical search does not understand synonyms. Search is a linear local scan;
very large libraries may eventually warrant a disposable derived index.

Attach another source's exact evidence to an idea before drafting. Duplicate
citations are idempotent. An existing pending draft keeps its original idea
snapshot; use `tasks cite <task-id>` with the same source/line/quote arguments to
add evidence to that task explicitly. Re-read the updated task before writing.
Extra citations carry into the resulting content record; the idea stays unchanged.
Pending compound analyses also support `tasks cite`, retaining prior excerpts and
their original performance baseline; see [compounding](COMPOUNDING.md).

## Bounded drafting context

New draft tasks use `inputs.source_context.version = 2`. `inputs.sources` maps
source IDs to arrays of excerpts, each with `quote`, original `start_line` /
`end_line`, offsets and metadata. Never number excerpt lines from one when citing.
Existing tasks containing complete source strings remain importable.

The engine reserves **all cited spans** first. Referenced short sources (at most
2,400 characters) stay whole when they fit alongside every other mandatory span.
It then adds nearby context and ranked passages from those same sources within
the remaining budget. Overlapping ranges are merged and counted once. Other
sources enter only after citation attachment. Existing task snapshots stay
unchanged. Defaults in `config.yaml`:

```yaml
retrieval:
  draft_source_chars: 16000
  draft_source_passages: 12
feedback:
  max_context_chars: 8000
```

These are character budgets for source excerpts and serialized feedback, **not
a total model token/cost limit**. Creator documents, idea records, parent posts
and task instructions have separate sizes. Large transcripts now use resumable
bounded mining windows; see [mining and revisions](MINING_AND_REVISIONS.md).
Source files stay complete on disk.

If mandatory citations exceed the budget, drafting stops before creating a
task. Narrow overly broad citations deliberately or raise the budget. There is
no quiet evidence truncation. Output claims must cite a real quote that was
supplied at the cited lines; the engine rejects unseen quotes even if they exist
elsewhere in the source. Exact citations still cannot prove entailment or good
editorial judgment. Every generated item remains NEEDS_REVIEW.

## Preserve explicit creator feedback

```sh
contentmaxxing --workspace ./my-creator feedback add <content-id> \
  --note "On X, end on the useful detail instead of asking whether people agree." \
  --by "Creator" --scope platform --category cta --excerpt "Agree?" --replacement ""
contentmaxxing --workspace ./my-creator feedback list --content <content-id>
contentmaxxing --workspace ./my-creator feedback retire <feedback-id> --reason "Creator changed this preference."
contentmaxxing --workspace ./my-creator tasks refresh-feedback <pending-task-id>
```

Use **content** for one item (the default), **platform** for future writing on
that item's platform, or **creator** for future writing across platforms. Infer
scope only when the creator's direction is clear; do not turn a local correction
into a universal rule. Records preserve the exact original body, revision, hash,
declared author and optional before/after example. The declared author is not
authenticated by the local CLI. Agents must never invent creator feedback.

Feedback is stored in `data/feedback/fb_*.json`. New tasks include applicable
active creator/platform records. Content-only feedback is retrieved during
review of its original item; it does not alter unrelated drafts. Feedback never
edits or approves content, rewrites identity, or serves as factual evidence.
Apply requested body changes with `edit`; they invalidate previous approval.

Pending tasks retain their original feedback snapshot until explicitly refreshed.
Completed tasks and committed import checkpoints cannot be refreshed. Retiring a
rule preserves its history; it affects new/refreshed tasks, not completed work.
Conflicting active rules stay visible for creator resolution. If active feedback
exceeds its budget, the engine asks for consolidation/scope changes or a larger
budget instead of forgetting older preferences.

Older workspaces can use this capability without replacing custom skills or
creator files. Missing new feedback schemas use the packaged fallback; existing
custom schemas remain authoritative. To update agent instructions, deliberately
copy the relevant new skill/command instructions into the workspace snapshot.
ZIP export includes feedback and pending tasks alongside the source originals.

## Reproduce the local illustration

```sh
python examples/feedback_loop.py --workspace /tmp/contentmaxxing-feedback-new
```

This uses a fictional creator, a long work log, scripted external-task responses
and simulated creator feedback. Inspect `DEMO.md`, `feedback-demo.json`,
`data/feedback/` and the second task's `creator_feedback` field. It demonstrates
context selection and persistence; it is not a live-model or human-quality trial.
