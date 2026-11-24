---
issue: "[The walk-me-through short-answer hook does not end an item's shown text at the next item when the item's heading has words between its number and its title](https://github.com/nedsnodes/nedsnodes/issues/4534)"
---

# The walk-me-through short-answer hook does not end an item's shown text at the next item when the item's heading has words between its number and its title

## Reproduction

On main at commit 0f5f600df, in `nn-systems/skills/walk-me-through/`, this script loads the short-answer hook, `walk-me-through-user-short-answer-to-approval-walk-item-expanded-into-instructions-user-prompt-submit-hook.py`, writes a transcript holding one assistant message that shows item 4 and then item 5, and asks the hook's `last_showing_message` for the text it shows for item 4:

```python
import importlib.util, json, sys
path = "walk-me-through-user-short-answer-to-approval-walk-item-expanded-into-instructions-user-prompt-submit-hook.py"
spec = importlib.util.spec_from_file_location("h", path)
h = importlib.util.module_from_spec(spec); sys.modules["h"] = h; spec.loader.exec_module(h)
parser = h.load_walk_finder().markdown_parser()
for title in ["Item 4 of 9: a decision", "Item 4 of 9 (revised): Filter"]:
    text = f"## {title}\n\nItem four text.\n\n## Item 5 of 9: next\n\nItem five text.\n"
    with open("t.jsonl", "w") as transcript:
        transcript.write(json.dumps({"type": "assistant", "timestamp": "2026-11-24T00:00:00Z",
                                     "message": {"content": [{"type": "text", "text": text}]}}) + "\n")
    heading = h.shown_words(f"## {title}", parser, {})
    print(repr(title), repr(h.last_showing_message("t.jsonl", heading, parser, {})[1]))
```

It prints:

```
'Item 4 of 9: a decision' '\nItem four text.\n'
'Item 4 of 9 (revised): Filter' '\nItem four text.\n\n## Item 5 of 9: next\n\nItem five text.\n'
```

With the first heading, the text shown for item 4 ends where item 5 begins. With the second, item 5's heading and text are taken as part of item 4's shown text.

## What is wrong

`last_showing_message` ends an item's shown text at the first later line for which `opens_another_item(words, heading)` returns True. `opens_another_item` returns False whenever `item_numbers_an_opening_names` returns None for either of its two inputs: `heading`, the waiting item's own heading, or `words`, the later line. `item_numbers_an_opening_names` reads numbers only from a heading that `ITEM_LABEL_WITHOUT_COUNT`, a pattern of the approval-walk item finder, matches (`nn-systems/skills/walk-me-through/walk_me_through_approval_walk_minutes_and_walk_document_item_finder_common.py`). `shown_words` turns `## Item 4 of 9: a decision` into `Item 4: a decision`, which the pattern matches, giving `['4']`. It turns `## Item 4 of 9 (revised): Filter` into `Item 4 (revised): Filter`, which the pattern does not match, giving None, so no later heading ends item 4's shown text. The later line fails the same way: `opens_another_item("Item 5 (revised): next", "Item 4: a decision")` returns False, so a revised item 5 does not end an ordinary item 4's shown text either.

`shown_words` takes out a count written as a bare `of 9`, but not one written in parentheses, `(of 7)`, so `## Item 7 (of 7) — three smaller findings` keeps its count and gives None too.

The same happens to every heading form below. Each was found in agents' messages to the user in the transcripts under `nedlern@ned-box:/home/nedlern/nedsnodes-logs/agent-session-files-by-machine/`, by this search:

```
rg -o -g '*.jsonl' '\\n#{1,4} Items? [0-9][0-9.]*( of [0-9]+)? \([^)]{1,30}\)'
```

Each gives None:

- `## Item 1 of 9 (revised): the walk hook shows the current item`, found 31 times;
- `## Item 3 of 12 (question 2): an unreadable supervisor state file`, found 22 times;
- `### Item 4.1 of 13 (after the research): what the lost-file research found`, found 18 times;
- `## Item 7 (of 7) — three smaller findings`, found 16 times.

The walk-me-through answer hook tells an agent to show a revised item when a discussion settles on another option, so headings marked `(revised)` are ordinary.

## Why it matters

When item 4's shown text runs on into item 5, the hook compares item 4's current lines with lines from both items. A line of item 4 that the message never showed can then be matched by a line of item 5, as the docstring of `message_copy_of_item` says of a similar case, and the user's short answer can be counted with no model check for text he was not shown. Whether this has happened to a real answer has not been checked (unverified).

GHI [The walk short-answer hook cannot tell a heading that opens an approval-walk item from one that only mentions items](https://github.com/nedsnodes/nedsnodes/issues/4412) is about the same function, but about headings that only mention items being read as opening one, the opposite error, so it does not cover this.

## Next action

The agent-seat that owns the hook, agent-instructions-editor, whose PR [walk-me-through: the short-answer hook reads a shown heading's item numbers with the walk finder's grammar](https://github.com/nedsnodes/nedsnodes/pull/4370) added `item_numbers_an_opening_names`, makes that function read an item's number when the heading has text between the number and the title, such as `(revised)`, `(question 2)` or a count in parentheses, `(of 7)`, so that both the waiting item's heading and a later item's heading are read. Whether the change goes in that function or in `ITEM_LABEL_WITHOUT_COUNT` is the owner's choice; if it changes `ITEM_LABEL_WITHOUT_COUNT`, it also runs the item finder's own test suite, since the item finder reads walk-document headings with the same pattern; at 0f5f600df no other program uses it.

It adds a test that runs each of the four headings listed above through `item_numbers_an_opening_names`, and a test with `## Item 4 of 9 (revised): Filter` followed by `## Item 5 of 9: next`, and one with `## Item 4 of 9: a decision` followed by `## Item 5 of 9 (revised): next`, each expecting item 4's shown text to end before item 5.
