---
issue: "[Fix-round move-finish step replaces an answers file written while the move is pushing](https://github.com/nedsnodes/nedsnodes/issues/4464)"
---

# Fix-round move-finish step replaces an answers file written while the move is pushing

## What happens

The program `scripts/pull-request-fix-round-author-brief-from-blocking-findings-and-one-commit-every-finding-answered-check.py` writes an answers file, `fix-round-answers-pull-request-<number>.md`, in which a fix-round's author answers each review finding. When a fix-round moves one change to a pull request of its own, `--move-change-to-own-pull-request-cut-new-topic-branch` moves that file to a set-aside path in the git directory, and `--move-change-to-own-pull-request-finish` moves it back after the push.

The move back is `shutil.move(set_aside, answers)`, at line 1638 of the program on main at commit 663c805a3. It replaces whatever is at the answers path. For example, if a second agent-session or subagent writes text to `fix-round-answers-pull-request-4453.md` while the finish step is pushing, that text is lost when the set-aside file comes back. The finish step refuses to start while an answers file is present, so only a file written after that check is at risk.

## How likely it is

No occurrence is known. A search of the agent transcripts on ned-box found the move commands run for one move, on 2026-11-10. The Mac's transcripts were not searched.

## Why it is not fixed yet

Two pull requests rewrote this code and closed at the fix-round limit: [Fix-round brief: keep this round's partial answers when the answers file is reopened](https://github.com/nedsnodes/nedsnodes/pull/4389) and [Fix-round brief keeps a copy of non-blank answers before any overwrite](https://github.com/nedsnodes/nedsnodes/pull/4453). The pull request that replaces them fixes only the brief's own overwrite of the answers file, and leaves both move commands as they are on main.

[Review 6030598757](https://github.com/nedsnodes/nedsnodes/pull/4453#pullrequestreview-6030598757) names three traps that a rewrite of the move commands must avoid:

1. A move started by the old program and finished by the new one must not delete the move record while the answers are still in the set-aside file: the finish step refuses and names that file.
2. A finish step given another pull request's number must not commit and push the answers file: the start step records the number, and the finish step refuses on a mismatch.
3. The `git switch` back to the original branch must not replace an ignored answers file when that branch has started tracking the path: that switch passes `--no-overwrite-ignore`.

## Options

1. Remove the set-aside code, so that both move commands leave the answers file in the worktree and the finish step unstages it before its commit. This removes the move back, and must avoid the three traps above.
2. Do nothing, because the case has not happened, and close this GitHub issue as not planned.

## Next action

On the Mac, search `~/.claude/projects/` for Bash commands that run `--move-change-to-own-pull-request-finish`. If no run lost an answer, or the transcripts cannot show one, take option 2. If a run lost an answer, take option 1.
