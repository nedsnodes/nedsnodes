---
issue: "[The stop-typing notice names the agent-seat whose shell started a child agent-session, as if the child were that agent-seat](https://github.com/nedsnodes/nedsnodes/issues/4841)"
---

# The stop-typing notice names the agent-seat whose shell started a child agent-session, as if the child were that agent-seat

## Reproduction

Codex reproduced this on main on 2026-11-25, in its review of [PR 4826](https://github.com/nedsnodes/nedsnodes/pull/4826), as Codex finding 72466ebc531a. merge-lane-2's review [6064208254](https://github.com/nedsnodes/nedsnodes/pull/4826#pullrequestreview-6064208254) grades it fix-next: a defect to fix in a follow-up pull request, which does not hold a merge. Steps:

1. In an agent-seat's shell on ned-box, where the handoff-supervisor has set `NEDSNODES_HANDOFF_SUPERVISOR_AGENT_NAME`, start a second `claude`. The child agent-session inherits the variable.
2. Let the child agent-session reach its own handoff threshold while it has no custom title.
3. Type a prompt in the child agent-session. The UserPromptSubmit hook `nn-systems/handoff/handoff-asked-stop-typing-user-notice-user-prompt-submit-hook.py` tells the user to type in the parent agent-seat's new agent-session, not the child's.

## Why it happens

`launched_agent_seat_name()`, at line 73 of the hook on main at ef94e0ca4, reads `NEDSNODES_HANDOFF_SUPERVISOR_AGENT_NAME` from the environment. `new_session_name()` uses it at line 89 when the transcript gives no title. Nothing checks that the hook payload's `session_id` belongs to the agent-session the handoff-supervisor launched. So any agent-session that inherited the variable is taken for the agent-seat.

## Why it matters

The notice sends the user to the wrong agent-session. A message he types there reaches an agent-seat that did not ask him to stop typing.

## What to do

PR 4826, open when this was written, adds the function `handoff_supervisor_launched_agent_session_agent_seat_name_or_empty_for_another_session` to `nn-systems/handoff/handoff-supervisor-launched-agent-session-environment-variable-names-common.py`. PR 4826 uses that function in the user-alert claim hook and the claude.ai rename Stop hook, as a pattern to follow. Once PR 4826 merges, call the same function with the payload's `session_id` in the stop-typing hook. When the function returns empty, the hook gives the notice it gives an agent-session that no handoff-supervisor launched, which names no agent-seat. Add a test, beside the hook's existing tests, in which the variable is set but the payload's `session_id` belongs to another agent-session, and which checks that the notice names no agent-seat. The agent-seat ned-box-helper, which wrote that function, owns this fix.

## Outcome

Fixed by [PR 4851, "Stop-typing notice names an agent-seat only in the agent-session the handoff-supervisor launched"](https://github.com/nedsnodes/nedsnodes/pull/4851), merged 2026-11-25. The hook now calls `handoff_supervisor_launched_agent_session_agent_seat_name_or_empty_for_another_session` with the payload's `session_id`, and its test file has a case in which the variable is set but the `session_id` belongs to another agent-session; that case fails on the code before the fix and passes after it.
