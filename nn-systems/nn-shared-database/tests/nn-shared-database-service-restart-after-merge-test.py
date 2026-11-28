#!/usr/bin/env python3
"""Tests for nn-systems/nn-shared-database/nn-shared-database-service-restart-after-merge.py
and scripts/git-client-side-hooks/post-merge, which runs it.

Each case fast-forwards a temporary repository and runs the program in it, with
a fake `systemctl` on PATH that records its arguments and succeeds, fails with
systemd's unit-not-found error, or fails otherwise, on request, and a fake
`journalctl` that prints lines, prints none, fails or hangs, on request: a
merge that changes the service restarts the unit, one that does not leaves it,
and a checkout that is not the reference-checkout is left alone. A failed
restart exits 1; its message is checked word for word, in the unit-not-found
form, and otherwise with journalctl's lines or with each way journalctl can
give none, its absence from PATH included. When git fails to
list the merge's changes, or to find the checkout for a reason other than
being outside one, the program exits 1 and, in the reference-checkout only,
restarts the unit anyway; each such message is checked word for word, with
the restart succeeding and failing. One case checks that the trigger files
name the service file and exist. A last case merges through the real post-merge hook in
a checkout that is not ned-box's reference-checkout, with nothing on stderr.

Run: python3 nn-systems/nn-shared-database/tests/nn-shared-database-service-restart-after-merge-test.py
Prints one line per case and exits non-zero if any case fails.
"""

import importlib.util
import io
import os
import subprocess
import tempfile
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
PROGRAM_PATH = (REPOSITORY_ROOT / "nn-systems" / "nn-shared-database"
                / "nn-shared-database-service-restart-after-merge.py")
HOOKS_DIRECTORY = REPOSITORY_ROOT / "scripts" / "git-client-side-hooks"
_spec = importlib.util.spec_from_file_location("nn_shared_database_service_restart_after_merge",
                                               PROGRAM_PATH)
restarter = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(restarter)

_git_environment_fixture_spec = importlib.util.spec_from_file_location(
    "git_redirecting_environment_removal_test_fixture",
    REPOSITORY_ROOT / "scripts" / "git-redirecting-environment-removal-test-fixture.py")
_git_environment_fixture = importlib.util.module_from_spec(_git_environment_fixture_spec)
_git_environment_fixture_spec.loader.exec_module(_git_environment_fixture)
_git_environment_fixture.remove_git_redirecting_environment_variables_from_this_process()

SERVICE_FILE = "nn-systems/nn-shared-database/nn-shared-database-service.py"
failures = 0


def check(name, condition, detail=None):
    global failures
    if condition:
        print(f"PASS  {name}")
    else:
        failures += 1
        print(f"FAIL  {name}: {detail!r}")


FAKE_SYSTEMCTL = """#!/bin/sh
if [ -z "$XDG_RUNTIME_DIR" ]; then
  echo "Failed to connect to user scope bus via local transport: No such file or directory" >&2
  exit 1
fi
echo "$@" >> "$FAKE_SYSTEMCTL_LOG"
echo "$XDG_RUNTIME_DIR" >> "$FAKE_SYSTEMCTL_LOG.runtime"
if [ "$FAKE_SYSTEMCTL_FAIL" = not-found ]; then
  echo "Failed to restart nn-shared-database-service.service: Unit nn-shared-database-service.service not found." >&2
  exit 5
fi
if [ "$FAKE_SYSTEMCTL_FAIL" = other ]; then
  echo "Job for nn-shared-database-service.service failed because the control process exited with error code." >&2
  exit 1
fi
"""

FAKE_JOURNALCTL = """#!/bin/sh
echo "$@" >> "$FAKE_JOURNALCTL_LOG"
echo "$XDG_RUNTIME_DIR" >> "$FAKE_JOURNALCTL_LOG.runtime"
case "$FAKE_JOURNALCTL_MODE" in
  fail) echo "Failed to open journal: Permission denied" >&2; exit 1 ;;
  hang) exec sleep 10 ;;
  empty) exit 0 ;;
esac
echo "Nov 27 10:00:00 ned-box python3[123]: Traceback (most recent call last):"
echo "Nov 27 10:00:01 ned-box systemd[1]: nn-shared-database-service.service: Failed with result 'exit-code'."
"""

