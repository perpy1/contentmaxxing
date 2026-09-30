---
name: kickoff
description: Start or resume a creator’s content engine through a guided conversation, real source mining, and a first reviewable batch. Use when they say kick off my content engine, get me started, or set up Contentmaxxing.
---

# Kick off a creator's content engine

Own the launch from conversation to useful drafts. The user should finish with a creator brain, learned or explicitly provisional voice, a sourced idea bank, a small first batch, and a manageable first-week rhythm. Use the shared engine and specialized skills. Don't make the creator operate task IDs, JSON files or terminal commands; handle that work in the agent environment.

## Choose a starting path

For a new creator, show the CONTENTMAXXING welcome HUD from the installed
`WELCOME.md` or workspace `assets/welcome.png`. Resolve that asset relative to
the intelligence bundle, not the current working directory. If the host cannot
render images, use `contentmaxxing welcome` as a text HUD. Offer:

1. **Curated interview:** a few tailored questions to refine their creator profile.
2. **Mega file dump:** organize existing source files, derive a cited profile
   proposal, confirm it with the creator, then mine and draft.

If the creator says the image is invisible, use the text HUD immediately and
continue onboarding. Do not retry broken image links or regenerate the logo.
Typefully and other connectors are optional. Do not ask for API keys during
kickoff; build the brain, idea bank and reviewable content using the current AI.

Run `start` to inspect progress. A blank setup returns WELCOME; record their
choice with `start --mode interview` or `start --mode files`. If their request
already chooses a path, honor it directly. Returning creators resume their saved
phase. They can combine paths or switch without discarding answers or sources.
For an interview, read [references/interview.md](references/interview.md).
For a source drop, read [references/file-dump.md](references/file-dump.md).

## Start with what is already known

Use the creator's current workspace if one exists. From the source repository, use `./my-creator` unless the user chose another location. `contentmaxxing start` selects that safe default when called inside the repository. In an initialized workspace it resumes instead of restarting. Use the installed CLI, or the repository's `.venv/bin/python -m contentmaxxing` with its working directory set to the repository. Keep `--workspace` explicit for subsequent commands.

If the CLI is not installed in a source checkout, set up a local `.venv` and install the repository with `python -m pip install -e .` before continuing. Handle that setup yourself within the environment's permissions. This workflow requires file access and command execution to persist the engine; do not claim files were saved in a chat environment that lacks those capabilities.

Run `contentmaxxing --workspace <folder> --provider external start` when you are executing the skills in the current agent environment. This creates/resumes a portable launch record and returns the next phase. Respect an explicitly selected internal model provider instead if the user wants that execution mode. The CLI is not itself a conversational model; you are the conversational interface. Never report a pending task as completed work.

Read existing creator documents and the conversation before asking anything. Ask at most three short questions at once, only for missing information. A useful opening is:

> Let’s turn the work you’re already doing into a content engine. What do you do, who do you want to reach, and what would you like content to do for you?

Follow with the initial platform and a realistic weekly pace when unknown. Capture the offer if there is one; “not selling anything” is valid. Use the onboarding skill for field definitions. Convert supplied answers to a **partial** profile JSON file under the creator workspace (for example `data/creator/intake-answers.json`) and save them with `start --answers <file>`. This file is agent bookkeeping, not a questionnaire to hand to the user. `posting_cadence` in this launch flow means target posts **per week**. Don't guess identity, proof or voice. Unknown optional profile fields can remain empty and be learned over time.

## Find the first real source

At SOURCE, ask for one useful piece of real work: a call, project note, customer question, process, mistake, win or an older piece of writing. Ask for a few writing samples and exclusions/restrictions alongside it when available. Record these answers before onboarding completes. Users do not need an existing content library.

If they have no files, interview them about a recent concrete event: what happened, what they did, why, what changed and what they learned. Preserve their exact answers as a labeled conversation transcript in the workspace. Do not write a polished invented story and call it a source. The creator's own responses can supply initial voice evidence; distinguish their words from your questions or summaries.

Save supplied text and call `start --source <path>` (repeat the option for multiple files). Sources supplied before the profile is complete are copied into the workspace inbox so a move or interruption does not lose them. Add late optional answers with `--answers` in the same call. The engine then creates BRAND_BRAIN.md, VOICE.md, CONTENT_PILLARS.md and OFFER.md, and captures the originals.

Use the voice skill and `voice learn` to turn actual samples into cited observations
before requesting the first draft tasks, so their snapshots include the learning.
Supply explicitly attributed captured excerpts if needed. Complete the analysis
task, show the useful findings and apply the initial proposal when consistent with
creator direction; onboarding authorizes this learning. Preserve manual guidance
and resolve genuine conflicts. Without enough evidence, retain a provisional voice
and ask for feedback on the first drafts. Never impose lowercase, slang or another
creator's identity. Keep existing creator-edited documents intact; deliberate
identity/voice changes use their corresponding skills.

## Carry the work through the engine

The `start` response names the current phase. Use its `agent_guide`, `pending_tasks` and candidate records as internal routing information.

- **CONTEXT / SOURCE:** continue the brief interview, persist answers/material, and call `start` again. Stop only for genuinely missing creator input.
- **WELCOME / FILE_DROP:** show the two choices or invite files according to the saved mode. Do not require an interview before accepting a source drop.
- **SOURCE_REVIEW / PROFILE_REVIEW:** follow the file-dump reference. Read the accepted files, save a cited profile proposal, and obtain creator confirmation/corrections before promoting file-derived identity.
- **MINING:** read each pending task, its selected transcript-mining skill and its output contract. Extract distinct topics, not finished posts. Write the result JSON yourself, import with `tasks complete <id> <file>`, then call `start` again. A model failure also leaves a task you can execute in this environment.
- **CHOOSE_TOPICS:** use editorial-planning to choose up to the target number (default 3) of strong source-backed ideas. For each, use `ideas select <id> --platform <platform> --format <native-format> --job <behavior>`. Preserve Topic + Format + Job. Start with one platform; select fewer pieces if the evidence warrants it. Call `start --idea <id> --idea <id> ...` with your selections. Do not ask for permission for routine editorial selection unless the creator requested that control.
- **DRAFTING:** execute pending native writing contracts, applying the voice document and cited sources. Import results and call `start` again. Don't fall back to literal extraction while presenting it as native writing.
- **REVIEW:** open the actual content records and show the drafts to the creator with concise topic/job context. Ask what sounds unlike them and which facts need correction. Show `data/creator/LAUNCH_PLAN.md`, explain the first-week pace and identify the next useful material to capture.

For direct agent work, use `tasks show <id>` and `tasks complete <id> <result.json>` without delegating these steps to the creator. Save result payloads under `data/task-results/`; `data/tasks/` contains engine-owned task records, not result payloads. Each `start` call checkpoints progress; repeated calls reuse pending/completed tasks and the first batch. After draft corrections, use the shared edit/review operations. This launch does not auto-approve, schedule or publish.

## Make the handoff useful

The first-week plan should name the starting audience, goal, platform, actual drafts, weekly target and next capture habit. New creator launch counts replace the high-volume defaults with explicitly supplied weekly counts, or a clearly proposed small first-week batch. Existing creators retain their workflow configuration.

Show the user the work, not an implementation report. Explain that performance learning starts after real publishing/measurement; never fabricate a baseline. Continue with the relevant skill when they request edits, approval, delivery or another batch. A returning creator can say “continue my content engine setup” and resume from saved files in any compatible agent environment.
