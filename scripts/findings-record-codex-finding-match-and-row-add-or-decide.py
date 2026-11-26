#!/usr/bin/env python3
"""Match each Codex finding on main's code against the findings record, and add the new ones to it.

The findings record is the nn-shared-database's findings_record_row table, one row per
defect a reviewer found on main, reached through the nn-shared-database service.

Usage:
  scripts/findings-record-codex-finding-match-and-row-add-or-decide.py [--service-url URL] match
      --pull-request N --head-commit SHA [--repository DIR] [--claude-program PATH] < findings.json
  scripts/findings-record-codex-finding-match-and-row-add-or-decide.py [--service-url URL] add
      --pull-request N --head-commit SHA [--repository DIR] [--possible-miss-log PATH]
      < graded-findings.json
  scripts/findings-record-codex-finding-match-and-row-add-or-decide.py [--service-url URL] decide
      RECORD_ID --state STATE --decision TEXT [--filed-where TEXT] [--owning-agent-seat NAME]

--service-url goes before the subcommand, since it belongs to the program, not to one subcommand.

match and add read a JSON list of findings, each {"finding_id", "priority", "heading",
"text"}, and for add also "grade", and for does-not-hold "reason": the heading is the
Codex heading's text, "<title> — <path>:<line>[-<line>]", and the text the whole finding
from its heading line on. --repository, by default this checkout, is where git reads
the cited line's text at the head commit. For each finding, code asks the service for
the row a sighting of finding_id is on, the three rows FTS5 ranks best for the text, and
the rows citing the same path and line text.

match records only sightings. When the held row was added from this finding at this head
commit, it answers NEW with that row's id; when another row holds the finding, SAME with
that row, with no judgment; otherwise, when the search gives candidates, one judgment
step, a headless `claude -p` with no tools, must answer exactly `SAME <record id>` of a
candidate, or `NEW`. On SAME it records the finding as a sighting of the row. It prints
one JSON object, by finding id: {"answer": "SAME", "record": <the row>,
"possible_regression": <whether the row is fixed>} or {"answer": "NEW", "record_id":
<the row already added from it, or null>}.

add, run once merge-lane-2's grades are accepted, adds each finding no row holds as a row
in state new holding the finding, its four labelled lines and its grade, a does-not-hold
reason as its decision; when a row already cites the same path and line text, it appends
one JSON line to the possible-miss log, by default
findings-record/findings-record-possible-misses.jsonl in the log-store. It prints one
JSON object, by finding id: {"record_id": <the row>, "possible_miss_of": [<record ids>]}.

decide records a decision on a row: its state, one of the service's
FINDINGS_RECORD_ROW_STATES, and its decision, a link or a reason.

Exit codes: 0 done; 1 a step failed, with what failed on standard error: the service
could not be reached or refused, git could not read the line, the judgment step failed
or answered other than one of its output states, or the possible-miss log could not be
written; 2 a bad invocation or input. Rows and sightings already recorded stay: running
the same command again records nothing twice.
"""

import argparse
import importlib.util
import json
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def load_program(path, module_name):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


service_call = load_program(
    REPOSITORY_ROOT / "nn-systems" / "nn-shared-database" / "nn-shared-database-service-call-common.py",
    "nn_shared_database_service_call_common")
command_line_prefix = load_program(
    REPOSITORY_ROOT / "nn-systems" / "general-tools"
    / "claude-code-headless-run-command-line-prefix-with-no-connectors-and-explicit-permission-mode-common.py",
    "claude_code_headless_run_command_line_prefix_with_no_connectors_and_explicit_permission_mode_common")
path_constants = load_program(
    REPOSITORY_ROOT / "nn-systems" / "general-tools"
    / "ned-box-home-directory-and-its-mac-mount-point-path-constants-common.py",
    "ned_box_home_directory_and_its_mac_mount_point_path_constants_common")

