#!/usr/bin/env python3
"""Merge one pull request through merge-gate.sh, retargeting the pull requests stacked on it first.

Usage:
  scripts/merge-lane-pull-request-merge-through-merge-gate-with-stacked-pull-request-retarget.py <pull request number>
      <nn-head-commit, all 40 characters> <reviewed-since>
      [--merge-lane-worktrees-and-outputs-directory DIR] [--merge-lane-review-worktrees-directory DIR] [--review-tools-worktree-at-main DIR]

Runs --review-tools-worktree-at-main's scripts/merge-gate.sh, never the pull
request's own copy, with the three arguments. While the gate
refuses with "mergeStateStatus is UNKNOWN", it runs the gate again, 5 seconds
apart, at most 8 times in all. When the gate passes, the merge command it
prints must be exactly the one this program expects; then every open pull
request whose base branch is this pull request's branch is retargeted to this
pull request's base branch, and the merge command runs. While the merge
command fails with GitHub's "Base branch was modified. Review and try the merge
again.", which GitHub gives when another merge moves the base branch during
this one, the program runs the merge command again, 5 seconds apart, at most 3
times in all. Whether the pull
request merged is decided by the state the program then reads from GitHub,
not by the merge command's exit code: a GitHub error after the merge is done,
such as a 502 on the response, makes the command exit nonzero over a merged
pull request. When it does, the program checks that the pull request's branch
is gone from GitHub, since the command's --delete-branch part may not have
run, and deletes it when it is there. When the state cannot be read, a merge
command that exited 0 counts as a merge. Once the pull request has merged, git in --review-tools-worktree-at-main removes the pull request's
review worktrees, pr<n>-head and pr<n>-merged, with any changes in them; a
worktree not there is left alone.

Then main is tested where the merge changed it: the program fetches the merge
commit alone from origin into --review-tools-worktree-at-main, which updates no
remote-tracking branch, makes a detached worktree pr<n>-merge-commit-on-main-worktree
at the merge commit GitHub reports, and runs that worktree's own
scripts/run-all-test-suites.py --only-suites-whose-recorded-inputs-changed-since
<since>, so only the suites whose recorded inputs changed since a tested tree
run. <since> is the pr<n>-merged commit the head test run passed on: of the
records pull-request-head-test-run.py filed under hr/pr<n>/log-store in the
worktrees and outputs directory, one test log per pr<n>-merged commit, named
by its hash, the program takes each test log whose last record says it tested
that commit and exited 0, and uses the one started last. When there is no
such record, or a test log cannot be read, which the program prints, <since>
is the nn-head-commit, which predates main's newer merges and so selects more
suites, never fewer; the program prints that it fell back. The run's suite logs and test-run-report.txt go in
<merge-lane-worktrees-and-outputs-directory>/pr<n>-after-merge-test-run-logs-<the
merge commit's first 12 characters>. The program prints the run's SUMMARY line,
each failed suite's line, and that directory, then removes the worktree.
In that worktree, before the test run, it adopts into hr/store, the recordings
every merge-lane head test run selects by, each recording that passed and
matches the merge commit's files from hr/pr<n>/recorded-inputs, where this pull
request's head test runs saved their recordings, and then removes that
directory, even when the adoption failed, because no later merge reads it.
Next it adopts the same way from hr/store into the runner's default
recorded-inputs directory, which the after-merge test run selects by: a suite
whose recording there is stale, but whose recording in hr/store matches the
merge commit, such as one the head test run passed on the same files, is then
not selected again. After the run, it adopts from the runner's default
directory, where the after-merge test run saved its recordings, into hr/store.
It prints how many it adopted each time. A failed adoption or removal does not
stop what follows: the program goes on, and exits 3.

After that run the program keeps failed tests in view, in the record of
scripts/merge-lane-failed-after-merge-test-suites-on-main-record.py, whose
notice merge-gate.sh prints. It runs each recorded suite the selective run did
not run, with --only-suites-named, and reads each test's verdict from the
runs' junit.xml. A recorded test leaves the record when it passes; when its
suite ran to the end, at a later commit than the one where the test last
failed, and reported nothing for it, not even a skip; or when git no longer
lists its suite at the merge commit. It prints the name of each test that
leaves. Each failed test not yet recorded joins it, and those tests together
get one repair task, on the task list of the agent-seat that authored the
merged branch's last commit. When that agent-seat has no task list or no
checkout, no task is opened and the STOP message says to ask the user. A
merge whose only failures are tests already recorded, with every suite run
to the end and every step done, prints a notice and exits 0, because their
repair task is already open; a new failed test in a recorded suite exits 3.

The merge command deletes the pull request's branch, and GitHub closes every
open pull request whose base branch is deleted. The retarget is here, not in
merge-gate.sh, because the gate only reads GitHub and its callers may run it
without merging; a retarget belongs just before a merge that is about to run.

Every gh call runs with GH_TOKEN read from the merge account's token file,
the file merge-gate.sh reads, so the gate, the retargets and the merge use one
token.

Before the gate runs, this program fetches origin in
--review-tools-worktree-at-main and checks that worktree out, detached, at
origin/main, so a stale worktree never lets an older gate decide a merge. It
refuses instead when the worktree holds work of its own, which a checkout
could lose or carry along: a branch checked out, a HEAD that is not an
ancestor of origin/main, a change to a tracked file, or a merge, rebase,
cherry-pick, revert or bisect in progress. Untracked files, ignored ones
included, stay: where origin/main tracks a path such a file is at, git
refuses the checkout and the program stops. A review whose Codex cell runs
from the same worktree at the same time may fail when the checkout moves
files under it; such a review is run again.

Last, once the pull request has merged, the program runs
merge-lane-open-prs-not-changes-requested-count-then-next-agent-seat-go-ahead-to-open-surviving-mutant-test-prs.py,
beside it, with the merge account's GH_TOKEN, and prints what it printed:
`RELEASED <agent-seat>` when it sent that agent-seat the release message, what
failed when it could not, or the count of pull requests waiting for merge-lane-2. When it exits 2 or another code it does
not document, the program prints that too; the exit code below never depends
on it.

Exit codes: 0 merged, with the review worktrees removed, and main's after-merge
test run passed; 1 the gate refused,
printed a merge command other than the expected one, or the pull request is
not merged after the merge command ran; 2 the token file could not be read or
was empty, --review-tools-worktree-at-main has no scripts/merge-gate.sh, could
not be fetched, holds work of its own or could not be checked out at origin/main, the gate could not run or exited with
a code it does not document, or a read or a retarget on GitHub failed, each
before any merge; 3 merged, but a step after the merge was not done: a review
worktree or the pr<n>-merge-commit-on-main-worktree worktree could not be removed, the
pull request's branch could not be read or deleted after a merge command that exited
nonzero, the after-merge test run did not pass, because a test not already on the failed
suites record failed, a suite did not run to the end, the runner gave no full verdict, or the
merge commit could not be read or its worktree made, or recordings could not be adopted, or
hr/pr<n>/recorded-inputs could not be removed, or the failed suites record could not be read
or written, its suites could not be run again, or a repair task could not be opened;
stdout names which; 4 the merge command exited nonzero and the pull request's state
could not be read, so whether it merged is unknown: read its state before doing
anything else.
"""

import argparse
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import time
import xml.etree.ElementTree
from pathlib import Path

_common_spec = importlib.util.spec_from_file_location(
    "merge_lane_pull_request_helpers_common", Path(__file__).resolve().with_name(
        "merge-lane-pull-request-helpers-common-options-paths-and-token.py"))
common = importlib.util.module_from_spec(_common_spec)
_common_spec.loader.exec_module(common)
_head_test_run_spec = importlib.util.spec_from_file_location(
    "pull_request_head_test_run", Path(__file__).resolve().with_name(
        "pull-request-head-test-run.py"))
