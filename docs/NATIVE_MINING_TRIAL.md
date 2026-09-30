# Long-conversation mining and continuity

The 2026-09-30 trial tests whether CONTENTMAXXING can mine a conversation in saved
windows and retain useful connections without depending on one chat's memory.
All creator details, stories and outcomes are fictional. No content was published,
no real creator graded the outputs, and no active pilot was changed.

## Whole-source native trial

`tests/fixtures/mining-workshop.txt` is a 9,800-character interview with Dana Demo,
a ceramics workshop teacher, an interviewer and a guest. It contains processes,
mistakes, questions, proposed tests, unverified guest results, missing artifacts,
privacy boundaries and points repeated later in the conversation. The separate
`mining-workshop-rubric.json` names review questions without imposing a topic quota.

`examples/mining_trial_seed.py` initializes a new isolated workspace and captures
the source. It seeds no candidate answers, drafts or grades. Mining is configured
for 4,000-character windows with 500-character overlap. A fresh Codex CLI session
invoked the native mine skill using the installed upgrade-increment wheel.

Observed results:

- Three completed windows covering the entire source.
- 21 saved BACKLOG ideas, four flagged as article candidates.
- 31 exact source citations; no chosen formats or generated drafts.
- Repeated tray-location and checklist examples attached to existing topics.
- Saved notes distinguish the guest's story, future experiments and missing media.
- Repeating the completed source pass leaves every data file unchanged.

One initial PATH lookup failed. The host recovered using the installed interpreter
hint. The original failure remains in the trace. These results establish this
fictional host workflow and exact citations, not exhaustive semantic coverage.
The rubric finds candidate records by source lines for human review; a matching
span alone does not establish that its meaning was captured.

The host used `ideas cite` to attach later passages. A stateless provider could
not make the same informed choice from its window alone: the earlier idea bank
was absent from its task input. This led to shared existing-topic context and
the optional `existing_idea_id` output field documented in
[mining and revisions](MINING_AND_REVISIONS.md).

## Independent window probes

Three fresh Codex sessions each received only a self-contained packet for the
closing source window and wrote one JSON response. They had no earlier chat
history or access to the original workspace. The current host performed the
reasoning; this is not live certification of another model provider's API.

| Packet | Prior-topic context | Candidates linking existing IDs | New idea records on import |
| --- | --- | ---: | ---: |
| Baseline | None | 0 | 9 |
| Titles | 19 IDs, titles and categories; 2,715 characters | 4 | 6 |
| Notes follow-up | Same topics plus bounded notes; 8,794 characters | 6 | 5 |

The first pair has identical shared instructions, source inputs and contracts.
The follow-up adds notes and matching instruction wording. It is a follow-up
probe, not an unchanged-prompt replication. All three use the same source inputs
apart from the explicit prior-topic context; outer task IDs/timestamps differ.

In the title-only response, the model treated an ambiguous "sent" tick as
different from the earlier empty-box topic because its title did not describe
the recurring ambiguity. With saved notes, it linked that example to the existing
topic. It also attached the visual handout opportunity to the existing rehearsal
idea, while keeping the guest's live demonstration and the creator's proposed
silent test distinct. These are agent-observed differences, not human grades.

The installed engine imported all responses into separate reconstructions of
the prior topic bank. Each reconstruction starts with the 19 original topic
records and their primary citations; it is not claimed to be a byte-identical
historic checkpoint. Existing IDs, notes, priorities, statuses and selections
were preserved. Imports added zero, three and five new references respectively;
one reused topic already had the cited passage. Repeat import changed no data.
The original whole-source QA workspace remained unchanged.

Higher reuse counts are not a score. An incorrect merge can be worse than an
extra idea, and an independent argument should remain separate. The engine checks
ID scope, stale context and source occurrence; a person must judge semantic
equivalence, missing ideas, attribution and usefulness. All three probes remain
`NEEDS_HUMAN_REVIEW`, with zero human grades. No broad success percentage is claimed.

## Reproduce the whole-source workflow

Use an installed engine and a fresh path:

```sh
python examples/mining_trial_seed.py --workspace /tmp/contentmaxxing-mining-trial
```

Open that folder in Codex and ask its native mine skill to mine the source ID in
`TRIAL.json`, ending at the idea bank. Then run:

```sh
python scripts/check_mining_trial.py --workspace /tmp/contentmaxxing-mining-trial \
  --output /tmp/contentmaxxing-mining-checks.json
```

The checker verifies window coverage, exact citations, unselected BACKLOG status
and byte-identical completed-pass resume. It produces the line-linked rubric for
separate editorial review. It does not assign human grades.

## Evidence and automated verification

Local evidence directories are recorded in `VERIFICATION.json`:

- `contentmaxxing-codex-qa/mining-native-evidence/`: prompt, complete trace, reply,
  saved-record checker output and ungraded rubric.
- `contentmaxxing-codex-qa/mining-window-evidence/`: three prompts/traces/replies,
  input preparation metadata, installed-engine replay checker and comparison.
- Packet and response files remain in the sibling `mining-window-*` folders.

Ten new regression tests cover bounded context, omissions, frozen pending tasks,
stateless multi-window extraction, stale/out-of-scope matches, preserved editorial
metadata, interrupted import recovery, legacy pass contracts and ZIP relocation.
The final suite passes 235 tests on Python 3.11 and 234 with one expected skip on
Python 3.9. The installed wheel passes the offline smoke, including existing-topic
attachments and creator-data preservation. Package artifacts are local under
`dist/mining-increment/`; this is not a public release or a repeated full native
mining trial using the final implementation.
