#!/usr/bin/env python3
"""Tests for cold-read-fast-read-new-words-fresh-reader-meaning-check.py.

The model calls are stubbed: new_word_fresh_reader_meaning_guess_and_compare_with_text_meaning and the section builder take the call as a function, and
the launcher call is run against a stub launcher script, so no case reaches a model.

Run: python3 nn-systems/cold-read/tests/cold-read-fast-read-new-words-fresh-reader-meaning-check-test.py
"""
import importlib.util
import pathlib
import sys
import tempfile
import time

SYSTEM_DIRECTORY = pathlib.Path(__file__).resolve().parent.parent


def load(name, file_name):
    spec = importlib.util.spec_from_file_location(name, SYSTEM_DIRECTORY / file_name)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


new_words = load("new_words_under_test", "cold-read-fast-read-new-words-fresh-reader-meaning-check.py")
findings_common = load("findings_common",
                       "cold-read-fast-read-report-findings-parse-and-finding-outcomes-check-common.py")

failures = []


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


# --- Reading the cell's section of words with a meaning of their own --------------------------------------------------------------------
report = ("## Question 1: What it says\n\n[s1]\n- a point\n\n## Question 3: What it does not cover\n\nNo issues\n\n"
          "## Words with a meaning of their own\n\n- `rider`: the words typed after the answer letter\n- `Rider`: a repeat\n\n"
          "- `fresh read`: a read by a new agent\n- `rider`: the words typed after the answer letter\n")
answer = new_words.fast_clarify_cell_report_new_words_section_split_off_and_parse(report)
check("each word line is read as (word, meaning); a word given a second meaning keeps both lines, and a repeated "
      "line is dropped",
      answer.words == [("rider", "the words typed after the answer letter"), ("Rider", "a repeat"),
                       ("fresh read", "a read by a new agent")] and answer.problems == [], repr(answer))
check("the section is taken out of the report, and the rest is kept",
      "## Words with a meaning of their own" not in answer.report_text_without_answer and "`rider`" not in answer.report_text_without_answer
      and "## Question 3: What it does not cover\n\nNo issues" in answer.report_text_without_answer,
      repr(answer.report_text_without_answer))
answer = new_words.fast_clarify_cell_report_new_words_section_split_off_and_parse("## Question 1: x\n\n## Words with a meaning of their own\n\n- none\n")
check("`- none` lists no word and is no problem", answer.words == [] and answer.problems == [], repr(answer))
answer = new_words.fast_clarify_cell_report_new_words_section_split_off_and_parse("## Question 1: x\n\n## Words with a meaning of their own\n\n")
check("a section that holds no line, not even `- none`, is a problem, not a section that lists no word",
      answer.words == [] and len(answer.problems) == 1 and "hold no line" in answer.problems[0], repr(answer))
empty_section, empty_stderr = new_words.new_words_fresh_reader_meaning_checks_run_into_report_section_and_stderr_lines(
    answer, whole_document=True, ask=lambda *_: (None, "unused"), known_words=lambda: set())
check("an empty section is reported as not checked, never as listing no such word",
      "listed no such word" not in empty_section and "Not checked" in empty_section
      and "1 not checked" in empty_stderr[0], repr((empty_section, empty_stderr)))
answer = new_words.fast_clarify_cell_report_new_words_section_split_off_and_parse(
    "## Words with a meaning of their own\n\n- `alpha`: one\n\n# Second document\n\n## Words with a meaning of their own\n\n")
check("when one of several sections is empty, its words are still read and the empty one is a problem",
      answer.words == [("alpha", "one")] and len(answer.problems) == 1 and answer.problems[0].startswith("1 of"),
      repr(answer))
answer = new_words.fast_clarify_cell_report_new_words_section_split_off_and_parse(
    "## Words with a meaning of their own\n\n- `rider`: a meaning\n\n## Question 9: after\n\n1. kept\n")
