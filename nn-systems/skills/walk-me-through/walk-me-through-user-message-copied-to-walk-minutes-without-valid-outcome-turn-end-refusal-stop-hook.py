#!/usr/bin/env python3
"""Stop hook: while an approval-walk is open, refuse to end the turn while a user message copied into its walk-minutes
needs an outcome and has none, as WALK_FINDER_FILE's docstring says under COPIED USER MESSAGES.

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
ANSWER_HOOK_FILE = HERE / "walk-me-through-user-short-answer-to-approval-walk-item-expanded-into-instructions-user-prompt-submit-hook.py"
CHECK_PROGRAM_FILE = HERE / "walk-me-through-answer-added-texts-cold-read-fast-read-check-and-close.py"
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
COPIED_LINE_ENTRY = "- id {id}, {item}, at {time}: {words}{answer_note}{unchanged}"
ANSWER_RECORDED_NOTE = " (this message answers the item, and the walk-minutes already record a decision on the item)"
ANSWER_NOT_RECORDED_NOTE = " (this message answers the item, and the walk-minutes record no decision on the item)"
UNCHANGED_NOTE = (" (its newest outcome says `changed`, which is not valid yet: the item's text in the walk-document "
                  "is the same as when the message was copied, apart from whitespace, `of M` and a deferred note; if the "
                  "walk-document already held the agreed change when the message was copied, run the printf command "
                  "labelled `no change`)")
WALK_ME_THROUGH_STOP_HOOK_REFUSAL_PRINTF_COMMAND_PER_OUTCOME_RECORDING_COPIED_USER_MESSAGE_OUTCOME_IN_WALK_MINUTES_LINE = (
    "  changed: printf '%s\\n' '#user_message_outcome {id} changed' >> {quoted_minutes}\n"
    "  no change: printf '%s\\n' '#user_message_outcome {id} no change' >> {quoted_minutes}\n"
    "  open: printf '%s\\n' '#user_message_outcome {id} open' >> {quoted_minutes}")
WALK_ME_THROUGH_STOP_HOOK_REFUSAL_TELLING_AGENT_TO_RECORD_COPIED_USER_MESSAGE_OUTCOME_LINES = (
    "For every id above, run one of the three printf commands listed under it before you end this turn; the newest "
    "outcome line for an id counts.",
    "If you and the user agreed a change to the text of the item its entry names, and the walk-document {document} "
    "did not hold the change when the message was copied, write the change there unless you already have, then run "
    "the printf command labelled `changed`.",
    "If the walk-document already held that change when the message was copied, as when the user repeats or confirms "
    "a change, run the printf command labelled `no change`, because `changed` is valid only when the item's text "
    "differs from its text at the copy.",
    "If you and the user agreed a change to the text of another item, write that change into that other item in the "
    "walk-document, unless the walk-document already holds the change.",
    "If the message needs no change to the text of the item its entry names, as when the message is about another item "
    "or unrelated to the approval-walk, run the printf command labelled `no change`.",
    "If the discussion is still going on, run the printf command labelled `open`. When the discussion settles, run "
    "the one labelled `no change`, or write the change into the walk-document and run the one labelled `changed`.",
    "An outcome line records no answer and decides no item.",
    "If an entry says the walk-minutes already record a decision on the item, do not run `check` for that answer, "
    "because the item is decided; if the user added words to the answer, as in `A, but reword the title`, carry out "
    "what he added unless that is already done, then run the printf command that fits.",
    "If an entry says the walk-minutes record no decision on the item and this agent-session holds a hook message "
    "saying `The user answered \"` and those words, follow that message, then run the printf command that fits.",
    "If an entry says the walk-minutes record no decision on the item and this agent-session holds no such message, as "
    "after a session-handoff, run the printf command labelled `open`, show the user the item as the walk-document now "
    "has it, quote his words, and ask him to answer again, because an answer counts only after this agent-session has "
    "shown him the item.",
    "If a message at this same Stop tells you to run the /handoff skill, first write any change agreed with the user "
    "into the walk-document, and run the printf command for each id whose outcome you know. Then run the skill: this "
    "hook refuses your successor until each id left without an outcome has one.",
)


def load_module(name, path):
    specification = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def answer_notes(missing, minutes_text, walk_finder, parser):
    """Return {id: the entry's note} for each message in missing that parsed_answer reads as an answer."""
    answer_hook = load_module(
        "walk_me_through_user_short_answer_to_approval_walk_item_expanded_into_instructions_user_prompt_submit_hook",
        ANSWER_HOOK_FILE)
    answers = {}
    for copied_id, _, item, words, _ in missing:
        delimiter = len(words) - len(words.lstrip("`"))
        if answer_hook.parsed_answer(words[delimiter:-delimiter].strip()) is not None:
            answers[copied_id] = item
    if not answers:
        return {}
    decided, _ = load_module("walk_me_through_answer_added_texts_cold_read_fast_read_check_and_close",
                             CHECK_PROGRAM_FILE).minutes_record(walk_finder, minutes_text, parser)

    def decision_recorded(item):
        try:
            return set(walk_finder.parse_items(item)[0]) <= decided
        except walk_finder.UnusableRange:  # A running count that names no item can hold no decision.
            return False

    return {copied_id: ANSWER_RECORDED_NOTE if decision_recorded(item) else ANSWER_NOT_RECORDED_NOTE
            for copied_id, item in answers.items()}


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
    minutes_text = minutes.read_text(encoding="utf-8")
    missing = walk_finder.approval_walk_user_message_lines_copied_to_walk_minutes_without_valid_outcome_find(
        minutes_text, document, parser)
    if not missing:
        return None
    notes = answer_notes(missing, minutes_text, walk_finder, parser)
    lines = [NO_OUTCOME_REFUSAL_OPENING_LINE.format(minutes=minutes, count=len(missing))]
    quoted_minutes = shlex.quote(str(minutes))
    for copied_id, time, item, words, unchanged in missing:
        lines.append(COPIED_LINE_ENTRY.format(id=copied_id, item=item, time=time, words=words[:WORDS_SHOWN_LIMIT],
                                              answer_note=notes.get(copied_id, ""),
                                              unchanged=UNCHANGED_NOTE if unchanged else ""))
        lines.append(WALK_ME_THROUGH_STOP_HOOK_REFUSAL_PRINTF_COMMAND_PER_OUTCOME_RECORDING_COPIED_USER_MESSAGE_OUTCOME_IN_WALK_MINUTES_LINE.format(id=copied_id, quoted_minutes=quoted_minutes))
    lines += [line.format(document=document) for line in WALK_ME_THROUGH_STOP_HOOK_REFUSAL_TELLING_AGENT_TO_RECORD_COPIED_USER_MESSAGE_OUTCOME_LINES]
    return json.dumps({"decision": "block", "reason": "\n".join(lines)}, ensure_ascii=False)


def main():
    try:
        output = run(sys.stdin.read(), os.environ)
    except Exception as error:
        print(f"walk-me-through-user-message-copied-to-walk-minutes-without-valid-outcome-turn-end-refusal-stop-hook: the hook failed, "
              f"so it did not check that each copied user message has an outcome; the agent need not act: {error!r}",
              file=sys.stderr)
        return 1
    if output is not None:
        print(output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
