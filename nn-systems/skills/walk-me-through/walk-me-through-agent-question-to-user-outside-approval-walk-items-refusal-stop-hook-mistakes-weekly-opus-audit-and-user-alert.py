#!/usr/bin/env python3
"""Have Opus label a sample of the lines the question-check Stop hook's model judged in the week before the run,
against the answer key's labelling rules; write the counts to the log-store; and write a user-alert, which becomes an
item of the user's approval-walk, only when a threshold below is crossed.

    python3 <this file>

It is not in nn-systems/general-tools/scheduled-jobs-on-each-machine.json, so it runs only when started by hand.

THE LINES are the rows of the hook's log of each reply line it sent its model, with the model's ask-or-not label,
which walk-me-through-agent-question-to-user-outside-approval-walk-items-refusal-stop-hook.py writes and its
reply_line_model_ask_or_not_label_log_path finds, written in the WINDOW_DAYS before this run. A row whose call failed
has no label and is left out. A line judged again in the same agent-session, as happens when the hook blocks and the
agent replies in the same turn, counts once, with its newest label. A row that is not a JSON object holding a time
with its time zone and every field the labeller needs is counted as malformed and left out.

THE SAMPLE is SAMPLE_SIZE_PER_VERDICT lines the hook's model called an ask, the refused lines, and as many it called
no ask, the passed lines, drawn at random, or every line when there are fewer.

THE LABELLER, LABELLER_MODEL, labels each line in a headless `claude -p` call of its own, the calls run by the hook's
reply_line_model_ask_or_not_label_from_claude_call, which checks that the answer gives the line exactly one label
whose `ask` is true or false and reports any other answer as a failed call. It is sent the same entry the hook's
model was sent, under a fresh id and with the refused and passed lines shuffled together, so it cannot tell which the
hook refused, after the answer key's labelling prompt, ANSWER_KEY_LABELLING_PROMPT_RELATIVE_TO_LOG_STORE, the prompt
the answer key's models were scored with: the labellers' rules with the user's rulings in general words. Labelling
is the job's only judgment.

THE COUNTS: a missed ask is a passed line the labeller calls an ask; a wrong stop is a refused line it calls no ask.
A user-alert is written when there is a missed ask, or when at least MINIMUM_LABELLED_REFUSED_LINES refused lines
were labelled and more than one in WRONG_STOPS_ONE_IN of them are wrong stops. Otherwise the counts go only to the
log-store. The alert goes to the user-alerts pending/ folder through
nn-systems/general-tools/user-alerts-pending-and-claimed-files-write-claim-release-and-delete-common.py, naming
each missed ask and wrong stop with the labeller's reason.

THE RECORD of every run, the window, the counts, every sampled line with both labels, and the user-alert's id when
one was written, is one JSON file named for the run's UTC time in COUNTS_DIRECTORY_NAME at the top of the log-store.

Exit status: 0 when every sampled line was labelled and the record, and any user-alert, were written. 1 when the
log-store, the log or the labelling prompt cannot be read, a labelling call failed, or the record or the user-alert
could not be written; the error goes to stderr, and never into a user-alert, which is
kept for a crossed threshold. Lines whose call failed are left out of the counts, and the counts of the lines
labelled still decide whether an alert is written.

Tool-messages-to-agent follow
docs/nedsnodes-wiki/nedsnodes-how-to-write-a-tool-message-to-agent-such-as-a-hook-refusal-or-script-error.md.
"""
import argparse
import concurrent.futures
import datetime
import importlib.util
import json
import os
import random
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
THIS_PROGRAM = "nn-systems/skills/walk-me-through/walk-me-through-agent-question-to-user-outside-approval-walk-items-refusal-stop-hook-mistakes-weekly-opus-audit-and-user-alert.py"
HOOK_FILE = HERE / "walk-me-through-agent-question-to-user-outside-approval-walk-items-refusal-stop-hook.py"
USER_ALERTS_FILE = (HERE.parents[1] / "general-tools"
                    / "user-alerts-pending-and-claimed-files-write-claim-release-and-delete-common.py")

