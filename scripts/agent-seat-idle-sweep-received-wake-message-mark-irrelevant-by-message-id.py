#!/usr/bin/env python3
"""Mark one idle-sweep reminder irrelevant, by the message_id the reminder names.

An agent-seat on ned-box runs this with the id its reminder gives, as
`python3 scripts/agent-seat-idle-sweep-received-wake-message-mark-irrelevant-by-message-id.py <message_id>`.
The Bash call in the agent-seat's transcript is the record: scripts/agent-seat-idle-sweep-verdicts-print.py
reads the id from the call's command line, whatever this program printed, and at its next run,
within a minute, the idle sweep ends the wait the message with that id was sent on, with no repeat,
escalation or user-alert. An id that names no message sent on the agent-seat's open wait ends
nothing. This program writes nothing; it checks the id against the idle sweep's log on ned-box, so
that the agent-seat learns at once when it copied an id wrong.

Exit 0 when the idle sweep's log holds a sent message with that id; 2 when the id is not 32
lowercase hexadecimal digits; 1 when the log cannot be read or holds no such message.
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
PROGRAM_PATH_IN_REPOSITORY = f"scripts/{Path(__file__).name}"
COPY_THE_ID_AGAIN_INSTRUCTION = (
    f"If the command you ran was not the reminder's own line copied unchanged: copy the whole "
    f"command line that starts `python3 {PROGRAM_PATH_IN_REPOSITORY}`, near the end of the "
    "reminder, and run it exactly as the reminder writes it.\nIf it was that line unchanged: the "
    "reminder did not come from ned-box's idle sweep, so do not run this program for it again; "
    "ignore the reminder and go on with your work.")


def sent_message_with_id(log_file, message_id):
    """The message_sent event the log holds with this message_id, or None. A line that does not
    parse, such as the last one while the sweep is writing it, is skipped. A log not yet made holds
    no message."""
    if not log_file.exists():
        return None
    with log_file.open(encoding="utf-8", errors="replace") as stream:
        for line in stream:
            try:
                event = json.loads(line)
            except ValueError:
                continue
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
    except OSError as error:
        print(f"The reminder {arguments.message_id} cannot be checked, because the idle sweep's log "
              f"{LOG_FILE} could not be read: {error}\nNothing more is needed from you: the idle "
              "sweep reads its log every minute, and when it cannot read the log it opens a task "
              "for the agent-seat that owns it, reboot-test. The command you just ran stays in "
              "your transcript, so once the log can be read again the idle sweep stops this "
              "reminder, provided you copied its id from the reminder's own command line.",
              file=sys.stderr)
        return 1
    if sent is None:
        print(f"Nothing is marked irrelevant: the idle sweep's log {LOG_FILE} holds no message "
              f"with the id {arguments.message_id}.\n{COPY_THE_ID_AGAIN_INSTRUCTION}",
              file=sys.stderr)
        return 1
    print(f"Marked irrelevant: the idle sweep's reminder {arguments.message_id}, sent to "
          f"{sent.get('agent_seat')} at {sent.get('send_started_at') or sent.get('at')}. The idle "
          "sweep runs every minute; at its next run it finds this command in your transcript and "
          "sends no repeat, escalation or user-alert about this reminder. A reminder with another "
          "id is not affected. Nothing more is needed from you.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
