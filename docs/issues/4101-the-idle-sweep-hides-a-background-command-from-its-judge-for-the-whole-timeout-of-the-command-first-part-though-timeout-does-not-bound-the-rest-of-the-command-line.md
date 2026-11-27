---
issue: "[The idle sweep hides a background command from its judge for the whole `timeout` of the command's first part, though `timeout` does not bound the rest of the command line](https://github.com/nedsnodes/nedsnodes/issues/4101)"
---

# The idle sweep hides a background command from its judge for the whole `timeout` of the command's first part, though `timeout` does not bound the rest of the command line

## Reproduction

Make a worktree of main at commit 45fd905ec, such as with `git worktree add --detach /tmp/sweep-45fd905ec 45fd905ec`, save the script below as `timeout-bounds-first-part-only-repro.py` in a directory of its own, and run `python3 timeout-bounds-first-part-only-repro.py /tmp/sweep-45fd905ec`. It asks `timeout_seconds_of_command_line` in `scripts/agent-seat-idle-sweep-verdicts-print.py` how long three compound command lines are bounded, then runs, in bash, a line whose first part is `timeout 1 true`, to show that the rest of the line runs past that first part's one-second `timeout`.

```python
"""Finding 3: the deadline that hides a background command from the judge is taken from a
leading `timeout`, which bounds only the first command of a compound line."""
import importlib.util, sys, subprocess, time
from pathlib import Path
root = Path(sys.argv[1])
spec = importlib.util.spec_from_file_location("v", root / "scripts/agent-seat-idle-sweep-verdicts-print.py")
v = importlib.util.module_from_spec(spec); spec.loader.exec_module(v)
for line in ["timeout 1h build && publish", "timeout 1h build; sleep 99999", "timeout 30m a | b"]:
    print(repr(line), "-> hidden from judge for", v.timeout_seconds_of_command_line(line), "s")
t = time.time()
p = subprocess.run(["bash", "-c", "timeout 1 true && timeout 3 sleep 3; echo second part ran past the first timeout"], capture_output=True, text=True)
print(p.stdout.strip(), f"(elapsed {time.time()-t:.1f}s > 1s bound)")
```

It printed, on 2026-11-21:

```
'timeout 1h build && publish' -> hidden from judge for 3600.0 s
'timeout 1h build; sleep 99999' -> hidden from judge for 3600.0 s
'timeout 30m a | b' -> hidden from judge for 1800.0 s
second part ran past the first timeout (elapsed 3.0s > 1s bound)
```

For `timeout 1h build && publish`, `timeout` bounds only `build`. When `build` ends at once and `publish` hangs, the idle sweep still counts the command as inside its own limit for an hour, so an idle agent-seat waiting on the hung `publish` is not nudged until the hour has passed.

## What is wrong

Line numbers are those of `scripts/agent-seat-idle-sweep-verdicts-print.py` on main at commit 45fd905ec. `TIMEOUT_COMMAND_LINE_START_PATTERN`, lines 105 to 108, matches a `timeout` and its duration at the start of a command line and ignores what follows, and `timeout_seconds_of_command_line`, lines 414 to 421, returns that duration as the bound of the whole line. Both came from commit 0988d9422, in pull request [3924](https://github.com/nedsnodes/nedsnodes/pull/3924).

The rule they carry out was approved by the user on 2026-11-18, item 55 of approval-walk md-skills-questions-waiting-2026-11-05, as commit 0988d9422's message records: at the idle sweep's rule 5, a command whose own timeout has not yet ended is work under way. A command line that joins other commands to the `timeout` with an unquoted `&&`, `||`, `;`, `|`, `&` or newline runs those other commands outside that limit: after the first part ends for `&&`, `||`, `;` and newline, and alongside it for `|` and `&`.

The defect was found by the Codex review cell, `scripts/code-review-codex-cell.py`, while reviewing pull request [4021](https://github.com/nedsnodes/nedsnodes/pull/4021), which does not change this code.

## What to do next

The owner, ned-box-helper, fixes the root cause: a command line counts as bounded by `timeout` only when no unquoted control operator follows the `timeout` command, such as by tokenizing the line with `shlex.shlex(command, posix=True, punctuation_chars=True)`, so that `timeout 1h bash -c 'a && b'` stays bounded; any other line gets no deadline, as a line with no `timeout` gets none today, and is judged as any running command is. The fix keeps the user's ruling for commands wholly inside their `timeout`, and carries a table-driven test with one line for each operator named above and the quoted `bash -c` line.

## Outcome

[Pull request 4078, "Idle sweep: take a timeout end only when the timeout stops the whole command line"](https://github.com/nedsnodes/nedsnodes/pull/4078), merged on 2026-11-22 at 02:48Z, fixed this defect: on main, a command line with an unquoted `&&`, `||`, `;`, `&` or newline after its `timeout` command gets no deadline, and `timeout 1h bash -c 'a && b'` keeps its deadline. Every pipe keeps the deadline, as in `timeout 600 pytest 2>&1 | sort`, so the stricter rule under "What to do next", which would also take the deadline from pipes, was not carried out, and [pull request 4109](https://github.com/nedsnodes/nedsnodes/pull/4109), which built that rule, was closed unmerged. The user ruled on 2026-11-24, at item 10.2 of approval-walk ned-box-helper-open-items-approval-walk-2026-11-22, that a pipe into a never-ending command, such as `| tail -f`, needs no rule, because none of the 585 background `timeout` commands started on ned-box in the prior 30 days did this; the Mac's commands were not counted. No work remains.
