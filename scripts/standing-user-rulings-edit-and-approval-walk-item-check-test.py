#!/usr/bin/env python3
"""Tests for standing-user-rulings-edit-and-approval-walk-item-check.py.

Run: python3 scripts/standing-user-rulings-edit-and-approval-walk-item-check-test.py
Prints one line per case and exits non-zero if any case fails.

Every case builds its own store in a temporary log-store; the real store is not read. The lookup's clock is fixed
at NOW, so every score is the same on every run.
"""

import contextlib
import datetime
import importlib.util
import io
import json
import math
import subprocess
import sys
import tempfile
from pathlib import Path

PROGRAM = Path(__file__).with_name("standing-user-rulings-edit-and-approval-walk-item-check.py")
spec = importlib.util.spec_from_file_location("standing_user_rulings_lookup", PROGRAM)
program = importlib.util.module_from_spec(spec)
spec.loader.exec_module(program)
index_program = program.index_program
NOW = datetime.datetime(2026, 11, 25, tzinfo=datetime.timezone.utc)
program.utc_now = lambda: NOW
failures = []


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


def run(log_store, given, *options):
    """Run the lookup with `given` on stdin: a dict is sent as JSON, a string as it is."""
    stdin_text = given if isinstance(given, str) else json.dumps(given)
    stdout, stderr = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        exit_code = program.main(["lookup", "--log-store", str(log_store), *options], stdin=io.StringIO(stdin_text))
    lines = [json.loads(line) for line in stdout.getvalue().splitlines()]
    return exit_code, (lines[0] if lines else None), lines[1:], stderr.getvalue()


def close(first, second):
    return math.isclose(first, second, rel_tol=1e-12)


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


# The constants against the user's figures: a week old weighs 1, three months old about a quarter of that, and the
# last 48 hours more again.
check("the recency weight is 1 for an entry a week old", program.recency_weight(7) == 1, program.recency_weight(7))
check("an entry 3 months old (90 to 92 days) weighs about a quarter of one a week old",
      all(0.24 <= program.recency_weight(days) <= 0.26 for days in (90, 91, 92)),
      [program.recency_weight(days) for days in (90, 91, 92)])
check("the recency weight halves every 6 weeks of age",
      close(program.recency_weight(7 + 42), 0.5) and close(program.recency_weight(7 + 84), 0.25),
      (program.recency_weight(49), program.recency_weight(91)))
unboosted_3_days = 2 ** (-(3 - 7) / 42)
check("an entry under a week old and over 48 hours old weighs more than 1, rising the same way, without the boost",
      close(program.recency_weight(3), unboosted_3_days) and program.recency_weight(3) > 1,
      program.recency_weight(3))
for hours, boosted in ((47, True), (49, False)):
    unboosted = 2 ** (-(hours / 24 - 7) / 42)
    check(f"an entry {hours} hours old weighs {'twice' if boosted else 'once'} what its age alone gives",
          close(program.recency_weight(hours / 24), unboosted * (2 if boosted else 1)),
          (program.recency_weight(hours / 24), unboosted))
