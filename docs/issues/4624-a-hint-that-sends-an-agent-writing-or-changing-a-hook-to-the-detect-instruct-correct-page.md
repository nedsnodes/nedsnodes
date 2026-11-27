---
issue: "[A hint that sends an agent writing or changing a hook to the detect-instruct-correct page](https://github.com/nedsnodes/nedsnodes/issues/4624)"
---

# A hint that sends an agent writing or changing a hook to the detect-instruct-correct page

## What to build

When an agent writes or changes a hook, a hint tells it that the detect-instruct-correct page says how to choose between a hint, a warning, a refusal and a revert, the last being the undoing of the agent's action after it happened, by a program or by the agent on the program's instruction, as the glossary's entry for detect-instruct-correct describes. A hook here is a Claude Code hook: a hook program under `.claude/guard-hooks/`, not its tests (`*-test.py`) or shared code (`*-common.py`); or a script that a settings file in the repository, today only `.claude/settings.json`, registers as a hook, including one the same change registers, such as `scripts/obsolete-file-edit-warning-hook.py`, which `.claude/settings.json` registers. Git hooks are not covered.

The hint obeys the page's own rule, as item 20 of the approval-walk below quotes it, that a hint must pay for the context it costs: for example, it is shown at most once per agent-session, not on every edit to a hook. How the change to a hook is detected, how the hint reaches the agent and how it records that it was shown are the builder's choice; the related GHIs at the end are where to start.

## Prerequisite: build nothing until the page is on main

The detect-instruct-correct page is the wiki page on detect-instruct-correct, the technique the glossary defines in `docs/nedsnodes-wiki/nedsnodes-glossary.md`. The cold-read-research agent-seat is writing it under its task "DIC wiki page + short glossary entry + delete block-and-inform". On 2026-11-24 it was not on `main`: `git ls-tree -r --name-only origin/main docs/nedsnodes-wiki` at commit 0d355d1ce lists no page whose name holds "detect" or "dic". Until the page merges, the hint has nothing to point to, so nothing is built before then. When the page merges, the cold-read-research agent-seat edits this GHI-MD to give the page's path. The next action, once the page is on `main`, is to build the hint and its test, naming the page by the path it then has on `main`; the test checks that the path the hint names exists, so a later rename or deletion of the page fails the test.

## Why

Hooks have chosen the wrong response, or delivered a right one wrongly, and each was fixed or reported only after the harm. Each was decided while an agent wrote or changed the hook, which is when this hint would show:

- A refusal where a hint was enough, which lost the user's answer: the walk-me-through hook refused a prompt holding an R answer. Commit fc95fde90, "walk-me-through hook: R goes to the agent as additionalContext instead of blocking the prompt", changed it to pass the answer on.
- A hint repeated on every reply: commit cd09c5b1e, "Bare-number citation hook: a title after a bold label and a number in a quoted subject are accepted; one note per reply, shortened after the first", cut the bare-number citation hook's note to one per reply, shorter after the first.
- A refusal that was a false alarm: two walk-me-through hooks refused a correct closing line, "No decision here; type N or next to continue.", on an item that asks no decision. The user asked why he was told it was not a question, and the agent answered that two hooks got it wrong: `nedlern@ned-box:/home/nedlern/nedsnodes-logs/session-dialogs/ned-box/-home-nedlern-agents-reboot-test/e6cb36f0-5030-4498-990a-7686ebd07f19-dialog-complete.md`, lines 712 to 722.
- An instruction that throws away work: `scripts/obsolete-file-edit-warning-hook.py`, lines 248, 255 and 262 on `main` at commit 0d355d1ce, tells the agent to run `git checkout -- {path}`, which discards the agent's uncommitted change to that file. The user called this stupid on 2026-11-24.

## The user's approval

The user approved this on 2026-11-24, answering "Item 20, I approve" to item 20, "Point hook authors to the DIC page with a hint, once the page is on main", of the approval-walk cold-read-research-hint-pacing-and-reviewer-steps-to-code-2026-11-22. That item recommended filing this GHI, to build once the page is on `main`. The walk-minutes record the approval at line 173: "item 20 of 33: the user answered approved #case_against_weak (2026-11-24 23:38Z)". The walk-document is on the user's Mac at `/Users/el/agents/cold-read-research/docs/walk/cold-read-research-hint-pacing-and-reviewer-steps-to-code-2026-11-22.md`, under "## Item 20 of 33", and its walk-minutes are beside it at `/Users/el/agents/cold-read-research/docs/walk/cold-read-research-hint-pacing-and-reviewer-steps-to-code-2026-11-22-minutes.md`. Both ship to `nedlern@ned-box:/home/nedlern/nedsnodes-logs/walk/` when the approval-walk closes.

## Related GHIs

- GHI [Design the project's Claude Code hooks: requirements drawn from the existing hooks, then keep, fix, merge, rewrite or remove each one](https://github.com/nedsnodes/nedsnodes/issues/1790) is the deferred design for all of the project's hooks; this hint is one small piece beside it.
- ghi-guide-agent named these to build the detection of a hook change on: GHI [Trigger-first instruction delivery (moved from nedlern#1972): delivery timing as a property of every instruction — step-2 CLAUDE.md design input + carried design and scan](https://github.com/nedsnodes/nedsnodes/issues/30), the design for delivering an instruction at the moment it applies; GHI [wiki-write skill, and the detect-set-aside-ask hook that enforces it — checking the file, not the tool call](https://github.com/nedsnodes/nedsnodes/issues/343) and GHI [Catch a guarded file changed without the user's approval, ask him, and keep every version](https://github.com/nedsnodes/nedsnodes/issues/1268), which detect a change to a file rather than matching a tool call; and GHI [MD-placement guidance as symmetric pre-tool remind hooks on both runtimes (boss-directed design, build deferred)](https://github.com/nedsnodes/nedsnodes/issues/11), which found that a guard matching only the Edit, Write and NotebookEdit tools misses a change made by a shell command.
