#!/usr/bin/env python3
"""Cases for the Stop hook that, during an open approval-walk, blocks the
agent's stop when its reply asks the user something outside the walk's items.

Most cases run the hook as a subprocess, its real stdin-to-stdout path, in a
scratch checkout this suite made, with a transcript this suite wrote. The model
call is never real: a fake `claude` first on PATH records each call and answers
as the case sets it. The refusal log goes to a file in the scratch directory.

With LIVE_MODEL_FLAG, the suite does not run: instead each of REAL_CASES, and
UNRELATED_ASK_CASE, runs
through the hook with the real `claude` behind a recorder first on PATH, and
the hook's decision and the real model's label for each numbered line are
printed. That run makes real model calls and asserts nothing; it exits 1 only
when `claude` is not on PATH.
"""

import ast
import contextlib
import importlib.machinery
import importlib.util
import io
import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

# Before anything runs git: a GIT_DIR or similar variable inherited from the
# caller would otherwise send this suite's `git init` into another repository.
_git_environment_fixture_spec = importlib.util.spec_from_file_location(
    "git_redirecting_environment_removal_test_fixture",
    Path(__file__).resolve().parents[4] / "scripts"
    / "git-redirecting-environment-removal-test-fixture.py")
_git_environment_fixture = importlib.util.module_from_spec(_git_environment_fixture_spec)
_git_environment_fixture_spec.loader.exec_module(_git_environment_fixture)
_git_environment_fixture.remove_git_redirecting_environment_variables_from_this_process()
_attendance_check_spec = importlib.util.spec_from_file_location(
    "agent_session_unattended_by_user_check_common",
    Path(__file__).resolve().parents[4] / "nn-systems" / "general-tools"
    / "agent-session-unattended-by-user-check-common.py")
attendance_check = importlib.util.module_from_spec(_attendance_check_spec)
_attendance_check_spec.loader.exec_module(attendance_check)

HOOK_SCRIPT = (Path(__file__).resolve().parents[1]
               / "walk-me-through-agent-question-to-user-outside-approval-walk-items-refusal-stop-hook.py")
_hook_spec = importlib.util.spec_from_file_location("question_refusal_stop_hook", HOOK_SCRIPT)
hook = importlib.util.module_from_spec(_hook_spec)
_hook_spec.loader.exec_module(hook)
# The walk-me-through skill's closing line after its link; the answer hook's suite checks SKILL.md holds it.
CLOSING_LINE_ANSWER_LETTERS = "A approve · D disapprove · M more responses"
SUITE_ROOT = Path(tempfile.mkdtemp(prefix="approval-walk-question-refusal-hook-test-")).resolve()
FAKE_BIN = SUITE_ROOT / "bin"
failures = []

ANSWER_LINE = ("Answer A to approve, AO to approve it as obvious, Aa to approve after an advisor check, D to "
               "disapprove, Z to defer, R to repeat the item, E to have it explained, or O to ask for other options.")
WALK_DOCUMENT = f"""# The poem page: approval-walk

This approval-walk settles where the poem page lives. It has 10 items.

## Item 1 of 10: the page's name

The page is named by the naming page. Recommendation: Use the name.

{ANSWER_LINE}

## Item 2 of 10: where the poem page lives

The page goes in the [wiki](file:///x/wiki), next to the glossary. Do you agree that agents look there first?

**The strongest case against:** one more page to read. Recommendation: Put it in the wiki.

{ANSWER_LINE}

## Item 3 of 10: the hook

A hook checks each written file. Recommendation: Build the hook.

{ANSWER_LINE}
"""
ITEM_2_SHOWN = """**Item 2 of 10: where the poem page lives**

The page goes in the wiki, next to the glossary. Do you agree that agents look there first?

**The strongest case against:** one more page to read. Recommendation: Put it in the wiki.

""" + ANSWER_LINE
# The minutes' `#next_to_present` line gives M as 10; once the agent adds the item a refusal asks for, the walk has 11.
M_AFTER_THE_ADDED_ITEM = "11"
M_WITH_NO_ITEM_ADDED = "10"
# Shown before every closing line the refusal gives, so that the agent copies none between backticks.
NOT_IN_BACKTICKS = ("Write the line or lines below as plain text, with no backticks around them, since the user sees "
                    "text between backticks as code.")
NO_QUESTION_SENTENCE = ("If the line asks him nothing, or only asks again for his answer to item 2, end your turn with "
                        f"the waiting item's closing line below and nothing after it. {NOT_IN_BACKTICKS}")
QUESTION_INSERT_PROGRAM = hook.QUESTION_INSERT_PROGRAM
INTERRUPTION_ITEM = f"""## Item 2.1 of 11: merge-lane-2's question about the GHI

merge-lane-2 asks: should I file one GHI listing the remaining seats' tests?

Recommendation: File it.

{ANSWER_LINE}
"""

# Real replies that show or explain the waiting item, each with that item's walk-document text; each must pass.
REAL_ITEM_5_REPLY = 'Item 5 of 23 is still waiting for your answer, so here it is again. The page linked below already shows it.\n\n## Item 5 of 23: when the rejected-rows alert repeats and clears\n\nOn 2026-10-26 you approved two rules for the rejected-rows alert (walk ghi-972-agent-seat-database-service-design-nine-remaining-decisions-approval-walk-2026-10-26, item 2):\n- While rows are still being rejected, the alert repeats 24 hours after the last one.\n- The alert\'s condition clears "after a sending-job pass that sends and has no new rejection".\n\nThis item changes the clearing rule, because it fails in two ways.\n\nExample 1: an alert reports row A. An hour later row B is rejected. The next pass sends with no new rejection, so the condition clears, and B is never reported.\n\nExample 2: on an idle Mac, no pass sends anything, so the condition never clears.\n\nThe strongest case against: No harm found; it costs only the work or a short delay.\n\n#new_if_d Alternative: keep the wording you approved on 2026-10-26.\n\nRecommendation: while the condition holds, rows rejected since the last alert set off a new alert 24 hours after the last one. A pass that finds no row rejected since the last alert clears the condition, and the next rejection then alerts at once.\n\n#new "While the condition holds, rows rejected since the last rejected-rows alert make the job write a new one 24 hours after the last; a pass that finds no row rejected since the last alert clears the condition, so the next rejection is reported on the pass that finds it."\n\n[Item 5 of 23, when the rejected-rows alert repeats and clears](https://claude.ai/artifact/G9kzSQvayD96kRMvRKsh1s) · A approve · D disapprove · M more responses'
REAL_ITEM_7_REPLY = 'Yes, item 7 is about losing ned-box\'s disk. But it doesn\'t propose solving that. It only corrects one sentence in the GHI 972 design ([docs/issues/972-a-small-service-on-ned-box-keeps-one.md](https://github.com/nedsnodes/nedsnodes/issues/972)) that promises more than the design delivers. Nothing gets built.\n\n**What the design says** (it\'s still a design; no program sends events yet):\n- A program that records an event about an agent-seat first writes it to a local events file on its own machine.\n- A sender then passes the event on to the agent-seat database service on ned-box.\n- A sent event stays in the local events file until a nightly backup holds it.\n- The backups are kept in `~/backups/agent-seat-database/` on ned-box, and the Mac copies the newest one each night.\n- After a restore, each machine sends again whatever its local events file still holds, so the record catches up.\n\n**The sentence**, from condition 1 of the design: "So a restore from the newest backup loses nothing, however long ago that backup ran."\n\n**Where the sentence is false** (a made-up example; it has never happened): ned-box\'s disk dies at 15:00, and the last backup ran at 02:00. You restore that backup from the Mac\'s copy.\n- The Mac\'s events since 02:00 are still in the Mac\'s local events file, so they come back.\n- ned-box\'s own events since 02:00 were in ned-box\'s local events file, on the dead disk, so they\'re gone.\n- The same loss hits one machine\'s events if its local events file is set aside as corrupt.\n\nSo up to a day of events can be lost, which the sentence says can\'t happen.\n\n**The proposed sentence:** "So a restore from the newest backup loses nothing that a machine\'s local events file still holds, however long ago that backup ran."\n\nThe point is that whoever runs the restore knows the record may be missing up to a day, and doesn\'t trust it as complete. I recommend approving it: it costs one sentence and nothing more. If you disapprove, the sentence stays as it is.\n\n[Item 7 of 23, "a restore from the newest backup loses nothing"](https://claude.ai/artifact/G9kzSQvayD96kRMvRKsh1s) · A approve · D disapprove · M more responses'
REAL_ITEM_1_REPLY = 'The handoff was written 16 seconds ago, so nothing has drifted. I\'m resuming the walk at item 1. The page is already published, so it stays at the same link.\n\nNo item in this walk has been ruled on yet. We resume at item 1 of 5.\n\n## Item 1 of 5: close the cold-read speed-up measurement on its first-half result\n\nOn 2026-10-03 this agent-seat started measuring whether a faster cold-read-full-run finds fewer problems than the slower one. The plan had two halves. The first half\'s interim result came in on 2026-10-04 and showed no loss: the faster run found as many of the known problems as the slower one (p=0.72, so no difference showed up; [first-half results](file:///Volumes/nedhome/nedsnodes-logs/seats/cold-read-improvement/cold-read-speed-up-measurement-first-half-2026-10-03/RESULTS-first-half-interim-2026-10-04.md)). Some scoring checks on the first half never ran, and neither did the second half.\n\nThe cold-read has changed a lot since then:\n- it now uses six reviewers instead of the old set;\n- a cold-read-fast-read now runs before every full run;\n- a rebuild is planned ([GHI 2158](https://github.com/nedsnodes/nedsnodes/issues/2158)).\n\nA second half would measure a cold-read that no longer exists.\n\n**Alternative:** plan a new measurement of today\'s cold-read once the rebuild lands.\n\n**The case against closing it:** the interim result comes from one small sample that was only partly scored, so "no loss" is weak evidence.\n\n**Recommendation:** close task #9, "Run the first half and bring results to the user", on the interim result and run no second half. Also close task #10, which only prepared the scoring checks.\n\n[Item 1 of 5 page](https://claude.ai/artifact/EZrNpowcQr6iRYHYAQCDHJ) · A approve · D disapprove · M more responses'
REAL_ITEM_3_1_REPLY = 'Item 3 is approved and recorded.\n\n`#new` text 1, "Proposed: that hook also gives every subagent a folder of...": fast read had to be run (/home/nedlern/agents/cold-read-improvement/cold-read-records/cold-read-improvement-open-items-2026-10-30-item-3-of-5-new-1-2026-10-30).\n\nNone of its findings changed what the item decides. I made one wording fix: "that hook" became "the Agent-tool pointer hook". A background subagent is building the scratch-folder hook. It will test it end to end, then send the pull request to merge-lane-2. The pointer to the briefs wiki page waits until that page exists, because a pointer to a missing page would be broken.\n\nI added item 3.1 from your remark about the reason against, so the walk now has 6 items. I also removed a line from the memory index that pointed at a note that doesn\'t exist.\n\n## Item 3.1 of 6: "more work for agents" is not a case against\n\nEvery approval-walk item states the strongest case against its recommendation, just before the recommendation. Item 3\'s case against was "a hook that edits briefs is more code to build and test than one sentence". You answered: "The reason against is the usual, this is more work." The time agents spend building something costs you almost nothing. What costs you is what you have to read and rule on.\n\nI tried to save that as a note in Claude Code\'s memory, and the instruction-file guard refused: a memory note is not read at the moment it applies. The place an agent would meet the rule is this sentence in the walk-me-through skill, `.claude/skills/walk-me-through/SKILL.md`: "Just before each recommendation, state in one sentence the strongest case against it."\n\n**Proposed:** add after that sentence: "The work agents must do to build it is not a case against; more for the user to read or rule on is. When you find no other case against, write "The case against this recommendation: none found.""\n\n**The alternative:** leave the skill as it is, and you keep pointing it out when an item does it.\n\n**The case against this recommendation:** an agent barred from the easy reason may reach for a vague one instead of writing "none found". An example is "this could have unforeseen effects".\n\n**Recommendation:** add the two sentences to the walk-me-through skill.\n\n[Item 3.1 of 6, "more work for agents" is not a case against](https://claude.ai/artifact/LXin9KHmdixhJGn3Hm3Fgx) · A approve · D disapprove · M more responses'
REAL_ITEM_5_DOCUMENT_TEXT = '## Item 5 of 23: when the rejected-rows alert repeats and clears\n\nYou approved on 2026-10-26 that the rejected-rows alert repeats 24 hours after the last one while rows are still rejected, and clears "after a sending-job pass that sends and has no new rejection" (walk ghi-972-agent-seat-database-service-design-nine-remaining-decisions-approval-walk-2026-10-26, item 2); this changes it because the clearing rule fails two ways.\n\nExample 1: an alert reports row A; an hour later row B is rejected; the next pass sends with no new rejection, so the condition clears and B is never reported. Example 2: on an idle Mac no pass sends anything, so the condition never clears.\n\nThe strongest case against: No harm found; it costs only the work or a short delay.\n\n#new_if_d Alternative: keep the user-ruling\'s wording.\n\nRecommendation: while the condition holds, rows rejected since the last alert make a new alert 24 hours after the last one; a pass with no rejection since the last alert clears the condition, and the next rejection then alerts at once.\n\n#new "While the condition holds, rows rejected since the last rejected-rows alert make the job write a new one 24 hours after the last; a pass that finds no row rejected since the last alert clears the condition, so the next rejection is reported on the pass that finds it."\n'
REAL_ITEM_7_DOCUMENT_TEXT = '## Item 7 of 23: "a restore from the newest backup loses nothing"\n\nCondition 1 says each machine keeps sent events until a backup holds them, "So a restore from the newest backup loses nothing, however long ago that backup ran." You approved that sentence on 2026-10-14 (walk ghi-972-seat-service-design-open-defects-2026-10-14, item 9); this changes it because it fails when the restore follows the loss of ned-box\'s disk, since ned-box\'s own local events file goes with it, and when a machine\'s local file was set aside as corrupt after that backup.\n\n\nThe strongest case against: No harm found; it costs only the work or a short delay.\n\n#new_if_d Alternative: leave the sentence.\n\nRecommendation: qualify the promise, so whoever runs a restore after a disk loss, or after a local events file was set aside as corrupt, does not expect a complete record.\n\n#new "So a restore from the newest backup loses nothing that a machine\'s local events file still holds, however long ago that backup ran."\n'
REAL_ITEM_1_DOCUMENT_TEXT = '## Item 1 of 5: close the cold-read speed-up measurement on its first-half result\n\nOn 2026-10-03 this agent-seat started a measurement: does a faster cold-read-full-run find fewer problems than the slower one? The measurement was planned in two halves, each a set of documents run both ways. The first half\'s interim result, on 2026-10-04, showed no loss: the faster run found as many of the known problems as the slower one (p=0.72, so no difference showed; [first-half results](file:///Volumes/nedhome/nedsnodes-logs/seats/cold-read-improvement/cold-read-speed-up-measurement-first-half-2026-10-03/RESULTS-first-half-interim-2026-10-04.md)). Some scoring checks on the first half, and the whole second half, never ran.\n\nSince then the cold-read has changed a great deal: six reviewers instead of the old set, a cold-read-fast-read before every full run, and a planned rebuild ([GHI 2158, Rebuild the /cold-read skill so its programs do the mechanical steps and print each instruction when the agent needs it](https://github.com/nedsnodes/nedsnodes/issues/2158)). A second half would measure a cold-read that no longer exists.\n\nAlternative: plan a new measurement of today\'s cold-read, after the rebuild lands.\n\nThe case against this recommendation: the interim result rests on one small, partly scored sample, so "no loss" is weak evidence.\n\nRecommendation: close task #9, "Run the first half and bring results to the user", on the interim result, run no second half, and close task #10, which only prepared the scoring checks.\n'
REAL_ITEM_3_1_DOCUMENT_TEXT = '## Item 3.1 of 6: "more work for agents" is not a case against\n\nEvery approval-walk item states, just before its recommendation, "the strongest case against it". Item 3 gave "a hook that edits briefs is more code to build and test than one sentence", and you answered: "The reason against is the usual, this is more work." The time agents spend building something costs you almost nothing; what costs you is what you have to read and rule on. I tried to save that as a note in Claude Code\'s memory, and the instruction-file guard refused: a memory note is not read at the moment it applies. The place an agent would meet the rule is this sentence in the walk-me-through skill, `.claude/skills/walk-me-through/SKILL.md`: "Just before each recommendation, state in one sentence the strongest case against it."\n\n#new Proposed: add after that sentence: "The work agents must do to build it is not a case against; more for the user to read or rule on is. When you find no other case against, write "The case against this recommendation: none found.""\n\nThe alternative: leave the skill as it is, and you keep pointing it out when an item does it.\n\nThe case against this recommendation: an agent barred from the easy reason may reach for a vague one, such as "this could have unforeseen effects", instead of writing "none found".\n\nRecommendation: add the two sentences to the walk-me-through skill.\n'
REAL_CASES = (
    ("a reply showing item 5 again with its recommendation reworded", REAL_ITEM_5_REPLY, REAL_ITEM_5_DOCUMENT_TEXT,
     "#next_to_present item 5 of 23",
     "Recommendation: while the condition holds, rows rejected since the last alert set off a new alert 24 hours "
     "after the last one."),
    ("an explanation of item 7 ending on its recommendation", REAL_ITEM_7_REPLY, REAL_ITEM_7_DOCUMENT_TEXT,
     "#next_to_present item 7 of 23", "I recommend approving it: it costs one sentence and nothing more."),
    ("a reply showing item 1 with its recommendation reworded", REAL_ITEM_1_REPLY, REAL_ITEM_1_DOCUMENT_TEXT,
     "#next_to_present item 1 of 5", "Recommendation: close task #9,"),
    ("a reply showing item 3.1 with its `#new Proposed:` line in bold", REAL_ITEM_3_1_REPLY,
     REAL_ITEM_3_1_DOCUMENT_TEXT, "#next_to_present item 3.1 of 6", None))
