---
issue: "[The idle sweep records running work as asked about before its nudge is sent, so after a failed send that work is never asked about again](https://github.com/nedsnodes/nedsnodes/issues/4089)"
---

# The idle sweep records running work as asked about before its nudge is sent, so after a failed send that work is never asked about again

## Reproduction

Make a worktree at commit 29939797d, such as with `git worktree add --detach /tmp/sweep-29939797d 29939797d`, save the script below as `repro3.sh` in a directory of its own, and run it from that worktree's root, passing the worktree's absolute path:

```
bash /path/to/repro3.sh /tmp/sweep-29939797d
```

The script's usage line says "checkout at origin/main" because origin/main was at commit 29939797d when it was written; at any other commit the line numbers it cuts at may be wrong. It writes `repro3-generated.py` beside itself. `repro3.sh` builds a script from the harness of the idle sweep's own test, `scripts/agent-seat-idle-sweep-headless-judge-wake-messages-send-and-user-alerts-write-test.py`, whose line numbers it takes as they are at commit 29939797d, and runs it:

```bash
#!/bin/bash
# Usage: repro3.sh <checkout at origin/main>. Builds a script from the idle sweep test's harness and runs it.
C=$1; S=$(dirname "$0"); T=$C/scripts/agent-seat-idle-sweep-headless-judge-wake-messages-send-and-user-alerts-write-test.py; R=$S/repro3-generated.py
{ sed -n 1,252p $T | sed "s|^PROGRAM = Path(__file__).with_name(|PROGRAM = Path('$C/scripts').joinpath(|"; sed -n 479,493p $T; sed -n 567,572p $T; cat <<'EOF'
for label, msg in (("message names bk1", "Your background command \"A\" (bk1) started 30 minutes ago. Is it taking longer than expected?"), ("control, message names nothing", "m")):
    machine = Machine()
    machine.seat("alpha", [user("go"), *background_bash_launch("bk1", "python3 scripts/a.py", at(-30), "tb1", description="A"), assistant("Waiting."), turn_end()])
    machine.script(judged(True, msg), {"sends": [send_to("alpha", is_error=True)], "answer": {"sent": False, "reason": "r"}})
    machine.run(0)
    a1 = [e.get("running_work_asked_about") for e in machine.events("judge_answer")]
    answered_with_a_tool_call_and_idle_again(machine, 1)
    machine.script(judged(True, msg), sent_ok())
    machine.run(8)
    print(f"{label}: sweep 1 send failed, asked_about={a1}, headless_failed={len(machine.events('headless_failed'))}, user_alert={len(machine.events('user_alert'))}; after sweep 2: judge_answers={len(machine.events('judge_answer'))}, message_sent={len(machine.events('message_sent'))}")
EOF
} > $R; python3 -B $R
```

It printed, on 2026-11-21:

```
message names bk1: sweep 1 send failed, asked_about=[['bk1']], headless_failed=1, user_alert=1; after sweep 2: judge_answers=1, message_sent=0
control, message names nothing: sweep 1 send failed, asked_about=[[]], headless_failed=1, user_alert=1; after sweep 2: judge_answers=2, message_sent=1
```

An agent-seat sits idle while its background command `bk1` runs. On the first sweep the judge writes a nudge that names `bk1`, and the send fails. The `judge_answer` event already records `bk1` in `running_work_asked_about`. On the second sweep, with the agent-seat idle again, the judge is not asked again and no nudge is sent. The control, where the failed nudge named no running work, is judged again and its nudge is sent.

## What is wrong

