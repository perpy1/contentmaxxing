# Engine reference

For the quick start, see the [README](../README.md). This guide covers the full engine and CLI.

One CONTENTMAXXING entrypoint, delivered through reusable skills, with your own
creator brain and content history saved in portable files.

Your AI becomes your content mastermind: it learns your positioning and voice,
finds useful material in your work, plans what to create, and learns from real
results. **Typefully is optional.** The core kit needs no publishing account or
additional model API key when your current AI executes its skills. Publish
manually and import CSV/manual metrics, or add a connector when you want it.

Capture → Create → Compound.

Find the good shit. Make something useful. If people care, keep going.

## One entrypoint, a guided journey

Open `$contentmaxxing` in Codex to see the welcome choices or your current stage,
saved work, and one next action. The main navigation is:

| Action | What happens |
| --- | --- |
| `start` | Interview or file dump → creator brain → first batch |
| `next` | Advance one useful step, stopping for your decisions |
| `progress` | Inspect what is saved and what comes next |
| `resume` | Continue the exact saved kickoff, plan, or batch |

Use action arguments such as `$contentmaxxing next`, or individual shortcuts such
as `$contentmaxxing-next`. Other hosts use their native invocation below.

```text
Capture → Idea bank → Plan → Create → Review → Publish → Measure → Compound
              ^                                                     |
              +-----------------------------------------------------+
```

`plan` saves Topic + Format + Job; `create` executes that exact plan. `week` runs
the broader editorial workflow through review. Publishing remains an explicit
creator choice. Focused tools remain available through `help`; newcomers do not
need to learn the full menu. [Creator journey and GSD mapping](JOURNEY.md).

## Kick off your content engine

![CONTENTMAXXING welcome HUD](../contentmaxxing/assets/welcome.png)

The first welcome gives creators two ways in:

1. **Curated interview:** a few tailored questions to refine their profile,
   audience, offer, voice, proof, boundaries, and starting direction.
2. **Mega file dump:** bring a folder or multiple files; the agent inventories
   the material, reads it in batches, proposes a cited creator profile, and asks
   for corrections and missing context before drafting.

Both paths can be combined and resumed. Existing launches keep their progress.

Install CONTENTMAXXING's skills into Codex, Claude Code, Cursor, or Gemini CLI.
Open your creator folder and run its start command:

| Environment | Start your engine | Browse abilities |
| --- | --- | --- |
| Codex CLI / IDE | `$contentmaxxing-start` | `$contentmaxxing-help` |
| Claude Code | `/contentmaxxing-start` | `/contentmaxxing-help` |
| Cursor | `/contentmaxxing-start` | `/contentmaxxing-help` |
| Gemini CLI | `/contentmaxxing:start` | `/contentmaxxing:help` |

These are native AI skills/commands. Your current AI supplies the reasoning;
external mode needs no additional model API key. The shared CLI handles files,
validation, and progress underneath. [Installation guide](INSTALL.md).

You can also say:

> Kick off my content engine. Walk me through it, ask a few questions at a time, and turn my real work into my first batch of content.

[START_HERE.md](../START_HERE.md) remains a portable fallback for filesystem-capable agents. The agent learns who you help, the outcome you want, and your starting platform; gathers a real piece of work and voice samples; then mines topics and creates a small first batch for your review. If you have no files, it interviews you about a recent project, decision or customer question and preserves your exact answers as source material.

The agent handles setup, files and task results. You provide your context, your work and editorial feedback. You leave with **Brand Brain + Voice + Pillars + Offer + Idea Bank + First Drafts + Launch Plan**. The first batch defaults to 3 pieces, with fewer when the evidence is thin. New kickoff workflows use your explicitly supplied weekly pace, or propose a small initial pace; they do not inherit the 21-post weekly target automatically. Existing creator documents and workflow settings are retained.

Setup resumes from `data/creator/kickoff.json`, including after moving the folder. Say “continue my content engine setup” to pick up where you left off. The plan lives in `data/creator/LAUNCH_PLAN.md`. Drafts remain `NEEDS_REVIEW`; kickoff does not publish.

