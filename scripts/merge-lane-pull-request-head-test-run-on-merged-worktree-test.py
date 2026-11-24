#!/usr/bin/env python3
"""Tests for merge-lane-pull-request-head-test-run-on-merged-worktree.py.

A scratch --review-tools-worktree-at-main, a real clone of a bare origin that
holds main and pull request heads at refs/pull/<n>/head, holds the real
rebuild program and a fake scripts/pull-request-head-test-run.py that logs its
arguments, working directory, the first PATH entry, whether GIT_DIR reached it
and whether its checkout holds main's newest file, prints a SUMMARY line and a
line on stderr, and exits with the code the case gives for its --checkout. The
program runs with GIT_DIR set, so a case that finds GIT_DIR absent shows the
program dropped it.

Run: python3 scripts/merge-lane-pull-request-head-test-run-on-merged-worktree-test.py
"""

import importlib.util
import pathlib

_start_and_end_lines_spec = importlib.util.spec_from_file_location(
    "nn_test_suite_start_time_line_and_end_results_line_print_common",
    pathlib.Path(__file__).resolve().parents[1] / "nn-systems/general-tools/nn-test-suite-start-time-line-and-end-results-line-print-common.py")
_start_and_end_lines = importlib.util.module_from_spec(_start_and_end_lines_spec)
_start_and_end_lines_spec.loader.exec_module(_start_and_end_lines)
_start_and_end_lines.nn_test_suite_start_time_line_print_now_and_end_results_line_print_at_normal_exit_register()

import importlib.util
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

_git_environment_fixture_spec = importlib.util.spec_from_file_location(
    "git_redirecting_environment_removal_test_fixture",
    Path(__file__).resolve().with_name(
        "git-redirecting-environment-removal-test-fixture.py"))
_git_environment_fixture = importlib.util.module_from_spec(_git_environment_fixture_spec)
_git_environment_fixture_spec.loader.exec_module(_git_environment_fixture)
_git_environment_fixture.remove_git_redirecting_environment_variables_from_this_process()
os.environ.update({"GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"})

PROGRAM = Path(__file__).with_name("merge-lane-pull-request-head-test-run-on-merged-worktree.py")
REBUILD_PROGRAM = PROGRAM.resolve().with_name(
    "merge-lane-pull-request-head-and-merged-worktrees-rebuild.py")
GIT_IDENTITY = ("-c", "user.name=test", "-c", "user.email=test@example.invalid")

FAKE_HEAD_TEST_RUN = r'''#!/usr/bin/env python3
import json, os, sys
argv = sys.argv[1:]
checkout = argv[argv.index("--checkout") + 1]
with open(os.environ["MERGE_LANE_HEAD_TEST_RUN_TEST_LOG"], "a") as log:
    log.write(json.dumps({"argv": argv, "cwd": os.getcwd(),
                          "first_path_entry": os.environ["PATH"].split(os.pathsep)[0],
                          "git_dir": os.environ.get("GIT_DIR"),
                          "holds_main_fix": os.path.exists(
                              os.path.join(checkout, "fixed-on-main.txt"))}) + "\n")
exit_code = json.loads(os.environ["MERGE_LANE_HEAD_TEST_RUN_TEST_EXITS"]).get(
    os.path.basename(checkout), 0)
print("pull-request-head-test-run: starting")
go_on = os.environ.get("MERGE_LANE_HEAD_TEST_RUN_TEST_GO_ON")
if go_on:
    import time
    print("a progress line on stderr", file=sys.stderr, flush=True)
    deadline = time.monotonic() + 20
    while not os.path.exists(go_on) and time.monotonic() < deadline:
        time.sleep(0.05)
    if not os.path.exists(go_on):
        sys.exit(9)
for _ in range(int(os.environ.get("MERGE_LANE_HEAD_TEST_RUN_TEST_EXTRA_STDERR_LINES", "0"))):
    print("y" * 200, file=sys.stderr)
print(f"SUMMARY: fake summary for {os.path.basename(checkout)}")
print("a line on stderr", file=sys.stderr)
sys.exit(exit_code)
'''

OVERLAPPING_FETCHES_CHILD = r'''
import importlib.util, os, sys
from pathlib import Path
spec = importlib.util.spec_from_file_location("head_test_run_program", sys.argv[1])
program = importlib.util.module_from_spec(spec)
spec.loader.exec_module(program)
for _ in range(10):
    commit, _failure = program.commit_fetched_from_origin(
        Path(sys.argv[2]), sys.argv[3], dict(os.environ))
    print(commit)
'''

failures = []


def review_worktrees_directory(helpers):
    return helpers.parent / f"{helpers.name}-review-worktrees"


def check(name, condition, detail=""):
    print(("PASS  " if condition else "FAIL  ") + name)
    if not condition:
        failures.append(name)
        if detail:
            print("      " + detail.replace("\n", "\n      "))


