#!/usr/bin/env python3
"""Rebuild a pull request's two detached worktrees under the review worktrees directory.

Usage:
  scripts/merge-lane-pull-request-head-and-merged-worktrees-rebuild.py <pull request number>
      <nn-head-commit> <main commit> [--merged-worktree-only] [--merge-lane-worktrees-and-outputs-directory DIR] [--merge-lane-review-worktrees-directory DIR] [--review-tools-worktree-at-main DIR]

Fetches the pull request's head from origin unless the nn-head-commit is already
local, then makes pr<n>-head at the nn-head-commit and pr<n>-merged at the main commit with the nn-head-commit merged
in, as merge-lane-2, always with a merge commit. A worktree already at either
path is removed first, with any changes in it; a worktree there whose .git is
gone is removed the same way once its .git is written back from git's record of
it. Every path is checked against git's records before anything is written or
removed: when either path is a symbolic link, a directory git records no
worktree at, such as a checkout of its own, or a worktree git records as locked,
the run stops and leaves both as they are. A worktree moved without
git worktree move leaves its record at the old path, and a directory made there
later is taken for that worktree and removed; this case is not detected.
--merged-worktree-only makes
pr<n>-merged alone and leaves pr<n>-head as it is, because reviewers may be
reading it.

Git runs in --review-tools-worktree-at-main. Every worktree of one repository shares its
objects, so the fetched nn-head-commit is visible to the new worktrees.

Exit codes: 0 both worktrees made, or pr<n>-merged alone with
--merged-worktree-only; 1 a git step failed, the head conflicts
with main, or a worktree's path is a symbolic link, a directory that is not a
recorded worktree, or a locked worktree, named on stdout.
"""

import argparse
import importlib.util
import subprocess
import sys
from pathlib import Path

MERGE_COMMIT_IDENTITY = ("-c", "user.name=merge-lane-2", "-c", "user.email=noreply@anthropic.com")

_common_spec = importlib.util.spec_from_file_location(
    "merge_lane_pull_request_helpers_common", Path(__file__).resolve().with_name(
        "merge-lane-pull-request-helpers-common-options-paths-and-token.py"))
common = importlib.util.module_from_spec(_common_spec)
_common_spec.loader.exec_module(common)
run_all_test_suites = common.run_all_test_suites
_git_output_spec = importlib.util.spec_from_file_location(
    "git_machine_readable_output_runner_and_parser_common",
    Path(__file__).resolve().parents[1] / "nn-systems" / "general-tools"
    / "git-machine-readable-output-runner-and-parser-common.py")
git_output = importlib.util.module_from_spec(_git_output_spec)
_git_output_spec.loader.exec_module(git_output)


class GitStepFailed(Exception):
    pass


class HeadConflictsWithMain(Exception):
    pass


class WorktreeNotRecorded(Exception):
    pass


class WorktreePathIsSymbolicLink(Exception):
    pass


class WorktreeLocked(Exception):
    pass


def parse_arguments(argv):
    parser = argparse.ArgumentParser(
        description="Make pr<n>-head at a pull request's nn-head-commit and pr<n>-merged "
                    "at that head merged onto main, both detached.")
    parser.add_argument("pull_request", type=int, help="the pull request's number")
    parser.add_argument("head_commit", help="the pull request's nn-head-commit")
    parser.add_argument("main_commit", help="the main commit to merge the nn-head-commit onto")
    parser.add_argument("--merged-worktree-only", action="store_true",
                        help="rebuild pr<n>-merged and leave pr<n>-head as it is")
    common.add_directory_options(parser, "nothing this program uses")
    return common.resolve_path_options(parser.parse_args(argv))


def git(directory, *arguments):
    completed = subprocess.run(
        ["git", "-C", str(directory), *arguments], capture_output=True, text=True,
        stdin=subprocess.DEVNULL,
        env=run_all_test_suites.environment_without_git_redirecting_variables())
    if completed.returncode != 0:
        raise GitStepFailed(f"git {' '.join(arguments)} in {directory} exited "
                            f"{completed.returncode}: {completed.stderr.strip()}")
    return completed.stdout.strip()


def recorded_worktree_lock_reasons(checkout):
    """Map each worktree path git records to its lock reason, None when it is not locked."""
    return {Path(record.path).resolve(): record.locked_reason
            for record in git_output.worktree_records(
                git(checkout, "worktree", "list", "--porcelain", "-z"))}


def recorded_worktree_administrative_directory(checkout, worktree):
    """Return the directory under .git/worktrees that holds git's record of a worktree."""
    common_directory = Path(git(checkout, "rev-parse", "--path-format=absolute",
                                "--git-common-dir"))
    for record in sorted((common_directory / "worktrees").glob("*/gitdir")):
        try:
            recorded = record.read_text().strip()
        except FileNotFoundError:
            # Another review removed its own worktree while this one scanned.
            continue
        # With worktree.useRelativePaths the record is relative to its own directory.
        if (record.parent / recorded).parent.resolve() == worktree.resolve():
            return record.parent
    raise WorktreeNotRecorded(worktree)


def worktree_remove_reporting_what_is_left(checkout, worktree, removed):
    try:
        git(checkout, "worktree", "remove", "--force", str(worktree))
    except GitStepFailed as failure:
        # git can delete its record and part of the directory before it fails.
        still_recorded = worktree.resolve() in recorded_worktree_lock_reasons(checkout)
        raise GitStepFailed(
            f"{failure}. After that failure, {worktree} "
            f"{'still exists' if worktree.exists() else 'is gone'}, and git "
            f"{'still records' if still_recorded else 'no longer records'} a worktree there. "
            + (f"Already removed in this run: {', '.join(map(str, removed))}."
               if removed else "No other worktree was removed in this run.")) from None
    removed.append(worktree)


