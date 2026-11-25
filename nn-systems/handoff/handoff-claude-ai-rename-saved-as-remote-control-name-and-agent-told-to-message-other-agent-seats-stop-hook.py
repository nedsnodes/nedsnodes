#!/usr/bin/env python3
"""At each turn's end, store a claude.ai rename and tell the agent to tell the other agent-seats.

A Stop hook. In the agent-session a handoff-supervisor launched, and not in a child session that
inherited its variables, it compares the transcript's latest
custom-title with the agent-seat's stored Remote Control name. On a difference it stores the title
and prints {"hookSpecificOutput": {"hookEventName": "Stop", "additionalContext": <instruction>}}.

A fault, such as stdin that is not a JSON object: one line on stderr naming the hook and the
fault, nothing on stdout, exit 1, which Claude Code records as a non-blocking error.
"""

import importlib.util
import json
import os
import sys
from pathlib import Path

PROGRAM = "handoff-claude-ai-rename-saved-as-remote-control-name-and-agent-told-to-message-other-agent-seats-stop-hook"
HANDOFF_SUPERVISOR_AGENT_NAME_ENVIRONMENT_VARIABLE = "NEDSNODES_HANDOFF_SUPERVISOR_AGENT_NAME"
HANDOFF_SUPERVISOR_SESSION_ID_ENVIRONMENT_VARIABLE = "NEDSNODES_HANDOFF_SUPERVISOR_SESSION_ID"

_common_specification = importlib.util.spec_from_file_location(
    "handoff_remote_control_name_common",
    Path(__file__).with_name("handoff-agent-seat-remote-control-name-stored-after-claude-ai-session-rename-common.py"))
remote_control_name_common = importlib.util.module_from_spec(_common_specification)
_common_specification.loader.exec_module(remote_control_name_common)

_stop_hooks_stay_silent_rule_specification = importlib.util.spec_from_file_location(
    "claude_code_stop_hooks_stay_silent_while_agent_answers_a_stop_hook_rule_common",
    Path(__file__).resolve().parents[1] / "general-tools"
    / "claude-code-stop-hooks-stay-silent-while-agent-answers-a-stop-hook-rule-common.py")
stop_hooks_stay_silent_rule = importlib.util.module_from_spec(_stop_hooks_stay_silent_rule_specification)
_stop_hooks_stay_silent_rule_specification.loader.exec_module(stop_hooks_stay_silent_rule)

# Messages below follow docs/nedsnodes-wiki/nedsnodes-how-to-write-a-tool-message-to-agent-such-as-a-hook-refusal-or-script-error.md.
REMOTE_CONTROL_RENAMED_REMINDER_MESSAGE = (
    "[rule handoff-remote-control-name-changed-in-claude-ai-tell-other-agent-seats] {instruction}")

HOOK_FAILED_MESSAGE = (
    PROGRAM + ": a claude.ai rename of this agent-seat, if there was one, was not stored, because "
    "the hook failed: {error}. Nothing needs doing now: the hook tries again at the next turn's end, "
    "and the handoff-supervisor checks for a rename again at the session-handoff.")


def main() -> int:
    try:
        payload = json.loads(sys.stdin.read())
        if not isinstance(payload, dict):
            raise ValueError("the input on the hook's stdin is JSON, but not an object")
        if stop_hooks_stay_silent_rule.stop_hook_stays_silent_while_agent_answers_a_stop_hook(payload):
            return 0
        agent_seat = os.environ.get(HANDOFF_SUPERVISOR_AGENT_NAME_ENVIRONMENT_VARIABLE, "").strip()
        transcript_path = payload.get("transcript_path")
        if not agent_seat or not isinstance(transcript_path, str) or not transcript_path:
            return 0
        # A child claude session inherits the supervisor's variables; its own title is not the agent-seat's name.
        if payload.get("session_id") != os.environ.get(HANDOFF_SUPERVISOR_SESSION_ID_ENVIRONMENT_VARIABLE):
            return 0
        rename = remote_control_name_common.handoff_remote_control_name_save_when_transcript_custom_title_changed_and_return_rename(
            agent_seat, transcript_path)
    except (OSError, ValueError) as error:
        print(HOOK_FAILED_MESSAGE.format(error=error), file=sys.stderr)
        return 1
    if rename:
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "Stop",
            "additionalContext": REMOTE_CONTROL_RENAMED_REMINDER_MESSAGE.format(
                instruction=remote_control_name_common.handoff_remote_control_rename_message_other_agent_seats_instruction_build(rename)),
        }}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
