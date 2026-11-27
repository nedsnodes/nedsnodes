#!/usr/bin/env python3
"""Check each new word a cold-read-fast-read's fast-clarify cold-read-cell lists against what a fresh reader
guesses it means, for nn-systems/cold-read/cold-read-fast-read.py.

The fast-clarify cell ends its report with a `## Words with a meaning of their own` section, here called its new
words: one line per word, or phrase, and meaning, that the lines the edit added or changed use in a meaning of
their own, written ``- `<word>`: <meaning>``, or the one
line `- none`. This module takes that section out of the cell's report, drops each word a glossary or the
ordinary hyphenated words list already has, and, for each other word, asks one model call what the word
means, given the word alone, and a second model call whether that guess matches the meaning the text gives.
The second call answers exactly MATCHES or DIFFERS; any other answer, a call that fails, and a line of the
section in any other form are reported as not checked, never as MATCHES.

The report section this module writes is not a finding section: its heading is not a `## Question N`
heading, so cold-read-fast-read-report-findings-parse-and-finding-outcomes-check-common.py counts none of its
entries, and the section says they take no finding outcome. A failed check never fails the read, as a failed
Question 4 cell does not.
"""
from __future__ import annotations

import concurrent.futures
import importlib.util
import itertools
import pathlib
import re
import subprocess
import sys
import threading
import time
import typing

SYSTEM_DIRECTORY = pathlib.Path(__file__).resolve().parent
REPO_ROOT = SYSTEM_DIRECTORY.parent.parent
_cell_common_spec = importlib.util.spec_from_file_location(
    "cold_read_cell_common", SYSTEM_DIRECTORY / "cold-read-cell-common.py")
cell_common = importlib.util.module_from_spec(_cell_common_spec)
_cell_common_spec.loader.exec_module(cell_common)
# The glossary and ordinary-word readers the new-shared-names lister already uses, so the two cannot disagree
# on which words a glossary has.
_new_shared_names_spec = importlib.util.spec_from_file_location(
    "new_shared_names_in_changed_files_list",
    REPO_ROOT / "scripts" / "new-shared-names-in-changed-files-list.py")
new_shared_names = importlib.util.module_from_spec(_new_shared_names_spec)
_new_shared_names_spec.loader.exec_module(new_shared_names)
_git_redirecting_removal_spec = importlib.util.spec_from_file_location(
    "git_redirecting_environment_variables_removal_common",
    REPO_ROOT / "nn-systems" / "general-tools" / "git-redirecting-environment-variables-removal-common.py")
git_redirecting_removal = importlib.util.module_from_spec(_git_redirecting_removal_spec)
_git_redirecting_removal_spec.loader.exec_module(git_redirecting_removal)

PROGRAM = "cold-read-fast-read"
NEW_WORDS_ANSWER_HEADING_TEXT = "Words with a meaning of their own"
NEW_WORDS_ANSWER_HEADING = re.compile(r"^#{1,3}\s+" + re.escape(NEW_WORDS_ANSWER_HEADING_TEXT) + r"\s*$")
ANY_HEADING = re.compile(r"^#{1,6}\s")
CODE_FENCE = re.compile(r"^\s*(`{3,}|~{3,})")
GLOSSARY_TERM_WITH_ALIASES = re.compile(r"^(.+?)\s*\(aka\s+(.+)\)$")
NEW_WORD_LINE = re.compile(r"^- `([^`]+)`: (\S.*)$")
NO_NEW_WORDS_LINE = "- none"
PROVENANCE_STAMP = re.compile(r"\A\s*<!-- provenance:.*?-->\s*", re.DOTALL)
NEW_WORD_MEANING_COMPARE_ANSWER_MATCHES = "MATCHES"
NEW_WORD_MEANING_COMPARE_ANSWER_DIFFERS = "DIFFERS"
NOT_CHECKED = "not checked"

NEW_WORDS_REPORT_SECTION_HEADING = (
    "## Words with a meaning of their own, checked against a fresh reader's guess (added by cold-read-fast-read)")
