---
issue: "[The GHI write tool, `scripts/ghi-issue-write.py`, resuming a design filing that an older create-GHI pushed as `<number>-<slug>.md`, tells the agent to rerun create-GHI on a `.tool.design.md` path that will not exist](https://github.com/nedsnodes/nedsnodes/issues/4096)"
---

# The GHI write tool, `scripts/ghi-issue-write.py`, resuming a design filing that an older create-GHI pushed as `<number>-<slug>.md`, tells the agent to rerun create-GHI on a `.tool.design.md` path that will not exist

## Reproduction

Make a worktree of main at commit 45fd905ec, such as with `git worktree add --detach /tmp/ghi-write-45fd905ec 45fd905ec`, save the script below as `ghi-design-resume-path-repro.py` in a directory of its own, and run `python3 ghi-design-resume-path-repro.py /tmp/ghi-write-45fd905ec`. The script stands in for git and GitHub: the remote holds the filing branch `ghi-4100-widget`, which create-GHI as it was before commit 3802f4a35 pushed with the file `docs/issues/4100-widget.md`, and that branch's pull request is open. It then runs today's `land_file` (step 4) and `link_body` (step 5) on the author's file `widget.tool.design.md`.

```python
"""Finding 1: a design filing whose branch was pushed by the pre-3802f4a35
create (file <n>-<slug>.md) is resumed by today's create, which reuses the
branch but tells the agent to rerun on <n>-<slug>.tool.design.md."""
import importlib.util, sys, tempfile, types
from pathlib import Path
root = Path(sys.argv[1])
spec = importlib.util.spec_from_file_location("g", root / "scripts/ghi-issue-write.py")
g = importlib.util.module_from_spec(spec); spec.loader.exec_module(g)
number, title = 4100, "Widget"
src = Path(tempfile.mkdtemp()) / "widget.tool.design.md"
src.write_text("# Widget\n\nbody\n")
old_branch_file = f"docs/issues/{number}-{g.slug(title)}.md"   # what 3802f4a35^ pushed
def runner(cmd, cwd=None, **k):
    out = ""
    if cmd[:2] == ["git", "ls-remote"]:
        out = f"abc\trefs/heads/ghi-{number}-{g.slug(title)}\n"
    return types.SimpleNamespace(stdout=out, returncode=0)
g.blob_at = lambda *a, **k: None
g.existing_pull_request_for_branch = lambda *a, **k: {"title": title, "url": "u"}
g.ghi_md_paths_for_issue = lambda *a, **k: []
dest = g.land_file("o/r", number, title, src, root, runner, print)
g.link_body("o/r", number, root, runner, print, dest)
print("FILE ON PUSHED BRANCH (lands on main):", old_branch_file)
print("PATH THE RERUN IS TOLD TO USE:        ", dest, "-> exists after merge:", dest == old_branch_file)
```

It printed, on 2026-11-21:

```
step 4 already done: pull request [Widget](u) is waiting for merge-lane
step 5 not done: no file for issue 4100 is on main yet, so its body keeps the placeholder.
Once the pull request from step 4 merges, pull main and rerun: scripts/ghi-issue-write.py create docs/issues/4100-widget.tool.design.md
FILE ON PUSHED BRANCH (lands on main): docs/issues/4100-widget.md
PATH THE RERUN IS TOLD TO USE:         docs/issues/4100-widget.tool.design.md -> exists after merge: False
```

The pull request merges `docs/issues/4100-widget.md`, but the tool tells the agent to rerun create-GHI on `docs/issues/4100-widget.tool.design.md`, which main will not hold. That rerun fails, and the agent has to work out by hand which file to give it.

## What is wrong

Line numbers are those of `scripts/ghi-issue-write.py` on main at commit 45fd905ec. `land_file`, from line 1869, works out the destination from today's naming rule, `create_ghi_landing_path_for_ghi_md`, before it looks at the remote. When the filing branch is already on the remote, with an open pull request or without one, it returns that computed destination without reading which file the branch actually holds. `link_body`, from line 2062, prints that destination as the path to rerun create-GHI on; the rerun needs the path only to find the issue's number, through `issue_whose_filing_stopped_before_step_5`, which requires the file to exist. Commit 3802f4a35, from pull request [3963](https://github.com/nedsnodes/nedsnodes/pull/3963), changed the naming rule so that a design keeps its `.<kind>.design` ending, such as `.tool.design`; a filing pushed before that commit holds the old name, so the destination `land_file` returns differs from the file the pull request merges, and step 5's rerun line names the wrong file.

No filing is affected now: merge-lane-2 checked the 23 `ghi-*` create branches on the remote on 2026-11-21, and none is a design filing pushed under the old name. The same mismatch would come back whenever the naming rule changes again while a filing waits.

The defect was found by the Codex review cell while reviewing pull request [4021](https://github.com/nedsnodes/nedsnodes/pull/4021), which does not change this code.

## What to do next

The owner, cold-read-improvement, the agent-seat whose pull request 3963 changed the naming rule, fixes the root cause: the rerun line step 5 prints must not depend on the naming rule staying the same while a filing waits. Two ways are open, and the choice is the owner's. The rerun line can name the file the pushed branch holds, read from that branch, when the branch is already on the remote. Or, since `link_body` finds the issue's files on main by the issue's number and the rerun uses the path only to find that number, the rerun can be keyed by the issue's number instead of a path, so no naming change can break it. The fix carries a test with the case above. The design of the tool is GHI [783](https://github.com/nedsnodes/nedsnodes/issues/783), `docs/issues/783-link-supporting-documents-and-name-issues.tool.design.md`; the owner updates it where it describes the rerun after step 4.
