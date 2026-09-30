# Analytics

Read analytics. Import a supplied CSV with `analytics import <file>`, or record
explicit manual observations with `analytics manual <id> --file <file>`. When
the creator asks for a Typefully sync, use `analytics sync typefully` and report
missing credentials/capabilities honestly. Run `report weekly` and inspect
`analytics winners`. Explain behavior by Topic + Format + Job, measured
baselines, missing metrics, and uncertainty. Never manufacture performance.

Inspect missing/conflicting values with `analytics show <content-id> --as-of
<timestamp>`; it includes original records and provenance. When the creator names
a cutoff, pass it to `analytics winners --as-of` and `report weekly --as-of` too.
Correct observations only from verified evidence; do not silently prefer a
connector or turn a partial manual observation into a merged snapshot.

For an experiment question, inspect `experiments list` and use
`experiments measure <id>` (or `--as-of <timestamp>`) for measured values and
provenance. Explain what is observed, what remains an interpretation, and what
to test next. Record a requested interpretation with `experiments save <file>`;
do not label a cumulative group median as a causal experiment result.
