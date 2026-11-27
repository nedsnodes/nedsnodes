---
issue: "[The handoff's queue recovery loses a user's unread reply when a peer message is delivered in a form that differs from its queued text](https://github.com/nedsnodes/nedsnodes/issues/4425)"
---

# The handoff's queue recovery loses a user's unread reply when a peer message is delivered in a form that differs from its queued text

## Reproduction

The program is `scripts/handoff-extract-conversation.py`, at main commit 4274d142d. Its function `claude_code_session_transcript_queued_user_messages_never_read_by_agent` tells a successor agent-session which messages the user queued that the agent never read. Given a transcript with these records, in order, it returns an empty list, so the user's message `human reply` is lost:

1. A queue operation `enqueue` with the content `human reply`.
2. A queue operation `enqueue` with the content `<cross-session-message from="s" hop-chain="abc" from-name="x" from-mode="prompting">`, a line `body`, and the closing tag.
3. A queue operation `dequeue`.
4. A user record whose text is `Another Claude session sent a message:`, then the same message without its `hop-chain` attribute. The real form also has closing advice after the message, which this reproduction does not need.
5. An assistant record.

The correct result is `["human reply"]`, because the dequeue delivered the peer message and the agent never read the reply.

## What goes wrong

A `dequeue` record names no content. The function looks in the user records before the next agent record for the exact text of a queued message, and when it finds none it removes the oldest queued message. Claude Code delivers a peer message in a different form from the one it queued, so the exact match fails and the oldest message, which can be the user's reply, is removed instead. The form differs in three ways: a first line `Another Claude session sent a message:`, added closing advice after the message, and, in Claude Code 2.1.330, no `hop-chain` attribute. Records 717 to 719 of `nedlern@ned-box:/home/nedlern/.claude/projects/-home-nedlern-agents-ned-box-helper/b63546cb-2d49-4f75-bcbb-baaebafcfbc2.jsonl` show this, and record 719 names version 2.1.330.

## How often it has happened

A read-only count on 2026-11-23 replayed each of the 510 ned-box transcripts under `~/.claude/projects` that hold both queue operations and a `hop-chain` attribute. It found 1,709 dequeues whose delivered record differs from a queued peer message only by the first line, the closing advice and `hop-chain`. In 1,062 of them the function removed an older entry instead of the peer message. In 3 transcripts the entry removed was a user's message that no later record shows:

- `nedlern@ned-box:/home/nedlern/.claude/projects/-home-nedlern-agents-cold-read-improvement/608ae0eb-4327-4622-8a42-e06b0f464244.jsonl`
- `nedlern@ned-box:/home/nedlern/.claude/projects/-home-nedlern-agents-merge-lane-2/8fe60f28-e6aa-413d-ac26-f71cb272e3bd.jsonl`
- `nedlern@ned-box:/home/nedlern/.claude/projects/-home-nedlern-agents-prime-intellect/fcbc9268-e319-43ce-8bdf-1c9eee1e2bbf.jsonl`

Open [PR 4415, handoff-extract-conversation: tie each queued message's delivery records together and keep a short question an unread reply answers](https://github.com/nedsnodes/nedsnodes/pull/4415) matches the first line, but compares the message with `hop-chain` still in it, so it does not fix this case.

## What to do

Build on PR 4415 once it merges. Make a dequeue identify a delivered `<cross-session-message>` by its `from` and `from-name` attributes and the text between its tags, ignoring `hop-chain`, the added first line and the closing advice after the closing tag, while a user's own reply still matches exactly. Add a test with the record sequence above, and with a real delivered form.
