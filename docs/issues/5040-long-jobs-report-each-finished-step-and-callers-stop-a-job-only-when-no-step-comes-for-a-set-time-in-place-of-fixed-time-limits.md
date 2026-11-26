---
issue: "[Long jobs report each finished step, and callers stop a job only when no step comes for a set time, in place of fixed time limits](https://github.com/nedsnodes/nedsnodes/issues/5040)"
kind: design
---

# Long jobs report each finished step, and callers stop a job only when no step comes for a set time, in place of fixed time limits

## Why

Today a caller gives each long job one fixed time limit. For example, `scripts/ghi-issue-write.py` waits up to 2,220 seconds for ghi-guide-agent's first answer after a fresh start. That figure is an estimate of the worst case: 220 file reads at 8.2 seconds each. The one fresh start timed since then read 1 file and answered in 6 seconds (unverified). A fixed limit therefore has to be sized for a rare worst case, and a job that is stuck keeps its caller waiting for the whole limit.

The user proposed the change below on 2026-11-24, while reading item 21 of approval-walk reboot-test-undecided-items-carried-over-from-git-worktrees-redesign-approval-walk-2026-11-22 (its minutes, line 174, at nedlern@ned-box:/home/nedlern/nedsnodes-logs/walk/reboot-test-undecided-items-carried-over-from-git-worktrees-redesign-approval-walk-2026-11-22-minutes.md). Item 92 of the same approval-walk, settled on 2026-11-26, files this GHI and brings its design back to him for approval.

## The proposal

- When a job starts, it reports that it started. A job that runs a model, such as `claude -p`, agy or Codex, reports nothing itself: its caller reads its steps from its transcript or output stream, as the last point says.
- As it finishes each step, it reports that step, such as "read file 40 of 220".
- It reports done only when it is done.
- The caller stops the job when no new step has come for a set time, such as 5 minutes. A message that only says the job is still running does not count, so a job that is alive but stuck is still stopped.
- An overall limit, set far above a usual run, also stops a job that keeps reporting steps forever.
- The caller's code, not the model, decides what counts as a step and what counts as done. For a job that runs a model, a step is a tool call in its transcript, and done is the process exiting with a valid result. An exit without a valid result is reported at once as a failure.

## Jobs it could cover

ghi-guide-agent questions, cold-read and sanity-check reviewers, merge-lane review runs, and scheduled jobs.

## Related GHIs

- [GHI 46](https://github.com/nedsnodes/nedsnodes/issues/46): ghi-guide-agent's design gives a question one overall timeout. As precedent it names a function that runs headless `claude -p` under three watchdogs, and it defers several watchdogs until the single timeout proves too blunt. Read that section of `docs/issues/46-ghi-guide-agent.system.design.md` before designing a new watcher.
- [GHI 2466](https://github.com/nedsnodes/nedsnodes/issues/2466), item 2.3: an agy cold-read-cell ends its read at agy's result line in stream-json output, and keeps the 30-minute limit when no result line comes. That stream of lines is a likely place to read finished steps from.
- [GHI 27](https://github.com/nedsnodes/nedsnodes/issues/27): it warns that killing a slow but working agent-session is worse than leaving a wedged one.
- [GHI 1983](https://github.com/nedsnodes/nedsnodes/issues/1983), closed: it set fixed time limits on every program that the Bash guard hooks under `.claude/guard-hooks/` start.

## What the design must decide

1. How each kind of job reports a step, and in what form; for a job that does not run a model, whether one shared `-common` module writes its started, step and done reports.
2. Where the caller reads those steps: a transcript, a stream of output lines, or a file.
3. The time with no step that stops a job, and the overall limit, for each kind of job, measured from the transcripts and output the log-store already keeps: the longest gap between finished steps and the longest whole run. The measure covers a model that thinks for a long time, or a single tool call that runs long, without a new step, which [GHI 27](https://github.com/nedsnodes/nedsnodes/issues/27) warns must not be killed.
4. When the no-step timer starts: at launch, so that a job that never reports it started is stopped too.
5. What a valid result is for each kind of job, and what the caller does when it stops a job: how it ends the process, and how its report tells a stop for no new step from a stop at the overall limit and from a failed exit.
6. Which callers change first.

## Next action

Write the design under "What the design must decide" and bring it to the user for approval. Build nothing until he approves it.
