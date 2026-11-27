#!/usr/bin/env python3
"""Refuse `gh api graphql --paginate` when its query has no `$endCursor` variable.

gh's --paginate sets only a variable named endCursor to the last page's
pageInfo.endCursor. A query whose cursor variable has another name, such as
$c, is sent unchanged each time, so gh fetches the first page again and again
and never stops.

The query is read from -f, --raw-field, -F or --field, as query=<text>, or,
for -F and --field, as query=@<file>, a relative file read from the Bash
call's working directory. The command is let through when its query text
cannot be read: a file that cannot be read, @- for standard input, a query
given only by --input, or a query word holding a shell expansion, such as
query="$QUERY" or query="$(cat q.graphql)", whose text the shell decides at
run time. One such word lets through every gh command of the same command
line.

Commands are read with the shared shell reader on tree-sitter-bash, past
wrappers such as env and timeout, and the command string of bash, sh or zsh -c
and the remote command of ssh are read the same way; a query file named in an
ssh remote command is on the other machine and is not read.
"""

# Deferred annotations let the hook load on the Mac's system Python 3.9.
from __future__ import annotations

import importlib.util
import json
import os
import re
import sys
from pathlib import Path

_crash_notice_spec = importlib.util.spec_from_file_location(
    "guard_hook_crash_fail_open_with_notice_common",
    Path(__file__).resolve().parent / "guard-hook-crash-fail-open-with-notice-common.py")
_crash_notice = importlib.util.module_from_spec(_crash_notice_spec)
_crash_notice_spec.loader.exec_module(_crash_notice)

with _crash_notice.guard_hook_crash_fail_open_with_notice_context_manager(
        __file__, __name__ == "__main__"):
    _shell_reader_spec = importlib.util.spec_from_file_location(
        "shell_command_tree_sitter_bash_reader_common",
        Path(__file__).resolve().parents[2] / "nn-systems" / "general-tools"
        / "shell-command-tree-sitter-bash-reader-common.py")
    shell_reader = importlib.util.module_from_spec(_shell_reader_spec)
    _shell_reader_spec.loader.exec_module(shell_reader)
is_program = shell_reader.is_program

GH_API_FIELD_OPTIONS_READING_FILES = {"-F", "--field"}
GH_API_FIELD_OPTIONS = GH_API_FIELD_OPTIONS_READING_FILES | {"-f", "--raw-field"}
GH_API_OPTIONS_TAKING_A_VALUE = GH_API_FIELD_OPTIONS | {
    "-H", "--header", "-X", "--method", "--input", "-q", "--jq", "-t", "--template",
    "--hostname", "--cache", "-p", "--preview"}
GH_API_SHORT_OPTIONS_TAKING_A_VALUE = {option for option in GH_API_OPTIONS_TAKING_A_VALUE
                                       if not option.startswith("--")}
END_CURSOR_VARIABLE_PATTERN = re.compile(r"\$endCursor\b")
SHELL_EXPANSION_NODE_TYPES = {"simple_expansion", "expansion", "command_substitution",
                              "process_substitution", "arithmetic_expansion"}

GH_API_GRAPHQL_PAGINATE_WITHOUT_END_CURSOR_REFUSAL = (
    "[rule bash-guard-gh-api-graphql-paginate-without-endcursor-variable] Refused: `gh api graphql "
    "--paginate` advances only a variable named `$endCursor`, and this query has none, so gh would fetch "
    "the first page again and again. Name the query's cursor variable `$endCursor`, adding one, with "
    "`pageInfo { endCursor hasNextPage }`, if the query has none.")

PARSER_UNAVAILABLE_NEXT_STEP_LINES = (
    "If the command ran `gh api graphql --paginate` with a query that has no `$endCursor` variable "
    "and it is still running, stop it, because gh is fetching the first page again and again, and "
    "run it again with the query's cursor variable named `$endCursor`.\n"
    "Otherwise use its output as it is.")


