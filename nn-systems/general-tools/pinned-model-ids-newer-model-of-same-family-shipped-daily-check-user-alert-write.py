#!/usr/bin/env python3
"""Write a user-alert naming each pinned model id for which a newer model of its family has shipped.

    python3 <this file>

A pin is a Python string literal whose whole value is a model id, in a file `git ls-files` lists in this
program's checkout, test files left out (as path_is_test_file in
nn-systems/general-tools/python-source-tool-message-to-agent-string-collector-common.py decides). A model id is
one of:
    gpt-<version>-<name>          family gpt-*-<name>, listed by `codex debug models`
    gemini-<version>-<name>[-…]   family gemini-*-<name>[-…], listed by `agy models`
    claude-<name>-<major>-<minor> family <name>, the newest being the model `claude --model <name>` runs
Within a family the highest version is the newest, compared as numbers part by part. A pin whose source line
carries `pin kept: <reason>` is skipped. The program changes no pin.

It writes up to two user-alerts, through
nn-systems/general-tools/user-alerts-pending-and-claimed-files-write-claim-release-and-delete-common.py:
one with a line per pin older than the newest of its family, and one naming each agent-binary that could not
list its models (not found, exit not 0, timed out, or output it cannot parse) and each pin whose family no
listing holds. A pin whose agent-binary failed is named only in the second. It keeps no state, so the alerts
come again each day until the pins are updated or marked.

It runs once a day on ned-box, from the table nn-systems/general-tools/scheduled-jobs-on-each-machine.json,
which nn-systems/general-tools/install-scheduled-jobs-on-this-machine.py installs as this cron line:
    45 7 * * * /usr/bin/python3 /home/nedlern/Projects/nedsnodes/nn-systems/general-tools/pinned-model-ids-newer-model-of-same-family-shipped-daily-check-user-alert-write.py >> /home/nedlern/.claude/pinned-model-ids-newer-model-of-same-family-shipped-daily-check-user-alert-write.log 2>&1
Each Claude family pinned costs one short `claude -p` call.

Exit status: 0 when every pin was checked and any alert needed was written. 1 when a pin could not be
checked, the search for pins failed, or an alert could not be written; an error the program cannot put in a
user-alert is printed only, to the cron log above.
"""
import argparse
import ast
import importlib.util
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[2]
GENERAL_TOOLS = REPOSITORY / "nn-systems" / "general-tools"


def _load(name, path):
    specification = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


user_alerts = _load("user_alerts_pending_and_claimed_files_write_claim_release_and_delete_common",
                    GENERAL_TOOLS / "user-alerts-pending-and-claimed-files-write-claim-release-and-delete-common.py")
headless = _load(
    "claude_code_headless_run_command_line_prefix_with_no_connectors_and_explicit_permission_mode_common",
    GENERAL_TOOLS / "claude-code-headless-run-command-line-prefix-with-no-connectors-and-explicit-permission-mode-common.py")
string_collector = _load("python_source_tool_message_to_agent_string_collector_common",
                         GENERAL_TOOLS / "python-source-tool-message-to-agent-string-collector-common.py")

THIS_PROGRAM = "nn-systems/general-tools/pinned-model-ids-newer-model-of-same-family-shipped-daily-check-user-alert-write.py"
CODEX, AGY, CLAUDE = "codex", "agy", "claude"
MODEL_ID_PATTERNS = {
    CODEX: re.compile(r"gpt-(?P<version>\d+(?:\.\d+)*)-(?P<family>[a-z]+)"),
    AGY: re.compile(r"gemini-(?P<version>\d+(?:\.\d+)*)-(?P<family>[a-z]+(?:-[a-z]+)*)"),
    CLAUDE: re.compile(r"claude-(?P<family>[a-z]+)-(?P<version>\d+-\d+)"),
}
LISTING_COMMANDS = {CODEX: "codex debug models", AGY: "agy models"}
PIN_KEPT = re.compile(r"pin kept: \S")
LISTING_TIMEOUT_SECONDS = 300
OUTPUT_SHOWN_CHARACTERS = 600
# Cron's PATH holds neither, and the agent-binaries are installed there on ned-box.
AGENT_BINARY_DIRECTORIES_OUTSIDE_CRON_PATH = (Path.home() / ".local" / "bin", Path("/usr/local/bin"))
CLAUDE_ALIAS_PROBE_PROMPT = "Reply with the single word ok."

