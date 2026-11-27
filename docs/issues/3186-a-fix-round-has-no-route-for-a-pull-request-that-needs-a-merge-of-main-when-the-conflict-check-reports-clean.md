---
issue: "[A fix-round has no route for a pull request that needs a merge of main when the conflict check reports clean](https://github.com/nedsnodes/nedsnodes/issues/3186)"
---

# A fix-round has no route for a pull request that needs a merge of main when the conflict check reports clean

## Reproduction

Pull request 3164 (head `024dec81bfb6e982be822e088c3c913dc2848294`, author account `ubuntu-claude`, written by the agent-seat cold-read-improvement) added this call at line 1585 of `nn-systems/skills/walk-me-through/walk-me-through-answer-added-texts-cold-read-fast-read-check-and-close.py`: `new_marks(text, tokens, ranges)`.

Pull request 3150, merged to main earlier (its head `b26ecc6b0`, its merge commit `af8961c67`), had changed that function to `def new_marks(text, tokens, ranges, shown):`; before it, the definition was `def new_marks(text, tokens, ranges):`. Pull request 3164's branch did not hold that change, and the two changes touch different lines, so git merges them without a conflict.

merge-lane-2's head test run on pull request 3164's head merged with main (`7e1875a1e`) failed five cases of `walk-me-through-answer-added-texts-cold-read-fast-read-check-and-close-test.py`, each with `TypeError: new_marks() missing 1 required positional argument: 'shown'`; the suite passes on origin/main `2992d1efb`. merge-lane-2's changes-requested review 5862710059 on pull request 3164 said, in its inline finding on line 1585: "Merge main into the branch and pass `shown` the way main's other callers of `new_marks` do."

The fix-round had no way to do that:

- The fix-round brief that `scripts/pull-request-fix-round-author-brief-from-blocking-findings-and-one-commit-every-finding-answered-check.py` prints tells the subagent, in step 1, to run `scripts/branch-conflict-check.py --pull-request <number>` and to act only on `VERDICT: CONFLICT`; its step 4 says "Put every change in one commit on top of the branch as step 1 left it."
- `scripts/branch-conflict-check.py` reports a textually clean branch as `VERDICT: CLEAN -- <head> does not conflict with <base>. Nothing to do.`, so its replace answer, which it gives an open pull request that conflicts with main, does not apply.
- Without a merge of main the fix cannot be tested: the branch's own `new_marks` still takes three arguments, so a call passing `shown` fails on the branch.
- With a merge of main, the program's `--check` refuses the round: its function `fix_commit_range` accepts, without `--after-conflict-merge`, only "one non-merge commit whose parent is the frozen-head", and refuses anything else with "A fix-round is one non-merge commit whose parent is the frozen-head."
- The check does have `--after-conflict-merge`, which accepts "a merge of origin/main whose first parent is the frozen-head, followed by at most one non-merge commit". Its `--help` says the flag is for a round that "starts with a merge of origin/main, made because branch-conflict-check.py reported a conflict", and the brief never offers it, so a fix-round agent on a clean verdict has no instruction that leads to it. The code does not itself check that a conflict was reported (read from `fix_commit_range` on origin/main, 2026-11-11).

The author closed pull request 3164 and replaced it by hand with pull request 3184, whose description says: "The fix-round could not carry this: the fix needs main's new signature, and a fix-round may not hold a merge commit."

It happened again on 2026-11-26, with a test that reads files rather than code that calls a function. Pull request [Hashtag glossary page, its test, and every hashtag reader accepts the closing #](https://github.com/nedsnodes/nedsnodes/pull/5024) (frozen-head `fb6500c704686574f7b67bbcc170eb02870c8093`, written by the agent-seat reboot-test) adds `scripts/nedsnodes-hashtag-glossary-lists-every-hashtag-in-use-and-no-other-test.py`, which checks that the hashtag glossary page lists every hashtag the repository's files use, and no other. After the branch was cut, main added four hashtags to `docs/agents/pr-reviewer-instructions.md`: `#defect_already_on_main`, `#pull_request_triggers_the_defect`, `#false_report_of_success_on_failure` and `#defect_evidence`. merge-lane-3's head test run, which it makes after its review on the pull request's frozen-head merged with main (`0f0557bb6c73`), failed that suite, and its changes-requested review 6074611866 said to merge main and add the four hashtags to the page. The fix-round's subagent tried both kinds of round commit:

- A merge of origin/main followed by the four entries (commit `6dbebad46`, never pushed): `--check` refused it with "A fix-round is one non-merge commit whose parent is the frozen-head … drop any merge of main."
- One commit on the frozen-head adding only the four entries (commit `f8d85d743`, never pushed): `--check` refused it because the glossary suite "fail[s] at the round's commit f8d85d74356a and not at the frozen-head fb6500c70468". The branch does not hold main's `docs/agents/pr-reviewer-instructions.md`, so the test sees the four entries as hashtags no file uses.

`scripts/branch-conflict-check.py --pull-request 5024`, run in the fix-round's step 1, reported `VERDICT: CLEAN`, so the replace route did not apply either.

## Why this matters

A semantic conflict with main, where main changed code the branch calls, or files the branch's tests read, without touching the branch's lines, is found only by the head test run on the merged tree, after the review. Each time it happens the author must leave the fix-round process, replace the pull request by hand, and have the replacement reviewed again from the start, at the cost of a full review instead of a fix-round review of one commit. Nothing in the brief tells the author that this is the route, so the next author may instead stop, or make a merge of main that `--check` refuses before the push, in step 6 of the brief, and then not know what to do.

## What to do

The route is decided and built: pull request [Fix-round check accepts a merge of origin/main that git makes without a conflict, before the one fix commit and the one overview commit](https://github.com/nedsnodes/nedsnodes/pull/3965), which carries items 67.1 and 67.2 of the approval-walk agent-instructions-editor-backlog-decisions-2026-11-05, approved by the user on 2026-11-19 (walk-minutes `nedlern@ned-box:/home/nedlern/nedsnodes-logs/walk/agent-instructions-editor-backlog-decisions-2026-11-05-minutes.md`, lines 573-581). With it, the fix-round's `--check` accepts a merge of origin/main that git makes without a conflict, followed by one non-merge fix commit, which is what both cases above needed.

When pull request 3965 merges, agent-instructions-editor, which owns the fix-round program, records the outcome here and closes this issue.

## Outcome

Fixed by pull request [Fix-round check accepts a merge of origin/main that git makes without a conflict, before the one fix commit and the one overview commit](https://github.com/nedsnodes/nedsnodes/pull/3965), merged on 2026-11-26 at 14:24Z as `d5bf4b8d2dd4`. The fix-round's `--check` now accepts a round that opens with a merge of origin/main whose first parent is the frozen-head, which git makes without a conflict, followed by one non-merge commit. It remakes the merge with `git merge-tree --write-tree` and refuses one whose tree differs. Pull request [Hashtag glossary page, its test, and every hashtag reader accepts the closing #](https://github.com/nedsnodes/nedsnodes/pull/5024) was replaced from main before this merged, and so did not use the route.
