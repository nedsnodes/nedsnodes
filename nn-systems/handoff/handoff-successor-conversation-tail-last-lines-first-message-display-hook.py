#!/usr/bin/env python3
"""Show the user the end of the last session's dialog above a session-handoff successor's first message.

A MessageDisplay hook, which Claude Code runs on each batch of lines of an assistant message as
it is drawn in the terminal. When the handoff-supervisor launched this agent-session as a
successor, it wrote the conversation-tail's last lines to
<session id>-conversation-tail-last-lines-for-first-message-display.md in ~/.claude/handoffs/.
On the first batch of the first assistant message with text, the hook returns that file's text
followed by the batch as the displayContent, which Claude Code draws in the batch's place while
the transcript and the agent keep the original, then deletes the file, so the lines are shown
once. Every other call finds no file and prints nothing, so the original is drawn.

Runs on every batch of every message, and Claude Code holds the batch until it returns: it does
nothing before checking for the file.

A fault, such as stdin that is not a JSON object: Python's traceback on stderr, nothing on
stdout, exit 1; Claude Code then draws the original text.
"""

import json
import sys
from pathlib import Path

HANDOFF_DIRECTORY = Path.home() / ".claude" / "handoffs"
CONVERSATION_TAIL_LAST_LINES_DISPLAY_FILE_SUFFIX = (
    "-conversation-tail-last-lines-for-first-message-display.md")


def conversation_tail_last_lines_display_file_path_for_session_id(handoff_directory: Path, session_id: str) -> Path:
    return handoff_directory / f"{session_id}{CONVERSATION_TAIL_LAST_LINES_DISPLAY_FILE_SUFFIX}"


def main() -> int:
    batch = json.load(sys.stdin)
    if batch["index"] != 0:
        return 0
    path = conversation_tail_last_lines_display_file_path_for_session_id(HANDOFF_DIRECTORY, batch["session_id"])
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return 0
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "MessageDisplay", "displayContent": text + batch["delta"]}}))
    path.unlink()
    return 0


if __name__ == "__main__":
    sys.exit(main())
