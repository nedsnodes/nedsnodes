---
issue: "[Findings record in the shared database, so a decided reviewer finding is not raised and graded again](https://github.com/nedsnodes/nedsnodes/issues/4821)"
kind: design
---

# Findings record in the shared database, so a decided reviewer finding is not raised and graded again

## Why

Reviewers, Codex most of all, raise the same defect on main again and again, in other words, on pull requests that do not cause it. Each time, a merge lane grades it from scratch, routes it again, and sometimes decides it differently. One defect at `agent-seat-terminal-captures-older-than-seven-days-delete.py:83` was found in the Codex review of [PR 3957](https://github.com/nedsnodes/nedsnodes/pull/3957). It was raised again in [PR 4034](https://github.com/nedsnodes/nedsnodes/pull/4034), [PR 4076](https://github.com/nedsnodes/nedsnodes/pull/4076) and [PR 4019](https://github.com/nedsnodes/nedsnodes/pull/4019). A record of every finding on main, with its decision, lets a merge lane see that a new finding was already decided and quote that decision instead of grading it again.

## What is decided

The user approved this design on 2026-11-25, answering A to item 23.2 of approval-walk merge-lane-2-review-lanes-and-merge-batch-auto-start-approval-walk-2026-11-24. The walk-minutes are at `nedlern@ned-box:/home/nedlern/nedsnodes-logs/walk/merge-lane-2-review-lanes-and-merge-batch-auto-start-approval-walk-2026-11-24-minutes.md`. Items 20 and 22 of the same approval-walk approved keeping the record at all and weighing an existing open-source database first. The full design, with the rulings it rests on and the measurements below, is `nedlern@ned-box:/home/nedlern/nedsnodes-logs/seats/merge-lane-2/findings-record-and-search-design-2026-11-25.md`.

- **Where:** new tables in the shared database (nn-shared-database), behind its existing HTTP service on ned-box (`nn-systems/nn-shared-database/nn-shared-database-service.py`), so they are covered by the nightly backup that already runs. Not a new SQLite file, and not a second service.
- **One row per defect.** A row holds:
  - the file path, the line, and that line's text at a recorded commit, or else an outside program's name and version;
  - a one-line statement of the defect, and the ids of the findings it came from;
  - the four labelled lines reviewers end a code finding with: `Main has it:`, `This pull request makes it happen:`, `Reports success on failure:` and `Shown by:`;
  - its grade, where it was filed, and the owning agent-seat;
  - its state: `new`, `filed`, `decided-fix`, `decided-not-worth-fixing`, `needs-user` or `fixed`;
  - the decision, with a link or a reason, and each later sighting.

  Rows are never deleted: the service offers no delete operation.
- **Matching a new finding is retrieval-augmented generation.** SQLite's built-in full-text search, FTS5, ranked with `bm25()`, searches on all of the new finding's words. Code passes the best three rows to one judgment step. That step answers exactly `SAME <row id>` or `NEW`, and code refuses any other answer, including a row id it did not pass. On `SAME`, the posting program, `scripts/merge-lane-pull-request-reviewer-review-post-and-read-back.py`, copies that row's decision, or its open state, into the posted review, and records the sighting on the row. A `SAME` match to a `fixed` row is reported as a possible regression.
- **Detecting misses.** When a `NEW` finding cites the same file and the same line text as an existing row, code logs it as a possible miss.
- **Regression test.** The seven real repeat pairs listed in the design become a committed test, with rewordings in a Claude reviewer's style added.
- **Search by meaning later, not now.** sqlite-vec, an open-source library for search by meaning, is added in the same database only after a logged possible miss is shown to be real.

The design file settles the rest, such as each state change and what to do with a refused answer; the builder settles what it leaves open.

Measured for the design: FTS5 ranked the earlier finding first in all seven real repeats, among about 1,500 earlier findings, two of them on lines that had moved. At most about 60 findings arrive a day, under 20,000 rows a year, and FTS5 ranks 20,000 rows in 47 ms on ned-box.

Not in this GHI: code that grades a finding from its `Reports success on failure:` line, and moving the merge lanes' grading rules into one committed file. Both come to the user as approval-walk items of their own.

## Related

- GHI [972](https://github.com/nedsnodes/nedsnodes/issues/972): the SQLite HTTP service this builds on.
- GHI [2505](https://github.com/nedsnodes/nedsnodes/issues/2505): one store for pull requests, reviews and approval-walks, whose tables sit beside these.
- GHI [2118](https://github.com/nedsnodes/nedsnodes/issues/2118): the user-rulings store, where the user approved sqlite-vec for search by meaning.
- GHI [1058](https://github.com/nedsnodes/nedsnodes/issues/1058): the maintenance list, one of the places a finding can be filed.

## Next action

fleet-restart-at-login, which designed the shared database service, builds:
- the tables;
- the service's named operations for adding a row, matching a finding and recording a decision;
- the match program, including its judgment step and its miss log;
- the regression test.

The merge lanes' posting program then calls the match program before grading. Once the record exists, a one-off script loads merge-lane-2's sorted backlog of Codex findings on main into it, sending each entry through the match program so that repeats within the backlog join one row: `nedlern@ned-box:/home/nedlern/nedsnodes-logs/seats/merge-lane-2/ungraded-codex-findings-backlog-sorted-2026-11-25.md`.
