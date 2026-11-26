#!/usr/bin/env python3
"""Tests for the match, add and decide subcommands of scripts/findings-record-codex-finding-match-and-row-add-or-decide.py.

Each case runs the program's main() in this process against a real nn-shared-database
service started on a loopback port with a database under a temporary directory, a git
repository made for the test, and a fake `claude` that logs its command line and
prompt and answers as FAKE_CLAUDE_REPLY and FAKE_CLAUDE_EXIT say. HOME is a scratch
directory holding the service token.

Run: python3 scripts/findings-record-codex-finding-match-and-row-add-or-decide-match-add-and-decide-subcommands-test.py
"""

import contextlib
import importlib.util
import io
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

HERE = Path(__file__).resolve().parent
_git_environment_fixture_spec = importlib.util.spec_from_file_location(
    "git_redirecting_environment_removal_test_fixture",
    HERE / "git-redirecting-environment-removal-test-fixture.py")
_git_environment_fixture = importlib.util.module_from_spec(_git_environment_fixture_spec)
_git_environment_fixture_spec.loader.exec_module(_git_environment_fixture)
_git_environment_fixture.remove_git_redirecting_environment_variables_from_this_process()
scratch = Path(tempfile.mkdtemp(prefix="findings-record-match-test-")).resolve()
os.environ["HOME"] = str(scratch / "home")
(scratch / "home" / ".config" / "nedsnodes").mkdir(parents=True)
(scratch / "home" / ".config" / "nedsnodes" / "nn-shared-database-service.token").write_text("test-token\n")


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


program = load(HERE / "findings-record-codex-finding-match-and-row-add-or-decide.py",
               "findings_record_codex_finding_match_and_row_add_or_decide")
service = load(HERE.parent / "nn-systems" / "nn-shared-database" / "nn-shared-database-service.py",
               "nn_shared_database_service")

failures = []


def check(name, condition, detail=""):
    print(("PASS  " if condition else "FAIL  ") + name)
    if not condition:
        failures.append(name)
        print("      " + str(detail).replace("\n", "\n      "))


tokens = scratch / "accepted-tokens"
tokens.write_text("test-token\n")
database = scratch / "nn-shared-database.sqlite3"
server = service.make_nn_shared_database_service_http_server(database, tokens, "127.0.0.1", 0)
server.RequestHandlerClass.log_message = lambda *arguments: None
threading.Thread(target=server.serve_forever, daemon=True).start()
SERVICE_URL = f"http://127.0.0.1:{server.server_address[1]}"
db = sqlite3.connect(str(database), isolation_level=None)

repository = scratch / "repository"
repository.mkdir()
(repository / "scripts").mkdir()
(repository / "scripts" / "thing.py").write_text("import os\n\nfor name in sorted(names):\n    os.unlink(name)\n")
for command in (["init", "-q"], ["add", "."],
                ["-c", "user.name=test", "-c", "user.email=test@example.invalid", "commit", "-q", "-m", "x"]):
    subprocess.run(["git", "-C", str(repository), *command], check=True)
HEAD = subprocess.run(["git", "-C", str(repository), "rev-parse", "HEAD"], capture_output=True, text=True,
                      check=True).stdout.strip()

fake_claude = scratch / "claude"
fake_claude_log = scratch / "claude-calls.jsonl"
fake_claude.write_text(f"""#!{sys.executable}
import json, os, sys
with open({str(fake_claude_log)!r}, "a") as log:
    log.write(json.dumps([sys.argv[1:], sys.stdin.read()]) + "\\n")
sys.stdout.write(os.environ.get("FAKE_CLAUDE_REPLY", ""))
sys.exit(int(os.environ.get("FAKE_CLAUDE_EXIT", "0")))
""")
fake_claude.chmod(0o755)
miss_log = scratch / "possible-misses.jsonl"


def claude_says(answer, exit_code=0, is_error=False, raw=None):
    os.environ["FAKE_CLAUDE_REPLY"] = raw if raw is not None else json.dumps({"result": answer, "is_error": is_error})
    os.environ["FAKE_CLAUDE_EXIT"] = str(exit_code)