def git(directory, *arguments):
    return subprocess.run(["git", "-C", str(directory), *GIT_IDENTITY, *arguments],
                          capture_output=True, text=True, check=True).stdout.strip()


def commit_file(directory, name, contents):
    (directory / name).write_text(contents)
    git(directory, "add", name)
    git(directory, "commit", "-q", "-m", name)
    return git(directory, "rev-parse", "HEAD")


def build_review_tools_clone(scratch):
    """Make origin with main and heads for pull requests 7, 8, 9 and 11; return
    (the clone that is the review tools worktree, the author's clone)."""
    origin = scratch / "origin.git"
    author = scratch / "author"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(origin)], check=True)
    subprocess.run(["git", "init", "-q", "-b", "main", str(author)], check=True)
    commit_file(author, "on-main.txt", "main\n")
    git(author, "checkout", "-q", "-b", "topic")
    commit_file(author, "on-topic.txt", "topic\n")
    git(author, "checkout", "-q", "-b", "conflicting-topic", "main")
    commit_file(author, "conflict.txt", "from the pull request\n")
    git(author, "push", "-q", str(origin), "main:refs/heads/main",
        *(f"topic:refs/pull/{number}/head" for number in (7, 8, 9)),
        "conflicting-topic:refs/pull/11/head")
    review_tools = scratch / "main-checkout"
    subprocess.run(["git", "clone", "-q", str(origin), str(review_tools)], check=True)
    (review_tools / "scripts").mkdir()
    (review_tools / "scripts" / "pull-request-head-test-run.py").write_text(FAKE_HEAD_TEST_RUN)
    (review_tools / "scripts" / REBUILD_PROGRAM.name).symlink_to(REBUILD_PROGRAM)
    return review_tools, author


def without_main_commit(stdout):
    return re.sub(r"; tested merged onto main [0-9a-f]{12}$", "", stdout, flags=re.M)


def run_program(scratch, helpers, exits, *pull_requests, review_tools=None, cwd=None):
    log = scratch / "head-test-run-calls.log"
    log.unlink(missing_ok=True)
    completed = subprocess.run(
        [sys.executable, str(PROGRAM), *pull_requests,
         "--merge-lane-worktrees-and-outputs-directory", str(helpers),
         "--merge-lane-review-worktrees-directory", str(review_worktrees_directory(helpers)),
         "--review-tools-worktree-at-main", str(review_tools or scratch / "main-checkout")],
        capture_output=True, text=True, cwd=cwd,
        env={**os.environ, "GIT_DIR": str(scratch / "no-such-git-directory"),
             "MERGE_LANE_HEAD_TEST_RUN_TEST_LOG": str(log),
             "MERGE_LANE_HEAD_TEST_RUN_TEST_EXITS": json.dumps(exits)})
    calls = ([json.loads(line) for line in log.read_text().splitlines()]
             if log.exists() else [])
    completed.stdout_naming_main = completed.stdout
    completed.stdout = without_main_commit(completed.stdout)
    return completed, calls


