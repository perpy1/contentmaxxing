# Continue the work without starting over

Creators can ask their AI to mine a long conversation or improve an existing
draft. The shared engine retains source coverage, task IDs, revision history and
review status across sessions and workspace moves. No connector or second model
key is required when the current AI executes external tasks.

## Long conversations

```sh
contentmaxxing --workspace ./my-creator --provider external mine call.txt
contentmaxxing --workspace ./my-creator mining <source-id>
```

The agent completes the returned task and calls `mine <source-id>` again. Large
sources use bounded, overlapping text windows with original line numbers and
mid-line boundary flags. Small sources retain the single-task contract. Windows
cover all normalized source characters; they do not silently drop the middle or
stop after a fixed number of topics. A model may legitimately find zero useful
ideas in a window.

`data/mining/mine_*.json` freezes the source hash, window boundaries, creator
context and selected instructions. Task IDs are allocated before execution;
crash/resume reuses the same IDs. Completed chunk results are imported through
the same idea persistence/deduplication rules. The raw source remains intact.

Default configuration:

```yaml
mining:
  chunk_chars: 16000
  overlap_chars: 800
  chunks_per_call: 3
  idea_context_chars: 12000
```

Overlap must be between zero and half the chunk size. Keep enough overlap for
speaker/context continuity. Extremely long turns may split inside a line: the
writer must not invent a speaker or missing context. Quotes must occur in the
supplied window at the cited original lines, even if a proposed quote occurs
elsewhere in the same source.

Internal providers process at most `chunks_per_call` windows per invocation,
then return IN_PROGRESS. External mode returns one saved pending task at a time.
Neither means the source is complete. `mining` and the home/progress view expose
coverage and remaining work; kickoff waits for the entire pass before topic
selection. The engine bounds source text and calls per invocation, **not the
host's total tokens, dollars or turns**. Creator context and instructions also
occupy space.

New tasks also receive `existing_ideas`: earlier topic IDs, titles, categories
and up to 600 characters of saved notes (with truncation explicitly marked),
within a separate character budget. Same-source topics come first, followed by
lexical matches. `existing_idea_context` reports eligible and omitted counts;
zero budget disables this shortlist. Archived ideas, compound derivatives and
ideas already snapshotted by a pending draft are excluded. This is a retrieval
aid, not a claim that no other relevant idea exists.

When the current passage supports the same actual topic, return its supplied
`existing_idea_id`, copy the supplied `topic` exactly, and provide the new quote
and lines in the normal extraction contract. Import appends that reference to
the same idea while preserving status, format, job, priority and notes. The full
response, including any proposed new interpretation, is retained in the completed
task's `extraction_output`; it does not overwrite editorial metadata. A genuinely
different argument or useful angle can remain a separate idea.

Only IDs included in that frozen task are eligible for this operation. A later
rename, change to the supplied notes/category, archive or new pending draft can invalidate an unapplied match. Imports
validate every candidate before writes; recovery recognizes an already attached
reference without undoing subsequent edits. Existing task packets and historical
pass contracts remain unchanged. Each newly created window snapshots the library
then available, so a stateless compatible provider can reuse earlier topics too.
Titles and notes are not proof: every added quotation must still be in the supplied source
window. A host with file/tools can use `ideas cite` for a separately reviewed
match outside the shortlist.

A failed call stays pending. `mine <source-id> --retry` explicitly retries that
chunk with its saved provider; it does not discard completed work. Completing a
pending task manually remains possible. A completed long-source pass is reused
by default. `--restart` starts a new pass only once the prior pass is complete,
using current skills/context and retaining old records. Small-source calls keep
their previous behavior: a fresh request can create another deduplicated pass.
Existing pending whole-source tasks are preserved instead of orphaned.

Coverage means every window was processed. It does not prove the model found
every idea, inferred every cross-window connection, or avoided every semantic
duplicate. The mining skill reviews those editorial questions; the offline
extractive provider remains a literal retrieval fixture, not a semantic miner.

## Revising a draft

```sh
contentmaxxing --workspace ./my-creator --provider external revise <content-id> \
  --direction "Keep the story, remove the generic lesson, and end on the working detail."
contentmaxxing --workspace ./my-creator revisions <content-id>
```

The pending task includes the current draft, applicable creator/platform/item
feedback, bounded source evidence and the original Topic + Format + Job. The
current AI supplies the complete revised body, updated claims and quality notes
through `tasks complete`. Omit direction only when explicit saved feedback
already provides it. Extractive mode cannot make editorial revisions.

The result keeps its **content ID**, increments its revision and returns to
NEEDS_REVIEW with approval cleared. `data/revisions/rev_*.json` journals full
before/after snapshots. Exact body replacements through `edit --file` now use
the same history. Saving a feedback note alone still changes neither the body
nor its approval.

Revision tasks are separate from new-batch tasks. They cannot be mistaken for a
new platform post by the weekly scheduler. A creator's later idea selection does
not silently change the existing draft's platform, format, job or experiment.

If the current draft changed after a revision task was prepared, import fails
without overwriting the newer edit, approval or publication. To discard an
obsolete request, use:

```sh
contentmaxxing --workspace ./my-creator tasks cancel <task-id> --reason "The creator replaced the opening while this was pending."
```

Then revise the current draft if still editable. Cancellation preserves the
abandoned task/candidate for inspection. If its content write actually committed
before a crash, recovery records that fact and preserves subsequent creator
work instead of pretending the revision was cancelled. Repeat completion does
not create another post or apply a prepared revision twice.

Only local NEEDS_REVIEW/APPROVED drafts without remote copies support this path.
Remote or published work uses the existing connector reconciliation/new-version
flow. Revisions do not approve or publish anything.

New optional schemas use packaged fallbacks in older workspaces. A missing new
revision skill also uses the packaged version; existing customized files are
retained. Sources, mining checkpoints, pending revisions, feedback and history
all travel in a workspace export.

## Try the fictional end-to-end example

```sh
python examples/feedback_loop.py --workspace /tmp/contentmaxxing-continuity-demo
```

It processes a 42,702-character work log in three windows, imports two curated
topics, creates a draft, records simulated feedback, revises the same post, and
carries the preference into another draft. Inspect `feedback-demo.json`,
`DEMO.md`, `data/mining/`, `data/tasks/` and `data/revisions/`.

Responses and reviewer direction are scripted fictional fixtures. This verifies
workflow mechanics; it is not a live-model or real-creator quality trial.
