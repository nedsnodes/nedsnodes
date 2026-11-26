#!/usr/bin/env python3
"""Post a pull request review, the Claude reviewer's as mac-claude or merge-lane-2's as ned-review-merge, then read it back from GitHub.

Did the review get posted on the named nn-head-commit, as the review file
says? Exits 0 if the review was posted and read back as expected, 2 otherwise.

Usage:
  scripts/merge-lane-pull-request-reviewer-review-post-and-read-back.py
      --pull-request N --head-commit SHA
      [--github-account mac-claude|ned-review-merge]
      [--merge-lane-worktrees-and-outputs-directory DIR]
      [--pull-request-review-plan-program PATH]
      [--findings-record-codex-finding-match-program PATH] <review file>

The review file is one JSON object with exactly "verdict", APPROVE or
REQUEST_CHANGES; "body", the review's text; and "comments", a list of inline
comments. A COULD_NOT_REVIEW verdict is refused: nothing is posted for a
review that did not finish.

With --github-account mac-claude, the default, the file is the Claude
reviewer's answer without its "note", which is for merge-lane-2 and never
posted: the shape of merge-lane-pull-request-claude-reviewer-review-schema.json
less "note", each comment with exactly "path", "line" and "body". A file that
still carries "note" is refused, like any other extra key. It is posted with
the token in ~/.config/nedsnodes/mac-claude.token, with the file's verdict.
Its event is the verdict when the pull request's author is ned-review-merge,
because GitHub refuses an approving review from a pull request's author and
merge-lane-2 approves as that account; for any other author the event is
COMMENT, and merge-lane-2 records the verdict itself.

With --github-account ned-review-merge, the file is merge-lane-2's own review,
which restates every finding the round's reviewers raised, each comment with
exactly "path", "line", "body" and "finding_category", one of FINDING_CATEGORIES, the
first four categories of the goals and philosophy page, and may carry "nit": true, which marks a
fix-in-maintenance finding as a nit for the fix-round program to carry; "nit" with any other
value, or on a comment of any other category, is refused. It is posted with the merge
account's token, read as
merge-lane-pull-request-helpers-common-options-paths-and-token.py reads it.
Its event is the verdict, except on a pull request ned-review-merge opened,
where GitHub refuses an approving or changes-requesting review from the
author: there the event is COMMENT, the body still opens with the verdict line
and carries every mark below, and the fix-round program reads such a review
that opens with REQUEST_CHANGES as a round. For this file, this
program alone writes what the fix-round program,
pull-request-fix-round-author-brief-from-blocking-findings-and-one-commit-every-finding-answered-check.py,
reads blocking findings by, using that program's BLOCKING_MARKER_PATTERN,
and nits by, using its NIT_MARK, and the category marks that
pull-request-follow-up-request-after-merge-finding-answers-and-next-step.py
reads non-blocking findings by:
- each comment is posted opening with review_comment_opening_mark_for_finding_category() of its
  category: "**Blocks** " for must-fix-now, and the category in bold, as in
  "**fix-next** ", for the other three, and NIT_MARK,
  "**fix-in-maintenance, nit** ", for a nit; a comment whose body already opens
  with a blocking mark, a category mark or the nit mark is refused;
- a comment with the same path, line and posted body as an earlier one is
  dropped, since the fix-round program counts such a repost once;
- when N comments are must-fix-now, N at least 1, the body carries
  "**Blocking: N**" alone on its line, after the verdict line and a blank
  line, the only place the fix-round program's BLOCKING_COUNT_PATTERN reads
  it, and only on merge-lane-2's reviews. No count is written when N is 0;
- after the count, a blank line and the fix-round program's REVIEW_BODY_POSTED_BY_MERGE_LANE_LINE_FORMAT
  naming the merge-lane that posts the review, the agent-seat GIT_AUTHOR_NAME names, which
  the fix-round program sends the round's messages to. Every merge-lane posts as
  ned-review-merge, so nothing else on GitHub tells them apart. A review that requests
  changes is refused when GIT_AUTHOR_NAME is not a merge-lane's name, such as merge-lane-1;
- the posted verdict is REQUEST_CHANGES when any comment is must-fix-now and
  APPROVE otherwise. A file whose verdict is REQUEST_CHANGES with no
  must-fix-now comment is refused rather than posted as an approval.

merge-lane-2's verdict review answers for every Codex finding on the reviewed
commit. The program reads each codex-review-run-record.json under
<--merge-lane-worktrees-and-outputs-directory>/cx/pr<n>-*/ whose "head_commit"
is --head-commit, as merge-lane-code-review-codex-cell-run-on-pull-request-head.py
writes it, and each finding heading, "- [Codex priority Pn (P0 highest)] ..." or
the older "- [Pn] ...", of the report of each run that exited 0. A report that
is Codex's review object, which a Codex cell older than its conversion wrote, is
read through scripts/code-review-codex-cell.py's conversion first, so its
findings get the ids they would have had in prose; one the conversion refuses is
refused here, with the command that runs the cell again. A report with no finding
heading is refused the same way when it holds text such as '"findings": [{', as
Codex's review object does whether or not it is valid JSON, or when some JSON
value in it decodes to an object with a non-empty "findings" list, as one with
escaped keys does. Not handled: a clean report that quotes such text or such an
object is refused too; the agent then asks merge-lane-2. Then:
- the file's optional "merge_lane_codex_review_finding_grades" lists one
  {"finding": <the id the refusal prints>, "grade": <grade>} per finding, the grade one
  of FINDING_CATEGORIES or "does-not-hold", which alone also takes a one-line "reason".
  The program refuses a finding with no grade, a grade for no finding on this commit, and
  a must-fix-now, fix-next, fix-in-maintenance or file-for-later grade with no comment of that
  finding_category whose body names the finding as "Codex finding <id>", since the fix-round program and the
  after-merge follow-up program read findings only from comments. It adds the grades to
  the posted body under a heading. Two findings of one report with the same priority and
  heading text get one id, and one grade answers both;
- before the grades are checked, each Codex finding whose text answers `#defect_already_on_main` yes
  goes to
  scripts/findings-record-codex-finding-match-and-row-add-or-decide.py match, which
  answers SAME with the findings record row already holding the finding, or NEW. A SAME
  finding whose text answers `#pull_request_triggers_the_defect` no needs no grade; one
  that answers yes is graded like any other. For a SAME finding with no grade, the posted body quotes its row's state, grade and decision
  under a heading, and calls it a possible regression when the row is fixed. Once every
  grade is accepted, the same program's add adds each NEW finding, with its grade, to the
  findings record, before the review is posted. The success line counts the findings held
  and added, and names each possible regression and possible miss. When either
  subcommand exits nonzero or prints an answer this program cannot read, nothing is
  posted;
- a run that found nothing, or exited nonzero, needs no grade, and the review posts as
  it would without this check;
- when no run record names the commit, the program reads the commit's review tier from
  pull-request-review-plan.py --json, the delta tier when the plan says a delta-only
  review applies. At no-reviewer-tier no Codex run belongs to the review, and it posts
  as it would without this check, unless the file grades Codex findings, which it then
  refuses. At any other tier the program refuses until the Codex cell has run on the
  commit, with or without grades in the file, and prints the command that runs it from
  the plan's base, the earlier reviewed head when a delta-only review applies, the merge
  base otherwise, naming the commit so the run refuses a pr<n>-head worktree at another one.
  A plan that fails, or does not give a known tier for this
  commit, also refuses, since the program then cannot tell whether a run belongs.

merge-lane-2's review file may instead be exactly {"body": ...}, a review with
no verdict, posted as COMMENT with the body as written, for the review
scripts/merge-gate.sh asks for when the pull request has activity after
reviewed-since: one saying what merge-lane-2 read. The program asks the gate's
own check, merge-gate.sh --print-new-activity-count-after-reviewed-since-bound,
how much was posted or edited after the latest time the gate accepts as
reviewed-since, and refuses the file when the answer is nothing, since a verdict
review is then what is due.

GitHub refuses a whole review when one inline comment is on a line outside the
pull request's diff, so each comment whose path and line are not on the new
side of the diff GitHub reports for the pull request is moved into the body,
under a heading, as `path:line: comment`, each line of the comment after its
first indented, so that no line of a comment's text can be read back as the
start of another; the success line ends with how many were moved. A file whose diff GitHub does not show, such as a binary
file, takes no inline comments. A must-fix-now comment moved into the body
still counts in N but carries no inline mark; the fix-round program refuses a
round whose review's body holds one, instead of missing the finding.

The body starts with a line APPROVE or REQUEST_CHANGES, so the verdict shows
even when the review is posted as a comment.

For a review with a verdict, the success line also counts the reviewer's findings
that lack, or leave unanswered, one of the hashtag lines docs/agents/pr-reviewer-instructions.md asks
each finding on code to end with, FINDING_FACT_LINE_HASHTAGS, and names each such finding and the hashtags it
lacks; a line that starts with the older label a hashtag replaced, from FINDING_FACT_LINE_OLDER_LABELS, counts
as that hashtag's line. The findings are the comments of the
Claude reviewer's file, and for merge-lane-2's review, the Codex findings on the
commit, each finding's text running from its heading to the next one. The posted review is then read
back by the id GitHub returned, and its state and commit must be the ones
asked for.

An interrupt or SIGTERM during the post or the read-back kills gh and exits 2,
saying the review may or may not be posted if it came during the post, and
that review <id> was posted if it came after GitHub returned the id.
"""

