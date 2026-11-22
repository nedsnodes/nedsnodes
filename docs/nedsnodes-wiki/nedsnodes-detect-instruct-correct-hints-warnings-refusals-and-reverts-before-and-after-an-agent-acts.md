# Detect-instruct-correct

Detect-instruct-correct (DIC) is how this project keeps an agent to a rule without trusting the agent to remember the rule. A program detects that an agent may be about to break a rule, or may have broken one; the program tells the agent what it found, why it matters and what to do; and the act is then avoided, or corrected by the agent or by the program. The glossary's entry for detect-instruct-correct points here; this page is the term's full definition.

Read this page before you add a hook, a test or a scheduled job that answers an agent's act, and before you add a rule to standing instructions: the [enforcement ladder](nedsnodes-enforcement-ladder.md) says why a program that detects the act usually serves a rule better than another line of text. How to word what the program says to the agent is in [How to write a tool-message-to-agent](nedsnodes-how-to-write-a-tool-message-to-agent-such-as-a-hook-refusal-or-script-error.md); this page says what the program and the agent do, not how the message is worded.

The work is split as code-prompt-code splits any work. Code detects what it can, as the act happens. An agent reviews prose and logs for the faults that need judgment. Code fixes what is mechanical; an agent fixes the rest, once a program has told it what not to do and why. A test or review too slow or too costly to run at the act runs later, in a maintenance-job, over the files changed since its last run. What neither code nor an agent can decide goes to the user.

Each case below is marked **built**, with a file on main that does it, or **not built**.

## What the program can know

A program's detection is one of two kinds.

- **A certain detection** finds that the rule is surely broken, or surely about to be. Examples: a guarded-file whose content hash has changed with no approval recorded for the new version; a hand-typed `gh issue create` found by parsing the shell command before it runs.
- **A guess** is a cheap detection that is often wrong, such as a pattern of words in the agent's reply. A guess is worth the context its message costs only if, over many firings, it leaves the work better than silence would.

Some faults are fully detectable and some only partly. A file's path, its hash, or a commit's diff against main can be read exactly, so a detection on them is certain for every route the program sees. A program that parses a shell command is certain about the commands it can parse and blind to the rest: the shared parser does not see inside `ssh`, `bash -c`, `eval` or a script file. A pattern in prose is always a guess. Where a certain detection is blind to a route, a second detection, later or by another means, can cover that route, as the guarded-file hook after every tool call covers the shell writes that the instruction-file guard before an edit does not see.

Two more things decide what the program does: the blast radius, and whether an undo exists. An act's blast radius is high when the act would lose or damage work, or would be hard to undo, and low when it loses nothing and is easy to undo. When no undo exists, as for a reply the user has already read or a commit others have fetched, the only correction is new work on top, so an act whose damage neither an undo nor new work can repair is one to refuse before the act. A detection, or a second detection behind a first, is added only where CLAUDE.md's two conditions for a guard hold: the failure has happened, or is foreseeable within 30 days on concrete evidence, and it would lose or damage work, stop other work, or go unnoticed until it does.

## Before the act

These programs run before the act, as Claude Code's PreToolUse hooks do, so they can stop it.

