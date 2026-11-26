#!/usr/bin/env python3
"""Cases for the weekly program that has Opus relabel a sample of the question-check Stop hook's line verdicts and
writes a user-alert only when a threshold is crossed.

The program runs in this process, with HOME, and so the user-alerts folder, in a scratch directory, and the
line-verdict log, the answer key's labelling prompt and the counts directory in a scratch log-store. The labeller is
never real: a fake `claude` first on PATH records each call and labels a line an ask when its text holds
LABELLER_ASK, fails its call as logged out when the text holds LABELLER_FAIL and with another error when it holds
LABELLER_OTHER_FAIL, and labels it no ask otherwise.
"""

import importlib.util
import pathlib

_start_and_end_lines_spec = importlib.util.spec_from_file_location(
    "nn_test_suite_start_time_line_and_end_results_line_print_common",
    pathlib.Path(__file__).resolve().parents[4] / "nn-systems/general-tools/nn-test-suite-start-time-line-and-end-results-line-print-common.py")
_start_and_end_lines = importlib.util.module_from_spec(_start_and_end_lines_spec)
_start_and_end_lines_spec.loader.exec_module(_start_and_end_lines)
_start_and_end_lines.nn_test_suite_start_time_line_print_now_and_end_results_line_print_at_normal_exit_register()
import datetime
import importlib.util
import json
import os
import random
import shutil
import sys
import tempfile
from pathlib import Path

PROGRAM = (Path(__file__).resolve().parents[1]
           / "walk-me-through-agent-question-to-user-outside-approval-walk-items-refusal-stop-hook-mistakes-weekly-opus-audit-and-user-alert.py")
_specification = importlib.util.spec_from_file_location("weekly_relabel", PROGRAM)
job = importlib.util.module_from_spec(_specification)
_specification.loader.exec_module(job)

SUITE_ROOT = Path(tempfile.mkdtemp(prefix="question-check-weekly-relabel-test-")).resolve()
FAKE_BIN = SUITE_ROOT / "bin"
LABELLER_ASK, LABELLER_FAIL, LABELLER_OTHER_FAIL = "[labeller-ask]", "[labeller-fail]", "[labeller-other-fail]"
NOW = datetime.datetime(2026, 11, 30, 6, 15, tzinfo=datetime.timezone.utc)
PROMPT_TEXT = "The answer key's labelling prompt.\nThe lines, as JSON:\n"
failures = []

FAKE_CLAUDE = """#!/usr/bin/env python3
import json, os, sys
prompt = sys.stdin.read()
with open(os.environ["FAKE_CLAUDE_CALLS"], "a") as calls:
    calls.write(json.dumps({"argv": sys.argv[1:], "stdin": prompt}) + "\\n")
entry = json.loads(prompt.split("The lines, as JSON:\\n", 1)[1])[0]
if "LABELLER_OTHER_FAIL" in entry["line"]:
    print(json.dumps({"type": "result", "is_error": True, "result": "API overloaded"}))
    sys.exit(1)
if "LABELLER_FAIL" in entry["line"]:
    print(json.dumps({"type": "result", "is_error": True, "result": "Not logged in"}))
    sys.exit(1)
ask = "LABELLER_ASK" in entry["line"]
print(json.dumps({"type": "result", "is_error": False,
                  "structured_output": {"labels": [{"id": entry["id"], "ask": ask, "reason": "the fake's reason"}]}}))
""".replace("LABELLER_OTHER_FAIL", LABELLER_OTHER_FAIL).replace("LABELLER_FAIL", LABELLER_FAIL).replace(
    "LABELLER_ASK", LABELLER_ASK)


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


def row(line, ask, days_ago=1, session="s1", **fields):
    return {"time": (NOW - datetime.timedelta(days=days_ago)).isoformat(timespec="seconds"), "session": session,
            "walk": "a-walk", "model": "claude-haiku-5-5", "id": "L1", "line": line, "turn_started_by": "human",
            "message_that_started_the_turn": "A", "agent_message_holding_the_line": f"Before. {line} After.",
            "waiting_walk_item_text": "## Item 2 of 10", "ask": ask, "reason": "haiku's reason",
            "failure": None if ask is not None else "claude exited 1", **fields}


