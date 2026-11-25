#!/usr/bin/env python3
"""Tests for merge-lane-code-review-codex-cell-run-on-pull-request-head.py.

A fake `gh` first on PATH logs its arguments and the GH_TOKEN it saw and
prints a description, or fails when the case says so. A scratch --review-tools-worktree-at-main
holds docs/agents/pr-reviewer-instructions.md and a fake
scripts/code-review-codex-cell.py that logs its arguments and
whether GIT_DIR or GH_TOKEN reached it, writes a report, and exits with the
case's code. The program runs with GIT_DIR set.

Run: python3 scripts/merge-lane-code-review-codex-cell-run-on-pull-request-head-test.py
"""

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

_git_environment_fixture_spec = importlib.util.spec_from_file_location(
    "git_redirecting_environment_removal_test_fixture",
    Path(__file__).resolve().with_name("git-redirecting-environment-removal-test-fixture.py"))
_git_environment_fixture = importlib.util.module_from_spec(_git_environment_fixture_spec)
_git_environment_fixture_spec.loader.exec_module(_git_environment_fixture)
_git_environment_fixture.remove_git_redirecting_environment_variables_from_this_process()

PROGRAM = Path(__file__).with_name(
    "merge-lane-code-review-codex-cell-run-on-pull-request-head.py")
TOKEN = "merge-lane-codex-test-token-not-a-credential"
BASE = "0123456789abcdef0123456789abcdef01234567"
DESCRIPTION = "The pull request's description.\n"

FAKE_GH = r'''#!/usr/bin/env python3
import json, os, sys
with open(os.environ["MERGE_LANE_CODEX_TEST_GH_LOG"], "a") as log:
    log.write(json.dumps({"argv": sys.argv[1:], "gh_token": os.environ.get("GH_TOKEN")}) + "\n")
if os.environ.get("MERGE_LANE_CODEX_TEST_GH_FAILS"):
    sys.stderr.write("HTTP 404: Not Found\n")
    sys.exit(1)
sys.stdout.write(os.environ["MERGE_LANE_CODEX_TEST_DESCRIPTION"])
'''

FAKE_CODEX_CELL = r'''#!/usr/bin/env python3
import json, os, sys
argv = sys.argv[1:]
with open(os.environ["MERGE_LANE_CODEX_TEST_CELL_LOG"], "a") as log:
    log.write(json.dumps({"argv": argv, "git_dir": os.environ.get("GIT_DIR"),
                          "gh_token": os.environ.get("GH_TOKEN")}) + "\n")
open(argv[argv.index("--output") + 1], "w").write("the report\n")
if os.environ.get("MERGE_LANE_CODEX_TEST_CELL_MOVES_HEAD"):
    import subprocess
    subprocess.run(["git", "-C", argv[argv.index("--repo") + 1], "-c", "user.name=t", "-c",
                    "user.email=t@example.invalid", "commit", "-q", "--allow-empty", "-m", "moved"],
                   check=True, env={k: v for k, v in os.environ.items() if k != "GIT_DIR"})
if os.environ.get("MERGE_LANE_CODEX_TEST_CELL_BREAKS_HEAD"):
    repo = argv[argv.index("--repo") + 1]
    os.rename(os.path.join(repo, ".git"), os.path.join(repo, ".git-away"))
print("cell stdout")
print("cell stderr", file=sys.stderr)
sys.exit(int(os.environ.get("MERGE_LANE_CODEX_TEST_CELL_EXIT", "0")))
'''

failures = []


def review_worktrees_directory(helpers):
    return helpers.parent / f"{helpers.name}-review-worktrees"


def check(name, condition, detail=""):
    print(("PASS  " if condition else "FAIL  ") + name)
    if not condition:
        failures.append(name)
        if detail:
            print("      " + detail.replace("\n", "\n      "))


def read_log(path):
    return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []


