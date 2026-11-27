#!/usr/bin/env python3
"""Cases for proposed-improvements-or-changes-file-entry-state-attempt-and-second-agent-verdict-lines-write.py.

Each case runs the program's main() on a file in a temporary directory, with
the time fixed, and checks the file's whole text and the exit code. A stand-in
`claude`, first on PATH, plays the second agent: it logs its arguments and the
prompt it is given, then prints the reply, exit code and delay a case sets.

Run: scripts/proposed-improvements-or-changes-file-entry-state-attempt-and-second-agent-verdict-lines-write-test.py
Exit codes: 0 all passed, 1 any failed.
"""

import contextlib
import importlib.util
import io
import json
import os
import shlex
import sys
import tempfile
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent

# Alerts go under a temporary home, so no case writes into the user's own pending/ alerts.
REAL_PENDING_ALERTS = Path.home() / ".local/state/nedsnodes/user-alerts/pending"
REAL_PENDING_BEFORE = sorted(os.listdir(REAL_PENDING_ALERTS)) if REAL_PENDING_ALERTS.is_dir() else []
TEST_HOME = Path(tempfile.mkdtemp())
os.environ["HOME"] = str(TEST_HOME)
TEST_SEAT = "test-seat"
(TEST_HOME / "agents" / TEST_SEAT / ".git").mkdir(parents=True)
LAUNCHED_IN = "NEDSNODES_HANDOFF_SUPERVISOR_WORKING_DIRECTORY"
os.environ[LAUNCHED_IN] = str(TEST_HOME / "agents" / TEST_SEAT)
PENDING_ALERTS = TEST_HOME / ".local/state/nedsnodes/user-alerts/pending"
SPEC = importlib.util.spec_from_file_location(
    "entry_lines_write",
    HERE / "proposed-improvements-or-changes-file-entry-state-attempt-and-second-agent-verdict-lines-write.py")
PROGRAM = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PROGRAM)
PROGRAM.now = lambda: "2026-11-10T12:00Z"

failures = []
case_count = 0

STAND_IN_CLAUDE = f"""#!{sys.executable}
import json, os, sys, time
from pathlib import Path
control = Path(os.environ["STAND_IN_CLAUDE_CONTROL"])
with (control / "calls.jsonl").open("a", encoding="utf-8") as log:
    log.write(json.dumps({{"argv": sys.argv[1:], "stdin": sys.stdin.read()}}) + "\\n")
answer = json.loads((control / "answer.json").read_text(encoding="utf-8"))
time.sleep(answer["sleep_seconds"])
sys.stdout.write(answer["stdout"])
sys.stderr.write(answer["stderr"])
sys.exit(answer["exit_code"])
"""
STAND_IN_DIRECTORY = Path(tempfile.mkdtemp())
(STAND_IN_DIRECTORY / "claude").write_text(STAND_IN_CLAUDE, encoding="utf-8")
(STAND_IN_DIRECTORY / "claude").chmod(0o755)
os.environ["PATH"] = f"{STAND_IN_DIRECTORY}{os.pathsep}{os.environ['PATH']}"
os.environ["STAND_IN_CLAUDE_CONTROL"] = str(STAND_IN_DIRECTORY)


def second_agent_answers(stdout, exit_code=0, stderr="", sleep_seconds=0):
    (STAND_IN_DIRECTORY / "answer.json").write_text(json.dumps(
        {"stdout": stdout, "exit_code": exit_code, "stderr": stderr, "sleep_seconds": sleep_seconds}), encoding="utf-8")
    (STAND_IN_DIRECTORY / "calls.jsonl").unlink(missing_ok=True)


def second_agent_calls():
    log = STAND_IN_DIRECTORY / "calls.jsonl"
    return [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()] if log.exists() else []


AGREES = "The ruling covers decisions, and the edit fixes a link.\nVERDICT: agrees\n"
DISAGREES = "The sources do not show it.\nVERDICT: disagrees\n"
VERDICT = ["second-agent-verdict", "E1", "--by", "h"]

FILE_TEXT = """# Proposed improvements or changes from ghi-guide-agent, 2026-11-10

Key of the GHI-MD text ghi-guide-agent reviewed: ghipair0

## E1 — possible problem: the edit may break the user-ruling "closed GHIs are frozen"
Goes wrong when: a closed GHI's decision changes without the user.
State: open

## E2 — improvement: remove the unused flag
Gain: a smaller tool.
State: open
"""


def case(name, condition):
    global case_count
    case_count += 1
    if not condition:
        failures.append(name)
        print(f"FAIL  {name}")


def run(path, *arguments):
    """(exit code, stdout, stderr) of main() on `path`."""
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = PROGRAM.main([arguments[0], str(path), *arguments[1:]])
    return code, out.getvalue(), err.getvalue()


def fresh(text=FILE_TEXT):
    directory = Path(tempfile.mkdtemp())
    path = directory / "x-proposed-improvements-or-changes-ghi-guide-agent-2026-11-10.md"
    path.write_text(text, encoding="utf-8")
    return path


def pending_alerts():
    """The pending alerts, oldest first, each removed once read."""
    alerts = []
    for alert_path in sorted(PENDING_ALERTS.glob("*.json")) if PENDING_ALERTS.is_dir() else []:
        alerts.append(json.loads(alert_path.read_text(encoding="utf-8")))
        alert_path.unlink()
    return alerts


def entry(path, name):
    lines = path.read_text(encoding="utf-8").splitlines()
    start, end = PROGRAM.entry_spans(lines)[name]
    return [line for line in lines[start:end] if line.strip()]


# An attempt goes under the entry, numbered, timed, and touches nothing else.
path = fresh()
code, out, _ = run(path, "attempt", "E1", "--by", "h handler", "--found", "read the ruling", "--outcome", "not-worth-doing", "--source", "PR 5")
case("an attempt exits 0", code == 0)
case("an attempt is the entry's last line",
     entry(path, "E1")[-1] == "Attempt 1 — h handler, 2026-11-10T12:00Z: read the ruling — sources read: PR 5")
case("an attempt leaves the other entry alone",
     entry(path, "E2") == ["## E2 — improvement: remove the unused flag", "Gain: a smaller tool.", "State: open"])
case("an attempt keeps the blank line before the next entry",
     "sources read: PR 5\n\n## E2" in path.read_text(encoding="utf-8"))
case("an attempt leaves the file's text before the entry alone",
     path.read_text(encoding="utf-8").startswith(FILE_TEXT.split("## E1")[0]))
