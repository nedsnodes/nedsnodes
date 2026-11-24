#!/usr/bin/env python3
"""The idle sweep's second build-slice: find each idle ned-box agent-seat with something to do, and
wake it with a cross-session message, judged by a headless agent-session where code cannot decide.

Design: docs/issues/940-tasks-raise-themselves-when-their-due-time-passes.md, § The idle sweep.
Cron runs this every minute on ned-box, from the entry in
nn-systems/general-tools/scheduled-jobs-on-each-machine.json.

Each invocation, under a lock that keeps two from overlapping:
1. Reads its log, the one record of what it has done, and derives from it each agent-seat's state:
   the last check, the open wait and its step, the sentences already checked, each usage-limit
   record seen and woken, the account last seen, and the messages whose delivery is not yet
   checked.
2. Takes slice 1's verdict for each agent-seat, by calling verdict_for_seat in
   scripts/agent-seat-idle-sweep-verdicts-print.py, which is the only reader of the transcripts,
   walk-minutes and task lists. Each prerequisite a verdict names as not asked of GitHub because
   the time budget for GitHub calls was spent is logged, at every invocation that skips it, as a
   github_conditions_skipped_for_budget event.
3. When `oauthAccount.accountUuid` in ~/.claude.json differs from the account last logged, sends
   every agent-seat with a running agent-session the account-change notice, through one headless
   agent-session; for an agent-seat idle at a usage limit, that notice is its limit wake.
4. Looks, a minute or more after each send, for the message in the agent-seat's transcript, once
   the agent-seat's turn has ended, and gives OWNING_AGENT_SEAT a task when it is not there.
5. For each idle agent-seat, applies the verdict's rule, skipping each step that starts a headless
   agent-session while a headless usage-limit pause holds, as "How it fails" below says: rule 1 wakes it once its limit has ended;
   rule 2 has unbacked promises and announced actions judged and named to it; rule 3 sends the
   handoff text; rule 4 ends a wait no rule 2 message was sent on; rule 5 has the judge
   decide whether to message it, and write the message. The judge is not told of a background
   command whose verdict gives a `timeout_ends_at` not yet reached, since such work ends by itself, nor of a background command, subagent or workflow a rule 5 message
   has already named, since the sweep asks once about each; when something runs and all of it is
   such work, the judge is not asked. Code ends a rule 5 message with a list of the open tasks
   the judge raised, and a task counts as raised only when the text sent lists it. Neither is
   the judge told of an open task a rule 5 message has
   already raised in this agent-session since the user last typed in it, unless the agent-seat has
   since recorded something the task waits on, and rule 3 does not send again about the same
   put-off handoff in that time, leaving the open tasks to the judge; when nothing else is left,
   nothing is sent. A
   wait whose rule 2 messages named only
   promises to act after an event and hold sentences ends when the agent-seat has recorded, after each
   message, one task per sentence it and the later messages named, a message whose send failed
   included, each with a TaskCreate or TaskUpdate call whose result
   succeeded and that sets `metadata.prerequisites` or `addBlockedBy`. A message starts a wait, unless a wait is
   already open: 15 minutes later, if the agent-seat is idle, code sends the escalation, which
   quotes the message that opened the wait and each rule 2 message whose send on the open wait
   failed, and 15 minutes after that writes the user a user-alert, once, which names the sentences
   of those failed messages too.

Every message to an agent-seat goes through Sweep.send_wake_message, which ends it with
DO_NOT_REPLY_SENTENCE: the headless agent-session that sends it reads no reply, and may still
be running when the agent-seat reads it.

Headless agent-sessions: `claude -p --model sonnet` in an empty working directory under the state
directory. A sender is allowed only SendMessage, ListAgents and ToolSearch; the rule 2 and rule 5
judges get no tool and send nothing. Code finds the ListAgents ref of the agent-session each
agent-seat's handoff-supervisor launched last, from Claude Code's session records, and tells
the sender to write only to the entry with that ref, whatever its name or tmux session; an
agent-seat with no running agent-session of that id is sent nothing, and is a user-alert. Each
answers JSON through --json-schema, and code reads a sender's SendMessage calls from its
stream-json output and checks each against that ref and the text code wrote. Each is stopped after
5 minutes.

What it does not handle: it runs only on ned-box and reads only ned-box's agent-seats. One
invocation runs its headless agent-sessions one after another, so a slow judge delays every other
agent-seat's step, and the lock makes the next minute's invocation skip, until it ends. A wait
does not end when the agent-seat only replies to a message in text; it ends when the agent-seat
makes a tool call after the nudge that opened the wait or has nothing to do (rule 4), in either
case only when no rule 2 message was sent on the wait, makes the task call a rule 2 message
asked for, as step 5 says, stops at a usage limit (rule 1), starts a
new agent-session, or spends tokens after the user was told. So an agent-seat that answers a
rule 3 or rule 5 message with a tool call and goes idle again is nudged again only about something
new, or once the user has typed, and is not escalated; a command that hangs after the one
question about it reaches nobody until the agent-seat looks. One that answers a rule 2 message
with a tool call and a fresh promise is escalated, because a tool call that ended a promise wait
would let an agent-seat that makes a fresh promise at each rule 2 message be nudged again forever
and never escalated.

How it fails, and who hears: each failure of this program goes to the agent-seat that owns it,
OWNING_AGENT_SEAT, as a task on its task list, one open task for each subject; the agent-seat
tells the user only when the fix needs a change to a guarded system or it cannot find the cause.
The user gets a user-alert only when that task cannot be written. The failures are: a sender
that sends a text other than the one code wrote, whose text is logged as a
sent_text_differs_from_code_text event, and which step 4's delivery check then looks for; a
headless agent-session that fails, is stopped, answers JSON code cannot use, or sends to the
wrong entry, with one subject for each cause code names, however claude's text for that cause
varies; a message missing from the agent-seat's transcript; a read failure slice 1 reports for
the same agent-seat with the same text at every run for 2 minutes or more, counted from the
failure's first run and through any invocation the lock made skip, since only a run that does
not meet the failure ends the count; and any other failure, such as an unwritable log, which
also prints a traceback. The invocation goes on to the other agent-seats, then exits 1. A read
failure seen once only, such as the last line of a transcript Claude Code is still writing, is
logged and not reported; a run that does not meet it again logs its end, so that it coming back
later is dated from its return. A headless agent-session stopped at a usage limit whose reset
time its own transcript carries opens no task: code logs a headless_usage_limit_pause event, and
starts no headless agent-session, for any agent-seat, until that time passes or the logged-in
account changes; a rule 2 judge stopped so logs neither the check nor its sentences, so that
they are judged after the pause. A message step is logged before its send, so a failed send is not retried every
minute: the wait goes on to its next step.
The harm it can cause is an extra message to an agent-seat, which costs that agent-seat one turn.
"""

import argparse
import fcntl
import hashlib
import importlib.util
import json
import os
import re
import shutil
import signal
import socket
import subprocess
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path


def _load(module_name, path):
    specification = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


_SCRIPTS = Path(__file__).resolve().parent
verdicts_print = _load("agent_seat_idle_sweep_verdicts_print",
                       _SCRIPTS / "agent-seat-idle-sweep-verdicts-print.py")
fields = verdicts_print.fields
user_alerts = _load("user_alerts_pending_and_claimed_files_write_claim_release_and_delete_common",
                    _SCRIPTS.parent / "nn-systems" / "general-tools"
                    / "user-alerts-pending-and-claimed-files-write-claim-release-and-delete-common.py")
agent_seat_task_list = _load(
    "agent_seat_task_list_new_pending_task_write_common",
    _SCRIPTS.parent / "nn-systems" / "general-tools" / "agent-seat-task-list-new-pending-task-write-common.py")
headless_command_line = _load(
    "claude_code_headless_run_command_line_prefix_with_no_connectors_and_explicit_permission_mode_common",
    _SCRIPTS.parent / "nn-systems" / "general-tools"
    / "claude-code-headless-run-command-line-prefix-with-no-connectors-and-explicit-permission-mode-common.py")

LOG_FILE = (Path.home() / "nedsnodes-logs" / "agent-seat-idle-sweep"
            / "agent-seat-idle-sweep-messages-sent-and-verdicts.jsonl")
STATE_DIRECTORY = (Path.home() / ".local" / "state" / "nedsnodes"
                   / "agent-seat-idle-sweep-run-lock-and-headless-agent-session-empty-working-directory")
# The folder's name is the name the receiving agent-seat sees the message come from.
HEADLESS_WORKING_DIRECTORY_NAME = "agent-seat-idle-sweep"
RUN_FAILURES_ALERTED_FILE_NAME = "run-failures-alerted.txt"
# The agent-seat that owns this program: each failure of the program goes to its task list, and
# the user hears of one only through that agent-seat, or when the task cannot be written.
OWNING_AGENT_SEAT = "reboot-test"
PROGRAM_PATH_IN_REPOSITORY = f"scripts/{Path(__file__).name}"
SENT_TEXT_DIFFERS_TASK_SUBJECT = "Idle sweep: a headless sender sent a text other than the one code wrote"
OWNING_AGENT_SEAT_TASK_LAST_LINES = (
    "Tell the user only if the fix needs a change to a guarded system, or if you cannot find the "
    "cause.\nMark this task completed when the cause is fixed; the idle sweep opens a new task at "
    "its next failure with this subject.")
# Logged when a headless agent-session stops at a usage limit whose reset time its transcript
# carries: no headless agent-session starts until that time, or until the account changes.
HEADLESS_USAGE_LIMIT_PAUSE = "headless_usage_limit_pause"

WAIT_STEP_SECONDS = 15 * 60
JUDGE_ASK_AGAIN_SECONDS = 15 * 60
LIMIT_WAKE_GRACE_SECONDS = 5 * 60
DELIVERY_CHECK_AFTER_SECONDS = 60
# Claude Code stamps a record when it writes it, which may be a moment before the send returns.
DELIVERY_CLOCK_SLACK_SECONDS = 120
READ_FAILURE_ALERT_AFTER_SECONDS = 2 * 60
HEADLESS_TIMEOUT_SECONDS = 5 * 60
HEADLESS_MODEL = "sonnet"
SENDING_TOOLS = "SendMessage,ListAgents,ToolSearch"
# Claude Code's session records, one <pid>.json file for each running agent-session, under HOME.
SESSION_RECORDS_DIRECTORY_UNDER_HOME = Path(".claude") / "sessions"
# The [ref] at the end of a SendMessage "to", as in "Cpc [9ea9da]".
TO_REF = re.compile(r"\[(?P<ref>[0-9a-f]+)\]\s*$")
JUDGED_TEXT_CHARACTERS = 4000

