# Project status

Earlier native Codex CLI onboarding passed the 2026-09-30 QA.
Both onboarding paths produced review drafts, and navigation preserved saved
creator data. That host acceptance predates the increments below. See
`docs/QA_REPORT.md` and `docs/CODEX_ACCEPTANCE.md`.

## Latest completed increment

The initial repository commit is `954961e`. A fresh clone installed successfully
using the README steps, registered 19 Codex actions, passed doctor and reached
WELCOME. Its exact candidate passed 268 installed tests on Python 3.11 and 267
plus one expected skip on Python 3.9; the installed offline workflow and core demo
also passed. All 102 runtime files matched the artifact inventory. See
`docs/TESTING_RELEASE.md`. No public remote or hosted CI run is claimed.

The repository now has a creator-facing testing-release README, a first-session
walkthrough, feedback/bug templates, contribution guidance, a changelog and
launch copy. The former long README remains as `docs/ENGINE_REFERENCE.md`.
The package manifest and verifier include the new root/community files.
Historical QA paths no longer expose the developer's home directory; local-only
evidence is identified explicitly. Relative links in the new guides resolve.

The current first milestone is a push-ready repository that invites creator
testing. Real creator voice/usefulness feedback is the purpose of that testing,
not a gate that prevents inviting it. Publication still needs a chosen remote
and actual hosted CI. See `PROJECT.md` and `docs/LAUNCH_KIT.md`.

## Previous release-pipeline increment

Release preparation now builds a wheel from the source archive and verifies
packaged runtime files, source guides/tests/CI, metadata versions and hashes.
Tagged candidates must match the version and a clean existing tag at HEAD.
Local builds are explicitly labeled; no publication or Git state is created.
CI builds once, tests that exact installed wheel on Python 3.9 and 3.11 with
checkout/user imports disabled, and retains per-runtime evidence. Its prepared
YAML has been parsed locally; it has not run on GitHub because there is no remote.

Eight new regressions cover missing skills/HUD, omitted source tests/CI, version
drift, stale or unexpected files, tag provenance and installed-file mismatches.
The candidate's installed Python 3.11 suite passes all 268 tests; Python 3.9 passes
267 with one expected skip. Both runtimes pass the offline workflow and core demo.
The stricter Python 3.9 run exposed user-site dependencies in the old QA environment;
dependencies are now installed inside it and system/user fallbacks are disabled.
Initial failure logs are retained. The license metadata also uses the current SPDX
format. See `docs/RELEASING.md` and `VERIFICATION.json` for artifacts and scope.

This does not certify real creator quality, other native hosts or a public
release. The active creator pilot remains untouched.

## Previous analytics increment

Analytics now resolves latest measurements consistently across reports, editorial
planning, experiments and compounding. Conflicting values stay unknown with all
original record IDs exposed; agreed metrics remain usable. Rates are computed
inside each observation, never from counts merged between origins. Older and
future imports no longer replace current idea performance, equivalent timestamp
spellings reuse the same observation, and identical imports leave data unchanged.

`analytics show` exposes the resolved view and original records. Winner and compound
commands accept an explicit cutoff. New plans carry conflict/metric status and
provenance; existing task inputs and saved reports retain their original evidence.
See `docs/ANALYTICS_HISTORY.md`.

Four regression cases failed before the fix, including a false 10x winner from
same-time disagreements. Twelve new cases cover order, timezones, conflicts,
custom metrics, missing values, frozen tasks and CLI cutoffs. All 260 tests pass
on Python 3.11; Python 3.9 passes 259 with one expected skip. The installed wheel
passes the offline workflow including conflict inspection, correction and export.
The original source-to-compound demo also passes. This is deterministic engine QA;
no new native host or real creator quality trial was run for this increment.
Active creator pilot data is untouched.

## Previous experiment increment

Experiment learning now has a read-only measurement view with sample counts,
metric provenance, missing/conflicting observations and observation ages. New
editorial tasks receive bounded summaries separately from recorded interpretations.
Saves reconcile post membership, preserve manual notes, update current experiment
learnings and leave data unchanged when repeated. Interrupted saves/draft imports
preserve deliberate later edits and recover their links.

Thirteen regressions cover those paths, metric/date boundaries, nulls, conflicting
origins, frozen planning context and export/restore. All 248 tests pass on Python
3.11; Python 3.9 passes 247 with one expected skip. The installed wheel passes the
offline workflow, including experiment measurement/idempotence/export.

