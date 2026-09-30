# The creator journey

Creators open CONTENTMAXXING inside their preferred AI, bring their actual work,
and always see where they are, what is saved, and the next useful action.

```text
Install kit → Open CONTENTMAXXING
                     |
          Interview OR file dump
                     |
           Confirm creator brain
                     |
        Capture → Mine → Idea bank
                     |
          Plan: Topic + Format + Job
                     |
        Create → Review → Approve
                     |
          Choose how to publish
                     |
           Measure → Compound
                        |
                    Idea bank
```

## What we borrow from GSD

GSD's documented journey combines guided setup, explicit workflow stages,
saved project context, and commands for progress and continuation. Its step
mode advances one unit; auto mode carries a longer workflow. See the official
[command reference](https://github.com/open-gsd/gsd-pi/blob/main/docs/user-docs/commands.md)
and [getting started](https://github.com/open-gsd/gsd-pi/blob/main/docs/user-docs/getting-started.md).

| GSD action | CONTENTMAXXING action | Creator result |
| --- | --- | --- |
| `new-project` | `start` | Interview/files → creator brain → first review batch |
| `plan-phase` | `plan` | Saved Topic + Format + Job choices |
| `execute-phase` | `create` | Drafts from that exact plan |
| `verify-work` | `review` | Editorial feedback and explicit approval |
| `ship` | `publish` | Explicit delivery or manual publication |
| `auto` | `week` | Editorial team runs to review |
| `progress` | `progress` | Current stage and next action |
| `next` | `next` | One bounded next step |
| `resume-work` | `resume` | Restore the saved checkpoint |

These are product mappings. CONTENTMAXXING uses host-native skills for reasoning
and a small local engine for persistence. It does not embed GSD's runtime or
promise that every host has the same slash-command syntax.

## First session in Codex

1. Install from the checkout using [INSTALL.md](INSTALL.md), then open the creator folder.
2. Invoke `$contentmaxxing` (or select the skill in a supporting UI).
3. See the welcome HUD and choose curated interview or mega file dump.
4. Confirm/correct the proposed creator identity; provide missing evidence.
5. The agent mines topics, selects a small first batch and produces actual drafts.
6. Review the drafts, refine the voice, and choose delivery when ready.

No separate model API key is required when Codex executes the skills.
The first-run command remains `$contentmaxxing start`; kickoff spans multiple
conversational stages and pauses for real creator decisions.

## Returning sessions

`$contentmaxxing` reads current progress. An illustrative home view:

```text
CONTENTMAXXING
CAPTURE → CREATE → COMPOUND

Stage       REVIEW
Saved       12 ideas · 3 drafts   (library totals)
Needs you   Review your drafts
Next        $contentmaxxing review
```

Those counts must come from files. Static welcome art is branding, not fabricated
live status. `$contentmaxxing next` performs the recommended bounded stage or
presents its required decision. `$contentmaxxing progress` only inspects.
`$contentmaxxing resume` restores the unfinished kickoff, plan, run, or task.
With multiple checkpoints, the creator chooses which to continue. No special
pause command is needed to preserve already saved work; unsaved chat is not
recoverable engine state.

The entrypoint accepts action arguments. Individual shortcuts such as
`$contentmaxxing-next` remain available. Claude Code/Cursor use their slash skill
entrypoints; Gemini has namespaced command files. Ordinary language routes through
the same procedures. The agent handles terminal commands, JSON, and IDs.

## A normal content week

Use `capture` throughout the week for real work. Run `plan` to inspect the proposed
topics, formats and jobs; `create` executes that saved plan. Or request `week` for
analytics, native batches, articles and compound opportunities through a single
resumable editorial workflow. Both stop at review. A thin source bank produces
a visible shortfall, never filler.

Approve individual items in `review`; use `publish` to choose Typefully delivery
or manual mode. Import real performance with `analytics`, then `compound` a
measured winner into useful follow-up opportunities. `next` recommends the
corresponding step from stored evidence. Navigation is advisory: creators may
request a different stage without clearing their existing work.

## Files behind the experience

| Saved work | Portable location |
| --- | --- |
| Creator identity/voice | `data/creator/*.md`, `profile.json` |
| Onboarding checkpoint | `data/creator/kickoff.json` |
| Captured evidence/ideas | `data/sources/`, `data/ideas/` |
| Editorial plan | `data/reports/plans/plan_*.json` and `.md` |
| Execution checkpoint | `data/runs/run_*.json` |
| Pending model work | `data/tasks/` |
| Review drafts/history | `data/content/` |
| Measurements/learnings | `data/analytics/`, reports, `LEARNINGS.md` |

Plans become immutable execution snapshots once started. Updating an in-flight
plan's choices is rejected; resume its original choices or deliberately create
a new plan. Moving the folder retains references and checkpoints. Home/progress
derive navigation from these files; there is no hidden navigation database.

Planning now has its own host task: choose from source-backed candidates, explain
selections and deferrals, and give each native writer an angle and reader payoff.
The weekly team runs this decision after analytics. A weekly plan always resumes
its originating run, including when its result was imported before drafting
started. See [editorial planning](EDITORIAL_PLANNING.md).

Terminal `home`, `progress`, `next`, and `resume` return read-only routing JSON.
The host agent executes the associated Markdown procedure. Terminal `create
--plan <id>` executes/resumes the shared scheduler, returning pending contracts
for the host to complete. It does not secretly invoke another LLM.

## Current boundaries

The kit is installable from its checkout/wheel. Fresh Codex CLI onboarding and
navigation passed [native acceptance](CODEX_ACCEPTANCE.md). Public distribution,
real editorial pilots and other hosts' discovery checks remain release work. Typefully
is typed and mock-tested; live account certification remains outstanding.
`publish` falls back to manual mode when credentials/capabilities are absent.
No navigation action infers approval, and `week` never automatically publishes.
