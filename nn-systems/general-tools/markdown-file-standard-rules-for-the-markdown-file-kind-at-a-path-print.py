#!/usr/bin/env python3
"""Print the Markdown file standard's rules for the file at a path: the common part, then the section for the file's kind.

Usage: markdown-file-standard-rules-for-the-markdown-file-kind-at-a-path-print.py <path of a Markdown file>

Exits 0 if a section of the standard covers the path, and prints the common part and that
section, or if the path is a record's or walk-minutes', and prints the common part, the file's
kind and the common part's rule Exemptions and precedence; 1 if neither holds, and prints the
common part alone; 2 if the standard could not be read or lacks a heading or rule this program
needs, or the program was called wrongly.

The kind is picked from the path, so the file need not exist yet; a GHI-MD that already exists
and whose front matter carries `kind: design` is a design, as /ghi-write names one. The path may be
relative or absolute, inside any checkout or worktree, or under the Mac's /Volumes/nedhome
mount of ned-box's home directory.
"""

import os
import re
import sys
from pathlib import Path

PROGRAM_NAME = "markdown-file-standard-rules-for-the-markdown-file-kind-at-a-path-print"
MARKDOWN_FILE_STANDARD_PATH = (
    Path(__file__).resolve().parents[2] / "docs" / "nedsnodes-wiki" / "queue"
    / "nedsnodes-markdown-file-standard-common-part-and-one-section-per-kind.md")
COMMON_PART_HEADING = "Common part"
COMMON_PART_EXEMPTIONS_AND_PRECEDENCE_BULLET_PREFIX = "- **Exemptions and precedence.**"

# Each kind's name is spelled as the project glossary's "Kinds of Markdown file" spells it. The
# standard has no section for these kinds, only the common part's exemption rule. They are asked
# before any section's kind, as the glossary's list orders them, because a record can be a
# frozen-copy of a file another pattern matches, such as a prompt's. A frozen-copy has no
# name of its own in a cold-read-record, so the exemption rule printed names both cases.
RECORD_AND_WALK_MINUTES_MARKDOWN_FILE_KIND_AND_PATH_PATTERNS = [
    ("record", r"(^|/)(cold-read-records|sanity-check-records)/.+\.md$"),
    ("record", r"(^|/)\.claude/handoffs/[^/]+-dialog-\d+\.md$"),
    ("walk-minutes", r"(^|/)(docs|nedsnodes-logs)/walk/[^/]+-minutes\.md$"),
]

# A test-design and a design-contract in docs/issues/ have names the GHI-MD pattern also
# matches, but design-to-main's agent-instructions say what they hold.
UNCOVERED_PATH_PATTERNS = [r"\.test-design\.md$", r"\.contract\.md$"]

# Each heading is a kind's name as the project glossary's "Kinds of Markdown file" spells it.
# The first pattern that matches the path picks the section, so the patterns keep that list's
# order, in which a kind is asked before any later kind that also matches its paths, such as
# a prompt in a skill's directory before the skill. Each pattern is anchored at a path
# component, so it matches the same file in any checkout.
KIND_SECTION_HEADING_AND_PATH_PATTERNS = [
    ("project instructions", r"(^|/)(CLAUDE|AGENTS)\.md$"),
    ("seat-brief", r"(^|/)CLAUDE\.local\.md$"),
    ("agent definition", r"(^|/)\.claude/agents/[^/]+\.md$"),
    # A prompt and a prompt template share the prompt section until a rule fits only one.
    # -prompt.md names either kind until the dot rule renames those files. Only a program reads
    # design-to-main's -agent-instructions.md files; an agent reads other -instructions.md
    # files, so their path does not say their kind.
    ("prompt", r"(^|/)[^/]+(\.prompt|\.prompt-template|-prompt|-agent-instructions)\.md$"),
    ("skill", r"(^|/)(\.claude|nn-systems)/skills/[^/]+/[^/]+\.md$"),
    ("session-handoff or next step file", r"(^|/)\.claude/handoffs/[^/]+-next-step-[^/]*\.md$"),
    ("glossary", r"(^|/)([^/]+-glossary|nedsnodes-sdlc-terms)\.md$"),
    ("design", r"(^|/)[^/]+\.design\.md$"),
    ("GHI-MD", r"(^|/)docs/issues/(queue/[^/]+|\d+-[^/]+)\.md$"),
    # A claim-check's proposed-improvements-or-changes-file sits beside its overview but is a
    # record of what the claim-check found, not a page.
    ("wiki page",
     r"(^|/)docs/nedsnodes-wiki/(queue/)?(?![^/]*-proposed-improvements-or-changes-)[^/]+\.md$"),
]


# /ghi-write marks a design GHI-MD with this front matter line, whatever its name ends in.
DESIGN_FRONT_MATTER_PATTERN = re.compile(r"\A---\n(?:.*\n)*?kind: design\n(?:.*\n)*?---\n")


def normalized_path(path):
    return Path(os.path.expanduser(path)).as_posix()


