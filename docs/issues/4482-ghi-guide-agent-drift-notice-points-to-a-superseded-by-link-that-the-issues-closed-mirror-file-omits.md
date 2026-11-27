---
issue: "[ghi-guide-agent's drift notice points to a Superseded-by link that the closed-issues mirror file omits](https://github.com/nedsnodes/nedsnodes/issues/4482)"
---

# ghi-guide-agent's drift notice points to a Superseded-by link that the closed-issues mirror file omits

## Reproduction

The Claude reviewer of [PR 4309, "ghi-guide-agent cold-start prompt: each JSON answer kind names its fields (PR 4281 fast-read follow-up)"](https://github.com/nedsnodes/nedsnodes/pull/4309) reproduced this defect on main at commit 65dc7ec52, in [review 6031703521](https://github.com/nedsnodes/nedsnodes/pull/4309#pullrequestreview-6031703521). Its test harness called the real `ask()` and `main()` of `scripts/ghi-guide-agent-ask.py`, `render_closed()` of `scripts/ghi-mirror-refresh.py` and `adjudicate()` of `scripts/ghi-issue-write.py`, with `run_claude` and the mirror refresh faked. No real `claude` turn ran.

1. The test gives a closed GHI, the old GHI, a body that names a new GHI in a `Superseded-by:` line.
2. ghi-guide-agent cites the old GHI in a reply, so `compose_drift_notice()` sends its drift notice.
3. The notice tells the agent to re-read the old GHI's entry in `issues-closed.md`, which `scripts/ghi-mirror-refresh.py` generates in the GHI mirror, "including any Superseded-by: link".
4. The entry holds only the number, title, close date and reason, as in `#13 — t13 — closed 2026-08-08 (completed)`, so the link is not there to read.
5. The agent cannot learn that the new GHI replaces the old one, and the write proceeds whichever way the ask ends. It proceeds on an `unrelated` verdict. It also proceeds on `adjudication skipped` when the agent answers a draft's verdict request with the corrected reading list the notice asks for, because a reading list is not a verdict.

## What is wrong

The drift notice and the third form of the cold-start prompt, both in `scripts/ghi-guide-agent-ask.py`, send the agent to a `Superseded-by:` link in `issues-closed.md`. `render_closed()` writes each closed GHI's number, title, close date and reason, and nothing from its body. `scripts/ghi-issue-write.py` tells authors to mark a covered GHI `Superseded-by:` and close it, so authors record a link the mirror file then drops.

The harm is repairable: a duplicate GHI can be merged and closed. No real case is recorded. None of the 122 closed GHIs in the current mirror carried the `Superseded-by:` line, in its body or its comments, when the reviewer searched on 2026-11-23.

## What to do next

reboot-test, the agent-seat that owns the ghi-guide-agent ask, does these steps:

1. Decide where the replacing GHI is recorded. A link-only-GHI's body holds only links, and the mirror's query does not fetch the target of `close --reason duplicate <number>`, so the mirror may need a new field.
2. Have the program name the replacing GHI in the drift notice, and say nothing about a replacement when a closed GHI has none. Remove the instruction to look for the link from the notice and from the third form of the cold-start prompt.
3. Have the notice ask for a corrected verdict on a draft's verdict request, and for a corrected reading list on a reading-list request.
4. Add a test that fails on today's behavior.
