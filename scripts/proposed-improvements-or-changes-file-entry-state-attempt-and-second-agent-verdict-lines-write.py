#!/usr/bin/env python3
"""Change the lines of a proposed-improvements-or-changes-file that its
handler may change, and refuse the changes that rules 4 and 5 of § The design
in docs/issues/1132-concerns-about-a-ghi-are-handled-by-agents.md forbid.

The handler is the forked subagent that settles a file's entries by
docs/agents/queue/proposed-improvements-or-changes-file-reviewer-entries-settling-subagent-instructions.md.
It changes the file only through this program, which
touches nothing but an entry's State line, its Attempt lines, its
"Second agent:" lines and its User-ruling lines, so an entry's own text is
never rewritten.

Subcommands, each on one file; show and attempt also read the GHI-MD's other files:

  show            every entry: its id, its State line, the attempts counted
                  since its last user-ruling line, and its last verdict.
                  Given a file in GHI_GUIDE_AGENT_LOG_STORE_DIRECTORY, shows
                  every proposed-improvements-or-changes-file there of the
                  same GHI-MD, those named after the part of its name before
                  FILE_NAME_INFIX as for a GHI-MD's name below; given any
                  other file, that file alone; each file under its path.
                  Given a GHI-MD's name
                  instead of a file, shows every
                  proposed-improvements-or-changes-file in the log-store named
                  after that GHI-MD, with or without its leading GHI number,
                  each under its path in the form nedlern@ned-box:<path>.
  attempt         adds one "Attempt <n> — <by>, <time>: <found> — sources read:
                  <source>; <source>" line under each entry named, the same
                  line under each for related entries. `--outcome` is what the
                  attempt reached. After an attempt whose outcome is left-open
                  brings an entry to MAXIMUM_ATTEMPTS attempts since its last
                  user-ruling line, marks the entry as needing the user, as
                  needs-the-user --because three-attempts does, giving
                  <found> as what the attempts could not settle; but when no
                  other entry is open in any proposed-improvements-or-changes-file
                  of its GHI-MD, it marks the entry only after a fourth
                  left-open attempt. The GHI-MD's files are the files beside
                  the given one that show would list for the part of its name
                  before FILE_NAME_INFIX; an entry with no State line counts
                  as open. Refused for an entry
                  that already has MAXIMUM_ATTEMPTS attempts while another
                  entry is open, and for one with MAXIMUM_ATTEMPTS + 1.
  second-agent-verdict
                  runs the second agent through `claude -p`, giving it
                  SECOND_AGENT_PROMPT, the entry's text without its State,
                  Attempt and "Second agent:" lines, which carry the handler's
                  conclusion, and the sources on the entry's last Attempt line;
                  prints its reply, and adds "Second agent: agrees (or
                  disagrees) that it is not worth doing, <who>, <time>" as the
                  reply's last line says. One verdict per attempt: refused, before
                  the agent runs, when no Attempt line follows the entry's last
                  verdict, so a disagreement spends the attempt it answers, and
                  asking again takes a new attempt; refused too when that Attempt line
                  names no sources. An agreement also settles the entry as
                  not worth doing, as settle --kind not-worth-doing does,
                  citing the Attempt line it answers, which holds the
                  handler's reasons. A disagreement on the entry's
                  MAXIMUM_ATTEMPTS-th attempt also marks the entry as needing the
                  user, as needs-the-user --because three-attempts does.
  settle          rewrites the State line as "settled, <how settled> — <by>,
                  <time>: <how>". "not worth doing", for an agreement that
                  second-agent-verdict did not write, is refused unless the
                  entry's last verdict is an agreement and no Attempt line
                  follows it; "new GHI filed" is refused unless <how> holds a
                  GHI's link. With `--settled-by [<file>] <upstream entry>`
                  in place of --kind and --how, for an entry the upstream
                  entry's change settled: adds an attempt under the entry,
                  as attempt --outcome settles does, naming the upstream
                  entry's file as its source, and settles the entry as done,
                  each line quoting the upstream entry's State line; refused
                  unless the upstream entry is settled as done. <file> is
                  the upstream entry's file when it is not the given one.
  needs-the-user  rewrites the State line as "needs the user — <by>, <time>:
                  <why>"; `--because three-attempts` is refused unless the
                  entry has MAXIMUM_ATTEMPTS attempts since its last user-ruling
                  line.
  user-ruling     run by the agent-seat that brought an entry that needs the
                  user to him: adds "User-ruling — the user, <time>, <where>:
                  <his words>" under the entry and, in the same write,
                  rewrites the State line as "State: open" or, with
                  `--state settled`, as "State: settled, by the user's
                  ruling — <by>, <time>: <where>". The only change made to an
                  entry whose State line says "needs the user"; refused for
                  any other entry.

Lines are recognised by how they open, as handlers have written them:
"State:", "Attempt" followed by a space or a colon, "Second agent:", and
"User-ruling" for the line recording the user's decision on the entry, from
which rule 4 counts attempts again. An entry runs from its "## E<n>" heading to
the next heading of level one or two. New lines go after the entry's last line that is not blank.

Each entry a subcommand marks as needing the user, needs-the-user's own and
those attempt and second-agent-verdict mark, gets a user-alert, written once
the file is replaced, naming the agent-seat whose agent-home the
handoff-supervisor launched this agent-session in, as
HANDOFF_SUPERVISOR_WORKING_DIRECTORY_ENVIRONMENT_VARIABLE names it; with no
agent-home there, such as a run through ssh, the alert names no agent-seat,
and goes to USER_ALERT_AGENT_SEAT_WHEN_ALERT_NAMES_NONE. Refused before any
change when that agent-seat's agent-home is not on this machine.

Every subcommand but show and user-ruling is refused on an entry whose
State line is not "State: open": a settled entry is never changed, and an
entry that needs the user takes only user-ruling.

The file is named by its path on this machine, or in the form
nedlern@ned-box:<path> that scripts/ghi-issue-write.py prints for a file in
the log-store; that form is read as a local path on ned-box and refused
elsewhere with the ssh command to run instead, its arguments quoted.

Does not handle: two handlers changing one file at the same time (that
design's open question 2): the file is read, changed and replaced whole, so the later
writer's replacement drops the earlier writer's lines.

Failures: a user-alert that cannot be written, after the file was changed, is
printed to stderr as FAILED: with the entries left without one and what to do,
and the program exits 1. Otherwise, a value holding a line break, a refused change, a missing file or entry, a file that cannot be
read or written, an upstream entry's file that cannot be read, another file of the GHI-MD that cannot be read, a log-store directory that cannot be listed, or a second agent that cannot be run, exits nonzero, runs past
SECOND_AGENT_TIMEOUT_SECONDS or ends its reply with a line other than
"VERDICT: agrees" or "VERDICT: disagrees", is printed to stderr with what to
do, and the program exits 1 without changing the file. Exit 0: done.
"""

