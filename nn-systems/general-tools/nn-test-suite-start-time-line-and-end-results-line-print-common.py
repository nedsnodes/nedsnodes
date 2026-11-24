#!/usr/bin/env python3
"""Make a test suite print a START line when it starts and an END line when it ends on its own.

Every nn-test-suite calls nn_test_suite_start_time_line_print_now_and_end_results_line_print_at_normal_exit_register() once,
first thing, which prints

    START <the time in UTC, as YYYY-MM-DDTHH:MM:SSZ>

on standard output at once, and, when the suite's process ends on its own, as the last line,

    END <the time in UTC> passed=12 failed=1

counting the case lines the suite printed through sys.stdout: a line opening PASS or ok as
passed, one opening FAIL as failed. scripts/run-all-test-suites.py counts a suite as having run to
the end only when its END line is there, so a suite that crashes partway, even before its first
case line, is told apart from one whose cases failed.

The END line is printed only when the process ends by returning from the suite or by sys.exit,
whatever its exit code. It is not printed when an uncaught exception ends the suite, when a
signal kills it, or in a child the suite forked, so its absence means the suite stopped partway.

Neither line is printed when the suite file is loaded as a module by another program rather than
run, or when CHILD_RUN_ENVIRONMENT_VARIABLE is set to 1: a suite that runs itself as a child
program and reads that child's output sets it for the child, so the lines do not mix into what
the parent reads.

Load it by path, under the snake_case form of its file name:

    spec = importlib.util.spec_from_file_location("nn_test_suite_start_time_line_and_end_results_line_print_common", <path>)
"""

import atexit
import os
import re
import sys
import time

PASSED_CASE_LINE = re.compile(r"^\s*(PASS|ok)\b")
FAILED_CASE_LINE = re.compile(r"^\s*FAIL\b")
START_LINE_WORD = "START"
END_LINE_WORD = "END"
CHILD_RUN_ENVIRONMENT_VARIABLE = "NN_TEST_SUITE_CHILD_RUN_PRINTS_NO_START_OR_END_LINE"
NN_TEST_SUITE_END_LINE_WITH_PASSED_AND_FAILED_COUNTS_REGEX = re.compile(
    r"^END \d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ passed=(?P<passed>\d+) failed=(?P<failed>\d+)$")


def utc_time_now_text():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


class CaseLineCountingStandardOutput:
    """Standard output that counts the PASS, ok and FAIL lines written through it."""

    def __init__(self, wrapped):
        self._wrapped = wrapped
        self._line_head = ""
        self.passed = 0
        self.failed = 0

    def write(self, text):
        for character in text:
            if character == "\n":
                self._count(self._line_head)
                self._line_head = ""
            elif len(self._line_head) < 16:
                self._line_head += character
        return self._wrapped.write(text)

    def _count(self, head):
        if PASSED_CASE_LINE.match(head):
            self.passed += 1
        elif FAILED_CASE_LINE.match(head):
            self.failed += 1

    def __getattr__(self, name):
        return getattr(self._wrapped, name)


def nn_test_suite_start_time_line_print_now_and_end_results_line_print_at_normal_exit_register():
    """Print the START line now, and arrange the END line for when the suite ends on its own."""
    if (sys._getframe(1).f_globals.get("__name__") != "__main__"
            or os.environ.get(CHILD_RUN_ENVIRONMENT_VARIABLE) == "1"):
        return
    counting = CaseLineCountingStandardOutput(sys.stdout)
    sys.stdout = counting
    print(f"{START_LINE_WORD} {utc_time_now_text()}", flush=True)
    started_in = os.getpid()
    ended_by_uncaught_exception = []
    hook_before = sys.excepthook

    def note_uncaught_exception(kind, value, traceback):
        ended_by_uncaught_exception.append(kind)
        hook_before(kind, value, traceback)

    sys.excepthook = note_uncaught_exception

    def print_end_line():
        if ended_by_uncaught_exception or os.getpid() != started_in:
            return
        counting._count(counting._line_head)
        stream = counting._wrapped
        if counting._line_head:
            stream.write("\n")
        stream.write(f"{END_LINE_WORD} {utc_time_now_text()} "
                     f"passed={counting.passed} failed={counting.failed}\n")
        stream.flush()

    atexit.register(print_end_line)