NAMING_PAGE = "docs/nedsnodes-wiki/nedsnodes-how-to-choose-a-name-for-files-code-and-glossary-terms.md"
# Both calls run on the cold-read-tier the fast-clarify cell ran on, through the launcher that wrote its report.
NEW_WORD_MODEL_CALL_COLD_READ_TIER = "fast"
NEW_WORD_MEANING_GUESS_COLD_READ_CELL_LABEL = "new-word-meaning-guess"
NEW_WORD_MEANING_COMPARE_COLD_READ_CELL_LABEL = "new-word-meaning-compare"
# One limit for every word's two calls together, so the read's own run time stays bounded however many words
# the cell lists; a word whose calls the limit cuts off is not checked. Gemini at low effort read whole
# documents in 100 to 150 s; one word is far less.
NEW_WORDS_MEANING_CHECKS_TOTAL_TIME_LIMIT_SECONDS = 10 * 60
NEW_WORDS_CHECKED_AT_ONCE = 8
NEW_WORD_MEANING_GUESS_PROMPT_TEMPLATE = (
    "{TARGET_PATH} holds one word or phrase, in backquotes, taken from instructions written for software "
    "agents. Read that file and nothing else: open, search or list no other file, and look nothing up, "
    "because the question is what a reader who meets the word alone takes it to mean. Write your report to "
    "{REPORT_PATH}, once: one sentence saying what you take the word to mean. That file is your entire "
    "deliverable: what you say in conversation is discarded. {REPORT_PATH} is the only file to create; write "
    "nothing anywhere else.\n")
NEW_WORD_MEANING_COMPARE_PROMPT_TEMPLATE = (
    "{TARGET_PATH} holds a word or phrase, the meaning a document gives it, and the meaning a reader who met "
    "the word alone guessed for it. Read that file and nothing else: open, search or list no other file. "
    "Decide whether a reader who acted on the guessed meaning would do what the document's meaning asks. "
    f"Write your report to {{REPORT_PATH}}, once: exactly one word, {NEW_WORD_MEANING_COMPARE_ANSWER_MATCHES} when the guess means the same as "
    f"the document's meaning, or {NEW_WORD_MEANING_COMPARE_ANSWER_DIFFERS} when it does not, and nothing else. That file is your entire "
    "deliverable: what you say in conversation is discarded. {REPORT_PATH} is the only file to create; write "
    "nothing anywhere else.\n")


class NewWordsAnswer(typing.NamedTuple):
    """The cell's report without its section of words with a meaning of their own, the (word, meaning) pairs that section lists, and
    each problem that kept a word of it from being read."""
    report_text_without_answer: str
    words: list
    problems: list


class NewWordCheck(typing.NamedTuple):
    word: str
    meaning: str
    verdict: str
    guess: str
    cause: str


