---
issue: "[The idle sweep loses a promise when it stops between marking the sentence checked and opening the wait](https://github.com/nedsnodes/nedsnodes/issues/4398)"
---

# The idle sweep loses a promise when it stops between marking the sentence checked and opening the wait

## Reproduction

This was run on main at commit `20930a4a08b7`, through the real program, `scripts/agent-seat-idle-sweep-headless-judge-wake-messages-send-and-user-alerts-write.py`, using the `Machine` class of its test file, `scripts/agent-seat-idle-sweep-headless-judge-wake-messages-send-and-user-alerts-write-test.py`.

1. Give an idle agent-seat a transcript whose last turn says "I'll report when PR 927 merges.", with no task recording it, and run the sweep at minute 0. The run logs `account_seen`, `sentence_checked`, `checked`, `wait_step`, `promise_message` and `message_sent`, in that order.
2. Cut the sweep's log after `checked`. The log then holds what a sweep stopped at that point would have written. The stop was simulated this way; no process was killed.
3. Run the sweep at minutes 3, 16, 32, 48 and 64, with the test file's fake `claude` program scripted to answer a send.

Every run exits 0. None starts a headless session, and the log gains no `wait_step` and no `message_sent`. No user-alert is written. The agent-seat is never told about its promise, and nobody is told that it was not.

## What is wrong

Rule 2 of the idle sweep, which GHI [Tasks raise themselves when their prerequisites are met, and agent-seats left idle with something to do are woken](https://github.com/nedsnodes/nedsnodes/issues/940) defines, finds a promise an agent-seat made and did not record, and sends it a message. When no wait is open, that message opens one, and the wait is what later brings the escalation and the user-alert.

The sweep writes two log events that say the sentence is dealt with, and only then opens the wait. At commit `20930a4a08b7`, `self.sentences_checked` is at line 1029, `self.checked` at line 1030 and `self.start_wait` at line 1039. A later invocation of the sweep skips a sentence the log calls checked. If the sweep stops between lines 1030 and 1039, the sentence is skipped and no wait exists to escalate, so the promise is lost without any report.

## Why it matters

The idle sweep exists to catch a promise an agent-seat did not record. This failure drops such a promise and reports nothing, so the work it named can go undone without anyone seeing it. The stop needs a kill, a crash or a reboot in a short window.

This failure has not been seen. A scan of the sweep's log, `nedlern@ned-box:/home/nedlern/nedsnodes-logs/agent-seat-idle-sweep/agent-seat-idle-sweep-messages-sent-and-verdicts.jsonl`, 28,459 events from 2026-11-09 to 2026-11-23, found no `checked` event that followed a `sentence_checked` for an unbacked or unjudged sentence with no wait, send or failure after it in the same minute.

## Next action

Make the step that marks the sentences checked and the step that keeps the promise pending one write: one log event holds the promise's text and each `record_uuid` and sentence it covers, and the sweep counts that event as checking those sentences. A later invocation that finds this event with no wait and no recorded send opens the wait and sends the message. Once a send has an outcome or the wait has ended, the event asks for nothing more.

Add a test that takes its stop points from the log: run the sweep once, then for each line of the log, rebuild the case, cut the log after that line, and check that the promise still reaches the agent-seat, or the escalation and the user-alert.

The agent-seat ned-box-helper owns this work. Its pull request [Idle sweep settles and reports a failed promise message correctly](https://github.com/nedsnodes/nedsnodes/pull/4372) closed unmerged on 2026-11-23; it covered only a promise on a wait that is already open. ned-box-helper's new pull request, which rebuilds how the sweep keeps a promise and covers this case too, waits on the user's ruling on the item "Rebuild how the idle sweep keeps a promise, so a stopped sweep does not lose it" of ned-box-helper's approval-walk ned-box-helper-open-items-approval-walk-2026-11-22.
