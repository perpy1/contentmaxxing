---
name: content-revision
description: Revise an existing local draft using creator direction and scoped feedback while preserving its identity and evidence.
---

# Content revision

The current draft is `inputs.revision_target`; the requested change is
`revision_direction` plus applicable `creator_feedback`. Keep the existing
Topic + Format + Job and creator voice. Fix the requested problem while retaining
useful material. A one-off correction does not become a universal voice rule.

Return the same writing output contract, with a complete revised body and an
updated claim map against the supplied excerpts. Previous prose and replacement
examples are context, not new factual evidence. Do not carry a claim merely
because the previous draft said it. Preserve speaker attribution and uncertainty.
Summarize material changes and unresolved evidence in quality_notes. If direction
conflicts or a requested claim lacks proof, surface that issue rather than inventing it.

Use `revise <content-id> --direction <creator-request>` or omit direction when
recorded creator feedback supplies it. The current AI executes a pending task
and imports it through `tasks complete`; creators do not prepare JSON. The engine
retains the content ID, journals before/after, increments the revision and
invalidates approval. `revisions <content-id>` shows the inspectable history.

If a newer edit/approval/publication makes a pending revision stale, preserve it.
Use `tasks cancel <task-id> --reason <reason>` when abandoning that obsolete
request, then start from the current draft if still editable. Cancellation only
applies to revision tasks; a committed result is reconciled, not erased.
The review command owns the creator-facing interaction. No revision publishes
or updates a remote draft. Drafts with remote copies require the connector's
existing reconciliation path instead of a local overwrite.
