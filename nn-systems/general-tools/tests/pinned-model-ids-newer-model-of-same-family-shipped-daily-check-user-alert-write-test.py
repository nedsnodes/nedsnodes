#!/usr/bin/env python3
"""Tests for nn-systems/general-tools/pinned-model-ids-newer-model-of-same-family-shipped-daily-check-user-alert-write.py.

Each case builds a scratch git repository of pins and a scratch home directory, and hands main() a stand-in for
subprocess.run that answers for codex, agy and claude, so no agent-binary runs and the real user-alerts directory
is never read or written.

Run: python3 nn-systems/general-tools/tests/pinned-model-ids-newer-model-of-same-family-shipped-daily-check-user-alert-write-test.py
Prints one line per case and exits non-zero if any case fails.
"""
import contextlib
import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

PROGRAM = (Path(__file__).resolve().parents[1]
           / "pinned-model-ids-newer-model-of-same-family-shipped-daily-check-user-alert-write.py")
_specification = importlib.util.spec_from_file_location("pinned_model_ids_daily_check", PROGRAM)
program = importlib.util.module_from_spec(_specification)
_specification.loader.exec_module(program)

FAILURES = []


def check(name, condition, detail=""):
    print(("PASS  " if condition else "FAIL  ") + name)
    if not condition:
        print(f"      {detail!r}")
        FAILURES.append(name)


CODEX_LISTING = json.dumps({"models": [{"slug": slug} for slug in
                                       ("gpt-6.10-sol", "gpt-6.9-sol", "gpt-6-luna", "gpt-reserve")]})
AGY_LISTING = ("Fetching available models...\n"
               "gemini-4.1-neon-high\tGemini 4.1 Neon (High)\n"
               "gemini-4-neon-high\tGemini 4 Neon (High)\n"
               "gemini-3.8-flash-low\tGemini 3.8 Flash (Low)\n"
               "gemini-pro-orchestrator\tOrchestrator (Carbon)\n"
               "claude-opus-5-5-low\tClaude Opus 5.5 (Low)\n")
CLAUDE_ALIASES = {"opus": "claude-opus-5-6", "sonnet": "claude-sonnet-5-5"}

PINS_SOURCE = '''"""Docstrings that mention gpt-6.9-sol are no pin."""
CODEX_MODEL = "gpt-6.9-sol"
LUNA = "gpt-6-luna"
GEMINI = ("gemini-4-neon-high", "gemini-3.8-flash-low")
OPUS = "claude-opus-5-5"
SONNET = "claude-sonnet-5-5"
KEPT = "claude-opus-5-5"  # pin kept: its effort table was measured on this model
REPORT_NAME = "agy-hunt-gemini-4-neon-high.md"
HELP = "e.g. gpt-6.9-sol"
'''


def completed(command, stdout, returncode=0, stderr=""):
    return subprocess.CompletedProcess(command, returncode, stdout, stderr)


def fake_run(answers=None, calls=None):
    """A stand-in for subprocess.run; answers maps "codex", "agy" or "claude:<alias>" to a stdout or a callable."""
    answers = answers or {}

    def run(command, **options):
        if calls is not None:
            calls.append((command, options))
        if command[1:] == ["debug", "models"]:
            key, default = "codex", CODEX_LISTING
        elif command[1:] == ["models"]:
            key, default = "agy", AGY_LISTING
        else:
            alias = command[command.index("--model") + 1]
            key = f"claude:{alias}"
            default = json.dumps({"modelUsage": {CLAUDE_ALIASES[alias]: {}}, "is_error": False})
        answer = answers.get(key, default)
        return answer(command) if callable(answer) else completed(command, answer)
    return run


DEFAULT_TRACKED_FILES = {"tools/pins.py": PINS_SOURCE, "tools/tests/pins-test.py": 'X = "gpt-5-sol"\n',
                         "tools/pins-test.py": 'X = "gpt-5-sol"\n'}


