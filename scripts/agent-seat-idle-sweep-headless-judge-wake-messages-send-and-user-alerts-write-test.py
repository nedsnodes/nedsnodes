#!/usr/bin/env python3
"""Cases for scripts/agent-seat-idle-sweep-headless-judge-wake-messages-send-and-user-alerts-write.py.

Every case runs the program as a subprocess against folders this suite made, never the real ones:
a handoff directory, agents, projects and tasks roots, a ~/.claude.json, a log file, a state
directory and HOME, under which user-alerts are written. `claude` is a fake placed first on PATH:
it answers each call with the next scripted answer, as stream-json, and records the call's
arguments and prompt. `gh` is never reached: the one case that gives a task prerequisites runs the
program through GITHUB_BUDGET_SPENT_RUNNER, which starts the GitHub budget spent. Each invocation
fixes the time with --now.
"""

import atexit
import fcntl
import hashlib
import json
import os
import re
import shutil
import site
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

PROGRAM = Path(__file__).with_name(
    "agent-seat-idle-sweep-headless-judge-wake-messages-send-and-user-alerts-write.py")
START = datetime(2026, 11, 2, 12, 0, tzinfo=timezone.utc)
LONG_AGO = "2026-11-02T11:50:00Z"

FAKE_CLAUDE = r'''#!{python}
import json, os, sys, time
prompt = sys.stdin.read()
calls_path = os.environ["FAKE_CLAUDE_CALLS"]
calls = open(calls_path).read().splitlines() if os.path.exists(calls_path) else []
with open(calls_path, "a") as stream:
    stream.write(json.dumps({{"argv": sys.argv[1:], "prompt": prompt}}) + "\n")
answers = json.load(open(os.environ["FAKE_CLAUDE_ANSWERS"]))
answer = answers[len(calls)] if len(calls) < len(answers) else {{"exit": 3}}
if answer.get("child"):
    import subprocess
    subprocess.Popen(["sleep", str(answer["child"])])
if answer.get("overwrite"):
    with open(answer["overwrite"][0], "w") as stream:
        stream.write(answer["overwrite"][1])
time.sleep(answer.get("sleep", 0))
def emit(event):
    print(json.dumps(event), flush=True)
if "session_id" in answer:
    emit({{"type": "system", "session_id": answer["session_id"]}})
if "transcript" in answer:
    import re
    project = os.path.join(os.environ["FAKE_CLAUDE_PROJECTS"],
                           re.sub(r"[^a-zA-Z0-9]", "-", os.path.realpath(os.getcwd())))
    os.makedirs(project, exist_ok=True)
    with open(os.path.join(project, answer["session_id"] + ".jsonl"), "w") as stream:
        stream.write(answer["transcript"])
text = prompt.split("----------\n", 1)[-1].rsplit("\n----------", 1)[0]
for number, send in enumerate(answer.get("sends", [])):
    message = {{"@prompt-text": text, "@prompt-text-without-last-paragraph": text.rsplit("\n\n", 1)[0]
               }}.get(send.get("message"), send.get("message", ""))
    emit({{"type": "assistant", "message": {{"content": [
        {{"type": "tool_use", "id": f"t{{number}}", "name": "SendMessage",
         "input": {{"to": send["to"], "message": message}}}}]}}}})
    emit({{"type": "user", "message": {{"content": [
        {{"type": "tool_result", "tool_use_id": f"t{{number}}", "content": "sent",
         "is_error": send.get("is_error", False)}}]}}}})
sys.stderr.write(answer.get("stderr", ""))
sys.stderr.flush()
if answer.get("garbage"):
    print(answer.get("garbage") if isinstance(answer["garbage"], str) else "not json")
if answer.get("garbage_then_result") or not answer.get("garbage"):
    if "result" in answer:
        emit(dict({{"type": "result"}}, **answer["result"]))
    elif "answer" in answer:
        emit({{"type": "result", "subtype": "success", "is_error": False,
              "structured_output": answer["answer"]}})
if answer.get("signal"):
    import signal
    os.kill(os.getpid(), signal.SIGTERM)
sys.exit(answer.get("exit", 0))
'''
# Long texts of distinct characters, so a cut one character off shows in an exact comparison.
LONG_TEXT = "".join(f"{number:05d}" for number in range(400))

failures = []
SUITE_ROOT = Path(tempfile.mkdtemp(prefix="agent-seat-idle-sweep-slice-2-test-"))
# atexit, so that a case that raises or a sys.exit still leaves no files in /tmp.
atexit.register(shutil.rmtree, SUITE_ROOT, ignore_errors=True)


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


def at(minutes):
    return (START + timedelta(minutes=minutes)).isoformat().replace("+00:00", "Z")


def assistant(text=None, when=LONG_AGO, tool=None, uuid=None, tool_id="t"):
    content = []
    if text is not None:
        content.append({"type": "text", "text": text})
    if tool is not None:
        content.append({"type": "tool_use", "id": tool_id, "name": tool[0], "input": tool[1]})
    return {"type": "assistant", "timestamp": when, "uuid": uuid or f"u-{when}-{text}",
            "message": {"model": "claude-opus-5-5", "content": content,
                        "usage": {"input_tokens": 100, "output_tokens": 100}}}


def user(text, when=LONG_AGO):
    return {"type": "user", "timestamp": when, "message": {"role": "user", "content": text}}


def task_result(tool_id, text, when=LONG_AGO):
    """A task call's result as Claude Code writes it, with no is_error: a success text such as
    "Task #1 created successfully: <subject>", or "Task not found"."""
    return {"type": "user", "timestamp": when, "message": {"role": "user", "content": [
        {"type": "tool_result", "tool_use_id": tool_id, "content": text}]}}


def turn_end(when=LONG_AGO):
    return {"type": "system", "subtype": "turn_duration", "timestamp": when}


def cross_session(text, when):
    return {**user("Another Claude session sent a message:\n<cross-session-message from=\"x\" "
                   f"from-name=\"agent-seat-idle-sweep-1f\">\n{text}\n</cross-session-message>", when),
            "origin": {"kind": "peer", "from": "uds:/tmp/x.sock"}}


def usage_limit(resets_at, when=LONG_AGO):
    return {"type": "assistant", "timestamp": when, "uuid": "limit-record",
            "apiError": "usage_limit_reached", "quotaLimits": {"resetsAt": resets_at},
            "message": {"model": "<synthetic>", "content": [
                {"type": "text", "text": "You've hit your session limit"}],
                "usage": {"input_tokens": 0, "output_tokens": 0}}}


DONE_TURN = [user("go"), assistant("Done."), turn_end()]
OWNER_TASKS = "nedsnodes-reboot-test-tasks"
DELIVERY_TASK_SUBJECT = "Idle sweep: a message it sent is missing from the agent-seat's transcript"


def socket_path(seat):
    """The messaging socket path Machine.seat records for an agent-seat's agent-session."""
    return f"/run/user/1000/cc-socks/{seat}.sock"


def listed_ref(path):
    """The [ref] ListAgents gives the agent-session whose messaging socket is at path."""
    return hashlib.sha256(f"session:{path}".encode()).hexdigest()[:6]


def send_to(seat, message="@prompt-text", **extra):
    return dict({"to": f"{seat} [{listed_ref(socket_path(seat))}]", "message": message}, **extra)


def sent_ok(seat="alpha"):
    return {"sends": [send_to(seat)], "answer": {"sent": True, "reason": "sent"}}


# Runs the program in a process whose GitHubConditionChecker reads 0 when it starts its budget and a
# time past the budget at every later read, so no prerequisite is asked of gh.
GITHUB_BUDGET_SPENT_RUNNER = r'''
import importlib.util, sys
spec = importlib.util.spec_from_file_location("sweep", sys.argv[1])
sweep = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sweep)
due_task_hook = sweep.verdicts_print.due_task_hook
readings = iter([0])
due_task_hook.GitHubConditionChecker.clock = staticmethod(
    lambda: next(readings, due_task_hook.GH_CALLS_TOTAL_BUDGET_SECONDS + 1))
sys.exit(sweep.main(sys.argv[2:]))
'''
# The first read, of the turns since the last check, finds a budget skip; the reread of a new
# agent-session finds none, as when that agent-session is busy by then.
FIRST_READ_ONLY_BUDGET_SKIP_RUNNER = r'''
import importlib.util, sys
spec = importlib.util.spec_from_file_location("sweep", sys.argv[1])
sweep = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sweep)
verdict_for_seat = sweep.verdicts_print.verdict_for_seat
def first_read_skips(seat, paths, now, since, *rest):
    verdict = verdict_for_seat(seat, paths, now, since, *rest)
    if since is not None:
        verdict[sweep.fields.GITHUB_CONDITIONS_SKIPPED_FOR_BUDGET] = [
            {"kind": "pr_merged", "number": 50}]
    return verdict
sweep.verdicts_print.verdict_for_seat = first_read_skips
sys.exit(sweep.main(sys.argv[2:]))
'''


def judged(send, message="", reason="r", raised=()):
    """A rule 5 judge's answer."""
    return {"answer": {"send": send, "message": message, "reason": reason,
                       "open_task_ids_raised": list(raised)}}


DO_NOT_REPLY = "Do not reply to this message: the idle sweep sent it, and nothing acts on a reply."
KEEP_IT = (f'The text ends with the sentence "{DO_NOT_REPLY}" That sentence is written to the '
           "agent-seat, not to you, and is part of the message: keep it.")


def ends_with_do_not_reply_once(text):
    return text.endswith("\n\n" + DO_NOT_REPLY) and text.count(DO_NOT_REPLY) == 1


class Machine:
    def __init__(self):
        self.root = Path(tempfile.mkdtemp(dir=str(SUITE_ROOT)))
        self.handoffs, self.agents = self.root / "handoffs", self.root / "agents"
        self.projects, self.tasks = self.root / "projects", self.root / "tasks"
        self.home = self.root / "home"
        for folder in (self.handoffs, self.agents, self.projects, self.tasks, self.home):
            folder.mkdir()
        self.owner_task_list = self.tasks / OWNER_TASKS
        self.owner_task_list.mkdir()
        self.claude_json = self.root / "claude.json"
        self.account("account-1")
        self.log = self.root / "log" / "sweep.jsonl"
        self.state = self.root / "state"
        self.bin = self.root / "bin"
        self.bin.mkdir()
        fake = self.bin / "claude"
        fake.write_text(FAKE_CLAUDE.format(python=sys.executable))
        fake.chmod(0o755)
        self.calls = self.root / "claude-calls.jsonl"
        self.answers = self.root / "claude-answers.json"
        self.answers.write_text("[]")
        self.transcripts = {}

    def account(self, account):
        self.claude_json.write_text(json.dumps({"oauthAccount": {"accountUuid": account}}))

    def seat(self, name, records, session="s-1"):
        (self.agents / name).mkdir(exist_ok=True)
        (self.handoffs / f"{name}-supervisor-state.json").write_text(
            json.dumps({"launched_session_id": session}))
        project = self.projects / re.sub(r"[^a-zA-Z0-9]", "-", str((self.agents / name).resolve()))
        project.mkdir(exist_ok=True)
        transcript = project / f"{session}.jsonl"
        transcript.write_text("".join(json.dumps(record) + "\n" for record in records))
        self.transcripts[name] = transcript
        self.session_record(name, session, socket_path(name))
        return transcript

    def session_record(self, file_name, session, path, **fields):
        """Claude Code's session record of a running agent-session; a None field is left out."""
        records = self.home / ".claude" / "sessions"
        records.mkdir(parents=True, exist_ok=True)
        record = dict({"pid": 1, "sessionId": session, "kind": "interactive",
                       "messagingSocketPath": path}, **fields)
        (records / f"{file_name}.json").write_text(json.dumps(
            {key: value for key, value in record.items() if value is not None}))

    def append(self, name, *records):
        with self.transcripts[name].open("a") as stream:
            for record in records:
                stream.write(json.dumps(record) + "\n")

    def task(self, seat, task_id):
        directory = self.tasks / f"nedsnodes-{seat}-tasks"
        directory.mkdir(exist_ok=True)
        (directory / f"{task_id}.json").write_text(json.dumps(
            {"id": task_id, "subject": f"task {task_id}", "status": "pending", "blocks": [],
             "blockedBy": []}))

    def handoff_put_off(self, session="s-1"):
        (self.handoffs / f"{session}-handoff-deferred").write_text("")

    def script(self, *answers):
        self.answers.write_text(json.dumps(list(answers)))
        if self.calls.exists():
            self.calls.unlink()

    def claude_calls(self):
        return ([json.loads(line) for line in self.calls.read_text().splitlines()]
                if self.calls.exists() else [])

    def events(self, kind=None):
        if not self.log.exists():
            return []
        events = [json.loads(line) for line in self.log.read_text().splitlines() if line.strip()]
        return [event for event in events if kind is None or event["event"] == kind]

    def owner_tasks(self):
        """The tasks on the owning agent-seat's task list, past any file that is not JSON."""
        tasks = []
        for path in sorted(self.owner_task_list.glob("*.json")) if self.owner_task_list.is_dir() else []:
            try:
                tasks.append(json.loads(path.read_text()))
            except ValueError:
                pass
        return tasks

    def owner_task_subjects(self):
        return [task["subject"] for task in self.owner_tasks()]

    def alerts(self):
        pending = self.home / ".local" / "state" / "nedsnodes" / "user-alerts" / "pending"
        return ([json.loads(path.read_text()) for path in sorted(pending.glob("*.json"))]
                if pending.is_dir() else [])

    def run(self, minutes, *extra, path_has_fake=True, github_budget_spent=False, runner_source=None):
        environment = dict(os.environ)
        environment["HOME"] = str(self.home)
        # Python finds the user's site-packages from HOME, and on the Mac markdown-it-py is installed there.
        environment["PYTHONUSERBASE"] = site.getuserbase()
        if path_has_fake:
            environment["PATH"] = f"{self.bin}{os.pathsep}{environment['PATH']}"
        else:
            environment["PATH"] = os.pathsep.join(
                part for part in environment["PATH"].split(os.pathsep)
                if not (Path(part) / "claude").exists())
        environment["FAKE_CLAUDE_CALLS"] = str(self.calls)
        environment["FAKE_CLAUDE_ANSWERS"] = str(self.answers)
        environment["FAKE_CLAUDE_PROJECTS"] = str(self.projects)
        if github_budget_spent:
            runner_source = GITHUB_BUDGET_SPENT_RUNNER
        runner = ["-c", runner_source] if runner_source else []
        completed = subprocess.run(
            [sys.executable, *runner, str(PROGRAM), "--now", at(minutes), "--handoff-directory",
             str(self.handoffs), "--agents-root", str(self.agents), "--projects-root",
             str(self.projects), "--tasks-root", str(self.tasks), "--claude-json",
             str(self.claude_json), "--due-task-raise-state-directory",
             str(self.root / "due-task-raise-state"), "--log-file", str(self.log), "--state-directory",
             str(self.state), "--machine-name", "ned-box", *extra],
            capture_output=True, text=True, env=environment, check=False)
        return completed.returncode, completed.stdout + completed.stderr


HANDOFF_TEXT_START = "Your handoff was put off at"

# --- rule 3: the nudge, the delivery check, the escalation and telling the user --------------
machine = Machine()
machine.seat("alpha", DONE_TURN)
machine.handoff_put_off()
machine.script(sent_ok())
code, output = machine.run(0)
calls = machine.claude_calls()
check("rule 3: exit 0, one headless agent-session", code == 0 and len(calls) == 1, (code, output))
argv = calls[0]["argv"] if calls else []
check("rule 3: the sender runs on Sonnet, allowed only SendMessage, ListAgents and ToolSearch",
      argv[argv.index("--model") + 1] == "sonnet"
      and argv[argv.index("--tools") + 1] == "SendMessage,ListAgents,ToolSearch"
      and argv[argv.index("--allowedTools") + 1] == "SendMessage,ListAgents,ToolSearch", argv)
check("rule 3: the sender is handed code's handoff text and the ref of the agent-seat's entry",
      calls and HANDOFF_TEXT_START in calls[0]["prompt"]
      and f"whose ref is [{listed_ref(socket_path('alpha'))}]" in calls[0]["prompt"], calls)
sent = machine.events("message_sent")
check("rule 3: the send is logged as the nudge, with the text code wrote",
      len(sent) == 1 and sent[0]["step"] == "nudge" and sent[0]["text"].startswith(HANDOFF_TEXT_START),
      sent)
check("rule 3: a wait starts, counted from the last token spent",
      [(event["step"], event.get("first_idle_at")) for event in machine.events("wait_step")]
      == [("nudge", LONG_AGO)], machine.events("wait_step"))
machine.script()
code, _ = machine.run(0.5)
check("a run inside the delivery check's minute and the wait's 15 minutes does nothing",
      code == 0 and not machine.claude_calls() and not machine.events("delivery_checked"),
      machine.events())
code, _ = machine.run(2)
check("the message missing from the transcript of an idle agent-seat: a task for reboot-test, no "
      "user-alert, exit 1",
      code == 1 and [event["found"] for event in machine.events("delivery_checked")] == [False]
      and not machine.alerts() and machine.owner_task_subjects() == [DELIVERY_TASK_SUBJECT]
      and "sent alpha its nudge message" in machine.owner_tasks()[0]["description"],
      (machine.events("delivery_checked"), machine.alerts(), machine.owner_tasks()))
machine.script(sent_ok())
code, _ = machine.run(16)
calls = machine.claude_calls()
nudge_text = machine.events("wait_step")[0]["text"]
expected = ("You've given this 26 minutes, please check; if not sure, hand off. At 2026-11-02 "
            "12:00Z the idle sweep wrote this, which you have not acted on:\n\n"
            + "\n".join("> " + line for line in nudge_text.split("\n")) + "\n\n" + DO_NOT_REPLY)
check("idle again 15 minutes after the nudge: the escalation with the minutes since it went idle, "
      "quoting the nudge without its do-not-reply sentence",
      len(calls) == 1 and machine.events("message_sent")[-1]["text"] == expected
      and expected in calls[0]["prompt"] and DO_NOT_REPLY not in nudge_text,
      (calls, machine.events("message_sent")))
# The agent-seat reads the escalation and answers it, and the delivery check finds it.
escalation = machine.events("message_sent")[-1]["text"]
machine.append("alpha", cross_session(escalation, at(16.2)), assistant("Still waiting.", at(16.3)),
               turn_end(at(16.4)))
machine.script()
code, _ = machine.run(18)
check("the message found in the agent-seat's transcript: no user-alert, no second task",
      [event["found"] for event in machine.events("delivery_checked")] == [False, True]
      and not machine.alerts() and len(machine.owner_tasks()) == 1, machine.events("delivery_checked"))
code, _ = machine.run(31.5)
check("idle again 15 minutes after the escalation: the user is told, and no message is sent",
      not machine.claude_calls() and len(machine.alerts()) == 1
      and "after a nudge and an escalation" in machine.alerts()[0]["title"], machine.alerts())
check("a text-only reply keeps the wait, and the user-alert counts the minutes from when the "
      "agent-seat first went idle, not from the reply",
      len(machine.alerts()) == 1 and machine.alerts()[0]["title"].startswith(
          "alpha has been idle 41 minutes after"), machine.alerts())
code, _ = machine.run(40)
check("after telling the user, nothing more while the agent-seat spends no tokens",
      not machine.claude_calls() and len(machine.alerts()) == 1, machine.alerts())
machine.append("alpha", user("more", at(41)), assistant("Back to it.", at(41.5)), turn_end(at(42)))
machine.script(sent_ok())
code, _ = machine.run(48)
check("spending tokens after the user was told starts the steps over, with a new nudge",
      len(machine.claude_calls()) == 1 and [event["step"] for event in machine.events("wait_step")]
      == ["nudge", "escalate", "tell_user", "nudge"]
      and machine.events("wait_ended")[-1]["why"] == "it spent tokens after the user was told",
      machine.events("wait_step"))

# --- a tool call after the nudge ends the wait ---------------------------------------------------
machine = Machine()
machine.seat("alpha", [user("go"), assistant(tool=("Bash", {"command": "ls"})), turn_end()])
machine.handoff_put_off()
machine.script(sent_ok())
machine.run(0)
machine.script()
machine.run(16)
check("a tool call made before the nudge does not end the wait: the escalation is sent",
      [event["step"] for event in machine.events("wait_step")] == ["nudge", "escalate"],
      machine.events("wait_step"))
machine = Machine()
machine.seat("alpha", DONE_TURN)
machine.handoff_put_off()
machine.script(sent_ok())
machine.run(0)
nudge = machine.events("message_sent")[-1]["text"]
machine.append("alpha", cross_session(nudge, at(0.2)),
               {**user("Carry on.", at(0.5)), "origin": {"kind": "human"}},
               assistant(tool=("Bash", {"command": "make"}), when=at(1)),
               assistant("Built it.", at(9)), turn_end(at(9.5)))
machine.script(sent_ok())
code, _ = machine.run(16)
check("a tool call after the nudge ends the wait: no escalation, and after the user has typed the "
      "next idle stretch gets a new nudge counted from its own start",
      code == 0 and [event["why"] for event in machine.events("wait_ended")]
      == ["it made a tool call after the nudge"]
      and [(event["step"], event.get("first_idle_at")) for event in machine.events("wait_step")]
      == [("nudge", LONG_AGO), ("nudge", at(9))]
      and not any(event["step"] == "escalate" for event in machine.events("message_sent")),
      (machine.events("wait_step"), machine.events("wait_ended")))

# --- rule 4 ends a wait; a new agent-session ends one too -------------------------------------
machine = Machine()
machine.seat("alpha", DONE_TURN)
machine.handoff_put_off()
machine.script(sent_ok())
machine.run(0)
(machine.handoffs / "s-1-handoff-deferred").unlink()
machine.script()
machine.run(20)
check("rule 4 ends the wait: nothing to do, no escalation",
      not machine.claude_calls() and machine.events("wait_ended")[-1]["why"] == "nothing to do",
      machine.events())
machine = Machine()
machine.seat("alpha", DONE_TURN)
machine.handoff_put_off()
machine.script(sent_ok())
machine.run(0)
machine.seat("alpha", DONE_TURN, session="s-2")
machine.handoff_put_off("s-2")
machine.script(sent_ok())
machine.run(20)
check("a new agent-session ends the wait and starts a new nudge, not the escalation",
      machine.events("wait_ended")[-1]["why"] == "a new agent-session"
      and machine.events("wait_step")[-1]["step"] == "nudge"
      and machine.events("wait_step")[-1]["session_id"] == "s-2", machine.events("wait_step"))

# --- rule 5: the judge decides whether to send --------------------------------------------------
machine = Machine()
machine.seat("alpha", DONE_TURN)
machine.task("alpha", "1")
# The judge takes over a second, as under load, so its answer is logged after the invocation's time.
machine.script(dict(judged(False, reason="a subagent started 3 minutes ago is still running"),
                    sleep=1.2))
code, _ = machine.run(0)
calls = machine.claude_calls()
check("rule 5: the judge is handed the open task and the agent-seat's last message, and no tool",
      len(calls) == 1 and '"task 1"' in calls[0]["prompt"] and '"Done."' in calls[0]["prompt"]
      and calls[0]["argv"][calls[0]["argv"].index("--tools") + 1] == ""
      and "--allowedTools" not in calls[0]["argv"], calls)
check("rule 5: a verdict not to send is logged with its reason, and no wait starts",
      [(event["send"], event["reason"]) for event in machine.events("judge_answer")]
      == [(False, "a subagent started 3 minutes ago is still running")]
      and not machine.events("wait_step"), machine.events())
LONG_DONE_TEXT = f"Done. {LONG_TEXT * 3} Done."
machine = Machine()
machine.seat("alpha", [user("go"), assistant(LONG_DONE_TEXT), turn_end()])
machine.task("alpha", "1")
machine.script(judged(False, reason="it is waiting"))
machine.run(0)
calls = machine.claude_calls()
check("rule 5: a last message longer than the judge is handed reaches it as its end only, as the "
      "design says",
      len(calls) == 1 and json.dumps(LONG_DONE_TEXT[-4000:])[1:-1] in calls[0]["prompt"]
      and "[...]" not in calls[0]["prompt"], calls)
walk_item_machine = Machine()
walk_item_machine.seat("alpha", DONE_TURN)
walk_item_machine.task("alpha", "1")
walk = walk_item_machine.agents / "alpha" / "docs" / "walk"
walk.mkdir(parents=True)
(walk / "w-minutes.md").write_text("#next_to_present item 2 of 3\n")
walk_item_machine.script(judged(False, reason="it is answering the user"))
walk_item_machine.run(0)
calls = walk_item_machine.claude_calls()
check("rule 5 with a walk item waiting: the judge is still asked, and is handed the walk item",
      len(calls) == 1 and '"task 1"' in calls[0]["prompt"]
      and '"approval_walk_items_waiting_on_the_user"' in calls[0]["prompt"]
      and '"item 2 of 3"' in calls[0]["prompt"], calls)
machine.script()
machine.run(10)
check("rule 5: not asked again within 15 minutes while the agent-seat spends no tokens",
      not machine.claude_calls(), machine.claude_calls())
machine.script(judged(True, "What's going on?", "nothing runs"), sent_ok())
machine.run(15)
calls = machine.claude_calls()
check("rule 5: asked again 15 minutes later; the message it wrote starts the wait with its text, "
      "and a sender sends it",
      len(calls) == 2 and "What's going on?" in calls[1]["prompt"]
      and machine.events("message_sent")[-1]["text"] == "What's going on?\n\n" + DO_NOT_REPLY
      and machine.events("wait_step")[-1]["step"] == "nudge"
      and machine.events("wait_step")[-1]["text"] == "What's going on?", machine.events())
