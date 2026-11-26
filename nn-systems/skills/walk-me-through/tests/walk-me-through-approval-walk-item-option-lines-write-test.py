#!/usr/bin/env python3
"""Tests for walk-me-through-approval-walk-item-option-lines-write.py and the finder's check of its stamp,
approval_walk_item_option_lines_problem.

Run: python3 nn-systems/skills/walk-me-through/tests/walk-me-through-approval-walk-item-option-lines-write-test.py
Prints one line per case and exits non-zero if any case fails.
"""

import importlib.util
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
WRITER = HERE.parent / "walk-me-through-approval-walk-item-option-lines-write.py"
FINDER_FILE = HERE.parent / "walk-me-through-approval-walk-minutes-and-walk-document-item-finder-common.py"
spec = importlib.util.spec_from_file_location("walk_finder", FINDER_FILE)
finder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(finder)

failures = []


def check(name, condition, detail=""):
    print(("PASS  " if condition else "FAIL  ") + name + ("" if condition else f": {detail}"))
    if not condition:
        failures.append(name)


DOCUMENT = """# A walk

## Item 3 of 9: The filter stays out

The filter drops rows.

#case_against weak: one more line.

The alternative: add the filter.

Recommendation: leave the filter out.

#### Withdrawn version 1 of item 3

Recommendation: an old recommendation.

## The next item

Recommendation: something else.
"""


def run(document_text, *arguments, make_unwritable=False):
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "walk.md"
        if document_text is not None:
            path.write_text(document_text, encoding="utf-8")
        if make_unwritable:
            os.chmod(directory, 0o555)
        result = subprocess.run([sys.executable, str(WRITER), str(path), *arguments], capture_output=True,
                                text=True)
        text = path.read_text(encoding="utf-8") if path.exists() else None
        if make_unwritable:
            os.chmod(directory, 0o755)
        return result, text


def item_lines(text, heading):
    lines = text.split("\n")
    start = lines.index(heading) + 1
    end = next(n for n in range(start, len(lines)) if re.match(r"^#{1,6}\s", lines[n]))
    return lines[start:end]


result, text = run(DOCUMENT, "--item-title", "The filter stays out", "--do-nothing", "leave the filter as it is.",
                   "--recommendation", "keep the filter out.")
check("the writer exits 0", result.returncode == 0, result.stderr)
own = item_lines(text, "## Item 3 of 9: The filter stays out")
check("the old Recommendation: and The alternative: lines are gone from the item",
      not any(line.startswith(("Recommendation:", "The alternative:")) for line in own), own)
check("the do-nothing line comes before the recommendation",
      own.index("#approval_walk_item_do_nothing# leave the filter as it is.")
      < own.index("#approval_walk_item_recommendation# keep the filter out."), own)
check("an item with no creative alternative gets no creative-alternative line",
      not any("#approval_walk_item_creative_alternative#" in line for line in own), own)
check("the item's own text is kept", "The filter drops rows." in own and any("#case_against" in l for l in own), own)
check("the withdrawn version's recommendation is left alone", "Recommendation: an old recommendation." in text)
check("the next item is left alone", "Recommendation: something else." in text)
check("the finder passes the lines the writer wrote", finder.approval_walk_item_option_lines_problem(own) is None)
check("the finder reads the recommendation from the hashtag line",
      finder.approval_walk_item_last_recommendation_text_from_item_lines(own) == "keep the filter out")

result, text = run(text, "--item-title", "The filter stays out", "--do-nothing", "leave the filter as it is.",
                   "--recommendation", "keep the filter out.", "--creative-alternative",
                   "drop the step that needs the filter.")
own = item_lines(text, "## Item 3 of 9: The filter stays out")
check("a second run replaces the lines rather than adding more",
      sum("#approval_walk_item_recommendation#" in line for line in own) == 1
      and sum("#approval_walk_item_option_lines_written#" in line for line in own) == 1, own)
check("the creative-alternative line sits between the do-nothing line and the recommendation",
      own.index("#approval_walk_item_do_nothing# leave the filter as it is.")
      < own.index("#approval_walk_item_creative_alternative# drop the step that needs the filter.")
      < own.index("#approval_walk_item_recommendation# keep the filter out."), own)
check("the finder passes the rewritten lines", finder.approval_walk_item_option_lines_problem(own) is None)

edited = [line.replace("keep the filter out.", "keep it out.") for line in own]
check("the finder refuses a line changed by hand after the writer wrote it",
      "typed or changed by hand" in (finder.approval_walk_item_option_lines_problem(edited) or ""))
typed = ["Text.", "", "#approval_walk_item_do_nothing# leave it.", "", "#approval_walk_item_recommendation# do it."]
check("the finder refuses hashtag lines with no stamp",
      "no stamp" in (finder.approval_walk_item_option_lines_problem(typed) or ""))
after = own + ["", "#approval_walk_item_recommendation# another."]
check("the finder refuses an option line after the stamp",
      "after the option-lines writer's stamp" in (finder.approval_walk_item_option_lines_problem(after) or ""))
check("the finder passes an item written before the writer, with plain labels",
      finder.approval_walk_item_option_lines_problem(["The alternative: x.", "", "Recommendation: y."]) is None)

result, untouched = run(DOCUMENT, "--item-title", "No such item", "--do-nothing", "x", "--recommendation", "y")
check("an unknown title exits 2 and writes nothing",
      result.returncode == 2 and "no `##` or `###` heading titled 'No such item'" in result.stderr
      and untouched == DOCUMENT, result.stderr)
twice = DOCUMENT + "\n## The filter stays out\n\nMore.\n"
result, untouched = run(twice, "--item-title", "The filter stays out", "--do-nothing", "x", "--recommendation", "y")
check("a title two headings share exits 2 and writes nothing",
      result.returncode == 2 and "2 headings titled" in result.stderr and untouched == twice, result.stderr)
result, untouched = run(DOCUMENT, "--item-title", "The filter stays out", "--do-nothing", "  ", "--recommendation",
                        "y")
check("an empty text exits 2, names the answer it is for, and writes nothing",
      result.returncode == 2 and "--do-nothing is empty" in result.stderr and "user's N" in result.stderr and untouched == DOCUMENT, result.stderr)
result, text = run(DOCUMENT, "--item-title", "Item 3 of 9: The filter stays out", "--do-nothing", "x",
                   "--recommendation", "two\n  lines")
check("a title given with its running count still finds the item, and a text's line break becomes a space",
      result.returncode == 0 and "#approval_walk_item_recommendation# two lines" in text, result.stderr)
result, untouched = run(DOCUMENT, "--item-title", "The filter stays out", "--do-nothing", "x", "--recommendation",
                        "y", "--creative-alternative", " ")
check("an empty creative alternative exits 2, says to leave the flag out, and writes nothing",
      result.returncode == 2 and "without --creative-alternative" in result.stderr and untouched == DOCUMENT,
      result.stderr)
result, _ = run(None, "--item-title", "The filter stays out", "--do-nothing", "x", "--recommendation", "y")
check("a missing walk-document exits 2 and says it could not be read",
      result.returncode == 2 and "could not be read" in result.stderr, result.stderr)
if os.geteuid() != 0:
    result, untouched = run(DOCUMENT, "--item-title", "The filter stays out", "--do-nothing", "x",
                            "--recommendation", "y", make_unwritable=True)
    check("a walk-document it cannot write exits 2 and says so",
          result.returncode == 2 and "could not be written" in result.stderr and untouched == DOCUMENT,
          result.stderr)

print(f"{len(failures)} failed")
sys.exit(1 if failures else 0)