UNRELATED_ASK = "I recommend we also delete the 37 finished topic-worktrees today, if you agree."
UNRELATED_ASK_CASE = ("item 1's reply with an unrelated ask added, which must block",
                      REAL_ITEM_1_REPLY.replace("\n\n[Item 1 of 5 page]", f"\n\n{UNRELATED_ASK}\n\n[Item 1 of 5 page]"),
                      REAL_ITEM_1_DOCUMENT_TEXT, "#next_to_present item 1 of 5", None)
REAL_ITEM_3_1_PROPOSED_LINE =next(line for line in REAL_ITEM_3_1_REPLY.split("\n") if line.startswith("**Proposed:**"))


# The fake answers each call for the one line it is given, the N-th question-like line by its id `L<N>`: `no` calls
# it no ask; `yes:N` (N 1 by default) calls line N an ask and the rest none; `asks:<json list>` gives line N the
# list's N-th true or false; `verdict:<json>` gives the whole structured output as written; `fail:N` fails line N's
# call only; `sleep:S` waits S seconds, then calls the line no ask; the other modes fail every call each its own way.
FAKE_CLAUDE = """#!/usr/bin/env python3
import json, os, sys, time
prompt = sys.stdin.read()
with open(os.environ["FAKE_CLAUDE_CALLS"], "a") as calls:
    calls.write(json.dumps({"argv": sys.argv[1:], "stdin": prompt}) + "\\n")
mode = os.environ.get("FAKE_CLAUDE_MODE", "no")
entry = json.loads(prompt.split("The lines, as JSON:\\n", 1)[1])[0]
number = int(entry["id"][1:])
if mode.startswith("verdict:"):
    print(json.dumps({"type": "result", "is_error": False, "structured_output": json.loads(mode[len("verdict:"):])}))
    sys.exit(0)
if mode.startswith("asks:"):
    ask = json.loads(mode[len("asks:"):])[number - 1]
else:
    ask = mode.startswith("yes") and number == (int(mode.split(":")[1]) if ":" in mode else 1)
verdict = {"labels": [{"id": entry["id"], "ask": ask, "reason": "the fake's answer"}]}
if mode == "sleep":
    time.sleep(30)
if mode.startswith("sleep:"):
    time.sleep(float(mode.split(":")[1]))
if mode == "fail" or mode == f"fail:{number}":
    print(json.dumps({"type": "result", "is_error": True, "result": "Not logged in"}))
    sys.exit(1)
if mode == "garbage":
    print("not json")
    sys.exit(0)
if mode == "stderr-only":
    print("Not logged in. Run claude login.", file=sys.stderr)
    sys.exit(1)
if mode == "error-exit-0":
    print(json.dumps({"type": "result", "is_error": True, "result": "API overloaded",
                      "structured_output": verdict}))
    sys.exit(0)
print(json.dumps({"type": "result", "is_error": False, "structured_output": verdict}), flush=True)
if mode == "verdict-exit-1":
    sys.exit(1)
if mode == "verdict-then-killed":
    import signal
    os.kill(os.getpid(), signal.SIGKILL)
"""

def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


def opening_prompt(turn_origin, text, **fields):
    return {"type": "user", "turnOrigin": turn_origin, **fields,
            "message": {"role": "user", "content": [{"type": "text", "text": text}]}}


USER_PROMPT = opening_prompt("human", "A", origin={"kind": "human"}, promptSource="typed")
PEER_PROMPT = opening_prompt("peer", "Another Claude session sent a message: should I file one GHI?",
                             origin={"kind": "peer"}, isMeta=True, promptSource="system")


def text_record(text):
    return {"type": "assistant", "message": {"content": [{"type": "text", "text": text}]}}


def tool_record(name, tool_input):
    return {"type": "assistant", "message": {"content": [{"type": "tool_use", "name": name, "input": tool_input}]}}


class Case:
    """One case's own checkout, walk files, transcript, fake model and log."""

    counter = 0

    def __init__(self, minutes="#next_to_present item 2 of 10", document=WALK_DOCUMENT):
        Case.counter += 1
        self.root = SUITE_ROOT / f"case-{Case.counter}"
        self.checkout = self.root / "checkout"
        self.checkout.mkdir(parents=True)
        subprocess.run(["git", "init", "-q", str(self.checkout)], check=True)
        self.walk = self.checkout / "docs" / "walk"
        self.walk.mkdir(parents=True)
        self.document = self.walk / "poem-page-2026-10-12.md"
        self.document.write_text(document)
        self.minutes = self.walk / "poem-page-2026-10-12-minutes.md"
        self.minutes.write_text(f"# Minutes\n\n{minutes}\n")
        self.transcript = self.root / "transcript.jsonl"
        self.calls = self.root / "model-calls.jsonl"
        self.log = self.root / "refusals.jsonl"

    def records(self, *records):
        self.transcript.write_text("".join(json.dumps(record) + "\n" for record in records))

    def reply(self, *texts, opening=USER_PROMPT):
        self.records(opening, *(text_record(text) for text in texts))

    def run(self, model="yes", stop_hook_active=False, last_assistant_message=None, environment_extra=None,
            stdin_text=None, bin_directory=FAKE_BIN):
        payload = {"hook_event_name": "Stop", "session_id": "test-session",
                   "transcript_path": str(self.transcript), "cwd": str(self.checkout),
                   "stop_hook_active": stop_hook_active}
        if last_assistant_message is not None:
            payload["last_assistant_message"] = last_assistant_message
        environment = attendance_check.environment_without_agent_session_attendance_variables(os.environ)
        environment.update({"PATH": f"{bin_directory}{os.pathsep}{os.environ['PATH']}",
                            "FAKE_CLAUDE_CALLS": str(self.calls), "FAKE_CLAUDE_MODE": model,
                            hook.LOG_PATH_VARIABLE: str(self.log),
                            # The machine's real emergency-stop folder must not decide a case.
                            "NEDSNODES_EMERGENCY_STOP_FOLDER": str(self.calls.parent / "no-emergency-stop")})
        environment.update(environment_extra or {})
        return subprocess.run([sys.executable, str(HOOK_SCRIPT)],
                              input=json.dumps(payload) if stdin_text is None else stdin_text,
                              capture_output=True, text=True, env=environment, cwd=self.checkout)

    def model_calls(self):
        if not self.calls.exists():
            return []
        return [json.loads(line) for line in self.calls.read_text().splitlines()]

    def logged(self):
        if not self.log.exists():
            return []
        return [json.loads(line) for line in self.log.read_text().splitlines()]


def blocked_reason(result):
    if result.returncode != 0 or not result.stdout.strip():
        return None
    output = json.loads(result.stdout)
    return output["reason"] if output.get("decision") == "block" else None


def check_silent(case_name, result):
    check(case_name, result.returncode == 0 and result.stdout == "",
          f"exit {result.returncode}, stdout {result.stdout!r}, stderr {result.stderr!r}")


def check_blocked(case_name, result, *phrases):
    reason = blocked_reason(result)
    check(case_name, reason is not None and all(phrase in reason for phrase in phrases),
          f"exit {result.returncode}, stdout {result.stdout!r}, stderr {result.stderr!r}")


def test_a_question_mark_or_an_ask_phrase_sends_the_line_to_the_model_and_a_block_is_logged():
    case = Case()
    case.reply("The tests passed.\n\nShould I merge the pull request now?\n\nItem 2 of 10 is waiting for your answer.")
    result = case.run(model="yes")
    check_blocked("a sentence ending in a question mark blocks when the model says it asks the user something", result,
                  '"Should I merge the pull request now?"', "the model judged that it asks him something")
    calls = case.model_calls()
    check("a sentence ending in a question mark goes to the model",
          len(calls) == 1 and judged_line(calls[0]) == "Should I merge the pull request now?", calls)
    entries = case.logged()
    check("the refusal is logged with its time, session, walk, sentence and what decided",
          len(entries) == 1 and entries[0]["session"] == "test-session"
          and entries[0]["walk"] == "poem-page-2026-10-12"
          and entries[0]["sentence"] == "Should I merge the pull request now?"
          and entries[0]["decided_by"] == "model" and entries[0]["time"].endswith("+00:00"), entries)
    check_silent("a sentence ending in a question mark passes when the model says it asks nothing",
                 case.run(model="no"))
    check_blocked("a sentence ending in a question mark blocks when the model check fails", case.run(model="fail"),
                  '"Should I merge the pull request now?"', "the hook's `claude -p` call that has the model judge")
    for case_name, text in (
            ("`say yes`", "The fix is ready. Say yes and I will push it."),
            ("`answer A`", "The fix is ready. Answer A and I will push it."),
            ("`waiting for your answer` on a question that is not an item",
             "The cleanup of the old directories is still waiting for your answer."),
            ("a bold question", "**Do you agree with merging the two lines?** A: merge. D: keep both."),
            ("a cue split by bold marks, once the marks are dropped", "**Should** I go ahead with the merge."),
            ("a question relayed in quotes from another agent",
             'merge-lane-2 asks: "Should the hook be fixed today?" I recommend yes.')):
        case = Case()
        case.reply(text)
        check_blocked(case_name + " blocks when the model says it asks the user something", case.run(model="yes"),
                      "approval-walk question check", "the model judged that it asks him something")
        check_silent(case_name + " passes when the model says it asks nothing", case.run(model="no"))
        check(case_name + " goes to the model each time", len(case.model_calls()) == 2, case.model_calls())


# Lines agents wrote during approval-walks, one of each kind that holds a `?` or an ask phrase but asks the user nothing.
LOGGED_LINES_THAT_ASK_NOTHING = (
    ("the walk-me-through skill's answer line, with its item not shown", ANSWER_LINE),
    ("an answer to his question that restates the question first",
     "**Do we need it?** The processes cost nothing so far. The /tmp quota did stop work yesterday, so a daily /tmp "
     "check passes the project's bar for adding a guard: that failure has already happened. The process part is "
     "cheap to include with it."),
    ("the advisor-check questions the walk-me-through skill has the agent write",
     "Walk-start advisor call, on the draft above. Does anything change what the items decide? Then the six "
     "questions."),
    ("the waiting item's recommendation reworded", "Recommendation: answer A if the disk is back, or D if it isn't."),
    ("a check of what his last message meant as an answer to the waiting item",
     "I'm taking your \"Yeah\" as A, approve. Reply A to confirm."),
    ("a question routed to a later walk item",
     "One thing waits on you later, not now. Before merging that pull request, merge-lane-2 needs your approval of "
     "the not-restarted message it adds. I'll bring that to you once questions are allowed again."),
    ("an ask phrase inside a negation", "cold-read-improvement says the docstring fix for the record-names guard's "
     "list of what it does not catch is up for review: [PR 2368](https://github.com/nedsnodes/nedsnodes/pull/2368)."
     " Nothing here needs your answer."),
    ("a status report", "I'm continuing your request from the last session: everything that needs your ruling is "
     "collected into one approval-walk. Meanwhile, without needing you, I merged two GHI-MD pull requests, checked "
     "eight rulings that earlier pull requests had cited (all eight match your own words in the transcripts), and "
     "restarted the code-review queue in the background."),
    ("a question the agent asks itself", "Now #310 and #315's cleanup checks: are the locked worktrees free yet?"),
)


def test_each_kind_of_logged_line_that_asks_nothing_passes_once_the_model_says_so():
    for case_name, line in LOGGED_LINES_THAT_ASK_NOTHING:
        case = Case()
        case.reply("PR 1922 merged.\n\n" + line)
        check_silent(f"{case_name} passes when the model says it asks nothing", case.run(model="no"))
        calls = case.model_calls()
        check(f"{case_name} goes to the model", len(calls) == 1 and judged_line(calls[0]), calls)


def insert_command_from(reason, title="merge-lane-2's question about the merge", category="fix_next", waits_on=()):
    """The argument list of the command the refusal gives, its placeholders filled in, or None."""
    line = next((line for line in reason.split("\n") if line.startswith("python3 ")), None)
    if line is None:
        return None
    arguments = shlex.split(line)
    arguments[arguments.index(hook.QUESTION_INSERT_COMMAND_TITLE_ARGUMENT_PLACEHOLDER)] = title
    arguments[arguments.index(hook.QUESTION_INSERT_COMMAND_CATEGORY_ARGUMENT_PLACEHOLDER)] = category
    for each in waits_on:
        arguments += ["--waits-on", each]
    arguments[0] = sys.executable
    return arguments


def run_insert_command(case, reason, **keywords):
    arguments = insert_command_from(reason, **keywords)
    if arguments is None:
        return None
    return subprocess.run(arguments, capture_output=True, text=True, cwd=case.checkout)