check("with the store's count of 17,443, \"wait-limit\" finding 36 counts about one and a half times what "
      "\"in parallel\" finding 250 does",
      1.4 <= program.inverse_document_frequency(17443, 36) / program.inverse_document_frequency(17443, 250) <= 1.6,
      program.inverse_document_frequency(17443, 36) / program.inverse_document_frequency(17443, 250))

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

    exit_code, header, entries, stderr = run(log_store, {"tags": ["GHI 1"], "phrases": ["wait-limit"]})
    ids = [entry["id"] for entry in entries]
    check("a lookup by a tag and a phrase exits 0 and returns the standing entries either finds, with the other "
          "entry of a pair, highest score first",
          exit_code == 0 and ids == [f"entry-{both}", f"entry-{phrase_in_answered}", f"entry-{tagged_old}",
                                     f"entry-{paired_other}"], f"{exit_code} {ids} {stderr!r}")
    check("a superseded entry and an entry that is not the user's words are not returned",
          f"entry-{tagged_superseded}" not in ids and f"entry-{phrase_not_his}" not in ids, ids)
    by_id = {entry["id"]: entry for entry in entries}
    check("an entry found by a tag and by a phrase, in any letter case, lists both in matched_by",
          by_id.get(f"entry-{both}", {}).get("matched_by") == ["tag GHI 1", "phrase wait-limit"], by_id)
    # 5 standing entries; "GHI 1" finds 2 and "wait-limit" finds 2.
    both_entry = by_id[f"entry-{both}"]
    expected_weight = 2 ** (-(3 - 7) / 42)
    check("an entry's relevance is the sum of ln(N / n) over what matched it, and its score is relevance times its "
          "recency weight",
          close(both_entry["relevance"], 2 * math.log(5 / 2)) and close(both_entry["recency_weight"], expected_weight)
          and close(both_entry["ranking_score_from_relevance_and_recency"], 2 * math.log(5 / 2) * expected_weight), both_entry)
    check("the other entry of a pair, matched by nothing, has relevance 0 and score 0",
          by_id[f"entry-{paired_other}"]["relevance"] == 0 and by_id[f"entry-{paired_other}"]["ranking_score_from_relevance_and_recency"] == 0,
          by_id[f"entry-{paired_other}"])
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
    check("the first line counts the standing entries in the store, those each tag and phrase finds, and those "
          "matched and printed",
          header == {"lookup_store": str(program.store_path(log_store)), "tags": ["GHI 1"], "phrases": ["wait-limit"],
                     "standing_entry_count_in_store": 5,
                     "standing_entry_count_found_by_each_tag_and_phrase": {"tag GHI 1": 2, "phrase wait-limit": 2},
                     "standing_entries_matched": 4, "entries_printed": 4}, header)

    exit_code, header, entries, _ = run(log_store, {"tags": ["GHI 1", "GHI 1"], "phrases": ["wait-limit", "WAIT-LIMIT"]})
    by_id = {entry["id"]: entry for entry in entries}
    check("a tag or a phrase given twice, the phrase in another letter case, counts once",
          exit_code == 0 and header["tags"] == ["GHI 1"] and header["phrases"] == ["wait-limit"]
          and by_id[f"entry-{both}"]["matched_by"] == ["tag GHI 1", "phrase wait-limit"]
          and close(by_id[f"entry-{both}"]["relevance"], 2 * math.log(5 / 2)), (header, by_id.get(f"entry-{both}")))

    exit_code, header, entries, _ = run(log_store, {"tags": ["GHI 1"], "limit": 1})
    check("\"limit\" prints the N highest-scoring entries, and the first line still counts every match",
          exit_code == 0 and [entry["id"] for entry in entries] == [f"entry-{both}"]
          and header["standing_entries_matched"] == 3 and header["entries_printed"] == 1, (header, entries))

    exit_code, header, entries, _ = run(log_store, {"tags": ["GHI 1"], "phrases": ["old name"], "limit": 1})
    check("\"limit\" does not cut the other entry of a pair a printed entry is in: it is printed after the top entries",
          exit_code == 0 and [entry["id"] for entry in entries] == [f"entry-{tagged_old}", f"entry-{paired_other}"]
          and header["entries_printed"] == 2, (header, entries))

    exit_code, header, entries, _ = run(log_store, {"phrases": ["no such words here"]})
    check("a lookup that finds nothing exits 0 with a first line counting 0",
          exit_code == 0 and entries == [] and header["standing_entries_matched"] == 0
          and header["standing_entry_count_found_by_each_tag_and_phrase"] == {"phrase no such words here": 0}, (exit_code, header))

    store.add('He said "both" here.', "2026-11-24T00:00:00Z")
    exit_code, header, entries, stderr = run(log_store, {"phrases": ['"both"']})
    check("a phrase holding a double quote is looked up as a phrase, not read as query syntax",
          exit_code == 0 and header["standing_entries_matched"] == 2, (exit_code, header, stderr))

    example_input = json.loads(program.LOOKUP_INPUT_EXAMPLE)
    exit_code, header, _, stderr = run(log_store, example_input)
    check("the input the refusals give as an example runs",
          exit_code == 0 and header["tags"] == example_input["tags"], (exit_code, stderr))

    completed = subprocess.run([sys.executable, str(PROGRAM), "lookup", "--log-store", str(log_store)],
                               input='{"tags": ["GHI 1"]}', capture_output=True, text=True, timeout=60)
    check("the program run as a command reads its input from stdin",
          completed.returncode == 0 and json.loads(completed.stdout.splitlines()[0])["standing_entries_matched"] == 3,
          (completed.returncode, completed.stderr))

    completed = subprocess.run([sys.executable, str(PROGRAM), "lookup", "--help"], capture_output=True, text=True,
                               timeout=60)
    check("lookup --help gives the input object's keys, the score and the output",
          completed.returncode == 0 and all(text in completed.stdout for text in (
              "INPUT. One JSON object on stdin", "SCORE.", "OUTPUT.")), completed.stdout[:300])

    refusal_opening ="FAILED: the standing user-rulings lookup did not run, and printed no entries: "
    for case_name, given, reason in (
            ("stdin that is not JSON", '{"tags": ["GHI 1"', "stdin is not JSON: "),
            ("an empty stdin", "", "stdin is not JSON: "),
            ("a JSON value that is not an object", '["GHI 1"]', "stdin holds a JSON list, not an object"),
            ("an object with a key the lookup does not take", {"tag": ["GHI 1"]},
             "the input object has keys this lookup does not take: tag"),
            ("\"tags\" that is a string, not a list", {"tags": "GHI 1"}, '"tags" is not a list of strings'),
            ("\"phrases\" holding a number", {"phrases": ["wait-limit", 3]}, '"phrases" is not a list of strings'),
            ("a negative \"limit\"", {"tags": ["GHI 1"], "limit": -1}, '"limit" is -1, not a whole number 0 or more'),
            ("a \"limit\" that is not a whole number", {"tags": ["GHI 1"], "limit": 2.5},
             '"limit" is 2.5, not a whole number 0 or more'),
            ("a \"limit\" that is true", {"tags": ["GHI 1"], "limit": True},
             '"limit" is true, not a whole number 0 or more')):
        exit_code, header, _, stderr = run(log_store, given)
        check(f"{case_name} is refused: exit 2, no output, a FAILED line saying why and the input's form",
              exit_code == 2 and header is None and stderr.startswith(refusal_opening + reason)
              and '"tags" (a list of strings)' in stderr
              and f"echo '{program.LOOKUP_INPUT_EXAMPLE}' | python3 {PROGRAM.resolve()} lookup" in stderr,
              (exit_code, stderr))

    exit_code, header, _, stderr = run(log_store, {})
    check("a lookup with no tag and no phrase exits 2 with a FAILED line and what to give",
          exit_code == 2 and header is None
          and stderr.startswith(refusal_opening + "nothing to look up: no tag or phrase was given")
          and f"echo '{program.LOOKUP_INPUT_EXAMPLE}' | python3 {PROGRAM.resolve()} lookup" in stderr,
          (exit_code, stderr))

    exit_code, _, _, stderr = run(log_store, {"phrases": ["  "]})
    check("an empty phrase exits 2 with a FAILED line",
          exit_code == 2 and stderr.startswith(refusal_opening + 'phrase 1 of "phrases", "  ", is empty or only spaces')
          and "drop each phrase that is empty" in stderr, (exit_code, stderr))

    exit_code, _, _, stderr = run(Path(directory) / "mistyped", {"tags": ["GHI 1"]})
    check("a --log-store directory that does not exist exits 2 and says to check the path, not to fill a store there",
          exit_code == 2 and "the --log-store directory" in stderr and "typing mistake" in stderr
          and "index program" not in stderr, (exit_code, stderr))

    missing = Path(directory) / "no-log-store"
    missing.mkdir()
    exit_code, _, _, stderr = run(missing, {"tags": ["GHI 1"]})
    check("a missing store exits 2, names the path and says to run the index program",
          exit_code == 2 and f"the standing user-rulings store {program.store_path(missing)} does not exist" in stderr
          and f"has not yet filled a store in this lookup's log-store, {missing}." in stderr
          and f"--log-store {missing}\n" in stderr
          and "Run this lookup again once" not in stderr, (exit_code, stderr))

    broken = Path(directory) / "broken-log-store"
    program.store_path(broken).parent.mkdir(parents=True)
    program.store_path(broken).write_text("not a database")
    exit_code, _, _, stderr = run(broken, {"tags": ["GHI 1"]})
    check("a store that cannot be read exits 2, says so and says not to search by hand",
          exit_code == 2 and f"the standing user-rulings store {program.store_path(broken)} cannot be read" in stderr
          and "Do not search the store or the transcripts by hand" in stderr, (exit_code, stderr))

    real_find = program.find_standing_entries_by_tags_and_phrases_with_what_matched_each

    def failing_find(connection, tags, phrases, tag_now):
        raise program.sqlite3.OperationalError("database disk image is malformed")
    program.find_standing_entries_by_tags_and_phrases_with_what_matched_each = failing_find
    try:
        exit_code, _, _, stderr = run(log_store, {"tags": ["GHI 1"]})
    finally:
        program.find_standing_entries_by_tags_and_phrases_with_what_matched_each = real_find
    check("a store that opens but fails during the lookup exits 2 with the store's error",
          exit_code == 2 and "cannot be read: database disk image is malformed" in stderr, (exit_code, stderr))

    not_a_checkout = Path(directory) / "not-a-checkout"
    not_a_checkout.mkdir()
    exit_code, header, _, stderr = run(log_store, {"tags": ["GHI 1"]}, "--repository-checkout", str(not_a_checkout))
    check("a repository checkout whose origin/main cannot be read exits 2, says the lookup needs it and how to fetch it",
          exit_code == 2 and header is None and "git ls-tree of origin/main" in stderr
          and "needs origin/main to give each stored tag" in stderr
          and f"git -C {not_a_checkout} fetch origin main" in stderr and "Nothing was added" not in stderr,
          (exit_code, stderr))

    store.connection.close()

