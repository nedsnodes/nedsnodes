#!/usr/bin/env python3
"""Tests for nn-systems/general-tools/markdown-file-standard-rules-for-the-markdown-file-kind-at-a-path-print.py.

The program must pick the right section of the Markdown file standard for each kind of path,
print the common part and its exemption rule for a record or walk-minutes path,
print the common part alone and exit 1 for a path no section covers, and exit 2 when the
standard is missing, lacks a heading, or the program is called wrongly. The real standard
must hold every heading the program's constants name.

Run: python3 nn-systems/general-tools/tests/markdown-file-standard-rules-for-the-markdown-file-kind-at-a-path-print-test.py
Prints one line per case and a verdict line, and exits 1 if any case fails.
"""

import contextlib
import importlib.util
import io
import os
import subprocess
import sys
import tempfile
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
PROGRAM_PATH = Path(os.environ.get(
    "MARKDOWN_FILE_STANDARD_RULES_FOR_THE_MARKDOWN_FILE_KIND_AT_A_PATH_PRINT_PROGRAM_PATH",
    REPOSITORY_ROOT / "nn-systems" / "general-tools"
    / "markdown-file-standard-rules-for-the-markdown-file-kind-at-a-path-print.py"))
_spec = importlib.util.spec_from_file_location(
    "markdown_file_standard_rules_for_the_markdown_file_kind_at_a_path_print", PROGRAM_PATH)
program = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(program)

failures = 0


def check(name, condition, detail=None):
    global failures
    if condition:
        print(f"PASS  {name}")
    else:
        failures += 1
        print(f"FAIL  {name}: {detail!r}")


def run(argv, standard_path=program.MARKDOWN_FILE_STANDARD_PATH):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = program.main(argv, standard_path)
    return code, out.getvalue(), err.getvalue()


# Each kind's paths, including the ones a wider pattern also matches.
expected_kinds = {
    "CLAUDE.md": "project instructions",
    "/home/nedlern/agents/x-wt/AGENTS.md": "project instructions",
    "/home/nedlern/agents/merge-lane-2/CLAUDE.local.md": "seat-brief",
    "CLAUDE.local.md": "seat-brief",
    ".claude/agents/new-name-propose-and-check-fresh-agent.md": "agent definition",
    "docs/agents/sanity-checker-cut-adversarial-prompt.md": "prompt template",
    ".claude/skills/cold-read/prompts/defect-hunt-prompt.md": "prompt template",
    "docs/agents/queue/design-to-main-design-writing-agent-instructions.md": "prompt template",
    ".claude/skills/ghi-write/SKILL.md": "skill",
    "nn-systems/skills/explain/explain-how-to-write-an-identifier-instructions.md": "skill",
    "/home/nedlern/.claude/handoffs/merge-lane-2-next-step-20261117-133829.md": "session-handoff or next step file",
    "/Volumes/nedhome/.claude/handoffs/reboot-test-next-step-20261117-105148.md": "session-handoff or next step file",
    "docs/nedsnodes-wiki/nedsnodes-glossary.md": "glossary",
    "/home/nedlern/agents/x-wt/docs/nedsnodes-wiki/nedsnodes-glossary.md": "glossary",
    "nn-systems/handoff/handoff-system-glossary.md": "glossary",
    ".claude/skills/skills-glossary.md": "glossary",
    "docs/nedsnodes-wiki/nedsnodes-sdlc-terms.md": "glossary",
    "docs/issues/46-ghi-guide-agent.system.design.md": "design",
    "docs/issues/queue/topic-branch-creation-script.tool.design.md": "design",
    "docs/design-to-main/design-to-main-state-machine.system.design.md": "design",
    "docs/nedsnodes-wiki/nedsnodes-style-guide.md": "wiki page",
    "docs/nedsnodes-wiki/queue/nedsnodes-markdown-file-standard-common-part-and-one-section-per-kind.md": "wiki page",
    "docs/nedsnodes-wiki/nedsnodes-handoff-architecture-overview.md": "wiki page",
    "/Volumes/nedhome/Projects/nedsnodes/docs/nedsnodes-wiki/nedsnodes-agent-seat-model.md": "wiki page",
    "docs/issues/1080-type-definitions-for-the-project-s-kinds-of.md": "GHI-MD",
    "docs/issues/queue/the-signal-sandbox-test-fails.md": "GHI-MD",
}
for path, kind in expected_kinds.items():
    got = program.kind_section_heading_for_path(path)
    check(f"{path} is covered by {kind}", got == kind, got)

