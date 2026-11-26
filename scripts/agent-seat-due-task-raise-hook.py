#!/usr/bin/env python3
"""Raise an agent-seat's own tasks when what they wait on is done, at the end of each turn,
and keep an idle agent-seat from stopping with nothing for the user to answer.

Wired as a Stop hook in .claude/settings.json.

WHAT A TASK IS. A Claude Code task is the file
`~/.claude/tasks/<CLAUDE_CODE_TASK_LIST_ID>/<id>.json`, with the keys
activeForm, blockedBy, blocks, description, id, metadata, status and subject
(activeForm and metadata are optional, and a few files carry `owner`). An
agent-seat's list id is `nedsnodes-<seat>-tasks`, read from the environment
variable CLAUDE_CODE_TASK_LIST_ID, which the hook inherits from the session;
a session without one prints nothing. A list whose directory does not exist
yet holds no tasks, and its session can still get the next-action prompt.
Only `*.json` files are read, because
the list directory also holds the harness's `.lock`. Task files are never
written.

WHAT MAKES A TASK DUE. Two optional keys in a task's `metadata`:

  prerequisites  a non-empty list of conditions, each {"pr_merged": <number>}
                 or {"issue_closed": <number>} on the repository
                 nedsnodes/nedsnodes, or
                 {"approval_walk_item_decided": {"approval_walk_minutes_file_path":
                 <absolute path of a docs/walk/<name>-minutes.md file>,
                 "approval_walk_item_heading":
                 <the item's heading in the walk-document>}}. Met means every
                 condition is met. An empty list is never met: "every one of
                 nothing" would raise a task nobody set a prerequisite on. A
                 list this hook cannot read is never met, and the hook names
                 its fault to the agent once, as RAISED ONCE says, so the task
                 is not held in silence for good.
  approval       a string, not blank, saying why the task needs no
                 decision from the user. Any other value is no record.

APPROVAL-WALK ITEMS. An item is named by its heading, because its number and
count can change while the walk runs. The walk-document is the walk-minutes'
path with `-minutes.md` replaced by `.md`. Its item headings are compared with
the given heading as the answer program's heading_title reads both, so a
running count, a deferred note, backticks, spaces and case do not matter. The
item is decided when the answer program's
approval_walk_minutes_read_returning_decided_item_numbers counts its number
as decided; the hook asks that function rather than keeping a rule of its own,
so it never disagrees with the walk. A walk-minutes file that does not exist
is not decided, since the walk may not have written it yet; nor is an item not
yet numbered. A walk-document that
does not exist, or that holds no item with the heading, or more than one, is
a fault the hook names as it names an unreadable list: the walk-document
holds the item before its heading can be named, so its absence means a wrong
path. The files are read on this machine only, and each hook execution reads
them afresh; only its parse of a text it has already parsed is reused.

An open task (status pending or in_progress) is raised when its
prerequisites are met, and only when every task in its blockedBy is
completed. A blockedBy id with no task file does not hold the task: a deleted
task can never complete, and holding on it would silence the task for good.
A blocker file that exists but cannot be read does hold it, because its
status is unknown. An open task with no prerequisites, or one already
raised for its current prerequisites, whose blockedBy is a non-empty list of
tasks that all exist and are completed, is raised too: an agent told to
record a prerequisite task with addBlockedBy, at TaskCreate or after a
raise, is told this hook raises the task when that prerequisite is done. A
raise for prerequisites also records the completed blockedBy list, so the
same blockers do not raise the task a second time. A deleted blocker frees such
a task without raising it, because nothing it waited on was done.

A PENDING TASK THAT RECORDS approval is raised once it is ready: nothing in
its blockedBy holds it, and its prerequisites are met or it has none, so an
approval opts in even a task with nothing to wait on. Its raise tells the
agent to set the task in_progress and dispatch a forked subagent for it, in
place of "Act on task N now", whatever made it ready. A task whose
prerequisites cannot be used is never ready. An in_progress task with an
approval is raised as a task without one, since someone is already on it.
One such raise at most is given per stop, for the ready task most other open
tasks list in blockedBy, then the lowest task number, and none while the
payload's background_tasks list shows at least
SUBAGENTS_AND_WORKFLOWS_RUNNING_AT_ONCE_LIMIT subagents and workflows running;
a payload without the list counts as none running, and its raise then leaves
out the count. A ready task not raised keeps its record as it was, so a later
stop raises it.

A PULL REQUEST CLOSED WITHOUT MERGING never meets its `pr_merged`
condition, so its task would wait in silence. An open task is raised once
for each such pull request, with the words "closed without merging", so its
agent re-plans it, whatever its other prerequisites and its blockedBy tasks
say, and it is not raised for that pull request again when they change. A
pull request reopened and then merged meets its condition as usual. Until
this hook has raised it, such a task counts as one nothing holds back for the
idle sweep, which counts with this hook's code and reads its state file, so
the sweep does not apply its rule 4, nothing to do, to the task's agent-seat:
an agent-seat that went idle before the pull request closed reaches no stop
for this hook to raise the task at, so the sweep's rule 5 judge decides
whether to wake it.

RAISED ONCE. The hook records, per task, the prerequisites list it raised
the task for, or for a task raised because its blockers completed, its
blockedBy list, and for a task raised for its approval, the approval, and
does not raise the task again for the same values; changing any of them
lets the task be raised again. A task raised because a
pull request closed without merging records that pull request's number, and is
never raised again for that number. A prerequisites list the
hook cannot read, or whose approval-walk item it cannot find, is named to the
agent once per value of the list, recorded the same way. The Stop hook's
additionalContext continues the conversation, so a hook that said the same
thing at every turn boundary would never let the agent stop. The record is
written atomically BEFORE anything is printed, and no raise is printed if the
write fails, so a raise whose record was lost cannot happen; the failed write
is reported as a fault instead, as OUTPUT says.

THE STATE FILE is
`~/.local/state/claude/agent-seat-due-task-raise-state/<list id>.json`,
outside the task directory so the harness's handling of that directory never
meets it; ~/.local/state/claude/ exists on both machines. Its `raised`
entries are pruned to the task files that still exist, and its `checks`
entries to the conditions an open task still names. A state file that cannot
be parsed is treated as empty and replaced on the next write, because
silence on any fault would mute the hook for good after one torn file. Two
sessions sharing one list id that stop at the same instant could each raise
the same task once; that is not locked against.

GITHUB, and only for prerequisites. The conditions the due-task pass will ask about
are first asked together in one read-only `gh api graphql` query; a condition that
query leaves unanswered, because it failed or GitHub resolved nothing for that
number, is checked alone with `gh pr view` or `gh issue view` (read-only), whose
error is the one reported. Every gh call has GH_TOKEN removed from the environment so gh
uses its keyring login, stdin closed, each call bounded by
GH_CALL_TIMEOUT_SECONDS and all of a run's calls together, the due-task
pass's and the next-action prompt's, by GH_CALLS_TOTAL_BUDGET_SECONDS, which
leaves the rest of the run room inside the hook's 30-second timeout in
.claude/settings.json. A condition found met is answered from the state file for
good, and any other condition checked within CONDITION_RECHECK_INTERVAL_SECONDS
is answered from it too. A check
gh could not answer, because gh is missing, failed, timed out or printed no
JSON object, is not an answer: no task waiting on it is raised, it is
recorded as a failure with its time so it too waits the interval, and the
stop that asked reports it, as OUTPUT says. No condition is checked for a
task already raised for its current prerequisites; of a task held by
blockedBy, only its `pr_merged` pull requests not yet raised as closed without
merging are checked. Tasks no blockedBy holds are checked first, so a held
task's checks spend only the budget they leave. A condition not checked
because less than GH_CALLS_BUDGET_LEFT_MINIMUM_TO_MAKE_A_CALL_SECONDS of the budget is left is answered not met and not cached, so the next
stop asks gh, and this stop counts the open tasks that wait on it, as OUTPUT
says. An agent-seat whose tasks have no prerequisites makes no
network call. The same call
fetches the title and URL the raise line cites; a condition gh never
answered is cited by its number alone.

THE NEXT-ACTION PROMPT. At a stop that raises no task, the hook hands the
agent NEXT_ACTION_INSTRUCTIONS, which tell it to start subagents on ready
work and build an approval-walk, when every one of these holds; otherwise it
says nothing about it:
  - the payload names a session, a transcript that exists, and a cwd inside
    a git checkout that has docs/walk/;
  - no walk-minutes there has an unclosed `#next_to_present` line, paused
    or not, as the walk-me-through finder module reads it;
  - neither the handoff hook's asked marker nor its deferred marker exists
    for the session, and the context used plus the tokens compactions
    dropped, as a share of the context window, is below the reincarnation
    threshold, read with the handoff hook's own reader and its
    DEFAULT_THRESHOLD_USED_PERCENTAGE: Claude Code
    runs the hooks of one Stop group in parallel, so at the stop that first
    reaches the threshold the asked marker may not be written yet;
  - the payload's background_tasks list, read with the handoff hook's
    work_in_flight_from_background_tasks, holds no running subagent,
    workflow or background task; a payload without the list counts as no
    work running, and a transcript the reader cannot fully read counts as
    work running;
  - the session has run a tool since this hook last handed it the prompt.
    The state file's `next_action_prompt` entry holds the session id and the
    id of the newest tool call the transcript held when the prompt was
    handed; a stop that finds both unchanged is silent, so an agent that
    stops again without running a tool is let stop, and the hook never
    loops.
Code gathers what it can for the agent: the open tasks no blockedBy or
unmet prerequisite holds back (prerequisites are answered by the same gh
checker, and one gh could not answer holds its task), the count of the
held ones, and every walk-minutes line marked `<open>`, the tasks in the
order the approval raise names them in, each list cut at a
limit with a count of the rest. Which listed task is ready, which needs the
user, and what the walk holds is the agent's judgment. The entry is written
with the rest of the state, before the prompt is printed. A fault while
deciding, such as a walk-minutes file that cannot be read, is reported on
stderr with exit 1, saying the tasks were checked, and writes no state.

OUTPUT. Something to raise, or the next-action prompt: one JSON object,
{"hookSpecificOutput": {"hookEventName": "Stop", "additionalContext": ...}},
which Claude Code delivers to the model as non-error feedback while the
conversation continues. No `decision` field and no `systemMessage`: the text
is for the agent. The text is one instruction per due task, the approval
raise for a pending task that records approval and "Act on task N now" for
any other, then, when any task was raised, the instruction for a task that
cannot be acted on yet, then one line per task whose pull request closed
without merging and, when there is any, the instructions for re-planning it,
then two lines per prerequisites list the hook cannot use, then the
next-action prompt's lines, then one line per condition gh could not answer
at this stop, then, when the budget left a condition unchecked, one line
counting those conditions and the open tasks that wait on them; that line alone, with nothing
else to print, goes out the same way, as context that asks nothing, exit 0. Nothing to raise,
name or count and no next-action prompt: nothing printed, exit 0. A fault, such as a payload
that is not a JSON object, a state file that cannot be written, a condition
gh could not answer at a stop with nothing else to print, or any exception:
one line on stderr naming the hook and the fault, nothing on stdout, exit 1.
The line for a failed state write says how many due tasks went unraised, or
that none was due, and that the first stop after the state file can be
written raises them; the line for a condition gh could not answer quotes
gh's failure; the line for any other fault says no task was checked. Claude Code records a
Stop hook's exit 1 as a non-blocking error and still ends the turn. Exit 2 and additionalContext would both continue the conversation, and a
fault that recurs at every stop would then never let the agent stop.

ONLY THE AGENT-SEAT'S OWN SESSION IS RAISED, never a headless `claude -p`
child an agent-seat's program starts. A child inherits the agent-seat's
environment, CLAUDE_CODE_TASK_LIST_ID included, and the raise text would be
the last thing the child says, which its caller reads as the answer. The
hook stays silent when
nn-systems/general-tools/agent-session-unattended-by-user-check-common.py
says no user attends the agent-session; the Stop payload carries no field
that tells an attended agent-session from a headless child.

The project's own headless Claude callers run no project hook at all: the
cold-read Claude cell, and the restater-judge cell through it, pass
`--settings` with disableAllHooks; scripts/ghi-guide-agent-ask.py and
scripts/sanity-check-adversarial-prompts.py pass `--setting-sources user`. The attendance
check covers a child started any other way.
"""

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

