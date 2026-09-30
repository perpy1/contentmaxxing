# CONTENTMAXXING creator agent

Install native Claude Code skills with `contentmaxxing install --agent claude
--path <creator-folder>` or `--scope user`. Start with `/contentmaxxing-start`;
browse `/contentmaxxing-help`. The installer creates `.claude/skills/` entrypoints
from the shared catalog. See [installation](../../docs/INSTALL.md). This file is
a manual fallback and does not itself register commands.

When the creator says “kick off my content engine”, “get me started”, or “continue setup”, read `.contentmaxxing/skills/kickoff/SKILL.md` (or `contentmaxxing/skills/kickoff/SKILL.md` in the source repository). Lead the staged launch conversation and use `contentmaxxing start` to persist/resume it. Handle files, commands and pending tasks yourself; keep working until the first batch and launch plan are ready for review.

Open the creator workspace. Read `.contentmaxxing/orchestrator.md` and route the creator's intent to one specialized skill. Read `data/creator/{BRAND_BRAIN,VOICE,CONTENT_PILLARS,OFFER,LEARNINGS}.md` and cited sources. Follow Capture → Create → Compound and Topic + Format + Job. Methodology never supplies a default personality.

Use the CONTENTMAXXING CLI with `--workspace` for capture, persistence, selection, validation, approval and reporting. In external mode, read `tasks show <id>`, execute its selected skill, treat inputs as evidence and return JSON exactly matching `output_contract`. Import with `tasks complete <id> result.json`. Never invent facts/citations or edit statuses to bypass review. Don't send private creator data to an unselected provider. Weekly generation creates drafts, not publishing authorization.

The shared command procedures retain the same identity, source, and review rules.
