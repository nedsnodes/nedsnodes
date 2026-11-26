---
issue: "[handoff-extract-conversation: match a queued slash command typed without arguments to the record that delivers it](https://github.com/nedsnodes/nedsnodes/issues/4924)"
---

# handoff-extract-conversation: match a queued slash command typed without arguments to the record that delivers it

`scripts/handoff-extract-conversation.py` lists, in the conversation-tail a successor starts from, the user's queued messages that the agent never read. It works this out from the queue records of the agent-session's transcript: each `enqueue` adds a message, and each `dequeue` removes the message that the next user record shows.

## What is wrong

`typed_slash_command` turns a slash command's record back into the text the user typed, so that the dequeue can match it to the queued text. It returns nothing for a command typed without arguments, such as `/explain`, because it requires a non-empty `<command-args>` element. So no delivery record is matched to such a queued command, and the dequeue falls back to the oldest queued message from the user. When the user has also queued a reply that the agent has not read, that reply can be the one removed, and the conversation-tail then leaves it out as read.

PR [handoff-extract-conversation: a dequeue whose delivery shows no queued text takes the oldest message from that delivery's sender](https://github.com/nedsnodes/nedsnodes/pull/4861), not yet merged, narrows this fallback to the delivery's sender, and its review named this case as Codex finding 2a78c41b7ab1. The pull request leaves the matching alone, so the case remains.

## What to do

Make `typed_slash_command`, or the code that matches a dequeue's delivery to a queued text, match a human-typed command record without arguments to a queued text that is exactly the command's name, such as `/explain`, both where a `dequeue` takes it and where a delivered record removes a queued copy without one. `typed_slash_command` also decides which user turns `dialog_turn_from_record` keeps, so a change there must keep the dialog's turns as they are, or say why they change. Add a test in `scripts/handoff-extract-conversation-test.py` in which the user queues a reply and then `/explain`, and only the command is delivered: the reply must stay unread.
