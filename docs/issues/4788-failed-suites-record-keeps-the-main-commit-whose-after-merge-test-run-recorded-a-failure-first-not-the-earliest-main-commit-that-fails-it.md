---
issue: "[Failed suites record keeps the main commit whose after-merge test run recorded a failure first, not the earliest main commit that fails it](https://github.com/nedsnodes/nedsnodes/issues/4788)"
---

# Failed suites record keeps the main commit whose after-merge test run recorded a failure first, not the earliest main commit that fails it

Every line number below is in the file it cites, as that file is on main at `f054d6977`; the merge program is `scripts/merge-lane-pull-request-merge-through-merge-gate-with-stacked-pull-request-retarget.py`, and the record module is `scripts/merge-lane-failed-after-merge-test-suites-on-main-record.py`.

## What goes wrong

The merge program runs an after-merge test run on each merge commit and keeps main's failing tests in the failed suites record, the JSON file that the record module reads and writes. Each failing test on the record holds a `commit` field, which the record module's docstring (lines 14-15) describes as "the merge commit whose after-merge test run first failed it".

The field holds something else when two after-merge test runs of main overlap. The merge program's own docstring (lines 45-47) says such overlaps happen, "such as a scheduled merge and one by hand". Take an earlier main merge commit A and a later one B, both failing the same test, where the test run of B finishes first:

1. The test run of B finds the test absent from the record and adds it with `"commit": merge_commit`, which is B (line 823).
2. The test run of A finds the test already on the record, so the test is not new and `commit` is not written again. In `why_it_leaves`, `observed_at(suite, test, fields, True)` (lines 753-763) returns False, because `last_failed_commit`, B, is not an ancestor of A, so `last_failed_commit` stays B too.

The record therefore names B, the commit whose test run recorded the failure first, although A, an earlier commit, fails the test too.

For a merge into main nothing goes wrong, because main holds both commits. For a merge into a branch other than main, `failed_tests_main_does_not_fail_named` (lines 865-939) counts a failed test as main's only when the branch holds the recorded `commit` (line 938). A stacked branch that left main between A and B holds A but not B, so the program counts main's failure as the branch's own and prints the branch STOP ("failed tests that are not main's failures"), exit 3, telling the author to fix on the branch a test that main already fails.

The cause is that the record writes `commit` once, from whichever test run records the test first, and nothing lowers it when a test run of an earlier commit later fails the same test.

## What has been done

[Pull request 4783](https://github.com/nedsnodes/nedsnodes/pull/4783), open at the time of writing, adds to the branch STOP a paragraph for each failed test whose recorded `commit` the branch lacks: the paragraph names this case and tells the reader to run the suite at the commit where the branch left main, which `git merge-base <merge commit> origin/main` prints, to learn whether the failure is main's. That detects the case by hand; the program still gives the wrong verdict.

Whether this failure has happened is not known (unverified): no search of the after-merge test run logs was made for a branch STOP whose failed test was on the record.

## Source

The Codex review cell found this as finding 20bf0da70a60 (P2), "Track main failures in commit order, not completion order", in merge-lane-3's round-1 review of pull request 4783, [review 6060797392](https://github.com/nedsnodes/nedsnodes/pull/4783#pullrequestreview-6060797392), anchored at lines 947-950 of the merge program at that pull request's nn-head-commit `6c03fd761411`. The review says Codex reproduced the failure in memory; it does not say how. The review graded it file-for-later: main has it, pull request 4783 does not cause it, and merge-lane-2 asked on [pull request 4761](https://github.com/nedsnodes/nedsnodes/pull/4761) for detection (Codex finding e0c221fcae63), which pull request 4783 adds.

## Related

[GHI 3953](https://github.com/nedsnodes/nedsnodes/issues/3953), open, is about the same program's after-merge test run, and one of its options would refuse the next merge while main's latest after-merge test run failed, reading the failed suites record. Read `docs/issues/3953-a-pull-request-at-the-no-reviewer-review-tier-runs-no-head-test-run-so-a-markdown-change-that-a-test-suite-reads-can-break-main.md` before changing what the record stores.

## Next action

First run `gh pr view 4783 --repo nedsnodes/nedsnodes --json state`: while pull request 4783 is open, leave this GHI as it is, because that pull request changes the same function. Once it has merged or closed, fix the cause, as `CLAUDE.md` says for a cause in this project's own code: keep, for each test on the record, the earliest main commit known to fail it. Leave `commit` and the fields that belong to the repair task (`pull_request`, `log`, `failed_at`, `repair_task_agent_seat`, `repair_task_id`) as they are, because the repair task and the merge-gate notice, which prints `commit` and `pull_request` together (record module line 107), name the merge whose test run recorded the failure, and that merge's author holds the repair task.

1. Add the field `earliest_failed_commit` to each recorded test, and add it to `TEST_FIELD_TYPES` (record module line 31). A record file written before the field existed is read with `earliest_failed_commit` taken as the test's `commit`. A new test on the record gets the run's merge commit, as `commit` does (line 823).
2. In `failed_suites_kept_in_view`, when a test run fails a test already on the record and the run's merge commit is a strict ancestor of the recorded `earliest_failed_commit`, set `earliest_failed_commit` to the run's merge commit; when the two commits are the same, as in a rerun, change nothing. When git cannot say whether one is an ancestor of the other, record the test in `undecided`, as `observed_at` (lines 753-763) does, and leave the field as it is.
3. In `failed_tests_main_does_not_fail_named`, test ancestry against `earliest_failed_commit` instead of `commit` (line 938). Keep the paragraph pull request 4783 adds: a branch merged while the earlier commit's test run is still running still lacks the commit on the record, so the paragraph can still be reached.
4. Correct the record module's docstring (lines 14-15): `commit` is the merge commit whose after-merge test run recorded the test first, and `earliest_failed_commit` is the earliest main commit known to fail it.

Add a test that records a failure from the test run of a later commit, then fails the same test in the test run of an earlier commit, and checks that the record's `earliest_failed_commit` is the earlier commit while `commit` stays the later one, and that a merge into a branch holding only the earlier commit counts the failure as main's.
