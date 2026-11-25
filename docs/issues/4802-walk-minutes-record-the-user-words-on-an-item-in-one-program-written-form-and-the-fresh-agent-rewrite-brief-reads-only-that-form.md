---
issue: "[Walk-minutes record the user's words on an item in one program-written form, and the fresh-agent rewrite brief reads only that form](https://github.com/nedsnodes/nedsnodes/issues/4802)"
---

# Walk-minutes record the user's words on an item in one program-written form, and the fresh-agent rewrite brief reads only that form

## What is wrong

When an approval-walk item has been revised three times, the walk check program, `nn-systems/skills/walk-me-through/walk-me-through-answer-added-texts-cold-read-fast-read-check-and-close.py`, prints a brief for a fresh agent that rewrites the item from the user's words. Its function `approval_walk_item_user_words_in_minutes` finds those words by searching every line of the walk-minutes for the phrase "his words" and an item number or title before it. Walk-minutes are free prose that agents write in many forms, so the search keeps both kinds of error:

- It takes lines that do not record the user's words on the item. On 2026-11-25 it gave the brief for item 24 of 61 of approval-walk `ned-box-helper-open-items-approval-walk-2026-11-22` an agent's note that quoted the user on item 24 of another walk. PR [Fresh-agent rewrite brief quotes the user's reply that raised a bumped item, not any line saying "his words"](https://github.com/nedsnodes/nedsnodes/pull/4795) reads the item number only before "his words", which ends that case. Its review found two more cases that still pass: a line citing an earlier ruling for an already-decided item, and a line inside a fenced example (Codex findings 7a9dbd7538fb and 4829618bb6d6 on that pull request).
- It misses lines that do, whenever the recording agent worded them without "his words".

## What to do

Give the user's words on an item one fixed form, written by a program step, such as the walk-me-through hooks that already write the line `User (<date and time>), on item <N> of <M> while it waited, a reply in his words that is not a short answer: "<words>"`, and by the check program's answer and bump lines. Have `approval_walk_item_user_words_in_minutes` read only lines of that form, through the shared parsing module that GHI [Replace the hand-written parsers in the project's hooks and scripts with real parsers](https://github.com/nedsnodes/nedsnodes/issues/1196) sets for Python, so that no agent's prose can enter the brief. Say what becomes of walk-minutes written before the change, whose user's words are in other forms, and of lines whose words an agent types into a program, such as the check program's `--user-reply-as-typed`.

GHI [The walk-me-through check program reads untagged walk-minutes lines as decisions by their keywords](https://github.com/nedsnodes/nedsnodes/issues/1930) has the same cause for decisions; one design of the minutes' fixed forms should serve both. GHI [ruling-agent keeps user-rulings, checks approval-walk items against them](https://github.com/nedsnodes/nedsnodes/issues/2118) stores the user's words as rulings; a fix should read from that store if it is built first, not build a second one.

## Next action

ned-box-helper writes the change to the check program and the hooks that write the user's words, with a test for each case under "What is wrong", and opens its pull request.