NUDGE, ESCALATE, TELL_USER = "nudge", "escalate", "tell_user"
# A wait step recording that the wait carries a rule 2 message, which rule 4 does not settle.
PROMISE = "promise"
LIMIT_WAKE, ACCOUNT_NOTICE = "limit_wake", "account_notice"

# Kinds of headless failure that run_headless does not name, for headless_failed's key.
SENDS_WRONG = "the sender's SendMessage calls were not the sends code asked for"
JUDGE_ANSWER_UNUSABLE = "the judge's answer could not be used"
DO_NOT_REPLY_SENTENCE = "Do not reply to this message: the idle sweep sent it, and nothing acts on a reply."
ESCALATION_TEXT = ("You've given this {minutes} minutes, please check; if not sure, hand off. At "
                   "{nudge_time} the idle sweep wrote this, which you have not acted on:\n\n"
                   "{quoted_nudge}")
FAILED_PROMISE_ESCALATION_TEXT = ("\n\nAt {time} the idle sweep tried to send you this too, and the "
                                  "send failed:\n\n{quoted_text}")
LIMIT_WAKE_TEXT = ("The usage limit that stopped you has ended: {why}. Carry on with the work the "
                   "limit stopped.")
LIMIT_ENDED_BY_RESET = "its reset time has passed"
LIMIT_ENDED_BY_ACCOUNT = "the claude.ai account logged in on {machine} changed"
ACCOUNT_NOTICE_TEXT = (
    "The claude.ai account logged in on {machine} changed at {time}. Usage limits are now the new "
    "account's, so a limit message you saw before then, with its reset time, may no longer apply. "
    "Retry now any work a usage limit stopped that has not run again since, such as a subagent or "
    "a cold-read-cell; if the retry "
    "stops on a limit again, that limit is the new account's. A page you published to claude.ai "
    "under the earlier account, such as an approval-walk item page, may not open for the user; "
    "GitHub issue [A read-only web server on ned-box renders Markdown files as web pages on the "
    "LAN, for approval-walk item pages and other pages agents publish to claude.ai that only show "
    "text](https://github.com/nedsnodes/nedsnodes/issues/2175) covers serving such pages from "
    "ned-box.")
UNBACKED_SENTENCE_LINES = {
    fields.ANNOUNCED_ACTION: ("You said \"{sentence}\" {minutes} minutes ago and have not done it. "
                              "Do it now, or tell the user why not."),
    fields.PROMISE_AFTER_EVENT: ("You promised \"{sentence}\". Record it as a task whose "
                                 "prerequisites name the event, or tell the user you take the "
                                 "promise back."),
    fields.STANDING_RULE: ("You said \"{sentence}\". Back it with the hook or test that enforces it, "
                           "or a task to build one and a proposal to the user, or tell the user you "
                           "take it back."),
    fields.HOLD: ("You said \"{sentence}\". Record a task whose prerequisites name what releases the "
                  "hold, or tell the user you are no longer holding."),
}
# The kinds of sentence whose message asks for a task call that code can see: one that sets
# prerequisites or addBlockedBy. An announced action or a standing rule only the judge finds done.
TASK_CALL_SETTLED_KINDS = frozenset((fields.PROMISE_AFTER_EVENT, fields.HOLD))
# On a rule 5 judge_answer event: the ids of the background commands, subagents and workflows its
# message asked about, which no later rule 5 message asks about again.
RUNNING_WORK_ASKED_ABOUT = "running_work_asked_about"
# Logged after a rule 3 or rule 5 message reaches its sender: what it reminded the agent-seat of.
REMINDER_SENT = "reminder_sent"
# An event logged with each rule 2 message, carrying the sentences it names and their kinds.
PROMISE_MESSAGE = "promise_message"
# On an open wait: the rule 2 messages sent on it, [{"at", "kinds", "sentences"}], or None when one
# of them was sent by a version of this program that logged no sentences for it.
PROMISE_MESSAGES = "promise_messages"
# An event logged when a rule 2 message's send on an open wait failed, carrying its text and the
# sentences it names, since no message_sent or promise_message event holds them.
PROMISE_MESSAGE_SEND_FAILED = "promise_message_send_failed"
# On an open wait: the rule 2 messages whose send on it failed, [{"at", "kinds", "sentences", "text"}].
FAILED_PROMISE_MESSAGES = "failed_promise_messages"

SEND_ANSWER_SCHEMA = {"type": "object", "required": ["sent", "reason"],
                      "properties": {"sent": {"type": "boolean"}, "reason": {"type": "string"}}}
OPEN_TASK_IDS_RAISED = "open_task_ids_raised"
IDLE_JUDGE_ANSWER_SCHEMA = {
    "type": "object", "required": ["send", "message", "reason", OPEN_TASK_IDS_RAISED],
    "properties": {"send": {"type": "boolean"}, "message": {"type": "string"},
                   "reason": {"type": "string"},
                   OPEN_TASK_IDS_RAISED: {
                       "type": "array", "items": {"type": "string"},
                       "description": "The id of every task in open_tasks_nothing_holds that the "
                                      "agent-seat could act on now, whether or not the message "
                                      "names it: the program lists these tasks at the end of the "
                                      "message. Empty when send is false or none could be acted "
                                      "on."}}}
SENTENCES_ANSWER_SCHEMA = {
    "type": "object", "required": ["sentences"],
    "properties": {"sentences": {"type": "array", "items": {
        "type": "object", "required": ["index", "backed", "reason"],
        "properties": {"index": {"type": "integer"}, "backed": {"type": "boolean"},
                       "reason": {"type": "string"}}}}}}

# Without this sentence, a sender dropped the last sentence from a message that asks the agent-seat
# a question, taking it for an instruction to the sender.
KEEP_THE_LAST_SENTENCE = (
    f'The text ends with the sentence "{DO_NOT_REPLY_SENTENCE}" That sentence is written to the '
    "agent-seat, not to you, and is part of the message: keep it.")

FIND_THE_ENTRY = """\
Find the agent-seat's entry with ListAgents (load ListAgents and SendMessage with ToolSearch first \
if they are not loaded). Its entry is the one whose ref is [{ref}], whatever name it is listed by, \
because the user can rename an agent-session, as in "Cpc [{ref}] · interactive". Write only to that \
entry, never to another, even one named {seat} or in the tmux session {seat}. In SendMessage's \
"to", give the name and the ref as ListAgents lists them, as in "Cpc [{ref}]". If no entry has the \
ref [{ref}], send nothing."""

SENDER_PROMPT = """\
You deliver one message for the idle sweep, a program on ned-box that wakes idle agent-seats. You \
judge nothing: the program has decided the message is sent.

The agent-seat is {seat}. {find_the_entry}

Send it one message with SendMessage, whose "message" is the text between the two lines of dashes \
below, exactly as written, with nothing added or removed. {keep_the_last_sentence} Then answer: \
sent true if SendMessage succeeded, otherwise false, and reason, one sentence.
----------
{text}
----------"""

NOTICE_SENDER_PROMPT = """\
You deliver one notice for the idle sweep, a program on ned-box. You judge nothing: the program has \
decided the notice is sent.

Send it, with one SendMessage call for each, to each of these agent-seats, each given with the \
ref of its entry: {seats}. For each agent-seat, {find_the_entry}

Each message is the text between the two lines of dashes below, exactly as written, with nothing \
added or removed. {keep_the_last_sentence} Then answer: sent true if every send succeeded, \
otherwise false, and reason, one sentence naming any agent-seat you could not send to.
----------
{text}
----------"""

IDLE_JUDGE_PROMPT = """\
You judge one idle agent-seat for the idle sweep, a program on ned-box. The agent-seat {seat} has \
spent no tokens for {idle_minutes} minutes, and its last turn has ended. Code could not settle the \
case: something may be left for it to do, or it may rightly be waiting. The facts code found are in \
the JSON below. An approval-walk item waiting on the user holds back only that walk, not the \
agent-seat's other work. The agent-seat knows what it is waiting on the user for: never mention \
that wait in the message, and when waiting on the user is all that is left, such as an open task \
that is the running of that approval-walk, send no message.

Judge whether the agent-seat could act now. If it could, write it one short message saying what you \
saw. Name each background command, workflow and subagent that has not finished or reported, \
with how long it has run, and ask whether it is taking longer than expected. Name a background \
command by its description, in quotation marks, followed by its id in brackets, or by its id \
alone when its description is null, and a subagent or workflow by its id, such as "Your background command "Run the idle-sweep test \
suites" (b7k2m4qzp) started 25 minutes ago and has not finished. Is it taking longer than \
expected?". \
A subagent with stopped_at has stopped and reported: it is not running, and only the background \
commands it launched, under own_running_background_commands, still run. Say so, and name each of \
those commands with how long it has run, such as "Your subagent ae10c20d94ca876c9 reported 20 \
minutes ago. Your subagent's background command "Check which recorded surviving mutants current \
main kills" (bk9617lvz) started 29 minutes ago and has not finished. Is it still needed?". \
With nothing running, ask what is going on, such as "Your task "Open the pull request for the \
reviewed fix" is open and nothing holds it, and you have made no tool call for 12 minutes. What's \
going on?". If it could not act now, write \
no message. Send nothing yourself: the program sends the message.

Answer: send, whether the agent-seat should get a message; message, the message, or an empty string \
when send is false; and reason, one sentence on why, such as "a subagent started 3 minutes ago is \
still running".

{facts}"""

SENTENCES_JUDGE_PROMPT = """\
You judge sentences for the idle sweep, a program on ned-box. The agent-seat {seat} is idle, and \
messages that ended its turns hold the sentences below, each a promise or an announced action. For \
each sentence, judge whether it is backed, by these rules:

- An announced action, such as "Next I'm starting the pull request", is backed when a tool call in \
the same turn, before or after the sentence, or a later one does the action, or a background task \
it started is still running.
- A promise to act after an event, such as "I'll report when PR 927 merges", is backed by a task \
whose prerequisites or blockedBy name the event, so the idle check raises it.
- A standing rule, such as "from now on" or "Noted", is backed by the hook or test that enforces \
it, or by a task to build one together with a proposal to the user; a memory never backs it.
- A hold, such as "I'll hold", is backed by a task whose prerequisites name what releases the hold.

Judge each sentence by the rule of the kind the JSON gives it, because the message that names an \
unbacked sentence is worded for that kind; a sentence that, read whole, only declines an action \
and commits the agent-seat to nothing later, such as "ned-box's load is near 22, so I'm starting \
nothing else for now", leaves nothing undone: it is backed. A hold or a promise to act after an \
event puts off an action until something happens; judge it by its own rule above.

The tool calls the agent-seat made from the earliest sentence's turn on are in the JSON below, with \
the tasks they created or updated and the files they changed; so are its open tasks that have \
prerequisites or blockedBy, whenever they were created, and what is running. Send nothing. \
Answer, for every sentence by its index, backed true or false, and reason, one sentence.

{facts}"""


