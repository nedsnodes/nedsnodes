---
issue: "[The after-merge failed suites record drops a recorded failing test case that its test suite never reached, when the suite printed a FAIL line and then stopped without a Python traceback](https://github.com/nedsnodes/nedsnodes/issues/4809)"
---

# The after-merge failed suites record drops a recorded failing test case that its test suite never reached, when the suite printed a FAIL line and then stopped without a Python traceback

## Reproduction

Save this script as `repro.py` and run `python3 repro.py` in a checkout of main at [63dd962dd16b758eed8b1e08a4fc5526b3659191](https://github.com/nedsnodes/nedsnodes/tree/63dd962dd16b758eed8b1e08a4fc5526b3659191). The script points `HOME` at a temporary directory, so it never reads or writes the real record. It puts two failing cases of a made-up test suite, `scripts/x-test.py`, on the record: `case a` and `case b`, both recorded at commit A by pull request 9 with repair task 7. It then gives the merge program an after-merge test run at the later commit B in which that suite printed `FAIL  case b`, then stopped with exit code 1 before reaching `case a`, as a shell suite under `set -e` does when the command after a failed check fails. The suite printed no Python traceback.

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
program.repair_task_opened = lambda arguments, commit, seat, tests: ("seat", 1, None)
program.merged_branch_last_commit_author_name_read = lambda *a: "author"
program.repair_task_no_longer_open = lambda *a: False
record = Path.home() / ".local/state/nedsnodes/failed-after-merge-test-suites-on-main.json"
record.parent.mkdir(parents=True)
SUITE = "scripts/x-test.py"
FAIL_LINE = [f"FAIL {SUITE} exit 1 — log /logs/x.log"]
def case(verdict, text): return {"verdict": verdict, "name": text, "detail": "", "text": text, "began": 0, "ended": 0, "seconds": 0, "unix_time": 0}
entry = lambda: {"commit": A, "last_failed_commit": A, "pull_request": "9", "log": None, "failed_at": "2026-11-20T00:00:00Z", "repair_task_agent_seat": "seat-x", "repair_task_id": 7}
record.write_text(json.dumps({SUITE: {"failed_tests": {"case a": entry(), "case b": entry()}}}))
log_dir = Path(tempfile.mkdtemp(dir=scratch)); (log_dir / "x.log").write_text("FAIL  case b\n")
runner.write_case_times_suite_resources_and_junit_xml_of_run(log_dir, [{"suite": SUITE, "exit": 1, "cases": [case("FAIL", "case b")], "skips": [], "seconds": 1.0, "log": str(log_dir / "x.log")}])
printed = io.StringIO()
with contextlib.redirect_stdout(printed):
    program.failed_suites_kept_in_view(argparse.Namespace(pull_request="10"), B, repo, log_dir, env, FAIL_LINE)
for line in printed.getvalue().splitlines():
    if "left the failed" in line or line.startswith("STOP"): print(line)
print("record:", sorted(json.loads(record.read_text()).get(SUITE, {}).get("failed_tests", {})))
kept = json.loads(record.read_text())[SUITE]["failed_tests"].get("case a")
print("PASS: case a stays on the record" if kept and kept["repair_task_id"] == 7 else "FAIL: case a left the record")
```

It prints:

```
scripts/x-test.py: case a left the failed suites record: its suite ran to the end and reported nothing for it
record: ['case b']
FAIL: case a left the record
```

The same script prints the same three lines at the head of [PR 4807](https://github.com/nedsnodes/nedsnodes/pull/4807), `016682e0762874cce27a821c2ede28bb68cfdfe2`, which fixes the case where a suite stops before its first case line. The Codex review cell found this case while reviewing that pull request (merge-lane-1's review of PR 4807, Codex finding 1a083af0b57a).

## What is wrong

`case a` never ran at B, yet the merge program took it off the record as if its suite had run every case and reported nothing for it. Its entry, with the pull request that broke it, the commit it first failed at and the link to repair task 7, is deleted. If `case a` still fails once the suite runs to the end again, it comes back as a new failure blamed on whichever pull request merges then, and gets a second repair task. The run also reports nothing that needs attention, because `case b` is already on the record.

The cause is [`test_suite_ran_to_the_end` in `scripts/run-all-test-suites.py`, line 2733](https://github.com/nedsnodes/nedsnodes/blob/63dd962dd16b758eed8b1e08a4fc5526b3659191/scripts/run-all-test-suites.py#L2733). For a suite with case lines that exited nonzero, it returns true whenever one case line says FAIL and the log holds no uncaught Python traceback. The exit code cannot tell a suite that ran every case and failed one from a suite that stopped after its first failure, so this judgment is a guess. The merge program's [`why_it_leaves`, line 775](https://github.com/nedsnodes/nedsnodes/blob/63dd962dd16b758eed8b1e08a4fc5526b3659191/scripts/merge-lane-pull-request-merge-through-merge-gate-with-stacked-pull-request-retarget.py#L775), trusts that guess and deletes every recorded case the suite did not mention. [GHI 4640](https://github.com/nedsnodes/nedsnodes/issues/4640) is the same defect for a suite that stopped before its first case line, and PR 4807 fixes it only for that case.

## What to do

The fix keeps this invariant: a recorded case leaves the record for "reported nothing for it" only on evidence that its suite ran every case it would run, and an exit code alone is not that evidence when the suite failed. One way: `why_it_leaves` removes an unreported case only when its suite exited 0, and keeps it otherwise; this check comes after the checks it already makes, such as the one that keeps every case of a suite that did not run to the end, and `test_suite_ran_to_the_end` stays as it is. The cost is that a case deleted or renamed in a suite that still fails stays on the record until the suite passes once, which a later run repairs on its own. Another way: the runner counts a failed suite as run to the end only when it printed a line that only a finished suite prints. Whoever makes the fix chooses; the second way changes what every suite prints, so it needs the user's approval first.

Add a case to `scripts/merge-lane-pull-request-merge-through-merge-gate-with-stacked-pull-request-retarget-test.py` built from the reproduction above, expecting the record's entry for `case a` to equal, field for field, the entry it held before the run, since `case a` never ran at B; the reproduction's last line prints PASS once the fix is in. When PR 4807 has merged, check whether its early return in `why_it_leaves`, the one for a suite whose only failure is the one named for the suite, is still needed: delete it and run that test file; when no case fails, leave it deleted. When PR 4807 has not merged, there is no such return.
