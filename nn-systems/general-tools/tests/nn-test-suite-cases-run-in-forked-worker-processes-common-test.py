#!/usr/bin/env python3
"""Tests for nn-systems/general-tools/nn-test-suite-cases-run-in-forked-worker-processes-common.py.

Each case writes a small suite that calls the module, runs it as a child process with the worker
count set or unset, and reads what it printed and the files its cases wrote: which process ran each
case, whether one case's lines stayed together, which names reached the suite's failures list, and
what a worker that crashes, is killed, raises or hangs leaves behind. A child that has not exited
within CHILD_TIME_LIMIT_SECONDS is killed and its case fails.

Run: python3 nn-systems/general-tools/tests/nn-test-suite-cases-run-in-forked-worker-processes-common-test.py
Prints one line per case and exits non-zero if any case fails.
"""

import importlib.util
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

MODULE_PATH = (Path(__file__).resolve().parents[1]
               / "nn-test-suite-cases-run-in-forked-worker-processes-common.py")
_spec = importlib.util.spec_from_file_location("nn_test_suite_cases_run_in_forked_worker_processes_common",
                                               MODULE_PATH)
workers = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(workers)

CHILD_TIME_LIMIT_SECONDS = 120
failures = []


def check(name, condition, detail=""):
    if condition:
        print(f"PASS  {name}")
    else:
        print(f"FAIL  {name}: {detail}")
        failures.append(name)


# The suite under test: SUITE_CASES is spliced in, a list of (name, source of the case's body) whose body
# may use RECORDS, the directory each case writes to.
SUITE = r'''
import importlib.util, os, signal, subprocess, sys, time
from pathlib import Path
spec = importlib.util.spec_from_file_location("workers", sys.argv[1])
workers = importlib.util.module_from_spec(spec)
spec.loader.exec_module(workers)
RECORDS = Path(sys.argv[2])
BUILT_IN_PARENT = os.getpid()
failures = []

def check(name, condition):
    print(("PASS  " if condition else "FAIL  ") + name)
    if not condition:
        failures.append(name)

def record(name):
    (RECORDS / name).write_text(f"{os.getpid()} {BUILT_IN_PARENT}\n")

def setup(number):
    (RECORDS / f"setup-{number}").write_text(str(os.getpid()))

cases = []
SUITE_CASES
limit = float(os.environ.get("CASE_LIMIT", "300"))
workers.nn_test_suite_cases_run_in_forked_worker_processes(cases, failures, worker_setup=setup,
                                                          case_time_limit_seconds=limit)
print("FAILURES " + repr(failures))
sys.exit(1 if failures else 0)
'''


def suite_running(cases, worker_count, case_limit=None, signal_after=None):
    """(exit code, output, records directory) of the suite made from cases, run with this worker count.

    signal_after, (seconds, signal), sends that signal to the suite that many seconds after it starts."""
    scratch = Path(tempfile.mkdtemp(prefix="forked-case-workers-test-"))
    records = scratch / "records"
    records.mkdir()
    body = "".join(f"def case_{number}():\n" + "".join(f"    {line}\n" for line in source.splitlines())
                   + f"cases.append(({name!r}, case_{number}))\n" for number, (name, source) in enumerate(cases))
    program = scratch / "suite.py"
    program.write_text(SUITE.replace("SUITE_CASES", body))
    environment = dict(os.environ)
    environment.pop(workers.NN_TEST_SUITE_CASE_WORKER_PROCESS_COUNT_ENVIRONMENT_VARIABLE, None)
    if worker_count is not None:
        environment[workers.NN_TEST_SUITE_CASE_WORKER_PROCESS_COUNT_ENVIRONMENT_VARIABLE] = str(worker_count)
    if case_limit is not None:
        environment["CASE_LIMIT"] = str(case_limit)
    # Unbuffered, as scripts/run-all-test-suites.py runs a suite.
    process = subprocess.Popen([sys.executable, "-u", str(program), str(MODULE_PATH), str(records)],
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=environment,
                               start_new_session=True)
    if signal_after is not None:
        time.sleep(signal_after[0])
        process.send_signal(signal_after[1])
    try:
        output, _ = process.communicate(timeout=CHILD_TIME_LIMIT_SECONDS)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
        output, _ = process.communicate()
        output += f"\n[killed after {CHILD_TIME_LIMIT_SECONDS} s]"
    return process.returncode, output, scratch, records


def pid_of(records, name):
    return int((records / name).read_text().split()[0])


