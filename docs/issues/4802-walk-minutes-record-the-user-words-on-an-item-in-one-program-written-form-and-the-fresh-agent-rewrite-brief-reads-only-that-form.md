---
issue: "[Walk-minutes record the user's words on an item in one program-written form, and the fresh-agent rewrite brief reads only that form](https://github.com/nedsnodes/nedsnodes/issues/4802)"
---

# Walk-minutes record the user's words on an item in one program-written form, and the fresh-agent rewrite brief reads only that form

## What is wrong

When an approval-walk item has been revised three times, the walk check program, `nn-systems/skills/walk-me-through/walk-me-through-answer-added-texts-cold-read-fast-read-check-and-close.py`, prints a brief for a fresh agent that rewrites the item from the user's words. Its function `approval_walk_item_user_words_in_minutes` finds those words by searching every line of the walk-minutes for the phrase "his words" and an item number or title before it. Walk-minutes are free prose that agents write in many forms, so the search keeps both kinds of error:

- It takes lines that do not record the user's words on the item. On 2026-11-25 it gave the brief for item 24 of 61 of approval-walk `ned-box-helper-open-items-approval-walk-2026-11-22` an agent's note that quoted the user on item 24 of another walk. PR [Fresh-agent rewrite brief quotes the user's reply that raised a bumped item, not any line saying "his words"](https://github.com/nedsnodes/nedsnodes/pull/4795) reads the item number only before "his words", which ends that case. Its review found two more cases that still pass: a line citing an earlier ruling for an already-decided item, and a line inside a fenced example (Codex findings 7a9dbd7538fb and 4829618bb6d6 on that pull request). After it merged, merge-lane-2's follow-up review on that pull request found two more:
  - When the user bumps an existing item 7 while item 2 waits, item 7's brief quotes his replies on item 2, because a bump line records the order items are shown in, not which reply raised the bumped item (Codex finding 7e70599c3586).
  - A remark the user made outside any item, which names an item only to say when he made it, enters the brief of every item a bump line links to that item, as line 83 of `nedlern@ned-box:/home/nedlern/agents/MD-skills-2/docs/walk/md-skills-2-agent-seat-items-awaiting-user-ruling-approval-walk-2026-11-21-minutes.md` does with "while item 6 of 24 was being prepared" (Codex finding 52365ee3c36b).
- It misses lines that do, whenever the recording agent worded them without "his words".
  - When a reply answers item 1 and raises a new item, and the agent advances before bumping, the bump names item 2 as waiting, so the new item's brief misses the reply (Codex finding 7e70599c3586 on PR 4795).
  - The search reads no item number from a line whose number is followed by a comma and a date, as in "on item 3, 2026-11-23T01:34Z, his words", so it misses that line; three such lines are item 3's in the walk-minutes above, item 1's in `nedlern@ned-box:/home/nedlern/nedsnodes-logs/walk/cold-read-improvement-open-items-approval-walk-2026-11-22-minutes.md` and item 34's in `nedlern@ned-box:/home/nedlern/nedsnodes-logs/walk/ghi-783-ghi-md-picks-and-renames-approval-walk-2026-11-05-minutes.md`.

## What to do

Give the user's words on an item one fixed form, written by a program step, such as the walk-me-through hooks that already write the line `User (<date and time>), on item <N> of <M> while it waited, a reply in his words that is not a short answer: "<words>"`, and by the check program's answer and bump lines. Have `approval_walk_item_user_words_in_minutes` read only lines of that form, through the shared parsing module that GHI [Replace the hand-written parsers in the project's hooks and scripts with real parsers](https://github.com/nedsnodes/nedsnodes/issues/1196) sets for Python, so that no agent's prose can enter the brief. The fixed form names the item the words are on, written when the line is written: a bump or a new item records the reply that raised it, and a remark made outside any item takes a form that no item's brief reads. Say what becomes of walk-minutes written before the change, whose user's words are in other forms, and of lines whose words an agent types into a program, such as the check program's `--user-reply-as-typed`. When an item's brief would carry no line of the fixed form, the check program says so and names the walk-minutes file, rather than printing a brief with no words of the user's.

GHI [The walk-me-through check program reads untagged walk-minutes lines as decisions by their keywords](https://github.com/nedsnodes/nedsnodes/issues/1930) has the same cause for decisions; one design of the minutes' fixed forms should serve both. GHI [ruling-guide keeps user-rulings, checks approval-walk items against them](https://github.com/nedsnodes/nedsnodes/issues/2118) stores the user's words as rulings; a fix should read from that store if it is built first, not build a second one.

## Next action

ned-box-helper writes the change to the check program and the hooks that write the user's words, with a test for each case under "What is wrong", and opens its pull request.
