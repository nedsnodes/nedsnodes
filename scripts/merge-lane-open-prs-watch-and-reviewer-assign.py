#!/usr/bin/env python3
"""Watch open pull requests and emit flushed OPENED, NEW-HEAD and READY events, REVIEW-ASSIGNED events giving each a merge-lane agent-seat to review it, and NEEDS A LOOK events for the GHI-MD edit job's notices.

A draft pull request raises no OPENED, NEW-HEAD or READY event: it is not to
be reviewed. The one draft that gets a REVIEW-ASSIGNED line is the bottom of
a stack whose ready pull request is assigned, as below. The baseline line
lists drafts apart. A pull request that was a draft at the last
successful poll and is not one now raises READY, however it was marked
ready. A pull request turned back into a draft raises nothing.

The first successful poll establishes a silent baseline unless --from-start
is set. Failed polls preserve state and announce blindness; activity that
opens and closes between successful polls cannot be recovered. State lives
only in the process: an opening or a draft marked ready while the watcher is
not running is absorbed into the next baseline and raises no event.

Each poll, failed or not, also lists the needs-a-look/ directory that
merge-lane-ghi-md-edit-pull-requests-provisional-additions-only-check-approve-and-merge.py
writes merge-lane-2's notices to, its pr<number>-<head>.txt files and
invocation-stopped.txt, and prints NEEDS A LOOK for each regular file in it
not yet printed by this process, or changed since; the line names the move
into needs-a-look/handled/ that marks the notice handled. Unlike openings,
notices already there at the first poll are reported, since a file left
outside handled/ is unhandled whoever restarted the watcher. So with
--exit-after-first-poll-with-events, a notice not moved makes every restart
exit at its first poll, before any pull request event can show, and with
--batch-events-for-seconds N, makes every restart exit after its poll at N
seconds: the line says to move it as soon as it is read. A missing
directory, before the job first writes one, raises nothing. A directory that
cannot be listed raises one NEEDS A LOOK line naming the error, again only
after a listing has succeeded in between; a notice that cannot be read is
reported with the error in place of its first line, and an entry whose
status cannot be read, other than one gone since the listing or a dangling
link, is reported once with the error. A notice moved out and back between
two polls, keeping its modification time, is not reported again by the same
process; one that a poll found missing is reported again when it comes back.
The watcher never moves or deletes a notice.

Each successful poll, the baseline included, also gives every open pull
request that is not a draft and has no line in the assignment file yet a
merge-lane agent-seat to review it, oldest first, and prints PR #<number>
REVIEW-ASSIGNED <merge-lane agent-seat> for each. The assignment file,
--merge-lane-pr-review-assignments-file, holds one `<number> <merge-lane
agent-seat>` line per pull request; only this watcher writes it. A pull
request with a line keeps that agent-seat for every fix-round. A stacked
pull request, whose base branch is not main, takes the agent-seat of the
bottom of its stack: the open pull request whose head branch is its base,
followed down to the one whose base is main; that bottom one, draft or not,
is assigned first when it has no line. When a lookup on the way down finds
no open pull request, or more than one, or comes back to a pull request
already passed, the pull request is taken as not stacked. The lookup goes by
branch name alone, so a fork's pull request whose head branch shares a base
branch's name is not handled: it can be taken as the pull request below, or
make the stack read as not stacked. Every other one
goes to whichever agent-seat of
MERGE_LANE_PULL_REQUEST_REVIEW_ASSIGNEE_AGENT_SEATS_IN_TIE_ORDER has fewer
pull requests waiting, ties to the first, leaving out the agent-seat named as
the author of the pull request's first commit, which the agent-seat
launchers set to the agent-seat that wrote it; each assignment counts at
once. A stacked pull request still takes its bottom's agent-seat, so the
author of its first commit is not checked. A
pull request waits for its agent-seat when it is open, not a draft, and no
review by ned-review-merge on its newest commit carries a verdict, read as
the fix-round program reads one: the state APPROVED or CHANGES_REQUESTED,
or, on a pull request ned-review-merge opened, a COMMENTED review whose body
opens with the line APPROVE or REQUEST_CHANGES, or there a review by
mac-claude whose state is APPROVED or CHANGES_REQUESTED, which the merge gate
takes as the verdict, once ned-review-merge has also reviewed that commit. On
a pull request another account opened, mac-claude's reviews are not required
to be readable. A pull request dealt with its verdict already on its
newest commit does not add to its agent-seat's count. Only the newest
REVIEWS_READ_PER_PULL_REQUEST reviews by each of the two accounts on each
pull request are read, so a verdict followed by REVIEWS_READ_PER_PULL_REQUEST
or more reviews by its own account is not read; this is not handled. Such a
pull request counts as waiting only when no verdict on its newest commit is
read from either account that counts for it, so on a pull request
ned-review-merge opened, a mac-claude verdict still read keeps it from
counting. A missing, unreadable or
malformed assignment file stops all assignment, so that no pull request it
names is assigned again; so does
a file that cannot be rewritten, until it can. The watcher writes the whole
new file beside it and renames it over the old one, so a failed write leaves
the old file whole and every pull request it dealt is dealt again at the
next poll. Each failure prints a WATCH line whenever its case differs from
the last poll's.
--merge-lane-pr-review-assignments-file-write-from-seed-and-reviewed-prs-then-exit
makes the file once, and --merge-lane-pr-review-assignments-list-for lists
one agent-seat's pull requests.
Without --merge-lane-pr-review-assignments-file, the default assignment file
is used for DEFAULT_REPO only, its owner and name read in any case, as GitHub
reads them; each other repository needs its own file, named with that option.
With another --repo and no file named, the watch assigns no review and
prints no line saying so, and the seed and the listing exit 2.

With --batch-events-for-seconds N, every OPENED, NEW-HEAD, READY, REVIEW-ASSIGNED and NEEDS A
LOOK line is held in the process instead of printed. The watcher prints them
all, in the order seen, and exits 0 when a poll finishes N or more seconds
after the start while it holds a line, even a line that poll found. Once it
holds a line, it starts its next poll no later than N seconds after the
start. A poll can finish up to the GitHub query's timeout per page after it
starts.
WATCH lines still print at once. The held lines live only in the process: a
watcher killed before it exits loses them, and its next start absorbs the
openings into the baseline.

With --poll-once, the form the one-minute cron job runs, the watcher makes
one poll and exits, under a lock, so that it outlives any agent-session. Its
state is a file, so an opening or a draft marked ready between two runs raises
its event. It appends each event to an event file in the log-store. A task on
merge-lane-2's task list names the new lines, only when there are new lines,
no events task is open, and the last one opened at least
WATCH_OPEN_PULL_REQUESTS_MINIMUM_SECONDS_BETWEEN_EVENTS_TASKS ago; a run that finds nothing new writes no task
and sends no message. A missing or unreadable state file stops the run with a
task saying how to repair it, and never becomes a new baseline, which would
drop the events since the last run; --poll-once-write-baseline makes the first
state file. Each successful poll also assigns reviews as above; its
REVIEW-ASSIGNED lines, and a WATCH line saying assignment stopped, go to the
event file, the WATCH line once per case as the state file records. A run whose
append fails keeps the deal of each pull request whose REVIEW-ASSIGNED line the
event file holds, or of every one when the file cannot be read back, names those
pull requests in its failure task, since a failed append may not survive a crash,
and puts the rest back out of the assignment file, so the next run that can
append deals them again. A failed
poll keeps the state, assigns nothing, and only
WATCH_OPEN_PULL_REQUESTS_FAILED_GITHUB_POLLS_IN_A_ROW_BEFORE_FAILURE_TASK failed polls in a row open a task.
Not detected: a run killed between writing the assignment file and appending
its REVIEW-ASSIGNED lines, whose pull requests stay assigned with no line;
an event file emptied and then refilled by later polls to at least
as many lines as were delivered, whose lost lines no task names; when
writing the task fails at that failed poll, the rest of the same outage, which
opens no task; and a task list directory that does not exist, so that each
failure reaches only the cron log. With another --repo, --poll-once needs its own
--poll-once-directory, so that the default state is never another repository's.
A cron run, the loop watcher and the seed each hold a lock file
beside the assignment file from reading it to replacing it.

Polling needs no public webhook endpoint. GraphQL selects only needed fields
and avoids gh versions’ differing --json field lists."""

import argparse
import datetime
import fcntl
import getpass
import json
import os
import shlex
import stat
import subprocess
import tempfile
import sys
import time
import importlib.util
from pathlib import Path

_ghi_md_edit_job_spec = importlib.util.spec_from_file_location(
    "ghi_md_edit_pull_requests_check_approve_and_merge", Path(__file__).resolve().with_name(
        "merge-lane-ghi-md-edit-pull-requests-provisional-additions-only-check-approve-and-merge.py"))
ghi_md_edit_job = importlib.util.module_from_spec(_ghi_md_edit_job_spec)
_ghi_md_edit_job_spec.loader.exec_module(ghi_md_edit_job)
_fix_round_spec = importlib.util.spec_from_file_location(
    "pull_request_fix_round_author_brief_from_blocking_findings_and_one_commit_every_finding_answered_check",
    Path(__file__).resolve().with_name(
        "pull-request-fix-round-author-brief-from-blocking-findings-and-one-commit-every-finding-answered-check.py"))
fix_round = importlib.util.module_from_spec(_fix_round_spec)
_fix_round_spec.loader.exec_module(fix_round)

