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

## Source

The Codex review cell found this as finding f86d6ce9600f (P2), "Honor a retained Codex ID even when wording changes", in merge-lane-3's round-1 review of [Follow-up request block: a later review's comments pair with earlier findings in passes, exact match first, then nearest line](https://github.com/nedsnodes/nedsnodes/pull/4770), [review 6060270330](https://github.com/nedsnodes/nedsnodes/pull/4770#pullrequestreview-6060270330). The review graded it fix-next, not blocking, because main drops the finding in the same way and that pull request does not cause it; the review reproduced it on that pull request's head and on main. Pull request 4770 is the follow-up to [Follow-up request block: a later review restates each earlier finding at most once; one Codex finding id in two forms is one finding](https://github.com/nedsnodes/nedsnodes/pull/4751), and rewrites the same pairing into passes, exact match first and then nearest line, so the fix belongs to the code that pull request leaves.

## Next action

The finding is on the fix-next list of pull request 4770's author, the agent-seat overall-cleanup; after pull request 4770 merges, merge-lane-2 sends that agent-seat the list, and it fixes the finding in a follow-up pull request or tells merge-lane-2 why not. While pull request 4770 is open, leave this issue as it is, because its fix-round may fix this too. When pull request 4770 merges, or closes without merging, run the reproduction above on main. If the block holds review 1's finding once and the finding at line 9, record that as this issue's outcome and close it as completed. Otherwise fix it in a new pull request, in the pairing code main then has, whether or not pull request 4770 merged:

- Pair a comment with an earlier finding of the same category and path that shares one of its Codex finding ids, whatever the wording, before any pairing by text, so that a comment whose text matches an earlier finding cannot take a finding that its own Codex finding id does not name. A comment with no Codex finding id pairs by text, as now.
- When a comment could pair with more than one earlier finding, raise `Refused` and print no block, as the subcommand already does for a comment that opens with no category mark: name the comments, and tell merge-lane-2 to write the block by hand. This is the answer merge-lane-3's [comment 4696967578](https://github.com/nedsnodes/nedsnodes/pull/4770#discussion_r4696967578) on pull request 4770 asks for when that pull request's nearest-line pass has to choose.
- Add the three comments above as a test case that expects the block to hold review 1's finding once and the finding at line 9.
