---
issue: "[refresh-design: when a system's code lands, bring its design, build-slice plan and overview into line — removing, never revising](https://github.com/nedsnodes/nedsnodes/issues/670)"
kind: design
---

# refresh-design: bring a system's design and build-slice plan into line with the code on main

## What is wanted

Build **`refresh-design`**: the step that brings a system's two documents, its design and its build-slice plan, into line with the code merged to main since each was last checked. The name is the user's coinage (approval-walk of 2026-09-22, item 6). No program performs this step today. The user's rulings of 2026-10-30 and 2026-10-31 make the refresh a nightly maintenance-job that removes or fixes stale lines, as the section "What is decided: the refresh as a nightly maintenance-job" says. Where any other section of this GHI-MD differs from that section or from the section "What is decided: no architecture overview", those two sections decide.

## What is decided: no architecture overview

The refresh covers no architecture overview. The user ruled on 2026-11-23, to the agent-seat ned-box-helper: "I would just dump the overview machinery, and I would dump all the overviews. I think they're junk." On 2026-11-25 he approved taking every overview part out of this GHI, as item 18 of approval-walk cold-read-improvement-open-items-approval-walk-2026-11-22, whose walk-minutes are `nedlern@ned-box:/home/nedlern/nedsnodes-logs/walk/cold-read-improvement-open-items-approval-walk-2026-11-22-minutes.md`. GHI [Replace every architecture overview with a domain-guide for each system under `nn-systems/`, and remove the overviews and everything that writes, checks or refreshes them](https://github.com/nedsnodes/nedsnodes/issues/4653) removes the overviews, their how-to page, the handoff-supervisor's overview reminder and `path_is_architecture_overview_described_code` in `scripts/pull-request-review-plan.py`. Every earlier ruling below that has the refresh cover, create or check an overview is replaced by the ruling of 2026-11-23 and stays here only as the record of what was ruled.

## What is decided: the refresh as a nightly maintenance-job

The user ruled the five bullets below on 2026-10-30 and 2026-10-31, as items 9.2, 9.3, 9.3.1 and 9.4 of the agent-seat prime-intellect's approval-walk prime-intellect-handed-over-items-2026-10-29. Its walk-document and walk-minutes, which record each answer with his words, are `nedlern@ned-box:/home/nedlern/nedsnodes-logs/walk/prime-intellect-handed-over-items-2026-10-29.md` and `nedlern@ned-box:/home/nedlern/nedsnodes-logs/walk/prime-intellect-handed-over-items-2026-10-29-minutes.md`. He approved each item's recommendation, except item 9.4, whose answer the bullet "It is a maintenance-job" gives.

- **It covers designs, and fixes what the code cannot show (item 9.3.1, approved 2026-10-30).** Item 9.3.1 had it cover designs as well as overviews; its overviews are replaced by the ruling of 2026-11-23. A stale line that restates what the code shows, such as a list of files to read, is removed; a stale line about what the code cannot show, such as a reason or a decision, is fixed. This revises the rule of 2026-09-22 that a refresh removes and never revises. The user's words of 2026-10-30: "stale items should be either fixed or removed. It makes sense to remove design items which can simply be, here are the files you should read. [...] things that are not easily or not visibly not in the code or otherwise clear from reading the code have to be fixed."
- **What is due (item 9.3.1).** Each document gets a `**Checked against:**` line when it is checked. A program lists a document as due when its system's code changed after the commit that line names, or when it has no such line.
- **How often, and when (items 9.3.1 and 9.2).** One document every 2 hours, the oldest check first. While the 5-hour usage limit lasts, the refresh runs only overnight: from the end of ned-box's full test run of main, which starts at 00:00 Pacific (the job `scheduled-full-test-run-of-main` in `nn-systems/general-tools/scheduled-jobs-on-each-machine.json`), until 08:00 Pacific; once that limit no longer applies, around the clock.
- **It is a maintenance-job (item 9.4, answered on 2026-10-31).** The refresh becomes one of the maintenance-jobs of GHI [Regular maintenance: the list of maintenance jobs, how often each runs, and how each reaches the user](https://github.com/nedsnodes/nedsnodes/issues/1058), and its questions go to the approval-walk of that GHI's nightly overseer agent-session. The overseer runs in tmux on ned-box with Remote Control on, and an iTerm2 window on the Mac, attached to its tmux session, opens each night. The recommendation built no Mac window; the user disapproved that recommendation, so the window opens: "It'd be safer to make it show up in Tmux Mac, just in case there's some message I need to see that doesn't get echoed in remote control."
- **A question waits until the user answers it (item 9.3, approved 2026-10-30).** A question has no deadline and carries into the next night's continuation of the same approval-walk. This replaces the 04:30 end of the ruling of 2026-10-04 in the section "What is decided: corrections, unanswered questions and the cold read".

## What is decided: corrections, unanswered questions and the cold read

The user ruled the three bullets below in merge-lane-2's agent-session on ned-box, each answering a decision of the refresh agent's design, which planned an overview refresh alone and was deleted on 2026-11-25 by the ruling of 2026-11-23. Each holds for any document the refresh changes.

- **A correction reaches main without the user (2026-10-04 about 00:15Z, "y").** A refresh's changes are sorted by the rule of step 9 of `.claude/skills/cold-read/SKILL.md` into those that go to the user and those that do not; the refresh's own agent and a fresh-agent given only the diff each sort it, without seeing the other's list. When neither finds anything that goes to the user, the change merges without him; anything either picks goes to him.
- **An unanswered question holds the whole document (2026-10-04 about 16:30Z, "y").** Nothing of that document is published, corrections included, until he answers. The ruling's 04:30 end, after which the next night asked afresh, is replaced by item 9.3 of 2026-10-30, as the bullet "A question waits until the user answers it" says.
- **A refresh takes a cold-read-fast-read, not a cold-read-full-run (2026-10-05 about 04:25Z).** His words: "for daily maintenance a fast cold read is enough". He added a separate proposal, not part of this GHI: a monthly cold-read-full-run, staggered across the month, of each important Markdown file, wiki pages included, that has never had one or has changed since its last one.

No page defines a refresh of a design or a build-slice plan, so the five bullets of the section "What is decided: the refresh as a nightly maintenance-job" decide, and the sections after this one, which record the rulings those bullets rest on, stand only where the bullets are silent.

**The glossary gets its entry only when the step exists.** The user's words, 2026-09-23: "I would not add this to the glossary yet. I'd try to keep the glossary true now, not true eventually. Instead I'd make a GHI for it, assuming there isn't one." Until it is built, this GHI is where the definition lives. A search on 2026-09-23 found no issue for it: `scripts/ghi-guide-ask.py --include-closed` over open and closed issues, and `gh issue list --state all --search 'refresh-design OR "refresh design" OR overview OR BIPP OR "design lifecycle"'`.

## The draft definition, as put to the user on 2026-09-23

> **refresh-design** — brings a system's three documents into line with what landed on main since the last refresh; run at a landing, and when a reincarnated agent's opening prompt reports the system due. The **design** is streamlined: what the build superseded is removed. The **build-slice plan** marks the slices that landed. The **overview** — what neither the code nor the design says: how the parts fit, why the system is built this way, what was rejected — is re-checked against the code, and created if the system has none. A refresh removes and never revises; a change to a decision is a redesign, a full design-to-main run. Each refresh appends a pinned line carrying the landing commit to the design and the overview. Over an empty commit range it does nothing.

He redirected it here rather than approving it for the glossary; its wording is a draft, not a ruling. Its overview sentence, and its pinned line in the overview, are replaced by the ruling of 2026-11-23.

## The rulings it rests on — walk "what a design becomes when its code lands", 2026-09-22/23

The walk's minutes are shipped at its close to the log-store as `nedlern@ned-box:/home/nedlern/nedsnodes-logs/walk/what-a-design-becomes-when-its-code-lands-2026-09-22-minutes.md`. Items 4, 5 and 6 concern overviews only and are replaced by the ruling of 2026-11-23, as is the overview among item 2's three documents.

1. **A design is pinned to what landed (item 5, accepted).** It is not refined between design-to-main runs. It carries decisions, never build status: decisions do not go out of phase, descriptions of the build do. The evidence, on 2026-09-22: `nn-systems/main-gatekeeper/main-gatekeeper.system.design.md` carries a `status:` line and an Implementation status block and has been patched out of phase; `nn-systems/handoff/handoff.system.design.md` carries neither and has taken no substantive edit since moving.
2. **What a refresh is (item 6; the user: "Y but be careful").**
   - **It removes; it never revises.** Revised on 2026-10-30 by item 9.3.1, as the section "What is decided: the refresh as a nightly maintenance-job" says: a stale line the code cannot show is fixed. A change that revises a decision is a **redesign** — a full design-to-main run with its own reviews (`scripts/design-to-main/design-to-main-state-tables-common.py`, whose reject verdicts send the design, contract, implementation, tests or test-design back to its writer). Checkable, before that revision: a refresh commit's diff is deletions plus the pinned line. His caution, in his words: "We ran into endless problems with designs chasing code, code and test code chasing design changes … once the code lands on main (ie pasts all test) then we can refresh the design."
   - **It runs at landing** (his word: "y").
   - **It refreshes all three documents.** His words: "Designs do go stale, that's why we need refresh-design (which probably should refresh all 3 documents)." The three are the design, the build-slice plan and the overview; the overview is replaced by the ruling of 2026-11-23.
   - **The design does not move**, and each landing appends one pinned line carrying the **commit**, not only a date — so the next refresh's range is exact.
   - Prior art: `docs/nedsnodes-wiki/nedsnodes-fleet-git-worktree-working-model.md`'s closing note, streamlined 2026-08-20 after its mechanism prose was three times found stale against the code.
3. **Built / in-process / planned live in the build-slice plan (item 7, accepted).** The BIPP (built-in-process-planned) document kind is retired — his words: "Just one type of overview." `docs/issues/3-main-gatekeeper-build-slice-plan.md` is the one build-slice plan on main. **A cut slice is a decision, not a phase** — his words: "will not built is not a phase, its a removal of a part of the design" — so it leaves the plan and is recorded in the design with its date and reason. Slices are named and numbered when scheduled.
4. **An overview is created by the first refresh, at first landing, and updated by every one after (item 8, accepted).**
5. **Who keeps an overview true (items 9 and 14, accepted).**
   - **Trigger: reincarnation**, his proposal — "Maybe check if any designs need to be refreshed during reincarnation - would that work? That's our usual maintence period."
   - **The staleness check runs in the handoff supervisor**, `nn-systems/handoff/handoff-supervisor.py` (item 14, 2026-09-23; his words: "this goes into the handoff supervisor and ultimately into the (next) reincarnated agent"). It compares each system's last commit under `nn-systems/<system>/` with the commit pinned in that system's overview, and a stale system gets a "refresh due" line in the successor's opening prompt, beside the launch-time-git-sync line the supervisor already writes. Item 9 first placed it in `scripts/checkout-freshness-catch-up.py`, which is wrong: that is a Stop hook and runs at every turn boundary, so it would report every turn.
   - **A fresh subagent performs the refresh**, given one system and one commit range, `git log <pinned commit>..HEAD -- nn-systems/<system>/`, which lesson 2 below widens to the system's files outside that directory — his words: "this could be done by a subagent as this is a type of one off." The refresh scopes itself by commit subjects, never by diff size: `git diff --stat` sized the handoff overview's due refresh at 7,745 insertions when nearly all of it was a directory move.
   - **No owner.** His words: "why not just refresh - the refresh skill should be smart enough to do nothing if nothing needs to be done, and smart enough to do a little if a little needs to be done." Idempotence makes ownership moot: a second run finds an empty range and stops.
6. **What an overview is (his correction at item 14).** His words: "the overview should not be limited to - a page that says what the system is now. Thats not an overview. It needs to complement the 'what it is now' that is complement the prose and code." An overview complements the code and the design and does not restate them. The one overview on main is `docs/nedsnodes-wiki/nedsnodes-handoff-architecture-overview.md`; on 2026-09-22 it was due a refresh, verified 2026-09-16 against a system last changed 2026-09-22.

## Constraints on the build

- **Design-to-main is not built** (its design, `docs/design-to-main/design-to-main-state-machine.system.design.md`, reads `status: design, not built`), so no landing fires a refresh. The nightly maintenance-job does not wait for it.
- Item 9.3.1 of 2026-10-30 names the line a check adds `**Checked against:**`; its exact format, and whether it replaces the pinned line of the rulings above, are not yet fixed, and the program that lists due documents reads it, so the two are built together.

## What the first refresh by hand taught, 2026-09-23

The handoff overview was refreshed by hand before this step exists, in PR [Handoff overview: refreshed by hand against the code at 40afb38](https://github.com/nedsnodes/nedsnodes/pull/677). Five lessons for whoever builds the step, which hold for a design or a build-slice plan as they held for that overview:

1. **A document's last commit is not its verification commit.** The handoff overview's last commit was the 2026-09-20 directory move, and finding the commit it was actually checked against took `git log --follow` and a read of commit subjects. The pinned line must carry the commit.
2. **While a system is half-migrated, the range must cover its files outside `nn-systems/<system>/`.** Seven of the handoff system's parts still live in `scripts/`.
3. **A GitHub issue's status is itself stale.** GHI [recover-crashed-seats.py: the six changes ruled 2026-09-02 — exit record, process-identity liveness, parking marker, verified restart, by-hand resume, window](https://github.com/nedsnodes/nedsnodes/issues/242) says in its header that change 5 is not built and in its body that it is. A refresh reads the code and the merged pull requests, never an issue's claim about what is built.
4. **A text match is not behaviour.** A grep reported that `resupervise-seat.py` passes `--adopt-session-id`; the hit was in its docstring. A claim is checked against the code path.
5. **Most of what was new was "why" material** — how the parts fit and why — which a mechanical diff would miss. The refresh is judgment, done by an agent.

## Related, not parents

- GHI [Replace every architecture overview with a domain-guide for each system under `nn-systems/`, and remove the overviews and everything that writes, checks or refreshes them](https://github.com/nedsnodes/nedsnodes/issues/4653) — removes the overviews this GHI no longer refreshes.
- GHI [built-in-process-planned documents: design docs convert to a pointer map of built / in process / planned, with a skill that verifies and updates them](https://github.com/nedsnodes/nedsnodes/issues/219) — its 2026-08-29 update-at-landing ruling is this step's predecessor; item 7 retires the BIPP document it proposed.
- GHI [Queue drain procedure — the review process that empties the wiki queue, the pair queue, nn-queue, the drafts directory and the queue-drain-candidate-label issue queue](https://github.com/nedsnodes/nedsnodes/issues/24) — the precedent for a report at reincarnation: it planned a report of each queue's depth at each session-handoff.

## The daily reminder turned down; a refresh agent deferred, 2026-10-03

On 2026-10-03 at about 23:00Z the user turned down the handoff-supervisor's daily reminder that an overview was due: "no - this is a stupid design - we should build the refresh agent" (item 5 of the approval-walk whose minutes are `nedlern@ned-box:/home/nedlern/nedsnodes-logs/walk/handoff-system-overview-refresh-2026-10-03-minutes.md`). He deferred the refresh agent to later maintenance work, and took it up on 2026-10-30, as the section "What is decided: the refresh as a nightly maintenance-job" says. GHI 4653 removes the reminder.

## Next action

Build the refresh as a maintenance-job of GHI 1058, after that GHI's nightly overseer, which is built first: the program that lists the documents due by their `**Checked against:**` line, and the refresh itself, one document every 2 hours overnight, as the section "What is decided: the refresh as a nightly maintenance-job" says. Settle the draft definition and the line's format with the user first. Add the glossary entry in the pull request that makes the step exist.

Item 13b of the approval-walk git-checkouts-worktrees-and-branch-rules-design-draft-2026-10-09-2, which the user answered "Y" on 2026-10-11 (walk-minutes `nedlern@ned-box:/home/nedlern/nedsnodes-logs/walk/git-checkouts-worktrees-and-branch-rules-design-draft-2026-10-09-2-minutes.md`, line 26), added a task: "the overview-refresh reminder finds every architecture overview in the wiki and counts changes to every component each lists, the hooks and the scheduled-jobs file, as the how-to page says". The ruling of 2026-11-23 replaces it, and GHI 4653 removes the reminder.

## Deferred-decisions

- Which designs the refresh covers, and which files count as the code of a design or a build-slice plan.
- What the refresh does for a system with no design or no build-slice plan.
- Where in a design or a build-slice plan the `**Checked against:**` line goes, settled with the line's format.
- How a refresh marks a build-slice that has merged, since a slice's status is not a stale line to remove.
- The order among documents that have no `**Checked against:**` line, or whose lines name the same commit, under the rule "the oldest check first".
- Whether a document is picked again while its refresh's pull request or its question waits, whether a refresh of another document goes ahead while a question waits, and whether the questions carried from night to night have a limit.
- How the 2-hour slots are counted from the end of the test run, and what happens to a refresh still running after 2 hours, still running at 08:00, or hung, and what happens when ned-box's full test run of main fails or does not end.
- What event ends the 5-hour usage limit's overnight-only period.
- Where fixing a stale line about a decision ends and a redesign begins.
- How a refresh's pull request merges when neither sorter finds anything that goes to the user, what a refresh does with a cold-read-fast-read finding it cannot resolve, and what happens to its change when the user rules against it.
