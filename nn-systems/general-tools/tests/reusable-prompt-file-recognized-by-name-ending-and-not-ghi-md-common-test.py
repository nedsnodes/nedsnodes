#!/usr/bin/env python3
"""Tests for nn-systems/general-tools/reusable-prompt-file-recognized-by-name-ending-and-not-ghi-md-common.py.

Run: python3 nn-systems/general-tools/tests/reusable-prompt-file-recognized-by-name-ending-and-not-ghi-md-common-test.py
Prints one line per case and exits non-zero if any case fails.
"""

import importlib.util
import pathlib

_start_and_end_lines_spec = importlib.util.spec_from_file_location(
    "nn_test_suite_start_time_line_and_end_results_line_print_common",
    pathlib.Path(__file__).resolve().parents[3] / "nn-systems/general-tools/nn-test-suite-start-time-line-and-end-results-line-print-common.py")
_start_and_end_lines = importlib.util.module_from_spec(_start_and_end_lines_spec)
_start_and_end_lines_spec.loader.exec_module(_start_and_end_lines)
_start_and_end_lines.nn_test_suite_start_time_line_print_now_and_end_results_line_print_at_normal_exit_register()

import importlib.util
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


rule = load("reusable_prompt_file_recognized_by_name_ending_and_not_ghi_md_common",
            REPOSITORY_ROOT / "nn-systems" / "general-tools"
            / "reusable-prompt-file-recognized-by-name-ending-and-not-ghi-md-common.py")
ghi_issue_write = load("ghi_issue_write", REPOSITORY_ROOT / "scripts" / "ghi-issue-write.py")
recognized = rule.has_reusable_prompt_file_name_and_is_not_ghi_md
numbered = rule.is_numbered_ghi_md_path

failures = 0


def check(name, condition, detail=None):
    global failures
    if condition:
        print(f"PASS  {name}")
    else:
        failures += 1
        print(f"FAIL  {name}: {detail!r}")


GHI_MD_ENDING_IN_INSTRUCTIONS = (
    "docs/issues/4080-fix-the-defects-a-full-cold-read-found-in-the-design-to-main-state-machine-"
    "design-and-its-arbitrator-agent-instructions.md")

check("a -instructions.md and a -prompt.md at any depth are reusable-prompts",
      recognized("x/y-instructions.md") and recognized("a-prompt.md")
      and recognized("nn-systems/cold-read/cold-read-fast-clarify-prompt.md"))
check("a GHI-MD whose name ends in -instructions.md or -prompt.md is not a reusable-prompt, "
      "in docs/issues/ or in a system's directory",
      not recognized(GHI_MD_ENDING_IN_INSTRUCTIONS) and not recognized("docs/issues/7-a-prompt.md")
      and not recognized("nn-systems/handoff/7-the-handoff-agent-instructions.md"))
check("docs/issues/AGENTS.md and other files without the endings are not numbered GHI-MD paths, "
      "nor reusable-prompts",
      not numbered("docs/issues/AGENTS.md") and not recognized("docs/issues/AGENTS.md")
      and not recognized("x/y-design.md") and not recognized("x/instructions.md"))
check("a -instructions.md not where a GHI-MD named for its issue may sit is a reusable-prompt",
      recognized("docs/issues/queue/7-x-instructions.md")
      and recognized("docs/issues/archived/7-x-instructions.md")
      and recognized("docs/issues/x-instructions.md")
      and recognized("x/docs/issues/7-x-instructions.md")
      and recognized("nn-systems/handoff/docs/7-x-instructions.md")
      and recognized("nn-systems/7-x-instructions.md"))
check("a name the edit operation accepts but create would not build, such as "
      "docs/issues/4080-v2.1-instructions.md, is a numbered GHI-MD path and not a reusable-prompt",
      all(numbered(path) and not recognized(path)
          for path in ("docs/issues/4080-v2.1-instructions.md", "docs/issues/7-X-instructions.md",
                       "docs/issues/7-x--instructions.md",
                       "nn-systems/handoff/4080-v2.1-instructions.md")))
fresh_rule = load("reusable_prompt_rule_fresh_copy",
                  REPOSITORY_ROOT / "nn-systems" / "general-tools"
                  / "reusable-prompt-file-recognized-by-name-ending-and-not-ghi-md-common.py")
check("a path without a reusable-prompt ending is answered without loading scripts/ghi-issue-write.py",
      fresh_rule.has_reusable_prompt_file_name_and_is_not_ghi_md("docs/issues/7-x.md") is False
      and fresh_rule._ghi_issue_write is None)
check("create's design landing form is a numbered GHI-MD path",
      numbered("docs/issues/46-ghi-guide-agent.system.design.md"))
check("the path create_ghi_landing_path_for_ghi_md builds, and that path moved into a system's "
      "directory, are numbered GHI-MD paths where writable_relative_path lets a GHI-MD sit",
      all(numbered(path) and ghi_issue_write.writable_relative_path(path)
          for number, title, source in (
              (4080, "Fix the arbitrator's agent instructions", "x.md"),
              (9, "A [GHI 5](https://example.com) prompt", "draft.md"),
              (46, "GHI guide agent", "ghi-guide-agent.system.design.md"))
          for landed in (ghi_issue_write.create_ghi_landing_path_for_ghi_md(number, title, source),)
          for path in (landed, "nn-systems/handoff/" + landed.rsplit("/", 1)[-1]))
      and not recognized(ghi_issue_write.create_ghi_landing_path_for_ghi_md(
          4080, "Fix the arbitrator's agent instructions", "x.md")))

if failures:
    print(f"{failures} case(s) failed")
    sys.exit(1)
print("all cases passed")
