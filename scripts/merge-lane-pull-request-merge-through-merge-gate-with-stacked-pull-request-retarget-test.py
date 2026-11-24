#!/usr/bin/env python3
"""Tests for merge-lane-pull-request-merge-through-merge-gate-with-stacked-pull-request-retarget.py.

The program is loaded by path and its main() is called in this process, with
a fake scripts/merge-gate.sh in a scratch --review-tools-worktree-at-main,
a clone of a scratch origin repository at its origin/main, a
fake `gh` first on PATH, and HOME pointing at a scratch home that holds the
merge account's token file. The fake
gate answers each run from a numbered output file and exit code the case
writes. The fake `gh` logs every call with the GH_TOKEN it saw and answers
from a routes file the case writes, keyed by its first two arguments, or, for
`gh api`, by whether it reads or deletes the branch; a route that is a list
answers its nth call with its nth entry, and every later call with its last;
it does not filter `gh pr list` by base
branch, so the program's own filter is what each stacked case tests; a route
may remove a directory, such as origin, when it is called, or move origin's main
to a commit. A case may make the merge commit a new commit the clone lacks,
and may give the clone an upload-pack for origin that, once the
merge has run, runs another fetch into the clone while the program's fetch
waits, as another agent-seat's fetch into the same clone does. The
waits between gate runs go to a list instead of sleeping. A case may make the
pull request's review worktrees in a scratch review worktrees directory, as
worktrees of the review tools clone; a pr10-head that is a plain directory
instead makes git worktree remove fail. A route may kill the fake `gh` with
SIGKILL, and a case may put a `git` first on PATH that kills itself on
`git worktree remove`, of any path or of one path, or that fails, by a
signal or exit 1, on any git command holding a given text once the fake
`gh` has run the merge, and runs the real git otherwise. Origin's one commit holds a fake scripts/run-all-test-suites.py,
the runner the after-merge test run starts in its worktree at that commit,
which the fake `gh` reports as the merge commit; the fake runner logs its
arguments and directory and answers from an output file and exit code the
case writes, or passes when the case writes none. A case may add suite files to
origin's commit and, before the program runs, write recordings under the outputs
directory or under the runner's default recorded-inputs directory, which each case
points into its scratch home, or put a plain file or a read-only directory where
hr/store goes so no recording can be saved. The program's
SURVIVING_MUTANT_TEST_PRS_GO_AHEAD_PROGRAM is a fake that logs the GH_TOKEN it
saw and answers from the output and exit code the case gives, so no case reads
GitHub or the log-store through the real one.

Run: python3 scripts/merge-lane-pull-request-merge-through-merge-gate-with-stacked-pull-request-retarget-test.py
"""

import argparse
import contextlib
import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

_git_environment_fixture_spec = importlib.util.spec_from_file_location(
    "git_redirecting_environment_removal_test_fixture",
    Path(__file__).resolve().with_name("git-redirecting-environment-removal-test-fixture.py"))
_git_environment_fixture = importlib.util.module_from_spec(_git_environment_fixture_spec)
_git_environment_fixture_spec.loader.exec_module(_git_environment_fixture)
_git_environment_fixture.remove_git_redirecting_environment_variables_from_this_process()

PROGRAM = Path(__file__).with_name("merge-lane-pull-request-merge-through-merge-gate-with-stacked-pull-request-retarget.py")
_spec = importlib.util.spec_from_file_location("merge_lane_pull_request_merge", PROGRAM)
program = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(program)

PULL_REQUEST = "10"
HEAD = "a" * 40
SINCE = "2026-10-09T21:00:00Z"
BRANCH = "topic-of-pull-request-10"
TOKEN = "merge-lane-merge-test-token-not-a-credential"
EXPECTED_MERGE = ["pr", "merge", PULL_REQUEST, "--repo", "nedsnodes/nedsnodes", "--merge",
                  "--delete-branch", "--match-head-commit", HEAD]
GATE_PASSED = ("gate passed (#10): approved commit " + HEAD + "\n"
               "MERGE WITH THIS EXACT COMMAND:\n"
               "  gh pr merge 10 --repo nedsnodes/nedsnodes --merge --delete-branch "
               "--match-head-commit " + HEAD + "\n"
               "Run that command with GH_TOKEN set to the merge account's token.\n")
GATE_UNKNOWN = "GATE REFUSED (#10): mergeStateStatus is UNKNOWN\nUNKNOWN: run the gate again.\n"
GATE_REFUSED = "GATE REFUSED (#10): no APPROVED review found\n"

FAKE_GATE = r'''#!/bin/bash
directory=$MERGE_LANE_MERGE_TEST_DIRECTORY
echo "$*" >> "$directory/gate-calls.log"
# macOS's wc pads the count with spaces; the arithmetic expansion drops them.
count=$(( $(wc -l < "$directory/gate-calls.log") ))
[ -f "$directory/gate-$count.out" ] || count=last
cat "$directory/gate-$count.out"
exit "$(cat "$directory/gate-$count.exit")"
'''

FAKE_GH = r'''#!/usr/bin/env python3
import json, os, sys
directory = os.environ["MERGE_LANE_MERGE_TEST_DIRECTORY"]
argv = sys.argv[1:]
with open(os.path.join(directory, "gh-calls.log"), "a") as log:
    log.write(json.dumps({"argv": argv, "gh_token": os.environ.get("GH_TOKEN")}) + "\n")
routes = json.load(open(os.path.join(directory, "gh-routes.json")))
if argv[:2] == ["pr", "view"] and "headRefName,baseRefName" in argv:
    key = "view-branches"
elif argv[:2] == ["pr", "view"]:
    key = "view-state"
elif argv[:1] == ["api"]:
    key = "api-delete-branch" if "DELETE" in argv else "api-read-branch"
else:
    key = " ".join(argv[:2])
route = routes.get(key)
if isinstance(route, list):
    calls_so_far = os.path.join(directory, "gh-calls-so-far-" + key.replace(" ", "-"))
    count = int(open(calls_so_far).read()) if os.path.exists(calls_so_far) else 0
    open(calls_so_far, "w").write(str(count + 1))
    route = route[min(count, len(route) - 1)]
if route is None:
    sys.stderr.write("fake gh: unarranged call %r\n" % (argv,))
    sys.exit(97)
if route.get("killed"):
    os.kill(os.getpid(), 9)
if key == "pr merge":
    open(os.path.join(directory, "merge-ran"), "w").close()
if route.get("remove_directory"):
    import shutil
    shutil.rmtree(route["remove_directory"])
if route.get("origin_main_to"):
    import subprocess
    subprocess.run(["git", "--git-dir", route["origin"], "update-ref", "refs/heads/main",
                    route["origin_main_to"]], check=True)
sys.stdout.write(route.get("stdout", ""))
sys.stderr.write(route.get("stderr", ""))
sys.exit(route.get("exit", 0))
'''

FAKE_RUNNER = r'''#!/usr/bin/env python3
import json, os, sys
directory = os.environ["MERGE_LANE_MERGE_TEST_DIRECTORY"]
with open(os.path.join(directory, "runner-calls.log"), "a") as log:
    log.write(json.dumps({"argv": sys.argv[1:], "cwd": os.getcwd()}) + "\n")
answer = os.path.join(directory, "runner")
if "--only-suites-named" in sys.argv and os.path.exists(answer + "-rerun.out"):
    answer += "-rerun"
if os.path.exists(answer + ".out"):
    output, code = open(answer + ".out").read(), int(open(answer + ".exit").read())
else:
    output, code = ("PASS scripts/some-test.py (1s)\n"
                    "SUMMARY: 1 passed, 0 failed, 1 total; fake runner\n"), 0
if "SUMMARY:" in output and "--log-dir" in sys.argv and not os.path.exists(
        os.path.join(directory, "runner-writes-no-junit")):
    log_dir = sys.argv[sys.argv.index("--log-dir") + 1]
    os.makedirs(log_dir, exist_ok=True)
    if os.path.exists(answer + ".junit"):
        junit = open(answer + ".junit").read()
    else:
        # Each suite on a PASS or FAIL line is the one test named for it, as the runner writes a
        # suite that printed no case line.
        verdicts, failure = {}, '<failure message="x"/>'
        for line in output.splitlines():
            if line.startswith(("PASS ", "FAIL ")):
                verdicts.setdefault(line.split()[1], line.startswith("FAIL "))
        junit = "<testsuites>" + "".join(
            f'<testsuite name="{suite}" ran_to_the_end="true" judged="true">'
            f'<testcase name="{suite}">{failure if failed else ""}'
            f"</testcase></testsuite>" for suite, failed in sorted(verdicts.items())) + "</testsuites>"
    open(os.path.join(log_dir, "junit.xml"), "w").write(junit)
sys.stdout.write(output)
sys.stdout.flush()
if code < 0:
    os.kill(os.getpid(), -code)
sys.exit(code)
'''
# The clone's upload-pack for origin. Once the merge has run, at the first fetch that asks
# origin for objects, it runs another fetch into the clone to its end before serving the
# first: the first fetch has by then read origin/main's old value, as when another agent-seat
# fetches into the same clone at the same moment.
COMPETING_FETCH_UPLOAD_PACK = r'''#!/usr/bin/env python3
import os, subprocess, sys
directory = os.environ["MERGE_LANE_MERGE_TEST_DIRECTORY"]
marker = os.path.join(directory, "competing-fetch-ran")
child = subprocess.Popen(["git", "upload-pack", *sys.argv[1:]], stdin=subprocess.PIPE)
while True:
    chunk = os.read(0, 65536)
    if not chunk:
        break
    if (b"want " in chunk and os.path.exists(os.path.join(directory, "merge-ran"))
            and not os.path.exists(marker)):
        open(marker, "w").close()
        subprocess.run(["git", "-C", os.path.join(directory, "review-tools"), "fetch",
                        "--quiet", "origin"], check=True, stdin=subprocess.DEVNULL)
    child.stdin.write(chunk)
    child.stdin.flush()
child.stdin.close()
sys.exit(child.wait())
'''
FAKE_GO_AHEAD = r'''#!/usr/bin/env python3
import json, os, sys
directory = os.environ["MERGE_LANE_MERGE_TEST_DIRECTORY"]
with open(os.path.join(directory, "go-ahead-calls.log"), "a") as log:
    log.write(json.dumps({"argv": sys.argv[1:], "gh_token": os.environ.get("GH_TOKEN")}) + "\n")
answer = json.load(open(os.path.join(directory, "go-ahead-answer.json")))
sys.stdout.write(answer[0])
sys.exit(answer[1])
'''
GO_AHEAD_COUNT_ONLY = ("12 open pull requests that are not drafts wait for merge-lane-2 to review "
                       "or merge them. ... The count is over 10, the most at which merge-lane-2's "
                       "queue is quiet, so no agent-seat holding mutant-test tasks is released; "
                       "fake go-ahead\n", 3)
RUNNER_PASSED_SUMMARY ="SUMMARY: 1 passed, 0 failed, 1 total; fake runner"
RUNNER_FAILED = ("PASS scripts/some-test.py (1s)\n"
                 "FAIL scripts/broken-test.py exit 1 (2s)\n"
                 "\n1 failed:\n"
                 "FAIL scripts/broken-test.py exit 1 — log /logs/broken-test.py.log\n"
                 "SUMMARY: 1 passed, 1 failed, 2 total; fake runner\n")
RUNNER_COULD_NOT_RUN = "run-all-test-suites.py: git cannot resolve the COMMIT given\n"

failures = []
GIT_ENVIRONMENT = dict(os.environ)
GIT_IDENTITY = ["-c", "user.name=merge-lane-test", "-c", "user.email=test@example.invalid"]


# The merge program's instructions to tell the user a STOP message, written out whole here
# so that a change to the program's wording fails a case.
TELL_THE_USER_WITH_THE_GIT_ERROR = ("tell the user this message as printed, from its STOP "
                                    "line, which quotes git's error, through this line.")
TELL_THE_USER_WITH_THE_GH_ERROR = ("tell the user this message as printed, from its STOP line, "
                                   "which quotes gh's error, through this line.")
TELL_THE_USER_WITH_THE_ERROR = ("tell the user this message as printed, from its STOP line, "
                                "which quotes the error, through this line.")
TELL_THE_USER_WITH_BOTH_GH_ERRORS = ("tell the user this message as printed, from its STOP line, "
                                     "which quotes gh's error, through this line, and the error "
                                     "the deletion command printed.")
RERUN_ONCE_THEN = "Run this again once; if it fails the same way, "


def git(*arguments, cwd=None):
    subprocess.run(["git", *GIT_IDENTITY, *arguments], cwd=cwd, env=GIT_ENVIRONMENT,
                   check=True, capture_output=True, stdin=subprocess.DEVNULL)


def origin_with_one_commit(scratch, extra_files=None):
    """Return a bare origin repository whose main has one commit, holding extra_files too."""
    origin = scratch / "origin.git"
    seed = scratch / "origin-seed"
    git("init", "-q", "-b", "main", str(seed))
    (seed / "README").write_text("seed\n")
    (seed / "scripts").mkdir()
    (seed / "scripts" / "run-all-test-suites.py").write_text(FAKE_RUNNER)
    for relative, body in (extra_files or {}).items():
        (seed / relative).write_text(body)
    git("add", "README", "scripts", cwd=seed)
    git("commit", "-q", "-m", "seed", cwd=seed)
    git("clone", "-q", "--bare", str(seed), str(origin))
    return origin


def git_output(checkout, *arguments, check=True):
    """Return what git prints in checkout, stripped; "" when it fails and check is False."""
    completed = subprocess.run(["git", "-C", str(checkout), *arguments], capture_output=True,
                               text=True, env=GIT_ENVIRONMENT, stdin=subprocess.DEVNULL)
    if completed.returncode != 0 and check:
        raise RuntimeError(f"git {arguments} failed: {completed.stderr}")
    return completed.stdout.strip() if completed.returncode == 0 else ""


def git_path(checkout, name):
    """Return the path of name in checkout's git directory."""
    return checkout / git_output(checkout, "rev-parse", "--git-path", name)


def check(name, condition, detail=""):
    print(("PASS  " if condition else "FAIL  ") + name)
    if not condition:
        failures.append(name)
        if detail:
            print("      " + detail.replace("\n", "\n      "))


def default_routes(open_pull_requests, edit_exit=0, merge_exit=0):
    return {
        "view-branches": {"stdout": json.dumps({"headRefName": BRANCH, "baseRefName": "main"})},
        "pr list": {"stdout": json.dumps(open_pull_requests)},
        "pr edit": {"exit": edit_exit, "stderr": "" if edit_exit == 0 else "edit refused\n"},
        "pr merge": {"exit": merge_exit},
        "view-state": {"stdout": '{"state":"MERGED","mc":"MERGE_COMMIT"}\n'},
    }


STACKED_AND_NOT = [{"number": 20, "baseRefName": BRANCH},
                   {"number": 21, "baseRefName": "main"},
                   {"number": 22, "baseRefName": "some-other-topic"}]


