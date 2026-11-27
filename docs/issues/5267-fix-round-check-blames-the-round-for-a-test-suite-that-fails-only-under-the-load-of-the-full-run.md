---
issue: "[Fix-round check blames the round for a test suite that fails only under the load of the full run](https://github.com/nedsnodes/nedsnodes/issues/5267)"
---

# Fix-round check blames the round for a test suite that fails only under the load of the full run

## What goes wrong

`scripts/pull-request-fix-round-author-brief-from-blocking-findings-and-one-commit-every-finding-answered-check.py --check` judges a fix-round's commit by its nn-test-suites in two runs that are not alike. On main at 2765c1b88, `suites_the_round_broke_and_suites_failing_at_frozen_head_too`:

1. runs the suites that `scripts/pull-request-ready-for-review-mark-after-description-defect-line-and-test-suites-check.py`, the pull request ready command, would run, in a scratch worktree of the round's commit, with no `-j`, so the runner starts one suite per core: on the user's Mac, 8 at a time out of 274;
2. runs again, in a scratch worktree of the frozen-head, only the suites that failed in step 1, together and with no other suite running;
3. blames the round for every suite that failed in step 1 and passed in step 2, and refuses.

A suite whose test cases time work against a short wall-clock limit can fail in step 1 because the machine is busy and pass in step 2 because it is not. The check then says the round's change broke that suite, though the round never touched it. Its refusal's only route for this case is to run the check again once and, if the same suite fails again, tell the merge-lane and not push. So every load-only failure costs a full rerun of the suites and then a merge-lane allowing the push by hand.

## What happened

