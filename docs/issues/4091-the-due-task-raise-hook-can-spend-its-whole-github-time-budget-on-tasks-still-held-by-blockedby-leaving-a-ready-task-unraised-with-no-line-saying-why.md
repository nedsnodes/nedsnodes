---
issue: "[The due-task raise hook can spend its whole GitHub time budget on tasks still held by blockedBy, leaving a ready task unraised with no line saying why](https://github.com/nedsnodes/nedsnodes/issues/4091)"
---

# The due-task raise hook can spend its whole GitHub time budget on tasks still held by blockedBy, leaving a ready task unraised with no line saying why

## Reproduction

Save the script below as `repro4.py`, make an empty directory to serve as the task directory, and run, from the repository root of a checkout of main at commit 29939797d:

```
python3 -B /path/to/repro4.py scripts/agent-seat-due-task-raise-hook.py /path/to/empty-directory
```

`repro4.py`:

```python
import importlib.util, sys, time
from pathlib import Path
spec = importlib.util.spec_from_file_location("h", sys.argv[1]); h = importlib.util.module_from_spec(spec); spec.loader.exec_module(h)
fake = [0.0]
h.GitHubConditionChecker.clock = staticmethod(lambda: fake[0])
asked = []
def ask_gh(kind, number, timeout):
    asked.append(number); fake[0] += 7  # a slow but successful gh call
    return {"met": number == 99, h.CLOSED_WITHOUT_MERGING_ANSWER_KEY: False, "title": "t", "url": "u"}
h.GitHubConditionChecker.ask_gh = staticmethod(ask_gh)
tasks = {
  "1": {"id": "1", "status": "pending", "subject": "blocker, still open"},
  "2": {"id": "2", "status": "pending", "subject": "held by blocker", "blockedBy": ["1"],
        "metadata": {"prerequisites": [{"pr_merged": 11}, {"pr_merged": 12}, {"pr_merged": 13}]}},
  "3": {"id": "3", "status": "pending", "subject": "ready: waits only on merged PR 99",
        "metadata": {"prerequisites": [{"pr_merged": 99}]}},
}
state = {"raised": {}, "checks": {}}
checker = h.GitHubConditionChecker(state["checks"], time.time())
lines, closed, problems, _ = h.due_task_lines(tasks, Path(sys.argv[2]), state, checker)
print("gh asked about:", asked); print("raise lines:", lines); print("problem lines:", problems)
tasks2 = {"3": tasks["3"]}; asked.clear(); fake[0] = 0.0
state2 = {"raised": {}, "checks": {}}
lines, *_ = h.due_task_lines(tasks2, Path(sys.argv[2]), state2, h.GitHubConditionChecker(state2["checks"], time.time()))
print("control without the held task -> gh asked:", asked, "raise lines:", len(lines))
# Next stop, same state, within the 300 s cache interval:
asked.clear(); fake[0] = 0.0
lines, *_ = h.due_task_lines(tasks, Path(sys.argv[2]), state, h.GitHubConditionChecker(state["checks"], time.time()))
print("second stop, same state -> gh asked:", asked, "raise lines:", len(lines))
```

It printed, on 2026-11-21:

```
gh asked about: [11, 12, 13]
raise lines: []
problem lines: []
control without the held task -> gh asked: [99] raise lines: 1
second stop, same state -> gh asked: [99] raise lines: 1
```

Each GitHub call is made to take 7 seconds against the 20-second budget. Task 2 is held by its open `blockedBy` task 1, so it cannot be raised, yet the hook asks GitHub about its three `pr_merged` pull requests, 11, 12 and 13, which uses up the budget. Task 3, whose one prerequisite has merged, is then answered "not met" without a call, and the stop prints no raise line and no problem line. The control, without task 2, raises task 3. The third run shows the hook raises task 3 at the next stop, once the earlier answers are cached; that holds only while the cache is fresh, `CONDITION_RECHECK_INTERVAL_SECONDS`, 300 seconds (line 240). A next stop more than 300 seconds later asks GitHub about the held task's pull requests again, and can run out of budget the same way.

## What is wrong

Line numbers are those of `scripts/agent-seat-due-task-raise-hook.py` on main at commit 29939797d.

For every open task whose `prerequisites` are not the ones it was last raised for, a task never raised included, `due_task_lines` asks GitHub whether each `pr_merged` pull request closed without merging (lines 683 to 694), before it checks at line 698 whether the task's `blockedBy` tasks still hold it. The docstring, lines 113 to 116, says this is meant: "of a task held by blockedBy, only its `pr_merged` pull requests not yet raised as closed without merging are checked". All gh calls of one run share `GH_CALLS_TOTAL_BUDGET_SECONDS`, 20 seconds (line 242). When the budget is spent, `GitHubConditionChecker` answers every later condition `{"met": False}` (lines 535 to 539), with no problem recorded, so the stop's output does not say a check was skipped.

The harm: a ready task is not raised at a stop where it should be, and nothing tells the agent or a reader of the output that the budget ran out. The hook runs only when the agent ends a turn, so if the agent goes idle after that stop, the task waits for the next turn's end. The idle sweep, which asks GitHub itself about open tasks that nothing holds (GHI 940, § The idle sweep, rule 4), can then wake the agent, but only on its own schedule and through a nudge rather than the raise line.

The design is GHI [Tasks raise themselves when their prerequisites are met, and agent-seats left idle with something to do are woken](https://github.com/nedsnodes/nedsnodes/issues/940), `docs/issues/940-tasks-raise-themselves-when-their-due-time-passes.md`, § What to build, item 2, which says network checks are made at most once every few minutes, each with a short timeout, and sets no total budget. Its § Deferred-decisions lists "Whether item 4's raise of a task whose pull request closed without merging waits for the task's open `blockedBy` tasks, … to be settled when item 4's raise is built"; the hook's docstring above shows the build settled it as not waiting, which is why a held task spends the budget.

## What to do next

The owner, reboot-test, whose pull request [3920](https://github.com/nedsnodes/nedsnodes/pull/3920) added the closed-without-merging checks at lines 683 to 694, by `git blame` on main, fixes the root cause, in two parts:

- A run that runs out of budget says so. A condition answered `{"met": False}` without a gh call because the budget ran out is recorded as a gh failure is (lines 521 to 525), so the stop prints a problem line through the same output that already reports a failed gh call. This part is required, since a failed step is reported, not left silent.
- The budget goes to ready tasks first. Whether a held task's closed-without-merging checks run only after every ready task's checks, only when budget is left, or not at all while the task is held, is the owner's choice; the choice reopens the deferred decision quoted above, so the owner writes it into GHI 940's GHI-MD.

The fix carries a test with the case above, asserting that task 3 gets a raise line, or else that a problem line says the budget ran out. The defect was found by the Codex review cell while reviewing pull request [4001](https://github.com/nedsnodes/nedsnodes/pull/4001), which changes this hook; the defect is on main without it.
