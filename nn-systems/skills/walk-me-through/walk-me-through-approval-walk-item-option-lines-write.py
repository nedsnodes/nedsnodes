#!/usr/bin/env python3
"""Write the option lines that end an approval-walk item: the do-nothing line, the creative-alternative line when
the item has one, then the recommendation, each opening with its hashtag, followed by a stamp the walk check program
reads to refuse option lines an agent typed or changed by hand.

    python3 walk-me-through-approval-walk-item-option-lines-write.py <walk-document> --item-title <title>
        --do-nothing <text> --recommendation <text> [--creative-alternative <text>]

<title> is the item's heading, as in `The filter stays out`; a leading `##` and any `Item N of M: ` the walk check
program wrote are ignored, and a sub-step's `###` heading is matched the same way. The item's own text runs from its
heading to the next heading, so a sub-step or a `#### Withdrawn version` section after it is left alone. The writer
removes the item's earlier option lines, in either form, `#approval_walk_item_...#` or the plain `Recommendation:`
and `The alternative:` labels, and any earlier stamp, then appends:

    #approval_walk_item_do_nothing# <text>

    #approval_walk_item_creative_alternative# <text>      (only with --creative-alternative)

    #approval_walk_item_recommendation# <text>

    <!-- #approval_walk_item_option_lines_written# sha256=<hash of the lines from the first option line to here> -->

Each text is written as one line, line breaks in it becoming spaces. A creative alternative is given only when it solves the problem in a fundamentally
different, simpler or more powerful way, not as a variation of the recommendation; an item whose recommendation is
to do nothing gives the same text to both. Exit 0 prints what was written; exit 2 prints why nothing was written.
"""

import argparse
import importlib.util
import os
import re
import sys
from pathlib import Path

WALK_FINDER_FILE = Path(__file__).resolve().parent / (
    "walk-me-through-approval-walk-minutes-and-walk-document-item-finder-common.py")
HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
RUNNING_COUNT = re.compile(r"^Item\s+\d+(?:\.\d+)*\s+of\s+\d+:\s*")
OLD_OPTION_LINE = re.compile(r"^\s*(?:Recommendation:|The alternative:)")

NOTHING_WRITTEN = "nothing written: {problem}"
ITEM_NOT_FOUND = (
    "the walk-document {document} has no `##` or `###` heading titled {title!r}.\n"
    "Run the writer again with --item-title set to the heading's text exactly as the walk-document has it, after "
    "`## ` or `### ` and after any `Item N of M: ` the walk check program wrote.")
ITEM_FOUND_TWICE = (
    "the walk-document {document} has {count} headings titled {title!r}, so the writer cannot tell which item to "
    "write.\n"
    "Retitle the item you mean so its heading is unique, keeping its point, then run the writer again with that "
    "title.")
TEXT_EMPTY = ("--{option} is empty.\n"
              "Run the writer again with --{option} set to what the user's {answer} would do.")
CREATIVE_ALTERNATIVE_EMPTY = ("--creative-alternative is empty.\n"
                              "If the item has no creative alternative, run the writer again without "
                              "--creative-alternative; otherwise give the text of what the user's C would do.")
ANSWER_OF_OPTION = {"do-nothing": "N", "recommendation": "A"}
DOCUMENT_UNREADABLE = ("the walk-document {document} could not be read: {error}.\n"
                       "Check that the path names the walk's `docs/walk/<walk name>.md` in your checkout, then run the "
                       "writer again.")
DOCUMENT_UNWRITABLE = ("the walk-document {document} could not be written: {error}; it is as it was before, since "
                       "the writer replaces it only once the new text is written whole.\n"
                       "Fix what the error names, such as the file's permissions, then run the writer again; if it "
                       "fails the same way, tell the user the walk-document cannot be written and what the error "
                       "said.")
WRITTEN = "wrote the option lines of {title!r} in {document}:\n{block}"