A fresh native Codex session reviewed six fictional posts, used the new measurement
command and saved an interpretation plus next test. It reported the known medians
and unequal ages, excluded missing data, and avoided a causal conclusion. Only the
existing experiment and current learning notes changed; a weekly report was added.
One PATH lookup failed before the runtime fallback succeeded. No creator quality
grade or real audience evidence is claimed. See `docs/EXPERIMENTS.md` and
`docs/NATIVE_EXPERIMENT_TRIAL.md`. The active pilot is untouched.

## Previous mining increment

Transcript mining now carries continuity across stateless calls: a bounded view
of prior topic IDs, titles, categories and saved notes, plus an optional existing
idea reference in the extraction contract. New evidence attaches to the same idea
without changing its saved editorial choices. Stale/out-of-context targets are
rejected; pending packets and historical pass contracts retain their snapshots.

A native Codex trial mined a 9,800-character fictional conversation across three
windows into 21 topics with 31 citations and four article candidates. Repeating
the completed pass changed no data. It predates the new task context and used
host-side citation tools. Three fresh self-contained packet probes then tested
the new contract: no prior context reused no IDs; titles reused four; titles plus
bounded notes reused six. All imported successfully, preserved metadata and
remained idempotent. Counts alone do not establish the correctness of a merge;
all probes remain NEEDS_HUMAN_REVIEW. See `docs/NATIVE_MINING_TRIAL.md`.

All 235 tests pass on Python 3.11; Python 3.9 passes 234 with one expected skip.
The installed wheel passes the offline workflow smoke, including evidence
attachment to existing topics, upgrades and export/restore. Ten new regressions
cover context limits, stale matches, metadata preservation, interrupted import,
legacy contracts and moving a pending task. The creator pilot is untouched.

## Previous upgrade increment

Existing workspaces can now receive improved intelligence through `upgrade`.
Initialization records accepted asset hashes; upgrades preview changes, update
unchanged defaults, add new assets and preserve custom, deleted or untracked
files. Legacy folders can adopt exact matches deliberately and review remaining
diffs. Reviewed replacement binds both file versions and keeps before-files.
Interrupted upgrades recover from portable journals without replacing newer edits.

Fourteen local regressions verify these paths, including actual engine behavior:
new writing tasks receive updated instructions while pending tasks, creator data
and root settings stay unchanged. All 225 tests pass on Python 3.11; Python 3.9
passes 224 with one expected skip. The installed wheel passes the offline smoke.
A replay on an isolated copy of the earlier fictional weekly workspace updates
four reviewed stock files, preserves its custom template and all 77 data files,
and changes nothing on repeat. The original QA folder is unchanged.
See `docs/WORKSPACE_UPGRADES.md` and `VERIFICATION.json` for evidence.
This increment does not repeat native host
discovery or establish real creator writing quality. The active pilot is untouched.

## Previous weekly increment

Native weekly QA now covers analytics → one saved editorial plan → four native
review drafts → three measured-winner follow-ups. Eleven new topics were mined;
the planner left three slots unfilled and retained concrete capture questions.
Repeating the same completed run and plan changed no creator data. The trial
used fictional sources, metrics and review preferences, not a real creator pilot.

An observed failure led to compound-task evidence attachment through `tasks cite`.
It preserves the original comparison and earlier excerpts, checks the frozen
budget and closes after import preparation. Four new regressions cover source
addition, rejection without changes, lifecycle gates and export/restore; three
failed before the fix. All 211 tests pass on Python 3.11. Native weekly acceptance
predates this fix; its failed call remains in the trace. See
`docs/WEEKLY_CREATOR_TRIAL.md` and `VERIFICATION.json` for the follow-up validation.

Shared writing guidance now keeps internal audit notes out of public prose unless
they change the claim or its use. A matched two-case native comparison preserved
unfinished-test uncertainty while moving an irrelevant measurement caveat into
review notes. All four attempts remain NEEDS_HUMAN_REVIEW; no human grades exist.
The separate `reader-scope-v1` suite preserves these briefs for future comparisons.

## Previous increments

Fresh native Codex CLI sessions now exercise the voice command after onboarding,
real model-written X/LinkedIn/TikTok drafts, a same-ID X revision, X-only feedback
and fresh-session navigation. The fictional bookbinding persona supplied three
writing samples and a workshop note. All four final drafts remain NEEDS_REVIEW;
the TikTok explicitly requires filming. The active creator pilot was untouched.

The trial exposed unnecessary short-source clipping and duplicated context.
Retrieval now preserves whole short sources when they fit after reserving all
required evidence, and merges overlapping ranges. Two regression cases failed
before the fix; all 19 retrieval/feedback tests now pass. Existing task snapshots
and citation gates are preserved.

