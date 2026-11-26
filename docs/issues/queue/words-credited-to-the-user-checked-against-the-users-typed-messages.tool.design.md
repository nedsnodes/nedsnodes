---
kind: design
---

# Check that words an agent credits to the user are words the user typed

## What goes wrong

Agents quote the user back to him, as in `you said "…"` or `your ruling "…"`, and nothing checks that he wrote those words. On 2026-10-24 he told ned-box-helper that agents often quote his rulings back to him wrongly. He wanted a hook to check the pattern rather than a CLAUDE.md rule (`nedlern@ned-box:/home/nedlern/agents/ned-box-helper/docs/walk/ned-box-helper-combined-open-items-2026-10-22-minutes.md` line 181).

A Codex study that day, `nedlern@ned-box:/home/nedlern/nedsnodes-logs/analysis/absolute-word-warn-categories-2026-10-24/codex-misquoted-user-rulings-report-2026-10-24.md`, sampled 100 agent replies that quote him, checking the first quote of four words or more in each, with seed 20261024:

| Result | Replies |
|---|---|
| Matched what he typed exactly | 59 |
| Matched once case, spacing and punctuation were made equal | 7 |
| Close to what he typed, but changed | 13 |
| Matched nothing he typed | 21 |

Some quotes that matched nothing became part of standing documents, or were cited as the reason for a change, and he never corrected them:

- MD-skills, 2026-09 (`nedlern@ned-box:/home/nedlern/nedsnodes-logs/session-dialogs/mac/-Users-el-agents-MD-skills/019b6b73-f703-41e1-b321-6cc0c77313de-dialog-complete.md`):
  - Line 316 told him the glossary's purpose paragraph "now carries your rule in your words, "Include key-terms that all or most agents might need. Do not include terms that will be rarely needed."". He had written "remember this is a file that all agents will read … don't put in stuff for rare agents" (line 272 of the same file).
  - Line 1198 then answered six reviewers' findings on the glossary with "The two sentences are your own statement of that ruling".
- merge-lane (`nedlern@ned-box:/home/nedlern/nedsnodes-logs/session-dialogs/mac/-Users-el-agents-merge-lane/f311cdb6-30a8-445b-a9f6-ba7105577c5d-dialog-complete.md` line 107): a reviewer step was rewritten under "Your ruling "a mutation is asserted applied"". The study found no message he typed that holds those words.

He approved decisions resting on words he never wrote, and the instructions that agents follow carry them as his.

## What is decided

Item 6.3 of approval-walk ned-box-helper-combined-open-items-2026-10-22, "A hook checks each quote of your words against what you actually wrote", was approved on 2026-10-24 (same walk-minutes, line 213). Its three parts:

1. A small Python program does the check. When the user sends a message, a hook runs it on the agent's previous reply. It takes each quote the reply credits to him, after cues such as "you said", "your words" or "your ruling was". It searches the transcript, his typed messages in the session dialogs, and the walk records, which hold rulings he approved with a letter. It allows for case, spacing and "…". When a quote is not found, the hook tells the agent: "I couldn't find '…' in the user's messages or rulings. Check the source and quote the user exactly, or say you are paraphrasing."
2. A skill, `/check-quote`, runs the same program on any quote the user or an agent gives it. It prints where the quote appears, or the nearest match.
3. cold-read-improvement builds the program, the hook and the skill.

The hook warns and never blocks.

## How it works

- **Program:** proposed name `scripts/user-quote-in-agent-reply-check.py`. It reads a reply on standard input and finds the quotes in it, or takes one bare quote with `--quote`, which needs no cue. It exits 0 when every quote is found, 1 when one or more is not, and 2 when it could not finish, such as on an unreadable transcript.
- **Finding the quotes:** it takes each quoted span of four words or more that follows a cue crediting the user, within the same sentence or as the block quote that follows. The cues are the ones the study lists in its section 4:
  - "you said", "you wrote", "you asked", "you told";
  - "your words", "your own words", "your exact words";
  - "your answer was", "your ruling was", "your ruling says";
  - "as you put it";
  - "user-ruled YYYY-MM-DD:".

  It skips a quote by fixed rules, never by judgment: a cue after "if", "say" or "e.g." marks a hypothetical; a quote within the same sentence as a file path or a backticked file name is credited to that file; a quote that is a whole link text or heading is a title. The study's 100 sampled replies are the test cases for these rules.
