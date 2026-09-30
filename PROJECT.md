# CONTENTMAXXING

An installable creator agent kit, delivered through skills. Creators use their
preferred AI to turn real work into a custom content engine.

**Capture → Create → Compound.** Plan with **Topic + Format + Job**.

## Scope

One Markdown orchestrator, reusable skills, inspectable creator memory and a
shared local engine. Provider adapters and optional connectors remain thin.
Typefully is optional. The current AI can execute tasks without another model
API key. Identity and voice come from the creator, never a default personality.

## Current milestone: official repository ready for creator testing

Prepare a push-ready repository and an honest testing-release launch. The user
has made this the first milestone; collecting real creator feedback is the next
step after people can install and try it, not a prerequisite for inviting tests.

- A concise README explains the product, evidence limits and Codex quick start.
- A creator can follow a first-session test and report useful feedback.
- Shared engine/skills, source-linked drafts, review, resume and portability have
  executable verification; the distributable contains the required assets.
- Contribution guidance, issue templates, changelog and usable launch copy exist.
- The Git repository has a reviewed initial commit, with creator data and secrets
  excluded, and can be cloned and tested from that commit.
- The local package and CI workflow are ready. Actual pushing/publication requires
  a destination; a public URL or successful hosted run must not be invented.

## Broader product acceptance after the testing release

- A new creator can install, choose interview or source dump, and reach a
  sourced idea bank, creator brain and reviewable first batch.
- A fresh host session resumes that work without duplicate drafts or lost edits.
- Changing a skill or model can be evaluated against the same editorial briefs,
  with mechanical checks separated from creator judgment.
- Real creator pilots validate voice and usefulness. A versioned public install
  endpoint and CI identify the exact artifacts being shipped.

## Where things live

| Foundation concept | Repository / creator workspace |
| --- | --- |
| Rules | `AGENTS.md`, shared orchestrator and selected skills |
| Current work | `STATUS.md`; creator CLI `progress` derives state from records |
| Decisions | `DECISIONS.md`; creator identity in `data/creator/` |
| Inbox | Creator `data/inbox/` and its intake manifest |
| Areas | `contentmaxxing/skills/`, schemas, engine, adapters and tests |
| Queued / active / completed work | Idea/content statuses and task/run records |
| Resources | Preserved `data/sources/`, creator documents and `.contentmaxxing/` |
| Outputs | `data/content/` and `data/reports/` |
| Archive | ARCHIVED records retain their IDs and history |

Use these existing locations. Do not mirror the same work into another set of
queued/active/completed folders. Root rules apply throughout; add local rules
only for a concrete area-specific requirement.