check("a heading after the section ends it",
      answer.words == [("rider", "a meaning")] and "1. kept" in answer.report_text_without_answer, repr(answer))
answer = new_words.fast_clarify_cell_report_new_words_section_split_off_and_parse(
    "### Words with a meaning of their own\n\n- `alpha`: one\n\n# Second document\n\n### Words with a meaning of their own\n\n- `beta`: two\n")
check("a report about several documents gives every section's words",
      [word for word, _ in answer.words] == ["alpha", "beta"], repr(answer))
answer = new_words.fast_clarify_cell_report_new_words_section_split_off_and_parse("## Question 1: x\n\n```\n## Words with a meaning of their own\n```\n")
check("a report with no such section outside fenced code is a problem, not a list of no words",
      answer.words == [] and answer.problems == ["the fast-clarify cell's report has no `## Words with a meaning of their own` section"],
      repr(answer))
answer = new_words.fast_clarify_cell_report_new_words_section_split_off_and_parse("## Words with a meaning of their own\n\n1. rider - a meaning\n- `ok`: fine\n")
check("a line in another form is a problem quoting it, and the readable lines are still read",
      answer.words == [("ok", "fine")] and len(answer.problems) == 1 and "1. rider - a meaning" in answer.problems[0],
      repr(answer))


# --- One word's check, with the calls stubbed ----------------------------------------------------------------
def scripted_ask(*answers):
    calls = []
    queue = list(answers)

    def ask(cell_label, prompt_template, question_text):
        calls.append((cell_label, question_text))
        return queue.pop(0)
    return ask, calls


ask, calls = scripted_ask(("a person on a horse", ""), ("DIFFERS", ""))
result = new_words.new_word_fresh_reader_meaning_guess_and_compare_with_text_meaning("rider", "the words after the letter", ask)
check("DIFFERS is the verdict when the compare call answers DIFFERS, and the guess is kept",
      result.verdict == new_words.NEW_WORD_MEANING_COMPARE_ANSWER_DIFFERS and result.guess == "a person on a horse", repr(result))
check("the guess call is given the word alone, and the compare call the word, both meanings",
      calls[0] == (new_words.NEW_WORD_MEANING_GUESS_COLD_READ_CELL_LABEL, "`rider`\n")
      and calls[1][0] == new_words.NEW_WORD_MEANING_COMPARE_COLD_READ_CELL_LABEL
      and "the words after the letter" in calls[1][1] and "a person on a horse" in calls[1][1], repr(calls))
ask, _ = scripted_ask(("the words after the letter", ""), ("MATCHES", ""))
check("MATCHES is the verdict when the compare call answers MATCHES",
      new_words.new_word_fresh_reader_meaning_guess_and_compare_with_text_meaning("rider", "the words after the letter", ask).verdict == new_words.NEW_WORD_MEANING_COMPARE_ANSWER_MATCHES)
ask, _ = scripted_ask(("a guess", ""), ("Matches, mostly.", ""))
result = new_words.new_word_fresh_reader_meaning_guess_and_compare_with_text_meaning("rider", "m", ask)
check("any compare answer other than exactly MATCHES or DIFFERS leaves the word not checked, naming the answer",
      result.verdict == new_words.NOT_CHECKED and "'Matches, mostly.'" in result.cause, repr(result))
ask, calls = scripted_ask((None, "the call exited 1: cause: model-limit"))
result = new_words.new_word_fresh_reader_meaning_guess_and_compare_with_text_meaning("rider", "m", ask)
check("a failed guess call leaves the word not checked with its cause, and no compare call is made",
      result.verdict == new_words.NOT_CHECKED and "model-limit" in result.cause and len(calls) == 1, repr(result))
ask, _ = scripted_ask(("", ""))
check("an empty guess leaves the word not checked",
      new_words.new_word_fresh_reader_meaning_guess_and_compare_with_text_meaning("rider", "m", ask).verdict == new_words.NOT_CHECKED)