machine = Machine()
machine.seat("alpha", DONE_TURN)
machine.task("alpha", "1")
machine.script(judged(False, reason="busy"))
machine.run(0)
machine.append("alpha", user("go on", at(1)), assistant("Done again.", at(2)), turn_end(at(2)))
machine.script(judged(False, reason="busy"))
machine.run(8)
check("rule 5: asked again when the agent-seat spent tokens and went idle again",
      len(machine.claude_calls()) == 1, machine.events())

machine = Machine()
transcript = machine.seat("alpha", [
    user("go"),
    dict(user("", when=at(-60)), toolUseResult={"status": "async_launched", "agentId": "a1b2"}),
    user("<task-notification>\n<task-id>a1b2</task-id>\n<status>completed</status>\n<note>the "
         "result below may be interim.</note>\n<result>Fix-round pushed.</result>\n"
         "</task-notification>", when=at(-40)),
    assistant("Waiting on the subagent."), turn_end()])
(transcript.with_suffix("") / "subagents").mkdir(parents=True)
(transcript.with_suffix("") / "subagents" / "agent-a1b2.jsonl").write_text("".join(
    json.dumps(record) + "\n" for record in [
        dict(user("", when=at(-50)), toolUseResult={"backgroundTaskId": "b3c4"}),
        assistant("Fix-round pushed.", when=at(-41))]))
machine.script(judged(False, reason="its test-suite run may be needed"))
machine.run(0)
calls = machine.claude_calls()
prompt = calls[0]["prompt"] if calls else "\n{}"
judge_facts = json.loads(prompt[prompt.rindex("\n{") + 1:])
check("rule 5: a subagent stopped with a background command of its own still running is handed "
      "to the judge with its stop time, and that command with its minutes",
      judge_facts.get("running_subagents") == [{
          "id": "a1b2", "started": at(-60), "minutes_running": 60, "stopped_at": at(-40),
          "own_running_background_commands": [
              {"id": "b3c4", "started": at(-50), "minutes_running": 50, "description": None,
               "timeout_ends_at": None}]}], calls)

machine = Machine()
machine.seat("alpha", [
    user("go"),
    dict(user("", when=at(-30)), toolUseResult={
        "status": "async_launched", "taskId": "wn6fctb8y", "taskType": "local_workflow"}),
    assistant("Waiting on the workflow."), turn_end()])
machine.script(judged(False, reason="the workflow is still running"))
machine.run(0)
calls = machine.claude_calls()
prompt = calls[0]["prompt"] if calls else "\n{}"
judge_facts = json.loads(prompt[prompt.rindex("\n{") + 1:])
check("rule 5: a running Workflow-tool run is handed to the judge with its minutes",
      judge_facts.get("running_workflows") == [
          {"id": "wn6fctb8y", "started": at(-30), "minutes_running": 30}], calls)


def background_bash_launch(task_id, command, when, tool_id, description=None):
    """The Bash call that starts a background command, and its result naming the command's id."""
    tool_input = {"command": command, "run_in_background": True}
    if description is not None:
        tool_input["description"] = description
    return [assistant(tool=("Bash", tool_input), when=when, tool_id=tool_id),
            dict(task_result(tool_id, f"Command running in background with ID: {task_id}", when),
                 toolUseResult={"backgroundTaskId": task_id})]


def rule_five_judge_facts(machine):
    calls = machine.claude_calls()
    prompt = calls[0]["prompt"] if calls else "\n{}"
    return calls, json.loads(prompt[prompt.rindex("\n{") + 1:])


machine = Machine()
machine.seat("alpha", [
    user("go"),
    *background_bash_launch("bk1", "python3 scripts/surviving-mutants-check.py", at(-29), "tb1",
                            description="Check which recorded surviving mutants current main kills"),
    *background_bash_launch("bk2", "python3 scripts/x-test.py", at(-20), "tb2"),
    assistant("Waiting on the checks."), turn_end()])
machine.script(judged(False, reason="the checks are still running"))
machine.run(0)
calls, judge_facts = rule_five_judge_facts(machine)
check("rule 5: a background command with no timeout is handed to the judge by its description, and "
      "one whose Bash call gave no description by its command line",
      judge_facts.get("running_background_commands") == [
          {"id": "bk1", "started": at(-29), "minutes_running": 29,
           "description": "Check which recorded surviving mutants current main kills",
           "timeout_ends_at": None},
          {"id": "bk2", "started": at(-20), "minutes_running": 20,
           "description": "python3 scripts/x-test.py", "timeout_ends_at": None}], calls)

machine = Machine()
machine.seat("alpha", [
    user("go"),
    *background_bash_launch("bk1", "timeout 30m python3 scripts/x-test.py", at(-10), "tb1",
                            description="Run the x test suite"),
    assistant("Waiting on the test suite."), turn_end()])
machine.script(judged(True, message="m"))
machine.run(0)
check("rule 5: a background command whose own `timeout 30m` has not ended it is work under way, and "
      "with nothing else running the judge is not asked and nothing is sent",
      machine.claude_calls() == [] and machine.events("judge_answer") == [], machine.events())
machine.run(20)
calls, judge_facts = rule_five_judge_facts(machine)
check("rule 5: once the command's own timeout has passed, the judge is asked about it",
      [entry["id"] for entry in judge_facts.get("running_background_commands", [])] == ["bk1"],
      calls)

machine = Machine()
machine.seat("alpha", [
    user("go"),
    *background_bash_launch("bk1", "timeout -k 5 1h python3 scripts/x-test.py", at(-10), "tb1",
                            description="Run the x test suite"),
    dict(user("", when=at(-5)), toolUseResult={"status": "async_launched", "agentId": "a1b2"}),
    assistant("Waiting."), turn_end()])
machine.script(judged(False, reason="a subagent is running"))
machine.run(0)
calls, judge_facts = rule_five_judge_facts(machine)
check("rule 5: beside a running subagent, a background command its own timeout has not ended is "
      "not handed to the judge",
      judge_facts.get("running_background_commands") == []
      and [entry["id"] for entry in judge_facts.get("running_subagents", [])] == ["a1b2"], calls)

machine = Machine()
transcript = machine.seat("alpha", [
    user("go"),
    dict(user("", when=at(-60)), toolUseResult={"status": "async_launched", "agentId": "a1b2"}),
    user("<task-notification>\n<task-id>a1b2</task-id>\n<status>completed</status>\n<note>the "
         "result below may be interim.</note>\n<result>Started the check.</result>\n"
         "</task-notification>", when=at(-40)),
    assistant("Waiting on the subagent."), turn_end()])
(transcript.with_suffix("") / "subagents").mkdir(parents=True)
(transcript.with_suffix("") / "subagents" / "agent-a1b2.jsonl").write_text("".join(
    json.dumps(record) + "\n" for record in [
        *background_bash_launch("b3c4", "timeout 2h python3 scripts/surviving-mutants-check.py",
                                at(-50), "tb1"),
        assistant("Started the check.", when=at(-41))]))
machine.script(judged(True, message="m"))
machine.run(0)
check("rule 5: a stopped subagent whose only running command is inside that command's own timeout "
      "is work under way, and the judge is not asked",
      machine.claude_calls() == [], machine.events())


def answered_with_a_tool_call_and_idle_again(machine, minutes, received=True):
    """The agent-seat receives the last message sent, if any and unless received is False, answers
    it with a tool call, which ends the wait, and its turn ends."""
    sent = machine.events("message_sent")
    if received and sent:
        machine.append("alpha", cross_session(sent[-1]["text"], at(minutes - 0.5)))
    machine.append("alpha", assistant(tool=("Read", {"file_path": "x"}), when=at(minutes)),
                   assistant("Still waiting.", when=at(minutes)), turn_end(at(minutes)))


def ids_handed_to_judge(judge_facts):
    return sorted(entry["id"] for key in ("running_background_commands", "running_subagents",
                                          "running_workflows")
                  for entry in judge_facts.get(key, []))


ASKED_ABOUT_ALL = ("Your background command \"Check the mutants\" (bk1) started 29 minutes ago, your "
                   "subagent a1b2 started 20 minutes ago and your workflow wn6fctb8y started 10 "
                   "minutes ago. Are they taking longer than expected?")
machine = Machine()
machine.seat("alpha", [
    user("go"),
    *background_bash_launch("bk1", "python3 scripts/mutants.py", at(-29), "tb1",
                            description="Check the mutants"),
    dict(user("", when=at(-20)), toolUseResult={"status": "async_launched", "agentId": "a1b2"}),
    dict(user("", when=at(-10)), toolUseResult={
        "status": "async_launched", "taskId": "wn6fctb8y", "taskType": "local_workflow"}),
    assistant("Waiting."), turn_end()])
machine.script(judged(True, ASKED_ABOUT_ALL), sent_ok())
machine.run(0)
check("rule 5: a message that asks about running work logs the ids it names",
      [event.get("running_work_asked_about") for event in machine.events("judge_answer")]
      == [["a1b2", "bk1", "wn6fctb8y"]] and len(machine.events("message_sent")) == 1,
      machine.events())
answered_with_a_tool_call_and_idle_again(machine, 1)
machine.script(judged(True, "m"), sent_ok())
machine.run(8)
check("rule 5: once a message has asked about everything still running, the next sweep neither asks "
      "the judge nor nudges",
      machine.claude_calls() == [] and len(machine.events("judge_answer")) == 1
      and len(machine.events("message_sent")) == 1, machine.events())
machine.append("alpha", *background_bash_launch("bk2", "python3 scripts/x-test.py", at(9), "tb2",
                                                description="Run the x test suite"),
               assistant("Waiting.", when=at(9)), turn_end(at(9)))
machine.script(judged(True, "Your background command \"Run the x test suite\" (bk2) started 7 "
                            "minutes ago. Is it taking longer than expected?"), sent_ok())
machine.run(16)
calls, judge_facts = rule_five_judge_facts(machine)
check("rule 5: a command started after the others were asked about is handed to the judge alone",
      ids_handed_to_judge(judge_facts) == ["bk2"]
      and machine.events("judge_answer")[-1]["running_work_asked_about"] == ["bk2"], calls)

machine = Machine()
machine.seat("alpha", [
    user("go"),
    *background_bash_launch("bk1", "python3 scripts/a.py", at(-30), "tb1", description="A"),
    assistant("Waiting."), turn_end()])
machine.log.parent.mkdir(parents=True)
machine.log.write_text(json.dumps({
    "at": at(-20), "event": "judge_answer", "agent_seat": "alpha", "rule": 5, "session_id": "s-1",
    "last_activity": at(-25), "send": True, "reason": "r", "failed": False}) + "\n")
machine.script(judged(False, reason="r"))
code, output = machine.run(0)
calls, judge_facts = rule_five_judge_facts(machine)
check("rule 5: a judge_answer logged before running_work_asked_about was logged asks about nothing",
      code == 0 and ids_handed_to_judge(judge_facts) == ["bk1"], (code, output, calls))

machine = Machine()
machine.seat("alpha", [
    user("go"),
    *background_bash_launch("bk1", "python3 scripts/a.py", at(-30), "tb1", description="A"),
    *background_bash_launch("bk2", "python3 scripts/b.py", at(-30), "tb2", description="B"),
    assistant("Waiting."), turn_end()])
machine.script(judged(True, "Your background command \"A\" (bk1) started 30 minutes ago. Is it "
                            "taking longer than expected?"), sent_ok())
machine.run(0)
answered_with_a_tool_call_and_idle_again(machine, 1)
machine.script(judged(False, reason="r"))
machine.run(8)
calls, judge_facts = rule_five_judge_facts(machine)
check("rule 5: of two running commands, the one the message left out is handed to the judge at the "
      "next sweep, and the one it asked about is not",
      machine.events("judge_answer")[0]["running_work_asked_about"] == ["bk1"]
      and ids_handed_to_judge(judge_facts) == ["bk2"], calls)
check("rule 5: a verdict not to send asks about nothing",
      machine.events("judge_answer")[-1]["running_work_asked_about"] == [], machine.events())
answered_with_a_tool_call_and_idle_again(machine, 9)
machine.script(judged(False, reason="r"))
machine.run(16)
calls, judge_facts = rule_five_judge_facts(machine)
check("rule 5: a command a verdict not to send was handed is handed to the judge again",
      ids_handed_to_judge(judge_facts) == ["bk2"], calls)

machine = Machine()
machine.seat("alpha", [
    user("go"),
    *background_bash_launch("bk1", "python3 scripts/a.py", at(-30), "tb1", description="A"),
    assistant("Waiting."), turn_end()])
machine.script(judged(True, "Your background command \"A\" (bk1) started 30 minutes ago. Is it "
                            "taking longer than expected?"),
               {"sends": [send_to("alpha", is_error=True)], "answer": {"sent": False, "reason": "r"}})
machine.run(0)
check("rule 5: a message whose send failed asks about nothing",
      machine.events("judge_answer")[0]["running_work_asked_about"] == [], machine.events())
answered_with_a_tool_call_and_idle_again(machine, 1)
machine.script(judged(False, reason="r"))
machine.run(8)
calls, judge_facts = rule_five_judge_facts(machine)
check("rule 5: a command named in a message whose send failed is handed to the judge again",
      ids_handed_to_judge(judge_facts) == ["bk1"], calls)

BK1_ASKED = ("Your background command \"A\" (bk1) started 30 minutes ago. Is it taking longer than "
             "expected?")
machine = Machine()
machine.seat("alpha", [
    user("go"),
    *background_bash_launch("bk1", "python3 scripts/a.py", at(-30), "tb1", description="A"),
    assistant("Waiting."), turn_end()])
machine.script(judged(True, BK1_ASKED), {"exit": 1})
machine.run(0)
check("rule 5: a message whose sender exits nonzero asks about nothing",
      [event["running_work_asked_about"] for event in machine.events("judge_answer")] == [[]]
      and any("claude exited 1" in event["problem"] for event in machine.events("headless_failed")),
      machine.events())

# The send succeeded, but to a stale agent-session of the same name, so the transcript the delivery
# check reads never holds the message.
machine = Machine()
machine.seat("alpha", [
    user("go"),
    *background_bash_launch("bk1", "python3 scripts/a.py", at(-30), "tb1", description="A"),
    assistant("Waiting."), turn_end()])
machine.script(judged(True, BK1_ASKED), sent_ok())
machine.run(0)
answered_with_a_tool_call_and_idle_again(machine, 1, received=False)
machine.script(judged(False, reason="r"))
machine.run(8)
calls, judge_facts = rule_five_judge_facts(machine)
check("rule 5: a command named in a message the delivery check did not find is handed to the judge "
      "again", [event["found"] for event in machine.events("delivery_checked")] == [False]
      and ids_handed_to_judge(judge_facts) == ["bk1"], (calls, machine.events()))

machine = Machine()
machine.seat("alpha", [
    user("go"),
    *background_bash_launch("bk1", "python3 scripts/a.py", at(-30), "tb1", description="A"),
    assistant("Waiting."), turn_end()])
machine.script(judged(True, "Your background command \"A\" (bk1) started 30 minutes ago. Is it "
                            "taking longer than expected?"), sent_ok())
machine.run(0)
machine.append("alpha", cross_session(machine.events("message_sent")[-1]["text"], at(0.5)),
               *background_bash_launch("bk2", "timeout 1h python3 scripts/b.py", at(1),
                                                "tb2", description="B"),
               assistant("Waiting.", when=at(1)), turn_end(at(1)))
machine.script(judged(True, "m"), sent_ok())
machine.run(8)
check("rule 5: a command already asked about beside one inside its own timeout: the judge is not "
      "asked", machine.claude_calls() == [] and len(machine.events("judge_answer")) == 1,
      machine.events())

machine = Machine()
transcript = machine.seat("alpha", [
    user("go"),
    dict(user("", when=at(-60)), toolUseResult={"status": "async_launched", "agentId": "a1b2"}),
    user("<task-notification>\n<task-id>a1b2</task-id>\n<status>completed</status>\n<note>the "
         "result below may be interim.</note>\n<result>Started the check.</result>\n"
         "</task-notification>", when=at(-40)),
    assistant("Waiting on the subagent."), turn_end()])
(transcript.with_suffix("") / "subagents").mkdir(parents=True)
(transcript.with_suffix("") / "subagents" / "agent-a1b2.jsonl").write_text("".join(
    json.dumps(record) + "\n" for record in [
        *background_bash_launch("b3c4", "python3 scripts/surviving-mutants-check.py", at(-50),
                                "tb1"),
        assistant("Started the check.", when=at(-41))]))
machine.script(judged(True, "Your subagent a1b2 reported 40 minutes ago. Your subagent's background "
                            "command (b3c4) started 50 minutes ago. Is it still needed?"), sent_ok())
machine.run(0)
answered_with_a_tool_call_and_idle_again(machine, 1)
machine.script(judged(True, "m"), sent_ok())
machine.run(8)
check("rule 5: a stopped subagent whose own running command was asked about is not asked about "
      "again",
      machine.events("judge_answer")[0]["running_work_asked_about"] == ["b3c4"]
      and machine.claude_calls() == [], machine.events())

# --- rule 2: promises and announced actions -------------------------------------------------------
def rechecked(*backed):
    """The rule 2 judge's answer, backed or not for each sentence in order."""
    return {"answer": {"sentences": [{"index": index, "backed": is_backed,
                                      "reason": f"sentence {index} {'backed' if is_backed else 'not backed'}"}
                                     for index, is_backed in enumerate(backed)]}}


PROMISE = "I'll report when PR 927 merges."
machine = Machine()
machine.seat("alpha", [user("go"), assistant(PROMISE), turn_end()])
machine.script(sent_ok())
machine.run(0)
calls = machine.claude_calls()
check("rule 2, an unbacked promise code settles: no judge, one sender with the promise line",
      len(calls) == 1 and 'You promised "I\'ll report when PR 927 merges.". Record it as a task'
      in calls[0]["prompt"], calls)
check("rule 2: the sentence is logged as checked, and the message is the nudge",
      [event["sentence"] for event in machine.events("sentence_checked")] == [PROMISE]
      and machine.events("wait_step")[0]["step"] == "nudge", machine.events())
machine.script()
machine.run(3)
check("rule 2: a sentence is raised once only", not machine.claude_calls(), machine.claude_calls())
check("rule 2: nothing to do does not end the wait a promise message started",
      not machine.events("wait_ended"), machine.events("wait_ended"))
machine.script(rechecked(False), sent_ok())
machine.run(16)
calls = machine.claude_calls()
check("rule 2: still idle 15 minutes after the promise message, the re-check finding the promise "
      "unbacked: the escalation is sent",
      len(calls) == 2 and "please check" in calls[1]["prompt"]
      and [event["step"] for event in machine.events("wait_step")] == ["nudge", "escalate"],
      machine.events("wait_step"))
machine.script()
machine.run(32)
check("rule 2: idle 15 minutes after the escalation: the user is told",
      [event["step"] for event in machine.events("wait_step")] == ["nudge", "escalate", "tell_user"]
      and any("after a nudge and an escalation" in alert["title"] for alert in machine.alerts()),
      (machine.events("wait_step"), machine.alerts()))

SECOND_PROMISE = "I'll fix it after lunch."
machine = Machine()
machine.seat("alpha", [user("go"), assistant(PROMISE), turn_end()])
machine.script(sent_ok())
machine.run(0)
machine.append("alpha", cross_session("You promised", at(0.5)), assistant(SECOND_PROMISE, at(1)),
               turn_end(at(1)))
machine.script(sent_ok())
machine.run(7)
check("rule 2: a promise given in answer to the message is raised on the open wait",
      len(machine.claude_calls()) == 1 and SECOND_PROMISE in machine.claude_calls()[0]["prompt"]
      and [event["step"] for event in machine.events("wait_step")] == ["nudge"]
      and machine.events("wait_step")[0]["at"] == at(0), machine.events("wait_step"))
machine.script(rechecked(False, False), sent_ok())
machine.run(16)
check("rule 2: the second promise did not put off the escalation",
      [event["step"] for event in machine.events("wait_step")] == ["nudge", "escalate"]
      and machine.events("message_sent")[-1]["step"] == "escalate",
      machine.events("wait_step"))

machine = Machine()
machine.seat("alpha", [user("go"), assistant(PROMISE), turn_end()])
machine.script(sent_ok())
machine.run(0)
machine.append("alpha", cross_session("You promised", at(0.5)),
               assistant(tool=("Bash", {"command": "ls"}), when=at(0.8)),
               assistant(SECOND_PROMISE, at(1)), turn_end(at(1)))
machine.script(sent_ok())
machine.run(7)
machine.script(rechecked(False, False), sent_ok())
machine.run(16)
check("rule 2: a tool call and a fresh promise in answer to the message do not end the wait, "
      "and the escalation is sent",
      not machine.events("wait_ended")
      and [event["step"] for event in machine.events("wait_step")] == ["nudge", "escalate"]
      and machine.events("message_sent")[-1]["step"] == "escalate",
      (machine.events("wait_step"), machine.events("wait_ended")))

# A promise sent on a wait a rule 5 or rule 3 message opened keeps that wait going through rule 4.
for opener in ("rule 5", "rule 3"):
    machine = Machine()
    machine.seat("alpha", DONE_TURN)
    if opener == "rule 5":
        machine.task("alpha", "1")
        machine.script(judged(True, "What's going on?", "nothing runs"), sent_ok())
    else:
        machine.handoff_put_off()
        machine.script(sent_ok())
    machine.run(0)
    if opener == "rule 5":
        (machine.tasks / "nedsnodes-alpha-tasks" / "1.json").unlink()
    else:
        (machine.handoffs / "s-1-handoff-deferred").unlink()
    machine.append("alpha", cross_session(machine.events("message_sent")[-1]["text"], at(0.5)),
                   assistant(PROMISE, at(1)), turn_end(at(1)))
    machine.script(sent_ok())
    machine.run(7)
    machine.script()
    machine.run(8)
    check(f"a promise sent on a {opener} wait: nothing to do does not end the wait",
          not machine.events("wait_ended")
          and [event["step"] for event in machine.events("wait_step")] == ["nudge", "promise"],
          machine.events())
    machine.script(rechecked(False), sent_ok())
    machine.run(16)
    machine.script()
    machine.run(32)
    check(f"a promise sent on a {opener} wait: the escalation, then the user is told",
          [event["step"] for event in machine.events("wait_step")]
          == ["nudge", "promise", "escalate", "tell_user"]
          and machine.events("message_sent")[-1]["step"] == "escalate"
          and any("after a nudge and an escalation" in alert["title"] for alert in machine.alerts()),
          (machine.events("wait_step"), machine.alerts()))

def promise_sent_on_rule_five_wait(promise_sender):
    """A machine whose agent-seat answered a rule 5 message with a promise, and whose promise
    message promise_sender sent at minute 7."""
    machine = Machine()
    machine.seat("alpha", DONE_TURN)
    machine.task("alpha", "1")
    machine.script(judged(True, "What's going on?", "nothing runs"), sent_ok())
    machine.run(0)
    (machine.tasks / "nedsnodes-alpha-tasks" / "1.json").unlink()
    machine.append("alpha", cross_session(machine.events("message_sent")[-1]["text"], at(0.5)),
                   assistant(PROMISE, at(1)), turn_end(at(1)))
    machine.script(promise_sender)
    machine.run(7)
    return machine


def failed_send_sentences(machine):
    """The sentences of each failed promise message, read through the records its event names, as
    the program reads them."""
    on_wait = {tuple(record) for event in machine.events("rule_2_sentences_on_wait")
               for record in event["records"]}
    return [[record[1] for record in event.get("records", []) if tuple(record) in on_wait]
            for event in machine.events("promise_message_send_failed")]


PROMISE_SEND_FAILS = {"sends": [send_to("alpha", is_error=True)],
                      "answer": {"sent": False, "reason": "r"}}
machine = promise_sent_on_rule_five_wait(PROMISE_SEND_FAILS)
check("rule 2: a promise message on an open wait whose send failed logs the promise step and the "
      "failed message's sentences, but no promise_message event",
      [event["step"] for event in machine.events("wait_step")] == ["nudge", "promise"]
      and failed_send_sentences(machine) == [[PROMISE]]
      and set(machine.events("promise_message_send_failed")[0]) >= {"records", "text"}
      and "sentences" not in machine.events("promise_message_send_failed")[0]
      and not machine.events("promise_message") and len(machine.events("headless_failed")) == 1,
      machine.events())
machine.script()
machine.run(8)
check("rule 2: after a promise message on an open wait failed to send, nothing to do does not end "
      "the wait, so the dropped promise is not lost unreported",
      not machine.events("wait_ended"), machine.events())
machine.script(rechecked(False), sent_ok())
machine.run(16)
escalation = machine.events("message_sent")[-1]["text"]
check("rule 2: the escalation quotes the promise message whose send on the open wait failed",
      "please check" in escalation and "send failed" in escalation and PROMISE in escalation,
      escalation)
machine.script()
machine.run(32)
check("rule 2: after a promise message on an open wait failed to send, the wait goes on to the "
      "escalation and the user-alert, which names the failed message's sentence",
      [event["step"] for event in machine.events("wait_step")]
      == ["nudge", "promise", "escalate", "tell_user"]
      and any("after a nudge and an escalation" in alert["title"] and PROMISE in alert["alert_text"]
              for alert in machine.alerts()),
      (machine.events("wait_step"), machine.alerts()))

