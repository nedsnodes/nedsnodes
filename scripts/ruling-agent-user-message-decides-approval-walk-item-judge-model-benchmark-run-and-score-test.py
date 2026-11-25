#!/usr/bin/env python3
"""Cases for ruling-agent-user-message-decides-approval-walk-item-judge-model-benchmark-run-and-score.py, with a stub model in place of a paid one.

Run: scripts/ruling-agent-user-message-decides-approval-walk-item-judge-model-benchmark-run-and-score-test.py
Exit codes: 0 all passed, 1 any failed.
"""

import contextlib
import importlib.util
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location(
    "ruling_agent_user_message_decides_approval_walk_item_judge_model_benchmark_run_and_score", HERE / "ruling-agent-user-message-decides-approval-walk-item-judge-model-benchmark-run-and-score.py")
BENCHMARK = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BENCHMARK)

KNOWN, OTHER_1, OTHER_2 = "entry-3", "entry-2", "entry-1"


def write_case_set(root, cases=("case-a",)):
    (root / "cases").mkdir(parents=True)
    for case_id in cases:
        (root / "cases" / f"{case_id}.json").write_text(json.dumps({
            "case_id": case_id, "walk_item_text": "## Item 6 of 24: How long the successor looks for a speed-up\n",
            "known_rulings": [{"store_entry_id": KNOWN}, {"store_entry_id": None}],
            "grep": {"hits_newest_first": [KNOWN, OTHER_1, OTHER_2]}}))
    with open(root / "candidate-entries.jsonl", "w") as handle:
        for entry_id in (KNOWN, OTHER_1, OTHER_2):
            handle.write(json.dumps({"id": entry_id, "said_at_utc": "2026-11-20T19:01:25Z", "text": f"words of {entry_id}",
                                     "agent_message_answered": f"agent message before {entry_id}"}) + "\n")


def write_instructions_checkout(root):
    (root / "docs" / "nedsnodes-wiki").mkdir(parents=True)
    (root / "nn-systems" / "handoff").mkdir(parents=True)
    (root / "CLAUDE.md").write_text("CLAUDE TEXT\n")
    (root / BENCHMARK.PROJECT_GLOSSARY_RELATIVE_PATH).write_text("PROJECT GLOSSARY lists `nn-systems/handoff/handoff-system-glossary.md` "
                                                   "and `nn-systems/absent/absent-glossary.md`.\n")
    (root / "nn-systems/handoff/handoff-system-glossary.md").write_text("HANDOFF GLOSSARY\n")


class StubModel:
    """Replaces agent_binary_model_run_argv_stdin_working_directory_and_answer_stdout_or_report_file with a Python one-liner that prints `answer` after `sleep` seconds and exits `exit_code`."""

    def __init__(self, answer, sleep=0, exit_code=0):
        self.answer, self.sleep, self.exit_code, self.prompts = answer, sleep, exit_code, []

    def __call__(self, runtime, model, effort, prompt_file, report_file):
        self.prompts.append(prompt_file.read_text())
        code = (f"import sys, time; sys.stdin.read(); time.sleep({self.sleep}); "
                f"sys.stdout.write({self.answer!r}); sys.stderr.write('stub stderr'); sys.exit({self.exit_code})")
        return [sys.executable, "-c", code], "prompt", None, "stdout"


class BenchmarkTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        write_case_set(self.root / "case-set")
        write_instructions_checkout(self.root / "checkout")
        self.rows = self.root / "rows.jsonl"
        self.original_invocation = BENCHMARK.agent_binary_model_run_argv_stdin_working_directory_and_answer_stdout_or_report_file
        self.original_limit = BENCHMARK.BENCHMARK_MODEL_RUN_SECONDS_LIMIT_THAT_DROPS_THE_MODEL_AND_EFFORT

    def tearDown(self):
        BENCHMARK.agent_binary_model_run_argv_stdin_working_directory_and_answer_stdout_or_report_file = self.original_invocation
        BENCHMARK.BENCHMARK_MODEL_RUN_SECONDS_LIMIT_THAT_DROPS_THE_MODEL_AND_EFFORT = self.original_limit
        self.directory.cleanup()

    def main(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = BENCHMARK.main(list(argv))
        return code, out.getvalue(), err.getvalue()

    def run_benchmark(self, stub, *extra, repeats="1"):
        BENCHMARK.agent_binary_model_run_argv_stdin_working_directory_and_answer_stdout_or_report_file = stub
        return self.main("run", "--case-set", str(self.root / "case-set"), "--runtime", "claude", "--model", "claude-sonnet-5-5",
                         "--effort", "low", "--hits-from", "grep:hits_newest_first", "--first-n", "3", "--rows", str(self.rows),
                         "--repeats", repeats, "--instructions-checkout", str(self.root / "checkout"), *extra)

    def rows_written(self):
        return [json.loads(line) for line in self.rows.read_text().splitlines()]

    def test_prompt_holds_instructions_item_and_numbered_messages_with_the_agent_messages_answered(self):
        stub = StubModel("m1: DECIDES\nm2: NO\nm3: NO\n")
        self.assertEqual(self.run_benchmark(stub)[0], BENCHMARK.EXIT_OK)
        prompt = stub.prompts[0]
        for text in ("CLAUDE TEXT", "PROJECT GLOSSARY", "HANDOFF GLOSSARY", "How long the successor looks for a speed-up",
                     "## m1, said", "words of entry-3", "agent message before entry-3", "## m3, said", "exactly 3 lines"):
            self.assertIn(text, prompt)
        self.assertNotIn("absent-glossary.md =====", prompt)

    def test_answered_row_counts_the_known_ruling_found_and_the_wrong_decides(self):
        self.run_benchmark(StubModel("m1: DECIDES\nm2: DECIDES\n\nm3: NO\n"))
        [row] = self.rows_written()
        self.assertEqual(row["state"], BENCHMARK.BENCHMARK_ROW_STATE_MODEL_ANSWERED)
        self.assertTrue(row["found"])
        self.assertEqual((row["other_messages"], row["other_messages_decided"]), (2, 1))
        self.assertEqual(row["known_rulings_decided"], [KNOWN])

    def test_first_n_cuts_the_list(self):
        stub = StubModel("m1: NO\n")
        BENCHMARK.agent_binary_model_run_argv_stdin_working_directory_and_answer_stdout_or_report_file = stub
        self.main("run", "--case-set", str(self.root / "case-set"), "--runtime", "claude", "--model", "m", "--effort", "low",
                  "--hits-from", "grep:hits_newest_first", "--first-n", "1", "--rows", str(self.rows), "--repeats", "1",
                  "--instructions-checkout", str(self.root / "checkout"))
        [row] = self.rows_written()
        self.assertEqual((row["messages"], row["found"], row["other_messages"]), (1, False, 0))
        self.assertNotIn("## m2,", stub.prompts[0])

    def test_unparsable_answers_are_failures_recorded_in_the_row(self):
        for answer, reason in [("m1: DECIDES\nm2: MAYBE\nm3: NO\n", "'MAYBE', which is not DECIDES or NO"),
                               ("Here are my answers:\nm1: NO\nm2: NO\nm3: NO\n", "a line is not"),
                               ("m1: NO\nm2: NO\n", "1 message(s) got no answer, the first m3"),
                               ("m1: NO\nm1: NO\nm2: NO\nm3: NO\n", "m1 was answered twice"),
                               ("m1: NO\nm2: NO\nm3: NO\nm4: NO\n", "m4 is not one of the ids m1 to m3")]:
            with self.subTest(answer=answer):
                self.rows.unlink(missing_ok=True)
                self.assertEqual(self.run_benchmark(StubModel(answer))[0], BENCHMARK.EXIT_OK)
                [row] = self.rows_written()
                self.assertEqual(row["state"], BENCHMARK.BENCHMARK_ROW_STATE_MODEL_ANSWER_UNPARSABLE)
                self.assertIn(reason, row["failure"])
                self.assertFalse(row["found"])

    def test_a_run_past_the_limit_drops_the_combination_and_runs_nothing_more(self):
        BENCHMARK.BENCHMARK_MODEL_RUN_SECONDS_LIMIT_THAT_DROPS_THE_MODEL_AND_EFFORT = 1
        code, _, err = self.run_benchmark(StubModel("m1: NO\nm2: NO\nm3: NO\n", sleep=5), repeats="3")
        self.assertEqual(code, BENCHMARK.EXIT_MODEL_AND_EFFORT_DROPPED_PAST_TIME_LIMIT)
        self.assertIn("DROPPED: This run stopped because claude claude-sonnet-5-5 at effort low took over 1 seconds", err)
        self.assertIn("Do not run this model and effort again; go on with the next model and effort", err)
        [row] = self.rows_written()
        self.assertEqual((row["state"], row["exit_code"]), (BENCHMARK.BENCHMARK_ROW_STATE_MODEL_AND_EFFORT_DROPPED_PAST_TIME_LIMIT, None))
        self.assertLess(row["seconds"], 4)

    def test_a_rerun_of_a_dropped_combination_runs_no_model(self):
        BENCHMARK.BENCHMARK_MODEL_RUN_SECONDS_LIMIT_THAT_DROPS_THE_MODEL_AND_EFFORT = 1
        self.run_benchmark(StubModel("m1: NO\nm2: NO\nm3: NO\n", sleep=5), repeats="3")
        stub = StubModel("m1: NO\nm2: NO\nm3: NO\n")
        code, _, err = self.run_benchmark(stub, repeats="3")
        self.assertEqual(code, BENCHMARK.EXIT_MODEL_AND_EFFORT_DROPPED_PAST_TIME_LIMIT)
        self.assertIn(f"DROPPED: {self.rows} already shows that claude claude-sonnet-5-5 at effort low took over", err)
        self.assertEqual((stub.prompts, len(self.rows_written())), ([], 1))

    def test_a_model_run_that_exits_nonzero_stops_the_run_and_says_why(self):
        code, _, err = self.run_benchmark(StubModel("", exit_code=3))
        self.assertEqual(code, BENCHMARK.EXIT_COULD_NOT_RUN)
        self.assertIn("FAILED: the claude run of claude-sonnet-5-5 at effort low on case case-a exited 3, so that case "
                      "has no row", err)
        self.assertIn("stub stderr", err)
        self.assertIn("the same command run again skips them and starts at this case", err)
        self.assertIn("run nothing more on claude until he says it is fixed", err)
        self.assertIn("Otherwise: run the same command once more. If it fails again, tell the user", err)
        self.assertIn("If you are a subagent, do none of the above: send this whole message to the agent that dispatched", err)
        self.assertFalse(self.rows.exists() and self.rows.read_text())

    def test_a_rerun_skips_the_cases_and_repeats_the_rows_already_hold(self):
        write_case_set(self.root / "two-cases", cases=("case-a", "case-b"))
        stub = StubModel("m1: NO\nm2: NO\nm3: NO\n")
        self.rows.write_text(json.dumps({"case_id": "case-a", "repeat": 1, "runtime": "claude", "model": "claude-sonnet-5-5",
                                         "effort": "low", "hits_from": "grep:hits_newest_first", "first_n": 3}) + "\n")
        BENCHMARK.agent_binary_model_run_argv_stdin_working_directory_and_answer_stdout_or_report_file = stub
        self.main("run", "--case-set", str(self.root / "two-cases"), "--runtime", "claude", "--model", "claude-sonnet-5-5",
                  "--effort", "low", "--hits-from", "grep:hits_newest_first", "--first-n", "3", "--rows", str(self.rows),
                  "--repeats", "1", "--instructions-checkout", str(self.root / "checkout"))
        self.assertEqual([row["case_id"] for row in self.rows_written()], ["case-a", "case-b"])
        self.assertEqual(len(stub.prompts), 1)

    def test_a_cell_launcher_report_is_read_without_its_provenance_stamp(self):
        def cell_stub(runtime, model, effort, prompt_file, report_file):
            code = (f"open({str(report_file)!r}, 'w').write('<!-- provenance: runtime=agy duration_s=3 -->\\n\\n"
                    f"m1: DECIDES\\nm2: NO\\nm3: NO\\n')")
            return [sys.executable, "-c", code], None, None, report_file
        self.run_benchmark(cell_stub)
        [row] = self.rows_written()
        self.assertEqual((row["state"], row["found"]), (BENCHMARK.BENCHMARK_ROW_STATE_MODEL_ANSWERED, True))

    def test_bad_arguments_and_case_sets_could_not_run(self):
        stub = StubModel("m1: NO\n")
        for argv_change, message in [
                (("--case-set", str(self.root)), "is not a case set: it has no cases/ directory and no "
                                                 "candidate-entries.jsonl file"),
                (("--hits-from", "meaning:hits"), "holds no list 'meaning:hits'; no model was run. The lists it holds "
                                                  "are: grep:hits_newest_first.\nRun again with --hits-from"),
                (("--case", "no-such-case"), "has the case_id no-such-case. The case_ids it holds are: case-a.\n"
                                             "Run again with each --case"),
                (("--first-n", "0"), "--first-n was 0, and must be 1 or more")]:
            with self.subTest(change=argv_change):
                BENCHMARK.agent_binary_model_run_argv_stdin_working_directory_and_answer_stdout_or_report_file = stub
                argv = {"--case-set": str(self.root / "case-set"), "--runtime": "claude", "--model": "m", "--effort": "low",
                        "--hits-from": "grep:hits_newest_first", "--first-n": "3", "--rows": str(self.rows), "--repeats": "1",
                        "--instructions-checkout": str(self.root / "checkout")}
                argv[argv_change[0]] = argv_change[1]
                code, _, err = self.main("run", *[part for pair in argv.items() for part in pair])
                self.assertEqual(code, BENCHMARK.EXIT_COULD_NOT_RUN)
                self.assertIn(message, err)
        self.assertEqual(stub.prompts, [])

    def test_a_list_missing_from_a_later_case_is_found_before_any_model_run(self):
        write_case_set(self.root / "two-cases", cases=("case-a", "case-b"))
        case_b = self.root / "two-cases" / "cases" / "case-b.json"
        case_b.write_text(json.dumps({**json.loads(case_b.read_text()), "grep": {}}))
        stub = StubModel("m1: NO\nm2: NO\nm3: NO\n")
        BENCHMARK.agent_binary_model_run_argv_stdin_working_directory_and_answer_stdout_or_report_file = stub
        code, _, err = self.main("run", "--case-set", str(self.root / "two-cases"), "--runtime", "claude", "--model", "m",
                                 "--effort", "low", "--hits-from", "grep:hits_newest_first", "--first-n", "3",
                                 "--rows", str(self.rows), "--instructions-checkout", str(self.root / "checkout"))
        self.assertEqual(code, BENCHMARK.EXIT_COULD_NOT_RUN)
        self.assertIn("case case-b holds no list 'grep:hits_newest_first'; no model was run. The lists it holds are: none.", err)
        self.assertEqual(stub.prompts, [])

    def score(self, rows):
        self.rows.write_text("".join(json.dumps(row) + "\n" for row in rows))
        code, out, err = self.main("score", "--rows", str(self.rows))
        return code, [json.loads(line) for line in out.splitlines()], err

    def row(self, case_id, repeat, seconds, found, other=10, decided=0, state=BENCHMARK.BENCHMARK_ROW_STATE_MODEL_ANSWERED):
        return {"case_id": case_id, "runtime": "claude", "model": "m", "effort": "low", "hits_from": "grep:hits_newest_first",
                "first_n": 3, "repeat": repeat, "seconds": seconds, "state": state, "found": found,
                "other_messages": other, "other_messages_decided": decided}

    def test_score_is_middle_repeat_percent_found_over_mean_seconds(self):
        rows = [self.row(case, repeat, seconds, found)
                for repeat, seconds, found_b in ((1, 4, True), (2, 10, False), (3, 6, True))
                for case, found in (("a", True), ("b", found_b))]
        code, [result], _ = self.score(rows)
        self.assertEqual(code, BENCHMARK.EXIT_OK)
        self.assertEqual((result["found_middle_of_repeats"], result["mean_seconds_per_case_middle_of_repeats"]), (2, 6))
        self.assertEqual(result["score"], round(100 * 2 / 2 / 6, 4))
        self.assertEqual(result["out"], [])

    def test_score_puts_out_a_dropped_an_over_flagging_and_an_incomplete_combination(self):
        _, [dropped], _ = self.score([self.row("a", 1, 120, False, state=BENCHMARK.BENCHMARK_ROW_STATE_MODEL_AND_EFFORT_DROPPED_PAST_TIME_LIMIT), self.row("b", 1, 5, True)])
        self.assertIn("took over 120 seconds on a case", dropped["out"])
        _, [flagging], _ = self.score([self.row("a", 1, 5, True, other=10, decided=2), self.row("b", 1, 5, True, other=10, decided=1)])
        self.assertEqual(flagging["out"], ["answered DECIDES on 3 of 20 other messages, more than 1 in 10"])
        _, [incomplete], _ = self.score([self.row("a", 1, 5, True), self.row("b", 1, 5, True), self.row("a", 2, 5, True)])
        self.assertEqual(incomplete["out"], ["has 3 rows, fewer than its 2 cases times 2 repeats"])

    def test_score_without_rows_could_not_run(self):
        self.assertIn("hold no rows, so there is nothing to score.\nRun score again with --rows naming", self.score([])[2])
        code, _, err = self.main("score", "--rows", str(self.root / "missing.jsonl"))
        self.assertEqual(code, BENCHMARK.EXIT_COULD_NOT_RUN)
        self.assertIn("missing.jsonl does not exist.\nRun score again with --rows naming", err)
        code, _, err = self.main("score", "--rows", str(self.root))
        self.assertEqual(code, BENCHMARK.EXIT_COULD_NOT_RUN)
        self.assertIn("cannot open the rows file", err)

    def test_score_refuses_a_line_that_is_not_a_json_row(self):
        self.rows.write_text(json.dumps(self.row("a", 1, 5, True)) + "\nnot json\n")
        code, _, err = self.main("score", "--rows", str(self.rows))
        self.assertEqual(code, BENCHMARK.EXIT_COULD_NOT_RUN)
        self.assertIn(f"line 2 of the rows file {self.rows} is not a JSON row", err)
        self.assertIn("'not json'. run writes whole JSON rows", err)
        self.assertIn("Delete that line, then run the same command again", err)

    def test_score_reads_a_rows_file_named_twice_once(self):
        self.rows.write_text(json.dumps(self.row("a", 1, 5, True)) + "\n")
        code, out, _ = self.main("score", "--rows", str(self.rows), str(self.rows))
        self.assertEqual((code, json.loads(out)["cases"]), (BENCHMARK.EXIT_OK, 1))

    def test_score_refuses_two_rows_for_one_case_and_repeat(self):
        code, _, err = self.score([self.row("a", 1, 5, True), self.row("a", 1, 5, True)])
        self.assertEqual(code, BENCHMARK.EXIT_COULD_NOT_RUN)
        self.assertIn(f"two rows are for case a repeat 1 of claude m at effort low: line 1 of {self.rows} and line 2 of "
                      f"{self.rows}. score would count that run twice, so it scored nothing.", err)
        self.assertIn("If the two lines are the same: delete either one", err)
        self.assertIn("tell the user both lines' files and line numbers, and ask which to keep", err)

    def test_claude_invocation_uses_the_common_prefix_no_tools_and_an_empty_directory(self):
        prompt_file = self.root / "p.md"
        prompt_file.write_text("PROMPT")
        argv, stdin_text, directory, place = self.original_invocation("claude", "claude-sonnet-5-5", "low", prompt_file, None)
        self.assertEqual(argv[:3], ["claude", "-p", "--strict-mcp-config"])
        self.assertEqual(argv[argv.index("--tools") + 1], "")
        self.assertEqual((stdin_text, directory, place), ("PROMPT", self.root / "empty-working-directory", "stdout"))

    def test_codex_invocation_runs_the_codex_cell_in_its_fast_mode_tier(self):
        argv, stdin_text, _, place = self.original_invocation("codex", "gpt-6", "low", self.root / "p.md", self.root / "r.md")
        self.assertTrue(argv[1].endswith("cold-read-codex-cell.py"))
        self.assertEqual(argv[argv.index("--tier") + 1], "deep")
        self.assertEqual((stdin_text, place), (None, self.root / "r.md"))


if __name__ == "__main__":
    unittest.main()
