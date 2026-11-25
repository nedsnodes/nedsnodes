#!/usr/bin/env python3
"""Run main's code-review-codex-cell.py on a pull request's pr<n>-head worktree.

Usage:
  scripts/merge-lane-code-review-codex-cell-run-on-pull-request-head.py <pull request number>
      <base commit> [--expected-head-commit COMMIT] [--merge-lane-worktrees-and-outputs-directory DIR] [--merge-lane-review-worktrees-directory DIR] [--review-tools-worktree-at-main DIR]

The base commit is the merge base for a first review, or the nn-head-commit
reviewed before for a fix-round, unless that fix-round merged main or rewrote
history, when it is the merge base again. Saves the pull request's description from
GitHub to
cx/pr<n>-<first 8 characters of the base>/pull-request-description.md under
the worktrees and outputs directory, then runs
--review-tools-worktree-at-main's scripts/code-review-codex-cell.py, not the
pull request's, on pr<n>-head from the base commit, with
--review-tools-worktree-at-main's docs/agents/pr-reviewer-instructions.md as
the rules the review applies, so a pull request cannot change the rules its
own review is held to. The report, codex-code-review-report.md, and stdout
and stderr go to the same directory.
The same directory also gets codex-review-run-record.json, holding
"pull_request", "head_commit", "base_commit", "exit_code" and "report_file".
It is removed before the run and written after it, so a run that was killed
leaves none; a run refused because pr<n>-head's commit could not be read or is
not --expected-head-commit leaves the earlier record as it was. A second run for the same pull request and base always replaces
the first run's record, so after a rerun that fails the posting program no
longer sees the first run's findings and asks no grade for them; it replaces
the report only when Codex ran, so a rerun stopped before Codex starts, by a
missing review tool or an unreadable token, leaves the earlier report beside
a record that names the failed run.
With --expected-head-commit, the run refuses before the review when pr<n>-head
holds another commit, since the review would record the wrong one.
merge-lane-pull-request-reviewer-review-post-and-read-back.py
reads it to tell a Codex run that found nothing from one that failed.
gh reads the description with the merge account's token, the one file every
merge-lane helper and merge-gate.sh read.

Exit codes: the review's exit code; 2 when the token, the description,
--review-tools-worktree-at-main's scripts/code-review-codex-cell.py or its
docs/agents/pr-reviewer-instructions.md could not be read, before the review
runs, or when the pull request's head commit could not be read or is not
--expected-head-commit, or the run record could not be removed or written.
"""

import argparse
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

CODEX_CELL = Path("scripts") / "code-review-codex-cell.py"
PULL_REQUEST_REVIEWER_INSTRUCTIONS = Path("docs") / "agents" / "pr-reviewer-instructions.md"

_common_spec = importlib.util.spec_from_file_location(
    "merge_lane_pull_request_helpers_common", Path(__file__).resolve().with_name(
        "merge-lane-pull-request-helpers-common-options-paths-and-token.py"))
common = importlib.util.module_from_spec(_common_spec)
_common_spec.loader.exec_module(common)
run_all_test_suites = common.run_all_test_suites
REPOSITORY = common.REPOSITORY


def parse_arguments(argv):
    parser = argparse.ArgumentParser(
        description="Run main's code-review-codex-cell.py on pr<n>-head from a base "
                    "commit, with the pull request's description.")
    parser.add_argument("pull_request", type=int, help="the pull request's number")
    parser.add_argument("base_commit",
                        help="the merge base, or for a fix-round that neither merged main nor "
                             "rewrote history, the nn-head-commit reviewed before")
    parser.add_argument("--expected-head-commit",
                        help="refuse unless pr<n>-head holds this commit")
    common.add_directory_options(parser, "cx/")
    return common.resolve_path_options(parser.parse_args(argv))