case("show is printed after a change", "E1: State: open; attempts since the user last decided: 1 of 3" in out)

# Related entries: one attempt line under each, each numbered for its own entry.
path = fresh()
run(path, "attempt", "E2", "--by", "h", "--found", "first", "--outcome", "not-worth-doing", "--source", "PR 5")
code, _, _ = run(path, "attempt", "E1", "E2", "--by", "h", "--found", "one cause", "--outcome", "not-worth-doing", "--source", "PR 5")
case("an attempt on two entries exits 0", code == 0)
case("the first related entry gets attempt 1", entry(path, "E1")[-1] == "Attempt 1 — h, 2026-11-10T12:00Z: one cause — sources read: PR 5")
case("the second related entry gets attempt 2", entry(path, "E2")[-1] == "Attempt 2 — h, 2026-11-10T12:00Z: one cause — sources read: PR 5")

# A third not-worth-doing attempt sends the entry to the second agent; while another entry is open, a fourth
# attempt is refused, under every entry named, and the file is unchanged.
path = fresh()
for number in range(3):
    _, third_out, _ = run(path, "attempt", "E1", "--by", "h", "--found", f"attempt {number}", "--outcome", "not-worth-doing", "--source", "PR 5")
case("a second attempt says nothing of 3 attempts",
     "now has" not in run(fresh(), "attempt", "E1", "--by", "h", "--found", "x", "--outcome", "not-worth-doing", "--source", "PR 5")[1])
before = path.read_text(encoding="utf-8")
code, _, err = run(path, "attempt", "E2", "E1", "--by", "h", "--found", "fourth", "--outcome", "left-open", "--source", "PR 5")
case("a third not-worth-doing attempt leaves the entry open", entry(path, "E1")[2] == "State: open")
case("a third not-worth-doing attempt sends the entry to the second agent",
     "Entry E1 now has 3 attempts: run the second-agent-verdict subcommand" in third_out)
case("a fourth attempt while another entry is open exits 1", code == 1)
case("a fourth attempt while another entry is open says to mark the entry for the user",
     "REFUSED:" in err and "while another entry of the GHI-MD is open" in err and "--because three-attempts" in err)
case("a refused attempt changes no entry", path.read_text(encoding="utf-8") == before)

# A third left-open attempt marks the entry as needing the user while another entry of its GHI-MD is open,
# in its own file or in another of the GHI-MD's files.
SOLE_ENTRY_TEXT = FILE_TEXT.split("\n## E2")[0] + "\n"


def sibling(path, text, suffix="-2"):
    other = path.with_name(path.name.replace(".md", f"{suffix}.md"))
    other.write_text(text, encoding="utf-8")
    return other


for name, text, other_text in (("in its own file", FILE_TEXT, None),
                               ("in another file of its GHI-MD", SOLE_ENTRY_TEXT, FILE_TEXT)):
    path = fresh(text)
    if other_text is not None:
        sibling(path, other_text)
    for number in range(3):
        code, out, _ = run(path, "attempt", "E1", "--by", "h", "--found", f"could not settle {number}", "--outcome", "left-open", "--source", "PR 5")
    case(f"a third left-open attempt while an entry is open {name} marks the entry as needing the user", code == 0
         and entry(path, "E1")[2] == "State: needs the user — h, 2026-11-10T12:00Z: still open after 3 attempts; could not settle 2")
    case(f"a third left-open attempt while an entry is open {name} says the entry was marked",
         "Attempt 3 left entry E1 open" in out and "marked as needing the user" in out)

# When the other file's entries are settled or need the user, the third left-open attempt does not mark the
# entry, and the fourth does; a fifth is refused.
for name, other_state in (("settled", "State: settled, done — h, t: removed"), ("needing the user", "State: needs the user — h, t: decide")):
    path = fresh(SOLE_ENTRY_TEXT)
    other = sibling(path, FILE_TEXT.replace("State: open", other_state))
    for number in range(3):
        code, out, _ = run(path, "attempt", "E1", "--by", "h", "--found", f"could not settle {number}", "--outcome", "left-open", "--source", "PR 5")
    case(f"with the other file's entries {name}, a third left-open attempt leaves the entry open",
         code == 0 and entry(path, "E1")[2] == "State: open")
    case(f"with the other file's entries {name}, a third left-open attempt says a fourth is allowed",
         "Entry E1 now has 3 attempts, and no other entry of the GHI-MD is open, so it gets a fourth attempt" in out)
    code, out, _ = run(path, "attempt", "E1", "--by", "h", "--found", "could not settle 3", "--outcome", "left-open", "--source", "PR 5")
    case(f"with the other file's entries {name}, a fourth left-open attempt marks the entry as needing the user", code == 0
         and entry(path, "E1")[2] == "State: needs the user — h, 2026-11-10T12:00Z: still open after 4 attempts; could not settle 3"
         and entry(path, "E1")[-1].startswith("Attempt 4 — h"))
    case(f"with the other file's entries {name}, the other file is unchanged",
         other.read_text(encoding="utf-8") == FILE_TEXT.replace("State: open", other_state))
path = fresh(SOLE_ENTRY_TEXT.replace("State: open\n", "State: open\nAttempt 1 — h, t: a\nAttempt 2 — h, t: b\n"
                                     "Attempt 3 — h, t: c\nAttempt 4 — h, t: d\n"))
before = path.read_text(encoding="utf-8")
code, _, err = run(path, "attempt", "E1", "--by", "h", "--found", "fifth", "--outcome", "settles", "--source", "PR 5")
case("a fifth attempt is refused", code == 1 and "already has 4 attempts" in err and path.read_text(encoding="utf-8") == before)

# A file of another GHI-MD beside it is not counted; an entry with no State line is.
path = fresh(SOLE_ENTRY_TEXT)
other = path.with_name("y" + path.name[1:])
other.write_text(FILE_TEXT, encoding="utf-8")
for number in range(3):
    run(path, "attempt", "E1", "--by", "h", "--found", f"n {number}", "--outcome", "left-open", "--source", "PR 5")
case("an open entry of another GHI-MD's file does not take the fourth attempt away", entry(path, "E1")[2] == "State: open")
path = fresh(SOLE_ENTRY_TEXT)
sibling(path, FILE_TEXT.replace("Gain: a smaller tool.\nState: open\n", "Gain: a smaller tool.\n")
        .replace("changes without the user.\nState: open", "changes without the user.\nState: settled, done — h, t: x"))