import argparse
import datetime
import importlib.util
import os
import re
import shlex
import socket
import subprocess
import sys
import tempfile
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parent.parent


def _load(module_name, relative_path):
    specification = importlib.util.spec_from_file_location(module_name, REPOSITORY_ROOT / relative_path)
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


command_line_prefix = _load(
    "claude_code_headless_run_command_line_prefix_with_no_connectors_and_explicit_permission_mode_common",
    "nn-systems/general-tools/claude-code-headless-run-command-line-prefix-with-no-connectors-and-explicit-permission-mode-common.py")

ghi_issue_write = _load("ghi_issue_write", "scripts/ghi-issue-write.py")

user_alerts = _load(
    "user_alerts_pending_and_claimed_files_write_claim_release_and_delete_common",
    "nn-systems/general-tools/user-alerts-pending-and-claimed-files-write-claim-release-and-delete-common.py")

launched_agent_session = _load(
    "handoff_supervisor_launched_agent_session_environment_variable_names_common",
    "nn-systems/handoff/handoff-supervisor-launched-agent-session-environment-variable-names-common.py")
HANDOFF_SUPERVISOR_WORKING_DIRECTORY_ENVIRONMENT_VARIABLE = (
    launched_agent_session.HANDOFF_SUPERVISOR_WORKING_DIRECTORY_ENVIRONMENT_VARIABLE)
USER_ALERT_AGENT_SEAT_WHEN_ALERT_NAMES_NONE = user_alerts.USER_ALERT_AGENT_SEAT_WHEN_ALERT_NAMES_NONE
# The subcommands that can mark an entry as needing the user.
MARKING_COMMANDS = ("attempt", "second-agent-verdict", "needs-the-user")
INSTRUCTIONS = "docs/agents/queue/proposed-improvements-or-changes-file-reviewer-entries-settling-subagent-instructions.md"

SECOND_AGENT_PROMPT = "docs/agents/queue/proposed-improvements-or-changes-file-entry-not-worth-doing-second-agent-prompt.md"
SECOND_AGENT_MODEL = "claude-opus-5-5"
SECOND_AGENT_EFFORT = "high"
# Bash is kept because the agent reads its sources with git, gh and ssh. --tools is the whole tool set,
# so the agent has no Agent, Write or Edit tool; --allowedTools alone would leave them.
SECOND_AGENT_TOOLS = "Bash,Read,Grep,Glob"
# Reading one entry's few sources; well past what that takes, short of a stuck run holding the handler for long.
SECOND_AGENT_TIMEOUT_SECONDS = 1800
# The repository's hooks are written for interactive agent-sessions and can block or redirect a headless one.
SECOND_AGENT_SETTINGS = {"disableAllHooks": True}
SECOND_AGENT_VERDICTS = {"VERDICT: agrees": True, "VERDICT: disagrees": False}
MAXIMUM_ATTEMPTS = 3

ENTRY_HEADING_PATTERN = re.compile(r"^## (E\d+)\b")
# Only a heading of level one or two ends an entry: an entry's body may hold a
# hashtag line or a lower heading.
ENTRY_ENDING_HEADING_PATTERN = re.compile(r"^#{1,2} ")
STATE_LINE_OPENING = "State:"
ATTEMPT_LINE_PATTERN = re.compile(r"^Attempt[ :]")
# An Attempt line's sources follow the last ATTEMPT_SOURCES_DELIMITER, so a --found that holds the delimiter
# never reaches the second agent.
ATTEMPT_SOURCES_DELIMITER = " — sources read: "
ATTEMPT_SOURCES_SEPARATOR = "; "
SECOND_AGENT_LINE_OPENING = "Second agent:"
SECOND_AGENT_AGREES_OPENING = "Second agent: agrees"
USER_RULING_LINE_OPENING = "User-ruling"
OPEN_STATE_OPENING = "State: open"