# A rule 5 wait whose only rule 2 group is a failed message's: a task call after the failure still
# ends it, though no promise_message event is on the wait.
machine = promise_sent_on_rule_five_wait(PROMISE_SEND_FAILS)
machine.append("alpha", user("go on", at(7.5)),
               assistant(tool=("TaskCreate", {"subject": "report on PR 927", "metadata": {
                   "prerequisites": [{"pr_merged": 927}]}}), when=at(7.6), tool_id="t-after"),
               task_result("t-after", "Task #1 created successfully: report on PR 927", at(7.61)),
               assistant("Recorded.", at(8)), turn_end(at(8)))
machine.script()
machine.run(14)
check("rule 2: a task call after the failed send of a rule 5 wait's only promise message ends the "
      "wait",
      [event["why"] for event in machine.events("wait_ended")]
      == ["it recorded what a task waits on after the promise message"], machine.events())

# The same, but the task call falls while the failing send was still being tried: it cannot answer
# a message the agent-seat never got, so it does not end the wait.
machine = promise_sent_on_rule_five_wait(dict(PROMISE_SEND_FAILS, sleep=2.5))
machine.append("alpha", user("go on", at(7.005)),
               assistant(tool=("TaskCreate", {"subject": "report on PR 927", "metadata": {
                   "prerequisites": [{"pr_merged": 927}]}}), when=at(7.02), tool_id="t-during"),
               task_result("t-during", "Task #1 created successfully: report on PR 927", at(7.021)),
               assistant("Recorded.", at(8)), turn_end(at(8)))
machine.script()
machine.run(14)
check("rule 2: a task call made while a promise message's failing send was tried does not end the "
      "wait",
      machine.events("promise_message_send_failed")[0]["at"] > at(7.02)
      and not machine.events("wait_ended"), machine.events())

# A wait that already has a delivered promise message, then a second whose send failed: a task call
# backing the first promise alone does not end the wait before the failed one is reported.
OTHER_PROMISE = "I'll report when PR 928 merges."
machine = Machine()
machine.seat("alpha", [user("go"), assistant(PROMISE), turn_end()])
machine.script(sent_ok())
machine.run(0)
machine.append("alpha", cross_session(machine.events("message_sent")[-1]["text"], at(0.5)),
               assistant(OTHER_PROMISE, at(1)), turn_end(at(1)))
machine.script(PROMISE_SEND_FAILS)
machine.run(7)
machine.append("alpha", user("go on", at(7.5)),
               assistant(tool=("TaskCreate", {"subject": "report on PR 927", "metadata": {
                   "prerequisites": [{"pr_merged": 927}]}}), when=at(7.6), tool_id="t-first"),
               task_result("t-first", "Task #1 created successfully: report on PR 927", at(7.61)),
               assistant("Recorded.", at(8)), turn_end(at(8)))
machine.script()
machine.run(14)
check("rule 2: a task call backing a delivered promise does not end a wait whose later promise "
      "message failed to send",
      failed_send_sentences(machine) == [[OTHER_PROMISE]] and not machine.events("wait_ended"), machine.events())
machine.append("alpha", user("and the other", at(14.5)),
               assistant(tool=("TaskCreate", {"subject": "report on PR 928", "metadata": {
                   "prerequisites": [{"pr_merged": 928}]}}), when=at(14.6), tool_id="t-second"),
               task_result("t-second", "Task #2 created successfully: report on PR 928", at(14.61)),
               assistant("Recorded.", at(15)), turn_end(at(15)))
machine.run(21)
check("rule 2: a task call for each promise, the failed message's included, ends the wait and "
      "lists both sentences",
      [(event["why"], event.get("sentences")) for event in machine.events("wait_ended")]
      == [("it recorded what a task waits on after the promise message",
           [PROMISE, OTHER_PROMISE])], machine.events("wait_ended"))

# The sender runs on after its SendMessage, and the agent-seat records the task before it ends.
machine = promise_sent_on_rule_five_wait(dict(sent_ok(), sleep=2.5))
machine.append("alpha", cross_session(machine.events("message_sent")[-1]["text"], at(7.01)),
               assistant(tool=("TaskCreate", {"subject": "report on PR 927", "metadata": {
                   "prerequisites": [{"pr_merged": 927}]}}), when=at(7.025), tool_id="t-early"),
               task_result("t-early", "Task #1 created successfully: report on PR 927", at(7.03)),
               assistant("Recorded.", at(8)), turn_end(at(8)))
machine.script()
machine.run(14)
check("rule 2: a task call made after a promise message's send started, but before its sender "
      "ended, ends the wait",
      machine.events("promise_message")[0]["at"] > at(7.025)
      and [event["why"] for event in machine.events("wait_ended")]
      == ["it recorded what a task waits on after the promise message"], machine.events())

# A promise message that opens its wait reaches the agent-seat in the escalation, which quotes it,
# when its own send fails.
machine = Machine()
machine.seat("alpha", [user("go"), assistant(PROMISE), turn_end()])
machine.script(PROMISE_SEND_FAILS)
machine.run(0)
machine.script(rechecked(False), sent_ok())
machine.run(16)
escalation = machine.events("message_sent")[-1]["text"]
machine.append("alpha", cross_session(escalation, at(16.2)),
               assistant(tool=("TaskCreate", {"subject": "report on PR 927", "metadata": {
                   "prerequisites": [{"pr_merged": 927}]}}), when=at(16.5), tool_id="t-late"),
               task_result("t-late", "Task #1 created successfully: report on PR 927", at(16.51)),
               assistant("Recorded.", at(17)), turn_end(at(17)))
machine.script()
machine.run(23)
check("rule 2: a promise message that opened its wait and failed to send is quoted in the "
      "escalation, and a task call after the escalation ends the wait",
      PROMISE in escalation and [event["why"] for event in machine.events("wait_ended")]
      == ["it recorded what a task waits on after the promise message"], machine.events())

ANNOUNCED = "I'm starting the PR 1633 work now."

# An agent-seat that records the task a promise message asked for, and then sits idle waiting on it.
RECORDED_TASK = assistant(tool=("TaskCreate", {"subject": "report on PR 927", "metadata": {
    "prerequisites": [{"pr_merged": 927}]}}), when=at(0.8), tool_id="t-recorded")
RECORDED_TASK_RESULT = task_result("t-recorded", "Task #1 created successfully: report on PR 927",
                                   at(0.81))
machine = Machine()
machine.seat("alpha", [user("go"), assistant(PROMISE), turn_end()])
machine.script(sent_ok())
machine.run(0)
machine.append("alpha", cross_session(machine.events("message_sent")[-1]["text"], at(0.5)),
               RECORDED_TASK, RECORDED_TASK_RESULT,
               assistant("Recorded.", at(1)), turn_end(at(1)))
machine.script()
machine.run(7)
check("rule 2: a task call recording what a task waits on, after the promise message, ends the wait",
      [event["why"] for event in machine.events("wait_ended")]
      == ["it recorded what a task waits on after the promise message"], machine.events())
machine.script(sent_ok())
machine.run(16)
machine.script()
machine.run(32)
check("rule 2: the agent-seat that recorded the task is neither escalated nor reported to the user",
      [event["step"] for event in machine.events("wait_step")] == ["nudge"]
      and not machine.events("message_sent")[1:] and not machine.alerts(),
      (machine.events("wait_step"), machine.events("message_sent"), machine.alerts()))
check("rule 2: the wait_ended event lists the sentence and the task call taken to settle it",
      [(event.get("sentences"), event.get("task_calls")) for event in machine.events("wait_ended")]
      == [([PROMISE], [{"time": at(0.8), "name": "TaskCreate", "task": "1"}])],
      machine.events("wait_ended"))


def promise_wait_after(transcript, *answer_records):
    """A machine whose agent-seat gave the promise message an answer, run to minute 16."""
    machine = Machine()
    machine.seat("alpha", transcript)
    machine.script(sent_ok())
    machine.run(0)
    machine.append("alpha", cross_session(machine.events("message_sent")[-1]["text"], at(0.5)),
                   *answer_records, assistant("Recorded.", at(1)), turn_end(at(1)))
    machine.script()
    machine.run(7)
    machine.script(rechecked(*[False] * sum(len(event["sentences"])
                                            for event in machine.events("promise_message"))),
                   sent_ok())
    machine.run(16)
    return machine


def waited_on_to_escalation(machine):
    return (not machine.events("wait_ended")
            and [event["step"] for event in machine.events("wait_step")] == ["nudge", "escalate"]
            and machine.events("message_sent")[-1]["step"] == "escalate")


# A task call made in an earlier turn, before the promise message, backs nothing that message asks.
machine = promise_wait_after(
    [user("plan", "2026-11-02T11:40:00Z"),
     assistant(tool=("TaskCreate", {"subject": "older task",
                                    "metadata": {"prerequisites": [{"pr_merged": 5}]}}),
               when="2026-11-02T11:41:00Z", tool_id="t-older"),
     task_result("t-older", "Task #1 created successfully: older task", "2026-11-02T11:41:01Z"),
     assistant("Set up.", "2026-11-02T11:42:00Z"), turn_end("2026-11-02T11:42:00Z"),
     user("go"), assistant(PROMISE), turn_end()])
check("rule 2: a task call made before the promise message does not end the wait, and the "
      "escalation is sent", waited_on_to_escalation(machine),
      (machine.events("wait_step"), machine.events("wait_ended")))

HOLD_SENTENCE = "I'll hold the deploy until you approve."
TWO_PROMISES = [user("go"), assistant(f"{PROMISE} {HOLD_SENTENCE}"), turn_end()]
machine = promise_wait_after(TWO_PROMISES, RECORDED_TASK, RECORDED_TASK_RESULT)
check("rule 2: one task call does not end a wait whose message named two promises",
      waited_on_to_escalation(machine), (machine.events("wait_step"), machine.events("wait_ended")))
SAME_TASK_UPDATED = [
    record for number in range(2)
    for record in (assistant(tool=("TaskUpdate", {"taskId": "2", "addBlockedBy": ["1"]}),
                             when=at(0.8), tool_id=f"t-same-{number}"),
                   task_result(f"t-same-{number}", "Updated task #2 blockedBy", at(0.81)))]
machine = promise_wait_after(TWO_PROMISES, *SAME_TASK_UPDATED)
check("rule 2: two calls on one task do not end a wait whose message named two promises",
      waited_on_to_escalation(machine), (machine.events("wait_step"), machine.events("wait_ended")))
machine = promise_wait_after(
    TWO_PROMISES, RECORDED_TASK, RECORDED_TASK_RESULT,
    assistant(tool=("TaskUpdate", {"taskId": "2", "addBlockedBy": ["1"]}), when=at(0.9),
              tool_id="t2"),
    task_result("t2", "Updated task #2 blockedBy", at(0.91)))
check("rule 2: a task call for each of the message's two promises ends the wait, and the "
      "wait_ended event lists both sentences and both calls",
      [(event["why"], event.get("sentences"), [call["task"] for call in event.get("task_calls", [])])
       for event in machine.events("wait_ended")]
      == [("it recorded what a task waits on after the promise message",
           [PROMISE, HOLD_SENTENCE], ["1", "2"])],
      machine.events("wait_ended"))

machine = promise_wait_after(
    [user("go"), assistant(PROMISE), turn_end()],
    assistant(tool=("TaskUpdate", {"taskId": "2", "metadata": {
        "prerequisites": [{"pr_merged": 927}]}}), when=at(0.8), tool_id="t-no-result"))
check("rule 2: a TaskUpdate with no result, as when its turn was interrupted, does not end the wait",
      waited_on_to_escalation(machine), (machine.events("wait_step"), machine.events("wait_ended")))

machine = promise_wait_after(
    [user("go"), assistant(PROMISE), turn_end()],
    assistant(tool=("TaskUpdate", {"taskId": "99", "metadata": {
        "prerequisites": [{"pr_merged": 927}]}}), when=at(0.8), tool_id="t-failed"),
    task_result("t-failed", "Task not found", at(0.85)))
check("rule 2: a TaskUpdate answered 'Task not found', with no is_error, does not end the wait",
      waited_on_to_escalation(machine), (machine.events("wait_step"), machine.events("wait_ended")))

# A wait whose rule 2 message was logged by the version before PROMISE_MESSAGE events named their
# sentences: what that message named is unknown, so no task call ends the wait.
machine = Machine()
machine.seat("alpha", [user("go"), assistant(PROMISE), turn_end()])
machine.script(sent_ok())
machine.run(0)
machine.log.write_text("".join(
    json.dumps({key: value for key, value in event.items() if key != "sentences"}) + "\n"
    for event in machine.events()))
machine.append("alpha", cross_session(machine.events("message_sent")[-1]["text"], at(0.5)),
               RECORDED_TASK, RECORDED_TASK_RESULT, assistant("Recorded.", at(1)), turn_end(at(1)))
machine.script()
machine.run(7)
machine.script(sent_ok())
machine.run(16)
check("rule 2: a task call does not end a wait whose promise message was logged without its "
      "sentences, and with no sentences to re-check the escalation is sent without the re-check",
      waited_on_to_escalation(machine) and len(machine.claude_calls()) == 1,
      (machine.events("wait_step"), machine.events("wait_ended")))
machine = Machine()
machine.seat("alpha", [user("go"), assistant(PROMISE), turn_end()])
machine.script(sent_ok())
machine.run(0)
machine.log.write_text("".join(json.dumps(event) + "\n" for event in machine.events()
                               if event["event"] != "promise_message"))
machine.append("alpha", cross_session(machine.events("message_sent")[-1]["text"], at(0.5)),
               assistant(HOLD_SENTENCE, at(1)), turn_end(at(1)))
machine.script(sent_ok())
machine.run(7)
machine.append("alpha", user("ok", at(7.5)),
               assistant(tool=("TaskCreate", {"subject": "hold the deploy", "metadata": {
                   "prerequisites": [{"pr_merged": 9}]}}), when=at(7.8), tool_id="t-hold"),
               task_result("t-hold", "Task #2 created successfully: hold the deploy", at(7.81)),
               assistant("Recorded.", at(8)), turn_end(at(8)))
machine.script()
machine.run(14)
check("rule 2: a promise message logged on a wait whose first rule 2 message has no "
      "promise_message event does not let a task call end the wait",
      not machine.events("wait_ended") and len(machine.events("promise_message")) == 1,
      (machine.events("promise_message"), machine.events("wait_ended")))

machine = Machine()
machine.seat("alpha", [user("go"), assistant(PROMISE), turn_end()])
machine.script(sent_ok())
machine.run(0)
machine.log.write_text("".join(
    json.dumps({key: value for key, value in event.items()
                if key != "agent_seat_idle_sweep_invocation_started_at"}) + "\n"
    for event in machine.events() if event["event"] != "promise_message"))
machine.append("alpha", cross_session(machine.events("message_sent")[-1]["text"], at(0.5)),
               assistant(HOLD_SENTENCE, at(1)), turn_end(at(1)))
machine.script(sent_ok())
machine.run(7)
machine.append("alpha", user("ok", at(7.5)),
               assistant(tool=("TaskCreate", {"subject": "hold the deploy", "metadata": {
                   "prerequisites": [{"pr_merged": 9}]}}), when=at(7.8), tool_id="t-hold"),
               task_result("t-hold", "Task #2 created successfully: hold the deploy", at(7.81)),
               assistant("Recorded.", at(8)), turn_end(at(8)))
machine.script()
machine.run(14)
check("rule 2: on a wait whose first rule 2 message was logged with no invocation stamp and no "
      "promise_message event, a later promise message does not let a task call end the wait",
      not machine.events("wait_ended") and len(machine.events("promise_message")) == 1,
      (machine.events("promise_message"), machine.events("wait_ended")))

machine = Machine()
machine.seat("alpha", [user("go"), assistant(PROMISE), turn_end()])
machine.script(sent_ok())
machine.run(0)
machine.append("alpha", cross_session(machine.events("message_sent")[-1]["text"], at(0.5)),
               assistant(HOLD_SENTENCE, at(1)), turn_end(at(1)))
machine.script(sent_ok())
machine.run(7)
machine.append("alpha", user("ok", at(7.5)),
               assistant(tool=("TaskCreate", {"subject": "hold the deploy", "metadata": {
                   "prerequisites": [{"pr_merged": 9}]}}), when=at(7.8), tool_id="t-hold"),
               task_result("t-hold", "Task #2 created successfully: hold the deploy", at(7.81)),
               assistant("Recorded.", at(8)), turn_end(at(8)))
machine.script()
machine.run(14)
check("rule 2: two rule 2 messages on one wait, each naming one promise, and one task call after "
      "the second: the first message's promise has no task of its own, so the wait stays open",
      not machine.events("wait_ended") and len(machine.events("promise_message")) == 2,
      (machine.events("promise_message"), machine.events("wait_ended")))

CREATED_THEN_UPDATED = [
    RECORDED_TASK, RECORDED_TASK_RESULT,
    assistant(tool=("TaskUpdate", {"taskId": "1", "addBlockedBy": ["4"]}), when=at(0.9),
              tool_id="t-update-1"),
    task_result("t-update-1", "Updated task #1 blockedBy", at(0.91))]
machine = promise_wait_after(TWO_PROMISES, *CREATED_THEN_UPDATED)
check("rule 2: a TaskCreate and a later TaskUpdate of the same task count as one task, so they do "
      "not end a wait whose message named two promises",
      waited_on_to_escalation(machine), (machine.events("wait_step"), machine.events("wait_ended")))
SAME_SUBJECT_CREATED_TWICE = [
    record for number in (1, 2)
    for record in (assistant(tool=("TaskCreate", {"subject": "report", "metadata": {
                       "prerequisites": [{"pr_merged": 927}]}}), when=at(0.8 + number / 100),
                             tool_id=f"t-create-{number}"),
                   task_result(f"t-create-{number}", f"Task #{number} created successfully: report",
                               at(0.81 + number / 100)))]
machine = promise_wait_after(TWO_PROMISES, *SAME_SUBJECT_CREATED_TWICE)
check("rule 2: two TaskCreates with one subject create two tasks, which end a wait whose message "
      "named two promises",
      [[call["task"] for call in event.get("task_calls", [])]
       for event in machine.events("wait_ended")] == [["1", "2"]],
      machine.events("wait_ended"))

machine = Machine()
machine.seat("alpha", [user("go"), assistant(f"{PROMISE} {ANNOUNCED}"), turn_end()])
machine.script({"answer": {"sentences": [{"index": 0, "backed": False, "reason": "no tool call"}]}},
               sent_ok())
machine.run(0)
machine.append("alpha", cross_session(machine.events("message_sent")[-1]["text"], at(0.5)),
               *CREATED_THEN_UPDATED[:2],
               assistant(tool=("TaskUpdate", {"taskId": "2", "addBlockedBy": ["1"]}), when=at(0.9),
                         tool_id="t2"),
               task_result("t2", "Updated task #2 blockedBy", at(0.91)),
               assistant("Recorded.", at(1)), turn_end(at(1)))
machine.script()
machine.run(7)
check("rule 2: task calls do not end a wait whose message also named an announced action, which "
      "only the judge can find done", not machine.events("wait_ended"), machine.events("wait_ended"))
machine.script(rechecked(True, False), sent_ok())
machine.run(16)
check("rule 2: the re-check finds the promise backed by its task and the announced action not "
      "done: the escalation is sent",
      not machine.events("wait_ended") and len(machine.claude_calls()) == 2
      and [event["step"] for event in machine.events("wait_step")] == ["nudge", "escalate"]
      and machine.events("message_sent")[-1]["step"] == "escalate"
      and [answer["backed"] for answer in machine.events("judge_answer")[-1]["answers"]]
      == [True, False],
      (machine.events("wait_step"), machine.events("wait_ended"), machine.events("judge_answer")))

# --- rule 2: the re-check before the escalation ---------------------------------------------------
OPENING_PULL_REQUEST = "Next I'm opening the pull request."
machine = Machine()
machine.seat("alpha", [user("go"), assistant(OPENING_PULL_REQUEST), turn_end()])
machine.script(rechecked(False), sent_ok())
machine.run(0)
machine.append("alpha", cross_session(machine.events("message_sent")[-1]["text"], at(1)),
               assistant(tool=("Bash", {"command": "gh pr create --fill"}), when=at(2), tool_id="t-pr"),
               assistant("Opened PR 1.", at(2.2)), turn_end(at(2.3)))
machine.script(rechecked(True))
machine.run(16)
check("re-check: an agent-seat that did its announced action after the nudge is not escalated, and "
      "the wait ends with the sentence and the judge's reason",
      [(event["why"], event.get("sentences"), event.get("judge_reasons"))
       for event in machine.events("wait_ended")]
      == [("the judge found every sentence its promise messages named backed",
           [OPENING_PULL_REQUEST], ["sentence 0 backed"])]
      and [event["step"] for event in machine.events("message_sent")] == ["nudge"],
      (machine.events("wait_ended"), machine.events("message_sent")))
machine.script()
machine.run(32)
check("re-check: a wait the judge ended reaches no user-alert and no second re-check",
      not machine.alerts() and not machine.claude_calls(), (machine.alerts(), machine.claude_calls()))


def first_judge_facts(calls):
    """The JSON facts that end the first call's prompt, or {} when that prompt is not a judge's."""
    prompt = calls[0]["prompt"] if calls else ""
    return json.loads(prompt[prompt.rindex("\n{") + 1:]) if "\n{" in prompt else {}


# An agent-seat that announced an action, then deferred it: it told the user what the change waits
# on, and recorded a task whose prerequisites name that.
EDITOR_SENTENCE = ("I'll start its change together with item 59.3's, because all three edits go on "
                   "the same line of the skill and in one topic branch.")
EDITOR_SECOND_SENTENCE = "Next I'm opening the pull request for item 58."
EDITOR_REPLY = ("The skill change for item 59.2 starts when you answer item 59.3, because both items "
                "edit the same line of the skill. I logged it as task #389.")
EDITOR_DEFERRAL = [
    assistant(tool=("TaskCreate", {"subject": "Items 59.2 and 59.3: edit the skill"}), when=at(0.3),
              tool_id="t-389"),
    task_result("t-389", "Task #389 created successfully: Items 59.2 and 59.3: edit the skill",
                at(0.31)),
    assistant(tool=("TaskUpdate", {"taskId": "389", "metadata": {"prerequisites": [
        {"approval_walk_item_decided": {
            "approval_walk_minutes_file_path": "docs/walk/backlog-decisions-minutes.md",
            "approval_walk_item_heading": "Item 59.3 of 117"}}]}}), when=at(0.4),
              tool_id="t-389-update"),
    task_result("t-389-update", "Updated task #389 metadata", at(0.41)),
    assistant(EDITOR_REPLY, at(0.5)), turn_end(at(0.5))]


def editor_deferred_machine(message):
    """A machine whose agent-seat was nudged at minute 0 about the sentences of message, and
    answered by deferring them as task 389 and telling the user so."""
    machine = Machine()
    machine.seat("alpha", [user("present item 59.3"), assistant(message), turn_end()])
    sentence_count = len([sentence for sentence in (EDITOR_SENTENCE, EDITOR_SECOND_SENTENCE)
                          if sentence in message])
    machine.script(rechecked(*[False] * sentence_count), sent_ok())
    machine.run(0)
    machine.append("alpha", cross_session(machine.events("message_sent")[-1]["text"], at(0.2)),
                   *EDITOR_DEFERRAL)
    return machine


machine = editor_deferred_machine(f"Item 59.2 is approved as obvious. {EDITOR_SENTENCE}")
machine.script()
machine.run(7)
check("re-check: before the escalation falls due, no judge is asked and the wait stays open",
      not machine.events("wait_ended") and not machine.claude_calls(),
      (machine.events("wait_ended"), machine.claude_calls()))
machine.script(rechecked(True))
machine.run(16)
calls = machine.claude_calls()
recheck_facts = first_judge_facts(calls)
check("re-check: the judge is handed the raised sentence, the deferral's task calls and the text "
      "telling the user, and no tool",
      len(calls) == 1 and calls[0]["argv"][calls[0]["argv"].index("--tools") + 1] == ""
      and [item["sentence"] for item in recheck_facts.get("sentences", [])] == [EDITOR_SENTENCE]
      and [call["name"] for call in recheck_facts.get("tool_calls_since", [])]
      == ["TaskCreate", "TaskUpdate"]
      and "approval_walk_item_decided" in recheck_facts["tool_calls_since"][-1]["input"]
      and [call["task"] for call in recheck_facts.get(
          "successful_task_tool_calls_setting_prerequisites_or_blocked_by_since", [])] == ["389"]
      and EDITOR_REPLY in [item["text"] for item in recheck_facts.get("text_messages_since", [])],
      calls)

machine = editor_deferred_machine(
    f"Item 59.2 is approved as obvious. {EDITOR_SENTENCE} {EDITOR_SECOND_SENTENCE}")
machine.script(rechecked(True, False), sent_ok())
machine.run(16)
calls = machine.claude_calls()
check("re-check finds one sentence of two unbacked: the escalation is sent after it",
      len(calls) == 2 and "please check" in calls[1]["prompt"] and not machine.events("wait_ended")
      and [event["step"] for event in machine.events("wait_step")] == ["nudge", "escalate"]
      and machine.events("message_sent")[-1]["step"] == "escalate",
      (calls, machine.events("wait_step"), machine.events("wait_ended")))
machine.script()
machine.run(31.5)
check("an escalated wait reaches the user-alert without another re-check",
      not machine.claude_calls()
      and [event["step"] for event in machine.events("wait_step")] == ["nudge", "escalate", "tell_user"]
      and any("after a nudge and an escalation" in alert["title"] for alert in machine.alerts()),
      (machine.claude_calls(), machine.events("wait_step"), machine.alerts()))

