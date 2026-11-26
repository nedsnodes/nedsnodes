#!/usr/bin/env python3
"""Extract the two-voice dialog from a Claude Code session transcript.

The handoff system's dialog carrier (specification:
nn-systems/handoff/handoff.system.design.md). A retiring session names a
boundary; the supervisor runs this after killing that session, and the
extracted markdown becomes the successor's context.

By default it carries the tail of the conversation: enough turns to clear a
word floor, extended back to the nearest user prompt so the extract opens on
a clean turn. Nobody chooses a boundary — the retiring agent has no judgment
to exercise here, and the header states how many earlier turns were left in
the transcript, so a successor whose work reaches further back knows to go
read them.

Two overrides exist for manual use:
  --boundary-quote "<first line of a user prompt>"
      Start at a named prompt instead of the floor-sized tail.
  --last-turns N
      Carry exactly N final turns, ignoring the floor.

Locating the transcript, in order: --transcript-path when given; otherwise
the session id keyed against the project directory derived from --cd (or
the current working directory); otherwise a search for <session-id>.jsonl
across every project directory. Latest-by-modification-time is never used:
a second session in the same worktree makes that a race.

Kept verbatim: user prompts and assistant display text; a slash command the
user typed with words is kept as "/command words". Dropped: tool
calls and their results, thinking blocks, system and harness records,
the subagents' own records (isSidechain), and harness-injected pseudo-prompts with the
short agent acknowledgements that answer them — none of which the successor
needs and all of which are large.

The conversation-tail carries a User turn, at the place in the dialog where the
user typed them, for messages the user queued that the agent never read before
the session was stopped, as
claude_code_session_transcript_queued_user_messages_never_read_by_agent says; the complete dialog does not carry it.

Kept as a third voice, Subagent: for each subagent the session dispatched,
what it was asked and what it reported, never its own records. These subagent
turns have the voice "subagent" even when the session's agent wrote them, as
it wrote each task. The subagent tracker,
scripts/handoff-extract-conversation-subagent-tracker-hack.py, finds them and
says which records it reads. The tracker is nn-hack: when it cannot be
loaded or raises, the subagent turns are left out, and one note says so and
why: as a line in the header of the conversation-tail, which is also what
stdout gets; as a section of its own, "Subagent tasks and reports left out",
in the body of the complete dialog, when one is written; and on stderr. The
handoff still writes its dialog and exits 0. Because a report answers
the session, the agent's short reply to one is kept, not dropped as an
acknowledgement. Subagent turns go in the complete dialog only, every one
whole: the tail, which the successor reads first, carries the user's and the
agent's turns alone, so a handoff writes the complete dialog whenever the
session has a subagent turn. read_dialog_turns returns subagent turns only when
asked, so its other callers keep the two voices they expect.

Alongside the extraction, when it leaves turns behind, the complete filtered
dialog is written as a sibling file: the tail is the successor's working set,
the companion is the conversation's history without the raw transcript's tool
dumps.

The session dialogs the log-store keeps for the past-discussion search hold
all of a session's turns, and scripts/log-store-session-dialogs-refresh-common.py
writes them from the session's transcript with this file's renderer for the
handoff's companion. They differ from the companion in two ways. First, in
them, an agent paragraph identical to one the agent showed earlier in the
session becomes one line, "(repeated: <its first eight
words> …)". A paragraph is text between blank lines. The first copy stays
whole, and the user's and the subagent turns are never shortened. The
handoff's own files keep every repeat, since a successor needs the current
item's closing line. Second, each session dialog ends with a line naming the
sha256 of the extractor that wrote it, which the companion does not have.

Exit codes: 0 extraction written, 2 bad invocation, 3 transcript not
found, 4 transcript unusable (empty, unparseable, or boundary not found).
"""

import argparse
import importlib.util
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

PROJECTS_ROOT = Path.home() / ".claude" / "projects"

# Bound oversized tool dumps so one record cannot defeat extraction.
MAXIMUM_RECORD_BYTES = 4 * 1024 * 1024

# A short tail limits every restart's context cost; the companion and transcript let a successor recover omitted dialog.
MINIMUM_DIALOG_WORDS = 1000


# Openings of records Claude Code writes as context around a delivery rather than as one. Not <bash-input>, a
# command the user typed, nor a slash command's or task notification's record, each of which delivers a queued text.
CONTEXT_RECORD_TEXT_OPENINGS = (
    "Base directory for this skill:",
    "<local-command-caveat>",
    "<local-command-stdout>",
    "<local-command-stderr>",
    "<bash-stdout>",
    "<bash-stderr>",
    "<system-reminder>",
)

# Typed slash commands with arguments must be recovered before checking these injected prefixes.
INJECTED_TEXT_PREFIXES = CONTEXT_RECORD_TEXT_OPENINGS + (
    "<task-notification>",
    "<command-message>",
    "<command-name>",
)

# The two notices Claude Code writes when the user presses Escape. Only a message that is wholly one is a
# notice: a prompt the user typed that opens with one, pasted, is his.
INTERRUPT_NOTICE_PATTERN = re.compile(r"\[Request interrupted by user( for tool use)?\]")


def text_is_whole_interrupt_notice(text):
    """Whether the text, stripped, is exactly one of Claude Code's interrupt notices."""
    return bool(INTERRUPT_NOTICE_PATTERN.fullmatch(text.strip()))

