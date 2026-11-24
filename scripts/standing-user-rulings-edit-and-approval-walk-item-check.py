#!/usr/bin/env python3
"""Look up the user's standing user-rulings and words in the standing user-rulings store, by tags and key phrases.

Usage:
  scripts/standing-user-rulings-edit-and-approval-walk-item-check.py lookup
      [--tag TAG ...] [--phrase PHRASE ...] [--limit N] [--log-store DIR]

  --tag     a tag as the store writes it: "GHI <number>", "PR <number>", "task <agent-seat> <number>",
            "nn-systems/<system>/" or a repository path. Matched exactly. Repeat for more.
  --phrase  a key phrase, matched as a phrase, case-insensitively, in his words and in the agent message he
            was answering. Repeat for more.
  --limit   print at most N entries; 0, the default, prints every match.
  --log-store  default /home/nedlern/nedsnodes-logs, the log-store on ned-box.

This is the lookup of the ruling-agent design, docs/issues/2118-ruling-agent-keeps-user-rulings-checks-approval-
walk.md, section "The store, the lookup and the index file": tags and key phrases in, standing entries out, newest
first. It opens the store read-only and needs no model; judging whether an entry bears on a question is
ruling-agent's prompt's work, not this program's. The write commands and the approval-walk item check that the
design gives this file are later parts of its build order.

An entry matches when it carries any given tag or contains any given phrase. Only standing entries are returned.
When an entry found is one of a pair that ruling-agent's prompt linked, the other entry of the pair is returned
too, when it is standing, marked with the pair's id and state.

OUTPUT. JSON Lines on stdout. The first line: {"lookup_store": ..., "tags": [...], "phrases": [...],
"standing_entries_matched": N, "entries_printed": M}. Then one line per entry, newest first: its id
("entry-<number>", as the index file names it), kind, said_at_utc, link, agent_seat, tags, matched_by (each
"tag <tag>" or "phrase <phrase>" that found it; empty for an entry returned only as the other of a pair), pair
(null, or {"pair_id", "state", "other_entry"}), text and agent_message_answered.

EXIT. 0 when the lookup ran, whether or not anything matched. 2 when it could not run: no tag or phrase was
given, a phrase is empty, or the store cannot be opened or read; a line starting FAILED on stderr says which,
followed by what to do.
"""

import argparse
import importlib.util
import json
import sqlite3
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
_index_program_spec = importlib.util.spec_from_file_location(
    "standing_user_rulings_index_program",
    HERE / "standing-user-rulings-store-add-from-transcripts-and-walk-minutes-then-index-file-and-anchor-list-for-hooks-write.py")
index_program = importlib.util.module_from_spec(_index_program_spec)
_index_program_spec.loader.exec_module(index_program)

EXIT_OK, EXIT_COULD_NOT_RUN = 0, 2

NOTHING_TO_LOOK_UP_INSTRUCTIONS = (
    "Run it again with one or more --tag or --phrase options, each repeatable, for example:\n"
    f"  python3 {Path(__file__).resolve()} lookup --tag 'GHI 2118' --phrase 'ruling-agent'")
EMPTY_PHRASE_INSTRUCTIONS = (
    "Run it again with every --phrase holding at least one word; drop each --phrase that is empty or only spaces.")
STORE_MISSING_INSTRUCTIONS_TEMPLATE = (
    "The index program has not yet filled a store in this lookup's log-store, {log_store}. Run\n"
    f"  python3 {Path(index_program.__file__).resolve()} --log-store {{log_store}}\n"
    "and do what it prints if it fails, then run this lookup again.")
STORE_UNREADABLE_INSTRUCTIONS = (
    "Stop the work that needed the lookup and tell the user: \"The standing user-rulings lookup cannot read its "
    "store:\", followed by the FAILED line above. Do not search the store or the transcripts by hand in its place, because a hand search misses what "
    "the lookup would find without saying so.\n"
    "A subagent passes that sentence to the agent that dispatched it instead.")


class CouldNotRun(Exception):
    def __init__(self, reason, instructions):
        super().__init__(reason)
        self.reason, self.instructions = reason, instructions


def store_path(log_store):
    return Path(log_store) / index_program.STORE_DIRECTORY_NAME / index_program.STORE_FILE_NAME


LOG_STORE_MISSING_INSTRUCTIONS = (
    "Check the --log-store path for a typing mistake and run this lookup again; leave --log-store out to use the "
    "log-store on ned-box.")


def open_store_read_only(path, log_store):
    if not Path(log_store).is_dir():
        raise CouldNotRun(f"the --log-store directory {log_store} does not exist", LOG_STORE_MISSING_INSTRUCTIONS)
    if not path.is_file():
        raise CouldNotRun(f"the standing user-rulings store {path} does not exist",
                          STORE_MISSING_INSTRUCTIONS_TEMPLATE.format(log_store=log_store))
    try:
        connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        connection.execute("SELECT 1 FROM entries LIMIT 1").fetchall()
    except sqlite3.Error as error:
        raise CouldNotRun(f"the standing user-rulings store {path} cannot be read: {error}",
                          STORE_UNREADABLE_INSTRUCTIONS) from error
    return connection


def full_text_phrase(phrase):
    return '"' + phrase.replace('"', '""') + '"'


