#!/usr/bin/env python3
"""Keep the nn-shared-database: a record of every agent-seat on both machines, and the findings
record of reviewer findings on main, behind a narrow JSON API over HTTP.

Usage:
  nn-systems/nn-shared-database/nn-shared-database-service.py
      [--database PATH] [--accepted-tokens-file PATH] [--host HOST] [--port N]

  --database              default ~/.local/state/nedsnodes/nn-shared-database.sqlite3,
                          made when absent, and given each table of its schema
                          it lacks at every start
  --accepted-tokens-file  default ~/.config/nedsnodes/nn-shared-database-service-accepted-tokens,
                          one token per line, read at every request
  --host, --port          default every address, port 8765

On ned-box the systemd user unit nn-shared-database-service.service, beside
this file, runs it. Callers never see the tables: they send named operations.

EVERY REQUEST carries `Authorization: Bearer <token>`. A token that is no line
of the accepted-tokens file is answered 401.

  POST /events             store one event; the body is a JSON object with
                           exactly the keys event_id, machine, operation,
                           occurred_at, seat_id (null for machine-booted) and
                           fields, an object with exactly the operation's fields
                           in OPERATION_FIELDS
  GET /agent-seats         list agent-seats; ?machine=mac or ?machine=ned-box
                           lists one machine's
  GET /agent-seats/<id>    one agent-seat, with its handoff-supervisor runs,
                           agent-sessions, session-handoffs and restart attempts
  POST /findings-record-rows/search
                           read only: the body is a JSON object with exactly
                           finding_id and finding_text, text, and path and
                           line_text, text or null; answers {"held": the row a
                           sighting of finding_id is on, or null, "candidates":
                           the FINDINGS_RECORD_ROW_SEARCH_CANDIDATES rows whose
                           finding_text FTS5 ranks best by bm25() for any word of
                           finding_text, best first, "same_line_record_ids": the
                           rows with this path and line_text}; 422 for another body

POST /events answers:
  200  {"sequence": N, ...}: stored now, or, for an event ID already held, the
       sequence number it was stored under
  400  the body is not a JSON object, or has no event ID, or an event ID that
       is not a string SQLite can store
  422  an unknown machine; an occurred_at or seat_id that is not a string
       SQLite can store or null, or a field that is not a string SQLite can
       store, a number SQLite can store, true, false or null, where NaN and
       infinity, which the body may hold as NaN, Infinity or a number too large
       for a float, are numbers SQLite cannot store, and a string holding a
       lone surrogate, which the body may hold as \\udc80, is a string SQLite
       cannot store; a seat ID with no agent-seat row; an agent-seat name
       another agent-seat not retired holds; an unknown operation; keys or
       fields other than the operation's; or a seat_id on an operation that
       names no agent-seat, or none on one that does
  500  any other error, as {"error": "<its type>: <its message>"}; nothing is
       stored

The findings record holds one findings_record_row row per defect, never deleted, since no
operation deletes one. A findings-record-row-added event makes a row in state new, with the
event's sequence number as its record_id, and a sighting of its finding_id; a
findings-record-row-sighted event records one more finding as a sighting of a row, once per
finding_id and head_commit; a findings-record-row-decided event sets a row's state, one of
FINDINGS_RECORD_ROW_STATES, and its decision, and its filed_where and owning_agent_seat
unless null. None of the three names an agent-seat.

An agent-seat's state is its events applied in sequence-number order, as each
is stored. An agent-seat stops being parked at its next handoff-supervisor-began,
agent-seat-paused or agent-seat-retired event, and stops being paused at its next
handoff-supervisor-began or agent-seat-retired event; when either state stops,
its column, parked_at or paused_at, is set to null.

Exit codes: 2 a bad invocation; otherwise the program runs until stopped.
"""

import argparse
import json
import math
import os
import re
import sqlite3
import sys
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

