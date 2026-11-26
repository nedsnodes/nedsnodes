#!/usr/bin/env python3
"""Merge the merge queue's approved lines in merge order, one merge at a time, until none is left.

Usage:
  scripts/merge-lane-merge-queue-approved-lines-merge-in-order-until-none-left.py merge-batch-start [--quiet]
  scripts/merge-lane-merge-queue-approved-lines-merge-in-order-until-none-left.py merge-batch-resume [--merge-only <pull request>]
  scripts/merge-lane-merge-queue-approved-lines-merge-in-order-until-none-left.py merge-batch-list-waiting
  scripts/merge-lane-merge-queue-approved-lines-merge-in-order-until-none-left.py merge-batch-run-in-queue-order [--merge-only <pull request>]
  Each takes --merge-queue-file, --merge-batches-directory, --merge-program-outputs-directory,
  --merge-program, --follow-up-program and --gh, which only tests change.

merge-lane-2 runs merge-batch-start, which starts merge-batch-run-in-queue-order as a
process in its own session, so the merge batch outlives the command that started it, and
prints one line opening with its outcome state, checked in this order:
  STOPPED            the stop file exists, with no in-progress file a dead batch left beside
                     it; the line quotes it; nothing was started
  ALREADY RUNNING    a merge batch holds merge-batch.lock, and will see any line added
  DIED MID-MERGE     a merge batch ended during a merge, so main is untested; the stop file
                     and a stopped notice now say so, or a FAILED line says which could not
                     be written (exit 1); nothing was started
  STARTED            a merge batch was started; its log is merge-batch.log
  NOT STARTED        the merge batch could not be started; the line says why (exit 1)
With --quiet, STOPPED and ALREADY RUNNING print nothing. The DIED MID-MERGE check is made
only while merge-batch.lock is held: by merge-batch-start, by merge-batch-run-in-queue-order
run directly, and by a merge batch each time it takes the lock back. When the last two find
the stop file too, which merge-batch-start reports as STOPPED before this check, the check
quotes it and leaves it as it is. A merge batch given --merge-only that finds the lock held
writes the stop file and a stopped notice saying its merge did not run, and exits 1.

The merge queue file is read as merge-lane-2's lanes write it: the last line for a pull
request decides its state. "<pr> <nn-head-commit> <review commissioned at> <author> (...)"
makes it waiting; the same line opening with "HOLD-<reason> " holds it for its lane;
"MERGED <pr> ..." and "DROPPED-<reason> <pr> ..." mean done; "HELD <pr> ..." means it waits
for a new approved line. "NOTE" lines, "#" lines and empty lines are skipped. A waiting pull
request's age is the place of its last line: the earlier, the older.

Waiting pull requests merge in this order, chosen again before each merge:
  1. those labeled high-priority on GitHub, oldest first;
  2. while the count of prose-only merges in a row is under 3, the oldest prose-only one,
     before any code one;
  3. once that count is 3 or more, the oldest code one, before any prose-only one.
When no line of the kind a rule wants is waiting, the oldest other line goes. A pull request
is prose-only when every file it changes, from its merge base with main to its queued
nn-head-commit, which is the commit about to be merged, is Markdown under docs/ that
scripts/pull-request-review-plan.py classes as prose, so no line it changes is inside a
fenced code block; any other pull request is code, and so is one whose files could not be
read, which the log says. The count of prose-only merges in a row is kept in
merge-batch-prose-only-merges-in-a-row.txt in the merge batches directory, so it carries from
one merge batch to the next. Every merge this program makes counts, whichever rule or
--merge-only chose it: a prose-only merge adds 1, past 3 when no code line waits, and a code
merge sets the count to 0. Whether a pull request is prose-only is read before it merges,
since once it has merged its head is an ancestor of main and nothing seems changed. The count
is read before each merge: a missing file counts 0, and a file that holds no count stops the
merge batch before the merge. A count that cannot be written after a merge stops the merge
batch, after the merge's MERGED notice, or with that merge's notice in the stop.

merge-batch-run-in-queue-order takes merge-batch.lock without waiting, and exits 0 when
another process holds it. It makes passes over the queue file until a pass neither merges
nor appends, then releases the lock and reads the file's size again, and makes another
pass when a line was appended meanwhile. A pass chooses each next pull request from the
queue file as it is once the next merge may start, so a HOLD- line appended during a merge
holds that pull request; and it reads the queue file again just before the merge program
starts, choosing again when the chosen line is no longer the pull request's last line, so a
HOLD- line appended while it was chosen and checked holds it too. For each waiting pull
request it reads GitHub: merged already gets a MERGED line; closed, or an nn-head-commit other than the queued one,
gets a HELD line; a base branch other than main that is exactly one open pull request's
branch is passed over until that pull request merges; any other base branch gets a HELD
line. A HELD line is appended only while the line that was checked is still the pull
request's last line; otherwise the pull request is read again at once, from the line a lane
appended meanwhile. A pull request passed over as stacked is tried again after the next merge in the same
pass. Otherwise it runs the merge program, with reviewed-since the merge account's latest
review of the queued nn-head-commit, or the queued time when there is none, since that
review is the record that its author read everything posted before it, and with this
program's --merge-program-outputs-directory as its outputs directory.

Before each merge, one function decides whether it may start. It stops the merge batch
when the stop file, merge-queue-stopped.txt in the merge program's outputs directory,
exists: the merge program writes it when it exits 3 or 4, whoever ran it, and this program
creates it on each of its own stops, never replacing one already there, which its STOPPED
notice quotes instead. It waits, checking every 15 seconds, while any merge
program holds merge-program.lock, which the merge program holds through its after-merge
test run, so no merge starts while main's latest test run is still running.

Each outcome writes one notice file for merge-lane-2 in the notice directory, whose first
line opens with its outcome state: MERGED <pr> <merge commit> <author>, with the follow-up
request the follow-up program printed; HELD <pr> <author>, with the queue line written;
STOPPED, with the reason and the merge program's STOP, FAIL and SUMMARY lines, and, when
GitHub shows the pull request merged, its merge commit, author and follow-up request. A
stop file written outside the merge batch ends it with a STOPPED notice quoting that file;
the stop file itself is left as it is. merge-lane-2
sends the merge notices, handles each notice, moves it into handled/, and runs
merge-batch-resume once a stopped merge batch is handled.

merge-batch-resume refuses while a merge batch holds merge-batch.lock; otherwise, holding
that lock, it removes the stop file and the in-progress file, then starts a merge batch. With --merge-only, that
pull request, which must be waiting, merges first; the merge batch goes on only when it
merged and its after-merge test run passed, and otherwise stops again, with the stop file
and a stopped notice naming its outcome.

merge-batch-list-waiting prints, without merging, each waiting pull request with its state
on GitHub and its base branch.

Each path option is made absolute where it enters, and the merge-batch-resume command that
a STOPPED line and a stopped notice print names the merge queue file and both directories
in use.

Exit codes: 0 done as printed, including a merge batch that stopped for any reason exit 1
does not name; 1 a file or GitHub could not be read or written, the stop file or a stopped
notice included, whether a merge batch then stopped or another subcommand failed, or the
merge batch could not be started, as printed; 2 a refusal, as printed.
"""
import argparse
import datetime
import fcntl
import importlib.util
import json
import os
import re
import shlex
import subprocess
import sys
import time
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
_common_spec = importlib.util.spec_from_file_location(
    "merge_lane_pull_request_helpers_common",
    SCRIPTS / "merge-lane-pull-request-helpers-common-options-paths-and-token.py")
