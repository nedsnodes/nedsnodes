---
issue: "[Read the walk-me-through #new and #new_if_d marks with one shared parser in the short-answer hook and the walk check program](https://github.com/nedsnodes/nedsnodes/issues/4715)"
---

# Read the walk-me-through #new and #new_if_d marks with one shared parser in the short-answer hook and the walk check program

## What is wrong

In an approval-walk's walk-document, a line that opens with `#new` holds a text the item's recommendation adds, and a line that opens with `#new_if_d` holds a text its alternative adds. Two programs read these marks, each with its own code:

- The short-answer hook, `nn-systems/skills/walk-me-through/walk-me-through-user-short-answer-to-approval-walk-item-expanded-into-instructions-user-prompt-submit-hook.py`. Its function `new_text_as_shown` strips list and quote prefixes with `LINE_MARKS`, then matches `NEW_TEXT_MARK` (line 561), which is case-insensitive, and gives the lead-in form an agent uses when it shows the line without its mark. The question Stop hook, `nn-systems/skills/walk-me-through/walk-me-through-agent-question-to-user-outside-approval-walk-items-refusal-stop-hook.py`, accepts that form.
- The walk check program, `nn-systems/skills/walk-me-through/walk-me-through-answer-added-texts-cold-read-fast-read-check-and-close.py`. Its `NEW_LINE` pattern (line 587), which is case-sensitive, finds the lines whose texts its check step gives a fast read before an answer takes effect.

They disagree. Calling the hook's `new_text_as_shown` and the check program's `NEW_LINE.match` on sample lines, on main at f839f0018, gives the first two columns below. The third column is the result the shared function should give: a mark is spelled exactly as the walk-me-through skill spells it, in lower case, followed by a space or a colon, after any list or quote prefix.

| line | hook reads a mark | check program reads a mark | shared function should read |
|---|---|---|---|
| `#NEW x` | `#new` | none | none |
| `#New: x` | `#new` | none | none |
| `#NEW_IF_D x` | `#new_if_d` | none | none |
| `#newé x` | `#new` | none | none |
| `#new x` | `#new` | `#new` | `#new` |
| `- #new x` | `#new` | `#new` | `#new` |
| `#new_if_d x` | `#new_if_d` | `#new_if_d` | `#new_if_d` |

## Why it matters

When a walk-document line opens with `#NEW text`, the question Stop hook accepts its lead-in form as a shown text, but the check step never gives it a fast read, so an approved text can take effect unread. The cause is that two programs each decide what a mark is, so a change to one of them opens a new disagreement, as [PR 4695](https://github.com/nedsnodes/nedsnodes/pull/4695)'s `re.ASCII` change did for `#newé`.

## What to do

1. Write one function that takes a line and returns the mark, `#new`, `#new_if_d` or none, with the text after it; it strips the list and quote prefixes itself, so that rule also exists once. Put it in a module both programs import, beside the check program.
2. Make the hook and the check program call it, and remove `NEW_TEXT_MARK`, `NEW_LINE` and the hook's own prefix stripping.
3. Test it with every row of the table above, asserting the last column.
4. Before the pull request is marked ready, run the old readers and the new function over every walk-document under `/home/nedlern/agents/*/docs/walk` and the log-store's `walk/`, and list in the pull request's description each line whose reading changes.

[The walk check program does not read a `#new` line that a shared setext heading shows above its underline (issue 4245)](https://github.com/nedsnodes/nedsnodes/issues/4245) concerns which lines of an item the check program reads; this issue concerns how one line is read, so the two do not overlap.

## Source

merge-lane-3 graded this finding file-for-later in its review of [PR 4695](https://github.com/nedsnodes/nedsnodes/pull/4695), from the mac-claude reviewer's inline comment at the hook's line 560.