for case, answer, subject in (
        ("exits nonzero", {"exit": 2, "stderr": "the re-check judge failed"},
         "Idle sweep: a headless agent-session failed: claude exited 2"),
        ("answers for too few sentences", {"answer": {"sentences": []}},
         "Idle sweep: a headless agent-session failed: the judge's answer could not be used")):
    machine = editor_deferred_machine(f"Item 59.2 is approved as obvious. {EDITOR_SENTENCE}")
    machine.script(answer, sent_ok())
    code, _ = machine.run(16)
    check(f"the re-check judge {case}: a task for the owning agent-seat, no user-alert, and the "
          "escalation is sent",
          code == 1 and len(machine.claude_calls()) == 2
          and [event["purpose"] for event in machine.events("headless_failed")]
          == ["re-check whether the sentences its promise messages named are backed"]
          and machine.owner_task_subjects() == [subject] and not machine.alerts()
          and not machine.events("wait_ended")
          and [event["step"] for event in machine.events("wait_step")] == ["nudge", "escalate"]
          and machine.events("message_sent")[-1]["step"] == "escalate",
          (code, machine.events("headless_failed"), machine.owner_tasks(), machine.alerts()))
    machine.script()
    machine.run(17)
    check(f"the re-check judge {case}: the next invocation asks no re-check again",
          not machine.claude_calls(), machine.claude_calls())

# The transcript turns unreadable between the verdict pass and the re-check: here the first judge,
# a headless agent-session that runs before the due step, breaks it.
machine = Machine()
machine.seat("alpha", [user("go"), assistant(OPENING_PULL_REQUEST), turn_end()])
machine.script(rechecked(False), sent_ok())
machine.run(0)
machine.append("alpha", cross_session(machine.events("message_sent")[-1]["text"], at(1)),
               assistant(ANNOUNCED, at(2)), turn_end(at(2.3)))
machine.seat("beta", [user("go"), assistant(ANNOUNCED, when=at(2)), turn_end(at(2.3))])
machine.script(dict(rechecked(True), overwrite=[str(machine.transcripts["alpha"]), "not json\n"]),
               sent_ok(), rechecked(True))
code, _ = machine.run(16)
calls = machine.claude_calls()
check("re-check: a transcript unreadable at the re-check is a read failure for that agent-seat; "
      "its escalation is sent, and the next agent-seat is still swept",
      [event["agent_seat"] for event in machine.events("read_failure")] == ["alpha"]
      and [event["step"] for event in machine.events("wait_step")] == ["nudge", "escalate"]
      and len(calls) == 3 and "please check" in calls[1]["prompt"]
      and '"agent_seat": "beta"' in calls[2]["prompt"]
      and any(event["step"] == "escalate" and event["agent_seat"] == "alpha"
              for event in machine.events("message_sent")),
      (code, machine.events("read_failure"), machine.events("wait_step"),
       machine.events("message_sent"), calls))

# An agent-seat that promised a report and gave it in a text-only reply, after its turn ended and
# before the nudge.
REPORT_SENTENCE = "I'll tell you what it finds."
REPORT_TEXT = ("The subagent found that my second explanation was also wrong, so there is no simple "
               "bug to fix.")
machine = Machine()
machine.seat("alpha", [user("go", "2026-11-02T11:30:00Z"), assistant("Started.", "2026-11-02T11:31:00Z"),
                       turn_end("2026-11-02T11:31:00Z")])
machine.run(-20)
machine.append(
    "alpha", user("file it", "2026-11-02T11:44:00Z"),
    assistant(tool=("Agent", {"description": "Find the idle sweep's miss"}),
              when="2026-11-02T11:44:30Z", tool_id="t-agent"),
    assistant(f"I haven't filed the GHI. {REPORT_SENTENCE}", "2026-11-02T11:45:00Z"),
    turn_end("2026-11-02T11:45:00Z"),
    user("<task-notification>\n<task-id>a8063202</task-id>\n<status>completed</status>\n"
         "</task-notification>", "2026-11-02T11:52:00Z"),
    assistant(REPORT_TEXT, "2026-11-02T11:53:00Z"),
    assistant("Task #743 is waiting for your answer on the judge re-check.", "2026-11-02T11:54:00Z"),
    turn_end("2026-11-02T11:54:00Z"))
machine.script(rechecked(False), sent_ok())
machine.run(0)
check("re-check: a rule 2 message logs the time of the earliest sentence it names",
      [event["sentences"] for event in machine.events("promise_message")] == [[REPORT_SENTENCE]]
      and machine.events("promise_message")[0].get("earliest_sentence_at")
      == "2026-11-02T11:45:00Z", machine.events())
machine.append("alpha", cross_session(machine.events("message_sent")[-1]["text"], at(0.2)),
               assistant("I had already done it: my message before last gives you the subagent's "
                         "findings.", at(0.3)), turn_end(at(0.3)))
machine.script(rechecked(True))
machine.run(16)
calls = machine.claude_calls()
recheck_facts = first_judge_facts(calls)
check("re-check: the text reply written after the sentence and before the nudge is handed to the "
      "judge, and the sentence's own message is not",
      len(calls) == 1
      and REPORT_TEXT in [item["text"] for item in recheck_facts.get("text_messages_since", [])]
      and not any(REPORT_SENTENCE in item["text"]
                  for item in recheck_facts.get("text_messages_since", [])), calls)
check("re-check backs a promise kept in a text-only reply: the wait ends, and no escalation is sent",
      [event["why"] for event in machine.events("wait_ended")]
      == ["the judge found every sentence its promise messages named backed"]
      and [event["step"] for event in machine.events("message_sent")] == ["nudge"],
      (machine.events("wait_ended"), machine.events("message_sent")))

machine = Machine()
machine.seat("alpha", [user("go"), assistant(OPENING_PULL_REQUEST), turn_end()])
machine.script(rechecked(False), sent_ok())
machine.run(0)
machine.log.write_text("".join(
    json.dumps({key: value for key, value in event.items() if key != "earliest_sentence_at"}) + "\n"
    for event in machine.events()))
machine.append("alpha", assistant("Early text.", at(-1)),
               assistant("Text after the message.", at(1)), turn_end(at(1)))
machine.script(rechecked(True))
machine.run(16)
recheck_facts = first_judge_facts(machine.claude_calls())
check("re-check: a promise_message logged without earliest_sentence_at is read from the message's "
      "own time", recheck_facts.get("since") == at(0)
      and [item["text"] for item in recheck_facts.get("text_messages_since", [])]
      == ["Text after the message."], recheck_facts)

# A delivered sentence and a later one whose message failed to send: the wait may end only when the
# judge has answered for both.
MIGRATION_SENTENCE = "Next I'm running the migration."


def delivered_and_failed_sentences_machine():
    machine = Machine()
    machine.seat("alpha", [user("go"), assistant(OPENING_PULL_REQUEST), turn_end()])
    machine.script(rechecked(False), sent_ok())
    machine.run(0)
    machine.append("alpha", cross_session(machine.events("message_sent")[-1]["text"], at(1)),
                   assistant(tool=("Bash", {"command": "gh pr create --fill"}), when=at(2),
                             tool_id="t-pr"),
                   assistant(MIGRATION_SENTENCE, at(2.2)), turn_end(at(2.3)))
    machine.script(rechecked(False), PROMISE_SEND_FAILS)
    machine.run(9)
    return machine


machine = delivered_and_failed_sentences_machine()
machine.script(rechecked(True), sent_ok())
machine.run(17)
recheck_facts = first_judge_facts(machine.claude_calls())
check("re-check: the judge is asked about a sentence whose message failed to send, so an answer "
      "covering only the delivered sentence does not end the wait",
      [item["sentence"] for item in recheck_facts.get("sentences", [])]
      == [OPENING_PULL_REQUEST, MIGRATION_SENTENCE] and not machine.events("wait_ended")
      and machine.events("message_sent")[-1]["step"] == "escalate"
      and MIGRATION_SENTENCE in machine.events("message_sent")[-1]["text"],
      (recheck_facts.get("sentences"), machine.events("wait_ended")))
machine = delivered_and_failed_sentences_machine()
failures_before = len(machine.events("headless_failed"))
machine.script(rechecked(True, True))
machine.run(17)
check("re-check: when the judge finds the delivered and the failed sentence both backed, the wait "
      "ends and lists both",
      [event.get("sentences") for event in machine.events("wait_ended")]
      == [[OPENING_PULL_REQUEST, MIGRATION_SENTENCE]]
      and len(machine.events("headless_failed")) == failures_before,
      (machine.events("wait_ended"), machine.events("headless_failed")))
machine = delivered_and_failed_sentences_machine()
machine.script(rechecked(True, False), sent_ok())
machine.run(17)
check("re-check: when the judge finds the failed message's sentence unbacked, the escalation quotes "
      "that sentence",
      not machine.events("wait_ended") and machine.events("message_sent")[-1]["step"] == "escalate"
      and MIGRATION_SENTENCE in machine.events("message_sent")[-1]["text"],
      (machine.events("wait_ended"), machine.events("message_sent")))

# A sentence whose first judge failed on an open wait has no message, and the wait answers for it.
JUDGE_FAILS = {"exit": 1, "stderr": "529 overloaded"}


def first_judge_failed_on_open_wait():
    machine = Machine()
    machine.seat("alpha", [user("go"), assistant(PROMISE), turn_end()])
    machine.script(sent_ok())
    machine.run(0)
    machine.append("alpha", cross_session(machine.events("message_sent")[-1]["text"], at(0.5)),
                   assistant(OPENING_PULL_REQUEST, at(1)), turn_end(at(1)))
    machine.script(JUDGE_FAILS)
    machine.run(7)
    return machine


machine = first_judge_failed_on_open_wait()
machine.script(rechecked(True), sent_ok())
machine.run(16)
recheck_facts = first_judge_facts(machine.claude_calls())
check("re-check: a sentence whose first judge failed is asked about, so an answer covering only the "
      "older sentence does not end the wait, and the escalation is sent",
      [item["sentence"] for item in recheck_facts.get("sentences", [])]
      == [PROMISE, OPENING_PULL_REQUEST] and not machine.events("wait_ended")
      and machine.events("message_sent")[-1]["step"] == "escalate",
      (recheck_facts.get("sentences"), machine.events("wait_ended")))
machine = first_judge_failed_on_open_wait()
machine.script(rechecked(True, True))
machine.run(16)
check("re-check: when the judge finds the older sentence and the one whose first judge failed both "
      "backed, the wait ends and lists both",
      [event.get("sentences") for event in machine.events("wait_ended")]
      == [[PROMISE, OPENING_PULL_REQUEST]], machine.events("wait_ended"))

machine = Machine()
machine.seat("alpha", [user("go"), assistant(PROMISE), turn_end()])
machine.script(sent_ok())
machine.run(0)
machine.append("alpha", cross_session(machine.events("message_sent")[-1]["text"], at(0.5)),
               assistant(OPENING_PULL_REQUEST, at(1)), turn_end(at(1)))
machine.script(JUDGE_FAILS, rechecked(True), sent_ok())
machine.run(16)
recheck_facts = first_judge_facts(machine.claude_calls()[1:])
check("re-check: a sentence whose first judge fails in the invocation the escalation falls due is "
      "asked about too",
      [item["sentence"] for item in recheck_facts.get("sentences", [])]
      == [PROMISE, OPENING_PULL_REQUEST] and not machine.events("wait_ended")
      and machine.events("message_sent")[-1]["step"] == "escalate",
      (recheck_facts.get("sentences"), machine.events("wait_ended")))

machine = first_judge_failed_on_open_wait()
machine.append("alpha", user("go on", at(8)),
               assistant(tool=("TaskCreate", {"subject": "report on PR 927", "metadata": {
                   "prerequisites": [{"pr_merged": 927}]}}), when=at(8.1), tool_id="t-after-failed"),
               task_result("t-after-failed", "Task #1 created successfully: report on PR 927",
                           at(8.11)),
               assistant("Recorded.", at(8.2)), turn_end(at(8.2)))
machine.script()
machine.run(14)
check("rule 2: a task call backing the older promise does not end a wait holding a sentence whose "
      "first judge failed", not machine.events("wait_ended"), machine.events("wait_ended"))

machine = Machine()
machine.seat("alpha", DONE_TURN)
machine.task("alpha", "1")
machine.script(judged(True, "What's going on?", "nothing runs"), sent_ok())
machine.run(0)
(machine.tasks / "nedsnodes-alpha-tasks" / "1.json").unlink()
machine.append("alpha", cross_session(machine.events("message_sent")[-1]["text"], at(0.5)),
               assistant(OPENING_PULL_REQUEST, at(1)), turn_end(at(1)))
machine.script(JUDGE_FAILS)
machine.run(7)
machine.append("alpha", user("go on", at(8)),
               assistant(tool=("Bash", {"command": "ls"}), when=at(8.1)),
               assistant("Listed.", at(8.2)), turn_end(at(8.2)))
machine.script()
machine.run(14)
check("rule 2: on a wait a rule 5 message opened, a tool call does not end the wait once a sentence's "
      "first judge has failed", not machine.events("wait_ended"), machine.events("wait_ended"))

# An invocation stopped after a rule 2 message's send and before its promise_message event.
machine = Machine()
machine.seat("alpha", [user("go"), assistant(PROMISE), turn_end()])
machine.script(sent_ok())
machine.run(0)
machine.append("alpha", cross_session(machine.events("message_sent")[-1]["text"], at(0.5)),
               assistant(SECOND_PROMISE, at(1)), turn_end(at(1)))
machine.script(sent_ok())
machine.run(7)
log_lines = machine.log.read_text().splitlines(keepends=True)
last_message = max(number for number, line in enumerate(log_lines)
                   if json.loads(line)["event"] == "promise_message")
machine.log.write_text("".join(log_lines[:last_message] + log_lines[last_message + 1:]))
machine.script(rechecked(True), sent_ok())
machine.run(16)
recheck_facts = first_judge_facts(machine.claude_calls())
check("re-check: a sentence whose invocation was stopped before logging its message is asked about",
      [item["sentence"] for item in recheck_facts.get("sentences", [])] == [PROMISE, SECOND_PROMISE]
      and not machine.events("wait_ended")
      and machine.events("message_sent")[-1]["step"] == "escalate",
      (recheck_facts.get("sentences"), machine.events("wait_ended")))

machine = promise_sent_on_rule_five_wait(PROMISE_SEND_FAILS)
machine.script(rechecked(True))
machine.run(16)
check("re-check: a wait a rule 5 message opened, whose only rule 2 message failed to send, is "
      "re-checked and ends when its sentence is backed",
      [event.get("sentences") for event in machine.events("wait_ended")] == [[PROMISE]],
      machine.events("wait_ended"))

machine = Machine()
machine.seat("alpha", [user("go"), assistant(PROMISE), turn_end()])
machine.script(sent_ok())
machine.run(0)
machine.log.write_text("".join(json.dumps(event) + "\n" for event in machine.events()
                               if event["event"] != "promise_message"))
machine.append("alpha", cross_session(machine.events("message_sent")[-1]["text"], at(0.5)),
               assistant(HOLD_SENTENCE, at(1)), turn_end(at(1)))
machine.script(PROMISE_SEND_FAILS)
machine.run(7)
machine.script(sent_ok())
machine.run(16)
check("re-check: a wait holding a rule 2 message whose sentences the log lacks, and a later failed "
      "one, is not re-checked, and the escalation is sent",
      len(machine.claude_calls()) == 1 and not machine.events("wait_ended")
      and machine.events("message_sent")[-1]["step"] == "escalate",
      (machine.claude_calls(), machine.events("wait_ended")))

machine = Machine()
machine.seat("alpha", [user("go"), assistant(OPENING_PULL_REQUEST), turn_end()])
machine.script(rechecked(False), sent_ok())
machine.run(0)
machine.append("alpha", cross_session(machine.events("message_sent")[-1]["text"], at(0.5)),
               assistant("Recorded.", at(1)), turn_end(at(1)))
machine.script({"answer": {"sentences": [{"index": 0, "backed": True}]}}, sent_ok())
code, output = machine.run(16)
check("the re-check judge finds every sentence backed but gives no reason: a judge failure, and the "
      "escalation is sent",
      code == 1 and "Traceback" not in output and not machine.events("wait_ended")
      and machine.owner_task_subjects()
      == ["Idle sweep: a headless agent-session failed: the judge's answer could not be used"]
      and machine.events("message_sent")[-1]["step"] == "escalate",
      (code, output[-300:], machine.events("wait_ended"), machine.owner_tasks()))

STANDING_RULE_BACKED = ('A standing rule, such as "from now on" or "Noted", is backed by the hook or '
                        "test that enforces it, or by a task to build one together with a proposal "
                        "to the user; a memory never backs it.")
machine = Machine()
machine.seat("alpha", [user("go"), assistant(OPENING_PULL_REQUEST), turn_end()])
machine.script(rechecked(False), sent_ok())
machine.run(0)
rule_2_prompt = machine.claude_calls()[0]["prompt"]
machine.append("alpha", cross_session(machine.events("message_sent")[-1]["text"], at(0.5)),
               assistant("Recorded.", at(1)), turn_end(at(1)))
machine.script(rechecked(True))
machine.run(16)
recheck_prompt = machine.claude_calls()[0]["prompt"]
check("the rule 2 judge and the re-check are given one definition of backed, so one compliant action "
      "does not back a standing rule",
      STANDING_RULE_BACKED in rule_2_prompt and STANDING_RULE_BACKED in recheck_prompt
      and "now follows it" not in recheck_prompt, recheck_prompt[:900])

# The rule for an announced action that both rule 2 judges must be given word for word.
ANNOUNCED_ACTION_BACKED = (
    'An announced action, such as "Next I\'m starting the pull request", is backed when a tool call '
    "in the same turn, before or after the sentence, or a later one does the action, or a background "
    "task it started is still running; when the action is to tell the user something, by a text "
    "message in the same turn or a later one that tells it; and when the agent-seat put the action "
    "off, by an open task whose prerequisites or blockedBy name what the action waits on.")
check("the rule 2 judge and the re-check are given the user's rule for an announced action word for "
      "word, and told that a tool call marked failed backs nothing",
      all(ANNOUNCED_ACTION_BACKED in prompt and "A tool call marked failed did not do its action"
          in prompt for prompt in (rule_2_prompt, recheck_prompt)), rule_2_prompt[:1500])

# The first judge sees the agent-seat's text messages of the sentence's turn: one that already told
# the user what the sentence announced can back it.
TOLD_THE_USER = "The test failed: test_merge_gate exits 1 on an empty description."
machine = Machine()
machine.seat("alpha", [user("go", at(-12)), assistant(TOLD_THE_USER, at(-11.9)),
                       assistant(tool=("Bash", {"command": "false"}), when=at(-11.8), tool_id="t-false"),
                       {"type": "user", "timestamp": at(-11.7), "message": {"role": "user", "content": [
                           {"type": "tool_result", "tool_use_id": "t-false", "is_error": True,
                            "content": "Exit code 1"}]}},
                       assistant("Next I'll tell the user the test failed.", at(-11.6)),
                       turn_end(at(-11.5))])
machine.script(rechecked(True))
machine.run(0)
facts = first_judge_facts(machine.claude_calls())
check("the first rule 2 judge is handed the text messages and tool calls of the sentence's turn, a "
      "failed call marked failed",
      [item["text"] for item in facts.get(
          "assistant_text_messages_since_start_of_earliest_turn_with_sentence_to_judge", [])]
      == [TOLD_THE_USER, "Next I'll tell the user the test failed."]
      and [(call["name"], call.get("failed")) for call in facts.get(
          "tool_calls_since_start_of_earliest_turn_with_sentence_to_judge", [])]
      == [("Bash", True)], facts)

# A judge's answer of the wrong shape is a judge failure, never a crash.
for case, answer in (
        ("an index missing beside an integer one",
         {"sentences": [{"index": 0, "backed": True, "reason": "r"}, {"backed": True, "reason": "r"}]}),
        ("a null index beside an integer one",
         {"sentences": [{"index": 0, "backed": True, "reason": "r"},
                        {"index": None, "backed": True, "reason": "r"}]}),
        ("a string index beside an integer one",
         {"sentences": [{"index": 0, "backed": True, "reason": "r"},
                        {"index": "1", "backed": True, "reason": "r"}]}),
        ("the right indexes and an item that is not an object",
         {"sentences": [{"index": 0, "backed": True, "reason": "r"}, "backed"]}),
        ("sentences null", {"sentences": None})):
    machine = Machine()
    machine.seat("alpha", [user("go"), assistant(OPENING_PULL_REQUEST), turn_end()])
    machine.script({"answer": answer})
    code, output = machine.run(0)
    check(f"a rule 2 judge whose answer has {case}: a judge failure, exit 1, no traceback",
          code == 1 and "Traceback" not in output
          and "the judge's answer does not give backed" in
          (machine.events("headless_failed") or [{}])[0].get("problem", "")
          and not machine.events("message_sent"),
          (code, output[-500:], machine.events("headless_failed")))

# Another agent-seat's headless agent-session breaks this one's task list after the verdict's read.
machine = Machine()
machine.seat("beta", [user("go"), assistant(OPENING_PULL_REQUEST), turn_end()], session="s-beta")
(machine.tasks / "nedsnodes-beta-tasks").mkdir()
(machine.tasks / "nedsnodes-beta-tasks" / "7.json").write_text(json.dumps(
    {"id": "7", "subject": "waits on task 9", "status": "pending", "blocks": [], "blockedBy": ["9"]}))
machine.script(rechecked(False), sent_ok("beta"))
machine.run(0)
machine.append("beta", cross_session(machine.events("message_sent")[-1]["text"], at(0.5)),
               assistant("Recorded.", at(1)), turn_end(at(1)))
machine.seat("alpha", DONE_TURN)
machine.task("alpha", "1")
machine.script(dict(judged(False), overwrite=[str(machine.tasks / "nedsnodes-beta-tasks" / "bad.json"),
                                              "not json"]), rechecked(True), judged(False))
code, output = machine.run(16)
recheck_facts = first_judge_facts(machine.claude_calls()[1:])
check("re-check: the judge is handed the open waiting tasks the verdict read, with no second read of "
      "the task list",
      code == 0 and "Traceback" not in output
      and [task["id"] for task in recheck_facts.get("open_tasks_with_prerequisites_or_blocked_by", [])]
      == ["7"], (code, output[-300:], recheck_facts))

machine = Machine()
machine.seat("alpha", [user("go"), assistant(ANNOUNCED), turn_end()])
machine.script({"answer": {"sentences": [{"index": 0, "backed": True, "reason": "a test runs"}]}})
machine.run(0)
calls = machine.claude_calls()
check("rule 2 judged backed: the judge has no tool, and rules 3 to 5 decide (rule 4: no wake)",
      len(calls) == 1 and calls[0]["argv"][calls[0]["argv"].index("--tools") + 1] == ""
      and "--allowedTools" not in calls[0]["argv"] and not machine.events("message_sent"), calls)
machine = Machine()
machine.seat("alpha", [user("go"), assistant(ANNOUNCED, when="2026-11-02T11:48:00Z"), turn_end()])
machine.script({"answer": {"sentences": [{"index": 0, "backed": False, "reason": "no call"}]}},
               sent_ok())
machine.run(0)
calls = machine.claude_calls()
check("rule 2 judged unbacked: a second headless agent-session sends the announced-action line",
      len(calls) == 2 and 'You said "I\'m starting the PR 1633 work now." 12 minutes ago and have '
      "not done it. Do it now, or tell the user why not." in calls[1]["prompt"], calls)
TOLD_AT_START = "I told the user the PR 1633 work is starting."
LONG_TURN_TEXT = f"{TOLD_AT_START} {LONG_TEXT * 3} {ANNOUNCED}"
machine = Machine()
machine.seat("alpha", [user("go"), assistant(LONG_TURN_TEXT), turn_end()])
machine.script({"answer": {"sentences": [{"index": 0, "backed": True, "reason": "told"}]}})
machine.run(0)
calls = machine.claude_calls()
prompt = calls[0]["prompt"] if calls else "\n{}"
judge_facts = json.loads(prompt[prompt.rindex("\n{") + 1:])
handed = [item["text"] for item in judge_facts.get(
    "assistant_text_messages_since_start_of_earliest_turn_with_sentence_to_judge", [])]
check("rule 2: a text longer than the judge is handed reaches it with its start and its end",
      len(handed) == 1 and handed[0].startswith(TOLD_AT_START) and handed[0].endswith(ANNOUNCED)
      and "\n[...]\n" in handed[0] and len(handed[0]) < len(LONG_TURN_TEXT)
      and judge_facts["last_turn_ending_message"]["text"] == handed[0], handed)
machine = Machine()
machine.seat("alpha", [user("go"), assistant(f"{PROMISE} {ANNOUNCED}"), turn_end()])
machine.script({"answer": {"sentences": [{"index": 0, "backed": True, "reason": "a test runs"}]}},
               sent_ok())
machine.run(0)
calls = machine.claude_calls()
prompt = calls[0]["prompt"] if calls else "\n{}"
judge_facts = json.loads(prompt[prompt.rindex("\n{") + 1:])
check("rule 2, a promise code finds unbacked and an announced action to judge: the judge gets only "
      "the announced action, and the message names only the promise",
      [item["sentence"] for item in judge_facts.get("sentences", [])] == [ANNOUNCED]
      and len(calls) == 2 and "You promised \"I'll report when PR 927 merges.\"" in calls[1]["prompt"]
      and ANNOUNCED not in calls[1]["prompt"], calls)