# Every Stop hook obeys this rule first: see the module's docstring.
_stop_hooks_stay_silent_rule_specification = importlib.util.spec_from_file_location(
    "claude_code_stop_hooks_stay_silent_while_agent_answers_a_stop_hook_rule_common",
    Path(__file__).resolve().parents[1] / "nn-systems" / "general-tools"
    / "claude-code-stop-hooks-stay-silent-while-agent-answers-a-stop-hook-rule-common.py")
stop_hooks_stay_silent_rule = importlib.util.module_from_spec(_stop_hooks_stay_silent_rule_specification)
_stop_hooks_stay_silent_rule_specification.loader.exec_module(stop_hooks_stay_silent_rule)

_agent_session_unattended_by_user_check_common_specification = importlib.util.spec_from_file_location(
    "agent_session_unattended_by_user_check_common",
    Path(__file__).resolve().parents[1] / "nn-systems" / "general-tools"
    / "agent-session-unattended-by-user-check-common.py")
agent_session_unattended_by_user_check_common = importlib.util.module_from_spec(
    _agent_session_unattended_by_user_check_common_specification)
_agent_session_unattended_by_user_check_common_specification.loader.exec_module(
    agent_session_unattended_by_user_check_common)

_HOOK_DIRECTORY = Path(__file__).resolve().parent


def _load_module_by_path(module_name: str, path: Path):
    specification = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


TASK_LIST_ID_ENVIRONMENT_VARIABLE = "CLAUDE_CODE_TASK_LIST_ID"
TASKS_ROOT_UNDER_HOME = Path(".claude") / "tasks"
STATE_DIRECTORY_UNDER_HOME = (Path(".local") / "state" / "claude"
                              / "agent-seat-due-task-raise-state")
OPEN_TASK_STATUSES = ("pending", "in_progress")
COMPLETED_TASK_STATUS = "completed"

GITHUB_REPOSITORY = "nedsnodes/nedsnodes"
CONDITION_RECHECK_INTERVAL_SECONDS = 300
GH_CALL_TIMEOUT_SECONDS = 8
GH_CALLS_TOTAL_BUDGET_SECONDS = 20
# A `gh pr view` takes over half a second on ned-box; with less time left than this, a call can
# only time out, which would be reported as a GitHub failure.
GH_CALLS_BUDGET_LEFT_MINIMUM_TO_MAKE_A_CALL_SECONDS = 2

# condition kind -> (gh subcommand, the gh state that means met, the ID-type
# written in the raise line, the word for met in the raise line)
CONDITION_KINDS = {
    "pr_merged": ("pr", "MERGED", "PR", "merged"),
    "issue_closed": ("issue", "CLOSED", "GHI", "closed"),
}

APPROVAL_WALK_ITEM_KIND = "approval_walk_item_decided"
WALK_MINUTES_FIELD = "approval_walk_minutes_file_path"
ITEM_HEADING_FIELD = "approval_walk_item_heading"
WALK_MINUTES_SUFFIX = "-minutes.md"
PREREQUISITES_KEY = "prerequisites"
APPROVAL_KEY = "approval"
PENDING_TASK_STATUS = "pending"
PULL_REQUEST_KIND = "pr_merged"
CLOSED_WITHOUT_MERGING_ANSWER_KEY = "closed_without_merging"
CLOSED_WITHOUT_MERGING_RECORD_KEY = "pull_requests_closed_without_merging"
PREREQUISITES_PROBLEM_RECORD_KEY = "prerequisites_problem"
PREREQUISITE_FORMS = (
    '{"pr_merged": <number>}, {"issue_closed": <number>} or {"' + APPROVAL_WALK_ITEM_KIND
    + '": {"' + WALK_MINUTES_FIELD + '": "<absolute path of the walk-minutes file>", "'
    + ITEM_HEADING_FIELD + '": "<the item\'s heading in the walk-document>"}}')

RAISE_LINE_TEMPLATE = ('[rule due-task-raise-when-prerequisites-met] Act on task {task_id} "{subject}" '
                       "now: {reasons}.")
# The user set this number and the wordings that name it; change them only with his approval.
SUBAGENTS_AND_WORKFLOWS_RUNNING_AT_ONCE_LIMIT = 3
APPROVAL_RAISE_LINE_TEMPLATE = (
    '[rule due-task-approved-ready-task-forked-subagent-dispatch-reminder] Task {task_id} "{subject}" is ready and '
    "needs no decision from the user ({approval}).{running_sentence} Set it in_progress with TaskUpdate, "
    'then dispatch a forked subagent for it, with the Agent tool\'s isolation "worktree", and mark the '
    "task completed when the subagent reports it done.")
