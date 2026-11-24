---
issue: "[The idle sweep sends no put-off handoff reminder when a GitHub prerequisite check of the agent-seat's tasks fails](https://github.com/nedsnodes/nedsnodes/issues/4540)"
---

# The idle sweep sends no put-off handoff reminder when a GitHub prerequisite check of the agent-seat's tasks fails

## Reproduction

The script below, saved as `repro.py`, loads `scripts/agent-seat-idle-sweep-verdicts-print.py` from a worktree of main at 98506562b. It replaces `due_task_hook.unheld_and_held_tasks` with a fake that records one GitHub failure on the checker, as a `gh` call that times out records one, and then calls `rules_three_to_five` for an idle agent-seat that has put off its handoff (`handoff_deferred_marker` is true) and has one open task waiting on a pull request:

```python
import importlib.util, sys, tempfile, pathlib, json, types
from datetime import datetime, timezone
root = pathlib.Path(sys.argv[1])
sys.path.insert(0, str(root / "scripts"))
spec = importlib.util.spec_from_file_location("sweep", root / "scripts/agent-seat-idle-sweep-verdicts-print.py")
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
tmp = pathlib.Path(tempfile.mkdtemp())
tasks = tmp / "tasks"; tasks.mkdir()
(tasks / "1.json").write_text(json.dumps({"id": "1", "subject": "await PR 1", "status": "pending",
    "metadata": {"prerequisites": [{"pr_merged": 1}]}}))
state = tmp / "state"; state.mkdir()
checker = types.SimpleNamespace(gh_failures=[], conditions_skipped_for_budget=[])
def injected(tasks_, d, chk, raised):
    chk.gh_failures.append(("pull request", 1, "gh timed out after 20 seconds"))  # injected timeout
    return [], []
m.due_task_hook.unheld_and_held_tasks = injected
verdict = {"running": {}, "handoff_deferred_marker": True}
try:
    print(m.rules_three_to_five(verdict, datetime(2026, 11, 24, tzinfo=timezone.utc), checker, tasks, state))
except Exception as e:
    print(f"RAISED {type(e).__name__}: {e}")
```

Run as `python3 -I repro.py <worktree path>`, it prints:

```
RAISED ReadFailure: GitHub could not say whether pull request 1 holds: gh timed out after 20 seconds
```

Rule 3 should have returned the `WAKE_HANDOFF_PUT_OFF` decision, because the handoff was put off. Instead `verdict_for_seat` catches the `ReadFailure` (line 951), adds it to the verdict's `errors`, and the agent-seat's verdict carries no rule, so no reminder to run the put-off handoff is sent for that sweep.

The Codex review cell, a pull request reviewer, first found this, with an injected timeout, in merge-lane-2's [review 6035004732](https://github.com/nedsnodes/nedsnodes/pull/4293#pullrequestreview-6035004732) of [PR 4293](https://github.com/nedsnodes/nedsnodes/pull/4293), which does not cause it.

## What is wrong

In `rules_three_to_five`, `open_tasks_nothing_holds` runs before the rule 3 check of `handoff_deferred_marker`. `open_tasks_nothing_holds` asks GitHub about each task's prerequisites and raises `ReadFailure` when any `gh` call fails. Rule 3 does not need that answer: whether the handoff was put off is known without GitHub. So any GitHub failure on any of the agent-seat's task prerequisites, such as a timeout or an outage, stops the handoff reminder for that sweep. The order came in with [PR 4434](https://github.com/nedsnodes/nedsnodes/pull/4434) (commit 1ec6bdad4). An idle agent-seat whose handoff is put off gets no reminder to run it from any sweep in which GitHub fails.

## What to do

The agent-seat ned-box-helper, whose [PR 4434](https://github.com/nedsnodes/nedsnodes/pull/4434) put the task read first, makes the fix. It keeps the task read before rule 3, since that pull request put it there so the verdict carries `open_tasks_nothing_holds`. When `handoff_deferred_marker` is set and that read raises `ReadFailure`, `rules_three_to_five` adds the failure to the verdict's `errors` and still returns rule 3's `WAKE_HANDOFF_PUT_OFF` decision. When `handoff_deferred_marker` is not set, a failed read still raises as today. In `scripts/agent-seat-idle-sweep-verdicts-print-test.py`, add a case that injects the GitHub failure as the script above does, and expects rule 3's decision with the failure in `errors`.