def fast_clarify_cell_report_new_words_section_split_off_and_parse(report_text: str) -> NewWordsAnswer:
    """Take every section headed NEW_WORDS_ANSWER_HEADING_TEXT out of the fast-clarify cell's report and read its lines. A report
    about several documents may give one section per document, so every section is read."""
    kept, answer_lines, inside, sections = [], [], False, 0
    # The opening fence's delimiter while inside fenced code: only a line of the same character, at least as
    # long and with nothing after it, closes it, so a shorter or other fence quoted inside does not.
    open_fence = None
    # Lines of each section, so that a section with no line at all, not even `- none`, is caught: the
    # cell must say `- none` to say there is no such word.
    lines_in_section = []
    for line in report_text.split("\n"):
        fence = CODE_FENCE.match(line)
        if fence and open_fence is None:
            open_fence = fence.group(1)
        elif (fence and fence.group(1)[0] == open_fence[0] and len(fence.group(1)) >= len(open_fence)
              and not line.strip()[len(fence.group(1)):].strip()):
            open_fence = None
        fenced = open_fence is not None or bool(fence)
        if not fenced and NEW_WORDS_ANSWER_HEADING.match(line):
            inside, sections = True, sections + 1
            lines_in_section.append(0)
            continue
        if inside and not fenced and ANY_HEADING.match(line):
            inside = False
        if inside and line.strip():
            lines_in_section[-1] += 1
        (answer_lines if inside else kept).append(line)
    words, problems, seen = [], [], set()
    if not sections:
        problems.append(f"the fast-clarify cell's report has no `## {NEW_WORDS_ANSWER_HEADING_TEXT}` section")
    empty_sections = lines_in_section.count(0)
    if empty_sections:
        problems.append(f"{empty_sections} of the fast-clarify cell's `## {NEW_WORDS_ANSWER_HEADING_TEXT}` sections "
                        f"hold no line, not even `{NO_NEW_WORDS_LINE}`")
    for line in answer_lines:
        stripped = line.strip()
        if not stripped or stripped == NO_NEW_WORDS_LINE:
            continue
        parsed = NEW_WORD_LINE.match(stripped)
        if parsed is None:
            problems.append(f"this line of the `## {NEW_WORDS_ANSWER_HEADING_TEXT}` section is not in the form ``- `<word>`: "
                            f"<meaning>``: {stripped}")
            continue
        word, meaning = parsed.group(1).strip(), parsed.group(2).strip()
        # One line per meaning: two documents may give one word two meanings, and each is checked.
        if (word.lower(), meaning) not in seen:
            seen.add((word.lower(), meaning))
            words.append((word, meaning))
    return NewWordsAnswer("\n".join(kept), words, problems)


def known_words_in_glossaries_and_ordinary_hyphenated_words_list(checkout: pathlib.Path) -> set:
    """Every term a glossary git tracks in `checkout` lists, each alias an entry gives as `<term> (aka
    <alias>)` included, and every word of the ordinary hyphenated words list, lowercase. Raises
    new_shared_names.GitFailure when git cannot list the glossaries."""
    # Without the variables, a read started inside a git command, such as a hook, lists `checkout`'s own glossaries.
    terms = new_shared_names.every_glossary_term(
        checkout, environment=git_redirecting_removal.environment_without_git_redirecting_variables())
    known = set()
    for term in terms:
        with_aliases = GLOSSARY_TERM_WITH_ALIASES.match(term)
        if with_aliases is None:
            known.add(term)
            continue
        known.add(with_aliases.group(1).strip())
        known.update(alias.strip() for alias in re.split(r",|\bor\b", with_aliases.group(2)) if alias.strip())
    return known | new_shared_names.ordinary_hyphenated_words(checkout)


def word_is_known(word: str, known: set) -> bool:
    lowered = word.lower()
    return any(new_shared_names.listed_word_or_its_form(form, known) for form in (lowered, "/" + lowered))


def answer_without_provenance_stamp(text: str) -> str:
    return PROVENANCE_STAMP.sub("", text, count=1).strip()


class NewWordsMeaningCheckRunningModelCallProcessesTrackerWithStopAll:
    """The model-call processes the word checks have running, so that a read ended by a signal can stop them
    all and start no further call: each runs in a session of its own, which a signal to the read misses."""

    def __init__(self):
        self.lock = threading.Lock()
        self.processes = set()
        self.stopped = False

    def start(self, command: list, **popen_arguments):
        """The started process, or None once stop_all has run. Raises OSError when the process cannot start."""
        with self.lock:
            if self.stopped:
                return None
            process = subprocess.Popen(command, start_new_session=True, **popen_arguments)
            self.processes.add(process)
            return process

    def finished(self, process) -> None:
        with self.lock:
            self.processes.discard(process)

    def stop_all(self) -> None:
        with self.lock:
            self.stopped = True
            running = list(self.processes)
        for process in running:
            cell_common.stop_process_tree(process)