for number in range(3):
    run(path, "attempt", "E1", "--by", "h", "--found", f"n {number}", "--outcome", "left-open", "--source", "PR 5")
case("an entry with no State line in another file counts as open", entry(path, "E1")[2].startswith("State: needs the user"))

# Two related entries left open together: each is the other's open entry, so both are marked.
path = fresh()
for number in range(3):
    code, _, _ = run(path, "attempt", "E1", "E2", "--by", "h", "--found", f"one cause {number}", "--outcome", "left-open", "--source", "PR 5")
case("a third left-open attempt on two related entries marks both", code == 0
     and entry(path, "E1")[2].startswith("State: needs the user") and entry(path, "E2")[2].startswith("State: needs the user"))

# Another file of the GHI-MD that cannot be read fails, and the file is left as it was.
path = fresh(SOLE_ENTRY_TEXT.replace("State: open\n", "State: open\nAttempt 1 — h, t: a\nAttempt 2 — h, t: b\n"))
path.with_name(path.name.replace(".md", "-2.md")).mkdir()
before = path.read_text(encoding="utf-8")
code, _, err = run(path, "attempt", "E1", "--by", "h", "--found", "n", "--outcome", "left-open", "--source", "PR 5")
case("another file of the GHI-MD that cannot be read fails", code == 1 and "FAILED:" in err
     and "another file of the same GHI-MD, could not be read" in err and path.read_text(encoding="utf-8") == before)

# A file whose name holds no -proposed-improvements-or-changes- cannot have its GHI-MD's files found.
path = Path(tempfile.mkdtemp()) / "notes.md"
path.write_text(SOLE_ENTRY_TEXT.replace("State: open\n", "State: open\nAttempt 1 — h, t: a\nAttempt 2 — h, t: b\n"), encoding="utf-8")
before = path.read_text(encoding="utf-8")
code, _, err = run(path, "attempt", "E1", "--by", "h", "--found", "n", "--outcome", "left-open", "--source", "PR 5")
case("a third left-open attempt on a file named without the infix is refused", code == 1 and "REFUSED:" in err
     and "holds no -proposed-improvements-or-changes-" in err and path.read_text(encoding="utf-8") == before)

# A user-ruling line starts the count again.
path = fresh(FILE_TEXT.replace("State: open\n\n## E2",
                               "State: open\nAttempt 1 — h, t: a\nAttempt 2: b\nAttempt 3 — h, t: c\n"
                               "User-ruling — the user, 2026-11-09: keep it\n\n## E2"))
code, _, _ = run(path, "attempt", "E1", "--by", "h", "--found", "after the ruling", "--outcome", "not-worth-doing", "--source", "PR 5")
case("an attempt after a user-ruling line is allowed", code == 0)
case("an attempt after a user-ruling line is attempt 1",
     entry(path, "E1")[-1] == "Attempt 1 — h, 2026-11-10T12:00Z: after the ruling — sources read: PR 5")

# A Try line is not an Attempt line, so it is not counted.
path = fresh(FILE_TEXT.replace("State: open\n\n## E2",
                               "State: open\nTry 1 — h, t: a\nTry 2 — h, t: b\nTry 3 — h, t: c\n\n## E2"))
code, _, _ = run(path, "attempt", "E1", "--by", "h", "--found", "after Try lines", "--outcome", "not-worth-doing", "--source", "PR 5")
case("an attempt after three Try lines is attempt 1", code == 0
     and entry(path, "E1")[-1] == "Attempt 1 — h, 2026-11-10T12:00Z: after Try lines — sources read: PR 5")

# A settled entry takes no attempt, verdict or new state.
settled_text = FILE_TEXT.replace("Gain: a smaller tool.\nState: open", "Gain: a smaller tool.\nState: settled, done — h, t: removed")
for command in (["attempt", "E2", "--by", "h", "--found", "x", "--outcome", "not-worth-doing", "--source", "PR 5"],
                ["second-agent-verdict", "E2", "--by", "h"],
                ["settle", "E2", "--kind", "done", "--by", "h", "--how", "x"],
                ["needs-the-user", "E2", "--because", "user-ruling-change", "--by", "h", "--why", "x"]):
    path = fresh(settled_text)
    code, _, err = run(path, *command)
    case(f"{command[0]} on a settled entry is refused",
         code == 1 and "is not open" in err and path.read_text(encoding="utf-8") == settled_text)
    waiting_text = settled_text.replace("State: settled, done — h, t: removed", "State: needs the user — h, t: decide")
    path = fresh(waiting_text)
    code, _, err = run(path, *command)
    case(f"{command[0]} on an entry that needs the user is refused",
         code == 1 and "is not open" in err and path.read_text(encoding="utf-8") == waiting_text)

# A hashtag line or a lower heading inside an entry does not end it.
path = fresh(FILE_TEXT.replace("Goes wrong when: a closed GHI's decision changes without the user.\n",
                               "Goes wrong when: a closed GHI's decision changes without the user.\n#prose\n### Detail\n"))
code, _, _ = run(path, "settle", "E1", "--kind", "done", "--by", "h", "--how", "fixed")
case("an entry with a hashtag line and a lower heading keeps its State line", code == 0
     and entry(path, "E1")[-1].startswith("State: settled, done")
     and sum(line.startswith("State:") for line in entry(path, "E1")) == 1)

# A value with a line break is refused, since it would split the line.
path = fresh()
code, _, err = run(path, "attempt", "E1", "--by", "h", "--found", "one\nState: settled", "--outcome", "not-worth-doing", "--source", "PR 5")
case("a value with a line break is refused", code == 1 and "line break" in err
     and path.read_text(encoding="utf-8") == FILE_TEXT)
code, _, _ = run(path, "settle", "E1", "--kind", "done", "--by", "h", "--how", "a\rb")
case("a carriage return is refused too", code == 1 and path.read_text(encoding="utf-8") == FILE_TEXT)

# A missing entry is refused, naming the entries there are.
path = fresh()
code, _, err = run(path, "attempt", "E9", "--by", "h", "--found", "x", "--outcome", "not-worth-doing", "--source", "PR 5")
case("a missing entry is refused", code == 1 and "no entry E9" in err and "E1, E2" in err)

