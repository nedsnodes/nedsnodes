#!/usr/bin/env python3
"""Mark one idle-sweep reminder irrelevant, by the message_id the reminder names.

An agent-seat on ned-box runs this with the id its reminder gives, by the command line the
reminder writes, which names this program by its absolute path in the checkout the idle sweep runs
from. The Bash call in the agent-seat's transcript is the record:
scripts/agent-seat-idle-sweep-verdicts-print.py reads the id from the call's command line, whatever
this program printed, and at the idle sweep's first run after the agent-seat is idle again, the
sweep ends the wait the message with that id was sent on, with no repeat or escalation. An id that
names no message sent on the agent-seat's open wait ends nothing. This program writes nothing; it
checks the id against the idle sweep's log on ned-box, so that the agent-seat learns at once when it
copied an id wrong. It checks only the default log, LOG_FILE, not a log a sweep run by hand was
given with --log-file.

Exit 0 when the idle sweep's log holds a sent message with that id; 1 when it holds no such
message; 2 when the id is not 32 lowercase hexadecimal digits, or the log cannot be checked.
"""

import argparse
import json
import re
import sys
from pathlib import Path

# The idle sweep's own log, as
# scripts/agent-seat-idle-sweep-headless-judge-wake-messages-send-and-user-alerts-write.py writes it.
LOG_FILE = (Path.home() / "nedsnodes-logs" / "agent-seat-idle-sweep"
            / "agent-seat-idle-sweep-messages-sent-and-verdicts.jsonl")
MESSAGE_ID_PATTERN = re.compile(r"[0-9a-f]{32}")
COPY_THE_ID_AGAIN_INSTRUCTION = (
    f"If the command you ran was not the reminder's own line copied unchanged: copy the whole "
    f"command line that names `{Path(__file__).name}`, near the end of the reminder, and run it "
    "exactly as the reminder writes it.\nIf it was that line unchanged: do not run this program "
    "for it again, and go on with your work. The idle sweep logs a reminder only when the "
    "agent-session that sent it ends, which can be minutes after the reminder reached you; the "
    "command you ran stays in your transcript and counts once the reminder is logged.")


class LogCannotBeChecked(Exception):
    pass


def sent_message_with_id(log_file, message_id):
    """The message_sent event the log holds with this message_id, or None. A log not yet made holds
    no message. Read as the idle sweep's SweepLog reads it: a last line with no newline, which the
    sweep may be writing, is skipped, and any other line that is not UTF-8 JSON raises
    LogCannotBeChecked, as does a log that cannot be read."""
    if not log_file.exists():
        return None
    try:
        lines = log_file.read_bytes().split(b"\n")
    except OSError as error:
        raise LogCannotBeChecked(f"it could not be read: {error}") from error
    for number, raw in enumerate(lines, start=1):
        if not raw.strip():
            continue
        try:
            event = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, ValueError) as error:
            if number == len(lines):
                continue
            raise LogCannotBeChecked(f"its line {number} is not UTF-8 JSON: {error}") from error
        if (isinstance(event, dict) and event.get("event") == "message_sent"
                and event.get("message_id") == message_id):
            return event
    return None


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("message_id", help="the id the reminder names")
    arguments = parser.parse_args(argv)
    if not MESSAGE_ID_PATTERN.fullmatch(arguments.message_id):
        print(f"Nothing is marked irrelevant: the argument {arguments.message_id!r} is not a reminder's "
              "message_id, which is 32 characters, each a digit or a lowercase letter a to f."
              f"\n{COPY_THE_ID_AGAIN_INSTRUCTION}",
              file=sys.stderr)
        return 2
    try:
        sent = sent_message_with_id(LOG_FILE, arguments.message_id)
    except LogCannotBeChecked as error:
        print(f"The reminder {arguments.message_id} cannot be checked, because of the idle sweep's "
              f"log {LOG_FILE}: {error}\nNothing more is needed from you: the idle "
              "sweep reads its log every minute, and when it cannot read the log it opens a task "
              "for the agent-seat that owns it, reboot-test. The command you just ran stays in "
              "your transcript, so once the log can be read again the idle sweep stops this "
              "reminder, provided you copied its id from the reminder's own command line.",
              file=sys.stderr)
        return 2
    if sent is None:
        print(f"Nothing is marked irrelevant: the idle sweep's log {LOG_FILE} holds no message "
              f"with the id {arguments.message_id}.\n{COPY_THE_ID_AGAIN_INSTRUCTION}",
              file=sys.stderr)
        return 1
    print(f"Marked irrelevant: the idle sweep's reminder {arguments.message_id}, sent to "
          f"{sent.get('agent_seat')} at {sent.get('send_started_at') or sent.get('at')}. The idle "
          "sweep runs every minute; at its first run after you are idle again it finds this command "
          "in your transcript and "
          "sends no repeat or escalation about this reminder. A reminder with another "
          "id is not affected. Nothing more is needed from you.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