class Case:
    counter = 0

    def __init__(self, rows=(), extra_text="", prompt=True):
        Case.counter += 1
        self.root = SUITE_ROOT / f"case-{Case.counter}"
        self.home = self.root / "home"
        self.home.mkdir(parents=True)
        self.log_store = self.root / "nedsnodes-logs"
        self.log_store.mkdir()
        self.log = self.log_store / "line-verdicts.jsonl"
        self.log.write_text("".join(json.dumps(r) + "\n" for r in rows) + extra_text)
        if prompt:
            prompt_file = self.log_store / job.ANSWER_KEY_LABELLING_PROMPT_RELATIVE_TO_LOG_STORE
            prompt_file.parent.mkdir(parents=True)
            prompt_file.write_text(PROMPT_TEXT)
        self.calls = self.root / "calls.jsonl"
        self.stderr = ""

    def run(self):
        environment = {job.hook.REPLY_LINE_MODEL_ASK_OR_NOT_LABEL_LOG_PATH_VARIABLE: str(self.log)}
        saved = {name: os.environ.get(name) for name in ("HOME", "PATH", "FAKE_CLAUDE_CALLS")}
        os.environ.update({"HOME": str(self.home), "PATH": f"{FAKE_BIN}{os.pathsep}{saved['PATH']}",
                           "FAKE_CLAUDE_CALLS": str(self.calls)})
        stderr_file = self.root / "stderr.txt"
        saved_stderr = sys.stderr
        try:
            with open(stderr_file, "w") as sys.stderr:
                status = job.main(["--now", NOW.isoformat()], environment=environment, rng=random.Random(7))
        finally:
            sys.stderr = saved_stderr
            for name, value in saved.items():
                if value is None:
                    os.environ.pop(name, None)
                else:
                    os.environ[name] = value
        self.stderr = stderr_file.read_text()
        return status

    def model_calls(self):
        return [json.loads(line) for line in self.calls.read_text().splitlines()] if self.calls.exists() else []

    def alerts(self):
        pending = self.home / ".local" / "state" / "nedsnodes" / "user-alerts" / "pending"
        return [json.loads(path.read_text()) for path in sorted(pending.glob("*.json"))] if pending.is_dir() else []

    def record(self):
        records = sorted((self.log_store / job.COUNTS_DIRECTORY_NAME).glob("*.json"))
        return json.loads(records[-1].read_text()) if records else None


def test_a_week_the_hook_judged_as_the_labeller_does_writes_counts_and_no_alert():
    rows = ([row(f"Should I merge {n}? {LABELLER_ASK}", True) for n in range(30)]
            + [row(f"I merged {n}.", False) for n in range(30)])
    case = Case(rows)
    status = case.run()
    calls = case.model_calls()
    check("a clean week exits 0", status == 0, case.stderr)
    check("20 refused and 20 passed lines are labelled, one call each", len(calls) == 40, len(calls))
    record = case.record()
    check("the record holds the counts",
          record["counts"] == {"lines_in_window": 60, "malformed_rows": 0, "refused_labelled": 20, "wrong_stops": 0,
                               "passed_labelled": 20, "missed_asks": 0, "labelling_failed": 0}, record["counts"])
    check("no threshold crossed, no user-alert", case.alerts() == [] and record["user_alert_id"] is None, case.alerts())
    argv = calls[0]["argv"]
    check("the labeller is Opus, sent the hook's schema", argv[argv.index("--model") + 1] == job.LABELLER_MODEL
          and json.loads(argv[argv.index("--json-schema") + 1]) == job.hook.MODEL_SCHEMA, argv)
    entries = [json.loads(call["stdin"].split("The lines, as JSON:\n", 1)[1])[0] for call in calls]
    check("the labeller is sent the answer key's prompt", all(call["stdin"].startswith(PROMPT_TEXT) for call in calls))
    check("the labeller is sent the line's context but never the hook's verdict, under a fresh id",
          all(set(entry) == {"id", *job.ENTRY_FIELDS} for entry in entries)
          and sorted(entry["id"] for entry in entries) == sorted(f"L{n}" for n in range(1, 41)), entries[0])
    asks = [LABELLER_ASK in entry["line"] for entry in entries]
    check("refused and passed lines are shuffled together", asks != sorted(asks) and asks != sorted(asks, reverse=True),
          asks)


