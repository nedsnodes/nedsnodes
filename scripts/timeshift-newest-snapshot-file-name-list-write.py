#!/usr/bin/env python3
"""Write the file-name list of ned-box's newest Timeshift snapshot, which a bare-name backup search reads.

Usage:
  scripts/timeshift-newest-snapshot-file-name-list-write.py [--snapshot-root DIR] [--list-directory DIR]

Run every hour on ned-box by the scheduled-jobs table. It finds the newest
snapshot under the snapshot root. When the list directory already holds that
snapshot's list, it does nothing. Otherwise it runs `find` over the
directories scripts/find-deleted-path-across-backups.py searches by bare name,
inside that snapshot, and writes every path, one per line, gzip-compressed, to
<list directory>/<snapshot name>.paths.gz. The list is written to a temporary
file and renamed into place only when `find` succeeded; then the lists of
older snapshots are deleted.

A `find` over one snapshot takes about 8 minutes on the backup disk, which is
why the search reads this list instead of walking the snapshot's trees.

Prints nothing when it succeeds. Prints what failed and exits 1 when the
snapshot root is missing or empty, when `find` fails, or when a list cannot be
written or an older one deleted; the previous list is then left as it was.
"""

from __future__ import annotations

import argparse
import glob
import gzip
import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

_finder_spec = importlib.util.spec_from_file_location(
    "find_deleted_path_across_backups", Path(__file__).resolve().with_name("find-deleted-path-across-backups.py"))
finder = importlib.util.module_from_spec(_finder_spec)
_finder_spec.loader.exec_module(finder)


class ListWriteFailure(Exception):
    """A step failed; its text says what, and the old list is left in place."""


def newest_snapshot(snapshot_root):
    if not os.path.isdir(snapshot_root):
        raise ListWriteFailure("%s does not exist — is the backup drive mounted?" % snapshot_root)
    names = sorted(name for name in os.listdir(snapshot_root) if os.path.isdir(os.path.join(snapshot_root, name)))
    if not names:
        raise ListWriteFailure("%s holds no snapshot" % snapshot_root)
    return names[-1]


def snapshot_search_bases(snapshot_root, snapshot, search_roots):
    bases = []
    for root in search_roots:
        bases.extend(sorted(path for path in glob.glob(os.path.join(snapshot_root, snapshot, "localhost") + root)
                            if os.path.isdir(path)))
    return bases


def write_list(snapshot_root, snapshot, list_directory, search_roots):
    """Write <snapshot>.paths.gz in list_directory from one find over the snapshot's search bases."""
    final = os.path.join(list_directory, snapshot + finder.TIMESHIFT_FILE_NAME_LIST_SUFFIX)
    bases = snapshot_search_bases(snapshot_root, snapshot, search_roots)
    descriptor, partial = tempfile.mkstemp(prefix=".%s." % snapshot, suffix=".partial", dir=list_directory)
    try:
        with os.fdopen(descriptor, "wb") as raw, gzip.GzipFile(fileobj=raw, mode="wb") as compressed:
            if bases:
                process = subprocess.Popen(["find", *bases], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                shutil.copyfileobj(process.stdout, compressed)
                stderr = process.stderr.read().decode(errors="replace")
                if process.wait() != 0:
                    first = stderr.strip().splitlines()[0] if stderr.strip() else "no error text"
                    raise ListWriteFailure("find over snapshot %s failed (exit %s) — %s"
                                           % (snapshot, process.returncode, first))
        os.replace(partial, final)
    except BaseException:
        Path(partial).unlink(missing_ok=True)
        raise
    return final


def delete_older_lists(list_directory, keep):
    for name in sorted(os.listdir(list_directory)):
        path = os.path.join(list_directory, name)
        if name.endswith(finder.TIMESHIFT_FILE_NAME_LIST_SUFFIX) and path != keep:
            os.unlink(path)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--snapshot-root", default=finder.DEFAULT_TIMESHIFT_SNAPSHOT_ROOT)
    parser.add_argument("--list-directory", default=os.path.expanduser(finder.TIMESHIFT_FILE_NAME_LIST_DIRECTORY))
    args = parser.parse_args(argv)
    try:
        snapshot = newest_snapshot(args.snapshot_root)
        final = os.path.join(args.list_directory, snapshot + finder.TIMESHIFT_FILE_NAME_LIST_SUFFIX)
        if os.path.isfile(final):
            return 0
        os.makedirs(args.list_directory, exist_ok=True)
        final = write_list(args.snapshot_root, snapshot, args.list_directory, finder.DEFAULT_BOX_SEARCH_ROOTS)
        delete_older_lists(args.list_directory, final)
    except (ListWriteFailure, OSError) as failure:
        print("timeshift-newest-snapshot-file-name-list-write: FAILED: %s" % failure, file=sys.stderr)
        print("Until this program succeeds, a bare-name search of Timeshift by %s reports Timeshift as not searched, "
              "because no list of the newest snapshot is in %s." % (finder.PROGRAM_PATH, args.list_directory),
              file=sys.stderr)
        print("If the backup drive is not mounted, mount it, then run this program again on ned-box: "
              "python3 %s" % finder.TIMESHIFT_FILE_NAME_LIST_WRITER, file=sys.stderr)
        print("Otherwise run it again once; if it fails the same way, send the failure line above to the "
              "agent-seat that owns the job timeshift-newest-snapshot-file-name-list-write in "
              "nn-systems/general-tools/scheduled-jobs-on-each-machine.json.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
