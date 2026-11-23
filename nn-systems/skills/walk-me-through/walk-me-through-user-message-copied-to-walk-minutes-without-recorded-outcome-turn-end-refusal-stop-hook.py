#!/usr/bin/env python3
"""Stop hook: while an approval-walk is open, refuse to end the turn while a user message copied into its walk-minutes
has no outcome, as WALK_FINDER_FILE's docstring says under COPIED USER MESSAGES.

The state is the walk-minutes alone, so a successor is refused for a line its predecessor left. Any turn is checked,
whatever started it. The hook is silent while the agent answers a Stop hook, as the Stop-hook silence rule's module
requires, in an agent-session no user attends, during an emergency stop, and when no single approval-walk is open.

ON A FAULT, such as input that is not JSON or a file it cannot read, the hook prints one line naming it on stderr and
exits 1: Claude Code records a Stop hook's exit 1 as a non-blocking error and still ends the turn.

Tool-messages-to-agent follow
docs/nedsnodes-wiki/nedsnodes-how-to-write-a-tool-message-to-agent-such-as-a-hook-refusal-or-script-error.md.
"""
import importlib.util
import json
import os
import shlex
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CHECKOUT = HERE.parents[2]
WALK_FINDER_FILE = HERE / "walk-me-through-approval-walk-minutes-and-walk-document-item-finder-common.py"
STOP_HOOKS_STAY_SILENT_RULE_FILE = (CHECKOUT / "nn-systems" / "general-tools"
                                    / "claude-code-stop-hooks-stay-silent-while-agent-answers-a-stop-hook-rule-common.py")
ATTENDANCE_CHECK_FILE = CHECKOUT / "nn-systems" / "general-tools" / "agent-session-unattended-by-user-check-common.py"
EMERGENCY_STOP_READER_FILE = HERE.parent / "emergency-stop" / "emergency-stop-file-in-force-read-common.py"
WORDS_SHOWN_LIMIT = 200

NO_OUTCOME_REFUSAL_OPENING_LINE = (
    "[rule walk-me-through-user-message-copied-line-needs-outcome] This hook refused to end the turn on purpose: the "
    "walk-minutes {minutes} hold {count} copied user message(s) with no valid outcome. Without one, a change agreed "
    "with the user can be lost at a session-handoff, and his approval could then approve the opposite of what he "
    "agreed:")
COPIED_LINE_ENTRY = "- id {id}, {item}, at {time}: {words}{unchanged}"
UNCHANGED_NOTE = (" (its newest outcome says `changed`, which is not valid yet: the item's text in the walk-document "
                  "is the same as when the message was copied, apart from whitespace, `of M` and a deferred note)")
WALK_ME_THROUGH_STOP_HOOK_REFUSAL_PRINTF_COMMAND_PER_OUTCOME_RECORDING_COPIED_USER_MESSAGE_OUTCOME_IN_WALK_MINUTES_LINE = (
    "  changed: printf '%s\\n' '#user_message_outcome {id} changed' >> {quoted_minutes}\n"
    "  no change: printf '%s\\n' '#user_message_outcome {id} no change' >> {quoted_minutes}\n"
    "  open: printf '%s\\n' '#user_message_outcome {id} open' >> {quoted_minutes}")
WALK_ME_THROUGH_STOP_HOOK_REFUSAL_TELLING_AGENT_TO_RECORD_COPIED_USER_MESSAGE_OUTCOME_LINES = (
    "For every id above, run one of the three printf commands listed under it before you end this turn; the newest "
    "outcome line for an id counts.",
    "If the message changed the text of the item its entry names, first write the change into the walk-document "
    "{document}, then run the printf command labelled `changed`.",
    "If the message left that item's text as it is, including a message about another item or unrelated to the "
    "approval-walk, run the printf command labelled `no change`.",
    "If the discussion is still going on, run the printf command labelled `open`. When the discussion settles, run "
    "the one labelled `no change`, or write the change into the walk-document and run the one labelled `changed`.",
    "An outcome line does not answer the item: leave the item waiting for the user's answer.",
    "If a message at this same Stop tells you to run the /handoff skill, first write any change agreed with the user "
    "into the walk-document, then run the skill without recording an outcome: this hook then refuses your successor "
    "until it records the outcome.",
)


def load_module(name, path):
    specification = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def run(stdin_text, environment):
    """Return the text to print, or None."""
    payload = json.loads(stdin_text)
    rule = load_module("claude_code_stop_hooks_stay_silent_while_agent_answers_a_stop_hook_rule_common",
                       STOP_HOOKS_STAY_SILENT_RULE_FILE)
    if rule.stop_hook_stays_silent_while_agent_answers_a_stop_hook(payload):
        return None
    if load_module("agent_session_unattended_by_user_check_common",
                   ATTENDANCE_CHECK_FILE).agent_session_unattended_by_user(environment):
        return None
    emergency_stop = load_module("emergency_stop_file_in_force_read_common", EMERGENCY_STOP_READER_FILE)
    stop_state = emergency_stop.read_state(emergency_stop.emergency_stop_folder(environment))
    if isinstance(stop_state, (emergency_stop.InForce, emergency_stop.Unreadable)):
        return None
    if not payload.get("cwd"):
        return None
    walk_finder = load_module("walk_me_through_approval_walk_minutes_and_walk_document_item_finder_common",
                              WALK_FINDER_FILE)
    top = walk_finder.checkout_top(Path(payload["cwd"]))
    if top is None or not (top / walk_finder.WALK_DIRECTORY).is_dir():
        return None
    parser = walk_finder.markdown_parser()
    try:
        walk = walk_finder.open_walk(top / walk_finder.WALK_DIRECTORY, parser)
    except walk_finder.MoreThanOneUnclosedApprovalWalk:
        return None
    if walk is None:
        return None
    minutes = walk[0]
    document = minutes.with_name(minutes.name[:-len(walk_finder.MINUTES_SUFFIX)] + ".md")
    missing = walk_finder.approval_walk_user_message_lines_copied_to_walk_minutes_without_valid_outcome_find(
        minutes.read_text(encoding="utf-8"), document, parser)
    if not missing:
        return None
    lines = [NO_OUTCOME_REFUSAL_OPENING_LINE.format(minutes=minutes, count=len(missing))]
    quoted_minutes = shlex.quote(str(minutes))
    for copied_id, time, item, words, unchanged in missing:
        lines.append(COPIED_LINE_ENTRY.format(id=copied_id, item=item, time=time, words=words[:WORDS_SHOWN_LIMIT],
                                              unchanged=UNCHANGED_NOTE if unchanged else ""))
        lines.append(WALK_ME_THROUGH_STOP_HOOK_REFUSAL_PRINTF_COMMAND_PER_OUTCOME_RECORDING_COPIED_USER_MESSAGE_OUTCOME_IN_WALK_MINUTES_LINE.format(id=copied_id, quoted_minutes=quoted_minutes))
    lines += [line.format(document=document) for line in WALK_ME_THROUGH_STOP_HOOK_REFUSAL_TELLING_AGENT_TO_RECORD_COPIED_USER_MESSAGE_OUTCOME_LINES]
    return json.dumps({"decision": "block", "reason": "\n".join(lines)}, ensure_ascii=False)


def main():
    try:
        output = run(sys.stdin.read(), os.environ)
    except Exception as error:
        print(f"walk-me-through-user-message-copied-to-walk-minutes-without-recorded-outcome-turn-end-refusal-stop-hook: the hook failed, "
              f"so it did not check that each copied user message has an outcome; the agent need not act: {error!r}",
              file=sys.stderr)
        return 1
    if output is not None:
        print(output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
