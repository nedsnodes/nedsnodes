#!/usr/bin/env python3
"""Print what the user said in every agent-session whose dialog names an approval-walk item's title, and every
walk-minutes line that names it.

Usage:
  walk-me-through-approval-walk-item-title-search-user-messages-in-session-dialogs-and-lines-in-walk-minutes-print.py
      --title TITLE [--title TITLE]... --item-number N [--item-number N]...

The walk check program's pre-show step, approval-walk-waiting-item-cold-read-fast-read of
walk-me-through-answer-added-texts-cold-read-fast-read-check-and-close.py beside this program, runs this before each
item is shown, giving the item's title, each title an earlier read text of the item had, and the item's numbers.

WHAT IT SEARCHES. The log-store's session dialogs,
session-dialogs/<machine>/<project-key>/*-dialog-complete.md, and the walk-minutes files, *-minutes.md, in the
log-store's walk/ and in /home/nedlern/agents/*/docs/walk/, those of the walk/ directories that exist. A line names
a title when it holds the title, in any case and with no letter or digit right after it, where it reads as one: after
a running count as the walk finder reads one, as in "Item 6 of 27: <title>" or "**Items 9.1, 9.2 of 35**: <title>",
in quotes, or as a whole heading or list line, its `#`, `-` or `1.` and emphasis marks allowed. A title of fewer than
four words, such as "The fix", is too common for that, so it names one only after a running count that names one of
the item's own numbers.

WHAT IT PRINTS. For each agent-session whose dialog names a title, newest first, each message the user typed in it,
the whole agent-session and not only near the title, since the user's ruling can come before the title is named;
each after an excerpt of the agent message it answers, with the dialog's file and line, or the transcript's when
the dialog does not hold the message. Messages are told from the agent's and from a program's prompts by
search-user-messages-in-transcripts.py's speaker test, so an agent-session in which the user typed nothing, one a
program started, is skipped and counted in the first line printed. An agent-session whose transcript is not in the
log-store gets one line naming its dialog, for the agent to read. Several messages the user typed in a row follow
one excerpt of the agent message before them. Then each walk-minutes line that names a title, with its file and line.

FROM THE MAC. When the log-store is not on this machine and this machine is not ned-box, ned-box's copy of this
program runs over ssh, as scripts/log-store-past-discussions-regex-search-newest-first.py does.

Exit 2 when anything could not be searched, even when something was found, each failure named on stderr by a line
opening FAILED; otherwise 0 when something was found and 3 when nothing was, after the line
APPROVAL_WALK_ITEM_TITLE_SEARCH_OUTPUT_FORMAT_VERSION_STDERR_LINE_TEMPLATE on stderr, which names the version of
what this copy prints, so that a caller can tell an older copy's search apart.

Environment, for the tests:
  LOG_STORE_PAST_DISCUSSIONS_SEARCH_LOG_STORE_ROOT_OVERRIDE  the log-store's root
  LOG_STORE_PAST_DISCUSSIONS_SEARCH_RIPGREP_PROGRAM_OVERRIDE  the rg program
  WALK_ME_THROUGH_AGENT_HOMES_DIRECTORY_OVERRIDE             the directory holding the agent-homes
"""

import argparse
import base64
import importlib.util
import json
import os
import re
import stat
import sys
from pathlib import Path

PROGRAM_PATH = Path(__file__).resolve()
SEARCH_PROGRAM_FILE = PROGRAM_PATH.parents[3] / "scripts" / "log-store-past-discussions-regex-search-newest-first.py"
EXTRACTOR_PATH = PROGRAM_PATH.parents[3] / "scripts" / "handoff-extract-conversation.py"
WALK_FINDER_FILE = PROGRAM_PATH.with_name("walk-me-through-approval-walk-minutes-and-walk-document-item-finder-common.py")
NED_BOX_PROGRAM_PATH = f"/home/nedlern/Projects/nedsnodes/nn-systems/skills/walk-me-through/{PROGRAM_PATH.name}"
DEFAULT_AGENT_HOMES_DIRECTORY = Path("/home/nedlern/agents")
AGENT_HOMES_DIRECTORY_OVERRIDE_ENVIRONMENT_VARIABLE = "WALK_ME_THROUGH_AGENT_HOMES_DIRECTORY_OVERRIDE"
WALK_MINUTES_GLOB = "*-minutes.md"
SHORT_TITLE_WORDS = 4
AGENT_EXCERPT_CHARACTERS = 300

