---
issue: "[The after-merge failed suites record drops a recorded failing test case when its test suite crashes before printing its first case line](https://github.com/nedsnodes/nedsnodes/issues/4640)"
---

# The after-merge failed suites record drops a recorded failing test case when its test suite crashes before printing its first case line

## Reproduction

Save this script as `repro.py` and run `python3 repro.py` in a checkout of main at [0d355d1cee79caecbbe7092fe6583928bc14e252](https://github.com/nedsnodes/nedsnodes/tree/0d355d1cee79caecbbe7092fe6583928bc14e252). The script points `HOME` at a temporary directory, so it never reads or writes the real record. It puts on the record one failing case, `case a`, of a made-up test suite the script names `scripts/x-test.py`, recorded at commit A by pull request 9 with repair task 7. It then gives the merge program an after-merge test run at the later commit B in which that suite crashed at import, printed a Python traceback and no case line, and exited 1.

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
record.write_text(json.dumps({SUITE: {"failed_tests": {"case a": {"commit": A, "last_failed_commit": A, "pull_request": "9", "log": None, "failed_at": "2026-11-20T00:00:00Z", "repair_task_agent_seat": "seat-x", "repair_task_id": 7}}}}))
after_merge_test_run(B, 1, [], log_text="Traceback (most recent call last):\n  File \"x\", line 1\nImportError: boom\n")
kept = json.loads(record.read_text())[SUITE]["failed_tests"].get("case a")
print("PASS: case a stays on the record" if kept and kept["repair_task_id"] == 7 else "FAIL: case a left the record")
```

It prints:

```
scripts/x-test.py: case a left the failed suites record: its suite ran to the end and reported nothing for it
record: {'scripts/x-test.py': ('10', 1)}
FAIL: case a left the record
```

## What is wrong

`case a` never ran at B, yet the merge program took it off the record as if its suite had run every case and reported nothing for it. The entry for `case a`, with the pull request that broke it, the commit it first failed at and the link to repair task 7, is deleted, and a new entry for the whole suite, blamed on pull request 10 and given a second repair task, takes its place. Once the crash is fixed, a `case a` that still fails comes back as a new failure blamed on whichever pull request merges then.

The cause is [`test_suite_ran_to_the_end` in `scripts/run-all-test-suites.py`, line 2983](https://github.com/nedsnodes/nedsnodes/blob/0d355d1cee79caecbbe7092fe6583928bc14e252/scripts/run-all-test-suites.py#L2983): a suite with no case lines counts as having run to the end whatever its exit code, so its JUnit XML says `ran_to_the_end="true"`, and the check for an uncaught Python traceback below that line never runs for it. The merge program's [`why_it_leaves`, lines 745 to 748](https://github.com/nedsnodes/nedsnodes/blob/0d355d1cee79caecbbe7092fe6583928bc14e252/scripts/merge-lane-pull-request-merge-through-merge-gate-with-stacked-pull-request-retarget.py#L745) trusts that attribute and deletes every recorded case the suite did not mention. Commit 56a4263605, by the agent-seat overall-cleanup, wrote both.

## What to do

The fix keeps this invariant: an after-merge test run in which a suite exited nonzero without printing any case line takes none of that suite's recorded cases off the record, whether or not the suite printed a Python traceback, because a shell suite stopped by `set -e`, or a Python suite that calls `sys.exit(1)` at import, prints none. The suite-level failure the merge program records for that run, `scripts/x-test.py` above, with its repair task, stays as it is today, beside the kept cases. Two places could keep the invariant, and whoever makes the fix chooses one:
- `test_suite_ran_to_the_end` returns false for a suite that exited nonzero with no case lines. The merge program then prints its STOP for a suite that did not run to the end, so its text, at [lines 709 to 713](https://github.com/nedsnodes/nedsnodes/blob/0d355d1cee79caecbbe7092fe6583928bc14e252/scripts/merge-lane-pull-request-merge-through-merge-gate-with-stacked-pull-request-retarget.py#L709), must also name a suite that stopped before its first case line; and every failing suite that only ever reports by its exit code then gets that STOP too.
- `why_it_leaves` in the merge program keeps every recorded case of a suite whose verdict holds no case but the one named for the suite and that failed, and `ran_to_the_end` stays as it is.

Add a case to `scripts/merge-lane-pull-request-merge-through-merge-gate-with-stacked-pull-request-retarget-test.py` built from the reproduction above, expecting `case a` to stay on the record with pull request 9 and repair task 7; the reproduction's last line prints PASS once the fix is in. When the fix changes `test_suite_ran_to_the_end`, also add a case to `scripts/run-all-test-suites-test.py` for a suite with no case lines that exited 1, expecting it to return false.
