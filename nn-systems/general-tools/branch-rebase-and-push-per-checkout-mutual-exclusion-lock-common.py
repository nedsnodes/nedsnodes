#!/usr/bin/env python3
"""One lock per git checkout, so that a Stop hook's rebase of its branch and another Stop hook's push of
it never run at once.

Claude Code runs a Stop group's hooks in parallel. scripts/checkout-freshness-catch-up.py rebases a
never-pushed branch, and
nn-systems/general-tools/agent-seat-owned-nn-topic-branches-push-and-draft-pr-open-stop-hook.py
pushes it. A push that reads the branch mid-rebase sends the old commits, and the branch is then
split between origin and the checkout. Each hook holds this lock: catch-up from deciding the branch
was never pushed until its rebase ends, the push hook around its `git push`.
"""

import contextlib
import fcntl
import os
import time
from pathlib import Path

LOCK_FILE_NAME = "nn-branch-rebase-and-push.lock"
POLL_SECONDS = 0.1


@contextlib.contextmanager
def branch_rebase_and_push_per_checkout_mutual_exclusion_lock(git_directory, wait_seconds):
    """Yield True while this process holds the lock of the checkout whose `git rev-parse
    --absolute-git-dir` is git_directory, or False, holding nothing, when another process held it
    for all of wait_seconds."""
    descriptor = os.open(Path(git_directory) / LOCK_FILE_NAME, os.O_CREAT | os.O_RDWR, 0o644)
    try:
        deadline = time.monotonic() + max(wait_seconds, 0)
        while True:
            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    yield False
                    return
                time.sleep(POLL_SECONDS)
        try:
            yield True
        finally:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
    finally:
        os.close(descriptor)
