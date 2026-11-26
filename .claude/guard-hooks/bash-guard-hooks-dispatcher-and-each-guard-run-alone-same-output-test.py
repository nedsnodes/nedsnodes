#!/usr/bin/env python3
"""Check that every Bash guard prints the same through .claude/guard-hooks/bash-guard-hooks-dispatcher.py as run alone.

For each command, every guard in the dispatcher's guard list is run alone, as Claude Code runs a hook,
`python3 <guard file>` with the hook payload on its input, all at once; then the dispatcher is run once
with --print-each-guard-hook-result-as-json. Each guard's standard output, standard error and exit status must be the
same both ways. A guard missing from the dispatcher's results, or one more, fails too.

Both ways run in the same sandbox, so a command's guards act on nothing real: git, gh, tmux, ssh, codex
and claude on PATH are fakes that print nothing and exit 1, the payload's working directory is an empty
directory of this test's own, and each run of the guards gets a temporary directory of its own, which is
where the emergency-stop hook keeps its once-per-agent-session record. The guards' probes therefore
all fail the same way both ways; what differs from one command to the next is how each guard reads the
command text.

Commands:
- By default, the committed list FIXTURE_COMMANDS below: commands each guard refuses or comments on,
  one that two guards refuse, commands the shell reader finds hard, and a payload that is not JSON.
- --recorded-commands: the agents' recorded Bash commands, collected from the transcripts as
  nn-systems/general-tools/bash-guards-verdict-changes-between-git-refs-on-recorded-commands-check.py
  collects them (--transcript-directory, repeatable, defaults to that check's). Running 13 processes for
  each of tens of thousands of commands takes hours, so that check's in-process readings first pick
  every command some guard does not pass, then --sample-of-passed-commands commands (500 by default)
  that every guard passes, drawn with a fixed seed.

Run: python3 .claude/guard-hooks/bash-guard-hooks-dispatcher-and-each-guard-run-alone-same-output-test.py
     [--recorded-commands [--transcript-directory <directory>]... [--sample-of-passed-commands <n>]] [--jobs <n>]
Prints one line per command that differs, then a summary. Exit status: 0 when every guard printed the
same both ways on every command; 1 when one did not; 2 when the commands could not be collected.
"""

import argparse
import concurrent.futures
import importlib.util
import json
import multiprocessing
import os
import random
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
DISPATCHER = Path(__file__).resolve().with_name("bash-guard-hooks-dispatcher.py")
VERDICT_CHECK = (REPOSITORY_ROOT / "nn-systems" / "general-tools"
                 / "bash-guards-verdict-changes-between-git-refs-on-recorded-commands-check.py")
FAKED_PROGRAMS = ("git", "gh", "tmux", "ssh", "codex", "claude")
DEFAULT_SAMPLE_OF_PASSED_COMMANDS = 500
SAMPLE_SEED = 20261126
PRINTED_CHARACTERS = 300
# Slack over a guard's own timeout for a run alone, which has no dispatcher to stop it.
ALONE_TIMEOUT_SLACK_SECONDS = 5

_spec = importlib.util.spec_from_file_location("bash_guard_hooks_dispatcher", DISPATCHER)
dispatcher = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(dispatcher)

NOT_JSON_PAYLOAD = "this payload is not JSON"
FIXTURE_COMMANDS = [
    "true",
    "git log -1 --oneline",
    "ls -la && echo done",
    "pkill -f worker",
    "killall python3",
    "kill $(pgrep -f run-all-test-suites.py)",
    "until ! kill -0 $(pgrep -f x | head -1); do sleep 5; done",
    'codex exec -C /tmp/x "do the task"',
    "tmux kill-server",
    "tmux kill-session -t agent",
    "tmux send-keys -t agent 'ls' Enter",
    "git push --force origin some-topic-branch",
    "git push origin HEAD",
    "gh pr merge 12 --repo nedsnodes/nedsnodes --squash",
    'gh issue create --title "x" --body "y"',
    "grep -r pattern -file-named-like-an-option.txt",
    "rg -n foo -- -x.md",
    "cat new.md > docs/issues/1-some-ghi.md",
    "python3 nn-systems/cold-read/cold-read-grid.py --target docs/x.md",
    "git worktree remove /nonexistent/worktree",
    "git worktree remove --force ../another-worktree && echo removed",
    "pkill -f x; codex exec hi",
    "bash -c 'pkill -f inner'",
    "ssh nedlern@ned-box 'pkill -f remote'",
    "cat <<'EOF' > /tmp/x\npkill -f in-a-heredoc\nEOF",
    "echo $'\\u00e9\\c?' | sed 's/a/b/'",
    "for p in $(pgrep x); do kill $p; done",
    "echo 'unclosed",
    NOT_JSON_PAYLOAD,
]


