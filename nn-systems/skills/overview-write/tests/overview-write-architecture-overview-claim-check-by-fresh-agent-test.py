#!/usr/bin/env python3
"""Check the overview claim check's stages, its refusals and the reports it writes.

Each case runs the program in a disposable git repository. A stand-in `claude`,
first on PATH, logs the prompt it is given and prints a canned report, or, for
a recheck prompt naming an assertion the case lists, that assertion's canned
answer, or, for the prompt of the fresh-agent that judges whether an unsettled
entry covers a claim, the case's canned judge answer; the
repository's own scripts/md-drift-lint.py is a stand-in that exits as the case
asks. No case runs a model or touches the log-store.

Run: python3 nn-systems/skills/overview-write/tests/overview-write-architecture-overview-claim-check-by-fresh-agent-test.py
Prints one line per case and exits non-zero if any case fails.
"""

import contextlib
import importlib.util
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.dont_write_bytecode = True
_removal_spec = importlib.util.spec_from_file_location(
    "git_redirecting_environment_removal_test_fixture",
    Path(__file__).resolve().parents[4] / "scripts" / "git-redirecting-environment-removal-test-fixture.py")
_removal_module = importlib.util.module_from_spec(_removal_spec)
_removal_spec.loader.exec_module(_removal_module)
_removal_module.remove_git_redirecting_environment_variables_from_this_process()
PROGRAM = Path(__file__).resolve().parents[1] / "overview-write-architecture-overview-claim-check-by-fresh-agent.py"
_spec = importlib.util.spec_from_file_location("overview_claim_check", PROGRAM)
claim_check = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(claim_check)

OVERVIEW = "docs/nedsnodes-wiki/nedsnodes-example-architecture-overview.md"
PROPOSALS = "nn-systems/example/docs/example-architecture-overview-proposed-improvements-or-changes-entries.md"
CONTROL_VARIABLE = "OVERVIEW_CLAIM_CHECK_TEST_CONTROL_DIRECTORY"
TIMEOUT_SECONDS = 120
RECHECK_SLEEP_SECONDS = 3
failures = []

STAND_IN_CLAUDE = f"""#!{sys.executable}
import json, os, pathlib, sys
control = pathlib.Path(os.environ[{CONTROL_VARIABLE!r}])
prompt = sys.stdin.read()
with (control / "claude-calls.jsonl").open("a", encoding="utf-8") as log:
    log.write(json.dumps({{"argv": sys.argv[1:], "stdin": prompt, "cwd": os.getcwd(), "started": __import__("time").time(),
                          "overview_there": pathlib.Path({OVERVIEW!r}).read_text(encoding="utf-8")}}) + "\\n")
answer = json.loads((control / "claude.json").read_text(encoding="utf-8"))
for assertion, recheck in answer.get("rechecks", {{}}).items():
    if f"The assertion: {{assertion}}\\n" in prompt:
        answer = recheck
if prompt.startswith({claim_check.UNSETTLED_ENTRY_COVERS_FIX_LATER_CLAIM_JUDGE_PROMPT_TEMPLATE[:60]!r}):
    answer = answer.get("covering_judge", {{"stdout": "no judge answer was given for this case\\n"}})
__import__("time").sleep(answer.get("sleep_seconds", 0))
if "append_while_running" in answer:
    with open(answer["append_while_running"]["path"], "a", encoding="utf-8") as changed:
        changed.write(answer["append_while_running"]["text"])
if "replace_while_running" in answer:
    replaced = answer["replace_while_running"]
    with open(replaced["path"], encoding="utf-8") as before:
        text = before.read()
    with open(replaced["path"], "w", encoding="utf-8") as after:
        after.write(text.replace(replaced["old"], replaced["new"], 1))
sys.stdout.write(answer["stdout"])
sys.stderr.write(answer.get("stderr", ""))
sys.exit(answer.get("exit_code", 0))
"""

STAND_IN_MD_DRIFT_LINT = f"""#!/usr/bin/env python3
import json, os, pathlib, sys
control = pathlib.Path(os.environ[{CONTROL_VARIABLE!r}])
answer = json.loads((control / "lint.json").read_text(encoding="utf-8"))
(control / "lint-calls.txt").open("a").write(" ".join(sys.argv[1:]) + "\\n")
__import__("time").sleep(answer.get("sleep_seconds", 0))
sys.stdout.write(answer["stdout"])
sys.exit(answer["exit_code"])
"""

# GOOD_REPORT's evidence names no file, so its verdict is never kept and every case that gives it runs the fresh-agent.
GOOD_REPORT = "VERDICT 1 supported: the program exists\n  not checked against the code\nCOUNTS supported=1 contradicted=0 unsupported=0\n"
UNSUPPORTED_REPORT = "VERDICT 1 unsupported must-fix: the program exists\nCOUNTS supported=0 contradicted=0 unsupported=1\n"


def check(name, condition, detail=""):
    print(f"{'PASS' if condition else 'FAIL'}  {name}" + ("" if condition else f": {detail}"))
    if not condition:
        failures.append(name)