Line numbers are those of `scripts/agent-seat-idle-sweep-headless-judge-wake-messages-send-and-user-alerts-write.py` on main at commit 29939797d, which opens at those lines as [this file at that commit](https://github.com/nedsnodes/nedsnodes/blob/29939797d/scripts/agent-seat-idle-sweep-headless-judge-wake-messages-send-and-user-alerts-write.py).

In `judge_idle_seat`, lines 1010 to 1042, the rule 5 `judge_answer` event, with the running work the message names in `running_work_asked_about`, is recorded at line 1031, and the message is sent at line 1042. `send`, lines 729 to 741, reports a failed send as `headless_failed` and returns, but nothing takes back the record. On every later sweep, `running_work_asked_about` (lines 403 to 405) counts that work as asked about, and lines 1018 to 1022 return without judging when everything still running has been asked about. So the nudge the agent-seat never received is never sent again; the user gets one user-alert for the failed send, and the agent-seat stays idle until something else wakes it.

The design, GHI [Tasks raise themselves when their prerequisites are met, and agent-seats left idle with something to do are woken](https://github.com/nedsnodes/nedsnodes/issues/940), `docs/issues/940-tasks-raise-themselves-when-their-due-time-passes.md`, says in § Decided, point 5, that the sweep asks once about each piece of running work; says in § The idle sweep that, for rule 5, "code logs the nudge and then sends the message", without saying what a failed send does to that log; and lists in § Deferred-decisions "Whether code records a raised sentence before or after the send is confirmed; to be settled when the job is built." That deferred line is about rule 2's raised sentences; rule 5's running work has the same question, which the design does not list. This GHI reports what the code does today for rule 5: it records before the send, so a failed send uses up the one ask.

## What to do next

The owner, ned-box-helper, fixes it. By `git blame` on main, the record-before-send order at lines 1031 and 1032 came from pull request [2732](https://github.com/nedsnodes/nedsnodes/pull/2732), the idle sweep's slice 2, and the `running_work_asked_about` field it now carries, lines 1033 to 1035, from pull request [3924](https://github.com/nedsnodes/nedsnodes/pull/3924). The owner fixes the root cause: running work counts as asked about only when a message naming it was sent. How is the owner's choice, such as reading `running_work_asked_about` from the `message_sent` events rather than from `judge_answer`. The owner also decides what the sweep does after a failed send once this is fixed: when it next judges, given `JUDGE_ASK_AGAIN_SECONDS`, and whether each further failed send raises another user-alert. The owner checks whether rule 2 records its sentences before its send in the same way, and if it does, gives rule 2 the same fix. The fix carries a test with the failed send above, and one for rule 2 when rule 2 shares the order. The owner then writes the decision into GHI 940's GHI-MD, in the body, and removes the deferred line, as its § Deferred-decisions asks. The defect was found by the Codex review cell while reviewing pull request [4001](https://github.com/nedsnodes/nedsnodes/pull/4001), which does not change the idle sweep.

## Outcome

Fixed by three pull requests. Pull request [Idle sweep: running work counts as asked about only once its message was sent](https://github.com/nedsnodes/nedsnodes/pull/4075) made rule 5 count running work as asked about only once a message naming it was sent. Pull request [Idle sweep: a promise message or running work counts as asked only once the message was sent and found](https://github.com/nedsnodes/nedsnodes/pull/4168) gave rule 2 the same order for a promise message sent on an open wait, logging its `promise` wait step and `promise_message` event only after the send succeeds, and made rule 5 also leave out work named by a message the delivery check did not find in the agent-seat's transcript. Pull request [Idle sweep: a promise message on an open wait keeps the wait open when its send fails](https://github.com/nedsnodes/nedsnodes/pull/4208) logs the `promise` wait step before the send again, so that when the send fails the wait stays open and goes on to its escalation and user-alert, rather than being ended with the promise unreported; the `promise_message` event is still logged only once sent, so a task call cannot settle a promise the agent-seat never received.

One point pull request 4168 left to the owner, ned-box-helper, is left out: a sender that rewrites the message and drops a command id still records that id as asked about, because the ids come from the judge's message, not from the text the sender sent. No case has been seen. In `nedlern@ned-box:/home/nedlern/nedsnodes-logs/agent-seat-idle-sweep/agent-seat-idle-sweep-messages-sent-and-verdicts.jsonl`, searched on 2026-11-22, there is no `sent_text_differs_from_code_text` event, and each of the 29 `judge_answer` events with a non-empty `running_work_asked_about` whose message was sent has every id it lists in the text of its `message_sent` event; the 30th, MD-skills at 2026-11-22T00:54:11Z, is a failed send, the case this GHI reports. So under CLAUDE.md's rule on guards, nothing is added.
