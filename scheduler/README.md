# Clock-independent scheduler

`contentmaxxing init` copies the packaged defaults into the creator's `workflows.yaml`. The canonical defaults are [workflows.yaml](../contentmaxxing/config/workflows.yaml); edit the creator copy for timezone, cron cadence, ordered stages and target counts.

`contentmaxxing run <workflow>` executes the configured steps and persists `data/runs/run_<id>.json`. A pending external/model task makes a stage WAITING. Import its result and run again with `--run-id` to reuse the report and completed stages. Source shortages are recorded, not filled by invention. Article stages require an article candidate. Editorial runs never schedule or publish.

After analytics, new external/model runs request one shared editorial plan for
all requested native platforms before starting any writing. While that task is
pending, the run is WAITING and the native stages remain PLANNED. Its saved
plan/briefs belong to the same run and completion synchronizes both. Legacy runs
retain their existing choices. Explicit extractive mode uses a labeled heuristic.
See [editorial decisions](../docs/EDITORIAL_PLANNING.md).

The executor does not itself keep a clock. Map each cadence + IANA timezone to cron, GitHub Actions, a daemon, Temporal or a platform task. For example, a local cron entry can call:

```sh
/path/to/.venv/bin/contentmaxxing --workspace /absolute/creator run weekly_analytics
```

Configure the scheduler's timezone explicitly; `workflows.yaml` metadata does not alter an OS cron's timezone. A full external-agent editorial run needs a supervisor to complete tasks and resume the saved run ID. That supervisor is intentionally not implemented as a vendor-specific scheduler.

Use one writer per creator folder. Overlapping writers fail with a busy-lock error. Do not create a new run ID when attempting to resume waiting work.