EXIT_FOUND = 0
# Not 1, which Python exits with on an uncaught exception, so that a crash is never read as nothing found.
EXIT_NOTHING_FOUND = 3
EXIT_FAILED = 2
# Raise it whenever a change to this program changes what a search finds or prints.
APPROVAL_WALK_ITEM_TITLE_SEARCH_OUTPUT_FORMAT_VERSION = 1
APPROVAL_WALK_ITEM_TITLE_SEARCH_OUTPUT_FORMAT_VERSION_STDERR_LINE_TEMPLATE = "title search output format {version}"
FAILURES_CLOSING_LINE = (
    "The user's messages printed on stdout are real, but those in the records the FAILED lines name are missing, and "
    "may decide the approval-walk item whose title was searched for.\n"
    "Tell the user what each FAILED line says, word for word, and do not show the item until this search runs "
    "without a FAILED line.")


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    # The extractor's dataclasses look their module up in sys.modules while it loads.
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


search = load_module("log_store_past_discussions_regex_search_newest_first", SEARCH_PROGRAM_FILE)
walk_finder = load_module("walk_me_through_approval_walk_minutes_and_walk_document_item_finder_common",
                          WALK_FINDER_FILE)


def title_matcher(title, numbers):
    """A function telling whether a line names title as a title; see the module's WHAT IT SEARCHES."""
    # Not \b, which needs a word character before it, so that a title ending in punctuation still ends here; and
    # not (?!\w), which rejects a title closed by underscore emphasis, as `_The fix_`. Underscores end the title only
    # when no letter or digit follows them, so `Fix foo` does not match in `Fix foo_bar`.
    escaped = re.escape(title) + r"(?!_*[^\W_])"
    # The running count as the walk finder reads one, its bold closing before or after the count's `:`.
    item_form = re.compile(rf"\bitems?\s+(?P<numbers>{walk_finder.NUMBER_LIST})(?:\s+of\s+\d+)?[*_]*\s*[:,.]?\s*"
                           rf"[*_\"“]*\s*" + escaped, re.IGNORECASE)
    if len(title.split()) < SHORT_TITLE_WORDS:
        def names(line):
            for match in item_form.finditer(line):
                try:
                    if set(walk_finder.expand_numbers(match["numbers"])) & set(numbers):
                        return True
                except walk_finder.UnusableRange:
                    continue
            return False
        return names
    quoted = r"[\"“'‘]\s*" + escaped + r"\s*[\"”'’]"
    whole_line = r"^\s*(?:#+|[-*+]|\d+[.)])?\s*[*_]*" + escaped + r"[*_]*\s*[.:]?\s*$"
    pattern = re.compile("|".join([item_form.pattern, quoted, whole_line]), re.IGNORECASE)
    return lambda line: pattern.search(line) is not None


def ripgrep_lines(titles, paths, glob, failures):
    """[(path, line number, line)] of each line in paths' files matching glob that holds one of titles, any case."""
    if not paths:
        return []
    found = []
    for title in titles:
        command = search.ripgrep_command(["--json", "--fixed-strings", "--glob", glob], title, paths)
        for raw in search.run_ripgrep(command, failures).splitlines():
            try:
                message = json.loads(raw)
            except ValueError:
                continue
            if message.get("type") != "match":
                continue
            data = message["data"]
            found.append((ripgrep_json_text(data["path"]), data["line_number"],
                          ripgrep_json_text(data["lines"]).rstrip("\n")))
    return sorted(set(found))


def ripgrep_json_text(field):
    """The text of a field of ripgrep's JSON output, which holds base64 "bytes" instead of "text" when the file's
    name or line is not valid UTF-8."""
    if "text" in field:
        return field["text"]
    return base64.b64decode(field["bytes"]).decode("utf-8", "replace")


def transcript_turns(transcript):
    """[(voice, text, line number)] of each turn in one transcript, "user" only for a message the user typed, as
    the speaker test tells them. Raises OSError when the transcript cannot be read."""
    reader = search.speaker_test_in_this_process().TurnReader()
    turns = []
    with transcript.open("r", errors="replace") as handle:
        for number, line in enumerate(handle, 1):
            try:
                record = json.loads(line)
            except ValueError:
                continue
            # A subagent's records belong to its own transcript; its task, written by the agent, reads as typed.
            if not isinstance(record, dict) or record.get("isSidechain"):
                continue
            turn = reader.turn(record)
            if turn is not None:
                turns.append((turn[0], turn[1], number))
    return turns


