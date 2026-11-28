---
issue: "[The walk finder starts a live item unit from a bold running count under a Withdrawn heading](https://github.com/nedsnodes/nedsnodes/issues/5438)"
---

# The walk finder starts a live item unit from a bold running count under a Withdrawn heading

Owner: agent-seat reboot-test. It wrote the Withdrawn-section skip in `item_unit_starts`, in commit `2ae17fbd7` of pull request [Walk finder and its callers agree on unnumbered, shared, reused and withdrawn layouts](https://github.com/nedsnodes/nedsnodes/pull/3739).

## What is wrong

The walk-me-through skill's shared walk finder, `nn-systems/skills/walk-me-through/walk-me-through-approval-walk-minutes-and-walk-document-item-finder-common.py`, splits a walk-document into item units: the line spans that each hold one item's text, or one shared heading's items. Every walk program that finds an item reads those units: `item_unit_spans` (lines 618 to 659 on main at commit `3dc455fccfa90e168b9f0962787a9bd1be03818f`) returns them, and `item_unit_starts` (lines 689 to 750) decides where each one starts.

The module docstring (lines 89 to 96) says that a heading opening with `Withdrawn` ends the unit it falls in, and that a heading deeper than it, up to the next heading as high or higher, starts no unit. So a version the walk-document keeps after replacing it is never read for the item's recommendation, its `#new` lines or its parts.

`item_unit_starts` applies that rule only to headings. Its Withdrawn-section check, `withdrawn_level` (lines 709 to 719), sits inside the branch for `heading_open` tokens. A top-level paragraph that opens with `**` and a running count, the `Item N of M` numbering of an item, such as `**Item 4.1 of 9:** ...`, takes the branch for paragraphs, which never reads `withdrawn_level`. So such a paragraph under `### Withdrawn: Item 4.1 of 9` starts a live unit for item 4.1.

This is a defect and not a documented exception. The same module's `item_opening_lines` (lines 333 to 384) already treats a bold label or count under a Withdrawn heading as the withdrawn version's own, not as an opening, when it names only the items that heading names.

## What it breaks

Shown by the reproduction below, on main:

- The item page builder, `nn-systems/skills/walk-me-through/walk-me-through-approval-walk-item-page-html-build-from-walk-document.py`, builds a page for the withdrawn 4.1. With the Withdrawn heading alone, it refuses because there is no heading for item 4.1. `waiting_item_units`, at line 960 of the finder, likewise returns the withdrawn text as item 4.1's unit, so a `#next_to_present item 4.1 of 9` line would show the user the withdrawn text.
- When a live `### Item 4.1 of 9` replaces the withdrawn version, as the Withdrawn label is meant to allow, the walk-document has two units for 4.1. `waiting_item_units` then raises "more than one heading for `Item 4.1`", and the page builder refuses item 4.1. Each program that reads the waiting item through `waiting_item_units` stops on that walk-document until the agent rewrites the withdrawn version's paragraph.

The Previous link is a separate matter. On main, an item page's Previous link comes only from the walk-minutes' `#item_page` lines (`neighbour_links` and `own_page_links_in_number_order` in the page builder). It does not read the units. So item 5's page links to a withdrawn 4.1's recorded page whether or not the bold paragraph is there (variants c and e below).

Pull request [Walk item page builder: the page chain owns shared links, skips unheaded numbers, and names the stale page after](https://github.com/nedsnodes/nedsnodes/pull/5302), open at head `9ae518c22f698546da4d1088365d27cd43e072a9` when this was written, makes the page chain, the Previous and Next links between item pages in number order, skip a number that no unit names. With that change, the Withdrawn heading alone drops 4.1 from the chain (variant c). The bold paragraph keeps it there, and item 5's page still gets `Previous: item 4.1` (variant e). That is Codex finding 9ae2411ed745 in merge-lane-1's review of pull request 5302, https://github.com/nedsnodes/nedsnodes/pull/5302#pullrequestreview-6097206258. The review-posting program recorded it as row 37 of that review's findings record. Pull request 5302 does not cause this defect: the units are the same on main and on its head.

## Reproduction

Run on ned-box on 2026-11-28. The fixtures and the script are kept in `nedlern@ned-box:/home/nedlern/nedsnodes-logs/seats/merge-lane-1/withdrawn-bold-paragraph-item-unit-repro-2026-11-28/`. Each `variant-*` directory holds a walk-document, `repro-walk.md`, with `## Item 4 of 9`, `### Withdrawn: Item 4.1 of 9` and `## Item 5 of 9`. Beside it is its walk-minutes, `repro-walk-minutes.md`. The variants:

- a: the Withdrawn heading only; the walk-minutes record pages for 4 and 5.
- b: as a, plus the paragraph `**Item 4.1 of 9:** ...` under the Withdrawn heading.
- c: as a, with a page for 4.1 also recorded in the walk-minutes.
- d: as b, plus a live `### Item 4.1 of 9` after the withdrawn version.
- e: as b, with a page for 4.1 also recorded in the walk-minutes.

`repro.py` takes a checkout and the reproduction directory. For each variant it prints the units `item_unit_spans` returns and what `waiting_item_units` gives for 4.1. It then runs the page builder for items 4.1 and 5 and prints each run's exit code and the page's `<nav>`. Run `python3 /home/nedlern/nedsnodes-logs/seats/merge-lane-1/withdrawn-bold-paragraph-item-unit-repro-2026-11-28/repro.py <checkout> /home/nedlern/nedsnodes-logs/seats/merge-lane-1/withdrawn-bold-paragraph-item-unit-repro-2026-11-28`. Its output on main is kept beside it as `output-on-main.txt`, and on pull request 5302's head as `output-on-pr-5302-head.txt`.

On main, in short:

| Variant | Units | `waiting_item_units` for 4.1 | Page for 4.1 | Item 5's Previous link |
|---|---|---|---|---|
| a | 4, 5 | no heading `Item 4.1` | refused | item 4 |
| b | 4, 4.1 (lines 9 to 12, the withdrawn text), 5 | the withdrawn unit | built | item 4 |
| c | 4, 5 | no heading `Item 4.1` | refused | item 4.1 |
| d | 4, 4.1, 4.1, 5 | more than one heading for `Item 4.1` | refused | item 4 |
| e | 4, 4.1, 5 | the withdrawn unit | built | item 4.1 |

On pull request 5302's head, every row is the same, except that item 5's Previous link in variant c is item 4.

## What to do

1. Add a test that fails on main. The finder has no test file of its own; its Withdrawn-layout tests are in `nn-systems/skills/walk-me-through/tests/walk-me-through-answer-added-texts-cold-read-fast-read-check-and-close-test.py`, so put it there. Build it from variants b and d: `item_unit_spans` must return no unit for the bold paragraph under `### Withdrawn: Item 4.1 of 9`, and `waiting_item_units` must return the live `### Item 4.1 of 9` in variant d as item 4.1's one unit.
2. Fix it in `item_unit_starts`: inside a Withdrawn heading's section, a top-level bold paragraph with a running count starts no unit, just as a deeper heading starts none. Then `item_unit_spans`, `item_opening_lines` and every caller read the same starts. Change the module docstring (lines 89 to 96) and `item_unit_starts`' docstring (lines 690 to 695), which state the rule for headings only, to say it covers such a paragraph too.
3. Run `gh pr view 5302 --repo nedsnodes/nedsnodes --json state`. If it says `MERGED`, also add a test to `nn-systems/skills/walk-me-through/tests/walk-me-through-approval-walk-item-page-html-build-from-walk-document-test.py`, built from variant e: item 5's page must get `Previous: item 4`. If it has not merged, leave that test to pull request 5302's page chain, which reads the fixed units.
4. Run `python3 scripts/run-all-test-suites.py --only-suites-whose-recorded-inputs-changed-since origin/main`, which runs every nn-test-suite the change to the shared finder can affect.
