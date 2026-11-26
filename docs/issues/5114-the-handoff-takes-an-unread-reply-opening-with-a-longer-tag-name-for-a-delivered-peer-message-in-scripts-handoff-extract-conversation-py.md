---
issue: "[The handoff takes an unread reply opening with a longer tag name for a delivered peer message, in `scripts/handoff-extract-conversation.py`](https://github.com/nedsnodes/nedsnodes/issues/5114)"
---

# The handoff takes an unread reply opening with a longer tag name for a delivered peer message, in `scripts/handoff-extract-conversation.py`

When the handoff writes a conversation-tail, `scripts/handoff-extract-conversation.py` works out which of the user's queued replies were never shown to the agent-session, and lists them in the conversation-tail, so that the next agent-session is told about them. It leaves out a queued reply it believes was delivered. One test of "delivered" still matches a peer message's tag by its bare prefix, so a reply that opens with a longer tag name, such as `<agent-message-id>`, can be dropped from the unread list although the agent-session never read it. The reply is then missing from the conversation-tail, and nothing warns that it was dropped.

## What is wrong

On main at [7cfdcbeb](https://github.com/nedsnodes/nedsnodes/blob/7cfdcbeb8f89cedf0f270d8bcb492b9889768554/scripts/handoff-extract-conversation.py#L432-L437), `shown_text_is_queued_text(shown, queued)` counts a queued text as shown when it equals the shown text, or when the queued text opens with a peer-message tag and the shown text is that queued text inside the harness's delivered-peer-message wrapper, whose first line is `Another Claude session sent a message:`. The peer-message test is

```python
queued.startswith(PEER_MESSAGE_TAG_OPENINGS)
```

with `PEER_MESSAGE_TAG_OPENINGS = ("<cross-session-message", "<agent-message")` ([line 403](https://github.com/nedsnodes/nedsnodes/blob/7cfdcbeb8f89cedf0f270d8bcb492b9889768554/scripts/handoff-extract-conversation.py#L403)). Those openings carry no end to the tag name, so `<agent-message-id> ...` passes the test.

The failing case: the user queues a reply that opens `<agent-message-id>`, it stays unread, and a later prompt quotes that reply inside the delivered-peer-message wrapper. `shown_text_is_queued_text` then returns true for that later prompt, `first_pending_position_shown` finds the reply's position, and the reply is removed from the unread list. Codex found this in its review of PR [#4501](https://github.com/nedsnodes/nedsnodes/pull/4501) (finding bf64f497bd55, [inline comment](https://github.com/nedsnodes/nedsnodes/pull/4501#discussion_r4707856863), on head e6587e05e3f10a749c10a51a17bf6dc25eb46ff6) and reproduced the dropped reply, an unread list of `[]`, on both that pull request's base and its head.

PR #4501, open when this was written, fixes the same bare-prefix match where the script builds the unread list, by adding `text_opens_with_tag(text, tag_openings)`, which requires the character after the tag name to be `>` or whitespace ([its head, line 583](https://github.com/nedsnodes/nedsnodes/blob/e6587e05e3f10a749c10a51a17bf6dc25eb46ff6/scripts/handoff-extract-conversation.py#L583)). At that head it moves every other match on these tag openings onto the helper, and leaves `shown_text_is_queued_text` the one bare `startswith` on them ([its head, line 440](https://github.com/nedsnodes/nedsnodes/blob/e6587e05e3f10a749c10a51a17bf6dc25eb46ff6/scripts/handoff-extract-conversation.py#L440)).

## What to do

1. After PR #4501 merges, change the test in `shown_text_is_queued_text` to `text_opens_with_tag(queued, PEER_MESSAGE_TAG_OPENINGS)`. If PR #4501 is closed instead, add a helper like its `text_opens_with_tag` in the same change, and move every bare match on the tag openings onto it, as that pull request does.
2. Add a case to `scripts/handoff-extract-conversation-test.py` that queues an unread reply opening `<agent-message-id>`, follows it with a prompt that quotes it inside the delivered-peer-message wrapper, and checks that the reply is still in the unread list. Run it with `python3 scripts/handoff-extract-conversation-test.py`, and check that the case fails before the change and passes after it.
3. Check that `grep -nE "startswith\((PEER_MESSAGE_TAG_OPENINGS|QUEUED_TEXT_OF_ANOTHER_SENDER_TAG_OPENINGS)" scripts/handoff-extract-conversation.py` prints nothing, so no match on a tag name is left without its end.
