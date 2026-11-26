#!/usr/bin/env python3
"""Add a question for the user to the open approval-walk as an unnumbered item after the whole waiting item.

Usage:
  walk-me-through-agent-question-to-user-insert-as-unnumbered-item-after-waiting-item-and-record-in-walk-minutes.py
      [--cwd DIR] --title TITLE --category CATEGORY [--waits-on TITLE ...] --flagged-line LINE [--flagged-line LINE ...]

The question check, walk-me-through-agent-question-to-user-outside-approval-walk-items-refusal-stop-hook.py,
prints this command, its --flagged-line arguments filled in, when it refuses a reply that asks the user
something outside the walk's items. The command writes the parts of the item that need no judgment:
- the walk-document gets `## <TITLE>` after the whole item holding the last waiting item, where the user alert
  program puts an alert, by the approval-walk finder's
  approval_walk_document_text_with_lines_added_after_whole_item; under it the category line, one
  `#approval_walk_item_waits_on` line per --waits-on, the `#approval_walk_item_first_entered` line giving today
  on this machine's clock, each --flagged-line on a line of its own, word for word, which is the form the
  question check reads back, and the line `#case_against <rating>: <the strongest case against your
  recommendation>`, which the walk check program refuses until the agent rates it;
- the walk-minutes get a re-planning line naming the item.
The agent then writes the rest of the question, the case against, the alternative and the recommendation, as
the command's output says. A TITLE that a `##` heading would not read as an unnumbered item, such as
"Item 3 of 9: reboot", gets the prefix "Question: ". The walk check program's close step numbers the item when
it is shown.

Exit 0 when the item was added; 1, before changing any file, when no approval-walk is open, more than one is,
its waiting item cannot be found, or the walk-document's items sit under `##` part headings, with a message on
stderr saying which and what to do.

Tool-messages-to-agent follow
docs/nedsnodes-wiki/nedsnodes-how-to-write-a-tool-message-to-agent-such-as-a-hook-refusal-or-script-error.md.
"""
import argparse
import importlib.util
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROGRAM = Path(__file__).stem
WALK_FINDER_FILE = HERE / "walk-me-through-approval-walk-minutes-and-walk-document-item-finder-common.py"
WALK_CHECK_PROGRAM = HERE / "walk-me-through-answer-added-texts-cold-read-fast-read-check-and-close.py"
QUESTION_CHECK_HOOK_FILE = HERE / "walk-me-through-agent-question-to-user-outside-approval-walk-items-refusal-stop-hook.py"

UNNUMBERED_TITLE_PREFIX = "Question: "
CASE_AGAINST_PLACEHOLDER = "#case_against <rating>: <the strongest case against your recommendation>"
NO_WALK_MESSAGE = ("no approval-walk is open in {walk_directory}, so no item was added. The question check that "
                   "printed this command runs only while one is open; if the walk was closed since, ask the user "
                   "your question in your next message.")
MORE_THAN_ONE_WALK_MESSAGE = (
    "more than one approval-walk is open or paused in {walk_directory}, so this program cannot tell which one the "
    "question belongs in, and no file was changed. Keep one as the walk-me-through skill's paragraph on more than "
    "one open approval-walk says, close the others, then run this command again. The walk-minutes of each:\n"
    "{minutes}")
UNUSABLE_WALK_MESSAGE = (
    "the open approval-walk's waiting item cannot be found, so no file was changed: its `#next_to_present` line, "
    "`{value}`, {problem}. Fix that line in {minutes} or the item's heading in {document}, then run this command "
    "again.")
NO_UNNUMBERED_ITEMS_MESSAGE = (
    "the walk-document {document} holds its items under `##` part headings, so a `##` heading added there is not "
    "an item, and no file was changed. Add the question by hand, after the whole of item {whole}, with each "
    "flagged line on a line of its own.")
REPLANNED_MINUTES_LINE = ("- Re-planned {date}: added the unnumbered item {title} after the whole of item {whole}, "
                          "from a question the question check flagged.")
DONE_LINES = (
    "Added the unnumbered item `## {title}` to {document}, after the whole of item {whole}.",
    "In that item, put the rest of the question on lines of its own, if the flagged lines are not all of it; on the "
    "`#case_against` line, put in place of `<rating>` one of none, weak, medium, strong or very strong, and after "
    "the colon the strongest case against your recommendation; then add the line `The alternative: <what D does "
    "instead>.` and, last, the recommendation stated as an action, as in `Recommendation: <what you recommend "
    "doing>.`",
    "End the message you write next with the line `I added the question to the walk as a new item.` and then "
    "{closing_lines_named} below, as its last text. {not_in_backticks}\n{closing_lines}",
)


def load_module(name, path):
    specification = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


class Refused(Exception):
    pass


def heading_title(title, walk_finder, parser):
    """title, with UNNUMBERED_TITLE_PREFIX when a `##` heading of title alone would not be an unnumbered item."""
    probe = f"## Item 1 of 1: probe\n\n## {title}\n"
    if sum(map(walk_finder.approval_walk_unit_is_unnumbered_item, walk_finder.item_unit_spans(probe, parser))) == 1:
        return title
    return UNNUMBERED_TITLE_PREFIX + title


