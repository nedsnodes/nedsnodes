---
status: ruled — produced at the close of the git/worktree rules approval-walk
  (2026-08-17/18); every rule disposition below was user-ruled item by
  item.
  Streamlined 2026-08-20 on the user's ruling: mechanism prose removed in
  favor of script citations; the full original text is this file's git
  history.
scope: fleet-wide — both machines, every agent-seat, and the two agent runtimes,
  Claude Code and Codex
---

# Fleet git and worktree working model

The ruled working model for how this project's agent fleet uses git: which
directory a session works in, whose directories it may touch, how work
reaches main, how landed changes reach running agent-seats, and what makes most
damage recoverable when noticed in time. The dispositions and dates below
are the user's rulings. Where a ruling shipped code, the pull request is
named; where it deliberately built nothing, the reason and the revisit
trigger are stated — an unbuilt rule here is a decision, not an omission.

What this document deliberately does not do: describe how the named
scripts work. A sentence here must stay true when a script is rewritten
tomorrow; how a script satisfies its rule today is readable at the cited
path. This boundary is itself a ruling (2026-08-20), made after three
mechanism descriptions in this document went stale within hours of
passing review.

## Scope

Rules about git, worktrees, agent-sessions, agent-seats, and machines, plus the
enforcement programs that implement them. Deliberately excluded: workflow
governance content (the cold read's cells, ghi-write's routing, approval-walk conduct),
prose-quality rules, and communication conventions. Coverage is bounded by
the sweep that built the inventory — the agent-seats' briefs
(`docs/agents/*-instructions.md`), `nn-systems/handoff/handoff.system.design.md`,
and agent-seat `CLAUDE.local.md` files were not swept.

Reach, so nothing below is assumed to protect more than it does: every
enforcement program in this document is a Claude Code feature, registered
in Claude Code's settings and running only inside Claude Code sessions. A
Codex invocation gets none of that machinery; it is bound only by what it
reads and by GitHub's branch protection, which binds everyone. No work is
planned to extend the guards to Codex. R26 alone is designed for both
runtimes from the start.

## The enforcement ladder

The rungs that the Index's Rung column names (impossible, default, block, detect and reverse, remind, text) are defined, with an example of each, on [the enforcement ladder](nedsnodes-enforcement-ladder.md).

## Standing rulings and principles

These govern every row below.

- **The reference checkout** is the reference-checkout the glossary defines. A standalone clone is its own workspace, never the reference checkout; where a guard's mechanical test disagrees with that, the definition governs.
- **The PR process**: each pull request merges one atomic nn-topic-branch, reviewed and merged as `CLAUDE.md`'s pull-request paragraph says; deputization, at R13, is the ruled exception.
- **The override markers** — `.walk-approved` (instruction-file guard) and `.location-write-approved` (session-location guard), both gitignored, each holding the user's quoted approval words, consumed by the one guarded call it approves (see Marker honesty); `.walk-approved` holds instead `#pre_approved_change` and the reason for a change that `docs/nedsnodes-wiki/nedsnodes-which-changes-need-the-users-approval.md` does not require his approval for.
- **Prose yields to code** (user-ruled 2026-08-19): anything that can move
  from CLAUDE.md — or any instruction prose — into a small program should
  move, and never the other way. A check in code runs; a check in prose
  waits to be remembered.
- **A blocking guard carries an escape** (user-ruled 2026-08-17): a false
  fire must be *self-detecting* — the refusal names the file, the reason,
  and the fix — and *self-repairable*: either the consumed-marker lane
  passes one approved write, or the refusal itself teaches a repair that
  releases the block. A future block that cannot meet this bar is built
  as detect-and-report instead. The backup guard (R11) is the one ruled
  exception: its no-lane form is deliberate, and reading stays free so
  recovery is never blocked by it.
- **Gray-zone deciders**, per guard: the *program* decides mechanically
  (the gatekeeper); the *user* decides with the agent recording (the
  marker lane); or *no one* — the write is not the agent's to make
  (the backup guard). Fourth value, *nobody-now*: defer, valid only where
  a named later gate covers the case; no rule currently uses it.