# Short post-notification replies are acknowledgements; longer reactions may contain substantive analysis.
MAXIMUM_ACKNOWLEDGEMENT_WORDS = 60

SUBAGENT_VOICE = "subagent"
SUBAGENT_TRACKER_MODULE_FILE_NAME = "handoff-extract-conversation-subagent-tracker-hack.py"
# The kind of the one turn that says the subagent turns were left out; it is not a subagent turn.
SUBAGENT_TURNS_LEFT_OUT_KIND = "left-out"


class TranscriptProblem(Exception):
    """The transcript cannot be used for extraction."""


def project_directory_for_working_directory(working_directory: Path) -> Path:
    """Return the harness project directory holding the worktree's sessions."""
    # Same rule as claude-code-session-transcript-lookup-and-text-search-common.py,
    # copied because this script runs copied beside hooks that lack that module; that
    # module's test fails if the two disagree.
    return PROJECTS_ROOT / re.sub(r"[^a-zA-Z0-9]", "-", str(Path(working_directory).resolve()))


def transcript_paths_for_session(session_id: str, working_directory: Path) -> list:
    """Return the keyed transcript when it exists, else every project directory's copy, sorted."""
    # Same rule as the common module's
    # claude_code_session_transcript_paths_for_session_id_in_working_directory_project_directory_if_present_else_in_every_project_directory,
    # copied for the same reason as the folder rule above; that module's test fails if the two disagree.
    keyed_path = project_directory_for_working_directory(working_directory) / f"{session_id}.jsonl"
    if keyed_path.is_file():
        return [keyed_path]
    return sorted(PROJECTS_ROOT.glob(f"*/{session_id}.jsonl"))


def find_transcript_path(session_id: str, working_directory: Path) -> Path:
    """Find a session transcript by keyed lookup, then by search."""
    keyed_path = project_directory_for_working_directory(working_directory) / f"{session_id}.jsonl"
    matches = transcript_paths_for_session(session_id, working_directory)
    if len(matches) == 1:
        return matches[0]
    if not matches:
        raise TranscriptProblem(
            f"no transcript for session {session_id}: looked at {keyed_path} "
            f"and searched {PROJECTS_ROOT}/*/"
        )
    raise TranscriptProblem(
        f"session {session_id} appears in several project directories: "
        + ", ".join(str(match) for match in matches)
    )


def read_dialog_turns(transcript_path: Path, drop_acknowledgements=True,
                      include_subagent_tasks_and_reports=False):
    """Return (turns, skip_counts), counting malformed and oversized records as skipped.

    Each turn holds its voice, its text and its record's timestamp ("" when the record has none); a user or
    agent turn also holds its record's transcript line index.
    With drop_acknowledgements False, every agent message is kept, a short one after a
    notification included, so a reader attributing a user's reply sees the message it followed.
    With include_subagent_tasks_and_reports True, the turns also carry each subagent's tasks and reports,
    in voice SUBAGENT_VOICE, with the keys SubagentTracker documents. A task is the session's agent's
    words but has that voice too, so a caller collecting the "assistant" voice will not see it.
    """
    tracker = None
    tracker_failure = None
    if include_subagent_tasks_and_reports:
        try:
            tracker = new_subagent_tracker()
        except Exception as error:
            tracker_failure = subagent_turns_left_out_turn(error)
    # The writer may still be exiting, leaving a partial final record.
    turns = []
    skip_counts = {
        "malformed": 0, "oversized": 0, "partial_final_record": 0,
        "injected": 0, "acknowledgement": 0, "resent_after_interrupt": 0,
    }
    following_injected_record = False
    # The harness re-sends queued user text after an interrupt; deduplicate only across that interrupt without intervening dialog.
    carried_queued_text = None
    interrupted_since_queued = False

    with transcript_path.open("rb") as handle:
        raw_lines = handle.readlines()

    for index, raw_line in enumerate(raw_lines):
        is_final_line = index == len(raw_lines) - 1

        if len(raw_line) > MAXIMUM_RECORD_BYTES:
            skip_counts["oversized"] += 1
            continue

        stripped = raw_line.strip()
        if not stripped:
            continue

        try:
            record = json.loads(stripped)
        except (json.JSONDecodeError, UnicodeDecodeError):
            # An unterminated final line may still be in flight.
            if is_final_line and not stripped.endswith(b"}"):
                skip_counts["partial_final_record"] += 1
            else:
                skip_counts["malformed"] += 1
            continue
        # A subagent's own records belong to its transcript, not to this session's dialog or its subagent turns.
        if isinstance(record, dict) and record.get("isSidechain"):
            continue

        turn = dialog_turn_from_record(record)
        if turn is None:
            # Harness state can separate a notification from its acknowledgement; intervening tool work ends that pairing.
            if record_shows_tool_activity(record):
                following_injected_record = False
        elif turn["voice"] == "user":
            turn["timestamp"] = record.get("timestamp") or ""
            turn["line_index"] = index
            interrupt_notice = text_is_whole_interrupt_notice(turn["text"])
            if interrupt_notice or turn["text"].startswith(INJECTED_TEXT_PREFIXES):
                skip_counts["injected"] += 1
                following_injected_record = True
                if interrupt_notice:
                    interrupted_since_queued = True
            elif interrupted_since_queued and turn["text"] == carried_queued_text:
                skip_counts["resent_after_interrupt"] += 1
                carried_queued_text = None
                # A re-sent user message ends the acknowledgement window: the next assistant text answers the user.
                following_injected_record = False
            else:
                turns.append(turn)
                following_injected_record = False
                carried_queued_text = turn["text"] if record.get("type") == "attachment" else None
                interrupted_since_queued = False
        else:
            turn["timestamp"] = record.get("timestamp") or ""
            turn["line_index"] = index
            # Once the tracker fails, no record can show it carried a report, so a short reply may answer one: keep it.
            if (drop_acknowledgements and following_injected_record and tracker_failure is None
                    and len(turn["text"].split()) <= MAXIMUM_ACKNOWLEDGEMENT_WORDS):
                skip_counts["acknowledgement"] += 1
            else:
                turns.append(turn)
                carried_queued_text = None
            following_injected_record = False

        if tracker is not None:
            try:
                subagent_turns, carried_subagent_report = tracker.turns_from_record(record)
            except Exception as error:
                tracker = None
                tracker_failure = subagent_turns_left_out_turn(error)
                turns = [turn for turn in turns if turn["voice"] != SUBAGENT_VOICE]
                continue
            for subagent_turn in subagent_turns:
                subagent_turn["timestamp"] = record.get("timestamp") or ""
            turns.extend(subagent_turns)
            # Every copy of a carried report, the first or a repeat, makes the agent's next reply an answer to it.
            if carried_subagent_report:
                following_injected_record = False

    if tracker_failure is not None:
        turns.append(tracker_failure)
    return turns, skip_counts


