#!/usr/bin/env python3
"""Print what the user said in every agent-session whose dialog names an approval-walk item's title, and every
walk-minutes line that names it.

Usage:
  walk-me-through-approval-walk-item-title-search-user-messages-in-session-dialogs-and-lines-in-walk-minutes-print.py
      --title TITLE [--title TITLE]... --item-number N [--item-number N]...

The walk check program's pre-show step, approval-walk-waiting-item-cold-read-fast-read, runs this before each item
is shown, giving the item's title, each title an earlier read text of the item had, and the item's numbers.

WHAT IT SEARCHES. The log-store's session dialogs,
session-dialogs/<machine>/<project-key>/*-dialog-complete.md, and the walk-minutes files, *-minutes.md, in the
log-store's walk/ and in /home/nedlern/agents/*/docs/walk/. A line names a title when it holds the title where it
reads as one: after "Item <number>", in quotes, or as a whole heading or list line. A title of fewer than
SHORT_TITLE_WORDS words, such as "The fix", is too common for that, so it names one only right after
"Item <number>" with one of the item's own numbers.

WHAT IT PRINTS. For each agent-session whose dialog names a title, newest first, each message the user typed in it,
the whole agent-session and not only near the title, since the user's ruling can come before the title is named;
each after an excerpt of the agent message it answers, with the dialog's file and line, or the transcript's when
the dialog does not hold the message. Messages are told from the agent's and from a program's prompts by
search-user-messages-in-transcripts.py's speaker test, so an agent-session in which the user typed nothing, one a
program started, is skipped and counted. Then each walk-minutes line that names a title, with its file and line.

FROM THE MAC. When the log-store is not on this machine and this machine is not ned-box, ned-box's copy of this
program runs over ssh, as scripts/log-store-past-discussions-regex-search-newest-first.py does.

Exit 0 when something was found, 1 when nothing was, and 2 when anything could not be searched, each failure named
on stderr by a line opening FAILED.

Environment, for the tests:
  LOG_STORE_PAST_DISCUSSIONS_SEARCH_LOG_STORE_ROOT_OVERRIDE  the log-store's root
  LOG_STORE_PAST_DISCUSSIONS_SEARCH_RIPGREP_PROGRAM_OVERRIDE  the rg program
  WALK_ME_THROUGH_AGENT_HOMES_DIRECTORY_OVERRIDE             the directory holding the agent-homes
"""

import argparse
import importlib.util
import json
import os
import re
import sys
from pathlib import Path

PROGRAM_PATH = Path(__file__).resolve()
SEARCH_PROGRAM_FILE = PROGRAM_PATH.parents[3] / "scripts" / "log-store-past-discussions-regex-search-newest-first.py"
NED_BOX_PROGRAM_PATH = f"/home/nedlern/Projects/nedsnodes/nn-systems/skills/walk-me-through/{PROGRAM_PATH.name}"
DEFAULT_AGENT_HOMES_DIRECTORY = Path("/home/nedlern/agents")
AGENT_HOMES_DIRECTORY_OVERRIDE_ENVIRONMENT_VARIABLE = "WALK_ME_THROUGH_AGENT_HOMES_DIRECTORY_OVERRIDE"
WALK_MINUTES_GLOB = "*-minutes.md"
SHORT_TITLE_WORDS = 4
AGENT_EXCERPT_CHARACTERS = 300

EXIT_FOUND = 0
EXIT_NOTHING_FOUND = 1
EXIT_FAILED = 2