# Paths of a record or walk-minutes, which get the common part's exemption rule instead of a section,
# including ones a section's pattern would also match, such as a frozen-copy of a prompt template.
expected_record_kinds = {
    "docs/walk/1058-daily-maintenance-in-one-daily-step-starting-with-2026-10-13-2-minutes.md": "walk-minutes",
    "/home/nedlern/nedsnodes-logs/walk/1206-the-daily-full-test-runs-tell-the-user-2026-10-12-minutes.md":
        "walk-minutes",
    "cold-read-records/2026-08-24-composed-defect-hunt/cold-read-triage.md": "record",
    "/home/nedlern/agents/MD-skills/cold-read-records/1-2026-11-12/claude-hunt-deep.md": "record",
    "/Volumes/nedhome/nedsnodes-logs/cold-read-records/1-2026-11-12/item-3-with-sentence-ids.md": "record",
    "cold-read-records/1-2026-11-12/sanity-checker-cut-adversarial-prompt.md": "record",
    "cold-read-records/1-2026-11-12/CLAUDE.md": "record",
    "sanity-check-records/2026-08-25-cold-read-tooling-design/cut-claude.md": "record",
    "/home/nedlern/.claude/handoffs/merge-lane-2-dialog-0002.md": "record",
}
for path, kind in expected_record_kinds.items():
    got = program.record_or_walk_minutes_kind_for_path(path)
    check(f"{path} is a {kind}", got == kind, got)
    check(f"no section covers the {kind} {path}", program.kind_section_heading_for_path(path) is None,
          program.kind_section_heading_for_path(path))
for path in [
    "docs/walk/walk-me-through-skill-refactor-approval-walk-2026-11-02.md",
    "docs/walk/1058-daily-maintenance-2026-10-13-2-draft.md",
    "docs/issues/queue/walk-minutes.md",
    "/home/nedlern/.claude/handoffs/merge-lane-2-next-step-20261117-133829.md",
    "docs/nedsnodes-wiki/nedsnodes-glossary.md",
]:
    got = program.record_or_walk_minutes_kind_for_path(path)
    check(f"{path} is not a record or walk-minutes", got is None, got)

# Paths no section covers.
for path in [
    "README.md",
    "docs/issues/README.md",
    "docs/issues/queue/x.tool.test-design.md",
    "docs/issues/46-ghi-guide-agent.system.test-design.md",
    "docs/issues/46-ghi-guide-agent.system.contract.md",
    "nn-systems/handoff/handoff-design.md",
    "docs/agents/pr-reviewer-instructions.md",
    "nn-systems/skills/explain/tests/explain-reply-cold-read-fast-read-fixtures/capture-note.md",
    "docs/nedsnodes-wiki/nedsnodes-handoff-architecture-overview-proposed-improvements-or-changes-overview-write-claim-check-by-fresh-agent-2026-11-04.md",
    "docs/walk/walk-me-through-skill-refactor-approval-walk-2026-11-02.md",
    "notes-CLAUDE.local.md.bak",
]:
    got = program.kind_section_heading_for_path(path)
    check(f"no section covers {path}", got is None, got)

# Real files in this checkout, so that a renamed directory fails here instead of matching nothing.
tracked = subprocess.run(["git", "-C", str(REPOSITORY_ROOT), "ls-files", "*.md"],
                         capture_output=True, text=True, check=True).stdout.split()
check("the project glossary exists where its pattern looks",
      (REPOSITORY_ROOT / "docs/nedsnodes-wiki/nedsnodes-glossary.md").is_file())
covered_kinds = {program.kind_section_heading_for_path(str(REPOSITORY_ROOT / name)) for name in tracked}
for kind in ["project instructions", "agent definition", "prompt template", "skill", "glossary", "design",
             "wiki page", "GHI-MD"]:
    check(f"a tracked file is covered by {kind}", kind in covered_kinds, sorted(map(str, covered_kinds)))
check("the standard's own path is covered by wiki page",
      program.kind_section_heading_for_path(str(program.MARKDOWN_FILE_STANDARD_PATH)) == "wiki page")

with tempfile.TemporaryDirectory() as scratch:
    issues = Path(scratch) / "docs" / "issues"
    issues.mkdir(parents=True)
    design = issues / "12-a-component-built-like-this.md"
    design.write_text('---\nissue: "[t](u)"\nkind: design\n---\n\n# T\n', encoding="utf-8")
    plain = issues / "13-a-bug.md"
    plain.write_text('---\nissue: "[t](u)"\n---\n\n# T\n\nkind: design\n', encoding="utf-8")
    check("a GHI-MD whose front matter carries kind: design is covered by design",
          program.kind_section_heading_for_path(str(design)) == "design")
    check("kind: design outside the front matter does not make a design",
          program.kind_section_heading_for_path(str(plain)) == "GHI-MD")

# The real standard holds every heading the constants name, and the exemption rule.
real_sections = program.markdown_file_standard_sections()
for heading in [program.COMMON_PART_HEADING] + [h for h, _ in program.KIND_SECTION_HEADING_AND_PATH_PATTERNS]:
    check(f"the standard has the heading ## {heading}", heading in real_sections, sorted(real_sections))