File intake accepts UTF-8 TXT, Markdown, CSV, JSON/JSONL, SRT and VTT. It preserves
the originals in the workspace inbox and records an inventory with duplicate
and exception reporting. PDF, DOCX, images, audio and video need text extraction
or transcription through the host's tools or a supplied export. Unsupported
originals stay in their original locations; the engine does not silently claim
to have read them. Hidden/generated directories and symlinks are skipped;
individual text files over 50 MiB must be split.

Agent-side examples (creators can simply choose in chat):

```sh
contentmaxxing welcome
contentmaxxing --workspace ./my-creator start --mode interview
contentmaxxing --workspace ./my-creator start --mode files --source ./source-library
```

The install command shows a terminal HUD when run interactively; scripted output
stays JSON with welcome image/document paths. The start skill displays the image
when the host supports local images, and otherwise uses the text HUD. A host's
own home screen is controlled by that host. The CONTENTMAXXING welcome appears
inside its installation/onboarding flow. `--json` forces structured welcome and
installation output.

For agents/developers, `contentmaxxing start` is the executable entrypoint. It initializes a workspace if necessary and returns the next phase. In this repository it defaults to `my-creator/`, keeping creator data apart from the source files. `--answers` accepts partial profile facts, `--source` accepts real text material, `--idea` records the agent's editorial selection, and repeating `start` reuses pending/completed tasks. The [kickoff skill](../contentmaxxing/skills/kickoff/SKILL.md) tells the host agent how to carry those phases through to actual drafts. The CLI itself is not an interactive language model.

Creators repeatedly start from zero even when their work, calls, projects, replies and mistakes contain useful material. CONTENTMAXXING preserves that evidence, turns it into a searchable idea bank, creates content in the creator's voice, measures what people actually did, and returns stronger angles to the bank.

```text
Real work / calls / ideas / proof
             |
          CAPTURE ----> Sources + cited topics
             |                  |
             +------------> Idea bank <-------------------------+
                                |                               |
                        TOPIC + FORMAT + JOB                    |
                                |                               |
                             CREATE                             |
                                |                               |
                         NEEDS_REVIEW                           |
                                |                               |
                     APPROVE → SCHEDULE → PUBLISH                |
                                |                               |
                         Measure behavior                       |
                                |                               |
                          COMPOUND WINNERS ---------------------+
```

The enemy is `post → forget → start from zero tomorrow`. This is an engine, not a dashboard or a quota-driven content generator. Gabe's methodology is shared; Gabe's voice is never a default. The included creator, Morgan Demo, is fictional.

## How the agent works

One Markdown orchestrator routes to 19 specialized skills. Skills, schemas, framework templates and creator documents are first-class files that another AI agent can read and execute. A shared Python engine handles persistence, source checks, review gates, analytics and recurring runs. Model servers and publishing services sit behind thin adapters; they do not own the editorial logic.

One command catalog generates the native host entrypoints. The commands are
`start`, `next`, `progress`, `resume`, `voice`, `capture`, `mine`, `ideas`, `plan`, `create`,
`draft`, `article`, `week`, `review`, `publish`, `analytics`, `compound`, `status`,
and `help`. Each routes to a shared Markdown
procedure and the relevant skills. Installed assets are separate from creator
data; moving a creator folder preserves the engine's memory and identity.

Every idea separates **Topic** (what it says), **Format** (how it is expressed), and **Job** (what behavior it should create). Jobs include reach, saves, shares, conversation, profile visits, follows, trust, proof, authority, inbound and calls. Formats live in an editable registry. Articles choose one of HADES, BUZZ, LOGAN, JUAN, EP, FREDERICK or SERIES / TECHNICAL OPERATOR; structure never replaces creator voice.

Three execution modes share the same task/result validation:

| Mode | What actually happens |
| --- | --- |
| `external` (default) | Saves a self-contained task for Codex, Claude Code, Cursor, Gemini or any other agent. Import its JSON result with the CLI. No model key required. |
| `openai-compatible` | Sends the same selected skill, creator context and output contract to a configurable Chat Completions endpoint. Model JSON is checked locally. |
| `extractive` | Offline literal sentence retrieval and source-excerpt drafts for X, LinkedIn and Notes. It is deliberately **not** semantic mining or native AI writing. Video and articles require an external agent or model. |

