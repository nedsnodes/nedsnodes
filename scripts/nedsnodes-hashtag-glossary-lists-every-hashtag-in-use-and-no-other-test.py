#!/usr/bin/env python3
"""docs/nedsnodes-wiki/nedsnodes-hashtag-glossary.md lists every hashtag in use, and no other.

A hashtag is found in either form: closed, `#` and lowercase words joined by underscores and a closing `#`, as in
`#next_to_present#`; or open, without the closing `#`, which only a hashtag of two or more words can be told by, as in
`#next_to_present`. A `#` right after a letter, a digit, `/`, `.`, `&`, `;`, `#` or `]` starts no hashtag, and one
right after `(` starts no open one, so a URL fragment, a link to a heading or a colour is not read as one. An open
one-word hashtag is found only when it is one of those in use when hashtags came to take two or more words, such as
`#new`.

Fails, naming the hashtag and a file:
  - a hashtag used in a tracked file but not listed, searching every file but the glossary itself, docs/walk/ and
    cold-read-records/, which quote old text, docs/issues/, whose GHI-MDs quote proposed hashtags, and test files,
    whose fixtures hold made-up ones;
  - a hashtag listed but used in no tracked file other than the glossary and this suite, searching every other one,
    test files included, because a program may write a hashtag it builds from parts, such as `#case_against_` and a
    rating, that only a test spells whole;
  - a bullet, opening `- `, `* ` or `+ `, not written `` - `#<name>#` — <definition> ``, a name listed twice, names out of alphabetical order, or a
    one-word name other than those in use when hashtags came to take two or more words.
"""
import importlib.util
import re
import subprocess
import sys
import tempfile
from pathlib import Path

# Before anything runs git, so that a run started with GIT_DIR set builds its scratch repository where it says.
_git_environment_fixture_spec = importlib.util.spec_from_file_location(
    "git_redirecting_environment_removal_test_fixture",
    Path(__file__).resolve().with_name("git-redirecting-environment-removal-test-fixture.py"))
_git_environment_fixture = importlib.util.module_from_spec(_git_environment_fixture_spec)
_git_environment_fixture_spec.loader.exec_module(_git_environment_fixture)
_git_environment_fixture.remove_git_redirecting_environment_variables_from_this_process()

TOP = Path(__file__).resolve().parent.parent
GLOSSARY = "docs/nedsnodes-wiki/nedsnodes-hashtag-glossary.md"
# This suite's fixtures spell made-up hashtags, so they are no use of a listed one.
THIS_SUITE = Path(__file__).resolve().relative_to(TOP).as_posix()
NOT_SEARCHED_FOR_USES = (GLOSSARY, "docs/walk/", "cold-read-records/", "docs/issues/")
TEST_FILE = re.compile(r"(?:^|/)tests?/|-test\.(?:py|sh)$|(?:^|/)[^/]*-test-[^/]*/")
# A link to a heading, `](#heading)`, never ends with `#`, so only an open hashtag cannot start right after `(`.
NOT_A_CLOSED_HASHTAG_START = r"(?<![\w/.&;#\]])"
NOT_AN_OPEN_HASHTAG_START = r"(?<![\w/.&;#(\]])"
NAME = r"[a-z][a-z0-9]*(?:_[a-z0-9]+)*"
CLOSED = re.compile(NOT_A_CLOSED_HASHTAG_START + rf"#({NAME})#")
OPEN_HASHTAG_END = r"(?![\w#<-])"
OPEN_OF_TWO_OR_MORE_WORDS = re.compile(NOT_AN_OPEN_HASHTAG_START + r"#([a-z][a-z0-9]*(?:_[a-z0-9]+)+)"
                                       + OPEN_HASHTAG_END)
ANY_BULLET = re.compile(r"^[-*+] ")
BULLET = re.compile(rf"^- `#({NAME})#` — \S")
# The one-word hashtags in use when hashtags came to take two or more words; no other may be one word.
ONE_WORD_HASHTAGS_KEPT = frozenset({"code", "data", "edit", "new", "prose", "reason", "rejected", "replaces"})
OPEN_ONE_WORD_KEPT = re.compile(NOT_AN_OPEN_HASHTAG_START + "#(" + "|".join(sorted(ONE_WORD_HASHTAGS_KEPT))
                                + ")" + OPEN_HASHTAG_END)


