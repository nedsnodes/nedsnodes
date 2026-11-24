#!/usr/bin/env python3
"""Tests for standing-user-rulings-edit-and-approval-walk-item-check.py.

Run: python3 scripts/standing-user-rulings-edit-and-approval-walk-item-check-test.py
Prints one line per case and exits non-zero if any case fails.

Every case builds its own store in a temporary log-store; the real store is not read.
"""

import contextlib
import importlib.util
import io
import json
import sys
import tempfile
from pathlib import Path

PROGRAM = Path(__file__).with_name("standing-user-rulings-edit-and-approval-walk-item-check.py")
spec = importlib.util.spec_from_file_location("standing_user_rulings_lookup", PROGRAM)
program = importlib.util.module_from_spec(spec)
spec.loader.exec_module(program)
index_program = program.index_program
failures = []


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


def run(argv):
    stdout, stderr = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        exit_code = program.main(argv)
    lines = [json.loads(line) for line in stdout.getvalue().splitlines()]
    return exit_code, (lines[0] if lines else None), lines[1:], stderr.getvalue()


class Store:
    def __init__(self, log_store):
        self.log_store = log_store
        path = program.store_path(log_store)
        path.parent.mkdir(parents=True)
        self.connection = index_program.open_store(path)
        self.count = 0

    def add(self, text, said_at, state="standing", answered=None, tags=()):
        self.count += 1
        cursor = self.connection.execute(
            "INSERT INTO entries (kind, state, said_at_utc, text, agent_message_answered, source_path, source_line, "
            "agent_seat, added_at_utc, added_by, duplicate_key) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("user-words", state, said_at, text, answered, f"/transcripts/t{self.count}.jsonl", self.count,
             "alpha-seat", said_at, "test", f"key-{self.count}"))
        for tag in tags:
            self.connection.execute("INSERT INTO entry_tags (entry_id, tag, tag_source) VALUES (?, ?, 'user-words')",
                                    (cursor.lastrowid, tag))
        self.connection.commit()
        return cursor.lastrowid

    def pair(self, first, second):
        self.connection.execute("INSERT INTO entry_pairs (first_entry_id, second_entry_id, linked_at_utc, linked_by) "
                                "VALUES (?, ?, '2026-11-24T00:00:00Z', 'test')", (min(first, second), max(first, second)))
        self.connection.commit()