FINDINGS_RECORD_ROW_STATES = ("new", "filed", "decided-fix", "decided-not-worth-fixing", "needs-user", "fixed")
MATCH_JUDGMENT_MODEL = "claude-sonnet-5-5"
MATCH_JUDGMENT_TIMEOUT_SECONDS = 300
MATCH_JUDGMENT_ANSWER = re.compile(r"\A(?:SAME (\d+)|NEW)\Z")
CODEX_HEADING_PATH_AND_LINE = re.compile(r" — (\S+?):(\d+)(?:-\d+)?\s*\Z")
# docs/agents/pr-reviewer-instructions.md asks a reviewer to end each finding on code with these hashtag lines.
FINDING_FACT_LINE_HASHTAG_FIELDS = {"#defect_already_on_main": "main_has_it",
                                    "#pull_request_triggers_the_defect": "this_pull_request_makes_it_happen",
                                    "#false_report_of_success_on_failure": "reports_success_on_failure",
                                    "#defect_evidence": "shown_by"}
# Reviewers may still write the labels the hashtags replaced, each followed by a colon.
FINDING_FACT_LINE_OLDER_LABELS = {"Main has it": "#defect_already_on_main",
                                  "This pull request makes it happen": "#pull_request_triggers_the_defect",
                                  "Reports success on failure": "#false_report_of_success_on_failure",
                                  "Shown by": "#defect_evidence"}
# A hashtag or a label may open a list item of any kind and sit inside code or bold marks, and a label's colon
# may sit inside or outside them.
FINDING_FACT_LINE = re.compile(
    r"^[ \t]*(?:(?:[-*+]|\d+[.)])[ \t]+)?[`*_]*(?:("
    + "|".join(map(re.escape, FINDING_FACT_LINE_HASHTAG_FIELDS)) + r")(?!\w)|("
    + "|".join(map(re.escape, FINDING_FACT_LINE_OLDER_LABELS)) + r")[`*_]*:)[ \t]*(.*)$", re.MULTILINE)
POSSIBLE_MISS_LOG_UNDER_LOG_STORE = Path("findings-record") / "findings-record-possible-misses.jsonl"
DOES_NOT_HOLD_GRADE = "does-not-hold"

MATCH_JUDGMENT_SYSTEM_PROMPT = (
    "You decide whether a new code review finding reports the same defect as one of the earlier findings "
    "listed with it. The same defect means the same wrong behaviour in the same code, even when the "
    "wording, the title or the line numbers differ, because the code may have moved. A different defect "
    "in the same file or function is not the same. Answer with exactly one line and nothing else: "
    "`SAME <record id>`, with the record id of the earlier finding that reports the same defect, or `NEW` "
    "when none does.")

# Messages follow docs/nedsnodes-wiki/nedsnodes-how-to-write-a-tool-message-to-agent-such-as-a-hook-refusal-or-script-error.md.
FAILED_MESSAGE_FIRST_LINES = (
    "FAILED: the findings record {command}, scripts/findings-record-codex-finding-match-and-row-add-or-decide.py "
    "{command}, stopped at finding {finding_id} of pull request {number}: {reason}\n"
    "Rows and sightings recorded before this finding stay, and running the same command again, with the same "
    "input, records none of them twice.\n")
SERVICE_CALL_FAILED_MESSAGE = FAILED_MESSAGE_FIRST_LINES + (
    "Do what the nn-shared-database service's message above says; if it says to tell the user, post no review of "
    "pull request {number} until he answers.")
STEP_FAILED_MESSAGE = FAILED_MESSAGE_FIRST_LINES + (
    "Do the step the reason gives, if it gives one. Then run once more the command you ran: "
    "scripts/merge-lane-pull-request-reviewer-review-post-and-read-back.py, which runs this program, or this "
    "program itself.\n"
    "If that rerun prints this message again, at any finding, do not run it a third time: tell the user \"The "
    "findings record {command} for pull request {number} fails: {reason}\", and post no review of pull request "
    "{number} until he answers; go on with other work meanwhile.\n"
    "If you are a subagent, send those words to the agent that dispatched you instead.")
