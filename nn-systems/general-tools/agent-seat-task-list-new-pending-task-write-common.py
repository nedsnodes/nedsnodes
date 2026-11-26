#!/usr/bin/env python3
"""Write a new pending task into an agent-seat's Claude Code task list, for a program that hands
an agent-seat work.

An agent-seat's task list is the directory `~/.claude/tasks/nedsnodes-<seat>-tasks/`; each task
is `<id>.json` there, and `.highwatermark` holds the highest id Claude Code has used, deleted
tasks included. Every program that writes `.highwatermark` writes it with this module.

Load it by path, under the snake_case form of its file name:

    spec = importlib.util.spec_from_file_location(
        "agent_seat_task_list_new_pending_task_write_common", <path>)
"""

import json
import os
import re
import tempfile
from pathlib import Path

TASK_FILE_NAME_PATTERN = re.compile(r"[1-9][0-9]*\.json")
TASK_HIGH_WATER_MARK_FILE_NAME = ".highwatermark"
# The open-pull-request watcher writes this subject, and the idle sweep wakes merge-lane-2 on it.
AGENT_SEAT_TASK_LIST_MERGE_LANE_2_READ_PULL_REQUEST_EVENTS_TASK_SUBJECT_LINE = (
    "Read the new pull-request events in the watcher's event file")


def agent_seat_task_list_new_pending_task_write(list_directory, subject, description, metadata=None):
    """Write a new pending task into the list, with metadata when given; return its id. Raises
    OSError.

    The id is one more than the highest of the list's task ids and its .highwatermark, as
    Claude Code numbers a new task; the file is linked into place only where no file of that
    name exists, so a task Claude Code creates at the same moment is not overwritten. A list
    directory that does not exist raises FileNotFoundError: a caller whose agent-seat may have
    made no task yet creates the directory first.
    """
    list_directory = Path(list_directory)
    if not list_directory.is_dir():
        raise FileNotFoundError(f"the task list directory {list_directory} does not exist")
    highest = 0
    for path in list_directory.iterdir():
        if TASK_FILE_NAME_PATTERN.fullmatch(path.name):
            highest = max(highest, int(path.stem))
    mark_path = list_directory / TASK_HIGH_WATER_MARK_FILE_NAME
    mark = mark_path.read_text(encoding="utf-8").strip() if mark_path.is_file() else ""
    if mark.isdigit():
        highest = max(highest, int(mark))
    task_id = highest + 1
    with tempfile.NamedTemporaryFile("w", dir=list_directory, prefix=".task-", suffix=".partial",
                                     delete=False, encoding="utf-8") as partial:
        partial_path = Path(partial.name)
    try:
        while True:
            task = {"id": str(task_id), "subject": subject, "description": description,
                    "status": "pending", "blocks": [], "blockedBy": []}
            if metadata is not None:
                task["metadata"] = metadata
            partial_path.write_text(json.dumps(task, indent=2), encoding="utf-8")  # pragma: no mutate, the indent only changes whitespace, and Claude Code and every program here read the task file as JSON
            try:
                os.link(partial_path, list_directory / f"{task_id}.json")
                break
            except FileExistsError:
                task_id += 1
    finally:
        partial_path.unlink(missing_ok=True)
    agent_seat_task_list_high_water_mark_write(list_directory, task_id)
    return task_id


def agent_seat_task_list_high_water_mark_write(list_directory, value):
    """Replace the list's .highwatermark with value; raises OSError, leaving no partial file.

    Each call writes through a partial file of its own, because writers on one list can run at
    the same moment: the handoff writer's prune and a program handing the agent-seat a task.
    """
    list_directory = Path(list_directory)
    descriptor, partial_name = tempfile.mkstemp(
        dir=list_directory, prefix=TASK_HIGH_WATER_MARK_FILE_NAME + "-", suffix=".partial")
    partial_path = Path(partial_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as partial:
            partial.write(str(value))
        os.replace(partial_path, list_directory / TASK_HIGH_WATER_MARK_FILE_NAME)
    except OSError:
        partial_path.unlink(missing_ok=True)
        raise
