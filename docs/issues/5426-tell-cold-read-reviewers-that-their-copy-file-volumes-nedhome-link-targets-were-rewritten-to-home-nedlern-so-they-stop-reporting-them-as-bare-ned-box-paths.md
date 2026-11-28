---
issue: "[Tell cold-read reviewers that their copy's file:///Volumes/nedhome/ link targets were rewritten to /home/nedlern/, so they stop reporting them as bare ned-box paths](https://github.com/nedsnodes/nedsnodes/issues/5426)"
---

# Tell cold-read reviewers that their copy's file:///Volumes/nedhome/ link targets were rewritten to /home/nedlern/, so they stop reporting them as bare ned-box paths

## Reproduction

1. Open the cold-read-fast-read report `nedlern@ned-box:/home/nedlern/agents/MD-skills-2/cold-read-records/md-skills-2-agent-seat-items-awaiting-user-ruling-approval-walk-2026-11-26-item-1-of-13-2026-11-25/cold-read-fast-read.md`. Its line 149, Question 2 finding 5, says that the link in `[s7]` "uses a bare ned-box filesystem path rather than a repository path or `nedlern@ned-box:/home/nedlern/nedsnodes-logs/...`, so it does not resolve in the repository or on the Mac."
2. Open the copy the reviewer read, `md-skills-2-agent-seat-items-awaiting-user-ruling-approval-walk-2026-11-26-item-1-of-13-with-sentence-ids.md` in the same directory. Its line 9, sentence `[s7]`, links `/home/nedlern/nedsnodes-logs/walk/claude-md-lines-already-covered-by-hooks-and-skills-approval-walk-2026-11-21-minutes.md`.
3. Open the original document, which the cold-read-fast-read copied under `target/` in the same directory before it rewrote any link. The same link there is `file:///Volumes/nedhome/nedsnodes-logs/walk/claude-md-lines-already-covered-by-hooks-and-skills-approval-walk-2026-11-21-minutes.md`, the form that opens on the user's Mac.
4. Open `cold-read-fast-read-finding-outcomes.json` in the same directory. Finding `Q2.5` is declined with the reason "the link is the file:///Volumes/nedhome form, which opens on the Mac".

## What is wrong

Change 3 of [GHI 2464](https://github.com/nedsnodes/nedsnodes/issues/2464) has `nn-systems/cold-read/cold-read-fast-read.py` and `nn-systems/cold-read/cold-read-grid.py` give their reviewers a copy in which each inline link target that starts `file:///Volumes/nedhome/` starts `/home/nedlern/` instead, so that a reviewer on ned-box can open the file. Both programs call `cold_read_reviewer_copy_text_with_mac_mount_of_ned_box_home_file_links_rewritten_as_ned_box_home_paths_where_mac_mount_absent` in `nn-systems/cold-read/cold-read-record-names-common.py` ([line 269 on main at 09e50fda](https://github.com/nedsnodes/nedsnodes/blob/09e50fda6b6d27cc63179ae120383d25e9a6458b/nn-systems/cold-read/cold-read-record-names-common.py#L269)): the fast-read on its copy with sentence ids, and the grid in `freeze_target` on the frozen copy every grid reviewer reads.

Nothing tells the reviewer that the rewrite happened. The reviewer sees a `/home/nedlern/` link, which the project's `CLAUDE.md` does not allow in a document the user reads on his Mac, and reports it. The finding is wrong, because the original has the Mac form, so the author declines it, and each one costs a triage step.

Counts, made on ned-box on 2026-11-27 with a script that takes each numbered finding naming a `/home/nedlern/` path together with words such as "bare", "local path", "Mac" or the `nedlern@ned-box:` form, and checks whether the document under `target/` has the same path in the `file:///Volumes/nedhome/` form:

- MD-skills-2's records `md-skills-2-agent-seat-items-awaiting-user-ruling-approval-walk-2026-11-26-*` hold 64 cold-read-fast-read reports. 24 hold such a finding, and in 23 of them the finding is on a link the rewrite made. Their finding-outcomes files decline 22 findings for this reason, in 19 records. MD-skills-2 had counted 42 of 128; 128 is twice 64, so that count probably took each report's `.agent-session.json` as a second report (unverified).
- cold-read-improvement's records, `nedlern@ned-box:/home/nedlern/agents/cold-read-improvement/cold-read-records/`, hold 802 cold-read-fast-read reports. 83 hold such a finding, and in 74 of them the finding is on a link the rewrite made. Their finding-outcomes files decline 18 findings for this reason.
- The grid's reviewers read the same rewritten text with nothing said about it, by the code of `freeze_target` in `nn-systems/cold-read/cold-read-grid.py`; their reports were not counted.

## What to do

Have the program that launches each reviewer name, in the reviewer's prompt, each link target the rewrite changed, and add nothing when it changed none. The cold-read-cell launchers, `nn-systems/cold-read/cold-read-agy-cell.py`, `nn-systems/cold-read/cold-read-claude-cell.py` and `nn-systems/cold-read/cold-read-codex-cell.py`, build every reviewer's prompt in `compose_prompt` of `nn-systems/cold-read/cold-read-cell-common.py`, which already appends a paragraph of its own for a frozen copy.

1. The rewrite returns, with the rewritten text, the list of link targets it rewrote, in their `/home/nedlern/` form.
2. The fast-read and the grid pass each of those targets to the launcher with a launcher option given once per target. A target that holds several documents passes the targets of all of them.
3. `compose_prompt` then adds one paragraph that lists those targets. It says that each was `file:///Volumes/nedhome/` in the original document, the form that opens the file on the user's Mac, and was rewritten so the reviewer can open it on ned-box; that the reviewer should not report a link to one of them for its form; and that any other `/home/nedlern/` link target is in the original as written, and is reported as usual. Naming the targets, rather than every `/home/nedlern/` link, keeps a real bare ned-box path reportable in a document that has both.

The prompt templates under `.claude/skills/cold-read/prompts/` stay as they are.

The work is done when a reviewer given a rewritten copy is told which targets were rewritten, a reviewer given an unchanged copy is told nothing, and tests show both.
