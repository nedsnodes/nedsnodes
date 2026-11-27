#!/usr/bin/env python3
"""The last line a search program prints: its name, then `#search_complete#` or `#search_incomplete#`.

The /find-info skill tells an agent to read this line, not a search program's other wording, to tell a
search that failed or ran only in part from one that found nothing. The log-store search, the locator, the
approval search and the backup search print it; the locator also reads the backup search's.

Load it by path, under the snake_case form of its file name:

    spec = importlib.util.spec_from_file_location(
        "search_program_ending_search_complete_or_search_incomplete_hashtag_line_common", <path>)
"""

SEARCH_COMPLETE_HASHTAG = "#search_complete#"
SEARCH_INCOMPLETE_HASHTAG = "#search_incomplete#"


def search_ending_hashtag_line(program_name, not_searched=None):
    """The line, with what was not searched after the hashtag when the search was incomplete."""
    if not_searched is None:
        return f"{program_name}: {SEARCH_COMPLETE_HASHTAG}"
    return f"{program_name}: {SEARCH_INCOMPLETE_HASHTAG} {not_searched}"


def search_was_complete_by_ending_hashtag_line(program_name, line):
    """True or False when line is program_name's ending line, saying whether its search was complete; else None."""
    opening = f"{program_name}: "
    if not line.startswith(opening):
        return None
    rest = line[len(opening):]
    if rest.rstrip("\n") == SEARCH_COMPLETE_HASHTAG:
        return True
    if rest.startswith(SEARCH_INCOMPLETE_HASHTAG):
        return False
    return None
