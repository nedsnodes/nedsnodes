#!/usr/bin/env python3
"""Run every Bash guard hook on one Bash tool call, each in a child forked from one process that imported their libraries.

Claude Code runs this one PreToolUse hook on a Bash call in place of one Python process per guard. It
reads the hook payload, imports the libraries the guards use, tree-sitter-bash above all, once, then
forks one child process per guard in the guard list, bash-guard-hooks-dispatcher-guard-list.json beside
this file. Each child runs its guard's file unchanged as __main__, as `python3 <guard file>` would, with
the payload on its standard input, so a guard's crash, exit or hang stays in its own child; the children
run at the same time.

Claude Code is given one hook output that combines every guard's, in guard-list order:
- permissionDecision: the strictest any guard gave, deny over ask over allow, with the reason of every
  guard that gave it, each in a paragraph of its own. Claude Code, given two hooks that refuse, shows
  the agent only one of the two reasons.
- additionalContext and systemMessage: every guard's, each in a paragraph of its own.
- A guard that exits 2 refuses, with its standard error as its reason, as Claude Code reads exit 2.
- A guard that runs past its timeout, exits with a status other than 0 or 2, is killed by a signal, or
  prints output that is not PreToolUse hook JSON this program combines lets the call go ahead, and the
  agent and the user are told which guard failed and how, as the guards' own crash notice tells them.
Nothing is printed when no guard printed anything to combine. A crash of this program itself lets the
call go ahead unchecked, with the crash notice.

--print-each-guard-hook-result-as-json prints each guard's standard output, standard error and exit status as JSON
instead of the combined hook output, for the test that compares them with each guard run alone.
--guard-list-file <path> reads another guard list, for tests.
"""

# Deferred annotations let the hook load on the Mac's system Python 3.9.
from __future__ import annotations

import builtins
import importlib.machinery
import importlib.util
import io
import json
import os
import selectors
import signal
import socket
import sys
import tempfile
import time
import traceback
import types
from pathlib import Path

_crash_notice_spec = importlib.util.spec_from_file_location(
    "guard_hook_crash_fail_open_with_notice_common",
    Path(__file__).resolve().parent / "guard-hook-crash-fail-open-with-notice-common.py")
_crash_notice = importlib.util.module_from_spec(_crash_notice_spec)
_crash_notice_spec.loader.exec_module(_crash_notice)

BASH_GUARD_HOOKS_DISPATCHER_GUARD_LIST_FILE = (
    Path(__file__).resolve().parent / "bash-guard-hooks-dispatcher-guard-list.json")

# Imported once here, so no child spends time importing them. Importing them is most of a guard's start;
# loading the guards' own shared modules here as well saved no measurable time, so each guard loads those.
PRELOADED_LIBRARY_MODULES = ("tree_sitter", "tree_sitter_bash", "subprocess", "shlex", "threading", "glob",
                             "fcntl", "contextlib", "re", "bisect", "codecs", "collections", "functools")

PRINT_EACH_GUARD_HOOK_RESULT_AS_JSON_COMMAND_LINE_FLAG = "--print-each-guard-hook-result-as-json"
GUARD_LIST_FILE_OPTION = "--guard-list-file"
PERMISSION_DECISIONS_STRICTEST_FIRST = ("deny", "ask", "allow")
HOOK_OUTPUT_KEYS_COMBINED = {"hookSpecificOutput", "systemMessage"}
HOOK_SPECIFIC_OUTPUT_KEYS_COMBINED = {"hookEventName", "permissionDecision", "permissionDecisionReason",
                                      "additionalContext"}
READ_CHUNK_BYTES = 65536
# How often a child that closed its output but has not exited is looked at again.
EXIT_POLL_SECONDS = 0.002
OUTPUT_CHARACTERS_QUOTED = 1000