_subagent_tracker_module = None


def new_subagent_tracker():
    """Return a new SubagentTracker, loading the tracker's file on first use; any failure raises."""
    global _subagent_tracker_module
    if _subagent_tracker_module is None:
        specification = importlib.util.spec_from_file_location(
            "handoff_extract_conversation_subagent_tracker_hack", subagent_tracker_module_path())
        module = importlib.util.module_from_spec(specification)
        specification.loader.exec_module(module)
        if module.SUBAGENT_VOICE != SUBAGENT_VOICE:
            raise ValueError(f"the tracker's voice is {module.SUBAGENT_VOICE!r}, "
                             f"the extractor's {SUBAGENT_VOICE!r}")
        _subagent_tracker_module = module
    return _subagent_tracker_module.SubagentTracker()


def subagent_tracker_module_path() -> Path:
    # Asked for only when subagent turns are, because a caller may run this file's source with no __file__.
    return Path(__file__).resolve().with_name(SUBAGENT_TRACKER_MODULE_FILE_NAME)


def subagent_turns_left_out_turn(error):
    text = (f"The subagent tracker, {SUBAGENT_TRACKER_MODULE_FILE_NAME}, failed, so this dialog leaves out every "
            f"subagent task and report: {type(error).__name__}: {error}")
    return {"voice": SUBAGENT_VOICE, "kind": SUBAGENT_TURNS_LEFT_OUT_KIND, "text": text,
            "subagent": {"agent_id": "", "description": "", "details": []}, "status": "", "timestamp": ""}


def record_shows_tool_activity(record) -> bool:
    """Return whether the record carries tool calls or results from this session."""
    if not isinstance(record, dict) or record.get("isSidechain"):
        return False
    # Some harness records have message=null; dict.get's default handles only a missing key.
    content = (record.get("message") or {}).get("content")
    return isinstance(content, list) and any(
        isinstance(block, dict) and block.get("type") in ("tool_use", "tool_result")
        for block in content
    )


def joined_text_blocks(content) -> str:
    if not isinstance(content, list):
        return ""
    return "\n".join(
        block.get("text", "")
        for block in content
        if isinstance(block, dict) and block.get("type") == "text"
    )


def dialog_turn_from_record(record):
    """Return a dialog turn for a record, or None to drop it."""
    if not isinstance(record, dict):
        return None
    if record.get("isSidechain"):
        return None
    if record.get("type") == "user" and record.get("isMeta"):
        return None

    record_type = record.get("type")

    # Mid-turn human messages arrive as queued_command attachments; the same shape also carries injected peer traffic.
    if record_type == "attachment":
        attachment = record.get("attachment")
        if not isinstance(attachment, dict) or attachment.get("type") != "queued_command":
            return None
        origin = attachment.get("origin")
        if not isinstance(origin, dict) or origin.get("kind") != "human":
            return None
        prompt = attachment.get("prompt")
        text = prompt.strip() if isinstance(prompt, str) else ""
        return {"voice": "user", "text": text} if text else None

    if record_type not in ("user", "assistant"):
        return None

    content = (record.get("message") or {}).get("content")
    if record_type == "user" and isinstance(content, str):
        text = content.strip()
        command = typed_slash_command(text, record)
        if command:
            return {"voice": "user", "text": command}
    else:
        text = joined_text_blocks(content).strip()

    return {"voice": record_type, "text": text} if text else None


