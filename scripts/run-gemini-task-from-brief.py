#!/usr/bin/env python3
"""Run a Gemini task from a UTF-8 brief file inside agy's credential sandbox.

Usage: run-gemini-task-from-brief.py -C CHECKOUT --brief FILE [-o REPORT]
       [--sandbox read-only|workspace-write] [-m MODEL] [--effort EFFORT]
       [--writable-root FOLDER]... [--deadline-minutes N]
       [--run-log FILE]

-o may be left out only where the log-store is on this machine, as on ned-box:
REPORT is then report.md in the run's own numbered folder, described below,
with its run log beside it, where no later run writes. Elsewhere, as on the
Mac, -o is required, and a run without it is refused; there a run that
writes its report also saves a copy of it, as the Codex task program does:
scripts/run-codex-task-from-brief.py says where.

Reads use the cold-read agy sandbox: the filesystem, including log-store
paths, is readable except for credential paths. No --readable-root is
needed. As in that sandbox, agy's own login remains readable; Linux masks
the credential directories and login files, and no file by its name, so a
`.env` or `*.token` file outside those directories is readable.

read-only lets agy write REPORT and, when the log-store is on this machine,
the run's own numbered folder <agent-seat>/<brief file name without its
extension>/<number> of
~/nedsnodes-logs/codex-and-gemini-sandboxed-task-runs-shared-writable-folder/,
1 for the brief's first run and one more than the highest number there after
that, whose path the launcher prints on stderr and the brief names; nothing else, not even its own state under
~/.gemini, so agy logs failed cache writes. workspace-write also lets it
write CHECKOUT and each --writable-root folder. The report file is bound
individually on Linux, so replacing it by rename is not supported. Existing
report content is removed before the task starts. Files in writable folders
may be overwritten by the task and are not rolled back on failure.

With workspace-write and CHECKOUT the top folder of a git worktree, the brief
tells agy to write its commit message in CHECKOUT/commit-message.txt, and,
when agy's run succeeds, as the stream-json paragraph below says, the
launcher, outside the sandbox,
stages every change in the worktree, commits it with that message under the
git identity the worktree gives the agent-seat, and deletes the file. A
commit-message.txt already there when the run starts is deleted first. When
the file is missing or empty, it commits nothing, lists the uncommitted
changes and exits 1. A run that changes nothing commits nothing. After a
commit, the launcher runs the worktree's own `scripts/run-all-test-suites.py
--only-suites-whose-recorded-inputs-changed-since <the commit HEAD was at when
the run started> --leave-recorded-inputs-and-failure-history-unchanged` in the
worktree, outside the deadline, copying its output to stderr. A worktree whose
HEAD names no commit is refused before agy starts. Give REPORT
outside the worktree, or the report and run log are committed with the
change. The agent-seat reviews the commit and pushes it.

agy always reaches the network, its own web tool included: its model
connection needs it, and no proxy separates model traffic from tool
traffic.

The launcher removes the agent-seat's GitHub tokens, which can push and
merge, from agy's environment, and sets GH_TOKEN to the read-only token in
~/.config/nedsnodes-sandboxed-models/, so that `gh` inside the sandbox
reads public GitHub. When that token cannot be read, agy runs without one,
and the run log says why after the model listing. How gh behaves inside the
macOS sandbox is said beside CREDENTIAL_DIRECTORIES in
nn-systems/cold-read/cold-read-cell-common.py. This launcher does not provision
logins, recover reports from chat, retry models, or verify report content.

agy runs on its own Google login, never on a Gemini API key: the launcher
removes GEMINI_API_KEY from agy's environment, because a key is billed per
call. When agy has no login, its "Authentication required." message is in
the log.

Runs `agy models` inside the same sandbox before starting the task, refusing
unknown names with the known names. The default is gemini-4-neon-high.
--effort is refused with a model id that ends in an effort, such as
gemini-4-hydrogen-xhigh, and so with the default; give it only with an id
that carries none, such as gemini-pro-orchestrator.
Closes stdin and logs both output streams to REPORT.run.log, or to
--run-log; an existing log at that path is overwritten. The
deadline covers model discovery and task execution after sandbox setup.

agy often prints its result and then hangs for minutes, ignoring SIGTERM,
so the task runs with `--output-format stream-json`, and the stdout line
whose `event` is `result` ends it: the launcher waits up to the agy
cold-read-cell's wait for the report file or for agy to exit, then kills
agy's process group with SIGKILL. The result's `status` SUCCESS is a
successful run and any other status a failed one, whatever agy's exit
code. A run with no result line ends when agy exits, its exit code
deciding, or at the deadline, when agy's process group is stopped and the
run fails.

Exits 0 with `report: PATH` for a nonblank report, 2 for invalid arguments,
and 1 with a diagnostic for file errors, unavailable sandbox, agy startup
or model-list failures, unknown models, timeout, a result whose status is
not SUCCESS, nonzero exit without a result line, no report,
changes that could not be committed, or, after a commit, a test-suite runner
that cannot be started, names failing nn-test-suites, which the message
lists, or ends without judging every suite.
Requires bwrap on Linux or sandbox-exec on macOS; never runs unsandboxed.
"""

