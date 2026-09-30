# CONTENTMAXXING release QA — 2026-09-30

This is a historical QA log. Counts, paths and Git state below describe the
candidate tested in each section. For the current testing release, start with
[STATUS.md](../STATUS.md), [VERIFICATION.json](../VERIFICATION.json) and the
[creator trial guide](BETA_TEST.md). A real creator pilot evaluates the early
testing release; it is not a prerequisite for inviting creators to try it.

## Subsequent mining/revision increment

Long transcripts now use resumable bounded windows; kickoff and progress track
the complete pass. Local draft revisions preserve IDs, record before/after
history and return to review. Twenty-seven new regression tests cover coverage,
original citations, crash recovery, newer-edit conflicts, older workspaces,
explicit restarts, and export/resume. The current Python 3.11 suite passes 145
tests; Python 3.9 passes 144 with one expected skip. All 19 skills validate.
The final installed-wheel smoke passes offline outside the checkout, including
long-source resume and same-ID revision/history. See `docs/MINING_AND_REVISIONS.md`.
The fictional demo completes three windows and a same-ID revision. Native host
acceptance and real editorial validation were not repeated for this increment.

## Subsequent retrieval/feedback increment

Local source search, bounded draft excerpts, explicit evidence enrichment of
pending tasks and persistent scoped creator feedback now share the core engine.
Sixteen regression tests cover budgets, original citations, repeated quotes at
unseen lines, legacy tasks, scoped preferences, snapshots, retirement and ZIP
portability. `examples/feedback_loop.py` illustrates the flow with fictional
scripted responses and reviewer direction, not real editorial acceptance.
The full suite passes 118 tests on Python 3.11 and 117 plus one expected skip on
3.9 with the wheel installed. All 18 skills validate. The installed wheel smoke
passes offline outside the checkout, including the feedback/export path.
See `docs/RETRIEVAL_AND_FEEDBACK.md`. Native host sessions below predate this
increment; no active creator pilot was changed or reinstalled.

## Subsequent evaluation/foundation increment

After the native acceptance described below, the kit added repository foundation
documents, a six-case editorial eval lab and parent-post context for derivative
writing. That increment passed 102 tests on Python 3.11 (101 plus one skip on
3.9). The example eval's six mechanical results pass; human grades remain pending.
See `docs/EVALUATIONS.md` and `STATUS.md`. The native sessions below certify the
earlier candidate; they were not repeated for the new evaluation skill. The
earlier release artifacts remain separate from this increment's build.

## Verdict

**Ready for a guided Codex beta from the checkout or a verified wheel. Not yet
approved for a broad, frictionless public launch.** The engine and installable
skill bundle pass the local checks below, including fresh Codex CLI discovery
and both onboarding conversations with fictional creators. A real editorial
pilot and a published versioned install entrypoint are still outstanding.

The product is an installable content mastermind powered by the creator's current
AI, modular skills, inspectable creator memory and shared workflows. **Typefully
is optional and is not a release gate.** Manual publishing plus CSV/manual
measurements completes the same Capture → Create → Compound loop. No connector
or second model API key is needed for the default host-agent path.

## Verified

| Area | Result | Evidence and limit |
| --- | --- | --- |
| Automated suite, Python 3.11 | Pass | 91 tests, including eight release-QA regression tests |
| Python 3.9 compatibility | Pass | 91 discovered, 90 passed, one TOML test skipped because `tomllib` is 3.11+; existing system dependencies |
| Fresh Python 3.11 environment | Pass | Wheel and dependencies installed into a new virtual environment; `pip check` clean |
| Packaged core loop with no API keys | Pass | `scripts/release_smoke.py` uses the installed package outside the checkout, removes configured API keys and prohibits socket connections |
| Guided interview path | Pass | Welcome → profile/source → mining → selection → five external-task drafts → review |
| File-dump path | Pass | Preserved documents → cited profile proposal → explicit simulated confirmation → ideas → three review drafts; unsupported files reported |
| Performance loop | Pass | Simulated manual publication → five fictional CSV measurements → 10× save-rate winner → three compound opportunities |
| Creator ownership | Pass | Voice included in tasks; export/restore preserves it; uninstall preserves creator records; repeat kickoff does not create another batch |
| Review boundaries | Pass | Drafts remain NEEDS_REVIEW; editing invalidates approval; native weekly/create flows do not publish |
| Native host adapters | Format-tested | One catalog, 18 actions plus umbrella; Codex/Claude/Cursor skill validation and Gemini TOML tests; generic Markdown entrypoint |
| Fresh Codex CLI onboarding | Pass after fixes | Native skill discovery, three-question interview, file-derived profile confirmation, provisional voice and three actual model-written review drafts per path; see [acceptance evidence](CODEX_ACCEPTANCE.md) |
| Fresh Codex progress/resume | Pass | Existing drafts reopened with the reproduced stray result files present; all creator data remained byte-for-byte unchanged |
| Fresh Codex next | Pass | Displayed the saved review batch and requested editorial input; no file changes, duplicate drafts or implicit approval |
| Packaging | Pass | Wheel includes shared skills, schemas, commands and current retro PNG; source archive includes guides, demo scripts and fictional fixtures |
| Optional publishing connector | Mock-tested | Missing credentials preserve local drafts; review gates, uncertain actions, reconciliation and response mappings covered; no live Typefully account used |
| Welcome delivery | Text fallback verified | First host session omitted the HUD; corrected instructions displayed it in subsequent interview and file-dump sessions. Desktop PNG rendering remains unverified |

