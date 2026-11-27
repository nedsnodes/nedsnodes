---
issue: "[Follow-up request block drops a new finding worded as an earlier finding that a later review rewords under its Codex finding id](https://github.com/nedsnodes/nedsnodes/issues/4778)"
---

# Follow-up request block drops a new finding worded as an earlier finding that a later review rewords under its Codex finding id

## What goes wrong

The subcommand `print-follow-up-request-block-from-merge-lane-2-reviews` of `scripts/pull-request-follow-up-request-after-merge-finding-answers-and-next-step.py` prints the `#follow_up_request` block that merge-lane-2 puts, unchanged, at the end of its notice to an author that their pull request merged. The block lists every fix-next, fix-in-maintenance and file-for-later finding in merge-lane-2's reviews of the pull request, and prints a finding that a later review restates only once.

In `print_follow_up_request_block_from_merge_lane_2_reviews`, on main at 71344a302, a comment counts as restating an earlier finding (lines 1045 to 1047) when its category, path and text equal the earlier finding's, or when its category, path and text without the `(Codex finding <id>)` mark equal the earlier finding's and either the Codex finding ids are the same or the comment is in a later review that has not yet restated that finding. Text is the only thing these tests always compare; a shared Codex finding id never pairs two comments whose text differs.

So when these three comments are all in merge-lane-2's reviews of one pull request:

- review 1, a request for changes: `**fix-next** Rename it (Codex finding aaaaaaaaaaaa).` at `scripts/thing.py:3`;
- review 2, the approval, restating it reworded under the same id: `**fix-next** Rename the helper (Codex finding aaaaaaaaaaaa).` at line 3;
- review 2, a new finding that happens to use review 1's old wording under another id: `**fix-next** Rename it (Codex finding bbbbbbbbbbbb).` at line 9;

the reworded restatement does not pair with review 1's finding, because its text differs, and is printed as a second finding; the new finding at line 9 pairs with review 1's finding, because its text matches and review 2 has not yet restated that finding, and is left out. The program exits 0 and prints:

```
#follow_up_request pull request 1964
1. fix-next: `scripts/thing.py:3`: Rename it (Codex finding aaaaaaaaaaaa).
2. fix-next: `scripts/thing.py:3`: Rename the helper (Codex finding aaaaaaaaaaaa).
```

Review 1's finding is printed twice, once in each wording, and the finding at line 9 is missing. A finding left out of the block never reaches the author, and nothing reports that it was left out.

This was reproduced on main at 71344a302 by running the subcommand in process with the helpers of `scripts/pull-request-follow-up-request-after-merge-finding-answers-and-next-step-test.py`: `print_block` fakes gh to return the given reviews and comments, and the pull request number 1964 is the test file's. The reproduction is this code, run with those helpers loaded, which the test file does when it is imported without its last lines, the loop that runs every test:

```python
reviews = [merge_lane_review(1, state="CHANGES_REQUESTED", body="REQUEST_CHANGES\n\nRound 1."), merge_lane_review(2)]
comments = [
    merge_lane_comment(10, 1, "**fix-next** Rename it (Codex finding aaaaaaaaaaaa).", line=3),
    merge_lane_comment(11, 2, "**fix-next** Rename the helper (Codex finding aaaaaaaaaaaa).", line=3),
    merge_lane_comment(12, 2, "**fix-next** Rename it (Codex finding bbbbbbbbbbbb).", line=9),
]
code, out, err = print_block(reviews, comments)
```

The same test also drops a new finding when the later review does not restate the earlier finding at all. When merge-lane-2's reviews of one pull request hold only these two comments:

- review 1, a request for changes: `**fix-next** Rename it (Codex finding aaaaaaaaaaaa).` at `scripts/thing.py:3`;
- review 2, the approval, a new finding with the same wording under another id: `**fix-next** Rename it (Codex finding bbbbbbbbbbbb).` at line 90;

the comment at line 90 pairs with review 1's finding, because its text without the Codex finding mark matches and review 2 has not yet restated that finding, and is left out. The program exits 0 and prints:

```
#follow_up_request pull request 1964
1. fix-next: `scripts/thing.py:3`: Rename it (Codex finding aaaaaaaaaaaa).
```

This was reproduced on main at ea0d050d9 in the same way as the first case, with the first case's `reviews` and `print_block` call, and these two comments in place of its three:

