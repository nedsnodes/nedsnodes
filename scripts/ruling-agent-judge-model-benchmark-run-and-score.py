#!/usr/bin/env python3
"""Run one model and effort on the ruling-agent judge benchmark's cases, and score the rows such runs wrote.

The benchmark picks the model that ruling-agent's prompt runs to judge whether a stored message of the user's
decides an approval-walk item (docs/issues/2118-ruling-agent-keeps-user-rulings-checks-approval-walk.md). The user
approved it as items 12 and 13 of approval-walk md-skills-2-agent-seat-items-awaiting-user-ruling-approval-walk-
2026-11-21. Its case set is in the log-store, because it holds the user's words: one JSON file per case under
<case set>/cases/, and every store entry a case lists under <case set>/candidate-entries.jsonl.

Usage:
  ruling-agent-judge-model-benchmark-run-and-score.py run --case-set DIR --runtime {claude,agy,codex}
      --model MODEL --effort EFFORT --hits-from RETRIEVER:LIST --first-n N --rows FILE
      [--repeats 3] [--case CASE_ID ...] [--instructions-checkout DIR] [--keep DIR]
  ruling-agent-judge-model-benchmark-run-and-score.py score --rows FILE [FILE ...]

run: for each repeat and each case, one fresh agent gets, in one prompt, CLAUDE.md, the project glossary and the
system glossaries it lists, the item's text, and the first N messages of the case's list --hits-from names, each
with the agent message it answered, and answers DECIDES or NO for each. --hits-from names a retriever's ranked
list inside a case file, such as grep:hits_newest_first, so a search by meaning that writes its own list into the
cases is run the same way. One JSON row per case and repeat is appended to --rows. A case whose model run passes
120 seconds drops the whole model and effort: its row says so and the run stops.

score: for each model, effort, list and N in the rows, the middle of the repeats' found-out-of-cases and of their
mean seconds per case, the score (percent of cases whose known ruling was answered DECIDES, divided by that mean
seconds; highest wins), and the wrong-DECIDES count on the other messages. A combination is out when it was
dropped, when more than 1 in 10 of its other messages across all its rows were answered DECIDES, or when it has
fewer rows than its cases times its repeats.

EXIT. 0 when every run finished, or every row was scored. 1 when a combination was dropped at 120 seconds.
2 when the run or score could not be done: bad arguments or case set, or a model run that failed; a line opening
FAILED on stderr says which.
"""

import argparse
import importlib.util
import json
import os
import re
import signal
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPOSITORY = HERE.parent
_prefix_spec = importlib.util.spec_from_file_location(
    "claude_code_headless_run_command_line_prefix_with_no_connectors_and_explicit_permission_mode_common",
    REPOSITORY / "nn-systems" / "general-tools"
    / "claude-code-headless-run-command-line-prefix-with-no-connectors-and-explicit-permission-mode-common.py")
command_line_prefix = importlib.util.module_from_spec(_prefix_spec)
_prefix_spec.loader.exec_module(command_line_prefix)

EXIT_OK, EXIT_DROPPED, EXIT_COULD_NOT_RUN = 0, 1, 2
ANSWER_WORDS = ("DECIDES", "NO")
DROP_AFTER_SECONDS = 120
OVER_FLAG_LIMIT = 0.1
PROJECT_GLOSSARY = "docs/nedsnodes-wiki/nedsnodes-glossary.md"
SYSTEM_GLOSSARY_IN_PROJECT_GLOSSARY = re.compile(r"`([^`\s]+-glossary\.md)`")
ANSWER_LINE = re.compile(r"^(m\d+):\s*(\S+)\s*$")
STATE_ANSWERED, STATE_ANSWER_UNPARSABLE, STATE_DROPPED = "answered", "answer-unparsable", "dropped-over-120-seconds"