import argparse
import hashlib
import importlib.util
import json
import os
import re
import shlex
import signal
import subprocess
import sys
from pathlib import Path


def load_program(file_name, module_name):
    spec = importlib.util.spec_from_file_location(
        module_name, Path(__file__).resolve().with_name(file_name))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


common = load_program("merge-lane-pull-request-helpers-common-options-paths-and-token.py",
                      "merge_lane_pull_request_helpers_common")
codex_cell = load_program("code-review-codex-cell.py", "code_review_codex_cell")
fix_round = load_program(
    "pull-request-fix-round-author-brief-from-blocking-findings-and-one-commit-every-finding-"
    "answered-check.py", "pull_request_fix_round_author_brief")

REPOSITORY = "nedsnodes/nedsnodes"
MAC_CLAUDE_ACCOUNT = "mac-claude"
MERGE_LANE_ACCOUNT = "ned-review-merge"
POSTED_VERDICTS = ("APPROVE", "REQUEST_CHANGES")
MERGE_GATE = Path(__file__).resolve().with_name("merge-gate.sh")
NEW_ACTIVITY_COUNT_OPTION = "--print-new-activity-count-after-reviewed-since-bound"
# The goals and philosophy page's first four categories of a finding; only the first blocks. Its fifth, Declined,
# is the grade DOES_NOT_HOLD_GRADE. A program after the
# post reads each category only from comments, so a Codex finding graded with any of them needs one.
FINDING_CATEGORIES = ("must-fix-now", "fix-next", "fix-in-maintenance", "file-for-later")
BLOCKING_CATEGORY = "must-fix-now"
# The only category a finding marked "nit" may have; the fix-round program carries its nits.
NIT_CATEGORY = "fix-in-maintenance"
BLOCKING_MARK = "**Blocks** "
NON_BLOCKING_CATEGORY_MARK_FORMAT = "**{category}** "
BLOCKING_COUNT_FORMAT = "**Blocking: {count}**"
DOES_NOT_HOLD_GRADE = "does-not-hold"
CODEX_FINDING_GRADES_KEY = "merge_lane_codex_review_finding_grades"
NO_REVIEWER_TIER = "no-reviewer-tier"
REVIEW_TIERS_THAT_RUN_CODEX = ("codex-review-and-head-tests-tier", "claude-and-codex-review-and-head-tests-tier")
REVIEW_PLAN_PROGRAM = Path(__file__).resolve().with_name("pull-request-review-plan.py")
# The plan prints its JSON and exits 3 when a message in it has no fast-read command; its tier still holds.
REVIEW_PLAN_EXIT_CODES_WITH_A_PLAN = (0, 3)
# The plan makes several GitHub reads and a diff of the pull request.
REVIEW_PLAN_TIMEOUT_SECONDS = 300
CODEX_FINDING_HEADING = re.compile(r"^- \[(?:Codex priority )?(P[0-3])(?: \(P0 highest\))?\] (.+)$")
# The review worktree's own path differs between runs on the same commit.
CODEX_FINDING_WORKTREE_PATH = re.compile(r"\S*/pr\d+-head/")
CODEX_REPORT_PROVENANCE_COMMENT = re.compile(r"\A<!--.*?-->\n?", re.DOTALL)
CODEX_REVIEW_OBJECT_NON_EMPTY_FINDINGS_LIST_REGEX = re.compile(r'"findings"\s*:\s*\[\s*\{')
CODEX_GRADES_BODY_HEADING = "**Codex findings graded:**"
FINDINGS_RECORD_BODY_HEADING = "**Codex findings the findings record already holds:**"
FINDINGS_RECORD_CODEX_FINDING_MATCH_PROGRAM = Path(__file__).resolve().with_name(
    "findings-record-codex-finding-match-and-row-add-or-decide.py")
# docs/agents/pr-reviewer-instructions.md asks a reviewer to end each finding on code with these hashtag lines.
FINDING_FACT_LINE_HASHTAGS = ("#defect_already_on_main", "#pull_request_triggers_the_defect",
                              "#false_report_of_success_on_failure", "#defect_evidence")
# Reviewers may still write the labels the hashtags replaced, each followed by a colon.
FINDING_FACT_LINE_OLDER_LABELS = {"Main has it": "#defect_already_on_main",
                                  "This pull request makes it happen": "#pull_request_triggers_the_defect",
                                  "Reports success on failure": "#false_report_of_success_on_failure",
                                  "Shown by": "#defect_evidence"}
# A hashtag or a label may open a list item of any kind and sit inside code or bold marks, and a label's colon
# may sit inside or outside them.
FINDING_FACT_LINE = re.compile(
    r"^[ \t]*(?:(?:[-*+]|\d+[.)])[ \t]+)?[`*_]*(?:("
    + "|".join(re.escape(hashtag) for hashtag in FINDING_FACT_LINE_HASHTAGS)
    + r")(?!\w)|("
    + "|".join(re.escape(label) for label in FINDING_FACT_LINE_OLDER_LABELS)
    + r")[`*_]*:)(.*)$", re.MULTILINE)
FINDING_FACT_LINE_MARKS_AND_SPACE = re.compile(r"[`*_\s]")
OUTSIDE_THE_DIFF_HEADING = fix_round.OUTSIDE_THE_DIFF_HEADING
OUTSIDE_THE_DIFF_LINE_FORMAT = "- `{path}:{line}`: {body}"
OUTSIDE_THE_DIFF_LINE_PATTERN = fix_round.OUTSIDE_THE_DIFF_LINE_PATTERN
# Two spaces also keep a continuation line inside its list item when GitHub renders the body.
OUTSIDE_THE_DIFF_CONTINUATION_INDENT = fix_round.OUTSIDE_THE_DIFF_CONTINUATION_INDENT
HUNK_HEADER = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@")
# The state GitHub gives a review posted with each event.
EVENT_STATES = {"APPROVE": "APPROVED", "REQUEST_CHANGES": "CHANGES_REQUESTED",
                "COMMENT": "COMMENTED"}
EXIT_POSTED = 0
EXIT_NOT_POSTED = 2

REVIEW_FILE_UNUSABLE = (
    "review not posted: the review file {path} {reason}.\n"
    "Do not post the review any other way.\n"
    "If the file came from a reviewer's run, "
    "scripts/merge-lane-pull-request-claude-reviewer-headless-run-and-review-post.py, which ran "
    "the reviewer, should have refused this file instead of handing it to the posting script.\n"
    "In that case, do not run "
    "scripts/merge-lane-pull-request-claude-reviewer-headless-run-and-review-post.py again, for "
    "any pull request, until the user answers.\n"
    "Tell the user this whole message.")
NO_NEW_ACTIVITY = (
    "review not posted: the review file {path} holds a review with no verdict, which answers only the "
    "gate's refusal for activity after reviewed-since, and scripts/merge-gate.sh finds nothing posted or "
    "edited on pull request {number} after {account}'s latest review or the pin.\n"
    "Do not post the review any other way.\n"
    "If you have reviewed the nn-head-commit, give the file your verdict and findings, in the form this "
    "program's docstring describes, and run the same command again.\n"
    "If the gate refused for new activity, run the gate again: what it counted may have been your own "
    "review.")
