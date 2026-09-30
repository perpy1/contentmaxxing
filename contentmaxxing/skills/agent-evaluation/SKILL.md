---
name: agent-evaluation
description: Evaluate CONTENTMAXXING skill or model changes against fixed editorial briefs. Use for regression evaluations and comparing kit versions, not ordinary creator drafting or publication approval.
---

# Evaluate the creator agent

Use the existing AI host to run matched editorial tasks, then separate mechanical
checks from human editorial judgment. This lab does not publish content or modify
the creator's workspace. Do not treat an eval result as publication approval.

## Prepare and execute

Run `contentmaxxing evals prepare --output <new-folder> --label <host-model-skill-version>`.
This creates six fictional cases, isolated engine workspaces and self-contained
`cases/<id>/packet.json` files. Use the runtime fallback from `commands/README.md`
if the CLI is absent. Omit global `--workspace` and `--provider` options for evals.

For workspace-customized intelligence, pass `--intelligence <.contentmaxxing-folder>`.
Only skills, prompts and templates change; fixtures and validation remain shared.
Use `--suite <json>` for a reviewed custom suite matching `eval-suite.schema.json`.
Anonymize real failures before making them reusable cases. Keep suite revisions
deliberate, so a changed task is not mistaken for an improved model.

Read RUN.md, then one packet at a time. Execute its task instructions against its
supplied inputs; write the output-contract JSON to `responses/<case>.json` and run:

```sh
contentmaxxing evals submit --run <folder> --case <case> --file <response.json>
```

Do not complete or edit the frozen case's task directly. Submission imports a
copy through the real engine and retains the response, check results, outcome
records and evaluator events in `run.json`. Do not inspect earlier responses or
human rubrics to copy the desired answer. Default budget: one submitted attempt
per case. If a trial fails, preserve it. Extra trials require a new labeled run or
an explicitly configured `--max-attempts` at preparation. Host turns and costs
are outside this limit; use the host's own controls for those.

## Judge and compare

`contentmaxxing evals report --run <folder>` shows each case's automatic checks
and its human rubric. Exact citations, valid schemas and review-state checks
cannot establish attribution, truth, learned voice or usefulness.

Show the source, response and question to a human reviewer. Record only feedback
they actually supply:

```sh
contentmaxxing evals grade --run <folder> --case <case> --verdict pass --reviewer <name> --note <evidence-based-feedback>
contentmaxxing evals compare --baseline <old-run> --candidate <new-run>
```

Never record your own judgment as human review. Unreviewed work remains
NEEDS_HUMAN_REVIEW. New attempts need fresh review; previous feedback remains
attached to the original response. Comparisons use first attempts and report
individual checks. The suite and grader must match. Skill instructions may
differ; their hashes are retained. There is no universal quality score.

The recorded trace covers evaluator operations, not the host's entire tool use.
Reviewer names are declared, not authenticated. These are local evaluation
records, not a security boundary against a host with filesystem access.