head_test_run = importlib.util.module_from_spec(_head_test_run_spec)
_head_test_run_spec.loader.exec_module(head_test_run)
_failed_suites_record_spec = importlib.util.spec_from_file_location(
    "merge_lane_failed_after_merge_test_suites_on_main_record", Path(__file__).resolve().with_name(
        "merge-lane-failed-after-merge-test-suites-on-main-record.py"))
failed_suites_record = importlib.util.module_from_spec(_failed_suites_record_spec)
_failed_suites_record_spec.loader.exec_module(failed_suites_record)
_task_write_spec = importlib.util.spec_from_file_location(
    "agent_seat_task_list_new_pending_task_write_common",
    Path(__file__).resolve().parents[1] / "nn-systems" / "general-tools"
    / "agent-seat-task-list-new-pending-task-write-common.py")
task_write = importlib.util.module_from_spec(_task_write_spec)
_task_write_spec.loader.exec_module(task_write)

REPOSITORY = common.REPOSITORY

# merge-gate.sh keeps this text in the first line of its UNKNOWN refusal.
MERGE_STATE_UNKNOWN_REFUSAL = "mergeStateStatus is UNKNOWN"
MERGE_GATE_TRIES = 8
SECONDS_BETWEEN_MERGE_GATE_TRIES = 5
MERGE_COMMAND_HEADING = "MERGE WITH THIS EXACT COMMAND:"
# GitHub's refusal when another merge moved the base branch during this one; nothing merged.
BASE_BRANCH_MODIFIED_MERGE_REFUSAL = "Base branch was modified. Review and try the merge again."
MERGE_TRIES = 3
SECONDS_BETWEEN_MERGE_TRIES = 5
# The words git prints when a checkout would overwrite files, tracked or untracked.
CHECKOUT_WOULD_OVERWRITE_FILES = "would be overwritten by checkout"
# Present in the git directory while each operation is in progress.
OPERATION_IN_PROGRESS_GIT_PATHS = {
    "MERGE_HEAD": "a merge", "rebase-merge": "a rebase", "rebase-apply": "a rebase",
    "CHERRY_PICK_HEAD": "a cherry-pick", "REVERT_HEAD": "a revert", "BISECT_LOG": "a bisect"}

# gh pr list returns 30 pull requests unless told otherwise; a stacked pull
# request beyond the limit would be missed and then closed by the merge.
OPEN_PULL_REQUEST_LIST_LIMIT = 1000

EXIT_MERGED = 0
EXIT_REFUSED = 1
EXIT_COULD_NOT_RUN = 2
EXIT_MERGED_BUT_A_STEP_AFTER_THE_MERGE_NOT_DONE = 3
EXIT_MERGE_OUTCOME_UNKNOWN = 4
MERGE_GATE_DOCUMENTED_EXITS = (0, 1, 2)
MERGE_GATE = Path("scripts") / "merge-gate.sh"
SURVIVING_MUTANT_TEST_PRS_GO_AHEAD_PROGRAM = Path(__file__).resolve().with_name(
    "merge-lane-open-prs-not-changes-requested-count-then-next-agent-seat-go-ahead-to-open-surviving-mutant-test-prs.py")
# 0 named an agent-seat to release, 3 named none; 1, Python's status for a crash, is not an answer.
SURVIVING_MUTANT_TEST_PRS_GO_AHEAD_ANSWERS = (0, 3)


def parse_arguments(argv):
    parser = argparse.ArgumentParser(
        description="Run merge-gate.sh for one pull request; when it passes, retarget the "
                    "open pull requests based on its branch, then run the merge command the "
                    "gate printed.")
    parser.add_argument("pull_request", help="the pull request's number")
    parser.add_argument("head_commit", help="the nn-head-commit, all 40 characters")
    parser.add_argument("reviewed_since",
                        help="the reviewed-since time merge-gate.sh takes, YYYY-MM-DDTHH:MM:SSZ")
    common.add_directory_options(parser, "the after-merge test runs' logs")
    return common.resolve_path_options(parser.parse_args(argv))


def run(command, environment):
    return subprocess.run(command, capture_output=True, text=True, env=environment,
                          stdin=subprocess.DEVNULL)


git_error = common.run_all_test_suites.git_failure_stderr_first_line_or_printed_no_error_text


def gh_error(completed):
    return completed.stderr.strip() or f"gh exited {completed.returncode} and printed no error"


def merge_gate_after_retries(arguments, environment, wait):
    """Return the last run of the gate, stdout and stderr together."""
    for attempt in range(1, MERGE_GATE_TRIES + 1):
        gate = subprocess.run(
            ["bash", str(arguments.review_tools_worktree_at_main / MERGE_GATE),
             arguments.pull_request, arguments.head_commit,
             arguments.reviewed_since],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=environment,
            stdin=subprocess.DEVNULL)
        if (gate.returncode == 0 or MERGE_STATE_UNKNOWN_REFUSAL not in gate.stdout
                or attempt == MERGE_GATE_TRIES):
            return gate
        print(f"try {attempt}: {MERGE_STATE_UNKNOWN_REFUSAL}", flush=True)
        wait(SECONDS_BETWEEN_MERGE_GATE_TRIES)


def merge_after_retries(command, environment, wait):
    """Return the last run of the merge command."""
    for attempt in range(1, MERGE_TRIES + 1):
        merge = run(command, environment)
        if (merge.returncode == 0 or BASE_BRANCH_MODIFIED_MERGE_REFUSAL not in merge.stderr
                or attempt == MERGE_TRIES):
            return merge
        print(f"merge try {attempt} of {MERGE_TRIES}: GitHub refused the merge because main "
              f"moved during it; this program runs the merge command again in "
              f"{SECONDS_BETWEEN_MERGE_TRIES} seconds", flush=True)
        wait(SECONDS_BETWEEN_MERGE_TRIES)