- **Marker honesty**: a marker mechanism cannot verify whose words the
  marker holds or when approval was given — any non-empty marker passes.
  A guard's claimed strictness above that is carried only by its refusal
  text; the audit value is the visible quote in the marker and transcript.
  A marker lives at the root of the checkout it resolves from, is consumed
  at the guard's hook call, and persists unconsumed until a guarded call
  consumes it.
- **Silent safety is the enemy**: a conservative default must be
  distinguishable from a clean result, and a protection must be verifiable
  as actually in force.
- **Detection is the scarce half of undo**: git plus the snapshot stores
  can reverse most damage if noticed in time. Two carve-outs: content
  never committed that lived shorter than the host's snapshot interval is
  protected by neither store; and reversal restores artifacts, never
  consequences already drawn from them.
- **Rules are delivered at their trigger moment, not held in memory**
  (R28, re-ruled 2026-08-17): refusal text teaches at denial; boot reports
  teach when someone looks; the agent-seat first-prompt teaches at birth.
  CLAUDE.md's rules section shrinking is the health signal — rules leave
  when mechanized; rationale lives in design documents like this one.

## The rules

Status vocabulary: **BUILT** marks code the approval-walk shipped, with its pull
request named. **built-live** marks a mechanism already running before the
approval-walk began.

### Q1 — Which directory am I in?

