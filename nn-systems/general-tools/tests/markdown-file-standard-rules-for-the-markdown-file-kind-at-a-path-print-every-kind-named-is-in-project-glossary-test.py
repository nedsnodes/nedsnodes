#!/usr/bin/env python3
"""Every kind the Markdown file standard or its print program names is one the project glossary lists.

The project glossary, docs/nedsnodes-wiki/nedsnodes-glossary.md, holds the one list of the kinds of
Markdown file and the one list of the kinds of GHI, each a numbered list under its own level-2
heading. The standard names a kind of Markdown file in each level-2 heading other than its
common part, and a kind of GHI in each `- **<kind>**:` item of its GHI-MD section; the program,
nn-systems/general-tools/markdown-file-standard-rules-for-the-markdown-file-kind-at-a-path-print.py,
names a kind of Markdown file in each heading of KIND_SECTION_HEADING_AND_PATH_PATTERNS. A kind
named there that the glossary's list lacks fails here. Only that direction is checked: most kinds
have no section of the standard.

Run: python3 nn-systems/general-tools/tests/markdown-file-standard-rules-for-the-markdown-file-kind-at-a-path-print-every-kind-named-is-in-project-glossary-test.py
Prints one line per case and a verdict line, and exits 1 if any case fails.
"""

import importlib.util
import re
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
GENERAL_TOOLS = REPOSITORY_ROOT / "nn-systems" / "general-tools"
PROJECT_GLOSSARY_RELATIVE_PATH = "docs/nedsnodes-wiki/nedsnodes-glossary.md"
MARKDOWN_FILE_KINDS_HEADING = "Kinds of Markdown file"
GHI_KINDS_HEADING = "Kinds of GHI"
STANDARD_COMMON_PART_HEADING = "Common part"
STANDARD_GHI_MD_SECTION_HEADING = "GHI-MD"


def load(module_name, path):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


program = load("markdown_file_standard_rules_for_the_markdown_file_kind_at_a_path_print",
               GENERAL_TOOLS / "markdown-file-standard-rules-for-the-markdown-file-kind-at-a-path-print.py")
RULE_FAILURE_LINES = load(
    "rule_enforcing_nc_test_suite_failure_message_closing_lines_text_common",
    GENERAL_TOOLS / "rule-enforcing-nc-test-suite-failure-message-closing-lines-text-common.py")
STANDARD_RELATIVE_PATH = program.MARKDOWN_FILE_STANDARD_PATH.relative_to(REPOSITORY_ROOT).as_posix()
PROGRAM_RELATIVE_PATH = (
    "nn-systems/general-tools/markdown-file-standard-rules-for-the-markdown-file-kind-at-a-path-print.py")

NUMBERED_KIND_ITEM = re.compile(r"^\d+\. \*\*(.+?)\*\*")
GHI_KIND_ITEM = re.compile(r"^\s*- \*\*(.+?)\*\*:")

failures = 0


def check(name, condition, detail=""):
    global failures
    if condition:
        print(f"PASS  {name}")
    else:
        failures += 1
        print(f"FAIL  {name}:\n{detail}")


def kinds_listed_under(sections, heading):
    """The kinds numbered in the glossary section under `heading`, in their order."""
    return [match.group(1) for line in sections.get(heading, "").splitlines()
            if (match := NUMBERED_KIND_ITEM.match(line))]


def kinds_named_by_the_standard_or_the_program_missing_from_the_glossary(
        glossary_text, standard_text, program_headings):
    """One failure message per kind named but not listed; empty when every kind is listed."""
    glossary_sections = program.level_two_sections(glossary_text)
    standard_sections = program.level_two_sections(standard_text)
    file_kinds = kinds_listed_under(glossary_sections, MARKDOWN_FILE_KINDS_HEADING)
    ghi_kinds = kinds_listed_under(glossary_sections, GHI_KINDS_HEADING)
    guarded_glossary_line = RULE_FAILURE_LINES.\
        guarded_file_fix_failure_message_line_pointing_to_approval_page_and_guard_refusal(
            PROJECT_GLOSSARY_RELATIVE_PATH)
    closing = RULE_FAILURE_LINES.FAILURE_MAY_COME_FROM_MAIN_NOT_YOUR_CHANGE_REPORT_IT_CLOSING_LINE
    messages = []
    for heading, kinds in [(MARKDOWN_FILE_KINDS_HEADING, file_kinds), (GHI_KINDS_HEADING, ghi_kinds)]:
        if not kinds:
            messages.append(
                f"{PROJECT_GLOSSARY_RELATIVE_PATH} has no numbered item under \"## {heading}\", so "
                "no kind named by the standard could be checked.\n"
                f"Restore the heading \"## {heading}\" and its items, each a line beginning "
                "`<number>. **<kind>**`.\n" + guarded_glossary_line + "\n" + closing)
    if messages:
        return messages

    def missing(kind, kinds, heading, where, fix):
        if kind not in kinds:
            messages.append(
                f"{where} names the kind \"{kind}\", which {PROJECT_GLOSSARY_RELATIVE_PATH} does not "
                f"list under \"## {heading}\"; that list is the one list of kinds.\n"
                f"If \"{kind}\" is a misspelling of a listed kind, {fix} to spell it as the list does.\n"
                f"If it is a kind the list lacks, ask the user to add it to the list before the "
                f"standard names it.\n" + closing)

    for heading in standard_sections:
        if heading != STANDARD_COMMON_PART_HEADING:
            missing(heading, file_kinds, MARKDOWN_FILE_KINDS_HEADING,
                    f"The level-2 heading \"## {heading}\" of {STANDARD_RELATIVE_PATH}",
                    "rename the heading, and the program's constant that holds it,")
    for heading in program_headings:
        missing(heading, file_kinds, MARKDOWN_FILE_KINDS_HEADING,
                f"KIND_SECTION_HEADING_AND_PATH_PATTERNS in {PROGRAM_RELATIVE_PATH}",
                "change the constant, and the standard's heading it names,")
    ghi_md_section = standard_sections.get(STANDARD_GHI_MD_SECTION_HEADING, "")
    named_ghi_kinds = [match.group(1) for line in ghi_md_section.splitlines()
                       if (match := GHI_KIND_ITEM.match(line))]
    if not named_ghi_kinds:
        messages.append(
            f"The section \"## {STANDARD_GHI_MD_SECTION_HEADING}\" of {STANDARD_RELATIVE_PATH} has no "
            "item beginning `- **<kind>**:`, so the kinds of GHI it names could not be checked.\n"
            "Give each kind of GHI the section names its own item in that form.\n" + closing)
    for kind in named_ghi_kinds:
        missing(kind, ghi_kinds, GHI_KINDS_HEADING,
                f"The section \"## {STANDARD_GHI_MD_SECTION_HEADING}\" of {STANDARD_RELATIVE_PATH}",
                "change its item")
    return messages