for case, answer in (("an index missing", {"sentences": []}),
                     ("backed not true or false", {"sentences": [{"index": 0, "backed": "yes",
                                                                  "reason": "r"}]})):
    machine = Machine()
    machine.seat("alpha", [user("go"), assistant(ANNOUNCED), turn_end()])
    machine.script({"answer": answer})
    code, _ = machine.run(0)
    check(f"rule 2, the judge's answer with {case}: a task for reboot-test, no user-alert, exit 1, "
          "nothing sent",
          code == 1 and not machine.alerts() and machine.owner_task_subjects()
          == ["Idle sweep: a headless agent-session failed: the judge's answer could not be used"]
          and not machine.events("message_sent"), (code, machine.alerts(), machine.owner_tasks()))

# --- a prerequisite the GitHub budget left unasked ----------------------------------------------
machine = Machine()
machine.seat("alpha", DONE_TURN)
machine.task("alpha", "1")
task_file = machine.tasks / "nedsnodes-alpha-tasks" / "1.json"
task_file.write_text(json.dumps({**json.loads(task_file.read_text()),
                                 "metadata": {"prerequisites": [{"pr_merged": 50}]}}))
machine.script(judged(False, reason="r"))
code, output = machine.run(0, github_budget_spent=True)
skipped = [{"kind": "pr_merged", "number": 50}]
check("a prerequisite the GitHub budget left unasked: logged by name",
      code == 0 and [(event["agent_seat"], event["conditions"]) for event in
                     machine.events("github_conditions_skipped_for_budget")] == [("alpha", skipped)],
      (code, output, machine.events()))
calls, judge_facts = rule_five_judge_facts(machine)
check("a prerequisite the GitHub budget left unasked: the rule 5 judge is called, is not told of "
      "the skip, and is told of no open task nothing holds",
      len(calls) == 1 and "github_conditions_skipped_for_budget" not in judge_facts
      and judge_facts.get("open_tasks_nothing_holds") == [], (calls, judge_facts))

machine = Machine()
machine.seat("alpha", DONE_TURN)
machine.script()
machine.run(0)
machine.seat("alpha", DONE_TURN, session="s-2")
machine.script()
code, output = machine.run(20, runner_source=FIRST_READ_ONLY_BUDGET_SKIP_RUNNER)
check("a budget skip the first read found and a new agent-session's reread did not: still logged",
      code == 0 and [(event["agent_seat"], event["conditions"]) for event in
                     machine.events("github_conditions_skipped_for_budget")] == [("alpha", skipped)],
      (code, output, machine.events()))

# --- rule 1: a usage limit ------------------------------------------------------------------------
RESET_PASSED = int(START.timestamp()) - 60
machine = Machine()
machine.seat("alpha", [user("go"), assistant("working", when="2026-11-02T10:00:00Z"), user("more"),
                       usage_limit(RESET_PASSED)])
machine.task("alpha", "1")
machine.script(sent_ok())
machine.run(0)
calls = machine.claude_calls()
check("rule 1, the reset time passed: one wake with code's text",
      len(calls) == 1 and "The usage limit that stopped you has ended: its reset time has passed."
      in calls[0]["prompt"] and [event["step"] for event in machine.events("message_sent")]
      == ["limit_wake"], calls)
machine.script()
machine.run(3)
check("rule 1: no second wake for the same limit record", not machine.claude_calls(),
      machine.claude_calls())
machine.script(judged(False))
machine.run(6)
check("rule 1: still idle 5 minutes after the wake, rules 2 to 5 decide (rule 5's judge)",
      len(machine.claude_calls()) == 1 and machine.events("judge_answer"), machine.events())

machine = Machine()
machine.seat("alpha", [user("go"), usage_limit(RESET_PASSED + 86400)])
machine.script()
machine.run(0)
check("rule 1, the reset time not passed: no wake, the limit's account recorded",
      not machine.claude_calls()
      and [event["account"] for event in machine.events("limit_seen")] == ["account-1"],
      machine.events())

# --- the account changes ---------------------------------------------------------------------------
machine = Machine()
machine.seat("alpha", [user("go"), usage_limit(RESET_PASSED + 86400)])
machine.seat("beta", DONE_TURN, session="s-beta")
machine.script()
machine.run(0)
check("the first account seen is only recorded",
      not machine.claude_calls() and [event["account"] for event in machine.events("account_seen")]
      == ["account-1"], machine.events())
machine.claude_json.write_text("{}")
machine.run(1)
check("a missing account is not a change", not machine.claude_calls(), machine.claude_calls())
machine.account("account-2")
machine.script({"sends": [send_to("alpha"), send_to("beta")], "answer": {"sent": True, "reason": "r"}})
code, _ = machine.run(2)
calls = machine.claude_calls()
check("an account change: one headless agent-session sends the notice to every agent-seat",
      code == 0 and len(calls) == 1
      and f"alpha [{listed_ref(socket_path('alpha'))}], beta [{listed_ref(socket_path('beta'))}]"
      in calls[0]["prompt"]
      and "The claude.ai account logged in on ned-box changed at" in calls[0]["prompt"]
      and sorted(event["agent_seat"] for event in machine.events("message_sent")) == ["alpha", "beta"],
      (code, calls))
check("an account change: the notice is the wake of an agent-seat idle at a limit, no second one",
      [event["agent_seat"] for event in machine.events("limit_wake")] == ["alpha"]
      and len(calls) == 1, machine.events("limit_wake"))
check("an account change: the notice's sender is told that the do-not-reply sentence is part of "
      "the message", KEEP_IT in calls[0]["prompt"].replace("\n", " "), calls)
machine.script()
machine.run(3)
check("the account change is noticed once", not machine.claude_calls(), machine.claude_calls())

machine = Machine()
machine.seat("alpha", [user("go"), usage_limit(RESET_PASSED + 86400)])
machine.script()
machine.run(0)
machine.claude_json.write_text("{not json")
code, _ = machine.run(1)
check("an unreadable ~/.claude.json is logged as a read failure, not a change",
      not machine.claude_calls() and machine.events("read_failure")
      and len(machine.events("account_seen")) == 1, machine.events())
code, _ = machine.run(4)
check("an unreadable ~/.claude.json still unreadable minutes later: a task for reboot-test, no "
      "user-alert",
      not machine.alerts() and len(machine.owner_tasks()) == 1
      and machine.owner_task_subjects()[0].startswith("Idle sweep: cannot read what it needs: "),
      (machine.alerts(), machine.owner_tasks()))
machine.run(5)
check("a read failure gets one task while it is open",
      not machine.alerts() and len(machine.owner_tasks()) == 1, machine.owner_tasks())

machine = Machine()
machine.seat("alpha", [user("go"), usage_limit(RESET_PASSED + 86400)])
machine.script()
machine.run(0)
machine.account("account-2")
machine.script({"answer": {"sent": True, "reason": "r"}})
machine.run(1)
check("a notice the headless agent-session did not send: no second wake at the limit",
      len(machine.claude_calls()) == 1 and len(machine.events("limit_wake")) == 1, machine.events())
code, _ = machine.run(3)
check("a notice missing from a listed agent-seat's transcript: a task for reboot-test, exit 1",
      code == 1 and not machine.alerts() and machine.owner_task_subjects() == [DELIVERY_TASK_SUBJECT]
      and "its account notice message" in machine.owner_tasks()[0]["description"],
      (machine.alerts(), machine.owner_tasks()))

# --- a sender that sends a text other than the one code wrote --------------------------------------
# Every such case seen dropped the do-not-reply sentence and still reached the agent-seat.
SENT_TEXT_TASK_SUBJECT = "Idle sweep: a headless sender sent a text other than the one code wrote"
DROPPED = send_to("alpha", "@prompt-text-without-last-paragraph")


def owner_tasks(machine):
    return machine.owner_tasks()


machine = Machine()
machine.seat("alpha", DONE_TURN)
machine.handoff_put_off()
(machine.tasks / OWNER_TASKS / "7.json").write_text("{not json")
machine.script({"sends": [DROPPED], "answer": {"sent": True, "reason": "r"}})
code, output = machine.run(0)
differs = machine.events("sent_text_differs_from_code_text")
sent = machine.events("message_sent")
check("a sender that drops the do-not-reply sentence: no user-alert, no headless failure, exit 0",
      code == 0 and not machine.alerts() and not machine.events("headless_failed"),
      (code, output, machine.alerts()))
check("a sender that drops the do-not-reply sentence: the text code wrote and the text sent are logged",
      len(differs) == 1 and differs[0]["agent_seat"] == "alpha" and differs[0]["step"] == "nudge"
      and ends_with_do_not_reply_once(differs[0]["text"])
      and differs[0]["sent_text"] == differs[0]["text"].rsplit("\n\n", 1)[0], differs)
check("a sender that drops the do-not-reply sentence: the send is logged with the text sent, for the "
      "delivery check", len(sent) == 1 and sent[0]["text"] == differs[0]["sent_text"], sent)
tasks = owner_tasks(machine)
check("a sender that drops the do-not-reply sentence: reboot-test gets a pending task, past a task "
      "file that is not JSON",
      len(tasks) == 1 and tasks[0]["subject"] == SENT_TEXT_TASK_SUBJECT
      and tasks[0]["status"] == "pending" and str(machine.log) in tasks[0]["description"]
      and [event["task_id"] for event in machine.events("owning_agent_seat_task_opened")] == [8],
      (tasks, machine.events("owning_agent_seat_task_opened")))
machine.append("alpha", cross_session(sent[0]["text"], at(0.2)), assistant("On it.", at(0.3)),
               turn_end(at(0.4)))
machine.script()
code, _ = machine.run(2)
check("the text sent found in the agent-seat's transcript: no user-alert",
      [event["found"] for event in machine.events("delivery_checked")] == [True]
      and not machine.alerts(), (machine.events("delivery_checked"), machine.alerts()))
machine.script({"sends": [DROPPED], "answer": {"sent": True, "reason": "r"}})
machine.run(17)
check("a second difference while the task is open: logged, and no second task",
      len(machine.events("sent_text_differs_from_code_text")) == 2 and len(owner_tasks(machine)) == 1
      and len(machine.events("owning_agent_seat_task_opened")) == 1, owner_tasks(machine))
task_path = machine.tasks / OWNER_TASKS / "8.json"
task_path.write_text(json.dumps(dict(json.loads(task_path.read_text()), status="completed")))
machine.script({"sends": [DROPPED], "answer": {"sent": True, "reason": "r"}})
machine.handoff_put_off("s-2")
machine.seat("alpha", DONE_TURN, session="s-2")
machine.run(40)
check("a difference after the task is completed: a new task",
      [event["task_id"] for event in machine.events("owning_agent_seat_task_opened")
       if event["subject"] == SENT_TEXT_TASK_SUBJECT] == [8, 10],
      machine.events("owning_agent_seat_task_opened"))

machine = Machine()
machine.seat("alpha", DONE_TURN)
machine.handoff_put_off()
machine.owner_task_list.rmdir()
machine.script({"sends": [DROPPED], "answer": {"sent": True, "reason": "r"}})
code, _ = machine.run(0)
alerts = machine.alerts()
check("a difference whose task cannot be written: one user-alert naming the error, without the "
      "claude -p remedy, exit 1",
      code == 1 and len(alerts) == 1 and "could not give reboot-test a task" in alerts[0]["title"]
      and "FileNotFoundError" in json.dumps(alerts[0]) and "claude -p" not in json.dumps(alerts[0])
      and len(machine.events("sent_text_differs_from_code_text")) == 1
      and len(machine.events("message_sent")) == 1, (code, alerts))

machine = Machine()
machine.seat("alpha", DONE_TURN)
machine.handoff_put_off()
machine.script({"sends": [DROPPED, send_to("beta")], "answer": {"sent": True, "reason": "r"}})
code, _ = machine.run(0)
failed = machine.events("headless_failed")
check("a difference beside a send to another entry: each goes to a task of its own, no user-alert",
      code == 1 and len(machine.events("sent_text_differs_from_code_text")) == 1
      and machine.owner_task_subjects() == [
          SENT_TEXT_TASK_SUBJECT, "Idle sweep: a headless agent-session failed: the sender's "
          "SendMessage calls were not the sends code asked for"]
      and len(failed) == 1 and failed[0]["problem"]
      == f"sent to 'beta [{listed_ref(socket_path('beta'))}]', which is not alpha"
      and not machine.alerts(), (failed, machine.alerts(), machine.owner_tasks()))

machine = Machine()
machine.seat("alpha", DONE_TURN)
machine.seat("beta", DONE_TURN, session="s-beta")
machine.run(0)
machine.account("account-2")
machine.script({"sends": [DROPPED, send_to("beta")], "answer": {"sent": True, "reason": "r"}})
code, _ = machine.run(1)
differs = machine.events("sent_text_differs_from_code_text")
sent = {event["agent_seat"]: event["text"] for event in machine.events("message_sent")}
check("an account notice sent to one agent-seat with another text: logged, a task, no user-alert, "
      "and each agent-seat's send logged with the text it was sent",
      code == 0 and not machine.alerts() and [event["agent_seat"] for event in differs] == ["alpha"]
      and differs[0]["step"] == "account_notice" and len(owner_tasks(machine)) == 1
      and sent["alpha"] == differs[0]["sent_text"] and sent["beta"] == differs[0]["text"],
      (code, machine.alerts(), differs, sent))

machine = Machine()
machine.seat("alpha", DONE_TURN)
machine.seat("beta", DONE_TURN, session="s-beta")
machine.run(0)
machine.account("account-2")
machine.script({"sends": [send_to("beta"), DROPPED], "answer": {"sent": True, "reason": "r"}})
code, _ = machine.run(1)
differs = machine.events("sent_text_differs_from_code_text")
sent = {event["agent_seat"]: event["text"] for event in machine.events("message_sent")}
check("an account notice whose last send went to another agent-seat: each agent-seat's send is "
      "logged with the text sent to it, not the last send's text",
      code == 0 and [event["agent_seat"] for event in differs] == ["alpha"]
      and sent["alpha"] == differs[0]["sent_text"] and sent["beta"] == differs[0]["text"],
      (code, differs, sent))

# "~" sorts after every letter, so the first message sorts after the text code wrote.
machine = Machine()
machine.seat("alpha", DONE_TURN)
machine.handoff_put_off()
machine.script({"sends": [send_to("alpha", "~ another text"), send_to("alpha")],
                "answer": {"sent": True, "reason": "r"}})
code, _ = machine.run(0)
differs = machine.events("sent_text_differs_from_code_text")
sent = machine.events("message_sent")
check("two sends to one agent-seat, the first with a text that sorts after code's: the first is "
      "logged as a difference, and the send is logged with the last send's text",
      code == 0 and [event["sent_text"] for event in differs] == ["~ another text"]
      and len(sent) == 1 and sent[0]["text"] == differs[0]["text"], (code, differs, sent))


def owner_task_file_write(machine, name, subject, status="pending"):
    (machine.tasks / OWNER_TASKS / name).write_text(json.dumps({"subject": subject, "status": status}))


machine = Machine()
machine.seat("alpha", DONE_TURN)
machine.handoff_put_off()
owner_task_file_write(machine, "1.json", "A" + SENT_TEXT_TASK_SUBJECT)
owner_task_file_write(machine, "2.json", SENT_TEXT_TASK_SUBJECT + " too")
machine.script({"sends": [DROPPED], "answer": {"sent": True, "reason": "r"}})
machine.run(0)
check("open tasks whose subjects sort before and after the sent-text task's: a new task",
      [event["task_id"] for event in machine.events("owning_agent_seat_task_opened")] == [3],
      (owner_tasks(machine), machine.events("owning_agent_seat_task_opened")))

machine = Machine()
machine.seat("alpha", DONE_TURN)
machine.handoff_put_off()
for name in ("1.json", "2.json"):
    (machine.tasks / OWNER_TASKS / name).write_text("")
# The program reads the task files in the order glob lists them, which the file system sets.
first, second = (machine.tasks / OWNER_TASKS).glob("*.json")
first.write_text("{not json")
owner_task_file_write(machine, second.name, SENT_TEXT_TASK_SUBJECT)
machine.script({"sends": [DROPPED], "answer": {"sent": True, "reason": "r"}})
machine.run(0)
check("a task file that is not JSON listed before the open sent-text task: no second task",
      not machine.events("owning_agent_seat_task_opened") and len(owner_tasks(machine)) == 1,
      (owner_tasks(machine), machine.events("owning_agent_seat_task_opened")))

machine = Machine()
machine.seat("alpha", DONE_TURN)
machine.handoff_put_off()
machine.script(sent_ok())
machine.run(0)
check("the sender is told that the do-not-reply sentence is part of the message",
      KEEP_IT in machine.claude_calls()[0]["prompt"].replace("\n", " "), machine.claude_calls())


# --- which entry is the agent-seat's: the ref of the agent-session its supervisor launched last ----
def reached(to, prepare=lambda machine: None, session="s-1"):
    """Run rule 3 for alpha with one send to `to`; return the machine."""
    machine = Machine()
    machine.seat("alpha", DONE_TURN, session=session)
    machine.handoff_put_off(session)
    prepare(machine)
    machine.script({"sends": [{"to": to, "message": "@prompt-text"}],
                    "answer": {"sent": True, "reason": "sent"}})
    machine.run(0)
    return machine


def counted(machine):
    return bool(machine.events("message_sent")) and not machine.events("headless_failed")


# After a session-handoff, a helper the previous agent-session started in the agent-seat's tmux
# pane, such as a reviewer, can still run; it is older than the successor and may share its name.
HELPER_SOCKET = "/run/user/1000/cc-socks/4100.sock"
SUCCESSOR_SOCKET = "/run/user/1000/cc-socks/4200.sock"


def helper_and_successor(machine):
    machine.session_record("4100", "s-1", HELPER_SOCKET, name="alpha", tmux="alpha:@0.%0",
                           startedAt=1_000)
    machine.session_record("alpha", "s-2", SUCCESSOR_SOCKET, name="alpha", tmux="alpha:@0.%0",
                           startedAt=2_000)


machine = reached(f"alpha [{listed_ref(HELPER_SOCKET)}]", helper_and_successor, session="s-2")
check("after a session-handoff, a send to an older helper named after the agent-seat does not "
      "count: the agent-seat is the agent-session whose id the supervisor launched last",
      not machine.events("message_sent") and any(
          "no SendMessage to alpha succeeded" in event["problem"]
          for event in machine.events("headless_failed")), machine.events())
machine = reached(f"alpha [{listed_ref(SUCCESSOR_SOCKET)}]", helper_and_successor, session="s-2")
check("after a session-handoff, a send to the successor counts",
      counted(machine), machine.events())
check("the sender is told the successor's ref, not the helper's",
      f"[{listed_ref(SUCCESSOR_SOCKET)}]" in machine.claude_calls()[0]["prompt"]
      and listed_ref(HELPER_SOCKET) not in machine.claude_calls()[0]["prompt"],
      machine.claude_calls())

# MD-skills-2's entry, as ListAgents listed it on ned-box for the agent-session whose socket was this
# path: the ref is computed as Claude Code computes it.
machine = reached("Cpc [bc3857]", lambda machine: machine.session_record(
    "alpha", "s-1", "/run/user/1000/cc-socks/3996201.sock"))
check("a renamed agent-session counts by its ref, whatever its name", counted(machine),
      machine.events())

for to, case in (("alpha [aaaaaa]", "a send to the agent-seat's name with another ref"),
                 ("alpha", "a send to the agent-seat's name with no ref")):
    machine = reached(to)
    check(f"{case} does not count", not machine.events("message_sent") and any(
        "sent to" in event["problem"] for event in machine.events("headless_failed")),
        machine.events())


def unreadable_records_first(machine):
    records = machine.home / ".claude" / "sessions"
    (records / "0-a-directory.json").mkdir()
    (records / "1-not-json.json").write_text("{not json")
    (records / "2-not-an-object.json").write_text("[]")


machine = reached(send_to("alpha")["to"], unreadable_records_first)
check("session records that cannot be read are skipped, and the agent-seat's is found",
      counted(machine), machine.events())

for case, breaks in (
        ("no session record", lambda machine: (
            machine.home / ".claude" / "sessions" / "alpha.json").unlink()),
        ("its session record gives no socket path",
         lambda machine: machine.session_record("alpha", "s-1", None))):
    machine = Machine()
    machine.seat("alpha", DONE_TURN)
    machine.handoff_put_off()
    breaks(machine)
    machine.script(sent_ok())
    code, _ = machine.run(0)
    check(f"{case} has the id the supervisor launched last: no sender is started, and a "
          "user-alert, exit 1",
          code == 1 and not machine.claude_calls() and not machine.events("message_sent")
          and [event["session_id"] for event in machine.events("agent_seat_entry_not_found")]
          == ["s-1"] and [alert["title"] for alert in machine.alerts()]
          == ["The idle sweep found no running agent-session of alpha"],
          (code, machine.claude_calls(), machine.events(), machine.alerts()))

machine = Machine()
machine.seat("alpha", DONE_TURN)
machine.seat("beta", DONE_TURN, session="s-beta")
machine.run(0)
(machine.home / ".claude" / "sessions" / "beta.json").unlink()
machine.account("account-2")
machine.script(sent_ok())
code, _ = machine.run(1)
calls = machine.claude_calls()
check("an account notice for an agent-seat with no running agent-session goes to the others only, "
      "and that agent-seat is alerted",
      code == 1 and len(calls) == 1 and "beta" not in calls[0]["prompt"].split("----------")[0]
      and [event["agent_seat"] for event in machine.events("message_sent")] == ["alpha"]
      and [event["agent_seat"] for event in machine.events("agent_seat_entry_not_found")]
      == ["beta"], (code, calls, machine.events()))

machine = Machine()
machine.seat("alpha", DONE_TURN)
machine.run(0)
(machine.home / ".claude" / "sessions" / "alpha.json").unlink()
machine.account("account-2")
machine.script(sent_ok())
code, _ = machine.run(1)
check("an account notice when no agent-seat has a running agent-session: no sender is started",
      code == 1 and not machine.claude_calls() and not machine.events("message_sent")
      and len(machine.events("agent_seat_entry_not_found")) == 1, (code, machine.events()))

# --- headless agent-sessions that fail --------------------------------------------------------------
FAILURES = (
    ("exits nonzero", {"exit": 1}, "claude exited 1"),
    ("gives no result event", {"garbage": True}, "no result event"),
    ("reports an error", {"result": {"subtype": "error_during_execution", "is_error": True,
                                     "result": "boom"}}, "claude reported an error"),
    ("gives no JSON answer", {"result": {"subtype": "success", "is_error": False}},
     "no JSON answer"),
    ("sends to another entry", {"sends": [send_to("beta")], "answer": {"sent": True, "reason": "r"}},
     f"sent to 'beta [{listed_ref(socket_path('beta'))}]'"),
    ("has its send fail", {"sends": [send_to("alpha", is_error=True)],
                           "answer": {"sent": False, "reason": "r"}}, "no SendMessage to alpha"),
    ("runs past its time", {"sleep": 5, "answer": {"sent": True, "reason": "r"}}, "stopped after"),
    ("is killed by a signal", {"signal": True, "answer": {"sent": True, "reason": "r"}},
     "claude exited -15"),
    ("ends without success", {"result": {"subtype": "error_max_turns", "is_error": False,
                                         "structured_output": {"sent": True, "reason": "r"}}},
     "claude reported an error"),
    ("ends with a result of an unknown kind",
     {"result": {"subtype": "unknown_subtype", "is_error": False,
                 "structured_output": {"sent": True, "reason": "r"}}}, "claude reported an error"),
    ("reports an error on a result marked success",
     {"result": {"subtype": "success", "is_error": True,
                 "structured_output": {"sent": True, "reason": "r"}}}, "claude reported an error"),
)
# The error text keeps the end of stderr, the end of stdout, or the start of the result's text.
EXACT_FAILURES = (
    ("exits nonzero with a long stderr", {"exit": 1, "stderr": LONG_TEXT},
     f"claude exited 1: {LONG_TEXT[-500:]}"),
    ("gives a long output with no result event", {"garbage": LONG_TEXT},
     f"claude gave no result event: {(LONG_TEXT + chr(10))[-500:]!r}"),
    ("reports a long error", {"result": {"subtype": "error_during_execution", "is_error": True,
                                         "result": LONG_TEXT}},
     f"claude reported an error: {LONG_TEXT[:500]}"),
)
for case, answer, words in FAILURES + EXACT_FAILURES:
    machine = Machine()
    machine.seat("alpha", DONE_TURN)
    machine.handoff_put_off()
    machine.script(answer)
    # Only the case that runs past its time gets the 1-second limit: under load, starting the fake
    # claude alone can take a second, which would turn any other case into a stop.
    code, output = machine.run(0, *(("--headless-timeout-seconds", "1")
                                    if case == "runs past its time" else ()))
    failed = machine.events("headless_failed")
    exact = (case, answer, words) in EXACT_FAILURES
    tasks = machine.owner_tasks()
    check(f"a sender that {case}: logged, a task for reboot-test, no user-alert, exit 1, no "
          "delivery check pending",
          code == 1 and len(failed) == 1
          and (failed[0]["problem"] == words if exact else words in failed[0]["problem"])
          and not machine.alerts() and len(tasks) == 1
          and tasks[0]["subject"].startswith("Idle sweep: a headless agent-session failed: ")
          and failed[0]["problem"] in tasks[0]["description"]
          and not machine.events("message_sent"),
          (code, output, failed, machine.alerts(), tasks))
    if case == "exits nonzero":
        machine.script({"exit": 1})
        machine.run(1)
        check("a failed send is not retried every minute: the wait goes on to its next step",
              not machine.claude_calls() and len(machine.owner_tasks()) == 1, machine.claude_calls())

