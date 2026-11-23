#!/usr/bin/env python3
"""UserPromptSubmit hook: while an approval-walk is open, copy each message the user typed that is not only an answer
into its walk-minutes, with the time, as WALK_FINDER_FILE's docstring says under COPIED USER MESSAGES.

Only an answer is what ANSWER_HOOK_FILE's parsed_answer reads as a single, all or numbered answer, its `bump` form, or
a navigation word alone. An answer with a condition or a rider holds other words, so it is copied. Copied too is a
message unrelated to the approval-walk, whose outcome is `no change`.

Not copied: a prompt no user typed, as ALERTS_HOOK_FILE's typed_by_user decides; the handoff-supervisor's prompt that
starts a successor or resumes a crashed agent-session, which Claude Code records as typed; and any prompt of an
agent-session no user attends.

The hook never blocks the prompt. When the copy fails, additionalContext says so and what to do. A payload that is not
JSON is a fault: one line on stderr, exit 1, which Claude Code records as a non-blocking error.

Tool-messages-to-agent follow
docs/nedsnodes-wiki/nedsnodes-how-to-write-a-tool-message-to-agent-such-as-a-hook-refusal-or-script-error.md.
"""
import importlib.util
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
CHECKOUT = HERE.parents[2]
WALK_FINDER_FILE = HERE / "walk-me-through-approval-walk-minutes-and-walk-document-item-finder-common.py"
ANSWER_HOOK_FILE = HERE / "walk-me-through-user-short-answer-to-approval-walk-item-expanded-into-instructions-user-prompt-submit-hook.py"
ALERTS_HOOK_FILE = HERE / "walk-me-through-pending-user-alerts-claim-and-insert-as-approval-walk-items-user-prompt-submit-hook.py"
ATTENDANCE_CHECK_FILE = CHECKOUT / "nn-systems" / "general-tools" / "agent-session-unattended-by-user-check-common.py"
HANDOFF_SUPERVISOR_PROMPT = re.compile(
    r"^(?:Read .+? — the dialog from the session you are continuing, |This session was resumed by crash recovery )")
ANSWER_WITH_OTHER_WORDS_FORMS = ("condition", "rider")

COPY_FAILED_LINES = (
    "[rule walk-me-through-user-message-copied-to-walk-minutes] The hook could not copy the user's message into an "
    "approval-walk's walk-minutes, because {error!r}, so a change he asks for here could be lost at a session-handoff.",
    "If exactly one file docs/walk/*-minutes.md in this checkout has a last `#next_to_present` line that is not `none` "
    "or `closed`, add to that file, before you end this turn, one line holding the UTC time and his exact words, "
    "opening with neither an item's running count nor a hashtag, so that no program reads it as a decision.",
    "If no such file exists, no approval-walk is open: do nothing more about this message.",
    "If more than one such file exists, or the write fails, tell the user: \"Your last message is not in the "
    "walk-minutes, because <the error above>.\" A subagent gives that sentence to the agent that dispatched it instead.",
)


def load_module(name, path):
    specification = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def is_only_an_answer(prompt, walk_finder):
    answer_hook = load_module(
        "walk_me_through_user_short_answer_to_approval_walk_item_expanded_into_instructions_user_prompt_submit_hook",
        ANSWER_HOOK_FILE)
    text = prompt.strip()
    if answer_hook.BUMP.match(text) or walk_finder.NAVIGATION_WORD_ALONE.match(text):
        return True
    answer = answer_hook.parsed_answer(text)
    return answer is not None and answer["form"] not in ANSWER_WITH_OTHER_WORDS_FORMS


def copy_message(payload, environment, moment):
    """Append the copied line when the payload's prompt is one to copy and an approval-walk is open."""
    prompt = payload.get("prompt") or ""
    if not prompt.strip() or HANDOFF_SUPERVISOR_PROMPT.match(prompt):
        return
    if load_module("agent_session_unattended_by_user_check_common",
                   ATTENDANCE_CHECK_FILE).agent_session_unattended_by_user(environment):
        return
    walk_finder = load_module("walk_me_through_approval_walk_minutes_and_walk_document_item_finder_common",
                              WALK_FINDER_FILE)
    if is_only_an_answer(prompt, walk_finder):
        return
    if not load_module("walk_me_through_pending_user_alerts_claim_and_insert_as_approval_walk_items_user_prompt_submit_hook",
                       ALERTS_HOOK_FILE).typed_by_user(payload):
        return
    top = walk_finder.checkout_top(Path(payload.get("cwd") or os.getcwd()))
    if top is None or not (top / walk_finder.WALK_DIRECTORY).is_dir():
        return
    parser = walk_finder.markdown_parser()
    walk = walk_finder.open_walk(top / walk_finder.WALK_DIRECTORY, parser)
    if walk is None:
        return
    minutes, value, _ = walk
    document = minutes.with_name(minutes.name[:-len(walk_finder.MINUTES_SUFFIX)] + ".md")
    existing = minutes.read_text(encoding="utf-8")
    line = walk_finder.approval_walk_minutes_user_message_copied_line_build(existing, value, document, prompt, moment, parser)
    with open(minutes, "a", encoding="utf-8") as file:
        file.write(("" if existing.endswith("\n") else "\n") + line + "\n")


def output_for(payload, environment, moment):
    try:
        copy_message(payload, environment, moment)
    except Exception as error:  # noqa: BLE001 - every failure to copy is reported to the agent
        return {"hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext": "\n".join(
            line.format(error=error) for line in COPY_FAILED_LINES)}}
    return None


def main():
    try:
        output = output_for(json.loads(sys.stdin.read()), os.environ, datetime.now(timezone.utc))
    except Exception as error:
        print(f"walk-me-through-user-message-not-only-an-answer-copied-to-walk-minutes-user-prompt-submit-hook: the "
              f"hook failed, so the user's message was not copied into the walk-minutes: {error!r}", file=sys.stderr)
        return 1
    if output is not None:
        print(json.dumps(output, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
