---
issue: "[The merge-lane merge program stops a merge batch when GitHub deletes the merged branch between its read and its delete](https://github.com/nedsnodes/nedsnodes/issues/4543)"
---

# The merge-lane merge program stops a merge batch when GitHub deletes the merged branch between its read and its delete

## Reproduction

On 2026-11-24, merge-lane-2's merge batch 66 ran `scripts/merge-lane-pull-request-merge-through-merge-gate-with-stacked-pull-request-retarget.py` for [PR 4469](https://github.com/nedsnodes/nedsnodes/pull/4469). Its output, in the directory of merge batch logs that merge-lane-2 started on 2026-11-22, `nedlern@ned-box:/home/nedlern/nedsnodes-logs/seats/merge-lane-2/merge-queue-drain-2026-11-22/merge-4469.out`, shows:

```
merge exit 1
{"mc":"93458c7e93636500d68207791e7f5cf9e1658ad7","mergedAt":"2026-11-24T06:52:56Z","state":"MERGED"}
pull request 4469 merged although the merge command exited 1: EOF
STOP: merged, but the branch restart-page-its-own-restart-wording-and-last-paragraph-points-to-the-notice-topic-branch is still on GitHub and could not be deleted: gh: Reference does not exist (HTTP 422)
```

The program exited 3, and the batch stopped before its third pull request. Afterwards, `gh api repos/nedsnodes/nedsnodes/branches/restart-page-its-own-restart-wording-and-last-paragraph-points-to-the-notice-topic-branch` answered `Branch not found (HTTP 404)`: the branch was gone, so nothing was left to do.

## What is wrong

`gh pr merge --delete-branch` exited 1 with `EOF` after GitHub had merged, so `merged_branch_deleted` runs. It reads the branch with `gh api repos/<repository>/branches/<branch>`, finds it present, and then sends `DELETE repos/<repository>/git/refs/heads/<branch>`. Between the read and the delete, GitHub's own branch deletion for the merge removed the branch, so the delete answered HTTP 422 `Reference does not exist`. The program treats every failed delete as a branch still on GitHub, prints a STOP that says so, and exits 3. That reports a step as not done when it is done, and stops the merge batch, which then waits for merge-lane-2 to read the log and start the next batch by hand.

## What to do

The agent-seat ned-box-helper, whose commit c30d1736c wrote this code, makes the fix. After a failed delete, `merged_branch_deleted` reads the branch again before it prints the STOP:
- When that read answers HTTP 404, the branch is gone: print `the branch <branch> is gone from GitHub`, as the first read does today, and return exit 0.
- When the branch is still there, or the read fails, print the STOP as today and return exit 3.

Reading again covers every way the race can end, whatever error text GitHub gives the delete, so the fix does not match on `Reference does not exist`.

In `scripts/merge-lane-pull-request-merge-through-merge-gate-with-stacked-pull-request-retarget-test.py`, add a case whose first read answers with the branch, whose delete answers HTTP 422 `Reference does not exist`, and whose second read answers HTTP 404. It expects exit 0, the `is gone from GitHub` line and no STOP. The existing case `merged-branch-not-deleted` answers every read with the branch, so it still expects exit 3 and stays as it is.