def main(argv=None):
    arguments = parse_arguments(argv)
    number, base = arguments.pull_request, arguments.base_commit
    outputs = arguments.merge_lane_worktrees_and_outputs_directory / "cx" / f"pr{number}-{base[:8]}"
    outputs.mkdir(parents=True, exist_ok=True)
    environment = run_all_test_suites.environment_without_git_redirecting_variables()
    record = outputs / common.CODEX_REVIEW_RUN_RECORD_FILE_NAME
    head = subprocess.run(
        ["git", "-C", str(common.pull_request_head_worktree(arguments, number)), "rev-parse",
         "--verify", "HEAD^{commit}"],
        capture_output=True, text=True, env=environment, stdin=subprocess.DEVNULL)
    if head.returncode != 0:
        print(f"PR {number}: Codex review not run: could not read the head commit of "
              f"{common.pull_request_head_worktree(arguments, number)}: {head.stderr.strip()}\n"
              f"Rebuild the pull request's worktrees, then run this again.")
        return 2
    if arguments.expected_head_commit and head.stdout.strip() != arguments.expected_head_commit:
        print(f"PR {number}: Codex review not run: "
              f"{common.pull_request_head_worktree(arguments, number)} holds commit "
              f"{head.stdout.strip()}, not {arguments.expected_head_commit}, so the review would "
              f"record the wrong commit.\nRebuild the pull request's worktrees at "
              f"{arguments.expected_head_commit}, then run this again.")
        return 2
    try:
        record.unlink(missing_ok=True)
    except OSError as error:
        print(f"PR {number}: Codex review not run: could not remove the earlier run record "
              f"{record}: {error}\nFix the cause, then run this again.")
        return 2
    exit_code = codex_review_exit_code(arguments, outputs, environment)
    temporary = record.with_name(f"{record.name}.{os.getpid()}.tmp")
    try:
        temporary.write_text(json.dumps({
            "pull_request": number, "head_commit": head.stdout.strip(), "base_commit": base,
            "exit_code": exit_code,
            "report_file": str(outputs / "codex-code-review-report.md")}) + "\n")
        os.replace(temporary, record)
    except OSError as error:
        temporary.unlink(missing_ok=True)
        print(f"PR {number}: the Codex review exited {exit_code}, but its run record {record} "
              f"could not be written: {error}\nFix the cause, then run this again, because the "
              f"review cannot be posted without the record.")
        return 2
    return exit_code


def codex_review_exit_code(arguments, outputs, environment):
    number, base = arguments.pull_request, arguments.base_commit
    review_tools_worktree = arguments.review_tools_worktree_at_main

    missing = (common.review_tool_missing_message(arguments, CODEX_CELL)
               or common.review_tool_missing_message(arguments, PULL_REQUEST_REVIEWER_INSTRUCTIONS))
    if missing:
        print(f"PR {number}: Codex review not run: {missing}")
        return 2
    try:
        environment["GH_TOKEN"] = common.read_merge_account_token()
    except common.MergeAccountTokenUnusable as unusable:
        print(f"PR {number}: Codex review not run: {unusable}.\n"
              f"Tell the user this message: only the user can restore the token.")
        return 2
    description = subprocess.run(
        ["gh", "pr", "view", str(number), "--repo", REPOSITORY, "--json", "body",
         "--jq", ".body"], capture_output=True, text=True, env=environment,
        stdin=subprocess.DEVNULL)
    if description.returncode != 0:
        print(f"PR {number}: Codex review not run: could not read the pull request's "
              f"description: {description.stderr.strip()}\n"
              f"Run this again once; if it fails the same way, tell the user this message.")
        return 2
    (outputs / "pull-request-description.md").write_text(description.stdout)
    del environment["GH_TOKEN"]

    with open(outputs / "stdout", "w") as stdout, open(outputs / "stderr", "w") as stderr:
        review = subprocess.run(
            [sys.executable, str(review_tools_worktree / CODEX_CELL),
             "--base", base, "--repo", str(common.pull_request_head_worktree(arguments, number)),
             "--instructions-file",
             str(review_tools_worktree / PULL_REQUEST_REVIEWER_INSTRUCTIONS),
             "--pull-request-description-file", str(outputs / "pull-request-description.md"),
             "--output", str(outputs / "codex-code-review-report.md")],
            env=environment, stdin=subprocess.DEVNULL, stdout=stdout, stderr=stderr)
    print(f"PR {number} codex cell (base {base[:8]}) exit {review.returncode}; "
          f"report {outputs / 'codex-code-review-report.md'}")
    return review.returncode


if __name__ == "__main__":
    sys.exit(main())