The corrected X keeps its ID at revision 2. The next X task receives the platform
preference but not the one-off correction. LinkedIn, TikTok and creator documents
remain byte-identical; a fresh progress session leaves all 40 data files unchanged.
See `docs/NATIVE_CREATOR_TRIAL.md` for evidence and the initial recoverable failures.
This is fictional host acceptance, not a real creator quality grade or a repeated
onboarding trial.

At that increment: 207 tests on Python 3.11; Python 3.9 discovered 207, with 206 passing
and one expected skip. The installed candidate wheel passes the offline smoke
outside the checkout. Final artifact details are in `VERIFICATION.json`.

Voice learning now uses a shared analysis task with exact sample quotations,
declared medium/platform scope, tentative or recurring observations, unknowns
and conflicts. Link-only and duplicate samples are excluded; whole-sample budgets
disclose omissions. Reference creators and desired tone are not observed voice.

`voice learn` saves a reviewable proposal; `voice apply` preserves manual VOICE.md
guidance and rejects stale profile, feedback, evidence or edited generated sections.
The before/after journal recovers interrupted writes without undoing later edits.
No samples means provisional voice, not blocked drafting. Existing pending drafts
keep their frozen context. Native host entrypoints include the voice command;
onboarding instructs the host to learn from supplied samples before draft tasks.
See `docs/VOICE_LEARNING.md`.

The fictional illustration at `demo-output/voice-learning-final/` applies a
tentative sample-backed observation while preserving an explicit creator
correction, then writes an X draft in NEEDS_REVIEW with that context. Responses
are scripted fixtures, not a real creator voice trial. No active pilot was changed.

At that increment: 204 tests on Python 3.11,
Python 3.9 compatibility, all 19 core skills and 20 generated entrypoints per
native host (19 actions plus umbrella), and offline installed-wheel smoke.
The later native trial above exercises the voice command in a fresh host session.
Build artifacts: `dist/voice-increment/`.

Compounding now uses one shared external/model task to develop measured winners
for the creator's platforms. It freezes the parent, metric comparison, creator
context, existing native follow-ups and bounded original/related evidence.
Opportunities preserve new value, rationale, native Topic + Format + Job and
specific missing-evidence questions. Drafting and weekly selection reject
unresolved development gaps; cited resolutions unlock the same idea.

Imports preallocate IDs and validate before writes. Recovery preserves later
edits, explicit cancellation preserves committed ideas, and winner watch resumes
saved tasks without duplicate opportunities or automatic paid retries. Empty
assessments are valid. A new native format can keep the original topic. Measured
observations are stored separately from hypotheses about why something worked.
See `docs/COMPOUNDING.md`.

At that increment, 186 tests passed on Python 3.11; the installed wheel on Python 3.9 passed 185 with
one expected skip. All 19 skills validated. The wheel smoke passed offline outside
the checkout, including compound tasks/gaps, planning/briefs, mining, revisions,
feedback and export/restore. See VERIFICATION.json. Build: `dist/compound-increment/`.

The illustration at `demo-output/compound-loop-final/` develops an X winner into
an X utility idea and a TikTok story idea. The story is blocked until a captured
answer resolves its gap, then becomes a native review draft. Repeating the
analysis creates no duplicate ideas. All creator answers, metrics, publications
and model responses in this demo are scripted fictional fixtures.

The preceding editorial-planning increment retains saved decisions and writing
briefs across weekly resume; see `docs/EDITORIAL_PLANNING.md` and the illustration
at `demo-output/editorial-planning/`.

The previous source-continuity increment remains available: bounded resumable
mining, same-ID revisions with before/after journals and scoped creator feedback.
See `docs/MINING_AND_REVISIONS.md` and `demo-output/mining-revision-loop/`.

The six-case editorial lab remains available, plus a separately versioned
`evals/compounding-v1.json` case with a reproducible measured winner. The engine
checks imports and lifecycle; a person must judge usefulness and evidence support.
The earlier `demo-output/evaluation-demo/` has no human grades and is not
a blind benchmark of these increments. Full onboarding acceptance predates these
increments; the later trial covers post-onboarding work. No active creator pilot
was changed.

Next quality work: matched creator-facing trials for topic coverage, useful
platform writing, revisions and weekly editorial decisions. Improve behavior
from observed failures; mechanical coverage alone is not proof of a strong
content engine. The broad powerhouse objective remains unproven.

## Release work remaining

Real creator editorial pilots, a reviewed versioned public install endpoint and
an actual passing run of the prepared release CI. Other hosts and desktop PNG rendering need separate acceptance.
Typefully certification is independent and optional.

## Resume work

Read `AGENTS.md`, this file and `DECISIONS.md`; inspect the affected implementation
and current tests. Creator workspace `progress` is read-only and remains the
authoritative way to derive its next action. This project status is a developer
handoff, not a duplicate creator task database.