ask, _ = scripted_ask(("a guess", ""), (None, "stopped at the time limit"))
result = new_words.new_word_fresh_reader_meaning_guess_and_compare_with_text_meaning("rider", "m", ask)
check("a failed compare call leaves the word not checked with its cause",
      result.verdict == new_words.NOT_CHECKED and result.cause == "stopped at the time limit", repr(result))


# --- The report section --------------------------------------------------------------------------------------
def ask_by_word(table):
    def ask(cell_label, prompt_template, question_text):
        word = question_text.split("`")[1]
        guess, verdict = table[word]
        if cell_label == new_words.NEW_WORD_MEANING_GUESS_COLD_READ_CELL_LABEL:
            return guess
        return verdict
    return ask


answer = new_words.fast_clarify_cell_report_new_words_section_split_off_and_parse(
    "## Words with a meaning of their own\n\n- `rider`: words after the letter\n- `nudge`: a reminder\n- `flaky`: fails at random\n"
    "- `agent-seats`: named agents\n- `/cold-read`: the skill\n- `bad line\n")
section, stderr_lines = new_words.new_words_fresh_reader_meaning_checks_run_into_report_section_and_stderr_lines(
    answer, whole_document=False,
    ask=ask_by_word({"rider": (("a horse rider", ""), ("DIFFERS", "")),
                     "nudge": (("a reminder", ""), ("MATCHES", "")),
                     "flaky": (("unreliable", ""), ("maybe", ""))}),
    known_words=lambda: {"agent-seat", "/cold-read"})
check("each listed word gets one fate in the section: another way, not checked, as the text means, or dropped",
      "- `rider`: the text means: words after the letter Given the word alone, a model took it to mean: "
      "a horse rider" in section
      and "- `flaky`: the compare call answered 'maybe'" in section
      and "as the text means them: `nudge`." in section
      and "already has these words: `agent-seats`, `/cold-read`." in section
      and "bad line" in section, section)
check("the section says its entries are not findings, and the findings parser counts none of them",
      "not findings and take no finding outcome" in section
      and findings_common.cold_read_fast_read_report_findings(
          "## Question 2: Where you struggled\n\n1. one\n" + section) == [
          findings_common.Finding(2, 1, "one")], section)
check("an edit's section names the sentences the edit added or changed",
      "the sentences the edit added or changed use" in section, section)
check("stderr counts every fate, and names each word not checked with its cause",
      stderr_lines[0].startswith("cold-read-fast-read: words with a meaning of their own: 5 listed, 2 already in a glossary, "
                                 "1 read as the text means, 1 read another way, 2 not checked")
      and any("`flaky` not checked" in line for line in stderr_lines)
      and any("bad line" in line for line in stderr_lines), repr(stderr_lines))

calls = []
section, stderr_lines = new_words.new_words_fresh_reader_meaning_checks_run_into_report_section_and_stderr_lines(
    new_words.fast_clarify_cell_report_new_words_section_split_off_and_parse("## Words with a meaning of their own\n\n- none\n"), whole_document=True,
    ask=lambda *arguments: calls.append(arguments), known_words=lambda: calls.append("glossary") or set())
check("a list of no words makes no model call and reads no glossary, and the section says no word was listed",
      calls == [] and "listed no such word" in section and "the document use" in section, section)


def glossaries_unlistable():
    raise new_words.new_shared_names.GitFailure("git ls-files exited 128: not a git repository")


section, stderr_lines = new_words.new_words_fresh_reader_meaning_checks_run_into_report_section_and_stderr_lines(
    new_words.fast_clarify_cell_report_new_words_section_split_off_and_parse("## Words with a meaning of their own\n\n- `rider`: m\n"), whole_document=False,
    ask=ask_by_word({"rider": (("g", ""), ("DIFFERS", ""))}), known_words=glossaries_unlistable)