Generated content always begins `NEEDS_REVIEW`. Editing a local draft invalidates approval. The weekly workflow never publishes. Source quote validation catches invented citations; a human still checks voice, factual interpretation, restrictions and consent. The engine does not claim it can prove every generated sentence true.

## Install and run locally

Python 3.9+ is supported; Python 3.11+ is recommended for a fresh environment.

```sh
cd contentmaxxing
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
contentmaxxing --help
# Choose your AI; install into the folder you will open in it:
contentmaxxing install --agent claude --path ../my-content
contentmaxxing doctor --agent claude --path ../my-content
```

Replace `claude` with `codex`, `cursor`, or `gemini`. Open `../my-content` in
that AI, reload skills/restart if needed, and invoke the start command above.
For installation across your local projects, use `--scope user` instead of
`--path`. `--dry-run` previews writes. Installing commands does not onboard you
or change existing creator documents. Ask your agent to perform these setup
steps if you prefer staying in conversation.

This release installs from the checkout; no public PyPI/npm package or marketplace
listing is claimed. Host files are generated and tested against documented
formats. Fresh Codex CLI onboarding has been exercised with fictional creators;
other hosts still need native acceptance tests. See [validation limits](INSTALL.md#verification-and-release-scope).

You can also run `python3 -m contentmaxxing` from the repository when the two runtime dependencies (`jsonschema`, `PyYAML`) are available. There is no cloud service, database daemon or JavaScript runtime to start. The installed CLI works outside the repository; its intelligence resources ship inside the Python package. Native commands carry a machine-local interpreter fallback for sessions without the virtual environment on PATH.

For scripted/manual onboarding, create a separate creator folder:

```sh
contentmaxxing --workspace ./my-creator init --timezone America/New_York
contentmaxxing --workspace ./my-creator onboard --template ./creator.json
# Fill in creator.json. Empty lists are explicit unknowns, not invented facts.
contentmaxxing --workspace ./my-creator onboard --profile ./creator.json
```

`onboard` without options runs an interactive questionnaire; list/object answers use JSON. It collects identity, niche, audience/ICP, offers/goals, expertise/history, proof/stories/opinions, desired and excluded topics, platforms/cadence, tone/samples/top posts/articles, references, CTAs and restrictions. It creates:

```text
data/creator/profile.json
data/creator/BRAND_BRAIN.md
data/creator/VOICE.md
data/creator/CONTENT_PILLARS.md
data/creator/OFFER.md
data/creator/LEARNINGS.md
```

The voice document starts with actual samples and provisional direction. Ask your
agent to **“learn my voice from these samples”** (Codex: `$contentmaxxing-voice`).
The shared voice skill saves cited observations and a reviewable proposal.
Applying it preserves manual guidance and rejects stale evidence or edited
generated sections. Speech, writing and known platform scope remain distinct;
one sample cannot establish a recurring pattern. No samples means provisional
voice, not a default personality. See [voice learning](VOICE_LEARNING.md).

Onboarding does not overwrite an existing creator. Daily drafts read these files
but do not rewrite positioning. Markdown creator documents are authoritative for
editorial context; edit `profile.json` deliberately when changing structured settings.

## Add source material and mine topics

```sh
contentmaxxing --workspace ./my-creator capture ./transcript.txt --consent "creator-cleared; clients anonymized"
contentmaxxing --workspace ./my-creator mine src_REPLACE_WITH_ID
# Or capture and mine together:
contentmaxxing --workspace ./my-creator mine ./transcript.txt
```

Capture preserves UTF-8 text/Markdown, an integrity digest and source metadata. Byte-identical files deduplicate. Mining produces topics, not just finished posts: stories, beliefs, disagreements, tactical processes, objections, customer language, case studies, tutorial/article candidates and visual opportunities. Every candidate cites an exact quote and line range. There is no top-N cap. For very long conversations, the external transcript skill instructs the agent to work in line-range chunks and merge distinct topics.

External mode returns `PENDING` and a task file. Execute it from your preferred agent:

```sh
contentmaxxing --workspace ./my-creator tasks list
contentmaxxing --workspace ./my-creator tasks show task_REPLACE_WITH_ID
# Ask your agent to follow instructions, use inputs as evidence,
# and write a JSON object matching output_contract into result.json.
contentmaxxing --workspace ./my-creator tasks complete task_REPLACE_WITH_ID ./result.json
contentmaxxing --workspace ./my-creator ideas list --status BACKLOG
```

A task includes the selected skill, quality rules, creator context, supplied sources and a JSON output contract. Results from external agents and model servers take the same path. Invalid citations/JSON remain pending and do not become drafts. Exact normalized topics and near-identical topics on the same evidence span merge references conservatively; deeper semantic deduplication belongs to the mining skill. Original speaker attribution remains visible. Binary media, OCR and transcription are deferred; supply a textual description or transcript for now.

## Select, draft and review

```sh
contentmaxxing --workspace ./my-creator ideas select idea_REPLACE_WITH_ID \
  --platform x --format "short post" --job "Conversation"
contentmaxxing --workspace ./my-creator draft x --idea idea_REPLACE_WITH_ID
# Complete the pending agent task if using external mode.
contentmaxxing --workspace ./my-creator review
contentmaxxing --workspace ./my-creator review post_REPLACE_WITH_ID
contentmaxxing --workspace ./my-creator review post_REPLACE_WITH_ID --approve
```

`draft linkedin`, `draft tiktok`, `draft substack_note`, `draft substack`, and `article --platform x_article` use native platform skills. Each requires `--idea`; `--format` and `--job` are configurable for drafts. X does not inherit LinkedIn polish or automatic lowercase. TikTok outputs scripts and shot requirements, not a tweet to read into a camera. Articles use operator prose, scoped proof and practical sections; the default target is 700–1,000 words, configurable in `config.yaml`.

Review notes identify missing evidence, voice or assets; approval is the creator's assertion that these have been checked. Modify unscheduled local content using `edit <id> --file draft.md`; it resets approval. JSON content is authoritative; the `.md` sidecar is regenerated for reading. Ideas track the latest related draft state; **content records retain separate per-platform lifecycle states**.

For manual publishing, export, publish yourself, and record the real result:

```sh
contentmaxxing --workspace ./my-creator status post_REPLACE_WITH_ID PUBLISHED \
  --url "https://example.com/your-actual-post" --published-at "2026-09-29T10:00:00-04:00"
```

This command requires prior approval. `SCHEDULED` requires `--at` with an offset timestamp; it records a manual scheduling decision and does not call a publisher. Approval can return to review. Published content is not overwritten; capture/draft another version. The v1 CLI enforces review even if someone edits the informational `review_first` config field. A fully autonomous approval policy is intentionally deferred.

## Generate a week

```sh
contentmaxxing --workspace ./my-creator plan week
contentmaxxing --workspace ./my-creator create --plan <plan-id>
contentmaxxing --workspace ./my-creator run weekly-editorial
```

In external mode, planning first saves an editorial task for the current AI.
Import its response to save inspectable JSON/Markdown under `data/reports/plans/`.
Each choice includes an angle, reader payoff, evidence and reason; unselected
candidates get explicit deferrals. Writers receive those exact briefs. Repeating
`plan week` resumes unfinished planning; `--new` requests an intentional alternative.
The explicit extractive mode keeps a labeled priority/default-mix heuristic.
See [editorial planning](EDITORIAL_PLANNING.md) for context bounds and recovery.

`workflows.yaml` configures counts, timezone, cadence and ordered stages. Default targets are 21 X posts (3/day with reach, saves and operator/personal intent), 3 LinkedIn posts, 3 TikToks, 1 X Article, 1 Substack article and 3 Notes. They are ceilings: a thin bank yields a documented shortfall. Exact posting dates/times are editorial decisions, not automatically scheduled batch outputs. You can adjust counts to the creator's cadence before running.

```text
Analytics Lab → Editorial plan → X batch → LinkedIn → TikTok → Article Lab
            → Substack article + Notes → Winner Compound Watch
```

A run produces a report first, requests one shared editorial decision across the
configured platforms, then creates native draft tasks. Its plan remains attached
to that run. External-agent tasks stop downstream stages until results are
imported. Resume the same run:

```sh
contentmaxxing --workspace ./my-creator tasks complete task_REPLACE_WITH_ID result.json
contentmaxxing --workspace ./my-creator run weekly-editorial --run-id run_REPLACE_WITH_ID
```

The saved report is reused on resume, completed stages do not regenerate, and existing platform drafts are not blindly recycled. Provider failures also leave tasks available for external completion. All output is reviewable. `run weekly_x_batch` or another YAML workflow runs a smaller sequence. `workflows list` prints validated definitions. [Scheduler details](../scheduler/README.md) explain clock mapping; v1 provides an executor, not an always-running daemon.

## Import analytics and compound winners

CSV requires `content_id` and a timezone-aware `observed_at`. Optional measurements include impressions, views, engagements, engagement_rate (fraction), likes, replies, reposts, shares, bookmarks, profile_visits, new_followers, unfollows, net_followers, link_clicks, leads and calls. Aliases: `comments`, `saves`, `profile_clicks`, `follows`. Blank cells are unknown, not zero. Counts must be finite; timestamps must follow publication. Unknown columns are rejected. The entire CSV is checked before import. Reimporting the same content/observation/origin updates the snapshot.

```csv
content_id,observed_at,impressions,bookmarks,profile_visits,new_followers
post_REPLACE_WITH_ID,2026-09-29T18:00:00Z,1000,20,50,
```

```sh
contentmaxxing --workspace ./my-creator analytics import ./analytics.csv
contentmaxxing --workspace ./my-creator analytics manual post_REPLACE_WITH_ID --file metrics.json
contentmaxxing --workspace ./my-creator report weekly
contentmaxxing --workspace ./my-creator analytics winners
contentmaxxing --workspace ./my-creator analytics show post_REPLACE_WITH_ID --as-of 2026-09-29T23:59:59Z
contentmaxxing --workspace ./my-creator compound post_REPLACE_WITH_ID
```

Rates include visits/follows/bookmarks per 1k impressions, shares/saves/replies/follow rate, profile-to-follow conversion and manual leads/calls per 1k. Zero or unknown denominators produce null. Reports group by Topic + Format + Job **within platform and job**, show sample sizes, timezone-aware posting windows and tentative findings. Per-account follower growth is separate from post-attributed follows.

A winner must beat a same-platform/job peer median by the configured multiplier (default 1.5×), with at least 3 peers and 100 known impressions. The tested post is excluded from its own baseline. A zero baseline does not justify infinite lift. Bookmarks are scored on saves, not reach; Trust/Proof/Authority have no fabricated impressions proxy. Add creator-specific job metric mappings in `.contentmaxxing/config/formats.json` when you have measured evidence. Cumulative snapshots may have unequal ages, so findings are tentative; fixed-window causal experiment analysis is deferred.

Older imports do not replace newer performance. Conflicting observations at the
same instant produce unknown values, with original record IDs available through
`analytics show`. Reports, experiments, planning and compounding share this rule.
Use `--as-of` consistently on `analytics winners`, `report weekly` and a new
`compound` analysis. [Measurement history and corrections](ANALYTICS_HISTORY.md).

`compound` now asks the current AI to develop the winner using original and
related source evidence. It saves distinct native follow-ups with a clear added
value and any capture questions. Unresolved evidence gaps block drafting until
cited material resolves them. Repeat the command to resume; use `--new` for an
intentional further pass. The explicit extractive mode retains labeled template
prompts. See [compounding and capture gaps](COMPOUNDING.md), including a
fictional end-to-end demo and a separate quality evaluation case.

Compounding creates new idea opportunities with a parent ID, required evidence and addition type: utility, argument or format in the v1 deterministic nomination engine. The skill can explore more context/proof/story and platform moves. It does not pretend missing proof exists. Derivative drafting rejects near-identical parent prose; human review checks that the derivative actually adds value. Measured learnings persist in `LEARNINGS.md`.

Experiments are portable JSON records with hypothesis, dates, content IDs, metric, result, learning and next_action:

```sh
contentmaxxing --workspace ./my-creator experiments save experiment.json
contentmaxxing --workspace ./my-creator experiments list
contentmaxxing --workspace ./my-creator experiments measure exp_REPLACE_WITH_ID --as-of 2026-09-29T23:59:59Z
# Include an existing experiment ID to update its result/learning.
```

Experiment measurements are read-only: known metrics, sample counts, original
measurement IDs, missing/conflicting values and observation ages. Group medians
stay separate by platform, job and format; they do not establish causation.
New editorial plans receive bounded measurement summaries alongside recorded
interpretations. Repeated saves do not repeat learnings; changing membership
reconciles post links. See [experiment learning](EXPERIMENTS.md) for dates,
metric names, correction/recovery and portability.

## Connect Typefully

The adapter follows [Typefully's public API v2](https://typefully.com/docs/api). It implements accounts, drafts, updates, scheduling, immediate publish requests, X post analytics, follower totals and queue inspection. The documented shapes are covered by mocked transport tests; **no live account validation is claimed**.

```sh
export TYPEFULLY_API_KEY="your-key"
contentmaxxing --workspace ./my-creator connect accounts
# Set typefully_social_set_id in my-creator/config.yaml to the chosen integer ID.
contentmaxxing --workspace ./my-creator connect deliver post_REPLACE_WITH_ID
# After review/approval, choose an explicit scheduling or publishing action:
contentmaxxing --workspace ./my-creator connect deliver post_REPLACE_WITH_ID \
  --action schedule --at "2026-10-01T10:00:00-04:00"
contentmaxxing --workspace ./my-creator connect reconcile post_REPLACE_WITH_ID
contentmaxxing --workspace ./my-creator analytics sync typefully --start 2026-09-22 --end 2026-09-29
```

| Capability | v1 behavior |
| --- | --- |
| X / LinkedIn | Text drafts and explicit schedule/publish operations |
| X Articles | Standalone Markdown article payload; account/platform entitlement still applies |
| Substack Notes | Supported only when connected on the social set |
| X analytics | Imports documented engagement metrics; unmatched remote posts are retained in raw data |
| Follower analytics | Saves account daily totals; never invents per-post follows |
| TikTok / Substack articles | Manual/export delivery |
| Media uploads / QRT attachments | Deferred; these formats require manual export in v1 |

Missing keys/capabilities produce actionable errors and leave the rest of the engine usable. `--action publish` requires explicit approval. Typefully may acknowledge `publish_at=now` asynchronously; local content stays un-published until reconciliation finds a published URL. Uncertain mutation outcomes are never automatically retried. After a creation timeout, verify the draft in Typefully and `connect reconcile <id> --remote-id <verified-id>`; do not send it again. Comment-anchored drafts must be edited in Typefully without stripping markers. Remote changes cannot inherit an earlier local approval.

Raw connector responses stay under `data/analytics/raw/`. The adapter only attributes metrics to existing content via remote draft IDs scoped to the social set or published URLs. Importing arbitrary historical posts and automatic source capture from an account are deferred. Typefully documents its API for personal/company automations; this repository is a local creator workspace, not a hosted multi-tenant publishing backend.

## Use models and other agent environments

Set `provider: openai-compatible`, a server `base_url` ending at its API root, and `model` in the workspace `config.yaml`. Set the key using the environment variable named by `api_key_env` (default `CONTENTMAXXING_API_KEY`). HTTPS is required except for localhost. The adapter uses `/chat/completions` and plain JSON completion parsing, without assuming a vendor-specific structured-output extension. Invalid, truncated or filtered output leaves a recoverable task. A creator explicitly choosing a hosted provider is choosing to send the task's source/creator context to that provider.

For agent-native use, install your host's entrypoints and open the **creator workspace**.
The host reads the orchestrator and relevant skills, executes saved task contracts,
and imports results using the shared engine. Nothing depends on a prior vendor
conversation. The [installer](../contentmaxxing/installation.py) generates the wrappers
from one catalog; no per-host content logic or extra model SDK is involved.
Other filesystem-capable agents can use `--agent generic` and read the resulting
`CONTENTMAXXING.md`. Plain browser chat needs a filesystem/execution integration
to operate this persistent engine; a model name alone is not a host integration.

## Extend skills, formats and platforms

Add `contentmaxxing/skills/<name>/SKILL.md` with YAML `name`/`description`, input sources, evidence constraints, useful procedure and task output. Add an intent route to the orchestrator. Use shared schemas and quality checks; do not duplicate the creator brain or provider logic. After updating the engine, run `contentmaxxing --workspace <creator-folder> upgrade --dry-run`, then `upgrade` to bring new skills and unchanged bundled files into an existing workspace. Customized and untracked files are preserved for review. See [workspace upgrades](WORKSPACE_UPGRADES.md).

To expose a creator command, add its entry to `config/commands.json` and its
procedure to `commands/<name>.md`. Reinstall host entrypoints. Do not hand-maintain
copies of the same procedure in each AI's command format.

To add a format, extend the platform list in `config/formats.json` (or the workspace snapshot) and describe its selection conditions in the writing skill. To add a platform, add its registry entry and skill, the small platform→skill route in `Engine.draft`, CLI choices, scheduler step/default-job route if needed, and a connector capability if a real publishing API is available. Preserve one shared engine and task contract. Add tests for native routing and capability failures; do not add copied orchestration for a provider.

## Data and portability

```text
contentmaxxing/                 Repository
├── README.md / AGENTS.md / LICENSE / IMPLEMENTATION_PLAN.md
├── contentmaxxing/
│   ├── orchestrator.md / skills/ (19) / schemas/ (12)
│   ├── templates/ / prompts/ / config/ / commands/
│   ├── installation.py / workspace_assets.py / kickoff.py / overview.py / voice.py
│   ├── engine.py / store.py / analytics.py / providers.py
│   ├── connectors/ / publishing.py / scheduler.py / cli.py / export.py
├── providers/ / docs/          Environment and installation guides
├── connectors/                 Adapter entrypoint documentation
├── scheduler/ / cli/           Execution documentation
├── data/                       Empty creator-data directories
├── examples/demo.py
└── tests/fixtures/              Fictional creator and transcript
```

An initialized creator folder contains `config.yaml`, `workflows.yaml`, an `AGENTS.md` entrypoint, `.contentmaxxing/` intelligence and `data/{creator,sources,ideas,content,analytics,reports,experiments,feedback,mining,revisions,tasks,runs}`. JSON records are authoritative; source files and brain Markdown remain inspectable. Writes are atomic per file and CLI mutations use a portable single-writer lock. Cross-record changes are not database transactions; task/run checkpoints make normal resumes idempotent. After a process crash, verify no writer is running before removing `.writer.lock`. Back up your folder before manually editing record relationships.

Record filenames match their IDs: a prefix, underscore and 12 hexadecimal digits.
External-agent response files belong in `data/task-results/`; `data/tasks/` holds
engine task records. Other working files are preserved but are not collection
records. Corrupt canonical records are reported rather than silently skipped.

```sh
contentmaxxing --workspace ./my-creator export --output ../my-creator.zip
```

The ZIP includes identity, voice, source originals, IDs, ideas, history, analytics/raw responses, skills, article frameworks, learnings, experiments and pending runs. Environment credentials are not included. Unzip anywhere, install the CLI, and point `--workspace` at it. The tests verify this move.

## Demonstrated behavior and boundaries

**Release QA: ready for a guided Codex beta; public plug-and-play launch still
needs a real editorial pilot and a published install entrypoint.** Typefully is
optional. See [the QA report](QA_REPORT.md) for reproduced bugs, fixes,
installation evidence and remaining release checks.

Run `python -m unittest discover -s tests -v` after installing the repository.
The current verification includes 235 passing tests on Python 3.11.
[Fresh Codex CLI acceptance](CODEX_ACCEPTANCE.md) exercised native discovery,
interview and file-dump onboarding, text-HUD fallback, and three actual
model-written X drafts per path in NEEDS_REVIEW. Tests use fictional creator
material; real voice/editorial acceptance remains a pilot milestone. Packaging and adapter
validation details are recorded in [VERIFICATION.json](../VERIFICATION.json).

A later [native creator trial](NATIVE_CREATOR_TRIAL.md) exercised voice
learning, X/LinkedIn/TikTok writing, a same-ID revision and an X-only preference
in fresh Codex sessions. It found and fixed unnecessary clipping of short source
notes. The persona and review direction were fictional; no real creator quality
grade is claimed.

The [weekly creator trial](WEEKLY_CREATOR_TRIAL.md) ran analytics → planning →
four native review drafts → three winner follow-ups, preserving the same week
on resume. It also led to explicit evidence attachment for pending compound
tasks and a narrow writing-guidance comparison. All trial data is fictional.

The [mining trial](NATIVE_MINING_TRIAL.md) covered a multi-speaker conversation
across three windows, then tested independent extraction packets without chat
history. New tasks carry bounded prior-topic context and can attach evidence to
an existing idea without replacing its editorial choices. The model probes and
mechanical checks remain separate from human semantic quality review.

```sh
python examples/demo.py --workspace /tmp/contentmaxxing-demo-new
python examples/intake_demo.py --workspace /tmp/contentmaxxing-intake-demo-new
python examples/journey_demo.py --workspace /tmp/contentmaxxing-journey-demo-new
python examples/feedback_loop.py --workspace /tmp/contentmaxxing-feedback-new
python examples/voice_learning.py --workspace /tmp/contentmaxxing-voice-new
```

The offline demo onboards Morgan, captures a transcript, mines 6 literal candidates, stores/selects them, creates 6 source-excerpt X drafts, records simulated review/publication, imports 6 **fictional** analytics rows, identifies a 10× bookmark winner against 5 matched peers, and creates 3 new-value opportunities. Nothing is sent to a model or published. `demo-result.json` and the creator folder make every step inspectable. External-agent native writing, article/video routing and weekly resume are separately tested using explicit task results.

Completed in v1: installable host entrypoints and shared command procedures,
guided kickoff, live home/progress routing, resumable saved-plan execution,
portable intelligence/data contracts, onboarding, text
resumable source mining, bounded evidence retrieval, explicit scoped creator feedback,
same-ID draft revisions with history, cited voice proposals with safe application,
bank/search/dedup, selection/planning, reviewable
platform generation, provider abstraction, job-aware analytics/reports,
compound opportunities, experiments, ZIP portability, Typefully typed adapter
and mocked coverage, and resumable YAML workflow execution.

Intentionally deferred: dashboard, media/OCR/transcription ingestion, live Typefully account certification, media/QRT upload, direct TikTok/Substack-article publishing, account-wide historical post import, always-on scheduler hosting, autonomous approval, richer semantic retrieval/indexing, fixed-age causal analytics and native SDKs per model provider.

Next three milestones:

1. Pilot complete loops with real creators: evaluate learned voice, useful topics, evidence quality and feedback across subsequent batches.
2. Publish a reviewed, versioned release with CI and a verified public install entrypoint.
3. Verify additional AI hosts and recurring execution. Certify optional connectors such as Typefully independently of the core release.

The [release procedure](RELEASING.md) builds a wheel from the source archive,
checks packaged resources and versions, and tests that exact installed wheel.
CI retains candidate hashes and per-runtime evidence. The workflow is prepared
locally; a passing public CI run and a public download endpoint remain pending.

## Project foundation and editorial evaluations

The engine now retrieves exact passages from the creator's source library and
supplies bounded evidence to drafts. Explicit creator corrections can apply to
one item, one platform or future writing generally; their scope and original
revision remain inspectable. Ask your AI to find relevant proof or remember a
specific preference. See [retrieval and feedback](RETRIEVAL_AND_FEEDBACK.md)
for the CLI, task contract, configurable budgets and fictional demo.

Long transcripts now mine through saved bounded windows, and revision tasks apply
creator feedback to existing drafts while preserving content IDs and before/after
history. See [mining and revisions](MINING_AND_REVISIONS.md) for resume,
conflict recovery, review boundaries and the end-to-end example.

`PROJECT.md`, `STATUS.md` and `DECISIONS.md` preserve this repository's purpose,
current state and important choices alongside `AGENTS.md`. They map the existing
inbox, work states and outputs without creating another task database. See
[the foundation mapping](FOUNDATION.md).

The optional evaluation lab makes skill/model changes reviewable against six
fixed fictional briefs. Your current AI executes the same shared task contracts;
the engine checks imports and lifecycle behavior. Human judgment of voice,
attribution and usefulness remains explicit and pending until supplied.

```sh
contentmaxxing evals prepare --output ./eval-runs/baseline --label codex-baseline
contentmaxxing evals report --run ./eval-runs/baseline
```

Ask your host to run the prepared packets and show you the human checks. The
agent-evaluation skill handles submission and comparison; creators do not need
to author result JSON. Each response, failed attempt and declared human review
is retained. First-pass comparisons do not hide retries. See
[the evaluation guide](EVALUATIONS.md) for matched trials and limits.