def dialog_lines_by_transcript_line(transcript, dialog_text):
    """{transcript line number: the dialog line where that record's turn text starts}, from the session dialog
    extractor's own turns, or {} when dialog_text is not what the extractor renders from the transcript now, as
    when the transcript grew after the dialog was written; a turn the dialog leaves out has no entry."""
    extractor = load_module("handoff_extract_conversation", EXTRACTOR_PATH)
    turns, report = extractor.complete_dialog_turns_and_report(transcript)
    rendered = extractor.render_companion(turns, report)
    if not dialog_text.startswith(rendered + "\n"):
        return {}
    turn_lines = [len("\n".join(extractor.render_turn(turn)).split("\n")) for turn in turns]
    # render_turn puts a user or agent turn's text two lines below its heading.
    line = len(rendered.split("\n")) - sum(turn_lines) + 3
    placed = {}
    for turn, count in zip(turns, turn_lines):
        if "line_index" in turn:
            placed[turn["line_index"] + 1] = line
        line += count
    return placed


def flat(text):
    return " ".join(text.split())


def session_lines(root, dialog, title_lines, failures):
    """The lines printed for one agent-session's dialog, or None when the user typed nothing in it."""
    machine, project_key = search.session_parts(dialog, root)
    transcript = search.session_transcript(root, {"path": str(dialog), "machine": machine,
                                                  "project_key": project_key})
    seat = search.seat_from_project_key(project_key)
    named_at = (f"Agent-session {transcript.stem} ({', '.join(filter(None, [seat, machine]))}), its dialog naming the "
                f"title at line(s) {', '.join(str(number) for number in title_lines)}")
    try:
        turns = transcript_turns(transcript)
    except FileNotFoundError:
        # Some dialogs outlive their transcripts in the log-store; no rerun brings the transcript back.
        return [f"{named_at}: its transcript {transcript} is not in the log-store, so the user's messages in it cannot "
                f"be told from programs' prompts here; read its \"## User\" turns in {dialog} yourself."]
    except OSError as error:
        failures.append(f"could not read the transcript {transcript} of the session dialog {dialog}, which names "
                        f"the item's title, so the user's messages in it were not printed: {error}")
        return None
    if not any(voice == "user" for voice, _, _ in turns):
        return None
    try:
        placed = dialog_lines_by_transcript_line(transcript, dialog.read_bytes().decode("utf-8", "replace"))
    except OSError as error:
        failures.append(f"could not read the session dialog {dialog} after ripgrep searched it, so its messages are "
                        f"cited by the transcript's lines: {error}")
        placed = {}
    printed = [f"{named_at}:"]
    agent = shown_agent = None
    for voice, text, number in turns:
        line = placed.get(number)
        cited = f"{dialog}:{line}" if line else f"{transcript}:{number}"
        if voice != "user":
            agent = (cited, text)
            continue
        # Several messages the user typed in a row answer one agent message, shown once before them.
        if agent and agent is not shown_agent:
            shown = flat(agent[1])
            if len(shown) > AGENT_EXCERPT_CHARACTERS:
                shown = "…" + shown[-AGENT_EXCERPT_CHARACTERS:]
            printed.append(f"  agent  {agent[0]}  {shown}")
        elif not agent and not printed[1:]:
            printed.append("  agent  (no agent message before it)")
        shown_agent = agent
        printed.append(f"  user   {cited}  {text.strip()}")
    return printed


def walk_directories(root, agent_homes, failures):
    """The log-store's walk/ and each agent-home's docs/walk/ that exist; one that cannot be looked at, or an
    agent-homes directory that is missing or cannot be listed, is a failure, so its walk-minutes are never left out
    unseen. An agent-home without docs/walk/ is the ordinary case and is skipped."""
    try:
        homes = sorted(entry.path for entry in os.scandir(agent_homes))
    except (FileNotFoundError, NotADirectoryError):
        failures.append(f"there is no agent-homes directory at {agent_homes}, so no agent-home's walk-minutes "
                        f"were searched")
        homes = []
    except OSError as error:
        failures.append(f"could not list the agent-homes directory {agent_homes}, so no agent-home's walk-minutes "
                        f"were searched: {error}")
        homes = []
    found = []
    for directory in [root / "walk", *(Path(home) / "docs" / "walk" for home in homes)]:
        try:
            mode = directory.stat().st_mode
        except (FileNotFoundError, NotADirectoryError):
            continue
        except OSError as error:
            failures.append(f"could not look at {directory}, so its walk-minutes were not searched: {error}")
            continue
        if stat.S_ISDIR(mode):
            found.append(directory)
    return found


