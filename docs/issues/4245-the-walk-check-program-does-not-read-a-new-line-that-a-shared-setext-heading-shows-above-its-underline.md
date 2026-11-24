---
issue: "[The walk check program does not read a `#new` line that a shared setext heading shows above its underline](https://github.com/nedsnodes/nedsnodes/issues/4245)"
---

# The walk check program does not read a `#new` line that a shared setext heading shows above its underline

## Reproduction

Walk-document, with the walk-minutes' last line `#next_to_present item 2 of 2`:

```
# A walk

Items 1 and 2 of 2: two rows
#new "Hide the old rows."
----------------------------

**Item 1:** the first row.

#case_against none.

Recommendation: approve.

**Item 2:** the second row.

#case_against none.

Recommendation: approve.
```

On main at fe6194a84, `approval_walk_item_text_as_shown_to_user(text, parser, units, unit, "2")`, called with that walk-document's text, in `nn-systems/skills/walk-me-through/walk_me_through_approval_walk_minutes_and_walk_document_item_finder_common.py`, returns item 2's copy with the line `#new "Hide the old rows."` in it. So the item page and the agent's message show the user that proposed text with item 2.

Then the walk check program's check step, `nn-systems/skills/walk-me-through/walk-me-through-answer-added-texts-cold-read-fast-read-check-and-close.py check`, run in a checkout holding that walk-document and its walk-minutes, exits 0 and prints `no proposed text marked`. It runs no fast read: the test suite's fast-read stand-in records no call. The close step it then names records the user's answer with no fast read of the text he approved.

The test `test_a_waiting_item_reads_a_new_line_of_its_shared_setext_heading_that_its_shown_copy_holds`, in `nn-systems/skills/walk-me-through/tests/walk-me-through-answer-added-texts-cold-read-fast-read-check-and-close-test.py`, runs this case; it fails on main at fe6194a84.

## Why it happens

Two functions each decided which lines of the walk-document belong to an item that shares its heading with other items. `own_lines_of_unit`, in the finder module, builds the copy the user is shown. Below a setext heading, it puts the heading's further lines first, the lines between the heading's first line and its underline. `item_line_ranges`, in the check program, collects the `#new` marks. It started the item at the item's own opening, `**Item 2:**`, so it never read the heading's further lines. A `#new_if_d` mark there is missed the same way.

## Next action

Pull request [Walk check: collect an item's marks from the line ranges its shown copy uses](https://github.com/nedsnodes/nedsnodes/pull/4244), open and awaiting merge-lane-2's review, moves the range rule into one finder function, `approval_walk_unit_heading_end_and_item_line_ranges_below_heading_line`, which the shown copy and the check both read, and adds the test above. Once it merges, the agent-seat that filed this issue, agent-instructions-editor, records the outcome here and closes the issue with close-GHI.

## Source

merge-lane-2 sent this finding on 2026-11-22. The Codex review cell (P1) found it in PR [Walk item copy: a setext heading's further lines and underline go with every item it names](https://github.com/nedsnodes/nedsnodes/pull/4200) while merge-lane-2 reviewed the merge of main into PR [Walk items that add nothing, and item 56.2's simplification or deletion as kind 8, settle without the user; a #new mark after a part's Part N. is read](https://github.com/nedsnodes/nedsnodes/pull/4163). merge-lane-2 asked for a reproduction, and agent-instructions-editor reproduced it on 2026-11-22.
