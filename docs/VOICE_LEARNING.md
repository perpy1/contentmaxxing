# Learn a creator's voice without losing their corrections

The current host executes the same Markdown voice skill as a compatible model
provider. No extra API key, connector or service is required. Ask the agent to
learn from supplied samples; it handles the commands and files below.

```sh
contentmaxxing --workspace ./my-creator --provider external voice learn
contentmaxxing --workspace ./my-creator tasks show task_REPLACE_WITH_ID
# The host reads the voice skill and returns the task's output_contract JSON.
contentmaxxing --workspace ./my-creator tasks complete task_REPLACE_WITH_ID ./voice-result.json
contentmaxxing --workspace ./my-creator voice show voice_REPLACE_WITH_ID
contentmaxxing --workspace ./my-creator voice apply voice_REPLACE_WITH_ID
```

Learning creates a proposal; applying changes VOICE.md. Initial onboarding or an
explicit request to learn/apply voice authorizes using consistent observations.
Show the creator the findings. Resolve conflicting creator directions before
applying them. An inspection-only request leaves the proposal unapplied.

## Evidence and scope

Inline `writing_samples`, `top_posts` and `articles_newsletters` in the profile
are eligible. Link-only entries are explicitly omitted: retrieve and capture the
actual text first. Reference creators, desired-tone adjectives, generated drafts
and engagement measurements do not become observed creator voice.

Captured sources require explicit creator attribution. Inspect the surrounding
source and select only their own text. Pass a JSON array using `--samples file.json`:

```json
[{"source_reference":{"source_id":"src_0123456789ab","start_line":12,"end_line":12,"quote":"Morgan: Name the owner before handing it off."},"platform":null,"medium":"speech","attribution":"creator","speaker":"Morgan"}]
```

Writing samples use `medium: "writing"` and may have `speaker: null`. Declare a
platform only when known. Profile strings have unspecified platform. Speech
observations cannot be imported as observed writing rules. A recurring pattern
needs quotations from two independent sample origins. Multiple excerpts from
one source and repeated identical text do not count as independent evidence.
One sample can support a tentative observation. No observations is also valid.

The engine checks exact supplied quotes and declared scope, not whether an
interpretation is insightful or a speaker label is truthful. The agent inspects
attribution; the creator judges fit. There is no fabricated confidence percentage.
Null platform means unknown, not universal. Requested tone and explicit scoped
feedback take precedence over inferred preferences.

`config.yaml` can set `voice.sample_chars` (default 16000), `max_samples` (24),
and `document_chars` (40000). Explicit source excerpts come first, then profile
writing, posts and articles. Samples are kept whole or listed as omitted; duplicate
text is removed. Oversized existing VOICE.md fails explicitly. These are character
budgets for these fields, not a bound on the entire task or host spending.

## Persistence and safe updates

```text
data/tasks/task_<id>.json             Frozen samples, provenance, scope and contract
data/creator/voice/voice_<id>.json     Analysis, before/after journal and status
data/creator/voice/voice_<id>.md       Readable generated proposal
data/creator/VOICE.md                 Creator guidance + applied observation section
```

The Markdown preview is generated from JSON. Creator guidance belongs in VOICE.md.
Future writing tasks read that document. Existing draft tasks retain their saved
context; voice learning does not secretly change or revise them.

Repeated `voice learn` returns the existing proposal or pending task. Use
`voice learn --new` for a deliberate fresh analysis. Finish or cancel a pending
task (`tasks cancel <id> --reason <text>`) before changing its samples. There are
no automatic paid retries. Extractive mode explicitly cannot learn voice.

Applying compares the current document, profile, active scoped feedback and source
evidence with the saved analysis. A stale proposal must be reconsidered with
`--new`. Updates replace only the recognized generated section, preserving all
other text and its newlines. If the creator edited that section, automatic
replacement stops. Preserve useful corrections as manual guidance outside its
markers; remove the old generated section deliberately and request a fresh analysis.
Do not delete creator changes to make an old proposal apply.

Application journals before writing the document. After an interruption, an intact
new observation block reconciles the journal without changing later manual text.
If that block was also edited, preserve it and reconcile manually. `voice dismiss
<id> --reason <text>` can set aside a proposal or interrupted application; it never
rolls back text already written. Applied history remains intact. Repeated apply of
an applied proposal does not replace later edits.

Voice history travels in normal workspace export. No external database or host
memory is required. Existing workspace skills remain customized local files;
installing an updated kit does not overwrite them. The engine provides a schema
fallback for older workspaces; review the updated voice procedure before adopting
it in a customized skill.

## Try the fictional example

```sh
python examples/voice_learning.py --workspace /tmp/contentmaxxing-voice-demo
```

The example learns a tentative action-first style, applies it without overwriting
a creator correction, and creates a review draft with that saved context. Responses
are scripted fixtures. This demonstrates persistence and boundaries, not a blind
editorial benchmark or real creator approval.
