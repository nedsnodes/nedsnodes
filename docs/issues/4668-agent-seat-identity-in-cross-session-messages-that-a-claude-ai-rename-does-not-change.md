---
issue: "[Agent-seat identity in cross-session messages that a claude.ai rename does not change](https://github.com/nedsnodes/nedsnodes/issues/4668)"
---

# Agent-seat identity in cross-session messages that a claude.ai rename does not change

## What is wrong

A cross-session message names its agent-seat only by `from-name`, the sender's Remote Control name, the name its session shows in claude.ai's Remote Control list. Its `from` attribute is a session id, which changes at every session-handoff. Since PR [Carry a claude.ai rename to the successor and tell the other agent-seats](https://github.com/nedsnodes/nedsnodes/pull/4493) merged, the user can rename an agent-seat in claude.ai, and its later agent-sessions launch under the new name, so the `from-name` of its messages changes too.

A program that recognises an agent-seat by its `from-name` then stops matching. Today one program does: `nn-systems/general-tools/pull-request-follow-up-request-from-merge-lane-2-message-save-and-forked-subagent-brief-hand-over-user-prompt-submit-hook.py` matches only `from-name="merge-lane-2"`. If the user renames merge-lane-2, a `#follow_up_request` from it is shown to the author as text but never saved, so its findings can be lost. The hook cannot match the stored name instead: it also runs on the Mac, and the stored name, in `~/.claude/handoffs/<agent-seat>-remote-control-name`, is kept on ned-box.

Until this is fixed, the user should not rename merge-lane-2. The open PR [Remote Control name store: launched session only, one directory, successor resends the rename line](https://github.com/nedsnodes/nedsnodes/pull/4664) adds a comment above the hook's `MERGE_LANE_2_SENDER_PATTERN` that says a rename of merge-lane-2 makes the hook save nothing.

## Root cause

No identity that stays the same across a rename, and that both machines can read, travels with a cross-session message or can be looked up from one.

## What to do

Give the programs that read cross-session messages an agent-seat identity that a rename does not change and that both machines can read, and have every program that recognises a sender by `from-name` match on it. GHI [A small HTTP service with SQLite on ned-box keeps one record of every agent-seat on both machines](https://github.com/nedsnodes/nedsnodes/issues/972) designs such a record; to serve here, it would also need to map a session id or Remote Control name to its agent-seat. Add an nn-test-suite case that fails when tracked code matches a literal `from-name="<agent-seat name>"`, so that no program matches on a name again, and rewrite the comment above `MERGE_LANE_2_SENDER_PATTERN` to match.