APPROVAL_RAISE_RUNNING_SENTENCE_TEMPLATE = (
    " {running} of the {limit} subagents and workflows you may run at once are running.")
DEFER_INSTRUCTION = (
    "If a task above cannot be acted on yet, record what it now waits on with TaskUpdate "
    "instead: a pull request, a GHI or an approval-walk item in a new "
    "metadata.prerequisites, or a task with addBlockedBy."
)
CLOSED_WITHOUT_MERGING_LINE_TEMPLATE = (
    '[rule due-task-pull-request-closed-without-merging-replace-or-delete] Task {task_id} "{subject}" waits on a pull request that was closed without merging: '
    "{citations}.")
CLOSED_WITHOUT_MERGING_INSTRUCTIONS = (
    "If a task named above as waiting on a pull request closed without merging is still wanted, "
    "put what it now waits on in its metadata.prerequisites with TaskUpdate, in place of that pull "
    "request, or act on the task now.",
    "If such a task is no longer wanted, set its status to deleted with TaskUpdate.",
    "If you expect such a pull request to be reopened and merged, leave its task as it is: this "
    "hook raises the task when the pull request merges, and does not name the closing again.",
)
PREREQUISITES_PROBLEM_LINE_TEMPLATE = (
    '[rule due-task-prerequisites-unusable-correct-them] Task {task_id} "{subject}" is never raised as its metadata.prerequisites stand, because '
    "{problem}.")
BUDGET_SKIPPED_LINE_TEMPLATE = (
    "[rule due-task-github-call-budget-ran-out-next-stop-asks-again] This hook's {budget}-second budget for GitHub calls ran out before it asked about "
    "{condition_count} pull request(s) or GHI(s) that {task_count} open task(s) wait on; nothing "
    "is needed, since the next stop asks again and raises each task whose prerequisites are met.")
PREREQUISITES_CORRECTION_INSTRUCTION = (
    'Correct the task with TaskUpdate, giving its metadata a "prerequisites" list whose entries '
    "are each one of " + PREREQUISITE_FORMS + '; if the task waits on no pull request, GHI or '
    'approval-walk item, set "prerequisites" to null, and record any task on your own task list '
    "it waits on with addBlockedBy.")


def single_line(text) -> str:
    """Collapse any whitespace run, newlines included, to one space."""
    return " ".join(str(text).split())


def task_list_directory(home: Path, environment) -> "Path | None":
    list_id = environment.get(TASK_LIST_ID_ENVIRONMENT_VARIABLE, "")
    if not list_id or "/" in list_id or list_id in (".", ".."):
        return None
    return home / TASKS_ROOT_UNDER_HOME / list_id


def state_file_path(home: Path, list_id: str) -> Path:
    return home / STATE_DIRECTORY_UNDER_HOME / f"{list_id}.json"


def read_tasks(directory: Path, unreadable: "list | None" = None) -> dict:
    """Every readable task in the list, by id; a missing directory holds none, and one that
    exists but cannot be listed raises OSError.

    A malformed file is skipped, and its path is appended to `unreadable` when one is given."""
    # Not Path.glob: it answers a directory it cannot list, even on EIO, as an empty one.
    try:
        names = os.listdir(directory)
    except FileNotFoundError:
        return {}
    tasks = {}
    for path in sorted(directory / name for name in names if name.endswith(".json")):
        try:
            task = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            task = None
        task_id = task.get("id") if isinstance(task, dict) else None
        if not isinstance(task_id, str) or not task_id:
            if unreadable is not None:
                unreadable.append(path)
            continue
        tasks[task_id] = task
    return tasks


def blocker_holds(blocker_id, tasks: dict, directory: Path) -> bool:
    """True while this blockedBy entry keeps its task from being raised."""
    if not isinstance(blocker_id, str):
        return True
    if blocker_id in tasks:
        return tasks[blocker_id].get("status") != COMPLETED_TASK_STATUS
    # Not among the readable tasks: held if the file exists but would not
    # read, free if the task is gone.
    return (directory / f"{blocker_id}.json").exists()


def completed_blockers(task: dict, tasks: dict) -> "list | None":
    """The blockedBy ids, sorted, when every one names a completed task; else None.

    Called only for a task is_held_by_blockers let through, so every blocker
    that exists is completed and only a deleted one is left to rule out.
    """
    blocked_by = task.get("blockedBy")
    if not isinstance(blocked_by, list) or not blocked_by:
        return None
    if not all(blocker in tasks for blocker in blocked_by):
        return None
    return sorted(set(blocked_by), key=lambda text: (len(text), text))


def is_held_by_blockers(task: dict, tasks: dict, directory: Path) -> bool:
    blocked_by = task.get("blockedBy") or []
    if not isinstance(blocked_by, list):
        return True
    return any(blocker_holds(blocker, tasks, directory) for blocker in blocked_by)


class UnreadablePrerequisites(ValueError):
    """A prerequisites list this hook cannot use; the argument says why, as a clause."""


def parse_prerequisites(value) -> list:
    """The prerequisites list as [(kind, number or approval-walk item object), ...].

    Raises UnreadablePrerequisites naming the first entry it cannot read."""
    if not isinstance(value, list):
        raise UnreadablePrerequisites(f"it is {json.dumps(value)}, not a list")
    if not value:
        raise UnreadablePrerequisites("it is an empty list, which names nothing to wait on")
    conditions = []
    for entry in value:
        shown = json.dumps(entry, ensure_ascii=False)
        if not isinstance(entry, dict) or len(entry) != 1:
            raise UnreadablePrerequisites(f"its entry {shown} is not an object with one key")
        (kind, condition), = entry.items()
        if kind == APPROVAL_WALK_ITEM_KIND:
            if (not isinstance(condition, dict)
                    or set(condition) != {WALK_MINUTES_FIELD, ITEM_HEADING_FIELD}
                    or not isinstance(condition[WALK_MINUTES_FIELD], str)
                    or not os.path.isabs(condition[WALK_MINUTES_FIELD])
                    or not condition[WALK_MINUTES_FIELD].endswith(WALK_MINUTES_SUFFIX)
                    or not isinstance(condition[ITEM_HEADING_FIELD], str)
                    or not condition[ITEM_HEADING_FIELD].strip()):
                raise UnreadablePrerequisites(
                    f'its entry {shown} does not give "{WALK_MINUTES_FIELD}" as the absolute path '
                    f'of a file whose name ends {WALK_MINUTES_SUFFIX} and "{ITEM_HEADING_FIELD}" '
                    f"as the item's heading, and no other key")
        elif kind not in CONDITION_KINDS:
            raise UnreadablePrerequisites(
                f'its entry {shown} names the kind "{kind}", which this hook does not know')
        elif isinstance(condition, bool) or not isinstance(condition, int) or condition <= 0:
            raise UnreadablePrerequisites(f"its entry {shown} does not give a positive whole number")
        conditions.append((kind, condition))
    return conditions


_walk_modules = []


def walk_finder_and_answer_program():
    """The walk-me-through finder module and answer program, loaded on first use only."""
    if not _walk_modules:
        _walk_modules.extend((
            _load_module_by_path(
                "walk_me_through_approval_walk_minutes_and_walk_document_item_finder_common",
                WALK_FINDER_FILE),
            _load_module_by_path(
                "walk_me_through_answer_added_texts_cold_read_fast_read_check_and_close",
                WALK_ANSWER_PROGRAM_FILE)))
    return _walk_modules


class MarkdownParserParsingEachTextOnce:
    """A markdown parser that parses each distinct text once; callers must not change its tokens.

    Keyed by the text itself, so a file that changes is parsed anew."""

    def __init__(self, parser):
        self._parser = parser
        self._tokens_by_text = {}

    def parse(self, text):
        if text not in self._tokens_by_text:
            self._tokens_by_text[text] = self._parser.parse(text)
        return self._tokens_by_text[text]


