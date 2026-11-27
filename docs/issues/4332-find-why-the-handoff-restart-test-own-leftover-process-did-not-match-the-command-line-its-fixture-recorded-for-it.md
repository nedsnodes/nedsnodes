---
issue: "[Find why the handoff restart test's own leftover process did not match the command line its fixture recorded for it](https://github.com/nedsnodes/nedsnodes/issues/4332)"
---

# Find why the handoff restart test's own leftover process did not match the command line its fixture recorded for it

## Outcome

Fixed by the pull request that closes this issue, which takes steps 1 and 2 of Next action:

- The cause is the race between `Popen` and exec, though not at the moment the text below names. On ned-box, 930 of 3,000 reads of `/proc/<pid>/cmdline` taken right after `subprocess.Popen(["sleep", "600"], cwd=…)` returned were empty, with `/proc/<pid>/comm` already `sleep`: `Popen` returns once the child's close-on-exec pipe closes, which the kernel does part way through `execve`, before it sets the new program's command line. `ps -o args=` shows such a process as `[sleep]`. Reads through `ps` never caught the window, in 1,000 tries plain and in an unfinished run under `strace -f`, so the command line the failing run recorded stays unknown.
- `start_leftover_in_agent_home()` records `sleep 600`, the command it started, instead of reading it back; so does the `sleep 600` that `process_cases()` hands to `end_process()`, which had the same race.
- `end_leftovers_from_step_2()`'s refusal now says, for each process, that step 2 did not list it, what step 2 listed it as, or that it is a tmux server.
- The case "step 5: a failed resupervise-seat.py ends step 2's leftovers before it is run once more" now makes the fixture's read return `[sleep]`. With the old fixture it fails with this issue's refusal, now ending "2609446: sleep 600 (step 2 listed it as [sleep])"; with the fix it passes.

Step 3 of Next action still applies to any later failure of this kind, whose refusal now shows the recorded command line.

In main's after-merge test run at commit 2df5c2435, the test `nn-systems/handoff/tests/handoff-supervisor-restart-onto-main-code-by-relaunch-from-reference-checkout-test.py` failed its case "step 5: a failed resupervise-seat.py ends step 2's leftovers before it is run once more", and passed when run alone twice afterwards. The log is nedlern@ned-box:/home/nedlern/nedsnodes-logs/seats/merge-lane-2/merge-helpers/pr4242-after-merge-test-run-logs-2df5c243508a/nn-systems__handoff__tests__handoff-supervisor-restart-onto-main-code-by-relaunch-from-reference-checkout-test.py.log.

In that case, step 5 of `nn-systems/handoff/handoff-supervisor-restart-onto-main-code-by-relaunch-from-reference-checkout.py` stopped with "processes other than those left from the old agent-session have their working directory in … so the program stopped: 396: sleep 600". Process 396 was the `sleep 600` the case itself had started as its leftover; it was the first case of the run to start one.

The case does not run the program's step 2. Its fixture plays step 2's part: `state_with_leftover()` calls `start_leftover_in_agent_home()`, which starts `sleep 600` with `subprocess.Popen`, reads its command line at once with `program.process_command_line(leftover.pid)`, and writes that pair into the state file's `agent_home_processes`, where step 2 would have written it. Step 5's `end_leftovers_from_step_2()` treats a process as a leftover only when its process ID and command line both equal that record, so the command line the fixture read for 396 was not `sleep 600`.

What the fixture read is not known: neither the log nor the failure message shows the recorded command line. The likeliest cause is that the read happened between `fork` and `exec`, when `ps` still reports the parent's command line (`python3 …-test.py`). A probe of 3,000 reads taken right after `Popen` of `sleep 600` under CPU load always read `sleep 600`, so the race is rare or the cause is another one; the probe is described in pull request https://github.com/nedsnodes/nedsnodes/pull/4301's description and was not rerun here.

Why it matters: the case can still fail on its own, which fails main's after-merge run and stops the merge queue, as it did once. Pull request https://github.com/nedsnodes/nedsnodes/pull/4301 stops one such failure from failing the later cases too, but does not remove its cause.

Next action:
1. Make the next failure show the answer: have `end_leftovers_from_step_2()` name, in its refusal for each process, the command line the record holds for that process ID, or that the record has none.
2. Fix the fixture so that the record cannot hold a command line read too early: `start_leftover_in_agent_home()` either records `sleep 600` itself, since it knows the command it started, or waits until `program.process_command_line()` reports `sleep 600`, and fails with what it read when it never does.
3. If a later failure shows a recorded command line that is `sleep 600`, or no record at all, the cause is not this race; look again from what that failure's message shows.
