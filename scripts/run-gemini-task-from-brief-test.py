#!/usr/bin/env python3
"""Test the Gemini launcher with fake agy and sandbox commands, without model calls.

Checks CLI forwarding, sandbox mount order and profiles, model discovery,
closed stdin, logging, every failure handler and process-group deadlines.
A fake scripts/run-all-test-suites.py in each test worktree stands in for
the worktree's own test-suite runner.
Sandbox argument tests do not claim that a host supports sandbox execution.
Run directly with Python; unittest exits nonzero on a failed assertion.
"""

import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

_git_environment_fixture_spec = importlib.util.spec_from_file_location(
    "git_redirecting_environment_removal_test_fixture",
    Path(__file__).resolve().with_name("git-redirecting-environment-removal-test-fixture.py"))
_git_environment_fixture = importlib.util.module_from_spec(_git_environment_fixture_spec)
_git_environment_fixture_spec.loader.exec_module(_git_environment_fixture)
_git_environment_fixture.remove_git_redirecting_environment_variables_from_this_process()

PROGRAM = Path(__file__).with_name("run-gemini-task-from-brief.py")
spec = importlib.util.spec_from_file_location("gemini_task", PROGRAM)
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)

LISTED_MODEL = "gemini-4-neon-high"
OTHER_LISTED_MODEL = "gemini-3.8-flash-medium"
# A strict prefix of a listed id, so a launcher that accepted prefixes would take it.
PARTIAL_MODEL = LISTED_MODEL.rsplit("-", 1)[0]

FAKE_AGY = r'''#!PYTHON
import json, os, pathlib, signal, sys, time
args = sys.argv[1:]
mode = os.environ.get("FAKE_AGY_MODE", "report")
with open(os.environ["FAKE_CALLS"], "a") as f:
    f.write(json.dumps([os.getcwd(), args, sys.stdin.read()]) + "\n")
with open(os.environ["FAKE_CALLS"] + ".environment", "w") as f:
    json.dump({name: os.environ.get(name) for name in ("GH_TOKEN", "GITHUB_TOKEN", "GH_CONFIG_DIR")}, f)
print("agy stderr", file=sys.stderr, flush=True)
if "GEMINI_API_KEY" in os.environ:
    print("agy was given GEMINI_API_KEY", flush=True)
    sys.exit(3)
if args == ["models"]:
    if mode == "models-fail":
        sys.exit(4)
    if mode != "models-sleep":
        print("Available models:\n  @LISTED@\n  @OTHER@\n  gemini-pro-orchestrator", flush=True)
        sys.exit(0)
if mode in ("sleep", "models-sleep"):
    child = os.fork()
    if child == 0:
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        pathlib.Path(os.environ["FAKE_CHILD"]).write_text(str(os.getpid()))
        time.sleep(120)
        os._exit(0)
    time.sleep(120)
print("agy stdout", flush=True)
if mode == "gh-refused":
    print('HTTP 401: Bad credentials (https://api.github.com/graphql)', flush=True)
report = pathlib.Path(os.environ["FAKE_REPORT"])
if mode == "fail":
    report.write_text("partial output")
    sys.exit(7)
if mode == "remove-report":
    report.unlink()
elif mode != "no-report":
    report.write_text("one\ntwo\nthree\n")
writes = os.environ.get("FAKE_AGY_WORKTREE_WRITES", "").split(",")
if "change" in writes:
    pathlib.Path(os.getcwd(), "changed.txt").write_text("Gemini's change\n")
if "message" in writes:
    pathlib.Path(os.getcwd(), "commit-message.txt").write_text("Gemini's subject\n\nGemini's body.\n")
if mode == "no-result-line":
    sys.exit(0)
if mode == "no-result-line-then-hang":
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
    pathlib.Path(os.environ["FAKE_CHILD"]).write_text(str(os.getpid()))
    time.sleep(120)
status = "ERROR" if mode.startswith("result-error") else "SUCCESS"
# Before the result line, which lets the launcher kill this process at once.
if mode.endswith("then-hang"):
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
    pathlib.Path(os.environ["FAKE_CHILD"]).write_text(str(os.getpid()))
print(json.dumps({"event": "result", "result": {"status": status, "response": "done"}}), flush=True)
if mode.endswith("then-hang"):
    time.sleep(120)
'''