def run_case(scratch, name, gate_answers, routes, token=TOKEN, review_tools_state="at-main",
             review_worktrees_state="none", git_killed_on_worktree_remove=None,
             git_fails_after_merge_on=None, git_killed_before_the_merge_on=None,
             runner_answer=None, head_test_run_test_logs=(),
             origin_files=None, before_the_program_runs=None,
             merge_commit_new_to_the_clone=False,
             another_fetch_races_the_after_merge_fetch=False,
             go_ahead_answer=GO_AHEAD_COUNT_ONLY):
    """Run main() once; return (exit code, output, gh calls, gate calls, waits).

    Each "MERGE_COMMIT" in routes becomes origin's commit, and each "ORIGIN"
    the path of origin.
    git_killed_on_worktree_remove: None, or the text a git worktree remove
    command must hold for the fake git to kill itself; "" kills on every one.
    git_fails_after_merge_on: None, or (text, "kill" or "exit 1"): once the
    merge has run, a git command holding text is killed by SIGKILL or exits 1.
    git_killed_before_the_merge_on: None, or the text a git command run before
    the merge must hold for the fake git to kill itself.
    runner_answer: None, for a fake runner that passes, or (output, exit code);
    a negative exit code -N makes the fake runner kill itself with signal N.
    head_test_run_test_logs: (file name, contents) pairs, each written as a head
    test run's test log under outputs/hr/pr10/log-store; contents None makes a
    directory there instead, and bytes are written as they are. Each "MERGED"
    in a file name or a text becomes a commit made in the review tools clone
    with the tree of origin's commit, as pr10-merged has when main has not
    moved since the head test run; its hash is in the case's merged-commit file.
    origin_files: path -> body, added to origin's one commit.
    before_the_program_runs: None, or a function given the case's directory, called last
    before main() runs.
    merge_commit_new_to_the_clone: the merge commit is a new commit the clone lacks, which
    a "pr merge" route with origin_main_to can make origin's main.
    another_fetch_races_the_after_merge_fetch: as merge_commit_new_to_the_clone, and the
    clone's upload-pack is COMPETING_FETCH_UPLOAD_PACK.
    go_ahead_answer: (output, exit code) of the fake go-ahead program.

    review_tools_state: "at-main", "behind-main" (origin/main moved on after the
    clone, by a commit that adds new-on-main.txt), "no-origin" (the clone's
    origin is gone) or "no-gate".
    review_worktrees_state: "none", "both" (pr10-head and pr10-merged are
    worktrees, pr10-merged with an untracked file), "merged-only" (pr10-merged
    is a worktree, pr10-head is not there) or "head-not-a-worktree" (pr10-head
    is a plain directory, pr10-merged a worktree).
    """
    directory = scratch / name
    directory.mkdir()
    bin_directory = directory / "bin"
    bin_directory.mkdir()
    (bin_directory / "gh").write_text(FAKE_GH)
    (bin_directory / "gh").chmod(0o755)
    (bin_directory / "go-ahead.py").write_text(FAKE_GO_AHEAD)
    (directory / "go-ahead-answer.json").write_text(json.dumps(list(go_ahead_answer)))
    if git_killed_on_worktree_remove is not None:
        (bin_directory / "git").write_text(
            '#!/bin/bash\ncase " $* " in *" worktree remove "*'
            f'{git_killed_on_worktree_remove}*) kill -9 $$;; esac\n'
            f'exec {shutil.which("git")} "$@"\n')
        (bin_directory / "git").chmod(0o755)
    if git_fails_after_merge_on is not None:
        text, failure = git_fails_after_merge_on
        (bin_directory / "git").write_text(
            '#!/bin/bash\n'
            f'if [ -e "{directory}/merge-ran" ]; then case " $* " in *"{text}"*) '
            f'{"kill -9 $$" if failure == "kill" else "echo fake git failed >&2; exit 1"};; '
            'esac; fi\n'
            f'exec {shutil.which("git")} "$@"\n')
        (bin_directory / "git").chmod(0o755)
    if git_killed_before_the_merge_on is not None:
        (bin_directory / "git").write_text(
            '#!/bin/bash\n'
            f'if [ ! -e "{directory}/merge-ran" ]; then case " $* " in '
            f'*"{git_killed_before_the_merge_on}"*) kill -9 $$;; esac; fi\n'
            f'exec {shutil.which("git")} "$@"\n')
        (bin_directory / "git").chmod(0o755)
    origin = origin_with_one_commit(directory, origin_files)
    review_tools = directory / "review-tools"
    git("clone", "-q", str(origin), str(review_tools))
    git("checkout", "-q", "--detach", "origin/main", cwd=review_tools)
    if merge_commit_new_to_the_clone or another_fetch_races_the_after_merge_fetch:
        seed = directory / "origin-seed"
        git("commit", "-q", "--allow-empty", "-m", "Merge pull request #10", cwd=seed)
        # Not under refs/heads, so the fetch before the gate does not bring it into the clone.
        git("push", "-q", str(origin), "HEAD:refs/merge-test/merge-commit", cwd=seed)
    if another_fetch_races_the_after_merge_fetch:
        upload_pack = directory / "competing-fetch-upload-pack"
        upload_pack.write_text(COMPETING_FETCH_UPLOAD_PACK)
        upload_pack.chmod(0o755)
        git("config", "remote.origin.uploadpack", str(upload_pack), cwd=review_tools)
    if review_tools_state != "no-gate":
        (review_tools / "scripts").mkdir(parents=True, exist_ok=True)
        (review_tools / "scripts" / "merge-gate.sh").write_text(FAKE_GATE)
    if review_tools_state == "behind-main":
        seed = directory / "origin-seed"
        (seed / "README").write_text("moved on\n")
        (seed / "new-on-main.txt").write_text("new\n")
        git("add", "README", "new-on-main.txt", cwd=seed)
        git("commit", "-q", "-m", "main moves on", cwd=seed)
        git("push", "-q", str(origin), "main", cwd=seed)
    review_worktrees = directory / "review-worktrees"
    if review_worktrees_state == "both":
        git("worktree", "add", "-q", "--detach", str(review_worktrees / "pr10-head"),
            cwd=review_tools)
    if review_worktrees_state == "head-not-a-worktree":
        (review_worktrees / "pr10-head").mkdir(parents=True)
        (review_worktrees / "pr10-head" / "README").write_text("not a worktree\n")
    if review_worktrees_state != "none":
        git("worktree", "add", "-q", "--detach", str(review_worktrees / "pr10-merged"),
            cwd=review_tools)
        (review_worktrees / "pr10-merged" / "left-by-a-test-run.txt").write_text("untracked\n")
    if head_test_run_test_logs:
        merged = subprocess.run(
            ["git", *GIT_IDENTITY, "-C", str(review_tools), "commit-tree", "HEAD^{tree}",
             "-p", "HEAD", "-m", "Merge commit into HEAD"],
            capture_output=True, text=True, env=GIT_ENVIRONMENT, check=True).stdout.strip()
        (directory / "merged-commit").write_text(merged)
        machine_directory = (directory / "outputs" / "hr" / "pr10" / "log-store"
                             / "pull-request-head-test-runs" / "ned-box")
        machine_directory.mkdir(parents=True)
        for file_name, contents in head_test_run_test_logs:
            test_log = machine_directory / file_name.replace("MERGED", merged)
            if contents is None:
                test_log.mkdir()
            elif isinstance(contents, bytes):
                test_log.write_bytes(contents)
            else:
                test_log.write_text(contents.replace("MERGED", merged))
    if review_tools_state == "no-origin":
        shutil.rmtree(origin)
    for number, (output, exit_code) in enumerate(gate_answers, start=1):
        (directory / f"gate-{number}.out").write_text(output)
        (directory / f"gate-{number}.exit").write_text(str(exit_code))
    (directory / "gate-last.out").write_text(gate_answers[-1][0])
    (directory / "gate-last.exit").write_text(str(gate_answers[-1][1]))
    merge_commit = subprocess.run(["git", "-C", str(directory / "origin-seed"), "rev-parse",
                                   "HEAD"], capture_output=True, text=True, env=GIT_ENVIRONMENT,
                                  check=True).stdout.strip()
    (directory / "gh-routes.json").write_text(
        json.dumps(routes).replace("MERGE_COMMIT", merge_commit).replace("ORIGIN", str(origin)))
    if runner_answer is not None:
        (directory / "runner.out").write_text(runner_answer[0])
        (directory / "runner.exit").write_text(str(runner_answer[1]))
    home = directory / "home"
    (home / ".config" / "nedsnodes").mkdir(parents=True)
    if token is not None:
        (home / ".config" / "nedsnodes" / "ned-review-merge.token").write_text(token + "\n")

    waits = []
    saved_path, saved_home = os.environ["PATH"], os.environ.get("HOME")
    os.environ["PATH"] = f"{bin_directory}{os.pathsep}{saved_path}"
    os.environ["HOME"] = str(home)
    # The runner fixed this path from the real HOME when it was imported.
    runner = program.common.run_all_test_suites
    saved_default = runner.DEFAULT_RECORDED_INPUTS_DIRECTORY
    saved_go_ahead = program.SURVIVING_MUTANT_TEST_PRS_GO_AHEAD_PROGRAM
    program.SURVIVING_MUTANT_TEST_PRS_GO_AHEAD_PROGRAM = bin_directory / "go-ahead.py"
    runner.DEFAULT_RECORDED_INPUTS_DIRECTORY = default_recorded_inputs_directory(directory)
    os.environ["MERGE_LANE_MERGE_TEST_DIRECTORY"] = str(directory)
    output = io.StringIO()
    if before_the_program_runs is not None:
        before_the_program_runs(directory)
    try:
        with contextlib.redirect_stdout(output):
            exit_code = program.main([PULL_REQUEST, HEAD, SINCE, "--review-tools-worktree-at-main",
                                      str(review_tools), "--merge-lane-review-worktrees-directory",
                                      str(review_worktrees),
                                      "--merge-lane-worktrees-and-outputs-directory",
                                      str(directory / "outputs")], wait=waits.append)
    finally:
        runner.DEFAULT_RECORDED_INPUTS_DIRECTORY = saved_default
        program.SURVIVING_MUTANT_TEST_PRS_GO_AHEAD_PROGRAM = saved_go_ahead
        os.environ["PATH"] = saved_path
        if saved_home is None:
            del os.environ["HOME"]
        else:
            os.environ["HOME"] = saved_home
    gh_log = directory / "gh-calls.log"
    gh_calls = ([json.loads(line) for line in gh_log.read_text().splitlines()]
                if gh_log.exists() else [])
    gate_log = directory / "gate-calls.log"
    gate_calls = gate_log.read_text().splitlines() if gate_log.exists() else []
    return exit_code, output.getvalue(), gh_calls, gate_calls, waits


def head_test_run_record(commit, exit_code, started="2026-11-07T21:07:48Z"):
    """A record in the shape pull-request-head-test-run.py writes, without the runner's output."""
    lines = [f'head: commit {commit} ("Merge commit into HEAD")',
             "selecting since: commit 0123456789ab, the merge base",
             f"runner exit code: {exit_code}",
             f"pull-request-head-test-run exit code: {exit_code}"]
    return "\n".join([f"pull-request-head-test-run: ned-box, started {started}, a record of "
                      f"{len(lines) + 1} lines", *lines]) + "\n"


def merged_commit(scratch, name):
    return (scratch / name / "merged-commit").read_text()


def tree_of(scratch, name, commit):
    return subprocess.run(["git", "-C", str(scratch / name / "review-tools"), "rev-parse",
                           f"{commit}^{{tree}}"], capture_output=True, text=True,
                          env=GIT_ENVIRONMENT, check=True).stdout.strip()


def registered_worktrees(review_tools):
    listing = subprocess.run(["git", "-C", str(review_tools), "worktree", "list", "--porcelain"],
                             capture_output=True, text=True, env=GIT_ENVIRONMENT, check=True)
    return [line.split(" ", 1)[1] for line in listing.stdout.splitlines()
            if line.startswith("worktree ")]


def argvs(gh_calls):
    return [call["argv"] for call in gh_calls]


def printed_in_order(output, *lines):
    """True when output holds every line, each after the one before; False, never an
    exception, when one is missing, so its check prints FAIL and later cases still run."""
    start = 0
    for line in lines:
        start = output.find(line, start)
        if start == -1:
            return False
        start += len(line)
    return True


def default_recorded_inputs_directory(directory):
    """The runner's default recorded-inputs directory while run_case runs a case in directory."""
    return directory / "home" / ".cache" / "nedsnodes-test-suite-recorded-inputs"


def index_of(calls, prefix):
    for index, argv in enumerate(calls):
        if argv[:len(prefix)] == prefix:
            return index
    return None


def go_ahead_calls_of(scratch, name):
    log = scratch / name / "go-ahead-calls.log"
    return [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []


def runner_calls(scratch, name):
    log = scratch / name / "runner-calls.log"
    return [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []


def origin_commit(scratch, name):
    return subprocess.run(["git", "-C", str(scratch / name / "origin-seed"), "rev-parse", "HEAD"],
                          capture_output=True, text=True, env=GIT_ENVIRONMENT,
                          check=True).stdout.strip()


RECORDED_SUITE = "scripts/recorded-test.py"
STALE_SUITE = "scripts/recorded-stale-test.py"


def recording_in_store(store, directory, suite, blob):
    """Write a passing recording of suite, which read only itself with the given blob, under
    store's directory for origin's root commit; return its path."""
    runner = program.common.run_all_test_suites
    root = subprocess.run(["git", "-C", str(directory / "origin-seed"), "rev-list",
                           "--max-parents=0", "HEAD"], capture_output=True, text=True,
                          env=GIT_ENVIRONMENT, check=True).stdout.split()[0]
    path = runner.recording_file_for(store / root[:16], suite)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "format": runner.RECORDED_INPUTS_FORMAT_VERSION, "suite": suite, "exit": 0,
        "seconds": 1.0, "skipped_cases": 0, "skipped_cases_this_machine_cannot_run": 0,
        "reads": {suite: blob}, "looked_for": {}, "lists": {},
        "git_commands_on_the_checkout": [], "git_calls_run_from_the_checkout": [],
        "files_fingerprint": "unused without git calls"}))
    return path


def blob_of(directory, suite):
    return subprocess.run(["git", "-C", str(directory / "origin-seed"), "rev-parse",
                           f"HEAD:{suite}"], capture_output=True, text=True,
                          env=GIT_ENVIRONMENT, check=True).stdout.strip()


def failed_suites_record_file(directory):
    return (directory / "home" / ".local" / "state" / "nedsnodes"
            / "failed-after-merge-test-suites-on-main.json")


def failed_suites_record_written(directory, suite="scripts/broken-test.py", tests=None):
    record = failed_suites_record_file(directory)
    record.parent.mkdir(parents=True, exist_ok=True)
    seed_head = subprocess.run(["git", "-C", str(directory / "origin-seed"), "rev-parse", "HEAD"],
                               capture_output=True, text=True, env=GIT_ENVIRONMENT,
                               check=True).stdout.strip()
    record.write_text(json.dumps({suite: {"failed_tests": {test: {
        "commit": seed_head, "last_failed_commit": seed_head, "pull_request": "9",
        "log": "/logs/old.log", "failed_at": "2026-11-20T17:18:00Z",
        "repair_task_agent_seat": "author-seat", "repair_task_id": 3}
        for test in (tests or [suite])}}}))


def junit_of_broken_suite(failing, passing, skipped=(), ran_to_the_end=True):
    cases = ("".join(f'<testcase name="{name}"><failure message="x"/></testcase>' for name in failing)
             + "".join(f'<testcase name="{name}"/>' for name in passing)
             + "".join(f'<testcase name="{name}"><skipped/></testcase>' for name in skipped))
    return (f'<testsuites><testsuite name="scripts/broken-test.py" judged="true" '
            f'ran_to_the_end="{str(ran_to_the_end).lower()}">{cases}</testsuite></testsuites>')


def recorded_tests_with_task(tests, failing, passing, task_text='{"status": "pending"}',
                             rerun=False, skipped=(), ran_to_the_end=True):
    def prepare(directory):
        task_list = author_seat_made(directory)
        failed_suites_record_written(directory, tests=tests)
        (task_list / "3.json").write_text(task_text)
        name = "runner-rerun" if rerun else "runner"
        (directory / f"{name}.junit").write_text(
            junit_of_broken_suite(failing, passing, skipped, ran_to_the_end))
        if rerun:
            (directory / "runner-rerun.out").write_text(RUNNER_FAILED)
            (directory / "runner-rerun.exit").write_text("1")
    return prepare


def tasks_of_author(directory):
    return sorted((directory / "home" / ".claude" / "tasks" / "nedsnodes-author-seat-tasks").glob("*.json"))


def failed_suites_record_of(directory):
    return json.loads(failed_suites_record_file(directory).read_text())


def newest_main_commit_left_no_test_failing_file(directory):
    return (directory / "home" / ".local" / "state" / "nedsnodes"
            / "newest-main-commit-whose-after-merge-test-run-left-no-test-failing.txt")


def newest_main_commit_left_no_test_failing_of(directory):
    path = newest_main_commit_left_no_test_failing_file(directory)
    return path.read_text().strip() if path.is_file() else None


def newest_main_commit_left_no_test_failing_written(text):
    """A before_the_program_runs that writes text to the file, makes a directory there when
    text is None, and writes nothing when text is "". In text, "PARENT" becomes the merge
    commit's parent, origin's first commit, and "UNRELATED" a commit with no parent in the
    review tools clone."""
    def prepare(directory):
        if text == "":
            return
        path = newest_main_commit_left_no_test_failing_file(directory)
        path.parent.mkdir(parents=True, exist_ok=True)
        if text is None:
            path.mkdir()
            return
        review_tools = directory / "review-tools"
        unrelated = subprocess.run(
            ["git", *GIT_IDENTITY, "-C", str(review_tools), "commit-tree", "HEAD^{tree}",
             "-m", "unrelated"], capture_output=True, text=True, env=GIT_ENVIRONMENT,
            check=True).stdout.strip()
        parent = git_output(directory / "origin-seed", "rev-parse", "HEAD~1")
        path.write_text(text.replace("PARENT", parent).replace("UNRELATED", unrelated))
    return prepare


