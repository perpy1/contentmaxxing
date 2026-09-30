# Compatible model execution

All model providers execute the same task and validation contract in `contentmaxxing/providers.py`. Select `openai-compatible` in creator config, set model/base_url/api_key_env, and supply the key through that environment variable. The endpoint is `<base_url>/chat/completions`. The adapter requires JSON object output but does not assume server support for a specific JSON mode extension.

This is also usable with local compatible servers. No model is selected by default, and there is no separate OpenAI editorial logic. Provider output is checked against task contracts, persisted schemas and exact source references. Errors leave task files available for external-agent completion.