check("the standard's common part has the exemption rule",
      f"\n{program.COMMON_PART_EXEMPTIONS_AND_PRECEDENCE_BULLET_PREFIX}"
      in real_sections[program.COMMON_PART_HEADING])

# A covered path prints the common part, then its section, and nothing of other sections.
code, out, err = run(["docs/issues/46-ghi-guide-agent.system.design.md"])
check("a covered path exits 0", code == 0, (code, err))
check("a covered path prints the common part first", out.startswith("## Common part\n"), out[:80])
check("a covered path prints its section", "\n## design\n" in out, out[-200:])
check("a covered path prints no other section", "## GHI-MD" not in out and "## seat-brief" not in out, out)
check("a covered path prints nothing on stderr", err == "", err)

# A path no section covers: the common part alone, a message on stderr, exit 1.
code, out, err = run(["README.md"])
check("an uncovered path exits 1", code == 1, code)
check("an uncovered path prints the common part alone",
      out.startswith("## Common part\n") and "\n## " not in out, out)
check("an uncovered path says no section covers it", "no section of the standard covers README.md" in err, err)

# A record: the common part, then the kind and the exemption rule again, exit 0.
code, out, err = run(["cold-read-records/1-2026-11-12/cold-read-triage.md"])
exemption_line = program.exemptions_and_precedence_bullet(program.markdown_file_standard_sections())
check("a record exits 0", code == 0, (code, err))
check("a record prints the common part first", out.startswith("## Common part\n"), out[:80])
check("a record prints no section", out.count("\n## ") == 0, out)
check("a record is named as one after the common part",
      "\ncold-read-records/1-2026-11-12/cold-read-triage.md is a record" in out, out[-400:])
check("a record prints the exemption rule last", out.endswith(exemption_line + "\n"), out[-400:])
check("a record prints nothing on stderr", err == "", err)
code, out, err = run(["docs/walk/x-2026-11-20-minutes.md"])
check("walk-minutes exit 0 and are named as walk-minutes",
      code == 0 and "docs/walk/x-2026-11-20-minutes.md is a walk-minutes" in out, (code, out[-400:]))

with tempfile.TemporaryDirectory() as scratch:
    # A standard with no exemption rule in its common part: exit 2, naming the rule.
    no_exemption = Path(scratch) / "no-exemption.md"
    no_exemption.write_text(
        "# Standard\n\n## Common part\n\n- **Length.** common\n\n"
        + "".join(f"## {h}\n\nbody\n\n" for h, _ in program.KIND_SECTION_HEADING_AND_PATH_PATTERNS),
        encoding="utf-8")
    code, out, err = run(["README.md"], no_exemption)
    check("a standard whose common part lacks the exemption rule exits 2", code == 2, code)
    check("a standard whose common part lacks the exemption rule names it on stderr",
          program.COMMON_PART_EXEMPTIONS_AND_PRECEDENCE_BULLET_PREFIX in err, err)

    # A standard that cannot be read: exit 2, nothing on stdout.
    code, out, err = run(["README.md"], Path(scratch) / "missing.md")
    check("a standard that cannot be read exits 2", code == 2, code)
    check("a standard that cannot be read prints nothing on stdout", out == "", out)
    check("a standard that cannot be read is named on stderr", "cannot read" in err and "missing.md" in err, err)

    # A standard missing a heading the constants name: exit 2, naming the heading.
    partial = Path(scratch) / "partial.md"
    partial.write_text(
        "# Standard\n\n## Common part\n\ncommon\n\n```\n## design\n```\n\n"
        + "".join(f"## {h}\n\nbody\n\n" for h, _ in program.KIND_SECTION_HEADING_AND_PATH_PATTERNS
                  if h != "design"),
        encoding="utf-8")
    code, out, err = run(["nn-systems/handoff/handoff.system.design.md"], partial)
    check("a standard missing a heading exits 2", code == 2, code)
    check("a heading inside a code fence does not count", '"## design"' in err, err)

# Called wrongly, and asked for help, as a separate process.
for argv, expected_code in [([], 2), (["a.md", "b.md"], 2), (["--help"], 0)]:
    result = subprocess.run([sys.executable, str(PROGRAM_PATH), *argv], capture_output=True, text=True)
    check(f"argv {argv} exits {expected_code}", result.returncode == expected_code,
          (result.returncode, result.stderr))
    if expected_code == 2:
        check(f"argv {argv} prints its usage on stderr", "Usage:" in result.stderr, result.stderr)
    else:
        check("--help prints the help on stdout", "Exits 0 if" in result.stdout, result.stdout)

print(f"VERDICT: {'FAIL' if failures else 'PASS'} ({failures} failed)")
sys.exit(1 if failures else 0)