def test_the_item_the_block_message_asks_for_is_one_the_close_step_can_place():
    case = Case()
    case.reply("Should I merge the pull request now?")
    reason = blocked_reason(case.run()) or ""
    close_spec = importlib.util.spec_from_file_location("check_and_close", hook.WALK_CHECK_PROGRAM)
    close = importlib.util.module_from_spec(close_spec)
    close_spec.loader.exec_module(close)
    check("the message names every category the close step reads",
          all(f"`{category}`" in reason for category in close.WALK_CATEGORIES), reason)
    result = run_insert_command(case, reason)
    check("the command the message gives adds the item", result is not None and result.returncode == 0,
          result and (result.stdout, result.stderr))
    document = case.document.read_text()
    parser = hook.walk_finder.markdown_parser()
    units = hook.walk_finder.item_unit_spans(document, parser)
    try:
        placing = close.unshown_items_placing(hook.walk_finder, document, units, parser, "walk.md", "2026-11-11")
    except close.WalkOrderUnusable as problem:
        placing = problem
    check("the item the command adds is placed by the close step's walk order",
          isinstance(placing, dict) and [key[0] for key, _ in placing.values()] == [1], placing)


def test_the_block_message_says_what_to_do():
    case = Case()
    case.reply("Should I merge the pull request now?")
    reason = blocked_reason(case.run()) or ""
    command = (f"python3 {QUESTION_INSERT_PROGRAM} --cwd {case.checkout} --title '<the point of the question>' "
               "--category '<category>' --flagged-line 'Should I merge the pull request now?'")
    expected = (
        "[rule walk-me-through-agent-question-to-user-outside-walk-items-refused] approval-walk question check: this "
        "hook refused to end your turn, because a line of your reply seems to ask the user something outside the "
        "items of the open approval-walk poem-page-2026-10-12 (the model judged that it asks him something): "
        "\"Should I merge the pull request now?\". His next letter answers only the waiting item, item 2, so it "
        "cannot also answer this line's question.\n"
        f"{NO_QUESTION_SENTENCE}\n"
        f"[Item 2 of {M_WITH_NO_ITEM_ADDED}, where the poem page lives](<page link>) · {CLOSING_LINE_ANSWER_LETTERS}\n"
        "The minutes record no `#item_page` line for item 2. For each such item, publish its page first if it has "
        f"none and add to {case.minutes} the line `#item_page item <N> of <M> <the page's link>`, which this hook "
        "reads back; then put the same link in place of `<page link>` in the item's closing line.\n"
        "Otherwise run this command, with the question's point as its title, the category for how soon its work "
        "must happen, one of `must_fix_now`, `fix_next`, `fix_during_maintenance`, "
        "`file_an_improvement_feature_or_change`, as the walk-me-through skill's section \"Re-planning\" says, and, "
        "for each item it must follow, a `--waits-on` with that item's heading without its `## ` and any `Item N of M: `, then "
        "do what it prints; do not show the new item now, since the walk shows it when its turn comes:\n"
        f"{command}")
    check("the refusal is the opening, the line for text that asks nothing with its one closing line, and the "
          "command for a question", reason == expected, f"{reason!r}\n!=\n{expected!r}")
    check("the refusal gives one closing line, with the walk's own count",
          f"Item 2 of {M_AFTER_THE_ADDED_ITEM}" not in reason and reason.count(CLOSING_LINE_ANSWER_LETTERS) == 1,
          reason)


def test_the_command_writes_the_item_and_prints_the_closing_line_with_the_count_raised():
    case = Case(minutes="#item_page item 2 of 10 https://claude.ai/artifact/p2\n#next_to_present item 2 of 10")
    case.reply("PR 1922 merged.\n\n- `x` is done.\n- Should I merge the pull request now?")
    reason = blocked_reason(case.run()) or ""
    result = run_insert_command(case, reason, waits_on=("where the poem page lives",))
    output = result.stdout if result else ""
    document = case.document.read_text()
    item = document[document.index("## merge-lane-2's question about the merge"):]
    check("the command adds the item after the waiting item, with its category, waits-on and first-entered lines, "
          "each flagged line on a line of its own and the case-against line to fill in",
          document.index("## Item 2 of 10") < document.index("## merge-lane-2's question") < document.index(
              "## Item 3 of 10")
          and "#approval_walk_item_in_category_fix_next\n#approval_walk_item_waits_on where the poem page lives\n"
              "#approval_walk_item_first_entered " in item
          and "\n\nPR 1922 merged.\n\n" not in item
          and "\n- Should I merge the pull request now?\n" in item
          and "\n#case_against <rating>: <the strongest case against your recommendation>\n" in item, item)
    check("the command records the re-planning in the minutes",
          "added the unnumbered item `merge-lane-2's question about the merge` after the whole of item 2"
          in case.minutes.read_text(), case.minutes.read_text())
    check("the command prints the closing line with the walk's count raised by the item it added",
          output.endswith(f"{NOT_IN_BACKTICKS}\n[Item 2 of {M_AFTER_THE_ADDED_ITEM}, where the poem page lives]"
                          f"(https://claude.ai/artifact/p2) · {CLOSING_LINE_ANSWER_LETTERS}\n"), output)
    case.reply("- Should I merge the pull request now?\n\nI added the question to the walk as a new item.\n\n"
               f"[Item 2 of {M_AFTER_THE_ADDED_ITEM}, where the poem page lives](https://claude.ai/artifact/p2) · "
               f"{CLOSING_LINE_ANSWER_LETTERS}")
    check_silent("once the command has added it, the question passes", case.run(model="yes"))
    case.reply(f"[Item 2 of {M_WITH_NO_ITEM_ADDED}, where the poem page lives](https://claude.ai/artifact/p2) · "
               f"{CLOSING_LINE_ANSWER_LETTERS}")
    check_silent("the reply the refusal asks for when the line asks nothing, the closing line alone, passes",
                 case.run(model="yes"))


# The line agent-instructions-editor wrote on 2026-11-26 after showing its waiting item 36 again, just before that
# item's closing line, when it could not tell whether the user's "I would too. Yeah." answered the item.
REAL_RE_ASK_LINE = ("I couldn't tell whether \"I would too. Yeah.\" answered this item, so nothing is recorded yet. "
                    "Reply A to send this version to merge-lane-2.")


def test_a_line_that_asks_again_for_the_waiting_items_letter_passes_before_its_closing_line():
    case = Case()
    case.reply(f"{ITEM_2_SHOWN}\n\n{REAL_RE_ASK_LINE}\n\n{closing_line('2 of 10')}")
    check_silent("the real re-ask of the waiting item, ending with its closing line, passes", case.run(model="yes"))
    check("the real re-ask never reaches the model", case.model_calls() == [], case.model_calls())
    for case_name, text in (
            ("the same re-ask in a message that does not end with the waiting item's closing line goes to the model",
             f"{ITEM_2_SHOWN}\n\n{REAL_RE_ASK_LINE}"),
            ("a re-ask ending with another item's closing line goes to the model",
             f"{REAL_RE_ASK_LINE}\n\n{closing_line('3 of 10')}"),
            ("a question beside the letter request goes to the model",
             f"Should I also delete the old branch? Reply A to do both.\n\n{closing_line('2 of 10')}"),
            ("a letter request that asks a question itself goes to the model",
             f"Reply A if you want me to delete the old branch too?\n\n{closing_line('2 of 10')}"),
            ("a letter request followed by an ask phrase goes to the model",
             f"Reply A and tell me which branch to delete.\n\n{closing_line('2 of 10')}")):
        case = Case()
        case.reply(text)
        check_blocked(case_name, case.run(model="yes"), "approval-walk question check")


def test_the_command_refuses_with_no_open_walk_and_prefixes_a_numbered_title():
    case = Case()
    case.minutes.write_text("# Minutes\n\n#next_to_present none, closed\n")
    result = subprocess.run([sys.executable, str(QUESTION_INSERT_PROGRAM), "--cwd", str(case.checkout), "--title", "t",
                             "--category", "fix_next", "--flagged-line", "Should I?"],
                            capture_output=True, text=True)
    check("the command exits 1 and changes nothing when no approval-walk is open",
          result.returncode == 1 and "no approval-walk is open" in result.stderr
          and case.document.read_text() == WALK_DOCUMENT, (result.returncode, result.stderr))
    case = Case()
    subprocess.run([sys.executable, str(QUESTION_INSERT_PROGRAM), "--cwd", str(case.checkout), "--title",
                    "Item 9 of 9: reboot", "--category", "fix_next", "--flagged-line", "Should I?"],
                   capture_output=True, text=True, check=True)
    check("a title a `##` heading would read as numbered gets the prefix `Question: `",
          "\n## Question: Item 9 of 9: reboot\n" in case.document.read_text(), case.document.read_text())


def test_a_reply_with_nothing_question_like_passes():
    case = Case()
    for case_name, text in (
            ("a plain report passes", "The background job finished, and its report is in the log-store."),
            ("the waiting-item line the skill requires passes",
             "PR 1922 merged.\n\nItem 2 of 10 is waiting for your answer."),
            ("a question in a code span passes", "I ran `grep -c 'why?' notes.md` and found none."),
            ("a question in a code block passes", "The test prints:\n\n```\nShould I retry?\n```\n\nIt retried once."),
            ("`answer a` followed by a noun is the article, not the letter A, so it passes",
             "> When you answer a finding with a new rule, check the rule against the program's real output.")):
        case.reply(text)
        check_silent(case_name, case.run(model="yes"))
    check("a reply with nothing question-like never calls the model", case.model_calls() == [], case.model_calls())


def test_a_question_like_line_goes_to_the_model():
    case = Case()
    case.reply("The fix has a second part, and I recommend building it next.")
    result = case.run(model="yes:1")
    check_blocked("a question-like line the model says asks the user blocks", result,
                  '"The fix has a second part, and I recommend building it next."',
                  "the model judged that it asks him something")
    calls = case.model_calls()
    argv = calls[0]["argv"] if calls else []
    check("the model is called once, as Haiku, with every hook disabled and no session file",
          len(calls) == 1 and argv[argv.index("--model") + 1] == hook.MODEL == "claude-haiku-5-5"
          and json.loads(argv[argv.index("--settings") + 1]) == {"disableAllHooks": True, "advisorModel": ""}
          and "--no-session-persistence" in argv, calls)
    check("the model is given the labelling prompt and, as JSON, the question-like line, the message, the waiting "
          "item's text and the message that started the turn with who sent it",
          calls and calls[0]["stdin"].startswith(hook.QUESTION_LIKE_LINE_ASK_LABELLING_MODEL_PROMPT)
          and judged_entry(calls[0]) == {
              "id": "L1", "line": "The fix has a second part, and I recommend building it next.",
              "turn_started_by": "human", "message_that_started_the_turn": "A",
              "agent_message_holding_the_line": "The fix has a second part, and I recommend building it next.",
              "waiting_walk_item_text": judged_entry(calls[0])["waiting_walk_item_text"]}
          and judged_entry(calls[0])["waiting_walk_item_text"].startswith("## Item 2 of 10"), calls)
    check("a block the model decided is logged as the model's",
          [entry["decided_by"] for entry in case.logged()] == ["model"], case.logged())
    check_silent("a question-like line the model says asks nothing passes", case.run(model="no"))
    case.reply("Waiting on you: should line 34 change, as item 2 of 10 asks?")
    check_silent("a question on a line naming an item goes to the model too", case.run(model="no"))
    case.reply("I recommend building it next.\n\nThat also fixes the second part, if you agree with the plan.")
    check_blocked("the line the model calls an ask is the sentence named", case.run(model="yes:2"),
                  '"That also fixes the second part, if you agree with the plan."')


def judged_entry(call):
    return json.loads(call["stdin"][len(hook.QUESTION_LIKE_LINE_ASK_LABELLING_MODEL_PROMPT):])[0]


def judged_line(call):
    return judged_entry(call)["line"]


def test_a_line_about_only_the_waiting_items_decision_passes():
    for case_name, reply, item_text, minutes, reworded in REAL_CASES:
        case = Case(document=f"# A walk\n\n{item_text}\n", minutes=minutes)
        case.reply(reply)
        check_silent(f"{case_name} passes when the model calls none of its lines an ask", case.run(model="no"))
        calls = case.model_calls()
        if reworded is None:
            check(f"{case_name}: the model is not given the `#new Proposed:` line",
                  all(REAL_ITEM_3_1_PROPOSED_LINE.replace("**", "") not in judged_line(call) for call in calls),
                  calls)
            continue
        check(f"{case_name}: the model is given the waiting item's text and the reworded line",
              calls and all(item_text.split("\n")[0] in judged_entry(call)["waiting_walk_item_text"] for call in calls)
              and any(reworded in judged_line(call) for call in calls), calls)
        check_blocked(f"{case_name} still blocks when the model calls a line an ask",
                      case.run(model="yes"), "the model judged that it asks him something")
    case = Case(document=f"# A walk\n\n{REAL_ITEM_3_1_DOCUMENT_TEXT}\n", minutes="#next_to_present item 3.1 of 6")
    heading = REAL_ITEM_3_1_DOCUMENT_TEXT.split("\n")[0]
    closing = REAL_ITEM_3_1_REPLY.rstrip().split("\n")[-1]
    case.reply(f"{heading}\n\n{REAL_ITEM_3_1_PROPOSED_LINE}\n\n{closing}")
    check_silent("a `#new Proposed:` line shown as `**Proposed:**` matches the walk-document's line",
                 case.run(model="yes"))
    check("a `#new Proposed:` line shown as `**Proposed:**` never reaches the model", case.model_calls() == [],
          case.model_calls())
    case.reply(f"{heading}\n\n#new {REAL_ITEM_3_1_PROPOSED_LINE.replace('**', '')}\n\n{closing}")
    check_silent("the walk-document's `#new Proposed:` line copied with its marker matches too", case.run(model="yes"))
    check("a hashtag marker is dropped only when a word character follows `#`, so a heading keeps its text",
          hook.normalized("#new_if_d Alternative: x") == "alternative: x" and hook.normalized("## Item 3") == "item 3"
          and hook.normalized("#9 is closed") == "is closed", hook.normalized("#new_if_d Alternative: x"))


def test_while_a_sub_step_waits_the_interruption_item_goes_after_the_whole_item():
    case = Case(document=f"# A walk\n\n{REAL_ITEM_3_1_DOCUMENT_TEXT}\n## Item 4 of 6: next\n\nRecommendation: go.\n",
                minutes="#next_to_present item 3.1 of 6")
    case.reply("Should I merge the pull request now?")
    result = run_insert_command(case, blocked_reason(case.run(model="yes")) or "")
    document = case.document.read_text()
    check("while sub-step 3.1 waits, the command puts the interruption item after the whole of item 3, not between "
          "its sub-steps", result is not None and result.returncode == 0
          and 0 <= document.find("## Item 3.1 of 6") < document.find("## merge-lane-2's question")
          < document.find("## Item 4 of 6"),
          document)


def test_a_question_about_something_other_than_the_waiting_item_still_blocks():
    _, reply, item_text, minutes, _ = UNRELATED_ASK_CASE
    case = Case(document=f"# A walk\n\n{item_text}\n", minutes=minutes)
    unrelated = UNRELATED_ASK
    case.reply(reply)
    result = case.run(model="asks:[false, true]")
    check_blocked("an unrelated ask without a question mark, called an ask, blocks", result,
                  f'"{unrelated}"', "the model judged that it asks him something")
    case.reply(REAL_ITEM_1_REPLY.replace("**Recommendation:** close task #9",
                                         "**Recommendation:** shall I close task #9"))
    calls_before = len(case.model_calls())
    check_silent("a reworded recommendation holding an ask phrase passes when the model calls it no ask",
                 case.run(model="no"))
    calls = case.model_calls()[calls_before:]
    check("a reworded recommendation holding an ask phrase goes to the model",
          any("shall I close task #9" in judged_line(call) for call in calls), calls)
    case.reply(REAL_ITEM_1_REPLY.replace("Also close task #10, which only prepared the scoring checks.",
                                         "Do you approve closing task #10 too?"))
    check_blocked("a reworded recommendation ending in a question mark blocks when the model says it asks something "
                  "else", case.run(model="yes"), 'Do you approve closing task #10 too?"',
                  "the model judged that it asks him something")


