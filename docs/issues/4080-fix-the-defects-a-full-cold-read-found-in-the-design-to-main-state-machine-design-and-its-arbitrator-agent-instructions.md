---
issue: "[Fix the defects a full cold read found in the design-to-main state machine design and its arbitrator agent-instructions](https://github.com/nedsnodes/nedsnodes/issues/4080)"
---

# Fix the defects a full cold read found in the design-to-main state machine design and its arbitrator agent-instructions

## What is wrong

On 2026-10-03 six cold-read-cells read the passages that pull request [design-to-main: a resume from the arbitrator's third-entry investigation is an ordinary resume; the held-ruling replay is removed](https://github.com/nedsnodes/nedsnodes/pull/4002) changes in the design-to-main state machine design, `docs/design-to-main/design-to-main-state-machine.system.design.md`, in the arbitrator's agent-instructions, `docs/agents/queue/design-to-main-test-suite-arbitrating-agent-instructions.md`, and in their README, `docs/agents/queue/design-to-main-agent-instructions-README.md`. That pull request merged on 2026-11-21 with the defects in the text it changed fixed. The cold-read-cells also found defects in text that pull request does not change, and its triage deferred them to a GHI. They are listed below, so that someone can fix them in a later pull request.

The reports and the triage are in the cold-read-record `nedlern@ned-box:/home/nedlern/nedsnodes-logs/cold-read-records/design-to-main-ordinary-resume-after-third-entry-passages-2026-10-03/`; the triage in that directory, `cold-read-triage.md`, lists which findings were deferred. Each report is a file in the same directory, named here by its abbreviation in that triage: CHD is `claude-hunt-deep.md`, CHS `claude-hunt-second.md`, XHD `codex-hunt-deep.md`, XHS `codex-hunt-second.md`, CTD `claude-terminology-deep.md` and XTD `codex-terminology-deep.md`; a number after the abbreviation is the number of the finding in that report. A Q number is a finding of the cold-read-fast-read of the rewritten passages, `nedlern@ned-box:/home/nedlern/nedsnodes-logs/cold-read-records/design-to-main-ordinary-resume-after-third-entry-passages-rewrite-2026-11-20/cold-read-fast-read.md`. The reports quote the files at their 2026-10-03 names and line numbers; each defect below was checked against `main` at commit `3ce20669d` on 2026-11-21, and is quoted from that commit. Findings that `main` has fixed since are left out: CTD 6, whose "no arbitrator launched" wording the merged pull request removed; and CHS 6 and CTD 2, which are about the cold-read document's own introduction and title.

Why it matters: the design is the specification the design-to-main build, GHI [Build the design-to-main state machine: the Python machine, its per-state agent-instructions, and the nine items the design defers to the build](https://github.com/nedsnodes/nedsnodes/issues/282), implements and binds by tests, and the agent-instructions are what each agent in a design-to-main workflow execution acts on. Where the design says one thing and the code does another, or a sentence has two readings, the builder or the agent picks one, and two agents pick differently.

## The defects

### Counting and the design version

1. The design counts the arbitrator's third entry "in a design version" (§3.2's bullet "The arbitrator is launched in two states", §6.6's list of what opens an investigation, §7's arbitrator-rulings row, row 65's "entered for the third time in the design version"), while every `resume` zeroes the six per-version counters without starting a new design version (§7: "A resume from an investigation zeroes the six per-version counters"). The machine opens the investigation when the counter reaches its ceiling since the last zeroing, so one design version can hold several third entries. Reports: CHD 3, 6, 22, 26, 35; CHS 9; XHD 2; XHS 1; XTD 1; CTD 4, 5.
2. Row 65's trigger, "applied on entry, the arbitrator not ruling on that entry", does not say what is applied, and its counter column "—" reads as "no counter changes", though §7 increments arbitrator-rulings on every entry. Reports: CHD 22, CHS 22, CHS 23.
3. §7's arbitrator-rulings row says the writer's counter "stops deciding once the arbitrator is in and is not reset", while every `resume` zeroes it. "reset" is also the design-to-main glossary's word for the user's zeroing of every counter. Reports: CHD 36, CHS 30, XHD 19, CTD 24.
4. §6.5's "A fresh arbitrator is launched only when that one is lost, as in a crash" leaves out the investigation the main-gatekeeper's rejection opens after the arbitrator's life ended at `submit-to-PR-gate`, in which a fresh arbitrator is launched with none lost. Reports: CHD 28, XHD 13. XTD 6 raises the same lifetime comparison for the initiator.
5. §6.5's first sentence, "`test-suite-arbitrating` launches the one reviewer", reads as a launch on every entry, and "on its first and second entries it rules alone" makes the state, which does not rule, the subject. Report: CHS 26.
6. §7's rule "The third failed implementation-write goes to the arbitrator" counts failures, while the implementation-writes counter counts emitted writes, the first included; the two disagree when a write passes review and a later one fails. Report: XHD 20.
7. "dropping the refusal the earlier rule carried" (§6.6) does not say what was refused. Reports: CHD 25, CHD 32, CHS 29, CTD 21.

### The arbitrator's return from an investigation

8. The arbitrator's instructions say a returned arbitrator rules "on the failed test suite or the reviewer's ceiling that entered it before the pause", and do not cover a pause that a suite which could not run twice caused. Reports: CHD 11, CHS 12, XHD 4, Q2.5.
9. The same sentence's "your `advance` means what it meant then" reads as if `advance` could follow a failed suite, which the arbitrator's own table forbids. Report: Q2.2.
10. "a `resume` may name `test-suite-arbitrating` only from an investigation that paused there" does not say what the machine does when a `resume` names it from another investigation. Reports: CHS 13, Q3.2.
11. What the returning arbitrator receives to avoid repeating its earlier determination is not said; the machine records what entered the state (`test-suite-arbitrating-entered-from` in `scripts/design-to-main/design-to-main-run-state.py`) and could hand it over. Reports: Q3.3, Q4.1.

### Resume routing

12. The design does not give the routing on `resume` when several artifacts are edited, both work-streams' artifacts, a component file together with another file, or an edit together with a named destination; and `resume` routes "the earliest state downstream of what the user changed" without saying how an edit only to files inside the component's record directory, such as a corrected note, is classed. Reports: CHD 24, CHD 30, XHD 14, XHD 15, XHD 16, XHS 6, CHS 24, Q3.1.
13. The arbitrator's instructions say "`stop` is how a run ends", but a `resume` toward a redesign at the redesigns ceiling ends the workflow execution (row 73), and so does the main-gatekeeper accepting after `submit-to-PR-gate`. Reports: CHD 14, XHD 6.
14. "Any document the user edited is re-read" does not say whether scripts and tests count, nor who receives the cold-read reports. Reports: CHD 34, XHD 17.

### The state-exit

15. §2 says "`state`, `verdict` and `package-commit` required", while the same section says `named-files` is "always written" and the code requires it: `STATE_EXIT_JSON_FIELDS_REQUIRED = ("state", "verdict", "package-commit", "named-files")` in `scripts/design-to-main/design-to-main-state-tables-common.py`. Reports: CHD 16, CHD 19, CHS 20, XHD 11.
16. §2's "the one the verdict needs" reads as if every verdict needs one of those fields; the README already says "where it needs one". Report: CHD 18.
17. §2's "The three sentences before this one were written down on 2026-09-11, the ninth walk" dates sentences that cite user-rulings of 2026-09-14. Reports: CHD 20, CHS 19, XHD 9.
18. "a writing state's `emitted` that names none is a machine error, since a write that named no file did not happen" leaves no valid state-exit for a test-writer whose set is all `no-tests`, which writes no test file; and a write the agent made but did not name did happen, so the reason given is wrong. Reports: XHD 7, XHD 8, XTD 9.
19. `refusal-class` is "`submit-to-PR-gate`'s, which launches no agent", while the state-exit is described as a file the agent writes; who writes `submit-to-PR-gate`'s state-exit is not said. Report: XHS 3.
20. "Every state emits one state-exit per instance" overstates: `ended` emits none, and a process can die before its state-exit is committed. "instance" is also used both for one entry of a state and for the life of an agent that stays across entries. Reports: XHD 10, XHS 4, CTD 15, XTD 7.
21. The README lists `investigation-focus` as "(`design`, `test-design`)", while the arbitrator's instructions give the report's investigation-focus four values, `design`, `contract`, `test-design` or `unknown`; whether these are one field is not said. Reports: CHS 15, XHS 2, Q2.3, CTD 7.

### Other passages

22. The arbitrator's instructions give the report's path with `<n>` and do not say what `<n>` counts or that the state-package hands the path over as `investigation-report`, which §9 says. Report: CHD 10.
23. §6.5's "a failed suite, which is the one way the two work-streams' disagreement becomes visible after review" excludes a disagreement the arbitrator finds on a reviewer's-ceiling entry, and one that shows as `could-not-run`. Report: XHD 12.
24. "a ruling that changes intent is written into the design at the next redesign or by the user's own edit" guarantees neither before the workflow execution ends, so the delivered design can keep an intent the user overruled. Reports: XHD 18, Q4.5.
25. §7's "so that the reviewer's rejections never leave the arbitrator with no chance of its own" does not hold when two failed suites have already spent arbitrator-rulings: the reviewer's next rejection is the arbitrator's third entry, on which it does not rule. Report: XHD 21.
26. The README's "which these drafts do on `resume` alone" and the design's "the talking agent" leave the reader to work out which files and which agent are meant; §6.6 names "the arbitrator" for every investigation, though one opened before any arbitrator exists is the initiator's. Reports: CHS 14, CHS 27.

### Terms, for the user to decide

27. Words that differ from the glossaries' terms or carry two meanings: "design version" and "redesign" have no glossary entry of their own in the sense used (CTD 5, CTD 19); arbitrator-rulings is not in the design-to-main glossary (XTD 2); "rulings" is used both for the user's user-rulings and for the arbitrator's decisions (CTD 3, XTD 3); "the reviewer's ceiling" names an event with the word for a counter's maximum (CTD 9, XTD 4); "type" for coverage-type (XTD 5); "exit" and "exits" for both the state-exit file and the investigation's verdicts (CTD 17, XTD 10); bare "walk" in citations where the project glossary's term is approval-walk (CTD 16, XTD 8); "script tests" for code-based-test (CTD 18); "a suite that could not run" for `could-not-run` (CTD 20); "entry" for one string of `rulings` (CTD 11); the record directory and the branch history both called "the record" (CTD 14); state-exit defined again in §2 and the README (CTD 12); "machine error" (CTD 13); "refreshes" (CTD 22); "program check" (CTD 23); "cold-read runs" (CTD 8); and the bare "arbitrator" beside the project glossary's agent-arbitrator (CTD 1). The term proposals are in the "Proposed definitions" sections of the two terminology reports, `claude-terminology-deep.md` and `codex-terminology-deep.md` in the cold-read-record named above.

### What could be code

28. The cold-read-fast-read's question 4 proposes code for work the agents now do by hand: running and counting the two cold-read-full-runs of the investigation report (Q4.2); writing the report's header from what the machine holds and checking that each commit it cites exists (Q4.3); refusing a `resume` whose branch was rebased, since the resume's diff starts at the commit the investigation opened at (Q4.4); and checking that each `rulings` entry is the user's words verbatim (Q4.6). The cold-read-fast-read of this GHI-MD added two more: a test pairing each prose list in the design with the constant that holds the same rule in code, as the design's tables are already paired, so the prose cannot drift from the code again; and, once the user has decided the terms of defect 27, a test that fails when a retired word comes back into these files.

### Found later, outside that cold read

29. §4's paragraph "Every writing state that emits prose cold-reads it inside the state before emitting" (line 366 of the design on `main` at commit `553233b9f`) says the cold-read reports return to the writer, "never to a fresh one", and backs it with "a fresh author given the reports resolved 14–17 of 50 known defects; the writer's own revision resolved 42.7". The report it cites, `nedlern@ned-box:/home/nedlern/nedsnodes-logs/cold-read-records/2026-09-03-cold-read-tier-roster-campaign/REPORT.md`, finding 3 below its table of arms, says the 42.7 came from "the author's own 09-02 fix pass", which "had the repository, could measure git's actual behaviour, and worked without a word budget", while the one-pass authors had "no repo access" and were held "within 90 to 96 percent of the original length". So the two numbers differ in repository access and word budget as well as in who revised, and do not show that the writer revises better than a fresh agent. The user has not decided on the rule itself; only its evidence is in question. Agent-seat MD-skills found this on 2026-11-22.

## The work

Several of these rules are already held in code, so a change to the prose may also change the code and its tests: the required state-exit fields are `STATE_EXIT_JSON_FIELDS_REQUIRED` and the resume routing is `RESUME_DESTINATION_BY_EDITED_DOCUMENT`, both in `scripts/design-to-main/design-to-main-state-tables-common.py`; `refuse_a_write_that_named_no_file` (defect 18) and `refuse_malformed_resume` (defect 10) are in `scripts/design-to-main/design-to-main-state-machine.py`; and tests pair the design's tables with the code in the same file. The design is a file the instruction-file guard protects, by its `.design.md` name; the agent-instructions in `docs/agents/queue/`, which are pending approval, are not.

1. Check each defect against `main` as it then stands, and drop each one `main` has fixed.
2. Bring the user the remaining defects, each with a proposed change, the term proposals of defect 27 and the programs of defect 28, in one approval-walk.
3. Carry out what he approves, in as many pull requests cut from `main` as `CLAUDE.md` requires, since each pull request merges one nn-topic-branch and holds nothing outside its topic; each program of defect 28 he approves is its own pull request. Record each defect's outcome in this GHI-MD: a defect he disapproves is marked as left as it is, and one he defers stays listed here. Close this GHI when no defect is left undecided or approved but not carried out.

## What is decided

- On 2026-11-22 the user deferred this GHI's 28 defects until he resumes the design-to-main build, and said to coordinate then with the agent-seats Cpc and helper2. His ruling is item 36 of `nedlern@ned-box:/home/nedlern/nedsnodes-logs/walk/ai-native-software-development-objective-page-cleanup-2026-11-17-minutes.md`.

## Next action

None until the user resumes the design-to-main build. Then the agent-seat agent-instructions-editor, which makes changes to the files the instruction-file guard protects, does work item 1 and runs the approval-walk of work item 2. The design-to-main build is paused by the user since 2026-09-16, per GHI [Build the design-to-main state machine: the Python machine, its per-state agent-instructions, and the nine items the design defers to the build](https://github.com/nedsnodes/nedsnodes/issues/282).
