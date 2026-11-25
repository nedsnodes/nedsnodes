#!/usr/bin/env python3
"""Cases for the program that prints what the user said in every agent-session whose dialog names an approval-walk
item's title, and every walk-minutes line naming it. Each case runs the program as a subprocess over a fixture
log-store and fixture agent-homes this suite writes; the exit code is asserted on every case."""

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

PROGRAM = (Path(__file__).resolve().parents[1]
           / "walk-me-through-approval-walk-item-title-search-user-messages-in-session-dialogs-and-lines-in-walk-minutes-print.py")
LOG_STORE_PAST_DISCUSSIONS_SEARCH_ROOT_OVERRIDE_ENVIRONMENT_VARIABLE = "LOG_STORE_PAST_DISCUSSIONS_SEARCH_LOG_STORE_ROOT_OVERRIDE"
LOG_STORE_PAST_DISCUSSIONS_SEARCH_RIPGREP_OVERRIDE_ENVIRONMENT_VARIABLE = "LOG_STORE_PAST_DISCUSSIONS_SEARCH_RIPGREP_PROGRAM_OVERRIDE"
AGENT_HOMES_DIRECTORY_OVERRIDE_ENVIRONMENT_VARIABLE = "WALK_ME_THROUGH_AGENT_HOMES_DIRECTORY_OVERRIDE"
LOG_STORE_PAST_DISCUSSIONS_SEARCH_THIS_MACHINE_OVERRIDE_ENVIRONMENT_VARIABLE = "LOG_STORE_PAST_DISCUSSIONS_SEARCH_THIS_MACHINE_OVERRIDE"
LOG_STORE_PAST_DISCUSSIONS_SEARCH_SSH_OVERRIDE_ENVIRONMENT_VARIABLE = "LOG_STORE_PAST_DISCUSSIONS_SEARCH_SSH_PROGRAM_OVERRIDE"
ITEM_6_TITLE = "How long the successor looks for a speed-up"
RULING = ("I had a discussion on this topic - check the session dialogs. I thought we agree to split tasks into "
          "those that could and should be backgrounded and others that should not")
PROJECT_KEY = "-home-nedlern-agents-MD-skills"
PROGRAM_PROJECT_KEY = "-home-nedlern--local-state-nedsnodes-agent-seat-idle-sweep"

failures = []


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


def user_record(text, entrypoint="cli"):
    return {"type": "user", "entrypoint": entrypoint, "timestamp": "2026-11-21T10:00:00Z",
            "message": {"role": "user", "content": text}}


def agent_record(text):
    return {"type": "assistant", "timestamp": "2026-11-21T10:00:01Z",
            "message": {"role": "assistant", "content": [{"type": "text", "text": text}]}}


def dialog_text(records):
    """A session dialog as the extractor writes one: a "## User" or "## Agent" heading, a blank line, the text."""
    lines = ["# Complete session dialog", "", "---", ""]
    for record in records:
        content = record["message"]["content"]
        text = content if isinstance(content, str) else content[0]["text"]
        lines += ["## User" if record["type"] == "user" else "## Agent", "", text, ""]
    return "\n".join(lines) + "\n"


class Store:
    """One case's fixture log-store and agent-homes."""

    def __init__(self, root):
        self.root = root
        self.log_store = root / "log-store"
        (self.log_store / "session-dialogs").mkdir(parents=True)
        (self.log_store / "walk").mkdir()
        self.agent_homes = root / "agent-homes"
        self.agent_homes.mkdir()

    def session(self, session_id, records, project_key=PROJECT_KEY, write_transcript=True):
        """Write a session's transcript and its dialog; return the dialog's path."""
        dialog = self.log_store / "session-dialogs" / "ned-box" / project_key / f"{session_id}-dialog-complete.md"
        dialog.parent.mkdir(parents=True, exist_ok=True)
        dialog.write_text(dialog_text(records))
        if write_transcript:
            transcript = (self.log_store / "agent-session-files-by-machine" / "ned-box" / "projects" / project_key
                          / f"{session_id}.jsonl")
            transcript.parent.mkdir(parents=True, exist_ok=True)
            transcript.write_text("".join(json.dumps(record) + "\n" for record in records))
        return dialog

    def run(self, *words, environment=None):
        environment = dict(os.environ, **(environment or {}))
        environment[LOG_STORE_PAST_DISCUSSIONS_SEARCH_ROOT_OVERRIDE_ENVIRONMENT_VARIABLE] = str(self.log_store)
        environment[AGENT_HOMES_DIRECTORY_OVERRIDE_ENVIRONMENT_VARIABLE] = str(self.agent_homes)
        return subprocess.run([sys.executable, str(PROGRAM), *words], capture_output=True, text=True,
                              env=environment)


