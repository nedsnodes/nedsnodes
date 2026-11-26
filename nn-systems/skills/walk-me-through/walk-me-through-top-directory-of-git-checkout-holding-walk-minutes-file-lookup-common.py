#!/usr/bin/env python3
"""Ask git for a directory's checkout top, and whether that checkout holds a walk-minutes file.

The walk finder's patterns need Python 3.11 and the Mac's python3 is 3.9, so a hook that runs in every checkout calls
top_directory_of_git_checkout_holding_walk_minutes_file_or_none before it loads the walk finder. This module must keep
loading on Python 3.9.

Load it by path, under the snake_case form of its file name.
"""
import importlib.util
import os
from pathlib import Path

GENERAL_TOOLS = Path(__file__).resolve().parents[2] / "general-tools"
GIT_MODULE_FILE = GENERAL_TOOLS / "git-machine-readable-output-runner-and-parser-common.py"
GIT_REDIRECTING_REMOVAL_FILE = GENERAL_TOOLS / "git-redirecting-environment-variables-removal-common.py"
WALK_DIRECTORY = Path("docs") / "walk"
MINUTES_SUFFIX = "-minutes.md"


def load_module(name, path):
    specification = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


git = load_module("git_machine_readable_output_runner_and_parser_common", GIT_MODULE_FILE)
git_redirecting_removal = load_module("git_redirecting_environment_variables_removal_common", GIT_REDIRECTING_REMOVAL_FILE)


def checkout_top(directory):
    """Return the top of directory's checkout, or None outside one."""
    output = git.run_git_unless_outside_a_repository(
        directory, ["rev-parse", "--show-toplevel"],
        environment=git_redirecting_removal.environment_without_git_redirecting_variables())
    if output is None:
        return None
    return Path(os.fsdecode(output).rstrip("\n"))


def top_directory_of_git_checkout_holding_walk_minutes_file_or_none(directory):
    """Return the top of directory's checkout when that checkout has a walk-minutes file, else None. When git cannot
    answer, as inside a `.git` directory or for a directory since removed, raise only if the directory or a parent
    holds a walk-minutes file: a hook must report a message it may have lost, and stay silent everywhere else."""
    try:
        top = checkout_top(directory)
    except git.GitCommandFailed:
        if any(any((candidate / WALK_DIRECTORY).glob("*" + MINUTES_SUFFIX))
               for candidate in (directory, *directory.parents)):
            raise
        return None
    if top is None or not any((top / WALK_DIRECTORY).glob("*" + MINUTES_SUFFIX)):
        return None
    return top
