#!/usr/bin/env python3
"""Tests for design-to-main-deferred-and-rejected-decisions-line-form-check.py.

Run: python3 scripts/design-to-main/tests/design-to-main-deferred-and-rejected-decisions-line-form-check-test.py
"""

import contextlib
import importlib.util
import io
import pathlib
import tempfile
import unittest
from unittest import mock

MACHINE_DIRECTORY = pathlib.Path(__file__).resolve().parent.parent
CHECK_PATH = MACHINE_DIRECTORY / "design-to-main-deferred-and-rejected-decisions-line-form-check.py"

_specification = importlib.util.spec_from_file_location(
    "design_to_main_deferred_and_rejected_decisions_line_form_check", CHECK_PATH)
CHECK = importlib.util.module_from_spec(_specification)
_specification.loader.exec_module(CHECK)

WELL_FORMED_DESIGN = """# A design

## 11. Not decided here

### Deferred-decisions

- #not_in_this_run **The report's content**, beyond a placeholder. #reason no run has needed it. #revisit_after a real investigation.
- #not_in_this_run# A sandbox. #reason# none exists yet.
  - A nested note with no tag, which belongs to the line above.
- #rejected A second binary. #reason the user turned it down.
1. #not_in_this_run An ordered line, written
   over two source lines. #reason it still has its reason.

#### A sub-heading inside the section

- #not_in_this_run Still in the section. #reason a deeper heading does not end it.

### Rejected-decisions

- #rejected A retry loop. #reason the failure has not happened.

### Decided elsewhere

- Who restarts the machine: merge-lane-2 decides.

## Another section

- An untagged line outside both sections.
"""


def run_check(*arguments):
    """Return (exit status, stdout, stderr) of the check's main()."""
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        status = CHECK.main(list(arguments))
    return status, out.getvalue(), err.getvalue()


class LineFormCheckTest(unittest.TestCase):

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)

    def design(self, text, name="design.md"):
        path = pathlib.Path(self.directory.name) / name
        path.write_text(text, encoding="utf-8")
        return str(path)

    def malformed(self, text):
        return [(number, heading, problem) for number, heading, _source, problem
                in CHECK.malformed_lines(CHECK.markdown_parser(), text)]

    def test_well_formed_design_exits_0_and_prints_nothing(self):
        self.assertEqual(run_check(self.design(WELL_FORMED_DESIGN)), (0, "", ""))

    def test_deferred_line_without_a_tag_is_reported_with_its_line_number(self):
        text = "## Deferred-decisions\n\n- #not_in_this_run Fine. #reason ok.\n- An unsorted case.\n"
        self.assertEqual(self.malformed(text), [
            (4, "Deferred-decisions", "it does not begin with `#not_in_this_run` or `#rejected`")])

    def test_line_whose_tag_is_not_its_first_word_is_reported(self):
        text = "## Deferred-decisions\n\n- **A case.** #not_in_this_run #reason late tag.\n"
        self.assertEqual(len(self.malformed(text)), 1)

    def test_line_without_a_reason_is_reported(self):
        text = "## Deferred-decisions\n\n- #not_in_this_run A case with no why.\n"
        self.assertEqual(self.malformed(text), [
            (3, "Deferred-decisions", "it gives no `#reason` after its `#not_in_this_run`")])

    def test_reason_before_the_tag_does_not_count(self):
        text = "## Rejected-decisions\n\n- #reason first. #rejected then the case.\n"
        self.assertEqual(len(self.malformed(text)), 1)

    def test_longer_hashtag_is_not_the_tag(self):
        text = ("## Deferred-decisions\n\n- #not_in_this_run_either A case. #reason ok.\n"
                "- #not_in_this_run A case. #reasoned no reason tag.\n")
        self.assertEqual([problem for _number, _heading, problem in self.malformed(text)], [
            "it does not begin with `#not_in_this_run` or `#rejected`",
            "it gives no `#reason` after its `#not_in_this_run`"])

    def test_deferred_tag_under_rejected_decisions_is_reported(self):
        text = "## Rejected-decisions\n\n- #not_in_this_run A case. #reason misplaced.\n"
        self.assertEqual(self.malformed(text), [
            (3, "Rejected-decisions", "it does not begin with `#rejected`")])

    def test_section_ends_at_a_heading_at_the_same_or_a_shallower_level(self):
        text = ("# Top\n\n### Deferred-decisions\n\n- #not_in_this_run A. #reason ok.\n\n"
                "### Decided elsewhere\n\n- Untagged, not in the section.\n\n"
                "### Deferred-decisions\n\n- Untagged, in the section again.\n\n"
                "## Shallower\n\n- Untagged, not in the section.\n")
        self.assertEqual([number for number, _heading, _problem in self.malformed(text)], [13])

    def test_list_in_a_fenced_block_or_a_heading_merely_containing_the_name_is_not_read(self):
        text = ("## Deferred-decisions\n\n```\n- An untagged example.\n```\n\n"
                "## About Deferred-decisions\n\n- Untagged, outside the section.\n")
        self.assertEqual(self.malformed(text), [])

    def test_malformed_design_exits_1_and_prints_each_line_and_what_to_do(self):
        path = self.design("## Deferred-decisions\n\n- An unsorted case.\n")
        status, out, err = run_check(path)
        self.assertEqual((status, err), (1, ""))
        self.assertIn(f"{path}:3: under `Deferred-decisions`, it does not begin with", out)
        self.assertIn("- An unsorted case.", out)
        self.assertIn("If the user has sorted the line, rewrite it in that form", out)
        self.assertIn(CHECK.DESIGN_WRITING_INSTRUCTIONS, out)

    def test_every_file_is_checked_and_only_malformed_ones_reported(self):
        good = self.design(WELL_FORMED_DESIGN, "good.md")
        bad = self.design("## Rejected-decisions\n\n- Untagged.\n", "bad.md")
        status, out, _err = run_check(good, bad)
        self.assertEqual(status, 1)
        self.assertNotIn(good, out)
        self.assertIn(f"{bad}:3:", out)

    def test_unreadable_file_exits_2_and_says_to_tell_the_user(self):
        missing = str(pathlib.Path(self.directory.name) / "missing.md")
        status, out, err = run_check(self.design(WELL_FORMED_DESIGN), missing)
        self.assertEqual((status, out), (2, ""))
        self.assertIn(f"did not run, because {missing} could not be read", err)
        self.assertIn("Tell the user this whole message.", err)

    def test_file_that_is_not_utf_8_exits_2(self):
        path = pathlib.Path(self.directory.name) / "binary.md"
        path.write_bytes(b"\xff\xfe\x00")
        self.assertEqual(run_check(str(path))[0], 2)

    def test_markdown_parser_that_cannot_be_loaded_exits_2(self):
        broken = pathlib.Path(self.directory.name) / "broken-parser.py"
        broken.write_text("raise ImportError('markdown-it-py is missing')\n", encoding="utf-8")
        with mock.patch.object(CHECK, "MARKDOWN_PARSER_MODULE", broken):
            status, out, err = run_check(self.design(WELL_FORMED_DESIGN))
        self.assertEqual((status, out), (2, ""))
        self.assertIn(f"the Markdown parser {broken} could not be loaded: markdown-it-py is missing", err)

    def test_no_file_or_an_option_exits_2_with_the_usage(self):
        for arguments in ((), ("--all",)):
            status, out, err = run_check(*arguments)
            self.assertEqual((status, out), (2, ""))
            self.assertIn("Usage:", err)


if __name__ == "__main__":
    unittest.main(verbosity=2)