def check_commit_fetched_from_origin(review_tools, author, origin, main_commit):
    spec = importlib.util.spec_from_file_location("head_test_run_program", PROGRAM)
    program = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(program)
    environment = dict(os.environ)
    pull_head = git(origin, "rev-parse", "refs/pull/8/head")
    references_before_overlap = git(review_tools, "for-each-ref")
    sources = [("refs/heads/main", main_commit), ("refs/pull/8/head", pull_head)] * 8
    def fetched_commits(pair):
        return subprocess.run(
            [sys.executable, "-c", OVERLAPPING_FETCHES_CHILD, str(PROGRAM), str(review_tools),
             pair[0]], capture_output=True, text=True).stdout.split()
    with ThreadPoolExecutor(max_workers=len(sources)) as pool:
        results = list(pool.map(fetched_commits, sources))
    check("overlapping processes fetching different sources each get their own source's commit",
          results == [[commit] * 10 for _, commit in sources], repr(results[:2]))
    check("overlapping fetches leave the references as they were",
          git(review_tools, "for-each-ref") == references_before_overlap)

    real_git_output = program.git_output_or_failure
    commands = []
    def recording_git_output(tools, command, environment):
        commands.append(command)
        return real_git_output(tools, command, environment)
    program.git_output_or_failure = recording_git_output
    commit, failure = program.commit_fetched_from_origin(
        review_tools, "refs/heads/main", environment)
    program.git_output_or_failure = real_git_output
    fetches = [command for command in commands if command[0] == "fetch"]
    check("the fetch names the commit with no destination, so no other run can see a "
          "reference of this run's",
          commit == main_commit and failure is None and len(fetches) == 1
          and fetches[0][-1] == main_commit
          and not any(command[0] == "update-ref" for command in commands), repr(commands))

    blob = git(author, "rev-parse", "HEAD:on-main.txt")
    git(author, "push", "-q", str(origin), f"{blob}:refs/pull/12/head")
    references_before = git(review_tools, "for-each-ref")
    commit, failure = program.commit_fetched_from_origin(
        review_tools, "refs/pull/12/head", environment)
    check("a fetched object that is not a commit is reported and leaves no reference behind",
          commit is None and failure and "rev-parse" in failure
          and git(review_tools, "for-each-ref") == references_before, f"{commit!r} {failure!r}")

    # ls-remote matches trailing path components, and these sort before the exact references.
    siblings = {"refs/heads/a/refs/heads/main": pull_head,
                "refs/heads/fix/refs/pull/8/head": main_commit,
                "refs/heads/fix/refs/pull/13/head": main_commit}
    git(author, "push", "-q", str(origin),
        *(f"{commit}:{reference}" for reference, commit in siblings.items()))
    check("main is the commit of refs/heads/main, not of a branch whose name ends in it",
          program.commit_fetched_from_origin(review_tools, "refs/heads/main", environment)
          == (main_commit, None))
    check("a pull request's head is the commit of its own reference, not of a branch whose "
          "name ends in it",
          program.commit_fetched_from_origin(review_tools, "refs/pull/8/head", environment)
          == (pull_head, None))
    commit, failure = program.commit_fetched_from_origin(
        review_tools, "refs/pull/13/head", environment)
    check("a reference only a longer branch name matches is reported as not found",
          commit is None and failure and "refs/pull/13/head" in failure,
          f"{commit!r} {failure!r}")
    git(author, "push", "-q", str(origin), *(f":{reference}" for reference in siblings))


