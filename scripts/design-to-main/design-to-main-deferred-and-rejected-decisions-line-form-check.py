#!/usr/bin/env python3
"""Report each malformed line under a design's `Deferred-decisions` or `Rejected-decisions` heading.

Usage: design-to-main-deferred-and-rejected-decisions-line-form-check.py <design file>...

A line is a top-level item of a list in the section: from the heading, at any level, to the
next heading at the same or a shallower level. A nested item is part of the line above it.
A line is well formed when it begins with one of its heading's tags, in DECISIONS_SECTION_HEADING_TO_HASHTAGS_A_LINE_UNDER_IT_MAY_BEGIN_WITH,
and gives a `#reason` after it, as in
`- #not_in_this_run **The report's content.** #reason no run has needed it yet.`
A tag may be written with or without the closing `#` the hashtag glossary describes.

Exit 0 when every line is well formed, 1 when one is not, each printed with its file and line
number, 2 when the check could not run: a file it could not read, or the Markdown parser.
"""

import importlib.util
import re
import sys
from pathlib import Path

CHECKOUT = Path(__file__).resolve().parents[2]
MARKDOWN_PARSER_MODULE = (CHECKOUT / "nn-systems" / "general-tools"
                          / "markdown-commonmark-parser-with-tables-common.py")
DESIGN_WRITING_INSTRUCTIONS = "docs/agents/queue/design-to-main-design-writing-agent-instructions.md"

DECISIONS_SECTION_HEADING_TO_HASHTAGS_A_LINE_UNDER_IT_MAY_BEGIN_WITH = {
    "Deferred-decisions": ("#not_in_this_run", "#rejected"),
    "Rejected-decisions": ("#rejected",),
}
REASON_TAG = "#reason"
LIST_ITEM_MARKER = re.compile(r"^\s*(?:[-*+]|\d{1,9}[.)])\s*")

EXIT_WELL_FORMED = 0
EXIT_MALFORMED = 1
EXIT_COULD_NOT_RUN = 2


class CouldNotRun(Exception):
    """The check could not run; the message says why."""


def markdown_parser():
    """Return the project's CommonMark parser; raise CouldNotRun when it cannot be loaded."""
    try:
        specification = importlib.util.spec_from_file_location(
            "markdown_commonmark_parser_with_tables_common", MARKDOWN_PARSER_MODULE)
        module = importlib.util.module_from_spec(specification)
        specification.loader.exec_module(module)
        return module.markdown_parser()
    except Exception as error:
        raise CouldNotRun(f"the Markdown parser {MARKDOWN_PARSER_MODULE} could not be loaded: "
                          f"{error}") from error


def tag_pattern(tag):
    """Match the tag as a whole word, with or without its closing `#`."""
    return re.compile(re.escape(tag) + r"#?(?![\w#])")


def line_problem(heading, item_text):
    """Return why the line under this heading is malformed, or None when it is well formed."""
    tags = DECISIONS_SECTION_HEADING_TO_HASHTAGS_A_LINE_UNDER_IT_MAY_BEGIN_WITH[heading]
    opening = next((match for match in (tag_pattern(tag).match(item_text) for tag in tags)
                    if match), None)
    if opening is None:
        return f"it does not begin with {' or '.join(f'`{tag}`' for tag in tags)}"
    if not tag_pattern(REASON_TAG).search(item_text, opening.end()):
        return f"it gives no `{REASON_TAG}` after its `{opening.group(0).rstrip('#')}`"
    return None


def malformed_lines(parser, text):
    """Return (line number, heading, line's first source line, problem) for each malformed line."""
    lines = text.split("\n")
    found = []
    heading = None
    heading_level = None
    tokens = parser.parse(text)
    for index, token in enumerate(tokens):
        if token.type == "heading_open":
            level = int(token.tag[1:])
            if heading is not None and level <= heading_level:
                heading = None
            name = tokens[index + 1].content.strip()
            if name in DECISIONS_SECTION_HEADING_TO_HASHTAGS_A_LINE_UNDER_IT_MAY_BEGIN_WITH:
                heading, heading_level = name, level
        elif heading is not None and token.type == "list_item_open" and token.level == 1:
            first = token.map[0]
            item_text = LIST_ITEM_MARKER.sub("", " ".join(
                line.strip() for line in lines[token.map[0]:token.map[1]]), count=1)
            problem = line_problem(heading, item_text)
            if problem:
                found.append((first + 1, heading, lines[first], problem))
    return found


def report(path, found):
    """Return the message for one file's malformed lines."""
    lines = [f"{path}:{number}: under `{heading}`, {problem}: {source.strip()}"
             for number, heading, source, problem in found]
    return "\n".join(lines)


def instructions():
    """Return the lines that say what to do about the malformed lines reported above them."""
    forms = "; ".join(f"under `{heading}`, `{tags[0]} <the case>. {REASON_TAG} <why>.`"
                      for heading, tags in DECISIONS_SECTION_HEADING_TO_HASHTAGS_A_LINE_UNDER_IT_MAY_BEGIN_WITH.items())
    return "\n".join([
        "These lines are not in the form each line of the section must have: " + forms + ".",
        "If the user has sorted the line, rewrite it in that form, keeping its case and its reason.",
        f"If he has not, sort it with him as step 2 of {DESIGN_WRITING_INSTRUCTIONS} says.",
    ])


def main(arguments):
    if not arguments or any(argument.startswith("-") for argument in arguments):
        print(__doc__.split("\n\n")[1], file=sys.stderr)
        return EXIT_COULD_NOT_RUN
    try:
        parser = markdown_parser()
        reports = []
        for argument in arguments:
            try:
                text = Path(argument).read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError) as error:
                raise CouldNotRun(f"{argument} could not be read: {error}") from error
            found = malformed_lines(parser, text)
            if found:
                reports.append(report(argument, found))
    except CouldNotRun as error:
        print(f"The Deferred-decisions and Rejected-decisions line check did not run, because {error}.",
              file=sys.stderr)
        print("Tell the user this whole message.", file=sys.stderr)
        return EXIT_COULD_NOT_RUN
    if not reports:
        return EXIT_WELL_FORMED
    print("\n".join(reports + [instructions()]))
    return EXIT_MALFORMED


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
