---
issue: "[The idle sweep loses a promise on an open wait when it stops after marking the sentence checked and a usage limit ends the wait](https://github.com/nedsnodes/nedsnodes/issues/4406)"
---

# The idle sweep loses a promise on an open wait when it stops after marking the sentence checked and a usage limit ends the wait

## Reproduction

The program is `scripts/agent-seat-idle-sweep-headless-judge-wake-messages-send-and-user-alerts-write.py` at main commit 39e77c119. The reproduction ran it against scratch folders with the fake `claude` of its test file, `scripts/agent-seat-idle-sweep-headless-judge-wake-messages-send-and-user-alerts-write-test.py`. Line numbers below are that program's at that commit. The sweep's numbered rules and its waits are defined in [Tasks raise themselves when their prerequisites are met, and agent-seats left idle with something to do are woken](https://github.com/nedsnodes/nedsnodes/issues/940). "PR 927" below is fixture text, not a real pull request.

1. The sweep sends an idle agent-seat a rule 5 message, which opens a wait.
2. The agent-seat answers with the promise "I'll report when PR 927 merges." and goes idle.
3. At minute 7 the sweep judges that sentence unbacked and logs `sentence_checked` for it. To simulate a sweep stopped at that moment, the log is cut right after that line, so no promise message, `wait_step` or failure event follows it.
4. The agent-seat's transcript then ends in a usage limit.
5. At minute 9 the sweep applies rule 1 and logs `wait_ended` with the reason "a usage limit".
6. Runs at minutes 16, 32, 64 and 80 start no headless agent-session.

Result: no message the sweep sent and no user-alert names the promise, and the sentence stays logged as checked, so the sweep never judges it again. The promise is lost.

## Why it happens

The sweep marks a promise's sentences checked at line 1029, before it logs or sends anything that names the promise on an open wait, at lines 1047 to 1057. After a stop between the two, only the open wait can still lead to the promise being raised, and it holds no record of the promise. Rule 1 then ends that wait at line 963.

## Relation to other work

[The idle sweep loses a promise when it stops between marking the sentence checked and opening the wait](https://github.com/nedsnodes/nedsnodes/issues/4398) covers a promise that opens its wait. This issue covers a promise on a wait that is already open.

[Idle sweep settles and reports a failed promise message correctly](https://github.com/nedsnodes/nedsnodes/pull/4372) added a `promise_message_pending` record that holds the promise's text; mac-claude's review of its head c84a03041c5d reported that this loss remained there, and it closed unmerged on 2026-11-23. ned-box-helper's new pull request, which rebuilds how the sweep keeps a promise, waits on the user's ruling on the item "Rebuild how the idle sweep keeps a promise, so a stopped sweep does not lose it" of ned-box-helper's approval-walk ned-box-helper-open-items-approval-walk-2026-11-22.

## What to do

Keep a promise whose send has no logged result, meaning neither `promise_message` nor `promise_message_send_failed`, when its wait ends for any reason, not only a usage limit. After that wait ends, the first invocation that finds the agent-seat no longer at a usage limit opens a new wait for every such promise and sends them in one message.

Add a test that cuts the log after each line the promise step writes, ends the wait by each reason `end_wait` is given, and asserts that a later message names the promise. The owner is ned-box-helper.
