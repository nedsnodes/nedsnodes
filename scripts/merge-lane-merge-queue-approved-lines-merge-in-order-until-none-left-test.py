#!/usr/bin/env python3
"""Tests for merge-lane-merge-queue-approved-lines-merge-in-order-until-none-left.py.

Each case runs the program on a merge queue file in a temporary directory, with a fake gh
and a fake merge program that read and change one JSON state file, so no case reads or
writes GitHub, the live merge queue file or the merge-helpers directory.
"""
import contextlib
import fcntl
import importlib.util
import io
import json
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

PROGRAM = Path(__file__).resolve().with_name(
    "merge-lane-merge-queue-approved-lines-merge-in-order-until-none-left.py")
_spec = importlib.util.spec_from_file_location("merge_queue", PROGRAM)
program = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(program)

STOP_FILE_NAME = program.merge_program.MERGE_QUEUE_STOP_FILE_NAME
A = "a" * 40
B = "b" * 40
C = "c" * 40
MOVED = "d" * 40
QUEUED = "2026-11-25T10:00:00Z"
REVIEWED = "2026-11-25T10:20:00Z"

FAKE_GH = r'''#!/usr/bin/env python3
import json, os, sys
state_file = os.environ["FAKE_STATE"]
state = json.load(open(state_file))
argv = sys.argv[1:]
with open(state_file + ".gh-calls", "a") as log:
    log.write(json.dumps(argv) + "\n")
for garbled in state.get("gh_garbles", []):
    if " ".join(argv).startswith(garbled):
        print("<html>502</html>"); sys.exit(0)
for failing in state.get("gh_fails", []):
    if " ".join(argv).startswith(failing):
        sys.stderr.write("HTTP 502: bad gateway\n"); sys.exit(1)
for call, lines in state.get("gh_queue_appends", {}).items():
    marker = state_file + ".appended-on-" + call.replace(" ", "-")
    if " ".join(argv).startswith(call) and not os.path.exists(marker):
        open(marker, "w").close()
        with open(os.environ["FAKE_QUEUE"], "a") as queue:
            queue.writelines(line + "\n" for line in lines)
if argv[:2] == ["pr", "view"]:
    print(json.dumps(state["prs"][argv[2]]))
elif argv[:2] == ["pr", "list"]:
    branch = argv[argv.index("--head") + 1]
    print(json.dumps([{"number": n} for n in state.get("branches", {}).get(branch, [])]))
elif argv[0] == "api":
    number = argv[1].split("/")[-2]
    print(json.dumps([state.get("reviews", {}).get(number, [])]))
else:
    sys.stderr.write(f"fake gh has no route for {argv}\n"); sys.exit(1)
'''

FAKE_MERGE_PROGRAM = r'''import json, os, sys
state_file = os.environ["FAKE_STATE"]
state = json.load(open(state_file))
number, head, since = sys.argv[1:4]
outputs = sys.argv[sys.argv.index("--merge-lane-worktrees-and-outputs-directory") + 1]
with open(state_file + ".merge-calls", "a") as log:
    log.write(json.dumps([number, head, since]) + "\n")
outcome = state["merge_outcomes"].get(number, {"exit": 0, "merged": True})
for line in outcome.get("queue_append", []):
    with open(os.environ["FAKE_QUEUE"], "a") as queue:
        queue.write(line + "\n")
if outcome.get("merged"):
    state["prs"][number].update(state="MERGED", mergeCommit={"oid": number.rjust(40, "e")})
    for other in outcome.get("retargets", []):
        state["prs"][other]["baseRefName"] = "main"
json.dump(state, open(state_file, "w"))
print(outcome.get("output", "SUMMARY: 1 suite passed"))
if outcome["exit"] in (3, 4):
    open(os.path.join(outputs, "merge-queue-stopped.txt"), "w").write(
        f"pull request {number}'s merge program exited {outcome['exit']}\n")
sys.exit(outcome["exit"])
'''

FAKE_FOLLOW_UP = r'''import os, sys
if os.environ.get("FAKE_FOLLOW_UP_FAILS"):
    print("Traceback: no reviews"); sys.exit(1)
print(f"#follow_up_request pull request {sys.argv[1]}\n1. fix-next: something")
'''

failures = []


def check(name, condition, detail=""):
    print(f"{'PASS' if condition else 'FAIL'}  {name}")
    if not condition:
        failures.append(name)
        for line in str(detail).splitlines()[:40]:
            print(f"      {line}")


def pr(head, base="main", state="OPEN"):
    return {"state": state, "headRefOid": head, "baseRefName": base, "mergeCommit": None}


def merge_account_review(head, at):
    return {"user": {"login": "ned-review-merge"}, "commit_id": head, "submitted_at": at}