real_messages = kinds_named_by_the_standard_or_the_program_missing_from_the_glossary(
    (REPOSITORY_ROOT / PROJECT_GLOSSARY_RELATIVE_PATH).read_text(encoding="utf-8"),
    program.MARKDOWN_FILE_STANDARD_PATH.read_text(encoding="utf-8"),
    [heading for heading, _ in program.KIND_SECTION_HEADING_AND_PATH_PATTERNS])
check("every kind the standard or the program names is in the project glossary's lists",
      not real_messages, "\n\n".join(real_messages))

# --- The check, pinned on fixtures --------------------------------------------------------------

FIXTURE_GLOSSARY = """# A glossary

- **term** — a term.

## Kinds of GHI

1. **research** (`.research.md`) — a GHI that asks a question.
2. **bug** (`.bug.md`) — a GHI about a broken thing.

## Kinds of Markdown file

1. **skill** — a skill.
2. **GHI-MD** — a GHI-MD.
"""

FIXTURE_STANDARD = """# A standard

## Common part

- rules

## skill

```
## not a heading
```

## GHI-MD

2. The one heading its kind of work takes:
   - **research**: `## Question`.
   - **bug**: `## Reproduction`.

A GHI-MD leaves out:

- **Bold** text that is not a kind.
"""

FIXTURE_PROGRAM_HEADINGS = ["skill", "GHI-MD"]


def fixture_messages(glossary=FIXTURE_GLOSSARY, standard=FIXTURE_STANDARD,
                     program_headings=FIXTURE_PROGRAM_HEADINGS):
    return kinds_named_by_the_standard_or_the_program_missing_from_the_glossary(
        glossary, standard, program_headings)


check("the fixture passes", not fixture_messages(), fixture_messages())

messages = fixture_messages(standard=FIXTURE_STANDARD + "\n## change request\n\nbody\n")
check("a heading of the standard the glossary lacks fails, naming the heading",
      len(messages) == 1 and '"## change request"' in messages[0], messages)

messages = fixture_messages(program_headings=FIXTURE_PROGRAM_HEADINGS + ["Seat-briefs"])
check("a heading the program names that the glossary lacks fails, naming the program",
      len(messages) == 1 and "KIND_SECTION_HEADING_AND_PATH_PATTERNS" in messages[0]
      and '"Seat-briefs"' in messages[0], messages)

messages = fixture_messages(standard=FIXTURE_STANDARD.replace("- **bug**:", "- **change request**:"))
check("a kind of GHI the GHI-MD section names that the glossary lacks fails",
      len(messages) == 1 and '"change request"' in messages[0]
      and '"## Kinds of GHI"' in messages[0], messages)

messages = fixture_messages(standard=FIXTURE_STANDARD.replace("## skill", "## glossary"))
check("a Markdown file kind is not taken from the list of GHI kinds, nor the reverse",
      len(messages) == 1 and '"## glossary"' in messages[0], messages)
messages = fixture_messages(standard=FIXTURE_STANDARD.replace("- **bug**:", "- **skill**:"))
check("a GHI kind is not taken from the list of Markdown file kinds",
      len(messages) == 1 and '"skill"' in messages[0], messages)

messages = fixture_messages(glossary=FIXTURE_GLOSSARY.split("## Kinds of GHI")[0])
check("a glossary with no lists of kinds is a failure, not a pass",
      len(messages) == 2 and all("has no numbered item" in message for message in messages), messages)

messages = fixture_messages(standard=FIXTURE_STANDARD.replace("   - **", "   - "))
check("a GHI-MD section with no item naming a kind is a failure, not a pass",
      len(messages) == 1 and "has no item beginning" in messages[0], messages)

check("every failure message ends with the closing line for a failure that may come from main",
      all(message.endswith(RULE_FAILURE_LINES.FAILURE_MAY_COME_FROM_MAIN_NOT_YOUR_CHANGE_REPORT_IT_CLOSING_LINE)
          for message in fixture_messages(standard=FIXTURE_STANDARD + "\n## change request\n")
          + fixture_messages(glossary="# empty\n")),
      "a failure message lacks the closing line")

print(f"VERDICT: {'FAIL' if failures else 'PASS'} ({failures} failed)")
sys.exit(1 if failures else 0)
