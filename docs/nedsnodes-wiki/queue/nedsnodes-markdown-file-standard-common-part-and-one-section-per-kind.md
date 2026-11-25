# Markdown file standard: a common part and one section per kind

This page is the standard for the project's Markdown files: a common part that every Markdown file follows, then one section for each of ten kinds of file, saying what a file of that kind contains and what it leaves out. The kinds are those the project glossary, `docs/nedsnodes-wiki/nedsnodes-glossary.md`, lists under "Kinds of Markdown file", and each section's heading is a kind's name as that list spells it; a file of a kind with no section here follows the common part alone. Do not read the whole page before you write or edit a file. Run `nn-systems/general-tools/markdown-file-standard-rules-for-the-markdown-file-kind-at-a-path-print.py <path of the file>`, giving the path the file will have once it is in place, such as `CLAUDE.local.md` for a seat-brief drafted in a scratchpad. It prints the common part and the one section for that file's kind; for a record or walk-minutes at a path it knows, such as `docs/walk/<name>-minutes.md` or a file in `cold-read-records/`, the common part and its rule Exemptions and precedence again; or the common part alone when neither holds. Read another section only where the printed one points to it. The program picks the kind by the path, and, for a GHI-MD that already exists, also by its front matter, as the GHI-MD section says. It reads this page's level-2 headings, and the bold lead of the common part's rule Exemptions and precedence, as data, and holds this page's path: a heading is renamed, or the page moved, only together with the program's constant that holds it. `nn-systems/general-tools/tests/markdown-file-standard-rules-for-the-markdown-file-kind-at-a-path-print-every-kind-named-is-in-project-glossary-test.py` fails when a heading of this page, a kind the program names, or a kind of work the GHI-MD section names is missing from the glossary's lists.

## Common part

- **Write for a fresh-reader.** The reader has the file and what it links to, not the conversation that produced it. Every reference opens from the reader's machine: a path from the repository root, a log-store citation, or a full URL.
- **State what is, not how it came to be.** Leave out the dates of events, retellings of approval-walks and user-rulings, review rounds, incidents, "was replaced by", "previously", "no longer", and pull requests or GHIs cited as provenance; git history, pull requests and walk-minutes hold them. A decision is written as what holds now. A past fact stays only where a reader would otherwise misread the present, as one clause with no date.
- **One canonical location for each fact.** Link to the document or file that holds a fact instead of restating it. Leave to the code what the code states, such as flags, exit codes, message texts and file formats: name the file and stop.
- **A reason is one clause**, attached to the statement it explains, and only where it helps the reader act. Do not defend a decision or list rejected alternatives, unless the kind's section asks for them.
- **Headings.** Where a kind's section lists headings, the file has each one that section does not make optional or conditional, and keeps that section's order. A heading or line that a program reads, such as `## Provisional additions (not yet vetted by the user)` or a front matter line, keeps its exact text.
- **Kept true.** When the thing a file describes changes, change the sentence that describes it. Do not append a dated note, an "Update:" paragraph or an "as of" line beside the old sentence.
- **Exemptions and precedence.** A file whose job is to record what happened, such as a log, walk-minutes, a report, a commit message or a pull request description, is exempt from the rules State what is and Kept true, and a word-for-word copy, such as a frozen-copy, follows none of this standard. Where a kind's section asks for something a common-part rule tells writers to leave out, such as the exact command in a bug's `## Reproduction`, the kind's section wins.

## project instructions

A project instructions file, `CLAUDE.md` or `AGENTS.md` at the root of a checkout, is in context for the whole of every agent-session started in the checkout, so each word costs every agent-session of every agent-seat. `AGENTS.md` sends Codex to `CLAUDE.md`, so a rule goes in `CLAUDE.md`.

It contains a level-1 heading naming the project, then each rule that every agent-session in the checkout needs, whatever its agent-seat or task, as one paragraph or list item: the instruction, the condition it applies under, and a reason only where it helps. Where another file holds a rule's detail, the rule gives that file's path and the condition under which to read it, such as the rule that sends a reviewer of a pull request to `docs/agents/pr-reviewer-instructions.md`.

A project instructions file leaves out:

- A rule that one agent-seat, one skill or one kind of task alone needs: it goes in that seat-brief, skill or wiki page, and a rule names that file only when every agent-session must know to read it.
- Steps that need no judgment, and the order of steps: a program holds them, as the code-prompt-code rule in `CLAUDE.md` says.
- History and citations, which `CLAUDE.md` keeps out of standing instructions.

A project instructions file holds no rule that belongs in a seat-brief, a skill, a wiki page or a program; the rule goes in that file.

## seat-brief