NOT_A_MERGE_LANE = (
    "review not posted: the review requests changes, so its body must name the merge-lane that posts it, "
    "which this program takes from GIT_AUTHOR_NAME, but GIT_AUTHOR_NAME is {name!r}, not a merge-lane's name "
    "such as merge-lane-1. The fix-round program sends the pull request author's messages to the merge-lane "
    "that line names.\n"
    "Do not post the review any other way.\n"
    "If you are a merge-lane, run the same command again with your agent-seat's name before it, as in "
    "GIT_AUTHOR_NAME=merge-lane-1 python3 scripts/merge-lane-pull-request-reviewer-review-post-and-read-back.py ...\n"
    "Otherwise tell the user this message.")
NOT_POSTED = (
    "review not posted: {reason}.\n"
    "Do not post the review any other way.\n"
    "If the cause above is one you can fix, fix it and run the same command again; otherwise, "
    "tell the user this message.")
POST_FAILED = (
    "review may or may not be posted: posting the review failed: {reason}\n"
    "GitHub may have made the review before the failure, and a second post would add a second "
    "review.\n"
    "Before running this command again, list {account}'s reviews on commit {head} of pull "
    "request {number}:\n"
    "  gh api --paginate 'repos/{repository}/pulls/{number}/reviews' --jq "
    "'.[] | select(.user.login == \"{account}\" and .commit_id == \"{head}\") "
    "| [.id, .state, .html_url] | @tsv'\n"
    "If it lists nothing, run the posting command that printed this message again.\n"
    "If it lists one or more reviews, do not post again: {account} already has a review on this "
    "commit, whether this command's post or an earlier one, and the list gives each one's id and "
    "link.")
CODEX_FINDINGS_NOT_GRADED = (
    "review not posted: {count} Codex finding(s) on commit {head} have no grade in the review file "
    "{path}:\n{findings}\n"
    "Add one entry per finding to the file's \"merge_lane_codex_review_finding_grades\" list, as "
    "{{\"finding\": \"<id>\", \"grade\": \"<grade>\"}}, the grade one of {grades}.\n"
    "When a finding does not hold, use the grade does-not-hold and add a one-line \"reason\".\n"
    "Then run the same command again.")
NO_CODEX_RUN_RECORD = (
    "review not posted: no Codex run record under {directory} names commit {head}, and "
    "scripts/pull-request-review-plan.py gives this review {tier}, which runs Codex.\n"
    "Run the Codex cell on this commit from {base_reason}, the base the review plan gives:\n"
    "  {codex_cell_command}\n"
    "Then run this posting command again.")
CODEX_GRADE_WITH_NO_COMMENT = (
    "review not posted: the review file {path} grades {count} Codex finding(s) must-fix-now, fix-next, "
    "fix-in-maintenance or file-for-later, but has no comment of that \"finding_category\" whose \"body\" names the "
    "finding as \"Codex finding <id>\":\n{findings}\n"
    "The programs that act on such findings, "
    "scripts/pull-request-fix-round-author-brief-from-blocking-findings-and-one-commit-every-finding-answered-check.py "
    "and scripts/pull-request-follow-up-request-after-merge-finding-answers-and-next-step.py, read findings "
    "only from comments, so the grade alone would leave the finding unacted on.\n"
    "For each finding listed, add to \"comments\" an entry like the others, with \"path\", \"line\", "
    "\"body\" and \"finding_category\", the category being the grade and the body naming the finding "
    "anywhere as \"Codex finding <id>\", such as \"... (Codex finding <id>)\".\n"
    "If the finding does not hold after all, change its grade to does-not-hold with a one-line \"reason\" "
    "instead.\n"
    "Then run this posting command again.\n"
    "From now on, give every Codex finding you grade must-fix-now, fix-next, fix-in-maintenance or "
    "file-for-later a comment of that category naming it as \"Codex finding <id>\".")
# How a comment names the Codex finding it carries, the only form the grade check accepts; restated findings are
# compared without it, because a finding's id changes when its line range does.
CODEX_FINDING_ID_MARK_IN_REVIEW_COMMENT_PATTERN = re.compile(r" ?\(?Codex finding ([0-9a-f]{12})\)?")
REVIEW_TIER_UNREADABLE = (
    "review not posted: no Codex run record names commit {head}, and its review tier could not be read "
    "from {program}: {reason}\n"
    "Without the tier, this program cannot tell whether a Codex run belongs to this review.\n"
    "If the text above gives a step, do it, then run the same command again.\n"
    "Otherwise, tell the user this message.")
READ_BACK_FAILED = (
    "review {review_id} was posted, but reading it back failed: {reason}\n"
    "Do not post the review again: it is on the pull request.\n"
    "Check review {review_id} on pull request {number} yourself.")
READ_BACK_DIFFERS = (
    "review {review_id} was posted on pull request {number}, but GitHub's copy differs from what "
    "was asked for: {differences}.\n"
    "The review is on the pull request as GitHub kept it: in each difference above, the first "
    "value is what GitHub kept and the second is what was asked for.\n"
    "Do not post the review again: a second post adds a second review and leaves this one as "
    "it is.\n"
    "Look at the review with:\n"
    "  gh api 'repos/{repository}/pulls/{number}/reviews/{review_id}' --jq "
    "'[.state, .commit_id, .html_url] | @tsv'\n"
    "Then tell the user this whole message and what that command printed, and do nothing more "
    "with this review or this pull request's merge until the user answers.")


class ReviewFileUnusable(Exception):
    pass


class GhFailed(Exception):
    pass


class CodexRunRecordUnusable(Exception):
    pass


