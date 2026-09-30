# Prepare a release candidate

The kit is currently a local Codex beta. There is no public download endpoint or
package-registry release yet. This workflow prepares inspectable candidates; it
does not publish a release, create a tag, or certify creator writing quality.

## Build and inspect

From a checkout with Python 3.11+, create/activate a virtual environment, then run:

```sh
python -m pip install -r requirements-dev.txt
python -m build --outdir dist/candidate
python scripts/verify_release.py --dist dist/candidate --output dist/candidate/ARTIFACTS.json
```

Use a fresh output directory for each candidate. The default PyPA build produces
the source archive first and builds the wheel from that archive. This catches a
source distribution that cannot rebuild the kit. With an already provisioned
build environment, `--no-isolation` permits an offline build; record that choice.
Normal builds resolve dependencies from the index, so this is a reproducible
procedure, not a promise of identical compressed bytes across toolchain versions.
See the [PyPA packaging guide](https://packaging.python.org/en/latest/tutorials/packaging-projects/).

`verify_release.py` compares every packaged runtime file with the checkout,
including skills, schemas, commands, templates, evaluation fixtures and the
welcome image. The source archive must also contain the guides, tests, fixtures,
scripts and CI workflow. Missing/changed/stale files, mixed archive versions and
unexpected packaged creator data fail verification.

The output is:

- The wheel and source archive.
- `ARTIFACTS.json`: version, source commit when available, worktree state, file
  hashes and package hashes. It records integrity checks, not test results.
- `SHA256SUMS`: hashes of the two distributable archives.

An uncommitted/local build is labeled `LOCAL_CANDIDATE`. To verify a tagged
candidate, add `--tag v0.1.0` (substitute the actual version). The tag must already
exist at HEAD, match both package versions, and have a clean worktree. The script
never creates Git state. `pyproject.toml` and `contentmaxxing/__init__.py` must agree.

## Test the exact wheel

Install the candidate into a separate, non-editable virtual environment. These
commands assume the shell remains at the repository root and `.qa-venv` is a
new disposable environment outside the checkout:

```sh
python -m venv ../.qa-venv
../.qa-venv/bin/python -m pip install -r requirements-dev.txt dist/candidate/*.whl
../.qa-venv/bin/python -m pip check
../.qa-venv/bin/contentmaxxing --help
../.qa-venv/bin/python -I scripts/verify_release.py --installed dist/candidate/ARTIFACTS.json
../.qa-venv/bin/python -I -m unittest discover -s tests -v
../.qa-venv/bin/python -I scripts/release_smoke.py --output dist/candidate/smoke.json
```

On Windows use the environment's `Scripts/python.exe` and `Scripts/contentmaxxing.exe`.
`-I` prevents checkout/PYTHONPATH imports. The installed check rejects an editable
checkout and compares installed file hashes to the candidate. The smoke test uses
fictional sources and scripted external-task responses with network calls disabled.
It exercises onboarding, voice, mining, review, manual measurement, compounding,
planning, revisions, feedback, experiments, upgrades and export/restore. Actual
creator judgment and native-host acceptance remain separate tests.

## GitHub workflow

`.github/workflows/tests.yml` runs on pushes, pull requests and manual dispatch:

1. Build once with Python 3.11 and verify archive contents. Tag runs enforce the
   tag/version/clean-tree checks.
2. Upload that exact candidate for both Python 3.9 and 3.11 jobs.
3. Each job checks archive hashes, installs the same wheel, checks installed bytes,
   runs the full suite outside the checkout, and exercises the demo and offline smoke.
4. Retain per-runtime logs and smoke reports. `candidate-ready` passes only after
   both runtime jobs succeed.

The `candidate` artifact can exist even if tests fail. Download and inspect the
matching `evidence-python-*` artifacts; require the whole workflow, including
`candidate-ready`, to pass. This workflow has read-only repository permissions and
does not publish to GitHub Releases or PyPI. GitHub execution cannot be certified
until the repository exists and the workflow actually runs there.

## Publish the reviewed candidate

For an early testing release, use the README and `docs/BETA_TEST.md` to invite
creator feedback, and disclose the tested hosts and limitations in
`docs/LAUNCH_KIT.md`. A completed real creator pilot is not required to invite
that testing. Require the package checks and a passing hosted CI run before
publishing downloadable artifacts.

Before claiming broader product acceptance, require a real creator pilot with usable voice/content,
native host acceptance for the hosts advertised as tested, and successful CI for
the exact tagged commit. Keep Typefully optional; live connector validation is
required only for claims about that integration. Do not conflate the offline
smoke or fictional Codex trials with real audience outcomes.

Once a repository destination is chosen and publication is authorized:

1. Commit the reviewed source, set the release version and push its matching tag.
2. Download the passing tag workflow's `candidate` and evidence artifacts. Check
   `ARTIFACTS.json` identifies that tag/commit and the archive hashes match.
3. Draft release notes describing tested hosts, installation, changes, limitations
   and the actual creator review. Attach these exact archives; do not rebuild.
4. Create a draft release using `gh release create TAG --verify-tag --draft
   --notes-file NOTES_FILE WHEEL SOURCE_ARCHIVE ARTIFACTS_JSON SHA256SUMS` with the
   real paths. Review the final assets/notes, then publish when authorized.

GitHub CLI's [`--verify-tag` and `--draft`](https://cli.github.com/manual/gh_release_create)
avoid implicitly creating a tag or publishing during preparation. Release notes
should link the exact passing workflow and keep its per-runtime evidence.

After publication, document the actual owner/repository and versioned asset URL
in `docs/INSTALL.md`. Until then, do not advertise a made-up registry install,
marketplace listing or download URL. Registry publication and a one-command
bootstrap are separate distribution choices.
