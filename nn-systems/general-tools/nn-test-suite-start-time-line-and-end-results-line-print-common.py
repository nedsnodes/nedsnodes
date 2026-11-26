#!/usr/bin/env python3
"""Make a test suite print a START line when it starts and an END line when it ends on its own.

Every nn-test-suite calls nn_test_suite_start_time_line_print_now_and_end_results_line_print_at_normal_exit_register() once,
first thing, which prints

    START <the time in UTC, as YYYY-MM-DDTHH:MM:SSZ>

on standard output at once, and, when the suite's process ends on its own, as the last line, one of

    END <the time in UTC> passed=12 failed=0 #nc_test_suite_pass             exit code 0
    END <the time in UTC> passed=12 failed=1 #nc_test_suite_fail             exit code 1
    END <the time in UTC> passed=0 failed=0 #nc_test_suite_could_not_run     exit code 2

The counts are of the case lines the suite printed through sys.stdout: a line opening PASS or ok
as passed, one opening FAIL as failed. The verdict is the suite's own exit code: exit 0 passes,
whatever FAIL lines it printed, such as a child suite's that it passes through; a suite that stops
before testing anything, such as one missing a program it needs, calls
nn_test_suite_could_not_run_exit(); any other exit fails. The process then exits with the code its
verdict gives, so a suite that exits 3 exits 1. scripts/run-all-test-suites.py counts a suite as
having run to the end only when its END line is its last line and agrees with its exit code, so a
suite that crashes partway, even before its first case line, is told apart from one whose cases
failed.

The END line is printed only when the process ends by returning from the suite or by SystemExit,
such as sys.exit, from anywhere in the suite. It is not printed when an uncaught exception ends the
suite, when a signal kills it, when it calls os._exit, or in a child the suite forked, so its
absence means the suite stopped partway.

Neither line is printed when the suite file is loaded as a module by another program rather than
run, or when CHILD_RUN_ENVIRONMENT_VARIABLE is set to 1: a suite that runs itself as a child
program and reads that child's output sets it for the child, so the lines do not mix into what
the parent reads.

A shell suite prints the same lines by running this file:

    python3 <this file> start
    python3 <this file> end <passed> <failed> <exit code>      exits with the verdict's code

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
NN_TEST_SUITE_PASS_HASHTAG = "#nc_test_suite_pass"
NN_TEST_SUITE_FAIL_HASHTAG = "#nc_test_suite_fail"
NN_TEST_SUITE_COULD_NOT_RUN_HASHTAG = "#nc_test_suite_could_not_run"
NN_TEST_SUITE_EXIT_CODE_OF_VERDICT_HASHTAG = {
    NN_TEST_SUITE_PASS_HASHTAG: 0, NN_TEST_SUITE_FAIL_HASHTAG: 1, NN_TEST_SUITE_COULD_NOT_RUN_HASHTAG: 2}
NN_TEST_SUITE_END_LINE_REGEX = re.compile(
    r"^END \d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ passed=(?P<passed>\d+) failed=(?P<failed>\d+) "
    r"(?P<verdict>#nc_test_suite_(?:pass|fail|could_not_run))$")
# sys.monitoring reserves 0, 1, 2 and 5 for debuggers, coverage tools, profilers and optimizers.
_MONITORING_TOOL_IDS_FREE_FOR_OTHER_USES = (3, 4)


def utc_time_now_text():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def nn_test_suite_verdict_hashtag(exit_code, could_not_run, passed, failed):
    """The verdict the END line gives a suite that exited with exit_code."""
    if exit_code == 0:
        return NN_TEST_SUITE_PASS_HASHTAG
    if could_not_run and exit_code == 2 and passed == failed == 0:
        return NN_TEST_SUITE_COULD_NOT_RUN_HASHTAG
    return NN_TEST_SUITE_FAIL_HASHTAG


def nn_test_suite_end_line_text(passed, failed, verdict_hashtag):
    return f"{END_LINE_WORD} {utc_time_now_text()} passed={passed} failed={failed} {verdict_hashtag}"


def exit_code_of_system_exit(exception):
    code = exception.code
    if code is None:
        return 0
    if isinstance(code, int):
        return code
    return 1


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


_could_not_run = []


def nn_test_suite_could_not_run_exit(reason):
    """End a suite that stops before testing anything, such as one missing a program it needs."""
    print(reason, file=sys.stderr)
    _could_not_run.append(reason)
    sys.exit(2)


def nn_test_suite_start_time_line_print_now_and_end_results_line_print_at_normal_exit_register():
    """Print the START line now, and arrange the END line for when the suite ends on its own."""
    suite_frame = sys._getframe(1)
    if (suite_frame.f_globals.get("__name__") != "__main__"
            or os.environ.get(CHILD_RUN_ENVIRONMENT_VARIABLE) == "1"):
        return
    suite_code = suite_frame.f_code
    monitoring = sys.monitoring
    tool = next((tool for tool in _MONITORING_TOOL_IDS_FREE_FOR_OTHER_USES
                 if monitoring.get_tool(tool) is None), None)
    if tool is None:
        raise RuntimeError(
            "nn-test-suite-start-time-line-and-end-results-line-print-common.py: sys.monitoring tool ids "
            f"{_MONITORING_TOOL_IDS_FREE_FOR_OTHER_USES} are all taken, so the suite's exit code cannot be read")
    # How the suite's top level ended: an atexit handler cannot otherwise see the exit code.
    ended = []

    def note_unwind(code, offset, exception):
        if code is suite_code:
            ended.append(exception)

    def note_return(code, offset, value):
        if code is suite_code:
            ended.append(None)

    monitoring.use_tool_id(tool, "nn-test-suite END line")
    monitoring.register_callback(tool, monitoring.events.PY_UNWIND, note_unwind)
    monitoring.register_callback(tool, monitoring.events.PY_RETURN, note_return)
    monitoring.set_events(tool, monitoring.events.PY_UNWIND)
    monitoring.set_local_events(tool, suite_code, monitoring.events.PY_RETURN)

    counting = CaseLineCountingStandardOutput(sys.stdout)
    sys.stdout = counting
    print(f"{START_LINE_WORD} {utc_time_now_text()}", flush=True)
    started_in = os.getpid()

    def print_end_line():
        if os.getpid() != started_in or not ended:
            return
        how = ended[-1]
        if how is None:
            exit_code = 0
        elif isinstance(how, SystemExit):
            exit_code = exit_code_of_system_exit(how)
        else:
            return
        counting._count(counting._line_head)
        verdict = nn_test_suite_verdict_hashtag(exit_code, bool(_could_not_run), counting.passed, counting.failed)
        stream = counting._wrapped
        if counting._line_head:
            stream.write("\n")
        stream.write(nn_test_suite_end_line_text(counting.passed, counting.failed, verdict) + "\n")
        stream.flush()
        verdict_exit_code = NN_TEST_SUITE_EXIT_CODE_OF_VERDICT_HASHTAG[verdict]
        if verdict_exit_code != exit_code:
            # Registered first, this handler runs after every other atexit handler.
            sys.stderr.flush()
            os._exit(verdict_exit_code)

    atexit.register(print_end_line)


def main(arguments):
    usage = ("usage: nn-test-suite-start-time-line-and-end-results-line-print-common.py "
             "start | end <passed> <failed> <exit code>")
    if arguments == ["start"]:
        print(f"{START_LINE_WORD} {utc_time_now_text()}")
        return 0
    if len(arguments) == 4 and arguments[0] == "end" and all(word.isdigit() for word in arguments[1:]):
        passed, failed, exit_code = (int(word) for word in arguments[1:])
        verdict = nn_test_suite_verdict_hashtag(exit_code, False, passed, failed)
        print(nn_test_suite_end_line_text(passed, failed, verdict))
        return NN_TEST_SUITE_EXIT_CODE_OF_VERDICT_HASHTAG[verdict]
    print(usage, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