def typed_slash_command(text: str, record):
    """Return a human-typed command with its arguments, or None for other records."""
    # Built-in and older skill-command records omit origin; their tag-wrapped words are still user input.
    if not text.startswith(("<command-message>", "<command-name>")):
        return None
    origin = record.get("origin")
    if isinstance(origin, dict) and origin.get("kind") != "human":
        return None
    words = re.search(r"<command-args>(.*?)</command-args>", text, re.S)
    if not words or not words.group(1).strip():
        return None
    name = re.search(r"<command-name>(.*?)</command-name>", text, re.S)
    if name and name.group(1).strip():
        command_name = name.group(1).strip()
    else:
        message = re.search(r"<command-message>(.*?)</command-message>", text, re.S)
        if not message or not message.group(1).strip():
            return None
        command_name = "/" + message.group(1).strip().lstrip("/")
    return f"{command_name} {words.group(1).strip()}"


CONVERSATION_TAIL_QUEUED_USER_MESSAGES_NEVER_READ_BY_AGENT_INTRODUCTION = (
    "Queued before the handoff and never read by your predecessor, whose turns below were written without it; "
    "treat each message of this turn as a reply to the dialog above it."
)
CONVERSATION_TAIL_UNREAD_QUEUED_USER_MESSAGE_TYPED_BEFORE_FIRST_SHOWN_TURN_INTRODUCTION_LINE_TEXT = (
    "Queued before the handoff and never read by your predecessor, whose turns below were written without it; "
    "treat it as a reply to the dialog that came before every turn in this file, which is in {where_that_dialog_is}."
)
QUEUED_TEXT_OF_ANOTHER_SENDER_TAG_OPENINGS = ("<task-notification", "<cross-session-message", "<agent-message")
PEER_MESSAGE_TAG_OPENINGS = ("<cross-session-message", "<agent-message")
DELIVERED_PEER_MESSAGE_FIRST_LINE = "Another Claude session sent a message:"
QUEUE_REMOVE_REASON_ABSORBED_MID_TURN = "absorbed_mid_turn"


def texts_shown_to_agent(record) -> list:
    """Return each form in which a record shows the agent queued text: a prompt, its typed slash command or shell command, or an absorbed attachment."""
    if not isinstance(record, dict) or record.get("isSidechain"):
        return []
    if record.get("type") == "attachment":
        attachment = record.get("attachment")
        if isinstance(attachment, dict) and attachment.get("type") == "queued_command":
            prompt = attachment.get("prompt")
            return [prompt.strip()] if isinstance(prompt, str) else []
        return []
    if record.get("type") != "user":
        return []
    content = (record.get("message") or {}).get("content")
    if isinstance(content, str):
        text = content.strip()
        shell_command = re.fullmatch(r"<bash-input>(.*)</bash-input>", text, re.S)
        return [text, typed_slash_command(text, record) or "", shell_command.group(1).strip() if shell_command else ""]
    return [joined_text_blocks(content).strip()]


class QueuedCommandAttachmentShownForms(list):
    """The shown texts of a queued_command attachment, the one record type that delivers an absorbed removal."""


def shown_text_is_queued_text(shown: str, queued: str) -> bool:
    """Match exactly, so that `A` is not read in any text containing it; a peer message may carry the harness's wrapper."""
    if shown == queued:
        return True
    return (text_opens_with_tag(queued, PEER_MESSAGE_TAG_OPENINGS)
            and f"{shown}\n".startswith(f"{DELIVERED_PEER_MESSAGE_FIRST_LINE}\n{queued}\n"))


def first_pending_position_shown(pending: list, shown_forms: list):
    for position, queued in enumerate(pending):
        if any(shown_text_is_queued_text(shown, queued) for shown in shown_forms):
            return position
    return None


def queue_events_of_transcript(transcript_path: Path) -> list:
    """Return queue operations as dicts with their line index, each record's shown texts as a list, and one None per run of agent records."""
    events = []
    with transcript_path.open("rb") as handle:
        for line_index, raw_line in enumerate(handle):
            if len(raw_line) > MAXIMUM_RECORD_BYTES:
                continue
            try:
                record = json.loads(raw_line)
            except (json.JSONDecodeError, UnicodeDecodeError):
                continue
            if not isinstance(record, dict) or record.get("isSidechain"):
                continue
            if record.get("type") == "queue-operation":
                events.append({**{key: record.get(key) for key in ("operation", "content", "reason")},
                               "line_index": line_index})
            elif record.get("type") == "assistant":
                if events and events[-1] is not None:
                    events.append(None)
            else:
                shown_forms = [text for text in texts_shown_to_agent(record) if text]
                if shown_forms:
                    events.append(QueuedCommandAttachmentShownForms(shown_forms)
                                  if record.get("type") == "attachment" else shown_forms)
    return events


def claim_delivery_record(events: list, operation_index: int, claimed: set, queued_texts: list, record_type: type = list):
    """Claim the first unclaimed record of record_type before the next agent record that shows a queued text; return that text's position."""
    for position, queued in enumerate(queued_texts):
        for index in range(operation_index + 1, len(events)):
            event = events[index]
            if event is None:
                break
            if isinstance(event, record_type) and index not in claimed and first_pending_position_shown([queued], event) is not None:
                claimed.add(index)
                return position
    return None


def queued_text_sender_kind(text: str) -> str:
    """Return who sent a queued text, or the record delivering one: a peer, a background task, or the user."""
    peer_first_line = f"{DELIVERED_PEER_MESSAGE_FIRST_LINE}\n"
    if text.startswith(peer_first_line):
        text = text[len(peer_first_line):]
    if text_opens_with_tag(text, PEER_MESSAGE_TAG_OPENINGS):
        return "peer"
    if text_opens_with_tag(text, QUEUED_TEXT_OF_ANOTHER_SENDER_TAG_OPENINGS):
        return "task-notification"
    return "user"