A seat-brief is in context for the whole of every agent-session of its agent-seat, so each word costs every agent-session. `.claude/skills/start-agent-seat/SKILL.md` step 2 says how a new one is written and approved; this section says what it holds, for a new seat-brief and for each edit of one.

It contains, in this order:

1. A level-1 heading naming the agent-seat.
2. What the agent-seat owns, in one paragraph.
3. Its first job, or the standing work it does when no task is open.
4. Where its work goes: nn-topic-branches and pull requests, the log-store directory, and which agent-seat it reports to, if any.
5. Rules for this agent-seat alone that no `CLAUDE.md`, skill, wiki page or program holds. The user's words go in quotation marks where a paraphrase would lose his meaning, with no date or attribution.

A seat-brief leaves out:

- Anything `CLAUDE.md`, a skill, a wiki page or a program already says, and procedures of more than a few steps: a procedure goes into a skill or a program, and the seat-brief names it.
- How the agent-seat was started, who asked for it, and the incidents behind its rules.
- Facts about another agent-seat or a machine that change on their own, such as which agent-seat merges pull requests; the seat-brief names the document that holds them.

A seat-brief holds no procedure; a procedure belongs in a skill or a program. When a skill or a program takes over a rule, the rule leaves the seat-brief in the same change.

## agent definition

An agent definition is the file `.claude/agents/<name>.md` that Claude Code uses as the instructions of the subagent of that name. The dispatching agent reads its front matter's `description` to choose the subagent and to know what to send it, so the `description` is in context in every agent-session.

It contains, in this order:

1. The front matter Claude Code reads: `name`, the file's name without `.md`; `description`, saying when to use the subagent and what to send it; and `tools`, the tools the subagent needs and no others.
2. The body: the subagent's job, what it is sent, the steps that need judgment, each with what the subagent judges by, and what it returns, in the form the dispatching agent reads.

An agent definition leaves out:

- What `CLAUDE.md` already says, which the subagent has in context too.
- Steps that need no judgment: a program does them, and the body names the program.
- History and citations, which `CLAUDE.md` keeps out of standing instructions.

An agent definition holds no step that needs no judgment; such a step belongs in a program.

## prompt

A prompt is a file a program of this project pastes into a model's prompt word for word, such as `docs/agents/seat-first-prompt.md`, and a prompt template is one with slots the program fills first, such as the cold-read prompts in `.claude/skills/cold-read/prompts/`; this section covers both. Its reader is the model the program runs, which has the prompt and what the prompt names, and none of the conversation that led to the run.

It contains, in this order:

1. A first paragraph: the model's job, and what the program gives it.
2. The steps that need judgment, each with what the model judges by.
3. The output: its form, exactly as the program reads it, or the path of the JSON Schema the program checks it against.

A prompt or prompt template leaves out:

- Steps the program does, such as reading and writing files, putting steps in order, retrying and checking the output's form, as the code-prompt-code rule in `CLAUDE.md` says.
- The text the program puts in place of a placeholder.
- History and citations, which `CLAUDE.md` keeps out of standing instructions.

A prompt or prompt template holds no step that needs no judgment; such a step belongs in its program.

## skill

A skill is a skill's `SKILL.md` in `.claude/skills/<name>/`, which Claude Code loads when the skill is invoked, or a Markdown file beside it or in `nn-systems/skills/<name>/` that the `SKILL.md` tells the agent to read; a prompt or prompt template among them follows the prompt section. The `description` in a `SKILL.md`'s front matter is in context in every agent-session, which reads it to decide when to invoke the skill, so each of its words costs every agent-session.

It contains, in this order:

1. For a `SKILL.md`, the front matter Claude Code reads: `name`, the skill's directory name, and `description`: the situations and the user's words that call for the skill, then what it does, in one sentence.
2. A level-1 heading naming the skill, or, in another file of the skill, naming that file's subject.
3. The steps that need judgment, each an action with what the agent judges by. Where the skill's steps run in a fixed order, a program holds that order and the record of which steps are done, as the code-prompt-code rule in `CLAUDE.md` says, and the skill gives the command the agent runs to ask it for its next step.

A skill leaves out:

- What `CLAUDE.md` or another skill already says: the skill names that file instead.
- Steps that need no judgment, which its program does.
- History and citations, which `CLAUDE.md` keeps out of standing instructions.

A skill holds no fixed order of steps; that order belongs in a program.

## session-handoff or next step file

This section covers the next step file that `/handoff` step 2 writes in `~/.claude/handoffs/`; `nn-systems/handoff/handoff-write-and-check-supervisor.py` copies its text into the session-handoff, which the successor agent-session, which did not see the work, starts from, and writes the rest of the session-handoff itself, so no section of this page covers the session-handoff file. `.claude/skills/handoff/SKILL.md` step 2 says what goes in a next step file and what stays out; this section adds the order and the form.

