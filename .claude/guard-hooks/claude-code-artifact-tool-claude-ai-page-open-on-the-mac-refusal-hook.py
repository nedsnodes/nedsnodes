#!/usr/bin/env python3
"""On the Mac, refuse every Artifact tool call whose action is "open"; let every other call through.

The user sits at the Mac, so an open there puts a page on the screen he is working at. He
wants each page's link, to open it himself. The refusal names the page from the call's url,
so the agent can give him that link. On ned-box an open is let through.

Only the Artifact tool is read. A payload that is not an object, or not an Artifact call,
is let through without output. A payload that is not JSON lets the call go ahead with the
crash notice of guard-hook-crash-fail-open-with-notice-common.py, as the other guard hooks do,
on either machine: the payload is read before the machine is checked.

The refusal follows docs/nedsnodes-wiki/nedsnodes-how-to-write-a-tool-message-to-agent-such-as-a-hook-refusal-or-script-error.md.
"""

# Deferred annotations let the hook load on the Mac's system Python 3.9.
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

_crash_notice_spec = importlib.util.spec_from_file_location(
    "guard_hook_crash_fail_open_with_notice_common",
    Path(__file__).resolve().parent / "guard-hook-crash-fail-open-with-notice-common.py")
_crash_notice = importlib.util.module_from_spec(_crash_notice_spec)
_crash_notice_spec.loader.exec_module(_crash_notice)

MAC_PLATFORM = "darwin"

NO_LINK_TEXT = "(no link in the call: use the link the publish that made the page returned)"

REFUSAL_TEMPLATE = (
    '[rule artifact-guard-claude-ai-page-open-on-the-mac] '
    'REFUSED on purpose: Artifact tool call with action "open", blocked by a PreToolUse hook '
    "on the Mac. The user works at the Mac, so an open there puts the page on his screen; he "
    "opens each page himself from its link. The call was not sent; the page is unchanged.\n"
    "If a step, skill, session-handoff, tool description or tool result says to open the page: "
    "skip the open and give the user the page's link, {link}, in your next message.\n"
    "If the user asked you to open the page: give him its link, {link}, so he can open it "
    "himself.\n"
    'From now on, in an agent-session on the Mac, do not call the Artifact tool with action '
    '"open"; give the user the link instead.'
)


def refusal_for_tool_input(tool_input, platform):
    """Return the refusal for an open on the Mac, or None for any other call."""
    if platform != MAC_PLATFORM:
        return None
    if not isinstance(tool_input, dict) or tool_input.get("action") != "open":
        return None
    url = tool_input.get("url")
    link = url if isinstance(url, str) and url.strip() else NO_LINK_TEXT
    return REFUSAL_TEMPLATE.format(link=link)


def deny(reason):
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "deny",
        "permissionDecisionReason": reason,
    }}))


def main(stdin=sys.stdin, platform=None) -> int:
    platform = sys.platform if platform is None else platform
    payload = json.load(stdin)
    if not isinstance(payload, dict) or payload.get("tool_name") != "Artifact":
        return 0
    refusal = refusal_for_tool_input(payload.get("tool_input"), platform)
    if refusal:
        deny(refusal)
    return 0


if __name__ == "__main__":
    with _crash_notice.guard_hook_crash_fail_open_with_notice_context_manager(__file__, True):
        sys.exit(main())