def review_tools_worktree_moved_to_main_refusal_message(worktree):
    """Fetch origin in worktree and check it out, detached, at origin/main unless it holds
    work of its own; return None when it is at origin/main, else what to do."""
    environment = common.run_all_test_suites.environment_without_git_redirecting_variables()

    def git(*arguments):
        return subprocess.run(["git", "-C", str(worktree), *arguments], capture_output=True,
                              text=True, env=environment, stdin=subprocess.DEVNULL)

    def could_not_read(what, failed):
        return (f"could not read {what} in {worktree}: {git_error(failed)}\n"
                f"Tell the user this message as printed, from its STOP line, which quotes git's "
                f"error, through this line.")

    fetch = git("fetch", "--quiet", "origin")
    if fetch.returncode != 0:
        return (f"could not fetch origin in {worktree}, so whether its merge-gate.sh is "
                f"main's cannot be told: {git_error(fetch)}\n"
                f"Run this again once; if it fails the same way, tell the user this message as "
                f"printed, from its STOP line, which quotes git's error, through this line.")
    head = git("rev-parse", "HEAD")
    main = git("rev-parse", "origin/main")
    if head.returncode != 0 or main.returncode != 0:
        return could_not_read("HEAD and origin/main", head if head.returncode != 0 else main)
    head, main = head.stdout.strip(), main.stdout.strip()
    if head == main:
        return None

    own_work = []
    branch = git("symbolic-ref", "--quiet", "--short", "HEAD")
    if branch.returncode not in (0, 1):
        return could_not_read("whether a branch is checked out", branch)
    if branch.returncode == 0:
        own_work.append(f"the branch {branch.stdout.strip()} is checked out")
    ancestor = git("merge-base", "--is-ancestor", head, main)
    if ancestor.returncode not in (0, 1):
        return could_not_read(f"whether HEAD {head[:8]} is an ancestor of origin/main", ancestor)
    if ancestor.returncode == 1:
        own_work.append(f"HEAD {head[:8]} is not an ancestor of origin/main, so it may hold "
                        f"commits main lacks")
    status = git("status", "--porcelain", "--untracked-files=no")
    if status.returncode != 0:
        return could_not_read("the changes to tracked files", status)
    changed = [line[3:] for line in status.stdout.splitlines()]
    if changed:
        own_work.append(f"a tracked file is changed, such as {changed[0]}")
    names = list(OPERATION_IN_PROGRESS_GIT_PATHS)
    git_paths = git("rev-parse", *(argument for name in names
                                   for argument in ("--git-path", name)))
    if git_paths.returncode != 0:
        return could_not_read("where git keeps its operation state", git_paths)
    for name, git_path in zip(names, git_paths.stdout.splitlines()):
        if (worktree / git_path).exists():
            own_work.append(f"{OPERATION_IN_PROGRESS_GIT_PATHS[name]} is in progress")
    leave_it = (f"Leave {worktree} as it is: do not move, remove, discard, stash or overwrite "
                f"anything in it unless the user tells you to, because it may be someone's "
                f"unsaved work.")
    subagent = "If you are a subagent, ask the agent that dispatched you instead."
    if own_work:
        return (f"{worktree} is at {head[:8]}, not at origin/main {main[:8]}, and holds work "
                f"of its own, so this program does not check out origin/main in it: "
                f"{'; '.join(own_work)}.\n"
                f"{leave_it}\n"
                f"Tell the user that merges stop until that work is kept elsewhere and "
                f"{worktree} is detached at origin/main or an older commit of main, with no "
                f"change to a tracked file and no operation in progress; name the work, and ask how the user wants it "
                f"kept and who does it. Once {worktree} is in that state, run this program "
                f"again, which then checks out origin/main in it itself. {subagent}")
    # By name, not the commit read above: a parallel run may already have moved the worktree
    # to a newer main, and origin/main only moves forward.
    checkout = git("checkout", "--quiet", "--no-overwrite-ignore", "--detach", "origin/main")
    if checkout.returncode != 0:
        could_not_check_out = (f"could not check {worktree} out at origin/main, so its "
                               f"merge-gate.sh may not be main's")
        if CHECKOUT_WOULD_OVERWRITE_FILES in checkout.stderr:
            # Whole, because the files git lists are on the lines after its first.
            return (f"{could_not_check_out}: {checkout.stderr.strip()}\n"
                    f"{leave_it} Do not move or remove the files git lists, whatever git "
                    f"suggests above.\n"
                    f"Tell the user that merges stop until the files git lists are gone from "
                    f"{worktree}; name them, and ask how the user wants them kept and who moves "
                    f"them. Once they are gone, run this program again. {subagent}")
        return (f"{could_not_check_out}: {git_error(checkout)}\n"
                f"Run this program again once; if it fails the same way, tell the user this "
                f"message as printed, from its STOP line, which quotes git's error, through "
                f"this line.")
    print(f"checked out origin/main in {worktree}, which was at {head[:8]}", flush=True)
    return None


def printed_merge_command(gate_output):
    lines = gate_output.splitlines()
    for index, line in enumerate(lines[:-1]):
        if line == MERGE_COMMAND_HEADING:
            return lines[index + 1].strip()
    return None


def stacked_pull_requests_retarget(pull_request, environment):
    """Retarget the open pull requests based on this one's branch.

    Return (exit code, the pull request's branch, None when it could not be read).
    """
    view = run(["gh", "pr", "view", pull_request, "--repo", REPOSITORY,
                "--json", "headRefName,baseRefName"], environment)
    if view.returncode != 0:
        print(f"STOP: not merged: could not read pull request {pull_request}'s branch, so the "
              f"pull requests based on it could not be found: {gh_error(view)}\n"
              f"Run this again once; if it fails the same way, tell the user this message as "
              f"printed, from its STOP line, which quotes gh's error, through this line.")
        return EXIT_COULD_NOT_RUN, None
    branches = json.loads(view.stdout)
    branch, base = branches["headRefName"], branches["baseRefName"]

    listing = run(["gh", "pr", "list", "--repo", REPOSITORY, "--state", "open",
                   "--limit", str(OPEN_PULL_REQUEST_LIST_LIMIT),
                   "--json", "number,baseRefName"], environment)
    if listing.returncode != 0:
        print(f"STOP: not merged: could not list the open pull requests, so those based on "
              f"{branch} could not be found: {gh_error(listing)}\n"
              f"Run this again once; if it fails the same way, tell the user this message as "
              f"printed, from its STOP line, which quotes gh's error, through this line.")
        return EXIT_COULD_NOT_RUN, branch
    stacked = sorted(entry["number"] for entry in json.loads(listing.stdout)
                     if entry["baseRefName"] == branch)
    if not stacked:
        print(f"no open pull request is based on {branch}")
        return EXIT_MERGED, branch

    for number in stacked:
        edit = run(["gh", "pr", "edit", str(number), "--repo", REPOSITORY, "--base", base],
                   environment)
        if edit.returncode != 0:
            print(f"STOP: not merged: could not retarget pull request #{number} from {branch} "
                  f"to {base}: {gh_error(edit)}\n"
                  f"The merge deletes {branch}, and GitHub would then close #{number}.\n"
                  f"Retarget #{number} by hand: gh pr edit {number} --repo {REPOSITORY} "
                  f"--base {base}\n"
                  f"Then run this again.")
            return EXIT_COULD_NOT_RUN, branch
        print(f"retargeted pull request #{number} from {branch} to {base}; if this merge "
              f"does not happen, set it back with: gh pr edit {number} --repo {REPOSITORY} "
              f"--base {branch}", flush=True)
    return EXIT_MERGED, branch


def merged_branch_deleted(branch, environment):
    """Delete the merged pull request's branch from GitHub when it is still there; return
    an exit code."""
    path = f"repos/{REPOSITORY}/branches/{branch}"
    read = run(["gh", "api", path], environment)
    if read.returncode != 0 and "HTTP 404" in read.stderr:
        print(f"the branch {branch} is gone from GitHub")
        return EXIT_MERGED
    by_hand = f"gh api -X DELETE repos/{REPOSITORY}/git/refs/heads/{branch}"
    if read.returncode != 0:
        print(f"STOP: merged, but whether the branch {branch} is gone from GitHub could not "
              f"be read: {gh_error(read)}\n"
              f"If it is still there, delete it: {by_hand}\n"
              f"If that fails, tell the user this message as printed, from its STOP line, which "
              f"quotes gh's error, through this line, and the error the deletion command printed.")
        return EXIT_MERGED_BUT_A_STEP_AFTER_THE_MERGE_NOT_DONE
    deletion = run(["gh", "api", f"repos/{REPOSITORY}/git/refs/heads/{branch}",
                    "-X", "DELETE"], environment)
    if deletion.returncode != 0:
        # GitHub's own deletion for the merge can remove the branch between the read and the
        # delete; a second read tells that apart from a delete that failed, whatever error
        # text the delete got.
        reread = run(["gh", "api", path], environment)
        if reread.returncode != 0 and "HTTP 404" in reread.stderr:
            print(f"the branch {branch} is gone from GitHub")
            return EXIT_MERGED
        if reread.returncode != 0:
            print(f"STOP: merged, but the branch {branch} could not be deleted, and whether it "
                  f"is gone from GitHub could not be read.\n"
                  f"The deletion's error: {gh_error(deletion)}\n"
                  f"The read's error: {gh_error(reread)}\n"
                  f"If it is still there, delete it: {by_hand}\n"
                  f"If that fails, tell the user this message as printed, from its STOP line "
                  f"through this line, and the error the deletion command printed.")
            return EXIT_MERGED_BUT_A_STEP_AFTER_THE_MERGE_NOT_DONE
        print(f"STOP: merged, but the branch {branch} is still on GitHub and could not be "
              f"deleted: {gh_error(deletion)}\n"
              f"Delete it: {by_hand}\n"
              f"If that fails, tell the user this message as printed, from its STOP line, which "
              f"quotes gh's error, through this line, and the error the deletion command printed.")
        return EXIT_MERGED_BUT_A_STEP_AFTER_THE_MERGE_NOT_DONE
    print(f"deleted the branch {branch}, which the merge command left on GitHub")
    return EXIT_MERGED


