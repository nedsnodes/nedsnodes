---
issue: "[The tool-message-to-agent collector misses a module string constant that reaches a raise or print only by name](https://github.com/nedsnodes/nedsnodes/issues/4720)"
---

# The tool-message-to-agent collector misses a module string constant that reaches a raise or print only by name

## Reproduction

PR [4709](https://github.com/nedsnodes/nedsnodes/pull/4709) adds a refusal to `nn-systems/skills/walk-me-through/walk-me-through-answer-added-texts-cold-read-fast-read-check-and-close.py`. It defines the text at module level and raises it through a local helper:

```python
FRESH_AGENT_REWRITE_ITEM_START_MOVED = (
    "would make the walk-document read {item} as starting at line {line}, not at its heading `{heading}`, ...")
...
    def refused(problem):
        return Failure(FRESH_AGENT_REWRITE_REFUSED.format(..., problem=problem, ...))
...
            raise refused(FRESH_AGENT_REWRITE_ITEM_START_MOVED.format(
                item=item, line=spans_after[position][3] + 1, heading=lines[unit[3]].strip()))
```

`python3 scripts/pull-request-review-plan.py --pull-request 4709`, run on main at 2ff1681ac, prints:

```
tool-message-to-agent text, whole pull request (516a496b6183..7f9354c1bca8):
  none
```

So the review plan lists no cold-read-fast-read for this new message, and merge-lane-1 found the gap only by reading the diff.

Main has the same miss today. Run on main's copy of the same file, `tool_message_to_agent_string_nodes_in_source` in `nn-systems/general-tools/python-source-tool-message-to-agent-string-collector-common.py` returns none of these refusal texts: `FRESH_AGENT_REWRITE_REFUSED`, `FRESH_AGENT_REWRITE_MISSING`, `FRESH_AGENT_REWRITE_EMPTY`, `FRESH_AGENT_REWRITE_SHARED_HEADING`, `FRESH_AGENT_REWRITE_ITEMS_CHANGED`, `FRESH_AGENT_REWRITE_WITHDRAWN_HEADING_NOT_READ`, `FRESH_AGENT_REWRITE_HEADING`. It does return `FRESH_AGENT_REWRITE_TAG_LINE`, because that name ends in `_LINE`.

## Why it is missed

The collector counts a string as a tool-message-to-agent by its form. A module constant assigned a string counts when its name ends in one of `AGENT_STRING_NAME_SUFFIXES`, such as `_LINE` or `_REFUSAL` (`visit_assignment_value`), or when a dict literal gives it as the value of a hook output key (`visit_Dict`). Nothing else makes it count. In particular, when a raise, a print or a helper printer reads a module constant by its name, whether as `CONSTANT`, as `CONSTANT.format(...)`, or inside a call such as `refused(CONSTANT.format(...))`, the collector does not follow the name to the constant's string. A function's return statement that the collector follows, such as `refused`'s `return Failure(FRESH_AGENT_REWRITE_REFUSED.format(...))`, has the same gap. So any constant named without one of those suffixes, such as `..._MOVED` or `..._MISSING`, is invisible to the review plan and to every other caller of the collector.

## What to do

Make the collector follow a module constant's name: wherever it already collects a string written in place, in a raise, a print, a helper printer's argument or a followed return statement, it also collects the string of a module constant named there, bare, with `.format(...)`, or as an argument of a call. GHI [2393](https://github.com/nedsnodes/nedsnodes/issues/2393) settled how the collector's earlier misses were fixed: in the rule that missed, with a test that fails without the fix. Do the same here, with one test case for each of the forms above, and one that checks the collector returns every `FRESH_AGENT_REWRITE_*` message constant of `nn-systems/skills/walk-me-through/walk-me-through-answer-added-texts-cold-read-fast-read-check-and-close.py`.

Owner: cold-read-improvement, which has kept the collector (PRs [3952](https://github.com/nedsnodes/nedsnodes/pull/3952) and [4186](https://github.com/nedsnodes/nedsnodes/pull/4186)).

## Outcome

Fixed by PR [4726](https://github.com/nedsnodes/nedsnodes/pull/4726), merged as 91ba6ab3 on 2026-11-25. The collector now follows a module string constant named at a raise, a print, a helper printer or a followed return, bare or through `.format`, with one test for each form. `scripts/pull-request-review-plan.py --pull-request 4709` now lists `FRESH_AGENT_REWRITE_ITEM_START_MOVED`. The forms it still misses, a constant reached through `+` or a string literal's `join` and a bare constant given to a dotted exception class, such as `raise argparse.ArgumentTypeError(PROBLEM)`, went to cold-read-improvement as fix-next findings 3 and 4 of PR 4726's follow-up request. It also still misses a constant given bare as an argument of a call that is neither a printer nor followed, inside a print or a raise, such as `print(f(a, C))` or `raise ValueError(f(C))`, which is the "as an argument of a call" form 'What to do' names; PR 4726 left it out because following such arguments collected seven strings that are not messages, such as `cause_line(program, CAUSE)`. That form is with cold-read-improvement, for [PR 4741](https://github.com/nedsnodes/nedsnodes/pull/4741)'s fix-round or a follow-up pull request.