machine = Machine()
machine.seat("alpha", DONE_TURN)
machine.handoff_put_off()
code, _ = machine.run(0, path_has_fake=False)
check("claude that cannot be started: a user-alert, exit 1",
      code == 1 and "could not start claude" in machine.events("headless_failed")[0]["problem"],
      machine.events("headless_failed"))

for case, answer in (("send with no message", judged(True, "  ")),
                     ("send not true or false", judged("yes", "hi")),
                     ("no message field", {"answer": {"send": False, "reason": "r"}})):
    machine = Machine()
    machine.seat("alpha", DONE_TURN)
    machine.task("alpha", "1")
    machine.script(answer)
    code, _ = machine.run(0)
    check(f"a rule 5 judge whose answer has {case}: a user-alert, exit 1, no wait, nothing sent",
          code == 1 and "the judge's answer does not give send" in
          machine.events("headless_failed")[0]["problem"] and len(machine.claude_calls()) == 1
          and not machine.events("wait_step") and machine.events("judge_answer")[0]["send"] is False,
          machine.events())

# --- one cause of a headless failure, met again the same day with other text from claude --------
def usage_limit_exit(uuid, duration_ms):
    """claude at a usage limit, as ned-box's claude gives it: exit 1 after a result event whose
    reset time, ids and duration differ from one invocation to the next."""
    return {"exit": 1, "result": {
        "subtype": "success", "is_error": True, "api_error_status": 429,
        "api_error": "usage_limit_reached",
        "result": "You've hit your weekly limit · resets Nov 16, 8pm (America/Los_Angeles)",
        "duration_ms": duration_ms, "uuid": uuid}}


machine = Machine()
machine.seat("alpha", DONE_TURN)
machine.task("alpha", "1")
machine.script(usage_limit_exit("34551553-ce2f-4bed-88d6-09449375602d", 394))
machine.run(0)
machine.script(usage_limit_exit("c28e3474-6909-42c5-a3e7-fc096dd93dfe", 402))
code, _ = machine.run(16)
problems = [event["problem"] for event in machine.events("headless_failed")]
check("one usage limit with no transcript to read its reset time from, failing the judge twice, "
      "with different text from claude each time: both failures logged, one task, no pause",
      code == 1 and len(problems) == 2 and problems[0] != problems[1] and not machine.alerts()
      and machine.owner_task_subjects()
      == ["Idle sweep: a headless agent-session failed: claude exited 1: usage_limit_reached"]
      and not machine.events("headless_usage_limit_pause"),
      (code, problems, machine.alerts(), machine.owner_tasks()))
machine.script({"exit": 1, "stderr": "Invalid API key · Please run /login"})
machine.run(32)
check("another cause for the same agent-seat: a second task",
      len(machine.events("headless_failed")) == 3 and len(machine.owner_tasks()) == 2
      and not machine.alerts(), machine.owner_tasks())

USAGE_LIMIT_TASK_SUBJECT = "Idle sweep: a headless agent-session failed: claude exited 1: usage_limit_reached"


def machine_with_one_seat(records):
    machine = Machine()
    machine.seat("alpha", records)
    return machine


def account_changed_machine():
    machine = machine_with_one_seat(DONE_TURN)
    machine.run(0)
    machine.account("account-2")
    return machine


for path, machine, seat, start_minute in (
        ("a sender of a rule 2 message",
         machine_with_one_seat([user("go"), assistant(PROMISE), turn_end()]), "alpha", 0),
        ("the rule 2 judge",
         machine_with_one_seat([user("go"), assistant(ANNOUNCED), turn_end()]), "alpha", 0),
        ("the sender of the account-change notice", account_changed_machine(), "alpha", 1)):
    machine.script(usage_limit_exit("34551553-ce2f-4bed-88d6-09449375602d", 394))
    code, _ = machine.run(start_minute)
    tasks = machine.owner_tasks()
    check(f"{path} at a usage limit: the task's subject is the cause code names",
          code == 1 and [task["subject"] for task in tasks] == [USAGE_LIMIT_TASK_SUBJECT]
          and f"for the agent-seat {seat}," in tasks[0]["description"], (code, tasks))

# --- a headless agent-session at a usage limit whose reset time its transcript carries -------------
RESET_IN_AN_HOUR = int(START.timestamp()) + 3600


def usage_limit_exit_with_transcript(resets_at, session_id="headless-1"):
    """claude at a usage limit, with the transcript Claude Code writes for the headless
    agent-session: its usage-limit record carries the reset time, when given, in quotaLimits."""
    record = usage_limit(resets_at)
    if resets_at is None:
        del record["quotaLimits"]
    return dict(usage_limit_exit("34551553-ce2f-4bed-88d6-09449375602d", 394),
                session_id=session_id, transcript=json.dumps(record) + "\n")


def two_seats_with_open_tasks():
    machine = Machine()
    # Each agent-seat has its own agent-session: the sweep finds an entry by its session id.
    for seat, session in (("alpha", "s-1"), ("beta", "s-beta")):
        machine.seat(seat, DONE_TURN, session=session)
        machine.task(seat, "1")
    return machine


machine = two_seats_with_open_tasks()
machine.script(usage_limit_exit_with_transcript(RESET_IN_AN_HOUR))
code, output = machine.run(0)
pauses = machine.events("headless_usage_limit_pause")
check("a judge at a usage limit whose reset time its transcript carries: the failure is logged, "
      "a pause until the reset time, no task, no user-alert",
      len(machine.events("headless_failed")) == 1 and [event["resets_at"] for event in pauses]
      == [at(60)] and not machine.owner_tasks() and not machine.alerts(),
      (code, output, machine.events(), machine.owner_tasks()))
check("the pause holds in the same invocation: the next agent-seat's judge is not started",
      len(machine.claude_calls()) == 1, machine.claude_calls())
machine.script(judged(False), judged(False))
code, _ = machine.run(30)
check("the pause holds at the next invocations, before the reset time: no headless agent-session, "
      "exit 0", code == 0 and not machine.claude_calls() and len(machine.events("headless_failed")) == 1,
      (code, machine.claude_calls()))
machine.script(judged(False), judged(False))
code, _ = machine.run(60)
check("the reset time passed: the judges run again",
      code == 0 and len(machine.claude_calls()) == 2, (code, machine.claude_calls()))

machine = two_seats_with_open_tasks()
machine.script(usage_limit_exit_with_transcript(RESET_IN_AN_HOUR))
machine.run(0)
machine.account("account-2")
machine.script({"sends": [send_to("alpha"), send_to("beta")], "answer": {"sent": True, "reason": "r"}},
               judged(False))
code, _ = machine.run(5)
calls = machine.claude_calls()
check("the account changed before the reset time: the pause ends, the notice is sent and the "
      "agent-seat not judged since is judged",
      code == 0 and len(calls) == 2 and "agent-seat beta has spent no tokens" in calls[1]["prompt"],
      (code, calls))

machine = Machine()
machine.seat("alpha", [user("go"), assistant(ANNOUNCED, when="2026-11-02T11:48:00Z"), turn_end()])
machine.script(usage_limit_exit_with_transcript(RESET_IN_AN_HOUR))
machine.run(0)
machine.script({"answer": {"sentences": [{"index": 0, "backed": False, "reason": "no call"}]}},
               sent_ok())
code, _ = machine.run(60)
calls = machine.claude_calls()
prompt = calls[0]["prompt"] if calls else "\n{}"
judge_facts = json.loads(prompt[prompt.rindex("\n{") + 1:])
check("a rule 2 judge at a usage limit with a reset time ahead: after the reset, the same sentence "
      "is judged and the agent-seat woken",
      code == 0 and [item["sentence"] for item in judge_facts.get("sentences", [])] == [ANNOUNCED]
      and len(calls) == 2 and len(machine.events("message_sent")) == 1, (code, calls))

machine = Machine()
machine.seat("alpha", [user("go"), assistant(PROMISE), turn_end()])
machine.script(sent_ok())
machine.run(0)
machine.script(rechecked(False), sent_ok())
machine.run(16)
machine.seat("beta", DONE_TURN)
machine.task("beta", "1")
machine.script(usage_limit_exit_with_transcript(RESET_IN_AN_HOUR))
machine.run(20)
machine.script()
machine.run(32)
check("a pause holds over a stuck wait: the user is still told, and no headless agent-session starts",
      len(machine.events("headless_usage_limit_pause")) == 1
      and [event["step"] for event in machine.events("wait_step")] == ["nudge", "escalate", "tell_user"]
      and any("after a nudge and an escalation" in alert["title"] for alert in machine.alerts())
      and not machine.claude_calls(),
      (machine.events("wait_step"), machine.alerts(), machine.claude_calls()))

machine = Machine()
machine.seat("alpha", [user("go"), assistant(PROMISE), turn_end()])
machine.script(sent_ok())
machine.run(0)
machine.append("alpha", cross_session("You promised", at(0.5)), assistant(SECOND_PROMISE, at(9)),
               turn_end(at(9)))
machine.script(rechecked(False), usage_limit_exit_with_transcript(RESET_IN_AN_HOUR), sent_ok())
code, _ = machine.run(16)
check("an escalation sender at a usage limit with a reset time ahead: a pause, no task, and the "
      "promise message due in the same step is not sent",
      len(machine.events("headless_usage_limit_pause")) == 1
      and USAGE_LIMIT_TASK_SUBJECT not in machine.owner_task_subjects()
      and len(machine.claude_calls()) == 2
      and [event["step"] for event in machine.events("message_sent")] == ["nudge"],
      (code, machine.events("headless_usage_limit_pause"), machine.owner_tasks(),
       machine.claude_calls()))
machine.script(sent_ok())
code, _ = machine.run(90)
check("after the reset, the promise message the escalation's pause held back is sent",
      code == 0 and [event["step"] for event in machine.events("message_sent")] == ["nudge", "nudge"]
      and "after lunch" in machine.events("message_sent")[-1]["text"],
      (code, machine.events("message_sent"), machine.claude_calls()))
groups = machine.events("rule_2_sentences_on_wait")
check("after the reset, the promise judged again is not logged on the wait a second time, and "
      "its message takes it off the wait",
      [group["sentences"] for group in groups] == [[SECOND_PROMISE]]
      and [event.get("records") for event in machine.events("promise_message")][-1:]
      == [groups[0]["records"]], (groups, machine.events("promise_message")))

machine = Machine()
machine.seat("alpha", [user("go"), assistant(PROMISE), turn_end()])
machine.script(sent_ok())
machine.run(0)
machine.append("alpha", cross_session("You promised", at(0.5)), assistant(ANNOUNCED, at(9)),
               turn_end(at(9)))
machine.script({"answer": {"sentences": [{"index": 0, "backed": True, "reason": "a test runs"}]}},
               rechecked(False), usage_limit_exit_with_transcript(RESET_IN_AN_HOUR))
checked_count_before_minute_16 = len(machine.events("checked"))
machine.run(16)
calls_before_reset = machine.claude_calls()
checked_before_reset = machine.events("checked")[checked_count_before_minute_16:]
machine.script()
code, _ = machine.run(90)
check("every sentence judged backed, then an escalation sender at a usage limit: the sentences and "
      "the check are logged, so no second judge is started after the reset",
      code == 0 and ANNOUNCED in [event["sentence"] for event in machine.events("sentence_checked")]
      and any(event["rule"] == 2 for event in checked_before_reset)
      and len(machine.events("headless_usage_limit_pause")) == 1 and len(calls_before_reset) == 3
      and not machine.claude_calls(),
      (code, machine.events("sentence_checked"), checked_before_reset, calls_before_reset,
       machine.claude_calls()))

machine = Machine()
machine.seat("alpha", [user("go"), assistant(PROMISE), turn_end()])
machine.script(sent_ok())
machine.run(0)
machine.append("alpha", cross_session("You promised", at(0.5)),
               assistant(ANNOUNCED, at(8), uuid="backed-record"),
               turn_end(at(8)), user("and again", at(8.5)),
               assistant(ANNOUNCED, at(9), uuid="unbacked-record"),
               turn_end(at(9)))
machine.script({"answer": {"sentences": [{"index": 0, "backed": True, "reason": "a test ran"},
                                         {"index": 1, "backed": False, "reason": "nothing ran"}]}},
               rechecked(False), usage_limit_exit_with_transcript(RESET_IN_AN_HOUR))
machine.run(16)
same_sentence_checked = [event for event in machine.events("sentence_checked")
                         if event["sentence"] == ANNOUNCED]
check("two turns end with the same sentence, one judged backed and one not, and a pause holds back "
      "the message: the backed record is logged and the unbacked one is not",
      [event["record_uuid"] for event in same_sentence_checked] == ["backed-record"],
      (same_sentence_checked, machine.claude_calls()))

machine = Machine()
machine.seat("alpha", [user("go"), assistant(PROMISE), turn_end()])
machine.script(sent_ok())
machine.run(0)
machine.append("alpha", cross_session("You promised", at(0.5)),
               assistant(f"{SECOND_PROMISE} {ANNOUNCED}", at(9)), turn_end(at(9)))
machine.script({"answer": {"sentences": [{"index": 0, "backed": True, "reason": "a test runs"}]}},
               rechecked(False), usage_limit_exit_with_transcript(RESET_IN_AN_HOUR))
machine.run(16)
checked_sentences_before_reset = [event["sentence"] for event in machine.events("sentence_checked")]
machine.script(sent_ok())
code, _ = machine.run(90)
sent = machine.events("message_sent")
check("one sentence judged backed and a promise unbacked, then an escalation sender at a usage "
      "limit: the backed sentence is logged, so after the reset no second judge runs and the "
      "promise message names only the promise",
      code == 0 and ANNOUNCED in checked_sentences_before_reset
      and SECOND_PROMISE not in checked_sentences_before_reset
      and [event["step"] for event in sent] == ["nudge", "nudge"]
      and "after lunch" in sent[-1]["text"] and "PR 1633" not in sent[-1]["text"],
      (code, checked_sentences_before_reset, sent, machine.claude_calls()))

machine = Machine()
machine.seat("alpha", [user("go"), assistant(PROMISE), turn_end()])
machine.script(sent_ok())
machine.run(0)
machine.seat("beta", DONE_TURN)
machine.task("beta", "1")
machine.script(usage_limit_exit_with_transcript(RESET_IN_AN_HOUR))
machine.run(5)
machine.script()
code, _ = machine.run(16)
check("a pause another agent-seat's judge started holds when a wait's escalation falls due: no "
      "escalation is logged or sent",
      code == 0 and [event["step"] for event in machine.events("wait_step")] == ["nudge"]
      and not machine.claude_calls() and len(machine.events("headless_usage_limit_pause")) == 1,
      (code, machine.events("wait_step"), machine.claude_calls()))

machine = Machine()
machine.seat("alpha", [user("go"), assistant(PROMISE), turn_end()])
machine.script(sent_ok())
machine.run(0)
machine.append("alpha", cross_session(machine.events("message_sent")[-1]["text"], at(0.5)),
               assistant("Recorded.", at(1)), turn_end(at(1)))
machine.script(usage_limit_exit_with_transcript(RESET_IN_AN_HOUR))
machine.run(16)
check("the re-check judge at a usage limit with a reset time ahead: a pause, no task, and no "
      "escalation logged or sent",
      len(machine.events("headless_usage_limit_pause")) == 1 and not machine.owner_tasks()
      and len(machine.claude_calls()) == 1
      and [event["step"] for event in machine.events("wait_step")] == ["nudge"]
      and [event["step"] for event in machine.events("message_sent")] == ["nudge"],
      (machine.events("headless_usage_limit_pause"), machine.owner_tasks(), machine.claude_calls(),
       machine.events("wait_step")))
machine.script()
machine.run(30)
check("the re-check judge's pause holds: no headless agent-session before the reset",
      not machine.claude_calls(), machine.claude_calls())
machine.script(rechecked(False), sent_ok())
code, _ = machine.run(61)
check("after the reset, the re-check is asked again, and the escalation is sent",
      code == 0 and len(machine.claude_calls()) == 2
      and [event["step"] for event in machine.events("wait_step")] == ["nudge", "escalate"],
      (code, machine.claude_calls(), machine.events("wait_step")))

machine = account_changed_machine()
machine.script(usage_limit_exit_with_transcript(RESET_IN_AN_HOUR))
code, _ = machine.run(1)
check("the sender of the account-change notice at a usage limit with a reset time ahead: a pause, "
      "no task", len(machine.events("headless_usage_limit_pause")) == 1 and not machine.owner_tasks(),
      (code, machine.events("headless_usage_limit_pause"), machine.owner_tasks()))

for case, resets_at in (("carries no reset time", None),
                        ("carries a reset time already passed", int(START.timestamp()) - 60)):
    machine = two_seats_with_open_tasks()
    machine.script(usage_limit_exit_with_transcript(resets_at), judged(False))
    code, _ = machine.run(0)
    check(f"a judge at a usage limit whose transcript {case}: a task for reboot-test, no pause, the "
          "next agent-seat judged",
          code == 1 and machine.owner_task_subjects() == [USAGE_LIMIT_TASK_SUBJECT]
          and not machine.events("headless_usage_limit_pause") and len(machine.claude_calls()) == 2,
          (code, machine.owner_tasks(), machine.claude_calls()))

# --- delivery while the agent-seat is busy ----------------------------------------------------------
machine = Machine()
machine.seat("alpha", DONE_TURN)
machine.handoff_put_off()
machine.script(sent_ok())
machine.run(0)
machine.append("alpha", user("next", at(0.5)))
machine.script()
machine.run(2)
check("the message not yet in the transcript of a busy agent-seat: the delivery check waits",
      not machine.events("delivery_checked") and not machine.alerts(), machine.events())

machine = Machine()
machine.seat("alpha", DONE_TURN)
machine.handoff_put_off()
machine.script(sent_ok())
machine.run(0)
machine.transcripts["alpha"].write_text("{not json\n" + json.dumps(turn_end()) + "\n")
machine.script()
code, _ = machine.run(2)
check("a transcript the delivery check cannot read: a read failure logged, the check left pending",
      not machine.events("delivery_checked") and not machine.alerts()
      and any("s-1.jsonl line 1" in event["error"] for event in machine.events("read_failure")),
      machine.events())

machine = Machine()
machine.seat("alpha", [user("go"), usage_limit(RESET_PASSED + 86400)])
machine.seat("beta", DONE_TURN, session="s-beta")
machine.run(0)
machine.account("account-2")
machine.script({"sends": [send_to("alpha"), send_to("beta")], "answer": {"sent": True, "reason": "r"}})
machine.run(1)
machine.transcripts["alpha"].write_text("{not json\n" + json.dumps(turn_end()) + "\n")
machine.script()
machine.run(3)
check("an unreadable transcript at one delivery check does not stop the next agent-seat's check",
      [(event["agent_seat"], event["found"]) for event in machine.events("delivery_checked")]
      == [("beta", False)], machine.events("delivery_checked"))

machine = Machine()
machine.seat("alpha", DONE_TURN)
machine.handoff_put_off()
machine.script(dict(sent_ok(), garbage="a line that is not JSON", garbage_then_result=True))
code, _ = machine.run(0)
check("a line of output that is not JSON, before the result: skipped, the send stands",
      code == 0 and not machine.events("headless_failed") and machine.events("message_sent"),
      machine.events())

machine = Machine()
machine.seat("alpha", DONE_TURN)
machine.handoff_put_off()
machine.script({"sends": [send_to("alpha", "Your handoff was put off\n at")],
                "answer": {"sent": True, "reason": "r"}})
machine.run(0)
text = machine.claude_calls()[0]["prompt"].split("----------\n", 1)[1].rsplit("\n----------", 1)[0]
machine.script({"sends": [send_to("alpha", text.replace(" ", "\n", 3))],
                "answer": {"sent": True, "reason": "r"}})
machine.run(1, "--state-directory", str(machine.root / "state-2"), "--log-file",
            str(machine.root / "log-2.jsonl"))
check("a sender that reflows the lines of code's text: no failure",
      not [event for event in map(json.loads, (machine.root / "log-2.jsonl").read_text().splitlines())
           if event["event"] == "headless_failed"], (machine.root / "log-2.jsonl").read_text())

# --- read failures, the lock, and a failed invocation -----------------------------------------------
machine = Machine()
machine.seat("alpha", DONE_TURN)
(machine.handoffs / "alpha-supervisor-state.json").write_text("{not json")
code, _ = machine.run(0)
check("a read failure seen once: logged, no user-alert", len(machine.events("read_failure")) == 1
      and not machine.alerts(), machine.events())
code, _ = machine.run(3)
check("the same read failure minutes later: a task for reboot-test, no user-alert, exit 1",
      code == 1 and not machine.alerts() and len(machine.owner_tasks()) == 1,
      (code, machine.alerts(), machine.owner_tasks()))

machine = Machine()
machine.seat("alpha", DONE_TURN)
machine.handoff_put_off()
machine.state.mkdir()
with (machine.state / "run.lock").open("w") as held:
    fcntl.flock(held, fcntl.LOCK_EX | fcntl.LOCK_NB)
    code, output = machine.run(0)
check("an earlier invocation still running: this one does nothing and exits 0",
      code == 0 and "still running" in output and not machine.claude_calls()
      and not machine.events(), (code, output))

machine = Machine()
machine.seat("alpha", DONE_TURN)
machine.log.parent.mkdir(parents=True)
machine.log.write_text("{not json\n{}\n")
code, output = machine.run(0)
check("an unreadable log: a traceback, exit 1, and a task for reboot-test, no user-alert",
      code == 1 and "IdleSweepLogLineNotUtf8Json" in output and not machine.alerts()
      and len(machine.owner_tasks()) == 1 and machine.owner_task_subjects()[0].startswith(
          "Idle sweep: an invocation failed: IdleSweepLogLineNotUtf8Json"), (code, output))
machine.run(1)
check("the same failed invocation gets one task while it is open",
      len(machine.owner_tasks()) == 1 and not machine.alerts(), machine.owner_tasks())
for path in machine.owner_task_list.glob("*"):
    path.unlink()
machine.owner_task_list.rmdir()
code, output = machine.run(2)
check("a failed invocation whose task cannot be written: one user-alert naming both errors",
      code == 1 and len(machine.alerts()) == 1
      and "could not give reboot-test a task" in machine.alerts()[0]["alert_text"], machine.alerts())
machine.run(3)
check("the same failed invocation, its task still unwritable: alerted once",
      len(machine.alerts()) == 1, machine.alerts())
machine = Machine()
machine.seat("alpha", DONE_TURN)
machine.log.parent.mkdir(parents=True)
machine.log.write_text('{"event": "account_seen", "account": "account-1", "at": "' + at(-5)
                       + '"}\n{"event": "acc')
code, output = machine.run(0)
check("a log whose last line was cut short: the line is skipped, exit 0", code == 0, output)
code, output = machine.run(1)
check("a log whose last line was cut short: later runs still read the log, exit 0",
      code == 0 and "IdleSweepLogLineNotUtf8Json" not in output, (code, output))
check("a log whose last line was cut short: the skipped line is dropped before the next event",
      '{"event": "acc' not in machine.log.read_text().splitlines()
      and machine.log.read_text().startswith('{"event": "account_seen", "account": "account-1"')
      and all(json.loads(line) for line in machine.log.read_text().splitlines()),
      machine.log.read_text())
machine = Machine()
machine.seat("alpha", DONE_TURN)
machine.log.parent.mkdir(parents=True)
WHOLE_LAST_LINE = '{"event": "account_seen", "account": "account-1", "at": "' + at(-5) + '"}'
machine.log.write_text(WHOLE_LAST_LINE)
code, output = machine.run(0)
check("a log whose whole last line has no newline: the line is kept, and the next event follows it",
      code == 0 and machine.log.read_text().splitlines()[0] == WHOLE_LAST_LINE
      and all(json.loads(line) for line in machine.log.read_text().splitlines()),
      machine.log.read_text())
appended = {}
# With no account in the log, one run writes account_seen and then checked: two appends.
for name, text in (("empty", ""), ("cut short", '{"event": "acc')):
    machine = Machine()
    machine.seat("alpha", DONE_TURN)
    machine.log.parent.mkdir(parents=True)
    machine.log.write_text(text)
    machine.run(0)
    appended[name] = machine.log.read_text().splitlines()
check("a log whose last line was cut short: every event of the run is kept, not only its first",
      len(appended["empty"]) >= 2 and len(appended["cut short"]) == len(appended["empty"])
      and all(json.loads(line) for line in appended["cut short"]), appended)

# --- the steps of a wait, worked out apart from the rule 2 send ------------------------------------
machine = Machine()
machine.seat("alpha", DONE_TURN)
machine.handoff_put_off()
machine.script(sent_ok())
machine.run(0)
machine.script(sent_ok())
machine.run(16)
machine.script()
machine.run(32)
(machine.handoffs / "s-1-handoff-deferred").unlink()
machine.append("alpha", user("more", at(40)), assistant(PROMISE, at(41)), turn_end(at(41)))
machine.script(sent_ok())
machine.run(47)
check("a promise after the user was told: the old wait ends and the promise message opens a new one",
      len(machine.claude_calls()) == 1
      and [event["why"] for event in machine.events("wait_ended")][-1:]
      == ["it spent tokens after the user was told"]
      and [event["step"] for event in machine.events("wait_step")]
      == ["nudge", "escalate", "tell_user", "nudge"], machine.events("wait_step"))
machine.script(rechecked(False), sent_ok())
machine.run(63)
calls = machine.claude_calls()
check("a promise after the user was told: still idle 15 minutes later, the escalation is sent",
      len(calls) == 2 and "please check" in calls[1]["prompt"]
      and [event["step"] for event in machine.events("wait_step")][-2:] == ["nudge", "escalate"],
      (calls, machine.events("wait_step")))
