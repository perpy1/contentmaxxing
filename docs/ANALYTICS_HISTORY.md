# Reliable measurement history

Reports, winner selection, editorial planning, compounding and experiments use
one resolver over the original JSON observations in `data/analytics/`. Typefully,
CSV and manual entry feed the same engine.

```sh
contentmaxxing --workspace ./my-creator analytics show post_REPLACE_WITH_ID --as-of 2026-09-25T00:00:00Z
contentmaxxing --workspace ./my-creator analytics winners --as-of 2026-09-25T00:00:00Z
contentmaxxing --workspace ./my-creator report weekly --as-of 2026-09-25T00:00:00Z
contentmaxxing --workspace ./my-creator compound post_REPLACE_WITH_ID --as-of 2026-09-25T00:00:00Z
```

`show` and `winners` are read-only. `show` returns the selected job metric, its
status, the resolved view and all original observations at that latest instant.
The other commands retain their normal save/task behavior. Omit the cutoff to
use current observations. A cutoff does not reconstruct historical edits to a
content item, experiment or observation record.

## What happens when data arrives out of order

The observation timestamp controls performance order, not the time a file was
imported. Backfilling an older row preserves the newer value cached on its idea.
Future-dated observations are retained but excluded until the requested cutoff
reaches them. The idea performance cache refreshes on import; read-only analytics
derive the current view directly from original records, independent of that cache.

Import identity is content ID + origin + observed instant. `12:00Z` and
`08:00-04:00` describe the same instant. Repeating the same import leaves the
record ID, timestamps and idea data unchanged. Correcting it updates that origin's
observation while retaining its ID. Imports supply a complete snapshot; omitted
fields become unknown, not a request to keep an earlier count.

Older versions could create multiple same-origin records using equivalent
timezone spellings. A correction now updates all of those records consistently
while preserving their IDs. Until corrected, disagreements are visible. Raw
observation JSON remains inspectable, but same-origin corrections are in-place
updates, not a versioned history of every past correction. Preserve exports when
you need that audit trail.

## What happens when sources disagree

At the newest observed instant at or before the cutoff, every record must agree
on a value for that value to be used. A disagreement, including known versus
unknown, produces null and an explicit conflict. An older known value is never
substituted. No connector has automatic priority over manual or CSV observations.

Resolution happens per metric. For example, two records can agree on 1,000
impressions while disagreeing on 40 versus 4 bookmarks. Reach still has an
agreed observation; bookmark performance is unknown, so this post cannot become
a save-rate winner. The original records remain unchanged by resolution.

Built-in derived rates are recomputed inside each original observation and then
compared; the engine never combines a numerator from one origin with a denominator
from another. If 20/1,000 and 40/2,000 agree on the same save rate, that rate is
usable descriptively, while the raw count conflicts remain visible. Winner
selection still requires an agreed impression count for its exposure threshold.
Explicit custom derived fields are preserved and require the same agreement.

Use `analytics show` to inspect the observations. Correct the original CSV/manual
observation only when verified evidence supports the correction, or capture a new
complete observation at its real timestamp. Do not guess a preferred origin or
invent a timestamp to bypass a conflict. Keep unsupported qualitative metrics
unknown rather than substituting impressions for trust or authority.

Weekly reports disclose conflict counts and affected IDs. New planning tasks
include metric status, conflicts and measurement IDs. Compound tasks freeze the
resolved parent observation and peer provenance. Existing pending tasks and saved
reports retain their original evidence; deliberately cancel/replan or request a
new analysis after corrections. A new cutoff does not silently refresh a pending
task. This preserves reproducibility rather than retroactively rewriting a plan.

These are cumulative observations. Even an agreed value does not establish equal
observation ages, a representative sample, causal effects or statistical
significance. The creator's actual job remains the criterion for success.
