#!/usr/bin/env python3
"""Name, once for every program, how many subagents and workflows an agent-seat is told it may run
at once: the due-task Stop hook names no approved ready task while this many run, and its
reminders and the handoff-supervisor's first prompt state the number.

The user set the number; change it only with his approval.

Load it by path, under the snake_case form of its file name:

    spec = importlib.util.spec_from_file_location(
        "agent_seat_subagents_and_workflows_running_at_once_limit_constant_common", <path>)
"""

SUBAGENTS_AND_WORKFLOWS_RUNNING_AT_ONCE_LIMIT = 3
