---
issue: "[The approval-walk short-answer hook crashes when a transcript record's message is a string](https://github.com/nedsnodes/nedsnodes/issues/5112)"
---

# The approval-walk short-answer hook crashes when a transcript record's message is a string

## Reproduction

On main at 2b7729a53, in `nn-systems/skills/walk-me-through/walk-me-through-user-short-answer-to-approval-walk-item-expanded-into-instructions-user-prompt-submit-hook.py`, the function `item_shown_in_transcript` reads each record as `(record.get("message") or {}).get("content")`. A record whose `message` is a string makes that line raise `AttributeError: 'str' object has no attribute 'get'`. The function's docstring says it raises only `OSError` or `ValueError`, which are the errors its caller handles, so the `AttributeError` escapes as a traceback.

To reproduce, run this from a checkout at main:

```
echo '{"type":"assistant","message":"a string message"}' > /tmp/t.jsonl
python3 - /tmp/t.jsonl <<'E'
import importlib.util, sys
p = "nn-systems/skills/walk-me-through/walk-me-through-user-short-answer-to-approval-walk-item-expanded-into-instructions-user-prompt-submit-hook.py"
spec = importlib.util.spec_from_file_location("h", p); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
parser = m.shown_text_parser(m.load_walk_finder())
m.item_shown_in_transcript(sys.argv[1], "Item 1 of 2: x", parser, {})
E
```

It prints a traceback ending in `AttributeError: 'str' object has no attribute 'get'`.

## Why it matters

The hook runs `item_shown_in_transcript` when the user approves or disapproves a waiting approval-walk item with a short answer. One malformed record anywhere in the agent-session's transcript then crashes the hook with a traceback. The mac-claude reviewer of PR [Walk short-answer hook: stop comparing a revised item and stop calling a model](https://github.com/nedsnodes/nedsnodes/pull/4491) found this case, and said PR [Walk answer hook: settled-discussion line fixes from PR 4438's follow-up](https://github.com/nedsnodes/nedsnodes/pull/4519) fixed the same pattern in another path of the hook (unverified). No record shows a real Claude Code transcript with a string `message` (unverified).

## What to do

Make the hook skip any record whose `message` is not an object, as it already skips a content block that is not an object. The best place is the shared transcript reader, `scripts/claude-code-session-transcript-records-read-backward-common.py`, so that every program reading transcripts through it gets the same check. Add a case to `nn-systems/skills/walk-me-through/tests/walk-me-through-user-short-answer-to-approval-walk-item-expanded-into-instructions-user-prompt-submit-hook-test.py` that feeds the record above to `item_shown_in_transcript` and asserts that it returns False. The agent-seat agent-instructions-editor wrote this function and owns the fix.
