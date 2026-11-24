#!/usr/bin/env python3
"""Cases for the hook that tells the user an agent-session is handing off.

Run: python3 nn-systems/handoff/tests/handoff-asked-stop-typing-user-notice-user-prompt-submit-hook-test.py

Every case runs the hook as a subprocess under this suite's own HOME, so the
handoff-asked marker files and files recording a shown notice are ones this suite made, never the
real ~/.claude/handoffs. The threshold hook computes HANDOFF_DIRECTORY from
Path.home() at import, so HOME decides the directory.

The agent-seat name and launched session id variables are set or removed explicitly
in every case, because an agent-seat running this suite has its own values in the
environment. A case that sets an agent-seat name runs as the launched agent-session,
whose session id the launched session id variable holds, unless it names another.

The exit code is asserted on every case: exit 2 from a UserPromptSubmit hook
would block the user's message.

Prints one line per case and exits non-zero if any case fails.
"""

import importlib.util
import pathlib

_start_and_end_lines_spec = importlib.util.spec_from_file_location(
    "nn_test_suite_start_time_line_and_end_results_line_print_common",
    pathlib.Path(__file__).resolve().parents[3] / "nn-systems/general-tools/nn-test-suite-start-time-line-and-end-results-line-print-common.py")
_start_and_end_lines = importlib.util.module_from_spec(_start_and_end_lines_spec)
_start_and_end_lines_spec.loader.exec_module(_start_and_end_lines)
_start_and_end_lines.nn_test_suite_start_time_line_print_now_and_end_results_line_print_at_normal_exit_register()

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

SYSTEM_DIRECTORY = Path(__file__).resolve().parent.parent
HOOK_SCRIPT = SYSTEM_DIRECTORY / "handoff-asked-stop-typing-user-notice-user-prompt-submit-hook.py"

_hook_specification = importlib.util.spec_from_file_location(
    "handoff_asked_stop_typing_user_notice_user_prompt_submit_hook", HOOK_SCRIPT)
hook = importlib.util.module_from_spec(_hook_specification)
_hook_specification.loader.exec_module(hook)

_supervisor_specification = importlib.util.spec_from_file_location(
    "handoff_supervisor", SYSTEM_DIRECTORY / "handoff-supervisor.py")
supervisor = importlib.util.module_from_spec(_supervisor_specification)
_supervisor_specification.loader.exec_module(supervisor)
AGENT_NAME_VARIABLE = supervisor.HANDOFF_SUPERVISOR_AGENT_NAME_ENVIRONMENT_VARIABLE
LAUNCHED_SESSION_ID_VARIABLE = supervisor.HANDOFF_SUPERVISOR_SESSION_ID_ENVIRONMENT_VARIABLE

failures = []


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


def run_hook(payload, home, agent_seat_name=None, raw_input_text=None, launched_session_id=None,
             stdout_encoding=None):
    environment = {**os.environ, "HOME": str(home)}
    if stdout_encoding is not None:
        environment["PYTHONIOENCODING"] = stdout_encoding
    environment.pop(AGENT_NAME_VARIABLE, None)
    environment.pop(LAUNCHED_SESSION_ID_VARIABLE, None)
    if agent_seat_name is not None:
        environment[AGENT_NAME_VARIABLE] = agent_seat_name
        if launched_session_id is None and isinstance(payload, dict):
            launched_session_id = payload.get("session_id")
        if launched_session_id:
            environment[LAUNCHED_SESSION_ID_VARIABLE] = launched_session_id
    text = raw_input_text if raw_input_text is not None else json.dumps(payload)
    return subprocess.run([sys.executable, str(HOOK_SCRIPT)], input=text, capture_output=True,
                          text=True, check=False, env=environment)


def shown_notice(result):
    """The systemMessage, when stdout is exactly one object with that key alone; else None."""
    try:
        output = json.loads(result.stdout)
    except json.JSONDecodeError:
        return None
    if not isinstance(output, dict) or set(output) != {"systemMessage"}:
        return None
    return output["systemMessage"]


def silent(result):
    return result.returncode == 0 and result.stdout == "" and result.stderr == ""


def expected_named(name):
    return ("This session is handing off; stop typing here. Use the new " + name
            + " session when it appears in claude.ai.")


EXPECTED_UNNAMED = ("This session is handing off; stop typing here. Use this agent-seat's new"
                    " session when it appears in claude.ai.")


def custom_title_record(title):
    return json.dumps({"type": "custom-title", "customTitle": title, "sessionId": "s"})


def user_record(text):
    return json.dumps({"type": "user", "message": {"role": "user", "content": text}})


