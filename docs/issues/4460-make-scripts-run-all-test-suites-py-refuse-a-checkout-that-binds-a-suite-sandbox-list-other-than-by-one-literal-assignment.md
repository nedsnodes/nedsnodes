---
issue: "[Make `scripts/run-all-test-suites.py` refuse a checkout that binds a suite sandbox list other than by one literal assignment](https://github.com/nedsnodes/nedsnodes/issues/4460)"
---

# Make `scripts/run-all-test-suites.py` refuse a checkout that binds a suite sandbox list other than by one literal assignment

## Reproduction

This reproduction ran on ned-box on 2026-11-23 against origin/main at `a3219b2ada51e8dd21c8f1461c950909d45cc00a`. It extracts that commit to a scratch directory, so it changes no checkout. Each case gives `suite_sandbox_lists_read_from_checkout_under_test` a checkout whose `scripts/run-all-test-suites.py` binds `SUITES_THAT_RUN_THE_REAL_CLAUDE_CLI` in a different way.

Save this program as `reproduce.py` in an empty scratch directory:

```python
import importlib.util, pathlib, sys, tempfile
spec = importlib.util.spec_from_file_location("runner", sys.argv[1])
runner = importlib.util.module_from_spec(spec)
sys.modules["runner"] = runner
spec.loader.exec_module(runner)
NAME = "SUITES_THAT_RUN_THE_REAL_CLAUDE_CLI"
FIRST = NAME + ' = {"a-test.py": "r"}\n'
CASES = {
    "|= after the literal": FIRST + NAME + ' |= {"b-test.py": "r"}\n',
    "for after the literal": FIRST + "for " + NAME + ' in [{"b-test.py": "r"}]:\n    pass\n',
    "def only": "def " + NAME + "():\n    pass\n",
    "class only": "class " + NAME + ":\n    pass\n",
    "import-as only": "import json as " + NAME + "\n",
}
own = set(runner.SUITE_SANDBOX_LISTS_OF_THIS_PROGRAM[NAME])
for label, text in CASES.items():
    with tempfile.TemporaryDirectory() as directory:
        top = pathlib.Path(directory)
        (top / "scripts").mkdir()
        (top / "scripts" / "run-all-test-suites.py").write_text(text)
        try:
            got = set(runner.suite_sandbox_lists_read_from_checkout_under_test(top)[0][NAME])
        except runner.CouldNotRun:
            print(f"{label}: refused")
            continue
        print(f"{label}: no error; " + ("the runner's own list" if own <= got else f"returned {sorted(got)}"))
```

From a clone of the repository on ned-box, with `$SCRATCH` set to that directory, run:

```bash
mkdir "$SCRATCH/main"
git archive a3219b2ada51e8dd21c8f1461c950909d45cc00a scripts nn-systems | tar -x -C "$SCRATCH/main"
cd "$SCRATCH" && python3 reproduce.py main/scripts/run-all-test-suites.py
```

It printed:

```text
|= after the literal: no error; returned ['a-test.py']
for after the literal: no error; returned ['a-test.py']
def only: no error; the runner's own list
class only: no error; the runner's own list
import-as only: no error; the runner's own list
```

In the first two cases the checkout's list also holds `b-test.py`, which the runner drops. In the last three, the checkout binds the name to something that is not a list of suites, and the runner uses its own list as if the checkout had no such name.

## What is wrong

`scripts/run-all-test-suites.py` decides which sandbox each suite runs in from four suite sandbox lists, named in `SUITE_SANDBOX_LIST_NAMES_READ_FROM_CHECKOUT_UNDER_TEST`. Despite the word list, each is a Python dict of suite path to reason; in older commits some were Python sets. The function `suite_sandbox_lists_read_from_checkout_under_test` parses them from the checkout under test without running its code. It is meant to refuse a list it cannot read, and its refusal tells the author to assign each list once, at the top level, as a literal dict.

Two gaps let a list it cannot read through without a refusal:

- A later binding that is not a plain assignment, such as `|=` or a `for` target, reaches `found.setdefault(bound.id, None)`. `setdefault` keeps the value already found, so the first literal stands and the later binding is ignored.
- A `def`, a `class` or an `import ... as` under one of the names is not an `ast.Name` store, so the parser does not see it. The name counts as absent, and the runner supplies its own list, which is the treatment meant for a checkout older than these lists.

## Why it matters

A suite added to a list in one of these ways gets the wrong sandbox treatment, and nothing reports it. For example, a suite added with `|=` to `SUITES_THAT_RUN_THE_REAL_CLAUDE_CLI` runs without the treatment that list gives it, so the head test run's result for that suite can be wrong.

No real checkout is known to do this. At `a3219b2ada51e8dd21c8f1461c950909d45cc00a`, a parse of `scripts/run-all-test-suites.py` for name stores, `def`, `class` and imports found exactly one binding of each of the four names. The same count, which also covers `except ... as` and `match` captures, over all 233 versions of the file in main's history up to that commit, found no version that binds any of the four names more than once. Neither search covers branches that have not merged.

## What to do next

The agent-seat cold-read-research owns this code: it authored commit `0df2f0ba8`, in [pull request 4223](https://github.com/nedsnodes/nedsnodes/pull/4223), which wrote the `setdefault` lines. Pull request 4223 was opened under the shared `mac-claude` account, so the commit's author name and email are the evidence for the agent-seat.

The agent-seat cold-read-research makes this change:

1. Change `suite_sandbox_lists_read_from_checkout_under_test` so that it accepts a list only when the file binds its name exactly once, by a top-level assignment with one target, annotated or not. Count every form of Python binding, including a second plain assignment, augmented assignment, tuple unpacking, several targets, `for`, `with`, `def`, `class`, `import ... as`, `except ... as`, `match` captures and their `async` forms. An annotation without a value, such as `NAME: dict`, binds nothing and is not counted. A name with any other binding raises `CouldNotRun`, with the existing instruction to assign each list once as a literal dict.
2. Keep the fallback to the runner's own list for a checkout that has no binding of the name, or that assigns it a set once, because older checkouts need it. Before merging, run the changed function on every version of the file in main's history and confirm that none is refused.
3. Add one table of binding forms to the runner's test suite, looped over all four names in `SUITE_SANDBOX_LIST_NAMES_READ_FROM_CHECKOUT_UNDER_TEST`, asserting the refusal for each form.
