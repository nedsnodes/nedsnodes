"""The environment variables the handoff-supervisor sets for each agent-session it launches, shared by the
handoff-supervisor and the hooks that read them, which load this small file instead of handoff-supervisor.py.

A child agent-session, such as a `claude` started from the launched agent-session's shell, inherits all three;
only the launched agent-session's own Claude Code session id equals HANDOFF_SUPERVISOR_SESSION_ID's value, so a
reader that must name the launched agent-session's agent-seat compares the two first.
"""

HANDOFF_SUPERVISOR_AGENT_NAME_ENVIRONMENT_VARIABLE = "NEDSNODES_HANDOFF_SUPERVISOR_AGENT_NAME"
HANDOFF_SUPERVISOR_WORKING_DIRECTORY_ENVIRONMENT_VARIABLE = "NEDSNODES_HANDOFF_SUPERVISOR_WORKING_DIRECTORY"
HANDOFF_SUPERVISOR_SESSION_ID_ENVIRONMENT_VARIABLE = "NEDSNODES_HANDOFF_SUPERVISOR_SESSION_ID"


def handoff_supervisor_launched_agent_seat_name(environment, session_id):
    """The agent-seat the handoff-supervisor launched this agent-session under, or "" when none did, or when
    session_id, the Claude Code session id of the agent-session asking, is not the launched agent-session's."""
    if not session_id or session_id != environment.get(HANDOFF_SUPERVISOR_SESSION_ID_ENVIRONMENT_VARIABLE, ""):
        return ""
    return environment.get(HANDOFF_SUPERVISOR_AGENT_NAME_ENVIRONMENT_VARIABLE, "").strip()