# --- The log, and the state derived from it ---

class IdleSweepLogLineNotUtf8Json(Exception):
    pass


class SweepLog:
    """The append-only JSONL log: each message sent, each verdict, each user-alert written."""

    def __init__(self, path):
        self.path = path
        self.events = []
        # An event written after a last line with no newline would join it into a line that, no
        # longer last, would stop every later read. A cut-short line the read skipped is dropped
        # by truncating to this size; a whole one the read accepted only gets its newline. Set at
        # the read, so that an append need not read the log again.
        self.truncate_to = None
        self.add_newline = False
        if path.exists():
            data = path.read_bytes()
            lines = data.split(b"\n")
            for number, raw in enumerate(lines, start=1):
                if not raw.strip():
                    continue
                try:
                    event = json.loads(raw.decode("utf-8"))
                except (UnicodeDecodeError, ValueError) as error:
                    # A last line with no newline is one an invocation was stopped while writing.
                    if number == len(lines):
                        self.truncate_to = data.rfind(b"\n") + 1
                        continue
                    raise IdleSweepLogLineNotUtf8Json(
                        f"{path} line {number} is not UTF-8 JSON: {error}") from error
                if isinstance(event, dict):
                    self.events.append(event)
            self.add_newline = (self.truncate_to is None and bool(data)
                                and not data.endswith(b"\n"))

    def append(self, event, now, agent_seat_idle_sweep_invocation_started_at):
        event = {"at": iso(now), "agent_seat_idle_sweep_invocation_started_at":
                 iso(agent_seat_idle_sweep_invocation_started_at), **event}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.truncate_to is not None:
            os.truncate(self.path, self.truncate_to)
        elif self.add_newline:
            with self.path.open("ab") as stream:
                stream.write(b"\n")
        self.truncate_to, self.add_newline = None, False
        with self.path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")
        self.events.append(event)
        return event

    def of_seat(self, seat, *kinds):
        return [event for event in self.events
                if event.get("agent_seat") == seat and event.get("event") in kinds]

    def last_check(self, seat):
        checks = self.of_seat(seat, "checked")
        return checks[-1] if checks else None

    def open_wait(self, seat):
        wait = None
        # Whether a PROMISE step awaits its PROMISE_MESSAGE, and the invocation that logged the
        # step.
        owed, owed_by = False, None
        for event in self.of_seat(seat, "wait_step", "wait_ended", PROMISE_MESSAGE,
                                  PROMISE_MESSAGE_SEND_FAILED):
            invocation = event.get("agent_seat_idle_sweep_invocation_started_at")
            if event["event"] == "wait_ended":
                wait, owed = None, False
            elif event["event"] == PROMISE_MESSAGE_SEND_FAILED:
                if wait is not None:
                    wait[FAILED_PROMISE_MESSAGES].append({
                        "at": event["at"], "kinds": set(event["kinds"]),
                        "sentences": event["sentences"], "text": event["text"]})
                owed = False
            elif event["event"] == PROMISE_MESSAGE:
                if wait is None:
                    continue
                if (owed and owed_by != invocation) or "sentences" not in event:
                    wait[PROMISE_MESSAGES] = None
                elif wait[PROMISE_MESSAGES] is not None:
                    wait[PROMISE_MESSAGES].append({
                        "at": event.get("send_started_at", event["at"]),
                        "kinds": set(event["kinds"]), "sentences": event["sentences"]})
                owed = False
            elif event["step"] == NUDGE or (wait is not None and event["step"] == PROMISE):
                if event["step"] == NUDGE:
                    wait = {"session_id": event["session_id"],
                            "first_idle_at": event["first_idle_at"], NUDGE: event["at"],
                            "nudge_text": event["text"], PROMISE_MESSAGES: [],
                            FAILED_PROMISE_MESSAGES: []}
                    owed = False
                    if event.get("rule") != 2:
                        continue
                wait[PROMISE] = event["at"]
                owed, owed_by = True, invocation
            elif wait is not None:
                wait[event["step"]] = event["at"]
        return wait

    def last_judge_answer(self, seat):
        answers = [event for event in self.of_seat(seat, "judge_answer") if event.get("rule") == 5]
        return answers[-1] if answers else None

    def running_work_asked_about(self, seat):
        """The running work rule 5 messages named, less what a message the delivery check did not
        find in the agent-seat's transcript named."""
        not_found = {event["message_id"] for event in self.of_seat(seat, "delivery_checked")
                     if not event["found"]}
        return {work_id for event in self.of_seat(seat, "judge_answer") if event.get("rule") == 5
                and event.get("message_id") not in not_found
                for work_id in event.get(RUNNING_WORK_ASKED_ABOUT, [])}

    def reminded_subjects(self, seat, session_id, last_user_typed_at, last_held_at):
        """What a rule 3 or rule 5 message has reminded this agent-session of since the user last
        typed in it, less what a message the delivery check did not find named and what
        last_held_at, {subject: time}, shows was held after the message arrived."""
        not_found = {event["message_id"] for event in self.of_seat(seat, "delivery_checked")
                     if not event["found"]}
        # Typing or a hold while the sender runs, before the message arrives, has not answered it:
        # until the delivery check gives the time it arrived, the time the send was logged stands in.
        received_at = {event["message_id"]: event["received_at"]
                       for event in self.of_seat(seat, "delivery_checked") if event.get("received_at")}
        typed = parse_time(last_user_typed_at) if last_user_typed_at else None
        reminded = set()
        for event in self.of_seat(seat, REMINDER_SENT):
            if event["session_id"] != session_id or event["message_id"] in not_found:
                continue
            arrived = parse_time(received_at.get(event["message_id"], event["at"]))
            if typed is not None and arrived < typed:
                continue
            reminded.update(subject for subject in event["subjects"]
                            if subject not in last_held_at or last_held_at[subject] < arrived)
        return reminded

    def checked_sentences(self, seat):
        return {(event["record_uuid"], event["sentence"])
                for event in self.of_seat(seat, "sentence_checked")}

    def limit_account(self, seat, record_uuid):
        """The account logged in when code first saw the limit record, the first one known."""
        accounts = [event.get("account") for event in self.of_seat(seat, "limit_seen")
                    if event["record_uuid"] == record_uuid]
        return next((account for account in accounts if account), None), bool(accounts)

    def limit_wakes(self, seat):
        return {event["record_uuid"]: event["at"] for event in self.of_seat(seat, "limit_wake")}

    def last_account(self):
        seen = [event for event in self.events if event.get("event") == "account_seen"]
        return seen[-1]["account"] if seen else None

    def deliveries_pending(self):
        checked = {event["message_id"] for event in self.events
                   if event.get("event") == "delivery_checked"}
        return [event for event in self.events
                if event.get("event") == "message_sent" and event["message_id"] not in checked]

    def read_failure_first_seen(self, seat, text):
        """The event that began the failure's current run: its latest read_failure, unless a
        read_failure_ended follows it."""
        first_seen = None
        for event in self.of_seat(seat, "read_failure", "read_failure_ended"):
            if event["error"] == text:
                first_seen = event if event["event"] == "read_failure" else None
        return first_seen

    def read_failures_open(self):
        open_failures = set()
        record = {"read_failure": open_failures.add, "read_failure_ended": open_failures.discard}
        for event in self.events:
            if event.get("event") in record:
                record[event["event"]]((event["agent_seat"], event["error"]))
        return open_failures

    def headless_usage_limit_pause(self):
        """The last headless_usage_limit_pause event, unless an account_seen event follows it: the
        new account has limits of its own."""
        pause = None
        for event in self.events:
            if event.get("event") == HEADLESS_USAGE_LIMIT_PAUSE:
                pause = event
            elif event.get("event") == "account_seen":
                pause = None
        return pause

    def alerted(self, key):
        return any(event.get("event") == "user_alert" and event.get("key") == key
                   for event in self.events)


def iso(moment):
    return verdicts_print.iso(moment)


def parse_time(stamp):
    return verdicts_print.parse_time(stamp)


def agent_seat_idle_sweep_invocation_started_at(event):
    """The time of the invocation that logged the event. The judge's ask-again and a read
    failure's user-alert count their minutes from that invocation, and compare this time with a
    later invocation's: the event's "at" adds the seconds the invocation had taken, a judge's
    included, so a step due a whole number of minutes later would come a minute late. A wait's
    steps and a limit wake count from "at", the time their message went out. An event logged
    before "agent_seat_idle_sweep_invocation_started_at" was logged has only its "at"."""
    return event.get("agent_seat_idle_sweep_invocation_started_at", event["at"])


def seconds_between(earlier, later):
    earlier = parse_time(earlier) if isinstance(earlier, str) else earlier
    return (later - earlier).total_seconds()


def quoted(text):
    return "\n".join(f"> {line}" for line in text.split("\n"))


def task_calls_settling_promise_messages(promise_messages, task_calls):
    """The task calls that settle a wait's rule 2 messages, or None while they do not.

    They settle the messages when every message named only promises to act after an event and
    holds, and each sentence named can have a task of its own recorded after its message: for each
    message, the distinct tasks the calls after it record are at least as many as the sentences it
    and every later message named. Two calls on one task id count once, a TaskCreate and a later
    TaskUpdate of that task included. Code cannot tell which promise a call backs, so the wait_ended event lists the sentences and the calls for a reader to check."""
    if any(not message["kinds"] <= TASK_CALL_SETTLED_KINDS for message in promise_messages):
        return None
    calls_after = [[call for call in task_calls
                    if call["time"] and parse_time(call["time"]) > parse_time(message["at"])]
                   for message in promise_messages]
    for index, calls in enumerate(calls_after):
        tasks = {call["task"] for call in calls}
        if len(tasks) < sum(len(message["sentences"]) for message in promise_messages[index:]):
            return None
    return calls_after[0]


# --- Headless agent-sessions ---

class HeadlessOutcome:
    def __init__(self):
        self.error = None          # why the headless agent-session failed, or None
        self.error_kind = None     # the error's cause, worded by code alone: a user-alert's key
        self.answer = None         # its --json-schema answer
        self.sends = []            # [{"to", "message", "succeeded", "result"}]
        self.session_id = None     # the agent-session's id, which names its transcript


def claude_binary():
    # Cron's PATH does not hold ~/.local/bin, where claude is installed.
    return shutil.which("claude") or str(Path.home() / ".local" / "bin" / "claude")


