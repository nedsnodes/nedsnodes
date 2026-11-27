---
issue: "[Keep Claude Code's auto-memory out of Claude cold-read-cells](https://github.com/nedsnodes/nedsnodes/issues/4651)"
---

# Keep Claude Code's auto-memory out of Claude cold-read-cells

## What happens

A Claude cold-read-cell is meant to read a text the way a reader new to the project would: it should know only `CLAUDE.md`, the glossaries and the text. [Pull request 4628, cold-read: every Claude cold-read-cell starts with only what a fresh reader needs](https://github.com/nedsnodes/nedsnodes/pull/4628) launches each Claude cell with `--setting-sources user,project --disable-slash-commands --tools Read,Grep,Glob,Write,WebFetch` and without `CLAUDE_CODE_TASK_LIST_ID`, which keeps out the launching agent-seat's `CLAUDE.local.md`, its task list, slash commands and unused tool definitions. It does not keep out Claude Code's auto-memory.

The real test launch made for that pull request on ned-box on 2026-11-24, session `f5980c53-fa7a-4011-8ed7-6dfff2de39a7`, transcript `nedlern@ned-box:/home/nedlern/.claude/projects/-home-nedlern-Projects-nedsnodes--claude-worktrees-cold-read-claude-cell-launches-with-only-project-and-user-settings-its-five-tools-no-slash-commands-and-no-task-list-topic-branch/f5980c53-fa7a-4011-8ed7-6dfff2de39a7.jsonl`, carries two things from auto-memory:
- the auto-memory instructions, which tell the session to save memories in `/home/nedlern/.claude/projects/-home-nedlern-Projects-nedsnodes/memory/`;
- that directory's index, `MEMORY.md`, which today holds only its heading, "# Memory index".

## Why it matters

A cell holds the Write tool, so the instructions invite it to write memories. Anything any agent-session later saves in that directory's index reaches every Claude cell launched from a checkout of this repository on ned-box, so cells would no longer read as a reader new to the project. Nothing has been saved there yet, so no cold-read report has been affected so far.

## What to do

Whether Claude cold-read-cells should run without auto-memory is the user's decision, because the approval he gave for pull request 4628, item 26 of 41 of approval-walk nodes-design-open-questions-2026-11-23, named only the three flags. The agent-seat MD-skills brings it to him as a new item in that approval-walk. If he approves, the Claude cell launcher in `nn-systems/cold-read/cold-read-claude-cell.py` switches auto-memory off for every Claude cold-read-cell, with a test in `nn-systems/cold-read/tests/cold-read-cell-common-test.py` that fails when the launcher does not pass the setting that switches auto-memory off. Claude Code 2.1.331's `claude --help` lists auto-memory among what its `--bare` option switches off, together with other things such as `CLAUDE.md` auto-discovery, so `--bare` cannot be used as it stands: the change has to find a way that keeps `CLAUDE.md`, and a real launch has to show that `CLAUDE.md` still loads while the memory instructions and `MEMORY.md` do not. If Claude Code offers no such way, the agent that takes this issue tells the user so and records it in this GHI-MD. If he declines, record his ruling in this GHI-MD and close the issue as not planned.