def claude_calls():
    return [json.loads(line) for line in fake_claude_log.read_text().splitlines()] if fake_claude_log.exists() else []


def run(arguments, stdin=""):
    out, err = io.StringIO(), io.StringIO()
    sys.stdin = io.StringIO(stdin)
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = program.main(arguments)
        except SystemExit as stop:
            code = stop.code
    sys.stdin = sys.__stdin__
    return code, out.getvalue(), err.getvalue()


def match(findings, number=4034, head=HEAD, service_url=SERVICE_URL, claude=str(fake_claude)):
    code, out, err = run(["--service-url", service_url, "match", "--pull-request", str(number), "--head-commit", head,
                          "--repository", str(repository), "--claude-program", claude], json.dumps(findings))
    return code, (json.loads(out) if code == 0 else None), err


def add(findings, number=4034, head=HEAD, service_url=SERVICE_URL, log=miss_log):
    code, out, err = run(["--service-url", service_url, "add", "--pull-request", str(number), "--head-commit", head,
                          "--repository", str(repository), *(["--possible-miss-log", str(log)] if log else [])],
                         json.dumps(findings))
    return code, (json.loads(out) if code == 0 else None), err


def finding(finding_id, title, body, line=4):
    heading = f"{title} — scripts/thing.py:{line}-{line}"
    text = (f"- [Codex priority P1 (P0 highest)] {heading}\n  {body}\n  - `Main has it:` `yes`\n"
            f"  This pull request makes it happen: no\n  Reports success on failure: no\n"
            f"  Shown by: judged from the code only")
    return {"finding_id": finding_id, "priority": "P1", "heading": heading, "text": text}


def count(table):
    return db.execute(f"SELECT count(*) FROM {table}").fetchone()[0]


capture = "The cleanup sorts every file in the capture directory and unlinks old ones, the newest capture too."
first = finding("aaaa00000001", "Filter terminal captures before deleting", capture)

code, answers, err = match([first])
check("a finding the findings record holds nothing like is NEW with no judgment, and match adds no row",
      code == 0 and answers == {"aaaa00000001": {"answer": "NEW", "record_id": None}}
      and claude_calls() == [] and count("findings_record_row") == 0, (code, answers, err))

graded = {**first, "grade": "fix-next"}
code, added, err = add([graded])
record_id = (added or {}).get("aaaa00000001", {}).get("record_id")
row = db.execute("SELECT path, line, line_text, line_commit, main_has_it, this_pull_request_makes_it_happen, "
                 "shown_by, grade, state, statement FROM findings_record_row").fetchall()
check("add makes a graded finding a row in state new, with its line's text at the head commit and its four "
      "labelled lines without their code marks", code == 0 and isinstance(record_id, int) and row == [(
          "scripts/thing.py", 4, "    os.unlink(name)", HEAD, "yes", "no", "judged from the code only", "fix-next",
          "new", graded["heading"])], (code, added, err, row))
hashtag_answers = program.fact_line_answers(
    "A finding.\n  - `#defect_already_on_main` `yes`\n  #pull_request_triggers_the_defect no\n"
    "  - **#false_report_of_success_on_failure** no\n  #defect_evidence judged from the code only")
check("a finding's hashtag lines fill the same fields as the older labelled lines", hashtag_answers == {
          "main_has_it": "yes", "this_pull_request_makes_it_happen": "no", "reports_success_on_failure": "no",
          "shown_by": "judged from the code only"}, hashtag_answers)
code, again, err = add([graded])
check("running the same add again adds no second row or sighting",
      code == 0 and again == added and count("findings_record_row") == 1
      and count("findings_record_row_sighting") == 1, (code, again, err))
code, answers, err = match([first])
check("matching a finding after its own row was added at this head commit answers NEW with that row, with no "
      "judgment", code == 0 and answers == {"aaaa00000001": {"answer": "NEW", "record_id": record_id}}
      and claude_calls() == [], (code, answers, err))
code, out, err = run(["--service-url", SERVICE_URL, "add", "--pull-request", "1", "--head-commit", HEAD],
                     json.dumps([first]))