def review_worktrees_remove(arguments):
    """Remove the pull request's review worktrees; return an exit code."""
    checkout = arguments.review_tools_worktree_at_main
    exit_code = EXIT_MERGED
    for worktree in (common.pull_request_head_worktree(arguments, arguments.pull_request),
                     common.pull_request_merged_worktree(arguments, arguments.pull_request)):
        if not worktree.exists():
            continue
        removal = subprocess.run(
            ["git", "-C", str(checkout), "worktree", "remove", "--force", str(worktree)],
            capture_output=True, text=True, stdin=subprocess.DEVNULL,
            env=common.run_all_test_suites.environment_without_git_redirecting_variables())
        if removal.returncode != 0:
            print(f"STOP: merged, but the review worktree {worktree} was not removed: git "
                  f"worktree remove exited {removal.returncode}: {git_error(removal)}\n"
                  f"If git names a cause you can fix, fix it and remove the worktree: "
                  f"git -C {checkout} worktree remove --force {worktree}\n"
                  f"Otherwise, tell the user this message as printed, from its STOP line, which "
                  f"quotes git's error, through this line.")
            exit_code = EXIT_MERGED_BUT_A_STEP_AFTER_THE_MERGE_NOT_DONE
            continue
        print(f"removed the review worktree {worktree}")
    return exit_code


def head_test_run_passed_merged_commit(arguments):
    """Return (the pr<n>-merged commit of the newest passing head test run record, None),
    or (None, why no record gave one)."""
    kind = (common.pull_request_head_test_run_log_store_root_directory(arguments, arguments.pull_request)
            / head_test_run.PULL_REQUEST_HEAD_TEST_RUNS_KIND_DIRECTORY_NAME)
    newest = None
    for test_log in sorted(kind.glob("*/*.txt")):
        commit = test_log.stem
        try:
            started, record = (
                head_test_run.pull_request_head_test_run_test_log_split_into_records(
                    test_log.read_text(encoding="utf-8"))[-1])
        except (OSError, UnicodeDecodeError,
                head_test_run.PullRequestHeadTestRunTestLogNotWholeRecordsError) as error:
            print(f"the head test run record {test_log} could not be read, so it is not "
                  f"used: {error}\n"
                  f"Nothing to do: without it the test run selects more suites, never fewer.")
            continue
        if not head_test_run.pull_request_head_test_run_record_passed_on_commit_check(
                record, commit):
            continue
        if newest is None or started > newest[0]:
            newest = (started, commit)
    if newest is None:
        return None, f"no readable head test run record under {kind} passed"
    return newest[1], None


def recordings_matching_the_merge_commit_adopted(worktree, source, which_source, into,
                                                  without_them):
    """Adopt into into the recordings under source that match worktree, at the merge commit;
    print what happened and return False when adoption failed. without_them says what runs
    do while into lacks them."""
    runner = common.run_all_test_suites
    try:
        adopted = runner.adopt_passing_recordings_that_match_the_checkout(worktree, into, [source])
    except (runner.CouldNotRun, OSError) as error:
        # A refusal's lines after its first tell the agent to rerun the runner, which is not
        # what failed here; the lines below say what to do instead.
        what_failed = str(error).partition("\n")[0]
        print(f"STOP: merged, but the recordings in {source}, {which_source}, were not adopted "
              f"into {into}: {what_failed}\n"
              f"{without_them} Nothing else waits on this adoption: the program goes on and "
              f"exits 3, and the next merge adopts its own recordings.\n"
              f"If the error names a cause you can fix, fix it; nothing needs to be run again. "
              f"Otherwise, tell the user this message as printed, from its STOP line, which "
              f"quotes the error, through this line.")
        return False
    print(f"adopted {len(adopted)} recordings into {into} from {source}, {which_source}; a "
          f"recording is adopted only when its run passed and it matches the merge commit")
    return True


def suites_on_runner_lines(lines, prefix):
    """Each suite on a line opening with prefix, with its log when a line names one."""
    suites = {}
    for line in lines:
        if line.startswith(prefix):
            words = line[len(prefix):].split()
            if words:
                log = line.partition(" — log ")[2].strip() or None
                suites[words[0]] = log or suites.get(words[0])
    return suites


def merged_branch_last_commit_author_name_read(worktree, merge_commit, environment):
    """The author name of the merged branch's last commit, or None when git cannot read it."""
    author = subprocess.run(
        ["git", "-C", str(worktree), "log", "-1", "--format=%an", f"{merge_commit}^2"],
        capture_output=True, text=True, env=environment, stdin=subprocess.DEVNULL)
    return author.stdout.strip() or None if author.returncode == 0 else None


def test_named(suite, test):
    """A failed test as a reader sees it; a suite with no case lines is its own one test."""
    return suite if test == suite else f"{suite}: {test}"


def repair_task_opened(arguments, merge_commit, seat, failed_tests):
    """Open one repair task on seat's list for {suite: {test: log}}; return (seat, id, why none)."""
    task_list = Path.home() / ".claude" / "tasks" / f"nedsnodes-{seat}-tasks"
    if not seat or not task_list.is_dir() or not (Path.home() / "agents" / seat).is_dir():
        return None, None, (f"the merged branch's author, {seat or 'unknown'}, has no task "
                            f"list or no checkout on this machine")
    named = " ".join(sorted(failed_tests))
    logs = "\n".join(f"- {test_named(suite, test)}: {log}"
                     for suite, tests in sorted(failed_tests.items())
                     for test, log in sorted(tests.items()))
    count = sum(len(tests) for tests in failed_tests.values())
    description = (
        f"The after-merge test run of main at {merge_commit} failed, after pull request "
        f"{arguments.pull_request} merged. Merges go on while main fails, so this needs a fix "
        f"on main.\n\nFailed tests and their logs:\n{logs}\n\n"
        f"Reproduce in a detached worktree at origin/main: python3 scripts/run-all-test-suites.py "
        f"--only-suites-named {named}\n"
        f"Open a pull request that fixes the cause. Complete this task once it merges; the next "
        f"after-merge test run then takes each passing test off the record that "
        f"scripts/merge-gate.sh shows.")
    try:
        task_id = task_write.agent_seat_task_list_new_pending_task_write(
            task_list, f"Main fails after pull request {arguments.pull_request}: fix "
                       f"{count} failed test(s)", description)
    except OSError as error:
        return None, None, f"the repair task could not be written to {task_list}: {error}"
    return seat, task_id, None


def repair_task_no_longer_open(seat, task_id):
    """True when the task is completed or gone; an unreadable task file counts as gone, because
    a second repair task costs less than a failing test nobody is assigned."""
    task_file = Path.home() / ".claude" / "tasks" / f"nedsnodes-{seat}-tasks" / f"{task_id}.json"
    try:
        return json.loads(task_file.read_text(encoding="utf-8")).get("status") == "completed"
    except (OSError, ValueError, AttributeError):
        return True


def run_verdicts_by_suite(lines, junit_file):
    """{suite: verdict} for each suite the run judged, and what went wrong reading junit_file, or
    None.

    A verdict holds "failed", {test: log}; "passed", the set of tests that passed; "skipped", the
    text of each SKIP line; and "ran_to_the_end", whether the suite ended on its own after every
    case it would run. The runner names each test in junit.xml, a suite that printed no case
    line being the one test named for the suite; a suite NOT RUN or stopped by the run has no
    verdict."""
    logs = suites_on_runner_lines(lines, common.run_all_test_suites.FAILED_SUITE_LINE_PREFIX)
    try:
        root = xml.etree.ElementTree.parse(junit_file).getroot()
    except FileNotFoundError:
        return {}, f"{junit_file} does not exist"
    except (OSError, xml.etree.ElementTree.ParseError) as caught:
        return {}, f"{junit_file} could not be read: {caught}"
    verdicts = {}
    for element in root.iter("testsuite"):
        if element.get("judged") == "false":
            continue
        suite = element.get("name")
        verdict = verdicts.setdefault(suite, {"failed": {}, "passed": set(), "skipped": [],
                                              "ran_to_the_end": True})
        verdict["ran_to_the_end"] = (verdict["ran_to_the_end"]
                                     and element.get("ran_to_the_end") == "true")
        for case in element.iter("testcase"):
            if case.find("skipped") is not None:
                verdict["skipped"].append(case.get("name"))
            elif case.find("failure") is not None:
                verdict["failed"][case.get("name")] = logs.get(suite)
            else:
                verdict["passed"].add(case.get("name"))
    for verdict in verdicts.values():
        verdict["passed"] -= set(verdict["failed"])
    return verdicts, None