def run_program(scratch, helpers, extra_environment=None, home=None, extra_arguments=()):
    for log in ("gh.log", "cell.log"):
        (scratch / log).unlink(missing_ok=True)
    completed = subprocess.run(
        [sys.executable, str(PROGRAM), "7", BASE, "--merge-lane-worktrees-and-outputs-directory", str(helpers),
         "--merge-lane-review-worktrees-directory", str(review_worktrees_directory(helpers)),
         "--review-tools-worktree-at-main", str(scratch / "main-checkout"), *extra_arguments],
        capture_output=True, text=True,
        env={**os.environ,
             "HOME": str(home or scratch / "home"),
             "PATH": f"{scratch / 'bin'}{os.pathsep}{os.environ['PATH']}",
             "GIT_DIR": str(scratch / "no-such-git-directory"),
             "MERGE_LANE_CODEX_TEST_GH_LOG": str(scratch / "gh.log"),
             "MERGE_LANE_CODEX_TEST_CELL_LOG": str(scratch / "cell.log"),
             "MERGE_LANE_CODEX_TEST_DESCRIPTION": DESCRIPTION,
             **(extra_environment or {})})
    return completed, read_log(scratch / "gh.log"), read_log(scratch / "cell.log")


def main():
    # Resolved, because macOS's mkdtemp path is a symlink and the program resolves its paths.
    scratch = Path(tempfile.mkdtemp(prefix="merge-lane-codex-test-")).resolve()
    try:
        (scratch / "bin").mkdir()
        (scratch / "bin" / "gh").write_text(FAKE_GH)
        (scratch / "bin" / "gh").chmod(0o755)
        (scratch / "main-checkout" / "scripts").mkdir(parents=True)
        (scratch / "main-checkout" / "scripts" / "code-review-codex-cell.py").write_text(
            FAKE_CODEX_CELL)
        instructions = scratch / "main-checkout" / "docs" / "agents" / "pr-reviewer-instructions.md"
        instructions.parent.mkdir(parents=True)
        instructions.write_text("# PR reviewer instructions\n")
        token_directory = scratch / "home" / ".config" / "nedsnodes"
        token_directory.mkdir(parents=True)
        (token_directory / "ned-review-merge.token").write_text(TOKEN + "\n")
        helpers = scratch / "merge-helpers"
        outputs = helpers / "cx" / "pr7-01234567"
        record = outputs / "codex-review-run-record.json"
        head_worktree = review_worktrees_directory(helpers) / "pr7-head"
        head_worktree.mkdir(parents=True)
        for command in (["init", "-q"], ["-c", "user.name=t", "-c", "user.email=t@example.invalid", "commit",
                                         "-q", "--allow-empty", "-m", "head"]):
            subprocess.run(["git", "-C", str(head_worktree), *command], check=True)
        head = subprocess.run(["git", "-C", str(head_worktree), "rev-parse", "HEAD"], check=True,
                              capture_output=True, text=True).stdout.strip()

        completed, gh_calls, cell_calls = run_program(scratch, helpers)
        detail = f"exit {completed.returncode}\n{completed.stdout}{completed.stderr}"
        check("a finished run records the pull request, head, base, exit code and report",
              record.exists() and json.loads(record.read_text()) == {
                  "pull_request": 7, "head_commit": head, "base_commit": BASE, "exit_code": 0,
                  "report_file": str(outputs / "codex-code-review-report.md")}, detail)
        check("the description is read from GitHub with the merge account's token",
              gh_calls == [{"argv": ["pr", "view", "7", "--repo", "nedsnodes/nedsnodes",
                                     "--json", "body", "--jq", ".body"], "gh_token": TOKEN}],
              json.dumps(gh_calls))
        check("the description is saved under cx/pr<n>-<base>",
              (outputs / "pull-request-description.md").read_text() == DESCRIPTION, detail)
        check("main's review runs on pr<n>-head from the base commit, with main's "
              "PR reviewer instructions",
              cell_calls and cell_calls[0]["argv"] == [
                  "--base", BASE, "--repo", str(review_worktrees_directory(helpers) / "pr7-head"),
                  "--instructions-file", str(instructions),
                  "--pull-request-description-file", str(outputs / "pull-request-description.md"),
                  "--output", str(outputs / "codex-code-review-report.md")], json.dumps(cell_calls))
        check("neither GIT_DIR nor the token reaches the review",
              cell_calls and cell_calls[0]["git_dir"] is None
              and cell_calls[0]["gh_token"] is None, json.dumps(cell_calls))
        check("the review's stdout, stderr and report are kept under cx/pr<n>-<base>",
              (outputs / "stdout").read_text() == "cell stdout\n"
              and (outputs / "stderr").read_text() == "cell stderr\n"
              and (outputs / "codex-code-review-report.md").read_text() == "the report\n", detail)
        check("one line names the exit code and the report, and the program exits 0",
              completed.returncode == 0 and completed.stdout ==
              f"PR 7 codex cell (base 01234567) exit 0; report {outputs / 'codex-code-review-report.md'}\n",
              detail)

        completed, _, _ = run_program(scratch, helpers, {"MERGE_LANE_CODEX_TEST_CELL_EXIT": "3"})
        check("the review's exit code is the program's",
              completed.returncode == 3 and "exit 3;" in completed.stdout,
              f"exit {completed.returncode}\n{completed.stdout}")
        check("a failed run's record holds its exit code", json.loads(record.read_text())["exit_code"] == 3,
              record.read_text())

        completed, _, cell_calls = run_program(scratch, helpers,
                                               {"MERGE_LANE_CODEX_TEST_GH_FAILS": "1"})
        check("a description gh cannot read exits 2 before the review runs",
              completed.returncode == 2 and cell_calls == []
              and "HTTP 404" in completed.stdout,
              f"exit {completed.returncode}\n{completed.stdout}{completed.stderr}")
        check("a run that stopped before the review records exit 2, replacing the earlier record",
              json.loads(record.read_text())["exit_code"] == 2, record.read_text())

        earlier_record = record.read_text()
        head_worktree.rename(head_worktree.with_name("pr7-head-away"))
        completed, gh_calls, cell_calls = run_program(scratch, helpers)
        head_worktree.with_name("pr7-head-away").rename(head_worktree)
        check("an unreadable head commit exits 2 before the review runs, and leaves the earlier record as it was",
              completed.returncode == 2 and gh_calls == [] and cell_calls == []
              and record.read_text() == earlier_record
              and "could not read the head commit" in completed.stdout,
              f"exit {completed.returncode}\n{completed.stdout}{completed.stderr}")

        completed, _, cell_calls = run_program(scratch, helpers, extra_arguments=("--expected-head-commit", head))
        check("a run given the commit pr<n>-head holds as --expected-head-commit reviews it",
              completed.returncode == 0 and len(cell_calls) == 1
              and json.loads(record.read_text())["head_commit"] == head,
              f"exit {completed.returncode}\n{completed.stdout}{completed.stderr}")
        earlier_record = record.read_text()
        completed, gh_calls, cell_calls = run_program(scratch, helpers,
                                                      extra_arguments=("--expected-head-commit", head[:8]))
        check("a run whose --expected-head-commit is not the full commit pr<n>-head holds exits 2 before the "
              "review, naming both commits, and leaves the earlier record for that commit as it was",
              completed.returncode == 2 and gh_calls == [] and cell_calls == []
              and record.read_text() == earlier_record and json.loads(earlier_record)["head_commit"] == head
              and f"holds commit {head}, not {head[:8]}" in completed.stdout,
              f"exit {completed.returncode}\n{completed.stdout}{completed.stderr}")

        completed, _, cell_calls = run_program(scratch, helpers, {"MERGE_LANE_CODEX_TEST_CELL_MOVES_HEAD": "1"},
                                               extra_arguments=("--expected-head-commit", head))
        moved_to = subprocess.run(["git", "-C", str(head_worktree), "rev-parse", "HEAD"], check=True,
                                  capture_output=True, text=True).stdout.strip()
        check("a run whose pr<n>-head moves during the review exits 2, records exit code 2 with the commit it "
              "started on, and names both commits",
              completed.returncode == 2 and len(cell_calls) == 1 and moved_to != head
              and json.loads(record.read_text())["exit_code"] == 2
              and json.loads(record.read_text())["head_commit"] == head
              and f"held commit {head} when the review started and now holds commit {moved_to}" in completed.stdout,
              f"exit {completed.returncode}\n{completed.stdout}{completed.stderr}")
        head = moved_to

        completed, _, cell_calls = run_program(scratch, helpers, {"MERGE_LANE_CODEX_TEST_CELL_BREAKS_HEAD": "1"})
        (head_worktree / ".git-away").rename(head_worktree / ".git")
        check("a run whose pr<n>-head commit cannot be read after the review exits 2 and records exit code 2",
              completed.returncode == 2 and len(cell_calls) == 1
              and json.loads(record.read_text())["exit_code"] == 2
              and "has a head commit that could not be read" in completed.stdout,
              f"exit {completed.returncode}\n{completed.stdout}{completed.stderr}")

        record.unlink()
        record.mkdir()
        (record / "keeps-the-directory-from-being-replaced").write_text("")
        completed, _, cell_calls = run_program(scratch, helpers)
        check("a record path that cannot be removed exits 2 before the review runs",
              completed.returncode == 2 and cell_calls == []
              and "could not remove the earlier run record" in completed.stdout,
              f"exit {completed.returncode}\n{completed.stdout}{completed.stderr}")
        shutil.rmtree(record)

        fake_cell = scratch / "main-checkout" / "scripts" / "code-review-codex-cell.py"
        fake_cell.write_text(FAKE_CODEX_CELL.replace(
            'sys.exit(int(', 'os.chmod(os.path.dirname(argv[argv.index("--output") + 1]), 0o555)\nsys.exit(int('))
        completed, _, _ = run_program(scratch, helpers)
        outputs.chmod(0o755)
        fake_cell.write_text(FAKE_CODEX_CELL)
        check("a run record that cannot be written exits 2 and says why, even after a passing review",
              completed.returncode == 2 and "could not be written" in completed.stdout and not record.exists(),
              f"exit {completed.returncode}\n{completed.stdout}{completed.stderr}")

        completed, gh_calls, cell_calls = run_program(scratch, helpers,
                                                      home=scratch / "home-with-no-token")
        check("an unreadable token file exits 2 before gh or the review runs",
              completed.returncode == 2 and gh_calls == [] and cell_calls == [],
              f"exit {completed.returncode}\n{completed.stdout}{completed.stderr}")

        blank_home = scratch / "home-with-blank-token"
        (blank_home / ".config" / "nedsnodes").mkdir(parents=True)
        (blank_home / ".config" / "nedsnodes" / "ned-review-merge.token").write_text(" \n\t\n")
        completed, gh_calls, cell_calls = run_program(scratch, helpers, home=blank_home)
        check("a token file holding only whitespace exits 2 before gh or the review runs",
              completed.returncode == 2 and gh_calls == [] and cell_calls == []
              and "is empty" in completed.stdout,
              f"exit {completed.returncode}\n{completed.stdout}{completed.stderr}")

        cell = scratch / "main-checkout" / "scripts" / "code-review-codex-cell.py"
        cell.rename(cell.with_suffix(".away"))
        completed, gh_calls, cell_calls = run_program(scratch, helpers)
        cell.with_suffix(".away").rename(cell)
        check("a review tools worktree without code-review-codex-cell.py exits 2 before gh runs",
              completed.returncode == 2 and gh_calls == [] and cell_calls == []
              and "code-review-codex-cell.py is missing" in completed.stdout,
              f"exit {completed.returncode}\n{completed.stdout}{completed.stderr}")

        instructions.rename(instructions.with_suffix(".away"))
        completed, gh_calls, cell_calls = run_program(scratch, helpers)
        instructions.with_suffix(".away").rename(instructions)
        check("a review tools worktree without pr-reviewer-instructions.md exits 2 before gh "
              "or the review runs",
              completed.returncode == 2 and gh_calls == [] and cell_calls == []
              and "pr-reviewer-instructions.md is missing" in completed.stdout,
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