@contextlib.contextmanager
def scratch(tracked=None):
    """A git repository holding tracked and one untracked pin, and a home directory HOME points at."""
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory).resolve()
        repository, home = root / "repository", root / "home"
        home.mkdir()
        tracked = DEFAULT_TRACKED_FILES if tracked is None else tracked
        for relative, text in {**tracked, "untracked.py": 'X = "gpt-5-sol"\n'}.items():
            path = repository / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        subprocess.run(["git", "init", "-q", str(repository)], check=True)
        subprocess.run(["git", "-C", str(repository), "add", "--", *tracked], check=True)
        saved_home = os.environ["HOME"]
        os.environ["HOME"] = str(home)
        try:
            yield repository, home
        finally:
            os.environ["HOME"] = saved_home


def pending_alerts(home):
    pending = home / ".local" / "state" / "nedsnodes" / "user-alerts" / "pending"
    return sorted((json.loads(path.read_text(encoding="utf-8")) for path in pending.glob("*.json")),
                  key=lambda alert: alert["title"])


def run_main(repository, run_command):
    output, errors = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
        exit_code = program.main([], repository=repository, run_command=run_command)
    return exit_code, output.getvalue(), errors.getvalue()


def alert_titled(alerts, title):
    return next((alert for alert in alerts if alert["title"] == title), None)


real_agent_binary_path = program.agent_binary_path
program.agent_binary_path = lambda name: f"/fake/bin/{name}"

STALE_LINES = [
    "A newer model has shipped for a pinned model id: tools/pins.py:2 pins gpt-6.9-sol; the newest of its family is "
    "gpt-6.10-sol. Update the pin in a pull request, or add `pin kept: <reason>` to its line.",
    "A newer model has shipped for a pinned model id: tools/pins.py:4 pins gemini-4-neon-high; the newest of its "
    "family is gemini-4.1-neon-high. Update the pin in a pull request, or add `pin kept: <reason>` to its line.",
    "A newer model has shipped for a pinned model id: tools/pins.py:5 pins claude-opus-5-5; the newest of its family "
    "is claude-opus-5-6. Update the pin in a pull request, or add `pin kept: <reason>` to its line.",
]

with scratch() as (repository, home):
    calls = []
    exit_code, output, errors = run_main(repository, fake_run(calls=calls))
    alerts = pending_alerts(home)
    check("a pin older than the newest of its family gets the approved line, in one user-alert; a current pin, a pin "
          "kept, a docstring, a report name, help text, a test file and an untracked file get none, and the exit is 0",
          exit_code == 0 and len(alerts) == 1 and alerts[0]["title"] == program.STALE_TITLE
          and alerts[0]["alert_text"].splitlines() == STALE_LINES and alerts[0]["action"] == program.STALE_ACTION,
          (exit_code, alerts, output, errors))
    claude_calls = [(command, options) for command, options in calls if "--model" in command]
    prefix = program.headless.claude_code_headless_run_command_line_prefix_build("default", program="/fake/bin/claude")
    check("each Claude family pinned is asked once, through the headless prefix, from a directory outside the "
          "repository, and every listing has a timeout",
          sorted(command[command.index("--model") + 1] for command, _ in claude_calls) == ["opus", "sonnet"]
          and all(command[:len(prefix)] == prefix and options["cwd"] != str(repository) for command, options in claude_calls)
          and all(options.get("timeout") == program.LISTING_TIMEOUT_SECONDS for _, options in calls)
          and len(calls) == 4, calls)

with scratch({"tools/pins.py": 'A = "gpt-6.10-sol"\nB = "claude-sonnet-5-5"\nC = "gemini-4.1-neon-high"\n'}) as (
        repository, home):
    exit_code, output, errors = run_main(repository, fake_run())
    check("with every pin the newest of its family, no user-alert is written and the exit is 0",
          exit_code == 0 and pending_alerts(home) == [] and "is the newest of its family" in output,
          (exit_code, output, errors))

with scratch({"tools/pins.py": 'A = "gpt-6.10-sol"\n'}) as (repository, home):
    calls = []
    run_main(repository, fake_run(calls=calls))
    check("an agent-binary no pin needs is not run", [command[1:] for command, _ in calls] == [["debug", "models"]],
          calls)


