# Voice

Read the voice skill. Learn from actual creator writing or clearly attributed
speech, not reference creators, desired-tone adjectives or inaccessible links.

Run `voice learn` to use inline profile samples. For captured material, inspect
it first and supply exact creator-only excerpts through `--samples <file>` using
the skill's manifest shape. The agent handles this file and task IDs.

If navigation supplies a `task_id`, complete that saved contract. If it supplies
`proposal_ids`, review those proposals before starting another analysis. Otherwise
execute the pending voice task and import its output. Show the creator the few
useful patterns, sample evidence, uncertainty and conflicts in ordinary language.

`voice apply <id>` adds/replaces the generated observation section in VOICE.md.
Initial onboarding or an explicit request to learn/apply voice authorizes this
when there are no conflicting creator directions. Preserve manual guidance and
ask about actual conflicts; do not ask for the same authorization again. A request
only to inspect/analyze should leave a proposal for review. Deliberate subsequent
voice changes need creator direction; never infer permission from engagement.

Use `voice learn --new` for a later analysis. Finish or explicitly cancel a pending
task before changing its sample set. `voice dismiss <id> --reason <text>` records
why a proposal or interrupted application was set aside; it never rolls back
text already written. If an apply reports stale evidence or a
creator-edited observation block, preserve the document and reconcile the change
with the creator. Never delete their edits or force an old proposal through.

No samples means provisional voice, not an invented personality. Request a sample
while continuing source-backed drafting when that is the creator's intent.
