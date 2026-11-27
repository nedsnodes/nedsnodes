---
issue: "[Make `scripts/log-store-session-dialogs-refresh-hack.py` deletable without breaking the scheduled-jobs installer or its test](https://github.com/nedsnodes/nedsnodes/issues/5281)"
---

# Make `scripts/log-store-session-dialogs-refresh-hack.py` deletable without breaking the scheduled-jobs installer or its test

Deleting `scripts/log-store-session-dialogs-refresh-hack.py` today breaks two files that do not end in the -hack suffix: the scheduled-jobs installer, `nn-systems/general-tools/install-scheduled-jobs-on-this-machine.py`, and its test, `nn-systems/general-tools/tests/install-scheduled-jobs-on-this-machine-test.py`. This GHI asks that they stop depending on the hack, so that the hack can be deleted on its own and they keep working. The owner is the agent-seat cold-read-research, which owns the hack's scheduled job. Its approval-walk category is fix-during-maintenance: nothing is broken or lost today, no one has deleted the hack, and no open pull request deletes it.

## Why this is a defect

The hack is nn-hack code, because its name ends in the -hack suffix. The entry for nn-hack in the project glossary, `docs/nedsnodes-wiki/nedsnodes-glossary.md`, sets four limits on nn-hack code. One of them is that "deleting it, or reverting the pull request that added it, leaves nothing broken behind". The same entry also says: "Code that needs nn-hack code in order to work is nn-hack too." The reviewer instructions, `docs/agents/pr-reviewer-instructions.md`, apply that rule in their bullet on files with the -hack suffix. That bullet makes it a blocking finding when "deleting the file, or reverting the pull request that added it, would leave something broken". It also makes it one when a file without the suffix "needs code from an -hack file in order to work". The installer and its test are both such files.

## What breaks, on main at commit 4d7871d59

Each line number below was checked on main at commit 4d7871d59 on 2026-11-27.

1. The job table, `nn-systems/general-tools/scheduled-jobs-on-each-machine.json`, has a job named `log-store-session-dialogs-refresh` at lines 40 to 48. Its owner is `cold-read-research`, its program is `scripts/log-store-session-dialogs-refresh-hack.py`, and it runs on ned-box from cron every 10 minutes.
2. The installer's `refuse_missing_programs()`, at line 861, raises a refusal when any selected job's program is not a file on the machine. Its one caller, `install_mode()`, calls it at line 881, before it writes any job. The after-merge program, `nn-systems/general-tools/install-scheduled-jobs-on-this-machine-after-reference-checkout-merge-and-report-install-failure-as-task-for-installer-owner-agent-seat.py`, runs the installer with `--install` after each merge into ned-box's reference-checkout. So if the hack's file is gone while its row stays, any install run that selects the job refuses to install any ned-box job, until a pull request removes the row. An install run selects every job of the machine unless it is given `--job`. The after-merge program reports that failure as a task.
3. The installer's test reads and pins the hack in several places:
   - lines 83 to 86 pin the hack's cron line as the constant `NED_BOX_SESSION_DIALOGS_LINE`;
   - the case "the session dialogs refresh runs on ned-box alone, every 10 minutes, and its program documents the table's line", at lines 384 to 392, reads the hack's source with `read_text` at line 391. If the hack's file is gone, that call raises `FileNotFoundError`, so the test file stops at that point and none of its later cases run;
   - the case "every job's program is a file of this repository", at line 393, fails while the row names a missing file;
   - the job-name lists near lines 344 and 378, and the `--print` expectation near line 533, pin the row itself. These do not fail when the file alone is deleted, but a pull request that removes the row must change them.

A pull request that deletes the hack and its row together must therefore also edit the installer's test in all of these places. Leaving those places alone is what the nn-hack rule requires.

Codex finding 1303a727bdd3 reported the defect in merge-lane-3's round-2 review of [pull request 5123, Guarded-file store prune renamed to say it also deletes copies of committed versions](https://github.com/nedsnodes/nedsnodes/pull/5123). The finding's text and evidence are in `nedlern@ned-box:/home/nedlern/nedsnodes-logs/seats/merge-lane-3/pr5123-codex-findings.json`. Codex reproduced the refusal with `python3 -B`, with `Path.is_file()` stubbed so that only the hack reports missing: the installer refused the install before it called any scheduler. The finding records that the defect is already on main, and that pull request 5123 does not cause it. Pull request 5123 changes the job table and the installer's test, but does not delete the hack.

