---
issue: "[The cold-read grid's stray-write undo leaves a renamed tracked file deleted](https://github.com/nedsnodes/nedsnodes/issues/4380)"
---

# The cold-read grid's stray-write undo leaves a renamed tracked file deleted

## Reproduction

When a cold-read-cell is stopped, the cold-read grid prints a stray-write line for each file that changed while the cell ran. The line says what to read and gives a command that undoes the change. This was run on 2026-11-23 against main at commit `a83436200656`, calling the real `stopped_cells_write_check_lines` in `nn-systems/cold-read/cold-read-grid.py` on a scratch git repository.

1. Commit a file `a.md`, then take the snapshot the grid takes before it launches its cold-read-cells, by calling `working_tree_state()` in `nn-systems/cold-read/cold-read-cell-common.py`.
2. Do what a stopped cold-read-cell could do: run `git mv a.md b.md`, then write a new `a.md`. `git status --porcelain` now shows `R  a.md -> b.md` and `?? a.md`.
3. Call `stopped_cells_write_check_lines`. It prints one stray-write line per path. The line for `a.md` offers `rm -r -- <repository>/a.md`, and the line for `b.md` offers `git -C <repository> restore --staged --worktree -- b.md`.
4. Run both printed commands. `git status --porcelain` now shows `D  a.md`, and neither file is on disk.

The committed text is not lost: `git restore --staged --worktree -- a.md` brings `a.md` back. Run from the state in step 2 instead of the printed commands, `git restore --staged --worktree -- a.md b.md` returns the repository to an empty status with the committed text in `a.md`.

The Claude reviewer of PR [cold-read-grid: a stray-write line reads a path by all its git status entries and names untracked files absolutely](https://github.com/nedsnodes/nedsnodes/pull/4369) reported the same result in [its review](https://github.com/nedsnodes/nedsnodes/pull/4369#pullrequestreview-6019022392). It also reported the same outcome after `git rm --cached a.md`, staging a new file with nearly the same content as `a.md`, and rewriting `a.md`, because git pairs the deletion and the new file as a rename. That second sequence was not rerun for this GHI-MD (unverified).

## What is wrong

An agent that follows the grid's printed undo commands, to remove what a stopped cold-read-cell did, ends with a tracked file deleted and the deletion staged. The commands are offered as the way back to the state before the cold-read-cell started.

The cause is at `nn-systems/cold-read/cold-read-grid.py:1003`, `untracked = {entry.path for entry in entries if entry.code == "??"}`. For a staged rename, git's status entry holds the new name in `entry.path` and the old name in `entry.origin_path`. The classification reads only `entry.path`, so it does not see that the index has removed `a.md`, and it treats the re-created `a.md` as a file git has never tracked. `working_tree_state()` in `nn-systems/cold-read/cold-read-cell-common.py` already adds both names to its snapshot, so the grid knows the path changed but classifies it wrongly.

The same classification chooses what the line tells the agent to read. By the code at `cold-read-grid.py:1021`, when `a.md` already had uncommitted changes before the cold-read-cell started, the line tells the agent to read `a.md` as a file git does not track, although `a.md` is tracked at `HEAD` and its staged removal is part of the change. This case was read from the code and not run.

The pull request named above does not cause this defect, and at its nn-head-commit `b09ac55a46aa` does not fix it: it still groups status codes by `entry.path`.

## What to do

The owner is the agent-seat cold-read-improvement. Fix the root cause: make the stray-write classification count a staged rename's `origin_path` as a removal from the index, so that a re-created rename source is not called untracked, and so that following the printed undo commands for both names restores the file. Each stray-write line is printed per path, so the fix must work when the agent runs the two lines' commands one after the other, in either order. Add a test that runs the printed undo commands after `git mv a.md b.md` and a re-created `a.md`, and checks that the repository returns to its state before the cold-read-cell started.
