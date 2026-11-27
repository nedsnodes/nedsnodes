---
issue: "[The test runner names a failing test case whose name holds a colon differently from the same case passing, so the after-merge failed suites record drops it and records it again as new](https://github.com/nedsnodes/nedsnodes/issues/4642)"
---

# The test runner names a failing test case whose name holds a colon differently from the same case passing, so the after-merge failed suites record drops it and records it again as new

## Reproduction

Save this script as `repro.py` and run `python3 repro.py` in a checkout of main at [0d355d1cee79caecbbe7092fe6583928bc14e252](https://github.com/nedsnodes/nedsnodes/tree/0d355d1cee79caecbbe7092fe6583928bc14e252). The script points `HOME` at a temporary directory, so it never reads or writes the real record. It names cases with the runner's own `test_cases_with_failing_case_names_resolved_against_the_suites_other_case_names`, and gives the merge program two after-merge test runs of a made-up test suite the script names `scripts/x-test.py`. At commit A the suite's one case fails, its FAIL line reading `control: when the runs share one temporary file, the checks above fail`, a case name the suite `scripts/run-all-test-suites-test.py` really prints, at its line 2220. At the later commit B the same case still fails, and a new passing case, `control: with separate temporary files the checks pass`, has been added beside it.

```python
import argparse, contextlib, importlib.util, io, json, os, subprocess, sys, tempfile
from pathlib import Path
scratch = Path(tempfile.mkdtemp())
os.environ["HOME"] = str(scratch / "home")
sys.path.insert(0, "scripts")
spec = importlib.util.spec_from_file_location("m", "scripts/merge-lane-pull-request-merge-through-merge-gate-with-stacked-pull-request-retarget.py")
program = importlib.util.module_from_spec(spec); spec.loader.exec_module(program)
runner = program.common.run_all_test_suites
env = runner.environment_without_git_redirecting_variables()
repo = scratch / "repo"; repo.mkdir()
def git(*a): return subprocess.run(["git", "-C", str(repo), *a], capture_output=True, text=True, env=env, check=True).stdout.strip()
git("init", "-q", "-b", "main")
for message in ("A", "B"): git("-c", "user.name=x", "-c", "user.email=x@x", "commit", "-q", "--allow-empty", "-m", message)
A, B = git("rev-parse", "HEAD~1"), git("rev-parse", "HEAD")
opened = []
program.repair_task_opened = lambda arguments, commit, seat, tests: (opened.append(tests) or ("seat", len(opened), None))
program.merged_branch_last_commit_author_name_read = lambda *a: "author"
program.repair_task_no_longer_open = lambda *a: False
record = Path.home() / ".local/state/nedsnodes/failed-after-merge-test-suites-on-main.json"
record.parent.mkdir(parents=True); record.write_text("{}")
SUITE = "scripts/x-test.py"
FAIL_LINE = [f"FAIL {SUITE} exit 1 — log /logs/x.log"]
def case(verdict, text): return {"verdict": verdict, "name": text, "detail": "", "text": text, "began": 0, "ended": 0, "seconds": 0, "unix_time": 0}
def after_merge_test_run(commit, exit_code, cases, log_text=""):
    log_dir = Path(tempfile.mkdtemp(dir=scratch)); (log_dir / "x.log").write_text(log_text)
    runner.write_case_times_suite_resources_and_junit_xml_of_run(log_dir, [{"suite": SUITE, "exit": exit_code, "cases": cases, "skips": [], "seconds": 1.0, "log": str(log_dir / "x.log")}])
    printed = io.StringIO()
    with contextlib.redirect_stdout(printed):
        program.failed_suites_kept_in_view(argparse.Namespace(pull_request="10"), commit, repo, log_dir, env, FAIL_LINE if exit_code else [])
    for line in printed.getvalue().splitlines():
        if "left the failed" in line: print(line)
    print("record:", {test: (fields["pull_request"], fields["repair_task_id"]) for test, fields in json.loads(record.read_text()).get(SUITE, {}).get("failed_tests", {}).items()})
resolve = runner.test_cases_with_failing_case_names_resolved_against_the_suites_other_case_names
text = "control: when the runs share one temporary file, the checks above fail"
after_merge_test_run(A, 1, resolve([case("FAIL", text)]))
after_merge_test_run(B, 1, resolve([case("PASS", "control: with separate temporary files the checks pass"), case("FAIL", text)]))
print("PASS: one entry, first repair task" if list(json.loads(record.read_text())[SUITE]["failed_tests"].values())[0]["repair_task_id"] == 1 and len(opened) == 1 else "FAIL: the case was recorded again as new")
```

It prints:

```
record: {'control': ('10', 1)}
scripts/x-test.py: control left the failed suites record: its suite ran to the end and reported nothing for it
record: {'control: when the runs share one temporary file, the checks above fail': ('10', 2)}
FAIL: the case was recorded again as new
```

## What is wrong

The same failing case was named `control` at A and by its full text at B. The merge program therefore took `control` off the record as if the suite no longer reported it, and recorded the full name as a new failure, with a second repair task and blamed on the pull request merged at B. The record's link to the pull request that broke the case, the commit it first failed at and its first repair task are lost. When the case passes, the runner names it by its full text. The merge program takes a recorded case off the record when a later run passes a case of exactly that name, or when the suite ran to the end without naming it; so when a suite run is killed after the case passed, a recorded `control` stays on the record although the case passed.

The cause is [`test_cases_with_failing_case_names_resolved_against_the_suites_other_case_names` in `scripts/run-all-test-suites.py`, line 2940](https://github.com/nedsnodes/nedsnodes/blob/0d355d1cee79caecbbe7092fe6583928bc14e252/scripts/run-all-test-suites.py#L2940). A FAIL line prints a case name, `: ` and a detail, and a name may itself hold `: `, so the function guesses where the name ends from the other case lines of the same suite run. The guess changes when the other case lines change, and differs from the name a PASS line gives the same case. Commit 56a4263605, by the agent-seat overall-cleanup, wrote it.

## What to do

Give every case line, PASS and FAIL alike, a case name that the line alone determines, so that a case has one name whether it passes or fails and whatever other cases its suite prints. Today no such rule exists: `TEST_CASE_LINE` in `scripts/run-all-test-suites.py` reads a verdict and the rest of the line, and the function above guesses where the name ends. One way, which whoever makes the fix may replace with a better one:
- One constant in `scripts/run-all-test-suites.py` defines a delimiter between a case's name and its detail, and `TEST_CASE_LINE` splits on it; a FAIL line with no detail prints no delimiter, and its whole text is the name.
- One shared function prints PASS, FAIL and SKIP lines with that delimiter and refuses a case name that holds it, and a source-scan test, like `scripts/test-suites-source-scan-for-skipped-case-prints-run-all-test-suites-cannot-count-test.py`, fails on any suite that prints a case line without that function. Many suites under `scripts/`, `.claude/guard-hooks/` and `nn-systems/` print their own FAIL lines today, so the change can move them over in parts, while the runner keeps today's guess for a line without the delimiter.
- GHI [1206](https://github.com/nedsnodes/nedsnodes/issues/1206) is settling the format of a skipped case's line; whichever of the two changes merges second follows the delimiter or quoting the first chose.

Entries already on the record under a guessed name leave it as today, when their suite runs to the end without naming them, so they need no migration.

Add a test to `scripts/merge-lane-pull-request-merge-through-merge-gate-with-stacked-pull-request-retarget-test.py` built from the reproduction above, expecting the case to keep one entry on the record with its first repair task; the reproduction's last line prints PASS once the fix is in.