def listed_names(glossary_text):
    """(the names the glossary's bullets list, in page order, problems with its bullets)."""
    names, problems = [], []
    for number, line in enumerate(glossary_text.split("\n"), 1):
        if not ANY_BULLET.match(line):
            continue
        bullet = BULLET.match(line)
        if bullet is None:
            problems.append(f"{GLOSSARY}:{number}: the bullet is not written "
                            "`` - `#<name>#` — <definition> ``; write it so")
            continue
        names.append(bullet[1])
        if "_" not in bullet[1] and bullet[1] not in ONE_WORD_HASHTAGS_KEPT:
            problems.append(f"{GLOSSARY}:{number}: #{bullet[1]}# is one word, and a new hashtag takes two or more "
                            "words joined by underscores; name it with more words")
    if not names:
        problems.append(f"{GLOSSARY} lists no hashtag in the form `` - `#<name>#` — <definition> ``, so nothing "
                        "was checked; list each hashtag in that form")
    for name in sorted({name for name in names if names.count(name) > 1}):
        problems.append(f"{GLOSSARY} lists #{name}# more than once; keep one bullet")
    for before, after in zip(names, names[1:]):
        if after < before:
            problems.append(f"{GLOSSARY} lists #{after}# after #{before}#; put the bullets in alphabetical order")
    return names, problems


def hashtags_used(texts):
    """{name: the first file using it} for every hashtag found in texts, {path: text}, in either form."""
    used = {}
    for path, text in texts.items():
        for pattern in (CLOSED, OPEN_OF_TWO_OR_MORE_WORDS, OPEN_ONE_WORD_KEPT):
            for found in pattern.finditer(text):
                used.setdefault(found[1], path)
    return used


def is_used(name, texts):
    use = re.compile(f"{NOT_A_CLOSED_HASHTAG_START}#{re.escape(name)}#"
                     f"|{NOT_AN_OPEN_HASHTAG_START}#{re.escape(name)}{OPEN_HASHTAG_END}")
    return any(use.search(text) for path, text in texts.items() if path not in (GLOSSARY, THIS_SUITE))


def problems_in(texts):
    """Every problem with texts, {repository path: text}, which holds the glossary among the tracked files."""
    if GLOSSARY not in texts:
        return [f"{GLOSSARY} is not a tracked file, so no hashtag could be checked; add the page"]
    names, problems = listed_names(texts[GLOSSARY])
    searched = {path: text for path, text in texts.items()
                if not path.startswith(NOT_SEARCHED_FOR_USES) and not TEST_FILE.search(path)}
    for name, path in sorted(hashtags_used(searched).items()):
        if name not in names:
            problems.append(f"{path} uses #{name}#, which {GLOSSARY} does not list; add its bullet, with its "
                            "definition, in the same commit")
    for name in names:
        if not is_used(name, texts):
            problems.append(f"{GLOSSARY} lists #{name}#, which no other tracked file uses; remove its bullet")
    return problems


def tracked_texts(top):
    listed = subprocess.run(["git", "-C", str(top), "ls-files", "-z"], capture_output=True, check=True).stdout
    texts = {}
    for path in filter(None, listed.decode("utf-8").split("\0")):
        try:
            texts[path] = (top / path).read_text(encoding="utf-8")
        except (UnicodeDecodeError, IsADirectoryError, FileNotFoundError):
            continue
    return texts


failures = []


def check(label, condition, detail=""):
    print(f"{'PASS' if condition else 'FAIL'}  {label}" + ("" if condition else f": {detail}"))
    if not condition:
        failures.append(label)


GOOD_GLOSSARY = ("# Hashtag glossary\n\n"
                 "- `#new#` — a one-word hashtag.\n"
                 "- `#next_to_present#` — names the waiting item.\n"
                 "- `#root_cause#` — names the root cause.\n")
GOOD = {GLOSSARY: GOOD_GLOSSARY,
        "docs/a.md": "#next_to_present item 3 of 9\n- **#root_cause#** the cause\n#new text\n"}



def with_texts(changes):
    return {**GOOD, **changes}


def with_glossary(text):
    return with_texts({GLOSSARY: text})


check("a glossary listing every hashtag used, open or closed, passes", problems_in(GOOD) == [],
      problems_in(GOOD))
unlisted = problems_in(with_texts({"docs/b.md": "see #branch_conflicts_with_main# here\n"}))
check("a closed hashtag the glossary does not list fails, naming it and its file",
      any("docs/b.md uses #branch_conflicts_with_main#" in problem for problem in unlisted), unlisted)
unlisted_open = problems_in(with_texts({"docs/b.md": "#approval_walk_paused for lunch\n"}))
check("an open hashtag of two words the glossary does not list fails",
      any("#approval_walk_paused#" in problem for problem in unlisted_open), unlisted_open)
not_hashtags = problems_in(with_texts({"docs/b.md": "https://x/pull/1#discussion_r5 [a](#some_heading) #fff a#b_c "
                                                    "#task here #discussion_r<id>\n"}))
check("a URL fragment, a heading link, a colour, a placeholder and a one-word open mark not kept from before the "
      "two-word rule are not read as hashtags",
      not_hashtags == [], not_hashtags)
check("a hashtag only quoted in walk files, cold-read-records, GHI-MDs or tests is not required to be listed",
      problems_in(with_texts({"docs/walk/w-minutes.md": "#user_alert 3\n",
                              "cold-read-records/r/x.md": "#user_alert# 3\n",
                              "docs/issues/1-x.md": "#proposed_hashtag\n",
                              "scripts/thing-test.py": "'#made_up_marker x'\n"})) == [],
      "a skipped file's hashtag was required")