NN_SHARED_DATABASE_FILE_PATH = Path.home() / ".local" / "state" / "nedsnodes" / "nn-shared-database.sqlite3"
ACCEPTED_TOKENS_FILE_PATH = (Path.home() / ".config" / "nedsnodes"
                             / "nn-shared-database-service-accepted-tokens")
PORT = 8765
MACHINES = ("mac", "ned-box")
BUSY_TIMEOUT_SECONDS = 5

EVENT_KEYS = {"event_id", "machine", "operation", "occurred_at", "seat_id", "fields"}
OPERATION_FIELDS = {
    "agent-seat-created": {"seat_name", "seat_directory", "task_list_name"},
    "agent-seat-seen": {"seat_name", "seat_directory", "task_list_name"},
    "agent-seat-paused": set(),
    "agent-seat-parked": set(),
    "agent-seat-retired": set(),
    "machine-booted": {"boot_id", "booted_at", "previous_boot", "stop_estimated_at",
                       "stop_estimate_method"},
    "handoff-supervisor-began": {"run_id", "boot_id", "process_id", "process_started_at",
                                 "generation", "restart_attempt_id"},
    "handoff-supervisor-ended": {"run_id"},
    "agent-session-launched": {"session_id", "run_id", "transcript_path", "predecessor_session"},
    "agent-session-ended": {"session_id", "run_id", "exit_code"},
    "session-handoff-written": {"restart_counter", "writer_session", "next_step_text",
                                "dont_restart_reason"},
    "session-handoff-consumed": {"written_event_id", "run_id"},
    "restart-attempted": {"attempt_id", "boot_id", "why_picked", "action", "began_at",
                          "ended_at", "result"},
    "findings-record-row-added": {"finding_id", "pull_request", "head_commit", "path", "line",
                             "line_text", "outside_program", "statement", "finding_text",
                             "main_has_it", "this_pull_request_makes_it_happen",
                             "reports_success_on_failure", "shown_by", "grade", "decision",
                             "filed_where", "owning_agent_seat"},
    "findings-record-row-sighted": {"record_id", "finding_id", "pull_request", "head_commit"},
    "findings-record-row-decided": {"record_id", "state", "decision", "filed_where",
                               "owning_agent_seat"},
}
FINDINGS_RECORD_ROW_STATES = ("new", "filed", "decided-fix", "decided-not-worth-fixing", "needs-user",
                         "fixed")
FINDINGS_RECORD_ROW_SEARCH_CANDIDATES = 3
OPERATIONS_THAT_NAME_NO_AGENT_SEAT = {"machine-booted", "findings-record-row-added",
                                      "findings-record-row-sighted", "findings-record-row-decided"}
OPERATIONS_THAT_MAY_NAME_A_NEW_AGENT_SEAT = {"agent-seat-created", "agent-seat-seen"}