WINDOW_DAYS = 7
SAMPLE_SIZE_PER_VERDICT = 20
MINIMUM_LABELLED_REFUSED_LINES = 10
WRONG_STOPS_ONE_IN = 5
LABELLER_MODEL = "claude-opus-5-5"
LABELLER_TIMEOUT_SECONDS = 300
LABELLER_CALLS_AT_ONCE = 8
NOT_LOGGED_IN = "Not logged in"
ANSWER_KEY_LABELLING_PROMPT_RELATIVE_TO_LOG_STORE = (
    Path("seats") / "fleet-restart-at-login" / "answer-key-fast-model-scores-2026-11-22"
    / "fast-model-ask-or-not-prompt.txt")
COUNTS_DIRECTORY_NAME = "walk-me-through-agent-question-to-user-outside-approval-walk-items-refusal-stop-hook-reply-line-model-ask-or-not-labels-weekly-opus-relabel-samples-labels-and-counts"
ENTRY_FIELDS = ("line", "turn_started_by", "message_that_started_the_turn", "agent_message_holding_the_line",
                "waiting_walk_item_text")

ALERT_TITLE = "The question-check hook's weekly relabelling found {found}"
ALERT_TEXT_OPENING = (
    "Each week {model} labels a sample of the lines the question-check Stop hook "
    "(walk-me-through-agent-question-to-user-outside-approval-walk-items-refusal-stop-hook.py) sent to its model, "
    "{hook_model}, using the answer key's labelling prompt. This week, from {start} to {end}: {refused} refused lines "
    "labelled, {wrong} of them wrong stops; {passed} passed lines labelled, {missed} of them missed asks. An item is "
    "raised when any passed line is a missed ask, or when more than 1 in {one_in} of at least {minimum} refused lines "
    "are wrong stops. The labeller can be wrong too; each line below is given with its reason. The whole sample, with "
    "the context each line was judged in, is in {record}.\n")
ALERT_ACTION = (
    "Only the user can decide whether the question-check hook's prompt or model should change. Present the lines "
    "above in an approval-walk item, saying for each whether you agree with the labeller after reading the line's "
    "context in the record, with a recommendation.")
RERUN_COMMAND = "cd /home/nedlern/Projects/nedsnodes && python3 " + THIS_PROGRAM + " --now {now}"
RERUN_INSTRUCTION = (
    "Fix each cause named, then run `" + RERUN_COMMAND + "` on ned-box, which samples the same week this run did. "
    "When you cannot fix a cause yourself, or the rerun fails again, tell the user, in one plain sentence, what "
    "failed and why, saying that the weekly relabelling of the lines the question-check Stop hook, "
    "walk-me-through-agent-question-to-user-outside-approval-walk-items-refusal-stop-hook.py, sent its model does "
    "not run until it is fixed; a subagent tells the agent that dispatched it instead, with the rerun command.")
PROMPT_UNREADABLE_REASON = (
    "the answer key's labelling prompt {path} could not be read ({error}); it is the prompt the answer key's models "
    "were scored with, and the labeller is given nothing else")
LOG_UNREADABLE_REASON = ("the hook's log of each reply line it sent its model, {path}, could not be read ({error})")
LOG_STORE_UNREACHABLE_REASON = "the hook's log of each reply line it sent its model cannot be found, {problem}"
LABELLING_FAILED_LINE = "Labelling failed for the line {line}: {failure}."
EVERY_LABELLING_CALL_LOGGED_OUT_MESSAGE = (
    "Every labelling call failed because `claude` on ned-box is not logged in, so no line was labelled and no "
    "user-alert was written.\n"
    "Tell the user this sentence, with no approval-walk item: \"`claude` on ned-box is logged out, so this week's "
    "relabelling of the question-check hook's lines could not run; you can log in from a Terminal on your Mac with "
    "`ssh nedlern@ned-box 'claude auth login'`.\" A subagent tells the agent that dispatched it instead, with the "
    "rerun command below, and stops.\n"
    "Once he says he has logged in, run `" + RERUN_COMMAND + "` on ned-box, which samples the same week this run did.")