_task_list_write_spec = importlib.util.spec_from_file_location(
    "agent_seat_task_list_new_pending_task_write_common",
    Path(__file__).resolve().parent.parent / "nn-systems" / "general-tools"
    / "agent-seat-task-list-new-pending-task-write-common.py")
agent_seat_task_list = importlib.util.module_from_spec(_task_list_write_spec)
_task_list_write_spec.loader.exec_module(agent_seat_task_list)

DEFAULT_REPO = "nedsnodes/nedsnodes"
DEFAULT_POLL_SECONDS = 60.0
DEFAULT_TOKEN_FILE = "~/.config/nedsnodes/ned-review-merge.token"

# GitHub caps GraphQL pages at 100; bound page count to prevent an endless pagination loop.
PAGE_SIZE = 100
MAX_PAGES = 10

# Bound hung queries so the watcher can announce blindness.
GH_QUERY_TIMEOUT_SECONDS = 30.0

# Use an exit code gh cannot return to distinguish failure to run from a completed query.
GH_DID_NOT_RUN = -1

HEAD_SHA_PREFIX_CHARS = 8
TITLE_SNIPPET_CHARS = 120
FAILURE_REASON_SNIPPET_CHARS = 300
NOTICE_FIRST_LINE_CHARS = 300
# Stands in the reported record for a notice whose status could not be read; no mtime equals it.
STATUS_UNREADABLE = "status unreadable"

POLL_ONCE_DIRECTORY_NAME = "open-pull-request-watcher-poll-once-state-events-and-lock"
OPEN_PRS_WATCH_POLL_ONCE_STATE_EVENTS_AND_LOCK_DEFAULT_DIRECTORY = (
    ghi_md_edit_job.common.DEFAULT_MERGE_LANE_WORKTREES_AND_OUTPUTS_DIRECTORY / POLL_ONCE_DIRECTORY_NAME)
WATCH_OPEN_PULL_REQUESTS_POLL_STATE_BETWEEN_CRON_RUNS_FILE_NAME = "poll-state.json"
WATCH_OPEN_PULL_REQUESTS_EVENTS_LOG_FILE_NAME = "pull-request-events.log"
LOCK_FILE_NAME = "poll-once.lock"
FAILURE_TASK_SUBJECT_PREFIX = "Open-pull-request watcher cron job failed: "
WATCH_OPEN_PULL_REQUESTS_MINIMUM_SECONDS_BETWEEN_EVENTS_TASKS = 1200
# A short GitHub outage costs no event, because the state file keeps the last good poll.
WATCH_OPEN_PULL_REQUESTS_FAILED_GITHUB_POLLS_IN_A_ROW_BEFORE_FAILURE_TASK = 10
# Every message to an agent follows
# docs/nedsnodes-wiki/nedsnodes-how-to-write-a-tool-message-to-agent-such-as-a-hook-refusal-or-script-error.md.
MERGE_LANE_PULL_REQUEST_REVIEW_ASSIGNMENTS_DEFAULT_FILE = Path(
    "/home/nedlern/nedsnodes-logs/seats/merge-lane-2/merge-lane-pr-review-assignments.txt")
# In tie order. merge-lane-2 only merges, so no line of the assignment file may name it.
MERGE_LANE_PULL_REQUEST_REVIEW_ASSIGNEE_AGENT_SEATS_IN_TIE_ORDER = ("merge-lane-1", "merge-lane-3")
ASSIGNMENT_LINE_FORMAT = (f"<pull request number> "
                          f"<one of {', '.join(MERGE_LANE_PULL_REQUEST_REVIEW_ASSIGNEE_AGENT_SEATS_IN_TIE_ORDER)}>, "
                          f"with one space between")
# The seed's lane for a pull request reviewed before assignment by backlog, by its number mod 3.
# Remainder 2 was merge-lane-2's, which no longer reviews: the watcher deals those afresh.
MERGE_LANE_BY_PULL_REQUEST_NUMBER_REMAINDER = {1: "merge-lane-1", 0: "merge-lane-3"}
MERGE_LANE_BY_PULL_REQUEST_NUMBER_REMAINDER_TEXT = (
    "the remainder of its number divided by 3: "
    + ", ".join(f"{remainder} {lane}" for remainder, lane in MERGE_LANE_BY_PULL_REQUEST_NUMBER_REMAINDER.items())
    + ", and 2 none, so the watcher deals it as a new one")
STACK_BOTTOM_BASE_BRANCH = "main"
# A pull request's reviews on its head commit are its newest, so the last few suffice.
REVIEWS_READ_PER_PULL_REQUEST = 20
# GitHub refuses an approval from a pull request's author, so on a pull request ned-review-merge
# opened, the merge gate takes this account's approval as the verdict.
MAC_CLAUDE_ACCOUNT = "mac-claude"

# A short redaction pattern would corrupt ordinary output; reject invalid credentials at startup.
MINIMUM_PLAUSIBLE_TOKEN_CHARS = 8

OPEN_PULL_REQUESTS_QUERY = """
query($owner: String!, $name: String!, $cursor: String) {
  repository(owner: $owner, name: $name) {
    pullRequests(states: OPEN, first: %d, after: $cursor,
                 orderBy: {field: CREATED_AT, direction: ASC}) {
      nodes {
        number
        title
        isDraft
        headRefOid
        author { login }
        createdAt
        baseRefName
        headRefName
        commits(first: 1) { nodes { commit { author { name } } } }
        reviews(author: "%s", last: %d) { nodes { state body commit { oid } } }
        macClaudeReviews: reviews(author: "%s", last: %d) { nodes { state commit { oid } } }
      }
      pageInfo { hasNextPage endCursor }
    }
  }
}
""" % (PAGE_SIZE, fix_round.MERGE_LANE_2_REVIEWER_LOGIN, REVIEWS_READ_PER_PULL_REQUEST,
       MAC_CLAUDE_ACCOUNT, REVIEWS_READ_PER_PULL_REQUEST)

# Redact every output path, including quoted gh stderr.
SECRETS_TO_REDACT = []


def redact_secrets(text):
    for secret in SECRETS_TO_REDACT:
        text = text.replace(secret, "[REDACTED]")
    return text


def emit(line):
    # Flush immediately so a buffered event cannot look like an inactive watch.
    print(redact_secrets(line), flush=True)


def warn(line):
    print(redact_secrets(line), file=sys.stderr, flush=True)


def one_line_snippet(text, limit):
    """Return a redacted, single-line snippet bounded by limit."""
    # Redact before truncation: a partial token no longer matches the whole-token redactor.
    return " ¶ ".join(redact_secrets(str(text)).strip().splitlines())[:limit]


def read_token(token_file: Path):
    """Return (token, None) or (None, reason), never including file contents in errors."""
    try:
        token = token_file.read_text(encoding="utf-8", errors="replace").strip()
    except OSError as error:
        return None, (f"cannot read the token file {token_file}: "
                      f"{error.strerror or type(error).__name__}")
    if len(token) < MINIMUM_PLAUSIBLE_TOKEN_CHARS:
        return None, (f"the token file {token_file} holds {len(token)} "
                      f"characters after stripping whitespace, which is not "
                      f"a GitHub token")
    return token, None


def run_gh(arguments, token, timeout=GH_QUERY_TIMEOUT_SECONDS):
    """Run gh with the credential in the environment and return its own exit status and output."""
    # Keep the token out of argv, which process listings and command errors can expose.
    environment = dict(os.environ)
    environment["GH_TOKEN"] = token
    try:
        return subprocess.run(["gh", *arguments], capture_output=True, text=True,
                              check=False, timeout=timeout, env=environment)
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(
            arguments, GH_DID_NOT_RUN, "",
            f"gh did not answer within {timeout:g}s")
    except (OSError, subprocess.SubprocessError) as error:
        return subprocess.CompletedProcess(
            arguments, GH_DID_NOT_RUN, "", f"{type(error).__name__}: {error}")


def pull_request_from_node(node):
    """Return (pull_request, None) or (None, reason) for an invalid node."""
    # Dropping a malformed node would falsely report the pull request as newly opened at the next poll.
    if not isinstance(node, dict):
        return None, "a pull request came back as JSON that is not an object"
    number = node.get("number")
    head_sha = node.get("headRefOid")
    if not isinstance(number, int):
        return None, "a pull request came back with no usable number"
    if not isinstance(head_sha, str) or not head_sha:
        return None, f"pull request #{number} came back with no head commit sha"
    for field in ("createdAt", "baseRefName", "headRefName"):
        if not isinstance(node.get(field), str):
            return None, f"pull request #{number} came back with no {field}"
    author = node.get("author")
    # GitHub returns null authors for deleted accounts.
    author = (author or {}).get("login") or "(unknown)"
    # mac-claude's reviews decide nothing on a pull request another account opened.
    required_review_lists = (("reviews", "macClaudeReviews")
                             if author == fix_round.MERGE_LANE_2_REVIEWER_LOGIN else ("reviews",))
    review_lists = {"macClaudeReviews": []}
    for field in required_review_lists:
        reviews = node.get(field)
        reviews = reviews.get("nodes") if isinstance(reviews, dict) else None
        # A review with no state would make the fix-round program's verdict reader raise.
        if not isinstance(reviews, list) or not all(
                isinstance(review, dict) and isinstance(review.get("state"), str) for review in reviews):
            return None, f"pull request #{number} came back with no usable list of {field}"
        review_lists[field] = reviews
    first_commits = (node.get("commits") or {}).get("nodes") or [{}]
    first_commit_author = (first_commits[0].get("commit") or {}).get("author") or {}
    return {
        "number": number,
        "head_sha": head_sha,
        "title": node.get("title") or "",
        "is_draft": bool(node.get("isDraft")),
        "author": author,
        # The agent-seat launchers set GIT_AUTHOR_NAME to the agent-seat's name.
        "first_commit_author_name": first_commit_author.get("name"),
        "created_at": node["createdAt"],
        "base_branch": node["baseRefName"],
        "head_branch": node["headRefName"],
        "reviews": review_lists["reviews"],
        "mac_claude_reviews": review_lists["macClaudeReviews"],
    }, None


