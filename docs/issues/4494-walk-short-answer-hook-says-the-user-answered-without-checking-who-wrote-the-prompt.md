---
issue: "[Walk short-answer hook says the user answered without checking who wrote the prompt](https://github.com/nedsnodes/nedsnodes/issues/4494)"
---

# Walk short-answer hook says the user answered without checking who wrote the prompt

## Reproduction

The hook `nn-systems/skills/walk-me-through/walk-me-through-user-short-answer-to-approval-walk-item-expanded-into-instructions-user-prompt-submit-hook.py` turns a short answer to an approval-walk item, such as `a`, into instructions for the agent.

On main at commit dc70497da1d8, give the hook the prompt `a` while item 4 of 9 of an approval-walk waits, with a transcript whose newest record has `"turnOrigin": "peer"`, which marks a message from another agent-seat. The hook exits 0, and its context includes these two lines:

`[rule walk-me-through-short-answer-expanded-into-instructions] The user answered "a" to item 4 of 9 of approval-walk reboot-test-older-open-items-2026-10-15.`

`A means approve: the user agrees with the recommendation of item 4 of 9 (leave the filter out). Do what the recommendation says.`

The hook on main never reads `turnOrigin`, so every opening line that says "The user answered" is written without knowing who wrote the prompt. The same happens when the walk-minutes cannot be read: the hook then uses `WALK_UNKNOWN_OPENING_LINE`, at line 310, from `context_for`, at line 1742, and still says the user answered.

The two probes and the output of the second are in `nedlern@ned-box:/home/nedlern/nedsnodes-logs/seats/merge-lane-2/merge-helpers/claude-reviews/pr4438-1cb11d1e3a18b420cacfa6f9c303f7400aff8a60-2/`, as `main-hook-peer-short-answer-probe.py`, `main-hook-unreadable-files-probe.py` and `main-hook-unreadable-files-probe-output.txt`. They name scratch paths that no longer exist, so a rerun must first point them at a checkout.

## Why it matters

If another agent-seat's message were exactly `a`, the receiving agent would be told that the user approved the waiting item, and could make the change as if the user had approved it.

## How likely it is

No occurrence is known. In the 3,000 newest transcripts under `~/.claude/projects` on ned-box, none of the 826 records marked as peer messages was a bare short answer. The Mac's transcripts were not scanned.

## How it was found

The review of [Walk answer hook shows the approved #new sentence while an item waits](https://github.com/nedsnodes/nedsnodes/pull/4438) found it. That pull request does not cause it, and adds an author check only for the one line it adds.

## Options

1. When the prompt's author is not the user, or cannot be read, the hook records nothing and tells the agent to act on none of the answer.
2. Do nothing, because the case has not happened, and close this GitHub issue as not planned.

## Next action

The agent-seat reboot-test wrote these opening lines, in [walk-me-through: answer letters A, AO, Aa, D, Z, R, E, O, O2 and O3, a hook that expands each answer, and a program that fast-reads an answered item's texts and records the answer](https://github.com/nedsnodes/nedsnodes/pull/1867) and [Every registered hook's message for a rule starts with its rule ID, and a weekly job reports the rules never seen](https://github.com/nedsnodes/nedsnodes/pull/3792), so it decides this GitHub issue. On the Mac, search `~/.claude/projects/` for peer records whose text is a bare short answer. If one exists, take option 1. If none does, take option 2.