def record_or_walk_minutes_kind_for_path(path):
    """The kind, record or walk-minutes, whose path patterns match the path, or None."""
    normalized = normalized_path(path)
    for kind, pattern in RECORD_AND_WALK_MINUTES_MARKDOWN_FILE_KIND_AND_PATH_PATTERNS:
        if re.search(pattern, normalized):
            return kind
    return None


def kind_section_heading_for_path(path):
    """The heading of the standard's section that covers the path, or None when none does."""
    normalized = normalized_path(path)
    if record_or_walk_minutes_kind_for_path(normalized) is not None:
        return None
    if any(re.search(pattern, normalized) for pattern in UNCOVERED_PATH_PATTERNS):
        return None
    for heading, pattern in KIND_SECTION_HEADING_AND_PATH_PATTERNS:
        if re.search(pattern, normalized):
            if heading == "GHI-MD" and is_design_by_front_matter(normalized):
                return "design"
            return heading
    return None


def is_design_by_front_matter(path):
    """Whether the file at path exists and its front matter carries `kind: design`."""
    try:
        text = Path(path).read_text(encoding="utf-8")
    except FileNotFoundError:
        return False
    return DESIGN_FRONT_MATTER_PATTERN.match(text) is not None


class MarkdownFileStandardUnreadable(Exception):
    """The standard could not be read, or lacks a heading this program needs."""


def level_two_sections(text):
    """Map each level-2 heading's text to its section, heading line included.

    Lines inside fenced code blocks are not headings."""
    sections = {}
    current = None
    in_fence = False
    for line in text.splitlines(keepends=True):
        if line.lstrip().startswith(("```", "~~~")):
            in_fence = not in_fence
        elif not in_fence and line.startswith("## "):
            current = line[3:].strip()
            sections[current] = ""
        if current is not None:
            sections[current] += line
    return sections


def markdown_file_standard_sections(standard_path=MARKDOWN_FILE_STANDARD_PATH):
    """The standard's level-2 sections; raises MarkdownFileStandardUnreadable when one is missing."""
    try:
        text = Path(standard_path).read_text(encoding="utf-8")
    except OSError as error:
        raise MarkdownFileStandardUnreadable(f"cannot read {standard_path}: {error}") from error
    sections = level_two_sections(text)
    needed = [COMMON_PART_HEADING] + [heading for heading, _ in KIND_SECTION_HEADING_AND_PATH_PATTERNS]
    missing = [heading for heading in needed if heading not in sections]
    if missing:
        raise MarkdownFileStandardUnreadable(
            f"{standard_path} has no level-2 heading "
            + ", ".join(f'"## {heading}"' for heading in missing)
            + f", which {PROGRAM_NAME}.py's constants name")
    if exemptions_and_precedence_bullet(sections) is None:
        raise MarkdownFileStandardUnreadable(
            f"{standard_path}'s \"## {COMMON_PART_HEADING}\" has no line beginning "
            f"\"{COMMON_PART_EXEMPTIONS_AND_PRECEDENCE_BULLET_PREFIX}\", which {PROGRAM_NAME}.py's "
            "COMMON_PART_EXEMPTIONS_AND_PRECEDENCE_BULLET_PREFIX names")
    return sections


def exemptions_and_precedence_bullet(sections):
    """The common part's rule Exemptions and precedence, found by its prefix, or None."""
    return next((line for line in sections.get(COMMON_PART_HEADING, "").splitlines()
                 if line.startswith(COMMON_PART_EXEMPTIONS_AND_PRECEDENCE_BULLET_PREFIX)), None)


def main(argv, standard_path=MARKDOWN_FILE_STANDARD_PATH):
    if len(argv) == 1 and argv[0] in ("-h", "--help"):
        print(__doc__.strip())
        return 0
    if len(argv) != 1:
        print(f"{PROGRAM_NAME}: takes exactly one argument, the path of a Markdown file.\n"
              f"Usage: {PROGRAM_NAME}.py <path of a Markdown file>", file=sys.stderr)
        return 2
    try:
        sections = markdown_file_standard_sections(standard_path)
    except MarkdownFileStandardUnreadable as error:
        print(f"{PROGRAM_NAME}: {error}.\n"
              "Tell the user what this message says. Until the standard is fixed, write the "
              "file without it.", file=sys.stderr)
        return 2
    heading = kind_section_heading_for_path(argv[0])
    sys.stdout.write(sections[COMMON_PART_HEADING].rstrip("\n") + "\n")
    record_kind = record_or_walk_minutes_kind_for_path(argv[0])
    if record_kind is not None:
        print(f"\n{argv[0]} is a {record_kind} file, which the standard gives no section; "
              "the common part's exemption rule says which of the rules above it follows:\n"
              + exemptions_and_precedence_bullet(sections))
        return 0
    if heading is None:
        kinds = ", ".join(heading for heading, _ in KIND_SECTION_HEADING_AND_PATH_PATTERNS)
        print(f"{PROGRAM_NAME}: no section of the standard covers {argv[0]}; "
              f"its sections cover {kinds}. Follow the common part printed above.",
              file=sys.stderr)
        return 1
    sys.stdout.write("\n" + sections[heading].rstrip("\n") + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
