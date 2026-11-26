---
issue: "[Analyze the handoff files to find ways to make session-handoffs better](https://github.com/nedsnodes/nedsnodes/issues/4337)"
---

# Analyze the handoff files to find ways to make session-handoffs better

## Why

Every agent-seat's agent-session hands off to a successor when its context fills, so a session-handoff that loses a fact, carries a stale instruction or costs extra tokens repeats across the agent-seats. Nobody has yet read the files that session-handoffs leave behind to measure how well they work. On 2026-11-23 the user asked for this work: "At some point, we probably will look at them and to analyze our handoffs and make them better. Maybe file a GHI for that. If there isn't one already, you can ask the GHI agent to analyze the handoff files and look for optimizations."

GHI [Low priority: handoff-quality instrumentation (deferred — ladder not earned; interim = narrated correction summary)](https://github.com/nedsnodes/nedsnodes/issues/6) proposed measuring handoff quality with new machinery. It was closed on 2026-09-21 as not planned, because the handoff ceremony it measured had been retired, and it said to re-file against the handoff-system as it now stands if the measurement is wanted. What has changed since: the handoff-system now leaves two months of files on ned-box, so this work can read what already exists and needs no new instrumentation.

## What to read

All of these are on ned-box, in `~/.claude/handoffs/` unless stated. The counts are from 2026-11-23, when the folder held 1,941 files and 12 MB; its other 70 files are not handoff records and are left out. The Mac's copies are mirrored to `/home/nedlern/nedsnodes-logs/agent-session-files-by-machine/mac/handoffs/` and `.../mac/projects/` on ned-box.

- 700 next-step files, `<agent-seat>-next-step-<date>-<time>.md`, dated from 2026-09-22 to 2026-11-22. Each holds the next step a retiring agent-session wrote for its successor.
- 32 session-handoffs: 11 latest, `<agent-seat>-handoff.md`, and 21 earlier, `<agent-seat>-handoff-<number>.md`.
- 21 pairs of dialogs, `<agent-seat>-dialog-<number>.md` and `<agent-seat>-dialog-<number>-complete.md`.
- 1,097 marker files, which record per agent-session that a handoff was asked for or deferred: 650 `<session ID>-handoff-asked`, 234 `<session ID>-handoff-deferred` and 213 `<session ID>-handoff-deferred-fired`. An approval-walk item open on 2026-11-23 proposes moving them to `~/.claude/handoffs/session-marker-files/`.
- The transcripts of the retiring agent-session and its successor, `~/.claude/projects/<directory named for the agent-seat's checkout>/<session ID>.jsonl`, which show what the successor actually did with what it was given.

## What to find out

For the session-handoffs the program in the next section samples:

1. What did the successor have to rediscover, or ask for again, because the session-handoff left it out?
2. What did the session-handoff tell the successor that was already stale or wrong? GHI [A session-handoff's next step carries forward a step that a later ruling or skill change removed](https://github.com/nedsnodes/nedsnodes/issues/2412) is one such defect; do not re-report it.
3. What in the session-handoff and the successor's initial-agent-instructions did the successor never cite or act on, and about how many tokens is that, counted per section?
4. How often was a handoff deferred, for how long, and what held it up?
5. Which of these could a program do or check, instead of an agent writing or remembering it?

## What to do next

Write a program that finds the files above by name, pairs each next-step file with its retiring and successor transcripts, lists any it cannot pair, draws a seeded sample of up to 10 per agent-seat, and computes what needs no judgment: deferral counts and durations, tokens per section, and which paths, commands, branches, GHIs and pull requests each session-handoff names and its successor then used. Give each sampled session-handoff and the program's output for it to a fresh agent, to judge what was lost, stale or unused. Write one report to the log-store, under `nedlern@ned-box:/home/nedlern/nedsnodes-logs/analysis/`, giving for each finding its evidence, by file and agent-session, how often it happens, and a proposed change. Bring the proposed changes to the user in an approval-walk. Build nothing until the user has decided on them.

If the analysis needs to read subagent events from transcripts, use the shared reader of GHI [One shared reader of a transcript's subagent start, resume and finish events for scripts/handoff-context-threshold-hook.py and nn-systems/handoff/handoff-write-and-check-supervisor.py](https://github.com/nedsnodes/nedsnodes/issues/3546) if it has been built, rather than writing another. GHI [Handoffs become one pending file per session, archived only after a successor is up](https://github.com/nedsnodes/nedsnodes/issues/754) proposes a change to where session-handoff files are stored, which is why the program finds them by name anywhere under `~/.claude/handoffs/`.
