---
issue: "[Make approval-walks wrap up faster: read the next item ahead, reread after a fix only when the fix touches facts, and stop the /Volumes false alarm in cold reads](https://github.com/nedsnodes/nedsnodes/issues/2464)"
---

# Make approval-walks wrap up faster: read the next item ahead, reread after a fix only when the fix touches facts, and stop the /Volumes false alarm in cold reads

In an approval-walk, after the user answers one item, the agent runs checks before it shows the next item, chiefly a cold-read-fast-read (`nn-systems/cold-read/cold-read-fast-read.py`) of the next item and of each revision of it. The user waits through those checks. This GHI holds three changes, built as code, that cut the wait without dropping the first read of an item. Owner: the agent-seat cold-read-improvement, which owns the fast read.

## The measurement

On 2026-11-01 a subagent of merge-lane-2 measured 284 waits between the user's answer and the next item, across 9 agent-seats, 2026-10-18 to 2026-11-01. Its data and scripts are in `nedlern@ned-box:/home/nedlern/nedsnodes-logs/seats/merge-lane-2/walk-wrap-up-check-measurement-2026-11-01/`; the hand classification of 33 reads is `classification.tsv` there, and the full cold read runs are `fullruns.txt`. The figures, as item 7.1.1 of the approval-walk merge-lane-2-open-rulings-2026-10-30 gave them to the user:

- The median wait is 3.4 minutes. With no fast read it is 0.7 minutes; with one it is 5.2 minutes, and the read itself takes a median of 196 seconds. Fast reads are at least 37% of all the waiting.
- The walk-me-through skill already asks for one fast read of the whole walk before item 1. Then it asks for a fast read of each item that is revised, and again after each fix that is more than an obvious-error-fix. Items are almost never read again unchanged: of 444 pairs of reads of the same item, only 4 were of identical text. The repeats are that read, fix, read loop, most within 5 minutes.
- A read's time is mostly a fixed start-up cost: about 2 minutes on Gemini, the main reader, plus about 20 seconds per 1,000 words. Sonnet takes about a third as long. One read of a whole 16-item walk takes about 4 minutes, against about 30 for 16 item reads, but it returns about 8 findings in all, against about 7 for each item read on its own, about 110 for the 16.
- First reads find real defects: 6 of 21 sampled reads before showing an item caught one, such as "a test already checks that they match" when no such test exists. The rereads in the sample found only wording.
- The full cold read at the end of a design or skill takes a median of 28 minutes. In 5 of 8 sampled runs it found real defects the fast reads had missed, such as two false statements about what the worktree cleaner does today.
- The /Volumes false alarm comes up in 313 of 320 reads whose text has a Mac link. The reader runs on ned-box and never sees the rule that `file:///Volumes/nedhome/` is ned-box's home seen from the Mac.

## Decided

The user approved item 7.1.1 of merge-lane-2's approval-walk merge-lane-2-open-rulings-2026-10-30 on 2026-11-02 at 09:56 Pacific time (17:56Z), in his words "A approved is with the Gemini fast read." Walk-document: `/home/nedlern/agents/merge-lane-2/docs/walk/merge-lane-2-open-rulings-2026-10-30.md` on ned-box, section "Item 7.1.1 of 25"; walk-minutes: `/home/nedlern/agents/merge-lane-2/docs/walk/merge-lane-2-open-rulings-2026-10-30-minutes.md`, the line "item 7.1.1 of 25: the user answered approved #case_against_weak (2026-11-02 09:56)". The item's recommendation was: "file the GHI for the three changes and hand it to cold-read-improvement."

The case against that the user saw, graded weak: change 2 lets a wording fix that adds a new mistake reach the user unread, and only 33 reads were classified by hand, 21 before showing an item and 12 in the check step. The alternative he did not take: change nothing until a larger sample is classified.

The approval keeps the Gemini fast read as the reader. The full cold read at the end of a design or skill stays as it is, apart from change 3.

## The three changes

1. **Read the next item ahead.** The walk check program, `nn-systems/skills/walk-me-through/walk-me-through-answer-added-texts-cold-read-fast-read-check-and-close.py`, gets a step that starts the fast read of item N+1 in the background as item N is shown, keyed to a hash of item N+1's text. When the user answers item N, the agent uses that read if item N+1's text is unchanged, and waits for it if it is still running; if item N+1's text changed meanwhile, the program reads it again.
2. **Reread after a fix only when the fix touches facts.** After a fast read's fixes, the walk check program compares the item before and after, and starts another read only when the change touches a number, a path, a file or program name, a link, or the item's line that begins "Recommendation:", "The alternative:" or a `#case_against` tag such as `#case_against_weak`. Today `.claude/skills/walk-me-through/SKILL.md` leaves that call to the agent: "give it another fast read if a fix was more than an obvious-error-fix". The pull request for this change also changes that sentence of the skill, and the new wording goes to the user for approval before it merges, as every standing instruction does.
3. **Stop the /Volumes false alarm.** `nn-systems/cold-read/cold-read-fast-read.py` rewrites `file:///Volumes/nedhome/` to `/home/nedlern/` in the copy of the text it hands the reader, and the full cold read, `nn-systems/cold-read/cold-read-grid.py`, does the same.