def read_review_file(path, account):
    """Return (verdict, body, comments, Codex answers) from the account's review file, verdict None for
    merge-lane-2's review with no verdict, or raise ReviewFileUnusable. The Codex answers are the file's
    grades of Codex findings, as a dict holding CODEX_FINDING_GRADES_KEY when the file has it."""
    try:
        review = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError) as error:
        raise ReviewFileUnusable(f"could not be read: {error}")
    except ValueError as error:
        raise ReviewFileUnusable(f"is not JSON: {error}")
    if account == MERGE_LANE_ACCOUNT and isinstance(review, dict) and set(review) == {"body"}:  # pragma: no mutate, --github-account allows only mac-claude and ned-review-merge, and mac-claude sorts before ned-review-merge, so >= gives what == gives
        if not isinstance(review["body"], str) or not review["body"].strip():
            raise ReviewFileUnusable("has no \"body\" text")
        return None, review["body"], [], {}
    codex_answers = {}
    if account == MERGE_LANE_ACCOUNT and isinstance(review, dict):  # pragma: no mutate, --github-account allows only mac-claude and ned-review-merge, and mac-claude sorts before ned-review-merge, so >= gives what == gives
        review = dict(review)
        if CODEX_FINDING_GRADES_KEY in review:
            codex_answers[CODEX_FINDING_GRADES_KEY] = review.pop(CODEX_FINDING_GRADES_KEY)
        codex_answers_check(codex_answers)
    if not isinstance(review, dict) or set(review) != {"verdict", "body", "comments"}:
        raise ReviewFileUnusable(
            "must hold one JSON object with exactly \"verdict\", \"body\" and \"comments\""
            + (", or, for a review with no verdict, exactly \"body\"" if account == MERGE_LANE_ACCOUNT else ""))
    verdict, body, comments = review["verdict"], review["body"], review["comments"]
    if verdict not in POSTED_VERDICTS:
        raise ReviewFileUnusable(
            f"has the verdict {verdict!r}; only {' and '.join(POSTED_VERDICTS)} are posted")
    if not isinstance(body, str) or not body.strip():
        raise ReviewFileUnusable("has no \"body\" text")
    categorized = account == MERGE_LANE_ACCOUNT  # pragma: no mutate, --github-account allows only mac-claude and ned-review-merge, and mac-claude sorts before ned-review-merge, so >= gives what == gives
    keys = {"path", "line", "body", "finding_category"} if categorized else {"path", "line", "body"}
    if not isinstance(comments, list) or not all(
            isinstance(comment, dict) and (set(comment) == keys or categorized and set(comment) == keys | {"nit"})
            and isinstance(comment["path"], str)
            and isinstance(comment["line"], int) and not isinstance(comment["line"], bool)
            and isinstance(comment["body"], str)
            for comment in comments):
        raise ReviewFileUnusable(
            "has a \"comments\" entry that is not exactly a text \"path\", a number \"line\" and "
            "a text \"body\"" + (", and a \"finding_category\"," if categorized else ",")
            + " with no other keys" + (" but an optional \"nit\": true" if categorized else ""))
    if not categorized:
        return verdict, body, comments, codex_answers
    for comment in comments:
        where = f"{comment['path']}:{comment['line']}"
        if comment["finding_category"] not in FINDING_CATEGORIES:
            raise ReviewFileUnusable(
                f"has a comment on {where} whose \"finding_category\" is {comment['finding_category']!r}, not one "
                f"of {', '.join(FINDING_CATEGORIES)}")
        if "nit" in comment and comment["nit"] is not True:
            raise ReviewFileUnusable(
                f"has a comment on {where} whose \"nit\" is {comment['nit']!r}; give \"nit\" only as "
                f"the JSON value true, on a nit, a small fix that names no failure, such as a misspelt name, "
                f"and omit the \"nit\" key from any other comment")
        if "nit" in comment and comment["finding_category"] != NIT_CATEGORY:
            raise ReviewFileUnusable(
                f"has a comment on {where} with \"nit\": true whose \"finding_category\" is "
                f"{comment['finding_category']!r}; only a {NIT_CATEGORY} finding can be a nit, so make its "
                f"category {NIT_CATEGORY} or omit the \"nit\" key")
        mark = fix_round.BLOCKING_MARKER_PATTERN.match(comment["body"].lstrip())
        if mark:
            raise ReviewFileUnusable(
                f"has a comment on {where} whose body already opens with the blocking mark "
                f"{mark.group(0)}; this program writes that mark for each {BLOCKING_CATEGORY} "
                f"comment, so remove the mark from the start of its \"body\"")
        marked = finding_category_and_text_read_from_review_comment_opening_mark(comment["body"])
        if marked:
            raise ReviewFileUnusable(
                f"has a comment on {where} whose body already opens with the category mark "
                f"{review_comment_opening_mark_for_finding_category(marked[0], marked[2]).strip()}, the bold "
                f"opening that names the finding's category; this program writes that mark from the comment's "
                f"\"finding_category\" and \"nit\", so remove the mark from the start of its \"body\"")
    if verdict == "REQUEST_CHANGES" and not any(  # pragma: no mutate, the verdict is APPROVE or REQUEST_CHANGES by now, and APPROVE sorts first, so >= gives what == gives
            comment["finding_category"] == BLOCKING_CATEGORY for comment in comments):  # pragma: no mutate, every category is one of FINDING_CATEGORIES by now, and the other three sort before must-fix-now, so >= gives what == gives
        raise ReviewFileUnusable(
            f"has the verdict 'REQUEST_CHANGES' but no comment whose \"finding_category\" is "
            f"{BLOCKING_CATEGORY}; this program posts REQUEST_CHANGES only for a must-fix-now "
            f"comment, so it refuses the file rather than post it as an approval. Give the "
            f"category {BLOCKING_CATEGORY} to each comment that blocks the merge; if no comment "
            f"blocks it, make the verdict APPROVE")
    return verdict, body, comments, codex_answers


def one_line_text(value):
    return isinstance(value, str) and bool(value.strip()) and len(value.splitlines()) == 1


def codex_answers_check(answers):
    """Raise ReviewFileUnusable when the review file's Codex answers are malformed."""
    grades = answers.get(CODEX_FINDING_GRADES_KEY, [])
    if not isinstance(grades, list):
        raise ReviewFileUnusable(f"has a \"{CODEX_FINDING_GRADES_KEY}\" that is not a list")
    seen = set()
    for entry in grades:
        if not isinstance(entry, dict) or not isinstance(entry.get("finding"), str):
            raise ReviewFileUnusable(f"has a \"{CODEX_FINDING_GRADES_KEY}\" entry with no text \"finding\"")
        finding, grade = entry["finding"], entry.get("grade")
        if finding in seen:
            raise ReviewFileUnusable(f"grades Codex finding {finding} more than once")
        seen.add(finding)
        if grade not in (*FINDING_CATEGORIES, DOES_NOT_HOLD_GRADE):
            raise ReviewFileUnusable(f"gives Codex finding {finding} the grade {grade!r}, not one of "
                                     f"{', '.join((*FINDING_CATEGORIES, DOES_NOT_HOLD_GRADE))}")
        keys = {"finding", "grade", "reason"} if grade == DOES_NOT_HOLD_GRADE else {"finding", "grade"}
        if set(entry) != keys or (grade == DOES_NOT_HOLD_GRADE and not one_line_text(entry["reason"])):
            raise ReviewFileUnusable(
                f"has a grade for Codex finding {finding} that is not exactly \"finding\" and \"grade\", "
                f"with a one-line \"reason\" only for {DOES_NOT_HOLD_GRADE}")


def finding_fact_lines_lacking(text):
    """The hashtags of the lines that end a finding on code which a finding's text lacks or leaves unanswered,
    in FINDING_FACT_LINE_HASHTAGS order; empty when every one is there with an answer."""
    answered = {hashtag or FINDING_FACT_LINE_OLDER_LABELS[label]
                for hashtag, label, answer in FINDING_FACT_LINE.findall(text)
                if FINDING_FACT_LINE_MARKS_AND_SPACE.sub("", answer)}
    return tuple(hashtag for hashtag in FINDING_FACT_LINE_HASHTAGS if hashtag not in answered)


def codex_findings_in_report(report):
    """{finding id: (priority, heading text, [the fact-line hashtags each entry lacks], [each entry's text])} for
    each finding heading of a Codex report; a finding's text runs from its heading line to the next heading.
    Entries with the same priority and heading share an id, so each list holds one item per entry."""
    findings, finding_id, finding_lines = {}, None, []

    def close_finding():
        if finding_id is not None:
            findings[finding_id][2].append(finding_fact_lines_lacking("\n".join(finding_lines)))
            findings[finding_id][3].append("\n".join(finding_lines).strip())
    for line in report.splitlines():
        heading = CODEX_FINDING_HEADING.match(line)
        if heading:
            close_finding()
            text = CODEX_FINDING_WORKTREE_PATH.sub("", heading[2])
            identity = f"{heading[1]}\0{text}".encode("utf-8")
            finding_id = hashlib.sha256(identity).hexdigest()[:12]
            finding_lines = [CODEX_FINDING_WORKTREE_PATH.sub("", line)]
            findings.setdefault(finding_id, (heading[1], text, [], []))
        elif finding_id is not None:
            finding_lines.append(line)
    close_finding()
    return findings


def codex_cell_command(number, base, head, outputs_directory):
    """Return the command that runs the Codex cell on this pull request's head, refusing unless
    pr<number>-head still holds head, so the run reviews the commit being posted for."""
    directory_option = (
        "" if outputs_directory == common.DEFAULT_MERGE_LANE_WORKTREES_AND_OUTPUTS_DIRECTORY
        else f" --merge-lane-worktrees-and-outputs-directory {shlex.quote(str(outputs_directory))}")
    return (f"scripts/merge-lane-code-review-codex-cell-run-on-pull-request-head.py {number} {base} "
            f"--expected-head-commit {head}{directory_option}")


def report_holds_json_object_with_non_empty_findings_list(report):
    """Whether the report holds text such as '"findings": [{', as Codex's review object does whether or not
    it is valid JSON and whatever text wraps it, or a JSON value starting at a "{" that decodes to an object
    whose "findings" is a non-empty list, which also catches a review object whose keys are escaped. A clean
    report that quotes such text is refused too."""
    if CODEX_REVIEW_OBJECT_NON_EMPTY_FINDINGS_LIST_REGEX.search(report):
        return True
    decoder = json.JSONDecoder()
    for start in (index for index, character in enumerate(report) if character == "{"):
        try:
            value, _ = decoder.raw_decode(report, start)
        except ValueError:
            continue
        if isinstance(value, dict) and isinstance(value.get("findings"), list) and value["findings"]:
            return True
    return False