def fetch_open_pull_requests(repo, token):
    """Return (all_open_pull_requests, None) or (None, reason); never return partial results."""
    owner, _, name = repo.partition("/")
    pull_requests = []
    cursor = None
    for _ in range(MAX_PAGES):
        arguments = ["api", "graphql",
                     "-f", f"query={OPEN_PULL_REQUESTS_QUERY}",
                     "-f", f"owner={owner}", "-f", f"name={name}"]
        if cursor:
            arguments += ["-f", f"cursor={cursor}"]
        result = run_gh(arguments, token)
        if result.returncode != 0:
            reason = (result.stderr or result.stdout or "").strip()
            return None, reason or f"gh exited {result.returncode} with no message"
        try:
            payload = json.loads(result.stdout)
        except (json.JSONDecodeError, ValueError) as error:
            return None, f"gh returned unparseable JSON: {error}"
        if not isinstance(payload, dict):
            return None, "gh returned JSON that is not an object"
        # GraphQL can return HTTP 200 with errors and partial data; reject the whole poll.
        if payload.get("errors"):
            return None, f"GraphQL error: {payload['errors']}"
        try:
            connection = payload["data"]["repository"]["pullRequests"]
            nodes = connection["nodes"]
            page_info = connection["pageInfo"]
        except (KeyError, TypeError) as error:
            return None, f"unexpected response shape: {type(error).__name__} {error}"
        if not isinstance(nodes, list) or not isinstance(page_info, dict):
            return None, "unexpected response shape: nodes or pageInfo missing"
        for node in nodes:
            pull_request, reason = pull_request_from_node(node)
            if reason is not None:
                return None, reason
            pull_requests.append(pull_request)
        if not page_info.get("hasNextPage"):
            return pull_requests, None
        cursor = page_info.get("endCursor")
        if not cursor:
            return None, "another page was reported but no cursor came with it"
    return None, (f"gave up after {MAX_PAGES} pages ({len(pull_requests)} pull "
                  f"requests) — pagination did not end")


def event_line(pull_request, event_name):
    return (f"PR #{pull_request['number']} {event_name} "
            f"{pull_request['head_sha'][:HEAD_SHA_PREFIX_CHARS]} "
            f"{pull_request['author']}: "
            f"{one_line_snippet(pull_request['title'], TITLE_SNIPPET_CHARS)}")


def events_for_poll(known_pull_requests, pull_requests):
    """Return events from changes to (number, head_sha, is_draft) since the last successful poll."""
    lines = []
    for pull_request in pull_requests:
        if pull_request["is_draft"]:
            continue
        seen = known_pull_requests.get(pull_request["number"])
        if seen is None:
            lines.append(event_line(pull_request, "OPENED"))
        elif seen["is_draft"]:
            lines.append(event_line(pull_request, "READY"))
        elif seen["head_sha"] != pull_request["head_sha"]:
            lines.append(event_line(pull_request, "NEW-HEAD"))
    return lines


def handled_move_command(directory, name):
    handled = directory / ghi_md_edit_job.HANDLED_MESSAGES_DIRECTORY_NAME
    return f"mkdir -p {handled} && mv {directory / name} {handled}/"


def needs_a_look_events(directory, state, state_survives_restarts=False):
    """Return a NEEDS A LOOK line per notice in directory not yet reported, as state records."""
    try:
        entries = sorted(directory.iterdir())
    except FileNotFoundError:
        state["unlistable"] = False
        return []
    except OSError as error:
        if state.get("unlistable"):
            return []
        state["unlistable"] = True
        return [f"NEEDS A LOOK: cannot list the GHI-MD edit job's notices in {directory}: "
                f"{error.strerror or error}; notices there go unreported until it can be listed"]
    state["unlistable"] = False
    reported = state.setdefault("reported", {})
    lines = []
    present = set()
    for path in entries:
        try:
            status = path.stat()
        except FileNotFoundError:
            # Gone since the listing, or a dangling link: nothing to read.
            continue
        except OSError as error:
            present.add(path.name)
            if reported.get(path.name) != STATUS_UNREADABLE:
                reported[path.name] = STATUS_UNREADABLE
                lines.append(f"NEEDS A LOOK {path.name}: (could not read its status: "
                             f"{error.strerror or error}) -- look at {path}")
            continue
        if not stat.S_ISREG(status.st_mode):
            continue
        modified = status.st_mtime_ns
        present.add(path.name)
        if reported.get(path.name) == modified:
            continue
        reported[path.name] = modified
        try:
            first_line = (path.read_text(encoding="utf-8", errors="replace")
                          .splitlines() or ["(empty file)"])[0]
        except OSError as error:
            first_line = f"(could not read it: {error.strerror or error})"
        lines.append(f"NEEDS A LOOK {path.name}: "
                     f"{one_line_snippet(first_line, NOTICE_FIRST_LINE_CHARS)} -- read {path}, "
                     + ("then move it: " if state_survives_restarts else
                        "then at once, before acting on it, move it, or each restart of this "
                        "watcher reports it again first: ")
                     + handled_move_command(directory, path.name))
    for name in set(reported) - present:
        del reported[name]
    return lines


def pull_requests_by_number(pull_requests):
    return {pull_request["number"]: pull_request
            for pull_request in pull_requests}


class MergeLanePullRequestReviewAssignmentsFileUnusable(Exception):
    """The assignment file is missing, unreadable or malformed: case is "missing", "unreadable" or
    "line", and the text says what was found."""

    def __init__(self, case, text):
        super().__init__(text)
        self.case = case


def merge_lane_pull_request_review_assignments_file_repair_steps(path, case, options_in_use=()):
    """The instruction lines that repair the assignment file at path, for the case its read failed in.
    options_in_use are the --repo and --token-file options the watcher runs with, which the seed
    command it prints repeats."""
    if case == "unreadable":
        return f"  Make the file readable by the user {getpass.getuser()}, who runs the watcher.\n"
    if case == "line":
        return (f"  Correct that line by hand as '{ASSIGNMENT_LINE_FORMAT}', keeping every other "
                f"line as it is.\n")
    seed_files = sorted(path.parent.glob(f"{path.stem}-seed-*{path.suffix}"))
    if len(seed_files) == 1:
        seed_file_text = shlex.quote(str(seed_files[0]))
        found = ""
    else:
        seed_file_text = "<seed file>"
        found = (f"; <seed file> is one of {', '.join(str(seed) for seed in seed_files)}"
                 if seed_files else
                 f"; <seed file> holds those assignments as '{ASSIGNMENT_LINE_FORMAT}' lines")
    return (f"  If you know the file was never made, make it once, on ned-box, from the file of "
            f"assignments made by hand before this watcher assigned any{found}: "
            + shlex.join(["python3", "scripts/merge-lane-open-prs-watch-and-reviewer-assign.py",
                          *options_in_use,
                          "--merge-lane-pr-review-assignments-file", str(path),
                          "--merge-lane-pr-review-assignments-file-write-from-seed-and-reviewed-prs-then-exit"])
            + f" {seed_file_text}\n"
            f"  If the file existed before, or you cannot tell, do not make it from a seed file, "
            f"because that would "
            f"give each reviewed pull request the merge-lane agent-seat of "
            f"{MERGE_LANE_BY_PULL_REQUEST_NUMBER_REMAINDER_TEXT}, in place of the one it was "
            f"assigned. Tell the user the file is gone, and that no other copy exists but the "
            f"REVIEW-ASSIGNED lines in merge-lane-2's agent-session transcripts, and ask whether to "
            f"rebuild it from them.\n")


def merge_lane_pull_request_review_assignments_file_read(path, file_kind="assignment file"):
    """Return {pull request number: merge-lane agent-seat} from the assignment file, or a seed file
    in its format, which file_kind names. Raises MergeLanePullRequestReviewAssignmentsFileUnusable."""
    return merge_lane_pull_request_review_assignments_file_text_and_assignments_read(path, file_kind)[1]