SCHEMA = """
CREATE TABLE IF NOT EXISTS event (
    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id TEXT NOT NULL UNIQUE,
    machine TEXT NOT NULL,
    operation TEXT NOT NULL,
    occurred_at TEXT,
    received_at TEXT NOT NULL,
    body TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS agent_seat (
    seat_id TEXT PRIMARY KEY,
    machine TEXT NOT NULL,
    seat_name TEXT NOT NULL,
    seat_directory TEXT,
    task_list_name TEXT,
    created_at TEXT,
    paused_at TEXT,
    parked_at TEXT,
    retired_at TEXT);
CREATE UNIQUE INDEX IF NOT EXISTS agent_seat_name_among_not_retired ON agent_seat (seat_name)
    WHERE retired_at IS NULL;
CREATE TABLE IF NOT EXISTS supervisor_run (
    run_id TEXT PRIMARY KEY,
    seat_id TEXT NOT NULL,
    boot_id TEXT,
    process_id INTEGER,
    process_started_at TEXT,
    generation INTEGER,
    began_at TEXT,
    ended_at TEXT,
    restart_attempt_id TEXT);
CREATE TABLE IF NOT EXISTS agent_session (
    machine TEXT NOT NULL,
    session_id TEXT NOT NULL,
    run_id TEXT NOT NULL,
    seat_id TEXT NOT NULL,
    transcript_path TEXT,
    predecessor_session TEXT,
    launched_at TEXT,
    ended_at TEXT,
    exit_code INTEGER,
    PRIMARY KEY (machine, session_id, run_id));
CREATE TABLE IF NOT EXISTS handoff_event (
    event_id TEXT PRIMARY KEY,
    seat_id TEXT NOT NULL,
    restart_counter INTEGER,
    writer_session TEXT,
    written_at TEXT,
    next_step_text TEXT,
    dont_restart_reason TEXT,
    consumed_by_run TEXT,
    consumed_at TEXT);
CREATE TABLE IF NOT EXISTS machine_boot (
    machine TEXT NOT NULL,
    boot_id TEXT NOT NULL,
    booted_at TEXT,
    previous_boot TEXT,
    stop_estimated_at TEXT,
    stop_estimate_method TEXT,
    PRIMARY KEY (machine, boot_id));
CREATE TABLE IF NOT EXISTS restart_attempt (
    attempt_id TEXT PRIMARY KEY,
    machine TEXT NOT NULL,
    boot_id TEXT,
    seat_id TEXT NOT NULL,
    why_picked TEXT,
    action TEXT,
    began_at TEXT,
    ended_at TEXT,
    result TEXT);
CREATE TABLE IF NOT EXISTS findings_record_row (
    record_id INTEGER PRIMARY KEY,
    added_from_finding_id TEXT NOT NULL,
    path TEXT,
    line INTEGER,
    line_text TEXT,
    line_commit TEXT,
    outside_program TEXT,
    statement TEXT NOT NULL,
    finding_text TEXT NOT NULL,
    main_has_it TEXT,
    this_pull_request_makes_it_happen TEXT,
    reports_success_on_failure TEXT,
    shown_by TEXT,
    grade TEXT,
    filed_where TEXT,
    owning_agent_seat TEXT,
    state TEXT NOT NULL,
    decision TEXT,
    added_at TEXT,
    decided_at TEXT);
CREATE TABLE IF NOT EXISTS findings_record_row_sighting (
    finding_id TEXT NOT NULL,
    head_commit TEXT NOT NULL,
    record_id INTEGER NOT NULL,
    pull_request INTEGER,
    seen_at TEXT,
    PRIMARY KEY (finding_id, head_commit));
CREATE VIRTUAL TABLE IF NOT EXISTS findings_record_row_text USING fts5(finding_text);
"""


class Answer(Exception):
    def __init__(self, status, body):
        super().__init__(status)
        self.status = status
        self.body = body


def connect(database_path):
    connection = sqlite3.connect(str(database_path), timeout=BUSY_TIMEOUT_SECONDS,
                                 isolation_level=None)
    connection.row_factory = sqlite3.Row
    return connection


def create_nn_shared_database_if_absent(database_path):
    """Create the database file, and each table of SCHEMA it lacks, such as a table added
    after the file was made."""
    database_path = Path(database_path)
    database_path.parent.mkdir(parents=True, exist_ok=True)
    connection = connect(database_path)
    try:
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("BEGIN IMMEDIATE")
        for statement in SCHEMA.split(";"):
            if statement.strip():
                connection.execute(statement)
        connection.execute("COMMIT")
    finally:
        connection.close()


def accepted_tokens(accepted_tokens_path):
    try:
        lines = Path(accepted_tokens_path).read_text(encoding="utf-8").splitlines()
    except OSError:
        return set()
    return {line.strip() for line in lines if line.strip()}


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def parse_event(raw_body):
    try:
        event = json.loads(raw_body)
    except ValueError:
        raise Answer(400, {"error": "the body is not JSON"})
    if not isinstance(event, dict):
        raise Answer(400, {"error": "the body is not a JSON object"})
    if not isinstance(event.get("event_id"), str) or not event["event_id"]:
        raise Answer(400, {"error": "the event has no event_id"})
    if not sqlite_can_store(event["event_id"]):
        raise Answer(400, {"error": "the event's event_id holds a lone surrogate, such as "
                                    "\\udc80, which does not encode to UTF-8, so SQLite "
                                    "cannot store it"})
    return event


