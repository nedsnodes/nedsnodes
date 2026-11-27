---
issue: "[The approval-walk answer program's item_title reads item openings with its own grammar instead of the item finder's, so the title search misses earlier messages](https://github.com/nedsnodes/nedsnodes/issues/4997)"
---

# The approval-walk answer program's item_title reads item openings with its own grammar instead of the item finder's, so the title search misses earlier messages

## Reproduction

The pre-show step of `nn-systems/skills/walk-me-through/walk-me-through-answer-added-texts-cold-read-fast-read-check-and-close.py` searches earlier messages for each waiting item's title, so that a user-ruling already given on the item is shown before the item is presented again. The program takes each title from the item's heading or opening line with its function `item_title`. The item finder, `nn-systems/skills/walk-me-through/walk-me-through-approval-walk-minutes-and-walk-document-item-finder-common.py`, decides which lines are item headings and openings. `item_title` reads those lines with patterns of its own, and in three cases the item finder reads a line as an item's heading or opening while `item_title` gives a title that an earlier message naming the item does not hold.

merge-lane-3's changes-requested review [6068214989](https://github.com/nedsnodes/nedsnodes/pull/4886#pullrequestreview-6068214989) of [PR 4886](https://github.com/nedsnodes/nedsnodes/pull/4886) raised the three cases as findings 7, 8 and 9 of its inline findings: the Claude reviewer's finding on `separators`, and Codex findings 048145209e5e and a0b6323cf2c5. The review does not let the three findings hold PR 4886's merge, because main already has each defect, and asks for each to be fixed in a later pull request. merge-lane-3 reproduced all three on main at [3e67fb9e7f9e24684740fdceb44ca1f7c4c03ebc](https://github.com/nedsnodes/nedsnodes/tree/3e67fb9e7f9e24684740fdceb44ca1f7c4c03ebc) on 2026-11-25, with the script below. Save the script as `probe.py` and run `python3 -B probe.py` from the root of a checkout:

```python
import importlib.util, sys
from pathlib import Path
here = Path("nn-systems/skills/walk-me-through")
def load(name, file):
    spec = importlib.util.spec_from_file_location(name, here / file)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module
check = load("check", "walk-me-through-answer-added-texts-cold-read-fast-read-check-and-close.py")
finder = load("finder", "walk-me-through-approval-walk-minutes-and-walk-document-item-finder-common.py")
search = load("search", "walk-me-through-approval-walk-item-title-search-user-messages-in-session-dialogs-and-lines-in-walk-minutes-print.py")
document = ("# Approval-walk\n\n## Items 3 and 4 of 9: two fixes\n\n### Item 3, Follow-up\n\nBody.\n\n"
            "- **Item 4 of 9** — the first\n\nBody.\n\n**Item 5 of 9: Keep this** (but not that)\n---\n\nBody.\n")
openings = finder.item_opening_lines(document, finder.markdown_parser())
lines = document.split("\n")
print("openings the finder reads:", {lines[line]: numbers for line, (numbers, _) in openings.items()})
print("unit starts:", [lines[start[-1]] for start in finder.item_unit_starts(finder.markdown_parser().parse(document), lines)])
for line, earlier_message, numbers in [
        ("### Item 3, Follow-up", "Item 3 of 9: Follow-up", ["3"]),
        ("- **Item 4 of 9** — the first", "Item 4 of 9: the first", ["4"]),
        ("- **Item 4** — the first", "Item 4: the first", ["4"]),
        ("**Item 5 of 9: Keep this** (but not that)", 'He decided "Keep this (but not that)" on Monday.', ["5"]),
        ("## **Item 5 of 9: Keep this** (but not that)", 'He decided "Keep this (but not that)" on Monday.', ["5"])]:
    title = check.item_title(finder, line)
    found = title in earlier_message and search.title_matcher(title, numbers)(earlier_message)
    print(f"{line!r}: title {title!r}; finds {earlier_message!r}: {found}")
```

