#!/usr/bin/env python3
"""Tests for .claude/guard-hooks/gh-api-graphql-paginate-without-endcursor-variable-refusal-hook.py.

Each case drives main() with the JSON payload the harness sends, and two cases
pipe a payload into the hook as a real process.

Run: python3 .claude/guard-hooks/gh-api-graphql-paginate-without-endcursor-variable-refusal-hook-test.py
Prints one line per case and exits non-zero if any case fails.
"""

import contextlib
import importlib.util
import io
import json
import subprocess
import sys
import tempfile
from pathlib import Path

HOOK_SCRIPT = Path(__file__).with_name("gh-api-graphql-paginate-without-endcursor-variable-refusal-hook.py")
_spec = importlib.util.spec_from_file_location("gh_api_graphql_paginate_refusal", HOOK_SCRIPT)
hook = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(hook)

failures = []


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


def hook_output(payload_text):
    stdout = io.StringIO()
    with contextlib.redirect_stdout(stdout):
        code = hook.main(stdin=io.StringIO(payload_text))
    return code, stdout.getvalue().strip()


def refused(command, cwd, tool_name="Bash"):
    code, text = hook_output(json.dumps({"tool_name": tool_name, "cwd": cwd, "tool_input": {"command": command}}))
    if code != 0:
        return f"<exit {code}>"
    if not text:
        return False
    output = json.loads(text)["hookSpecificOutput"]
    return (output.get("permissionDecision") == "deny"
            and output.get("permissionDecisionReason") == hook.GH_API_GRAPHQL_PAGINATE_WITHOUT_END_CURSOR_REFUSAL)


# The command of 2026-11-24 that refetched page 1 for 35 minutes, shortened.
QUERY_WITH_C = ("query($c:String){repository(owner:\"nedsnodes\",name:\"nedsnodes\"){pullRequests(states:OPEN,"
                "first:100,after:$c){pageInfo{hasNextPage endCursor} nodes{number}}}}")
QUERY_WITH_END_CURSOR = QUERY_WITH_C.replace("$c", "$endCursor")

