---
issue: "[Move the whole project to nodes and state machines](https://github.com/nedsnodes/nedsnodes/issues/5227)"
---

# Move the whole project to nodes and state machines

## What this is

On 2026-11-21 the user asked to "organize as much as possible project into modules that get called from modules that are organized in a state machine like fashion". The design for that work is [Moving NedsNodes to nodes and state machines](https://github.com/nedsnodes/nedsnodes/blob/nodes-and-state-machines-project-wide-design-for-user-review-topic-branch/docs/nedsnodes-wiki/queue/nedsnodes-moving-the-project-to-nodes-and-state-machines.md), `docs/nedsnodes-wiki/queue/nedsnodes-moving-the-project-to-nodes-and-state-machines.md` on the branch `nodes-and-state-machines-project-wide-design-for-user-review-topic-branch`. That branch is pushed and has no pull request (`gh pr list --repo nedsnodes/nedsnodes --head nodes-and-state-machines-project-wide-design-for-user-review-topic-branch --state all` listed none on 2026-11-26), so the design is not on main. In the design, a workflow such as an approval-walk, a cold read or a session-handoff becomes a set of small typed programs, called nodes, and a machine file that says which node follows which. A runner does the sequencing, counting, validation and storage, and a model, or the user, is called only for a step that needs judgment. The user approved filing this one GHI for the whole project on 2026-11-26, answering "a" to item 4 of approval-walk agent-instructions-editor-backlog-decisions-approval-walk-2026-11-26 (walk-minutes `nedlern@ned-box:/home/nedlern/agents/agent-instructions-editor/docs/walk/agent-instructions-editor-backlog-decisions-approval-walk-2026-11-26-minutes.md`).

## Why

Most of the project's multi-step work today lives as programs and skills whose order is written in prose or in each program's own chains of if-statements. An agent that follows such prose can skip or misorder a step, and the prose costs tokens every time it is loaded. `CLAUDE.md`'s code-prompt-code rule asks for every step that needs no judgment to be in code; the design says how to do that across the project, one piece at a time, and only where it pays.

## What comes next

1. The user answers the open questions below, in approval-walk nodes-design-open-questions-refreshed-2026-11-26 (walk-document `nedlern@ned-box:/home/nedlern/agents/MD-skills/docs/walk/nodes-design-open-questions-refreshed-2026-11-26.md`, walk-minutes beside it with the suffix `-minutes.md`). Agent-seat MD-skills runs that approval-walk.
2. MD-skills carries out each of the user's answers, those about PR 3937 and GHI 1919 below included, writes them into the design on its branch, and brings the design to the user for his approval to move it from `docs/nedsnodes-wiki/queue/` into `docs/nedsnodes-wiki/`, in a pull request.
3. The build follows the design's section 12, "Proposed order", each step its own pull request that leaves the project working, starting with the rename of the shared modules.

## Open questions

These are the items of approval-walk nodes-design-open-questions-refreshed-2026-11-26 that have no recorded answer. Its items 1, 2.1 and 2.2 are answered.

1. Item 3: when Gemini refuses the cold-read-full-run's defect-hunt cold-read-cell because its quota is used up, should the cold-read-full-run skip that cold-read-cell and still count as complete, instead of running it on Opus 5.5 at medium effort? A yes replaces the Opus backup the user approved in item 1.
2. The item titled "The walk check program numbers an item's sub-steps, and the skill stops telling the agent to": the walk check program is `nn-systems/skills/walk-me-through/walk-me-through-answer-added-texts-cold-read-fast-read-check-and-close.py`. Does the user approve the skill sentence that [PR 3937, Walk read step numbers an item's unnumbered sub-steps, so an answer decides only the waiting sub-step](https://github.com/nedsnodes/nedsnodes/pull/3937), changes?
3. The item titled "Measure on Claude, Codex and Gemini whether a cold-read-cell is cheaper with its files in the prompt, before building one tool for all three": should a new question, numbered 12 in the list of questions of the GHI-MD of GHI 1919, Cut cold-read-fast-read Gemini token cost, be added and run now, to measure on Claude, Codex and Gemini whether a cold-read-cell is cheaper with `CLAUDE.md` and the project glossary in its prompt? GHI 1919 and its GHI-MD have since been deleted, so the item needs restating before the user answers it.
4. The item titled "Let the runner take over the approval-walk's bookkeeping when walks move onto it": does the approval-walk's bookkeeping move into code only when approval-walks move onto the runner, with no chain of steps added to the walk check program before then, each step refusing until the one before it is recorded? This is the design's open question 12.
5. The item titled "Give each approval-walk item a lasting id when walks move onto the runner": does each approval-walk item get its lasting id from its record when approval-walks move onto the runner, with no `#approval_walk_item_id <id>` line, written once into each item of the walk-document and never changed, added before then? This is the design's open question 14.

The approval-walk's last item, a summary of what the design will say, is written from these answers.

## Related GHIs

- Work on design-to-main stays in [GHI 282, Build the design-to-main state machine: the Python machine, its per-state agent-instructions, and the nine items the design defers to the build](https://github.com/nedsnodes/nedsnodes/issues/282). The user decided on 2026-11-23 to defer it until other parts have stabilized (the design's section 12), and no step of this GHI changes or depends on it.
- [GHI 2505, Pull requests, their reviews and approval-walks held as one state machine over one schema and one store, so code tracks their state and agents are handed only the steps that need judgment](https://github.com/nedsnodes/nedsnodes/issues/2505) covers the records and machine for pull requests, reviews and approval-walks, one part of this work. In the design's section 12, its approval-walk half is built when approval-walks move onto the runner, and its pull-request half follows.
- [GHI 4080, Fix the defects a full cold read found in the design-to-main state machine design and its arbitrator agent-instructions](https://github.com/nedsnodes/nedsnodes/issues/4080) covers defects in the design-to-main design only.