def oldest_position_from_sender_of_first_delivery_record(events: list, operation_index: int, claimed: set, pending: list):
    """For a dequeue whose delivery shows no queued text, claim the first unclaimed user record before the next agent record
    that delivers a message, and return the oldest pending position from its sender; with no such record, the oldest position.

    Claude Code delivers some messages in another form than it queued them, such as a peer message without its hop-chain
    attribute or a slash command without arguments, but never from another sender, so a stale message from another sender
    is not taken in their place. A record of context Claude Code adds, such as a skill's base directory, delivers nothing,
    and a record showing a message enqueued after this dequeue delivers that later message, so neither is claimed.
    """
    enqueued_later = []
    for index in range(operation_index + 1, len(events)):
        event = events[index]
        if event is None:
            break
        if isinstance(event, dict):
            if event["operation"] == "enqueue" and isinstance(event["content"], str):
                enqueued_later.append(event["content"].strip())
            continue
        if type(event) is not list or index in claimed:
            continue
        if event[0].startswith(CONTEXT_RECORD_TEXT_OPENINGS) or first_pending_position_shown(enqueued_later, event) is not None:
            continue
        claimed.add(index)
        sender = queued_text_sender_kind(event[0])
        return next((position for position, queued in enumerate(pending) if queued_text_sender_kind(queued) == sender), None)
    return 0


def claude_code_session_transcript_queued_user_messages_never_read_by_agent(transcript_path: Path) -> list:
    """Return, in the order typed, the text of each message unread_queued_user_messages_with_enqueue_lines returns."""
    return [message["text"] for message in unread_queued_user_messages_with_enqueue_lines(transcript_path)]


def unread_queued_user_messages_with_enqueue_lines(transcript_path: Path) -> list:
    """Return, in the order typed, the user's queued messages that no later record shows the agent reading.

    A queue-operation "enqueue" adds a message; "remove" takes the first with its content away; "popAll"
    returns every message to the input box; "dequeue", which names no content, takes the message that a
    user record before the next agent record shows, or else the oldest from that record's sender, or, when no
    record follows before the next agent record, the oldest. A queued_command attachment delivers
    an absorbed remove. The record that delivers either removes no second copy; any other record showing a
    message removes one copy.
    Messages from another sender's known tag are left out. Each is a dict of its text and its enqueue's
    transcript line index, which keeps its place among the dialog turns.
    """
    events = queue_events_of_transcript(transcript_path)
    pending = []
    enqueue_lines = []
    claimed = set()
    for index, event in enumerate(events):
        if event is None:
            continue
        if isinstance(event, list):
            if index not in claimed:
                position = first_pending_position_shown(pending, event)
                if position is not None:
                    del pending[position], enqueue_lines[position]
            continue
        operation = event["operation"]
        content = event["content"].strip() if isinstance(event["content"], str) else ""
        if operation == "enqueue" and content:
            pending.append(content)
            enqueue_lines.append(event["line_index"])
        elif operation == "remove" and content in pending:
            position = pending.index(content)
            del pending[position], enqueue_lines[position]
            if event["reason"] == QUEUE_REMOVE_REASON_ABSORBED_MID_TURN:
                claim_delivery_record(events, index, claimed, [content], QueuedCommandAttachmentShownForms)
        elif operation == "popAll":
            pending, enqueue_lines = [], []
        elif operation == "dequeue" and pending:
            position = claim_delivery_record(events, index, claimed, pending)
            if position is None:
                position = oldest_position_from_sender_of_first_delivery_record(events, index, claimed, pending)
            if position is not None:
                del pending[position], enqueue_lines[position]
    return [{"text": text, "enqueue_line": line} for text, line in zip(pending, enqueue_lines)
            if not text_opens_with_tag(text, QUEUED_TEXT_OF_ANOTHER_SENDER_TAG_OPENINGS)]


def text_opens_with_tag(text: str, tag_openings: tuple) -> bool:
    """Require the tag name to end, so that a user's `<agent-message-id> ...` is not taken for an `<agent-message`."""
    for opening in tag_openings:
        if text.startswith(opening):
            after_name = text[len(opening):]
            if after_name[:1] == ">" or after_name[:1].isspace() or after_name.startswith("/>"):
                return True
    return False


def first_line_of(text: str) -> str:
    return text.splitlines()[0].strip() if text.splitlines() else ""


def word_count(turns) -> int:
    """Return the words of the user's and the agent's turns; subagent turns do not count."""
    return sum(len(turn["text"].split()) for turn in turns if turn["voice"] != SUBAGENT_VOICE)


def turns_left_out_notes(turns) -> list:
    return [turn for turn in turns if turn["voice"] == SUBAGENT_VOICE and turn["kind"] == SUBAGENT_TURNS_LEFT_OUT_KIND]


def subagent_turn_count(turns) -> int:
    return sum(1 for turn in turns if turn["voice"] == SUBAGENT_VOICE) - len(turns_left_out_notes(turns))