check("when git cannot list the glossaries, the section and stderr say so, and every word is still checked",
      "the glossaries could not be listed" in section and "not a git repository" in section
      and "- `rider`: the text means" in section
      and any("glossaries could not be listed" in line for line in stderr_lines), section)


# --- One call through a cold-read-cell launcher, against a stub launcher -------------------------------------
STUB_LAUNCHER = """import pathlib, sys, time
argv = sys.argv
report = pathlib.Path(argv[argv.index("--report") + 1])
behaviour = pathlib.Path(argv[argv.index("--target") + 1]).read_text(encoding="utf-8").strip()
if behaviour in ("`answer`", "`warn`"):
    if behaviour == "`warn`":
        print("cold-read-agy-cell: stray write: a file outside the report changed")
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text("<!-- provenance: runtime=agy model=m -->\\n\\nMATCHES\\n", encoding="utf-8")
elif behaviour == "`fail`":
    print("progress line")
    print("cold-read-agy-cell: cause: model-limit — quota")
    sys.exit(1)
else:
    time.sleep(60)
"""
with tempfile.TemporaryDirectory() as scratch_name:
    scratch = pathlib.Path(scratch_name)
    launcher = scratch / "stub-launcher.py"
    launcher.write_text(STUB_LAUNCHER, encoding="utf-8")
    later = time.monotonic() + 30
    answer_text, cause = new_words.cold_read_cell_launcher_call_with_one_prompt_on_fast_tier_returning_answer_or_failure_cause(
        launcher, "new-word-meaning-compare", "{TARGET_PATH} {REPORT_PATH}", "`answer`\n", scratch / "a", later)
    check("a launcher's report is the answer, without its provenance stamp", (answer_text, cause) == ("MATCHES", ""),
          repr((answer_text, cause)))
    answer_text, cause = new_words.cold_read_cell_launcher_call_with_one_prompt_on_fast_tier_returning_answer_or_failure_cause(
        launcher, "new-word-meaning-guess", "{TARGET_PATH} {REPORT_PATH}", "`fail`\n", scratch / "b", later)
    check("a launcher that fails gives no answer, and its cause line is the cause",
          answer_text is None and "exited 1" in cause and "cause: model-limit" in cause, repr((answer_text, cause)))
    import contextlib
    import io
    captured = io.StringIO()
    with contextlib.redirect_stderr(captured):
        answer_text, cause = new_words.cold_read_cell_launcher_call_with_one_prompt_on_fast_tier_returning_answer_or_failure_cause(
            launcher, "new-word-meaning-compare", "{TARGET_PATH} {REPORT_PATH}", "`warn`\n", scratch / "w", later)
    check("a launcher that exits 0 after a warning gives its answer, and its warning reaches stderr",
          (answer_text, cause) == ("MATCHES", "") and "stray write" in captured.getvalue(),
          repr((answer_text, cause, captured.getvalue())))
    started = time.monotonic()
    answer_text, cause = new_words.cold_read_cell_launcher_call_with_one_prompt_on_fast_tier_returning_answer_or_failure_cause(
        launcher, "new-word-meaning-guess", "{TARGET_PATH} {REPORT_PATH}", "`hang`\n", scratch / "c",
        time.monotonic() + 1)
    check("a launcher still running at the deadline is stopped, and gives no answer",
          answer_text is None and "time limit" in cause and time.monotonic() - started < 20, repr(cause))
    answer_text, cause = new_words.cold_read_cell_launcher_call_with_one_prompt_on_fast_tier_returning_answer_or_failure_cause(
        launcher, "new-word-meaning-guess", "{TARGET_PATH} {REPORT_PATH}", "`answer`\n", scratch / "d",
        time.monotonic() - 1)
    check("a call whose deadline has passed starts no launcher",
          answer_text is None and "ran out before this call started" in cause
          and not (scratch / "d" / "answer").exists(), repr(cause))

    answer_text, cause = new_words.cold_read_cell_launcher_call_with_one_prompt_on_fast_tier_returning_answer_or_failure_cause(
        launcher, "new-word-meaning-guess", "{TARGET_PATH} {REPORT_PATH}", "`answer`\n", scratch / "a", later)
    check("a call whose files cannot be written, here because its directory already exists, gives no answer "
          "and its cause, and raises nothing",
          answer_text is None and "could not be written" in cause and "File exists" in cause, repr(cause))
    real_start = new_words.ModelCallsInFlight.start

    def start_refused(self, command, **popen_arguments):
        raise OSError(11, "Resource temporarily unavailable")
    new_words.ModelCallsInFlight.start = start_refused
    try:
        answer_text, cause = new_words.cold_read_cell_launcher_call_with_one_prompt_on_fast_tier_returning_answer_or_failure_cause(
            launcher, "new-word-meaning-guess", "{TARGET_PATH} {REPORT_PATH}", "`answer`\n", scratch / "e", later)
    finally:
        new_words.ModelCallsInFlight.start = real_start
    check("a launcher that cannot start, as at a process limit, gives no answer and its cause, and raises nothing",
          answer_text is None and "could not start" in cause and "Resource temporarily unavailable" in cause,
          repr(cause))

    # A signal during the checks: the launchers run in sessions of their own, so the read must stop them.
    import os
    import signal
    import threading
    calls = new_words.NewWordModelCalls(launcher, scratch / "signalled", deadline=time.monotonic() + 120)
    started_calls = []
    real_call = new_words.cold_read_cell_launcher_call_with_one_prompt_on_fast_tier_returning_answer_or_failure_cause

    def counted_call(*arguments):
        started_calls.append(arguments[1])
        return real_call(*arguments)
    new_words.cold_read_cell_launcher_call_with_one_prompt_on_fast_tier_returning_answer_or_failure_cause = counted_call
    previous_handler = signal.signal(signal.SIGTERM, lambda number, _frame: (_ for _ in ()).throw(SystemExit(128 + number)))
    threading.Timer(2, lambda: os.kill(os.getpid(), signal.SIGTERM)).start()
    started, ended_by = time.monotonic(), None
    try:
        new_words.new_words_fresh_reader_meaning_checks_run_into_report_section_and_stderr_lines(
            new_words.NewWordsAnswer("", [("hang", "m"), ("hang", "n")], []), whole_document=True,
            ask=lambda label, template, _question: calls(label, template, "`hang`\n"),
            known_words=lambda: set(), stop_model_calls=calls.stop_all)
    except SystemExit as error:
        ended_by = error.code
    finally:
        signal.signal(signal.SIGTERM, previous_handler)
        new_words.cold_read_cell_launcher_call_with_one_prompt_on_fast_tier_returning_answer_or_failure_cause = real_call
    check("a SIGTERM during the checks ends them within seconds, stops every running launcher, and starts "
          "no compare call",
          ended_by == 128 + signal.SIGTERM and time.monotonic() - started < 20 and not calls.calls.processes
          and started_calls == ["new-word-meaning-guess", "new-word-meaning-guess"],
          repr((ended_by, time.monotonic() - started, calls.calls.processes, started_calls)))
    answer_text, cause = calls("new-word-meaning-compare", "{TARGET_PATH} {REPORT_PATH}", "`answer`\n")
    check("once stopped, a call starts no launcher", answer_text is None and "ended before this call started" in cause,
          repr(cause))


