#!/usr/bin/env python3
"""Restart the nn-shared-database service when a merge into ned-box's reference-checkout changes it.

Usage (git runs it from scripts/git-client-side-hooks/post-merge, in the
checkout's top directory, after every merge, a fast-forward included):
  nn-systems/nn-shared-database/nn-shared-database-service-restart-after-merge.py
      [--reference-checkout DIR]

  --reference-checkout  default /home/nedlern/Projects/nedsnodes, ned-box's
                        reference-checkout, from which the systemd user unit
                        nn-shared-database-service.service runs the service

Every checkout of the clone on both machines runs the same post-merge hook,
because core.hooksPath names the reference-checkout's hook directory. In any
checkout but ned-box's reference-checkout this program does nothing. There,
when `git diff ORIG_HEAD HEAD` names a file of NN_SHARED_DATABASE_SERVICE_RESTART_AFTER_MERGE_TRIGGER_FILES, it runs
`systemctl --user restart nn-shared-database-service.service`, so the
service runs the merged code and no person has to restart it. When the caller
has no XDG_RUNTIME_DIR, systemctl is given /run/user/<uid>, where the user
bus lives. A change to the unit file itself is not picked up this way: run the
unit's install step again.

Git ignores a post-merge hook's exit code; the merge stands either way. Git
puts this program's output on its own stderr; checkout-freshness-catch-up.py,
which fast-forwards the reference-checkout, shows it to the user when the
post-merge hook adds its #post_merge_hook_failed# line, as it does whenever
this program exits nonzero.

Exit codes: 0 outside any Git checkout, not ned-box's reference-checkout,
nothing to restart, or the restart succeeded; 1 `git rev-parse --show-toplevel`
failed for another reason, such as a GIT_DIR naming a missing directory, git
could not list the merge's changes, or the restart failed, with git's or
systemctl's error on standard error. After either git failure in ned-box's
reference-checkout, told without git by the current directory, the checkout's
top directory that git runs this program in, the service is restarted anyway
and the exit code is still 1.
"""

import argparse
import importlib.util
import os
import subprocess
import sys
from pathlib import Path

PROGRAM = "nn-systems/nn-shared-database/nn-shared-database-service-restart-after-merge.py"
UNIT_NAME = "nn-shared-database-service.service"
NN_SHARED_DATABASE_SERVICE_RESTART_AFTER_MERGE_TRIGGER_FILES = ("nn-systems/nn-shared-database/nn-shared-database-service.py",)
EXIT_DONE = 0
EXIT_FAILED = 1

_ned_box_paths_spec = importlib.util.spec_from_file_location(
    "ned_box_home_directory_and_its_mac_mount_point_path_constants_common",
    Path(__file__).resolve().parents[1] / "general-tools"
    / "ned-box-home-directory-and-its-mac-mount-point-path-constants-common.py")
ned_box_paths = importlib.util.module_from_spec(_ned_box_paths_spec)
_ned_box_paths_spec.loader.exec_module(ned_box_paths)

_git_output_spec = importlib.util.spec_from_file_location(
    "git_machine_readable_output_runner_and_parser_common",
    Path(__file__).resolve().parents[1] / "general-tools"
    / "git-machine-readable-output-runner-and-parser-common.py")
git_output = importlib.util.module_from_spec(_git_output_spec)
_git_output_spec.loader.exec_module(git_output)

NED_BOX_REFERENCE_CHECKOUT = f"{ned_box_paths.NED_BOX_HOME}/Projects/nedsnodes"

AFTER_A_GIT_FAILURE = (
    "Put right what git names, such as a GIT_DIR that names a missing directory.\n"
    "If you are a subagent, give this whole message to the agent that dispatched you.\n"
    "If you cannot put it right, tell the user, quoting this whole message.")


def in_reference_checkout_without_git(reference_checkout):
    """Whether the current directory is the reference-checkout, which git runs this program in."""
    try:
        current = os.getcwd()
    except FileNotFoundError:
        return False
    return os.path.realpath(current) == os.path.realpath(reference_checkout)


