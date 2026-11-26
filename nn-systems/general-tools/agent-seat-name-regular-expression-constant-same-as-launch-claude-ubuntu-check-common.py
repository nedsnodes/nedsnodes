"""The agent-seat names scripts/launch-claude-ubuntu accepts, for every Python program that checks one.

Match a name with AGENT_SEAT_NAME_PATTERN.fullmatch, never match or search: `$` would let a trailing newline
through, which the launcher refuses. scripts/mac-request-from-ned-box-forced-command-test.py runs the launcher's
own check on a list of names and fails when it and this pattern disagree on one.
"""
import re

AGENT_SEAT_NAME_PATTERN = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_-]*")
