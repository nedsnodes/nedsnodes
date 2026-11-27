#!/usr/bin/env python3
"""Look up the user's standing user-rulings and words in the standing user-rulings store, by tags and key phrases.

Usage:
  echo '{"tags": [...], "phrases": [...], "limit": N}' |
    scripts/standing-user-rulings-edit-and-approval-walk-item-check.py lookup [--log-store DIR] [--repository-checkout DIR]

INPUT. One JSON object on stdin, with no keys but these:
  tags     a list of tags as the store writes them: "GHI <number>", "PR <number>", "task <agent-seat> <number>",
           "nn-systems/<system>/" or a repository path, as the index file shows it. A tag the store kept under its
           name from before the project rename, such as "nc-systems/handoff/", matches under the name the index file
           shows, "nn-systems/handoff/".
  phrases  a list of key phrases, each matched as a phrase, case-insensitively, in his words and in the agent message
           he was answering.
  limit    a whole number, 0 or more: print this many entries at most, the highest scores, and after them the other
           entry of each pair a printed entry is in; 0, the default, prints every match.
At least one tag or phrase is needed; "tags" and "phrases" default to empty lists. A tag given twice, also under
its name from before the project rename, or a phrase given twice in any letter case, counts once, under the
spelling given first.
  --log-store  default /home/nedlern/nedsnodes-logs, the log-store on ned-box.
  --repository-checkout  default the checkout this file is in; its origin/main gives each stored tag the name the
            index file shows, as the index program's option of the same name does.

This is the lookup of the ruling-agent design, docs/issues/2118-ruling-agent-keeps-user-rulings-checks-approval-
walk.md, section "The store, the lookup and the index file": tags and key phrases in, standing entries out, highest
score first. It opens the store read-only and needs no model; judging whether an entry bears on a question is
ruling-agent's prompt's work, not this program's. The write commands and the approval-walk item check that the
design gives this file are later parts of its build order.

An entry matches when it carries any given tag or contains any given phrase. Only standing entries are returned.
When an entry found is in a pair that ruling-agent's prompt linked, the other entry of every such pair is returned
too, when it is standing, marked with the pair's id and state.

SCORE. Each entry's score is its relevance times its recency weight. Relevance is the sum, over the given tags and
phrases that matched the entry, of ln(N / n), where N is the number of standing entries in the store and n the
number of standing entries that tag or phrase finds, so a rare tag or phrase counts for more than a common one.
The recency weight is 1 at 7 days old (RECENCY_WEIGHT_IS_ONE_AT_AGE_DAYS) and halves every 42 days of age
(RECENCY_WEIGHT_HALF_LIFE_DAYS), rising the same way below 7 days; an entry younger than 48 hours
(RECENT_ENTRY_BOOST_WITHIN_HOURS) has it multiplied by 2 (RECENT_ENTRY_BOOST_FACTOR). An entry returned only as the
other of a pair has relevance 0 and score 0.

OUTPUT. JSON Lines on stdout. The first line: {"lookup_store": ..., "tags": [...], "phrases": [...],
"standing_entry_count_in_store": N,
"standing_entry_count_found_by_each_tag_and_phrase": {"tag <tag>" or "phrase <phrase>": n, ...},
"standing_entries_matched": M, "entries_printed": P}. Then one line per entry, highest score first, then newest
first: its id ("entry-<number>", as the index file names it), kind, said_at_utc, link, agent_seat, tags,
matched_by (each "tag <tag>" or "phrase <phrase>" that found it; empty for an entry returned only as the other of a
pair), ranking_score_from_relevance_and_recency (its score), relevance, recency_weight, pairs (a list, empty or of
{"pair_id", "state", "other_entry"}, one for each pair the entry is in), text and agent_message_answered. Tags are printed under the names the index file shows.

EXIT. 0 when the lookup ran, whether or not anything matched. 2 when it could not run: stdin is not a JSON object
of the keys above with the types above, no tag or phrase was given, a phrase is empty, the store cannot be opened
or read, or origin/main cannot be read in the repository checkout; a line starting FAILED on stderr says which,
followed by what to do.
"""

import argparse
import importlib.util
import datetime
import json
import math
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

