---
issue: "[Printed git remedy commands ignore the reader's git-redirecting environment, through one shared helper](https://github.com/nedsnodes/nedsnodes/issues/4959)"
---

# Printed git remedy commands ignore the reader's git-redirecting environment, through one shared helper

## What is wrong

Many programs print a git command for the reader to run when a step fails, such as `scripts/run-suite-in-signal-sandbox.py`, whose `mutation_testing_worktree_remove` prints "Remove it with: git -C {top} worktree remove --force {copy}". When the reader's shell sets a git-redirecting variable, such as `GIT_DIR`, git acts on that repository whatever `-C` says, so the printed remedy acts on the wrong repository or fails.

[PR 4909, "Scheduled full test run: the fetch ref is deleted after the worktree add, in a finally; printed git remedies ignore the reader's GIT_DIR; the overlap setup write is checked"](https://github.com/nedsnodes/nedsnodes/pull/4909) fixes this for `scripts/scheduled-full-test-run-of-main.py` alone, with its own constant `PRINTED_GIT_COMMAND_IGNORING_THE_READERS_GIT_DIR = "env -u GIT_DIR -u GIT_WORK_TREE git"`. The project lists six git-redirecting variables in `GIT_REDIRECTING_ENVIRONMENT_VARIABLES`, in `nn-systems/general-tools/git-redirecting-environment-variables-removal-common.py`; that constant unsets only two of them, leaving out `GIT_COMMON_DIR` among others. It got through because `scripts/git-redirecting-environment-variables-defined-once-test.py` looks for copies of the list only in tuple, list and set literals, not in a string such as `env -u GIT_DIR -u GIT_WORK_TREE git`.

`git grep -c "git -C {" origin/main -- 'scripts/*.py' 'nn-systems/*.py'`, run on 2026-11-26, lists 34 files that build such a command in an f-string; how many of them print it for a reader rather than run it is not counted (unverified).

## Why it matters

A remedy that acts on the wrong repository can change another clone's refs or worktrees, and the reader, following the program's own instructions, has no reason to suspect it.

## What to do

In scope is every git command a program prints for a reader to run, such as a remedy after a failure or a next step, with or without `-C`, in a Python program or a shell script. Out of scope are commands a program runs itself, which already strip the variables through `environment_without_git_redirecting_variables`, and usage examples in docstrings.

1. Add to the shared module a function that returns the prefix of a printed git command, `env -u <each variable in the list> git`, so the printed command unsets every variable the list holds; a shell script prints the same prefix, read from the module or checked against it by the test in step 2.
2. Write the test first: an `ast` scan of the Python files in `scripts/` and `nn-systems/`, and a text scan of their `.sh` files, that fails on each string or f-string, docstrings left out, whose text holds `git -C ` or starts with `git `, unless the helper's prefix comes first. A command the program runs is an argument list, such as `["git", "-C", ...]`, and does not match. The files and lines it fails on are the work-list for step 3.
3. Move each program on that work-list onto the helper, starting with `scripts/scheduled-full-test-run-of-main.py`'s constant.
4. Extend `scripts/git-redirecting-environment-variables-defined-once-test.py` to fail on any string outside the shared module that holds `-u ` followed by one of the listed variables, so a hand-written prefix cannot come back.

[GHI 1123, "Agents reuse what the project has already solved: shared helpers, one page of reusable components, and a reuse check before, during and after the build"](https://github.com/nedsnodes/nedsnodes/issues/1123) moves the list into the shared module (its ruling 9); it says nothing about printed commands, which is this issue's subject.
