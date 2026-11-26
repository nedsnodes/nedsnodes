---
issue: "[The merge-lane head test run reuses a stale merged worktree, so a suite already fixed on main fails again](https://github.com/nedsnodes/nedsnodes/issues/4347)"
---

# The merge-lane head test run reuses a stale merged worktree, so a suite already fixed on main fails again

## What is wrong

`scripts/merge-lane-pull-request-head-test-run-on-merged-worktree.py` tests the worktree `pr<n>-merged` as it finds it. Line 91 at main commit `f863364a1` passes that path to the runner as `--checkout`, and nothing compares the worktree with main or with the pull request's current head. `scripts/pull-request-head-test-run.py` checks only that the worktree's tracked files match its own commit.

When a head test run fails because main was broken, and main is then fixed, running this program again tests the old merge and fails on the suite main has already fixed. merge-lane-2 then has to merge `origin/main` into `pr<n>-merged` by hand, or send a pull request back for a failure it did not cause.

## Evidence

A reported case, not checked against the live merge-lane worktrees: on 2026-11-20, a rerun for pull requests 3908, 3901 and 3095, after pull request 3944 fixed main, reused the `pr<n>-merged` worktrees, one at commit `b02ed4391464`, and failed again on the fixed suite (unverified).

A reproduction in a throwaway git repository, with the real program at `f863364a1` and a fake runner that runs a `suite.sh` file made for the reproduction: `pr7-merged` was built on a main whose suite exits 1, main was then fixed at `d8cd645`, and the program was run again. It printed `PR 7 head test run: exit 1; SUMMARY: suite.sh in pr7-merged exited 1`, and `pr7-merged` stayed at `e6286f5`, which does not contain `d8cd645`.

## What to do

Make the program rebuild `pr<n>-merged` before it tests, on each run, from two commits. The main commit is the one `--review-tools-worktree-at-main` has checked out, not `origin/main`, because `scripts/merge-lane-pull-request-worktrees-reviewer-brief-codex-review-and-head-tests-run-without-merge.py`, the review pipeline, pins that worktree at the main commit it reviews, while a concurrent fetch can move `origin/main`. The head is the new option `--head-commit`, which takes one pull request and which the review pipeline must be changed to pass, so that a push during a review cannot make the test run cover a different head. Without the option, the program reads the pull request's current head from `refs/pull/<n>/head` on origin.

The rebuild reuses `scripts/merge-lane-pull-request-head-and-merged-worktrees-rebuild.py`, through a new option `--merged-worktree-only`. That option leaves `pr<n>-head` in place, because the review pipeline runs this program at the same time as its Codex and Claude reviewers, which read `pr<n>-head`.

When a rebuild fails, as on a merge conflict, the program prints what failed, runs no tests for that pull request, goes on to the next pull request, and exits 2. `scripts/merge-lane-pull-request-head-test-run-on-merged-worktree-test.py` covers a main that has moved past `pr<n>-merged` and a rebuild that fails.

A rerun outside the review pipeline rebuilds on whatever commit the review tools worktree has checked out, so whoever reruns it must first move that worktree to the fixed main. Making the program fetch main itself is left out of this fix.
