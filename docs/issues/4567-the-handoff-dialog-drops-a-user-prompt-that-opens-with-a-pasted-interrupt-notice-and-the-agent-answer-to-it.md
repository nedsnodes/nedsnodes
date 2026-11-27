---
issue: "[The handoff dialog drops a user prompt that opens with a pasted interrupt notice, and the agent's answer to it](https://github.com/nedsnodes/nedsnodes/issues/4567)"
---

# The handoff dialog drops a user prompt that opens with a pasted interrupt notice, and the agent's answer to it

Filed by merge-lane-2 on ned-box on 2026-11-24, without asking the user first, because the defect is reproduced and makes the code behave wrongly when it runs; merge-lane-2's seat-brief directs that such a finding found during a review be filed this way. The reproduction comes first; the cause and the next action follow it.

## Reproduction

The program is `scripts/handoff-extract-conversation.py` as it is on main at `07e35ad53`. On ned-box, its main-branch copy and its helper `scripts/handoff-extract-conversation-subagent-tracker-hack.py` were written into a scratch directory with `git show origin/main:<path>`, beside a 4-record transcript, `transcript.jsonl`:

```
{"type":"user","message":{"role":"user","content":"first prompt"},"timestamp":"2026-11-24T10:00:00Z"}
{"type":"assistant","message":{"role":"assistant","content":[{"type":"text","text":"working"}]},"timestamp":"2026-11-24T10:00:01Z"}
{"type":"user","message":{"role":"user","content":"[Request interrupted by user] was all I saw; please carry on."},"timestamp":"2026-11-24T10:00:02Z"}
{"type":"assistant","message":{"role":"assistant","content":[{"type":"text","text":"Carrying on with the task now."}]},"timestamp":"2026-11-24T10:00:03Z"}
```

A short script loaded the program with `importlib`, called `read_dialog_turns(<scratch directory>/transcript.jsonl)` with its defaults, and printed each turn's voice and text, then each nonzero skip count. It printed:

```
[('user', 'first prompt'), ('assistant', 'working')]
{'injected': 1, 'acknowledgement': 1}
```

The third record is a prompt the user typed, and the fourth is the agent's answer to it. Both are missing from the turns, and nothing but the two skip counts says they were dropped. A successor agent-session that starts from this handoff never sees what the user said.

The finding was first reproduced by the `mac-claude` reviewer of PR [Idle sweep: the user's typing is read from untimed queued messages and only whole interrupt notices are skipped](https://github.com/nedsnodes/nedsnodes/pull/4558), in review [6037228246](https://github.com/nedsnodes/nedsnodes/pull/4558#pullrequestreview-6037228246), as a defect on main that the pull request does not change.

## Cause

`read_dialog_turns` drops any user record whose text starts with one of `INJECTED_TEXT_PREFIXES`, and that tuple holds `"[Request interrupted"`. A starts-with check cannot tell the notice Claude Code writes from a prompt the user typed that begins with the same words, such as one quoting the notice he saw. After a dropped record, the function also drops the next assistant reply of at most `MAXIMUM_ACKNOWLEDGEMENT_WORDS` (60) words as an acknowledgement of a notification, so the agent's answer goes too.

Claude Code writes only two whole notices of this kind. A scan on ned-box on 2026-11-24 of every user text block in `~/.claude/projects/**/*.jsonl` that starts with `[Request interrupted` found 53: 30 that are exactly `[Request interrupted by user]` and 23 that are exactly `[Request interrupted by user for tool use]`, and no other text. A whole-text match of those two notices therefore drops every real notice and keeps every typed prompt except one that is exactly a notice and nothing else, which cannot be told from the real notice and is dropped as one.

The other entries of `INJECTED_TEXT_PREFIXES`, such as `"<system-reminder>"`, are checked the same way, so a typed prompt that opens with a pasted tag of that kind would be dropped too (unverified: no transcript was searched for such a prompt). Those entries are opening tags around text that varies, so a whole-text match cannot replace them the way it replaces the interrupt notice.

## Next action

The agent-seat helper2, which made the recent commits to `scripts/handoff-extract-conversation.py`, changes `read_dialog_turns` so that a user record counts as an interrupt notice only when its whole text, with surrounding whitespace stripped, is one of the two notices. Today the notice is caught in two places, and both change:

- the drop, which tests `turn["text"].startswith(INJECTED_TEXT_PREFIXES)`: remove the entry `"[Request interrupted"` from `INJECTED_TEXT_PREFIXES` and drop a record that the whole-notice match accepts, with the same skip count and acknowledgement handling as now; no other file on main uses `INJECTED_TEXT_PREFIXES` (searched with `git grep -n INJECTED_TEXT_PREFIXES origin/main`);
- the line `if turn["text"].startswith("[Request interrupted"):`, which sets `interrupted_since_queued`: use the same whole-notice match.

PR [4558](https://github.com/nedsnodes/nedsnodes/pull/4558), open when this was filed, gives `scripts/search-user-messages-in-transcripts.py` that match as the new `INTERRUPT_NOTICE_PATTERN`, a regular expression on the notice text, and changes that file's existing `is_interrupt_notice(record)` to use it. The two readers should use one definition of the notice text rather than each keeping its own, so they cannot drift apart. Start the fix after PR 4558 merges, so the definition is on main to build on. Where the shared definition lives is helper2's choice, keeping in mind that `handoff-extract-conversation.py` runs copied beside hooks and cannot import every module in `scripts/`; if that forces a copy, add a test that fails when the copy and `INTERRUPT_NOTICE_PATTERN` disagree on the two whole notices and on a prompt that quotes one, as a test already does for the project-directory rule this file copies.

The fix adds three tests of `read_dialog_turns`: the 4-record transcript above returns all four turns; a whole notice is still dropped together with a short reply after it; and a typed prompt that starts with `[Request interrupted`, followed by queued text sent again, keeps that text rather than counting it as `resent_after_interrupt`. In the pull request, helper2 also says whether a typed prompt can plausibly open with any of the other prefixes in `INJECTED_TEXT_PREFIXES`, and either fixes that case in the same pull request or names why not.
