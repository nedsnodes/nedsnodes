---
issue: "[The walk-me-through waiting-item read step offers the handoff row again after an unclosed `check --already-decided`, so a rerun records the answer twice](https://github.com/nedsnodes/nedsnodes/issues/4647)"
---

# The walk-me-through waiting-item read step offers the handoff row again after an unclosed `check --already-decided`, so a rerun records the answer twice

## Outcome

Done, before this GHI-MD merged. PR [Walk check --already-decided records a disapproval, and no item is settled twice](https://github.com/nedsnodes/nedsnodes/pull/4961) merged to main at 2026-11-26T09:34:04Z as merge commit `31eef15b4`; its commit `9763b0210` removed `settling_left_unclosed`, so the function and the line numbers this file names below no longer describe main. In its place, `unclosed_last_answer` in `nn-systems/skills/walk-me-through/walk-me-through-answer-added-texts-cold-read-fast-read-check-and-close.py` returns the walk-minutes' last answer line whenever no close line follows it, whatever the answer's form and whichever item it names. `no_answer_rows_for_waiting_item_lines` offers no row while it returns one, and `check` refuses every `--not-asked`, `--already-decided` and `--now-over-later-already-decided` then, which covers both places the next action below names.

On main at `60ad213e5` the reproduction below prints `NOT REPRODUCED (handoff row offered again: False; answer lines for item 1: 1)`; with the program put back to its version at `9802b30ef` it prints `DEFECT REPRODUCED (handoff row offered again: True; answer lines for item 1: 2)`. The tests are already in the suite `nn-systems/skills/walk-me-through/tests/walk-me-through-answer-added-texts-cold-read-fast-read-check-and-close-test.py`: `test_the_read_step_presents_an_item_rated_none_that_is_shown_all_the_same` checks that the read step offers no no-answer row after an unclosed `check --already-decided`, and `test_check_refuses_a_second_settling_of_an_item_whose_settling_has_no_close_and_takes_his_own_answer` checks that a second settling is refused, writing nothing. With the read-step guard removed from `no_answer_rows_for_waiting_item_lines`, the first of these and four other cases fail. An unclosed `--moved-on` answer also blocks every settling, but a second `--moved-on` is not refused, since `--moved-on` is not one of `SETTLING_FLAGS`; that is outside this defect. The GHI is closed as completed.

## Reproduction

Run this from the repository root on main at 9802b30ef. It builds its walk in the test suite's own temporary directory and removes it afterwards; it touches no real walk-minutes and no log-store.

```bash
python3 - nn-systems/skills/walk-me-through/tests/walk-me-through-answer-added-texts-cold-read-fast-read-check-and-close-test.py <<'EOF'
import importlib.util, re, shlex, shutil, subprocess, sys
spec = importlib.util.spec_from_file_location("t", sys.argv[1]); t = importlib.util.module_from_spec(spec); spec.loader.exec_module(t)
try:
    document = t.RATED_NONE_DOCUMENT.replace("print the poem count after the list", "shorten the session-handoff file's opening").replace(
        "#case_against none.\n\nRecommendation: print it.", f"#case_against {t.WEAK_COST_ONLY}\n\nRecommendation: print it.", 1)
    case = t.Case(next_to_present="item 1 of 3", document=document)
    def handoff_rows():
        return [row for row in t.no_answer_rows_printed(case.run(t.WAITING_ITEM_READ)) if row.startswith("- the handoff's own internals:")]
    assert "session-handoff" in document and t.WEAK_COST_ONLY in document, "the test module's fixture text changed"
    rows = handoff_rows()
    assert rows, "the first read offers no handoff row"
    command = shlex.split(re.search(r"run `([^`]+)` and do what it prints", rows[0])[1]) + t.case_paths(case)[2:]
    subprocess.run(command, capture_output=True, text=True, cwd=case.checkout)
    offered_again = bool(handoff_rows())
    subprocess.run(command, capture_output=True, text=True, cwd=case.checkout)
    answers = case.minutes.read_text().count("settled without asking the user, already decided by")
    print("DEFECT REPRODUCED" if offered_again and answers == 2 else "NOT REPRODUCED",
          f"(handoff row offered again: {offered_again}; answer lines for item 1: {answers})")
finally:
    shutil.rmtree(t.SUITE_ROOT, ignore_errors=True)
EOF
```

It prints `DEFECT REPRODUCED` on main today. Expected: the second read offers no handoff row, and the walk-minutes hold one answer line for item 1. Observed: the read step offers the handoff row again, `check` exits 0 the second time, and the walk-minutes hold two identical lines `item 1 of 3: settled without asking the user, already decided by ...`. A later `close` exits 0 and writes one close line after both.

## What is wrong

`settling_left_unclosed` in `nn-systems/skills/walk-me-through/walk-me-through-answer-added-texts-cold-read-fast-read-check-and-close.py` decides whether the walk-minutes' last answer settled the waiting item without asking the user and has no close after it. Its docstring says that rerunning the settling would then record the item twice, and `no_answer_rows_for_waiting_item_lines` offers no row in that case. But the function matches only answers of the form `not asked, <label>`. The handoff row of the no-answer table settles an item with `check --already-decided`, whose answer begins `already decided by ` (`ALREADY_DECIDED_PREFIX`), so an unclosed handoff settlement is not recognized, and the read step offers the same command again.

## Why it matters

The walk-minutes are the record of the user's approval-walk. A duplicated answer line makes the record say the item was answered twice, and a reader or a program counting answers per item reads it wrongly. Work is not lost: the duplicate can be deleted by hand.

## Next action

Fix it in two places, in one pull request:

1. In `check`, where the answer line is written: before it appends an answer, refuse, say what is wrong and exit nonzero when the walk-minutes' last answer has no close after it and names the same item. This stops a second answer however the agent reached the command, including the `--now-over-later-already-decided` command the read step prints whatever `settling_left_unclosed` returns (the `now_over_later_command` lines near line 3052 of the program). Add a test case that runs `check --already-decided` twice on one item without `close` and checks that the second run exits nonzero and the walk-minutes hold one answer line.
2. In the read step: build the set of answers `settling_left_unclosed` matches from the same code that writes them, the answer builder near line 2077 that uses `ALREADY_DECIDED_PREFIX`, so that no settling form is left out again; whether an unclosed `--moved-on` answer belongs in that set is for the fixer to decide from that builder. Add a test function of its own, beside `test_read_step_offers_the_handoff_row_only_for_an_item_naming_the_handoff`, that uses that test's document, which names the session-handoff, records an unclosed `--already-decided` answer, and checks that the read step offers no handoff row.

GHI [4644](https://github.com/nedsnodes/nedsnodes/issues/4644) fixes another defect in the same read step, a KeyError on a brace in a no-answer row; a fixer may take both in turn.

## Where it was found

The Codex review cell's report on pull request 4559, `nedlern@ned-box:/home/nedlern/nedsnodes-logs/seats/merge-lane-2/merge-helpers/cx/pr4559-58eac7f6/codex-code-review-report.md`, raised it as a P3 finding on code already on main. merge-lane-3 reproduced it with the script above.

## Search receipt

`scripts/ghi-guide-agent-ask.py`, asked on 2026-11-24 whether an open issue covers this, answered that none does and named GHI 4644 as the nearest. `gh issue list --repo nedsnodes/nedsnodes --state open --search "\"already decided\""` returned no issue.