# The user's figures, which the test checks: a week old weighs 1, three months old (13 weeks) about a quarter of
# that, and the last 48 hours more again.
RECENCY_WEIGHT_IS_ONE_AT_AGE_DAYS = 7
RECENCY_WEIGHT_HALF_LIFE_DAYS = 42
RECENT_ENTRY_BOOST_WITHIN_HOURS = 48
RECENT_ENTRY_BOOST_FACTOR = 2

# Messages to the agent follow docs/nedsnodes-wiki/nedsnodes-how-to-write-a-tool-message-to-agent-such-as-a-hook-refusal-or-script-error.md.
LOOKUP_INPUT_KEYS = ("tags", "phrases", "limit")
LOOKUP_INPUT_EXAMPLE = '{"tags": ["GHI 2118"], "phrases": ["ruling-agent"], "limit": 20}'
MALFORMED_INPUT_INSTRUCTIONS = (
    "Run it again with stdin holding one JSON object whose keys are among \"tags\" (a list of strings), "
    "\"phrases\" (a list of strings) and \"limit\" (a whole number, 0 or more), for example:\n"
    f"  echo '{LOOKUP_INPUT_EXAMPLE}' | python3 {Path(__file__).resolve()} lookup")
NOTHING_TO_LOOK_UP_INSTRUCTIONS = (
    "Run it again with one or more strings in \"tags\" or \"phrases\", for example:\n"
    f"  echo '{LOOKUP_INPUT_EXAMPLE}' | python3 {Path(__file__).resolve()} lookup")
EMPTY_PHRASE_INSTRUCTIONS = (
    "Run it again with every phrase holding at least one word; drop each phrase that is empty or only spaces.")
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


REPOSITORY_UNREADABLE_INSTRUCTIONS_TEMPLATE = (
    "The lookup needs origin/main to give each stored tag the name the index file shows. Run\n"
    "  git -C {checkout} fetch origin main\n"
    "then this lookup again; if origin/main still cannot be read, run it again with --repository-checkout naming "
    "another nedsnodes checkout on ned-box, such as /home/nedlern/Projects/nedsnodes.")
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


def find_standing_entries_by_tags_and_phrases_with_what_matched_each(connection, tags, phrases, tag_now):
    """Return {entry_id: [what matched it, ...]} for the standing entries the tags and phrases find.

    tag_now gives a stored tag the name the index file shows it under."""
    matched = {}
    stored_tags_by_tag_now = {}
    for (stored_tag,) in connection.execute("SELECT DISTINCT tag FROM entry_tags"):
        stored_tags_by_tag_now.setdefault(tag_now(stored_tag), []).append(stored_tag)
    for tag in tags:
        stored_tags = stored_tags_by_tag_now.get(tag_now(tag), [])
        if not stored_tags:
            continue
        marks = ",".join("?" * len(stored_tags))
        for (entry_id,) in connection.execute(
                f"SELECT DISTINCT entry_id FROM entry_tags JOIN entries USING (entry_id) "
                f"WHERE tag IN ({marks}) AND state = ?", (*stored_tags, index_program.STATE_STANDING)):
            matched.setdefault(entry_id, []).append(f"tag {tag}")
    for phrase in phrases:
        for (entry_id,) in connection.execute(
                "SELECT entries.entry_id FROM entries_full_text JOIN entries ON entries.entry_id = entries_full_text.rowid "
                "WHERE entries_full_text MATCH ? AND entries.state = ?",
                (full_text_phrase(phrase), index_program.STATE_STANDING)):
            matched.setdefault(entry_id, []).append(f"phrase {phrase}")
    return matched


def pairs_of(connection, entry_ids):
    """Return {entry_id: [(pair_id, state, other_entry_id), ...]}, every pair each entry of entry_ids is in."""
    pairs = {}
    for pair_id, first, second, state in connection.execute(
            "SELECT pair_id, first_entry_id, second_entry_id, state FROM entry_pairs ORDER BY pair_id"):
        if first in entry_ids:
            pairs.setdefault(first, []).append((pair_id, state, second))
        if second in entry_ids:
            pairs.setdefault(second, []).append((pair_id, state, first))
    return pairs


def utc_now():
    return datetime.datetime.now(datetime.timezone.utc)


