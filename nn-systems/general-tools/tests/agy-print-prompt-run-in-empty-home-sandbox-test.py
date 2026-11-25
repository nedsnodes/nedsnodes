#!/usr/bin/env python3
"""Tests for nn-systems/general-tools/agy-print-prompt-run-in-empty-home-sandbox.py.

Run: python3 nn-systems/general-tools/tests/agy-print-prompt-run-in-empty-home-sandbox-test.py

No case runs the real agy. A scratch home holds .gemini beside other entries,
and a stub agy stands in for the real one.

  - `ls -A $HOME` run inside the sandbox prefix the program builds shows
    .gemini and nothing else.
  - Inside that prefix /usr and /etc are mounted read-only, and so is
    /run/systemd/resolve when this machine has it.
  - With bwrap missing from PATH the program refuses, exit 1, naming bwrap,
    with that one line and nothing else on stderr.
  - With agy missing from PATH the program refuses, exit 1, naming agy,
    with that one line and nothing else on stderr.
  - A stub agy that fails exits the program with the stub's code, its stderr
    passed through and a line naming the failure; a stub that succeeds has
    its result line's response printed and its arguments as the program built them;
    it runs as the sandbox's agy with only .gemini in its home, in the empty
    /tmp/agy-working-directory, with no agy on PATH and only the prompt's
    stream-json line on its stdin, not the caller's stdin, and a GEMINI_API_KEY, GH_TOKEN or GITHUB_TOKEN the caller set does not reach it, while
    other variables do.
  - A PROMPT of - over 131,072 bytes, read from stdin, reaches agy whole on
    stdin and in no argument.
  - A stub agy that exits 0 with no result line, or with a result whose
    status is not SUCCESS, makes the program exit 1 with nothing on stdout.
  - Without --model the program refuses, exit 2.
  - Run in this process with sys.platform set, the program hands agy a fresh
    temporary working directory on macOS and none on any other platform.
  - The Gemini launcher path the macOS branch loads names an existing file.

The real bwrap cannot start inside the nn-test-sandbox. So the checks only
it makes true, the home holding nothing but .gemini, the read-only mounts and
the empty working directory, run only with --real-sandbox-cases-only, which
nn-systems/general-tools/tests/agy-print-prompt-run-in-empty-home-sandbox-real-sandbox-test.py
passes; that suite needs bwrap on PATH and fails without it. Every other case
runs with the cold-read fixture's pass-through stand-in for bwrap, which logs
the prefix the program built so a case can compare it with the program's own.

Linux only: elsewhere every case is skipped, with a line saying why. Prints
one line per case and exits non-zero if any case fails.
"""

import importlib.util
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile

SCRIPT_PATH = (pathlib.Path(__file__).resolve().parent.parent
               / "agy-print-prompt-run-in-empty-home-sandbox.py")
_spec = importlib.util.spec_from_file_location("agy_print_prompt_run", SCRIPT_PATH)
program = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(program)
# The cold-read fixture holds the pass-through stand-in for bwrap that the other
# suites whose programs start bwrap use too.
_fixture_spec = importlib.util.spec_from_file_location(
    "cold_read_scratch_repository_test_fixture",
    pathlib.Path(__file__).resolve().parents[2] / "cold-read" / "tests"
    / "cold-read-scratch-repository-test-fixture.py")
fixture = importlib.util.module_from_spec(_fixture_spec)
_fixture_spec.loader.exec_module(fixture)

failures = []


def check(case_name, condition, detail=""):
    print(f"{'PASS' if condition else 'FAIL'}  {case_name}")
    if not condition:
        failures.append(case_name)
        if detail:
            print(f"      {detail}")


def scratch_home(root: pathlib.Path) -> pathlib.Path:
    home = root / "home"
    for directory in (".gemini", ".ssh", ".config/nedsnodes", ".local/bin"):
        (home / directory).mkdir(parents=True)
    (home / ".bashrc").write_text("export SECRET=1\n")
    (home / ".config/nedsnodes/gemini-api.key").write_text("key\n")
    return home


