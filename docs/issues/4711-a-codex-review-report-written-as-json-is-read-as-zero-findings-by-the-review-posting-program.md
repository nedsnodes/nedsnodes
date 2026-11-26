---
issue: "[A Codex review report written as JSON is read as zero findings by the review-posting program](https://github.com/nedsnodes/nedsnodes/issues/4711)"
---

# A Codex review report written as JSON is read as zero findings by the review-posting program

## Reproduction

On 2026-11-25 the Codex review cell, `scripts/code-review-codex-cell.py`, reviewed [PR 4700](https://github.com/nedsnodes/nedsnodes/pull/4700) at base ede402d3ea62 and exited 0. Its report, `nedlern@ned-box:/home/nedlern/nedsnodes-logs/seats/merge-lane-2/merge-helpers/cx/pr4700-ede402d3/codex-code-review-report.md`, holds a JSON object after its provenance comment, `{"findings": [{"title": "[P2] Keep waiting for the worker when the status query fails", "body": ...}, ...]}`, with 3 findings. Other recent reports, such as `nedlern@ned-box:/home/nedlern/nedsnodes-logs/seats/merge-lane-2/merge-helpers/cx/pr4704-dcc6f3b5/codex-code-review-report.md`, are prose followed by one `- [Codex priority P2 ...]` line per finding.

Loading `scripts/merge-lane-pull-request-reviewer-review-post-and-read-back.py` from main as a module and calling `codex_findings_in_report` on each report's text returns 0 findings for the [PR 4700](https://github.com/nedsnodes/nedsnodes/pull/4700) report and 3 for the [PR 4704](https://github.com/nedsnodes/nedsnodes/pull/4704) report. `json.loads` on the [PR 4700](https://github.com/nedsnodes/nedsnodes/pull/4700) report's text after its `-->` gives a `findings` list of 3.

So on [PR 4700](https://github.com/nedsnodes/nedsnodes/pull/4700) the posting program asked merge-lane-1 for no grades and no Codex finding ids, and would have posted the review with Codex's three findings dropped and no message saying so. merge-lane-1 noticed the report's form and cited the three findings in its review by title.

## Why it matters

`codex_findings_in_report` reads only lines that match `CODEX_FINDING_HEADING`, so a report in any other form counts as a report with no findings. `codex_findings_on_commit` then treats that Codex review as one with no findings, and the posting program lets a verdict through with no grades for findings it never saw. A report with no findings has no fixed form to check against: of the 2625 reports under `nedlern@ned-box:/home/nedlern/nedsnodes-logs/seats/merge-lane-2/merge-helpers/cx/` on 2026-11-25, 1510 have no finding line and are free prose, such as "No actionable defects found in the changes relative to the specified base." The JSON form is not new: 8 of the 2625 reports are JSON, a line starting with `{` after the provenance comment, the earliest for pull request 4076, so earlier pull requests may have merged with Codex findings that no reviewer graded and no author was told about (unverified for each of the 8).

## What to do

1. Fix the cause where the report is written. `scripts/code-review-codex-cell.py` already rewrites each finding line of Codex's output when it writes the report; when Codex's output after the provenance comment is a JSON object with a `findings` list, the cell writes one finding line per entry in the form `CODEX_FINDING_HEADING` reads, `- [Codex priority P<n> (P0 highest)] <title without its [P<n>] prefix> — <code_location.absolute_file_path>:<line_range.start>-<line_range.end>`, taking `<n>` from the entry's integer `priority`, so a finding gets the same id in either form. When the JSON cannot be turned into finding lines, such as an entry with no `priority` or no `title`, the cell exits nonzero and names the report file. An empty `findings` list is a report with no findings.
2. Make the posting program refuse, with a message naming the file, a report whose text after its provenance comment starts with `{`, so a JSON report the cell did not convert can never be read as zero findings.
3. Add a test for each of steps 1 and 2 that fails on main, using the PR 4700 report as the JSON case.
4. Check the other 7 JSON reports, in the directories `pr4076-5c7d201f`, `pr4128-aa93ac53`, `pr4174-f7f13a6f`, `pr4227-6493a3ec`, `pr4414-e8a6c576`, `pr4560-09cbd782` and `pr4631-0d355d1c` under that `cx/` directory, for findings no reviewer graded, and send any found to the merge lane that reviewed that pull request.

The nearest designs are [GHI 2505](https://github.com/nedsnodes/nedsnodes/issues/2505), which plans one schema and one store for review state, and [GHI 3891](https://github.com/nedsnodes/nedsnodes/issues/3891), which plans to post every merge-lane review through one program.
