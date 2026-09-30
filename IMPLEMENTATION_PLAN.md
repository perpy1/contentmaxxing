# CONTENTMAXXING v1 implementation plan

The engine is the product. Preserve Capture → Create → Compound and Topic + Format + Job.

Current first milestone: a push-ready official repository for an early creator
testing release. Complete the public quick start, trial/feedback path, launch
copy and reviewed Git baseline; verify a clean clone and distributable. The
broader real-creator quality work follows that invitation. See `PROJECT.md`.

## Installable agent distribution

Keep the current engine and make it usable inside a creator's existing AI. The
first distribution slice is install → native start command → saved kickoff →
first reviewed batch. A single command catalog and Markdown procedures generate
Codex/Claude Code skill entrypoints, with thin Cursor/Gemini and generic adapters.
Support project and user scopes, repeatable installation, ownership-aware update
and uninstall, and read-only installation diagnostics. Keep creator data separate
from installed resources. Test generated formats, preservation, portability,
and the full installed kickoff contract before documenting release readiness.
Prioritize real Codex/Claude Code discovery testing before a public release;
do not equate generated-file validation with a verified host session.

## Engine implementation

The creator-facing package is an **installable agent kit, delivered through
skills**. A new welcome offers curated interview or mega file dump. Bulk intake
preserves supported sources, reports exceptions, and validates exact citations
for a proposed creator profile. The creator confirms/corrects that proposal
before it becomes identity. Both routes converge on the existing content loop.
The HUD ships as a real PNG with a terminal fallback; host UI replacement is
outside this package's control. Legacy launches retain their existing progress.

1. **Vertical slice:** initialize a portable workspace; collect a creator profile; write Brand Brain, Voice, Pillars and Offer; preserve a transcript; mine cited topic candidates; deduplicate and persist ideas; select ideas; draft X content into NEEDS_REVIEW; record approval and publication; import analytics; score winners against a matched baseline; return distinct compound opportunities to the idea bank. Test and demonstrate this before extending the engine.
2. **Portable intelligence:** one orchestrator, focused Markdown skills, JSON schemas, framework templates, external-agent task/result contracts, and a thin OpenAI-compatible adapter. An explicitly labeled extractive provider makes the slice usable offline without pretending to be a generative model.
3. **Integrations:** typed publishing protocol, filesystem/manual export, strict CSV import, and Typefully v2 adapter with injected transport and mocked response tests. Live integration requires credentials; unsupported account capabilities produce explicit errors.
4. **Recurring work:** configurable YAML workflows; persistent resumable weekly runs; analytics first, then native platform batches, article selection, Substack and winner watch. No scheduling/publishing inside the editorial workflow. Track experiments and learnings.
5. **Delivery:** installable CLI, fictional fixtures, executable demo, documentation, full test suite and packaging verification. Defer dashboard, hosted execution, media ingestion/OCR and provider-specific SDKs.

Storage is ordinary JSON records and Markdown/source files, with atomic replacement and a portable single-writer lock. There is no hidden database required to move a creator folder. IDs and references survive export and moves. Schemas validate every persisted core record. Model and external-agent outputs share the same validation path.

Review is mandatory by default. Source attribution can be checked mechanically; truthfulness of generated arguments and voice still requires human review. Missing metrics stay unknown. Reports describe small-sample findings as tentative.