def judgement(lines, **keywords):
    index, failure = hook.model_judgement(lines, range(len(lines)), "## Item 2 of 10", "human", "A", **keywords)
    return None if index is None else lines[index], failure


def test_a_failed_model_check_blocks():
    case = Case()
    case.reply("The fix has a second part, and I recommend building it next.")
    for case_name, mode, phrase in (
            ("a model call that exits nonzero blocks", "fail", "claude exited 1"),
            ("a model call that prints no verdict blocks, quoting its output", "garbage", "without a verdict (JSONDecodeError"),
            ("the output of a call with no verdict is quoted", "garbage", "): not json"),
            ("a model call that writes only to stderr blocks, quoting stderr", "stderr-only",
             "Not logged in. Run claude login."),
            ("a model call that reports an error with exit 0 blocks", "error-exit-0",
             "claude exited 0 reporting an error: API overloaded"),
            ("a model call that prints a verdict but exits 1 blocks", "verdict-exit-1",
             "claude exited 1 reporting an error"),
            ("a model call killed by a signal after printing a verdict blocks", "verdict-then-killed",
             "claude exited -9 reporting an error"),
            ("a model verdict that labels no line blocks", 'verdict:{"labels": []}',
             "claude's verdict does not give the line exactly one label with a true or false ask")):
        check_blocked(case_name, case.run(model=mode), "the hook's `claude -p` call that has the model judge this question-like text failed", phrase,
                      '"The fix has a second part, and I recommend building it next."')
    check("a block after a failed model check is logged as such",
          [entry["decided_by"] for entry in case.logged()] == ["model-check-failed"] * 8, case.logged())
    saved_path = os.environ["PATH"]
    os.environ["FAKE_CLAUDE_CALLS"] = str(case.calls)
    try:
        os.environ["PATH"] = str(SUITE_ROOT / "no-such-directory")
        line, failure = judgement(["x"])
        check("a model that cannot be run is a failure, naming its line", line == "x" and "could not be run" in (failure or ""),
              failure)
        os.environ["PATH"] = f"{FAKE_BIN}{os.pathsep}{saved_path}"
        os.environ["FAKE_CLAUDE_MODE"] = "sleep"
        line, failure = judgement(["x"], timeout_seconds=1)
        check("a model call past its time limit is a failure",
              line == "x" and "no answer within 1 seconds" in (failure or ""), failure)
        for mode, expected in (("yes:3", "c"), ("yes:2", "b"), ("no", None), ("asks:[false, false, true]", "c"),
                               ("asks:[false, true, true]", "b")):
            os.environ["FAKE_CLAUDE_MODE"] = mode
            line, failure = judgement(["a", "b", "c"])
            check(f"the model's answer {mode} picks question-like line {expected}", (line, failure) == (expected, None),
                  (line, failure))
        os.environ["FAKE_CLAUDE_MODE"] = "fail:2"
        line, failure = judgement(["a", "b", "c"])
        check("a failed call for the second line names that line", line == "b" and "claude exited 1" in (failure or ""),
              (line, failure))
        calls_before = len(case.model_calls())
        os.environ["FAKE_CLAUDE_MODE"] = "no"
        judgement(["a", "b", "c"])
        calls = case.model_calls()[calls_before:]
        check("each question-like line is judged in a call of its own, numbered by its place",
              sorted((judged_entry(call)["id"], judged_line(call)) for call in calls)
              == [("L1", "a"), ("L2", "b"), ("L3", "c")], calls)
        check("each call is sent the labelling schema and system prompt",
              len(calls) == 3 and all(
                  json.loads(argv[argv.index("--json-schema") + 1]) == hook.MODEL_SCHEMA
                  and argv[argv.index("--system-prompt") + 1] == hook.MODEL_SYSTEM_PROMPT
                  for argv in (call["argv"] for call in calls)), calls)
        os.environ["FAKE_CLAUDE_MODE"] = "sleep:3"
        started = time.monotonic()
        line, failure = judgement(["a", "b", "c"], timeout_seconds=20)
        took = time.monotonic() - started
        check("the calls run at the same time: three calls of 3 seconds take less than 9",
              (line, failure) == (None, None) and took < 7.5, (line, failure, took))
        for case_name, verdict in (
                ("a verdict with no labels is a failure", {"lines": []}),
                ("a verdict whose labels are not a list is a failure", {"labels": "ask"}),
                ("a verdict with no label is a failure", {"labels": []}),
                ("a verdict with two labels is a failure",
                 {"labels": [{"id": "L1", "ask": False}, {"id": "L1", "ask": True}]}),
                ("a verdict whose label is not an object is a failure", {"labels": [True]}),
                ("a verdict whose ask is not true or false is a failure", {"labels": [{"id": "L1", "ask": "maybe"}]}),
                ("a verdict whose label has no ask is a failure", {"labels": [{"id": "L1"}]})):
            os.environ["FAKE_CLAUDE_MODE"] = "verdict:" + json.dumps(verdict)
            line, failure = judgement(["a"])
            expected = "without a verdict (KeyError('labels'))" if "labels" not in verdict else \
                "claude's verdict does not give the line exactly one label with a true or false ask"
            check(case_name, line == "a" and expected in (failure or ""), (line, failure))
    finally:
        os.environ["PATH"] = saved_path
        os.environ.pop("FAKE_CLAUDE_MODE", None)
        os.environ.pop("FAKE_CLAUDE_CALLS", None)


def test_a_question_above_a_label_subheading_in_an_interruption_item_is_held():
    stray = "merge-lane-2 asks: should I file one GHI listing the remaining seats' tests?"
    item = INTERRUPTION_ITEM.replace("Recommendation: File it.", "#### Item 2.1: details\n\nMore.\n\nRecommendation: File it.")
    case = Case(document=WALK_DOCUMENT.replace("of 10", "of 11") + "\n" + item, minutes="#next_to_present item 2 of 11")
    case.records(PEER_PROMPT, text_record(stray),
                 text_record("I added it as Item 2.1 of 11.\n\nItem 2 of 11 is waiting for your answer."))
    check_silent("a question above a `#### Item 2.1: details` subheading in interruption item 2.1 is still the item's, "
                 "so it passes", case.run(model="yes"))


def test_a_question_held_in_an_interruption_item_is_not_checked():
    stray = "merge-lane-2 asks: should I file one GHI listing the remaining seats' tests?"
    closing = "I added it as Item 2.1 of 11.\n\nItem 2 of 11 is waiting for your answer."
    held = Case(document=WALK_DOCUMENT.replace("of 10", "of 11") + "\n" + INTERRUPTION_ITEM,
                minutes="#next_to_present item 2 of 11")
    held.records(PEER_PROMPT, text_record(stray), text_record(closing))
    check_silent("a question an interruption item after the waiting item holds passes, with no tool call this turn",
                 held.run(model="yes"))
    check("a question held in an interruption item never reaches the model", held.model_calls() == [],
          held.model_calls())
    unnumbered = Case(document=WALK_DOCUMENT + "\n" + INTERRUPTION_ITEM.replace("## Item 2.1 of 11: ", "## "))
    unnumbered.records(PEER_PROMPT, text_record(stray), text_record(
        "I added the question to the walk as a new item.\n\nItem 2 of 10 is waiting for your answer."))
    check_silent("a question an unnumbered item holds, headed as the refusal's step 1 says, passes",
                 unnumbered.run(model="yes"))
    held.reply("Should I merge the pull request now?\n\n" + closing)
    check_blocked("a question the interruption item does not hold still blocks", held.run(),
                  '"Should I merge the pull request now?"')
    part_word = Case(document=WALK_DOCUMENT.replace("of 10", "of 11") + "\n"
                     + INTERRUPTION_ITEM.replace("one GHI", "one GHIs"), minutes="#next_to_present item 2 of 11")
    part_word.reply("merge-lane-2 asks: should I file one GHI?")
    check_blocked("a line that matches the item only to part of a word still blocks", part_word.run(),
                  "approval-walk question check")
    for case_name, document, minutes in (
            ("the same question in an item that is not an interruption item blocks",
             WALK_DOCUMENT.replace("of 10", "of 11") + "\n" + INTERRUPTION_ITEM.replace("Item 2.1 of 11", "Item 11 of 11"),
             "#next_to_present item 2 of 11"),
            ("the same question in an interruption item after another item than the waiting one blocks",
             WALK_DOCUMENT.replace("of 10", "of 11") + "\n" + INTERRUPTION_ITEM.replace("Item 2.1", "Item 3.1"),
             "#next_to_present item 2 of 11"),
            ("the same question with no interruption item blocks", WALK_DOCUMENT, "#next_to_present item 2 of 10"),
            ("the same question in an interruption item that is itself waiting blocks",
             WALK_DOCUMENT.replace("of 10", "of 11") + "\n" + INTERRUPTION_ITEM,
             "#next_to_present items 2 and 2.1 of 11")):
        case = Case(document=document, minutes=minutes)
        case.records(PEER_PROMPT, text_record(stray), text_record(closing))
        check_blocked(case_name, case.run(), "approval-walk question check")
    for case_name, document, minutes in (
            ("an interruption item retitled after it was added still holds its question",
             WALK_DOCUMENT.replace("of 10", "of 11") + "\n"
             + INTERRUPTION_ITEM.replace("merge-lane-2's question about the GHI", "the remaining seats' GHI, revised"),
             "#next_to_present item 2 of 11"),
            ("an interruption item with a newer total than the minutes' still holds its question",
             WALK_DOCUMENT + "\n" + INTERRUPTION_ITEM, "#next_to_present item 2 of 10")):
        case = Case(document=document, minutes=minutes)
        case.records(PEER_PROMPT, text_record(stray), text_record(closing))
        check_silent(case_name, case.run(model="yes"))
    for case_name, reply_line, item_line, passes in (
            ("a bold question the item holds without bold passes",
             "**Should we rename the hook before it merges?**", "Should we rename the hook before it merges?", True),
            ("a question with a code span the item holds passes",
             "Should I rerun `run-all-test-suites.py` before the push?",
             "Should I rerun `run-all-test-suites.py` before the push?", True),
            ("a list joined to its lead-in that the item holds passes",
             "Should I do one of these:\n- merge the lines\n- keep both",
             "Should I do one of these:\n- merge the lines\n- keep both", True),
            ("a question holding a quotation the walk-document holds passes once the item holds it",
             'Should I label the pull request "needs-tests"?', 'Should I label the pull request "needs-tests"?', True),
            ("a numbered question passes when the item holds it without its number",
             "1. Should I keep both hooks?", "Should I keep both hooks?", True),
            ("a question the item holds with a link passes when the reply holds the link's text",
             "Should I merge PR 5 now?", "Should I merge [PR 5](https://github.com/nedsnodes/nedsnodes/pull/5) now?",
             True),
            ("a line that is the end of an item word for word passes", ANSWER_LINE, "Should I keep both hooks?", True),
            ("a question that is only part of a word of the item blocks",
             "File it?", "Should I refile it?", False),
            ("a word the item bolds in part does not match the whole word, so the question blocks",
             "Should we refile it?", "Should we re**file** it?", False),
            ("a short question whose words run inside the item's longer question blocks",
             "Should I merge?", "Should I merge PR 5 now?", False),
            ("an ask without a question mark whose words start the item's longer question blocks",
             "Should I merge.", "Should I merge PR 5 now?", False),
            ("a question the item holds only as a statement blocks", "Should I merge?", "Should I merge.", False),
            ("a question the item quotes after a colon in a longer line blocks",
             "Should I merge PR 5 now?", 'merge-lane-2 asks: "Should I merge PR 5 now?" before the release.', False),
            ("a question the item holds after a colon on the same line blocks",
             "Should I merge PR 5 now?", "merge-lane-2 asks: Should I merge PR 5 now?", False),
            ("an ask that is the text before an item line's colon blocks",
             "Which do you want.", "Which do you want: PR 5 or PR 6?", False),
            ("a line holding the question and more words blocks",
             "Should I merge PR 5 now? It has two open findings.", "Should I merge PR 5 now?", False),
            ("a line that is only the first sentence of the item's line blocks",
             "Should I merge PR 5 now?", "Should I merge PR 5 now? It has two open findings.", False),
            ("a two-sentence line the item holds whole passes",
             "Should I merge PR 5 now? It has two open findings.",
             "merge-lane-2 asks before the release\nShould I merge PR 5 now? It has two open findings.", True),
            ("a list copied whole, each line on its own, passes",
             "Which should I run:\n- `merge.py`\n- `keep.py`",
             "merge-lane-2 asks:\nWhich should I run:\n- `merge.py`\n- `keep.py`", True),
            ("a question the item holds on a line of its own passes",
             "Should I merge PR 5 now?", "merge-lane-2 asks before the release\nShould I merge PR 5 now?", True),
            ("a question the item holds as a `>` quote line passes",
             "Should I merge PR 5 now?", "merge-lane-2 asks before the release\n> Should I merge PR 5 now?", True),
            ("a question the item holds as a `-` list item passes",
             "Should I merge PR 5 now?", "merge-lane-2 asks before the release\n- Should I merge PR 5 now?", True),
            ("a question the item holds as a `1.` list item passes",
             "Should I merge PR 5 now?", "merge-lane-2 asks before the release\n1. Should I merge PR 5 now?", True),
            ("a question the item quotes inside a longer sentence blocks",
             "Should I merge PR 5 now?", 'merge-lane-2 asks "Should I merge PR 5 now?" before the release.', False),
            ("an ask without a question mark whose words start the item's longer question with a quotation blocks",
             "Should I merge.", 'Should I merge "PR 5" now?', False),
            ("a list whose lead-in the item holds, with other choices, blocks",
             "PR 1922 merged.\n\nShould I do one of these:\n- delete the hook\n- keep it",
             "Should I do one of these:\n- merge the lines\n- keep both", False),
            ("a list of code spans whose lead-in the item holds, with other choices, blocks",
             "Should I run one of these:\n- `delete-all.py`\n- `keep.py`",
             "Should I run one of these:\n- `merge.py`\n- `keep.py`", False),
            ("a list of code spans the item holds with its lead-in passes",
             "Should I run one of these:\n- `merge.py`\n- `keep.py`",
             "Should I run one of these:\n- `merge.py`\n- `keep.py`", True),
            ("a list the item holds whole passes when one of its lines has no text once marks are dropped",
             "Should I use one of these marks:\n- `*`\n- `-`",
             "Should I use one of these marks:\n- `*`\n- `-`", True)):
        item = f"## Item 2.1 of 11: a question\n\n{item_line}\n\nRecommendation: Merge.\n\n{ANSWER_LINE}\n"
        case = Case(document=WALK_DOCUMENT.replace("of 10", "of 11") + "\n" + item,
                    minutes="#next_to_present item 2 of 11")
        case.reply(reply_line + "\n\n" + closing)
        if passes:
            check_silent(case_name, case.run(model="yes"))
        else:
            check_blocked(case_name, case.run(), "approval-walk question check")
    with_openings = (f"## Items 2.1 and 3 of 11: two questions\n\n**Item 2.1:**\n\nShould I file the GHI?\n\n"
                     f"{ANSWER_LINE}\n\n**Item 3:**\n\nShould I merge PR 5 now?\n\n{ANSWER_LINE}\n")
    partly_opened = (f"## Items 3, 2.1 and 2.2 of 11: three questions\n\n**Item 3:**\n\nShould I merge PR 5 now?\n\n"
                     f"Should I file the GHI?\n\n**Item 2.2:**\n\nShould I rename the hook?\n\n{ANSWER_LINE}\n")
    without_openings = "## Items 2.1 and 3 of 11: two questions\n\nShould I file the GHI?\n\nShould I merge PR 5 now?\n"
    for case_name, shared, reply_line, passes in (
            ("under a shared heading, the interruption item's own question passes",
             with_openings, "Should I file the GHI?", True),
            ("under a shared heading, the other item's question blocks", with_openings, "Should I merge PR 5 now?", False),
            ("under a shared heading, an interruption item's question passes after items without their own",
             partly_opened, "Should I rename the hook?", True),
            ("under a shared heading whose items have no openings, the interruption item's question blocks",
             without_openings, "Should I file the GHI?", False),
            ("under a shared heading whose items have no openings and that keeps a Withdrawn version, the "
             "interruption item's question still blocks",
             without_openings + "\n#### Withdrawn version 1 of items 2.1 and 3\n\nShould I file two GHIs?\n",
             "Should I file the GHI?", False)):
        case = Case(document=WALK_DOCUMENT.replace("of 10", "of 11") + "\n" + shared,
                    minutes="#next_to_present item 2 of 11")
        case.reply(reply_line + "\n\n" + closing)
        if passes:
            check_silent(case_name, case.run(model="yes"))
        else:
            check_blocked(case_name, case.run(), "approval-walk question check")
    headed = Case(document=WALK_DOCUMENT.replace("of 10", "of 11")
                  + f"\n## Item 2.1 of 11: should I file the GHI?\n\nRecommendation: File it.\n\n{ANSWER_LINE}\n",
                  minutes="#next_to_present item 2 of 11")
    headed.reply("Item 2.1 of 11: should I file the GHI?\n\nRecommendation: File it.\n\n" + closing)
    check_silent("lines that are the start of an item word for word pass", headed.run(model="yes"))
    headed.reply("no proposed text marked\n\nItem 2.1 of 11's answer is recorded in the minutes, and its change may "
                 "now be made.\n\n" + closing)
    check_silent("the lines the walk-me-through skill and its check and close programs have the agent write pass",
                 headed.run(model="yes"))