# --- Fixes from pull request 4887's follow-up -----------------------------------------------------------------
section, _ = new_words.new_words_fresh_reader_meaning_checks_run_into_report_section_and_stderr_lines(
    new_words.NewWordsAnswer("", [("rider", "m")], []), whole_document=True,
    ask=ask_by_word({"rider": (("a guess\n\n## Question 2: Where you struggled\n\n1. a list item\n", ""),
                               ("DIFFERS", ""))}),
    known_words=lambda: set())
check("a guess holding a heading and a numbered list is quoted on one line, so the findings parser counts "
      "nothing from it",
      "\n## Question 2" not in section and "a guess ## Question 2: Where you struggled 1. a list item" in section
      and findings_common.cold_read_fast_read_report_findings(section) == [], section)

calls = []
section, stderr_lines = new_words.new_words_fresh_reader_meaning_checks_run_into_report_section_and_stderr_lines(
    new_words.NewWordsAnswer("", [("rider", "m")], []), whole_document=False,
    ask=lambda *arguments: calls.append(arguments), known_words=lambda: calls.append("glossary") or set(),
    edit_added_or_changed_no_sentence=True)
check("when the edit only removed text, no word is checked and no glossary read, and the section and "
      "stderr say so",
      calls == [] and "added or changed no sentence, so no word was checked" in section
      and "1 listed, 0 already in a glossary, 0 read as the text means, 0 read another way, 1 not checked"
      in stderr_lines[0], repr((section, stderr_lines)))

