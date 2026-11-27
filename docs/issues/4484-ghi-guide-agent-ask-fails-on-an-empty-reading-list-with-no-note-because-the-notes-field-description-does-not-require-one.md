---
issue: "[ghi-guide-agent ask fails on an empty reading list with no note, because the notes field's description does not require one](https://github.com/nedsnodes/nedsnodes/issues/4484)"
---

# ghi-guide-agent ask fails on an empty reading list with no note, because the notes field's description does not require one

## Reproduction

The Claude reviewer of [PR 4309, "ghi-guide-agent cold-start prompt: each JSON answer kind names its fields (PR 4281 fast-read follow-up)"](https://github.com/nedsnodes/nedsnodes/pull/4309) reproduced this on main at commit 65dc7ec52, in [review 6031703521](https://github.com/nedsnodes/nedsnodes/pull/4309#pullrequestreview-6031703521). Its test harness called the real `ask()` and `main()` of `scripts/ghi-guide-agent-ask.py`, with `run_claude` and the mirror refresh faked. No real `claude` turn ran.

1. Run one resumed reading-list ask, which sends no cold-start prompt.
2. Have the model answer `{"kind": "reading-list", "issues": []}`, which the answer schema allows.
3. The ask exits 1 with empty stdout. Its stderr includes `the reading-list answer names no issue and gives no note: {"kind": "reading-list", "issues": []}`, then gives the fallback instruction.
4. The same answer with a non-blank note exits 0.

## What is wrong

The answer validation in `scripts/ghi-guide-agent-ask.py` rejects a reading list that names no GHI and gives no note. What the model is told says otherwise: the `notes` field's schema description reads "For reading-list: note lines in plain sentences, only when needed.", and the cold-start prompt's first form says "plus, only when needed, note lines". [PR 4309](https://github.com/nedsnodes/nedsnodes/pull/4309) corrects the prompt, but a resumed agent-session keeps its old cold-start prompt until it is replaced, and the schema description stays as it is.

The harm is negligible: the failure is visible, nothing is lost, and the ask can be rerun. No real rejection is recorded. Of 28 real reading lists the reviewer counted on 2026-11-23, 4 were empty and all 4 had notes.

## What to do next

reboot-test, the agent-seat that owns the ghi-guide-agent ask, makes the program print a fixed line, such as "no GHI to read on this topic", for an empty reading list with no note, in place of failing, so that the result no longer depends on the model's wording. reboot-test adds a test that feeds `{"kind": "reading-list", "issues": []}` through the real answer validation and output, and asserts exit 0 with that line on stdout.