def test_line_marks_strips_the_list_and_quotation_marks_and_keeps_a_mark_only_spacing_opens():
    for line, stripped in (("> - text", "text"), ("- text", "text"), ("1. text", "text"), ("2) text", "text"),
                           ("+ > text", "text"), ("  * #new x", "#new x"), (" #new x", " #new x"),
                           ("-text", "-text"), ("text", "text")):
        check(f"LINE_MARKS turns {line!r} into {stripped!r}", hook.LINE_MARKS.sub("", line) == stripped,
              repr(hook.LINE_MARKS.sub("", line)))
    check("an indented `#new` line with no list mark keeps its mark through normalized()",
          hook.normalized(" #new x") == "new x", repr(hook.normalized(" #new x")))


def walk_finder_rule_replaced_in(tree, rule):
    """Sets the value of the module-level assignment that binds the walk finder's list or quotation mark rule to
    rule, whether the assignment is plain, annotated or chained; fails this case and returns False unless exactly
    one such assignment exists."""
    assignments = [node for node in tree.body
                   if (isinstance(node, ast.Assign) and any(getattr(target, "id", None)
                       == "MARKDOWN_LINE_OPENING_LIST_OR_QUOTATION_MARK_PATTERN_TEXT" for target in node.targets))
                   or (isinstance(node, ast.AnnAssign) and node.value is not None and getattr(node.target, "id", None)
                       == "MARKDOWN_LINE_OPENING_LIST_OR_QUOTATION_MARK_PATTERN_TEXT")]
    check("the walk finder assigns its list or quotation mark rule once, at module level",
          len(assignments) == 1, len(assignments))
    if len(assignments) != 1:
        return False
    assignments[0].value = ast.copy_location(ast.Constant(rule), assignments[0].value)
    return True


def test_the_rule_replacement_finds_the_finder_constant_however_it_is_assigned():
    name = "MARKDOWN_LINE_OPENING_LIST_OR_QUOTATION_MARK_PATTERN_TEXT"
    for form, source in (("plain", f"{name} = 'old'"), ("annotated", f"{name}: str = 'old'"),
                         ("chained", f"OTHER = {name} = 'old'")):
        tree = ast.parse(source)
        replaced = walk_finder_rule_replaced_in(tree, "new")
        namespace = {}
        exec(compile(ast.fix_missing_locations(tree), "<finder variant>", "exec"), namespace)
        check(f"the rule replacement sets the {form} assignment's value", replaced and namespace[name] == "new",
              namespace.get(name))
    failures_before = len(failures)
    with contextlib.redirect_stdout(io.StringIO()):
        replaced = walk_finder_rule_replaced_in(ast.parse("OTHER = 'old'"), "new")
    recorded = failures[failures_before:]
    del failures[failures_before:]
    check("a finder with no assignment of the rule makes the replacement report False", replaced is False, replaced)
    check("a finder with no assignment of the rule fails the once-at-module-level case",
          recorded == ["the walk finder assigns its list or quotation mark rule once, at module level"], recorded)


def modules_loaded_with_the_walk_finder_list_or_quotation_mark_rule_replaced(rule):
    """The walk finder, this hook and the walk check program, each loaded afresh while the walk finder's source
    holds rule in place of its list or quotation mark rule, so a pattern that spells the rule out by hand, rather
    than building from the finder's constant, still reads the real marks and not rule; None when the finder's
    rule assignment cannot be found, which has already failed a case."""
    finder_file = hook.WALK_FINDER_FILE.resolve()
    replaced = ast.parse(finder_file.read_text(encoding="utf-8"), str(finder_file))
    if not walk_finder_rule_replaced_in(replaced, rule):
        return None

    class ReplacedFinderLoader(importlib.machinery.SourceFileLoader):
        def get_code(self, fullname):
            return compile(replaced, self.path, "exec")

    real = importlib.util.spec_from_file_location

    def redirected(name, location=None, *arguments, **keywords):
        if location is not None and Path(location).resolve() == finder_file:
            return real(name, location, loader=ReplacedFinderLoader(name, str(location)))
        return real(name, location, *arguments, **keywords)

    def load(name, path):
        specification = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(specification)
        specification.loader.exec_module(module)
        return module

    importlib.util.spec_from_file_location = redirected
    try:
        return (load("walk_finder_with_replaced_rule", finder_file),
                load("question_refusal_stop_hook_with_replaced_rule", HOOK_SCRIPT),
                load("check_and_close_with_replaced_rule", hook.WALK_CHECK_PROGRAM))
    finally:
        importlib.util.spec_from_file_location = real


def test_every_pattern_reading_list_or_quotation_marks_follows_the_walk_finder_rule():
    modules = modules_loaded_with_the_walk_finder_list_or_quotation_mark_rule_replaced(r"(?:Q\s+)")
    if modules is None:
        return
    finder, replaced_hook, close = modules
    patterns = (("the `#new` mark pattern", finder.APPROVAL_WALK_ITEM_NEW_TEXT_MARK_LINE_PATTERN, "#new x"),
                ("the walk check program's `#case_against` line", close.CASE_AGAINST_LINE, "#case_against weak"),
                ("the walk check program's evidence line", close.EVIDENCE_LINE, "#not_asked_test x"),
                ("the walk check program's category line", close.WALK_CATEGORY_LINE,
                 "#approval_walk_item_in_category_fix_next"))
    for name, pattern, marker in patterns:
        check(f"{name} reads the replaced rule's mark", bool(pattern.match("Q " + marker)), pattern.pattern)
        check(f"{name} no longer reads a mark the replaced rule drops", not pattern.match("- " + marker),
              pattern.pattern)
    check("LINE_MARKS strips the replaced rule's mark and no other",
          (replaced_hook.LINE_MARKS.sub("", "Q text"), replaced_hook.LINE_MARKS.sub("", "- text")) == ("text", "- text"),
          replaced_hook.LINE_MARKS.pattern)


def test_the_final_message_from_the_payload_is_checked():
    case = Case()
    case.records(USER_PROMPT, tool_record("Bash", {"command": "ls"}))
    check_blocked("a question only in the payload's last_assistant_message blocks",
                  case.run(last_assistant_message="Do you want me to merge it?"), '"Do you want me to merge it?"')
    check_silent("a turn with no text in the transcript or the payload passes", case.run())


def test_the_final_message_already_in_the_transcript_is_checked_once():
    case = Case()
    case.reply("Should I merge it?")
    check_blocked("a question in the final message blocks", case.run(last_assistant_message="Should I merge it?"),
                  '"Should I merge it?"')
    check("the payload's final message, already the transcript's last assistant text, is judged once, not twice",
          [judged_line(call) for call in case.model_calls()] == ["Should I merge it?"], case.model_calls())


def test_a_long_message_is_cut_around_the_line_as_the_benchmark_cut_it():
    case = Case()
    before = "\n".join(f"Report line {number} is done." for number in range(400))
    after = "\n".join(f"Closing note {number} is filed." for number in range(200))
    line = "I recommend building the second part next."
    case.reply(f"{before}\n{line}\n{after}")
    case.run(model="no")
    calls = case.model_calls()
    message = judged_entry(calls[0])["agent_message_holding_the_line"] if calls else ""
    at = message.find(line)
    check("a long message's entry holds only the window around the line, marked as cut on both sides",
          len(calls) == 1 and message.startswith("[...] ") and message.endswith(" [...]")
          and at == len("[...] ") + hook.AGENT_MESSAGE_CHARACTERS_KEPT_BEFORE_THE_LINE
          and len(message) - at - len(line) == hook.AGENT_MESSAGE_CHARACTERS_KEPT_AFTER_THE_LINE + len(" [...]"),
          (len(message), at))
    shared_start = "The second part of the fix is ready, and every test for it passes"
    case.reply(f"{shared_start}.\n{before}\n{shared_start}; should I merge it?\n{after}")
    calls_before = len(case.model_calls())
    case.run(model="no")
    calls = case.model_calls()[calls_before:]
    message = judged_entry(calls[0])["agent_message_holding_the_line"] if calls else ""
    check("the window is cut around the judged line, not around an earlier line that starts with the same text",
          len(calls) == 1 and message.startswith("[...] ")
          and message.find(f"{shared_start}; should I merge it?")
          == len("[...] ") + hook.AGENT_MESSAGE_CHARACTERS_KEPT_BEFORE_THE_LINE, (len(message), message[:80]))


def test_the_shown_item_and_quotes_from_it_are_not_checked():
    case = Case()
    case.reply("Recorded your answer to item 1.\n\n" + ITEM_2_SHOWN)
    check_silent("a question inside the item the reply shows does not block", case.run(model="yes"))
    after = Case()
    after.reply(ITEM_2_SHOWN + "\n\nShould I also add a link to it?")
    check_blocked("a question after the shown item still blocks", after.run(), '"Should I also add a link to it?"')
    case.reply('You asked about "Do you agree that agents look there first?" It means the wiki comes first.')
    check_silent("a quote of the walk-document's text is not checked", case.run(model="no"))
    case.reply("> Do you agree that agents look there first?\n\nThat line is the item's question.")
    check_silent("a quotation line holding the walk-document's text is not checked", case.run(model="no"))
    check("quoted text from the walk-document never reaches the model", case.model_calls() == [], case.model_calls())
    alternative = " D: the page stays out of the wiki."
    with_alternative = Case(document=WALK_DOCUMENT.replace(ANSWER_LINE, ANSWER_LINE + alternative))
    with_alternative.reply(ITEM_2_SHOWN)
    check_silent("the shown item's answer line passes without the alternative the walk-document adds after it",
                 with_alternative.run(model="yes"))
    with_alternative.reply(ITEM_2_SHOWN + alternative)
    check_silent("the shown item's answer line passes with the alternative", with_alternative.run(model="yes"))
    numbered = Case(document=WALK_DOCUMENT.replace(f"\n{ANSWER_LINE}\n", f"\n6. {ANSWER_LINE}{alternative}\n"))
    numbered.reply(ITEM_2_SHOWN)
    check_silent("the shown item's answer line passes without the number and the alternative the walk-document adds",
                 numbered.run(model="yes"))


def test_a_withdrawn_versions_lines_under_a_shared_heading_are_not_the_shown_items():
    document = (f"# The poem page: approval-walk\n\n## Items 2 and 3 of 10: the poem page\n\n"
                f"**Item 2: where it lives.** Should I keep the poem page in the wiki?\n\n"
                f"#### Withdrawn version 1 of item 2\n\nShould I drop the poem page?\n\n"
                f"**Item 3: its name.** Should I keep its name?\n\n{ANSWER_LINE}\n")
    for case_name, line, passes in (
            ("a reply showing a shared heading passes the live item's own line",
             "**Item 2: where it lives.** Should I keep the poem page in the wiki?", True),
            ("a reply showing a shared heading passes the line of an item whose opening follows another item's "
             "Withdrawn version", "**Item 3: its name.** Should I keep its name?", True),
            ("a reply showing a shared heading still has a line copied from a Withdrawn version under it checked",
             "Should I drop the poem page?", False)):
        case = Case(document=document)
        case.reply("## Items 2 and 3 of 10: the poem page\n\n" + line)
        if passes:
            check_silent(case_name, case.run(model="yes"))
        else:
            check_blocked(case_name, case.run(), '"Should I drop the poem page?"')


