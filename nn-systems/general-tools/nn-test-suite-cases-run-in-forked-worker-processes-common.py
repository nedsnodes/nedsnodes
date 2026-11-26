"""Run an nn-test-suite's cases in forked worker processes, as many as scripts/run-all-test-suites.py gives it.

The runner sets NN_TEST_SUITE_CASE_WORKER_PROCESS_COUNT_ENVIRONMENT_VARIABLE for each suite its
SUITES_WHOSE_CASES_RUN_IN_FORKED_WORKER_PROCESSES lists, and holds that many admission slots and that
many times a suite's CPU weight while the suite runs. Unset, or 1, as when a suite is run directly,
the cases run one after another in this process, exactly as a loop over them would.

The workers are forked once the suite has loaded, so what the suite builds before it calls this
function is built once and shared. Each case's output, its subprocesses' included, goes to a file of
its own and is printed whole when the case ends, so the lines of two cases never interleave; cases
are printed in the order they end. The names check() appended to the suite's failures list in a
worker are appended to the caller's list, so the suite's summary and exit code come out as they would
in one process.

A case whose worker ends before the case does, as by a crash, an uncaught exception or os._exit, or
that is still running after case_time_limit_seconds, fails: its output so far is printed, then a FAIL
line naming the case and why, and its name is appended to failures. Its worker is killed with its
process group, and a fresh worker is forked for the cases left.

What it does not do: keep two cases apart that write the same path. A suite that names its scratch
directories from a counter gives each worker a directory of its own in worker_setup.
"""

import os
import select
import shutil
import signal
import sys
import tempfile
import time
import traceback

NN_TEST_SUITE_CASE_WORKER_PROCESS_COUNT_ENVIRONMENT_VARIABLE = "NN_TEST_SUITE_CASE_WORKER_PROCESS_COUNT"
# Cases of the suites that use this take at most a few seconds on a busy ned-box; a case past this
# is hung, and stopping it here prints which case it was, which the runner's suite timeout cannot.
NN_TEST_SUITE_CASE_TIME_LIMIT_SECONDS = 300
FAILED_CASE_LINE_PREFIX = "FAIL  "


def nn_test_suite_case_worker_process_count():
    """The worker count the runner gave this suite, or 1 when it gave none or one that is not a whole number above 0."""
    given = os.environ.get(NN_TEST_SUITE_CASE_WORKER_PROCESS_COUNT_ENVIRONMENT_VARIABLE, "")
    return int(given) if given.isdigit() and int(given) > 0 else 1


def nn_test_suite_cases_run_in_forked_worker_processes(cases, failures, worker_setup=None,
                                                        case_time_limit_seconds=NN_TEST_SUITE_CASE_TIME_LIMIT_SECONDS,
                                                        worker_count=None):
    """Run each (case name, function of no arguments) of cases, appending failing case names to failures.

    worker_setup, when given, is called with the worker's number in each worker before its first case.
    worker_count defaults to nn_test_suite_case_worker_process_count()."""
    cases = list(cases)
    count = min(nn_test_suite_case_worker_process_count() if worker_count is None else worker_count,
                len(cases))
    if count <= 1:
        for _, function in cases:
            function()
        return
    _CaseWorkers(cases, failures, worker_setup, case_time_limit_seconds).run(count)