def stub_agy(bin_directory: pathlib.Path, body: str) -> None:
    bin_directory.mkdir(parents=True, exist_ok=True)
    stub = bin_directory / "agy"
    stub.write_text("#!/bin/sh\n" + body)
    stub.chmod(0o755)


def read_only_mount_points(mountinfo: str) -> set:
    """Return the mount points that /proc/self/mountinfo lists with the ro option."""
    read_only = set()
    for line in mountinfo.splitlines():
        fields = line.split()
        if len(fields) > 5 and "ro" in fields[5].split(","):
            read_only.add(fields[4])
    return read_only


def run_program(home, path, *arguments, extra_environment=None, caller_stdin="caller-stdin"):
    environment = {**os.environ, "HOME": str(home), "PATH": path,
                   "GEMINI_API_KEY": "caller-key", "GH_TOKEN": "caller-gh-token",
                   "GITHUB_TOKEN": "caller-github-token", "AAA_CALLER_VARIABLE": "kept-a",
                   "ZZZ_CALLER_VARIABLE": "kept-z", **(extra_environment or {})}
    return subprocess.run([sys.executable, str(SCRIPT_PATH), *arguments],
                          input=caller_stdin, capture_output=True, text=True,
                          env=environment)


# What the echoing stub agy answers, as the response of a stream-json result
# line, field by field: its arguments, then what it sees of its key, the
# caller's variables, its own path, its home, its working directory, PATH and
# stdin.
ECHOING_AGY_BODY = ('fields=$(printf "%s|" "$@" "key=${GEMINI_API_KEY-unset}${GH_TOKEN-unset}${GITHUB_TOKEN-unset}" '
                    '"${AAA_CALLER_VARIABLE-unset}" "${ZZZ_CALLER_VARIABLE-unset}" "$0" '
                    '"$(ls -A "$HOME" | tr "\\n" " ")" "cwd=$(pwd)" '
                    '"cwd-entries=$(ls -A)" "agy-on-path=$(command -v agy || echo none)" '
                    '"stdin=$(cat)")\n'
                    'python3 -c \'import json, sys; print(json.dumps({"event": "result", '
                    '"result": {"status": "SUCCESS", "response": sys.argv[1]}}))\' "$fields"\n')
SAY_HI_STDIN_LINE = '{"event": "user", "message": {"content": "say hi"}}'
ECHOED_FIELDS = ["--model", "gemini-x", "--input-format", "stream-json", "--output-format",
                 "stream-json", "--print", "",
                 "key=unsetunsetunset", "kept-a", "kept-z", program.AGY_PATH_INSIDE_SANDBOX,
                 ".gemini ", "cwd=/tmp/agy-working-directory", "cwd-entries=",
                 "agy-on-path=none", f"stdin={SAY_HI_STDIN_LINE}", ""]
# The fields only the real bwrap makes true: agy's own path is the bind's
# destination, the home holds only .gemini, and the working directory is empty.
# The stand-in starts the bind's source instead, so a case using it checks the
# path the program asked for in the stand-in's log.
FIELDS_ONLY_THE_REAL_SANDBOX_MAKES_TRUE = (11, 12, 14)

# With this flag only the cases that need the real bwrap run;
# nn-systems/general-tools/tests/agy-print-prompt-run-in-empty-home-sandbox-real-sandbox-test.py
# runs this suite so, and is listed in scripts/run-all-test-suites.py's
# SUITES_RUN_WITHOUT_ANY_SANDBOX. Without it the other cases run with the cold-read
# fixture's pass-through stand-in for bwrap, so this suite runs inside the nn-test-sandbox.
REAL_SANDBOX_CASES_ONLY_FLAG = "--real-sandbox-cases-only"


