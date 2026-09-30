# Decisions

## 2026-09-30 — Agent kit delivered through skills

Keep editorial intelligence in Markdown skills, schemas, creator files and
config. Hosts supply model execution; adapters share one engine. Switching hosts
must preserve creator identity, sources, IDs and history.

## 2026-09-30 — Optional connectors

Manual publishing and manual/CSV analytics complete the core loop. Typefully
enhances delivery and measurement; it does not gate onboarding or core release.

## 2026-09-30 — Simple project foundation

Use PROJECT.md for purpose/done, STATUS.md for developer handoff and DECISIONS.md
for durable reasoning. Map the foundation's inbox/work/output concepts to the
existing data model. Do not create competing sources of truth or move records
between status folders. Local AGENTS.md files are optional specialization.

## 2026-09-30 — Evaluate editorial behavior before adding complexity

Use the article's layers as a review checklist. “Jev” is a vendor implementation
of classification/routing; keep routing generic. Benchmark figures, token
multipliers and cache discounts are workload/provider-specific observations,
not architectural constants.

Add fixed fictional editorial briefs and deterministic import/lifecycle checks.
Voice, source entailment, speaker attribution and usefulness require explicit
human judgment. A response that matches a schema is not necessarily true or good.
Record first and later attempts separately; do not improve a reported first-pass
result by silently retrying. Host-wide token/dollar accounting and complete host
tool traces are not observable through the portable engine today.

## 2026-09-30 — Bounded evidence and explicit creator learning

Use source-span retrieval without requiring embeddings or another service. Keep
all cited evidence and original line numbers; add relevant context within a
configurable character budget. Exact occurrence checks prevent a quote from an
unseen speaker turn being accepted merely because the same words appear in a
supplied turn. Human review still evaluates meaning and attribution.

Persist only explicit creator feedback, with narrow scope by default and a
revision snapshot. Creator/platform preferences enter future writing tasks;
one-off content notes remain local to review. Keep pending task snapshots stable
until explicitly refreshed. Preserve retired rules and creator-edited identity.
No automatic promotion of analytics or agent critique into creator preference.

## 2026-09-30 — Continue long-source passes and revise existing content

Checkpoint large source windows with overlap, original line numbers and stable
task IDs. Freeze pass instructions and creator context so resumes do not silently
mix skill revisions. Bound model calls per invocation; make provider retries and
new passes explicit. Report processed coverage without claiming semantic completeness.

Revisions use the same platform writing contract with the original draft and
scoped feedback attached. Retain the content ID, journal before/after snapshots
and clear approval. Compare the saved base before writing; preserve newer edits,
approval and publication. A journal written before content enables recovery;
subsequent history proves an earlier applied revision without undoing new work.
Keep revision tasks separate from new-batch allocation. No remote overwrites.

## 2026-09-30 — Preserve editorial decisions as executable briefs

Use one shared planning skill/task in external and compatible-provider modes.
Give it the creator brain, source-backed candidates, history, feedback and
measurements. Save why each topic/container/job was chosen, its angle and reader
payoff, and why other supplied ideas were deferred. Pass that brief to the native
writer. Counts are ceilings; exact citations alone do not establish quality.

Keep the explicit extractive fallback labeled as heuristic. Bound candidate
context without truncating individual references; disclose omitted candidates.
Performance evidence must match the platform/job and have a known metric.
Preserve plans, task inputs and run ownership across resume/export so continuity
does not depend on old conversations. No parallel work-folder hierarchy is needed.

## 2026-09-30 — Source-backed compounding with capture questions

Replace the default three-template compound output with one portable skill/task
that develops measured winners for the creator's platforms. Keep the extractive
templates explicitly heuristic. Store proposed new value, parent provenance and
concrete missing-evidence questions in the existing idea bank. Preserve Topic +
Format + Job: a format derivative can keep its original topic.

An unresolved question blocks drafting and weekly selection. A cited resolution
preserves the question and adds captured evidence to the same idea. It is an
editorial assertion, not a guarantee of factual entailment. Do not invent source
material to open that gate. Store only the measured observation as a tentative
learning; an explanation of why something worked remains a hypothesis.

