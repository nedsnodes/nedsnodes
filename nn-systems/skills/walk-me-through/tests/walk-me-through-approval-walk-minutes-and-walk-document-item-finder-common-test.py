#!/usr/bin/env python3
"""Tests of the walk finder's item label patterns: each compiles on Python 3.9 and reads a number whole.

The hooks that load the finder run under the Mac's system python3, 3.9, which rejects the atomic groups and
possessive quantifiers of Python 3.11. Parsing with the running interpreter finds both forms on any later version.

Run: python3 nn-systems/skills/walk-me-through/tests/walk-me-through-approval-walk-minutes-and-walk-document-item-finder-common-test.py
Prints one line per failed case and a summary, and exits non-zero if any case fails.
"""
import importlib.util
import random
import re
import sys
import time
from pathlib import Path

FINDER_FILE = (Path(__file__).resolve().parents[1]
               / "walk-me-through-approval-walk-minutes-and-walk-document-item-finder-common.py")
FIRST_PYTHON_WITH_ATOMIC_GROUPS = (3, 11)
FUZZ_INPUT_COUNT = 40000
LONG_INPUT_ELEMENT_COUNT = 50000
LONG_INPUT_SECONDS_LIMIT = 5

failures = []
case_count = 0


def check(name, condition, detail=""):
    global case_count
    case_count += 1
    if not condition:
        failures.append(name)
        print(f"FAIL  {name}: {detail!r}"[:400])


def load_finder():
    specification = importlib.util.spec_from_file_location("walk_finder_for_finder_test", FINDER_FILE)
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def pattern_uses_syntax_python_3_9_rejects(pattern_text, flags=0):
    from re import _constants, _parser

    rejected = {_constants.ATOMIC_GROUP, _constants.POSSESSIVE_REPEAT}

    def holds_rejected(node):
        if isinstance(node, _parser.SubPattern):
            return any(holds_rejected(child) for child in node.data)
        if isinstance(node, (tuple, list)):
            return any(child in rejected if isinstance(child, _constants._NamedIntConstant) else holds_rejected(child)
                       for child in node)
        return False

    return holds_rejected(_parser.parse(pattern_text, flags))


def atomic_group_reference_patterns(finder):
    whole = f"(?>{finder.NUMBER})"
    label = re.compile(
        rf"^(?:(?P<bold>\*\*|__)item\s+(?P<bold_number>{whole})(?:\s+of\s+(?P<total>\d+))?"
        rf"(?=\s*[:.,]|(?P=bold)\s*(?:[:.,\-–—]|$))"
        rf"|item\s+(?P<plain_number>{whole})[:.](?=\s|$))", re.I)
    without_count = re.compile(
        rf"^[*_\s]*(?:item\s+(?P<numbers>(?>{finder.NUMBER_LIST}))[*_]*(?:\s*[:.,\-–—][*_]*(?=\s|$)|\s*$)"
        rf"|items\s+(?P<plural_numbers>(?>{finder.NUMBER_LIST}))(?=[\s*_:.,;\-–—]|$))", re.I)
    return label, without_count


def match_result(pattern, text):
    match = pattern.match(text)
    if match is None:
        return None
    return match.span(), match.groups(), {name: match.span(name) for name in pattern.groupindex}


def fuzz_inputs():
    tokens = ["item", "items", "Item", "ITEMS", " ", "  ", "\t", "0", "1", "6", "12", "٣", ".", ",", "&", "and",
              " and ", "to", " to ", "-", "–", "—", "**", "__", "*", "_", ":", ";", " of ", "of", "x", "'s",
              "\n"]
    openings = ["item ", "items ", "**item ", "__Item ", "## item ", "* items ", ""]
    generator = random.Random(39)
    return [generator.choice(openings) + "".join(generator.choice(tokens) for _ in range(generator.randint(0, 14)))
            for _ in range(FUZZ_INPUT_COUNT)]


finder = load_finder()

if sys.version_info >= FIRST_PYTHON_WITH_ATOMIC_GROUPS:
    check("the syntax test finds an atomic group", pattern_uses_syntax_python_3_9_rejects(r"a(?>b+)c"))
    check("the syntax test finds a possessive quantifier", pattern_uses_syntax_python_3_9_rejects(r"ab++c"))
    check("the syntax test passes a lookahead and backreference",
          not pattern_uses_syntax_python_3_9_rejects(r"(?=(?P<n>b+))(?P=n)c"))
    for name, value in vars(finder).items():
        if isinstance(value, re.Pattern):
            check(f"{name} compiles on Python 3.9", not pattern_uses_syntax_python_3_9_rejects(value.pattern, value.flags),
                  value.pattern)

    reference_label, reference_without_count = atomic_group_reference_patterns(finder)
    for name, reference, current in (("ITEM_LABEL", reference_label, finder.ITEM_LABEL),
                                     ("ITEM_LABEL_WITHOUT_COUNT", reference_without_count,
                                      finder.ITEM_LABEL_WITHOUT_COUNT)):
        check(f"{name} keeps its group numbers and names", reference.groupindex == current.groupindex,
              dict(current.groupindex))
        differing = [text for text in fuzz_inputs() if match_result(reference, text) != match_result(current, text)]
        check(f"{name} matches as its atomic group form does", not differing, differing[:3])

for mention in ("**Item 6.2** shows the rewrite.", "Item 6.2 shows the rewrite", "**Item 6** of 8", "Item 60 of the plan"):
    check(f"ITEM_LABEL does not read {mention!r} as a label", finder.ITEM_LABEL.match(mention) is None, mention)
check("ITEM_LABEL reads a dotted number whole", finder.ITEM_LABEL.match("**Item 6.2:** x")["bold_number"] == "6.2")
check("ITEM_LABEL reads a plain number whole", finder.ITEM_LABEL.match("Item 6.2: x")["plain_number"] == "6.2")
check("a title opening with an item's number is no grouping label",
      finder.ITEM_LABEL_WITHOUT_COUNT.match("Item 36's three added texts") is None)
check("a number followed by a dot and digit is not shortened to end the label",
      finder.ITEM_LABEL_WITHOUT_COUNT.match("Item 3.4x") is None)
check("group `numbers` holds the whole list",
      finder.ITEM_LABEL_WITHOUT_COUNT.match("Item 3, 4 and 5.1: x")["numbers"] == "3, 4 and 5.1")
check("group `plural_numbers` holds the whole list",
      finder.ITEM_LABEL_WITHOUT_COUNT.match("Items 3 to 5 are smaller")["plural_numbers"] == "3 to 5")

long_inputs = {
    "a long list before a word": (finder.ITEM_LABEL_WITHOUT_COUNT,
                                  "item " + ", ".join(["1"] * LONG_INPUT_ELEMENT_COUNT) + " x"),
    "a long dotted number before a word": (finder.ITEM_LABEL, "**item " + ".".join(["1"] * LONG_INPUT_ELEMENT_COUNT)
                                           + "** shows"),
    "a long run of digits before a word": (finder.ITEM_LABEL_WITHOUT_COUNT,
                                           "item " + "1" * LONG_INPUT_ELEMENT_COUNT + "x"),
}
for name, (pattern, text) in long_inputs.items():
    started = time.perf_counter()
    found = pattern.match(text)
    elapsed = time.perf_counter() - started
    check(f"{name} is refused", found is None)
    check(f"{name} takes under {LONG_INPUT_SECONDS_LIMIT} seconds", elapsed < LONG_INPUT_SECONDS_LIMIT, elapsed)

print(f"{case_count - len(failures)} of {case_count} cases passed")
sys.exit(1 if failures else 0)
