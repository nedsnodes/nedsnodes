---
issue: "[Make the guarded-file hook's outside-group stocking keep what earlier runs recorded about an outside file](https://github.com/nedsnodes/nedsnodes/issues/4975)"
---

# Make the guarded-file hook's outside-group stocking keep what earlier runs recorded about an outside file

## Reproduction

`nedlern@ned-box:/home/nedlern/nedsnodes-logs/seats/merge-lane-1/guarded-file-hook-pr-4916-outlive-findings-reproduction/repro_4916.py` runs `.claude/guard-hooks/guarded-file-unapproved-change-afterward-backup-and-ask-hook.py` as a program in a temporary directory, with a temporary store, home, agents directory and outside state (the hook's test variables `GUARDED_FILE_VERSIONS_*`); it never touches the real store. Run as `python3 -I repro_4916.py <checkout>` on origin/main at 157731f5 and on pull request [#4916](https://github.com/nedsnodes/nedsnodes/pull/4916)'s head a852a6d1, it saved `output-at-origin-main-157731f5.txt` and `output-at-pr-4916-head-a852a6d1.txt` in the same directory. The hook checks files in two groups: the outside group, the files every run checks from any directory (`~/.claude/CLAUDE.md`, `~/.claude/settings.json` and every agent-seat's `CLAUDE.local.md` and `.claude/settings.local.json`), whose state is one file per machine; and the checkout group, the guarded files of the checkout the run is in, whose state is in that checkout's git directory. Stocking here means a run that approves an outside file's present version as `stock` without asking: the run that finds no outside state file, and the run that finds one without the key `agent_seat_files_stocked`.

Case 1, an Edit made on a version a run asked about (Codex finding fca71b8637ff in merge-lane-1's review [6068238058](https://github.com/nedsnodes/nedsnodes/pull/4916#pullrequestreview-6068238058) of #4916). A seat-brief's v0 is approved; a Bash command writes v1, and the hook asks about it; then an Edit made on v1 writes v2.

- With the outside state in place, the Edit's run asks about v2. That is the design's rule: an Edit made on an unapproved version adds nothing.
- With the outside state file deleted before the Edit, the Edit's run logs v2 `seen … how=stock`, approves it, and says nothing. The same happens for a path with no approved version whose v1 an older checkout run asked about, both with no outside state file and with one that lacks `agent_seat_files_stocked`. Main and #4916's head give the same results. In the output below, the third line is the path with no approved version (`fca` names Codex finding fca71b8637ff), with an outside state that lacks `agent_seat_files_stocked`.

```
  outside state missing=False: v2 approved=False
  outside state missing=True: v2 approved=True
  fca never-approved: v2 approved=True asked=False
```

Case 2, a log that keys the file by git's filtered blob id (Codex finding bd2b0859acb7, same review). Before pull request [#4860](https://github.com/nedsnodes/nedsnodes/pull/4860) (commit a9ca65781, 2026-11-25), an agent-seat file was checked by its own checkout's group, which keys a version by `git hash-object --path`, with line-ending filters applied; the outside group keys the same file by its raw bytes (its hash function returns nothing, line 1309 on main, and the stocking block hashes raw bytes, line 1383). The case writes a CRLF seat-brief whose log holds only the filtered id, then runs the first outside run with an outside state that lacks `agent_seat_files_stocked`; a control does the same with LF bytes, whose filtered and raw ids are equal.

- Filtered id approved before: the CRLF file is asked about again, under its raw id, though the user approved those bytes; the LF control is not. Main and #4916's head give the same results.
- Filtered id asked about before: the CRLF file is approved as `stock`. On #4916's head the LF control stays asked about, so there the filter causes it; on main the LF control is approved too, because main's stocking approves an asked-about version whatever its bytes, the defect #4916 fixes.

```
                                                main   #4916 head
  CRLF, filtered id approved before: asked      yes    yes
  LF control, approved before: asked            no     no
  CRLF, filtered id asked about before: approved yes   yes
  LF control, asked about before: approved      yes    no
```

## Whether it happens in real use

Stocking is rare. On ned-box the outside state file, `/home/nedlern/.cache/guarded-file-unapproved-change-afterward-backup-and-ask-hook/guarded-file-unapproved-change-afterward-backup-and-ask-hook-state.json`, exists and holds `agent_seat_files_stocked: true`, so ned-box stocks again only if that file is lost. A machine whose hook has not run since #4860 merged stocks at its next run; the Mac's state was not checked (unverified). Case 2 also needs a line-ending filter: on ned-box, `git config core.autocrlf` is unset globally and in every `~/agents/*` checkout, no agent-seat's `CLAUDE.local.md` or `.claude/settings.local.json` holds a carriage return (`grep -l $'\r'` found none), and none is tracked by git (`git ls-files --error-unmatch` in each checkout found none).

## Why it matters

In case 1 and the second half of case 2, a version the user never approved enters the approved set without anyone being asked, and the hook stops reminding about it; the store keeps the copy and the log marks it `stock`, so it can be found and undone, but nothing points anyone to it. In the first half of case 2, the user is asked again about bytes he already approved.

## Root cause

Stocking decides from the present bytes alone, under a key computed a different way from the one earlier runs recorded, and without the rules those runs applied: the `elif stocking` branch (line 1425 on main) gives `HOW_STOCK` before the Edit rule's branch (line 1429) is reached, so the Edit rule's check of the version the Edit was made on never runs, and the key it compares with the log is the raw-byte id, which a log written by a checkout run under a filter does not hold. The design, GHI [#1268](https://github.com/nedsnodes/nedsnodes/issues/1268) (`docs/issues/1268-catch-a-guarded-file-changed-without-the-user.md`), § The approved set, says a version a run saw unapproved enters the approved set only by the user's yes, by origin/main or as a deletion, and that an Edit made on an unapproved version adds nothing.

## What to do

The agent-seat reboot-test, which owns the hook and #4916, makes stocking keep what the path's log records, at every place that approves as `stock` (on main, the agent-seat block at lines 1379-1386 and the `elif stocking` branch at line 1425; #4916 changes both):

- An Edit's result goes through the Edit rule rather than being stocked. The version the Edit was made on is the one the outside state names, or, when the state has no entry for the path, the last version the path's log records as seen, as #4916's `store_phase` takes it; when that version is not approved, the Edit's result is asked about.
- A version the log records under git's filtered blob id counts as the same version as its raw bytes, both for approval and for asking. reboot-test chooses how, for example by having `log_seen` record both ids, or by one lookup that every comparison with the log calls; and decides which id `approved`, the log, the copies, `--approve` and `--restore` use from then on.

One way to cover every such place at once: refuse, where a version enters the approved set, any approval other than the user's yes, origin/main or a deletion for a key the path's log records as seen and not approved. The work builds on #4916 once it merges, since #4916 replaces main's stocking block. The pull request adds to `.claude/guard-hooks/guarded-file-unapproved-change-afterward-backup-and-ask-hook-test.py` one test for each wrong result above, four in all: the two in case 1, and the two CRLF rows of case 2 that the LF control does not share at #4916's head; each fails before the fix. It cites this issue in its `#root_cause` line. Before that, reboot-test checks on the Mac whether `~/.cache/guarded-file-unapproved-change-afterward-backup-and-ask-hook/guarded-file-unapproved-change-afterward-backup-and-ask-hook-state.json` exists and holds `agent_seat_files_stocked`; when the Mac has already stocked, it reads the `stock` lines its stocking run wrote in the Mac's store and brings the user any version among them that a run had asked about.