The search that found no open pull request or issue that deletes the hack: `gh pr list --repo nedsnodes/nedsnodes --state open --search "log-store-session-dialogs-refresh-hack"` returned only pull request 5123, and `gh issue list --repo nedsnodes/nedsnodes --state open --search "log-store-session-dialogs-refresh-hack"` returned nothing. Both were run on 2026-11-27.

## Other files that name the hack

These files without the -hack suffix name the hack in their text: `scripts/log-store-past-discussions-regex-search-newest-first.py`, `scripts/log-store-session-dialogs-refresh-common.py`, `nn-systems/cold-read/cold-read-record-ship.py` and `nn-systems/handoff/handoff.system.design.md`. A grep of the three programs for the hack's name found no import or run of it, only text that names it. `scripts/log-store-past-discussions-regex-search-newest-first.py`, and the design in GHI-MD [2118](https://github.com/nedsnodes/nedsnodes/issues/2118), `docs/issues/2118-ruling-agent-keeps-user-rulings-checks-approval-walk.md`, also read the session dialogs that the hack writes into the log-store. Whether depending on the hack's output counts as needing nn-hack code is not settled (unverified); cold-read-research settles it within this GHI and records its answer in this GHI-MD before the GHI closes.

## What to do next

The goal: a pull request that deletes the hack, and with it only files whose names end in the -hack suffix, leaves main's tests passing and every other ned-box job installing. The files it deletes are the program, its own test `scripts/log-store-session-dialogs-refresh-hack-test.py`, and any -hack file the design moves the job's row or test case into. Today that is not possible, because the row and the test case live in the job table and the installer's test, which do not end in the suffix.

Codex proposes separating the hack's row and its test case from the required job table and the installer's test. The exact design is for cold-read-research, which decides, among other things:
- where the row and the test case go, for example into a file with the -hack suffix that the same installer reads beside the job table. ghi-guide-agent advised that the design keep the one installer and the one table format, which GHIs [1058](https://github.com/nedsnodes/nedsnodes/issues/1058) and [3075](https://github.com/nedsnodes/nedsnodes/issues/3075) build on, rather than add a second installer;
- whether the change handles every job whose program ends in the -hack suffix, or this job alone. It is the only such job in the table today;
- what the installer does when a hack job's program is missing. Whatever it does, it reports the missing program where an agent or the user will see it, and does not hide it.

One option for the installer's test, from the cold-read-fast-read of this GHI-MD: build the job-name lists and the `--print` expectation from the table rather than copying the rows by hand, so removing a row needs no edit to the test. Another: a test that, for every job whose program ends in the -hack suffix, stubs the program as missing and checks that the installer still installs the other jobs.

The next action for cold-read-research is to choose the design, and then to open the pull request that makes it. That pull request includes a test that stubs the hack's -hack files as missing, and shows that the installer still installs every other ned-box job and that the installer's test still passes.

## Approval

The user approved filing this GHI. He answered A to item 1 of 2 of merge-lane-3's approval-walk merge-lane-3-scheduled-jobs-refresh-hack-row-ghi-question-approval-walk-2026-11-27. The walk-minutes record that answer at 2026-11-27 06:30Z, on line 7 of `nedlern@ned-box:/home/nedlern/agents/merge-lane-3/docs/walk/merge-lane-3-scheduled-jobs-refresh-hack-row-ghi-question-approval-walk-2026-11-27-minutes.md`. The item's text is the version directly under the heading "## Item 1 of 2", at line 3 of `nedlern@ned-box:/home/nedlern/agents/merge-lane-3/docs/walk/merge-lane-3-scheduled-jobs-refresh-hack-row-ghi-question-approval-walk-2026-11-27.md`; the withdrawn versions follow it.

[ghi-guide-agent](https://github.com/nedsnodes/nedsnodes/issues/46), asked on 2026-11-27 with `--include-closed`, read GHIs 3960, 1518, 2118, 1196, 3075 and 1058. It answered that no open or closed GHI covers this defect.