def approval_walk_item_decided_or_problem(condition: dict, checker=None) -> dict:
    """{"met": bool}, with "problem", a clause saying why, when the item cannot be found.

    With `checker`, parses through the parser it keeps for this execution."""
    walk_finder, answer_program = walk_finder_and_answer_program()
    minutes = Path(condition[WALK_MINUTES_FIELD])
    document = minutes.with_name(minutes.name[:-len(WALK_MINUTES_SUFFIX)] + ".md")
    heading = condition[ITEM_HEADING_FIELD]
    try:
        document_text = document.read_text(encoding="utf-8")
    except FileNotFoundError:
        # The walk-document holds the item before anyone can name its heading, so a missing one
        # means a wrong path, which would otherwise hold the task in silence for good.
        return {"met": False, "problem": f"the walk-document {document}, which the walk-minutes "
                                         f"path {minutes} names, does not exist"}
    parser = (walk_finder.markdown_parser() if checker is None
              else checker.markdown_parser_parsing_each_text_once(walk_finder))
    lines = document_text.split("\n")
    title = answer_program.heading_title(walk_finder, heading)
    units = walk_finder.item_unit_spans(document_text, parser)
    matching = [unit for unit in units
                if answer_program.heading_title(walk_finder, lines[unit[3]]) == title]
    if len(matching) != 1:
        found = "no item heading that reads" if not matching else f"{len(matching)} item headings that read"
        return {"met": False, "problem": f'the walk-document {document} holds {found} '
                                         f'"{single_line(heading)}" once its running count is left out'}
    numbers = matching[0][0]
    if not numbers or not minutes.exists():
        return {"met": False}
    decided = answer_program.approval_walk_minutes_read_returning_decided_item_numbers(walk_finder, minutes, parser)
    return {"met": all(number in decided for number in numbers)}


def condition_answer(kind: str, condition, checker) -> dict:
    if kind == APPROVAL_WALK_ITEM_KIND:
        return approval_walk_item_decided_or_problem(condition, checker)
    return checker.answer(kind, condition)


def condition_key(kind: str, number: int) -> str:
    return f"{kind}:{number}"


