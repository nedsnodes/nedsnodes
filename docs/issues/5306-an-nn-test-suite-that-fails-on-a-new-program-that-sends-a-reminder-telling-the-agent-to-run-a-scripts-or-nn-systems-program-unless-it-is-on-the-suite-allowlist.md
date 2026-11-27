---
issue: "[An nn-test-suite that fails on a new program that sends a reminder telling the agent to run a `scripts/` or `nn-systems/` program, unless it is on the suite's allowlist](https://github.com/nedsnodes/nedsnodes/issues/5306)"
---

# An nn-test-suite that fails on a new program that sends a reminder telling the agent to run a `scripts/` or `nn-systems/` program, unless it is on the suite's allowlist

## Why

A reminder is a hook's `additionalContext` message sent by a hook that never refuses: the action goes ahead, and the agent is asked to act afterwards. No code checks afterwards whether the agent did, and agents often do not. In a search on 2026-11-25, in 29 of 187 transcripts that held the push citation-check reminder of `nn-systems/general-tools/claude-code-bash-git-push-of-markdown-change-citation-checks-reminder-hook.py`, the agent never ran either check it asks for. GHI [Design the project's Claude Code hooks: requirements drawn from the existing hooks, then keep, fix, merge, rewrite or remove each one](https://github.com/nedsnodes/nedsnodes/issues/1790) found that agents acted on 7 of 10 sampled reminders.

GHI 1790 decides, hook by hook, what happens to the reminders that exist. Nothing stops a new one from being added meanwhile. This nn-test-suite fails when a program on main sends such a reminder and names a `scripts/` or `nn-systems/` program for the agent to run, unless the program is on the suite's allowlist. The allowlist starts with the 11 programs below, and each entry points to GHI 1790, where that program is decided. When GHI 1790's work fixes or removes a program, its entry leaves the allowlist.

The user approved this on 2026-11-27, as item 12 of 52 of the approval-walk kept on ned-box at `nedlern@ned-box:/home/nedlern/agents/prime-intellect/docs/walk/prime-intellect-open-items-refreshed-against-main-approval-walk-2026-11-26.md`, answer A.

## Inputs

- The search: `nedlern@ned-box:/home/nedlern/nedsnodes-logs/seats/prime-intellect/agent-instruction-messages-without-outcome-check-search-2026-11-25/`. Its `summary.md` gives the counts; `ignored-messages.json` gives the two messages agents ignored.
- The recount that gives the 11, with its commands and what reading each program shows: `nedlern@ned-box:/home/nedlern/nedsnodes-logs/seats/prime-intellect/agent-instruction-messages-without-outcome-check-search-2026-11-25/reminder-programs-that-tell-the-agent-to-run-something-recount-2026-11-27.md`.
- `nn-systems/general-tools/python-source-tool-message-to-agent-string-collector-common.py`, which finds the tool-messages-to-agent in a Python file, including the value of each hook output key in `TOOL_MESSAGE_TO_AGENT_HOOK_OUTPUT_KEYS` and the text of each module string constant that reaches it.
- `scripts/registered-hook-messages-carry-no-citations-test.py`, an nn-test-suite of the same shape: it reads the hooks `.claude/settings.json` registers, lists its exceptions by file, and fails when an exception names a file that is no longer a registered hook.
- `nn-systems/general-tools/claude-code-registered-hook-rule-id-pattern-hook-files-list-and-source-scan-common.py`, whose `registered_hook_paths` lists the hooks `.claude/settings.json` registers.
- GHI [Hooks that tell the agent something on stderr with exit 1 are read only by the user, because Claude Code never gives that stderr to the model](https://github.com/nedsnodes/nedsnodes/issues/1796): exit 2 hands stderr to the model as a blocking error, so a hook that exits 2 refuses.
- GHI [Every refusal and warning a program hands an agent says why and what to do instead](https://github.com/nedsnodes/nedsnodes/issues/956) and GHI [One shared list of the kinds of check failure, used by reviewers, authors and test writers, and a daily check that each kind is handled the same way](https://github.com/nedsnodes/nedsnodes/issues/3968), which the suite's failure message follows.

## The allowlist's first 11

The recount's rule, at commit 2c42b2d19, found these 11; the recount file gives the rule.

- `.claude/guard-hooks/guarded-file-unapproved-change-afterward-backup-and-ask-hook.py`
- `nn-systems/general-tools/bash-guards-verdict-changes-between-git-refs-on-recorded-commands-check.py`
- `nn-systems/general-tools/claude-code-bash-git-push-of-markdown-change-citation-checks-reminder-hook.py`
- `nn-systems/general-tools/failed-command-tool-message-to-agent-rerun-once-then-stop-and-report-lines-common.py`
- `nn-systems/general-tools/python-edit-changed-tool-message-to-agent-strings-check-reminder-hook.py`
- `nn-systems/skills/walk-me-through/walk-me-through-user-short-answer-to-approval-walk-item-expanded-into-instructions-user-prompt-submit-hook.py`
- `scripts/agent-reply-possibly-stale-system-status-claim-recheck-reminder-hook.py`
- `scripts/checkout-freshness-catch-up.py`
- `scripts/new-shared-names-reminder-hook.py`
- `scripts/obsolete-file-edit-warning-hook.py`
- `scripts/unvalidated-negative-result-check.py`

The rule was a grep, and it is not the suite's test. At bef9e17ce, on 2026-11-27, it also finds `.claude/guard-hooks/bash-guard-hooks-dispatcher.py`. Read by eye, 2 of the 11 send no reminder of their own: `nn-systems/general-tools/bash-guards-verdict-changes-between-git-refs-on-recorded-commands-check.py` only reads a hook's `additionalContext`, and `nn-systems/general-tools/failed-command-tool-message-to-agent-rerun-once-then-stop-and-report-lines-common.py` is a shared module that builds it for the hook that imports it. The dispatcher, the twelfth, merges other guards' reminders. The grep also misses reminders that do name a program to run, such as `scripts/agent-seat-due-task-raise-hook.py` and `scripts/cold-read-fast-read-due-for-linked-document-reminder-hook.py`. The recount file lists each case.

## What the suite must settle

Each question below has a recommendation. The suite's author settles each, and brings to the user, in an approval-walk, any answer that adds a program to the allowlist beyond the 11, leaves one of the 11 off it, or counts a program outside `scripts/` and `nn-systems/` as one to run.

1. Which files count as a program on main. Recommendation: every Python file git tracks on main that is not a test, as `path_is_test_file` in the collector decides, and whose source writes a value under `additionalContext` in a dict literal, as the collector finds it. Registered hooks alone would leave out 3 of the 11, which `.claude/settings.json` does not register by name. A shared module that writes the dict, such as the failed-command module above, whose line 162 writes `"additionalContext": text`, is judged as a program itself, because that is where a new reminder's text would be written. A file that only reads the key, such as the bash-guards verdict check, writes no dict literal and is not a program here.
2. How "never refuses" is told from the source. Recommendation: a file refuses when its source writes `"decision": "block"`, or `"permissionDecision"` with `"deny"` or `"ask"`, or exits 2 through `sys.exit(2)`, `raise SystemExit(2)` or a `main()` whose return value is passed to `sys.exit`. A refusal made only inside an imported helper is not seen; the suite's author lists each such hook found on main. The test is per file, as the approved wording says: a file that refuses on one path and reminds on another is not a reminder program. Whether to judge each message instead stays open, because a file that both refuses and reminds, such as `.claude/guard-hooks/force-push-with-open-pull-request-guard-hook.py`, escapes the per-file test.
3. How "names a program for the agent to run" is told from the text. Recommendation: the message's text, as the collector's `render_string_node_text_as_agent_reads_it_with_placeholder_stand_ins` gives it, with each `{name}` field replaced by the string a module constant of that name holds in the same file, holds `python3 ` or the word `run` followed, within the same sentence, by a path under `scripts/` or `nn-systems/` ending in `.py` or `.sh`. A path the message only cites, for the agent to read or edit, does not count. The backup-and-ask hook names `python3 {program}`, a program under `.claude/`, so it matches only if `.claude/` programs count too. Whether they do, and whether a message that names a skill, such as `/walk-me-through`, counts, stays open: the approved wording names only `scripts/` and `nn-systems/`.
4. Whether a stale allowlist entry fails the suite. Recommendation: yes, as in `scripts/registered-hook-messages-carry-no-citations-test.py`. An entry fails when its file is gone from main or no longer matches; the failure message says to remove the entry. A program that is flagged and not on the allowlist fails with a message that names the file, says it sends a reminder that names a program to run with no check that the agent ran it, and says to make the hook run the program itself or check that the agent did, or, when the user approves the reminder, to add an allowlist entry. This keeps the allowlist the list of programs GHI 1790 still has to decide. It also means an entry of the 11 that the suite's test does not match must leave the allowlist when the suite lands; the user decides that in the approval-walk above.
5. Which regex dialect the suite uses. Recommendation: Python's `re`, run on the collector's text, not grep on source lines. The search's grep patterns, listed in its `summary.md`, are GNU grep `-E` patterns (POSIX extended regular expressions); the first finds hook output keys, and the other 4 go into GHI 1790's Inputs as search aids, not as the suite's test.
6. Each allowlist entry. Recommendation: the entry is the file's path from the repository root, with a one-line reason that cites GHI 1790.

## Next action

Write the suite as a file under `scripts/` whose name ends in `-test.py`, which `scripts/run-all-test-suites.py` then runs as one nn-test-suite; its name is checked with the new-name-propose-and-check-fresh-agent. Settle each question above. Run the suite on main with the 11 as its allowlist, and have it print every program it flags that is not among the 11, and every one of the 11 it does not flag. Bring the user those two lists, and the answers the paragraph above the questions names, in one approval-walk. Land the suite with the allowlist his rulings give, and list both sets in the pull request.
