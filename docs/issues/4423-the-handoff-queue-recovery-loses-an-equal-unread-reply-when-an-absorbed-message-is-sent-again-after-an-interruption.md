---
issue: "[The handoff's queue recovery loses an equal unread reply when an absorbed message is sent again after an interruption](https://github.com/nedsnodes/nedsnodes/issues/4423)"
---

# The handoff's queue recovery loses an equal unread reply when an absorbed message is sent again after an interruption

## Reproduction

The program is `scripts/handoff-extract-conversation.py`, at main commit 4274d142d. Its function `claude_code_session_transcript_queued_user_messages_never_read_by_agent` tells a successor agent-session which messages the user queued that the agent never read. Given a transcript with these records, in order, it returns an empty list, so the second `A` is lost:

1. A queue operation `enqueue` with the content `A`.
2. A queue operation `enqueue` with the content `A`.
3. A queue operation `remove` with the content `A`.
4. An attachment record of type `queued_command` with the prompt `A`.
5. A user record `[Request interrupted by user]`.
6. A queue operation `dequeue`.
7. A user record `A`.
8. An assistant record.

The user typed `A` twice and the agent was shown it once, sent again after the interruption, so the correct result is `["A"]`.

## What goes wrong

An absorbed message is a queued message Claude Code delivers during a turn, as a `queued_command` attachment. Claude Code can then send the same message again as a user prompt after an interruption. `read_dialog_turns` in the same program already treats that second record as a resend. The function does not. On main the removal and the attachment each take away one copy, so this sequence loses the second `A` even without the interruption. Open PR 4415 makes the removal and its attachment one delivery, but the resend's dequeue still takes the second `A`, so that pull request does not fix this case.

## How often it has happened

No real case is known. A read-only search on 2026-11-23 of the 21,530 ned-box transcripts with queue records, by the reviewer of [PR 4415, handoff-extract-conversation: tie each queued message's delivery records together and keep a short question an unread reply answers](https://github.com/nedsnodes/nedsnodes/pull/4415), found equal copies pending at only 2 removals that delivered a message, and both were messages from another sender, not a user's reply.

## What to do

Build on PR 4415 once it merges. Apply the resend rule of `read_dialog_turns` to this function, so that a user record equal to an absorbed message, after an interruption and with no dialog between them, takes no second copy. Add a test with the record sequence above that expects `["A"]`. Because no real case is known, a smaller fix that names this case as not handled in the function's docstring is also acceptable.
