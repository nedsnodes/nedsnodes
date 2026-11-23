#!/usr/bin/env python3
"""Run main's pull-request-head-test-run.py on each pull request's pr<n>-merged worktree.

Usage:
  scripts/merge-lane-pull-request-head-test-run-on-merged-worktree.py <pull request number>...
      [--head-commit COMMIT] [--merge-lane-worktrees-and-outputs-directory DIR] [--merge-lane-review-worktrees-directory DIR] [--review-tools-worktree-at-main DIR]

For each pull request in turn, first rebuilds pr<n>-merged, with
--review-tools-worktree-at-main's
scripts/merge-lane-pull-request-head-and-merged-worktrees-rebuild.py, from the
commit that worktree has checked out and the pull request's head on origin, or
--head-commit, which a caller reviewing one fixed head passes and which takes
one pull request. pr<n>-head is left as it is, because reviewers may be reading
it. When the rebuild fails, that pull request's tests do not run.

Then runs --review-tools-worktree-at-main's
scripts/pull-request-head-test-run.py, not the pull request's, so a pull
request cannot pass by changing its runner. It tests pr<n>-merged under the
review worktrees directory and, under the worktrees and outputs directory,
files the record under hr/pr<n>/log-store, uses hr/pr<n>/tmp as its temporary directory,
selects by the recordings in hr/store and saves its own in hr/pr<n>/recorded-inputs, so a
pull request that does not merge, or merges onto a newer main, never replaces a recording
of main's; the merge program adopts into hr/store those that match the merge commit. It
also selects, read-only, by the runner's default recordings directory, where a running
after-merge test run saves each suite's recording as the suite passes: the merge program
adopts those into hr/store only when that test run ends. It writes its output to hr/pr<n>/stdout and
hr/pr<n>/stderr; each line of the run's stderr, where it copies the
runner's progress, is also printed on this program's stderr as it arrives,
so a run stopped before it ends has shown how far it got. tripwire-bin/ goes first on PATH: its claude and codex log
the call and exit 1, so no suite starts a real agent.

pull-request-head-test-run.py waits for the machine's test lock itself, so
nothing here retries.

Prints one line per pull request with the run's exit code and SUMMARY line.
Exit codes: 0 every run exited 0 and every copy of its stderr was written;
otherwise the code set by the first pull request that failed: 2 when its
pr<n>-merged could not be rebuilt, or a copy of its run's stderr could not be
written, even when the run exited nonzero, else its run's exit code; 2 also,
before any run, when tripwire-bin/ or either program named above is missing
from --review-tools-worktree-at-main, or git cannot read that worktree's commit.
"""

import argparse
import importlib.util
import os
import shlex
import subprocess
import sys
from pathlib import Path

HEAD_TEST_RUNNER = Path("scripts") / "pull-request-head-test-run.py"
MERGED_WORKTREE_REBUILD = Path("scripts") / "merge-lane-pull-request-head-and-merged-worktrees-rebuild.py"

_common_spec = importlib.util.spec_from_file_location(
    "merge_lane_pull_request_helpers_common", Path(__file__).resolve().with_name(
        "merge-lane-pull-request-helpers-common-options-paths-and-token.py"))
common = importlib.util.module_from_spec(_common_spec)
_common_spec.loader.exec_module(common)
run_all_test_suites = common.run_all_test_suites


def parse_arguments(argv):
    parser = argparse.ArgumentParser(
        description="Run main's pull-request-head-test-run.py on pr<n>-merged for each "
                    "pull request, with its outputs under the worktrees and outputs directory.")
    parser.add_argument("pull_requests", type=int, nargs="+", metavar="pull_request",
                        help="a pull request's number")
    parser.add_argument("--head-commit",
                        help="the head to merge, instead of the pull request's head on origin; "
                             "takes one pull request")
    common.add_directory_options(parser, "hr/ and tripwire-bin/")
    arguments = parser.parse_args(argv)
    if arguments.head_commit and len(arguments.pull_requests) != 1:
        parser.error("--head-commit takes exactly one pull request; run this program once for "
                     "each pull request, or leave --head-commit out")
    return common.resolve_path_options(arguments)


