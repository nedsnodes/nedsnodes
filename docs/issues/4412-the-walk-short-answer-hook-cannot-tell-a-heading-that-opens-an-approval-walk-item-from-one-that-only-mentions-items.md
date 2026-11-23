---
issue: "[The walk short-answer hook cannot tell a heading that opens an approval-walk item from one that only mentions items](https://github.com/nedsnodes/nedsnodes/issues/4412)"
---

# The walk short-answer hook cannot tell a heading that opens an approval-walk item from one that only mentions items

## What is wrong

When the user answers an approval-walk item, the short-answer hook, `nn-systems/skills/walk-me-through/walk-me-through-user-short-answer-to-approval-walk-item-expanded-into-instructions-user-prompt-submit-hook.py`, finds the text the agent showed him for that item. Its function `opens_another_item` ends that text at a heading that opens a different item. It decides from the heading's words alone, with the pattern `ITEM_LABEL_WITHOUT_COUNT` in `nn-systems/skills/walk-me-through/walk-me-through-approval-walk-minutes-and-walk-document-item-finder-common.py`, the walk finder, so it misreads two forms:

- A sub-heading that only mentions other items ends the text too early. With item 4 waiting, `opens_another_item("Items 13, 14, 15 are written", "Item 4: x")` returns True, so a recommendation below `### Items 13, 14, 15 are written` is reported as not shown although the agent showed it word for word. The answer then costs a retry.
- A heading that does open another item can be missed. `opens_another_item("Item 5, 2 things changed", "Item 4: x")` and the same call with `Item 5:foo` return False, so item 5's decision line can count as shown for item 4, and the user's answer to item 4 can count for text that belonged to item 5.

## Why it matters

The first form has happened: `### Items 13, 14, 15 are written` is in the Mac transcripts mirrored at `nedlern@ned-box:/home/nedlern/nedsnodes-logs/agent-session-files-by-machine/mac/projects/-Users-el-agents-MD-skills/4cf99e0a-14cb-461a-b096-3342584f432e.jsonl`. Whether it ever cost a refused answer has not been checked (unverified). The second form has not happened: merge-lane-2's review of [pull request 4394](https://github.com/nedsnodes/nedsnodes/pull/4394) found it in none of the 14,809 stored item openings.

## Next action

Search the transcripts under `nedlern@ned-box:/home/nedlern/nedsnodes-logs/agent-session-files-by-machine/` for the hook's refusal tag `[rule walk-me-through-short-answer-to-item-not-shown-discarded]`, and read each refused answer for a line the agent showed below a deeper heading of the first form.

If no refusal has that cause, record the search in this GHI-MD and close the issue as not planned with `scripts/ghi-issue-write.py close`, because `CLAUDE.md`'s guard rule then supports no new parsing. If the search cannot be finished, record why and leave the issue open.

If a refusal has that cause, fix the first form: pass the heading's level to `opens_another_item`, so that a heading deeper than the waiting item's heading does not end its text, and add a test with `### Items 13, 14, 15 are written`. A heading at the waiting item's level still ends its text. Leave the second form alone until it happens.
