# Install CONTENTMAXXING into your AI

CONTENTMAXXING adds creator abilities to your existing AI environment. Install
the local engine once, register its native commands, then let the AI guide you
from real work to a custom content engine. Your AI handles command execution and
internal files; you provide context, source material, and editorial judgment.

No Typefully account or publishing API key is required. The default experience
uses your current AI and local files. Manual publishing and CSV/manual analytics
complete the same content loop; connectors can be added later.

Maintainers can build and test a downloadable wheel using the
[release procedure](RELEASING.md). It records exact artifact hashes and exercises
the installed package; public hosting and a versioned download URL remain pending.

## From this checkout

Python 3.9+ is required. In the CONTENTMAXXING checkout:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install .
contentmaxxing install --agent claude --path ../my-content
```

On Windows, activate with `.venv\Scripts\Activate.ps1` in PowerShell. Choose
`codex`, `claude`, `cursor`, `gemini`, or `generic`. The path names the project
folder you will open in your AI; it can be a new folder. The AI must have file
and command execution access to it. Reopen the host or reload its skills if the
new commands do not appear.

Ask your AI to do the setup from the checked-out repository if you prefer:

> Install CONTENTMAXXING into this AI for my creator folder. Set up its local
> Python engine, install the native skills, check installation, then start my
> content engine. Ask me for missing context a few questions at a time.

The repository is not published to a package registry or marketplace. Do not
use a guessed `npx` or `pip install contentmaxxing` command. A public one-command
bootstrap is a release milestone after the package identity and hosting exist.

## Choose installation scope

Project scope is the default and keeps the command bundle in the chosen folder:

```sh
contentmaxxing install --agent codex --path ../my-content --dry-run
contentmaxxing install --agent codex --path ../my-content
contentmaxxing doctor --agent codex --path ../my-content
```

For abilities across your local projects, install once in user scope:

```sh
contentmaxxing install --agent claude --scope user
contentmaxxing doctor --agent claude --scope user
```

User scope registers commands under your home directory. The host works on the
creator folder you open, and saves creator data there. It does not use your home
directory as the creator workspace. `--path` and user scope cannot be combined.
Installation does not edit AGENTS.md, CLAUDE.md, GEMINI.md, host settings, or other
skills. Host security/trust settings still apply.

## Commands in each environment

| Host | Native entrypoint | Individual action | Installation directory |
| --- | --- | --- | --- |
| Codex CLI / IDE | `$contentmaxxing` | `$contentmaxxing-start` | `.agents/skills/` |
| Claude Code | `/contentmaxxing` | `/contentmaxxing-start` | `.claude/skills/` |
| Cursor | `/contentmaxxing` | `/contentmaxxing-start` | `.cursor/skills/` |
| Gemini CLI | `/contentmaxxing` | `/contentmaxxing:start` | `.gemini/commands/` |
| Generic agent | Read `CONTENTMAXXING.md` | Ask “contentmaxxing start” | `.contentmaxxing-agent/generic/` |

Project directories are relative to your selected folder; user-scope directories
are relative to your home. Generic is an explicit Markdown entrypoint, not an
automatically registered slash command. In Codex desktop/chat interfaces, use
the available skill selector; the `$` spelling above is for Codex CLI/IDE.

All hosts expose the same 19 actions. Begin with the umbrella entrypoint and use
`next` to follow the guided journey; `help` exposes the full menu. Action arguments
such as `$contentmaxxing next` route through that same umbrella skill in Codex.

| Action | What you get |
| --- | --- |
| `start` | Guided setup/resume, learned voice, real ideas, first drafts and launch plan |
| `next` | One useful step based on saved progress |
| `progress` | Read-only current stage, saved work and next action |
| `resume` | Continue a saved checkpoint without replacing the batch |
| `voice` | Learn sample-backed voice observations and preserve creator corrections |
| `capture` | Preserved real source material |
| `mine` | Distinct topics with exact citations |
| `ideas` | Search and selection from your idea bank |
| `plan` | Weekly Topic + Format + Job choices |
| `create` | Execute that saved plan through the shared scheduler |
| `draft` | Native X, LinkedIn, TikTok or Substack content |
| `article` | Evidence-backed article with one structural framework |
| `week` | Resumable editorial workflow ending in review |
| `review` | Actual drafts, edits and explicit approval |
| `publish` | Explicit connector delivery or manual publication flow |
| `analytics` | Imported metrics, behavioral outcomes and measured winners |
| `compound` | New value from a winner |
| `status` | Read-only saved progress and next step |
| `help` | Command menu |

For example, `/contentmaxxing-draft a LinkedIn post from yesterday's client call`
in Claude Code supplies intent to the draft skill. The AI resolves the source,
asks only for missing choices, and executes the shared procedure. Ordinary
language works too. `contentmaxxing commands --agent claude` prints the menu.
The native `status` action calls the read-only CLI `overview`; the CLI's separate
`status <id> <state>` operation deliberately changes a content record.

The standard entrypoint plus 19 actions are thin wrappers. One catalog at
`contentmaxxing/config/commands.json` and shared procedures under `commands/`
own the routing. The 19 specialized skills remain modular underneath.

## First session

