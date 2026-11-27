---
issue: "[Open-pull-request watcher: a pull request can be assigned a review lane with no REVIEW-ASSIGNED line, because the assignment and its event line are two writes with no pending record between them](https://github.com/nedsnodes/nedsnodes/issues/4867)"
---

# Open-pull-request watcher: a pull request can be assigned a review lane with no REVIEW-ASSIGNED line, because the assignment and its event line are two writes with no pending record between them

## What goes wrong

`scripts/merge-lane-open-prs-watch-and-reviewer-assign.py`, run with `--poll-once` by merge-lane-2's one-minute cron job, gives each open pull request that has no review lane yet a merge-lane agent-seat to review it. It does this in two writes. First, `merge_lane_pull_request_review_assignment_lines` replaces the assignment file with one that adds a `<number> <merge-lane agent-seat>` line for each pull request it dealt. Then its `record_assigned_lines` callback, `record_with_this_polls_events` in `poll_once`, appends one `PR #<number> REVIEW-ASSIGNED <merge-lane agent-seat>` line per pull request to the event file, which merge-lane-2 reads through its events tasks and forwards to the lanes. A pull request already in the assignment file is never dealt again, so a pull request that reaches the assignment file but not the event file stays assigned to a lane that is never told.

Since [PR 4848, Open-pull-request watcher: a run that cannot append its REVIEW-ASSIGNED lines puts the assignment file back](https://github.com/nedsnodes/nedsnodes/pull/4848) merged on 2026-11-25, a failed append puts the assignment file back as it was, so the next run that can append deals those pull requests again. Two cases are still not covered (line numbers on main at 2c42b2d19):

1. The invocation is killed, or the machine stops, after the assignment file is replaced (line 743) and before the append returns (line 1095). Nothing puts the file back. Codex's review of that pull request showed this with an in-memory poll interrupted at the event-file open, at both the pull request's base commit and its nn-head-commit: Codex finding 5ab29b6c8898 (P1).
2. The append fails and putting the file back fails too (lines 761-770), while a failure task with the subject "Open-pull-request watcher cron job failed: it could not record or deliver events" is still open from an earlier run. The raised error names the pull requests to forward by hand, but `failure_reported` (line 990) opens no second task under the same subject, so that list reaches only cron's standard error, which no agent reads. Codex showed this in an in-memory poll with a second append failure and a failed put-back: Codex finding 0e9d844fe322 (P2), in the same review.

Neither case is known to have happened (unverified: the cron log was not searched). Each leaves one pull request unreviewed until someone notices that it never got a review, and the cron job runs every minute, so a kill during a deploy or reboot is the likelier of the two.

The cause is that the program keeps no record that a deal is pending between the two writes, so neither a later run nor a reader can tell that a line is owed.

## What to do

Keep a record of each deal that is still owed its REVIEW-ASSIGNED line, so a later `--poll-once` invocation finishes what a killed or failed one left. The assignment file alone cannot serve as that record: on 2026-11-25, 153 open pull requests were in the live assignment file, `/home/nedlern/nedsnodes-logs/seats/merge-lane-2/merge-lane-pr-review-assignments.txt`, with no REVIEW-ASSIGNED line in the live event file, because the one-time seed wrote their lines without event lines, so a check of the assignment file against the event file would forward all of them again. One way, which whoever builds it may replace with a better one:

- Before replacing the assignment file, write the batch's REVIEW-ASSIGNED lines, together with any lines the file still holds, to an owed-lines file beside the event file, whole, through a temporary file, `os.fsync` and `os.replace`. When that write fails, deal nothing in this invocation, as when the assignment file cannot be written.
- At the start of every `--poll-once` invocation that deals reviews, under the assignment file's lock: when the owed-lines file exists, keep each of its lines whose pull request the assignment file holds with the same merge-lane agent-seat, and which no line of the event file ends with once the event file's leading UTC time is set aside; append those with this invocation's other event lines; and remove the owed-lines file once the append returns. A line for a pull request the assignment file does not hold is dropped, because that deal never reached the file. A whole-line comparison does not count a line a crash cut short.
- An owed-lines file that cannot be read stops the invocation with a repair message, as an unreadable state file does. One that cannot be removed is left for the next invocation, which finds its lines already in the event file and appends nothing.
- The put-back after a failed append is then no longer needed: drop it, and drop the error text that names pull requests to forward by hand.
- `--poll-once-write-baseline` writes no event line, so it leaves the owed-lines file for the next invocation.

Keep this owed-lines file next to the delivery record that [GHI 4780, Open-pull-request watcher baseline counts undelivered event lines as delivered](https://github.com/nedsnodes/nedsnodes/issues/4780) plans, and build both on one reader and writer if both are built, rather than two unrelated records.

Add tests that cause each case: an invocation interrupted after the assignment file is replaced, then a normal invocation, which must append each owed REVIEW-ASSIGNED line once; an invocation whose append fails, then a normal invocation, with the same check; and an invocation interrupted after the owed-lines file is written and before the assignment file is replaced, after which no line is appended.

Before building, apply the rule for guards in `CLAUDE.md` again: search the cron log, `nedlern@ned-box:/home/nedlern/.claude/merge-lane-open-prs-watch-and-reviewer-assign-poll-once.log`, for the text "could not be put back as it was", and ask merge-lane-2 whether any pull request went unreviewed for lack of a REVIEW-ASSIGNED line. If neither case has happened and none is foreseeable within the next 30 days, close this GHI as not planned, recording why here.
