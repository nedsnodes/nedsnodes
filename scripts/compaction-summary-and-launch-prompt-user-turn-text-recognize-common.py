#!/usr/bin/env python3
"""Recognize a user turn that Claude Code, the handoff-supervisor or crash recovery wrote, by its text.

The handoff-supervisor, scripts/recover-crashed-seats.py and scripts/agent-seat-transcript-worth-resuming-common.py
build their prompts from the constants here, so a prompt they add or reword cannot slip past this reader. Each
check is anchored to where its program puts the words, the prompt's opening or a line of its own, so a user who
quotes the words inside a reply of his own is still read as typing it. This module imports nothing from the
repository, because a UserPromptSubmit hook loads it on every prompt."""

import re

COMPACTION_SUMMARY_OPENING = "This session is being continued from a previous conversation"
# Also opens scripts/recover-crashed-seats.py's resume prompts; the transcript reader recognizes all three by it.
CRASH_RECOVERY_RESUME_PROMPT_OPENING = "This session was resumed by crash recovery (nedschorus#120)"
FIRST_PROMPT_FOR_AGENT_SEAT_WITHOUT_A_HANDOFF_TEMPLATE = "You are {agent}. No handoff exists yet; ask what to work on."
# Claude Code records a prompt passed on its command line as typed by a person, so this line is the only mark
# by which a reader tells the launch command's prompt from the user's words.
FIRST_PROMPT_FROM_LAUNCH_COMMAND_NOT_TYPED_BY_THE_USER_LINE = (
    "The text above this line came from the handoff-supervisor's --first-prompt-file or --first-prompt; "
    "the user did not type it.")
# Transcripts already written end their launch command's prompt with these, so the reader must still know them.
FIRST_PROMPT_FROM_LAUNCH_COMMAND_NOT_TYPED_BY_THE_USER_LINE_EARLIER_WORDINGS = (
    "The handoff-supervisor was given this first prompt with --first-prompt-file or --first-prompt; "
    "the user did not type it.",
)
# Keep the marker short enough to match both timestamp forms stored in transcripts.
REINCARNATION_OPENER_MARKER = "the dialog from the session you are continuing"
# Anchor the opener to avoid matching its text quoted in a hand-written brief.
REINCARNATION_OPENER_PATTERN = re.compile(
    r"Read .+? — (?:it is )?" + re.escape(REINCARNATION_OPENER_MARKER))
IGNITION_WITHOUT_CONVERSATION_TAIL_OPENING = "(Recovered at "
IGNITION_WITHOUT_CONVERSATION_TAIL_MARKER = "the previous session's conversation-tail is unavailable"
FRESH_SESSION_FROM_CONVERSATION_TAIL_PROMPT_PHRASE = "it is the dialog from this seat's last recorded session"
FIRST_PROMPT_AFTER_RECORDED_EXIT_MARKER = "as it does when a session is stopped on purpose"
FIRST_PROMPT_AFTER_RECORDED_EXIT_SENTENCE = (
    f"This seat's supervisor recorded the exit of its last session, {FIRST_PROMPT_AFTER_RECORDED_EXIT_MARKER}, "
    "so recovery did not bring the seat back on its own.")

FIRST_PROMPT_FOR_AGENT_SEAT_WITHOUT_A_HANDOFF_PATTERN = re.compile(
    re.escape(FIRST_PROMPT_FOR_AGENT_SEAT_WITHOUT_A_HANDOFF_TEMPLATE).replace(re.escape("{agent}"), ".+?"))
FRESH_SESSION_FROM_CONVERSATION_TAIL_PROMPT_PATTERN = re.compile(
    r"Read .+? — " + re.escape(FRESH_SESSION_FROM_CONVERSATION_TAIL_PROMPT_PHRASE))
# Prompts written before 2026-11-17 put this note on a line of its own after the next step.
IGNITION_WITHOUT_CONVERSATION_TAIL_PATTERN = re.compile(
    "^" + re.escape(IGNITION_WITHOUT_CONVERSATION_TAIL_OPENING) + r"[^:\n]+: "
    + re.escape(IGNITION_WITHOUT_CONVERSATION_TAIL_MARKER), re.MULTILINE)
FIRST_PROMPT_AFTER_RECORDED_EXIT_PATTERN = re.compile(
    r"(?:You are .+?\. )?" + re.escape(FIRST_PROMPT_AFTER_RECORDED_EXIT_SENTENCE))
# The handoff-supervisor puts this line after the launch command's prompt, and leftovers may follow it.
FIRST_PROMPT_FROM_LAUNCH_COMMAND_LINE_PATTERN = re.compile(
    "^(?:" + "|".join(re.escape(line) for line in (FIRST_PROMPT_FROM_LAUNCH_COMMAND_NOT_TYPED_BY_THE_USER_LINE,
                                                   *FIRST_PROMPT_FROM_LAUNCH_COMMAND_NOT_TYPED_BY_THE_USER_LINE_EARLIER_WORDINGS))
    + r")[ \t]*$", re.MULTILINE)


def user_turn_text_is_compaction_summary_or_launch_prompt(text):
    """Whether a user turn's text is a compaction summary or a prompt the handoff-supervisor or crash recovery wrote."""
    return (text.startswith(COMPACTION_SUMMARY_OPENING)
            or text.startswith(CRASH_RECOVERY_RESUME_PROMPT_OPENING)
            or FIRST_PROMPT_FOR_AGENT_SEAT_WITHOUT_A_HANDOFF_PATTERN.match(text) is not None
            or REINCARNATION_OPENER_PATTERN.match(text) is not None
            or FRESH_SESSION_FROM_CONVERSATION_TAIL_PROMPT_PATTERN.match(text) is not None
            or IGNITION_WITHOUT_CONVERSATION_TAIL_PATTERN.search(text) is not None
            or FIRST_PROMPT_AFTER_RECORDED_EXIT_PATTERN.match(text) is not None
            or FIRST_PROMPT_FROM_LAUNCH_COMMAND_LINE_PATTERN.search(text) is not None)