def recency_weight(age_days):
    weight = 2 ** (-(age_days - RECENCY_WEIGHT_IS_ONE_AT_AGE_DAYS) / RECENCY_WEIGHT_HALF_LIFE_DAYS)
    if age_days * 24 < RECENT_ENTRY_BOOST_WITHIN_HOURS:
        weight *= RECENT_ENTRY_BOOST_FACTOR
    return weight


def inverse_document_frequency(standing_entry_count_in_store, entries_found_by_term):
    return math.log(standing_entry_count_in_store / entries_found_by_term)


def age_in_days(said_at_utc, now):
    said_at = datetime.datetime.fromisoformat(said_at_utc.replace("Z", "+00:00"))
    return (now - said_at).total_seconds() / 86400


def lookup(connection, tags, phrases, tag_now, now):
    """Return (N, {term: n}, entries): N the standing entries in the store, n those each "tag <tag>" or
    "phrase <phrase>" finds, and entries the standing entries found, with the other entry of each pair, highest
    score first, then newest first."""
    # One read transaction, so every query sees the same version of the store while the index program writes.
    connection.execute("BEGIN")
    (standing_entry_count_in_store,) = connection.execute(
        "SELECT COUNT(*) FROM entries WHERE state = ?", (index_program.STATE_STANDING,)).fetchone()
    matched = find_standing_entries_by_tags_and_phrases_with_what_matched_each(connection, tags, phrases, tag_now)
    found_by_each = {term: 0 for term in [f"tag {tag}" for tag in tags] + [f"phrase {phrase}" for phrase in phrases]}
    for terms in matched.values():
        for term in terms:
            found_by_each[term] += 1
    pairs = pairs_of(connection, set(matched))
    others = {other for entry_pairs in pairs.values() for _, _, other in entry_pairs if other not in matched}
    wanted = set(matched) | others
    pairs = pairs_of(connection, wanted)
    if not wanted:
        return standing_entry_count_in_store, found_by_each, []
    marks = ",".join("?" * len(wanted))
    rows = connection.execute(
        f"SELECT entry_id, kind, said_at_utc, source_path, source_line, agent_seat, text, agent_message_answered "
        f"FROM entries WHERE entry_id IN ({marks}) AND state = ? ORDER BY said_at_utc DESC, entry_id DESC",
        (*wanted, index_program.STATE_STANDING)).fetchall()
    tags_by_entry = {}
    for entry_id, tag in connection.execute(
            f"SELECT entry_id, tag FROM entry_tags WHERE entry_id IN ({marks}) ORDER BY tag", tuple(wanted)):
        tags_by_entry.setdefault(entry_id, set()).add(tag_now(tag))
    entries = []
    for entry_id, kind, said_at, source_path, source_line, agent_seat, text, answered in rows:
        matched_by = matched.get(entry_id, [])
        relevance = sum(inverse_document_frequency(standing_entry_count_in_store, found_by_each[term]) for term in matched_by)
        weight = recency_weight(age_in_days(said_at, now))
        entries.append({
            "id": f"entry-{entry_id}", "kind": kind, "said_at_utc": said_at,
            "link": index_program.link_to(source_path, source_line), "agent_seat": agent_seat,
            "tags": sorted(tags_by_entry.get(entry_id, ())), "matched_by": matched_by,
            "ranking_score_from_relevance_and_recency": relevance * weight, "relevance": relevance, "recency_weight": weight,
            "pairs": [{"pair_id": pair_id, "state": state, "other_entry": f"entry-{other}"}
                      for pair_id, state, other in pairs.get(entry_id, [])],
            "text": text, "agent_message_answered": answered})
    # The rows arrive newest first and the sort is stable, so equal scores stay newest first.
    entries.sort(key=lambda entry: entry["ranking_score_from_relevance_and_recency"], reverse=True)
    return standing_entry_count_in_store, found_by_each, entries


