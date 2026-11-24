#!/usr/bin/env python3
"""The cases of cold-read-agy-cell-test.py that need the real sandbox
program: that no credential file can be read from inside the agy cell,
under the real bwrap on Linux or sandbox-exec on macOS.

The real bwrap cannot start inside the nn-test-sandbox, so this suite is
listed in scripts/run-all-test-suites.py's SUITES_RUN_WITHOUT_ANY_SANDBOX and
waits for that list's machine-wide lock. It runs
nn-systems/cold-read/tests/cold-read-agy-cell-test.py with
--real-sandbox-cases-only, which runs those cases alone and puts no stand-in
for the sandbox program on PATH; the other cases of that suite run inside the
nn-test-sandbox with a stand-in. Its exit code and output are that run's.

Run: python3 nn-systems/cold-read/tests/cold-read-agy-cell-real-sandbox-test.py
"""

import importlib.util
import pathlib

_start_and_end_lines_spec = importlib.util.spec_from_file_location(
    "nn_test_suite_start_time_line_and_end_results_line_print_common",
    pathlib.Path(__file__).resolve().parents[3] / "nn-systems/general-tools/nn-test-suite-start-time-line-and-end-results-line-print-common.py")
_start_and_end_lines = importlib.util.module_from_spec(_start_and_end_lines_spec)
_start_and_end_lines_spec.loader.exec_module(_start_and_end_lines)
_start_and_end_lines.nn_test_suite_start_time_line_print_now_and_end_results_line_print_at_normal_exit_register()

import subprocess
import sys
from pathlib import Path

SUITE = Path(__file__).resolve().parent / "cold-read-agy-cell-test.py"

sys.exit(subprocess.run([sys.executable, str(SUITE), "--real-sandbox-cases-only"],
                        check=False).returncode)