On 2026-11-27 (UTC), the fix-round of pull request [Guarded-file hook and find-deleted-path-across-backups put a saved copy back with one shared function](https://github.com/nedsnodes/nedsnodes/pull/4825) had round commit 0056be630 on frozen-head 2a33f5a0ac55. The round changed four files: `.claude/guard-hooks/guarded-file-unapproved-change-afterward-backup-and-ask-hook.py`, its test, and `nn-systems/general-tools/saved-copy-put-back-at-path-staged-beside-and-swapped-in-whole-common.py` and its test, which that pull request adds and main does not have yet. `--check` refused three times:

| Run | Suites that failed at the round's commit (`-j 8`, 274 suites) | Blamed on the round |
|---|---|---|
| 1 | `scripts/clean-worktrees-test.py`, plus the two below that also fail at the frozen-head | `scripts/clean-worktrees-test.py` |
| 2 | `scripts/clean-worktrees-test.py`, `scripts/agent-seat-idle-sweep-headless-judge-wake-messages-send-and-user-alerts-write-test.py`, `scripts/pull-request-follow-up-request-after-merge-finding-answers-and-next-step-test.py`, plus the two below | the first three, as the dispatching agent reported (the output of run 2's check was not kept) |
| 3 | `scripts/clean-worktrees-test.py`, `scripts/run-gemini-task-from-brief-test.py`, plus the two below | `scripts/clean-worktrees-test.py`, `scripts/run-gemini-task-from-brief-test.py` |

`scripts/python-files-pass-selected-ruff-rules-test.py` and `nn-systems/skills/walk-me-through/tests/walk-me-through-pending-user-alerts-claim-and-insert-as-approval-walk-items-user-prompt-submit-hook-test.py` failed in every run at both heads, so the check rightly did not blame the round for them.

Three of the four blamed suites failed on a time limit or on timing; the log of the fourth shows no cause:

- `scripts/clean-worktrees-test.py`: `git ls-remote origin 'refs/pull/*/head'` "timed out after 1 seconds" in one to three test cases per run; the suite took 258 to 302 s.
- `scripts/pull-request-follow-up-request-after-merge-finding-answers-and-next-step-test.py`: "gh pr create did not finish within 0.5 s; then gh pr create did not finish within 0.5 s".
- `scripts/run-gemini-task-from-brief-test.py`: `test_deadline_kills_children_during_discovery_and_task` read a child's process-ID file before the child had written it (`FileNotFoundError`).
- `scripts/agent-seat-idle-sweep-headless-judge-wake-messages-send-and-user-alerts-write-test.py`: one re-check case failed after a 350.9 s run; its log prints the case's inputs but no error, so whether load caused it is not known.

None of these four suites, nor `scripts/clean-worktrees.py` or `scripts/run-gemini-task-from-brief.py`, names a file the round changed: grep for `saved-copy-put-back`, `saved_copy_put_back`, `guarded-file-unapproved-change-afterward` and `guarded_file_unapproved` in them found nothing. Run on their own at 0056be630, the two of them together at `-j 2`, `scripts/clean-worktrees-test.py` and `scripts/run-gemini-task-from-brief-test.py` both passed. The dispatching agent reported, and this issue has not checked, that the Mac's load average was 4 to 12 during the runs, and that merge-lane-1, which reviews the pull request, allowed the round's push by hand and asked for this issue to be filed.

Run 3's refusal, as the check printed it:

> REFUSED: The round does not pass: these nn-test-suites fail at the round's commit 0056be6304a9 and not at the frozen-head 2a33f5a0ac55, so the round's change broke them: scripts/clean-worktrees-test.py, scripts/run-gemini-task-from-brief-test.py.

The logs are copied to `nedlern@ned-box:/home/nedlern/nedsnodes-logs/analysis/fix-round-check-load-only-test-suite-failures-blamed-on-round-pull-request-4825-2026-11-27/`, which you can open from the Mac at [file:///Volumes/nedhome/nedsnodes-logs/analysis/fix-round-check-load-only-test-suite-failures-blamed-on-round-pull-request-4825-2026-11-27/](file:///Volumes/nedhome/nedsnodes-logs/analysis/fix-round-check-load-only-test-suite-failures-blamed-on-round-pull-request-4825-2026-11-27/). `round-commit-run-1` to `round-commit-run-3` hold each full run's report and suite logs, `frozen-head-rerun-3` holds run 3's frozen-head run, `check-run-3-output-tail.txt` holds the end of run 3's check output, and `round-commit-two-suites-by-themselves` holds the passing run of the two suites.

## Why it matters

The check exists to stop a round that breaks a suite from being pushed under review. When it refuses a round that broke nothing, the round waits: a full run of the suites takes several minutes per retry, and the push then needs a merge-lane to allow it by hand. That stops work beyond the failing suite, and it teaches authors and merge-lanes to override the check, which then lets real breakage through.

## Root cause

The check compares the round's commit with the frozen-head under different load: the full run at the round's commit, a small run at the frozen-head. A suite that passes at one head and fails at the other is blamed on the round, though the difference may come from the load and not from the commit.

Tests that fail on a busy machine are a cause of their own, tracked in GHI [Tests that time work against a wall-clock limit sized to an idle machine fail when ned-box is busy](https://github.com/nedsnodes/nedsnodes/issues/1830). Fixing them removes these triggers, but the check would still blame the round for the next suite that fails only under load, so the comparison needs its own fix.

## Next action

Change `suites_the_round_broke_and_suites_failing_at_frozen_head_too` so that the round's commit and the frozen-head are compared under the same conditions:

1. After the full run at the round's commit, run the suites that failed there again, in a new scratch worktree of the round's commit made by `failing_suites_in_scratch_worktree`, with the command the frozen-head run uses today: `scripts/run-all-test-suites.py --leave-recorded-inputs-and-failure-history-unchanged --wait-for-lock-seconds <seconds> --only-suites-named <suites>`. A run that stops before judging every suite is handled as `failing_suites_in_scratch_worktree` already handles it, with `StepFailed`.
2. Run at the frozen-head, in the same way, only the suites that failed again in step 1 and that the frozen-head has. When no suite failed again in step 1, skip this run.
3. Sort each suite that failed in the full run into one of three outcomes:
   - fails in step 1 and passes at the frozen-head, or the frozen-head does not have it: the round broke it, and the check refuses, as today;
   - fails in step 1 and at the frozen-head: not the round's doing, as today;
   - passes in step 1: not the round's doing; it failed only in the full run.

The check passes when no suite falls in the first outcome. The record file the check writes, named by `PULL_REQUEST_FIX_ROUND_CHECK_TEST_SUITES_ALSO_FAILING_AT_FROZEN_HEAD_RECORD_FILE_NAME`, keeps the two kinds of suite that are not the round's doing apart, and the check's pass output and the merge-lane message name each kind under its own line: "fail at the frozen-head too" for a suite of the second outcome, and "failed only in the full run of the suites, and passed when run again by themselves at the round's commit" for a suite of the third.

In the same pull request:

- change the docstring at lines 120 to 126 of the program to describe the new comparison;
- change the refusal's text: it keeps telling the author to fix the cause in the round's commit, and drops the advice to run the whole check again for a suite that fails only now and then, since the check has then already rerun that suite by itself; a suite that still fails by itself at the round's commit and passes at the frozen-head is the round's to fix, or, when the author judges the cause lies outside the round's change, to report to the merge-lane with its logs, as the refusal says today;
- in `scripts/pull-request-fix-round-author-brief-from-blocking-findings-and-one-commit-every-finding-answered-check-test.py`, add a test whose stubbed runner fails a suite in the full run and passes it in the rerun at the round's commit, and check that `--check` passes, runs nothing at the frozen-head, and names that suite under the "failed only in the full run" line; and keep or add a test in which the suite fails in the rerun at the round's commit and passes at the frozen-head, and check that `--check` refuses.

When GHI [The test runner's history of failing test cases says whether each failure was a caught defect or a flaky failure, keeps a retried attempt's output, and names the pull request](https://github.com/nedsnodes/nedsnodes/issues/2263) lands, the check should record a suite that failed only in the full run there as a flaky failure, instead of keeping a record of its own.