# A verdict needs an attempt after the last verdict, and the agent is not run without one.
path = fresh()
second_agent_answers(AGREES)
code, _, err = run(path, *VERDICT)
case("a verdict with no attempt is refused", code == 1 and "no Attempt line after its last verdict" in err)
case("no second agent runs for a refused verdict", second_agent_calls() == [])
run(path, "attempt", "E1", "--by", "h", "--found", "not real", "--outcome", "not-worth-doing", "--source", "PR 5")
second_agent_answers(DISAGREES)
code, out, _ = run(path, *VERDICT)
case("a verdict after an attempt exits 0", code == 0)
case("a disagreement is recorded in the ruled wording",
     entry(path, "E1")[-1] == "Second agent: disagrees that it is not worth doing, "
     "claude-opus-5-5 run through `claude -p` for h, 2026-11-10T12:00Z")
case("the second agent's reply is printed", "The sources do not show it." in out)
second_agent_answers(AGREES)
code, _, err = run(path, *VERDICT)
case("a second verdict on one attempt is refused", code == 1 and "no Attempt line after its last verdict" in err)

# A disagreement on the third attempt marks the entry as needing the user; on an earlier attempt, or an agreement, does not.
path = fresh()
for number in range(2):
    run(path, "attempt", "E1", "--by", "h", "--found", f"attempt {number}", "--outcome", "not-worth-doing", "--source", "PR 5")
    second_agent_answers(DISAGREES)
    code, out, _ = run(path, *VERDICT)
case("a disagreement on the second attempt leaves the entry open", code == 0 and entry(path, "E1")[2] == "State: open"
     and "marked as needing the user" not in out)
run(path, "attempt", "E1", "--by", "h", "--found", "attempt 3", "--outcome", "not-worth-doing", "--source", "PR 5")
code, out, _ = run(path, *VERDICT)
case("a disagreement on the third attempt is recorded", code == 0
     and entry(path, "E1")[-1].startswith("Second agent: disagrees that it is not worth doing"))
case("a disagreement on the third attempt marks the entry as needing the user",
     entry(path, "E1")[2] == "State: needs the user — h, 2026-11-10T12:00Z: still open after 3 attempts; "
     "the last attempt found the entry not worth doing, and the second agent disagreed")
case("a disagreement on the third attempt says the entry was marked", "so the entry was marked as needing the user" in out)
path = fresh()
for number in range(3):
    run(path, "attempt", "E1", "--by", "h", "--found", f"attempt {number}", "--outcome", "not-worth-doing", "--source", "PR 5")
    second_agent_answers(DISAGREES if number < 2 else AGREES)
    run(path, *VERDICT)
case("an agreement on the third attempt leaves the entry open to settle",
     entry(path, "E1")[2] == "State: open" and entry(path, "E1")[-1].startswith("Second agent: agrees"))

# An agreement is recorded; the agent is run headless, with Bash to read its sources.
path = fresh()
run(path, "attempt", "E1", "--by", "h", "--found", "not real", "--outcome", "not-worth-doing", "--source", "PR 5")
second_agent_answers(AGREES)
code, _, _ = run(path, *VERDICT)
case("an agreement is recorded", code == 0 and entry(path, "E1")[-1].startswith("Second agent: agrees that it is not worth doing"))
argv = second_agent_calls()[0]["argv"]
case("the second agent runs through the common prefix, in dontAsk mode",
     argv[:5] == ["-p", "--strict-mcp-config", "--permission-mode", "dontAsk", "--settings"]
     and json.loads(argv[5]).get("disableAllHooks") is True)
case("the second agent has Bash and no tool that writes",
     argv[argv.index("--tools") + 1] == "Bash,Read,Grep,Glob" and argv[argv.index("--allowedTools") + 1] == "Bash,Read,Grep,Glob")

# Each failure of the second agent records no verdict and leaves the file as it was.
for name, answer, expected in (
        ("a reply ending in another line", dict(stdout="VERDICT: agrees\nI think so.\n"), "does not end with the line"),
        ("a reply ending in a verdict with words after it", dict(stdout="VERDICT: agrees, mostly\n"), "does not end with the line"),
        ("an empty reply", dict(stdout=""), "Its reply: empty"),
        ("a nonzero exit", dict(stdout="VERDICT: agrees\n", stderr="Not logged in", exit_code=1), "exited 1"),
        ("a run past the timeout", dict(stdout="VERDICT: agrees\n", sleep_seconds=5), "did not finish within 1 s")):
    path = fresh()
    run(path, "attempt", "E1", "--by", "h", "--found", "not real", "--outcome", "not-worth-doing", "--source", "PR 5")
    before = path.read_text(encoding="utf-8")
    second_agent_answers(**answer)
    with mock.patch.object(PROGRAM, "SECOND_AGENT_TIMEOUT_SECONDS", 1):
        code, _, err = run(path, *VERDICT)
    case(f"{name} exits 1 with what came back", code == 1 and "FAILED:" in err and expected in err)
    case(f"{name} records no verdict", path.read_text(encoding="utf-8") == before)
path = fresh()
run(path, "attempt", "E1", "--by", "h", "--found", "not real", "--outcome", "not-worth-doing", "--source", "PR 5")
second_agent_answers("Not logged in\n", exit_code=1, stderr="Please run /login")
code, _, err = run(path, *VERDICT)
case("a nonzero exit prints what the agent printed", "Please run /login" in err and "Not logged in" in err)
with mock.patch.dict(os.environ, {"PATH": str(Path(tempfile.mkdtemp()))}):
    code, _, err = run(path, *VERDICT)
case("a missing claude exits 1 and says claude could not be started",
     code == 1 and "`claude` could not be started" in err)

# The verdict is written into the file as it is when the agent finishes.
path = fresh()
run(path, "attempt", "E1", "--by", "h", "--found", "not real", "--outcome", "not-worth-doing", "--source", "PR 5")


def reply_while_another_attempt_lands(prompt):
    path.write_text(path.read_text(encoding="utf-8").replace("Gain: a smaller tool.", "Gain: a smaller tool.\nAttempt 1 — other, t: meanwhile"),
                    encoding="utf-8")
    return AGREES


with mock.patch.object(PROGRAM, "second_agent_reply", reply_while_another_attempt_lands):
    code, _, _ = run(path, *VERDICT)
case("a line written while the agent ran is kept", code == 0 and "Attempt 1 — other, t: meanwhile" in entry(path, "E2"))

# The handler's own value cannot be given as the verdict.
with contextlib.redirect_stderr(io.StringIO()):
    try:
        PROGRAM.main(["second-agent-verdict", str(path), "E1", "--agrees", "--who", "w"])
        refused = False
    except SystemExit as stop:
        refused = stop.code == 2
