---
issue: "[The cold-read grid's fallback undo command reads a file name as a wildcard and discards another file's edit](https://github.com/nedsnodes/nedsnodes/issues/4402)"
---

# The cold-read grid's fallback undo command reads a file name as a wildcard and discards another file's edit

## Reproduction

In a scratch git repository, commit two files, `chapter[1].md` and `chapter1.md`. Make an uncommitted edit to `chapter1.md`, and write different text to `chapter[1].md` to stand for a stopped cold-read-cell's stray write. Then run the cold-read grid's printed command `git restore --staged --worktree <path>`, with `'chapter[1].md'` in place of `<path>`:

```
git restore --staged --worktree 'chapter[1].md'
```

The command exits 0 and restores both files. `chapter1.md` is back to its committed text, so the uncommitted edit is lost. Git reads `chapter[1].md` as a wildcard pathspec, which matches `chapter1.md` as well as the file of that exact name.

The same steps with this command restore only `chapter[1].md` and keep the edit in `chapter1.md`:

```
git --literal-pathspecs restore --staged --worktree -- 'chapter[1].md'
```

The single quotes are needed too. Without them, bash expands `chapter[1].md` to `chapter1.md` before git runs, so the same command discards the edit in `chapter1.md` and leaves the stray write in `chapter[1].md`.

## What the message does

When a cold-read-cell is stopped before it checks for files it wrote outside its report, the cold-read grid checks for it. When the grid cannot run that check, it prints the message `STOPPED_CELL_WRITE_CHECK_LINE`, defined at line 282 of `nn-systems/cold-read/cold-read-grid.py` and printed at line 1010. The message is fixed text with the placeholder `<path>`. It tells the agent to read `git status`, to delete an untracked file a reviewer wrote, and to undo a tracked file a reviewer wrote by running `git restore --staged --worktree <path>`.

## Why it matters

An agent that follows the message on a file whose name holds a wildcard character loses uncommitted work in another file. Git reports success and prints nothing about the second file, so the agent has no sign of the loss.

## What to do

In `STOPPED_CELL_WRITE_CHECK_LINE`, change the command to `git --literal-pathspecs restore --staged --worktree -- '<path>'`, and tell the agent to keep the path in single quotes when it deletes or restores a file.

Write the restore command once, in text that both `STOPPED_CELL_WRITE_CHECK_LINE` and `STRAY_WRITE_UNDO_TRACKED` use, so that the two messages cannot differ.

In `nn-systems/cold-read/tests/cold-read-grid-test.py`, add a test that takes the restore command from the printed message, puts `chapter[1].md` in place of `<path>`, runs it through a shell on the reproduction above, and asserts that the edit in `chapter1.md` survives and the stray write is gone.

The pull request [cold-read-grid: stray-write commands read paths literally and show both conflict sides](https://github.com/nedsnodes/nedsnodes/pull/4395) adds `--literal-pathspecs` to the commands the grid builds for each changed path, but not to this message. GHI [The cold-read grid's stray-write undo leaves a renamed tracked file deleted](https://github.com/nedsnodes/nedsnodes/issues/4380) is a different defect in the stray-write undo.