def entries_matched(connection, tags, phrases):
    """Return {entry_id: [what matched it, ...]} for the standing entries the tags and phrases find."""
    matched = {}
    for tag in tags:
        for (entry_id,) in connection.execute(
                "SELECT entry_id FROM entry_tags JOIN entries USING (entry_id) WHERE tag = ? AND state = ?",
                (tag, index_program.STATE_STANDING)):
            matched.setdefault(entry_id, []).append(f"tag {tag}")
    for phrase in phrases:
        for (entry_id,) in connection.execute(
                "SELECT entries.entry_id FROM entries_full_text JOIN entries ON entries.entry_id = entries_full_text.rowid "
                "WHERE entries_full_text MATCH ? AND entries.state = ?",
                (full_text_phrase(phrase), index_program.STATE_STANDING)):
            matched.setdefault(entry_id, []).append(f"phrase {phrase}")
    return matched


def pairs_of(connection, entry_ids):
    """Return {entry_id: (pair_id, state, other_entry_id)} for every pair an entry of entry_ids is in."""
    pairs = {}
    for pair_id, first, second, state in connection.execute(
            "SELECT pair_id, first_entry_id, second_entry_id, state FROM entry_pairs"):
        if first in entry_ids:
            pairs.setdefault(first, (pair_id, state, second))
        if second in entry_ids:
            pairs.setdefault(second, (pair_id, state, first))
    return pairs


def lookup(connection, tags, phrases):
    """Return the standing entries the tags and phrases find, with the other entry of each pair, newest first."""
    matched = entries_matched(connection, tags, phrases)
    pairs = pairs_of(connection, set(matched))
    others = {other for _, _, other in pairs.values() if other not in matched}
    if others:
        pairs.update(pairs_of(connection, others))
    wanted = set(matched) | others
    if not wanted:
        return []
    marks = ",".join("?" * len(wanted))
    rows = connection.execute(
        f"SELECT entry_id, kind, said_at_utc, source_path, source_line, agent_seat, text, agent_message_answered "
        f"FROM entries WHERE entry_id IN ({marks}) AND state = ? ORDER BY said_at_utc DESC, entry_id DESC",
        (*wanted, index_program.STATE_STANDING)).fetchall()
    tags_by_entry = {}
    for entry_id, tag in connection.execute(
            f"SELECT entry_id, tag FROM entry_tags WHERE entry_id IN ({marks}) ORDER BY tag", tuple(wanted)):
        tags_by_entry.setdefault(entry_id, []).append(tag)
    entries = []
    for entry_id, kind, said_at, source_path, source_line, agent_seat, text, answered in rows:
        pair = pairs.get(entry_id)
        entries.append({
            "id": f"entry-{entry_id}", "kind": kind, "said_at_utc": said_at,
            "link": index_program.link_to(source_path, source_line), "agent_seat": agent_seat,
            "tags": tags_by_entry.get(entry_id, []), "matched_by": matched.get(entry_id, []),
            "pair": None if pair is None else {"pair_id": pair[0], "state": pair[1], "other_entry": f"entry-{pair[2]}"},
            "text": text, "agent_message_answered": answered})
    return entries


def run_lookup(arguments):
    stdout = sys.stdout
    if not arguments.tag and not arguments.phrase:
        raise CouldNotRun("nothing to look up: no --tag or --phrase was given", NOTHING_TO_LOOK_UP_INSTRUCTIONS)
    if any(not phrase.strip() for phrase in arguments.phrase):
        raise CouldNotRun("a --phrase is empty", EMPTY_PHRASE_INSTRUCTIONS)
    path = store_path(arguments.log_store)
    connection = open_store_read_only(path, arguments.log_store)
    try:
        entries = lookup(connection, arguments.tag, arguments.phrase)
    except sqlite3.Error as error:
        raise CouldNotRun(f"the standing user-rulings store {path} cannot be read: {error}",
                          STORE_UNREADABLE_INSTRUCTIONS) from error
    finally:
        connection.close()
    printed = entries if arguments.limit == 0 else entries[:arguments.limit]
    stdout.write(json.dumps({"lookup_store": str(path), "tags": arguments.tag, "phrases": arguments.phrase,
                             "standing_entries_matched": len(entries), "entries_printed": len(printed)}) + "\n")
    for entry in printed:
        stdout.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return EXIT_OK


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    lookup_parser = commands.add_parser("lookup", help="tags and key phrases in, standing entries out, newest first")
    lookup_parser.add_argument("--tag", action="append", default=[])
    lookup_parser.add_argument("--phrase", action="append", default=[])
    lookup_parser.add_argument("--limit", type=int, default=0)
    lookup_parser.add_argument("--log-store", type=Path, default=index_program.DEFAULT_LOG_STORE)
    arguments = parser.parse_args(argv)
    if arguments.limit < 0:
        parser.error("--limit must be 0 or more")
    try:
        return run_lookup(arguments)
    except CouldNotRun as could_not_run:
        sys.stderr.write(f"FAILED: the standing user-rulings lookup did not run, and printed no entries: "
                         f"{could_not_run.reason}\n{could_not_run.instructions}\n")
        return EXIT_COULD_NOT_RUN


if __name__ == "__main__":
    sys.exit(main())