def found_lines(root, agent_homes, titles, numbers, failures):
    """(lines to print, whether anything was found)."""
    matchers = [title_matcher(title, numbers) for title in titles]
    dialogs_directory = root / search.SESSION_DIALOGS
    if not dialogs_directory.is_dir():
        failures.append(f"the log-store has no {dialogs_directory}, so no session dialog was searched")
    dialog_hits = ripgrep_lines(titles, [dialogs_directory] if dialogs_directory.is_dir() else [],
                                "*" + search.SESSION_DIALOG_FILE_NAME_SUFFIX, failures)
    minutes_hits = ripgrep_lines(titles, walk_directories(root, agent_homes, failures), WALK_MINUTES_GLOB, failures)
    named = {}
    for path, number, text in dialog_hits:
        if any(names(text) for names in matchers):
            named.setdefault(Path(path), []).append(number)
    sessions, skipped = [], 0
    for dialog, title_lines in named.items():
        printed = session_lines(root, dialog, title_lines, failures)
        if printed is None:
            skipped += 1
            continue
        try:
            newest = search.session_transcript(root, {"path": str(dialog), "machine": search.session_parts(
                dialog, root)[0], "project_key": search.session_parts(dialog, root)[1]}).stat().st_mtime
        except OSError:
            newest = 0
        sessions.append((newest, printed))
    sessions.sort(key=lambda session: session[0], reverse=True)
    quoted = ", ".join(f'"{title}"' for title in titles)
    lines = [f"The user's words where the item's title, {quoted}, was named before: {len(sessions)} agent-session(s), "
             f"newest first, each message the user typed in it after the end of the agent message it answers"
             + (f"; {skipped} agent-session(s) in which the user typed nothing, such as those a program started, "
                f"left out" if skipped else "") + "."]
    for _, printed in sessions:
        lines += printed
    minutes = [(path, number, text) for path, number, text in minutes_hits
               if any(names(text) for names in matchers)]
    lines.append(f"Walk-minutes lines naming the title: {len(minutes)}.")
    lines += [f"  {path}:{number}  {text}" for path, number, text in minutes]
    return lines, bool(sessions or minutes)


def argument_parser():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--title", action="append", required=True, help="a title the item has or had; repeatable")
    parser.add_argument("--item-number", action="append", required=True,
                        help="one of the item's numbers, such as 9.2; repeatable")
    return parser


def main(argv=None):
    arguments = sys.argv[1:] if argv is None else argv
    parsed = argument_parser().parse_args(arguments)
    root_override = os.environ.get(search.ROOT_OVERRIDE)
    root = Path(root_override) if root_override else search.DEFAULT_LOG_STORE_ROOT
    if not root.is_dir():
        if search.this_machine() != search.NED_BOX_HOSTNAME:
            return search.run_on_ned_box_over_ssh(list(arguments), NED_BOX_PROGRAM_PATH)
        print(f"FAILED: there is no log-store at {root} on {search.this_machine()}, so no session dialog or "
              f"walk-minutes file was searched for the item's title.\n"
              f"The log-store is on ned-box at {search.DEFAULT_LOG_STORE_ROOT}: tell the user it is missing there.",
              file=sys.stderr)
        return EXIT_FAILED
    agent_homes = Path(os.environ.get(AGENT_HOMES_DIRECTORY_OVERRIDE_ENVIRONMENT_VARIABLE) or DEFAULT_AGENT_HOMES_DIRECTORY)
    failures = []
    try:
        lines, found = found_lines(root, agent_homes, [title.strip() for title in parsed.title if title.strip()],
                                   parsed.item_number, failures)
    except search.RipgrepMissing as missing:
        print(f"FAILED: ripgrep ({missing}) is not installed on {search.this_machine()}, so no session dialog or "
              f"walk-minutes file was searched for the item's title.\n"
              f"Ask the user to install it there, with `sudo apt install ripgrep`; an agent cannot run sudo.",
              file=sys.stderr)
        return EXIT_FAILED
    print("\n".join(lines))
    for failure in failures:
        print(f"FAILED: {failure}", file=sys.stderr)
    if failures:
        print(FAILURES_CLOSING_LINE, file=sys.stderr)
        return EXIT_FAILED
    print(APPROVAL_WALK_ITEM_TITLE_SEARCH_OUTPUT_FORMAT_VERSION_STDERR_LINE_TEMPLATE.format(version=APPROVAL_WALK_ITEM_TITLE_SEARCH_OUTPUT_FORMAT_VERSION), file=sys.stderr)
    return EXIT_FOUND if found else EXIT_NOTHING_FOUND


if __name__ == "__main__":
    sys.exit(main())