def model_call_process_run_until_deadline(calls: NewWordsMeaningCheckRunningModelCallProcessesTrackerWithStopAll, command: list, *, what: str,
                                          cwd: pathlib.Path, stdin_text, deadline: float) -> tuple:
    """Run one model-call process to its end or to `deadline`. Returns (exit status, stdout, stderr), or
    (None, the cause the call gave no answer, "")."""
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        return None, "the time limit for checking new words ran out before this call started", ""
    try:
        process = calls.start(command, stdin=subprocess.DEVNULL if stdin_text is None else subprocess.PIPE,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=cwd, text=True)
    except OSError as error:
        return None, f"the {what} could not start: {error}", ""
    if process is None:
        return None, "the read was ended before this call started", ""
    try:
        try:
            output, errors = process.communicate(input=stdin_text, timeout=remaining)
        except subprocess.TimeoutExpired:
            cell_common.stop_process_tree(process)
            process.communicate()
            return None, (f"stopped at the time limit for checking new words, "
                          f"{NEW_WORDS_MEANING_CHECKS_TOTAL_TIME_LIMIT_SECONDS / 60:g} minutes"), ""
    finally:
        calls.finished(process)
    if calls.stopped:
        return None, "the read was ended while this call ran", ""
    return process.returncode, output or "", errors or ""


def cold_read_cell_launcher_call_with_one_prompt_on_fast_tier_returning_answer_or_failure_cause(launcher: pathlib.Path, cell_label: str, prompt_template: str,
                                       question_text: str, work_directory: pathlib.Path,
                                       deadline: float, calls: NewWordsMeaningCheckRunningModelCallProcessesTrackerWithStopAll = None) -> tuple:
    """One model call through a cold-read-cell launcher on the fast cold-read-tier: `question_text` is the
    target, `prompt_template` the prompt. Returns (the answer without its provenance stamp, "") or (None, the
    cause of the failure). The launcher runs in a process group of its own, stopped at `deadline`."""
    calls = calls or NewWordsMeaningCheckRunningModelCallProcessesTrackerWithStopAll()
    # One directory below the work directory, so the launcher's misplaced-report recovery, which searches
    # the report's grandparent, sees no other call's report.
    report = work_directory / "answer" / f"{cell_label}-answer.md"
    try:
        work_directory.mkdir(parents=True)
        target = work_directory / f"{cell_label}-question.md"
        target.write_text(question_text, encoding="utf-8")
        prompt_file = work_directory / f"{cell_label}-prompt.md"
        prompt_file.write_text(prompt_template, encoding="utf-8")
    except OSError as error:
        return None, f"the {cell_label} call's files could not be written: {error}"
    command = [sys.executable, str(launcher), "--cell", cell_label, "--tier", NEW_WORD_MODEL_CALL_COLD_READ_TIER,
               "--target", str(target), "--report", str(report), "--prompt-file", str(prompt_file)]
    returncode, output, errors = model_call_process_run_until_deadline(
        calls, command, what=f"{cell_label} call through {launcher.name}", cwd=REPO_ROOT, stdin_text=None,
        deadline=deadline)
    if returncode is None:
        return None, output
    output += errors
    # A launcher that exits 0 can still have warned, such as of a stray write, so its output always reaches stderr.
    if output:
        print(output, file=sys.stderr, end="" if output.endswith("\n") else "\n")
    if returncode != 0:
        lines = [line.strip() for line in output.splitlines() if line.strip()]
        causes = [line for line in lines if cell_common.CAUSE_PHRASE in line]
        detail = causes[-1] if causes else (lines[-1] if lines else "no output")
        return None, f"the {cell_label} call through {launcher.name} exited {returncode}: {detail}"
    try:
        return answer_without_provenance_stamp(report.read_text(encoding="utf-8")), ""
    except OSError as error:
        return None, f"the {cell_label} call's answer could not be read: {error}"