def newest_main_commit_left_no_test_failing_cases(scratch):
    routes = default_routes([])
    routes["pr merge"] = {"origin_main_to": "MERGE_COMMIT", "origin": "ORIGIN"}

    def case(name, written, **options):
        exit_code, output, _, _, _ = run_case(
            scratch, name, [(GATE_PASSED, 0)], routes, merge_commit_new_to_the_clone=True,
            before_the_program_runs=newest_main_commit_left_no_test_failing_written(written),
            **options)
        directory = scratch / name
        return (exit_code, output, runner_calls(scratch, name),
                git_output(directory / "origin-seed", "rev-parse", "HEAD~1"),
                origin_commit(scratch, name), newest_main_commit_left_no_test_failing_of(directory))

    exit_code, output, calls, parent, merge_commit, recorded = case(
        "no-test-failing-at-parent", "PARENT\n")
    path = newest_main_commit_left_no_test_failing_file(scratch / "no-test-failing-at-parent")
    check("after-merge test run selects since the recorded newest main commit whose after-merge "
          "test run left no test failing, and then records the merge commit in its place",
          exit_code == 0 and len(calls) == 1
          and calls[0]["argv"][:2] == ["--only-suites-whose-recorded-inputs-changed-since", parent]
          and f"selecting the nn-test-suites whose recorded inputs changed since {parent[:12]}, "
              f"the newest main commit whose after-merge test run left no test failing" in output
          and "since the head commit" not in output
          and recorded == merge_commit
          and f"recorded {merge_commit[:12]} in {path}, so the next after-merge test run selects "
              f"the suites whose recorded inputs changed since it" in output,
          f"exit {exit_code}\n{output}\n{calls}\n{recorded}")

    for name, runner_answer, why in (
            ("no-test-failing-kept-after-a-failed-run", (RUNNER_FAILED, 1), "failed"),
            ("no-test-failing-kept-after-a-run-with-no-summary",
             ("PASS scripts/some-test.py (1s)\n", 0), "printed no SUMMARY line"),
            ("no-test-failing-kept-after-a-killed-run", ("PASS scripts/some-test.py (1s)\n", -9),
             "was killed")):
        exit_code, output, calls, parent, merge_commit, recorded = case(
            name, "PARENT\n", runner_answer=runner_answer)
        check(f"an after-merge test run that {why} exits 3 and leaves the recorded commit as it "
              f"was, so the next run still compares with the commit before the break",
              exit_code == 3 and recorded == parent
              and calls[0]["argv"][:2] == ["--only-suites-whose-recorded-inputs-changed-since",
                                           parent],
              f"exit {exit_code}\n{output}\n{recorded}")

    for name, written, why in (
            ("no-test-failing-file-missing", "", "does not exist"),
            ("no-test-failing-file-malformed", "not a commit\n",
             "does not hold one commit hash of 40 characters. The next after-merge test run that "
             "leaves no test failing replaces it"),
            ("no-test-failing-file-names-an-unknown-commit", "b" * 40 + "\n",
             f"git could not say whether {'b' * 12}, which "),
            ("no-test-failing-file-names-a-commit-not-an-ancestor", "UNRELATED\n",
             "is not an ancestor of ")):
        exit_code, output, calls, parent, merge_commit, recorded = case(name, written)
        check(f"{name.replace('-', ' ')}: the after-merge test run selects since the head commit, "
              f"as before, prints why, and records the merge commit once it leaves no test "
              f"failing",
              exit_code == 0 and len(calls) == 1
              and calls[0]["argv"][:2] == ["--only-suites-whose-recorded-inputs-changed-since",
                                           HEAD]
              and "no main commit whose after-merge test run left no test failing is used: " in output
              and why in output
              and f"changed since the head commit {HEAD[:12]}, which selects more suites" in output
              and recorded == merge_commit,
              f"exit {exit_code}\n{output}\n{calls}\n{recorded}")

    exit_code, output, calls, parent, merge_commit, recorded = case(
        "no-test-failing-file-a-directory", None)
    path = newest_main_commit_left_no_test_failing_file(scratch / "no-test-failing-file-a-directory")
    check("a record that cannot be read or written: the after-merge test run selects since the "
          "head commit, says why, and exits 3 with a STOP saying the merge commit was not recorded",
          exit_code == 3 and calls[0]["argv"][:2] == [
              "--only-suites-whose-recorded-inputs-changed-since", HEAD]
          and f"{path} could not be read: " in output
          and f"STOP: merged, and main's test run left no test failing, but {merge_commit[:12]} "
              f"was not recorded in {path}: " in output
          and f"Otherwise, {TELL_THE_USER_WITH_THE_ERROR}" in output,
          f"exit {exit_code}\n{output}\n{calls}")


def author_seat_made(directory):
    task_list = directory / "home" / ".claude" / "tasks" / "nedsnodes-author-seat-tasks"
    task_list.mkdir(parents=True)
    (directory / "home" / "agents" / "author-seat").mkdir(parents=True)
    return task_list