def process_running(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    # A zombie has ended; only its parent has not reaped it.
    try:
        return Path(f"/proc/{pid}/stat").read_text().split(") ", 1)[1][0] != "Z"
    except (FileNotFoundError, IndexError):
        return os.path.exists(f"/proc/{pid}") if os.path.isdir("/proc") else True


EIGHT_CASES = [(f"case {number}", f'record("case-{number}")\nprint("PASS  case {number} first line")\n'
                                  f'time.sleep(0.2)\n'
                                  f'subprocess.run(["printf", "PASS  case {number} from a subprocess\\n"])\n'
                                  f'check("case {number} last line", {number} != 5)')
               for number in range(8)]


def test_unset_worker_count_runs_every_case_in_this_process_in_order():
    code, output, scratch, records = suite_running(EIGHT_CASES, None)
    try:
        lines = [line for line in output.splitlines() if line.startswith(("PASS  ", "FAIL  "))]
        expected = [line for number in range(8) for line in (
            f"PASS  case {number} first line", f"PASS  case {number} from a subprocess",
            f"{'FAIL' if number == 5 else 'PASS'}  case {number} last line")]
        pids = {pid_of(records, f"case-{number}") for number in range(8)}
        check("with no worker count given, every case runs in the suite's own process, in the order given",
              lines == expected and len(pids) == 1 and not list(records.glob("setup-*")), output)
        check("with no worker count given, the failing case reaches the suite's failures and the suite exits 1",
              code == 1 and "FAILURES ['case 5 last line']" in output, output)
    finally:
        shutil.rmtree(scratch)


def test_a_worker_count_of_one_or_one_that_is_not_a_whole_number_above_zero_runs_in_this_process():
    for given in ("1", "0", "-3", "four", ""):
        os.environ[workers.NN_TEST_SUITE_CASE_WORKER_PROCESS_COUNT_ENVIRONMENT_VARIABLE] = given
        try:
            count = workers.nn_test_suite_case_worker_process_count()
        finally:
            del os.environ[workers.NN_TEST_SUITE_CASE_WORKER_PROCESS_COUNT_ENVIRONMENT_VARIABLE]
        check(f"a worker count of {given!r} is read as 1", count == 1, count)
    os.environ[workers.NN_TEST_SUITE_CASE_WORKER_PROCESS_COUNT_ENVIRONMENT_VARIABLE] = "4"
    try:
        check("a worker count of '4' is read as 4", workers.nn_test_suite_case_worker_process_count() == 4)
    finally:
        del os.environ[workers.NN_TEST_SUITE_CASE_WORKER_PROCESS_COUNT_ENVIRONMENT_VARIABLE]


def test_three_workers_run_every_case_once_each_case_printed_whole_and_failures_reach_the_parent():
    code, output, scratch, records = suite_running(EIGHT_CASES, 3)
    try:
        lines = output.splitlines()
        whole = all(
            lines.count(f"PASS  case {number} first line") == 1
            and lines[lines.index(f"PASS  case {number} first line") + 1] == f"PASS  case {number} from a subprocess"
            and lines[lines.index(f"PASS  case {number} first line") + 2]
            == f"{'FAIL' if number == 5 else 'PASS'}  case {number} last line"
            for number in range(8))
        check("with 3 workers each case's lines, its subprocess's included, are printed together, each case once",
              whole, output)
        ran_in = {pid_of(records, f"case-{number}") for number in range(8)}
        parent = int((records / "case-0").read_text().split()[1])
        setups = sorted(path.name for path in records.glob("setup-*"))
        check("with 3 workers the cases run in 3 forked processes, none of them the suite's own, each set up once",
              len(ran_in) == 3 and parent not in ran_in and setups == ["setup-0", "setup-1", "setup-2"]
              and {int((records / name).read_text()) for name in setups} == ran_in, (ran_in, parent, setups))
        check("what the suite built before the call is built once, in its own process, and shared by the workers",
              {(records / f"case-{number}").read_text().split()[1] for number in range(8)} == {str(parent)})
        check("a name check() appended in a worker reaches the suite's failures list, so the suite exits 1",
              code == 1 and "FAILURES ['case 5 last line']" in output, output)
    finally:
        shutil.rmtree(scratch)


def test_a_worker_that_crashes_fails_its_case_and_a_fresh_worker_runs_the_rest():
    cases = [("crashing case", 'record("crashing")\nprint("PASS  before the crash", flush=True)\nos._exit(3)'),
             *[(f"case {number}", f'record("case-{number}")\ntime.sleep(0.5)\ncheck("case {number}", True)')
               for number in range(6)]]
    code, output, scratch, records = suite_running(cases, 2)
    try:
        crash_line = "FAIL  crashing case: its worker process ended with exit code 3 before the case did"
        check("a case whose worker exits fails with a line naming the case and the exit code, after the output "
              "the case printed", crash_line in output
              and output.index("PASS  before the crash") < output.index(crash_line), output)
        check("after a worker crashes, every other case still runs once, and the suite fails naming only the "
              "crashed case", all(output.count(f"PASS  case {number}\n") == 1 for number in range(6))
              and "FAILURES ['crashing case']" in output and code == 1, output)
        check("a fresh worker is forked in the crashed one's place",
              sorted(path.name for path in records.glob("setup-*")) == ["setup-0", "setup-1", "setup-2"],
              sorted(path.name for path in records.glob("setup-*")))
    finally:
        shutil.rmtree(scratch)


def test_a_worker_whose_case_forked_a_process_still_running_is_seen_to_end_at_once():
    # A forked process keeps the worker's results pipe open, as the walk-me-through close test's read-ahead does.
    linger = 'if os.fork() == 0:\n    time.sleep(40)\n    os._exit(0)\n'
    cases = [("crash leaving a forked process", linger + "os._exit(3)"),
             ("pass leaving a forked process", linger + 'check("pass leaving a forked process", True)')]
    started = time.monotonic()
    code, output, scratch, _ = suite_running(cases, 2, case_limit=30)
    seconds = time.monotonic() - started
    try:
        check("a worker that crashes while a process its case forked still runs is reported as crashed, not as "
              "timed out, and the suite ends long before that process would",
              "FAIL  crash leaving a forked process: its worker process ended with exit code 3 before the case did"
              in output and "PASS  pass leaving a forked process" in output and code == 1 and seconds < 20,
              (seconds, output))
    finally:
        shutil.rmtree(scratch)


def test_a_worker_killed_by_a_signal_fails_its_case_naming_the_signal():
    cases = [("killed case", "os.kill(os.getpid(), signal.SIGKILL)"),
             ("next case", 'check("next case", True)')]
    code, output, scratch, _ = suite_running(cases, 2)
    try:
        check("a case whose worker is killed by SIGKILL fails naming the signal, and the other case passes",
              "FAIL  killed case: its worker process ended with signal SIGKILL before the case did" in output
              and "PASS  next case" in output and code == 1, output)
    finally:
        shutil.rmtree(scratch)


def test_a_case_that_raises_fails_with_its_traceback_printed_before_the_fail_line():
    cases = [("raising case", 'print("PASS  before the raise")\nraise RuntimeError("the case broke")'),
             ("next case", 'check("next case", True)')]
    code, output, scratch, _ = suite_running(cases, 2)
    try:
        fail_line = "FAIL  raising case: its worker process ended with exit code 70 before the case did"
        check("a case that raises has its traceback printed with its output, then fails",
              "RuntimeError: the case broke" in output and fail_line in output
              and output.index("PASS  before the raise") < output.index("RuntimeError: the case broke")
              < output.index(fail_line), output)
        check("after a case raises, the other case still passes and the suite exits 1",
              "PASS  next case" in output and code == 1, output)
    finally:
        shutil.rmtree(scratch)


def test_a_case_past_its_time_limit_is_killed_with_the_processes_it_started_and_fails():
    cases = [("hanging case", 'child = subprocess.Popen(["sleep", "300"])\n'
                              '(RECORDS / "hanging-child").write_text(str(child.pid))\n'
                              'print("PASS  hanging case started", flush=True)\ntime.sleep(300)'),
             *[(f"case {number}", f'time.sleep(0.5)\ncheck("case {number}", True)') for number in range(4)]]
    started = time.monotonic()
    code, output, scratch, records = suite_running(cases, 2, case_limit=2)
    seconds = time.monotonic() - started
    try:
        fail_line = ("FAIL  hanging case: still running after 2.0 s, so its worker process and every process it "
                     "started were killed")
        check("a case still running at its time limit fails with a line naming it, after the output it printed",
              fail_line in output and output.index("PASS  hanging case started") < output.index(fail_line), output)
        child = int((records / "hanging-child").read_text())
        check("the hanging case's worker is killed with the subprocess it started", not process_running(child),
              child)
        check("after a case times out, every other case still runs once and the suite exits 1 well before the "
              "hanging case would have ended", all(output.count(f"PASS  case {number}\n") == 1 for number in range(4))
              and code == 1 and seconds < 60, (seconds, output))
    finally:
        shutil.rmtree(scratch)


def test_a_suite_stopped_by_sigterm_leaves_no_worker_or_case_process_running():
    cases = [(f"case {number}", f'child = subprocess.Popen(["sleep", "300"])\n'
                                f'(RECORDS / "child-{number}").write_text(str(child.pid))\n'
                                f'record("case-{number}")\ntime.sleep(300)') for number in range(2)]
    code, output, scratch, records = suite_running(cases, 2, signal_after=(3, signal.SIGTERM))
    try:
        started = [pid_of(records, f"case-{number}") for number in range(2) if (records / f"case-{number}").exists()]
        children = [int((records / f"child-{number}").read_text()) for number in range(2)
                    if (records / f"child-{number}").exists()]
        check("once a suite that set no SIGTERM handler is stopped by SIGTERM, it exits 143 and none of its workers "
              "or the processes its cases started runs on",
              code == 143 and len(started) == 2 and len(children) == 2
              and not any(process_running(pid) for pid in started + children), (code, started, children, output))
    finally:
        shutil.rmtree(scratch)


def main():
    for name, function in sorted(globals().items()):
        if name.startswith("test_") and callable(function):
            function()
    print()
    if failures:
        print(f"{len(failures)} case(s) failed")
        return 1
    print("all cases passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
