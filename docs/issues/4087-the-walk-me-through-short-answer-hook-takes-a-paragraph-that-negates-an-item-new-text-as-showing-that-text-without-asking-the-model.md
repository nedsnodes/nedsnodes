---
issue: "[The walk-me-through short-answer hook takes a paragraph that negates an item's `#new` text as showing that text, without asking the model](https://github.com/nedsnodes/nedsnodes/issues/4087)"
---

# The walk-me-through short-answer hook takes a paragraph that negates an item's `#new` text as showing that text, without asking the model

## Reproduction

Run from a checkout of main at commit 29939797d, from the repository root:

```
python3 -B repro1.py nn-systems/skills/walk-me-through/walk-me-through-user-short-answer-to-approval-walk-item-expanded-into-instructions-user-prompt-submit-hook.py
```

where `repro1.py` is:

```python
import importlib.util, sys
p = sys.argv[1]
spec = importlib.util.spec_from_file_location("hook", p); h = importlib.util.module_from_spec(spec); spec.loader.exec_module(h)
parser = h.shown_text_parser(h.load_walk_finder())
body = "#new delete the old config file\n"
for copy in ["Do not delete the old config file\n", "We will never delete the old config file\n", "#new keep the old config file\n"]:
    env = {}; parser.parse(body, env); menv = {}; parser.parse(copy, menv)
    cur = h.decision_bearing_lines(body, parser, env, False)
    shown = h.decision_bearing_lines(copy, parser, menv, False)
    checks = h.decision_line_checks(cur, shown, h.shown_units(copy, parser, menv), h.shown_units(body, parser, env))
    print(repr(copy.strip()), "-> checks sent to model:", checks)
```

It printed, on 2026-11-21:

```
'Do not delete the old config file' -> checks sent to model: []
'We will never delete the old config file' -> checks sent to model: []
'#new keep the old config file' -> checks sent to model: [('`#new` line', '#new keep the old config file', 'delete the old config file', False)]
```

The walk-document's item holds the line `#new delete the old config file`. When the message the user was shown holds "Do not delete the old config file" or "We will never delete the old config file", with no `#new` line, `decision_line_checks` returns no check, so the item passes as shown and the model never reads the pair. The third case, a message with its own `#new` line, is the control: there the pair does go to the model.

## What is wrong

The hook, `nn-systems/skills/walk-me-through/walk-me-through-user-short-answer-to-approval-walk-item-expanded-into-instructions-user-prompt-submit-hook.py`, checks that the message the user answered with a short answer showed each decision-bearing line of the item as the walk-document now holds it. Line numbers below are those of main at commit 29939797d.

In `decision_line_checks`, lines 1138 to 1184, a current line that is not a `Recommendation:` or `The alternative:` line passes without the model when the message holds no line of its kind and a unit of the message, a paragraph, an HTML block, or a whole list or quotation, ends with the line's words (lines 1162 to 1167). This applies to every decision-bearing line but those two, so to `#new_if_d`, `#case_against` and `Part N.` lines as well as `#new` lines. The test is a suffix match on words (line 1164), so any paragraph whose last words are the line's words passes, whatever comes before them, a negation included. The docstring at lines 150 to 160 describes this second way of passing; it was meant for a message that dropped the `#new` mark or put "If you approve, the new text:" before the text.

The harm: when the message shown to the user said the opposite of the item's `#new` text, but in words that end the same way, the user's short answer, such as `A`, passes this check, and the hook expands it into instructions to carry out the walk-document's text. The user's approval is then recorded for the opposite of what he was shown.

The design of this check is in the hook's docstring; the walk-me-through skill is `.claude/skills/walk-me-through/SKILL.md`.

## What to do next

The owner, agent-instructions-editor, fixes it. By `git blame` on main, the suffix match at line 1164 came from pull request [4007](https://github.com/nedsnodes/nedsnodes/pull/4007), and the lines around it from pull requests [4022](https://github.com/nedsnodes/nedsnodes/pull/4022) and [4035](https://github.com/nedsnodes/nedsnodes/pull/4035). The owner fixes the root cause: a unit that only ends with the line's words is not proof that the message showed the line. The cases this way of passing was built for must still pass: a unit whose words are the line's words, and the lead-in the docstring names at lines 1147 and 1148, `If you approve, the new text:`, before them. Two ways to do that, between which the owner chooses: in code, pass such a unit only when its words equal the line's words or equal a closed list of known lead-ins followed by them, and pair every other line as a line that did not pass is paired today (lines 1168 to 1182), so it goes to the model; or send every such pair to the model. The fix carries two tests: one with the negated paragraphs above, asserting that `decision_line_checks` returns a check for each of them; and one that, for each case the existing tests pass without the model, puts words such as "Do not" before the shown text and asserts that the pair then goes to the model, so a later loosening of the match fails a test. The defect was found by the Codex review cell while reviewing pull request [4001](https://github.com/nedsnodes/nedsnodes/pull/4001), which does not change this hook.