def test_which_rows_are_sampled():
    rows = [row("Old? [x]", True, days_ago=8), row("Failed call?", None), row("Twice?", True, session="s2"),
            row("Twice?", False, session="s2", days_ago=0.5), row("Twice?", True, session="s3"),
            dict(row("Missing context?", True), agent_message_holding_the_line=7),
            dict(row("No time zone?", True), time="2026-11-29T06:00:00"), dict(row("No time?", True), time=None),
            dict(row("List session?", True), session=[]), row("No waiting item?", True)]
    rows[-3].pop("time")
    rows[-1].pop("waiting_walk_item_text")
    case = Case(rows, extra_text="not json\n[1, 2]\n")
    case.run()
    lines = sorted((item["row"]["line"], item["row"]["session"], item["row"]["ask"]) for item in case.record()["lines"])
    check("rows older than the week, rows with no verdict and malformed rows are left out; a line judged twice in "
          "one agent-session counts once, with its newest verdict",
          lines == [("Twice?", "s2", False), ("Twice?", "s3", True)], lines)
    check("malformed rows, a row with a time but no time zone, a row with no time, a session that is not a string "
          "and a row missing a field included, are counted",
          case.record()["counts"]["malformed_rows"] == 7, case.record()["counts"])
    empty = Case()
    check("a week with no lines exits 0 and makes no call", empty.run() == 0 and empty.model_calls() == [], empty.stderr)


def test_a_now_without_a_time_zone_is_refused_before_anything_is_read():
    case = Case([row("Ask? [x]", True)])
    saved_stderr = sys.stderr
    try:
        with open(case.root / "stderr.txt", "w") as sys.stderr:
            try:
                job.main(["--now", "2026-11-30T06:15"],
                         environment={job.hook.REPLY_LINE_MODEL_ASK_OR_NOT_LABEL_LOG_PATH_VARIABLE: str(case.log)})
                status = None
            except SystemExit as stop:
                status = stop.code
    finally:
        sys.stderr = saved_stderr
    check("a --now with no time zone exits 2, naming the value, and writes no record",
          status == 2 and "has no time zone" in (case.root / "stderr.txt").read_text() and case.record() is None,
          status)


def test_a_missed_ask_writes_one_user_alert():
    rows = [row(f"Done {n}.", False) for n in range(3)] + [row(f"Tell me when to go. {LABELLER_ASK}", False)]
    case = Case(rows)
    check("a run with a missed ask exits 0", case.run() == 0, case.stderr)
    alerts = case.alerts()
    check("one user-alert is written, its id in the record",
          len(alerts) == 1 and case.record()["user_alert_id"] == alerts[0]["id"], alerts)
    text = alerts[0]["alert_text"] if alerts else ""
    check("the alert names the missed ask, both verdicts and the labeller's reason",
          "1 missed ask" in alerts[0]["title"] and "Tell me when to go." in text and "the hook's model: not an ask" in text
          and "the fake's reason" in text and job.COUNTS_DIRECTORY_NAME in text, alerts)


def test_wrong_stops_write_an_alert_only_past_one_in_five_of_at_least_ten():
    for case_name, refused, wrong, alerted in (
            ("3 wrong stops in 10 refused lines write an alert", 10, 3, True),
            ("2 wrong stops in 10 refused lines, 1 in 5 exactly, write none", 10, 2, False),
            ("9 wrong stops in 9 refused lines, fewer than 10, write none", 9, 9, False)):
        rows = ([row(f"Merge {n}? {LABELLER_ASK}", True) for n in range(refused - wrong)]
                + [row(f"Merged {n}?", True) for n in range(wrong)])
        case = Case(rows)
        case.run()
        alerts = case.alerts()
        check(case_name, (len(alerts) == 1) == alerted, alerts)
        if alerted:
            check("the alert names each wrong stop", alerts[0]["alert_text"].count("Merged ") == wrong
                  and "3 wrong stops in 10 refused lines" in alerts[0]["title"], alerts[0])


