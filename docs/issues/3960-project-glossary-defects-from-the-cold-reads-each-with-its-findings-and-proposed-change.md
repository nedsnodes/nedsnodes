# Project glossary defects from the cold reads, each with its findings and proposed change

This is the list of defects that work item 1 of GHI [Fix the defects a full cold read found in the project glossary, `docs/nedsnodes-wiki/nedsnodes-glossary.md`](https://github.com/nedsnodes/nedsnodes/issues/3960) asks for. It sorts the 228 findings of the cold-read-full-run, and the four findings of the later cold-read-fast-read, into distinct defects. Each defect is checked against the glossary on main at commit `2765c1b88`, after pull request [5239](https://github.com/nedsnodes/nedsnodes/pull/5239) merged. Pull request 5239 replaced PR [Project glossary: fleet-restart-at-login is named as an agent-seat in the agent-crash-watcher and failed-restart-notice entries](https://github.com/nedsnodes/nedsnodes/pull/3948), which closed without merging. Findings that main has fixed since are listed once, under "Findings main has fixed", and nowhere else.

The findings are cited by report and number. The reports are in two cold-read-records:

- `nedlern@ned-box:/home/nedlern/nedsnodes-logs/cold-read-records/nedsnodes-glossary-2026-11-20-3`:
  - CH is `claude-hunt-deep.md`.
  - C2 is `claude-hunt-second-strongest-model.md`.
  - CT is `claude-terminology-deep.md`.
  - XH is `codex-hunt-deep.md`.
  - X2 is `codex-hunt-second-strongest-model.md`.
  - AG is `agy-hunt-gemini-4-argon-high.md`.
  - XT is `codex-terminology-deep.md`.
  - Q4 is `question-4-what-should-be-code-answer.md`.
- `nedlern@ned-box:/home/nedlern/nedsnodes-logs/cold-read-records/nedsnodes-glossary-2026-11-20-8`: FR is `cold-read-fast-read.md`.

Each defect gives the glossary's text on main, a proposed change, the case against that change with a rating, an alternative, and a recommendation. Work item 3's approval-walk shows these to the user. Where a recommendation says to check something first, such as code or a search of the repository, the agent that runs the approval-walk does that check, and revises the item from it, before it shows the item. A part that changes a file other than the glossary goes in the same pull request as the glossary changes.

Every finding is cited exactly once, in the list of fixed findings, under one defect or under one proposed program. AG2, AG10 and CT32 are each split in two and cited once for each half. Q4-1 is also named under D5, whose defect it found.

Three pages are named often below. The approval page is `docs/nedsnodes-wiki/nedsnodes-which-changes-need-the-users-approval.md`. The file-naming page is `docs/nedsnodes-wiki/nedsnodes-file-naming-and-location-standards.md`. The SDLC-terms page is `docs/nedsnodes-wiki/nedsnodes-sdlc-terms.md`. Some defects are marked as a pre-approved-change candidate. That means an exception of the approval page may cover the change, so the agent running the approval-walk checks the exception before it shows the item.

## Findings main has fixed

These 20 findings, and the first half of AG10, need no work:

- CH1, C2-32, CT1, CT12, CH43: the title is "nedsnodes glossary", the NC entry is now NN, the nc- terms are now nn- terms, and the GHI links point to `nedsnodes/nedsnodes`.
- XT5, XH15, C2-34, CT33, AG10 (first half): the term is nn-system, so "nn-systems" is its plural.
- CH7: the five cold-read terms moved into this glossary.
- CH15, C2-12, CT41: agent-binary now reads "the installed program an agent runs its model through".
- CH20: close-GHI and edit-GHI no longer say the tool merges into main.
- CH36, XH14, X2-11, C2-33, AG11: nn-mutation-testing no longer says "`CLAUDE.md` says which code must be shown this way".
- X2-3: the "case fix" entry is gone.

## The obvious-error-fix

Work item 2's pull request makes one obvious-error-fix. The nn-test-suite entry said that a selective run picks "the nn-test-suites its docstring's selection rules pick". Since commit `ac11b908d`, the docstring of `scripts/run-all-test-suites.py` says under SELECTION that "Which suites a run selects, and why, is on the page `docs/nedsnodes-wiki/nedsnodes-how-the-test-runner-selects-which-nn-test-suites-a-test-run-runs.md`". The entry now points to that page. The 22 lines marked UNRESOLVED in `cold-read-reference-check.md` of the cold-read-record `nedsnodes-glossary-2026-11-20-3` are all name patterns, such as `-test.py` and `~/.claude/handoffs/`, or paths that live outside the repository; none of them is a broken reference. Every other repository path, section name and docstring heading that the glossary cites resolves on main.

## The defects

### D1. "Generic SDLC vocabulary is deliberately absent" while nn- entries open with generic definitions

Findings: CH2, C2-1, CT2.

Old: "A list of the phrases and terms of this project approved by the user, in alphabetical order, skills first. Generic SDLC vocabulary is deliberately absent."

New: "A list of the phrases and terms of this project approved by the user, in alphabetical order, skills first. An SDLC-term used with its standard meaning has no entry here; an entry whose name begins nn-, such as nn-head-commit, gives the standard meaning first and then what this project adds to it."

#case_against weak: it adds a sentence that explains the page.

The alternative: delete the sentence "Generic SDLC vocabulary is deliberately absent."

Recommendation: replace the sentence with the new text.

### D2. "A project-term takes one of four forms", but "ready" and three terms that contain a space fit none of them

Findings: CH3, XH1, AG3, C2-3, CT3, X2-16, C2-45.

"ready" is one ordinary word. CLAUDE.md also uses it in GitHub's sense: "when the pull request is marked ready". The terms "emergency-stop file", "instruction-file guard" and "obvious-fix marker" each join a hyphenated phrase and an ordinary word with a space. The /cold-read skill forbids proposing to rename a project-term, so the proposal changes the rule to fit the terms.

Old: "A project-term takes one of four forms: an abbreviation such as GHI, a skill's slash name such as /handoff, a hyphenated phrase such as agent-seat, or a filename suffix such as -draft."

New: "A project-term takes one of four forms: an abbreviation such as GHI, a skill's slash name such as /handoff, a hyphenated phrase such as agent-seat, which may be followed by one ordinary word, as in emergency-stop file, or a filename suffix such as -draft. The one exception is ready, an ordinary word that this page gives a project meaning for tasks and approved changes; ready said of a pull request keeps GitHub's meaning."

#case_against medium: making ready an explicit exception keeps an ordinary word with a hidden meaning, which the hyphen rule exists to prevent.

The alternative: ask the user to rule on a new name for ready, such as work-ready.

Recommendation: change the sentence to the new text.

### D3. Hyphenated words that no list holds, and no reference that settles a word's standard spelling

Findings: CH4, C2-4, CT23, FR Q3.2.

The page writes "force-pushed" (frozen-head), "hand-typed" (block-and-inform), "re-explains" (/explain) and "minimal-context" (fresh-agent). None of them is in `docs/nedsnodes-wiki/nedsnodes-ordinary-hyphenated-words-list.md`. The opening tells a writer to add such a word to that list, but does not say what shows that a word's standard spelling has a hyphen.

Part 1. Add force-pushed, hand-typed and re-explains to `docs/nedsnodes-wiki/nedsnodes-ordinary-hyphenated-words-list.md`.

Part 2. In fresh-agent, change "a minimal-context agent" to "an agent with minimal context".

Part 3. Old: "A word whose standard spelling, in a dictionary or in computing, has a hyphen, such as fast-forward, is neither a project-term nor a system-term;" New: "A word whose standard spelling has a hyphen, in a general English dictionary such as Merriam-Webster or in the documentation of the program it belongs to, such as git's fast-forward, is neither a project-term nor a system-term;"

#case_against weak: naming one dictionary may reject a hyphenated word that other references accept.

The alternative: make parts 1 and 2, and leave the sentence of part 3 as it is.

Recommendation: make all three parts.

### D4. What a system-term is gets said four times, and the copies differ

Findings: CH5, C2-5, CT5, CT6.

Opening paragraph 1 says "A term used by one system or subsystem alone is a system-term". Paragraph 2 says "A term used by one system alone is defined in that system's glossary, not here". The project-term and system-term entries say it again. Paragraph 1 says that hyphens mark "a project-term or a system-term", while project-term says that a suffix's "leading hyphen marks it as a project-term". handoff-system calls itself "the subsystem" although it is an nn-system with its own directory, `nn-systems/handoff/`.

Part 1. Delete the first sentence of paragraph 2, "A term used by one system alone is defined in that system's glossary, not here."

Part 2. Old project-term: "a name with a meaning specific to this project and used by more than one of its systems or subsystems, listed in this glossary: an abbreviation such as GHI, a skill's slash name such as /handoff, or a hyphenated phrase such as agent-seat, or a filename suffix such as -draft, whose leading hyphen marks it as a project-term. A word this glossary does not list is not a project-term; a term one system uses alone is a system-term." New: "a name with a meaning specific to this project, used by more than one nn-system, and listed in this glossary in one of the forms the top of this page gives."

Part 3. Old system-term: "a term used by one system or subsystem alone, defined in that system's own glossary rather than here; a term used by more than one is a project-term, defined here and in no system glossary. The system glossaries are listed at the top of this page." New: "a term used by one nn-system alone, defined in that nn-system's glossary, which the top of this page lists."

Part 4. In handoff-system, change "the subsystem that replaces" to "the nn-system that replaces", and in paragraph 1 change "one system or subsystem alone" to "one nn-system alone".

#case_against medium: design-to-main has no directory under `nn-systems/` yet, and nn-system covers it only through "or whose files are still to move there".

The alternative: make only part 1.

Recommendation: make all four parts.

### D5. Project-term entries are built on terms that only a system glossary defines

Findings: CH6, CT7; the test Q4-1 proposes is P3.

design-contract uses component-consumers, test-design and test-requirement use coverage-type and no-tests, which only `docs/design-to-main/design-to-main-glossary.md` defines, and ready uses handoff-deferral, which only `nn-systems/handoff/handoff-system-glossary.md` defines. By the rule "a term more than one system uses is defined here", either these terms move here, or the entries that use them are system-terms.

Proposed change: move design-contract, design-requirement, test-design and test-requirement into the design-to-main glossary, because only design-to-main uses them. In ready, replace "while the handoff-deferral of the agent-session that would start it lasts" with "while the agent-session that would start it has put off its session-handoff, as the handoff-system glossary's handoff-deferral says".

#case_against medium: `scripts/glossary-term-has-entries-in-only-one-glossary-test.py` and every reader who now finds these four terms here must find them in another glossary instead, and whether other systems use them was not checked.

The alternative: move handoff-deferral, component-consumer, coverage-type and no-tests into this glossary.

Recommendation: before the approval-walk, search the repository for each of the four terms outside `docs/design-to-main/`, then move them, or keep them here, as that search shows. D8, D27 and D48 change the same four entries, and apply to them in whichever glossary they end up in.

### D6. "a term this page does not list is not a project-term, at least not yet" contradicts itself

Findings: C2-2.

Old: "Every project-term should be listed here; a term this page does not list is not a project-term, at least not yet."

New: "Every project-term is listed here; a term this page does not list is not a project-term until the user approves its entry."

#case_against weak: none beyond the work of the edit.

The alternative: leave the sentence as it is.

Recommendation: change the sentence to the new text.

### D7. The system-glossaries test sees only git-tracked files named `-glossary.md`

Findings: CH8, XH2, X2-1, C2-6.

Old: "A new system glossary is listed here when it is created; `scripts/system-glossaries-listed-on-the-project-glossary-test.py` fails until it is listed."

New: "A new system glossary is named `<system>-glossary.md` and listed here when it is created; once git tracks it, `scripts/system-glossaries-listed-on-the-project-glossary-test.py` fails until it is listed."

#case_against weak: it adds a naming rule, although every system glossary already follows it except `.claude/skills/skills-glossary.md`, whose name also ends in `-glossary.md`.

The alternative: change only the clause about the test, and add no naming rule.

Recommendation: change the sentence to the new text.

### D8. Entries that define a kind of text, a change to text or a check on text carry no #prose, #code or #data label

Findings: CH9, XH4, AG4, C2-7, X2-2, X2-9, X2-10, X2-19, FR Q2.3, and a point that agent-instructions-editor added when it handed out this work on 2026-11-26.

The opening says such an entry "ends with one or more of the labels #prose, #code and #data". These entries carry none: agent-instructions, initial-agent-instructions, tool-message-to-agent, design-requirement, design-contract, test-design, test-requirement, provisional-addition, GHI-MD, link-only-GHI, deferred-decisions, conversation-tail, seat-brief, supporting-document, walk-minutes, user-approved-change, pre-approved-change, hand-merge, fix-round, nn-mutation-testing and nn-test-suite. The five cold-read entries that pull request [4344](https://github.com/nedsnodes/nedsnodes/pull/4344) moved here from the skills glossary also carry none: cold-read-cell, cold-read-fast-read, cold-read-full-run, cold-read-target and cold-read-tier. Of these five, cold-read-fast-read and cold-read-full-run are checks on text and cold-read-target is a text. cold-read-cell and cold-read-tier name a thing.

Which labels each entry needs is a judgment, so the proposed change gives a label to each entry:

- #prose: agent-instructions, initial-agent-instructions, provisional-addition, GHI-MD, link-only-GHI, deferred-decisions, conversation-tail, seat-brief, supporting-document, walk-minutes, design-requirement, design-contract, test-design, test-requirement, fix-round, cold-read-fast-read, cold-read-full-run and cold-read-target;
- #prose #code #data: user-approved-change, pre-approved-change and hand-merge;
- #prose: tool-message-to-agent, which the approval page's section Prose, code and data counts as prose even inside a program's source;
- #code: nn-mutation-testing and nn-test-suite;
- no label: cold-read-cell and cold-read-tier, which name a thing.

#case_against medium: a label also narrows what the term covers ("the term does not cover a kind its labels leave out"), so a wrong label silently drops a kind. For example, #prose on GHI-MD would mean that a GHI-MD's first heading, which a program reads, is not part of the GHI-MD.

The alternative: delete the label rule and every label from the page.

Recommendation: add the labels as listed, after the user has checked each one.

### D9. The two-kinds sentence contradicts machine-readable

Findings: CH10, XH3, C2-31.

Old: "A part of a file that is two kinds at once, such as a Markdown heading that people read and a program reads as data, is covered by a term only when the term's labels name both kinds."

New: "A part of a file that is two kinds at once, such as a Markdown heading that people read and a program reads as data, is covered by each term whose labels name either kind, and gets the checks of each."

#case_against medium: this widens which terms cover such a part, and any rule that relies on the narrow reading changes with it.

The alternative: change machine-readable to say that a heading of two kinds belongs to machine-readable alone.

Recommendation: change the sentence to the new text.

### D10. The label rule does not say where prose, code and data are defined

Findings: CT8.

New sentence at the end of opening paragraph 3: "Prose, code and data are as `docs/nedsnodes-wiki/nedsnodes-which-changes-need-the-users-approval.md` § Prose, code and data defines them."

#case_against none.

The alternative: leave the paragraph as it is.

Recommendation: add the sentence.

### D11. The opening line's claims about what the page holds and its order

Findings: AG1.

The page says it is "in alphabetical order, skills first", but does not say that filename suffixes come after the skills, or how capitalised entries such as AO and GHI sort.

Old: "in alphabetical order, skills first."

New: "skills first, then filename suffixes, then every other term in alphabetical order, ignoring case."

#case_against weak: `scripts/nedsnodes-glossary-alphabetical-order-test.py` may sort another way, and the sentence must match it.

The alternative: leave the line as it is.

Recommendation: read the order test, then state the order it enforces.

### D12. /cold-read is described as a skill for readability alone

Findings: C2-8.

Old: "a skill used to improve the readability of prose."

New: "a skill that has fresh reviewers read a text and report how they understood it, so that its writer can fix what they misread or found missing."

#case_against weak: none beyond the edit.

The alternative: leave the entry as it is.

Recommendation: change the entry to the new text.

### D13. /emergency-stop says only the user runs it

Findings: CH11, XH5.

`.claude/skills/emergency-stop/SKILL.md` has an agent run the skill when the user says stop in any words, or when the agent sees an emergency it cannot stop by stopping its own work. The skill also lifts the stop.

Old: "the skill the user runs to stop every agent-seat's work at once."

New: "the skill an agent runs, when the user tells it to stop every agent-seat's work or when it sees an emergency it cannot stop by stopping its own work, to stop every agent-seat's work at once; it also lifts the stop when the user says so."

#case_against none: the new text states what the skill already says.

The alternative: leave the entry as it is.

Recommendation: change the entry to the new text. This is a pre-approved-change candidate under "Rewording a sentence of prose to remove an ambiguity or a contradiction".

### D14. /handoff uses "reincarnation threshold", which no glossary lists, and bare "handoff"

Findings: XT1, CT10.

Part 1. Add to `nn-systems/handoff/handoff-system-glossary.md`: "**reincarnation-threshold** — the share of its context window an agent-session may use before the threshold-hook tells it to write its session-handoff." Then write reincarnation-threshold in /handoff and threshold-hook.

Part 2. In /handoff, change "or the user asks for a handoff" to "or the user asks for a session-handoff". In guide-agent, change "no handoffs" to "no session-handoffs".

#case_against weak: the value and the hook that reads it were not checked against `nn-systems/handoff/` for this list.

The alternative: make only part 2.

Recommendation: check the value and the hook in the code, then make both parts. Coining a system-term is a pre-approved-change candidate, and part 2 is one under "Respelling".

### D15. -draft is defined twice, and "six more suffixes" counts the -hack paragraph or not

Findings: CH12, AG5, C2-9, CT11, and the -draft half of AG2.

`docs/nedsnodes-wiki/nedsnodes-file-naming-and-location-standards.md` § Filename suffixes defines -draft in the same words as this entry. It lists six suffixes, -draft among them, and then has a paragraph on -hack that says "The project glossary ... defines -hack". -common, which this page lists as a filename suffix, is not in that section. Whether "six more" is wrong turns on whether the -hack paragraph counts, so this is not an obvious-error.

Old: "The section "Filename suffixes" of `docs/nedsnodes-wiki/nedsnodes-file-naming-and-location-standards.md` defines it and six more suffixes."

New: "The section "Filename suffixes" of `docs/nedsnodes-wiki/nedsnodes-file-naming-and-location-standards.md` lists it among the six suffixes that mark a log, and says where each such file is kept."

#case_against weak: the definition stays in two places; only the count sentence changes.

The alternative: delete -draft's definition from the file-naming page and point that page to this entry.

Recommendation: change the sentence to the new text.

### D16. -hack and nn-hack: the tests of nn-hack code, and a dependency rule that breaks the deletion limit

Findings: CH13, C2-10, XH18.

"Code that needs nn-hack code in order to work is nn-hack too" makes `scripts/log-store-session-dialogs-refresh-hack-test.py`, and the seven other `*-hack-test.py` files, nn-hack code in files whose names end `-test`, not `-hack`. Nothing checks the rule.

Old (nn-hack): "Code that is nn-hack lives only in files whose names end with the -hack suffix."

New: "Code that is nn-hack lives only in files whose names end with the -hack suffix, except a test of nn-hack code, whose file name ends `-hack-test.py`."

The test that Q4-5 and FR Q4.2 propose is item P5 below.

#case_against weak: none beyond the edit.

The alternative: leave the entry as it is.

Recommendation: change the sentence to the new text.

### D17. nn-hack's guard rule cannot be measured, and "four limits only" is followed by more rules

Findings: CH39, XH19, C2-36, C2-37, C2-38, CT34.

"add a guard, retry or fallback to nn-hack code only when the failure it prevents happens about as often as that least reliable step fails" gives no rate. CLAUDE.md has its own two-condition rule for proposing a guard. "held to four limits only" is followed by the dependency rule and the file-name rule. "the agent's quiet recovery" has no referent. "an instruction file or a skill" names what the page calls agent-instructions.

Part 1. Old: "Beyond what the four limits require, add a guard, retry or fallback to nn-hack code only when the failure it prevents happens about as often as that least reliable step fails." New: "Beyond what the four limits require, add a guard, retry or fallback to nn-hack code only when `CLAUDE.md`'s rule for proposing one allows it and the failure it prevents has happened about as often as the agent step of the same work fails."

Part 2. Change "the way an instruction file or a skill mostly works" to "the way agent-instructions mostly work".

Part 3. Change "unlike the agent's quiet recovery" to "unlike an agent's recovery that it does not report".

#case_against medium: part 1 changes how reviewers judge nn-hack code.

The alternative: make only parts 2 and 3.

Recommendation: make all three parts.

### D18. agent-arbitrator says nothing of who starts one or what it settles

Findings: CH14, CT13.

Proposed change: before the approval-walk, find where an agent-arbitrator is started, by searching the repository for "agent-arbitrator" and "arbitrator". Then rewrite the entry to say who starts it, for which kind of disagreement, which is not a git merge conflict, and what it returns. If nothing starts one, ask the user whether to delete the entry.

#case_against none.

The alternative: leave the entry as it is.

Recommendation: do the search first, then bring the user the rewrite or the deletion.

### D19. agent-crash-watcher and failed-restart-notice: fleet-restart-at-login has no entry, the cases are stated twice, and one case is missing

Findings: CH16, AG6, C2-13, CT14, CT15.

`docs/nedsnodes-wiki/nedsnodes-handoff-architecture-overview.md` says the agent-crash-watcher restarts each agent-seat at most once an hour, that fleet-restart-at-login is "the agent-seat that owns the agent-crash-watcher", and that it "also shows him a notice after a restart that `recover-crashed-seats.py` reports started the agent-seat outside the user's systemd manager".

Part 1. In agent-crash-watcher, change "at most once an hour" to "at most once an hour per agent-seat", and change "for an agent-seat down in a state only he restarts from, for the agent-seat fleet-restart-at-login when it leaves that agent-seat down, and for a task it cannot write" to "in the cases the failed-restart-notice entry lists".

Part 2. Add to the end of failed-restart-notice: "; and after a restart that `scripts/recover-crashed-seats.py` reports started the agent-seat outside the user's systemd manager."

Part 3. Change the first "the agent-seat fleet-restart-at-login" in agent-crash-watcher to "the agent-seat fleet-restart-at-login, which owns the agent-crash-watcher".

#case_against weak: the user approved the wording "the agent-seat fleet-restart-at-login" as item 52 of approval-walk agent-instructions-editor-backlog-decisions-2026-11-05 (`nedlern@ned-box:/home/nedlern/nedsnodes-logs/walk/agent-instructions-editor-backlog-decisions-2026-11-05-minutes.md`, line 406), and part 3 adds to it.

The alternative: make parts 1 and 2 only.

Recommendation: make all three parts.

### D20. agent-home is called the directory an agent-seat works in, yet it holds no work

Findings: CH17, XH6, AG7.

Old: "the directory an agent-seat works in, `~/agents/<seat name>` on the agent-seat's machine: a git worktree that holds no work and rests on a detached HEAD at `origin/main`,"

New: "the directory an agent-seat's agent-sessions start in, `~/agents/<seat name>` on the agent-seat's machine unless `NEDSNODES_AGENTS_ROOT` names another root: a git worktree that holds no work and rests on a detached HEAD at the commit `origin/main` named at its last launch-time-git-sync,"

#case_against weak: the environment variable comes from `scripts/recover-crashed-seats.py` alone, and the launchers were not checked for this list.

The alternative: change only "works in" to "starts in".

Recommendation: check the launchers, then change the entry to the new text.

### D21. agent-seat says agent-sessions are joined by session-handoffs, but resumes and crash restarts join them too

Findings: C2-14.

Old: "held by a series of agent-sessions joined by session-handoffs."

New: "held by a series of agent-sessions, each started from a session-handoff, a resume or a restart of the one before."

#case_against weak: none beyond the edit.

The alternative: leave the entry as it is.

Recommendation: change the entry to the new text.

### D22. AO does not say what it stands for

Findings: CH18, XH7.

Proposed change: find what AO stands for in `.claude/skills/walk-me-through/SKILL.md` or in the user's words, and add it to the entry as "AO (approve, obvious)". If no source gives an expansion, ask the user.

#case_against none.

The alternative: leave the entry as it is.

Recommendation: add the expansion that a source gives.

### D23. C-numbers and frozen-copy are each used by one system

Findings: CH19, CT17.

The main-gatekeeper's C-numbers C1 to C7 cover more than "the credential that pushes to main". Outside the main-gatekeeper's files, they appear only in `docs/nedsnodes-wiki/nedsnodes-fleet-git-worktree-working-model.md` and `scripts/merge-gate-test.py`. frozen-copy belongs to the cold read and repeats cold-read-target's "copies it there at launch".

Part 1. Old C-numbers: "the identifiers `C1`, `C2` … of the main-gatekeeper's decisions on the credential that pushes to main," New: "the identifiers `C1`, `C2` … of the main-gatekeeper's decisions on credentials and their enforcement,"

Part 2. Old cold-read-target: "the document under review; a run that makes a cold-read-record copies it there at launch." New: "the document under review; a run that makes a cold-read-record copies it there at launch, as its frozen-copy."

#case_against weak: both terms stay here although one system uses each.

The alternative: move C-numbers into `nn-systems/main-gatekeeper/main-gatekeeper-glossary.md`.

Recommendation: make both parts.

### D24. close-GHI, edit-GHI and create-GHI do not say what happens when a step fails, and create-GHI's refusal can fail open

Findings: X2-4, C2-11, CH23.

`scripts/ghi-issue-write.py` asks ghi-guide-agent, and when ghi-guide-agent cannot be reached, "the write proceeds".

Old (create-GHI): "refusing when an open GHI already covers the same ground."

New: "refusing when ghi-guide-agent answers that an open GHI already covers the same ground, and filing anyway when ghi-guide-agent cannot be reached."

The failure cases of close-GHI and edit-GHI belong in the tool's docstring, not in the glossary.

#case_against none: the new text states what the code does.

The alternative: leave the entries as they are.

Recommendation: change create-GHI to the new text, and leave close-GHI and edit-GHI as they are.

### D25. code-prompt-code is defined in two places, and the definitions differ

Findings: CH21, XH8, X2-5, X2-6, AG8, C2-16.

CLAUDE.md says "Build code-prompt-code: a step that needs no judgment ... goes in code, never in a prompt", with no form check. It also requires "exactly one of a fixed list of output states". The glossary requires that the program "checks the form of what the agent returns".

Old: "then checks the form of what the agent returns, such as its required sections, before its code uses it."

New: "then checks the form of what the agent returns, such as its required sections or its one output state, before its code uses it, and reports a missing or unlisted one as a failure. `CLAUDE.md` says when to build this way."

#case_against medium: CLAUDE.md keeps its own wording, so the two texts still differ in emphasis.

The alternative: shorten CLAUDE.md's sentence to point to this entry, which changes CLAUDE.md and needs its own approval-walk item.

Recommendation: change the entry to the new text.

### D26. cosmetic-change and user-approved-change are defined here and on the approval page, and the copies differ

Findings: CH22, CT19, CT42, and the half of AG2 about the approval page.

The approval page's user-approved-change includes "carrying a user-ruling to a place that does not yet say what the user-ruling says". The glossary's definition, "a specific change the user approved before an agent makes it", excludes it.

Proposed change: make each entry a pointer only. cosmetic-change: "a change to prose that alters only its formatting or its place; `docs/nedsnodes-wiki/nedsnodes-which-changes-need-the-users-approval.md` § cosmetic-change defines it. #prose". user-approved-change: "a change the user approved, which `docs/nedsnodes-wiki/nedsnodes-which-changes-need-the-users-approval.md` § user-approved-change defines. #prose #code #data"

#case_against medium: a glossary entry that only points elsewhere makes the reader open a second page.

The alternative: move both definitions here and have the approval page point to this glossary.

Recommendation: change both entries to the new text.

### D27. design-contract and design-requirement do not say where a design's design-requirements are listed

Findings: CH24, C2-18.

Old (design-requirement): "A design's design-requirements are its list of them."

New: "A design's design-requirements are listed in its design-contract."

#case_against weak: design-to-main may list them in the design as well, which was not checked.

The alternative: leave the entry as it is.

Recommendation: check `docs/design-to-main/` for where they are listed, then change the sentence to match.

### D28. design-to-main does not say which user-rulings are "made for today's system"

Findings: CH25, C2-19.

Old: "A user-ruling made for today's system, in which an agent-seat opens a pull request, a merge-lane manages its review and merge-lane-2 merges it, does not apply to the steps inside a design-to-main run unless the user rules that it does;"

New: "A user-ruling about how an agent-seat opens a pull request, how a merge-lane manages its review, or how merge-lane-2 merges it does not apply to the steps inside a design-to-main run unless the user rules that it does;"

#case_against medium: this narrows the user-rulings that do not apply, and the user-ruling behind the sentence was not found for this list.

The alternative: leave the sentence as it is.

Recommendation: find the user-ruling behind the sentence first, then change it only as far as that user-ruling allows.

### D29. detect-instruct-correct gives no case for an action that neither the program nor the agent can undo

Findings: CH26, CT20.

New sentence at the end of the entry: "When neither can undo it, such as a message already sent, the program tells the agent what it detected, and the agent reports it to the user."

#case_against medium: this adds a rule for programs that do not yet exist.

The alternative: leave the entry as it is.

Recommendation: add the sentence.

### D30. emergency-stop file gives no path, and log-store's "byproducts ... cold-read-records first" is unclear

Findings: CH27, XH9, C2-29.

`nn-systems/skills/emergency-stop/emergency-stop-file-in-force-read-common.py` reads the file from `/home/nedlern/nedsnodes-logs/emergency-stop/` on ned-box, and through the Mac's mount at `/Volumes/nedhome/nedsnodes-logs/emergency-stop/`.

Part 1. Old: "the one file in the log-store that every agent-session is shown until the user lifts the stop." New: "the one file in the log-store's `emergency-stop/` directory, which every agent-session is shown until the user lifts the stop."

Part 2. Old (log-store): "holding the byproducts of the work that are not the system, cold-read-records first." New: "holding what the work leaves behind that is not part of the repository, such as cold-read-records, logs and the emergency-stop file."

#case_against weak: none beyond the edit.

The alternative: make only part 1.

Recommendation: make both parts.

### D31. fix-round's "the round's check" names no program, and "an overview of the pull request" reads two ways

Findings: CH28, C2-20, CT21, CT22.

Old: "plus the one nn-architecture-overview commit the round's check asks for when the round changes code an overview of the pull request describes."

New: "plus the one nn-architecture-overview commit that the `--check` of `scripts/pull-request-fix-round-author-brief-from-blocking-findings-and-one-commit-every-finding-answered-check.py` asks for when the round changes code that an nn-architecture-overview describes."

#case_against weak: the condition under which the program asks for that commit was not checked.

The alternative: leave the sentence as it is.

Recommendation: check the program's `--check`, then change the sentence to match it.

### D32. fresh-agent overstates what it has read, and fresh-reader contradicts it

Findings: CH29, CH30, XH10, C2-21, C2-22, CT24.

"every file `CLAUDE.md` names" counts files that CLAUDE.md names only for some cases. fresh-reader is "a fresh-agent ... with no context beyond the document and what it links", while a fresh-agent has also read CLAUDE.md and every glossary.

Part 1. In fresh-agent, change "every file `CLAUDE.md` names" to "every file `CLAUDE.md` tells every agent to read".

Part 2. Old (fresh-reader): "a fresh-agent, or a person, reading a document with no context beyond the document and what it links." New: "a fresh-agent, or a person, reading a document with no context beyond what a fresh-agent has read, the document and what it links."

#case_against weak: none beyond the edit.

The alternative: make only part 2.

Recommendation: make both parts.

### D33. frozen-head and nn-head-commit freeze a draft pull request's head; CLAUDE.md does not

Findings: CH31, XH11, X2-8, C2-23, CT25.

CLAUDE.md says: "A pull request's nn-head-commit becomes a frozen-head when the pull request is marked ready, or, once it is ready, the moment the commit is pushed".

Part 1. Old (frozen-head): "a pull request's nn-head-commit once pushed, which is never amended or force-pushed; a fix is a new commit on top." New: "a pull request's nn-head-commit once the pull request is marked ready, or, once it is ready, the moment the commit is pushed; it is never amended or force-pushed, and a fix is a new commit on top."

Part 2. Old (nn-head-commit): "a pull request's nn-head-commit, once pushed, is the frozen-head" New: "a pull request's nn-head-commit, once it is a frozen-head,"

#case_against none: the new text states the rule CLAUDE.md already gives.

The alternative: leave the entries as they are.

Recommendation: make both parts. This is a pre-approved-change candidate under "Rewording a sentence of prose to remove an ambiguity or a contradiction", because CLAUDE.md's sentence settles which meaning is intended.

### D34. instruction-file guard names fewer files than guarded-file, and three entries disagree on the marker for an obvious-error-fix

Findings: CH32, C2-27, CT29, AG9, CH33, XH13, C2-28, C2-40, CT36, C2-25.

The hook guards every guarded-file. The instruction-file guard entry says a change outside the approval page's list needs `#pre_approved_change`. user-block and obvious-fix marker say an obvious-error-fix uses the marker that begins "Obvious fix under CLAUDE.md's standing approval:", which the hook accepts. pre-approved-change does not name "the list". guarded-file's "with the exceptions that guard makes" names none, although the hook excepts `.test-design.md` and `.contract.md`.

Part 1. Old (instruction-file guard): "which refuses an edit to an agent-instructions file or a Claude Code settings file until the `.walk-approved` marker file holds the user's approval, for a change `docs/nedsnodes-wiki/nedsnodes-which-changes-need-the-users-approval.md` lists and does not except, or, for any other change, `#pre_approved_change` and the reason the change needs no approval." New: "which refuses an edit to a guarded-file until the `.walk-approved` marker file at the root of the checkout holds the user's approval, for a change `docs/nedsnodes-wiki/nedsnodes-which-changes-need-the-users-approval.md` lists and does not except; an obvious-fix marker, for an obvious-error-fix; or, for any other change, `#pre_approved_change` and the reason the change needs no approval."

Part 2. Old (pre-approved-change): "one not on the list of changes that need approval, or one of the list's exceptions." New: "one not on the list in `docs/nedsnodes-wiki/nedsnodes-which-changes-need-the-users-approval.md` § Changes that need approval, or one of that page's exceptions."

Part 3. In guarded-file, change "with the exceptions that guard makes" to "except a `.test-design.md` or `.contract.md` file and the other exceptions the guard's code makes".

#case_against weak: part 1 makes the entry longer.

The alternative: make parts 2 and 3 only.

Recommendation: make all three parts.

### D35. loose-end: handed-over work in an unread session-handoff, the queues, and "minutes"

Findings: CH34, C2-30, CT31, XT4; CT32 is under D43.

The entry says something is not a loose-end when an unread session-handoff lists it, and then says handed-over work is a loose-end unless a task, GHI or pull request holds it. It says a queue directory does not hold a loose-end because "nothing routinely processes them", while queue-drain is "the procedure that empties the queue directories".

Part 1. Old: "Work handed to another agent-seat is a loose-end unless a task, GHI or pull request holds it on one side or the other," New: "Work handed to another agent-seat is a loose-end unless a task, GHI or pull request holds it on one side or the other, even when a session-handoff lists it,"

Part 2. Change "A closed approval-walk's minutes" to "A closed approval-walk's walk-minutes".

Part 3. Change "because nothing routinely processes them" to "because only a queue-drain, which no schedule starts, processes them".

#case_against weak: it was not checked whether a schedule starts a queue-drain.

The alternative: make only part 2.

Recommendation: check whether a schedule starts a queue-drain, then make all three parts. Part 2 is a pre-approved-change candidate under "Respelling".

### D36. nn-architecture-overview says there is one page per system, but only the handoff-system has one

Findings: CH35, AG10 (second half).

Old: "In this project, it is one wiki page per system under `nn-systems/`, `docs/nedsnodes-wiki/nedsnodes-<system>-architecture-overview.md`,"

New: "In this project, each nn-system has, or is to have, one wiki page, `docs/nedsnodes-wiki/nedsnodes-<nn-system directory name>-architecture-overview.md`,"

#case_against weak: the name pattern still matches `nedsnodes-how-to-write-an-architecture-overview.md`.

The alternative: leave the sentence as it is.

Recommendation: change the sentence to the new text.

### D37. nn-test-suite says that a selective run includes every suite the change may affect, but the runner leaves some out

Findings: CH37, XH16, AG12, X2-12.

The docstring of `scripts/run-all-test-suites.py`, under SUITES LEFT OUT OF A SELECTIVE RUN, leaves out some suites the selection would have picked, and under WHAT A RECORDING CANNOT SEE it lists inputs that a recording misses. The runner also reports a suite killed by a stopped run "as stopped, not as failed".

Old: "which include every nn-test-suite the change may affect;"

New: "which leave out the suites that the runner's docstring lists under SUITES LEFT OUT OF A SELECTIVE RUN and can miss what it lists under WHAT A RECORDING CANNOT SEE;"

#case_against none: the new text states what the code does. The glossary is excepted from the approval page's exception for updating wiki pages to match the code, so this change needs the user.

The alternative: delete the clause.

Recommendation: change the clause to the new text.

### D38. nn-topic-branch excludes a branch whose pull request is not yet open

Findings: CH38, C2-35.

Old: "in this project, the branch whose commits a pull request brings into main."

New: "in this project, the branch whose commits a pull request brings, or will bring, into main."

#case_against none.

The alternative: leave the entry as it is.

Recommendation: change the entry to the new text.

### D39. one-off-prompt: "never kept in a checkout", and a sentence that reads as a description or an instruction

Findings: CH40.

Old: "The user does not review a one-off-prompt; a brief to a fresh subagent gets the cold-read-fast-read."

New: "The user does not review a one-off-prompt; an agent gives a brief to a fresh subagent a cold-read-fast-read before it dispatches the subagent, when the brief is longer than a lookup."

#case_against medium: this turns a sentence that may describe practice into a rule, with a threshold the user has not set.

The alternative: delete the second clause.

Recommendation: change the sentence to the new text, without the clause "when the brief is longer than a lookup".

### D40. outside-program-term says "never pull-request", yet ready writes "a pull-request review"

Findings: CH41, C2-44, CT39.

In ready, change "a cold-read-full-run or a pull-request review" to "a cold-read-full-run or a review of a pull request". The word check that Q4-4 proposes is item P4 below.

#case_against none.

The alternative: leave the entry as it is.

Recommendation: make the change. It is a pre-approved-change candidate under "Rewording a sentence of prose to remove an ambiguity or a contradiction", because outside-program-term settles the spelling.

### D41. proposed-improvements-or-changes-file leaves "ruling questions", `<source>` and `<date>` undefined

Findings: CH42, XT7, X2-14, C2-41, CT37.

Proposed change: read how `scripts/ghi-issue-write.py` names the file, then rewrite "ghi-guide-agent's ruling questions about a GHI-MD" as "the questions ghi-guide-agent raises for the user about a GHI-MD", and give the name as `<document name>-proposed-improvements-or-changes-ghi-guide-agent-<YYYY-MM-DD>.md`, with the numeric suffix the tool adds when that name is taken.

#case_against weak: none beyond the edit.

The alternative: leave the entry as it is.

Recommendation: check the tool, then rewrite the entry to match it.

### D42. provisional-addition says "an issue's Markdown file", "a ruling" and "reviews the issue"

Findings: CH44, XH20, C2-42.

Old: "a line an agent adds to an issue's Markdown file under "Provisional additions (not yet vetted by the user)", which becomes a ruling only when the user reviews the issue."

New: "a line an agent adds to a GHI-MD under "Provisional additions (not yet vetted by the user)", which becomes a user-ruling only when the user approves it in an approval-walk."

#case_against medium: "approves it in an approval-walk" is narrower than "reviews the issue", and the user may have meant any review.

The alternative: change only "an issue's Markdown file" to "a GHI-MD" and "a ruling" to "a user-ruling".

Recommendation: change the entry to the new text.

### D43. queue-drain does not name the queues, and its outcomes do not always empty them

Findings: CH45, XH21, X2-15, C2-43, CT32.

The GHI-MD of GHI [Queue drain procedure — the review process that empties the wiki queue, the pair queue, nn-queue, the drafts directory and the queue-drain-candidate-label issue queue](https://github.com/nedsnodes/nedsnodes/issues/24), `docs/issues/24-queue-drain-procedure-the-review-process-that-empties.md`, allows the outcomes "edit", which keeps an item queued, and "demote". It also covers the GHIs labelled `queue-drain-candidate`, which are not a directory.

Old: "the procedure that empties the queue directories and `docs/drafts/`, promoting, archiving or deleting each item;"

New: "the procedure that reviews each item in `docs/nedsnodes-wiki/queue/`, `docs/issues/queue/`, `docs/agents/queue/`, `docs/drafts/` and the issues labelled `queue-drain-candidate`, and promotes, edits, demotes, archives or deletes it;"

#case_against weak: That GHI's title also names "the pair queue" and "nn-queue", which were not found as directories for this list.

The alternative: leave the entry as it is.

Recommendation: check that GHI-MD for the full list of queues, then change the entry to match it.

### D44. ready: "long work" has no threshold

Findings: CH46, CT38.

Old: "Nor is long work ready, such as a cold-read-full-run or a pull-request review,"

New: "Nor is work that starts a cold-read-full-run, a review of a pull request or any other run of fresh-agents ready,"

#case_against medium: other long work, such as a full test run, would then count as ready during a handoff-deferral.

The alternative: leave "long work" and add "work expected to take more than 10 minutes".

Recommendation: change the sentence to the new text.

### D45. ruling-agent ends in -agent like guide-agent, but is an agent-seat

Findings: CH47.

Proposed change: none to the name, since /cold-read does not propose renaming a project-term. Add to the end of guide-agent: "A name ending in -agent does not mark a guide-agent: ruling-agent is an agent-seat."

#case_against weak: it adds a sentence to explain a name.

The alternative: leave both entries as they are.

Recommendation: add the sentence.

### D46. shared-log claims every program writes it through Python's logging, and gives no path

Findings: CH48, XH22, XH23, X2-17, C2-50.

Old: "the one log that every program on a machine writes to through Python's logging, one JSON line per event, copied to the log-store."

New: "the one log that every Python program of this repository on a machine writes to through Python's logging, one JSON line per event, at the path that its setup code in `nn-systems/general-tools/` gives, copied to the log-store."

#case_against weak: the setup module's path was not found for this list, and the entry should name it.

The alternative: change only "every program" to "every Python program of this repository".

Recommendation: find the setup module, then write its path into the entry.

### D47. standing-agent-instructions is defined in CLAUDE.md too, under the unhyphenated "Standing instructions"

Findings: CH49, XH24, AG15, C2-51, X2-18.

Proposed change in CLAUDE.md: change "Standing instructions, which are this file, `AGENTS.md`, the seat-briefs, every `-instructions.md` and `-prompt.md` file, every skill's `SKILL.md`, and every agent definition in `.claude/agents/`, hold instructions" to "standing-agent-instructions, as the project glossary defines them, hold instructions".

#case_against medium: CLAUDE.md is read first and is the most costly file to change; the list there saves every agent a lookup.

The alternative: keep CLAUDE.md's list and respell it "Standing-agent-instructions", which is a pre-approved-change candidate under "Respelling".

Recommendation: make the respelling of the alternative.

### D48. test-design says one test-requirement per design-requirement "a test must observe", but test-requirement allows `no-tests`

Findings: CH50, C2-52.

Old: "listing one test-requirement per design-requirement a test must observe,"

New: "listing one test-requirement for each design-requirement in its design-contract,"

#case_against none.

The alternative: leave the entry as it is.

Recommendation: change the entry to the new text.

### D49. tool-message-to-agent blames the writing program for any message that never arrives

Findings: CH51, X2-20.

Old: "A tool-message-to-agent that never reaches the agent is a defect of the program that writes it."

New: "A tool-message-to-agent that never reaches the agent is a defect of the program that writes it, unless the agent-binary drops it."

#case_against weak: none beyond the edit.

The alternative: leave the sentence as it is.

Recommendation: change the sentence to the new text.

### D50. user-alert says "a failure only the user can fix", but the agent-crash-watcher writes one for a failure an agent can fix

Findings: CH52, XH25, X2-21, C2-53.

`nn-systems/handoff/handoff-agent-crash-watcher.py` writes a user-alert whose text says "An agent on ned-box can fix why the crash watcher could not write the task". The entry also does not say what happens when no approval-walk is open, or whether one prompt claims every pending alert.

Part 1. Old: "when it hits a failure only the user can fix;" New: "when it hits a failure that it must bring to the user;"

Part 2. Old: "and the agent turns it into the next item of his approval-walk." New: "and the agent turns it into the next item of his approval-walk, opening one when none is open."

#case_against weak: whether one prompt claims every pending alert was not checked against `nn-systems/general-tools/user-alerts-pending-and-claimed-files-write-claim-release-and-delete-common.py`.

The alternative: make only part 1.

Recommendation: check the claim code, then make both parts.

### D51. handoff-supervisor leaves out the terminal check, and "brought new work" is undefined

Findings: XH12, C2-26.

`nn-systems/handoff/handoff-supervisor.py` resumes only when a terminal is attached (`sys.stdin.isatty()`).

Old: "resumes it if it exited with a non-zero code and its last resume, if any, brought new work;"

New: "resumes it if it exited with a non-zero code, a terminal is attached, and its last resume, if any, added to its transcript;"

#case_against weak: "added to its transcript" is this list's reading of "brought new work" and was not checked in the code.

The alternative: add only "a terminal is attached".

Recommendation: check what the code counts as new work, then change the sentence to match.

### D52. ned-box is defined both here and in CLAUDE.md

Findings: XH17, AG13.

The two definitions agree, and CLAUDE.md's sentence is a rule about where commands run, not a definition. No change is proposed.

#case_against weak: two texts can drift apart.

The alternative: shorten CLAUDE.md's description of ned-box to a pointer.

Recommendation: leave both as they are.

### D53. cold-read-record and walk-minutes do not say what happens when shipping fails

Findings: X2-7, X2-22.

The shippers say this themselves (the /cold-read skill's step 9 gives `REFUSED:` and `FAILED:`). No change is proposed: a glossary entry need not state every failure of the program it names.

#case_against weak: none.

The alternative: add "until it reaches the log-store, the checkout's copy is the only one" to cold-read-record.

Recommendation: leave both entries as they are.

### D54. nn-shared-database's "later stores" is undefined

Findings: X2-13.

Old: "which the project's later stores join as tables of their own;"

New: "which each later store of this project's data joins as a table of its own;"

#case_against none.

The alternative: leave the entry as it is.

Recommendation: change the entry to the new text.

### D55. Words that no glossary defines: build plan, NNNN, MD, scratchpad and the launchers

Findings: C2-15, C2-17, C2-24, C2-39, C2-48.

Part 1. In build-slice, change "a build plan" to "a build plan, the part of a design that lists its build-slices".

Part 2. In conversation-tail, change "`~/.claude/handoffs/<seat>-dialog-NNNN.md`" to "`~/.claude/handoffs/<seat>-dialog-NNNN.md`, NNNN being the agent-session's number in its agent-seat's series", after checking it against `nn-systems/handoff/handoff-supervisor.py`.

Part 3. In GHI-MD, change "the MD file used to explain a GitHub issue." to "the Markdown file under `docs/issues/` that holds the text of a GHI."

Part 4. In seat-branch, change "that the launchers created" to "that the launchers `scripts/launch-claude-mac` and `scripts/launch-claude-ubuntu` created".

Part 5. In one-off-prompt, change "written in the agent's scratchpad" to "written in the scratchpad directory that Claude Code gives each agent-session". D58 part 5 covers PR.

#case_against weak: each part adds words to an entry.

The alternative: make parts 3 and 4 only.

Recommendation: make all five parts, after checking part 2 in the code.

### D56. reusable-prompt, SDLC-term and user-ruling say more than holds

Findings: C2-46, C2-47, C2-54.

Part 1. In reusable-prompt, change "a file in a checkout whose name ends in `-prompt.md` or `-instructions.md`, or prompt text in code" to "such as a file in a checkout whose name ends in `-prompt.md` or `-instructions.md`, or prompt text in code".

Part 2. In SDLC-term, change "lists those this project relies on" to "lists those this project relies on that a reader might take for project-terms".

Part 3. user-ruling's "recorded where it applies in the form (user-ruled YYYY-MM-DD)" is against CLAUDE.md's "Program text, code comments and standing instructions carry no history or citations". Add "except in standing instructions, which carry none" after "(user-ruled YYYY-MM-DD)".

#case_against weak: part 2's condition is this list's reading of the SDLC-terms page.

The alternative: make parts 1 and 3 only.

Recommendation: make all three parts.

### D57. seat-brief says "the root of an agent-seat's checkout", and "occupant"

Findings: AG14, C2-49, CT40.

Old: "the `CLAUDE.local.md` at the root of an agent-seat's checkout, which git does not track: the file an agent-seat's occupant reads to learn its job."

New: "the `CLAUDE.local.md` at the root of an agent-seat's agent-home, which git does not track: the file each agent-session of the agent-seat reads to learn its job."

#case_against none.

The alternative: leave the entry as it is.

Recommendation: change the entry to the new text.

### D58. Plain words written where a listed term exists

Findings: XT2, XT3, XT6, CT26, CT27, CT28, CT30, CT35.

Part 1. In ghi-guide-agent, change "the GHI knowledge agent, which an agent asks, with `scripts/ghi-guide-agent-ask.py`, which issues to read before filing or editing an issue" to "the guide-agent for GHIs, which an agent asks, with `scripts/ghi-guide-agent-ask.py`, which GHIs to read before filing or editing a GHI".

Part 2. In link-only-GHI, change "its GHI-MD and supporting documents" to "its GHI-MD and supporting-documents".

Part 3. In nn-test-sandbox, change "what a suite can see, and which suites and machines get one" to "what an nn-test-suite can see, and which nn-test-suites and machines get one".

Part 4. In ID-type, change "and the ordinary word for a commit, task or session" to "and the ordinary word for a commit or task, and agent-session for an agent-session".

Part 5. In guide-agent, main-gatekeeper and merge-lane, write "pull request" for "PR", and in obvious-error, obvious-error-fix and ready, write "user-approved-change" where the text means one.

#case_against none.

The alternative: leave the entries as they are.

Recommendation: make all five parts. Parts 2, 3 and 5 are pre-approved-change candidates under "Respelling".

### D59. Bare words that carry several meanings on the page: system, label, cold read, checkout and worktree

Findings: CT4, CT9, CT16, CT18.

"system" means an nn-system in the opening, and something wider in log-store ("not the system"), design-to-main ("today's system") and /handoff ("a system message"). "label" means a #prose label, a GitHub label and Claude Code's "hook error" label. "cold read" is unlisted and is also written "cold-read" as a verb. "checkout" and "worktree" name the same thing.

Proposed change: write nn-system wherever the page means one, and leave the other meanings of "system" as ordinary words. In tool-message-to-agent, change "Claude Code's "hook error" label" to "Claude Code's "hook error" prefix". In tool-message-to-agent, change "found, cold-read, tested and rewritten" to "found, given a cold read, tested and rewritten". Leave "checkout" and "worktree" as they are, since git uses both.

#case_against weak: "cold read" stays unlisted.

The alternative: ask the user for a project-term for a cold read.

Recommendation: make the changes as listed.

### D60. "fast-clarify" in the cold-read-fast-read entry is in no glossary

Findings: a point that agent-instructions-editor added when it handed out this work on 2026-11-26.

"fast-clarify" names the prompt `.claude/skills/cold-read/prompts/fast-clarify-prompt.md`, whose copy `nn-systems/cold-read/cold-read-fast-read.py` holds as `FAST_CLARIFY_PROMPT_TEMPLATE`. None of the listed glossaries has an entry for it. The name exists, so this is not an obvious-error. cold-read-full-run's "the defect-hunt prompt and the terminology prompt" names its prompts the same way, but without the hyphenated form.

Old: "one fast-clarify cold-read-cell on the fast cold-read-tier"

New: "one cold-read-cell on the fast cold-read-tier under the prompt `.claude/skills/cold-read/prompts/fast-clarify-prompt.md`"

#case_against none.

The alternative: add a fast-clarify entry to this glossary.

Recommendation: change the phrase to the new text.

## Proposed programs

Each of these is a separate pull request, if the user approves it. Every finding below asks for code, so it goes to the user as a program to build or not.

- P1, a test that each term on a listed glossary fits one of the four forms, allowing an `(aka X)` suffix. Finding: Q4-3. Today it would flag ready and the three terms that contain a space (D2). Recommendation: build it after the user decides D2, so that the test encodes the forms he chose.
- P2, a term lookup program and a test that every hyphenated term inside an entry has an entry in some listed glossary, with an allow-list for agent-seat names and paths that also accepts every word on `docs/nedsnodes-wiki/nedsnodes-ordinary-hyphenated-words-list.md`. Finding: Q4-2. Today the test would flag fast-clarify (D60), reincarnation threshold (D14) and minimal-context (D3). Recommendation: build both.
- P3, a test that a system-term is used by one system only. Finding: Q4-1. It would have caught D5. Recommendation: build it after the user decides D5.
- P4, a word check that flags `pull-request` outside a file, skill or script name. Finding: Q4-4. Recommendation: add the check to `scripts/style-guide-word-checker-hack.py`, if that checker can tell a name from prose; otherwise build nothing.
- P5, a test that no file without the -hack suffix imports, loads or runs a -hack file, apart from a reviewed allow-list, and that each -hack file's docstring has the parts the nn-hack entry requires. Findings: Q4-5, FR Q4.2. `scripts/handoff-extract-conversation.py` loads `scripts/handoff-extract-conversation-subagent-tracker-hack.py` and would be the first case on the allow-list. Recommendation: build it.
- P6, a test of the #prose, #code and #data label format: only those three, only at the end of an entry, separated by single spaces, and on no entry for a skill or a filename suffix. Findings: Q4-10, FR Q4.3. Recommendation: build it.
- P7, a test that design-requirement names are unique across the repository and that each test-design matches its design-contract one to one. Finding: Q4-6. Recommendation: file it through /ghi-write, which finds the GHI that covers design-to-main's tests.
- P8, the program that sends a message between agent-seats, not identified for this list, opens the sender's task when work is handed over and closes it on the receiver's acknowledgement. Finding: Q4-7. Recommendation: build nothing until a handed-over loose-end has been lost, as CLAUDE.md's rule on guards requires.
- P9, a program that answers ready's state checks: whether a pull request has merged, whether ned-box can be reached, and whether a handoff-deferral is active. Finding: Q4-8. Recommendation: build nothing until an agent has started work that was not ready.
- P10, the cold-read programs, `nn-systems/cold-read/cold-read-grid.py` and `nn-systems/cold-read/cold-read-fast-read.py`, put a document's `Deferred-decisions` section into the reviewer's prompt. Finding: Q4-9. Recommendation: file it through /ghi-write, which finds the GHI that covers the cold-read programs.
- P11, a test that every backticked repository path in the glossary exists and every quoted section or docstring heading appears in the file it names. Finding: Q4-11. The nn-test-suite reference that work item 2 fixes would have failed it. Recommendation: build it, and run it over the system glossaries too.

## Proposals from the cold-read-fast-read of 2026-11-26

The cold-read-fast-read of work item 2's change, in the cold-read-record `nedlern@ned-box:/home/nedlern/nedsnodes-logs/cold-read-records/nedsnodes-glossary-2026-11-26-3` and cited here as F26, found nothing about the changed sentence. Seven of its findings repeat earlier ones: Q2.1 repeats D40, Q2.2 repeats D2, Q4.2 P5, Q4.4 P8, Q4.7 P7, Q4.8 P1 and P6, and Q4.9 P2. Its other findings propose code. CLAUDE.md allows a guard only once its failure has happened or is shown to be foreseeable, and none of these failures is cited, so each recommendation is to build nothing until it is:

- P12, a pre-push hook that refuses a push that is not a fast-forward to the branch of a ready pull request. Finding: F26 Q4.1.
- P13, a scheduled-jobs entry that runs `scripts/scheduled-full-mutation-pass-of-merged-pull-requests-and-survivor-tasks-open.py` as a maintenance-job. Finding: F26 Q4.3. This is a decision about cost, not a guard, so the recommendation is to ask the user.
- P14, a script that retires an agent-seat in the four steps of `docs/nedsnodes-wiki/nedsnodes-agent-seat-model.md`. Finding: F26 Q4.5.
- P15, a check that a hand-merge changed only the paths that conflicted. Finding: F26 Q4.6.
- P16, a hook that refuses to dispatch a fresh subagent whose brief has had no cold-read-fast-read. Finding: F26 Q4.10.
- P17, a commit-msg hook that requires a source line in a commit made with an obvious-fix marker. Finding: F26 Q4.11.
- P18, a maintenance-job that deletes nn-one-shot-canary-tests older than 30 days from the log-store, and a test that no `-common` file runs on its own. Findings: F26 Q4.12, F26 Q4.13.