def real_sandbox_cases(root, home):
    bwrap_directory = str(pathlib.Path(shutil.which("bwrap")).parent)
    stub_agy(home / ".local/bin", "exit 0\n")
    listing = subprocess.run(
        [*program.empty_home_sandbox_prefix(home, str(home / ".local/bin/agy")),
         "ls", "-A", str(home)], capture_output=True, text=True)
    check("the sandbox shows .gemini and no other home entry",
          listing.returncode == 0 and listing.stdout.split() == [".gemini"],
          repr((listing.returncode, listing.stdout, listing.stderr)))
    mounts = subprocess.run(
        [*program.empty_home_sandbox_prefix(home, str(home / ".local/bin/agy")),
         "cat", "/proc/self/mountinfo"], capture_output=True, text=True)
    read_only = read_only_mount_points(mounts.stdout)
    check("the sandbox mounts /usr and /etc read-only",
          mounts.returncode == 0 and {"/usr", "/etc"} <= read_only,
          repr((mounts.returncode, sorted(read_only), mounts.stderr)))
    if pathlib.Path("/run/systemd/resolve").is_dir():
        check("the sandbox mounts /run/systemd/resolve read-only, as this machine has it",
              "/run/systemd/resolve" in read_only, repr(sorted(read_only)))
    else:
        print("SKIP  the /run/systemd/resolve bind: this machine has no /run/systemd/resolve.")
    echoing = root / "echoing-agy"
    stub_agy(echoing, ECHOING_AGY_BODY)
    result = run_program(home, f"{echoing}:{bwrap_directory}", "--model", "gemini-x", "say hi")
    check("agy succeeding under the real bwrap: run as the sandbox's agy with only "
          ".gemini in its home, in an empty working directory, with agy off PATH, "
          "only the prompt's stream-json line on stdin and no GEMINI_API_KEY, exit 0",
          result.returncode == 0 and result.stdout.split("|") == ECHOED_FIELDS
          and result.stderr == "",
          repr((result.returncode, result.stdout, result.stderr)))