case("a verdict typed by the handler is not accepted", refused)

# Not worth doing needs an agreement that answers the last attempt.
path = fresh()
run(path, "attempt", "E1", "--by", "h", "--found", "not real", "--outcome", "not-worth-doing", "--source", "PR 5")
code, _, err = run(path, "settle", "E1", "--kind", "not-worth-doing", "--by", "h", "--how", "x")
case("not worth doing with no verdict is refused", code == 1 and "stays open" in err)
second_agent_answers(DISAGREES)
run(path, *VERDICT)
code, _, _ = run(path, "settle", "E1", "--kind", "not-worth-doing", "--by", "h", "--how", "x")
case("not worth doing after a disagreement is refused", code == 1)
run(path, "attempt", "E1", "--by", "h", "--found", "again", "--outcome", "not-worth-doing", "--source", "PR 5")
second_agent_answers(AGREES)
run(path, *VERDICT)
code, _, _ = run(path, "settle", "E1", "--kind", "not-worth-doing", "--by", "h", "--how", "the ruling covers decisions")
case("not worth doing after an agreement exits 0", code == 0)
case("the State line is rewritten in place",
     entry(path, "E1")[2] == "State: settled, not worth doing — h, 2026-11-10T12:00Z: the ruling covers decisions")
case("only one State line remains", sum(line.startswith("State:") for line in entry(path, "E1")) == 1)

path = fresh()
run(path, "attempt", "E1", "--by", "h", "--found", "a", "--outcome", "not-worth-doing", "--source", "PR 5")
second_agent_answers(AGREES)
run(path, *VERDICT)
run(path, "attempt", "E1", "--by", "h", "--found", "b", "--outcome", "not-worth-doing", "--source", "PR 5")
code, _, _ = run(path, "settle", "E1", "--kind", "not-worth-doing", "--by", "h", "--how", "x")
case("an agreement followed by a newer attempt does not settle", code == 1)

# Done and new GHI need no verdict; an entry with no State line gets one.
path = fresh(FILE_TEXT.replace("Gain: a smaller tool.\nState: open\n", "Gain: a smaller tool.\n"))
code, _, _ = run(path, "settle", "E2", "--kind", "new-ghi", "--by", "h", "--how",
                 "filed as https://github.com/nedsnodes/nedsnodes/issues/9")
case("new GHI settles with no verdict", code == 0)
case("an entry with no State line gets one at its end",
     entry(path, "E2")[-1] == "State: settled, new GHI filed — h, 2026-11-10T12:00Z: filed as https://github.com/nedsnodes/nedsnodes/issues/9")
for how in ("GHI 9", "https://github.com/nedsnodes/nedsnodes/pull/9", "https://github.com/nedsnodes/nedsnodes/issues/"):
    path = fresh()
    code, _, err = run(path, "settle", "E2", "--kind", "new-ghi", "--by", "h", "--how", how)
    case(f"new GHI with --how {how!r} is refused", code == 1 and "holds no GHI link" in err
         and path.read_text(encoding="utf-8") == FILE_TEXT)

# Settled by an upstream entry: an attempt and a done State line, each quoting the upstream entry's State line.
UPSTREAM_DONE = "State: settled, done — h, t: PR 7 deletes the job"
UPSTREAM_TEXT = FILE_TEXT.replace("changes without the user.\nState: open", f"changes without the user.\n{UPSTREAM_DONE}")
CITES = f"settled by the change that settled E1: {UPSTREAM_DONE}"
path = fresh(UPSTREAM_TEXT)
code, _, _ = run(path, "settle", "E2", "--settled-by", "E1", "--by", "h")
case("settled by an entry of the same file exits 0", code == 0)
case("settled by an entry of the same file writes the attempt and the done State line", entry(path, "E2")[2:] == [
    f"State: settled, done — h, 2026-11-10T12:00Z: {CITES}",
    f"Attempt 1 — h, 2026-11-10T12:00Z: {CITES} — sources read: {path}"])
case("settled by an upstream entry leaves the upstream entry alone", entry(path, "E1")[2] == UPSTREAM_DONE)
path = fresh()
other = sibling(path, UPSTREAM_TEXT)
code, _, _ = run(path, "settle", "E2", "--settled-by", str(other), "E1", "--by", "h")
cited_elsewhere = f"settled by the change that settled E1 of {other}: {UPSTREAM_DONE}"
case("settled by an entry of another file cites that file", code == 0 and entry(path, "E2")[2:] == [
    f"State: settled, done — h, 2026-11-10T12:00Z: {cited_elsewhere}",
    f"Attempt 1 — h, 2026-11-10T12:00Z: {cited_elsewhere} — sources read: {other}"])
case("settled by an entry of another file leaves that file alone", other.read_text(encoding="utf-8") == UPSTREAM_TEXT)
for name, text, arguments, expected in (
        ("an upstream entry that is open", FILE_TEXT, ["--settled-by", "E1"], "is not settled as done (State: open)"),
        ("an upstream entry settled as not worth doing",
         FILE_TEXT.replace("changes without the user.\nState: open", "changes without the user.\nState: settled, not worth doing — h, t: x"),
         ["--settled-by", "E1"], "is not settled as done"),
        ("an upstream entry with no State line", FILE_TEXT.replace("changes without the user.\nState: open\n", "changes without the user.\n"),
         ["--settled-by", "E1"], "no State line"),
        ("a missing upstream entry", UPSTREAM_TEXT, ["--settled-by", "E9"], "has no entry E9"),
        ("an upstream file that cannot be read", UPSTREAM_TEXT, ["--settled-by", "/nonexistent/x.md", "E1"], "could not be read"),
        ("three values", UPSTREAM_TEXT, ["--settled-by", "a", "b", "E1"], "was given 3 values"),
        ("--kind with it", UPSTREAM_TEXT, ["--settled-by", "E1", "--kind", "done"], "takes no --kind or --how"),
        ("--how with it", UPSTREAM_TEXT, ["--settled-by", "E1", "--how", "x"], "takes no --kind or --how"),
        ("neither it nor --how", UPSTREAM_TEXT, ["--kind", "done"], "needs both --kind and --how, or --settled-by")):
    path = fresh(text)
    code, _, err = run(path, "settle", "E2", *arguments, "--by", "h")
    case(f"settled by with {name} is refused", code == 1 and expected in err and path.read_text(encoding="utf-8") == text)