GUARD_FAILED_AGENT_NOTICE = (
    "The Bash guard hook {guard_name} failed on {host} ({failure}), so this tool call went ahead without "
    "being checked by it, and the call has run; the other Bash guards checked it as usual. A failed guard "
    "lets the call go ahead so that the failure does not stop work; the user has been shown that the guard "
    "failed.\n"
    "Check whether this call is one {guard_name} would have refused; the docstring at the top of "
    "{guard_file} says which calls it refuses.\n"
    "If it is, or you cannot tell, report what the call did and ask whether to undo it: a subagent asks the "
    "agent that dispatched it, any other agent asks the user. Do not undo the call before you have the "
    "answer, because an undo can do further damage.\n"
    "If it is not, go on with your task.")
GUARD_FAILED_USER_NOTICE = (
    "The Bash guard hook {guard_name} failed on {host} and let a tool call through unchecked ({failure}). "
    "The agent has been told to check what the call did.")
TIMED_OUT_FAILURE = "it ran past its timeout of {timeout} seconds and was stopped"
EXIT_STATUS_FAILURE = "it exited {status}{error_output}"
KILLED_BY_SIGNAL_FAILURE = "it was killed by signal {signal}{error_output}"
OUTPUT_NOT_COMBINED_FAILURE = ("it printed output that is not PreToolUse hook JSON this dispatcher combines "
                               "({problem}): {output}")
ERROR_OUTPUT_ENDING = ", and its error output ends: {text}"
GUARD_LIST_FIX_LINE = (
    "make the file hold {\"guards\": [{\"path\": <guard file, relative to the repository root>, "
    "\"timeout_seconds\": <seconds, a number above 0>}, ...]}, one entry per guard, as on main, "
    "where git show origin/main:.claude/guard-hooks/bash-guard-hooks-dispatcher-guard-list.json prints it")


class BashGuardHooksDispatcherGuardListUnreadable(Exception):
    """The guard list file cannot be read, is not JSON, or holds an entry that is not a guard path and timeout."""


def bash_guard_hooks_dispatcher_guard_list_read(list_path=BASH_GUARD_HOOKS_DISPATCHER_GUARD_LIST_FILE):
    """Return [(guard file path, timeout in seconds)] from the guard list file, in its order.

    A path is relative to the repository root, unless it is absolute.
    """
    try:
        entries = json.loads(Path(list_path).read_text(encoding="utf-8"))["guards"]
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise BashGuardHooksDispatcherGuardListUnreadable(
            f"the Bash guard hooks dispatcher's guard list {list_path}, which names the guard files it runs, cannot "
            f"be read ({error!r}), so no Bash guard checked this call; " + GUARD_LIST_FIX_LINE) from error
    if not isinstance(entries, list) or not entries:
        raise BashGuardHooksDispatcherGuardListUnreadable(
            f"the Bash guard hooks dispatcher's guard list {list_path} holds no list of guards under \"guards\", "
            "so no Bash guard checked this call; " + GUARD_LIST_FIX_LINE)
    guards = []
    for entry in entries:
        path = entry.get("path") if isinstance(entry, dict) else None
        timeout = entry.get("timeout_seconds") if isinstance(entry, dict) else None
        if not isinstance(path, str) or not path or isinstance(timeout, bool) \
                or not isinstance(timeout, (int, float)) or timeout <= 0:
            raise BashGuardHooksDispatcherGuardListUnreadable(
                f"the Bash guard hooks dispatcher's guard list {list_path} holds the entry {entry!r}, so no Bash "
                "guard checked this call; " + GUARD_LIST_FIX_LINE)
        guards.append((path, timeout))
    return guards


def _library_modules_preloaded():
    for name in PRELOADED_LIBRARY_MODULES:
        try:
            importlib.import_module(name)
        except ImportError:
            pass  # The shell reader installs tree-sitter-bash, or says it cannot, in each child that needs it.