The smoke responses are literal fictional fixtures. They demonstrate persistence,
contracts and routing, **not** the quality of an LLM's writing or autonomous
judgment. The separate native sessions used actual model-written task responses;
their fictional persona is not a substitute for a real creator's editorial
feedback. The current user's active Codex pilot workspace was not altered.

## Bugs reproduced and fixed

| Priority | Failure before fix | Change |
| --- | --- | --- |
| P1 | A provider-side interruption after writing content could erase its planned result ID; retry produced a second draft | Preserve the latest persisted task checkpoint when recording an error |
| P1 | Retrying an incomplete task could overwrite subsequent creator edits and approval | Existing saved content is authoritative during task recovery, including revision, approval and creation time |
| P1 | Interrupted onboarding left profile.json present with missing creator documents, preventing retry | Write profile.json only after all initial brain documents are saved |
| P1 | Workspace export followed a symlink to a file outside the creator folder | Reject symlinks throughout exported files before creating the archive |
| P1 | A failed export destroyed the previous backup at the selected destination | Build the ZIP in a sibling temporary file and replace the destination only after success |
| P2 | Model URL prefix checks accepted HTTP hosts such as localhost.example.test and user-info tricks | Parse and validate scheme, exact loopback hostname, credentials and port |
| P1 for release | Source archive omitted guides, examples and test fixtures; `.gitignore` hid the fictional creator fixture | Add an explicit source manifest, narrow the ignore patterns and include README in package metadata |
| P2 | Welcome instructions could repeat invisible local-image previews | Explicit one-attempt fallback to the portable text HUD |
| P1 | Native agent saved result JSON beside task records; resume tried to parse the results as tasks and failed on a missing ID | Read canonical record filenames only, retain other files, report corrupt record identities and direct working results to a separate folder |
| P2 | Fresh host misresolved a core path and omitted the HUD | Anchor paths to the instruction's containing directory and require a visible image or fenced text banner |

The eight executable regression tests were run against the prior behavior and
failed before the fixes; they now pass. CI also runs the installed-package core
smoke test so a checkout-only success does not count as installation success.

## Remaining release acceptance

1. **Real editorial pilot:** check positioning, learned voice, useful topic
   extraction and first drafts with a few creators. Verify that uncertain claims
   remain flagged and creator feedback improves subsequent work. Exact citation
   checks do not prove that every natural-language claim follows from its source.
2. **Release distribution:** create a reviewed commit/tag and a real public
   install entrypoint. This checkout currently has no commits or configured Git
   remote. Do not advertise a guessed registry install command. Run CI against
   that release commit and publish only the verified artifacts.

Fresh Codex CLI discovery and both first-run paths are covered by
[the native acceptance check](CODEX_ACCEPTANCE.md). Desktop PNG rendering is
not certified. Claude Code, Cursor and Gemini have generated/tested file formats, but have not
been exercised in fresh host sessions here. Advertise them as unverified adapters
until those sessions pass. Linux/Windows execution was not performed locally;
the configured Linux CI has not run against a published commit.

Typefully account certification can happen independently after core beta release.
Live posting is not part of this QA. Local editing after a remote draft exists
and reconciling a changed remote body remain restricted; do not claim a complete
bidirectional remote editing workflow. Media/QRT upload, direct TikTok/Substack
article publication and hosted recurring execution remain outside v1 scope.

## Reproduce

```sh
python -m unittest discover -s tests -v
python examples/demo.py --workspace /tmp/contentmaxxing-qa-demo-UNIQUE
python examples/intake_demo.py --workspace /tmp/contentmaxxing-qa-intake-UNIQUE
python examples/journey_demo.py --workspace /tmp/contentmaxxing-qa-journey-UNIQUE
```

Build the wheel and source archive, install the wheel into a separate environment,
then run the smoke script with that environment's interpreter:

```sh
python -m pip install build
python -m build
python -m venv /tmp/contentmaxxing-qa-clean-UNIQUE
/tmp/contentmaxxing-qa-clean-UNIQUE/bin/python -m pip install dist/contentmaxxing-0.1.0-py3-none-any.whl
/tmp/contentmaxxing-qa-clean-UNIQUE/bin/python scripts/release_smoke.py
```

`docs/QA_REPORT.md` and `VERIFICATION.json` are the release evidence record.
The offline tests do not register a global skill, modify the active creator
pilot, contact a publishing service or send content to a model API. The separate
native acceptance sessions use the signed-in Codex host with fictional material.
