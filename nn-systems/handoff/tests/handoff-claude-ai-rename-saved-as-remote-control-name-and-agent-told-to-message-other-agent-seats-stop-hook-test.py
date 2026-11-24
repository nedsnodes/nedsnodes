#!/usr/bin/env python3
"""Cases for the Stop hook that stores a claude.ai rename and its shared name file.

Run: python3 nn-systems/handoff/tests/handoff-claude-ai-rename-saved-as-remote-control-name-and-agent-told-to-message-other-agent-seats-stop-hook-test.py

Every case runs the hook under this suite's own HOME, never the real ~/.claude/handoffs.
"""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HOOK = (Path(__file__).resolve().parent.parent
        / "handoff-claude-ai-rename-saved-as-remote-control-name-and-agent-told-to-message-other-agent-seats-stop-hook.py")
SEAT_VARIABLE = "NEDSNODES_HANDOFF_SUPERVISOR_AGENT_NAME"
failures = 0


def check(name, passed, detail=""):
    global failures
    print(f"{'PASS' if passed else 'FAIL'}: {name}" + ("" if passed else f" ({detail})"))
    failures += 0 if passed else 1


def run_hook(home, stdin_text, seat="seat-a"):
    environment = {**os.environ, "HOME": str(home)}
    environment.pop(SEAT_VARIABLE, None)
    if seat:
        environment[SEAT_VARIABLE] = seat
    return subprocess.run([sys.executable, str(HOOK)], input=stdin_text, capture_output=True,
                          text=True, env=environment, timeout=30, check=False)


def transcript_with_titles(directory, *titles):
    path = Path(directory) / "transcript.jsonl"
    path.write_text("not json custom-title\n" + "".join(
        json.dumps({"type": "custom-title", "customTitle": title}) + "\n" for title in titles),
        encoding="utf-8")
    return str(path)


with tempfile.TemporaryDirectory() as directory:
    home = Path(directory)
    handoffs = home / ".claude" / "handoffs"
    handoffs.mkdir(parents=True)
    stored = handoffs / "seat-a-remote-control-name"

    transcript = transcript_with_titles(directory, "seat-a")
    result = run_hook(home, json.dumps({"transcript_path": transcript}))
    check("a title equal to the agent-seat name stores nothing and says nothing",
          result.returncode == 0 and result.stdout == "" and not stored.exists(), result)

    transcript = transcript_with_titles(directory, "seat-a", "----new name")
    result = run_hook(home, json.dumps({"transcript_path": transcript}))
    context = json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"]
    check("a changed title is stored", stored.read_text(encoding="utf-8") == "----new name\n")
    check("the agent is given the exact line to send every other agent-seat",
          "seat-a is now ----new name in Remote Control; message it there." in context
          and "to each other session ListAgents lists that is not offline" in context
          and "send to each, addressed as `<name> [<ref>]`" in context, context)

    result = run_hook(home, json.dumps({"transcript_path": transcript}))
    check("the same title at the next turn's end says nothing", result.stdout == "", result.stdout)

    transcript = transcript_with_titles(directory, "----new name", "third")
    result = run_hook(home, json.dumps({"transcript_path": transcript}))
    check("a second rename names the stored name as the old name",
          "----new name is now third" in result.stdout, result.stdout)

    stored.unlink()
    result = run_hook(home, json.dumps({"transcript_path": transcript}), seat="")
    check("a session no handoff-supervisor launched stores nothing",
          result.returncode == 0 and result.stdout == "" and not stored.exists(), result)

    no_title = Path(directory) / "no-title.jsonl"
    no_title.write_text('{"type":"user"}\n', encoding="utf-8")
    result = run_hook(home, json.dumps({"transcript_path": str(no_title)}))
    check("a transcript with no custom-title record changes nothing",
          result.returncode == 0 and result.stdout == "" and not stored.exists(), result)

    result = run_hook(home, json.dumps({"transcript_path": str(home / "missing.jsonl")}))
    check("a transcript not yet written changes nothing",
          result.returncode == 0 and result.stdout == "" and not stored.exists(), result)

    result = run_hook(home, "[]")
    check("stdin that is not an object exits 1 and names the hook on stderr",
          result.returncode == 1 and result.stdout == "" and HOOK.stem in result.stderr, result)

    result = run_hook(home, json.dumps({"transcript_path": str(home)}))
    check("a transcript that cannot be read exits 1 and reports it",
          result.returncode == 1 and "was not stored" in result.stderr
          and "tries again at the next turn's end" in result.stderr, result)

    stored.mkdir()
    transcript = transcript_with_titles(directory, "renamed")
    result = run_hook(home, json.dumps({"transcript_path": transcript}))
    check("a name that cannot be read or stored exits 1 and reports it",
          result.returncode == 1 and "was not stored" in result.stderr, result)

sys.exit(1 if failures else 0)