def select_tail_clearing_floor(turns, minimum_words: int = MINIMUM_DIALOG_WORDS, keep_short_final_agent_turns: bool = False):
    """Return (selected_turns, start_index) for a tail clearing the word floor at a user prompt."""
    # Short final assistant turns may be fragments cut off by the retiring session's termination,
    # but an unread reply may answer one, such as `A` to a short approval question.
    end = len(turns)
    while (not keep_short_final_agent_turns and end > 0 and turns[end - 1]["voice"] == "assistant"
           and len(turns[end - 1]["text"].split()) <= MAXIMUM_ACKNOWLEDGEMENT_WORDS):
        end -= 1
    if end == 0:
        end = len(turns)

    index = end
    while index > 0 and word_count(turns[index:end]) < minimum_words:
        index -= 1

    while index > 0 and turns[index]["voice"] != "user":
        index -= 1

    return turns[index:end], index


def widen_to_minimum_words(turns, boundary_index: int, minimum_words: int) -> int:
    """Return the boundary widened to an earlier user prompt to clear the word floor when possible."""
    index = boundary_index
    while word_count(turns[index:]) < minimum_words:
        earlier = [
            candidate
            for candidate in range(index - 1, -1, -1)
            if turns[candidate]["voice"] == "user"
        ]
        if not earlier:
            return 0 if index > 0 else index
        index = earlier[0]
    return index


def select_turns_from_boundary(turns, boundary_quote: str, minimum_words: int = MINIMUM_DIALOG_WORDS):
    """Return turns from the quoted user prompt, widened as needed to clear the word floor."""
    wanted = boundary_quote.strip()
    for index, turn in enumerate(turns):
        if turn["voice"] != "user":
            continue
        if first_line_of(turn["text"]) == wanted or turn["text"].strip().startswith(wanted):
            widened = widen_to_minimum_words(turns, index, minimum_words)
            return turns[widened:], widened, index
    raise TranscriptProblem(
        f"boundary quote not found among {sum(1 for t in turns if t['voice'] == 'user')} "
        f"user prompts: {wanted!r}"
    )


@dataclass
class ExtractionReport:
    """Extraction results for the successor's header."""

    session_id: str
    transcript_path: Path
    boundary_note: str
    turns_left_behind: int
    total_turns: int
    skip_counts: dict
    companion_path: Path = None
    left_out_notes: list = field(default_factory=list)
    queued_user_messages_never_read_by_agent: list = field(default_factory=list)


def render_pointers(report: ExtractionReport) -> list:
    lines = []
    if report.companion_path:
        lines.append(
            f"The complete dialog, noise-free, with every earlier turn and every subagent task "
            f"and report: {report.companion_path}."
        )
    lines.append(
        f"The full transcript is at {report.transcript_path} — every tool call "
        "and result, and the retiring agent's thinking, where the reasoning "
        "behind a decision often lives."
    )
    return lines


def subagent_directory(report: ExtractionReport) -> Path:
    return report.transcript_path.with_suffix("") / "subagents"


def subagent_transcripts_pointer(report: ExtractionReport) -> str:
    return (f"Each subagent's own transcript, its tool calls included, is "
            f"{subagent_directory(report)}/agent-<agent id>.jsonl; a workflow's agents "
            f"are under {subagent_directory(report)}/workflows/<run id>/.")


def subagent_turns_note(turns) -> str:
    count = subagent_turn_count(turns)
    return f"; {count} subagent turns, not counted in the words" if count else ""


REPEATED_PARAGRAPH_OPENING_WORDS = 8
# Blank lines, however many, between two paragraphs; captured, so the paragraphs keep their spacing.
PARAGRAPH_BREAK = re.compile(r"(\n(?:[ \t]*\n)+)")


def turns_with_repeated_agent_paragraphs_shortened(turns):
    """Return the turns with each agent paragraph identical to an earlier agent paragraph made one line.

    The line is "(repeated: <its first eight words> …)"; paragraphs are compared with their outer
    whitespace stripped. Only "assistant" turns are changed, and only copies after the first.
    """
    shown = set()
    shortened = []
    for turn in turns:
        if turn["voice"] != "assistant":
            shortened.append(turn)
            continue
        pieces = PARAGRAPH_BREAK.split(turn["text"])
        for index in range(0, len(pieces), 2):
            paragraph = pieces[index].strip()
            if not paragraph:
                continue
            if paragraph in shown:
                opening = " ".join(paragraph.split()[:REPEATED_PARAGRAPH_OPENING_WORDS])
                pieces[index] = f"(repeated: {opening} …)"
            else:
                shown.add(paragraph)
        shortened.append(dict(turn, text="".join(pieces)))
    return shortened


SUBAGENT_HEADINGS = {
    "task": "Subagent task",
    "follow-up": "Subagent task, continued",
    "report": "Subagent report",
    "message": "Subagent message",
    SUBAGENT_TURNS_LEFT_OUT_KIND: "Subagent tasks and reports left out",
}


