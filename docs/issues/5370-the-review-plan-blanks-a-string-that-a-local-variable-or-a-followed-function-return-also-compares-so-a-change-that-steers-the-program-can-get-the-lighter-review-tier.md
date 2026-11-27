---
issue: "[The review plan blanks a string that a local variable or a followed function's return also compares, so a change that steers the program can get the lighter review tier](https://github.com/nedsnodes/nedsnodes/issues/5370)"
---

# The review plan blanks a string that a local variable or a followed function's return also compares, so a change that steers the program can get the lighter review tier

## What is wrong

`scripts/pull-request-review-plan.py` picks how much review a pull request gets. When a Python file's only change is to text the program shows to an agent, such as a message it prints, the change counts as a wording change rather than a behaviour change, and the pull request can get `codex-review-and-head-tests-tier`, a Codex review only, instead of `claude-and-codex-review-and-head-tests-tier`, which adds a Claude reviewer. To tell the two apart, `normalized_syntax_tree_dump_without_docstrings_or_tool_message_to_agent_strings` dumps each version of the file with every string that `tool_message_to_agent_string_literal_positions` lists blanked out, and compares the dumps. The strings come from the tool-message-to-agent string collector, `nn-systems/general-tools/python-source-tool-message-to-agent-string-collector-common.py`.

The defect: a string the program both shows and compares is still blanked when it reaches the comparison through a local variable or through a function's return. In both examples below, changing `"old"` to `"new"` changes what the program does, yet the two versions give the same dump, so the change reads as wording only:

```python
def main(r):
    mode = "old"
    print(mode)
    return r == mode
```

```python
def mode():
    return "old"

def main(r):
    print(mode())
    return r == mode()
```

Main already handles this case for a module constant, such as `MODE = "old"` used in `print(MODE)` and `r == MODE`: the collector marks such an entry `collected_string_is_module_constant_whose_value_also_steers_the_program`, and the review plan leaves it unblanked. No such check covers a local variable's binding or a followed function's return.

This matters because the review plan is meant to send every behaviour change to a full review. A change to a value that steers the program can get a lighter review, with no warning.

## Why it happens

The collector decides a string is message text from where it is shown, here `print`, without checking whether the same value is also compared. Commit `7c23fe915` added the check that the value is also used another way only for module constants, in `module_constant_names_that_steer_the_program`. The strings the collector reaches through a local's binding, or through a function it follows for its return value, never get that check.

## Reproduction

Run on ned-box on 2026-11-27 in a detached worktree of main at commit `54d68f5c7`, as `python3 - <path of the worktree> < probe.py`, where `probe.py` holds the script below. It loads the review plan from the worktree and dumps each example above with `"old"` and with `"new"`:

```python
import importlib.util, sys
spec = importlib.util.spec_from_file_location("p", sys.argv[1] + "/scripts/pull-request-review-plan.py")
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
f = m.normalized_syntax_tree_dump_without_docstrings_or_tool_message_to_agent_strings
a = 'def main(r):\n    mode = "{v}"\n    print(mode)\n    return r == mode\n'
b = 'def mode():\n    return "{v}"\n\ndef main(r):\n    print(mode())\n    return r == mode()\n'
for n, s in (("local compared", a), ("followed return compared", b)):
    print(n, "-> same dump for old/new:", f(s.format(v="old")) == f(s.format(v="new")))
```

Output:

```
local compared -> same dump for old/new: True
followed return compared -> same dump for old/new: True
```

Both are `True`: the dumps match, so the review plan reads each change as wording only.

The agent-seat mac-claude, the Claude reviewer on the user's Mac, found this defect in its review of pull request [Review plan blanks no module constant, and the tool-message-to-agent collector stops guessing which constants steer](https://github.com/nedsnodes/nedsnodes/pull/5287), finding on line 518 of `scripts/pull-request-review-plan.py` in review https://github.com/nedsnodes/nedsnodes/pull/5287#pullrequestreview-6090751761, and reproduced it at that pull request's merge base and at its head. That pull request leaves local bindings and followed returns as they are, which its approved scope allows, and does not cause this defect.

## What to do

1. Turn the reproduction script into two tests in `scripts/pull-request-review-plan-test.py`, one for each example above, each asserting that changing `"old"` to `"new"` gives a different dump. Run them against main and check that both fail.
2. In the collector, leave out of the blanked set every string it reaches through a local's binding or a followed function's return, as mac-claude's review suggests, the same way main leaves out a module constant that `module_constant_names_that_steer_the_program` finds. Any use other than being shown as text counts, as it does for module constants, not only `==`.
3. Run `scripts/run-all-test-suites.py --only-suites-whose-recorded-inputs-changed-since origin/main`, since the collector is a common module that other programs import, then open the pull request.