common = importlib.util.module_from_spec(_common_spec)
_common_spec.loader.exec_module(common)
_merge_spec = importlib.util.spec_from_file_location(
    "merge_lane_pull_request_merge",
    SCRIPTS / "merge-lane-pull-request-merge-through-merge-gate-with-stacked-pull-request-retarget.py")
merge_program = importlib.util.module_from_spec(_merge_spec)
_merge_spec.loader.exec_module(merge_program)
_review_plan_spec = importlib.util.spec_from_file_location(
    "pull_request_review_plan", SCRIPTS / "pull-request-review-plan.py")
review_plan = importlib.util.module_from_spec(_review_plan_spec)
_review_plan_spec.loader.exec_module(review_plan)

REPOSITORY = "nedsnodes/nedsnodes"
MERGE_ACCOUNT = "ned-review-merge"
DEFAULT_MERGE_QUEUE_FILE = Path(
    "/home/nedlern/nedsnodes-logs/seats/merge-lane-2/merge-queue-2026-11-21.txt")
DEFAULT_MERGE_BATCHES_DIRECTORY = Path(
    "/home/nedlern/nedsnodes-logs/seats/merge-lane-2/merge-queue-merge-batches")
MERGE_PROGRAM = SCRIPTS / "merge-lane-pull-request-merge-through-merge-gate-with-stacked-pull-request-retarget.py"
FOLLOW_UP_PROGRAM = SCRIPTS / "pull-request-follow-up-request-after-merge-finding-answers-and-next-step.py"
MERGE_BATCH_LOCK_FILE_NAME = "merge-batch.lock"
MERGE_BATCH_LOG_FILE_NAME = "merge-batch.log"
PROSE_ONLY_MERGES_IN_A_ROW_FILE_NAME = "merge-batch-prose-only-merges-in-a-row.txt"
PROSE_ONLY_MERGES_IN_A_ROW_BEFORE_A_CODE_MERGE = 3
HIGH_PRIORITY_LABEL = "high-priority"
# The checkout whose git objects the prose-only check reads, fetching any commit missing.
REPOSITORY_ROOT = common.REPOSITORY_ROOT
MERGE_IN_PROGRESS_FILE_NAME = "merge-batch-merge-in-progress.txt"
MERGE_BATCH_OUTCOME_NOTICES_FOR_MERGE_LANE_2_DIRECTORY_NAME = "merge-batch-outcome-notices-for-merge-lane-2"
NEXT_MERGE_STARTS, NEXT_MERGE_WAITS, NEXT_MERGE_STOPS = "STARTS", "WAITS", "STOPS"
SECONDS_BETWEEN_NEXT_MERGE_MAY_START_CHECKS = 15
MERGE_PROGRAM_EXIT_MEANINGS = {
    0: "it reported a merge that GitHub does not show",
    1: "it refused, yet GitHub shows the pull request merged",
    2: "it could not run, and merged nothing",
    3: "it merged, but a step after the merge, such as main's after-merge test run, did not pass",
    4: "whether it merged is unknown"}

APPROVED_LINE = re.compile(r"^(?P<hold>HOLD-\S+ )?(?P<pr>[0-9]+) (?P<head>[0-9a-f]{40}) "
                           r"(?P<since>\S+) (?P<author>\S+)")