JUDGMENT_ANSWER_UNLISTED_REASON = (
    "the judgment step answered {answer!r}, which is neither NEW nor SAME with one of the record ids it was "
    "given, {record_ids}, so the program did not guess which it meant")
LINE_UNREADABLE_REASON = (
    "git could not read {path} at commit {head} in {repository}: {error}. The row records the line's text "
    "at the head commit. If the commit is missing there, run `git -C {repository} fetch origin "
    "pull/{number}/head`")


class MatchStepFailed(Exception):
    pass


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def finding_fact_lines(text):
    """(hashtag, answer) for each fact line of a finding's text, in order, a line opened by an older label
    given under the hashtag that replaced it; the answer is the rest of the line as written."""
    return [(hashtag or FINDING_FACT_LINE_OLDER_LABELS[label], answer)
            for hashtag, label, answer in FINDING_FACT_LINE.findall(text)]


def fact_line_answers(text):
    answers = dict.fromkeys(FINDING_FACT_LINE_HASHTAG_FIELDS.values())
    for hashtag, answer in finding_fact_lines(text):
        field = FINDING_FACT_LINE_HASHTAG_FIELDS[hashtag]
        answers[field] = answers[field] or answer.strip().strip("`*_ \t") or None
    return answers


def line_text_at_head(repository, head, path, line, number):
    completed = subprocess.run(["git", "-C", str(repository), "show", f"{head}:{path}"],
                               capture_output=True, text=True, stdin=subprocess.DEVNULL)
    if completed.returncode != 0:
        raise MatchStepFailed(LINE_UNREADABLE_REASON.format(
            path=path, head=head, repository=repository, error=completed.stderr.strip(), number=number))
    lines = completed.stdout.splitlines()
    if not 0 < line <= len(lines):
        raise MatchStepFailed(LINE_UNREADABLE_REASON.format(
            path=path, head=head, repository=repository, number=number,
            error=f"the finding cites line {line}, and the file has {len(lines)} line(s) there"))
    return lines[line - 1]


def match_judgment(finding, candidates, claude_program):
    """Return the record id the judgment step answers SAME with, or None for NEW."""
    listed = [{key: row[key] for key in ("record_id", "path", "line", "line_text", "finding_text")}
              for row in candidates]
    prompt = ("New finding:\n" + finding["text"] + "\n\nEarlier findings:\n"
              + json.dumps(listed, ensure_ascii=False, indent=1) + "\n")
    command = [*command_line_prefix.claude_code_headless_run_command_line_prefix_build(
                   "dontAsk", program=claude_program, caller_claude_code_session_settings={"disableAllHooks": True}),
               "--model", MATCH_JUDGMENT_MODEL, "--output-format", "json", "--system-prompt",
               MATCH_JUDGMENT_SYSTEM_PROMPT, "--tools", "", "--no-session-persistence"]
    try:
        completed = subprocess.run(command, input=prompt, capture_output=True, text=True,
                                   timeout=MATCH_JUDGMENT_TIMEOUT_SECONDS, cwd=tempfile.gettempdir())
    except subprocess.TimeoutExpired:
        raise MatchStepFailed(f"the judgment step, {claude_program} -p, gave no answer within "
                              f"{MATCH_JUDGMENT_TIMEOUT_SECONDS} seconds")
    except OSError as error:
        raise MatchStepFailed(f"the judgment step, {claude_program} -p, could not be run: {error}")
    try:
        result = json.loads(completed.stdout)
        answer = result["result"]
    except (ValueError, TypeError, KeyError) as error:
        detail = (completed.stderr or completed.stdout or "no output").strip()[:300]
        raise MatchStepFailed(f"the judgment step, {claude_program} -p, exited {completed.returncode} with no "
                              f"answer ({error!r}): {detail}")
    if completed.returncode != 0 or result.get("is_error"):
        raise MatchStepFailed(f"the judgment step, {claude_program} -p, exited {completed.returncode} "
                              f"reporting an error: {str(answer)[:300]}")
    record_ids = [row["record_id"] for row in candidates]
    parsed = MATCH_JUDGMENT_ANSWER.match(str(answer).strip())
    if not parsed or (parsed[1] is not None and int(parsed[1]) not in record_ids):
        raise MatchStepFailed(JUDGMENT_ANSWER_UNLISTED_REASON.format(answer=answer, record_ids=record_ids))
    return int(parsed[1]) if parsed[1] is not None else None