def sqlite_can_store(value):
    if isinstance(value, int) and not isinstance(value, bool):
        return -2 ** 63 <= value < 2 ** 63
    if isinstance(value, float):
        return math.isfinite(value)
    if isinstance(value, str):
        # sqlite3 binds a str by encoding it to UTF-8, which fails on a lone surrogate.
        try:
            value.encode("utf-8")
        except UnicodeEncodeError:
            return False
        return True
    return value is None or isinstance(value, bool)


def check_event_fits_its_operation(connection, event):
    if event.get("machine") not in MACHINES:
        raise Answer(422, {"error": f"unknown machine {event.get('machine')!r}"})
    operation = event.get("operation")
    if operation not in OPERATION_FIELDS:
        raise Answer(422, {"error": f"unknown operation {operation!r}"})
    fields = event.get("fields")
    if set(event) != EVENT_KEYS or not isinstance(fields, dict) \
            or set(fields) != OPERATION_FIELDS[operation]:
        raise Answer(422, {"error": f"the keys or fields differ from {operation}'s: event keys "
                                    f"{sorted(EVENT_KEYS)}, fields "
                                    f"{sorted(OPERATION_FIELDS[operation])}"})
    wrong = [key for key in ("occurred_at", "seat_id")
             if not (event[key] is None
                     or isinstance(event[key], str) and sqlite_can_store(event[key]))]
    wrong += [f"fields.{name}" for name, value in sorted(fields.items())
              if not sqlite_can_store(value)]
    if wrong:
        raise Answer(422, {"error": f"nn-shared-database-service.py did not store event "
                                    f"{event['event_id']} ({operation}, from {event['machine']}): "
                                    f"each of these holds a value it cannot store: "
                                    f"{', '.join(wrong)}. A name fields.<name> is the field "
                                    f"<name> inside the event's fields object. These rules give "
                                    f"the JSON type only: occurred_at and seat_id are each a "
                                    f"string or null, and each value in the fields object is a "
                                    f"string, an integer from -2**63 to 2**63-1, a finite number "
                                    f"with a decimal point, true, false or null, never NaN, "
                                    f"Infinity, a list or an object; no string holds a lone "
                                    f"surrogate, such as \\udc80, which does not encode to "
                                    f"UTF-8. These operations alone take a null seat_id: "
                                    f"{', '.join(sorted(OPERATIONS_THAT_NAME_NO_AGENT_SEAT))}; "
                                    f"every other operation takes a string. "
                                    f"Correct the program that sent it."})
    names_no_seat = operation in OPERATIONS_THAT_NAME_NO_AGENT_SEAT
    if names_no_seat != (event["seat_id"] is None):
        raise Answer(422, {"error": f"{operation} takes "
                                    f"{'no' if names_no_seat else 'a'} seat_id"})
    if not names_no_seat and operation not in OPERATIONS_THAT_MAY_NAME_A_NEW_AGENT_SEAT \
            and connection.execute("SELECT 1 FROM agent_seat WHERE seat_id = ?",
                                   (event["seat_id"],)).fetchone() is None:
        raise Answer(422, {"error": f"no agent-seat has seat_id {event['seat_id']!r}"})
    if operation == "findings-record-row-decided" and fields["state"] not in FINDINGS_RECORD_ROW_STATES:
        raise Answer(422, {"error": f"the state {fields['state']!r} is not one of "
                                    f"{', '.join(FINDINGS_RECORD_ROW_STATES)}"})
    if operation in ("findings-record-row-sighted", "findings-record-row-decided") \
            and connection.execute("SELECT 1 FROM findings_record_row WHERE record_id = ?",
                                   (fields["record_id"],)).fetchone() is None:
        raise Answer(422, {"error": f"no findings record row has record_id "
                                    f"{fields['record_id']!r}"})
    if operation == "findings-record-row-added" and not (
            isinstance(fields["finding_id"], str) and isinstance(fields["head_commit"], str)
            and isinstance(fields["statement"], str) and isinstance(fields["finding_text"], str)
            and (isinstance(fields["path"], str) or isinstance(fields["outside_program"], str))):
        raise Answer(422, {"error": "findings-record-row-added takes a text finding_id, head_commit, "
                                    "statement and finding_text, and a text path or "
                                    "outside_program"})
    if operation == "findings-record-row-added":
        sighted = connection.execute(
            "SELECT record_id FROM findings_record_row_sighting WHERE finding_id = ? AND head_commit = ?",
            (fields["finding_id"], fields["head_commit"])).fetchone()
        if sighted is not None:
            raise Answer(422, {"error": f"finding {fields['finding_id']!r} at commit "
                                        f"{fields['head_commit']!r} is already a sighting of "
                                        f"findings record row {sighted[0]}, so it is not added "
                                        "as a new row"})