def failure_case(name, answers, reason_fragment, failed_command):
    with scratch() as (repository, home):
        exit_code, output, errors = run_main(repository, fake_run(answers))
        alerts = pending_alerts(home)
        unchecked = alert_titled(alerts, program.UNCHECKED_TITLE)
        stale = alert_titled(alerts, program.STALE_TITLE)
        text = unchecked["alert_text"] if unchecked else ""
        check(name + ": a user-alert names the agent-binary and why, the other pins are still checked, and the exit is 1",
              exit_code == 1 and f"`{failed_command}` could not list its models" in text and reason_fragment in text
              and unchecked["action"] == program.UNCHECKED_ACTION and stale is not None
              and len(stale["alert_text"].splitlines()) == 2, (exit_code, alerts, output, errors))


def raises(error):
    def run(command):
        raise error
    return run


failure_case("codex exits 1 because it is logged out",
             {"codex": lambda command: completed(command, "", 1, "Not logged in. Run codex login.")},
             "exited 1, printing: Not logged in. Run codex login.", "codex debug models")
failure_case("codex prints text that is not JSON", {"codex": "Error: unexpected"}, "is not the JSON object of models",
             "codex debug models")
failure_case("codex prints JSON with no models list", {"codex": '{"error": "x"}'}, "is not the JSON object of models",
             "codex debug models")
failure_case("codex lists no gpt-<version>-<name> model", {"codex": '{"models": [{"slug": "gpt-reserve"}]}'},
             "lists no gpt-<version>-<name> model", "codex debug models")
failure_case("agy prints only its fetching line", {"agy": "Fetching available models...\n"},
             "lists no gemini-<version>-<name> model", "agy models")
failure_case("agy does not finish in time", {"agy": raises(subprocess.TimeoutExpired(["agy"], 300))},
             f"did not finish within {program.LISTING_TIMEOUT_SECONDS} seconds", "agy models")
failure_case("agy cannot be started", {"agy": raises(PermissionError(13, "Permission denied"))},
             "could not be started", "agy models")
failure_case("claude does not know the alias",
             {"claude:opus": json.dumps({"modelUsage": {}, "is_error": True, "terminal_reason": "api_error"})},
             "names 0 models of the family opus, not one", "claude -p --model opus")
failure_case("claude prints text that is not JSON",
             {"claude:opus": "[claude-code:unrecognized_model] {\"model\":\"opus\"}"},
             "is not the JSON result it should print", "claude -p --model opus")

with scratch() as (repository, home):
    exit_code, output, errors = run_main(repository, fake_run({"claude:opus": json.dumps(
        {"modelUsage": {"claude-opus-5-6": {}, "claude-opus-5-5": {}}})}))
    text = (alert_titled(pending_alerts(home), program.UNCHECKED_TITLE) or {}).get("alert_text", "")
    check("a Claude result naming two models of the family is reported, since the newest cannot be told",
          exit_code == 1 and "names 2 models of the family opus" in text, (exit_code, text, output))

program.agent_binary_path = lambda name: None if name == "codex" else f"/fake/bin/{name}"
with scratch() as (repository, home):
    exit_code, output, errors = run_main(repository, fake_run())
    text = (alert_titled(pending_alerts(home), program.UNCHECKED_TITLE) or {}).get("alert_text", "")
    check("an agent-binary that is not installed is reported, with where it was looked for",
          exit_code == 1 and "no codex was found on PATH or in" in text
          and str(program.AGENT_BINARY_DIRECTORIES_OUTSIDE_CRON_PATH[0]) in text, (exit_code, text, output))
program.agent_binary_path = lambda name: f"/fake/bin/{name}"

with scratch({"tools/pins.py": 'A = "gpt-6-nova"\n'}) as (repository, home):
    exit_code, output, errors = run_main(repository, fake_run())
    text = (alert_titled(pending_alerts(home), program.UNCHECKED_TITLE) or {}).get("alert_text", "")
    check("a pin whose family the listing does not hold is reported as unchecked, and the exit is 1",
          exit_code == 1 and text == program.FAMILY_NOT_LISTED_LINE.format(
              file="tools/pins.py", line=1, id="gpt-6-nova", command="codex debug models"), (exit_code, text))