def default_possible_miss_log():
    for home in (path_constants.NED_BOX_HOME, path_constants.MAC_MOUNT_OF_NED_BOX_HOME):
        log_store = Path(home) / "nedsnodes-logs"
        if log_store.is_dir():
            return log_store / POSSIBLE_MISS_LOG_UNDER_LOG_STORE
    raise MatchStepFailed(f"the log-store, which holds the possible-miss log, is at neither "
                          f"{path_constants.NED_BOX_HOME}/nedsnodes-logs nor "
                          f"{path_constants.MAC_MOUNT_OF_NED_BOX_HOME}/nedsnodes-logs")


def possible_miss_log_append(log_path, entry):
    try:
        log_path = log_path or default_possible_miss_log()
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(log_path, "a", encoding="utf-8") as log:
            log.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError as error:
        raise MatchStepFailed(f"the possible-miss log {log_path} could not be written: {error}")


def search_one(finding, arguments, call):
    """Return (path, line, line text, the service's search answer) for one finding."""
    cited = CODEX_HEADING_PATH_AND_LINE.search(finding["heading"])
    if not cited:
        raise MatchStepFailed(f"its heading {finding['heading']!r} cites no `<path>:<line>` after ` — `, "
                              f"so the row would have no place in the code")
    path, line = cited[1], int(cited[2])
    line_text = line_text_at_head(arguments.repository, arguments.head_commit, path, line, arguments.pull_request)
    found = call("/findings-record-rows/search", {"finding_id": finding["finding_id"],
                                                  "finding_text": finding["text"], "path": path,
                                                  "line_text": line_text})
    return path, line, line_text, found


def added_from_this_finding(held, finding, head):
    return held is not None and held["added_from_finding_id"] == finding["finding_id"] and held["line_commit"] == head


def match_one(finding, arguments, call):
    number, head = arguments.pull_request, arguments.head_commit
    _, _, _, found = search_one(finding, arguments, call)
    held, candidates = found["held"], found["candidates"]
    if added_from_this_finding(held, finding, head):
        return {"answer": "NEW", "record_id": held["record_id"]}
    if held is not None:
        same = held
    else:
        same_id = match_judgment(finding, candidates, arguments.claude_program) if candidates else None
        same = next((row for row in candidates if row["record_id"] == same_id), None)
    if same is None:
        return {"answer": "NEW", "record_id": None}
    call("/events", service_call.nn_shared_database_event_body(
        "findings-record-row-sighting-added", None,
        {"record_id": same["record_id"], "finding_id": finding["finding_id"], "pull_request": number,
         "head_commit": head},
        event_id=f"findings-record-row-sighting-added-{finding['finding_id']}-{head}"))
    return {"answer": "SAME", "record": same, "possible_regression": same["state"] == "fixed"}


