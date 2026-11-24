#!/usr/bin/env python3
"""Rebuild a pull request's two detached worktrees under the review worktrees directory.

Usage:
  scripts/merge-lane-pull-request-head-and-merged-worktrees-rebuild.py <pull request number>
      <nn-head-commit> <main commit> [--merged-worktree-only] [--merge-lane-worktrees-and-outputs-directory DIR] [--merge-lane-review-worktrees-directory DIR] [--review-tools-worktree-at-main DIR]

Fetches the pull request's head from origin unless the nn-head-commit is already
local, then makes pr<n>-head at the nn-head-commit and pr<n>-merged at the main commit with the nn-head-commit merged
in, as merge-lane-2, always with a merge commit. A worktree already at either
path is removed first, with any changes in it. --merged-worktree-only makes
pr<n>-merged alone and leaves pr<n>-head as it is, because reviewers may be
reading it. Its last line of output, on success, gives the full hash of the merged commit
it built. Another run can rebuild the same pr<n>-merged at any moment, so it exits 1 when the
commit it reads back is not main merged with the nn-head-commit.

Git runs in --review-tools-worktree-at-main. Every worktree of one repository shares its
objects, so the fetched nn-head-commit is visible to the new worktrees.

Exit codes: 0 both worktrees made, or pr<n>-merged alone with
--merged-worktree-only; 1 a git step failed, or the head conflicts
with main, named on stdout.
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


def commit_is_main_merged_with_head(checkout, commit, main_full, head_full):
    parents = git(checkout, "rev-list", "--parents", "-n", "1", commit).split()[1:]
    if parents == [main_full, head_full]:
        return True
    # A head main already holds merges to main itself, with no new commit.
    return commit == main_full and git(checkout, "merge-base", head_full, main_full) == head_full


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
        for worktree in rebuilt:
            if worktree.exists():
                git(checkout, "worktree", "remove", "--force", str(worktree))
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
        merged_full = git(merged_worktree, "rev-parse", "--verify", "HEAD^{commit}")
        main_full = git(checkout, "rev-parse", "--verify", f"{arguments.main_commit}^{{commit}}")
        if not commit_is_main_merged_with_head(checkout, merged_full, main_full, head_full):
            print(f"PR {number}: pr{number}-merged not usable: {merged_worktree} is at "
                  f"{merged_full}, which is not main {main_full} merged with head {head_full}, "
                  f"so another run rebuilt it while this one did, and a test run there would "
                  f"test that run's commit.\n"
                  f"Run `pgrep -af merge-lane-pull-request-head-test-run-on-merged-worktree.py`.\n"
                  f"While that pgrep command lists a process with the pull request argument "
                  f"{number}, repeat the pgrep command once a minute, for at most 2 hours.\n"
                  f"If it still lists one after 2 hours, tell the user that process's line, "
                  f"because it may be hung; a subagent tells the agent that dispatched it.\n"
                  f"When it lists none, run the command you first typed again, with the same "
                  f"options, whether that was the head test run or this rebuild program; it "
                  f"rebuilds pr{number}-merged.")
            return 1
        merged_short = git(checkout, "rev-parse", "--short", merged_full)
        merged_tree = git(checkout, "rev-parse", f"{merged_full}^{{tree}}")
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
    except GitStepFailed as failure:
        print(f"PR {number}: worktrees not rebuilt: {failure}\n"
              f"If the git error above names a cause you can fix, such as a wrong commit, fix "
              f"it and run this again.\n"
              f"Otherwise, tell the user this message.")
        return 1
    print(f"PR {number}: head {head_short}, merged {merged_short} tree {merged_tree} "
          f"on main {arguments.main_commit[:8]}\n"
          f"{common.MERGE_LANE_REBUILT_MERGED_WORKTREE_COMMIT_LINE_PREFIX}{merged_full}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