def run_headless(prompt, schema, tools, working_directory, timeout_seconds):
    """Run one headless agent-session and read its SendMessage calls and its answer."""
    outcome = HeadlessOutcome()
    command = headless_command_line.claude_code_headless_run_command_line_prefix_build(
        "dontAsk", program=claude_binary()) + [
        "--model", HEADLESS_MODEL, "--output-format", "stream-json", "--verbose",
        "--json-schema", json.dumps(schema), "--tools", tools]
    if tools:
        command += ["--allowedTools", tools]
    working_directory.mkdir(parents=True, exist_ok=True)
    try:
        process = subprocess.Popen(command, cwd=str(working_directory), stdin=subprocess.PIPE,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                                   start_new_session=True)
    except OSError as error:
        outcome.error = f"could not start claude: {error}"
        outcome.error_kind = "could not start claude"
        return outcome
    try:
        stdout, stderr = process.communicate(prompt, timeout=timeout_seconds)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
        stdout, stderr = process.communicate()
        outcome.error = f"stopped after {timeout_seconds} seconds"
        outcome.error_kind = "stopped at its time limit"
    calls, result = {}, None
    for line in stdout.splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if not isinstance(event, dict):
            continue
        if isinstance(event.get("session_id"), str):
            outcome.session_id = event["session_id"]
        if event.get("type") == "result":
            result = event
        content = (event.get("message") or {}).get("content")
        for block in content if isinstance(content, list) else []:
            if not isinstance(block, dict):
                continue
            if block.get("type") == "tool_use" and block.get("name") == "SendMessage":
                tool_input = block.get("input") or {}
                calls[block.get("id")] = {"to": str(tool_input.get("to", "")),
                                          "message": str(tool_input.get("message", "")),
                                          "succeeded": False, "result": None}
            elif block.get("type") == "tool_result" and block.get("tool_use_id") in calls:
                call = calls[block["tool_use_id"]]
                call["succeeded"] = not block.get("is_error")
                call["result"] = str(block.get("content"))[:500]
    outcome.sends = list(calls.values())
    if outcome.error:
        return outcome
    # Such as "usage_limit_reached": the result's text holds a reset time, so it cannot name the cause.
    api_error = f": {result['api_error']}" if result and result.get("api_error") else ""
    if process.returncode != 0:
        outcome.error = f"claude exited {process.returncode}: {(stderr or stdout)[-500:].strip()}"
        outcome.error_kind = f"claude exited {process.returncode}{api_error}"
    elif result is None:
        outcome.error = f"claude gave no result event: {stdout[-500:]!r}"
        outcome.error_kind = "claude gave no result event"
    elif result.get("is_error") or result.get("subtype") != "success":
        outcome.error = f"claude reported an error: {str(result.get('result'))[:500]}"
        outcome.error_kind = f"claude reported an error{api_error}"
    elif not isinstance(result.get("structured_output"), dict):
        outcome.error = outcome.error_kind = "claude gave no JSON answer"
    else:
        outcome.answer = result["structured_output"]
    return outcome


def list_agents_tool_entry_ref_of_running_agent_session_id(session_id):
    """The [ref] ListAgents gives the running agent-session session_id, from Claude Code's
    session records; None when no running agent-session has that id.

    The ref is the first 6 hex digits of the SHA-256 of "session:" and the agent-session's
    messaging socket path, as Claude Code 2.1.330 computes it. Should Claude Code change that, no
    entry has the ref, so the sender sends nothing and the send is reported as failed; and
    scripts/agent-seat-idle-sweep-list-agents-ref-formula-matches-installed-claude-code-test.py
    fails first, comparing this with the refs the installed Claude Code advertises."""
    for path in sorted((Path.home() / SESSION_RECORDS_DIRECTORY_UNDER_HOME).glob("*.json")):
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            # Claude Code rewrites a record while its agent-session runs and deletes it when the
            # agent-session exits, either of which can happen mid-read.
            continue
        if (isinstance(record, dict) and session_id and record.get("sessionId") == session_id
                and isinstance(record.get("messagingSocketPath"), str)):
            socket_path = record["messagingSocketPath"]
            return hashlib.sha256(f"session:{socket_path}".encode()).hexdigest()[:6]
    return None


def list_agents_tool_entry_ref_of_agent_seat_last_handoff_supervisor_launched_agent_session_find(
        seat, handoff_directory):
    """list_agents_tool_entry_ref_of_running_agent_session_id for the agent-session seat's
    handoff-supervisor launched last; None also when its supervisor state cannot be read or names
    none. For a program with no verdict, which holds that agent-session's id."""
    path = verdicts_print.supervisor.supervisor_state_path(Path(handoff_directory).expanduser(), seat)
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(state, dict):
        return None
    return list_agents_tool_entry_ref_of_running_agent_session_id(
        state.get(verdicts_print.LAUNCHED_SESSION_ID_KEY)
        or state.get(verdicts_print.LEGACY_SESSION_ID_KEY))


def entry_seat(to, refs):
    """The agent-seat a SendMessage "to" reaches: the one in refs, {agent-seat: ref}, whose
    current agent-session's ref the "to" ends with; None for any other entry. The name in "to"
    does not count: the user can rename an agent-session, and a session started inside an
    agent-seat's tmux pane, such as a reviewer, is listed in the agent-seat's tmux session."""
    match = TO_REF.search(to)
    return next((seat for seat, ref in refs.items() if match and ref == match["ref"]), None)


def send_problems(outcome, refs):
    """What is wrong with where a sender sent: each send must go to one of the agent-seats in
    refs, and a send to each must succeed."""
    problems = [f"sent to {send['to']!r}, which is not {', '.join(refs)}"
                for send in outcome.sends if entry_seat(send["to"], refs) is None]
    for seat in refs:
        if not any(send["succeeded"] and entry_seat(send["to"], refs) == seat
                   for send in outcome.sends):
            problems.append(f"no SendMessage to {seat} succeeded")
    return problems


def sent_texts_other_than_code_wrote(outcome, refs, text):
    """Each send to one of the agent-seats in refs whose message is not the text code wrote, as
    (agent-seat, message)."""
    # Compared as the delivery check compares: a sender may reflow the lines of the text.
    return [(entry_seat(send["to"], refs), send["message"]) for send in outcome.sends
            if entry_seat(send["to"], refs) is not None
            and " ".join(send["message"].split()) != " ".join(text.split())]


def text_sent_to(outcome, refs, seat, text):
    """The message of the last send to the agent-seat that succeeded, or code's text when none
    did: the text the delivery check looks for."""
    sent = [send["message"] for send in outcome.sends
            if send["succeeded"] and entry_seat(send["to"], refs) == seat]
    return sent[-1] if sent else text


def owning_agent_seat_task_opened_unless_open(tasks_root, subject, description):
    """Open a task on OWNING_AGENT_SEAT's task list unless one with the subject that is not marked
    completed is there; return the new task's id, or None. Raises OSError."""
    list_directory = tasks_root / f"nedsnodes-{OWNING_AGENT_SEAT}-tasks"
    if list_directory.is_dir():
        for path in list_directory.glob("*.json"):
            try:
                task = json.loads(path.read_text(encoding="utf-8"))
            except ValueError:
                continue
            if (task.get("status") != "completed"  # pragma: no mutate, Claude Code writes pending, in_progress or completed, and both others sort after completed, so > says the same
                    and task.get("subject") == subject):
                return None
    return agent_seat_task_list.agent_seat_task_list_new_pending_task_write(
        list_directory, subject, description)


# --- One invocation ---

