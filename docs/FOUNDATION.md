# Applying the project foundation and agent layers

The project foundation provides orientation. The engineering layers describe
the behavior that must hold up inside it. They complement each other.

| Layer | CONTENTMAXXING application | Current boundary |
| --- | --- | --- |
| Context | Load the relevant skill, creator brain, scoped feedback and bounded source windows; give derivative/revision writers their actual prior post | Lexical retrieval is not semantic search; source-window budgets do not bound the whole task's tokens |
| Execution | Deterministic intake, statuses and checkpoints; the host supplies editorial decisions | Host-wide turn and spending limits belong to the host; eval submission budgets are enforced locally |
| Routing / triage | Command catalog, source-type inventory, duplicate detection and intent-to-skill routing | Add a classifier only if a labeled workload justifies it; no Jev dependency |
| Tools and boundaries | One shared engine, schema/citation checks, review gates and optional publishing adapters | A host with full filesystem access can bypass local conventions; the kit is not an OS sandbox |
| Evaluations | Fixed fictional briefs, real engine imports, per-check results and explicit human rubrics | Editorial judgment and full host traces are not replaced by schema validation |

Root `PROJECT.md`, `STATUS.md` and `DECISIONS.md` make the development project
resumable without its old chat. `PROJECT.md` maps inbox, work stages, resources
and outputs to the existing repository and creator data model. `AGENTS.md`
supplies shared rules. Add local rule files only when an area's behavior needs
them; do not create a deep folder hierarchy to anticipate imaginary complexity.

These root documents are currently repository handoffs. Creator identity remains
in the Brand Brain and Voice, and creator progress is derived from saved records.
We have not created a parallel set of task folders or a manually maintained
creator STATUS file that can silently contradict the engine.

The supplied article is useful as a checklist, but its sponsor implementation
and benchmark numbers are not requirements. TypeSafe describes Jev as a
structured decision model; its schema guarantee does not establish factual
correctness. See [the primary announcement](https://typesafe.ai/blog/introducing-system-one-models-and-jev).
Anthropic's [context engineering guidance](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)
and [evaluation guidance](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents)
support selective context and combining code-based checks with human judgment.

Bounded source retrieval and explicit scoped creator feedback now have a working
CLI and shared task contract; see [the guide](RETRIEVAL_AND_FEEDBACK.md).
Resumable large-source mining and revisions with before/after history now share
the same engine; see [the continuity guide](MINING_AND_REVISIONS.md).
Weekly editorial decisions now persist the angle, payoff, evidence and selection
reason in a plan that writers and later sessions reuse; see
[editorial planning](EDITORIAL_PLANNING.md). Deferrals preserve why an idea was
left for later, without turning them into permanent creator beliefs.
Measured winners now produce source-backed follow-up briefs and capture questions
through the shared compound skill. Resolutions preserve the question and add
cited evidence to the same idea; see [compounding](COMPOUNDING.md).
Voice analysis now has saved sample evidence, reviewable proposals and safe
application to the creator's document; see [voice learning](VOICE_LEARNING.md).
This records the basis for an inference without promoting it into unquestioned
identity. The next quality milestone remains matched real-creator trials of voice,
usefulness, mining completeness and application of editorial feedback.
Hosted orchestration, extra model vendors and a dashboard should follow an
observed need.
