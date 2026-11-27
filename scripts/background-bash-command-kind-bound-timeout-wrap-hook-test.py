#!/usr/bin/env python3
"""Cases for the PreToolUse hook that runs each background Bash command under `timeout`.

Hook cases run the hook as a subprocess, its real stdin-to-stdout path. Cases that need a command
stopped build the wrapper in-process with a bound of seconds, injected because the real bounds
are 75 minutes and more, and run it with bash.

Run: python3 scripts/background-bash-command-kind-bound-timeout-wrap-hook-test.py
"""

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

HOOK_SCRIPT = Path(__file__).with_name("background-bash-command-kind-bound-timeout-wrap-hook.py")
_hook_specification = importlib.util.spec_from_file_location(
    "background_bash_command_kind_bound_timeout_wrap_hook", HOOK_SCRIPT)
hook = importlib.util.module_from_spec(_hook_specification)
_hook_specification.loader.exec_module(hook)
_threshold_specification = importlib.util.spec_from_file_location(
    "handoff_context_threshold_hook", Path(__file__).with_name("handoff-context-threshold-hook.py"))
threshold_hook = importlib.util.module_from_spec(_threshold_specification)
_threshold_specification.loader.exec_module(threshold_hook)

SHORT_BOUND_MINUTES = 0.03


def run_hook(command, run_in_background=True, environment=None):
    tool_input = {"command": command, "description": "a case", "timeout": 600000}
    if run_in_background is not None:
        tool_input["run_in_background"] = run_in_background
    completed = subprocess.run(
        [sys.executable, str(HOOK_SCRIPT)],
        input=json.dumps({"hook_event_name": "PreToolUse", "tool_name": "Bash",
                          "tool_input": tool_input}),
        capture_output=True, text=True, check=False, env=environment)
    return completed


def updated_input(completed):
    return json.loads(completed.stdout)["hookSpecificOutput"]["updatedInput"]


def stop_message(minutes, kind):
    return hook.BACKGROUND_COMMAND_KIND_BOUND_TIMEOUT_STOP_MESSAGE.format(minutes=minutes, kind=kind)


class HookRewritesBackgroundCommands(unittest.TestCase):

    def test_waiting_task_is_bounded_at_75_minutes_and_keeps_its_wait_limit_of_0(self):
        completed = run_hook("gh pr checks 12 --watch")
        self.assertEqual(completed.returncode, 0, completed.stderr)
        command = updated_input(completed)["command"]
        self.assertTrue(command.startswith("timeout 4500s bash -c "), command)
        self.assertIn(stop_message("75", "waiting-task"), command)
        self.assertEqual(threshold_hook.background_task_kind_and_wait_limit_minutes_from_command(command),
                         ("waiting-task", 0.0))

    def test_kind_with_a_wait_limit_is_bounded_at_it(self):
        command = updated_input(run_hook("pytest -q scripts"))["command"]
        self.assertTrue(command.startswith("timeout 5400s bash -c "), command)
        self.assertIn(stop_message("90", "test-suite"), command)

    def test_command_no_kind_matches_is_reported_as_kind_unmatched(self):
        command = updated_input(run_hook("make build"))["command"]
        self.assertTrue(command.startswith("timeout 4500s bash -c "), command)
        self.assertIn(stop_message("75", "unmatched"), command)

    def test_other_input_fields_are_carried_through(self):
        rewritten = updated_input(run_hook("make build"))
        self.assertEqual((rewritten["run_in_background"], rewritten["description"], rewritten["timeout"]),
                         (True, "a case", 600000))

    def test_programs_that_enforce_their_own_time_limits_are_not_wrapped(self):
        for command in ("python3 scripts/run-all-test-suites.py --only-suites-whose-recorded-inputs-changed-since origin/main",
                        "cd /x && python3 /home/nedlern/repo/nn-systems/cold-read/cold-read-grid.py --target a.md"):
            with self.subTest(command=command):
                completed = run_hook(command)
                self.assertEqual((completed.returncode, completed.stdout), (0, ""), completed.stderr)

    def test_a_foreground_command_is_not_wrapped(self):
        for run_in_background in (False, None):
            with self.subTest(run_in_background=run_in_background):
                completed = run_hook("sleep 120", run_in_background=run_in_background)
                self.assertEqual((completed.returncode, completed.stdout), (0, ""), completed.stderr)

    def test_missing_timeout_program_leaves_the_command_unbounded_and_tells_the_agent(self):
        with tempfile.TemporaryDirectory() as empty_path_directory:
            completed = run_hook("sleep 120", environment={**os.environ, "PATH": empty_path_directory})
        self.assertEqual(completed.returncode, 0, completed.stderr)
        output = json.loads(completed.stdout)["hookSpecificOutput"]
        self.assertNotIn("updatedInput", output)
        self.assertIn("coreutils `timeout` is not on PATH", output["additionalContext"])


