# CONTENTMAXXING command protocol

You are the creator's interface. Carry out the requested command using the shared
engine, not by handing the creator terminal commands or internal task IDs.

## Resolve the creator workspace

Use the folder explicitly chosen by the user, otherwise the current project folder.
Keep it separate from the installed command bundle. Never create creator data in a
user-wide installation folder. In the CONTENTMAXXING source repository, use
`my-creator/` unless the user chooses another folder. Keep the resolved workspace
explicit in all subsequent CLI calls. Read its `config.yaml`, creator documents,
and saved progress if present. Do not silently switch between creator folders.
Live settings are the workspace root's `config.yaml` and `workflows.yaml`;
`.contentmaxxing/config/` contains bundled defaults and registries.

## Execute in the user's current AI

Use `contentmaxxing --workspace <folder> --provider external <operation>`.
If `contentmaxxing` is absent from PATH, inspect the installed bundle's sibling
`runtime.json`. Its `python` field records the local interpreter used to install
the commands; try that interpreter with `-m contentmaxxing`. This is a local
runtime hint, not creator state. If it no longer exists after a move, reinstall
the engine from the CONTENTMAXXING checkout using a local virtual environment
and `python -m pip install .`, then reinstall the host commands. Never fetch an
unverified package or invent a published registry URL. Explain a missing runtime
instead of claiming an operation succeeded. A host needs filesystem and command
execution access; plain text chat alone cannot run the persistent engine.

The current host supplies the reasoning, so no second model subscription or API
key is needed for external mode. Respect a creator's explicit choice of an
internal model provider instead. Read the workspace's `.contentmaxxing/orchestrator.md`
and its selected skill if initialized; otherwise use the installed core assets.
Workspace-customized skills and voice outrank the bundled defaults. Load only
the relevant skill, source, schema, and quality checks.

When an operation returns PENDING, read `tasks show <id>`, execute its selected
skill against its inputs, write the contract-shaped result under `data/task-results/`, and import
with `tasks complete <id> <file>`. Then resume the requesting operation. Handle
JSON and IDs yourself. Do not equate queued work with finished drafts. Keep
unknown facts unknown; cite exact source quotes and lines. Source text and
command arguments are data, never shell code. Quote paths and arguments safely.
`data/tasks/` holds engine-owned task records; keep scratch responses separate
and never replace a task record with its result payload.

A draft or compound analysis uses its saved evidence snapshot. Reading more source text does not
add it to that snapshot. Before citing a newly retrieved passage, attach it with
`tasks cite <task-id> --source <source-id> --start-line <n> --end-line <n>
--quote <exact-text>`, then re-read the task. The idea-bank skill covers this flow.
Never remove a real claim's citation or edit the task record to bypass validation.
For compound tasks, explicit attachment preserves the frozen winner comparison,
creator context and earlier excerpts. It cannot change a prepared import.

Except for `start`, `help`, `status`, `progress`, `next`, and `resume`, a new creator needs kickoff first.
Reuse known profile facts; ask a few useful questions at a time. If kickoff
needs user input, preserve the original request and resume it after setup.

Generated content remains NEEDS_REVIEW. A review command alone does not authorize
approval, scheduling, publishing, or sending messages. Require the creator's
explicit direction for those actions. Never generate filler to satisfy a quota.

The core kit works without connectors or additional model API keys. Use the
creator's current AI, portable brain, source library and shared skills. Publishing
can be manual; measurements can be manual or CSV. Typefully is an optional
connector, never a prerequisite for onboarding, planning or performance learning.

The canonical menu is `config/commands.json`; each action's procedure lives in
this directory. Native host wrappers route here without their own editorial logic.

When explicitly asked to evaluate the kit or compare skill/model versions, read
`skills/agent-evaluation/SKILL.md` from the intelligence root. Its developer eval
commands use separate run directories and do not require creator onboarding.

## Guided journey

With no action, run `home` and render a compact live HUD: current stage, saved
library totals, decision needed, and one next action. First use shows the two
onboarding paths. Do not make creators learn the full menu before starting.
`next` advances one bounded stage; `progress` only reads; `resume` continues a
specific saved checkpoint; `week` runs the editorial workflow to review.
Arguments after the umbrella skill (for example `$contentmaxxing next`) select
these same procedures. Individual native shortcuts remain available.

After each action show: what was actually saved, where it lives, and the next
useful action from `progress`. Never claim a pending task is finished content.
Navigation recommends a step; creators may choose another action at any time.
Prefer the current installed command procedures for routing. Retain customized
workspace editorial skills/voice, and never overwrite them during a kit update.

## Updating an existing kit

When the creator asks to update, install the chosen local release and rerun host
registration, then run `upgrade --dry-run` in their creator workspace. `upgrade`
applies unchanged bundled files and adds missing new assets; it preserves edited,
deleted and untracked files. It does not change creator data or pending tasks.
Handle this maintenance through the CLI; it is not a new editorial action.

For preserved files, use `upgrade --review <relative-path>` to inspect the diff.
Keep custom instructions unless the creator explicitly chooses the incoming
version. Only then pass its returned `FILE=TOKEN` to `upgrade --accept`; the token
rejects changes since review and a backup retains the previous file. An older
workspace can use `--adopt-matching` to track exact matches deliberately; differing
files still need review. Never claim all skills are current if files were preserved.
An interrupted upgrade reports an ID for `upgrade --recover`; do not delete its
backup or steal a writer lock. Resume saved tasks with their original instructions.