# Messages below follow docs/nedsnodes-wiki/nedsnodes-how-to-write-a-tool-message-to-agent-such-as-a-hook-refusal-or-script-error.md.
STALE_TITLE = "A newer model has shipped for a pinned model id"
STALE_LINE = ("A newer model has shipped for a pinned model id: {file}:{line} pins {id}; the newest of its family is "
              "{newer}. Update the pin in a pull request, or add `pin kept: <reason>` to its line.")
STALE_ACTION = "Update each pin named in a pull request, or add `pin kept: <reason>` to its line."
UNCHECKED_TITLE = "The daily check for newer models could not check every pinned model id"
AGENT_BINARY_FAILED_LINE = "`{command}` could not list its models, so pins of {families} went unchecked: {reason}"
FAMILY_NOT_LISTED_LINE = ("{file}:{line} pins {id}, but `{command}` lists no model of its family, so it went "
                          "unchecked; the family may be retired, or the id mistyped.")
UNCHECKED_ACTION = (
    "For each agent-binary that could not list its models: an agent on ned-box runs the command named by hand and "
    "reads what it prints. When it says the agent-binary is logged out, tell the user, quoting what it printed, that "
    "this agent-binary on ned-box is logged out, so its pinned models go unchecked; he logs it in from a Terminal on "
    "his Mac with ssh nedlern@ned-box. Otherwise fix the cause it prints.\n"
    "For each pin whose family no listing holds: update the pin in a pull request, or add `pin kept: <reason>` to "
    "its line.\n"
    f"Then run python3 {THIS_PROGRAM} on ned-box again; it exits 0 when every pin was checked.")
SEARCH_FAILED_TITLE = "The daily search of main's code for pinned model ids failed"
SEARCH_FAILED_ACTION = (f"An agent on ned-box runs python3 {THIS_PROGRAM} by hand, reads the error it prints, and "
                        "fixes its cause; until then no pinned model id is checked for a newer model.")


@dataclass(frozen=True)
class Pin:
    file: str
    line: int
    model_id: str
    agent_binary: str
    family: str
    version: tuple


class AgentBinaryCannotListModels(Exception):
    pass


def model_id_parts(text):
    """(agent_binary, family, version) when text is wholly a model id, else None."""
    for agent_binary, pattern in MODEL_ID_PATTERNS.items():
        match = pattern.fullmatch(text)
        if match:
            version = tuple(int(part) for part in re.split(r"[.-]", match["version"]))
            return agent_binary, match["family"], version
    return None


def pins_in_code(repository):
    """Every pin in the Python files git lists in repository, outside tests, not marked `pin kept:`.

    Raises OSError, SyntaxError, UnicodeDecodeError or subprocess.CalledProcessError when the search cannot finish."""
    listed = subprocess.run(["git", "-C", str(repository), "ls-files", "-z", "--", "*.py"],
                            capture_output=True, check=True).stdout.decode()
    pins = set()
    for relative in filter(None, listed.split("\0")):
        if string_collector.path_is_test_file(relative):
            continue
        source = (repository / relative).read_text(encoding="utf-8")
        lines = source.splitlines()
        for node in ast.walk(ast.parse(source, filename=relative)):
            if not (isinstance(node, ast.Constant) and isinstance(node.value, str)):
                continue
            parts = model_id_parts(node.value)
            if parts and not PIN_KEPT.search(lines[node.lineno - 1]):
                pins.add(Pin(relative, node.lineno, node.value, *parts))
    return sorted(pins, key=lambda pin: (pin.file, pin.line, pin.model_id))


def agent_binary_path(name):
    search_path = os.pathsep.join([os.environ.get("PATH", ""), *map(str, AGENT_BINARY_DIRECTORIES_OUTSIDE_CRON_PATH)])
    return shutil.which(name, path=search_path)


