#!/usr/bin/env python3
"""Regression test: the findings record search ranks the earlier finding first for real repeated findings.

The fixture beside this file holds Codex findings from merge-lane-2's Codex reviews: four
earlier findings, seven later findings that repeat one of them on another pull request,
two on lines that had moved, and 300 findings of other defects raised before them as
distractors. Each earlier finding is also asked in a Claude reviewer's wording, written
for this test. The test loads every earlier finding and distractor into a new
nn-shared-database as findings record rows, through the service's own event code, and
runs the service's search for each later finding: the earlier finding it repeats must be
the first candidate. The judgment step that then answers SAME or NEW is not run here; it
is what tells a different defect on the same lines, which the search can also rank
first, from a repeat.

Run: python3 scripts/findings-record-codex-finding-match-and-row-add-or-decide-repeat-findings-regression-test.py
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
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIXTURE = HERE / "findings-record-codex-finding-match-and-row-add-or-decide-repeat-findings-regression-test-fixture.json"
spec = importlib.util.spec_from_file_location(
    "nn_shared_database_service", HERE.parent / "nn-systems" / "nn-shared-database" / "nn-shared-database-service.py")
service = importlib.util.module_from_spec(spec)
spec.loader.exec_module(service)

CLAUDE_REVIEWER_WORDINGS = {
    "capture-3957": (
        "`delete_old_captures()` decides which files to keep by sorting everything in the agent-seat's capture "
        "directory, not only the terminal captures. A stray file that sorts last takes the newest capture's "
        "protected place, so a capture tmux still writes to can be unlinked once it is a week old, and unrelated "
        "old files are deleted with it. Match the capture filename pattern first, then sort and prune.\n"
        "Main has it: yes\nThis pull request makes it happen: no\nReports success on failure: no\n"
        "Shown by: judged from the code only"),
    "transcripts-4001": (
        "The sandbox bind list in `run-all-test-suites.py` mounts the whole real `~/.claude/projects` directory "
        "read-only into every suite's sandbox. Read-only still lets any suite, one from a pull request included, "
        "read private Claude transcripts and print them into a kept test log. Give the transcript reader test "
        "synthetic fixture transcripts and keep the real directory out of the sandbox.\n"
        "Main has it: yes\nThis pull request makes it happen: no\nReports success on failure: no\n"
        "Shown by: judged from the code only"),
    "settlement-4471": (
        "When the advisor objects after `check --not-asked` recorded a settlement, the read path already sends "
        "the item back to be presented, but the row list still offers the same `check --not-asked` command, so "
        "an agent following the rows records a second provisional settlement. The row generator should reuse the "
        "unclosed settlement decision.\n"
        "Main has it: yes\nThis pull request makes it happen: no\nReports success on failure: no\n"
        "Shown by: judged from the code only"),
    "guard-4161": (
        "`instruction-file-guard.py` keeps its own suffix check, so it still treats the GHI-MD for GHI 4080 as a "
        "reusable prompt and refuses an ordinary edit without `.walk-approved`. Moving the guard onto the shared "
        "classifier waits for approval; until then the pull request should carry a `#root_cause_not_fixed` line "
        "linking that follow-up.\n"
        "Main has it: yes\nThis pull request makes it happen: no\nReports success on failure: no\n"
        "Shown by: judged from the code only"),
}

failures = []


def check(name, condition, detail=""):
    print(("PASS  " if condition else "FAIL  ") + name)
    if not condition:
        failures.append(name)
        print("      " + str(detail))


fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
with tempfile.TemporaryDirectory() as scratch:
    database = Path(scratch) / "nn-shared-database.sqlite3"
    service.create_nn_shared_database_if_absent(database)
    connection = service.connect(database)
    record_ids = {}

    def add(key, text):
        heading = text.splitlines()[0]
        cited = re.search(r" — (\S+?):(\d+)", heading)
        event = {"event_id": f"add-{key}", "machine": "ned-box", "operation": "findings-record-row-added",
                 "occurred_at": None, "seat_id": None, "fields": {
                     "finding_id": key, "pull_request": None, "head_commit": "fixture",
                     "path": cited[1] if cited else "unknown", "line": int(cited[2]) if cited else None,
                     "line_text": None, "outside_program": None, "statement": heading, "finding_text": text,
                     "main_has_it": "yes", "this_pull_request_makes_it_happen": "no",
                     "reports_success_on_failure": None, "shown_by": None, "grade": None, "decision": None,
                     "filed_where": None, "owning_agent_seat": None}}
        return service.store_event(connection, json.dumps(event))["sequence"]

    for index, text in enumerate(fixture["distractor_findings"]):
        add(f"distractor-{index}", text)
    for key, text in fixture["earlier_findings"].items():
        record_ids[key] = add(key, text)

    def ranked(text):
        answer = service.findings_record_rows_search(connection, json.dumps(
            {"finding_id": "query", "finding_text": text, "path": None, "line_text": None}))
        return [row["record_id"] for row in answer["candidates"]]

    rows = len(fixture["distractor_findings"]) + len(record_ids)
    for repeat in fixture["repeat_findings"]:
        heading = repeat["text"].splitlines()[0]
        got = ranked(repeat["text"])
        check(f"{repeat['pull_request']}'s repeat of {repeat['repeats']} ranks the earlier finding first among "
              f"{rows} rows: {heading[:80]}", got[:1] == [record_ids[repeat["repeats"]]], got)
    for key, text in CLAUDE_REVIEWER_WORDINGS.items():
        got = ranked(text)
        check(f"a Claude reviewer's wording of {key} ranks the earlier finding first", got[:1] == [record_ids[key]],
              got)
    connection.close()

print(f"{len(failures)} failure(s)")
sys.exit(1 if failures else 0)
