#!/usr/bin/env python3
"""Say whether a repository-relative path is a reusable-prompt file, as the
glossary defines one, by its name.

A GHI-MD named for its issue has its issue's title as a slug in its name, so
an issue titled "... agent instructions" gives a name ending in
-instructions.md, and the name ending alone would take it for a
reusable-prompt. has_reusable_prompt_file_name_and_is_not_ghi_md leaves out
every path that scripts/ghi-issue-write.py's edit operation accepts as a
GHI-MD named for its issue, by asking that program's own rule.

It has no side effects on load, so a guard hook can load it.
has_reusable_prompt_file_name_and_is_not_ghi_md loads
scripts/ghi-issue-write.py only for a path with a reusable-prompt ending,
because loading it takes tens of milliseconds and the hooks that call it run
on every prompt; is_numbered_ghi_md_path loads it on every first call. Load this module by path, under the snake_case form
of its file name:

    spec = importlib.util.spec_from_file_location(
        "reusable_prompt_file_recognized_by_name_ending_and_not_ghi_md_common", <path>)
"""

import importlib.util
from pathlib import Path

REUSABLE_PROMPT_SUFFIXES = ("-prompt.md", "-instructions.md")

GHI_ISSUE_WRITE_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "ghi-issue-write.py"

_ghi_issue_write = None


def _ghi_issue_write_module():
    global _ghi_issue_write
    if _ghi_issue_write is None:
        spec = importlib.util.spec_from_file_location("ghi_issue_write", GHI_ISSUE_WRITE_SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _ghi_issue_write = module
    return _ghi_issue_write


def is_numbered_ghi_md_path(repository_relative_path):
    """True when the path, relative to the repository root with / separators,
    is one scripts/ghi-issue-write.py's edit operation accepts as a GHI-MD
    named for its issue: a name beginning with its issue's number, where
    writable_relative_path lets a GHI-MD sit."""
    path = str(repository_relative_path)
    writer = _ghi_issue_write_module()
    return (writer.issue_number_in_file_name(Path(path)) is not None
            and writer.writable_relative_path(path))


def has_reusable_prompt_file_name_and_is_not_ghi_md(repository_relative_path):
    """True when the file name ends in a REUSABLE_PROMPT_SUFFIXES entry and the
    path, relative to the repository root with / separators, is not a GHI-MD
    named for its issue."""
    path = str(repository_relative_path)
    return (path.rsplit("/", 1)[-1].endswith(REUSABLE_PROMPT_SUFFIXES)
            and not is_numbered_ghi_md_path(path))