class NewWordsMeaningCheckColdReadCellLauncherCallsWithOneSharedDeadline:
    """The `ask` new_word_fresh_reader_meaning_guess_and_compare_with_text_meaning takes: each call through
    `launcher` in a directory of its own under `scratch_directory`, every call stopped at one `deadline`,
    NEW_WORDS_MEANING_CHECKS_TOTAL_TIME_LIMIT_SECONDS from now when None, and stop_all to stop them all."""

    def __init__(self, launcher: pathlib.Path, scratch_directory: pathlib.Path, deadline: float = None):
        self.launcher = launcher
        self.scratch_directory = scratch_directory
        self.deadline = (time.monotonic() + NEW_WORDS_MEANING_CHECKS_TOTAL_TIME_LIMIT_SECONDS
                         if deadline is None else deadline)
        self.calls = NewWordsMeaningCheckRunningModelCallProcessesTrackerWithStopAll()
        self.call_numbers = itertools.count(1)

    def __call__(self, cell_label, prompt_template, question_text):
        return cold_read_cell_launcher_call_with_one_prompt_on_fast_tier_returning_answer_or_failure_cause(
            self.launcher, cell_label, prompt_template, question_text,
            self.scratch_directory / "new-word-checks" / f"call-{next(self.call_numbers)}", self.deadline,
            self.calls)

    def stop_all(self) -> None:
        self.calls.stop_all()


def new_word_fresh_reader_meaning_guess_and_compare_with_text_meaning(word: str, meaning: str, ask) -> NewWordCheck:
    """Ask for a guess at the word's meaning, given the word alone, then whether the guess matches `meaning`.
    `ask(cell_label, prompt_template, question_text)` makes one model call and returns (answer or None,
    cause)."""
    guess, cause = ask(NEW_WORD_MEANING_GUESS_COLD_READ_CELL_LABEL, NEW_WORD_MEANING_GUESS_PROMPT_TEMPLATE,
                       f"`{word}`\n")
    if guess is None:
        return NewWordCheck(word, meaning, NOT_CHECKED, "", cause)
    if not guess:
        return NewWordCheck(word, meaning, NOT_CHECKED, "", "the guess call wrote an empty answer")
    verdict, cause = ask(NEW_WORD_MEANING_COMPARE_COLD_READ_CELL_LABEL, NEW_WORD_MEANING_COMPARE_PROMPT_TEMPLATE,
                         f"Word: `{word}`\n\nMeaning the document gives it: {meaning}\n\n"
                         f"Meaning a reader who met the word alone guessed: {guess}\n")
    if verdict is None:
        return NewWordCheck(word, meaning, NOT_CHECKED, guess, cause)
    if verdict not in (NEW_WORD_MEANING_COMPARE_ANSWER_MATCHES, NEW_WORD_MEANING_COMPARE_ANSWER_DIFFERS):
        return NewWordCheck(word, meaning, NOT_CHECKED, guess,
                            f"the compare call answered {verdict[:200]!r}, which is neither {NEW_WORD_MEANING_COMPARE_ANSWER_MATCHES} nor {NEW_WORD_MEANING_COMPARE_ANSWER_DIFFERS}")
    return NewWordCheck(word, meaning, verdict, guess, "")


def one_line(text: str) -> str:
    """`text` with its line breaks and runs of spaces made single spaces, so that a model's answer quoted in the
    report cannot start a heading or list of its own that the findings parser would count."""
    return " ".join(text.split())


