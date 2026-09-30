# CONTENTMAXXING

[![Package and test](https://github.com/perpy1/contentmaxxing/actions/workflows/tests.yml/badge.svg?branch=main)](https://github.com/perpy1/contentmaxxing/actions/workflows/tests.yml)

**Your work is already full of content. Stop starting from zero.**

An open-source creator agent kit for the AI you already use. Install its skills,
bring your real work, and build a content engine around your own voice.

![CONTENTMAXXING terminal logo](contentmaxxing/assets/welcome.png)

**Capture → Create → Compound.**

Find the good shit. Make something useful. If people care, keep going.

**Early testing release · MIT · Local-first · Codex tested**

[Start testing](docs/BETA_TEST.md) · [Install guide](docs/INSTALL.md) · [Full engine reference](docs/ENGINE_REFERENCE.md) · [Contribute](CONTRIBUTING.md)

## What it does

Calls, projects, customer questions, work notes, old posts and mistakes contain
ideas worth using again. CONTENTMAXXING preserves that source material, finds
useful topics, plans what to make, and helps you develop what works.

You get a **Brand Brain, Voice, Content Pillars, Offer, Idea Bank, first drafts
and a launch plan**. Later sessions build on that saved work and your corrections.

Your current AI supplies the reasoning. **Typefully is optional.** You can review
and publish manually, then import CSV/manual analytics. The default host-agent
path needs no additional model API key.

```text
Real work → Capture → Idea bank → Plan → Create → Review → Publish
                         ↑                                  ↓
                    New angles ← Compound winners ← Measure behavior
```

Every plan separates **Topic + Format + Job**: what you want to say, the container
that suits it, and what you want readers to do. Impressions are one signal;
saves, conversations, follows, trust and inbound can matter more for a given job.

## Start in Codex

You need Python 3.9+ (3.11+ recommended) and an AI environment with local file and
command access. Native Codex CLI sessions have exercised both onboarding paths.
Ordinary browser chat alone cannot execute this kit.

Clone the repository and install the kit:

```sh
git clone https://github.com/perpy1/contentmaxxing.git
cd contentmaxxing
python3 -m venv .venv
source .venv/bin/activate
python -m pip install .
contentmaxxing install --agent codex --path ../my-content
contentmaxxing doctor --agent codex --path ../my-content
```

Open `../my-content` in Codex and start a new session. Invoke:

```text
$contentmaxxing-start
```

Or ask your coding agent to perform the setup from this repository:

> Install CONTENTMAXXING for my creator folder, verify the installation, and
> walk me through building my content engine. Ask a few questions at a time.

The welcome offers two ways in:

1. **Curated interview** — refine your audience, offer, voice and direction through
   a conversation about your real experience.
2. **Mega file dump** — bring a folder of source material; review the profile and
   topic suggestions it extracts before they become your creator identity.

You can combine both. The first batch targets up to three drafts, with fewer when
there is not enough evidence. You review before publishing.

Use the [first-session walkthrough](docs/BETA_TEST.md) to test voice, useful topics,
corrections and fresh-session resume. For Windows, other hosts, updates and
troubleshooting, see [installation](docs/INSTALL.md).

## Commands you will actually use

In Codex, `$contentmaxxing` opens the home view. These are actions for your AI;
it handles the underlying CLI and task files.

| Action | What it helps you do |
| --- | --- |
| `$contentmaxxing-start` | Onboard and create your first batch |
| `$contentmaxxing-next` | Take the next useful step |
| `$contentmaxxing-progress` | See saved work and the next decision |
| `$contentmaxxing-resume` | Continue an unfinished session or batch |
| `$contentmaxxing-capture` / `$contentmaxxing-mine` | Save real material and find source-linked topics |
| `$contentmaxxing-voice` | Learn from your writing samples and corrections |
| `$contentmaxxing-plan` / `$contentmaxxing-create` | Make and execute a Topic + Format + Job plan |
| `$contentmaxxing-week` | Run the weekly editorial workflow through review |
| `$contentmaxxing-review` | Read and revise your actual drafts |
| `$contentmaxxing-analytics` / `$contentmaxxing-compound` | Measure outcomes and develop useful follow-ups |
| `$contentmaxxing-help` | Browse all 19 actions |

The shared writing skills cover X, LinkedIn, TikTok scripts, articles, Substack
articles and Notes. A source can travel between platforms, but each expression
should suit its audience and format. Your voice comes from your material, not
from a built-in creator personality.

## Use your preferred AI

| Environment | Installer option | Testing status |
| --- | --- | --- |
| Codex CLI | `--agent codex` | Native onboarding, drafting and resume trials with fictional creators |
| Claude Code | `--agent claude` | Adapter and file-format tests; native trial needed |
| Cursor | `--agent cursor` | Adapter and file-format tests; native trial needed |
| Gemini CLI | `--agent gemini` | Adapter and file-format tests; native trial needed |
| Other filesystem-capable agents | `--agent generic` | Portable Markdown entrypoint |

One orchestrator routes to **19 shared skills**. Thin host adapters expose those
same instructions; they do not contain separate editorial engines. An optional
OpenAI-compatible provider executes the same task contracts through an API.

## Your creator memory belongs to you

Sources, creator documents, ideas, drafts, analytics and experiments live in
inspectable local files. Export the workspace and move it to another compatible
AI. Reinstall the runtime and host commands on a new machine; your creator
history stays with the folder.

```text
contentmaxxing/       Orchestrator, skills, schemas, templates and Python engine
providers/           Host and model adapter guides
connectors/          Optional integration guides
scheduler/           Portable recurring-workflow configuration
examples/            Fictional demonstrations
scripts/             Package and acceptance checks
tests/               Automated tests and fictional fixtures
docs/                Installation, testing, architecture and launch guides
```

Your separate creator folder contains `data/creator`, `data/sources`,
`data/ideas`, `data/content`, `data/analytics` and `data/reports`. The full
[engine reference](docs/ENGINE_REFERENCE.md) covers the CLI, Typefully setup,
weekly runs, schemas, experiments, adding skills and adding platforms.

## What has been verified

The latest installed-package run passed **268 tests on Python 3.11** and **267
plus one expected skip on Python 3.9**. Offline checks exercise the content loop,
review gates, resume, export and upgrades. Native Codex trials used fictional
creators and actual model-written responses.

Those checks do not establish real creator voice quality or audience growth.
That is what this testing release is for. Share feedback through this
repository's **Issues → New issue → Creator beta feedback**. See
[STATUS.md](STATUS.md), [verification records](VERIFICATION.json) and the
[testing walkthrough](docs/BETA_TEST.md) for scope.

Direct intake supports UTF-8 TXT, Markdown, CSV, JSON/JSONL, SRT and VTT.
PDF, image, audio and video inputs need host extraction or a text export.
Typefully has a typed adapter and mocked tests; live integration remains
unverified. Desktop welcome-image rendering depends on the host.

A dashboard, hosted scheduler, automatic media ingestion and autonomous approval
are outside this first testing release. The repository and wheel are the install
paths; no public PyPI/npm package or marketplace listing is claimed.

## Build and contribute

See [CONTRIBUTING.md](CONTRIBUTING.md) for setup and tests, [AGENTS.md](AGENTS.md)
for coding-agent rules, and [the release procedure](docs/RELEASING.md) for building
and verifying the exact package. [Launch copy](docs/LAUNCH_KIT.md) and a
[changelog](CHANGELOG.md) are included.

Next milestones: learn from real creator trials, publish a versioned download
with passing hosted CI, then verify more hosts and optional connectors.

[MIT license](LICENSE). Capture → Create → Compound.
