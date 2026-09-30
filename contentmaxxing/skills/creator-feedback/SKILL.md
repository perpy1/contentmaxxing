---
name: creator-feedback
description: Save explicit creator corrections or preferences during review and apply their chosen scope to future writing.
---

# Creator feedback

Use when the creator corrects a draft, explains why something works, or asks the
agent to remember a writing preference. The creator's words are the evidence for
their preference. Approval, analytics, your own critique and a quoted source do
not imply a durable preference.

Read the draft and `feedback list --content <id>`. Record the supplied direction
with `feedback add <id> --note <direction> --by <declared-reviewer> --category
<voice|evidence|structure|angle|cta|other> --scope <content|platform|creator>`.
Handle IDs and JSON yourself. Preserve the intended scope:

- **content** (default): this item only; do not generalize “remove this CTA” to all writing.
- **platform**: future drafts on the reviewed item's platform, when the creator says so.
- **creator**: future writing across platforms, when the creator expresses a general preference.

Use `--excerpt` for exact text in the current body and optional `--replacement`
for the creator's alternative. The engine saves revision, body hash and full
snapshot; the example remains attributable after editing. Examples are not proof
of new factual claims. The declared reviewer is not authenticated by the CLI.
Never manufacture a creator correction or label your own judgment as theirs.

Use `revise <id>` to execute a rewrite from saved feedback, or supply explicit
`--direction <request>`. The content-revision skill keeps the content ID and
journals the change. Use `edit <id> --file <file>` for an exact body replacement.
Show the updated draft; both paths require review again. Saving feedback itself does not
edit, reject, approve or publish the item. It does not rewrite Brand Brain or
VOICE.md. Use the voice/brand skills for a deliberate creator-directed document change.

New writing tasks receive active creator/platform feedback. Content-only notes
are retained for review of that item. Pending tasks keep their original snapshot;
after a correction use `tasks refresh-feedback <id>` before executing an
uncommitted pending draft. Re-read it after refreshing. Completed work stays intact.

When a creator changes a preference, retire the superseded record with
`feedback retire <id> --reason <creator-direction>` and record the new one.
If active directions conflict, ask the focused editorial question; do not silently
promote the newest into a universal rule. If the context budget is full, consolidate
with creator direction instead of deleting inconvenient feedback.