LOG_STORE_HOST = "nedlern@ned-box"
LOG_STORE_HOSTNAME = "ned-box"
GHI_GUIDE_AGENT_LOG_STORE_DIRECTORY = ghi_issue_write.GHI_GUIDE_AGENT_LOG_STORE_DIRECTORY
FILE_NAME_INFIX = ghi_issue_write.PROPOSED_IMPROVEMENTS_OR_CHANGES_INFIX
GHI_LINK_PATTERN = re.compile(r"https://github\.com/[^/\s]+/[^/\s]+/issues/\d+")

SETTLED_KINDS = {
    "not-worth-doing": "not worth doing",
    "done": "done",
    "new-ghi": "new GHI filed",
}
NEEDS_THE_USER_REASONS = {
    "cold-read-document": "the change would alter a document the cold-read skill sends to a cold-read-full-run, in a way its step 9 sends to the user",
    "user-ruling-change": "a question whether a user-ruling should change",
    "three-attempts": "still open after {attempts} attempts",
}
DONE_STATE_OPENING = f"State: settled, {SETTLED_KINDS['done']} — "
# Not in SETTLED_KINDS, so `settle --kind` cannot claim a ruling the user never made.
USER_RULING_SETTLED_KIND = "by the user's ruling"
NEEDS_THE_USER_STATE_OPENING = "State: needs the user"
USER_RULING_STATES = ("open", "settled")
ATTEMPT_OUTCOMES = ("settles", "not-worth-doing", "goes-to-the-user", "left-open")
THIRD_ATTEMPT_DISAGREEMENT_WHY = "the last attempt found the entry not worth doing, and the second agent disagreed"


class Refused(Exception):
    pass


class Failed(Exception):
    pass


def now() -> str:
    """The time a line carries. A function so a test can fix it."""
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%MZ")


def refuse_unless_on_ned_box(what: str, argv):
    if socket.gethostname().split(".")[0] != LOG_STORE_HOSTNAME:
        remote = shlex.join(["cd", "/home/nedlern/Projects/nedsnodes"]) + " && " + shlex.join(
            ["python3", "scripts/proposed-improvements-or-changes-file-entry-state-attempt-and-second-agent-verdict-lines-write.py", *argv])
        raise Refused(
            f"{what} in the log-store on ned-box, and this machine is not ned-box, so nothing was changed.\n"
            "Run the same command on ned-box, exactly as printed here, quoting included:\n"
            f"ssh {LOG_STORE_HOST} {shlex.quote(remote)}")


def local_path(named: str, argv) -> Path:
    if named.startswith(LOG_STORE_HOST + ":"):
        refuse_unless_on_ned_box(f"{named} is", argv)
        return Path(named[len(LOG_STORE_HOST) + 1:])
    return Path(named)


def ghi_md_file_names(ghi_md_name: str, directory: str):
    """The names of the GHI-MD's files in `directory`, oldest name first."""
    number = re.match(r"(\d+)-", ghi_md_name)
    bare = ghi_md_name[number.end():] if number else ghi_md_name
    leading = re.escape(number.group(0)) if number else r"\d+-"
    pattern = re.compile(f"(?:{leading})?{re.escape(bare + FILE_NAME_INFIX)}.*\\.md")
    try:
        names = sorted(name for name in os.listdir(directory) if pattern.fullmatch(name))
    except OSError as failure:
        raise Failed(f"the directory {directory} could not be listed: {failure}")
    if not names:
        raise Refused(
            f"No file in {directory} is named after GHI-MD {ghi_md_name}.\n"
            "Give the file you were given itself, or the GHI-MD's name as the part of that file's name before "
            f"{FILE_NAME_INFIX}, without its directory.")
    numbers = sorted({match.group(1) for match in (re.match(r"(\d+)-", name) for name in names) if match}, key=int)
    if len(numbers) > 1:
        # Two GHIs can share a slug; their files must not be read as one GHI-MD's.
        raise Refused(
            f"GHI-MD name {ghi_md_name} has no GHI number, and files of GHIs {', '.join(numbers)} in "
            f"{directory} carry it, so nothing was shown or changed.\n"
            f"Give the name with its GHI number, such as {numbers[0]}-{bare}.")
    return names


def entry_spans(lines):
    """{entry id: (index of its heading, index after its last line)}."""
    spans, current, start = {}, None, 0
    for index, line in enumerate(lines):
        if ENTRY_ENDING_HEADING_PATTERN.match(line):
            if current is not None:
                spans[current] = (start, index)
                current = None
            match = ENTRY_HEADING_PATTERN.match(line)
            if match:
                current, start = match.group(1), index
    if current is not None:
        spans[current] = (start, len(lines))
    return spans


def entry_lines(lines, spans, entry):
    if entry not in spans:
        raise Refused(f"The file has no entry {entry}; its entries are: {', '.join(spans) or 'none'}. Nothing was changed.")
    start, end = spans[entry]
    return lines[start:end]


def attempts_since_user_ruling(block) -> int:
    count = 0
    for line in block:
        if line.startswith(USER_RULING_LINE_OPENING):
            count = 0
        elif ATTEMPT_LINE_PATTERN.match(line):
            count += 1
    return count


def last_index(block, test):
    found = -1
    for index, line in enumerate(block):
        if test(line):
            found = index
    return found


def last_verdict_answers_last_attempt(block):
    """(the last "Second agent:" line, or None, and whether it follows the last Attempt line)."""
    verdict = last_index(block, lambda line: line.startswith(SECOND_AGENT_LINE_OPENING))
    attempt = last_index(block, lambda line: bool(ATTEMPT_LINE_PATTERN.match(line)))
    if verdict < 0:
        return None, False
    return block[verdict], verdict > attempt