Freeze the analysis context and preallocate result IDs before writes. Recover
without replacing later creator edits or duplicating learnings. Cancellation
preserves committed work and is respected by winner watch. No separate provider
logic, new publishing permission or additional cloud dependency is needed.

## 2026-09-30 — Preserve the evidence behind voice learning

Use one shared voice skill/task to analyze the creator's own samples. Keep exact
quotes, declared medium/platform, omissions, tentative observations and unresolved
conflicts in a portable proposal. Reference creators and requested-tone adjectives
are not evidence of the creator's observed habits. Source attribution still needs
judgment; matching the schema and quote does not prove an insightful interpretation.

Apply observations in a managed VOICE.md section while preserving manual guidance.
Compare document/evidence state before writing; never replace a creator-edited
section. Journal first so retries can recover without undoing later work. Initial
onboarding authorizes evidence-based learning, while later identity changes require
creator direction. Missing samples leave voice provisional and do not block first
drafts. This extends inspectable creator memory without another database or provider.

## 2026-09-30 — Preserve useful short-source context

A native Codex writing trial exposed needless citation failures: the host read a
complete 1,256-character workshop note, but its saved writing tasks supplied only
fragments even with a 16,000-character budget. Adding evidence could also duplicate
overlapping passages. The citation checker correctly rejected unseen claims.

Reserve all required evidence, then retain referenced sources of at most 2,400
characters whole when they fit. Merge overlapping ranges and charge unique covered
characters. Keep larger-source retrieval bounded and preserve existing task
snapshots. Reading a source separately does not expand a task; attach additional
evidence explicitly and re-read before import. Record initial failed imports and
recovery separately from the final successful outcome.

## 2026-09-30 — Expand a pending compound task deliberately

Native weekly QA attempted to attach a real source passage to its compound task;
the draft-only command rejected it. Support the same explicit citation operation
for uncommitted compound tasks. Preserve every earlier excerpt, the measured
baseline, parent and creator context. Merge overlapping ranges within the frozen
source budget. Invalid or oversized evidence leaves the saved task unchanged.
Prepared, completed and cancelled analyses cannot be changed through attachment.

The same trial exposed evidence-audit prose inside routine public instructions.
Keep that material in review notes unless it changes the claim or reader's use.
Retain material scope and uncertainty, especially when discussing an unfinished
experiment. Two matched fictional writing cases exercise both sides of this
distinction. Their structural passes are not human editorial grades.

## 2026-09-30 — Update workspace intelligence separately from host commands

Reinstalling native commands did not update initialized workspace skills. That
left creators on older editorial instructions even after updating the engine.
Keep workspace customizations authoritative, but record each newly initialized
asset's accepted hash so unchanged defaults can receive future improvements.

Use one provider-independent upgrade operation with a read-only preview. Add new
assets, update unchanged tracked files, and preserve unknown/custom/deleted files.
Legacy workspaces need deliberate matching-file adoption or individual diff
review; no trustworthy historic baseline exists to infer prior ownership.
Reviewed replacement binds both current and incoming bytes. Ordinary backups and
a journal permit interrupted recovery after moving the folder, without undoing
subsequent edits. Pending tasks keep their frozen instructions; new tasks read
the updated skills. Creator memory and live settings are not migration targets.

## 2026-09-30 — Carry mining continuity in the shared task

A native long-conversation trial used host-side idea lookup and citation tools to
retain repeated evidence. A stateless provider received only the current window,
so that continuity depended on host memory/tools instead of the portable contract.

Supply a bounded shortlist of earlier topic IDs, titles, categories and saved
notes when creating each new extraction task. Same-source topics are preferred;
lexical matching supplies other candidates, and omissions are explicit. Notes
clarify an existing topic's meaning without becoming source proof. A title-only
probe missed a connection preserved by the saved notes, motivating their bounded
inclusion rather than a universal instruction to merge more ideas.

