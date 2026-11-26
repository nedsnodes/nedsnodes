#!/usr/bin/env python3
"""The record, in a pull request's topic-worktree's own git directory, of the frozen-heads its fix-rounds were
briefed on.

A fix-round may merge origin/main into its frozen-head when git makes that merge without a conflict, and the
fix-round check confirms the merge's tree. scripts/checkout-freshness-catch-up.py reports every clean merge of
main on a branch as the catch-up merge CLAUDE.md bans, so it reads this record and leaves out a merge whose first
parent is a recorded frozen-head. scripts/pull-request-fix-round-author-brief-from-blocking-findings-and-one-commit-every-finding-answered-check.py
writes the record when it prints a fix-round brief.

The record lives in the worktree's own git directory, which no commit carries and which goes when the worktree is
removed. It holds one frozen-head SHA per line.

Load it by path, under the snake_case form of its file name:

    spec = importlib.util.spec_from_file_location(
        "pr_fix_round_briefed_frozen_heads_record_write_and_read_in_topic_worktree_own_git_directory_common", <path>)
"""

from pathlib import Path

PR_FIX_ROUND_BRIEFED_FROZEN_HEADS_RECORD_FILE_NAME = "pull-request-fix-round-frozen-heads-record.txt"


def pull_request_fix_round_frozen_head_record_add(worktree_git_directory: Path, frozen_head: str) -> None:
    path = Path(worktree_git_directory) / PR_FIX_ROUND_BRIEFED_FROZEN_HEADS_RECORD_FILE_NAME
    if frozen_head in pull_request_fix_round_frozen_head_record_read_all(worktree_git_directory):
        return
    with path.open("a", encoding="utf-8") as record:
        record.write(frozen_head + "\n")


def pull_request_fix_round_frozen_head_record_read_all(worktree_git_directory: Path) -> set:
    """The full SHAs recorded; an empty set when the worktree has no record."""
    path = Path(worktree_git_directory) / PR_FIX_ROUND_BRIEFED_FROZEN_HEADS_RECORD_FILE_NAME
    try:
        return {line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()}
    except FileNotFoundError:
        return set()