def state_line(block):
    for line in block:
        if line.startswith(STATE_LINE_OPENING):
            return line
    return None


def insertion_index(lines, spans, entry) -> int:
    start, end = spans[entry]
    while end > start + 1 and not lines[end - 1].strip():
        end -= 1
    return end


def replace_state(lines, spans, entry, new_state):
    start, end = spans[entry]
    for index in range(start, end):
        if lines[index].startswith(STATE_LINE_OPENING):
            lines[index] = new_state
            return
    lines.insert(insertion_index(lines, spans, entry), new_state)


def refuse_unless_open(block, entry):
    state = state_line(block)
    if state is not None and not state.startswith(OPEN_STATE_OPENING):
        raise Refused(
            f"Entry {entry} is not open ({state}), so nothing was changed.\n"
            "A settled entry is never changed. An entry that needs the user waits for his ruling, which the agent-seat that brought it to him records with this program's user-ruling subcommand.")


def is_open(block) -> bool:
    state = state_line(block)
    return state is None or state.startswith(OPEN_STATE_OPENING)


def ghi_md_file_names_beside(path: Path, what: str):
    """The names of the files of `path`'s GHI-MD in its directory; `what` says what a refusal left undone."""
    if FILE_NAME_INFIX not in path.name:
        raise Refused(
            f"{path.name} holds no {FILE_NAME_INFIX}, so its GHI-MD's other files cannot be found and {what}.\n"
            "Give the proposed-improvements-or-changes-file as scripts/ghi-issue-write.py named it.")
    return ghi_md_file_names(path.name.split(FILE_NAME_INFIX)[0], str(path.parent))


def open_entries_of_ghi_md(path: Path, lines):
    """{(file name, entry id)} of every open entry in the GHI-MD's files beside `path`, reading `path` as `lines`."""
    found = set()
    for name in ghi_md_file_names_beside(path, "no attempt was recorded"):
        if name == path.name:
            text_lines = lines
        else:
            try:
                text_lines = (path.parent / name).read_text(encoding="utf-8").splitlines()
            except OSError as failure:
                raise Failed(f"{name} in {path.parent}, another file of the same GHI-MD, could not be read: {failure}")
        spans = entry_spans(text_lines)
        found |= {(name, entry) for entry in spans if is_open(entry_lines(text_lines, spans, entry))}
    return found


def another_entry_is_open(path: Path, lines, entry) -> bool:
    return bool(open_entries_of_ghi_md(path, lines) - {(path.name, entry)})


def add_attempt(lines, entries, by, found, sources, outcome, path: Path):
    """(the lines, and the entries the attempt marked as needing the user)."""
    spans = entry_spans(lines)
    for entry in entries:
        block = entry_lines(lines, spans, entry)
        refuse_unless_open(block, entry)
        count = attempts_since_user_ruling(block)
        if count > MAXIMUM_ATTEMPTS or (count == MAXIMUM_ATTEMPTS and another_entry_is_open(path, lines, entry)):
            raise Refused(
                f"Entry {entry} already has {count} attempts since the user last decided on it, so no attempt was recorded under any entry named.\n"
                f"Rule 4 of GHI 1132 allows no more{'' if count > MAXIMUM_ATTEMPTS else ' while another entry of the GHI-MD is open'}; the entry goes to the user:\n"
                f"run this program's needs-the-user subcommand on {entry} with --because three-attempts.")
    listed = ATTEMPT_SOURCES_SEPARATOR.join(sources)
    for entry in sorted(entries, key=lambda name: spans[name][0], reverse=True):
        number = attempts_since_user_ruling(entry_lines(lines, spans, entry)) + 1
        lines.insert(insertion_index(lines, spans, entry),
                     f"Attempt {number} — {by}, {now()}: {found}{ATTEMPT_SOURCES_DELIMITER}{listed}")
    if outcome != "left-open":
        return lines, []
    spans = entry_spans(lines)
    counts = {entry: attempts_since_user_ruling(entry_lines(lines, spans, entry)) for entry in entries}
    # Decided for every entry before any is marked, so that marking one does not leave another the only one open.
    marked = [entry for entry in entries
              if counts[entry] > MAXIMUM_ATTEMPTS
              or (counts[entry] == MAXIMUM_ATTEMPTS and another_entry_is_open(path, lines, entry))]
    for entry in marked:
        lines = needs_the_user(lines, entry, "three-attempts", by, found)
    return lines, marked


def second_agent_input(lines, entry, sources) -> str:
    spans = entry_spans(lines)
    block = entry_lines(lines, spans, entry)
    kept = [line for line in block
            if not line.startswith(STATE_LINE_OPENING)
            and not ATTEMPT_LINE_PATTERN.match(line)
            and not line.startswith(SECOND_AGENT_LINE_OPENING)]
    prompt = (REPOSITORY_ROOT / SECOND_AGENT_PROMPT).read_text(encoding="utf-8")
    listed = "\n".join(f"- {source}" for source in sources)
    return (f"{prompt.rstrip()}\n\n## The entry\n\n" + "\n".join(kept).strip()
            + f"\n\n## The sources the handler cites\n\n{listed}\n")