def cases_with_the_stand_in_sandbox(root, home):
    fake_directory = str(fixture.install_fake_sandbox_programs(root / "fake-sandbox-programs"))
    no_bwrap = root / "path-without-bwrap"
    stub_agy(no_bwrap, "exit 0\n")
    result = run_program(home, str(no_bwrap), "--model", "m", "prompt")
    check("bwrap missing from PATH: refused, exit 1, naming bwrap",
          result.returncode == 1 and result.stderr == f"{program.PROGRAM}: refused: "
          "bwrap is not on PATH, so agy was not run.\n",
          repr((result.returncode, result.stderr)))

    result = run_program(home, fake_directory, "--model", "m", "prompt")
    check("agy missing from PATH: refused, exit 1, naming agy",
          result.returncode == 1 and result.stderr == f"{program.PROGRAM}: refused: "
          "agy is not on PATH, so agy was not run.\n",
          repr((result.returncode, result.stderr)))

    failing = root / "failing-agy"
    stub_agy(failing, "echo agy-stub-failure-text >&2\nexit 7\n")
    result = run_program(home, f"{failing}:{fake_directory}", "--model", "m", "prompt")
    check("agy failing: exit code passed through, its stderr kept, failure named",
          result.returncode == 7 and "agy-stub-failure-text" in result.stderr
          and "failed with exit code 7" in result.stderr,
          repr((result.returncode, result.stderr)))

    echoing = root / "echoing-agy"
    stub_agy(echoing, ECHOING_AGY_BODY)
    argv_log = root / "fake-sandbox-argv.jsonl"
    result = run_program(home, f"{echoing}:{fake_directory}", "--model", "gemini-x", "say hi",
                         extra_environment={"FAKE_SANDBOX_PROGRAM_ARGV_LOG": str(argv_log)})
    fields = result.stdout.split("|")
    check("agy succeeding: its result's response printed, arguments as built, no "
          "GEMINI_API_KEY, GH_TOKEN or GITHUB_TOKEN but every other variable, in "
          "/tmp/agy-working-directory, with agy off PATH and only the prompt's "
          "stream-json line on stdin, not the caller's stdin, exit 0",
          result.returncode == 0 and len(fields) == len(ECHOED_FIELDS)
          and all(field == expected for index, (field, expected)
                  in enumerate(zip(fields, ECHOED_FIELDS))
                  if index not in FIELDS_ONLY_THE_REAL_SANDBOX_MAKES_TRUE)
          and result.stderr == "",
          repr((result.returncode, result.stdout, result.stderr)))
    launches = ([json.loads(line) for line in argv_log.read_text().splitlines()]
                if argv_log.is_file() else [])
    expected_prefix = program.empty_home_sandbox_prefix(home, str(echoing / "agy"))
    check("the program starts bwrap with the empty-home prefix, then the sandbox's agy",
          len(launches) == 1 and launches[0][1:len(expected_prefix)] == expected_prefix[1:]
          and launches[0][0] == "bwrap"
          and launches[0][len(expected_prefix)] == program.AGY_PATH_INSIDE_SANDBOX,
          repr(launches))

    # Linux refuses any one argument over 131,072 bytes (MAX_ARG_STRLEN) with E2BIG.
    recording = root / "recording-agy"
    received_stdin_path = root / "recording-agy-stdin.txt"
    received_argv_path = root / "recording-agy-argv.txt"
    stub_agy(recording, f'cat > "{received_stdin_path}"\nprintf "%s\\n" "$@" > "{received_argv_path}"\n'
                        'echo \'{"event":"result","result":{"status":"SUCCESS","response":"answer"}}\'\n')
    oversize_prompt = "filler line of an oversize prompt\n" * 6000 + "OVERSIZE TAIL MARKER\n"
    result = run_program(home, f"{recording}:{fake_directory}", "--model", "m", "-",
                         caller_stdin=oversize_prompt)
    received_line = (received_stdin_path.read_text(encoding="utf-8")
                     if received_stdin_path.is_file() else "")
    received_argv = (received_argv_path.read_text(encoding="utf-8")
                     if received_argv_path.is_file() else "")
    check("PROMPT - reads a prompt over 131,072 bytes from stdin and hands agy all of it on "
          "stdin, none of it as an argument",
          result.returncode == 0 and result.stdout == "answer"
          and json.loads(received_line or "{}").get("message", {}).get("content") == oversize_prompt
          and "OVERSIZE TAIL MARKER" not in received_argv,
          repr((result.returncode, result.stdout, result.stderr[-300:], len(received_line))))

    for case, stub_stdout, wanted in (
            ("printed no result line", "not a result line", "printed no result line"),
            ("a result whose status is ERROR",
             '{"event":"result","result":{"status":"ERROR","response":"partial"}}',
             "its result's status is not SUCCESS")):
        no_answer = root / f"no-answer-agy-{len(wanted)}"
        stub_agy(no_answer, f"cat > /dev/null\necho '{stub_stdout}'\nexit 0\n")
        result = run_program(home, f"{no_answer}:{fake_directory}", "--model", "m", "say hi")
        check(f"agy exiting 0 having {case}: exit 1, nothing on stdout, the cause and what "
              "to do on stderr",
              result.returncode == 1 and result.stdout == "" and wanted in result.stderr
              and "do not take the empty stdout for agy's answer" in result.stderr,
              repr((result.returncode, result.stdout, result.stderr)))

    result = run_program(home, f"{echoing}:{fake_directory}", "say hi")
    check("--model missing: refused by argument parsing, exit 2, agy not run",
          result.returncode == 2 and "--model" in result.stderr and result.stdout == "",
          repr((result.returncode, result.stdout, result.stderr)))


class StubGeminiLauncher:
    """Stands in for the Gemini launcher: a fixed macOS prefix, and an environment
    filter that removes one more variable than the real one, so a case can tell
    that the program uses the launcher's filter."""

    EXTRA_REMOVED_VARIABLE = "AGY_PRINT_PROMPT_TEST_VARIABLE_THE_SHARED_FILTER_REMOVES"

    @staticmethod
    def credential_sandbox_prefix():
        return ["sandbox-exec"]

    agy_command_arguments_and_stream_json_stdin_line_build_for_prompt = staticmethod(
        program.load_cold_read_skill_agy_cell_launcher_program_module()
        .agy_command_arguments_and_stream_json_stdin_line_build_for_prompt)
    agy_stream_json_stdout_line_final_result_event_parse_to_exit_code_and_response_or_none = staticmethod(
        program.load_cold_read_skill_agy_cell_launcher_program_module()
        .agy_stream_json_stdout_line_final_result_event_parse_to_exit_code_and_response_or_none)

    @staticmethod
    def agy_environment_copy_without_gemini_api_key_or_github_token(environment):
        return {name: value for name, value in environment.items()
                if name != StubGeminiLauncher.EXTRA_REMOVED_VARIABLE}