def test_skipped(test, verdict):
    """Whether a SKIP line of the suite names test; its text is the name, then ": " and why."""
    return any(text == test or text.startswith(test + ": ") for text in verdict["skipped"])


TELL_AUTHOR_AND_USER_THE_STOP_MESSAGE = (
    "Tell the pull request's author, and the user, this message as printed, from its "
    "STOP line through this line, with the FAIL and NOT RUN suite lines printed above "
    "it, if any.")


def failed_suites_kept_in_view(arguments, merge_commit, worktree, log_dir, environment, lines):
    """Update the failed suites record from this run and a rerun of the suites it left out.

    Return {"complete": whether every step worked and every suite that gave a verdict ran to the
    end, "new_tests": the {suite: {test: log}} this merge newly failed, "seat" and "task_id" of
    their repair task, the task_id None when none was opened, and "why_none"}. Each step that
    did not work prints its own STOP line."""
    runner = common.run_all_test_suites
    kept = {"complete": True, "new_tests": {}, "seat": None, "task_id": None, "why_none": None}
    tell_the_user = (
        "The merge is done and later merges are not held up, but merge-gate.sh may not show "
        "tests failing on main until the record works.\n"
        "If the error names a cause you can fix, fix it; the next after-merge test run then "
        "records its own failures. This test run's failed suites, listed above, are not on the "
        "record, so send them to the pull request's author.\n"
        "Otherwise tell the user: \"The record of test suites failing on main could not be "
        "updated on ned-box, so the merge gate may not show them. Merges go on.\", followed by "
        "the error. If you are a subagent, tell the agent that dispatched you instead.")
    try:
        recorded = failed_suites_record.failed_after_merge_test_suites_on_main_record_read()
    except failed_suites_record.FailedAfterMergeTestSuitesOnMainRecordFileUnreadableOrUnwritable as error:
        print(f"STOP: merged, but the failed suites record was not updated: {error}\n"
              f"{tell_the_user}")
        kept["complete"] = False
        return kept
    if not recorded and not any(line.startswith(runner.FAILED_SUITE_LINE_PREFIX)
                                for line in lines):
        return kept

    verdicts, junit_error = run_verdicts_by_suite(lines, log_dir / runner.JUNIT_XML_FILE_NAME)
    if junit_error:
        print(f"STOP: merged, but this test run's failed tests could not be named: {junit_error}\n"
              f"{tell_the_user}")
        kept["complete"] = False
    still_to_run = sorted(set(recorded) - set(verdicts))
    gone = set()
    if still_to_run:
        listed = subprocess.run(["git", "-C", str(worktree), "ls-files", "--", *still_to_run],
                                capture_output=True, text=True, env=environment,
                                stdin=subprocess.DEVNULL)
        if listed.returncode != 0:
            print(f"STOP: merged, but the recorded failed suites were not run again: git "
                  f"ls-files failed: {git_error(listed)}\n{tell_the_user}")
            kept["complete"] = False
            still_to_run = []
        else:
            tracked = set(listed.stdout.splitlines())
            gone = set(still_to_run) - tracked
            still_to_run = [suite for suite in still_to_run if suite in tracked]
    if still_to_run:
        print(f"rerunning the {len(still_to_run)} recorded failed suite(s) that this selective "
              f"test run left out", flush=True)
        rerun_log_dir = log_dir.with_name(log_dir.name + "-recorded-failed-suites")
        rerun = subprocess.run(
            [sys.executable, str(worktree / "scripts" / "run-all-test-suites.py"),
             "--only-suites-named", *still_to_run,
             "--leave-recorded-inputs-and-failure-history-unchanged",
             "--log-dir", str(rerun_log_dir)],
            cwd=worktree, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
            env=environment, stdin=subprocess.DEVNULL)
        rerun_lines = rerun.stdout.splitlines()
        rerun_gave_every_verdict = (
            runner.run_all_test_suites_output_parse_whether_failed_suites_were_the_runs_only_problem(
                rerun.returncode, rerun.stdout)
            or (rerun.returncode == 0
                and any(line.startswith(runner.SUMMARY_LINE_PREFIX) for line in rerun_lines)))
        rerun_verdicts, rerun_junit_error = run_verdicts_by_suite(
            rerun_lines, rerun_log_dir / runner.JUNIT_XML_FILE_NAME)
        if not rerun_gave_every_verdict:
            print(f"STOP: merged, but the recorded failed suites could not all be run again: the "
                  f"runner exited {rerun.returncode}. Each suite it gave no verdict stays on the "
                  f"record. Its output was:\n{rerun.stdout.rstrip()}\n{tell_the_user}")
            kept["complete"] = False
        elif rerun_junit_error:
            print(f"STOP: merged, but the rerun's failed tests could not be named: "
                  f"{rerun_junit_error}. They stay on the record.\n{tell_the_user}")
            kept["complete"] = False
        verdicts.update({suite: verdict for suite, verdict in rerun_verdicts.items()
                         if suite in still_to_run})
    for suite, verdict in sorted(verdicts.items()):
        if not verdict["ran_to_the_end"]:
            print(f"STOP: merged, but {suite} did not run to the end: it was killed, passed its "
                  f"time limit, or stopped after a case line with no verdict, so its later cases "
                  f"have none.\n{TELL_AUTHOR_AND_USER_THE_STOP_MESSAGE}")
            kept["complete"] = False

    opened_again = []
    could_not_open_again = []
    removed = []
    undecided = {}
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    def observed_at(suite, test, fields, strictly_later):
        # A run of an older commit says nothing about a failure a newer run observed.
        last = fields["last_failed_commit"]
        if strictly_later and last == merge_commit:
            return False
        ancestor = subprocess.run(
            ["git", "-C", str(worktree), "merge-base", "--is-ancestor", last, merge_commit],
            capture_output=True, text=True, env=environment, stdin=subprocess.DEVNULL)
        if ancestor.returncode not in (0, 1):
            undecided[test_named(suite, test)] = git_error(ancestor)
        return ancestor.returncode == 0

    def why_it_leaves(suite, test, fields):
        if suite in gone:
            return "git no longer lists its suite" if observed_at(suite, test, fields, False) else None
        verdict = verdicts.get(suite)
        if verdict is None:
            return None
        if test in verdict["passed"]:
            return "it passed" if observed_at(suite, test, fields, False) else None
        if test in verdict["failed"]:
            if observed_at(suite, test, fields, True):
                fields["last_failed_commit"] = merge_commit
            return None
        if test_skipped(test, verdict) or not verdict["ran_to_the_end"]:
            return None
        if not observed_at(suite, test, fields, True):
            return None
        # One SKIP line can stand for a group of cases, so a test it covered looks unreported.
        skips = "; ".join(verdict["skipped"])
        return ("its suite ran to the end and reported nothing for it" + (
            f", but the suite printed SKIP lines naming other cases ({skips}); if one of them "
            f"covers this test, the test was not run" if skips else ""))

    to_open = {"new_tests": {}, "again": {}}
    # What the first save left on each test whose repair task opens after it; the second save
    # names the task only on an entry still holding that, since another run may have changed it.
    left_by_first_save = {}
    closed_task_of_test = {}

    def change(suites):
        for suite in list(suites):
            tests = suites[suite]["failed_tests"]
            for test, fields in list(tests.items()):
                why = why_it_leaves(suite, test, fields)
                if why:
                    del tests[test]
                    removed.append((suite, test, why))
            if not tests:
                del suites[suite]

        new_tests, to_open_again = {}, {}
        for suite, verdict in verdicts.items():
            on_record = suites.get(suite, {}).get("failed_tests", {})
            for test, log in verdict["failed"].items():
                fields = on_record.get(test)
                if fields is None:
                    new_tests.setdefault(suite, {})[test] = log
                elif (fields["repair_task_id"] is not None and repair_task_no_longer_open(
                        fields["repair_task_agent_seat"], fields["repair_task_id"])):
                    to_open_again.setdefault(fields["repair_task_agent_seat"], {}).setdefault(
                        suite, {})[test] = log
                    closed_task_of_test[(suite, test)] = (fields["repair_task_agent_seat"],
                                                          fields["repair_task_id"])
                    # As for a new test: if the second save fails, the closed task's id must
                    # not stay, or the next merge opens a second task beside this one.
                    fields["repair_task_agent_seat"] = fields["repair_task_id"] = None
                    left_by_first_save[(suite, test)] = (fields["commit"], fields["failed_at"])

        # Repair tasks open only once the record is saved, so a failed write cannot leave a
        # task whose tests the next merge, finding them unrecorded, gives a second task.
        for suite, tests in new_tests.items():
            on_record = suites.setdefault(suite, {"failed_tests": {}})["failed_tests"]
            for test, log in tests.items():
                on_record[test] = {"commit": merge_commit, "last_failed_commit": merge_commit,
                                   "pull_request": arguments.pull_request, "log": log,
                                   "failed_at": now, "repair_task_agent_seat": None,
                                   "repair_task_id": None}
                left_by_first_save[(suite, test)] = (merge_commit, now)
        to_open.update(new_tests=new_tests, again=to_open_again)

    try:
        left = failed_suites_record.failed_after_merge_test_suites_on_main_record_change_apply_under_lock(change)
    except failed_suites_record.FailedAfterMergeTestSuitesOnMainRecordFileUnreadableOrUnwritable as error:
        print(f"STOP: merged, but the failed suites record was not updated: {error}\n"
              f"{tell_the_user}")
        kept.update(complete=False, new_tests=to_open["new_tests"],
                    why_none="the failed suites record could not be written")
        return kept

    task_of_test = {}
    for seat, tests_of_seat in sorted(to_open["again"].items()):
        _, task_id, why_none = repair_task_opened(arguments, merge_commit, seat, tests_of_seat)
        if task_id is None:
            could_not_open_again.append((seat, tests_of_seat, why_none))
            task_of_test.update({(suite, test): closed_task_of_test[(suite, test)]
                                 for suite, tests in tests_of_seat.items() for test in tests})
            continue
        opened_again.append((seat, task_id, tests_of_seat))
        task_of_test.update({(suite, test): (seat, task_id)
                             for suite, tests in tests_of_seat.items() for test in tests})
    if to_open["new_tests"]:
        author = merged_branch_last_commit_author_name_read(worktree, merge_commit, environment)
        seat, task_id, why_none = repair_task_opened(arguments, merge_commit, author,
                                                     to_open["new_tests"])
        kept.update(new_tests=to_open["new_tests"], seat=seat, task_id=task_id,
                    why_none=why_none)
        if task_id is not None:
            task_of_test.update({(suite, test): (seat, task_id)
                                 for suite, tests in to_open["new_tests"].items()
                                 for test in tests})

    changed_since_first_save = {}

    def tasks_named(suites):
        changed_since_first_save.clear()
        for (suite, test), (seat, task_id) in task_of_test.items():
            fields = suites.get(suite, {}).get("failed_tests", {}).get(test)
            if (fields is None or fields["repair_task_id"] is not None
                    or (fields["commit"], fields["failed_at"]) != left_by_first_save[(suite, test)]):
                changed_since_first_save[(suite, test)] = (seat, task_id)
                continue
            fields["repair_task_agent_seat"], fields["repair_task_id"] = seat, task_id

    if task_of_test:
        try:
            left = failed_suites_record.failed_after_merge_test_suites_on_main_record_change_apply_under_lock(
                tasks_named)
        except failed_suites_record.FailedAfterMergeTestSuitesOnMainRecordFileUnreadableOrUnwritable as error:
            print(f"STOP: merged, but the failed suites record does not name the repair tasks "
                  f"just opened, so merge-gate.sh shows those tests with no repair task: "
                  f"{error}\n{tell_the_user}")
            kept["complete"] = False
            changed_since_first_save.clear()
    for (suite, test), (seat, task_id) in sorted(changed_since_first_save.items()):
        if closed_task_of_test.get((suite, test)) == (seat, task_id):
            continue
        print(f"STOP: merged, but another merge's test run changed {test_named(suite, test)} on "
              f"the failed suites record after this run saved it, so the record does not name "
              f"repair task #{task_id} on {seat}'s task list, opened for it by this run. The run "
              f"that changed it either took the test off the record or recorded it anew and "
              f"opened its own repair task, so task #{task_id} is not needed.\n"
              f"Complete task #{task_id} on {seat}'s task list, with a note that the run of the "
              f"merge after pull request {arguments.pull_request} handles the test. If you are a "
              f"subagent, tell the agent that dispatched you instead.")
        kept["complete"] = False
    for name, error in sorted(undecided.items()):
        print(f"STOP: merged, but {name} stays on the failed suites record: git could not say "
              f"whether the commit it last failed at is an ancestor of {merge_commit}: {error}\n"
              f"{tell_the_user}")
        kept["complete"] = False
    for suite, test, why in sorted(removed):
        print(f"{test_named(suite, test)} left the failed suites record: {why}")
    for seat, task_id, tests_of_seat in opened_again:
        names = ", ".join(test_named(suite, test) for suite, tests in sorted(tests_of_seat.items())
                          for test in sorted(tests))
        print(f"opened repair task #{task_id} on {seat}'s task list, because its earlier repair "
              f"task is closed and these still fail: {names}")
    for seat, tests_of_seat, why_none in could_not_open_again:
        names = ", ".join(test_named(suite, test) for suite, tests in sorted(tests_of_seat.items())
                          for test in sorted(tests))
        print(f"STOP: merged, but {names} still fail(s), the repair task on {seat}'s task list is "
              f"closed, and no new one could be opened: {why_none}.\n"
              f"Ask the user: \"Main still fails {names}, and no new repair task could go to "
              f"{seat}. I recommend that merge-lane-2 fixes it. Should it?\" If the user says "
              f"yes, merge-lane-2 opens a pull request that fixes it; otherwise do what the user "
              f"says. Merges go on meanwhile. If you are a subagent, ask the agent that "
              f"dispatched you instead.")
        kept["complete"] = False
    notice = failed_suites_record.merge_gate_notice(left)
    if notice:
        print(notice)
    return kept


