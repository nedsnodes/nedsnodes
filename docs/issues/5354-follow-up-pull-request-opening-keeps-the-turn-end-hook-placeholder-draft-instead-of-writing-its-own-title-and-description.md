---
issue: "[Follow-up pull request opening keeps the turn-end hook's placeholder draft instead of writing its own title and description](https://github.com/nedsnodes/nedsnodes/issues/5354)"
---

# Follow-up pull request opening keeps the turn-end hook's placeholder draft instead of writing its own title and description

## What goes wrong

Two programs can open the pull request of a follow-up topic branch, and when the wrong one wins, the pull request is left as a draft with a placeholder description:

- The turn-end Stop hook, `nn-systems/general-tools/agent-seat-owned-nn-topic-branches-push-and-draft-pr-open-stop-hook.py`, pushes every branch of the agent-seat's worktrees that has a commit origin lacks, a subagent's worktree included (docstring, line 18), and, when the branch has no open pull request, opens a draft whose description is the placeholder `DRAFT_PULL_REQUEST_DESCRIPTION` (lines 66-72, `gh pr create --draft` at lines 210-211). The placeholder carries none of the lines `#root_cause`, `#root_cause_not_fixed` or `#no_defect_fixed`, so `scripts/merge-gate.sh` refuses the pull request (lines 493-494) until its owner rewrites the description.
- The open-pull-request step of `scripts/pull-request-follow-up-request-after-merge-finding-answers-and-next-step.py` reads the title and description the subagent wrote into the file `follow-up-pull-request-title-and-description.md` in its worktree (`FOLLOW_UP_PULL_REQUEST_TITLE_AND_DESCRIPTION_FILE_NAME`, lines 179 and 612-613), pushes, and runs `gh pr create` without `--draft`, passing that title and description (lines 636-638).

When the agent-seat's turn end, which runs the hook, comes after the subagent commits but before the open-pull-request step runs, the hook opens the draft first. `gh pr create` in the step then refuses with "already exists", and `gh_pr_create_tried_twice` treats that refusal as success, returning "Found already open" (lines 677-679, the words matched at line 187). The step records that pull request's link and deletes `follow-up-pull-request-title-and-description.md` (line 649). It runs no `gh pr edit` and no `gh pr ready` anywhere in the file (search: `grep -n 'pr", "edit\|pr", "ready\|"ready"'` over the file, no hit), so the subagent's title and description never reach the pull request, it stays a draft, and the only copy of the description is gone.

## Seen

On 2026-11-27, PR [find-deleted-path-across-backups: refuse a path the system cannot reach, and name the spelling a symlink hides](https://github.com/nedsnodes/nedsnodes/pull/5344), opened 15:42:03Z, sat as a draft with the placeholder description. Another agent rewrote the description from the commit, and the pull request was marked ready at 15:48:06Z. The sibling follow-up PR [run-all-test-suites refuses a suite sandbox list bound other than once by a literal assignment](https://github.com/nedsnodes/nedsnodes/pull/5333), opened the same day by the same step, did not hit it, so the outcome depends on when the agent-seat's turn ends. That the hook's draft came first is inferred from the placeholder the pull request carried; which turn end fired the hook is unverified.

## Why it matters

The step reports success, so nothing tells the agent that the pull request is a draft with the wrong description. The pull request then stops at `scripts/merge-gate.sh`, and the description the subagent wrote is lost, so someone must write it again.

## Root cause

The step treats "a pull request for this branch is already open" as "the pull request this step would have opened", although the hook's draft differs from it in title, description and draft state. The "already open" handling was written for a first try of the step's own that opened the pull request and then failed (the module docstring, lines 62-64), not for a pull request another program opened.

## Next action

Design the fix and merge it, with a test that injects an already-open draft whose description is the hook's placeholder. Two directions to weigh:

1. When the step finds the branch's pull request already open and its description is exactly the hook's `DRAFT_PULL_REQUEST_DESCRIPTION`, the step writes into it, with `gh pr edit`, the title and the description it passes to `gh pr create` today (the file's text with the `#follow_up_request pull request <number>` line that `build_pull_request_description_ending_with_follow_up_request_line`, line 553, adds), and marks it ready when it is a draft. Any other description it leaves alone and reports, since another agent may have rewritten it. This also covers any other program that opens the pull request first.
2. The Stop hook skips a branch that the step's record `pull-request-<number>-follow-up-topic-branches-and-worktrees.json` (`TOPIC_BRANCHES_AND_WORKTREES_FILE_NAME_FORMAT`, line 177) lists for a finding with no answer yet, so only the step opens that branch's pull request. This removes only this race and leaves the step's "already open" handling as it is.

Direction 1 fixes the root cause named above. Under either direction, the step reads the pull request back with `gh pr view --json title,body,isDraft` after opening or editing it, and when the title or description differs from what it sent, or the pull request is still a draft, it exits nonzero and keeps `follow-up-pull-request-title-and-description.md`, so a mismatch is reported instead of passing silently. GHI [Topic-branch base enforcement: a branch-creation script and a gh pr create check that refuses an undeclared carry of another PR's commits](https://github.com/nedsnodes/nedsnodes/issues/238) plans a validation on `gh pr create`; a pull request direction 1 edits instead of creating should still meet it.
