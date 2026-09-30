# Typefully v2 adapter

Implementation: `contentmaxxing/connectors/typefully.py`. Publishing gates/reconciliation: `contentmaxxing/publishing.py`. Reference: https://typefully.com/docs/api (checked 2026-09-29).

Supports X/LinkedIn text, standalone X Articles and connected Substack Notes. X-only post/follower analytics and queue inspection are implemented. A key and a social-set ID are required. Account entitlements and permissions still apply. Transport is injected in tests; live certification is deferred.

No auto-retries of writes. Publish acknowledgements can be asynchronous. Updates refuse active/published or comment-anchored content rather than stripping markers. Media/QRT attachments, TikTok delivery and Substack article publishing use manual export in v1. Typefully's public API documentation describes personal/company automation scope; this is not a hosted public publishing backend.