def after_merge_test_run_closing_message_printed_returning_whether_stop(arguments, merge_commit, run_exit_code, summaries,
                                 failed_suites_were_the_only_problem, kept, every_step_complete,
                                 by_hand):
    """Print the after-merge test run's closing message; return whether it is a STOP."""
    runner = common.run_all_test_suites
    new_tests = kept["new_tests"]
    if new_tests:
        if run_exit_code == 0:
            print(f"STOP: merged, and the test run of main at {merge_commit} passed, but the "
                  f"rerun of the recorded failed suites failed tests not on the record; they are "
                  f"listed above.")
        else:
            print(f"STOP: merged, but the test run of main at {merge_commit} exited "
                  f"{run_exit_code} and failed tests not on the failed suites record; the failed "
                  f"suites are listed above, each with its log.")
        if kept["task_id"] is not None and every_step_complete:
            print(f"Repair task #{kept['task_id']} is on {kept['seat']}'s task list, so nothing "
                  f"needs sending. Go on with the next merge.")
        elif kept["task_id"] is not None:
            print(f"Repair task #{kept['task_id']} on {kept['seat']}'s task list covers only the "
                  f"newly failed tests; the rest of this test run has no verdict, or a step after "
                  f"the merge did not work, as the lines above say.\n"
                  f"{TELL_AUTHOR_AND_USER_THE_STOP_MESSAGE}")
        else:
            tests_named = ", ".join(test_named(suite, test)
                                    for suite, tests in sorted(new_tests.items())
                                    for test in sorted(tests))
            if not every_step_complete:
                print(TELL_AUTHOR_AND_USER_THE_STOP_MESSAGE)
            print(f"No repair task was opened: {kept['why_none']}. Nobody is assigned to fix main.\n"
                  f"Ask the user: \"Main fails {tests_named} after pull request "
                  f"{arguments.pull_request}, and no repair task could go to its author. I "
                  f"recommend that merge-lane-2 fixes it. Should it?\" If the user says yes, "
                  f"merge-lane-2 opens a pull request that fixes it; otherwise do what the user "
                  f"says. Merges go on meanwhile. If you are a subagent, ask the agent that "
                  f"dispatched you instead.")
        return True
    if failed_suites_were_the_only_problem and every_step_complete:
        print(f"the test run of main at {merge_commit} failed only suites already on the failed "
              f"suites record. The merge that first failed each one opened its repair task or "
              f"said to ask the user, so nothing is needed for them here. Go on with the next "
              f"merge, if there is one.")
        return False
    if run_exit_code != 0:
        print(f"STOP: merged, but the test run of main at {merge_commit} exited "
              f"{run_exit_code}, so main may be broken; the failed suites, if any, are "
              f"listed above, each with its log.\n{TELL_AUTHOR_AND_USER_THE_STOP_MESSAGE}")
        return True
    if not summaries:
        print(f"STOP: merged, but the test run of main at {merge_commit} exited 0 and printed "
              f"no {runner.SUMMARY_LINE_PREFIX} line, so it gave no verdict on main.\n"
              f"In a detached worktree at {merge_commit}, run: {by_hand}\n"
              f"If that run also prints no {runner.SUMMARY_LINE_PREFIX} line, tell the user "
              f"this message.")
        return True
    return not every_step_complete