path = fresh(UPSTREAM_TEXT.replace("Gain: a smaller tool.\nState: open", "Gain: a smaller tool.\nState: needs the user — h, t: decide"))
before = path.read_text(encoding="utf-8")
code, _, err = run(path, "settle", "E2", "--settled-by", "E1", "--by", "h")
case("settled by on an entry that is not open is refused", code == 1 and "is not open" in err and path.read_text(encoding="utf-8") == before)

# Needs the user: three-attempts needs three attempts; the other reasons need none.
path = fresh()
code, _, err = run(path, "needs-the-user", "E1", "--because", "three-attempts", "--by", "h", "--why", "x")
case("three-attempts with no attempts is refused", code == 1 and "fewer than 3" in err)
for number in range(3):
    run(path, "attempt", "E1", "--by", "h", "--found", "t", "--outcome", "not-worth-doing", "--source", "PR 5")
code, _, _ = run(path, "needs-the-user", "E1", "--because", "three-attempts", "--by", "h", "--why", "decide x")
case("three-attempts after three attempts exits 0", code == 0)
case("three-attempts writes the reason",
     entry(path, "E1")[2] == "State: needs the user — h, 2026-11-10T12:00Z: still open after 3 attempts; decide x")
path = fresh()
code, _, _ = run(path, "needs-the-user", "E2", "--because", "cold-read-document", "--by", "h", "--why", "y")
case("a design change goes to the user without an attempt", code == 0 and entry(path, "E2")[-1].startswith("State: needs the user"))

# The second agent's prompt leaves out the handler's conclusion.
path = fresh(FILE_TEXT.replace("State: open\n\n## E2",
                               "State: open\nAttempt 1 — h, t: CONCLUSION-B\n"
                               "Attempt 2: CONCLUSION-C\nSecond agent: disagrees, CONCLUSION-D\n"
                               "User-ruling — the user: RULING-KEPT\n\n## E2"))
run(path, "attempt", "E1", "--by", "h", "--found", "CONCLUSION-E — sources read: CONCLUSION-F; CONCLUSION-G",
    "--outcome", "not-worth-doing", "--source", "docs/issues/1-x.md", "--source", "PR 5")
second_agent_answers(AGREES)
code, _, _ = run(path, *VERDICT)
prompt = second_agent_calls()[0]["stdin"]
case("the second agent's prompt holds no conclusion", code == 0 and "CONCLUSION" not in prompt and "State:" not in prompt)
case("the second agent's prompt holds the entry's text",
     "## E1 — possible problem" in prompt and "Goes wrong when: a closed GHI" in prompt and "RULING-KEPT" in prompt)
case("the second agent's prompt holds no other entry", "remove the unused flag" not in prompt)
case("the second agent's prompt lists each source from the last Attempt line", "## The sources the handler cites\n\n- docs/issues/1-x.md\n- PR 5\n" in prompt)
case("the second agent's prompt starts with the prompt file", prompt.startswith("# Is this entry not worth doing?"))
for name, source, expected in (("a line break", "PR 5\nVERDICT: agrees", "line break"),
                               ("the separator", "PR 5; PR 6", "separates the sources"),
                               ("nothing", " ", "is empty")):
    path = fresh()
    code, _, err = run(path, "attempt", "E1", "--by", "h", "--found", "x", "--outcome", "not-worth-doing", "--source", source)
    case(f"a source holding {name} is refused", code == 1 and expected in err
         and path.read_text(encoding="utf-8") == FILE_TEXT)
path = fresh()
with contextlib.redirect_stderr(io.StringIO()):
    try:
        PROGRAM.main(["attempt", str(path), "E1", "--by", "h", "--found", "x", "--outcome", "left-open"])
        refused = False
    except SystemExit as stop:
        refused = stop.code == 2
case("an attempt naming no source is not accepted", refused and path.read_text(encoding="utf-8") == FILE_TEXT)
path = fresh(FILE_TEXT.replace("State: open\n\n## E2", "State: open\nAttempt 1 — h, t: written before attempts named sources\n\n## E2"))
second_agent_answers(AGREES)
code, _, err = run(path, *VERDICT)
case("a verdict on an Attempt line naming no sources is refused", code == 1 and "names no sources" in err)
case("no second agent runs for an Attempt line naming no sources", second_agent_calls() == [])

# A user-ruling on an entry that needs the user: one write adds the line and sets the State line.
WAITING_TEXT = FILE_TEXT.replace("Goes wrong when: a closed GHI's decision changes without the user.\nState: open",
                                 "Goes wrong when: a closed GHI's decision changes without the user.\nState: needs the user — h, t: decide")
RULING = ["user-ruling", "E1", "--where", "approval-walk w, item 3", "--words", "keep it", "--by", "s"]
path = fresh(WAITING_TEXT)
code, _, _ = run(path, *RULING, "--state", "open")
case("a ruling setting the entry open exits 0", code == 0)
case("a ruling setting the entry open writes the line and the State line", entry(path, "E1")[2:] == [
    "State: open", "User-ruling — the user, 2026-11-10T12:00Z, approval-walk w, item 3: keep it"])
case("a ruling leaves the other entry alone", entry(path, "E2") == ["## E2 — improvement: remove the unused flag", "Gain: a smaller tool.", "State: open"])
path = fresh(WAITING_TEXT)
code, _, _ = run(path, *RULING, "--state", "settled")
case("a ruling settling the entry writes the line and the settled State line", code == 0 and entry(path, "E1")[2:] == [
    "State: settled, by the user's ruling — s, 2026-11-10T12:00Z: approval-walk w, item 3",
    "User-ruling — the user, 2026-11-10T12:00Z, approval-walk w, item 3: keep it"])
for name, text in (("an open entry", FILE_TEXT),
                   ("a settled entry", FILE_TEXT.replace("changes without the user.\nState: open",
                                                         "changes without the user.\nState: settled, done — h, t: removed")),
                   ("an entry with no State line", FILE_TEXT.replace("changes without the user.\nState: open\n",
                                                                     "changes without the user.\n"))):
    path = fresh(text)
    code, _, err = run(path, *RULING, "--state", "open")
    case(f"a ruling on {name} is refused", code == 1 and "REFUSED:" in err and "does not need the user" in err
         and path.read_text(encoding="utf-8") == text)
