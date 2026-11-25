#!/usr/bin/env python3
"""Tests for nn-systems/general-tools/saved-copy-put-back-at-path-staged-beside-and-swapped-in-whole-common.py.

Run: python3 nn-systems/general-tools/tests/saved-copy-put-back-at-path-staged-beside-and-swapped-in-whole-common-test.py
Prints one line per case and exits non-zero if any case fails.
"""

import errno
import importlib.util
import os
import shutil
import stat
import sys
import tempfile
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]

_spec = importlib.util.spec_from_file_location(
    "saved_copy_put_back_at_path_staged_beside_and_swapped_in_whole_common",
    REPOSITORY_ROOT / "nn-systems" / "general-tools"
    / "saved-copy-put-back-at-path-staged-beside-and-swapped-in-whole-common.py")
put_back = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(put_back)

failures = 0


def check(name, condition, detail=None):
    global failures
    if condition:
        print(f"PASS  {name}")
    else:
        failures += 1
        print(f"FAIL  {name}: {detail!r}")


def raised_by(saved_copy, path):
    try:
        put_back.saved_copy_put_back_at_path(saved_copy, path)
    except OSError as error:
        return error
    return None


def umask():
    current = os.umask(0)
    os.umask(current)
    return current


def names_in(directory):
    return sorted(entry.name for entry in Path(directory).iterdir())


def copy_then_fail(source, target, *rest):
    target.write(source.read(4))
    raise OSError(errno.ENOSPC, "No space left on device")