def apply_event(connection, event, sequence):
    """Bring the state tables up to date with one event, in the caller's transaction; a
    findings-record-row-added event's sequence number becomes its row's record_id."""
    operation, seat_id, fields = event["operation"], event["seat_id"], event["fields"]
    at, machine = event["occurred_at"], event["machine"]
    execute = connection.execute
    if operation == "findings-record-row-added":
        execute("INSERT INTO findings_record_row (record_id, added_from_finding_id, path, line, "
                "line_text, line_commit, outside_program, statement, finding_text, main_has_it, "
                "this_pull_request_makes_it_happen, reports_success_on_failure, shown_by, grade, "
                "filed_where, owning_agent_seat, state, decision, added_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'new', ?, ?)",
                (sequence, fields["finding_id"], fields["path"], fields["line"],
                 fields["line_text"], fields["head_commit"], fields["outside_program"],
                 fields["statement"], fields["finding_text"], fields["main_has_it"],
                 fields["this_pull_request_makes_it_happen"],
                 fields["reports_success_on_failure"], fields["shown_by"], fields["grade"],
                 fields["filed_where"], fields["owning_agent_seat"], fields["decision"], at))
        execute("INSERT INTO findings_record_row_text (rowid, finding_text) VALUES (?, ?)",
                (sequence, fields["finding_text"]))
        execute("INSERT OR IGNORE INTO findings_record_row_sighting VALUES (?, ?, ?, ?, ?)",
                (fields["finding_id"], fields["head_commit"], sequence, fields["pull_request"], at))
    elif operation == "findings-record-row-sighted":
        execute("INSERT OR IGNORE INTO findings_record_row_sighting VALUES (?, ?, ?, ?, ?)",
                (fields["finding_id"], fields["head_commit"], fields["record_id"],
                 fields["pull_request"], at))
    elif operation == "findings-record-row-decided":
        execute("UPDATE findings_record_row SET state = ?, decision = ?, "
                "filed_where = coalesce(?, filed_where), "
                "owning_agent_seat = coalesce(?, owning_agent_seat), decided_at = ? "
                "WHERE record_id = ?",
                (fields["state"], fields["decision"], fields["filed_where"],
                 fields["owning_agent_seat"], at, fields["record_id"]))
    elif operation in ("agent-seat-created", "agent-seat-seen"):
        execute("INSERT INTO agent_seat (seat_id, machine, seat_name, seat_directory, "
                "task_list_name, created_at) VALUES (?, ?, ?, ?, ?, ?) "
                "ON CONFLICT (seat_id) DO UPDATE SET machine = excluded.machine, "
                "seat_name = excluded.seat_name, seat_directory = excluded.seat_directory, "
                "task_list_name = excluded.task_list_name, "
                "created_at = coalesce(excluded.created_at, created_at)",
                (seat_id, machine, fields["seat_name"], fields["seat_directory"],
                 fields["task_list_name"], at if operation == "agent-seat-created" else None))
    elif operation == "agent-seat-paused":
        execute("UPDATE agent_seat SET paused_at = ?, parked_at = NULL WHERE seat_id = ?",
                (at, seat_id))
    elif operation == "agent-seat-parked":
        execute("UPDATE agent_seat SET parked_at = ? WHERE seat_id = ?", (at, seat_id))
    elif operation == "agent-seat-retired":
        execute("UPDATE agent_seat SET retired_at = ?, paused_at = NULL, parked_at = NULL "
                "WHERE seat_id = ?", (at, seat_id))
    elif operation == "machine-booted":
        execute("INSERT OR REPLACE INTO machine_boot VALUES (?, ?, ?, ?, ?, ?)",
                (machine, fields["boot_id"], fields["booted_at"], fields["previous_boot"],
                 fields["stop_estimated_at"], fields["stop_estimate_method"]))
    elif operation == "handoff-supervisor-began":
        execute("INSERT INTO supervisor_run (run_id, seat_id, boot_id, process_id, "
                "process_started_at, generation, began_at, restart_attempt_id) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?) ON CONFLICT (run_id) DO UPDATE SET "
                "boot_id = excluded.boot_id, process_id = excluded.process_id, "
                "process_started_at = excluded.process_started_at, "
                "generation = excluded.generation, began_at = excluded.began_at, "
                "restart_attempt_id = excluded.restart_attempt_id",
                (fields["run_id"], seat_id, fields["boot_id"], fields["process_id"],
                 fields["process_started_at"], fields["generation"], at,
                 fields["restart_attempt_id"]))
        execute("UPDATE agent_seat SET paused_at = NULL, parked_at = NULL WHERE seat_id = ?",
                (seat_id,))
    elif operation == "handoff-supervisor-ended":
        execute("INSERT INTO supervisor_run (run_id, seat_id, ended_at) VALUES (?, ?, ?) "
                "ON CONFLICT (run_id) DO UPDATE SET ended_at = excluded.ended_at",
                (fields["run_id"], seat_id, at))
    elif operation == "agent-session-launched":
        execute("INSERT INTO agent_session (machine, session_id, run_id, seat_id, "
                "transcript_path, predecessor_session, launched_at) VALUES (?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT (machine, session_id, run_id) DO UPDATE SET "
                "transcript_path = excluded.transcript_path, "
                "predecessor_session = excluded.predecessor_session, "
                "launched_at = excluded.launched_at",
                (machine, fields["session_id"], fields["run_id"], seat_id,
                 fields["transcript_path"], fields["predecessor_session"], at))
    elif operation == "agent-session-ended":
        execute("INSERT INTO agent_session (machine, session_id, run_id, seat_id, ended_at, "
                "exit_code) VALUES (?, ?, ?, ?, ?, ?) "
                "ON CONFLICT (machine, session_id, run_id) DO UPDATE SET "
                "ended_at = excluded.ended_at, exit_code = excluded.exit_code",
                (machine, fields["session_id"], fields["run_id"], seat_id, at,
                 fields["exit_code"]))
    elif operation == "session-handoff-written":
        execute("INSERT INTO handoff_event (event_id, seat_id, restart_counter, writer_session, "
                "written_at, next_step_text, dont_restart_reason) VALUES (?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT (event_id) DO UPDATE SET "
                "restart_counter = excluded.restart_counter, "
                "writer_session = excluded.writer_session, written_at = excluded.written_at, "
                "next_step_text = excluded.next_step_text, "
                "dont_restart_reason = excluded.dont_restart_reason",
                (event["event_id"], seat_id, fields["restart_counter"], fields["writer_session"],
                 at, fields["next_step_text"], fields["dont_restart_reason"]))
    elif operation == "session-handoff-consumed":
        execute("INSERT INTO handoff_event (event_id, seat_id, consumed_by_run, consumed_at) "
                "VALUES (?, ?, ?, ?) ON CONFLICT (event_id) DO UPDATE SET "
                "consumed_by_run = excluded.consumed_by_run, consumed_at = excluded.consumed_at",
                (fields["written_event_id"], seat_id, fields["run_id"], at))
    elif operation == "restart-attempted":
        execute("INSERT OR REPLACE INTO restart_attempt VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (fields["attempt_id"], machine, fields["boot_id"], seat_id, fields["why_picked"],
                 fields["action"], fields["began_at"], fields["ended_at"], fields["result"]))