def merge_lane_pull_request_review_assignments_file_text_and_assignments_read(path, file_kind="assignment file"):
    """Return (the file's text, its assignments), so that a rewrite builds on the text it dealt
    from. Lines end at \n alone, as the writer ends them."""
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError as error:
        raise MergeLanePullRequestReviewAssignmentsFileUnusable(
            "missing", f"the {file_kind} {path} does not exist") from error
    except (OSError, UnicodeDecodeError) as error:
        raise MergeLanePullRequestReviewAssignmentsFileUnusable(
            "unreadable", f"the {file_kind} {path} cannot be read: {error}") from error
    assignments = {}
    lines = text.split("\n")
    if lines[-1] == "":
        lines.pop()
    for line_number, line in enumerate(lines, 1):
        number, _, lane = line.partition(" ")
        if not (number.isascii() and number.isdigit()) or lane not in MERGE_LANE_PULL_REQUEST_REVIEW_ASSIGNEE_AGENT_SEATS_IN_TIE_ORDER:
            raise MergeLanePullRequestReviewAssignmentsFileUnusable(
                "line", f"line {line_number} of the {file_kind} {path} is {line!r}, not "
                f"'{ASSIGNMENT_LINE_FORMAT}'")
        if int(number) in assignments:
            raise MergeLanePullRequestReviewAssignmentsFileUnusable(
                "line", f"line {line_number} of the {file_kind} {path} assigns pull request "
                f"#{number} a second time")
        assignments[int(number)] = lane
    return text, assignments


def merge_lane_pull_request_review_assignments_file_write(path, text, only_when_absent=False):
    """Write text as the file at path, through a temporary file of its own beside the file a
    symbolic link at path names, so that a write that fails leaves the old file whole and the
    link in place. The new file keeps the old one's mode, or takes the mode a new file gets. The
    caller holds merge_lane_pull_request_review_assignments_file_lock. Raises OSError, and
    FileExistsError when only_when_absent is set and a file is at path, which is then left as
    it is. Returns None, or, when the file was written but its temporary file could not be
    removed, the sentence that names that temporary file and the error.
    Not handled: a symbolic link at path repointed between the caller's read and this write,
    which sends the text read from the old file to the new one; and a directory with a default
    ACL, whose mode for a new file 0o666 & ~umask overrides."""
    target = path.resolve()
    descriptor, partial_name = tempfile.mkstemp(dir=target.parent, prefix=target.name + ".",
                                                suffix=".partial")
    partial = Path(partial_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as partial_file:
            partial_file.write(text)
        try:
            mode = stat.S_IMODE(target.stat().st_mode)
        except FileNotFoundError:
            umask = os.umask(0)
            os.umask(umask)
            mode = 0o666 & ~umask
        os.chmod(partial, mode)
        if only_when_absent:
            os.link(partial, target)
        else:
            os.replace(partial, target)
    except BaseException:
        partial.unlink(missing_ok=True)
        raise
    # After os.link the temporary name remains, so a failed removal must not read as a failed write.
    try:
        partial.unlink(missing_ok=True)
    except OSError as error:
        return f"its temporary file {partial} was left behind, because removing it failed: {error}"
    return None


def pull_request_waits_for_merge_lane_verdict(pull_request):
    """Whether the pull request is not a draft and no review on its newest commit carries a
    verdict: one by ned-review-merge, or, on a pull request ned-review-merge opened, an approval or
    request for changes by mac-claude once ned-review-merge has also reviewed that commit."""
    if pull_request["is_draft"]:
        return False

    def on_head(review):
        return (review.get("commit") or {}).get("oid") == pull_request["head_sha"]

    merge_lane_reviews_on_head = [review for review in pull_request["reviews"] if on_head(review)]
    if any(fix_round.merge_lane_review_verdict_from_review_state_or_comment_review_first_line(
               review, pull_request["author"], fix_round.MERGE_LANE_2_REVIEWER_LOGIN)
           for review in merge_lane_reviews_on_head):
        return False
    # Until the lane posts its own review, its grading of Codex findings can still turn
    # mac-claude's approval into a request for changes.
    return not (pull_request["author"] == fix_round.MERGE_LANE_2_REVIEWER_LOGIN
                and merge_lane_reviews_on_head and any(
                    review["state"] in ("APPROVED", "CHANGES_REQUESTED")
                    for review in pull_request["mac_claude_reviews"] if on_head(review)))


def merge_lane_pull_request_reviews_waiting_counts(pull_requests, assignments):
    counts = dict.fromkeys(MERGE_LANE_PULL_REQUEST_REVIEW_ASSIGNEE_AGENT_SEATS_IN_TIE_ORDER, 0)
    for pull_request in pull_requests:
        lane = assignments.get(pull_request["number"])
        if lane in counts and pull_request_waits_for_merge_lane_verdict(pull_request):
            counts[lane] += 1
    return counts


def pull_request_stack_bottom(pull_request, open_pull_requests_by_head_branch):
    """The pull request at the bottom of the stack, whose base is main; None when not stacked,
    or when a lookup on the way down finds no open pull request, or more than one."""
    if pull_request["base_branch"] == STACK_BOTTOM_BASE_BRANCH:
        return None
    seen = {pull_request["number"]}
    current = pull_request
    while current["base_branch"] != STACK_BOTTOM_BASE_BRANCH:
        below = open_pull_requests_by_head_branch.get(current["base_branch"], [])
        # A cycle of bases would otherwise loop forever.
        if len(below) != 1 or below[0]["number"] in seen:
            return None
        current = below[0]
        seen.add(current["number"])
    return current


def merge_lane_pull_request_review_assignments_for_unassigned_pull_requests(pull_requests, assignments):
    """Return [(pull request, merge-lane agent-seat)] for the open pull requests that are not drafts
    and have no assignment, oldest first, with each stacked one's bottom before it when the bottom
    has none. Does not change assignments."""
    unassigned = sorted((pull_request for pull_request in pull_requests
                         if not pull_request["is_draft"] and pull_request["number"] not in assignments),
                        key=lambda each: (each["created_at"], each["number"]))
    if not unassigned:
        return []
    assignments = dict(assignments)
    counts = merge_lane_pull_request_reviews_waiting_counts(pull_requests, assignments)
    open_pull_requests_by_head_branch = {}
    for pull_request in pull_requests:
        open_pull_requests_by_head_branch.setdefault(pull_request["head_branch"], []).append(pull_request)
    dealt = []

    def assign(pull_request, lane):
        assignments[pull_request["number"]] = lane
        dealt.append((pull_request, lane))
        # As in the starting counts, which leave out a pull request that already has its verdict.
        if pull_request_waits_for_merge_lane_verdict(pull_request):
            counts[lane] += 1

    def fewest_waiting(pull_request):
        # A merge lane never reviews a pull request it wrote.
        lanes = [lane for lane in MERGE_LANE_PULL_REQUEST_REVIEW_ASSIGNEE_AGENT_SEATS_IN_TIE_ORDER
                 if lane != pull_request.get("first_commit_author_name")]
        return min(lanes, key=lambda lane: counts[lane])

    for pull_request in unassigned:
        # The bottom of an earlier one's stack is assigned already.
        if pull_request["number"] in assignments:
            continue
        bottom = pull_request_stack_bottom(pull_request, open_pull_requests_by_head_branch)
        if bottom is None:
            assign(pull_request, fewest_waiting(pull_request))
            continue
        if bottom["number"] not in assignments:
            assign(bottom, fewest_waiting(bottom))
        assign(pull_request, assignments[bottom["number"]])
    return dealt


def merge_lane_pull_request_review_assignments_file_lock(path):
    """Return the lock file beside the assignment file, opened and locked exclusively; closing it
    releases the lock. Every writer of the assignment file, the cron run, the loop watcher and the
    seed, holds it from its read to its replace, so no writer replaces a file another writer
    read before it. Raises OSError."""
    lock = path.with_name(path.name + ".lock").open("a", encoding="utf-8")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX)
    except OSError:
        lock.close()
        raise
    return lock