def test_an_item_under_a_shared_heading_is_shown_by_its_own_opening_or_item_n_of_m_heading():
    item_3_opening = "**Item 3: its name.** The name follows the naming page."
    item_3_question = "Should I keep its name?"
    document = (f"# The poem page: approval-walk\n\n## Items 2 and 3 of 10: the poem page?\n\n"
                f"**Item 2: where it lives.** Should I keep the poem page in the wiki?\n\n{ANSWER_LINE}\n\n"
                f"{item_3_opening}\n\n{item_3_question}\n\n{ANSWER_LINE}\n\n"
                f"**Item 4 of 10: its hook.** Should I build the hook?\n\n{ANSWER_LINE}\n")
    closing = f"[Item 3 of 10, its name](https://claude.ai/artifact/x) · {CLOSING_LINE_ANSWER_LETTERS}"
    for case_name, reply in (
            ("the second item of a shared unit shown under its own `Item N of M` heading sends no line to the model",
             f"## Item 3 of 10: its name\n\n{item_3_opening}\n\n{item_3_question}\n\n{ANSWER_LINE}\n\n{closing}"),
            ("the second item of a shared unit shown from its own opening sends no line to the model",
             f"{item_3_opening}\n\n{item_3_question}\n\n{ANSWER_LINE}\n\n{closing}"),
            ("the shared heading's own line, shown with only the second item, sends no line to the model",
             f"## Items 2 and 3 of 10: the poem page?\n\n{item_3_opening}\n\n{item_3_question}\n\n{closing}"),
            ("every item of a shared unit shown under the shared heading sends no line to the model, past the first "
             "item's answer line",
             f"## Items 2 and 3 of 10: the poem page?\n\n**Item 2: where it lives.** Should I keep the poem page in "
             f"the wiki?\n\n{ANSWER_LINE}\n\n{item_3_opening}\n\n{item_3_question}\n\n{ANSWER_LINE}\n\n{closing}")):
        case = Case(minutes="#next_to_present item 3 of 10", document=document)
        case.reply(reply)
        check_silent(case_name, case.run(model="yes"))
        check(f"{case_name}: no model call", case.model_calls() == [], case.model_calls())
    for case_name, reply, flagged in (
            ("an item of a shared unit whose closing line alone names it is not shown, so its question is checked",
             f"{item_3_question}\n\n{closing}", item_3_question),
            ("an item shown under its own heading does not show the next unit's item",
             f"## Item 3 of 10: its name\n\nShould I build the hook?\n\n{closing}", "Should I build the hook?"),
            ("an item shown under its own heading does not show the other item of its unit",
             f"## Item 3 of 10: its name\n\nShould I keep the poem page in the wiki?\n\n{closing}",
             "Should I keep the poem page in the wiki?")):
        case = Case(minutes="#next_to_present item 3 of 10", document=document)
        case.reply(reply)
        check_blocked(case_name, case.run(model="yes"), f'"{flagged}"')
    lead_in = "Both items ask whether the page should change?"
    case = Case(minutes="#next_to_present item 3 of 10",
                document=document.replace("the poem page?\n\n", f"the poem page?\n\n{lead_in}\n\n", 1))
    case.reply(f"## Items 2 and 3 of 10: the poem page?\n\n{lead_in}\n\n{item_3_opening}\n\n{closing}")
    check_silent("a reply showing a shared heading passes the unit's lines before its first item's opening",
                 case.run(model="yes"))
    case.reply(f"## Item 3 of 10: its name\n\n{lead_in}\n\n{closing}")
    check_blocked("an item shown under its own heading does not show its unit's lines before the first item's opening",
                  case.run(model="yes"), f'"{lead_in}"')
    case = Case(minutes="#next_to_present item 3 of 10", document=document)
    case.reply(f"## Items 2 and 3 of 10: the poem page?\n\n{item_3_question}\n\n{closing}")
    check_silent("the shared heading alone shows each item of its unit, with no opening or own heading shown",
                 case.run(model="yes"))
    withdrawn_question = "Should the poem page move to the archive?"
    case = Case(minutes="#next_to_present item 3 of 10",
                document=document.replace("the poem page?\n\n", f"the poem page?\n\n#### Withdrawn version\n\n"
                                                                  f"{withdrawn_question}\n\n", 1))
    case.reply(f"## Items 2 and 3 of 10: the poem page?\n\n{withdrawn_question}\n\n{item_3_opening}\n\n{closing}")
    check_blocked("a Withdrawn version before a shared unit's first opening is not shown by the shared heading",
                  case.run(model="yes"), f'"{withdrawn_question}"')
    case = Case(minutes="#next_to_present item 3 of 10",
                document=document.replace("the poem page?\n\n", "the poem page?\n\n#new The new text: both items "
                                                                  "keep the poem page?\n\n", 1))
    case.reply(f"## Items 2 and 3 of 10: the poem page?\n\nIf you approve, the new text: both items keep the poem "
               f"page?\n\n{item_3_opening}\n\n{closing}")
    check_silent("a `#new` line before a shared unit's first opening passes shown after `If you approve, the new text:`",
                 case.run(model="yes"))
    without_openings = (f"# The poem page: approval-walk\n\n## Items 2 and 3 of 10: the poem page\n\n"
                        f"Should I keep the poem page in the wiki?\n\n{ANSWER_LINE}\n\n{item_3_question}\n\n"
                        f"{ANSWER_LINE}\n")
    case = Case(minutes="#next_to_present item 3 of 10", document=without_openings)
    case.reply(f"## Item 3 of 10: its name\n\n{item_3_question}\n\n{ANSWER_LINE}\n\n{closing}")
    check_silent("an item of a shared unit with no opening of its own holds the whole unit, past the first answer line",
                 case.run(model="yes"))


HANDOFF_WALK_ITEM_1_2_LINES = (
    "## Item 1.2 of 6: a wait limit for each kind of background Bash task",
    "Item 1.1, from about 9,000 measured runs, proposed 90 minutes for a test suite, 105 for nn-mutation-testing, 75 for every other kind, and 0 for a waiter (explained below). In [handoff-design.md](https://github.com/nedsnodes/nedsnodes/blob/main/nn-systems/handoff/handoff-design.md), the threshold hook's old text: \"The hook now counts a background Bash task as in flight while it is younger than `--background-task-wait-minutes` and no completion notification names it, judging each task's wait on its own;\"",
    "#new The new text: \"The hook now counts a background Bash task as in flight while it is younger than its kind's wait limit and no completion notification names it, judging each task's wait on its own. A table the hook reads gives each kind its command patterns and its wait limit, and replaces the hook's `--background-task-wait-minutes` option: the first kind whose pattern matches the command is the task's kind, a command no pattern matches gets 75 minutes, and a kind that only waits, such as `gh pr checks --watch` or a `sleep` loop, has a limit of 0 minutes, so it is never in flight.\"",
    "The rule for a subagent's own background work, approved 2026-10-30, reads the same table. [advisor]",
    "A waiter, such as `gh pr checks --watch`, does no work; it only watches for an outside event. A limit of 0 means the handoff never waits for it, and the next agent-session starts the watch again.",
    "The advisor reviewed this item, and the new text had its own fast read.",
    "#case_against medium: the alternative needs no table kept up to date, but holds the handoff up to 30 minutes longer behind a stuck task. [advisor]",
    "The alternative: one limit of 105 minutes for every kind, waiters at 0, and no table.",
    "Recommendation: adopt the table and the new text.",
)
HANDOFF_WALK_ITEM_1_2_REPLY = "\n\n".join((
    "Last ruled on: item 1.1.1 (the glossary terms), which you approved on 2026-11-01.",
    "I found two work-snapshots in this seat's worktree. Both held the same four drafts in docs/drafts/ (work-with-mac skill, its proposals, the bang-prefix sentence and the objective section). Those files are still there, uncommitted, with the same contents, so there was nothing to restore. I deleted both snapshots.",
    "## Item 1.2 of 6: a wait limit for each kind of background Bash task",
    "Item 1.1, from about 9,000 measured runs, proposed 90 minutes for a test suite, 105 for nn-mutation-testing, 75 for every other kind, and 0 for a waiter (explained below). In [handoff-design.md](https://github.com/nedsnodes/nedsnodes/blob/main/nn-systems/handoff/handoff-design.md), the threshold hook's old text: \"The hook now counts a background Bash task as in flight while it is younger than `--background-task-wait-minutes` and no completion notification names it, judging each task's wait on its own;\"",
    "If you approve, the new text: \"The hook now counts a background Bash task as in flight while it is younger than its kind's wait limit and no completion notification names it, judging each task's wait on its own. A table the hook reads gives each kind its command patterns and its wait limit, and replaces the hook's `--background-task-wait-minutes` option: the first kind whose pattern matches the command is the task's kind, a command no pattern matches gets 75 minutes, and a kind that only waits, such as `gh pr checks --watch` or a `sleep` loop, has a limit of 0 minutes, so it is never in flight.\"",
    "The rule for a subagent's own background work, approved 2026-10-30, reads the same table. [advisor]",
    "A waiter, such as `gh pr checks --watch`, does no work; it only watches for an outside event. A limit of 0 means the handoff never waits for it, and the next agent-session starts the watch again.",
    "The advisor reviewed this item, and the new text had its own fast read.",
    "#case_against medium: the alternative needs no table kept up to date, but holds the handoff up to 30 minutes longer behind a stuck task. [advisor]",
    "The alternative: one limit of 105 minutes for every kind, waiters at 0, and no table.",
    "Recommendation: adopt the table and the new text.",
    "[Item 1.2 of 6, a wait limit for each kind of background Bash task](https://claude.ai/artifact/T2uhWgiK9eFspNAiZ5MEyb) · A approve · D disapprove · M more responses",
))


def test_a_new_text_line_shown_as_if_you_approve_the_new_text_is_the_items_own_text():
    document = "# Handoff wait limits: approval-walk\n\n" + "\n\n".join(HANDOFF_WALK_ITEM_1_2_LINES) + "\n"
    case = Case(minutes="#next_to_present item 1.2 of 6", document=document)
    case.reply(HANDOFF_WALK_ITEM_1_2_REPLY)
    check_silent("the reply that showed item 1.2's `#new` line as `If you approve, the new text:` passes",
                 case.run(model="yes"))
    check("that reply sends no line to the model", case.model_calls() == [], case.model_calls())
    for case_name, document_line, shown_line in (
            ("a `#new` line with no `The new text:` passes shown after `If you approve, the new text:`, "
             "whatever the case of its first letter",
             "#new The threshold-hook bullet becomes: \"The hook waits.\"",
             "If you approve, the new text: the threshold-hook bullet becomes: \"The hook waits.\""),
            ("a `#new_if_d` line passes shown after `If you disapprove, the new text:`",
             "#new_if_d The new text: the hook waits unless you stop it.",
             "If you disapprove, the new text: the hook waits unless you stop it."),
            ("a `#new` line whose `The new text:` label is bold passes shown after `If you approve, the new text:`",
             "#new **The new text:** the hook waits for the bold label.",
             "If you approve, the new text: the hook waits for the bold label."),
            ("a `#new` line that opens with a list mark passes shown after `If you approve, the new text:`",
             "- #new The new text: the hook waits for the list.",
             "If you approve, the new text: the hook waits for the list."),
            ("a `#new` line that opens with a quote mark passes shown after `If you approve, the new text:`",
             "> #new The new text: the hook waits for the quote.",
             "If you approve, the new text: the hook waits for the quote."),
            ("a `#new` line after a part's `Part 1.` passes shown as `Part 1. If you approve, the new text:`",
             "Part 1. #new The new text: the hook waits for the part.",
             "Part 1. If you approve, the new text: the hook waits for the part.")):
        varied = Case(minutes="#next_to_present item 1.2 of 6",
                      document=document.replace(HANDOFF_WALK_ITEM_1_2_LINES[2], document_line))
        varied.reply(HANDOFF_WALK_ITEM_1_2_REPLY.replace(HANDOFF_WALK_ITEM_1_2_REPLY.split("\n\n")[4], shown_line))
        check_silent(case_name, varied.run(model="yes"))
    case.reply(HANDOFF_WALK_ITEM_1_2_REPLY.replace("its kind's wait limit", "a wait limit you choose"))
    check_blocked("a shown new text that differs from the item's `#new` line still goes to the model",
                  case.run(model="yes"), "If you approve, the new text:")


def test_every_turn_is_checked_whoever_started_it():
    case = Case()
    case.reply("merge-lane-2 reports PR 1922 merged. Should I start the next fix?", opening=PEER_PROMPT)
    check_blocked("a turn started by another agent-seat's message is checked", case.run(),
                  '"merge-lane-2 reports PR 1922 merged. Should I start the next fix?"')
    notice = opening_prompt("task_notification", "<task-notification>done</task-notification>",
                            origin={"kind": "task-notification"}, promptSource="system")
    case.reply("The subagent finished. Should I open the pull request?", opening=notice)
    check_blocked("a turn started by a background-task notice is checked", case.run(), "approval-walk question check")
    case.records(USER_PROMPT, text_record("Should I open the pull request?"), USER_PROMPT,
                 text_record("Recorded."))
    check_silent("a question from an earlier turn is not checked again", case.run())
    unmarked_peer_prompt = {key: value for key, value in PEER_PROMPT.items() if key != "turnOrigin"}
    case.records(USER_PROMPT, text_record("Should I open the pull request?"), unmarked_peer_prompt,
                 text_record("Noted.\n\nItem 2 of 10 is waiting for your answer."))
    check_silent("a question from an earlier turn is not checked again when the newer turn's start has no "
                 "turnOrigin", case.run())
    scheduled_prompt = opening_prompt("scheduled", "Hourly stall check.", isMeta=True, promptSource="system")
    case.records(USER_PROMPT, text_record("Should I open the pull request?"), scheduled_prompt,
                 text_record("The stall check found nothing. I recommend merging PR 1922 next."))
    calls_before = len(case.model_calls())
    check_blocked("a scheduled turn after the user's turn is checked", case.run(model="yes"),
                  "I recommend merging PR 1922 next.")
    calls = case.model_calls()[calls_before:]
    check("a scheduled turn's own opening prompt, not the user's earlier one, starts the turn the model is given, "
          "and the earlier turn's question is not judged again",
          [(judged_entry(call)["turn_started_by"], judged_entry(call)["message_that_started_the_turn"],
            judged_line(call)) for call in calls]
          == [("scheduled", "Hourly stall check.",
               "The stall check found nothing. I recommend merging PR 1922 next.")], calls)


def test_when_the_hook_stays_silent():
    case = Case()
    case.reply("Should I merge the pull request now?")
    check_silent("silent while the agent answers a Stop hook", case.run(stop_hook_active=True))
    check_silent("silent in a headless claude -p child",
                 case.run(environment_extra={"CLAUDE_CODE_SESSION_ATTENDED": "0"}))
    check_silent("silent in a child whose caller owns its session",
                 case.run(environment_extra={"NEDSNODES_SESSION_REINCARNATION_OWNED_BY_CALLER": "x"}))
    closed = Case(minutes="#next_to_present none, closed")
    closed.reply("Should I merge the pull request now?")
    check_silent("silent when no approval-walk is open", closed.run())
    unreadable = Case(minutes="#next_to_present item 7 of 10")
    unreadable.reply("Should I merge the pull request now?")
    check_silent("silent when the walk-document has no heading for the waiting item", unreadable.run())
    old_marker = Case(minutes="Next to present: item 2 of 10")
    old_marker.reply("Should I merge the pull request now?")
    check_silent("silent when the minutes carry only the old marker", old_marker.run())
    check("no silent case is logged", case.logged() == [] and closed.logged() == [], case.logged())


def test_the_refusal_log():
    case = Case()
    case.reply("Should I merge the pull request now?")
    case.log.mkdir()
    check_blocked("a refusal that cannot be logged still blocks and says it was not logged", case.run(),
                  "This refusal was not logged, because", str(case.log))
    homes = SUITE_ROOT / "log-store-homes"
    (homes / "mac-mount" / hook.LOG_STORE_DIRECTORY_NAME).mkdir(parents=True)
    path, problem = hook.log_path({}, [str(homes / "ned-box-home"), str(homes / "mac-mount")])
    check("the log-store is reached through the Mac's mount when ned-box's path is missing",
          (path, problem) == (homes / "mac-mount" / hook.LOG_STORE_DIRECTORY_NAME / hook.LOG_FILE_NAME, None),
          (path, problem))
    path, problem = hook.log_path({}, [str(homes / "ned-box-home"), str(homes / "nowhere")])
    check("an unreachable log-store is reported", path is None and "reachable at neither" in problem, problem)
    path, _ = hook.log_path({})
    check("by default the log-store is the one under ned-box's home or the Mac's mount",
          path is None or path.name == hook.LOG_FILE_NAME and path.parent.name == "nedsnodes-logs", path)


