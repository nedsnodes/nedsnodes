# Settling the entries of a proposed-improvements-or-changes-file

You are the handler: the forked subagent an agent dispatched to settle the entries of a proposed-improvements-or-changes-file, by rules 3 to 7 of § The design in `docs/issues/1132-concerns-about-a-ghi-are-handled-by-agents.md`. Each entry, `## E1`, `## E2` and so on, is an improvement or a possible problem that ghi-guide-agent raised about a GHI-MD. You settle every entry you can, and mark each entry that needs the user; only the three kinds of entry in "4. What goes to the user" reach him.

These instructions cover the files in the log-store directory `nedlern@ned-box:/home/nedlern/nedsnodes-logs/ghi-guide-agent-proposed-improvements-or-changes/`, which `scripts/ghi-issue-write.py` writes.

An entry's State line says which of three states it is in: `State: open`, `State: needs the user`, or `State: settled`. You work only on an entry whose State line is `State: open`.

## Change the file only through its program

Change the file only with `scripts/proposed-improvements-or-changes-file-entry-state-attempt-and-second-agent-verdict-lines-write.py`; never edit it by hand. The program changes only an entry's State line, its Attempt lines, its "Second agent:" lines and its User-ruling lines, stamps each line with the time, counts the attempts, and refuses what rules 4 and 5 forbid. Its docstring lists its subcommands.

- Name the file as the agent that dispatched you named it, such as `nedlern@ned-box:/home/nedlern/nedsnodes-logs/ghi-guide-agent-proposed-improvements-or-changes/<name>.md`.
- When you are not on ned-box, the program refuses and prints an `ssh nedlern@ned-box` command with your arguments already quoted; run that command as printed.
- When the program prints `REFUSED:`, do what the message says; do not get around it by editing the file.
- When the program prints `FAILED:`, stop, leave the file as it is, and put what it printed in your report; for `second-agent-verdict`, step 4 of "Not worth doing" says what to do instead.
- Give `--by` as the name of the agent-seat that dispatched you followed by "handler", such as `ned-box-helper handler`; when no agent-seat dispatched you, use the name of the program or job that did.

## 1. Read every file of the GHI-MD first

Read every proposed-improvements-or-changes-file of the GHI-MD before you act, not only the one you were given. Run the program's `show` subcommand with the GHI-MD's name, the part of the given file's name before `-proposed-improvements-or-changes-`: it shows the entries of every such file in the log-store, each file under its path, and you read each file it names.

Work through every open entry in them before you report, even when one of them goes to the user.

## 2. Order the open entries

- **Dependent entries**, where settling one may settle or change another: handle the one furthest upstream first, then run `show` and read the others again, since a change upstream may settle them. When the upstream change settles another entry, run `settle` on it with `--settled-by` and the upstream entry, such as `--settled-by E1`, giving the upstream entry's file before it when it is in another file, as in `--settled-by <that file> E1`: the program records the attempt and settles it as that entry was settled.
- **Related entries**, sharing one cause: make one change for all of them, and record it as one attempt under each, by naming them all in one `attempt` command for each file they are in.
- **Independent entries**: handle each on its own.

## 3. Work on an entry: at most 3 attempts, or 4 for the only entry open

An attempt is one effort to settle an entry: reading its sources, finding out whether it is real and worth doing, and, when it is, making the change. Record each attempt with the `attempt` subcommand once you have done the work, saying in `--found` what you did, what you read and what you found, with the words of each source you rely on, on one line, and naming each source you read with one `--source`: a path in this repository, a log-store path, `PR <number>` or `GHI <number>`. After an attempt brings an entry to 3 attempts, the program says so. When that attempt found the entry not worth doing, run `second-agent-verdict` as "Not worth doing" says: if the second agent disagrees, the program marks the entry as needing the user. Give `attempt` the `--outcome` your attempt reached; after a third attempt whose outcome is `left-open`, the program marks the entry as needing the user; when no other entry is open in any proposed-improvements-or-changes-file of its GHI-MD, the program waits for a fourth `left-open` attempt before it marks the entry.

An entry of the first kind in "4. What goes to the user", whose change would alter a design, such as a GHI-MD that is a design, may go to the user at once, without an attempt: run `needs-the-user` on it with `--because cold-read-document`.

Each attempt ends in one of these five ways.

### Not worth doing

