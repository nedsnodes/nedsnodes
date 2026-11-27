---
issue: "[The walk read step never shows an unnumbered sub-step that follows an item's numbered sub-steps](https://github.com/nedsnodes/nedsnodes/issues/5330)"
---

# The walk read step never shows an unnumbered sub-step that follows an item's numbered sub-steps

## What is wrong

The walk-me-through skill's answer program, `nn-systems/skills/walk-me-through/walk-me-through-answer-added-texts-cold-read-fast-read-check-and-close.py`, has a read step, the subcommand `approval-walk-waiting-item-cold-read-fast-read`. It gives the approval-walk item that the walk-minutes' last `#next_to_present` line names its cold-read-fast-read before the agent shows that item to the user. When that item is split into numbered `###` sub-steps, such as `### Item 3.1 of 9` and `### Item 3.2 of 9`, the read step moves the `#next_to_present` line to the first sub-step the walk-minutes record no answer to, so the user is shown one sub-step at a time.

The defect: when the item also has an unnumbered `###` heading after its last numbered sub-step, such as `### A trailing unnumbered sub-step`, the read step reads 3.1, then 3.2, and exits 0 each time. No read covers the text under the trailing heading. The user is never shown that text, so it is never decided, and nothing warns the agent.

The same happens when the `#next_to_present` line already names a numbered sub-step, such as `#next_to_present item 3.2 of 9`: the read step reads that sub-step alone and never looks at the headings after it.

This matters because a `#new` text under the trailing heading is a change the user is meant to approve. The walk then goes on as though the item were fully decided.

## Why it happens

`item_unit_spans`, in the walk-document item finder `nn-systems/skills/walk-me-through/walk-me-through-approval-walk-minutes-and-walk-document-item-finder-common.py`, ends a numbered sub-step's unit at the next `###` heading. So the trailing unnumbered heading belongs to no numbered sub-step. The answer program's `approval_walk_item_first_numbered_sub_step_without_answer` picks only from numbered sub-steps, so it never picks the trailing heading either. When `#next_to_present` names a sub-step number such as 3.2, that function is not called at all.

## Reproduction

Run on ned-box on 2026-11-27 in a detached worktree of main at commit `8e16dabab`. The script is kept at `nedlern@ned-box:/home/nedlern/nedsnodes-logs/seats/merge-lane-1/ghi-drafts/walk-read-step-trailing-unnumbered-sub-step-repro/repro.py`. It loads the answer program's test file, `nn-systems/skills/walk-me-through/tests/walk-me-through-answer-added-texts-cold-read-fast-read-check-and-close-test.py`, and uses its `Case` harness, as the test `test_the_waiting_item_read_step_names_and_reads_the_first_undecided_numbered_sub_step_of_the_item_named` does. It splits item 3 into `### Item 3.1 of 9` and `### Item 3.2 of 9`, then adds `### A trailing unnumbered sub-step` holding the line `#new TRAILINGTEXT must be shown to the user.` at the item's end. From the root of a checkout of main, run `python3 /home/nedlern/nedsnodes-logs/seats/merge-lane-1/ghi-drafts/walk-read-step-trailing-unnumbered-sub-step-repro/repro.py nn-systems/skills/walk-me-through/tests/walk-me-through-answer-added-texts-cold-read-fast-read-check-and-close-test.py`.

Output:

```
read1 rc 0 #next_to_present item 3.1 of 9
close1 0 #next_to_present item 3.2 of 3
read2 rc 0 #next_to_present item 3.2 of 3 False
read records holding TRAILINGTEXT: [] of 7
items read: ['item 3.1 of 9', 'item 3.2 of 9']
```

Both read steps exit 0. The items read are 3.1 and 3.2 only, and none of the 7 files the reads wrote holds the trailing text. The script's second `check` and `close` exit 1 only because the script does not give that check an answer in the form the harness needs; that failure is not part of this defect.

Two reviewers of pull request [Walk read step numbers an item's unnumbered sub-steps, so an answer decides only the waiting sub-step](https://github.com/nedsnodes/nedsnodes/pull/3937) found the same defect, in merge-lane-1's review of 2026-11-27, https://github.com/nedsnodes/nedsnodes/pull/3937#pullrequestreview-6088814235:
- Codex finding 435244c63a60, which the review reports Codex reproduced in memory, without the test harness, for both the trailing heading and the `#next_to_present` line naming a sub-step.
- mac-claude's finding on line 3680 of that pull request's version of the answer program, in review https://github.com/nedsnodes/nedsnodes/pull/3937#pullrequestreview-6088765817, which mac-claude reproduced through the same `Case` harness.

That pull request adds a check for an unnumbered heading between two numbered sub-steps. Its check stops at the end of the last numbered sub-step's unit, so it does not reach a heading after it, and the pull request does not cause this defect.

## What to do

1. First write two tests that fail on main: one with the trailing unnumbered heading, and one with the `#next_to_present` line naming sub-step 3.2 and a trailing heading after it. The reproduction script above shows how to build them with the `Case` harness.
2. If pull request 3937 has merged when you start, run the two tests first. If both pass, it fixed this defect: land the tests alone, record that in this file, and close the issue.
3. Otherwise make one rule in one place, beside `item_unit_spans` in the walk-document item finder: once an item has a numbered `###` sub-step, every `###` heading that item owns in the walk-document must be numbered. A heading the item owns is one inside the item and not marked `Withdrawn:` at its start; another item's headings are not the item's own. The rule then covers an unnumbered heading in any position: before the first numbered sub-step, between two, or after the last. Check the item's own headings, rather than the lines between two line numbers, which is how pull request 3937's round-3 check misses the trailing heading.
4. Make the read step apply that rule before it writes anything, whether the `#next_to_present` line names the item or one of its sub-steps. When the rule fails, the read step refuses, writes nothing, names every unnumbered heading the item owns, and prints for each the numbered heading line to put in its place, such as `### Item 3.3 of 9: A trailing unnumbered sub-step`.