| Detection | Blast radius | What the program does | What the agent does | Status and example |
|---|---|---|---|---|
| Certain | Any | Refuses the act, saying what is wrong, why, and what to do instead, such as the program that does the step right: a hard-block, or a user-block when only the user may allow the act | Does what the refusal says instead, and retries; for a user-block, asks the user first | Built: `.claude/guard-hooks/ghi-issue-write-hand-typed-gh-command-refusal.py` refuses a hand-typed `gh issue create` and sends the agent to `scripts/ghi-issue-write.py`; `.claude/guard-hooks/instruction-file-guard.py` refuses an edit of a guarded-file until the user's approval is quoted into a marker file |
| Guess | High | Refuses the act, but lets the agent go ahead once the agent says it checked: a soft-block, cleared by the agent's reason written into the marker file the refusal names | Checks; when the act is right, writes its reason into the marker file and retries; otherwise does the act the right way | Built: `.claude/guard-hooks/ghi-md-whole-file-replacement-soft-block.py` refuses a whole-file replacement of a GHI-MD until the agent writes its reason |
| Guess | Low | Lets the act go ahead, and adds a hint ("this would be better"), a warning ("this might be a problem"), or both; a hint is paced as [How often a hint fires](#how-often-a-hint-fires) says | Weighs the hint or warning; carries on when it has already weighed it | Built: `nn-systems/general-tools/claude-code-bash-git-push-of-markdown-change-citation-checks-reminder-hook.py` reminds the agent, before a push that changes a Markdown file, to run the two citation programs, and never blocks the push |

Every agent-action-block teaches: its tool-message-to-agent says what was stopped, why, and what to do instead, so that the agent learns the wanted behavior and not only how to get past one refusal. The glossary's hard-block, soft-block, user-block and reminder-block say what, if anything, clears each kind.

## After the act

These programs run after the act: just after a tool runs, at the end of the agent's turn, when the user's next prompt arrives, at a push or a pull request, or on a schedule. The act has happened, so they cannot stop it; they can only have it corrected. What the agent does depends also on whether others already have the work; the four cases under "What a message says" in [How to write a tool-message-to-agent](nedsnodes-how-to-write-a-tool-message-to-agent-such-as-a-hook-refusal-or-script-error.md) say what the message tells the agent in each. Below, "does the act again the right way" means: the right way when the act had a right way, and not at all when the act itself was what the rule forbids.

| Detection | When | What the program does | What the agent does | Status and example |
|---|---|---|---|---|
| Certain | The program can undo the act safely | Reverts the act, keeping a copy of what it replaced, and tells the agent what it reverted, why, where the copy is, and how to do the act correctly | Does the act again the right way | Not built: no program on main undoes an agent's act on its own (the enforcement ladder's rung 5) |
| Certain | Only the agent can undo the act safely | Tells the agent what it detected and how to revert it | Reverts the act, then does it again the right way | Built: `scripts/obsolete-file-edit-warning-hook.py`, after an edit of a file that main has since changed, tells the agent how to drop the edit with `git checkout -- <path>` and rebase |
| Certain | Only the user can decide whether the act stands | Keeps a copy of every version, and tells the agent to show the user the change and run the program's approve or restore command | Asks the user, with a recommendation; runs `--approve` when he approves, or `--restore` when he does not | Built: `.claude/guard-hooks/guarded-file-unapproved-change-afterward-backup-and-ask-hook.py`, after every tool call, finds a guarded-file changed without approval; the change stays in place while the user is asked |
| Guess | Any | Warns the agent that the act may have broken the rule, and says how to check | Checks; when it finds the rule broken, reverts the act, or corrects it in its next message when the act was a reply, and does it again the right way; otherwise carries on | Built: `scripts/absence-claim-locator-reminder-hook.py`, at the end of a turn whose reply says a file is missing, sends the agent once to run `scripts/locate-file-copies-across-machines.py` |
| Certain or guess | Too slow or too costly to check at the act | A maintenance-job checks later, over what changed since its last run, and reports each fault where an agent or the user will act on it | Fixes the reported fault, as new work on top | Built: `scripts/scheduled-full-mutation-pass-of-merged-pull-requests-and-survivor-tasks-open.py` runs nn-mutation-testing each night on the pull requests merged since its last run, and opens a task for each line with surviving mutants |

## When the guess is wrong

A guess is often wrong, and a certain detection can be wrong when its program has a defect. Four things limit the cost of being wrong.