def main(argv=None):
    arguments = parse_arguments(argv)
    number = arguments.pull_request
    checkout = arguments.review_tools_worktree_at_main
    head_worktree = common.pull_request_head_worktree(arguments, number)
    merged_worktree = common.pull_request_merged_worktree(arguments, number)
    try:
        try:
            git(checkout, "cat-file", "-e", f"{arguments.head_commit}^{{commit}}")
        except GitStepFailed:
            # A review pipeline sharing this checkout reads FETCH_HEAD after its own fetch.
            git(checkout, "fetch", "-q", "--no-write-fetch-head", "origin",
                f"pull/{number}/head")
        rebuilt =((merged_worktree,) if arguments.merged_worktree_only
                   else (head_worktree, merged_worktree))
        # Every path is checked before anything is written or removed, so a refusal
        # changes nothing.
        lock_reasons = recorded_worktree_lock_reasons(checkout)
        removals = []
        for worktree in rebuilt:
            # git worktree remove follows a link to whatever worktree it points at.
            if worktree.is_symlink():
                raise WorktreePathIsSymbolicLink(worktree)
            if not worktree.exists():
                continue
            if worktree.resolve() not in lock_reasons:
                raise WorktreeNotRecorded(worktree)
            if lock_reasons[worktree.resolve()] is not None:
                raise WorktreeLocked(worktree, lock_reasons[worktree.resolve()])
            removals.append((worktree, None if (worktree / ".git").exists()
                             else recorded_worktree_administrative_directory(checkout, worktree)))
        removed = []
        for worktree, administrative_directory in removals:
            if administrative_directory is not None:
                # git worktree remove refuses a worktree whose .git is gone, even with --force.
                (worktree / ".git").write_text(f"gitdir: {administrative_directory}\n")
            worktree_remove_reporting_what_is_left(checkout, worktree, removed)
        if not arguments.merged_worktree_only:
            git(checkout, "worktree", "add", "-q", "--detach", str(head_worktree),
                arguments.head_commit)
        git(checkout, "worktree", "add", "-q", "--detach", str(merged_worktree),
            arguments.main_commit)
        head_full = git(checkout, "rev-parse", "--verify", f"{arguments.head_commit}^{{commit}}")
        try:
            git(merged_worktree, *MERGE_COMMIT_IDENTITY, "merge", "-q", "--no-edit", "--no-ff",
                arguments.head_commit)
        except GitStepFailed:
            conflicted = git_output.nul_separated_fields(
                git(merged_worktree, "diff", "-z", "--name-only", "--diff-filter=U"))
            if not conflicted:
                raise
            git(merged_worktree, "merge", "--abort")
            raise HeadConflictsWithMain(", ".join(conflicted))
        head_short = git(checkout, "rev-parse", "--short", head_full)
        merged_short = git(merged_worktree, "rev-parse", "--short", "HEAD")
        merged_tree = git(merged_worktree, "rev-parse", "HEAD^{tree}")
    except HeadConflictsWithMain as conflict:
        print(f"PR {number}: worktrees not rebuilt: head {arguments.head_commit[:8]} conflicts "
              f"with main {arguments.main_commit[:8]} in: {conflict}\n"
              f"The pull request's author clears a conflict with main, not merge-lane-2 and "
              f"not the user.\n"
              f"Confirm it from {checkout}, which holds the nn-head-commit:\n"
              f"cd {checkout} && python3 scripts/branch-conflict-check.py --head {head_full} "
              f"--pull-request {number}\n"
              f"If that reports VERDICT: CONFLICT, send pull request {number} back to its "
              f"author to do what that report says.\n"
              f"If it reports no conflict, run this again with the current main commit.")
        return 1
    except WorktreeNotRecorded as unrecorded:
        print(f"PR {number}: worktrees not rebuilt: the checkout {checkout} records no worktree "
              f"at {unrecorded.args[0]}, so it may be an ordinary directory or a checkout of "
              f"its own. Nothing was deleted.\n"
              f"Look at what the directory holds. When nothing in it is needed, delete it and "
              f"run this again.\n"
              f"When something in it is needed, or you cannot tell, tell the user this message.")
        return 1
    except WorktreeLocked as locked:
        worktree, reason = locked.args
        print(f"PR {number}: worktrees not rebuilt: git records {worktree} as locked"
              f"{f', with the reason: {reason}' if reason else ', with no reason given'}, so "
              f"neither worktree was removed. Nothing was deleted.\n"
              f"When nothing needs that worktree, unlock it with: git -C {checkout} worktree "
              f"unlock {worktree}\n"
              f"Then run this again.\n"
              f"When something needs it, or you cannot tell, tell the user this message.")
        return 1
    except WorktreePathIsSymbolicLink as link:
        print(f"PR {number}: worktrees not rebuilt: {link.args[0]} is a symbolic link to "
              f"{link.args[0].readlink()}, and removing it as a worktree would remove what it "
              f"points at. Nothing was deleted.\n"
              f"When nothing needs the link, delete the link alone, with rm and no -r, and run "
              f"this again.\n"
              f"When something needs it, or you cannot tell, tell the user this message.")
        return 1
    except GitStepFailed as failure:
        print(f"PR {number}: worktrees not rebuilt: {failure}\n"
              f"If the git error above names a cause you can fix, such as a wrong commit, fix "
              f"it and run this again.\n"
              f"Otherwise, tell the user this message.")
        return 1
    print(f"PR {number}: head {head_short}, merged {merged_short} tree {merged_tree} "
          f"on main {arguments.main_commit[:8]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