def render_turn(turn) -> list:
    """Return the Markdown lines of one turn."""
    if turn["voice"] != SUBAGENT_VOICE:
        speaker = "User" if turn["voice"] == "user" else "Agent"
        return [f"## {speaker}", "", turn["text"], ""]
    subagent = turn["subagent"]
    heading = SUBAGENT_HEADINGS[turn["kind"]]
    if subagent.get("description"):
        heading += f" — {subagent['description']}"
    facts = []
    if subagent.get("agent_id"):
        facts.append(f"agent {subagent['agent_id']}")
    if turn["kind"] == "task":
        facts += subagent.get("details") or []
    if turn.get("status") and turn["status"] != "completed":
        facts.append(turn["status"])
    lines = [f"## {heading}", ""]
    if facts:
        lines += [f"({', '.join(facts)})", ""]
    return lines + [turn["text"] or "(no text)", ""]


def render_extraction_diagnostics(turns, report: ExtractionReport) -> list:
    """Return the lines about how the tail was read and cut, which main prints on stderr, not in the tail."""
    lines = ["Turn counts are dialog only — harness-injected records and their acknowledgements are filtered out."]
    trimmed_at_end = report.total_turns - report.turns_left_behind - len(turns)
    if trimmed_at_end > 0:
        lines.append(
            f"Trimmed from the end: {trimmed_at_end} short agent turn(s) — "
            f"fragments from the session's last moments before the handoff."
        )
    skipped = ", ".join(f"{count} {name}" for name, count in report.skip_counts.items() if count)
    if skipped:
        lines.append(f"Records skipped while reading: {skipped}.")
    return lines


def render_extraction(turns, report: ExtractionReport) -> str:
    lines = [
        f"# Session dialog — {report.session_id}",
        "",
        f"Boundary: {report.boundary_note}",
        f"Turns carried: {len(turns)} of {report.total_turns} ({word_count(turns)} words).",
    ]

    if report.turns_left_behind:
        lines.append(
            f"Earlier in this session, and NOT below: {report.turns_left_behind} turns."
        )
    # The tail holds no subagent turn, so a tracker-failure note is carried here, where the successor reads it.
    lines += [note["text"] for note in report.left_out_notes]

    lines += ["", "---", ""]

    unread = list(report.queued_user_messages_never_read_by_agent)
    before_tail_introduction = CONVERSATION_TAIL_UNREAD_QUEUED_USER_MESSAGE_TYPED_BEFORE_FIRST_SHOWN_TURN_INTRODUCTION_LINE_TEXT.format(
        where_that_dialog_is=f"the complete dialog, {report.companion_path}" if report.companion_path
        else f"the full transcript, {report.transcript_path}")
    for position, turn in enumerate(turns):
        typed_before_turn = [message for message in unread if message["enqueue_line"] < turn.get("line_index", -1)]
        lines += rendered_unread_queued_messages(
            typed_before_turn,
            before_tail_introduction if position == 0
            else CONVERSATION_TAIL_QUEUED_USER_MESSAGES_NEVER_READ_BY_AGENT_INTRODUCTION)
        unread = unread[len(typed_before_turn):]
        lines += render_turn(turn)
    lines += rendered_unread_queued_messages(unread)

    lines += ["---", "", "Need more than this?"]
    lines += render_pointers(report)
    lines.append("")
    return "\n".join(lines)


def rendered_unread_queued_messages(
        messages: list, introduction: str = CONVERSATION_TAIL_QUEUED_USER_MESSAGES_NEVER_READ_BY_AGENT_INTRODUCTION) -> list:
    if not messages:
        return []
    lines = ["## User", "", introduction, ""]
    for message in messages:
        lines += [message["text"], ""]
    return lines


def render_companion(turns, report: ExtractionReport) -> str:
    """Render the complete filtered dialog."""
    lines = [
        f"# Complete session dialog — {report.session_id}",
        "",
        f"All {len(turns) - len(turns_left_out_notes(turns))} dialog turns ({word_count(turns)} words{subagent_turns_note(turns)}), "
        f"harness-injected records and their acknowledgements filtered out.",
        f"Tool calls, results, and the agent's thinking are only in the full "
        f"transcript: {report.transcript_path}",
    ]
    if subagent_turn_count(turns):
        lines.append(subagent_transcripts_pointer(report))
    lines += ["", "---", ""]
    for turn in turns:
        lines += render_turn(turn)
    return "\n".join(lines)


def complete_dialog_turns_and_report(transcript_path: Path):
    """Return (turns, report) for render_companion to render as a transcript's session dialog for the log-store:
    its complete filtered dialog, subagent turns included, with each agent paragraph shown before made one line,
    as turns_with_repeated_agent_paragraphs_shortened says."""
    turns, skip_counts = read_dialog_turns(transcript_path, include_subagent_tasks_and_reports=True)
    turns = turns_with_repeated_agent_paragraphs_shortened(turns)
    report = ExtractionReport(
        session_id=transcript_path.stem,
        transcript_path=transcript_path,
        boundary_note="the whole session",
        turns_left_behind=0,
        total_turns=len(turns),
        skip_counts=skip_counts,
    )
    return turns, report


def complete_dialog_lines_with_turn_timestamps(transcript_path: Path):
    """Return (lines, left_out_notes) for the text of the transcript's session dialog for the log-store.

    lines pairs each line with the timestamp of the turn it belongs to: "" for a heading line, or a turn
    whose record has none. left_out_notes holds the text of each note saying the subagent tracker failed,
    so the lines lack every subagent turn; it is empty when the dialog is whole.
    """
    turns, report = complete_dialog_turns_and_report(transcript_path)
    lines = render_companion(turns, report).split("\n")
    stamps = []
    for turn in turns:
        stamps += [turn.get("timestamp") or ""] * len("\n".join(render_turn(turn)).split("\n"))
    return (list(zip(lines, [""] * (len(lines) - len(stamps)) + stamps)),
            [note["text"] for note in turns_left_out_notes(turns)])