class WrappedCommandRuns(unittest.TestCase):

    def run_wrapped(self, command, kind="unmatched"):
        wrapped = hook.background_bash_command_text_wrapped_in_kind_bound_timeout_with_stop_message(
            command, SHORT_BOUND_MINUTES, kind)
        started = time.monotonic()
        completed = subprocess.run(["bash", "-c", wrapped], capture_output=True, text=True,
                                   check=False, timeout=60)
        return completed, time.monotonic() - started

    def test_a_command_past_its_bound_is_stopped_with_its_child_and_ends_with_the_message(self):
        with tempfile.TemporaryDirectory() as directory:
            child_pid_file = Path(directory) / "child.pid"
            completed, elapsed = self.run_wrapped(
                f"sleep 300 & echo $! > {child_pid_file}; wait")
            child_pid = int(child_pid_file.read_text())
        self.assertEqual(completed.returncode, hook.TIMEOUT_STOPPED_EXIT_STATUS)
        self.assertLess(elapsed, 30)
        self.assertTrue(completed.stdout.endswith(stop_message("0.03", "unmatched") + "\n"),
                        completed.stdout)
        time.sleep(0.5)
        with self.assertRaises(ProcessLookupError):
            os.kill(child_pid, 0)

    def test_a_stopped_command_that_holds_gh_pr_view_ends_with_the_pull_request_wait_line(self):
        completed, _ = self.run_wrapped(
            "while true; do echo gh pr view 4339 --json state; sleep 1; done")
        self.assertTrue(completed.stdout.endswith(
            stop_message("0.03", "unmatched") + "\n"
            + 'To wait for a pull request, use TaskUpdate to give the task on your task list that '
            'waits for it the metadata {"prerequisites": [{"pr_merged": 4339}]} instead.\n'),
            completed.stdout)

    def test_a_command_that_ends_within_its_bound_keeps_its_exit_status_and_gets_no_message(self):
        completed, _ = self.run_wrapped("echo ran; exit 3")
        self.assertEqual((completed.returncode, completed.stdout), (3, "ran\n"))

    def test_a_command_without_gh_pr_view_gets_no_pull_request_wait_line(self):
        completed, _ = self.run_wrapped("sleep 300")
        self.assertNotIn("To wait for a pull request", completed.stdout)


class Unwrap(unittest.TestCase):

    def test_a_wrapped_command_unwraps_to_the_original(self):
        for command in ("sleep 120", "echo 'it'\"'\"'s' ; ls \"$HOME\"", "a\nb ; c"):
            with self.subTest(command=command):
                wrapped = hook.background_bash_command_text_wrapped_in_kind_bound_timeout_with_stop_message(command, 75, "k")
                self.assertEqual(hook.background_bash_command_unwrapped_from_kind_bound_timeout(wrapped),
                                 command)

    def test_a_command_this_hook_did_not_wrap_is_returned_unchanged(self):
        for command in ("timeout 60s bash -c 'sleep 5'", "timeout 60s bash -c 'unclosed", "ls", None):
            with self.subTest(command=command):
                self.assertEqual(hook.background_bash_command_unwrapped_from_kind_bound_timeout(command),
                                 command)


if __name__ == "__main__":
    unittest.main()
