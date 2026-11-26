---
issue: "[scripts/merge-gate-test.py passes a case that expects a scripted gh failure when its gh fake fails instead](https://github.com/nedsnodes/nedsnodes/issues/4995)"
---

# scripts/merge-gate-test.py passes a case that expects a scripted gh failure when its gh fake fails instead

## Reproduction

Codex found this defect as Codex finding 3bf3cc8eb59a in merge-lane-3's round-2 review of [PR 4878](https://github.com/nedsnodes/nedsnodes/pull/4878), review [6068534939](https://github.com/nedsnodes/nedsnodes/pull/4878#pullrequestreview-6068534939), which grades it as a defect to file as a GHI rather than fix in PR 4878, because main already has it and PR 4878 does not cause it. The graded findings are in `nedlern@ned-box:/home/nedlern/nedsnodes-logs/seats/merge-lane-3/pr4878-review-round-2.json`. merge-lane-3 reproduced it on main at [3e67fb9e7f9e24684740fdceb44ca1f7c4c03ebc](https://github.com/nedsnodes/nedsnodes/tree/3e67fb9e7f9e24684740fdceb44ca1f7c4c03ebc) on 2026-11-25.

The case `case_e9_inline_channel_fails_after_its_first_page` arranges a scripted gh failure: the `inline:paginated` route prints a first page and then exits with a captured 404's exit code and stderr, and the case expects `scripts/merge-gate.sh` to exit 2 with the message that it could not read the inline comments. The script below removes that route before `run_gate` writes the routes, so the gh fake, `GH_STAND_IN`, meets a gh call nobody arranged and exits 97 itself. Save the script as `repro.py` and run `python3 -B repro.py scripts/merge-gate-test.py` from the root of a checkout of main:

```python
import importlib.util, sys
from pathlib import Path
spec = importlib.util.spec_from_file_location("merge_gate_test", Path(sys.argv[1]))
suite = importlib.util.module_from_spec(spec)
spec.loader.exec_module(suite)
real_run_gate = suite.run_gate
def run_gate_without_the_inline_route(gate, pr, expected, since, routes, **options):
    routes = {key: route for key, route in routes.items() if key != "inline:paginated"}
    return real_run_gate(gate, pr, expected, since, routes, **options)
suite.run_gate = run_gate_without_the_inline_route
passed, summary = suite.case_e9_inline_channel_fails_after_its_first_page(suite.GATE)
print("PASS" if passed else "FAIL")
print(summary)
```

The script prints `PASS`. The summary shows exit 2, and stderr starting `merge-gate-test stand-in: unarranged gh call ['api', 'repos/nedsnodes/nedsnodes/pulls/667/comments', '--paginate']`, followed by the message the case expected: `GATE COULD NOT RUN: could not read the inline comments of pull request 667; any error gh printed is just above this line.` So the case passed although the scripted failure it was arranged to test never ran.

## Why it happens

`scripts/merge-gate.sh` turns every failing gh call into the same exit 2 and the same message, whatever made gh fail. `run_gate` in `scripts/merge-gate-test.py` returns a `Run` holding only the exit code, stdout, stderr and the logged gh calls. The helpers that judge a `Run`, such as `could_not_run_after_gh` and `refused_with`, test only the exit code, the calls and substrings of stderr. Nothing records that the gh fake failed for a reason of its own. The fake's failure adds its own line to stderr, but the `Run` it gives still has the exit code and the stderr phrases the case looks for, so the case passes as if the scripted failure had run. On main the fake fails for a reason of its own in one way: exit 97, for an unarranged gh call. PR 4878, open when this GHI-MD was written, replaces the fake with a bash script that adds exit 96, for a call the fake could not log, and exit 98, for a route body the fake could not send; the defect covers all three.

## Why it matters

A case that expects a scripted gh failure keeps passing after the arrangement it depends on breaks, for example after a change to the fake's routing or to a gh command `scripts/merge-gate.sh` runs. The suite then reports a failure path of `scripts/merge-gate.sh` as tested when no test exercises it. On main, `scripts/merge-gate-test.py` calls `could_not_run_after_gh` or `refused_with` 46 times (`grep -c 'co## What to do

Make `run_gate` report a failure of the gh fake for every case, apart from the case's own verdict. Send every exit the fake makes for a reason of its own through one function in the fake that appends a line, naming the reason, to a file whose path `run_gate` passes in the fake's environment, and then exits; today that is the bare `sys.exit(97)` in `GH_STAND_IN`, and in PR 4878's bash fake one shell function for exits 96, 97 and 98. After the fake has run, `run_gate` reads the file and, when the file is not empty, records a failed check of its own with `check`, naming the case and the reason, so that the suite exits 1. The failed check must not come only through the case's return value: in `run_mutations`, a case that returns false counts as having detected the mutation, so a false verdict there would hide the fake's failure instead of reporting it. Exit codes alone cannot tell the two failures apart, because a route may script any exit code.

Add a test that runs `run_gate` once for each exit the fake makes for a reason of its own, such as with a route removed as the script above does, and checks that `failures` gained the entry, then takes the entry out again so that the suite's own result is not changed; the test fails before the fix. The agent-seat mac-claude, which wrote `run_gate` in commit 980401662, "The merge gate enters the repository, with a test for every refusal", owns this fix.
