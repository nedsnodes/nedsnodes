#!/usr/bin/env python3
"""Checks the idle sweep's ListAgents ref formula against the refs the installed Claude Code
gives the agent-sessions on this machine.

The idle sweep, scripts/agent-seat-idle-sweep-headless-judge-wake-messages-send-and-user-alerts-write.py,
computes an agent-session's ListAgents ref from its session record in ~/.claude/sessions with a
formula read out of the Claude Code binary, which Claude Code does not document. Should a Claude
Code update change the formula or the session record, every wake message would fail to send; this
suite reports the change at the next full test run, since a selective run does not see a Claude
Code update.

Each agent-session with a session record that has called ListAgents since it started has the result in its
transcript, ~/.claude/projects/<project>/<sessionId>.jsonl, opening "This session is <name>
[<ref>]": the ref Claude Code advertises for it. The suite computes the ref of each such
agent-session with the idle sweep's own function and compares the two. It reads the real HOME and
writes nothing. Where no agent-session has such a result, as on a machine with no
agent-sessions, it prints a SKIP line.

What it does not handle: a Claude Code update that renames `sessionId` or `startedAt` leaves no
agent-session to compare, so the suite prints SKIP and passes; and while running agent-sessions
still run an older version than the installed binary, it checks only that older version's refs.
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
import re
import sys
from datetime import datetime
from pathlib import Path

PROGRAM = Path(__file__).with_name(
    "agent-seat-idle-sweep-headless-judge-wake-messages-send-and-user-alerts-write.py")
_spec = importlib.util.spec_from_file_location("idle_sweep", PROGRAM)
idle_sweep = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(idle_sweep)

# Claude Code lengthens a ref past 6 hex digits only when two refs share their first 6.
SELF_LINE = re.compile(r"This session is .* \[(?P<ref>[0-9a-f]{6,})\]")
SELF_LINE_MARKER = b"This session is "

failures = []


def check(name, condition, detail=""):
    print(("PASS  " if condition else "FAIL  ") + name)
    if not condition:
        failures.append(name)
        if detail:
            print("      " + str(detail).replace("\n", "\n      "))


def session_records_by_session_id(records_directory):
    """{sessionId: record} for each readable session record; a session id two records share is
    left out, since which one ListAgents shows cannot be told. Whether a record's process still
    runs is not checked: the test sandbox has its own process ids, and a dead process's record
    still names the socket its ListAgents results were computed from."""
    by_session = {}
    for path in sorted(records_directory.glob("*.json")):
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue  # Claude Code rewrites and deletes records while agent-sessions run and exit
        if not isinstance(record, dict):
            continue
        by_session.setdefault(record.get("sessionId"), []).append(record)
    return {session: records[0] for session, records in by_session.items()
            if session and len(records) == 1}


def last_advertised_ref(transcript, started_at_milliseconds):
    """The ref in the last ListAgents result in transcript recorded since the agent-session's
    process started, or None. A resumed agent-session's earlier processes had other sockets, so
    other refs."""
    ref = None
    with transcript.open("rb") as stream:
        for line in stream:
            if SELF_LINE_MARKER not in line:
                continue
            try:
                entry = json.loads(line)
                when = datetime.fromisoformat(entry["timestamp"].replace("Z", "+00:00"))
            except (ValueError, KeyError, TypeError, AttributeError):
                continue
            if when.timestamp() * 1000 < started_at_milliseconds:
                continue
            content = (entry.get("message") or {}).get("content")
            for part in content if isinstance(content, list) else []:
                if not isinstance(part, dict) or part.get("type") != "tool_result":
                    continue
                text = part.get("content")
                if isinstance(text, list):
                    text = "".join(piece.get("text", "") for piece in text if isinstance(piece, dict))
                match = SELF_LINE.match(text) if isinstance(text, str) else None
                if match:
                    ref = match["ref"]
    return ref


def main():
    claude = Path.home() / ".claude"
    records_directory = Path.home() / idle_sweep.SESSION_RECORDS_DIRECTORY_UNDER_HOME
    records = session_records_by_session_id(records_directory)
    compared = 0
    for session_id, record in records.items():
        transcripts = list((claude / "projects").glob(f"*/{session_id}.jsonl"))
        if len(transcripts) != 1 or not isinstance(record.get("startedAt"), (int, float)):
            continue
        advertised = last_advertised_ref(transcripts[0], record["startedAt"])
        if advertised is None:
            continue
        compared += 1
        computed = idle_sweep.list_agents_tool_entry_ref_of_running_agent_session_id(session_id)
        check(f"the idle sweep computes the ref Claude Code {record.get('version')} advertises for "
              f"agent-session {session_id}",
              computed is not None and computed.startswith(advertised),
              f"advertised [{advertised}], computed {computed!r}, from the record of pid "
              f"{record.get('pid')} with messagingSocketPath {record.get('messagingSocketPath')!r}")
    if compared == 0:
        print(f"SKIP  the ref formula: no agent-session in {records_directory} has a "
              "ListAgents result in its transcript since it started")
    if failures:
        print(f"{len(failures)} case(s) failed")
        return 1
    print("all cases passed")
    return 0


if __name__ == "__main__":
    # A crash ends the suite with its traceback and no END line, which is how the test runner tells it apart from a failure.
    sys.exit(main())