def refuse_unless_an_attempt_awaits_a_verdict(lines, entry):
    """The sources on the Attempt line that awaits a verdict."""
    block = entry_lines(lines, entry_spans(lines), entry)
    refuse_unless_open(block, entry)
    attempt = last_index(block, lambda line: bool(ATTEMPT_LINE_PATTERN.match(line)))
    verdict = last_index(block, lambda line: line.startswith(SECOND_AGENT_LINE_OPENING))
    if attempt < 0 or verdict > attempt:
        raise Refused(
            f"Entry {entry} has no Attempt line after its last verdict, so no second agent was run and no verdict was recorded.\n"
            "Each verdict answers one attempt: record the attempt that shows the entry is not worth doing with the attempt subcommand first,\n"
            "then run the second-agent-verdict subcommand again.")
    delimiter = block[attempt].rfind(ATTEMPT_SOURCES_DELIMITER)
    if delimiter < 0:
        raise Refused(
            f"Entry {entry}'s last Attempt line names no sources, so no second agent was run and no verdict was recorded.\n"
            "The second agent judges from the sources the attempt read: record a new attempt with the attempt subcommand, naming each source with --source,\n"
            "then run the second-agent-verdict subcommand again.")
    return block[attempt][delimiter + len(ATTEMPT_SOURCES_DELIMITER):].split(ATTEMPT_SOURCES_SEPARATOR)


class SecondAgentFailed(Exception):
    pass


