#!/usr/bin/env python3
"""Tests for nn-systems/general-tools/nn-test-suite-start-time-line-and-end-results-line-print-common.py.

Each case runs a small suite that loads the module and ends in one way, and reads what it printed.

Run: python3 nn-systems/general-tools/tests/nn-test-suite-start-time-line-and-end-results-line-print-common-test.py
"""

import importlib.util
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1] / "nn-test-suite-start-time-line-and-end-results-line-print-common.py"
_spec = importlib.util.spec_from_file_location("nn_test_suite_start_time_line_and_end_results_line_print_common", MODULE)
start_and_end_lines = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(start_and_end_lines)
start_and_end_lines.nn_test_suite_start_time_line_print_now_and_end_results_line_print_at_normal_exit_register()

START = re.compile(r"^START \d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$")
END = re.compile(r"^END \d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ passed=(\d+) failed=(\d+)$")
SCRATCH = Path(tempfile.mkdtemp(prefix="nn-test-suite-start-time-line-and-end-results-line-print-common-test-"))
failures = []


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


def run_suite(name, body, environment=None):
    path = SCRATCH / f"{name}-test.py"
    path.write_text(
        "import importlib.util, os, signal, sys\n"
        f"spec = importlib.util.spec_from_file_location('m', {str(MODULE)!r})\n"
        "m = importlib.util.module_from_spec(spec)\n"
        "spec.loader.exec_module(m)\n"
        "m.nn_test_suite_start_time_line_print_now_and_end_results_line_print_at_normal_exit_register()\n" + body)
    completed = subprocess.run([sys.executable, "-u", str(path)], capture_output=True, text=True, timeout=60,
                               env=None if environment is None else {**os.environ, **environment})
    return completed, completed.stdout.splitlines()


def end_counts(lines):
    found = [END.match(line) for line in lines if END.match(line)]
    return [(int(match[1]), int(match[2])) for match in found]


try:
    completed, lines = run_suite("ends-on-its-own", "print('PASS  a')\nprint('FAIL  b: why')\nprint('ok c')\n")
    check("a suite that ends on its own prints START first", bool(lines) and START.match(lines[0]), lines)
    check("a suite that ends on its own prints END last, counting PASS and ok as passed and FAIL as failed",
          bool(lines) and END.match(lines[-1]) and end_counts(lines) == [(2, 1)], lines)

    completed, lines = run_suite("exits-one-after-a-failure", "print('FAIL  b: why')\nsys.exit(1)\n")
    check("a suite that calls sys.exit(1) after a failed case still prints END, exit 1",
          completed.returncode == 1 and end_counts(lines) == [(0, 1)], (completed.returncode, lines))

    completed, lines = run_suite("crashes-after-start", "raise RuntimeError('broken fixture')\n")
    check("a suite that raises after START prints START and no END",
          completed.returncode != 0 and any(START.match(line) for line in lines) and not end_counts(lines),
          (completed.returncode, lines, completed.stderr))
    check("a suite that raises still shows its traceback", "RuntimeError: broken fixture" in completed.stderr,
          completed.stderr)

    completed, lines = run_suite("killed-by-a-signal", "print('PASS  a')\nos.kill(os.getpid(), signal.SIGKILL)\n")
    check("a suite killed by a signal prints no END", completed.returncode < 0 and not end_counts(lines),
          (completed.returncode, lines))

    completed, lines = run_suite(
        "forks-a-child", "print('PASS  a')\nif os.fork() == 0:\n    sys.exit(0)\nos.wait()\n")
    check("a suite whose forked child exits on its own prints one END, its own",
          completed.returncode == 0 and end_counts(lines) == [(1, 0)], (completed.returncode, lines))

    completed, lines = run_suite("last-line-unended", "print('PASS  a', end='')\n")
    check("a last case line with no newline is counted, and END goes on a line of its own",
          lines[-2:-1] == ["PASS  a"] and end_counts(lines) == [(1, 0)], lines)

    completed, lines = run_suite(
        "child-process-output", "import subprocess\nsubprocess.run([sys.executable, '-c', 'print(\"PASS  child\")'])\n"
        "print('PASS  own')\n")
    check("case lines a child process writes to the shared output are not the suite's own count",
          end_counts(lines) == [(1, 0)], lines)

    completed, lines = run_suite(
        "child-run", "print('PASS  a')\n",
        {start_and_end_lines.CHILD_RUN_ENVIRONMENT_VARIABLE: "1"})
    check("a suite run as a child with the child-run variable set to 1 prints neither line",
          completed.returncode == 0 and lines == ["PASS  a"], lines)

    loaded_suite = SCRATCH / "loaded-as-a-module-test.py"
    run_suite("loaded-as-a-module", "print('PASS  a')\n")
    completed, lines = run_suite(
        "loads-another-suite",
        f"s = importlib.util.spec_from_file_location('other', {str(loaded_suite)!r})\n"
        "other = importlib.util.module_from_spec(s)\ns.loader.exec_module(other)\nprint('PASS  own')\n")
    check("a suite file loaded as a module by another program prints neither line into that program's output",
          [line for line in lines if START.match(line)] == [lines[0]] and end_counts(lines) == [(2, 0)], lines)
finally:
    shutil.rmtree(SCRATCH, ignore_errors=True)

print()
if failures:
    print(f"{len(failures)} case(s) failed: {', '.join(failures)}")
    sys.exit(1)
print("all cases passed")