def test_a_failed_labelling_call_is_reported_and_left_out_of_the_counts():
    rows = [row(f"Merge {n}? {LABELLER_ASK}", True) for n in range(10)] + [row(f"Merged? {LABELLER_FAIL}", True)]
    case = Case(rows)
    status = case.run()
    check("a failed labelling call exits 1, naming the line and why, and that nothing needs doing",
          status == 1 and "Labelling failed for the line" in case.stderr and "Merged?" in case.stderr
          and "claude exited 1" in case.stderr and "1 of 11 labelling calls failed" in case.stderr
          and "Nothing needs doing." in case.stderr and "logged out" not in case.stderr, case.stderr)
    counts = case.record()["counts"]
    check("the failed line is left out of the counts",
          counts["refused_labelled"] == 10 and counts["labelling_failed"] == 1 and counts["wrong_stops"] == 0, counts)
    logged_out = Case([row(f"Merge {n}? {LABELLER_FAIL}", True) for n in range(3)])
    check("when every call fails as logged out, the message gives the sentence for the user and the rerun command",
          logged_out.run() == 1 and "`claude` on ned-box is logged out" in logged_out.stderr
          and "ssh nedlern@ned-box 'claude auth login'" in logged_out.stderr
          and job.RERUN_COMMAND.format(now=NOW.isoformat()) in logged_out.stderr and "Nothing needs doing" not in logged_out.stderr,
          logged_out.stderr)
    other = Case([row(f"Merge? {LABELLER_FAIL}", True), row(f"Merged? {LABELLER_OTHER_FAIL}", True)])
    check("when every call fails for mixed causes, the message says to fix the cause and rerun",
          other.run() == 1 and "Every labelling call failed, as the line or lines above say" in other.stderr
          and "API overloaded" in other.stderr and job.RERUN_COMMAND.format(now=NOW.isoformat()) in other.stderr
          and "logged out" not in other.stderr, other.stderr)


def test_failures_that_leave_nothing_to_count():
    case = Case([row("Merge?", True)], prompt=False)
    check("a missing labelling prompt exits 1 with no call",
          case.run() == 1 and "No lines were relabelled" in case.stderr and "could not be read" in case.stderr
          and "the answer key's labelling prompt" in case.stderr and job.RERUN_COMMAND.format(now=NOW.isoformat()) in case.stderr
          and case.model_calls() == [], case.stderr)
    unreadable_log = Case([row("Merge?", True)])
    unreadable_log.log.unlink()
    unreadable_log.log.mkdir()
    check("an unreadable log exits 1, naming the log", unreadable_log.run() == 1
          and "the hook's log of each reply line it sent its model" in unreadable_log.stderr
          and str(unreadable_log.log) in unreadable_log.stderr, unreadable_log.stderr)
    saved = job.hook.reply_line_model_ask_or_not_label_log_path
    job.hook.reply_line_model_ask_or_not_label_log_path = lambda environment: (None, "because the log-store is reachable at neither x")
    try:
        unreachable = Case([row("Merge?", True)])
        check("an unreachable log-store exits 1", unreachable.run() == 1
              and "the hook's log of each reply line it sent its model cannot be found, because the log-store is "
              "reachable at neither x"
              in unreachable.stderr, unreachable.stderr)
    finally:
        job.hook.reply_line_model_ask_or_not_label_log_path = saved


def test_an_alert_or_record_that_cannot_be_written_exits_1():
    case = Case([row(f"Go? {LABELLER_ASK}", False)])
    alerts_directory = case.home / ".local" / "state" / "nedsnodes"
    alerts_directory.mkdir(parents=True)
    (alerts_directory / "user-alerts").write_text("a file where the folder should be")
    check("a user-alert that cannot be written exits 1 and says so",
          case.run() == 1 and "the user-alert could not be written" in case.stderr, case.stderr)
    check("the record is still written, with no alert id", case.record()["user_alert_id"] is None, case.record())
    unrecorded = Case([row("Merge?", True)])
    (unrecorded.log_store / job.COUNTS_DIRECTORY_NAME).write_text("a file where the folder should be")
    check("a record that cannot be written exits 1 and says so",
          unrecorded.run() == 1 and "The record of this run could not be written" in unrecorded.stderr,
          unrecorded.stderr)


def main():
    FAKE_BIN.mkdir(parents=True)
    fake = FAKE_BIN / "claude"
    fake.write_text(FAKE_CLAUDE.replace("#!/usr/bin/env python3", f"#!{sys.executable}", 1))
    fake.chmod(0o755)
    try:
        for name, function in sorted(globals().items()):
            if name.startswith("test_") and callable(function):
                function()
    finally:
        shutil.rmtree(SUITE_ROOT, ignore_errors=True)
    if failures:
        print(f"{len(failures)} failed: {', '.join(failures)}")
        return 1
    print("all passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
