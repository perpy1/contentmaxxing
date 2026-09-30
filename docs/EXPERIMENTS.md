# Learn from a saved experiment

Experiments retain the hypothesis, publication dates, content IDs, metric,
recorded result, learning and next action as ordinary JSON in `data/experiments/`.
Use the existing analytics action from your preferred host, or the CLI directly.
No publishing connector or extra model service is needed.

```json
{
  "hypothesis": "A working checklist helps this audience save the process.",
  "start_date": "2026-09-01",
  "end_date": "2026-09-30",
  "content_ids": [],
  "metric": "bookmarks_per_1k"
}
```

Save that JSON with `contentmaxxing --workspace ./my-creator experiments save experiment.json`.
Add real content IDs to the array, or let an editorial plan tied to that experiment
attach its new drafts. Include the returned experiment ID in later updates. One
post can belong to one experiment; remove it from the previous experiment before
reassigning it. Removing membership clears the post's reverse pointer without
changing its prose, revision, approval or publication status.

After importing real analytics:

```sh
contentmaxxing --workspace ./my-creator experiments list
contentmaxxing --workspace ./my-creator experiments measure exp_REPLACE_WITH_ID --as-of 2026-09-30T23:59:59Z
```

The second command reads without saving anything. Omit `--as-of` for current
observations. Its result includes each post's topic, native format and job;
measurement IDs and origins; the latest value; observation age in hours; and
group sample counts and medians separated by platform, job and format.

The cutoff applies to measurements, **not** historical experiment definitions:
membership, content metadata and recorded interpretations are current. Start/end
dates are inclusive publication dates in the workspace timezone. An observation
can occur after the experiment's end date, provided it precedes the cutoff.
These bounds do not create a fixed-age or randomized comparison.

Supported metrics are normalized analytics fields (`impressions`, `views`,
`engagements`, `engagement_rate`, `likes`, `replies`, `reposts`, `shares`,
`bookmarks`, `profile_visits`, `new_followers`, `unfollows`, `net_followers`,
`link_clicks`, `leads`, `calls`) and derived fields (`profile_visits_per_1k`,
`bookmarks_per_1k`, `leads_per_1k`, `calls_per_1k`, `follows_per_1k`, `share_rate`,
`save_rate`, `profile_to_follow_conversion`, `follow_rate`, `reply_rate`). Rates
are fractions; per-1k values multiply by 1,000. Engagement rate is recomputed from
engagements/impressions, consistent with job scoring. Other metric labels remain
valid for qualitative experiments but produce `MANUAL_METRIC`, not an invented
numeric proxy. Explicit custom values stored in an observation's `derived` map
are also available; the CLI does not invent or compute those custom measures.

Missing latest values stay unknown, even when an older measurement had a value.
Zero with a positive denominator remains zero. Zero/unknown denominators are
unknown. Same-time observations from multiple origins count as one sample only
if they agree on the requested value; otherwise `CONFLICTING_OBSERVATIONS`
excludes the post for that metric. All tied measurement IDs remain inspectable.
Reports, winner selection, compounding and experiments share this resolution.
Other agreed metrics remain available. The minimum-impression gate for winner
selection additionally requires an agreed raw impression count. Use `analytics
show <content-id> --as-of <timestamp>` to see the original tied records. See
[measurement history](ANALYTICS_HISTORY.md) for import corrections and cutoffs.

The engine never declares a hypothesis proven or fills `result`, `learning`, or
`next_action` automatically. Record an interpretation deliberately, separating
the observation from its possible explanation and the next test. Different topics,
audience conditions and observation ages can explain differences between groups.
No control assignment, significance calculation or causal inference is provided.

New editorial planning tasks receive complete experiment records and measurement
group summaries under `experiment_measurements`. Per-post rows stay available
through the CLI. `editorial.experiment_chars` defaults to 16,000 characters across
these paired records; at most 20 are supplied, most recently updated first.
Oversized records are omitted whole and coverage is disclosed. Setting the budget
to zero omits this context. Pending plans keep their original snapshots after
new metrics or interpretations arrive; request a new plan deliberately.

## Correct a learning without accumulating contradictory advice

Saving an experiment updates its current entry inside a hash-marked generated
section of `data/creator/LEARNINGS.md`. Unrelated saves do not append the same
learning again. Changing or clearing the learning changes that current entry.
Manual text and old unmarked experiment notes are preserved; the current JSON
and generated section supersede historical experiment notes.

Edit the JSON through `experiments save`, keeping manual Markdown outside the
generated section. If that section was manually edited, saving fails before any
record changes. Preserve the edits outside it, then restore the generated block
from your backup, or remove the entire block (including both markers) to let the
next save regenerate it. The engine will not discard those edits automatically.

Records commit before reverse links and the Markdown view. After an interruption,
rerun a save with the existing ID to reconcile from current records; unchanged
records and prose remain untouched. A draft retry uses the saved post's current
experiment pointer, preserving a creator's later removal/reassignment. This is
recoverable file persistence, not an atomic multi-file database transaction.

An exported workspace retains the experiment records, linked posts, observations,
current notes and frozen planning tasks. The measurement view can be reproduced
after moving it by using the same cutoff and unchanged records.

## Offline demonstration

From the repository, run `python examples/experiment_demo.py --workspace /tmp/my-experiment-demo`
with a new destination. It seeds six fictional posts across two formats with
unequal observation ages and one missing metric. `experiment-demo.json` exposes
the measurements without filling in a result or learning. This is a data-flow
demonstration, not a creator quality grade or real audience experiment.
