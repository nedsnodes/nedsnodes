#!/usr/bin/env python3
"""Put a saved copy of a file back at its path, whole or not at all.

saved_copy_put_back_at_path writes the copy to a temporary file beside the
file it replaces and swaps it in with os.replace, so a write that fails partway
leaves the file already there as it was. It creates missing parent
directories and keeps the permission bits of the file it replaces. When the
path is a symlink, the file the symlink points to is replaced and the symlink
is kept, unless the caller passes follow_symlink=False, which replaces the
symlink itself with a regular file. A symlink that points to itself, directly
or through others, is replaced, not kept, either way.

It refuses:
- a copy that is the file at the path, through a symlink or a hard link too,
  since replacing the file would destroy the only copy;
- a file at the path that its owner cannot write, since os.replace would
  replace it anyway.

Not kept: the replaced file's group owner, ACL and extended attributes. The
new file takes the group and, where the directory has a default ACL, the ACL
that a file newly created in that directory gets.

Load it by path, under the snake_case form of its file name:

    spec = importlib.util.spec_from_file_location(
        "saved_copy_put_back_at_path_staged_beside_and_swapped_in_whole_common", <path>)
"""

import io
import os
import shutil
import tempfile

# Fixed and short, so a file whose name is near the length limit can still be staged beside it.
STAGED_FILE_PREFIX = ".restoring."


class SavedCopyPutBackFailedWithStagedFileLeftBehind(OSError):
    """The put-back failed, and its temporary file could not be removed either."""

    def __init__(self, error, staged, cleanup_error):
        super().__init__(error.errno, "%s; the temporary file %s was left behind, and removing it failed: %s: %s"
                         % (error.strerror or error, staged, type(cleanup_error).__name__, cleanup_error))
        self.staged = staged


def saved_copy_put_back_at_path(saved_copy, path, follow_symlink=True):
    """Write saved_copy, given as bytes or as the path of a file, to path.

    With follow_symlink=False, a symlink at path is itself replaced, and the
    file it points to is left as it was.

    Raise OSError when it cannot, with any file already at path left as it was:
    shutil.SameFileError when saved_copy is the file at path, PermissionError
    when the file at path is not writable, and SavedCopyPutBackFailedWithStagedFileLeftBehind when the
    temporary file could not be removed after a failure.
    """
    in_memory = isinstance(saved_copy, bytes)
    replaces_symlink = not follow_symlink and os.path.islink(path)
    target = os.path.realpath(path) if os.path.islink(path) and follow_symlink else path
    # Opened first, so a copy that cannot be read leaves no new directories behind.
    with io.BytesIO(saved_copy) if in_memory else open(saved_copy, "rb") as source:
        # A symlink being replaced gives no permission bits to keep, and its target's are not the path's own.
        exists = not replaces_symlink and os.path.exists(target)
        if not in_memory and exists and os.path.samefile(saved_copy, target):
            raise shutil.SameFileError(
                "the saved copy %s and %s are one file, reached by the same path, a symlink or a hard link, so "
                "nothing was put back and %s was left as it was; to put back a different version, give the "
                "path of a saved copy that is a separate file" % (saved_copy, path, path))
        if exists and not os.access(target, os.W_OK):
            raise PermissionError("%s is read-only, so nothing was put back and it was left as it was; if it "
                                  "should be replaced, run chmod u+w %s, then the same command again, then "
                                  "chmod u-w %s to make it read-only again" % (path, target, target))
        directory = os.path.dirname(target) or "."
        os.makedirs(directory, exist_ok=True)
        descriptor, staged = tempfile.mkstemp(dir=directory, prefix=STAGED_FILE_PREFIX)
        try:
            with os.fdopen(descriptor, "wb") as staged_file:
                shutil.copyfileobj(source, staged_file)
            if exists:
                shutil.copymode(target, staged)
            else:
                # mkstemp makes the file 0600; a file open() creates gets 0666 less the umask.
                umask = os.umask(0)
                os.umask(umask)
                os.chmod(staged, 0o666 & ~umask)
            os.replace(staged, target)
        except BaseException as error:
            try:
                os.unlink(staged)
            except FileNotFoundError:
                pass
            except OSError as cleanup_error:
                if isinstance(error, OSError):
                    raise SavedCopyPutBackFailedWithStagedFileLeftBehind(error, staged, cleanup_error) from error
            raise
