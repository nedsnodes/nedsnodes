---
issue: "[Write one design for background and in-review mutation testing](https://github.com/nedsnodes/nedsnodes/issues/4359)"
---

# Write one design for background and in-review mutation testing

Owner: agent-seat fleet-restart-at-login, which has been changing the mutation-testing programs.

## What this GHI asks for

Write one design document for mutation testing, and bring it to the user for approval. Mutation testing makes a small change to a line of code, a mutant, and runs the tests; a mutant the tests do not catch is a surviving mutant, which shows a behavior no test checks.

Build nothing until the user approves the design. Until then, reviewers keep mutating by hand, and line 20 of `nedlern@ned-box:/home/nedlern/agents/merge-lane-2/walk-ledgers/mac-claude-reviewer-brief-standing-text.md`, a file outside the repository, stays as it is.

## Why now

Today a nightly job, `scripts/scheduled-full-mutation-pass-of-merged-pull-requests-and-survivor-tasks-open.py`, mutates lines changed by newly merged pull requests and opens a task for each line with a surviving mutant. Mutation testing has programs and docstrings but no design. Nothing measures line coverage, maps tests to modules, or shares CPU between background passes and passes run during a review.

One part of this work is on the critical path. Measured on ned-box at 2026-11-23 05:07Z:

- The load average was 24 on 16 CPUs.
- 42 command lines matched the mutation-testing program or its temporary worktrees. That count includes child processes, so it is not 42 mutants.
- Suites in three head test runs waited up to 657 seconds to be admitted.
- 49 approved pull requests were waiting in the merge queue.

These measurements show that mutation runs compete with the merge lane for CPU. They do not show how much of the wait mutation runs cause.

The user said on 2026-11-23: "If this is slowing us down, if this is the critical path for progress, we should attack it now."

## What the design covers

The design's first section is point 1 below, and it is the first thing proposed for building once the user approves the design.

1. When a review starts, running background mutants finish, and no background pass starts again until no review is active. All mutation slots, a set number of mutants running at once, are split evenly among active reviews. For example, with 4 active reviews and 12 slots, each review gets 3.
2. Background passes run when CPUs are free, new and changed lines first.
3. An in-review pass starts when the review is commissioned. Once the rest of the review is done, no new mutant starts; running mutants finish, and a survivor they find goes to the author without holding the merge.
4. During a review, a survivor goes to the pull request's author. After the merge, it goes to the agent assigned to that file's system, a `claude -p` agent woken when needed. That agent adds a test that catches the mutant or records why no test can.
5. Line coverage: which tests run each line.
6. How tests map to files and modules, and module tests versus system tests.
7. Which agent is assigned to each system, since no such agents exist yet.

## The user's rulings this design follows

All are from 2026-11-23, in `nedlern@ned-box:/home/nedlern/agents/merge-lane-2/docs/walk/merge-lane-2-idle-alerts-and-seat-mailboxes-ghi-approval-walk-2026-11-20-minutes.md`, item 27 of 27:

- "That's fine as long as we're not critical path by mutation tests."
- "the mutations mostly should run in when the system CPUs are not have plenty of space in them"
- "maybe we don't do any background mutation tests when there are PR coming in, so we have all the mutation test slots available for the PRs. And then if one PR is only in at a time, we can use all the slots for that PR. And if there's two, we have to divide in two"
- "if there's zero, then we can just go back to the background PR tests" (zero active reviews; "background PR tests" here means the background passes)
- "Any review pass, I don't say, wouldn't say pauses. I would say wraps, lets the background processes wrap up and complete, and review, and will not restart them until there's no active review passes."
- "during the PR process, there's a known writer, and then during the maintenance process, there isn't. But like I said, the solution, I think, is to have a -p agent assigned to each system that can be woken up as necessary."

## What to reuse

- GHI [2259](https://github.com/nedsnodes/nedsnodes/issues/2259) records line coverage per test case; use it for points 5 and 6.
- GHI [1374](https://github.com/nedsnodes/nedsnodes/issues/1374) built the start of test suites by free CPU and memory. Use its thresholds for "CPUs are free" in point 2, and consider its lock-based slots for counting active reviews in point 1.
- GHI [2135](https://github.com/nedsnodes/nedsnodes/issues/2135) built the pre-push mutation run and the daily full mutation pass.
- Surviving mutants already reach agent-seats as tasks named "Surviving mutants in <file>:<line>". Point 4 says whether a `claude -p` agent reads those tasks or needs another route, and no mutant may reach two recipients.

## Cases the design settles

- What marks a review as active and as finished, and what records it so that a crashed review does not block background passes forever.
- How many mutation slots there are and where that number is set; how a remainder is split, as with 5 reviews and 12 slots; what happens with more reviews than slots; and how slots move when a review joins or leaves while mutants run.
- Which lines an in-review pass mutates, and when a background pass ends or starts again.
- Whether a survivor found while the review is still running can block the merge. The user's ruling covers only survivors found after the rest of the review is done, which do not hold it.
- Who receives a survivor from a mutant still running when the pull request merges.
- How a `claude -p` agent branches, runs tests, opens a pull request and reports a failure.
- Whether the in-review pass replaces the hand procedure at line 20 or runs beside it.

Following the code-prompt-code rule in `CLAUDE.md`, the design puts these in code: the record of active reviews, the slot split, the stop event, the choice of a survivor's recipient, the table from file path to system and agent, the waking of agents, and the check that a `# pragma: no mutate` gives a reason. A model chooses only what needs judgment, such as whether a mutant is equivalent to the original code.

## Next action

fleet-restart-at-login writes the design, starting with point 1, and brings it to the user for approval.