def merge_lane_pull_request_review_assignment_lines(path, pull_requests, state, options_in_use=(),
                                                    report_stop=emit, record_assigned_lines=None):
    """Deal the pull requests with no assignment, write them to the assignment file, and return
    a REVIEW-ASSIGNED event line for each one the file holds afterwards. A failure passes a WATCH
    line to report_stop each time its case differs from the last poll's, as state records.
    record_assigned_lines, when given, is called with those lines while the lock is held. When it
    raises OSError, the assignment file keeps the deal of each pull request whose line the error
    names as in the event file (EventLinesAppendFailed.written_lines), or every deal when the
    event file could not be read back, and loses the others, so the next poll deals those again;
    the OSError raised then names the kept pull requests, whose lines a failed append may not keep
    through a crash. When putting the file back fails too, it names the pull requests the file
    keeps with no REVIEW-ASSIGNED line recorded."""

    def stop(case, message):
        if state.get("stopped") != case:
            report_stop(message)
        state["stopped"] = case

    try:
        lock = merge_lane_pull_request_review_assignments_file_lock(path)
    except OSError as error:
        stop("lock",
             f"WATCH: review assignment stopped: the lock file beside the assignment file {path} "
             f"cannot be opened or locked ({error}), so no open pull request is given a "
             f"merge-lane agent-seat to review it; the watch goes on otherwise.\n"
             f"  Make the directory {path.parent} writable by the user {getpass.getuser()}, who "
             f"runs the watcher. The watcher assigns again at the first poll that takes the lock.")
        return []
    with lock:
        try:
            text, assignments = merge_lane_pull_request_review_assignments_file_text_and_assignments_read(path)
        except MergeLanePullRequestReviewAssignmentsFileUnusable as error:
            stop(error.case,
                 f"WATCH: review assignment stopped: {error}, so no open pull request is given "
                 f"a merge-lane agent-seat to review it; the watch goes on otherwise.\n"
                 f"{merge_lane_pull_request_review_assignments_file_repair_steps(path, error.case, options_in_use)}"
                 f"  The watcher assigns again at the first poll that reads the whole file.")
            return []
        dealt = merge_lane_pull_request_review_assignments_for_unassigned_pull_requests(
            pull_requests, assignments)
        if not dealt:
            state["stopped"] = None
            return []
        # A write that fails leaves the old file whole, so every pull request dealt here is dealt
        # again at the next poll.
        separator = "\n" if text and not text.endswith("\n") else ""
        try:
            merge_lane_pull_request_review_assignments_file_write(
                path, text + separator + "".join(f"{pull_request['number']} {lane}\n"
                                                 for pull_request, lane in dealt))
        except OSError as error:
            stop("write",
                 f"WATCH: review assignment stopped: the assignment file {path} cannot be "
                 f"rewritten ({error}); it is left as it was, so the pull requests each poll deals "
                 f"are given no merge-lane agent-seat to review them; the watch goes on otherwise.\n"
                 f"  Make the file and its directory writable by the user {getpass.getuser()}, who "
                 f"runs the watcher. Each later poll deals those pull requests again, and the first "
                 f"poll that can write them to the file prints their REVIEW-ASSIGNED lines.")
            return []
        state["stopped"] = None
        assigned_lines = [event_line(pull_request, f"REVIEW-ASSIGNED {lane}")
                          for pull_request, lane in dealt]
        if record_assigned_lines is not None:
            try:
                record_assigned_lines(assigned_lines)
            except OSError as error:
                written = getattr(error, "written_lines", [])
                read_back = getattr(error, "read_back", True)
                # A deal whose line reached, or may have reached, the event file stands: dealing it
                # again could send the pull request to a second agent-seat.
                kept = [(deal, line) for deal, line in zip(dealt, assigned_lines)
                        if line in written or not read_back]
                put_back = [line for line in assigned_lines if read_back and line not in written]
                message = str(error)
                if kept:
                    message += (
                        f". The assignment file {path} keeps these pull requests, whose "
                        f"REVIEW-ASSIGNED lines the event file "
                        + ("held" if read_back else "may hold")
                        + " after the failed append: " + "; ".join(line for _, line in kept)
                        + ". Those lines may not survive a crash, because the append failed. For "
                        "each one the event file does not hold, forward the line to its merge-lane "
                        "agent-seat as you forward REVIEW-ASSIGNED lines")
                if put_back:
                    try:
                        merge_lane_pull_request_review_assignments_file_write(
                            path, text + separator + "".join(
                                f"{pull_request['number']} {lane}\n" for (pull_request, lane), _ in kept))
                    except OSError as put_back_error:
                        raise OSError(
                            f"{message}; and the assignment file {path} could not be put back "
                            f"({put_back_error}), so it assigns these pull requests although no "
                            f"REVIEW-ASSIGNED line for them was recorded: "
                            + "; ".join(put_back)
                            + ". Send each to its merge-lane agent-seat yourself") from error
                if isinstance(error, EventFileCutBackFailed):
                    raise
                raise OSError(message) from error
        return assigned_lines


def merge_lane_pull_request_review_assignments_seed(path, seed_path, repo, token, options_in_use=()):
    """Write the assignment file once: the seed file's lines, then each other open pull request
    with a review by ned-review-merge whose number's remainder MERGE_LANE_BY_PULL_REQUEST_NUMBER_REMAINDER
    gives an agent-seat; the watcher deals the rest. Return the exit status."""
    try:
        lock = merge_lane_pull_request_review_assignments_file_lock(path)
    except OSError as error:
        warn(f"merge-lane-open-prs-watch-and-reviewer-assign: nothing was seeded, because the lock "
             f"file beside the assignment file {path} cannot be opened or locked: {error}. No "
             f"assignment file was made.\n"
             f"  Make the directory {path.parent} writable by the user {getpass.getuser()}, then run "
             f"the same command again.")
        return 1

    def existing_file_kept():
        try:
            merge_lane_pull_request_review_assignments_file_read(path)
        except MergeLanePullRequestReviewAssignmentsFileUnusable as error:
            warn(f"merge-lane-open-prs-watch-and-reviewer-assign: nothing was seeded, because the assignment file "
                 f"exists: seeding would replace it, giving each reviewed pull request the seed "
                 f"file does not name the merge-lane agent-seat of "
                 f"{MERGE_LANE_BY_PULL_REQUEST_NUMBER_REMAINDER_TEXT}, in place of the one it was "
                 f"assigned. The file is damaged: {error}.\n"
                 + merge_lane_pull_request_review_assignments_file_repair_steps(
                     path, error.case, options_in_use)
                 .rstrip("\n"))
            return 1
        emit(f"WATCH: nothing was seeded, because the assignment file {path} exists and every "
             f"line of it reads correctly: seeding would replace it, giving each reviewed pull "
             f"request the seed file does not name the merge-lane agent-seat of "
             f"{MERGE_LANE_BY_PULL_REQUEST_NUMBER_REMAINDER_TEXT}, in place of the one it was "
             f"assigned.\n"
             f"  Do nothing more: the watcher reads the file at each poll.")
        return 0

    with lock:
        if path.exists():
            return existing_file_kept()
        try:
            assignments = merge_lane_pull_request_review_assignments_file_read(seed_path, "seed file")
        except MergeLanePullRequestReviewAssignmentsFileUnusable as error:
            warn(f"merge-lane-open-prs-watch-and-reviewer-assign: nothing was seeded, because {error}.\n"
                 f"  Correct that line as '{ASSIGNMENT_LINE_FORMAT}', asking whoever made the seed "
                 f"file when you cannot tell which agent-seat it meant, then run the same command "
                 f"again.")
            return 1
        pull_requests, reason = fetch_open_pull_requests(repo, token)
        if reason is not None:
            warn(f"merge-lane-open-prs-watch-and-reviewer-assign: nothing was seeded, because reading the open pull "
                 f"requests from GitHub failed: "
                 f"{one_line_snippet(reason, FAILURE_REASON_SNIPPET_CHARS)}\n"
                 f"  Run the same command again once; if it fails again, tell the user that gh on "
                 f"ned-box cannot read the open pull requests, quoting the first line of the "
                 f"last failure's message, and that merge-lane-2's watcher assigns no review until the assignment "
                 f"file is made.\n"
                 f"  If you are a subagent, tell the agent that dispatched you instead of the user.")
            return 1
        from_seed = len(assignments)
        for pull_request in pull_requests:
            lane = MERGE_LANE_BY_PULL_REQUEST_NUMBER_REMAINDER.get(pull_request["number"] % 3)
            if pull_request["number"] not in assignments and pull_request["reviews"] and lane:
                assignments[pull_request["number"]] = lane
        # The lock binds only the programs, so a file put back by hand while GitHub was read is
        # found by the write, which never replaces one.
        try:
            leftover = merge_lane_pull_request_review_assignments_file_write(
                path, "".join(f"{number} {lane}\n" for number, lane in assignments.items()),
                only_when_absent=True)
        except FileExistsError:
            return existing_file_kept()
        except OSError as error:
            warn(f"merge-lane-open-prs-watch-and-reviewer-assign: nothing was seeded, because the "
                 f"assignment file {path} could not be written: {error}. No assignment file was made.\n"
                 f"  Make the directory {path.parent} writable by the user {getpass.getuser()}, then run "
                 f"the same command again.")
            return 1
        emit(f"WATCH: wrote {len(assignments)} assignment(s) to {path}: {from_seed} from {seed_path}, "
             f"and {len(assignments) - from_seed} open pull request(s) with a review by "
             f"the GitHub account {fix_round.MERGE_LANE_2_REVIEWER_LOGIN}, each given the merge-lane agent-seat of "
             f"{MERGE_LANE_BY_PULL_REQUEST_NUMBER_REMAINDER_TEXT}")
        if leftover:
            warn(f"merge-lane-open-prs-watch-and-reviewer-assign: the assignment file {path} was made, "
                 f"but {leftover}.\n"
                 f"  The watcher does not read that file; delete it by hand.")
        return 0


