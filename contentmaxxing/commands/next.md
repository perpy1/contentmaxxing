# Next

Read CLI `next`; it returns a read-only routing decision, not completed work.
Follow the returned `next_action.command` procedure with its exact saved IDs.
Execute one bounded stage, then show actual saved outputs and fresh `progress`.
The agent runs the skill; the CLI does not contain an internal reasoning loop.

If the action requires user input, present the specific decision or request
(profile confirmation, source material, review, delivery choice, measurements).
Reuse any decision already explicitly supplied in this conversation. Never infer
approval/publication from `next`. For multiple checkpoints, follow `resume` and
ask which to continue. Do not recursively invoke next/resume without resolving
that choice. Do not run a whole week unless requested through `week`.