def _shown(text):
    text = text.strip()
    return text if len(text) <= OUTPUT_SHOWN_CHARACTERS else text[:OUTPUT_SHOWN_CHARACTERS] + " …"


def listing_output(command, run_command, cwd=None):
    """The standard output of command, or AgentBinaryCannotListModels saying why there is none."""
    try:
        result = run_command(command, capture_output=True, text=True, timeout=LISTING_TIMEOUT_SECONDS, cwd=cwd)
    except subprocess.TimeoutExpired:
        raise AgentBinaryCannotListModels(f"it did not finish within {LISTING_TIMEOUT_SECONDS} seconds") from None
    except OSError as error:
        raise AgentBinaryCannotListModels(f"it could not be started: {error!r}") from None
    if result.returncode != 0:
        raise AgentBinaryCannotListModels(
            f"it exited {result.returncode}, printing: {_shown(result.stdout + result.stderr) or '(nothing)'}")
    return result.stdout


def newest_by_family(model_ids, agent_binary):
    """{family: (version, model id)} for the highest version of each family among model_ids."""
    newest = {}
    for model_id in model_ids:
        parts = model_id_parts(model_id)
        if parts and parts[0] == agent_binary and (parts[1] not in newest or parts[2] > newest[parts[1]][0]):
            newest[parts[1]] = (parts[2], model_id)
    return newest


def codex_models(output):
    try:
        models = json.loads(output)["models"]
        slugs = [model["slug"] for model in models]
    except (ValueError, KeyError, TypeError) as error:
        raise AgentBinaryCannotListModels(
            f"its output is not the JSON object of models it should print ({error!r}): {_shown(output)}") from None
    newest = newest_by_family(slugs, CODEX)
    if not newest:
        raise AgentBinaryCannotListModels(f"its output lists no gpt-<version>-<name> model: {_shown(output)}")
    return newest


def agy_models(output):
    # Each model is a line `<id>\t<display name>`, after a line saying the models are being fetched.
    ids = [line.split("\t", 1)[0] for line in output.splitlines() if "\t" in line]
    newest = newest_by_family(ids, AGY)
    if not newest:
        raise AgentBinaryCannotListModels(f"its output lists no gemini-<version>-<name> model: {_shown(output)}")
    return newest


def claude_alias_model(output, family):
    """The id of the one model of family the JSON result of a `claude -p --output-format json` run used."""
    try:
        used = list(json.loads(output)["modelUsage"])
    except (ValueError, KeyError, TypeError) as error:
        raise AgentBinaryCannotListModels(
            f"its output is not the JSON result it should print ({error!r}): {_shown(output)}") from None
    matches = [match for match in map(MODEL_ID_PATTERNS[CLAUDE].match, used) if match and match["family"] == family]
    if len(matches) != 1:
        raise AgentBinaryCannotListModels(
            f"its result names {len(matches)} models of the family {family}, not one: {_shown(output)}")
    parts = model_id_parts(matches[0][0])
    return {family: (parts[2], matches[0][0])}