def resolve_transcript_path(arguments) -> Path:
    if arguments.transcript_path:
        transcript_path = Path(arguments.transcript_path).expanduser()
        if not transcript_path.is_file():
            raise TranscriptProblem(f"no transcript at {transcript_path}")
        return transcript_path
    return find_transcript_path(
        arguments.session_id, Path(arguments.cd).expanduser().resolve()
    )


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Extract two-voice dialog from a Claude Code session transcript.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--session-id", help="session whose transcript to extract")
    parser.add_argument("--transcript-path", help="explicit JSONL path, bypassing lookup")
    parser.add_argument("--cd", default=".", help="worktree whose project directory holds the session (default: cwd)")
    boundary_group = parser.add_mutually_exclusive_group()
    boundary_group.add_argument("--boundary-quote", help="override: start at this user prompt")
    boundary_group.add_argument("--last-turns", type=int, help="override: carry exactly N final turns")
    parser.add_argument(
        "--minimum-words", type=int, default=MINIMUM_DIALOG_WORDS,
        help=f"dialog the default tail must clear (default {MINIMUM_DIALOG_WORDS})",
    )
    parser.add_argument("--output", help="write here instead of stdout")
    arguments = parser.parse_args(argv)

    if not arguments.session_id and not arguments.transcript_path:
        parser.error("one of --session-id or --transcript-path is required")
    if arguments.last_turns is not None and arguments.last_turns < 1:
        parser.error("--last-turns must be at least 1")
    if arguments.minimum_words < 1:
        parser.error("--minimum-words must be at least 1")

    try:
        transcript_path = resolve_transcript_path(arguments)
    except TranscriptProblem as problem:
        print(f"handoff-extract-conversation: {problem}", file=sys.stderr)
        return 3

    session_id = arguments.session_id or transcript_path.stem

    try:
        turns, skip_counts = read_dialog_turns(transcript_path, include_subagent_tasks_and_reports=True)
        dialog = [turn for turn in turns if turn["voice"] != SUBAGENT_VOICE]
        if not dialog:
            raise TranscriptProblem(
                f"{transcript_path} yielded no dialog turns "
                f"(skipped: {skip_counts}) — refusing to write an empty extraction"
            )

        queued_user_messages = unread_queued_user_messages_with_enqueue_lines(transcript_path)
        if arguments.boundary_quote:
            selected, start_index, quoted_index = select_turns_from_boundary(
                dialog, arguments.boundary_quote, arguments.minimum_words
            )
            boundary_note = (
                f"the prompt quoted as {arguments.boundary_quote.strip()!r} "
                f"(turn {quoted_index + 1})"
            )
            if start_index < quoted_index:
                boundary_note += (
                    f", widened back to turn {start_index + 1} to clear the "
                    f"{arguments.minimum_words}-word floor"
                )
        elif arguments.last_turns:
            start_index = max(0, len(dialog) - arguments.last_turns)
            selected = dialog[start_index:]
            boundary_note = f"final {len(selected)} turns (explicit turn count)"
        else:
            selected, start_index = select_tail_clearing_floor(
                dialog, arguments.minimum_words, keep_short_final_agent_turns=bool(queued_user_messages))
            boundary_note = (
                f"the tail of the conversation clearing {arguments.minimum_words} words, "
                f"opening at the user prompt on turn {start_index + 1}"
            )
    except TranscriptProblem as problem:
        print(f"handoff-extract-conversation: {problem}", file=sys.stderr)
        return 4

    # stderr also carries the note, so the supervisor's console shows the tracker's failure as it happens.
    for note in turns_left_out_notes(turns):
        print(f"handoff-extract-conversation: {note['text']}", file=sys.stderr)

    report = ExtractionReport(
        session_id=session_id,
        transcript_path=transcript_path,
        boundary_note=boundary_note,
        turns_left_behind=start_index,
        total_turns=len(dialog),
        skip_counts=skip_counts,
        left_out_notes=turns_left_out_notes(turns),
        queued_user_messages_never_read_by_agent=queued_user_messages,
    )

    for line in render_extraction_diagnostics(selected, report):
        print(f"handoff-extract-conversation: {line}", file=sys.stderr)

    if arguments.output:
        output_path = Path(arguments.output).expanduser()
        # The tail leaves out every subagent turn, so a session with one also gets its complete dialog.
        if len(selected) < len(dialog) or subagent_turn_count(turns):
            report.companion_path = output_path.with_name(
                f"{output_path.stem}-complete{output_path.suffix}"
            )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(render_extraction(selected, report), encoding="utf-8")
        print(f"wrote {len(selected)} turns to {output_path}", file=sys.stderr)
        if report.companion_path:
            report.companion_path.write_text(
                render_companion(turns, report), encoding="utf-8")
            print(f"wrote all {len(turns) - len(turns_left_out_notes(turns))} turns to {report.companion_path}",
                  file=sys.stderr)
    else:
        sys.stdout.write(render_extraction(selected, report))

    return 0


if __name__ == "__main__":
    sys.exit(main())