```python
comments = [
    merge_lane_comment(10, 1, "**fix-next** Rename it (Codex finding aaaaaaaaaaaa).", line=3),
    merge_lane_comment(12, 2, "**fix-next** Rename it (Codex finding bbbbbbbbbbbb).", line=90),
]
```

In this case no comment shares a Codex finding id with review 1's finding, and only one earlier finding could pair, so neither the pairing by shared Codex finding id nor the refusal of a comment that could pair with more than one earlier finding, both under Next action, changes what is printed. The pairing across Codex finding ids is on purpose: the code comment above the test says a later review restates an earlier finding with a new Codex finding id when its line range moved. The comments alone cannot tell such a restatement from a new finding that happens to have the same wording: both have the same category, path and text, and a different Codex finding id and line.

## Source

The Codex review cell found this as finding f86d6ce9600f (P2), "Honor a retained Codex ID even when wording changes", in merge-lane-3's round-1 review of [Follow-up request block: a later review's comments pair with earlier findings in passes, exact match first, then nearest line](https://github.com/nedsnodes/nedsnodes/pull/4770), [review 6060270330](https://github.com/nedsnodes/nedsnodes/pull/4770#pullrequestreview-6060270330). The review graded it fix-next, not blocking, because main drops the finding in the same way and that pull request does not cause it; the review reproduced it on that pull request's head and on main. Pull request 4770 is the follow-up to [Follow-up request block: a later review restates each earlier finding at most once; one Codex finding id in two forms is one finding](https://github.com/nedsnodes/nedsnodes/pull/4751), and rewrites the same pairing into passes, exact match first and then nearest line, so the fix belongs to the code that pull request leaves.

The Codex review cell found the second case as finding 3e981be21ff3 (P2), "Do not treat a lone lookalike as a confirmed restatement", in merge-lane-3's round-2 review of pull request 4770, [review 6062336225](https://github.com/nedsnodes/nedsnodes/pull/4770#pullrequestreview-6062336225), and [comment 4698708164](https://github.com/nedsnodes/nedsnodes/pull/4770#discussion_r4698708164) there. The review graded it fix-next, not blocking, for the same reason as the first case, and said it reproduced it on that pull request's head 27643144a and on main a8ca00d83. It asks for detection rather than better guessing: refuse in this case too, or record why the pairing is accepted.

## Next action

Both findings are on the fix-next list of pull request 4770's author, the agent-seat overall-cleanup; after pull request 4770 merges, merge-lane-2 sends that agent-seat the list, and it fixes them in a follow-up pull request or tells merge-lane-2 why not. While pull request 4770 is open, leave this issue as it is, because its fix-round may fix this too. When pull request 4770 merges, or closes without merging, run both reproductions above on main. If the first prints a block holding review 1's finding once and the finding at line 9, and the second prints no block and exits with the refusal the third item below describes, record that as this issue's outcome and close it as completed. Otherwise the agent-seat that acts on this issue, overall-cleanup when merge-lane-2 sends it the list, fixes whichever case still fails in a new pull request, in the pairing code main then has, whether or not pull request 4770 merged, with the items below that the failing case needs and the test case for each case:

- Pair a comment with an earlier finding of the same category and path that shares one of its Codex finding ids, whatever the wording, before any pairing by text, so that a comment whose text matches an earlier finding cannot take a finding that its own Codex finding id does not name. A comment with no Codex finding id pairs by text, as now.
- When a comment could pair with more than one earlier finding, raise `Refused` and print no block, as the subcommand already does for a comment that opens with no category mark: name the comments, and tell merge-lane-2 to write the block by hand. This is the answer merge-lane-3's [comment 4696967578](https://github.com/nedsnodes/nedsnodes/pull/4770#discussion_r4696967578) on pull request 4770 asks for when that pull request's nearest-line pass has to choose.
- When a comment and an earlier finding both carry Codex finding ids, the comment would pair with the earlier finding only by its text without the Codex finding mark, their Codex finding ids differ, and the comment's review restates that earlier finding under none of the earlier finding's Codex finding ids, raise `Refused` in the same way instead of pairing, because the comment may be a new finding. This also refuses a real restatement whose Codex finding id changed, and merge-lane-2 then writes that block by hand.
- Add the three comments of the first case as a test case that expects the block to hold review 1's finding once and the finding at line 9, and the two comments of the second case as a test case that expects the refusal.