# The cold-read cell launchers already run agy and codex inside the credential sandbox the project requires, and
# write the model's answer to the report file. Codex's fast mode is that launcher's "deep" tier, whose
# service_tier is "priority".
CELL_LAUNCHERS = {"agy": ("cold-read-agy-cell.py", "fast"), "codex": ("cold-read-codex-cell.py", "deep")}

PROMPT_TEMPLATE = """You judge whether messages the user once typed decide an approval-walk item that an agent is about to show him. A message decides the item when it already settles the question the item asks, so that showing the item again would ask him to decide what he has decided. Every file you need is given in full below; open no file and run no tool.

First come CLAUDE.md and the glossaries, which every agent of this project reads. Then the item. Then {count} messages of the user's, each with the agent message it answered, ids m1 to m{count}.

Answer with exactly {count} lines and nothing else, one per message, in order, each the message's id, a colon, a space and one word: DECIDES when that message decides the item, NO otherwise. For example:
m1: NO
m2: DECIDES

# Files given in full
{files}
# The approval-walk item

{item}
# The user's messages
{messages}
Answer now with the {count} lines only."""

MESSAGE_TEMPLATE = """
## {message_id}, said {said_at_utc}

The agent message it answered:
<<<
{answered}
>>>

The user's message:
<<<
{text}
>>>
"""


class CouldNotRun(Exception):
    pass


class AnswerUnparsable(Exception):
    pass


def load_case_set(case_set):
    cases_directory = Path(case_set) / "cases"
    entries_file = Path(case_set) / "candidate-entries.jsonl"
    if not cases_directory.is_dir() or not entries_file.is_file():
        raise CouldNotRun(f"{case_set} has no cases/ directory or no candidate-entries.jsonl, so it is not a case set; "
                          f"give --case-set the directory the case-set build wrote")
    cases = {}
    for path in sorted(cases_directory.glob("*.json")):
        case = json.loads(path.read_text(encoding="utf-8"))
        cases[case["case_id"]] = case
    entries = {}
    with entries_file.open(encoding="utf-8") as handle:
        for line in handle:
            entry = json.loads(line)
            entries[entry["id"]] = entry
    return cases, entries


def instruction_files(checkout):
    """[(path, text)] of CLAUDE.md, the project glossary and each system glossary the project glossary lists."""
    checkout = Path(checkout)
    project_glossary = (checkout / PROJECT_GLOSSARY).read_text(encoding="utf-8")
    paths = ["CLAUDE.md", PROJECT_GLOSSARY]
    for path in SYSTEM_GLOSSARY_IN_PROJECT_GLOSSARY.findall(project_glossary):
        if path not in paths and (checkout / path).is_file():
            paths.append(path)
    return [(path, (checkout / path).read_text(encoding="utf-8")) for path in paths]


def case_hits(case, hits_from):
    retriever, _, list_name = hits_from.partition(":")
    try:
        return case[retriever][list_name]
    except (KeyError, TypeError):
        raise CouldNotRun(f"case {case['case_id']} has no list {list_name!r} under {retriever!r}; give --hits-from "
                          f"as RETRIEVER:LIST naming a list a case file holds, such as grep:hits_newest_first") from None


def build_prompt(case, entries, hits, files):
    """(prompt, [entry id of m1, m2, ...])."""
    message_ids = list(hits)
    messages = "".join(MESSAGE_TEMPLATE.format(
        message_id=f"m{number}", said_at_utc=entries[entry_id]["said_at_utc"],
        answered=(entries[entry_id].get("agent_message_answered") or "(none stored)").strip(),
        text=entries[entry_id]["text"].strip()) for number, entry_id in enumerate(message_ids, 1))
    given = "".join(f"\n===== BEGIN {path} =====\n{text}\n===== END {path} =====\n" for path, text in files)
    prompt = PROMPT_TEMPLATE.format(count=len(message_ids), files=given, item=case["walk_item_text"], messages=messages)
    return prompt, message_ids


