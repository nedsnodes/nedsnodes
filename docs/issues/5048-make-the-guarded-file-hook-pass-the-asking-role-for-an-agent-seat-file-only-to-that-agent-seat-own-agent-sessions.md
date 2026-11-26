---
issue: "[Make the guarded-file hook pass the asking role for an agent-seat file only to that agent-seat's own agent-sessions](https://github.com/nedsnodes/nedsnodes/issues/5048)"
---

# Make the guarded-file hook pass the asking role for an agent-seat file only to that agent-seat's own agent-sessions

## What is wrong

`.claude/guard-hooks/guarded-file-unapproved-change-afterward-backup-and-ask-hook.py` copies every unapproved version of a guarded file and names one agent-session in the backup directory's log as the asking agent-session: the one that asks the user to approve or restore the version. The asking agent-session gets the full request and then a reminder after every tool call; every other agent-session that sees the file gets the reminder once. Both texts carry the line "If you are any other subagent, stop: make no further edit, and report the change to the agent that dispatched you instead of asking the user." (`ASK_INSTRUCTIONS` and `UNAPPROVED_VERSION_REMINDER_MESSAGE`, lines 153-188 on main at 783e295c0).

On ned-box, when the asking agent-session ends, the role passes to whichever agent-session's tool call runs the hook next, in any agent-seat. That agent-session then shows the reminder after every tool call, and each of its subagents that is not the one fixing the file stops at its next tool call. One agent-seat's unapproved change to its own seat-brief thereby moves from agent-seat to agent-seat across ned-box and stops unrelated work.

## Evidence

The log for `/home/nedlern/agents/pr-review-maintenance-findings-batch-fix-agent/CLAUDE.local.md`, at `nedlern@ned-box:/home/nedlern/nedsnodes-logs/guarded-file-versions-and-approvals/ned-box/home/nedlern/agents/pr-review-maintenance-findings-batch-fix-agent/CLAUDE.local.md/log`, records version `4fa570e96c97f8d7f8abc3640fafd17025398763` of that seat-brief. Its `seen` and `asking` lines name these asking agent-sessions, in order (times UTC; each agent-session's agent-seat is the transcript directory under `/home/nedlern/.claude/projects/` that holds its `<session id>.jsonl`):

| Became the asking agent-session | Agent-session | Agent-seat | Last transcript entry of the agent-session it replaced |
|---|---|---|---|
| 2026-11-25 22:22:35, first saw the version | `fa5f85a4` | pr-review-maintenance-findings-batch-fix-agent | — |
| 2026-11-25 23:17:10 | `ebf05918` | pr-review-maintenance-findings-batch-fix-agent | 2026-11-25 23:15:52 |
| 2026-11-26 01:32:49 | `71b37fc6` | merge-lane-1 | 01:32:47 |
| 2026-11-26 01:44:47 | `49eafa97` | merge-lane-3 | 01:44:46 |
| 2026-11-26 04:02:13 | `d8e5b750` | MD-skills-2 | 04:02:10 |
| 2026-11-26 04:57:59 | `d6f55943` | overall-cleanup | 04:57:57 |
| 2026-11-26 06:20:29 | `cfaf8c9b` | merge-lane-1 | 06:20:09 |
| 2026-11-26 06:34:16 | `783ddf8d` | agent-instructions-editor | 06:34:12 |

Each hand-over came seconds after the previous asking agent-session's last transcript entry, so the hook's test of whether the asking agent-session has ended worked; the defect is in who receives the role. The owning agent-seat's next agent-session, `f89ca850`, whose transcript starts at 01:34:01, came about a minute after merge-lane-1 had taken the role, and was reminded once, at 01:34:07.

In agent-instructions-editor's agent-session `783ddf8d`, the full request reached subagent `a0557752db3374b17`, then building pull request 5035, at 06:34:16, and the reminder followed every later tool call of that subagent and of subagent `a484ce2aa4c8af6e1`, closing GHI 4245 (transcripts under `/home/nedlern/.claude/projects/-home-nedlern-agents-agent-instructions-editor/783ddf8d-fd3b-4987-9518-69dea77b636f/subagents/`). Subagent `a324de2e868b0d6ea`, dispatched at 06:54:50 to follow up pull request 4897, reported "I made no edits and stopped before `start-topic-branch`", citing the reminder. The log's `restored` line at 06:55:59 shows the version was put back with `--restore` from a command line.

## Root cause

Three parts of the hook combine, all on main at 783e295c0:

- `agent_seat_files()` (line 805) and `run_hook` (lines 1272-1274) put every agent-seat's seat-brief and `.claude/settings.local.json` in the files every invocation of the hook compares, from any working directory, as the user-ruling of 2026-11-25 (item 66, cited in GHI 1268's GHI-MD) asks.
- `store_phase` hands the role over at line 1096, for a file whose content changed since the agent-session's last invocation, and at lines 1112-1116, for a file left unsettled: when the asking agent-session's claude process has ended (`owner_alive`, line 1001), the current agent-session writes an `asking` line and takes the role. Neither condition asks whether the current agent-session belongs to the agent-seat whose file changed.
- Lines 1117-1118 then remind the new asking agent-session after every tool call, and a subagent's tool calls carry its parent's `session_id` (line 1255), so the stop line reaches every subagent of that agent-session.

