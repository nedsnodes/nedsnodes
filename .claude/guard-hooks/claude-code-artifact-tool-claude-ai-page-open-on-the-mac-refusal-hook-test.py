#!/usr/bin/env python3
"""Tests for .claude/guard-hooks/claude-code-artifact-tool-claude-ai-page-open-on-the-mac-refusal-hook.py.

Each case drives main() with the JSON payload the harness sends and the machine's platform
given, so that both the Mac's and ned-box's behaviour run on either machine; one case pipes a
payload into the hook as a real process, on the machine the suite runs on.

Run: python3 .claude/guard-hooks/claude-code-artifact-tool-claude-ai-page-open-on-the-mac-refusal-hook-test.py
Prints one line per case and exits non-zero if any case fails.
"""

import contextlib
import importlib.util
import io
import json
import subprocess
import sys
from pathlib import Path

HOOK_SCRIPT = Path(__file__).with_name("claude-code-artifact-tool-claude-ai-page-open-on-the-mac-refusal-hook.py")
_spec = importlib.util.spec_from_file_location("artifact_open_on_the_mac_refusal", HOOK_SCRIPT)
hook = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(hook)

PAGE_LINK = "https://claude.ai/artifact/WHyP4PeJM2iHEAAk2cPQTg"
MAC = "darwin"
NED_BOX = "linux"

failures = []


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


def run_main(stdin_text, platform):
    """Return (exit code, stdout) of main() on the given stdin and platform."""
    stdout = io.StringIO()
    with contextlib.redirect_stdout(stdout):
        code = hook.main(stdin=io.StringIO(stdin_text), platform=platform)
    return code, stdout.getvalue().strip()


def deny_reason_of(code, text):
    if code != 0:
        return f"<exit {code}>"
    if not text:
        return None
    output = json.loads(text)["hookSpecificOutput"]
    if output.get("hookEventName") != "PreToolUse" or output.get("permissionDecision") != "deny":
        return f"<unexpected output {text}>"
    return output.get("permissionDecisionReason")


def refusal(tool_input, platform=MAC, tool_name="Artifact"):
    """Return the deny reason the hook gives, None when it lets the call through."""
    return deny_reason_of(*run_main(json.dumps({"tool_name": tool_name, "tool_input": tool_input}), platform))


reason = refusal({"action": "open", "url": PAGE_LINK})
check("on the Mac, an open is refused", reason is not None and reason.startswith(
    '[rule artifact-guard-claude-ai-page-open-on-the-mac] '
    'REFUSED on purpose: Artifact tool call with action "open", blocked by a PreToolUse hook on the Mac.'),
    reason)
check("the refusal says why: the user does not want pages put on his screen, even one he asked for",
      reason is not None and "does not want agents putting pages on his screen there, even a page he "
      "asked to see; he opens each page himself from its link." in reason, reason)
check("the refusal says the open did not happen", reason is not None
      and "The open did not happen; the claude.ai page the call named is unchanged." in reason, reason)
check("the refusal tells the agent, whatever asked for the open, to give the link and carry on",
      reason is not None and "your own choice or the user himself: give the user the page's link, "
      f"{PAGE_LINK}, in your next message to him, count the open as done, and carry on;" in reason, reason)
check("the refusal tells the agent not to open the page another way", reason is not None
      and "do not open the page another way, such as with the shell's `open` command." in reason, reason)
check("the refusal tells a subagent to pass the link up", reason is not None
      and "If you are a subagent: put the link in your report to the agent that dispatched you" in reason,
      reason)
check("the refusal says what to do from now on", reason is not None
      and 'do not call the Artifact tool with action "open"; give the user the link instead.' in reason,
      reason)
check("the refusal has its four lines", reason is not None and len(reason.splitlines()) == 4, reason)

for case_name, tool_input in [
        ("an open with no url", {"action": "open"}),
        ("an open with an empty url", {"action": "open", "url": "  "}),
        ("an open with a url that is not text", {"action": "open", "url": 7})]:
    reason = refusal(tool_input)
    check(f"on the Mac, {case_name} is refused, saying the call has no link", reason is not None
          and f"the page's link, {hook.NO_LINK_TEXT}, in your next message to him" in reason, reason)

check("on ned-box, an open is let through", refusal({"action": "open", "url": PAGE_LINK}, NED_BOX) is None,
      refusal({"action": "open", "url": PAGE_LINK}, NED_BOX))

for case_name, tool_input in [
        ("a publish with no action", {"file_path": "/tmp/page.html"}),
        ("an explicit publish", {"action": "publish", "file_path": "/tmp/page.html", "url": PAGE_LINK}),
        ("a read", {"action": "read", "url": PAGE_LINK}),
        ("a delete", {"action": "delete", "url": PAGE_LINK}),
        ("a list", {"action": "list"}),
        ("a tool_input that is not an object", "open")]:
    check(f"on the Mac, {case_name} is let through", refusal(tool_input) is None, refusal(tool_input))

check("on the Mac, an open by another tool is let through",
      refusal({"action": "open", "url": PAGE_LINK}, tool_name="Bash") is None)

for platform in (MAC, NED_BOX):
    code, text = run_main("[1, 2]", platform)
    check(f"on {platform}, a JSON payload that is not an object is let through with exit 0 and no output",
          code == 0 and text == "", f"exit {code}, output {text!r}")
    try:
        run_main("not JSON", platform)
        raised = None
    except json.JSONDecodeError as error:
        raised = error
    check(f"on {platform}, a payload that is not JSON raises, so the crash notice reports it",
          raised is not None)

process = subprocess.run(
    [sys.executable, str(HOOK_SCRIPT)],
    input=json.dumps({"tool_name": "Artifact", "tool_input": {"action": "open", "url": PAGE_LINK}}),
    capture_output=True, text=True, timeout=30)
process_reason = deny_reason_of(process.returncode, process.stdout.strip())
if sys.platform == MAC:
    check("run as a process on the Mac, an open exits 0 with a deny", process_reason is not None
          and process_reason.startswith("[rule artifact-guard-claude-ai-page-open-on-the-mac]"),
          f"exit {process.returncode}, stdout {process.stdout!r}, stderr {process.stderr!r}")
else:
    check(f"run as a process on {sys.platform}, an open exits 0 with no output",
          process.returncode == 0 and process.stdout == "",
          f"exit {process.returncode}, stdout {process.stdout!r}, stderr {process.stderr!r}")

if failures:
    print(f"\n{len(failures)} case(s) failed")
    sys.exit(1)
print("\nall cases passed")