def codex_findings_on_commit(outputs_directory, number, head):
    """Return the findings of the Codex runs recorded for this commit, {} when they found nothing or
    failed, or None when no run record names it; raise CodexRunRecordUnusable when one cannot be read, or
    when a successful run's report is Codex's review object that the Codex cell's converter cannot turn
    into finding lines."""
    findings, recorded = {}, False
    for record_file in sorted((outputs_directory / "cx").glob(
            f"pr{number}-*/{common.CODEX_REVIEW_RUN_RECORD_FILE_NAME}")):
        try:
            record = json.loads(record_file.read_text(encoding="utf-8"))
            record_head, exit_code, report_file = record["head_commit"], record["exit_code"], record["report_file"]
        except (OSError, ValueError, KeyError, TypeError) as error:
            raise CodexRunRecordUnusable(f"the Codex run record {record_file} could not be read: {error!r}")
        if not isinstance(exit_code, int) or isinstance(exit_code, bool) or not isinstance(report_file, str):
            raise CodexRunRecordUnusable(f"the Codex run record {record_file} holds a field of the wrong type")
        if record_head != head:
            continue
        recorded = True
        if exit_code != 0:
            continue
        try:
            report = Path(report_file).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as error:
            raise CodexRunRecordUnusable(
                f"the Codex run record {record_file} says the run succeeded, but its report could not "
                f"be read: {error}")
        def unusable(what):
            base = record.get("base_commit") or "<the commit after base= in the report's first line>"
            return CodexRunRecordUnusable(
                f"review not posted: the Codex report {report_file} {what}.\n"
                f"Do not post the review any other way: the review would carry none of this run's findings.\n"
                f"Run the Codex cell on commit {head} again, from the same base; the new run replaces that "
                f"report, whose text is at the end of this message:\n"
                f"  {codex_cell_command(number, base, head, outputs_directory)}\n"
                f"If that command exits 0, run this posting command again:\n"
                f"  {review_posting_program_rerun_command_line_with_git_author_name()}\n"
                f"Otherwise do what that command prints.\n"
                f"The report's text:\n{report}")
        # A cell older than the conversion wrote Codex's review object as the report.
        review_object_text = codex_cell.codex_review_object_json_text_from_report_or_none_when_prose(
            CODEX_REPORT_PROVENANCE_COMMENT.sub("", report, count=1))
        if review_object_text is not None:
            try:
                report = codex_cell.codex_review_object_as_prose_report(review_object_text)
            except codex_cell.CodexReviewObjectNotConvertible as error:
                raise unusable(
                    f"is Codex's review as a JSON object, which this program cannot turn into finding lines, "
                    f"the \"- [Pn] <title> — <path>:<lines>\" lines it reads findings from: {error}")
        report_findings = codex_findings_in_report(report)
        if not report_findings and report_holds_json_object_with_non_empty_findings_list(report):
            raise unusable(
                "has no finding line, the \"- [Pn] <title> — <path>:<lines>\" lines this program reads "
                "findings from, but holds a JSON \"findings\" list that is not empty: it is likely Codex's "
                "review as a JSON object, written in a form neither the Codex cell nor this program "
                "recognizes, such as with text before its ```json fence")
        # Runs on one commit share ids; each run's entries are kept, so the fact-line count sees them all.
        for finding_id, (priority, text, entries, texts) in report_findings.items():
            kept = findings.setdefault(finding_id, (priority, text, [], []))
            kept[2].extend(entries)
            kept[3].extend(texts)
    return findings if recorded else None


def review_posting_program_rerun_command_line_with_git_author_name():
    """This posting command as it was run, with the GIT_AUTHOR_NAME that names the merge-lane posting
    the review, which a command line copied from sys.argv alone would leave out."""
    merge_lane = os.environ.get("GIT_AUTHOR_NAME")
    prefix = f"GIT_AUTHOR_NAME={shlex.quote(merge_lane)} " if merge_lane else ""
    return prefix + shlex.join(sys.argv)


def review_tier_of_commit(plan_program, number, head):
    """Return (tier, base commit, what the base is) the plan gives this commit's review, the base the one
    its Codex run starts from, or raise CodexRunRecordUnusable with the refusal."""
    def unreadable(reason):
        return CodexRunRecordUnusable(REVIEW_TIER_UNREADABLE.format(head=head, program=plan_program, reason=reason))
    try:
        completed = subprocess.run(
            [sys.executable, str(plan_program), "--pull-request", str(number), "--json",
             "--repository", str(Path(__file__).resolve().parents[1])],
            capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=REVIEW_PLAN_TIMEOUT_SECONDS,
            env=common.run_all_test_suites.environment_without_git_redirecting_variables())
    except (OSError, subprocess.TimeoutExpired) as error:
        raise unreadable(f"it could not be run: {error}")
    if completed.returncode not in REVIEW_PLAN_EXIT_CODES_WITH_A_PLAN:
        raise unreadable(f"it exited {completed.returncode}: {completed.stderr.strip()}")
    try:
        plan = json.loads(completed.stdout)
        plan_head, delta_only = plan["head"], plan["delta_only_review_applies"]
        tier = plan["delta_tier"] if delta_only is True else plan["tier"]
        base, base_reason = ((plan["earlier_reviewed_head"], "the head reviewed before, since a delta-only "
                              "review applies") if delta_only is True else (plan["merge_base"], "the merge base"))
    except (ValueError, KeyError, TypeError) as error:
        raise unreadable(f"its output is not a plan: {error!r}")
    if plan_head != head:
        raise unreadable(f"the pull request's head is now {plan_head}, so review that commit instead")
    if tier != NO_REVIEWER_TIER and tier not in REVIEW_TIERS_THAT_RUN_CODEX:
        raise unreadable(f"it gives the unknown tier {tier!r}")
    return tier, base, base_reason


def body_with_codex_answers(body, comments, answers, findings, plan, number, head, review_file, outputs_directory,
                            recorded=None):
    """Return the body with the Codex grades, and with the findings record rows of the findings in recorded,
    or raise CodexRunRecordUnusable with the whole refusal when an answer is missing or does not fit the run
    records. plan, review_tier_of_commit()'s answer, is None unless findings is None. recorded holds, by
    finding id, the match program's SAME answer for each finding the findings record already holds, which
    needs no grade."""
    recorded = recorded or {}
    grades = {entry["finding"]: entry for entry in answers.get(CODEX_FINDING_GRADES_KEY, [])}
    if findings is None:
        tier, base, base_reason = plan
        if grades and tier == NO_REVIEWER_TIER:
            raise CodexRunRecordUnusable(
                f"review not posted: the review file {review_file} grades Codex findings, but no Codex run "
                f"record names commit {head}, and the review plan gives {tier}, which runs no Codex.\n"
                f"Remove \"{CODEX_FINDING_GRADES_KEY}\" and run the same command again.")
        if tier != NO_REVIEWER_TIER:
            raise CodexRunRecordUnusable(NO_CODEX_RUN_RECORD.format(
                directory=outputs_directory / "cx", head=head, tier=tier, base_reason=base_reason,
                codex_cell_command=codex_cell_command(number, base, head, outputs_directory)))
        return body
    unknown = sorted(set(grades) - set(findings))
    if unknown:
        raise CodexRunRecordUnusable(
            f"review not posted: the review file {review_file} grades {', '.join(unknown)}, which no Codex "
            f"report on commit {head} holds.\nRemove or correct each, then run the same command again.")
    missing = [finding for finding in findings if finding not in grades and finding not in recorded]
    if missing:
        raise CodexRunRecordUnusable(CODEX_FINDINGS_NOT_GRADED.format(
            count=len(missing), head=head, path=review_file,
            findings="\n".join(f"- {finding}: {findings[finding][0]} {findings[finding][1]}" for finding in missing),
            grades=", ".join((*FINDING_CATEGORIES, DOES_NOT_HOLD_GRADE)))
            + findings_record_rows_already_holding_lines(recorded, "\nThese Codex findings need no grade, since "
                                                                  "the findings record already holds each:"))
    if not findings:
        return body
    graded = [finding for finding in findings if finding in grades]
    uncommented = [finding for finding in graded if grades[finding]["grade"] in FINDING_CATEGORIES
                   and not any(comment["finding_category"] == grades[finding]["grade"]
                               and finding in CODEX_FINDING_ID_MARK_IN_REVIEW_COMMENT_PATTERN.findall(comment["body"])
                               for comment in comments)]
    if uncommented:
        raise CodexRunRecordUnusable(CODEX_GRADE_WITH_NO_COMMENT.format(
            path=review_file, count=len(uncommented),
            findings="\n".join(f"- {finding}: {grades[finding]['grade']}: {findings[finding][1]}"
                               for finding in uncommented)))
    lines = [f"- {finding} ({findings[finding][0]}): {grades[finding]['grade']}"
             + (f", {grades[finding]['reason']}" if "reason" in grades[finding] else "")
             + f": {findings[finding][1]}" for finding in graded]
    if lines:
        body = "\n".join((f"{body}\n\n{CODEX_GRADES_BODY_HEADING}", *lines))
    return body + findings_record_rows_already_holding_lines(recorded, f"\n\n{FINDINGS_RECORD_BODY_HEADING}")