def merge_lane_pull_request_review_assignments_list(path, lane, repo, token, options_in_use=()):
    """Print the lane's open pull requests that are not drafts, and whether each waits for its
    verdict. Return the exit status."""
    try:
        # The lock keeps the read from seeing a deal that a failed append is about to put back.
        lock = merge_lane_pull_request_review_assignments_file_lock(path)
    except OSError as error:
        warn(f"merge-lane-open-prs-watch-and-reviewer-assign: cannot list {lane}'s pull requests, because "
             f"the lock file beside the assignment file {path} cannot be opened or locked ({error}).\n"
             f"  Tell merge-lane-2, which runs the watcher, quoting this message.\n"
             f"  If you are a subagent, report this message to the agent that dispatched you instead of acting on it.")
        return 1
    try:
        with lock:
            assignments = merge_lane_pull_request_review_assignments_file_read(path)
    except MergeLanePullRequestReviewAssignmentsFileUnusable as error:
        warn(f"merge-lane-open-prs-watch-and-reviewer-assign: cannot list {lane}'s pull requests, because "
             f"{error}. merge-lane-2's open-pull-request watcher meets the same failure, and "
             f"assigns no review until the file is repaired.\n"
             f"  If you are merge-lane-2, repair the file by the step for your case:\n"
             + merge_lane_pull_request_review_assignments_file_repair_steps(path, error.case, options_in_use)
             .replace("\n  ", "\n    ").replace("  ", "    ", 1)
             + "  Otherwise, review the pull requests merge-lane-2 has forwarded to you as "
             "REVIEW-ASSIGNED lines, and run this command again before you start the next one.\n"
             "  If you are a subagent, report this message to the agent that dispatched you instead of acting on it.")
        return 1
    pull_requests, reason = fetch_open_pull_requests(repo, token)
    if reason is not None:
        warn(f"merge-lane-open-prs-watch-and-reviewer-assign: cannot list {lane}'s pull requests, because "
             f"reading the open pull requests from GitHub failed: "
             f"{one_line_snippet(reason, FAILURE_REASON_SNIPPET_CHARS)}\n"
             f"  Run the same command again once; if it fails again, tell the user that gh on "
             f"ned-box cannot read the open pull requests, quoting the first line of the "
             f"last failure's message, then carry on with work that does not need the list.\n"
             f"  If you are a subagent, tell the agent that dispatched you instead of the user.")
        return 1
    mine = [pull_request for pull_request in pull_requests
            if assignments.get(pull_request["number"]) == lane and not pull_request["is_draft"]]
    waiting = [pull_request for pull_request in mine
               if pull_request_waits_for_merge_lane_verdict(pull_request)]
    emit(f"{lane}: {len(mine)} open pull request(s) that are not drafts are assigned to it; "
         f"{len(waiting)} of them wait for its verdict on their newest commit")
    for pull_request in mine:
        emit(event_line(pull_request, "WAITS-FOR-VERDICT" if pull_request in waiting
                        else "HAS-VERDICT"))
    return 0


def baseline_line(repo, poll_seconds, pull_requests, from_start):
    ready = [pull_request for pull_request in pull_requests
             if not pull_request["is_draft"]]
    drafts = [pull_request for pull_request in pull_requests
              if pull_request["is_draft"]]
    numbers = " ".join(f"#{pull_request['number']}" for pull_request in ready)
    draft_numbers = " ".join(f"#{pull_request['number']}"
                             for pull_request in drafts)
    what_happens_next = ("each reported below as OPENED" if from_start
                         else "not events; --from-start reports them")
    return (f"WATCH: watching {repo} every {poll_seconds:g}s; "
            f"{len(ready)} open at baseline"
            f"{': ' + numbers if numbers else ''} "
            f"({what_happens_next})"
            + (f"; {len(drafts)} draft(s), not to be reviewed until marked "
               f"ready, which raises READY: {draft_numbers}" if drafts else ""))


class PollStateUnusable(Exception):
    """The state file or event file cannot be trusted; the text says why and how to repair it."""


def poll_state_read(path):
    """Return the state in path. Raises PollStateUnusable, so that no caller can re-baseline."""
    repair = (f"Find out why, then move {path} aside and run this program with "
              f"--poll-once-write-baseline. Events since the last good run are then not reported, "
              f"so list the open pull requests by hand once.")
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise PollStateUnusable(
            f"the state file {path} does not exist. On the first run, run this program with "
            f"--poll-once-write-baseline. If it existed before: {repair}") from error
    except (OSError, ValueError) as error:
        raise PollStateUnusable(f"the state file {path} cannot be read ({error}). {repair}") from error
    try:
        pull_requests = {int(number): {"head_sha": seen["head_sha"], "is_draft": seen["is_draft"]}
                         for number, seen in state["pull_requests"].items()}
        usable = (isinstance(state["notices"], dict)
                  and isinstance(state["notices"].get("reported", {}), dict)
                  and type(state["failed_polls"]) is int
                  and type(state["event_lines_delivered"]) is int
                  and isinstance(state.get("review_assignment", {}), dict)
                  and (state["last_events_task_opened_at"] is None
                       or isinstance(state["last_events_task_opened_at"], (int, float))))
    except (KeyError, TypeError, ValueError, AttributeError) as error:
        raise PollStateUnusable(
            f"the state file {path} lacks a usable field ({error!r}). {repair}") from error
    if not usable:
        raise PollStateUnusable(f"the state file {path} holds a field of the wrong type. {repair}")
    state["pull_requests"] = pull_requests
    return state


def poll_state_write(path, state):
    """Replace the state file whole, so that a run killed while writing leaves the last state."""
    partial = path.with_name(path.name + ".partial")
    partial.write_text(json.dumps(state), encoding="utf-8")
    os.replace(partial, path)


def event_file_line_count(path):
    try:
        return path.read_bytes().count(b"\n")
    except FileNotFoundError:
        return 0


class EventLinesAppendFailed(OSError):
    """An append to the event file failed after it opened the file. written_lines holds the lines
    of the append the file holds whole at the append's offset, in order, which may not survive a
    crash; read_back is False when the file could not be read back, so any line may be there."""

    def __init__(self, message, written_lines, read_back):
        super().__init__(message)
        self.written_lines = written_lines
        self.read_back = read_back


class EventFileCutBackFailed(OSError):
    """The event file ends inside a line, and the bytes after its last newline could not be cut."""


def event_file_cut_back_to_last_whole_line(path):
    """Cut the bytes after the event file's last newline, which an append that stopped inside a
    line leaves, so that the next line does not glue onto them. Raises EventFileCutBackFailed when
    they cannot be cut."""
    try:
        with path.open("rb") as events:
            end = events.seek(0, os.SEEK_END)
            if end == 0:
                return
            events.seek(end - 1)
            if events.read(1) == b"\n":
                return
            while end > 0:
                start = max(0, end - 65536)
                events.seek(start)
                chunk = events.read(end - start)
                newline = chunk.rfind(b"\n")
                if newline >= 0:
                    end = start + newline + 1
                    break
                end = start
    except FileNotFoundError:
        return
    try:
        os.truncate(path, end)
    except OSError as error:
        raise EventFileCutBackFailed(
            f"the event file {path} ends inside a line, which a failed append left, and the poll "
            f"could not cut that line back ({error}), so this poll recorded nothing. Each later "
            f"poll cuts the line back itself before it records, so polls record again once the "
            f"cut works. Fix what the error names; do not edit the event file by hand. When a "
            f"later poll has recorded events, mark this task completed") from error


