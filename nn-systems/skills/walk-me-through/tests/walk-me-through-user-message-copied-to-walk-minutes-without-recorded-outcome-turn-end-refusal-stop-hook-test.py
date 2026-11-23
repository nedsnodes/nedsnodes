#!/usr/bin/env python3
"""Cases for the Stop hook that refuses to end a turn while a user message copied into the open approval-walk's
walk-minutes has no outcome. Each case runs the hook as a subprocess in a scratch checkout this suite made."""

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[4]
WALK_SKILL_DIRECTORY = Path(__file__).resolve().parents[1]


def load(name, path):
    specification = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


load("git_redirecting_environment_removal_test_fixture", REPOSITORY / "scripts" / "git-redirecting-environment-removal-test-fixture.py"
     ).remove_git_redirecting_environment_variables_from_this_process()
attendance_check = load("agent_session_unattended_by_user_check_common",
                        REPOSITORY / "nn-systems" / "general-tools" / "agent-session-unattended-by-user-check-common.py")
walk_finder = load("walk_me_through_approval_walk_minutes_and_walk_document_item_finder_common",
                   WALK_SKILL_DIRECTORY / "walk-me-through-approval-walk-minutes-and-walk-document-item-finder-common.py")
HOOK_SCRIPT = (WALK_SKILL_DIRECTORY
               / "walk-me-through-user-message-copied-to-walk-minutes-without-recorded-outcome-turn-end-refusal-stop-hook.py")
SUITE_ROOT = Path(tempfile.mkdtemp(prefix="walk-user-message-outcome-stop-hook-test-")).resolve()
WALK_DOCUMENT = ("# A walk\n\n## Item 3 of 9: the poem page\n\nThe page goes in the wiki.\n\nRecommendation: put it there.\n\n"
                 "## Item 4 of 9: the hook\n\nA hook checks pages.\n\nRecommendation: add it.\n")
failures = []


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


class Case:
    counter = 0

    def __init__(self, extra_minutes=""):
        Case.counter += 1
        self.checkout = SUITE_ROOT / f"case-{Case.counter}"
        self.walk = self.checkout / "docs" / "walk"
        self.walk.mkdir(parents=True)
        subprocess.run(["git", "init", "-q", str(self.checkout)], check=True)
        self.document = self.walk / "poem.md"
        self.document.write_text(WALK_DOCUMENT)
        self.minutes = self.walk / "poem-minutes.md"
        parser = walk_finder.markdown_parser()
        line = walk_finder.approval_walk_minutes_user_message_copied_line_build(
            "", "item 3 of 9", self.document, "please reword the page", datetime(2026, 11, 23, 17, 38, tzinfo=timezone.utc), parser)
        self.minutes.write_text(f"# Minutes\n\n#next_to_present item 3 of 9\n{line}\n{extra_minutes}")

    def add(self, line):
        with open(self.minutes, "a", encoding="utf-8") as file:
            file.write(line + "\n")

    def run(self, stop_hook_active=False, environment_extra=None, stdin_text=None, session_id="test-session"):
        payload = {"hook_event_name": "Stop", "session_id": session_id, "cwd": str(self.checkout),
                   "transcript_path": str(self.checkout / "no-transcript.jsonl"), "stop_hook_active": stop_hook_active}
        environment = attendance_check.environment_without_agent_session_attendance_variables(os.environ)
        environment["NEDSNODES_EMERGENCY_STOP_FOLDER"] = str(self.checkout / "no-emergency-stop")
        environment.update(environment_extra or {})
        return subprocess.run([sys.executable, str(HOOK_SCRIPT)],
                              input=json.dumps(payload) if stdin_text is None else stdin_text,
                              capture_output=True, text=True, env=environment, cwd=self.checkout)


def reason(result):
    if result.returncode != 0 or not result.stdout.strip():
        return None
    output = json.loads(result.stdout)
    return output["reason"] if output.get("decision") == "block" else None


def check_silent(case_name, result):
    check(case_name, result.returncode == 0 and result.stdout == "", f"{result!r}")


def test_a_copied_line_with_no_outcome_refuses_and_says_what_to_add():
    case = Case()
    refusal = reason(case.run())
    check("a copied line with no outcome refuses the turn's end",
          refusal is not None and refusal.startswith("[rule walk-me-through-user-message-copied-line-needs-outcome]"), refusal)
    check("the refusal names the id, item, his words and all three outcomes",
          refusal is not None and all(phrase in refusal for phrase in (
              "id 1, item 3 of 9", "please reword the page", "'#user_message_outcome 1 changed' >> ",
              "'#user_message_outcome 1 no change' >> ", "'#user_message_outcome 1 open' >> ")), refusal)
    check("a successor, with another session id, is refused for the same line",
          reason(case.run(session_id="successor-session")) is not None)


