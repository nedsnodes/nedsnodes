#!/usr/bin/env python3
"""Cases for the MessageDisplay hook that shows a successor's user the end of the last session.

Run: python3 nn-systems/handoff/tests/handoff-successor-conversation-tail-last-lines-first-message-display-hook-test.py

Every case runs the hook as a subprocess under this suite's own HOME, so the display files are
ones this suite made, never the real ~/.claude/handoffs.

Prints one line per case and exits non-zero if any case fails.
"""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HOOK_SCRIPT = (Path(__file__).resolve().parent.parent
               / "handoff-successor-conversation-tail-last-lines-first-message-display-hook.py")
SESSION_ID = "5b2a9c8e-1f63-4d8a-b7c4-9e0d2a6f1c3b"
DISPLAY_TEXT = "The end of the last session: ...\n\nturn 99\nturn 100\n\nThe new session's first message:\n\n"

failures = []


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


def run_hook(home, index, delta="Reading the dialog first.\n", raw_input_text=None):
    batch = {"session_id": SESSION_ID, "hook_event_name": "MessageDisplay", "turn_id": "t",
             "message_id": "m", "index": index, "final": True, "delta": delta}
    return subprocess.run(
        [sys.executable, str(HOOK_SCRIPT)],
        input=raw_input_text if raw_input_text is not None else json.dumps(batch),
        capture_output=True, text=True, check=False, env={**os.environ, "HOME": str(home)})


with tempfile.TemporaryDirectory() as directory:
    home = Path(directory)
    handoffs = home / ".claude" / "handoffs"
    handoffs.mkdir(parents=True)
    display_file = handoffs / f"{SESSION_ID}-conversation-tail-last-lines-for-first-message-display.md"

    display_file.write_text(DISPLAY_TEXT, encoding="utf-8")
    later_batch = run_hook(home, index=1)
    check("a batch after the first prints nothing and leaves the display file",
          later_batch.returncode == 0 and later_batch.stdout == "" and display_file.exists(),
          repr(later_batch))

    first_batch = run_hook(home, index=0)
    try:
        output = json.loads(first_batch.stdout)
    except json.JSONDecodeError:
        output = None
    check("the first batch is drawn as the display file's text followed by the batch",
          first_batch.returncode == 0 and output == {"hookSpecificOutput": {
              "hookEventName": "MessageDisplay",
              "displayContent": DISPLAY_TEXT + "Reading the dialog first.\n"}},
          repr(first_batch))
    check("the display file is deleted once shown", not display_file.exists())

    next_message = run_hook(home, index=0)
    check("the next message's first batch, with no display file, prints nothing",
          next_message.returncode == 0 and next_message.stdout == "", repr(next_message))

    not_json = run_hook(home, index=0, raw_input_text="not json")
    check("stdin that is not JSON exits 1 with nothing on stdout, so the original text is drawn",
          not_json.returncode == 1 and not_json.stdout == "", repr(not_json))

if failures:
    print(f"\n{len(failures)} case(s) failed")
    sys.exit(1)
print("\nall cases passed")
