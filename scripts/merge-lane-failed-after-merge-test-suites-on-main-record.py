#!/usr/bin/env python3
"""Keep each test that failed an after-merge test run of main until it passes or is gone.

Usage:
  python3 scripts/merge-lane-failed-after-merge-test-suites-on-main-record.py --print-merge-gate-notice

scripts/merge-lane-pull-request-merge-through-merge-gate-with-stacked-pull-request-retarget.py
loads this file by path and writes the record. scripts/merge-gate.sh runs it with
--print-merge-gate-notice, which prints the notice on stdout, and nothing when no suite is on
the record.

The record is the JSON object in ~/.local/state/nedsnodes/failed-after-merge-test-suites-on-main.json,
one key per suite path, each holding failed_tests, an object with one key per failing test, as
junit.xml names it. Each test holds commit, the merge commit whose after-merge test run first
failed it; last_failed_commit, the newest commit at which a run has seen it fail since;
pull_request, log, failed_at, repair_task_agent_seat and repair_task_id; the last two are null
when no repair task was opened.

Exit codes: 0 the notice, if any, was printed; 1 the record could not be read, and stderr says why.
"""

import fcntl
import json
import os
import sys
from pathlib import Path

# merge-gate.sh runs this with --print-merge-gate-notice on every gate run, and its test suite runs
# the gate hundreds of times, so that path imports only what it uses: argparse alone costs Python
# 3.14 about 30 ms to set up, and tempfile about 15 ms.

NOTICE_HEADING = "FAILED TEST SUITES ON MAIN"
TEST_FIELD_TYPES = {"commit": str, "last_failed_commit": str, "pull_request": str, "log": (str, type(None)),
                    "failed_at": str, "repair_task_agent_seat": (str, type(None)),
                    "repair_task_id": (int, str, type(None))}


class FailedAfterMergeTestSuitesOnMainRecordFileUnreadableOrUnwritable(Exception):
    """The record's file could not be read, parsed or written."""


def failed_suites_record_file():
    # Read at each call, because a test points HOME at a scratch directory after this loads.
    return (Path.home() / ".local" / "state" / "nedsnodes"
            / "failed-after-merge-test-suites-on-main.json")


def failed_after_merge_test_suites_on_main_record_read():
    """The record as a dict of suite to fields; empty when the file does not exist."""
    path = failed_suites_record_file()
    try:
        suites = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except (OSError, UnicodeDecodeError, ValueError) as error:
        raise FailedAfterMergeTestSuitesOnMainRecordFileUnreadableOrUnwritable(f"could not read {path}: {error}") from error
    if not isinstance(suites, dict) or not all(
            isinstance(suite, dict) and isinstance(suite.get("failed_tests"), dict)
            and suite["failed_tests"] and all(
                isinstance(fields, dict) and all(
                    name in fields and isinstance(fields[name], kind)
                    for name, kind in TEST_FIELD_TYPES.items())
                for fields in suite["failed_tests"].values())
            for suite in suites.values()):
        raise FailedAfterMergeTestSuitesOnMainRecordFileUnreadableOrUnwritable(
            f"could not read {path}: it is not an object of suites whose failed_tests each hold "
            f"{', '.join(TEST_FIELD_TYPES)}, each of its type")
    return suites


def failed_after_merge_test_suites_on_main_record_change_apply_under_lock(change):
    """Call change(suites) under the record's lock and write what it leaves; return that.

    Two merges can finish their after-merge test runs at once, so each reads and writes the
    record inside one lock.
    """
    import tempfile

    path = failed_suites_record_file()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path.with_name(path.name + ".lock"), "w", encoding="utf-8") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            suites = failed_after_merge_test_suites_on_main_record_read()
            change(suites)
            with tempfile.NamedTemporaryFile("w", dir=path.parent, prefix=f".{path.name}.",
                                             delete=False, encoding="utf-8") as partial:
                json.dump(suites, partial, indent=2, sort_keys=True)
            os.replace(partial.name, path)
    except OSError as error:
        raise FailedAfterMergeTestSuitesOnMainRecordFileUnreadableOrUnwritable(f"could not write {path}: {error}") from error
    return suites


def merge_gate_notice(suites):
    """The notice's text, or "" when no suite is on the record."""
    if not suites:
        return ""
    count = sum(len(suite["failed_tests"]) for suite in suites.values())
    lines = [f"{NOTICE_HEADING}: {count} test(s) in {len(suites)} test suite(s) failed an "
             f"after-merge test run of main and have not passed since. The gate goes on; each "
             f"later after-merge test run runs them again, and a test that passes, or that a suite "
             f"run to the end no longer reports, leaves this notice."]
    for suite, entry in sorted(suites.items()):
        for test, fields in sorted(entry["failed_tests"].items()):
            task = (f"repair task #{fields['repair_task_id']} on "
                    f"{fields['repair_task_agent_seat']}'s task list"
                    if fields["repair_task_id"] is not None
                    else "no repair task, so merge-lane-2 asks the user who fixes it")
            name = suite if test == suite else f"{suite}: {test}"
            lines.append(f"  {name}: failed at {fields['commit'][:12]}, after pull request "
                         f"{fields['pull_request']}, on {fields['failed_at']}; log "
                         f"{fields['log']}; {task}")
    return "\n".join(lines)


def main(argv=None):
    if (sys.argv[1:] if argv is None else list(argv)) != ["--print-merge-gate-notice"]:
        import argparse

        parser = argparse.ArgumentParser(
            description="Print the merge-gate.sh notice of test suites that failed on main.")
        parser.add_argument("--print-merge-gate-notice", action="store_true", required=True)
        parser.parse_args(argv)
    try:
        notice = merge_gate_notice(failed_after_merge_test_suites_on_main_record_read())
    except FailedAfterMergeTestSuitesOnMainRecordFileUnreadableOrUnwritable as error:
        print(f"{NOTICE_HEADING}: {error}. merge-gate.sh cannot show which suites fail on main "
              f"until this is fixed; the gate goes on.\n"
              f"If the file holds bad JSON, read it, then fix it. If you cannot, send this message "
              f"to merge-lane-2, which owns the record.", file=sys.stderr)
        return 1
    if notice:
        print(notice)
    return 0


if __name__ == "__main__":
    sys.exit(main())
