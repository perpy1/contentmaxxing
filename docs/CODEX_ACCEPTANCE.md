# Fresh Codex CLI acceptance — 2026-09-30

This check launches the installed CONTENTMAXXING kit in fresh Codex CLI sessions,
outside the development checkout. The test persona and documents are fictional.
The host supplies actual model-generated extraction and writing responses;
these are not the literal response fixtures used by the offline smoke test.

## Method

- Codex CLI 0.159.1, existing host sign-in and default model configuration.
- A noneditable wheel installed into a separate Python 3.11 virtual environment.
- Separate project installs for interview and file-dump onboarding.
- Each invocation starts an ephemeral session with workspace-write sandboxing.
  No development conversation or expected answer is supplied to the host.
- Prompts name the native skill and supply normal creator requests, answers and
  source paths. The host must discover the skill and operate the engine itself.
- No Typefully setup, publishing requests or second model API key. The current
  user's active creator pilot is left untouched.

Native Codex required permission to initialize its app-server client outside
the parent process sandbox. Its own command sandbox remained workspace-write.
This check uses the host's model/account; it is not an offline test.

## Observed corrections

The first session discovered `$contentmaxxing`, recovered from an incorrect
relative-path lookup, and offered both onboarding choices. It omitted the HUD.
The installer now explicitly anchors core paths to the directory containing
the instruction file, and asks the host to include either a rendered image or
the text banner in its reply. Inspecting an image is distinguished from
displaying it to the creator.

After rebuilding and reinstalling the kit, `$contentmaxxing-start` displayed
the text HUD when told the image was invisible and asked three interview
questions. The new file-dump session also displayed the text HUD without being
told where the skill bundle lived.

The file-dump agent then saved mining response JSON directly in `data/tasks/`.
The old record reader treated every JSON file there as a task, so resuming failed
with a missing `id`. The host recovered by moving its working files. The engine
now lists only canonical record filenames (`prefix_` plus 12 hexadecimal digits),
preserves other files, and reports ID/filename mismatches in actual records.
The shared instructions direct result payloads to `data/task-results/`.
Two new regression tests cover resume with stray/unfinished result files and
the corruption check; both failed before the fix.

## Acceptance evidence

The interview used Morgan Demo, independent studio operators as the audience,
a goal of useful working notes and trust, X at three posts per week, and a
sentence-case writing sample. The host saved the creator brain, marked the
voice provisional, mined four distinct topics from six source lines, and
created three X drafts under 280 characters. All remained NEEDS_REVIEW with
source references. The fourth topic remained in the bank. A launch plan was
saved with the requested weekly cadence.

The file-dump session preserved two documents and prepared a cited profile
proposal. Before confirmation, the saved phase was PROFILE_REVIEW, profile.json
did not exist, and there were no content records. A later simulated creator
message explicitly confirmed the fictional identity and supplied cadence and
restrictions.

After confirmation, the host created four distinct ideas across the two sources
and three X drafts in NEEDS_REVIEW, plus the creator documents and launch plan.
Repeated automation advice was merged into one idea with both source references.
No task IDs, JSON authoring or terminal commands were delegated to the simulated
creator.

Finally, fresh sessions invoked `$contentmaxxing-progress` with a request to
resume the file-dump workspace, and `$contentmaxxing next` in the interview
workspace. Both displayed the existing drafts and waited for editorial input.
Snapshots of every file under each `data/` directory were byte-for-byte
unchanged: no duplicate drafts, new tasks or implicit approvals. For the resume
check, the original misplaced mining payloads and an unfinished JSON response
were deliberately put back beside task records after installing the fix. They
were preserved and did not disrupt the host.

Seven native sessions were run in total. The final automated suite passes
91 tests on Python 3.11; Python 3.9 passes 90 with one expected TOML-test skip.

## Repeating the check

Install into a fresh creator directory using `contentmaxxing install --agent
codex --path <directory>`. Open that directory in Codex and use the skill name
alone; do not supply the wrapper path or development instructions. Exercise
both onboarding choices, then restart the host and check progress, resume and
next. Compare saved draft IDs, bodies and approval states before and after
navigation. Keep all generated content in review.

The local evidence directory is `../contentmaxxing-codex-qa/evidence` relative
to the source checkout. It contains the exact prompts, host event streams,
creator-facing replies and state snapshots. Fictional creator records live in
the sibling `interview/` and `file-dump/` workspaces. These are local QA artifacts,
not part of the distributable kit.

## Limits

This is a Codex CLI acceptance check, not certification of every host interface.
It does not verify that the desktop app displays a PNG, another host discovers
its commands, or real creators recognize their voices in the drafts. It does
not test live publishing. A real editorial pilot and a published, versioned
installation entrypoint remain release work. Typefully remains optional.
