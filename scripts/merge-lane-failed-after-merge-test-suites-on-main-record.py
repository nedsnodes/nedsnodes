#!/usr/bin/env python3
"""Keep the test suites that failed an after-merge test run of main until each passes.

Usage:
  scripts/merge-lane-failed-after-merge-test-suites-on-main-record.py --print-merge-gate-notice

scripts/merge-lane-pull-request-merge-through-merge-gate-with-stacked-pull-request-retarget.py
loads this file by path and writes the record. scripts/merge-gate.sh runs it with
--print-merge-gate-notice, which prints the notice on stdout, and nothing when no suite is on
the record.

The record is the JSON object in ~/.local/state/nedsnodes/failed-after-merge-test-suites-on-main.json,
one key per suite path, each holding commit, pull_request, log, failed_at, repair_task_agent_seat
and repair_task_id; the last two are null when no repair task was opened.

Exit codes: 0 the notice, if any, was printed; 1 the record could not be read, and stderr says why.
"""

import argparse
import fcntl
import json
import os
import sys
import tempfile
from pathlib import Path

NOTICE_HEADING = "FAILED TEST SUITES ON MAIN"
SUITE_FIELDS = ("commit", "pull_request", "log", "failed_at", "repair_task_agent_seat",
                "repair_task_id")


class FailedSuitesRecordUnusable(Exception):
    """The record's file could not be read, parsed or written."""


def failed_suites_record_file():
    # Read at each call, because a test points HOME at a scratch directory after this loads.
    return (Path.home() / ".local" / "state" / "nedsnodes"
            / "failed-after-merge-test-suites-on-main.json")


def failed_suites_record_read():
    """The record as a dict of suite to fields; empty when the file does not exist."""
    path = failed_suites_record_file()
    try:
        suites = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except (OSError, UnicodeDecodeError, ValueError) as error:
        raise FailedSuitesRecordUnusable(f"could not read {path}: {error}") from error
    if not isinstance(suites, dict) or not all(
            isinstance(fields, dict) and all(name in fields for name in SUITE_FIELDS)
            for fields in suites.values()):
        raise FailedSuitesRecordUnusable(
            f"could not read {path}: it is not an object of suites holding {', '.join(SUITE_FIELDS)}")
    return suites


def failed_suites_record_changed(change):
    """Call change(suites) under the record's lock and write what it leaves; return that.

    Two merges can finish their after-merge test runs at once, so each reads and writes the
    record inside one lock.
    """
    path = failed_suites_record_file()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path.with_name(path.name + ".lock"), "w", encoding="utf-8") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            suites = failed_suites_record_read()
            change(suites)
            with tempfile.NamedTemporaryFile("w", dir=path.parent, prefix=f".{path.name}.",
                                             delete=False, encoding="utf-8") as partial:
                json.dump(suites, partial, indent=2, sort_keys=True)
            os.replace(partial.name, path)
    except OSError as error:
        raise FailedSuitesRecordUnusable(f"could not write {path}: {error}") from error
    return suites


def merge_gate_notice(suites):
    """The notice's text, or "" when no suite is on the record."""
    if not suites:
        return ""
    lines = [f"{NOTICE_HEADING}: {len(suites)} test suite(s) failed an after-merge test run of "
             f"main and have not passed since. The gate goes on; each later after-merge test run "
             f"runs them again, and a suite that passes leaves this notice."]
    for suite, fields in sorted(suites.items()):
        task = (f"repair task #{fields['repair_task_id']} on {fields['repair_task_agent_seat']}'s "
                f"task list" if fields["repair_task_id"] is not None
                else "no repair task, so merge-lane-2 asks the user who fixes it")
        lines.append(f"  {suite}: failed at {fields['commit'][:12]}, after pull request "
                     f"{fields['pull_request']}, on {fields['failed_at']}; log {fields['log']}; "
                     f"{task}")
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Print the merge-gate.sh notice of test suites that failed on main.")
    parser.add_argument("--print-merge-gate-notice", action="store_true", required=True)
    parser.parse_args(argv)
    try:
        notice = merge_gate_notice(failed_suites_record_read())
    except FailedSuitesRecordUnusable as error:
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
