---
issue: "[Walk check: title search output that cannot be decoded crashes the walk check with no FAILED line](https://github.com/nedsnodes/nedsnodes/issues/4953)"
---

# Walk check: title search output that cannot be decoded crashes the walk check with no FAILED line

## Reproduction

On main at 003a0b81c, `approval_walk_item_title_user_messages_in_earlier_agent_sessions_lines` in `nn-systems/skills/walk-me-through/walk-me-through-answer-added-texts-cold-read-fast-read-check-and-close.py` runs the title search, `TITLE_SEARCH_PROGRAM`, with `subprocess.run(..., capture_output=True, text=True)` (line 3672). The script `nedlern@ned-box:/home/nedlern/nedsnodes-logs/seats/merge-lane-1/ghi-reproductions-2026-11-25/repro1.py` loads the program, replaces `TITLE_SEARCH_PROGRAM` with `nedlern@ned-box:/home/nedlern/nedsnodes-logs/seats/merge-lane-1/ghi-reproductions-2026-11-25/fake_search.py`, which writes `FAILED: the walk minutes file /tmp/café.md cannot be read.` to stderr encoded as Latin-1 and exits 2, and calls the function with one group of titles and `CLAUDE_CODE_SESSION_ID` unset. Run as `env -u CLAUDE_CODE_SESSION_ID python3 -I repro1.py <checkout> fake_search.py` on ned-box, the call raised `UnicodeDecodeError: 'utf-8' codec can't decode byte 0xe9 in position 38: invalid continuation byte`, not the program's `Failure` with its refusal.

Codex found the defect while reviewing [PR 4880, Walk check: a failed title search always gives a FAILED line, and older cache files are searched again](https://github.com/nedsnodes/nedsnodes/pull/4880), as Codex finding 6dc7a1511eeb, and reproduced it with Latin-1 stderr at both that pull request's merge base and its nn-head-commit. merge-lane-1 graded it fix-next, a defect that does not block the merge and is fixed soon after it, in [review 6067713709](https://github.com/nedsnodes/nedsnodes/pull/4880#pullrequestreview-6067713709). PR 4880 has merged; it did not cause the defect, which main had before it.

## What goes wrong

`subprocess.run(..., text=True)` decodes the child's stdout and stderr strictly, in the parent's locale encoding, before it returns. When either stream holds bytes that do not decode, `subprocess.run` raises, so neither failure branch after it runs and the refusal `APPROVAL_WALK_ITEM_TITLE_SEARCH_FAILED` is never built. `main` catches only `Failure` (line 4909), so the agent gets a Python traceback, with no FAILED line to relay and no command to run again. PR 4880's title says a failed title search always gives a FAILED line; this case is the exception.

Such bytes can reach the walk check when the title search prints a path or a user message holding bytes that are not UTF-8, for example under the C locale, where Python writes such bytes out with `surrogateescape`, or when the child runs with another `PYTHONIOENCODING`. No record shows it happening (unverified: the walk check's past output was not searched). The harm is repairable: the agent sees a traceback instead of a refusal, and once whatever made the title search fail is fixed, running the step again works.

## Why it can happen

The program decodes child output strictly in every `subprocess.run` call that passes `text=True`. On main at 003a0b81c the same file has four more such calls, at lines 2298, 2507, 2919 and 4586. Whoever fixes the title search call checks each of those for the same case, and gives the same treatment, with a test, to each whose caller turns a failed child into a refusal. One shared helper that runs a child and decodes its output this way, used by every such call, keeps the next call from repeating the defect.

## What to do

Capture the title search's output as bytes, and decode it in the encoding `text=True` uses now, the parent's locale encoding. Decode stderr with `errors="replace"` in both failure branches, the one where `load_module("title_search", TITLE_SEARCH_PROGRAM)` raises and the one for an exit status other than found or nothing found, so a failed search always reaches `title_search_failure_said` and its refusal, `APPROVAL_WALK_ITEM_TITLE_SEARCH_FAILED`, carries a FAILED line. Decode stdout strictly only once the exit status is checked; stdout that does not decode, from a search that succeeded, raises that same refusal, whose FAILED line says the search's output could not be decoded, not a traceback. Add a test whose fake title search writes Latin-1 stderr and exits nonzero, and one whose fake writes Latin-1 stdout and exits 0, and check that each gives the refusal with a FAILED line.

The author of PR 4880 was sent this finding as fix-next, so a follow-up pull request from that author may fix it. On 2026-11-25, `gh pr list --state all --search "walk-me-through-answer-added-texts-cold-read-fast-read-check-and-close in:title,body created:>=2026-11-25"` listed no pull request that changes this call. Before starting, list the open and recently merged pull requests that change `nn-systems/skills/walk-me-through/walk-me-through-answer-added-texts-cold-read-fast-read-check-and-close.py`. When one of them fixes this call and is open, leave the fix to its author; when it has merged, record the outcome here and close this GHI.