section, stderr_lines = new_words.new_words_fresh_reader_meaning_checks_run_into_report_section_and_stderr_lines(
    new_words.NewWordsAnswer("", [("agent-seat", "one meaning"), ("agent-seat", "another meaning")], []),
    whole_document=True, ask=lambda *_: (None, "unused"), known_words=lambda: {"agent-seat"})
check("two meanings of one glossary word count as two dropped, so the counts add up, and the word is named once",
      "2 listed, 2 already in a glossary" in stderr_lines[0] and section.count("`agent-seat`") == 1,
      repr((section, stderr_lines)))

answer = new_words.fast_clarify_cell_report_new_words_section_split_off_and_parse(
    "## Question 1: x\n\n````\n```\n## Words with a meaning of their own\n\n- `quoted`: an example\n```\n````\n\n"
    "## Words with a meaning of their own\n\n- `real`: the real one\n")
check("a three-backtick line inside a four-backtick fence does not close it, so a quoted section is not read",
      answer.words == [("real", "the real one")], repr(answer))
answer = new_words.fast_clarify_cell_report_new_words_section_split_off_and_parse(
    "~~~\n```\n## Words with a meaning of their own\n\n- `quoted`: an example\n~~~\n\n"
    "## Words with a meaning of their own\n\n- none\n")
check("a backtick fence quoted inside a tilde fence does not toggle it",
      answer.words == [] and answer.problems == [], repr(answer))

import os
known = new_words.known_words_in_glossaries_and_ordinary_hyphenated_words_list(new_words.REPO_ROOT)
check("a glossary entry's alias, `code-prompt-code (aka CPC)`, makes both the name and the alias known words",
      new_words.word_is_known("code-prompt-code", known) and new_words.word_is_known("CPC", known), repr(sorted(known)[:20]))
saved = {name: os.environ.get(name) for name in ("GIT_DIR", "GIT_INDEX_FILE")}
os.environ["GIT_DIR"] = "/nonexistent-git-directory"
os.environ["GIT_INDEX_FILE"] = "/nonexistent-git-index"
try:
    with_redirect = new_words.known_words_in_glossaries_and_ordinary_hyphenated_words_list(new_words.REPO_ROOT)
    redirect_error = ""
except new_words.new_shared_names.GitFailure as error:
    with_redirect, redirect_error = set(), str(error)
finally:
    for name, value in saved.items():
        if value is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = value
check("with GIT_DIR and GIT_INDEX_FILE set elsewhere, as inside a git hook, the checkout's own glossaries are listed",
      with_redirect == known, redirect_error or repr(len(with_redirect)))

print()
if failures:
    print(f"{len(failures)} case(s) failed: {', '.join(failures)}")
    sys.exit(1)
print("all cases passed")
