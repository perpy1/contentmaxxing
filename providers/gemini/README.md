# Gemini / other model environments

For Gemini CLI, run `contentmaxxing install --agent gemini --path <creator-folder>`
or use `--scope user`. The installer generates TOML commands under `.gemini/commands/`.
Invoke `/contentmaxxing:start` or `/contentmaxxing:help`. These route to the same
Markdown procedures and skills used by other hosts. See [installation](../../docs/INSTALL.md)
for validation limits and runtime setup.

Use the generic external-agent task contract: load the workspace orchestrator and selected skill, read creator/source inputs, write JSON matching output_contract, then import it using the CLI. This retains identity and evidence without requiring a Gemini-specific SDK.

A compatible Chat Completions server can also use the common model adapter when its documented endpoint and model are configured by the creator. Native Gemini tool-calling/SDK transport is deferred; no unsupported API capability is implied.
