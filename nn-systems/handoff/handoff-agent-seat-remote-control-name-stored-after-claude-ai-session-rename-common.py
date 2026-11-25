#!/usr/bin/env python3
"""The Remote Control name an agent-seat keeps across session-handoffs after a claude.ai rename.

A rename in claude.ai reaches an agent-session as a custom-title record in its transcript. The
name is stored in ~/.claude/handoffs/<agent-seat>-remote-control-name; an agent-seat with no such
file answers to its agent-seat name. A transcript with no custom-title record changes nothing.
"""

import json
import os
from pathlib import Path
from typing import NamedTuple, Optional

REMOTE_CONTROL_NAME_FILE_SUFFIX = "-remote-control-name"
CUSTOM_TITLE_RECORD_TYPE = "custom-title"

# Messages below follow docs/nedsnodes-wiki/nedsnodes-how-to-write-a-tool-message-to-agent-such-as-a-hook-refusal-or-script-error.md.
REMOTE_CONTROL_RENAME_LINE_TEMPLATE = "{old_name} is now {new_name} in Remote Control; message it there."
REMOTE_CONTROL_RENAME_INSTRUCTION_TEMPLATE = (
    "The user renamed this agent-seat in claude.ai from {old_name} to {new_name}. Its sessions "
    "now start under the new name, so a message sent to the old name may reach no one.\n"
    "With SendMessage, send this line, word for word, to each other session ListAgents lists "
    "that is not offline:\n"
    "{line}\n"
    "When several live rows share a name, send to each, addressed as `<name> [<ref>]` with the "
    "ref that row shows."
)


class RemoteControlRename(NamedTuple):
    old_name: str
    new_name: str


def remote_control_name_file_path(handoff_directory: Path, agent_seat: str) -> Path:
    return handoff_directory / f"{agent_seat}{REMOTE_CONTROL_NAME_FILE_SUFFIX}"


def handoff_remote_control_name_read_stored_or_default_to_agent_seat_name(handoff_directory: Path, agent_seat: str) -> str:
    """Return the stored name, or the agent-seat name when none is stored; raise OSError if unreadable."""
    try:
        stored = remote_control_name_file_path(handoff_directory, agent_seat).read_text(
            encoding="utf-8").strip()
    except FileNotFoundError:
        return agent_seat
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
        handoff_directory: Path, agent_seat: str, transcript_path) -> Optional[RemoteControlRename]:
    """Store a title that differs from the stored name and return the rename, else return None.

    Raise OSError when the transcript exists but cannot be read, or the name cannot be stored."""
    try:
        title = session_title_from_transcript(transcript_path)
    except FileNotFoundError:
        return None
    if not title:
        return None
    old_name = handoff_remote_control_name_read_stored_or_default_to_agent_seat_name(handoff_directory, agent_seat)
    if title == old_name:
        return None
    path = remote_control_name_file_path(handoff_directory, agent_seat)
    # The Stop hook and the handoff-supervisor can both store; a reader must never see half a name.
    temporary_path = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    temporary_path.write_text(title + "\n", encoding="utf-8")
    os.replace(temporary_path, path)
    return RemoteControlRename(old_name, title)


def handoff_remote_control_rename_message_other_agent_seats_instruction_build(rename: RemoteControlRename) -> str:
    return REMOTE_CONTROL_RENAME_INSTRUCTION_TEMPLATE.format(
        old_name=rename.old_name, new_name=rename.new_name,
        line=REMOTE_CONTROL_RENAME_LINE_TEMPLATE.format(
            old_name=rename.old_name, new_name=rename.new_name))
