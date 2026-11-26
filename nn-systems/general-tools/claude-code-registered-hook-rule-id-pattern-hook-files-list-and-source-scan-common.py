#!/usr/bin/env python3
"""The rule IDs of the Claude Code hooks .claude/settings.json registers.

Each message a registered hook prints for a rule, a refusal, a warning or a
reminder, starts with that rule's ID, written `[rule <id>]` and followed by one
space, where <id> is lowercase words joined by hyphens. A message that says the
hook failed, or could not check and let the act through, carries no ID, so a
check that never ran is never counted as the rule firing.

The ID is written whole, as literal text, at the start of the message's text in
the hook's own source, so a search for the ID finds the rule.

scripts/registered-hook-rule-messages-start-with-unique-rule-id-test.py and
nn-systems/general-tools/claude-code-registered-hook-rule-ids-in-both-machines-transcripts-weekly-count-and-never-seen-rules-report.py
load this file with importlib.util.spec_from_file_location, because Python
cannot import a hyphenated file name by name.
"""

import json
import re
from pathlib import Path

RULE_ID_WORDS = r"[a-z0-9]+(?:-[a-z0-9]+)*"
RULE_ID_PATTERN = re.compile(r"\[rule (" + RULE_ID_WORDS + r")\]")
RULE_ID_OPENING_PATTERN = re.compile(r"\[rule (" + RULE_ID_WORDS + r")\] ")
# A `\[rule` is a regular expression that matches an ID, not an ID.
RULE_ID_LIKE_PATTERN = re.compile(r"(?<!\\)\[rule\b[^\]\n]*\]?")
CLAUDE_PROJECT_DIRECTORY_PREFIXES = ('"$CLAUDE_PROJECT_DIR"/', "$CLAUDE_PROJECT_DIR/")
BASH_GUARD_HOOKS_DISPATCHER = ".claude/guard-hooks/bash-guard-hooks-dispatcher.py"
BASH_GUARD_HOOKS_DISPATCHER_GUARD_LIST = ".claude/guard-hooks/bash-guard-hooks-dispatcher-guard-list.json"


def registered_hook_paths(settings_path):
    """The repository-relative paths of the Python hook files the settings file registers, each once, in order."""
    settings = json.loads(Path(settings_path).read_text(encoding="utf-8"))
    paths = []
    for event_matchers in settings.get("hooks", {}).values():
        for matcher in event_matchers:
            for hook in matcher.get("hooks", []):
                for word in hook.get("command", "").split():
                    for prefix in CLAUDE_PROJECT_DIRECTORY_PREFIXES:
                        word = word.replace(prefix, "")
                    word = word.strip("\"'")
                    if word.endswith(".py") and word not in paths:
                        paths.append(word)
    if BASH_GUARD_HOOKS_DISPATCHER in paths:
        # The dispatcher runs the guards its guard list names, and their messages carry the rule IDs.
        list_path = Path(settings_path).resolve().parents[1] / BASH_GUARD_HOOKS_DISPATCHER_GUARD_LIST
        for entry in json.loads(list_path.read_text(encoding="utf-8"))["guards"]:
            if entry["path"] not in paths:
                paths.append(entry["path"])
    return paths


def rule_id_at_message_start(text):
    """The rule ID a message's text starts with, or None."""
    match = RULE_ID_OPENING_PATTERN.match(text)
    return match.group(1) if match else None


def rule_ids_in_source(source):
    """{rule ID: [line, ...]} for every `[rule <id>]` written in the source, lines counted from 1."""
    found = {}
    for line_number, line in enumerate(source.splitlines(), start=1):
        for match in RULE_ID_PATTERN.finditer(line):
            found.setdefault(match.group(1), []).append(line_number)
    return found


def malformed_rule_ids_in_source(source):
    """(line, text) for each `[rule` written in the source that is not a well-formed `[rule <id>]`."""
    malformed = []
    for line_number, line in enumerate(source.splitlines(), start=1):
        for match in RULE_ID_LIKE_PATTERN.finditer(line):
            if not RULE_ID_PATTERN.fullmatch(match.group(0)):
                malformed.append((line_number, match.group(0)))
    return malformed