import argparse
import importlib.util
import math
import os
import pathlib
import re
import shutil
import subprocess
import sys
import time


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ROOT = pathlib.Path(__file__).resolve().parent.parent
agy_cell = _load("cold_read_agy_cell", ROOT / "nn-systems/cold-read/cold-read-agy-cell.py")
codex_task = _load("run_codex_task_from_brief", ROOT / "scripts/run-codex-task-from-brief.py")
PROGRAM = "run-gemini-task-from-brief"
# The values `agy --help` gives for --effort; a model id ending in one of them carries its effort.
AGY_EFFORT_WORDS = ("low", "medium", "high", "xhigh", "max")


def _parser():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("-C", dest="checkout", required=True)
    parser.add_argument("--brief", required=True)
    parser.add_argument("-o", dest="report",
                        help="required unless the log-store is on this machine, where the "
                             "default is report.md in the run's numbered folder")
    parser.add_argument("--sandbox", choices=("read-only", "workspace-write"), default="read-only")
    parser.add_argument("-m", dest="model", default="gemini-4-neon-high")
    parser.add_argument("--effort")
    parser.add_argument("--writable-root", action="append", default=[])
    parser.add_argument("--deadline-minutes", type=float, default=60)
    parser.add_argument("--run-log")
    return parser


def _run(command, checkout, log, deadline, environment):
    process = subprocess.Popen(command, cwd=checkout, env=environment, stdin=subprocess.DEVNULL,
                               stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
    try:
        code = process.wait(timeout=max(0, deadline - time.monotonic()))
    except subprocess.TimeoutExpired:
        codex_task.stop_process_group(process)
        raise RuntimeError("deadline passed; agy and its children were stopped") from None
    if code != 0:
        raise RuntimeError(f"agy exited {code}")


def _run_task_until_its_result_line(command, checkout, log, deadline, environment, report):
    """Run the task with agy's stream-json output; its result line, not agy's exit, ends the run."""
    result_line_answers = []

    def log_line_and_parse_it(line):
        log.write(line)
        log.flush()
        answer = agy_cell.agy_stream_json_stdout_line_final_result_event_parse_to_exit_code_and_response_or_none(line)
        if answer is not None:
            result_line_answers.append(answer)
        return answer

    # A decoding error in the reader thread would stop line reading and leave the run to its deadline.
    process = subprocess.Popen(command, cwd=checkout, env=environment, stdin=subprocess.PIPE,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                               encoding="utf-8", errors="replace", start_new_session=True)
    completed = agy_cell.common.run_reviewer_program_until_its_result_line(
        process, command, None, max(0, deadline - time.monotonic()), log_line_and_parse_it, report,
        agy_cell.COLD_READ_AGY_CELL_WAIT_FOR_REPORT_FILE_AFTER_AGY_STDOUT_RESULT_LINE_BEFORE_PROCESS_GROUP_KILL_SECONDS)
    log.write(completed.stderr)
    log.flush()
    # Before the result line: one read while agy was being stopped at the deadline does not count.
    if completed.returncode is None:
        raise RuntimeError("deadline passed with no result line from agy; agy and its children were stopped")
    if result_line_answers:
        if isinstance(completed, agy_cell.common.ReviewerRunEndedByResultLine):
            print(f"{PROGRAM}: agy {agy_cell.common.AGENT_BINARY_KILLED_AFTER_FINAL_RESULT_LINE_PHRASE}, "
                  "so its process group was killed", file=sys.stderr)
        if result_line_answers[0][0] != 0:
            raise RuntimeError(f"agy's result line did not report {agy_cell.AGY_RESULT_SUCCESS_STATUS}; "
                               f"its response: {result_line_answers[0][1] or '(empty)'}")
        return
    if completed.returncode != 0:
        raise RuntimeError(f"agy exited {completed.returncode}")


def main(argv=None):
    parser = _parser()
    args = parser.parse_args(argv)
    if not math.isfinite(args.deadline_minutes) or args.deadline_minutes <= 0:
        parser.error("--deadline-minutes must be finite and greater than zero")
    if args.writable_root and args.sandbox != "workspace-write":
        parser.error("--writable-root requires --sandbox workspace-write")
    if args.effort and args.model.rpartition("-")[2] in AGY_EFFORT_WORDS:
        parser.error(f"--effort is refused with the model {args.model}, whose id already "
                     "carries an effort; give -m an id that carries none, such as "
                     "gemini-pro-orchestrator, or leave out --effort")
    checkout = pathlib.Path(args.checkout).resolve()
    brief = pathlib.Path(args.brief).resolve()
    roots = [pathlib.Path(root).resolve() for root in args.writable_root]
    if not checkout.is_dir() or any(not root.is_dir() for root in roots):
        parser.error("-C and every --writable-root must name existing directories")
    try:
        shared_subfolder = (
            codex_task.codex_or_gemini_task_run_subfolder_in_shared_writable_folder_create(brief))
    except OSError as error:
        print(f"{PROGRAM}: failed while creating the run's folder in the shared writable "
              f"folder: {error}", file=sys.stderr)
        return 1
    report = (pathlib.Path(args.report).resolve() if args.report is not None
              else codex_task.codex_or_gemini_task_report_path_in_run_numbered_folder_when_dash_o_omitted(
                  parser, shared_subfolder))
    log_path = (pathlib.Path(args.run_log).resolve() if args.run_log
                else report.with_name(report.name + ".run.log"))
    if len({brief, report, log_path}) != 3:
        parser.error("--brief, -o and --run-log must name different files")
    sandbox = agy_cell.credential_sandbox_program()
    stage = "preparing the sandbox"
    log_written_this_run = False
    try:
        if sandbox is None or shutil.which(sandbox) is None:
            raise RuntimeError(f"required sandbox {sandbox or 'bwrap (Linux) or sandbox-exec (macOS)'} is unavailable")
        stage = f"reading the brief {brief}"
        prompt = brief.read_text(encoding="utf-8")
        if not prompt.strip():
            raise RuntimeError("the brief is empty")
        stage = "preparing the sandbox"
        environment, token_note = (
            agy_cell.common.process_environment_copy_with_agent_seat_github_tokens_replaced_by_read_only_github_token(
                agy_cell.agy_environment_copy_without_gemini_api_key_or_github_token(os.environ)))
        if shared_subfolder:
            print(f"{PROGRAM}: this run's folder is {shared_subfolder}", file=sys.stderr)
            prompt = codex_task.brief_with_shared_writable_subfolder(prompt, shared_subfolder)
        stage = "checking whether -C is a git worktree to commit in"
        worktree_to_commit = codex_task.codex_or_gemini_workspace_write_run_worktree_path_to_commit_later_or_none(
            checkout, args.sandbox)
        if worktree_to_commit:
            start_commit, error = codex_task.codex_or_gemini_workspace_write_run_start_commit(
                worktree_to_commit)
            if error:
                raise RuntimeError(error)
            # A message left by an earlier run must not pass for this run's.
            (worktree_to_commit / codex_task.CODEX_OR_GEMINI_COMMIT_MESSAGE_FILE_NAME).unlink(
                missing_ok=True)
            prompt = codex_task.brief_with_commit_message_file_instruction(
                prompt, worktree_to_commit)
        stage = "preparing the sandbox"
        writable_folders = [checkout, *roots] if args.sandbox == "workspace-write" else []
        writable_folders += [shared_subfolder] if shared_subfolder else []
        prefix = agy_cell.credential_sandbox_prefix(
            writable_paths=[(report, False), *((folder, True) for folder in writable_folders)])
        stage = f"preparing report {report} and log {log_path}"
        report.parent.mkdir(parents=True, exist_ok=True)
        report.unlink(missing_ok=True)
        # bwrap needs an existing file to bind without granting its parent directory.
        report.touch()
        with log_path.open("w+", encoding="utf-8") as log:
            log_written_this_run = True
            deadline = time.monotonic() + args.deadline_minutes * 60
            stage = "listing models with agy models"
            _run([*prefix, "agy", "models"], checkout, log, deadline, environment)
            log.seek(0)
            listing = re.sub(r"\x1b\[[0-9;]*m", "", log.read())
            # IDs in agy's human-readable listing are whitespace-delimited hyphenated words.
            known = sorted(set(re.findall(r"(?<![\w.-])[a-z][a-z0-9]*(?:[-.][a-z0-9]+)+(?![\w.-])", listing)))
            if args.model not in known:
                raise RuntimeError(f"unknown model {args.model!r}; known names: {', '.join(known) or '(none listed)'}")
            # After the listing is parsed: its words would read as model names.
            if token_note:
                log.write(f"{PROGRAM}: {token_note}\n")
                log.flush()
            command = [*prefix, "agy", "--add-dir", str(checkout),
                       "--dangerously-skip-permissions", "--model", args.model,
                       "--print-timeout", f"{math.ceil(args.deadline_minutes * 60)}s",
                       "--output-format", "stream-json"]
            for root in roots:
                command += ["--add-dir", str(root)]
            if args.effort:
                command += ["--effort", args.effort]
            command += ["--print", prompt + f"\n\nWrite the task's report to this exact file: {report}\n"]
            stage = "running the task"
            print(f"{PROGRAM}: running Gemini in {checkout}; log {log_path}", file=sys.stderr)
            _run_task_until_its_result_line(command, checkout, log, deadline, environment, report)
        stage = f"reading report {report}"
        if not report.is_file() or not report.read_text(encoding="utf-8").strip():
            raise RuntimeError(f"agy exited 0 but wrote no report at {report}")
        # A copy that fails does not stop the commit: the run's changes are kept either way.
        report_copy_error = None
        try:
            report_copy = (codex_task.
                           codex_or_gemini_task_report_copy_into_run_numbered_folder_on_a_machine_without_the_log_store(
                               brief, report))
        except OSError as error:
            report_copy, report_copy_error = None, error
        if report_copy:
            print(f"{PROGRAM}: a copy of the report, which goes to the log-store, is at "
                  f"{report_copy}", file=sys.stderr)
        if worktree_to_commit:
            stage = f"committing the run's changes; the report is at {report}"
            done, error = codex_task.codex_or_gemini_finished_workspace_write_run_changes_commit(
                worktree_to_commit)
            if error:
                raise RuntimeError(error)
            if done:
                print(f"{PROGRAM}: {done}", file=sys.stderr)
                stage = (f"running the nn-test-suites the run's change touches; the report is "
                         f"at {report}")
                error = (codex_task.
                         codex_or_gemini_committed_run_test_suites_whose_recorded_inputs_changed_run(
                             worktree_to_commit, start_commit))
                if error:
                    raise RuntimeError(error)
        if report_copy_error:
            stage = (f"saving the copy of the report that goes to the log-store; the report is "
                     f"at {report}")
            raise report_copy_error
    except (OSError, UnicodeError, RuntimeError) as error:
        print(f"{PROGRAM}: failed while {stage}: {error}; output: {log_path}", file=sys.stderr)
        status = 1
    else:
        print(f"report: {report}")
        status = 0
    # A log at this path left by an earlier run is not this run's output.
    if log_written_this_run:
        agy_cell.common.sandboxed_model_run_output_gh_read_only_github_token_refused_by_github_check_and_report(
            PROGRAM, log_path.read_text(encoding="utf-8", errors="replace"))
    return status


if __name__ == "__main__":
    sys.exit(main())