def store_event(connection, raw_body):
    """Store one event; an answer raised here leaves the transaction open, and the
    request's connection, closed by its caller, rolls it back."""
    event = parse_event(raw_body)
    connection.execute("BEGIN IMMEDIATE")
    held = connection.execute("SELECT sequence FROM event WHERE event_id = ?",
                              (event["event_id"],)).fetchone()
    if held is not None:
        connection.execute("ROLLBACK")
        return {"sequence": held[0]}  # pragma: no mutate, the query selects the sequence alone, so [-1] is the same column
    check_event_fits_its_operation(connection, event)
    sequence = connection.execute(
        "INSERT INTO event (event_id, machine, operation, occurred_at, received_at, body) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (event["event_id"], event["machine"], event["operation"], event["occurred_at"],
         utc_now(), json.dumps(event, sort_keys=True))).lastrowid
    try:
        apply_event(connection, event, sequence)
    except sqlite3.IntegrityError:
        raise Answer(422, {"error": "another agent-seat not retired holds the name "
                                    f"{event['fields'].get('seat_name')!r}"})
    connection.execute("COMMIT")
    return {"sequence": sequence}


def rows(connection, query, parameters):
    return [dict(row) for row in connection.execute(query, parameters)]


def list_agent_seats(connection, query_string):
    machines = parse_qs(query_string).get("machine")
    if machines:
        seats = rows(connection, "SELECT * FROM agent_seat WHERE machine = ? ORDER BY seat_name",
                     (machines[0],))
    else:
        seats = rows(connection, "SELECT * FROM agent_seat ORDER BY seat_name", ())
    return {"agent_seats": seats}