in_parentheses = problems_in(with_texts({"docs/b.md": "For example: (#made_up_marker#)\n"}))
check("a closed hashtag right after `(` the glossary does not list fails",
      any("docs/b.md uses #made_up_marker#" in problem for problem in in_parentheses), in_parentheses)
check("a listed hashtag used only closed right after `(` counts as used",
      problems_in(with_texts({"docs/a.md": "#next_to_present item 3\n(#root_cause#) the cause\n#new text\n"})) == [],
      "a closed use after `(` did not count")
unlisted_kept = problems_in(with_glossary(GOOD_GLOSSARY.replace("- `#new#` — a one-word hashtag.\n", "")))
check("a kept one-word hashtag used only open whose bullet is gone fails",
      any("docs/a.md uses #new#" in problem for problem in unlisted_kept), unlisted_kept)
unused = problems_in(with_texts({"docs/a.md": "#next_to_present item 3\n#new text\n"}))
check("a listed hashtag no other file uses fails", any("lists #root_cause#, which no" in problem for problem in unused),
      unused)
check("a listed hashtag used only in a test file counts as used",
      problems_in(with_texts({"docs/a.md": "#next_to_present item 3\n#new text\n",
                              "scripts/x-test.py": "'#root_cause the cause'\n"})) == [],
      "a use in a test file did not count")
unused_new = problems_in(with_texts({"docs/a.md": "#next_to_present item 3\n- **#root_cause#** the cause\n"}))
check("a listed one-word hashtag no file uses fails", any("lists #new#" in problem for problem in unused_new),
      unused_new)
check("a one-word name inside a longer hashtag is not a use of it",
      any("lists #new#" in problem for problem in problems_in(with_texts(
          {"docs/a.md": "#next_to_present item 3\n#root_cause x\n#new_if_d text\n"}))),
      "#new_if_d counted as a use of #new")
unordered = problems_in(with_glossary(GOOD_GLOSSARY.replace("- `#new#` — a one-word hashtag.\n", "")
                                      + "- `#new#` — a one-word hashtag.\n"))
check("bullets out of alphabetical order fail", any("put the bullets in alphabetical order" in p for p in unordered),
      unordered)
doubled = problems_in(with_glossary(GOOD_GLOSSARY + "- `#root_cause#` — again.\n"))
check("a name listed twice fails", any("more than once" in p for p in doubled), doubled)
malformed = problems_in(with_glossary(GOOD_GLOSSARY + "- `#root_causes` — no closing hash.\n"))
check("a bullet not in the listed form fails", any("is not written" in p for p in malformed), malformed)
one_word = problems_in(with_texts({GLOSSARY: GOOD_GLOSSARY + "- `#task#` — a new one-word hashtag.\n",
                                   "docs/c.md": "#task S1\n"}))
check("a one-word hashtag not kept from before the two-word rule fails", any("is one word" in p for p in one_word),
      one_word)
star_doubled = problems_in(with_glossary(GOOD_GLOSSARY + "* `#root_cause#` — again.\n"))
check("a bullet opening `* ` fails its form", any("is not written" in p for p in star_doubled), star_doubled)
only_in_this_suite = problems_in(with_texts({"docs/a.md": "#next_to_present item 3\n#new text\n",
                                             THIS_SUITE: "'#root_cause the cause'\n"}))
check("a listed hashtag used only in this suite's own fixtures fails",
      any("lists #root_cause#, which no" in p for p in only_in_this_suite), only_in_this_suite)
placeholder_only = problems_in(with_texts({"docs/a.md": "#next_to_present item 3\n#new text\n#root_cause<id>\n"}))
check("a listed hashtag used only as the start of a placeholder, such as #root_cause<id>, fails",
      any("lists #root_cause#, which no" in p for p in placeholder_only), placeholder_only)
empty = problems_in(with_glossary("# Hashtag glossary\n"))
check("a glossary with no readable bullet fails rather than passes", any("lists no hashtag" in p for p in empty), empty)
check("a missing glossary fails", any("is not a tracked file" in p for p in problems_in({"docs/a.md": "#x_y\n"})),
      "no failure for a missing glossary")


with tempfile.TemporaryDirectory() as directory:
    subprocess.run(["git", "init", "-q", directory], check=True)
    Path(directory, "docs").mkdir()
    Path(directory, "docs", "a.md").write_text("#new_hashtag_here\n", encoding="utf-8")
    subprocess.run(["git", "-C", directory, "add", "-A"], check=True)
    check("tracked files are read from git", tracked_texts(Path(directory)) == {"docs/a.md": "#new_hashtag_here\n"},
          tracked_texts(Path(directory)))

repository_problems = problems_in(tracked_texts(TOP))
check(f"{GLOSSARY} lists every hashtag in use and no other", repository_problems == [],
      "\n  " + "\n  ".join(repository_problems))

sys.exit(1 if failures else 0)
