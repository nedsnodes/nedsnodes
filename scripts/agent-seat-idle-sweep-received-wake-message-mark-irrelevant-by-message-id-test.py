#!/usr/bin/env python3
"""Cases for scripts/agent-seat-idle-sweep-received-wake-message-mark-irrelevant-by-message-id.py.

Each case runs the program as a subprocess with HOME set to a folder this suite made, so that it
reads a log this suite wrote, never the real one.
"""

import atexit
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

PROGRAM = Path(__file__).with_name(
    "agent-seat-idle-sweep-received-wake-message-mark-irrelevant-by-message-id.py")
MESSAGE_ID = "3f9a1c0e5b7d4e2a9c8b1f6d0e4a7c3b"
SUITE_ROOT = Path(tempfile.mkdtemp(prefix="agent-seat-idle-sweep-mark-irrelevant-test-"))
atexit.register(shutil.rmtree, SUITE_ROOT, ignore_errors=True)
failures = []


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


def home_with_log(lines=None, log_is_directory=False):
    home = Path(tempfile.mkdtemp(dir=str(SUITE_ROOT)))
    log = home / "nedsnodes-logs" / "agent-seat-idle-sweep" / "agent-seat-idle-sweep-messages-sent-and-verdicts.jsonl"
    log.parent.mkdir(parents=True)
    if log_is_directory:
        log.mkdir()
    elif lines is not None:
        log.write_text("".join(line + "\n" for line in lines[:-1]) + (lines[-1] if lines else ""))
    return home


def run(home, *arguments):
    completed = subprocess.run([sys.executable, str(PROGRAM), *arguments], capture_output=True,
                               text=True, env={**os.environ, "HOME": str(home)}, check=False)
    return completed.returncode, completed.stdout, completed.stderr


SENT = json.dumps({"event": "message_sent", "agent_seat": "alpha", "message_id": MESSAGE_ID,
                   "send_started_at": "2026-11-24T08:00:00Z", "at": "2026-11-24T08:01:00Z"})
OTHER = json.dumps({"event": "wait_step", "agent_seat": "alpha", "message_id": MESSAGE_ID})

code, out, err = run(home_with_log([OTHER, SENT, '{"event": "message_se']), MESSAGE_ID)
check("an id the log holds as a sent message: exit 0, naming the agent-seat and the send time; a "
      "cut-short last line is skipped",
      code == 0 and "Marked irrelevant" in out and "alpha" in out
      and "2026-11-24T08:00:00Z" in out and not err, (code, out, err))

code, out, err = run(home_with_log([OTHER]), MESSAGE_ID)
check("an id only another kind of event carries: exit 1, nothing marked, copy the id from the "
      "reminder's command line, and a second miss means leave the reminder unanswered",
      code == 1 and "holds no message with the id" in err and "copy the whole command line" in err
      and "do not run this program for it again" in err and not out, (code, out, err))

code, out, err = run(home_with_log([SENT]), MESSAGE_ID.upper())
check("an id that is not 32 lowercase hexadecimal digits: exit 2, the log is not read",
      code == 2 and "is not a reminder's message_id" in err and "copy the whole command line" in err
      and not out, (code, out, err))

code, out, err = run(home_with_log(), MESSAGE_ID)
check("no log yet: exit 1, as for a log that holds no such message",
      code == 1 and "holds no message with the id" in err and not out, (code, out, err))

code, out, err = run(home_with_log(['{"event": "message_se', SENT, OTHER]), MESSAGE_ID)
check("a log with a line not UTF-8 JSON before its last, which stops the idle sweep: exit 2, the "
      "reminder cannot be checked, naming the line",
      code == 2 and "cannot be checked" in err and "line 1 is not UTF-8 JSON" in err
      and "Nothing more is needed from you" in err and not out, (code, out, err))

code, out, err = run(home_with_log(log_is_directory=True), MESSAGE_ID)
check("a log that cannot be read: exit 2, the reminder cannot be checked, and nothing more is "
      "needed, since the idle sweep reports its own log",
      code == 2 and "could not be read" in err and "cannot be checked" in err
      and "Nothing more is needed from you" in err, (code, out, err))

if failures:
    print(f"{len(failures)} case(s) failed")
    sys.exit(1)
print("all cases passed")