The `found` test mirrors the title search: the search first selects lines that hold the title as a fixed string, then keeps those `title_matcher` accepts. On main the script prints that the item finder reads `### Item 3, Follow-up` and `- **Item 4 of 9** — the first` as openings of items 3 and 4 under the shared heading, and the Setext heading `**Item 5 of 9: Keep this** (but not that)` as the start of item 5. Every line then prints `False`:

1. A dash after the closing bold. `item_title`'s `separators`, `[ :,.;]*`, holds no dash, although the item finder's `ITEM_LABEL` accepts a dash after the bold closes. For `- **Item 4 of 9** — the first`, `item_title` gives `— the first`, which `Item 4 of 9: the first` does not hold. For the form without a count, `- **Item 4** — the first`, main's `item_title` reads no count at all and gives the whole line, `**Item 4** — the first`.
2. A heading label without a count. Under a heading several items share, the item finder reads `### Item 3, Follow-up` as item 3's opening through `ITEM_LABEL_WITHOUT_COUNT`. `item_title` reads only `HEADING_COUNT`, which needs `of M`, so it gives the whole line, `Item 3, Follow-up`, and misses an earlier message that says `Item 3 of 9: Follow-up`.
3. The text after the bold in a heading. For `**Item 5 of 9: Keep this** (but not that)`, `item_title` gives `Keep this`, so an earlier message quoting the heading's whole text, `"Keep this (but not that)"`, is missed; on main the ATX form `## **Item 5 of 9: Keep this** (but not that)` gives the same title.

## What PR 4886 changes

PR 4886, open when this GHI-MD was written, rewrites `item_title`. At its nn-head-commit [5dd0ead7cb32824d7e9fc8bc30ef0016294bc457](https://github.com/nedsnodes/nedsnodes/tree/5dd0ead7cb32824d7e9fc8bc30ef0016294bc457) the same script prints `False` for every line but the ATX heading, which now gives `Keep this (but not that)`: case 3 is fixed for ATX headings only, because the function tells a heading from a paragraph by a leading `#`, and a Setext heading has none. Case 1's form without a count now gives `— the first`, as the counted form does. Case 2 is unchanged. The review's blocking finding on PR 4886 asks for `item_title` to read the closing emphasis from markdown-it's parse of the opening line, which may change all three results again.

## Why it matters

The pre-show step exists so that an item the user has already decided is not put to him again as if new. A missed earlier message means the user may be asked again to decide an item he decided before, and nothing reports that the search missed. The three cases share one cause: the answer program and the item finder do not read an item's opening with one grammar. The first `#root_cause` line of PR 4886's description says that pull request removes the cause, "they now share the finder's patterns", but the script above shows all three cases still missing at PR 4886's nn-head-commit, apart from the ATX form of case 3.

## What to do

After PR 4886 merges or closes, which `gh pr view 4886 --repo nedsnodes/nedsnodes --json state` tells, run the script above on main again. When every line prints `True`, record that outcome in this GHI-MD and close the GHI as completed. Otherwise fix the cases that still print `False` at the cause, by reading each opening's title from the item finder's own parse instead of from patterns of `item_title`'s own. `item_title` is given one line, and one line cannot tell a Setext heading from a paragraph, so move the title reading into the item finder, as one function that returns the title of each opening and heading the finder reads, from the label `ITEM_LABEL` or `ITEM_LABEL_WITHOUT_COUNT` matched and the heading token markdown-it gave, and have the answer program call that function. GHI [The walk check program does not read a `#new` line that a shared setext heading shows above its underline](https://github.com/nedsnodes/nedsnodes/issues/4245) describes the same kind of fix, moving a rule into one item-finder function that both programs read. Add a test for each case above, and a test that, for every opening and heading in the item finder's own test documents, checks that the title the new function gives is found by `title_matcher` in a message written as `Item N of M: <title>`, so that the next form the two programs read differently fails a test. The agent-seat cold-read-improvement, which wrote main's `item_title` in commit c342ba926 and is the author of PR 4886, owns this fix.