# The index program writes four forms of said_at_utc; a walk-minutes line that gives only a date is stored as
# "YYYY-MM-DD", with no zone, and the lookup must still weigh it.
with tempfile.TemporaryDirectory() as directory:
    log_store = Path(directory) / "logs"
    store = Store(log_store)
    forms = {"2026-11-18": 7, "2026-11-18T00:00Z": 7, "2026-11-18T00:00:00Z": 7, "2026-11-18T00:00:00.000Z": 7}
    ids_by_form = {form: store.add(f"Stored as {form}.", form, tags=("GHI 9",)) for form in forms}
    exit_code, header, entries, stderr = run(log_store, {"tags": ["GHI 9"]})
    weights = {entry["said_at_utc"]: entry["recency_weight"] for entry in entries}
    check("every form of said_at_utc the index program writes, a date alone included, is weighed as UTC",
          exit_code == 0 and set(weights) == set(forms) and all(close(weight, 1) for weight in weights.values()),
          (exit_code, weights, stderr))
    store.connection.close()

# Two entries the same tag finds have the same relevance, so the newer one, weighing more, comes first.
with tempfile.TemporaryDirectory() as directory:
    log_store = Path(directory) / "logs"
    store = Store(log_store)
    older = store.add("Older.", "2026-08-01T00:00:00Z", tags=("GHI 7",))
    newer = store.add("Newer.", "2026-11-10T00:00:00Z", tags=("GHI 7",))
    store.add("Elsewhere.", "2026-11-10T00:00:00Z", tags=("GHI 8",))
    exit_code, header, entries, stderr = run(log_store, {"tags": ["GHI 7"]})
    check("of two entries with the same relevance, the newer scores higher and comes first",
          exit_code == 0 and [entry["id"] for entry in entries] == [f"entry-{newer}", f"entry-{older}"]
          and entries[0]["relevance"] == entries[1]["relevance"] and entries[0]["ranking_score_from_relevance_and_recency"] > entries[1]["ranking_score_from_relevance_and_recency"],
          (entries, stderr))
    store.connection.close()

