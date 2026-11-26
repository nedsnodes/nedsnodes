#!/usr/bin/env python3
"""Fail when git tracks a file whose name writes a dot suffix with a hyphen.

docs/nedsnodes-wiki/nedsnodes-file-naming-and-location-standards.md defines a
suffix as written with its leading dot. DOT_SUFFIXES lists the suffixes of
Markdown files that take one; a tracked `.md` file whose stem ends in one of
them written with a hyphen, such as `docs/agents/seat-first-prompt.md` for
`docs/agents/seat-first.prompt.md`, fails this test, unless its name also
ends in a dot suffix, as `x.test-design.md` does, or it is a GHI-MD, whose
name is its issue's title as a slug and may end in any word.

Run: python3 nn-systems/general-tools/tests/tracked-file-names-write-each-dot-suffix-with-a-dot-not-a-hyphen-test.py
Prints one line per case and exits non-zero if any case fails.
"""

import importlib.util
import subprocess
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
GENERAL_TOOLS = REPOSITORY_ROOT / "nn-systems" / "general-tools"

DOT_SUFFIXES = (".instructions", ".prompt", ".design", ".test-design", ".contract")

# Pull request 4956 renames this file; its rebase onto this test removes the entry.
EXEMPT_PATHS = {"docs/agents/pr-reviewer-instructions.md"}


def load(module_name, path):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


reusable_prompt_rule = load(
    "reusable_prompt_file_recognized_by_name_ending_and_not_ghi_md_common",
    GENERAL_TOOLS / "reusable-prompt-file-recognized-by-name-ending-and-not-ghi-md-common.py")
git_environment = load("git_redirecting_environment_variables_removal_common",
                       GENERAL_TOOLS / "git-redirecting-environment-variables-removal-common.py")


def writes_a_dot_suffix_with_a_hyphen(path):
    """True when the Markdown file's stem ends in a DOT_SUFFIXES entry written with a hyphen and
    in no entry written with its dot."""
    if not path.endswith(".md"):
        return False
    stem = path.rsplit("/", 1)[-1][:-len(".md")]
    if stem.endswith(DOT_SUFFIXES):
        return False
    return stem.endswith(tuple("-" + suffix[1:] for suffix in DOT_SUFFIXES))


def misnamed(paths):
    return sorted(path for path in paths
                  if writes_a_dot_suffix_with_a_hyphen(path) and path not in EXEMPT_PATHS
                  and not reusable_prompt_rule.is_numbered_ghi_md_path(path))


failures = 0


def check(name, condition, detail=None):
    global failures
    if condition:
        print(f"PASS  {name}")
    else:
        failures += 1
        print(f"FAIL  {name}: {detail!r}")


check("a hyphen-written suffix fails, at any depth and for each suffix",
      misnamed(["docs/agents/seat-first-prompt.md", "x/y-instructions.md", "a-design.md",
                "a.tool-design.md", "b-test-design.md", "c-contract.md"])
      == sorted(["docs/agents/seat-first-prompt.md", "x/y-instructions.md", "a-design.md",
                 "a.tool-design.md", "b-test-design.md", "c-contract.md"]))
check("a dot-written suffix passes, a test-design's ending included",
      misnamed(["docs/agents/seat-first.prompt.md", "x/y.instructions.md", "a.tool.design.md",
                "a.tool.test-design.md", "a.tool.contract.md"]) == [])
check("a name with no suffix, or a file that is not Markdown, passes",
      misnamed(["docs/prompt-writing-notes.md", "scripts/x-prompt.py",
                "scripts/scenarios/re-reviews-the-test-design.yaml"]) == [])
check("a GHI-MD passes, whatever its name ends in",
      misnamed(["docs/issues/4080-fix-the-arbitrator-agent-instructions.md",
                "nn-systems/handoff/7-the-handoff-prompt.md"]) == [])
check("a hyphen-written name where no GHI-MD may sit fails",
      misnamed(["docs/issues/queue/7-x-prompt.md"]) == ["docs/issues/queue/7-x-prompt.md"])
check("the exempt path passes", misnamed(sorted(EXEMPT_PATHS)) == [])

tracked = [path for path in subprocess.run(
    ["git", "-C", str(REPOSITORY_ROOT), "ls-files", "-z"], capture_output=True, text=True,
    check=True, env=git_environment.environment_without_git_redirecting_variables()
).stdout.split("\0") if path]
check("git ls-files lists this repository's files", bool(tracked))
found = misnamed(tracked)
check("no tracked file writes a dot suffix with a hyphen; rename each one listed with its "
      "suffix's dot, as docs/nedsnodes-wiki/nedsnodes-file-naming-and-location-standards.md "
      "defines a suffix", found == [], found)

if failures:
    print(f"{failures} case(s) failed")
    sys.exit(1)
print("all cases passed")
