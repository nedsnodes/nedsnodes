---
issue: "[The handoff-supervisor's waiting approval-walk item line takes a directory name in the next step as naming an approval-walk](https://github.com/nedsnodes/nedsnodes/issues/4334)"
---

# The handoff-supervisor's waiting approval-walk item line takes a directory name in the next step as naming an approval-walk

## Reproduction

The script below, saved as `repro.py`, loads the handoff-supervisor from a detached worktree of main at 14f3e6e70 (`14f3e6e707809ac679adc2b841791088e7fc4ffc`), made with `git worktree add --detach <path> origin/main`. In a temporary directory it makes two open approval-walks under `docs/walk/`: `A-walk`, waiting on item 1, and `B-walk`, waiting on item 2. `A-walk` has the newer walk-minutes, so `B-walk` is chosen only when the next step is found to name it. It then calls `successor_initial_agent_instructions_line_naming_waiting_approval_walk_item` in `nn-systems/handoff/handoff-supervisor.py` with two next steps. The second next step names `A-walk` only as a directory in a path, and tells the successor to resume `B-walk`:

```python
import importlib.util, os, sys, tempfile, time
from pathlib import Path
wt = Path(sys.argv[1])
spec = importlib.util.spec_from_file_location("fx", wt / "nn-systems/handoff/tests/handoff-supervisor-test-fixture.py")
fx = importlib.util.module_from_spec(spec); spec.loader.exec_module(fx)
DOC = "# W

## Item 1 of 2: First

Recommendation: x.

## Item 2 of 2: Second

Recommendation: y.
"
root = Path(tempfile.mkdtemp()); d = root / "docs" / "walk"; d.mkdir(parents=True)
for name, item in (("A-walk", "1"), ("B-walk", "2")):
    (d / f"{name}.md").write_text(DOC); (d / f"{name}-minutes.md").write_text(f"#next_to_present item {item} of 2
")
os.utime(d / "B-walk-minutes.md", (time.time() - 3600,) * 2)  # A-walk has the newer walk-minutes
for step in ("Resume approval-walk B-walk.",
             "Read cold-read-records/A-walk/cold-read-triage.md, then resume approval-walk B-walk."):
    print("next_step:", step)
    for line in fx.supervisor.successor_initial_agent_instructions_line_naming_waiting_approval_walk_item(root, step):
        print("  ->", line[:90], "...")
```

Run as `python3 repro.py <worktree path>`, it prints:

```
next_step: Resume approval-walk B-walk.
  -> Approval-walk B-walk: item 2 of 2, Second, is waiting for the user; the walk-minutes recor ...
next_step: Read cold-read-records/A-walk/cold-read-triage.md, then resume approval-walk B-walk.
  -> Approval-walk A-walk: item 1 of 2, First, is waiting for the user; the walk-minutes record ...
```

The first line shows that `resume approval-walk B-walk` in prose is found as naming `B-walk`. The second next step names `B-walk` the same way and should give the same line; it gives `A-walk`'s, because `A-walk` appears earlier in the text, as a directory.

## What is wrong

The handoff-supervisor adds a line to a successor's initial-agent-instructions naming the open approval-walk's waiting item and its last page link; the handoff design, `nn-systems/handoff/handoff.system.design.md`, says that when several approval-walks are open the line names "the one the session-handoff's next step names, or else the one with the latest walk-minutes". The function picks that approval-walk by searching the next step's text for each open approval-walk's name, at [lines 1290 to 1298 of `handoff-supervisor.py` at 14f3e6e70](https://github.com/nedsnodes/nedsnodes/blob/14f3e6e707809ac679adc2b841791088e7fc4ffc/nn-systems/handoff/handoff-supervisor.py#L1290-L1298), and takes the approval-walk whose name appears first. The pattern refuses a name followed by a word character or `-`, and treats every other character after it as the end of the name, `/` included, so a directory that has an approval-walk's name counts as naming that approval-walk.

That collision is built into the project's naming: the /walk-me-through skill, `.claude/skills/walk-me-through/SKILL.md`, names an approval-walk that rules on a cold-read-full-run by its cold-read-record's name, and that approval-walk's rulings are recorded in that cold-read-record's `cold-read-triage.md`, under `cold-read-records/<name>/`. So a next step that mentions a cold-read-record's triage file before the approval-walk it says to resume selects the cold-read approval-walk instead.

## What goes wrong for the agent

The successor's first prompt names the wrong approval-walk's waiting item and tells it to open that item's page, or publish it, and show it in full in its first message. The successor then shows the user an item from an approval-walk the previous agent-session did not mean to resume, and, when it publishes the page, appends an `#item_page` line to that approval-walk's walk-minutes. The user has to notice and redirect it; nothing is lost, but the turn is wasted and the wrong walk-minutes gain a line.

## Where it was found

Codex found it in the round-2 review of pull request [#4290](https://github.com/nedsnodes/nedsnodes/pull/4290), which changes the same pattern. merge-lane-2's review there records that the pattern on main and the pattern at that pull request's head both match `A-walk` at the directory name, so the defect is main's, not that pull request's.

## What to do next

The owner of this code, the agent-seat fleet-restart-at-login, which wrote it in pull requests [#4095](https://github.com/nedsnodes/nedsnodes/pull/4095), [#4197](https://github.com/nedsnodes/nedsnodes/pull/4197) and [#4236](https://github.com/nedsnodes/nedsnodes/pull/4236), fixes the root cause: the function guesses from free prose which approval-walk the retiring agent meant, by matching each name against the text with a hand-written pattern of which characters may end a name, and each revision of that pattern has let a new form through or shut a valid one out; pull request #4290 is revising it again. One way to remove the guess is a structured field in the session-handoff that names the approval-walk to resume, chosen by the handoff writer from the open approval-walks and checked against `docs/walk/` when the session-handoff is written, which the handoff-supervisor reads instead of searching the next step. GHI [#2412](https://github.com/nedsnodes/nedsnodes/issues/2412), still open, lists as one candidate having code draft the open approval-walks into the next step; that drafts the list but not the choice among them. If the fix keeps searching the prose instead, it must say what counts as naming an approval-walk so that a plain mention such as `resume approval-walk B-walk` still counts and a directory in another path does not. Add the reproduction above as a test case, asserting that the second next step's line begins `Approval-walk B-walk:`, in `nn-systems/handoff/tests/handoff-supervisor-successor-initial-agent-instructions-line-naming-waiting-approval-walk-item-test.py`, failing before the fix and passing after it.
