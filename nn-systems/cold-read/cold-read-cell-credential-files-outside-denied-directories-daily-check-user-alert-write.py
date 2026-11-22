#!/usr/bin/env python3
"""Write a user-alert naming each file named *.token or .env in the home directory that ned-box's list of credential files leaves out.

    python3 <this file>

On Linux the sandboxes of the cold-read-cells and of the Codex and Gemini task programs deny a reviewer program
only the files CREDENTIAL_FILES_ON_NED_BOX and REVIEWER_PROGRAM_LOGIN_FILES list, by exact path, both in
nn-systems/cold-read/cold-read-cell-common.py. A credential file added later is readable until it is added to that
list. This program walks the home directory, read from HOME, skipping the log-store (~/nedsnodes-logs, whose test
leftovers match the patterns but hold no credential), and when it finds a file named by a pattern of
CREDENTIAL_FILE_NAME_PATTERNS, `*.token` or `.env`, that neither list names and IGNORED_FILES does not name, writes
one user-alert naming every one found, through
nn-systems/general-tools/user-alerts-pending-and-claimed-files-write-claim-release-and-delete-common.py.
It keeps no state, so the alert comes again each day until the file is added to CREDENTIAL_FILES_ON_NED_BOX or
deleted.

It runs once a day on ned-box, from the table nn-systems/general-tools/scheduled-jobs-on-each-machine.json,
which nn-systems/general-tools/install-scheduled-jobs-on-this-machine.py installs as this cron line:
    45 7 * * * /usr/bin/python3 /home/nedlern/Projects/nedsnodes/nn-systems/cold-read/cold-read-cell-credential-files-outside-denied-directories-daily-check-user-alert-write.py >> /home/nedlern/.claude/cold-read-cell-credential-files-outside-denied-directories-daily-check-user-alert-write.log 2>&1

Skipped: a folder this user cannot read, because the reviewers run as the same user and cannot read it
either; a folder removed while the walk runs; the target of a symbolic link to a folder.
Not found: a credential file named by neither pattern.

Exit status: 0 when nothing was found or the alert naming the files was written. 1 when the walk failed,
whether or not the user-alert reporting that failure was written, or when the alert naming the files
could not be written; an error the program cannot put in a user-alert is printed only, to the cron log
above. The program writes only to the user-alerts directory, and cron appends its output to that log.
"""
import argparse
import fnmatch
import importlib.util
import os
import sys
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[2]


def _load(name, path):
    specification = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


cell_common = _load("cold_read_cell_common", REPOSITORY / "nn-systems" / "cold-read" / "cold-read-cell-common.py")
user_alerts = _load(
    "user_alerts_pending_and_claimed_files_write_claim_release_and_delete_common",
    REPOSITORY / "nn-systems" / "general-tools"
    / "user-alerts-pending-and-claimed-files-write-claim-release-and-delete-common.py")

THIS_PROGRAM = "nn-systems/cold-read/cold-read-cell-credential-files-outside-denied-directories-daily-check-user-alert-write.py"
FOUND_TITLE = "A credential file on ned-box is readable to the cold-read-cells' reviewer programs"
FOUND_ACTION = (
    "Only the user can say whether the file holds a credential. An agent on ned-box asks him, then, if it does, adds "
    "the file's path to CREDENTIAL_FILES_ON_NED_BOX in nn-systems/cold-read/cold-read-cell-common.py in a pull request, "
    "or deletes the file if he says to; if it does not, adds the path to IGNORED_FILES in "
    f"{THIS_PROGRAM} in a pull request.")
NAME_PATTERNS = " or ".join(cell_common.CREDENTIAL_FILE_NAME_PATTERNS)
FAILED_TITLE = "The daily search of ned-box for credential files the cold-read-cells can read failed"
FAILED_ACTION = (
    f"An agent on ned-box can run python3 {THIS_PROGRAM} by hand, read the error it prints, and fix its cause; "
    "until then a new credential file missing from CREDENTIAL_FILES_ON_NED_BOX goes unreported.")
# Files named like credentials that the user does not count as credentials to protect, relative to the home folder.
IGNORED_FILES = (".steam/steam.token",)


def listed_or_ignored_files(home):
    return ({Path(path) for path in cell_common.CREDENTIAL_FILES_ON_NED_BOX}
            | {Path(path) for path in cell_common.reviewer_program_login_files()}
            | {home / path for path in IGNORED_FILES})


def _raise_unless_unreadable_or_gone(error):
    # The reviewers run as this same user, so a folder this user cannot read is no leak.
    if not isinstance(error, (PermissionError, FileNotFoundError)):
        raise error


def credential_named_files_missing_from_the_list(home):
    """Every file under home outside the log-store whose name matches CREDENTIAL_FILE_NAME_PATTERNS, unlisted."""
    known = listed_or_ignored_files(home)
    found = []
    for directory, subdirectories, files in os.walk(home, onerror=_raise_unless_unreadable_or_gone):
        subdirectories[:] = [name for name in subdirectories if Path(directory) / name != home / "nedsnodes-logs"]
        found += [Path(directory) / name for name in files
                  if any(fnmatch.fnmatchcase(name, pattern) for pattern in cell_common.CREDENTIAL_FILE_NAME_PATTERNS)
                  and Path(directory) / name not in known]
    return sorted(found)


def main(argv=None):
    argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter).parse_args(argv)
    home = Path.home()
    try:
        found = credential_named_files_missing_from_the_list(home)
    except OSError as error:
        text = (f"The search of {home} for files named {NAME_PATTERNS} missing from CREDENTIAL_FILES_ON_NED_BOX ended "
                f"before it had looked everywhere: {error!r}")
        print(text, file=sys.stderr)
        try:
            user_alerts.user_alert_write_to_pending(FAILED_TITLE, text, FAILED_ACTION)
        except OSError as alert_error:
            print(f"The user-alert saying so could not be written either, so no alert reached pending/: "
                  f"{alert_error!r}", file=sys.stderr)
        return 1
    if not found:
        print(f"The search found no file named {NAME_PATTERNS} under {home} that CREDENTIAL_FILES_ON_NED_BOX in "
              f"nn-systems/cold-read/cold-read-cell-common.py leaves out, outside the log-store {home / 'nedsnodes-logs'}.")
        return 0
    text = (f"Each file below is named {NAME_PATTERNS} and is missing from CREDENTIAL_FILES_ON_NED_BOX in "
            "nn-systems/cold-read/cold-read-cell-common.py, so on ned-box the Claude, Codex and agy programs that "
            "the cold-read-cells and task programs start can read it:\n"
            + "\n".join(str(path) for path in found))
    print(text)
    try:
        alert_id = user_alerts.user_alert_write_to_pending(FOUND_TITLE, text, FOUND_ACTION)
    except OSError as error:
        print(f"The user-alert naming these files could not be written, so no alert reached pending/: {error!r}",
              file=sys.stderr)
        return 1
    print(f"This program wrote user-alert {alert_id} into the user-alerts pending/ folder.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
