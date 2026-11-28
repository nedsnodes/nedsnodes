#!/usr/bin/env python3
"""Show the user, once per handoff request, that this agent-session is handing off.

A UserPromptSubmit hook, run each time the user sends a message, a message queued
while the agent is busy included. When the threshold hook's handoff-asked marker
file for this agent-session exists, the hook prints {"systemMessage": <line>},
which Claude Code shows the user, in the terminal and on the claude.ai page, and
not the agent. The message itself always goes through unchanged.

The line names the new agent-session by this agent-session's current title, the
customTitle of the last custom-title record in its transcript, which is the name
claude.ai shows and changes when the user renames the agent-session there. With
no such record, or a transcript that cannot be read, the line names the agent-seat
the handoff-supervisor launched the agent-session under, when this is that launched
agent-session and not a child started from its shell, and failing that, says
"this agent-seat's new session".

The line is shown once per marker file, because a refused handoff leaves the
marker file in place and a wrong notice must not repeat on every message. Before
printing, the hook writes the marker file's modification time, in nanoseconds,
into a file beside it, named for the marker file; a marker file written later, after a compaction
deleted the first, has another modification time, so the line is shown again.

A fault, such as stdin that is not a JSON object: one line on stderr naming the
hook and the fault, nothing on stdout, exit 1, which Claude Code records as a
non-blocking error. Exit 2 would block the user's message and is never used.
"""

import importlib.util
import json
import os
import pathlib
import sys

# Messages below follow docs/nedsnodes-wiki/nedsnodes-how-to-write-a-tool-message-to-agent-such-as-a-hook-refusal-or-script-error.md.

PROGRAM = "handoff-asked-stop-typing-user-notice-user-prompt-submit-hook"

THRESHOLD_HOOK_PATH = (pathlib.Path(__file__).resolve().parents[2]
                       / "scripts" / "handoff-context-threshold-hook.py")
LAUNCHED_AGENT_SESSION_ENVIRONMENT_PATH = pathlib.Path(__file__).resolve().with_name(
    "handoff-supervisor-launched-agent-session-environment-variable-names-common.py")
REMOTE_CONTROL_NAME_COMMON_PATH = pathlib.Path(__file__).resolve().with_name(
    "handoff-agent-seat-remote-control-name-stored-after-claude-ai-session-rename-common.py")

SHOWN_RECORD_SUFFIX = "-user-notice-shown"

# {name} is the Remote Control name the successor keeps; claude.ai lists the successor under it.
HANDOFF_ASKED_STOP_TYPING_WITH_NEW_SESSION_NAME_USER_NOTICE_TEMPLATE = (
    "This session is handing off; stop typing here. Use the new {name} session when it"
    " appears in claude.ai.")
HANDOFF_ASKED_STOP_TYPING_WITHOUT_NEW_SESSION_NAME_USER_NOTICE = (
    "This session is handing off; stop typing here. Use this agent-seat's new session when it"
    " appears in claude.ai.")

HOOK_FAILED_MESSAGE = (
    PROGRAM + ": the user was not shown that this agent-session is handing off, because the"
    " hook failed; the user's message went through as usual: {error}")


def module_from_path(module_name, path):
    specification = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def hook_payload_from_stdin() -> dict:
    payload = json.loads(sys.stdin.read())
    if not isinstance(payload, dict):
        raise ValueError("the input on the hook's stdin is JSON, but not an object")
    return payload


def launched_agent_seat_name(session_id) -> str:
    launched = module_from_path("handoff_supervisor_launched_agent_session_environment_variable_names_common",
                                LAUNCHED_AGENT_SESSION_ENVIRONMENT_PATH)
    return launched.handoff_supervisor_launched_agent_session_agent_seat_name_or_empty_for_another_session(
        os.environ, session_id)


def new_session_name(transcript_path_text, session_id) -> str:
    """Return the name the line gives the new agent-session, or "" when none is found."""
    remote_control_name_common = module_from_path("handoff_remote_control_name_common",
                                                  REMOTE_CONTROL_NAME_COMMON_PATH)
    if isinstance(transcript_path_text, str) and transcript_path_text:
        try:
            title = remote_control_name_common.session_title_from_transcript(transcript_path_text)
        except OSError:
            title = ""
        if title:
            return title
    agent_seat = launched_agent_seat_name(session_id)
    if not agent_seat:
        return ""
    # The handoff-supervisor launches the successor under the stored name, as it does here when the file is unreadable.
    try:
        return remote_control_name_common.handoff_remote_control_name_read_stored_or_default_to_agent_seat_name(agent_seat)
    except OSError:
        return agent_seat


def user_notice(name: str) -> str:
    if name:
        return HANDOFF_ASKED_STOP_TYPING_WITH_NEW_SESSION_NAME_USER_NOTICE_TEMPLATE.format(name=name)
    return HANDOFF_ASKED_STOP_TYPING_WITHOUT_NEW_SESSION_NAME_USER_NOTICE


def main() -> int:
    try:
        payload = hook_payload_from_stdin()
        session_id = payload.get("session_id")
        if not isinstance(session_id, str) or not session_id:
            return 0
        threshold = module_from_path("handoff_context_threshold_hook", THRESHOLD_HOOK_PATH)
        marker = threshold.handoff_asked_marker_path(session_id)
        try:
            marker_modified = str(marker.stat().st_mtime_ns)
        except FileNotFoundError:
            return 0
        shown_record = marker.with_name(marker.name + SHOWN_RECORD_SUFFIX)
        try:
            if shown_record.read_text(encoding="utf-8").strip() == marker_modified:
                return 0
        except FileNotFoundError:
            pass
        notice = user_notice(new_session_name(payload.get("transcript_path"), session_id))
        shown_record.write_text(marker_modified + "\n", encoding="utf-8")
        print(json.dumps({"systemMessage": notice}))
    except Exception as error:
        print(HOOK_FAILED_MESSAGE.format(error=f"{type(error).__name__}: {error}"), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
