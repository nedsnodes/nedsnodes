---
issue: "[The test runner `scripts/run-all-test-suites.py` records which code each test case covers, using coverage.py's per-test contexts](https://github.com/nedsnodes/nedsnodes/issues/2259)"
---

# The test runner `scripts/run-all-test-suites.py` records which code each test case covers, using coverage.py's per-test contexts

## What this GHI asks for

A mapping from each test case to the lines and branches of code it executes, recorded by the test runner, `scripts/run-all-test-suites.py`, when it runs the test suites. coverage.py can record, for each line it measures, which test executed it, through its dynamic contexts; coverage 7.16.2 is pinned in `nn-systems/general-tools/python-libraries-pinned-requirements.txt`, and the runner does not use it today.

This GHI is a placeholder: no design exists yet. The design answers these questions:

1. How the test case boundaries reach coverage.py. A suite here is a script, in Python or shell, that prints one PASS or FAIL line per test case after the case ends, rather than a pytest file, and coverage.py's dynamic contexts need to be told when each case starts, in the process being measured.
2. What is recorded for a suite that is not in Python, for the programs a suite starts, and for a suite that crashes, times out or prints no PASS or FAIL line.
3. Which test runs record the mapping, given that measuring coverage slows a suite; how each suite's coverage data leaves its nn-test-sandbox, whose `/tmp` and checkout overlay are thrown away when the suite ends; and how the data of suites run at once is combined.
4. Where the mapping is stored and for how long, and what the readers named under Related need from it, such as branches rather than only lines.

## Why

The user decided the mapping on 2026-10-14, as part of point 4 of the approval-walk ned-box-head-test-runs-in-isolated-test-environments-2026-10-14, recorded in GHI [Each test suite on ned-box runs in its own throwaway test environment, and suites start by free CPU and memory instead of waiting for a machine-wide lock](https://github.com/nedsnodes/nedsnodes/issues/1374), whose GHI-MD is `docs/issues/1374-each-test-suite-on-ned-box-runs-in.md`. Point 4 reads: "Later, as a step of its own, a mapping from each test case to the code it covers." That GHI-MD's list of parts to reuse names "coverage.py with its per-test contexts for the later coverage mapping". The build of that GHI did not include the mapping, and that GHI closes with this GHI carrying the work.

The user approved a second use of the mapping on 2026-11-24, in item 3, "Test-run speed and the critical path", of approval-walk side-discussions-not-followed-up-approval-walk-2026-11-24, answer "A" at 16:19Z (the walk-document's copy is in nedlern@ned-box:/home/nedlern/nedsnodes-logs/walk-document-copies/side-discussions-not-followed-up-approval-walk-2026-11-24/). One of the items that item lists as missing reads: "a map from each test to the files it covers, so a change runs only its own tests, where GHI 2569 skips only whole suites whose inputs did not change". GHI 2569 is [The test runner `scripts/run-all-test-suites.py` reruns suites whose recorded inputs did not change, because it keeps one recording per suite for every branch and selects every suite that runs a content-reading git command on the checkout](https://github.com/nedsnodes/nedsnodes/issues/2569). So the design also decides whether, and how, the runner uses the mapping to run, within a suite it selects, only the test cases whose covered files the change touches.

## Questions the design must settle before that use is built

1. How the runner runs only some of a suite's test cases. On main at 2c42b2d19, 273 files match `*-test.py` or `*-test.sh` (`git ls-files '*-test.py' '*-test.sh' | wc -l`), and 22 of the Python ones import unittest or pytest (`git ls-files '*-test.py' | xargs grep -l -E '^import unittest|^from unittest|pytest' | wc -l`); the rest are scripts that go through every case in order and print one PASS or FAIL line per case, with no way to ask for one case. Running only some cases means each such suite learns to take a list of case names, for example through one shared helper that every case runs through, which also tells coverage.py when each case starts; or the runner skips nothing inside a suite, and the mapping serves only the readers under Related.
2. How much running only the touched test cases saves beyond selecting whole suites, as GHI [2569](https://github.com/nedsnodes/nedsnodes/issues/2569) does. prime-intellect knows of no measurement of it (unverified): the saving is the time taken by the cases left out, in the suites that selection of whole suites still picks. The measurement comes first, from the recorded inputs and timings of merge-lane-2's head test runs, kept under nedlern@ned-box:/home/nedlern/nedsnodes-logs/seats/merge-lane-2/merge-helpers/hr/, so that the user can weigh the cost of question 1 against it.
3. Whether the mapping keys on files, as item 3's words say, or on lines and branches, as the first paragraph of What this GHI asks for says. Files are cheaper to record and enough for selection; lines and branches are what GHI [#18](https://github.com/nedsnodes/nedsnodes/issues/18) and GHI [#35](https://github.com/nedsnodes/nedsnodes/issues/35) under Related need.

## Related

On 2026-10-30, `scripts/ghi-guide-agent-ask.py --include-closed`, asked for a GHI that builds this mapping, found none. Three GHIs would read such a mapping without building it: GHI [#18](https://github.com/nedsnodes/nedsnodes/issues/18) (`docs/issues/18-write-test-plan-riders-and-test-evidence-rules.md`), whose rule 2 has each planned test declare the code paths it reaches and compares them with the paths coverage.py measures; GHI [#35](https://github.com/nedsnodes/nedsnodes/issues/35) (`docs/issues/35-declaration-vs-reality-posit-ladder.md`), a research thread whose point 3 makes the same comparison for every test; and GHI [#2135](https://github.com/nedsnodes/nedsnodes/issues/2135) (`docs/issues/2135-mutation-testing-before-push-mutates-only-failure-handling.md`), which decides what code mutation testing mutates, and could use the mapping to choose the test suites that run against each mutant. The design reads all three, so that one mapping serves them.

## Next action

prime-intellect, the agent-seat that owns the work to make test runs faster, measures question 2 of the section on the questions the design must settle, records the result in the log-store under nedlern@ned-box:/home/nedlern/nedsnodes-logs/seats/prime-intellect/, and brings questions 1 to 3 to the user. Then write the design in this GHI-MD, answering the four questions above and following his user-rulings on questions 1 to 3 after reading the three GHI-MDs under Related; then add the line `kind: design` to the front matter at the top of this GHI-MD, between its `---` lines, and build the mapping in its own pull request.
