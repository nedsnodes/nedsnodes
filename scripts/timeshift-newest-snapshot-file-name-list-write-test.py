#!/usr/bin/env python3
"""Tests for timeshift-newest-snapshot-file-name-list-write.py.

Run: python3 scripts/timeshift-newest-snapshot-file-name-list-write-test.py
Prints one line per case and exits non-zero if any case fails.

Every case runs the program for real against a fake snapshot tree in a
temporary directory; a failing `find` is injected by a fake `find` first on
PATH, since a real one cannot be made to fail reliably for every user.
"""

import gzip
import os
import subprocess
import sys
import tempfile
from pathlib import Path

PROGRAM = Path(__file__).resolve().with_name("timeshift-newest-snapshot-file-name-list-write.py")
failures = []


def check(name, condition, detail=""):
    print("%s  %s%s" % ("PASS" if condition else "FAIL", name, "" if condition else " — " + detail))
    if not condition:
        failures.append(name)


def run(snapshot_root, list_directory, path_prefix=None):
    environment = dict(os.environ)
    if path_prefix:
        environment["PATH"] = path_prefix + os.pathsep + environment["PATH"]
    return subprocess.run([sys.executable, str(PROGRAM), "--snapshot-root", str(snapshot_root),
                           "--list-directory", str(list_directory)],
                          capture_output=True, text=True, env=environment)


def snapshot(root, name, files):
    for relative in files:
        path = Path(root, name, "localhost", "home", "nedlern", relative)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("x\n")


def listed(path):
    with gzip.open(path, "rt") as stream:
        return stream.read().splitlines()


with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp, "snapshots")
    lists = Path(tmp, "lists")
    snapshot(root, "2026-08-13_10-00-00", ["agents/seat-a/old.md"])
    snapshot(root, "2026-08-14_11-35-50", ["agents/seat-a/new.md", "Projects/nedsnodes/docs/x.md", "elsewhere/y.md"])

    result = run(root, lists)
    newest_list = Path(lists, "2026-08-14_11-35-50.paths.gz")
    check("a first run exits 0 and prints nothing", result.returncode == 0 and not result.stdout and not result.stderr,
          "%s %r %r" % (result.returncode, result.stdout, result.stderr))
    check("it writes the newest snapshot's list, named after that snapshot", newest_list.is_file(),
          str(sorted(os.listdir(lists))))
    paths = listed(newest_list)
    check("the list holds the snapshot paths under the search roots, the seat-glob root included",
          str(Path(root, "2026-08-14_11-35-50", "localhost", "home/nedlern/agents/seat-a/new.md")) in paths
          and str(Path(root, "2026-08-14_11-35-50", "localhost", "home/nedlern/Projects/nedsnodes/docs/x.md")) in paths,
          str(paths))
    check("the list leaves out folders outside the search roots, and the older snapshot",
          not any("elsewhere" in p or "2026-08-13" in p for p in paths), str(paths))
    check("no temporary file is left in the list directory", sorted(os.listdir(lists)) == [newest_list.name],
          str(sorted(os.listdir(lists))))

    before = newest_list.stat().st_mtime_ns
    result = run(root, lists)
    check("a run when the newest snapshot is already listed does nothing",
          result.returncode == 0 and newest_list.stat().st_mtime_ns == before, "%s %r" % (result.returncode, result.stderr))

    snapshot(root, "2026-08-15_09-00-00", ["agents/seat-a/newer.md"])
    result = run(root, lists)
    check("a new snapshot gets its list and the older list is deleted",
          result.returncode == 0 and sorted(os.listdir(lists)) == ["2026-08-15_09-00-00.paths.gz"],
          "%s %r %s" % (result.returncode, result.stderr, sorted(os.listdir(lists))))

    fake_bin = Path(tmp, "fake-bin")
    fake_bin.mkdir()
    fake_find = Path(fake_bin, "find")
    fake_find.write_text("#!/bin/sh\necho 'find: injected failure' >&2\nexit 1\n")
    fake_find.chmod(0o755)
    snapshot(root, "2026-08-16_09-00-00", ["agents/seat-a/newest.md"])
    result = run(root, lists, path_prefix=str(fake_bin))
    check("a find that fails exits 1, names the snapshot and find's error, and says what to do",
          result.returncode == 1 and "find over snapshot 2026-08-16_09-00-00 failed (exit 1) — find: injected failure"
          in result.stderr and "run it again once" in result.stderr, "%s %r" % (result.returncode, result.stderr))
    check("a failed find keeps the previous list and leaves no partial file",
          sorted(os.listdir(lists)) == ["2026-08-15_09-00-00.paths.gz"], str(sorted(os.listdir(lists))))

    Path(lists, "2026-08-15_09-00-00.paths.gz").unlink()
    Path(lists, "2026-08-15_09-00-00.paths.gz").mkdir()
    result = run(root, lists)
    check("an older list that cannot be deleted makes the run exit 1, with the new list in place",
          result.returncode == 1 and "FAILED" in result.stderr
          and Path(lists, "2026-08-16_09-00-00.paths.gz").is_file(), "%s %r" % (result.returncode, result.stderr))

    result = run(Path(tmp, "no-such-root"), lists)
    check("a missing snapshot root exits 1 and asks whether the backup drive is mounted",
          result.returncode == 1 and "is the backup drive mounted?" in result.stderr
          and "mount it, then run this program again on ned-box" in result.stderr,
          "%s %r" % (result.returncode, result.stderr))

    Path(tmp, "empty").mkdir()
    result = run(Path(tmp, "empty"), lists)
    check("a snapshot root with no snapshot exits 1", result.returncode == 1 and "holds no snapshot" in result.stderr,
          "%s %r" % (result.returncode, result.stderr))

if failures:
    print("\n%d case(s) failed: %s" % (len(failures), "; ".join(failures)))
    sys.exit(1)
print("\nall cases passed")