def restart_service(merge_changed_it):
    """Restart the unit, print its outcome, and return the exit code it earns."""
    # An agent's Stop hook can run this merge without XDG_RUNTIME_DIR, and
    # systemctl --user then cannot find the user bus, which lives there.
    environment = {**os.environ}
    environment.setdefault("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")
    restarted = subprocess.run(["systemctl", "--user", "restart", UNIT_NAME],
                               capture_output=True, text=True, env=environment)
    if restarted.returncode != 0:
        reason = "the merge changed the nn-shared-database service, and " if merge_changed_it else ""
        print(f"{PROGRAM}: FAILED — {reason}"
              f"`systemctl --user restart {UNIT_NAME}` exited {restarted.returncode}, so the "
              f"service may still run the code from before the merge, or not run at all. "
              f"systemctl said: {restarted.stderr.strip()}\n"
              f"If systemctl said the unit was not found, the unit's install step has not "
              f"run on ned-box yet; it is the user's, so do nothing.\n"
              f"Otherwise run `journalctl --user -u {UNIT_NAME} -n 50` on ned-box and tell the "
              f"user that the nn-shared-database service failed to restart after a merge, "
              f"quoting systemctl's line above and journalctl's last lines. If you are a "
              f"subagent, tell the agent that dispatched you instead, with the same quotes.",
              file=sys.stderr)
        return EXIT_FAILED
    if merge_changed_it:
        print(f"{PROGRAM}: restarted {UNIT_NAME}, since the merge changed the service")
    else:
        print(f"{PROGRAM}: restarted {UNIT_NAME}, which is safe whether or not the merge changed it")
    return EXIT_DONE


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--reference-checkout", default=NED_BOX_REFERENCE_CHECKOUT)
    arguments = parser.parse_args(argv)
    # LC_ALL=C keeps git's message in English, so the outside-a-checkout case can be told apart.
    top = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True,
                         env={**os.environ, "LC_ALL": "C"})
    if top.returncode != 0:
        if git_output.git_stderr_says_outside_a_repository(top.stderr):
            return EXIT_DONE
        failed = (f"{PROGRAM}: FAILED — `git rev-parse --show-toplevel` exited {top.returncode} "
                  f"for a reason other than the current directory being outside any Git checkout")
        git_said = git_output.git_stderr_first_error_message_else_last_line(top.stderr)
        if not in_reference_checkout_without_git(arguments.reference_checkout):
            print(f"{failed}; this is not ned-box's reference-checkout, so the "
                  f"nn-shared-database service needs no restart. git said: {git_said}\n"
                  f"{AFTER_A_GIT_FAILURE}", file=sys.stderr)
            return EXIT_FAILED
        print(f"{failed}, so this program could not tell whether this merge changed the "
              f"nn-shared-database service, and restarts the service below, which is safe "
              f"either way. git said: {git_said}\n{AFTER_A_GIT_FAILURE}", file=sys.stderr)
        restart_service(merge_changed_it=False)
        return EXIT_FAILED
    if os.path.realpath(top.stdout.strip()) != os.path.realpath(arguments.reference_checkout):
        return EXIT_DONE
    changed = subprocess.run(["git", "diff", "--name-only", "ORIG_HEAD", "HEAD", "--",
                              *NN_SHARED_DATABASE_SERVICE_RESTART_AFTER_MERGE_TRIGGER_FILES], capture_output=True, text=True)
    if changed.returncode != 0:
        print(f"{PROGRAM}: FAILED — `git diff --name-only ORIG_HEAD HEAD` in "
              f"{arguments.reference_checkout} exited {changed.returncode}, so this merge's "
              f"changes to the nn-shared-database service are unknown, and this program "
              f"restarts the service below, which is safe either way: {changed.stderr.strip()}\n"
              f"{AFTER_A_GIT_FAILURE}", file=sys.stderr)
        restart_service(merge_changed_it=False)
        return EXIT_FAILED
    if not changed.stdout.strip():
        return EXIT_DONE
    return restart_service(merge_changed_it=True)


if __name__ == "__main__":
    sys.exit(main())
