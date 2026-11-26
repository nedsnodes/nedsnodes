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
               / "walk-me-through-user-message-copied-to-walk-minutes-without-valid-outcome-turn-end-refusal-stop-hook.py")
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


def test_the_refusal_gives_each_case_its_own_instruction():
    refusal = reason(Case().run())
    for instruction in (
            "If you and the user agreed a change to the text of the item its entry names, and the walk-document ",
            "did not hold the change when the message was copied, write the change there unless you already have, then "
            "run the printf command labelled `changed`.",
            "If the walk-document already held that change when the message was copied, as when the user repeats or "
            "confirms a change, run the printf command labelled `no change`, because `changed` is valid only when the "
            "item's text differs from its text at the copy.",
            "If you and the user agreed a change to the text of another item, write that change into that other item "
            "in the walk-document, unless the walk-document already holds the change.",
            "If the message needs no change to the text of the item its entry names, as when the message is about "
            "another item or unrelated to the approval-walk, run the printf command labelled `no change`.",
            "An outcome line records no answer and decides no item.",
            "and run the printf command for each id whose outcome you know. Then run the skill: this hook refuses your "
            "successor until each id left without an outcome has one."):
        check(f"the refusal gives the line {instruction!r}", refusal is not None and instruction in refusal, refusal)


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


def test_a_change_the_walk_document_held_before_the_copy_is_recorded_as_no_change():
    case = Case()
    case.add("#user_message_outcome 1 changed")
    refusal = reason(case.run())
    check("the entry for an invalid `changed` says a change held before the copy takes `no change`",
          refusal is not None and "if the walk-document already held the agreed change when the message was copied, run "
          "the printf command labelled `no change`" in refusal, refusal)
    command = next(line.split(": ", 1)[1] for line in refusal.split("\n") if line.startswith("  no change: printf"))
    subprocess.run(["bash", "-c", command], check=True)
    check_silent("the printed `no change` command ends the refusal with the item's text unchanged", case.run())


CHECK_PROGRAM_FILE = WALK_SKILL_DIRECTORY / "walk-me-through-answer-added-texts-cold-read-fast-read-check-and-close.py"
ANSWER_HOOK_FILE = (WALK_SKILL_DIRECTORY
                    / "walk-me-through-user-short-answer-to-approval-walk-item-expanded-into-instructions-user-prompt-submit-hook.py")
ANSWER_RECORDED = "walk-minutes already record a decision on the item"
ANSWER_NOT_RECORDED = "walk-minutes record no decision on the item"


def case_with_rider_answer(closed):
    case = Case()
    text = case.minutes.read_text().replace("please reword the page", "A, but reword the title")
    if closed:
        check_program = load("walk_check_program_for_stop_hook_test", CHECK_PROGRAM_FILE)
        closed_line = check_program.CLOSE_TOOK_EFFECT_MINUTES.format(
            item="item 3 of 9", answered="approved", outcome=check_program.OUTCOMES[check_program.APPROVED])
        text = f"{text}{closed_line}\n#next_to_present item 4 of 9\n"
    case.minutes.write_text(text)
    return case


def test_an_outcome_for_an_answer_already_closed_leaves_the_next_item_undecided():
    case = case_with_rider_answer(closed=True)
    check_program = load("walk_check_program_for_stop_hook_test", CHECK_PROGRAM_FILE)
    parser = walk_finder.markdown_parser()
    decided_before, _ = check_program.minutes_record(walk_finder, case.minutes.read_text(), parser)
    refusal = reason(case.run())
    entry = next((line for line in (refusal or "").split("\n") if line.startswith("- id 1,")), "")
    check("the entry for an answer already closed says the walk-minutes record its decision", ANSWER_RECORDED in entry, refusal)
    check("the refusal tells an agent with no earlier instructions not to rerun `check` for a recorded answer",
          refusal is not None and "do not run `check` for that answer" in refusal
          and "carry out what he added unless that is already done" in refusal, refusal)
    check("the refusal no longer relies on instructions a successor never saw",
          refusal is not None and "still govern" not in refusal, refusal)
    command = next(line.split(": ", 1)[1] for line in refusal.split("\n") if line.startswith("  no change: printf"))
    subprocess.run(["bash", "-c", command], check=True)
    text = case.minutes.read_text()
    decided_after, _ = check_program.minutes_record(walk_finder, text, parser)
    check("the outcome line leaves the approval-walk waiting at the next item",
          walk_finder.next_to_present(text, parser) == ("item 4 of 9", False, False), text)
    check("the outcome line decides no item", "3" in decided_before and decided_after == decided_before and "4" not in decided_after,
          f"{decided_before} {decided_after}")
    check_silent("the hook is silent after the outcome line", case.run())


