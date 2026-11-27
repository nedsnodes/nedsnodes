#!/usr/bin/env python3
"""Run one Claude cold-read-cell against a cold-read-target.

One invocation = one cold-read-cell — the twin of the Codex cold-read-cell
launcher (nn-systems/cold-read/cold-read-codex-cell.py). Everything the two do apart
from invoking their model lives in nn-systems/cold-read/cold-read-cell-common.py and is
imported by both, so the legs cannot drift. Read that file for the report
contract, the write-detection rule, and why the reviewer writes a file rather
than answering in chat.

Usage:
  nn-systems/cold-read/cold-read-claude-cell.py --cell defect-hunt --tier second-strongest-model \\
      --target docs/drafts/foo.md \\
      --report cold-read-records/foo-2026-01-01/claude-defect-hunt-second-strongest-model.md

The cold-read-tier `second-strongest-model` asks for the agent-binary's
second-strongest model. The cold-read-tier `fast` runs Claude Sonnet at low
effort.
nn-systems/cold-read/cold-read-fast-read.py runs this tier as its backup when
the Gemini cold-read-cell fails.

The reviewer writes its findings to --report. This program prints progress
to stderr and nothing to stdout.

Exit codes: 0 a model produced a report; 1 every model in the cold-read-tier's
chain failed to produce one; 64 this program refused the invocation and never
launched a model, naming its own fix. 64 rather than the conventional 2 for the
reason written beside EXIT_BAD_INVOCATION in nn-systems/cold-read/cold-read-cell-common.py,
which both cold-read-cells share.

WHY A CLAUDE COLD-READ-CELL'S STAMP CARRIES NO `tokens=` FIELD. Every stamp
records `duration_s=` (user-ruled 2026-08-25), and Codex cold-read-cells also
record `tokens=` because the Codex CLI prints a total. The Claude CLI prints
no equivalent, so there is no figure to record and the field is omitted rather
than filled with a zero -- an omitted field reads as "not reported", a zero
would read as "this cold-read-cell cost nothing". If the CLI starts printing a
"tokens used" line, the shared parser in nn-systems/cold-read/cold-read-cell-common.py picks
it up with no change here.
"""

import importlib.util
import json
import pathlib
import sys

_common_spec = importlib.util.spec_from_file_location(
    "cold_read_cell_common", pathlib.Path(__file__).with_name("cold-read-cell-common.py")
)
common = importlib.util.module_from_spec(_common_spec)
_common_spec.loader.exec_module(common)
_command_line_prefix_spec = importlib.util.spec_from_file_location(
    "claude_code_headless_run_command_line_prefix_with_no_connectors_and_explicit_permission_mode_common",
    pathlib.Path(__file__).resolve().parent.parent / "general-tools"
    / "claude-code-headless-run-command-line-prefix-with-no-connectors-and-explicit-permission-mode-common.py")
command_line_prefix = importlib.util.module_from_spec(_command_line_prefix_spec)
_command_line_prefix_spec.loader.exec_module(command_line_prefix)

PROGRAM = "cold-read-claude-cell"

# No fallback within a tier: each tier must use its pinned model rather than silently substitute a weaker reviewer.
# The fast tier is no such substitute: the fast read runs it only after its Gemini cell fails, and says so.
TIER_TO_CLAUDE_MODEL_CHAIN = {
    "deep": ("claude-opus-5-5",),
    "second-strongest-model": ("claude-fable-5-1",),
    "fast": ("claude-sonnet-5-5",),
}

# Pin effort so results do not depend on the machine's default.
TIER_TO_REASONING_EFFORT = {
    "deep": "xhigh",
    "second-strongest-model": "max",
    "fast": "low",
}

# Write is needed for the report; WebFetch lets the reviewer inspect linked pages.
ALLOWED_TOOLS = "Read,Grep,Glob,Write,WebFetch"

# --allowedTools adds to the user's own allow rules, which may allow some Bash commands; explicitly
# deny both Bash and Monitor to remove shell access, including access to keychain credentials.
DISALLOWED_TOOLS = "Bash,Monitor"