def new_words_fresh_reader_meaning_checks_run_into_report_section_and_stderr_lines(answer: NewWordsAnswer, *, whole_document: bool, ask,
                                              known_words=None, edit_added_or_changed_no_sentence: bool = False,
                                              stop_model_calls=None) -> tuple:
    """Check every word `answer` lists and return (the report section, the lines for stderr). `known_words`
    returns the set word_is_known looks words up in; `ask` is as new_word_fresh_reader_meaning_guess_and_compare_with_text_meaning takes it.
    When `edit_added_or_changed_no_sentence`, the edit only removed text, so no word is checked. When the checks
    are ended by an exception, such as the SystemExit a signal raises, `stop_model_calls` stops every model
    call still running, and no further call starts."""
    problems = list(answer.problems)
    to_check = [] if edit_added_or_changed_no_sentence else list(answer.words)
    dropped_pairs = []
    if to_check:
        try:
            known = (known_words or (lambda: known_words_in_glossaries_and_ordinary_hyphenated_words_list(REPO_ROOT)))()
        except new_shared_names.GitFailure as error:
            problems.append(f"the glossaries could not be listed, so no word was dropped as one a glossary "
                            f"has: {error}")
            known = set()
        dropped_pairs = [(word, meaning) for word, meaning in to_check if word_is_known(word, known)]
        to_check = [(word, meaning) for word, meaning in to_check if not word_is_known(word, known)]
    dropped = list(dict.fromkeys(word for word, _ in dropped_pairs))
    checks = []
    if to_check:
        pool = concurrent.futures.ThreadPoolExecutor(max_workers=min(len(to_check), NEW_WORDS_CHECKED_AT_ONCE))
        try:
            checks = list(pool.map(lambda pair: new_word_fresh_reader_meaning_guess_and_compare_with_text_meaning(pair[0], pair[1], ask), to_check))
        except BaseException:
            # Before the pool waits for its workers: their calls run in sessions of their own, which a signal to
            # the read does not reach, and would run on to the deadline.
            if stop_model_calls is not None:
                stop_model_calls()
            pool.shutdown(wait=True, cancel_futures=True)
            raise
        pool.shutdown()
    differs = [check for check in checks if check.verdict == NEW_WORD_MEANING_COMPARE_ANSWER_DIFFERS]
    matches = [check for check in checks if check.verdict == NEW_WORD_MEANING_COMPARE_ANSWER_MATCHES]
    not_checked = [check for check in checks if check.verdict == NOT_CHECKED]
    lines = ["", NEW_WORDS_REPORT_SECTION_HEADING, "",
             f"The fast-clarify cell listed the words that "
             f"{'the document' if whole_document else 'the sentences the edit added or changed'} use in a "
             f"meaning of their own. For each word that neither a glossary nor the ordinary hyphenated words "
             f"list has, one model given only the word guessed its meaning, and a second compared that guess with "
             f"the meaning the text gives. The entries below are not findings and take no finding outcome.", ""]
    if edit_added_or_changed_no_sentence:
        lines += ["The edit removed or replaced text and added or changed no sentence, so no word was checked.", ""]
    elif not answer.words and not problems:
        lines += ["The fast-clarify cell listed no such word.", ""]
    if differs:
        lines += ["A fresh reader takes these words another way. Rewrite each in plain words, dismiss it as "
                  "plain English, or propose it as a project-term:", ""]
        lines += [f"- `{check.word}`: the text means: {check.meaning} Given the word alone, a model took it to "
                  f"mean: {one_line(check.guess)}" for check in differs]
        lines.append("")
    if not_checked or problems:
        lines += [f"Not checked. Ask a fresh subagent what each word means, given the word alone, as "
                  f"`{NAMING_PAGE}` says, and compare its answer with the meaning the text gives:", ""]
        lines += [f"- `{check.word}`: {one_line(check.cause)}." for check in not_checked]
        lines += [f"- {one_line(problem)}." for problem in problems]
        lines.append("")
    if matches:
        lines += ["A fresh reader takes these words as the text means them: "
                  + ", ".join(f"`{check.word}`" for check in matches) + ".", ""]
    if dropped:
        lines += ["A glossary or the ordinary hyphenated words list already has these words: "
                  + ", ".join(f"`{word}`" for word in dropped) + ".", ""]
    unchecked_because_no_sentence = len(answer.words) if edit_added_or_changed_no_sentence else 0
    stderr_lines = [
        f"{PROGRAM}: words with a meaning of their own: {len(answer.words)} listed, {len(dropped_pairs)} already in a glossary, "
        f"{len(matches)} read as the text means, {len(differs)} read another way, "
        f"{len(not_checked) + len(problems) + unchecked_because_no_sentence} not checked; the report's section "
        f"`{NEW_WORDS_REPORT_SECTION_HEADING}` lists each."]
    stderr_lines += [f"{PROGRAM}: word with a meaning of its own `{check.word}` not checked: {check.cause}." for check in not_checked]
    stderr_lines += [f"{PROGRAM}: words with a meaning of their own not checked: {problem}." for problem in problems]
    return "\n".join(lines), stderr_lines