EVERY_LABELLING_CALL_FAILED_MESSAGE = (
    "Every labelling call failed, as the line or lines above say, so no line was labelled and no user-alert was "
    "written. " + RERUN_INSTRUCTION)
SOME_LABELLING_CALLS_FAILED_MESSAGE = (
    "{failed} of {total} labelling calls failed, as the line or lines above say; those lines are left out of the counts, and "
    "the {labelled} lines labelled decided whether a user-alert was written. Nothing needs doing.")


def load_module(name, path):
    specification = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


hook = load_module("walk_me_through_agent_question_to_user_outside_approval_walk_items_refusal_stop_hook", HOOK_FILE)
user_alerts = load_module("user_alerts_pending_and_claimed_files_write_claim_release_and_delete_common",
                          USER_ALERTS_FILE)


class JobFailed(Exception):
    """A step failed that leaves nothing to count."""


def claude_binary():
    # Cron's PATH does not hold ~/.local/bin, where claude is installed.
    return shutil.which("claude") or str(Path.home() / ".local" / "bin" / "claude")


def window_lines(log_text, start, end):
    """(the newest row of each line judged between start and end with a label, one per agent-session and line; the
    number of malformed rows)."""
    newest, malformed = {}, 0
    for text in log_text.splitlines():
        if not text.strip():
            continue
        try:
            row = json.loads(text)
            if (not isinstance(row, dict)
                    or not all(field in row and isinstance(row[field], (str, type(None))) for field in ENTRY_FIELDS)
                    or not isinstance(row.get("line"), str) or not isinstance(row.get("session"), str)):
                raise ValueError("not a row of the hook's log")
            time = datetime.datetime.fromisoformat(row["time"])
            in_window = start <= time < end
        except (ValueError, TypeError, KeyError):
            # TypeError also covers a time without a time zone, which cannot be compared with the window.
            malformed += 1
            continue
        if in_window and type(row.get("ask")) is bool:
            newest[(row.get("session"), row["line"])] = row
    return list(newest.values()), malformed


def sample(rows, rng):
    """(up to SAMPLE_SIZE_PER_VERDICT refused rows, up to as many passed rows), each drawn at random."""
    refused = [row for row in rows if row["ask"]]
    passed = [row for row in rows if not row["ask"]]
    return (rng.sample(refused, min(SAMPLE_SIZE_PER_VERDICT, len(refused))),
            rng.sample(passed, min(SAMPLE_SIZE_PER_VERDICT, len(passed))))


def label(rows, prompt, rng, program):
    """One {row, id, labeller_ask, labeller_reason, labeller_failure} per row, shuffled, each labelled in its own call."""
    shuffled = rows[:]
    rng.shuffle(shuffled)
    entries = [{"id": f"L{number}", **{field: row.get(field) for field in ENTRY_FIELDS}}
               for number, row in enumerate(shuffled, 1)]
    with concurrent.futures.ThreadPoolExecutor(max_workers=LABELLER_CALLS_AT_ONCE) as pool:
        verdicts = list(pool.map(lambda entry: hook.reply_line_model_ask_or_not_label_from_claude_call(
            entry, LABELLER_TIMEOUT_SECONDS, model=LABELLER_MODEL, program=program, prompt=prompt), entries))
    return [{"row": row, "id": entry["id"], "labeller_ask": ask, "labeller_reason": reason,
             "labeller_failure": failure}
            for row, entry, (ask, reason, failure) in zip(shuffled, entries, verdicts)]