check("add refuses a finding with no grade, with exit 2", code == 2 and "grade" in err, err)

reworded = finding("bbbb00000002", "Restrict deletion to terminal capture files",
                   "The job sorts every regular file in the capture directory and can delete the newest capture.")
claude_says(f"SAME {record_id}")
code, answers, err = match([reworded], number=4076)
calls = claude_calls()
check("a reworded repeat goes to one judgment step with no tools and no connectors, given the candidate rows",
      len(calls) == 1 and calls[0][0][:3] == ["-p", "--strict-mcp-config", "--permission-mode"]
      and calls[0][0][calls[0][0].index("--tools") + 1] == "" and f'"record_id": {record_id}' in calls[0][1]
      and reworded["text"] in calls[0][1], calls)
check("on SAME the answer carries the row and records the finding as a sighting of the row",
      code == 0 and answers["bbbb00000002"]["answer"] == "SAME"
      and answers["bbbb00000002"]["record"]["record_id"] == record_id
      and answers["bbbb00000002"]["possible_regression"] is False
      and db.execute("SELECT record_id, pull_request FROM findings_record_row_sighting WHERE finding_id = ?",
                     ("bbbb00000002",)).fetchall() == [(record_id, 4076)], (code, answers, err))
code, again, err = match([reworded], number=4019)
check("a finding already sighted is SAME again with no judgment", code == 0
      and again["bbbb00000002"]["answer"] == "SAME" and len(claude_calls()) == 1, (code, again, err))

code, out, err = run(["--service-url", SERVICE_URL, "decide", str(record_id), "--state", "fixed",
                      "--decision", "PR 4100 merged", "--owning-agent-seat", "md-skills"])
check("decide records the state, decision and owner on the row",
      code == 0 and db.execute("SELECT state, decision, owning_agent_seat FROM findings_record_row").fetchall()
      == [("fixed", "PR 4100 merged", "md-skills")] and f"row {record_id} is now fixed" in out, (code, out, err))
code, again, err = match([reworded], number=4019)
check("a match to a fixed row is a possible regression",
      code == 0 and again["bbbb00000002"]["possible_regression"] is True, (code, again, err))
code, out, err = run(["--service-url", SERVICE_URL, "decide", str(record_id), "--state", "wontfix",
                      "--decision", "x"])
check("decide refuses a state that is not a findings record row state", code == 2, (code, out, err))

other_defect = {**finding("cccc00000003", "Prune mixed-case capture names",
                          "Lowercase capture names are ignored on the Mac, so they never expire."),
                "grade": "does-not-hold", "reason": "The Mac writes one spelling."}
code, added, err = add([other_defect], number=4353)
logged = [json.loads(line) for line in miss_log.read_text().splitlines()] if miss_log.exists() else []
new_id = (added or {}).get("cccc00000003", {}).get("record_id")
check("a finding added on the same path and line text as a row is logged as a possible miss, and a "
      "does-not-hold reason becomes its decision",
      code == 0 and added["cccc00000003"]["possible_miss_of"] == [record_id]
      and logged and logged[-1]["same_path_and_line_text_as"] == [record_id] and logged[-1]["finding_id"] == "cccc00000003"
      and db.execute("SELECT grade, decision FROM findings_record_row WHERE record_id = ?", (new_id,)).fetchall()
      == [("does-not-hold", "The Mac writes one spelling.")], (code, added, err, logged))

before = (count("findings_record_row"), count("findings_record_row_sighting"))
fresh = finding("dddd00000004", "Filter capture names", capture)
for name, reply in (("a record id it was not given", dict(answer="SAME 99999")),
                    ("a word outside its output states", dict(answer="SAME-ish")),
                    ("text around its answer", dict(answer=f"I think SAME {record_id}")),
                    ("an error", dict(answer="SAME 1", is_error=True)),
                    ("a nonzero exit", dict(answer="NEW", exit_code=1)),
                    ("output that is not JSON", dict(answer=None, raw="not json"))):
    claude_says(**reply)
    code, answers, err = match([fresh])
    check(f"a judgment step that answers with {name} fails the match, records nothing, and says why",
          code == 1 and "FAILED: the findings record match, " in err and "stopped at finding dddd00000004" in err
          and "the judgment step" in err
          and (count("findings_record_row"), count("findings_record_row_sighting")) == before, (code, err))
