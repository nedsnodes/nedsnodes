#!/usr/bin/env python3
"""Tests for nn-systems/general-tools/nn-test-suite-start-time-line-and-end-results-line-print-common.py.

Each case runs a small suite that loads the module and ends in one way, and reads what it printed and its exit
code; the last cases run the module as a program, as a shell suite does, and check that every tracked nn-test-suite
calls it.

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
END = re.compile(r"^END \d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ passed=(\d+) failed=(\d+) (#nc_test_suite_\w+)$")
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
    return [(int(match[1]), int(match[2]), match[3]) for match in found]


PASS_TAG, FAIL_TAG, COULD_NOT_RUN_TAG = "#nc_test_suite_pass", "#nc_test_suite_fail", "#nc_test_suite_could_not_run"
try:
    completed, lines = run_suite("ends-on-its-own", "print('PASS  a')\nprint('ok c')\n")
    check("a suite that ends on its own prints START first", bool(lines) and START.match(lines[0]), lines)
    check("a suite that ends on its own prints END last, counting PASS and ok as passed, with the pass verdict, exit 0",
          completed.returncode == 0 and bool(lines) and END.match(lines[-1]) and end_counts(lines) == [(2, 0, PASS_TAG)],
          (completed.returncode, lines))

    completed, lines = run_suite("exits-one-after-a-failure", "print('PASS  a')\nprint('FAIL  b: why')\nsys.exit(1)\n")
    check("a suite that calls sys.exit(1) after a failed case prints END with the fail verdict, counting FAIL as failed, exit 1",
          completed.returncode == 1 and end_counts(lines) == [(1, 1, FAIL_TAG)], (completed.returncode, lines))

    completed, lines = run_suite(
        "raises-system-exit-in-a-function", "def end():\n    raise SystemExit(1)\nprint('FAIL  b: why')\nend()\n")
    check("a suite that raises SystemExit(1) inside a function prints END with the fail verdict, exit 1",
          completed.returncode == 1 and end_counts(lines) == [(0, 1, FAIL_TAG)], (completed.returncode, lines))

    completed, lines = run_suite("exits-with-a-message", "sys.exit('the fixture broke')\n")
    check("a suite that calls sys.exit with a message prints END with the fail verdict, exit 1",
          completed.returncode == 1 and end_counts(lines) == [(0, 0, FAIL_TAG)]
          and "the fixture broke" in completed.stderr, (completed.returncode, lines, completed.stderr))

    completed, lines = run_suite("exits-three", "print('PASS  a')\nsys.exit(3)\n")
    check("a suite that exits 3 prints END with the fail verdict and exits 1, the code the verdict gives",
          completed.returncode == 1 and end_counts(lines) == [(1, 0, FAIL_TAG)], (completed.returncode, lines))

    completed, lines = run_suite("exits-two-on-its-own", "sys.exit(2)\n")
    check("a suite that exits 2 without calling the could-not-run function fails, exit 1",
          completed.returncode == 1 and end_counts(lines) == [(0, 0, FAIL_TAG)], (completed.returncode, lines))

    completed, lines = run_suite("passes-a-child-fail-line-through", "print('FAIL  child case')\nsys.exit(0)\n")
    check("a suite that exits 0 passes, with its FAIL line counted, exit 0",
          completed.returncode == 0 and end_counts(lines) == [(0, 1, PASS_TAG)], (completed.returncode, lines))

    completed, lines = run_suite("could-not-run", "m.nn_test_suite_could_not_run_exit('no tmux on this machine')\n")
    check("a suite that calls the could-not-run function before any case prints END with the could-not-run verdict, exit 2",
          completed.returncode == 2 and end_counts(lines) == [(0, 0, COULD_NOT_RUN_TAG)]
          and "no tmux on this machine" in completed.stderr, (completed.returncode, lines, completed.stderr))

    completed, lines = run_suite(
        "could-not-run-after-a-case", "print('PASS  a')\nm.nn_test_suite_could_not_run_exit('no tmux')\n")
    check("a suite that calls the could-not-run function after a case line fails, exit 1",
          completed.returncode == 1 and end_counts(lines) == [(1, 0, FAIL_TAG)], (completed.returncode, lines))

    completed, lines = run_suite(
        "other-exit-handler", "import atexit\natexit.register(lambda: print('cleanup ran', flush=True))\nsys.exit(3)\n")
    check("a suite whose exit code the verdict changes still runs its own exit handlers first, and END is last",
          completed.returncode == 1 and lines[-2:-1] == ["cleanup ran"] and end_counts(lines) == [(0, 0, FAIL_TAG)],
          (completed.returncode, lines))

    completed, lines = run_suite("crashes-after-start", "raise RuntimeError('broken fixture')\n")
    check("a suite that raises after START prints START and no END",
          completed.returncode != 0 and any(START.match(line) for line in lines) and not end_counts(lines),
          (completed.returncode, lines, completed.stderr))
    check("a suite that raises still shows its traceback", "RuntimeError: broken fixture" in completed.stderr,
          completed.stderr)

    completed, lines = run_suite(
        "catches-its-own-system-exit", "try:\n    sys.exit(1)\nexcept SystemExit:\n    pass\nprint('PASS  a')\n")
    check("a suite that catches a SystemExit and then ends on its own passes, exit 0",
          completed.returncode == 0 and end_counts(lines) == [(1, 0, PASS_TAG)], (completed.returncode, lines))

    completed, lines = run_suite("killed-by-a-signal", "print('PASS  a')\nos.kill(os.getpid(), signal.SIGKILL)\n")
    check("a suite killed by a signal prints no END", completed.returncode < 0 and not end_counts(lines),
          (completed.returncode, lines))

    completed, lines = run_suite(
        "forks-a-child", "print('PASS  a')\nif os.fork() == 0:\n    sys.exit(0)\nos.wait()\n")
    check("a suite whose forked child exits on its own prints one END, its own",
          completed.returncode == 0 and end_counts(lines) == [(1, 0, PASS_TAG)], (completed.returncode, lines))

    completed, lines = run_suite("last-line-unended", "print('PASS  a', end='')\n")
    check("a last case line with no newline is counted, and END goes on a line of its own",
          lines[-2:-1] == ["PASS  a"] and end_counts(lines) == [(1, 0, PASS_TAG)], lines)

    completed, lines = run_suite(
        "child-process-output", "import subprocess\nsubprocess.run([sys.executable, '-c', 'print(\"PASS  child\")'])\n"
        "print('PASS  own')\n")
    check("case lines a child process writes to the shared output are not the suite's own count",
          end_counts(lines) == [(1, 0, PASS_TAG)], lines)

    completed, lines = run_suite(
        "child-run", "print('PASS  a')\n",
        {start_and_end_lines.CHILD_RUN_ENVIRONMENT_VARIABLE: "1"})
    check("a suite run as a child with the child-run variable set to 1 prints neither line",
          completed.returncode == 0 and lines == ["PASS  a"], lines)

    loaded_suite = SCRATCH / "loaded-as-a-module-test.py"
    run_suite("loaded-as-a-module", "print('PASS  a')\nsys.exit(1)\n")
    completed, lines = run_suite(
        "loads-another-suite",
        f"s = importlib.util.spec_from_file_location('other', {str(loaded_suite)!r})\n"
        "other = importlib.util.module_from_spec(s)\ntry:\n    s.loader.exec_module(other)\nexcept SystemExit:\n    pass\n"
        "print('PASS  own')\n")
    check("a suite file loaded as a module by another program prints neither line into that program's output",
          [line for line in lines if START.match(line)] == [lines[0]] and end_counts(lines) == [(2, 0, PASS_TAG)],
          (completed.returncode, lines))

    for case, arguments, exit_code, line in (
            ("a passing shell suite", ["end", "3", "0", "0"], 0, (3, 0, PASS_TAG)),
            ("a failing shell suite", ["end", "2", "1", "1"], 1, (2, 1, FAIL_TAG)),
            ("a shell suite that exits 3", ["end", "0", "0", "3"], 1, (0, 0, FAIL_TAG))):
        completed = subprocess.run([sys.executable, str(MODULE), *arguments], capture_output=True, text=True,
                                   timeout=60)
        check(f"run as a program, the module prints the END line of {case} and exits {exit_code}",
              completed.returncode == exit_code and end_counts(completed.stdout.splitlines()) == [line],
              (completed.returncode, completed.stdout))
    completed = subprocess.run([sys.executable, str(MODULE), "start"], capture_output=True, text=True, timeout=60)
    check("run as a program with start, the module prints the START line",
          completed.returncode == 0 and bool(START.match(completed.stdout.strip())), completed.stdout)
    completed = subprocess.run([sys.executable, str(MODULE), "--help"], capture_output=True, text=True, timeout=60)
    check("run as a program with --help, the module prints its usage on standard output and exits 0",
          completed.returncode == 0 and completed.stdout.startswith("usage:"), completed)
    completed = subprocess.run([sys.executable, str(MODULE), "end", "x"], capture_output=True, text=True, timeout=60)
    check("run as a program with arguments it cannot read, the module prints its usage and exits 2",
          completed.returncode == 2 and "usage:" in completed.stderr and not completed.stdout, completed)

    for verdict, exit_code in start_and_end_lines.NN_TEST_SUITE_EXIT_CODE_OF_VERDICT_HASHTAG.items():
        text = start_and_end_lines.nn_test_suite_end_line_text(4, 0, verdict)
        match = start_and_end_lines.NN_TEST_SUITE_END_LINE_REGEX.match(text)
        check(f"the END line regex reads back the {verdict} line the module prints",
              match is not None and match["verdict"] == verdict, text)

    repository_root = MODULE.parents[2]
    tracked = subprocess.run(["git", "-C", str(repository_root), "ls-files", "-z", "*-test.py", "*-test.sh"],
                             capture_output=True, text=True, timeout=60, check=True).stdout.split("\0")
    call_of_suite_kind = {".py": "nn_test_suite_start_time_line_print_now_and_end_results_line_print_at_normal_exit_register()",
                          ".sh": MODULE.name}
    missing = [path for path in tracked if path and call_of_suite_kind[Path(path).suffix]
               not in (repository_root / path).read_text(encoding="utf-8", errors="replace")]
    check("every tracked -test.py file calls the module's register function, and every -test.sh file runs the "
          "module, so its END line is there for scripts/run-all-test-suites.py to read", not missing,
          f"add the call to {missing}, as the first lines of scripts/run-all-test-suites-test.py make it")
finally:
    shutil.rmtree(SCRATCH, ignore_errors=True)

print()
if failures:
    print(f"{len(failures)} case(s) failed: {', '.join(failures)}")
    sys.exit(1)
print("all cases passed")
