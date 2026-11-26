---
issue: "[The merge queue program merges a pull request over a `HOLD-` line appended after it read the queue file and before the merge program merges](https://github.com/nedsnodes/nedsnodes/issues/4985)"
---

# The merge queue program merges a pull request over a `HOLD-` line appended after it read the queue file and before the merge program merges

## Reproduction

Make a worktree of main at commit 6c23b1178ef3, such as with `git worktree add --detach /tmp/late-hold-6c23b117 6c23b1178ef3`, and run, on ned-box, `python3 -I /home/nedlern/nedsnodes-logs/seats/merge-lane-1/late-hold-repro-2026-11-25/repro_late_hold.py /tmp/late-hold-6c23b117`; the script and its output, `output.txt`, are at `nedlern@ned-box:/home/nedlern/nedsnodes-logs/seats/merge-lane-1/late-hold-repro-2026-11-25/`. The script loads the `Case` helper of `scripts/merge-lane-merge-queue-approved-lines-merge-in-order-until-none-left-test.py`, which runs the merge queue program on a temporary queue file with a fake `gh` and a fake merge program, so it touches neither GitHub nor the live queue. The queue holds one approved line for pull request 10. The fake `gh` appends `HOLD-user-approval 10 <same line>` to the queue file when the program calls it, once during `gh pr view 10` and, in a second case, during `gh api repos/.../pulls/10/reviews`. Both calls come after the program has read the queue file. In both cases the fake merge program is called for pull request 10, and the queue file ends with the `HOLD-user-approval` line followed by `MERGED 10 ...`:

```
--- HOLD- appended during `gh pr view 10` (after the queue read)
queue file:
10 aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa 2026-11-25T10:00:00Z author-seat (round 1)
HOLD-user-approval 10 aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa 2026-11-25T10:00:00Z author-seat (round 1)
MERGED 10 eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee10

merge program calls: [['10', 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa', '2026-11-25T10:00:00Z']]
REPRODUCED: merged over the hold
```

## What is wrong

In `scripts/merge-lane-merge-queue-approved-lines-merge-in-order-until-none-left.py`, `one_pass` reads the queue file once, with `self.waiting(self.queue_lines())`, and picks the first waiting line. `one_pull_request` then reads the pull request and its reviews from GitHub, and `merged` starts the merge program without reading the queue file again. The merge program, `scripts/merge-lane-pull-request-merge-through-merge-gate-with-stacked-pull-request-retarget.py`, and the `scripts/merge-gate.sh` it runs do not read the queue file either (searched on main for `queue` and `HOLD-`: no read of the queue file). So a `HOLD-` line a merge-lane appends from the moment the queue file is read until the merge program merges on GitHub is not obeyed, and the pull request merges over the hold. The program's docstring promises that a `HOLD-` line appended while the previous merge runs holds the pull request; it says nothing of this later window, so a merge-lane that appends a hold has no way to know it came too late, apart from the `MERGED` line after it.

The window has two parts: the merge queue program's `gh pr view` and `gh api .../reviews` calls, which took 0.84 to 0.89 seconds in three timed runs on ned-box on 2026-11-25, and the merge program's own steps before its merge (a `git fetch`, a checkout, `merge-gate.sh` and the retargets of stacked pull requests), which were not timed (unverified: likely tens of seconds). No merge batch has yet run at the program's default merge batches directory, `nedlern@ned-box:/home/nedlern/nedsnodes-logs/seats/merge-lane-2/merge-queue-merge-batches`, which does not exist, so no real record shows a merge over a hold.

Why it matters: a `HOLD-` line is how a merge-lane stops a merge it approved, such as one still waiting on the user's approval. A merge over it lands a commit on main that the hold was meant to keep out, and only a revert takes it back.

[Pull request 4947](https://github.com/nedsnodes/nedsnodes/pull/4947), which changes how the next line is chosen, widens this window slightly with label and compare calls; its review (merge-lane-1, review 6068312303, Codex finding 5b6d2733e236) graded that part fix-next, a grade defined in merge-lane-2's seat-brief `nedlern@ned-box:/home/nedlern/agents/merge-lane-2/CLAUDE.local.md`, on that pull request, so a fix for this issue and pull request 4947 touch the same lines.

## What to do

Close both parts of the window, and report a hold that still comes too late:

1. In the merge queue program, just before `merged` starts the merge program, read the queue file again under its lock, and start the merge program only when the line that was checked is still the pull request's last line. When it is not, read the pull request again at once from its new last line, as `held` already does through `append_while_still_last` and `READ_AGAIN_OUTCOME`.
2. Pass the queue file to the merge program, and have it make the same last-line check under the lock just before its `gh pr merge` call, refusing the merge when the check fails, so the merge program's own steps before the merge are no longer a window.
3. After the merge, when the queue file holds a `HOLD-` line for the pull request after the checked line, write a notice that names the merge-lane and the hold, so the merge-lane learns its hold came too late, instead of only a `MERGED` line under it.
4. Add tests that append the `HOLD-` line during the merge queue program's GitHub reads, as the reproduction does, and during the merge program's run, and check that no merge starts in the first case and that the late hold is reported in the second.