def test_which_line_is_flagged_and_how_lines_are_joined():
    case = Case()
    case.reply("Should I merge it now?\n\nShould I also tag it?")
    check_blocked("of two questions the model flags, the first is flagged", case.run(), '"Should I merge it now?"')
    case.reply("I recommend merging it.\n\nI recommend tagging it too.")
    check_blocked("after a failed model check, the first question-like line is flagged", case.run(model="fail"),
                  '"I recommend merging it."')
    case.reply("Still waiting for you:\n- the cleanup of the old directories;\n- the naming change.\n\nDone.")
    calls_before = len(case.model_calls())
    case.run(model="no")
    calls = case.model_calls()[calls_before:]
    check("a list is judged with the line ending in `:` that introduces it, in one call",
          [judged_line(call) for call in calls]
          == ["Still waiting for you: - the cleanup of the old directories; - the naming change."], calls)
    case.reply("Should I run one of these:\n- `delete-all.py`\n- **keep.py**")
    check_blocked("a flagged list is named as written, line by line, marks included", case.run(),
                  '"Should I run one of these:\n- `delete-all.py`\n- **keep.py**"')
    case.reply("Should I run `delete-all.py`?\n\nShould I run `keep.py`?")
    check_blocked("of two lines checked alike but written differently, the one the model flags is named as written",
                  case.run(model="yes:2"), '"Should I run `keep.py`?"')
    case.reply("Should I merge the café page now?")
    case.run()
    check("the log keeps a sentence's letters as written", "café" in case.log.read_text(encoding="utf-8"),
          case.log.read_text(encoding="utf-8"))


def test_two_waiting_items():
    case = Case(minutes="#next_to_present items 2 and 3 of 10")
    case.reply("Should I merge the pull request now?")
    reason = blocked_reason(case.run()) or ""
    check("with two items waiting, the refusal names both and gives each item's closing line, on a line of its own",
          "only asks again for his answer to item 2 and 3, end your turn with each waiting item's closing line, on a "
          f"line of its own below and nothing after it. {NOT_IN_BACKTICKS}\n[Item 2 of {M_WITH_NO_ITEM_ADDED}, where "
          f"the poem page lives](<page link>) · {CLOSING_LINE_ANSWER_LETTERS}\n[Item 3 of {M_WITH_NO_ITEM_ADDED}, the "
          f"hook](<page link>) · {CLOSING_LINE_ANSWER_LETTERS}\nThe minutes record no `#item_page` line for items 2 "
          "and 3." in reason, reason)
    result = run_insert_command(case, reason)
    document = case.document.read_text()
    check("with two items waiting, the command puts the item after the later one and prints both closing lines "
          "with the count raised", result is not None
          and document.index("## Item 3 of 10") < document.index("## merge-lane-2's question")
          and f"[Item 2 of {M_AFTER_THE_ADDED_ITEM}, where the poem page lives](<page link>) · "
              f"{CLOSING_LINE_ANSWER_LETTERS}\n[Item 3 of {M_AFTER_THE_ADDED_ITEM}, the hook](<page link>) · "
              f"{CLOSING_LINE_ANSWER_LETTERS}" in result.stdout, (document, result and result.stdout))
    mixed = Case(minutes="#item_page item 3 of 10 https://claude.ai/artifact/p3\n#next_to_present items 2 and 3 of 10")
    mixed.reply("Should I merge the pull request now?")
    check_blocked("with two items waiting and a page for one, each gets its own form of the closing line",
                  mixed.run(), f"[Item 2 of {M_WITH_NO_ITEM_ADDED}, where the poem page lives](<page link>) · "
                  f"{CLOSING_LINE_ANSWER_LETTERS}\n[Item 3 of {M_WITH_NO_ITEM_ADDED}, the hook]"
                  f"(https://claude.ai/artifact/p3) · {CLOSING_LINE_ANSWER_LETTERS}\n"
                  "The minutes record no `#item_page` line for item 2. For each such item")


def test_only_a_reminder_of_the_open_walks_waiting_items_is_skipped():
    case = Case()
    for case_name, reminder in (
            ("a reminder of an item that is not waiting is checked", "Item 99 of 10 is waiting for your answer."),
            ("a reminder whose range runs backwards is checked", "Items 3 to 2 of 10 are waiting for your answer.")):
        case.reply("PR 1922 merged.\n\n" + reminder)
        check_blocked(case_name, case.run(model="yes"), f'"{reminder}"')
    two_waiting = Case(minutes="#next_to_present items 2 and 3 of 10")
    two_waiting.reply("PR 1922 merged.\n\nItem 2 of 10 is waiting for your answer.")
    check_silent("a reminder of one of two waiting items is skipped", two_waiting.run(model="yes"))
    case.reply("PR 1922 merged.\n\nItem 2 of 200 is waiting for your answer.")
    check_silent("a reminder of a waiting item is skipped whatever M it gives, since M is display only",
                 case.run(model="yes"))


def closing_line(count, point="the poem page is recommended for the wiki"):
    label = f"Item {count}, {point}" if point else f"Item {count}"
    return f"[{label}](https://claude.ai/artifact/x) · {CLOSING_LINE_ANSWER_LETTERS}"


def test_only_the_waiting_items_closing_line_is_skipped():
    case = Case()
    for case_name, text in (
            ("the waiting item's closing line after an event note passes, though its point differs from the "
             "heading's and holds `recommended`", "PR 1922 merged.\n\n" + closing_line("2 of 10")),
            ("the waiting item's closing line after the item shown in full passes",
             ITEM_2_SHOWN + "\n\n" + closing_line("2 of 10")),
            ("a closing line without a point passes", closing_line("2 of 10", point=None))):
        case.reply(text)
        check_silent(case_name, case.run(model="yes"))
    for case_name, count in (("a waiting item's closing line with a larger M passes, since M is display only", "2 of 11"),
                             ("a waiting item's closing line with a smaller M passes", "2 of 1")):
        case.reply("PR 1922 merged.\n\n" + closing_line(count))
        check_silent(case_name, case.run(model="yes"))
    check("a waiting item's closing line never reaches the model", case.model_calls() == [], case.model_calls())
    for case_name, line in (
            ("a closing line naming an item that is not waiting is checked", closing_line("3 of 10")),
            ("a closing line with text after its answer letters is checked", closing_line("2 of 10") + " Agree?"),
            ("a closing line with text before it on its line is checked", "Recommended: " + closing_line("2 of 10")),
            ("a closing line missing an answer letter is checked",
             closing_line("2 of 10").replace(" · M more responses", ""))):
        case.reply("PR 1922 merged.\n\n" + line)
        check_blocked(case_name, case.run(model="yes"), "approval-walk question check")
    two_waiting = Case(minutes="#next_to_present items 2 and 3 of 10")
    two_waiting.reply(closing_line("2 of 10") + "\n\n" + closing_line("3 of 10"))
    check_silent("the closing line of each of two waiting items passes", two_waiting.run(model="yes"))


def test_a_closing_line_passes_only_as_one_link_followed_by_the_answer_letters():
    case = Case()
    point = "the *poem* page in `docs/` is recommended"
    case.reply(f"[Item 2 of 10, {point}](https://claude.ai/artifact/x) · {CLOSING_LINE_ANSWER_LETTERS}")
    check_silent("a closing line whose point holds emphasis and a code span passes", case.run(model="yes"))
    case.reply(closing_line("2 of 10").replace("https://claude.ai/artifact/x", "file:///Volumes/nedhome/x/walk.md"))
    check_silent("a closing line whose link is a file:// link passes", case.run(model="yes"))
    case.reply(closing_line("2 of 10", point="the page recommended for `docs/`"))
    check_silent("a closing line whose point ends in a code span passes", case.run(model="yes"))
    letters = f" · {CLOSING_LINE_ANSWER_LETTERS}"
    for case_name, line in (
            ("a question between the link and the answer letters is checked",
             f"[Item 2 of 10, x](https://claude.ai/artifact/x) Should I also merge PR 9?{letters}"),
            ("a closing line without its link is checked",
             f"Item 2 of 10, the poem page is recommended for the wiki{letters}"),
            ("a closing line with its label in brackets but no link target is checked",
             f"[Item 2 of 10, the poem page is recommended for the wiki]{letters}"),
            ("a closing line written as a list item is checked", "- " + closing_line("2 of 10")),
            ("a closing line in bold marks is checked", f"**{closing_line('2 of 10')}**"),
            ("a closing line whose label opens with bold marks is checked",
             closing_line("2 of 10").replace("[Item 2 of 10,", "[**Item 2 of 10**,")),
            ("a closing line whose label opens with a code span is checked",
             closing_line("2 of 10").replace("[Item 2 of 10,", "[`Item 2 of 10`,")),
            ("an italic count and point followed by an empty link is checked",
             f"*Item 2 of 10, the poem page is recommended*[](https://claude.ai/artifact/x){letters}"),
            ("a bold count and point followed by an empty link is checked",
             f"**Item 2 of 10, the poem page is recommended**[](https://claude.ai/artifact/x){letters}"),
            ("a closing line whose label does not open with `Item` in capitals is checked",
             closing_line("2 of 10").replace("[Item", "[item")),
            ("a closing line whose label puts no comma after the count is checked",
             closing_line("2 of 10").replace("2 of 10,", "2 of 10:")),
            ("the closing line's link alone is checked",
             "[Item 2 of 10, the poem page is recommended for the wiki](https://claude.ai/artifact/x)"),
            ("a closing line whose answer letters are a code span is checked",
             f"[Item 2 of 10, the poem page is recommended for the wiki](https://claude.ai/artifact/x)`{letters}`"),
            ("a closing line with emphasis right after its answer letters is checked",
             closing_line("2 of 10") + "*really*"),
            ("a closing line with a second link after the answer letters is checked",
             closing_line("2 of 10") + " [why](https://claude.ai/artifact/y)")):
        case.reply("PR 1922 merged.\n\n" + line)
        check_blocked(case_name, case.run(model="yes"), "approval-walk question check")


def test_the_answer_hooks_closing_line_for_a_point_with_brackets_passes():
    document = WALK_DOCUMENT.replace("## Item 2 of 10: where the poem page lives",
                                     "## Item 2 of 10: the [advisor] check is recommended for the poem page")
    case = Case(document=document,
                minutes="#item_page item 2 of 10 https://claude.ai/artifact/p2\n#next_to_present item 2 of 10")
    line = hook.answer_hook.closing_line("2", hook.answer_hook.read_walk(case.checkout))
    check("the answer hook escapes the point's brackets in its closing line",
          line is not None and line.startswith("[Item 2 of 10, the \\[advisor\\] check"), line)
    case.reply("PR 1922 merged.\n\n" + str(line))
    check_silent("the answer hook's closing line for a point holding brackets passes", case.run(model="yes"))
    case.reply("PR 1922 merged.\n\n" + str(line).replace("\\[", "[").replace("\\]", "]"))
    check_silent("the closing line for a point holding unescaped brackets passes", case.run(model="yes"))
    check("a closing line whose point holds brackets never reaches the model", case.model_calls() == [],
          case.model_calls())


def test_the_refusal_gives_the_waiting_items_closing_line_and_it_passes_once_the_steps_are_done():
    case = Case(minutes="#item_page item 2 of 10 https://claude.ai/artifact/p2\n#next_to_present item 2 of 10")
    case.reply("Should I merge the pull request now?")
    reason = blocked_reason(case.run()) or ""
    unchanged = (f"[Item 2 of {M_WITH_NO_ITEM_ADDED}, where the poem page lives](https://claude.ai/artifact/p2) · "
                 f"{CLOSING_LINE_ANSWER_LETTERS}")
    check("the refusal gives the waiting item's closing line with its page link and the walk's own count, and no "
          "line about a missing page", f"{NO_QUESTION_SENTENCE}\n{unchanged}\nOtherwise run this command" in reason,
          reason)


def test_the_closing_line_and_the_item_ending_are_the_walk_skills():
    skill = (Path(__file__).resolve().parents[4] / ".claude" / "skills" / "walk-me-through" / "SKILL.md").read_text()
    example = next((line for line in skill.split("\n") if line.startswith("[Item 4 of 9, <the point>](<page link>)")),
                   None)
    check("SKILL.md holds the closing line's form, `[Item 4 of 9, <the point>](<page link>) · ...`, on a line of its "
          "own", example is not None, "no such line")
    case = Case()
    case.reply("PR 1922 merged.\n\n" + str(example).replace("4 of 9", "2 of 10").replace(
        "<the point>", "the poem page is recommended for the wiki").replace("<page link>", "https://claude.ai/artifact/x"))
    check_silent("SKILL.md's closing line, filled in for the waiting item, passes", case.run(model="yes"))
    command_spec = importlib.util.spec_from_file_location("question_insert", QUESTION_INSERT_PROGRAM)
    command = importlib.util.module_from_spec(command_spec)
    command_spec.loader.exec_module(command)
    ending = "the recommendation stated as an action"
    check("the command's output ends the new item as SKILL.md's section \"Each item\" says",
          "end it with " + ending in skill and ending in command.NEXT_STEPS_LINES[0], command.NEXT_STEPS_LINES[0])
    check("the command's output and SKILL.md's section \"Each item\" both open the alternative with "
          "\"The alternative:\"", "`The alternative: " in command.NEXT_STEPS_LINES[0]
          and "State the alternative just before the recommendation, as in \"The alternative: " in skill,
          command.NEXT_STEPS_LINES[0])
    check("SKILL.md's Style paragraph puts the strongest case against just before the alternative, where \"Each item\" "
          "puts the alternative", "Just before the alternative, state the strongest case against the recommendation"
          in skill)
    check_spec = importlib.util.spec_from_file_location(
        "walk_check", Path(QUESTION_INSERT_PROGRAM).parent / "walk-me-through-answer-added-texts-cold-read-fast-read-check-and-close.py")
    walk_check = importlib.util.module_from_spec(check_spec)
    check_spec.loader.exec_module(walk_check)
    check("the walk check program's missing-line refusal puts the `#case_against` line where SKILL.md does",
          "just before its `The alternative:` line" in walk_check.CASE_AGAINST_MISSING, walk_check.CASE_AGAINST_MISSING)
    for name, text in (("the walk check program's missing-line refusal", walk_check.CASE_AGAINST_MISSING),
                       ("the command's output", command.NEXT_STEPS_LINES[0])):
        check(name + " gives the rated form and SKILL.md's `#case_against none.` form",
              "`#case_against weak: the fix costs an hour of fast reads.`" in text and "`#case_against none.`" in text
              and "`#case_against none.`" in skill, text)


SUB_STEP_2_1_NO_DECISION_CLOSING_LINE = "[No decision here; type N or next to continue.](https://claude.ai/artifact/p21)"


def test_the_no_decision_line_is_skipped_whatever_item_waits():
    sub_step = Case(document=WALK_DOCUMENT.replace("of 10", "of 11") + "\n" + INTERRUPTION_ITEM,
                    minutes="#next_to_present item 2.1 of 11")
    sub_step.reply("PR 1922 merged.\n\n" + SUB_STEP_2_1_NO_DECISION_CLOSING_LINE)
    check_silent("the no-decision line passes while a sub-step waits", sub_step.run(model="yes"))
    check("the no-decision line never reaches the model", sub_step.model_calls() == [], sub_step.model_calls())
    sub_step.reply("PR 1922 merged.\n\n" + SUB_STEP_2_1_NO_DECISION_CLOSING_LINE + " Agree?")
    check_blocked("the no-decision line with text after it is checked", sub_step.run(model="yes"),
                  "approval-walk question check")
    whole_item = Case()
    for case_name, line in (
            ("the no-decision line a whole item's summary ended with passes, since it asks nothing",
             "[No decision here; type N or next to continue.](https://claude.ai/artifact/EfeHPme4RgDpPRFiVaXegU)"),
            ("the no-decision line without its link passes", "No decision here; type N or next to continue.")):
        whole_item.reply("No decision here.\n\n" + line)
        check_silent(case_name, whole_item.run(model="yes"))
    check("the no-decision line of a whole item never reaches the model", whole_item.model_calls() == [],
          whole_item.model_calls())