def _guard_file_run_as_main_then_exit(guard_file, payload, output_descriptor, error_descriptor, descriptors_to_close):
    """In a forked child: run guard_file as `python3 guard_file` would, with payload as its input, then exit."""
    status = 1
    try:
        for descriptor in descriptors_to_close:
            os.close(descriptor)
        os.dup2(output_descriptor, 1)
        os.dup2(error_descriptor, 2)
        os.close(output_descriptor)
        os.close(error_descriptor)
        # A file, not a pipe: a payload larger than a pipe holds would block the writer.
        with tempfile.TemporaryFile() as payload_file:
            payload_file.write(payload)
            payload_file.flush()
            payload_file.seek(0)
            os.dup2(payload_file.fileno(), 0)
        sys.stdin = io.TextIOWrapper(io.BufferedReader(io.FileIO(0, "r", closefd=False)),
                                     encoding=sys.stdin.encoding, errors=sys.stdin.errors)
        main_module = types.ModuleType("__main__")
        main_module.__file__ = guard_file
        main_module.__builtins__ = builtins
        main_module.__loader__ = importlib.machinery.SourceFileLoader("__main__", guard_file)
        sys.modules["__main__"] = main_module
        sys.argv = [guard_file]
        sys.path[0] = os.path.dirname(os.path.realpath(guard_file))
        with open(guard_file, "rb") as source:
            code = compile(source.read(), guard_file, "exec", dont_inherit=True)
        try:
            exec(code, main_module.__dict__)
            status = 0
        except SystemExit as stop:
            if stop.code is None:
                status = 0
            elif isinstance(stop.code, int):
                status = stop.code & 0xFF
            else:
                print(stop.code, file=sys.stderr)
                status = 1
    except BaseException:
        traceback.print_exc()
        status = 1
    finally:
        for stream in (sys.stdout, sys.stderr):
            try:
                stream.flush()
            except Exception:
                status = status or 120  # The status Python exits with when it cannot flush its output.
        os._exit(status)


class _Child:
    def __init__(self, path, timeout, pid, output_descriptor, error_descriptor, started):
        self.path, self.timeout, self.pid = path, timeout, pid
        self.descriptors = {output_descriptor: bytearray(), error_descriptor: bytearray()}
        self.output_descriptor, self.error_descriptor = output_descriptor, error_descriptor
        self.deadline = started + timeout
        self.wait_status, self.timed_out, self.closed = None, False, set()

    def result(self):
        exit_status = signal_number = None
        if self.wait_status is not None and os.WIFSIGNALED(self.wait_status):
            signal_number = os.WTERMSIG(self.wait_status)
        elif self.wait_status is not None:
            exit_status = os.WEXITSTATUS(self.wait_status)
        return {"path": self.path, "timeout_seconds": self.timeout,
                "stdout": bytes(self.descriptors[self.output_descriptor]).decode("utf-8", "replace"),
                "stderr": bytes(self.descriptors[self.error_descriptor]).decode("utf-8", "replace"),
                "exit_status": None if self.timed_out else exit_status,
                "signal": None if self.timed_out else signal_number,
                "timed_out": self.timed_out}


def bash_guard_hook_results_from_one_forked_child_each(guards, payload, repository_root, clock=time.monotonic):
    """Run each guard of [(path, timeout seconds)] in a child of its own, all at once, and return their results.

    Each result is {"path", "timeout_seconds", "stdout", "stderr", "exit_status", "signal", "timed_out"}, in
    the order of guards. A guard is done when its output and error output are closed and it has exited, as
    Claude Code waits for a hook's; one still not done at its timeout is killed and is timed_out.
    """
    sys.stdout.flush()
    sys.stderr.flush()
    children, parent_descriptors = [], []
    for path, timeout in guards:
        output_read, output_write = os.pipe()
        error_read, error_write = os.pipe()
        pid = os.fork()
        if pid == 0:
            _guard_file_run_as_main_then_exit(os.path.join(repository_root, path), payload, output_write,
                                              error_write, parent_descriptors + [output_read, error_read])
        os.close(output_write)
        os.close(error_write)
        parent_descriptors += [output_read, error_read]
        children.append(_Child(path, timeout, pid, output_read, error_read, clock()))
    selector = selectors.DefaultSelector()
    for child in children:
        for descriptor in child.descriptors:
            os.set_blocking(descriptor, False)
            selector.register(descriptor, selectors.EVENT_READ, child)
    pending = list(children)
    try:
        while pending:
            closed_but_running = [child for child in pending if not child.descriptors.keys() - child.closed]
            wait = min(child.deadline for child in pending) - clock()
            if closed_but_running:
                wait = min(wait, EXIT_POLL_SECONDS)
            for key, _ in (selector.select(max(0.0, wait)) if selector.get_map() else _sleep(max(0.0, wait))):
                _read_or_close(selector, key.fileobj, key.data)
            for child in list(pending):
                if _done(child):
                    pending.remove(child)
                elif clock() >= child.deadline:
                    # Output that came, and an exit, since the last look still count: only a guard still
                    # running is timed out.
                    _ready_output_read(selector, child)
                    if not _done(child):
                        _kill_and_reap(selector, child)
                    pending.remove(child)
    finally:
        for child in pending:
            _kill_and_reap(selector, child)
        selector.close()
    return [child.result() for child in children]


