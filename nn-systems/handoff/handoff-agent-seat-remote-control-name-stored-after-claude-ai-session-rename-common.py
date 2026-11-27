#!/usr/bin/env python3
"""The Remote Control name an agent-seat keeps across session-handoffs after a claude.ai rename.

A rename in claude.ai reaches an agent-session as a custom-title record in its transcript. The
name is stored in ~/.claude/handoffs/<agent-seat>-remote-control-name, whatever --handoff-dir the
handoff-supervisor was given, because the Stop hook and the Remote Control watcher, which read and
store it too, are not told that flag. An agent-seat with no such file answers to its agent-seat
name. A transcript with no custom-title record changes nothing.
"""

import json
import os
from pathlib import Path
from typing import NamedTuple, Optional

REMOTE_CONTROL_NAME_FILE_SUFFIX = "-remote-control-name"
# Every name the other agent-seats may know this agent-seat by since its launch: the launched
# name, then each name stored after it, one per line.
REMOTE_CONTROL_NAMES_ANNOUNCED_SINCE_LAUNCH_FILE_SUFFIX = "-remote-control-names-announced-since-launch"
CUSTOM_TITLE_RECORD_TYPE = "custom-title"

# Messages below follow docs/nedsnodes-wiki/nedsnodes-how-to-write-a-tool-message-to-agent-such-as-a-hook-refusal-or-script-error.md.
REMOTE_CONTROL_RENAME_LINE_TEMPLATE = "The agent-seat {old_name} is now {new_name} in Remote Control; send it messages under that name."
REMOTE_CONTROL_RENAME_INSTRUCTION_TEMPLATE = (
    "The user renamed this agent-seat in claude.ai from {old_name} to {new_name}. This "
    "agent-seat's sessions now start under the new name, so a message sent to {the_old_name} may reach no one.\n"
    "With SendMessage, send {this_line}, word for word, to each other session ListAgents lists "
    "that is not offline:\n"
    "{line}\n"
    "When several live rows share a name, send to each, addressed as `<name> [<ref>]` with the "
    "ref that row shows."
)


class RemoteControlRename(NamedTuple):
    old_name: str
    new_name: str


def remote_control_name_file_path(agent_seat: str) -> Path:
    # Path.home() at each call, so a test's HOME decides the directory.
    return Path.home() / ".claude" / "handoffs" / f"{agent_seat}{REMOTE_CONTROL_NAME_FILE_SUFFIX}"


def handoff_agent_seat_remote_control_names_it_was_announced_under_since_its_launch_file_path_build(agent_seat: str) -> Path:
    return Path.home() / ".claude" / "handoffs" / f"{agent_seat}{REMOTE_CONTROL_NAMES_ANNOUNCED_SINCE_LAUNCH_FILE_SUFFIX}"


def handoff_agent_seat_remote_control_names_it_was_announced_under_since_its_launch_reset_to_launched_name(agent_seat: str, launched_name: str) -> None:
    """Start the record of announced names afresh with the launched name; raise OSError on failure."""
    path = handoff_agent_seat_remote_control_names_it_was_announced_under_since_its_launch_file_path_build(agent_seat)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    temporary_path.write_text(launched_name + "\n", encoding="utf-8")
    os.replace(temporary_path, path)


def handoff_agent_seat_remote_control_names_it_was_announced_under_since_its_launch_read(agent_seat: str) -> list:
    """Return the recorded names in order, or [] when none are recorded; raise OSError if unreadable."""
    path = handoff_agent_seat_remote_control_names_it_was_announced_under_since_its_launch_file_path_build(agent_seat)
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return []
    except UnicodeDecodeError as error:
        raise OSError(f"{path} is not UTF-8 text: {error}") from error
    return [line.strip() for line in text.splitlines() if line.strip()]


def handoff_remote_control_name_read_stored_or_default_to_agent_seat_name(agent_seat: str) -> str:
    """Return the stored name, or the agent-seat name when none is stored; raise OSError if unreadable."""
    path = remote_control_name_file_path(agent_seat)
    try:
        stored = path.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return agent_seat
    except UnicodeDecodeError as error:
        # Every caller handles OSError alone; a ValueError would escape them.
        raise OSError(f"{path} is not UTF-8 text: {error}") from error
    return stored or agent_seat


def session_title_from_transcript(transcript_path) -> str:
    """Return the customTitle of the transcript's last custom-title record, or ""."""
    title = ""
    with open(transcript_path, encoding="utf-8", errors="replace") as transcript:
        for line in transcript:
            if CUSTOM_TITLE_RECORD_TYPE not in line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(record, dict) or record.get("type") != CUSTOM_TITLE_RECORD_TYPE:
                continue
            custom_title = record.get("customTitle")
            if isinstance(custom_title, str) and custom_title.strip():
                title = custom_title.strip()
    return title


def handoff_remote_control_name_save_when_transcript_custom_title_changed_and_return_rename(
        agent_seat: str, transcript_path) -> Optional[RemoteControlRename]:
    """Store a title that differs from the stored name and return the rename, else return None.

    Raise OSError when the transcript exists but cannot be read, or the name cannot be stored."""
    try:
        title = session_title_from_transcript(transcript_path)
    except FileNotFoundError:
        return None
    if not title:
        return None
    old_name = handoff_remote_control_name_read_stored_or_default_to_agent_seat_name(agent_seat)
    if title == old_name:
        return None
    path = remote_control_name_file_path(agent_seat)
    path.parent.mkdir(parents=True, exist_ok=True)
    # The Stop hook and the handoff-supervisor can both store; a reader must never see half a name.
    # Whoever stores it is told to announce it, so the others may know the agent-seat by it from now on.
    # Recorded before the store: a failed append then leaves the name unstored, and the next try redoes both.
    with open(handoff_agent_seat_remote_control_names_it_was_announced_under_since_its_launch_file_path_build(agent_seat), "a", encoding="utf-8") as record:
        record.write(title + "\n")
    temporary_path = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    temporary_path.write_text(title + "\n", encoding="utf-8")
    os.replace(temporary_path, path)
    return RemoteControlRename(old_name, title)


def handoff_remote_control_rename_message_other_agent_seats_instruction_build(rename: RemoteControlRename) -> str:
    return handoff_agent_seat_remote_control_rename_from_each_old_name_agent_told_to_message_other_agent_seats_instruction_build(
        [rename.old_name], rename.new_name)


def handoff_agent_seat_remote_control_rename_from_each_old_name_agent_told_to_message_other_agent_seats_instruction_build(old_names: list, new_name: str) -> str:
    """The instruction to send one line for each name the others may still use, oldest first."""
    several = len(old_names) > 1
    return REMOTE_CONTROL_RENAME_INSTRUCTION_TEMPLATE.format(
        old_name=", then ".join(old_names) + ("," if several else ""), new_name=new_name,
        the_old_name="an old name" if several else "the old name",
        this_line="these lines" if several else "this line",
        line="\n".join(REMOTE_CONTROL_RENAME_LINE_TEMPLATE.format(old_name=old_name, new_name=new_name)
                       for old_name in old_names))
