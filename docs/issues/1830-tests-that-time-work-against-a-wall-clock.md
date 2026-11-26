---
issue: "[Tests that time work against a wall-clock limit sized to an idle machine fail when ned-box is busy](https://github.com/nedsnodes/nedsnodes/issues/1830)"
---

# Tests that time work against a wall-clock limit sized to an idle machine fail when ned-box is busy

## What is wrong

Six test files on main check that an operation finishes fast by comparing elapsed wall-clock time with a fixed limit. Each limit was sized on an idle machine. When ned-box is busy, the code under test is correct but takes longer, so the test fails although nothing is wrong. A false failure blocks a merge or a pre-push run until someone reruns it, and it teaches agents to rerun failing tests rather than read them.

The same kind of check has already failed for real, so this is not a guess about the class:
- PR [Tests that passed only on a quiet machine wait for the event, or count work or CPU time](https://github.com/nedsnodes/nedsnodes/pull/1828), merged 2026-10-22T00:49Z, rewrote five such tests after failures under load, among them the shell-reader redirection case that failed on ned-box at main 35f494ca.
- On 2026-10-21, `scripts/pull-request-review-plan-test.py` failed ned-box's daily full test run with a 10-second subprocess timeout; commit b4ada4e49 raised that limit.
- Closed issues [Two test cases that fail on a busy machine and pass on rerun](https://github.com/nedsnodes/nedsnodes/issues/1112) and [The Codex task runner's deadline test case fails on a busy machine](https://github.com/nedsnodes/nedsnodes/issues/1323) fixed three more cases between them.

How busy ned-box gets: on 2026-10-21 its load average reached 15 to 19.

None of the checks below has been seen to fail falsely yet; each is judged from reading the code.

## The checks

Line numbers are on main at adb96dc59. The last column names the agent-seat whose commit last changed the file, which owns the rewrite.

| File | Line | What it times | Limit | Owner |
|---|---|---|---|---|
| `nn-systems/handoff/tests/handoff-supervisor-session-launch-and-seat-lock-test.py` | 985, 1005 | a held lock makes the update skip at once | 0.5 s | reboot-test |
| same file | 925 | a hung update is killed at its timeout | 15 s | reboot-test |
| `scripts/markdown-edit-hard-wrapped-paragraph-reminder-hook-hack-test.py` | 337 | judging a 1.6 MB Markdown file | 5 s | agent-instructions-editor |
| `scripts/style-guide-word-checker-markdown-edit-hook-hack-test.py` | 567 | a 60 KB run of text with no whitespace before a hit | 5 s | agent-instructions-editor |
| `scripts/git-client-side-hooks-pre-push-test.py` | 975, 1257 | a hung test run does not hold the push (`HANGING_CASE_WALL_CLOCK_LIMIT_SECONDS`, line 91) | 15 s | reboot-test |
| `scripts/launch-claude-mac-test.py` | 480, 1034, 1065 | a skipped launch finishes; a stopped terminal is stopped at its timeout; a command whose streams are closed is stopped at its timeout | 15 s | reboot-test |
| `scripts/launch-claude-ubuntu-test.py` | 1068, 1100 | with another update holding the lock, the seat is still prepared without hanging; a command whose streams are closed is stopped at its timeout | 15 s | reboot-test |

The two 0.5-second limits are the likeliest to fail.

## Load test of the hung-update row

The hung-update row is now at lines 1117-1137 of the handoff supervisor test file on main at c64990f57. PR [GHI 1830: handoff-supervisor, pre-push hook and launch-claude test suites stop failing timed work on a wall-clock limit](https://github.com/nedsnodes/nedsnodes/pull/2956) gave it the timeout form that What to do asks for: the case asserts status 124 and the "was stopped" message, and its one elapsed-time check, `elapsed < hung_update_backstop_seconds`, is a backstop of 15 times the 1-second timeout. Codex finding bbab0f2a6d44, raised in merge-lane-1's round-1 review of [PR 4972](https://github.com/nedsnodes/nedsnodes/pull/4972) (`nedlern@ned-box:/home/nedlern/nedsnodes-logs/seats/merge-lane-1/review-4972-r1.json`), judged from the code alone that this backstop can still fail when ned-box is busy. On 2026-11-25 merge-lane-1 ran the test file twice on ned-box, which has 16 CPUs, with 48 `yes` CPU hogs added on top of a load average near 22; the load average rose to about 60, and both runs passed. Ten direct calls of `run_agent_binary_update_under_lock` with the same stub agent and the same timeout, made under the same load, each returned 124 within 1.04 s. Only an injected stall failed the bound: a standalone script that makes the same call, paused with SIGSTOP for 15 s, returned 124 after 15.37 s, which the test's backstop would count as a failure although the timeout worked. So CPU load did not make this check fail; a pause of about 14 s in the test process would. This row therefore counts as rewritten for the closing condition under What to do. PR 2956's commit message says it also rewrote the held-lock row of this file and the rows of the pre-push hook and the two launch-claude test files; this section checked none of those, so the table above still lists them as they stood at adb96dc59.

## What to do

merge-lane-2 sends each owner this issue's link. For each check it owns, the owner rewrites the check so that load cannot fail it, keeping what it proves:
- where the check proves that something does not wait, assert that the waiting step was never reached, by counting calls or reading a marker, rather than timing it;
- where it proves that a timeout fires, assert the timeout's own outcome, such as its exit status or the killed process, and keep a wall-clock limit only as a backstop at least ten times the timeout and below the suite's own time limit;
- where it proves that work does not grow too fast with input size, as the two hook rows do, run the hook on the large input and on one a quarter its size, and compare their CPU times, as PR 1828 did for the shell reader.

Show each rewritten check still catches its defect with a mutant, as PR 1828 did. An owner who shows a limit is safe under load leaves that check as it is, and records why in this issue's GHI-MD with the edit-GHI operation.

The owner's pull request names this issue. When the last row is rewritten or recorded as safe, merge-lane-2 records the outcome in the GHI-MD and closes the issue.
