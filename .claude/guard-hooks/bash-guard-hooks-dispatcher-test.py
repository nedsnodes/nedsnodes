#!/usr/bin/env python3
"""Tests for .claude/guard-hooks/bash-guard-hooks-dispatcher.py, with fake guards.

Each case writes small guard files of its own and a guard list naming them, pipes a hook payload into the
dispatcher as a real process, and reads what Claude Code would be given: two refusals combined, every
listed guard run, and each failure the dispatcher handles caused for real (a guard that crashes, exits
nonzero, is killed by a signal, runs past its timeout, cannot be compiled, or prints output that cannot
be combined, and a guard list that cannot be read). One case checks that the guard list names exactly
the Bash PreToolUse hooks in .claude/settings.json, with their timeouts.

Run: python3 .claude/guard-hooks/bash-guard-hooks-dispatcher-test.py
Prints one line per case and exits non-zero if any case fails.
"""

import importlib.util
import json
import re
import shutil
import subprocess
import sys
import tempfile
import textwrap
import time
from pathlib import Path

DISPATCHER = Path(__file__).with_name("bash-guard-hooks-dispatcher.py")
REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("bash_guard_hooks_dispatcher", DISPATCHER)
dispatcher = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(dispatcher)

failures = []
SCRATCH = Path(tempfile.mkdtemp(prefix="bash-guard-hooks-dispatcher-test-"))


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


def guard(name, body):
    path = SCRATCH / f"{name}.py"
    path.write_text("import json, os, sys, time\n" + textwrap.dedent(body))
    return path


def deny_guard(name, reason, context=None, message=None):
    output = {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                     "permissionDecisionReason": reason}}
    if context:
        output["hookSpecificOutput"]["additionalContext"] = context
    if message:
        output["systemMessage"] = message
    return guard(name, f"sys.stdin.read()\nprint(json.dumps({output!r}))\n")


def dispatch(guards, command="true", extra_arguments=(), timeout=60):
    """Return (the dispatcher's completed process, its output read as JSON or None, seconds it took)."""
    list_file = SCRATCH / f"list-{time.monotonic_ns()}.json"
    list_file.write_text(json.dumps({"guards": [
        {"path": str(path), "timeout_seconds": seconds} for path, seconds in
        ((entry if isinstance(entry, tuple) else (entry, 30)) for entry in guards)]}))
    payload = json.dumps({"hook_event_name": "PreToolUse", "tool_name": "Bash", "session_id": "test",
                          "cwd": str(SCRATCH), "tool_input": {"command": command}})
    started = time.monotonic()
    completed = subprocess.run([sys.executable, str(DISPATCHER), "--guard-list-file", str(list_file),
                                *extra_arguments], input=payload, capture_output=True, text=True, timeout=timeout)
    took = time.monotonic() - started
    try:
        output = json.loads(completed.stdout) if completed.stdout.strip() else None
    except ValueError:
        output = None
    return completed, output, took


def specific(output):
    return (output or {}).get("hookSpecificOutput", {})


# ---------------------------------------------------------------- two guards refuse one command

one = deny_guard("refuses-one", "REASON ONE", context="CONTEXT ONE", message="MESSAGE ONE")
two = deny_guard("refuses-two", "REASON TWO", message="MESSAGE TWO")
silent = guard("silent", "sys.stdin.read()\n")
completed, output, _ = dispatch([one, silent, two])
check("two refusals: Claude Code is given a deny", specific(output).get("permissionDecision") == "deny",
      completed.stdout)
check("two refusals: both reasons are given, in guard-list order, a paragraph each",
      specific(output).get("permissionDecisionReason") == "REASON ONE\n\nREASON TWO", completed.stdout)
check("two refusals: the context and both system messages are kept",
      specific(output).get("additionalContext") == "CONTEXT ONE"
      and (output or {}).get("systemMessage") == "MESSAGE ONE\n\nMESSAGE TWO", completed.stdout)
check("two refusals: the dispatcher exits 0 and writes no error output",
      completed.returncode == 0 and not completed.stderr, completed.stderr)

exit_two = guard("exit-two", "sys.stdin.read()\nprint('REFUSED BY EXIT 2', file=sys.stderr)\nsys.exit(2)\n")
completed, output, _ = dispatch([exit_two, one])
check("a guard that exits 2 refuses with its error output as its reason, beside a JSON refusal",
      specific(output).get("permissionDecisionReason") == "REFUSED BY EXIT 2\n\nREASON ONE", completed.stdout)

