# Test your first content engine

This is an early testing release. Start with Codex CLI/IDE, the host exercised in
native trials. The goal of your first session is useful drafts in your voice,
with evidence you recognize. Publishing and connecting analytics can come later.

## Bring one real thing

Use a work note, transcript, old post or newsletter you are comfortable giving
your AI. One text file is enough. Two or three writing samples help it distinguish
your actual voice from a preferred tone. You can also start with an interview
about something you recently did.

TXT, Markdown, CSV, JSON/JSONL, SRT and VTT are accepted directly. PDF, images,
audio and video need a text export or extraction through your host. An ordinary
browser chatbot without local file and command access cannot run this kit.

## Start

Follow the [installation guide](INSTALL.md), open your creator folder in Codex,
start a new session if needed, and invoke `$contentmaxxing-start`.

Choose **curated interview** or **mega file dump**. Tell it your starting platform
and a realistic cadence. Confirm or correct the profile it proposes. The AI
handles commands and task files; you should be making editorial decisions.

Useful first-session prompt:

> Build my content engine from this material. Ask a few questions at a time.
> Show me the strongest topics and create up to three drafts for my review.
> Keep my voice, cite the source material, and flag anything you need me to verify.

If you are trying the interview, describe a specific project, decision, mistake
or customer question. If you are trying the file dump, name your source folder.

## What a successful first session looks like

- Your Brand Brain, Voice, Pillars and Offer reflect your answers, with unknowns
  left visible. Look under `data/creator/`.
- The idea bank contains distinct topics you recognize, with source references.
- You have a small review batch and a launch plan. Fewer drafts are appropriate
  when there is not enough evidence. Drafts remain `NEEDS_REVIEW`.
- It has not invented an achievement, customer story, metric or personality.

Now correct one draft: say what to change and whether that preference applies
only to this piece, to that platform, or to future writing generally. Ask for
the revised draft and a second draft from another real source. Check whether
the correction was used at the scope you intended.

Open a fresh session in the same creator folder. Run `$contentmaxxing-progress`,
then `$contentmaxxing-resume`. It should recover your saved work and the next
decision, without silently starting a duplicate batch.

## Report what happened

Use this repository's **Issues → New issue → Creator beta feedback**. Use **Bug
report** for installation errors, lost work or a failing command. If the repository
hasn't been published yet, send the same details to the person who gave you the kit.

Include your host, OS, package version, onboarding path and the stage you reached.
For writing feedback, share one small anonymized example: the source excerpt,
the draft, and how you would change it. Report voice, usefulness and factual
support separately; “the installation worked” does not grade the writing.

Share only material you intend to make public. Don't attach your whole creator
folder, client conversations, credentials or private analytics to an issue.
No telemetry or feedback upload runs automatically.

To inspect the installed version, run:

```sh
python -c "from importlib.metadata import version; print(version('contentmaxxing'))"
contentmaxxing doctor --agent codex --path ../my-content
```

Use the Python environment and creator path you installed. `doctor` checks local
files; it does not prove the host loaded a skill. If commands are absent, reopen
the correct creator folder and start a fresh host session. Your agent can read
`.agents/skills/contentmaxxing-start/SKILL.md` directly as a Codex fallback.

## A second session

Once the first batch is useful, add another real source and ask for a small weekly
plan using `$contentmaxxing-week`. Review the selection, platform choices and
unfilled slots. After publishing manually, import real CSV/manual metrics with
`$contentmaxxing-analytics`; use `$contentmaxxing-compound` when there is enough
comparable evidence for a winner. Typefully is optional throughout.