def item_6_store(root):
    """The item 6 case: the user's ruling comes in an agent-session well before its dialog names the item's title,
    which a program-started agent-session's dialog names too."""
    store = Store(root)
    dialog = store.session("77caebaf", [
        agent_record("[Item 67 of 158, A background Bash task outlives a session] · A approve · D disapprove"),
        user_record(RULING),
        user_record("in fact we were discussing building a more ambitious system"),
        agent_record("Rewriting item 67."),
        agent_record(f"## {ITEM_6_TITLE}\n\nThe successor looks for a speed-up first."),
    ])
    store.session("sweep0001", [
        user_record(f"[Item 6 of 27, {ITEM_6_TITLE}] the idle sweep's prompt", entrypoint="sdk-cli"),
        agent_record("Nothing to do."),
    ], project_key=PROGRAM_PROJECT_KEY)
    minutes = store.agent_homes / "MD-skills-2" / "docs" / "walk" / "some-walk-2026-11-21-minutes.md"
    minutes.parent.mkdir(parents=True)
    minutes.write_text(f"# Minutes\n\nitem 6 of 27, \"{ITEM_6_TITLE}\": the user answered later.\n")
    # A walk-document naming the title is not walk-minutes, so it is not printed.
    (minutes.parent / "some-walk-2026-11-21.md").write_text(f"## Item 6 of 27: {ITEM_6_TITLE}\n")
    return store, dialog, minutes


def test_the_user_ruling_in_an_agent_session_naming_the_title_is_printed_after_the_agent_message_it_answers(root):
    store, dialog, minutes = item_6_store(root)
    result = store.run("--title", ITEM_6_TITLE, "--item-number", "6")
    lines = result.stdout.splitlines()
    ruling = next((index for index, line in enumerate(lines) if RULING in line), None)
    check("the user's ruling is printed, with the dialog's file and line, after the agent message it answers",
          result.returncode == 0 and ruling is not None
          and lines[ruling].startswith(f"  user   {dialog}:11  ")
          and lines[ruling - 1].startswith(f"  agent  {dialog}:7  [Item 67 of 158")
          and lines[ruling + 1].startswith(f"  user   {dialog}:15  in fact")
          and "Agent-session 77caebaf (MD-skills, ned-box), its dialog naming the title at line(s) 23:" in lines,
          result.stdout + result.stderr)
    check("an agent-session a program started is left out, and counted",
          "sweep0001" not in result.stdout and "the idle sweep's prompt" not in result.stdout
          and "1 agent-session(s) in which the user typed nothing" in lines[0],
          result.stdout)
    check("a walk-minutes line naming the title is printed with its file and line, and a walk-document's is not",
          f"  {minutes}:3  item 6 of 27, \"{ITEM_6_TITLE}\": the user answered later." in lines
          and "Walk-minutes lines naming the title: 1." in lines and "some-walk-2026-11-21.md:" not in result.stdout,
          result.stdout)


def test_a_short_title_names_the_item_only_right_after_one_of_its_numbers(root):
    store = Store(root)
    named = store.session("named", [agent_record("### Item 9.2 of 35: The fix\n\nWhat you are approving."),
                                    user_record("a")])
    store.session("heading", [agent_record("## The fix\n\nAnother walk's fix."), user_record("not this one")])
    store.session("other-number", [agent_record("### Item 9.25 of 35: The fix"), user_record("nor this one")])
    result = store.run("--title", "The fix", "--item-number", "9.2")
    check("a title of fewer than four words is matched only after \"Item\" and one of the item's numbers",
          result.returncode == 0 and f"  user   {named}:13  a" in result.stdout
          and "not this one" not in result.stdout and "nor this one" not in result.stdout,
          result.stdout + result.stderr)


def test_nothing_found_exits_3(root):
    store = Store(root)
    store.session("unrelated", [agent_record("Something else."), user_record("ok")])
    result = store.run("--title", ITEM_6_TITLE, "--item-number", "6")
    check("nothing found exits 3, not 1, which an uncaught exception exits with, and says so",
          result.returncode == 3 and "was named before: 0 agent-session(s)" in result.stdout
          and "Walk-minutes lines naming the title: 0." in result.stdout and result.stderr == "",
          result.stdout + result.stderr)


def test_a_walk_minutes_line_that_is_not_valid_utf_8_is_printed(root):
    store = Store(root)
    minutes = store.agent_homes / "MD-skills-2" / "docs" / "walk" / "some-walk-2026-11-21-minutes.md"
    minutes.parent.mkdir(parents=True)
    # ripgrep's JSON gives such a line as base64 "bytes", not "text".
    minutes.write_bytes(f"item 6 of 27, \"{ITEM_6_TITLE}\": answered \xff later.\n".encode("latin-1"))
    result = store.run("--title", ITEM_6_TITLE, "--item-number", "6")
    check("a walk-minutes line that is not valid UTF-8 is printed, its bad byte replaced",
          result.returncode == 0
          and f"  {minutes}:1  item 6 of 27, \"{ITEM_6_TITLE}\": answered \ufffd later." in result.stdout,
          result.stdout + result.stderr)