def failed_suites_kept_in_view_cases(scratch):
    broken_on_origin = {"scripts/broken-test.py": "raise SystemExit(1)\n"}
    saved_author = program.merged_branch_last_commit_author_name_read
    program.merged_branch_last_commit_author_name_read = lambda *_: "author-seat"
    try:
        exit_code, output, _, _, _ = run_case(
            scratch, "failed-suite-new", [(GATE_PASSED, 0)], default_routes([]),
            runner_answer=(RUNNER_FAILED, 1), before_the_program_runs=author_seat_made)
        directory = scratch / "failed-suite-new"
        task_files = list((directory / "home" / ".claude" / "tasks"
                           / "nedsnodes-author-seat-tasks").glob("*.json"))
        task = json.loads(task_files[0].read_text()) if len(task_files) == 1 else {}
        record = failed_suites_record_of(directory)
        check("a newly failed suite joins the record and gets one repair task on its author's list",
              exit_code == 3 and list(record) == ["scripts/broken-test.py"]
              and record["scripts/broken-test.py"]["failed_tests"]["scripts/broken-test.py"]["log"]
              == "/logs/broken-test.py.log"
              and record["scripts/broken-test.py"]["failed_tests"]["scripts/broken-test.py"][
                  "repair_task_agent_seat"] == "author-seat"
              and "scripts/broken-test.py" in task.get("description", "")
              and f"Repair task #{task.get('id')} is on author-seat's task list" in output,
              f"exit {exit_code}\n{output}\n{record}\n{task}")

        def recorded_with_author(directory):
            task_list = author_seat_made(directory)
            failed_suites_record_written(directory)
            (task_list / "3.json").write_text('{"status": "pending"}')

        exit_code, output, _, _, _ = run_case(
            scratch, "failed-suite-known", [(GATE_PASSED, 0)], default_routes([]),
            runner_answer=(RUNNER_FAILED, 1), before_the_program_runs=recorded_with_author)
        directory = scratch / "failed-suite-known"
        check("a merge that fails only a recorded suite exits 0, with a notice and no second task, "
              "and is not recorded as a commit whose after-merge test run left no test failing",
              exit_code == 0 and "STOP" not in output
              and not newest_main_commit_left_no_test_failing_file(directory).exists()
              and "failed only suites already on the failed suites record" in output
              and failed_suites_record_of(directory)["scripts/broken-test.py"]["failed_tests"][
                  "scripts/broken-test.py"]["repair_task_id"] == 3
              and [path.name for path in tasks_of_author(directory)] == ["3.json"],
              f"exit {exit_code}\n{output}")

        def recorded_and_rerun(rerun_output, rerun_exit):
            def prepare(directory):
                task_list = author_seat_made(directory)
                (task_list / "3.json").write_text('{"status": "pending"}')
                failed_suites_record_written(directory)
                (directory / "runner-rerun.out").write_text(rerun_output)
                (directory / "runner-rerun.exit").write_text(str(rerun_exit))
            return prepare

        exit_code, output, _, _, _ = run_case(
            scratch, "failed-suite-rerun-passes", [(GATE_PASSED, 0)], default_routes([]),
            origin_files=broken_on_origin, before_the_program_runs=recorded_and_rerun(
                "PASS scripts/broken-test.py (1s)\nSUMMARY: 1 passed, 0 failed, 1 total\n", 0))
        calls = runner_calls(scratch, "failed-suite-rerun-passes")
        check("a recorded suite the selective run left out is run by name, and leaves the record "
              "when it passes",
              exit_code == 0 and failed_suites_record_of(scratch / "failed-suite-rerun-passes") == {}
              and len(calls) == 2 and "--only-suites-named" in calls[1]["argv"]
              and "scripts/broken-test.py" in calls[1]["argv"]
              and "--leave-recorded-inputs-and-failure-history-unchanged" in calls[1]["argv"]
              and "scripts/broken-test.py left the failed suites record: it passed" in output
              and newest_main_commit_left_no_test_failing_of(
                  scratch / "failed-suite-rerun-passes")
              == origin_commit(scratch, "failed-suite-rerun-passes"),
              f"exit {exit_code}\n{output}\n{calls}")

        exit_code, output, _, _, _ = run_case(
            scratch, "failed-suite-rerun-fails", [(GATE_PASSED, 0)], default_routes([]),
            origin_files=broken_on_origin, before_the_program_runs=recorded_and_rerun(
                "FAIL scripts/broken-test.py exit 1 (1s)\nSUMMARY: 0 passed, 1 failed, 1 total\n", 1))
        check("a recorded suite that fails its rerun stays on the record, and the merge exits 0, "
              "though the selective test run passed, without recording the merge commit as one "
              "whose after-merge test run left no test failing",
              exit_code == 0 and "scripts/broken-test.py" in failed_suites_record_of(
                  scratch / "failed-suite-rerun-fails")
              and not newest_main_commit_left_no_test_failing_file(
                  scratch / "failed-suite-rerun-fails").exists()
              and "FAILED TEST SUITES ON MAIN" in output, f"exit {exit_code}\n{output}")

        exit_code, output, _, _, _ = run_case(
            scratch, "failed-suite-rerun-could-not-run", [(GATE_PASSED, 0)], default_routes([]),
            origin_files=broken_on_origin, before_the_program_runs=recorded_and_rerun(
                "PASS scripts/broken-test.py (1s)\nrunner could not finish\n", 2))
        check("a rerun with no verdict exits 3, and keeps the suite even if a PASS line was printed",
              exit_code == 3 and "could not all be run again" in output
              and "scripts/broken-test.py" in failed_suites_record_of(
                  scratch / "failed-suite-rerun-could-not-run"),
              f"exit {exit_code}\n{output}")

        exit_code, output, _, _, _ = run_case(
            scratch, "failed-suite-deleted", [(GATE_PASSED, 0)], default_routes([]),
            before_the_program_runs=failed_suites_record_written)
        calls = runner_calls(scratch, "failed-suite-deleted")
        check("a recorded suite git no longer lists leaves the record without a rerun",
              exit_code == 0 and failed_suites_record_of(scratch / "failed-suite-deleted") == {}
              and len(calls) == 1
              and "left the failed suites record: git no longer lists it" in output,
              f"exit {exit_code}\n{output}\n{calls}")

        exit_code, output, _, _, _ = run_case(
            scratch, "failed-suite-ls-files-fails", [(GATE_PASSED, 0)], default_routes([]),
            git_fails_after_merge_on=(" ls-files -- scripts/broken-test.py", "exit 1"),
            before_the_program_runs=failed_suites_record_written)
        check("a git failure listing the recorded suites exits 3 and keeps them",
              exit_code == 3 and "the recorded failed suites were not run again" in output
              and "fake git failed" in output
              and "scripts/broken-test.py" in failed_suites_record_of(
                  scratch / "failed-suite-ls-files-fails"), f"exit {exit_code}\n{output}")

        def unreadable(directory):
            record = failed_suites_record_file(directory)
            record.parent.mkdir(parents=True)
            record.write_text("not json")

        exit_code, output, _, _, _ = run_case(
            scratch, "failed-suite-record-unreadable", [(GATE_PASSED, 0)], default_routes([]),
            before_the_program_runs=unreadable)
        check("an unreadable record exits 3, naming the file, and leaves it as it was",
              exit_code == 3 and "the failed suites record was not updated: could not read" in output
              and failed_suites_record_file(
                  scratch / "failed-suite-record-unreadable").read_text() == "not json",
              f"exit {exit_code}\n{output}")

        def lock_blocked(directory):
            record = failed_suites_record_file(directory)
            record.parent.mkdir(parents=True)
            record.with_name(record.name + ".lock").mkdir()

        exit_code, output, _, _, _ = run_case(
            scratch, "failed-suite-record-not-written", [(GATE_PASSED, 0)], default_routes([]),
            runner_answer=(RUNNER_FAILED, 1), before_the_program_runs=lock_blocked)
        check("a record that cannot be written exits 3, and says so",
              exit_code == 3 and "the failed suites record was not updated: could not write" in output,
              f"exit {exit_code}\n{output}")

        def null_commit_recorded(directory):
            failed_suites_record_written(directory)
            record = failed_suites_record_of(directory)
            record["scripts/broken-test.py"]["failed_tests"]["scripts/broken-test.py"]["commit"] = None
            failed_suites_record_file(directory).write_text(json.dumps(record))

        exit_code, output, _, _, _ = run_case(
            scratch, "failed-suite-record-null-commit", [(GATE_PASSED, 0)], default_routes([]),
            before_the_program_runs=null_commit_recorded)
        check("a record whose commit is null is unusable: the merge exits 3 and says so",
              exit_code == 3 and "the failed suites record was not updated: could not read" in output
              and "Traceback" not in output, f"exit {exit_code}\n{output}")

        for name, problem_line in (
                ("records-not-written",
                 f"{program.common.run_all_test_suites.RUN_CASE_TIMES_SUITE_RESOURCES_JUNIT_XML_OR_FAILURE_HISTORY_NOT_WRITTEN_LINE_PREFIX}: disk full\n"),
                ("readings-stopped",
                 f"{program.common.run_all_test_suites.MACHINE_CPU_AND_MEMORY_READINGS_STOPPED_BEFORE_RUN_END_LINE_PREFIX} before "
                 f"the run ended: boom\n"),
                ("not-run", "NOT RUN scripts/unjudged-test.py no slot — log /logs/unjudged.log\n")):
            exit_code, output, _, _, _ = run_case(
                scratch, f"failed-suite-known-and-{name}", [(GATE_PASSED, 0)], default_routes([]),
                runner_answer=(problem_line + RUNNER_FAILED, 1),
                before_the_program_runs=recorded_with_author)
            check(f"a recorded failure with another problem in the run ({name}) is a STOP",
                  exit_code == 3 and "STOP: merged, but the test run of main" in output
                  and "failed only suites already" not in output
                  and "Tell the pull request's author, and the user" in output,
                  f"exit {exit_code}\n{output}")

        exit_code, output, _, _, _ = run_case(
            scratch, "failed-suite-new-and-not-run", [(GATE_PASSED, 0)], default_routes([]),
            runner_answer=("NOT RUN scripts/unjudged-test.py no slot — log /logs/unjudged.log\n"
                           + RUNNER_FAILED, 1), before_the_program_runs=author_seat_made)
        check("a new failure with no verdict on the rest of the run (not-run) still tells the "
              "author and the user",
              exit_code == 3 and "nothing needs sending" not in output
              and "covers only the newly failed tests" in output
              and "Tell the pull request's author, and the user" in output,
              f"exit {exit_code}\n{output}")

        exit_code, output, _, _, _ = run_case(
            scratch, "failed-suite-new-and-cut-short", [(GATE_PASSED, 0)], default_routes([]),
            runner_answer=("FAIL scripts/broken-test.py exit 1 (2s)\n"
                           f"{program.common.run_all_test_suites.NOT_RUN_TO_THE_END_LINE_PREFIX}"
                           " — stopped by SIGTERM.\n", 1), before_the_program_runs=author_seat_made)
        check("a run cut short before its junit.xml is a STOP that sends its failed suites to the "
              "author and the user, and never says nothing needs sending",
              exit_code == 3 and "nothing needs sending" not in output
              and "failed tests could not be named" in output
              and "Tell the pull request's author, and the user" in output,
              f"exit {exit_code}\n{output}")

        exit_code, output, _, _, _ = run_case(
            scratch, "failed-suite-new-and-not-run-no-task", [(GATE_PASSED, 0)], default_routes([]),
            runner_answer=("NOT RUN scripts/unjudged-test.py no slot — log /logs/unjudged.log\n"
                           + RUNNER_FAILED, 1))
        check("a new failure with a suite not run and no task tells the author and asks the user",
              exit_code == 3 and "Tell the pull request's author, and the user" in output
              and "Ask the user:" in output, f"exit {exit_code}\n{output}")

        exit_code, output, _, _, _ = run_case(
            scratch, "failed-suite-rerun-fail-and-not-run", [(GATE_PASSED, 0)], default_routes([]),
            origin_files=broken_on_origin, before_the_program_runs=recorded_and_rerun(
                "FAIL scripts/broken-test.py exit 1 (1s)\n"
                "NOT RUN scripts/other-test.py no slot (0s)\n"
                "SUMMARY: 0 passed, 1 failed, 1 not run, 2 total\n", 1))
        check("a rerun that fails one suite and leaves another not run exits 3, not a known failure",
              exit_code == 3 and "could not all be run again" in output
              and "scripts/broken-test.py" in failed_suites_record_of(
                  scratch / "failed-suite-rerun-fail-and-not-run"),
              f"exit {exit_code}\n{output}")

        exit_code, output, _, _, _ = run_case(
            scratch, "test-new-in-recorded-suite", [(GATE_PASSED, 0)], default_routes([]),
            runner_answer=(RUNNER_FAILED, 1), before_the_program_runs=recorded_tests_with_task(
                ["case a"], ["case a", "case b"], []))
        directory = scratch / "test-new-in-recorded-suite"
        tests = failed_suites_record_of(directory)["scripts/broken-test.py"]["failed_tests"]
        new_tasks = [path for path in tasks_of_author(directory) if path.name != "3.json"]
        check("a new test failing in a recorded suite is a STOP with one repair task for it",
              exit_code == 3 and sorted(tests) == ["case a", "case b"] and len(new_tasks) == 1
              and tests["case b"]["repair_task_id"] != 3 and tests["case a"]["repair_task_id"] == 3
              and "case b" in json.loads(new_tasks[0].read_text())["description"]
              and "case a" not in json.loads(new_tasks[0].read_text())["description"]
              and "failed only suites already" not in output, f"exit {exit_code}\n{output}\n{tests}")

        exit_code, output, _, _, _ = run_case(
            scratch, "test-passes-another-stays", [(GATE_PASSED, 0)], default_routes([]),
            runner_answer=(RUNNER_FAILED, 1), before_the_program_runs=recorded_tests_with_task(
                ["case a", "case b"], ["case b"], ["case a"]))
        tests = failed_suites_record_of(scratch / "test-passes-another-stays")[
            "scripts/broken-test.py"]["failed_tests"]
        check("a recorded test that passes leaves the record while another stays, and the merge "
              "exits 0",
              exit_code == 0 and list(tests) == ["case b"]
              and "scripts/broken-test.py: case a left the failed suites record: it passed" in output,
              f"exit {exit_code}\n{output}\n{tests}")

        exit_code, output, _, _, _ = run_case(
            scratch, "test-not-reached-stays", [(GATE_PASSED, 0)], default_routes([]),
            runner_answer=(RUNNER_FAILED, 1), before_the_program_runs=recorded_tests_with_task(
                ["case a", "case b"], ["case b"], []))
        tests = failed_suites_record_of(scratch / "test-not-reached-stays")[
            "scripts/broken-test.py"]["failed_tests"]
        check("a recorded test the failing suite did not reach stays on the record",
              exit_code == 0 and sorted(tests) == ["case a", "case b"],
              f"exit {exit_code}\n{output}\n{tests}")

        for name, task_text in (("completed", '{"status": "completed"}'), ("unreadable", "not json")):
            exit_code, output, _, _, _ = run_case(
                scratch, f"task-{name}-test-still-fails", [(GATE_PASSED, 0)], default_routes([]),
                runner_answer=(RUNNER_FAILED, 1), before_the_program_runs=recorded_tests_with_task(
                    ["case a"], ["case a"], [], task_text=task_text))
            directory = scratch / f"task-{name}-test-still-fails"
            tests = failed_suites_record_of(directory)["scripts/broken-test.py"]["failed_tests"]
            new_tasks = [path for path in tasks_of_author(directory) if path.name != "3.json"]
            check(f"a {name} repair task with its test still failing gets one new task, noted on "
                  "the record",
                  exit_code == 0 and len(new_tasks) == 1
                  and str(tests["case a"]["repair_task_id"]) == new_tasks[0].stem
                  and "because its earlier repair task is closed" in output,
                  f"exit {exit_code}\n{output}\n{tests}")

        def completed_task_and_no_checkout(directory):
            recorded_tests_with_task(["case a"], ["case a"], [],
                                     task_text='{"status": "completed"}')(directory)
            shutil.rmtree(directory / "home" / "agents" / "author-seat")

        exit_code, output, _, _, _ = run_case(
            scratch, "task-completed-none-can-open", [(GATE_PASSED, 0)], default_routes([]),
            runner_answer=(RUNNER_FAILED, 1), before_the_program_runs=completed_task_and_no_checkout)
        tests = failed_suites_record_of(scratch / "task-completed-none-can-open")[
            "scripts/broken-test.py"]["failed_tests"]
        check("a completed repair task that cannot be replaced is a STOP that asks the user",
              exit_code == 3 and "no new one could be opened" in output and "Ask the user:" in output
              and tests["case a"]["repair_task_id"] == 3, f"exit {exit_code}\n{output}\n{tests}")

        def recorded_and_rerun_by_test(directory):
            recorded_tests_with_task(["case a"], ["case b"], ["case a"], rerun=True)(directory)

        exit_code, output, _, _, _ = run_case(
            scratch, "rerun-compares-by-test", [(GATE_PASSED, 0)], default_routes([]),
            origin_files=broken_on_origin, before_the_program_runs=recorded_and_rerun_by_test)
        tests = failed_suites_record_of(scratch / "rerun-compares-by-test")[
            "scripts/broken-test.py"]["failed_tests"]
        calls = runner_calls(scratch, "rerun-compares-by-test")
        check("a rerun runs the whole recorded suite and compares by test name, and a new failure "
              "in it is a STOP",
              exit_code == 3 and list(tests) == ["case b"] and len(calls) == 2
              and "--only-suites-named" in calls[1]["argv"]
              and "the rerun of the recorded failed suites failed tests not on the record" in output,
              f"exit {exit_code}\n{output}\n{tests}")

        exit_code, output, _, _, _ = run_case(
            scratch, "names-sharing-a-start", [(GATE_PASSED, 0)], default_routes([]),
            runner_answer=(RUNNER_FAILED, 1), before_the_program_runs=recorded_tests_with_task(
                ["--failures-only: prints X"],
                ["--failures-only: prints X", "--failures-only: prints Y"], []))
        tests = failed_suites_record_of(scratch / "names-sharing-a-start")[
            "scripts/broken-test.py"]["failed_tests"]
        check("two failing tests whose names share the text before their first ': ' are two "
              "tests, so the second is a new failure and a STOP",
              exit_code == 3 and sorted(tests) == ["--failures-only: prints X",
                                                   "--failures-only: prints Y"]
              and "failed only suites already" not in output, f"exit {exit_code}\n{output}\n{tests}")

        exit_code, output, _, _, _ = run_case(
            scratch, "known-failure-suite-cut-short", [(GATE_PASSED, 0)], default_routes([]),
            runner_answer=(RUNNER_FAILED, 1), before_the_program_runs=recorded_tests_with_task(
                ["case a"], ["case a"], [], ran_to_the_end=False))
        check("a known failure in a suite that did not run to the end is a STOP, not a known "
              "failure",
              exit_code == 3 and "STOP: merged, but scripts/broken-test.py did not run to the end"
              in output and "failed only suites already" not in output
              and "nothing needs sending" not in output, f"exit {exit_code}\n{output}")

        def partial_rerun_with_a_new_failure(directory):
            recorded_tests_with_task(["case a"], ["case a", "case b"], [], rerun=True)(directory)
            (directory / "runner-rerun.out").write_text(
                "FAIL scripts/broken-test.py exit 1 (1s)\n"
                "NOT RUN scripts/other-test.py no slot (0s)\n"
                "SUMMARY: 0 passed, 1 failed, 1 not run, 2 total\n")

        exit_code, output, _, _, _ = run_case(
            scratch, "partial-rerun-keeps-finished-verdicts", [(GATE_PASSED, 0)],
            default_routes([]), origin_files=broken_on_origin,
            before_the_program_runs=partial_rerun_with_a_new_failure)
        tests = failed_suites_record_of(scratch / "partial-rerun-keeps-finished-verdicts")[
            "scripts/broken-test.py"]["failed_tests"]
        check("a partial rerun keeps the verdicts of the suites that finished: a new failing test "
              "in one is recorded and named, with a STOP that never says nothing needs sending",
              exit_code == 3 and sorted(tests) == ["case a", "case b"]
              and "could not all be run again" in output and "case b" in output
              and "nothing needs sending" not in output
              and "covers only the newly failed tests" in output,
              f"exit {exit_code}\n{output}\n{tests}")

        def new_failure_and_rerun_not_run(directory):
            recorded_tests_with_task(["case a"], [], [], rerun=True)(directory)
            (directory / "runner-rerun.out").write_text("NOT RUN scripts/broken-test.py no slot\n")
            (directory / "runner-rerun.exit").write_text("2")

        exit_code, output, _, _, _ = run_case(
            scratch, "new-failure-and-rerun-not-run", [(GATE_PASSED, 0)], default_routes([]),
            runner_answer=(RUNNER_FAILED.replace("broken-test.py", "new-broken-test.py"), 1),
            origin_files=broken_on_origin, before_the_program_runs=new_failure_and_rerun_not_run)
        check("a new failure with a repair task, when the rerun exits 2 with NOT RUN, never says "
              "nothing needs sending",
              exit_code == 3 and "could not all be run again" in output
              and "nothing needs sending" not in output
              and "covers only the newly failed tests" in output, f"exit {exit_code}\n{output}")

        def new_failure_and_closed_task_not_replaced(directory):
            completed_task_and_no_checkout(directory)
            (directory / "runner.junit").write_text(junit_of_broken_suite(["case a", "case b"], []))

        saved_opened = program.repair_task_opened

        def opened_only_for_the_new_test(arguments, merge_commit, seat, failed_tests):
            if any("case b" in tests for tests in failed_tests.values()):
                return "author-seat", 7, None
            return None, None, "the author-seat has no checkout"

        program.repair_task_opened = opened_only_for_the_new_test
        try:
            exit_code, output, _, _, _ = run_case(
                scratch, "new-failure-and-closed-task-not-replaced", [(GATE_PASSED, 0)],
                default_routes([]), runner_answer=(RUNNER_FAILED, 1),
                before_the_program_runs=new_failure_and_closed_task_not_replaced)
        finally:
            program.repair_task_opened = saved_opened
        check("a new failure with a repair task, when a closed task cannot be replaced, never "
              "says nothing needs sending",
              exit_code == 3 and "no new one could be opened" in output
              and "nothing needs sending" not in output
              and "covers only the newly failed tests" in output, f"exit {exit_code}\n{output}")

        def no_junit(directory):
            recorded_with_author(directory)
            (directory / "runner-writes-no-junit").write_text("")

        exit_code, output, _, _, _ = run_case(
            scratch, "junit-missing", [(GATE_PASSED, 0)], default_routes([]),
            runner_answer=(RUNNER_FAILED, 1), before_the_program_runs=no_junit)
        check("a run whose junit.xml is missing is a STOP, since its failed tests cannot be named",
              exit_code == 3 and "failed tests could not be named" in output
              and "does not exist" in output, f"exit {exit_code}\n{output}")

        def corrupt_junit(directory):
            recorded_with_author(directory)
            (directory / "runner.junit").write_text("not xml")

        exit_code, output, _, _, _ = run_case(
            scratch, "junit-corrupt", [(GATE_PASSED, 0)], default_routes([]),
            runner_answer=(RUNNER_FAILED, 1), before_the_program_runs=corrupt_junit)
        check("a run whose junit.xml cannot be parsed is a STOP",
              exit_code == 3 and "failed tests could not be named" in output
              and "could not be read" in output, f"exit {exit_code}\n{output}")

        def corrupt_rerun_junit(directory):
            recorded_tests_with_task(["case a"], ["case a"], [], rerun=True)(directory)
            (directory / "runner-rerun.junit").write_text("not xml")

        exit_code, output, _, _, _ = run_case(
            scratch, "rerun-junit-corrupt", [(GATE_PASSED, 0)], default_routes([]),
            origin_files=broken_on_origin, before_the_program_runs=corrupt_rerun_junit)
        tests = failed_suites_record_of(scratch / "rerun-junit-corrupt")[
            "scripts/broken-test.py"]["failed_tests"]
        check("a rerun whose junit.xml cannot be parsed is a STOP and keeps the recorded test",
              exit_code == 3 and "the rerun's failed tests could not be named" in output
              and list(tests) == ["case a"], f"exit {exit_code}\n{output}\n{tests}")

        saved_write = program.task_write.agent_seat_task_list_new_pending_task_write

        def task_write_fails(*_):
            raise OSError("disk full")

        program.task_write.agent_seat_task_list_new_pending_task_write = task_write_fails
        try:
            exit_code, output, _, _, _ = run_case(
                scratch, "failed-suite-task-not-written", [(GATE_PASSED, 0)], default_routes([]),
                runner_answer=(RUNNER_FAILED, 1), before_the_program_runs=author_seat_made)
        finally:
            program.task_write.agent_seat_task_list_new_pending_task_write = saved_write
        record = failed_suites_record_of(scratch / "failed-suite-task-not-written")
        check("a repair task that cannot be written exits 3, tells the user, and keeps the suite",
              exit_code == 3 and "the repair task could not be written" in output
              and "disk full" in output and "Ask the user:" in output
              and record["scripts/broken-test.py"]["failed_tests"]["scripts/broken-test.py"][
                  "repair_task_id"] is None,
              f"exit {exit_code}\n{output}\n{record}")
    finally:
        program.merged_branch_last_commit_author_name_read = saved_author

    author_repository = scratch / "author-repository"
    author_repository.mkdir()
    git("init", "-q", "-b", "main", cwd=author_repository)
    git("-c", "user.name=main-author", "-c", "user.email=m@example.invalid", "commit", "-q",
        "--allow-empty", "-m", "base", cwd=author_repository)
    git("checkout", "-q", "-b", "topic", cwd=author_repository)
    git("commit", "-q", "--author=branch-author <b@example.invalid>",
        "--allow-empty", "-m", "work", cwd=author_repository)
    git("checkout", "-q", "main", cwd=author_repository)
    git("-c", "user.name=main-author", "-c", "user.email=m@example.invalid", "commit", "-q",
        "--allow-empty", "-m", "moved", cwd=author_repository)
    git("-c", "user.name=github", "-c", "user.email=g@example.invalid", "merge", "-q",
        "--no-ff", "-m", "Merge", "topic", cwd=author_repository)
    check("the author is the merged branch's last commit's, not the merge commit's",
          program.merged_branch_last_commit_author_name_read(author_repository, "HEAD", GIT_ENVIRONMENT) == "branch-author")
    check("a commit with no second parent has no branch author",
          program.merged_branch_last_commit_author_name_read(author_repository, "HEAD~1", GIT_ENVIRONMENT) is None)

    older, newer = (subprocess.run(["git", "-C", str(author_repository), "rev-parse", name],
                                   capture_output=True, text=True, env=GIT_ENVIRONMENT,
                                   check=True).stdout.strip() for name in ("HEAD~1", "HEAD"))
    runs = iter(range(1000))

    def kept_in_view_directly(last_failed_commit, tested_commit, junit,
                              test="scripts/x-test.py"):
        run = next(runs)
        home = scratch / f"direct-home-{run}"
        log_dir = scratch / f"direct-logs-{run}"
        log_dir.mkdir()
        (log_dir / "junit.xml").write_text(junit)
        saved_home = os.environ.get("HOME")
        os.environ["HOME"] = str(home)
        try:
            record = (home / ".local" / "state" / "nedsnodes"
                      / "failed-after-merge-test-suites-on-main.json")
            record.parent.mkdir(parents=True)
            record.write_text(json.dumps({"scripts/x-test.py": {"failed_tests": {test: {
                "commit": older if last_failed_commit != "0" * 40 else last_failed_commit,
                "last_failed_commit": last_failed_commit, "pull_request": "9", "log": None,
                "failed_at": "2026-11-20T17:18:00Z", "repair_task_agent_seat": None,
                "repair_task_id": None}}}}))
            printed = io.StringIO()
            with contextlib.redirect_stdout(printed):
                kept = program.failed_suites_kept_in_view(
                    argparse.Namespace(pull_request="10"), tested_commit, author_repository,
                    log_dir, GIT_ENVIRONMENT,
                    ["FAIL scripts/x-test.py exit 1 — log /logs/x.log"])
            return kept["complete"], json.loads(record.read_text()), printed.getvalue()
        finally:
            if saved_home is None:
                del os.environ["HOME"]
            else:
                os.environ["HOME"] = saved_home

    def x_suite(cases, ran_to_the_end=True):
        return (f'<testsuites><testsuite name="scripts/x-test.py" judged="true" '
                f'ran_to_the_end="{str(ran_to_the_end).lower()}">{cases}</testsuite></testsuites>')

    passed = x_suite('<testcase name="scripts/x-test.py"/>')
    worked, left, output = kept_in_view_directly(newer, older, passed)
    check("a pass at an older commit keeps a test a newer run saw fail",
          worked and "scripts/x-test.py" in left and "left the failed suites record" not in output,
          f"{worked} {left}\n{output}")
    worked, left, output = kept_in_view_directly(older, newer, passed)
    check("a pass at a descendant of the commit the test last failed at removes it",
          worked and left == {} and "left the failed suites record: it passed" in output,
          f"{worked} {left}\n{output}")
    worked, left, output = kept_in_view_directly("0" * 40, newer, passed)
    check("a commit git cannot judge keeps the test and is a STOP",
          not worked and "scripts/x-test.py" in left and "STOP: merged, but scripts/x-test.py stays"
          in output, f"{worked} {left}\n{output}")

    still_failing = x_suite('<testcase name="scripts/x-test.py"><failure message="x"/></testcase>')
    worked, left, _ = kept_in_view_directly(older, newer, still_failing)
    refreshed = left["scripts/x-test.py"]["failed_tests"]["scripts/x-test.py"]
    worked_after, left_after, output = kept_in_view_directly(
        refreshed["last_failed_commit"], older, passed)
    check("runs finishing out of order, A, C, B: a known failure at C records C, so a later "
          "pass at the older B keeps the test",
          worked and refreshed["last_failed_commit"] == newer and refreshed["commit"] == older
          and worked_after and "scripts/x-test.py" in left_after,
          f"{left}\n{left_after}\n{output}")

    other_case = x_suite('<testcase name="case b"/>')
    worked, left, output = kept_in_view_directly(older, newer, other_case, test="case a")
    check("a recorded test its suite, run to the end at a later commit, no longer reports leaves "
          "the record, and its name is printed",
          worked and left == {}
          and "scripts/x-test.py: case a left the failed suites record: its suite ran to the end "
              "and reported nothing for it" in output, f"{worked} {left}\n{output}")
    worked, left, output = kept_in_view_directly(newer, newer, other_case, test="case a")
    check("a recorded test not reported at the commit where it last failed stays",
          worked and "case a" in left["scripts/x-test.py"]["failed_tests"], f"{left}\n{output}")
    worked, left, output = kept_in_view_directly(
        older, newer, x_suite('<testcase name="case b"/>', ran_to_the_end=False), test="case a")
    check("a suite that did not run to the end clears no recorded test, and is a STOP",
          not worked and "case a" in left["scripts/x-test.py"]["failed_tests"]
          and "STOP: merged, but scripts/x-test.py did not run to the end" in output,
          f"{left}\n{output}")
    worked, left, output = kept_in_view_directly(
        older, newer, x_suite('<testcase name="case b"/><testcase name="case a: no Mac">'
                              '<skipped/></testcase>'), test="case a")
    check("a recorded test that is skipped stays on the record",
          worked and "case a" in left["scripts/x-test.py"]["failed_tests"], f"{left}\n{output}")
    worked, left, output = kept_in_view_directly(
        older, newer, x_suite('<testcase name="case a"/>'), test="scripts/x-test.py")
    check("a test named for its suite, recorded when the suite failed with no case line, leaves "
          "once the suite runs to the end with case lines",
          worked and left == {} and "reported nothing for it" in output, f"{left}\n{output}")
    worked, left, output = kept_in_view_directly(
        older, newer, x_suite('<testcase name="case b"><failure message="x"/></testcase>'),
        test="scripts/x-test.py exit")
    check("a recorded failure after the last case line leaves once the suite runs to the end "
          "without one",
          "scripts/x-test.py exit" not in left["scripts/x-test.py"]["failed_tests"]
          and "case b" in left["scripts/x-test.py"]["failed_tests"],
          f"{left}\n{output}")
    worked, left, output = kept_in_view_directly(
        "0" * 40, newer, x_suite('<testcase name="scripts/x-test.py"><failure message="x"/>'
                                 '</testcase><testcase name="case n"><failure message="x"/>'
                                 '</testcase>'))
    printed = io.StringIO()
    with contextlib.redirect_stdout(printed):
        stop = program.after_merge_test_run_closing_message_printed_returning_whether_stop(
            argparse.Namespace(pull_request="10"), newer, 1, ["SUMMARY: 0 passed, 1 failed"], True,
            {"complete": worked, "new_tests": {"scripts/x-test.py": {"case n": None}},
             "seat": "author-seat", "task_id": 7, "why_none": None}, worked, "by hand")
    check("a new failure with a repair task, when git cannot judge a recorded commit, never says "
          "nothing needs sending",
          not worked and stop and "STOP: merged, but scripts/x-test.py stays" in output
          and "nothing needs sending" not in printed.getvalue()
          and "covers only the newly failed tests" in printed.getvalue(),
          f"{output}\n{printed.getvalue()}")
    junit_file = scratch / "not-judged-junit.xml"
    junit_file.write_text('<testsuites><testsuite name="scripts/x-test.py" judged="false" '
                          'ran_to_the_end="false"><testcase name="scripts/x-test.py">'
                          '<failure message="x"/></testcase></testsuite></testsuites>')
    verdicts, error = program.run_verdicts_by_suite([], junit_file)
    check("a suite NOT RUN or stopped by the run gives no verdict, not even a failure",
          verdicts == {} and error is None, f"{verdicts} {error}")