class Case:
    def __init__(self, scratch, name, queue_lines, prs, merge_outcomes=None, reviews=None,
                 branches=None, gh_fails=None, gh_garbles=None, gh_queue_appends=None):
        self.directory = scratch / name
        self.directory.mkdir()
        self.queue = self.directory / "merge-queue.txt"
        self.queue.write_text("".join(line + "\n" for line in queue_lines))
        self.batches = self.directory / "merge-queue-merge-batches"
        self.outputs = self.directory / "merge-helpers"
        self.outputs.mkdir()
        self.state = self.directory / "state.json"
        self.state.write_text(json.dumps({
            "prs": prs, "merge_outcomes": merge_outcomes or {}, "reviews": reviews or {},
            "branches": branches or {}, "gh_fails": gh_fails or [],
            "gh_garbles": gh_garbles or [], "gh_queue_appends": gh_queue_appends or {}}))
        bin_directory = self.directory / "bin"
        bin_directory.mkdir()
        self.gh = bin_directory / "gh"
        self.gh.write_text(FAKE_GH)
        self.gh.chmod(0o755)
        self.merge_program = bin_directory / "merge.py"
        self.merge_program.write_text(FAKE_MERGE_PROGRAM)
        self.follow_up = bin_directory / "follow-up.py"
        self.follow_up.write_text(FAKE_FOLLOW_UP)
        self.environment = {"FAKE_STATE": str(self.state), "FAKE_QUEUE": str(self.queue)}

    def argv(self, *subcommand):
        return ["--merge-queue-file", str(self.queue), "--merge-batches-directory",
                str(self.batches), "--merge-program-outputs-directory", str(self.outputs),
                "--merge-program", str(self.merge_program), "--follow-up-program",
                str(self.follow_up), "--gh", str(self.gh), *subcommand]

    def run(self, *subcommand, extra_environment=None):
        saved = dict(os.environ)
        os.environ.update(self.environment, **(extra_environment or {}))
        output = io.StringIO()
        try:
            with contextlib.redirect_stdout(output):
                exit_code = program.main(self.argv(*subcommand))
        finally:
            os.environ.clear()
            os.environ.update(saved)
        return exit_code, output.getvalue()

    def queue_text(self):
        return self.queue.read_text()

    def merge_calls(self):
        log = Path(str(self.state) + ".merge-calls")
        return [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []

    def notices(self):
        directory = self.batches / program.MERGE_BATCH_OUTCOME_NOTICES_FOR_MERGE_LANE_2_DIRECTORY_NAME
        return ({path.name: path.read_text() for path in sorted(directory.iterdir())}
                if directory.is_dir() else {})

    def stop_text(self):
        stop_file = self.outputs / STOP_FILE_NAME
        return stop_file.read_text() if stop_file.is_file() else None


def approved(number, head, author="author-seat", hold=""):
    return f"{hold}{number} {head} {QUEUED} {author} (round 1)"


def merging_cases(scratch):
    case = Case(scratch, "merges-in-order",
                [approved(10, A), approved(11, B, hold="HOLD-user-approval "), approved(12, C)],
                {"10": pr(A), "11": pr(B), "12": pr(C)},
                reviews={"10": [merge_account_review(A, REVIEWED),
                                merge_account_review(MOVED, "2026-11-25T11:00:00Z")]})
    exit_code, output = case.run("merge-batch-run-in-queue-order")
    calls = case.merge_calls()
    check("a merge batch merges the waiting lines in order, passes over a held one, and appends "
          "a MERGED line for each",
          exit_code == 0 and [call[0] for call in calls] == ["10", "12"]
          and f"MERGED 10 {'10'.rjust(40, 'e')}\n" in case.queue_text()
          and f"MERGED 12 {'12'.rjust(40, 'e')}\n" in case.queue_text()
          and "MERGED 11" not in case.queue_text() and "DONE: nothing left to merge" in output,
          f"{calls}\n{case.queue_text()}\n{output}")
    check("reviewed-since is the merge account's latest review of the queued nn-head-commit, "
          "not the queued time, and the queued time when there is no such review",
          calls[:1] == [["10", A, REVIEWED]] and calls[1:] == [["12", C, QUEUED]], calls)
    notices = case.notices()
    check("each merge writes a MERGED notice naming the author, with the follow-up request",
          notices.get(f"merged-10-{'10'.rjust(40, 'e')[:12]}.txt", "").startswith(
              f"MERGED 10 {'10'.rjust(40, 'e')} author-seat\n#follow_up_request pull request 10"),
          notices)
    check("a merge that went on leaves no in-progress file",
          not (case.batches / program.MERGE_IN_PROGRESS_FILE_NAME).exists())

    case = Case(scratch, "stacked", [approved(11, B), approved(10, A)],
                {"10": pr(A), "11": pr(B, base="topic-10")},
                merge_outcomes={"10": {"exit": 0, "merged": True, "retargets": ["11"]}},
                branches={"topic-10": [10]})
    exit_code, output = case.run("merge-batch-run-in-queue-order")
    check("a pull request stacked on an open one is passed over, and merges in the next pass "
          "once the one below it merges and it is retargeted to main",
          [call[0] for call in case.merge_calls()] == ["10", "11"]
          and "stacked on topic-10" in output and "HELD 11" not in case.queue_text(),
          f"{case.merge_calls()}\n{output}")

    case = Case(scratch, "base-not-a-pull-request", [approved(10, A)],
                {"10": pr(A, base="gone-branch")})
    case.run("merge-batch-run-in-queue-order")
    check("a base branch that is no open pull request's branch gets a HELD line and notice",
          "HELD 10 base branch gone-branch is not main and is not the branch of exactly one "
          "open pull request" in case.queue_text()
          and case.notices().get("held-10.txt", "").startswith("HELD 10 author author-seat\n")
          and case.merge_calls() == [], case.queue_text())

    case = Case(scratch, "github-states", [approved(10, A), approved(11, B), approved(12, C)],
                {"10": {**pr(A, state="MERGED"), "mergeCommit": {"oid": "f" * 40}},
                 "11": pr(B, state="CLOSED"), "12": pr(MOVED)})
    exit_code, output = case.run("merge-batch-run-in-queue-order")
    check("merged already, closed and moved each get their queue line, and the batch goes on",
          exit_code == 0 and case.merge_calls() == []
          and f"MERGED 10 {'f' * 40} (merged on GitHub outside the merge queue)" in case.queue_text()
          and "HELD 11 closed on GitHub" in case.queue_text()
          and f"HELD 12 nn-head-commit moved to {MOVED}" in case.queue_text(), case.queue_text())

    case = Case(scratch, "refused", [approved(10, A), approved(11, B), approved(12, C)],
                {"10": pr(A), "11": pr(B), "12": pr(C)},
                merge_outcomes={
                    "10": {"exit": 1, "output": "STOP: not merged: mergeStateStatus is DIRTY"},
                    "11": {"exit": 1, "output": "GATE REFUSED (#11): the approval covers x"}})
    case.run("merge-batch-run-in-queue-order")
    check("a DIRTY refusal and any other refusal each get a HELD line, and the batch goes on",
          "HELD 10 conflicts with main (mergeStateStatus DIRTY)" in case.queue_text()
          and "HELD 11 refused: GATE REFUSED (#11): the approval covers x" in case.queue_text()
          and "MERGED 12" in case.queue_text(), case.queue_text())

    case = Case(scratch, "follow-up-fails", [approved(10, A), approved(11, B)],
                {"10": pr(A), "11": pr(B)})
    case.run("merge-batch-run-in-queue-order", extra_environment={"FAKE_FOLLOW_UP_FAILS": "1"})
    notice = next(iter(case.notices().values()), "")
    check("a follow-up program that fails is reported in the MERGED notice, and the batch goes on",
          "The follow-up program exited 1; run it by hand" in notice
          and "MERGED 11" in case.queue_text(), notice)

    case = Case(scratch, "merge-only", [approved(10, A), approved(11, B)],
                {"10": pr(A), "11": pr(B)})
    case.run("merge-batch-run-in-queue-order", "--merge-only", "11")
    check("--merge-only merges the named pull request first, then the rest in order",
          [call[0] for call in case.merge_calls()] == ["11", "10"], case.merge_calls())

    case = Case(scratch, "held-during-a-merge", [approved(10, A), approved(11, B), approved(12, C)],
                {"10": pr(A), "11": pr(B), "12": pr(C)},
                merge_outcomes={"10": {"exit": 0, "merged": True,
                                       "queue_append": [approved(11, B, hold="HOLD-lane ")]}})
    case.run("merge-batch-run-in-queue-order")
    check("a HOLD- line appended while an earlier pull request merges holds that pull request "
          "in the same pass",
          [call[0] for call in case.merge_calls()] == ["10", "12"]
          and "MERGED 11" not in case.queue_text(), f"{case.merge_calls()}\n{case.queue_text()}")

    case = Case(scratch, "merge-only-stacked", [approved(10, A), approved(11, B)],
                {"10": pr(A), "11": pr(B, base="topic-12")}, branches={"topic-12": [12]})
    case.run("merge-batch-run-in-queue-order", "--merge-only", "11")
    stop = case.stop_text() or ""
    check("a --merge-only pull request that is stacked and passed over stops the batch, with "
          "the stop file and a stopped notice, and nothing else merges",
          case.merge_calls() == []
          and "pull request 11, named by --merge-only to merge first, did not merge" in stop
          and "passed over" in stop
          and any(name.startswith("stopped-") for name in case.notices()),
          f"{case.merge_calls()}\n{stop}\n{case.notices()}")

    case = Case(scratch, "merge-only-refused", [approved(10, A), approved(11, B)],
                {"10": pr(A), "11": pr(B)},
                merge_outcomes={"11": {"exit": 1, "output": "GATE REFUSED (#11): the approval covers x"}})
    case.run("merge-batch-run-in-queue-order", "--merge-only", "11")
    stop = case.stop_text() or ""
    check("a --merge-only pull request the gate refuses gets its HELD line, then stops the "
          "batch before any other pull request merges",
          [call[0] for call in case.merge_calls()] == ["11"]
          and "HELD 11 refused: GATE REFUSED (#11)" in case.queue_text()
          and "MERGED 10" not in case.queue_text()
          and "did not merge with a passing after-merge test run" in stop and "HELD 11" in stop,
          f"{case.merge_calls()}\n{case.queue_text()}\n{stop}")

    case = Case(scratch, "merge-only-merged-outside", [approved(10, A), approved(11, B)],
                {"10": pr(A), "11": {**pr(B, state="MERGED"), "mergeCommit": {"oid": "f" * 40}}})
    case.run("merge-batch-run-in-queue-order", "--merge-only", "11")
    stop = case.stop_text() or ""
    check("a --merge-only pull request already merged outside the merge queue stops the batch, "
          "since its after-merge test run was not seen",
          case.merge_calls() == [] and "this program did not see its after-merge test run" in stop,
          f"{case.merge_calls()}\n{stop}")

    case = Case(scratch, "appended-after-the-last-pass", [approved(10, A)],
                {"10": pr(A), "11": pr(B)})
    real_one_pass = program.MergeQueuePullRequestMergeBatchRunner.one_pass
    passes = []

    def one_pass_then_another_seat_appends(self, merge_only):
        appended = real_one_pass(self, merge_only)
        passes.append(appended)
        if len(passes) == 2:
            with open(self.arguments.merge_queue_file, "a") as queue:
                queue.write(approved(11, B) + "\n")
        return appended
    program.MergeQueuePullRequestMergeBatchRunner.one_pass = one_pass_then_another_seat_appends
    try:
        case.run("merge-batch-run-in-queue-order")
    finally:
        program.MergeQueuePullRequestMergeBatchRunner.one_pass = real_one_pass
    check("a line appended after the last pass read the file, before the lock is released, is "
          "merged by another pass",
          [call[0] for call in case.merge_calls()] == ["10", "11"], (passes, case.merge_calls()))

    case = Case(scratch, "another-batch-takes-the-lock", [approved(10, A)],
                {"10": pr(A), "11": pr(B)})
    real_flock = program.fcntl.flock
    flock_calls = []

    def another_batch_takes_it_after_the_release(lock, operation):
        flock_calls.append(operation)
        if operation == fcntl.LOCK_UN:
            with open(case.queue, "a") as queue:
                queue.write(approved(11, B) + "\n")
        if len(flock_calls) > 1 and operation == fcntl.LOCK_EX | fcntl.LOCK_NB:
            raise BlockingIOError
        return real_flock(lock, operation)
    program.fcntl.flock = another_batch_takes_it_after_the_release
    try:
        exit_code, output = case.run("merge-batch-run-in-queue-order")
    finally:
        program.fcntl.flock = real_flock
    check("when another merge batch takes the lock after this one released it, this one exits "
          "0 and leaves the new line to it",
          exit_code == 0 and [call[0] for call in case.merge_calls()] == ["10"]
          and "DONE" not in output, f"{flock_calls}\n{output}")

    case = Case(scratch, "reapproved-while-checked", [approved(10, A)], {"10": pr(MOVED)},
                gh_queue_appends={"pr view 10": [approved(10, MOVED)]})
    exit_code, output = case.run("merge-batch-run-in-queue-order")
    check("a new approved line a lane appends while the old line is checked is not put behind a "
          "HELD line, and is read again at once and merged",
          exit_code == 0 and "HELD 10" not in case.queue_text()
          and case.merge_calls() == [["10", MOVED, QUEUED]] and case.notices().get("held-10.txt") is None,
          f"{case.queue_text()}\n{case.merge_calls()}\n{output}")

    case = Case(scratch, "stacked-before-a-line-appended-meanwhile",
                [approved(11, B), approved(10, A)],
                {"10": pr(A), "11": pr(B, base="topic-10"), "12": pr(C)},
                merge_outcomes={"10": {"exit": 0, "merged": True, "retargets": ["11"],
                                       "queue_append": [approved(12, C)]}},
                branches={"topic-10": [10]})
    case.run("merge-batch-run-in-queue-order")
    check("a stacked pull request passed over is tried again after the merge below it, before a "
          "line appended during that merge",
          [call[0] for call in case.merge_calls()] == ["10", "11", "12"], case.merge_calls())

    case = Case(scratch, "merge-only-refused-then-reapproved", [approved(10, A), approved(11, B)],
                {"10": pr(A), "11": pr(B)},
                merge_outcomes={"11": {"exit": 1, "output": "GATE REFUSED (#11): the approval covers x"}})
    real_held = program.MergeQueuePullRequestMergeBatchRunner.held

    def held_then_a_lane_reapproves(self, number, *rest):
        appended = real_held(self, number, *rest)
        with open(self.arguments.merge_queue_file, "a") as queue:
            queue.write(approved(number, B) + "\n")
        return appended
    program.MergeQueuePullRequestMergeBatchRunner.held = held_then_a_lane_reapproves
    try:
        case.run("merge-batch-run-in-queue-order", "--merge-only", "11")
    finally:
        program.MergeQueuePullRequestMergeBatchRunner.held = real_held
    stop = case.stop_text() or ""
    check("a --merge-only stop names the outcome the merge batch saw, even when a lane appends "
          "a new line for that pull request before the stop",
          "HELD 11 refused: GATE REFUSED (#11)" in stop and "stacked" not in stop, stop)


def stopping_cases(scratch):
    case = Case(scratch, "exit-3", [approved(10, A), approved(11, B)],
                {"10": pr(A), "11": pr(B)},
                merge_outcomes={"10": {"exit": 3, "merged": True,
                                       "output": "FAIL scripts/x-test.py\nSUMMARY: 1 failed"}})
    exit_code, output = case.run("merge-batch-run-in-queue-order")
    stopped = [text for name, text in case.notices().items() if name.startswith("stopped-")]
    check("a merge that exits 3 is recorded MERGED, stops the batch with a STOPPED notice "
          "quoting its FAIL and SUMMARY lines, and merges nothing after it",
          exit_code == 0 and "MERGED 10" in case.queue_text()
          and [call[0] for call in case.merge_calls()] == ["10"]
          and len(stopped) == 1 and stopped[0].startswith(
              "STOPPED pull request 10: the merge program exited 3 and GitHub says MERGED: it "
              "merged, but a step after the merge")
          and "FAIL scripts/x-test.py" in stopped[0] and "SUMMARY: 1 failed" in stopped[0],
          f"{case.queue_text()}\n{stopped}\n{output}")
    check("a merge that exits 3 after GitHub shows it merged puts its merge commit, author and "
          "follow-up request in the STOPPED notice, since resuming never reaches it again",
          stopped and f"Pull request 10 merged as {'10'.rjust(40, 'e')}; its author agent-seat is author-seat." in stopped[0]
          and "#follow_up_request pull request 10" in stopped[0], stopped)
    exit_code, output = case.run("merge-batch-start")
    check("merge-batch-start starts nothing while the stop file exists, quotes it, and names "
          "the newest stopped notice",
          exit_code == 0 and output.startswith("STOPPED: ") and "exited 3" in output
          and "Handle its stopped notice, " in output and "stopped-" in output, output)
    exit_code, output = case.run("merge-batch-start", "--quiet")
    check("with --quiet, a start the stop file prevents prints nothing", output == "", output)

    for name, outcome, says in (
            ("exit-0-not-merged", {"exit": 0, "merged": False}, "exited 0 and GitHub says OPEN"),
            ("exit-1-merged", {"exit": 1, "merged": True}, "exited 1 and GitHub says MERGED"),
            ("exit-2", {"exit": 2}, "exited 2 and GitHub says OPEN"),
            ("exit-4", {"exit": 4}, "exited 4 and GitHub says OPEN")):
        case = Case(scratch, name, [approved(10, A), approved(11, B)], {"10": pr(A), "11": pr(B)},
                    merge_outcomes={"10": outcome})
        case.run("merge-batch-run-in-queue-order")
        check(f"{name}: the batch stops, writes the stop file and a notice, and merges nothing "
              f"after it",
              says in (case.stop_text() or "") and len(case.merge_calls()) == 1
              and any(text.startswith("STOPPED ") for text in case.notices().values())
              and not (case.batches / program.MERGE_IN_PROGRESS_FILE_NAME).exists(),
              f"{case.stop_text()}\n{case.notices()}")

    case = Case(scratch, "github-read-fails", [approved(10, A)], {"10": pr(A)},
                gh_fails=["pr view 10"])
    exit_code, output = case.run("merge-batch-run-in-queue-order")
    check("a GitHub read that fails stops the batch, quoting gh's error, and exits 1",
          exit_code == 1 and "gh pr view 10 exited 1: HTTP 502: bad gateway" in (case.stop_text() or ""),
          f"exit {exit_code}\n{case.stop_text()}")

    case = Case(scratch, "github-read-not-json", [approved(10, A)], {"10": pr(A)},
                gh_garbles=["pr view 10"])
    case.run("merge-batch-run-in-queue-order")
    check("a GitHub read that prints what is not JSON stops the batch, quoting it",
          "printed what is not JSON: '<html>502</html>" in (case.stop_text() or ""),
          case.stop_text())

    case = Case(scratch, "queue-unwritable", [approved(10, A)], {"10": pr(A)})
    case.queue.chmod(0o444)
    exit_code, output = case.run("merge-batch-run-in-queue-order")
    check("a merge queue file that cannot be appended to stops the batch, naming the error, "
          "and exits 1",
          exit_code == 1 and "Permission denied" in (case.stop_text() or ""),
          f"exit {exit_code}\n{case.stop_text()}")

    case = Case(scratch, "branch-list-fails", [approved(10, A)], {"10": pr(A, base="topic")},
                gh_fails=["pr list"])
    case.run("merge-batch-run-in-queue-order")
    check("a failed read of the base branch's pull requests stops the batch",
          "gh pr list --repo exited 1" in (case.stop_text() or ""), case.stop_text())

    case = Case(scratch, "unknown-line", [approved(10, A), "SOMETHING 10 odd"], {"10": pr(A)})
    exit_code, output = case.run("merge-batch-run-in-queue-order")
    check("a line of no known kind stops the batch, naming its number, and exits 0, since the "
          "file was read",
          exit_code == 0 and "line 2 of " in (case.stop_text() or "")
          and "'SOMETHING 10 odd'" in case.stop_text() and case.merge_calls() == [],
          case.stop_text())

    case = Case(scratch, "stop-file-before-the-pass", [approved(10, A)], {"10": pr(A)})
    (case.outputs / STOP_FILE_NAME).write_text("the GHI-MD edit merge job's merge exited 3\n")
    exit_code, output = case.run("merge-batch-run-in-queue-order")
    stopped = [text for name, text in case.notices().items() if name.startswith("stopped-")]
    check("a stop file written by another caller ends the batch before its next merge, with a "
          "STOPPED notice quoting it, and leaves the stop file as it was",
          exit_code == 0 and case.merge_calls() == [] and len(stopped) == 1
          and "written outside this merge batch, says: the GHI-MD edit merge job's merge exited 3"
          in stopped[0]
          and case.stop_text() == "the GHI-MD edit merge job's merge exited 3\n"
          and "the stop file exists, so the merge batch ends" in output,
          f"{output}\n{case.notices()}")

    case = Case(scratch, "merge-only-not-waiting", [approved(10, A)], {"10": pr(A)})
    case.run("merge-batch-run-in-queue-order", "--merge-only", "99")
    check("--merge-only naming a pull request that is not waiting stops the batch",
          "pull request 99, named by --merge-only, is not waiting" in (case.stop_text() or ""),
          case.stop_text())

    case = Case(scratch, "notice-unwritable", [approved(10, A)], {"10": pr(A)})
    case.batches.mkdir()
    (case.batches / program.MERGE_BATCH_OUTCOME_NOTICES_FOR_MERGE_LANE_2_DIRECTORY_NAME).write_text("a file, not a directory\n")
    exit_code, output = case.run("merge-batch-run-in-queue-order")
    check("a notice that cannot be written stops the batch, the log says why, and it exits 1",
          exit_code == 1 and "could not write the notice" in output
          and "could not write the notice" in (case.stop_text() or ""),
          f"exit {exit_code}\n{output}\n{case.stop_text()}")

    case = Case(scratch, "stop-file-unwritable", [approved(10, A)], {"10": pr(A)},
                gh_fails=["pr view 10"])
    shutil.rmtree(case.outputs)
    case.outputs.write_text("a file, not a directory\n")
    exit_code, output = case.run("merge-batch-run-in-queue-order")
    stopped = [text for name, text in case.notices().items() if name.startswith("stopped-")]
    check("a stop file that cannot be written is said in the notice and the log, with what to do",
          stopped and "could not be written" in stopped[0] and "append a HOLD- line" in output,
          f"{stopped}\n{output}")

    case = Case(scratch, "stop-file-unwritable-in-progress-kept", [approved(10, A)], {"10": pr(A)})
    case.batches.mkdir()
    in_progress = case.batches / program.MERGE_IN_PROGRESS_FILE_NAME
    in_progress.write_text("pull request 9, started 2026-11-25T10:00:00Z\n")
    shutil.rmtree(case.outputs)
    case.outputs.write_text("a file, not a directory\n")
    exit_code, output = case.run("merge-batch-start")
    check("when the stop file cannot be written, the in-progress file is kept, so the next start "
          "still finds that the batch died mid-merge and starts nothing",
          output.startswith("DIED MID-MERGE: ") and in_progress.exists()
          and case.run("merge-batch-start")[1].startswith("DIED MID-MERGE: ")
          and case.merge_calls() == [], f"{output}\n{in_progress.exists()}")


def next_merge_decision_cases(scratch):
    case = Case(scratch, "next-merge-decision", [approved(10, A)], {"10": pr(A)})
    queue = program.MergeQueuePullRequestMergeBatchRunner(program.parse_arguments(case.argv("merge-batch-list-waiting")))
    check("the next merge starts when there is no stop file and no merge program holds its lock",
          queue.next_merge_may_start()[0] == program.NEXT_MERGE_STARTS)
    lock_path = case.outputs / program.merge_program.MERGE_PROGRAM_RUN_LOCK_FILE_NAME
    with open(lock_path, "a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        held = queue.next_merge_may_start()
    check("the next merge waits while a merge program holds its lock, so main's after-merge "
          "test run is still running",
          held[0] == program.NEXT_MERGE_WAITS and "still running" in held[1], held)
    check("the next merge starts once that lock is free again",
          queue.next_merge_may_start()[0] == program.NEXT_MERGE_STARTS)
    (case.outputs / STOP_FILE_NAME).write_text("pull request 9's merge program exited 3\n")
    stopped = queue.next_merge_may_start()
    check("the next merge stops while the stop file exists, quoting it",
          stopped == (program.NEXT_MERGE_STOPS, "pull request 9's merge program exited 3"),
          stopped)

    case = Case(scratch, "waits-then-merges", [approved(10, A)], {"10": pr(A)})
    lock_path = case.outputs / program.merge_program.MERGE_PROGRAM_RUN_LOCK_FILE_NAME
    holder = open(lock_path, "a")
    fcntl.flock(holder, fcntl.LOCK_EX)
    waits = []

    def wait_then_release(seconds):
        waits.append(seconds)
        fcntl.flock(holder, fcntl.LOCK_UN)
    queue = program.MergeQueuePullRequestMergeBatchRunner(
        program.parse_arguments(case.argv("merge-batch-run-in-queue-order")),
        wait=wait_then_release)
    saved = dict(os.environ)
    os.environ.update(case.environment)
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            queue.run_in_queue_order(None)
    finally:
        os.environ.clear()
        os.environ.update(saved)
        holder.close()
    check("a merge batch waits while another merge program's test run holds the lock, then "
          "merges",
          waits == [program.SECONDS_BETWEEN_NEXT_MERGE_MAY_START_CHECKS]
          and [call[0] for call in case.merge_calls()] == ["10"], (waits, case.merge_calls()))


def starting_cases(scratch):
    case = Case(scratch, "died-mid-merge", [approved(10, A)], {"10": pr(A)})
    case.batches.mkdir()
    (case.batches / program.MERGE_IN_PROGRESS_FILE_NAME).write_text(
        "pull request 10, started 2026-11-25T10:00:00Z\n")
    exit_code, output = case.run("merge-batch-start")
    first_notices = case.notices()
    exit_code_again, output_again = case.run("merge-batch-start")
    check("a start that finds the in-progress file with the lock free writes the stop file and "
          "one notice, and starts nothing; a second start writes no second notice",
          exit_code == 0 and output.startswith("DIED MID-MERGE: ") and len(first_notices) == 1
          and "main is untested" in (case.stop_text() or "")
          and output_again.startswith("STOPPED: ") and case.notices() == first_notices
          and case.merge_calls() == [], f"{output}\n{output_again}\n{case.notices()}")

    case = Case(scratch, "run-directly-after-a-death", [approved(10, A)], {"10": pr(A)})
    case.batches.mkdir()
    (case.batches / program.MERGE_IN_PROGRESS_FILE_NAME).write_text(
        "pull request 9, started 2026-11-25T10:00:00Z\n")
    exit_code, output = case.run("merge-batch-run-in-queue-order")
    check("merge-batch-run-in-queue-order run directly after a batch died mid-merge merges "
          "nothing and writes the stop file and a stopped notice",
          exit_code == 0 and case.merge_calls() == [] and "main is untested" in (case.stop_text() or "")
          and any(name.startswith("stopped-") for name in case.notices()), f"{output}\n{case.notices()}")

    case = Case(scratch, "lock-held-and-stopped", [approved(10, A)], {"10": pr(A)})
    case.batches.mkdir()
    (case.outputs / STOP_FILE_NAME).write_text("pull request 9's merge program exited 3\n")
    with open(case.batches / program.MERGE_BATCH_LOCK_FILE_NAME, "a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        exit_code, output = case.run("merge-batch-start")
    check("a start while a merge batch holds the lock and the stop file exists says STOPPED, "
          "not ALREADY RUNNING",
          exit_code == 0 and output.startswith("STOPPED: ") and "exited 3" in output, output)

    case = Case(scratch, "lock-held", [approved(10, A)], {"10": pr(A)})
    case.batches.mkdir()
    with open(case.batches / program.MERGE_BATCH_LOCK_FILE_NAME, "a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        start_code, start_output = case.run("merge-batch-start")
        run_code, run_output = case.run("merge-batch-run-in-queue-order")
        resume_code, resume_output = case.run("merge-batch-resume")
    check("while a merge batch holds the lock, a start says ALREADY RUNNING, a second batch "
          "exits 0 merging nothing, and resume is refused",
          start_code == 0 and start_output.startswith("ALREADY RUNNING")
          and run_code == 0 and case.merge_calls() == []
          and resume_code == 2 and resume_output.startswith("REFUSED: a merge batch is running"),
          f"{start_output}\n{run_output}\n{resume_output}")

    case = Case(scratch, "resume-merge-only-not-waiting", [approved(10, A)], {"10": pr(A)})
    (case.outputs / STOP_FILE_NAME).write_text("stopped\n")
    exit_code, output = case.run("merge-batch-resume", "--merge-only", "99")
    check("resume --merge-only naming a pull request that is not waiting is refused, and the "
          "stop file is left",
          exit_code == 2 and output.startswith("REFUSED: pull request 99 is not waiting")
          and case.stop_text() == "stopped\n", output)

    case = Case(scratch, "start-cannot-start", [approved(10, A)], {"10": pr(A)})
    real_popen = program.subprocess.Popen

    def popen_fails(*arguments, **keywords):
        raise OSError("[Errno 12] Cannot allocate memory")
    program.subprocess.Popen = popen_fails
    try:
        exit_code, output = case.run("merge-batch-start")
    finally:
        program.subprocess.Popen = real_popen
    check("a merge batch that cannot be started is NOT STARTED, exit 1",
          exit_code == 1 and output.startswith("NOT STARTED: ") and "Cannot allocate" in output,
          output)

    case = Case(scratch, "start-for-real", [approved(10, A)], {"10": pr(A)})
    (case.outputs / STOP_FILE_NAME).write_text("stopped\n")
    saved = dict(os.environ)
    os.environ.update(case.environment)
    try:
        exit_code, output = case.run("merge-batch-resume")
        log = case.batches / program.MERGE_BATCH_LOG_FILE_NAME
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline and "DONE" not in (log.read_text() if log.exists()
                                                             else ""):
            time.sleep(0.2)
    finally:
        os.environ.clear()
        os.environ.update(saved)
    check("resume removes the stop file and starts a merge batch in the background, which "
          "merges and logs DONE",
          exit_code == 0 and output.startswith("STARTED: ") and case.stop_text() is None
          and "MERGED 10" in case.queue_text() and "DONE" in log.read_text(),
          f"{output}\n{log.read_text() if log.exists() else ''}")

    case = Case(scratch, "list-waiting", [approved(10, A), approved(11, B, hold="HOLD-x ")],
                {"10": pr(A), "11": pr(B)})
    exit_code, output = case.run("merge-batch-list-waiting")
    check("merge-batch-list-waiting prints each waiting pull request, and merges nothing",
          exit_code == 0 and output.startswith("10 OPEN base main queued aaaaaaaaaaaa")
          and "11 " not in output and case.merge_calls() == [], output)

    case = Case(scratch, "queue-unreadable", [], {})
    case.queue.unlink()
    exit_code, output = case.run("merge-batch-list-waiting")
    check("a merge queue file that cannot be read is FAILED, exit 1",
          exit_code == 1 and output.startswith("FAILED: "), output)


def main():
    scratch = Path(tempfile.mkdtemp(prefix="merge-queue-test-")).resolve()
    try:
        merging_cases(scratch)
        stopping_cases(scratch)
        next_merge_decision_cases(scratch)
        starting_cases(scratch)
    finally:
        shutil.rmtree(scratch, ignore_errors=True)
    if failures:
        print(f"\n{len(failures)} case(s) failed")
        return 1
    print("\nall cases passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
