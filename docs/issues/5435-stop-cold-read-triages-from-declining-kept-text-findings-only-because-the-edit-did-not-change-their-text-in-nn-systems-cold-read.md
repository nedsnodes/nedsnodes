---
issue: "[Stop cold-read triages from declining `#kept_text` findings only because the edit did not change their text, in `nn-systems/cold-read/`](https://github.com/nedsnodes/nedsnodes/issues/5435)"
---

# Stop cold-read triages from declining `#kept_text` findings only because the edit did not change their text, in `nn-systems/cold-read/`

Owner: most likely agent-seat cold-read-improvement. It wrote the rule this GHI enforces (commit `411d994da`) and the program that records finding outcomes (commit `0e4250f96`). Agent-seat ned-box-helper has made more commits to `nn-systems/cold-read/cold-read-fast-read.py` (8, against cold-read-improvement's 6), so if cold-read-improvement declines this GHI, ask ned-box-helper.

## What is wrong

Step 8 of the /cold-read skill, `.claude/skills/cold-read/SKILL.md:17`, says: "When the cold-read-target is an edit of a document on main, do not decline a finding only because the edit did not change the text the finding is about. Record each such finding in `cold-read-triage.md` as one of four: fixed in this edit; already recorded, citing where the document records the problem, or the user-ruling that answers it; deferred, with where you recorded it; or not solid, declined with a reason checked against the finding's source." Step 4, `.claude/skills/cold-read/SKILL.md:13`, applies the same rule when the cold read is only a cold-read-fast-read: "When the document is an edit, record each finding about text the edit did not change in `cold-read-triage.md` with one of the four dispositions step 8 names". The rule was committed as `411d994da` on 2026-11-10 and reached main through pull request [3073](https://github.com/nedsnodes/nedsnodes/pull/3073) on 2026-11-11.

Agents break this rule routinely. They record a cold-read-fast-read finding labeled `#kept_text` as declined, with a reason that says only that the edit did not change the text. For example:

- `nedlern@ned-box:/home/nedlern/nedsnodes-logs/cold-read-records/236-pull-request-skill-how-a-change-reaches-main-2026-11-27/cold-read-triage.md:5`: "Q2.1: declined: out of scope: this change is only an obvious-error-fix of citations that went stale (GHI 572 md-drift-lint sweep); the finding concerns the GHI's substance, left to the GHI's owner". The report's finding is labeled `#kept_text` and ends "not recorded": it says the document's commands use the retired `seat-branch`, so an agent following them "will fail or follow a retired workflow".
- `nedlern@ned-box:/home/nedlern/nedsnodes-logs/cold-read-records/31-review-system-design-requirements-learned-from-the-legacy-2026-11-23/cold-read-triage.md:7`: "Q2.4: declined: out of scope: about text PR 4364 did not change; the follow-up task lists it and takes no action".
- `nedlern@ned-box:/home/nedlern/nedsnodes-logs/cold-read-records/nedsnodes-style-guide-2026-11-25-2/cold-read-triage.md:20`: "Q2.16: declined: about text this change did not touch, outside the scope the dispatching agent-instructions-editor set; reported to it".
- `nedlern@ned-box:/home/nedlern/nedsnodes-logs/cold-read-records/940-tasks-raise-themselves-when-their-due-time-passes-2026-11-25-8/cold-read-triage.md:27` copies an earlier triage's declines, and says what that loses: "Each is declined as outside this edit, as the triage of PR 4638's edit of the same GHI-MD did (…). Some are real defects that still need routing, such as claude-hunt-second-strongest-model 22 and claude-terminology-deep 31".

A real problem that a cold read found and a triage declined this way is recorded nowhere else, so it is lost.

## How often it happens

A read-only search on 2026-11-28 read every `cold-read-fast-read-finding-outcomes.json` under `nedlern@ned-box:/home/nedlern/nedsnodes-logs/cold-read-records/`, the file `--record-finding-outcomes-in-cold-read-record` writes, whose first copy was recorded on 2026-11-20. It counted an outcome when the outcome is `declined`, its reason matches a pattern for "the edit did not change this text", such as "out of scope", "did not change" or "untouched", and its reason matches no pattern for step 8's allowed dispositions, such as "already recorded", "deferred" or "not solid". It found:

- 849 such declines of findings the report labels `#kept_text`, in 118 cold-read-records, on each day from 2026-11-20 to 2026-11-28.
- 322 more of findings labeled `#edit`, which step 8 does not cover, and 2,634 of findings with no label. The fast-clarify prompt labels only Questions 2 and 3, and gives no label when the cold-read-target is not an edit, so the 849 leave these out.
- Two batches among the 849: 107 reading "out of scope: this change is only an obvious-error-fix of citations that went stale (GHI 572 md-drift-lint sweep)…", and 21 reading "out of scope: about text PR 4364 did not change…". With unlabeled findings included, the PR 4364 batch is 352 outcomes in 14 cold-read-records.

An earlier pass, over the `cold-read-triage.md` files changed in the 30 days before 2026-11-28 whose cold-read-record is dated 2026-11-12 or later, found 856 such lines in 113 of 480 cold-read-records. Of those 113 cold-read-records, 78 were written in the agent-sessions of 12 agent-seats, among them reboot-test (21), MD-skills-2 (17), agent-instructions-editor (8) and ned-box-helper (7); the other 35 could not be matched to an agent-seat.

The patterns match words, not meaning, so the counts are estimates. Of 10 of the 849 drawn at random from outside the two batches, 8 give no reason but the untouched text; one adds that the term is a glossary term, and one was forwarded to another agent-seat to file. The scripts and their output are in `nedlern@ned-box:/home/nedlern/nedsnodes-logs/seats/merge-lane-1/cold-read-kept-text-scope-only-declines-2026-11-28/`: `count.py` and `result.json` for the outcomes files, `analyze.py` and `out3.json` for the triage files.

## Why it happens

1. The `#kept_text` label reads as "decline". The fast-clarify prompt defines it at `.claude/skills/cold-read/prompts/fast-clarify-prompt.md:25`, and `FAST_CLARIFY_PROMPT_TEMPLATE` in `nn-systems/cold-read/cold-read-fast-read.py:419` holds the same text: "`#kept_text`: the item is about sentences the edit did not change, and the edit did not cause it; end the item by saying whether the document already records the problem, citing where, such as "open question 6", or with "not recorded"." The tag's entry in `docs/nedsnodes-wiki/nedsnodes-hashtag-glossary.md:41` says the same. None of them says what a `#kept_text` finding needs next.
2. The program offers only two outcomes. After a read, `finding_outcomes_to_record_lines` in `nn-systems/cold-read/cold-read-fast-read.py` (about lines 1827 to 1843) tells the agent to record each finding as `applied` or `declined: <your reason>`, and says nothing of step 8. `cold_read_fast_read_finding_outcomes_from_values`, at `nn-systems/cold-read/cold-read-fast-read-report-findings-parse-and-finding-outcomes-check-common.py:121`, accepts any reason that matches `DECLINED_WITH_REASON` (line 47), which is any text after `declined:`. Step 8's "already recorded" and "deferred" have no outcome of their own, so an agent must write them as `declined`, in the same form as the declines step 8 forbids.
3. Agents copy the scope they are given. The style guide's triage declines "outside the scope the dispatching agent-instructions-editor set", and the 940 triage copies the declines of an earlier triage of the same GHI-MD (both cited above). How many other dispatch briefs limit triage to the edited text was not checked (unverified).

## What to do

Fix this in the program, not by telling agents again. The owner decides the design. The direction:

- When `cold-read-fast-read.py` lists the report's findings after a read, it prints beside each `#kept_text` finding the four dispositions step 8 allows.
- `--record-finding-outcomes-in-cold-read-record` gives each of step 8's dispositions an outcome of its own, or another form the program can check, and refuses an outcome for a `#kept_text` finding that is none of them. `applied` can stay as "fixed in this edit". A reason under "not solid" is still free text, so the refusal also needs to refuse a reason that says only that the edit did not change the text, for example by the patterns `count.py` uses. Where the outcome cites a place, such as the open question that already records the problem, or the GHI or task a deferral went to, the program can check that the place exists. This is rejecting malformed input where it enters the program, which `CLAUDE.md` exempts from needing a test that reproduces the failure; the refusal's own code still carries its tests.

Two more questions for the design. First, three of the four examples above are lines an agent wrote by hand in `cold-read-triage.md`, which a check in the outcomes flag does not reach; the program could write a cold-read-fast-read's lines of `cold-read-triage.md` from `cold-read-fast-read-finding-outcomes.json`, and the triage of a cold-read-full-run's reports needs its own answer. Second, the check rests on the reviewer model giving the `#kept_text` label; the program could instead find, by comparing the cold-read-target with main, which findings quote only unchanged text.

GHI [Rebuild the /cold-read skill so its programs do the mechanical steps and print each instruction when the agent needs it](https://github.com/nedsnodes/nedsnodes/issues/2158) and GHI [Build the cold-read-fast-read refusals and reads the user ordered for all lasting agent-facing prose](https://github.com/nedsnodes/nedsnodes/issues/3129) are where such a check would most likely already be planned; extend whichever plans it rather than building a second check. GHI [Fix the problems the cold reads found in the unchanged text of the cold-read prompts under `.claude/skills/cold-read/prompts/`](https://github.com/nedsnodes/nedsnodes/issues/4114) holds findings on the same label, its items 8 and 9, but is about the prompts' wording, not this check.

## Open question

Whether the 849 past declines need redoing, or only the triages of pull requests still open when the check lands. The owner puts this to the user.

## Next action

The owner reads GHIs 2158 and 3129 for a plan that overlaps this one, writes the design of the outcome check in this GHI-MD, and builds it.

## How this GHI was found

On 2026-11-28 `scripts/ghi-guide-agent-ask.py --include-closed` found no open or closed issue on these declines or on the outcomes flag accepting any reason, and named GHIs 4114, 2158 and 3129 as nearest. A search of `docs/issues/` on main at `66bebe65d` for `kept_text` found only GHI 4114.