def merged_worktree_rebuild_failure(arguments, number, main_commit, environment):
    """Rebuild pr<n>-merged; return None, or what failed."""
    tools = arguments.review_tools_worktree_at_main
    head = arguments.head_commit
    if head is None:
        read = subprocess.run(
            ["git", "-C", str(tools), "ls-remote", "--exit-code", "origin",
             f"refs/pull/{number}/head"],
            capture_output=True, text=True, env=environment, stdin=subprocess.DEVNULL)
        if read.returncode != 0:
            return (f"git ls-remote could not read refs/pull/{number}/head from origin "
                    f"(exit {read.returncode}): {read.stderr.strip()}\n"
                    f"Check the pull request number, then run this again.")
        head = read.stdout.split()[0]
    rebuild = subprocess.run(
        [sys.executable, str(tools / MERGED_WORKTREE_REBUILD), str(number), head, main_commit,
         "--merged-worktree-only", *common.directory_options_argv(arguments)],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors="replace",
        env=environment, stdin=subprocess.DEVNULL)
    if rebuild.returncode != 0:
        return f"{MERGED_WORKTREE_REBUILD.name} exited {rebuild.returncode}:\n{rebuild.stdout.strip()}"
    return None


def main(argv=None):
    arguments = parse_arguments(argv)
    helpers = arguments.merge_lane_worktrees_and_outputs_directory
    review_tools_worktree = arguments.review_tools_worktree_at_main
    tripwire = helpers / "tripwire-bin"
    if not tripwire.is_dir():
        print(f"not run: {tripwire} is missing, and without it a suite could start a real "
              f"claude or codex.\n"
              f"Restore {tripwire} with a claude and a codex that exit 1, or pass the "
              f"--merge-lane-worktrees-and-outputs-directory that holds it.")
        return 2
    for tool in (HEAD_TEST_RUNNER, MERGED_WORKTREE_REBUILD):
        missing = common.review_tool_missing_message(arguments, tool)
        if missing:
            print(f"not run: {missing}")
            return 2
    environment = run_all_test_suites.environment_without_git_redirecting_variables()
    environment["PATH"] = f"{tripwire}{os.pathsep}{environment.get('PATH', '')}"
    main_read = subprocess.run(
        ["git", "-C", str(review_tools_worktree), "rev-parse", "--verify", "HEAD^{commit}"],
        capture_output=True, text=True, env=environment, stdin=subprocess.DEVNULL)
    if main_read.returncode != 0:
        print(f"not run: git cannot read the commit checked out in {review_tools_worktree}: "
              f"{main_read.stderr.strip()}\n"
              f"Pass a --review-tools-worktree-at-main that is a checkout at main.")
        return 2
    main_commit = main_read.stdout.strip()

    first_failure = 0
    for number in arguments.pull_requests:
        failure = merged_worktree_rebuild_failure(arguments, number, main_commit, environment)
        if failure is not None:
            print(f"PR {number} head test run: not run, because pr{number}-merged could not be "
                  f"rebuilt on main {main_commit[:12]}, so no suite ran for this pull request.\n"
                  f"{failure}", flush=True)
            if first_failure == 0:
                first_failure = 2
            continue
        log_store = common.pull_request_head_test_run_log_store_root_directory(arguments, number)
        outputs = log_store.parent
        log_store.mkdir(parents=True, exist_ok=True)
        (outputs / "tmp").mkdir(parents=True, exist_ok=True)
        with open(outputs / "stdout", "w") as stdout, open(outputs / "stderr", "w") as stderr:
            run = subprocess.Popen(
                [sys.executable, str(review_tools_worktree / HEAD_TEST_RUNNER),
                 "--checkout", str(common.pull_request_merged_worktree(arguments, number)),
                 "--log-store-root", str(log_store),
                 "--temporary-directory", str(outputs / "tmp"),
                 "--recorded-inputs-directory",
                 str(common.merge_lane_head_test_run_recorded_inputs_store_directory(arguments)),
                 "--save-recorded-inputs-to-directory",
                 str(common.pull_request_head_test_run_saved_recorded_inputs_directory(
                     arguments, number)),
                 "--also-leave-out-suites-whose-recorded-inputs-in-read-only-directory-match-checkout",
                 str(run_all_test_suites.DEFAULT_RECORDED_INPUTS_DIRECTORY)],
                cwd=helpers, env=environment, stdin=subprocess.DEVNULL,
                stdout=stdout, stderr=subprocess.PIPE, text=True, errors="replace")
            copy_failures = {}
            # A failed write stops copying to that target only; the pipe is still read
            # to its end, so the run is never left blocked on it.
            for line in run.stderr:
                for target, name in ((stderr, f"{outputs}/stderr"), (sys.stderr, "stderr")):
                    if name in copy_failures:
                        continue
                    try:
                        target.write(line)
                        target.flush()
                    except (OSError, ValueError) as error:
                        copy_failures[name] = f"{type(error).__name__}: {error}"
                        if target is stderr:
                            # The line that failed stays in the file's buffer, and the close
                            # at the end of the with block would raise the same error on it.
                            try:
                                stderr.close()
                            except OSError as close_error:
                                copy_failures[name] += (f"; closing it then failed too "
                                                        f"({type(close_error).__name__}: "
                                                        f"{close_error})")
                        if target is sys.stderr:
                            # Python flushes sys.stderr again at exit, and a failure there
                            # would replace this program's exit code with 120.
                            sys.stderr = open(os.devnull, "w")
            completed = subprocess.CompletedProcess(run.args, run.wait())
        rerun = shlex.join([
            sys.executable, str(Path(__file__).resolve()), str(number),
            *common.directory_options_argv(arguments)])
        for name, failure in copy_failures.items():
            # Only the copy to this program's own stderr failed, so the file has every line.
            if f"{outputs}/stderr" not in copy_failures:
                where_to_find_it = (f"When you need the lost stderr, read {outputs}/stderr, "
                                    f"which holds all of it.")
            else:
                where_to_find_it = (
                    f"When you need the lost stderr, run the head test run for PR {number} "
                    f"again with this command, from any directory: {rerun}\n"
                    f"Before you run it, give it a stderr that takes every write: do not "
                    f"close its stderr, pipe it to a program that exits before the run ends, "
                    f"or redirect it to a read-only file or a file on a full disk; and when "
                    f"{outputs}/stderr is the copy that failed, fix what "
                    f"{copy_failures[f'{outputs}/stderr']} names first.")
            print(f"PR {number} head test run, process {run.pid}: writing its stderr to "
                  f"{name} failed ({failure}); the run went on to its end, and that copy "
                  f"lacks the run's stderr from the first line that could not be written to "
                  f"it onward.\n"
                  f"The run's verdict still stands: the line below gives the run's exit code and "
                  f"SUMMARY line, from the run's stdout, not from this copy. "
                  f"{Path(__file__).name} exits 2 for the failed copy, even when the head "
                  f"test run itself exited nonzero, unless an earlier pull request's run or failed copy "
                  f"already set a nonzero exit code; that 2 says nothing about the tests.\n"
                  f"{where_to_find_it}",
                  flush=True)
            if first_failure == 0:
                first_failure = 2
        summaries = [line for line in (outputs / "stdout").read_text().splitlines()
                     if line.startswith(run_all_test_suites.SUMMARY_LINE_PREFIX)]
        summary = summaries[-1] if summaries else f"no SUMMARY line; see {outputs}/stderr"
        print(f"PR {number} head test run: exit {completed.returncode}; {summary}", flush=True)
        if completed.returncode != 0 and first_failure == 0:
            first_failure = completed.returncode
    return first_failure


if __name__ == "__main__":
    sys.exit(main())