- **Logs show how often each rule is right.** That rate sets how often the rule's hint fires, or shows that its detection should be tightened. Built in part: `scripts/absence-claim-locator-reminder-hook.py` logs one line for each reply it fires on, and `nn-systems/general-tools/claude-code-registered-hook-rule-ids-in-both-machines-transcripts-weekly-count-and-never-seen-rules-report.py` counts, each week, how often each registered hook's rule ID appears in both machines' transcripts. Not built: a record of whether each firing was right, from which a rule's rate could be read.
- **A wrong refusal is passed by the agent after checking.** Built for the refusals that are soft-blocks, such as the GHI-MD whole-file replacement soft-block above; a hard-block cannot be passed, so it is used only where its detection is certain.
- **A wrong revert is undone from the kept copy.** A program that reverts an act keeps a copy of what it replaced and says where the copy is, so that an agent whose check finds the revert wrong puts the copy back. Not built, since no program reverts on its own; the guarded-file hook's store of every version, from which `--restore` puts any kept version back, is the existing model for such a copy.
- **A confirmed fault makes the rule fire more for a while.** A fault is confirmed when a certain detection after the act finds the rule broken. A mistake just made is likelier to be made again soon, so after a correction confirms that the agent broke the rule, the rule's hint fires more often for a while, then returns to its usual spacing. Not built.

## How often a hint fires

A hint costs context each time it fires, and hints that are seldom right teach the agent to skip hints, so how often a hint fires depends on how often it is right and on what the mistake it guards against would cost. A hint that guards against a costly mistake may fire each time its detection matches. A hint that is right only about 1 time in 10 fires at most once per stretch of the agent's work, such as once per 50,000 tokens the agent-session has spent since that rule's last hint. The token count includes the tokens that Claude Code's compaction later summarizes away, because compaction makes the agent remember less, not more. A mistake just made is likelier to be made again soon, so after a correction confirms that the agent broke the rule, the rule's hint fires more often for a while, then returns to its usual spacing.

Built today: a hook fires once per agent-session, as `scripts/absence-claim-locator-reminder-hook.py` does, or sends its full text once per agent-session and after each compaction and one line after that, as `scripts/bare-number-citation-in-markdown-and-agent-reply-warning-hook.py` does.