def load_search():
    spec = importlib.util.spec_from_file_location("log_store_past_discussions_regex_search_newest_first",
                                                  SEARCH_PROGRAM_FILE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


search = load_search()


def title_pattern(title, numbers):
    """The regular expression for a line that names title as a title; see the module's WHAT IT SEARCHES."""
    escaped = re.escape(title)
    numbered = r"[\d.]+"
    if len(title.split()) < SHORT_TITLE_WORDS:
        numbered = "(?:" + "|".join(re.escape(number) for number in numbers) + r")(?![\d.]*\d)"
    item_form = (r"\bitems?\s+(?:[\d.]+\s+(?:and|to)\s+)*" + numbered
                 + r"(?:\s+(?:and|to)\s+[\d.]+)*(?:\s+of\s+\d+)?\s*[:,]?\s*[*_\"“]*\s*" + escaped)
    if len(title.split()) < SHORT_TITLE_WORDS:
        return re.compile(item_form, re.IGNORECASE)
    quoted = r"[\"“'‘]\s*" + escaped + r"\s*[\"”'’]"
    whole_line = r"^\s*(?:#+|[-*+]|\d+[.)])?\s*[*_]*" + escaped + r"[*_]*\s*[.:]?\s*$"
    return re.compile("|".join([item_form, quoted, whole_line]), re.IGNORECASE)


def ripgrep_lines(titles, paths, glob, failures):
    """[(path, line number, line)] of each line in paths' files matching glob that holds one of titles, any case."""
    if not paths:
        return []
    found = []
    for title in titles:
        command = search.ripgrep_command(["--json", "--fixed-strings", "--glob", glob], title, paths)
        command[0] = os.environ.get(search.RIPGREP_OVERRIDE) or "rg"
        for raw in search.run_ripgrep(command, failures).splitlines():
            try:
                message = json.loads(raw)
            except ValueError:
                continue
            if message.get("type") != "match":
                continue
            data = message["data"]
            found.append((data["path"]["text"], data["line_number"], data["lines"]["text"].rstrip("\n")))
    return sorted(set(found))


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


def dialog_line(dialog_lines, heading, text, start):
    """(line number in the dialog of the turn under heading whose text opens as text does, or None, and where to
    look for the next turn); turns are looked for in order, so a repeated message takes its own place."""
    first = text.strip().split("\n", 1)[0]
    for index in range(start, len(dialog_lines) - 2):
        if dialog_lines[index] == heading and dialog_lines[index + 2] == first:
            return index + 3, index + 3
    return None, start


def flat(text):
    return " ".join(text.split())


def session_lines(root, dialog, title_lines, failures):
    """The lines printed for one agent-session's dialog, or None when the user typed nothing in it."""
    machine, project_key = search.session_parts(dialog, root)
    transcript = search.session_transcript(root, {"path": str(dialog), "machine": machine,
                                                  "project_key": project_key})
    try:
        turns = transcript_turns(transcript)
    except OSError as error:
        failures.append(f"could not read the transcript {transcript} of the session dialog {dialog}, which names "
                        f"the item's title, so the user's messages in it were not printed: {error}")
        return None
    if not any(voice == "user" for voice, _, _ in turns):
        return None
    try:
        lines = dialog.read_bytes().decode("utf-8", "replace").split("\n")
    except OSError as error:
        failures.append(f"could not read the session dialog {dialog} after ripgrep searched it, so its messages are "
                        f"cited by the transcript's lines: {error}")
        lines = []
    seat = search.seat_from_project_key(project_key)
    printed = [f"Agent-session {transcript.stem} ({', '.join(filter(None, [seat, machine]))}), its dialog naming the "
               f"title at line(s) {', '.join(str(number) for number in title_lines)}:"]
    agent = shown_agent = None
    start = 0
    for voice, text, number in turns:
        heading = "## User" if voice == "user" else "## Agent"
        line, start = dialog_line(lines, heading, text, start)
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


def found_lines(root, agent_homes, titles, numbers, failures):
    """(lines to print, whether anything was found)."""
    patterns = [title_pattern(title, numbers) for title in titles]
    dialogs_directory = root / search.SESSION_DIALOGS
    walk_directories = [directory for directory in [root / "walk", *sorted(agent_homes.glob("*/docs/walk"))]
                        if directory.is_dir()]
    if not dialogs_directory.is_dir():
        failures.append(f"the log-store has no {dialogs_directory}, so no session dialog was searched")
    dialog_hits = ripgrep_lines(titles, [dialogs_directory] if dialogs_directory.is_dir() else [],
                                "*" + search.SESSION_DIALOG_FILE_NAME_SUFFIX, failures)
    minutes_hits = ripgrep_lines(titles, walk_directories, WALK_MINUTES_GLOB, failures)
    named = {}
    for path, number, text in dialog_hits:
        if any(pattern.search(text) for pattern in patterns):
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
               if any(pattern.search(text) for pattern in patterns)]
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
        print(f"FAILED: there is no log-store at {root} on {search.this_machine()}, so nothing was searched.",
              file=sys.stderr)
        return EXIT_FAILED
    agent_homes = Path(os.environ.get(AGENT_HOMES_DIRECTORY_OVERRIDE_ENVIRONMENT_VARIABLE) or DEFAULT_AGENT_HOMES_DIRECTORY)
    failures = []
    try:
        lines, found = found_lines(root, agent_homes, [title.strip() for title in parsed.title if title.strip()],
                                   parsed.item_number, failures)
    except search.RipgrepMissing as missing:
        print(f"FAILED: ripgrep ({missing}) is not installed on {search.this_machine()}, so nothing was searched.\n"
              f"Install it: sudo apt install ripgrep.", file=sys.stderr)
        return EXIT_FAILED
    print("\n".join(lines))
    for failure in failures:
        print(f"FAILED: {failure}", file=sys.stderr)
    if failures:
        return EXIT_FAILED
    return EXIT_FOUND if found else EXIT_NOTHING_FOUND


if __name__ == "__main__":
    sys.exit(main())