with tempfile.TemporaryDirectory() as workspace:
    workspace = Path(workspace)
    home = workspace / "home"
    handoffs = home / ".claude" / "handoffs"
    handoffs.mkdir(parents=True)

    titled = workspace / "titled.jsonl"
    titled.write_text("\n".join([
        custom_title_record("efficiency"),
        user_record("mentions custom-title in passing, which is no record"),
        "{not json, custom-title",
        custom_title_record("efficiency-renamed"),
        user_record("later turn"),
    ]) + "\n", encoding="utf-8")
    untitled = workspace / "untitled.jsonl"
    untitled.write_text(user_record("no title here") + "\n", encoding="utf-8")

    def marker(session_id):
        return handoffs / f"{session_id}-handoff-asked"

    # ---- no marker file ----------------------------------------------------

    result = run_hook({"session_id": "s-none", "transcript_path": str(titled)}, home,
                      agent_seat_name="seat-a")
    check("no marker file: no output, exit 0", silent(result),
          f"code {result.returncode}, stdout {result.stdout!r}, stderr {result.stderr!r}")
    check("no marker file: no file recording a shown notice written",
          list(handoffs.iterdir()) == [], [path.name for path in handoffs.iterdir()])

    # ---- marker file present, shown once -----------------------------------

    marker("s-once").write_text("40.0\n", encoding="utf-8")
    os.utime(marker("s-once"), ns=(1_000_000_000_000, 1_000_000_000_000))
    payload = {"session_id": "s-once", "transcript_path": str(titled)}
    result = run_hook(payload, home, agent_seat_name="seat-a")
    check("marker file present: the line names the last custom-title, exit 0",
          result.returncode == 0 and shown_notice(result) == expected_named("efficiency-renamed"),
          f"code {result.returncode}, stdout {result.stdout!r}, stderr {result.stderr!r}")
    check("marker file present: the file recording the shown notice holds the marker file's modification time",
          (handoffs / "s-once-handoff-asked-user-notice-shown").read_text(encoding="utf-8").strip()
          == "1000000000000")

    result = run_hook(payload, home, agent_seat_name="seat-a")
    check("second message, same marker file: no output, exit 0", silent(result),
          f"code {result.returncode}, stdout {result.stdout!r}, stderr {result.stderr!r}")

    os.utime(marker("s-once"), ns=(2_000_000_000_000, 2_000_000_000_000))
    result = run_hook(payload, home, agent_seat_name="seat-a")
    check("a newer marker file: the line again",
          result.returncode == 0 and shown_notice(result) == expected_named("efficiency-renamed"),
          f"code {result.returncode}, stdout {result.stdout!r}")
    result = run_hook(payload, home, agent_seat_name="seat-a")
    check("a newer marker file, second message: no output", silent(result),
          f"stdout {result.stdout!r}")

    # ---- fallbacks for the name --------------------------------------------

    marker("s-untitled").write_text("40.0\n", encoding="utf-8")
    result = run_hook({"session_id": "s-untitled", "transcript_path": str(untitled)}, home,
                      agent_seat_name="seat-a")
    check("no title record: the line names the launched agent-seat",
          result.returncode == 0 and shown_notice(result) == expected_named("seat-a"),
          f"code {result.returncode}, stdout {result.stdout!r}, stderr {result.stderr!r}")

    (handoffs / "seat-a-remote-control-name").write_text("seat-a-renamed\n", encoding="utf-8")
    marker("s-stored").write_text("40.0\n", encoding="utf-8")
    result = run_hook({"session_id": "s-stored", "transcript_path": str(untitled)}, home,
                      agent_seat_name="seat-a")
    check("no title record and a stored Remote Control name: the line names the stored name",
          result.returncode == 0 and shown_notice(result) == expected_named("seat-a-renamed"),
          f"code {result.returncode}, stdout {result.stdout!r}, stderr {result.stderr!r}")
    (handoffs / "seat-a-remote-control-name").unlink()
    (handoffs / "seat-a-remote-control-name").mkdir()
    marker("s-stored-unreadable").write_text("40.0\n", encoding="utf-8")
    result = run_hook({"session_id": "s-stored-unreadable", "transcript_path": str(untitled)}, home,
                      agent_seat_name="seat-a")
    check("no title record and an unreadable stored name: the line names the agent-seat, "
          "as the handoff-supervisor launches under it then",
          result.returncode == 0 and shown_notice(result) == expected_named("seat-a"),
          f"code {result.returncode}, stdout {result.stdout!r}, stderr {result.stderr!r}")
    (handoffs / "seat-a-remote-control-name").rmdir()

    accented = workspace / "accented.jsonl"
    accented.write_text(custom_title_record("café") + "\n", encoding="utf-8")
    marker("s-ascii-stdout").write_text("40.0\n", encoding="utf-8")
    result = run_hook({"session_id": "s-ascii-stdout", "transcript_path": str(accented)}, home,
                      stdout_encoding="ascii")
    check("a title with é and an ASCII stdout: the line, exit 0",
          result.returncode == 0 and shown_notice(result) == expected_named("café"),
          f"code {result.returncode}, stdout {result.stdout!r}, stderr {result.stderr!r}")

    marker("s-unnamed").write_text("40.0\n", encoding="utf-8")
    result = run_hook({"session_id": "s-unnamed", "transcript_path": str(untitled)}, home)
    check("no title record and no agent-seat name: the line says this agent-seat's new session",
          result.returncode == 0 and shown_notice(result) == EXPECTED_UNNAMED,
          f"code {result.returncode}, stdout {result.stdout!r}, stderr {result.stderr!r}")

    marker("s-unreadable").write_text("40.0\n", encoding="utf-8")
    result = run_hook({"session_id": "s-unreadable", "transcript_path": str(workspace)}, home)
    check("unreadable transcript: the line with the fallback, exit 0",
          result.returncode == 0 and shown_notice(result) == EXPECTED_UNNAMED,
          f"code {result.returncode}, stdout {result.stdout!r}, stderr {result.stderr!r}")

    marker("s-unreadable-seat").write_text("40.0\n", encoding="utf-8")
    result = run_hook({"session_id": "s-unreadable-seat",
                       "transcript_path": str(workspace / "missing.jsonl")}, home,
                      agent_seat_name="seat-b")
    check("missing transcript: the line names the launched agent-seat, exit 0",
          result.returncode == 0 and shown_notice(result) == expected_named("seat-b"),
          f"code {result.returncode}, stdout {result.stdout!r}, stderr {result.stderr!r}")

    marker("s-no-path").write_text("40.0\n", encoding="utf-8")
    result = run_hook({"session_id": "s-no-path"}, home, agent_seat_name="seat-c")
    check("no transcript_path: the line names the launched agent-seat",
          result.returncode == 0 and shown_notice(result) == expected_named("seat-c"),
          f"code {result.returncode}, stdout {result.stdout!r}")

    marker("s-child").write_text("40.0\n", encoding="utf-8")
    result = run_hook({"session_id": "s-child", "transcript_path": str(untitled)}, home,
                      agent_seat_name="seat-a", launched_session_id="s-parent")
    check("a child agent-session started from the launched one's shell: the line names no agent-seat",
          result.returncode == 0 and shown_notice(result) == EXPECTED_UNNAMED,
          f"code {result.returncode}, stdout {result.stdout!r}, stderr {result.stderr!r}")

    # ---- faults --------------------------------------------------------------

    result = run_hook(None, home, raw_input_text="[1, 2]")
    check("stdin not a JSON object: exit 1, nothing on stdout, one stderr line naming the hook",
          result.returncode == 1 and result.stdout == ""
          and len(result.stderr.splitlines()) == 1
          and result.stderr.startswith(hook.PROGRAM + ": "),
          f"code {result.returncode}, stdout {result.stdout!r}, stderr {result.stderr!r}")

    marker("s-record-unwritable").write_text("40.0\n", encoding="utf-8")
    (handoffs / "s-record-unwritable-handoff-asked-user-notice-shown").mkdir()
    result = run_hook({"session_id": "s-record-unwritable", "transcript_path": str(titled)},
                      home, agent_seat_name="seat-a")
    check("the file recording a shown notice cannot be read: exit 1, nothing on stdout, one stderr line",
          result.returncode == 1 and result.stdout == ""
          and len(result.stderr.splitlines()) == 1
          and result.stderr.startswith(hook.PROGRAM + ": "),
          f"code {result.returncode}, stdout {result.stdout!r}, stderr {result.stderr!r}")

    # A home of its own, so that making its handoffs directory read-only touches no other case.
    unwritable_home = workspace / "unwritable-home"
    unwritable_handoffs = unwritable_home / ".claude" / "handoffs"
    unwritable_handoffs.mkdir(parents=True)
    (unwritable_handoffs / "s-record-absent-handoff-asked").write_text("40.0\n", encoding="utf-8")
    unwritable_handoffs.chmod(0o555)
    try:
        result = run_hook({"session_id": "s-record-absent", "transcript_path": str(titled)},
                          unwritable_home, agent_seat_name="seat-a")
    finally:
        unwritable_handoffs.chmod(0o755)
    check("no file recording a shown notice, and its directory refuses writes: exit 1, nothing on"
          " stdout, one stderr line",
          result.returncode == 1 and result.stdout == ""
          and len(result.stderr.splitlines()) == 1
          and result.stderr.startswith(hook.PROGRAM + ": "),
          f"code {result.returncode}, stdout {result.stdout!r}, stderr {result.stderr!r}")

    result = run_hook({"transcript_path": str(titled)}, home, agent_seat_name="seat-a")
    check("no session_id: no output, exit 0", silent(result), f"stdout {result.stdout!r}")

if failures:
    print(f"{len(failures)} case(s) failed")
    sys.exit(1)
print("all cases passed")
