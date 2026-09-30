# Evaluate CONTENTMAXXING changes

The engine tests establish persistence, contracts and lifecycle behavior. The
editorial lab asks a different question: how does a particular AI, using a
particular skill version, handle the same creator briefs?

The lab runs locally, uses the shared engine and requires no publishing service,
model API or paid evaluation platform. Your chosen host writes the responses.
Another host can take the same folder and continue the trial.

## Run a trial

```sh
contentmaxxing evals prepare --output ./eval-runs/baseline --label codex-baseline
```

Ask your AI: “Run the packets in this evaluation folder. Submit your responses,
then show me the editorial checks that need my judgment.” The installed
`agent-evaluation` skill explains the procedure. It is also available from the
orchestrator when you ask to evaluate a kit change; there is no new required
step in ordinary creator onboarding.

The six initial cases test distinct topic mining, speaker attribution, missing
proof, a different creator's voice, a TikTok screen demonstration and additional
utility when compounding. All sources and creators are fictional. The compound
case starts with a seeded parent post; it tests writing a derivative, not winner
selection or measured performance.

Each `cases/<id>/packet.json` contains a brief and the same task contract used
by the production engine: selected instructions, creator context, sources and
output schema. The host should read one packet at a time, write its result under
`responses/`, and submit it:

```sh
contentmaxxing evals submit --run ./eval-runs/baseline --case missing-proof --file ./eval-runs/baseline/responses/missing-proof.json
contentmaxxing evals report --run ./eval-runs/baseline
```

Submission uses a temporary copy of the frozen case workspace. The real engine
checks schema/citations/platform limits, produces review-only records and checks
that importing the same response again does not duplicate or change records.
The original case remains unchanged. Invalid responses remain visible as failed
attempts instead of disappearing into retries.

## Human editorial checks

`contentmaxxing/evals/compounding-v1.json` supplies a separate measured-winner
case. Prepare it with `--suite <path>`. Its frozen fictional observations establish
a 10× saves comparison against four peers through the real engine. The AI must
develop useful angles while distinguishing available evidence from unanswered
questions. Empty opportunities are allowed by the contract and judged by the
human rubric, so the evaluation does not reward filling a quota. See
[compounding](COMPOUNDING.md).

`contentmaxxing/evals/reader-scope-v1.json` adds two cases from native weekly QA:
a usable notebook-record post and an unfinished saves experiment. Prepare with
`--suite <path>`. The first asks whether evidence-audit notes distract from a
routine practice; the second checks that material uncertainty remains visible.
These are human editorial rubrics, not phrase bans or automatic style grades.

Every case has one focused human rubric. The report shows each automatic check
and the rubric separately. A mechanical pass remains NEEDS_HUMAN_REVIEW until a
person has reviewed the actual response and its source.

```sh
contentmaxxing evals grade --run ./eval-runs/baseline --case missing-proof --verdict fail --reviewer "Creator" --note "The source says the change has not been measured; the draft claims a result."
```

Agents may record feedback supplied by the person. They must not label their
own assessment as a human review. The CLI records a declared reviewer and an
evidence-based note; it cannot authenticate who gave that judgment. A human pass
does not override a failed automatic check or approve any content for publishing.

The lab deliberately demonstrates the limit of citation checking: a fabricated
claim paired with an exact but irrelevant quote can pass structural validation.
Entailment, voice, attribution and usefulness still need editorial judgment.
There is no automatic universal quality score or uncalibrated model judge.

## Compare a skill or model change

Prepare another labeled run. Use another host/model, or supply changed Markdown
intelligence with `--intelligence ./my-creator/.contentmaxxing`. That option
copies skills, prompts and templates; it preserves the same fixtures and grader.

```sh
contentmaxxing evals prepare --output ./eval-runs/candidate --label changed-voice-skill --intelligence ./my-creator/.contentmaxxing
contentmaxxing evals compare --baseline ./eval-runs/baseline --candidate ./eval-runs/candidate
```

Comparison uses **first attempts** and individual check results. Later attempts
and their own reviews remain in the run report. Unrun/unreviewed cases are
explicitly incomplete. The suite and grader/engine hashes must match; to compare
skills after changing the engine, prepare both matched trials using that engine.
Instructions may differ, and their hashes are recorded.

The default submission budget is one attempt per case. Set `--max-attempts 2`
when deliberately evaluating revision behavior. Retrying the identical latest
response is idempotent. A changed response needs a fresh human review. No hidden
retry can turn a failed first attempt into a reported first-pass success.

## Grow from actual failures

Start with the bundled `contentmaxxing/evals/editorial-v1.json`, governed by
`schemas/eval-suite.schema.json`. Add anonymized, consented source material, a
specific brief and one focused rubric. Use `--suite <file>` to prepare that set.
Do not put real private creator files into the public repository. Keep changed
suites separately versioned and review their grading expectations.

`run.json` retains raw responses, result records, checks, reviews and evaluator
events. `suite.json` and the frozen case files preserve the inputs. Moving the
folder preserves the trial; relative paths and stable record IDs remain valid.
Editing frozen fixtures invalidates the trial and requires a new run.

This trace covers evaluation operations, not the host's full tool history.
Submission limits do not cap the host's turns, tokens or spending. Enforce those
through the host/provider controls. Live trajectory capture and calibrated
model-based judges remain future work.