## Next action

cold-read-improvement designs and builds the three changes, each with a test that fails without it. Changes 1 and 2 may land in one pull request and change 3 in another, since change 3 runs the cold-read test suites and not the walk's.

The design settles these points, which the GHI-MD's own fast read raised:

- What starts the read ahead. The walk check program's `close` step, which already sets the walk-minutes' `#next_to_present` line, can start item N+1's read itself, so the saving does not depend on the agent remembering to start it.
- Which side compares the hash and waits. The program can do both and hand the agent findings only for item N+1's text as it stands, leaving the agent only to apply them.
- The last item of a walk, which has no item N+1, and item 1, which the read of the whole walk covers.
- A background read that fails or never ends: the agent must not show item N+1 unread because of it.
- Where the program keeps the item's text from before the fixes, to compare against.
- How code tells that a change touches a program name. One rule the fast read proposed: a changed word counts when it is in backquotes, ends in a file extension, or is a path or file name that `git ls-files` lists; any changed digit counts as a number.
- Whether change 3 also rewrites `/Volumes/nedhome/` written without `file://`, and whether a finding that quotes a rewritten path is shown with the path as the item has it. One function that both programs import keeps the two rewrites the same.

## The next item at once after N, A, AO or D

On 2026-11-26 the user asked, in an approval-walk of the agent-seat pr-review-maintenance-findings-batch-fix-agent: "When I type n can we just send the next part using code? Why the delay". He then asked: "If we can go to the next item with mostly code after an N, could we also go to the next item with a pure A? Isn't that what we're assuming is going to happen? So the walk would be correctly structured. I guess we could, in other words, it would immediately, the next item would immediately appear, but if the A takes time to process, that would happen in the background. Do I misunderstand something? N obviously is just doesn't actually do anything besides show the next item, so that might be a simpler case." He approved, as obvious ("ao"), item 5 of that walk, timeshift-search-timeout-and-maintenance-agent-seat-names-approval-walk-2026-11-25, whose recommendation was: "file a GHI asking the walk check program to check the next item and publish its page while the current item waits, so that N, A, AO and D each show the next item at once, with the work an answer approves running in the background." Walk-document: `/home/nedlern/agents/pr-review-maintenance-findings-batch-fix-agent/docs/walk/timeshift-search-timeout-and-maintenance-agent-seat-names-approval-walk-2026-11-25.md` on ned-box, section "Item 5 of 6"; walk-minutes: the `-minutes.md` file beside it.

The case that prompted it: after his N on item 3, item 4 took several minutes to appear. The walk check program named item 2 next and gave it a fresh read, since its heading's count had changed; the agent then bumped item 4, a question added to the walk earlier, ahead of item 2 with `check --bump`. No read ahead covered item 4, so its first cold-read-fast-read ran only then, each fix to it set off another read, three reads of it in all, and its item page was then built and published.

Changes 1 and 2 above are in the walk check program on main: its docstring's section "READ AHEAD" and its `--after-fixes-reread-only-when-facts-change` flag (checked with grep on main, 2026-11-26). What this ruling adds, to the three changes above; N needs only changes 4 and 5, since it approves nothing:

4. **Read ahead an item as soon as it is added or bumped.** An item added to the walk while another is shown, or moved up by `check --bump`, gets its read started at once, so it is ready when its turn comes.
5. **Build and publish the next item's page ahead.** The next item's page is built and published while the current item waits, so that showing it needs no page step.
6. **Show the next item at once after A, AO or D.** The answer is recorded at once and the next item is shown; the fast read of the texts the answer adds and the work the answer approves both start at once, in the background. A finding that would change what the user approved comes back to him as a new item, as it does today. This changes two rules of `.claude/skills/walk-me-through/SKILL.md`: "an answer that makes a change takes effect only after check has given every text the change adds a fast read" and "An answer that makes a change advances the approval-walk only once the check step has finished." The new wording goes to the user for approval before it merges, as every standing instruction does.

cold-read-improvement, this GHI's owner, designs and builds changes 4 to 6 too. The design settles these points, which this section's fast read raised:

- What starts the read of an item the agent writes into the walk-document without `check --bump`, such as a finding that comes back as a new item. One way: every `check`, `close` and waiting-item step starts a read for each waiting item that has none.
- Who publishes the page ahead. Publishing needs the Artifact tool, which only the agent has, so the program can build the page and print the publish as the agent's next step in the turn that shows the current item.
- A read ahead or page that is still running, has failed, or is stale because the item changed, when the user answers.
- How the program records the background read of an answer's texts and brings its findings back, so that nothing depends on the agent remembering; who applies the findings that do not change what he approved; and what happens when a finding lands after he has answered later items that build on the approved text.
- How Aa, which waits for the advisor, Z, O2 and O3 behave under change 6.


## Not in this GHI

The user's further ideas, given with his approval, are not decided and are not part of this work: a ready pool of warm readers, trying other reader models, and having readers name the instruction behind each finding. A separate research GHI, which links to this one, holds them.
