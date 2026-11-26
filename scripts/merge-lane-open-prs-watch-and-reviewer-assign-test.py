#!/usr/bin/env python3
"""Tests for merge-lane-open-prs-watch-and-reviewer-assign.py.

Run: python3 scripts/merge-lane-open-prs-watch-and-reviewer-assign-test.py
Prints one line per case and exits non-zero if any case fails.

No case reaches GitHub. The subprocess cases put a fake `gh` first on the
watcher's PATH: a small script that answers from a control file the test
rewrites between phases, records the GH_TOKEN it was handed, and logs every
call. That fake is what makes the interesting properties testable at all —
a failed query, a query that leaks the token into its own stderr, a
response that is HTTP-fine but GraphQL-broken — and it exercises the real
`gh` invocation path rather than a seam added for the tests. The token the
fixture holds is a string invented here, not a credential.

A reader thread drains the watcher's stdout as it flows, which is also what
proves the flushing: every "a line appears mid-run" wait would hang on a
buffered stdout.

Synchronization without sleeps: the fake `gh` appends to a call log, so a
test can wait for the Nth poll rather than guessing a duration — which is
how "no event for an unchanged poll" is checked (polls demonstrably
happened and produced nothing) and how "the blind line fires once, not once
per failed poll" is checked.

The control file is written temp-then-rename throughout: at a 0.05s poll
interval the fake would otherwise read a half-written file and the suite
would flake.
"""

import contextlib
import importlib.util
import io
import json
import os
import re
import stat
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

WATCH_SCRIPT = Path(__file__).with_name("merge-lane-open-prs-watch-and-reviewer-assign.py")

_spec = importlib.util.spec_from_file_location("watch_open_pull_requests",
                                               WATCH_SCRIPT)
watcher_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(watcher_module)

# Invented here, never a credential: long enough to be a plausible token
# (the program refuses shorter ones) and distinctive enough that a leak
# into any output stream is unmistakable.
FIXTURE_TOKEN = "fixture-token-never-a-real-credential-0123456789"

CONTROL_DIRECTORY_VARIABLE = "WATCH_OPEN_PULL_REQUESTS_TEST_CONTROL_DIR"

# Every wait returns as soon as its event happens, so this limit only stops a
# wait whose event never comes. Each poll starts a Python process for the fake
# gh, which takes seconds on a busy ned-box: 10 s failed a correct watcher
# there. 60 s keeps a total failure, every wait timing out, inside the
# runner's 600 s suite limit only because wait_for and wait_for_calls give up
# when the watcher has exited.
EVENT_WAIT_BACKSTOP_SECONDS = 60.0

# The fake gh. It answers from control.json (one file, so a phase change is
# atomic), records the token it was handed, and logs each call. A call
# carrying a `cursor=` argument answers from control-next-page.json instead,
# which is how the pagination case is driven.
FAKE_GH_SOURCE = f'''#!/usr/bin/env python3
import json, os, pathlib, sys

control = pathlib.Path(os.environ["{CONTROL_DIRECTORY_VARIABLE}"])
(control / "token-seen.txt").write_text(os.environ.get("GH_TOKEN", "<unset>"),
                                        encoding="utf-8")
arguments = " ".join(sys.argv[1:])
with (control / "calls.log").open("a", encoding="utf-8") as handle:
    handle.write(("page2" if "cursor=" in arguments else "page1") + "\\n")
name = "control-next-page.json" if "cursor=" in arguments else "control.json"
answer = json.loads((control / name).read_text(encoding="utf-8"))
sys.stdout.write(answer.get("stdout", ""))
sys.stderr.write(answer.get("stderr", ""))
sys.exit(answer.get("exit_code", 0))
'''

failures = []


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


def pull_request_node(number, head_sha, title="a title", draft=False,
                      author="nedlern"):
    return {"number": number, "title": title, "isDraft": draft,
            "headRefOid": head_sha, "author": {"login": author},
            "createdAt": "2026-11-24T00:00:00Z", "baseRefName": "main",
            "headRefName": f"branch-{number}", "reviews": {"nodes": []},
            "macClaudeReviews": {"nodes": []}}


# Every number the event cases use has a line, so they raise no REVIEW-ASSIGNED line; the default
# file is merge-lane-2's real one.
EVERY_PULL_REQUEST_ASSIGNED_DIRECTORY = tempfile.TemporaryDirectory()
EVERY_PULL_REQUEST_ASSIGNED_FILE = (Path(EVERY_PULL_REQUEST_ASSIGNED_DIRECTORY.name)
                                    / "every-pull-request-assigned.txt")
EVERY_PULL_REQUEST_ASSIGNED_FILE.write_text(
    "".join(f"{number} merge-lane-1\n" for number in range(1, 1000)), encoding="utf-8")


def graphql_body(nodes, has_next_page=False, end_cursor=None):
    return json.dumps({"data": {"repository": {"pullRequests": {
        "nodes": nodes,
        "pageInfo": {"hasNextPage": has_next_page, "endCursor": end_cursor}}}}})


class FakeGitHubCommand:
    """The fake `gh` on disk, plus the control file the tests rewrite."""

    def __init__(self, directory: Path):
        self.directory = directory
        self.binary_directory = directory / "bin"
        self.binary_directory.mkdir(parents=True)
        gh_path = self.binary_directory / "gh"
        gh_path.write_text(FAKE_GH_SOURCE, encoding="utf-8")
        gh_path.chmod(0o755)
        self.answer(graphql_body([]))
        self.answer(graphql_body([]), name="control-next-page.json")

    def answer(self, stdout="", exit_code=0, stderr="",
               name="control.json"):
        """Set what the fake `gh` says next — temp-then-rename, so a poll
        landing mid-write never reads half a file."""
        payload = json.dumps({"stdout": stdout, "exit_code": exit_code,
                              "stderr": stderr})
        temporary = self.directory / (name + ".partial")
        temporary.write_text(payload, encoding="utf-8")
        temporary.replace(self.directory / name)

    def call_count(self):
        try:
            return len((self.directory / "calls.log")
                       .read_text(encoding="utf-8").splitlines())
        except OSError:
            return 0

    def token_seen(self):
        try:
            return (self.directory / "token-seen.txt").read_text(encoding="utf-8")
        except OSError:
            return None

    def environment(self):
        return {**os.environ,
                "PATH": f"{self.binary_directory}{os.pathsep}{os.environ['PATH']}",
                CONTROL_DIRECTORY_VARIABLE: str(self.directory),
                "PYTHONIOENCODING": "utf-8"}