It contains, in this order:

1. The first action, in one paragraph starting `First action:`: what the user is waiting on, or, when he waits on nothing, the task to start first, naming an approval-walk by its name or a task by its id, and the exact command or message to send first where it is already decided.
2. Running work that must be restarted now and that no record shows, as `/handoff` step 2 says, one line each, with its command.
3. What the successor needs that no task, walk-minutes, committed file or `CLAUDE.md` holds, one line each, with a path, or a repository and number, for each reference.

A next step file leaves out what this agent-session did, the text of an approval-walk item or a task, which their files hold, the times and wording of the user's replies unless the successor acts on them, and the reasons behind the first action unless the successor would otherwise act differently.

A next step file holds no list of work to do; that work belongs in tasks.

## glossary

This section covers each glossary: the project glossary, `docs/nedsnodes-wiki/nedsnodes-glossary.md`, each system glossary it names, and `docs/nedsnodes-wiki/nedsnodes-sdlc-terms.md`. The project glossary's opening paragraphs say what qualifies as a project-term, which glossary holds a term, the order of entries and when an entry carries the labels #prose, #code and #data; this section says what an entry holds.

Every entry follows one template, on one line, in which `[…]` marks an optional part:

```
- **<term>** — <definition>[, such as <one example>].[ <one sentence naming the document or program that holds the detail, such as "The program is `<path>`.">][ <labels>]
```

- The definition is one sentence. It starts with the kind of thing the term names, such as "a skill", "the program" or "a filename suffix", then says what sets it apart from others of that kind. It does not use the term itself.
- The example is a real one from this repository, given only where the definition alone leaves a reader unsure what counts.
- The sentence naming the detail's canonical location, such as the program that implements the term, is given where one exists.
- In the project glossary's two lists of kinds, an entry is a numbered item instead, in the order its kind is tried, and a kind that an entry of its own already defines points to that entry instead of defining it again.

An entry leaves out history, user-rulings, quotations of the user, the reasons for the term or the thing it names, how-to steps, design detail, a list of the term's cases, and anything the linked document says.

An entry holds no detail that belongs in the linked document.

## design

A design decides how something will be built. It is a file whose name ends `.design.md`, as `docs/nedsnodes-wiki/nedsnodes-file-naming-and-location-standards.md` names one at each stage and says where it lives, or a GHI-MD whose front matter carries `kind: design`, as `/ghi-write` step 4 says. No section of this page covers a test-design or a design-contract, and the program prints the common part alone for either.

A design has these seven level-2 headings, in this order. A design that does not need one of the seven keeps its heading, and the section's whole body is one line, `Not needed:` followed by the reason.

1. `## Problem`: what is wrong or missing, who it costs, and what the design must achieve, measurable where it can be.
2. `## Goals and non-goals`: what the design delivers, and what it deliberately does not, one line each.
3. `## Design`: the components, the data each holds or passes, and how they work together, at the level a builder needs; subsections as the design needs them.
4. `## Steps that need judgment`: each step given to a model, and why code cannot do it. Every step not listed here is code.
5. `## Failure handling`: each failure the design handles, how the program reports it, and, for a guard, validation, retry or workaround, the failure that `CLAUDE.md`'s two conditions require.
6. `## Testing`: how each design-requirement is tested, or the test-design that says so.
7. `## Alternatives considered`: each alternative rejected, in one or two sentences with its reason.

These headings follow the seven when the design has them, and are left out when it does not: `## Deferred-decisions`, one line for each case the design leaves open, and `## Decided elsewhere`, one line for each decision another component, document or agent-seat makes, naming that owner, each line in the form the paragraph headed `initiate-design-to-main` in `docs/design-to-main/design-to-main-state-machine.system.design.md` gives, such as a deferred line marked `#not_in_this_run` with its reason; `## Defects fixed`, a `#root_cause` or `#root_cause_not_fixed` line for each defect the design's code fixes, or the line `#no_defect_fixed`, as `CLAUDE.md` gives them for a pull request description and `scripts/merge-gate.sh` checks them; `## Relations`; and, for a design that is a GHI-MD, the GHI-MD section's `## Next action`, `## Done when`, `## Outcome` and `## Provisional additions (not yet vetted by the user)`, as that section describes them. A design that is a GHI-MD also opens with the front matter `/ghi-write` step 4 gives it, then the GHI's title heading.

A design leaves out:

- Its own revision history, such as "this revision folds in", and the dates its decisions were made. The `**Pinned to what landed:**` lines that `docs/nedsnodes-wiki/nedsnodes-file-naming-and-location-standards.md` asks for after each merge stay, because `scripts/stale-code-citation-check.py` reads them. A user-ruling the design rests on is stated as what is decided, followed by its walk-minutes citation in parentheses.
- Detail the design-contract or the test-design holds.
- Once its code has merged, any detail the code now states. From then on, a change to what the design promises goes through a GHI-MD for a feature, which revises the design before the code.

