---
issue: "[Check-in timing: infrequently-updated files immediately after update; append-type logs at logical breakpoints](https://github.com/nedsnodes/nedsnodes/issues/25)"
---

# Check-in timing: infrequently-updated files immediately after update; append-type logs at logical breakpoints

## Outcome: closed as superseded (2026-11-24)

The user approved closing this GHI as superseded in item 23 of 29 of approval-walk claude-md-lines-already-covered-by-hooks-and-skills-approval-walk-2026-11-21. The enforcement this GHI waited for was not built, and three rules now govern these files:

- Specs, docs and code reach main in a pull request, which merge-lane-2 reviews and merges ([CLAUDE.md](https://github.com/nedsnodes/nedsnodes/blob/main/CLAUDE.md)).
- A session-handoff file stays on its agent-seat's machine and is never committed ([the glossary's session-handoff entry](https://github.com/nedsnodes/nedsnodes/blob/main/docs/nedsnodes-wiki/nedsnodes-glossary.md)).
- Logs go in the log-store on ned-box, never in the repository ([CLAUDE.md](https://github.com/nedsnodes/nedsnodes/blob/main/CLAUDE.md)).

One gap stays open: no rule on main now says when to commit a spec or code. The GHI-MD on when to push, which the user approved on 2026-10-14 and which is not yet filed, covers pushing only.

The two designs cited below, `fast-handoff-design.md` and `comms-bridge-spec.md`, are no longer on main.

## Ruling (boss, 2026-07-24)

Check-in through the git-gatekeeper is fast, safe, and reversible, so nothing waits without a reason. Two file classes, two timings:

- **Infrequently-updated files** — specs, docs, code, and the handoff files and read stamps (written once per session, not appended): check in **immediately after update**.
- **Append-type log files** — currently only the future mini-comms logs (companion era): check in at a **logical breakpoint** — session end or next session start — never per append, so log traffic never churns main's head.

## Where this is applied

- https://github.com/nedsnodes/nedsnodes/blob/main/docs/cross-project/fast-handoff-design.md — handoff files and read stamps submit through `git-gatekeeper.py check-in` immediately when written; the files reach disk first, so a failed submission never blocks a session boundary, and resubmission is always safe (a gatekeeper guarantee).
- https://github.com/nedsnodes/nedsnodes/blob/295c9f35/docs/cross-project/comms-bridge-spec.md — log rotation happens when a handoff is written.

## Destination and close condition

A CLAUDE.md line was the destination until the step-2 admission (2026-08-06) declined it — the floor keeps only lines unique to the project or the boss's preferred working methods, and this rule's delivery moves to code: the git-gatekeeper can enforce the timing and stamp session ids mechanically when built. This issue closes when that enforcement lands, or if the rule is superseded.

Placement note: briefly recorded in founding plan § Standing decisions, then re-homed here same day (boss: Standing decisions cover the boot-up phase only; post-boot needs are GHIs — short ones issue-only, long ones MD-GHI pairs).

—
Session: 23789ca5-e422-422a-bb1d-f03616746770 (new-vp)