def get_agent_seat(connection, seat_id):
    seat = rows(connection, "SELECT * FROM agent_seat WHERE seat_id = ?", (seat_id,))
    if not seat:
        raise Answer(404, {"error": f"no agent-seat has seat_id {seat_id!r}"})
    return {
        "agent_seat": seat[0],
        "supervisor_runs": rows(connection, "SELECT * FROM supervisor_run WHERE seat_id = ? "
                                            "ORDER BY began_at", (seat_id,)),
        "agent_sessions": rows(connection, "SELECT * FROM agent_session WHERE seat_id = ? "
                                           "ORDER BY launched_at", (seat_id,)),
        "session_handoffs": rows(connection, "SELECT * FROM handoff_event WHERE seat_id = ? "
                                             "ORDER BY written_at", (seat_id,)),
        "restart_attempts": rows(connection, "SELECT * FROM restart_attempt WHERE seat_id = ? "
                                             "ORDER BY began_at", (seat_id,))}


def findings_record_rows_search(connection, raw_body):
    """The findings record rows a new finding may repeat; see the module docstring."""
    try:
        request = json.loads(raw_body)
    except ValueError:
        raise Answer(400, {"error": "the body is not JSON"})
    if not (isinstance(request, dict)
            and set(request) == {"finding_id", "finding_text", "path", "line_text"}
            and isinstance(request["finding_id"], str) and isinstance(request["finding_text"], str)
            and all(request[key] is None or isinstance(request[key], str)
                    for key in ("path", "line_text"))
            and all(sqlite_can_store(value) for value in request.values())):
        raise Answer(422, {"error": "the search takes a JSON object with exactly a text "
                                    "finding_id and finding_text, and a text or null path and "
                                    "line_text"})
    held = rows(connection, "SELECT findings_record_row.* FROM findings_record_row_sighting JOIN "
                            "findings_record_row USING (record_id) WHERE finding_id = ? "
                            "ORDER BY seen_at LIMIT 1", (request["finding_id"],))
    # Each word is quoted, since FTS5 reads a bare word such as NOT, or a colon, as its syntax,
    # and the words are joined by OR, since FTS5 otherwise asks for every one of them.
    words = sorted(set(re.findall(r"\w+", request["finding_text"].lower())))
    candidates = rows(connection, "SELECT findings_record_row.* FROM findings_record_row_text JOIN "
                                  "findings_record_row ON findings_record_row.record_id = "
                                  "findings_record_row_text.rowid WHERE findings_record_row_text MATCH ? "
                                  "ORDER BY bm25(findings_record_row_text) LIMIT ?",
                      (" OR ".join(f'"{word}"' for word in words),
                       FINDINGS_RECORD_ROW_SEARCH_CANDIDATES)) if words else []
    same_line = [row["record_id"] for row in rows(
        connection, "SELECT record_id FROM findings_record_row WHERE path = ? AND line_text = ? "
                    "ORDER BY record_id", (request["path"], request["line_text"]))] \
        if request["path"] and request["line_text"] and request["line_text"].strip() else []
    return {"held": held[0] if held else None, "candidates": candidates,
            "same_line_record_ids": same_line}