def findings_record_rows_already_holding_lines(recorded, heading):
    """The heading and one line per Codex finding the findings record already holds, quoting its row's state,
    grade and decision; empty when it holds none of them."""
    if not recorded:
        return ""
    lines = []
    for finding, answer in recorded.items():
        row = answer["record"]
        lines.append(f"- {finding}: the same defect as findings record row {row['record_id']}, state {row['state']}, "
                     f"grade {row['grade']}" + (f", decision: {row['decision']}" if row["decision"] else "")
                     + ("; a possible regression, since the row is fixed" if answer["possible_regression"] else ""))
    return "\n".join((heading, *lines))


def findings_record_summary(matched, added):
    """The success line's account of the findings record match and add, empty when no finding was matched."""
    if not matched:
        return ""
    same = [finding for finding, answer in matched.items() if answer["answer"] == "SAME"]
    notes = [f"possible regression: {finding} matches fixed row {answer['record']['record_id']}"
             for finding, answer in matched.items() if answer["answer"] == "SAME" and answer["possible_regression"]]
    notes += [f"possible miss: {finding} cites the same line as row(s) "
              f"{', '.join(map(str, answer['possible_miss_of']))}, logged for review"
              for finding, answer in added.items() if answer["possible_miss_of"]]
    rows = ", ".join(f"{finding} as row {answer['record_id']}" for finding, answer in added.items())
    return (f"; findings record: {len(same)} already held, {len(added)} added" + (f" ({rows})" if rows else "")
            + "".join(f"; {note}" for note in notes))


def codex_finding_fact_line_answers(texts, hashtag_wanted):
    """Every answer the entries of a Codex finding give its hashtag_wanted line, or the older label's, lowercased with
    marks and spaces removed, so that "not checked" reads as "notchecked", never as "no"."""
    return [FINDING_FACT_LINE_MARKS_AND_SPACE.sub("", answer).lower()
            for text in texts for hashtag, label, answer in FINDING_FACT_LINE.findall(text)
            if (hashtag or FINDING_FACT_LINE_OLDER_LABELS[label]) == hashtag_wanted]


def codex_finding_says_main_has_it(texts):
    """Whether any entry of a Codex finding answers its `#defect_already_on_main` line yes."""
    return "yes" in codex_finding_fact_line_answers(texts, "#defect_already_on_main")


def findings_record_rows_needing_no_grade(matched, findings):
    """The SAME answers, by finding id, of the matched findings that need no grade: those whose every entry answers
    `#pull_request_triggers_the_defect` no. One that answers yes, not checked, or yes in one entry and no in another
    is still graded, since this pull request may bring the defect back, and the earlier row's grade is for main."""
    def every_entry_answers_no(texts):
        answers = codex_finding_fact_line_answers(texts, "#pull_request_triggers_the_defect")
        return bool(answers) and all(answer == "no" for answer in answers)
    return {finding: answer for finding, answer in matched.items() if answer["answer"] == "SAME"
            and every_entry_answers_no(findings[finding][3])}


def findings_record_program_answers(program, subcommand, number, head, request, answer_is_readable):
    """Run the findings record program's subcommand on the request; return its answer by finding id, or raise
    CodexRunRecordUnusable when it exits nonzero or answers other than answer_is_readable accepts for each
    finding sent."""
    completed = subprocess.run(
        [sys.executable, str(program), subcommand, "--pull-request", str(number), "--head-commit", head],
        input=json.dumps(request), capture_output=True, text=True)
    if completed.returncode != 0:
        raise CodexRunRecordUnusable(
            f"the findings record program {program} {subcommand} exited {completed.returncode}, so the review cannot "
            f"say which Codex findings the findings record holds; it printed:\n{completed.stderr.strip()}")
    try:
        answers = json.loads(completed.stdout)
        if set(answers) != {entry["finding_id"] for entry in request} or not all(
                answer_is_readable(answer) for answer in answers.values()):
            raise ValueError("it does not give a readable answer for exactly the findings sent")
    except (ValueError, TypeError, KeyError) as error:
        raise CodexRunRecordUnusable(f"the findings record program {program} {subcommand} printed an answer this "
                                     f"program cannot read ({error}): {completed.stdout.strip()[:300]}")
    return answers


def findings_record_match(program, number, head, findings):
    """The findings record program's match answer for each Codex finding that says main has it, by finding id."""
    request = [{"finding_id": finding, "priority": priority, "heading": heading, "text": texts[0]}
               for finding, (priority, heading, _, texts) in findings.items() if codex_finding_says_main_has_it(texts)]
    if not request:
        return {}
    return findings_record_program_answers(
        program, "match", number, head, request,
        lambda answer: answer["answer"] == "NEW" and "record_id" in answer
        or answer["answer"] == "SAME" and isinstance(answer["possible_regression"], bool)
        and {"record_id", "state", "grade", "decision"} <= set(answer["record"]))


def findings_record_add(program, number, head, findings, matched, answers):
    """Add each matched NEW Codex finding, with its accepted grade, to the findings record; return the program's
    add answer by finding id."""
    grades = {entry["finding"]: entry for entry in answers.get(CODEX_FINDING_GRADES_KEY, [])}
    request = [{"finding_id": finding, "priority": findings[finding][0], "heading": findings[finding][1],
                "text": findings[finding][3][0], "grade": grades[finding]["grade"],
                **({"reason": grades[finding]["reason"]} if "reason" in grades[finding] else {})}
               for finding, answer in matched.items() if answer["answer"] == "NEW"]
    if not request:
        return {}
    return findings_record_program_answers(
        program, "add", number, head, request,
        lambda answer: isinstance(answer["record_id"], int) and isinstance(answer["possible_miss_of"], list))


def review_comment_opening_mark_for_finding_category(category, nit=False):
    """The mark a comment of this finding_category opens with when posted, the nit mark for a nit."""
    if nit:
        return fix_round.NIT_MARK
    if category == BLOCKING_CATEGORY:  # pragma: no mutate, every caller passes one of FINDING_CATEGORIES, and the other three sort before must-fix-now, so >= gives what == gives
        return BLOCKING_MARK
    return NON_BLOCKING_CATEGORY_MARK_FORMAT.format(category=category)


def finding_category_and_text_read_from_review_comment_opening_mark(body):
    """(finding_category, text, nit) of a posted merge-lane-2 comment, read by the mark it opens with,
    nit True only for the nit mark, which reads as NIT_CATEGORY; or None when it opens with none.
    A blocking mark is read as the fix-round program reads it."""
    stripped = body.lstrip()
    blocking = fix_round.BLOCKING_MARKER_PATTERN.match(stripped)
    if blocking:
        return BLOCKING_CATEGORY, stripped[blocking.end():].strip(), False
    if stripped.startswith(fix_round.NIT_MARK):
        return NIT_CATEGORY, stripped[len(fix_round.NIT_MARK):].strip(), True
    for category in FINDING_CATEGORIES:
        mark = review_comment_opening_mark_for_finding_category(category)
        if category != BLOCKING_CATEGORY and stripped.startswith(mark):
            return category, stripped[len(mark):].strip(), False
    return None


outside_the_diff_comments_read_back_from_review_body = fix_round.outside_the_diff_comments_read_back_from_review_body