code, answers, err = match([fresh], claude=str(scratch / "no-such-claude"))
check("a judgment step that cannot be run fails the match", code == 1 and "could not be run" in err, (code, err))
timeout, program.MATCH_JUDGMENT_TIMEOUT_SECONDS = program.MATCH_JUDGMENT_TIMEOUT_SECONDS, 0.5
slow = scratch / "slow-claude"
slow.write_text(f"#!{sys.executable}\nimport time\ntime.sleep(5)\n")
slow.chmod(0o755)
code, answers, err = match([fresh], claude=str(slow))
program.MATCH_JUDGMENT_TIMEOUT_SECONDS = timeout
check("a judgment step that gives no answer in time fails the match", code == 1 and "no answer within" in err,
      (code, err))

code, answers, err = match([fresh], head="0" * 40)
check("a head commit git cannot read fails the match and gives the fetch command",
      code == 1 and "git could not read scripts/thing.py" in err
      and f"git -C {repository} fetch origin pull/4034/head" in err, (code, err))
for past_end in (0, 99):
    code, answers, err = match([finding("eeee0000000" + str(past_end % 10), "Filter capture names", capture,
                                        line=past_end)])
    check(f"a finding citing line {past_end}, outside the file, fails the match instead of recording an empty line",
          code == 1 and f"cites line {past_end}, and the file has 4 line(s) there" in err, (code, err))
code, answers, err = match([{**fresh, "heading": "No place cited"}])
check("a heading that cites no path and line fails the match", code == 1 and "cites no `<path>:<line>`" in err,
      (code, err))
code, answers, err = match([fresh], service_url="http://127.0.0.1:9")
check("a service that cannot be reached fails the match with the service call's own message, and says to post "
      "no review of the pull request until the user answers if a second try fails",
      code == 1 and "cannot be reached" in err and "post no review of pull request 4034 until he answers" in err,
      (code, err))
code, added, err = add([{**fresh, "grade": "fix-next"}], service_url="http://127.0.0.1:9")
check("a service that cannot be reached fails the add", code == 1
      and "FAILED: the findings record add, " in err and "stopped at finding dddd00000004" in err and "cannot be reached" in err,
      (code, err))
code, out, err = run(["--service-url", "http://127.0.0.1:9", "decide", str(record_id), "--state", "fixed",
                      "--decision", "x"])
check("decide fails when the service cannot be reached", code == 1 and "cannot be reached" in err, (code, err))

same_line = {**finding("eeee00000005", "Another defect on that line", "Unrelated words entirely."),
             "grade": "fix-next"}
rows_before = count("findings_record_row")
code, added, err = add([same_line], log=scratch)
check("a possible-miss log that cannot be written fails the add before the row is added", code == 1 and count("findings_record_row") == rows_before
      and "possible-miss log" in err and "could not be written" in err, (code, err))
homes = (program.path_constants.NED_BOX_HOME, program.path_constants.MAC_MOUNT_OF_NED_BOX_HOME)
program.path_constants.NED_BOX_HOME = program.path_constants.MAC_MOUNT_OF_NED_BOX_HOME = str(scratch / "none")
code, added, err = add([{**same_line, "finding_id": "ffff00000006"}], log=None)
program.path_constants.NED_BOX_HOME, program.path_constants.MAC_MOUNT_OF_NED_BOX_HOME = homes
check("a possible miss with no log-store reachable fails the add", code == 1 and "log-store" in err, (code, err))

code, out, err = run(["--service-url", SERVICE_URL, "match", "--pull-request", "1", "--head-commit", HEAD],
                     json.dumps([{"finding_id": "x"}]))
check("findings that are not the documented list are refused with exit 2", code == 2 and "FAILED" in err, err)

server.shutdown()
print(f"{len(failures)} failure(s)")
sys.exit(1 if failures else 0)
