# Contributing to CONTENTMAXXING

Start with [AGENTS.md](AGENTS.md) for architecture and invariants. Preserve
Capture → Create → Compound and Topic + Format + Job. Methodology is shared;
creator identity and voice come from their material.

For creator testing, use the [beta walkthrough](docs/BETA_TEST.md). Report the
host, OS, installed version, steps, expected behavior and actual behavior.
Writing feedback should separate usefulness, voice and evidence quality.
Use anonymized excerpts; public issues and pull requests are not a place for
private creator workspaces or credentials.

## Development

Python 3.11+ is recommended for development; the runtime supports 3.9+.

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e . -r requirements-dev.txt
python -m unittest discover -s tests -v
python examples/demo.py --workspace ../contentmaxxing-demo
```

Use a new directory for each demo. The demo is fictional and offline. For package
changes, run the [installed-artifact checks](docs/RELEASING.md). A green local
suite does not establish a creator's approval of the writing.

## Changes

Keep shared content logic in skills and the engine. New hosts should adapt the
same catalog and task contracts. New connectors translate transport shapes;
they should not own editorial behavior. See the [engine reference](docs/ENGINE_REFERENCE.md)
for adding skills and platforms.

Include relevant behavior tests, fictional fixtures and documentation. Explain
the trigger, resulting behavior and verification in the pull request. Never add
real creator data or API keys. Check the staged file list before committing.
New integrations should state which capabilities are mocked and which have
actually been exercised against the service.