def after_merge_test_run(arguments, merge_commit):
    """Run the selective test run in a fresh worktree at merge_commit; return an exit code."""
    checkout = arguments.review_tools_worktree_at_main
    since, why_not = head_test_run_passed_merged_commit(arguments)
    if since is None:
        since = arguments.head_commit
        print(f"selecting the nn-test-suites whose recorded inputs changed since the head "
              f"commit {since[:12]}, which selects more suites than "
              f"the merge changed: {why_not}.\n"
              f"Nothing to do: this run still tests every suite the merge could have changed.")
    else:
        print(f"selecting the nn-test-suites whose recorded inputs changed since "
              f"{since[:12]}, the commit the head test run passed on: "
              f"pull request {arguments.pull_request}'s head merged with main as main was "
              f"when that run started")
    by_hand = (f"python3 scripts/run-all-test-suites.py "
               f"--only-suites-whose-recorded-inputs-changed-since {since}")
    if not merge_commit:
        print(f"STOP: merged, but the merge commit could not be read, so main was not "
              f"tested.\n"
              f"Read it: gh pr view {arguments.pull_request} --repo {REPOSITORY} "
              f"--json mergeCommit\n"
              f"Then, in a detached worktree at that commit, run: {by_hand}")
        return EXIT_MERGED_BUT_A_STEP_AFTER_THE_MERGE_NOT_DONE
    environment = common.run_all_test_suites.environment_without_git_redirecting_variables()

    def git(*git_arguments):
        return subprocess.run(["git", "-C", str(checkout), *git_arguments],
                              capture_output=True, text=True, env=environment,
                              stdin=subprocess.DEVNULL)

    worktree = arguments.merge_lane_review_worktrees_directory / f"pr{arguments.pull_request}-merge-commit-on-main-worktree"
    log_dir = (arguments.merge_lane_worktrees_and_outputs_directory
               / f"pr{arguments.pull_request}-after-merge-test-run-logs-{merge_commit[:12]}")
    next_steps = (f"If git names a cause you can fix, fix it; then, in a detached worktree at "
                  f"{merge_commit}, run: {by_hand}\n"
                  f"Otherwise, tell the user this message as printed, from its STOP line, which "
                  f"quotes git's error, through this line.")
    # Not a fetch of every branch: that updates origin/main, which every agent-seat's
    # checkout of the same clone also fetches into, and git refuses the second of two
    # fetches that update it at once with "incorrect old value provided".
    fetch = git("fetch", "--quiet", "--no-write-fetch-head", "origin", merge_commit)
    if fetch.returncode != 0:
        print(f"STOP: merged, but main was not tested: could not fetch origin in {checkout} "
              f"to get the merge commit {merge_commit}: "
              f"{git_error(fetch)}\n{next_steps}")
        return EXIT_MERGED_BUT_A_STEP_AFTER_THE_MERGE_NOT_DONE
    add = git("worktree", "add", "--detach", str(worktree), merge_commit)
    if add.returncode != 0:
        print(f"STOP: merged, but main was not tested: git worktree add, run in {checkout}, "
              f"could not make the worktree {worktree} at the merge commit {merge_commit}: "
              f"{git_error(add)}\n{next_steps}")
        return EXIT_MERGED_BUT_A_STEP_AFTER_THE_MERGE_NOT_DONE

    runner = common.run_all_test_suites
    store = common.merge_lane_head_test_run_recorded_inputs_store_directory(arguments)
    stale_in_the_store = (f"Until a later merge adopts recordings that match main, merge-lane "
                          f"head test runs select each suite whose recording in {store} is "
                          f"stale, unless its recording in "
                          f"{runner.DEFAULT_RECORDED_INPUTS_DIRECTORY} matches main, and so may run "
                          f"more suites than they need.")
    # Before the test run, so head test runs on the new main find the merged pull request's
    # recordings for the minutes the run takes.
    saved_apart = common.pull_request_head_test_run_saved_recorded_inputs_directory(
        arguments, arguments.pull_request)
    done_before_the_run = recordings_matching_the_merge_commit_adopted(
        worktree, saved_apart, "where this pull request's head test runs saved their recordings",
        store, stale_in_the_store)
    # Removed whether or not adoption succeeded: no later merge reads it.
    try:
        shutil.rmtree(saved_apart)
    except FileNotFoundError:
        pass
    except OSError as error:
        print(f"STOP: merged, but {saved_apart}, which no run reads any more, was not "
              f"removed: {error}\n"
              f"If the error names a cause you can fix, fix it and remove {saved_apart}. "
              f"Otherwise, tell the user this message as printed, from its STOP line, which "
              f"quotes the error, through this line.")
        done_before_the_run = False
    # The run selects by the runner's default directory, which no head test run writes.
    done_before_the_run = recordings_matching_the_merge_commit_adopted(
        worktree, store, "the store merge-lane head test runs select by",
        runner.DEFAULT_RECORDED_INPUTS_DIRECTORY,
        f"So this after-merge test run selects the suites whose recordings in "
        f"{runner.DEFAULT_RECORDED_INPUTS_DIRECTORY} do not match the merge commit, and so may "
        f"run suites again that a head test run passed on the same files.") and done_before_the_run
    print(f"testing main at the merge commit {merge_commit[:12]}: the suites whose recorded "
          f"inputs changed since {since[:12]}", flush=True)
    run_all = subprocess.run(
        [sys.executable, str(worktree / "scripts" / "run-all-test-suites.py"),
         "--only-suites-whose-recorded-inputs-changed-since", since,
         "--log-dir", str(log_dir)],
        cwd=worktree, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
        env=environment, stdin=subprocess.DEVNULL)
    lines = run_all.stdout.splitlines()
    summaries = [line for line in lines if line.startswith(runner.SUMMARY_LINE_PREFIX)]
    for line in lines:
        if line.startswith((runner.FAILED_SUITE_LINE_PREFIX, runner.NOT_RUN_SUITE_LINE_PREFIX)):
            print(line)
    print(summaries[-1] if summaries
          else f"the test run printed no {runner.SUMMARY_LINE_PREFIX} line; its output was:\n"
               f"{run_all.stdout.rstrip()}")
    print(f"the test run's logs and test-run-report.txt: {log_dir}")
    failed_suites_were_the_only_problem = (
        runner.run_all_test_suites_output_parse_whether_failed_suites_were_the_runs_only_problem(
            run_all.returncode, run_all.stdout))
    kept = failed_suites_kept_in_view(arguments, merge_commit, worktree, log_dir, environment,
                                      lines)
    every_step_complete = done_before_the_run and kept["complete"] and (
        failed_suites_were_the_only_problem or (run_all.returncode == 0 and bool(summaries)))

    if not recordings_matching_the_merge_commit_adopted(
            worktree, runner.DEFAULT_RECORDED_INPUTS_DIRECTORY,
            "where the after-merge test run saved its recordings", store, stale_in_the_store):
        every_step_complete = False

    removal = git("worktree", "remove", "--force", str(worktree))
    if removal.returncode != 0:
        print(f"STOP: merged, but the worktree {worktree} was not removed: git worktree "
              f"remove exited {removal.returncode}: {git_error(removal)}\n"
              f"If git names a cause you can fix, fix it and remove the worktree: "
              f"git -C {checkout} worktree remove --force {worktree}\n"
              f"Otherwise, tell the user this message as printed, from its STOP line, which "
              f"quotes git's error, through this line.")
        every_step_complete = False
    else:
        print(f"removed the worktree {worktree}")

    # Chosen once every step has run, so that "nothing needs sending" never follows a step
    # that did not work.
    stop = after_merge_test_run_closing_message_printed_returning_whether_stop(
        arguments, merge_commit, run_all.returncode, summaries,
        failed_suites_were_the_only_problem, kept, every_step_complete, by_hand)
    return EXIT_MERGED_BUT_A_STEP_AFTER_THE_MERGE_NOT_DONE if stop else EXIT_MERGED


