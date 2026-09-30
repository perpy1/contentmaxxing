# Mine

Read transcript-mining. Resolve the supplied source or path from the user's
request and saved library; ask only if ambiguous. Run `mine <source-id-or-file>`
and complete its pending contract. For a long source, repeat `mine <source-id>`
after importing each window until `mining <source-id>` reports COMPLETED.
On IN_PROGRESS, resume the saved pass; do not report the source finished.
Extract every distinct useful topic with
evidence; do not stop at finished posts or create artificial duplicates.
Show the strongest topics, their source links, and useful article candidates.

If next/resume supplies a `task_id`, complete that exact saved task instead of
starting mining again. If it supplies `source_ids`, mine one source as the next
bounded step; additional sources remain available for subsequent actions.
`source_window` provides original line numbers and boundary context. Never cite
unseen text. A failed model call remains pending; `mine --retry` explicitly
retries it using its saved provider. `--restart` starts a new long-source pass
only after the old one completes, keeping prior ideas and history.
