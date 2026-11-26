---
issue: "[Open-pull-request watcher baseline counts undelivered event lines as delivered](https://github.com/nedsnodes/nedsnodes/issues/4780)"
---

# Open-pull-request watcher baseline counts undelivered event lines as delivered

## What goes wrong

`scripts/merge-lane-open-prs-watch-and-reviewer-assign.py`, run with `--poll-once` by the one-minute cron job, keeps one state file beside its event file. That state file holds two different things: the snapshot of the open pull requests (`pull_requests`, with each one's head commit and draft flag), and the delivery progress of the event file (`event_lines_delivered`, the number of event-file lines that an events task on merge-lane-2's task list has already named). Each run that finds new lines and may open an events task names lines `event_lines_delivered + 1` to the file's line count in that task, with the description "Read lines N to M of <event file path>.", then sets `event_lines_delivered` to the line count.

When the state file is missing or unreadable, the run stops and tells the operator to move it aside and run the program with the command-line option `--poll-once-write-baseline`. That option, carried out by the function `poll_once_write_baseline`, writes a new state file whose `event_lines_delivered` is `event_file_line_count(events_path)`, the event file's full line count (line 994 on main at 71344a302). Any line appended after the last events task opened and before the state file was lost, such as a REVIEW-ASSIGNED line or an OPENED line, is then counted as delivered: no later run names it in an events task, so merge-lane-2 never acts on it unless someone reads the event file by hand.

The cause is that the delivery progress lives in the same file as the snapshot, so losing or replacing the snapshot also loses the delivery progress, even though the event file it counts is still intact.

## What has been done

[Pull request 4774](https://github.com/nedsnodes/nedsnodes/pull/4774), open at the time of writing, at head cc04f218fe3b, leaves the count as it is and adds a sentence to the baseline's WATCH message, where `<event file>` stands for the event file's path: "The baseline also counts every line of <event file> as delivered: read any line no events task named before this baseline." That tells the operator to look, but the program still skips the lines.

This failure is not known to have happened. Search receipt: `scripts/log-store-past-discussions-regex-search-newest-first.py --kind session-dialogs --since 2026-10-01 'poll-once-write-baseline|WATCH: wrote the baseline'`, run on 2026-11-25, found only review discussions of pull requests 4470 and 4774 and the filing of this issue, and no run of the baseline after a lost state file.

## Source

The Codex review cell found this as finding 9e784e395fd9 (P2), "Keep undelivered event lines pending after a new baseline", in merge-lane-3's round-1 review of pull request 4774, [review 6060287411](https://github.com/nedsnodes/nedsnodes/pull/4774#pullrequestreview-6060287411), anchored at line 1023 of the watcher at that head. The review graded it file-for-later: main has it, pull request 4774 only adds the WATCH message sentence that the review of [pull request 4470](https://github.com/nedsnodes/nedsnodes/pull/4470) asked for, and keeping confirmed delivery progress apart from the pull-request snapshot is an improvement for later.

## Next action

First run `gh pr view 4774 --repo nedsnodes/nedsnodes --json state`: while pull request 4774 is open, leave this issue as it is, because that pull request changes the same function. Once it has merged or closed, decide whether the fix is worth its code under the rule for guards in `CLAUDE.md`: the failure needs a lost state file, it has not happened (see the search receipt above; rerun it with a later `--since` first), and its harm is event lines that merge-lane-2 never acts on. If it is not worth its code, close this issue as not planned, recording why in this GHI-MD.

If it is worth its code, have `--poll-once-write-baseline` find the delivery progress somewhere that losing the state file does not lose. Two ways, the first needing no new file:

1. Read it from the events tasks: take the highest M from the descriptions "Read lines N to M of <event file path>." of the events tasks in the task list directory, which `open_task_with_subject_exists` already lists by their subject. That completed tasks stay in that directory as files is unverified; check it first.
2. Keep it in a file of its own beside the event file, which every `--poll-once` run reads and the events-task step writes, and drop `event_lines_delivered` from the state file and from the checks in `poll_state_read`. A delivery file that exists but cannot be read stops the baseline with a repair message, as an unreadable state file stops a run, rather than falling back to the full line count.

Either way, use the event file's full line count only when no delivery record exists at all, as on the very first baseline. Then drop the sentence pull request 4774 adds to the baseline's WATCH message, and update the module docstring's account of the state file. Add a test that runs a poll which opens an events task, appends further event lines, removes the state file, runs `--poll-once-write-baseline`, and checks both that the next run names the appended lines in an events task and that the baseline's WATCH output no longer says every line is counted as delivered.