# An entry tagged before the project rename keeps its old tag in the store; the index file shows it renamed, so a
# lookup by the index file's tag must find it, and print the tag as the index file does.
with tempfile.TemporaryDirectory() as directory:
    log_store = Path(directory) / "logs"
    store = Store(log_store)
    old_tagged = store.add("Handoffs keep one file.", "2026-10-20T00:00:00Z", tags=("nc-systems/handoff/",))
    new_tagged = store.add("Handoffs keep it still.", "2026-11-20T00:00:00Z", tags=("nn-systems/handoff/",))
    exit_code, header, entries, stderr = run(log_store, {"tags": ["nn-systems/handoff/"]})
    by_id = {entry["id"]: entry for entry in entries}
    check("a tag given as the index file shows it finds an entry the store tagged before the project rename, and "
          "prints the tag renamed",
          exit_code == 0 and set(by_id) == {f"entry-{old_tagged}", f"entry-{new_tagged}"}
          and by_id[f"entry-{old_tagged}"]["tags"] == ["nn-systems/handoff/"]
          and by_id[f"entry-{old_tagged}"]["matched_by"] == ["tag nn-systems/handoff/"], (exit_code, entries, stderr))
    exit_code, header, entries, stderr = run(log_store, {"tags": ["nc-systems/handoff/"]})
    check("a tag given under its name from before the project rename finds the same entries",
          exit_code == 0 and header["standing_entries_matched"] == 2, (exit_code, header, stderr))
    exit_code, header, entries, stderr = run(log_store, {"tags": ["nn-systems/handoff/", "nc-systems/handoff/"]})
    check("a tag given under both its names counts once",
          exit_code == 0 and header["tags"] == ["nn-systems/handoff/"]
          and all(entry["matched_by"] == ["tag nn-systems/handoff/"] for entry in entries), (header, entries, stderr))
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
    exit_code, header, entries, stderr = run(log_store, {"tags": ["GHI 5"]})
    by_id = {entry["id"]: entry for entry in entries}
    check("an entry in two pairs is returned with both pairs, and the other entry of each pair is returned",
          exit_code == 0 and set(by_id) == {f"entry-{found_entry}", f"entry-{first_other}", f"entry-{second_other}"}
          and [pair["other_entry"] for pair in by_id[f"entry-{found_entry}"]["pairs"]]
          == [f"entry-{first_other}", f"entry-{second_other}"], (exit_code, entries, stderr))
    store.connection.close()

# A ruling whose own words share no key phrase with the question, and whose tags differ from it, is found only
# through the agent message he answered, by one rare phrase; newer entries that broad tags and phrases match must
# not rank above it.
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
    exit_code, header, entries, _ = run(log_store, {
        "tags": ["PR 4123", "nn-systems/handoff/"], "phrases": ["speed-up", "wait-limit", "run again"]})
    check("item 6's tags and key phrases find the user's 2026-11-20 ruling through the agent message he answered, "
          "and it ranks first, above nine newer entries that broad matches find",
          exit_code == 0 and entries and entries[0]["id"] == f"entry-{ruling}"
          and entries[0]["matched_by"] == ["phrase wait-limit"], entries)
    store.connection.close()

print(f"{'FAILED' if failures else 'all cases passed'}: {len(failures)} failure(s)")
sys.exit(1 if failures else 0)
