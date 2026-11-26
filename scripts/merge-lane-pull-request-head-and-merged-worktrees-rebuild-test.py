#!/usr/bin/env python3
"""Tests for merge-lane-pull-request-head-and-merged-worktrees-rebuild.py.

Runs the program against real git in a scratch directory: a bare origin
holding main and a pull request's head at refs/pull/7/head, as GitHub keeps
it, and a clone of that origin as the checkout git runs in. The program runs
with GIT_DIR pointing at a directory that does not exist, so a case passes
only if the program drops the variables that redirect git, and with no
identity in its environment or a global git config, so the merge commit's
author comes from the program alone.

Run: python3 scripts/merge-lane-pull-request-head-and-merged-worktrees-rebuild-test.py
"""

import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

_git_environment_fixture_spec = importlib.util.spec_from_file_location(
    "git_redirecting_environment_removal_test_fixture",
    Path(__file__).resolve().with_name(
        "git-redirecting-environment-removal-test-fixture.py"))
_git_environment_fixture = importlib.util.module_from_spec(_git_environment_fixture_spec)
_git_environment_fixture_spec.loader.exec_module(_git_environment_fixture)
_git_environment_fixture.remove_git_redirecting_environment_variables_from_this_process()

PROGRAM = Path(__file__).with_name("merge-lane-pull-request-head-and-merged-worktrees-rebuild.py")
BRANCH_CONFLICT_CHECK = Path(__file__).resolve().with_name("branch-conflict-check.py")
FAILING_GH = "#!/bin/sh\necho 'gh is not available in this test' >&2\nexit 1\n"
GIT_ENVIRONMENT = {
    **{key: value for key, value in os.environ.items() if not key.startswith("GIT_")},
    "GIT_AUTHOR_NAME": "test", "GIT_AUTHOR_EMAIL": "test@example.invalid",
    "GIT_COMMITTER_NAME": "test", "GIT_COMMITTER_EMAIL": "test@example.invalid",
    "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1",
}

failures = []


def review_worktrees_directory(helpers):
    return helpers.parent / f"{helpers.name}-review-worktrees"


def check(name, condition, detail=""):
    print(("PASS  " if condition else "FAIL  ") + name)
    if not condition:
        failures.append(name)
        if detail:
            print("      " + detail.replace("\n", "\n      "))


def git(directory, *arguments):
    return subprocess.run(["git", "-C", str(directory), *arguments], capture_output=True,
                          text=True, check=True, env=GIT_ENVIRONMENT).stdout.strip()


def build_repositories(scratch):
    """Return (checkout, main commit, nn-head-commit)."""
    origin = scratch / "origin.git"
    author = scratch / "author"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(origin)], check=True,
                   env=GIT_ENVIRONMENT)
    subprocess.run(["git", "init", "-q", "-b", "main", str(author)], check=True,
                   env=GIT_ENVIRONMENT)
    (author / "on-main.txt").write_text("main\n")
    git(author, "add", ".")
    git(author, "commit", "-q", "-m", "main")
    main_commit = git(author, "rev-parse", "HEAD")
    git(author, "checkout", "-q", "-b", "topic")
    (author / "on-topic.txt").write_text("topic\n")
    git(author, "add", ".")
    git(author, "commit", "-q", "-m", "topic")
    head_commit = git(author, "rev-parse", "HEAD")
    git(author, "push", "-q", str(origin), "main:refs/heads/main",
        "topic:refs/pull/7/head")
    checkout = scratch / "checkout"
    subprocess.run(["git", "clone", "-q", str(origin), str(checkout)], check=True,
                   env=GIT_ENVIRONMENT)
    return checkout, main_commit, head_commit


def run_program(helpers, checkout, *arguments, cwd=None):
    return subprocess.run(
        [sys.executable, str(PROGRAM), *arguments, "--merge-lane-worktrees-and-outputs-directory", str(helpers),
         "--merge-lane-review-worktrees-directory", str(review_worktrees_directory(helpers)),
         "--review-tools-worktree-at-main", str(checkout)],
        capture_output=True, text=True, cwd=cwd,
        env={**{key: value for key, value in GIT_ENVIRONMENT.items()
                if not key.startswith(("GIT_AUTHOR_", "GIT_COMMITTER_"))},
             "GIT_DIR": str(helpers / "no-such-git-directory")})


