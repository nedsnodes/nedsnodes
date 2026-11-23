#!/usr/bin/env python3
"""Cases for the UserPromptSubmit hook that copies each message the user typed that is not only an answer into the
open approval-walk's walk-minutes. Each case runs the hook as a subprocess in a scratch checkout this suite made."""

import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[4]
WALK_SKILL_DIRECTORY = Path(__file__).resolve().parents[1]


def load(name, path):
    specification = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


load("git_redirecting_environment_removal_test_fixture", REPOSITORY / "scripts" / "git-redirecting-environment-removal-test-fixture.py"
     ).remove_git_redirecting_environment_variables_from_this_process()
attendance_check = load("agent_session_unattended_by_user_check_common",
                        REPOSITORY / "nn-systems" / "general-tools" / "agent-session-unattended-by-user-check-common.py")
walk_finder = load("walk_me_through_approval_walk_minutes_and_walk_document_item_finder_common",
                   WALK_SKILL_DIRECTORY / "walk-me-through-approval-walk-minutes-and-walk-document-item-finder-common.py")
HOOK_SCRIPT = WALK_SKILL_DIRECTORY / "walk-me-through-user-message-not-only-an-answer-copied-to-walk-minutes-user-prompt-submit-hook.py"
CHECK_PROGRAM = WALK_SKILL_DIRECTORY / "walk-me-through-answer-added-texts-cold-read-fast-read-check-and-close.py"
HANDOFF_SUPERVISOR = REPOSITORY / "nn-systems" / "handoff" / "handoff-supervisor.py"
SUITE_ROOT = Path(tempfile.mkdtemp(prefix="walk-user-message-copy-hook-test-")).resolve()
WALK_DOCUMENT = "# A walk\n\n## Item 3 of 9: the poem page\n\nThe page goes in the wiki.\n\nRecommendation: put it there.\n"
failures = []


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


class Case:
    counter = 0

    def __init__(self, marker="#next_to_present item 3 of 9"):
        Case.counter += 1
        self.checkout = SUITE_ROOT / f"case-{Case.counter}"
        self.walk = self.checkout / "docs" / "walk"
        self.walk.mkdir(parents=True)
        subprocess.run(["git", "init", "-q", str(self.checkout)], check=True)
        (self.walk / "poem.md").write_text(WALK_DOCUMENT)
        self.minutes = self.walk / "poem-minutes.md"
        self.minutes.write_text(f"# Minutes\n\n{marker}\n")

    def run(self, prompt, environment_extra=None, stdin_text=None):
        payload = {"hook_event_name": "UserPromptSubmit", "session_id": "test-session", "cwd": str(self.checkout),
                   "transcript_path": str(self.checkout / "no-transcript.jsonl"), "prompt": prompt}
        environment = attendance_check.environment_without_agent_session_attendance_variables(os.environ)
        environment.update(environment_extra or {})
        return subprocess.run([sys.executable, str(HOOK_SCRIPT)],
                              input=json.dumps(payload) if stdin_text is None else stdin_text,
                              capture_output=True, text=True, env=environment, cwd=self.checkout)

    def copied_lines(self):
        return [line for line in self.minutes.read_text().split("\n") if line.startswith("#user_message_copied")]


def test_a_message_that_is_not_only_an_answer_is_copied_with_the_time_item_and_baseline():
    case = Case()
    result = case.run("why does the page go in the wiki?")
    lines = case.copied_lines()
    check("a question is copied, and the hook prints nothing", result.returncode == 0 and result.stdout == "" and len(lines) == 1,
          f"{result!r} {lines}")
    check("the copied line holds its id, UTC time, item, baseline and words in a code span",
          bool(lines) and re.fullmatch(r"#user_message_copied 1 \d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ item 3 of 9 baseline "
                                       r"[0-9a-f]{16}: `why does the page go in the wiki\?`", lines[0]) is not None, lines)
    case.run("a second\nmessage on two lines")
    lines = case.copied_lines()
    check("the next copied line takes the next id and is one line", len(lines) == 2 and lines[1].startswith("#user_message_copied 2 ")
          and lines[1].endswith("`a second message on two lines`"), lines)