def main():
    # Every other case runs a fake go-ahead program in its place.
    check("the go-ahead program the merge script runs after a merge is a file",
          program.SURVIVING_MUTANT_TEST_PRS_GO_AHEAD_PROGRAM.is_file(),
          str(program.SURVIVING_MUTANT_TEST_PRS_GO_AHEAD_PROGRAM))
    # Resolved, because macOS's mkdtemp path is a symlink and the program resolves its paths.
    scratch = Path(tempfile.mkdtemp(prefix="merge-lane-merge-test-")).resolve()
    try:
        exit_code, output, gh_calls, gate_calls, waits = run_case(
            scratch, "stacked", [(GATE_PASSED, 0)], default_routes(STACKED_AND_NOT),
            review_worktrees_state="both")
        calls = argvs(gh_calls)
        edit_20 = index_of(calls, ["pr", "edit", "20"])
        merge = index_of(calls, ["pr", "merge"])
        check("a pull request based on the merged branch is retargeted to main before the merge",
              edit_20 is not None and merge is not None and edit_20 < merge
              and calls[edit_20] == ["pr", "edit", "20", "--repo", "nedsnodes/nedsnodes",
                                     "--base", "main"], json.dumps(calls))
        check("a pull request based on main is left alone",
              index_of(calls, ["pr", "edit", "21"]) is None, json.dumps(calls))
        check("a pull request based on another branch is left alone",
              index_of(calls, ["pr", "edit", "22"]) is None, json.dumps(calls))
        check("the merge runs exactly the command the gate printed",
              merge is not None and calls[merge] == EXPECTED_MERGE, json.dumps(calls))
        check("the gate that runs is --review-tools-worktree-at-main's, not the one beside the program",
              gate_calls == [f"{PULL_REQUEST} {HEAD} {SINCE}"], repr(gate_calls))
        check("every gh call carries the merge account's token, read from the gate's own file",
              gh_calls and all(call["gh_token"] == TOKEN for call in gh_calls),
              json.dumps(gh_calls))
        check("the retarget is printed with how to undo it",
              f"retargeted pull request #20 from {BRANCH} to main" in output
              and f"--base {BRANCH}" in output, output)
        check("a merged pull request exits 0 and prints its state after the merge",
              exit_code == 0 and '"state":"MERGED"' in output, f"exit {exit_code}\n{output}")
        review_worktrees = scratch / "stacked" / "review-worktrees"
        left = registered_worktrees(scratch / "stacked" / "review-tools")
        check("a merged pull request's two review worktrees are removed, an untracked file "
              "in one included, and each removal is printed",
              not (review_worktrees / "pr10-head").exists()
              and not (review_worktrees / "pr10-merged").exists()
              and not any("review-worktrees" in path for path in left)
              and f"removed the review worktree {review_worktrees / 'pr10-head'}" in output
              and f"removed the review worktree {review_worktrees / 'pr10-merged'}" in output,
              f"{left}\n{output}")

        go_ahead_calls = go_ahead_calls_of(scratch, "stacked")
        check("after a merge the go-ahead program runs once, with the merge account's token, "
              "and its output is printed after main's test run",
              go_ahead_calls == [{"argv": [], "gh_token": TOKEN}]
              and printed_in_order(output, RUNNER_PASSED_SUMMARY, GO_AHEAD_COUNT_ONLY[0])
              and "go-ahead.py exited" not in output,
              f"{go_ahead_calls}\n{output}")

        release = ("RELEASED reboot-test\n10 open pull requests ... reboot-test was sent this "
                   "message, and is recorded as released\n")
        exit_code, output, _, _, _ = run_case(
            scratch, "go-ahead-names-an-agent-seat", [(GATE_PASSED, 0)],
            default_routes(STACKED_AND_NOT), go_ahead_answer=(release, 0))
        check("a RELEASED the go-ahead program prints is printed whole, and the merge exits 0",
              exit_code == 0 and release in output, f"exit {exit_code}\n{output}")

        killed = (lambda directory: (directory / "bin" / "go-ahead.py").write_text(
            "import os\nos.kill(os.getpid(), 9)\n"))
        for name, answer, before, code in (
                ("go-ahead-could-not-tell", ("could not tell: gh failed\n", 2), None, 2),
                ("go-ahead-crashed", ("Traceback (most recent call last):\n", 1), None, 1),
                ("go-ahead-killed", ("", 0), killed, -9)):
            exit_code, output, _, _, _ = run_case(
                scratch, name, [(GATE_PASSED, 0)], default_routes(STACKED_AND_NOT),
                go_ahead_answer=answer, before_the_program_runs=before)
            check(f"a go-ahead program that exits {code} is reported with what to do, and the "
                  f"merge still exits 0",
                  exit_code == 0 and answer[0] in output
                  and f"go-ahead.py exited {code}, so whether an agent-seat holding mutant-test "
                      f"tasks may open its pull requests was not decided; the merge is done all "
                      f"the same.\nFollow the instructions it printed above; when it printed "
                      f"none, run it once: python3 scripts/go-ahead.py" in output,
                  f"exit {exit_code}\n{output}")

        exit_code, output, _, _, _ = run_case(
            scratch, "merged-only",[(GATE_PASSED, 0)], default_routes(STACKED_AND_NOT),
            review_worktrees_state="merged-only")
        review_worktrees = scratch / "merged-only" / "review-worktrees"
        check("a review worktree that is not there is skipped, and the other is still removed",
              exit_code == 0 and not (review_worktrees / "pr10-merged").exists(),
              f"exit {exit_code}\n{output}")

        exit_code, output, gh_calls, _, _ = run_case(
            scratch, "review-worktree-not-removable", [(GATE_PASSED, 0)],
            default_routes(STACKED_AND_NOT), review_worktrees_state="head-not-a-worktree")
        review_tools = scratch / "review-worktree-not-removable" / "review-tools"
        not_removable = scratch / "review-worktree-not-removable" / "review-worktrees" / "pr10-head"
        check("a review worktree that git cannot remove exits 3 after the merge is reported, "
              "naming the worktree, git's error as text and the command to remove it",
              exit_code == 3 and index_of(argvs(gh_calls), ["pr", "merge"]) is not None
              and '"state":"MERGED"' in output
              and f"STOP: merged, but the review worktree {not_removable} was not removed"
              in output and "exited 128: fatal: " in output and "is not a working tree" in output
              and f"git -C {review_tools} worktree remove --force {not_removable}\n"
                  f"Otherwise, {TELL_THE_USER_WITH_THE_GIT_ERROR}" in output,
              f"exit {exit_code}\n{output}")
        check("the other review worktree is still removed when one cannot be",
              not (not_removable.parent / "pr10-merged").exists(), output)

        exit_code, output, _, _, _ = run_case(
            scratch, "git-killed", [(GATE_PASSED, 0)], default_routes(STACKED_AND_NOT),
            review_worktrees_state="both", git_killed_on_worktree_remove="")
        check("a git worktree remove killed by a signal exits 3 after the merge",
              exit_code == 3 and "STOP: merged, but the review worktree" in output
              and "exited -9: git printed no error\n" in output, f"exit {exit_code}\n{output}")

        exit_code, output, gh_calls, _, _ = run_case(
            scratch, "none-stacked", [(GATE_PASSED, 0)],
            default_routes([{"number": 21, "baseRefName": "main"}]))
        calls = argvs(gh_calls)
        check("with no stacked pull request nothing is retargeted and the merge runs",
              index_of(calls, ["pr", "edit"]) is None
              and index_of(calls, ["pr", "merge"]) is not None and exit_code == 0,
              f"exit {exit_code}\n{json.dumps(calls)}")
        check("with no stacked pull request the output says so",
              f"no open pull request is based on {BRANCH}" in output, output)

        exit_code, output, gh_calls, gate_calls, waits = run_case(
            scratch, "unknown-then-passes",
            [(GATE_UNKNOWN, 1), (GATE_UNKNOWN, 1), (GATE_PASSED, 0)],
            default_routes(STACKED_AND_NOT))
        check("the gate runs again, 5 seconds apart, while it reports UNKNOWN",
              len(gate_calls) == 3 and waits == [5, 5], f"{gate_calls} {waits}")
        check("a gate that passes after UNKNOWN goes on to merge",
              exit_code == 0 and index_of(argvs(gh_calls), ["pr", "merge"]) is not None,
              f"exit {exit_code}\n{output}")

        exit_code, output, gh_calls, gate_calls, waits = run_case(
            scratch, "unknown-always", [(GATE_UNKNOWN, 1)], default_routes(STACKED_AND_NOT))
        check("the gate runs at most 8 times while it reports UNKNOWN",
              len(gate_calls) == 8 and len(waits) == 7, f"{len(gate_calls)} {waits}")
        check("a gate still UNKNOWN after 8 runs stops with its exit code, touching nothing",
              exit_code == 1 and gh_calls == [], f"exit {exit_code}\n{json.dumps(gh_calls)}")

        exit_code, output, gh_calls, gate_calls, waits = run_case(
            scratch, "refused", [(GATE_REFUSED, 1)], default_routes(STACKED_AND_NOT))
        check("a refusal other than UNKNOWN is not retried",
              len(gate_calls) == 1 and waits == [], f"{gate_calls} {waits}")
        check("a refused gate retargets nothing and merges nothing",
              exit_code == 1 and gh_calls == [] and GATE_REFUSED.strip() in output,
              f"exit {exit_code}\n{output}\n{json.dumps(gh_calls)}")
        check("without a merge the go-ahead program does not run",
              go_ahead_calls_of(scratch, "refused") == [], output)

        exit_code, output, gh_calls, _, _ = run_case(
            scratch, "could-not-run", [("GATE COULD NOT RUN: jq is not on PATH.\n", 2)],
            default_routes(STACKED_AND_NOT))
        check("a gate that could not run exits 2, touching nothing",
              exit_code == 2 and gh_calls == [], f"exit {exit_code}\n{output}")

        unexpected = GATE_PASSED.replace(" --match-head-commit " + HEAD, "")
        exit_code, output, gh_calls, _, _ = run_case(
            scratch, "unexpected-command", [(unexpected, 0)], default_routes(STACKED_AND_NOT))
        check("a merge command other than the expected one is refused, touching nothing",
              exit_code == 1 and gh_calls == [] and "STOP: not merged" in output
              and "Do not merge, by either command." in output,
              f"exit {exit_code}\n{output}\n{json.dumps(gh_calls)}")

        exit_code, output, gh_calls, _, _ = run_case(
            scratch, "retarget-fails", [(GATE_PASSED, 0)],
            default_routes(STACKED_AND_NOT, edit_exit=1))
        calls = argvs(gh_calls)
        check("a retarget that fails stops before the merge, exit 2",
              exit_code == 2 and index_of(calls, ["pr", "merge"]) is None,
              f"exit {exit_code}\n{json.dumps(calls)}")
        check("a failed retarget names the pull request and gh's error",
              "could not retarget pull request #20" in output and "edit refused" in output,
              output)

        routes = default_routes(STACKED_AND_NOT)
        routes["pr list"] = {"exit": 1, "stderr": "HTTP 502\n"}
        exit_code, output, gh_calls, _, _ = run_case(
            scratch, "list-fails", [(GATE_PASSED, 0)], routes)
        calls = argvs(gh_calls)
        check("an open pull request list that fails stops before the merge, exit 2",
              exit_code == 2 and index_of(calls, ["pr", "merge"]) is None
              and f"could not be found: HTTP 502\n{RERUN_ONCE_THEN}"
                  f"{TELL_THE_USER_WITH_THE_GH_ERROR}" in output,
              f"exit {exit_code}\n{output}")

        routes = default_routes(STACKED_AND_NOT, merge_exit=1)
        routes["view-state"] = {"stdout": '{"state":"OPEN","mc":null}\n'}
        exit_code, output, gh_calls, _, _ = run_case(
            scratch, "merge-fails", [(GATE_PASSED, 0)], routes, review_worktrees_state="both")
        check("a merge that fails, leaving the pull request open, exits 1",
              exit_code == 1 and "merge exit 1" in output
              and "STOP: not merged: pull request 10 is OPEN after the merge command ran; "
                  "the merge command exited 1" in output
              and runner_calls(scratch, "merge-fails") == [], f"exit {exit_code}\n{output}")
        review_worktrees = scratch / "merge-fails" / "review-worktrees"
        check("a merge that fails leaves the review worktrees in place",
              (review_worktrees / "pr10-head").is_dir()
              and (review_worktrees / "pr10-merged").is_dir(), output)

        routes = default_routes(STACKED_AND_NOT)
        routes["pr merge"] = {"killed": True}
        routes["view-state"] = {"stdout": '{"state":"OPEN","mc":null}\n'}
        exit_code, output, _, _, _ = run_case(
            scratch, "merge-killed", [(GATE_PASSED, 0)], routes, review_worktrees_state="both")
        review_worktrees = scratch / "merge-killed" / "review-worktrees"
        check("a merge killed by a signal exits 1 and leaves the review worktrees in place",
              exit_code == 1 and (review_worktrees / "pr10-head").is_dir()
              and (review_worktrees / "pr10-merged").is_dir(), f"exit {exit_code}\n{output}")

        exit_code, output, gh_calls, gate_calls, _ = run_case(
            scratch, "no-token", [(GATE_PASSED, 0)], default_routes(STACKED_AND_NOT),
            token=None)
        check("an unreadable token file exits 2 before the gate or gh runs, quoting the "
              "operating system's error and saying to tell the user the message",
              exit_code == 2 and gate_calls == [] and gh_calls == []
              and "could not read the merge account's token at " in output
              and ": No such file or directory.\nTell the user this message as printed, from its "
                  "STOP line, which says why the token is unusable, through this line: only the "
                  "user can restore the token." in output,
              f"exit {exit_code}\n{output}")

        exit_code, output, gh_calls, gate_calls, _ = run_case(
            scratch, "blank-token", [(GATE_PASSED, 0)], default_routes(STACKED_AND_NOT),
            token=" \t ")
        check("a token file holding only whitespace exits 2 before the gate or gh runs",
              exit_code == 2 and gate_calls == [] and gh_calls == []
              and "STOP: not merged" in output and "is empty" in output,
              f"exit {exit_code}\n{output}")

        exit_code, output, gh_calls, gate_calls, _ = run_case(
            scratch, "review-tools-behind-main", [(GATE_PASSED, 0)],
            default_routes(STACKED_AND_NOT), review_tools_state="behind-main")
        review_tools = scratch / "review-tools-behind-main" / "review-tools"
        main_now = origin_commit(scratch, "review-tools-behind-main")
        check("a review tools worktree behind origin/main that holds nothing of its own is "
              "checked out, detached, at origin/main before the gate, and the merge goes on",
              exit_code == 0 and git_output(review_tools, "rev-parse", "HEAD") == main_now
              and git_output(review_tools, "symbolic-ref", "-q", "HEAD", check=False) == ""
              and (review_tools / "new-on-main.txt").is_file()
              and (review_tools / "scripts" / "merge-gate.sh").is_file()
              and gate_calls == [f"{PULL_REQUEST} {HEAD} {SINCE}"]
              and index_of(argvs(gh_calls), ["pr", "merge"]) is not None
              and printed_in_order(output,
                                   f"checked out origin/main in {review_tools}, which was at ",
                                   "gate passed (#10)"),
              f"exit {exit_code}\n{output}")

        leave_it_alone = ("Leave {worktree} as it is: do not move, remove, discard, stash or "
                          "overwrite anything in it unless the user tells you to, because it may "
                          "be someone's unsaved work.")
        subagent = "If you are a subagent, ask the agent that dispatched you instead."
        own_work_to_the_user = (
            leave_it_alone + "\nTell the user that merges stop until that work is kept elsewhere "
            "and {worktree} is detached at origin/main or an older commit of main, with no "
            "change to a tracked file and no operation in progress; name the work, and ask how the user wants it kept and who "
            "does it. Once {worktree} is in that state, run this program again, which then checks "
            "out origin/main in it itself. " + subagent)
        files_in_the_way_to_the_user = (
            leave_it_alone + " Do not move or remove the files git lists, whatever git suggests "
            "above.\nTell the user that merges stop until the files git lists are gone from "
            "{worktree}; name them, and ask how the user wants them kept and who moves them. Once "
            "they are gone, run this program again. " + subagent)
        for name, arrange, own_work in (
                ("tracked change", lambda tools: (tools / "README").write_text("edited\n"),
                 "a tracked file is changed, such as README"),
                ("branch", lambda tools: git("checkout", "-q", "-b", "local-work", cwd=tools),
                 "the branch local-work is checked out"),
                ("commit of its own",
                 lambda tools: git("commit", "-q", "--allow-empty", "-m", "own", cwd=tools),
                 "is not an ancestor of origin/main, so it may hold commits main lacks"),
                ("cherry-pick in progress",
                 lambda tools: git_path(tools, "CHERRY_PICK_HEAD").write_text(
                     git_output(tools, "rev-parse", "HEAD") + "\n"),
                 "a cherry-pick is in progress")):
            case = "review-tools-behind-main-" + name.replace(" ", "-")
            head_before = []

            def arrange_and_remember(directory, arrange=arrange, head_before=head_before):
                tools = directory / "review-tools"
                arrange(tools)
                head_before.append(git_output(tools, "rev-parse", "HEAD"))

            exit_code, output, gh_calls, gate_calls, _ = run_case(
                scratch, case, [(GATE_PASSED, 0)], default_routes(STACKED_AND_NOT),
                review_tools_state="behind-main", before_the_program_runs=arrange_and_remember)
            review_tools = scratch / case / "review-tools"
            check(f"a review tools worktree behind origin/main that holds a {name} is left "
                  f"where it is, and the program stops before the gate, exit 2, saying what "
                  f"work it holds, to leave it alone and to tell the user",
                  exit_code == 2 and gate_calls == [] and gh_calls == []
                  and git_output(review_tools, "rev-parse", "HEAD") == head_before[0]
                  and ("and holds work of its own, so this program does not check out "
                       "origin/main in it: ") in output
                  and own_work in output
                  and output.rstrip().endswith(
                      own_work_to_the_user.format(worktree=review_tools)),
                  f"exit {exit_code}\n{output}")

        case = "review-tools-behind-main-checkout-fails"
        exit_code, output, gh_calls, gate_calls, _ = run_case(
            scratch, case, [(GATE_PASSED, 0)], default_routes(STACKED_AND_NOT),
            review_tools_state="behind-main",
            before_the_program_runs=lambda directory: (
                directory / "review-tools" / "new-on-main.txt").write_text("untracked\n"))
        review_tools = scratch / case / "review-tools"
        check("a review tools worktree whose checkout at origin/main git refuses over an "
              "untracked file main adds stops before the gate, exit 2, with git's whole error, "
              "which names the file, saying to leave the worktree alone and tell the user, the "
              "untracked file kept",
              exit_code == 2 and gate_calls == [] and gh_calls == []
              and f"could not check {review_tools} out at origin/main" in output
              and "would be overwritten by checkout:\n\tnew-on-main.txt" in output
              and (review_tools / "new-on-main.txt").read_text() == "untracked\n"
              and output.rstrip().endswith(
                  files_in_the_way_to_the_user.format(worktree=review_tools)),
              f"exit {exit_code}\n{output}")

        def ignored_file_main_adds(directory):
            tools = directory / "review-tools"
            (tools / "new-on-main.txt").write_text("ignored\n")
            exclude = git_path(tools, "info/exclude")
            exclude.parent.mkdir(parents=True, exist_ok=True)
            with exclude.open("a") as excluded:
                excluded.write("new-on-main.txt\n")

        case = "review-tools-behind-main-checkout-refuses-ignored-file"
        exit_code, output, gh_calls, gate_calls, _ = run_case(
            scratch, case, [(GATE_PASSED, 0)], default_routes(STACKED_AND_NOT),
            review_tools_state="behind-main", before_the_program_runs=ignored_file_main_adds)
        review_tools = scratch / case / "review-tools"
        check("a review tools worktree holding an ignored file at a path main adds is not "
              "checked out at origin/main over the file: the program stops before the gate, "
              "exit 2, with git's whole error, which names the file, the ignored file kept",
              exit_code == 2 and gate_calls == [] and gh_calls == []
              and "would be overwritten by checkout:\n\tnew-on-main.txt" in output
              and (review_tools / "new-on-main.txt").read_text() == "ignored\n"
              and output.rstrip().endswith(
                  files_in_the_way_to_the_user.format(worktree=review_tools)),
              f"exit {exit_code}\n{output}")

        case = "review-tools-behind-main-checkout-killed"
        exit_code, output, gh_calls, gate_calls, _ = run_case(
            scratch, case, [(GATE_PASSED, 0)], default_routes(STACKED_AND_NOT),
            review_tools_state="behind-main", git_killed_before_the_merge_on=" checkout ")
        review_tools = scratch / case / "review-tools"
        check("a review tools worktree whose checkout at origin/main fails otherwise, here "
              "killed by a signal, stops before the gate, exit 2, saying to run the program "
              "again once and then tell the user",
              exit_code == 2 and gate_calls == [] and gh_calls == []
              and f"could not check {review_tools} out at origin/main" in output
              and output.rstrip().endswith(
                  ": git printed no error\nRun this program again once; if it fails the same "
                  "way, " + TELL_THE_USER_WITH_THE_GIT_ERROR),
              f"exit {exit_code}\n{output}")

        exit_code, output, gh_calls, gate_calls, _ = run_case(
            scratch, "review-tools-fetch-fails", [(GATE_PASSED, 0)],
            default_routes(STACKED_AND_NOT), review_tools_state="no-origin")
        check("a review tools worktree that cannot fetch origin stops before the gate, exit 2",
              exit_code == 2 and gate_calls == [] and gh_calls == []
              and "could not fetch origin" in output
              and f"\n{RERUN_ONCE_THEN}{TELL_THE_USER_WITH_THE_GIT_ERROR}" in output,
              f"exit {exit_code}\n{output}")

        for failing, words, instruction in (
                (" fetch ", "main's cannot be told",
                 RERUN_ONCE_THEN + TELL_THE_USER_WITH_THE_GIT_ERROR),
                (" rev-parse ", "could not read HEAD and origin/main in",
                 "T" + TELL_THE_USER_WITH_THE_GIT_ERROR[1:])):
            exit_code, output, gh_calls, gate_calls, _ = run_case(
                scratch, f"review-tools{failing.replace(' ', '-')}killed", [(GATE_PASSED, 0)],
                default_routes(STACKED_AND_NOT), git_killed_before_the_merge_on=failing)
            check(f"a git{failing}in the review tools worktree killed by a signal stops before "
                  f"the gate, exit 2, saying git printed no error and to tell the user the "
                  f"message with the git error it quotes",
                  exit_code == 2 and gate_calls == [] and gh_calls == []
                  and words in output and f": git printed no error\n{instruction}" in output,
                  f"exit {exit_code}\n{output}")

        for failing, words in ((" symbolic-ref ", "could not read whether a branch is checked "
                                                  "out in "),
                               (" merge-base ", "could not read whether HEAD "),
                               (" status ", "could not read the changes to tracked files in "),
                               (" --git-path ", "could not read where git keeps its operation "
                                                "state in ")):
            exit_code, output, gh_calls, gate_calls, _ = run_case(
                scratch, f"review-tools-behind-main{failing.replace(' ', '-')}killed",
                [(GATE_PASSED, 0)], default_routes(STACKED_AND_NOT),
                review_tools_state="behind-main", git_killed_before_the_merge_on=failing)
            check(f"a git{failing}that reads whether a review tools worktree behind origin/main "
                  f"holds work of its own, killed by a signal, stops before the gate, exit 2, "
                  f"saying git printed no error and to tell the user the message",
                  exit_code == 2 and gate_calls == [] and gh_calls == []
                  and words in output
                  and output.rstrip().endswith(
                      ": git printed no error\nT" + TELL_THE_USER_WITH_THE_GIT_ERROR[1:]),
                  f"exit {exit_code}\n{output}")

        exit_code, output, gh_calls, gate_calls, _ = run_case(
            scratch, "no-gate", [(GATE_PASSED, 0)],
            default_routes(STACKED_AND_NOT), review_tools_state="no-gate")
        check("a review tools worktree without merge-gate.sh stops before any run, exit 2",
              exit_code == 2 and gh_calls == [] and "merge-gate.sh is missing" in output,
              f"exit {exit_code}\n{output}")

        exit_code, output, gh_calls, _, _ = run_case(
            scratch, "gate-undocumented-exit", [("bash: something broke\n", 127)],
            default_routes(STACKED_AND_NOT))
        check("a gate exit outside 0, 1 and 2 is reported as could-not-run, exit 2",
              exit_code == 2 and gh_calls == [] and "exited 127" in output,
              f"exit {exit_code}\n{output}")

        routes = default_routes(STACKED_AND_NOT)
        routes["view-branches"] = {"exit": 1, "stderr": "HTTP 503\n"}
        exit_code, output, gh_calls, _, _ = run_case(
            scratch, "view-branches-fails", [(GATE_PASSED, 0)], routes)
        calls = argvs(gh_calls)
        check("a pull request whose branches cannot be read stops before the merge, exit 2",
              exit_code == 2 and index_of(calls, ["pr", "merge"]) is None
              and index_of(calls, ["pr", "edit"]) is None
              and "STOP: not merged: could not read pull request 10's branch" in output
              and f"could not be found: HTTP 503\n{RERUN_ONCE_THEN}"
                  f"{TELL_THE_USER_WITH_THE_GH_ERROR}" in output,
              f"exit {exit_code}\n{output}")

        exit_code, output, _, _, _ = run_case(
            scratch, "after-merge-passes", [(GATE_PASSED, 0)], default_routes(STACKED_AND_NOT))
        merge_commit = origin_commit(scratch, "after-merge-passes")
        merge_commit_worktree = scratch / "after-merge-passes" / "review-worktrees" / "pr10-merge-commit-on-main-worktree"
        log_dir = (scratch / "after-merge-passes" / "outputs"
                   / f"pr10-after-merge-test-run-logs-{merge_commit[:12]}")
        calls = runner_calls(scratch, "after-merge-passes")
        check("with no head test run record, after the merge the runner in a worktree at the "
              "merge commit runs the suites whose recorded inputs changed since the reviewed "
              "head, its logs in the outputs directory, and says it fell back to the head",
              f"selecting the nn-test-suites whose recorded inputs changed since the head "
              f"commit {HEAD[:12]}, which selects more suites than the merge changed: no "
              f"readable head test run record under" in output
              and len(calls) == 1 and calls[0]["cwd"] == str(merge_commit_worktree)
              and calls[0]["argv"] == ["--only-suites-whose-recorded-inputs-changed-since", HEAD,
                                       "--log-dir", str(log_dir)], json.dumps(calls))
        check("a passing after-merge test run prints its SUMMARY and log directory, removes "
              "its worktree and exits 0",
              exit_code == 0 and RUNNER_PASSED_SUMMARY in output
              and f"test-run-report.txt: {log_dir}" in output
              and "PASS scripts/some-test.py" not in output
              and f"removed the worktree {merge_commit_worktree}" in output
              and not merge_commit_worktree.exists()
              and not any("pr10-merge-commit-on-main-worktree" in path for path in registered_worktrees(
                  scratch / "after-merge-passes" / "review-tools")),
              f"exit {exit_code}\n{output}")

        def head_test_run_recordings(directory):
            saved = directory / "outputs" / "hr" / "pr10" / "recorded-inputs"
            recording_in_store(saved, directory, RECORDED_SUITE,
                               blob_of(directory, RECORDED_SUITE))
            recording_in_store(saved, directory, STALE_SUITE, "0" * 40)

        name = "recordings-adopted"
        exit_code, output, _, _, _ = run_case(
            scratch, name, [(GATE_PASSED, 0)], default_routes(STACKED_AND_NOT),
            origin_files={RECORDED_SUITE: "print('ok')\n", STALE_SUITE: "print('ok')\n"},
            before_the_program_runs=head_test_run_recordings)
        outputs = scratch / name / "outputs"
        store = outputs / "hr" / "store"
        saved = outputs / "hr" / "pr10" / "recorded-inputs"
        adopted = sorted(path.name for path in store.glob("*/*.json"))
        adopted_line = (f"adopted 1 recordings into {store} from {saved}, where this pull "
                        f"request's head test runs saved their recordings; a recording is "
                        f"adopted only when its run passed and it matches the merge commit")
        check("before the after-merge test run starts, a recording the head test run saved "
              "under hr/pr10/recorded-inputs that matches the merge commit is adopted into "
              "hr/store, one that read another copy of its suite is not, and "
              "hr/pr10/recorded-inputs is removed",
              exit_code == 0
              and adopted == [RECORDED_SUITE.replace("/", "__") + ".json"]
              and printed_in_order(output, adopted_line, "testing main at the merge commit")
              and not saved.exists(), f"exit {exit_code}\n{output}\n{adopted}")
        default = default_recorded_inputs_directory(scratch / name)
        in_default = sorted(path.name for path in default.glob("*/*.json"))
        check("before the after-merge test run starts, and after hr/pr10/recorded-inputs is "
              "adopted, the recordings in hr/store that match the merge commit are adopted into "
              "the runner's default recorded-inputs directory, which the run selects by",
              in_default == [RECORDED_SUITE.replace("/", "__") + ".json"]
              and printed_in_order(output, adopted_line,
                                   f"adopted 1 recordings into {default} from {store}, the "
                                   f"store merge-lane head test runs select by; a recording is adopted only when",
                                   "testing main at the merge commit"),
              f"{output}\n{in_default}")
        check("after the after-merge test run, recordings are adopted from the runner's "
              "default recorded-inputs directory too",
              printed_in_order(output, "testing main at the merge commit",
                               f"adopted 0 recordings into {store} from "
                               f"{default_recorded_inputs_directory(scratch / name)}, "
                               f"where the after-merge test run saved its recordings"), output)

        def after_merge_test_run_recording(directory):
            recording_in_store(default_recorded_inputs_directory(directory), directory,
                               RECORDED_SUITE, blob_of(directory, RECORDED_SUITE))

        name = "recordings-adopted-from-the-default-store"
        exit_code, output, _, _, _ = run_case(
            scratch, name, [(GATE_PASSED, 0)], default_routes(STACKED_AND_NOT),
            origin_files={RECORDED_SUITE: "print('ok')\n"},
            before_the_program_runs=after_merge_test_run_recording)
        store = scratch / name / "outputs" / "hr" / "store"
        adopted = sorted(path.name for path in store.glob("*/*.json"))
        check("after the after-merge test run, a recording in the runner's default "
              "recorded-inputs directory that matches the merge commit is adopted into hr/store",
              exit_code == 0 and adopted == [RECORDED_SUITE.replace("/", "__") + ".json"]
              and printed_in_order(output, "testing main at the merge commit",
                                   f"adopted 1 recordings into {store} from "
                                   f"{default_recorded_inputs_directory(scratch / name)}, "
                                   f"where the after-merge test run saved its recordings"),
              f"exit {exit_code}\n{output}\n{adopted}")

        def stale_default_and_matching_store(directory):
            store = directory / "outputs" / "hr" / "store"
            recording_in_store(store, directory, RECORDED_SUITE, blob_of(directory, RECORDED_SUITE))
            recording_in_store(store, directory, STALE_SUITE, "0" * 40)
            recording_in_store(default_recorded_inputs_directory(directory), directory,
                               RECORDED_SUITE, "0" * 40)

        name = "recordings-adopted-into-the-default-store"
        exit_code, output, _, _, _ = run_case(
            scratch, name, [(GATE_PASSED, 0)], default_routes(STACKED_AND_NOT),
            origin_files={RECORDED_SUITE: "print('ok')\n", STALE_SUITE: "print('ok')\n"},
            before_the_program_runs=stale_default_and_matching_store)
        default = default_recorded_inputs_directory(scratch / name)
        found = {path.name: json.loads(path.read_text())["reads"]
                 for path in default.glob("*/*.json")}
        check("before the after-merge test run, a stale recording in the runner's default "
              "recorded-inputs directory is replaced by the one in hr/store that matches the "
              "merge commit, and a recording in hr/store that does not match is not adopted",
              exit_code == 0
              and found == {RECORDED_SUITE.replace("/", "__") + ".json": {
                  RECORDED_SUITE: blob_of(scratch / name, RECORDED_SUITE)}}
              and printed_in_order(output, f"adopted 1 recordings into {default} from ",
                                   "testing main at the merge commit"),
              f"exit {exit_code}\n{output}\n{found}")

        def default_cannot_be_written(directory):
            stale_default_and_matching_store(directory)
            for held in default_recorded_inputs_directory(directory).glob("*"):
                held.chmod(0o555)

        name = "recordings-not-adopted-into-the-default-store"
        try:
            exit_code, output, _, _, _ = run_case(
                scratch, name, [(GATE_PASSED, 0)], default_routes(STACKED_AND_NOT),
                origin_files={RECORDED_SUITE: "print('ok')\n", STALE_SUITE: "print('ok')\n"},
                before_the_program_runs=default_cannot_be_written)
        finally:
            for held in default_recorded_inputs_directory(scratch / name).glob("*"):
                held.chmod(0o755)
        default = default_recorded_inputs_directory(scratch / name)
        store = scratch / name / "outputs" / "hr" / "store"
        check("a recording from hr/store that cannot be saved into the runner's default "
              "recorded-inputs directory exits 3 with one STOP line, which names both "
              "directories and says the after-merge test run may run suites again, and the run "
              "still runs",
              exit_code == 3 and output.count("STOP:") == 1
              and printed_in_order(output,
                                   f"STOP: merged, but the recordings in {store}, the store "
                                   f"merge-lane head test runs select by, were not "
                                   f"adopted into {default}: ",
                                   f"So this after-merge test run selects the suites whose "
                                   f"recordings in {default} do not match the merge commit",
                                   "testing main at the merge commit", RUNNER_PASSED_SUMMARY)
              and len(runner_calls(scratch, name)) == 1, f"exit {exit_code}\n{output}")

        name = "recordings-not-adopted-git-killed"
        exit_code, output, _, _, _ = run_case(
            scratch, name, [(GATE_PASSED, 0)], default_routes(STACKED_AND_NOT),
            origin_files={RECORDED_SUITE: "print('ok')\n"},
            git_fails_after_merge_on=(" ls-tree ", "kill"))
        stop_lines = [line for line in output.splitlines() if line.startswith("STOP:")]
        check("an adoption whose git ls-tree is killed by a signal exits 3 with STOP lines that "
              "carry the runner's first line, saying git printed no error, and none of the "
              "runner's own next steps",
              exit_code == 3 and len(stop_lines) == 3
              and all("were not adopted into" in line
                      and line.endswith("failed in "
                                        f"{scratch / name / 'review-worktrees' / 'pr10-merge-commit-on-main-worktree'}"
                                        ": git printed no error")
                      for line in stop_lines)
              and "run-all-test-suites.py command" not in output, f"exit {exit_code}\n{output}")

        def only_the_after_run_adoption_can_fail(directory):
            after_merge_test_run_recording(directory)
            (directory / "outputs" / "hr" / "store").mkdir(parents=True)
            (directory / "outputs" / "hr" / "store").chmod(0o555)

        name = "recordings-not-adopted-after-the-run"
        try:
            exit_code, output, _, _, _ = run_case(
                scratch, name, [(GATE_PASSED, 0)], default_routes(STACKED_AND_NOT),
                origin_files={RECORDED_SUITE: "print('ok')\n"},
                before_the_program_runs=only_the_after_run_adoption_can_fail)
        finally:
            (scratch / name / "outputs" / "hr" / "store").chmod(0o755)
        store = scratch / name / "outputs" / "hr" / "store"
        saved = scratch / name / "outputs" / "hr" / "pr10" / "recorded-inputs"
        check("when the adoption before the after-merge test run succeeds and the run passes, "
              "a recording from the default recorded-inputs directory that cannot be saved into "
              "hr/store exits 3 with that adoption's STOP line alone, which does not say to remove "
              "the default directory",
              exit_code == 3 and output.count("STOP:") == 1
              and printed_in_order(output,
                                   f"adopted 0 recordings into {store} from {saved}, ",
                                   RUNNER_PASSED_SUMMARY,
                                   f"STOP: merged, but the recordings in "
                                   f"{default_recorded_inputs_directory(scratch / name)}, where "
                                   f"the after-merge test run saved its recordings, were not adopted "
                                   f"into {store}")
              and "then remove" not in output, f"exit {exit_code}\n{output}")

        def store_cannot_be_written(directory):
            head_test_run_recordings(directory)
            (directory / "outputs" / "hr" / "store").write_text("not a directory\n")

        name = "recordings-not-adopted"
        exit_code, output, _, _, _ = run_case(
            scratch, name, [(GATE_PASSED, 0)], default_routes(STACKED_AND_NOT),
            origin_files={RECORDED_SUITE: "print('ok')\n", STALE_SUITE: "print('ok')\n"},
            before_the_program_runs=store_cannot_be_written)
        merge_commit_worktree = (scratch / name / "review-worktrees"
                                 / "pr10-merge-commit-on-main-worktree")
        saved = scratch / name / "outputs" / "hr" / "pr10" / "recorded-inputs"
        check("a recording that cannot be saved into hr/store exits 3, says the recordings "
              "were not adopted, removes hr/pr10/recorded-inputs, which no later merge reads, "
              "still runs the after-merge test run and removes the worktree",
              exit_code == 3
              and f"STOP: merged, but the recordings in {saved}, where this pull request's "
                  f"head test runs saved their recordings, were not adopted into "
                  f"{scratch / name / 'outputs' / 'hr' / 'store'}" in output
              and ("Nothing else waits on this adoption: the program goes on and exits 3, and "
                   "the next merge adopts its own recordings.\nIf the error names a cause you can "
                   "fix, fix it; nothing needs to be run again. Otherwise, "
                   + TELL_THE_USER_WITH_THE_ERROR)
              in output
              and f"remove {saved}" not in output
              and not saved.exists() and len(runner_calls(scratch, name)) == 1
              and not merge_commit_worktree.exists(), f"exit {exit_code}\n{output}")

        def store_cannot_be_written_nor_saved_apart_removed(directory):
            store_cannot_be_written(directory)
            for held in (directory / "outputs" / "hr" / "pr10" / "recorded-inputs").glob("*"):
                held.chmod(0o555)

        name = "recordings-not-adopted-and-saved-apart-not-removed"
        try:
            exit_code, output, _, _, _ = run_case(
                scratch, name, [(GATE_PASSED, 0)], default_routes(STACKED_AND_NOT),
                origin_files={RECORDED_SUITE: "print('ok')\n", STALE_SUITE: "print('ok')\n"},
                before_the_program_runs=store_cannot_be_written_nor_saved_apart_removed)
        finally:
            for held in (scratch / name / "outputs" / "hr" / "pr10" / "recorded-inputs").glob("*"):
                held.chmod(0o755)
        saved = scratch / name / "outputs" / "hr" / "pr10" / "recorded-inputs"
        check("after a failed adoption before the run, a hr/pr10/recorded-inputs that cannot "
              "be removed exits 3 with a STOP line naming it, after the adoption's own",
              exit_code == 3
              and printed_in_order(output, f"STOP: merged, but the recordings in {saved}, ",
                                   f"STOP: merged, but {saved}, which no run reads any more, "
                                   f"was not removed")
              and len(runner_calls(scratch, name)) == 1, f"exit {exit_code}\n{output}")

        def saved_apart_cannot_be_removed(directory):
            head_test_run_recordings(directory)
            for held in (directory / "outputs" / "hr" / "pr10" / "recorded-inputs").glob("*"):
                held.chmod(0o555)

        name = "recordings-saved-apart-not-removed"
        try:
            exit_code, output, _, _, _ = run_case(
                scratch, name, [(GATE_PASSED, 0)], default_routes(STACKED_AND_NOT),
                origin_files={RECORDED_SUITE: "print('ok')\n", STALE_SUITE: "print('ok')\n"},
                before_the_program_runs=saved_apart_cannot_be_removed)
        finally:
            for held in (scratch / name / "outputs" / "hr" / "pr10" / "recorded-inputs").glob("*"):
                held.chmod(0o755)
        saved = scratch / name / "outputs" / "hr" / "pr10" / "recorded-inputs"
        check("a hr/pr10/recorded-inputs that cannot be removed after its recordings are "
              "adopted exits 3, naming it",
              exit_code == 3
              and f"STOP: merged, but {saved}, which no run reads any more, was not removed"
              in output and f"fix it and remove {saved}. Otherwise, "
                            f"{TELL_THE_USER_WITH_THE_ERROR}" in output
              and len(runner_calls(scratch, name)) == 1, f"exit {exit_code}\n{output}")

        name = "since-merged-main-not-moved"
        exit_code, output, _, _, _ = run_case(
            scratch, name, [(GATE_PASSED, 0)], default_routes(STACKED_AND_NOT),
            head_test_run_test_logs=[
                (f"{'0' * 40}.txt", head_test_run_record("0" * 40, 0, "2026-11-07T20:00:00Z")),
                ("MERGED.txt", head_test_run_record("MERGED", 0)),
                (f"{'f' * 40}.txt", head_test_run_record("f" * 40, 0, "2026-11-07T19:00:00Z"))])
        merged = merged_commit(scratch, name)
        calls = runner_calls(scratch, name)
        check("when main has not moved since the head test run, the after-merge run selects "
              "since the pr10-merged commit of the passing record started last, whose tree is "
              "the merge commit's, so no suite is selected",
              exit_code == 0 and len(calls) == 1 and calls[0]["argv"][:2] == [
                  "--only-suites-whose-recorded-inputs-changed-since", merged]
              and tree_of(scratch, name, merged)
              == tree_of(scratch, name, origin_commit(scratch, name))
              and f"selecting the nn-test-suites whose recorded inputs changed since "
                  f"{merged[:12]}, the commit the head test run passed on: "
                  f"pull request 10's head merged with main as main was when that run started"
                  in output
              and f"changed since {merged[:12]}" in output
              and "since the head commit" not in output,
              f"exit {exit_code}\n{output}\n{json.dumps(calls)}")

        name = "since-merged-past-an-unreadable-test-log"
        exit_code, output, _, _, _ = run_case(
            scratch, name, [(GATE_PASSED, 0)], default_routes(STACKED_AND_NOT),
            head_test_run_test_logs=[(f"{'0' * 40}.txt", None),
                                     ("MERGED.txt", head_test_run_record("MERGED", 0))])
        merged = merged_commit(scratch, name)
        calls = runner_calls(scratch, name)
        check("a test log that cannot be read is passed over, and a passing record in a "
              "test log read after it is still used",
              exit_code == 0 and len(calls) == 1 and calls[0]["argv"][:2] == [
                  "--only-suites-whose-recorded-inputs-changed-since", merged]
              and "could not be read, so it is not used" in output,
              f"exit {exit_code}\n{output}\n{json.dumps(calls)}")

        for name, test_logs, notice in (
                ("since-head-when-last-record-failed",
                 [("MERGED.txt", head_test_run_record("MERGED", 0)
                   + head_test_run_record("MERGED", 1, "2026-11-07T22:00:00Z"))],
                 "no readable head test run record under"),
                ("since-head-when-record-names-another-commit",
                 [("MERGED.txt", head_test_run_record("b" * 40, 0))],
                 "no readable head test run record under"),
                ("since-head-when-test-log-is-a-directory", [("MERGED.txt", None)],
                 "could not be read, so it is not used"),
                ("since-head-when-record-is-torn",
                 [("MERGED.txt", head_test_run_record("MERGED", 0).rsplit("\n", 2)[0] + "\n")],
                 "could not be read, so it is not used"),
                ("since-head-when-test-log-is-not-utf-8", [("MERGED.txt", b"\xff\n")],
                 "could not be read, so it is not used")):
            exit_code, output, _, _, _ = run_case(
                scratch, name, [(GATE_PASSED, 0)], default_routes(STACKED_AND_NOT),
                head_test_run_test_logs=test_logs)
            calls = runner_calls(scratch, name)
            check(f"{name.replace('-', ' ')}: the after-merge run selects since the head "
                  f"commit, as before, and prints that it fell back",
                  exit_code == 0 and len(calls) == 1 and calls[0]["argv"][:2] == [
                      "--only-suites-whose-recorded-inputs-changed-since", HEAD]
                  and notice in output
                  and f"changed since the head commit {HEAD[:12]}, which selects more suites "
                      f"than the merge changed" in output,
                  f"exit {exit_code}\n{output}\n{json.dumps(calls)}")

        exit_code, output, _, _, _ = run_case(
            scratch, "after-merge-fails", [(GATE_PASSED, 0)], default_routes(STACKED_AND_NOT),
            runner_answer=(RUNNER_FAILED, 1))
        merge_commit_worktree = scratch / "after-merge-fails" / "review-worktrees" / "pr10-merge-commit-on-main-worktree"
        check("a failing after-merge test run exits 3, naming each failed suite with its log, "
              "with its SUMMARY, and still removes its worktree",
              exit_code == 3
              and "FAIL scripts/broken-test.py exit 1 — log /logs/broken-test.py.log" in output
              and "SUMMARY: 1 passed, 1 failed" in output
              and "STOP: merged, but the test run of main at" in output and "exited 1" in output
              and ("No repair task was opened: the merged branch's author, unknown, has no task "
                   "list or no checkout on this machine. Nobody is assigned to fix main.\n"
                   "Ask the user: \"Main fails scripts/broken-test.py after pull request 10")
              in output
              and not merge_commit_worktree.exists(), f"exit {exit_code}\n{output}")

        failed_suites_kept_in_view_cases(scratch)
        newest_main_commit_left_no_test_failing_cases(scratch)

        exit_code, output, _, _, _ = run_case(
            scratch, "after-merge-could-not-run", [(GATE_PASSED, 0)],
            default_routes(STACKED_AND_NOT), runner_answer=(RUNNER_COULD_NOT_RUN, 2))
        check("an after-merge test run with no SUMMARY line exits 3 and prints its whole output",
              exit_code == 3 and "printed no SUMMARY: line" in output
              and RUNNER_COULD_NOT_RUN.strip() in output and "exited 2" in output,
              f"exit {exit_code}\n{output}")

        exit_code, output, _, _, _ = run_case(
            scratch, "after-merge-exit-0-no-summary", [(GATE_PASSED, 0)],
            default_routes(STACKED_AND_NOT), runner_answer=("PASS scripts/some-test.py (1s)\n", 0))
        merge_commit_worktree = (scratch / "after-merge-exit-0-no-summary" / "review-worktrees"
                                 / "pr10-merge-commit-on-main-worktree")
        check("an after-merge test run that exits 0 with no SUMMARY line exits 3, says main's "
              "test run gave no verdict, and still removes its worktree",
              exit_code == 3 and "printed no SUMMARY: line" in output
              and "STOP: merged, but the test run of main at" in output
              and "gave no verdict" in output
              and "--only-suites-whose-recorded-inputs-changed-since" in output
              and not merge_commit_worktree.exists(), f"exit {exit_code}\n{output}")

        merge_502 = {"exit": 1, "stderr": "non-200 OK status code: 502 Bad Gateway\n"}
        branch_path = f"repos/nedsnodes/nedsnodes/branches/{BRANCH}"
        ref_path = f"repos/nedsnodes/nedsnodes/git/refs/heads/{BRANCH}"

        routes = default_routes(STACKED_AND_NOT)
        routes["pr merge"] = merge_502
        routes["api-read-branch"] = {"stdout": json.dumps({"name": BRANCH})}
        routes["api-delete-branch"] = {}
        exit_code, output, gh_calls, _, _ = run_case(
            scratch, "merge-exits-1-but-merged", [(GATE_PASSED, 0)], routes,
            review_worktrees_state="both")
        calls = argvs(gh_calls)
        review_worktrees = scratch / "merge-exits-1-but-merged" / "review-worktrees"
        check("a merge command that exits 1 over a merged pull request reports its error and "
              "goes on: the branch it left is deleted, the review worktrees removed and main "
              "tested, exit 0",
              exit_code == 0 and "pull request 10 merged although the merge command exited 1: "
                                 "non-200 OK status code: 502 Bad Gateway" in output
              and ["api", branch_path] in calls and ["api", ref_path, "-X", "DELETE"] in calls
              and f"deleted the branch {BRANCH}" in output
              and not (review_worktrees / "pr10-head").exists()
              and not (review_worktrees / "pr10-merged").exists()
              and len(runner_calls(scratch, "merge-exits-1-but-merged")) == 1
              and RUNNER_PASSED_SUMMARY in output, f"exit {exit_code}\n{output}\n{calls}")

        routes = default_routes(STACKED_AND_NOT)
        routes["pr merge"] = merge_502
        routes["api-read-branch"] = {"exit": 1, "stderr": "gh: Branch not found (HTTP 404)\n"}
        exit_code, output, gh_calls, _, _ = run_case(
            scratch, "merge-exits-1-branch-gone", [(GATE_PASSED, 0)], routes)
        check("a merge command that exits 1 over a merged pull request whose branch is gone "
              "deletes nothing and exits 0",
              exit_code == 0 and f"the branch {BRANCH} is gone from GitHub" in output
              and index_of(argvs(gh_calls), ["api", ref_path]) is None,
              f"exit {exit_code}\n{output}")

        routes = default_routes(STACKED_AND_NOT)
        routes["pr merge"] = merge_502
        routes["api-read-branch"] = {"stdout": json.dumps({"name": BRANCH})}
        routes["api-delete-branch"] = {"exit": 1, "stderr": "HTTP 422: Reference does not exist\n"}
        exit_code, output, _, _, _ = run_case(
            scratch, "merged-branch-not-deleted", [(GATE_PASSED, 0)], routes,
            review_worktrees_state="both")
        review_worktrees = scratch / "merged-branch-not-deleted" / "review-worktrees"
        check("a branch left by the merge that cannot be deleted exits 3 with gh's error and "
              "the command, and the review worktrees are still removed and main tested",
              exit_code == 3 and f"STOP: merged, but the branch {BRANCH} is still on GitHub "
                                 "and could not be deleted: HTTP 422" in output
              and f"Delete it: gh api -X DELETE {ref_path}\nIf that fails, "
                  f"{TELL_THE_USER_WITH_BOTH_GH_ERRORS}" in output
              and not (review_worktrees / "pr10-merged").exists()
              and len(runner_calls(scratch, "merged-branch-not-deleted")) == 1,
              f"exit {exit_code}\n{output}")

        routes = default_routes(STACKED_AND_NOT)
        routes["pr merge"] = merge_502
        routes["api-read-branch"] = [{"stdout": json.dumps({"name": BRANCH})},
                                     {"exit": 1, "stderr": "gh: Branch not found (HTTP 404)\n"}]
        routes["api-delete-branch"] = {"exit": 1,
                                       "stderr": "gh: Reference does not exist (HTTP 422)\n"}
        exit_code, output, gh_calls, _, _ = run_case(
            scratch, "merged-branch-gone-before-its-delete", [(GATE_PASSED, 0)], routes)
        branch_calls = [argv for argv in argvs(gh_calls) if argv[:1] == ["api"]]
        check("a branch that GitHub deletes between the program's read and its delete is "
              "found gone by a second read after the delete, and the program exits 0 "
              "without a STOP",
              exit_code == 0 and f"the branch {BRANCH} is gone from GitHub" in output
              and "STOP" not in output
              and branch_calls == [["api", branch_path],
                                   ["api", ref_path, "-X", "DELETE"],
                                   ["api", branch_path]]
              and len(runner_calls(scratch, "merged-branch-gone-before-its-delete")) == 1,
              f"exit {exit_code}\n{output}\n{json.dumps(branch_calls)}")

        routes = default_routes(STACKED_AND_NOT)
        routes["pr merge"] = merge_502
        routes["api-read-branch"] = [{"stdout": json.dumps({"name": BRANCH})},
                                     {"exit": 1, "stderr": "gh: Bad Gateway (HTTP 502)\n"}]
        routes["api-delete-branch"] = {"exit": 1,
                                       "stderr": "gh: Reference does not exist (HTTP 422)\n"}
        exit_code, output, _, _, _ = run_case(
            scratch, "merged-branch-reread-fails", [(GATE_PASSED, 0)], routes)
        check("a failed delete whose second read fails other than with HTTP 404 exits 3, "
              "says whether the branch is gone could not be read, and quotes both errors",
              exit_code == 3
              and f"STOP: merged, but the branch {BRANCH} could not be deleted, and whether "
                  "it is gone from GitHub could not be read." in output
              and "The deletion's error: gh: Reference does not exist (HTTP 422)" in output
              and "The read's error: gh: Bad Gateway (HTTP 502)" in output
              and "is still on GitHub" not in output
              and f"If it is still there, delete it: gh api -X DELETE {ref_path}\n" in output
              and len(runner_calls(scratch, "merged-branch-reread-fails")) == 1,
              f"exit {exit_code}\n{output}")

        routes = default_routes(STACKED_AND_NOT)
        routes["pr merge"] = merge_502
        routes["api-read-branch"] = {"exit": 1, "stderr": "HTTP 502\n"}
        exit_code, output, _, _, _ = run_case(
            scratch, "merged-branch-unread", [(GATE_PASSED, 0)], routes)
        check("a branch that cannot be read after a merge command that exited 1 over a merged "
              "pull request exits 3, and main is still tested",
              exit_code == 3 and f"whether the branch {BRANCH} is gone from GitHub could not "
                                 "be read: HTTP 502" in output
              and f"\nIf that fails, {TELL_THE_USER_WITH_BOTH_GH_ERRORS}" in output
              and len(runner_calls(scratch, "merged-branch-unread")) == 1,
              f"exit {exit_code}\n{output}")

        routes = default_routes(STACKED_AND_NOT)
        routes["pr merge"] = merge_502
        routes["view-state"] = {"stdout": '{"state":"CLOSED","mc":null}\n'}
        exit_code, output, gh_calls, _, _ = run_case(
            scratch, "merge-exits-1-closed", [(GATE_PASSED, 0)], routes,
            review_worktrees_state="both")
        review_worktrees = scratch / "merge-exits-1-closed" / "review-worktrees"
        check("a merge command that exits 1 over a closed pull request exits 1 with its error, "
              "touching the branch and the review worktrees not at all",
              exit_code == 1 and "pull request 10 is CLOSED after the merge command ran; the "
                                 "merge command exited 1: non-200 OK status code: 502" in output
              and index_of(argvs(gh_calls), ["api"]) is None
              and (review_worktrees / "pr10-merged").is_dir()
              and runner_calls(scratch, "merge-exits-1-closed") == [],
              f"exit {exit_code}\n{output}")

        routes = default_routes(STACKED_AND_NOT)
        routes["pr merge"] = merge_502
        routes["view-state"] = {"exit": 1, "stderr": "HTTP 503\n"}
        exit_code, output, gh_calls, _, _ = run_case(
            scratch, "merge-outcome-unknown", [(GATE_PASSED, 0)], routes,
            review_worktrees_state="both")
        review_worktrees = scratch / "merge-outcome-unknown" / "review-worktrees"
        check("a merge command that exits 1 when the state cannot be read exits 4, naming both "
              "errors and how to read the state, and does nothing after the merge",
              exit_code == 4 and "STOP: whether pull request 10 merged is unknown: the merge "
                                 "command exited 1: non-200 OK status code: 502" in output
              and "HTTP 503" in output and "gh pr view 10 --repo nedsnodes/nedsnodes" in output
              and index_of(argvs(gh_calls), ["api"]) is None
              and (review_worktrees / "pr10-merged").is_dir()
              and runner_calls(scratch, "merge-outcome-unknown") == [],
              f"exit {exit_code}\n{output}")

        routes = default_routes(STACKED_AND_NOT)
        routes["view-state"] = {"stdout": '{"state":"OPEN","mc":null}\n'}
        exit_code, output, _, _, _ = run_case(
            scratch, "merge-exits-0-but-open", [(GATE_PASSED, 0)], routes)
        check("a merge command that exits 0 while the pull request stays open exits 1",
              exit_code == 1 and "STOP: not merged: pull request 10 is OPEN" in output
              and runner_calls(scratch, "merge-exits-0-but-open") == [],
              f"exit {exit_code}\n{output}")

        routes = default_routes(STACKED_AND_NOT)
        routes["view-state"] = {"exit": 1, "stderr": "HTTP 502\n"}
        exit_code, output, _, _, _ = run_case(
            scratch, "merge-commit-unread", [(GATE_PASSED, 0)], routes)
        check("a merge commit that cannot be read after the merge exits 3 without a test run, "
              "saying how to run it by hand",
              exit_code == 3 and runner_calls(scratch, "merge-commit-unread") == []
              and "the merge commit could not be read" in output
              and f"--only-suites-whose-recorded-inputs-changed-since {HEAD}" in output,
              f"exit {exit_code}\n{output}")

        routes = default_routes(STACKED_AND_NOT)
        routes["view-state"] = {"stdout": "not json\n"}
        exit_code, output, _, _, _ = run_case(
            scratch, "merge-commit-not-json", [(GATE_PASSED, 0)], routes)
        check("a pull request state that is not JSON exits 3 without a test run",
              exit_code == 3 and runner_calls(scratch, "merge-commit-not-json") == []
              and "the merge commit could not be read" in output, f"exit {exit_code}\n{output}")

        routes = default_routes(STACKED_AND_NOT)
        routes["view-state"] = {"stdout": json.dumps({"state": "MERGED", "mc": "b" * 40})}
        exit_code, output, _, _, _ = run_case(
            scratch, "merge-commit-unknown", [(GATE_PASSED, 0)], routes)
        check("a merge commit origin does not have exits 3 at the fetch without a test run, "
              "naming git's error",
              exit_code == 3 and runner_calls(scratch, "merge-commit-unknown") == []
              and "to get the merge commit " + "b" * 40 in output
              and "could not make the worktree" not in output
              and "fatal: " in output, f"exit {exit_code}\n{output}")

        routes = default_routes(STACKED_AND_NOT)
        routes["pr merge"] = {"origin_main_to": "MERGE_COMMIT", "origin": "ORIGIN"}
        exit_code, output, _, _, _ = run_case(
            scratch, "fetch-raced-after-merge", [(GATE_PASSED, 0)], routes,
            another_fetch_races_the_after_merge_fetch=True)
        raced = scratch / "fetch-raced-after-merge"
        calls = runner_calls(scratch, "fetch-raced-after-merge")
        check("another fetch into the clone that moves origin/main while the after-merge fetch "
              "runs leaves the fetch, the worktree and the test run of the merge commit whole",
              (raced / "competing-fetch-ran").exists() and exit_code == 0
              and "could not fetch" not in output and RUNNER_PASSED_SUMMARY in output
              and len(calls) == 1 and calls[0]["cwd"].endswith(
                  "pr10-merge-commit-on-main-worktree"),
              f"exit {exit_code}\n{output}")

        routes = default_routes(STACKED_AND_NOT)
        routes["pr merge"] = {"origin_main_to": "MERGE_COMMIT", "origin": "ORIGIN"}
        exit_code, output, _, _, _ = run_case(
            scratch, "fetch-head-kept-after-merge", [(GATE_PASSED, 0)], routes,
            merge_commit_new_to_the_clone=True)
        kept = scratch / "fetch-head-kept-after-merge"
        merge_commit = subprocess.run(
            ["git", "-C", str(kept / "origin-seed"), "rev-parse", "HEAD"], capture_output=True,
            text=True, env=GIT_ENVIRONMENT, check=True).stdout.strip()
        fetch_head = subprocess.run(
            ["git", "-C", str(kept / "review-tools"), "rev-parse", "--git-path", "FETCH_HEAD"],
            capture_output=True, text=True, env=GIT_ENVIRONMENT, check=True).stdout.strip()
        fetch_head_text = (kept / "review-tools" / fetch_head).read_text()
        # The review program reads FETCH_HEAD after its own fetch in the same worktree, so an
        # after-merge fetch that wrote it could hand that program the merge commit.
        check("the after-merge fetch leaves the review tools worktree's FETCH_HEAD as the fetch "
              "before the gate wrote it",
              exit_code == 0 and RUNNER_PASSED_SUMMARY in output
              and merge_commit not in fetch_head_text and "branch 'main'" in fetch_head_text,
              f"exit {exit_code}\nFETCH_HEAD: {fetch_head_text}\n{output}")

        routes = default_routes(STACKED_AND_NOT)
        routes["pr merge"] = {"remove_directory": "ORIGIN"}
        exit_code, output, _, _, _ = run_case(
            scratch, "fetch-fails-after-merge", [(GATE_PASSED, 0)], routes)
        check("a fetch that fails after the merge exits 3 without a test run",
              exit_code == 3 and runner_calls(scratch, "fetch-fails-after-merge") == []
              and "could not fetch origin in " in output
              and "could not make the worktree" not in output
              and output.endswith(f"Otherwise, {TELL_THE_USER_WITH_THE_GIT_ERROR}\n"
                                  f"{GO_AHEAD_COUNT_ONLY[0]}"),
              f"exit {exit_code}\n{output}")

        exit_code, output, _, _, _ = run_case(
            scratch, "merge-commit-worktree-kept", [(GATE_PASSED, 0)],
            default_routes(STACKED_AND_NOT), git_killed_on_worktree_remove="pr10-merge-commit-on-main-worktree")
        merge_commit_worktree = (scratch / "merge-commit-worktree-kept" / "review-worktrees"
                                 / "pr10-merge-commit-on-main-worktree")
        check("an after-merge worktree that cannot be removed after a passing run exits 3, "
              "naming it and the command to remove it",
              exit_code == 3 and RUNNER_PASSED_SUMMARY in output
              and f"STOP: merged, but the worktree {merge_commit_worktree} was not removed" in output
              and f"worktree remove --force {merge_commit_worktree}" in output
              and "remove exited -9: git printed no error\n" in output
              and f"worktree remove --force {merge_commit_worktree}\nOtherwise, "
                  f"{TELL_THE_USER_WITH_THE_GIT_ERROR}" in output,
              f"exit {exit_code}\n{output}")

        exit_code, output, _, _, _ = run_case(
            scratch, "fetch-killed-after-merge", [(GATE_PASSED, 0)],
            default_routes(STACKED_AND_NOT), git_fails_after_merge_on=(" fetch ", "kill"))
        check("a fetch killed by a signal after the merge exits 3 without a test run",
              exit_code == 3 and runner_calls(scratch, "fetch-killed-after-merge") == []
              and "/review-tools to get the merge commit " in output
              and "could not make the worktree" not in output
              and ": git printed no error\n" in output,
              f"exit {exit_code}\n{output}")

        exit_code, output, _, _, _ = run_case(
            scratch, "worktree-add-killed", [(GATE_PASSED, 0)],
            default_routes(STACKED_AND_NOT), git_fails_after_merge_on=(" worktree add ", "kill"))
        check("a git worktree add killed by a signal exits 3 without a test run",
              exit_code == 3 and runner_calls(scratch, "worktree-add-killed") == []
              and "STOP: merged, but main was not tested: git worktree add, run in "
                  f"{scratch / 'worktree-add-killed' / 'review-tools'}, could not make the "
                  f"worktree {scratch / 'worktree-add-killed' / 'review-worktrees'}"
                  "/pr10-merge-commit-on-main-worktree at the merge commit " in output
              and ": git printed no error\n" in output
              and output.endswith(f"Otherwise, {TELL_THE_USER_WITH_THE_GIT_ERROR}\n"
                                  f"{GO_AHEAD_COUNT_ONLY[0]}"),
              f"exit {exit_code}\n{output}")

        exit_code, output, _, _, _ = run_case(
            scratch, "runner-killed", [(GATE_PASSED, 0)], default_routes(STACKED_AND_NOT),
            runner_answer=("PASS scripts/some-test.py (1s)\n", -9))
        check("an after-merge test run killed by a signal exits 3",
              exit_code == 3 and "STOP: merged, but the test run of main at" in output
              and "exited -9" in output, f"exit {exit_code}\n{output}")

        exit_code, output, _, _, _ = run_case(
            scratch, "merge-commit-worktree-remove-exits-1", [(GATE_PASSED, 0)],
            default_routes(STACKED_AND_NOT),
            git_fails_after_merge_on=(" worktree remove ", "exit 1"))
        check("an after-merge worktree whose removal exits 1 exits 3, with git's error",
              exit_code == 3 and "was not removed: git worktree remove exited 1: fake git failed"
              in output, f"exit {exit_code}\n{output}")
        base_modified = {"exit": 1, "stderr": "GraphQL: Base branch was modified. Review and "
                                              "try the merge again. (mergePullRequest)\n"}
        routes = default_routes(STACKED_AND_NOT)
        routes["pr merge"] = [base_modified, {}]
        exit_code, output, gh_calls, _, waits = run_case(
            scratch, "merge-base-branch-modified-once", [(GATE_PASSED, 0)], routes)
        merges = [argv for argv in argvs(gh_calls) if argv[:2] == ["pr", "merge"]]
        check("a merge GitHub refuses once with \"Base branch was modified\" is run again 5 "
              "seconds later, the same command, and merges, exit 0",
              exit_code == 0 and merges == [EXPECTED_MERGE, EXPECTED_MERGE] and waits == [5]
              and "merge try 1 of 3: GitHub refused the merge because main moved during it; "
                  "this program runs the merge command again in 5 seconds\n" in output
              and "merge exit 0" in output,
              f"exit {exit_code}\n{output}")

        routes = default_routes(STACKED_AND_NOT)
        routes["pr merge"] = base_modified
        routes["view-state"] = {"stdout": '{"state":"OPEN","mc":null}\n'}
        exit_code, output, gh_calls, _, waits = run_case(
            scratch, "merge-base-branch-modified-every-time", [(GATE_PASSED, 0)], routes)
        merges = [argv for argv in argvs(gh_calls) if argv[:2] == ["pr", "merge"]]
        check("a merge GitHub refuses with \"Base branch was modified\" every time is run 3 "
              "times, then reported as not merged with GitHub's error, exit 1",
              exit_code == 1 and len(merges) == 3 and waits == [5, 5]
              and "STOP: not merged: pull request 10 is OPEN after the merge command ran; the "
                  "merge command exited 1: GraphQL: Base branch was modified." in output
              and output.rstrip().endswith(
                  "GitHub refused the merge 3 times because main moved during it, as when other "
                  "merges run at the same time; GitHub's \"Review and try the merge again\" asks "
                  "for no new review.\nRun this program again once; if it is refused "
                  "this way again, tell the user that merges keep failing because main moves "
                  "during each one. If you are a subagent, report it to the agent that dispatched "
                  "you instead."),
              f"exit {exit_code}\n{output}")

        routes = default_routes(STACKED_AND_NOT)
        routes["pr merge"] = {"exit": 1, "stderr": "GraphQL: Pull request is not mergeable\n"}
        routes["view-state"] = {"stdout": '{"state":"OPEN","mc":null}\n'}
        exit_code, output, gh_calls, _, waits = run_case(
            scratch, "merge-refused-otherwise", [(GATE_PASSED, 0)], routes)
        merges = [argv for argv in argvs(gh_calls) if argv[:2] == ["pr", "merge"]]
        check("a merge GitHub refuses for any other reason is not run again, exit 1",
              exit_code == 1 and len(merges) == 1 and waits == [], f"exit {exit_code}\n{output}")
    finally:
        shutil.rmtree(scratch, ignore_errors=True)

    if failures:
        print(f"\n{len(failures)} case(s) failed")
        return 1
    print("\nall cases passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