def agy_run_with_stubs(platform):
    """Run main() in this process as if sys.platform were platform, with which(),
    the Gemini launcher and subprocess.run stubbed, and return the exit code, the
    cwd the program handed subprocess.run with whether that directory existed then,
    and the environment it handed subprocess.run."""
    seen = {}

    def fake_run(command, **keywords):
        seen["cwd"] = keywords.get("cwd")
        seen["existed"] = seen["cwd"] is not None and os.path.isdir(seen["cwd"])
        seen["env"] = keywords.get("env")
        return subprocess.CompletedProcess(
            command, 0, '{"event":"result","result":{"status":"SUCCESS","response":""}}\n')

    saved = (sys.platform, sys.argv, program.shutil.which, program.subprocess.run,
             program.load_cold_read_skill_agy_cell_launcher_program_module)
    sys.platform = platform
    sys.argv = [str(SCRIPT_PATH), "--model", "m", "prompt"]
    program.shutil.which = lambda name: f"/stub/{name}"
    program.subprocess.run = fake_run
    program.load_cold_read_skill_agy_cell_launcher_program_module = lambda: StubGeminiLauncher
    os.environ[StubGeminiLauncher.EXTRA_REMOVED_VARIABLE] = "x"
    try:
        exit_code = program.main()
    finally:
        (sys.platform, sys.argv, program.shutil.which, program.subprocess.run,
         program.load_cold_read_skill_agy_cell_launcher_program_module) = saved
        del os.environ[StubGeminiLauncher.EXTRA_REMOVED_VARIABLE]
    return exit_code, seen.get("cwd"), seen.get("existed"), seen.get("env")


def working_directory_cases():
    exit_code, cwd, existed, environment = agy_run_with_stubs("darwin")
    check("on macOS agy runs in a fresh agy-working-directory- temporary directory",
          exit_code == 0 and cwd is not None and existed
          and pathlib.Path(cwd).name.startswith("agy-working-directory-"),
          repr((exit_code, cwd, existed)))
    # cygwin sorts before darwin and linux after it, so between them they tell
    # == from <= and >=.
    for platform in ("linux", "cygwin"):
        exit_code, cwd, existed, environment = agy_run_with_stubs(platform)
        check(f"on {platform} agy gets no temporary working directory, since bwrap's "
              "--chdir sets it",
              exit_code == 0 and cwd is None, repr((exit_code, cwd, existed)))
        check(f"on {platform} agy's environment comes from the Gemini launcher's filter, "
              "so a variable added to that filter does not reach agy",
              environment is not None
              and StubGeminiLauncher.EXTRA_REMOVED_VARIABLE not in environment
              and environment.get("PATH") == os.environ.get("PATH"),
              repr(sorted(environment or {})))


def main() -> int:
    if not sys.platform.startswith("linux"):
        print("SKIP  every case: the empty-home sandbox is bwrap on Linux, and this "
              "machine is not Linux.")
        return 0
    real_sandbox_cases_only = REAL_SANDBOX_CASES_ONLY_FLAG in sys.argv[1:]
    if real_sandbox_cases_only and shutil.which("bwrap") is None:
        print("FAIL  the real-sandbox cases need bwrap on PATH, and this machine has none")
        return 1
    with tempfile.TemporaryDirectory() as temporary:
        root = pathlib.Path(temporary)
        home = scratch_home(root)
        if real_sandbox_cases_only:
            real_sandbox_cases(root, home)
        else:
            cases_with_the_stand_in_sandbox(root, home)

    if not real_sandbox_cases_only:
        working_directory_cases()
        check("the macOS branch's Gemini launcher path names the launcher file",
              program.GEMINI_LAUNCHER_PATH.is_file()
              and program.GEMINI_LAUNCHER_PATH.name == "cold-read-agy-cell.py",
              str(program.GEMINI_LAUNCHER_PATH))
    print(f"\n{len(failures)} failure(s)" if failures else "\nall passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
