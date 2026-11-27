# Kinds of document in this project: what each holds, who reads it, and where it lives

This page lets an agent decide, for any fact, which kind of document holds it, so that the agent knows where to look for the fact and where to write it. Each fact has one canonical location, in one kind of document; every other document that needs the fact links there instead of restating it.

Each kind's entry names its text-intended-reader-category, and a document of that kind is written and checked for that category, as the category's entry in `docs/nedsnodes-wiki/nedsnodes-glossary.md` says. A kind has rules of its own only where its work needs them, such as the `#root_cause` line of a pull request description; every other kind follows its text-intended-reader-category's rules alone.

This page names the kinds and says what each holds, who reads it and where it lives. It defines none of them again. A kind's type definition, the document that says what the kind contains, what it leaves out and how long it runs, is where the kind's entry says after "Defined in:"; an entry with no "Defined in:" has no type definition but this entry. [GHI 1080, Type definitions for the project's kinds of markdown: what each contains, leaves out, and how long it runs](https://github.com/nedsnodes/nedsnodes/issues/1080) is writing the ones still missing; an entry cites it by the name of its item in `docs/issues/1080-type-definitions-for-the-project-s-kinds-of.md`. A kind's file name pattern and directory are in `docs/nedsnodes-wiki/nedsnodes-file-naming-and-location-standards.md`, and its project-term or system-term is in its glossary.

## The kinds are a flat list

Every document is one kind; a document that fits no other kind is miscellaneous, as the section "A document that fits no kind, or two" says. A program's file holds two things: its docstring, which is a document, and the code under it, which is not a document; the code is listed below with the documents only because it is the canonical location of what the system does. A project-term that groups several kinds names a group, not a kind: agent-instructions covers CLAUDE.md, seat-briefs, skills and prompts; the standing-agent-instructions are CLAUDE.md, `AGENTS.md`, the seat-briefs, every `-instructions.md` and `-prompt.md` file, every skill's `SKILL.md` and every agent definition in `.claude/agents/`. A document whose parts each fit a different kind is a defect of that document, which an agent fixes without asking: the part that fits the other kind moves to a document of that kind, and the document links it.

## The code, and the documents that describe the system

- **The code and its tests.** Holds: what the system does, in full; a test says what must keep passing. Reader category: machine-readable; its comments are agent-readable. Read by: any agent that changes the system, and any agent checking what a document claims. Lives in: `nn-systems/<system>/`, `scripts/` and the other code directories. Every other kind in this section leaves to the code what the code states.
- **A program's docstring and `--help`.** Holds: what one program does, how to run it, its options, exit codes and failure behaviour, what it does not handle, and what a person or agent does just before and after running it. A hook and a -common module have the docstring alone; a test's docstring, and a test helper's, says what it covers. Reader category: human-and-agent-readable. Read by: an agent or the user about to run the program, and an agent about to change it. Lives in: the top of the program's file; every program a person or agent runs prints it for `--help`, as `scripts/every-repository-program-help-option-test.py` tests. Defined in: `CLAUDE.md`'s bullet on comments; for a -hack file, the glossary entry nn-hack.
- **nn-architecture-overview.** Holds: the facts about a system that no single file states: what it is for, its components in a sentence each, its invariants, its shared state, its entry points and its planned work; it links the other kinds that hold the rest, as the section "How an overview links to the other kinds" says. Reader category: human-and-agent-readable. Read by: an agent about to change, debug or review a system, mostly by searching it for one fact and then reading the code; a cold-read-cell reads it whole. Lives in: `docs/nedsnodes-wiki/nedsnodes-<system>-architecture-overview.md`, one per system; the whole project has one, `docs/nedsnodes-wiki/nedsnodes-project-architecture-overview.md`, which links every system's; and a subsystem with its own directory, `nn-systems/<system>/<subsystem>/`, may have one, `docs/nedsnodes-wiki/nedsnodes-<system>-<subsystem>-architecture-overview.md`. Defined in: the glossary and `docs/nedsnodes-wiki/nedsnodes-how-to-write-an-architecture-overview.md`, which says the sections and length of each level.
- **Design.** Holds: before its code is built, what to build and why; once built, only what the code cannot say: the user-rulings and their reasons, the alternatives turned down, the facts about outside programs the design rests on, its known holes and its deferred-decisions. Reader category: human-and-agent-readable. Read by: an agent that builds the design, changes it, or checks a change against a user-ruling; the user, when he rules on it. Lives in: the naming standards' entry "Design document". Defined in: GHI 1080, item "Designs" (not yet written).
- **Test-design and design-contract.** Hold: what the glossary entries test-design and design-contract say. Reader category: human-and-agent-readable. Read by: the agent that builds or tests the design, and the user, to whom design-to-main brings them. Lives in: beside their design, as the naming standards' entry "Tests, test-designs, design-contracts" says. Defined in: the glossary.
- **Runbook.** Holds: the steps of one operation that spans several programs or machines, such as restarting a handoff-supervisor or setting up a machine, each with the machine it runs on: in order, with what to look at before going on, or, where each case needs a different program, which one to run in which case. An operation that one program does, with what the agent does just before and after, belongs to that program's docstring, not to a runbook. Reader category: human-and-agent-readable. Read by: the agent or the user carrying out the operation. Lives in: `docs/nedsnodes-wiki/nedsnodes-<operation>.md`. Defined in: this entry, until GHI 1080 defines it.
- **Glossary.** Holds: one definition of each project-term or system-term, with a link to more detail. Reader category: human-and-agent-readable. Read by: every agent, at the start of an agent-session and when it meets a term. Lives in: `docs/nedsnodes-wiki/nedsnodes-glossary.md` and the system glossaries it lists. Defined in: the project glossary's opening paragraphs; GHI 1080, item "Project glossary entries".
- **Rules page.** Holds: the rules an agent applies to one kind of work across the project, such as naming, word choice, which changes need the user's approval, or how to write a tool-message-to-agent. Reader category: human-and-agent-readable. Read by: an agent doing that work, sent there by `CLAUDE.md`, a skill or a hook. Lives in: `docs/nedsnodes-wiki/`. Defined in: GHI 1080, item "Wiki pages other than overviews" (not yet written).
- **Explanation page.** Holds: a model that no one system owns and that an agent needs in order to judge a case no rule covers, such as the agent-seat model or the git worktree working model. Reader category: human-and-agent-readable. Read by: an agent facing such a case, and the user. Lives in: `docs/nedsnodes-wiki/`. Defined in: GHI 1080, item "Wiki pages other than overviews" (not yet written).
- **README.** Holds: what a directory is for, for a person who opens it first. Reader category: human-and-agent-readable. Read by: a person new to the repository or the directory. Lives in: the directory it describes, as `README.md`.

## Documents that instruct agents

- **`CLAUDE.md`.** Holds: the rules every agent follows in every agent-session; `AGENTS.md` points Codex at it. Reader category: human-and-agent-readable. Read by: every Claude Code agent, which loads it at start, and every Codex agent, which `AGENTS.md` sends to it. Lives in: the repository's root.
- **Seat-brief.** Holds: one agent-seat's job, what it owns and where its work goes. Reader category: human-and-agent-readable. Read by: every agent-session of that agent-seat. Lives in: the glossary entry seat-brief says. Defined in: GHI 1080, item "Seat-briefs" (not yet written).
- **Skill.** Holds: the procedure an agent follows for recurring work that needs judgment, loaded when the task its `description` names comes up. A skill differs from a runbook by its reader and its trigger: an agent follows a skill whenever its task recurs, while a runbook serves whoever carries out one operation. Reader category: human-and-agent-readable. Read by: the agent doing that work. Lives in: `.claude/skills/<skill name>/SKILL.md`, and the rest of the skill under `nn-systems/skills/<skill name>/`.
- **Agent definition.** Holds: one kind of subagent's description, which Claude Code shows an agent choosing a subagent, and its instructions. Reader category: human-and-agent-readable. Read by: the agent choosing a subagent, and the subagent it starts. Lives in: `.claude/agents/<agent name>.md`.
- **Prompt.** Holds: agent-instructions that a program hands an agent, initial-agent-instructions and text appended to a system prompt included. Reader category: human-and-agent-readable for a `-prompt.md` or `-instructions.md` file; agent-readable for a one-off-prompt. Read by: the agent the program starts. Lives in: the naming standards' entries "Skill prompt" and "agent-instructions".
- **tool-message-to-agent.** Holds: what a program stopped or found, why, and what the agent does next. Reader category: agent-readable. Read by: the agent the program reports to. Lives in: the program's source. Defined in: the glossary and `docs/nedsnodes-wiki/nedsnodes-how-to-write-a-tool-message-to-agent-such-as-a-hook-refusal-or-script-error.md`.

## Documents that track work and decisions

- **GHI-MD.** Holds: one GitHub issue's subject, why it matters, what the user has decided about it, its open questions and its next action. Reader category: human-and-agent-readable; a heading a script reads is also machine-readable. Read by: the agent that takes up the work, ghi-guide-agent, reviewers and the user. Lives in: `docs/issues/`. Defined in: the /ghi-write skill; GHI 1080, item "GHI-MDs" (not yet written).
- **Walk-document and walk-minutes.** Hold: the items of one approval-walk as shown to the user, and what he answered to each. Reader category: human-and-agent-readable. Read by: the user, the agent running the approval-walk and its successor, and agents searching for a user-ruling. Lives in: `docs/walk/` of the agent-home while the approval-walk is open, then the log-store's `walk/`. Defined in: the /walk-me-through skill.
- **Build-slice plan.** Holds: a design's numbered build-slices, and which are built, being built or planned. Reader category: human-and-agent-readable. Read by: the agent building the next build-slice, and the user. Lives in: `docs/issues/`, beside its design's GHI-MD. Defined in: GHI [refresh-design: when a system's code lands, bring its design, build-slice plan and overview into line — removing, never revising](https://github.com/nedsnodes/nedsnodes/issues/670).
- **Pull request review.** Holds: a reviewer's findings on one pull request, one finding per comment. Reader category: agent-readable. Read by: the pull request's author and merge-lane-2. Lives in: GitHub. Defined in: the /pull-request-review-write skill and `docs/agents/pr-reviewer-instructions.md`.
- **Commit message and pull request description.** Hold: what one change did and why, and the history and citations behind it, which no other kind holds. Reader category: agent-readable. Read by: reviewers, merge-lane-2, and an agent tracing why the code is as it is. Lives in: git and GitHub. Rule of its own: a pull request description that fixes a defect on main carries a `#root_cause` or `#root_cause_not_fixed` line for each such defect, which `scripts/merge-gate.sh` reads, as step 1 of `docs/agents/pr-reviewer-instructions.md` says.
- **proposed-improvements-or-changes-file.** Holds: one reviewer's proposed changes to a document or to what the document describes, until they are settled. Reader category: agent-readable. Read by: the agent that settles them. Lives in: the glossary entry says.
- **`-draft` and `-candidate` files.** Hold: a document still being written, or a version frozen for reviewers, as the naming standards' section "Filename suffixes" defines the two suffixes. Reader category: that of the kind the document will be. Read by: the writer and the reviewers. Lives in: a queue directory, `docs/drafts/` or the log-store, as the naming standards say.

## Records of agent-sessions and work

- **Session-handoff and conversation-tail.** Hold: what a successor agent-session needs to continue: the next step, the open work, and the verbatim tail of the dialog. Reader category: agent-readable. Read by: the successor, once, at its start. Lives in: `~/.claude/handoffs/` on the agent-seat's machine, never committed. Defined in: the glossary; GHI 1080, item "Handoff next-step files", which covers the session-handoff (not yet written).
- **Log-store records.** Hold: what was done and found: the files named by the log suffixes the naming standards' section "Filename suffixes" lists, other than `-draft` and `-candidate`, and cold-read-records. Reader category: agent-readable for reports and analyses, the reports in a cold-read-record included; machine-readable for every other record. Read by: the agent that asked for the work, the user, and agents searching the past with the /find-info skill. Lives in: the log-store.

## Where each fact lives

| The fact | Its kind |
|---|---|
| How to run one program, its options, exit codes and failures | that program's docstring and `--help` |
| What the code does, in detail | the code and its tests |
| A rule several components keep that no single file states | nn-architecture-overview, Invariants |
| What a component is for, and where it is | nn-architecture-overview, Components, in one sentence |
| Why the system is built as it is; a user-ruling and its reason | design |
| The steps of one operation across several programs or machines | runbook |
| The steps an agent follows each time a kind of work recurs | skill |
| What a term means | its glossary |
| What every agent does in every agent-session | `CLAUDE.md` |
| One agent-seat's job | seat-brief |
| Work not yet done, and its open questions | GHI-MD |
| How something came to be: dates, incidents, review rounds, other than the date and reason a design keeps with each user-ruling | commit message, pull request description, walk-minutes |

## How an overview links to the other kinds

An nn-architecture-overview holds only the facts no single file states, so it links each other kind its system has rather than restating it:

- Its Components list gives each program one sentence and its path, and says which programs answer `--help`, so a reader knows where to find how to run each one.
- It links each runbook for the system, in the sentence of the program the runbook runs, and holds none of the runbook's steps.
- It links the system's designs, which hold the reasons for the system's rules, and the skills that drive the system.
- It uses the terms of the project glossary and its system's glossary without defining them.

Everything else an overview holds is in `docs/nedsnodes-wiki/nedsnodes-how-to-write-an-architecture-overview.md`.

## Kinds this page leaves out

Settings and data files, such as `.claude/settings.json` or `nn-systems/general-tools/scheduled-jobs-on-each-machine.json`, are code, not documents. A file of prose that a program reads as data, such as the word table of `docs/nedsnodes-wiki/nedsnodes-style-guide.md`, is the kind its content is, and the naming standards' entry "Prose a program reads as its data" says where it lives.

## A document that fits no kind, or two

A document that fits no other kind on this page is miscellaneous, such as the research notes under `docs/cross-project/`. A miscellaneous document says in its opening lines which text-intended-reader-category it is written for, and follows that category's rules; it is not brought to the user. Claude Code's memory files, under `~/.claude/projects/`, are miscellaneous too, but Claude Code fixes their format, so this page names their category instead: human-and-agent-readable.

A document that, taken whole, fits the description of two kinds, so that an agent cannot tell which kind it is, is brought to the user, who decides whether it belongs to one of them, should be split, or is a new kind. A new kind is added to this page only once he approves it.