asks = guard("asks", "sys.stdin.read()\nprint(json.dumps({'hookSpecificOutput': {'hookEventName': 'PreToolUse', "
                     "'permissionDecision': 'ask', 'permissionDecisionReason': 'ASKED'}}))\n")
completed, output, _ = dispatch([asks, two])
check("deny wins over ask, and only the refusing guard's reason is given",
      specific(output).get("permissionDecision") == "deny"
      and specific(output).get("permissionDecisionReason") == "REASON TWO", completed.stdout)
completed, output, _ = dispatch([asks, silent])
check("an ask alone is passed on with its reason",
      specific(output).get("permissionDecision") == "ask"
      and specific(output).get("permissionDecisionReason") == "ASKED", completed.stdout)

completed, _, _ = dispatch([silent, silent])
check("nothing is printed when no guard prints anything", completed.stdout == "" and completed.returncode == 0,
      repr(completed.stdout))

# ---------------------------------------------------------------- every guard runs, as __main__

runs = [guard(f"runs-{number}", f"""
    payload = json.loads(sys.stdin.read())
    seen = [__name__, os.path.basename(sys.argv[0]), os.path.basename(__file__), payload['tool_input']['command']]
    print(json.dumps({{'hookSpecificOutput': {{'hookEventName': 'PreToolUse', 'additionalContext': 'RAN {number} ' + repr(seen)}}}}))
    """) for number in range(6)]
completed, output, _ = dispatch(runs, command="echo every guard")
context = specific(output).get("additionalContext", "")
check("every listed guard runs, in guard-list order",
      [int(found) for found in re.findall(r"RAN (\d)", context)] == list(range(6)), context)
check("each guard runs as __main__, with its own file as sys.argv[0] and __file__, and the payload on its input",
      all(f"RAN {number} ['__main__', 'runs-{number}.py', 'runs-{number}.py', 'echo every guard']" in context
          for number in range(6)), context)

completed, _, _ = dispatch(runs[:3], extra_arguments=["--print-each-guard-hook-result-as-json"])
results = json.loads(completed.stdout)
check("--print-each-guard-hook-result-as-json gives one result per guard, with its output and exit status",
      [Path(result["path"]).name for result in results] == ["runs-0.py", "runs-1.py", "runs-2.py"]
      and all(result["exit_status"] == 0 and "RAN" in result["stdout"] for result in results), completed.stdout)

big_command = "echo " + "x" * 300_000
big_reader = guard("big-reader", """
    payload = json.loads(sys.stdin.read())
    sys.stderr.write('e' * 2_000_000)
    print(json.dumps({'hookSpecificOutput': {'hookEventName': 'PreToolUse', 'additionalContext': 'LENGTH ' + str(len(payload['tool_input']['command']))}}))
    """)
completed, output, took = dispatch([big_reader, big_reader], command=big_command)
check("a payload larger than a pipe holds reaches each guard whole, and 2 MB of error output does not stall it",
      specific(output).get("additionalContext") == f"LENGTH {len(big_command)}\n\nLENGTH {len(big_command)}",
      f"{completed.stdout[:300]} after {took:.1f} s")

# ---------------------------------------------------------------- each failure the dispatcher handles


def failure_notice_check(case_name, failing_guard, failure_words, timeout=30):
    completed, output, took = dispatch([one, (failing_guard, timeout)])
    context = specific(output).get("additionalContext", "")
    message = (output or {}).get("systemMessage", "")
    check(f"{case_name}: the other guard's refusal still stands",
          specific(output).get("permissionDecision") == "deny"
          and specific(output).get("permissionDecisionReason") == "REASON ONE", completed.stdout[:500])
    check(f"{case_name}: the agent is told which guard failed, how, and to check the call",
          f"The Bash guard hook {failing_guard.name} failed on" in context and failure_words in context
          and "Check whether this call is one" in context, context[:800])
    check(f"{case_name}: the user is told too", f"The Bash guard hook {failing_guard.name} failed on" in message
          and failure_words in message, message[:500])
    return took


failure_notice_check("a guard that raises", guard("raises", "sys.stdin.read()\nraise RuntimeError('BOOM')\n"),
                     "it exited 1, and its error output ends: Traceback")