Not built: spacing counted in tokens. The trigger-first design, `docs/issues/30-trigger-first-instruction-delivery.system.design.md`, of GHI [Trigger-first instruction delivery (moved from nedlern#1972): delivery timing as a property of every instruction — step-2 CLAUDE.md design input + carried design and scan](https://github.com/nedsnodes/nedsnodes/issues/30), holds the mechanism: a setting `min_spacing_tokens`, default 50000 with a per-rule override, and a count kept per agent-session and rule, measured in the growth of the transcript's bytes, about 200 KB for 50,000 tokens, so that compaction does not reset it. Spacing tied to how often a hint is right, and a raised rate after a confirmed fault, are not in that design yet.

Open questions, for the build to bring to the user:

- After a correction confirms a fault, how much more often does the hint fire, and for how long?
- When a warning asks the agent to check and the agent finds the rule broken, does that also raise the rate? That needs a way for the agent to report what it found.
- Does 50,000 tokens stay the default? The trigger-first design's own note says roughly 50,000 to 100,000 tokens.
- How is a hint's rate of being right measured? That needs a record of each hint and its outcome, which code may read from the agent's next tool calls, such as a `git checkout -- <path>` after the obsolete-file warning, rather than from the agent's own report.
- Is a warning paced the same way as a hint when its detection is a guess, while a correction after a certain detection fires each time?

## Detection techniques the project uses

Each technique is listed with one program on main that uses it.

- **Parsing a shell command before it runs.** `nn-systems/general-tools/shell-command-tree-sitter-bash-reader-common.py` is the shared parser; `.claude/guard-hooks/ghi-issue-write-hand-typed-gh-command-refusal.py` uses it to find a hand-typed `gh issue create`. It does not see inside `ssh`, `bash -c`, `eval` or a script file.
- **A path checked before an edit tool runs.** `.claude/guard-hooks/instruction-file-guard.py` refuses an Edit, Write or NotebookEdit of a guarded-file until the `.walk-approved` marker file holds an approval. It does not see a shell command's writes.
- **A file's stat data, then its hash, compared after every tool call.** `.claude/guard-hooks/guarded-file-unapproved-change-afterward-backup-and-ask-hook.py` hashes only a file whose stat data changed, so it sees a guarded-file changed by any tool, the shell included.
- **A pattern in text the agent just wrote to a file.** `scripts/style-guide-word-checker-markdown-edit-hook-hack.py`, after an Edit or Write of a Markdown file, reports each word the style guide lists.
- **A pattern in the agent's reply, at the end of its turn.** `scripts/absence-claim-locator-reminder-hook.py`, a Stop hook, reads the last reply in the transcript.
- **A pattern in the agent's previous reply, when the user's next prompt arrives.** `scripts/ned-box-path-in-agent-reply-unclickable-on-mac-warning-hook.py`, a UserPromptSubmit hook, notes each ned-box path the user cannot open on the Mac.
- **A diff against main.** `scripts/obsolete-file-edit-warning-hook.py` compares the edited file with main after each Edit or Write; `scripts/branch-reverts-a-file-to-an-older-main-version-check.py`, which the pre-push git hook runs, finds a branch that sets a file back to a version main has replaced.
- **What a pull request carries, before it merges.** `scripts/merge-gate.sh` refuses a merge whose description has no `#root_cause`, `#root_cause_not_fixed` or `#no_defect_fixed` line; `scripts/pull-request-head-test-run.py` runs the affected nn-test-suites at the pull request's nn-head-commit.
- **A maintenance-job, over what changed since its last run.** `scripts/scheduled-full-test-run-of-main.py` runs every nn-test-suite on main once a day; `scripts/scheduled-full-mutation-pass-of-merged-pull-requests-and-survivor-tasks-open.py` runs nn-mutation-testing each night on the pull requests merged since its last run.
- **A count from logs.** `nn-systems/general-tools/claude-code-registered-hook-rule-ids-in-both-machines-transcripts-weekly-count-and-never-seen-rules-report.py` counts each rule ID in both machines' transcripts each week and lists the rules never seen.
- **A model's judgment.** merge-lane-2's pull request reviewers and the cold-read-cells read prose and code for faults no pattern finds.

## Undo techniques the project uses

Each technique but the last is listed with one program on main that uses it; the last is done by hand. In each, the agent runs the undo; no program on main runs one on its own.

- **Restore from the program's kept copy.** `.claude/guard-hooks/guarded-file-unapproved-change-afterward-backup-and-ask-hook.py` keeps every version of a guarded-file in the log-store; `--restore <path> <hash>` puts a kept version back, and for a new file that no approved version or main holds, the hook offers the `rm` that deletes it.
- **Revert with git, told the command.** `scripts/obsolete-file-edit-warning-hook.py` tells the agent to drop an edit of an outdated file with `git checkout -- <path>`.
- **Restore uncommitted work from a work-snapshot.** `scripts/uncommitted-work-snapshot-hook.py` keeps a work-snapshot of each worktree's uncommitted changes after every Edit, Write, NotebookEdit and Bash call; `python3 nn-systems/handoff/uncommitted-work-snapshots.py restore <ref> --keep <file> ...` commits the kept files' changes on a new branch.
- **Find a deleted file's copies, to restore one by hand.** `scripts/find-deleted-path-across-backups.py` searches git, the transcripts and both machines' backups for a path no longer on disk; it finds copies, and the agent copies one back.
- **Correct with new work on top**, when no undo exists or others already have the work, such as a reply the user has read or a commit pushed for review: the agent makes a new commit, or corrects its reply in its next message, as [How to write a tool-message-to-agent](nedsnodes-how-to-write-a-tool-message-to-agent-such-as-a-hook-refusal-or-script-error.md) says.

Whether Claude Code's rewind could let a program undo an agent's act is GHI [Find whether Claude Code's rewind can correct an agent's wrong act, triggered by a program](https://github.com/nedsnodes/nedsnodes/issues/1758).