machine.script()
machine.run(79)
check("a promise after the user was told: 15 minutes after that escalation, the user is told again",
      [event["step"] for event in machine.events("wait_step")][-3:]
      == ["nudge", "escalate", "tell_user"]
      and sum("after a nudge and an escalation" in alert["title"] for alert in machine.alerts()) == 2,
      (machine.events("wait_step"), machine.alerts()))

THIRD_PROMISE = "I'll push once the tests pass."
machine = Machine()
machine.seat("alpha", [user("go"), assistant(PROMISE), turn_end()])
machine.script(sent_ok())
machine.run(0)
machine.append("alpha", cross_session("You promised", at(0.5)), assistant(SECOND_PROMISE, at(1)),
               turn_end(at(1)))
machine.script(sent_ok())
machine.run(7)
machine.append("alpha", cross_session("You promised", at(7.5)), assistant(THIRD_PROMISE, at(8)),
               turn_end(at(8)))
machine.script(rechecked(False, False, False), sent_ok())
machine.run(16)
calls = machine.claude_calls()
check("a fresh promise at every run does not put off the escalation 15 minutes after the nudge: "
      "the re-check judges the promise found in the escalation's own run, and the escalation "
      "names it in place of a message of its own",
      len(calls) == 2 and THIRD_PROMISE in calls[0]["prompt"] and '"index": 2' in calls[0]["prompt"]
      and "please check" in calls[1]["prompt"] and THIRD_PROMISE in calls[1]["prompt"]
      and [event["step"] for event in machine.events("wait_step")] == ["nudge", "escalate"]
      and len(machine.events("promise_message")) == 2,
      (calls, machine.events("wait_step")))
machine.script()
machine.run(32)
check("the user-alert names the sentence the escalation named, which no message of its own named",
      any(THIRD_PROMISE in alert["alert_text"] and "sent it no message of their own" in alert["alert_text"]
          for alert in machine.alerts()), machine.alerts())

# The re-check finds every sentence backed, the one found in its own run included: the wait ends,
# and no message about that sentence opens a wait of its own.
machine = Machine()
machine.seat("alpha", [user("go"), assistant(PROMISE), turn_end()])
machine.script(sent_ok())
machine.run(0)
machine.append("alpha", cross_session("You promised", at(0.5)), assistant(SECOND_PROMISE, at(8)),
               turn_end(at(8)))
machine.script(rechecked(True, True))
machine.run(16)
check("a promise found in the escalation's own run, which the re-check finds backed with the rest, "
      "ends the wait and opens no new one",
      [event["why"] for event in machine.events("wait_ended")]
      == ["the judge found every sentence its promise messages named backed"]
      and [event["step"] for event in machine.events("wait_step")] == ["nudge"]
      and len(machine.events("message_sent")) == 1 and len(machine.claude_calls()) == 1,
      (machine.events(), machine.claude_calls()))

# --- delivery counts only a record that shows the agent-seat received the message -------------------
for received, record_of in (
        (False, lambda text, when: {"type": "queue-operation", "operation": "enqueue",
                                    "timestamp": when, "content": text}),
        (True, lambda text, when: {"type": "attachment", "timestamp": when, "attachment": {
            "type": "queued_command", "prompt": f"<cross-session-message>\n{text}\n"}})):
    machine = Machine()
    machine.seat("alpha", DONE_TURN)
    machine.handoff_put_off()
    machine.script(sent_ok())
    machine.run(0)
    machine.append("alpha", record_of(machine.events("message_sent")[-1]["text"], at(0.2)))
    machine.script()
    code, _ = machine.run(2)
    kind = "a queued_command attachment" if received else "only Claude Code's enqueue record"
    check(f"the message in {kind}: delivery found {received}",
          [event["found"] for event in machine.events("delivery_checked")] == [received]
          and len(machine.owner_tasks()) == (0 if received else 1) and not machine.alerts(),
          machine.events("delivery_checked"))

# --- what a headless agent-session may use -------------------------------------------------------------
machine = Machine()
machine.seat("alpha", [user("go"), assistant(ANNOUNCED, when="2026-11-02T11:48:00Z"), turn_end()])
machine.script({"answer": {"sentences": [{"index": 0, "backed": False, "reason": "no call"}]}},
               sent_ok())
machine.run(0)
calls = machine.claude_calls()
check("every headless agent-session loads no MCP server and asks no permission it was not given",
      len(calls) == 2 and all("--strict-mcp-config" in call["argv"]
                              and "--permission-mode" in call["argv"]
                              and call["argv"][call["argv"].index("--permission-mode") + 1]
                              == "dontAsk" for call in calls), calls)

# --- a rule 5 message whose send failed ------------------------------------------------------------
machine = Machine()
machine.seat("alpha", DONE_TURN)
machine.task("alpha", "1")
machine.script(judged(True, "What's going on?"),
               {"sends": [send_to("alpha", is_error=True)], "answer": {"sent": False, "reason": "r"}})
code, _ = machine.run(0)
check("a rule 5 message whose send failed: a task, exit 1, the wait started so that the send "
      "is not retried every minute",
      code == 1
      and any("no SendMessage to alpha" in event["problem"]
              for event in machine.events("headless_failed"))
      and len(machine.owner_tasks()) == 1 and len(machine.events("wait_step")) == 1
      and not machine.events("message_sent"), machine.events())

# --- each event carries the time it was written, not the time the run started ---------------------
machine = Machine()
machine.seat("alpha", DONE_TURN)
machine.seat("beta", DONE_TURN, session="s-beta")
machine.handoff_put_off()
machine.handoff_put_off("s-beta")
machine.script(dict(sent_ok(), sleep=2.5), sent_ok("beta"))
machine.run(0)
nudges = {event["agent_seat"]: event["at"] for event in machine.events("wait_step")}
check("a nudge logged after an earlier headless agent-session carries the time it was logged",
      set(nudges) == {"alpha", "beta"} and max(datetime.fromisoformat(stamp.replace("Z", "+00:00"))
                                               for stamp in nudges.values())
      >= START + timedelta(seconds=2), nudges)

machine = Machine()
machine.seat("alpha", DONE_TURN)
machine.handoff_put_off()
machine.seat("beta", DONE_TURN, session="s-beta")
(machine.handoffs / "beta-supervisor-state.json").write_text("{not json")
machine.script(dict(sent_ok(), sleep=1.2))
machine.run(0)
machine.script()
code, _ = machine.run(2)
check("a read failure logged after an earlier headless agent-session: alerted 2 minutes after the "
      "invocation that logged it",
      code == 1 and any("the idle sweep skips beta" in task["description"]
                        for task in machine.owner_tasks()), (code, machine.owner_tasks()))

machine = Machine()
machine.seat("alpha", DONE_TURN)
machine.task("alpha", "1")
machine.log.parent.mkdir()
machine.log.write_text(json.dumps(
    {"event": "judge_answer", "at": at(0), "agent_seat": "alpha", "rule": 5, "session_id": "s-1",
     "last_activity": LONG_AGO, "send": False, "reason": "r", "failed": False}) + "\n")
machine.script(judged(False))
machine.run(14)
asked_at_14 = machine.claude_calls()
machine.script(judged(False))
machine.run(15)
check("a judge answer logged without agent_seat_idle_sweep_invocation_started_at: "
      "the next ask is counted from its at",
      not asked_at_14 and len(machine.claude_calls()) == 1, (asked_at_14, machine.events()))

# --- a read failure that persists keeps the run failing ---------------------------------------------
machine = Machine()
machine.seat("alpha", DONE_TURN)
(machine.handoffs / "alpha-supervisor-state.json").write_text("{not json")
machine.run(0)
machine.run(3)
code, _ = machine.run(5)
check("a read failure still there after its task: exit 1 again, no second task",
      code == 1 and len(machine.owner_tasks()) == 1 and not machine.alerts(),
      (code, machine.owner_tasks()))

# --- a headless agent-session past its time is stopped with every process it started --------------
machine = Machine()
machine.seat("alpha", DONE_TURN)
machine.handoff_put_off()
machine.script({"child": 30, "sleep": 30, "answer": {"sent": True, "reason": "r"}})
began = datetime.now(timezone.utc)
code, _ = machine.run(0, "--headless-timeout-seconds", "1")
took = (datetime.now(timezone.utc) - began).total_seconds()
check("a sender past its time whose child holds its output open: stopped in seconds, not 30",
      code == 1 and took < 15
      and any("stopped after" in event["problem"] for event in machine.events("headless_failed")),
      (code, took, machine.events("headless_failed")))

# --- an older open task that waits on something reaches the judge ---------------------------------
machine = Machine()
machine.seat("alpha", [user("go"), assistant(PROMISE), turn_end()])
machine.task("alpha", "6")
machine.task("alpha", "7")
# blockedBy, not a pull request prerequisite, so that no gh query is made.
older_task = machine.tasks / "nedsnodes-alpha-tasks" / "7.json"
older_task.write_text(json.dumps(dict(json.loads(older_task.read_text()), blockedBy=["6"])))
# Judged backed, rule 5 follows for the open task 6, and its judge sends nothing.
machine.script({"answer": {"sentences": [{"index": 0, "backed": True, "reason": "task 7"}]}},
               judged(False, reason="busy"))
machine.run(0)
calls = machine.claude_calls()
check("a promise with an older open task held by blockedBy: the judge is handed that task",
      len(calls) == 2 and '"open_tasks_with_prerequisites_or_blocked_by": [ { "id": "7", "subject": '
      '"task 7", "prerequisites": [], "blockedBy": [ "6" ] } ]' in " ".join(calls[0]["prompt"].split())
      and not machine.events("message_sent"), calls)

# --- the next check reads from the time of the transcript read, not of the record --------------
# alpha's sender takes 2 s, so beta's check record is written 2 s after beta's transcript was read;
# a promise beta writes 1 s into the run must still be read on the next run.
machine = Machine()
machine.seat("alpha", [user("go"), assistant(PROMISE), turn_end()])
machine.seat("beta", [user("go"), assistant(PROMISE), turn_end()], session="s-2")
machine.script(dict(sent_ok(), sleep=2), sent_ok("beta"))
machine.run(0)
beta_checks = [event for event in machine.events("checked") if event["agent_seat"] == "beta"]
check("a check record keeps the time the transcript was read, apart from the time it was written",
      len(beta_checks) == 1 and beta_checks[0]["transcript_read_at"] == at(0)
      and beta_checks[0]["at"] > at(0), beta_checks)
machine.append("beta", user("more", at(1 / 60)), assistant(SECOND_PROMISE, at(1 / 60)),
               turn_end(at(1 / 60)))
machine.script(sent_ok("beta"), sent_ok("beta"))
machine.run(7)
check("a promise written between the transcript read and the check record is read on the next run",
      SECOND_PROMISE in [event["sentence"] for event in machine.events("sentence_checked")
                         if event["agent_seat"] == "beta"], machine.events())

# --- the delivery check measures from the send's start, not from the sender's end ------------------
# The sender runs 2 s, so its message_sent record is written 2 s after the send began. A received
# record 119 s before the start is inside the 120 s clock slack from the start, and outside it from
# the end: found only when the check measures from the start.
machine = Machine()
machine.seat("alpha", DONE_TURN)
machine.handoff_put_off()
machine.script(dict(sent_ok(), sleep=2))
machine.run(0)
sent = machine.events("message_sent")
check("a send logs the time it started, apart from the time the record is written",
      len(sent) == 1 and sent[0].get("send_started_at") == at(0) and sent[0]["at"] > at(0), sent)
early = (START - timedelta(seconds=119)).isoformat().replace("+00:00", "Z")
machine.append("alpha", user(sent[0]["text"], early))
machine.script()
machine.run(2)
check("a sender that runs on after its send: the delivery check finds the message, no user-alert",
      [event["found"] for event in machine.events("delivery_checked")] == [True]
      and not machine.alerts(), (machine.events("delivery_checked"), machine.alerts()))

# --- a message_sent record with no send_started_at, as the log holds from older invocations ------
machine = Machine()
machine.seat("alpha", DONE_TURN)
machine.handoff_put_off()
machine.script(sent_ok())
machine.run(0)
older = [{key: value for key, value in event.items() if key != "send_started_at"}
         for event in machine.events()]
machine.log.write_text("".join(json.dumps(event) + "\n" for event in older))
machine.append("alpha", user(machine.events("message_sent")[0]["text"], at(0)))
machine.script()
code, output = machine.run(2)
check("a pending send logged with no send_started_at: checked from its \"at\", no crash",
      code == 0 and [event["found"] for event in machine.events("delivery_checked")] == [True],
      (code, output, machine.events("delivery_checked")))

# --- a read failure that ended and came back is dated from its return ---------------------------
machine = Machine()
machine.seat("alpha", DONE_TURN)
state_file = machine.handoffs / "alpha-supervisor-state.json"
good_state = state_file.read_text()
state_file.write_text("{not json")
machine.run(0)
state_file.write_text(good_state)
machine.script()
machine.run(1)
check("a read failure not met again: its end is logged",
      [event["event"] for event in machine.events() if event["event"].startswith("read_failure")]
      == ["read_failure", "read_failure_ended"], machine.events())
machine.script()
machine.run(2)
check("a read failure already ended: a second clean run logs no second end",
      [event["event"] for event in machine.events() if event["event"].startswith("read_failure")]
      == ["read_failure", "read_failure_ended"], machine.events())
state_file.write_text("{not json")
code, _ = machine.run(10)
check("the failure back days later: logged anew, no task at once",
      len(machine.events("read_failure")) == 2 and not machine.owner_tasks(), machine.owner_tasks())
code, _ = machine.run(13)
check("the failure back, minutes after its return: one task",
      code == 1 and len(machine.owner_tasks()) == 1 and not machine.alerts(),
      (code, machine.owner_tasks()))

# --- the escalation quotes a nudge of several lines --------------------------------------------------
machine = Machine()
machine.seat("alpha", [user("go"), assistant(f"{PROMISE} {SECOND_PROMISE}"), turn_end()])
machine.script(sent_ok())
machine.run(0)
nudge_text = machine.events("wait_step")[0]["text"]
machine.script(rechecked(False, False), sent_ok())
machine.run(16)
escalation = machine.events("message_sent")[-1]["text"]
quote = escalation.split("which you have not acted on:\n\n", 1)[-1].rsplit("\n\n", 1)[0]
check("an escalation after a nudge of two lines: each line of the nudge quoted with \"> \", the "
      "do-not-reply sentence once, after the quote and on no quoted line",
      len(nudge_text.split("\n")) == 2 and machine.events("message_sent")[-1]["step"] == "escalate"
      and quote == "\n".join("> " + line for line in nudge_text.split("\n"))
      and ends_with_do_not_reply_once(escalation)
      and not any(DO_NOT_REPLY in line for line in escalation.split("\n") if line.startswith(">")),
      (nudge_text, escalation))

# --- every wake message ends with the do-not-reply sentence ---------------------------------------
wake_texts = []
def sender_texts(machine):
    return [call["prompt"].split("----------\n", 1)[1].rsplit("\n----------", 1)[0]
            for call in machine.claude_calls() if "----------\n" in call["prompt"]]
machine = Machine()
machine.seat("alpha", DONE_TURN)
machine.handoff_put_off()
machine.script(sent_ok())
machine.run(0)
wake_texts += [("rule 3 nudge", text) for text in sender_texts(machine)]
machine.script(sent_ok())
machine.run(16)
wake_texts += [("escalation", text) for text in sender_texts(machine)]
machine = Machine()
machine.seat("alpha", [user("go"), assistant(PROMISE), turn_end()])
machine.script(sent_ok())
machine.run(0)
wake_texts += [("rule 2 nudge", text) for text in sender_texts(machine)]
machine = Machine()
machine.seat("alpha", DONE_TURN)
machine.task("alpha", "1")
machine.script(judged(True, "What's going on?"), sent_ok())
machine.run(0)
wake_texts += [("rule 5 nudge", text) for text in sender_texts(machine)]
machine = Machine()
machine.seat("alpha", [user("go"), usage_limit(RESET_PASSED)])
machine.script(sent_ok())
machine.run(0)
wake_texts += [("limit wake", text) for text in sender_texts(machine)]
machine = Machine()
machine.seat("alpha", DONE_TURN)
machine.seat("beta", DONE_TURN, session="s-beta")
machine.run(0)
machine.account("account-2")
machine.script({"sends": [send_to("alpha"), send_to("beta")], "answer": {"sent": True, "reason": "r"}})
machine.run(1)
wake_texts += [("account notice", text) for text in sender_texts(machine)]
check("every wake message a sender is handed ends with the do-not-reply sentence, once",
      [kind for kind, _ in wake_texts] == ["rule 3 nudge", "escalation", "rule 2 nudge",
                                           "rule 5 nudge", "limit wake", "account notice"]
      and all(ends_with_do_not_reply_once(text) for _, text in wake_texts), wake_texts)
check("the account notice is logged for each agent-seat as sent, with the do-not-reply sentence",
      len(machine.events("message_sent")) == 2
      and all(event["text"] == wake_texts[-1][1] for event in machine.events("message_sent")),
      machine.events("message_sent"))

# --- rule 5: an open pull-request events task wakes merge-lane-2 in code ------------------------
EVENTS_SEAT = "merge-lane-2"
EVENTS_TASK_SUBJECT = "Read the new pull-request events in the watcher's event file"
FAKE_GITHUB = """#!{python}
import os, sys
sys.stdout.write(open(os.environ["FAKE_GITHUB_ANSWER"]).read())
"""


def github_answer(*numbers):
    return json.dumps({"data": {"repository": {"pullRequests": {
        "nodes": [{"number": number, "title": "t", "isDraft": False, "headRefOid": "a" * 40,
                   "author": {"login": "nedlern"}, "createdAt": "2026-11-02T00:00:00Z",
                   "baseRefName": "main", "headRefName": f"branch-{number}",
                   "reviews": {"nodes": []}, "macClaudeReviews": {"nodes": []}} for number in numbers],
        "pageInfo": {"hasNextPage": False, "endCursor": None}}}}})


class RealWatcher:
    """merge-lane-open-prs-watch-and-reviewer-assign.py itself, run as cron runs it, against a fake gh."""

    def __init__(self, machine):
        self.root = machine.root / "watcher"
        (self.root / "bin").mkdir(parents=True)
        fake_gh = self.root / "bin" / "gh"
        fake_gh.write_text(FAKE_GITHUB.format(python=sys.executable))
        fake_gh.chmod(0o755)
        self.answer = self.root / "answer.json"
        self.token = self.root / "token"
        self.token.write_text("fixture-token-never-a-real-credential")
        self.tasks = machine.tasks / f"nedsnodes-{EVENTS_SEAT}-tasks"
        self.tasks.mkdir(exist_ok=True)
        # Every number assigned already, so no REVIEW-ASSIGNED line; the default file is
        # merge-lane-2's real one.
        self.assignments = self.root / "assignments.txt"
        self.assignments.write_text("1 merge-lane-1\n2 merge-lane-3\n")

    def run(self, flag, *numbers):
        self.answer.write_text(github_answer(*numbers))
        environment = dict(os.environ, FAKE_GITHUB_ANSWER=str(self.answer),
                           PATH=f"{self.root / 'bin'}{os.pathsep}{os.environ['PATH']}")
        return subprocess.run(
            [sys.executable, str(PROGRAM.with_name("merge-lane-open-prs-watch-and-reviewer-assign.py")), flag,
             "--token-file", str(self.token), "--poll-once-directory", str(self.root / "state"),
             "--task-list-directory", str(self.tasks),
             "--needs-a-look-directory", str(self.root / "notices"),
             "--merge-lane-pr-review-assignments-file", str(self.assignments)],
            env=environment, capture_output=True, text=True, check=False).returncode

    def complete_tasks(self):
        for path in self.tasks.glob("*.json"):
            task = json.loads(path.read_text())
            path.write_text(json.dumps(dict(task, status="completed")))


machine = Machine()
machine.seat(EVENTS_SEAT, DONE_TURN)
watcher = RealWatcher(machine)
baseline_code = watcher.run("--poll-once-write-baseline", 1)
quiet_code = watcher.run("--poll-once", 1)
machine.script()
machine.run(0)
check("a watcher run that detects nothing new opens no task, and the sweep starts no agent-session "
      "and sends merge-lane-2 nothing",
      (baseline_code, quiet_code) == (0, 0) and not list(watcher.tasks.glob("*.json"))
      and not machine.claude_calls() and not machine.events("message_sent"),
      (baseline_code, quiet_code, machine.claude_calls()))
new_code = watcher.run("--poll-once", 1, 2)
task_id = next(watcher.tasks.glob("*.json")).stem
machine.script(sent_ok(EVENTS_SEAT))
machine.run(1)
calls = machine.claude_calls()
check("the watcher's events task wakes idle merge-lane-2: one sender and no judge, with code's text",
      new_code == 0 and len(calls) == 1 and "SendMessage" in calls[0]["argv"][calls[0]["argv"].index("--tools") + 1]
      and machine.events("message_sent")[-1]["agent_seat"] == EVENTS_SEAT
      and machine.events("message_sent")[-1]["text"].startswith(f"Task {task_id} on your task list holds new "
                                                               "pull-request events.")
      and machine.events("wait_step")[-1]["step"] == "nudge", (calls, machine.events()))
machine.script()
machine.run(2)
check("the open wait sends no second wake", not machine.claude_calls(), machine.claude_calls())
machine.append(EVENTS_SEAT, assistant(None, at(3), tool=("Read", {"file_path": "/x"}), tool_id="r1"),
               task_result("r1", "ok", at(3)), assistant("Done again.", at(4)), turn_end(at(4)))
machine.script()
machine.run(10)
check("a tool call ends the wait, and the same task wakes no one again within 15 minutes",
      not machine.claude_calls()
      and machine.events("wait_ended")[-1]["why"] == "it made a tool call after the nudge",
      (machine.claude_calls(), machine.events("wait_ended")))
machine.script(sent_ok(EVENTS_SEAT))
machine.run(17)
check("the task still open 15 minutes after the wake wakes merge-lane-2 once more",
      len(machine.claude_calls()) == 1 and len(machine.events("message_sent")) == 2, machine.events())
watcher.complete_tasks()
machine.append(EVENTS_SEAT, assistant("Handled.", at(18)), turn_end(at(18)))
machine.script()
machine.run(24)
check("with the events task completed, the sweep wakes no one",
      not machine.claude_calls() and len(machine.events("message_sent")) == 2
      and machine.events("checked")[-1]["rule"] == 4, machine.claude_calls())

machine = Machine()
machine.seat("alpha", DONE_TURN)
directory = machine.tasks / "nedsnodes-alpha-tasks"
directory.mkdir()
(directory / "1.json").write_text(json.dumps({"id": "1", "subject": EVENTS_TASK_SUBJECT,
                                              "status": "pending", "blocks": [], "blockedBy": []}))
machine.script(judged(False, reason="not its work"))
machine.run(0)
calls = machine.claude_calls()
check("the same task subject on another agent-seat's list still goes to the judge",
      len(calls) == 1 and calls[0]["argv"][calls[0]["argv"].index("--tools") + 1] == ""
      and not machine.events("message_sent"), calls)

machine = Machine()
machine.seat(EVENTS_SEAT, DONE_TURN)
directory = machine.tasks / f"nedsnodes-{EVENTS_SEAT}-tasks"
directory.mkdir()
(directory / "1.json").write_text(json.dumps({"id": "1", "subject": "task 1", "status": "pending",
                                              "blocks": [], "blockedBy": []}))
machine.script(judged(False, reason="busy"))
machine.run(0)
check("another task on merge-lane-2's list still goes to the judge",
      len(machine.claude_calls()) == 1 and not machine.events("message_sent"), machine.claude_calls())

machine = Machine()
machine.seat(EVENTS_SEAT, DONE_TURN)
directory = machine.tasks / f"nedsnodes-{EVENTS_SEAT}-tasks"
directory.mkdir()
(directory / "1.json").write_text(json.dumps({"id": "1", "subject": EVENTS_TASK_SUBJECT,
                                              "status": "pending", "blocks": [], "blockedBy": []}))
running_machine = Machine()
running_machine.seat(EVENTS_SEAT, [
    user("go"), *background_bash_launch("bk1", "python3 scripts/x-test.py", at(-20), "tb1"),
    assistant("Waiting on the check."), turn_end()])
running_directory = running_machine.tasks / f"nedsnodes-{EVENTS_SEAT}-tasks"
running_directory.mkdir()
(running_directory / "7.json").write_text(json.dumps({"id": "7", "subject": EVENTS_TASK_SUBJECT,
                                                      "status": "pending", "blocks": [],
                                                      "blockedBy": []}))
running_machine.script(sent_ok(EVENTS_SEAT))
running_machine.run(0)
calls = running_machine.claude_calls()
check("an idle merge-lane-2 with a background command running is still woken for its events task, "
      "with no judge",
      len(calls) == 1 and "SendMessage" in calls[0]["argv"][calls[0]["argv"].index("--tools") + 1]
      and running_machine.events("message_sent")[-1]["text"].startswith("Task 7 on your task list"),
      (calls, running_machine.events()))

machine.script({"exit": 3})
machine.run(0)
check("a wake whose send fails is reported to the sweep's owner, and its wait stays open to escalate",
      not machine.events("message_sent") and machine.events("wait_step")[-1]["step"] == "nudge"
      and machine.owner_tasks() != [], machine.events())
check("a wake whose send fails is logged as not sent",
      [event["send"] for event in machine.events("judge_answer")] == [False],
      machine.events("judge_answer"))
