#!/usr/bin/env python3
"""PreToolUse hook on Bash: run each run_in_background command under coreutils `timeout`.

The bound is the wait-limit of the command's kind, from the table in
scripts/handoff-context-threshold-hook.py, whose classifier this hook shares. A waiting-task,
whose wait-limit is 0 so that it never holds back a session-handoff, is bounded at
WAITING_TASK_KIND_BOUND_TIMEOUT_MINUTES instead. A command that names a program in
PROGRAMS_THAT_ENFORCE_THEIR_OWN_TIME_LIMITS runs as it is: such a program may wait to start
for CPU, and `timeout` would count that wait.

When `timeout` stops the command, its output ends with the stop message, and, when the command
holds `gh pr view <number>`, with the line that says how to wait for a pull request instead.

Claude Code's background_tasks list shows the rewritten command, while the transcript keeps the
original, so the threshold hook unwraps a command before it classifies it."""

import importlib.util
import json
import re
import shlex
import shutil
import socket
import sys
from pathlib import Path, PurePosixPath

WAITING_TASK_KIND_BOUND_TIMEOUT_MINUTES = 75.0
PROGRAMS_THAT_ENFORCE_THEIR_OWN_TIME_LIMITS = (
    "scripts/run-all-test-suites.py",
    "nn-systems/cold-read/cold-read-grid.py",
)
UNMATCHED_KIND_NAME = "unmatched"
STOP_MESSAGE = (
    "This background command was stopped after {minutes} minutes, its bound for kind {kind}. "
    "It is stuck or slower than its kind allows; find why before you run it again.")
PULL_REQUEST_WAIT_MESSAGE = (
    "To wait for a pull request, use TaskUpdate to give the task on your task list that waits "
    'for it the metadata {{"prerequisites": [{{"pr_merged": {number}}}]}} instead.')
GH_PR_VIEW_NUMBER_PATTERN = re.compile(r"\bgh[ \t]+pr[ \t]+view[ \t]+#?(\d+)\b")
TIMEOUT_PROGRAM = "timeout"
# coreutils `timeout` exits 124 when the bound stopped the command.
TIMEOUT_STOPPED_EXIT_STATUS = 124
_WRAPPER_PREFIX_PATTERN = re.compile(r"timeout [0-9.]+s bash -c ")
# A space before the ";" keeps the quoted command one whitespace-split token.
_WRAPPER_TAIL_START = ' ; status=$?; if [ "$status" -eq ' + str(TIMEOUT_STOPPED_EXIT_STATUS) + " ]; then printf "
TIMEOUT_PROGRAM_MISSING_MESSAGE = (
    "background-bash-command-kind-bound-timeout-wrap-hook: coreutils `timeout` is not on PATH on "
    "{machine}, so this background command runs with no bound, and nothing stops it if it is stuck.\n"
    "Stop it yourself with TaskStop if it is still running after {minutes} minutes, its bound for "
    "kind {kind}.\n"
    "Tell the user, once in this agent-session: \"Background commands on {machine} run with no time "
    "bound, because coreutils `timeout` is not installed there.\"\n"
    "If you are a subagent, pass that sentence to the agent that dispatched you instead.")


def background_bash_command_text_wrapped_in_kind_bound_timeout_with_stop_message(command: str, bound_minutes: float,
                                                          kind: str) -> str:
    """Return the shell command that runs `command` under `timeout` at bound_minutes and, when the
    bound stops it, prints the stop message; it keeps the command's exit status."""
    lines = [STOP_MESSAGE.format(minutes=f"{bound_minutes:g}", kind=kind)]
    pull_request = GH_PR_VIEW_NUMBER_PATTERN.search(command)
    if pull_request:
        lines.append(PULL_REQUEST_WAIT_MESSAGE.format(number=pull_request.group(1)))
    printed = " ".join(shlex.quote(line) for line in lines)
    # `(exit ...)`, not `exit`: the shell that runs this may have more to run after it.
    return (f"timeout {bound_minutes * 60:g}s bash -c {shlex.quote(command)}"
            f"{_WRAPPER_TAIL_START}'%s\\n' {printed}; fi; (exit \"$status\")")


def background_bash_command_unwrapped_from_kind_bound_timeout(command):
    """Return the command a wrapped command runs, or the command itself when it is not wrapped."""
    if not isinstance(command, str) or not _WRAPPER_PREFIX_PATTERN.match(command):
        return command
    rest = command[_WRAPPER_PREFIX_PATTERN.match(command).end():]
    lexer = shlex.shlex(rest, posix=True)
    lexer.whitespace_split = True
    try:
        inner = lexer.get_token()
    except ValueError:
        return command
    if inner is None or not rest[len(shlex.quote(inner)):].startswith(_WRAPPER_TAIL_START):
        return command
    return inner


def names_a_program_that_enforces_its_own_time_limits(command: str) -> bool:
    return any(re.search(r"(?<![\w.-])" + re.escape(PurePosixPath(program).name) + r"(?![\w.-])",
                         command)
               for program in PROGRAMS_THAT_ENFORCE_THEIR_OWN_TIME_LIMITS)


def _threshold_hook():
    # Loaded only here: the threshold hook loads this module, so a load at import would be a cycle.
    specification = importlib.util.spec_from_file_location(
        "handoff_context_threshold_hook",
        Path(__file__).resolve().with_name("handoff-context-threshold-hook.py"))
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def kind_and_bound_minutes(command: str) -> tuple:
    threshold_hook = _threshold_hook()
    kind, wait_limit_minutes = threshold_hook.background_task_kind_and_wait_limit_minutes_from_command(
        command)
    if kind == threshold_hook.BACKGROUND_TASK_KIND_WHEN_NO_KIND_MATCHES:
        kind = UNMATCHED_KIND_NAME
    return kind, (WAITING_TASK_KIND_BOUND_TIMEOUT_MINUTES if wait_limit_minutes <= 0 else wait_limit_minutes)


def main() -> int:
    payload = json.load(sys.stdin)
    tool_input = payload.get("tool_input") if isinstance(payload, dict) else None
    if not isinstance(tool_input, dict) or tool_input.get("run_in_background") is not True:
        return 0
    command = tool_input.get("command")
    if not isinstance(command, str) or names_a_program_that_enforces_its_own_time_limits(command):
        return 0
    kind, bound_minutes = kind_and_bound_minutes(command)
    if shutil.which(TIMEOUT_PROGRAM) is None:
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "additionalContext": TIMEOUT_PROGRAM_MISSING_MESSAGE.format(
                machine=socket.gethostname(), minutes=f"{bound_minutes:g}", kind=kind),
        }}))
        return 0
    # updatedInput replaces the whole input, so every other field is carried through.
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "updatedInput": {**tool_input, "command": background_bash_command_text_wrapped_in_kind_bound_timeout_with_stop_message(
            command, bound_minutes, kind)},
    }}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
