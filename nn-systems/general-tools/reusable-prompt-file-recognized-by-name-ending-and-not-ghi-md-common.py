#!/usr/bin/env python3
"""Say whether a repository-relative path is a reusable-prompt file, as the
glossary defines one, by its name.

A GHI-MD named for its issue has its issue's title as a slug in its name, so
an issue titled "... agent instructions" gives a name ending in
-instructions.md, and the name ending alone would take it for a
reusable-prompt. has_reusable_prompt_file_name_and_is_not_ghi_md leaves out
such a name wherever scripts/ghi-issue-write.py's writable_relative_path lets
one sit.

Standard library only, with no side effects on load, so a guard hook can load
it. Load it by path, under the snake_case form of its file name:

    spec = importlib.util.spec_from_file_location(
        "reusable_prompt_file_recognized_by_name_ending_and_not_ghi_md_common", <path>)
"""

import re

REUSABLE_PROMPT_SUFFIXES = ("-prompt.md", "-instructions.md")

# <number>-<slug>.md, or <number>-<slug>.<kind>.design.md, directly in
# docs/issues/ or directly in a system's directory, where slug() in
# scripts/ghi-issue-write.py joins lowercase letters and digits with hyphens.
_NUMBERED_GHI_MD_PATH = re.compile(
    r"(?:docs/issues|nn-systems/[^/]+)/[0-9]+-[a-z0-9]+(?:-[a-z0-9]+)*(?:\.[a-z]+\.design)?\.md")


def is_numbered_ghi_md_path(repository_relative_path):
    """True when the path, relative to the repository root with / separators,
    has the form of a GHI-MD named for its issue."""
    return _NUMBERED_GHI_MD_PATH.fullmatch(str(repository_relative_path)) is not None


def has_reusable_prompt_file_name_and_is_not_ghi_md(repository_relative_path):
    """True when the file name ends in a REUSABLE_PROMPT_SUFFIXES entry and the
    path, relative to the repository root with / separators, does not have the
    form of a GHI-MD named for its issue."""
    path = str(repository_relative_path)
    return (path.rsplit("/", 1)[-1].endswith(REUSABLE_PROMPT_SUFFIXES)
            and not is_numbered_ghi_md_path(path))
