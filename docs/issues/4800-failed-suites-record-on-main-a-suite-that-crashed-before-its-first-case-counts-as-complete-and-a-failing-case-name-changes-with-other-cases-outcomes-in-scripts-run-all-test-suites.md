---
issue: "[Failed suites record on main: a suite that crashed before its first case counts as complete, and a failing case's name changes with other cases' outcomes, in `scripts/run-all-test-suites.py`](https://github.com/nedsnodes/nedsnodes/issues/4800)"
---

# Failed suites record on main: a suite that crashed before its first case counts as complete, and a failing case's name changes with other cases' outcomes, in `scripts/run-all-test-suites.py`

## What goes wrong

The failed suites record is the record of tests failing on main that `scripts/merge-lane-failed-after-merge-test-suites-on-main-record.py` keeps, and that `scripts/merge-lane-pull-request-merge-through-merge-gate-with-stacked-pull-request-retarget.py` updates after each merge. To update it, the merge program reads the JUnit XML file that `scripts/run-all-test-suites.py` writes for the after-merge test run: each `testsuite` element carries a `ran_to_the_end` attribute and one `testcase` element per case. The merge program adds each newly failing case, and removes a recorded case that passed, or whose suite ran to the end and reported nothing for it (its function `why_it_leaves`). Three defects in the runner make the record or the XML wrong. Each was reproduced on main at a8ca00d83 by loading the runner as a module and calling the function named, with the inputs written out below.

1. **A suite that crashed before its first case counts as having run to the end.** `test_suite_ran_to_the_end` (line 2973) returns `True` for any suite with no case lines (`if not result.get("cases") or result["exit"] == 0: return True`), whatever its exit code, before it reads the log for an uncaught Python traceback. Called with `{"exit": 1, "cases": [], "log": <a file holding "Traceback (most recent call last):" and "ImportError: no module named y">}`, it returns `True`. When a suite whose cases are on the record crashes on import, the merge program then removes every one of those cases with the reason "its suite ran to the end and reported nothing for it", although none of them ran, and the record keeps only one failing case named after the suite. The function's docstring says a suite that "printed an uncaught Python traceback" stopped partway, so the code contradicts it.

2. **A failing case's name depends on whether the suite's other cases ran.** `test_cases_with_failing_case_names_resolved_against_the_suites_other_case_names` (line 2940) names a FAIL case by the shortest part of its line, ending before a `": "`, that no PASS case of the suite has as its name or name prefix and that no other FAIL line starts with. For the FAIL line text `task: reads metadata: AssertionError`, it gives the name `task: reads metadata` when the suite also has a PASS case `task: checks timing`, and the name `task` when that case did not run, such as when it was skipped. The record then sees a different case: it removes the old entry and adds a new one, and the merge program opens a new repair task for the same failure.

3. **The JUnit `tests` total leaves out skipped cases.** `write_case_times_suite_resources_and_junit_xml_of_run` (line 2994) writes one `testcase` element for each SKIP line, but sets `tests` to the number of case lines (or 1 for a suite with none), plus one for a failure after the last case line. For a suite with one FAIL case and one SKIP line it writes `tests="1"` and two `testcase` elements. A search of `scripts/` and `nn-systems/` for code reading a `tests` attribute (`grep -rn 'get("tests")\|\["tests"\]'`, excluding tests, on 2026-11-25) found no reader of this total, so today nothing acts on the wrong number.

## Who owns it

overall-cleanup wrote all three in commit 56a426360, "Failed-test record: name each case in full, judge each suite by whether it ran to the end, and choose the closing message once every step is done", the last commit to touch each of the lines above (`git log -L` on main at a8ca00d83).

## Source

The Codex review cell found all three while reviewing [pull request 4559](https://github.com/nedsnodes/nedsnodes/pull/4559) round 3 against base 4a86860beda3, as findings on code that pull request does not change: "Keep recorded failures when a suite crashes before its first case" (P2), "Give failing cases names that stay stable across runs" (P2) and "Include skipped cases in the JUnit test total" (P3). The report is `nedlern@ned-box:/home/nedlern/nedsnodes-logs/seats/merge-lane-2/merge-helpers/cx/pr4559-4a86860b/codex-code-review-report.md`. merge-lane-2's [review 6050958787](https://github.com/nedsnodes/nedsnodes/pull/4559#pullrequestreview-6050958787) left them out of that pull request's grading because the pull request does not trigger them.

## Next action

overall-cleanup fixes the three in one pull request, with a test for each that fails on main:

1. In `test_suite_ran_to_the_end`, return `False` for a suite with no case lines and a nonzero exit, so that the merge program keeps its recorded cases; a suite with no case lines that exits 0 still ran to the end. Check that a suite that prints no case lines by design, and is recorded as one case named after the suite, is still added to and removed from the record as before.
2. Give each failing case a name that does not depend on which other cases ran, such as the case line's text up to a separator the case-line format fixes, and have the merge program's test feed it a record holding names in the old form, so the change neither drops nor duplicates entries already on the record.
3. Count the SKIP `testcase` elements in the `tests` attribute, and assert in the runner's test that `tests` equals the number of `testcase` elements.

Read GHI [The test runner's history of failing test cases](https://github.com/nedsnodes/nedsnodes/issues/2263) before changing how a failing case is named, since it records failing cases by name too, and GHI [Failed suites record keeps the main commit whose after-merge test run recorded a failure first](https://github.com/nedsnodes/nedsnodes/issues/4788), which changes the same failed suites record.