for option, value, expected in (("--words", "", "is empty"), ("--words", " ", "is empty"),
                                ("--words", "keep it\nState: settled", "line break"),
                                ("--where", "", "is empty"), ("--where", "walk\nitem 3", "line break")):
    path = fresh(WAITING_TEXT)
    arguments = list(RULING)
    arguments[arguments.index(option) + 1] = value
    code, _, err = run(path, *arguments, "--state", "open")
    case(f"a ruling with {option} {value!r} is refused", code == 1 and expected in err
         and path.read_text(encoding="utf-8") == WAITING_TEXT)

# The attempt count restarts at the line the user-ruling subcommand writes.
path = fresh()
for number in range(3):
    run(path, "attempt", "E1", "--by", "h", "--found", f"attempt {number}", "--outcome", "not-worth-doing", "--source", "PR 5")
run(path, "needs-the-user", "E1", "--because", "three-attempts", "--by", "h", "--why", "decide x")
code, out, _ = run(path, *RULING, "--state", "open")
case("after a ruling, show counts no attempts", code == 0 and "E1: State: open; attempts since the user last decided: 0 of 3" in out)
code, _, _ = run(path, "attempt", "E1", "--by", "h", "--found", "after the ruling", "--outcome", "not-worth-doing", "--source", "PR 5")
case("an attempt after the ruling is attempt 1", code == 0
     and entry(path, "E1")[-1] == "Attempt 1 — h, 2026-11-10T12:00Z: after the ruling — sources read: PR 5")

# Show.
path = fresh()
code, out, _ = run(path, "show")
case("show lists each entry", code == 0 and out.startswith("E1: State: open; attempts since the user last decided: 0 of 3; last verdict: none"))

# Show given a GHI-MD's name: every file named after it in the log-store, with or without its GHI number.
store = Path(tempfile.mkdtemp())
for name in ("1058-daily-x-proposed-improvements-or-changes-ghi-guide-agent-2026-10-19.md",
             "1058-daily-x-proposed-improvements-or-changes-ghi-guide-agent-2026-10-19-2.md",
             "daily-x-proposed-improvements-or-changes-ghi-guide-agent-2026-10-01.md",
             "1058-daily-x-y-proposed-improvements-or-changes-ghi-guide-agent-2026-10-19.md",
             "999-daily-x-proposed-improvements-or-changes-ghi-guide-agent-2026-10-19.md",
             "1058-daily-x-proposed-improvements-or-changes-ghi-guide-agent-2026-10-19.txt"):
    (store / name).write_text(FILE_TEXT, encoding="utf-8")


def show_by_name(name, hostname="ned-box", directory=store):
    with mock.patch.object(PROGRAM.socket, "gethostname", return_value=hostname), \
            mock.patch.object(PROGRAM, "GHI_GUIDE_AGENT_LOG_STORE_DIRECTORY", str(directory)):
        return run(name, "show")


code, out, _ = show_by_name("1058-daily-x")
shown = [line for line in out.splitlines() if line.startswith("nedlern@ned-box:")]
case("show by name shows the GHI-MD's files, -2 and unnumbered ones included, and no other file", code == 0 and shown == [
    f"nedlern@ned-box:{store}/1058-daily-x-proposed-improvements-or-changes-ghi-guide-agent-2026-10-19-2.md",
    f"nedlern@ned-box:{store}/1058-daily-x-proposed-improvements-or-changes-ghi-guide-agent-2026-10-19.md",
    f"nedlern@ned-box:{store}/daily-x-proposed-improvements-or-changes-ghi-guide-agent-2026-10-01.md"])
case("show by name shows each file's entries under its path",
     out.count("E1: State: open; attempts since the user last decided: 0 of 3") == 3)
code, out, err = show_by_name("daily-x")
case("show by a name with no GHI number that files of two GHIs carry is refused, naming both numbers",
     code == 1 and "REFUSED:" in err and "GHIs 999, 1058" in err and "nedlern@ned-box:" not in out)
one_ghi = Path(tempfile.mkdtemp())
for name in ("1058-daily-x-proposed-improvements-or-changes-ghi-guide-agent-2026-10-19.md",
             "daily-x-proposed-improvements-or-changes-ghi-guide-agent-2026-10-01.md"):
    (one_ghi / name).write_text(FILE_TEXT, encoding="utf-8")
code, out, _ = show_by_name("daily-x", directory=one_ghi)
case("show by a name with no GHI number shows the one GHI's numbered files and the unnumbered ones",
     code == 0 and sum(line.startswith("nedlern@ned-box:") for line in out.splitlines()) == 2)
code, _, err = show_by_name("1058-nothing-here")
case("show by a name no file has is refused", code == 1 and "REFUSED:" in err and "No file in" in err)
code, _, err = show_by_name("1058-daily-x", directory=store / "missing")
case("show by name with a log-store directory that cannot be listed fails",
     code == 1 and "FAILED:" in err and "could not be listed" in err)
unreadable = Path(tempfile.mkdtemp())
(unreadable / "1058-daily-x-proposed-improvements-or-changes-ghi-guide-agent-2026-10-19.md").mkdir()
code, _, err = show_by_name("1058-daily-x", directory=unreadable)
case("show by name with a file that cannot be read fails", code == 1 and "FAILED:" in err and "could not be read" in err)
code, _, err = show_by_name("1058-daily-x", hostname="ned-mac.local")
case("show by name off ned-box is refused, with the ssh command",
     code == 1 and "ssh nedlern@ned-box " in err and shlex.split(shlex.split(err.strip().splitlines()[-1])[2])[-2:] == ["show", "1058-daily-x"])

# The log-store form of a path.
with mock.patch.object(PROGRAM.socket, "gethostname", return_value="ned-mac.local"):
    code, _, err = run("nedlern@ned-box:/home/nedlern/x.md", "attempt", "E1", "--by", "h", "--found", "the ruling's words", "--outcome", "not-worth-doing", "--source", "PR 5")
case("the log-store form is refused off ned-box, with the ssh command",
     code == 1 and "ssh nedlern@ned-box " in err)
command_line = err.strip().splitlines()[-1]
case("the ssh command carries the arguments, quoted",
     shlex.split(shlex.split(command_line)[2])[-11:]
     == ["attempt", "nedlern@ned-box:/home/nedlern/x.md", "E1", "--by", "h", "--found", "the ruling's words", "--outcome", "not-worth-doing", "--source", "PR 5"])
path = fresh()
with mock.patch.object(PROGRAM.socket, "gethostname", return_value="ned-box"):
    code, out, _ = run(f"nedlern@ned-box:{path}", "show")