def test_each_printed_command_records_its_outcome():
    for label, outcome in (("no change", "no change"), ("open", "open")):
        case = Case()
        refusal = reason(case.run())
        command = next(line.split(": ", 1)[1] for line in refusal.split("\n") if line.startswith(f"  {label}: printf"))
        subprocess.run(["bash", "-c", command], check=True)
        check(f"the printed `{label}` command writes the outcome line",
              f"#user_message_outcome 1 {outcome}\n" in case.minutes.read_text(), case.minutes.read_text())
        check_silent(f"after the printed `{label}` command the hook is silent", case.run())
    case = Case()
    refusal = reason(case.run())
    command = next(line.split(": ", 1)[1] for line in refusal.split("\n") if line.startswith("  changed: printf"))
    case.document.write_text(WALK_DOCUMENT.replace("in the wiki", "in the handbook"))
    subprocess.run(["bash", "-c", command], check=True)
    check_silent("after an item edit and the printed `changed` command the hook is silent", case.run())


def test_no_change_and_open_each_end_the_refusal():
    for outcome in ("no change", "open"):
        case = Case()
        case.add(f"#user_message_outcome 1 {outcome}")
        check_silent(f"outcome `{outcome}` ends the refusal", case.run())


def test_changed_counts_only_when_the_items_text_changed():
    case = Case()
    case.add("#user_message_outcome 1 changed")
    refusal = reason(case.run())
    check("`changed` on an unchanged item refuses and says so", refusal is not None and "is the same as when the message was copied" in refusal, refusal)
    case.document.write_text(WALK_DOCUMENT.replace("## Item 3 of 9", "## Item 3 of 12"))
    check("a new `of M` is not a change", reason(case.run()) is not None)
    case.document.write_text(WALK_DOCUMENT.replace(
        "## Item 3 of 9:", f"## Item 3 of 9 {walk_finder.APPROVAL_WALK_DEFERRED_ITEM_HEADING_NOTE_AFTER_RUNNING_COUNT}:"))
    check("a deferred note is not a change", reason(case.run()) is not None)
    case.document.write_text(WALK_DOCUMENT.replace("The page goes in the wiki.", "The  page goes\nin the wiki."))
    check("a whitespace edit is not a change", reason(case.run()) is not None)
    case.document.write_text(WALK_DOCUMENT.replace("A hook checks pages.", "A hook reads pages."))
    check("an edit to another item is not a change to this one", reason(case.run()) is not None)
    case.document.write_text(WALK_DOCUMENT.replace("in the wiki", "in the handbook"))
    check_silent("`changed` passes once the item's text changed", case.run())
    case.document.write_text(WALK_DOCUMENT.replace("## Item 3 of 9: the poem page", "## Withdrawn: the poem page"))
    check_silent("`changed` passes when the item was removed", case.run())


def test_the_newest_outcome_counts_and_an_unlisted_one_is_none():
    case = Case()
    case.add("#user_message_outcome 1 open")
    case.add("#user_message_outcome 1 changed")
    check("a newer `changed` replaces `open`, and is checked", reason(case.run()) is not None)
    case.add("#user_message_outcome 1 no change")
    check_silent("a newer `no change` replaces `changed`", case.run())
    for line in ("#user_message_outcome 1 maybe", "#user_message_outcome 2 no change", "`#user_message_outcome 1 no change`"):
        case = Case()
        case.add(line)
        check(f"{line!r} is no outcome for id 1", reason(case.run()) is not None)


def test_the_hook_is_silent_where_it_must_be():
    check_silent("silent while the agent answers a Stop hook", Case().run(stop_hook_active=True))
    check_silent("silent in an agent-session no user attends", Case().run(environment_extra={"CLAUDE_CODE_SESSION_ATTENDED": "0"}))
    case = Case()
    stop_folder = case.checkout / "emergency-stop"
    stop_folder.mkdir()
    (stop_folder / "2026-10-30T01-00-00Z.md").write_text("# Emergency stop\ncoordinating agent-seat: test\n")
    environment = {"NEDSNODES_EMERGENCY_STOP_FOLDER": str(stop_folder)}
    check_silent("silent during an emergency stop", case.run(environment_extra=environment))
    check_silent("silent once the approval-walk closed", Case("#next_to_present none, closed\n").run())
    check_silent("silent while the approval-walk is paused", Case("#approval_walk_paused the user paused it\n").run())
    case = Case()
    (case.walk / "other-minutes.md").write_text("#next_to_present item 1 of 2\n")
    check_silent("silent with two open approval-walks", case.run())


def test_a_fault_exits_1_and_names_the_hook():
    case = Case()
    result = case.run(stdin_text="not json")
    check("input that is not JSON exits 1 on stderr", result.returncode == 1 and HOOK_SCRIPT.stem in result.stderr
          and result.stdout == "", f"{result!r}")
    case = Case()
    case.add("#user_message_outcome 1 changed")
    case.document.unlink()
    result = case.run()
    check("a walk-document that cannot be read exits 1 on stderr", result.returncode == 1 and HOOK_SCRIPT.stem in result.stderr
          and result.stdout == "", f"{result!r}")


def main():
    try:
        for name, function in list(globals().items()):
            if name.startswith("test_"):
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