# Disable hooks without disabling CLAUDE.md: hooks can block reports or rebase the reviewed checkout.
# Read deny patterns need // for absolute paths; authentication happens outside model tools.
def credential_read_deny_rules(platform: str = sys.platform) -> list:
    if platform.startswith("linux"):
        return [f"Read(/{path})" for path in common.CREDENTIAL_FILES_ON_NED_BOX
                + tuple(common.reviewer_program_login_files())]
    return ([f"Read(~/{directory.relative_to(pathlib.Path.home())}/**)"
             for directory in common.CREDENTIAL_DIRECTORIES]
            + [f"Read(//**/{pattern})" for pattern in common.CREDENTIAL_FILE_NAME_PATTERNS]
            + [f"Read(/{path})" for path in common.reviewer_program_login_files()])


CREDENTIAL_READ_DENY_RULES = credential_read_deny_rules()
SETTINGS = {"disableAllHooks": True, "permissions": {"deny": CREDENTIAL_READ_DENY_RULES}}
PROMPT_CACHE_FIVE_MINUTE_TTL_SETTINGS = {"promptCacheTtl": "5m"}


def cold_read_cell_launcher_own_command_line_options_adder(parser):
    parser.add_argument(
        "--prompt-cache-five-minute-ttl", action="store_true",
        help='add "promptCacheTtl": "5m" to the run\'s Claude Code settings, so '
             "the run writes 5-minute prompt cache instead of the default 1-hour cache",
    )


def invocation_builder(effort: str, parsed_arguments=None):
    """Return a callback yielding model argv and prompt input for the shared runner."""
    settings = (
        {**SETTINGS, **PROMPT_CACHE_FIVE_MINUTE_TTL_SETTINGS}
        if parsed_arguments is not None and parsed_arguments.prompt_cache_five_minute_ttl
        else SETTINGS)
    # Pass the prompt on stdin: variadic --allowedTools can swallow a trailing positional argument.
    def build_invocation(model: str, prompt: str):
        # dontAsk: a tool call ALLOWED_TOOLS does not allow is refused, with no one to ask.
        command = [
            *command_line_prefix.claude_code_headless_run_command_line_prefix_build(
                "dontAsk", caller_claude_code_session_settings=settings),
            "--model", model,
            "--effort", effort,
            # Stream events as they come, so the agent-binary's output grows while it works;
            # --print takes stream-json only with --verbose.
            "--output-format", "stream-json", "--verbose",
            "--allowedTools", ALLOWED_TOOLS,
            "--disallowedTools", DISALLOWED_TOOLS,
        ]
        return command, prompt
    return build_invocation


def claude_stream_json_stdout_result_event_text_or_stdout(stdout: str) -> str:
    """Return what `--output-format text` prints: the last result event's text and a newline.
    Return stdout as it is when it holds no result event, as when the agent-binary was stopped."""
    for line in reversed(stdout.splitlines()):
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if isinstance(event, dict) and event.get("type") == "result" and isinstance(event.get("result"), str):
            return event["result"] + "\n"
    return stdout


RECOGNISED_FAILURE_TEXTS = (
    common.RecognisedFailureText("logged-out", "Not logged in", common.DETAIL_IS_WHOLE_LINE),
)


def main() -> int:
    return common.run_cell(
        program=PROGRAM, runtime="claude", description=__doc__,
        model_help="explicit Claude model id; overrides the tier mapping",
        tier_to_model_chain=TIER_TO_CLAUDE_MODEL_CHAIN,
        tier_to_effort=TIER_TO_REASONING_EFFORT,
        invocation_builder=invocation_builder,
        recognised_failure_texts=RECOGNISED_FAILURE_TEXTS,
        cold_read_cell_launcher_own_command_line_options_adder=cold_read_cell_launcher_own_command_line_options_adder,
        agent_binary_stdout_to_response_text=claude_stream_json_stdout_result_event_text_or_stdout,
    )


if __name__ == "__main__":
    sys.exit(main())