class Sweep:
    def __init__(self, log, now, paths, state_directory, timeout_seconds, machine):
        self.log = log
        self.now = now
        self.paths = paths
        self.working_directory = state_directory / HEADLESS_WORKING_DIRECTORY_NAME
        self.timeout_seconds = timeout_seconds
        self.machine = machine
        self.failed = False
        self.read_failures_this_run = set()
        self.started_monotonic = time.monotonic()

    def current(self):
        """The run's time plus the time the run has taken: headless agent-sessions run one after
        another, so a step logged late in a run must not carry the run's start. Whole seconds, so
        that a run that takes none logs the run's time itself."""
        return self.now + timedelta(seconds=int(time.monotonic() - self.started_monotonic))

    def record(self, event):
        return self.log.append(event, self.current(), self.now)

    def alert(self, key, title, text, action, failure=True):
        """Write a user-alert once for each key, and log it."""
        self.failed = self.failed or failure
        if self.log.alerted(key):
            return None
        alert_id = user_alerts.user_alert_write_to_pending(title, text, action, now=self.current())
        self.record({"event": "user_alert", "key": key, "alert_id": alert_id, "title": title})
        print(f"user-alert {alert_id}: {title}", flush=True)
        return alert_id

    def headless_failed(self, seat, purpose, problem, kind, outcome=None):
        """problem is the failure's full text; kind names its cause in words code alone chose, so
        that a cause met at every invocation, such as a usage limit, opens one task. A usage limit
        whose reset time is still ahead opens none: it pauses every headless agent-session, and
        this returns True."""
        self.failed = True
        self.record({"event": "headless_failed", "agent_seat": seat, "purpose": purpose,
                     "problem": problem})
        resets_at = self.usage_limit_reset_time(outcome) if outcome else None
        if resets_at is not None and resets_at > self.now.timestamp():
            self.record({"event": HEADLESS_USAGE_LIMIT_PAUSE, "agent_seat": seat,
                         "resets_at": iso(datetime.fromtimestamp(resets_at, timezone.utc))})
            return True
        self.owning_agent_seat_task(
            f"Idle sweep: a headless agent-session failed: {kind}",
            f"The idle sweep, {PROGRAM_PATH_IN_REPOSITORY}, started a headless agent-session to "
            f"{purpose} for the agent-seat {seat}, and it failed: {problem}\n"
            f"Each such failure is a headless_failed event in the idle sweep's log, {self.log.path}. "
            "Find the cause and fix it; to see whether claude is logged out, run `claude -p` by hand "
            "on ned-box.\n" + OWNING_AGENT_SEAT_TASK_LAST_LINES)
        return False

    def usage_limit_reset_time(self, outcome):
        """The reset time of the last usage-limit record in the headless agent-session's
        transcript, or None when there is none or the transcript cannot be read."""
        if not outcome.session_id:
            return None
        transcript = (verdicts_print.transcript_lookup.project_directory_for_seat(
            self.working_directory, self.paths.projects_root) / f"{outcome.session_id}.jsonl")
        try:
            limits = [record for record in verdicts_print.transcript_records(transcript)
                      if verdicts_print.is_usage_limit(record)]
        except verdicts_print.ReadFailure:
            return None
        return verdicts_print.usage_limit_reset_time(limits[-1]) if limits else None

    def headless_usage_limit_pause_holds(self):
        pause = self.log.headless_usage_limit_pause()
        return pause is not None and self.now < parse_time(pause["resets_at"])

    def entry_not_found(self, seat, purpose, session_id):
        """No running agent-session has the id seat's handoff-supervisor launched last, so no
        sender is started: the agent-seat's entry cannot be told from any other."""
        self.failed = True
        state_path = verdicts_print.supervisor.supervisor_state_path(self.paths.handoff_directory,
                                                                     seat)
        self.record({"event": "agent_seat_entry_not_found", "agent_seat": seat, "purpose": purpose,
                     "session_id": session_id})
        self.alert(f"entry-not-found:{seat}:{session_id}:{self.now.date()}",
                   f"The idle sweep found no running agent-session of {seat}",
                   f"The idle sweep was to {purpose} for the agent-seat {seat}, but no running "
                   f"agent-session in ~/{SESSION_RECORDS_DIRECTORY_UNDER_HOME} has the session id "
                   f"{session_id}, which its handoff-supervisor launched last, so nothing was sent.",
                   f"An agent on ned-box can check whether {seat}'s claude is running, and compare "
                   f"the sessionId in its ~/{SESSION_RECORDS_DIRECTORY_UNDER_HOME}/<pid>.json with "
                   f"launched_session_id in {state_path}.")

    def sent_texts_differ(self, outcome, refs, text, step):
        """Log each text a sender sent in place of code's, and give OWNING_AGENT_SEAT a task to
        find why: the difference is this program's defect, with nothing for the user to do."""
        differing = sent_texts_other_than_code_wrote(outcome, refs, text)
        for seat, sent_text in differing:
            self.record({"event": "sent_text_differs_from_code_text", "agent_seat": seat, "step": step,
                         "text": text, "sent_text": sent_text})
        if not differing:
            return
        self.owning_agent_seat_task(
            SENT_TEXT_DIFFERS_TASK_SUBJECT,
            f"A headless agent-session the idle sweep, {PROGRAM_PATH_IN_REPOSITORY}, started to send "
            "a message sent a text other than the one code wrote. Each time is a "
            "sent_text_differs_from_code_text event in the "
            f"idle sweep's log, {self.log.path}, with the text code wrote and the text sent.\n"
            "Compare the two, find why the sender changed the text, such as a sender prompt "
            "that lets it, and fix the cause in a pull request.\n"
            "Mark this task completed when the fix is merged; the idle sweep opens a new task "
            "at the next difference.")

    def owning_agent_seat_task(self, subject, description):
        """Open a task on OWNING_AGENT_SEAT's task list unless one with the subject is open, and
        log it; write a user-alert when the task cannot be written, the only other route."""
        try:
            task_id = owning_agent_seat_task_opened_unless_open(self.paths.tasks_root, subject,
                                                                description)
        except OSError as error:
            failure = f"{type(error).__name__}: {error}"
            self.alert(f"owner-task-not-written:{subject}:{failure}:{self.now.date()}",
                       f"The idle sweep could not give {OWNING_AGENT_SEAT} a task",
                       f"The idle sweep could not write the task \"{subject}\" on "
                       f"{OWNING_AGENT_SEAT}'s task list: {failure}. The task says:\n\n{description}",
                       "An agent on ned-box can fix what the error names, such as the task list "
                       f"directory of {OWNING_AGENT_SEAT} not existing, and give {OWNING_AGENT_SEAT} "
                       "the task.")
            return
        if task_id is not None:
            self.record({"event": "owning_agent_seat_task_opened", "agent_seat": OWNING_AGENT_SEAT,
                         "task_id": task_id, "subject": subject})

    def send_wake_message(self, refs, text):
        """The one way a message reaches an agent-seat: end the text with DO_NOT_REPLY_SENTENCE and
        have one headless agent-session send it to the entry of each agent-seat in refs,
        {agent-seat: ref}. Returns the text as sent, the headless outcome and the time the send
        started."""
        text = f"{text}\n\n{DO_NOT_REPLY_SENTENCE}"
        if len(refs) == 1:
            (seat, ref), = refs.items()
            prompt = SENDER_PROMPT.format(seat=seat, text=text,
                                          find_the_entry=FIND_THE_ENTRY.format(seat=seat, ref=ref),
                                          keep_the_last_sentence=KEEP_THE_LAST_SENTENCE)
        else:
            prompt = NOTICE_SENDER_PROMPT.format(
                seats=", ".join(f"{seat} [{ref}]" for seat, ref in refs.items()), text=text,
                find_the_entry=FIND_THE_ENTRY.format(seat="<agent-seat>", ref="<its ref>"),
                keep_the_last_sentence=KEEP_THE_LAST_SENTENCE)
        started_at = self.current()
        outcome = run_headless(prompt, SEND_ANSWER_SCHEMA, SENDING_TOOLS, self.working_directory,
                               self.timeout_seconds)
        return text, outcome, started_at

    def send(self, seat, verdict, text, step):
        """Send code's text to one agent-seat; log the send for the delivery check. Returns the
        message_sent event, or False when the send failed."""
        ref = list_agents_tool_entry_ref_of_running_agent_session_id(verdict.get(fields.SESSION_ID))
        if ref is None:
            self.entry_not_found(seat, f"send its {step} message", verdict.get(fields.SESSION_ID))
            return False
        refs = {seat: ref}
        text, outcome, started_at = self.send_wake_message(refs, text)
        if outcome.error:
            self.headless_failed(seat, f"send its {step} message", outcome.error,
                                 outcome.error_kind, outcome)
            return False
        self.sent_texts_differ(outcome, refs, text, step)
        problems = send_problems(outcome, refs)
        if problems:
            self.headless_failed(seat, f"send its {step} message", "; ".join(problems), SENDS_WRONG)
            return False
        return self.message_sent(seat, verdict, text_sent_to(outcome, refs, seat, text), step,
                                 started_at)

    def message_sent(self, seat, verdict, text, step, started_at):
        # The delivery check compares transcript times with the send's start: a sender may run on
        # for minutes after its SendMessage, and the record is written when it ends.
        return self.record({"event": "message_sent", "agent_seat": seat, "step": step, "text": text,
                            "send_started_at": iso(started_at), "message_id": uuid.uuid4().hex,
                            "session_id": verdict.get(fields.SESSION_ID),
                            "transcript_path": verdict.get(fields.TRANSCRIPT_PATH)})

    # --- The account ---

    def account_change(self, verdicts):
        try:
            account = verdicts_print.logged_in_account(self.paths.claude_json)
        except verdicts_print.ReadFailure as error:
            self.read_failure("the account check", str(error))
            return
        last = self.log.last_account()
        # A missing account, as in the middle of a switch, is not a change.
        if account is None or account == last:
            return
        self.record({"event": "account_seen", "account": account})
        if last is None:
            return
        seats = [seat for seat, verdict in verdicts.items()
                 if verdict.get(fields.SESSION_ID) and not verdict.get(fields.NOT_CHECKED)]
        text = ACCOUNT_NOTICE_TEXT.format(machine=self.machine, time=iso(self.now))
        self.record({"event": "account_notice", "old_account": last, "new_account": account,
                     "agent_seats": seats})
        refs = {}
        for seat in seats:
            ref = list_agents_tool_entry_ref_of_running_agent_session_id(
                verdicts[seat][fields.SESSION_ID])
            if ref is None:
                self.entry_not_found(seat, "send the account-change notice",
                                     verdicts[seat][fields.SESSION_ID])
            else:
                refs[seat] = ref
        if not refs:
            return
        text, outcome, started_at = self.send_wake_message(refs, text)
        if outcome.error:
            self.headless_failed(", ".join(refs), "send the account-change notice", outcome.error,
                                 outcome.error_kind, outcome)
            return
        self.sent_texts_differ(outcome, refs, text, ACCOUNT_NOTICE)
        wrong = [problem for problem in send_problems(outcome, refs)
                 if not problem.startswith("no SendMessage")]
        if wrong:
            self.headless_failed(", ".join(refs), "send the account-change notice", "; ".join(wrong),
                                 SENDS_WRONG)
        # The delivery check looks in the transcript of every agent-seat the notice was for, whether
        # its send succeeded or not.
        for seat in refs:
            self.message_sent(seat, verdicts[seat], text_sent_to(outcome, refs, seat, text),
                              ACCOUNT_NOTICE, started_at)
            limit = verdicts[seat].get(fields.USAGE_LIMIT)
            if verdicts[seat].get(fields.RULE) == 1 and limit:
                self.record({"event": "limit_wake", "agent_seat": seat,
                             "record_uuid": limit["record_uuid"],
                             "why": "the account-change notice is its wake"})

    # --- Delivery ---

    def delivery_checks(self, verdicts):
        for sent in self.log.deliveries_pending():
            if seconds_between(sent["at"], self.now) < DELIVERY_CHECK_AFTER_SECONDS:
                continue
            seat = sent["agent_seat"]
            verdict = verdicts.get(seat, {})
            # A record written before the send's start was logged has only its "at", and stays
            # pending in the log until it is checked.
            send_started_at = sent.get("send_started_at", sent["at"])
            try:
                found = message_in_transcript(Path(sent["transcript_path"]), sent["text"],
                                              parse_time(send_started_at))
            except verdicts_print.ReadFailure as error:
                self.read_failure(seat, str(error))
                continue
            same_session = verdict.get(fields.SESSION_ID) == sent["session_id"]
            if found is None and same_session and verdict.get(fields.TURN_ENDED) is False:
                continue  # the turn running at the send has not ended; it may yet read the message
            self.record({"event": "delivery_checked", "agent_seat": seat,
                         "message_id": sent["message_id"], "found": found is not None,
                         **({"received_at": iso(found)} if found else {})})
            if not found:
                self.failed = True
                self.owning_agent_seat_task(
                    "Idle sweep: a message it sent is missing from the agent-seat's transcript",
                    f"At {sent['at']} the idle sweep sent {seat} its {sent['step'].replace('_', ' ')} "
                    f"message, and its transcript {sent['transcript_path']} does not hold it:\n\n"
                    f"{sent['text']}\n\n"
                    "Each such message is a delivery_checked event with found false in the idle "
                    f"sweep's log, {self.log.path}. Find why, such as the agent-seat having more "
                    "than one ListAgents entry, an offline Remote Control one among them, and fix "
                    "the cause; send each agent-seat its message with SendMessage if it still "
                    "needs it.\n" + OWNING_AGENT_SEAT_TASK_LAST_LINES)

    # --- Read failures ---

    def read_failure(self, seat, text):
        self.read_failures_this_run.add((seat, text))
        first_seen = self.log.read_failure_first_seen(seat, text)
        if first_seen is None:
            self.record({"event": "read_failure", "agent_seat": seat, "error": text})
            return
        if (seconds_between(agent_seat_idle_sweep_invocation_started_at(first_seen), self.now)
                >= READ_FAILURE_ALERT_AFTER_SECONDS):
            # The subject holds the text alone: two readers of one broken file, such as
            # ~/.claude.json, report it in the same words.
            self.failed = True
            self.owning_agent_seat_task(
                f"Idle sweep: cannot read what it needs: {text}",
                f"Since {first_seen['at']} the idle sweep has failed, at every run, to read: "
                f"{text}\nUntil it can, the idle sweep skips {seat}. Open the file the failure names, "
                "find why it cannot be read, and fix the cause.\n"
                + OWNING_AGENT_SEAT_TASK_LAST_LINES)

    def read_failures_end(self):
        """A failure this invocation did not meet again has ended, so that one coming back later
        is dated from its return."""
        for seat, text in sorted(self.log.read_failures_open() - self.read_failures_this_run):  # pragma: no mutate, read_failure records each failure it adds to read_failures_this_run as open unless it already is, and only this method ends one, so read_failures_this_run is a subset of the open failures and ^ gives what - gives
            self.record({"event": "read_failure_ended", "agent_seat": seat, "error": text})

    # --- One idle agent-seat ---

    def handle_seat(self, seat, verdict, transcript_read_at):
        # Checked before each step that starts a headless agent-session: a judge or send earlier in
        # this invocation, for this agent-seat too, may have started the pause. During it, only the
        # steps that start none run; the others are not logged, so they run after it.
        session = verdict[fields.SESSION_ID]
        stretch = (verdict.get(fields.LAST_ACTIVITY) or {}).get("time")
        wait = self.log.open_wait(seat)
        if wait and wait["session_id"] != session:
            self.end_wait(seat, "a new agent-session")
            wait = None
        check = self.log.last_check(seat)
        check_is_new = not (check and check["session_id"] == session
                            and check["last_activity"] == stretch)
        rule, text = verdict[fields.RULE], verdict.get(fields.TEXT)
        if rule == 1:
            if self.headless_usage_limit_pause_holds():
                return
            self.checked(seat, verdict, transcript_read_at, check_is_new)
            if wait:
                self.end_wait(seat, "a usage limit")
            self.usage_limit(seat, verdict)
            return
        # A tool call does not settle a promise a rule 2 message named, as rule 4 below does not.
        worked_at = verdict.get(fields.LAST_TOOL_CALL_AT)
        if (wait and PROMISE not in wait and worked_at
                and parse_time(worked_at) > parse_time(wait[NUDGE])):
            self.end_wait(seat, "it made a tool call after the nudge")
            wait = None
        if wait and wait[PROMISE_MESSAGES]:
            # A failed message's sentences must be backed too, so that a call backing an earlier
            # promise does not end the wait before the escalation and the user-alert report them.
            messages = sorted(wait[PROMISE_MESSAGES] + wait[FAILED_PROMISE_MESSAGES],
                              key=lambda message: parse_time(message["at"]))
            settling_calls = task_calls_settling_promise_messages(
                messages,
                verdict.get(
                    fields.SUCCESSFUL_TASK_TOOL_CALLS_SETTING_PREREQUISITES_OR_BLOCKED_BY) or [])
            if settling_calls is not None:
                self.end_wait(seat, "it recorded what a task waits on after the promise message",
                              sentences=[sentence for message in messages
                                         for sentence in message["sentences"]],
                              task_calls=settling_calls)
                wait = None
        if wait and TELL_USER in wait and stretch and parse_time(stretch) > parse_time(wait[TELL_USER]):
            self.end_wait(seat, "it spent tokens after the user was told")
            wait = None
        promise_text = None
        judged_sentences = rule == 2
        sentences_checked = []
        if judged_sentences and self.headless_usage_limit_pause_holds():
            if wait:
                self.due_step(seat, verdict, wait)
            return
        if judged_sentences:
            outcome, promise, sentences_checked = self.sentences(seat, verdict)
            if outcome == "paused":
                # The check is not logged, so that the next read after the reset still holds the
                # sentences the judge could not judge.
                return
            promise_text, promise_kinds, promise_records = promise or (None, None, ())
            fallback = verdict.get(fields.IF_EVERY_SENTENCE_BACKED)
            if outcome == "all backed" and fallback is not None:
                rule, text = fallback[fields.RULE], fallback.get(fields.TEXT)
            elif not promise_text:
                rule = None
        if not judged_sentences:
            self.checked(seat, verdict, transcript_read_at, check_is_new)
        # Nothing to do settles the open tasks a rule 3 or 5 message was about, but not a promise
        # a rule 2 message named, whatever message opened the wait it was sent on.
        if rule == 4 and wait and PROMISE not in wait:
            self.end_wait(seat, "nothing to do")
            wait = None
        if wait:
            self.due_step(seat, verdict, wait)
        paused = self.headless_usage_limit_pause_holds()
        # An escalation stopped at a usage limit can start the pause after the sentences were
        # judged. When it holds back their promise message, the unbacked sentences and the check
        # are not logged, so that after the reset they are judged again and the message is sent.
        # Every other sentence checked is logged, so that a second judge cannot answer
        # differently about it and add a wrong line to that message.
        if judged_sentences and paused and promise_text:
            unbacked_keys = {(item["record_uuid"], item["sentence"]) for item in promise_records}
            self.sentences_checked(seat, [item for item in sentences_checked
                                          if (item["record_uuid"], item["sentence"]) not in unbacked_keys])
        elif judged_sentences:
            self.sentences_checked(seat, sentences_checked)
            self.checked(seat, verdict, transcript_read_at, check_is_new)
        if paused:
            return
        if promise_text:
            promise_sentences = [item["sentence"] for item in promise_records]
            # A promise given in answer to a message goes on the open wait, so that repeated
            # promises cannot put off its escalation and the user-alert.
            if not wait:
                # Logged before the send: the escalation quotes the nudge that opened the wait, so
                # a promise message whose own send failed still reaches the agent-seat.
                self.start_wait(seat, verdict, stretch, promise_text, 2)
                self.record({"event": PROMISE_MESSAGE, "agent_seat": seat, "kinds": promise_kinds,
                             "sentences": promise_sentences})
                self.send(seat, verdict, promise_text, NUDGE)
            else:
                # The promise step is logged whether or not the send succeeds: its sentences are
                # already logged as checked, so only the wait's escalation and user-alert can
                # still report the promise, and they read a failed message from its own event.
                if PROMISE not in wait:
                    self.record({"event": "wait_step", "agent_seat": seat, "step": PROMISE})
                sent = self.send(seat, verdict, promise_text, NUDGE)
                if sent:
                    self.record({"event": PROMISE_MESSAGE, "agent_seat": seat,
                                 "kinds": promise_kinds, "sentences": promise_sentences,
                                 "send_started_at": sent["send_started_at"]})
                else:
                    self.record({"event": PROMISE_MESSAGE_SEND_FAILED, "agent_seat": seat,
                                 "kinds": promise_kinds, "sentences": promise_sentences,
                                 "text": promise_text})
        elif not wait:
            self.nudge(seat, verdict, rule, text, stretch)

    def end_wait(self, seat, why, **details):
        self.record({"event": "wait_ended", "agent_seat": seat, "why": why, **details})

    def start_wait(self, seat, verdict, stretch, step_text, rule):
        self.record({"event": "wait_step", "agent_seat": seat, "step": NUDGE, "rule": rule,
                     "session_id": verdict[fields.SESSION_ID], "first_idle_at": stretch,
                     "text": step_text})

    def due_step(self, seat, verdict, wait):
        """The step of an open wait that is due: the escalation 15 minutes after the nudge, then
        the user-alert 15 minutes after the escalation; after that, none. The escalation is a
        send, so a headless usage-limit pause holds it."""
        if TELL_USER in wait:
            return
        minutes = int(seconds_between(wait["first_idle_at"] or wait[NUDGE], self.now) // 60)
        failed = wait[FAILED_PROMISE_MESSAGES]
        if ESCALATE in wait:
            if seconds_between(wait[ESCALATE], self.now) >= WAIT_STEP_SECONDS:
                self.record({"event": "wait_step", "agent_seat": seat, "step": TELL_USER})
                self.alert(f"tell-user:{seat}:{wait[NUDGE]}",
                           f"{seat} has been idle {minutes} minutes after a nudge and an escalation",
                           f"The idle sweep found {seat} idle with something to do, messaged it "
                           f"at {wait[NUDGE]} and escalated at {wait[ESCALATE]}, and it is idle "
                           f"again. Its transcript is {verdict[fields.TRANSCRIPT_PATH]}. The idle "
                           "sweep sends it nothing more until it spends tokens and goes idle again."
                           + "".join(f" At {message['at']} the idle sweep failed to send it a "
                                     "message naming these sentences of its own, which only the "
                                     "escalation quoted: "
                                     + " ".join(f'"{sentence}"' for sentence in message["sentences"])
                                     for message in failed),
                           f"An agent on ned-box can read {seat}'s transcript and its tmux session "
                           f"{seat} to see why it stopped, and message it with SendMessage; the "
                           "user may want to look at it himself.", failure=False)
            return
        if (seconds_between(wait[NUDGE], self.now) >= WAIT_STEP_SECONDS
                and not self.headless_usage_limit_pause_holds()):
            text = ESCALATION_TEXT.format(
                minutes=minutes, nudge_time=parse_time(wait[NUDGE]).strftime("%Y-%m-%d %H:%MZ"),
                quoted_nudge=quoted(wait["nudge_text"])) + "".join(
                    FAILED_PROMISE_ESCALATION_TEXT.format(
                        time=parse_time(message["at"]).strftime("%Y-%m-%d %H:%MZ"),
                        quoted_text=quoted(message["text"]))
                    for message in failed)
            self.record({"event": "wait_step", "agent_seat": seat, "step": ESCALATE, "text": text})
            self.send(seat, verdict, text, ESCALATE)

    def nudge(self, seat, verdict, rule, text, stretch):
        if rule == 3:
            subject = f"handoff put off: {text}"
            if subject in self.reminded_subjects(seat, verdict):
                if verdict.get(fields.OPEN_TASKS_NOTHING_HOLDS):
                    self.judge_idle_seat(seat, {**verdict, fields.HANDOFF_DEFERRED_MARKER: None},
                                         stretch)
                return
            self.start_wait(seat, verdict, stretch, text, 3)
            self.reminder_sent(seat, verdict, self.send(seat, verdict, text, NUDGE), [subject])
        elif rule == 5:
            self.judge_idle_seat(seat, verdict, stretch)

    def reminded_subjects(self, seat, verdict):
        last_held_at = {}
        holds = [(call["time"], call["task"]) for call in verdict.get(
            fields.SUCCESSFUL_TASK_TOOL_CALLS_SETTING_PREREQUISITES_OR_BLOCKED_BY) or []]
        holds += [(call["time"], task) for call in verdict.get(
            fields.IDLE_SWEEP_VERDICT_FIELD_LISTING_SUCCESSFUL_TASK_UPDATE_TOOL_CALLS_SETTING_ADD_BLOCKS_WITH_BLOCKED_TASKS) or []
            for task in call["blocked_tasks"]]
        for time, task in holds:
            moment = parse_time(time)
            if moment:
                subject = open_task_subject(task)
                last_held_at[subject] = max(moment, last_held_at.get(subject, moment))
        return self.log.reminded_subjects(seat, verdict[fields.SESSION_ID],
                                          verdict.get(fields.LAST_USER_TYPED_AT), last_held_at)

    def reminder_sent(self, seat, verdict, sent, subjects):
        if sent:
            self.record({"event": REMINDER_SENT, "agent_seat": seat,
                         "session_id": verdict[fields.SESSION_ID], "subjects": subjects,
                         "message_id": sent["message_id"],
                         "send_started_at": sent["send_started_at"]})

    def facts(self, seat, verdict):
        running = verdict.get(fields.RUNNING) or {}
        def with_minutes(items):
            own = fields.SUBAGENT_OWN_RUNNING_BACKGROUND_COMMANDS
            return [{**item, "minutes_running": int(seconds_between(item["started"], self.now) // 60)
                     if item.get("started") else None,
                     **({own: with_minutes(item[own])} if own in item else {})} for item in items]
        last_message = dict(verdict.get(fields.LAST_TURN_ENDING_MESSAGE) or {})
        if last_message.get("text"):
            last_message["text"] = last_message["text"][-JUDGED_TEXT_CHARACTERS:]
        return {"agent_seat": seat, "tmux_session": seat, "now": iso(self.now),
                "last_token_spent_at": (verdict.get(fields.LAST_ACTIVITY) or {}).get("time"),
                "last_turn_ending_message": last_message or None,
                "open_tasks_nothing_holds": verdict.get(fields.OPEN_TASKS_NOTHING_HOLDS),
                "handoff_deferral_marker_file": verdict.get(fields.HANDOFF_DEFERRED_MARKER),
                "approval_walk_items_waiting_on_the_user":
                    verdict.get(fields.APPROVAL_WALK_ITEMS_WAITING_ON_THE_USER),
                "running_subagents": with_minutes(running.get("subagents", [])),
                "running_background_commands": with_minutes(running.get("background_commands", [])),
                "running_workflows": with_minutes(running.get("workflows", []))}

    def running_work_to_ask_about(self, facts, asked_about):
        """The facts less the running work not to ask the agent-seat about: each background
        command whose own timeout has not yet ended it, since it ends by itself; each command,
        subagent and workflow a rule 5 message has already asked about, since the sweep asks once
        about each; and each stopped subagent left with no other command."""
        own = fields.SUBAGENT_OWN_RUNNING_BACKGROUND_COMMANDS
        ends_at = fields.BACKGROUND_COMMAND_TIMEOUT_ENDS_AT

        def to_ask_about(commands):
            return [command for command in commands if command["id"] not in asked_about
                    and not (command.get(ends_at) and parse_time(command[ends_at]) > self.now)]
        subagents = []
        for entry in facts["running_subagents"]:
            if own in entry:
                entry = {**entry, own: to_ask_about(entry[own])}
                if not entry[own]:
                    continue
            elif entry["id"] in asked_about:
                continue
            subagents.append(entry)
        return {**facts, "running_subagents": subagents,
                "running_background_commands": to_ask_about(facts["running_background_commands"]),
                "running_workflows": [workflow for workflow in facts["running_workflows"]
                                      if workflow["id"] not in asked_about]}

    def judge_idle_seat(self, seat, verdict, stretch):
        answer = self.log.last_judge_answer(seat)
        if (answer and answer["session_id"] == verdict[fields.SESSION_ID]
                and answer["last_activity"] == stretch
                and seconds_between(agent_seat_idle_sweep_invocation_started_at(answer), self.now)
                < JUDGE_ASK_AGAIN_SECONDS):
            return
        all_facts = self.facts(seat, verdict)
        facts = dict(self.running_work_to_ask_about(all_facts, self.log.running_work_asked_about(seat)),
                     step=NUDGE)
        running_keys = ("running_subagents", "running_background_commands", "running_workflows")
        if any(all_facts[key] for key in running_keys) and not any(facts[key] for key in running_keys):
            return
        reminded = self.reminded_subjects(seat, verdict)
        open_tasks = all_facts["open_tasks_nothing_holds"] or []
        facts["open_tasks_nothing_holds"] = [task for task in open_tasks
                                             if open_task_subject(task["id"]) not in reminded]
        if open_tasks and not facts["open_tasks_nothing_holds"] and not any(
                facts[key] for key in running_keys):
            return
        idle_minutes = int(seconds_between(stretch, self.now) // 60) if stretch else None
        prompt = IDLE_JUDGE_PROMPT.format(seat=seat, idle_minutes=idle_minutes,
                                          facts=json.dumps(facts, indent=1, ensure_ascii=False))
        outcome = run_headless(prompt, IDLE_JUDGE_ANSWER_SCHEMA, "", self.working_directory,
                               self.timeout_seconds)
        problem = outcome.error or idle_judge_answer_problem(
            outcome.answer, [task["id"] for task in facts["open_tasks_nothing_holds"] or []])
        answer = outcome.answer or {}
        send = not problem and answer["send"]
        sent = False
        if send:
            raised = [task for task in facts["open_tasks_nothing_holds"]
                      if task["id"] in answer[OPEN_TASK_IDS_RAISED]]
            message = answer["message"] + open_tasks_raised_listing(raised)
            self.start_wait(seat, verdict, stretch, message, 5)
            sent = self.send(seat, verdict, message, NUDGE)
            # The listing, not the judge's own words, says which tasks the message covers, and a
            # task the sender left out of the text sent was never reminded of.
            self.reminder_sent(seat, verdict, sent, [
                open_task_subject(task["id"]) for task in raised
                if sent and open_task_listed_in(sent["text"], task["id"])])
        # Work counts as asked about only once a message reached the agent-seat: a failed send
        # leaves it for a later sweep to hand to the judge again.
        self.record({"event": "judge_answer", "agent_seat": seat, "rule": 5,
                     "session_id": verdict[fields.SESSION_ID], "last_activity": stretch,
                     "send": send, "reason": answer.get("reason"), "failed": bool(problem),
                     RUNNING_WORK_ASKED_ABOUT: running_work_named_in(facts, answer["message"])
                     if sent else [], **({"message_id": sent["message_id"]} if sent else {})})
        if problem:
            self.headless_failed(seat, "judge whether it could act now", problem,
                                 outcome.error_kind or JUDGE_ANSWER_UNUSABLE, outcome)

    def checked(self, seat, verdict, transcript_read_at, check_is_new):
        """Log the check, which moves where the next read of the agent-seat's transcript starts."""
        if check_is_new:
            self.record({"event": "checked", "agent_seat": seat, "session_id": verdict[fields.SESSION_ID],
                         "transcript_read_at": iso(transcript_read_at),
                         "last_activity": (verdict.get(fields.LAST_ACTIVITY) or {}).get("time"),
                         "rule": verdict[fields.RULE], "decision": verdict.get(fields.DECISION)})

    def sentences(self, seat, verdict):
        """Rule 2: judge what code could not settle, and word one message naming every unbacked
        sentence. Returns ("unbacked", (the message, the sorted kinds of the sentences it names,
        their records), the sentences checked), ("failed", None, []), ("paused", None, []) or
        ("all backed", None, the sentences checked). The caller logs the sentences checked, except,
        when a pause a later launch starts holds back the promise message, the unbacked ones, which
        are judged again after the reset; a judge stopped by the pause logs none, and a failed judge
        logs them all."""
        checked = self.log.checked_sentences(seat)
        new_by_code_reading = fields.verdict_sentences_grouped_by_code_reading(
            item for item in verdict.get(fields.SENTENCES, [])
            if (item["record_uuid"], item["sentence"]) not in checked)
        judged = new_by_code_reading.get(fields.JUDGE, [])
        unbacked = new_by_code_reading.get(fields.UNBACKED, [])
        new = judged + unbacked
        if not new:
            return "all backed", None, []
        backed = {}
        if judged:
            facts = dict(self.facts(seat, verdict),
                         sentences=[{"index": index, "time": item["time"], "kind": item["kind"],
                                     "sentence": item["sentence"]}
                                    for index, item in enumerate(judged)],
                         tool_calls_since_start_of_earliest_turn_with_sentence_to_judge=verdict.get(
                             fields.TOOL_CALLS_SINCE_START_OF_EARLIEST_TURN_WITH_SENTENCE_TO_JUDGE, []),
                         open_tasks_with_prerequisites_or_blocked_by=verdict.get(
                             fields.OPEN_TASKS_WITH_PREREQUISITES_OR_BLOCKED_BY, []))
            prompt = SENTENCES_JUDGE_PROMPT.format(
                seat=seat, facts=json.dumps(facts, indent=1, ensure_ascii=False))
            outcome = run_headless(prompt, SENTENCES_ANSWER_SCHEMA, "", self.working_directory,
                                   self.timeout_seconds)
            problem = outcome.error or sentence_answer_problem(outcome.answer, len(judged))
            if problem and self.headless_failed(seat, "judge whether its promises are backed",
                                                problem, outcome.error_kind or JUDGE_ANSWER_UNUSABLE,
                                                outcome):
                return "paused", None, []
            if problem:
                self.sentences_checked(seat, new)
                return "failed", None, []
            for answer in outcome.answer["sentences"]:
                backed[answer["index"]] = answer["backed"]
            self.record({"event": "judge_answer", "agent_seat": seat, "rule": 2,
                         "answers": outcome.answer["sentences"]})
        unbacked += [item for index, item in enumerate(judged) if not backed[index]]
        if not unbacked:
            return "all backed", None, new
        return "unbacked", ("\n".join(UNBACKED_SENTENCE_LINES[item["kind"]].format(
            sentence=item["sentence"],
            minutes=int(seconds_between(item["time"], self.now) // 60) if item["time"] else "some")
            for item in unbacked), sorted({item["kind"] for item in unbacked}), unbacked), new

    def sentences_checked(self, seat, items):
        for item in items:
            self.record({"event": "sentence_checked", "agent_seat": seat,
                         "record_uuid": item["record_uuid"], "sentence": item["sentence"]})

    def usage_limit(self, seat, verdict):
        limit = verdict[fields.USAGE_LIMIT]
        record_uuid, account_now = limit["record_uuid"], limit["account_now_logged_in"]
        account, seen = self.log.limit_account(seat, record_uuid)
        if not seen or (account is None and account_now):
            self.record({"event": "limit_seen", "agent_seat": seat, "record_uuid": record_uuid,
                         "account": account_now})
            account = account or account_now
        if record_uuid in self.log.limit_wakes(seat):
            return
        if limit["reset_time_passed"]:
            why = LIMIT_ENDED_BY_RESET
        elif account and account_now and account_now != account:
            why = LIMIT_ENDED_BY_ACCOUNT.format(machine=self.machine)
        else:
            return
        text = LIMIT_WAKE_TEXT.format(why=why)
        self.record({"event": "limit_wake", "agent_seat": seat, "record_uuid": record_uuid,
                     "why": why})
        self.send(seat, verdict, text, LIMIT_WAKE)


def sentence_answer_problem(answer, count):
    indexes = sorted(item.get("index") for item in (answer or {}).get("sentences", [])
                     if isinstance(item, dict))
    if indexes != list(range(count)) or not all(
            isinstance(item.get("backed"), bool) for item in answer["sentences"]):
        return f"the judge's answer does not give backed true or false once for each of {count} " \
               f"sentences: {json.dumps(answer)[:500]}"
    return None


def running_work_named_in(facts, message):
    """The ids of the running work handed to the judge that its message names: the prompt asks it
    to name each by id, and one it left out is asked about at the next rule 5 nudge instead of
    never."""
    own = fields.SUBAGENT_OWN_RUNNING_BACKGROUND_COMMANDS
    ids = [command["id"] for entry in facts["running_subagents"] for command in entry.get(own, [])]
    ids += [entry["id"] for entry in facts["running_subagents"] if own not in entry]
    ids += [entry["id"] for key in ("running_background_commands", "running_workflows")
            for entry in facts[key]]
    return sorted(work_id for work_id in set(ids) if work_id in message)


def open_task_subject(task_id):
    return f"open task: {task_id}"


def open_tasks_raised_listing(tasks):
    """The sentence code adds to a rule 5 message naming every open task the judge raised, or ""."""
    if not tasks:
        return ""
    return " Open tasks nothing holds: " + "; ".join(
        f'#{task["id"]} "{task.get("subject") or ""}"' for task in tasks) + "."


def open_task_listed_in(text, task_id):
    return re.search(rf"(?<![\w#])#{re.escape(task_id)}(?![\w])", text) is not None


def idle_judge_answer_problem(answer, open_task_ids):
    if not isinstance(answer.get("send"), bool) or not isinstance(answer.get("message"), str) or (
            answer["send"] and not answer["message"].strip()):
        return f"the judge's answer does not give send true or false, with a message when true: " \
               f"{json.dumps(answer)[:500]}"
    raised = answer.get(OPEN_TASK_IDS_RAISED)
    if not isinstance(raised, list) or any(task_id not in open_task_ids for task_id in raised):
        return f"the judge's answer does not list, in {OPEN_TASK_IDS_RAISED}, only ids of the " \
               f"open tasks it was given, {open_task_ids}: {json.dumps(answer)[:500]}"
    return None


def message_received(record):
    """Whether the record is one by which the agent-seat's model received a message: a user turn,
    or a message queued into a running turn. Claude Code's queue-operation record is written when
    a message is queued, before the model has it, and the message is lost if the agent-session
    ends first."""
    attachment = record.get("attachment")
    return record.get("type") == "user" or (
        record.get("type") == "attachment" and isinstance(attachment, dict)
        and attachment.get("type") == "queued_command")


def message_in_transcript(path, text, sent_at):
    """The time of the first record by which the agent-seat received a message, written at or after
    the send, that holds the text, compared with all runs of whitespace made one space; or None."""
    needle = " ".join(text.split())
    for record in verdicts_print.transcript_records(path):
        if not message_received(record):
            continue
        moment = parse_time(record.get("timestamp"))
        if moment is None or (sent_at - moment).total_seconds() > DELIVERY_CLOCK_SLACK_SECONDS:
            continue
        if any(needle in " ".join(value.split()) for value in strings_in(record)):
            return moment
    return None


def strings_in(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from strings_in(item)
    elif isinstance(value, list):
        for item in value:
            yield from strings_in(item)


# --- The program ---

def sweep(arguments, now):
    paths = verdicts_print.Paths(arguments)
    log = SweepLog(Path(arguments.log_file).expanduser())
    machine = arguments.machine_name or socket.gethostname()
    run = Sweep(log, now, paths, Path(arguments.state_directory).expanduser(),
                arguments.headless_timeout_seconds, machine)
    seats = verdicts_print.agent_seats(paths.handoff_directory)
    checker = verdicts_print.due_task_hook.GitHubConditionChecker({}, now.timestamp())
    parser = verdicts_print.walk_finder.markdown_parser()
    verdicts, read_times = {}, {}
    for seat in seats:
        check = log.last_check(seat)
        skipped = {record_uuid for record_uuid, woken_at in log.limit_wakes(seat).items()
                   if seconds_between(woken_at, now) >= LIMIT_WAKE_GRACE_SECONDS}
        # Sentences only from the turns that ended since the last check of the same agent-session;
        # a new agent-session is read again with its last turn-ending message only. Since the read,
        # not the record: judge calls for other agent-seats run between the two, and a turn that
        # ends then must be read next time.
        since = parse_time(check["transcript_read_at"]) if check else None
        read_times[seat] = run.current()
        verdict = verdicts_print.verdict_for_seat(seat, paths, now, since, checker, parser, skipped)
        budget_skips = list(verdict.get(fields.GITHUB_CONDITIONS_SKIPPED_FOR_BUDGET, []))
        if since and verdict.get(fields.SESSION_ID) not in (None, check["session_id"]):
            verdict = verdicts_print.verdict_for_seat(seat, paths, now, None, checker, parser,
                                                      skipped)
            # The reread decides the wake, but the first read's skips happened too.
            budget_skips += [condition for condition
                             in verdict.get(fields.GITHUB_CONDITIONS_SKIPPED_FOR_BUDGET, [])
                             if condition not in budget_skips]
        verdicts[seat] = verdict
        if budget_skips:
            run.record({"event": fields.GITHUB_CONDITIONS_SKIPPED_FOR_BUDGET, "agent_seat": seat,
                        "conditions": budget_skips})
    run.account_change(verdicts)
    run.delivery_checks(verdicts)
    for seat, verdict in verdicts.items():
        for error in verdict.get(fields.ERRORS, []):
            run.read_failure(seat, error)
        if verdict.get(fields.ERRORS) or not verdict.get(fields.IDLE) or verdict.get(fields.RULE) is None:
            continue
        run.handle_seat(seat, verdict, read_times[seat])
    run.read_failures_end()
    return 1 if run.failed else 0


def run_failure_report(state_directory, tasks_root, error_text):
    """A task on OWNING_AGENT_SEAT's task list for a failure of a whole invocation, which may be
    the log itself; when the task cannot be written, one user-alert for each distinct failure,
    recorded in the state directory."""
    try:
        owning_agent_seat_task_opened_unless_open(
            tasks_root, f"Idle sweep: an invocation failed: {error_text}",
            f"The idle sweep, {PROGRAM_PATH_IN_REPOSITORY}, failed: {error_text}\nThe traceback is "
            "in the cron output log ~/.claude/agent-seat-idle-sweep-headless-judge-wake-messages-"
            "send-and-user-alerts-write.log on ned-box; until the cause is fixed, no idle agent-seat "
            "is woken. Find the cause and fix it.\n" + OWNING_AGENT_SEAT_TASK_LAST_LINES)
        return
    except OSError as error:
        task_error = f"{type(error).__name__}: {error}"
    alerted_file = state_directory / RUN_FAILURES_ALERTED_FILE_NAME
    alerted = alerted_file.read_text(encoding="utf-8").splitlines() if alerted_file.exists() else []
    if error_text in alerted:
        return
    user_alerts.user_alert_write_to_pending(
        "The idle sweep failed", f"The idle sweep, {Path(__file__).name}, failed: {error_text}. "
        f"It could not give {OWNING_AGENT_SEAT} a task about it: {task_error}",
        "An agent on ned-box can read the traceback in the cron output log "
        "~/.claude/agent-seat-idle-sweep-headless-judge-wake-messages-send-and-user-alerts-write.log "
        "and fix the cause; until then no idle agent-seat is woken.")
    with alerted_file.open("a", encoding="utf-8") as stream:
        stream.write(error_text + "\n")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--now", default=None, help="ISO time to act at, for tests")
    parser.add_argument("--log-file", default=str(LOG_FILE))
    parser.add_argument("--state-directory", default=str(STATE_DIRECTORY))
    parser.add_argument("--headless-timeout-seconds", type=float, default=HEADLESS_TIMEOUT_SECONDS)
    parser.add_argument("--machine-name", default=None, help="the machine named in messages")
    parser.add_argument("--handoff-directory", default="~/.claude/handoffs")
    parser.add_argument("--agents-root", default="~/agents")
    parser.add_argument("--projects-root", default="~/.claude/projects")
    parser.add_argument("--tasks-root", default="~/.claude/tasks")
    parser.add_argument("--claude-json", default="~/.claude.json")
    parser.add_argument("--due-task-raise-state-directory",
                        default=str(Path("~") / verdicts_print.due_task_hook.STATE_DIRECTORY_UNDER_HOME))
    arguments = parser.parse_args(argv)
    now = parse_time(arguments.now) if arguments.now else datetime.now(timezone.utc)
    if now is None:
        parser.error("--now is not an ISO time")
    state_directory = Path(arguments.state_directory).expanduser()
    state_directory.mkdir(parents=True, exist_ok=True)
    with (state_directory / "run.lock").open("w") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print(f"{iso(now)} an earlier invocation is still running; this one does nothing",
                  flush=True)
            return 0
        try:
            return sweep(arguments, now)
        except Exception as error:
            run_failure_report(state_directory, Path(arguments.tasks_root).expanduser(),
                               f"{type(error).__name__}: {error}")
            raise


if __name__ == "__main__":
    sys.exit(main())