def add_one(finding, arguments, call):
    number, head = arguments.pull_request, arguments.head_commit
    path, line, line_text, found = search_one(finding, arguments, call)
    if found["held"] is not None:
        return {"record_id": found["held"]["record_id"], "possible_miss_of": []}
    # Logged before the row is added, since a rerun finds the row held and would log nothing.
    misses = found["same_line_record_ids"]
    if misses:
        possible_miss_log_append(arguments.possible_miss_log, {
            "at": utc_now(), "finding_id": finding["finding_id"], "same_path_and_line_text_as": misses,
            "pull_request": number, "head_commit": head, "path": path, "line_text": line_text})
    added = call("/events", service_call.nn_shared_database_event_body(
        "findings-record-row-added", None,
        {"finding_id": finding["finding_id"], "pull_request": number, "head_commit": head, "path": path,
         "line": line, "line_text": line_text, "outside_program": None,
         "statement": finding["heading"], "finding_text": finding["text"], **fact_line_answers(finding["text"]),
         "grade": finding["grade"],
         "decision": finding.get("reason") if finding["grade"] == DOES_NOT_HOLD_GRADE else None,
         "filed_where": None, "owning_agent_seat": None},
        event_id=f"findings-record-row-added-{finding['finding_id']}"))
    return {"record_id": added["sequence"], "possible_miss_of": misses}


def findings_read(text, graded):
    findings = json.loads(text)
    keys = {"finding_id", "priority", "heading", "text"} | ({"grade"} if graded else set())
    if not isinstance(findings, list) or not all(
            isinstance(finding, dict)
            and (set(finding) == keys or graded and set(finding) == keys | {"reason"})
            and all(isinstance(value, str) for value in finding.values()) for finding in findings):
        raise ValueError("not a list of objects with exactly a text finding_id, priority, heading and text"
                         + (", and grade, and for a does-not-hold grade a reason" if graded else ""))
    return findings


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--service-url", default=service_call.NN_SHARED_DATABASE_SERVICE_URL)
    commands = parser.add_subparsers(dest="command", required=True)
    match = commands.add_parser("match")
    match.add_argument("--pull-request", type=int, required=True)
    match.add_argument("--head-commit", required=True)
    match.add_argument("--repository", type=Path, default=REPOSITORY_ROOT)
    match.add_argument("--claude-program", default=command_line_prefix.CLAUDE_CODE_PROGRAM)
    add = commands.add_parser("add")
    add.add_argument("--pull-request", type=int, required=True)
    add.add_argument("--head-commit", required=True)
    add.add_argument("--repository", type=Path, default=REPOSITORY_ROOT)
    add.add_argument("--possible-miss-log", type=Path)
    decide = commands.add_parser("decide")
    decide.add_argument("record_id", type=int)
    decide.add_argument("--state", choices=FINDINGS_RECORD_ROW_STATES, required=True)
    decide.add_argument("--decision", required=True)
    decide.add_argument("--filed-where")
    decide.add_argument("--owning-agent-seat")
    arguments = parser.parse_args(argv)

    def call(path, body):
        return service_call.nn_shared_database_service_http_request_single_attempt(
            path, body, service_url=arguments.service_url)

    if arguments.command == "decide":
        try:
            call("/events", service_call.nn_shared_database_event_body(
                "findings-record-row-decision-recorded", None,
                {"record_id": arguments.record_id, "state": arguments.state, "decision": arguments.decision,
                 "filed_where": arguments.filed_where, "owning_agent_seat": arguments.owning_agent_seat}))
        except service_call.NnSharedDatabaseServiceCallFailed as failure:
            print(failure, file=sys.stderr)
            return 1
        print(f"findings record row {arguments.record_id} is now {arguments.state}: {arguments.decision}")
        return 0
    try:
        findings = findings_read(sys.stdin.read(), graded=arguments.command == "add")
    except ValueError as error:
        print(f"FAILED: the findings on standard input are {error}; give the JSON list this program's "
              f"docstring describes.", file=sys.stderr)
        return 2
    answers = {}
    for finding in findings:
        try:
            answers[finding["finding_id"]] = (add_one if arguments.command == "add" else match_one)(
                finding, arguments, call)
        except (MatchStepFailed, service_call.NnSharedDatabaseServiceCallFailed) as error:
            message = STEP_FAILED_MESSAGE if isinstance(error, MatchStepFailed) else SERVICE_CALL_FAILED_MESSAGE
            print(message.format(command=arguments.command, finding_id=finding["finding_id"],
                                 number=arguments.pull_request, reason=error), file=sys.stderr)
            return 1
    print(json.dumps(answers, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