def counts(labelled):
    refused = [item for item in labelled if item["row"]["ask"] and item["labeller_failure"] is None]
    passed = [item for item in labelled if not item["row"]["ask"] and item["labeller_failure"] is None]
    return {"refused_labelled": len(refused), "wrong_stops": sum(not item["labeller_ask"] for item in refused),
            "passed_labelled": len(passed), "missed_asks": sum(item["labeller_ask"] for item in passed),
            "labelling_failed": sum(item["labeller_failure"] is not None for item in labelled)}


def wrong_stops_over_limit(numbers):
    return (numbers["refused_labelled"] >= MINIMUM_LABELLED_REFUSED_LINES
            and numbers["wrong_stops"] * WRONG_STOPS_ONE_IN > numbers["refused_labelled"])


def threshold_crossed(numbers):
    return numbers["missed_asks"] > 0 or wrong_stops_over_limit(numbers)


def alert_line(item):
    row = item["row"]
    return (f"- {json.dumps(row['line'], ensure_ascii=False)} (agent-session {row.get('session')}, {row.get('time')}); "
            f"the hook's model: {'ask' if row['ask'] else 'not an ask'}; {LABELLER_MODEL}: "
            f"{'ask' if item['labeller_ask'] else 'not an ask'}, because {item['labeller_reason']}")


def alert_text(numbers, labelled, start, end, record_path):
    missed = [item for item in labelled if item["labeller_failure"] is None and not item["row"]["ask"]
              and item["labeller_ask"]]
    wrong = [item for item in labelled if item["labeller_failure"] is None and item["row"]["ask"]
             and not item["labeller_ask"]]
    text = ALERT_TEXT_OPENING.format(
        model=LABELLER_MODEL, hook_model=hook.MODEL, start=start.isoformat(timespec="seconds"),
        end=end.isoformat(timespec="seconds"), refused=numbers["refused_labelled"], wrong=numbers["wrong_stops"],
        passed=numbers["passed_labelled"], missed=numbers["missed_asks"], one_in=WRONG_STOPS_ONE_IN,
        minimum=MINIMUM_LABELLED_REFUSED_LINES, record=record_path)
    if missed:
        text += "\nMissed asks, passed lines the labeller calls an ask:\n" + "\n".join(map(alert_line, missed)) + "\n"
    if wrong:
        text += "\nWrong stops, refused lines the labeller calls no ask:\n" + "\n".join(map(alert_line, wrong)) + "\n"
    found = " and ".join(part for part in (
        f"{numbers['missed_asks']} missed ask{'s' if numbers['missed_asks'] != 1 else ''}" if missed else "",
        f"{numbers['wrong_stops']} wrong stops in {numbers['refused_labelled']} refused lines"
        if wrong_stops_over_limit(numbers) else "") if part)
    return ALERT_TITLE.format(found=found), text


def labelling_failures_report(labelled, now):
    """(the lines and the one message that say which labelling calls failed and what to do, or []; exit status)."""
    when = now.isoformat(timespec="seconds")
    failed = [item for item in labelled if item["labeller_failure"] is not None]
    if not failed:
        return [], 0
    lines = [LABELLING_FAILED_LINE.format(line=json.dumps(item["row"]["line"], ensure_ascii=False)[:200],
                                          failure=item["labeller_failure"]) for item in failed]
    if len(failed) == len(labelled) and all(NOT_LOGGED_IN in item["labeller_failure"] for item in failed):
        lines.append(EVERY_LABELLING_CALL_LOGGED_OUT_MESSAGE.format(now=when))
    elif len(failed) == len(labelled):
        lines.append(EVERY_LABELLING_CALL_FAILED_MESSAGE.format(now=when))
    else:
        lines.append(SOME_LABELLING_CALLS_FAILED_MESSAGE.format(failed=len(failed), total=len(labelled),
                                                                labelled=len(labelled) - len(failed)))
    return lines, 1