def load_walk_finder():
    spec = importlib.util.spec_from_file_location("walk_finder", WALK_FINDER_FILE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Refused(Exception):
    pass


def item_span(lines, title, document):
    """(first line after the heading, end) of the one `##` or `###` item titled title."""
    found = []
    title = RUNNING_COUNT.sub("", title.strip().lstrip("#").strip())
    for number, line in enumerate(lines):
        match = HEADING.match(line)
        if match and len(match[1]) in (2, 3) and RUNNING_COUNT.sub("", match[2]) == title:
            found.append(number)
    if not found:
        raise Refused(ITEM_NOT_FOUND.format(document=document, title=title))
    if len(found) > 1:
        raise Refused(ITEM_FOUND_TWICE.format(document=document, count=len(found), title=title))
    start = found[0] + 1
    end = next((number for number in range(start, len(lines)) if HEADING.match(lines[number])), len(lines))
    return start, end


def option_block(finder, do_nothing, recommendation, creative_alternative):
    lines = [f"{finder.APPROVAL_WALK_ITEM_DO_NOTHING_HASHTAG} {do_nothing}", ""]
    if creative_alternative is not None:
        lines += [f"{finder.APPROVAL_WALK_ITEM_CREATIVE_ALTERNATIVE_HASHTAG} {creative_alternative}", ""]
    lines += [f"{finder.APPROVAL_WALK_ITEM_RECOMMENDATION_HASHTAG} {recommendation}", ""]
    stamp = (f"<!-- {finder.APPROVAL_WALK_ITEM_OPTION_LINES_WRITTEN_STAMP} "
             f"sha256={finder.approval_walk_item_option_lines_stamp_hash(lines)} -->")
    return lines + [stamp]


def written_text(text, finder, title, document, do_nothing, recommendation, creative_alternative):
    lines = text.split("\n")
    start, end = item_span(lines, title, document)
    body = [line for line in lines[start:end]
            if not (finder.APPROVAL_WALK_ITEM_OPTION_LINE_PATTERN.match(line) or OLD_OPTION_LINE.match(line)
                    or finder.APPROVAL_WALK_ITEM_OPTION_LINES_WRITTEN_STAMP_LINE_PATTERN.match(line.strip()))]
    while body and not body[-1].strip():
        body.pop()
    block = option_block(finder, do_nothing, recommendation, creative_alternative)
    return "\n".join(lines[:start] + body + [""] + block + [""] + lines[end:]), block


def checked_text(name, value):
    """The option's text on one line, each run of line breaks and the spaces around it made one space."""
    if value is None:
        return None
    if not value.strip():
        if name == "creative-alternative":
            raise Refused(CREATIVE_ALTERNATIVE_EMPTY)
        raise Refused(TEXT_EMPTY.format(option=name, answer=ANSWER_OF_OPTION[name]))
    return re.sub(r"\s*[\r\n]+\s*", " ", value.strip())


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("walk_document")
    parser.add_argument("--item-title", required=True)
    parser.add_argument("--do-nothing", required=True)
    parser.add_argument("--recommendation", required=True)
    parser.add_argument("--creative-alternative")
    arguments = parser.parse_args(argv)
    document = Path(arguments.walk_document)
    finder = load_walk_finder()
    try:
        do_nothing = checked_text("do-nothing", arguments.do_nothing)
        recommendation = checked_text("recommendation", arguments.recommendation)
        creative_alternative = checked_text("creative-alternative", arguments.creative_alternative)
        try:
            text = document.read_text(encoding="utf-8")
        except OSError as error:
            raise Refused(DOCUMENT_UNREADABLE.format(document=document, error=error))
        new_text, block = written_text(text, finder, arguments.item_title, document, do_nothing, recommendation,
                                       creative_alternative)
        temporary = document.with_name(f".{document.name}.option-lines-write.tmp")
        try:
            temporary.write_text(new_text, encoding="utf-8")
            os.replace(temporary, document)
        except OSError as error:
            temporary.unlink(missing_ok=True)
            raise Refused(DOCUMENT_UNWRITABLE.format(document=document, error=error))
    except Refused as refusal:
        print(NOTHING_WRITTEN.format(problem=refusal), file=sys.stderr)
        return 2
    print(WRITTEN.format(title=arguments.item_title, document=document, block="\n".join(block)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
