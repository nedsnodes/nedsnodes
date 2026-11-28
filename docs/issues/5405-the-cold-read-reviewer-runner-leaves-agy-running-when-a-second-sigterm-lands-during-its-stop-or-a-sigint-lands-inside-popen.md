---
issue: "[The cold-read reviewer runner leaves agy running when a second SIGTERM lands during its stop, or a SIGINT lands inside Popen](https://github.com/nedsnodes/nedsnodes/issues/5405)"
---

# The cold-read reviewer runner leaves agy running when a second SIGTERM lands during its stop, or a SIGINT lands inside Popen

The cold-read cells start their reviewer program, such as agy, with `run_reviewer_program_in_own_process_group_until_timeout` in `nn-systems/cold-read/cold-read-cell-common.py`. The reviewer runs in a session of its own, so it is outside the process group that the cold-read grid runner, `nn-systems/cold-read/cold-read-grid.py`, stops when it stops a cell. Only the runner's `except BaseException` handler stops it, by calling `stop_process_tree`. Two signals can stop that handler from killing the reviewer. Each leaves agy running after its cell has exited. Line numbers below are on main at [09e50fda6](https://github.com/nedsnodes/nedsnodes/blob/09e50fda6b6d27cc63179ae120383d25e9a6458b/nn-systems/cold-read/cold-read-cell-common.py).

## Reproduction

Both failures were reproduced on main at 09e50fda6 on ned-box, on 2026-11-27. The harness was a throwaway script, not committed; the test cases under "The fix" repeat what it showed. It called the runner as the agy cell, `nn-systems/cold-read/cold-read-agy-cell.py`, calls it, with the parser the agy cell uses for agy's result line. Its fake agy ignored SIGTERM, as the real agy does, wrote its process ID, and slept for 300 seconds. After the cell process exited, the harness checked whether the fake agy was still alive.

| What the harness did | Cell's exit | Fake agy alive after the cell exited |
|---|---|---|
| One SIGTERM to the cell (control) | 143 | no |
| One SIGTERM, then a second one 0.3 seconds later, during `stop_process_tree`'s one-second grace wait | 143 | **yes** |
| A SIGINT sent from a wrapper around `subprocess.Popen.__init__`, after the real `__init__` had started the fake agy | -2 (uncaught KeyboardInterrupt) | **yes** |

**(a) A second SIGTERM during the stop.** The first SIGTERM raises SystemExit through `exit_on_sigterm`. The handler then calls `stop_process_tree` ([line 753](https://github.com/nedsnodes/nedsnodes/blob/09e50fda6b6d27cc63179ae120383d25e9a6458b/nn-systems/cold-read/cold-read-cell-common.py#L753)). That function sends SIGTERM to the group, waits up to one second, and only then sends SIGKILL ([lines 640-656](https://github.com/nedsnodes/nedsnodes/blob/09e50fda6b6d27cc63179ae120383d25e9a6458b/nn-systems/cold-read/cold-read-cell-common.py#L640-L656)). `exit_on_sigterm` is still the SIGTERM handler while it waits. So a second SIGTERM raises SystemExit inside the wait, and the SIGKILL is never sent. agy ignores SIGTERM, so it keeps running.

**(b) A SIGINT inside Popen after the fork.** The runner records a SIGTERM that comes while `subprocess.Popen` runs, and acts on it once `process` is bound ([lines 711-735](https://github.com/nedsnodes/nedsnodes/blob/09e50fda6b6d27cc63179ae120383d25e9a6458b/nn-systems/cold-read/cold-read-cell-common.py#L711-L735)). It does not do the same for SIGINT. A KeyboardInterrupt raised inside Popen after the fork leaves the Popen call before `process` is bound. The handler that would stop the group is never reached, and agy keeps running.

## Why it matters

An agy that outlives its cell keeps reading and spends model tokens until its own `--print-timeout` ends it. Nothing reports that it is still running. The grid's check for files a stopped cell changed in the working tree runs when the cell has ended, so it never sees what agy writes after that. The runner's docstring says the group is killed when the cell is "sent SIGTERM at any point from the program's start on". Case (a) breaks that promise.

## How the signals could arrive

No program in this repository sends either signal at those points. The grid stops a cell once, in `stop_attempt_and_delete_unfinished_report` in `nn-systems/cold-read/cold-read-grid.py`: one SIGTERM, then SIGKILL after five seconds. The cold-read-fast-read can stop its Question 4 cell twice, from its time-limit timer and from `what_should_be_code_cell_abandon` in `nn-systems/cold-read/cold-read-fast-read.py`. That cell runs `claude`, though, and `claude` exits on the first SIGTERM. A search of `nn-systems/cold-read/` and `scripts/`, excluding tests, for `SIGINT` found no sender to a cell. Both failures therefore need a signal from outside the repository's code, such as a person or an agent running `kill`. No case of either is known.

## The fix

The runner records SIGTERM and SIGINT, instead of acting on them, at two points: while Popen runs, and while the `except BaseException` handler runs `stop_process_tree`. This holds whether Popen returns or raises, such as FileNotFoundError for a missing agy. After each point it puts the handlers back and acts on what it recorded: a recorded SIGTERM ends the cell with exit 143, as before, even when SIGINT was recorded too; a recorded SIGINT alone raises KeyboardInterrupt. A signal recorded during the stop replaces the exception that started the stop. The SIGTERM handler afterwards is `exit_on_sigterm`, as before; the SIGINT handler afterwards is the one the cell had, and a cell started with SIGINT ignored keeps ignoring it. The test cases in `nn-systems/cold-read/tests/cold-read-agy-cell-test.py` cover both failures. Case (a) is caused for real: two SIGTERMs sent to an agy cell whose stub agy ignores SIGTERM. Case (b) is injected through a wrapper around `Popen.__init__`. Both cases fail on 09e50fda6. Two more checks pin the handlers after a failed start: SIGTERM's and SIGINT's are back in place, and an ignored SIGINT is still ignored. No case sends SIGINT during the stop; it goes through the same recording as SIGTERM there. The fix's pull request is cut from main and closes this issue.
