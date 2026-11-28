---
issue: "[Fix-round brief tells the author to delete a complete answers file whose fix-round commit was reset away](https://github.com/nedsnodes/nedsnodes/issues/5400)"
---

# Fix-round brief tells the author to delete a complete answers file whose fix-round commit was reset away

## What goes wrong

The program `scripts/pull-request-fix-round-author-brief-from-blocking-findings-and-one-commit-every-finding-answered-check.py`, run without `--check` to print a fix-round brief, refuses when the topic-worktree is at the frozen-head and the answers file, `fix-round-answers-pull-request-<number>.md`, written after the round's review, has an entry for every finding. The program cannot tell whether a fix-round subagent stopped before making its commit, or whether its commit was reset away. The refusal handles the second case, and the case of an author who means to start the round again, by saying `delete <answers file>, then run this command:` followed by the rerun of the brief (lines 1003 and 1004 on main at 09e50fda6).

The author who follows that loses the answers. When the brief rewrites an answers file that holds text, it first keeps a copy in the round's kept-copies directory, `<git common dir>/fix-round-answers-kept-copies/pr-<number>-review-<round's review id>/`, and names that copy. That keeps answers safe on an ordinary rerun. A file the author deleted is gone before the brief runs, so the brief keeps no copy and names none. When the commit was reset away, the answers file can be the only remaining record of what the fixes were.

## Reproduction

On main at 09e50fda6, using the helpers of the program's test file: make the topic-worktree with a brief run, commit a fix, write an answers file that answers both findings, reset the worktree to the frozen-head, run the brief, delete the answers file as the refusal says, run the brief again, and look for the answers.

The script below, saved as `repro.py` outside the checkout and run from the checkout as `python3 <path to repro.py> scripts/pull-request-fix-round-author-brief-from-blocking-findings-and-one-commit-every-finding-answered-check-test.py`:

```python
import sys, tempfile, datetime, os
from pathlib import Path
test = Path(sys.argv[1]).resolve()
source = test.read_text().split("\ngh_timeout_case()\n")[0]
namespace = {"__file__": str(test), "__name__": "helpers"}
exec(compile(source, str(test), "exec"), namespace)
globals().update(namespace)
with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    repository, base, frozen_head = scratch_repository(root)
    submitted = "2026-11-11T12:00:00Z"
    seconds = datetime.datetime.fromisoformat(submitted.replace("Z", "+00:00")).timestamp()
    routes = routes_for(frozen_head, [dict(review(commit_id=frozen_head), submitted_at=submitted)])
    git(repository, "checkout", "-q", "--detach")
    run(root, repository, routes)
    made = root / "creator-worktrees" / BRANCH
    answers = made / ANSWERS_NAME
    commit_file(made, "hook.py", "fixed\n", "the round's fix")
    answers.write_text(GOOD_ANSWERS); os.utime(answers, (seconds + 60, seconds + 60))
    git(made, "reset", "-q", "--hard", frozen_head)
    code, out, err = run(root, repository, routes)
    print(f"--- brief run, exit {code}, stderr:\n{err}")
    answers.unlink()
    code, out, err = run(root, repository, routes)
    print(f"--- brief rerun after deleting, exit {code}; answers file now: {answers.read_text()!r}")
    kept = Path(git(made, "rev-parse", "--path-format=absolute", "--git-common-dir")) / "fix-round-answers-kept-copies"
    copies = [p.read_text() for p in kept.rglob("*.md")] if kept.exists() else []
    print(f"--- kept copies holding the subagent's answers: {[c for c in copies if c == GOOD_ANSWERS]}")
    print(f"--- brief names a kept copy: {'copied it unchanged' in out}")
```

Its output, with the temporary directory shortened to `<tmp>` and the program's path to `<program>`:

```
--- brief run, exit 1, stderr:
REFUSED: Pull request 7's topic-worktree <tmp>/creator-worktrees/topic-branch-of-the-pull-request is at the frozen-head 7b040da51b2c with no fix-round commit, and its answers file <tmp>/creator-worktrees/topic-branch-of-the-pull-request/fix-round-answers-pull-request-7.md answers every finding of this round, so a fix-round subagent wrote every answer.
If that subagent is still working there, wait for it to finish.
If the answers describe fixes, which means the fix-round commit was reset away, or if you mean to start the round again: delete <tmp>/creator-worktrees/topic-branch-of-the-pull-request/fix-round-answers-pull-request-7.md, then run this command:
cd <tmp>/creator-worktrees/topic-branch-of-the-pull-request && python3 <program> 7
Otherwise finish the round with this command, and do what it says:
cd <tmp>/creator-worktrees/topic-branch-of-the-pull-request && python3 <program> 7 --check

--- brief rerun after deleting, exit 0; answers file now: '1. \n2. \n'
--- kept copies holding the subagent's answers: []
--- brief names a kept copy: False
```

## Source

The Codex review cell found this on [pull request 4453](https://github.com/nedsnodes/nedsnodes/pull/4453), by reading the code. merge-lane-2 asked the agent-seat reboot-test to reproduce it on main, and the user approved sending that request with answer "A" to item 20 of the approval-walk merge-lane-2-maintenance-fix-agent-seat-brief-finding-grading-and-judged-main-findings-approval-walk-2026-11-25. [Fix-round brief: name only this round's answer copies, refuse a staged answers file](https://github.com/nedsnodes/nedsnodes/pull/4748) merged before main at 09e50fda6 and did not change this refusal.

## Next action

Change the refusal so that, instead of saying to delete the answers file, it prints, on a line of its own, one shell command that creates the round's kept-copies directory, the directory named above, when it is missing and moves the answers file into it, and then, on the next line, the rerun of the brief. The moved file's name ends in `.md` and carries the answers file's modification time, so that a second move in the same round does not overwrite the first. The brief already lists every `.md` file in that directory as a kept copy and tells the next fix-round subagent to read it, so the code that lists and names kept copies needs no change. The brief's line for a copy in the round's own directory says that this program copied the file, which is not true of a file the author moved; it should say only that the text is kept unchanged at that path. The line for a copy kept under another review already says only that an earlier brief kept it, and stays as it is. Add a test that runs the printed move command and the rerun, and checks that the moved copy holds every answer and that the brief names it. The agent-seat reboot-test makes this change in its own pull request.
