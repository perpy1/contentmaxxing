# Review

Use `review` to list drafts or `review <id>` to inspect a specific item. Read the
actual body and source references; show the creator the content, topic, format,
job, and material uncertainties. Read `feedback list --content <id>` for prior
corrections. When the creator supplies feedback, use the creator-feedback skill
to preserve it with the intended scope; a one-off edit is not a universal rule.
For agent-written changes, use content-revision and `revise <id> --direction
<creator-request>`, then execute its saved task. Use `edit <id> --file <path>` for
an exact replacement the creator supplied. Both preserve history and invalidate
approval. If next/resume supplies a revision `task_id`, complete that exact task;
do not start another draft. Only use `review <id> --approve` for
items the creator explicitly approves. Approval alone does not instruct you
to deliver or publish. If requested, use the documented connector/manual flow.