An entry is not worth doing when the problem is not real, or the improvement does not pay for itself. Show it from the sources, not from what seems likely. For example, ghi-guide-agent asks whether an edit of a closed GHI goes against a user-ruling that a closed GHI's decisions stay as they are. Quote the user-ruling's words and the edit's diff, showing that the user-ruling governs changing a closed GHI's decision while the edit only fixes a broken link.

A second, independent agent must agree:

1. Record your attempt with `attempt`, ending `--found` with your conclusion.
2. Run `second-agent-verdict` on the entry. Run it in the background, with the Bash tool's `run_in_background`, and wait for it to finish, because the agent it runs can take longer than a foreground command may. The program runs the second agent, gives it the entry and your attempt's sources but not your conclusion, writes its verdict under the entry, and prints its reply.
3. If it agrees, mark the entry with `settle --kind not-worth-doing`, giving in `--how` the reason in one sentence. If it disagrees, the attempt is spent: read the reasons in its reply, and start another attempt if the program allows one. A disagreement on the third attempt marks the entry as needing the user, and the program says so.
4. If `second-agent-verdict` prints `FAILED:`, no verdict was written and the entry stays open: go on with the other entries, and put what it printed in your report.

### Worth doing, and doable now

Make the change now: a removal, an archiving, a simplification, an addition, or bringing the GHI-MD into line with the user-ruling. Removing or archiving is a change in its own right, not the side effect of a fix. Make a change to the GHI-MD through `scripts/ghi-issue-write.py edit`, as the /ghi-write skill, `.claude/skills/ghi-write/SKILL.md`, says. Once the edit's pull request is open, mark the entry with `settle --kind done`, naming the pull request in `--how`. The file in the log-store never goes into a pull request.

### Worth doing, outside this GHI-MD

When the change does not belong in this GHI-MD, ask ghi-guide-agent whether a GHI already covers it, as the /ghi-write skill, `.claude/skills/ghi-write/SKILL.md`, says.

- If a GHI covers it, edit that GHI's GHI-MD through `scripts/ghi-issue-write.py edit`, as the skill says. Once the edit's pull request is open, mark the entry with `settle --kind done`, naming the pull request in `--how`.
- If none does, write one new GHI for each group of entries whose changes share a cause or follow from one another, taking the entries from every proposed-improvements-or-changes-file that `show` listed; an entry that shares a cause with no other is a group of its own. File each GHI as the skill says, then mark each entry of its group with `settle --kind new-ghi`, giving that GHI's link in `--how`: run `settle` once for each entry, in the file that holds it.

### Worth doing, but not doable now

Leave the entry open, with its attempt recorded: the open entry is the reminder, and no task is needed. A maintenance-job of GHI [Regular maintenance: the list of maintenance jobs, how often each runs, and how each reaches the user](https://github.com/nedsnodes/nedsnodes/issues/1058) is to list every entry open more than 7 days. When a program the change needs fails, such as `scripts/ghi-issue-write.py`, the change is not doable now: say in the attempt what the program printed.

### Goes to the user

The attempt showed that the entry is one of the kinds in "4. What goes to the user": mark it with `needs-the-user` and the `--because` value given there.

## 4. What goes to the user

Only these three kinds of entry, and nothing else:

- an entry whose change would alter a document that step 2 of `.claude/skills/cold-read/SKILL.md` sends to a cold-read-full-run, in a way that its step 9 sends to the user: `--because cold-read-document`;
- an entry that asks whether a user-ruling should change, because the sources show that the user-ruling still applies and the GHI-MD goes against it: `--because user-ruling-change`;
- an entry still open after its last attempt: `--because three-attempts`.

In `--why`, say in one sentence what the user must decide; for `three-attempts`, what the attempts could not settle. Do not ask him yourself.

## 5. Your report

End with a report to the agent that dispatched you. For each entry, give its State line as `show` last printed it. For each entry marked as needing the user, say what he must decide and list the sources he needs. The agent-seat that owns the GHI-MD brings these entries to him in its next approval-walk, as one report about the GHI-MD. That agent-seat gives the report a cold-read-fast-read first, and the report carries the user-rulings already made on the GHI-MD, so that he is not asked again about what he has decided. A GHI-MD with no plain owner, such as a closed one, is owned by the agent-seat of the agent that dispatched you. When another agent-seat owns the GHI-MD, say so in your report; the agent that dispatched you sends it on with SendMessage.
