---
issue: "[The handoff's queue recovery loses an unread reply when a dequeue takes the attachment of an absorbed message](https://github.com/nedsnodes/nedsnodes/issues/4435)"
---

# The handoff's queue recovery loses an unread reply when a dequeue takes the attachment of an absorbed message

## Reproduction

The program is `scripts/handoff-extract-conversation.py`. Its function `claude_code_session_transcript_queued_user_messages_never_read_by_agent` tells a successor agent-session which messages the user queued that the agent never read. Given a transcript with these records, in order, it returns an empty list:

1. A queue operation `enqueue` with the content `A`.
2. A queue operation `enqueue` with the content `A`.
3. A queue operation `enqueue` with the content `A`.
4. A queue operation `dequeue`.
5. A queue operation `remove` with the content `A`, whose reason is `absorbed_mid_turn`.
6. An attachment record of type `queued_command` with the prompt `A`.
7. A user record `A`.

The user queued `A` three times and the agent was shown it twice, so the correct result is `["A"]`, and the third `A` is lost.

The reviewer of [PR 4415, handoff-extract-conversation: tie each queued message's delivery records together and keep a short question an unread reply answers](https://github.com/nedsnodes/nedsnodes/pull/4415) ran this sequence and three others on 2026-11-23. The table gives the list the function returned at PR 4415's head 30061c6296d6, at its merge base d77ed343a01f, and at main 452db54ec3a9. The program file is the same at the merge base and at main.

| Records | PR 4415 head | Merge base | Main |
|---|---|---|---|
| `enqueue A` three times, dequeue, remove, attachment, user `A` | `[]` | `[]` | `[]` |
| The same, then the next agent record | `[]` | `[]` | `[]` |
| `enqueue A` three times, remove, dequeue, attachment, user `A` | `["A"]` | `[]` | `[]` |
| The same, then the next agent record | `["A"]` | `[]` | `[]` |

PR 4415 at 30061c6296d6 does not cause this loss, because main loses the same `A`. That head fixes the order with the removal first, and leaves the order with the dequeue first as it is on main.

## What goes wrong

A dequeued message reaches the agent as a user record. An absorbed message, which Claude Code delivers during a turn, reaches the agent as a `queued_command` attachment. At PR 4415's head, a dequeue can claim either kind of record, because the attachment's type is a subclass of `list` and the dequeue's claim accepts any `list`. In the first row, the dequeue claims the attachment, the absorbed removal then finds no attachment to claim, and the user record, which nothing has claimed, removes the third `A`.

## How often it has happened

No real case is known. In the same review, a read-only replay of the ned-box transcripts with queue records found that 0 of 46,565 dequeues claimed an attachment. A dropped reply is still a lost user message, because the successor agent-session is never told about it.

## What to do

The agent-seat helper2 owns this work, because it wrote PR 4415, which this fix builds on. After PR 4415 merges, change the function so that a dequeue can claim only a user record and an absorbed removal can claim only a `queued_command` attachment. Add one test for each of the table's four rows, each expecting `["A"]`.
