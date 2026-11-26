---
issue: "[The idle sweep gives a new pull-request events task no wake while an alerted deferred-handoff wait stays open](https://github.com/nedsnodes/nedsnodes/issues/4790)"
---

# The idle sweep gives a new pull-request events task no wake while an alerted deferred-handoff wait stays open

## Reproduction

Codex ran this while reviewing [Idle sweep: one code-written wake per pull-request events task; its wait ends when the task does](https://github.com/nedsnodes/nedsnodes/pull/4768) at head `12dba356f9e8`. merge-lane-1 posted it as [Codex finding cfc0b94466a8](https://github.com/nedsnodes/nedsnodes/pull/4768#discussion_r4697418416); the id is the review program's, and Codex's own report, `nedlern@ned-box:/home/nedlern/nedsnodes-logs/seats/merge-lane-2/merge-helpers/cx/pr4768-658492a6/codex-code-review-report.md`, lists the finding under the title "Let a new events task pass an alerted handoff wait". Codex ran the program `scripts/agent-seat-idle-sweep-headless-judge-wake-messages-send-and-user-alerts-write.py` in memory, from a script piped to `PYTHONDONTWRITEBYTECODE=1 python3 -` that was not saved, on both main and that head:

1. merge-lane-2 has a deferred-handoff marker, so the sweep picks rule 3 for it and sends the rule 3 nudge, which opens a wait.
2. merge-lane-2 stays idle, so the wait escalates and then writes a user-alert.
3. A new pull-request events task then opens on merge-lane-2's task list, while the marker is still there.

Result, on both revisions: the sweep makes zero sends. The new events task gets no wake. The filer did not run the reproduction again (unverified).

## What is wrong

The sweep's numbered rules and its waits are defined in GHI [Tasks raise themselves when their prerequisites are met, and agent-seats left idle with something to do are woken](https://github.com/nedsnodes/nedsnodes/issues/940). Under rule 5 the sweep wakes merge-lane-2 by code once for each open pull-request events task. A wait that has already told the user has no step left, but it stays open until the agent-seat spends tokens, and while it is open the sweep starts no new wait for that agent-seat.

PR 4768 adds a release for this case in `sweep_seat()`: an alerted wait no longer holds back a new events task's wake. The release applies only when the current sweep's verdict picks rule 5 (`rule == 5`, in the `if` that follows the comment "The user already has that wait's alert"). While a deferred-handoff marker is on the agent-seat, the verdict picks rule 3 instead, whichever rule opened the alerted wait, so the release never applies and the events task gets no wake. merge-lane-2 then never hears about the pull request events the task is for, and no one is told.

## Next action

The agent-seat that owns the idle sweep, overall-cleanup, makes the release apply whatever rule the current verdict picks, so that an alerted wait never holds back a new events task's wake, and adds a test case that opens an alerted wait under a deferred-handoff marker, adds a new events task, and checks that the sweep sends the events task's wake.