machine = Machine()
machine.seat(EVENTS_SEAT, DONE_TURN)
directory = machine.tasks / f"nedsnodes-{EVENTS_SEAT}-tasks"
directory.mkdir()
(directory / "1.json").write_text(json.dumps({"id": "1", "subject": EVENTS_TASK_SUBJECT,
                                              "status": "pending", "blocks": [], "blockedBy": []}))
machine.script(sent_ok(EVENTS_SEAT))
machine.run(0)
check("a wake whose send succeeds is logged as sent",
      [event["send"] for event in machine.events("judge_answer")] == [True],
      machine.events("judge_answer"))

# --- no reminder of a wait on the user, and no repeat until the user types ----------------------
def typed_by_the_user(text, when):
    return {**user(text, when), "origin": {"kind": "human"}}


def queued_by_the_user(text, when):
    return {"type": "attachment", "timestamp": when, "attachment": {
        "type": "queued_command", "prompt": text, "origin": {"kind": "human"}}}


def one_reminder_of_task_1():
    machine = Machine()
    machine.seat("alpha", DONE_TURN)
    machine.task("alpha", "1")
    machine.script(judged(True, 'Your task "task 1" is open and nothing holds it.', raised=["1"]), sent_ok())
    machine.run(0)
    answered_with_a_tool_call_and_idle_again(machine, 10)
    return machine


def judge_asked_at(machine, minutes):
    machine.script(judged(False))
    machine.run(minutes)
    return rule_five_judge_facts(machine)


machine = Machine()
machine.seat("alpha", DONE_TURN)
machine.task("alpha", "1")
machine.script(judged(False))
machine.run(0)
check("rule 5: the judge is told never to mention a wait on the user, and to send nothing when that "
      "is all that is left",
      "never mention that wait" in " ".join(machine.claude_calls()[0]["prompt"].split())
      and "send no message" in " ".join(machine.claude_calls()[0]["prompt"].split()),
      machine.claude_calls())

machine = one_reminder_of_task_1()
calls, _ = judge_asked_at(machine, 20)
check("rule 5: an open task already reminded of is not raised again, and no judge runs", not calls, calls)
machine.append("alpha", cross_session("A message from another agent-seat.", at(21)),
               assistant("Done.", when=at(21)), turn_end(at(21)))
calls, _ = judge_asked_at(machine, 40)
check("rule 5: a message from another agent-seat is not the user typing", not calls, calls)
machine.append("alpha", typed_by_the_user("Please carry on.", at(41)),
               assistant("On it.", when=at(41)), turn_end(at(41)))
calls, facts = judge_asked_at(machine, 60)
check("rule 5: once the user has typed, the same open task is raised again",
      [task["id"] for task in facts.get("open_tasks_nothing_holds", [])] == ["1"], calls)

for notice in (user([{"type": "text", "text": "[Request interrupted by user]"}], at(11)),
               typed_by_the_user("[Request interrupted by user for tool use]", at(11))):
    machine = one_reminder_of_task_1()
    machine.append("alpha", notice, assistant("Stopped.", when=at(11)), turn_end(at(11)))
    calls, _ = judge_asked_at(machine, 30)
    check("rule 5: an interrupt notice, which the user did not type, does not raise the task again",
          not calls, calls)

machine = Machine()
machine.seat("alpha", DONE_TURN)
machine.task("alpha", "1")
machine.script(judged(True, "You have open tasks.", raised=["1"]), sent_ok())
machine.run(0)
machine.append("alpha", typed_by_the_user("Something else.", at(2)))
answered_with_a_tool_call_and_idle_again(machine, 5)
machine.run(6)
calls, _ = judge_asked_at(machine, 20)
check("rule 5: the user typing after the send started, before the message arrived, does not raise "
      "the task again",
      [event.get("received_at") for event in machine.events("delivery_checked")] == [at(4.5)]
      and not calls, (machine.events("delivery_checked"), calls))

machine = one_reminder_of_task_1()
machine.append("alpha", queued_by_the_user("Also this.", at(11)),
               assistant("On it.", when=at(11)), turn_end(at(11)))
_, facts = judge_asked_at(machine, 30)
check("rule 5: a message the user typed while the agent-seat was mid-turn counts as the user typing",
      [task["id"] for task in facts.get("open_tasks_nothing_holds", [])] == ["1"], facts)

machine = one_reminder_of_task_1()
machine.task("alpha", "2")
_, facts = judge_asked_at(machine, 20)
check("rule 5: a new open task is raised, without the one already reminded of",
      [task["id"] for task in facts.get("open_tasks_nothing_holds", [])] == ["2"], facts)

machine = Machine()
machine.seat("alpha", DONE_TURN)
machine.task("alpha", "1")
machine.task("alpha", "2")
machine.script(judged(True, 'Your task "task 1" is open and nothing holds it.', raised=["1"]), sent_ok())
machine.run(0)
answered_with_a_tool_call_and_idle_again(machine, 10)
_, facts = judge_asked_at(machine, 20)
check("rule 5: an open task the message did not name is still raised",
      [task["id"] for task in facts.get("open_tasks_nothing_holds", [])] == ["2"], facts)

machine = Machine()
machine.seat("alpha", DONE_TURN)
machine.task("alpha", "1")
machine.task("alpha", "2")
machine.script(judged(True, "You have open tasks and nothing holds them.", raised=["1", "2"]),
               sent_ok())
machine.run(0)
answered_with_a_tool_call_and_idle_again(machine, 10)
calls, _ = judge_asked_at(machine, 20)
check("rule 5: every task the judge lists as raised counts as reminded", not calls, calls)

machine = Machine()
machine.seat("alpha", DONE_TURN)
machine.task("alpha", "1")
machine.task("alpha", "12")
machine.script(judged(True, 'Your task "task 12" is open: (1) rebase it.', raised=["12"]), sent_ok())
machine.run(0)
check("rule 5: only the ids the judge lists are recorded, whatever the message's words match",
      [event["subjects"] for event in machine.events("reminder_sent")] == [["open task: 12"]],
      machine.events("reminder_sent"))

machine = Machine()
machine.seat("alpha", DONE_TURN)
for task_id in ("1", "2", "3"):
    machine.task("alpha", task_id)
machine.script(judged(True, "You have open tasks nothing holds, for example #1.",
                      raised=["1", "2", "3"]), sent_ok())
machine.run(0)
sent_text = machine.events("message_sent")[0]["text"]
check("rule 5: code lists every raised task in the message, whatever examples the judge gave",
      'Open tasks nothing holds: #1 "task 1"; #2 "task 2"; #3 "task 3".' in sent_text
      and [event["subjects"] for event in machine.events("reminder_sent")]
      == [["open task: 1", "open task: 2", "open task: 3"]], sent_text)
answered_with_a_tool_call_and_idle_again(machine, 10)
calls, _ = judge_asked_at(machine, 20)
check("rule 5: one backlog gives one reminder, though the judge's words named one task", not calls,
      calls)

machine = Machine()
machine.seat("alpha", DONE_TURN)
machine.task("alpha", "1")
machine.task("alpha", "2")
machine.script(judged(True, "You have open tasks.", raised=["1", "2"]),
               {"sends": [send_to("alpha", 'You have open tasks. Open tasks nothing holds: #1 '
                                  f'"task 1".\n\n{DO_NOT_REPLY}')],
                "answer": {"sent": True, "reason": "sent"}})
machine.run(0)
check("rule 5: a task the sender left out of the text sent is not recorded as reminded",
      [event["subjects"] for event in machine.events("reminder_sent")] == [["open task: 1"]],
      machine.events("reminder_sent"))

for name, bad_raised in (("an id it was not given", ["9"]), ("no list", None)):
    machine = Machine()
    machine.seat("alpha", DONE_TURN)
    machine.task("alpha", "1")
    answer = judged(True, 'Your task "task 1" is open.', raised=["1"])
    answer["answer"]["open_task_ids_raised"] = bad_raised
    machine.script(answer)
    machine.run(0)
    check(f"rule 5: a judge answer listing {name} is a failure and sends nothing",
          not machine.events("message_sent") and not machine.events("reminder_sent")
          and machine.events("judge_answer")[-1]["failed"], machine.events("judge_answer"))

machine = Machine()
machine.seat("alpha", DONE_TURN)
machine.task("alpha", "1")
machine.script(judged(True, 'Your task "task 1" is open.', raised=["1"]),
               {"sends": [send_to("alpha", is_error=True)], "answer": {"sent": False, "reason": "r"}})
machine.run(0)
check("rule 5: a message whose send failed logs no reminder", not machine.events("reminder_sent"),
      machine.events())

machine = Machine()
machine.seat("alpha", DONE_TURN)
machine.task("alpha", "1")
machine.script(judged(True, 'Your task "task 1" is open.', raised=["1"]), sent_ok())
machine.run(0)
answered_with_a_tool_call_and_idle_again(machine, 10, received=False)
machine.run(11)
_, facts = judge_asked_at(machine, 20)
check("rule 5: a reminder the delivery check did not find is raised again",
      [event["found"] for event in machine.events("delivery_checked")] == [False]
      and [task["id"] for task in facts.get("open_tasks_nothing_holds", [])] == ["1"],
      machine.events("delivery_checked"))

machine = one_reminder_of_task_1()
machine.seat("alpha", DONE_TURN, session="s-2")
_, facts = judge_asked_at(machine, 20)
check("rule 5: a new agent-session is reminded of the task again",
      [task["id"] for task in facts.get("open_tasks_nothing_holds", [])] == ["1"], facts)

machine = Machine()
machine.seat("alpha", DONE_TURN)
machine.handoff_put_off()
machine.script(sent_ok())
machine.run(0)
answered_with_a_tool_call_and_idle_again(machine, 10)
machine.script()
machine.run(20)
check("rule 3: the same put-off handoff is not raised again until the user types",
      not machine.claude_calls() and len(machine.events("message_sent")) == 1, machine.events())
machine.append("alpha", typed_by_the_user("Go on.", at(21)), assistant("On it.", when=at(21)),
               turn_end(at(21)))
machine.script(sent_ok())
machine.run(40)
check("rule 3: once the user has typed, the put-off handoff is raised again",
      len(machine.events("message_sent")) == 2, machine.events("message_sent"))

machine = Machine()
machine.seat("alpha", DONE_TURN)
machine.task("alpha", "1")
machine.script(judged(True, 'Your task "task 1" is open.', raised=["1"]), sent_ok())
machine.run(0)
machine.append("alpha", cross_session(machine.events("message_sent")[-1]["text"], at(0.5)),
               assistant("Done.", when=at(1)), turn_end(at(1)))
machine.script(sent_ok())
machine.run(16)
machine.script()
machine.run(32)
check("a reminder already sent still goes on to its escalation and its user-alert",
      [event["step"] for event in machine.events("wait_step")] == ["nudge", "escalate", "tell_user"]
      and len(machine.alerts()) == 1, machine.events("wait_step"))

machine = one_reminder_of_task_1()
machine.append("alpha", assistant("I'll report when PR 927 merges.", when=at(11)), turn_end(at(11)))
machine.script(sent_ok())
machine.run(20)
check("a new promise is still raised while the open task's reminder is held",
      [event.get("rule") for event in machine.events("wait_step")] == [5, 2]
      and len(machine.events("message_sent")) == 2,
      ([event.get("rule") for event in machine.events("wait_step")],
       [event["event"] for event in machine.events()][-6:], machine.claude_calls()[:1]))

machine = one_reminder_of_task_1()
machine.append("alpha",
               assistant(tool=("TaskUpdate", {"taskId": "1", "metadata": {
                   "prerequisites": [{"pr_merged": 927}]}}), when=at(11), tool_id="t-hold"),
               task_result("t-hold", "Updated task #1 metadata", at(11.01)),
               assistant("Held.", when=at(11.1)), turn_end(at(11.1)))
_, facts = judge_asked_at(machine, 45)
check("rule 5: a reminded task held after the reminder is raised again once it is free",
      [task["id"] for task in facts.get("open_tasks_nothing_holds", [])] == ["1"], facts)

machine = one_reminder_of_task_1()
machine.append("alpha",
               assistant(tool=("TaskUpdate", {"taskId": "2", "addBlocks": ["1"]}), when=at(11),
                         tool_id="t-blocks"),
               task_result("t-blocks", "Updated task #2 blocks", at(11.01)),
               assistant("Held.", when=at(11.1)), turn_end(at(11.1)))
_, facts = judge_asked_at(machine, 45)
check("rule 5: a reminded task held through another task's addBlocks is raised again once it is free",
      [task["id"] for task in facts.get("open_tasks_nothing_holds", [])] == ["1"], facts)

machine = one_reminder_of_task_1()
machine.append("alpha",
               assistant(tool=("TaskUpdate", {"taskId": "2", "addBlocks": ["1"]}), when=at(11),
                         tool_id="t-blocks"),
               task_result("t-blocks", "Task not found", at(11.01)),
               assistant("Held.", when=at(11.1)), turn_end(at(11.1)))
machine.script()
machine.run(45)
check("rule 5: an addBlocks call that failed does not count as a hold, so the reminder stays withheld",
      not machine.claude_calls(), machine.claude_calls())

machine = Machine()
machine.seat("alpha", DONE_TURN)
machine.handoff_put_off()
machine.script(sent_ok())
machine.run(0)
answered_with_a_tool_call_and_idle_again(machine, 10)
machine.task("alpha", "2")
machine.script(judged(False))
machine.run(20)
_, facts = rule_five_judge_facts(machine)
check("rule 3: while its reminder is held, a new open task still goes to the judge, without the "
      "put-off handoff",
      [task["id"] for task in facts.get("open_tasks_nothing_holds", [])] == ["2"]
      and facts.get("handoff_deferral_marker_file") is None, facts)

machine = Machine()
machine.seat("alpha", DONE_TURN)
machine.handoff_put_off()
machine.script({"sends": [send_to("alpha", is_error=True)], "answer": {"sent": False, "reason": "r"}})
machine.run(0)
check("rule 3: a message whose send failed logs no reminder", not machine.events("reminder_sent"),
      machine.events())

import importlib.util
_spec = importlib.util.spec_from_file_location("idle_sweep_program", PROGRAM)
idle_sweep_program = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(idle_sweep_program)


def reminded(events, typed=None, held=None):
    path = SUITE_ROOT / f"reminded-{len(list(SUITE_ROOT.iterdir()))}.jsonl"
    path.write_text("".join(json.dumps({"agent_seat": "alpha", **event}) + "\n" for event in events))
    return idle_sweep_program.SweepLog(path).reminded_subjects(
        "alpha", "s1", typed, {subject: idle_sweep_program.parse_time(time)
                               for subject, time in (held or {}).items()})


REMINDER = {"event": "reminder_sent", "session_id": "s1", "message_id": "m1",
            "subjects": ["open task: 1"], "send_started_at": at(0), "at": at(0.1)}
ARRIVED = {"event": "delivery_checked", "message_id": "m1", "found": True, "received_at": at(0.5)}
check("a hold made while the sender ran, before the reminder arrived, has not answered it",
      reminded([REMINDER, ARRIVED], held={"open task: 1": at(0.3)}) == {"open task: 1"})
check("a hold made after the reminder arrived frees the task to be raised again",
      reminded([REMINDER, ARRIVED], held={"open task: 1": at(0.7)}) == set())
check("before the delivery check, typing before the send was logged has not answered the reminder",
      reminded([REMINDER], typed=at(0.05)) == {"open task: 1"})
check("before the delivery check, typing after the send was logged answers the reminder",
      reminded([REMINDER], typed=at(0.2)) == set())


# --- sentence groups on an open wait are matched by sentence, and the escalation sent names them ------
def rule_five_wait_with_promises(*records):
    """A machine whose agent-seat answered a rule 5 message, sent at minute 0, with records."""
    machine = Machine()
    machine.seat("alpha", DONE_TURN)
    machine.task("alpha", "1")
    machine.script(judged(True, "What's going on?", "nothing runs"), sent_ok())
    machine.run(0)
    (machine.tasks / "nedsnodes-alpha-tasks" / "1.json").unlink()
    machine.append("alpha", cross_session(machine.events("message_sent")[-1]["text"], at(0.5)),
                   *records)
    return machine


without_uuid = assistant(OTHER_PROMISE, at(1.1))
del without_uuid["uuid"]
machine = rule_five_wait_with_promises(assistant(PROMISE, at(1)), turn_end(at(1)), user("go on", at(1.05)),
                                       without_uuid, turn_end(at(1.1)))
machine.script(sent_ok())
code, output = machine.run(7)
check("a batch holding a sentence whose record has no uuid beside one that has a uuid: one group "
      "of both, and no traceback",
      "Traceback" not in output
      and [sorted(event["sentences"]) for event in machine.events("rule_2_sentences_on_wait")]
      == [sorted([PROMISE, OTHER_PROMISE])], (code, output, machine.events()))

# An invocation stopped after logging promise A's group, and promise B made before the next one.
machine = rule_five_wait_with_promises(assistant(PROMISE, at(1)), turn_end(at(1)))
machine.script(sent_ok())
machine.run(7)
log_lines = machine.log.read_text().splitlines(keepends=True)
group_line = next(number for number, line in enumerate(log_lines)
                  if json.loads(line)["event"] == "rule_2_sentences_on_wait")
machine.log.write_text("".join(log_lines[:group_line + 1]))
machine.append("alpha", user("go on", at(7.5)), assistant(OTHER_PROMISE, at(7.6)),
               turn_end(at(7.6)))
machine.script(sent_ok())
machine.run(14)
groups = machine.events("rule_2_sentences_on_wait")
check("a batch judged again with one sentence already on the wait and one new: only the new one is "
      "logged on the wait, and the message takes both off it",
      [group["sentences"] for group in groups] == [[PROMISE], [OTHER_PROMISE]]
      and [sorted(map(tuple, event.get("records", []))) for event in machine.events("promise_message")][-1:]
      == [sorted(tuple(record) for group in groups for record in group["records"])],
      (groups, machine.events("promise_message")))

# A promise found in the run the escalation falls due in, which only the escalation names.
def promise_named_only_by_escalation(escalation_sender, recheck_sleep=0):
    machine = rule_five_wait_with_promises(user("go on", at(8)), assistant(PROMISE, at(8.1)),
                                           turn_end(at(8.1)))
    machine.script(dict(rechecked(False), sleep=recheck_sleep), escalation_sender, sent_ok())
    machine.run(16)
    return machine


machine = promise_named_only_by_escalation(
    {"sends": [send_to("alpha", "You have been idle; please check your work.")],
     "answer": {"sent": True, "reason": "r"}})
steps = [event["step"] for event in machine.events("message_sent")]
check("an escalation sender that drops the promise from the text it sends: the promise gets a "
      "message of its own",
      steps[-2:] == ["escalate", "nudge"] and PROMISE in machine.events("message_sent")[-1]["text"]
      and not machine.events("message_sent")[-2].get("escalation_named_records"),
      (steps, machine.events("message_sent")))

machine = promise_named_only_by_escalation(sent_ok(), recheck_sleep=2)
named = [event for event in machine.events("message_sent") if event.get("escalation_named_records")]
check("an escalation that names a promise no message named: the sentence's time moves to the "
      "escalation's send, recorded in the escalation's own message_sent event",
      len(named) == 1 and named[0]["send_started_at"] > machine.events("rule_2_sentences_on_wait")[0]["at"]
      and [event["step"] for event in machine.events("message_sent")][-1] == "escalate",
      (named, machine.events("rule_2_sentences_on_wait")))
machine.append("alpha", user("go on", "2026-11-02T12:16:01Z"),
               assistant(tool=("TaskCreate", {"subject": "report on PR 927", "metadata": {
                   "prerequisites": [{"pr_merged": 927}]}}), when="2026-11-02T12:16:01Z",
                   tool_id="t-during-recheck"),
               task_result("t-during-recheck", "Task #1 created successfully: report on PR 927",
                           "2026-11-02T12:16:01Z"),
               assistant("Recorded.", at(16.5)), turn_end(at(16.5)))
machine.script()
machine.run(23)
check("a task call made while the re-check ran, before the escalation named the promise, does not "
      "end the wait", not machine.events("wait_ended"), machine.events("wait_ended"))

# An invocation stopped after the escalation named the promise and before its sentence was logged
# as checked.
machine = promise_named_only_by_escalation(sent_ok())
machine.log.write_text("".join(
    line for line in machine.log.read_text().splitlines(keepends=True)
    if not (json.loads(line).get("agent_seat_idle_sweep_invocation_started_at") == at(16)
            and json.loads(line)["event"] in ("sentence_checked", "checked"))))
machine.script(sent_ok())
machine.run(17)
check("the promise judged again after the escalation named it gets no message of its own",
      [event["step"] for event in machine.events("message_sent")][-1] == "escalate"
      and len(machine.events("rule_2_sentences_on_wait")) == 1,
      (machine.events("message_sent"), machine.events("rule_2_sentences_on_wait")))

# --- the wait tracks each sentence it answers for, not whole groups ---------------------------------
def on_wait_sentences(machine):
    wait = idle_sweep_program.SweepLog(machine.log).open_wait("alpha")
    return [sentence for entry in wait[idle_sweep_program.SENTENCES_WITH_NO_MESSAGE_EVENT]
            for sentence in entry["sentences"]]


def stopped_after_sentences_on_wait(machine):
    """Cut the log just after its last rule_2_sentences_on_wait event, as an invocation stopped
    there leaves it."""
    lines = machine.log.read_text().splitlines(keepends=True)
    last = max(number for number, line in enumerate(lines)
               if json.loads(line)["event"] == "rule_2_sentences_on_wait")
    machine.log.write_text("".join(lines[:last + 1]))


def logged_as_checked(machine, sentence, minutes):
    record_uuid = next(record[0] for event in machine.events("rule_2_sentences_on_wait")
                       for record in event["records"] if record[1] == sentence)
    with machine.log.open("a") as log:
        log.write(json.dumps({"event": "sentence_checked", "agent_seat": "alpha", "at": at(minutes),
                              "record_uuid": record_uuid, "sentence": sentence}) + "\n")


machine = rule_five_wait_with_promises(assistant(PROMISE, at(1)), turn_end(at(1)), user("go on", at(1.05)),
                                       assistant(OTHER_PROMISE, at(1.1)), turn_end(at(1.1)))
machine.script(sent_ok())
machine.run(7)
stopped_after_sentences_on_wait(machine)
logged_as_checked(machine, OTHER_PROMISE, 7.5)
machine.script(sent_ok())
machine.run(14)
check("a message for part of the sentences logged on the wait together takes only that part off "
      "the wait, and the rest stay owed",
      [event["step"] for event in machine.events("message_sent")][-1] == "nudge"
      and on_wait_sentences(machine) == [OTHER_PROMISE],
      (machine.events("promise_message"), on_wait_sentences(machine)))

machine = promise_named_only_by_escalation(sent_ok())
machine.log.write_text("".join(
    line for line in machine.log.read_text().splitlines(keepends=True)
    if not (json.loads(line).get("agent_seat_idle_sweep_invocation_started_at") == at(16)
            and json.loads(line)["event"] in ("sentence_checked", "checked"))))
machine.append("alpha", user("go on", at(16.5)), assistant(OTHER_PROMISE, at(16.6)),
               turn_end(at(16.6)))
machine.script(sent_ok())
machine.run(23)
last = machine.events("message_sent")[-1]
check("a promise the escalation named, judged again beside a fresh promise: the message names only "
      "the fresh one",
      last["step"] == "nudge" and OTHER_PROMISE in last["text"] and PROMISE not in last["text"],
      machine.events("message_sent"))

machine = promise_named_only_by_escalation(sent_ok())
machine.log.write_text("".join(
    line for line in machine.log.read_text().splitlines(keepends=True)
    if json.loads(line)["event"] == "message_sent"
    or not (json.loads(line).get("agent_seat_idle_sweep_invocation_started_at") == at(16)
            and json.loads(line)["event"] not in ("wait_step", "rule_2_sentences_on_wait",
                                                  "judge_answer"))))
machine.script(sent_ok())
machine.run(17)
check("an invocation stopped right after the escalation's send: the sentences it named are read "
      "from its message_sent event, and get no message of their own",
      [event["step"] for event in machine.events("message_sent")][-1] == "escalate",
      machine.events("message_sent"))

machine = rule_five_wait_with_promises(assistant(OTHER_PROMISE, at(1)), turn_end(at(1)))
machine.script(sent_ok())
machine.run(7)
stopped_after_sentences_on_wait(machine)
logged_as_checked(machine, OTHER_PROMISE, 7.5)
machine.append("alpha", user("go on", at(8)), assistant(PROMISE, at(8.1)), turn_end(at(8.1)))
machine.script(rechecked(False, False),
               {"sends": [send_to("alpha", f"You have been idle. You said: {PROMISE}")],
                "answer": {"sent": True, "reason": "r"}}, sent_ok())
machine.run(16)
check("an escalation that names the fresh promise but drops an older owed sentence: the fresh "
      "promise gets no second message",
      [event["step"] for event in machine.events("message_sent")][-1] == "escalate",
      machine.events("message_sent"))

machine = promise_named_only_by_escalation(
    {"sends": [send_to("alpha", "You have been idle. You said: " + PROMISE.replace(" ", "\n", 1))],
     "answer": {"sent": True, "reason": "r"}})
check("an escalation sender that wraps a promise over two lines still names it: no second message",
      [event["step"] for event in machine.events("message_sent")][-1] == "escalate",
      machine.events("message_sent"))

if failures:
    print(f"{len(failures)} case(s) failed")
    sys.exit(1)
print("all cases passed")
