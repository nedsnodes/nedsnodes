---
issue: "[The walk-me-through waiting-item read step crashes with KeyError when a no-answer row holds a brace pair](https://github.com/nedsnodes/nedsnodes/issues/4644)"
---

# The walk-me-through waiting-item read step crashes with KeyError when a no-answer row holds a brace pair

## Reproduction

Save this script as `repro.py` and run `python3 repro.py` in a checkout of main at [0d355d1cee79caecbbe7092fe6583928bc14e252](https://github.com/nedsnodes/nedsnodes/tree/0d355d1cee79caecbbe7092fe6583928bc14e252). It uses the program's own test fixtures to run the waiting-item read step of `nn-systems/skills/walk-me-through/walk-me-through-answer-added-texts-cold-read-fast-read-check-and-close.py` twice on the same walk-document, whose waiting item is rated none and asks a decision. The only difference between the two invocations is that the second checkout's path holds `{review}`.

```python
import importlib.util, shutil
spec = importlib.util.spec_from_file_location("t", "nn-systems/skills/walk-me-through/tests/walk-me-through-answer-added-texts-cold-read-fast-read-check-and-close-test.py")
t = importlib.util.module_from_spec(spec); spec.loader.exec_module(t)
try:
    for suffix in ("", "{review}"):
        document = ("# A walk\n\n" + t.CLOSE_THE_ISSUE_ITEM.format(touches="")
                    + "\n## Item 23 of 26: a later item\n\n#case_against weak: a line more.\n\nRecommendation: add it.\n")
        case = t.Case(next_to_present="item 22 of 26", document=document, root_name_suffix=suffix)
        case.minutes.write_text("# Minutes\n\n#next_to_present item 22 of 26\n")
        result = case.run(t.WAITING_ITEM_READ)
        print(f"checkout {case.checkout}: exit {result.returncode}; last stderr line: {result.stderr.strip().splitlines()[-1] if result.stderr.strip() else ''}")
finally:
    shutil.rmtree(t.SUITE_ROOT, ignore_errors=True)
```

It prints, with the temporary directory's name shortened to `...`:

```
checkout /tmp/.../case-1/checkout: exit 0; last stderr line:
checkout /tmp/.../case-2{review}/checkout: exit 1; last stderr line: KeyError: 'review'
```

## What is wrong

For an item rated none that is not to be shown to the user, the read step prints the lines `RATED_NONE_NOT_SHOWN_LINES` followed by the no-answer table's rows. The rows were already formatted by `no_answer_rows_for_waiting_item_lines`, which put the check command, with its `--cwd` path, and the item's missing-evidence text into them. [Lines 3022 to 3025](https://github.com/nedsnodes/nedsnodes/blob/0d355d1cee79caecbbe7092fe6583928bc14e252/nn-systems/skills/walk-me-through/walk-me-through-answer-added-texts-cold-read-fast-read-check-and-close.py#L3022) pass every line, the rows included, through `str.format` a second time. A brace pair in any text a row carries, the item's title in the table's heading row included, is then read as a placeholder: the step crashes with `KeyError` and prints none of the lines that tell the agent how to settle the item, or, for a brace pair that names one of the placeholders `{item}`, `{document}`, `{command}` and `{read_command}`, prints a row with other text put in its place and exits 0. Commits 8362e42ed7 and b864b94b96, both by the agent-seat cold-read-improvement, wrote these lines.

## What to do

Pass only the lines of `RATED_NONE_NOT_SHOWN_LINES` through `str.format`, then join them and the rows, unchanged, with newlines into the one `print` call, as today.

Add two cases to `nn-systems/skills/walk-me-through/tests/walk-me-through-answer-added-texts-cold-read-fast-read-check-and-close-test.py`, using the test file's own `Case` and the walk-document of `close_the_issue_case`, as the reproduction above does: one with `root_name_suffix="{review}"` and one with `root_name_suffix="{item}"`. Each expects exit 0 and every line of `result.stdout` that holds `--cwd` to hold the checkout's path, braces included, character for character. The path also appears in lines formatted once, so a test that only looks for the path anywhere in `result.stdout` passes on main for `{item}`: on main the rows print `case-2item 22 of 26` where the path held `{item}`.