def run(environment, now, rng, program):
    """Do one week's relabelling; return the exit status."""
    log_file, problem = hook.reply_line_model_ask_or_not_label_log_path(environment)
    if log_file is None:
        raise JobFailed(LOG_STORE_UNREACHABLE_REASON.format(problem=problem))
    log_store = log_file.parent
    prompt_file = log_store / ANSWER_KEY_LABELLING_PROMPT_RELATIVE_TO_LOG_STORE
    try:
        prompt = prompt_file.read_text(encoding="utf-8")
    except OSError as error:
        raise JobFailed(PROMPT_UNREADABLE_REASON.format(path=prompt_file, error=error)) from error
    try:
        log_text = log_file.read_text(encoding="utf-8") if log_file.exists() else ""
    except OSError as error:
        raise JobFailed(LOG_UNREADABLE_REASON.format(path=log_file, error=error)) from error
    start = now - datetime.timedelta(days=WINDOW_DAYS)
    rows, malformed = window_lines(log_text, start, now)
    refused, passed = sample(rows, rng)
    labelled = label(refused + passed, prompt, rng, program) if refused or passed else []
    numbers = {"lines_in_window": len(rows), "malformed_rows": malformed, **counts(labelled)}
    print(f"{start.isoformat(timespec='seconds')} to {now.isoformat(timespec='seconds')}: {json.dumps(numbers)}")
    failure_lines, status = labelling_failures_report(labelled, now)
    for line in failure_lines:
        print(line, file=sys.stderr)
    record_path = log_store / COUNTS_DIRECTORY_NAME / f"{now.strftime('%Y-%m-%dT%H%M%SZ')}.json"
    alert_id = None
    if threshold_crossed(numbers):
        title, text = alert_text(numbers, labelled, start, now, record_path)
        try:
            alert_id = user_alerts.user_alert_write_to_pending(title, text, ALERT_ACTION)
        except OSError as error:
            print(f"A threshold was crossed, but the user-alert could not be written, so none reached pending/: "
                  f"{error!r}. {RERUN_INSTRUCTION.format(now=now.isoformat(timespec='seconds'))}", file=sys.stderr)
            status = 1
        else:
            print(f"A threshold was crossed: user-alert {alert_id} written into the user-alerts pending/ folder.")
    record = {"window_start": start.isoformat(timespec="seconds"), "window_end": now.isoformat(timespec="seconds"),
              "labeller_model": LABELLER_MODEL, "hook_model": hook.MODEL, "counts": numbers,
              "user_alert_id": alert_id, "lines": labelled}
    try:
        record_path.parent.mkdir(parents=True, exist_ok=True)
        record_path.write_text(json.dumps(record, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    except OSError as error:
        print(f"The record of this run could not be written to {record_path}: {error!r}. Any user-alert this run "
              f"wrote stands and names that path. {RERUN_INSTRUCTION.format(now=now.isoformat(timespec='seconds'))}",
              file=sys.stderr)
        return 1
    print(f"Record written to {record_path}.")
    return status


def time_with_time_zone(text):
    time = datetime.datetime.fromisoformat(text)
    if time.tzinfo is None:
        raise argparse.ArgumentTypeError(f"{text!r} has no time zone; give one, as in {text}+00:00")
    return time


def main(argv=None, environment=None, rng=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--now", type=time_with_time_zone,
                        help="the end of the week sampled, as an ISO 8601 time with its time zone; default: now")
    arguments = parser.parse_args(argv)
    now = arguments.now or datetime.datetime.now(datetime.timezone.utc)
    try:
        return run(os.environ if environment is None else environment, now, rng or random.Random(), claude_binary())
    except JobFailed as error:
        print(f"No lines were relabelled and no user-alert was written, because {error}. "
              f"{RERUN_INSTRUCTION.format(now=now.isoformat(timespec='seconds'))}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
