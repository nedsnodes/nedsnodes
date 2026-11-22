#!/usr/bin/env python3
"""Fail when git tracks a log that the file naming page keeps out of git.

docs/nedsnodes-wiki/nedsnodes-file-naming-and-location-standards.md, section
"Filename suffixes": a log, as
nn-systems/general-tools/log-suffix-and-extension-file-classify-common.py
classifies one, is kept in the log-store and never in git, with two
exceptions, which this test allows:

  * a `-draft` or `-candidate` file in a draft place, as
    nn-systems/general-tools/draft-place-directory-check-common.py defines one
    for the instruction-file guard too. Whether the file is still pending
    approval, as the page also asks, is not something a file name shows, so
    it is not checked;
  * a GHI-MD, which is a file under `docs/issues/` whose name is the GHI's
    number, a hyphen, and the rest of its name ending `.md`, such as
    `docs/issues/142-draft-md-prompt-research-report.md`.

It reads `git ls-files` of the checkout this file is in, and prints each log it
finds outside the exceptions. The cases before it pin the exceptions on made-up
paths.

Run: python3 nn-systems/general-tools/tests/logs-tracked-by-git-outside-the-file-naming-page-exceptions-test.py
Prints one line per case and exits non-zero if any case fails.
"""

import importlib.util
import re
import subprocess
import sys
from pathlib import Path, PurePosixPath

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
GENERAL_TOOLS = REPOSITORY_ROOT / "nn-systems" / "general-tools"
PAGE = "docs/nedsnodes-wiki/nedsnodes-file-naming-and-location-standards.md"


def load(module_name, file_name):
    spec = importlib.util.spec_from_file_location(module_name, GENERAL_TOOLS / file_name)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


classify = load("log_suffix_and_extension_file_classify_common",
                "log-suffix-and-extension-file-classify-common.py")
draft_place = load("draft_place_directory_check_common", "draft-place-directory-check-common.py")
git_environment = load("git_redirecting_environment_variables_removal_common",
                       "git-redirecting-environment-variables-removal-common.py")

GHI_MD_NAME = re.compile(r"[0-9]+-[^/]*\.md")


def log_is_allowed_in_git(path):
    """Return True when `path`, a log, falls under one of the page's two exceptions."""
    parts = PurePosixPath(path).parts
    stem = PurePosixPath(path).stem
    if draft_place.directory_is_a_draft_place(parts[:-1]) and stem.endswith(("-draft", "-candidate")):
        return True
    return parts[:2] == ("docs", "issues") and GHI_MD_NAME.fullmatch(parts[-1]) is not None


def logs_outside_the_exceptions(paths):
    return [path for path in paths
            if classify.log_suffix_and_extension_file_classify_as_log_not_a_log_or_unlisted(path) == classify.LOG
            and not log_is_allowed_in_git(path)]


failures = 0


def check(name, condition, detail=None):
    global failures
    if condition:
        print(f"PASS  {name}")
    else:
        failures += 1
        print(f"FAIL  {name}: {detail!r}")


ALLOWED = (
    "docs/drafts/plan-draft.md",
    "docs/drafts/sub/plan-candidate.md",
    "docs/agents/queue/brief-draft.md",
    "docs/issues/queue/issue-candidate.txt",
    "docs/issues/142-draft-md-prompt-research-report.md",
    "docs/issues/archived/43-step-2-inputs-log.md",
)
NOT_ALLOWED = (
    "docs/drafts/plan-report.md",
    "nn-queue/item-draft.md",
    "docs/agents/queue/brief-log.md",
    "docs/plan-draft.md",
    "drafts/plan-draft.md",
    "queue-draft.md",
    "docs/queue-notes/plan-draft.md",
    "docs/issues/archived/notes-draft.md",
    "docs/issues/notes-report.md",
    "docs/issues/142-run-report.json",
    "scripts/docs/issues/142-run-report.md",
    "logs/run-log.txt",
)
for path in ALLOWED:
    check(f"allowed in git: {path}", log_is_allowed_in_git(path))
for path in NOT_ALLOWED:
    check(f"not allowed in git: {path}", not log_is_allowed_in_git(path))
guard_spec = importlib.util.spec_from_file_location(
    "instruction_file_guard", REPOSITORY_ROOT / ".claude" / "guard-hooks" / "instruction-file-guard.py")
guard = importlib.util.module_from_spec(guard_spec)
guard_spec.loader.exec_module(guard)
check("the guard reads its draft places from the file this test reads",
      Path(guard._draft_place.__file__).resolve() == Path(draft_place.__file__).resolve(),
      guard._draft_place.__file__)
guard._draft_place.DRAFT_PLACE_DIRECTORY_NAMES = ("queue", "made-up-draft-place")
check("a draft place added to the shared definition reaches the guard",
      guard.is_in_draft_or_working_place(("docs", "made-up-draft-place")))
check("the guard's scratch places are not draft places for this audit",
      not draft_place.directory_is_a_draft_place((".claude", "jobs"))
      and guard.is_in_draft_or_working_place((".claude", "jobs")))

check("only logs are reported",
      logs_outside_the_exceptions(["scripts/run-log.py", "logs/run-report.csv", "logs/run-log.txt",
                                   "docs/drafts/plan-draft.md"]) == ["logs/run-log.txt"])

listing = subprocess.run(
    ["git", "-C", str(REPOSITORY_ROOT), "ls-files", "-z"], capture_output=True, text=True,
    env=git_environment.environment_without_git_redirecting_variables())
check("git ls-files ran", listing.returncode == 0 and listing.stdout, listing.stderr)
offending = logs_outside_the_exceptions(listing.stdout.split("\0"))
for path in offending:
    print(f"LOG IN GIT  {path}")
check("git tracks no log outside the page's two exceptions", not offending,
      f"move each LOG IN GIT path above to the log-store, or rename it if it is not a log; "
      f"the rule is the section 'Filename suffixes' of {PAGE}" if offending else None)

print(f"\n{failures} failure(s)")
sys.exit(1 if failures else 0)