failure_notice_check("a guard that exits 3", guard("exits-three", "sys.exit(3)\n"), "it exited 3")
failure_notice_check("a guard killed by a signal", guard("killed", "os.kill(os.getpid(), 9)\n"),
                     "it was killed by signal 9")
failure_notice_check("a guard that cannot be compiled", guard("syntax-error", "def (:\n"),
                     "SyntaxError")
failure_notice_check("a guard file that does not exist", SCRATCH / "missing-guard.py", "FileNotFoundError")
took = failure_notice_check("a guard that runs past its timeout", guard("hangs", "time.sleep(60)\n"),
                            "it ran past its timeout of 0.5 seconds and was stopped", timeout=0.5)
check("a guard that runs past its timeout is stopped at its timeout, not waited for", took < 10, f"{took:.1f} s")
grandchild = guard("grandchild-holds-output", """
    import subprocess
    subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(4)'])
    """)
took = failure_notice_check("a guard whose child keeps its output open past the timeout", grandchild,
                            "ran past its timeout of 1 seconds", timeout=1)
check("a guard whose child keeps its output open is stopped at its timeout", took < 10, f"{took:.1f} s")
failure_notice_check("a guard that prints text that is not JSON", guard("prints-text", "print('hello')\n"),
                     "it printed output that is not PreToolUse hook JSON this dispatcher combines")
failure_notice_check("a guard that prints JSON with a key the dispatcher does not combine",
                     guard("prints-continue", "print(json.dumps({'continue': False}))\n"),
                     "it has the keys ['continue']")
failure_notice_check("a guard that prints JSON for another hook event",
                     guard("prints-other-event", "print(json.dumps({'hookSpecificOutput': "
                                                 "{'hookEventName': 'PostToolUse', 'additionalContext': 'x'}}))\n"),
                     "its hookEventName is 'PostToolUse'")

list_file = SCRATCH / "not-json-list.json"
list_file.write_text("not json")
completed = subprocess.run([sys.executable, str(DISPATCHER), "--guard-list-file", str(list_file)],
                           input="{}", capture_output=True, text=True, timeout=60)
check("a guard list that cannot be read lets the call go ahead with the crash notice, exit 0",
      completed.returncode == 0 and "BashGuardHooksDispatcherGuardListUnreadable" in completed.stdout
      and "crashed" in completed.stdout, completed.stdout + completed.stderr)
for entries, case_name in ((json.dumps({"guards": []}), "an empty guard list"),
                           (json.dumps({"guards": [{"path": "x.py", "timeout_seconds": 0}]}),
                            "a guard list entry whose timeout is not above 0"),
                           (json.dumps({"guards": [{"timeout_seconds": 3}]}), "a guard list entry without a path")):
    list_file.write_text(entries)
    try:
        dispatcher.bash_guard_hooks_dispatcher_guard_list_read(list_file)
        check(f"{case_name} is refused", False, "no BashGuardHooksDispatcherGuardListUnreadable raised")
    except dispatcher.BashGuardHooksDispatcherGuardListUnreadable as error:
        check(f"{case_name} is refused", True, str(error))

# ---------------------------------------------------------------- the guard list is the settings' Bash hooks


def settings_bash_hooks():
    settings = json.loads((REPOSITORY_ROOT / ".claude" / "settings.json").read_text())
    hooks = []
    for entry in settings["hooks"]["PreToolUse"]:
        matcher = entry.get("matcher") or "*"
        if matcher != "*" and not re.fullmatch(matcher, "Bash"):
            continue
        for hook in entry["hooks"]:
            path = re.search(r'"\$CLAUDE_PROJECT_DIR"/(\S+)', hook["command"]).group(1)
            hooks.append((path, hook.get("timeout", 60)))
    return hooks


listed = dispatcher.bash_guard_hooks_dispatcher_guard_list_read()
check("the guard list names exactly the Bash PreToolUse hooks in .claude/settings.json, in order, with their "
      "timeouts", listed == settings_bash_hooks(), f"list {listed}\nsettings {settings_bash_hooks()}")
check("every guard in the guard list exists", all((REPOSITORY_ROOT / path).is_file() for path, _ in listed),
      [path for path, _ in listed if not (REPOSITORY_ROOT / path).is_file()])

shutil.rmtree(SCRATCH, ignore_errors=True)
if failures:
    print(f"\n{len(failures)} case(s) failed: {failures}")
    sys.exit(1)
print("\nAll cases passed.")