def test_ripgrep_that_cannot_run_is_a_failure(root):
    store, _, _ = item_6_store(root)
    result = store.run("--title", ITEM_6_TITLE, "--item-number", "6",
                       environment={LOG_STORE_PAST_DISCUSSIONS_SEARCH_RIPGREP_OVERRIDE_ENVIRONMENT_VARIABLE: str(root / "no-such-rg")})
    check("a ripgrep that cannot be run prints a FAILED line and exits 2",
          result.returncode == 2 and result.stderr.startswith("FAILED: ripgrep (")
          and "is not installed" in result.stderr,
          result.stdout + result.stderr)


def test_a_dialog_whose_transcript_is_gone_is_named_for_the_agent_to_read(root):
    store = Store(root)
    dialog = store.session("lost", [agent_record(f"## {ITEM_6_TITLE}"), user_record("yes")], write_transcript=False)
    result = store.run("--title", ITEM_6_TITLE, "--item-number", "6")
    check("a dialog naming the title whose transcript is not in the log-store is named for the agent to read, "
          "and is no failure",
          result.returncode == 0 and result.stderr == ""
          and "its transcript " in result.stdout and f'read its "## User" turns in {dialog} yourself.' in result.stdout,
          result.stdout + result.stderr)


def test_a_transcript_that_cannot_be_read_is_a_failure(root):
    store = Store(root)
    dialog = store.session("unreadable", [agent_record(f"## {ITEM_6_TITLE}"), user_record("yes")])
    transcript = (store.log_store / "agent-session-files-by-machine" / "ned-box" / "projects" / PROJECT_KEY
                  / "unreadable.jsonl")
    transcript.unlink()
    transcript.mkdir()
    result = store.run("--title", ITEM_6_TITLE, "--item-number", "6")
    check("a dialog naming the title whose transcript cannot be read prints a FAILED line naming both and exits 2",
          result.returncode == 2 and "FAILED: could not read the transcript " in result.stderr
          and str(dialog) in result.stderr,
          result.stdout + result.stderr)


def test_a_missing_session_dialogs_directory_is_a_failure(root):
    store = Store(root)
    shutil.rmtree(store.log_store / "session-dialogs")
    result = store.run("--title", ITEM_6_TITLE, "--item-number", "6")
    check("a log-store without session-dialogs/ prints a FAILED line and exits 2",
          result.returncode == 2 and "FAILED: the log-store has no " in result.stderr,
          result.stdout + result.stderr)


def test_no_log_store_on_ned_box_is_a_failure_and_from_another_machine_runs_ned_box_copy_over_ssh(root):
    store = Store(root)
    shutil.rmtree(store.log_store)
    on_ned_box = store.run("--title", ITEM_6_TITLE, "--item-number", "6",
                           environment={LOG_STORE_PAST_DISCUSSIONS_SEARCH_THIS_MACHINE_OVERRIDE_ENVIRONMENT_VARIABLE: "ned-box"})
    check("no log-store on ned-box prints a FAILED line and exits 2",
          on_ned_box.returncode == 2 and on_ned_box.stderr.startswith("FAILED: there is no log-store at "),
          on_ned_box.stdout + on_ned_box.stderr)
    calls = root / "ssh-calls.json"
    ssh = root / "ssh-stand-in.py"
    ssh.write_text(f"#!{sys.executable}\nimport json, sys\n"
                   f"open({str(calls)!r}, 'w').write(json.dumps(sys.argv[1:]))\nprint('from ned-box')\n")
    ssh.chmod(0o755)
    on_mac = store.run("--title", ITEM_6_TITLE, "--item-number", "6",
                       environment={LOG_STORE_PAST_DISCUSSIONS_SEARCH_THIS_MACHINE_OVERRIDE_ENVIRONMENT_VARIABLE: "mac",
                                    LOG_STORE_PAST_DISCUSSIONS_SEARCH_SSH_OVERRIDE_ENVIRONMENT_VARIABLE: str(ssh)})
    remote = json.loads(calls.read_text())[-1] if calls.is_file() else ""
    check("from another machine without the log-store, ned-box's copy of this program runs over ssh",
          on_mac.returncode == 0 and on_mac.stdout == "from ned-box\n"
          and remote.startswith("python3 /home/nedlern/Projects/nedsnodes/nn-systems/skills/walk-me-through/"
                                + PROGRAM.name + " --title ")
          and "--item-number 6" in remote,
          on_mac.stdout + on_mac.stderr + str(remote))


def main():
    cases = [value for name, value in globals().items() if name.startswith("test_")]
    with tempfile.TemporaryDirectory() as scratch:
        for number, case in enumerate(cases):
            root = Path(scratch) / f"case-{number}"
            root.mkdir()
            case(root)
    print(f"{len(failures)} failed" if failures else "all passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