def test_an_ask_phrase_only_inside_quoted_text_goes_to_the_model():
    case = Case()
    explanation = ('The walk skill says an item that asks no decision, like the summary, ends with the line "No '
                   'decision here; type N or next to continue." I wrote exactly that line, and two hooks refused it:')
    case.reply(explanation)
    check_silent("an ask phrase quoted in an explanation passes when the model says it asks nothing",
                 case.run(model="no"))
    check("the line with the quoted ask phrase went to the model", len(case.model_calls()) == 1, case.model_calls())
    check_blocked("the same line blocks when the model says it asks the user something", case.run(model="yes:1"),
                  "the model judged that it asks him something")
    case.reply('merge-lane-2 says: "Answer A and I will merge it."')
    check_blocked("an ask relayed in quotes from another agent still blocks once the model says so",
                  case.run(model="yes:1"), "approval-walk question check")


def test_a_hyphenated_word_after_yes_or_no_is_not_an_ask():
    case = Case()
    for case_name, text in (
            ("a quoted task title with `a no-decision` passes without the model",
             'I started a background subagent on task #392, "Walk hooks contradict SKILL.md on a no-decision '
             'item\'s closing line".'),
            ("`on a no-decision item` outside quotes passes", "The hook now passes the line on a no-decision item."),
            ("`type no-op` passes", "Then type no-op lines into the test file.")):
        case.reply(text)
        check_silent(case_name, case.run(model="yes"))
    check("a hyphenated word after yes or no never reaches the model", case.model_calls() == [], case.model_calls())
    case.reply("The fix is ready; on a yes I will push it.")
    check_blocked("`on a yes` still goes to the model, and blocks when the model says it asks the user something",
                  case.run(model="yes"), "the model judged that it asks him something")


def test_an_answer_cue_followed_by_another_hyphenated_word_goes_to_the_model():
    for case_name, text in (("`Type A-D`", "Type A-D to answer."),
                            ("`Say yes-or-no`", "Say yes-or-no and I will merge it."),
                            ("`on a yes-or-no`", "I will merge it on a yes-or-no from you."),
                            ("`on a yes-decision`", "I will merge it on a yes-decision from you."),
                            ("`Reply A-OP`", "Reply A-OP to approve the operation."),
                            ("`Type D-OP`", "Type D-OP to drop the operation."),
                            ("`Say no-opinion`", "Say no-opinion if you have none.")):
        case = Case()
        case.reply(text)
        check_blocked(case_name + " blocks when the model says it asks the user something", case.run(model="yes:1"),
                      "the model judged that it asks him something")
        check(case_name + " went to the model", len(case.model_calls()) == 1, case.model_calls())
        check_silent(case_name + " passes when the model says it asks nothing", case.run(model="no"))


PUBLISH_FAILED_LINE = "#item_page item {number} of {total} publish failed: the Artifact tool timed out"
RECOMMENDED_ITEM_2_DOCUMENT = WALK_DOCUMENT.replace("## Item 2 of 10: where the poem page lives",
                                                    "## Item 2 of 10: the poem page is recommended for the wiki")


def test_the_closing_line_without_its_link_is_skipped_only_for_an_item_whose_publish_failed():
    failed = Case(document=RECOMMENDED_ITEM_2_DOCUMENT,
                  minutes=PUBLISH_FAILED_LINE.format(number=2, total=10) + "\n#next_to_present item 2 of 10")
    line = hook.answer_hook.closing_line("2", hook.answer_hook.read_walk(failed.checkout))
    check("the answer hook's closing line for an item whose publish failed has no link",
          line == f"Item 2 of 10, the poem page is recommended for the wiki · {CLOSING_LINE_ANSWER_LETTERS}", line)
    failed.reply("Recorded.\n\n" + str(line))
    check_silent("the closing line without its link passes for an item whose newest publish failed",
                 failed.run(model="yes"))
    check("the closing line without its link of an item whose publish failed never reaches the model",
          failed.model_calls() == [], failed.model_calls())
    republished = Case(document=RECOMMENDED_ITEM_2_DOCUMENT,
                       minutes=PUBLISH_FAILED_LINE.format(number=2, total=10)
                       + "\n#item_page item 2 of 10 https://claude.ai/artifact/p2\n#next_to_present item 2 of 10")
    republished.reply("Recorded.\n\n" + str(line))
    check_blocked("the closing line without its link is checked once a later `#item_page` line gives the item a page",
                  republished.run(model="yes"), "approval-walk question check")
    two_waiting = Case(document=RECOMMENDED_ITEM_2_DOCUMENT,
                       minutes=PUBLISH_FAILED_LINE.format(number=2, total=10) + "\n#next_to_present items 2 and 3 of 10")
    two_waiting.reply("Recorded.\n\n" + str(line) + "\n\n"
                      + f"Item 3 of 10, the hook is recommended · {CLOSING_LINE_ANSWER_LETTERS}")
    check_blocked("the closing line without its link is checked for a waiting item whose publish did not fail",
                  two_waiting.run(model="yes"), "approval-walk question check", "Item 3 of 10, the hook")


def test_a_message_ending_with_a_closing_line_blocks_when_the_checkout_holds_no_open_or_paused_walk():
    ending = "PR 1922 merged.\n\n" + closing_line("2 of 10")
    empty = Case()
    empty.document.unlink()
    empty.minutes.unlink()
    empty.reply(ending)
    reason = blocked_reason(empty.run(model="yes")) or ""
    walk_directory = empty.checkout / "docs" / "walk"
    for case_name, phrase in (
            ("a closing line with an empty docs/walk/ blocks, saying the hook refused on purpose",
             "approval-walk closing-line check: this hook refused to end your turn on purpose"),
            ("the block quotes the closing line", f'"{closing_line("2 of 10")}"'),
            ("the block names the checkout searched and its docs/walk/",
             f"the checkout you work in, {empty.checkout}, has no open or paused approval-walk in {walk_directory}."),
            ("the block tells the agent to move the walk's files into that docs/walk/",
             f"move both files into {walk_directory}, creating {walk_directory} if it is missing"),
            ("the block says what to do from now on",
             "From now on, keep the walk-document and walk-minutes of every approval-walk you run in the `docs/walk/` "
             "of the checkout you work in.")):
        check(case_name, phrase in reason, reason)
    check("a closing line with no walk never reaches the model", empty.model_calls() == [], empty.model_calls())
    entries = empty.logged()
    check("the block is logged with its sentence, no walk, and what decided",
          len(entries) == 1 and entries[0]["walk"] is None and entries[0]["sentence"] == closing_line("2 of 10")
          and entries[0]["decided_by"] == "no-walk-in-checkout", entries)
    missing = Case()
    shutil.rmtree(missing.walk)
    missing.reply(ending)
    check_blocked("a closing line with no docs/walk/ blocks, saying the folder does not exist", missing.run(),
                  f"in {missing.walk}, which does not exist.")
    closed = Case(minutes="#next_to_present none, closed")
    for case_name, text in (
            ("a closing line after a closed walk blocks", ending),
            ("a closing line without its link blocks",
             f"PR 1922 merged.\n\nItem 2 of 10, the poem page · {CLOSING_LINE_ANSWER_LETTERS}")):
        closed.reply(text)
        check_blocked(case_name, closed.run(), "approval-walk closing-line check", str(closed.checkout))
    check_blocked("a closing line only in the payload's last_assistant_message blocks",
                  closed.run(last_assistant_message=ending), "approval-walk closing-line check")
    closed.reply("Should I merge it?\n\n" + closing_line("2 of 10"))
    check_blocked("the closing line ending the turn's last text blocks when the payload has no last message",
                  closed.run(last_assistant_message=""), "approval-walk closing-line check")
    for case_name, text in (
            ("a reply with no walk and no closing line passes", "Should I merge it?"),
            ("a closing line that is not the message's last line passes", closing_line("2 of 10") + "\n\nDone."),
            ("a closing line inside a code block passes", f"PR 1922 merged.\n\n```\n{closing_line('2 of 10')}\n```"),
            ("a line holding the answer letters that is not a closing line passes",
             f"The skill's letters are {CLOSING_LINE_ANSWER_LETTERS}")):
        closed.reply(text)
        check_silent(case_name, closed.run())
    two = Case()
    # The second walk has a readable waiting item, so a finder that took either walk alone would ask the model.
    (two.walk / "a-second-walk.md").write_text("# A second walk\n\n## Item 4 of 9: the merge\n\nMerge it.\n")
    (two.walk / "a-second-walk-minutes.md").write_text("#next_to_present item 4 of 9\n")
    two.reply("The tests passed.\n\nShould I merge the pull request now?")
    check_silent("a question-like line passes when two approval-walks are open, since no waiting item is known",
                 two.run(model="yes"))
    check("a question-like line while two approval-walks are open never reaches the model",
          two.model_calls() == [], two.model_calls())
    paused = Case(minutes="#next_to_present item 2 of 10\n#approval_walk_paused")
    paused.reply(ending)
    check_silent("a closing line while the walk is paused passes", paused.run())
    paused.reply("The tests passed.\n\nShould I merge the pull request now?")
    check_silent("a question-like line while the walk is paused passes, though the model would say it asks",
                 paused.run(model="yes"))
    check("a question-like line while the walk is paused never reaches the model",
          paused.model_calls() == [], paused.model_calls())
    outside = Case()
    outside.reply(ending)
    shutil.rmtree(outside.checkout / ".git")
    check_silent("a closing line from a cwd outside any checkout passes", outside.run())


def test_a_fault_exits_1_and_names_it():
    case = Case()
    result = case.run(stdin_text="not json")
    check("input that is not JSON exits 1 and names the fault on stderr",
          result.returncode == 1 and result.stdout == "" and result.stderr.startswith(
              "walk-me-through-agent-question-to-user-outside-approval-walk-items-refusal-stop-hook: the hook failed")
          and "JSONDecodeError" in result.stderr and "Traceback" not in result.stderr,
          f"exit {result.returncode}, stderr {result.stderr!r}")


LIVE_MODEL_FLAG = "--skip-tests-and-print-live-claude-labels-of-sample-lines"
LIVE_BIN = SUITE_ROOT / "live-bin"
LIVE_RECORDER = """#!/usr/bin/env python3
import json, os, subprocess, sys
prompt = sys.stdin.read()
completed = subprocess.run([REAL_CLAUDE] + sys.argv[1:], input=prompt, capture_output=True, text=True)
with open(os.environ["FAKE_CLAUDE_CALLS"], "a") as calls:
    calls.write(json.dumps({"argv": sys.argv[1:], "stdin": prompt, "stdout": completed.stdout,
                            "stderr": completed.stderr, "returncode": completed.returncode}) + "\\n")
sys.stdout.write(completed.stdout)
sys.stderr.write(completed.stderr)
sys.exit(completed.returncode)
"""


def print_live_model_labels():
    real_claude = shutil.which("claude")
    if real_claude is None:
        print("claude is not on PATH, so the live model cannot be run.")
        return 1
    LIVE_BIN.mkdir(parents=True)
    recorder = LIVE_BIN / "claude"
    recorder.write_text(LIVE_RECORDER.replace("#!/usr/bin/env python3", f"#!{sys.executable}", 1)
                        .replace("REAL_CLAUDE", json.dumps(real_claude)))
    recorder.chmod(0o755)
    try:
        for case_name, reply, item_text, minutes, _ in REAL_CASES + (UNRELATED_ASK_CASE,):
            case = Case(document=f"# A walk\n\n{item_text}\n", minutes=minutes)
            case.reply(reply)
            result = case.run(bin_directory=LIVE_BIN)
            reason = blocked_reason(result)
            print(f"== {case_name}")
            print("hook: " + ("passed" if result.returncode == 0 and not result.stdout else
                              (reason or f"exit {result.returncode}: {result.stdout}{result.stderr}").split("\n")[0][:400]))
            calls = case.model_calls()
            if not calls:
                print("model: not called")
            for call in calls:
                try:
                    label = json.loads(call["stdout"])["structured_output"]["labels"][0]
                except (ValueError, TypeError, KeyError, IndexError):
                    print(f"model: no label; exit {call['returncode']}: {call['stdout'][:300]}{call['stderr'][:300]}")
                    continue
                print(f"model: ask {label.get('ask')} ({label.get('reason')}) <- {judged_line(call)[:160]}")
    finally:
        shutil.rmtree(SUITE_ROOT, ignore_errors=True)
    return 0


def test_silent_during_an_emergency_stop():
    case = Case()
    case.reply("The tests passed.\n\nShould I merge the pull request now?\n\nItem 2 of 10 is waiting for your answer.")
    stop_folder = case.root / "emergency-stop"
    stop_folder.mkdir()
    stop_file = stop_folder / "2026-10-30T01-00-00Z.md"
    stop_file.write_text("# Emergency stop\ncoordinating agent-seat: reboot-test\n")
    check_silent("a question outside the walk passes while an emergency stop is in force",
                 case.run(model="yes", environment_extra={"NEDSNODES_EMERGENCY_STOP_FOLDER": str(stop_folder)}))
    stop_file.write_bytes(b"\xff\xfe")
    check_silent("an unreadable emergency-stop file counts as a stop in force",
                 case.run(model="yes", environment_extra={"NEDSNODES_EMERGENCY_STOP_FOLDER": str(stop_folder)}))
    stop_file.write_text("started\n#emergency_stop_lifted all clear\n")
    check_blocked("after the lift the question is refused again",
                  case.run(model="yes", environment_extra={"NEDSNODES_EMERGENCY_STOP_FOLDER": str(stop_folder)}),
                  '"Should I merge the pull request now?"')


NO_DECISION_SUB_STEP_DOCUMENT = """# A walk

## Item 4 of 9: a filter

### Item 4.1 of 9: What a filter does

A filter hides old rows.

[No decision here; type N or next to continue.](https://claude.ai/artifact/p41)

### Item 4.2 of 9: The choice

Recommendation: leave the filter out.

## Item 5 of 9: the next item

Recommendation: do the next thing.
"""
NO_DECISION_LINE = "[No decision here; type N or next to continue.](https://claude.ai/artifact/p41)"
NO_DECISION_PAGES = ("#item_page item 4.1 of 9 https://claude.ai/artifact/p41\n"
                     "#item_page item 4.2 of 9 https://claude.ai/artifact/p42\n")


def test_the_question_refusal_on_a_no_decision_sub_step_offers_only_next():
    case = Case(document=NO_DECISION_SUB_STEP_DOCUMENT,
                minutes=NO_DECISION_PAGES + "#next_to_present item 4.1 of 9")
    case.reply("Should I merge the pull request now?\n\n" + NO_DECISION_LINE)
    result = case.run(model="yes")
    check_blocked("the refusal gives the no-decision line", result, NO_DECISION_LINE)
    check("the refusal offers no A, D or M", "A approve" not in (blocked_reason(result) or "A approve"),
          blocked_reason(result))
    case.reply("The tests passed.\n\n" + NO_DECISION_LINE)
    check_silent("the line the refusal printed passes when it ends the reply", case.run(model="no"))


def main():
    if sys.argv[1:] == [LIVE_MODEL_FLAG]:
        return print_live_model_labels()
    FAKE_BIN.mkdir(parents=True)
    fake = FAKE_BIN / "claude"
    fake.write_text(FAKE_CLAUDE.replace("#!/usr/bin/env python3", f"#!{sys.executable}", 1))
    fake.chmod(0o755)
    try:
        for name, function in sorted(globals().items()):
            if name.startswith("test_") and callable(function):
                function()
    finally:
        shutil.rmtree(SUITE_ROOT, ignore_errors=True)
    if failures:
        print(f"{len(failures)} failed: {', '.join(failures)}")
        return 1
    print("all passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