A design holds one design, and no detail that belongs in the design-contract, the test-design or the code; a second design goes in a file of its own.

## GHI-MD

This section covers each GHI-MD in `docs/issues/`, and each MD in `docs/issues/queue/` on its way to becoming one. `.claude/skills/ghi-write/SKILL.md` says how it is routed, titled, filed and edited; this section says what it holds. A GHI-MD that is a design, whose name ends `.design.md` or whose front matter carries `kind: design`, follows the design section instead. The program prints the design section for it by that name, or, once the file exists, by that line; for a new design GHI-MD whose name does not end `.design.md`, such as one `scripts/ghi-issue-write.py` names from its title, it prints this section, so read the design section on this page and follow it instead.

Its GHI is of one of the five kinds of work the project glossary lists under "Kinds of GHI". A bug whose fault turns out to be in its design is a feature, because the fix changes what the design promises.

It contains, in this order:

1. The first heading, the GHI's title, by the rules of `/ghi-write` step 4.
2. The one heading its kind of work takes:
   - **research**: `## Question`: the question, and what each likely answer would lead to.
   - **bug**: `## Reproduction`: the command or steps, what happened, and what should have happened, naming the file that promises it.
   - **chore**: `## Work`: the upkeep to do, the files or programs it touches, and why it is due now.
   - **refactor**: `## Change`: what is rebuilt or rearranged, and the design, documentation or tests that show that what it delivers stays the same.
   - **feature**: `## Change`: what is added, or what an existing thing will deliver differently, and the design, design-contract or documentation that promises it, or that none exists yet.
3. `## Why`: who or what the problem or gap costs, and how often.
4. `## Next action`: one action a fresh-reader can take.
5. `## Done when`: the condition that closes the GHI.
6. `## Relations`: each related GHI by title and link, with one clause on how it relates. Leave the section out when there are none.
7. `## Outcome`, added when the work is done: what was done, by pull request link, in one paragraph. When Outcome is added, `## Next action` is deleted, because it is then no longer true.
8. `## Provisional additions (not yet vetted by the user)`, always last, when the GHI-MD holds provisional-additions.

A GHI-MD leaves out:

- A dated account of events, such as a "Status on" section, a list of where a failure was seen beyond the one example that reproduces it, or the rounds of a review. A new event changes the section it affects, such as Why or Next action.
- A record of how a decision was reached. A user-ruling the work rests on is stated as what is decided, in the section it governs, followed by its walk-minutes citation in parentheses, because an agent must verify it before it acts against it.
- Data, measurements and working notes: they go in supporting-documents that the GHI links, as `/ghi-write` step 2 says.

A GHI-MD that is not a design holds no design, which goes in a GHI-MD of its own that carries `kind: design`, and no material that belongs in a supporting-document.

## wiki page

A wiki page is a page in `docs/nedsnodes-wiki/`, or one in `docs/nedsnodes-wiki/queue/` pending approval, other than a glossary and each proposed-improvements-or-changes-file beside an nn-architecture-overview. An nn-architecture-overview also follows `docs/nedsnodes-wiki/nedsnodes-how-to-write-an-architecture-overview.md`, which wins where the two differ.

Each page is a reference page, a how-to page or an explanation page, and keeps to what that one holds: a reference page lists rules or facts a reader looks up, such as `docs/nedsnodes-wiki/nedsnodes-style-guide.md`; a how-to page gives the steps of one job, such as `docs/nedsnodes-wiki/nedsnodes-how-to-choose-a-name-for-files-code-and-glossary-terms.md`; an explanation page says how part of the project works and why, such as `docs/nedsnodes-wiki/nedsnodes-agent-seat-model.md`. When a page grows material that belongs on another of the three, move that material to a page of its own and link to it.

A page contains, in this order:

1. A level-1 heading naming its subject.
2. A first paragraph saying what the page covers and when a reader needs it, so a reader can tell from that paragraph alone whether to read on. A page whose content a program reads as data names that program here, as the rule for prose a program reads in `docs/nedsnodes-wiki/nedsnodes-file-naming-and-location-standards.md` says.
3. The body: for a reference page, one rule or fact to an item, ordered for lookup; for a how-to page, numbered steps, each an action; for an explanation page, the parts and how they fit together, with a reason where it helps.

A wiki page leaves out front matter or opening lines that say which approval-walk or user-ruling produced the page, status lines such as "status: ruled" or "streamlined on", the approval-walk or user-ruling behind each rule, and examples taken from past events when a current file or command would serve.

A wiki page holds one page's material; material for a second page goes on a page of its own.
