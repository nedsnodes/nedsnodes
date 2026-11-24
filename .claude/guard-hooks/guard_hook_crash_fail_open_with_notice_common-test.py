#!/usr/bin/env python3
"""Tests for .claude/guard-hooks/guard_hook_crash_fail_open_with_notice_common.py, and for each
PreToolUse guard .claude/settings.json registers, each of which wraps its loads and its main() in it.

Each guard is crashed for real: once in main(), by stdin that is not JSON, and, when it loads
modules of its own, once while loading them, by running a copy of it from a directory that holds
none of them.

Run: python3 .claude/guard-hooks/guard_hook_crash_fail_open_with_notice_common-test.py
Prints one line per case and exits non-zero if any case fails.
"""

import contextlib
import importlib.util
import io
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

GUARD_HOOKS_DIRECTORY = Path(__file__).resolve().parent
MODULE_PATH = GUARD_HOOKS_DIRECTORY / "guard_hook_crash_fail_open_with_notice_common.py"
_spec = importlib.util.spec_from_file_location(
    "guard_hook_crash_fail_open_with_notice_common", MODULE_PATH)
crash_notice = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(crash_notice)

SETTINGS_PATH = GUARD_HOOKS_DIRECTORY.parent / "settings.json"
COMMON_MODULE_NAME_PATTERN = re.compile(r'"([A-Za-z0-9_-]+-common\.py)"')


def registered_guards():
    """Return (guard file name, whether it loads a -common.py module a copy run elsewhere cannot
    find) for each PreToolUse guard under .claude/guard-hooks that .claude/settings.json
    registers, so that a guard added there is crash-tested without being listed here."""
    guards = {}
    settings = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
    for group in settings["hooks"]["PreToolUse"]:
        for hook in group["hooks"]:
            for guard_name in re.findall(r"\.claude/guard-hooks/([A-Za-z0-9_.-]+\.py)",
                                         hook.get("command", "")):
                source = (GUARD_HOOKS_DIRECTORY / guard_name).read_text(encoding="utf-8")
                guards[guard_name] = any(
                    name != MODULE_PATH.name for name in COMMON_MODULE_NAME_PATTERN.findall(source))
    return sorted(guards.items())


GUARDS = registered_guards()

failures = []


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


def notices_of(stdout):
    """Return (agent notice, user notice) from the hook's stdout, or None when it is not one
    JSON object carrying both."""
    try:
        output = json.loads(stdout)
        hook_output = output["hookSpecificOutput"]
        if hook_output.get("hookEventName") != "PreToolUse" or "permissionDecision" in hook_output:
            return None
        return hook_output["additionalContext"], output["systemMessage"]
    except (ValueError, KeyError, TypeError):
        return None


def check_crash_notice(case_name, result, guard_name, exception_name):
    notices = notices_of(result.stdout)
    check(f"{case_name}: exits 0, so the call goes ahead", result.returncode == 0,
          (result.returncode, result.stderr))
    check(f"{case_name}: prints nothing on stderr", result.stderr == "", result.stderr)
    check(f"{case_name}: stdout is one JSON object with both notices", notices is not None,
          result.stdout)
    if notices is None:
        return
    agent_notice, user_notice = notices
    check(f"{case_name}: the agent is told which guard crashed, with what, and that the call ran",
          f"The guard hook {guard_name} crashed" in agent_notice and exception_name in agent_notice
          and "the call has run" in agent_notice, agent_notice)
    check(f"{case_name}: the user is told which guard crashed, with what, and that the call went "
          f"ahead unchecked",
          f"The guard hook {guard_name} crashed" in user_notice and exception_name in user_notice
          and "let a tool call through unchecked" in user_notice, user_notice)


# --- the helper on its own ---

def raise_inside(running_as_hook, error):
    with crash_notice.guard_hook_crash_fail_open_with_notice_context_manager(
            "/x/.claude/guard-hooks/some-guard.py", running_as_hook):
        raise error


# BaseException: an exit 0 escaping here would end this suite as a pass.
stdout = io.StringIO()
with contextlib.redirect_stdout(stdout):
    try:
        raise_inside(False, KeyError("injected"))
        raised = None
    except BaseException as error:
        raised = error
check("when not running as the hook, a crash is raised unchanged, so a test sees it",
      isinstance(raised, KeyError), raised)

stdout = io.StringIO()
with contextlib.redirect_stdout(stdout):
    try:
        raise_inside(True, ValueError("injected value"))
        exit_code = None
    except SystemExit as error:
        exit_code = error.code
notices = notices_of(stdout.getvalue())
check("when running as the hook, a crash exits 0 with both notices",
      exit_code == 0 and notices is not None, (exit_code, stdout.getvalue()))
if notices is not None:
    check("the notices name the guard, the exception and the line it was raised at",
          all("some-guard.py" in notice and "ValueError: injected value" in notice
              and "guard_hook_crash_fail_open_with_notice_common-test.py:" in notice
              for notice in notices), notices)
    check("the agent notice asks whether the guard would have refused the call, with the guard's "
          "path, and says whom to ask whether to undo it",
          "Check whether this call is one some-guard.py would have refused" in notices[0]
          and "/x/.claude/guard-hooks/some-guard.py says which calls it refuses" in notices[0]
          and "report what the call did and ask whether to undo it" in notices[0]
          and "a subagent asks the agent that dispatched it, any other agent asks the user"
          in notices[0]
          and "Do not undo the call before you have the answer" in notices[0], notices[0])