def test_a_rider_answer_with_no_recorded_decision_is_not_left_unapplied_by_a_successor():
    refusal = reason(case_with_rider_answer(closed=False).run(session_id="successor-session"))
    entry = next((line for line in (refusal or "").split("\n") if line.startswith("- id 1,")), "")
    check("the entry for an answer with no decision says the walk-minutes record none", ANSWER_NOT_RECORDED in entry, refusal)
    words_the_answer_hook_writes = "The user answered \""
    check("the answer hook's message still holds the words the refusal tells the agent to look for",
          words_the_answer_hook_writes in load("walk_answer_hook_for_stop_hook_test", ANSWER_HOOK_FILE).OPEN_WALK_OPENING_LINE)
    for instruction in (f"holds a hook message saying `{words_the_answer_hook_writes}` and those words, follow that message",
                        "holds no such message, as after a session-handoff, run the printf command labelled `open`, "
                        "show the user the item as the walk-document now has it, quote his words, and ask him to answer "
                        "again"):
        check(f"the refusal gives the line {instruction!r}", refusal is not None and instruction in refusal, refusal)


def test_a_copied_line_whose_running_count_runs_backwards_still_refuses():
    for words, note in (("A, but reword", "the walk-minutes record no decision on the item"), ("please reword", None)):
        case = Case()
        parser = walk_finder.markdown_parser()
        line = walk_finder.approval_walk_minutes_user_message_copied_line_build(
            "", "items 5 to 3 of 9", case.document, words, datetime(2026, 11, 23, 17, 38, tzinfo=timezone.utc), parser)
        case.minutes.write_text(f"# Minutes\n\n#next_to_present items 5 to 3 of 9\n{line}\n")
        result = case.run()
        refusal = reason(result)
        check(f"{words!r} under a backward range refuses the turn's end",
              refusal is not None and "id 1, items 5 to 3 of 9" in refusal
              and (note is None or note in refusal.split("\n")[1]), f"{result!r}")


def test_a_message_that_is_no_answer_gets_no_answer_note():
    refusal = reason(Case().run())
    entry = next((line for line in (refusal or "").split("\n") if line.startswith("- id 1,")), "")
    check("an entry for a message that is no answer says nothing about a decision",
          entry != "" and ANSWER_RECORDED not in entry and ANSWER_NOT_RECORDED not in entry, entry)


def test_a_copied_bare_answer_needs_no_outcome():
    def bare_answer_line(case):
        return walk_finder.approval_walk_minutes_user_message_copied_line_build(
            case.minutes.read_text(), "item 3 of 9", case.document, "a", datetime(2026, 11, 23, 17, 39, tzinfo=timezone.utc),
            walk_finder.markdown_parser(), needs_no_outcome=True)

    case = Case()
    case.add("#user_message_outcome 1 no change")
    case.add(bare_answer_line(case))
    check_silent("a copied bare answer does not refuse the turn's end", case.run())
    case = Case()
    case.add(bare_answer_line(case))
    refusal = reason(case.run())
    check("a line needing an outcome still refuses beside a copied bare answer, and only its id is listed",
          refusal is not None and "hold 1 copied user message(s)" in refusal and "id 1," in refusal, refusal)


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
