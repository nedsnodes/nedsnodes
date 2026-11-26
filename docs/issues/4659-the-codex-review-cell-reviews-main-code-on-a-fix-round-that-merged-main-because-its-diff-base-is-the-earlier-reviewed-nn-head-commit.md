---
issue: "[The Codex review cell reviews main's code on a fix-round that merged main, because its diff base is the earlier reviewed nn-head-commit](https://github.com/nedsnodes/nedsnodes/issues/4659)"
---

# The Codex review cell reviews main's code on a fix-round that merged main, because its diff base is the earlier reviewed nn-head-commit

## Reproduction

The Codex review cell is the Codex review that `scripts/merge-lane-pull-request-worktrees-reviewer-brief-codex-review-and-head-tests-run-without-merge.py` (the orchestrator below) runs on a pull request through `scripts/code-review-codex-cell.py`, passing it a diff base.

Pull request [#3957](https://github.com/nedsnodes/nedsnodes/pull/3957), fix-round, Codex review cell report `nedlern@ned-box:/home/nedlern/nedsnodes-logs/seats/merge-lane-2/merge-helpers/cx/pr3957-63677f09/codex-code-review-report.md`:

- The report's provenance line gives `base=63677f09f7307d74f11bdb34d72c5423559294f6`, the nn-head-commit reviewed in the round before. Between that commit and the pull request's head the author merged main.
- Codex's opening line says so itself: "The findings are in the changes brought in from `origin/main`".
- Its first P1, "Keep real Claude transcripts out of the shared test sandbox", cites `scripts/run-all-test-suites.py:924-926`. `git blame` at the pull request's head puts those lines in commit `88f0d23d51`, which reached main through [#3936](https://github.com/nedsnodes/nedsnodes/pull/3936), not through #3957. Its second P1 cites `nn-systems/handoff/agent-seat-terminal-captures-older-than-seven-days-delete.py:83-85`, blamed to commit `014d3448cf` of [#4013](https://github.com/nedsnodes/nedsnodes/pull/4013).

The same thing happened again after the survey below ended: on [#4455](https://github.com/nedsnodes/nedsnodes/pull/4455), round 2 (head `81b1733c`, whose only new commits are two merges of main), the lane's approving review says "The Codex review cell ran from f645dae006c3, so its diff held main's changes that the merges brought in", and set aside all five Codex findings as code the pull request does not change.

Counted over the 300 Codex reports with findings that the survey `nedlern@ned-box:/home/nedlern/nedsnodes-logs/seats/merge-lane-2/codex-and-claude-reviewer-misfires-survey-2026-11-24.md` collected, by `nedlern@ned-box:/home/nedlern/nedsnodes-logs/seats/merge-lane-2/reviewer-texts-facts-and-blocking-drafts-2026-11-25/evidence/stale.py` (run from a checkout with the pull request heads fetched, as `python3 stale.py <the evidence directory that holds stale.py, codex-rows.json and prinfo.json>`; output beside it in `stale-base-codex-reports-output.txt`, and a rerun on 2026-11-25 printed the same):

- 222 reports were first rounds and 78 were fix-rounds, whose base is a commit of the pull request.
- 17 of the fix-round reports, on 16 pull requests, had a merge commit on the first-parent range from the base to the pull request's final nn-head-commit, committed before the report was written: 3957, 4001, 4019, 4021, 4034, 4045, 4076, 4127, 4163 (twice), 4244, 4293, 4310, 4326, 4527, 4555 and 4559.
- Those 17 reports hold 68 findings. 51 are on files the pull request does not change, and the lanes posted none of the 51. The other 61 fix-round reports hold 1 such finding in 161, and the 222 first rounds 3 in 596.

Limits of the count: a finding is matched to the pull request's files by file name alone; the range ends at the final nn-head-commit rather than the one reviewed; and a report rerun on the same head counts each time.

## What is wrong

`scripts/merge-lane-pull-request-worktrees-reviewer-brief-codex-review-and-head-tests-run-without-merge.py` lines 340-354 (at main `2e9e302c3`) set the Codex review cell's base: when `--head-commit-reviewed-before` is given, the base is that commit, unconditionally; otherwise it is `git merge-base main head`. When the first-parent commits since the earlier reviewed nn-head-commit include a merge of main, the diff from that commit includes everything main gained, and Codex reviews main's code as if the pull request wrote it.

`scripts/pull-request-review-plan.py` already detects this case: its docstring (lines 31-37) and its code (lines 1211-1228) review a fix-round whole when the delta holds a merge commit or the history was rewritten, and restrict the delta's files to the pull request's own. The orchestrator's Codex path does not use that result. It also refuses a brief specifications entry carrying `reviewed_before` without the option (lines 218-221), and merge-lane-2's seat-brief says to add `--head-commit-reviewed-before` for every fix-round, so a lane cannot simply leave the option out.

## Why it matters

Each such report spends a Codex run on code the pull request did not write, and the lane must read and set aside every finding in it, one by one, as on #4455. A real defect in the pull request's own changes is easy to miss among them, since Codex reports only a handful of findings per run.

## What to do

Change the orchestrator so that, when the first-parent range from the earlier reviewed nn-head-commit to the head holds a merge commit, or the earlier reviewed nn-head-commit is not an ancestor of the head, the Codex review cell runs from the merge base with main instead, as `scripts/pull-request-review-plan.py` already reviews such a round whole. Take the decision from the plan's output, or from the same git checks, rather than a second rule written separately. Add a test with a scratch repository whose fix-round merges main, checking the base passed to the cell.

The fix must also settle what follows from the new base: the `base_kind` the orchestrator prints at line 403; the Codex record directory `cx/pr<n>-<base[:8]>` (line 435), which with the merge base can take the same name as the first round's record; and the case the plan also reviews whole, an earlier reviewed nn-head-commit missing from the checkout, which the orchestrator refuses today (lines 343-351).

Related open issues, none of which covers this defect (ghi-guide-agent, open issues, 2026-11-25): [#2505](https://github.com/nedsnodes/nedsnodes/issues/2505) proposes one store recording which round and nn-head-commit each review belongs to, from which this base could later come; [#2384](https://github.com/nedsnodes/nedsnodes/issues/2384) keys a pull request's rounds by nn-head-commit and tree; [#3186](https://github.com/nedsnodes/nedsnodes/issues/3186) is about a fix-round that needs a merge of main, the case that triggers this one.