def gh_api_arguments_read(arguments):
    """Return (endpoint, paginates, [(field option, field value), ...]) for the words after `gh api`."""
    endpoint, paginates, fields = None, False, []
    index = 0
    while index < len(arguments):
        word = arguments[index]
        index += 1
        if word == "--":
            endpoint = endpoint or (arguments[index] if index < len(arguments) else None)
            break
        if word == "--paginate":
            paginates = True
            continue
        if word.startswith("--") and "=" in word:
            option, value = word.split("=", 1)
        elif word in GH_API_OPTIONS_TAKING_A_VALUE:
            option = word
            value = arguments[index] if index < len(arguments) else None
            index += 1
        elif word[:2] in GH_API_SHORT_OPTIONS_TAKING_A_VALUE and len(word) > 2:
            option, value = word[:2], word[2:]
        elif word.startswith("-"):
            continue
        else:
            endpoint = endpoint or word
            continue
        if option in GH_API_FIELD_OPTIONS and value is not None:
            fields.append((option, value))
    return endpoint, paginates, fields


def query_text(fields, working_directory):
    """Return the text of the last query field, or None when it cannot be read."""
    queries = [(option, value[len("query="):]) for option, value in fields if value.startswith("query=")]
    if not queries:
        return None
    option, value = queries[-1]
    if option not in GH_API_FIELD_OPTIONS_READING_FILES or not value.startswith("@"):
        return value
    path = value[1:]
    if path == "-" or working_directory is None:
        return None
    try:
        return Path(os.path.join(working_directory, path)).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def query_word_holds_shell_expansion(command):
    """Return whether an argument word holding query= has an expansion the shell fills in at run time.

    The shell reader keeps an expansion as written, so its words cannot tell "$Q" from the
    single-quoted '$c' of a GraphQL variable; the syntax tree can.
    """
    tree = shell_reader.parser().parse(command.encode("utf-8"))
    pending = [tree.root_node]
    while pending:
        node = pending.pop()
        if node.parent is not None and node.parent.type == "command" and b"query=" in node.text:
            inside = [node]
            while inside:
                part = inside.pop()
                if part.type in SHELL_EXPANSION_NODE_TYPES:
                    return True
                inside.extend(part.children)
        pending.extend(node.children)
    return False


def nested_command_string(program, arguments):
    if is_program(program, "ssh"):
        return shell_reader.ssh_remote_command(arguments)
    if any(is_program(program, runner) for runner in shell_reader.SHELL_STRING_RUNNERS):
        return shell_reader.shell_command_string(arguments)
    return None


def refusal_for(command, working_directory):
    """Return the refusal for command, or None; working_directory None reads no query file."""
    for words in shell_reader.simple_commands(command):
        words = list(words)
        index, _ = shell_reader.simple_command_program_index_skipping_wrappers(words)
        if index is None:
            continue
        program, arguments = words[index], words[index + 1:]
        inner = nested_command_string(program, arguments)
        if inner is not None:
            reason = refusal_for(inner, None if is_program(program, "ssh") else working_directory)
            if reason:
                return reason
            continue
        if not is_program(program, "gh") or arguments[:1] != ["api"]:
            continue
        endpoint, paginates, fields = gh_api_arguments_read(arguments[1:])
        if endpoint != "graphql" or not paginates:
            continue
        text = query_text(fields, working_directory)
        if (text is not None and not END_CURSOR_VARIABLE_PATTERN.search(text)
                and not query_word_holds_shell_expansion(command)):
            return GH_API_GRAPHQL_PAGINATE_WITHOUT_END_CURSOR_REFUSAL
    return None


def deny(reason):
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "deny",
        "permissionDecisionReason": reason,
    }}))


def main(stdin=sys.stdin):
    payload = json.load(stdin)
    if not isinstance(payload, dict) or payload.get("tool_name") != "Bash":
        return 0
    command = (payload.get("tool_input") or {}).get("command")
    if not isinstance(command, str):
        return 0
    working_directory = payload.get("cwd")
    if not isinstance(working_directory, str):
        working_directory = os.getcwd()
    try:
        reason = refusal_for(command, working_directory)
    except shell_reader.ShellParserUnavailable as error:
        print(shell_reader.parser_unavailable_hook_output(
            "The gh api graphql --paginate guard", error, PARSER_UNAVAILABLE_NEXT_STEP_LINES))
        return 0
    if reason:
        deny(reason)
    return 0


if __name__ == "__main__":
    with _crash_notice.guard_hook_crash_fail_open_with_notice_context_manager(__file__, True):
        sys.exit(main())