def main():
    scratch = Path(tempfile.mkdtemp(prefix="merge-lane-head-test-run-test-")).resolve()
    try:
        review_tools, author = build_review_tools_clone(scratch)
        helpers = scratch / "merge-helpers"
        (helpers / "tripwire-bin").mkdir(parents=True)

        completed, calls = run_program(scratch, helpers, {}, "7", "8")
        detail = f"exit {completed.returncode}\n{completed.stdout}{completed.stderr}"
        check("each pull request is run in turn", [
            call["argv"][call["argv"].index("--checkout") + 1] for call in calls] == [
            str(review_worktrees_directory(helpers) / "pr7-merged"),
            str(review_worktrees_directory(helpers) / "pr8-merged")], detail)
        check("the run gets the paths under the worktrees and outputs directory, selecting by "
              "hr/store and, read-only, by the after-merge test run's recordings directory, "
              "and saving its recordings under hr/pr<n>",
              calls and calls[0]["argv"] == [
                  "--checkout", str(review_worktrees_directory(helpers) / "pr7-merged"),
                  "--log-store-root", str(helpers / "hr" / "pr7" / "log-store"),
                  "--temporary-directory", str(helpers / "hr" / "pr7" / "tmp"),
                  "--since", git(review_tools, "rev-parse", "origin/main"),
                  "--recorded-inputs-directory", str(helpers / "hr" / "store"),
                  "--save-recorded-inputs-to-directory",
                  str(helpers / "hr" / "pr7" / "recorded-inputs"),
                  "--also-leave-out-suites-whose-recorded-inputs-in-read-only-directory-match-checkout",
                  str(Path.home() / ".cache" / "nedsnodes-test-suite-recorded-inputs")],
              json.dumps(calls))
        check("the log-store root and temporary directory are made",
              (helpers / "hr" / "pr7" / "log-store").is_dir()
              and (helpers / "hr" / "pr7" / "tmp").is_dir(), detail)
        check("tripwire-bin is first on PATH",
              calls and all(call["first_path_entry"] == str(helpers / "tripwire-bin")
                            for call in calls), json.dumps(calls))
        check("GIT_DIR does not reach the run",
              calls and all(call["git_dir"] is None for call in calls), json.dumps(calls))
        check("the run starts in the worktrees and outputs directory",
              calls and all(call["cwd"] == str(helpers) for call in calls), json.dumps(calls))
        check("the run's stdout and stderr are kept under hr/pr<n>",
              "SUMMARY: fake summary for pr7-merged"
              in (helpers / "hr" / "pr7" / "stdout").read_text()
              and (helpers / "hr" / "pr7" / "stderr").read_text() == "a line on stderr\n",
              detail)
        check("the run's stderr is also printed on the program's stderr",
              completed.stderr == "a line on stderr\na line on stderr\n", detail)
        check("one line per pull request with its exit code and SUMMARY line",
              completed.stdout.splitlines() == [
                  "PR 7 head test run: exit 0; SUMMARY: fake summary for pr7-merged",
                  "PR 8 head test run: exit 0; SUMMARY: fake summary for pr8-merged"], detail)
        check("every run passing exits 0", completed.returncode == 0, detail)

        completed, calls = run_program(scratch, helpers, {"pr7-merged": 1, "pr8-merged": 4},
                                       "7", "8")
        detail = f"exit {completed.returncode}\n{completed.stdout}{completed.stderr}"
        check("a failed run does not stop the next one", len(calls) == 2, detail)
        check("the first nonzero exit code is the program's",
              completed.returncode == 1
              and "PR 8 head test run: exit 4;" in completed.stdout, detail)

        completed, calls = run_program(scratch, Path("merge-helpers"), {}, "7",
                                       review_tools=Path("main-checkout"), cwd=scratch)
        detail = f"exit {completed.returncode}\n{completed.stdout}{completed.stderr}"
        check("relative directory options run main's runner on the right checkout",
              completed.returncode == 0 and calls and calls[0]["argv"][:2] == [
                  "--checkout", str(review_worktrees_directory(helpers) / "pr7-merged")], detail)
        check("relative directory options still put an absolute tripwire-bin first on PATH",
              calls and calls[0]["first_path_entry"] == str(helpers / "tripwire-bin"),
              json.dumps(calls))

        go_on = scratch / "go-on"
        live = subprocess.Popen(
            [sys.executable, str(PROGRAM), "7",
             "--merge-lane-worktrees-and-outputs-directory", str(helpers),
             "--merge-lane-review-worktrees-directory", str(review_worktrees_directory(helpers)),
             "--review-tools-worktree-at-main", str(scratch / "main-checkout")],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            env={**os.environ, "MERGE_LANE_HEAD_TEST_RUN_TEST_LOG": str(scratch / "live.log"),
                 "MERGE_LANE_HEAD_TEST_RUN_TEST_EXITS": "{}",
                 "MERGE_LANE_HEAD_TEST_RUN_TEST_GO_ON": str(go_on)})
        first = live.stderr.readline()
        go_on.touch()
        stdout, rest = live.communicate(timeout=60)
        check("a line the run prints on stderr reaches the program's stderr while the run "
              "still runs, so a run stopped early has shown how far it got",
              first == "a progress line on stderr\n" and live.returncode == 0
              and without_main_commit(stdout)
              == "PR 7 head test run: exit 0; SUMMARY: fake summary for pr7-merged\n",
              f"exit {live.returncode}\n{first!r}\n{stdout}{rest}")

        # /dev/full fails every write with ENOSPC, as a full disk under the outputs does.
        if Path("/dev/full").exists():
            (helpers / "hr" / "pr9").mkdir(parents=True, exist_ok=True)
            (helpers / "hr" / "pr9" / "stderr").symlink_to("/dev/full")
            completed, calls = run_program(scratch, helpers, {}, "9")
            lines = completed.stdout.splitlines()
            check("when writing the run's stderr to <outputs>/stderr fails, the program "
                  "says so, with the failed close of that file, prints the run's exit code "
                  "and SUMMARY line, and exits 2",
                  completed.returncode == 2 and "Traceback" not in completed.stderr
                  and lines and lines[0].startswith("PR 9 head test run, process ")
                  and (f"writing its stderr to {helpers}/hr/pr9/stderr failed (OSError: "
                       "[Errno 28] No space left on device; closing it then failed too "
                       "(OSError: [Errno 28] No space left on device))") in lines[0]
                  and lines[-1]
                  == "PR 9 head test run: exit 0; SUMMARY: fake summary for pr9-merged",
                  f"exit {completed.returncode}\n{completed.stdout}{completed.stderr}")
            check("when writing the run's stderr to <outputs>/stderr fails, the program gives "
                  "the command that runs it again, not that file",
                  ("When you need the lost stderr, run the head test run for PR 9 again with "
                   "this command, from any directory: " + shlex.join([
                       sys.executable, str(PROGRAM.resolve()), "9",
                       "--head-commit", git(author, "rev-parse", "topic"),
                       "--main-commit", git(review_tools, "rev-parse", "origin/main"),
                       "--merge-lane-worktrees-and-outputs-directory", str(helpers.resolve()),
                       "--merge-lane-review-worktrees-directory", str(review_worktrees_directory(helpers).resolve()),
                       "--review-tools-worktree-at-main",
                       str((scratch / "main-checkout").resolve())])) in lines
                  and any(line.startswith("Before you run it, give it a stderr that takes "
                                          "every write: do not close its stderr")
                          for line in lines)
                  and "which holds all of it" not in completed.stdout,
                  f"exit {completed.returncode}\n{completed.stdout}{completed.stderr}")

            completed, calls = run_program(scratch, helpers, {"pr7-merged": 3}, "7", "9")
            check("a failed copy of a later pull request's run leaves an earlier run's "
                  "nonzero exit code as the program's",
                  completed.returncode == 3, f"exit {completed.returncode}\n{completed.stdout}")

            # Both copies fail: <outputs>/stderr is /dev/full and the program's stderr is a
            # pipe whose reading end is closed. The run itself exits 1.
            both = subprocess.Popen(
                [sys.executable, str(PROGRAM), "9",
                 "--merge-lane-worktrees-and-outputs-directory", str(helpers),
                 "--merge-lane-review-worktrees-directory", str(review_worktrees_directory(helpers)),
                 "--review-tools-worktree-at-main", str(scratch / "main-checkout")],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                env={**os.environ, "MERGE_LANE_HEAD_TEST_RUN_TEST_LOG": str(scratch / "both.log"),
                     "MERGE_LANE_HEAD_TEST_RUN_TEST_EXITS": json.dumps({"pr9-merged": 1}),
                     "MERGE_LANE_HEAD_TEST_RUN_TEST_EXTRA_STDERR_LINES": "2001"})
            both.stderr.close()
            try:
                stdout = both.stdout.read()
                both.wait(timeout=60)
            except subprocess.TimeoutExpired:
                both.kill()
                stdout = "still running after 60 s"
            lines = without_main_commit(stdout).splitlines()
            rerun_lines = [line for line in lines if line.startswith(
                "When you need the lost stderr, run the head test run for PR 9 again")]
            before_lines = [line for line in lines if line.startswith("Before you run it")]
            check("when both copies of the run's stderr fail, each copy-failure message gives "
                  "the command that runs it again, not the failed <outputs>/stderr, names that "
                  "file's own error as the one to fix first, and the program exits 2 although "
                  "the run exited 1",
                  both.returncode == 2 and len(rerun_lines) == 2
                  and "which holds all of it" not in stdout
                  and "writing its stderr to stderr failed (BrokenPipeError" in stdout
                  and len(before_lines) == 2
                  and all(f"{helpers}/hr/pr9/stderr is the copy that failed, fix what OSError: "
                          "[Errno 28] No space left on device; closing it then failed too "
                          "(OSError: [Errno 28] No space left on device) names first."
                          in line for line in before_lines)
                  and lines and lines[-1]
                  == "PR 9 head test run: exit 1; SUMMARY: fake summary for pr9-merged",
                  f"exit {both.returncode}\n{stdout}")
        else:
            print("SKIP  a failing write to <outputs>/stderr: /dev/full does not exist here")

        # The program's stderr is a pipe whose reading end is closed, so each write to it
        # fails; the run prints far more than a pipe holds.
        unread = subprocess.Popen(
            [sys.executable, str(PROGRAM), "7",
             "--merge-lane-worktrees-and-outputs-directory", str(helpers),
             "--merge-lane-review-worktrees-directory", str(review_worktrees_directory(helpers)),
             "--review-tools-worktree-at-main", str(scratch / "main-checkout")],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            env={**os.environ, "MERGE_LANE_HEAD_TEST_RUN_TEST_LOG": str(scratch / "unread.log"),
                 "MERGE_LANE_HEAD_TEST_RUN_TEST_EXITS": "{}",
                 "MERGE_LANE_HEAD_TEST_RUN_TEST_EXTRA_STDERR_LINES": "2001"})
        unread.stderr.close()
        try:
            stdout = unread.stdout.read()
            unread.wait(timeout=60)
        except subprocess.TimeoutExpired:
            unread.kill()
            stdout = "still running after 60 s"
        lines = without_main_commit(stdout).splitlines()
        check("when writing the run's stderr to the program's stderr fails, the run still "
              "goes to its end, its stderr file is whole, and the program says so with the "
              "run's process id, points at that file instead of a rerun, keeps the summary "
              "line unchanged, and exits 2",
              unread.returncode == 2 and len(lines) == 4
              and lines[0].startswith("PR 7 head test run, process ")
              and "writing its stderr to stderr failed (BrokenPipeError" in lines[0]
              and "that copy lacks the run's stderr from the first line that could not be "
                  "written to it onward" in lines[0]
              and "The run's verdict still stands" in lines[1]
              and f"{PROGRAM.name} exits 2 for the failed copy, even when the head test "
                  "run itself exited nonzero, unless an earlier pull request's run or failed copy already set a "
                  "nonzero exit code; that 2 says nothing about the tests" in lines[1]
              and lines[2] == (f"When you need the lost stderr, read {helpers}/hr/pr7/stderr, "
                               "which holds all of it.")
              and lines[3] == "PR 7 head test run: exit 0; SUMMARY: fake summary for pr7-merged"
              and len((helpers / "hr" / "pr7" / "stderr").read_text().splitlines()) == 2002,
              f"exit {unread.returncode}\n{stdout}")

        merged = review_worktrees_directory(helpers) / "pr7-merged"
        head_worktree = review_worktrees_directory(helpers) / "pr7-head"
        git(review_tools, "worktree", "add", "-q", "--detach", str(head_worktree), "origin/main")
        (head_worktree / "a-reviewer-is-reading-this.txt").write_text("in use\n")
        stale_merged = git(merged, "rev-parse", "HEAD")
        pinned_main = git(review_tools, "rev-parse", "HEAD")
        git(author, "checkout", "-q", "main")
        main_fix = commit_file(author, "fixed-on-main.txt", "fixed\n")
        git(author, "push", "-q", str(scratch / "origin.git"), "main:refs/heads/main")
        git(review_tools, "fetch", "-q", "origin", "refs/pull/8/head")
        fetch_head_before = (review_tools / ".git" / "FETCH_HEAD").read_text()
        tracking_main_before = git(review_tools, "rev-parse", "refs/remotes/origin/main")
        completed, calls = run_program(scratch, helpers, {}, "7")
        detail = f"exit {completed.returncode}\n{completed.stdout}{completed.stderr}"
        check("when origin's main has moved past the review tools worktree and pr<n>-merged, "
              "a direct run tests a rebuilt pr<n>-merged on origin's main, and says so",
              completed.returncode == 0 and len(calls) == 1 and calls[0]["holds_main_fix"]
              and git(merged, "rev-parse", "HEAD") != stale_merged
              and git(merged, "rev-parse", "HEAD^1") == main_fix
              and git(review_tools, "rev-parse", "HEAD") == pinned_main
              and f"; tested merged onto main {main_fix[:12]}\n" in completed.stdout_naming_main, detail)
        check("a direct run selects suites against the origin main it merged onto",
              calls and calls[0]["argv"][calls[0]["argv"].index("--since") + 1] == main_fix,
              json.dumps(calls))
        check("a direct run's fetches of main and of the head leave FETCH_HEAD as it was",
              (review_tools / ".git" / "FETCH_HEAD").read_text() == fetch_head_before, detail)
        check("a direct run's fetch of main leaves refs/remotes/origin/main as it was",
              git(review_tools, "rev-parse", "refs/remotes/origin/main") == tracking_main_before
              and tracking_main_before != main_fix, detail)
        check("a direct run leaves no reference of its own behind",
              git(review_tools, "for-each-ref", "refs/merge-lane-head-test-run") == "", detail)
        check_commit_fetched_from_origin(review_tools, author, scratch / "origin.git", main_fix)
        completed, calls = run_program(scratch, helpers, {}, "7", "--main-commit", pinned_main)
        detail = f"exit {completed.returncode}\n{completed.stdout}{completed.stderr}"
        check("--main-commit is the main merged onto, even when origin's main is newer",
              completed.returncode == 0 and git(merged, "rev-parse", "HEAD^1") == pinned_main
              and not calls[0]["holds_main_fix"]
              and f"; tested merged onto main {pinned_main[:12]}\n" in completed.stdout_naming_main, detail)
        check("--main-commit is also the commit suites are selected against, so a change "
              "between it and a newer tracking ref is not left out of selection",
              calls and calls[0]["argv"][calls[0]["argv"].index("--since") + 1] == pinned_main,
              json.dumps(calls))
        if Path("/dev/full").exists():
            completed, calls = run_program(scratch, helpers, {}, "9", "--main-commit", pinned_main)
            check("the lost-stderr rerun command of a pinned run names the same main and head, "
                  "although origin's main is newer",
                  shlex.join(["--head-commit", git(review_worktrees_directory(helpers) / "pr9-merged",
                                                   "rev-parse", "HEAD^2"),
                              "--main-commit", pinned_main]) in completed.stdout,
                  f"exit {completed.returncode}\n{completed.stdout}{completed.stderr}")
        completed, calls = run_program(scratch, helpers, {}, "7", "--main-commit", "no-such-commit")
        check("a --main-commit that names no commit exits 2 before any run",
              completed.returncode == 2 and calls == []
              and "not run: git cannot read the main commit: git rev-parse" in completed.stdout,
              f"exit {completed.returncode}\n{completed.stdout}{completed.stderr}")
        completed, calls = run_program(scratch, helpers, {}, "7")
        detail = f"exit {completed.returncode}\n{completed.stdout}{completed.stderr}"
        check("a run after --main-commit returns to origin's main",
              completed.returncode == 0 and git(merged, "rev-parse", "HEAD^1") == main_fix, detail)
        check("the rebuild leaves pr<n>-head in place, for the reviewers running beside it",
              (head_worktree / "a-reviewer-is-reading-this.txt").exists(), detail)

        reviewed_head = git(merged, "rev-parse", "HEAD^2")
        git(author, "checkout", "-q", "topic")
        pushed_head = commit_file(author, "pushed-later.txt", "later\n")
        git(author, "push", "-q", str(scratch / "origin.git"), "topic:refs/pull/7/head")
        completed, calls = run_program(scratch, helpers, {}, "7", "--head-commit", reviewed_head)
        detail = f"exit {completed.returncode}\n{completed.stdout}{completed.stderr}"
        check("--head-commit is the head merged, even when the pull request has a newer one",
              completed.returncode == 0 and git(merged, "rev-parse", "HEAD^2") == reviewed_head,
              detail)
        completed, calls = run_program(scratch, helpers, {}, "7")
        detail = f"exit {completed.returncode}\n{completed.stdout}{completed.stderr}"
        check("without --head-commit, the pull request's current head is merged",
              completed.returncode == 0 and git(merged, "rev-parse", "HEAD^2") == pushed_head,
              detail)

        completed, calls = run_program(scratch, helpers, {}, "7", "8",
                                       "--head-commit", reviewed_head)
        check("--head-commit with two pull requests exits 2 before any run",
              completed.returncode == 2 and calls == []
              and "--head-commit" in completed.stderr,
              f"exit {completed.returncode}\n{completed.stdout}{completed.stderr}")

        git(author, "checkout", "-q", "-b", "head-origin-replaces", pushed_head)
        replaced_head = commit_file(author, "replaced-by-a-rebase.txt", "replaced\n")
        git(author, "push", "-q", str(scratch / "origin.git"), "HEAD:refs/pull/7/head")
        git(author, "checkout", "-q", "-b", "head-after-rebase", pushed_head)
        rebased_head = commit_file(author, "after-the-rebase.txt", "rebased\n")
        rebased_marker = scratch / "head-already-rebased"
        rebasing_git = helpers / "tripwire-bin" / "git"
        real_git = shlex.quote(shutil.which("git"))
        # The head moves on origin right after the program first reads it.
        rebasing_git.write_text(
            f'#!/bin/sh\n{real_git} "$@"\ncode=$?\n'
            f'case "$*" in *refs/pull/7/head*)\n'
            f'  if [ ! -e {shlex.quote(str(rebased_marker))} ]; then\n'
            f'    touch {shlex.quote(str(rebased_marker))}\n'
            f'    {real_git} -C {shlex.quote(str(author))} push -q -f '
            f'{shlex.quote(str(scratch / "origin.git"))} '
            f'{rebased_head}:refs/pull/7/head\n'
            f'  fi;;\nesac\nexit $code\n')
        rebasing_git.chmod(0o755)
        completed, calls = run_program(scratch, helpers, {}, "7")
        rebasing_git.unlink()
        detail = f"exit {completed.returncode}\n{completed.stdout}{completed.stderr}"
        check("when the head is rebased on origin just after the program reads it, the commit "
              "it read is still merged and tested",
              completed.returncode == 0 and len(calls) == 1 and rebased_marker.exists()
              and git(scratch / "origin.git", "rev-parse", "refs/pull/7/head") == rebased_head
              and git(merged, "rev-parse", "HEAD^2") == replaced_head, detail)

        git_calls_log = scratch / "git-calls.log"
        git_logger = helpers / "tripwire-bin" / "git"
        git_logger.write_text(f'#!/bin/sh\nprintf "%s\\n" "$*" >> {shlex.quote(str(git_calls_log))}\n'
                              f'exec {shlex.quote(shutil.which("git"))} "$@"\n')
        git_logger.chmod(0o755)
        completed, calls = run_program(scratch, helpers, {}, "7")
        git_fetches = [line for line in git_calls_log.read_text().splitlines()
                       if " fetch " in f" {line} "]
        head_fetches = [line for line in git_fetches if rebased_head in line]
        check("a run fetches the pull request's head once, so the rebuild needs no second "
              "request to origin",
              completed.returncode == 0 and len(head_fetches) == 1
              and not any("pull/7/head" in line for line in git_fetches)
              and git(merged, "rev-parse", "HEAD^2") == rebased_head,
              f"exit {completed.returncode}, head fetches: {head_fetches}\n"
              f"{completed.stdout}{completed.stderr}")
        completed, calls = run_program(scratch, helpers, {}, "7",
                                       "--head-commit", reviewed_head.upper())
        check("an uppercase full hash is accepted as --head-commit",
              completed.returncode == 0 and git(merged, "rev-parse", "HEAD^2") == reviewed_head,
              f"exit {completed.returncode}\n{completed.stdout}{completed.stderr}")
        for option in ("--head-commit", "--main-commit"):
            git_calls_log.unlink(missing_ok=True)
            completed, calls = run_program(scratch, helpers, {}, "7", option, "")
            git_calls = git_calls_log.read_text() if git_calls_log.exists() else ""
            check(f"an empty {option} exits 2 with no suite run and no git call",
                  completed.returncode == 2 and calls == [] and git_calls == ""
                  and option in completed.stderr,
                  f"exit {completed.returncode}, {len(calls)} run(s), git calls: {git_calls!r}\n"
                  f"{completed.stdout}{completed.stderr}")
        for short_or_named in (reviewed_head[:12], "origin/topic"):
            git_calls_log.unlink(missing_ok=True)
            completed, calls = run_program(scratch, helpers, {}, "7",
                                           "--head-commit", short_or_named)
            git_calls = git_calls_log.read_text() if git_calls_log.exists() else ""
            check(f"a --head-commit that is not a full hash, {short_or_named}, exits 2 with no "
                  "suite run and no git call",
                  completed.returncode == 2 and calls == [] and git_calls == ""
                  and "full 40-character commit hash" in completed.stderr,
                  f"exit {completed.returncode}, {len(calls)} run(s), git calls: {git_calls!r}\n"
                  f"{completed.stdout}{completed.stderr}")
        git_logger.unlink()

        git(author, "checkout", "-q", "main")
        commit_file(author, "conflict.txt", "from main\n")
        git(author, "push", "-q", str(scratch / "origin.git"), "main:refs/heads/main")
        completed, calls = run_program(scratch, helpers, {}, "11", "8")
        detail = f"exit {completed.returncode}\n{completed.stdout}{completed.stderr}"
        check("a rebuild that fails on a merge conflict runs no tests for that pull request, "
              "says what failed, goes on to the next pull request and exits 2",
              completed.returncode == 2
              and [call["argv"][call["argv"].index("--checkout") + 1] for call in calls]
              == [str(review_worktrees_directory(helpers) / "pr8-merged")]
              and "PR 11 head test run: not run" in completed.stdout
              and "conflicts with main" in completed.stdout, detail)

        completed, calls = run_program(scratch, helpers, {}, "99")
        detail = f"exit {completed.returncode}\n{completed.stdout}{completed.stderr}"
        check("a pull request whose head origin does not have runs no tests and exits 2",
              completed.returncode == 2 and calls == []
              and "PR 99 head test run: not run" in completed.stdout, detail)

        rebuild_link = review_tools / "scripts" / REBUILD_PROGRAM.name
        rebuild_link.unlink()
        completed, calls = run_program(scratch, helpers, {}, "7")
        check("a review tools worktree without the rebuild program exits 2 before any run",
              completed.returncode == 2 and calls == []
              and f"{REBUILD_PROGRAM.name} is missing" in completed.stdout,
              f"exit {completed.returncode}\n{completed.stdout}{completed.stderr}")
        rebuild_link.symlink_to(REBUILD_PROGRAM)

        shutil.rmtree(helpers / "tripwire-bin")
        completed, calls = run_program(scratch, helpers, {}, "7")
        check("a missing tripwire-bin exits 2 before any run",
              completed.returncode == 2 and calls == []
              and "tripwire-bin is missing" in completed.stdout,
              f"exit {completed.returncode}\n{completed.stdout}{completed.stderr}")

        (helpers / "tripwire-bin").mkdir()
        completed, calls = run_program(scratch, helpers, {}, "7",
                                       review_tools=scratch / "no-such-checkout")
        check("a review tools worktree without pull-request-head-test-run.py exits 2 before any run",
              completed.returncode == 2 and calls == []
              and "pull-request-head-test-run.py is missing" in completed.stdout,
              f"exit {completed.returncode}\n{completed.stdout}{completed.stderr}")

        not_a_checkout = scratch / "holds-both-programs-but-is-not-a-git-checkout"
        (not_a_checkout / "scripts").mkdir(parents=True)
        (not_a_checkout / "scripts" / "pull-request-head-test-run.py").write_text(
            FAKE_HEAD_TEST_RUN)
        (not_a_checkout / "scripts" / REBUILD_PROGRAM.name).symlink_to(REBUILD_PROGRAM)
        completed, calls = run_program(scratch, helpers, {}, "7", review_tools=not_a_checkout)
        check("a review tools worktree that holds both programs but is not a git checkout "
              "exits 2 before any run, naming the git step that failed",
              completed.returncode == 2 and calls == []
              and "not run: git cannot read the main commit: git ls-remote" in completed.stdout
              and str(not_a_checkout) in completed.stdout,
              f"exit {completed.returncode}\n{completed.stdout}{completed.stderr}")
    finally:
        shutil.rmtree(scratch, ignore_errors=True)

    if failures:
        print(f"\n{len(failures)} case(s) failed")
        return 1
    print("\nall cases passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