An optional existing_idea_id attaches the current passage to the supplied topic.
Preserve its editorial metadata, reject stale or out-of-context matches, and keep
the full extraction response on the task for inspection. Existing pending packets
and historical pass contracts stay unchanged. Native packet probes exercise the
contract independently of chat history; they are not human quality grades or a
general deduplication benchmark. More reused IDs can also conceal over-merging,
so independent angles and semantic judgment still need editorial review.

## 2026-09-30 — Keep experiment observations separate from interpretations

Regression tests exposed repeated learnings on unrelated saves, stale post links
after membership removal, and silent reassignment between experiments. Reconcile
the single-experiment relationship from the saved experiment record; retries use
current state, including deliberate edits after an interrupted draft import.
Maintain current interpretations in a hash-owned LEARNINGS.md section, preserving
manual and legacy text. A changed generated section requires reconciliation, not
silent replacement. No-op saves leave all data bytes unchanged.

Add one read-only measurement view over existing observations, with explicit
metric provenance, null/conflict statuses and observation ages. Separate groups
by platform, job and format. Publication date bounds use the workspace timezone;
they do not create matched observation windows or controls. Keep a creator's
recorded result/learning separate from calculated medians. Supply bounded whole
experiment records and measurement summaries to new editorial tasks, with
omissions disclosed. Pending tasks and old schemas need no migration. No new
provider, connector, database or causal inference dependency is introduced.

## 2026-09-30 — Resolve measurement conflicts before learning from winners

Four regressions reproduced a false 10x winner from conflicting same-time origins,
older/future imports replacing current idea performance, and equivalent timestamp
spellings producing duplicate observations. Use one shared latest-observation
resolver across reports, planning, experiments and compounding, removing the
experiment-specific implementation added in the previous increment.

At the latest instant, require agreement per metric. Derive rates within original
observations, then compare them; never borrow counts between origins or silently
prefer a source. Disputed values stay unknown with explicit provenance and conflict
fields. A usable rate does not resolve a disputed raw exposure count. Custom
derived values remain available; built-in rates are recomputed from raw counts.

Compare import identity by observed instant and retain IDs on correction, including
legacy equivalent-time duplicates. Repeated identical imports leave data unchanged.
Idea performance is an import-refreshed view of current measurements, never the
authority for historical queries. Add a read-only inspection command and explicit
cutoffs to winner/compound commands. Preserve existing frozen task inputs and saved
reports; data corrections do not silently rewrite an earlier editorial decision.

## 2026-09-30 — Test the distributable, not only its source checkout

The previous CI installed from source and ran tests in the checkout. That could
miss packaging omissions. Build the sdist first and its wheel second, compare all
runtime payload bytes, require source guides/tests/CI, and retain artifact hashes.
Run the complete suite and offline smoke against a non-editable wheel with local
imports disabled. The stricter Python 3.9 check exposed dependencies supplied by
the developer user site; its isolated QA environment now owns its dependencies.

Use one read-only CI workflow to build once, test the same wheel on both supported
Python versions, and retain evidence. A package artifact alone is not a passing
release: both test jobs and the final gate must pass. Tagged candidates require
version agreement and an existing clean tag at HEAD. No automated public release
or invented install endpoint is introduced; the repository destination and real
creator review are still required. Local integrity and fictional smoke results
do not establish native host acceptance or editorial usefulness.

## 2026-09-30 — Ship the repository as an early testing release

The user made the first milestone an official repository that can be pushed and
marketed for testing. Put the creator journey and a Codex quick start at the
front, move the detailed CLI reference into docs, and provide a short trial plus
public feedback templates. Supply usable launch copy with evidence limits.

Prepare a reviewed local Git history so the repository can be cloned and pushed.
Do not invent a remote, marketplace install or hosted CI result. Real creator
feedback remains required for broader product claims, but it is an outcome of
this testing release rather than a prerequisite for inviting testers. Keep the
engine, Typefully-optional path and creator data boundaries unchanged.