with tempfile.TemporaryDirectory() as scratch:
    scratch = Path(scratch)
    bin_directory = scratch / "bin"
    bin_directory.mkdir()
    (bin_directory / "systemctl").write_text(FAKE_SYSTEMCTL, encoding="utf-8")
    (bin_directory / "systemctl").chmod(0o755)
    (bin_directory / "journalctl").write_text(FAKE_JOURNALCTL, encoding="utf-8")
    (bin_directory / "journalctl").chmod(0o755)
    systemctl_log = scratch / "systemctl.log"
    journalctl_log = scratch / "journalctl.log"
    os.environ.update(PATH=f"{bin_directory}:{os.environ['PATH']}",
                      FAKE_SYSTEMCTL_LOG=str(systemctl_log),
                      FAKE_JOURNALCTL_LOG=str(journalctl_log), GIT_AUTHOR_NAME="test",
                      GIT_AUTHOR_EMAIL="test@test.invalid", GIT_COMMITTER_NAME="test",
                      GIT_COMMITTER_EMAIL="test@test.invalid", GIT_CONFIG_GLOBAL="/dev/null",
                      GIT_CONFIG_NOSYSTEM="1")
    repository = scratch / "clone"

    def git(*arguments, hooks="/dev/null"):
        return subprocess.run(["git", "-c", f"core.hooksPath={hooks}", *arguments],
                              cwd=repository, capture_output=True, text=True, check=False)

    def commit_on_branch(branch, path, text):
        git("checkout", "-q", "-B", branch, "main")
        target = repository / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
        git("add", path)
        git("commit", "-q", "-m", f"change {path}")
        git("checkout", "-q", "main")

    def run(reference=None, fail="", directory=None, environment=None, journal=""):
        for log in (systemctl_log, journalctl_log, Path(f"{journalctl_log}.runtime")):
            if log.exists():
                log.unlink()
        os.environ["FAKE_SYSTEMCTL_FAIL"] = fail
        os.environ["FAKE_JOURNALCTL_MODE"] = journal
        os.environ.update(environment or {})
        printed, errors = io.StringIO(), io.StringIO()
        before = os.getcwd()
        os.chdir(directory or repository)
        try:
            with redirect_stdout(printed), redirect_stderr(errors):
                code = restarter.main(["--reference-checkout", str(reference or repository)])
        finally:
            os.chdir(before)
            for name in environment or {}:
                del os.environ[name]
        calls = systemctl_log.read_text().splitlines() if systemctl_log.exists() else []
        return code, calls, printed.getvalue(), errors.getvalue()

    subprocess.run(["git", "init", "-q", "-b", "main", str(repository)], check=True)
    git("commit", "-q", "--allow-empty", "-m", "start")

    program = restarter.PROGRAM
    restart_call = ["--user restart nn-shared-database-service.service"]
    after_a_git_failure = (
        "Put right what git names, such as a GIT_DIR that names a missing directory.\n"
        "If you are a subagent, give this whole message to the agent that dispatched you.\n"
        "If you cannot put it right, tell the user, quoting this whole message.\n")
    restarted_either_way = (f"{program}: restarted nn-shared-database-service.service, which is "
                            f"safe whether or not the merge changed it\n")
    journal_command = ("`journalctl --user -u nn-shared-database-service.service -n 50 "
                       "--no-pager`")
    journal_lines = (
        f"{journal_command} printed:\n"
        "  Nov 27 10:00:00 ned-box python3[123]: Traceback (most recent call last):\n"
        "  Nov 27 10:00:01 ned-box systemd[1]: nn-shared-database-service.service: Failed with "
        "result 'exit-code'.\n")
    journal_call = ["--user -u nn-shared-database-service.service -n 50 --no-pager"]

    def restart_failed(merge_changed_it, journal_text=journal_lines):
        """The other-failure message; the report line takes its recipient from the shared module."""
        reason = "the merge changed the nn-shared-database service, and " if merge_changed_it else ""
        return (f"{program}: FAILED — {reason}`systemctl --user restart "
                f"nn-shared-database-service.service` exited 1, so the service may still run the "
                f"code from before the merge, or not run at all. systemctl said: Job for "
                f"nn-shared-database-service.service failed because the control process exited "
                f"with error code.\n"
                f"{journal_text}"
                f"Tell {restarter.wording.REPORT_RECIPIENT_PHRASE_USER_OR_DISPATCHING_AGENT} that "
                f"the nn-shared-database service failed to restart after a merge, quoting this "
                f"whole message.\n")
    restart_failed_after_a_git_failure = restart_failed(merge_changed_it=False)

    git_diff_failed = (
        f"{program}: FAILED — `git diff --name-only ORIG_HEAD HEAD` in {repository} exited 128, "
        f"so this merge's changes to the nn-shared-database service are unknown, and this "
        f"program restarts the service below, which is safe either way: fatal: bad revision "
        f"'ORIG_HEAD'\n"
        f"{after_a_git_failure}")
    code, calls, printed, errors = run()
    check("git failing to list the merge's changes (no ORIG_HEAD): exit 1, the FAILED message "
          "word for word, then the restart, and its success line",
          code == 1 and calls == restart_call and errors == git_diff_failed
          and printed == restarted_either_way, (code, calls, printed, errors))
    code, calls, printed, errors = run(fail="other")
    check("git failing to list the merge's changes, and the restart failing: exit 1, the FAILED "
          "message, then the restart failure that does not say the merge changed the service",
          code == 1 and calls == restart_call
          and errors == git_diff_failed + restart_failed_after_a_git_failure
          and printed == "",
          (code, calls, printed, errors))

    commit_on_branch("docs", "README.md", "words")
    git("merge", "-q", "--ff-only", "docs")
    code, calls, printed, errors = run()
    check("a merge that does not change the service restarts nothing",
          code == 0 and calls == [] and errors == "", (code, calls, errors))

    commit_on_branch("service", SERVICE_FILE, "print('new')")
    git("merge", "-q", "--ff-only", "service")
    code, calls, printed, errors = run(reference=scratch / "elsewhere")
    check("in a checkout that is not the reference-checkout nothing is restarted",
          code == 0 and calls == [] and printed == "", (code, calls))
    code, calls, printed, errors = run()
    check("a fast-forward that changes the service restarts the unit",
          code == 0 and calls == ["--user restart nn-shared-database-service.service"]
          and "restarted" in printed, (code, calls, errors))
    saved_runtime_directory = os.environ.pop("XDG_RUNTIME_DIR", None)
    runtime_log = Path(f"{systemctl_log}.runtime")
    try:
        code, calls, printed, errors = run()
    finally:
        if saved_runtime_directory is not None:
            os.environ["XDG_RUNTIME_DIR"] = saved_runtime_directory
    check("a caller without XDG_RUNTIME_DIR, as an agent's Stop hook can be, still restarts "
          "the unit, with systemctl given /run/user/<uid>",
          code == 0 and calls == ["--user restart nn-shared-database-service.service"]
          and runtime_log.read_text().splitlines()[-1] == f"/run/user/{os.getuid()}",
          (code, calls, errors))
    os.environ["XDG_RUNTIME_DIR"] = str(scratch / "runtime")
    try:
        code, calls, printed, errors = run()
    finally:
        if saved_runtime_directory is None:
            os.environ.pop("XDG_RUNTIME_DIR")
        else:
            os.environ["XDG_RUNTIME_DIR"] = saved_runtime_directory
    check("a caller's own XDG_RUNTIME_DIR is passed to systemctl unchanged",
          code == 0 and runtime_log.read_text().splitlines()[-1] == str(scratch / "runtime"),
          (code, errors))
    code, calls, printed, errors = run(fail="not-found")
    check("after a merge that changed the service, systemctl saying the unit was not found: exit 1, "
          "the unit-not-found message word for word, and journalctl not run",
          code == 1 and calls == restart_call and not journalctl_log.exists()
          and errors == (f"{program}: FAILED — the merge changed the nn-shared-database service, "
                         f"and `systemctl --user restart nn-shared-database-service.service` "
                         f"exited 5, because ned-box's systemd has no unit of that name: the "
                         f"unit's install step has not run on ned-box yet. systemctl said: Failed "
                         f"to restart nn-shared-database-service.service: Unit "
                         f"nn-shared-database-service.service not found.\n"
                         f"Do nothing about it: the install step is the user's to run.\n"),
          (code, errors))
    saved_runtime_directory = os.environ.pop("XDG_RUNTIME_DIR", None)
    try:
        code, calls, printed, errors = run(fail="other")
    finally:
        if saved_runtime_directory is not None:
            os.environ["XDG_RUNTIME_DIR"] = saved_runtime_directory
    journal_runtime_log = Path(f"{journalctl_log}.runtime")
    check("after a merge that changed the service, a restart failing otherwise: exit 1, the "
          "message word for word with journalctl's last lines indented, and journalctl given "
          "/run/user/<uid> when the caller has no XDG_RUNTIME_DIR",
          code == 1 and errors == restart_failed(merge_changed_it=True)
          and journalctl_log.read_text().splitlines() == journal_call
          and journal_runtime_log.read_text().splitlines() == [f"/run/user/{os.getuid()}"],
          (code, errors))
    code, calls, printed, errors = run(fail="other", journal="fail")
    check("journalctl failing: exit 1, and the message says so in place of its lines",
          code == 1 and errors == restart_failed(
              True, f"{journal_command} exited 1, so its lines are not shown. journalctl said: "
                    f"Failed to open journal: Permission denied\n"), (code, errors))
    code, calls, printed, errors = run(fail="other", journal="empty")
    check("journalctl printing nothing: exit 1, and the message says it printed no lines",
          code == 1 and errors == restart_failed(True, f"{journal_command} printed no lines.\n"),
          (code, errors))
    saved_timeout = restarter.JOURNALCTL_TIMEOUT_SECONDS
    restarter.JOURNALCTL_TIMEOUT_SECONDS = 1
    try:
        code, calls, printed, errors = run(fail="other", journal="hang")
    finally:
        restarter.JOURNALCTL_TIMEOUT_SECONDS = saved_timeout
    check("journalctl not finishing within its timeout: exit 1, and the message says so",
          code == 1 and errors == restart_failed(
              True, f"{journal_command} did not finish within 1 seconds, so its lines are not "
                    f"shown.\n"), (code, errors))
    # Only the fake systemctl's directory on PATH, so no journalctl is found anywhere.
    hidden_journalctl = scratch / "journalctl-hidden"
    (bin_directory / "journalctl").rename(hidden_journalctl)
    saved_path = os.environ["PATH"]
    os.environ.update(PATH=str(bin_directory), FAKE_SYSTEMCTL_FAIL="other")
    errors = io.StringIO()
    try:
        with redirect_stderr(errors):
            code = restarter.restart_service(merge_changed_it=True)
    finally:
        os.environ["PATH"] = saved_path
        hidden_journalctl.rename(bin_directory / "journalctl")
    errors = errors.getvalue()
    check("journalctl not on PATH: exit 1, and the message says it could not be run, with the "
          "operating system's error",
          code == 1 and errors == restart_failed(
              True, f"{journal_command} could not be run, so its lines are not shown: [Errno 2] "
                    f"No such file or directory: 'journalctl'\n"), (code, errors))

    outside = scratch / "not-a-repository"
    outside.mkdir()
    before = os.getcwd()
    os.chdir(outside)
    try:
        code = restarter.main(["--reference-checkout", str(outside)])
    finally:
        os.chdir(before)
    check("outside any git checkout nothing is done", code == 0, code)

    stale_git_directory = scratch / "stale-git-directory"
    stale = {"GIT_DIR": str(stale_git_directory)}
    rev_parse_failed = ("`git rev-parse --show-toplevel` exited 128 for a reason other than the "
                        "current directory being outside any Git checkout")
    in_reference = (f"{program}: FAILED — {rev_parse_failed}, so this program could not tell "
                    f"whether this merge changed the nn-shared-database service, and restarts "
                    f"the service below, which is safe either way. git said: fatal: not a git "
                    f"repository: '{stale_git_directory}'\n{after_a_git_failure}")
    code, calls, printed, errors = run(environment=stale)
    check("a stale GIT_DIR in the reference-checkout: exit 1, the FAILED message word for word, "
          "then the restart, and its success line",
          code == 1 and calls == restart_call and errors == in_reference
          and printed == restarted_either_way, (code, calls, printed, errors))
    code, calls, printed, errors = run(environment=stale, fail="other")
    check("a stale GIT_DIR in the reference-checkout, and the restart failing: exit 1, the "
          "FAILED message, then the restart failure that does not say the merge changed the "
          "service",
          code == 1 and calls == restart_call
          and errors == in_reference + restart_failed_after_a_git_failure
          and printed == "",
          (code, calls, printed, errors))

    def not_reference(git_error):
        return (f"{program}: FAILED — {rev_parse_failed}; this is not ned-box's "
                f"reference-checkout, so the nn-shared-database service needs no restart. git "
                f"said: {git_error}\n{after_a_git_failure}")
    code, calls, printed, errors = run(reference=scratch / "elsewhere", environment=stale)
    check("a stale GIT_DIR in a checkout that is not the reference-checkout: exit 1, the "
          "FAILED message word for word, and nothing restarted",
          code == 1 and calls == [] and printed == ""
          and errors == not_reference(f"fatal: not a git repository: '{stale_git_directory}'"),
          (code, calls, printed, errors))

    removed = scratch / "removed"
    removed.mkdir()
    before = os.getcwd()
    os.chdir(removed)
    removed.rmdir()
    if systemctl_log.exists():
        systemctl_log.unlink()
    errors = io.StringIO()
    try:
        with redirect_stderr(errors):
            code = restarter.main(["--reference-checkout", str(removed)])
    finally:
        os.chdir(before)
    errors = errors.getvalue()
    check("a removed current directory counts as not the reference-checkout, even when "
          "--reference-checkout names it: exit 1, and nothing restarted",
          code == 1 and not systemctl_log.exists()
          and errors == not_reference("fatal: Unable to read current working directory: No "
                                      "such file or directory"), (code, errors))

    code, calls, printed, errors = run(
        reference=scratch / "elsewhere",
        environment={"GIT_CONFIG_COUNT": "1", "GIT_CONFIG_KEY_0": "core.bare",
                     "GIT_CONFIG_VALUE_0": "not a git repository"})
    check("a git error that quotes the words \"not a git repository\", such as a bad config "
          "value, is FAILED with exit 1, not taken for being outside a checkout",
          code == 1 and calls == []
          and "git said: fatal: bad boolean config value 'not a git repository'" in errors,
          (code, errors))

    check("the reference-checkout by default is ned-box's",
          restarter.NED_BOX_REFERENCE_CHECKOUT == "/home/nedlern/Projects/nedsnodes")

    trigger_files = restarter.NN_SHARED_DATABASE_SERVICE_RESTART_AFTER_MERGE_TRIGGER_FILES
    check("the merge restarts the service when the service file changes: the trigger files "
          "name it, and each is a file of the repository",
          SERVICE_FILE in trigger_files
          and all((REPOSITORY_ROOT / f).is_file() for f in trigger_files),
          trigger_files)

    unit_text = (REPOSITORY_ROOT / "nn-systems" / "nn-shared-database"
                 / "nn-shared-database-service.service").read_text(encoding="utf-8")
    exec_start = [line for line in unit_text.splitlines() if line.startswith("ExecStart=")]
    check("the unit's ExecStart runs the service file in ned-box's reference-checkout",
          exec_start == [f"ExecStart=/usr/bin/python3 {restarter.NED_BOX_REFERENCE_CHECKOUT}/"
                         f"{SERVICE_FILE}"], exec_start)

    commit_on_branch("service-again", SERVICE_FILE, "print('newer')")
    if systemctl_log.exists():
        systemctl_log.unlink()
    merged = git("merge", "--ff-only", "service-again", hooks=str(HOOKS_DIRECTORY))
    check("through the real post-merge hook, a merge in a checkout that is not ned-box's "
          "reference-checkout succeeds and restarts nothing",
          merged.returncode == 0 and merged.stderr == "" and not systemctl_log.exists()
          and git("rev-parse", "HEAD").stdout == git("rev-parse", "service-again").stdout,
          (merged.returncode, merged.stdout, merged.stderr))

raise SystemExit(1 if failures else 0)
