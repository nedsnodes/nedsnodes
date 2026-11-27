---
issue: "[The handoff dialog drops a short question after a notification, so a user's unread reply appears to answer an earlier question](https://github.com/nedsnodes/nedsnodes/issues/4421)"
---

# The handoff dialog drops a short question after a notification, so a user's unread reply appears to answer an earlier question

## Reproduction

The program is `scripts/handoff-extract-conversation.py`, at main commit 4274d142d. Its function `read_dialog_turns` builds the dialog a successor agent-session reads. Given a transcript with these records, in order, it keeps the long question and drops the short one, and the function `claude_code_session_transcript_queued_user_messages_never_read_by_agent` returns `["A"]`:

1. A user record `start`.
2. An assistant record holding a long question that ends `Approve item 1?`.
3. A user record `<task-notification>done</task-notification>`.
4. An assistant record `Tests passed. Approve the change?`.
5. A queue operation `enqueue` with the content `A`.

The successor sees the unread reply `A` directly after `Approve item 1?`, although the user typed it after `Tests passed. Approve the change?`. The successor can then take `A` as approval of item 1.

## What goes wrong

`read_dialog_turns` treats a short agent message right after a notification as an acknowledgement and drops it. It reads no queue operations, so it cannot see that an unread reply followed that message.

## How often it has happened

No real case is known. A read-only search on 2026-11-23 of the 9 ned-box transcripts with unread messages, by the reviewer of [PR 4415, handoff-extract-conversation: tie each queued message's delivery records together and keep a short question an unread reply answers](https://github.com/nedsnodes/nedsnodes/pull/4415), found 0 cases.

## What to do

Build on PR 4415 once it merges, because it changes how the tail keeps a short final question. Keep the last agent message before an unread user reply, even when it is short and comes right after a notification, so that the reply stays next to the message it answers. Add a test with the record sequence above that expects `Tests passed. Approve the change?` in the dialog.