class Fixture:
    def __init__(self, root):
        self.root = root
        self.repository = root / "repository"
        self.control = root / "control"
        self.reports = root / "reports"
        binaries = root / "bin"
        for directory in (self.repository, self.control, binaries):
            directory.mkdir()
        (binaries / "claude").write_text(STAND_IN_CLAUDE, encoding="utf-8")
        (binaries / "claude").chmod(0o755)
        self.environment = {**os.environ, "PATH": f"{binaries}{os.pathsep}{os.environ['PATH']}",
                            CONTROL_VARIABLE: str(self.control), "PYTHONDONTWRITEBYTECODE": "1"}
        self.git("init", "-q", "-b", "main")
        self.write("nn-systems/example/tool.py", "x = 1\n")
        self.write("scripts/md-drift-lint.py", STAND_IN_MD_DRIFT_LINT)
        self.code_commit = self.commit("code")
        self.git("update-ref", "refs/remotes/origin/main", self.code_commit)

    def git(self, *arguments):
        result = subprocess.run(["git", "-C", str(self.repository), "-c", "user.name=fixture",
                                 "-c", "user.email=fixture@nedschorus.invalid", "-c", "core.hooksPath=/dev/null",
                                 *arguments], env=self.environment, capture_output=True, text=True,
                                timeout=TIMEOUT_SECONDS)
        if result.returncode:
            raise AssertionError(f"fixture git {arguments}: {result.stderr}")
        return result.stdout.strip()

    def write(self, path, text):
        (self.repository / path).parent.mkdir(parents=True, exist_ok=True)
        (self.repository / path).write_text(text, encoding="utf-8")

    def commit(self, message):
        self.git("add", "-A")
        self.git("commit", "-q", "--allow-empty", "-m", message)
        return self.git("rev-parse", "HEAD")

    def commit_overview(self, checked_against=None, body="# Example overview\n\nThe example system.\n"):
        line = "" if checked_against is False else "\n" + claim_check.overview_path_reader.CHECKED_AGAINST_LINE_TEMPLATE.format(
            commit=checked_against or self.code_commit) + "\n"
        self.write(OVERVIEW, body + line)
        return self.commit("overview")

    def commit_overview_claims(self, *claims, checked_against=None):
        """Commit an overview whose claims are exactly these, one paragraph each, so a canned report's VERDICT lines
        can match them in number."""
        return self.commit_overview(checked_against, body="# Example overview\n\n" + "".join(f"{claim}\n\n" for claim in claims))

    def overview_blob(self):
        return self.git("rev-parse", f"HEAD:{OVERVIEW}")

    def answer(self, *, claude_stdout=GOOD_REPORT, claude_exit=0, lint_stdout="", lint_exit=0,
               claude_sleep=0, lint_sleep=0, rechecks=None, covering_judge=None):
        """rechecks maps an assertion to the {"stdout", "exit_code"} the stand-in gives a recheck prompt naming it;
        covering_judge is the {"stdout", "exit_code"} it gives the covering judge's prompt, with an optional
        "append_while_running": {"path", "text"} that it appends to that file, or "replace_while_running":
        {"path", "old", "new"} with which it replaces the first "old" in that file, before it answers."""
        (self.control / "claude.json").write_text(json.dumps(
            {"stdout": claude_stdout, "exit_code": claude_exit, "sleep_seconds": claude_sleep,
             "rechecks": rechecks or {}, **({"covering_judge": covering_judge} if covering_judge else {})}))
        (self.control / "lint.json").write_text(json.dumps(
            {"stdout": lint_stdout, "exit_code": lint_exit, "sleep_seconds": lint_sleep}))
        for log in ("claude-calls.jsonl", "lint-calls.txt"):
            (self.control / log).unlink(missing_ok=True)

    def claude_calls(self):
        log = self.control / "claude-calls.jsonl"
        return [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []

    def run(self, *arguments, report_directory=None):
        return subprocess.run(
            [sys.executable, str(PROGRAM), "--overview", OVERVIEW,
             "--report-directory", str(report_directory or self.reports), *arguments],
            cwd=self.repository, env=self.environment, capture_output=True, text=True, timeout=TIMEOUT_SECONDS)

    def run_in_process_with_timeouts(self, *, fresh_agent_seconds=60, lint_seconds=60, run_git=None):
        """Run main() here, so a test can shorten a timeout or replace run_git, which the program cannot be told from outside."""
        saved = (claim_check.FRESH_AGENT_TIMEOUT_SECONDS, claim_check.MD_DRIFT_LINT_TIMEOUT_SECONDS,
                 dict(os.environ), os.getcwd(), claim_check.run_git)
        claim_check.FRESH_AGENT_TIMEOUT_SECONDS, claim_check.MD_DRIFT_LINT_TIMEOUT_SECONDS = fresh_agent_seconds, lint_seconds
        claim_check.run_git = run_git or claim_check.run_git
        os.environ.clear()
        os.environ.update(self.environment)
        os.chdir(self.repository)
        try:
            with contextlib.redirect_stderr(io.StringIO()) as stderr, contextlib.redirect_stdout(io.StringIO()) as stdout:
                code = claim_check.main(["--overview", OVERVIEW, "--report-directory", str(self.reports)])
            self.last_in_process_stdout = stdout.getvalue()
            return code, stderr.getvalue()
        finally:
            claim_check.FRESH_AGENT_TIMEOUT_SECONDS, claim_check.MD_DRIFT_LINT_TIMEOUT_SECONDS = saved[0], saved[1]
            claim_check.run_git = saved[4]
            os.environ.clear()
            os.environ.update(saved[2])
            os.chdir(saved[3])

    def reports_written(self):
        return sorted(self.reports.rglob("*.md")) if self.reports.exists() else []

    def worktrees(self):
        return self.git("worktree", "list", "--porcelain").count("worktree ")


def recheck(verdict_and_rank, assertion="b"):
    verdict = verdict_and_rank.split()[0]
    counts = " ".join(f"{name}={int(name == verdict)}" for name in claim_check.VERDICTS)
    return f"VERDICT 1 {verdict_and_rank}: {assertion}\nCOUNTS {counts}\n"


def assertions_restated_in(report):
    return [match.group(4).strip() for match in claim_check.VERDICT_LINE.finditer(report)]


def run_unit_cases():
    def result(report, rechecks=None):
        return claim_check.result_from_fresh_agent_report(report, assertions_restated_in(report), rechecks)[1]

    all_supported = claim_check.OVERVIEW_WRITE_ARCHITECTURE_OVERVIEW_CLAIM_CHECK_RESULT_ALL_CLAIMS_SUPPORTED
    no_must_fix = claim_check.OVERVIEW_WRITE_ARCHITECTURE_OVERVIEW_CLAIM_CHECK_RESULT_NO_MUST_FIX_CLAIM_REMAINS
    must_fix_report = "VERDICT 1 supported: a\nVERDICT 2 contradicted must-fix: b\nCOUNTS supported=1 contradicted=1 unsupported=0\n"
    check("every claim supported gives the all-supported result", result(GOOD_REPORT) == all_supported)
    check("a must-fix claim the recheck ranks must-fix again gives the counts of what remains",
          result(must_fix_report, {2: recheck("contradicted must-fix")})
          == "must-fix claims remain: 1 must-fix, 0 fix-later, 0 nit")
    claims, _ = claim_check.result_from_fresh_agent_report(must_fix_report, ["a", "b"], {2: recheck("unsupported fix-later")})
    check("a must-fix claim the recheck ranks fix-later is ranked fix-later, and no must-fix claim remains",
          result(must_fix_report, {2: recheck("unsupported fix-later")}) == no_must_fix
          and claims[1].rank == claim_check.RANK_FIX_LATER, claims)
    check("a must-fix claim the recheck finds supported is ranked fix-later",
          claim_check.result_from_fresh_agent_report(must_fix_report, ["a", "b"], {2: recheck("supported")})[0][1].rank
          == claim_check.RANK_FIX_LATER)
    check("a must-fix claim the recheck ranks nit is ranked fix-later",
          claim_check.result_from_fresh_agent_report(must_fix_report, ["a", "b"], {2: recheck("contradicted nit")})[0][1].rank
          == claim_check.RANK_FIX_LATER)
    check("fix-later and nit claims alone leave no must-fix claim, with no recheck",
          result("VERDICT 1 unsupported fix-later: a\nVERDICT 2 contradicted nit: b\n"
                 "COUNTS supported=0 contradicted=1 unsupported=1\n") == no_must_fix)
    check("an unsupported claim with no rank is malformed",
          result("VERDICT 1 unsupported: a\nCOUNTS supported=0 contradicted=0 unsupported=1\n")
          == "malformed: VERDICT 1 is unsupported with the rank missing, not one of must-fix, fix-later, nit")
    check("a claim with a rank outside the three is malformed",
          result("VERDICT 1 contradicted later: a\nCOUNTS supported=0 contradicted=1 unsupported=0\n").startswith(
              "malformed: VERDICT 1 is contradicted with the rank later"))
    check("a supported claim with a rank is malformed",
          result("VERDICT 1 supported nit: a\nCOUNTS supported=1 contradicted=0 unsupported=0\n")
          == "malformed: VERDICT 1 is supported but has the rank nit")
    check("a malformed recheck makes the result malformed",
          result(must_fix_report, {2: "I could not check it.\n"})
          == "malformed: the recheck of VERDICT 2 is malformed: no VERDICT line")
    check("a recheck with two VERDICT lines makes the result malformed",
          result(must_fix_report, {2: "VERDICT 1 supported: b\nVERDICT 2 supported: c\n"
                                      "COUNTS supported=2 contradicted=0 unsupported=0\n"})
          == "malformed: the recheck of VERDICT 2 is malformed: 2 VERDICT lines, for 1 assertion(s) given")
    check("a report with fewer VERDICT lines than the assertions given is malformed",
          claim_check.claims_from_fresh_agent_report(GOOD_REPORT, ["a", "b"])
          == (None, "malformed: 1 VERDICT lines, for 2 assertion(s) given"))
    check("no assertions to judge and no report give no claims and no malformed result",
          claim_check.result_from_fresh_agent_report("", [], kept_claims=[claim_check.Claim(None, "supported", None, "a", "")])
          == ([], all_supported))
    claims, _ = claim_check.claims_from_fresh_agent_report(GOOD_REPORT, ["The overview's own sentence."])
    check("a claim takes its text from the assertion it was given, not from the fresh-agent's restatement",
          claims[0].assertion == "The overview's own sentence.", claims)
    claims, _ = claim_check.claims_from_fresh_agent_report(
        "VERDICT 1 contradicted fix-later: a\n  x.py:3 `y`\nVERDICT 2 supported: b\n  z.py:1 `w`\n"
        "COUNTS supported=1 contradicted=1 unsupported=0\n", ["a", "b"])
    check("each claim keeps the lines after its VERDICT line as its evidence, without the COUNTS line",
          [claim.evidence for claim in claims] == ["  x.py:3 `y`", "  z.py:1 `w`"], claims)
    check("a COUNTS line that disagrees with the VERDICT lines is malformed",
          result("VERDICT 1 supported: a\nCOUNTS supported=2 contradicted=0 unsupported=0\n").startswith("malformed: the COUNTS line"))
    check("VERDICT lines out of order are malformed",
          result("VERDICT 2 supported: a\nCOUNTS supported=1 contradicted=0 unsupported=0\n").startswith("malformed: the VERDICT lines"))
    check("no VERDICT line is malformed", result("I could not check it.\n") == "malformed: no VERDICT line")
    check("a missing COUNTS line is malformed", result("VERDICT 1 supported: a\n") == "malformed: 0 COUNTS lines, not one")
    check("the how-to page matches the template, so callers must check nn-systems/<system>",
          claim_check.nn_architecture_overview_described_system_name_from_page_path(
              "docs/nedsnodes-wiki/nedsnodes-how-to-write-an-architecture-overview.md") == "how-to-write-an")
    check("a proposed-improvements file beside an overview is not an overview path",
          claim_check.nn_architecture_overview_described_system_name_from_page_path(
              "docs/nedsnodes-wiki/nedsnodes-handoff-architecture-overview-proposed-improvements-or-changes-x.md") is None)
    check("an overview's one proposed-improvements-or-changes-file is in its system's docs/, outside the wiki folder",
          claim_check.nn_architecture_overview_proposed_improvements_or_changes_file_path_from_page_path(OVERVIEW) == PROPOSALS)
    check("the pointer line names the file and its directory in separate backtick spans, so md-drift-lint at an older "
          "commit, where the file is missing, finds no path to check",
          claim_check.overview_pointer_line_to_proposed_improvements_or_changes_file(OVERVIEW)
          == "This document has proposed improvements or changes: read "
             "`example-architecture-overview-proposed-improvements-or-changes-entries.md` in `nn-systems/example/docs/`.")


ENTRIES_WITH_EACH_STATE = (
    "# Proposed improvements or changes: the example overview\n\nAn introduction.\n\n"
    "## E3 — possible problem: an assertion of the overview is contradicted\n\nClaim: the tool sets x, once\n"
    "The claim check's evidence:\n> tool.py:1\nState: open\n\n"
    "## E4 — improvement: an entry an overview writer recorded\n\nState: needs the user — a handler, 2026-11-20T10:00Z: decide x\n\n"
    "## E5 — possible problem: an assertion of the overview is unsupported\n\nClaim: a settled claim\n"
    "State: settled, not worth doing — a handler, 2026-11-20T10:00Z: the overview was fixed.\n\n"
    "## E6 — improvement: an entry with no State line\n\nIt only says something.\n")


def run_covering_judge_unit_cases():
    unsettled_entries = claim_check.unsettled_entries_in_proposed_improvements_or_changes_file(ENTRIES_WITH_EACH_STATE)
    check("unsettled entries are those whose State: line is not settled, needs the user included, each with its whole text up to the next entry",
          sorted(unsettled_entries) == [3, 4] and unsettled_entries[3].startswith("## E3 ") and unsettled_entries[3].endswith("State: open")
          and "## E4" not in unsettled_entries[3], unsettled_entries)
    claims = [claim_check.Claim(1, "contradicted", claim_check.RANK_FIX_LATER, "the  tool sets x,\tonce", ""),
              claim_check.Claim(2, "contradicted", claim_check.RANK_FIX_LATER, "a settled claim", ""),
              claim_check.Claim(3, "unsupported", claim_check.RANK_FIX_LATER, "a new claim", ""),
              claim_check.Claim(4, "unsupported", claim_check.RANK_FIX_LATER, "a new claim", ""),
              claim_check.Claim(5, "contradicted", claim_check.RANK_NIT, "a nit", "")]
    check("a fix-later claim held word for word in an entry of any state is not new; a repeated new claim is new once, "
          "and a nit is never new",
          [claim.number for claim in claim_check.fix_later_claims_not_yet_in_proposed_improvements_or_changes_file(ENTRIES_WITH_EACH_STATE, claims)]
          == [3])

    def judged(answer, claim_numbers=(1, 2), unsettled_entry_numbers=frozenset({3, 4})):
        return claim_check.claim_number_to_covering_unsettled_entry_number_from_judge_answer(answer, list(claim_numbers), set(unsettled_entry_numbers))

    check("a judge answer gives each covered claim its entry, leaves out new claims, and reads past blank lines",
          judged("\nCLAIM 1 covered-by E4\n\nCLAIM 2 new\n\n") == ({1: 4}, None))
    check("a judge answer that skips a claim is malformed",
          judged("CLAIM 1 new\n") == (None, "it gives no answer for CLAIM 2"))
    check("a judge answer that answers a claim twice is malformed",
          judged("CLAIM 1 new\nCLAIM 1 covered-by E3\nCLAIM 2 new\n") == (None, "it answers CLAIM 1 twice"))
    check("a judge answer that corrects a claim in a CLAIM line not in either form is malformed, not read as its first answer",
          judged("CLAIM 1 covered-by E3\nCLAIM 1 new (correction)\nCLAIM 2 new\n")
          == (None, "its line `CLAIM 1 new (correction)` is not `CLAIM <number> covered-by E<number>` "
                    "or `CLAIM <number> new`, the only lines an answer may hold"))
    for case, correction in (("an indented", "  CLAIM 1 new"), ("a bulleted", "- CLAIM 1 new"), ("a backticked", "`CLAIM 1 new`")):
        check(f"a judge answer that corrects a claim in {case} CLAIM line is malformed, not read as its first answer",
              judged(f"CLAIM 1 covered-by E3\n{correction}\nCLAIM 2 new\n")
              == (None, f"its line `{correction.strip()}` is not `CLAIM <number> covered-by E<number>` "
                        "or `CLAIM <number> new`, the only lines an answer may hold"))
    check("a judge answer with a prose line is malformed",
          judged("My reasoning: claim 1 repeats E3.\nCLAIM 1 covered-by E3\nCLAIM 2 new\n")
          == (None, "its line `My reasoning: claim 1 repeats E3.` is not `CLAIM <number> covered-by E<number>` "
                    "or `CLAIM <number> new`, the only lines an answer may hold"))
    check("a judge answer about a claim it was not asked about is malformed",
          judged("CLAIM 1 new\nCLAIM 2 new\nCLAIM 9 new\n") == (None, "it answers CLAIM 9, which it was not asked about"))
    check("a judge answer naming an entry that is not one of the unsettled entries it was given, such as a settled one, is "
          "malformed",
          judged("CLAIM 1 covered-by E5\nCLAIM 2 new\n")
          == (None, "it says E5 covers CLAIM 1, but E5 is not one of the unsettled entries it was given"))

    with tempfile.TemporaryDirectory(prefix="overview-claim-check-test-") as temporary:
        repository = Path(temporary)
        expected = repository / claim_check.nn_architecture_overview_proposed_improvements_or_changes_file_path_from_page_path(OVERVIEW)
        grandparent_was_missing = not expected.parent.parent.exists()
        written = claim_check.write_fix_later_claims_to_proposed_improvements_or_changes_file(
            repository, OVERVIEW, [claims[2]], "a" * 40, "report.md", for_regular_maintenance=True)
        check("a fix-later claim is written to a new proposed-improvements-or-changes-file whose directory and its parent "
              "do not exist yet",
              grandparent_was_missing and written == expected and expected.is_file()
              and "a new claim" in expected.read_text(encoding="utf-8"), written)


def run_claim_split_and_kept_verdict_unit_cases():
    pointer_line = claim_check.overview_pointer_line_to_proposed_improvements_or_changes_file(OVERVIEW)
    text = ("# Example overview\n\n" + pointer_line + "\n\n## Components\n\n"
            "The tool sets x. It reads `a. B` first! Is it fast? yes, in `nn-systems/example/tool.py`.\n\n"
            "- `scripts/one.py`: runs once. Then stops.\n1. A numbered item.\n\n"
            "| Name | Job |\n|---|---|\n| tool | sets x |\n\n"
            "```\ntool ──> x\n\n# not a heading inside a fence\n```\n\nThe tool sets x.\n\n"
            + claim_check.overview_path_reader.CHECKED_AGAINST_LINE_TEMPLATE.format(commit="a" * 40) + "\n")
    claims = [claim for _key, claim in claim_check.overview_claims_split_from_text(text)]
    check("the overview splits into one claim per sentence and per fenced line, each once, leaving out headings, the "
          "pointer line, table delimiter rows, list markers and the **Checked against:** line, and no full stop inside "
          "a backtick span ends a sentence",
          claims == ["The tool sets x.", "It reads `a. B` first!", "Is it fast? yes, in `nn-systems/example/tool.py`.",
                     "`scripts/one.py`: runs once.", "Then stops.", "A numbered item.", "| Name | Job |",
                     "| tool | sets x |", "tool ──> x", "# not a heading inside a fence"], claims)
    keys = dict((claim, key) for key, claim in claim_check.overview_claims_split_from_text(text))
    edited = dict((claim, key) for key, claim in claim_check.overview_claims_split_from_text(
        text.replace("Then stops.", "Then  stops   at once.")))
    check("editing one sentence changes only that claim's key, and whitespace alone changes no key",
          {claim: key for claim, key in edited.items() if claim != "Then stops at once."}
          == {claim: key for claim, key in keys.items() if claim != "Then stops."}
          and claim_check.overview_claim_key_hashed_from_claim_text("a  b\n c") == claim_check.overview_claim_key_hashed_from_claim_text("a b c"), edited)

    blobs = {"nn-systems/example/tool.py": "1" * 40, "scripts/one.py": "2" * 40, "a/same.py": "3" * 40,
             "b/same.py": "4" * 40, OVERVIEW: "5" * 40}
    check("a text names a blob by its path from the top, after ./ or before a line number or a full stop, or by a bare "
          "file name only one path has",
          claim_check.repository_paths_named_in_text(
              "./scripts/one.py:3 `x`; tool.py:1; same.py:2; see nn-systems/example/tool.py. gone.py", blobs)
          == ["nn-systems/example/tool.py", "scripts/one.py"])
    check("a claim rests on the paths its backtick spans and its evidence name, never on the overview itself",
          claim_check.overview_claim_cited_file_blob_hashes_by_path("`scripts/one.py` runs, unlike tool.py", f"{OVERVIEW}:3 and a/same.py:1", blobs, OVERVIEW)
          == {"a/same.py": "3" * 40, "scripts/one.py": "2" * 40})

    record = {"key": "k", "claim": "the tool sets x", "verdict": "supported", "rank": None, "evidence": "",
              "files": {"nn-systems/example/tool.py": "1" * 40}}
    for case, changed_record, answers, kept in (
            ("a supported verdict whose files are unchanged is kept", record, "", True),
            ("a claim the last report lacks is judged again", None, "", False),
            ("a verdict other than supported is judged again", {**record, "verdict": "unsupported", "rank": "nit"}, "", False),
            ("a claim the writer's answers quote is judged again", record, "i dispute: the tool sets x, because", False),
            ("a claim whose file has another blob is judged again", {**record, "files": {"nn-systems/example/tool.py": "9" * 40}}, "", False),
            ("a claim whose file is gone is judged again", {**record, "files": {"gone.py": "1" * 40}}, "", False),
            ("a claim that rests on no file is judged again", {**record, "files": {}}, "", False)):
        check(case, claim_check.overview_claim_last_verdict_can_be_kept_without_fresh_agent_rejudging(changed_record, answers, blobs) is kept)

    with tempfile.TemporaryDirectory(prefix="overview-claim-check-test-") as temporary:
        directory = Path(temporary)
        check("a report directory with no report gives no claim records",
              claim_check.claim_records_of_newest_report_holding_them(directory) == (None, {}))
        heading = claim_check.CLAIM_RECORDS_SECTION_HEADING
        older = directory / f"{'f' * 40}-2026-11-01T00-00-00-000000Z.md"
        older.write_text(f"result: x\n\nbody\n\n{heading}\n\n" + json.dumps({**record, "key": "older"}) + "\n")
        newer = directory / f"{'0' * 40}-2026-11-02T00-00-00-000000Z.md"
        newer.write_text(f"result: x\n\nbody\n\n{heading}\n\n" + json.dumps({**record, "key": "newer"}) + "\n")
        check("the newest report is found by its time, whatever overview blob its name starts with",
              claim_check.claim_records_of_newest_report_holding_them(directory) == (newer, {"newer": {**record, "key": "newer"}}))
        newest_without_records = directory / f"{'1' * 40}-2026-11-03T00-00-00-000000Z.md"
        newest_without_records.write_text("result: malformed: no VERDICT line\n\nI could not check it.\n")
        check("a newer report without claim records, such as a malformed one, is passed over for the newest that has them",
              claim_check.claim_records_of_newest_report_holding_them(directory)[0] == newer)


def last_stdout_line(result):
    lines = result.stdout.strip().splitlines()
    return lines[-1] if lines else ""


def next_action_line(action):
    return claim_check.NEXT_ACTION_LINE_PREFIX + action


MUST_FIX_CLAIMS = ("the tool sets x", "the program exists")
MUST_FIX_REPORT = ("VERDICT 1 supported: the tool sets x\n  not checked against the code\n"
                   "VERDICT 2 contradicted must-fix: the program exists\n  FIRST-EVIDENCE-LINE\n"
                   "COUNTS supported=1 contradicted=1 unsupported=0\n")


def proposed_improvements_or_changes_files(fixture):
    """Every proposed-improvements-or-changes-file in the checkout, resolved, as the program prints them: the test
    sandbox's temporary directory is a symlink."""
    return sorted(path.resolve() for path in fixture.repository.rglob("*-proposed-improvements-or-changes*")
                  if ".git" not in path.parts)


def run_ranked_claim_cases(fixture):
    def newest_report():
        return claim_check.find_newest_architecture_overview_claim_check_report_path_and_result_for_overview_git_blob(
            fixture.reports, OVERVIEW, fixture.overview_blob())

    fixture.commit_overview_claims(*MUST_FIX_CLAIMS)
    fixture.answer(claude_stdout=MUST_FIX_REPORT,
                   rechecks={"the program exists": {"stdout": recheck("contradicted must-fix", "the program exists")}})
    result = fixture.run()
    calls = fixture.claude_calls()
    newest = newest_report()
    check("a must-fix claim the recheck ranks must-fix again exits 5, and the newest report counts what remains",
          result.returncode == 5 and newest[1] == "must-fix claims remain: 1 must-fix, 0 fix-later, 0 nit",
          (result, newest))
    check("a remaining must-fix claim ends with the next action: fix the must-fix claims, or bring round 3 to the user",
          last_stdout_line(result) == next_action_line(claim_check.NEXT_ACTION_WHEN_MUST_FIX_CLAIMS_REMAIN), result.stdout)
    check("both prompts give the three ranks", len(calls) == 2
          and all(claim_check.CLAIM_RANK_DEFINITIONS_FOR_FRESH_AGENT_PROMPT in call["stdin"] for call in calls), calls)
    recheck_prompt = calls[1]["stdin"] if len(calls) == 2 else ""
    check("the recheck prompt names the must-fix assertion alone, without the first verdict, rank or evidence",
          "The assertion: the program exists\n" in recheck_prompt and "FIRST-EVIDENCE-LINE" not in recheck_prompt
          and "contradicted must-fix" not in recheck_prompt and "the tool sets x" not in recheck_prompt
          and fixture.code_commit in recheck_prompt and calls[1]["cwd"] == calls[0]["cwd"], recheck_prompt)
    report_text = newest[0].read_text() if newest else ""
    check("the report holds the ranks after the recheck in its header, and the recheck's answer after the report",
          report_text.split("\n\n", 1)[0].endswith("\nranks after the recheck: 1 must-fix, 0 fix-later, 0 nit")
          and "# Recheck of VERDICT 2, which the report above ranks must-fix" in report_text, report_text)
    check("a run with no fix-later claim writes no proposed-improvements-or-changes-file",
          not proposed_improvements_or_changes_files(fixture))

    fixture.answer(claude_stdout=MUST_FIX_REPORT,
                   rechecks={"the program exists": {"stdout": recheck("contradicted fix-later", "the program exists")}})
    result = fixture.run()
    newest = newest_report()
    written = proposed_improvements_or_changes_files(fixture)
    check("a must-fix claim the recheck does not rank must-fix exits 0 with the no-must-fix result",
          result.returncode == 0 and newest[1] == claim_check.OVERVIEW_WRITE_ARCHITECTURE_OVERVIEW_CLAIM_CHECK_RESULT_NO_MUST_FIX_CLAIM_REMAINS,
          (result, newest))
    entry = written[0].read_text() if len(written) == 1 else ""
    check("the fix-later claim is written, with its evidence, its report and an open state, to the overview's one "
          "file in its system's docs/, outside the wiki folder",
          written == [(fixture.repository / PROPOSALS).resolve()]
          and entry.startswith(f"# Proposed improvements or changes: {Path(OVERVIEW).name}\n")
          and "## E1 — possible problem: an assertion of the overview is contradicted" in entry
          and "\nClaim: the program exists\n" in entry and ">   FIRST-EVIDENCE-LINE" in entry
          and "State: open" in entry and str(newest[0]) in entry and fixture.code_commit in entry, (written, entry))
    pointer_line = claim_check.overview_pointer_line_to_proposed_improvements_or_changes_file(OVERVIEW)
    check("with a fix-later file written and no pointer line, the next action says to commit the file, open the "
          "follow-up, add the pointer line and run again",
          last_stdout_line(result) == next_action_line(
              claim_check.NEXT_ACTION_WHEN_NO_MUST_FIX_CLAIM_REMAINS
              + claim_check.NEXT_ACTION_SUFFIX_WHEN_FIX_LATER_CLAIMS_WRITTEN_TO_PROPOSED_IMPROVEMENTS_OR_CHANGES_FILE.format(path=written[0] if written else None)
              + claim_check.NEXT_ACTION_SUFFIX_WHEN_OVERVIEW_LACKS_PROPOSED_IMPROVEMENTS_OR_CHANGES_POINTER_LINE.format(line=pointer_line)), result.stdout)

    calls_before = len(fixture.claude_calls())
    result = fixture.run()
    check("a fix-later claim the file already holds is not written again, and the file is left as it was, with no "
          "covering judge run",
          result.returncode == 0 and proposed_improvements_or_changes_files(fixture) == written
          and len(fixture.claude_calls()) == calls_before + 2
          and written[0].read_text() == entry
          and last_stdout_line(result) == next_action_line(claim_check.NEXT_ACTION_WHEN_NO_MUST_FIX_CLAIM_REMAINS),
          result.stdout)

    real_run_git = claim_check.run_git

    def run_git_whose_worktree_remove_fails(repository, *arguments, check=True):
        if arguments[:2] == ("worktree", "remove"):
            return subprocess.CompletedProcess(["git", *arguments], 128, "", "fatal: injected removal failure")
        return real_run_git(repository, *arguments, check=check)

    code, stderr = fixture.run_in_process_with_timeouts(run_git=run_git_whose_worktree_remove_fails)
    fixture.git("worktree", "prune")
    check("no must-fix claim with a worktree git cannot remove exits 6, with the next action to push and clean up",
          code == 6 and fixture.last_in_process_stdout.strip().splitlines()[-1] == next_action_line(
              claim_check.NEXT_ACTION_WHEN_NO_MUST_FIX_CLAIM_REMAINS_AND_WORKTREE_STAYS), (code, stderr))

    count = len(fixture.reports_written())
    fixture.answer(claude_stdout=MUST_FIX_REPORT,
                   rechecks={"the program exists": {"stdout": "", "exit_code": 1, "stderr": "usage limit reached"}})
    result = fixture.run()
    check("a recheck fresh-agent that fails exits 4, quotes its stderr and writes no report",
          result.returncode == 4 and "usage limit reached" in result.stderr and len(fixture.reports_written()) == count,
          result.stderr)

    fixture.answer(claude_stdout=MUST_FIX_REPORT,
                   rechecks={"the program exists": {"stdout": "I could not decide.\n"}})
    result = fixture.run()
    newest = newest_report()
    check("a malformed recheck exits 5 with a malformed result, and ends with the next action: run again",
          result.returncode == 5 and newest[1] == "malformed: the recheck of VERDICT 2 is malformed: no VERDICT line"
          and last_stdout_line(result) == next_action_line(claim_check.NEXT_ACTION_WHEN_FRESH_AGENT_REPORT_IS_MALFORMED_FIRST_TIME),
          (result, newest))
    for report in fixture.reports_written():
        if report.read_text().count("result: malformed"):
            report.unlink()

    fixture.commit_overview_claims("alpha claim", "beta claim")
    fixture.answer(claude_stdout="VERDICT 1 contradicted must-fix: alpha claim\nVERDICT 2 unsupported must-fix: beta claim\n"
                                 "COUNTS supported=0 contradicted=1 unsupported=1\n",
                   rechecks={"alpha claim": {"stdout": recheck("contradicted must-fix", "alpha claim"),
                                             "sleep_seconds": RECHECK_SLEEP_SECONDS},
                             "beta claim": {"stdout": recheck("unsupported fix-later", "beta claim"),
                                            "sleep_seconds": RECHECK_SLEEP_SECONDS}},
                   covering_judge={"stdout": "CLAIM 2 new\n"})
    result = fixture.run()
    rechecks = [call for call in fixture.claude_calls()[1:] if "The assertion: " in call["stdin"]]
    starts = sorted(call["started"] for call in rechecks)
    # Run one after the other, the second recheck would start only after the first's sleep ended.
    check("the rechecks run in parallel: the second starts before the first has finished",
          len(starts) == 2 and starts[1] - starts[0] < RECHECK_SLEEP_SECONDS, starts)
    check("each must-fix claim gets its own recheck, which names only that claim",
          result.returncode == 5 and len(rechecks) == 2
          and sorted(("alpha claim" in call["stdin"], "beta claim" in call["stdin"]) for call in rechecks)
          == [(False, True), (True, False)] and newest_report()[1] == "must-fix claims remain: 1 must-fix, 1 fix-later, 0 nit",
          (result, rechecks))
    appended = written[0].read_text() if written else ""
    check("a fix-later claim is appended to the same file as the next entry, even when a must-fix claim remains, and "
          "the next action names that file",
          proposed_improvements_or_changes_files(fixture) == written and appended.startswith(entry)
          and "## E2 — possible problem: an assertion of the overview is unsupported" in appended
          and "Claim: beta claim" in appended and appended.count("Claim: the program exists") == 1
          and "alpha claim" not in appended
          and last_stdout_line(result).startswith(next_action_line(claim_check.NEXT_ACTION_WHEN_MUST_FIX_CLAIMS_REMAIN))
          and str(written[0]) in last_stdout_line(result), (appended, result.stdout))

    for written_file in proposed_improvements_or_changes_files(fixture):
        written_file.unlink()
    with_pointer = fixture.commit_overview(body=f"# Example overview\n\n{pointer_line}\n\ngamma claim\n\ndelta claim\n")
    fixture.answer(claude_stdout="VERDICT 1 unsupported fix-later: gamma claim\nVERDICT 2 contradicted nit: delta claim\n"
                                 "COUNTS supported=0 contradicted=1 unsupported=1\n")
    result = fixture.run()
    written = proposed_improvements_or_changes_files(fixture)
    check("fix-later and nit claims need no recheck; only the fix-later one is written, and with the pointer line "
          "present the next action leaves it out",
          result.returncode == 0 and len(fixture.claude_calls()) == 1 and len(written) == 1
          and "gamma claim" in written[0].read_text() and "delta claim" not in written[0].read_text()
          and last_stdout_line(result) == next_action_line(
              claim_check.NEXT_ACTION_WHEN_NO_MUST_FIX_CLAIM_REMAINS
              + claim_check.NEXT_ACTION_SUFFIX_WHEN_FIX_LATER_CLAIMS_WRITTEN_TO_PROPOSED_IMPROVEMENTS_OR_CHANGES_FILE.format(path=written[0] if written else None)),
          (with_pointer, result.stdout))
    for written_file in written:
        written_file.unlink()

    main_before = fixture.git("rev-parse", "refs/remotes/origin/main")
    fixture.commit_overview(body=f"# Example overview\n\n{pointer_line}\n\nepsilon claim\n")
    entries_without_claims = ("# Proposed improvements or changes: the example overview\n\n"
                              "## E7 — improvement: an entry an overview writer recorded\n\nState: open")
    fixture.write(PROPOSALS, entries_without_claims)
    fixture.git("update-ref", "refs/remotes/origin/main", fixture.commit("the file on main, with no claim-check entry"))
    fixture.answer(claude_stdout="VERDICT 1 unsupported fix-later: epsilon claim\n"
                                 "COUNTS supported=0 contradicted=0 unsupported=1\n",
                   covering_judge={"stdout": "CLAIM 1 new\n"})
    result = fixture.run()
    appended = (fixture.repository / PROPOSALS).read_text()
    check("when the file on origin/main holds no claim from the claim check, a follow-up pull request fixes the new "
          "claims, appended after the highest entry number",
          result.returncode == 0 and appended.startswith(entries_without_claims + "\n\n## E8 — possible problem:")
          and "Claim: epsilon claim" in appended and "Fixed by: a follow-up pull request, in the overview." in appended
          and last_stdout_line(result).startswith(next_action_line(
              claim_check.NEXT_ACTION_WHEN_NO_MUST_FIX_CLAIM_REMAINS
              + claim_check.NEXT_ACTION_SUFFIX_WHEN_FIX_LATER_CLAIMS_WRITTEN_TO_PROPOSED_IMPROVEMENTS_OR_CHANGES_FILE.format(
                  path=(fixture.repository / PROPOSALS).resolve()))), (appended, result.stdout))

    fixture.git("update-ref", "refs/remotes/origin/main", fixture.commit("the file on main, with a claim-check entry"))
    fixture.commit_overview(body=f"# Example overview\n\n{pointer_line}\n\nzeta claim\n")
    fixture.answer(claude_stdout="VERDICT 1 unsupported fix-later: zeta claim\n"
                                 "COUNTS supported=0 contradicted=0 unsupported=1\n",
                   covering_judge={"stdout": "CLAIM 1 new\n"})
    result = fixture.run()
    appended = (fixture.repository / PROPOSALS).read_text()
    check("when the file on origin/main already holds a claim from the claim check, new claims ranked fix later go "
          "to regular maintenance, not to another follow-up pull request",
          result.returncode == 0 and "## E9 — possible problem:" in appended and "Claim: zeta claim" in appended
          and "Fixed by: regular maintenance, in the overview." in appended
          and last_stdout_line(result) == next_action_line(
              claim_check.NEXT_ACTION_WHEN_NO_MUST_FIX_CLAIM_REMAINS
              + claim_check.NEXT_ACTION_SUFFIX_WHEN_FOLLOW_UP_PULL_REQUEST_LEAVES_FIX_LATER_CLAIMS_TO_REGULAR_MAINTENANCE.format(
                  path=(fixture.repository / PROPOSALS).resolve())), (appended, result.stdout))
    check("without a claim from the claim check on origin/main, the entry says a follow-up pull request fixes it",
          "Fixed by: a follow-up pull request, in the overview." in entry, entry)
    (fixture.repository / PROPOSALS).unlink()
    fixture.commit("remove the file")
    fixture.git("update-ref", "refs/remotes/origin/main", main_before)
    fixture.commit_overview()


def run_covering_judge_cases(fixture):
    """Run after run_ranked_claim_cases, which leaves no proposed-improvements-or-changes-file and origin/main at the
    code commit."""
    fixture.commit_overview_claims("the tool sets x once", "the tool is fast", "a settled claim")
    fixture.write(PROPOSALS, ENTRIES_WITH_EACH_STATE)
    report = ("VERDICT 1 contradicted fix-later: the tool sets x once\n  COVERED-CLAIM-EVIDENCE\n"
              "VERDICT 2 unsupported fix-later: the tool is fast\nVERDICT 3 unsupported fix-later: a settled claim\n"
              "COUNTS supported=0 contradicted=1 unsupported=2\n")
    fixture.answer(claude_stdout=report, covering_judge={"stdout": "CLAIM 1 covered-by E3\nCLAIM 2 new\n"})
    result = fixture.run()
    calls = fixture.claude_calls()
    judge_prompt = calls[1]["stdin"] if len(calls) == 2 else ""
    appended = (fixture.repository / PROPOSALS).read_text()
    check("a claim the covering judge says an unsettled entry covers is not appended, and the run says which entry covers it",
          result.returncode == 0 and appended.startswith(ENTRIES_WITH_EACH_STATE.rstrip("\n"))
          and "Claim: the tool sets x once\n" not in appended and "Claim: the tool is fast" in appended
          and "## E7 — possible problem: an assertion of the overview is unsupported" in appended
          and f"the claim of VERDICT 1, ranked fix later, is not appended: unsettled entry E3 of {PROPOSALS} covers it"
          in result.stdout, (result, appended))
    check("the covering judge is asked only about claims new word for word, with their evidence, is shown only the "
          "unsettled entries, and runs with no tools",
          judge_prompt.startswith(claim_check.UNSETTLED_ENTRY_COVERS_FIX_LATER_CLAIM_JUDGE_PROMPT_TEMPLATE[:60])
          and "CLAIM 1: the tool sets x once\n  COVERED-CLAIM-EVIDENCE\n" in judge_prompt
          and "CLAIM 2: the tool is fast\n" in judge_prompt and "CLAIM 3" not in judge_prompt
          and "## E3 " in judge_prompt and "## E4 " in judge_prompt and "## E5 " not in judge_prompt
          and "## E6 " not in judge_prompt
          and calls[1]["argv"][calls[1]["argv"].index("--tools") + 1] == "" and "--allowedTools" not in calls[1]["argv"],
          calls)
    newest = sorted(fixture.reports_written(), key=lambda path: path.stat().st_mtime)[-1]
    check("the report holds the covering judge's answer after the claim check's report, and the claim records last",
          ("covers each claim ranked fix later that it did not hold word for word\n\nCLAIM 1 covered-by E3\nCLAIM 2 new\n"
           f"\n\n{claim_check.CLAIM_RECORDS_SECTION_HEADING}\n\n") in newest.read_text(), newest.read_text())

    fixture.write(PROPOSALS, ENTRIES_WITH_EACH_STATE)
    count = len(fixture.reports_written())
    for case, covering_judge, expected in (
            ("a covering judge that fails", {"stdout": "", "exit_code": 1, "stderr": "usage limit reached"},
             "usage limit reached"),
            ("a covering judge whose answer skips a claim", {"stdout": "CLAIM 1 new\n"},
             "it gives no answer for CLAIM 2"),
            ("a covering judge that names an entry it was not given", {"stdout": "CLAIM 1 covered-by E5\nCLAIM 2 new\n"},
             "E5 is not one of the unsettled entries it was given")):
        fixture.answer(claude_stdout=report, covering_judge=covering_judge)
        result = fixture.run()
        check(f"{case} exits 4 with why, writes no report, leaves the file as it was, and ends with the next action for "
              "exit 4",
              result.returncode == 4 and expected in result.stderr and len(fixture.reports_written()) == count
              and (fixture.repository / PROPOSALS).read_text() == ENTRIES_WITH_EACH_STATE
              and last_stdout_line(result) == next_action_line(claim_check.NEXT_ACTION_BY_EXIT_CODE[4]),
              (result, covering_judge))
    settled_e3 = ENTRIES_WITH_EACH_STATE.replace("> tool.py:1\nState: open\n", "> tool.py:1\nState: settled by a handler meanwhile\n", 1)
    for case, change, changed_text in (
            ("another claim check appends an entry",
             {"append_while_running": {"path": str(fixture.repository / PROPOSALS),
                                       "text": "\n## E7 — possible problem: an assertion of the overview is unsupported\n\n"
                                               "Claim: the tool is fast\nState: open\n"}},
             ENTRIES_WITH_EACH_STATE + "\n## E7 — possible problem: an assertion of the overview is unsupported\n\n"
                                       "Claim: the tool is fast\nState: open\n"),
            ("a handler settles the entry the judge names",
             {"replace_while_running": {"path": str(fixture.repository / PROPOSALS),
                                        "old": "> tool.py:1\nState: open\n",
                                        "new": "> tool.py:1\nState: settled by a handler meanwhile\n"}},
             settled_e3)):
        fixture.write(PROPOSALS, ENTRIES_WITH_EACH_STATE)
        fixture.answer(claude_stdout=report, covering_judge={"stdout": "CLAIM 1 covered-by E3\nCLAIM 2 new\n", **change})
        result = fixture.run()
        check(f"when {case} while the covering judge runs, the run exits 4, writes no report, appends nothing and "
              "says to run it again",
              result.returncode == 4 and "changed while this claim check decided" in result.stderr
              and len(fixture.reports_written()) == count
              and (fixture.repository / PROPOSALS).read_text() == changed_text
              and last_stdout_line(result) == next_action_line(claim_check.NEXT_ACTION_BY_EXIT_CODE[4]), result)
    fixture.write(PROPOSALS, ENTRIES_WITH_EACH_STATE)
    fixture.answer(claude_stdout=report, covering_judge={"stdout": "CLAIM 1 new\nCLAIM 2 new\n", "sleep_seconds": 5})
    code, stderr = fixture.run_in_process_with_timeouts(fresh_agent_seconds=2)
    check("a covering judge that runs past its timeout exits 4 and writes no report",
          code == 4 and "could not run" in stderr and len(fixture.reports_written()) == count
          and (fixture.repository / PROPOSALS).read_text() == ENTRIES_WITH_EACH_STATE, stderr)
    (fixture.repository / PROPOSALS).unlink()
    fixture.commit_overview()


def claim_records_in_report(path):
    return [json.loads(line) for line in path.read_text().rsplit(
        f"\n{claim_check.CLAIM_RECORDS_SECTION_HEADING}\n", 1)[1].splitlines() if line.strip()]


def run_kept_verdict_cases(fixture):
    """Run after run_covering_judge_cases, in a report directory of its own, so no other case's claim records are
    read; ends with the default overview committed again."""
    reports = fixture.root / "kept-verdict-reports"
    destination = claim_check.overview_write_architecture_overview_claim_check_report_directory_for_overview(reports, OVERVIEW)
    destination.mkdir(parents=True)

    def newest():
        return claim_check.find_newest_architecture_overview_claim_check_report_path_and_result_for_overview_git_blob(
            reports, OVERVIEW, fixture.overview_blob())

    def prompt_of_only_call():
        calls = fixture.claude_calls()
        return calls[0]["stdin"] if len(calls) == 1 else f"{len(calls)} calls"

    tool_blob = fixture.git("rev-parse", f"{fixture.code_commit}:nn-systems/example/tool.py")
    fixture.commit_overview_claims("the tool sets x", "the program exists", "the tool is fast")
    (destination / f"{fixture.overview_blob()}-2026-01-01T00-00-00-000000Z.md").write_text(
        "overview: x\nresult: all claims supported\n\nVERDICT 1 supported: a report from before claim records\n")
    fixture.answer(claude_stdout="VERDICT 1 supported: the tool sets x\n  nn-systems/example/tool.py:1 `x = 1`\n"
                                 "VERDICT 2 supported: the program exists\n  not checked against the code\n"
                                 "VERDICT 3 unsupported nit: the tool is fast\n"
                                 "COUNTS supported=2 contradicted=0 unsupported=1\n")
    result = fixture.run(report_directory=reports)
    first = newest()
    records = claim_records_in_report(first[0]) if first else []
    check("with only a report holding no claim records, every claim goes to the fresh-agent, numbered from 1",
          result.returncode == 0 and "\n1. the tool sets x\n2. the program exists\n3. the tool is fast\n" in prompt_of_only_call(),
          (result, prompt_of_only_call()))
    check("the report records every claim with its key, verdict, rank, evidence, the files it rests on with their blobs "
          "at the checked-against commit, and the report it was judged in",
          [(record["claim"], record["verdict"], record["rank"], record["files"]) for record in records]
          == [("the tool sets x", "supported", None, {"nn-systems/example/tool.py": tool_blob}),
              ("the program exists", "supported", None, {}), ("the tool is fast", "unsupported", "nit", {})]
          and all(record["judged_in"] == str(first[0]) for record in records)
          and records[0]["key"] == claim_check.overview_claim_key_hashed_from_claim_text("the tool sets x")
          and records[0]["evidence"] == "  nn-systems/example/tool.py:1 `x = 1`", records)

    fixture.answer(claude_stdout="VERDICT 1 supported: the program exists\n  not checked against the code\n"
                                 "VERDICT 2 unsupported nit: the tool is fast\n"
                                 "COUNTS supported=1 contradicted=0 unsupported=1\n")
    result = fixture.run(report_directory=reports)
    second = newest()
    text = second[0].read_text() if second else ""
    records = claim_records_in_report(second[0]) if second else []
    check("a supported claim whose file is unchanged keeps its verdict; a claim resting on no file and one not "
          "supported go to the fresh-agent again, renumbered from 1",
          result.returncode == 0 and "\n1. the program exists\n2. the tool is fast\n" in prompt_of_only_call()
          and "the tool sets x" not in prompt_of_only_call().split("The assertions to check:")[1], prompt_of_only_call())
    check("the report counts the kept claim in its result and ranks, says how many claims it kept, and records the "
          "report each kept verdict came from",
          second[1] == claim_check.OVERVIEW_WRITE_ARCHITECTURE_OVERVIEW_CLAIM_CHECK_RESULT_NO_MUST_FIX_CLAIM_REMAINS
          and "\nclaims kept from an earlier report: 1 of 3\n" in text
          and "\nranks after the recheck: 0 must-fix, 0 fix-later, 1 nit\n" in text
          and records[0]["judged_in"] == str(first[0]) and records[1]["judged_in"] == str(second[0]), (text, records))

    fixture.commit_overview_claims("the tool sets x")
    fixture.answer(claude_stdout="", claude_exit=1)
    result = fixture.run(report_directory=reports)
    check("when every claim keeps its verdict, read from a report on another overview text, no fresh-agent runs and the "
          "merge check's reader finds the result for the new text",
          result.returncode == 0 and not fixture.claude_calls() and newest()[1]
          == claim_check.OVERVIEW_WRITE_ARCHITECTURE_OVERVIEW_CLAIM_CHECK_RESULT_ALL_CLAIMS_SUPPORTED
          and last_stdout_line(result) == next_action_line(claim_check.NEXT_ACTION_BY_EXIT_CODE[0]), result)

    answers = fixture.root / "kept-verdict-writer-answers.md"
    answers.write_text("I dispute the verdict on: the tool  sets x. nn-systems/example/tool.py:1 `x = 1`\n")
    fixture.answer(claude_stdout="VERDICT 1 supported: the tool sets x\n  nn-systems/example/tool.py:1 `x = 1`\n"
                                 "COUNTS supported=1 contradicted=0 unsupported=0\n")
    result = fixture.run("--writer-answers", str(answers), report_directory=reports)
    check("a kept claim the writer's answers quote goes to the fresh-agent again",
          result.returncode == 0 and "\n1. the tool sets x\n" in prompt_of_only_call(), prompt_of_only_call())

    fixture.write("nn-systems/example/tool.py", "x = 2\n")
    changed_code = fixture.commit("the tool changes")
    fixture.commit_overview_claims("the tool sets x", checked_against=changed_code)
    fixture.answer(claude_stdout="VERDICT 1 supported: the tool sets x\n  nn-systems/example/tool.py:1 `x = 2`\n"
                                 "COUNTS supported=1 contradicted=0 unsupported=0\n")
    result = fixture.run(report_directory=reports)
    check("a supported claim whose file has another blob at the checked-against commit goes to the fresh-agent again",
          result.returncode == 0 and "\n1. the tool sets x\n" in prompt_of_only_call(), prompt_of_only_call())
    fixture.write("nn-systems/example/tool.py", "x = 1\n")
    fixture.commit("the tool as the code commit holds it")
    fixture.commit_overview()


def run_program_cases(fixture):
    head = fixture.commit_overview()
    blob = fixture.git("rev-parse", f"{head}:{OVERVIEW}")
    worktrees_before = fixture.worktrees()

    fixture.answer()
    result = fixture.run()
    reports = fixture.reports_written()
    calls = fixture.claude_calls()
    check("every claim supported exits 0 and writes one report named by the overview's blob",
          result.returncode == 0 and len(reports) == 1 and reports[0].name.startswith(blob + "-"), result.stderr)
    header = reports[0].read_text().split("\n\n", 1)[0] if reports else ""
    check("the report's header names the overview, the commit checked against and the result",
          f"checked against: {fixture.code_commit}" in header
          and f"{claim_check.RESULT_LINE_PREFIX}{claim_check.OVERVIEW_WRITE_ARCHITECTURE_OVERVIEW_CLAIM_CHECK_RESULT_ALL_CLAIMS_SUPPORTED}" in header, header)
    check("the reader finds that report and its result for the overview's blob",
          claim_check.find_newest_architecture_overview_claim_check_report_path_and_result_for_overview_git_blob(fixture.reports, OVERVIEW, blob)
          == (reports[0], claim_check.OVERVIEW_WRITE_ARCHITECTURE_OVERVIEW_CLAIM_CHECK_RESULT_ALL_CLAIMS_SUPPORTED) if reports else False)
    check("the fresh-agent runs once, at the checked-against commit, with the overview's text in place",
          len(calls) == 1 and "The example system." in calls[0]["overview_there"]
          and fixture.code_commit in calls[0]["stdin"] and claim_check.HOW_TO_PAGE in calls[0]["stdin"], calls)
    check("the fresh-agent's whole tool set is Read, Grep and Glob, so it cannot start subagents, and hooks are off",
          len(calls) == 1 and calls[0]["argv"][calls[0]["argv"].index("--tools") + 1] == "Read,Grep,Glob"
          and '"disableAllHooks": true' in calls[0]["argv"][calls[0]["argv"].index("--settings") + 1], calls)
    check("the temporary worktree is removed after a run", fixture.worktrees() == worktrees_before)
    check("every claim supported ends with the next action: push",
          last_stdout_line(result) == next_action_line(claim_check.NEXT_ACTION_BY_EXIT_CODE[0]), result.stdout)

    run_ranked_claim_cases(fixture)
    run_covering_judge_cases(fixture)
    run_kept_verdict_cases(fixture)

    real_run_git = claim_check.run_git

    def run_git_whose_worktree_remove_fails(repository, *arguments, check=True):
        if arguments[:2] == ("worktree", "remove"):
            if check:
                raise claim_check.ClaimCheckRefusal("`git worktree remove` failed with exit 128: fatal: injected removal failure")
            return subprocess.CompletedProcess(["git", *arguments], 128, "", "fatal: injected removal failure")
        return real_run_git(repository, *arguments, check=check)

    count = len(fixture.reports_written())
    fixture.answer()
    code, stderr = fixture.run_in_process_with_timeouts(run_git=run_git_whose_worktree_remove_fails)
    check("a worktree that git cannot remove exits 6, with git's words and the worktree's path, after writing the report",
          code == 6 and "injected removal failure" in stderr and "checkout-at-checked-against-commit" in stderr
          and len(fixture.reports_written()) == count + 1, stderr)
    cleanup = re.search(r"To clean up, once this program has exited: run `git -C (\S+) (worktree remove --force) (\S+)`",
                        stderr)
    worktree_path = Path(cleanup.group(3)) if cleanup else None
    check("after a failed removal the worktree's folder is gone and git still records the worktree",
          worktree_path is not None and not worktree_path.exists() and str(worktree_path) in fixture.git("worktree", "list"),
          stderr)
    if cleanup:
        fixture.git("worktree", "remove", "--force", str(worktree_path))
    check("the cleanup command the program prints after a failed removal clears git's record of the worktree",
          worktree_path is not None and str(worktree_path) not in fixture.git("worktree", "list"), stderr)
    fixture.git("worktree", "prune")
    fixture.answer(claude_stdout="", claude_exit=1)
    code, stderr = fixture.run_in_process_with_timeouts(run_git=run_git_whose_worktree_remove_fails)
    check("a worktree that git cannot remove after a failed fresh-agent keeps exit 4 and still reports the removal",
          code == 4 and "injected removal failure" in stderr and len(fixture.reports_written()) == count + 1, stderr)
    fixture.git("worktree", "prune")
    fixture.answer(claude_stdout=UNSUPPORTED_REPORT)
    code, stderr = fixture.run_in_process_with_timeouts(run_git=run_git_whose_worktree_remove_fails)
    check("a worktree that git cannot remove after an unsupported claim keeps exit 5, writes the report and still "
          "reports the removal",
          code == 5 and "injected removal failure" in stderr and len(fixture.reports_written()) == count + 2, stderr)
    fixture.git("worktree", "prune")

    for raised in (subprocess.TimeoutExpired(["git", "worktree", "remove"], 1), OSError("injected OSError")):
        def run_git_whose_worktree_remove_raises(repository, *arguments, check=True, raised=raised):
            if arguments[:2] == ("worktree", "remove"):
                raise raised
            return real_run_git(repository, *arguments, check=check)

        kind = type(raised).__name__
        fixture.answer(claude_stdout="", claude_exit=1)
        code, stderr = fixture.run_in_process_with_timeouts(run_git=run_git_whose_worktree_remove_raises)
        check(f"a worktree removal that raises {kind} after a failed fresh-agent keeps exit 4 and reports the removal",
              code == 4 and "could not run" in stderr and "checkout-at-checked-against-commit" in stderr, stderr)
        fixture.git("worktree", "prune")
        fixture.answer(claude_stdout=UNSUPPORTED_REPORT)
        code, stderr = fixture.run_in_process_with_timeouts(run_git=run_git_whose_worktree_remove_raises)
        check(f"a worktree removal that raises {kind} after an unsupported claim keeps exit 5", code == 5, stderr)
        fixture.git("worktree", "prune")
        fixture.answer()
        code, stderr = fixture.run_in_process_with_timeouts(run_git=run_git_whose_worktree_remove_raises)
        check(f"a worktree removal that raises {kind} with every claim supported exits 6 and reports the removal",
              code == 6 and "could not run" in stderr, stderr)
        fixture.git("worktree", "prune")

        def run_git_whose_worktree_prune_raises(repository, *arguments, check=True, raised=raised):
            if arguments[:2] == ("worktree", "prune"):
                raise raised
            return real_run_git(repository, *arguments, check=check)

        fixture.answer()
        code, stderr = fixture.run_in_process_with_timeouts(run_git=run_git_whose_worktree_prune_raises)
        check(f"a `git worktree prune` that would raise {kind} after a successful removal leaves an all-supported run "
              "at exit 0", code == 0 and "could not run" not in stderr and fixture.worktrees() == worktrees_before,
              stderr)

    fixture.answer(claude_stdout="I ran out of time.\n")
    result = fixture.run()
    newest = claim_check.find_newest_architecture_overview_claim_check_report_path_and_result_for_overview_git_blob(fixture.reports, OVERVIEW, blob)
    check("a malformed report exits 5 and is kept with a malformed result",
          result.returncode == 5 and newest[1] == "malformed: no VERDICT line", (result, newest))
    check("a first malformed report for this overview text ends with the next action: run again",
          last_stdout_line(result) == next_action_line(claim_check.NEXT_ACTION_WHEN_FRESH_AGENT_REPORT_IS_MALFORMED_FIRST_TIME), result.stdout)
    result = fixture.run()
    check("a second malformed report for the same overview text ends with the next action: tell the user",
          result.returncode == 5 and last_stdout_line(result) == next_action_line(
              claim_check.NEXT_ACTION_WHEN_FRESH_AGENT_REPORT_IS_MALFORMED_AGAIN.format(
                  directory=claim_check.overview_write_architecture_overview_claim_check_report_directory_for_overview(
                      fixture.reports, OVERVIEW), blob=blob)), result.stdout)

    undecodable_report = claim_check.overview_write_architecture_overview_claim_check_report_directory_for_overview(
        fixture.reports, OVERVIEW) / f"{blob}-x.md"
    undecodable_report.write_bytes(b"\xff\xfe not UTF-8\n")
    result = fixture.run()
    undecodable_report.unlink()
    check("a program defect, here an earlier report that is not UTF-8, exits 2 and ends with the next action for exit 2",
          result.returncode == 2 and "program defect" in result.stderr
          and last_stdout_line(result) == next_action_line(claim_check.NEXT_ACTION_BY_EXIT_CODE[2]),
          (result.returncode, result.stdout, result.stderr))

    count = len(fixture.reports_written())
    fixture.answer(claude_stdout="", claude_exit=1)
    (fixture.control / "claude.json").write_text(json.dumps({"stdout": "", "stderr": "Not logged in", "exit_code": 1}))
    result = fixture.run()
    check("a fresh-agent that fails exits 4, quotes its stderr and writes no report",
          result.returncode == 4 and "Not logged in" in result.stderr and len(fixture.reports_written()) == count, result.stderr)
    check("a failed fresh-agent ends with the next action for exit 4",
          last_stdout_line(result) == next_action_line(claim_check.NEXT_ACTION_BY_EXIT_CODE[4]), result.stdout)
    check("the temporary worktree is removed after a failed run", fixture.worktrees() == worktrees_before)
    (fixture.control / "claude.json").write_text(json.dumps({"stdout": GOOD_REPORT, "exit_code": 1}))
    result = fixture.run()
    check("a fresh-agent that exits nonzero after printing a report still writes no report",
          result.returncode == 4 and len(fixture.reports_written()) == count, result.stderr)
    fixture.answer(claude_stdout="  \n")
    result = fixture.run()
    check("a fresh-agent that exits 0 with no output writes no report",
          result.returncode == 4 and len(fixture.reports_written()) == count, result.stderr)
    bare_binaries = fixture.root / "bin-without-claude"
    bare_binaries.mkdir()
    (bare_binaries / "git").symlink_to(shutil.which("git"))
    fixture.answer()
    no_claude = subprocess.run(
        [sys.executable, str(PROGRAM), "--overview", OVERVIEW, "--report-directory", str(fixture.reports)],
        cwd=fixture.repository, env={**fixture.environment, "PATH": str(bare_binaries)},
        capture_output=True, text=True, timeout=TIMEOUT_SECONDS)
    check("no `claude` on PATH exits 4 with what to fix, and writes no report",
          no_claude.returncode == 4 and "could not run" in no_claude.stderr
          and len(fixture.reports_written()) == count, no_claude.stderr)
    fixture.answer(claude_sleep=5)
    code, stderr = fixture.run_in_process_with_timeouts(fresh_agent_seconds=1, lint_seconds=60)
    check("a fresh-agent that runs past its timeout exits 4 and writes no report",
          code == 4 and "could not run" in stderr and len(fixture.reports_written()) == count, stderr)
    fixture.answer(lint_sleep=5)
    code, stderr = fixture.run_in_process_with_timeouts(fresh_agent_seconds=60, lint_seconds=1)
    check("md-drift-lint that runs past its timeout exits 4 and runs no fresh-agent",
          code == 4 and "did not finish" in stderr and not fixture.claude_calls(), stderr)
    check("the temporary worktree is removed after a timeout", fixture.worktrees() == worktrees_before)
    result = fixture.run("--revision", fixture.code_commit)
    check("a revision that does not hold the overview is refused", result.returncode == 1
          and "is not in" in result.stderr and not fixture.claude_calls(), result.stderr)

    fixture.answer(lint_stdout=f"{OVERVIEW}:3: `nn-systems/example/gone.py` does not exist\n", lint_exit=1)
    result = fixture.run()
    check("md-drift-lint findings exit 3 before any fresh-agent runs, with the findings printed",
          result.returncode == 3 and not fixture.claude_calls() and "gone.py` does not exist" in result.stderr
          and len(fixture.reports_written()) == count, result.stderr)
    fixture.answer(lint_stdout="GitHub could not be queried\n", lint_exit=3)
    result = fixture.run()
    check("md-drift-lint that cannot finish exits 4 and runs no fresh-agent",
          result.returncode == 4 and not fixture.claude_calls(), result.stderr)

    answers = fixture.root / "writer-answers.md"
    answers.write_text("Verdict 1 is wrong: nn-systems/example/tool.py:1 `x = 1`\n")
    fixture.answer()
    result = fixture.run("--writer-answers", str(answers))
    calls = fixture.claude_calls()
    check("--writer-answers names the answers file in the fresh-agent's prompt and in the report",
          result.returncode == 0 and len(calls) == 1 and str(answers.resolve()) in calls[0]["stdin"]
          and f"writer answers: {answers.resolve()}" in claim_check.find_newest_architecture_overview_claim_check_report_path_and_result_for_overview_git_blob(
              fixture.reports, OVERVIEW, blob)[0].read_text(), result.stderr)
    fixture.answer(claude_stdout=UNSUPPORTED_REPORT)
    result = fixture.run("--writer-answers", str(answers))
    calls = fixture.claude_calls()
    check("the recheck prompt names the answers file with the wording for one assertion",
          len(calls) == 2 and claim_check.RECHECK_WRITER_ANSWERS_TEMPLATE.format(answers=answers.resolve()) in calls[1]["stdin"]
          and claim_check.FRESH_AGENT_WRITER_ANSWERS_TEMPLATE.format(answers=answers.resolve()) in calls[0]["stdin"],
          calls)

    fixture.answer()
    result = fixture.run("--writer-answers", str(fixture.root / "missing.md"))
    check("a --writer-answers file that does not exist is refused", result.returncode == 1 and not fixture.claude_calls(), result.stderr)
    result = fixture.run(report_directory=fixture.root / "no-such-log-store" / "reports")
    check("a report directory whose parent is missing is refused, naming ned-box",
          result.returncode == 1 and "ned-box" in result.stderr and not fixture.claude_calls(), result.stderr)
    result = subprocess.run([sys.executable, str(PROGRAM), "--overview",
                             "docs/nedsnodes-wiki/nedsnodes-how-to-write-an-architecture-overview.md",
                             "--report-directory", str(fixture.reports)], cwd=fixture.repository,
                            env=fixture.environment, capture_output=True, text=True, timeout=TIMEOUT_SECONDS)
    check("a path with no nn-systems/<system> directory is refused as not an overview",
          result.returncode == 1 and "is not an nn-architecture-overview" in result.stderr, result.stderr)

    fixture.commit_overview(checked_against=False)
    result = fixture.run()
    check("an overview with no **Checked against:** line is refused", result.returncode == 1
          and "no **Checked against:** last line" in result.stderr and not fixture.claude_calls(), result.stderr)
    fixture.commit_overview(checked_against="1" * 40)
    result = fixture.run()
    check("a **Checked against:** commit missing from the repository is refused with the fetch command",
          result.returncode == 1 and "fetch origin" in result.stderr and not fixture.claude_calls(), result.stderr)
    result = fixture.run("--revision", "no-such-branch")
    check("a revision that does not exist is refused with git's words",
          result.returncode == 1 and "git rev-parse" in result.stderr, result.stderr)
    fixture.commit_overview()
    fixture.git("update-ref", "-d", "refs/remotes/origin/main")
    fixture.answer()
    result = fixture.run()
    fixture.git("update-ref", "refs/remotes/origin/main", fixture.code_commit)
    check("a repository without origin/main is refused with the fetch command, before any fresh-agent runs",
          result.returncode == 1 and "origin/main is missing" in result.stderr and "fetch origin" in result.stderr
          and not fixture.claude_calls(), result.stderr)
    result = fixture.run("--no-such-flag")
    check("a malformed argument is refused with exit 1, not the program-defect exit",
          result.returncode == 1 and "--help" in result.stderr, result.stderr)
    check("a refusal's last line tells the agent to do what the refusal says",
          last_stdout_line(result) == next_action_line(claim_check.NEXT_ACTION_BY_EXIT_CODE[1]), result.stdout)


def main():
    run_unit_cases()
    run_covering_judge_unit_cases()
    run_claim_split_and_kept_verdict_unit_cases()
    with tempfile.TemporaryDirectory(prefix="overview-claim-check-test-") as temporary:
        run_program_cases(Fixture(Path(temporary)))
    print(f"{len(failures)} failed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
