---
issue: "[The file locator collapses `..` before following symlinks, so it and its backup search look for a cited path in the wrong directory](https://github.com/nedsnodes/nedsnodes/issues/5296)"
---

# The file locator collapses `..` before following symlinks, so it and its backup search look for a cited path in the wrong directory

## Reproduction

This was run on main at commit `aef6d2ef14ea`, on ned-box, by loading the locator, `scripts/locate-file-copies-across-machines.py`, as a module and calling its `resolve_query` function, which turns the path given as the query into the absolute path the locator searches.

1. Make a directory `fx` holding `real/inner/`, a symlink `fx/link` that points to `real/inner`, and a file `fx/real/notes.md`.
2. Call `resolve_query("<fx>/link/../notes.md")`. It returns `<fx>/notes.md`.
3. Call `os.path.realpath("<fx>/link/../notes.md")`. It returns `<fx>/real/notes.md`, and `os.path.exists` on the given path returns True: the system opens `fx/real/notes.md` for that path.
4. Call `resolve_query("fx/link/../notes.md", cwd="<the directory holding fx>")`. It also returns `<fx>/notes.md`.
5. Call `resolve_query("nedlern@ned-box:~/link/../notes.md")`. It returns `/home/nedlern/notes.md` without looking at the file system, so a `~/link` that points to `real/inner` would have needed `/home/nedlern/real/notes.md`.

Steps 2 to 5 show the wrong path that the locator searches. That this path is also what the backup search receives was read from the code, not run. The backup search is `scripts/find-deleted-path-across-backups.py`, which the locator runs when its own search finds no copy. `main` passes the result of `resolve_query` (line 1123) to `search_and_report`, which passes it to `query_target` (line 1201); when nothing is found, line 1207 passes `target.get("canonical", target["path"])` to `run_backup_search_after_nothing_found`, which runs the backup search with that path.

A Codex review of pull request [find-deleted-path-across-backups: a path from the current directory resolves .. through a symlink as the system does](https://github.com/nedsnodes/nedsnodes/pull/4728), at that pull request's commit `8bed9504`, reproduced the same defect through the backup call itself. With a symlink test double and a captured backup call, it printed `direct: /fixture/real/notes.md` for the backup search run directly and `locator fallback: /fixture/notes.md` for the backup search run by the locator. Its report is `nedlern@ned-box:/home/nedlern/nedsnodes-logs/seats/merge-lane-2/merge-helpers/cx/pr4728-8bed9504/codex-code-review-report.md`, lines 13 to 18.

## What is wrong

`resolve_query` makes the query's path absolute with `os.path.normpath`, at line 195 for every path and at line 202 for a path relative to the current directory. `normpath` removes each `..` together with the component before it, as text. The system instead follows a symlink in that component first and climbs from the directory the symlink leads to. When a path runs a `..` through a symlink, the two give different directories.

Every later step uses the collapsed path: the locator's own search of both machines, and the backup search it runs when that search finds nothing. The component that `normpath` removed is not in the path the backup search receives, so the backup search cannot recover it, whatever resolution it does itself.

## Why it matters

The skills /find-missing-file and /find-info tell agents to run this locator before they say a file is missing. For a path that runs `..` through a symlink, the locator and its backup search look in the wrong directory, so they can report that no copy was found for a file that a backup does hold. An agent can then tell the user that a file is gone when it can be recovered. The locator only searches and writes nothing, so this defect changes and deletes no file.

The failure has not been seen in agents' real work; the only cases are the constructed ones above.

## Next action

Make the locator resolve each `..` in the query's path the way the system does, by following the symlinks before it, before the locator uses the path, with the same function the backup search uses rather than a second copy of it.

On main, the backup search has the same lexical collapse, in `_plain_path_from_cited_query` at lines 721 and 738. Pull request 4728, open at its commit `35a78c400`, changes that function to resolve a path through `_placed_as_the_system_places_it`, which resolves the parent directory with `os.path.realpath` and keeps the file name as given. It does this only for a path on the machine the program runs on, because another machine's symlinks cannot be read from there. The first finding in the same Codex report questions whether that resolution should apply to a path with no `..`, because a backup snapshot can hold a file under a directory that is a symlink today. So:

1. The owner puts this work on its task list, blocked on pull request 4728, and starts it when that pull request merges or closes.
2. When pull request 4728 has merged, move the resolution main then has into the locator, which the backup search already loads as the module `locator`, and have both `resolve_query` and the backup search call it in place of their `normpath` calls. When pull request 4728 has closed without merging, write that function in the locator in this work, resolving each `..` as the system does, and have both programs call it. For the locator's own search of the live file system, a path with no `..` names the same file whether or not its symlinks are followed, so the question the Codex finding raises matters only for the backup search.
3. For a path on the other machine, resolve its `..` on that machine, in the part of the locator that runs there over ssh. When that machine cannot be reached, the locator already reports it as not searched, and that report stands.
4. Add test cases to `scripts/locate-file-copies-across-machines-test.py` for each of the three forms in the reproduction: an absolute path, a path relative to the current directory, and a path on the other machine, each with `link` a symlink to `real/inner`. Each case checks both the path the locator searches and the path it passes to the backup search.

The agent-seat that owns this code could not be confirmed. Both of the locator's `normpath` lines came from commits `b80ac90e75` and `0b480ac5cc`, by the git author `mac-claude`, merged in pull request [A fast locator finds every copy of a file by name on both machines](https://github.com/nedsnodes/nedsnodes/pull/703). That pull request's description cites the session `https://claude.ai/code/session_01DrPeDT27wNBfT16nSwACDB` and the walk whose minutes are `nedlern@ned-box:/home/nedlern/nedsnodes-logs/walk/merge-lane-mac-helper-open-items-and-questions-2026-09-23-minutes.md`. Those minutes name the Mac's merge-lane agent-seat, then working as the Mac-side helper, as the walk's seat. Whether that agent-seat still runs, and under what name, is unverified.