try:
    raise_inside(True, SystemExit(2))
    exit_code = None
except SystemExit as error:
    exit_code = error.code
check("a guard's own exit, such as a refusal's 2, passes through unchanged", exit_code == 2,
      exit_code)

# --- traceback is loaded only on the crash path ---

# A fresh interpreter, because this suite's own imports may already have loaded traceback; -I -S
# because a sitecustomize.py or .pth file could load it at startup.
LOAD_MODULE_SOURCE = (
    "import importlib.util\n"
    "import sys\n"
    "spec = importlib.util.spec_from_file_location(\n"
    f"    'guard_hook_crash_fail_open_with_notice_common', {str(MODULE_PATH)!r})\n"
    "crash_notice = importlib.util.module_from_spec(spec)\n"
    "spec.loader.exec_module(crash_notice)\n")
result = subprocess.run(
    [sys.executable, "-I", "-S", "-c", LOAD_MODULE_SOURCE + "print('traceback' in sys.modules)"],
    capture_output=True, text=True, timeout=60)
check("importing the module in a fresh interpreter leaves traceback out of sys.modules",
      result.returncode == 0 and result.stdout.strip() == "False",
      (result.returncode, result.stdout, result.stderr))

crash_results = []
with tempfile.TemporaryDirectory() as temporary_directory:
    crashing_guard = Path(temporary_directory) / "crashing-guard.py"
    # Both first lines keep the raise on line 10, so the two notices can be compared whole.
    for first_line in ("import traceback", ""):
        crashing_guard.write_text(
            first_line + "\n" + LOAD_MODULE_SOURCE
            + "with crash_notice.guard_hook_crash_fail_open_with_notice_context_manager(\n"
              "        '/x/.claude/guard-hooks/some-guard.py', True):\n"
              "    raise ValueError('injected value')\n", encoding="utf-8")
        crash_results.append(subprocess.run([sys.executable, "-I", "-S", str(crashing_guard)],
                                            capture_output=True, text=True, timeout=60))
loaded_before_crash, loaded_on_crash_path = crash_results
crash_notices = notices_of(loaded_on_crash_path.stdout)
check("a crash prints the same notice whether traceback was loaded before it or only on the "
      "crash path, and the notice names the line raised at",
      all(result.returncode == 0 and result.stderr == "" for result in crash_results)
      and loaded_on_crash_path.stdout == loaded_before_crash.stdout
      and crash_notices is not None
      and all("ValueError: injected value, at crashing-guard.py:10" in notice
              for notice in crash_notices),
      [(result.returncode, result.stdout, result.stderr) for result in crash_results])

# --- each guard, crashed for real ---

with tempfile.TemporaryDirectory() as temporary_directory:
    scratch = Path(temporary_directory)
    check("settings.json registers every guard this suite crashes, the ones that load nothing "
          "of their own included",
          {"instruction-file-guard.py", "claude-code-artifact-tool-claude-ai-page-delete-refusal-hook.py",
           "pkill-killall-and-process-name-pattern-kill-refusal-hook.py"}
          <= {guard_name for guard_name, _ in GUARDS}, GUARDS)
    for guard_name, loads_own_modules in GUARDS:
        guard_path = GUARD_HOOKS_DIRECTORY / guard_name
        result = subprocess.run([sys.executable, str(guard_path)], input="not JSON",
                                capture_output=True, text=True, timeout=60, cwd=scratch)
        check_crash_notice(f"{guard_name} crashing in main() on stdin that is not JSON", result,
                           guard_name, "JSONDecodeError")
        if not loads_own_modules:
            continue
        copy_directory = scratch / guard_path.stem / ".claude" / "guard-hooks"
        copy_directory.mkdir(parents=True)
        shutil.copy(guard_path, copy_directory)
        shutil.copy(MODULE_PATH, copy_directory)
        result = subprocess.run([sys.executable, str(copy_directory / guard_name)],
                                input=json.dumps({"tool_name": "Bash", "tool_input": {}}),
                                capture_output=True, text=True, timeout=60, cwd=scratch)
        check_crash_notice(f"{guard_name} crashing while loading its modules", result, guard_name,
                           "FileNotFoundError")

    keystroke_copy = (scratch / "synthetic-keystroke-guard-hook" / ".claude" / "guard-hooks"
                      / "synthetic-keystroke-guard-hook.py")
    result = subprocess.run([sys.executable, str(keystroke_copy), "--is-target-detached", "x"],
                            capture_output=True, text=True, timeout=60, cwd=scratch)
    check("the synthetic keystroke guard's check mode, which is no hook, still fails on a crash",
          result.returncode != 0 and "FileNotFoundError" in result.stderr
          and notices_of(result.stdout) is None, (result.returncode, result.stdout))

if failures:
    print(f"\n{len(failures)} case(s) failed: {', '.join(failures)}")
    sys.exit(1)
print("\nall cases passed")