def parse_answers(answer, message_ids):
    """{entry id: "DECIDES" or "NO"} from the model's answer; raises AnswerUnparsable unless every line but blank
    ones is "m<k>: DECIDES" or "m<k>: NO" and each message is answered exactly once."""
    by_label = {f"m{number}": entry_id for number, entry_id in enumerate(message_ids, 1)}
    answers = {}
    for line in answer.splitlines():
        if not line.strip():
            continue
        match = ANSWER_LINE.match(line.strip())
        if not match:
            raise AnswerUnparsable(f"a line is not '<id>: DECIDES' or '<id>: NO': {line.strip()[:200]!r}")
        label, word = match.groups()
        if label not in by_label:
            raise AnswerUnparsable(f"{label} is not one of the ids m1 to m{len(message_ids)}")
        if word not in ANSWER_WORDS:
            raise AnswerUnparsable(f"{label} was answered {word!r}, which is not DECIDES or NO")
        if by_label[label] in answers:
            raise AnswerUnparsable(f"{label} was answered twice")
        answers[by_label[label]] = word
    missing = [label for label, entry_id in by_label.items() if entry_id not in answers]
    if missing:
        raise AnswerUnparsable(f"{len(missing)} message(s) got no answer, the first {missing[0]}")
    return answers


def model_invocation(runtime, model, effort, prompt_file, report_file):
    """(argv, stdin text or None, working directory or None, where the answer is: "stdout" or the report file)."""
    if runtime == "claude":
        argv = [*command_line_prefix.claude_code_headless_run_command_line_prefix_build(
                    "dontAsk", caller_claude_code_session_settings={"disableAllHooks": True}),
                "--model", model, "--effort", effort, "--output-format", "text", "--tools", "",
                "--no-session-persistence"]
        # An empty working directory, so Claude Code loads no project CLAUDE.md on top of the one in the prompt.
        return argv, prompt_file.read_text(encoding="utf-8"), prompt_file.parent / "empty-working-directory", "stdout"
    launcher, tier = CELL_LAUNCHERS[runtime]
    argv = [sys.executable, str(REPOSITORY / "nn-systems" / "cold-read" / launcher), "--cell", "ruling-judge",
            "--tier", tier, "--target", str(prompt_file), "--report", str(report_file), "--prompt-file", str(prompt_file),
            "--model", model, "--effort", effort]
    return argv, None, None, report_file


def model_run_timed(argv, stdin_text, working_directory, limit_seconds):
    """(exit code or None when stopped at the limit, stdout, stderr, wall-clock seconds).

    The one timer here. agent-instructions-editor's fast-read timing script
    (nedlern@ned-box:/home/nedlern/nedsnodes-logs/seats/agent-instructions-editor/fast-read-timing-2026-11-24/) times a
    run the same way, wall-clock around one launcher subprocess; once it is published as a function that takes a
    command, this function calls it instead."""
    started = time.monotonic()
    process = subprocess.Popen(argv, stdin=subprocess.PIPE if stdin_text is not None else subprocess.DEVNULL,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, cwd=working_directory,
                               start_new_session=True)
    try:
        stdout, stderr = process.communicate(stdin_text, timeout=limit_seconds)
        return process.returncode, stdout, stderr, round(time.monotonic() - started, 2)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
        stdout, stderr = process.communicate()
        return None, stdout, stderr, round(time.monotonic() - started, 2)


def known_ruling_ids(case):
    return {ruling["store_entry_id"] for ruling in case["known_rulings"] if ruling["store_entry_id"]}