DONE_LINE = re.compile(r"^(MERGED|DROPPED-\S+) (?P<pr>[0-9]+)\b")
HELD_LINE = re.compile(r"^HELD (?P<pr>[0-9]+)\b")
SKIPPED_LINE = re.compile(r"^(NOTE\b|#|\s*$)")
MERGE_PROGRAM_REPORT_LINE = re.compile(r"^(STOP|FAIL|SUMMARY)\b")


class Stop(Exception):
    """The merge batch stops; the message says why."""


class ReadOrWriteFailed(Stop):
    """A file or GitHub could not be read or written, so the merge batch exits 1."""


class StopFileFound(Exception):
    """The stop file appeared during the merge batch, written outside it."""


STACKED_PASSED_OVER_OUTCOME = ("it is stacked on a pull request that has not merged, so it was "
                               "passed over; merge that one first with --merge-only")
# Kept apart from every outcome a stop names, since a pull request with this one is read again.
READ_AGAIN_OUTCOME = "a new line for it was appended while it was checked"


def now():
    return f"{datetime.datetime.now(datetime.timezone.utc):%Y-%m-%dT%H:%M:%SZ}"


def absolute_path(text):
    # The merge program runs in its own checkout, so a relative path would name another file there.
    return Path(text).resolve()


def parse_arguments(argv):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--merge-queue-file", type=absolute_path, default=DEFAULT_MERGE_QUEUE_FILE)
    parser.add_argument("--merge-batches-directory", type=absolute_path,
                        default=DEFAULT_MERGE_BATCHES_DIRECTORY)
    parser.add_argument("--merge-program-outputs-directory", type=absolute_path,
                        default=common.DEFAULT_MERGE_LANE_WORKTREES_AND_OUTPUTS_DIRECTORY)
    parser.add_argument("--merge-program", type=absolute_path, default=MERGE_PROGRAM)
    parser.add_argument("--follow-up-program", type=absolute_path, default=FOLLOW_UP_PROGRAM)
    parser.add_argument("--gh", default="gh")
    subcommands = parser.add_subparsers(dest="subcommand", required=True)
    start = subcommands.add_parser("merge-batch-start")
    start.add_argument("--quiet", action="store_true")
    for name in ("merge-batch-resume", "merge-batch-run-in-queue-order"):
        subcommands.add_parser(name).add_argument("--merge-only", type=int)
    subcommands.add_parser("merge-batch-list-waiting")
    return parser.parse_args(argv)