def lookup_input_from(text, tag_now):
    """Return (tags, phrases, limit) from the JSON object on stdin, each repeated tag or phrase dropped."""
    try:
        given = json.loads(text)
    except json.JSONDecodeError as error:
        raise CouldNotRun(f"stdin is not JSON: {error}", MALFORMED_INPUT_INSTRUCTIONS) from error
    if not isinstance(given, dict):
        raise CouldNotRun(f"stdin holds a JSON {type(given).__name__}, not an object", MALFORMED_INPUT_INSTRUCTIONS)
    unknown = sorted(set(given) - set(LOOKUP_INPUT_KEYS))
    if unknown:
        raise CouldNotRun(f"the input object has keys this lookup does not take: {', '.join(unknown)}",
                          MALFORMED_INPUT_INSTRUCTIONS)
    lists = {}
    for key in ("tags", "phrases"):
        value = given.get(key, [])
        if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
            raise CouldNotRun(f'"{key}" is not a list of strings', MALFORMED_INPUT_INSTRUCTIONS)
        lists[key] = value
    limit = given.get("limit", 0)
    if isinstance(limit, bool) or not isinstance(limit, int) or limit < 0:
        raise CouldNotRun(f'"limit" is {json.dumps(limit)}, not a whole number 0 or more',
                          MALFORMED_INPUT_INSTRUCTIONS)
    if not lists["tags"] and not lists["phrases"]:
        raise CouldNotRun("nothing to look up: no tag or phrase was given", NOTHING_TO_LOOK_UP_INSTRUCTIONS)
    for number, phrase in enumerate(lists["phrases"], start=1):
        if not phrase.strip():
            raise CouldNotRun(f'phrase {number} of "phrases", {json.dumps(phrase)}, is empty or only spaces',
                              EMPTY_PHRASE_INSTRUCTIONS)
    # A repeated tag or phrase would add its ln(N / n) to an entry's relevance twice.
    tags = list({tag_now(tag): tag for tag in reversed(lists["tags"])}.values())[::-1]
    phrases = list({phrase.casefold(): phrase for phrase in reversed(lists["phrases"])}.values())[::-1]
    return tags, phrases, limit


def run_lookup(arguments, stdin_text):
    stdout = sys.stdout
    try:
        repository = index_program.Repository(arguments.repository_checkout)
    except index_program.CouldNotRun as error:
        raise CouldNotRun(error.reason, REPOSITORY_UNREADABLE_INSTRUCTIONS_TEMPLATE.format(
            checkout=arguments.repository_checkout)) from error
    tags, phrases, limit = lookup_input_from(stdin_text, repository.path_now)
    path = store_path(arguments.log_store)
    connection = open_store_read_only(path, arguments.log_store)
    try:
        standing_entry_count_in_store, found_by_each, entries = lookup(
            connection, tags, phrases, repository.path_now, utc_now())
    except sqlite3.Error as error:
        raise CouldNotRun(f"the standing user-rulings store {path} cannot be read: {error}",
                          STORE_UNREADABLE_INSTRUCTIONS) from error
    finally:
        connection.close()
    printed = entries if limit == 0 else entries[:limit]
    printed_ids = {entry["id"] for entry in printed}
    others_wanted = {pair["other_entry"] for entry in printed for pair in entry["pairs"]} - printed_ids
    printed = printed + [entry for entry in entries if entry["id"] in others_wanted]
    stdout.write(json.dumps({"lookup_store": str(path), "tags": tags, "phrases": phrases,
                             "standing_entry_count_in_store": standing_entry_count_in_store,
                             "standing_entry_count_found_by_each_tag_and_phrase": found_by_each,
                             "standing_entries_matched": len(entries), "entries_printed": len(printed)},
                            ensure_ascii=False) + "\n")
    for entry in printed:
        stdout.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return EXIT_OK


def main(argv=None, stdin=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    lookup_parser = commands.add_parser(
        "lookup", help="a JSON object of tags and key phrases on stdin, standing entries out, highest score first",
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    lookup_parser.add_argument("--log-store", type=Path, default=index_program.DEFAULT_LOG_STORE)
    lookup_parser.add_argument("--repository-checkout", type=Path, default=HERE.parent)
    arguments = parser.parse_args(argv)
    try:
        return run_lookup(arguments, (stdin or sys.stdin).read())
    except CouldNotRun as could_not_run:
        sys.stderr.write(f"FAILED: the standing user-rulings lookup did not run, and printed no entries: "
                         f"{could_not_run.reason}\n{could_not_run.instructions}\n")
        return EXIT_COULD_NOT_RUN


if __name__ == "__main__":
    sys.exit(main())