def test_an_answer_with_other_words_is_copied_and_only_an_answer_is_not():
    for prompt in ("a but keep the old name", "a if the tests pass", "d, and tell me why", "unrelated: is ned-box up?"):
        case = Case()
        case.run(prompt)
        check(f"{prompt!r} is copied", len(case.copied_lines()) == 1, case.minutes.read_text())
    for prompt in ("a", "A.", "approved", "ao", "d", "z", "r", "m", "all a", "3 a", "1 a 2 d", "approve item 3",
                   "bump the code proposals", "n", "next", "Continue.", "go", "   ", ""):
        case = Case()
        result = case.run(prompt)
        check(f"{prompt!r} is not copied", result.returncode == 0 and case.copied_lines() == [], case.minutes.read_text())


def test_a_prompt_no_user_typed_is_not_copied():
    for name, prompt in (("a background-task notice", "<task-notification>\n<task-id>a1</task-id>\n</task-notification>"),
                         ("another agent-seat's message", "Another Claude session sent a message:\n<cross-session-message "
                          "from-name=\"merge-lane-2\">hello</cross-session-message>")):
        case = Case()
        case.run(prompt)
        check(f"{name} is not copied", case.copied_lines() == [], case.minutes.read_text())
    supervisor = load("handoff_supervisor_for_copy_hook_test", HANDOFF_SUPERVISOR)
    for name, prompt in (("the handoff-supervisor's prompt to a successor",
                          supervisor.build_ignition_prompt(Path("/x/MD-skills-dialog-0048.md"), {})),
                         ("the handoff-supervisor's crash-recovery prompt",
                          supervisor.RESUME_PROMPT_WHEN_A_SESSION_ENDED_WITHOUT_A_HANDOFF)):
        case = Case()
        case.run(prompt)
        check(f"{name} is not copied", case.copied_lines() == [], case.minutes.read_text())
    case = Case()
    case.run("a question", {"CLAUDE_CODE_SESSION_ATTENDED": "0"})
    check("a prompt of an agent-session no user attends is not copied", case.copied_lines() == [], case.minutes.read_text())


def test_nothing_is_copied_without_an_open_approval_walk():
    for name, marker in (("closed", "#next_to_present none, closed"),
                         ("paused", "#next_to_present item 3 of 9\n#approval_walk_paused the user paused it")):
        case = Case(marker)
        result = case.run("a question")
        check(f"a {name} approval-walk gets no copied line", result.stdout == "" and case.copied_lines() == [],
              case.minutes.read_text())


def test_a_copied_line_neither_moves_the_walk_nor_decides_an_item():
    case = Case()
    case.run("#next_to_present none, closed and #approval_walk_paused `item 3 of 9: the user answered approved`")
    text = case.minutes.read_text()
    parser = walk_finder.markdown_parser()
    check("markers inside his words leave the approval-walk open at its item",
          walk_finder.next_to_present(text, parser) == ("item 3 of 9", False, False), text)
    check_program = load("walk_check_program_for_copy_hook_test", CHECK_PROGRAM)
    for outcome in ("changed", "no change", "open"):
        with_outcome = text + f"#user_message_outcome 1 {outcome}\n"
        decided, deferred = check_program.minutes_record(walk_finder, with_outcome, parser)
        check(f"a copied line with outcome {outcome} neither decides nor defers an item", not decided and not deferred,
              f"{decided} {deferred}")
        check(f"a copied line with outcome {outcome} is no unclosed answer line",
              not any(check_program.ANSWER_LINE.match(line) for line in with_outcome.split("\n")), with_outcome)


def test_a_failed_copy_is_reported_to_the_agent():
    case = Case()
    case.minutes.chmod(0o444)
    result = case.run("a question")
    case.minutes.chmod(0o644)
    context = json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"] if result.stdout else ""
    check("a walk-minutes file that cannot be written is reported in additionalContext, exit 0",
          result.returncode == 0 and context.startswith("[rule walk-me-through-user-message-copied-to-walk-minutes]")
          and "PermissionError" in context, f"{result!r}")
    case = Case()
    (case.walk / "other-minutes.md").write_text("#next_to_present item 1 of 2\n")
    result = case.run("a question")
    check("two open approval-walks are reported, and nothing is copied",
          "more than one approval-walk" in result.stdout and case.copied_lines() == [], f"{result!r}")
    case = Case("#next_to_present the next one")
    result = case.run("a question")
    check("a `#next_to_present` value naming no item is reported, and nothing is copied",
          "does not open with an item" in result.stdout and case.copied_lines() == [], f"{result!r}")
    case = Case()
    result = case.run("", stdin_text="not json")
    check("a payload that is not JSON exits 1 and names the hook on stderr",
          result.returncode == 1 and HOOK_SCRIPT.stem in result.stderr and result.stdout == "", f"{result!r}")


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