class MergeQueuePullRequestMergeBatchRunner:
    def __init__(self, arguments, wait=time.sleep):
        self.arguments = arguments
        self.wait = wait
        self.directory = arguments.merge_batches_directory
        self.stop_file = (arguments.merge_program_outputs_directory
                          / merge_program.MERGE_QUEUE_STOP_FILE_NAME)
        self.in_progress_file = self.directory / MERGE_IN_PROGRESS_FILE_NAME
        self.notices = self.directory / MERGE_BATCH_OUTCOME_NOTICES_FOR_MERGE_LANE_2_DIRECTORY_NAME
        self.prose_only_merges_in_a_row_file = self.directory / PROSE_ONLY_MERGES_IN_A_ROW_FILE_NAME
        self.merged_cleanly = None
        self.outcome = None
        # Set before each merge, from the count and the line as they are before it.
        self.prose_only_merges_in_a_row_after_this_merge = 0
        self.prose_only_by_merge_base_and_head = {}
        # The in-progress file may be removed only while this is True, since without the lock
        # it may be a running batch's.
        self.holds_merge_batch_lock = False

    # The merge queue file

    def queue_lines(self):
        with open(self.arguments.merge_queue_file) as queue, self.queue_locked():
            return queue.read().splitlines()

    def queue_locked(self):
        lock = open(f"{self.arguments.merge_queue_file}.lock", "a")
        fcntl.flock(lock, fcntl.LOCK_EX)
        return lock

    def append(self, line):
        with self.queue_locked(), open(self.arguments.merge_queue_file, "a") as queue:
            queue.write(line + "\n")
        self.log(f"appended to the merge queue file: {line}")

    def append_while_still_last(self, number, checked_line, line):
        """Append line only while checked_line is still pull request number's last line.

        Read and appended under one hold of the queue file's lock, so a line a lane appends
        meanwhile is never put behind the outcome of a check of the line before it.
        """
        with self.queue_locked():
            if self.last_line(number) != checked_line:
                self.log(f"pull request {number} got a new line while it was checked, so "
                         f"{line!r} is not appended and the new line is read at once")
                return False
            with open(self.arguments.merge_queue_file, "a") as queue:
                queue.write(line + "\n")
        self.log(f"appended to the merge queue file: {line}")
        return True

    def last_line(self, number):
        """Return pull request number's last line in the queue file; the caller holds its lock."""
        last = None
        for queued in Path(self.arguments.merge_queue_file).read_text().splitlines():
            match = APPROVED_LINE.match(queued) or DONE_LINE.match(queued) or HELD_LINE.match(queued)
            if match and int(match["pr"]) == number:
                last = queued
        return last

    def waiting(self, lines):
        """Return the waiting pull requests' approved lines, in the order of their last lines."""
        last = {}
        for number, line in enumerate(lines, start=1):
            approved = APPROVED_LINE.match(line)
            other = DONE_LINE.match(line) or HELD_LINE.match(line)
            if approved:
                last.pop(int(approved["pr"]), None)
                last[int(approved["pr"])] = approved
            elif other:
                last.pop(int(other["pr"]), None)
                last[int(other["pr"])] = None
            elif not SKIPPED_LINE.match(line):
                raise Stop(f"line {number} of {self.arguments.merge_queue_file} is of no kind "
                           f"this program reads: {line!r}")
        return [line for line in last.values() if line is not None and not line["hold"]]

    # GitHub

    def gh(self, *arguments):
        completed = subprocess.run([self.arguments.gh, *arguments], capture_output=True,
                                   text=True, stdin=subprocess.DEVNULL)
        if completed.returncode != 0:
            raise ReadOrWriteFailed(f"gh {' '.join(arguments[:3])} exited {completed.returncode}: "
                                    f"{completed.stderr.strip() or 'no error printed'}")
        return completed.stdout

    def gh_json(self, *arguments):
        text = self.gh(*arguments)
        try:
            return json.loads(text)
        except ValueError:
            raise ReadOrWriteFailed(f"gh {' '.join(arguments[:3])} printed what is not JSON: "
                                    f"{text[:200]!r}")

    def pull_request(self, number):
        return self.gh_json("pr", "view", str(number), "--repo", REPOSITORY, "--json",
                            "state,headRefOid,baseRefName,mergeCommit")

    def reviewed_since(self, number, head, queued_since):
        reviews = self.gh_json("api", f"repos/{REPOSITORY}/pulls/{number}/reviews",
                               "--paginate", "--slurp")
        times = [review.get("submitted_at") for page in reviews for review in page
                 if (review.get("user") or {}).get("login") == MERGE_ACCOUNT
                 and review.get("commit_id") == head and review.get("submitted_at")]
        return max(times) if times else queued_since

    def open_pull_requests_with_branch(self, branch):
        return self.gh_json("pr", "list", "--repo", REPOSITORY, "--head", branch,
                            "--state", "open", "--json", "number")

    def high_priority_pull_requests(self):
        # Read before every choice, since a pull request can be labeled during a merge batch.
        return {entry["number"] for entry in self.gh_json(
            "pr", "list", "--repo", REPOSITORY, "--label", HIGH_PRIORITY_LABEL, "--state", "open",
            "--limit", "1000", "--json", "number")}

    # Merge order

    def prose_only(self, line):
        number, head = int(line["pr"]), line["head"]
        try:
            merge_base = self.gh("api", f"repos/{REPOSITORY}/compare/main...{head}",
                                 "--jq", ".merge_base_commit.sha").strip()
            if not re.fullmatch(r"[0-9a-f]{40}", merge_base):
                raise Stop(f"GitHub gave {merge_base[:200]!r} as its merge base with main")
            key = (merge_base, head)
            if key not in self.prose_only_by_merge_base_and_head:
                self.prose_only_by_merge_base_and_head[key] = self.changes_only_docs_prose(
                    merge_base, head)
            return self.prose_only_by_merge_base_and_head[key]
        except (Stop, review_plan.ReviewPlanRefusal, ValueError) as error:
            self.log(f"pull request {number}: whether {head} is prose-only could not be read, so "
                     f"it counts as code: {error}")
            return False

    def changes_only_docs_prose(self, merge_base, head):
        repository = REPOSITORY_ROOT
        missing = [commit for commit in (merge_base, head) if review_plan.run_git_in_repository(
            repository, "cat-file", "-e", f"{commit}^{{commit}}").returncode]
        if missing:
            # By commit and without FETCH_HEAD, as the merge program fetches, since a fetch
            # that updates origin/main can collide with another checkout's fetch.
            fetch = review_plan.run_git_in_repository(
                repository, "fetch", "--quiet", "--no-write-fetch-head", "origin", *missing)
            if fetch.returncode:
                raise Stop(f"git fetch of {' '.join(missing)} in {repository} exited "
                           f"{fetch.returncode}: {fetch.stderr.strip()}")
        return all(entry["path"].startswith("docs/") and entry["path"].endswith(".md")
                   and entry["class"] == "prose"
                   for entry in review_plan.changed_files_with_classes_and_tiers(
                       repository, merge_base, head))

    def prose_only_merges_in_a_row(self):
        try:
            text = self.prose_only_merges_in_a_row_file.read_text().strip()
        except FileNotFoundError:
            return 0
        if not text.isdigit():
            raise Stop(f"{self.prose_only_merges_in_a_row_file} holds {text[:200]!r}, not a count "
                       f"of 0 or more, so the next pull request cannot be chosen. The file holds "
                       f"the number of prose-only merges since the last code merge, as this "
                       f"program's docstring defines them. Remove the file, so that the count "
                       f"starts again from 0, then run: {self.resume_command()}")
        return int(text)

    def next_in_merge_order(self, waiting, in_a_row):
        """Return the line to merge next from the waiting lines, given oldest first, and
        whether it is prose-only."""
        high_priority = self.high_priority_pull_requests()
        for line in waiting:
            if int(line["pr"]) in high_priority:
                self.log(f"next: pull request {line['pr']}, the oldest labeled {HIGH_PRIORITY_LABEL}")
                return line, self.prose_only(line)
        wants_prose_only = in_a_row < PROSE_ONLY_MERGES_IN_A_ROW_BEFORE_A_CODE_MERGE
        wanted = "prose-only" if wants_prose_only else "code"
        line = next((line for line in waiting if self.prose_only(line) == wants_prose_only), None)
        if line is None:
            self.log(f"next: pull request {waiting[0]['pr']}, the oldest, since after {in_a_row} "
                     f"prose-only merges in a row a {wanted} one goes next and none waits")
            return waiting[0], not wants_prose_only
        self.log(f"next: pull request {line['pr']}, the oldest {wanted} one, after {in_a_row} "
                 f"prose-only merges in a row")
        return line, wants_prose_only

    def prose_only_merge_counted(self):
        """Write the count the merge just made leaves; return what failed, or None."""
        count = self.prose_only_merges_in_a_row_after_this_merge
        try:
            self.prose_only_merges_in_a_row_file.write_text(f"{count}\n")
        except OSError as error:
            return (f"the count of prose-only merges in a row, {count}, could not be written to "
                    f"{self.prose_only_merges_in_a_row_file} ({error}), so the next pull request "
                    f"cannot be chosen. Write {count} into that file, then run: {self.resume_command()}")
        return None

    # Files for merge-lane-2

    def log(self, text):
        print(f"{now()} {text}", flush=True)

    def notice(self, name, text):
        try:
            self.notices.mkdir(parents=True, exist_ok=True)
            (self.notices / name).write_text(text)
        except OSError as error:
            raise ReadOrWriteFailed(f"could not write the notice {self.notices / name}: {error}; "
                                    f"it said: {text.splitlines()[0]}") from None
        self.log(f"notice {name}: {text.splitlines()[0]}")

    def resume_command(self):
        return " ".join(shlex.quote(part) for part in (
            "python3", str(Path(__file__).resolve()),
            "--merge-queue-file", str(self.arguments.merge_queue_file),
            "--merge-batches-directory", str(self.directory),
            "--merge-program-outputs-directory", str(self.arguments.merge_program_outputs_directory),
            "merge-batch-resume")) + " [--merge-only <pull request>]"

    def stopped(self, reason):
        """Create the stop file and write a STOPPED notice, each failure said in the log;
        return whether every write succeeded.

        A stop file already there is kept and quoted, since the merge program may have just
        written its reason. The in-progress file is removed only once the stop file exists and
        the notice is written, so a start keeps reporting DIED MID-MERGE until both are, and
        only while this process holds merge-batch.lock.
        """
        written = True
        stop_text = f"{reason}, {now()}"
        kept = None
        try:
            self.stop_file.parent.mkdir(parents=True, exist_ok=True)
            try:
                with open(self.stop_file, "x") as stop:
                    stop.write(stop_text + "\n")
            except FileExistsError:
                kept = self.stop_file.read_text().strip()
        except OSError as error:
            written = False
            reason += (f"\nThe stop file {self.stop_file} could not be written ({error}), so "
                       f"a later merge-batch-start may merge again: append a HOLD- line for "
                       f"each waiting pull request until main is handled.")
        if kept is not None:
            reason += f"; {self.stop_file}, written outside this merge batch, says: {kept}"
        try:
            self.notice(f"stopped-{now()}.txt",
                        f"STOPPED {reason}\n"
                        f"No merge starts until you resume. Find the cause from the reason above "
                        f"and the merge program's output it names.\n"
                        f"When main is failing, get the failure fixed, then merge the fix first "
                        f"by resuming with --merge-only <the fix's pull request number>.\n"
                        f"When a pull request must not merge now, append a line for it to "
                        f"{self.arguments.merge_queue_file}, under flock on "
                        f"{self.arguments.merge_queue_file}.lock: HOLD-<reason> followed by "
                        f"its last approved line, or DROPPED-<reason> <pull request number>.\n"
                        f"Then run, which removes the stop file: {self.resume_command()}\n")
        except Stop as unwritable:
            written = False
            self.log(f"STOPPED, and {unwritable}")
        if written and self.holds_merge_batch_lock and self.stop_file.exists():
            self.in_progress_file.unlink(missing_ok=True)
        self.log(f"STOPPED {reason}")
        return written

    # One merge batch

    def run_in_queue_order(self, merge_only):
        self.directory.mkdir(parents=True, exist_ok=True)
        lock = open(self.directory / MERGE_BATCH_LOCK_FILE_NAME, "a")
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            if merge_only is None:
                self.log("ALREADY RUNNING: another merge batch holds the lock")
                return 0
            # The batch holding the lock reads the stop file before its next merge and ends.
            self.stopped(f"pull request {merge_only}, named by --merge-only to merge first, did "
                         f"not run: another merge batch held {MERGE_BATCH_LOCK_FILE_NAME} when "
                         f"this one started, so the order --merge-only asked for was lost")
            return 1
        self.holds_merge_batch_lock = True
        try:
            if (written := self.died_mid_merge_stopped()) is not None:
                return 0 if written else 1
            while True:
                size = os.path.getsize(self.arguments.merge_queue_file)
                while self.one_pass(merge_only):
                    merge_only = None
                    size = os.path.getsize(self.arguments.merge_queue_file)
                fcntl.flock(lock, fcntl.LOCK_UN)
                self.holds_merge_batch_lock = False
                if os.path.getsize(self.arguments.merge_queue_file) == size:
                    self.log("DONE: nothing left to merge")
                    return 0
                try:
                    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError:
                    return 0
                self.holds_merge_batch_lock = True
                # Another merge batch may have held the lock and died meanwhile.
                if (written := self.died_mid_merge_stopped()) is not None:
                    return 0 if written else 1
        except StopFileFound as found:
            self.log(f"the stop file exists, so the merge batch ends: {found}")
            return 0 if self.stopped("the stop file appeared during this merge batch, so it "
                                     "ends before its next merge") else 1
        except (ReadOrWriteFailed, OSError) as failed:
            self.stopped(str(failed))
            return 1
        except Stop as stop:
            return 0 if self.stopped(str(stop)) else 1
        finally:
            self.holds_merge_batch_lock = False
            lock.close()

    def died_mid_merge_stopped(self):
        """When a merge batch left the in-progress file, write a stopped notice and return
        whether every write succeeded; otherwise return None.

        Called only while this process holds merge-batch.lock, since a running batch writes
        the file under that lock and holds it through each merge. A stop file found here is
        quoted and kept, since it holds the reason the merge program gave.
        """
        if not self.in_progress_file.exists():
            return None
        left = self.in_progress_file.read_text().strip()
        died = (f"a merge batch ended during a merge, so main is untested: "
                f"{self.in_progress_file} says {left}")
        return self.stopped(died)

    def one_pass(self, merge_only):
        """Try each waiting pull request once; return whether any line was appended.

        Each next pull request is chosen from the queue file as it is once the next merge may
        start, so a HOLD- line a lane appends while the previous merge runs is obeyed.
        """
        tried = set()
        passed_over = set()
        appended = False
        while True:
            while (decision := self.next_merge_may_start())[0] == NEXT_MERGE_WAITS:
                self.log(f"waiting: {decision[1]}")
                self.wait(SECONDS_BETWEEN_NEXT_MERGE_MAY_START_CHECKS)
            if decision[0] == NEXT_MERGE_STOPS:
                raise StopFileFound(decision[1])
            waiting = [line for line in self.waiting(self.queue_lines())
                       if int(line["pr"]) not in tried]
            if merge_only is not None and merge_only not in tried:
                first = [line for line in waiting if int(line["pr"]) == merge_only]
                if not first:
                    raise Stop(f"pull request {merge_only}, named by --merge-only, is not waiting")
                waiting = first
            if not waiting:
                return appended
            in_a_row = self.prose_only_merges_in_a_row()
            if len(waiting) == 1:
                line, prose_only = waiting[0], self.prose_only(waiting[0])
            else:
                line, prose_only = self.next_in_merge_order(waiting, in_a_row)
            self.prose_only_merges_in_a_row_after_this_merge = in_a_row + 1 if prose_only else 0
            number = int(line["pr"])
            tried.add(number)
            self.merged_cleanly = None
            self.outcome = None
            appended_now = self.one_pull_request(line)
            appended |= appended_now
            if self.outcome == READ_AGAIN_OUTCOME:
                tried.discard(number)
                continue
            if self.outcome == STACKED_PASSED_OVER_OUTCOME:
                passed_over.add(number)
            elif appended_now and self.outcome.startswith("MERGED "):
                # The merge may have retargeted a passed-over pull request onto main.
                tried -= passed_over
                passed_over.clear()
            if number == merge_only and self.merged_cleanly != merge_only:
                raise Stop(f"pull request {merge_only}, named by --merge-only to merge first, "
                           f"did not merge with a passing after-merge test run, so no other "
                           f"pull request merges onto main before it: {self.outcome}")

    def next_merge_may_start(self):
        """Return (NEXT_MERGE_STARTS, NEXT_MERGE_WAITS or NEXT_MERGE_STOPS, why).

        Requirement 3 of the approved design is decided here alone: no merge starts while
        main's latest after-merge test run is failing (the stop file exists) or still running
        (a merge program holds merge-program.lock, which it holds through that run).
        """
        if self.stop_file.exists():
            return NEXT_MERGE_STOPS, self.stop_file.read_text().strip()
        lock_path = (self.arguments.merge_program_outputs_directory
                     / merge_program.MERGE_PROGRAM_RUN_LOCK_FILE_NAME)
        if lock_path.exists():
            with open(lock_path) as lock:
                try:
                    fcntl.flock(lock, fcntl.LOCK_SH | fcntl.LOCK_NB)
                except BlockingIOError:
                    return NEXT_MERGE_WAITS, (f"a merge program holds {lock_path}, so main's "
                                              f"latest after-merge test run is still running")
        return NEXT_MERGE_STARTS, ""

    def one_pull_request(self, line):
        """Check and merge one waiting pull request, setting self.outcome; return whether a
        line was appended."""
        number, head, author = int(line["pr"]), line["head"], line["author"]
        state = self.pull_request(number)
        merge_commit = (state.get("mergeCommit") or {}).get("oid")
        if state.get("state") == "MERGED":
            merged_line = (f"MERGED {number} {merge_commit} (merged on GitHub outside the merge "
                           f"queue)")
            self.append(merged_line)
            self.outcome = f"{merged_line}; this program did not see its after-merge test run"
            return True
        if state.get("state") == "CLOSED":
            return self.held(number, author, "closed on GitHub", line.string)
        if state.get("headRefOid") != head:
            return self.held(number, author, f"nn-head-commit moved to {state.get('headRefOid')}"
                                             f": needs a review of the new nn-head-commit",
                             line.string)
        base = state.get("baseRefName")
        if base != "main":
            if len(self.open_pull_requests_with_branch(base)) == 1:
                self.log(f"pull request {number} is stacked on {base}, not merged yet: passed over")
                self.outcome = STACKED_PASSED_OVER_OUTCOME
                return False
            return self.held(number, author, f"base branch {base} is not main and is not the "
                                             f"branch of exactly one open pull request",
                             line.string)
        return self.merged(number, head, author,
                           self.reviewed_since(number, head, line["since"]), line.string)

    def held(self, number, author, why, checked_line):
        held_line = f"HELD {number} {why}"
        if not self.append_while_still_last(number, checked_line, held_line):
            self.outcome = READ_AGAIN_OUTCOME
            return False
        self.outcome = held_line
        self.notice(f"held-{number}.txt",
                    f"HELD {number} author {author}\n{held_line}\n"
                    f"The merge batch went on without it. Tell its author agent-seat, with Claude "
                    f"Code's SendMessage tool, what the line above says it must do; it merges once "
                    f"its lane appends a new approved line for it.\n")
        return True

    def merged(self, number, head, author, reviewed_since, checked_line):
        with self.queue_locked():
            if self.last_line(number) != checked_line:
                self.log(f"pull request {number} got a new line while it was chosen and checked, "
                         f"so it does not merge now and its new line is read at once")
                self.outcome = READ_AGAIN_OUTCOME
                return False
        output_file = self.directory / f"merge-{number}.out"
        self.in_progress_file.write_text(f"pull request {number}, started {now()}\n")
        self.log(f"merging pull request {number} at {head} with reviewed-since {reviewed_since}")
        with open(output_file, "w") as output:
            # The outputs directory is passed on, so the merge program locks and writes the
            # stop file in the directory this program reads them from.
            exit_code = subprocess.run(
                [sys.executable, str(self.arguments.merge_program), str(number), head,
                 reviewed_since, "--merge-lane-worktrees-and-outputs-directory",
                 str(self.arguments.merge_program_outputs_directory)],
                stdout=output, stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL, cwd=self.arguments.merge_program.parent.parent).returncode
        text = output_file.read_text()
        report = "\n".join(line for line in text.splitlines()
                           if MERGE_PROGRAM_REPORT_LINE.match(line))
        self.log(f"pull request {number}: the merge program exited {exit_code}")
        merged_state = self.pull_request(number)
        merge_commit = (merged_state.get("mergeCommit") or {}).get("oid")
        on_github = merged_state.get("state") == "MERGED"
        if on_github:
            self.append(f"MERGED {number} {merge_commit}")
            self.outcome = f"MERGED {number} {merge_commit}"
        if exit_code == 0 and on_github:
            self.merged_cleanly = number
            self.in_progress_file.unlink(missing_ok=True)
            self.notice(f"merged-{number}-{merge_commit[:12]}.txt",
                        f"MERGED {number} {merge_commit} {author}\n"
                        f"{self.follow_up_request(number)}")
            # Written after the MERGED notice, so a failed write cannot cost the author it.
            count_failure = self.prose_only_merge_counted()
            if count_failure:
                raise ReadOrWriteFailed(f"pull request {number} merged as {merge_commit} and its "
                                        f"MERGED notice is written, but {count_failure}")
            return True
        if exit_code == 1 and not on_github:
            self.in_progress_file.unlink(missing_ok=True)
            if "mergeStateStatus is DIRTY" in text:
                why = ("conflicts with main (mergeStateStatus DIRTY): its author merges main "
                       "in, then the new nn-head-commit needs a new review")
            else:
                first = next((line for line in text.splitlines()
                              if line.startswith(("GATE REFUSED", "STOP"))), "no reason printed")
                why = f"refused: {first}"
            return self.held(number, author, why, checked_line)
        merge_notice = ""
        if on_github:
            # Resuming never reaches a pull request already MERGED, so its merge notice is
            # sent from this stop.
            merge_notice = (f"\nPull request {number} merged as {merge_commit}; its author "
                            f"agent-seat is {author}. Send that agent-seat its merge notice, as "
                            f"for a MERGED notice, with Claude Code's SendMessage tool: the merge "
                            f"commit, and this follow-up request:\n"
                            f"{self.follow_up_request(number)}")
        count_failure = self.prose_only_merge_counted() if on_github else None
        raise (ReadOrWriteFailed if count_failure else Stop)(
            f"pull request {number}: the merge program exited {exit_code} and GitHub "
            f"says {merged_state.get('state')}: "
            f"{MERGE_PROGRAM_EXIT_MEANINGS.get(exit_code, 'an exit code it does not document')}"
            f"; its output is in {output_file}" + (f"\n{report}" if report else "")
            + merge_notice + (f"\nAlso, {count_failure}" if count_failure else ""))

    def follow_up_request(self, number):
        completed = subprocess.run(
            [sys.executable, str(self.arguments.follow_up_program), str(number),
             "print-follow-up-request-block-from-merge-lane-2-reviews"],
            capture_output=True, text=True, stdin=subprocess.DEVNULL,
            cwd=self.arguments.follow_up_program.parent.parent)
        if completed.returncode != 0:
            return (f"The follow-up program exited {completed.returncode}; run it by hand: "
                    f"python3 {self.arguments.follow_up_program} {number} "
                    f"print-follow-up-request-block-from-merge-lane-2-reviews\n"
                    f"{completed.stdout}{completed.stderr}")
        return completed.stdout

    # Starting

    def start(self, quiet, merge_only=None):
        # The stop file is checked before the lock, since a running batch that finds a stop
        # file written outside it ends at its next check. A dead batch's in-progress file left
        # beside it means its stopped notice was not written, and the check below writes it.
        if self.stop_file.exists() and not self.dead_batch_left_in_progress_file():
            if not quiet:
                notices = (sorted(self.notices.glob("stopped-*.txt"))
                           if self.notices.is_dir() else [])
                where = (f"Handle its stopped notice, {notices[-1]}, as it says"
                         if notices else
                         "No stopped notice exists, so the merge program was run outside the "
                         "merge queue: read that run's output, find the cause and handle it")
                print(f"STOPPED: nothing was started, because {self.stop_file} says: "
                      f"{self.stop_file.read_text().strip()}\n"
                      f"{where}; then run, which removes the stop file: {self.resume_command()}")
            return 0
        self.directory.mkdir(parents=True, exist_ok=True)
        with open(self.directory / MERGE_BATCH_LOCK_FILE_NAME, "a") as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                if not quiet:
                    print(f"ALREADY RUNNING: a merge batch holds {MERGE_BATCH_LOCK_FILE_NAME} and "
                          f"will read any new line of {self.arguments.merge_queue_file} before it "
                          f"ends; nothing needs doing")
                return 0
            self.holds_merge_batch_lock = True
            try:
                if self.in_progress_file.exists():
                    print(f"DIED MID-MERGE: {self.in_progress_file} was left by a merge batch that "
                          f"ended during a merge, so that merge's outcome and main's after-merge test "
                          f"run are unchecked; nothing was started.")
                    if self.died_mid_merge_stopped():
                        print(f"The stop file and a stopped notice in {self.notices} now say that a "
                              f"merge batch died mid-merge: handle that notice as it says.")
                        return 0
                    print("FAILED: the stop file or the stopped notice could not be written, as the "
                          "lines above say. Fix what they name, then run merge-batch-start again; "
                          "until then the in-progress file is kept, so every merge-batch-start "
                          "reports DIED MID-MERGE and starts nothing.")
                    return 1
            finally:
                self.holds_merge_batch_lock = False
        # Released before the merge batch starts, since that batch takes the lock itself.
        command = [sys.executable, str(Path(__file__).resolve()),
                   "--merge-queue-file", str(self.arguments.merge_queue_file),
                   "--merge-batches-directory", str(self.directory),
                   "--merge-program-outputs-directory",
                   str(self.arguments.merge_program_outputs_directory),
                   "--merge-program", str(self.arguments.merge_program),
                   "--follow-up-program", str(self.arguments.follow_up_program),
                   "--gh", self.arguments.gh, "merge-batch-run-in-queue-order"]
        if merge_only is not None:
            command += ["--merge-only", str(merge_only)]
        log_file = self.directory / MERGE_BATCH_LOG_FILE_NAME
        try:
            with open(log_file, "a") as log:
                subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=log,
                                 stderr=subprocess.STDOUT, start_new_session=True)
        except OSError as error:
            print(f"NOT STARTED: the merge batch could not be started: {error}\n"
                  f"Tell the user that merges cannot start on ned-box because: {error}. A "
                  f"subagent tells the agent that dispatched it instead.")
            return 1
        print(f"STARTED: a merge batch; its log is {log_file}")
        return 0

    def dead_batch_left_in_progress_file(self):
        if not self.in_progress_file.exists():
            return False
        self.directory.mkdir(parents=True, exist_ok=True)
        with open(self.directory / MERGE_BATCH_LOCK_FILE_NAME, "a") as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                return False
        return True

    def resume(self, merge_only):
        self.directory.mkdir(parents=True, exist_ok=True)
        # Checked before the lock: a merge batch that found the lock held while resume read the
        # queue file would exit ALREADY RUNNING, and a refused resume would then start nobody.
        if merge_only is not None:
            numbers = [int(line["pr"]) for line in self.waiting(self.queue_lines())]
            if merge_only not in numbers:
                print(f"REFUSED: pull request {merge_only} is not waiting in the merge queue "
                      f"file, so it cannot merge first; the stop file is left in place.\n"
                      f"Name a pull request that this program's merge-batch-list-waiting "
                      f"subcommand prints.")
                return 2
        # The files are removed under the lock, so a batch that takes it cannot have its live
        # in-progress file removed.
        with open(self.directory / MERGE_BATCH_LOCK_FILE_NAME, "a") as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                print(f"REFUSED: a merge batch is running, and resume is only for a stopped one; "
                      f"the running batch will merge what is waiting. Read its log, "
                      f"{self.directory / MERGE_BATCH_LOG_FILE_NAME}, and run merge-batch-resume "
                      f"only after a stopped notice appears in {self.notices}.")
                return 2
            self.stop_file.unlink(missing_ok=True)
            self.in_progress_file.unlink(missing_ok=True)
        return self.start(quiet=False, merge_only=merge_only)

    def list_waiting(self):
        for line in self.waiting(self.queue_lines()):
            state = self.pull_request(int(line["pr"]))
            print(f"{line['pr']} {state.get('state')} base {state.get('baseRefName')} "
                  f"queued {line['head'][:12]} now {(state.get('headRefOid') or '')[:12]} "
                  f"{line['author']}")
        return 0


def main(argv=None):
    arguments = parse_arguments(argv)
    queue = MergeQueuePullRequestMergeBatchRunner(arguments)
    try:
        if arguments.subcommand == "merge-batch-run-in-queue-order":
            return queue.run_in_queue_order(arguments.merge_only)
        if arguments.subcommand == "merge-batch-start":
            return queue.start(arguments.quiet)
        if arguments.subcommand == "merge-batch-resume":
            return queue.resume(arguments.merge_only)
        return queue.list_waiting()
    except (Stop, OSError) as error:
        print(f"FAILED: {error}\n"
              f"Nothing was merged or started by this command. Fix the file or GitHub read "
              f"named above, then run the same command again.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
