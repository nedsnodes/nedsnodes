# The review lanes' mechanical review steps in one program: design

Status: a draft for the user's review. The user approved writing it, not building it: item 1 of approval-walk merge-lane-1-mechanical-review-steps-program-approval-walk-2026-11-26, answer "A" (walk-minutes `nedlern@ned-box:/home/nedlern/nedsnodes-logs/walk/merge-lane-1-mechanical-review-steps-program-approval-walk-2026-11-26-minutes.md`). Nobody builds it until he approves this design.

## The problem

A review lane, merge-lane-1 or merge-lane-3, follows its seat-brief by hand for each pull request: it lists its assignments, runs the review plan, writes the brief specifications, takes the commissioned time, starts the review run, grades, posts, writes the merge-queue line and sends messages. Only three of these steps need judgment. The others fail when an agent does them by hand:

- **PR 4925.** The merge gate refused the merge because the queue line's commissioned time, 03:42:24Z, was later than the approving review's submittedAt, 03:42:19Z. It was a no-reviewer-tier review, and the agent took the time after it posted (`nedlern@ned-box:/home/nedlern/nedsnodes-logs/seats/merge-lane-2/merge-queue-2026-11-21.txt`, lines 1616 and 1630).
- **PR 4917.** merge-lane-1 approved in review 6070885309 at 08:43:17Z, then posted a correction comment at 08:43:34Z. `scripts/merge-gate.sh` counts a comment newer than the approval as new activity, and merge-lane-2 had to post another review at 09:55:45Z before the merge (GitHub's review and comment lists for PR 4917).
- **Lane deals by hand.** The watcher deals by load, so a replacement pull request can go to a different lane than the one that reviewed the pull request it replaces. merge-lane-2 rerouted PRs 5123, 5124 and 5126 itself (`nedlern@ned-box:/home/nedlern/nedsnodes-logs/session-dialogs/ned-box/-home-nedlern-agents-merge-lane-2/d82bf417-d738-4c33-8635-a930c572db6f-dialog-complete.md`, line 184). merge-lane-3 keeps the replacement rule only in its own notes, along with "merge-lane-2's forwards sometimes say mod 3; check the log" (`nedlern@ned-box:/home/nedlern/nedsnodes-logs/session-dialogs/ned-box/-home-nedlern-agents-merge-lane-3/bc900014-2732-4d38-b154-e7d9a1d10b68-dialog-complete.md`, line 29). The two seat-briefs also disagree about pull requests opened by `ned-review-merge`: merge-lane-2's keeps them, and the watcher deals them.
- **Stale session refs.** Agents sent SendMessage to session refs that had already ended. This one comes from the dispatching brief: I found no record of it, so the design only reuses an existing function for it (see "Messages").

## What the program is

The program is `scripts/merge-lane-pr-review-mechanical-steps-run-until-judgment-needed.py --review-lane <merge-lane-1|merge-lane-3>`. Each call does every step that needs no judgment, then stops. The first line it prints is one output state from the table below. Under it come the files and text that the next step needs. The lane, or a fork of the lane, acts on that state and calls the program again. The program never decides what code alone cannot decide. The lane never does a step that the program does.

**What the program stores.** It stores only what GitHub, the watcher's assignment file and the merge queue file do not hold. That is one JSON file per pull request, `nedlern@ned-box:/home/nedlern/nedsnodes-logs/seats/<agent-seat name>/merge-lane-pr-review-mechanical-steps-per-round-state/pr<number>.json`. For each round it holds the head, the commissioned time, the review run's log path and exit status, the posted review id and the open holds. It reads everything else fresh on each call: the round, the tier, the earlier reviewed head and the reviews come from `scripts/pull-request-review-plan.py`, and the assignment from the watcher's listing. The per-round `review-commissioned-*.txt` files stop being written.

**One review run per lane.** The program keeps the lane's lock, `nedlern@ned-box:/home/nedlern/nedsnodes-logs/seats/<agent-seat name>/review-run.lock`, for as long as a review run lasts. A call that finds the lock held prints RUN-RUNNING and starts nothing.

## Output states and steps

| Output state (first line) | Who acts next | What the program did before printing it, and what it reuses | The lane's next step |
|---|---|---|---|
| `NONE-WAITING` | — | Ran `merge-lane-open-prs-watch-and-reviewer-assign.py --merge-lane-pr-review-assignments-list-for <lane>`. No pull request is WAITS-FOR-VERDICT, or each one that is has a refused or failed state on its current head. | Nothing. Call again when merge-lane-2 forwards an event. |
| `PLAN-REFUSED PR <n>` | judgment | Picked the pull request: high-priority label first, then oldest. Ran `pull-request-review-plan.py --pull-request <n>`, which exited nonzero, and printed what it said. | Act on what the plan said. The pull request is retried when its head changes, or when the lane calls with `--pull-request <n>`. |
| `WRITE-HAZARDS PR <n> <brief specifications file>` | judgment | Wrote the brief specifications entry with every field except `hazards`: tag, number and title from `gh`; author from the first commit's author name, as the watcher reads it; tests from the plan's changed test files; `claude_reviewer` from the tier. On a fix-round it also filled `reviewed_before` and `previous_reviews` from the plan, `new_commits` from `git log` of the plan's delta range, and `answer` from those commits' messages, quoted unchanged. | Write `hazards`, and add tests if needed, then call again. |
| `RUN-RUNNING PR <n> <log>` | wait | Took the lane's lock. Inside it, took the commissioned time with `date -u +%Y-%m-%dT%H:%M:%SZ` and recorded it. Then started `merge-lane-pull-request-worktrees-reviewer-brief-codex-review-and-head-tests-run-without-merge.py` in a session of its own, with `--review-tools-worktree-at-main /home/nedlern/.cache/merge-lane-review-worktrees/tools-<lane>`, and `--head-commit-reviewed-before` on a fix-round. In the same lock, it also ran the commands that the seat-brief ties to file kinds: each cold-read-fast-read command the plan prints, `scripts/md-drift-lint.py` on changed `.md` files, and the Bash guard verdict check when a Bash guard or a file one imports changes. | Wait for the run to exit, for example with Monitor on the log, then call again. |
| `RUN-FAILED PR <n> <log>` | judgment | The run exited nonzero. The program printed the log's last lines. | Answer `--answer <n> RERUN` when the log shows a passing fault, or `--answer <n> LEAVE-UNTIL-NEW-HEAD` after you report the failure to the code's owner. |
| `GRADE PR <n> <inputs directory> <review file to write>` | judgment | Collected the round's inputs into one directory: the plan, the Claude reviewer's review and note, the Codex report with its finding ids, the head test verdict, and the fast-read, lint and guard check outputs. On the no-reviewer tier it ran no review run and took the commissioned time just before printing this state. | Write the review file and call again. |
| `REVIEW-REFUSED PR <n>` | judgment | Passed the review file to `merge-lane-pull-request-reviewer-review-post-and-read-back.py --github-account ned-review-merge`, which refused it, and printed the refusal. | Fix the review file, then call again. |
| `ROUND-LIMIT PR <n>` | judgment | The verdict was REQUEST_CHANGES, but merge-lane-2's seat-brief allows no further round: round 3 with more than one must-fix-now finding, or round 4 with any. The program reads the round from the plan and counts the must-fix-now comments in the review file. | Grade again at the limit, then call again with a review file whose verdict is APPROVE or CLOSE. |
| `QUEUED PR <n>` + `SEND` block | lane sends | Posted the approval. Appended the queue line under `flock` and read it back: `<n> <head> <commissioned time> <author> (round <r>, review <id>, merge-lane-<x>[, stacked on <m>, merge after it])`, with a `HOLD-<words>` prefix while a hold is open. | Send the SEND block (see "Messages"). |
| `CHANGES-REQUESTED PR <n>` + `SEND` block | lane sends | Posted the review and recorded that the round waits for a new head. | Send the fix-round notice to the author. |
| `CLOSED PR <n>` + `SEND` block | lane sends | Posted the review with the remaining findings, then closed the pull request with `gh pr close`. | Send the author why. |
| `FAILED <what>` | lane reports | A step failed in a way that the program cannot classify. It exits 1 and prints what failed and what it changed. | Report it to the program's owner. |

**What the review file holds.** It has the shape the post program already takes, plus one key: `"holds"`, a list of `{"hold": "<a few words>", "waits_for": "user" | "author" | "fast-read"}`. The program removes `holds` before posting. When the review has comments, the program also appends the three closing sentences of merge-lane-2's seat-brief, word for word, so the lane does not type them. The post program already checks the verdict, every finding_category, and a grade for every Codex finding, so this program repeats none of those checks.

## How each case is handled

- **Fix-rounds.** A fix-round push makes the watcher's listing show the pull request as WAITS-FOR-VERDICT again. The program then sees the earlier round in its state file and the plan's earlier reviewed head, so the next call goes to WRITE-HAZARDS with the fix-round fields filled. A fix-round that merged main, or that rewrote history, is reviewed whole, as the plan and the review run already decide. The program decides none of this itself.
- **Changes requested.** The program posts the review, prints the author notice and keeps the round open until the head changes. The watcher listing, together with the state file, replaces the per-round task "Review PR <n> fix-round (round 2) when <author> reports it" (open question 3).
- **A head pushed during a round.** The review run reads the head once, from origin, and the post and the queue line name that head. The merge gate merges only the approved head. So a newer head is simply the next round, which the listing shows as WAITS-FOR-VERDICT. The program adds no check of its own for this.
- **Failed runs.** The program never retries by itself, because only the lane can tell a passing fault from a defect.
- **Holds.** Holds come from the lane's review file, never from the program's own guess. While a hold is open, the queue line carries `HOLD-`. When the hold clears, the lane runs `--hold-cleared <n> "<hold>"`. The program then appends the same line without `HOLD-`, or with the holds still open. The queue reader takes a pull request's last line as its state, so merge-lane-2 no longer edits the mark (open question 2). A hold that waits on the user goes into the lane's own approval-walk, which is judgment.
- **No posting after an approval.** On a head it has approved, the program refuses to post again. A correction goes to its reader by SendMessage, never as a comment on the pull request, because any comment newer than the approval makes the gate refuse (PR 4917). Taking the commissioned time inside the program, before the run or before GRADE, means it is always earlier than the approval (PR 4925).
- **Lane ownership and replacements.** The watcher's assignment file is the only place that says which lane a pull request belongs to. The program reviews only pull requests that the listing gives its lane. The replacement rule moves into the watcher, in a pull request of its own: a pull request whose `#replaces` chain, read by `scripts/pull-request-description-replaces-line-replaced-pull-request-chain-reader-common.py`, names one that is already assigned takes that one's lane. The program needs nothing for this. Because each pull request has exactly one lane, the first-job step "ask the other lanes which reviews they have running" is no longer needed (open question 4).

## Messages

A program cannot call SendMessage, so each SEND block names its recipient agent-seat, that agent-seat's current ListAgents ref and the message text. The recipient is merge-lane-2, or the author agent-seat taken from the first commit's author name. The program computes the ref when it prints the block, with `list_agents_tool_entry_ref_of_agent_seat_last_handoff_supervisor_launched_agent_session_find` in `scripts/agent-seat-idle-sweep-headless-judge-wake-messages-send-and-user-alerts-write.py`, and never reuses a ref from an earlier call. The lane sends the text unchanged. A queue message names every open hold, or says there is none.

## Steps that need judgment

1. Writing `hazards`, and adding tests the plan cannot find.
2. Grading each finding and choosing the verdict, including the regrade at the round limit and setting aside fast-read struggles.
3. Naming holds, and bringing to the user each hold that waits on him.
4. Acting on PLAN-REFUSED, RUN-FAILED and FAILED.

## Left out

The program leaves these to the lane, as the seat-briefs already say: agent-arbitrators for declined findings, a silent author, findings that outlive a pull request and their GHIs, sending fix-in-maintenance findings to their batch agent, merging, merge notices, and the after-merge follow-up list, which merge-lane-2 builds. It does not run the watcher, and it does not read a pull request's description for claims.

## Open questions for the user

1. **Pull requests opened by `ned-review-merge`.** merge-lane-2's seat-brief keeps them with merge-lane-2, but the watcher deals them to merge-lane-1 or merge-lane-3. Which rule holds? Recommendation: the watcher's, with merge-lane-2's seat-brief changed to match, so that the lane rules live in one place.
2. **Who clears a `HOLD-` mark.** May the lane append the unheld queue line itself, instead of asking merge-lane-2 to remove the mark? This changes both lanes' seat-briefs and merge-lane-2's.
3. **Per-pull-request tasks.** May the state files and the watcher listing replace the review lanes' per-pull-request and round-2 tasks? This changes the seat-briefs.
4. **The first-job ask.** Once the watcher is the only source of lane ownership, may the step "ask merge-lane-2 and merge-lane-3 which reviews they have running" be dropped from merge-lane-1's seat-brief?
5. **Build order.** The replacement rule goes into the watcher in its own pull request, before or alongside this program. Agree?