def event_lines_append(path, lines, now):
    """Append the lines, each after the UTC time. Raises EventLinesAppendFailed when the append
    fails after the file is opened, and OSError when it cannot be opened or ends inside a line
    that cannot be cut back."""
    if not lines:
        return
    # The caller's lock keeps other writers out, so bytes after the last newline are a failed
    # append's.
    event_file_cut_back_to_last_whole_line(path)
    stamp = datetime.datetime.fromtimestamp(now, datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    encoded = [f"{stamp} {redact_secrets(line)}\n".encode("utf-8", errors="replace") for line in lines]
    start = None
    try:
        with path.open("ab") as events:
            start = events.tell()
            events.write(b"".join(encoded))
            events.flush()
            os.fsync(events.fileno())
    except OSError as error:
        if start is None:
            raise
        held = event_file_count_of_appended_lines_found_whole_from_append_offset(path, start, encoded)
        if held is None:
            raise EventLinesAppendFailed(
                f"{error}; the event file {path} could not be read back, so it may hold any of "
                f"this append's {len(lines)} lines", [], read_back=False) from error
        # A WATCH event spans several physical lines, so the last newline may fall inside the
        # event the append stopped in; cut back to that event's start instead.
        whole_end = start + sum(len(line) for line in encoded[:held])
        cut = ""
        try:
            if path.stat().st_size > whole_end:
                os.truncate(path, whole_end)
        except OSError as cut_error:
            cut = (f"; the part of the next event it wrote could not be cut back ({cut_error}), so "
                   f"the next poll cuts back to the last newline, which may keep that event's first "
                   f"lines")
        raise EventLinesAppendFailed(
            f"{error}; the event file {path} holds {held} of this append's {len(lines)} lines{cut}",
            lines[:held], read_back=True) from error


def event_file_count_of_appended_lines_found_whole_from_append_offset(path, offset, encoded_lines):
    """Return how many of the encoded lines the file holds whole, in order, from the offset, or
    None when it cannot be read."""
    try:
        with path.open("rb") as events:
            events.seek(offset)
            found = events.read(sum(len(line) for line in encoded_lines))
    except OSError:
        return None
    held = 0
    for line in encoded_lines:
        if not found.startswith(line):
            break
        found = found[len(line):]
        held += 1
    return held


def open_task_with_subject_exists(task_list_directory, subject):
    """Say whether a task with the subject is not marked completed. Raises OSError."""
    if not task_list_directory.is_dir():
        return False
    for path in task_list_directory.glob("*.json"):
        try:
            task = json.loads(path.read_text(encoding="utf-8"))
        except (FileNotFoundError, ValueError):
            # Claude Code may be replacing the file or have deleted it since the listing.
            continue
        if (isinstance(task, dict) and task.get("subject") == subject
                and task.get("status") != "completed"):
            return True
    return False


def failure_reported(task_list_directory, kind, detail):
    """Print the failure, open one task for its kind, and return the exit status 1."""
    warn(f"merge-lane-open-prs-watch-and-reviewer-assign: {kind}: {detail}")
    subject = FAILURE_TASK_SUBJECT_PREFIX + kind
    try:
        if not open_task_with_subject_exists(task_list_directory, subject):
            agent_seat_task_list.agent_seat_task_list_new_pending_task_write(
                task_list_directory, subject, redact_secrets(detail))
    except OSError as error:
        warn(f"merge-lane-open-prs-watch-and-reviewer-assign: could not open a task in {task_list_directory}: {error}")
    return 1


def events_task_opened_when_due(state, state_path, events_path, task_list_directory, now):
    """Open one task for the undelivered event lines, when one is due; return its id or None."""
    total = event_file_line_count(events_path)
    delivered = state["event_lines_delivered"]
    if total < delivered:
        raise PollStateUnusable(
            f"the event file {events_path} holds {total} lines, but {delivered} were already "
            f"delivered, so it was truncated. Restore it, or set event_lines_delivered in "
            f"{state_path} to {total} once you have read what it holds.")
    if total == delivered or open_task_with_subject_exists(task_list_directory, agent_seat_task_list.AGENT_SEAT_TASK_LIST_MERGE_LANE_2_READ_PULL_REQUEST_EVENTS_TASK_SUBJECT_LINE):
        return None
    last_opened = state["last_events_task_opened_at"]
    if last_opened is not None and now - last_opened < WATCH_OPEN_PULL_REQUESTS_MINIMUM_SECONDS_BETWEEN_EVENTS_TASKS:
        return None
    task_id = agent_seat_task_list.agent_seat_task_list_new_pending_task_write(
        task_list_directory, agent_seat_task_list.AGENT_SEAT_TASK_LIST_MERGE_LANE_2_READ_PULL_REQUEST_EVENTS_TASK_SUBJECT_LINE,
        f"Read lines {delivered + 1} to {total} of {events_path}. Act on them, and mark this task "
        f"completed.")
    state["event_lines_delivered"] = total
    state["last_events_task_opened_at"] = now
    poll_state_write(state_path, state)
    return task_id


def poll_once_write_baseline(arguments, token, state_path, events_path):
    """Write the first state file from the pull requests open now; never replace one."""
    if state_path.exists():
        warn(f"merge-lane-open-prs-watch-and-reviewer-assign: {state_path} already exists, and replacing it would "
             f"drop the events since its last run. Move it aside first if it is unusable.")
        return 1
    pull_requests, reason = fetch_open_pull_requests(arguments.repo, token)
    if reason is not None:
        warn("merge-lane-open-prs-watch-and-reviewer-assign: the baseline poll failed: "
             + one_line_snippet(reason, FAILURE_REASON_SNIPPET_CHARS))
        return 1
    poll_state_write(state_path, {
        "pull_requests": {number: {"head_sha": seen["head_sha"], "is_draft": seen["is_draft"]}
                          for number, seen in pull_requests_by_number(pull_requests).items()},
        "notices": {}, "failed_polls": 0,
        "event_lines_delivered": event_file_line_count(events_path),
        "last_events_task_opened_at": None})
    emit(f"WATCH: wrote the baseline of {len(pull_requests)} open pull request(s) to {state_path}.\n"
         f"  The baseline raises no event, so list the open pull requests by hand once: a pull "
         f"request that opened, got a new head or was marked ready since the last good run, or "
         f"while a watcher started without --poll-once held its events, is reported by no "
         f"one.\n"
         f"  The baseline also counts every line of {events_path} as delivered: read any line "
         f"that no task on {arguments.task_list_directory}, the task list --poll-once opens "
         f"tasks on, named before this baseline.")
    return 0


def poll_once(arguments, assignments_file, options_in_use):
    """One cron run: see the module docstring. assignments_file is None when no review is
    assigned. Return the exit status."""
    directory = arguments.poll_once_directory
    task_list_directory = arguments.task_list_directory
    state_path = directory / WATCH_OPEN_PULL_REQUESTS_POLL_STATE_BETWEEN_CRON_RUNS_FILE_NAME
    events_path = directory / WATCH_OPEN_PULL_REQUESTS_EVENTS_LOG_FILE_NAME
    try:
        directory.mkdir(parents=True, exist_ok=True)
        lock = (directory / LOCK_FILE_NAME).open("w", encoding="utf-8")
    except OSError as error:
        return failure_reported(task_list_directory, "its directory cannot be used",
                                f"{directory}: {error}. Repair the directory.")
    with lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            if arguments.poll_once_write_baseline:
                warn(f"merge-lane-open-prs-watch-and-reviewer-assign: no baseline was written to {state_path}, because "
                     f"a cron run holds {directory / LOCK_FILE_NAME}.\n"
                     f"  Run the same command again; a cron run takes a few seconds.")
                return 1
            return 0
        token, reason = read_token(Path(arguments.token_file).expanduser())
        if reason is not None:
            return failure_reported(task_list_directory, "its GitHub token cannot be used",
                                    f"{reason}. Repair the token file.")
        SECRETS_TO_REDACT.append(token)
        try:
            if arguments.poll_once_write_baseline:
                return poll_once_write_baseline(arguments, token, state_path, events_path)
            state = poll_state_read(state_path)
            lines = needs_a_look_events(arguments.needs_a_look_directory, state["notices"],
                                        state_survives_restarts=True)
            pull_requests, reason = fetch_open_pull_requests(arguments.repo, token)
            now = time.time()
            if reason is None:
                state["failed_polls"] = 0
                lines += events_for_poll(state["pull_requests"], pull_requests)
                if assignments_file is not None:

                    def record_with_this_polls_events(assigned_lines):
                        event_lines_append(events_path, lines + assigned_lines, now)
                        lines.clear()

                    # Cron's output goes to a log nobody reads, so a stop goes to the event file.
                    merge_lane_pull_request_review_assignment_lines(
                        assignments_file, pull_requests, state.setdefault("review_assignment", {}),
                        options_in_use, report_stop=lines.append,
                        record_assigned_lines=record_with_this_polls_events)
                state["pull_requests"] = {
                    number: {"head_sha": seen["head_sha"], "is_draft": seen["is_draft"]}
                    for number, seen in pull_requests_by_number(pull_requests).items()}
            else:
                state["failed_polls"] += 1
            # The event is on disk before the state forgets it, so a crash repeats an event at worst.
            event_lines_append(events_path, lines, now)
            poll_state_write(state_path, state)
            events_task_opened_when_due(state, state_path, events_path, task_list_directory, now)
        except PollStateUnusable as error:
            return failure_reported(task_list_directory, "its state cannot be used", str(error))
        except EventFileCutBackFailed as error:
            # Its own subject, so an open append-failure task does not swallow it.
            return failure_reported(task_list_directory, "its polls record nothing until the event "
                                    "file's last line is cut back", str(error))
        except OSError as error:
            return failure_reported(task_list_directory, "it could not record or deliver events",
                                    f"{error}. The state file still holds the last run that "
                                    f"recorded its events, so the first run after this is repaired "
                                    f"finds this run's events again; lines already in "
                                    f"{events_path} reach a later events task.")
        if reason is None:
            return 0
        snippet = one_line_snippet(reason, FAILURE_REASON_SNIPPET_CHARS)
        if state["failed_polls"] == WATCH_OPEN_PULL_REQUESTS_FAILED_GITHUB_POLLS_IN_A_ROW_BEFORE_FAILURE_TASK:
            return failure_reported(
                task_list_directory, "GitHub queries keep failing",
                f"{state['failed_polls']} polls in a row failed, the last with: {snippet}. "
                f"No event is lost while the state file is kept, except a pull request that "
                f"opens and closes during the outage.")
        warn(f"merge-lane-open-prs-watch-and-reviewer-assign: poll failed: {snippet}")
        return 1


def parse_arguments(argv):
    parser = argparse.ArgumentParser(
        description="Watch a repository's open pull requests; print one "
                    "line per newly opened pull request, per new head "
                    "commit on an open one, per draft marked ready, and per merge-lane agent-seat assigned to review one. "
                    "A draft raises no line.")
    parser.add_argument("--repo", default=DEFAULT_REPO,
                        help=f"OWNER/NAME to watch (default: {DEFAULT_REPO})")
    parser.add_argument("--poll-seconds", type=float, default=DEFAULT_POLL_SECONDS,
                        help=f"seconds between queries (default: "
                             f"{DEFAULT_POLL_SECONDS:g}; one request each, "
                             f"against an authenticated 5,000/hour limit)")
    parser.add_argument("--token-file", default=DEFAULT_TOKEN_FILE,
                        help=f"file holding the GitHub token, passed to gh as "
                             f"GH_TOKEN and never printed (default: "
                             f"{DEFAULT_TOKEN_FILE})")
    parser.add_argument("--from-start", action="store_true",
                        help="report every pull request already open, and not "
                             "a draft, at the first poll as OPENED, instead "
                             "of taking them "
                             "as the silent baseline")
    when_to_exit = parser.add_mutually_exclusive_group()
    when_to_exit.add_argument("--exit-after-first-poll-with-events", action="store_true",
                              help="exit 0 after the first poll that prints an "
                                   "OPENED, NEW-HEAD, READY, REVIEW-ASSIGNED or NEEDS A LOOK line, once "
                                   "every event of that poll is printed")
    when_to_exit.add_argument("--batch-events-for-seconds", type=float, metavar="N",
                              help="hold every OPENED, NEW-HEAD, READY, REVIEW-ASSIGNED and NEEDS A "
                                   "LOOK line instead of printing it; print them "
                                   "all and exit 0 when a poll finishes N or more "
                                   "seconds after the start while any is held, even "
                                   "one that poll found; once one is held, the next "
                                   "poll starts by N at the latest; a poll can "
                                   "take up to "
                                   f"{GH_QUERY_TIMEOUT_SECONDS:g} seconds per query "
                                   "page")
    when_to_exit.add_argument("--poll-once", action="store_true",
                              help="make one poll, append its events to the event file, "
                                   "open a task on merge-lane-2's task list when one is "
                                   "due, and exit; the form the cron job runs")
    when_to_exit.add_argument("--poll-once-write-baseline", action="store_true",
                              help="write the first state file for --poll-once from the "
                                   "pull requests open now, raising no event; refuses when "
                                   "a state file exists")
    parser.add_argument("--poll-once-directory", type=Path,
                        help="directory of --poll-once's state, event file and lock "
                             f"(default: {OPEN_PRS_WATCH_POLL_ONCE_STATE_EVENTS_AND_LOCK_DEFAULT_DIRECTORY} with the default --repo; "
                             "with another --repo, give this option too)")
    parser.add_argument("--task-list-directory", type=Path,
                        default=Path.home() / ".claude" / "tasks" / "nedsnodes-merge-lane-2-tasks",
                        help="the task list --poll-once opens tasks on (default: %(default)s)")
    parser.add_argument("--needs-a-look-directory", type=Path,
                        default=ghi_md_edit_job.needs_a_look_directory(),
                        help="the GHI-MD edit job's notices directory to list each "
                             "poll (default: %(default)s)")
    parser.add_argument("--merge-lane-pr-review-assignments-file", type=Path,
                        help="the file of '<pull request number> <merge-lane agent-seat>' "
                             "lines this watcher reads and rewrites at each poll (default: "
                             f"{MERGE_LANE_PULL_REQUEST_REVIEW_ASSIGNMENTS_DEFAULT_FILE} with the "
                             "default --repo; with another --repo, none, and no review is "
                             "assigned)")
    # Each of these exits instead of watching, so it shares the group of the ways to watch.
    when_to_exit.add_argument(
        "--merge-lane-pr-review-assignments-file-write-from-seed-and-reviewed-prs-then-exit",
        type=Path, metavar="SEED_FILE",
        help="make the assignment file, once, from SEED_FILE's lines in the same format, "
             "plus each other open pull request with a review by "
             f"{fix_round.MERGE_LANE_2_REVIEWER_LOGIN}, given the merge-lane agent-seat of "
             "its number's remainder (1 merge-lane-1, 0 merge-lane-3, 2 none, left for the "
             "watcher to deal); "
             "refuses when the file exists; then exit instead of watching")
    when_to_exit.add_argument(
        "--merge-lane-pr-review-assignments-list-for",
        choices=MERGE_LANE_PULL_REQUEST_REVIEW_ASSIGNEE_AGENT_SEATS_IN_TIE_ORDER, metavar="MERGE_LANE",
        help="print the open pull requests that are not drafts the assignment file gives "
             "MERGE_LANE, and whether each waits for a verdict on its newest commit; then "
             "exit instead of watching")
    return parser.parse_args(argv)


def main(argv=None):
    arguments = parse_arguments(argv)
    if arguments.poll_seconds <= 0:
        warn("merge-lane-open-prs-watch-and-reviewer-assign: --poll-seconds must be > 0")
        return 2
    batch_seconds = arguments.batch_events_for_seconds
    if batch_seconds is not None and batch_seconds <= 0:
        warn("merge-lane-open-prs-watch-and-reviewer-assign: --batch-events-for-seconds must be > 0")
        return 2
    owner, slash, name = arguments.repo.partition("/")
    if not (owner and slash and name) or "/" in name:
        warn(f"merge-lane-open-prs-watch-and-reviewer-assign: --repo must be OWNER/NAME, "
             f"not {arguments.repo!r}")
        return 2
    assignments_file = arguments.merge_lane_pr_review_assignments_file
    # GitHub reads an owner and name in any case.
    repo_is_default = arguments.repo.lower() == DEFAULT_REPO.lower()
    # The default file holds the default repository's pull request numbers only.
    if assignments_file is None and repo_is_default:
        assignments_file = MERGE_LANE_PULL_REQUEST_REVIEW_ASSIGNMENTS_DEFAULT_FILE
    options_in_use = [*(["--repo", arguments.repo] if not repo_is_default else []),
                      *(["--token-file", arguments.token_file]
                        if arguments.token_file != DEFAULT_TOKEN_FILE else [])]
    if arguments.poll_once or arguments.poll_once_write_baseline:
        if arguments.poll_once_directory is None:
            if not repo_is_default:
                warn(f"merge-lane-open-prs-watch-and-reviewer-assign: --repo {arguments.repo} is not "
                     f"the default repository {DEFAULT_REPO}, and the default --poll-once-directory "
                     f"holds only {DEFAULT_REPO}'s state, so give --poll-once-directory a directory "
                     f"for {arguments.repo}'s state; the run makes it if it is missing.")
                return 2
            arguments.poll_once_directory = OPEN_PRS_WATCH_POLL_ONCE_STATE_EVENTS_AND_LOCK_DEFAULT_DIRECTORY
        return poll_once(arguments, assignments_file, options_in_use)
    token, reason = read_token(Path(arguments.token_file).expanduser())
    if reason is not None:
        warn(f"merge-lane-open-prs-watch-and-reviewer-assign: {reason}")
        return 2
    SECRETS_TO_REDACT.append(token)

    # Author-supplied titles must not kill the watch on an unencodable character.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")

    seed_file = arguments.merge_lane_pr_review_assignments_file_write_from_seed_and_reviewed_prs_then_exit
    instead_of_watching = (seed_file is not None
                           or arguments.merge_lane_pr_review_assignments_list_for is not None)
    if instead_of_watching and assignments_file is None:
        warn(f"merge-lane-open-prs-watch-and-reviewer-assign: --repo {arguments.repo} is not the default "
             f"repository, whose pull requests the default assignment file numbers, so name the "
             f"file for {arguments.repo} with --merge-lane-pr-review-assignments-file.")
        return 2
    if seed_file is not None:
        return merge_lane_pull_request_review_assignments_seed(
            assignments_file, seed_file, arguments.repo, token, options_in_use)
    if arguments.merge_lane_pr_review_assignments_list_for is not None:
        return merge_lane_pull_request_review_assignments_list(
            assignments_file, arguments.merge_lane_pr_review_assignments_list_for,
            arguments.repo, token, options_in_use)
    assignment_state = {}

    known_pull_requests = None
    blind_since = None
    failed_polls = 0
    notices_state = {}
    started = time.monotonic()
    held_lines = []

    def report(lines):
        if batch_seconds is None:
            for line in lines:
                emit(line)
        else:
            held_lines.extend(lines)

    def poll_ends_the_watch(poll_lines):
        """Print what batching held when the watch is over; return whether it is."""
        if batch_seconds is None:
            return bool(poll_lines) and arguments.exit_after_first_poll_with_events
        if not held_lines or time.monotonic() - started < batch_seconds:
            return False
        for line in held_lines:
            emit(line)
        return True

    def sleep_until_next_poll():
        seconds = arguments.poll_seconds
        if held_lines:
            # Poll again at N exactly, so held events print once the poll at N finishes.
            seconds = min(seconds, started + batch_seconds - time.monotonic())
        time.sleep(max(seconds, 0))

    while True:
        notice_lines = needs_a_look_events(arguments.needs_a_look_directory, notices_state)
        report(notice_lines)
        pull_requests, reason = fetch_open_pull_requests(arguments.repo, token)
        if reason is not None:
            failed_polls += 1
            if blind_since is None:
                blind_since = time.monotonic()
                emit("WATCH: query failed, so this watch is BLIND until it "
                     "recovers (nothing is being seen; the recovery line "
                     "below flags anything the blindness cost): "
                     + one_line_snippet(reason, FAILURE_REASON_SNIPPET_CHARS))
            if poll_ends_the_watch(notice_lines):
                return 0
            sleep_until_next_poll()
            continue

        if blind_since is not None:
            # Before the first baseline, outage openings cannot be distinguished from already-open pull requests.
            # --from-start reports all of them, so no loss warning applies.
            lost_openings_silently = (known_pull_requests is None
                                      and not arguments.from_start)
            emit(f"WATCH: query recovered after {failed_polls} failed poll(s), "
                 f"about {time.monotonic() - blind_since:.0f}s blind"
                 + (" — and this watch had NO BASELINE yet, so anything that "
                    "opened during that blindness is absorbed into the "
                    "baseline below and gets no OPENED line (re-run with "
                    "--from-start to have the baseline reported as events)"
                    if lost_openings_silently else ""))
            blind_since = None
            failed_polls = 0

        if known_pull_requests is None:
            emit(baseline_line(arguments.repo, arguments.poll_seconds,
                               pull_requests, arguments.from_start))
            known_pull_requests = ({} if arguments.from_start
                                   else pull_requests_by_number(pull_requests))

        event_lines = events_for_poll(known_pull_requests, pull_requests)
        if assignments_file is not None:
            event_lines += merge_lane_pull_request_review_assignment_lines(
                assignments_file, pull_requests, assignment_state, options_in_use)
        report(event_lines)
        if poll_ends_the_watch(notice_lines + event_lines):
            return 0
        # Drop closed pull requests so reopening produces another OPENED event.
        known_pull_requests = pull_requests_by_number(pull_requests)
        sleep_until_next_poll()


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(130)
    except BrokenPipeError:
        os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
        sys.exit(0)