with tempfile.TemporaryDirectory() as directory:
    Path(directory, "c.graphql").write_text(QUERY_WITH_C, encoding="utf-8")
    Path(directory, "end-cursor.graphql").write_text(QUERY_WITH_END_CURSOR, encoding="utf-8")
    Path(directory, "not-utf-8.graphql").write_bytes(b"\xff\xfe query")

    REFUSED = [
        ("the $c query of 2026-11-24, as -f query='...'", f"gh api graphql --paginate -f query='{QUERY_WITH_C}'"),
        ("--paginate after the query", f"gh api graphql -f query='{QUERY_WITH_C}' --paginate"),
        ("--raw-field query=...", f"gh api graphql --paginate --raw-field query='{QUERY_WITH_C}'"),
        ("--raw-field=query=...", f"gh api graphql --paginate --raw-field='query={QUERY_WITH_C}'"),
        ("-fquery=... attached", f"gh api graphql --paginate -fquery='{QUERY_WITH_C}'"),
        ("-F query=@file whose query has $c", "gh api graphql --paginate -F query=@c.graphql"),
        ("--field query=@file by absolute path", f"gh api graphql --paginate --field query=@{directory}/c.graphql"),
        ("piped into head, as on 2026-11-24", f"gh api graphql --paginate -f query='{QUERY_WITH_C}' | head -300"),
        ("behind timeout", f"timeout 60 gh api graphql --paginate -f query='{QUERY_WITH_C}'"),
        ("inside bash -c", f"bash -c \"gh api graphql --paginate -f query='{QUERY_WITH_C}'\""),
        ("inside an ssh remote command", f"ssh nedlern@ned-box \"gh api graphql --paginate -f query='{QUERY_WITH_C}'\""),
        ("a double-quoted query with no expansion",
         "gh api graphql --paginate -f query=\"query(\\$c:String){viewer{repositories(first:100,after:\\$c)"
         "{pageInfo{endCursor hasNextPage} nodes{name}}}}\""),
    ]
    for name, command in REFUSED:
        check(f"refused: {name}", refused(command, directory) is True, command)

    ALLOWED = [
        ("a query with $endCursor", f"gh api graphql --paginate -f query='{QUERY_WITH_END_CURSOR}'"),
        ("-F query=@file whose query has $endCursor", "gh api graphql --paginate -F query=@end-cursor.graphql"),
        ("no --paginate", f"gh api graphql -f query='{QUERY_WITH_C}'"),
        ("a REST endpoint with --paginate", "gh api repos/nedsnodes/nedsnodes/pulls --paginate -f state=open"),
        ("graphql only as a field value", f"gh api repos/x/y --paginate -f note=graphql -f query='{QUERY_WITH_C}'"),
        ("a query file that does not exist", "gh api graphql --paginate -F query=@missing.graphql"),
        ("a query file that is not UTF-8", "gh api graphql --paginate -F query=@not-utf-8.graphql"),
        ("a query on standard input", f"echo '{QUERY_WITH_C}' | gh api graphql --paginate -F query=@-"),
        ("a query file named in an ssh remote command", "ssh nedlern@ned-box 'gh api graphql --paginate -F query=@c.graphql'"),
        ("a query given only by --input", "gh api graphql --paginate --input body.json"),
        ("a query in a shell variable", "gh api graphql --paginate -f query=\"$QUERY\""),
        ("a query in an unquoted shell variable", "gh api graphql --paginate -f query=$QUERY"),
        ("a query from a command substitution", "gh api graphql --paginate -f query=\"$(cat c.graphql)\""),
        ("a query with a shell variable inside it",
         "gh api graphql --paginate -f query=\"query(\\$c:String){repository(owner:\\\"$OWNER\\\")"
         "{pullRequests(after:\\$c){nodes{number}}}}\""),
        ("gh api graphql --paginate as text in a grep pattern", "grep -n 'gh api graphql --paginate -f query=x' notes.md"),
        ("an echo of the command", f"echo gh api graphql --paginate -f query='{QUERY_WITH_C}'"),
    ]
    for name, command in ALLOWED:
        check(f"allowed: {name}", refused(command, directory) is False, command)

    check("a tool other than Bash is ignored",
          refused(f"gh api graphql --paginate -f query='{QUERY_WITH_C}'", directory, tool_name="Read") is False)

    for name, payload_text in [("a payload that is a JSON list", "[]"),
                               ("a command that is not a string",
                                json.dumps({"tool_name": "Bash", "tool_input": {"command": ["gh", "api"]}})),
                               ("a payload with no tool_input", json.dumps({"tool_name": "Bash"}))]:
        code, text = hook_output(payload_text)
        check(f"{name} exits 0 and prints nothing", code == 0 and text == "", f"exit {code}, stdout {text!r}")

    saved_simple_commands = hook.shell_reader.simple_commands

    def parser_missing(*_arguments, **_keywords):
        raise hook.shell_reader.ShellParserUnavailable("pip: no network")

    hook.shell_reader.simple_commands = parser_missing
    try:
        code, text = hook_output(json.dumps({"tool_name": "Bash", "cwd": directory, "tool_input": {
            "command": f"gh api graphql --paginate -f query='{QUERY_WITH_C}'"}}))
    finally:
        hook.shell_reader.simple_commands = saved_simple_commands
    output = json.loads(text or "{}").get("hookSpecificOutput", {})
    check("without the shell parser the hook exits 0, lets the command through and says so",
          code == 0 and "permissionDecision" not in output
          and "gh api graphql --paginate guard" in output.get("additionalContext", "")
          and "pip: no network" in output.get("additionalContext", ""), repr(output))

    process = subprocess.run(
        [sys.executable, str(HOOK_SCRIPT)],
        input=json.dumps({"tool_name": "Bash", "cwd": directory, "tool_input": {
            "command": f"gh api graphql --paginate -f query='{QUERY_WITH_C}'"}}),
        capture_output=True, text=True, check=False, timeout=60)
    decision = json.loads(process.stdout)["hookSpecificOutput"] if process.stdout.strip() else {}
    check("as a process, the hook denies the $c query and exits 0",
          process.returncode == 0 and decision.get("permissionDecision") == "deny",
          f"exit {process.returncode}, stdout {process.stdout!r}, stderr {process.stderr!r}")

    process = subprocess.run(
        [sys.executable, str(HOOK_SCRIPT)],
        input=json.dumps({"tool_name": "Bash", "cwd": directory, "tool_input": {
            "command": f"gh api graphql --paginate -f query='{QUERY_WITH_END_CURSOR}'"}}),
        capture_output=True, text=True, check=False, timeout=60)
    check("as a process, the hook allows the $endCursor query silently",
          process.returncode == 0 and not process.stdout.strip(),
          f"exit {process.returncode}, stdout {process.stdout!r}, stderr {process.stderr!r}")

if failures:
    print(f"{len(failures)} case(s) failed: " + ", ".join(failures))
    sys.exit(1)
print("all cases passed")
