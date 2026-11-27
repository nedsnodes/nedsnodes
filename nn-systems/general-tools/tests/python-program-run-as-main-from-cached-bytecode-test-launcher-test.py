#!/usr/bin/env python3
"""Tests for nn-systems/general-tools/python-program-run-as-main-from-cached-bytecode-test-launcher.py.

Each case runs a small program of its own both directly, as `python3 <program>`, and through the launcher,
and compares what the program saw and how it ended.

Run: python3 nn-systems/general-tools/tests/python-program-run-as-main-from-cached-bytecode-test-launcher-test.py
Prints one line per case and exits non-zero if any case fails.
"""

import importlib.util
import pathlib

_start_and_end_lines_spec = importlib.util.spec_from_file_location(
    "nn_test_suite_start_time_line_and_end_results_line_print_common",
    pathlib.Path(__file__).resolve().parents[3] / "nn-systems/general-tools/nn-test-suite-start-time-line-and-end-results-line-print-common.py")
_start_and_end_lines = importlib.util.module_from_spec(_start_and_end_lines_spec)
_start_and_end_lines_spec.loader.exec_module(_start_and_end_lines)
_start_and_end_lines.nn_test_suite_start_time_line_print_now_and_end_results_line_print_at_normal_exit_register()

import os
import signal
import subprocess
import sys
import tempfile
from pathlib import Path

LAUNCHER = (Path(__file__).resolve().parents[1]
            / "python-program-run-as-main-from-cached-bytecode-test-launcher.py")

# Prints what a program run as a script sees of itself, then ends as its first argument says.
PROBE = r'''import os, pickle, signal, sys
class Picklable: pass
print(repr((__name__, __spec__, sys.argv, __file__, sys.path[0], type(__loader__).__name__,
            type(pickle.loads(pickle.dumps(Picklable()))).__module__)), flush=True)
how = sys.argv[1] if len(sys.argv) > 1 else "0"
if how == "raise":
    raise ValueError("the probe raised")
if how == "sigterm":
    os.kill(os.getpid(), signal.SIGTERM)
sys.exit(int(how))
'''

failures = 0


def check(name, condition, detail=None):
    global failures
    if condition:
        print(f"PASS  {name}")
    else:
        failures += 1
        print(f"FAIL  {name}: {detail!r}")


# Reviewers set the first and a mutant run sets the second; either keeps the cache out of the probe's __pycache__.
CHILD_ENVIRONMENT = {name: value for name, value in os.environ.items()
                     if name not in ("PYTHONDONTWRITEBYTECODE", "PYTHONPYCACHEPREFIX")}


def run(*command, cwd):
    return subprocess.run([sys.executable, *map(str, command)], capture_output=True, text=True, cwd=cwd,
                          env=CHILD_ENVIRONMENT)


with tempfile.TemporaryDirectory() as scratch:
    root = Path(scratch)
    (root / "real").mkdir()
    (root / "real" / "probe.py").write_text(PROBE)
    # Through a link, so sys.path[0] must be the link's target directory, as a direct run makes it.
    (root / "link").symlink_to(root / "real")

    for how, expected_code in (("0", 0), ("3", 3), ("raise", 1), ("sigterm", -signal.SIGTERM)):
        direct = run("link/probe.py", how, cwd=root)
        launched = run(LAUNCHER, "link/probe.py", how, cwd=root)
        check(f"a program that ends with {how!r} sees itself and ends the same way through the launcher",
              launched.stdout == direct.stdout != "" and launched.returncode == direct.returncode == expected_code,
              (direct.returncode, direct.stdout, launched.returncode, launched.stdout, launched.stderr))
    # From a working directory reached through a link, as under a TMPDIR that is one: a direct run names the
    # program by the working directory with its links resolved, so the launcher must too.
    (root / "linked-root").symlink_to(root)
    direct_frame = next((line for line in run("link/probe.py", "raise", cwd=root / "linked-root").stderr.splitlines()
                         if 'probe.py", line' in line), "no frame")
    raised = run(LAUNCHER, "link/probe.py", "raise", cwd=root / "linked-root")
    check("an uncaught exception prints the program's own frame, as a direct run names it, and its exception",
          direct_frame.startswith('  File "') and direct_frame in raised.stderr.splitlines()
          and raised.stderr.rstrip().endswith("ValueError: the probe raised"), (direct_frame, raised.stderr))

    safe = run("-P", LAUNCHER, "link/probe.py", cwd=root)
    check("under -P the launcher leaves sys.path[0] as Python set it, as a direct run with -P does",
          safe.stdout == run("-P", "link/probe.py", cwd=root).stdout != "", (safe.stdout, safe.stderr))

    cached = list((root / "real" / "__pycache__").glob("probe.*.pyc"))
    check("a run through the launcher leaves the program's bytecode in its __pycache__", len(cached) == 1, cached)
    # A source no one may read: only a run that takes the cached bytecode can still start the program.
    os.chmod(root / "real" / "probe.py", 0)
    try:
        unreadable_direct = run("link/probe.py", cwd=root)
        unreadable_launched = run(LAUNCHER, "link/probe.py", cwd=root)
    finally:
        os.chmod(root / "real" / "probe.py", 0o644)
    if unreadable_direct.returncode == 0:
        # A process that can read any file, such as one run as root, cannot show which run used the cache.
        print("SKIP  a later run through the launcher takes the cached bytecode: this process reads unreadable files")
    else:
        check("a later run through the launcher takes the cached bytecode, not the source",
              unreadable_launched.returncode == 0, (unreadable_launched.returncode, unreadable_launched.stderr))

    no_program = run(LAUNCHER, cwd=root)
    check("the launcher given no program runs nothing, exits 2 and says to give the program's path first",
          no_program.returncode == 2 and no_program.stdout == ""
          and "it was given no program" in no_program.stderr
          and "Give the program's path first" in no_program.stderr,
          (no_program.returncode, no_program.stderr))

print(f"{failures} failed" if failures else "all cases passed")
sys.exit(1 if failures else 0)