GHI [Catch a guarded file changed without the user's approval, ask him, and keep every version](https://github.com/nedsnodes/nedsnodes/issues/1268), whose GHI-MD is `docs/issues/1268-catch-a-guarded-file-changed-without-the-user.md`, says in step 3 of "What it does when a file changes" that "when the log's asking session has ended, the first session to see the unsettled file is logged as the new asking session". That rule was written when a successor was "a new session in the same checkout"; the 2026-11-25 user-ruling made every agent-session on ned-box see every agent-seat's files, and the rule was not narrowed to match.

## Proposed fix

The fix changes a guard hook and GHI 1268's design, so it waits for the user's approval. An agent-seat file here means one of the files `agent_seat_files()` returns: an agent-seat's seat-brief, `CLAUDE.local.md`, or its `.claude/settings.local.json`, under the agents directory that function uses (`~/agents/`, or the directory the tests set in `GUARDED_FILE_VERSIONS_AGENTS_DIRECTORY`). The owning agent-seat is the agent-seat whose agent-home holds the file.

1. In `store_phase`, only an agent-session of the owning agent-seat may become the asking agent-session for an agent-seat file: on the first sighting (`asking is None`, line 1096) and at both hand-over points (lines 1096 and 1112-1116). Any other agent-session is treated as when the asking agent-session is still running: reminded once, with no `asking` line written, and its `seen` line does not make it the asking agent-session. `~/.claude/CLAUDE.md` and `~/.claude/settings.json` belong to no agent-seat and keep today's rule.
2. An agent-session belongs to the owning agent-seat when the directory it started in is that agent-seat's agent-home or a directory under it, such as a topic worktree under `.claude/worktrees/`. The hook reads that directory from the payload's `transcript_path`, whose project directory is the starting directory with each `/` written as `-`, or from the payload's `cwd`; the build picks one and compares paths after resolving symbolic links.
3. While the owning agent-seat has no running agent-session, no agent-session asks; the change stays in place, the hook's copy is kept, and the agent-seat's next agent-session becomes the asking agent-session at its first tool call. Each other agent-session is still reminded once.
4. Add tests to `.claude/guard-hooks/guarded-file-unapproved-change-afterward-backup-and-ask-hook-test.py`: an agent-session of another agent-seat that first sees the version, or that runs after the asking agent-session ended, is reminded once and writes no `asking` line; an agent-session of the owning agent-seat, working in its agent-home or in a topic worktree under it, becomes the asking agent-session; for `~/.claude/CLAUDE.md`, an ended asking agent-session still hands the role to any agent-session.
5. Change step 3 of "What it does when a file changes" in GHI 1268's GHI-MD to state the narrowed rule.

Outside this GHI: whether the once-only reminder to other agent-sessions should keep the stop line, and whether the hook should tell the user when the owning agent-seat has no running agent-session, as for an agent-seat that was retired. A later change could also send the stop line only to a subagent's tool calls, if the hook payload names the subagent (unverified that Claude Code's PostToolUse payload carries an `agent_id` field).

## Next action

Put the proposed fix to the user in an approval-walk. If he approves, build it on an nn-topic-branch cut from `origin/main`, with the tests in step 4 of the fix and the GHI 1268 change in the same pull request.