**R1. Enforcement programs resolve their roots correctly — resolvers FIXED
(PR [guards: markers resolve from the session's own checkout, and the backup override lane is removed](https://github.com/nedsnodes/nedsnodes/pull/86), merged 2026-08-17); registration residue closed won't-fix
(user-ruled 2026-08-22).** Two questions
hide under "the root": which repository owns the target file, and which
checkout the session is in — the latter from the session's own working
directory, never from `$CLAUDE_PROJECT_DIR`, which names the wrong
checkout in forked sessions. User revision made at approval: override
markers resolve from the *session's own* checkout, not the target's;
target-derived resolution is only the fallback when the session sits in
no checkout. The residue, closed won't-fix: the hook and status-line *registration*
lines in `.claude/settings.json` resolve through `$CLAUDE_PROJECT_DIR`
and stay that way — benign while all checkouts carry identical copies.
A re-registration was attempted and deliberately reverted (PR [guard and catch-up review fixes: item 1 of the working model's build queue](https://github.com/nedsnodes/nedsnodes/pull/103),
2026-08-19) after three shell forms in one day, two wrong; the PR
records all three forms and their evidence. The closing ruling: a
registration line carries no more machinery, because the forked-session
wrong-copy failure this would guard against has never been observed —
per CLAUDE.md's rule on guards, hardening needs a named behavior.
Reopen trigger: that failure actually observed — a guard demonstrably
running as another checkout's copy, with effect.

**R2. A session states and verifies its git context at start — satisfied
by composition (ruled 2026-08-17), nothing built.** The four facts of
issue [Successor startup must state its git context — app-spawned agents land in a worktree, not the checkout](https://github.com/nedsnodes/nedsnodes/issues/34) each have a delivery at least as good as a session-start print:
directory and branch on the status line (R5); the write blocks covering
the demonstrated wrong-place classes (R3, R6); the PR process in
CLAUDE.md's ruled paragraph, the gatekeeper at activation, and branch
protection at push time. A session-start hook rides the same committed
repository as CLAUDE.md, so the print adds zero reach.

**R3. Detached HEAD or sitting in the reference checkout refuses writes —
BUILT (PR [session-location write guard: no file writes from a detached HEAD or the reference checkout](https://github.com/nedsnodes/nedsnodes/pull/88), merged 2026-08-17).**
`.claude/guard-hooks/session-location-write-guard.py`, PreToolUse block on
Edit/Write/NotebookEdit; exception lane via `.location-write-approved`.
Scope, corrected 2026-08-19: the detached-HEAD test governs writes into
the session's *own* checkout; a write landing in the reference checkout is
R6+R7's block, which applies to any session however its HEAD is set.
Writes into another agent-seat's agent-home stay unbuilt (R6). The adjacent
*starting-stale* block was ruled **not built**: launch-time-git-sync plus the
catch-up hook (R15) shrink exposure to one turn, and the motivating
incident was a stale *read*, which no write-guard sees. Revisit trigger: a real incident traced to
the one-turn window.

**R4. Stale base — absorbed (ruled 2026-08-17).** The original rule
(block first write on a stale base; warn when main moves mid-task; harden
at push) is superseded by R15's catch-up hook plus the Claude Code
runtime's own refusal to edit files changed since last read. Residues
assigned: starting-stale rides R3's ruling; push-time hardening rides the
gatekeeper permanently.

**R5. Status line shows the branch — ruled kept (2026-08-17, PR [status line: the │ separators become two plain spaces](https://github.com/nedsnodes/nedsnodes/pull/89)).**
`scripts/session-statusline-command.py`. Kept because shell git commands
pass no file-write guard — the line is that mistake's only always-on
visibility.

### Q2 — Whose directory is this?

**R6 + R7. No agent writes into the reference checkout — BUILT as a block
(PR [session-location guard: writes landing in the reference checkout are refused from any seat](https://github.com/nedsnodes/nedsnodes/pull/91), merged 2026-08-17).** The session-location guard's second
condition: a write *landing* in the reference checkout from a session
seated elsewhere is refused, same marker lane. Scoped to the demonstrated
class — all four recorded cross-checkout incidents targeted the reference.
The four, so the evidence outlives the approval-walk papers: on 2026-08-14 a
session seated in its own worktree edited twelve documents and staged 235
deletions in the reference checkout; cold-read records were later written
into it; a git branch was created in it, twice; and on 2026-08-15 an approval-walk's
minutes were written into it. Zero incidents targeted another agent-seat's
home or a scratch worktree. Writes into
*another agent-seat's* agent-home are recorded-unbuilt with an incident as the build
trigger; a session's own scratch worktrees are deliberately untouched.
Block outranked detect-and-reverse because the undo is imperfect exactly
where damage is worst: a cross-checkout write over uncommitted work is
unrecoverable by git. R7 (the reference is a reference, never a bench)
rides this mechanism; the merge-lane agent-seat's legitimate conflict edits pass
through the marker lane.

**R8. One live session per directory — waits on detection; build
nothing.** No detector yet meets the bar: it must classify attached
viewers, forked sessions, and background sessions correctly from each
session's own state.

**R9. One name = one agent-seat; a handoff refuses a foreign claim — built-live
(PR [handoff: the agent name defaults to the seat's directory, and a foreign claim is refused](https://github.com/nedsnodes/nedsnodes/pull/72), merged 2026-08-17).**
`nn-systems/handoff/handoff-write-and-check-supervisor.py`: handoffs stamp
`written-in:`; a writer whose directory differs is refused; `--claim`
overrides deliberately, the typed flag in the transcript being the audit
trail. The accident it kills: two same-name sessions overwrote a handoff
eleven seconds apart, first lost unread. Residuals: handoffs written before PR
[handoff: the agent name defaults to the seat's directory, and a foreign claim is refused](https://github.com/nedsnodes/nedsnodes/pull/72)
carry no stamp; directory basenames are not globally unique across machines
(machine-suffixed names deferred — rider 5 in
`nedlern@ned-box:/home/nedlern/nedsnodes-logs/seats/cold-read-research/45-session-seat-and-isolation-riders-retired-from-issues-queue-2026-10-02.md`). An agent-seat's
*first* handoff is written by its provisioner from elsewhere, the guard
correctly refuses, and `--claim` is the sanctioned path.

**R10. Whether a change to an agent-instructions file needs the user's approval is set by the [approval page](nedsnodes-which-changes-need-the-users-approval.md) —
built-live (root-resolution fixed by PR [guards: markers resolve from the session's own checkout, and the backup override lane is removed](https://github.com/nedsnodes/nedsnodes/pull/86)).**
`.claude/guard-hooks/instruction-file-guard.py`: CLAUDE.md, per-seat
`CLAUDE.local.md`, `.claude/` (minus `worktrees/`, `jobs/` and `handoffs/`),
reusable prompts, and the files the user reviews block on write; approval quoted into `.walk-approved`, or, for a change `docs/nedsnodes-wiki/nedsnodes-which-changes-need-the-users-approval.md` does not require his approval for, `#pre_approved_change` and the reason. **The shell-write gap is
named and ruled unguarded** (2026-08-17): every recorded bypass was
accidental, not adversarial. Build trigger: an actually observed
shell-route bypass. A periodic drift sweep was rejected: it
false-positives on agent-seats legitimately carrying approved-but-unmerged
changes. Codex's instruction file — `AGENTS.md` at the repository root,
added 2026-08-20 — is not in this guard's list: a known fact, not a
decision, and consistent with CLAUDE.md's rule on guards, which landed alongside it
(no recorded incident, no guard).

**R11. Backup stores are read-only to agents — built-live; lane removed
(user-ruled 2026-08-17).**
`.claude/guard-hooks/backup-and-snapshot-write-guard.py`: the Timeshift store
and configuration and Time Machine state refuse agent tool-writes
*unconditionally* — no marker lane; a real configuration need routes to
the user's keyboard. Rationale: an undo store agents can write is not
one. Reading stays free, so snapshot recovery is untouched. Precedent
(2026-08-18): the user may direct an agent's hands, in that agent's own
session, to paths outside the guarded class; the guarded paths stay
agent-unwritable.

### Q3 — How does work reach main?

**R12. Agents never push to main; only the main-gatekeeper does — partial,
hardened 2026-08-20.** Branch protection is live: pushes to main restricted
to two accounts — the user's own (`nedlern`, which authors) and
`ned-review-merge` (merge-lane's identity, which reviews and merges,
added 2026-08-19 so approval comes from a non-author); enforce-admins on;
force-push and deletion blocked; and, since 2026-08-20, **one approving
review is required for every merge** — enabled with the user present and
drilled live on PR [catch-up hook: a git that never ran reports GIT_DID_NOT_RUN, not 1](https://github.com/nedsnodes/nedsnodes/pull/104). This is rung 1 at the account tier only: any
process holding either credential can push, so "agents never push" is
instructed, not impossible, until the main-gatekeeper's credential design,
ruling C2 of `nn-systems/main-gatekeeper/main-gatekeeper.system.design.md`,
lands. The restriction was proven live 2026-08-18 by a user-authorized
fence test (a non-allow-listed push refused with GH006 while an
unprotected control accepted the same credential and commit); the same
test established that a refused push leaves NO trace in the activity log
— a quiet log means nothing got through, never that nobody tried. The
gate's own program path was proven end to end 2026-08-18 (commit b24e376;
record at
`nn-systems/main-gatekeeper/main-gatekeeper-first-live-check-in-record.md`) while
the gate stays dormant for daily work.

**R13. The PR process — built-live (process); retired when the gate
activates.** Lives in CLAUDE.md's PR-process paragraph and
`docs/agents/seat-first-prompt.md` § Reaching main. **Deputization** is
the PR process's recorded exception (ruled 2026-08-18, PR [CLAUDE.md lane text: deputization recorded as the interim lane's exception](https://github.com/nedsnodes/nedsnodes/pull/93)): the user may
instruct a specific agent-seat, in that agent-seat's own session, to merge a specific
PR; relayed words are hearsay and are refused — exercised before it was
recorded (a relayed instruction refused 2026-08-16; the user then deputized
directly for PR [handoff: the agent name defaults to the seat's directory, and a foreign claim is refused](https://github.com/nedsnodes/nedsnodes/pull/72)'s merge).

**R14. One branch, one writer — satisfied by defaults (ruled 2026-08-17);
the old push-time check is retired.** An own-branch-only push check would
refuse the ruled atomic-PR lane. The residual hazard (two writers, one
branch) is covered by defaults with git's non-fast-forward refusal as
backstop; these are defaults, not guarantees — branch protection covers
main only. Push discipline as a whole becomes the gatekeeper's at
activation: a push is a shell operation no file-write hook sees.

### Q4 — How does a change reach a running agent-seat, and what keeps agent-seats alive?

**R15. A landed change reaches every running agent-seat — BUILT (PR [checkout freshness: mid-session catch-up Stop hook, status-line display, reference-checkout pull](https://github.com/nedsnodes/nedsnodes/pull/87), merged
2026-08-17; delivery ruling PR [catch-up: the abort-failed state alone is delivered to the agent as a forced turn](https://github.com/nedsnodes/nedsnodes/pull/90)).**
`scripts/checkout-freshness-catch-up.py` is the delivery; the status
line's `⇣N` shows the lag; the launchers freshen the reference checkout
at boot; the supervisor's launch-time-git-sync remains the floor. Coverage
stated exactly: delivery happens at turn boundaries when the agent-seat is
clean and conflict-free — an
agent-seat that lags says so on its status line rather than silently. **Who
hears it** (ruled 2026-08-17): exactly one state forces an agent turn — a
conflict whose cleanup failed, leaving the tree mid-merge; routine events
stay display-plus-stamp. **Known structural finding:** the atomic-PR lane reliably produces add/add conflicts on files
a cherry-picked topic *created*. Manual remedy: `git status` to list,
`git checkout --theirs <file>` to take main's canonical version, `git
add`, commit. The candidate launch-reset of fully-merged seat-branches
no longer applies: an agent-home rests on a detached HEAD at `origin/main`
and has no seat-branch to reset.

**R16. Binary updates at launch, never in background — built-live
(accreted, no single PR).** Both launchers update the binary at launch,
warn-and-proceed on failure; their guarantee is that *they* never swap it
under a live session. **Since 2026-09-22 the handoff-supervisor updates too**,
before every session it launches — which covers the handoff restart, crash
recovery and the login restart, the three paths that reach an agent-seat without
passing a launcher. It was added because an agent-seat restarted by handoff passed
no update moment at all, so a long-lived agent-seat drifted: both machines sat on
2.1.278 with 2.1.280 published when the user asked why (user-ruled
2026-09-22). The box's `DISABLE_AUTOUPDATER=1` flag was
removed 2026-08-17 (dated backup beside it) when issue [Claude auto-update purges the running version under live fleet sessions — updates need a drain-or-retain policy](https://github.com/nedsnodes/nedsnodes/issues/62)'s auto-update
theory was retracted — which left background auto-update ON fleet-wide.
The same flag returned 2026-08-22 for a different, still-valid reason:
with launch as the update moment, the background updater adds nothing
but its mid-session "update available" banner, which the user ruled
clutter. It now lives in the checked-in `.claude/settings.json` env
block, reaching every agent-seat's worktree on both machines; the docs state
it stops only the background check, leaving the launchers' explicit
`claude update` working. The launch-time version check that was queued
here closed 2026-08-22 without building a version check.

**R17. Shared machinery lives in the repository, self-updating at safe
points — principle; two open gaps (recorded 2026-08-19).** The principle:
every deployed copy keeps itself current from its source at safe points
(launch, reincarnation, invocation), never by swapping under a live consumer.
The two gaps, each owned by named code: `launch-claude-mac` runs the
supervisor from whatever checkout it is invoked in, which need not be the
checkout that was freshened — whether the launcher *should* always
operate on the reference checkout is an open design question routed to
issue [Run named agents on the Ubuntu box, reachable from iTerm2 by name: launch-claude with tmux attach-or-create, and the migration it requires](https://github.com/nedsnodes/nedsnodes/issues/45) (design pair:
`docs/issues/45-remote-named-agent-launch-and-reattach.md`); and a freshening that fails is reported nowhere, on either
launcher — the failure is recorded in a stamp file and nothing reads it
(owned by `checkout-freshness-catch-up.py --reference-pull`, not by the
launchers that call it). How each launcher wires freshening to launch is
the launchers' own business; read the scripts `scripts/launch-claude-ubuntu`
and `scripts/launch-claude-mac`, not this paragraph.

**R18. Agent-seat hosts are provisioned to survive disconnects — checklist
ruled (2026-08-17).** Per host: (1) on systemd hosts, `loginctl
enable-linger <agent-user>`, verified by an actual multi-minute gap, not
by reading the flag (the Mac has no linger equivalent; its agent-seats ride the
desktop session); (2) a restore-one-file snapshot verification (done for
the box 2026-08-17; not yet for the Mac); (3) the host's snapshot cadence
per R19; (4) `lsof` present, for R21's vacancy check. Linger covers
logout-triggered kills; reboots and power loss fall to git and snapshots.
Completed and gap-verified for the box; the Mac has not been walked
through this list.

**R19. Snapshot cadence — ruled and LIVE (2026-08-17/18).** The box:
10-minute Timeshift snapshots via `/etc/cron.d/timeshift-10min`
(installed 2026-08-18, first tick verified), joining the auto-pruned
hourly ring — a ruled trade of ring depth for cadence, raisable at the
user's keyboard. Undo: delete the cron file. Applied by the git-infra
agent-seat on the user's direct in-session instruction — `/etc/cron.d` is
outside R11's guarded class. The Mac stays at OS-default hourly: no
recorded Mac-side loss. What it buys, honestly: minutes-cadence never
reaches the seconds class (R9's guard closed that class).

**R20. The handoff channel preserves structure end to end — BUILT
(PR [handoff: a multi-line next step survives the channel end to end (R20)](https://github.com/nedsnodes/nedsnodes/pull/108), merged 2026-08-20; fix ruled 2026-08-18).** Both ends: the
writer (`nn-systems/handoff/handoff-write-and-check-supervisor.py`) emits a
delimited multi-line block and the reader
(`nn-systems/handoff/handoff-supervisor.py`) parses it — a reader-only fix could not
have restored newlines already destroyed. The format specification, and
the exact-terminator trade it records, live in
`nn-systems/handoff/handoff.system.design.md`, given a cold read before the build
per design-first.

### Q5 — What piles up, and who sweeps it?

**R21. A session worktree is removed once its branch is merged into main and no running program is working inside it, whatever files it still holds; the cleaner names each file it discards —
built-live (PR [clean-worktrees: mechanical reaper for finished session worktrees, reporting at every seat launch](https://github.com/nedsnodes/nedsnodes/pull/73)); vacancy made provable (PR [worktree reaper: prove vacancy before reaping, instead of assuming it](https://github.com/nedsnodes/nedsnodes/pull/100), merged 2026-08-19).**
`scripts/clean-worktrees.py`: anything failing or ambiguous is kept with
its reason; the launcher runs only the safe subset at boot; removal runs
daily at 06:30 as `clean-worktrees.py --remove`. The posture it set,
reused across this model: mechanical predicates, ambiguity keeps, report
before remove. PR [worktree reaper: prove vacancy before reaping, instead of assuming it](https://github.com/nedsnodes/nedsnodes/pull/100) closed the gap where an untrustworthy vacancy
answer read as vacant: vacancy is now proven by a usable answer or the
worktree is kept, with a reason that does not claim a process that was
never seen. `lsof` present at provisioning is R18's checklist line.

**R22. Untracked files classified; junk ignored by pattern — ruled closed
(2026-08-17; issue [Worktree file hygiene: classify untracked files so junk is ignored rather than accumulating in search results](https://github.com/nedsnodes/nedsnodes/issues/50) closed).** The `.gitignore` is the living list —
new patterns as new junk classes are observed, each with its reason
beside it. The periodic cleanup script is not built; build trigger: a
real accumulation surfacing — then its first version reports and never
deletes. Unpromoted work is protected by exactly one net: commit it.

**R23. Agent scratch lives in the scratchpad — satisfied by a Claude Code
runtime default (ruled 2026-08-17).** The runtime names a per-session
scratchpad outside the repository in every system prompt. A remind-tier
hook on scratch-shaped writes stays a recorded candidate sharing R26's
hook-plus-config pattern.

**R24. Branch surveys fetch before they conclude — mostly encoded: the Stop hook `scripts/checkout-freshness-catch-up.py` fetches origin at the end of each turn, at most once every five minutes, so the remote-tracking refs are rarely more than a few minutes old; a survey that must be exact still fetches first.**
Before concluding what exists or is
merged: `git fetch --prune origin` and read remote-tracking refs; a
survey that cannot reach the remote says so. Evidence: a prune list built
from unfetched refs missed four merged branches (2026-08-17).

**R25. Dead worktree registrations get surfaced — BUILT (PR [clean-worktrees: one report line names dead registrations and the prune command (R25)](https://github.com/nedsnodes/nedsnodes/pull/112), merged
2026-08-20).** A worktree registered under a temporary directory
(`/private/tmp` on macOS, `/tmp` on the box) leaves a dead entry when the
temp area clears, and `git worktree prune` is manual. The
`clean-worktrees.py` report carries one line naming dead registrations and
the prune command — report only; the prune stays deliberate.

**R26. New MDs land in canonical locations — ruled-unbuilt (issue [MD-placement guidance as symmetric pre-tool remind hooks on both runtimes (boss-directed design, build deferred)](https://github.com/nedsnodes/nedsnodes/issues/11)).** A
PreToolUse *remind* hook on MD writes outside the canonical locations, symmetric
across both agent runtimes, one shared config — the page
`docs/nedsnodes-wiki/nedsnodes-founding-principles-actors-and-repository-layout.md` § "Where things live" becomes the single-source path list at
build time (known gap: it lacks `docs/agents/`). Remind, not block: MD
creation is overwhelmingly legitimate. Build trigger: a note landing
astray despite the queue rule. The hook-plus-config pair serves R23 and
R26 both — build once, configure twice.

**R27. Records kept on one machine stay out of commits — built-live (accreted
entry by entry).** `.gitignore` carries the walk-ledger, review-record,
marker, and `CLAUDE.local.md` patterns, each with its reason. Limit,
observed live: gitignore protects the repository, not the placement — a
file can still land in the wrong checkout (R6's business).

### Cross-cutting

**R28. Rules are delivered at their trigger moment** — see Standing
rulings; listed here to keep the numbering complete.

## Index

| # | Rule | Rung |
|---|---|---|
| R1 | Guards resolve roots correctly | — (foundation) |
| R2 | Session states its git context | — (composition of R3/R5/R6) |
| R3 | Detached/reference agent-seat refuses writes | block |
| R4 | Stale base | — |
| R5 | Status line shows branch | default |
| R6+R7 | No writes into the reference | block |
| R8 | One live session per directory | — |
| R9 | One name = one agent-seat | default + block |
| R10 | The approval page sets which agent-instructions changes need approval | block |
| R11 | Backups read-only to agents | block (no lane) |
| R12 | Agents never push to main | impossible (account tier) + text (agent tier) |
| R13 | PR process + deputization | text (process) |
| R14 | One branch, one writer | default |
| R15 | Landed changes reach running agent-seats | default + block (attention) |
| R16 | Binary updates at launch only | default |
| R17 | Machinery self-updates at safe points | text (principle) |
| R18 | Hosts survive disconnects | default |
| R19 | Snapshot cadence | default |
| R20 | Handoff preserves structure | default |
| R21 | Worktrees reaped when safe | detect + remind |
| R22 | Junk ignored by pattern | default |
| R23 | Scratch lives in the scratchpad | default |
| R24 | Surveys fetch before concluding | default + text |
| R25 | Dead registrations surfaced | remind (report) |
| R26 | New MDs land in canonical locations | remind |
| R27 | On-machine records stay uncommitted | default |
| R28 | Rules delivered at trigger | principle |