real_write = program.user_alerts.user_alert_write_to_pending


def write_that_fails(title, alert_text, action):
    raise OSError(28, "No space left on device")


program.user_alerts.user_alert_write_to_pending = write_that_fails
try:
    with scratch() as (repository, home):
        exit_code, output, errors = run_main(repository, fake_run())
        check("when the user-alert naming the stale pins cannot be written, the error is printed and the exit is 1",
              exit_code == 1 and "could not be written" in errors and "No space left on device" in errors
              and STALE_LINES[0] in output, (exit_code, output, errors))
finally:
    program.user_alerts.user_alert_write_to_pending = real_write

with tempfile.TemporaryDirectory() as directory:
    home = Path(directory) / "home"
    home.mkdir()
    saved_home = os.environ["HOME"]
    os.environ["HOME"] = str(home)
    try:
        exit_code, output, errors = run_main(Path(directory) / "not-a-repository", fake_run())
        alerts = pending_alerts(home)
        check("when git cannot list the files, a user-alert says the search failed, with git's error, and the exit is 1",
              exit_code == 1 and len(alerts) == 1 and alerts[0]["title"] == program.SEARCH_FAILED_TITLE
              and "CalledProcessError" in alerts[0]["alert_text"] and "fatal" in alerts[0]["alert_text"],
              (exit_code, alerts, errors))
        program.user_alerts.user_alert_write_to_pending = write_that_fails
        try:
            exit_code, output, errors = run_main(Path(directory) / "not-a-repository", fake_run())
        finally:
            program.user_alerts.user_alert_write_to_pending = real_write
        check("when the search fails and the user-alert saying so cannot be written, both errors are printed and the "
              "exit is 1", exit_code == 1 and "CalledProcessError" in errors and "No space left on device" in errors,
              (exit_code, errors))
    finally:
        os.environ["HOME"] = saved_home

with scratch({"tools/broken.py": 'A = "gpt-6-sol"\ndef (\n'}) as (repository, home):
    exit_code, output, errors = run_main(repository, fake_run())
    alerts = pending_alerts(home)
    check("a tracked Python file that does not parse fails the search, in a user-alert naming the file",
          exit_code == 1 and len(alerts) == 1 and alerts[0]["title"] == program.SEARCH_FAILED_TITLE
          and "broken.py" in alerts[0]["alert_text"], (exit_code, alerts))

check("versions compare as numbers part by part",
      program.model_id_parts("gpt-6.10-sol")[2] > program.model_id_parts("gpt-6.9-sol")[2]
      > program.model_id_parts("gpt-6-sol")[2]
      and program.model_id_parts("claude-opus-5-10")[2] > program.model_id_parts("claude-opus-5-9")[2])
check("a Claude id without a minor version, a Gemini id without a version and a file name are no model id",
      program.model_id_parts("claude-opus-5") is None and program.model_id_parts("gemini-pro-orchestrator") is None
      and program.model_id_parts("gemini-4-neon-high.md") is None)

program.agent_binary_path = real_agent_binary_path
with tempfile.TemporaryDirectory() as directory:
    installed = Path(directory) / "claude"
    installed.write_text("#!/bin/sh\n", encoding="utf-8")
    installed.chmod(0o755)
    saved_directories, saved_path = program.AGENT_BINARY_DIRECTORIES_OUTSIDE_CRON_PATH, os.environ["PATH"]
    program.AGENT_BINARY_DIRECTORIES_OUTSIDE_CRON_PATH = (Path(directory),)
    os.environ["PATH"] = "/usr/bin:/bin"
    try:
        found = program.agent_binary_path("claude")
    finally:
        program.AGENT_BINARY_DIRECTORIES_OUTSIDE_CRON_PATH, os.environ["PATH"] = saved_directories, saved_path
    check("under cron's PATH an agent-binary is found in the directories cron's PATH leaves out",
          found == str(installed), found)

if FAILURES:
    print(f"\n{len(FAILURES)} case(s) FAILED:")
    for name in FAILURES:
        print(f"  - {name}")
    sys.exit(1)
print("\nall cases passed")
