# Week

Read weekly-editorial-team. Inspect `overview` and `data/runs/` for an existing
unfinished weekly-editorial run. Resume it with `run weekly-editorial --run-id <id>`;
otherwise start `run weekly-editorial`. Execute pending tasks, then resume the
same run until it finishes or genuinely requires creator input. Analytics
comes first, then one editorial-planning task chooses and explains the native
batches before writing starts. Complete the planning contract and resume the
same run; then complete each native draft contract. Article work and compound
opportunities follow. Carry the saved angle/payoff through every draft.
Show the report, actual drafts, and shortfalls. This command never auto-publishes.

When navigation supplies a specific workflow/run ID, resume that exact workflow
instead of defaulting to weekly-editorial. When several runs are unfinished,
ask which to continue. A checkpoint with a plan ID belongs to `create`; finish
that saved plan before starting a separate weekly batch unless the creator
explicitly requests a different batch. Every pending contract must be completed
before advancing its stage. Fully unattended host execution is not implemented.