with tempfile.TemporaryDirectory() as directory:
    log_store = Path(directory) / "logs"
    store = Store(log_store)
    tagged_old = store.add("Keep the old name.", "2026-10-01T00:00:00Z", tags=("GHI 1",))
    tagged_superseded = store.add("Rename it.", "2026-10-02T00:00:00Z", state="superseded", tags=("GHI 1",))
    phrase_in_answered = store.add("Yes, handle both.", "2026-11-20T19:01:25Z",
                                   answered="Should the wait-limit apply to every task?")
    phrase_not_his = store.add("A program prompt about the wait-limit.", "2026-11-21T00:00:00Z",
                               state="not-the-user's-words")
    both = store.add("The Wait-Limit stays, as GHI 1 says.", "2026-11-22T00:00:00Z", tags=("GHI 1",))
    paired_other = store.add("No limit at all.", "2026-09-01T00:00:00Z")
    store.pair(tagged_old, paired_other)
    unrelated = store.add("Something else.", "2026-11-23T00:00:00Z", tags=("GHI 2",))

    exit_code, header, entries, stderr = run(["lookup", "--log-store", str(log_store), "--tag", "GHI 1",
                                              "--phrase", "wait-limit"])
    ids = [entry["id"] for entry in entries]
    check("a lookup by a tag and a phrase exits 0 and returns the standing entries either finds, with the other "
          "entry of a pair, newest first",
          exit_code == 0 and ids == [f"entry-{both}", f"entry-{phrase_in_answered}", f"entry-{tagged_old}",
                                     f"entry-{paired_other}"], f"{exit_code} {ids} {stderr!r}")
    check("a superseded entry and an entry that is not the user's words are not returned",
          f"entry-{tagged_superseded}" not in ids and f"entry-{phrase_not_his}" not in ids, ids)
    by_id = {entry["id"]: entry for entry in entries}
    check("an entry found by a tag and by a phrase, in any letter case, lists both in matched_by",
          by_id.get(f"entry-{both}", {}).get("matched_by") == ["tag GHI 1", "phrase wait-limit"], by_id)
    check("a phrase that appears only in the agent message he answered finds his words, and the entry carries that "
          "message",
          by_id.get(f"entry-{phrase_in_answered}", {}).get("agent_message_answered")
          == "Should the wait-limit apply to every task?", by_id)
    check("the other entry of a pair is returned with an empty matched_by, and both entries name the pair",
          by_id.get(f"entry-{paired_other}", {}).get("matched_by") == []
          and by_id[f"entry-{paired_other}"]["pairs"] == [{"pair_id": 1, "state": "unreviewed",
                                                           "other_entry": f"entry-{tagged_old}"}]
          and [pair["other_entry"] for pair in by_id[f"entry-{tagged_old}"]["pairs"]] == [f"entry-{paired_other}"]
          and by_id[f"entry-{both}"]["pairs"] == [], by_id)
    check("each entry carries its link in the index file's form, its agent-seat and its tags",
          by_id[f"entry-{tagged_old}"]["link"] == f"nedlern@ned-box:/transcripts/t{tagged_old}.jsonl line {tagged_old}"
          and by_id[f"entry-{tagged_old}"]["agent_seat"] == "alpha-seat"
          and by_id[f"entry-{tagged_old}"]["tags"] == ["GHI 1"], by_id[f"entry-{tagged_old}"])
    check("the first line counts the standing entries matched and printed",
          header == {"lookup_store": str(program.store_path(log_store)), "tags": ["GHI 1"], "phrases": ["wait-limit"],
                     "standing_entries_matched": 4, "entries_printed": 4}, header)

    exit_code, header, entries, _ = run(["lookup", "--log-store", str(log_store), "--tag", "GHI 1", "--limit", "1"])
    check("--limit prints the newest N entries, and the first line still counts every match",
          exit_code == 0 and [entry["id"] for entry in entries] == [f"entry-{both}"]
          and header["standing_entries_matched"] == 3 and header["entries_printed"] == 1, (header, entries))

    exit_code, header, entries, _ = run(["lookup", "--log-store", str(log_store), "--phrase", "no such words here"])
    check("a lookup that finds nothing exits 0 with a first line counting 0",
          exit_code == 0 and entries == [] and header["standing_entries_matched"] == 0, (exit_code, header))

    store.add('He said "both" here.', "2026-11-24T00:00:00Z")
    exit_code, header, entries, stderr = run(["lookup", "--log-store", str(log_store), "--phrase", '"both"'])
    check("a phrase holding a double quote is looked up as a phrase, not read as query syntax",
          exit_code == 0 and header["standing_entries_matched"] == 2, (exit_code, header, stderr))

    exit_code, header, _, stderr = run(["lookup", "--log-store", str(log_store)])
    check("a lookup with no tag and no phrase exits 2 with a FAILED line and what to give",
          exit_code == 2 and header is None and stderr.startswith("FAILED: the standing user-rulings lookup did not run, and printed no entries: nothing to "
                                                   "look up")
          and f"{PROGRAM.resolve()} lookup --tag 'GHI 2118'" in stderr, (exit_code, stderr))

    exit_code, _, _, stderr = run(["lookup", "--log-store", str(log_store), "--phrase", "  "])
    check("an empty phrase exits 2 with a FAILED line",
          exit_code == 2 and "lookup did not run, and printed no entries: a --phrase is empty" in stderr, (exit_code, stderr))

    exit_code, _, _, stderr = run(["lookup", "--log-store", str(Path(directory) / "mistyped"), "--tag", "GHI 1"])
    check("a --log-store directory that does not exist exits 2 and says to check the path, not to fill a store there",
          exit_code == 2 and "the --log-store directory" in stderr and "typing mistake" in stderr
          and "index program" not in stderr, (exit_code, stderr))

    missing = Path(directory) / "no-log-store"
    missing.mkdir()
    exit_code, _, _, stderr = run(["lookup", "--log-store", str(missing), "--tag", "GHI 1"])
    check("a missing store exits 2, names the path and says to run the index program",
          exit_code == 2 and f"the standing user-rulings store {program.store_path(missing)} does not exist" in stderr
          and f"has not yet filled a store in this lookup's log-store, {missing}." in stderr
          and f"--log-store {missing}\n" in stderr
          and "Run this lookup again once" not in stderr, (exit_code, stderr))

    broken = Path(directory) / "broken-log-store"
    program.store_path(broken).parent.mkdir(parents=True)
    program.store_path(broken).write_text("not a database")
    exit_code, _, _, stderr = run(["lookup", "--log-store", str(broken), "--tag", "GHI 1"])
    check("a store that cannot be read exits 2, says so and says not to search by hand",
          exit_code == 2 and f"the standing user-rulings store {program.store_path(broken)} cannot be read" in stderr
          and "Do not search the store or the transcripts by hand" in stderr, (exit_code, stderr))

    real_find = program.find_standing_entries_by_tags_and_phrases_with_what_matched_each

    def failing_find(connection, tags, phrases, tag_now):
        raise program.sqlite3.OperationalError("database disk image is malformed")
    program.find_standing_entries_by_tags_and_phrases_with_what_matched_each = failing_find
    try:
        exit_code, _, _, stderr = run(["lookup", "--log-store", str(log_store), "--tag", "GHI 1"])
    finally:
        program.find_standing_entries_by_tags_and_phrases_with_what_matched_each = real_find
    check("a store that opens but fails during the lookup exits 2 with the store's error",
          exit_code == 2 and "cannot be read: database disk image is malformed" in stderr, (exit_code, stderr))

    not_a_checkout = Path(directory) / "not-a-checkout"
    not_a_checkout.mkdir()
    exit_code, header, _, stderr = run(["lookup", "--log-store", str(log_store), "--tag", "GHI 1",
                                        "--repository-checkout", str(not_a_checkout)])
    check("a repository checkout whose origin/main cannot be read exits 2, says the lookup needs it and how to fetch it",
          exit_code == 2 and header is None and "git ls-tree of origin/main" in stderr
          and "needs origin/main to give each stored tag" in stderr
          and f"git -C {not_a_checkout} fetch origin main" in stderr and "Nothing was added" not in stderr,
          (exit_code, stderr))

    store.connection.close()