def make_request_handler(database_path, accepted_tokens_path):
    class RequestHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.answer_request(None)

        def do_POST(self):
            length = int(self.headers.get("Content-Length") or 0)
            self.answer_request(self.rfile.read(length))

        def answer_request(self, raw_body):
            connection = connect(database_path)
            try:
                status, body = 200, self.route(connection, raw_body)
            except Answer as answer:
                status, body = answer.status, answer.body
            except Exception as error:
                status, body = 500, {"error": f"{type(error).__name__}: {error}"}
            finally:
                connection.close()
            encoded = json.dumps(body).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def route(self, connection, raw_body):
            scheme, _, token = (self.headers.get("Authorization") or "").partition(" ")
            if scheme != "Bearer" or token.strip() not in accepted_tokens(accepted_tokens_path):
                raise Answer(401, {"error": "no accepted token: send `Authorization: Bearer "
                                            "<token>` with a line of the service's "
                                            "accepted-tokens file"})
            path = urlsplit(self.path)
            if raw_body is not None and path.path == "/events":
                return store_event(connection, raw_body)
            if raw_body is not None and path.path == "/findings-record-rows/search":
                return findings_record_rows_search(connection, raw_body)
            if raw_body is None and path.path == "/agent-seats":
                return list_agent_seats(connection, path.query)
            if raw_body is None and path.path.startswith("/agent-seats/"):
                return get_agent_seat(connection, path.path[len("/agent-seats/"):])
            raise Answer(404, {"error": f"no operation at {self.command} {path.path}"})

    return RequestHandler


def make_nn_shared_database_service_http_server(database_path, accepted_tokens_path, host, port):
    create_nn_shared_database_if_absent(database_path)
    return ThreadingHTTPServer((host, port),
                               make_request_handler(database_path, accepted_tokens_path))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--database", default=str(NN_SHARED_DATABASE_FILE_PATH))
    parser.add_argument("--accepted-tokens-file", default=str(ACCEPTED_TOKENS_FILE_PATH))
    parser.add_argument("--host", default="")
    parser.add_argument("--port", type=int, default=PORT)
    arguments = parser.parse_args(argv)
    # Only nedlern may read or write the database, its WAL files included.
    os.umask(0o077)
    server = make_nn_shared_database_service_http_server(arguments.database, arguments.accepted_tokens_file,
                         arguments.host, arguments.port)
    server.serve_forever()


if __name__ == "__main__":
    sys.exit(main())
