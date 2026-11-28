---
issue: "[The pending-user-alerts hook drops the transcript read error for a record whose message is a string, and no other hook reports it when no approval-walk item waits](https://github.com/nedsnodes/nedsnodes/issues/5414)"
---

# The pending-user-alerts hook drops the transcript read error for a record whose message is a string, and no other hook reports it when no approval-walk item waits

## Reproduction

On main at [09e50fda6](https://github.com/nedsnodes/nedsnodes/commit/09e50fda6b6d27cc63179ae120383d25e9a6458b), write a transcript whose newest record is `{"type": "user", "turnOrigin": "human", "message": "hello"}`, so its `message` is a string, not an object. Close every approval-walk in the checkout. Then give the prompt `hello` to two UserPromptSubmit hooks:

- `nn-systems/skills/walk-me-through/walk-me-through-pending-user-alerts-claim-and-insert-as-approval-walk-items-user-prompt-submit-hook.py`, the pending-user-alerts hook;
- `nn-systems/skills/walk-me-through/walk-me-through-user-short-answer-to-approval-walk-item-expanded-into-instructions-user-prompt-submit-hook.py`, the short-answer hook.

Both hooks exit 0. When an alert is pending, the pending-user-alerts hook claims it, and its output does not name the read error. When no alert is pending, it prints nothing. The short-answer hook prints nothing either way. Whatever the case, neither hook's output mentions the transcript or the error.

The pull request that fixes this adds two cases to `nn-systems/skills/walk-me-through/tests/walk-me-through-pending-user-alerts-claim-and-insert-as-approval-walk-items-user-prompt-submit-hook-test.py`. Each case expects the hook to exit 0 and to show the read error to the user and to the agent. One case has an alert pending and expects it claimed. The other has none pending and expects nothing claimed. Run against the hook on main with `python3 <that test file>`, both cases fail:

    FAIL  a transcript record whose message is a string is a failed read, ... with an alert pending and no approval-walk open the hook exits 0, claims the alert, and shows the user and the agent the read error, which no other hook reports then: {"hookSpecificOutput": {... "additionalContext": "[rule walk-me-through-pending-user-alerts-added-as-walk-items] The user-alerts hook claimed 1 alert(s) ..."}}
    FAIL  a transcript record whose message is a string is a failed read, ... with no alert pending and no approval-walk open the hook exits 0, claims nothing, and shows the user and the agent the read error, which no other hook reports then: []
    2 case(s) failed

## What is wrong

`record_text` in the pending-user-alerts hook raises AttributeError for a record whose `message` is not an object. The hook's `output_for` catches it and decides who wrote the prompt from how it opens, as for any prompt it cannot match to a transcript record, and it reports the error nowhere. The comment on that `except` says the short-answer hook reports the error. It does so only while an approval-walk item waits and the prompt is not a short answer: its `own_words_output` returns None when no approval-walk is open. On the path for a short answer, its line `prompt_typed_by_user_and_transcript_read_error(payload)[0]` drops the error too.

So when no item waits, the pending-user-alerts hook decides who wrote the prompt from its opening alone, and nothing anyone reads records that the transcript could not be read.

## How often it happens

None of the 55,144 records that carry `turnOrigin`, in the 35,375 ned-box transcripts under `~/.claude/projects/` changed in the 30 days to 2026-11-27, has a `message` that is not an object. The scan is `nedlern@ned-box:/home/nedlern/nedsnodes-logs/seats/MD-skills-2/task-595-string-message-scan/transcript-turn-origin-record-message-type-count-last-30-days.py`, and its output is beside it. The fallback came in [PR 4525](https://github.com/nedsnodes/nedsnodes/pull/4525). Codex found this defect in round 2 of [PR 4555](https://github.com/nedsnodes/nedsnodes/pull/4555). Part 4 of item 20 of merge-lane-2's approval-walk, whose walk-document is `nedlern@ned-box:/home/nedlern/agents/merge-lane-2/docs/walk/merge-lane-2-maintenance-fix-agent-seat-brief-finding-grading-and-judged-main-findings-approval-walk-2026-11-25.md`, which the user approved on 2026-11-28, sent it to its author to reproduce.

## What to do

The cause is that the decision of who wrote the prompt and the fallback after a failed transcript read are written twice, once in each hook, and the pending-user-alerts hook's copy drops the error. Make one function in the pending-user-alerts hook, `typed_by_user_and_transcript_read_error`, that returns whether the user typed the prompt together with the read error or None. It catches OSError and ValueError while reading the transcript, and `record_text` raises ValueError for a `message` that is not an object. The short-answer hook calls that function instead of its own copy.

Whenever that function returns an error, the pending-user-alerts hook shows the error, with the transcript's path, to the user as a systemMessage and to the agent as additionalContext. It does so whether or not the prompt counts as typed, and whether or not it claimed an alert. When the hook has other output for the same prompt, the read error's sentence comes first in each field. A prompt that counts as typed still claims alerts. The short-answer hook's line that keeps only the function's first value can stay, because the pending-user-alerts hook now shows that error on every prompt it reads the transcript for. While an approval-walk item waits, both hooks show the error.
