---
issue: "[The merge gate refuses an approval on its first try because the approval's own inline comments, and the reviewer's review read before it, count as new activity](https://github.com/nedsnodes/nedsnodes/issues/5200)"
---

# The merge gate refuses an approval on its first try because the approval's own inline comments, and the reviewer's review read before it, count as new activity

`scripts/merge-gate.sh`, the check that runs before every merge, refuses most merges on the first try when the approval carries inline comments, or when the reviewer posted a review between the review's commissioned time and the approval. merge-lane-2's merge batch, `nedlern@ned-box:/home/nedlern/nedsnodes-logs/seats/merge-lane-2/merge-queue-drain-2026-11-22/drive.sh`, then runs the merge program a second time. This time it passes as reviewed-since the `submitted_at` of `ned-review-merge`'s latest review on the head, which is the approval itself. Each refusal costs a second run of the merge program. The second run also counts nothing posted between the commissioned time and the approval, so the gate's activity check does not cover that window on any pull request that took the retry.

The terms, as the gate uses them:

- reviewed-since: the time the gate takes as its third argument. The gate counts what was posted or edited after it as new activity, which must be read before merging.
- the pin, or pinned approval: the latest approving review on the pull request, the one the gate's merge is pinned to.
- the merge account: `ned-review-merge`, the GitHub account the merge lanes post their approvals as.
- the reviewer: `mac-claude`, the account the reviewing agent posts its review as, before the merge lane approves.
- the three channels: a pull request's inline comments, its issue comments and its reviews, which the gate reads.

## What happens

The merge program, `scripts/merge-lane-pull-request-merge-through-merge-gate-with-stacked-pull-request-retarget.py`, passes the gate as reviewed-since the time it is given. `drive.sh` gives it the commissioned time from the pull request's line in the merge queue file. That time is always earlier than the approval, because the approval is the review's last step.

The gate counts as new every inline comment, issue comment and review posted or edited after reviewed-since. Two kinds of activity are excluded:

- The pinned approval is excluded from the review count by its id.
- Some inline comments are read at their review's `submitted_at` instead of their own timestamp. This applies to a comment that belongs to the pinned approval or to one of the merge account's reviews, when that review was submitted at or before reviewed-since and the comment is unedited. The rule came from GHI [The merge gate refuses a merge when the merge account's own review carries inline comments stamped a second later](https://github.com/nedsnodes/nedsnodes/issues/729).

With reviewed-since earlier than the approval, the second exclusion never applies to the approval's own inline comments, so they count as new. The reviewer's review, posted after the commissioned time, counts too, along with its inline comments.

PR [3965](https://github.com/nedsnodes/nedsnodes/pull/3965) is one example:

- Its queue line's commissioned time was 2026-11-26T13:45:33Z.
- The reviewer's COMMENTED review 6075314788 was posted at 13:54:11Z with one inline comment.
- The merge account's approval 6075342563 was posted at 13:56:13Z with four inline comments, all stamped 13:56:13Z.
- The first gate run refused with `GATE REFUSED (#3965): 6 inline comment(s) posted or edited since 2026-11-26T13:45:33Z -- read them before merging` (`nedlern@ned-box:/home/nedlern/nedsnodes-logs/seats/merge-lane-2/merge-queue-drain-2026-11-22/merge-3965.first.out`).
- The retry passed `gate passed (#3965): ... no new channel activity since 2026-11-26T13:56:13Z`, the approval's own time, and the pull request merged at 2026-11-26T14:24:08Z (`merge-3965.out` in the same directory).

The refusal counted six comments, while the inline channel read on 2026-11-26 holds five after 13:45:33Z. The sixth may have been deleted after the refusal (unverified); either way, both steps below would still leave this pull request refused on the reviewer's review.

## How often

342 of the 1077 files `nedlern@ned-box:/home/nedlern/nedsnodes-logs/seats/merge-lane-2/merge-queue-drain-2026-11-22/merge-*.out` hold that inline refusal (`grep -l "inline comment(s) posted or edited since"`). Each of the 342 is a different pull request. For each refusal, the program `nedlern@ned-box:/home/nedlern/nedsnodes-logs/seats/merge-lane-1/merge-gate-pinned-approval-inline-comments-2026-11-26/classify.py` read the pull request's three channels on 2026-11-26. It took the pin to be the first approval at or after the refused reviewed-since, and sorted everything else posted between reviewed-since and the pin. Its per-refusal results are in `rows.json` beside it.

- In 76 refusals, the only activity in that window is the pin's own inline comments. PR [3925](https://github.com/nedsnodes/nedsnodes/pull/3925) is one: reviewed-since 13:36:14Z, and approval 6075080183 at 13:37:36Z with one inline comment at 13:37:36Z.
- In 266 refusals, there is other activity in the window. In 260 of them, it is the reviewer's COMMENTED review alone: 158 with no inline comments of its own and 102 with some. In the other 6, it includes the merge account's other reviews or issue comments. PR [3970](https://github.com/nedsnodes/nedsnodes/pull/3970) shows the first shape: all four refused comments are the approval's own, and the reviewer's review at 14:03:43Z has none. Once those four are not counted, the gate's review count, which it checks after the inline count, would refuse on that review.

These counts cover only refusals that the inline check printed. A pull request whose inline count was zero, but whose review count was not, was refused with a different message and is not among the 342.

## What to do

### Step 1, done now: the pinned approval's own inline comments

An unedited inline comment that belongs to the pinned approval is not counted, whatever reviewed-since is, just as the approval itself is not. Unedited means the comment's latest timestamp is no later than one second after the approval's `submitted_at`, the allowance GHI 729 set. An edit made later still counts, which keeps the gate's rule that a comment counts by its latest timestamp, the rule `scripts/merge-gate.sh`'s header calls F6. An inline comment on one of the merge account's other reviews is still left uncounted only when that review was submitted at or before reviewed-since. The pull request that does this names this issue on the `#root_cause` line of its description, which the gate requires. It removes the 76 refusals above. The other 266 still refuse, on the reviewer's review or its comments, or on the other activity in the 6.

### Step 2, proposed, not to be built until merge-lane-2 agrees: a read-through time on the queue line

The merge lane reads the reviewer's review and its inline comments before it posts the approval, but the gate has no record of that. The proposal:

- `scripts/merge-lane-pull-request-reviewer-review-post-and-read-back.py`, the program that posts the approval, reads the three channels itself before posting and shows the lane every item posted or edited after the commissioned time. It records as the read-through time the latest timestamp among the items it showed, or the commissioned time when it showed none. Because the program computes the time from what it showed, nothing rests on the lane's word about what it read.
- The pull request's line in the merge queue file carries that time, and the merge program passes it to the gate as reviewed-since in place of the commissioned time. A queue line written before the change, without the time, keeps today's behaviour.

This would remove the 260 refusals whose only other activity is the reviewer's review, and the 6 others whenever the lane was shown their activity before approving. It would also give the retry in `drive.sh` a recorded time to use in place of the approval's, so a comment posted after the read-through time and before the approval would still be counted.

Every lane writes queue lines to the same file, so the format change needs merge-lane-2's agreement first, and each lane's seat-brief and the merge program change with it; having the posting program append the queue line itself would take the format out of the seat-briefs. The next action on this step is for merge-lane-2 to agree or decline. When it agrees, the work is a pull request on the posting program, the queue-line format and the merge program, with tests that a comment posted after the read-through time still counts.