def run_one_case(case, entries, arguments, files, repeat, work):
    hits = case_hits(case, arguments.hits_from)[:arguments.first_n]
    prompt, message_ids = build_prompt(case, entries, hits, files)
    prompt_file = work / f"{case['case_id']}-prompt.md"
    prompt_file.write_text(prompt, encoding="utf-8")
    report_file = work / f"{case['case_id']}-repeat-{repeat}-answer.md"
    (work / "empty-working-directory").mkdir(exist_ok=True)
    argv, stdin_text, working_directory, answer_place = model_invocation(
        arguments.runtime, arguments.model, arguments.effort, prompt_file, report_file)
    started_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    exit_code, stdout, stderr, seconds = model_run_timed(argv, stdin_text, working_directory, DROP_AFTER_SECONDS)
    known = known_ruling_ids(case)
    row = {"case_id": case["case_id"], "runtime": arguments.runtime, "model": arguments.model, "effort": arguments.effort,
           "hits_from": arguments.hits_from, "first_n": arguments.first_n, "repeat": repeat, "started_at_utc": started_at,
           "seconds": seconds, "prompt_bytes": len(prompt.encode("utf-8")), "messages": len(message_ids),
           "known_rulings_in_messages": sorted(known & set(message_ids)), "exit_code": exit_code}
    if exit_code is None:
        return {**row, "state": STATE_DROPPED}, stdout
    answer = stdout if answer_place == "stdout" else (report_file.read_text(encoding="utf-8") if report_file.is_file() else "")
    if exit_code != 0:
        raise CouldNotRun(f"the {arguments.runtime} run of {arguments.model} at effort {arguments.effort} on case "
                          f"{case['case_id']} exited {exit_code}; its stderr ends: {stderr.strip()[-600:]}")
    if answer_place != "stdout":
        report_file.unlink(missing_ok=True)
    try:
        answers = parse_answers(answer, message_ids)
    except AnswerUnparsable as error:
        return {**row, "state": STATE_ANSWER_UNPARSABLE, "failure": str(error), "found": False}, answer
    others = [entry_id for entry_id in message_ids if entry_id not in known]
    return {**row, "state": STATE_ANSWERED,
            "known_rulings_decided": sorted(entry_id for entry_id in known if answers.get(entry_id) == "DECIDES"),
            "found": any(answers.get(entry_id) == "DECIDES" for entry_id in known),
            "other_messages": len(others), "other_messages_decided": sum(answers[e] == "DECIDES" for e in others),
            "answers": answers}, answer


def run(arguments):
    if arguments.first_n < 1:
        raise CouldNotRun("--first-n must be 1 or more")
    cases, entries = load_case_set(arguments.case_set)
    if arguments.case:
        unknown = [case_id for case_id in arguments.case if case_id not in cases]
        if unknown:
            raise CouldNotRun(f"no case named {unknown[0]} in {arguments.case_set}/cases/")
        cases = {case_id: cases[case_id] for case_id in arguments.case}
    files = instruction_files(arguments.instructions_checkout)
    with tempfile.TemporaryDirectory(prefix="ruling-agent-judge-benchmark-") as scratch:
        work = Path(arguments.keep) if arguments.keep else Path(scratch)
        work.mkdir(parents=True, exist_ok=True)
        with open(arguments.rows, "a", encoding="utf-8") as rows:
            for repeat in range(1, arguments.repeats + 1):
                for case in cases.values():
                    row, answer = run_one_case(case, entries, arguments, files, repeat, work)
                    rows.write(json.dumps(row) + "\n")
                    rows.flush()
                    if arguments.keep:
                        (work / f"{case['case_id']}-repeat-{repeat}-{arguments.model}-{arguments.effort}-answer.txt").write_text(
                            answer, encoding="utf-8")
                    print(json.dumps({k: v for k, v in row.items() if k != "answers"}), flush=True)
                    if row["state"] == STATE_DROPPED:
                        print(f"DROPPED: {arguments.model} at effort {arguments.effort} took over {DROP_AFTER_SECONDS} "
                              f"seconds on case {case['case_id']}, so this model and effort is out and no further "
                              f"case was run.", file=sys.stderr)
                        return EXIT_DROPPED
    return EXIT_OK


def combination_key(row):
    return (row["runtime"], row["model"], row["effort"], row["hits_from"], row["first_n"])