# An entry tagged before the project rename keeps its old tag in the store; the index file shows it renamed, so a
# lookup by the index file's tag must find it, and print the tag as the index file does.
with tempfile.TemporaryDirectory() as directory:
    log_store = Path(directory) / "logs"
    store = Store(log_store)
    old_tagged = store.add("Handoffs keep one file.", "2026-10-20T00:00:00Z", tags=("nc-systems/handoff/",))
    new_tagged = store.add("Handoffs keep it still.", "2026-11-20T00:00:00Z", tags=("nn-systems/handoff/",))
    exit_code, header, entries, stderr = run(["lookup", "--log-store", str(log_store), "--tag", "nn-systems/handoff/"])
    by_id = {entry["id"]: entry for entry in entries}
    check("a tag given as the index file shows it finds an entry the store tagged before the project rename, and "
          "prints the tag renamed",
          exit_code == 0 and set(by_id) == {f"entry-{old_tagged}", f"entry-{new_tagged}"}
          and by_id[f"entry-{old_tagged}"]["tags"] == ["nn-systems/handoff/"]
          and by_id[f"entry-{old_tagged}"]["matched_by"] == ["tag nn-systems/handoff/"], (exit_code, entries, stderr))
    exit_code, header, entries, stderr = run(["lookup", "--log-store", str(log_store), "--tag", "nc-systems/handoff/"])
    check("a tag given under its name from before the project rename finds the same entries",
          exit_code == 0 and header["standing_entries_matched"] == 2, (exit_code, header, stderr))
    store.connection.close()

# An entry may be in more than one pair; a lookup that finds it returns the other entry of every pair.
with tempfile.TemporaryDirectory() as directory:
    log_store = Path(directory) / "logs"
    store = Store(log_store)
    found_entry = store.add("Run both.", "2026-11-20T00:00:00Z", tags=("GHI 5",))
    first_other = store.add("Run one.", "2026-11-01T00:00:00Z")
    second_other = store.add("Run none.", "2026-10-01T00:00:00Z")
    store.pair(found_entry, first_other)
    store.pair(found_entry, second_other)
    exit_code, header, entries, stderr = run(["lookup", "--log-store", str(log_store), "--tag", "GHI 5"])
    by_id = {entry["id"]: entry for entry in entries}
    check("an entry in two pairs is returned with both pairs, and the other entry of each pair is returned",
          exit_code == 0 and set(by_id) == {f"entry-{found_entry}", f"entry-{first_other}", f"entry-{second_other}"}
          and [pair["other_entry"] for pair in by_id[f"entry-{found_entry}"]["pairs"]]
          == [f"entry-{first_other}", f"entry-{second_other}"], (exit_code, entries, stderr))
    store.connection.close()

# A ruling whose own words share no key phrase with the question, and whose tags differ from it, is found only
# through the agent message he answered; newer entries matching broader phrases must not hide it.
with tempfile.TemporaryDirectory() as directory:
    log_store = Path(directory) / "logs"
    store = Store(log_store)
    ruling = store.add(
        "My guess is that some tasks will easily detach and some won't. And so I think you're going to have to, I "
        "think we should probably handle both. Do you agree?", "2026-11-20T19:01:25Z",
        answered="Item 67: should the successor keep waiting past the wait-limit for a task that will not detach?",
        tags=("GHI 224", "task MD-skills 493"))
    for day in range(1, 10):
        store.add(f"A newer ruling about something run again, number {day}.", f"2026-11-2{day % 4 + 1}T0{day}:00:00Z",
                  tags=("nn-systems/handoff/",))
    exit_code, header, entries, _ = run(
        ["lookup", "--log-store", str(log_store), "--tag", "PR 4123", "--tag", "nn-systems/handoff/",
         "--phrase", "speed-up", "--phrase", "wait-limit", "--phrase", "run again"])
    found = [entry for entry in entries if entry["id"] == f"entry-{ruling}"]
    check("item 6's tags and key phrases find the user's 2026-11-20 ruling through the agent message he answered",
          exit_code == 0 and len(found) == 1 and found[0]["matched_by"] == ["phrase wait-limit"], entries)
    store.connection.close()

print(f"{'FAILED' if failures else 'all cases passed'}: {len(failures)} failure(s)")
sys.exit(1 if failures else 0)
