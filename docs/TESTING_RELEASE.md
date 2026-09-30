# Testing-release readiness — 2026-09-30

The repository is ready to push and invite guided creator testing. The engine,
skills, quick start, first-session trial, feedback templates and launch copy are
committed. A public remote, download URL and hosted CI run are still separate
publication steps. This readiness applies to the early testing milestone, not
to proven creator voice quality or audience outcomes.

## Verified from a clean clone

Source commit: `954961e66c5256e017da1a508a79021ac946051b`.
This report and the accompanying status updates are documentation-only successors.

| Check | Result |
| --- | --- |
| Fresh local clone of committed files | Passed; no ignored development files required |
| README installation in a new Python 3.11 environment | `pip install .` passed with isolated build dependencies |
| Codex command installation | All 19 actions registered |
| Installation doctor | Integrity check passed |
| First CLI kickoff | Reached WELCOME in a separate empty creator folder |
| Wheel built from source archive | Passed |
| Packaged files and metadata | Passed; includes community files, skills and welcome image |
| Installed bytes | All 102 runtime files match the candidate on Python 3.11 and 3.9 |
| Installed suite, Python 3.11 | 268 passed |
| Installed suite, Python 3.9 | 267 passed, one expected tomllib skip |
| Offline installed workflow | Passed; scripted fictional responses, no model or connector calls |
| Source-to-compound demo | Passed with fictional sources and analytics |
| Dependency check | No broken requirements |
| New documentation links | Relative targets resolve |
| Commit inventory | 211 files reviewed; creator data, environment files and generated evidence excluded |

The initial sandboxed install could not reach the dependency index. After
network access was allowed for this disposable environment, the same documented
install succeeded. That environment issue was not hidden by changing the
installation command. This trial did not start a new native AI conversation;
earlier Codex host acceptance remains documented separately.

## Candidate files

The tested local candidate and logs are retained under ignored
`dist/testing-launch/` and `dist/testing-launch-evidence/` in the maintainer
checkout. They are not promised as files in a public clone. The wheel hash is:

```text
738ddfd90bcae41bb15f3c4fc9147fee61a40dd02db6ac60e450041c90483261
```

`ARTIFACTS.json` records the source commit and both archive hashes. Reproduce the
build and installed checks using [RELEASING.md](RELEASING.md); hosted CI will
retain the actual release candidate and per-runtime evidence when it runs.

## Invite testers

Use [the launch kit](LAUNCH_KIT.md) to introduce the testing release and
[the first-session walkthrough](BETA_TEST.md) to collect useful feedback.
The next product question is whether creators recognize their voice and want
to use the drafts. Real creator feedback is explicitly still pending.