case("the log-store form is a local path on ned-box", code == 0 and out.startswith("E1:"))

# A change keeps the file's mode.
path = fresh()
os.chmod(path, 0o644)
run(path, "attempt", "E1", "--by", "h", "--found", "x", "--outcome", "not-worth-doing", "--source", "PR 5")
case("a change keeps the file's mode", (path.stat().st_mode & 0o777) == 0o644)

# A file that cannot be read, and a write that fails, leave the file as it was.
code, _, err = run(Path(tempfile.mkdtemp()) / "missing.md", "show")
case("a missing file exits 1", code == 1 and "FAILED:" in err)
code, _, err = run("missing-proposed-improvements-or-changes-ghi-guide-agent-2026-11-10.md", "show")
case("a file named without a directory is read as a file, not a GHI-MD's name",
     code == 1 and "could not be read or written" in err)
path = fresh()
with mock.patch.object(PROGRAM.os, "replace", side_effect=OSError("disk full")):
    code, _, err = run(path, "attempt", "E1", "--by", "h", "--found", "x", "--outcome", "not-worth-doing", "--source", "PR 5")
case("a failed write exits 1", code == 1 and "disk full" in err)
case("a failed write leaves the file as it was", path.read_text(encoding="utf-8") == FILE_TEXT)
case("a failed write leaves no temporary file", sorted(os.listdir(path.parent)) == [path.name])

# Each entry marked as needing the user gets a user-alert naming the agent-seat of the agent-home this
# agent-session was launched in; a change that marks none writes none.
pending_alerts()
path = fresh()
code, _, _ = run(path, "needs-the-user", "E2", "--because", "user-ruling-change", "--by", "h", "--why", "decide y")
alerts = pending_alerts()
case("needs-the-user writes one user-alert naming the agent-seat", code == 0 and len(alerts) == 1
     and alerts[0]["claiming_agent_seat_name"] == TEST_SEAT)
case("the user-alert names the file, the entry and its State line", alerts[0]["alert_text"] == (
    f"nedlern@ned-box:{path.resolve()}, entry E2: State: needs the user — h, 2026-11-10T12:00Z: "
    "a question whether a user-ruling should change; decide y") and "E2" in alerts[0]["title"])
path = fresh()
for number in range(3):
    code, _, _ = run(path, "attempt", "E1", "E2", "--by", "h", "--found", f"one cause {number}", "--outcome", "left-open", "--source", "PR 5")
alerts = pending_alerts()
case("a third left-open attempt on two entries writes a user-alert for each",
     code == 0 and sorted(alert["alert_text"].split(", entry ")[1][:2] for alert in alerts) == ["E1", "E2"])
path = fresh()
for number in range(3):
    run(path, "attempt", "E1", "--by", "h", "--found", f"attempt {number}", "--outcome", "not-worth-doing", "--source", "PR 5")
    second_agent_answers(DISAGREES)
    run(path, *VERDICT)
alerts = pending_alerts()
case("a disagreement on the third attempt writes one user-alert", len(alerts) == 1 and "entry E1: State: needs the user" in alerts[0]["alert_text"])
path = fresh(UPSTREAM_TEXT)
run(path, "attempt", "E2", "--by", "h", "--found", "x", "--outcome", "left-open", "--source", "PR 5")
run(path, "settle", "E2", "--kind", "done", "--by", "h", "--how", "PR 8")
case("an attempt and a settle that mark nothing write no user-alert", pending_alerts() == [])

# Launched in no agent-home, such as through ssh, the alert names no agent-seat; launched in a directory of
# ~/agents that is no agent-home, the change is refused before anything is written.
for name, launched_in in (("with no launch directory", None), ("launched outside ~/agents", str(TEST_HOME / "Projects" / "x"))):
    path = fresh()
    with mock.patch.dict(os.environ, {LAUNCHED_IN: launched_in} if launched_in else {}):
        if launched_in is None:
            os.environ.pop(LAUNCHED_IN)
        code, _, _ = run(path, "needs-the-user", "E2", "--because", "user-ruling-change", "--by", "h", "--why", "y")
    alerts = pending_alerts()
    case(f"{name}, the user-alert names no agent-seat",
         code == 0 and len(alerts) == 1 and alerts[0]["claiming_agent_seat_name"] is None)
path = fresh()
with mock.patch.dict(os.environ, {LAUNCHED_IN: str(TEST_HOME / "agents" / "no-such-seat")}):
    code, _, err = run(path, "needs-the-user", "E2", "--because", "user-ruling-change", "--by", "h", "--why", "y")
case("launched in a directory of ~/agents that is no agent-home, needs-the-user is refused and changes nothing",
     code == 1 and "REFUSED:" in err and "not an agent-home" in err and path.read_text(encoding="utf-8") == FILE_TEXT
     and pending_alerts() == [])
with mock.patch.dict(os.environ, {LAUNCHED_IN: str(TEST_HOME / "agents" / "no-such-seat")}):
    code, _, _ = run(path, "settle", "E2", "--kind", "done", "--by", "h", "--how", "PR 8")
case("a settle, which marks no entry, does not need an agent-home", code == 0)

# A user-alert that cannot be written fails after the file is changed, and says so.
path = fresh()
with mock.patch.object(PROGRAM.user_alerts, "user_alert_write_to_pending", side_effect=OSError("disk full")):
    code, out, err = run(path, "needs-the-user", "E2", "--because", "user-ruling-change", "--by", "h", "--why", "y")
case("a user-alert that cannot be written exits 1 with FAILED: naming the entry", code == 1 and "FAILED: entry E2 was marked" in err
     and "disk full" in err and "brings each such entry to the user itself" in err)
case("a user-alert that cannot be written leaves the entry marked", entry(path, "E2")[-1].startswith("State: needs the user"))

# The second agent's prompt file exists.
root = HERE.parent
case("the second agent's prompt exists", (root / PROGRAM.SECOND_AGENT_PROMPT).is_file())

# Other programs may write real alerts meanwhile, so only an alert of this program's counts.
case("no case wrote into the user's own pending alerts", not any(
    "proposed-improvements-or-changes-file needs the user" in (REAL_PENDING_ALERTS / name).read_text(encoding="utf-8")
    for name in (set(os.listdir(REAL_PENDING_ALERTS)) - set(REAL_PENDING_BEFORE) if REAL_PENDING_ALERTS.is_dir() else ())))
print(f"{case_count - len(failures)} of {case_count} cases passed")
raise SystemExit(1 if failures else 0)