class WatcherProcess:
    """The watcher as a subprocess, both its streams drained by threads."""

    def __init__(self, *flags, environment=None, token_file=None,
                 needs_a_look_directory=None):
        self.lines = []
        self.error_lines = []
        # The default is merge-lane-2's real notices directory, whose files would be events here.
        if needs_a_look_directory is None:
            needs_a_look_directory = Path(tempfile.gettempdir()) / "no-such-needs-a-look-directory-for-watcher-tests"
        self.process = subprocess.Popen(
            [sys.executable, str(WATCH_SCRIPT),
             "--poll-seconds", "0.05",
             "--token-file", str(token_file),
             "--needs-a-look-directory", str(needs_a_look_directory),
             "--merge-lane-pr-review-assignments-file", str(EVERY_PULL_REQUEST_ASSIGNED_FILE),
             *flags],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8", env=environment)
        self._threads = [
            threading.Thread(target=self._drain, args=(self.process.stdout,
                                                       self.lines), daemon=True),
            threading.Thread(target=self._drain, args=(self.process.stderr,
                                                       self.error_lines),
                             daemon=True)]
        for thread in self._threads:
            thread.start()

    @staticmethod
    def _drain(stream, sink):
        for line in stream:
            sink.append(line.rstrip("\n"))

    def wait_for(self, fragment, timeout=EVENT_WAIT_BACKSTOP_SECONDS):
        """True once some stdout line contains the fragment; False on timeout,
        or once the watcher has exited and its stdout is drained without it."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if any(fragment in line for line in self.lines):
                return True
            if self.process.poll() is not None and not self._threads[0].is_alive():
                return any(fragment in line for line in self.lines)
            time.sleep(0.02)
        return False

    def count(self, fragment):
        return sum(1 for line in self.lines if fragment in line)

    def stop(self):
        self.process.terminate()
        try:
            self.process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait()
        for thread in self._threads:
            thread.join(timeout=2)
        return list(self.lines)


def wait_for_calls(fake_gh, wanted, watcher, timeout=EVENT_WAIT_BACKSTOP_SECONDS):
    """Block until the fake `gh` has been called `wanted` times, and CHECK it.

    Gives up early once the watcher process has exited, since no more calls
    can come.

    This used to return a boolean that every one of its call sites discarded,
    which made the polls it waits for unproven. The damage was not theoretical:
    the cases that read "polls that change nothing produce no further lines"
    passed vacuously, because zero polls also produce no further lines. A fake
    that was never invoked — a broken control-directory variable, a hung child
    — would have timed out here silently and left the suite reporting success
    for a watcher it never ran.

    So the wait now records a failure of its own when it times out. Waiting for
    a count and never checking it is the same defect this whole program exists
    to prevent, one level up: a signal whose absence is indistinguishable from
    the quiet everything-is-fine case.
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if fake_gh.call_count() >= wanted:
            return True
        if watcher.process.poll() is not None:
            break
        time.sleep(0.02)
    if fake_gh.call_count() >= wanted:
        return True
    check(f"the fake gh was called at least {wanted} time(s) within {timeout:g}s, "
          "while the watcher ran "
          "— everything asserted after this point depends on those polls",
          False, f"call_count={fake_gh.call_count()}")
    return False


def run_unit_cases():
    # ------------------------------------------------------------------
    # The event key is (number, head sha, is_draft) and nothing else.
    # ------------------------------------------------------------------
    events_for_poll = watcher_module.events_for_poll
    by_number = watcher_module.pull_requests_by_number

    def state(head_sha="aaaaaaaaaaaa", is_draft=False, title="t",
              author="nedlern"):
        return [{"number": 7, "head_sha": head_sha, "title": title,
                 "is_draft": is_draft, "author": author}]

    unchanged = state()
    retitled = state(title="EDITED", author="someone-else")
    moved = state(head_sha="bbbbbbbbbbbb")
    draft = state(is_draft=True)
    draft_moved = state(head_sha="bbbbbbbbbbbb", is_draft=True)

    check("a pull request not seen before is OPENED",
          events_for_poll({}, unchanged) == [
              "PR #7 OPENED aaaaaaaa nedlern: t"],
          str(events_for_poll({}, unchanged)))
    check("the same head sha again is not an event",
          events_for_poll(by_number(unchanged), unchanged) == [], "")
    check("a title or author change alone is not an event",
          events_for_poll(by_number(unchanged), retitled) == [],
          str(events_for_poll(by_number(unchanged), retitled)))
    check("a changed head sha is NEW-HEAD",
          events_for_poll(by_number(unchanged), moved) == [
              "PR #7 NEW-HEAD bbbbbbbb nedlern: t"],
          str(events_for_poll(by_number(unchanged), moved)))
    check("a draft not seen before raises no event",
          events_for_poll({}, draft) == [], str(events_for_poll({}, draft)))
    check("a new head commit on a draft raises no event",
          events_for_poll(by_number(draft), draft_moved) == [],
          str(events_for_poll(by_number(draft), draft_moved)))
    check("a draft marked ready is one READY line",
          events_for_poll(by_number(draft), unchanged) == [
              "PR #7 READY aaaaaaaa nedlern: t"],
          str(events_for_poll(by_number(draft), unchanged)))
    check("a draft marked ready with a moved head is one READY line, "
          "carrying the current head",
          events_for_poll(by_number(draft), moved) == [
              "PR #7 READY bbbbbbbb nedlern: t"],
          str(events_for_poll(by_number(draft), moved)))
    check("a pull request turned back into a draft raises no event",
          events_for_poll(by_number(unchanged), draft) == [],
          str(events_for_poll(by_number(unchanged), draft)))
    baseline_with_draft = watcher_module.baseline_line(
        "o/n", 60, [unchanged[0], {**draft[0], "number": 8}], False)
    check("the baseline line lists a draft apart, as not to be reviewed",
          "1 open at baseline: #7 " in baseline_with_draft
          and "1 draft(s), not to be reviewed until marked ready, which "
              "raises READY: #8" in baseline_with_draft,
          baseline_with_draft)

    # ------------------------------------------------------------------
    # Redaction: every printed line goes through it, so it must replace
    # the token wherever it sits in a line.
    # ------------------------------------------------------------------
    saved_secrets = list(watcher_module.SECRETS_TO_REDACT)
    try:
        watcher_module.SECRETS_TO_REDACT[:] = [FIXTURE_TOKEN]
        redacted = watcher_module.redact_secrets(
            f"gh said: Authorization: Bearer {FIXTURE_TOKEN} (twice: "
            f"{FIXTURE_TOKEN})")
        check("redaction replaces every occurrence of the token",
              FIXTURE_TOKEN not in redacted and redacted.count("[REDACTED]") == 2,
              redacted)
    finally:
        watcher_module.SECRETS_TO_REDACT[:] = saved_secrets

    # ------------------------------------------------------------------
    # A node that is not the shape the query asked for fails the poll,
    # rather than being dropped — a dropped pull request would be
    # reported as OPENED again at the next poll.
    # ------------------------------------------------------------------
    from_node = watcher_module.pull_request_from_node
    check("pull_request_from_node reports a missing head sha as a reason",
          from_node({"number": 3, "title": "t"})[0] is None
          and "head commit sha" in from_node({"number": 3, "title": "t"})[1],
          str(from_node({"number": 3, "title": "t"})))
    check("pull_request_from_node reports a node that is not an object",
          from_node([1, 2]) == (None, "a pull request came back as JSON that is not an object"),
          str(from_node([1, 2])))

    # The case above tests the HELPER. The property that matters is the
    # CALLER's: fetch_open_pull_requests must return the failure rather than
    # skip the node. Nothing asserted that until now, and the gap was not
    # cosmetic — changing the caller's `return None, reason` to `continue`
    # left the entire suite passing, while producing exactly the behaviour the
    # program's docstring calls wrong: the dropped pull request would be
    # re-reported as OPENED at every poll, forever.
    class FakeCompletedProcess:
        def __init__(self, stdout):
            self.returncode = 0
            self.stdout = stdout
            self.stderr = ""

    saved_run_gh = watcher_module.run_gh
    try:
        watcher_module.run_gh = lambda *_a, **_k: FakeCompletedProcess(
            graphql_body([pull_request_node(3, "c" * 12),
                          {"number": 4, "title": "malformed"}]))
        fetched, reason = watcher_module.fetch_open_pull_requests("o/n", "tok")
        check("one malformed node fails the whole poll, dropping nothing",
              fetched is None and reason is not None and "head commit sha" in reason,
              f"fetched={fetched!r} reason={reason!r}")

        # Proves the harness above can succeed, so the case before it is a
        # real refusal rather than a fake that never worked.
        watcher_module.run_gh = lambda *_a, **_k: FakeCompletedProcess(
            graphql_body([pull_request_node(3, "c" * 12)]))
        fetched, reason = watcher_module.fetch_open_pull_requests("o/n", "tok")
        check("the same harness with only well-formed nodes returns them",
              reason is None and fetched is not None and len(fetched) == 1
              and fetched[0]["number"] == 3,
              f"fetched={fetched!r} reason={reason!r}")
    finally:
        watcher_module.run_gh = saved_run_gh
    check("a deleted author becomes (unknown), not a crash",
          from_node(pull_request_node(3, "cccccccccccc"))[0] is not None
          and from_node({**pull_request_node(3, "c" * 12),
                         "author": None})[0]["author"] == "(unknown)",
          str(from_node({**pull_request_node(3, "c" * 12), "author": None})))
    authored = {**pull_request_node(3, "c" * 12),
                "commits": {"nodes": [{"commit": {"author": {"name": "merge-lane-1"}}}]}}
    check("pull_request_from_node reads the first commit's author name, and None when GitHub "
          "gives no commits",
          from_node(authored)[0]["first_commit_author_name"] == "merge-lane-1"
          and from_node(pull_request_node(3, "c" * 12))[0]["first_commit_author_name"] is None,
          str(from_node(authored)))
    for field in ("createdAt", "baseRefName", "headRefName"):
        check(f"pull_request_from_node reports a missing {field} as a reason",
              from_node({**pull_request_node(3, "c" * 12), field: None})
              == (None, f"pull request #3 came back with no {field}"),
              str(from_node({**pull_request_node(3, "c" * 12), field: None})))
    for label, reviews in [("no reviews field", None),
                           ("a review with no state", {"nodes": [{"body": "APPROVE"}]})]:
        check(f"pull_request_from_node reports {label} as a reason, so no verdict is misread",
              from_node({**pull_request_node(3, "c" * 12), "reviews": reviews})
              == (None, "pull request #3 came back with no usable list of reviews"),
              str(from_node({**pull_request_node(3, "c" * 12), "reviews": reviews})))
    check("a null list of mac-claude's reviews is no reason to refuse a pull request another "
          "account opened, since those reviews decide nothing there",
          from_node({**pull_request_node(3, "c" * 12), "macClaudeReviews": None})[0] is not None,
          str(from_node({**pull_request_node(3, "c" * 12), "macClaudeReviews": None})))
    own_node = {**pull_request_node(3, "c" * 12),
                "author": {"login": watcher_module.fix_round.MERGE_LANE_2_REVIEWER_LOGIN},
                "macClaudeReviews": None}
    check("a null list of mac-claude's reviews is refused on a pull request ned-review-merge "
          "opened, where mac-claude's approval is the verdict",
          from_node(own_node)
          == (None, "pull request #3 came back with no usable list of macClaudeReviews"),
          str(from_node(own_node)))

    # ------------------------------------------------------------------
    # Titles are folded then truncated, so a multi-line title cannot
    # break the one-line-per-event contract.
    # ------------------------------------------------------------------
    folded = watcher_module.event_line(
        {"number": 9, "head_sha": "d" * 40, "title": "first\nsecond",
         "is_draft": False, "author": "nedlern"}, "OPENED")
    check("a newline in a title becomes ' ¶ ', keeping one line per event",
          folded == "PR #9 OPENED dddddddd nedlern: first ¶ second", folded)
    long_title = "T" * (watcher_module.TITLE_SNIPPET_CHARS + 50)
    long_line = watcher_module.event_line(
        {"number": 9, "head_sha": "d" * 40, "title": long_title,
         "is_draft": False, "author": "nedlern"}, "OPENED")
    check("a long title is truncated to the documented length",
          long_line.endswith("T" * watcher_module.TITLE_SNIPPET_CHARS)
          and "T" * (watcher_module.TITLE_SNIPPET_CHARS + 1) not in long_line,
          str(len(long_line)))

    # ------------------------------------------------------------------
    # The token file: refused at startup rather than half-trusted.
    # ------------------------------------------------------------------
    with tempfile.TemporaryDirectory() as scratch:
        short_token_file = Path(scratch) / "short.token"
        short_token_file.write_text("abc\n", encoding="utf-8")
        token, reason = watcher_module.read_token(short_token_file)
        check("a too-short token file is refused (it would corrupt redaction)",
              token is None and "not a GitHub token" in reason, str(reason))
        missing = Path(scratch) / "absent.token"
        token, reason = watcher_module.read_token(missing)
        check("a missing token file is refused, and the reason names the path",
              token is None and str(missing) in reason, str(reason))
        good = Path(scratch) / "good.token"
        good.write_text(FIXTURE_TOKEN + "\n", encoding="utf-8")
        check("the token is read with its trailing newline stripped",
              watcher_module.read_token(good) == (FIXTURE_TOKEN, None),
              str(watcher_module.read_token(good)))


def run_needs_a_look_unit_cases():
    events = watcher_module.needs_a_look_events
    with tempfile.TemporaryDirectory() as scratch:
        scratch = Path(scratch)
        directory = scratch / "needs-a-look"
        state = {}
        check("a notices directory that does not exist yet raises nothing",
              events(directory, state) == [], str(state))

        directory.mkdir()
        (directory / "pr9-bbbbbbbbbbbb.txt").write_text(
            "GHI-MD edit pull request 9 needs a look: https://x/pull/9\nTitle: t\n",
            encoding="utf-8")
        (directory / "handled").mkdir()
        (directory / "handled" / "pr8-aaaaaaaaaaaa.txt").write_text("old\n", encoding="utf-8")
        (directory / "dangling.txt").symlink_to(scratch / "no-such-file")
        lines = events(directory, state)
        handled = directory / "handled"
        check("a notice present at the first listing is one NEEDS A LOOK line with its first "
              "line and the move that marks it handled; handled/ and a dangling link raise nothing",
              lines == [f"NEEDS A LOOK pr9-bbbbbbbbbbbb.txt: GHI-MD edit pull request 9 needs a "
                        f"look: https://x/pull/9 -- read {directory / 'pr9-bbbbbbbbbbbb.txt'}, "
                        f"then at once, before acting on it, move it, or each restart of this "
                        f"watcher reports it again first: mkdir -p {handled} && mv "
                        f"{directory / 'pr9-bbbbbbbbbbbb.txt'} {handled}/"], "\n".join(lines))
        check("the same notice, unchanged, is not reported again",
              events(directory, state) == [], str(state))

        stopped = directory / "invocation-stopped.txt"
        stopped.write_text("stopped once\n", encoding="utf-8")
        os.utime(stopped, ns=(1, 1))
        first = events(directory, state)
        stopped.write_text("stopped again\n", encoding="utf-8")
        os.utime(stopped, ns=(2, 2))
        second = events(directory, state)
        check("a notice replaced by a later write is reported again",
              len(first) == 1 and "stopped once" in first[0]
              and len(second) == 1 and "stopped again" in second[0], f"{first}\n{second}")

        notice = directory / "pr9-bbbbbbbbbbbb.txt"
        saved_status = notice.stat()
        notice.rename(handled / notice.name)
        events(directory, state)
        (handled / notice.name).rename(notice)
        os.utime(notice, ns=(saved_status.st_atime_ns, saved_status.st_mtime_ns + 1))
        check("a notice that leaves the directory and comes back is reported again",
              len(events(directory, state)) == 1, str(state))
        saved_status = notice.stat()
        notice.rename(handled / notice.name)
        events(directory, state)
        (handled / notice.name).rename(notice)
        os.utime(notice, ns=(saved_status.st_atime_ns, saved_status.st_mtime_ns))
        check("a notice that a poll found missing is reported again when it comes back with "
              "the same modification time",
              len(events(directory, state)) == 1, str(state))

        looping = directory / "looping.txt"
        looping.symlink_to(looping)
        first = events(directory, state)
        second = events(directory, state)
        looping.unlink()
        check("an entry whose status cannot be read, other than a dangling link, is one NEEDS A "
              "LOOK line naming the error, not repeated while it stays so",
              first == [f"NEEDS A LOOK looping.txt: (could not read its status: Too many levels "
                        f"of symbolic links) -- look at {looping}"]
              and second == [], f"{first}\n{second}")

        empty = directory / "empty.txt"
        empty.write_text("", encoding="utf-8")
        check("an empty notice is reported as an empty file",
              any("NEEDS A LOOK empty.txt: (empty file)" in line
                  for line in events(directory, state)), str(state))

        unreadable = directory / "unreadable.txt"
        unreadable.write_text("secret\n", encoding="utf-8")
        unreadable.chmod(0)
        lines = events(directory, state)
        unreadable.chmod(0o600)
        check("a notice that cannot be read is reported with the error in place of its first line",
              len(lines) == 1 and lines[0].startswith(
                  "NEEDS A LOOK unreadable.txt: (could not read it: Permission denied)"),
              "\n".join(lines))

        not_a_directory = scratch / "a-file"
        not_a_directory.write_text("", encoding="utf-8")
        first = events(not_a_directory, state)
        second = events(not_a_directory, state)
        check("a notices directory that cannot be listed is one NEEDS A LOOK line naming it, "
              "not repeated while it stays unlistable",
              first == [f"NEEDS A LOOK: cannot list the GHI-MD edit job's notices in "
                        f"{not_a_directory}: Not a directory; notices there go unreported "
                        f"until it can be listed"]
              and second == [], f"{first}\n{second}")
        events(directory, state)
        again = events(not_a_directory, state)
        check("it is reported again after a listing succeeds in between",
              len(again) == 1, str(again))
        events(not_a_directory, state)
        events(scratch / "missing", state)
        check("a missing directory between two unlistable ones also lets the second be reported",
              len(events(not_a_directory, state)) == 1, str(state))

    job = watcher_module.ghi_md_edit_job
    check("the watcher's default notices directory is the one the GHI-MD edit job writes",
          watcher_module.parse_arguments([]).needs_a_look_directory
          == job.needs_a_look_directory()
          == job.common.DEFAULT_MERGE_LANE_WORKTREES_AND_OUTPUTS_DIRECTORY
          / job.STATE_DIRECTORY_NAME / "needs-a-look", "")


MERGE_LANE_REVIEWER = watcher_module.fix_round.MERGE_LANE_2_REVIEWER_LOGIN


def review(state, head_sha, body=""):
    return {"state": state, "body": body, "commit": {"oid": head_sha * 40}}


def assignable(number, created_at="2026-11-24T00:00:00Z", head_sha="a", reviews=(), draft=False,
               author="nedlern", base_branch="main", head_branch=None, first_commit_author_name=None,
               mac_claude_reviews=()):
    """A pull request as fetch_open_pull_requests returns it."""
    return {"number": number, "head_sha": head_sha * 40, "title": f"title {number}",
            "is_draft": draft, "author": author, "first_commit_author_name": first_commit_author_name,
            "created_at": created_at,
            "base_branch": base_branch, "head_branch": head_branch or f"branch-{number}",
            "reviews": list(reviews), "mac_claude_reviews": list(mac_claude_reviews)}


def dealt_numbers(pull_requests, assignments):
    return [(pull_request["number"], lane) for pull_request, lane in
            watcher_module.merge_lane_pull_request_review_assignments_for_unassigned_pull_requests(
                pull_requests, assignments)]


def run_merge_lane_pull_request_review_assignment_unit_cases():
    waiting_1, waiting_2, waiting_3 = assignable(1), assignable(2), assignable(3)
    approved_4 = assignable(4, reviews=[review("APPROVED", "a")])
    check("a new pull request goes to the merge-lane agent-seat with fewer pull requests waiting",
          dealt_numbers([waiting_1, waiting_2, waiting_3, assignable(10)],
                        {1: "merge-lane-1", 2: "merge-lane-1", 3: "merge-lane-3"})
          == [(10, "merge-lane-3")], "")
    check("a tie goes to merge-lane-1",
          dealt_numbers([waiting_1, waiting_3, assignable(10)],
                        {1: "merge-lane-1", 3: "merge-lane-3"}) == [(10, "merge-lane-1")], "")
    check("a pull request whose newest commit has a verdict does not wait, so its agent-seat "
          "counts fewer",
          dealt_numbers([waiting_1, approved_4, waiting_3, assignable(10)],
                        {1: "merge-lane-3", 4: "merge-lane-1", 3: "merge-lane-3"})
          == [(10, "merge-lane-1")], "")
    changes_on_older_commit = assignable(5, head_sha="b", reviews=[review("CHANGES_REQUESTED", "a")])
    check("a verdict on an older commit leaves the pull request waiting",
          dealt_numbers([changes_on_older_commit, assignable(10)], {5: "merge-lane-1"})
          == [(10, "merge-lane-3")], "")
    check("a review by ned-review-merge with no verdict leaves the pull request waiting",
          dealt_numbers([assignable(6, reviews=[review("COMMENTED", "a", "a note")]), assignable(10)],
                        {6: "merge-lane-1"}) == [(10, "merge-lane-3")], "")
    own_approved = assignable(7, author=MERGE_LANE_REVIEWER,
                              reviews=[review("COMMENTED", "a", "APPROVE\nno findings")])
    check("on a pull request ned-review-merge opened, a COMMENTED review opening with APPROVE is "
          "a verdict",
          dealt_numbers([own_approved, waiting_3, assignable(10)],
                        {7: "merge-lane-3", 3: "merge-lane-1"}) == [(10, "merge-lane-3")], "")
    mac_claude_approved = assignable(9, author=MERGE_LANE_REVIEWER,
                                     reviews=[review("COMMENTED", "a", "a note")],
                                     mac_claude_reviews=[review("APPROVED", "a")])
    check("on a pull request ned-review-merge opened, mac-claude's approval of the newest commit "
          "is a verdict, as the merge gate takes it",
          dealt_numbers([mac_claude_approved, waiting_3, assignable(10)],
                        {9: "merge-lane-3", 3: "merge-lane-1"}) == [(10, "merge-lane-3")], "")
    mac_claude_approved_before_lane_review = assignable(
        8, author=MERGE_LANE_REVIEWER, reviews=[review("COMMENTED", "b", "an older note")],
        mac_claude_reviews=[review("APPROVED", "a")])
    check("on a pull request ned-review-merge opened, mac-claude's approval waits for "
          "ned-review-merge's own review of the same commit, whose grading can still change it",
          dealt_numbers([mac_claude_approved_before_lane_review, waiting_3, assignable(10)],
                        {8: "merge-lane-3", 3: "merge-lane-1"}) == [(10, "merge-lane-1")], "")
    check("a draft does not wait for a verdict, so the count and the assignment agree on it",
          not watcher_module.pull_request_waits_for_merge_lane_verdict(assignable(13, draft=True)),
          "")
    check("mac-claude's approval is no verdict on a pull request another account opened",
          dealt_numbers([assignable(12, mac_claude_reviews=[review("APPROVED", "a")]), waiting_3,
                         assignable(10)], {12: "merge-lane-3", 3: "merge-lane-1"})
          == [(10, "merge-lane-1")], "")
    check("a pull request dealt with its verdict already on its newest commit is not counted as "
          "waiting, so the next one in the same poll goes by the pull requests waiting",
          dealt_numbers([assignable(40, created_at="2026-11-24T01:00:00Z",
                                    reviews=[review("APPROVED", "a")]),
                         assignable(41, created_at="2026-11-24T02:00:00Z")], {})
          == [(40, "merge-lane-1"), (41, "merge-lane-1")], "")
    check("a pull request ned-review-merge opened is assigned like any other",
          dealt_numbers([waiting_1, assignable(11, author=MERGE_LANE_REVIEWER)], {1: "merge-lane-1"})
          == [(11, "merge-lane-3")], "")
    check("oldest first, each assignment counted at once: three new ones alternate from the tie",
          dealt_numbers([assignable(22, created_at="2026-11-24T03:00:00Z"),
                         assignable(20, created_at="2026-11-24T01:00:00Z"),
                         assignable(21, created_at="2026-11-24T02:00:00Z")], {})
          == [(20, "merge-lane-1"), (21, "merge-lane-3"), (22, "merge-lane-1")], "")
    check("merge-lane-2 is never assigned a review, however few it has waiting",
          dealt_numbers([waiting_1, waiting_3, assignable(10)],
                        {1: "merge-lane-1", 3: "merge-lane-3"})[0][1] != "merge-lane-2", "")
    check("a pull request whose first commit merge-lane-1 wrote goes to merge-lane-3, though "
          "merge-lane-1 has fewer waiting",
          dealt_numbers([waiting_3, assignable(10, first_commit_author_name="merge-lane-1")],
                        {3: "merge-lane-3"}) == [(10, "merge-lane-3")], "")
    check("a pull request whose first commit merge-lane-3 wrote goes to merge-lane-1, though "
          "merge-lane-3 has fewer waiting",
          dealt_numbers([waiting_1, assignable(10, first_commit_author_name="merge-lane-3")],
                        {1: "merge-lane-1"}) == [(10, "merge-lane-1")], "")
    check("the bottom of a stack whose first commit merge-lane-1 wrote, and the stack with it, "
          "go to merge-lane-3",
          dealt_numbers([assignable(30, head_branch="bottom", first_commit_author_name="merge-lane-1"),
                         assignable(31, base_branch="bottom", head_branch="middle")], {})
          == [(30, "merge-lane-3"), (31, "merge-lane-3")], "")
    check("a draft is not assigned",
          dealt_numbers([assignable(10, draft=True)], {}) == [], "")
    fix_round_head = assignable(8, head_sha="b", reviews=[review("CHANGES_REQUESTED", "a")])
    check("a pull request with a line keeps it at its fix-round, even when the other agent-seat "
          "has fewer waiting",
          dealt_numbers([fix_round_head, waiting_1, waiting_2],
                        {8: "merge-lane-1", 1: "merge-lane-1", 2: "merge-lane-1"}) == [], "")

    bottom = assignable(30, head_branch="bottom")
    middle = assignable(31, base_branch="bottom", head_branch="middle")
    top = assignable(32, base_branch="middle", head_branch="top")
    check("a stacked pull request takes the agent-seat of the bottom of its stack, not the one "
          "with fewer waiting",
          dealt_numbers([bottom, middle, top, waiting_1], {30: "merge-lane-3", 1: "merge-lane-1"})
          == [(31, "merge-lane-3"), (32, "merge-lane-3")], "")
    draft_bottom = assignable(30, head_branch="bottom", draft=True)
    check("a stacked pull request whose bottom has no line has its bottom assigned first, "
          "draft or not",
          dealt_numbers([draft_bottom, middle, waiting_1], {1: "merge-lane-1"})
          == [(30, "merge-lane-3"), (31, "merge-lane-3")], "")
    check("a stacked pull request whose base no open pull request has as its head branch is "
          "taken as not stacked",
          dealt_numbers([middle, waiting_1], {1: "merge-lane-1"}) == [(31, "merge-lane-3")], "")
    twin = assignable(33, head_branch="bottom")
    check("a stacked pull request whose base two open pull requests have as their head branch is "
          "taken as not stacked",
          dealt_numbers([bottom, twin, middle, waiting_1],
                        {30: "merge-lane-1", 33: "merge-lane-1", 1: "merge-lane-1"})
          == [(31, "merge-lane-3")], "")
    loop_a = assignable(34, base_branch="loop-b", head_branch="loop-a")
    loop_b = assignable(35, base_branch="loop-a", head_branch="loop-b")
    check("a cycle of bases ends, and both pull requests are taken as not stacked",
          dealt_numbers([loop_a, loop_b], {}) == [(34, "merge-lane-1"), (35, "merge-lane-3")], "")

    read = watcher_module.merge_lane_pull_request_review_assignments_file_read
    unusable = watcher_module.MergeLanePullRequestReviewAssignmentsFileUnusable
    with tempfile.TemporaryDirectory() as scratch:
        path = Path(scratch) / "assignments.txt"
        path.write_text("4028 merge-lane-1\n4319 merge-lane-3\n", encoding="utf-8")
        check("the assignment file is read",
              read(path) == {4028: "merge-lane-1", 4319: "merge-lane-3"}, "")
        for label, text, fragment in [
                ("a line naming merge-lane-2, which only merges", "4470 merge-lane-2\n",
                 "line 1 of the assignment file"),
                ("a line naming no merge-lane agent-seat", "4028 merge-lane-4\n",
                 "line 1 of the assignment file"),
                ("a line with no number", "\n", "line 1 of the assignment file"),
                ("a pull request assigned twice", "1 merge-lane-1\n1 merge-lane-3\n",
                 "assigns pull request #1 a second time")]:
            path.write_text(text, encoding="utf-8")
            try:
                read(path)
                outcome = "read without error"
            except unusable as error:
                outcome = str(error)
            check(f"an assignment file with {label} is refused, naming the line", fragment in outcome,
                  outcome)
        path.chmod(0)
        try:
            read(path)
            outcome = "read without error"
        except unusable as error:
            outcome = str(error)
        path.chmod(0o600)
        check("an unreadable assignment file is refused, naming the error",
              "cannot be read" in outcome and "Permission denied" in outcome, outcome)


def run_watcher_in_process(flags, polls, token_file):
    """Run main() in-process, each poll a list of pull requests or a failure reason string, until
    it returns or polls past the script. Return (exit code, stdout lines, stderr text)."""
    output, errors = io.StringIO(), io.StringIO()
    clock = FakeClock(output)
    polls_made = []

    def scripted_fetch(_repo, _token):
        if len(polls_made) == len(polls):
            raise PollsRanOut(f"the watcher polled a {len(polls) + 1}th time")
        poll = polls[len(polls_made)]
        polls_made.append(clock.now)
        return (None, poll) if isinstance(poll, str) else (poll, None)

    saved = (watcher_module.time, watcher_module.fetch_open_pull_requests,
             list(watcher_module.SECRETS_TO_REDACT))
    watcher_module.time = clock
    watcher_module.fetch_open_pull_requests = scripted_fetch
    try:
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
            try:
                exit_code = watcher_module.main(["--poll-seconds", "60", "--token-file",
                                                 str(token_file), *flags])
            except PollsRanOut:
                exit_code = "still running"
    finally:
        (watcher_module.time, watcher_module.fetch_open_pull_requests,
         watcher_module.SECRETS_TO_REDACT[:]) = saved
    return exit_code, output.getvalue().splitlines(), errors.getvalue()


def run_merge_lane_pull_request_review_assignment_watcher_cases():
    with tempfile.TemporaryDirectory() as scratch:
        scratch = Path(scratch)
        token_file = scratch / "fixture.token"
        token_file.write_text(FIXTURE_TOKEN + "\n", encoding="utf-8")
        assignments = scratch / "assignments.txt"

        def watch(polls):
            return run_watcher_in_process(
                ["--needs-a-look-directory", str(scratch / "no-notices"),
                 "--merge-lane-pr-review-assignments-file", str(assignments)], polls, token_file)

        open_now = [assignable(1), assignable(40, created_at="2026-11-24T05:00:00Z")]
        assignments.write_text("1 merge-lane-1\n", encoding="utf-8")
        _, lines, _ = watch([open_now, open_now])
        check("the baseline poll assigns a pull request with no line, prints one REVIEW-ASSIGNED "
              "line naming the agent-seat, and writes it to the file",
              [line for line in lines if not line.startswith("WATCH: ")]
              == [f"PR #40 REVIEW-ASSIGNED merge-lane-3 {'a' * 8} nedlern: title 40"]
              and assignments.read_text(encoding="utf-8") == "1 merge-lane-1\n40 merge-lane-3\n",
              "\n".join(lines))

        assignments.unlink()
        seed_beside = scratch / "assignments-seed-2026-11-24.txt"
        seed_beside.write_text("1 merge-lane-1\n", encoding="utf-8")
        _, lines, _ = watch([open_now, open_now, open_now])
        seed_beside.unlink()
        stopped = [line for line in lines if "review assignment stopped" in line]
        check("a missing assignment file stops assignment with one WATCH line, saying how to seed "
              "it from the seed file beside it, and is not made",
              len(stopped) == 1 and "does not exist" in stopped[0]
              and any("--merge-lane-pr-review-assignments-file-write-from-seed-and-reviewed-prs-"
                      "then-exit" in line and str(seed_beside) in line for line in lines)
              and not any(line.startswith("PR #") for line in lines) and not assignments.exists(),
              "\n".join(lines))

        assignments.write_text("1 merge-lane-1\nforty merge-lane-3\n", encoding="utf-8")
        _, lines, _ = watch([open_now, open_now])
        check("a malformed assignment file stops assignment with one WATCH line naming the line, "
              "and is left as it was",
              sum("review assignment stopped" in line for line in lines) == 1
              and any("line 2 of the assignment file" in line for line in lines)
              and any("Correct that line by hand" in line for line in lines)
              and not any("readable" in line for line in lines)
              and not any(line.startswith("PR #") for line in lines)
              and assignments.read_text(encoding="utf-8") == "1 merge-lane-1\nforty merge-lane-3\n",
              "\n".join(lines))

        assignments.write_text("1 merge-lane-1\n", encoding="utf-8")
        scratch.chmod(0o500)
        try:
            _, lines, _ = watch([open_now, open_now])
        finally:
            scratch.chmod(0o700)
        check("an assignment file that cannot be rewritten stops assignment with one WATCH line, "
              "prints no REVIEW-ASSIGNED line, and is left as it was",
              sum("cannot be rewritten" in line for line in lines) == 1
              and not any(line.startswith("PR #") for line in lines)
              and assignments.read_text(encoding="utf-8") == "1 merge-lane-1\n",
              "\n".join(lines))
        _, lines, _ = watch([open_now])
        check("once the file can be written, the next poll assigns what waited",
              any("PR #40 REVIEW-ASSIGNED" in line for line in lines)
              and assignments.read_text(encoding="utf-8").endswith("40 merge-lane-3\n"),
              "\n".join(lines))

        assignments.write_text("1 merge-lane-1\n", encoding="utf-8")
        _, lines, _ = watch(["gh: HTTP 503", open_now])
        check("a failed GitHub query assigns nothing, and the next successful poll assigns",
              any("BLIND" in line for line in lines)
              and sum("PR #40 REVIEW-ASSIGNED" in line for line in lines) == 1, "\n".join(lines))

        assignments.write_text("1 merge-lane-1\n", encoding="utf-8")
        exit_code, lines, _ = run_watcher_in_process(
            ["--needs-a-look-directory", str(scratch / "no-notices"),
             "--merge-lane-pr-review-assignments-file", str(assignments),
             "--exit-after-first-poll-with-events"], [open_now], token_file)
        check("a REVIEW-ASSIGNED line is an event that ends --exit-after-first-poll-with-events",
              exit_code == 0 and any("PR #40 REVIEW-ASSIGNED" in line for line in lines),
              f"exit {exit_code!r}\n" + "\n".join(lines))

        assignments.write_text("1 merge-lane-1", encoding="utf-8")
        _, lines, _ = watch([open_now])
        check("a write to a file whose last line has no newline puts the new line on a line of its own",
              assignments.read_text(encoding="utf-8") == "1 merge-lane-1\n40 merge-lane-3\n"
              and any("PR #40 REVIEW-ASSIGNED merge-lane-3" in line for line in lines),
              "\n".join(lines))

        assignments.unlink()
        state = {}
        appended = watcher_module.merge_lane_pull_request_review_assignment_lines
        with contextlib.redirect_stdout(io.StringIO()):
            appended(assignments, open_now, state)
        assignments.write_text("1 merge-lane-1\n", encoding="utf-8")
        scratch.chmod(0o500)
        output = io.StringIO()
        try:
            with contextlib.redirect_stdout(output):
                events = appended(assignments, open_now, state)
        finally:
            scratch.chmod(0o700)
        check("a file made after a missing-file stop, but that cannot be rewritten, prints a "
              "WATCH line of its own for the new case",
              events == [] and "cannot be rewritten" in output.getvalue()
              and "the pull requests each poll deals are given no" in output.getvalue(),
              output.getvalue())

        real_fdopen = watcher_module.os.fdopen

        def fdopen_whose_write_fails_partway(*args, **kwargs):
            """A file that writes the first half of the new text, then fails as a full disk does."""
            opened = real_fdopen(*args, **kwargs)
            real_write = opened.write

            def write(text):
                real_write(text[:len(text) // 2])
                raise OSError(28, "No space left on device")
            opened.write = write
            return opened

        assignments.write_text("1 merge-lane-1\n", encoding="utf-8")
        two_new = [*open_now, assignable(41, created_at="2026-11-24T06:00:00Z")]
        output = io.StringIO()
        watcher_module.os.fdopen = fdopen_whose_write_fails_partway
        try:
            with contextlib.redirect_stdout(output):
                events = appended(assignments, two_new, {})
        finally:
            watcher_module.os.fdopen = real_fdopen
        check("a write that fails partway leaves the file as it was, prints no REVIEW-ASSIGNED "
              "line, and leaves no temporary file behind",
              events == [] and "No space left on device" in output.getvalue()
              and assignments.read_text(encoding="utf-8") == "1 merge-lane-1\n"
              and not list(scratch.glob("assignments.txt.*.partial")),
              f"{events}\n{output.getvalue()}")
        _, lines, _ = watch([two_new])
        check("the next poll deals every pull request the failed write dealt",
              [line.split(" ")[:4] for line in lines if " REVIEW-ASSIGNED " in line]
              == [["PR", "#40", "REVIEW-ASSIGNED", "merge-lane-3"],
                  ["PR", "#41", "REVIEW-ASSIGNED", "merge-lane-1"]]
              and assignments.read_text(encoding="utf-8")
              == "1 merge-lane-1\n40 merge-lane-3\n41 merge-lane-1\n",
              "\n".join(lines))

        # Two writers at once, as a cron run and the loop watcher are during the cutover: the
        # first pauses after its read, and the second runs while it waits.
        assignments.write_text("1 merge-lane-1\n", encoding="utf-8")
        first_has_read = threading.Event()
        first_may_replace = threading.Event()
        real_deal = watcher_module.merge_lane_pull_request_review_assignments_for_unassigned_pull_requests

        def deal_then_wait_in_the_first_writer(pull_requests, file_assignments):
            dealt = real_deal(pull_requests, file_assignments)
            if threading.current_thread().name == "first-writer":
                first_has_read.set()
                first_may_replace.wait(EVENT_WAIT_BACKSTOP_SECONDS)
            return dealt

        returned = {}

        # No redirect_stdout here: it swaps sys.stdout for the whole process, not one thread.
        def writer(name, pull_requests):
            returned[name] = appended(assignments, pull_requests, {}, report_stop=lambda _line: None)

        watcher_module.merge_lane_pull_request_review_assignments_for_unassigned_pull_requests = (
            deal_then_wait_in_the_first_writer)
        try:
            first = threading.Thread(target=writer, name="first-writer",
                                     args=("first", [assignable(1), assignable(40)]))
            first.start()
            first_has_read.wait(EVENT_WAIT_BACKSTOP_SECONDS)
            second = threading.Thread(target=writer, name="second-writer",
                                      args=("second", [assignable(1), assignable(41)]))
            second.start()
            second.join(0.5)
            second_waited = second.is_alive()
            first_may_replace.set()
            first.join(EVENT_WAIT_BACKSTOP_SECONDS)
            second.join(EVENT_WAIT_BACKSTOP_SECONDS)
        finally:
            first_may_replace.set()
            watcher_module.merge_lane_pull_request_review_assignments_for_unassigned_pull_requests = real_deal
        final = assignments.read_text(encoding="utf-8")
        check("a second writer waits for the first to replace the assignment file, so the file "
              "keeps every line either writer reported as REVIEW-ASSIGNED",
              second_waited and "40 merge-lane-" in final and "41 merge-lane-" in final
              and len(returned.get("first", [])) == 1 and len(returned.get("second", [])) == 1,
              f"second waited: {second_waited}\n{final}\n{returned}")

        assignments.write_text("1 merge-lane-1\n", encoding="utf-8")
        assignments.with_name(assignments.name + ".lock").unlink()
        scratch.chmod(0o500)
        output = io.StringIO()
        try:
            with contextlib.redirect_stdout(output):
                events = appended(assignments, open_now, {})
        finally:
            scratch.chmod(0o700)
        check("a lock file that cannot be made stops assignment with one WATCH line, and leaves "
              "the assignment file as it was",
              events == [] and "lock file beside the assignment file" in output.getvalue()
              and assignments.read_text(encoding="utf-8") == "1 merge-lane-1\n",
              output.getvalue())

        stray_partial = scratch / "assignments.txt.partial"
        stray_partial.write_text("someone else's file\n", encoding="utf-8")
        assignments.write_text("1 merge-lane-1\n", encoding="utf-8")
        assignments.chmod(0o640)  # tempfile.mkstemp makes 0o600, so only a kept mode gives 0o640
        with contextlib.redirect_stdout(io.StringIO()):
            appended(assignments, open_now, {})
        check("a rewrite leaves a file named <assignment file>.partial alone, and keeps the "
              "file's mode",
              stray_partial.read_text(encoding="utf-8") == "someone else's file\n"
              and assignments.read_text(encoding="utf-8") == "1 merge-lane-1\n40 merge-lane-3\n"
              and stat.S_IMODE(assignments.stat().st_mode) == 0o640,
              f"{stray_partial.read_text(encoding='utf-8')!r} {oct(assignments.stat().st_mode)}")
        stray_partial.unlink()

        linked_target = scratch / "assignments-kept-elsewhere.txt"
        linked_target.write_text("1 merge-lane-1\n", encoding="utf-8")
        link = scratch / "assignments-link.txt"
        link.symlink_to(linked_target)
        with contextlib.redirect_stdout(io.StringIO()):
            appended(link, open_now, {})
        check("a rewrite through a symbolic link keeps the link and writes the file it names",
              link.is_symlink()
              and linked_target.read_text(encoding="utf-8") == "1 merge-lane-1\n40 merge-lane-3\n",
              f"{link.is_symlink()} {linked_target.read_text(encoding='utf-8')!r}")

        # Reading text turns a carriage return into a newline, so only a line separator is left.
        assignments.write_text("1 merge-lane-1\u2028", encoding="utf-8")
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            events = appended(assignments, open_now, {})
        check("a file whose line ends in a line separator, not a newline, is refused as a "
              "damaged line before anything is written",
              events == [] and "line 1 of the assignment file" in output.getvalue()
              and assignments.read_text(encoding="utf-8") == "1 merge-lane-1\u2028",
              output.getvalue())

        # The seed.
        seed = scratch / "seed.txt"
        seed.write_text("4028 merge-lane-1\n4319 merge-lane-3\n", encoding="utf-8")
        seeded = scratch / "seeded.txt"
        reviewed = [review("COMMENTED", "a", "a note")]
        open_at_seed = [assignable(4028), assignable(4100, reviews=reviewed),
                        assignable(4101, reviews=reviewed), assignable(4102, reviews=reviewed),
                        assignable(4103)]

        def seed_with(polls):
            return run_watcher_in_process(
                ["--merge-lane-pr-review-assignments-file", str(seeded),
                 "--merge-lane-pr-review-assignments-file-write-from-seed-and-reviewed-prs-then-exit",
                 str(seed)], polls, token_file)

        exit_code, lines, errors = seed_with(["gh: HTTP 503"])
        check("the seed exits 1 when GitHub cannot be read, and writes no file",
              exit_code == 1 and "HTTP 503" in errors and not seeded.exists(), errors)
        exit_code, lines, errors = seed_with([open_at_seed])
        check("the seed writes the seed file's lines, then each other open pull request with a "
              "review by its number's remainder, none for remainder 2, merge-lane-2's, and none "
              "without a review",
              exit_code == 0
              and seeded.read_text(encoding="utf-8") == "4028 merge-lane-1\n4319 merge-lane-3\n"
              "4101 merge-lane-3\n4102 merge-lane-1\n"
              and any("wrote 4 assignment(s)" in line for line in lines),
              f"exit {exit_code!r} {errors}\n" + "\n".join(lines))
        stacked_on_4100 = assignable(4104, base_branch="branch-4100")
        _, lines, _ = run_watcher_in_process(
            ["--needs-a-look-directory", str(scratch / "no-notices"),
             "--merge-lane-pr-review-assignments-file", str(seeded)],
            [[*open_at_seed, stacked_on_4100]], token_file)
        dealt_after_seed = [line.split(" ")[1:4] for line in lines if " REVIEW-ASSIGNED " in line]
        check("after the seed, the watcher deals a reviewed pull request of remainder 2, and one "
              "stacked on it, to the same agent-seat, never merge-lane-2",
              [number for number, _, _ in dealt_after_seed] == ["#4100", "#4103", "#4104"]
              and dict((number, lane) for number, _, lane in dealt_after_seed)["#4100"]
              == dict((number, lane) for number, _, lane in dealt_after_seed)["#4104"]
              and all(lane in ("merge-lane-1", "merge-lane-3") for _, _, lane in dealt_after_seed),
              "\n".join(lines))
        exit_code, lines, errors = seed_with([open_at_seed])
        check("the seed leaves an assignment file that exists as it is, exits 0 and says it reads "
              "correctly",
              exit_code == 0 and any("every line of it reads correctly" in line for line in lines)
              and seeded.read_text(encoding="utf-8").startswith("4028 merge-lane-1\n"),
              f"exit {exit_code!r} {errors}\n" + "\n".join(lines))
        seeded.write_text("4028 merge-lane-1\n4028 merge-lane-3\n", encoding="utf-8")
        exit_code, lines, errors = seed_with([open_at_seed])
        check("the seed refuses to replace a damaged assignment file, naming the damaged line",
              exit_code == 1 and "The file is damaged: line 2 of the assignment file" in errors
              and seeded.read_text(encoding="utf-8") == "4028 merge-lane-1\n4028 merge-lane-3\n",
              errors)
        seeded.unlink()
        scratch.chmod(0o500)
        try:
            exit_code, lines, errors = seed_with([open_at_seed])
        finally:
            scratch.chmod(0o700)
        check("a seed run that cannot write the assignment file exits 1, says so, and makes none",
              exit_code == 1 and "could not be written" in errors and not seeded.exists(), errors)
        seeded.with_name(seeded.name + ".lock").unlink()
        scratch.chmod(0o500)
        try:
            exit_code, lines, errors = seed_with([open_at_seed])
        finally:
            scratch.chmod(0o700)
        check("a first seed run that cannot make the lock file exits 1, says so with no traceback, "
              "and makes no assignment file",
              exit_code == 1 and "lock file beside the assignment file" in errors
              and "Traceback" not in errors and not seeded.exists(), errors)

        class PutBackByHandWhileGitHubIsRead:
            def __len__(self):
                return 1

            def __getitem__(self, _index):
                seeded.write_text("4028 merge-lane-3\n", encoding="utf-8")
                return open_at_seed

        exit_code, lines, errors = seed_with(PutBackByHandWhileGitHubIsRead())
        check("a seed run whose assignment file is put back whole while GitHub is read keeps that "
              "file and says so, exiting 0 with nothing to rerun",
              exit_code == 0 and "exists and every line of it reads correctly" in "\n".join(lines)
              and seeded.read_text(encoding="utf-8") == "4028 merge-lane-3\n", f"{lines} {errors}")
        seeded.unlink()

        class PutBackDamagedWhileGitHubIsRead(PutBackByHandWhileGitHubIsRead):
            def __getitem__(self, _index):
                seeded.write_text("4028 lane-one\n", encoding="utf-8")
                return open_at_seed

        exit_code, lines, errors = seed_with(PutBackDamagedWhileGitHubIsRead())
        check("a seed run whose assignment file is put back damaged while GitHub is read exits 1, "
              "keeps that file and says how to repair it",
              exit_code == 1 and "The file is damaged" in errors
              and seeded.read_text(encoding="utf-8") == "4028 lane-one\n", errors)
        seeded.unlink()

        real_unlink = watcher_module.Path.unlink

        def unlink_failing_for_the_temporary_file(self, *args, **kwargs):
            if self.name.endswith(".partial") and seeded.exists():
                raise OSError(5, "Input/output error")
            return real_unlink(self, *args, **kwargs)

        watcher_module.Path.unlink = unlink_failing_for_the_temporary_file
        try:
            exit_code, lines, errors = seed_with([open_at_seed])
        finally:
            watcher_module.Path.unlink = real_unlink
        leftovers = list(scratch.glob("seeded.txt.*.partial"))
        check("a seed run whose assignment file is made but whose temporary file cannot then be "
              "removed exits 0, says the file was made, and names the temporary file left behind",
              exit_code == 0 and seeded.read_text(encoding="utf-8").startswith("4028 merge-lane-1\n")
              and "was made, but its temporary file" in errors and "Input/output error" in errors
              and "No assignment file was made" not in errors
              and len(leftovers) == 1 and str(leftovers[0].resolve()) in errors,
              f"exit {exit_code!r} {errors}")
        for leftover in leftovers:
            leftover.unlink()
        seeded.unlink()
        seed.write_text("4028 lane-one\n", encoding="utf-8")
        exit_code, lines, errors = seed_with([open_at_seed])
        check("a malformed seed file exits 1, naming it as the seed file, and writes no assignment "
              "file",
              exit_code == 1 and "line 1 of the seed file" in errors and not seeded.exists(),
              errors)

        # Another repository.
        stand_in_default = scratch / "default-assignments.txt"
        stand_in_default.write_text("1 merge-lane-1\n", encoding="utf-8")
        saved_default = watcher_module.MERGE_LANE_PULL_REQUEST_REVIEW_ASSIGNMENTS_DEFAULT_FILE
        watcher_module.MERGE_LANE_PULL_REQUEST_REVIEW_ASSIGNMENTS_DEFAULT_FILE = stand_in_default
        try:
            _, lines, _ = run_watcher_in_process(
                ["--repo", "someone/elsewhere", "--needs-a-look-directory", str(scratch / "no-notices")],
                [[assignable(1), assignable(70)]], token_file)
            check("with another --repo and no assignment file named, no review is assigned and the "
                  "default file is left alone",
                  not any(" REVIEW-ASSIGNED " in line for line in lines)
                  and stand_in_default.read_text(encoding="utf-8") == "1 merge-lane-1\n",
                  "\n".join(lines))
            exit_code, _, errors = run_watcher_in_process(
                ["--repo", "someone/elsewhere", "--merge-lane-pr-review-assignments-list-for",
                 "merge-lane-1"], [[assignable(1)]], token_file)
            check("the lookup with another --repo and no assignment file named exits 2 and asks "
                  "for the file",
                  exit_code == 2 and "--merge-lane-pr-review-assignments-file" in errors, errors)
            _, lines, _ = run_watcher_in_process(
                ["--repo", "NedsNodes/NedsNodes", "--needs-a-look-directory",
                 str(scratch / "no-notices")],
                [[assignable(1), assignable(70)]], token_file)
            check("--repo spelling the default repository in another case uses the default file "
                  "and assigns reviews",
                  any(" REVIEW-ASSIGNED " in line and "#70" in line for line in lines)
                  and "70 " in stand_in_default.read_text(encoding="utf-8"),
                  "\n".join(lines))
        finally:
            watcher_module.MERGE_LANE_PULL_REQUEST_REVIEW_ASSIGNMENTS_DEFAULT_FILE = saved_default

        spaced = scratch / "an assignment file.txt"
        steps = watcher_module.merge_lane_pull_request_review_assignments_file_repair_steps(
            spaced, "missing", ["--repo", "someone/elsewhere", "--token-file", "/tokens/a token"])
        check("the seed command the repair steps print repeats --repo and --token-file and quotes "
              "each path",
              "--repo someone/elsewhere --token-file '/tokens/a token' " in steps
              and f"--merge-lane-pr-review-assignments-file '{spaced}' " in steps, steps)

        # The lookup.
        assignments.write_text("50 merge-lane-1\n51 merge-lane-1\n52 merge-lane-1\n53 merge-lane-3\n",
                               encoding="utf-8")
        open_at_lookup = [assignable(50), assignable(51, reviews=[review("APPROVED", "a")]),
                          assignable(52, draft=True), assignable(53)]

        def look_up(lane, polls, path=assignments):
            return run_watcher_in_process(
                ["--merge-lane-pr-review-assignments-file", str(path),
                 "--merge-lane-pr-review-assignments-list-for", lane], polls, token_file)

        exit_code, lines, errors = look_up("merge-lane-1", [open_at_lookup])
        check("the lookup lists the agent-seat's open pull requests that are not drafts, and "
              "whether each waits for its verdict",
              exit_code == 0 and lines == [
                  "merge-lane-1: 2 open pull request(s) that are not drafts are assigned to it; "
                  "1 of them wait for its verdict on their newest commit",
                  f"PR #50 WAITS-FOR-VERDICT {'a' * 8} nedlern: title 50",
                  f"PR #51 HAS-VERDICT {'a' * 8} nedlern: title 51"],
              f"exit {exit_code!r} {errors}\n" + "\n".join(lines))
        exit_code, lines, errors = look_up("merge-lane-1", ["gh: HTTP 503"])
        check("the lookup exits 1 when GitHub cannot be read, naming the failure",
              exit_code == 1 and "HTTP 503" in errors and not lines, errors)
        exit_code, lines, errors = look_up("merge-lane-1", [open_at_lookup],
                                           path=scratch / "absent.txt")
        check("the lookup exits 1 when the assignment file is missing, giving merge-lane-2 the "
              "step that makes it",
              exit_code == 1 and "does not exist" in errors
              and "If you are merge-lane-2, repair the file" in errors
              and "--merge-lane-pr-review-assignments-file-write-from-seed-and-reviewed-prs-then-exit"
              in errors, errors)

        real_lock = watcher_module.merge_lane_pull_request_review_assignments_file_lock
        real_read = watcher_module.merge_lane_pull_request_review_assignments_file_read
        held = []
        read_while_held = []

        class NotedLock:
            def __init__(self, lock):
                self.lock = lock

            def __enter__(self):
                held.append(True)
                return self.lock.__enter__()

            def __exit__(self, *exc):
                held.pop()
                return self.lock.__exit__(*exc)

        def read_and_note(path):
            read_while_held.append(bool(held))
            return real_read(path)

        watcher_module.merge_lane_pull_request_review_assignments_file_lock = (
            lambda path: NotedLock(real_lock(path)))
        watcher_module.merge_lane_pull_request_review_assignments_file_read = read_and_note
        try:
            exit_code, lines, errors = look_up("merge-lane-1", [open_at_lookup])
        finally:
            watcher_module.merge_lane_pull_request_review_assignments_file_lock = real_lock
            watcher_module.merge_lane_pull_request_review_assignments_file_read = real_read
        check("the lookup reads the assignment file while it holds the file's lock, so it never "
              "sees a deal a failed append is about to put back",
              exit_code == 0 and read_while_held == [True], f"{read_while_held} {errors}")

        def lock_fails(path):
            raise OSError("injected: the lock file cannot be opened")

        watcher_module.merge_lane_pull_request_review_assignments_file_lock = lock_fails
        try:
            exit_code, lines, errors = look_up("merge-lane-1", [open_at_lookup])
        finally:
            watcher_module.merge_lane_pull_request_review_assignments_file_lock = real_lock
        check("the lookup exits 1 when the assignment file's lock cannot be taken, naming it",
              exit_code == 1 and "cannot be opened or locked" in errors and not lines, errors)


class PollsRanOut(Exception):
    """Raised by the scripted fetch when the watcher polls past the script."""


class FakeClock:
    """Stands in for the watcher's `time` module: sleep advances monotonic, and
    each sleep records how many lines stdout held then."""

    def __init__(self, output):
        self.now = 1000.0
        self.output = output
        self.lines_printed_at_each_sleep = []

    def monotonic(self):
        return self.now

    def sleep(self, seconds):
        self.lines_printed_at_each_sleep.append(len(self.output.getvalue().splitlines()))
        self.now += seconds


def run_batched_watcher(polls, batch_seconds, needs_a_look_directory, token_file):
    """Run main() in-process with --batch-events-for-seconds, a fake clock and
    the scripted polls, each a list of pull requests or a failure reason string.
    Return (exit code, stdout lines, clock, polls made)."""
    output = io.StringIO()
    clock = FakeClock(output)
    polls_made = []

    def scripted_fetch(_repo, _token):
        if len(polls_made) == len(polls):
            raise PollsRanOut(f"the watcher polled a {len(polls) + 1}th time")
        poll = polls[len(polls_made)]
        polls_made.append(clock.now)
        return (None, poll) if isinstance(poll, str) else (poll, None)

    saved = (watcher_module.time, watcher_module.fetch_open_pull_requests,
             list(watcher_module.SECRETS_TO_REDACT))
    watcher_module.time = clock
    watcher_module.fetch_open_pull_requests = scripted_fetch
    try:
        with contextlib.redirect_stdout(output):
            try:
                exit_code = watcher_module.main([
                    "--poll-seconds", "60", "--token-file", str(token_file),
                    "--needs-a-look-directory", str(needs_a_look_directory),
                    "--merge-lane-pr-review-assignments-file", str(EVERY_PULL_REQUEST_ASSIGNED_FILE),
                    "--batch-events-for-seconds", str(batch_seconds)])
            except PollsRanOut as error:
                exit_code = f"still running: {error}"
    finally:
        (watcher_module.time, watcher_module.fetch_open_pull_requests,
         watcher_module.SECRETS_TO_REDACT[:]) = saved
    return exit_code, output.getvalue().splitlines(), clock, polls_made


def run_batch_events_cases():
    def pull_request(number, head_sha):
        return {"number": number, "head_sha": head_sha * 40, "title": "t",
                "is_draft": False, "author": "nedlern"}

    with tempfile.TemporaryDirectory() as scratch:
        scratch = Path(scratch)
        token_file = scratch / "fixture.token"
        token_file.write_text(FIXTURE_TOKEN + "\n", encoding="utf-8")
        no_notices = scratch / "no-notices"
        baseline = [pull_request(145, "a")]

        # Polls at 0, 60, 120, 180 and 200 seconds after the start; events at 60 and 120.
        exit_code, lines, clock, polls_made = run_batched_watcher(
            [baseline,
             baseline + [pull_request(146, "b")],
             [pull_request(145, "c"), pull_request(146, "b")],
             [pull_request(145, "c"), pull_request(146, "b")],
             [pull_request(145, "c"), pull_request(146, "b")]],
            200, no_notices, token_file)
        events = [line for line in lines if line.startswith("PR #")]
        check("--batch-events-for-seconds with events seen before N exits 0 after one last "
              "poll at N",
              exit_code == 0 and clock.now - 1000.0 == 200
              and [made - 1000.0 for made in polls_made] == [0, 60, 120, 180, 200],
              f"exit {exit_code!r}, clock {clock.now - 1000.0}, polls {polls_made}")
        check("--batch-events-for-seconds prints every event it held, in the order seen",
              events == ["PR #146 OPENED bbbbbbbb nedlern: t",
                         "PR #145 NEW-HEAD cccccccc nedlern: t"], "\n".join(lines))
        check("--batch-events-for-seconds prints no event before it exits",
              clock.lines_printed_at_each_sleep and all(
                  count == 1 for count in clock.lines_printed_at_each_sleep)
              and lines[0].startswith("WATCH: watching"),
              f"{clock.lines_printed_at_each_sleep}\n" + "\n".join(lines))

        # No event by N = 100: polls at 0, 60, 120 and 180 seconds; the event comes at 180.
        exit_code, lines, clock, polls_made = run_batched_watcher(
            [baseline, baseline, baseline, baseline + [pull_request(147, "d")],
             baseline + [pull_request(147, "d")]],
            100, no_notices, token_file)
        check("--batch-events-for-seconds with no event before N keeps polling past N and "
              "exits 0 at the first poll with an event, printing it",
              exit_code == 0 and len(polls_made) == 4 and clock.now - 1000.0 == 180
              and [line for line in lines if line.startswith("PR #")]
              == ["PR #147 OPENED dddddddd nedlern: t"],
              f"exit {exit_code!r}, polls {polls_made}\n" + "\n".join(lines))

        # An event held before N, then every query fails from before N to past it.
        exit_code, lines, clock, polls_made = run_batched_watcher(
            [baseline, baseline + [pull_request(148, "e")], "gh: HTTP 503", "gh: HTTP 503",
             "gh: HTTP 503"],
            150, no_notices, token_file)
        check("--batch-events-for-seconds prints its held events and exits 0 after the poll "
              "at N while every query fails",
              exit_code == 0 and clock.now - 1000.0 == 150
              and any("PR #148 OPENED" in line for line in lines)
              and any("BLIND" in line for line in lines),
              f"exit {exit_code!r}, clock {clock.now - 1000.0}\n" + "\n".join(lines))

        # A notice already there at the first poll is held like any event, not an exit.
        notices = scratch / "needs-a-look"
        notices.mkdir()
        (notices / "pr9-bbbbbbbbbbbb.txt").write_text("pull request 9 needs a look\n",
                                                       encoding="utf-8")
        exit_code, lines, clock, polls_made = run_batched_watcher(
            [baseline, baseline + [pull_request(149, "f")], baseline + [pull_request(149, "f")]],
            120, notices, token_file)
        held = [line for line in lines if not line.startswith("WATCH: ")]
        check("--batch-events-for-seconds holds a notice present at the first poll until the "
              "poll at N, "
              "and prints it before the pull request events after it",
              exit_code == 0 and clock.now - 1000.0 == 120 and len(held) == 2
              and held[0].startswith("NEEDS A LOOK pr9-bbbbbbbbbbbb.txt: pull request 9")
              and held[1] == "PR #149 OPENED ffffffff nedlern: t",
              f"exit {exit_code!r}, clock {clock.now - 1000.0}\n" + "\n".join(lines))

        result = subprocess.run(
            [sys.executable, str(WATCH_SCRIPT), "--token-file", str(token_file),
             "--exit-after-first-poll-with-events", "--batch-events-for-seconds", "60"],
            capture_output=True, text=True, timeout=EVENT_WAIT_BACKSTOP_SECONDS)
        check("--exit-after-first-poll-with-events and --batch-events-for-seconds together "
              "exit 2, naming both, before any query",
              result.returncode == 2 and "not allowed with argument" in result.stderr,
              f"rc={result.returncode} stderr={result.stderr!r}")


def run_bad_invocation_cases(token_file, missing_token_file):
    """Bad invocations exit 2 with one stderr line, before any query."""
    for flags, label in [
            (["--poll-seconds", "0"], "--poll-seconds 0"),
            (["--poll-seconds", "-1"], "--poll-seconds -1"),
            (["--batch-events-for-seconds", "0"], "--batch-events-for-seconds 0"),
            (["--repo", "no-slash"], "--repo no-slash"),
            (["--repo", "a/b/c"], "--repo a/b/c")]:
        try:
            result = subprocess.run(
                [sys.executable, str(WATCH_SCRIPT),
                 "--token-file", str(token_file), *flags],
                capture_output=True, text=True, timeout=EVENT_WAIT_BACKSTOP_SECONDS)
            ok = (result.returncode == 2
                  and len(result.stderr.strip().splitlines()) == 1)
            detail = f"rc={result.returncode} stderr={result.stderr!r}"
        except subprocess.TimeoutExpired:
            ok, detail = False, (f"still running after {EVENT_WAIT_BACKSTOP_SECONDS:g}s"
                                  " — validation never fired")
        check(f"bad invocation {label} exits 2 with one stderr line", ok, detail)

    result = subprocess.run(
        [sys.executable, str(WATCH_SCRIPT),
         "--token-file", str(missing_token_file)],
        capture_output=True, text=True, timeout=EVENT_WAIT_BACKSTOP_SECONDS)
    check("an unreadable token file exits 2 and names the path",
          result.returncode == 2 and str(missing_token_file) in result.stderr,
          f"rc={result.returncode} stderr={result.stderr!r}")


def run_subprocess_cases():
    with tempfile.TemporaryDirectory() as scratch:
        scratch = Path(scratch)
        token_file = scratch / "fixture.token"
        token_file.write_text(FIXTURE_TOKEN + "\n", encoding="utf-8")

        run_bad_invocation_cases(token_file, scratch / "no-such.token")

        # ------------------------------------------------------------------
        # The main sequence, one watcher across every phase: baseline is
        # silent, a new pull request is an event, a moved head is an event,
        # an unchanged poll is not, a title edit is not.
        # ------------------------------------------------------------------
        fake_gh = FakeGitHubCommand(scratch / "sequence")
        fake_gh.answer(graphql_body([pull_request_node(145, "a" * 40,
                                                       "already open")]))
        watcher = WatcherProcess(environment=fake_gh.environment(),
                                 token_file=token_file)
        baseline = watcher.wait_for("WATCH: watching nedsnodes/nedsnodes "
                                    "every 0.05s; 1 open at baseline: #145")
        check("the first poll prints a baseline line naming what is open",
              baseline, "\n".join(watcher.lines))

        wait_for_calls(fake_gh, 4, watcher)
        check("a pull request open at the first poll is not an event",
              watcher.count("PR #145") == 0, "\n".join(watcher.lines))

        check("the credential reaches gh through the environment",
              fake_gh.token_seen() == FIXTURE_TOKEN,
              repr(fake_gh.token_seen()))

        fake_gh.answer(graphql_body([
            pull_request_node(145, "a" * 40, "already open"),
            pull_request_node(146, "b" * 40, "newly opened")]))
        opened = watcher.wait_for("PR #146 OPENED bbbbbbbb nedlern: "
                                  "newly opened")
        check("a newly opened pull request is one OPENED line", opened,
              "\n".join(watcher.lines))

        calls_now = fake_gh.call_count()
        wait_for_calls(fake_gh, calls_now + 4, watcher)
        check("polls that change nothing produce no further lines",
              watcher.count("PR #146") == 1 and watcher.count("PR #145") == 0,
              "\n".join(watcher.lines))

        # A title edit on both pull requests, no head movement.
        fake_gh.answer(graphql_body([
            pull_request_node(145, "a" * 40, "RETITLED 145"),
            pull_request_node(146, "b" * 40, "RETITLED 146")]))
        calls_now = fake_gh.call_count()
        wait_for_calls(fake_gh, calls_now + 4, watcher)
        check("a changed title is not an event",
              "RETITLED" not in "\n".join(watcher.lines), "\n".join(watcher.lines))

        # A new head commit on 146 only.
        fake_gh.answer(graphql_body([
            pull_request_node(145, "a" * 40, "RETITLED 145"),
            pull_request_node(146, "c" * 40, "RETITLED 146")]))
        moved = watcher.wait_for("PR #146 NEW-HEAD cccccccc")
        check("a new head commit on an open pull request is one NEW-HEAD line",
              moved and watcher.count("PR #146 NEW-HEAD") == 1,
              "\n".join(watcher.lines))
        check("the pull request whose head did not move stays silent",
              watcher.count("PR #145") == 0, "\n".join(watcher.lines))

        # A closed pull request that reopens is announced again — the
        # documented choice, since the seat must look at it again.
        fake_gh.answer(graphql_body([pull_request_node(146, "c" * 40,
                                                       "RETITLED 146")]))
        calls_now = fake_gh.call_count()
        wait_for_calls(fake_gh, calls_now + 3, watcher)
        fake_gh.answer(graphql_body([
            pull_request_node(145, "a" * 40, "reopened"),
            pull_request_node(146, "c" * 40, "RETITLED 146")]))
        reopened = watcher.wait_for("PR #145 OPENED aaaaaaaa nedlern: reopened")
        lines = watcher.stop()
        check("a pull request that closes and reopens is announced again",
              reopened, "\n".join(lines))
        check("closing a pull request is not itself announced",
              not any("CLOSED" in line for line in lines), "\n".join(lines))

        # ------------------------------------------------------------------
        # Drafts: one open at baseline and one opened later raise nothing,
        # nor does a new head commit on a draft; each raises one READY line
        # when marked ready, and nothing more after.
        # ------------------------------------------------------------------
        fake_gh = FakeGitHubCommand(scratch / "drafts")
        fake_gh.answer(graphql_body([
            pull_request_node(170, "a" * 40, "draft at baseline", draft=True)]))
        watcher = WatcherProcess(environment=fake_gh.environment(),
                                 token_file=token_file)
        baseline = watcher.wait_for("0 open at baseline")
        check("a draft at baseline is listed apart in the baseline line",
              baseline and any("not to be reviewed until marked ready"
                               in line and "#170" in line
                               for line in watcher.lines),
              "\n".join(watcher.lines))
        fake_gh.answer(graphql_body([
            pull_request_node(170, "a" * 40, "draft at baseline", draft=True),
            pull_request_node(171, "b" * 40, "opened as a draft", draft=True)]))
        calls_now = fake_gh.call_count()
        wait_for_calls(fake_gh, calls_now + 4, watcher)
        check("a pull request opened as a draft raises no line",
              watcher.count("PR #171") == 0, "\n".join(watcher.lines))
        fake_gh.answer(graphql_body([
            pull_request_node(170, "a" * 40, "draft at baseline", draft=True),
            pull_request_node(171, "c" * 40, "opened as a draft", draft=True)]))
        calls_now = fake_gh.call_count()
        wait_for_calls(fake_gh, calls_now + 4, watcher)
        check("a new head commit on a draft raises no line",
              watcher.count("PR #171") == 0, "\n".join(watcher.lines))
        fake_gh.answer(graphql_body([
            pull_request_node(170, "a" * 40, "draft at baseline"),
            pull_request_node(171, "c" * 40, "opened as a draft")]))
        ready_baseline = watcher.wait_for("PR #170 READY aaaaaaaa nedlern: "
                                          "draft at baseline")
        ready_later = watcher.wait_for("PR #171 READY cccccccc nedlern: "
                                       "opened as a draft")
        calls_now = fake_gh.call_count()
        wait_for_calls(fake_gh, calls_now + 4, watcher)
        lines = watcher.stop()
        check("a draft open at baseline and marked ready is one READY line",
              ready_baseline and watcher.count("PR #170") == 1,
              "\n".join(lines))
        check("a draft opened later and marked ready is one READY line, "
              "carrying the current head",
              ready_later and watcher.count("PR #171") == 1, "\n".join(lines))

        # ------------------------------------------------------------------
        # --exit-after-first-poll-with-events does not exit for a draft, and
        # does exit for the draft marked ready.
        # ------------------------------------------------------------------
        fake_gh = FakeGitHubCommand(scratch / "exit-on-ready")
        fake_gh.answer(graphql_body([]))
        watcher = WatcherProcess("--exit-after-first-poll-with-events",
                                 environment=fake_gh.environment(),
                                 token_file=token_file)
        watcher.wait_for("0 open at baseline")
        fake_gh.answer(graphql_body([
            pull_request_node(172, "d" * 40, "a draft", draft=True)]))
        calls_now = fake_gh.call_count()
        wait_for_calls(fake_gh, calls_now + 4, watcher)
        check("--exit-after-first-poll-with-events keeps polling when only a "
              "draft opened",
              watcher.process.poll() is None and watcher.count("PR #172") == 0,
              "\n".join(watcher.lines))
        fake_gh.answer(graphql_body([
            pull_request_node(172, "d" * 40, "a draft")]))
        try:
            exit_code = watcher.process.wait(timeout=EVENT_WAIT_BACKSTOP_SECONDS)
        except subprocess.TimeoutExpired:
            exit_code = None
        lines = watcher.stop()
        check("--exit-after-first-poll-with-events exits 0 on a draft marked "
              "ready, printing its READY line",
              exit_code == 0
              and any("PR #172 READY dddddddd" in line for line in lines),
              f"exit {exit_code}\n" + "\n".join(lines))

        # ------------------------------------------------------------------
        # --exit-after-first-poll-with-events: polls on through a silent baseline, then
        # prints every event of the first poll that has one and exits 0.
        # ------------------------------------------------------------------
        fake_gh = FakeGitHubCommand(scratch / "exit-after-first-poll-with-events")
        fake_gh.answer(graphql_body([pull_request_node(145, "a" * 40, "open")]))
        watcher = WatcherProcess("--exit-after-first-poll-with-events",
                                 environment=fake_gh.environment(),
                                 token_file=token_file)
        wait_for_calls(fake_gh, 3, watcher)
        check("--exit-after-first-poll-with-events keeps polling while no event comes",
              watcher.process.poll() is None, "\n".join(watcher.lines))
        fake_gh.answer(graphql_body([
            pull_request_node(145, "d" * 40, "open"),
            pull_request_node(147, "e" * 40, "opened with the move")]))
        try:
            exit_code = watcher.process.wait(timeout=EVENT_WAIT_BACKSTOP_SECONDS)
        except subprocess.TimeoutExpired:
            exit_code = None
        lines = watcher.stop()
        check("--exit-after-first-poll-with-events exits 0 after the first poll with an event",
              exit_code == 0, f"exit {exit_code}\n" + "\n".join(lines))
        check("--exit-after-first-poll-with-events prints every event of that poll",
              any("PR #145 NEW-HEAD dddddddd" in line for line in lines)
              and any("PR #147 OPENED eeeeeeee" in line for line in lines),
              "\n".join(lines))

        # ------------------------------------------------------------------
        # Blindness: announced once, recovery announced, and no event lost
        # while blind.
        # ------------------------------------------------------------------
        fake_gh = FakeGitHubCommand(scratch / "blindness")
        fake_gh.answer(graphql_body([pull_request_node(145, "a" * 40, "open")]))
        watcher = WatcherProcess(environment=fake_gh.environment(),
                                 token_file=token_file)
        watcher.wait_for("1 open at baseline")

        fake_gh.answer(stdout="", exit_code=1,
                       stderr="gh: HTTP 503 Service Unavailable")
        blind = watcher.wait_for("WATCH: query failed")
        check("a failed query announces the watch is blind, in plain words",
              blind and any("BLIND until it recovers" in line
                            and "HTTP 503" in line for line in watcher.lines),
              "\n".join(watcher.lines))
        # The blind line promises to FLAG what the blindness cost, and that
        # verb is load-bearing. An earlier wording promised the recovery line
        # would say "what was and was not captured"; with a baseline the
        # recovery line reports only counts and duration, so a reader had to
        # take the ABSENCE of a loss clause as the reassurance — the
        # absence-as-signal shape this program exists to avoid. A promise to
        # flag is kept by saying nothing when nothing was lost, which is what
        # the pair of checks here and after recovery pins.
        check("the blind line promises to flag what the blindness cost",
              any("BLIND until it recovers" in line
                  and "flags anything the blindness cost" in line
                  for line in watcher.lines),
              "\n".join(watcher.lines))

        calls_now = fake_gh.call_count()
        wait_for_calls(fake_gh, calls_now + 5, watcher)
        check("the blind line is printed once per episode, not once per poll",
              watcher.count("WATCH: query failed") == 1,
              "\n".join(watcher.lines))

        # A pull request opens while the watch is blind; the head of the
        # one already known moves at the same time.
        fake_gh.answer(graphql_body([
            pull_request_node(145, "z" * 40, "open"),
            pull_request_node(150, "d" * 40, "opened while blind")]))
        recovered = watcher.wait_for("WATCH: query recovered after ")
        missed_open = watcher.wait_for("PR #150 OPENED dddddddd nedlern: "
                                       "opened while blind")
        missed_move = watcher.wait_for("PR #145 NEW-HEAD zzzzzzzz")
        lines = watcher.stop()
        check("recovery is announced, with how many polls failed", recovered,
              "\n".join(lines))
        check("a pull request opened while blind is reported on recovery",
              missed_open, "\n".join(lines))
        # The other half of the flagging promise: a baseline existed, so
        # nothing was lost, so the recovery line flags nothing — and the
        # events it delayed arrive right behind it. Silence here is the
        # promise being kept, not the promise going unmet.
        check("with a baseline, the recovery line flags no loss",
              all("NO BASELINE" not in line
                  for line in lines if "query recovered" in line),
              "\n".join(lines))
        check("a head that moved while blind is reported on recovery",
              missed_move, "\n".join(lines))
        check("the recovery line comes before the events it delayed",
              [index for index, line in enumerate(lines)
               if "query recovered" in line][0]
              < [index for index, line in enumerate(lines)
                 if "PR #150 OPENED" in line][0],
              "\n".join(lines))

        # ------------------------------------------------------------------
        # Blindness BEFORE the first successful poll is the case the block
        # above does not cover, and the one the program used to describe
        # wrongly. With no baseline there is nothing to compare against, so a
        # pull request that opened during the outage is indistinguishable from
        # one that was open all along: it is absorbed into the baseline and
        # gets no OPENED line. That is unavoidable. What is not unavoidable is
        # a recovery line that reads exactly like the recoverable case — an
        # agent following the stated contract would see recovery, see no
        # events, and conclude nothing had opened. Seat boot is when a first
        # poll is likeliest to fail, so this is the common blind episode.
        # ------------------------------------------------------------------
        fake_gh = FakeGitHubCommand(scratch / "blind-before-baseline")
        fake_gh.answer(stdout="", exit_code=1,
                       stderr="gh: HTTP 503 Service Unavailable")
        watcher = WatcherProcess(environment=fake_gh.environment(),
                                 token_file=token_file)
        watcher.wait_for("WATCH: query failed")
        fake_gh.answer(graphql_body([
            pull_request_node(160, "e" * 40, "opened before any baseline"),
            pull_request_node(161, "f" * 40, "also opened before any baseline")]))
        recovered = watcher.wait_for("WATCH: query recovered after ")
        watcher.wait_for("open at baseline")
        calls_now = fake_gh.call_count()
        wait_for_calls(fake_gh, calls_now + 3, watcher)
        lines = watcher.stop()
        check("recovering with no baseline says the openings are absorbed",
              recovered and any("query recovered" in line and "NO BASELINE" in line
                                for line in lines),
              "\n".join(lines))
        check("and it does not silently claim those pull requests as events",
              not any("PR #160 OPENED" in line or "PR #161 OPENED" in line
                      for line in lines),
              "\n".join(lines))

        # ------------------------------------------------------------------
        # The same blind-before-baseline episode under --from-start, where the
        # absorption does not happen: the baseline is seeded empty, so every
        # open pull request IS emitted as OPENED. Announcing a loss here would
        # be the block above's defect pointing the other way — an agent
        # reading the stream by its stated contract would believe it had
        # missed openings it actually received, and the remedy the line offers
        # is the flag it is already running under.
        # ------------------------------------------------------------------
        fake_gh = FakeGitHubCommand(scratch / "blind-before-baseline-from-start")
        fake_gh.answer(stdout="", exit_code=1,
                       stderr="gh: HTTP 503 Service Unavailable")
        watcher = WatcherProcess("--from-start",
                                 environment=fake_gh.environment(),
                                 token_file=token_file)
        watcher.wait_for("WATCH: query failed")
        fake_gh.answer(graphql_body([
            pull_request_node(160, "e" * 40, "opened before any baseline"),
            pull_request_node(161, "f" * 40, "also opened before any baseline")]))
        watcher.wait_for("WATCH: query recovered after ")
        watcher.wait_for("PR #161 OPENED")
        lines = watcher.stop()
        recovery = [line for line in lines if "query recovered" in line]
        check("--from-start recovery does not claim the openings were absorbed",
              bool(recovery) and "NO BASELINE" not in recovery[0],
              "\n".join(lines))
        check("--from-start recovery does not recommend the flag already in use",
              bool(recovery) and "--from-start" not in recovery[0],
              "\n".join(lines))
        check("and both pull requests really were reported as OPENED, which is "
              "what makes the absorption claim false here",
              any("PR #160 OPENED" in line for line in lines)
              and any("PR #161 OPENED" in line for line in lines),
              "\n".join(lines))

        # ------------------------------------------------------------------
        # The credential never reaches any output stream, including the
        # failure path that quotes gh's own stderr back.
        # ------------------------------------------------------------------
        fake_gh = FakeGitHubCommand(scratch / "leak")
        fake_gh.answer(
            stdout="", exit_code=1,
            stderr=f"gh: request failed: Authorization: Bearer {FIXTURE_TOKEN}")
        watcher = WatcherProcess(environment=fake_gh.environment(),
                                 token_file=token_file)
        blind = watcher.wait_for("WATCH: query failed")
        fake_gh.answer(graphql_body([]))
        watcher.wait_for("WATCH: query recovered")
        lines = watcher.stop()
        everything = "\n".join(lines + watcher.error_lines)
        check("gh's stderr is quoted back, so the failure is diagnosable",
              blind and "request failed" in everything, everything)
        check("the token never reaches stdout or stderr, even quoting gh",
              FIXTURE_TOKEN not in everything and "[REDACTED]" in everything,
              everything)
        check("the fake gh was nonetheless handed the real fixture token",
              fake_gh.token_seen() == FIXTURE_TOKEN,
              repr(fake_gh.token_seen()))

        # ------------------------------------------------------------------
        # The same guarantee when gh's stderr is long enough that the snippet's
        # length cut falls INSIDE the token. Redaction replaces whole
        # occurrences, so a cut taken before redaction leaves an unmatchable
        # prefix on the line. The case above cannot catch that: its stderr is
        # shorter than the cut, so the token is never bisected. Measured
        # before the fix — 20 of the token's characters printed, no [REDACTED]
        # in the line.
        # ------------------------------------------------------------------
        cut = watcher_module.FAILURE_REASON_SNIPPET_CHARS
        surviving_characters = 20
        opening = "gh: request failed: "
        bisecting_stderr = (opening
                            + "x" * (cut - surviving_characters - len(opening))
                            + FIXTURE_TOKEN)
        check("the fixture stderr really does straddle the cut, or this case "
              "proves nothing",
              bisecting_stderr.index(FIXTURE_TOKEN) < cut < len(bisecting_stderr),
              f"token at {bisecting_stderr.index(FIXTURE_TOKEN)}, "
              f"cut at {cut}, reason length {len(bisecting_stderr)}")
        fake_gh = FakeGitHubCommand(scratch / "leak-across-the-cut")
        fake_gh.answer(stdout="", exit_code=1, stderr=bisecting_stderr)
        watcher = WatcherProcess(environment=fake_gh.environment(),
                                 token_file=token_file)
        watcher.wait_for("WATCH: query failed")
        fake_gh.answer(graphql_body([]))
        watcher.wait_for("WATCH: query recovered")
        lines = watcher.stop()
        everything = "\n".join(lines + watcher.error_lines)
        check("a token bisected by the length cut leaves no surviving prefix",
              FIXTURE_TOKEN[:surviving_characters] not in everything,
              everything)
        check("and the whole token is absent from a bisected line too",
              FIXTURE_TOKEN not in everything, everything)

        # ------------------------------------------------------------------
        # Answers that are not a failed exit status: a GraphQL error beside
        # a partial body (HTTP 200), and output that is not JSON at all.
        # Both are failures, and neither may reach the compared state.
        # ------------------------------------------------------------------
        for label, answer, expected_fragment in [
                ("a GraphQL error beside a partial body",
                 json.dumps({"data": {"repository": None},
                             "errors": [{"message": "Could not resolve to a "
                                                    "Repository"}]}),
                 "Could not resolve"),
                ("output that is not JSON",
                 "gh printed something else entirely",
                 "unparseable JSON")]:
            fake_gh = FakeGitHubCommand(scratch / f"answer-{len(label)}")
            fake_gh.answer(graphql_body([pull_request_node(145, "a" * 40,
                                                           "open")]))
            watcher = WatcherProcess(environment=fake_gh.environment(),
                                     token_file=token_file)
            watcher.wait_for("1 open at baseline")
            fake_gh.answer(stdout=answer, exit_code=0)
            blind = watcher.wait_for("WATCH: query failed")
            fake_gh.answer(graphql_body([pull_request_node(145, "a" * 40,
                                                           "open")]))
            recovered = watcher.wait_for("WATCH: query recovered")
            lines = watcher.stop()
            check(f"{label} (exit status 0) is a failure, not an empty answer",
                  blind and any(expected_fragment in line for line in lines),
                  "\n".join(lines))
            check(f"{label}: the compared state survives it",
                  recovered and not any("PR #145 OPENED" in line
                                        for line in lines), "\n".join(lines))

        # ------------------------------------------------------------------
        # A gh that never runs at all is a failure with a message, not a
        # traceback and not silence.
        # ------------------------------------------------------------------
        fake_gh = FakeGitHubCommand(scratch / "no-gh")
        environment_without_gh = {**fake_gh.environment(),
                                  "PATH": str(scratch / "empty-path")}
        (scratch / "empty-path").mkdir()
        watcher = WatcherProcess(environment=environment_without_gh,
                                 token_file=token_file)
        blind = watcher.wait_for("WATCH: query failed")
        lines = watcher.stop()
        check("a gh that cannot be run at all announces blindness",
              blind and any("FileNotFoundError" in line for line in lines),
              "\n".join(lines + watcher.error_lines))

        # ------------------------------------------------------------------
        # --from-start reports what is already open, and a paginated answer
        # assembles into one poll rather than two rounds of events.
        # ------------------------------------------------------------------
        fake_gh = FakeGitHubCommand(scratch / "from-start")
        fake_gh.answer(graphql_body([pull_request_node(145, "a" * 40, "first")],
                                    has_next_page=True, end_cursor="CURSOR"))
        fake_gh.answer(graphql_body([pull_request_node(146, "b" * 40, "second")]),
                       name="control-next-page.json")
        watcher = WatcherProcess("--from-start",
                                 environment=fake_gh.environment(),
                                 token_file=token_file)
        first = watcher.wait_for("PR #145 OPENED aaaaaaaa nedlern: first")
        second = watcher.wait_for("PR #146 OPENED bbbbbbbb nedlern: second")
        calls_now = fake_gh.call_count()
        wait_for_calls(fake_gh, calls_now + 4, watcher)
        lines = watcher.stop()
        check("--from-start reports every already-open pull request",
              first and second, "\n".join(lines))
        check("a second page is fetched and joins the same poll",
              watcher.count("PR #145") == 1 and watcher.count("PR #146") == 1,
              "\n".join(lines))
        check("--from-start says so in the baseline line",
              any("each reported below as OPENED" in line for line in lines),
              "\n".join(lines))

        # ------------------------------------------------------------------
        # A notice of the GHI-MD edit job already there at the first poll is
        # an event that ends --exit-after-first-poll-with-events, and so is
        # one that appears while every query fails.
        # ------------------------------------------------------------------
        notices = scratch / "needs-a-look"
        notices.mkdir()
        (notices / "pr9-bbbbbbbbbbbb.txt").write_text("pull request 9 needs a look\n",
                                                       encoding="utf-8")
        fake_gh = FakeGitHubCommand(scratch / "notice-at-start")
        watcher = WatcherProcess("--exit-after-first-poll-with-events",
                                 environment=fake_gh.environment(), token_file=token_file,
                                 needs_a_look_directory=notices)
        try:
            exit_code = watcher.process.wait(timeout=EVENT_WAIT_BACKSTOP_SECONDS)
        except subprocess.TimeoutExpired:
            exit_code = None
        lines = watcher.stop()
        check("a notice present at the first poll is reported and ends "
              "--exit-after-first-poll-with-events with exit 0",
              exit_code == 0 and watcher.count(
                  "NEEDS A LOOK pr9-bbbbbbbbbbbb.txt: pull request 9 needs a look") == 1,
              f"exit {exit_code}\n" + "\n".join(lines + watcher.error_lines))

        fake_gh = FakeGitHubCommand(scratch / "notice-while-blind")
        fake_gh.answer(exit_code=1, stderr="HTTP 502")
        empty_notices = scratch / "needs-a-look-empty"
        watcher = WatcherProcess("--exit-after-first-poll-with-events",
                                 environment=fake_gh.environment(), token_file=token_file,
                                 needs_a_look_directory=empty_notices)
        blind = watcher.wait_for("WATCH: query failed")
        wait_for_calls(fake_gh, fake_gh.call_count() + 2, watcher)
        still_running = watcher.process.poll() is None
        empty_notices.mkdir()
        (empty_notices / "invocation-stopped.txt").write_text("the job stopped\n",
                                                              encoding="utf-8")
        try:
            exit_code = watcher.process.wait(timeout=EVENT_WAIT_BACKSTOP_SECONDS)
        except subprocess.TimeoutExpired:
            exit_code = None
        lines = watcher.stop()
        check("a notice that appears while every query fails is reported and ends "
              "--exit-after-first-poll-with-events with exit 0",
              blind and still_running and exit_code == 0
              and watcher.count("NEEDS A LOOK invocation-stopped.txt: the job stopped") == 1,
              f"exit {exit_code}\n" + "\n".join(lines + watcher.error_lines))


class PollOnceMachine:
    """A scratch state directory, task list and scripted GitHub for --poll-once runs in-process."""

    def __init__(self, scratch, token_file):
        self.directory = scratch / "poll-once"
        self.tasks = scratch / "tasks"
        self.tasks.mkdir()
        self.notices = scratch / "notices"
        self.token_file = token_file
        self.now = 1_800_000_000.0
        self.poll = []
        self.state_path = self.directory / watcher_module.WATCH_OPEN_PULL_REQUESTS_POLL_STATE_BETWEEN_CRON_RUNS_FILE_NAME
        self.events_path = self.directory / watcher_module.WATCH_OPEN_PULL_REQUESTS_EVENTS_LOG_FILE_NAME
        self.assignments = scratch / "assignments.txt"
        self.assignments.write_text(EVERY_PULL_REQUEST_ASSIGNED_FILE.read_text(encoding="utf-8"),
                                    encoding="utf-8")

    def time(self):
        return self.now

    def run(self, flag="--poll-once", assignment_options=None):
        saved = (watcher_module.time, watcher_module.fetch_open_pull_requests,
                 list(watcher_module.SECRETS_TO_REDACT))
        watcher_module.time = self
        watcher_module.fetch_open_pull_requests = lambda _repo, _token: (
            (None, self.poll) if isinstance(self.poll, str) else (self.poll, None))
        errors, output = io.StringIO(), io.StringIO()
        try:
            with contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
                code = watcher_module.main([
                    flag, "--token-file", str(self.token_file),
                    "--poll-once-directory", str(self.directory),
                    "--task-list-directory", str(self.tasks),
                    "--needs-a-look-directory", str(self.notices),
                    *(["--merge-lane-pr-review-assignments-file", str(self.assignments)]
                      if assignment_options is None else assignment_options)])
        finally:
            (watcher_module.time, watcher_module.fetch_open_pull_requests,
             watcher_module.SECRETS_TO_REDACT[:]) = saved
        self.errors, self.output = errors.getvalue(), output.getvalue()
        return code

    def task_files(self):
        return sorted(self.tasks.glob("*.json"), key=lambda path: int(path.stem))

    def tasks_read(self):
        return [json.loads(path.read_text(encoding="utf-8")) for path in self.task_files()]

    def complete_tasks(self):
        for path in self.task_files():
            task = json.loads(path.read_text(encoding="utf-8"))
            task["status"] = "completed"
            path.write_text(json.dumps(task), encoding="utf-8")

    def event_lines(self):
        return (self.events_path.read_text(encoding="utf-8").splitlines()
                if self.events_path.exists() else [])


def poll_once_pull_request(number, head="a", draft=False):
    return {"number": number, "head_sha": head * 40, "title": "t", "is_draft": draft,
            "author": "nedlern", "created_at": f"2026-11-24T00:00:{number:02d}Z",
            "base_branch": "main", "head_branch": f"branch-{number}", "reviews": []}


def run_poll_once_cases(scratch_root, token_file):
    def machine_for(name):
        scratch = scratch_root / name
        scratch.mkdir()
        return PollOnceMachine(scratch, token_file)

    machine = machine_for("missing-state")
    machine.poll = [poll_once_pull_request(1)]
    code = machine.run()
    check("--poll-once with no state file exits 1, writes no state and opens one task saying how "
          "to repair it",
          code == 1 and not machine.state_path.exists() and len(machine.tasks_read()) == 1
          and "--poll-once-write-baseline" in machine.tasks_read()[0]["description"],
          f"{code} {machine.tasks_read()}")
    machine.run()
    check("a second run with the state still missing opens no second task",
          len(machine.tasks_read()) == 1, machine.tasks_read())

    machine = machine_for("unreadable-state")
    machine.directory.mkdir()
    machine.state_path.write_text("{ not json", encoding="utf-8")
    machine.poll = [poll_once_pull_request(1)]
    code = machine.run()
    check("an unreadable state file exits 1, is left as it was, and is not re-baselined",
          code == 1 and machine.state_path.read_text(encoding="utf-8") == "{ not json"
          and not machine.event_lines() and "cannot be read" in machine.tasks_read()[0]["description"],
          f"{code} {machine.tasks_read()}")
    check("--poll-once-write-baseline refuses to replace an existing state file",
          machine.run("--poll-once-write-baseline") == 1
          and machine.state_path.read_text(encoding="utf-8") == "{ not json", machine.errors)
    machine.state_path.write_text(json.dumps({"pull_requests": {}, "notices": {}, "failed_polls": "x",
                                              "event_lines_delivered": 0,
                                              "last_events_task_opened_at": None}), encoding="utf-8")
    check("a state file with a field of the wrong type exits 1",
          machine.run() == 1 and "wrong type" in machine.errors, machine.errors)
    machine.state_path.write_text(json.dumps({"pull_requests": {}, "notices": {"reported": None},
                                              "failed_polls": 0, "event_lines_delivered": 0,
                                              "last_events_task_opened_at": None}), encoding="utf-8")
    code = machine.run()
    check("a state file whose notices hold a record of the wrong type exits 1 with the repair "
          "step, not a traceback",
          code == 1 and "wrong type" in machine.errors and "Traceback" not in machine.errors,
          f"{code} {machine.errors}")

    machine = machine_for("quiet")
    machine.poll = [poll_once_pull_request(1), poll_once_pull_request(2, draft=True)]
    check("the baseline run exits 0 and raises no event",
          machine.run("--poll-once-write-baseline") == 0 and not machine.event_lines(),
          machine.errors)
    check("the baseline says to list the open pull requests by hand once, and to read the event "
          "lines no task named",
          "list the open pull requests by hand once" in machine.output
          and f"every line of {machine.events_path} as delivered" in machine.output,
          machine.output)
    machine.run()
    before = machine.state_path.read_text(encoding="utf-8")
    for _ in range(3):
        machine.now += 60
        code = machine.run()
    check("a run that detects nothing new exits 0, appends no event and opens no task",
          code == 0 and not machine.event_lines() and machine.tasks_read() == []
          and machine.state_path.read_text(encoding="utf-8") == before,
          f"{code} {machine.tasks_read()}")

    machine.poll = [poll_once_pull_request(1, "b"), poll_once_pull_request(2),
                    poll_once_pull_request(3)]
    machine.now += 60
    code = machine.run()
    lines = machine.event_lines()
    check("a new head, a draft marked ready and an opening between runs are each one event, and "
          "open one task naming the lines",
          code == 0 and len(lines) == 3 and "#1 NEW-HEAD" in lines[0] and "#2 READY" in lines[1]
          and "#3 OPENED" in lines[2] and len(machine.tasks_read()) == 1
          and f"lines 1 to 3 of {machine.events_path}" in machine.tasks_read()[0]["description"],
          f"{lines} {machine.tasks_read()}")
    machine.now += 60
    machine.run()
    check("the next run with nothing new repeats no event and opens no task",
          len(machine.event_lines()) == 3 and len(machine.tasks_read()) == 1, machine.event_lines())

    machine.poll = machine.poll + [poll_once_pull_request(4)]
    machine.now += 60
    machine.run()
    check("a later event waits while the events task is open",
          len(machine.event_lines()) == 4 and len(machine.tasks_read()) == 1, machine.tasks_read())
    machine.complete_tasks()
    machine.now += 60
    machine.run()
    check("once that task is completed, the event still waits until 20 minutes after the last "
          "task opened", len(machine.tasks_read()) == 1, machine.tasks_read())
    machine.now += watcher_module.WATCH_OPEN_PULL_REQUESTS_MINIMUM_SECONDS_BETWEEN_EVENTS_TASKS
    machine.run()
    check("after 20 minutes one new task names only the line not yet delivered",
          len(machine.tasks_read()) == 2
          and "lines 4 to 4 of" in machine.tasks_read()[1]["description"], machine.tasks_read())

    machine = machine_for("failed-polls")
    machine.poll = [poll_once_pull_request(1)]
    machine.run("--poll-once-write-baseline")
    machine.poll = "GitHub is down"
    codes = [machine.run() for _ in range(watcher_module.WATCH_OPEN_PULL_REQUESTS_FAILED_GITHUB_POLLS_IN_A_ROW_BEFORE_FAILURE_TASK - 1)]
    check("failed polls below the limit exit 1 and open no task",
          set(codes) == {1} and machine.tasks_read() == [], machine.tasks_read())
    machine.run()
    machine.run()
    check("the failed poll at the limit opens one task, and the next opens no other",
          len(machine.tasks_read()) == 1
          and "GitHub is down" in machine.tasks_read()[0]["description"], machine.tasks_read())
    machine.complete_tasks()
    machine.poll = [poll_once_pull_request(1), poll_once_pull_request(5)]
    check("after the outage the kept state reports what opened during it",
          machine.run() == 0 and any("#5 OPENED" in line for line in machine.event_lines()),
          machine.event_lines())

    machine = machine_for("notices")
    machine.poll = []
    machine.run("--poll-once-write-baseline")
    machine.notices.mkdir()
    (machine.notices / "pr1-abc.txt").write_text("look at this\n", encoding="utf-8")
    machine.run()
    machine.now += 60
    machine.run()
    check("a GHI-MD edit job notice is one event across runs, and says to move it",
          sum("NEEDS A LOOK pr1-abc.txt: look at this" in line for line in machine.event_lines()) == 1
          and "then move it:" in machine.event_lines()[0], machine.event_lines())

    machine = machine_for("append-fails")
    machine.poll = []
    machine.run("--poll-once-write-baseline")
    before = machine.state_path.read_text(encoding="utf-8")
    machine.events_path.mkdir()
    machine.poll = [poll_once_pull_request(1)]
    code = machine.run()
    check("when the event file cannot be written, the run exits 1, keeps the state so the event "
          "is seen again, and opens a task",
          code == 1 and machine.state_path.read_text(encoding="utf-8") == before
          and "could not record" in machine.tasks_read()[0]["subject"] + machine.errors,
          f"{code} {machine.errors}")

    machine = machine_for("append-fails-two-runs-after-assigning")
    machine.assignments.write_text("", encoding="utf-8")
    machine.poll = []
    machine.run("--poll-once-write-baseline")
    machine.events_path.mkdir()
    machine.poll = [poll_once_pull_request(1)]
    first = machine.run()
    machine.poll = [poll_once_pull_request(1), poll_once_pull_request(2)]
    second = machine.run()
    kept_while_failing = machine.assignments.read_text(encoding="utf-8")
    machine.events_path.rmdir()
    third = machine.run()
    assigned = [line for line in machine.event_lines() if " REVIEW-ASSIGNED " in line]
    check("when two runs in a row cannot append after dealing reviews, the assignment file is put "
          "back each time, and the first run that can append records each pull request's "
          "REVIEW-ASSIGNED line once",
          (first, second, third) == (1, 1, 0) and kept_while_failing == ""
          and [line.split()[2] for line in assigned] == ["#1", "#2"]
          and [line.split()[0] for line in
               machine.assignments.read_text(encoding="utf-8").splitlines()] == ["1", "2"],
          f"{(first, second, third)} {kept_while_failing!r} {assigned} {machine.errors}")

    machine = machine_for("append-written-then-fsync-fails")
    machine.assignments.write_text("", encoding="utf-8")
    machine.poll = []
    machine.run("--poll-once-write-baseline")
    machine.poll = [poll_once_pull_request(1)]
    real_fsync = watcher_module.os.fsync
    fsyncs = []

    def fsync_fails_once(descriptor):
        fsyncs.append(descriptor)
        if len(fsyncs) == 1:
            raise OSError("injected: fsync failed after the write")
        real_fsync(descriptor)

    watcher_module.os.fsync = fsync_fails_once
    try:
        first = machine.run()
    finally:
        watcher_module.os.fsync = real_fsync
    kept = machine.assignments.read_text(encoding="utf-8")
    description = machine.tasks_read()[0]["description"] if machine.tasks_read() else ""
    second = machine.run()
    assigned = [line for line in machine.event_lines() if " REVIEW-ASSIGNED " in line]
    check("when the append writes every line and then fsync fails, the run exits 1 but keeps the "
          "deal, so the next run deals the pull request no second time",
          (first, second) == (1, 0) and [line.split()[0] for line in kept.splitlines()] == ["1"]
          and [line.split()[2] for line in assigned] == ["#1"],
          f"{(first, second)} {kept!r} {assigned} {machine.errors}")
    check("when the append writes every line and then fsync fails, the failure task names each "
          "kept pull request and its lane, and says its line may not survive a crash",
          "PR #1 REVIEW-ASSIGNED" in description and "may not survive a crash" in description
          and "forward the line to its merge-lane agent-seat" in description,
          description)

    machine = machine_for("append-stops-after-the-first-review-assigned-line")
    machine.assignments.write_text("", encoding="utf-8")
    machine.poll = []
    machine.run("--poll-once-write-baseline")
    machine.poll = [poll_once_pull_request(1), poll_once_pull_request(2)]
    real_open = watcher_module.Path.open

    class FirstLineOnly:
        def __init__(self, handle):
            self.handle = handle

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            self.handle.close()
            return False

        def tell(self):
            return self.handle.tell()

        def write(self, payload):
            end = payload.index(b"\n", payload.index(b" REVIEW-ASSIGNED ")) + 1
            self.handle.write(payload[:end])
            self.handle.flush()
            raise OSError("injected: no space left after the first REVIEW-ASSIGNED line")

    def open_first_line_only(path, mode="r", *args, **kwargs):
        handle = real_open(path, mode, *args, **kwargs)
        if path == machine.events_path and mode == "ab":
            return FirstLineOnly(handle)
        return handle

    watcher_module.Path.open = open_first_line_only
    try:
        first = machine.run()
    finally:
        watcher_module.Path.open = real_open
    kept = machine.assignments.read_text(encoding="utf-8")
    description = machine.tasks_read()[0]["description"] if machine.tasks_read() else ""
    machine.complete_tasks()
    second = machine.run()
    assigned = [line for line in machine.event_lines() if " REVIEW-ASSIGNED " in line]
    check("when the append stops after one whole REVIEW-ASSIGNED line, the run keeps that deal, "
          "names it in the failure task, and puts the other back, so the next run deals only the "
          "other and no pull request gets a second REVIEW-ASSIGNED line",
          (first, second) == (1, 0) and [line.split()[0] for line in kept.splitlines()] == ["1"]
          and "PR #1 REVIEW-ASSIGNED" in description and "PR #2" not in description
          and [line.split()[2] for line in assigned] == ["#1", "#2"],
          f"{(first, second)} {kept!r} {description!r} {assigned} {machine.errors}")

    def append_stopping_inside_second_line(name, truncate=None):
        machine = machine_for(name)
        machine.assignments.write_text("", encoding="utf-8")
        machine.poll = []
        machine.run("--poll-once-write-baseline")
        machine.poll = [poll_once_pull_request(1), poll_once_pull_request(2)]

        class CutInsideSecondLine(FirstLineOnly):
            def write(self, payload):
                second_start = payload.index(b"\n", payload.index(b" REVIEW-ASSIGNED ")) + 1
                self.handle.write(payload[:payload.index(b"PR #", second_start) + len(b"PR #")])
                self.handle.flush()
                raise OSError("injected: no space left inside the second REVIEW-ASSIGNED line")

        def open_cut(path, mode="r", *args, **kwargs):
            handle = real_open(path, mode, *args, **kwargs)
            if path == machine.events_path and mode == "ab":
                return CutInsideSecondLine(handle)
            return handle

        real_truncate = watcher_module.os.truncate
        watcher_module.Path.open = open_cut
        if truncate is not None:
            watcher_module.os.truncate = truncate
        try:
            first = machine.run()
        finally:
            watcher_module.Path.open = real_open
            watcher_module.os.truncate = real_truncate
        description = machine.tasks_read()[0]["description"] if machine.tasks_read() else ""
        return machine, first, description

    machine, first, description = append_stopping_inside_second_line("append-stops-inside-the-second-line")
    machine.complete_tasks()
    second = machine.run()
    lines = machine.event_lines()
    check("when the append stops inside the second REVIEW-ASSIGNED line, the next run cuts the "
          "event file back to its last whole line before it appends, so it writes a whole, readable "
          "line for the put-back pull request",
          (first, second) == (1, 0)
          and [line.split()[2] for line in lines if " REVIEW-ASSIGNED " in line] == ["#1", "#2"]
          and machine.events_path.read_bytes().endswith(b"\n")
          and all(len(re.findall(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", line)) == 1 for line in lines),
          f"{(first, second)} {lines} {machine.errors}")

    def truncate_fails(path, length):
        raise OSError("injected: the event file cannot be cut")

    machine, first, description = append_stopping_inside_second_line(
        "append-stops-inside-the-second-line-and-cannot-cut", truncate_fails)
    # The first run's append-failure task stays open, as it does until merge-lane-2 reads it.
    before = machine.events_path.read_bytes()
    real_truncate = watcher_module.os.truncate
    watcher_module.os.truncate = truncate_fails
    try:
        second = machine.run()
    finally:
        watcher_module.os.truncate = real_truncate
    after = machine.events_path.read_bytes()
    tasks = machine.tasks_read()
    cut_tasks = [task for task in tasks if "cut back" in task["subject"]]
    cut_description = cut_tasks[0]["description"] if cut_tasks else ""
    whole_end = before.rfind(b"\n") + 1
    check("when the next run cannot cut the cut line back, it appends nothing, exits 1, and opens "
          "a task of its own beside the open append-failure task, saying polls record nothing "
          "until the cut works",
          first == 1 and second == 1 and after == before and len(tasks) == 2
          and len(cut_tasks) == 1 and "recorded nothing" in cut_description,
          f"{(first, second)} {before[-80:]!r} {after[-80:]!r} {tasks!r} {machine.errors}")
    third = machine.run()
    lines = machine.event_lines()
    check("once the cut works again, the next run cuts the cut line back and records the put-back "
          "pull request on a whole line",
          third == 0 and [line.split()[2] for line in lines if " REVIEW-ASSIGNED " in line] == ["#1", "#2"]
          and all(len(re.findall(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", line)) == 1 for line in lines),
          f"{third} {lines} {machine.errors}")
    check("the cut-failure task, still open after a later run recorded lines, names no byte offset "
          "and no cut to make, so following it deletes none of those lines",
          str(whole_end) not in cut_description and "bytes" not in cut_description
          and "cut the file" not in cut_description and "by hand" in cut_description,
          cut_description)

    machine = machine_for("append-fails-and-cannot-be-read-back")
    machine.assignments.write_text("", encoding="utf-8")
    machine.poll = []
    machine.run("--poll-once-write-baseline")
    machine.poll = [poll_once_pull_request(1)]
    real_fsync = watcher_module.os.fsync
    real_held = watcher_module.event_file_count_of_appended_lines_found_whole_from_append_offset

    def fsync_fails(descriptor):
        raise OSError("injected: fsync failed")

    watcher_module.os.fsync = fsync_fails
    watcher_module.event_file_count_of_appended_lines_found_whole_from_append_offset = lambda *arguments: None
    try:
        code = machine.run()
    finally:
        watcher_module.os.fsync = real_fsync
        watcher_module.event_file_count_of_appended_lines_found_whole_from_append_offset = real_held
    description = machine.tasks_read()[0]["description"] if machine.tasks_read() else ""
    check("when the failed append's event file cannot be read back, the run keeps the deal, so "
          "no later poll deals it again, and the failure task names it as a line the event file "
          "may hold",
          code == 1
          and [line.split()[0] for line in
               machine.assignments.read_text(encoding="utf-8").splitlines()] == ["1"]
          and "could not be read back" in description and "may hold after the failed append" in description
          and "PR #1 REVIEW-ASSIGNED" in description,
          f"{code} {description!r} {machine.errors}")
    check("an event file that cannot be read back gives no count of the lines it holds",
          watcher_module.event_file_count_of_appended_lines_found_whole_from_append_offset(
              machine.directory / "absent.log", 0, [b"x\n"]) is None)

    machine = machine_for("append-and-put-back-fail")
    machine.assignments.write_text("", encoding="utf-8")
    machine.poll = []
    machine.run("--poll-once-write-baseline")
    machine.events_path.mkdir()
    machine.poll = [poll_once_pull_request(1)]
    real_write = watcher_module.merge_lane_pull_request_review_assignments_file_write
    writes = []

    def write_then_fail(path, text):
        writes.append(text)
        if len(writes) > 1:
            raise OSError("injected: the put-back write failed")
        real_write(path, text)

    watcher_module.merge_lane_pull_request_review_assignments_file_write = write_then_fail
    try:
        code = machine.run()
    finally:
        watcher_module.merge_lane_pull_request_review_assignments_file_write = real_write
    description = machine.tasks_read()[0]["description"] if machine.tasks_read() else ""
    check("when the append fails and the assignment file cannot be put back, the failure task "
          "names the pull request the file keeps with no REVIEW-ASSIGNED line recorded",
          code == 1 and "could not be put back" in description
          and "PR #1 REVIEW-ASSIGNED" in description,
          f"{code} {description} {machine.errors}")

    machine = machine_for("another-repository-default-directory")
    # Should these cases regress into a poll, it must not touch merge-lane-2's real state or tasks.
    saved_default = watcher_module.OPEN_PRS_WATCH_POLL_ONCE_STATE_EVENTS_AND_LOCK_DEFAULT_DIRECTORY
    watcher_module.OPEN_PRS_WATCH_POLL_ONCE_STATE_EVENTS_AND_LOCK_DEFAULT_DIRECTORY = machine.directory
    safe = ["--task-list-directory", str(machine.tasks), "--needs-a-look-directory",
            str(machine.notices), "--token-file", str(token_file)]
    errors = io.StringIO()
    try:
        with contextlib.redirect_stderr(errors):
            code = watcher_module.main(["--poll-once", "--repo", "someone/elsewhere", *safe])
    finally:
        watcher_module.OPEN_PRS_WATCH_POLL_ONCE_STATE_EVENTS_AND_LOCK_DEFAULT_DIRECTORY = saved_default
    check("--poll-once with another --repo and no --poll-once-directory exits 2 and names the "
          "option, before any poll",
          code == 2 and "--poll-once-directory" in errors.getvalue()
          and not machine.state_path.exists(), errors.getvalue())

    errors = io.StringIO()
    with contextlib.redirect_stderr(errors):
        try:
            code = watcher_module.main(["--poll-once", "--merge-lane-pr-review-assignments-list-for",
                                        "merge-lane-1", "--poll-once-directory",
                                        str(machine.directory), *safe])
        except SystemExit as stop:
            code = stop.code
    check("--poll-once with an assignment listing is refused with exit 2", code == 2,
          f"{code} {errors.getvalue()}")

    machine = machine_for("truncated-events")
    machine.poll = []
    machine.run("--poll-once-write-baseline")
    machine.poll = [poll_once_pull_request(1)]
    machine.run()
    machine.events_path.write_text("", encoding="utf-8")
    machine.complete_tasks()
    code = machine.run()
    check("an event file shorter than the lines delivered exits 1 and says it was truncated",
          code == 1 and "truncated" in machine.errors, machine.errors)

    machine = machine_for("no-task-list")
    machine.poll = []
    machine.run("--poll-once-write-baseline")
    machine.tasks.rmdir()
    machine.poll = [poll_once_pull_request(1)]
    code = machine.run()
    delivered = json.loads(machine.state_path.read_text(encoding="utf-8"))["event_lines_delivered"]
    check("when the task cannot be written, the run exits 1 and the event stays undelivered",
          code == 1 and delivered == 0 and len(machine.event_lines()) == 1, machine.errors)
    machine.tasks.mkdir()
    machine.poll = [poll_once_pull_request(1)]
    code = machine.run()
    check("the next run delivers the event that waited",
          code == 0 and "lines 1 to 1 of" in machine.tasks_read()[0]["description"],
          machine.tasks_read())

    machine = machine_for("locked")
    machine.poll = []
    machine.run("--poll-once-write-baseline")
    machine.poll = [poll_once_pull_request(1)]
    with (machine.directory / watcher_module.LOCK_FILE_NAME).open("w", encoding="utf-8") as held:
        watcher_module.fcntl.flock(held, watcher_module.fcntl.LOCK_EX)
        code = machine.run()
    check("a run that finds the lock held exits 0 and does nothing",
          code == 0 and not machine.event_lines() and machine.tasks_read() == [], machine.errors)

    machine = machine_for("baseline-locked")
    machine.poll = []
    machine.directory.mkdir(parents=True, exist_ok=True)
    with (machine.directory / watcher_module.LOCK_FILE_NAME).open("w", encoding="utf-8") as held:
        watcher_module.fcntl.flock(held, watcher_module.fcntl.LOCK_EX)
        code = machine.run("--poll-once-write-baseline")
    check("--poll-once-write-baseline that finds the lock held says no baseline was written, "
          "and exits 1",
          code == 1 and "no baseline was written" in machine.errors
          and not (machine.directory
                   / watcher_module.WATCH_OPEN_PULL_REQUESTS_POLL_STATE_BETWEEN_CRON_RUNS_FILE_NAME).exists(),
          machine.errors)

    machine = machine_for("bad-token")
    machine.token_file = scratch_root / "no-such-token"
    code = machine.run()
    check("an unusable token exits 1 and opens a task",
          code == 1 and "token" in machine.tasks_read()[0]["subject"], machine.tasks_read())

    machine = machine_for("review-assigned")
    machine.assignments.write_text("1 merge-lane-1\n", encoding="utf-8")
    machine.poll = [poll_once_pull_request(1)]
    machine.run("--poll-once-write-baseline")
    machine.poll = [poll_once_pull_request(1), poll_once_pull_request(2)]
    code = machine.run()
    check("a run assigns a new pull request to the merge-lane agent-seat with fewer waiting, writes "
          "it to the assignment file, and puts its REVIEW-ASSIGNED line in the event file",
          code == 0 and machine.assignments.read_text(encoding="utf-8")
          == "1 merge-lane-1\n2 merge-lane-3\n"
          and len(machine.event_lines()) == 2 and "PR #2 OPENED" in machine.event_lines()[0]
          and "PR #2 REVIEW-ASSIGNED merge-lane-3" in machine.event_lines()[1],
          f"{code} {machine.event_lines()} {machine.errors}")
    machine.now += 60
    machine.poll = "GitHub is down"
    machine.run()
    check("a failed poll assigns nothing",
          machine.assignments.read_text(encoding="utf-8") == "1 merge-lane-1\n2 merge-lane-3\n"
          and len(machine.event_lines()) == 2, machine.event_lines())

    machine = machine_for("another-repository")
    machine.assignments.write_text("1 merge-lane-1\n", encoding="utf-8")
    other_repository = ["--repo", "someone/elsewhere"]
    machine.poll = [poll_once_pull_request(1)]
    machine.run("--poll-once-write-baseline", other_repository)
    machine.poll = [poll_once_pull_request(1), poll_once_pull_request(2)]
    saved_default = watcher_module.MERGE_LANE_PULL_REQUEST_REVIEW_ASSIGNMENTS_DEFAULT_FILE
    watcher_module.MERGE_LANE_PULL_REQUEST_REVIEW_ASSIGNMENTS_DEFAULT_FILE = machine.assignments
    try:
        code = machine.run("--poll-once", other_repository)
    finally:
        watcher_module.MERGE_LANE_PULL_REQUEST_REVIEW_ASSIGNMENTS_DEFAULT_FILE = saved_default
    check("a run with another --repo and no assignment file named reports the opening, assigns "
          "no review and leaves the default file alone",
          code == 0 and machine.assignments.read_text(encoding="utf-8") == "1 merge-lane-1\n"
          and len(machine.event_lines()) == 1 and "PR #2 OPENED" in machine.event_lines()[0],
          f"{code} {machine.event_lines()} {machine.errors}")

    machine = machine_for("assignment-file-missing")
    machine.assignments.unlink()
    machine.poll = [poll_once_pull_request(1)]
    machine.run("--poll-once-write-baseline")
    first_code = machine.run()
    machine.now += 60
    second_code = machine.run()
    stopped = [line for line in machine.event_lines() if "WATCH: review assignment stopped" in line]
    check("a missing assignment file puts one WATCH line with the seed step in the event file, "
          "not one per run, and opens a task naming it",
          (first_code, second_code) == (0, 0) and len(stopped) == 1
          and any("--merge-lane-pr-review-assignments-file-write-from-seed-and-reviewed-prs-then-exit"
                  in line for line in machine.event_lines())
          and len(machine.tasks_read()) == 1 and not machine.assignments.exists(),
          f"{machine.event_lines()} {machine.tasks_read()} {machine.errors}")
    machine.assignments.write_text("", encoding="utf-8")
    machine.now += 60
    machine.run()
    check("once the file exists, the next run assigns the pull request",
          machine.assignments.read_text(encoding="utf-8") == "1 merge-lane-1\n"
          and "REVIEW-ASSIGNED merge-lane-1" in machine.event_lines()[-1], machine.event_lines())

    machine = machine_for("append-stops-inside-a-watch-event")
    machine.assignments.unlink()
    machine.poll = [poll_once_pull_request(1)]
    machine.run("--poll-once-write-baseline")
    before = machine.events_path.read_bytes() if machine.events_path.exists() else b""
    real_open = watcher_module.Path.open

    class StopsAfterWatchHeader:
        def __init__(self, handle):
            self.handle = handle

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            self.handle.close()
            return False

        def tell(self):
            return self.handle.tell()

        def write(self, payload):
            self.handle.write(payload[:payload.index(b"\n  ") + 1])
            self.handle.flush()
            raise OSError("injected: no space left after the WATCH event's first line")

    def open_stops_after_header(path, mode="r", *args, **kwargs):
        handle = real_open(path, mode, *args, **kwargs)
        return StopsAfterWatchHeader(handle) if path == machine.events_path and mode == "ab" else handle

    watcher_module.Path.open = open_stops_after_header
    try:
        code = machine.run()
    finally:
        watcher_module.Path.open = real_open
    after = machine.events_path.read_bytes() if machine.events_path.exists() else b""
    check("when an append stops after a WATCH event's first line, before its repair steps, the "
          "run cuts the event file back to where that event began, so no later poll delivers the "
          "header without its steps",
          code == 1 and after == before, f"{code} {before[-120:]!r} {after[-120:]!r} {machine.errors}")

    machine = machine_for("directory-unusable")
    machine.directory.write_text("a file", encoding="utf-8")
    code = machine.run()
    check("a state directory that cannot be used exits 1 and opens a task",
          code == 1 and "directory" in machine.tasks_read()[0]["subject"], machine.tasks_read())


if __name__ == "__main__":
    run_unit_cases()
    run_merge_lane_pull_request_review_assignment_unit_cases()
    run_merge_lane_pull_request_review_assignment_watcher_cases()
    run_needs_a_look_unit_cases()
    run_batch_events_cases()
    with tempfile.TemporaryDirectory() as poll_once_scratch:
        poll_once_token_file = Path(poll_once_scratch) / "token"
        poll_once_token_file.write_text(FIXTURE_TOKEN, encoding="utf-8")
        run_poll_once_cases(Path(poll_once_scratch), poll_once_token_file)
    run_subprocess_cases()
    print()
    if failures:
        print(f"{len(failures)} case(s) failed: {', '.join(failures)}")
        sys.exit(1)
    print("all cases passed")