def payload_text(command, working_directory):
    if command == NOT_JSON_PAYLOAD:
        return command
    return json.dumps({"hook_event_name": "PreToolUse", "tool_name": "Bash", "session_id": "same-output-test",
                       "cwd": working_directory, "transcript_path": "/nonexistent/transcript.jsonl",
                       "permission_mode": "default", "tool_input": {"command": command}})


class Sandbox:
    """The fake programs, the empty working directory and the environment both ways of running share."""

    def __init__(self):
        self.root = Path(tempfile.mkdtemp(prefix="bash-guard-hooks-same-output-test-"))
        fakes = self.root / "fake-programs"
        fakes.mkdir()
        for program in FAKED_PROGRAMS:
            fake = fakes / program
            fake.write_text("#!/bin/sh\nexit 1\n")
            fake.chmod(0o755)
        self.working_directory = self.root / "working-directory"
        self.working_directory.mkdir()
        self.environment = {key: value for key, value in os.environ.items()
                            if not key.startswith(("GIT_", "TMUX", "CLAUDE_"))}
        self.environment.update(PATH=f"{fakes}{os.pathsep}{os.environ.get('PATH', '')}",
                                CLAUDE_PROJECT_DIR=str(REPOSITORY_ROOT))

    def run_environment(self):
        """An environment whose temporary directory is new, so no run sees a record another run wrote."""
        temporary = tempfile.mkdtemp(dir=self.root, prefix="run-")
        return dict(self.environment, TMPDIR=temporary)

    def remove(self):
        shutil.rmtree(self.root, ignore_errors=True)


def alone_results(guards, payload, sandbox):
    """Run every guard alone, all at once, and return [stdout, stderr, exit status or "timed out"] for each."""
    environment = sandbox.run_environment()
    processes = [subprocess.Popen([sys.executable, str(REPOSITORY_ROOT / path)], stdin=subprocess.PIPE,
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=sandbox.working_directory,
                                  env=environment) for path, _ in guards]
    results = []
    for process, (_, timeout) in zip(processes, guards):
        try:
            stdout, stderr = process.communicate(payload.encode(), timeout=timeout + ALONE_TIMEOUT_SLACK_SECONDS)
            status = process.returncode
        except subprocess.TimeoutExpired:
            process.kill()
            stdout, stderr = process.communicate()
            status = "timed out"
        results.append([stdout.decode("utf-8", "replace"), stderr.decode("utf-8", "replace"), status])
    return results


def dispatched_results(payload, sandbox):
    """Run the dispatcher once and return (its results by guard path, its error output)."""
    completed = subprocess.run([sys.executable, str(DISPATCHER), dispatcher.PRINT_EACH_GUARD_HOOK_RESULT_AS_JSON_COMMAND_LINE_FLAG],
                               input=payload.encode(), capture_output=True, cwd=sandbox.working_directory,
                               env=sandbox.run_environment(), timeout=600)
    try:
        results = json.loads(completed.stdout)
    except ValueError:
        return None, completed.stdout.decode("utf-8", "replace") + completed.stderr.decode("utf-8", "replace")
    return results, completed.stderr.decode("utf-8", "replace")


def differences_for_command(command, guards, sandbox):
    """Return (the lines that say how the dispatcher's results for one command differ from the guards' alone,
    the guards that printed something alone)."""
    payload = payload_text(command, str(sandbox.working_directory))
    alone = alone_results(guards, payload, sandbox)
    printed = {path for (path, _), (stdout, stderr, _) in zip(guards, alone) if stdout.strip() or stderr.strip()}
    results, dispatcher_error_output = dispatched_results(payload, sandbox)
    shown = repr(command[:PRINTED_CHARACTERS])
    if results is None or not isinstance(results, list):
        return [f"{shown}: the dispatcher printed no results: {dispatcher_error_output[:PRINTED_CHARACTERS]!r}"], printed
    lines = []
    if dispatcher_error_output:
        lines.append(f"{shown}: the dispatcher wrote error output: {dispatcher_error_output[:PRINTED_CHARACTERS]!r}")
    if [result.get("path") for result in results] != [path for path, _ in guards]:
        lines.append(f"{shown}: the dispatcher ran {[result.get('path') for result in results]}, "
                     f"not the guard list {[path for path, _ in guards]}")
        return lines, printed
    for (path, _), (stdout, stderr, status), result in zip(guards, alone, results):
        through = [result["stdout"], result["stderr"],
                   "timed out" if result["timed_out"] else result["exit_status"]
                   if result["signal"] is None else f"signal {result['signal']}"]
        alone_status = status if not isinstance(status, int) or status >= 0 else f"signal {-status}"
        for part, alone_value, through_value in zip(("stdout", "stderr", "exit status"),
                                                     (stdout, stderr, alone_status), through):
            if alone_value != through_value:
                lines.append(f"{shown}: {Path(path).name} {part} alone {str(alone_value)[:PRINTED_CHARACTERS]!r}, "
                             f"through the dispatcher {str(through_value)[:PRINTED_CHARACTERS]!r}")
    return lines, printed