def listings(pins, run_command):
    """{(agent_binary, family): (version, newest id)}, and (agent_binary, command, families, reason) per failure."""
    newest, failures = {}, []
    families_by_binary = {}
    for pin in pins:
        families_by_binary.setdefault(pin.agent_binary, set()).add(pin.family)
    requests = []
    if CODEX in families_by_binary:
        requests.append((CODEX, LISTING_COMMANDS[CODEX].split()[1:], codex_models, sorted(families_by_binary[CODEX])))
    if AGY in families_by_binary:
        requests.append((AGY, LISTING_COMMANDS[AGY].split()[1:], agy_models, sorted(families_by_binary[AGY])))
    with tempfile.TemporaryDirectory() as empty_directory:
        for family in sorted(families_by_binary.get(CLAUDE, ())):
            requests.append((CLAUDE, None, lambda output, family=family: claude_alias_model(output, family), [family]))
        for agent_binary, arguments, parse, families in requests:
            path = agent_binary_path(agent_binary)
            if arguments is None:
                prefix = headless.claude_code_headless_run_command_line_prefix_build("default", program=path or CLAUDE)
                command = prefix + [CLAUDE_ALIAS_PROBE_PROMPT, "--model", families[0], "--output-format", "json",
                                    "--tools", "", "--no-session-persistence"]
                shown = shlex.join([CLAUDE, "-p", CLAUDE_ALIAS_PROBE_PROMPT, "--model", families[0],
                                    "--output-format", "json"])
            else:
                command = [path or agent_binary, *arguments]
                shown = " ".join([agent_binary, *arguments])
            try:
                if path is None:
                    raise AgentBinaryCannotListModels(
                        f"no {agent_binary} was found on PATH or in "
                        f"{' or '.join(map(str, AGENT_BINARY_DIRECTORIES_OUTSIDE_CRON_PATH))}")
                # An empty directory, so the Claude probe is sent no project's CLAUDE.md.
                listed = parse(listing_output(command, run_command, cwd=empty_directory))
            except AgentBinaryCannotListModels as error:
                failures.append((agent_binary, shown, families, str(error)))
                continue
            newest.update({(agent_binary, family): found for family, found in listed.items()})
    return newest, failures


def report(pins, newest, failures):
    """(stale lines, unchecked lines)."""
    unchecked = [AGENT_BINARY_FAILED_LINE.format(command=command, families=", ".join(families), reason=reason)
                 for _, command, families, reason in failures]
    failed = {(agent_binary, family) for agent_binary, _, families, _ in failures for family in families}
    stale = []
    for pin in pins:
        key = (pin.agent_binary, pin.family)
        if key in failed:
            continue
        if key not in newest:
            unchecked.append(FAMILY_NOT_LISTED_LINE.format(file=pin.file, line=pin.line, id=pin.model_id,
                                                           command=LISTING_COMMANDS[pin.agent_binary]))
            continue
        version, newer = newest[key]
        if version > pin.version:
            stale.append(STALE_LINE.format(file=pin.file, line=pin.line, id=pin.model_id, newer=newer))
    return stale, unchecked


def _write_alert(title, lines, action):
    text = "\n".join(lines)
    print(text)
    try:
        alert_id = user_alerts.user_alert_write_to_pending(title, text, action)
    except OSError as error:
        print(f"The user-alert \"{title}\" could not be written, so it did not reach pending/: {error!r}",
              file=sys.stderr)
        return False
    print(f"This program wrote user-alert {alert_id} into the user-alerts pending/ folder.")
    return True


def main(argv=None, repository=REPOSITORY, run_command=subprocess.run):
    argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter).parse_args(argv)
    try:
        pins = pins_in_code(repository)
    except (OSError, SyntaxError, UnicodeDecodeError, subprocess.CalledProcessError) as error:
        detail = error.stderr.decode(errors="replace").strip() if isinstance(error, subprocess.CalledProcessError) else ""
        text = f"The search of {repository} for pinned model ids ended before it had read every file: {error!r} {detail}"
        print(text, file=sys.stderr)
        try:
            user_alerts.user_alert_write_to_pending(SEARCH_FAILED_TITLE, text.strip(), SEARCH_FAILED_ACTION)
        except OSError as alert_error:
            print(f"The user-alert saying so could not be written either, so no alert reached pending/: "
                  f"{alert_error!r}", file=sys.stderr)
        return 1
    newest, failures = listings(pins, run_command)
    stale, unchecked = report(pins, newest, failures)
    written = True
    if stale:
        written = _write_alert(STALE_TITLE, stale, STALE_ACTION) and written
    if unchecked:
        written = _write_alert(UNCHECKED_TITLE, unchecked, UNCHECKED_ACTION) and written
    if not stale and not unchecked:
        print(f"Each of the {len(pins)} pinned model ids in {repository} is the newest of its family.")
    return 0 if written and not unchecked else 1


if __name__ == "__main__":
    sys.exit(main())
