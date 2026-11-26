---
issue: "[Make the guarded-file hook approve an allowed Edit of an outside file when another agent-session's run sees the Edit's result first](https://github.com/nedsnodes/nedsnodes/issues/4973)"
---

# Make the guarded-file hook approve an allowed Edit of an outside file when another agent-session's run sees the Edit's result first

## What happened

The store log for merge-lane-1's seat-brief, `nedlern@ned-box:/home/nedlern/nedsnodes-logs/guarded-file-versions-and-approvals/ned-box/home/nedlern/agents/merge-lane-1/CLAUDE.local.md/log`, lines 96-103, written on ned-box on 2026-11-26 (UTC):

- Line 96, 02:08:57.94Z: `seen` version `725a51d0c0ec`, with no approval, by session `7f0b75cb-de60-4c28-9220-290f2cb5b4ac`, an agent-session of agent-instructions-editor (its transcript is `/home/nedlern/.claude/projects/-home-nedlern-agents-agent-instructions-editor/7f0b75cb-de60-4c28-9220-290f2cb5b4ac.jsonl`).
- Lines 97-102, 02:08:58Z to 02:09:10Z: six `reminded` lines for that version, the first by merge-lane-1's session `cfaf8c9b-73b7-474e-b511-f1e5b3323fa3`, the others by five more agent-sessions.
- Line 103, 02:09:17Z: `approved` from the command line, as the user's approval.

merge-lane-1's transcript, `/home/nedlern/.claude/projects/-home-nedlern-agents-merge-lane-1/cfaf8c9b-73b7-474e-b511-f1e5b3323fa3.jsonl`, shows what led to it:

- Lines 666-667, 02:08:50Z: merge-lane-1 writes the user's approval words into `/home/nedlern/agents/merge-lane-1/.walk-approved`.
- Line 678, 02:08:57.305Z: merge-lane-1's Edit of `/home/nedlern/agents/merge-lane-1/CLAUDE.local.md`, made on version `437f0bf7`, which the store's `approved` file lists. `instruction-file-guard.py` let the Edit through and consumed the marker (lines 370-378 of that file on main, through `consume_approval_marker` in `.claude/guard-hooks/guard-approval-marker-common.py`).
- Lines 681-682, 02:08:58Z: merge-lane-1's own PostToolUse run of the hook does not approve the Edit's result; it only reminds that the file "still holds version 725a51d0c0ec…, which the user has not approved".
- Line 700, 02:09:01Z: `--approve` is refused, because the marker is gone: "there is no approval in /home/nedlern/agents/merge-lane-1/.walk-approved".
- Lines 740 and 749, 02:09:17Z: the marker is absent; merge-lane-1 writes the user's words into it again, and `--approve` then succeeds.

So agent-instructions-editor's run, after some tool call of its own, scanned the file 0.6 s after merge-lane-1's Edit and before merge-lane-1's own run, and recorded the Edit's result as seen and unapproved. An Edit the guard had allowed with the user's approval was then reminded about by every agent-session on the machine, and the approval had to be written into the marker a second time.

## Reproduction

`nedlern@ned-box:/home/nedlern/nedsnodes-logs/seats/merge-lane-1/guarded-file-hook-pr-4916-outlive-findings-reproduction/repro_4916.py` runs the hook as a program, in a temporary directory with a temporary store, home, agents directory and outside state (the hook's test variables `GUARDED_FILE_VERSIONS_*`). Its first case writes a seat-brief, lets a first run stock it, changes it as an Edit would, and then:

- with no other run in between, runs the hook as session A's PostToolUse for an `Edit` of that file: the new version is logged `seen … how=edit` and approved;
- with session B's run first, after a `Read`: B's run logs the new version `seen` with no approval and asks; A's Edit run then logs `reminded` and approves nothing.

Run as `python3 -I repro_4916.py <checkout>`, it gives this on origin/main at 157731f5 (`output-at-origin-main-157731f5.txt` in the same directory) and on pull request [#4916](https://github.com/nedsnodes/nedsnodes/pull/4916)'s head a852a6d1 (`output-at-pr-4916-head-a852a6d1.txt`):

```
  other session first=False: v1 approved=True
  other session first=True: v1 approved=False
```

## Root cause

`.claude/guard-hooks/guarded-file-unapproved-change-afterward-backup-and-ask-hook.py` keeps the outside group's state (`~/.claude/CLAUDE.md`, `~/.claude/settings.json`, and every agent-seat's `CLAUDE.local.md` and `.claude/settings.local.json`) in one file per machine, `~/.cache/guarded-file-unapproved-change-afterward-backup-and-ask-hook/guarded-file-unapproved-change-afterward-backup-and-ask-hook-state.json` (`outside_state_path`, line 761 on main), which every agent-session's run scans after every tool call. The Edit rule approves a version only in the run whose own tool call wrote it (`elif edit_succeeded and written == path: how = HOW_EDIT`, line 1429). Whichever run first sees a new version records it, so when that run belongs to another agent-session the version is logged as seen and unapproved, and `approval_takes` then lets only the user's yes approve it. Since pull request [#4860](https://github.com/nedsnodes/nedsnodes/pull/4860) (commit a9ca65781, 2026-11-25) put every agent-seat's files in the outside group, every agent-session on the machine races the editing session for them; before it, `~/.claude/CLAUDE.md` and `~/.claude/settings.json` were already exposed the same way. The design, GHI [#1268](https://github.com/nedsnodes/nedsnodes/issues/1268) (`docs/issues/1268-catch-a-guarded-file-changed-without-the-user.md`), approves an Edit through the hook run after it (§ The approved set, way 2) and does not describe this race.

## Why it matters

Each time the race is lost, an Edit the guard allowed is reminded about by every running agent-session until someone records the approval by hand, and the agent that made it must put the user's approval into `.walk-approved` again, though the guard already consumed it. An agent reading the reminder can also take the approved change for an unapproved one and put back the old version. With a dozen agent-sessions on ned-box running tool calls every few seconds, the race is lost in ordinary use.

## What to do

The agent-seat reboot-test, which owns the hook, makes a successful write by one of the tools the guard checks (`FILE_WRITING_TOOLS`: Edit, Write and NotebookEdit) approved whichever agent-session's run first sees its result. The fix covers the outside files; a checkout's own guarded files have the same race when two agent-sessions run in one checkout, whose state file is shared too, and the fix covers them as well if the same mechanism does. One way: the PreToolUse guard, when it lets such a write to a guarded file through, records the path, the session and the version the write is made on; any run that then sees a new version of that path applies the Edit rule, including its check that the version written on was approved, from that record rather than from its own tool call. The record must not approve anything once the write it names has failed or once a different write has changed the file, so that a shell command run after a failed Edit is still asked about. reboot-test chooses the design, writes it into #1268, and adds a test to `.claude/guard-hooks/guarded-file-unapproved-change-afterward-backup-and-ask-hook-test.py` that has a second session's run see the Edit's result first and fails before the fix; the reproduction's first case can serve as its start. The pull request cites this issue in its `#root_cause` line.