def canonical_prerequisites(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def read_state(path: Path) -> dict:
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        state = {}
    if not isinstance(state, dict):
        state = {}
    raised = state.get("raised")
    checks = state.get("checks")
    result = {
        "raised": raised if isinstance(raised, dict) else {},
        "checks": checks if isinstance(checks, dict) else {},
    }
    if isinstance(state.get(NEXT_ACTION_STATE_KEY), dict):
        result[NEXT_ACTION_STATE_KEY] = state[NEXT_ACTION_STATE_KEY]
    return result


def write_state_atomically(path: Path, state: dict) -> None:
    """Replace the state file in one rename; raises OSError when it did not land."""
    temporary_name = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(
            dir=str(path.parent), prefix=path.name + ".", suffix=".tmp")
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(state, handle, indent=2, sort_keys=True)
            handle.write("\n")
        os.replace(temporary_name, str(path))
    except OSError:
        if temporary_name is not None:
            try:
                os.unlink(temporary_name)
            except OSError:
                pass
        raise


class GitHubConditionChecker:
    """Answers prerequisite conditions from the cache or from gh, within a budget.

    `gh_failures` gets a (kind, number, cause) entry for every failed answer `answer` returns,
    fresh or cached, so one condition answered twice is listed twice; a caller that answers
    for several agent-seats reads the entries its own calls appended.
    `conditions_skipped_for_budget` gets a (kind, number) entry for every condition answered
    not met because the budget was spent, in the same way.
    """

    # The budget's clock; the test replaces it so its budget cases do not depend on machine speed.
    clock = staticmethod(time.monotonic)

    def __init__(self, checks: dict, now_epoch: float):
        self.checks = checks
        self.now_epoch = now_epoch
        self.started = self.clock()
        self.changed = False
        self.gh_failures = []
        self.conditions_skipped_for_budget = []
        self._markdown_parser_parsing_each_text_once = None

    def markdown_parser_parsing_each_text_once(self, walk_finder) -> MarkdownParserParsingEachTextOnce:
        """The one parser of this checker, and so of this execution, built on first use."""
        if self._markdown_parser_parsing_each_text_once is None:
            self._markdown_parser_parsing_each_text_once = MarkdownParserParsingEachTextOnce(
                walk_finder.markdown_parser())
        return self._markdown_parser_parsing_each_text_once

    def answer(self, kind: str, number: int) -> dict:
        answer = self.cached_or_fresh_answer(kind, number)
        if "gh_failure" in answer:
            self.gh_failures.append((kind, number, answer["gh_failure"]))
        return answer

    def usable_cached_answer(self, kind: str, number: int) -> "dict | None":
        """The cached answer, when it is met or younger than the recheck interval; else None.
        A merged pull request or a closed GHI is kept met for good: a merge never changes back,
        and a GHI reopened after its task was raised already counts as met."""
        cached = self.checks.get(condition_key(kind, number))
        if not isinstance(cached, dict):
            return None
        if cached.get("met") is True:
            return cached
        if (isinstance(cached.get("checked_at_epoch"), (int, float))
                and 0 <= self.now_epoch - cached["checked_at_epoch"]
                < CONDITION_RECHECK_INTERVAL_SECONDS):
            return cached
        return None

    def budget_left_seconds(self) -> float:
        return GH_CALLS_TOTAL_BUDGET_SECONDS - (self.clock() - self.started)

    def store_fresh_answer(self, kind: str, number: int, fresh: dict) -> dict:
        key = condition_key(kind, number)
        fresh["checked_at_epoch"] = self.now_epoch
        previous = self.checks.get(key) if isinstance(self.checks.get(key), dict) else {}
        for citation_field in ("title", "url"):
            if citation_field not in fresh and isinstance(previous.get(citation_field), str):
                fresh[citation_field] = previous[citation_field]
        self.checks[key] = fresh
        self.changed = True
        return fresh

    def answer_all_in_one_query(self, conditions) -> None:
        """Ask GitHub, in one GraphQL call, about every (kind, number) the cache cannot answer,
        and cache each answer it gives. A condition the call leaves unanswered, because the call
        failed or GitHub gave nothing for it, is asked alone later by `answer`, whose gh call
        reports gh's own error."""
        unanswered = [(kind, number) for kind, number in dict.fromkeys(conditions)
                      if kind in CONDITION_KINDS and self.usable_cached_answer(kind, number) is None]
        remaining = self.budget_left_seconds()
        if not unanswered or remaining < GH_CALLS_BUDGET_LEFT_MINIMUM_TO_MAKE_A_CALL_SECONDS:
            return
        answers = self.ask_gh_in_one_query(unanswered, min(GH_CALL_TIMEOUT_SECONDS, remaining))
        for (kind, number), fresh in answers.items():
            self.store_fresh_answer(kind, number, fresh)

    def cached_or_fresh_answer(self, kind: str, number: int) -> dict:
        cached = self.usable_cached_answer(kind, number)
        if cached is not None:
            return cached
        remaining = self.budget_left_seconds()
        if remaining < GH_CALLS_BUDGET_LEFT_MINIMUM_TO_MAKE_A_CALL_SECONDS:
            # Not cached, so the next stop asks gh about it.
            self.conditions_skipped_for_budget.append((kind, number))
            return {"met": False}
        fresh = self.ask_gh(kind, number, min(GH_CALL_TIMEOUT_SECONDS, remaining))
        return self.store_fresh_answer(kind, number, fresh)

    @staticmethod
    def ask_gh_in_one_query(conditions, timeout_seconds: float) -> dict:
        """{(kind, number): {"met": ..., "title": ..., "url": ...}} for each condition GitHub
        answered in one `gh api graphql` call; empty when the call failed."""
        owner, name = GITHUB_REPOSITORY.split("/")
        fields = []
        for index, (kind, number) in enumerate(conditions):
            node = "pullRequest" if kind == PULL_REQUEST_KIND else "issue"
            fields.append(f"c{index}: {node}(number: {int(number)}) {{ state title url }}")
        query = (f'query {{ repository(owner: "{owner}", name: "{name}") {{ '
                 + " ".join(fields) + " } }")
        environment = dict(os.environ)
        environment.pop("GH_TOKEN", None)
        try:
            completed = subprocess.run(
                ["gh", "api", "graphql", "-f", f"query={query}"], stdin=subprocess.DEVNULL,
                capture_output=True, text=True, timeout=timeout_seconds, env=environment,
                check=False)
            body = json.loads(completed.stdout)
        except (OSError, subprocess.SubprocessError, ValueError):
            return {}
        # gh exits nonzero when GitHub cannot resolve one of the numbers, yet prints its answers
        # for the others, so the body is read whatever the exit code.
        data = body.get("data") if isinstance(body, dict) else None
        repository = (data.get("repository") if isinstance(data, dict) else None) or {}
        answers = {}
        for index, (kind, number) in enumerate(conditions):
            node = repository.get(f"c{index}")
            if not isinstance(node, dict) or not isinstance(node.get("state"), str):
                continue
            answer = {"met": node["state"] == CONDITION_KINDS[kind][1]}
            if kind == PULL_REQUEST_KIND:
                answer[CLOSED_WITHOUT_MERGING_ANSWER_KEY] = node["state"] == "CLOSED"
            for citation_field in ("title", "url"):
                if isinstance(node.get(citation_field), str):
                    answer[citation_field] = node[citation_field]
            answers[(kind, number)] = answer
        return answers

    @staticmethod
    def ask_gh(kind: str, number: int, timeout_seconds: float) -> dict:
        """Return {"met": ..., "title": ..., "url": ...}, or {"gh_failure": <cause>} when gh did not answer."""
        subcommand, met_state, _, _ = CONDITION_KINDS[kind]
        environment = dict(os.environ)
        environment.pop("GH_TOKEN", None)
        command = ["gh", subcommand, "view", str(number), "--repo", GITHUB_REPOSITORY,
                   "--json", "state,title,url"]
        command_text = f"`{' '.join(command)}`"
        try:
            completed = subprocess.run(
                command, stdin=subprocess.DEVNULL, capture_output=True, text=True,
                timeout=timeout_seconds, env=environment, check=False)
        except subprocess.TimeoutExpired:
            return {"gh_failure": f"{command_text} did not answer within "
                                  f"{timeout_seconds:g} seconds"}
        except (OSError, subprocess.SubprocessError) as error:
            return {"gh_failure": f"{command_text} could not be run: {error}"}
        if completed.returncode != 0:
            return {"gh_failure": f"{command_text} exited {completed.returncode}: "
                                  f"{single_line(completed.stderr) or 'with nothing on stderr'}"}
        try:
            answer = json.loads(completed.stdout)
        except ValueError:
            answer = None
        if not isinstance(answer, dict):
            return {"gh_failure": f"{command_text} exited 0 without printing a JSON object"}
        result = {"met": answer.get("state") == met_state}
        if kind == PULL_REQUEST_KIND:
            # MERGED is a closed pull request too, but gh reports it apart from CLOSED.
            result[CLOSED_WITHOUT_MERGING_ANSWER_KEY] = answer.get("state") == "CLOSED"
        for citation_field in ("title", "url"):
            if isinstance(answer.get(citation_field), str):
                result[citation_field] = answer[citation_field]
        return result


def condition_citation(kind: str, number, answer: dict) -> str:
    if kind == APPROVAL_WALK_ITEM_KIND:
        return (f'the approval-walk item "{single_line(number[ITEM_HEADING_FIELD])}" is decided '
                f"in {number[WALK_MINUTES_FIELD]}")
    return f"{github_item_citation(kind, number, answer)} is {CONDITION_KINDS[kind][3]}"


def github_item_citation(kind: str, number: int, answer: dict) -> str:
    """The pull request or GHI by its title and link, or by its number when gh gave neither."""
    id_type = CONDITION_KINDS[kind][2]
    title = answer.get("title")
    url = answer.get("url")
    if isinstance(title, str) and title.strip() and isinstance(url, str) and url:
        return f'{id_type} "{single_line(title)}" ({url})'
    return f"{id_type} {number}"


def pull_request_conditions_not_raised_as_closed(conditions, record: dict) -> list:
    """The `pr_merged` conditions this task's record has not raised as closed without merging."""
    already_closed = record.get(CLOSED_WITHOUT_MERGING_RECORD_KEY) or []
    return [(kind, number) for kind, number in conditions
            if kind == PULL_REQUEST_KIND and number not in already_closed]


def pull_requests_closed_without_merging(conditions, checker) -> list:
    """(number, answer) for each `pr_merged` condition gh says is closed without merging."""
    found = []
    for kind, number in conditions:
        if kind == PULL_REQUEST_KIND:
            answer = checker.answer(kind, number)
            if answer.get(CLOSED_WITHOUT_MERGING_ANSWER_KEY) is True:
                found.append((number, answer))
    return found


def gh_failure_line(kind: str, number: int, cause: str) -> str:
    _, _, id_type, met_word = CONDITION_KINDS[kind]
    return (f"This hook could not ask GitHub whether {id_type} {number} is {met_word}, so no "
            f"task waiting on it was raised: {cause}. It asks again at the first stop at least "
            f"{CONDITION_RECHECK_INTERVAL_SECONDS // 60} minutes after the failed call. If gh's error says "
            f"{id_type} {number} does not exist, correct the metadata.prerequisites that names it "
            f"with TaskUpdate. If it says gh is not logged in or its credentials are bad, ask "
            f"the user to run `gh auth login` on this machine.")


def prerequisites_raised_as_met(record: dict, prerequisites_value) -> bool:
    """Whether the task's record shows its current prerequisites raised as met. A raised
    `pr_merged` pull request stays merged, so none of them can have closed without merging; a
    raised `issue_closed` GHI that is reopened later still counts as met."""
    return record.get(PREREQUISITES_KEY) == canonical_prerequisites(prerequisites_value)


def budget_skipped_task_lines(tasks: dict, skipped_conditions, raised: dict) -> list:
    """One line counting the open tasks the skip left unraised, and the skipped conditions
    they name; nothing when there is none. A task counts when it names a condition the checker
    skipped for lack of budget and `raised`, the state file's record as this run leaves it,
    neither shows it raised as met nor shows it told to re-plan for a pull request closed
    without merging.

    Not handled: a pull request with an old closed-without-merging record that was reopened and
    merged since. Its task gets no line here even when the budget skipped the pull request; a
    later run that asks GitHub sees the merge, and raises the task once its other prerequisites
    and blockers allow."""
    skipped = set(skipped_conditions)
    task_count = 0
    skipped_named = set()
    for task_id in sorted(tasks, key=lambda text: (len(text), text)):
        task = tasks[task_id]
        metadata = task.get("metadata")
        if task.get("status") not in OPEN_TASK_STATUSES or not isinstance(metadata, dict):
            continue
        try:
            conditions = parse_prerequisites(metadata.get(PREREQUISITES_KEY))
        except UnreadablePrerequisites:
            continue
        record = raised.get(task_id) if isinstance(raised.get(task_id), dict) else {}
        closed_without_merging = record.get(CLOSED_WITHOUT_MERGING_RECORD_KEY) or []
        if (prerequisites_raised_as_met(record, metadata.get(PREREQUISITES_KEY))
                or any(kind == PULL_REQUEST_KIND and number in closed_without_merging
                       for kind, number in conditions)):
            continue
        named = {(kind, number) for kind, number in conditions
                 if kind in CONDITION_KINDS and (kind, number) in skipped}
        if named:
            task_count += 1
            skipped_named |= named
    if not task_count:
        return []
    return [BUDGET_SKIPPED_LINE_TEMPLATE.format(
        budget=GH_CALLS_TOTAL_BUDGET_SECONDS, condition_count=len(skipped_named),
        task_count=task_count)]


def github_conditions_the_due_task_pass_asks(tasks: dict, directory: Path, raised: dict) -> list:
    """The pull requests and GHIs `due_task_lines` asks GitHub about, so that one query can
    answer them first: of each open task not raised for its current prerequisites, its
    `pr_merged` pull requests not yet raised as closed without merging, and, when no blockedBy
    holds it, every pull request and GHI it names."""
    found = []
    for task_id, task in tasks.items():
        metadata = task.get("metadata")
        if task.get("status") not in OPEN_TASK_STATUSES or not isinstance(metadata, dict):
            continue
        prerequisites_value = metadata.get(PREREQUISITES_KEY)
        if prerequisites_value is None:
            continue
        try:
            conditions = parse_prerequisites(prerequisites_value)
        except UnreadablePrerequisites:
            continue
        record = raised.get(task_id) if isinstance(raised.get(task_id), dict) else {}
        if prerequisites_raised_as_met(record, prerequisites_value):
            continue
        found += pull_request_conditions_not_raised_as_closed(conditions, record)
        if not is_held_by_blockers(task, tasks, directory):
            found += [(kind, number) for kind, number in conditions if kind in CONDITION_KINDS]
    return list(dict.fromkeys(found))


def raise_line(task: dict, met_citations, done_blockers=None) -> str:
    reasons = []
    if met_citations is not None:
        reasons.append("its prerequisites are met: " + "; ".join(met_citations))
    if done_blockers is not None:
        reasons.append("the tasks it waited on are completed: "
                       + ", ".join(f"task {single_line(blocker)}" for blocker in done_blockers))
    return RAISE_LINE_TEMPLATE.format(task_id=task["id"], subject=single_line(task.get("subject", "")),
                                      reasons=", and ".join(reasons))


def approval_raise_line(task: dict, approval: str, running: "int | None") -> str:
    """`running` is None when Claude Code sent no background-work list, and the line then leaves
    out its count."""
    running_sentence = ("" if running is None else APPROVAL_RAISE_RUNNING_SENTENCE_TEMPLATE.format(
        running=running, limit=SUBAGENTS_AND_WORKFLOWS_RUNNING_AT_ONCE_LIMIT))
    return APPROVAL_RAISE_LINE_TEMPLATE.format(
        task_id=task["id"], subject=single_line(task.get("subject", "")),
        approval=single_line(approval), running_sentence=running_sentence)


def running_subagents_and_workflows(payload: dict) -> "int | None":
    """How many subagents and workflows the Stop payload's background-work list shows running, or
    None when the payload holds no list."""
    handoff = _load_module_by_path("handoff_context_threshold_hook", HANDOFF_THRESHOLD_HOOK_FILE)
    background_tasks = payload.get(handoff.BACKGROUND_TASKS_PAYLOAD_KEY)
    if not isinstance(background_tasks, list):
        return None
    return sum(1 for entry in background_tasks
               if isinstance(entry, dict)
               and entry.get("status") == handoff.RUNNING_TASK_STATUS
               and entry.get("type") in (handoff.SUBAGENT_TASK_TYPE, handoff.WORKFLOW_TASK_TYPE))


def tasks_in_start_order(task_ids, tasks: dict) -> list:
    """The ids, the one most other open tasks list in blockedBy first, then by task number."""
    blocking_counts = {}
    for other_id, other in tasks.items():
        blocked_by = other.get("blockedBy")
        if other.get("status") not in OPEN_TASK_STATUSES or not isinstance(blocked_by, list):
            continue
        for blocker in set(blocked_by):
            if isinstance(blocker, str) and blocker != other_id:
                blocking_counts[blocker] = blocking_counts.get(blocker, 0) + 1
    return sorted(task_ids, key=lambda task_id: (-blocking_counts.get(task_id, 0),
                                                 len(task_id), task_id))


def due_task_lines(tasks: dict, directory: Path, state: dict,
                   checker: "GitHubConditionChecker",
                   running: "int | None" = None) -> "tuple[list, list, list, bool]":
    """The raise lines, the lines naming tasks whose pull request closed without merging, the
    lines naming prerequisites the hook cannot use, and whether the state changed apart from
    `checker`'s cache.

    `running` is the count of running subagents and workflows, None when Claude Code sent no
    list. Of the pending tasks that record an approval and are ready, at most one is raised, in
    tasks_in_start_order's order, and none while `running` has reached the limit; the others
    keep their records unchanged, so a later stop raises them.

    Mutates `state` to record every raise and every named fault it returns, and to prune entries
    for tasks and conditions that no longer need them.
    """
    raised = state["raised"]
    lines = []
    closed_lines = []
    problem_lines = []
    state_changed = False
    # (task id, approval, the record keys its raise would set or remove, None meaning remove)
    approval_raise_candidates = []
    conditions_still_named = set()
    held_task_ids = {task_id for task_id, task in tasks.items()
                     if task.get("status") in OPEN_TASK_STATUSES
                     and is_held_by_blockers(task, tasks, directory)}

    # Tasks no blockedBy holds come first, so they spend the gh budget before held tasks do.
    for task_id in sorted(tasks, key=lambda text: (text in held_task_ids, len(text), text)):
        task = tasks[task_id]
        if task.get("status") not in OPEN_TASK_STATUSES:
            continue
        metadata = task.get("metadata")
        if metadata is None:
            metadata = {}
        if not isinstance(metadata, dict):
            continue
        record = raised.get(task_id) if isinstance(raised.get(task_id), dict) else {}
        new_record = dict(record)

        prerequisites_value = metadata.get(PREREQUISITES_KEY)
        problem = None
        conditions = None
        if prerequisites_value is not None:
            try:
                conditions = parse_prerequisites(prerequisites_value)
            except UnreadablePrerequisites as unreadable:
                problem = str(unreadable)
        if conditions is not None:
            conditions_still_named.update(condition_key(k, n) for k, n in conditions
                                          if k in CONDITION_KINDS)

        if conditions is not None and not prerequisites_raised_as_met(record, prerequisites_value):
            newly_closed = pull_requests_closed_without_merging(
                pull_request_conditions_not_raised_as_closed(conditions, record), checker)
            if newly_closed:
                new_record[CLOSED_WITHOUT_MERGING_RECORD_KEY] = sorted(
                    set(record.get(CLOSED_WITHOUT_MERGING_RECORD_KEY) or [])
                    | {number for number, _ in newly_closed})
                closed_lines.append(CLOSED_WITHOUT_MERGING_LINE_TEMPLATE.format(
                    task_id=task["id"], subject=single_line(task.get("subject", "")),
                    citations="; ".join(github_item_citation(PULL_REQUEST_KIND, number, answer)
                                        for number, answer in newly_closed)))

        approval = metadata.get(APPROVAL_KEY)
        if not isinstance(approval, str) or not approval.strip():
            approval = None
        prerequisite_citations = None
        done_blockers = None
        record_before_readiness = {key: new_record.get(key)
                                   for key in (PREREQUISITES_KEY, "blocked_by")}
        if task_id not in held_task_ids:
            blockers = completed_blockers(task, tasks)
            already_raised_for_prerequisites = False
            if conditions is not None:
                prerequisites_record = canonical_prerequisites(prerequisites_value)
                recorded = record.get(PREREQUISITES_KEY)
                already_raised_for_prerequisites = recorded == prerequisites_record
                if not already_raised_for_prerequisites:
                    answers = [(kind, number, condition_answer(kind, number, checker))
                               for kind, number in conditions]
                    problem = next((answer["problem"] for _, _, answer in answers
                                    if "problem" in answer), None)
                    if all(answer.get("met") is True for _, _, answer in answers):
                        prerequisite_citations = [
                            condition_citation(kind, number, answer)
                            for kind, number, answer in answers]
                        new_record[PREREQUISITES_KEY] = prerequisites_record
                        if blockers is not None:
                            new_record["blocked_by"] = blockers
            if ((prerequisites_value is None or already_raised_for_prerequisites)
                    and blockers is not None and record.get("blocked_by") != blockers):
                done_blockers = blockers
                new_record["blocked_by"] = blockers
            approval_ready = (approval is not None
                              and task.get("status") == PENDING_TASK_STATUS
                              and (prerequisites_value is None
                                   or already_raised_for_prerequisites
                                   or prerequisite_citations is not None))
            if approval_ready and (record.get(APPROVAL_KEY) != approval
                                   or prerequisite_citations is not None
                                   or done_blockers is not None):
                raise_record = {key: new_record.get(key) for key in record_before_readiness}
                raise_record[APPROVAL_KEY] = approval
                approval_raise_candidates.append((task_id, approval, raise_record))
                for key, value in record_before_readiness.items():
                    if value is None:
                        new_record.pop(key, None)
                    else:
                        new_record[key] = value
            elif prerequisite_citations is not None or done_blockers is not None:
                lines.append(raise_line(task, prerequisite_citations, done_blockers))
        # Kept while the list is unchanged, so a stop that does not look at the list, such as one
        # where a blocker holds the task, does not name the same fault again later.
        problem_record = canonical_prerequisites(prerequisites_value)
        if problem is not None and record.get(PREREQUISITES_PROBLEM_RECORD_KEY) != problem_record:
            new_record[PREREQUISITES_PROBLEM_RECORD_KEY] = problem_record
            problem_lines += [
                PREREQUISITES_PROBLEM_LINE_TEMPLATE.format(
                    task_id=task["id"], subject=single_line(task.get("subject", "")),
                    problem=problem),
                PREREQUISITES_CORRECTION_INSTRUCTION]
        elif problem is None and record.get(PREREQUISITES_PROBLEM_RECORD_KEY) != problem_record:
            new_record.pop(PREREQUISITES_PROBLEM_RECORD_KEY, None)

        if new_record != record:
            if new_record:
                raised[task_id] = new_record
            else:
                del raised[task_id]
            state_changed = True

    if approval_raise_candidates and (running is None
                                      or running < SUBAGENTS_AND_WORKFLOWS_RUNNING_AT_ONCE_LIMIT):
        candidates_by_id = {candidate[0]: candidate for candidate in approval_raise_candidates}
        task_id, approval, raise_record = candidates_by_id[
            tasks_in_start_order(list(candidates_by_id), tasks)[0]]
        record = dict(raised.get(task_id) or {})
        for key, value in raise_record.items():
            if value is None:
                record.pop(key, None)
            else:
                record[key] = value
        raised[task_id] = record
        state_changed = True
        lines.append(approval_raise_line(tasks[task_id], approval, running))

    for task_id in list(raised):
        if task_id not in tasks:
            del raised[task_id]
            state_changed = True
    for key in list(state["checks"]):
        if key not in conditions_still_named:
            del state["checks"][key]
            state_changed = True
    return lines, closed_lines, problem_lines, state_changed


WALK_FINDER_FILE = (_HOOK_DIRECTORY.parent / "nn-systems" / "skills" / "walk-me-through"
                    / "walk-me-through-approval-walk-minutes-and-walk-document-item-finder-common.py")
WALK_ANSWER_PROGRAM_FILE = WALK_FINDER_FILE.with_name(
    "walk-me-through-answer-added-texts-cold-read-fast-read-check-and-close.py")
HANDOFF_THRESHOLD_HOOK_FILE = _HOOK_DIRECTORY / "handoff-context-threshold-hook.py"
TRANSCRIPT_RECORDS_FILE = _HOOK_DIRECTORY / "claude-code-session-transcript-records-read-backward-common.py"
NEXT_ACTION_STATE_KEY = "next_action_prompt"
OPEN_OUTCOME_MARK = "<open>"
NEXT_ACTION_LISTED_TASKS_LIMIT = 40
NEXT_ACTION_LISTED_OPEN_ITEMS_LIMIT = 15
NEXT_ACTION_LISTED_LINE_CHARACTERS = 160

NEXT_ACTION_INSTRUCTIONS = (
    "[rule due-task-idle-agent-seat-start-ready-tasks-and-next-approval-walk] No approval-walk is open and none of "
    "your work is running, so do not stop here.",
    "Tell the user in one line that you are building a new approval-walk.",
    f"Start subagents on up to {SUBAGENTS_AND_WORKFLOWS_RUNNING_AT_ONCE_LIMIT} of the tasks listed "
    "below that need no review or approval from the user, taking them in the order listed, and "
    "start the next as one finishes.",
    "Build an approval-walk of 8 to 16 items, more than 16 only for one large thing with many "
    "parts, from your loose-ends, open questions, concerns, suggestions and tasks that need the "
    "user; put first the items that block work, then what makes the user's interaction easier "
    "and what makes agents or the process faster or cheaper, then the rest, the oldest first "
    "among equals.",
    "If you have none of these at all, ask ghi-guide-agent for 3 to 5 GHIs to work on, with "
    "`python3 scripts/ghi-guide-agent-ask.py \"Which 3 to 5 open GHIs would most improve how "
    "easy the user's interaction with agents is, or how fast or cheap agents and the "
    "development process are?\"`, choose among them the same way, and make them the walk's "
    "items.",
)
NEXT_ACTION_UNHELD_TASKS_HEADER = (
    "Your open tasks that no recorded prerequisite or blocker holds back; which of them are "
    "ready, and which need the user, is yours to judge:")
NEXT_ACTION_HELD_TASKS_LINE = (
    "{count} more open task(s) are not listed: each waits on a blocker task, a pull request or "
    "GHI that is not done, an approval-walk item not yet decided, or a pull request or GHI whose "
    "state this hook could not read from GitHub at this stop; or its metadata.prerequisites "
    "cannot be used, as this hook said when it first found them.")
NEXT_ACTION_OPEN_ITEMS_HEADER = (
    "Lines your walk-minutes mark <open>; each is a loose-end unless a task, GHI, pull request "
    "or later walk now holds it:")
NEXT_ACTION_MORE_LINE = "and {count} more."
NEXT_ACTION_STOP_AGAIN_LINE = (
    "If you end your turn again without running a tool, this hook lets the turn end.")


def shortened(text: str) -> str:
    text = single_line(text)
    if len(text) <= NEXT_ACTION_LISTED_LINE_CHARACTERS:
        return text
    return text[:NEXT_ACTION_LISTED_LINE_CHARACTERS - 3] + "..."


def newest_tool_use_id(records) -> "str | None":
    """The id of the newest tool call the transcript records, or None when it records none."""
    for record in records:
        message = record.get("message")
        if record.get("type") != "assistant" or not isinstance(message, dict):
            continue
        content = message.get("content")
        if not isinstance(content, list):
            continue
        for block in reversed(content):
            if isinstance(block, dict) and block.get("type") == "tool_use":
                return str(block.get("id"))
    return None


def open_outcome_lines(walk_directory: Path) -> list:
    """`<file>:<line>: <text>` for each walk-minutes line marked <open>, oldest file first."""
    found = []
    minutes_files = sorted(walk_directory.glob("*-minutes.md"),
                           key=lambda path: (path.stat().st_mtime, path.name))
    for minutes in minutes_files:
        for number, line in enumerate(minutes.read_text(encoding="utf-8").splitlines(), 1):
            if OPEN_OUTCOME_MARK in line:
                found.append(f"{minutes.name}:{number}: {shortened(line)}")
    return found


def unheld_and_held_tasks(tasks: dict, directory: Path, checker,
                          raised: dict) -> "tuple[list, int]":
    """The ids of open tasks nothing recorded holds back, or that wait on a pull request closed
    without merging that `raised`, the state file's record, does not show raised yet, oldest
    first, and the count of the rest.

    A task whose record shows its prerequisites raised as met is not asked about again, so in a
    Stop run every gh question for a task no blockedBy holds is one `due_task_lines` asked first,
    before its held tasks spent the budget, and is answered from the cache, except one the budget
    skipped there: that one is not cached, and with the budget spent its task is counted as held.
    The closed-without-merging scan asks a `pr_merged` question before `all()` runs and can skip
    it again, so `all()` stopping at an earlier unmet prerequisite saves only its own lookup. The
    scan leaves out a pull request the record shows raised as closed, so when `all()` stops before
    that prerequisite, no lookup for that pull request happens.

    Not handled: a task raised as met stays listed as unheld when what its prerequisites name
    changes afterwards, such as the walk-document of an `approval_walk_item_decided` being
    removed."""
    unheld = []
    held = 0
    held_by_blockers = {task_id for task_id, task in tasks.items()
                        if task.get("status") in OPEN_TASK_STATUSES
                        and is_held_by_blockers(task, tasks, directory)}
    # Tasks no blockedBy holds come first, so they spend the gh budget before held tasks do.
    for task_id in sorted(tasks, key=lambda text: (text in held_by_blockers, len(text), text)):
        task = tasks[task_id]
        if task.get("status") not in OPEN_TASK_STATUSES:
            continue
        metadata = task.get("metadata") if isinstance(task.get("metadata"), dict) else {}
        prerequisites_value = metadata.get(PREREQUISITES_KEY)
        conditions = None
        if prerequisites_value is not None:
            try:
                conditions = parse_prerequisites(prerequisites_value)
            except UnreadablePrerequisites:
                pass  # due_task_lines names it to the agent
        record = raised.get(task_id) if isinstance(raised.get(task_id), dict) else {}
        raised_as_met = (conditions is not None
                         and prerequisites_raised_as_met(record, prerequisites_value))
        if conditions and not raised_as_met and pull_requests_closed_without_merging(
                pull_request_conditions_not_raised_as_closed(conditions, record), checker):
            unheld.append(task_id)  # its agent must re-plan it, whatever else holds it
            continue
        if task_id in held_by_blockers:
            held += 1
            continue
        if prerequisites_value is not None and not raised_as_met:
            if conditions is None or not all(
                    condition_answer(kind, number, checker).get("met") is True
                    for kind, number in conditions):
                held += 1
                continue
        unheld.append(task_id)
    return sorted(unheld, key=lambda text: (len(text), text)), held


def unheld_tasks_listed_in_start_order(unheld: list, tasks: dict) -> list:
    """The lines listing the unheld tasks in tasks_in_start_order's order under their header, cut
    at the listing limit; none when there is none."""
    return listed_with_limit(
        NEXT_ACTION_UNHELD_TASKS_HEADER,
        [f'task {task_id} "{shortened(tasks[task_id].get("subject", ""))}"'
         for task_id in tasks_in_start_order(unheld, tasks)],
        NEXT_ACTION_LISTED_TASKS_LIMIT)


def listed_with_limit(header: str, entries: list, limit: int) -> list:
    if not entries:
        return []
    lines = [header] + [f"- {entry}" for entry in entries[:limit]]
    if len(entries) > limit:
        lines.append(NEXT_ACTION_MORE_LINE.format(count=len(entries) - limit))
    return lines


def next_action_prompt_lines(payload: dict, tasks: dict, directory: Path, state: dict,
                             checker: "GitHubConditionChecker", now: datetime) -> "list | None":
    """The next-action prompt's lines, or None when the hook stays silent about it.

    Silent when the session cannot be told idle: no readable transcript, no
    checkout with a walk directory, an approval-walk open or paused, a
    handoff asked or deferred, work in flight or work that cannot be counted,
    or no tool run since this hook last gave the prompt in this session.
    Records the prompt in `state` when it returns lines.
    """
    session_id = payload.get("session_id")
    transcript_path = payload.get("transcript_path")
    cwd = payload.get("cwd")
    if not session_id or not transcript_path or not cwd:
        return None
    transcript = Path(transcript_path).expanduser()
    if not transcript.is_file():
        return None
    walk_finder = _load_module_by_path(
        "walk_me_through_approval_walk_minutes_and_walk_document_item_finder_common",
        WALK_FINDER_FILE)
    top = walk_finder.checkout_top(Path(cwd))
    if top is None or not (top / walk_finder.WALK_DIRECTORY).is_dir():
        return None
    walk_directory = top / walk_finder.WALK_DIRECTORY
    if walk_finder.unclosed_approval_walks_including_paused(
            walk_directory, walk_finder.markdown_parser()):
        return None
    handoff = _load_module_by_path("handoff_context_threshold_hook", HANDOFF_THRESHOLD_HOOK_FILE)
    if (handoff.handoff_asked_marker_path(session_id).exists()
            or handoff.deferred_marker_path(session_id).exists()):
        return None
    used_percentage = handoff.context_used_plus_compaction_dropped_percentage_from_transcript(
        str(transcript))
    if used_percentage is not None and used_percentage >= handoff.DEFAULT_THRESHOLD_USED_PERCENTAGE:
        return None
    background_tasks = payload.get(handoff.BACKGROUND_TASKS_PAYLOAD_KEY)
    try:
        if isinstance(background_tasks, list) and handoff.work_in_flight_from_background_tasks(
                background_tasks, str(transcript), now=now):
            return None
    except handoff.TranscriptCouldNotBeFullyRead:
        return None  # running work that cannot be counted is not idleness
    records = _load_module_by_path("claude_code_session_transcript_records_read_backward_common",
                                   TRANSCRIPT_RECORDS_FILE).records_newest_first(transcript)
    tool_use_id = newest_tool_use_id(records)
    recorded = state.get(NEXT_ACTION_STATE_KEY)
    this_prompt = {"session_id": session_id, "newest_tool_use_id": tool_use_id}
    if recorded == this_prompt:
        return None
    state[NEXT_ACTION_STATE_KEY] = this_prompt

    unheld, held = unheld_and_held_tasks(tasks, directory, checker, state["raised"])
    lines = list(NEXT_ACTION_INSTRUCTIONS)
    lines += unheld_tasks_listed_in_start_order(unheld, tasks)
    if held:
        lines.append(NEXT_ACTION_HELD_TASKS_LINE.format(count=held))
    lines += listed_with_limit(NEXT_ACTION_OPEN_ITEMS_HEADER, open_outcome_lines(walk_directory),
                               NEXT_ACTION_LISTED_OPEN_ITEMS_LIMIT)
    lines.append(NEXT_ACTION_STOP_AGAIN_LINE)
    return lines


class HookFault(Exception):
    """A fault the hook reports on stderr instead of raising anything."""


def run(stdin_text: str, environment, home: Path, now: datetime) -> "str | None":
    """The JSON to print, or None for silence; raises on a fault."""
    payload = json.loads(stdin_text)
    if not isinstance(payload, dict):
        raise HookFault("the payload Claude Code sent on stdin is JSON, but not an object, "
                        "so no task was checked")
    if stop_hooks_stay_silent_rule.stop_hook_stays_silent_while_agent_answers_a_stop_hook(payload):
        return None
    if agent_session_unattended_by_user_check_common.agent_session_unattended_by_user(environment):
        return None  # a headless child: the raise would replace the answer its caller reads
    directory = task_list_directory(home, environment)
    if directory is None:
        return None
    tasks = read_tasks(directory)
    state_path = state_file_path(home, directory.name)
    state = read_state(state_path)
    # One checker for the whole run, so its GitHub budget bounds every gh call the run makes.
    checker = GitHubConditionChecker(state["checks"], now.timestamp())
    checker.answer_all_in_one_query(
        github_conditions_the_due_task_pass_asks(tasks, directory, state["raised"]))
    lines, closed_lines, problem_lines, state_changed = due_task_lines(
        tasks, directory, state, checker, running_subagents_and_workflows(payload))
    next_action_lines = []
    if not lines and not closed_lines:
        try:
            next_action_lines = next_action_prompt_lines(payload, tasks, directory, state,
                                                         checker, now) or []
        except Exception as error:
            raise HookFault(f"every task was checked and none was due, but the check whether to "
                            f"hand the next-action prompt failed, so none was handed at this "
                            f"stop: {type(error).__name__}: {error}. The next-action prompt "
                            f"tells an idle agent-seat to start its ready work and build its "
                            f"next approval-walk. Until this hook hands that prompt again, "
                            f"start your ready work and build your next approval-walk yourself "
                            f"whenever no approval-walk is open and none of your work is "
                            f"running. Tell the user this whole message, since the fault is in "
                            f"scripts/agent-seat-due-task-raise-hook.py or in a file it "
                            f"reads.") from error
        state_changed = state_changed or bool(next_action_lines)
    state_changed = state_changed or checker.changed
    gh_failure_lines = [gh_failure_line(kind, number, cause)
                        for kind, number, cause in dict.fromkeys(checker.gh_failures)]
    budget_skipped_lines = budget_skipped_task_lines(
        tasks, checker.conditions_skipped_for_budget, state["raised"])
    if state_changed:
        try:
            write_state_atomically(state_path, state)
        except OSError as error:
            if lines or closed_lines:
                outcome = (f"so {len(lines) + len(closed_lines)} due task(s) were not raised at this stop; the "
                           f"first stop after the state file can be written raises them")
            else:
                outcome = "no task was due at this stop, so none went unraised"
            raise HookFault(f"the state file {state_path} could not be written, and {outcome}. "
                            f"Make {state_path.parent} a directory this user can write to: "
                            f"{error}") from error
    if not lines and not closed_lines and not problem_lines and not next_action_lines:
        if gh_failure_lines:
            raise HookFault(" ".join(gh_failure_lines + budget_skipped_lines))
        if not budget_skipped_lines:
            return None
    # A skipped check is told to the agent as context, never as a fault: a task it skipped may be due.
    defer_lines = [DEFER_INSTRUCTION] if lines else []
    if closed_lines:
        closed_lines += CLOSED_WITHOUT_MERGING_INSTRUCTIONS
    return json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "Stop",
            "additionalContext": "\n".join(lines + defer_lines + closed_lines + problem_lines
                                           + next_action_lines + gh_failure_lines
                                           + budget_skipped_lines),
        }
    }, ensure_ascii=False)


def main() -> int:
    try:
        output = run(sys.stdin.read(), os.environ, Path.home(),
                     datetime.now(timezone.utc))
        if output is not None:
            print(output)
    except HookFault as error:
        print(f"agent-seat-due-task-raise-hook: {error}", file=sys.stderr)
        return 1
    except Exception as error:
        print(f"agent-seat-due-task-raise-hook: the hook failed, so no task was checked at "
              f"this stop; the first stop without this fault raises any task that is due: "
              f"{type(error).__name__}: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