def score(arguments):
    groups = {}
    for path in arguments.rows:
        try:
            lines = Path(path).read_text(encoding="utf-8").splitlines()
        except OSError as error:
            raise CouldNotRun(f"cannot read the rows file {path}: {error}") from error
        for line in lines:
            if line.strip():
                row = json.loads(line)
                groups.setdefault(combination_key(row), []).append(row)
    if not groups:
        raise CouldNotRun("the rows files hold no rows")
    for key, rows in sorted(groups.items()):
        case_ids = sorted({row["case_id"] for row in rows})
        repeats = sorted({row["repeat"] for row in rows})
        answered = [row for row in rows if row["state"] == STATE_ANSWERED]
        other = sum(row["other_messages"] for row in answered)
        other_decided = sum(row["other_messages_decided"] for row in answered)
        per_repeat = []
        for repeat in repeats:
            repeat_rows = [row for row in rows if row["repeat"] == repeat]
            per_repeat.append({"repeat": repeat, "found": sum(bool(row.get("found")) for row in repeat_rows),
                               "mean_seconds_per_case": statistics.mean(row["seconds"] for row in repeat_rows)})
        found = statistics.median_low([r["found"] for r in per_repeat])
        seconds = statistics.median([r["mean_seconds_per_case"] for r in per_repeat])
        out = []
        if any(row["state"] == STATE_DROPPED for row in rows):
            out.append(f"took over {DROP_AFTER_SECONDS} seconds on a case")
        if other and other_decided / other > OVER_FLAG_LIMIT:
            out.append(f"answered DECIDES on {other_decided} of {other} other messages, more than 1 in 10")
        if len(rows) < len(case_ids) * len(repeats):
            out.append(f"has {len(rows)} rows, fewer than its {len(case_ids)} cases times {len(repeats)} repeats")
        runtime, model, effort, hits_from, first_n = key
        print(json.dumps({
            "runtime": runtime, "model": model, "effort": effort, "hits_from": hits_from, "first_n": first_n,
            "cases": len(case_ids), "repeats": len(repeats),
            "found_middle_of_repeats": found, "mean_seconds_per_case_middle_of_repeats": round(seconds, 2),
            "score": round(100 * found / len(case_ids) / seconds, 4) if seconds else None,
            "other_messages": other, "other_messages_decided": other_decided,
            "answers_unparsable": sum(row["state"] == STATE_ANSWER_UNPARSABLE for row in rows),
            "out": out, "per_repeat": per_repeat}))
    return EXIT_OK


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    run_parser = commands.add_parser("run", help="run one model and effort on the cases")
    run_parser.add_argument("--case-set", required=True)
    run_parser.add_argument("--runtime", required=True, choices=["claude", *CELL_LAUNCHERS])
    run_parser.add_argument("--model", required=True)
    run_parser.add_argument("--effort", required=True)
    run_parser.add_argument("--hits-from", required=True, help="RETRIEVER:LIST, such as grep:hits_newest_first")
    run_parser.add_argument("--first-n", required=True, type=int)
    run_parser.add_argument("--rows", required=True, help="JSON Lines file the rows are appended to")
    run_parser.add_argument("--repeats", type=int, default=3)
    run_parser.add_argument("--case", action="append", default=[], help="run only this case id; repeatable")
    run_parser.add_argument("--instructions-checkout", default=str(REPOSITORY),
                            help="the checkout whose CLAUDE.md and glossaries go into the prompt")
    run_parser.add_argument("--keep", help="directory to keep each prompt and answer in")
    score_parser = commands.add_parser("score", help="score the rows of earlier runs")
    score_parser.add_argument("--rows", required=True, nargs="+")
    arguments = parser.parse_args(argv)
    try:
        return run(arguments) if arguments.command == "run" else score(arguments)
    except CouldNotRun as error:
        print(f"FAILED: {error}", file=sys.stderr)
        return EXIT_COULD_NOT_RUN


if __name__ == "__main__":
    sys.exit(main())
