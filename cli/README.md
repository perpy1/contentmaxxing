# CLI entrypoint

The installable `contentmaxxing` command and `python -m contentmaxxing` both route to `contentmaxxing/cli.py`. Output is JSON, validation failures return exit status 1, and external-agent work returns a PENDING task with exit status 0. `--workspace` and a temporary `--provider` override are global options placed before the command. See `contentmaxxing --help` and the main README for the complete workflow.

`install`, `uninstall`, and `doctor` manage native host skills with `--agent`,
`--scope project|user`, and optional project `--path`. They do not use `--workspace`
or initialize creator data. Install/uninstall support `--dry-run`. `commands --agent`
shows the creator-facing menu. `overview` reads saved creator progress without
the status mutations performed by `status <id> <state>`. See [installation](../docs/INSTALL.md).

`welcome` shows the text HUD and two onboarding choices; `--json welcome` emits
structured metadata. Interactive installs show the HUD; redirected/scripted
installs retain JSON (global `--json` forces it). `start --mode interview|files`
chooses/resumes an input path. `--source` accepts files or directories. In file
mode the host prepares a cited `--profile-proposal`, then records the creator's
confirmation with `--confirm-profile`; `--answers` supplies their corrections.
