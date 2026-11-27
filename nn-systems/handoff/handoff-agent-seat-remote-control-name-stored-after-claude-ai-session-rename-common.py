#!/usr/bin/env python3
"""The Remote Control label an agent-seat keeps across session-handoffs, and the addresses its agent-session holds.

The handoff-supervisor launches each agent-session with the agent-seat name as its address, the name the other
agent-seats message, and with the label stored in ~/.claude/handoffs/<agent-seat>-remote-control-name as the
name Remote Control lists it under; with no such file, or an empty one, the label is the agent-seat name. The
user, or an agent-seat for him, may write a label into that file by hand. It takes effect at the agent-seat's
next launch and is announced to no one, because it changes no address.

A rename in claude.ai reaches an agent-session as a custom-title record in its transcript, and changes its
address until its next launch; it is stored as the label. Every launch, a resume included, writes a
custom-title record of the launched address too, so a rename is a title other than the address the
agent-session holds: the last name in the record of addresses it was announced under since its launch. Both
files are under ~/.claude/handoffs whatever --handoff-dir the handoff-supervisor was given, because the Stop
hook, the status line and the Remote Control watcher, which read them too, are not told that flag.
"""

import json
import os
from pathlib import Path
from typing import NamedTuple, Optional

REMOTE_CONTROL_NAME_FILE_SUFFIX = "-remote-control-name"
# Every address the other agent-seats may know this agent-seat by since its launch: the launched
# address, then each claude.ai rename after it, one per line.
REMOTE_CONTROL_NAMES_ANNOUNCED_SINCE_LAUNCH_FILE_SUFFIX = "-remote-control-names-announced-since-launch"
CUSTOM_TITLE_RECORD_TYPE = "custom-title"

# Messages below follow docs/nedsnodes-wiki/nedsnodes-how-to-write-a-tool-message-to-agent-such-as-a-hook-refusal-or-script-error.md.
REMOTE_CONTROL_RENAME_LINE_TEMPLATE = "The agent-seat {old_name} is now {new_name} in Remote Control; send it messages under that name."
REMOTE_CONTROL_RENAMED_IN_CLAUDE_AI_REASON_TEMPLATE = (
    "The user renamed this agent-session in claude.ai from {old_names} to {new_name}. Until its next "
    "session-handoff the other agent-seats must message it as {new_name}, so a message sent to "
    "{the_old_name} may reach no one.")
REMOTE_CONTROL_ADDRESS_GIVEN_BACK_AT_LAUNCH_REASON_TEMPLATE = (
    "This agent-session was launched under its agent-seat name, {new_name}, and the other agent-seats "
    "message it as {new_name}: a claude.ai rename of an earlier agent-session of this agent-seat changes "
    "only the label Remote Control lists this one under. A message sent to {the_old_name}, "
    "{old_names}, may reach no one.")
REMOTE_CONTROL_OLD_NAME_LINES_SEND_INSTRUCTION_TEMPLATE = (
    "{reason}\n"
    "With SendMessage, send {this_line}, word for word, to each other session ListAgents lists "
    "that is not offline:\n"
    "{lines}\n"
    "When several live rows share a name, send to each, addressed as `<name> [<ref>]` with the "
    "ref that row shows.")


class RemoteControlRename(NamedTuple):
    old_name: str
    new_name: str


def remote_control_name_file_path(agent_seat: str) -> Path:
    # Path.home() at each call, so a test's HOME decides the directory.
    return Path.home() / ".claude" / "handoffs" / f"{agent_seat}{REMOTE_CONTROL_NAME_FILE_SUFFIX}"


def handoff_agent_seat_remote_control_names_it_was_announced_under_since_its_launch_file_path_build(agent_seat: str) -> Path:
    return Path.home() / ".claude" / "handoffs" / f"{agent_seat}{REMOTE_CONTROL_NAMES_ANNOUNCED_SINCE_LAUNCH_FILE_SUFFIX}"


def handoff_agent_seat_remote_control_names_it_was_announced_under_since_its_launch_reset_to_launched_name(agent_seat: str, launched_name: str) -> None:
    """Start the record of announced names afresh with the launched address; raise OSError on failure."""
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
    """Return the stored label, or the agent-seat name when none is stored; raise OSError if unreadable."""
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
    """Store a title that differs from the address the agent-session holds as the label, and return
    the rename from that address; else return None.

    Raise OSError when the transcript exists but cannot be read, or the name cannot be stored."""
    try:
        title = session_title_from_transcript(transcript_path)
    except FileNotFoundError:
        return None
    if not title:
        return None
    # Compared with the address, not the label: each launch's own custom-title record is the
    # agent-seat name, and must not overwrite a label written by hand.
    announced_names = handoff_agent_seat_remote_control_names_it_was_announced_under_since_its_launch_read(agent_seat)
    old_name = announced_names[-1] if announced_names else agent_seat
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


def _old_name_lines_send_instruction_build(reason_template: str, old_names: list, new_name: str) -> str:
    several = len(old_names) > 1
    reason = reason_template.format(
        old_names=", then ".join(old_names), new_name=new_name,
        the_old_name="an old name" if several else "the old name")
    return REMOTE_CONTROL_OLD_NAME_LINES_SEND_INSTRUCTION_TEMPLATE.format(
        reason=reason, this_line="these lines" if several else "this line",
        lines="\n".join(REMOTE_CONTROL_RENAME_LINE_TEMPLATE.format(old_name=old_name, new_name=new_name)
                        for old_name in old_names))


def handoff_remote_control_rename_message_other_agent_seats_instruction_build(rename: RemoteControlRename) -> str:
    return _old_name_lines_send_instruction_build(
        REMOTE_CONTROL_RENAMED_IN_CLAUDE_AI_REASON_TEMPLATE, [rename.old_name], rename.new_name)


def handoff_agent_seat_address_given_back_at_launch_old_names_to_announce(agent_seat: str, announced_names: list) -> list:
    """The addresses, oldest first and each once, that the others may know the agent-seat by and
    that a launch under its agent-seat name gives back."""
    old_names = []
    for name in announced_names:
        if name != agent_seat and name not in old_names:
            old_names.append(name)
    return old_names


def handoff_agent_seat_address_given_back_at_launch_message_other_agent_seats_instruction_build(old_names: list, agent_seat: str) -> str:
    """The instruction to send one line for each address the launch gave back, oldest first."""
    return _old_name_lines_send_instruction_build(
        REMOTE_CONTROL_ADDRESS_GIVEN_BACK_AT_LAUNCH_REASON_TEMPLATE, old_names, agent_seat)
