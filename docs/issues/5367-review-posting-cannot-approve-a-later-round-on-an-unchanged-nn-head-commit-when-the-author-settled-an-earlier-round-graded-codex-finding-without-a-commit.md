---
issue: "[Review posting cannot approve a later round on an unchanged nn-head-commit when the author settled an earlier round's graded Codex finding without a commit](https://github.com/nedsnodes/nedsnodes/issues/5367)"
---

# Review posting cannot approve a later round on an unchanged nn-head-commit when the author settled an earlier round's graded Codex finding without a commit

Owner: overall-cleanup, which wrote the program's grade check and confirmed this is a defect on 2026-11-27. The grade check is the step of `scripts/merge-lane-pull-request-reviewer-review-post-and-read-back.py` that refuses a review file unless it grades every Codex finding on the reviewed nn-head-commit.

## What is wrong

The program refuses to post a merge-lane's approving review in this case:

1. Round 1's review on nn-head-commit H graded a Codex finding must-fix-now and requested changes.
2. The author's fix-round settled the finding without a commit. A description edit settles a missing `#root_cause` line, as `docs/agents/pr-reviewer-instructions.md` step 2 says: "no new commit is needed". So the nn-head-commit stays H.
3. Round 2's review file on H, whose verdict is APPROVE, is refused whatever it holds:
   - With no grade for the finding, the program refuses because it has none (the message at line 293 of the program on main: "Codex finding(s) on commit … have no grade in the review file").
   - With the grade must-fix-now, it refuses because no comment of that category names the finding (the message at line 307).
   - A must-fix-now comment cannot be added. The program posts any review holding one as REQUEST_CHANGES (docstring, line 66). The fix-round program, `scripts/pull-request-fix-round-author-brief-from-blocking-findings-and-one-commit-every-finding-answered-check.py`, and the after-merge follow-up program, `scripts/pull-request-follow-up-request-after-merge-finding-answers-and-next-step.py`, would also read that comment as an open finding.
   - The grade does-not-hold would be false, because the finding held.

The docstring (lines 70 and after) lets a Codex finding go without a must-fix-now, fix-next, fix-in-maintenance or file-for-later grade in only three cases: it is graded does-not-hold; the findings record matches it as SAME, which the program checks only for a finding that answers `#defect_already_on_main` yes and that needs no grade only when it also answers `#pull_request_triggers_the_defect` no; or no Codex run names the nn-head-commit. None fits a finding that held, was graded and posted in round 1, and was then settled without a commit. The SAME case comes closest but does not apply. Round 1's posting adds each new finding of that kind to the findings record as a row (docstring, lines 94 and after). On the same nn-head-commit, `scripts/findings-record-codex-finding-match-and-row-add-or-decide.py` match answers NEW for a row added from this finding at this nn-head-commit (`added_from_this_finding`, line 236), so the finding needs a grade again. That holds even though the reproduction's finding answers `#defect_already_on_main` yes and `#pull_request_triggers_the_defect` no.

## Reproduction

- Pull request: PR [Cold-read cell test stubs dump only the environment variables a case names](https://github.com/nedsnodes/nedsnodes/pull/5314), at nn-head-commit `e398dc0fca472687d99a5d7f1ee33609c9909e8c`.
- Round 1: merge-lane-3's changes-requested review 6090833372, whose one blocking finding was Codex finding `f4fb8b21a07f`, graded must-fix-now: replace `#no_defect_fixed` with a `#root_cause` line.
- The fix-round: MD-skills edited the description and pushed nothing.
- Round 2's refused review file: `nedlern@ned-box:/home/nedlern/nedsnodes-logs/seats/merge-lane-3/pr5314-round-2/review-5314-r2.json`.
- Effect: that pull request cannot be approved or merged until this is fixed. merge-lane-2 asked that no merge-lane work around it in the review file. merge-lane-3's task list holds the step of posting its round-2 approval once the fix merges.

## Root cause

The grade check takes every Codex finding on the nn-head-commit as needing a grade from this review. It does not ask whether a review already posted on that nn-head-commit graded the finding. The findings record does not answer that question either, because its match treats a row added at this nn-head-commit as new.

## What to do

Overall-cleanup's proposed fix:
- A Codex finding that a review already posted on the same nn-head-commit graded needs no new grade in a later round's review file; its earlier grade stands.
- For each such finding the earlier review graded must-fix-now, the later review file says whether this round settled it or it is still open, one of those two answers, and the program refuses a file that gives neither. A finding still open keeps the review a REQUEST_CHANGES review, as it did in round 1. For example, when round 1 had two blocking findings and the fix-round settled only one, the round-2 file answers settled for one and still open for the other.
- The posted body lists each such finding, with its earlier grade and, for a must-fix-now finding, the answer, under the heading that lists the graded Codex findings. A finding graded fix-next, fix-in-maintenance, file-for-later or does-not-hold is listed with its earlier grade only.
- The fix-round and after-merge follow-up programs do not read a settled finding as open.

Two choices are left to the owner: whether a later review file may grade such a finding again, replacing its earlier grade, and where the program reads the earlier grade from.

Before building a second record of earlier grades per nn-head-commit, read GHI [Findings record in the shared database, so a decided reviewer finding is not raised and graded again](https://github.com/nedsnodes/nedsnodes/issues/4821). Its findings record already has the posting program copy a matched row's earlier decision into the posted review, and its row for a finding records the finding id, the nn-head-commit and the grade. It holds rows only for findings that answer `#defect_already_on_main` yes, though, so reusing it means either widening which findings it holds or keeping a second lookup for the rest. Reading a stored record keyed by nn-head-commit and finding id is sturdier than reading the grade back out of a posted review's text.

The test reproduces the reproduction's case: round 1's Codex run record and posted review on nn-head-commit H, then a round-2 review file on H whose verdict is APPROVE, with no grades and the finding answered as settled, which posts as APPROVE.