def run_printed_conflict_check(output, scratch):
    """Run the branch-conflict-check command the refusal printed, as printed.

    Only the script's path is swapped for this checkout's copy, because the
    fixture checkout holds no scripts/. gh fails, so the verdict is git's.
    """
    lines = [line for line in output.splitlines() if "branch-conflict-check.py" in line
             and line.startswith("cd ")]
    if len(lines) != 1:
        return None
    command = lines[0].replace("python3 scripts/branch-conflict-check.py",
                               f"{sys.executable} {BRANCH_CONFLICT_CHECK}")
    bin_directory = scratch / "failing-gh-bin"
    bin_directory.mkdir(exist_ok=True)
    (bin_directory / "gh").write_text(FAILING_GH)
    (bin_directory / "gh").chmod(0o755)
    return subprocess.run(
        ["bash", "-c", command], capture_output=True, text=True,
        env={**GIT_ENVIRONMENT, "PATH": f"{bin_directory}{os.pathsep}{os.environ['PATH']}"})


def main():
    scratch = Path(tempfile.mkdtemp(prefix="merge-lane-worktrees-rebuild-test-")).resolve()
    try:
        checkout, main_commit, head_commit = build_repositories(scratch)
        helpers = scratch / "merge-helpers"
        head_worktree = review_worktrees_directory(helpers) / "pr7-head"
        merged_worktree = review_worktrees_directory(helpers) / "pr7-merged"

        completed = run_program(helpers, checkout, "7", head_commit, main_commit)
        detail = f"exit {completed.returncode}\n{completed.stdout}{completed.stderr}"
        check("both worktrees are made, exit 0", completed.returncode == 0
              and head_worktree.is_dir() and merged_worktree.is_dir(), detail)
        if completed.returncode == 0:
            check("pr<n>-head is at the nn-head-commit",
                  git(head_worktree, "rev-parse", "HEAD") == head_commit, detail)
            check("pr<n>-head is detached",
                  git(head_worktree, "rev-parse", "--abbrev-ref", "HEAD") == "HEAD", detail)
            parents = git(merged_worktree, "rev-list", "--parents", "-n", "1", "HEAD").split()[1:]
            check("pr<n>-merged is a merge commit of main and the nn-head-commit",
                  parents == [main_commit, head_commit], repr(parents))
            check("the merge commit is made as merge-lane-2",
                  git(merged_worktree, "log", "-1", "--format=%an") == "merge-lane-2", detail)
            merged_tree = git(merged_worktree, "rev-parse", "HEAD^{tree}")
            check("the output names the head, the merge commit, its tree and main",
                  completed.stdout.strip() == (
                      f"PR 7: head {head_commit[:7]}, merged "
                      f"{git(merged_worktree, 'rev-parse', '--short', 'HEAD')} tree "
                      f"{merged_tree} on main {main_commit[:8]}"), completed.stdout)

            (head_worktree / "left-behind.txt").write_text("a change in the old worktree\n")
            completed = run_program(helpers, checkout, "7", head_commit, main_commit)
            check("running again replaces both worktrees, dropping changes in them",
                  completed.returncode == 0
                  and not (head_worktree / "left-behind.txt").exists()
                  and git(head_worktree, "rev-parse", "HEAD") == head_commit,
                  f"exit {completed.returncode}\n{completed.stdout}{completed.stderr}")

            (head_worktree / ".git").unlink()
            (head_worktree / "left-behind.txt").write_text("a change in the damaged worktree\n")
            completed = run_program(helpers, checkout, "7", head_commit, main_commit)
            check("a pr<n>-head that lost its .git is deleted and made again, exit 0",
                  completed.returncode == 0
                  and not (head_worktree / "left-behind.txt").exists()
                  and git(head_worktree, "rev-parse", "HEAD") == head_commit,
                  f"exit {completed.returncode}\n{completed.stdout}{completed.stderr}")

            moved_away = scratch / "moved-away-worktree"
            git(checkout, "worktree", "add", "-q", "--detach", str(scratch / "elsewhere"),
                main_commit)
            (scratch / "elsewhere").rename(moved_away)
            (head_worktree / ".git").unlink()
            completed = run_program(helpers, checkout, "7", head_commit, main_commit)
            check("rebuilding a pr<n>-head that lost its .git leaves git's record of another "
                  "worktree, moved and not yet repaired, in place",
                  completed.returncode == 0
                  and str(scratch / "elsewhere") in git(checkout, "worktree", "list",
                                                        "--porcelain"),
                  f"exit {completed.returncode}\n{completed.stdout}{completed.stderr}\n"
                  + git(checkout, "worktree", "list", "--porcelain"))

            git(checkout, "worktree", "lock", "--reason", "a reviewer is reading it",
                str(head_worktree))
            (head_worktree / ".git").unlink()
            (head_worktree / "kept.txt").write_text("in a locked worktree\n")
            completed = run_program(helpers, checkout, "7", head_commit, main_commit)
            check("a locked pr<n>-head that lost its .git is left with its files and no .git "
                  "written into it, exit 1 naming the lock and its reason",
                  completed.returncode == 1 and (head_worktree / "kept.txt").exists()
                  and not (head_worktree / ".git").exists()
                  and "as locked, with the reason: a reviewer is reading it" in completed.stdout
                  and "Nothing was deleted" in completed.stdout,
                  f"exit {completed.returncode}\n{completed.stdout}{completed.stderr}")
            git(checkout, "worktree", "unlock", str(head_worktree))
            shutil.rmtree(head_worktree)
            git(checkout, "worktree", "prune")

            head_worktree.mkdir()
            (head_worktree / "not-a-worktree.txt").write_text("an ordinary directory\n")
            completed = run_program(helpers, checkout, "7", head_commit, main_commit)
            check("an ordinary directory at pr<n>-head's path is left with its files, exit 1 "
                  "saying git records no worktree there and nothing was deleted",
                  completed.returncode == 1
                  and (head_worktree / "not-a-worktree.txt").exists()
                  and f"records no worktree at {head_worktree}" in completed.stdout
                  and "Nothing was deleted" in completed.stdout,
                  f"exit {completed.returncode}\n{completed.stdout}{completed.stderr}")
            shutil.rmtree(head_worktree)

            git(checkout, "worktree", "add", "-q", "--detach", str(head_worktree), head_commit)
            (head_worktree / "left-behind.txt").write_text("a change in the recorded pr<n>-head\n")
            git(checkout, "worktree", "remove", "--force", str(merged_worktree))
            merged_worktree.mkdir()
            (merged_worktree / "not-a-worktree.txt").write_text("an ordinary directory\n")
            completed = run_program(helpers, checkout, "7", head_commit, main_commit)
            check("a recorded pr<n>-head is kept, with its changes, when pr<n>-merged is a "
                  "directory git records no worktree at, exit 1 saying nothing was deleted",
                  completed.returncode == 1
                  and (head_worktree / "left-behind.txt").exists()
                  and (merged_worktree / "not-a-worktree.txt").exists()
                  and "Nothing was deleted" in completed.stdout,
                  f"exit {completed.returncode}\n{completed.stdout}{completed.stderr}")
            shutil.rmtree(merged_worktree)

            other_worktree = scratch / "other-worktree"
            git(checkout, "worktree", "add", "-q", "--detach", str(other_worktree), main_commit)
            (other_worktree / ".git").unlink()
            (other_worktree / "kept.txt").write_text("another worktree's file\n")
            git(checkout, "worktree", "remove", "--force", str(head_worktree))
            head_worktree.symlink_to(other_worktree)
            completed = run_program(helpers, checkout, "7", head_commit, main_commit)
            check("a pr<n>-head that is a symbolic link to another worktree that lost its .git "
                  "leaves that worktree and its record, exit 1 naming the link",
                  completed.returncode == 1
                  and (other_worktree / "kept.txt").exists()
                  and not (other_worktree / ".git").exists()
                  and str(other_worktree) in git(checkout, "worktree", "list", "--porcelain")
                  and "symbolic link" in completed.stdout
                  and "Nothing was deleted" in completed.stdout,
                  f"exit {completed.returncode}\n{completed.stdout}{completed.stderr}")
            head_worktree.unlink()

            def rebuilt_fresh():
                completed = run_program(helpers, checkout, "7", head_commit, main_commit)
                if completed.returncode != 0:
                    raise AssertionError(f"setup rebuild failed: {completed.stdout}")

            rebuilt_fresh()
            (head_worktree / "left.txt").write_text("a change in a healthy pr<n>-head\n")
            git(checkout, "worktree", "lock", str(merged_worktree))
            completed = run_program(helpers, checkout, "7", head_commit, main_commit)
            check("a healthy pr<n>-head keeps its changes when pr<n>-merged is locked, exit 1 "
                  "naming the lock and saying nothing was deleted",
                  completed.returncode == 1 and (head_worktree / "left.txt").exists()
                  and f"git records {merged_worktree} as locked, with no reason given"
                  in completed.stdout and "Nothing was deleted" in completed.stdout,
                  f"exit {completed.returncode}\n{completed.stdout}{completed.stderr}")
            git(checkout, "worktree", "unlock", str(merged_worktree))

            git(checkout, "worktree", "remove", "--force", str(merged_worktree))
            subprocess.run(["git", "init", "-q", str(merged_worktree)], check=True,
                           env=GIT_ENVIRONMENT)
            completed = run_program(helpers, checkout, "7", head_commit, main_commit)
            check("a healthy pr<n>-head keeps its changes when pr<n>-merged is a checkout of its "
                  "own, exit 1 saying git records no worktree there",
                  completed.returncode == 1 and (head_worktree / "left.txt").exists()
                  and (merged_worktree / ".git").is_dir()
                  and f"records no worktree at {merged_worktree}" in completed.stdout,
                  f"exit {completed.returncode}\n{completed.stdout}{completed.stderr}")
            shutil.rmtree(merged_worktree)

            rebuilt_fresh()
            git(checkout, "worktree", "lock", str(head_worktree))
            (merged_worktree / ".git").unlink()
            completed = run_program(helpers, checkout, "7", head_commit, main_commit)
            check("a locked pr<n>-head stops the run before pr<n>-merged, which lost its .git, "
                  "has one written into it",
                  completed.returncode == 1 and not (merged_worktree / ".git").exists()
                  and f"git records {head_worktree} as locked" in completed.stdout,
                  f"exit {completed.returncode}\n{completed.stdout}{completed.stderr}")
            git(checkout, "worktree", "unlock", str(head_worktree))
            shutil.rmtree(merged_worktree)
            git(checkout, "worktree", "prune")

            rebuilt_fresh()
            common_directory = Path(git(checkout, "rev-parse", "--path-format=absolute",
                                        "--git-common-dir"))
            # A gitdir record read after its worktree's removal: a link to nothing reads as gone.
            vanished = common_directory / "worktrees" / "0-vanished-during-the-scan"
            vanished.mkdir()
            (vanished / "gitdir").symlink_to(scratch / "no-such-gitdir-record")
            (head_worktree / ".git").unlink()
            completed = run_program(helpers, checkout, "7", head_commit, main_commit)
            check("a gitdir record that vanishes during the scan is skipped, and pr<n>-head, "
                  "which lost its .git, is made again, exit 0",
                  completed.returncode == 0
                  and git(head_worktree, "rev-parse", "HEAD") == head_commit,
                  f"exit {completed.returncode}\n{completed.stdout}{completed.stderr}")
            shutil.rmtree(vanished)

            head_record = next(record for record in (common_directory / "worktrees").glob(
                "*/gitdir") if Path(record.read_text().strip()).parent == head_worktree)
            head_record.write_text(os.path.relpath(head_worktree / ".git", head_record.parent)
                                   + "\n")
            (head_worktree / ".git").unlink()
            completed = run_program(helpers, checkout, "7", head_commit, main_commit)
            check("a pr<n>-head that lost its .git, whose gitdir record is relative to the "
                  "record's directory, is found and made again, exit 0",
                  completed.returncode == 0
                  and git(head_worktree, "rev-parse", "HEAD") == head_commit,
                  f"exit {completed.returncode}\n{completed.stdout}{completed.stderr}")

            unwritable = head_worktree / "unwritable"
            unwritable.mkdir()
            (unwritable / "stuck.txt").write_text("git cannot delete this\n")
            unwritable.chmod(0o500)
            try:
                completed = run_program(helpers, checkout, "7", head_commit, main_commit)
            finally:
                unwritable.chmod(0o700)
            check("a removal that fails part way says what is left of the directory and of "
                  "git's record, exit 1",
                  completed.returncode == 1
                  and f"After that failure, {head_worktree} still exists, and git no longer "
                      f"records a worktree there." in completed.stdout
                  and "No other worktree was removed in this run." in completed.stdout,
                  f"exit {completed.returncode}\n{completed.stdout}{completed.stderr}")
            shutil.rmtree(head_worktree)
            git(checkout, "worktree", "prune")
            rebuilt_fresh()

        relative_helpers = scratch / "relative-helpers"
        completed = run_program(Path("relative-helpers"), Path("checkout"), "7", head_commit,
                                main_commit, cwd=scratch)
        check("relative directory options make the worktrees under the caller's directory, "
              "not under the checkout git runs in",
              completed.returncode == 0
              and (review_worktrees_directory(relative_helpers) / "pr7-head").is_dir()
              and (review_worktrees_directory(relative_helpers) / "pr7-merged").is_dir()
              and not (checkout / "relative-helpers").exists(),
              f"exit {completed.returncode}\n{completed.stdout}{completed.stderr}")

        completed = run_program(helpers, checkout, "7", "0" * 40, main_commit)
        check("an nn-head-commit git cannot find exits 1 and names the failed step",
              completed.returncode == 1 and "worktrees not rebuilt" in completed.stdout
              and "worktree add" in completed.stdout,
              f"exit {completed.returncode}\n{completed.stdout}{completed.stderr}")

        author = scratch / "author"
        git(author, "checkout", "-q", "-b", "conflicting", main_commit)
        (author / "on-main.txt").write_text("the pull request's line\n")
        (author / "côté notes.md").write_text("the pull request's notes\n")
        git(author, "add", "-A")
        git(author, "commit", "-q", "-m", "pull request 9 changes on-main.txt")
        conflicting_head = git(author, "rev-parse", "HEAD")
        git(author, "checkout", "-q", "main")
        (author / "on-main.txt").write_text("main's later line\n")
        (author / "côté notes.md").write_text("main's notes\n")
        git(author, "add", "-A")
        git(author, "commit", "-q", "-m", "main changes on-main.txt")
        later_main = git(author, "rev-parse", "HEAD")
        git(author, "push", "-q", str(scratch / "origin.git"), "main:refs/heads/main",
            "conflicting:refs/pull/9/head")
        git(checkout, "fetch", "-q", "origin")
        completed = run_program(helpers, checkout, "9", conflicting_head, later_main)
        check("a head that conflicts with main exits 1, names each file as stored, a "
              "non-ASCII name with a space included, and sends the pull request back to its author",
              completed.returncode == 1 and "conflicts with main" in completed.stdout
              and "in: côté notes.md, on-main.txt\n" in completed.stdout
              and f"branch-conflict-check.py --head {conflicting_head} --pull-request 9"
              in completed.stdout
              and "back to its author" in completed.stdout,
              f"exit {completed.returncode}\n{completed.stdout}{completed.stderr}")
        confirmed = run_printed_conflict_check(completed.stdout, scratch)
        check("the printed branch-conflict-check command, run as printed, reports the conflict",
              confirmed is not None and confirmed.returncode != 0
              and "VERDICT: CONFLICT" in confirmed.stdout,
              "no single printed command" if confirmed is None else
              f"exit {confirmed.returncode}\n{confirmed.stdout}{confirmed.stderr}")
        check("the conflicted merge is aborted, leaving pr<n>-merged clean at main",
              git(review_worktrees_directory(helpers) / "pr9-merged", "status", "--porcelain") == ""
              and git(review_worktrees_directory(helpers) / "pr9-merged", "rev-parse", "HEAD") == later_main,
              git(review_worktrees_directory(helpers) / "pr9-merged", "status", "--porcelain"))

        git(author, "checkout", "-q", "--orphan", "unrelated")
        git(author, "rm", "-q", "-rf", ".")
        (author / "unrelated.txt").write_text("no shared history\n")
        git(author, "add", ".")
        git(author, "commit", "-q", "-m", "pull request 10 shares no history with main")
        unrelated_head = git(author, "rev-parse", "HEAD")
        git(author, "push", "-q", str(scratch / "origin.git"), "unrelated:refs/pull/10/head")
        completed = run_program(helpers, checkout, "10", unrelated_head, later_main)
        check("a merge that fails without a conflict exits 1 and reports the failed merge, "
              "not a failed abort",
              completed.returncode == 1 and "worktrees not rebuilt" in completed.stdout
              and "unrelated histories" in completed.stdout
              and "--abort" not in completed.stdout
              and "conflicts with main" not in completed.stdout,
              f"exit {completed.returncode}\n{completed.stdout}{completed.stderr}")

        completed = run_program(helpers, checkout, "8", head_commit, main_commit)
        check("a head commit already local is used with no fetch, even when origin no longer "
              "has the pull request's ref",
              completed.returncode == 0
              and git(review_worktrees_directory(helpers) / "pr8-merged", "rev-parse", "HEAD^2")
              == head_commit,
              f"exit {completed.returncode}\n{completed.stdout}{completed.stderr}")

        (author / "never-pushed.txt").write_text("only in the author's clone\n")
        git(author, "add", "never-pushed.txt")
        git(author, "commit", "-q", "-m", "a commit origin does not have")
        unpushed_commit = git(author, "rev-parse", "HEAD")
        completed = run_program(helpers, checkout, "12", unpushed_commit, main_commit)
        check("a head commit not local, of a pull request origin does not have, exits 1 at the "
              "fetch",
              completed.returncode == 1 and "git fetch" in completed.stdout,
              f"exit {completed.returncode}\n{completed.stdout}{completed.stderr}")
    finally:
        shutil.rmtree(scratch, ignore_errors=True)

    if failures:
        print(f"\n{len(failures)} case(s) failed")
        return 1
    print("\nall cases passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
