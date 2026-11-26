---
issue: "[Fix-round brief failure after the answers file rewrite does not name the kept copy](https://github.com/nedsnodes/nedsnodes/issues/4772)"
---

# Fix-round brief failure after the answers file rewrite does not name the kept copy

## What goes wrong

The program `scripts/pull-request-fix-round-author-brief-from-blocking-findings-and-one-commit-every-finding-answered-check.py`, run without `--check` to print a fix-round brief, rewrites the pull request's answers file, `fix-round-answers-pull-request-<number>.md` in the topic-worktree, with one empty `<n>. ` line per finding. When the file held answers, it first saves them in a kept copy, a new `.md` file in the round's kept-copies directory, `<git common dir>/fix-round-answers-kept-copies/pr-<number>-review-<round's review id>/`. The brief then names that copy, so the author can copy the answers back.

After the rewrite the program lists kept-copies directories again. When such a listing fails, `answers_kept_copies_oldest_first` raises `StepFailed`, and the program prints `FAILED: could not list the kept copies of the answers file in <directory>: <error>` and exits 2. That message does not say that the answers file now holds only empty numbered lines, nor which file holds the answers it replaced. The author, or the user the message tells the agent to show it to, is left with an answers file of placeholders and no word of where the answers went.

The listings after the rewrite, on main at f31f2d310:

1. The round's own directory, at line 928 in `fix_round_answers_file_placeholder_line_per_finding_write_and_earlier_files_kept_copies_list_oldest_first`, the wrapper that writes the answers file and then lists the round's copies. `answers_file_with_one_line_per_finding_write` returns the kept copy's path at line 927, but its caller, that wrapper, discards it, so neither the wrapper nor `print_brief` can name it. The message names the directory, but not the copy's file name, and the directory is the one that could not be listed.
2. Each directory named by another review on the same frozen-head, at lines 1067 and 1068 in `print_brief`. Its failure names that other directory, not the round's, so the message gives no path to the copy at all.

The copy itself is not lost: it stays in the round's directory, and a later brief run whose listing succeeds names it, because a rerun keeps no copy of an answers file that holds only empty numbered lines. Until then, the reader must know to look under `<git common dir>/fix-round-answers-kept-copies/pr-<number>-review-<round's review id>/` for the newest `.md` file.

A failed write of the answers file already names its copy: `answers_file_with_one_line_per_finding_write`, line 948, adds `A copy of its text is in <path>.` to its `StepFailed`. The listings after the rewrite have no such note.

## Source

The Codex review cell found this as finding ed6f5301710a (P2), "Report the saved copy when the round's own listing fails", in merge-lane-3's round-1 review of [Fix-round brief: a modified unstaged answers file is no change, round records name dismissed reviews](https://github.com/nedsnodes/nedsnodes/pull/4767), [review 6059716894](https://github.com/nedsnodes/nedsnodes/pull/4767#pullrequestreview-6059716894). Codex reproduced it. The review graded it fix-next, not blocking, because main has the same defect and that pull request does not cause it. That pull request adds a handler that names this round's kept copies when a later step fails, but the failure in listing 1 is raised inside the wrapper before that handler can see the path.

## Next action

This finding is already on the fix-next list of the author of pull request 4767, the agent-seat reboot-test, and the review asks it to fix the finding in its fix-round if it can; if it does not, its description's `#root_cause_not_fixed` line carries a `#follow_up` link, which should name this issue. Do not fix it twice: while pull request 4767 is open, leave this issue as it is. If pull request 4767 merges with the fix, record that as this issue's outcome and close it as completed. If it merges without the fix, or closes without merging, fix it in a new pull request: make the wrapper return the path `answers_file_with_one_line_per_finding_write` returns, along with the copies it lists, so that `print_brief` has it too, and catch `StepFailed` once around every step after the rewrite, adding to its message that the answers file was rewritten and the path of the kept copy, as line 948 does, so that a step added later cannot miss the note. When no copy was kept, because the answers file held no answers, the message stays as it is, since nothing was replaced. Whether pull request 4767 fixed it is settled by the same test: add a test that makes each listing after the rewrite fail and checks that the message names the copy, and run it on main after pull request 4767 merges.