def recorded_commands_picked(transcript_directories, sample_size, jobs):
    """Return (the recorded commands to compare, how many distinct recorded commands there are)."""
    spec = importlib.util.spec_from_file_location("bash_guards_verdict_changes_check", VERDICT_CHECK)
    check = importlib.util.module_from_spec(spec)
    # The check's worker pool sends its functions by module name, which a forked worker finds here and a
    # spawned one, macOS's default, cannot import.
    sys.modules[spec.name] = check
    multiprocessing.set_start_method("fork", force=True)
    spec.loader.exec_module(check)
    pairs, _ = check.recorded_command_pairs(transcript_directories or check.DEFAULT_TRANSCRIPT_DIRECTORIES)
    with tempfile.TemporaryDirectory() as search_file_directory:
        rows = check.ref_verdicts(REPOSITORY_ROOT, pairs, jobs, False, search_file_directory, False,
                                  check.DEFAULT_PER_PAIR_TIMEOUT_SECONDS)[0]
    not_passed, passed = [], []
    for (command, _), row in zip(pairs, rows):
        verdicts = [verdict[0] if isinstance(verdict, list) else verdict for verdict, _ in row.values()]
        # The force-push guard's reading gives None, not "passed", for a command it lets through.
        (passed if all(verdict in ("passed", None) for verdict in verdicts) else not_passed).append(command)
    commands = list(dict.fromkeys(not_passed))
    passed = list(dict.fromkeys(command for command in passed if command not in set(commands)))
    commands += random.Random(SAMPLE_SEED).sample(passed, min(sample_size, len(passed)))
    return commands, len(pairs), len(not_passed)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--recorded-commands", action="store_true")
    parser.add_argument("--transcript-directory", action="append", default=[])
    parser.add_argument("--sample-of-passed-commands", type=int, default=DEFAULT_SAMPLE_OF_PASSED_COMMANDS)
    parser.add_argument("--jobs", type=int, default=max(1, (os.cpu_count() or 2) // 2))
    arguments = parser.parse_args(argv)
    # A run over recorded commands takes long; each line then reaches a log as soon as it is printed.
    sys.stdout.reconfigure(line_buffering=True)
    guards = dispatcher.bash_guard_hooks_dispatcher_guard_list_read()
    if arguments.recorded_commands:
        try:
            commands, recorded, not_passed = recorded_commands_picked(
                arguments.transcript_directory, arguments.sample_of_passed_commands, arguments.jobs)
        except Exception as error:
            print(f"FAIL  the recorded commands could not be collected and read: {error!r}")
            return 2
        print(f"Comparing {len(commands)} of {recorded} distinct recorded commands: the {not_passed} that some "
              f"guard does not pass, and {len(commands) - not_passed} that every guard passes.")
    else:
        commands = FIXTURE_COMMANDS
    sandbox = Sandbox()
    differing, printing = 0, set()
    try:
        with concurrent.futures.ThreadPoolExecutor(arguments.jobs) as pool:
            for command, (lines, printed) in zip(commands, pool.map(
                    lambda command: differences_for_command(command, guards, sandbox), commands)):
                for line in lines:
                    print(f"FAIL  {line}")
                differing += bool(lines)
                printing |= printed
    finally:
        sandbox.remove()
    silent = [path for path, _ in guards if path not in printing]
    if not arguments.recorded_commands and silent:
        # A guard that prints nothing on any command would pass however the dispatcher ran it.
        print(f"FAIL  these guards printed nothing on any fixture command, so the fixture does not test them: "
              f"{silent}; add to FIXTURE_COMMANDS a command each of them refuses or comments on")
        differing += 1
    if differing:
        print(f"\n{differing} of {len(commands)} commands gave different output through the dispatcher.")
        return 1
    print(f"PASS  all {len(guards)} guards printed the same alone and through the dispatcher on all "
          f"{len(commands)} commands.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