class _CaseWorkers:
    def __init__(self, cases, failures, worker_setup, case_time_limit_seconds):
        self.cases = cases
        self.failures = failures
        self.worker_setup = worker_setup
        self.case_time_limit_seconds = case_time_limit_seconds
        self.waiting = list(range(len(cases)))
        self.workers = {}
        self.workers_forked = 0
        self.output_directory = tempfile.mkdtemp(prefix="nn-test-suite-case-output-")

    def run(self, count):
        sys.stdout.flush()
        sys.stderr.flush()
        # A stop signal's default action would end this process at once and leave the workers running.
        self.replaced = replaced = {stop: signal.signal(stop, _raise_system_exit) for stop in (signal.SIGTERM, signal.SIGHUP)
                                             if signal.getsignal(stop) == signal.SIG_DFL}
        try:
            for _ in range(count):
                self.fork_a_worker_and_give_it_a_case()
            while self.workers:
                self.collect_ended_cases()
        finally:
            for worker in list(self.workers.values()):
                self.kill(worker)
            shutil.rmtree(self.output_directory, ignore_errors=True)
            for stop, handler in replaced.items():
                signal.signal(stop, handler)

    def fork_a_worker_and_give_it_a_case(self):
        if not self.waiting:
            return
        number = self.workers_forked
        self.workers_forked += 1
        cases_read, cases_write = os.pipe()
        results_read, results_write = os.pipe()
        pid = os.fork()
        if pid == 0:
            try:
                os.close(cases_write)
                os.close(results_read)
                for worker in self.workers.values():
                    for descriptor in (worker["cases"], worker["results"]):
                        if descriptor is not None:
                            os.close(descriptor)
                self.worker_main(number, cases_read, results_write)
            except BaseException:
                traceback.print_exc()
            finally:
                os._exit(70)
        # Here as well as in the worker, so a kill sent before the worker runs still finds its group.
        try:
            os.setpgid(pid, pid)
        except OSError:
            pass
        os.close(cases_read)
        os.close(results_write)
        worker = {"pid": pid, "group": pid, "cases": cases_write, "results": results_read, "case": None,
                  "started": None, "unread": b""}
        self.workers[pid] = worker
        self.give_next_case(worker)

    def worker_main(self, number, cases_read, results_write):
        # A group of its own, so a case that hangs is killed with every process it started.
        os.setpgid(0, 0)
        # The suite's own handlers, so a case meets the signals as it would in the suite's process.
        for stop, handler in self.replaced.items():
            signal.signal(stop, handler)
        if self.worker_setup is not None:
            self.worker_setup(number)
        incoming = os.fdopen(cases_read, "rb")
        saved_stdout, saved_stderr = os.dup(1), os.dup(2)
        for line in incoming:
            index = int(line)
            before = len(self.failures)
            with open(self.output_path(index), "wb") as output:
                os.dup2(output.fileno(), 1)
                os.dup2(output.fileno(), 2)
            try:
                self.cases[index][1]()
            except BaseException:
                # Printed while the output still goes to the case's file, so it is shown with the case.
                traceback.print_exc()
                sys.stdout.flush()
                sys.stderr.flush()
                os._exit(70)
            sys.stdout.flush()
            sys.stderr.flush()
            os.dup2(saved_stdout, 1)
            os.dup2(saved_stderr, 2)
            failed = "\0".join(self.failures[before:])
            os.write(results_write, f"{index}\t{failed}\n".encode("utf-8", "surrogateescape"))
        os._exit(0)

    def output_path(self, index):
        return os.path.join(self.output_directory, f"case-{index}.out")

    def give_next_case(self, worker):
        if not self.waiting:
            os.close(worker["cases"])
            worker["cases"] = None
            return
        index = self.waiting.pop(0)
        worker["case"], worker["started"] = index, time.monotonic()
        os.write(worker["cases"], f"{index}\n".encode())

    def collect_ended_cases(self):
        now = time.monotonic()
        running = [worker for worker in self.workers.values() if worker["case"] is not None]
        wait = max(0.0, min((worker["started"] + self.case_time_limit_seconds - now for worker in running),
                            default=1.0))
        open_results = [worker["results"] for worker in self.workers.values() if worker["results"] is not None]
        ready, _, _ = select.select(open_results, [], [], min(wait, 1.0))
        for worker in list(self.workers.values()):
            if worker["results"] in ready:
                self.read_results(worker)
        # Ended workers are found by waitpid, not by the end of their results pipe: a process a case forked
        # holds that pipe open as long as it runs.
        for worker in list(self.workers.values()):
            ended, status = os.waitpid(worker["pid"], os.WNOHANG)
            if ended:
                worker["pid"] = None
                while worker["results"] is not None and select.select([worker["results"]], [], [], 0)[0]:
                    if not self.read_results(worker):
                        break
                self.worker_ended(worker, status)
        now = time.monotonic()
        for worker in list(self.workers.values()):
            if worker["case"] is not None and now - worker["started"] >= self.case_time_limit_seconds:
                index = worker["case"]
                self.kill(worker)
                self.case_failed(index, f"still running after {self.case_time_limit_seconds} s, so its worker "
                                        f"process and every process it started were killed")
                self.fork_a_worker_and_give_it_a_case()

    def read_results(self, worker):
        """Read what the worker has written and act on each whole line; False once the pipe has ended."""
        chunk = os.read(worker["results"], 65536)
        if not chunk:
            os.close(worker["results"])
            worker["results"] = None
            return False
        worker["unread"] += chunk
        while b"\n" in worker["unread"]:
            line, worker["unread"] = worker["unread"].split(b"\n", 1)
            index, failed = line.decode("utf-8", "surrogateescape").split("\t", 1)
            self.print_case_output(int(index))
            self.failures.extend(name for name in failed.split("\0") if name)
            worker["case"] = None
            self.give_next_case(worker)
        return True

    def worker_ended(self, worker, status):
        index = worker["case"]
        self.kill(worker)
        if index is None:
            if status != 0:
                print(f"{FAILED_CASE_LINE_PREFIX}a case worker process: it ended with {describe(status)} "
                      f"between cases", flush=True)
                self.failures.append("a case worker process")
            return
        self.case_failed(index, f"its worker process ended with {describe(status)} before the case did")
        self.fork_a_worker_and_give_it_a_case()

    def case_failed(self, index, why):
        name = self.cases[index][0]
        self.print_case_output(index)
        print(f"{FAILED_CASE_LINE_PREFIX}{name}: {why}", flush=True)
        self.failures.append(name)

    def print_case_output(self, index):
        try:
            with open(self.output_path(index), "rb") as output:
                shutil.copyfileobj(output, sys.stdout.buffer)
        except FileNotFoundError:
            pass
        sys.stdout.flush()

    def kill(self, worker):
        """Kill the worker's process group, reap the worker and drop it."""
        # The group outlives a worker that ended first while a process it started still runs.
        try:
            os.killpg(worker["group"], signal.SIGKILL)
        except ProcessLookupError:
            pass
        if worker["pid"] is not None:
            try:
                os.kill(worker["pid"], signal.SIGKILL)
            except ProcessLookupError:
                pass
            os.waitpid(worker["pid"], 0)
            worker["pid"] = None
        for key in ("cases", "results"):
            if worker[key] is not None:
                os.close(worker[key])
                worker[key] = None
        self.workers = {pid: other for pid, other in self.workers.items() if other is not worker}


def _raise_system_exit(signal_number, _frame):
    raise SystemExit(128 + signal_number)


def describe(status):
    if os.WIFSIGNALED(status):
        return f"signal {signal.Signals(os.WTERMSIG(status)).name}"
    return f"exit code {os.waitstatus_to_exitcode(status)}"