def _done(child):
    """Return whether child's output and error output are closed and it has exited, reaping it if so."""
    if child.descriptors.keys() - child.closed:
        return False
    reaped, wait_status = os.waitpid(child.pid, os.WNOHANG)
    if reaped:
        child.wait_status = wait_status
    return bool(reaped)


def _read_or_close(selector, descriptor, child):
    """Read what descriptor has waiting, or close it at its end; return whether anything was read."""
    try:
        data = os.read(descriptor, READ_CHUNK_BYTES)
    except BlockingIOError:
        return False
    if data:
        child.descriptors[descriptor] += data
        return True
    selector.unregister(descriptor)
    os.close(descriptor)
    child.closed.add(descriptor)
    return False


def _ready_output_read(selector, child):
    for descriptor in child.descriptors.keys() - child.closed:
        while _read_or_close(selector, descriptor, child):
            pass


def _kill_and_reap(selector, child):
    child.timed_out = True
    try:
        os.kill(child.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    for descriptor in child.descriptors.keys() - child.closed:
        selector.unregister(descriptor)
        os.close(descriptor)
        child.closed.add(descriptor)
    os.waitpid(child.pid, 0)


def _sleep(seconds):
    time.sleep(seconds)
    return []


def _ending(text):
    text = text.strip()
    return text if len(text) <= OUTPUT_CHARACTERS_QUOTED else "..." + text[-OUTPUT_CHARACTERS_QUOTED:]


def _failure(result):
    """Return how a guard failed, or None when it did not."""
    error_output = ERROR_OUTPUT_ENDING.format(text=_ending(result["stderr"])) if result["stderr"].strip() else ""
    if result["timed_out"]:
        return TIMED_OUT_FAILURE.format(timeout=result["timeout_seconds"])
    if result["signal"] is not None:
        return KILLED_BY_SIGNAL_FAILURE.format(signal=result["signal"], error_output=error_output)
    if result["exit_status"] not in (0, 2):
        return EXIT_STATUS_FAILURE.format(status=result["exit_status"], error_output=error_output)
    return None


def _hook_output_parts(stdout):
    """Return (decision, reason, context, system message) from a guard's printed hook JSON, or raise ValueError."""
    output = json.loads(stdout)
    if not isinstance(output, dict):
        raise ValueError("it is not a JSON object")
    if output.keys() - HOOK_OUTPUT_KEYS_COMBINED:
        raise ValueError(f"it has the keys {sorted(output.keys() - HOOK_OUTPUT_KEYS_COMBINED)}")
    specific = output.get("hookSpecificOutput", {})
    if not isinstance(specific, dict):
        raise ValueError("its hookSpecificOutput is not a JSON object")
    if specific.keys() - HOOK_SPECIFIC_OUTPUT_KEYS_COMBINED:
        raise ValueError(f"its hookSpecificOutput has the keys "
                         f"{sorted(specific.keys() - HOOK_SPECIFIC_OUTPUT_KEYS_COMBINED)}")
    if specific.get("hookEventName", "PreToolUse") != "PreToolUse":
        raise ValueError(f"its hookEventName is {specific['hookEventName']!r}")
    decision = specific.get("permissionDecision")
    if decision is not None and decision not in PERMISSION_DECISIONS_STRICTEST_FIRST:
        raise ValueError(f"its permissionDecision is {decision!r}")
    texts = (specific.get("permissionDecisionReason"), specific.get("additionalContext"), output.get("systemMessage"))
    if any(text is not None and not isinstance(text, str) for text in texts):
        raise ValueError("a reason, context or system message in it is not a string")
    return (decision,) + texts


def bash_guard_hook_results_combined_into_one_pre_tool_use_hook_output(results, host=None):
    """Return the one PreToolUse hook JSON text that gives Claude Code every guard's result, or "" for none."""
    host = host or socket.gethostname().split(".")[0]
    reasons = {decision: [] for decision in PERMISSION_DECISIONS_STRICTEST_FIRST}
    contexts, system_messages = [], []
    for result in results:
        failure = _failure(result)
        if failure is None and result["exit_status"] == 2:
            reasons["deny"].append(result["stderr"].strip())
            continue
        if failure is None and result["stdout"].strip():
            try:
                decision, reason, context, system_message = _hook_output_parts(result["stdout"])
            except ValueError as error:
                failure = OUTPUT_NOT_COMBINED_FAILURE.format(problem=str(error).splitlines()[0],
                                                             output=_ending(result["stdout"]))
            else:
                if decision is not None:
                    reasons[decision].append(reason or "")
                contexts += [context] if context else []
                system_messages += [system_message] if system_message else []
        if failure is not None:
            names = {"guard_name": Path(result["path"]).name, "guard_file": result["path"], "host": host,
                     "failure": failure}
            contexts.append(GUARD_FAILED_AGENT_NOTICE.format(**names))
            system_messages.append(GUARD_FAILED_USER_NOTICE.format(**names))
    specific = {}
    decision = next((decision for decision in PERMISSION_DECISIONS_STRICTEST_FIRST if reasons[decision]), None)
    if decision is not None:
        specific["permissionDecision"] = decision
        given = [reason for reason in reasons[decision] if reason]
        if given:
            specific["permissionDecisionReason"] = "\n\n".join(given)
    if contexts:
        specific["additionalContext"] = "\n\n".join(contexts)
    output = {}
    if specific:
        output["hookSpecificOutput"] = {"hookEventName": "PreToolUse", **specific}
    if system_messages:
        output["systemMessage"] = "\n\n".join(system_messages)
    return json.dumps(output) if output else ""


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    print_each = PRINT_EACH_GUARD_HOOK_RESULT_AS_JSON_COMMAND_LINE_FLAG in argv
    arguments = [argument for argument in argv if argument != PRINT_EACH_GUARD_HOOK_RESULT_AS_JSON_COMMAND_LINE_FLAG]
    list_path = BASH_GUARD_HOOKS_DISPATCHER_GUARD_LIST_FILE
    if arguments[:1] == [GUARD_LIST_FILE_OPTION] and len(arguments) == 2:
        list_path = Path(arguments[1])
    elif arguments:
        raise SystemExit(f"usage: {Path(__file__).name} [{PRINT_EACH_GUARD_HOOK_RESULT_AS_JSON_COMMAND_LINE_FLAG}] "
                         f"[{GUARD_LIST_FILE_OPTION} <path>]; given {argv}")
    payload = sys.stdin.buffer.read()
    guards = bash_guard_hooks_dispatcher_guard_list_read(list_path)
    # Not resolved: a guard's __file__ is then the path Claude Code would have run it by.
    repository_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    _library_modules_preloaded()
    results = bash_guard_hook_results_from_one_forked_child_each(guards, payload, repository_root)
    if print_each:
        print(json.dumps(results))
        return 0
    output = bash_guard_hook_results_combined_into_one_pre_tool_use_hook_output(results)
    if output:
        print(output)
    return 0


if __name__ == "__main__":
    with _crash_notice.guard_hook_crash_fail_open_with_notice_context_manager(__file__, True):
        sys.exit(main())
