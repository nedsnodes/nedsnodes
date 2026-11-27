---
issue: "[The idle sweep's wait never settles when it stops between the rule 2 nudge and the promise message record](https://github.com/nedsnodes/nedsnodes/issues/4408)"
---

# The idle sweep's wait never settles when it stops between the rule 2 nudge and the promise message record

## Reproduction

The program is `scripts/agent-seat-idle-sweep-headless-judge-wake-messages-send-and-user-alerts-write.py` at main commit 39e77c119. The reproduction ran it against scratch folders with the fake `claude` of its test file, `scripts/agent-seat-idle-sweep-headless-judge-wake-messages-send-and-user-alerts-write-test.py`. Line numbers below are that program's at that commit. The sweep's numbered rules and its waits are defined in [Tasks raise themselves when their prerequisites are met, and agent-seats left idle with something to do are woken](https://github.com/nedsnodes/nedsnodes/issues/940). "PR 927" below is fixture text, not a real pull request.

1. An idle agent-seat's last turn says "I'll report when PR 927 merges." with no task backing it. At minute 0 the sweep logs `sentence_checked`, `checked` and a `wait_step` for the rule 2 nudge, which opens a wait.
2. To simulate a sweep stopped at that moment, the log is cut right after that `wait_step`, so the `promise_message` event that names the wait's sentences is missing.
3. By minute 1 the agent-seat has recorded a task whose prerequisite is that pull request's merge.
4. The sweep runs at minutes 7, 16 and 32.

Result: the wait does not end. The sweep logs an `escalate` step and a `tell_user` step and writes one user-alert, although the agent-seat recorded the task.

Control: the same recorded task, with the `promise_message` event logged, ends the wait with the reason "it recorded what a task waits on after the promise message", with no escalation and no user-alert.

No promise is lost, because the escalation quotes the nudge. The harm is an unneeded message to the agent-seat and an unneeded user-alert.

## Why it happens

The sweep logs the wait's opening at line 1039 and the `promise_message` event at line 1040, as two writes. Only `promise_message` gives the wait the sentences that a recorded task can settle, and line 972 tries settlement only when the wait holds such a message. A stop between the two writes leaves a wait that no task can settle. By reading, and not run: on an already open wait, the promise `wait_step` at line 1048 and the `promise_message` at line 1051 are separated the same way.

## Relation to other work

[Idle sweep settles and reports a failed promise message correctly](https://github.com/nedsnodes/nedsnodes/pull/4372), open at head c84a03041c5d, changes how a promise is recorded. mac-claude, reviewing that head, reproduced this same outcome there, so that pull request does not fix it.

## What to do

Log the wait's opening and the sentences it covers so that a stop cannot separate them, for example in one event, while logs already written with separate events still read correctly. Add a test that replays the rule 2 scenarios with the log cut after each event, records the task, and asserts that every wait left open settles with no user-alert. The owner is ned-box-helper.
