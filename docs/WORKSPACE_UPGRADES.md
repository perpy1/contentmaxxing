# Keep the engine improving without losing your own system

Your host commands and your creator workspace have separate copies of the kit.
Reinstalling host commands updates `.contentmaxxing-agent/<host>/core/`. The engine
and agent use the initialized workspace's `.contentmaxxing/` skills when working
on content. Update that copy deliberately so improvements reach your next tasks.

You can ask your AI:

> Update my CONTENTMAXXING kit from this release. Preview my workspace changes,
> apply the unchanged bundled files, and show me any customized files that need
> a decision. Preserve my voice, sources, drafts and work in progress.

The following commands also work directly with the installed CLI. No connector,
model API key or network access is required by the workspace upgrade itself.

## Preview and apply

After installing the new engine from its local checkout or wheel and rerunning
`install --agent <host>` with your original scope/path:

```sh
contentmaxxing --workspace ../my-content upgrade --dry-run
contentmaxxing --workspace ../my-content upgrade
```

The preview is read-only. The apply uses the workspace's ordinary single-writer
lock. Each file has an explicit action:

| File state | Action |
| --- | --- |
| Bundled file unchanged since installation or its last accepted update | Update |
| New bundled file with no existing collision | Add |
| File already matches its tracked version and the incoming release | Leave unchanged |
| Edited or deliberately deleted tracked file | Preserve |
| Existing file with no recorded baseline | Preserve, even if it matches |
| File retired from the release or a creator-only skill | Retain |

Root `config.yaml`, `workflows.yaml`, `AGENTS.md`, `START_HERE.md`, host registration
and everything in `data/` are outside this operation. Defaults under
`.contentmaxxing/config/` are eligible; live root settings are not silently migrated.
Pending tasks keep their frozen instructions and evidence. Newly created tasks
use updated files. Existing saved mining passes retain their original instructions.

The output names written and preserved files and summarizes unchanged files.
Preserved files mean the workspace contains a mix of versions; the command does
not claim a complete upgrade or automatically merge editorial instructions.

## Review a preserved file

Paths are relative to `.contentmaxxing/`:

```sh
contentmaxxing --workspace ../my-content upgrade --review skills/x-writing/SKILL.md
```

This returns a unified text diff, current/incoming paths, both hashes and an
`accept` value such as `skills/x-writing/SKILL.md=<review-token>`. Binary files
return paths and hashes with a null diff; inspect both files before choosing.

To choose the incoming version, copy the exact returned value:

```sh
contentmaxxing --workspace ../my-content upgrade --accept 'skills/x-writing/SKILL.md=<review-token>'
```

The token binds the path and both versions. A changed local or incoming file
invalidates it before any upgrade writes. Acceptance replaces the whole selected
file, with a backup; it also applies other unchanged bundled updates in the same
operation. Repeat `--accept` for multiple reviewed files, or add `--dry-run` to
preview. To combine a customization with the incoming improvement, edit that
specific file manually instead. Such a merge remains a customization and future
automatic upgrades continue to preserve it.

## Workspaces created before tracking existed

No manifest means no evidence of which files were edited. Existing differing
files cannot safely be replaced automatically. The preview labels the workspace
as legacy and preserves them. New missing assets can still be added.

To register existing files that exactly match this installed release:

```sh
contentmaxxing --workspace ../my-content upgrade --adopt-matching --dry-run
contentmaxxing --workspace ../my-content upgrade --adopt-matching
```

Differing files remain preserved until individually reviewed. Exact matches can
receive future automatic updates after adoption. No inference from file dates or
a matching version label is used to replace unknown content.

## Inspect and recover

`.contentmaxxing/intelligence-manifest.json` records the last accepted hash for
each managed asset. Every changing upgrade saves ordinary before-files and a
report under `.contentmaxxing/updates/upgrade_<id>/`. These travel with exports.
The record has `PREPARED`, `APPLIED` or `ROLLED_BACK` status.

An ordinary write failure rolls back affected files. If the process terminates
abruptly, a PREPARED journal blocks further upgrades. Confirm the writer is no
longer running before removing a stale `.writer.lock`, then use:

```sh
contentmaxxing --workspace ../my-content upgrade --recover upgrade_<id>
```

Recovery preflights every affected file and backup, then restores the pre-upgrade
versions. A newer edit or a changed backup stops recovery without overwriting it.
Resolve that specific conflict manually while keeping both versions, then retry.
Recovery itself can be resumed after interruption. It does not undo a completed
upgrade; completed before-files remain available for deliberate manual restoration.
Symlinked targets and manifest paths outside the intelligence directories are refused.

## Verification scope

`tests/test_workspace_upgrade.py` verifies real engine task behavior, data and
customization preservation, legacy adoption, stale decisions, ordinary rollback,
interrupted recovery, malicious paths, writer exclusion and recovery after ZIP
export/move. These are local engine tests, not native host discovery or an editorial
quality trial. No active creator pilot is modified by the tests.

The 2026-09-30 verification passed 225 tests on Python 3.11 and 224 with one
expected skip on Python 3.9. The installed wheel passed the offline workflow
smoke outside the checkout, including upgrade, export, restore and repeated use.

A separate installed-CLI replay used a copy of the prior fictional native weekly
workspace. It adopted exact matches, then reviewed four differing files whose
bytes matched a known earlier wheel: the command protocol, compound procedure,
quality checks and compound skill. It preserved a deliberately customized Brand
Brain template, every root setting and all 77 creator data files. The source QA
folder was unchanged; repeating upgrade wrote nothing. Review decisions in this
replay are test actions on fictional material, not a new native model or human
editorial trial. Evidence is recorded in `VERIFICATION.json` under
`workspace_upgrades`; the local release is in `dist/upgrade-increment/`.