def insert(cwd, title, category, waits_on, flagged_lines, now=None):
    walk_finder = load_module("walk_me_through_approval_walk_minutes_and_walk_document_item_finder_common",
                              WALK_FINDER_FILE)
    check_program = load_module("walk_me_through_answer_added_texts_cold_read_fast_read_check_and_close",
                                WALK_CHECK_PROGRAM)
    parser = walk_finder.markdown_parser()
    top = walk_finder.checkout_top(Path(cwd))
    walk_directory = (top or Path(cwd)) / walk_finder.WALK_DIRECTORY
    try:
        walk = walk_finder.open_walk(walk_directory, parser) if walk_directory.is_dir() else None
    except walk_finder.MoreThanOneUnclosedApprovalWalk as several:
        raise Refused(MORE_THAN_ONE_WALK_MESSAGE.format(
            walk_directory=walk_directory, minutes="\n".join(f"  {path}" for path in several.minutes_paths)))
    if walk is None:
        raise Refused(NO_WALK_MESSAGE.format(walk_directory=walk_directory))
    minutes, value, _ = walk
    document = minutes.with_name(minutes.name[:-len(walk_finder.MINUTES_SUFFIX)] + ".md")
    try:
        numbers, total = walk_finder.parse_items(value)
        total, units = walk_finder.waiting_item_units(document, value, numbers, total, parser)
    except walk_finder.UnusableRange as problem:
        raise Refused(UNUSABLE_WALK_MESSAGE.format(value=value, problem=problem, minutes=minutes, document=document))
    waiting = numbers[-1]
    whole = waiting.split(".")[0]
    unit = next(unit for unit in units if waiting in unit[0])
    text = document.read_text(encoding="utf-8")
    title = heading_title(title, walk_finder, parser)
    now = now or datetime.now(timezone.utc)
    new_lines = (["", f"## {title}", "", f"{check_program.WALK_CATEGORY_TAG}{category}"]
                 + [f"{check_program.WALK_WAITS_ON_TAG} {each}" for each in waits_on]
                 + [f"{check_program.WALK_FIRST_ENTERED_TAG} {now.astimezone().date().isoformat()}", ""]
                 + [line for flagged in flagged_lines for line in (flagged, "")]
                 + [CASE_AGAINST_PLACEHOLDER, ""])
    new_text = walk_finder.approval_walk_document_text_with_lines_added_after_whole_item(text, unit, new_lines, parser)
    unnumbered = walk_finder.approval_walk_unit_is_unnumbered_item
    if (sum(map(unnumbered, walk_finder.item_unit_spans(new_text, parser)))
            != sum(map(unnumbered, walk_finder.item_unit_spans(text, parser))) + 1):
        raise Refused(NO_UNNUMBERED_ITEMS_MESSAGE.format(document=document, whole=whole))
    document.write_text(new_text, encoding="utf-8")
    walk_finder.append_to_minutes(minutes, [REPLANNED_MINUTES_LINE.format(
        date=now.strftime("%Y-%m-%d"), title=walk_finder.text_wrapped_as_markdown_code_span(title), whole=whole)])
    question_check = load_module("walk_me_through_agent_question_to_user_outside_approval_walk_items_refusal_stop_hook",
                                 QUESTION_CHECK_HOOK_FILE)
    new_units = walk_finder.item_unit_spans(new_text, parser)
    _, waiting_units = walk_finder.waiting_item_units(document, value, numbers, total, parser, all_units=new_units)
    pages = walk_finder.newest_item_page_link_per_item_from_walk_minutes(minutes.read_text(encoding="utf-8"), parser)
    closing, _ = question_check.closing_lines(pages, minutes.name[:-len(walk_finder.MINUTES_SUFFIX)], new_text,
                                              new_units, waiting_units, parser, numbers, str(int(total) + 1))
    values = {"title": title, "document": document, "whole": whole, "closing_lines": "\n".join(closing),
              "closing_lines_named": (question_check.SEVERAL_CLOSING_LINES_NAMED if numbers[1:]
                                      else question_check.ONE_CLOSING_LINE_NAMED),
              "not_in_backticks": question_check.current_item_hook.NOT_IN_BACKTICKS}
    return [line.format(**values) for line in DONE_LINES]


def main(argv=None):
    check_program = load_module("walk_me_through_answer_added_texts_cold_read_fast_read_check_and_close",
                                WALK_CHECK_PROGRAM)
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--cwd", default=os.getcwd(), help="a directory in the walk's checkout")
    parser.add_argument("--title", required=True, help="the point of the question, the item's heading")
    parser.add_argument("--category", required=True, choices=check_program.WALK_CATEGORIES,
                        help="how soon the item's work must happen")
    parser.add_argument("--waits-on", action="append", default=[], metavar="TITLE",
                        help="the heading, without `## ` or `Item N of M: `, of an item this one must follow")
    parser.add_argument("--flagged-line", action="append", required=True, metavar="LINE",
                        help="a line of the flagged text, word for word, as the question check printed it")
    arguments = parser.parse_args(argv)
    try:
        print("\n".join(insert(arguments.cwd, arguments.title, arguments.category, arguments.waits_on,
                               arguments.flagged_line)))
    except Refused as refusal:
        print(f"{PROGRAM}: {refusal.args[0]}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
