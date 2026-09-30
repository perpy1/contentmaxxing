# Resume

Run read-only CLI `resume` and restore context from the workspace, not chat memory.
An unfinished kickoff resumes through `start`. A checkpoint with `plan_id` uses
`create --plan <id>`; one with `run_id` uses `run <workflow> --run-id <id>`.
Complete its pending tasks before resuming that same checkpoint. If several
checkpoints exist, show their saved plans/stages and ask which to continue;
an explicitly named plan/run resolves the choice. Never start a replacement batch.

For a standalone `task_id`, inspect and complete that exact task through its
selected skill and command procedure; do not call generation again afterward.
Saved voice proposals resume through the voice command for review/application.
If no work is
interrupted, explain the current stage and show the next decision/action using
`progress`. Closing a host session needs no special pause command: persisted
tasks, plans and runs survive. Text generated only in chat must be saved before
claiming it is recoverable. Do not claim to restore unsaved host conversation.