Open your creator folder and invoke CONTENTMAXXING or its native `start` action. The welcome HUD
offers **1. Curated interview** or **2. Mega file dump**. Choose the interview for
a few tailored questions about your direction and real work. Choose the dump
to bring a folder or multiple files first; the agent reads them, proposes a
profile with file/line evidence, and asks you to confirm or correct it. It then
asks only for missing essentials. You can combine or switch paths without
discarding your sources or answers.

Direct inputs are UTF-8 TXT, Markdown, CSV, JSON/JSONL, SRT and VTT. The inventory
at `data/creator/intake-manifest.json` reports accepted files, duplicates and
exceptions. Hidden/generated directories and symlinks are skipped. Split files
larger than 50 MiB. PDF/DOCX, images, audio and video need extraction or
transcription through host tools or a text export; unsupported originals stay
at the supplied locations and are not claimed as read or portable.

The interactive terminal installer displays a text HUD. Scripted installs return
JSON containing paths to `WELCOME.md` and the PNG welcome asset. An agent doing
the installation/start should display that asset when its host supports local
images and present the two choices in chat; text-only hosts use the terminal
HUD. This does not replace the host application's own home screen. Run
`contentmaxxing welcome` to show the text HUD or `contentmaxxing --json welcome`
for its structured version.

The AI learns your voice from evidence, builds your creator documents, mines
topics, chooses a small batch, and writes actual drafts. You finish with a launch
plan and review queue. Setup is saved so another session or compatible AI can
resume. No model key is needed when your current host executes the skills.

## Update, remove, and move

After installing an updated engine from its checkout or wheel, rerun `install`
with the same agent/scope/path. A manifest records file hashes. Unchanged owned
entrypoints can update; locally edited or unowned files cause an actionable
conflict before writes. Resolve those specific files manually after preserving
your changes. There is no force-overwrite flag. Symlinked installation targets
are refused. Installation uses a lock and rolls back ordinary write failures;
an abrupt process/machine crash may require resolving partial files manually.

Then update the initialized creator workspace's own intelligence:

```sh
contentmaxxing --workspace ../my-content upgrade --dry-run
contentmaxxing --workspace ../my-content upgrade
```

This updates unchanged bundled skills, prompts, schemas and registries. It adds
new assets and preserves customized, deliberately deleted, untracked and retired
files. Creator documents, content, analytics, root settings and pending tasks stay
unchanged. A report lists anything preserved, so a partial upgrade is explicit.
Older workspaces without a baseline can adopt exact matches deliberately and
review other files individually. See [workspace upgrades](WORKSPACE_UPGRADES.md)
for diffs, reviewed replacement, backups and interrupted-write recovery.

```sh
contentmaxxing uninstall --agent claude --path ../my-content --dry-run
contentmaxxing uninstall --agent claude --path ../my-content
```

Uninstall removes only unchanged manifest-owned files. Edited files are listed
and retained. Creator data, workspace-customized skills, and other host files
are preserved. Empty installation directories may remain.

Installed core assets live in `.contentmaxxing-agent/<host>/core/`. They are
defaults. Initialized creator workspaces retain their own `.contentmaxxing/`
skills and inspectable `data/`; installations do not overwrite these. Links in
native wrappers are relative to the wrapper file so a project install can move.
`runtime.json` is a machine-local Python interpreter fallback for when the CLI
is not on the host's PATH. It is not a portable runtime: reinstall the engine
and host commands on a new machine.

Creator ZIP exports include creator data and workspace intelligence. They omit
machine-specific registrations. After unpacking, install your preferred host
commands into that folder. If you switch hosts on the same folder, uninstall the
old adapter first or use the generic entrypoint; some hosts discover other hosts'
skill directories and can otherwise show duplicate names.

## Verification and release scope

Automated tests cover command routing, relative paths, frontmatter/TOML, project
and user scopes, repeat installation, edited-file conflicts, rollback, uninstall
preservation, export/reinstall, and CLI kickoff from outside the checkout.
They also cover both onboarding paths, bulk inventories and deduplication,
profile evidence/confirmation, corrections, source integrity, portability,
interrupted intake recovery, legacy launches, and binary welcome assets.
`doctor` checks installation integrity; it does not open an AI host or prove its
skill-discovery behavior. A [fresh Codex CLI acceptance check](CODEX_ACCEPTANCE.md)
exercised native discovery and both onboarding paths with fictional creators.
Desktop image rendering, Claude Code, Cursor and Gemini still need their own
native acceptance checks; their adapter formats alone do not certify discovery.

This is a local CLI/skill distribution. Hosted chat applications require their
own file/execution or plugin integration. Installing a local skill does not
automatically register an account-wide browser assistant. Public registry
distribution, marketplace submission, and fully unattended host execution are
deferred.

## Reference and design rationale

The user's GSD reference now points to [GSD Pi](https://github.com/open-gsd/gsd-pi).
Its guided setup, discoverable commands, project memory and resumable work are
useful product patterns. GSD Pi also owns a standalone runtime. CONTENTMAXXING
uses the creator's host for reasoning and keeps its methodology in portable
files. See [GSD setup](https://github.com/open-gsd/gsd-pi/blob/main/docs/user-docs/getting-started.md).

Native paths and invocation formats were checked against official documentation:
[Codex skills](https://learn.chatgpt.com/docs/build-skills),
[Claude Code skills](https://code.claude.com/docs/en/skills),
[Cursor skills](https://cursor.com/help/customization/skills), and
[Gemini CLI commands](https://geminicli.com/docs/cli/custom-commands/).
