# Publish

Inspect the chosen content, approval, and remote state. Resolve which items and
whether the creator wants a remote draft, a schedule, immediate publication,
or manual export. The command name alone is insufficient to choose ambiguous
items, account, or timing. Reuse explicit delivery instructions already given.

Manual publishing is a complete supported path. If no connector is configured,
present the copy-ready draft and let the creator publish in their platform.
Offer Typefully only as an optional convenience when relevant; never require
an account, credentials, or connector setup to use the creator engine.

For Typefully, use `connect deliver <id> --action draft|schedule|publish` with
`--at <offset-timestamp|next-free-slot>` for scheduling. Scheduling/publication
requires approved content. If remote action is pending/uncertain/requested,
use `connect reconcile <id>` first; never blindly resend it. A remote draft or
asynchronous acknowledgement is not a published post.

Without credentials or supported attachments/platform, show the saved Markdown
for manual use. Preserve local approval/status. Only record publication using
`status <id> PUBLISHED --url <verified-url> --published-at <timestamp>` after the
creator supplies the actual URL/time or the connector confirms it. Exporting
does not mean published. End with the real delivery state and recommend importing
measurements when available. `next`, `week`, and a review approval never authorize
publishing by themselves.