def outside_the_diff_line(comment):
    """A moved comment as written into the body: each line after its first indented, so no line of
    its text can start another comment when outside_the_diff_comments_read_back_from_review_body()
    reads it back."""
    first, *rest = comment["body"].split("\n")
    return "\n".join([OUTSIDE_THE_DIFF_LINE_FORMAT.format(path=comment["path"], line=comment["line"], body=first),
                      *(OUTSIDE_THE_DIFF_CONTINUATION_INDENT + line for line in rest)])


def with_finding_category_marks(body, comments, merge_lane):
    """Return (verdict, body, comments) as posted for categorized comments: each opened with its
    category's mark, or the nit mark for a nit, no finding_category or nit key left, a comment repeating an earlier one's path, line
    and posted body dropped, as the fix-round program counts it once, and the verdict, the body's
    count and its merge-lane name line set by the must-fix-now ones left."""
    comments = fix_round.without_reposts([
        {"path": comment["path"], "line": comment["line"],
         "body": review_comment_opening_mark_for_finding_category(comment["finding_category"], comment.get("nit", False))
         + comment["body"]}
        for comment in comments])
    count = len(fix_round.marked(comments))
    verdict = "REQUEST_CHANGES" if count else "APPROVE"
    if count:
        body = (BLOCKING_COUNT_FORMAT.format(count=count) + "\n\n"
                + fix_round.REVIEW_BODY_POSTED_BY_MERGE_LANE_LINE_FORMAT.format(merge_lane=merge_lane) + "\n\n" + body)
    return verdict, body, comments


def posted_verdict_review_missing_review_posting_program_marks_reason_or_none(review, comments):
    """Why a verdict review GitHub holds, a dict with "state" and "body", lacks the marks this program
    writes into a review it posts as ned-review-merge, or None when it has them; comments are the
    review's inline comments as GitHub returns them. Any state but APPROVED and CHANGES_REQUESTED has
    no verdict to mark, and returns None."""
    body = review.get("body") or ""
    if review.get("state") == "APPROVED":
        if body.split("\n", 1)[0] != "APPROVE":
            return "its body does not open with the line APPROVE"
        return None
    if review.get("state") != "CHANGES_REQUESTED":
        return None
    count = fix_round.BLOCKING_COUNT_PATTERN.match(body)
    if not count:
        return ("its body does not open with the line REQUEST_CHANGES, a blank line and the line "
                + BLOCKING_COUNT_FORMAT.format(count="N"))
    stated = int(count.group(1))
    found = len(fix_round.marked(comments)) + len(
        fix_round.marked(outside_the_diff_comments_read_back_from_review_body(body)))
    if found != stated:
        return (f"its body states {BLOCKING_COUNT_FORMAT.format(count=stated)}, but {found} of its comments "
                f"open with {BLOCKING_MARK.strip()}")
    return None


def commentable_lines(files):
    """Map each path to the new-side line numbers its diff shows, from GitHub's pull request files."""
    lines = {}
    for entry in files:
        shown = lines.setdefault(entry["filename"], set())
        line = None
        for patch_line in (entry.get("patch") or "").split("\n"):
            header = HUNK_HEADER.match(patch_line)
            if header:
                line = int(header.group(1))
            elif line is not None and patch_line[:1] in ("+", " "):
                shown.add(line)
                line += 1
    return lines


def with_outside_comments_in_body(body, comments, lines):
    """Return (body, comments) with every comment GitHub would refuse moved into the body."""
    inside = [comment for comment in comments if comment["line"] in lines.get(comment["path"], ())]
    outside = [comment for comment in comments if comment not in inside]
    if outside:
        body = (body.rstrip("\n") + "\n\n" + OUTSIDE_THE_DIFF_HEADING + "\n"
                + "\n".join(outside_the_diff_line(comment) for comment in outside))
    return body, inside


def read_token(account):
    """Return the account's token, or raise GhFailed naming why it cannot be used."""
    if account == MERGE_LANE_ACCOUNT:  # pragma: no mutate, --github-account allows only mac-claude and ned-review-merge, and mac-claude sorts before ned-review-merge, so >= gives what == gives
        try:
            return common.read_merge_account_token()
        except common.MergeAccountTokenUnusable as error:
            raise GhFailed(str(error))
    token_file = Path.home() / ".config" / "nedsnodes" / "mac-claude.token"
    try:
        token = token_file.read_text(encoding="utf-8").strip()
    except (OSError, UnicodeDecodeError) as error:
        raise GhFailed(f"could not read mac-claude's token at {token_file}: {error}")
    # An empty GH_TOKEN makes gh fall back to its stored account, which is not mac-claude.
    if not token:
        raise GhFailed(f"mac-claude's token file {token_file} is empty")
    return token


def reason_of(error):
    if isinstance(error, GhFailed):
        return str(error)
    return f"GitHub's reply was not in the expected shape: {type(error).__name__}: {error}"


def new_activity_count_after_reviewed_since_bound(number):
    """What scripts/merge-gate.sh counts as posted or edited on the pull request after the latest
    reviewed-since it accepts, or raise GhFailed naming why the gate could not count it."""
    completed = subprocess.run(["bash", str(MERGE_GATE), NEW_ACTIVITY_COUNT_OPTION, str(number)],
                               capture_output=True, text=True, stdin=subprocess.DEVNULL)
    if completed.returncode != 0 or not completed.stdout.strip().isdigit():
        raise GhFailed(f"{MERGE_GATE} {NEW_ACTIVITY_COUNT_OPTION} {number} exited {completed.returncode}, "
                       f"printing {completed.stdout.strip()!r} and on standard error: {completed.stderr.strip()}")
    return int(completed.stdout)


def gh_json(token, arguments, input_text=None):
    completed = subprocess.run(
        ["gh", "api", *arguments], input=input_text, capture_output=True, text=True,
        env={**os.environ, "GH_TOKEN": token},
        stdin=None if input_text is not None else subprocess.DEVNULL)
    if completed.returncode != 0:
        raise GhFailed(f"gh exited {completed.returncode}: {completed.stderr.strip()}")
    try:
        return json.loads(completed.stdout)
    except ValueError as error:
        raise GhFailed(f"gh printed no JSON: {error}")


def parse_arguments(argv):
    parser = argparse.ArgumentParser(
        description="Post a pull request review, the Claude reviewer's as mac-claude or "
                    "merge-lane-2's as ned-review-merge, then read it back. Exits 0 if the review was posted and read back as "
                    "expected, 2 otherwise.")
    parser.add_argument("--pull-request", type=int, required=True,
                        help="the pull request's number")
    parser.add_argument("--head-commit", required=True,
                        help="the full hash of the nn-head-commit the review is on")
    parser.add_argument("--github-account", choices=(MAC_CLAUDE_ACCOUNT, MERGE_LANE_ACCOUNT),
                        default=MAC_CLAUDE_ACCOUNT,
                        help="the GitHub account the review is posted as, which also sets the "
                             "review file's format (default: mac-claude)")
    parser.add_argument("--merge-lane-worktrees-and-outputs-directory", type=Path,
                        default=common.DEFAULT_MERGE_LANE_WORKTREES_AND_OUTPUTS_DIRECTORY,
                        help="holds cx/, the Codex run records (default: "
                             f"{common.DEFAULT_MERGE_LANE_WORKTREES_AND_OUTPUTS_DIRECTORY})")
    parser.add_argument("--pull-request-review-plan-program", type=Path, default=REVIEW_PLAN_PROGRAM,
                        help="the program that gives the review tier when no Codex run record names the "
                             "commit (default: this checkout's pull-request-review-plan.py)")
    parser.add_argument("--findings-record-codex-finding-match-program", type=Path, default=FINDINGS_RECORD_CODEX_FINDING_MATCH_PROGRAM,
                        help="the program that matches each Codex finding on main's code against the findings "
                             "record (default: this checkout's "
                             "findings-record-codex-finding-match-and-row-add-or-decide.py)")
    parser.add_argument("review_file", type=Path,
                        help="the review: a JSON object with verdict, body and comments")
    return parser.parse_args(argv)


def exit_on_sigterm(signal_number, frame):
    raise SystemExit(128 + signal_number)