FAKE_TEST_SUITE_RUNNER = r'''#!PYTHON
import json, os, sys
with open(os.environ["FAKE_TEST_SUITE_RUNNER_CALLS"], "w") as record:
    json.dump([os.getcwd(), sys.argv[1:]], record)
mode = os.environ.get("FAKE_TEST_SUITE_RUNNER_MODE", "pass")
if mode == "pass":
    print("PASS scripts/a-test.py (1.0s)")
elif mode == "fail":
    print("FAIL scripts/a-test.py exit 1 (1.0s)")
    print("2 failed:")
    print("FAIL scripts/a-test.py exit 1 — log /logs/a-test.py.log")
    print("FAIL scripts/c-test.py exit 2 — log /logs/c-test.py.log")
    sys.exit(1)
elif mode == "no-verdict":
    print("NOT RUN scripts/a-test.py did not start: bwrap failed")
    sys.exit(2)
'''

FAKE_SANDBOX = r'''#!PYTHON
import json, os, sys
args = sys.argv[1:]
with open(os.environ["FAKE_SANDBOX_CALLS"], "a") as f:
    f.write(json.dumps(args) + "\n")
pos = args.index("agy")
os.execvp("agy", args[pos:])
'''


class GeminiTaskTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="gemini-task-test-")
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        self.checkout = self.base / "checkout"
        self.checkout.mkdir()
        self.bin = self.base / "bin"
        self.bin.mkdir()
        self.home = self.base / "home"
        self.home.mkdir()
        for name, content in (("agy", FAKE_AGY), ("bwrap", FAKE_SANDBOX),
                              ("sandbox-exec", FAKE_SANDBOX)):
            script = self.bin / name
            script.write_text(content.replace("#!PYTHON", "#!" + sys.executable)
                              .replace("@LISTED@", LISTED_MODEL).replace("@OTHER@", OTHER_LISTED_MODEL))
            script.chmod(0o755)
        self.brief = self.base / "brief.md"
        self.brief.write_text("---\nRead README.md.\nWrite three lines.\n")
        self.report = self.checkout / "report.md"
        self.log = self.base / "output.log"
        self.calls = self.base / "calls"
        self.sandbox_calls = self.base / "sandbox-calls"
        self.child = self.base / "child"
        self.env = dict(os.environ, PATH=str(self.bin) + os.pathsep + os.environ['PATH'],
                        HOME=str(self.home), FAKE_CALLS=str(self.calls),
                        FAKE_REPORT=str(self.report), FAKE_CHILD=str(self.child),
                        FAKE_SANDBOX_CALLS=str(self.sandbox_calls))
        self.args = ["-C", str(self.checkout), "--brief", str(self.brief), "-o", str(self.report),
                     "--run-log", str(self.log)]
        # Runs in this process read these paths, which the module set from the real home.
        self.shared_folder = (self.home / "nedsnodes-logs"
                              / "codex-and-gemini-sandboxed-task-runs-shared-writable-folder")
        self.token_file = (self.home / ".config" / "nedsnodes-sandboxed-models"
                           / "github-public-repositories-read-only-token")
        for module, name, value in (
                (runner.codex_task, "CODEX_AND_GEMINI_SHARED_WRITABLE_FOLDER", self.shared_folder),
                (runner.agy_cell.common, "SANDBOXED_MODELS_READ_ONLY_GITHUB_TOKEN_FILE", self.token_file)):
            patcher = patch.object(module, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def run_cli(self, mode="report", extra=(), **kwargs):
        return subprocess.run([sys.executable, str(PROGRAM), *self.args, *extra],
                              env=dict(self.env, FAKE_AGY_MODE=mode),
                              capture_output=True, text=True, timeout=25, **kwargs)

    def test_cli(self):
        first, second = self.base / "first folder", self.base / "second"
        first.mkdir()
        second.mkdir()
        result = self.run_cli(extra=("--sandbox", "workspace-write", "--writable-root", str(first),
                                    "--writable-root", str(second), "--effort", "medium",
                                    "-m", "gemini-pro-orchestrator", "--deadline-minutes", "10"),
                              input="caller stdin must not reach agy")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, f"report: {self.report}\n")
        calls = [json.loads(line) for line in self.calls.read_text().splitlines()]
        self.assertEqual(calls[0], [str(self.checkout), ["models"], ""])
        cwd, args, stdin = calls[1]
        self.assertEqual((cwd, stdin), (str(self.checkout), ""))
        self.assertTrue(args[-1].startswith(self.brief.read_text()))
        self.assertIn(str(self.report), args[-1])
        for flag, value in (("--model", "gemini-pro-orchestrator"), ("--effort", "medium"),
                            ("--print-timeout", "600s"), ("--output-format", "stream-json")):
            self.assertEqual(args[args.index(flag) + 1], value)
        self.assertIn("--dangerously-skip-permissions", args)
        self.assertEqual([args[i+1] for i, arg in enumerate(args) if arg == "--add-dir"],
                         list(map(str, (self.checkout, first, second))))
        self.assertIn("agy stdout", self.log.read_text())
        self.assertEqual(self.log.read_text().count("agy stderr"), 2)
        prefixes = [json.loads(line) for line in self.sandbox_calls.read_text().splitlines()]
        self.assertEqual(prefixes[0][:prefixes[0].index("agy")], prefixes[1][:prefixes[1].index("agy")])

    def test_defaults(self):
        self.args = self.args[:-2]
        with patch.dict(os.environ, self.env), contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(runner.main(self.args), 0)
        args = json.loads(self.calls.read_text().splitlines()[1])[1]
        self.assertEqual(args[args.index("--model") + 1], "gemini-4-neon-high")
        self.assertNotIn("--effort", args)
        self.assertTrue(self.report.with_name(self.report.name + ".run.log").is_file())

    def test_sandbox_mode_decides_whether_checkout_is_writable(self):
        outside_report = self.base / "log-store" / "report.md"
        self.args[self.args.index("-o") + 1] = str(outside_report)
        self.env["FAKE_REPORT"] = str(outside_report)
        for mode, writable in (("read-only", [outside_report]),
                               ("workspace-write", [outside_report, self.checkout])):
            with self.subTest(mode=mode):
                self.sandbox_calls.unlink(missing_ok=True)
                result = self.run_cli(extra=("--sandbox", mode))
                self.assertEqual(result.returncode, 0, result.stderr)
                prefix = json.loads(self.sandbox_calls.read_text().splitlines()[-1])
                if sys.platform == "darwin":
                    checkout_rule = f'(require-not (subpath {json.dumps(str(self.checkout))}))'
                    self.assertEqual(checkout_rule in prefix[1], mode == "workspace-write")
                else:
                    self.assertEqual([prefix[i + 1] for i, arg in enumerate(prefix) if arg == "--bind"],
                                     list(map(str, writable)))

    def test_inherited_gemini_api_key_is_removed_from_agy_environment(self):
        self.env["GEMINI_API_KEY"] = "test-key-from-caller"
        result = self.run_cli()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("test-key-from-caller", self.log.read_text())

    def environment_agy_saw(self):
        return json.loads(Path(str(self.calls) + ".environment").read_text())

    def test_agy_gets_the_read_only_github_token_and_the_network(self):
        self.token_file.parent.mkdir(parents=True)
        self.token_file.write_text("read-only-token\n")
        self.env.update(GH_TOKEN="agent-seat-token", GITHUB_TOKEN="agent-seat-token")
        result = self.run_cli()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.environment_agy_saw(), {
            "GH_TOKEN": "read-only-token", "GITHUB_TOKEN": None,
            "GH_CONFIG_DIR": str(self.token_file.parent)})
        self.assertNotIn("GitHub token", self.log.read_text())
        prefix = json.loads(self.sandbox_calls.read_text().splitlines()[-1])
        self.assertNotIn("--unshare-net", prefix)
        self.assertFalse(any("deny network" in argument for argument in prefix))

    def test_missing_read_only_token_runs_without_one_and_logs_it_after_the_model_listing(self):
        self.env.update(GH_TOKEN="agent-seat-token")
        result = self.run_cli()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.environment_agy_saw(), {
            "GH_TOKEN": None, "GITHUB_TOKEN": None, "GH_CONFIG_DIR": None})
        log = self.log.read_text()
        self.assertIn("run-gemini-task-from-brief: no read-only GitHub token (", log)
        self.assertLess(log.index("Available models"), log.index("no read-only GitHub token"))

    def test_shared_writable_subfolder_is_bound_writable_and_named_in_the_brief(self):
        self.shared_folder.parent.mkdir()
        self.env["CLAUDE_CODE_TASK_LIST_ID"] = "nedsnodes-test-seat-tasks"
        result = self.run_cli()
        self.assertEqual(result.returncode, 0, result.stderr)
        for number in ("1", "2"):
            if number == "2":
                self.calls.unlink()
                result = self.run_cli()
                self.assertEqual(result.returncode, 0, result.stderr)
            run_folder = self.shared_folder / "test-seat" / "brief" / number
            self.assertTrue(run_folder.is_dir())
            self.assertIn(f"this run's folder is {run_folder}\n", result.stderr)
            args = json.loads(self.calls.read_text().splitlines()[1])[1]
            self.assertIn(f"in this folder: {run_folder}\n", args[-1])
            prefix = json.loads(self.sandbox_calls.read_text().splitlines()[-1])
            if sys.platform == "darwin":
                self.assertIn(f'(require-not (subpath {json.dumps(str(run_folder))}))', prefix[2])
            else:
                self.assertEqual([prefix[i + 1] for i, arg in enumerate(prefix) if arg == "--bind"],
                                 [str(self.report), str(run_folder)])

    def test_run_takes_the_number_after_a_folder_already_there(self):
        brief_folder = self.shared_folder / "test-seat" / "brief"
        (brief_folder / "1").mkdir(parents=True)
        self.env["CLAUDE_CODE_TASK_LIST_ID"] = "nedsnodes-test-seat-tasks"
        result = self.run_cli()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((brief_folder / "2").is_dir())
        self.assertIn(f"this run's folder is {brief_folder / '2'}\n", result.stderr)

    def test_run_folder_taken_by_another_run_first_gets_the_next_number(self):
        # Another run creating a folder between the listing and the mkdir cannot be timed
        # from a test, so a wrapped os.mkdir creates the folder first, as that run would.
        brief_folder = self.shared_folder / "test-seat" / "brief"
        brief_folder.mkdir(parents=True)
        real_mkdir = os.mkdir
        taken_first = []

        def beaten_once(path, *rest, **options):
            if Path(path).parent == brief_folder and not taken_first:
                real_mkdir(path, *rest, **options)
                taken_first.append(Path(path).name)
            return real_mkdir(path, *rest, **options)

        def always_beaten(path, *rest, **options):
            if Path(path).parent == brief_folder:
                raise FileExistsError(path)
            return real_mkdir(path, *rest, **options)

        create = runner.codex_task.codex_or_gemini_task_run_subfolder_in_shared_writable_folder_create
        with patch.dict(os.environ, {"CLAUDE_CODE_TASK_LIST_ID": "nedsnodes-test-seat-tasks"}):
            with patch.object(runner.codex_task.os, "mkdir", beaten_once):
                self.assertEqual(create(self.brief), brief_folder / "2")
            self.assertEqual(taken_first, ["1"])
            with patch.object(runner.codex_task.os, "mkdir", always_beaten), \
                    self.assertRaisesRegex(OSError, "every numbered folder from 3 to 102"):
                create(self.brief)

    def test_two_runs_of_one_brief_without_dash_o_keep_both_reports_in_their_numbered_folders(self):
        self.shared_folder.parent.mkdir()
        self.env["CLAUDE_CODE_TASK_LIST_ID"] = "nedsnodes-test-seat-tasks"
        self.args = self.args[:4]
        brief_folder = self.shared_folder / "test-seat" / "brief"
        for number in ("1", "2"):
            report = brief_folder / number / "report.md"
            self.env["FAKE_REPORT"] = str(report)
            result = self.run_cli()
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, f"report: {report}\n")
            report.write_text(f"run {number}'s report\n")
            args = json.loads(self.calls.read_text().splitlines()[-1])[1]
            self.assertIn(f"Write the task's report to this exact file: {report}\n", args[-1])
        for number in ("1", "2"):
            run_folder = brief_folder / number
            self.assertEqual((run_folder / "report.md").read_text(), f"run {number}'s report\n")
            self.assertIn("agy stdout", (run_folder / "report.md.run.log").read_text())

    def test_run_without_dash_o_where_the_log_store_is_absent_is_refused(self):
        self.args = self.args[:4]
        result = self.run_cli()
        self.assertEqual(result.returncode, 2)
        self.assertIn("-o is required on this machine", result.stderr)
        self.assertFalse(self.calls.exists())

    def test_shared_writable_subfolder_that_cannot_be_created_stops_the_run(self):
        self.shared_folder.parent.mkdir()
        self.shared_folder.write_text("a file where the shared folder belongs")
        result = self.run_cli()
        self.assertEqual(result.returncode, 1)
        self.assertIn("creating the run's folder in the shared writable folder", result.stderr)
        self.assertFalse(self.calls.exists())

    def git(self, *words):
        return subprocess.run(["git", "-C", str(self.checkout), *words], env=self.git_env,
                              capture_output=True, text=True, check=True).stdout

    def make_checkout_a_worktree(self, with_test_suite_runner=True, with_commit=True):
        """Make -C a git worktree, with the report outside it; return its first commit."""
        self.git_env = dict(self.env)
        self.git_env.update(GIT_AUTHOR_NAME="test-seat", GIT_AUTHOR_EMAIL="test-seat@nedschorus.invalid",
                            GIT_COMMITTER_NAME="test-seat",
                            GIT_COMMITTER_EMAIL="test-seat@nedschorus.invalid")
        self.env = self.git_env
        outside_report = self.base / "report.md"
        self.args[self.args.index("-o") + 1] = str(outside_report)
        self.env["FAKE_REPORT"] = str(outside_report)
        self.git("init", "--quiet")
        (self.checkout / "existing.txt").write_text("before the run\n")
        self.git("add", "existing.txt")
        self.test_suite_runner_calls = self.base / "test-suite-runner-calls.json"
        self.env["FAKE_TEST_SUITE_RUNNER_CALLS"] = str(self.test_suite_runner_calls)
        if with_test_suite_runner:
            fake_runner = self.checkout / "scripts" / "run-all-test-suites.py"
            fake_runner.parent.mkdir()
            fake_runner.write_text(FAKE_TEST_SUITE_RUNNER.replace("#!PYTHON", "#!" + sys.executable))
            fake_runner.chmod(0o755)
            self.git("add", "scripts")
        if not with_commit:
            return None
        self.git("commit", "--quiet", "-m", "start")
        return self.git("rev-parse", "HEAD").strip()

    def run_in_worktree(self, writes, mode="report", sandbox="workspace-write", extra=()):
        self.env["FAKE_AGY_WORKTREE_WRITES"] = writes
        return self.run_cli(mode, extra=("--sandbox", sandbox, *extra))

    def test_workspace_write_run_in_a_worktree_is_committed_with_its_message(self):
        start = self.make_checkout_a_worktree()
        result = self.run_in_worktree("change,message")
        self.assertEqual(result.returncode, 0, result.stderr)
        prompt = json.loads(self.calls.read_text().splitlines()[1])[1][-1]
        self.assertIn(f"in the file {self.checkout / 'commit-message.txt'}:", prompt)
        self.assertEqual(self.git("rev-parse", "HEAD~1").strip(), start)
        self.assertEqual(self.git("log", "-1", "--format=%an|%B").strip(),
                         "test-seat|Gemini's subject\n\nGemini's body.")
        self.assertEqual(self.git("show", "--name-only", "--format=", "HEAD").split(), ["changed.txt"])
        self.assertFalse((self.checkout / "commit-message.txt").exists())
        self.assertEqual(self.git("status", "--porcelain"), "")
        self.assertIn(f"as {self.git('rev-parse', 'HEAD').strip()}", result.stderr)
        self.assertEqual(json.loads(self.test_suite_runner_calls.read_text()), [
            str(self.checkout), ["--only-suites-whose-recorded-inputs-changed-since", start,
                                 "--leave-recorded-inputs-and-failure-history-unchanged"]])
        self.assertIn("PASS scripts/a-test.py (1.0s)", result.stderr)
        self.assertEqual(result.stdout.strip(), f"report: {self.base / 'report.md'}")

    def test_test_suites_that_fail_or_give_no_verdict_after_the_commit_exit_1_keeping_it(self):
        for runner_mode, said in (
                ("fail", "failed after its commit: scripts/a-test.py, scripts/c-test.py."),
                ("no-verdict", "ended with exit 2 without naming a failing suite")):
            with self.subTest(runner_mode=runner_mode):
                shutil.rmtree(self.checkout)
                self.checkout.mkdir()
                start = self.make_checkout_a_worktree()
                self.env["FAKE_TEST_SUITE_RUNNER_MODE"] = runner_mode
                result = self.run_in_worktree("change,message")
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertEqual(self.git("rev-parse", "HEAD~1").strip(), start)
                self.assertIn("running the nn-test-suites the run's change touches", result.stderr)
                self.assertIn(said, result.stderr)
                self.assertIn("The run's commit is kept", result.stderr)
                self.assertNotIn("report:", result.stdout)

    def test_test_suite_runner_that_cannot_start_exits_1_keeping_the_commit(self):
        start = self.make_checkout_a_worktree(with_test_suite_runner=False)
        result = self.run_in_worktree("change,message")
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual(self.git("rev-parse", "HEAD~1").strip(), start)
        self.assertIn("could not start `scripts/run-all-test-suites.py", result.stderr)
        self.assertIn("no nn-test-suite was run on the commit", result.stderr)
        self.assertNotIn("report:", result.stdout)

    def test_worktree_whose_head_names_no_commit_stops_before_agy(self):
        self.make_checkout_a_worktree(with_commit=False)
        result = self.run_in_worktree("change,message")
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("could not read the commit HEAD is at", result.stderr)
        self.assertFalse(self.calls.exists())

    def test_changes_without_a_commit_message_are_listed_not_committed(self):
        start = self.make_checkout_a_worktree()
        result = self.run_in_worktree("change")
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual(self.git("rev-parse", "HEAD").strip(), start)
        self.assertIn("committing the run's changes", result.stderr)
        self.assertIn("missing or empty", result.stderr)
        self.assertIn("?? changed.txt", result.stderr)
        self.assertNotIn("report:", result.stdout)

    def test_commit_message_left_by_an_earlier_run_is_not_used(self):
        start = self.make_checkout_a_worktree()
        (self.checkout / "commit-message.txt").write_text("A stale subject from an earlier run\n")
        result = self.run_in_worktree("change")
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual(self.git("rev-parse", "HEAD").strip(), start)
        self.assertIn("missing or empty", result.stderr)
        self.assertFalse((self.checkout / "commit-message.txt").exists())

    def test_run_that_changes_nothing_commits_nothing(self):
        start = self.make_checkout_a_worktree()
        for writes in ("", "message"):
            with self.subTest(writes=writes):
                result = self.run_in_worktree(writes)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(self.git("rev-parse", "HEAD").strip(), start)
                self.assertFalse((self.checkout / "commit-message.txt").exists())
                self.assertFalse(self.test_suite_runner_calls.exists())

    def test_read_only_and_failed_runs_commit_nothing(self):
        start = self.make_checkout_a_worktree()
        for mode, sandbox, code in (("report", "read-only", 0), ("fail", "workspace-write", 1)):
            with self.subTest(mode=mode, sandbox=sandbox):
                self.calls.unlink(missing_ok=True)
                result = self.run_in_worktree("change,message", mode=mode, sandbox=sandbox)
                self.assertEqual(result.returncode, code, result.stderr)
                self.assertEqual(self.git("rev-parse", "HEAD").strip(), start)
                prompt = json.loads(self.calls.read_text().splitlines()[1])[1][-1]
                self.assertEqual("commit-message.txt" in prompt, sandbox == "workspace-write")

    def test_commit_git_refuses_keeps_changes_and_message(self):
        start = self.make_checkout_a_worktree()
        hook = self.checkout / ".git" / "hooks" / "pre-commit"
        hook.write_text("#!/bin/sh\necho 'pre-commit: refused for the test' >&2\nexit 1\n")
        hook.chmod(0o755)
        result = self.run_in_worktree("change,message")
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual(self.git("rev-parse", "HEAD").strip(), start)
        self.assertIn("could not commit the run's changes", result.stderr)
        self.assertIn("pre-commit: refused for the test", result.stderr)
        self.assertTrue((self.checkout / "commit-message.txt").exists())
        self.assertTrue((self.checkout / "changed.txt").exists())

    def test_gh_http_401_in_agy_output_is_reported_and_exit_status_kept(self):
        for mode, code in (("gh-refused", 0), ("report", 0)):
            with self.subTest(mode=mode):
                result = self.run_cli(mode)
                self.assertEqual(result.returncode, code, result.stderr)
                self.assertEqual("run-gemini-task-from-brief: read-only GitHub token refused"
                                 in result.stderr, mode == "gh-refused")

    def test_log_left_by_an_earlier_run_is_not_read_for_a_401(self):
        self.log.write_text("HTTP 401: Bad credentials (https://api.github.com/graphql)\n")
        self.brief.write_text("   ")
        result = self.run_cli()
        self.assertEqual(result.returncode, 1)
        self.assertNotIn("read-only GitHub token refused", result.stderr)

    def test_unknown_model_stops_before_task(self):
        self.assertTrue(LISTED_MODEL.startswith(PARTIAL_MODEL) and PARTIAL_MODEL != LISTED_MODEL)
        result = self.run_cli(extra=("-m", PARTIAL_MODEL))
        self.assertEqual(result.returncode, 1)
        self.assertIn("unknown model", result.stderr)
        self.assertIn(LISTED_MODEL, result.stderr)
        self.assertIn(OTHER_LISTED_MODEL, result.stderr)
        self.assertEqual(len(self.calls.read_text().splitlines()), 1)

    def test_nonzero_exits(self):
        for mode, stage, code in (("models-fail", "listing models", 4), ("fail", "running the task", 7)):
            with self.subTest(mode=mode):
                result = self.run_cli(mode)
                self.assertEqual(result.returncode, 1)
                self.assertIn(stage, result.stderr)
                self.assertIn(f"agy exited {code}", result.stderr)
                self.assertNotIn("report:", result.stdout)

    def test_no_report_and_empty_report_do_not_accept_stale_content(self):
        for mode in ("no-report", "remove-report"):
            with self.subTest(mode=mode):
                self.report.write_text("stale report")
                result = self.run_cli(mode)
                self.assertEqual(result.returncode, 1)
                self.assertIn("wrote no report", result.stderr)
                self.assertIn(str(self.log), result.stderr)
                self.assertNotIn("report:", result.stdout)

    def test_deadline_kills_children_during_discovery_and_task(self):
        for mode in ("models-sleep", "sleep"):
            with self.subTest(mode=mode):
                result = self.run_cli(mode, extra=("--deadline-minutes", "0.03"))
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertIn("deadline passed", result.stderr)
                self.assert_process_dies(int(self.child.read_text()))

    def test_result_line_ends_a_run_whose_agy_hangs_and_the_run_is_committed(self):
        start = self.make_checkout_a_worktree()
        result = self.run_in_worktree("change,message", mode="result-then-hang",
                                      extra=("--deadline-minutes", "0.25"))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(runner.agy_cell.common.AGENT_BINARY_KILLED_AFTER_FINAL_RESULT_LINE_PHRASE,
                      result.stderr)
        self.assertEqual(self.git("rev-parse", "HEAD~1").strip(), start)
        self.assertEqual(self.git("show", "--name-only", "--format=", "HEAD").split(), ["changed.txt"])
        self.assertIn('"event": "result"', self.log.read_text())
        self.assert_process_dies(int(self.child.read_text()))

    def test_result_line_status_other_than_success_fails_the_run_and_commits_nothing(self):
        start = self.make_checkout_a_worktree()
        for mode in ("result-error", "result-error-then-hang"):
            with self.subTest(mode=mode):
                result = self.run_in_worktree("change,message", mode=mode)
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertIn("result line did not report SUCCESS", result.stderr)
                self.assertEqual(self.git("rev-parse", "HEAD").strip(), start)
                self.assertNotIn("report:", result.stdout)

    def test_agy_that_exits_0_without_a_result_line_still_succeeds_on_its_report(self):
        result = self.run_cli("no-result-line")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("agy stdout", self.log.read_text())

    def test_run_with_no_result_line_is_stopped_at_the_deadline_and_commits_nothing(self):
        start = self.make_checkout_a_worktree()
        result = self.run_in_worktree("change,message", mode="no-result-line-then-hang",
                                      extra=("--deadline-minutes", "0.05"))
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("deadline passed with no result line", result.stderr)
        self.assertEqual(self.git("rev-parse", "HEAD").strip(), start)
        self.assertTrue((self.checkout / "changed.txt").exists())
        self.assert_process_dies(int(self.child.read_text()))

    def assert_process_dies(self, pid, timeout=10):
        # SIGKILL takes effect asynchronously; under load the child can still be running
        # when the launcher returns. Linux can keep a dead orphan as a zombie until PID 1 reaps it.
        deadline = time.monotonic() + timeout
        last = None
        while time.monotonic() < deadline:
            if sys.platform.startswith("linux"):
                try:
                    last = Path(f"/proc/{pid}/stat").read_text().split(") ")[-1][0]
                except FileNotFoundError:
                    return
                if last == "Z":
                    return
            else:
                try:
                    os.kill(pid, 0)
                except ProcessLookupError:
                    return
                last = "alive"
            time.sleep(0.05)
        self.fail(f"process {pid} still not dead after {timeout}s; last state {last!r}")

    def test_bad_arguments(self):
        for extra in (("--deadline-minutes", "nan"), ("--deadline-minutes", "0"),
                      ("--sandbox", "invalid"), ("--writable-root", str(self.base)),
                      ("-C", str(self.base / "absent")),
                      ("--run-log", str(self.brief)), ("-o", str(self.brief)),
                      ("--sandbox", "workspace-write", "--writable-root", str(self.base / "absent"))):
            with self.subTest(extra=extra):
                self.assertEqual(self.run_cli(extra=extra).returncode, 2)
        result = subprocess.run([sys.executable, str(PROGRAM), "--help"], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0)
        self.assertNotIn("--network", result.stdout)

    def test_effort_with_a_model_id_that_carries_one_is_refused_before_agy(self):
        for extra in (("--effort", "low"), ("--effort", "low", "-m", "gemini-4-hydrogen-xhigh"),
                      ("--effort", "high", "-m", "gemini-3.8-flash-medium")):
            with self.subTest(extra=extra):
                result = self.run_cli(extra=extra)
                self.assertEqual(result.returncode, 2)
                self.assertIn("already carries an effort", result.stderr)
                self.assertIn("gemini-pro-orchestrator", result.stderr)
                self.assertFalse(self.calls.exists())

    def test_effort_with_a_model_id_that_carries_none_is_passed_to_agy(self):
        result = self.run_cli(extra=("--effort", "xhigh", "-m", "gemini-pro-orchestrator"))
        self.assertEqual(result.returncode, 0, result.stderr)
        args = json.loads(self.calls.read_text().splitlines()[1])[1]
        self.assertEqual(args[args.index("--effort") + 1], "xhigh")
        self.assertEqual(args[args.index("--model") + 1], "gemini-pro-orchestrator")

    def test_file_failures(self):
        self.brief.unlink()
        self.assertIn("reading the brief", self.run_cli().stderr)
        self.brief.write_bytes(b'\xff')
        self.assertEqual(self.run_cli().returncode, 1)
        self.brief.write_text("   ")
        self.assertIn("brief is empty", self.run_cli().stderr)
        self.brief.write_text("task")
        self.log.mkdir()
        result = self.run_cli()
        self.assertEqual(result.returncode, 1)
        self.assertIn("preparing report", result.stderr)

    def test_missing_sandbox(self):
        for program in (None, "no-such-sandbox"):
            with patch.object(runner.agy_cell, "credential_sandbox_program", return_value=program), \
                    contextlib.redirect_stderr(io.StringIO()) as stderr:
                self.assertEqual(runner.main(self.args), 1)
                self.assertIn("required sandbox", stderr.getvalue())

    def test_start_failure(self):
        with patch.object(runner.agy_cell, "credential_sandbox_prefix", return_value=["/no/such/bwrap"]), \
                patch.object(runner.shutil, "which", return_value="bwrap"), \
                contextlib.redirect_stderr(io.StringIO()) as stderr:
            self.assertEqual(runner.main(self.args), 1)
            self.assertIn("listing models", stderr.getvalue())

    def test_sandbox_arguments_and_credential_denial_order(self):
        common = runner.agy_cell.common
        with patch.object(common, "ned_box_credential_and_login_files_present",
                          return_value=["/credentials/key", "/codex/auth.json"]) as listed:
            prefix = runner.agy_cell.credential_sandbox_prefix("linux", writable_paths=[
                (self.report, False), (self.base, True)])
            self.assertEqual(prefix, ["bwrap", "--ro-bind", "/", "/", "--dev", "/dev", "--bind", str(self.report),
                                     str(self.report), "--bind", str(self.base), str(self.base),
                                     "--ro-bind", "/dev/null", "/credentials/key",
                                     "--ro-bind", "/dev/null", "/codex/auth.json"])
            listed.assert_called_with(except_program="agy")
            legacy = runner.agy_cell.credential_sandbox_prefix("linux")
            self.assertEqual(legacy[:4], ["bwrap", "--dev-bind", "/", "/"])
        prefix = runner.agy_cell.credential_sandbox_prefix("darwin", writable_paths=[
            (Path('/report"file'), False), (Path("/data"), True)])
        self.assertEqual(prefix[:2], ["sandbox-exec", "-p"])
        self.assertIn('(require-not (literal "/report\\"file"))', prefix[2])
        self.assertIn('(require-not (subpath "/data"))', prefix[2])
        self.assertIn('(deny file-read* file-write*', prefix[2])
        self.assertEqual(runner.agy_cell.credential_sandbox_prefix("darwin"),
                         ["sandbox-exec", "-p", runner.agy_cell.sandbox_exec_profile()])


if __name__ == "__main__":
    unittest.main(verbosity=2)