- **Length:** the whole quote must be four words or more; a piece between "…" may be shorter.
- **Where it searches:**
  - his typed messages, as `scripts/search-user-messages-in-transcripts.py` reads them. `scripts/log-store-past-discussions-regex-search-newest-first.py --kind user-messages` already uses that reader, so the program reuses it rather than parsing transcripts again;
  - the user turns of the current agent-session's transcript, never its agent turns;
  - walk-documents and walk-minutes, in each agent-home's `docs/walk/` and in the log-store's `walk/` folder. On the Mac the program reaches the log-store over ssh to ned-box. An item's `#new` text counts as his words when the walk-minutes record "the user answered approved" for that item, because he approved it word for word.
- **Matching:** case, whitespace, straight and curly quotes, and punctuation are made equal. "…" or "..." splits the quote into pieces that must appear in order, in one message or one item; an empty piece, from a leading or trailing "…", is dropped.
- **Nearest match:** when a quote is not found, the program reports the stretch of his messages, of the quote's length, with the highest `difflib.SequenceMatcher` ratio.
- **Hook:** a UserPromptSubmit hook, proposed name `scripts/user-quote-in-agent-reply-warning-hook.py`, which runs the program on the reply and is built like `scripts/bare-number-citation-in-markdown-and-agent-reply-warning-hook.py`, which already reads the agent's previous reply at that event. It prints item 6.3's message for each quote not found, with the nearest match when there is one. It stops the program after 5 seconds and says the check did not finish, so a slow search never holds up the user's message.
- **Skill:** `/check-quote` runs the program with `--quote` and prints each place the quote is found, or the nearest match.
- **When ruling-agent is built:** GHI [ruling-agent keeps user-rulings, checks approval-walk items against them](https://github.com/nedsnodes/nedsnodes/issues/2118) plans a store of his verbatim words and an index file that hooks read. The program uses that index file when it exists, and the sources above when it does not, so no later change is needed.

## What it does not do

- **Quotes credited to a file:** checking those against the file is left out. In 204 `#old` lines across 12 walk-documents, no quote of a file was wrong against the source it named, and every misquote of a file on record was caught before the user answered (`nedlern@ned-box:/home/nedlern/nedsnodes-logs/seats/fleet-restart-at-login/old-quote-check-evidence-2026-11-22.md`). That does not meet CLAUDE.md's bar for a new check.
- **Unquoted claims** such as "you ruled" or "per your ruling" are not checked. Item 6.3's alternative, which asked the agent for the source of each one, was not chosen. The worst misstatements in the study were of this kind: prime-intellect told him he had ruled that agents do not add a task without first raising it with him, the opposite of what he had said, and he corrected it (`nedlern@ned-box:/home/nedlern/nedsnodes-logs/session-dialogs/ned-box/-home-nedlern-agents-prime-intellect/fcbc9268-e319-43ce-8bdf-1c9eee1e2bbf-dialog-complete.md` line 3432). Matching words cannot judge meaning.

## Test

The test that reproduces the failure is the MD-skills case: a reply crediting the user with "Include key-terms that all or most agents might need", beside a typed message holding only "don't put in stuff for rare agents", must be reported. Passing cases:

- an exact quote;
- a quote that differs only in case and punctuation;
- a quote with "…" whose pieces appear in order in one message;
- an approved `#new` text quoted as his ruling.

The program's own failure, such as an unreadable transcript, is reported in its output and lets the user's message go through.

The near-match threshold, how close a stretch must be to be shown as the nearest match, is set by a test from the study's 13 near matches and 21 quotes that matched nothing: the test fails if the threshold stops separating them.

## Deferred-decisions

- Whether the hook runs at Stop instead, on the reply before the user reads it, so the agent corrects a misquote before he answers it. Item 6.3 approved a UserPromptSubmit hook, which warns only after he has read the reply.

## Next action

Build the program and the UserPromptSubmit hook in one pull request, with the test above. Then build `/check-quote` in a second pull request.

## Relations

- GHI [ruling-agent keeps user-rulings, checks approval-walk items against them](https://github.com/nedsnodes/nedsnodes/issues/2118): its index file of his verbatim words becomes this program's source once it is built.
- ghi-guide-agent, asked on 2026-11-22 with `--include-closed` whether any issue covers checking quotes credited to the user, found none. GHI 2118 was the nearest.