def main(argv=None):
    # SIGTERM must raise, as an interrupt does, so the post and the read-back can report
    # what they leave on GitHub.
    signal.signal(signal.SIGTERM, exit_on_sigterm)
    arguments = parse_arguments(argv)
    number, head, account = arguments.pull_request, arguments.head_commit, arguments.github_account
    try:
        verdict, body, comments, codex_answers = read_review_file(arguments.review_file, account)
    except ReviewFileUnusable as error:
        # merge-lane-2 writes its own file, so no reviewer's run is to blame and it can fix the file.
        print(NOT_POSTED.format(reason=f"the review file {arguments.review_file} {error}")
              if account == MERGE_LANE_ACCOUNT  # pragma: no mutate, --github-account allows only mac-claude and ned-review-merge, and mac-claude sorts before ned-review-merge, so >= gives what == gives
              else REVIEW_FILE_UNUSABLE.format(path=arguments.review_file, reason=error),
              file=sys.stderr)
        return EXIT_NOT_POSTED
    # The reviewer's findings are its comments, or for merge-lane-2's verdict review, Codex's findings.
    fact_line_lacks = [(f"{comment['path']}:{comment['line']}", finding_fact_lines_lacking(comment["body"]))
                       for comment in comments]
    matched, added = {}, {}
    if verdict is not None and account == MERGE_LANE_ACCOUNT:  # pragma: no mutate, --github-account allows only mac-claude and ned-review-merge, and mac-claude sorts before ned-review-merge, so >= gives what == gives
        outputs_directory = arguments.merge_lane_worktrees_and_outputs_directory
        try:
            findings = codex_findings_on_commit(outputs_directory, number, head)
            fact_line_lacks = [(finding_id, lacking) for finding_id, finding in (findings or {}).items()
                               for lacking in finding[2]]
            plan = (review_tier_of_commit(arguments.pull_request_review_plan_program, number, head)
                    if findings is None else None)
            program = arguments.findings_record_codex_finding_match_program
            matched = findings_record_match(program, number, head, findings) if findings else {}
            body = body_with_codex_answers(
                body, comments, codex_answers, findings, plan, number, head, arguments.review_file,
                outputs_directory, findings_record_rows_needing_no_grade(matched, findings))
            # Added only once the grades are accepted, since a row keeps the grade it was added with.
            added = findings_record_add(program, number, head, findings, matched, codex_answers)
        except CodexRunRecordUnusable as error:
            refusal = str(error)
            print(refusal if refusal.startswith("review not posted:") else NOT_POSTED.format(reason=refusal),
                  file=sys.stderr)
            return EXIT_NOT_POSTED
    try:
        token = read_token(account)
    except GhFailed as error:
        print(NOT_POSTED.format(reason=error), file=sys.stderr)
        return EXIT_NOT_POSTED
    try:
        author = gh_json(token, [f"repos/{REPOSITORY}/pulls/{number}"])["user"]["login"]
    except (GhFailed, KeyError, TypeError) as error:
        print(NOT_POSTED.format(reason=f"reading the pull request's author failed: {reason_of(error)}"),
              file=sys.stderr)
        return EXIT_NOT_POSTED
    try:
        pages = gh_json(token, ["--paginate", "--slurp",
                                f"repos/{REPOSITORY}/pulls/{number}/files?per_page=100"])
        lines = commentable_lines(entry for page in pages for entry in page)
    except (GhFailed, KeyError, TypeError, AttributeError) as error:
        print(NOT_POSTED.format(reason=f"reading the pull request's diff failed: {reason_of(error)}"),
              file=sys.stderr)
        return EXIT_NOT_POSTED
    if verdict is None:
        try:
            new_activity = new_activity_count_after_reviewed_since_bound(number)
        except GhFailed as error:
            print(NOT_POSTED.format(reason=f"counting the pull request's activity failed: {error}"),
                  file=sys.stderr)
            return EXIT_NOT_POSTED
        if not new_activity:
            print(NO_NEW_ACTIVITY.format(path=arguments.review_file, number=number, account=account),
                  file=sys.stderr)
            return EXIT_NOT_POSTED
    elif account == MERGE_LANE_ACCOUNT:  # pragma: no mutate, --github-account allows only mac-claude and ned-review-merge, and mac-claude sorts before ned-review-merge, so >= gives what == gives
        merge_lane = os.environ.get("GIT_AUTHOR_NAME", "")
        verdict, body, comments = with_finding_category_marks(body, comments, merge_lane)
        if verdict == "REQUEST_CHANGES" and not fix_round.REVIEW_BODY_POSTED_BY_MERGE_LANE_LINE_PATTERN.match(f"{verdict}\n\n{body}"):
            print(NOT_A_MERGE_LANE.format(name=merge_lane), file=sys.stderr)
            return EXIT_NOT_POSTED
    body, inline_comments = with_outside_comments_in_body(body, comments, lines)
    moved_count = len(comments) - len(inline_comments)
    comments = inline_comments
    # GitHub refuses an approving or changes-requesting review from the pull request's author.
    if verdict is None:
        event = "COMMENT"
    elif account == MERGE_LANE_ACCOUNT:  # pragma: no mutate, --github-account allows only mac-claude and ned-review-merge, and mac-claude sorts before ned-review-merge, so >= gives what == gives
        event = "COMMENT" if author == MERGE_LANE_ACCOUNT else verdict
    else:
        event = verdict if author == MERGE_LANE_ACCOUNT else "COMMENT"
    review_id = None
    try:
        try:
            posted = gh_json(token, ["-X", "POST", f"repos/{REPOSITORY}/pulls/{number}/reviews",
                                     "--input", "-"],
                             input_text=json.dumps({"commit_id": head, "event": event,
                                                    "body": f"{verdict}\n\n{body}" if verdict else body,
                                                    "comments": comments}))
            review_id = posted["id"]
        except (GhFailed, KeyError, TypeError) as error:
            print(POST_FAILED.format(reason=reason_of(error), number=number, head=head,
                                     repository=REPOSITORY, account=account),
                  file=sys.stderr)
            return EXIT_NOT_POSTED
        try:
            copy = gh_json(token, [f"repos/{REPOSITORY}/pulls/{number}/reviews/{review_id}"])
            differences = [f"{field} is {copy.get(field)!r}, not {wanted!r}"
                           for field, wanted in (("state", EVENT_STATES[event]),
                                                 ("commit_id", head))
                           if copy.get(field) != wanted]
        except (GhFailed, AttributeError) as error:
            print(READ_BACK_FAILED.format(review_id=review_id, reason=reason_of(error),
                                          number=number),
                  file=sys.stderr)
            return EXIT_NOT_POSTED
        if differences:
            print(READ_BACK_DIFFERS.format(review_id=review_id,
                                           differences="; ".join(differences), number=number,
                                           repository=REPOSITORY),
                  file=sys.stderr)
            return EXIT_NOT_POSTED
        moved = f"; {moved_count} comment(s) moved into the body" if moved_count else ""
        lacks = [f"{name} lacks {', '.join(repr(hashtag) for hashtag in hashtags)}"
                 for name, hashtags in fact_line_lacks if hashtags]
        lacking = (f"; {len(lacks)} of {len(fact_line_lacks)} "
                   f"{'Codex ' if account == MERGE_LANE_ACCOUNT else ''}finding(s) lack an answered fact line"
                   f"{': ' + ' | '.join(lacks) if lacks else ''}" if fact_line_lacks and verdict else "")
        print(f"review {review_id} posted on pull request {number} by {account} as {event}, "
              f"{f'verdict {verdict}' if verdict else 'no verdict'}, on commit {head}; GitHub's copy reads back as {EVENT_STATES[event]}"
              f"{lacking}{moved}{findings_record_summary(matched, added)}")
        return EXIT_POSTED
    except (KeyboardInterrupt, SystemExit):
        # gh_json's subprocess.run has killed gh before this runs, so nothing more is sent.
        reason = "this command was interrupted"
        if review_id is None:
            print(POST_FAILED.format(reason=reason, number=number, head=head,
                                     repository=REPOSITORY, account=account),
                  file=sys.stderr)
        else:
            print(READ_BACK_FAILED.format(review_id=review_id, reason=reason, number=number),
                  file=sys.stderr)
        return EXIT_NOT_POSTED


if __name__ == "__main__":
    sys.exit(main())
