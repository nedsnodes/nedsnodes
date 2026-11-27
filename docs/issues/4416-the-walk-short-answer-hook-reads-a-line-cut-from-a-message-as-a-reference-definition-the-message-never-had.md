---
issue: "[The walk short-answer hook reads a line cut from a message as a reference definition the message never had](https://github.com/nedsnodes/nedsnodes/issues/4416)"
---

# The walk short-answer hook reads a line cut from a message as a reference definition the message never had

## Reproduction

Both cases ran on 2026-11-23 against main at 32591bbe1, through the hook's own test harness, `Case` in `nn-systems/skills/walk-me-through/tests/walk-me-through-user-short-answer-to-approval-walk-item-expanded-into-instructions-user-prompt-submit-hook-test.py`, with the user answering `a` to item 4 and a stand-in model that answers `changed`. Each case has a control without the line that reads as a definition, `[edits 4]: /docs` in case 1 and `[age]: /docs` in case 2. The scratch runs wrote nothing to the log-store.

Case 1, a correct answer is wrongly sent to the model and can be refused. The walk-document's item holds the line `[Proposed edits][edits 4]:`, and the agent's message shows that line unchanged, below a title followed by one extra line:

```markdown
**Item 4 of 9: a filter**
[edits 4]: /docs

[Proposed edits][edits 4]:
```

The hook made 1 model call and refused the answer. The control, without the `[edits 4]: /docs` line, counted the answer with 0 model calls. A real model might answer that the line is unchanged, so this failure costs at least one model call and can cost a wrong refusal.

Case 2, an answer is wrongly counted for text the user saw differently. The walk-document's item holds `#new Keep older rows.`, and the agent's message shows it with brackets added, below a two-line heading:

```markdown
Item 4 of 9: a filter
[age]: /docs
=====

#new Keep [older rows][age].
```

The user sees the brackets, because in the whole message `[age]: /docs` is part of the heading and defines nothing. The hook counted the answer with 0 model calls. The control, without the `[age]: /docs` line, made 1 model call and refused the answer. This is the more serious direction: the check that the user was shown the decision passes when the text he saw differs from the text he is approving.

## What the hook does and what goes wrong

When the user answers an approval-walk item, the hook compares the item's decision-bearing lines in the walk-document with the copy of them in the agent's last message. `message_copy_of_item` cuts that copy out of the message. The hook then parses the copy on its own, with the whole message's Markdown environment, in `rendered_blocks` (line 1164), `lead_ins` (line 1122) and `shown_units` (line 1200), called at lines 1570 and 1573 of `nn-systems/skills/walk-me-through/walk-me-through-user-short-answer-to-approval-walk-item-expanded-into-instructions-user-prompt-submit-hook.py`.

The cut can change what a line is. A line such as `[age]: /docs` is heading or paragraph text in the whole message, but when the cut makes it the copy's first line, markdown-it reads it as a reference definition. The definition then resolves a link in the copy that the whole message showed as literal brackets.

Root cause: the hook decides what the user saw by parsing a fragment, and a fragment's Markdown structure is not the structure the user saw rendered.

Copying the environment before each parse does not fix this, because the copy's own parse still reads the definition. [Walk short-answer hook: a line parsed alone adds no reference definition, and the lead-in caveats say what happens](https://github.com/nedsnodes/nedsnodes/pull/4414) fixes the separate case in `shown_words`, where a parsed fragment wrote a definition into the shared environment.

## What to do next

The owner is the agent-seat agent-instructions-editor, which wrote the hook's recent changes in this area.

1. Make `rendered_blocks`, `lead_ins` and `shown_units` read the copy from the whole message's parse, for example by selecting the tokens of the item's line range, so that a line that is not a definition in the message cannot become one in the copy. Check the hook's other parses of cut text too: `parser.parse(copy, {})` at line 1566, the `shown_words` calls on slices at lines 1183 and 1199, and the parses of `body` at line 1569.
2. Add both cases above to the hook's test file, each with its control. With the stand-in model answering `changed`, case 1 and its control must both count the answer with 0 model calls, and case 2 and its control must both make 1 model call and refuse the answer.