def second_agent_reply(prompt) -> str:
    command = [*command_line_prefix.claude_code_headless_run_command_line_prefix_build(
                   "dontAsk", caller_claude_code_session_settings=SECOND_AGENT_SETTINGS),
               "--model", SECOND_AGENT_MODEL, "--effort", SECOND_AGENT_EFFORT,
               "--output-format", "text", "--tools", SECOND_AGENT_TOOLS, "--allowedTools", SECOND_AGENT_TOOLS]
    try:
        # The prompt goes on stdin: variadic --allowedTools can swallow a trailing positional argument.
        result = subprocess.run(command, input=prompt, cwd=REPOSITORY_ROOT, capture_output=True, text=True,
                                timeout=SECOND_AGENT_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired:
        raise SecondAgentFailed(f"the second agent did not finish within {SECOND_AGENT_TIMEOUT_SECONDS} s.")
    except OSError as failure:
        raise SecondAgentFailed(f"`claude` could not be started: {failure}.\n"
                                "If `claude` is missing on this machine, report that.")
    if result.returncode:
        raise SecondAgentFailed(
            f"`claude -p` exited {result.returncode}.\nIts stderr: {result.stderr.strip()[-2000:] or 'empty'}\n"
            f"Its stdout: {result.stdout.strip()[-2000:] or 'empty'}\n"
            "If it says `claude` is logged out or a usage limit is reached, report what it said.")
    return result.stdout


def verdict_of(reply) -> bool:
    lines = [line.strip() for line in reply.splitlines() if line.strip()]
    if not lines or lines[-1] not in SECOND_AGENT_VERDICTS:
        raise SecondAgentFailed(
            "the second agent's reply does not end with the line \"VERDICT: agrees\" or \"VERDICT: disagrees\".\n"
            f"Its reply: {reply.strip()[-4000:] or 'empty'}")
    return SECOND_AGENT_VERDICTS[lines[-1]]


def add_verdict(lines, entry, agrees, who, by):
    """(the lines, and whether the verdict marked the entry as needing the user); an agreement settles the entry."""
    spans = entry_spans(lines)
    refuse_unless_an_attempt_awaits_a_verdict(lines, entry)
    block = entry_lines(lines, spans, entry)
    # Attempt numbers start again after a User-ruling line, so the cited attempt is named with its author and time too.
    answered = block[last_index(block, lambda line: bool(ATTEMPT_LINE_PATTERN.match(line)))].partition(": ")[0]
    word = "agrees" if agrees else "disagrees"
    lines.insert(insertion_index(lines, spans, entry),
                 f"Second agent: {word} that it is not worth doing, {who}, {now()}")
    if agrees:
        return settle(lines, entry, "not-worth-doing", by,
                      f"the second agent agreed with {answered}, whose line gives the reasons"), False
    if attempts_since_user_ruling(entry_lines(lines, entry_spans(lines), entry)) < MAXIMUM_ATTEMPTS:
        return lines, False
    return needs_the_user(lines, entry, "three-attempts", by, THIRD_ATTEMPT_DISAGREEMENT_WHY), True


def settle(lines, entry, kind, by, how):
    spans = entry_spans(lines)
    block = entry_lines(lines, spans, entry)
    refuse_unless_open(block, entry)
    if kind == "not-worth-doing":
        verdict, answers = last_verdict_answers_last_attempt(block)
        if verdict is None or not answers or not verdict.startswith(SECOND_AGENT_AGREES_OPENING):
            raise Refused(
                f"Entry {entry} cannot be settled as not worth doing: its last attempt has no agreement from a second agent, so the entry stays open.\n"
                "Rule 5 of GHI 1132 needs that agreement: run the second-agent-verdict subcommand on the entry.")
    if kind == "new-ghi" and not GHI_LINK_PATTERN.search(how):
        raise Refused(
            f"Entry {entry} was not settled as new GHI filed: --how holds no GHI link, such as https://github.com/<owner>/<repository>/issues/<number>, so nothing was changed.\n"
            "Give the link of the GHI you filed in --how.\n"
            "If you have not filed the GHI yet, file it first, as .claude/skills/ghi-write/SKILL.md says.")
    replace_state(lines, spans, entry, f"State: settled, {SETTLED_KINDS[kind]} — {by}, {now()}: {how}")
    return lines


def settle_by_upstream_entry(lines, path: Path, named: str, entry, by, settled_by, argv):
    """settle --settled-by: an attempt under the entry and its done State line, citing the upstream entry."""
    if len(settled_by) == 2:
        upstream_file, upstream = settled_by
        try:
            upstream_lines = local_path(upstream_file, argv).read_text(encoding="utf-8").splitlines()
        except OSError as failure:
            raise Failed(f"{upstream_file}, the file of upstream entry {upstream}, could not be read: {failure}")
        cited = f"{upstream} of {upstream_file}"
    else:
        upstream_file, upstream, upstream_lines, cited = named, settled_by[0], lines, settled_by[0]
    spans = entry_spans(upstream_lines)
    if upstream not in spans:
        raise Refused(f"{upstream_file} has no entry {upstream}; its entries are: {', '.join(spans) or 'none'}. Nothing was changed.\n"
                      "Give the upstream entry's file before the entry when the entry is in another file.")
    upstream_state = state_line(entry_lines(upstream_lines, spans, upstream))
    if upstream_state is None or not upstream_state.startswith(DONE_STATE_OPENING):
        raise Refused(
            f"Upstream entry {cited} is not settled as done ({upstream_state or 'no State line'}), so entry {entry} was not settled and nothing was changed.\n"
            "Only a change that was made settles another entry: settle the upstream entry as done first, or work on this entry in its own attempt.")
    cites = f"settled by the change that settled {cited}: {upstream_state}"
    lines, _ = add_attempt(lines, [entry], by, cites, [upstream_file], "settles", path)
    return settle(lines, entry, "done", by, cites)


def needs_the_user(lines, entry, because, by, why):
    spans = entry_spans(lines)
    block = entry_lines(lines, spans, entry)
    refuse_unless_open(block, entry)
    if because == "three-attempts" and attempts_since_user_ruling(block) < MAXIMUM_ATTEMPTS:
        raise Refused(
            f"Entry {entry} has {attempts_since_user_ruling(block)} attempts since the user last decided on it, fewer than {MAXIMUM_ATTEMPTS}, so it was not marked.\n"
            "Record another attempt with the attempt subcommand, or name the reason rule 7 of GHI 1132 sends it to the user with --because.")
    reason = NEEDS_THE_USER_REASONS[because].format(attempts=attempts_since_user_ruling(block))
    replace_state(lines, spans, entry, f"State: needs the user — {by}, {now()}: {reason}; {why}")
    return lines


def record_user_ruling(lines, entry, where, words, state, by):
    spans = entry_spans(lines)
    current = state_line(entry_lines(lines, spans, entry))
    if current is None or not current.startswith(NEEDS_THE_USER_STATE_OPENING):
        raise Refused(
            f"Entry {entry} does not need the user ({current or 'no State line'}), so no ruling was recorded and nothing was changed.\n"
            "A User-ruling line goes only under an entry whose State line says \"needs the user\".\n"
            "If you meant another entry, run `show` on the file and give that entry's id.")
    time = now()
    new_state = "State: open" if state == "open" else f"State: settled, {USER_RULING_SETTLED_KIND} — {by}, {time}: {where}"
    lines.insert(insertion_index(lines, spans, entry), f"{USER_RULING_LINE_OPENING} — the user, {time}, {where}: {words}")
    replace_state(lines, spans, entry, new_state)
    return lines


def show(lines) -> str:
    spans = entry_spans(lines)
    out = []
    for entry in spans:
        block = entry_lines(lines, spans, entry)
        verdict, answers = last_verdict_answers_last_attempt(block)
        out.append(f"{entry}: {state_line(block) or 'no State line'}; attempts since the user last decided: "
                   f"{attempts_since_user_ruling(block)} of {MAXIMUM_ATTEMPTS}; last verdict: "
                   f"{(verdict + (' (answers the last attempt)' if answers else ' (an attempt came after it)')) if verdict else 'none'}")
    return "\n".join(out) or "The file has no entries."


def show_files(directory: Path, names, shown_as) -> str:
    """show of each file in `directory` named, under its path as `shown_as` gives it."""
    out = []
    for name in names:
        try:
            text = (directory / name).read_text(encoding="utf-8")
        except OSError as failure:
            raise Failed(f"{name} in {directory} could not be read: {failure}")
        out.append(f"{shown_as(name)}\n{show(text.splitlines())}\n")
    return "\n".join(out)


def marking_agent_seat():
    """The agent-seat whose handler marks entries here: the name of the agent-home this agent-session was launched
    in, or None when it was launched in no agent-home."""
    launched_in = os.environ.get(HANDOFF_SUPERVISOR_WORKING_DIRECTORY_ENVIRONMENT_VARIABLE, "")
    if not launched_in or Path(launched_in).parent != Path.home() / user_alerts.AGENTS_RELATIVE_TO_HOME:
        return None
    seat = Path(launched_in).name
    if not user_alerts.agent_home_on_ned_box_found(seat):
        raise Refused(
            f"This agent-session was launched in {launched_in}, which is not an agent-home on this machine, so no user-alert could name agent-seat {seat} and nothing was changed.\n"
            f"Run this program on ned-box, from an agent-session of an agent-seat whose agent-home is there.")
    return seat


def user_alerts_write(path: Path, lines, entries, seat):
    """Write one user-alert for each entry marked; return the entries whose alert could not be written, with why."""
    spans = entry_spans(lines)
    unwritten = []
    for entry in entries:
        state = state_line(entry_lines(lines, spans, entry))
        try:
            user_alerts.user_alert_write_to_pending(
                f"Entry {entry} of a proposed-improvements-or-changes-file needs the user",
                f"{LOG_STORE_HOST}:{path.resolve()}, entry {entry}: {state}",
                f"The agent-seat named here brings the entry to the user in its approval-walk, as section 5 of {INSTRUCTIONS} says, "
                f"and records his ruling with the user-ruling subcommand of {Path(__file__).resolve().relative_to(REPOSITORY_ROOT)}.",
                claiming_agent_seat_name=seat)
        except (OSError, ValueError) as failure:
            unwritten.append((entry, failure))
    return unwritten


def write_replacing(path: Path, lines, ending: str):
    descriptor, temporary = tempfile.mkstemp(dir=str(path.parent), prefix=f".{path.name}.")
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as written:
            written.write("\n".join(lines) + ending)
        # mkstemp makes the file readable by its owner only; keep the mode the file had.
        os.chmod(temporary, path.stat().st_mode & 0o7777)
        os.replace(temporary, path)
    except BaseException:
        Path(temporary).unlink()
        raise


def parser():
    top = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    commands = top.add_subparsers(dest="command", required=True)
    command = commands.add_parser("show")
    command.add_argument("file", metavar="file-or-GHI-MD-name")
    command = commands.add_parser("attempt")
    command.add_argument("file")
    command.add_argument("entries", nargs="+")
    command.add_argument("--by", required=True)
    command.add_argument("--found", required=True)
    command.add_argument("--outcome", required=True, choices=ATTEMPT_OUTCOMES,
                         help="settles: you settle the entry next, as done or new GHI filed; not-worth-doing: you run "
                              "second-agent-verdict next; goes-to-the-user: you run needs-the-user next; left-open: the "
                              "entry stays open, such as one worth doing but not doable now")
    command.add_argument("--source", action="append", required=True,
                         help="one source the attempt read: a path in this repository, a log-store path, PR <number> or GHI <number>")
    command = commands.add_parser("second-agent-verdict")
    command.add_argument("file")
    command.add_argument("entry")
    command.add_argument("--by", required=True)
    command = commands.add_parser("settle")
    command.add_argument("file")
    command.add_argument("entry")
    command.add_argument("--kind", choices=sorted(SETTLED_KINDS))
    command.add_argument("--by", required=True)
    command.add_argument("--how")
    command.add_argument("--settled-by", nargs="+", metavar="FILE-OR-ENTRY",
                         help="[<file>] <upstream entry>, in place of --kind and --how: the upstream entry whose change "
                              "settled this one, after its file when that is not the given file")
    command = commands.add_parser("needs-the-user")
    command.add_argument("file")
    command.add_argument("entry")
    command.add_argument("--because", required=True, choices=sorted(NEEDS_THE_USER_REASONS))
    command.add_argument("--by", required=True)
    command.add_argument("--why", required=True)
    command = commands.add_parser("user-ruling")
    command.add_argument("file")
    command.add_argument("entry")
    command.add_argument("--where", required=True, help="where the user ruled, such as an approval-walk's name and item")
    command.add_argument("--words", required=True, help="the user's words")
    command.add_argument("--state", required=True, choices=USER_RULING_STATES)
    command.add_argument("--by", required=True)
    return top


def main(argv=None) -> int:
    arguments = parser().parse_args(argv)
    try:
        for name in ("found", "how", "why", "by", "source", "where", "words", "settled_by"):
            value = getattr(arguments, name, None)
            if value is not None and any("\n" in part or "\r" in part
                                         for part in (value if isinstance(value, list) else [value])):
                raise Refused(
                    f"--{name.replace('_', '-')} holds a line break, so nothing was changed: each value is written as part of one line,\n"
                    "and a second line could be read as a State, Attempt or Second agent line. Give it on one line.")
        for name in ("where", "words"):
            value = getattr(arguments, name, None)
            if value is not None and not value.strip():
                raise Refused(f"--{name} is empty, so nothing was changed: the User-ruling line needs it. Give it on one line.")
        for source in getattr(arguments, "source", None) or []:
            if not source.strip() or ATTEMPT_SOURCES_SEPARATOR.strip() in source:
                raise Refused(
                    f"--source {source!r} is empty or holds \"{ATTEMPT_SOURCES_SEPARATOR.strip()}\", which separates the sources on the Attempt line, so nothing was changed.\n"
                    "Give each source in its own --source, without that character.")
        if arguments.command == "settle":
            if arguments.settled_by is None and (arguments.kind is None or arguments.how is None):
                raise Refused("settle needs both --kind and --how, or --settled-by in place of both, so nothing was changed.")
            if arguments.settled_by is not None and (arguments.kind is not None or arguments.how is not None):
                raise Refused("--settled-by settles the entry as the upstream entry was settled, so it takes no --kind or --how; nothing was changed.\n"
                              "Give --settled-by alone, or --kind and --how alone.")
            if arguments.settled_by is not None and len(arguments.settled_by) > 2:
                raise Refused(f"--settled-by takes the upstream entry, after its file when it is in another file, and was given "
                              f"{len(arguments.settled_by)} values, so nothing was changed.\n"
                              "Give it as --settled-by E1, or --settled-by <that file> E1.")
        argv = sys.argv[1:] if argv is None else argv
        # A GHI-MD's name holds no directory and no extension.
        if arguments.command == "show" and "/" not in arguments.file and not arguments.file.endswith(".md"):
            refuse_unless_on_ned_box(f"The files of GHI-MD {arguments.file} are", argv)
            print(show_files(Path(GHI_GUIDE_AGENT_LOG_STORE_DIRECTORY),
                             ghi_md_file_names(arguments.file, GHI_GUIDE_AGENT_LOG_STORE_DIRECTORY),
                             lambda name: f"{LOG_STORE_HOST}:{GHI_GUIDE_AGENT_LOG_STORE_DIRECTORY}/{name}"))
            return 0
        path = local_path(arguments.file, argv)
        if arguments.command == "show":
            # So a missing file is reported as missing, not as a GHI-MD with no files.
            path.stat()
            if path.resolve().parent == Path(GHI_GUIDE_AGENT_LOG_STORE_DIRECTORY).resolve():
                print(show_files(path.resolve().parent, ghi_md_file_names_beside(path.resolve(), "nothing was shown"),
                                 lambda name: f"{LOG_STORE_HOST}:{GHI_GUIDE_AGENT_LOG_STORE_DIRECTORY}/{name}"))
            else:
                print(show_files(path.parent, [path.name], lambda name: str(path)))
            return 0
        seat = marking_agent_seat() if arguments.command in MARKING_COMMANDS else None
        marked = []
        text = path.read_text(encoding="utf-8")
        ending = "\n" if text.endswith("\n") else ""
        lines = text.splitlines()
        if arguments.command == "attempt":
            lines, marked = add_attempt(lines, arguments.entries, arguments.by, arguments.found, arguments.source,
                                        arguments.outcome, path)
        elif arguments.command == "second-agent-verdict":
            sources = refuse_unless_an_attempt_awaits_a_verdict(lines, arguments.entry)
            reply = second_agent_reply(second_agent_input(lines, arguments.entry, sources))
            agrees = verdict_of(reply)
            print(reply.rstrip())
            # The agent runs for minutes; the file may have changed meanwhile.
            text = path.read_text(encoding="utf-8")
            ending = "\n" if text.endswith("\n") else ""
            lines, marked_for_the_user = add_verdict(
                text.splitlines(), arguments.entry, agrees,
                f"{SECOND_AGENT_MODEL} run through `claude -p` for {arguments.by}", arguments.by)
            marked = [arguments.entry] if marked_for_the_user else []
        elif arguments.command == "settle" and arguments.settled_by is not None:
            lines = settle_by_upstream_entry(lines, path, arguments.file, arguments.entry, arguments.by,
                                             arguments.settled_by, argv)
        elif arguments.command == "settle":
            lines = settle(lines, arguments.entry, arguments.kind, arguments.by, arguments.how)
        elif arguments.command == "user-ruling":
            lines = record_user_ruling(lines, arguments.entry, arguments.where, arguments.words, arguments.state, arguments.by)
        else:
            lines = needs_the_user(lines, arguments.entry, arguments.because, arguments.by, arguments.why)
            marked = [arguments.entry]
        write_replacing(path, lines, ending)
    except Refused as refusal:
        print(f"REFUSED: {refusal}", file=sys.stderr)
        return 1
    except SecondAgentFailed as failure:
        print(f"FAILED: {failure}\nNo verdict was recorded, and the file was left as it was.", file=sys.stderr)
        return 1
    except Failed as failure:
        print(f"FAILED: {failure}\nNothing was changed.", file=sys.stderr)
        return 1
    except OSError as failure:
        print(f"FAILED: {arguments.file} could not be read or written, and was left as it was: {failure}\n"
              "If the path is wrong, run again with the path the file is at.", file=sys.stderr)
        return 1
    unwritten = user_alerts_write(path, lines, marked, seat)
    print(show(lines))
    if arguments.command == "attempt":
        spans = entry_spans(lines)
        for entry in arguments.entries:
            count = attempts_since_user_ruling(entry_lines(lines, spans, entry))
            if entry in marked:
                print(f"Attempt {count} left entry {entry} open, the last attempt rule 4 of GHI 1132 allows, so the entry was marked as needing the user.\n"
                      "In your report, say what the user must decide, from what the attempts found.")
            elif count >= MAXIMUM_ATTEMPTS and arguments.outcome == "left-open":
                print(f"Entry {entry} now has {count} attempts, and no other entry of the GHI-MD is open, so it gets a fourth attempt.\n"
                      "A fourth attempt whose outcome is left-open marks it as needing the user.")
            elif count >= MAXIMUM_ATTEMPTS and arguments.outcome == "not-worth-doing":
                print(f"Entry {entry} now has {count} attempts: run the second-agent-verdict subcommand on it.\n"
                      "If the second agent disagrees, that subcommand marks the entry as needing the user.")
    if arguments.command == "second-agent-verdict" and agrees:
        print(f"The second agent agreed, so entry {arguments.entry} was settled as not worth doing.")
    if arguments.command == "second-agent-verdict" and marked_for_the_user:
        print(f"The second agent disagreed on attempt {MAXIMUM_ATTEMPTS} of entry {arguments.entry}, the last attempt rule 4 of GHI 1132 allows, so the entry was marked as needing the user.\n"
              "In your report, say what the user must decide, from the second agent's reasons above.")
    if unwritten:
        for entry, failure in unwritten:
            print(f"FAILED: entry {entry} was marked as needing the user, but no user-alert was written for it: {failure}", file=sys.stderr)
        print("The file was changed as printed above. Put this in your report, so that the agent-seat that dispatched you brings each such entry to the user itself.",
              file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
