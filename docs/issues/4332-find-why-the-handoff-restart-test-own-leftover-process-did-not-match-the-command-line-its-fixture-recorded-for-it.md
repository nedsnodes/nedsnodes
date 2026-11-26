---
issue: "[Find why the handoff restart test's own leftover process did not match the command line its fixture recorded for it](https://github.com/nedsnodes/nedsnodes/issues/4332)"
---

# Find why the handoff restart test's own leftover process did not match the command line its fixture recorded for it

In main's after-merge test run at commit 2df5c2435, the test `nn-systems/handoff/tests/handoff-supervisor-restart-onto-main-code-by-relaunch-from-reference-checkout-test.py` failed its case "step 5: a failed resupervise-seat.py ends step 2's leftovers before it is run once more", and passed when run alone twice afterwards. The log is nedlern@ned-box:/home/nedlern/nedsnodes-logs/seats/merge-lane-2/merge-helpers/pr4242-after-merge-test-run-logs-2df5c243508a/nn-systems__handoff__tests__handoff-supervisor-restart-onto-main-code-by-relaunch-from-reference-checkout-test.py.log.

In that case, step 5 of `nn-systems/handoff/handoff-supervisor-restart-onto-main-code-by-relaunch-from-reference-checkout.py` stopped with "processes other than those left from the old agent-session have their working directory in … so the program stopped: 396: sleep 600". Process 396 was the `sleep 600` the case itself had started as its leftover; it was the first case of the run to start one.

The case does not run the program's step 2. Its fixture plays step 2's part: `state_with_leftover()` calls `start_leftover_in_agent_home()`, which starts `sleep 600` with `subprocess.Popen`, reads its command line at once with `program.process_command_line(leftover.pid)`, and writes that pair into the state file's `agent_home_processes`, where step 2 would have written it. Step 5's `end_leftovers_from_step_2()` treats a process as a leftover only when its process ID and command line both equal that record, so the command line the fixture read for 396 was not `sleep 600`.

What the fixture read is not known: neither the log nor the failure message shows the recorded command line. The likeliest cause is that the read happened between `fork` and `exec`, when `ps` still reports the parent's command line (`python3 …-test.py`). A probe of 3,000 reads taken right after `Popen` of `sleep 600` under CPU load always read `sleep 600`, so the race is rare or the cause is another one; the probe is described in pull request https://github.com/nedsnodes/nedsnodes/pull/4301's description and was not rerun here.

Why it matters: the case can still fail on its own, which fails main's after-merge run and stops the merge queue, as it did once. Pull request https://github.com/nedsnodes/nedsnodes/pull/4301 stops one such failure from failing the later cases too, but does not remove its cause.

Next action:
1. Make the next failure show the answer: have `end_leftovers_from_step_2()` name, in its refusal for each process, the command line the record holds for that process ID, or that the record has none.
2. Fix the fixture so that the record cannot hold a command line read too early: `start_leftover_in_agent_home()` either records `sleep 600` itself, since it knows the command it started, or waits until `program.process_command_line()` reports `sleep 600`, and fails with what it read when it never does.
3. If a later failure shows a recorded command line that is `sleep 600`, or no record at all, the cause is not this race; look again from what that failure's message shows.