with tempfile.TemporaryDirectory() as scratch:
    scratch = Path(scratch)
    content = b"\xff\xfe not utf-8 \x00\n"
    copy = scratch / "found" / "only.md"
    copy.parent.mkdir()
    copy.write_bytes(content)

    path = scratch / "made" / "deeper" / "b.md"
    error = raised_by(copy, path)
    check("a copy given by its path is written to a new path, creating its missing directories",
          error is None and path.read_bytes() == content, error)
    check("a new file gets the mode open() would give it, not mkstemp's 0600",
          stat.S_IMODE(path.stat().st_mode) == 0o666 & ~umask(), oct(path.stat().st_mode))

    error = raised_by(b"from memory\n", path)
    check("a copy given as bytes replaces the file already there",
          error is None and path.read_bytes() == b"from memory\n", error)

    path.chmod(0o640)
    error = raised_by(copy, path)
    check("a replaced file keeps its mode",
          error is None and path.read_bytes() == content and stat.S_IMODE(path.stat().st_mode) == 0o640,
          (error, oct(path.stat().st_mode)))
    check("no temporary file is left beside a file put back", names_in(path.parent) == ["b.md"],
          names_in(path.parent))

    error = raised_by(scratch / "found" / "never-saved.md", scratch / "gone" / "d.md")
    check("a copy that does not exist raises FileNotFoundError and creates no directory",
          isinstance(error, FileNotFoundError) and not (scratch / "gone").exists(), error)

    (scratch / "a-file").write_bytes(b"not a directory\n")
    error = raised_by(copy, scratch / "a-file" / "e.md")
    check("a path whose parent is a file raises OSError and leaves the file as it was",
          isinstance(error, OSError) and (scratch / "a-file").read_bytes() == b"not a directory\n", error)

    symlink = scratch / "symlink-to-copy.md"
    symlink.symlink_to(copy)
    hard_link = scratch / "hard-link-to-copy.md"
    os.link(copy, hard_link)
    for name, same in (("the copy's own path", copy), ("a symlink to the copy", symlink),
                       ("a hard link to the copy", hard_link)):
        error = raised_by(copy, same)
        check("putting the copy back at %s raises SameFileError, says what to give instead, and leaves "
              "the copy whole" % name,
              isinstance(error, shutil.SameFileError)
              and "give the path of a saved copy that is a separate file" in str(error)
              and copy.read_bytes() == content, error)

    linked_target = scratch / "targets" / "real.md"
    linked_target.parent.mkdir()
    linked_target.write_bytes(b"before\n")
    linked_target.chmod(0o640)
    link = scratch / "links" / "link.md"
    link.parent.mkdir()
    link.symlink_to(linked_target)
    error = raised_by(copy, link)
    check("a path that is a symlink keeps the symlink and puts the copy into the file it points to, "
          "with that file's mode",
          error is None and link.is_symlink() and os.readlink(link) == str(linked_target)
          and linked_target.read_bytes() == content and stat.S_IMODE(linked_target.stat().st_mode) == 0o640
          and names_in(linked_target.parent) == ["real.md"], error)

    if os.geteuid() == 0:
        print("SKIP  a read-only file at the path is refused: root can write any file")
    else:
        read_only = scratch / "read-only" / "r.md"
        read_only.parent.mkdir()
        read_only.write_bytes(b"kept\n")
        read_only.chmod(0o444)
        error = raised_by(copy, read_only)
        check("a read-only file at the path raises PermissionError, says how to make it writable and then "
              "read-only again, and is left as it was",
              isinstance(error, PermissionError) and "chmod u+w %s" % read_only in str(error)
              and "chmod u-w %s" % read_only in str(error)
              and read_only.read_bytes() == b"kept\n", error)

    long_name = "n" * 250 + ".md"
    long_path = scratch / "long" / long_name
    long_path.parent.mkdir()
    long_path.write_bytes(b"before\n")
    error = raised_by(copy, long_path)
    check("a file whose name is near the length limit is put back", error is None
          and long_path.read_bytes() == content and names_in(long_path.parent) == [long_name], error)

    existing = scratch / "kept" / "e.md"
    existing.parent.mkdir()
    existing.write_bytes(b"what was there before\n")
    fresh = scratch / "kept" / "new.md"
    real_copyfileobj = shutil.copyfileobj
    shutil.copyfileobj = copy_then_fail
    try:
        over_existing = raised_by(copy, existing)
        over_nothing = raised_by(copy, fresh)
    finally:
        shutil.copyfileobj = real_copyfileobj
    check("a write that fails partway raises its OSError and leaves the file already there as it was, "
          "with no temporary file beside it",
          isinstance(over_existing, OSError) and "No space left on device" in str(over_existing)
          and existing.read_bytes() == b"what was there before\n" and names_in(existing.parent) == ["e.md"],
          (over_existing, names_in(existing.parent)))
    check("a write to a new path that fails partway leaves nothing at the path",
          isinstance(over_nothing, OSError) and not fresh.exists(), over_nothing)

    real_copyfileobj, real_unlink = shutil.copyfileobj, os.unlink

    def unlink_fails(target, *rest, **keywords):
        raise PermissionError(errno.EACCES, "Permission denied")

    shutil.copyfileobj, os.unlink = copy_then_fail, unlink_fails
    try:
        left_behind = raised_by(copy, existing)
    finally:
        shutil.copyfileobj, os.unlink = real_copyfileobj, real_unlink
    staged = [name for name in names_in(existing.parent) if name.startswith(put_back.STAGED_FILE_PREFIX)]
    check("a failed write whose temporary file cannot be removed raises "
          "SavedCopyPutBackFailedWithStagedFileLeftBehind naming the "
          "write's error, the temporary file and the removal's error",
          isinstance(left_behind, put_back.SavedCopyPutBackFailedWithStagedFileLeftBehind) and len(staged) == 1
          and "No space left on device" in str(left_behind)
          and str(existing.parent / staged[0]) in str(left_behind)
          and "PermissionError" in str(left_behind) and "Permission denied" in str(left_behind)
          and existing.read_bytes() == b"what was there before\n",
          (left_behind, staged))

print()
if failures:
    print(f"{failures} case(s) failed")
    sys.exit(1)
print("all cases passed")
