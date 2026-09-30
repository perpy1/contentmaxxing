# Native weekly creator trial — 2026-09-30

A fresh Codex CLI 0.159.1 session executed the installed kit's weekly engine with
fictional bookbinding material. It learned from writing samples, mined 11 new
topics, analyzed four synthetic published posts, saved one plan, wrote four native
drafts and developed three follow-up ideas. Every new draft remained NEEDS_REVIEW.
The run finished with process exit 0 and `turn.completed`.

## What the test exercised

The seed supplies four historical X posts with the same Bookmarks / Saves job.
One has 40 saves from 1,000 impressions; its three peers each have four saves per
1,000 impressions. One peer has 10,000 impressions. This makes the save-rate
winner different from the highest-reach post. All metrics and publication records
are simulated, using `example.invalid` URLs. No connector is involved.

The new workshop source gives a practical record-keeping process, an unverified
visitor claim, explicitly missing footage and a proposed experiment with no
results. Profile cadence gives X 2, LinkedIn 1, TikTok 1 and Substack 1. Workflow
format defaults additionally expose article/Note slots; the planner elected to
leave those extra slots unused rather than expand the creator's stated cadence.

| Saved output | Topic / container / job |
| --- | --- |
| X | Replacing “improved” with visible movement / short post / Conversation |
| X | A copyable blank record / checklist / Bookmarks / Saves |
| LinkedIn | Read the previous note beside the actual book / LinkedIn post / Trust |
| Substack | Set up a record for one ordinary practice notebook / Substack article / Bookmarks / Saves |

The guide is 522 words within the configured 450–650 range and uses one LOGAN
framework. It gives a template, observations, actual-action fields, photo labels
and a return-visit step. The structure does not import another creator's voice.
TikTok stays unfilled because the host requested footage first; this run therefore
does not validate a newly generated TikTok script, X article or Substack Note.

Twelve of the 15 supplied candidates were explicitly deferred. The selected guide
idea supplies both a short X template and a longer Substack walkthrough with
different reader payoffs. The planner identifies the four-post sample and unequal
measurement ages as tentative, and does not use impressions to establish Trust.

The winner follow-ups add a visual matching exercise, a worked record across two
dated observations, and a future comparison of template versus finished-cover
content. All retain specific unresolved evidence gaps instead of inventing the
footage, completed records or experiment results. They remain ideas requiring
capture before drafting.

## Mechanical verification and observed failures

`scripts/check_weekly_trial.py` checks the original run/plan relationship, saved
writer briefs, platform ceilings, source citations, review status, article
framework, measured winner and exact duplicate bodies. It repeats the completed
run and plan and requires every creator-data file to remain byte-identical. This
check passed. It does not grade meaning, source entailment or usefulness.

The trace has 103 events and three failed commands before recovery: the executable
was absent from PATH, the host guessed a nonexistent workflow directory, and it
tried `tasks cite` on a compound task. At that time evidence attachment only
supported drafts. The host completed the compound output from the excerpts it
actually had; the failed operation is not erased from the evidence.

The engine now allows explicit citation attachment to an uncommitted compound
analysis. It preserves all earlier excerpts, parent, creator context, existing
follow-up snapshot and metric comparison. It adds the requested evidence and
bounded surrounding context, merges overlaps, and uses the original source
budget. Invalid or oversized evidence does not change the task. Prepared,
completed and cancelled tasks reject attachment. Four regressions cover those
properties and portability; three failed before the fix, and all 26 compounding
tests pass afterward. The original native run was not silently rerun with this
fix; installed-CLI verification is recorded in `VERIFICATION.json`.

## Writing-guidance comparison

Agent inspection found a narrower editorial problem: routine instructions ended
with an unmeasured-results disclaimer even though they made no result claim.
The shared quality guidance now puts evidence-audit/production notes in
`quality_notes`, keeping a qualification in the body when it changes the claim or
how a reader should use it. Material scope, attribution and uncertainty still apply.

Two fresh Codex sessions ran the same two fictional briefs with old and revised
guidance. Suite and grader hashes matched; instruction hashes differed. Each
case allowed one attempt. Both versions passed all mechanical checks, and all
four outputs remain NEEDS_HUMAN_REVIEW with no submitted human grades.

In the practice-record case, the baseline body included “I haven't measured time
saved or repair success.” The candidate put that information in review notes
while retaining the ordinary-notebook and treatment boundaries in the body.
Both versions of the experiment update explicitly said the posts were unpublished
and no results existed. This small observation supports keeping the narrow
guidance; it does not establish a general quality gain or a calibrated score.

The cases live in `contentmaxxing/evals/reader-scope-v1.json`. See
[editorial evaluations](EVALUATIONS.md) for matched runs and human review. These
native writing comparisons used the engine before the compound-citation fix;
their frozen reports remain historical evidence. New matched trials should use
the same current engine on both sides.

## Reproduce and inspect

With an installed engine, create a fresh fictional workspace:

```sh
python examples/weekly_trial_seed.py --workspace /tmp/contentmaxxing-week-trial
```

Open that folder in the intended host and ask `$contentmaxxing-week` to learn the
voice, mine the new workshop notes and complete the week up to local review and
winner follow-ups. The seed supplies historical fixtures only; it does not supply
the new mining response, plan, prose or compound response. Preserve the host trace.
After the host exits:

```sh
python scripts/check_weekly_trial.py --workspace /tmp/contentmaxxing-week-trial --events /path/to/host.events.jsonl
```

Local evidence (outside the distributable repository):

- `local-qa/weekly-native-evidence`: prompt,
  reply, JSONL trace, before/after hashes, completed-state snapshot and checks.
- `local-qa/reader-scope-evidence`: two prompts,
  traces, reports and comparison; frozen trial folders are adjacent.
- Weekly run `run_151ca5a1591f`, plan `plan_b18944efc245`, report
  `report_a418577f6b03`, compound task `task_bd0b02cc143d`.

Host token counts in those artifacts are cumulative, not per-call context size
or dollar cost. No real editorial pilot, publishing, public release or other-host
acceptance occurred. The active creator pilot was untouched. Typefully remains
optional.
