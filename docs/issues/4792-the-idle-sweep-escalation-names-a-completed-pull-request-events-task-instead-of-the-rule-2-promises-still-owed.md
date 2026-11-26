---
issue: "[The idle sweep's escalation names a completed pull-request events task instead of the rule 2 promises still owed](https://github.com/nedsnodes/nedsnodes/issues/4792)"
---

# The idle sweep's escalation names a completed pull-request events task instead of the rule 2 promises still owed

## Reproduction

Codex ran this while reviewing [Idle sweep: one code-written wake per pull-request events task; its wait ends when the task does](https://github.com/nedsnodes/nedsnodes/pull/4768) at head `1e15f68761d0`. merge-lane-1 posted it as [Codex finding fccb970c803f](https://github.com/nedsnodes/nedsnodes/pull/4768#discussion_r4697730610); the id is the review program's, and Codex's own report, `nedlern@ned-box:/home/nedlern/nedsnodes-logs/seats/merge-lane-2/merge-helpers/cx/pr4768-12dba356/codex-code-review-report.md`, lists the finding under the title "Escalate the outstanding promises, not the completed events task". Codex ran the program `scripts/agent-seat-idle-sweep-headless-judge-wake-messages-send-and-user-alerts-write.py` in memory, from a script piped to `python3 -B -` that was not saved:

1. The sweep wakes merge-lane-2 by code for its pull-request events task, which opens a wait whose quote is that wake's text.
2. merge-lane-2 makes a promise that no task records. The sweep sends the rule 2 message naming it, and the send succeeds, so the sentence goes on the open wait.
3. The events task is then completed, and the promise is still not recorded in any task.
4. 15 minutes after the wake, the sweep escalates.

Result: the escalation quotes only the events task's wake text, so it tells merge-lane-2 to work a task that is already completed. It does not name the promise still owed. The filer did not run the reproduction again (unverified).

## What is wrong

The sweep's numbered rules and its waits are defined in GHI [Tasks raise themselves when their prerequisites are met, and agent-seats left idle with something to do are woken](https://github.com/nedsnodes/nedsnodes/issues/940); rule 2 is the one that finds a promise an agent-seat made and did not record in a task, and sends it a message about it.

`due_step` builds the escalation, and 15 minutes later the user-alert, from the wait's opening quote, the messages whose send failed, and the sentences that no message event holds. A rule 2 message that was sent successfully is in none of these, so once the wait's opening reason is gone, the escalation and the user-alert name a reason that no longer holds and leave out the one that does. On main, a completed events task leaves the wait open with the same quote (judged from reading main at `f054d6977731`, unverified). PR 4768 makes the wait drop the events task when the task closes and the wait holds a promise, but leaves the quote as it was.

GHI 940, in its decision 13, rules that "the escalation quotes the nudge"; that quote stays, but the escalation must also say that the nudge's task is done and name what is still owed.

## Next action

The agent-seat that owns the idle sweep, overall-cleanup, makes the escalation and the user-alert of any wait whose opening reason is gone also name each rule 2 sentence on the wait that is still not backed by a task, while still quoting the nudge. It adds a test case that completes the events task after a successful rule 2 message and checks that the escalation names the promise.
