---
issue: "[Keep the shell's diagnosis when a Mac-side ask cannot enter ghi-guide-agent's agent-home, in `scripts/ghi-guide-agent-ask.py`](https://github.com/nedsnodes/nedsnodes/issues/4329)"
---

# Keep the shell's diagnosis when a Mac-side ask cannot enter ghi-guide-agent's agent-home, in `scripts/ghi-guide-agent-ask.py`

## Reproduction

Run on ned-box on 2026-11-22, in a worktree detached at origin/main 6417d79ce. The script below builds the command a Mac-side ask sends over ssh, with `build_remote_command()` from `scripts/ghi-guide-agent-ask.py`, runs it with `bash -c` in place of ned-box's login shell, under a `HOME` whose `agents/ghi-guide-agent` cannot be entered, and then applies to the stderr the same expression `scripts/ghi-issue-write.py` uses to pick the reason it reports (its lines 1166 to 1170 on that commit). Save it as `repro.py`.

```python
import importlib.util, subprocess, sys, os
spec = importlib.util.spec_from_file_location("ask", sys.argv[1] + "/scripts/ghi-guide-agent-ask.py")
ask = importlib.util.module_from_spec(spec); spec.loader.exec_module(ask)
cmd = ask.build_remote_command("Is there a GHI about X?", False, "nedsnodes/nedsnodes")
for home in sys.argv[2:]:
    done = subprocess.run(["bash", "-c", cmd], capture_output=True, text=True,
                          env={**os.environ, "HOME": home})
    print(f"== HOME={home}\nexit {done.returncode}\nstderr:\n{done.stderr}", end="")
    lines = [l.strip() for l in done.stderr.splitlines() if l.strip()]
    why = next((l for l in lines if "ghi-guide-agent's answer is not usable:" in l), lines[-1] if lines else None)
    print(f"ghi-issue-write.py would report: adjudication skipped: ghi-guide-agent did not answer: {why}\n")
```

Setup and run, with `$S` an empty scratch directory and `$W` the worktree:

```bash
mkdir -p $S/home-file/agents $S/home-noperm/agents/ghi-guide-agent
touch $S/home-file/agents/ghi-guide-agent            # a file, not a directory
chmod 000 $S/home-noperm/agents/ghi-guide-agent      # a directory that cannot be entered
python3 -I repro.py $W $S/home-file $S/home-noperm
```

Output, with the scratch directory's full path written as `$S`:

```text
== HOME=$S/home-file
exit 1
stderr:
bash: line 2: cd: $S/home-file/agents/ghi-guide-agent: Not a directory
ghi-guide-agent-ask: could not enter the ghi-guide-agent seat at $S/home-file/agents/ghi-guide-agent on this box — bootstrap it (a checkout of this repository at that path), then retry
ghi-issue-write.py would report: adjudication skipped: ghi-guide-agent did not answer: ghi-guide-agent-ask: could not enter the ghi-guide-agent seat at $S/home-file/agents/ghi-guide-agent on this box — bootstrap it (a checkout of this repository at that path), then retry

== HOME=$S/home-noperm
exit 1
stderr:
bash: line 2: cd: $S/home-noperm/agents/ghi-guide-agent: Permission denied
ghi-guide-agent-ask: could not enter the ghi-guide-agent seat at $S/home-noperm/agents/ghi-guide-agent on this box — bootstrap it (a checkout of this repository at that path), then retry
ghi-issue-write.py would report: adjudication skipped: ghi-guide-agent did not answer: ghi-guide-agent-ask: could not enter the ghi-guide-agent seat at $S/home-noperm/agents/ghi-guide-agent on this box — bootstrap it (a checkout of this repository at that path), then retry
```

In both cases the shell's own diagnosis, `Not a directory` or `Permission denied`, is on the first stderr line, and `scripts/ghi-issue-write.py` reports only the second, which tells the agent to bootstrap the agent-home whatever the cause. An agent-home that exists but cannot be entered is then reported as one that is missing.

## What is wrong

When `scripts/ghi-guide-agent-ask.py` runs anywhere but ned-box, `main()` sends the command `build_remote_command()` builds to ned-box over ssh, then writes ned-box's stderr to its own stderr unchanged (`sys.stderr.write(completed.stderr)`). That command starts with a shell preflight, `cd "$seat" || { echo "...bootstrap it..." >&2; exit 1; }`, which runs before the ned-box copy of the program, and so before its `main()`. A failed `cd` therefore leaves two stderr lines: the shell's diagnosis, then the generic remedy.

`scripts/ghi-issue-write.py`, when the ask returns no answer, reports one stderr line of the ask: the line holding "ghi-guide-agent's answer is not usable:" when there is one, and otherwise the last line. The docstring of `build_remote_command()` says the shell's diagnosis is kept because it names the real cause; for a caller that reads the last line only, it is dropped.

Pull request [ghi-guide-agent ask: a failed ask's reason is put on one line where it reaches stderr](https://github.com/nedsnodes/nedsnodes/pull/4295), open on 2026-11-22, puts every failure that the ask's `main()` writes through one function, `ask_failure_print_to_stderr_on_one_line`, and leaves the relayed ned-box stderr unchanged on purpose. The agent-home preflight is the one failure that never reaches a `main()`, so that pull request does not cover it. The Codex review cell found this path while reviewing pull request 4295 at base f0ad767c6; its report is `nedlern@ned-box:/home/nedlern/nedsnodes-logs/seats/merge-lane-2/merge-helpers/cx/pr4295-f0ad767c/codex-code-review-report.md`. Pull request 4295 does not make the defect happen: main behaves as the reproduction shows.

## Root cause

The rule that a failed ask reports its reason on one stderr line, which `scripts/ghi-issue-write.py` relies on, is kept by the ask's `main()`. The agent-home preflight is shell text inside `build_remote_command()` that runs outside any `main()`, and the Mac side relays its output without passing it through that rule.

## What to do

The agent-seat reboot-test, which wrote the one-line rule in pull requests 4275 and 4295 and the last-line reading in `scripts/ghi-issue-write.py`, fixes the root cause: a failed entry into the agent-home must reach `scripts/ghi-issue-write.py` with the shell's diagnosis in the reason it reports, and with the remedy. Two ways that work, for reboot-test to choose between: have the preflight shell capture the `cd` error, join it onto one line, and echo it inside the remedy line; or make the failure's reason structural rather than positional, for example by having a failed ask under `--print-answer-json` put a JSON object with a `reason` field on stdout, which the preflight shell can echo too, and having `scripts/ghi-issue-write.py` read that field instead of picking a stderr line. Moving the preflight into the ned-box copy of the program does not work, because that copy lives in the agent-home that could not be entered. The ned-box copy's `main()` also checks the agent-home (`if not seat_dir.is_dir()`) with a remedy of its own; the fix keeps the two remedies consistent, or leaves one check.

When the agent-home was entered and the ned-box copy of the program started, leave its relayed stderr unchanged, as pull request 4295 does.

Add a test that builds the command with `build_remote_command()` and runs it under a `HOME` whose `agents/ghi-guide-agent` is missing, is a file, and is a directory that cannot be entered, as the reproduction does, and checks that the reason `scripts/ghi-issue-write.py` reports contains `No such file or directory`, `Not a directory` and `Permission denied` respectively. The test gets that reason from `scripts/ghi-issue-write.py`'s own code, such as its line-picking moved into a named function the test calls, not from a copy of the expression as the reproduction uses.