def surviving_mutant_test_prs_go_ahead_printed(environment):
    """Run the go-ahead program and print its output; its outcome never changes the exit code."""
    program = SURVIVING_MUTANT_TEST_PRS_GO_AHEAD_PROGRAM
    go_ahead = subprocess.run([sys.executable, str(program)], stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT, text=True, env=environment,
                              stdin=subprocess.DEVNULL)
    print(go_ahead.stdout, end="" if go_ahead.stdout.endswith("\n") or not go_ahead.stdout
          else "\n")
    if go_ahead.returncode not in SURVIVING_MUTANT_TEST_PRS_GO_AHEAD_ANSWERS:
        print(f"{program.name} exited {go_ahead.returncode}, so whether an agent-seat holding "
              f"mutant-test tasks may open its pull requests was not decided; the merge is done "
              f"all the same.\n"
              f"Follow the instructions it printed above; when it printed none, run it once: "
              f"python3 scripts/{program.name}", flush=True)


def main(argv=None, wait=time.sleep):
    arguments = parse_arguments(argv)
    try:
        token = common.read_merge_account_token()
    except common.MergeAccountTokenUnusable as unusable:
        print(f"STOP: not merged: {unusable}.\n"
              f"Tell the user this message as printed, from its STOP line, which says why the "
              f"token is unusable, through this line: only the user can restore the token.")
        return EXIT_COULD_NOT_RUN
    environment = {**os.environ, "GH_TOKEN": token}

    # Moved first, so the missing-tool check reads main's files; a worktree that does not
    # exist is left to that check, which says how to make it.
    refusal = ((review_tools_worktree_moved_to_main_refusal_message(
                    arguments.review_tools_worktree_at_main)
                if arguments.review_tools_worktree_at_main.is_dir() else None)
               or common.review_tool_missing_message(arguments, MERGE_GATE))
    if refusal:
        print(f"STOP: not merged: {refusal}")
        return EXIT_COULD_NOT_RUN

    gate = merge_gate_after_retries(arguments, environment, wait)
    print(gate.stdout, end="" if gate.stdout.endswith("\n") or not gate.stdout else "\n")
    if gate.returncode not in MERGE_GATE_DOCUMENTED_EXITS:
        print(f"STOP: not merged: merge-gate.sh exited {gate.returncode}, a code it never "
              f"exits with on its own, so bash could not run it as written.\n"
              f"Tell the user this message, with the output above.")
        return EXIT_COULD_NOT_RUN
    if gate.returncode != 0:
        print(f"STOP: not merged: merge-gate.sh exited {gate.returncode}.\n"
              f"Follow the gate's own instructions, printed above.")
        return gate.returncode

    expected = (f"gh pr merge {arguments.pull_request} --repo {REPOSITORY} --merge "
                f"--delete-branch --match-head-commit {arguments.head_commit}")
    printed = printed_merge_command(gate.stdout)
    if printed != expected:
        print(f"STOP: not merged: merge-gate.sh and this program disagree on the merge "
              f"command, so one of them is out of date.\n"
              f"The gate printed: {printed!r}\n"
              f"This program runs only: {expected!r}\n"
              f"Do not merge, by either command.\n"
              f"Tell the user this message: only the user decides which command is right.")
        return EXIT_REFUSED

    retarget_exit, branch = stacked_pull_requests_retarget(arguments.pull_request, environment)
    if retarget_exit != EXIT_MERGED:
        return retarget_exit

    merge = merge_after_retries(expected.split(), environment, wait)
    print(merge.stdout, end="")
    print(f"merge exit {merge.returncode}", flush=True)
    merge_error = f"the merge command exited {merge.returncode}" + (
        f": {merge.stderr.strip()}" if merge.stderr.strip() else "")
    state = run(["gh", "pr", "view", arguments.pull_request, "--repo", REPOSITORY,
                 "--json", "state,mergedAt,mergeCommit",
                 "-q", "{state,mergedAt,mc:.mergeCommit.oid}"], environment)
    try:
        read = json.loads(state.stdout) if state.returncode == 0 else None
    except ValueError:
        read = None
    if not isinstance(read, dict):
        print(f"could not read pull request {arguments.pull_request}'s state after the "
              f"merge: {gh_error(state) if state.returncode != 0 else repr(state.stdout)}")
        if merge.returncode != 0:
            print(f"STOP: whether pull request {arguments.pull_request} merged is unknown: "
                  f"{merge_error}\n"
                  f"Read its state: gh pr view {arguments.pull_request} --repo {REPOSITORY} "
                  f"--json state,mergeCommit\n"
                  f"If it is MERGED, do by hand what this program does after a merge: delete "
                  f"the branch {branch} if GitHub still has it, remove the review worktrees and "
                  f"test main at the merge commit. Otherwise, run this again.")
            return EXIT_MERGE_OUTCOME_UNKNOWN
        read = {"state": "MERGED"}
    else:
        print(state.stdout.strip())
    if read.get("state") != "MERGED":
        print(f"STOP: not merged: pull request {arguments.pull_request} is "
              f"{read.get('state')} after the merge command ran; {merge_error}")
        if BASE_BRANCH_MODIFIED_MERGE_REFUSAL in merge.stderr:
            print(f"GitHub refused the merge {MERGE_TRIES} times because main moved during it, "
                  f"as when other merges run at the same time; GitHub's \"Review and try the "
                  f"merge again\" asks for no new review.\n"
                  f"Run this program again once; if it is refused this way again, "
                  f"tell the user that merges keep failing because main moves during each one. "
                  f"If you are a subagent, report it to the agent that dispatched you instead.")
        return EXIT_REFUSED
    branch_exit = EXIT_MERGED
    if merge.returncode != 0:
        print(f"pull request {arguments.pull_request} merged although {merge_error}")
        branch_exit = merged_branch_deleted(branch, environment)
    removal_exit = review_worktrees_remove(arguments)
    test_exit = after_merge_test_run(arguments, read.get("mc") or "")
    surviving_mutant_test_prs_go_ahead_printed(environment)
    return next((code for code in (test_exit, removal_exit, branch_exit) if code != EXIT_MERGED),
                EXIT_MERGED)


if __name__ == "__main__":
    sys.exit(main())
