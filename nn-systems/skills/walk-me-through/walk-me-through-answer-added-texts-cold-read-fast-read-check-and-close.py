#!/usr/bin/env python3
"""Carry out the user's A, AO, Aa, D, Z, O2 or O3 answer to the waiting item of an
open approval-walk, or his A, AO or D answer to each part of it, or his moving on
from an item that asks no decision: give each text
the answer adds a cold-read-fast-read, then record the answer in the
walk-minutes and set their `#next_to_present` line to the next item; or record
the waiting item as settled without showing it to him.

Usage, from the agent-session's checkout:
  walk-me-through-answer-added-texts-cold-read-fast-read-check-and-close.py check
      [--obvious | --after-advisor | --disapproved | --deferred | --option N
       | --part-answer N=ANSWER ... | --moved-on-no-decision
       | --not-asked KIND|adds-nothing|none|weak-cost-only|weak-alters-earlier-approved-text-only
       | --already-decided USER_RULING [A|D] | --now-over-later-already-decided
       | --moved-on REASON]
      --user-reply-as-typed REPLY    (every answer but --not-asked, --already-decided,
                                      --now-over-later-already-decided and --moved-on)
  walk-me-through-answer-added-texts-cold-read-fast-read-check-and-close.py check --bump ITEM
      [--user-reply-as-typed REPLY]
  walk-me-through-answer-added-texts-cold-read-fast-read-check-and-close.py close
      [--hold-answer-until-new-item-answered]
  walk-me-through-answer-added-texts-cold-read-fast-read-check-and-close.py approval-walk-waiting-item-cold-read-fast-read
      [--after-fixes-reread-only-when-facts-change]
      [--possibly-stale-system-status-claims-rechecked WHAT_YOU_RAN_AND_WHEN]
      [--approval-walk-item-fresh-agent-rewrite-file FILE]

The answer is an approval, A, unless a flag says otherwise: --obvious for AO,
--after-advisor for Aa, --disapproved for D, --deferred for Z, --option 2 or 3
for O2 or O3, which approve the item's "Option N" paragraph instead of its
recommendation. R, E and O decide nothing, so the program takes no flag for
them. --part-answer, given once for each part of an item that holds parts, as
in `--part-answer 1=A --part-answer 2=D`, gives that part its own answer, A, AO
or D. Z is not taken for a part, and a part number given twice is refused,
writing nothing. Three flags record an item the user does not answer, so that no
agent writes a deciding line by hand: --already-decided for an item an earlier
user-ruling decides, USER_RULING citing that ruling, followed by the answer the
ruling gives: nothing or A when it decides the item as the item recommends,
which adds the `#new` texts as A does; D when it decides the item against its
recommendation, for its alternative, which adds the `#new_if_d` texts as D does
and is recorded as disapproved; any other value after USER_RULING is refused,
writing nothing, and so is --already-decided given twice; --now-over-later-already-decided, the
same with the now-over-later ruling as its citation; and --moved-on for an item the walk
leaves with no decision, REASON saying why, which changes nothing. While the
walk-minutes' last answer, for any item and of any kind, has no close after it,
as when the advisor objected to a settling and the item is shown after all,
check refuses, writing nothing, every --not-asked, --already-decided and
--now-over-later-already-decided, and the read step offers neither a no-answer
row nor the now-over-later settling, since a settling then could record an item
twice and reverse what that answer recorded; the user's own answer is still
taken. When the
walk-minutes hold an `#item_page` line for the item, a link or a failed
publish, the user was shown it, so --moved-on writes its answer line opening
`shown to the user,` in place of `settled without asking the user,`, and CLOSE
says the item was shown in place of saying it was settled without being
shown.
--bump ITEM, for the user's "bump" and the item he names, records no answer: it
makes ITEM, an item not yet shown named by its heading's title, the next item
shown, numbering it and moving it to stand right before the waiting item in the
walk-document, so that close comes back to the waiting item once ITEM is
answered, or decided through its last sub-step, unless the waiting item is the
summary item, is decided or deferred twice, or is gone from the walk-document;
and it writes the minutes' `#next_to_present` line. It refuses, writing
nothing, an ITEM no item heading has, and one already shown, which is every
numbered item, decided or not; and it refuses, writing nothing, while close
has not yet recorded the last answer check wrote, since close would then take
that answer as the answer to ITEM too.
--moved-on-no-decision records that the user moved on from an
item that asks for no decision, such as a summary item: it needs no
`#case_against` line, runs no fast read, and close records the item as `<moved on, no
decision>`. It is refused, writing nothing, for an item that has a recommendation as
the short-answer hook reads it: text after its last "Recommendation:", outside
fenced or indented code and HTML comments, because that item asks for a decision.
It is refused too, writing nothing, when the item has no such recommendation but
does have one once a `<!--` inside an HTML tag opens no comment, as when the
`<!--` in an attribute, such as `<div title="<!--">`, hides the recommendation
from the short-answer hook's reading.

Every answer but --not-asked, --already-decided, --now-over-later-already-decided
and --moved-on, which record an item the user did not answer, needs --user-reply-as-typed, the user's reply
exactly as he typed it; check writes it, its whitespace runs squeezed to single
spaces, into the answer line right after the time of the answer, which check
writes in UTC marked Z, in the form `(YYYY-MM-DD HH:MMZ)`, as in ``in his words "`a
trivial - a bit longer doesn't matter.`"``, so that the minutes keep a
remark that rides with the answer. The reply, USER_RULING, REASON and the start
of each text in a status line are written as code spans, so that a
`#next_to_present` or `#approval_walk_paused` inside them is not read as the
walk's marker. A check without --user-reply-as-typed is refused, writing
nothing, and so is one that gives it with any of those four. A reply that is a
navigation word alone, next, N, continue or go, whatever its case and any
trailing period or exclamation mark, is refused for every answer but
--moved-on-no-decision, writing nothing: it approves nothing, and the
walk-me-through skill lets it advance only an item with no recommendation
outstanding.

The texts an answer adds are the item's lines that begin with the answer's
mark, `#new` or `#new_if_d`, as CHECK below describes them. A, AO, Aa, O2 and
O3 add the `#new` texts; D adds only the `#new_if_d` texts, the texts of the
alternative that D does instead of the item's recommendation. A line's mark
belongs to the whole item, not to a part, so answers to parts add the `#new`
texts when any part is A or AO, and the `#new_if_d` texts when any part is D.
An answer that adds no marked text gets no fast read, and its status line is
"no proposed text marked".

Every answer but O2, O3, --moved-on-no-decision, --already-decided and
--moved-on needs the item's
`#case_against` line, the first line of the item, outside fenced code, whose
first word after any list, quotation or emphasis marker is `#case_against`,
followed by a rating: none, weak, medium, strong or very strong. When the item
has that line, CHECK writes its rating into the answer line, whatever the
answer, as a hashtag right after the answer, as in
`approved #approved_obvious #case_against_weak`, so that one search finds every
rating beside its answer. When the item has no such line, CHECK refuses every
answer but those five, writing nothing. A
`#case_against` line that opens with no rating is refused for every answer,
those five included.

`--not-asked VALUE` settles the item without the user, as a row of the no-answer
table, NO_ANSWER_CASES, which `--help` prints whole and which holds each row's
meaning, evidence, check and what the agent then does. It checks what code can
from the item's evidence lines, each opening with its marker:
`#not_asked_touches` lists the files the change edits or deletes;
`#not_asked_test` names the test that fails before a fix and passes after it;
`#not_asked_source` cites the ruling, merged code or command; `#not_asked_unused`
names a thing removed; `#not_asked_rename` gives the old name, then the new one,
separated by a space, each in backquotes when it holds a space itself, as in
#not_asked_rename `instruction guard` `instruction-file guard`; `#not_asked_glossary_term`
names each glossary term the change puts in, in backquotes when it holds a space;
`#not_asked_hashtag_marker` names each hashtag marker the change adds;
`#not_asked_search` gives the first and last day of the search for the problem a
dropped proposal guarded against, the count of cases found and the places
searched, after `places:`, as in `#not_asked_search YYYY-MM-DD to YYYY-MM-DD, 0 cases,
places: the log-store's session dialogs and user messages and the commits on main`. An unused or old name is searched for as written and,
when it has two or more words, with its words joined by hyphens, by underscores
and by nothing, a run of digits both kept with the letters before it and
split off as a word of its own; every
spelling ignores case and matches even inside a longer name, so `poem-list` is
also found in `poem_list_path`, `POEM_LIST` and `PoemList`, `sha256_of` in
`sha256_of_file`, and `reader` in `Reader` and `readers`. A
failed check is refused, writing nothing, with every problem listed; a `git
grep` that fails is a failure too. Otherwise CHECK fast-reads the `#new` texts as
for A, writes the line `<item>: settled without asking the user, not asked,
kind KIND #case_against_<rating> (...)`, and tells the agent to ask the advisor
and judge what code cannot before running CLOSE, which records the item as
`<accepted>`. The checks cannot tell a case against that names only cost, or
only that the change alters text the user approved word for word on an earlier
date, from another weak one, or a fix that matches its design from one that does not;
the agent judges those.

Given `none` for an item rated weak, or a `weak-` value for one rated none, it
writes nothing and names the values that fit the rating. The minutes write the
answer as `not asked, ` and the row's label.

--already-decided refuses, writing nothing, a USER_RULING found only in
walk-minutes or a handoff dialog and dated more than RULING_DAYS_APPLIED, 90,
days before today, since the walk-me-through skill applies such a ruling only
that long. A citation that names a standing document with a line or section
in it, as STANDING_DOCUMENT_PLACE_CITED finds one, such as `GHI-MD 2118 line 63`,
is taken at any age; a standing document only mentioned, or named inside a
quotation, does not count. Any other citation's ruling is dated by the earliest
YYYY-MM-DD date in it that is not part of a name, since dates after the ruling's,
such as a merge's, often follow it; the date in `foo-2026-10-14-minutes.md` is
not read. A citation holding no such date is refused too: its ruling is taken
as too old, and the user is asked again unless the cited line holds the date.
Today is the local date. The now-over-later citation the program
supplies is not checked, since the program itself records that ruling.

`--now-over-later-already-decided` is --already-decided with the citation
supplied by the program, NOW_OVER_LATER_USER_RULING_CITATION, the user-ruling
that he is always for building now when the agents recommend now over later;
what this docstring says of --already-decided holds for it. It is for an item whose
only choice is whether to build something now or later and which recommends
now, and APPROVAL-WALK-WAITING-ITEM-COLD-READ-FAST-READ, below, says so in the
line that tells the agent to present the item. Before it writes anything, it
refuses an item that holds a `Part N.` paragraph, as the walk-me-through
UserPromptSubmit hook's part_starts finds one, a line opening `Option N`, or
a `#new_if_d` mark, since each of those is a choice the user makes, and
lists each such line by its line number in the walk-document.

The open approval-walk and its waiting items are found with
walk-me-through-approval-walk-minutes-and-walk-document-item-finder-common.py,
beside this program and loaded by path, the module the walk-me-through Stop
hook uses too, so the
`#next_to_present` line and the walk-document's item headings are read exactly
as that hook reads them. When the checkout's docs/walk/ holds more than one
approval-walk that is open or paused, every step refuses, writing nothing,
names each one's walk-minutes and says which to close and how to merge them,
since an agent-seat keeps at most one approval-walk open.

CHECK finds the texts the answer adds: the item's lines whose first word,
after any list or quotation marker and a part's opening `Part N.`, outside
fenced code, is a mark the answer adds;
the text is the rest of the line, without one pair of surrounding quotation
marks. Before it reads them, CHECK refuses, writing nothing, for every answer but
--deferred, --moved-on-no-decision and --moved-on, which add no text, when
any `#new` or `#new_if_d` line of the item has no text after its mark,
is inside fenced or indented code, has text cut from its own line as an HTML
comment, even one inside a code span, or opens a paragraph that runs onto the
lines right below it, since those texts would miss their fast read; the
refusal lists each such mark by its line number, gives the text joined into
one line where it can find it, from the run-on lines, from the rest of the
code block, or, for a mark with no text, from the lines running on right below
it or else the one fenced block or quotation after the blank lines below it,
and says how to rerun. A mark in an HTML comment is not refused, since the user
is not shown it. For each text it looks for a cold-read-record of this walk, one
whose name starts with the walk's name and a hyphen as every fast read this
program runs is named, holding a fast read's report and a file under target/
that contains the text, whitespace aside, in the checkout's cold-read-records/
and in the log-store's. Other records are not opened: the log-store holds
thousands, and a text fast-read outside this program is read again. The log-store's
cold-read-records directory is the path in cold-read-record-ship.py's
LOG_STORE_RECORDS_DESTINATION, read on ned-box as it is and on the Mac through
the Mac's mount of ned-box's home. For each text with none, it saves the text to
a scratch file and runs cold-read-fast-read.py --target on that file with
--without-question-4, which this program passes on every fast read it runs,
of a waiting item, read ahead or not, and of the texts an answer adds; the
scratch file's directory is removed when the fast read ends, whatever ends it,
SIGTERM and SIGHUP included, since the cold-read-record keeps its own copy. Then it
writes the answer line, which names each part's answer in part number order
when --part-answer is given, and one status line per text, naming its mark and
its number, from 1 in the walk-document's order, among the item's texts with
that mark, or "no proposed text
marked", into the walk-minutes, and prints the status lines, the judgement the
agent must make on new reports, and the close step to run. It appends one line
of counts to
walk-me-through-answer-added-texts-cold-read-fast-read-already-done-or-had-to-run-counts-per-check.tsv
beside the log-store's cold-read-records directory. A deferral and a move on
change nothing, so CHECK --deferred, CHECK --moved-on-no-decision and CHECK
--moved-on run no fast read, log no counts, and write only the answer line. When the `#next_to_present` line names more than
one item, CHECK refuses, writing nothing, because a run would record its one
answer, or its one set of part answers, for every item that line names; CHECK
then tells the agent to add a `#next_to_present` line naming one of those items
before each check run.

A fast read that prints a line opening FAILED, or exits nonzero, ends CHECK
before the walk-minutes are written: the program prints that line, or a FAILED
line of its own, then says the item stays waiting and tells the agent to ask
the user whether to run check again, and exits 1. The one exception is a fast
read that names its report on stdout and exits 1 because its record did not
reach the log-store, which its stderr says in a `record: FAILED` or
`record: REFUSED` line: its report is used like any other. A fast read whose
report is used but says on stderr that its record was not
shipped, or that its target changed during the read, has that line added to its
status line. An unshipped record, a log-store this machine cannot reach, and a
counts line that cannot be written are each printed after the rest, saying the
minutes record the answer, with exit 2; a changed target alone leaves the exit
code 0, since the report was written.

Each run of CHECK, CLOSE and the waiting-item step first saves the open
walk's walk-document, as it stands, to `walk-document-copies/<walk name>/` in
the log-store, named by the time in UTC and a hash of its content, keeping the
newest 20 of that walk. It saves nothing when the document is byte for byte the newest
copy, so runs that change nothing do not push older versions out. A copy that cannot be saved is printed after the step's own output,
with exit 2 if the step would have exited 0; the step itself still runs.

CLOSE reads the last answer line CHECK wrote. When the `#next_to_present` line
still names that line's items, it records the answer: that it took effect, or,
for answers to parts, a single line for the item naming each part's outcome,
or, for --moved-on-no-decision, that the user moved on from an item asking
no decision, or, for a deferral, that the item moves to just before the summary item, the item
whose heading's point opens with "summary"; an item deferred a second time
leaves the walk and stays open, and so does an item deferred for the first
time when the next item the minutes do not record after it in the walk is the
summary item and no unshown item is still to come; for --already-decided or --moved-on, that the
walk does not come back to the item, with the ruling or the reason, an already-decided
item recorded `<rejected>` when its ruling's answer is D. For a
deferral it also puts `(deferred: moved to just before the summary item)` right
after the running count of the item's walk-document heading, before it writes
the minutes, so the heading says why the item comes late; in a walk with no
summary item a deferred item goes to the end and gets no note. CLOSE takes the
note out again when it records any other answer to the item, or a second
deferral, which drops the item from the walk. On a first deferral, CLOSE
leaves the heading as it is when it holds the note already, or when it names more items
than the deferred ones, such as `Items 3 to 5 of 9`; for the second, CLOSE
prints that it gave the heading no note. It then writes a `#next_to_present` line as the
minutes' last line, naming the next item: walking the walk-document's items in
order, unnumbered items included, a once-deferred item placed just before the
summary item, from the item after the answered one, and round again from the
first, the first item the minutes do not record; `none, closed` when there is
none. The minutes record an item with sub-steps, such as 3 with 3.1 and 3.2,
once they decide every one of its sub-steps, unless its own answer is held
and no line decides it yet. The summary item is the one whose heading's point, after its running
count, or its whole title when it has no number, opens with "summary". When
the next item is unnumbered, a `## <title>` heading as the walk finder reads
one, CLOSE first writes its running count into that heading, `## Item K of M:
<title>`, K one more than the highest whole number any item heading holds and
M the walk finder's count of the items shown and waiting, and names it with
the same K and M. The line naming the next item gives that counted M,
whatever M the walk-document's headings give.

PREREQUISITE ENTRY. Last of what CLOSE prints when it names a next item, and
last of what APPROVAL-WALK-WAITING-ITEM-COLD-READ-FAST-READ prints when it
says to present the item, comes one line for each walk-document unit holding
that item: the `approval_walk_item_decided` entry, as
scripts/agent-seat-due-task-raise-hook.py reads it, that a task waiting on the
user's decision on the item appends to its metadata.prerequisites, giving the
walk-minutes' absolute path and the unit's heading line as the walk-document
holds it then. It comes after the lines the agent must pass on to the user,
so that it is not passed on.

RULING GIVEN. Once CLOSE has written the minutes for an answer that is not
held, it lists the open pull requests with `gh pr list`, run in the checkout,
and, for each answered item and each item whose held answer it decides with
it, posts on every pull request with a review holding the line
`#held_on_ruling <walk name> item <number>` the comment `#ruling_given <walk
name> item <number> <word>`, naming the same walk and item, so that a pull
request held on two items gets a comment for each that tells them apart. An
item the answer decides through its last sub-step gets a comment too, its word
its sub-steps' one word, moved_on ones left out, or part_answers when they
differ.
The walk name is the walk-minutes' file name without `-minutes.md`; a
review line matches only when, whitespace at its ends aside, it is that line
exactly. The word is `approved` for an answer recorded `<accepted>`, an
option, an item already decided as it recommends and an item settled without asking included;
`disapproved` for one recorded `<rejected>`; `deferred` for a deferral, a
second one included; `moved_on` for either move on; and `part_answers` for
answers to parts. merge-lane-2's pull request intake reads the comment. Each gh
call is stopped after GH_TIMEOUT_SECONDS. When the list cannot be had, or a
comment cannot be posted, the minutes stay as written: CLOSE prints, after the
rest, what failed and the gh command to run by hand, and exits 2. A held answer
gets no comment, since it records no ruling yet.

WALK ORDER. The unnumbered items, the summary item left out, are the items
not yet shown, and only they are sorted; a numbered item keeps its number and
its place. They come together, where the first of them comes on the round
above, or just before the summary item or a once-deferred item when one of
those comes sooner, in this order: an item after every item it waits on;
otherwise by category, the four of section 2 of
docs/nedsnodes-wiki/queue/nedsnodes-goals-and-philosophy-founding-statement-and-agent-working-principles.md
in the order WALK_CATEGORIES gives them, then by the day the item first
entered an approval-walk, then in walk-document order; an item waited on takes
the place the item waiting on it would take, when that is earlier. Any item
waiting on an item still to come, a deferred one included, is passed over.
Each such item gives its category on a line opening with
`#approval_walk_item_in_category_<category>`, each item it waits on on a line
`#approval_walk_item_waits_on <that item's heading title>`, the title after any
running count, in any case, and its day on a line
`#approval_walk_item_first_entered YYYY-MM-DD`, which CLOSE and the
APPROVAL-WALK-WAITING-ITEM-COLD-READ-FAST-READ step write right under the
heading, with today's date, into each such item that has none. Both steps
refuse, writing nothing, when such an item has no category tag on a line that
opens with one, more than one, or one not in WALK_CATEGORIES; a waits-on title
no other item heading has; a first-entered date not written YYYY-MM-DD; or
when such items wait on each other in a circle. Only a line CLOSE
writes records anything: a line for an answer that took effect, for answers to
parts, for --moved-on-no-decision, for --already-decided or for --moved-on
decides its items; a line for a
deferral defers its items once, and a line for a deferral that takes an item
out of the walk because it stood just before the summary item defers its
items twice. Every other line records nothing, whatever it
says, an agent's note included, so that a note such as `Items 3 to 5 revised
(item 3 is the change he approved today)` leaves items 3 to 5 waiting; CHECK's
answer lines and CLOSE's held-answer lines record nothing either.
CLOSE refuses, writing nothing, when a line after the
last answer line already opens with the last answer line's item and a colon, as
every line close writes for an answer does: that answer was closed already, and
no check has run since. When the `#next_to_present` line names other items than
the answer line, a new item a finding raised is waiting: the answer is recorded
as held until the user answers the new item, and the `#next_to_present` line is
written again, unchanged, as the minutes' last line. With
--hold-answer-until-new-item-answered, CLOSE first numbers the unnumbered item
right after the answered item's heading, as it numbers the next item, and
holds the answer for it the same way, its `#next_to_present` line naming it;
when the heading right after is not an unnumbered item's, or there is none,
or when that item waits on an item still to come, an unshown one, the summary
item or a numbered item the minutes do not decide, CLOSE refuses, writing
nothing. When CLOSE later records
the new item approved, disapproved or already decided, it also writes the
already-decided line, with the same outcome, for each item a held-answer line
holds for it that no close line decides yet; after a deferral, a move on or
answers to parts, the held item stays waiting, so the walk comes back to it.
When the new item has sub-steps, and the minutes decide every sub-step so that
the new item counts as approved or disapproved, the first CLOSE that finds the
new item so decided, and does not itself record a new hold, writes the
already-decided line, with that outcome, for the held item, whichever item that
CLOSE itself records.
When it holds or defers the answer, it prints the lines the agent's next
message must include, the status lines among them. When an item waits, it
prints the command that gives that item its cold-read-fast-read before it is
presented.

READ AHEAD. When CLOSE names a next item, it also starts the cold-read-fast-read
of the item the walk would present after that one, found as CLOSE finds the
next item, with the next item counted as decided, in a detached process of its
own session that close does not wait for; and it tells the agent to run
APPROVAL-WALK-WAITING-ITEM-COLD-READ-FAST-READ, below, before presenting the
next item. That step starts the same read ahead, so a retried step or a
successor agent-session starts it too; a text whose read was started or written
before, whatever its outcome, is not read ahead again, so a failed read ahead is
never retried. The read ahead is a guess: when the walk presents another item
next, or the item's text changes before it is shown, the read is only left
unused; when it cannot be started, for example because the walk-document has two
headings for that item, close and the step print one line saying so and why,
and go on. The last item has no item after it, so no read ahead
starts while it is shown, and a close that writes `none, closed` starts none.
CLOSE names item 1 only when the walk comes round to it again, so no read ahead
covers item 1's first showing: the walk-me-through skill's cold-read-fast-read
of the whole walk before item 1 covers it. Item 2's read is run by the step after item 1's close,
since no read ahead was started while item 1 was shown.

APPROVAL-WALK-WAITING-ITEM-COLD-READ-FAST-READ gives the item the
`#next_to_present` line names its cold-read-fast-read, as its text stands: the
item's lines in the walk-document, heading and fenced code included, keyed by
the sha256 of that text unchanged, whitespace included. It first refuses,
as CHECK does and before it starts any read, an item with a `#new` or
`#new_if_d` mark whose text would not be read whole; then it refuses, also
before any read, an item whose text up to its first `###` sub-step, or one of
whose `###` sub-steps, holds more than 500 words, counting every run of
characters between spaces that holds a letter or a digit, on every line but
those opening `#approval_walk_item_`. When the line names one `##` item
whose `###` sub-step headings hold no running count, and none of its
sub-steps has one, the step first writes `Item K.1 of M: `, `Item K.2 of M: `
and so on into them, K the item's number and M its heading's, leaving the
headings of its Withdrawn versions as they are, and starts again; unnumbered,
the sub-steps would be read as the item's own lines, so one answer would
decide every one of them. A sub-step that the count's four words take over
the limit is refused with its heading numbered. Then, for an item that is to be shown, it
refuses, before any read, an item whose text states the
current status of something outside the walk, such as an agent-seat offline,
`claude` logged out, a machine down or work on hold, as
nn-systems/general-tools/agent-text-possibly-stale-system-status-claim-phrases-match-common.py
finds such claims, the list the Stop hook
scripts/agent-reply-possibly-stale-system-status-claim-recheck-reminder-hook.py
uses too, unless --possibly-stale-system-status-claims-rechecked says which
commands the agent ran, and when, to recheck them; the step then prints that
value beside the claims when it hands the item over, and repeats the flag in
every command it prints. An empty value is refused. When the line names one item that has
numbered sub-steps, such as `### Item 3.1 of 9`, the walk-minutes do not all
decide, the step then adds a `#next_to_present` line naming the first of them
the walk-minutes do not decide, since the user is shown such an item one sub-step at a time, and
reads that sub-step as this paragraph says. A read of that key
that wrote its report is used, a read ahead included; one a read-ahead worker
still runs is waited for, for as long as the worker's process lives, since the
fast read ends its own run with timeouts of its own; otherwise the step runs the
read itself, saying why when a read ahead of the same text failed or its worker
ended without writing its outcome. A read ahead that fails, or never ends, so
costs at most the wait for one more read, and never lets the item be shown
unread. A read the step runs itself that fails prints its FAILED line, says not
to present the item yet and how to run the step again, and exits 1.

For a waiting item that asks a decision, the step first prints the rows of the
no-answer table the item could settle by, each offered only at the ratings of
the case against that its row of the table allows: each row
whose evidence passes, with its command, and each row that fails only because an
evidence line is missing, naming the line to add and the command to run after
adding it, and each row that fails only because an evidence line it has is
malformed, naming the line to correct, rather than to add, and the command to
run after correcting it. A row whose check cannot run is reported and not
offered.

The step, in both forms, reads no item and does not say to present it when
the waiting item is one item that asks a decision, a line holding
"Recommendation:", and its first `#case_against` line rates the case against
none, since the no-answer table settles such an item without showing
it: the step prints that the item is not to be shown and the `check
--not-asked none` command that settles it, and exits 0. It reads and presents
the item as usual when the item's `#not_asked_touches` line names a file the
instruction-file guard protects, which `check --not-asked none` refuses, and
when the minutes' last answer line, not yet closed, already settles the item
as `not asked, case against none`, since the agent then shows it only because
the advisor objected or the advisor call failed.

With --after-fixes-reread-only-when-facts-change, which the agent gives after
applying a read's findings to the item, a text with no read of its own is
compared with the text of the item's latest read that wrote its report. When
the change touches no fact, the step runs no read and says so; otherwise it
reads the item, listing the facts touched. The words of the two texts are
matched by difflib, and a word changed, added or removed is a fact when it holds
a digit or a backquote; is a Markdown link or holds an autolink or `://`;
ends in a file extension, a dot then a letter and at most four more letters or
digits, unless it is a letter abbreviation such as `e.g.`; or, without the
punctuation around it and a trailing `/`, is a path `git ls-files` lists in the
checkout, a directory holding one, or the file name of one. The change also
touches a fact when the text from "Recommendation:" or "The alternative:" to the
end of its line, or a `#case_against` line, differs. When `git ls-files` fails,
every changed word counts as a fact, so the item is read. Since the comparison
is always with the latest text read, wording fixes each let pass cannot add up
to a changed fact unread.

FINDING OUTCOMES. The step hands the item over, printing the line that tells
the agent to present it, only when the report of the read it uses, the item's
latest read of its current text, has no finding without a recorded outcome,
as nn-systems/cold-read/cold-read-fast-read-report-findings-parse-and-finding-outcomes-check-common.py finds
findings and reads the outcomes file in the report's cold-read-record. A read
the step finds or runs is that read; with
--after-fixes-reread-only-when-facts-change and no fact touched, it is the
item's latest read that wrote its report. Otherwise the step lists the
findings, prints the cold-read-fast-read.py command that records an outcome for
each, naming the record, and tells the agent to run the step again, with
--after-fixes-reread-only-when-facts-change, once the outcomes are recorded,
and exits 1. When the report or its outcomes file cannot be read, the step
says so, with what to do, such as deleting that read's `<key>-outcome.json` so
that the step reads the item again when the record is gone, and exits 1. The
step exits 0 only when it hands the
item over. CHECK's reads of the texts an answer adds need no outcomes, and it
prints no such command.

USER'S EARLIER WORDS. For an item that is to be shown, the step then runs
walk-me-through-approval-walk-item-title-search-user-messages-in-session-dialogs-and-lines-in-walk-minutes-print.py
once, giving it the title of each heading that names a waiting item, in
the closing line's form too when that differs, as when the title holds a
link, each with the numbers of the waiting items its heading names; a lone waiting item's search
also gives the title of each earlier text of it read, which the next
paragraph finds, and a Withdrawn heading carries no title. It prints what that program prints right after its first line, which
names the read's report: each message the user typed
in an agent-session whose saved dialog names a title, after the agent message
it answers, and each walk-minutes line naming one, each with its file and line.
When the search fails, the step refuses, before any read, printing what the
search said, and exits 1; any exit of the search but its found and nothing-found
exits is a failure. The step saves what the search prints, a search with no
hits too, once it has written it out, in
`docs/walk/title-search-cache/<walk name>-item-<N>-<agent-session id>.md`, the
cache format's number and the titles and numbers searched for as a JSON list on its first line, the agent-session id
being $CLAUDE_CODE_SESSION_ID. A later run for the item in the same
agent-session prints only a line naming that file, unless the file is missing
or the item's titles differ from the saved ones; then it searches, prints and
saves again. When the file cannot be written, or the agent-session id is not
set, the step prints the search in full with a line saying why it was not
saved. walk-files-ship.py does not ship this directory.

Before it reads, the step keeps each earlier version of the item: each text of
the item that a read wrote its report for, oldest first, goes below the item's
live version, after the versions kept there already and before the next item,
under `#### Withdrawn version <n> of item <N>`, n one more than the Withdrawn
headings there that name the item, and the step prints a line for each. A text
is the item's when it was read under the item's number, whatever M; a read
ahead of an unnumbered item is the item's once a read step uses it for the
item, as its text stands, and until then whatever number close expected to
give it, only when its title, the heading's text after the running count, is
the item's title and no other item's. A read outcome written before outcomes
said whether their number was expected counts as such a read ahead. A text is
kept from its first line that is not blank, its indentation and all, so an
indented code block stays code. A text is left out when, without its
heading line and with its whitespace runs squeezed, it is empty, is the live
version's text, or is already below the live version, as an agent may have
kept it by hand. So every text a fast read read, a text the agent then changed
to apply that read's findings included, stays in the walk-document, except a
read ahead no read step used whose item another item now shares a title with;
the walk finder reads an item only up to its first Withdrawn heading. An item
whose heading names other items too, or a `#next_to_present` line naming
several items, keeps none. When the copy `<key>.md` of a text read under the
item's number is missing, the step refuses, writing nothing and reading
nothing, and says where the read's cold-read-record keeps its own copy.

FRESH-AGENT REWRITE. After keeping the earlier versions, the step counts the
revisions of the item's proposed text: the `#new` texts of the live versions of
the whole item and all its sub-steps, sorted, so that a split into sub-steps
that moves a text unchanged is no revision, are compared with those the step
saw last, and each change counts one; the count and the last texts are kept in
`item-<whole number>-proposed-text-revisions.json` in the directory below. A
step that sees no `#new` text counts nothing and keeps the last texts. When the
count reaches 3 and the waiting item, or sub-step, holds a `#new` text, the step
reads nothing and hands nothing over: it prints that the item's proposed text
has been revised three times and a brief for a fresh-agent, built from the
walk-minutes lines that hold the user's words and name the item, one of its
sub-steps, its title, or an item whose held answer raised it, as a
held-answer line from close records, and from the link targets of the item's
live versions,
a link into the Mac's mount of ned-box's home given with its path on ned-box
too, and holding no version of the item's text. The brief tells the
fresh-agent to write the item's text, with no heading line, to
`item-<number>-fresh-agent-rewrite.md` in that directory, and the step says to
run it again with --approval-walk-item-fresh-agent-rewrite-file naming that
file, and exits 1. A run with that flag refuses, writing nothing, a file that
cannot be read, is empty, or holds a Markdown heading or an
`#approval_walk_item_` line, a waiting item whose heading names other items
too, and a result in which the walk-document would hold other items, or the
withdrawn version's heading would not read as a heading, as an unclosed code
fence in the file makes it; otherwise, in one write, it puts the file's text in
place of the waiting item's text below its heading, a setext heading's
underline included, and the `#approval_walk_item_` lines right under it, and
keeps the replaced text below as a withdrawn version; it then starts the count
again from the new texts, and goes on as
the step does for any item; a later refusal of the new text leaves it in
place, to be fixed and read as any revision. A count file that cannot be read
stops the step with exit 1, naming the file to delete.

Each text read is kept in the directory
`docs/walk/<walk name>-item-cold-read-fast-read-review-status-per-text-hash/`,
beside the walk-minutes: `<key>.md` holds the text, the one an
--after-fixes-reread-only-when-facts-change step compares with;
`<key>-outcome.json` the read's outcome, done with its report and the fast
read's notes or failed with its FAILED line, with the item and the time it
ended; `<key>-started.json` the read-ahead worker's pid; and `<key>.log` the
worker's output. docs/walk/ is gitignored, and nn-systems/skills/walk-me-through/walk-files-ship.py ships
only the walk's own files, not this directory: each read's cold-read-record
keeps its own copy of the text read. The step
approval-walk-item-cold-read-fast-read-review-background-worker is that
detached read-ahead worker, which only close and the step above start.

No open approval-walk, or an item the walk-minutes or the walk-document do not
let the program find, is a failure: one line on stderr, exit 1.

Tool-messages-to-agent follow
docs/nedsnodes-wiki/nedsnodes-how-to-write-a-tool-message-to-agent-such-as-a-hook-refusal-or-script-error.md.
"""
import argparse
import collections
import contextlib
import datetime
import difflib
import fnmatch
import functools
import hashlib
import importlib.util
import json
import os
import re
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import urllib.parse
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPOSITORY_TOP = HERE.parents[2]
WALK_FINDER_FILE = HERE / "walk-me-through-approval-walk-minutes-and-walk-document-item-finder-common.py"
FAST_READ_PROGRAM = REPOSITORY_TOP / "nn-systems" / "cold-read" / "cold-read-fast-read.py"
FAST_READ_WITHOUT_QUESTION_4_OPTION = "--without-question-4"
RECORD_SHIPPER_FILE = REPOSITORY_TOP / "nn-systems" / "cold-read" / "cold-read-record-ship.py"
RECORD_NAMES_FILE = REPOSITORY_TOP / "nn-systems" / "cold-read" / "cold-read-record-names-common.py"
FINDING_OUTCOMES_COMMON_FILE = (REPOSITORY_TOP / "nn-systems" / "cold-read"
                                / "cold-read-fast-read-report-findings-parse-and-finding-outcomes-check-common.py")
TITLE_SEARCH_PROGRAM = HERE / "walk-me-through-approval-walk-item-title-search-user-messages-in-session-dialogs-and-lines-in-walk-minutes-print.py"
PATH_CONSTANTS_FILE = (REPOSITORY_TOP / "nn-systems" / "general-tools"
                       / "ned-box-home-directory-and-its-mac-mount-point-path-constants-common.py")
COUNTS_LOG_FILE_NAME = "walk-me-through-answer-added-texts-cold-read-fast-read-already-done-or-had-to-run-counts-per-check.tsv"
RECORDS_DIRECTORY_NAME = "cold-read-records"
PROGRAM = "walk-me-through-answer-added-texts-cold-read-fast-read-check-and-close"

def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@functools.cache
def load_walk_finder():
    return load_module("walk_me_through_approval_walk_minutes_and_walk_document_item_finder_common",
                       WALK_FINDER_FILE)


NEW_MARK, NEW_IF_D_MARK = "#new", "#new_if_d"
QUOTE_PAIRS = (('"', '"'), ("“", "”"), ("'", "'"))
FENCE_DELIMITER = re.compile(r"^\s*(?:>\s?)*\s*(?:`{3,}|~{3,})")
QUOTATION_LINE = re.compile(r"^\s*>")
QUOTATION_MARKERS = re.compile(r"^\s*(?:>\s?)*")
ANSWER_LINE = re.compile(r"^(?P<item>items? .+?): (?P<settled>the user answered|settled without asking the user,|"
                         r"shown to the user,) "
                         r"(?P<answered>.+?)(?: #approved_(?:obvious|after_advisor)#?)?(?: #case_against_[a-z_]+#?)? "
                         r"\([^)]*\)(?: in his words \".*\")?, which makes (?:its change\. Fast reads:|no change\.)$",
                         re.I)
# A marker is read with or without the closing `#` a hashtag takes.
MARKER_END = r"#?(?=[*_`]*(?:[:\s]|$))"
# Any list or quotation marks, then any emphasis or code marks, ahead of a marker; the list and quotation mark rule is
# the walk finder's, which the `#new` mark pattern is built from too, so every marker line takes the same list and
# quotation marks; only that rule is shared, and each marker keeps its own emphasis rule.
LINE_OPENING_MARKERS = rf"^\s*{load_walk_finder().MARKDOWN_LINE_OPENING_LIST_OR_QUOTATION_MARK_PATTERN_TEXT}*[*_`]*"
CASE_AGAINST_LINE = re.compile(rf"{LINE_OPENING_MARKERS}#case_against{MARKER_END}[*_`]*[:\s]*(.*)$")
CASE_AGAINST_RATING = re.compile(r"(very strong|none|weak|medium|strong)\b", re.I)
CASE_AGAINST_HASHTAG = " #case_against_{rating}"
NOT_ASKED_RATINGS = ("none", "weak")
NOT_ASKED_WEAK_CASE_AGAINST_THAT_SETTLES = ("weak with a case against that names only cost, or only that the change "
                                            "alters text the user approved word for word on an earlier date")
NOT_ASKED_RATED_NONE = "none"
NOT_ASKED_RATED_WEAK = "weak"
NOT_ASKED_COST_GROUND = "cost"
NOT_ASKED_EARLIER_APPROVAL_GROUND = "the user's earlier word-for-word approval of the text the change alters"
NOT_ASKED_EITHER_GROUND = f"one of these two alone: {NOT_ASKED_COST_GROUND}, or {NOT_ASKED_EARLIER_APPROVAL_GROUND}"
INSTRUCTION_FILE_GUARD_FILE = REPOSITORY_TOP / ".claude" / "guard-hooks" / "instruction-file-guard.py"
SYSTEM_GLOSSARIES_LISTED_FILE = REPOSITORY_TOP / "scripts" / "system-glossaries-listed-on-the-project-glossary-test.py"
OPTION_NUMBERS = (2, 3)
EVIDENCE_LINE = re.compile(LINE_OPENING_MARKERS + r"(#not_asked_(?:touches|test|source|unused|rename|glossary_term|hashtag_marker|search))"
                           rf"{MARKER_END}[*_`]*[:\s]*(.*)$")
TOUCHES, TEST, SOURCE, UNUSED, RENAME, GLOSSARY_TERM, ADDED_HASHTAG_MARKER, SEARCH = (
    f"#not_asked_{name}" for name in ("touches", "test", "source", "unused", "rename", "glossary_term", "hashtag_marker",
                                      "search"))
NotAskedEvidence = collections.namedtuple("NotAskedEvidence",
                                          "value rating found touched tests lines marks top item")
# unchecked: what the agent judges after settling by the row, when it differs from NOT_ASKED_UNCHECKED.
NoAnswerCase = collections.namedtuple("NoAnswerCase",
                                      "value label meaning ratings needed checks evidence ground flag unchecked",
                                      defaults=(None,))


class MissingEvidenceLine(str):
    """A problem that adding an evidence line to the item would cure, as against one the item's change has."""


class MalformedEvidenceLine(str):
    """A problem that correcting an evidence line the item already has would cure; adding a second line would not,
    since `check` still reads the first."""


def rating_and_needed_lines_problems(found):
    rating, case = found.rating, no_answer_case(found.value)
    problems = [] if rating in NOT_ASKED_RATINGS else [NOT_ASKED_RATING_PROBLEM.format(rating=rating)]
    for marker in case.needed:
        if not words(found.found[marker]):
            problems.append(MissingEvidenceLine(NOT_ASKED_NO_LINE_PROBLEM.format(marker=marker,
                                                                                 why=NOT_ASKED_WHY[marker])))
    return problems


def no_kind_problems(found):
    problems = []
    if found.rating not in NOT_ASKED_RATINGS:
        problems.append(NOT_ASKED_NOT_RATED_NONE_PROBLEM.format(rating=found.rating))
    # An empty touches line is a change that touches no file; only a missing line is refused.
    if TOUCHES not in found.found:
        problems.append(MissingEvidenceLine(NOT_ASKED_NO_LINE_PROBLEM.format(marker=TOUCHES,
                                                                             why=NOT_ASKED_WHY[TOUCHES])))
    for path in found.touched:
        if not (found.top / path).exists():
            problems.append(NOT_ASKED_MISSING_PATH_PROBLEM.format(marker=TOUCHES, path=path, top=found.top))
    for path in guarded_paths(found.top, found.touched):
        if found.rating != NOT_ASKED_RATED_WEAK:  # pragma: no mutate, rating is a rating word and weak sorts after the others, so `<` acts as `!=`
            problems.append(NOT_ASKED_GUARDED_FILE_PROBLEM.format(marker=TOUCHES, path=path))
        elif path.endswith(".md"):
            problems.append(NOT_ASKED_WEAK_GUARDED_MARKDOWN_PROBLEM.format(marker=TOUCHES, path=path))
    return problems


def has_new_text_problems(found):
    return [] if proposed_texts(found.marks, {NEW_MARK}) else [MissingEvidenceLine(NOT_ASKED_NO_NEW_TEXT_PROBLEM)]


def adds_nothing_problems(found):
    # A `#new_if_d` text is what the alternative would add, so it stays; a `#new` text is what approving adds.
    return [NOT_ASKED_ADDS_NOTHING_NEW_TEXT_PROBLEM] if proposed_texts(found.marks, {NEW_MARK}) else []


def touched_files_exist_problems(found):
    return [NOT_ASKED_MISSING_PATH_PROBLEM.format(marker=TOUCHES, path=path, top=found.top)
            for path in found.touched if not (found.top / path).exists()]


def code_fix_files_problems(found):
    # A code fix may add the test that shows it; any other new file is an addition the user sees.
    problems = [NOT_ASKED_NEW_FILE_PROBLEM.format(marker=TOUCHES, path=path, top=found.top)
                for path in found.touched if not (found.top / path).exists() and path not in found.tests]
    for path in found.tests:
        if "test" not in Path(path).name or not ((found.top / path).is_file() or path in found.touched):
            problems.append(NOT_ASKED_NOT_A_TEST_PROBLEM.format(marker=TEST, path=path, top=found.top))
    return problems


def removal_problems(found):
    problems = []
    unused = words(found.found[UNUSED])
    # Without a touches line, which rating_and_needed_lines_problems reports as missing, every file that still
    # names the removed thing would count against it; the item then lacks only that line.
    for word in unused if found.touched else ():
        others = sorted(files_naming(found.top, word, found.item, found.value) - set(found.touched))
        if others:
            problems.append(NOT_ASKED_STILL_USED_PROBLEM.format(word=word, marker=UNUSED, files=", ".join(others),
                                                               touches=TOUCHES))
    not_markdown = [path for path in found.touched if not path.endswith(".md")]
    if not unused and not_markdown:
        problems.append(MissingEvidenceLine(NOT_ASKED_NOT_MARKDOWN_PROBLEM.format(
            marker=UNUSED, touches=TOUCHES, paths=", ".join(not_markdown))))
    return problems


def rename_problems(found):
    problems = []
    for value in found.found[RENAME]:
        names = rename_names(value)
        if len(names) != 2:
            problems.append(NOT_ASKED_RENAME_SHAPE_PROBLEM.format(marker=RENAME, value=value))
            continue
        old, new = names
        if not glossary_entry_files(found.top, new, found.item, found.value):
            problems.append(NOT_ASKED_NOT_IN_GLOSSARY_PROBLEM.format(new=new, pattern=GLOSSARY_FILES))
        others = (sorted(files_naming(found.top, old, found.item, found.value) - set(found.touched))
                  if found.touched else [])
        if others:
            problems.append(NOT_ASKED_STILL_USED_PROBLEM.format(word=old, marker=RENAME, files=", ".join(others),
                                                               touches=TOUCHES))
    return problems


def term_or_marker_problems(found):
    return glossary_term_or_marker_problems(found.found, found.touched, found.top, found.item)


def system_glossary_problems(found):
    return not_system_glossary_problems(found.touched, found.top, found.item)


def dropped_proposal_search_problems(found):
    """Return why an item that drops a proposed check cannot settle on its `#not_asked_search` line: the line must
    be the SEARCH_LINE fields, with a window of at least SEARCH_WINDOW_DAYS ending yesterday or today and a count
    of 0 cases; and a dropped proposal adds no `#new` text."""
    problems = [NOT_ASKED_DROPPED_PROPOSAL_NEW_TEXT_PROBLEM] if proposed_texts(found.marks, {NEW_MARK}) else []
    values = found.found[SEARCH]
    if not values:
        return problems + [MissingEvidenceLine(NOT_ASKED_NO_LINE_PROBLEM.format(marker=SEARCH, why=NOT_ASKED_WHY[SEARCH]))]
    today = datetime.datetime.now(datetime.timezone.utc).date()
    yesterday = today - datetime.timedelta(days=1)
    for value in values:
        fields = SEARCH_LINE.fullmatch(value.strip())
        if not fields:
            problems.append(MalformedEvidenceLine(NOT_ASKED_SEARCH_SHAPE_PROBLEM.format(marker=SEARCH, value=value)))
            continue
        try:
            first, last = (datetime.date.fromisoformat(day) for day in fields.group(1, 2))
        except ValueError:
            problems.append(MalformedEvidenceLine(NOT_ASKED_SEARCH_SHAPE_PROBLEM.format(marker=SEARCH, value=value)))
            continue
        if (last - first).days < SEARCH_WINDOW_DAYS:
            problems.append(NOT_ASKED_SEARCH_WINDOW_SHORT_PROBLEM.format(marker=SEARCH, first=first, last=last,
                                                                         days=SEARCH_WINDOW_DAYS))
        if last < yesterday:
            problems.append(NOT_ASKED_SEARCH_WINDOW_OLD_PROBLEM.format(marker=SEARCH, last=last))
        if last > today:
            problems.append(NOT_ASKED_SEARCH_WINDOW_FUTURE_PROBLEM.format(marker=SEARCH, last=last))
        if int(fields[3]):
            problems.append(NOT_ASKED_SEARCH_FOUND_CASES_PROBLEM.format(marker=SEARCH, count=fields[3]))
    return problems


NOT_ASKED_FLAG, ALREADY_DECIDED_FLAG = "--not-asked", "--already-decided"
NOT_ASKED_ANY_RATING = (NOT_ASKED_RATED_NONE, NOT_ASKED_RATED_WEAK)
NOT_ASKED_ADDS_NOTHING = "adds-nothing"
NOT_ASKED_ADDS_NOTHING_LABEL = "adds nothing"
EVERY_RATING = ("none", "weak", "medium", "strong", "very strong")
DROPPED_PROPOSAL_VALUE = "proposed-check-dropped-search-found-no-case"
DROPPED_PROPOSAL_GROUND = "that the problem the dropped proposal guarded against may still come, at any rating"
HANDOFF_INTERNALS_VALUE = "handoff-internals"
HANDOFF_INTERNALS_CITATION = ("the user-ruling on the handoff's internals in nn-systems/handoff/handoff.system.design.md, "
                              "section User-rulings")
HANDOFF_INTERNALS_NAMED = re.compile(r"handoff|initial-agent-instructions", re.I)
# The one list of what needs no answer from the user: a new kind is one new row here.
NO_ANSWER_CASES = (
    NoAnswerCase(1, "kind 1", "text changed to state a cited ruling, what merged code does, or a fact a shown command "
                 "checked, adding no step, check or limiting word its source lacks",
                 NOT_ASKED_ANY_RATING, (TOUCHES, SOURCE),
                 (rating_and_needed_lines_problems, has_new_text_problems, touched_files_exist_problems),
                 "touches, a source and a `#new` text; every touched file exists", None, NOT_ASKED_FLAG),
    NoAnswerCase(2, "kind 2", "a code fix that a test shows failing before and passing after, adding no hook, job, "
                 "setting, retry or fallback and leaving failure handling as it is",
                 NOT_ASKED_ANY_RATING, (TOUCHES, TEST), (rating_and_needed_lines_problems, code_fix_files_problems),
                 "touches and a test; every touched file exists except that test", None, NOT_ASKED_FLAG),
    NoAnswerCase(3, "kind 3", "removing what a program shows nothing uses, or dates, citations and history from "
                 "standing instructions",
                 NOT_ASKED_ANY_RATING, (TOUCHES,),
                 (rating_and_needed_lines_problems, touched_files_exist_problems, removal_problems),
                 "touches; each `#not_asked_unused` name appears in no file outside the touched ones and docs/walk/, "
                 "or, with no such line, every touched file is Markdown", None, NOT_ASKED_FLAG),
    NoAnswerCase(4, "kind 4", "a rename to a name a glossary lists, with every reference updated",
                 NOT_ASKED_ANY_RATING, (TOUCHES, RENAME),
                 (rating_and_needed_lines_problems, touched_files_exist_problems, rename_problems),
                 "touches and a rename line; the new name is the term of a glossary entry, and the old name is in no "
                 "file outside the touched ones and docs/walk/", None, NOT_ASKED_FLAG),
    NoAnswerCase(5, "kind 5", "carrying out a cited ruling by filing its GHI, handing an item to its owner or, for "
                 "merge-lane-2, merging a pull request its review passed",
                 NOT_ASKED_ANY_RATING, (SOURCE,), (rating_and_needed_lines_problems,), "a source", None,
                 NOT_ASKED_FLAG),
    NoAnswerCase(6, "kind 6", "in prose, a word or phrase replaced by the term the project glossary or a system "
                 "glossary lists for what the word or phrase means there, or a hashtag marker no program reads added "
                 "to a line that already says what the marker marks",
                 NOT_ASKED_ANY_RATING, (TOUCHES,),
                 (rating_and_needed_lines_problems, touched_files_exist_problems, term_or_marker_problems),
                 "touches and a term or a marker line; every touched file is Markdown and no `*-glossary.md`, each "
                 "term is a glossary entry's term, and no program reads each marker", None, NOT_ASKED_FLAG),
    NoAnswerCase(7, "kind 7", "adding or changing an entry of a system glossary, which lists the system-terms of one "
                 "system",
                 NOT_ASKED_ANY_RATING, (TOUCHES,),
                 (rating_and_needed_lines_problems, touched_files_exist_problems, system_glossary_problems),
                 "touches; every touched file is a `*-glossary.md` git tracks, other than the project glossary",
                 None, NOT_ASKED_FLAG),
    NoAnswerCase(8, "kind 8", "a simplification or deletion that leaves unchanged what the text tells its reader to do, "
                 "or what the code does",
                 NOT_ASKED_ANY_RATING, (TOUCHES,), (rating_and_needed_lines_problems, touched_files_exist_problems),
                 "touches; every touched file exists", None, NOT_ASKED_FLAG),
    NoAnswerCase(NOT_ASKED_ADDS_NOTHING, NOT_ASKED_ADDS_NOTHING_LABEL,
                 "an item whose recommendation adds and changes nothing, such as leaving out a definition, a check or "
                 "a step that its alternative would add, whatever its case against is rated",
                 EVERY_RATING, (), (adds_nothing_problems,), "no `#new` text; any rating", None, NOT_ASKED_FLAG,
                 "whether the item's recommendation adds and changes nothing"),
    NoAnswerCase(NOT_ASKED_RATED_NONE, "case against none",
                 "an item of none of these kinds whose case against is rated none, unless it adds words the user has "
                 "not approved to a file the instruction-file guard protects",
                 (NOT_ASKED_RATED_NONE,), (TOUCHES,), (no_kind_problems,),
                 "a touches line, which may be empty for a change that touches no file; no touched file is one the "
                 "instruction-file guard protects", None, NOT_ASKED_FLAG),
    # Walk-minutes already written hold the cost label, so its text stays as it is.
    NoAnswerCase("weak-cost-only", "case against weak, cost only",
                 "an item of none of these kinds whose case against is rated weak and names only cost, such as code "
                 "to write or time spent",
                 (NOT_ASKED_RATED_WEAK,), (TOUCHES,), (no_kind_problems,),
                 "a touches line, which may be empty; no touched Markdown file is one the instruction-file guard "
                 "protects", NOT_ASKED_COST_GROUND, NOT_ASKED_FLAG),
    NoAnswerCase("weak-alters-earlier-approved-text-only", "case against weak, alters earlier approved text only",
                 "an item of none of these kinds whose case against is rated weak and names only that the change "
                 "alters text the user approved word for word on an earlier date",
                 (NOT_ASKED_RATED_WEAK,), (TOUCHES,), (no_kind_problems,),
                 "a touches line, which may be empty; no touched Markdown file is one the instruction-file guard "
                 "protects", NOT_ASKED_EARLIER_APPROVAL_GROUND, NOT_ASKED_FLAG),
    # CLAUDE.md's guard rule: a proposal whose search of the last 30 days found no case is dropped without the user,
    # whatever its case against's rating.
    NoAnswerCase(DROPPED_PROPOSAL_VALUE, "proposed check dropped, search found no case",
                 "an item that recommends dropping a proposed check, test, guard, refusal or hook, because a search of "
                 "the last 30 days, of every place the problem would leave a trace, found no case of it",
                 EVERY_RATING, (SEARCH,), (dropped_proposal_search_problems,),
                 "a search line giving a window of at least 30 days that ends no earlier than yesterday, 0 cases, "
                 "and the places searched; no `#new` text", None, NOT_ASKED_FLAG),
    NoAnswerCase(HANDOFF_INTERNALS_VALUE, "the handoff's own internals",
                 "an item about the handoff's own internals, such as what the handoff-supervisor, the session-handoff "
                 "file or the initial-agent-instructions do, when it only removes or shortens something and its case "
                 "against is rated none or weak; show it when it adds a step, check, retry or file to a "
                 "session-handoff, makes a session-handoff slower, can lose work, changes a design or decision of the "
                 "user's, or has a case against rated medium or above",
                 NOT_ASKED_ANY_RATING, (), (), "a citation of " + HANDOFF_INTERNALS_CITATION, None,
                 ALREADY_DECIDED_FLAG),
)
NOT_ASKED_KINDS = tuple(case.value for case in NO_ANSWER_CASES if isinstance(case.value, int))
NOT_ASKED_NO_KIND_VALUES = tuple(case.value for case in NO_ANSWER_CASES
                                 if isinstance(case.value, str) and case.flag == NOT_ASKED_FLAG)
NOT_ASKED_WEAK_GROUND_LABELS = {case.value: case.label for case in NO_ANSWER_CASES if case.ground}
# What a weak case against may name for the item to settle, as the refusal and the judgement lines say it.
NOT_ASKED_GROUNDS = {case.value: case.ground for case in NO_ANSWER_CASES if case.ground}
NOT_ASKED_KIND_RANGE = f"{NOT_ASKED_KINDS[0]} to {NOT_ASKED_KINDS[-1]}"
NO_ANSWER_TABLE_RULES = (
    "An item needs no answer from the user, and is not shown, when its change and its case against fit a row below.",
    f"Kinds {NOT_ASKED_KIND_RANGE} need a case against rated none, or rated weak and naming only cost, such as code to "
    "write or time spent, or only that the change alters text the user approved word for word on an earlier date; the "
    "item says which kind, with its evidence. Whether the instruction-file guard protects the file, and how long the "
    "text is, do not matter for these kinds.",
    "An item that recommends dropping a proposed check, test, guard, refusal or hook needs no answer, whatever its "
    "case against's rating, when a search of the last 30 days, of every place the problem would leave a trace, found "
    "no case of it.",
    "Every other item is shown, including any rated above none that adds a rule, instruction sentence, check, hook, "
    "job, glossary term, design choice, setting or recurring expense.",
    "Before settling an item, run its row's command and ask the advisor whether a later ruling or another open item "
    "overtakes it; if the program refuses, the advisor objects or the advisor call fails, show the item.",
    "The minutes record a settled item as <accepted>, with \"not asked\" and its kind number, or \"case against none\"; "
    "it keeps its number and its place in the count M, and its change is made with the walk's other approved changes.",
)


def not_asked_grounds(value):
    """What the case against may name for the item to settle as the row `value`, as refusals and judgement lines
    say it."""
    if value == DROPPED_PROPOSAL_VALUE:
        return DROPPED_PROPOSAL_GROUND
    return NOT_ASKED_GROUNDS.get(value, NOT_ASKED_EITHER_GROUND)


def no_answer_case(value):
    return next(case for case in NO_ANSWER_CASES if case.value == value)


def no_answer_case_words(case):
    """The check flags that settle an item by this row, as in `--not-asked 4`."""
    return (case.flag, HANDOFF_INTERNALS_CITATION if case.flag == ALREADY_DECIDED_FLAG else str(case.value))


def no_answer_table_text():
    """The no-answer table as `--help` prints it."""
    rows = [f"  {' '.join(no_answer_case_words(case)[:1])} {case.value}: {case.meaning}. Evidence: {case.evidence}."
            if case.flag == NOT_ASKED_FLAG else
            f"  {case.flag} \"{HANDOFF_INTERNALS_CITATION}\": {case.meaning}. Evidence: {case.evidence}."
            for case in NO_ANSWER_CASES]
    return "\n".join(["no-answer table:", *NO_ANSWER_TABLE_RULES, *rows])


HASHTAG_MARKER = re.compile(r"#[A-Za-z0-9_-]+")
HASHTAG_MARKER_CLOSING_HASH = re.compile(r"^(#[A-Za-z0-9_-]+)#$")
NOT_MARKDOWN_FILES = ":(exclude)*.md"
GLOSSARY_FILES = "*-glossary.md"
STATUS_LINE_PREFIX = "- "
OBVIOUS_HASHTAG = " #approved_obvious"
AFTER_ADVISOR_HASHTAG = " #approved_after_advisor"
APPROVED, DISAPPROVED, DEFERRED, MOVED_ON = "approved", "disapproved", "deferred", "moved on, no decision"
ALREADY_DECIDED_PREFIX, MOVED_ON_PREFIX = "already decided by ", "moved on, no decision: "
NAVIGATION_WORD_ALONE = re.compile(r"^(?:next|n|continue|go)[.!]*$", re.I)
OUTCOMES = {APPROVED: "<accepted>", DISAPPROVED: "<rejected>"}
PART_WORDS = {"A": APPROVED, "AO": APPROVED + OBVIOUS_HASHTAG, "D": DISAPPROVED}
PART_ARGUMENT = re.compile(r"^(\d+)=(ao|a|d)$", re.I)
# ANSWER_LINE's `answered` loses a last part's hashtag, so close reads each part's word on its own.
PART_IN_ANSWER = re.compile(r"\bpart (\d+) ((?:dis)?approved)\b")
PART_ARGUMENT_PROBLEM = ("`{value}` is not a part's answer: give the part's number, `=`, then A, AO or D, as in "
                         "`1=A`; a part takes no Z, so a deferral is given to the whole item with --deferred")
PART_REPEATED = ("nothing written: --part-answer gives {parts} more than one answer.\n"
                 "Run check again giving each part's number once, with the letter the user gave that part.")
ALREADY_DECIDED_WHOLE_ANSWERS = ("A", "D")
ALREADY_DECIDED_ANSWERS_PROBLEM = (
    "nothing written: --already-decided was given {answers} after USER_RULING, which is not an answer a ruling "
    "gives: after USER_RULING it takes nothing or A, for a ruling that decides the item as it recommends, or D, "
    "for one that decides it against its recommendation, for its alternative.\n"
    "Run check again with the answer the ruling gives.")

NO_PROPOSED_TEXT = "no proposed text marked"
STATUS_ALREADY_DONE = "`{mark}` text {number}, \"{excerpt}\": fast read already done ({record})."
STATUS_HAD_TO_BE_RUN = "`{mark}` text {number}, \"{excerpt}\": fast read had to be run ({record})."
STATUS_FAST_READ_NOTE = " The fast read also said: {note}"
# The fast read reports these on stderr after writing its report; an unshipped record also makes it exit 1.
FAST_READ_RECORD_NOT_SHIPPED_MARKERS = ("cold-read-fast-read: record: FAILED",
                                        "cold-read-fast-read: record: REFUSED")
FAST_READ_NOTE_MARKERS = FAST_READ_RECORD_NOT_SHIPPED_MARKERS + ("#cold_read_target_changed_during_run",)
HOLD_ANSWER_FLAG = "--hold-answer-until-new-item-answered"
CHECK_JUDGEMENT_LINES = (
    "Read the fast-read report of each text above whose status line says \"fast read had to be run\".",
    "If a finding holds and changes how a text is understood but not what the item decides, "
    "apply it to that text's marked line in the walk-document {document}.",
    "If a finding would change what the item decides, write that change as a new item right "
    "after {item} in the walk-document, headed `## <the point>` with no number, and give the close step below "
    "the flag `" + HOLD_ANSWER_FLAG + "`: it numbers the new item, holds {item}'s answer until the user answers "
    "it, and says when to present it.",
)
CHECK_CLOSE_LINE = "Then run `{command}` and do what it prints."
BUMP_NOT_FOUND = (
    "check --bump refused: no item heading in the walk-document {document} has the title `{title}`, so nothing "
    "was bumped and nothing was written.\n"
    "Run check --bump again with the title of an item not yet shown, its heading's text after `## `, as in "
    "`{command}`.")
BUMP_ALREADY_SHOWN = (
    "check --bump refused: `{heading}` in the walk-document {document} has already been shown, and {state}, so "
    "nothing was bumped and nothing was written.\n"
    "Bump only an item not yet shown. To show a shown item again, end your message with its closing line.")
BUMP_ALREADY_SHOWN_DECIDED = "the minutes record it as decided"
BUMP_ALREADY_SHOWN_WAITING = "it is not decided yet"
BUMP_ANSWER_NOT_CLOSED = (
    "check --bump refused: the walk-minutes {minutes} hold the user's answer to {item}, which check wrote and close "
    "has not yet recorded, so nothing was bumped and nothing was written. If the bump went ahead, close would "
    "then take that answer as the answer to the item you bump as well.\n"
    "Run `{close_command}` first and do what it prints, except reading and presenting the item "
    "it names next: in place of that, run `{bump_command}` and do what it prints, so that the item the user "
    "bumped is shown next.")
BUMP_MINUTES = "Bumped by the user: {bumped} is shown next, before {waiting}, which waits again after it.{words}"
BUMP_MINUTES_LINE = re.compile(r"^Bumped by the user: (?P<bumped>items? .+?) is shown next, before "
                               r"(?P<waiting>items? .+?), which waits again after it\.")
BUMP_DONE = (
    "{bumped} is now the waiting item, and {waiting} comes right after it.\n"
    "Then run `{command}`, which gives {bumped} its cold-read-fast-read, and do what it prints before you "
    "present it.")
COUNTS_NOT_LOGGED = (
    "The minutes record the answer, but the fast-read counts were not logged to {log}: {error}.",
    "Include this line in your next message to the user, and carry on as the lines above say.",
)
WALK_DOCUMENT_COPIES_DIRECTORY_IN_LOG_STORE = "walk-document-copies"
WALK_DOCUMENT_COPIES_KEPT = 20
WALK_DOCUMENT_COPY_STAMP_FORMAT = "%Y-%m-%dT%H-%M-%S.%fZ"
WALK_DOCUMENT_COPY_NAME = re.compile(r"(\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2}\.\d{6}Z)(-[0-9a-f]{16})?\.md")
WALK_DOCUMENT_COPY_NOT_SAVED = (
    "FAILED: no timestamped copy of the walk-document {document} was saved on ned-box: {error}.\n"
    "This step's own work is not affected by that failure.\n"
    "Go on with the walk: the next run of this program tries the copy again.\n"
    "If the failure repeats, tell the user, because until a copy lands a bad edit to the walk-document cannot be "
    "undone from one.")
WALK_DOCUMENT_COPIES_NOT_PRUNED = (
    "FAILED: the timestamped copy of the walk-document {document} is saved on ned-box, but its oldest copies were "
    "not pruned: {error}.\n"
    "This step's own work is not affected by that failure.\n"
    "Go on with the walk: the next run of this program finishes the prune.\n"
    "If the failure repeats, tell the user, because the copies folder then grows past {kept} copies.")
LOG_STORE_UNREACHABLE = ("this machine reaches the log-store at neither {paths}, so its cold-read-records were "
                         "not searched either")
RECORDS_NOT_SHIPPED = (
    "The minutes record the answer, but the fast read of `{mark}` text {number} did not ship its record: {note}",
    "The record stays at {record}; once ned-box can be reached, run `{ship_command}`.",
    "If the line above says REFUSED, first rename {record} with a -2 suffix, or the next number not taken, "
    "and ship the renamed directory instead.",
    "Include these lines in your next message to the user, and carry on as the lines above say.",
)
FAST_READ_FAILED_LINES = (
    "The item stays waiting: the minutes do not record the answer.",
    "Tell the user the line above, and ask whether to run `{command}` again or "
    "answer the item another way.",
)
STOP_SIGNAL_SCRATCH_NOT_REMOVED_LINES = (
    "{program}: a {signal} stopped it while a cold-read-fast-read was running, and the scratch directory "
    "{directory}, which held the text sent to that cold-read-fast-read, could not be removed: {error}\n"
    "Run `chmod -R u+rwX {quoted_directory} && rm -rf {quoted_directory}`, because nothing else removes that "
    "directory, and the disk it is on can fill.\n"
    "{after_removal}")
STOP_SIGNAL_CHECK_AFTER_REMOVAL = ("The walk-minutes do not record the user's answer: then run `{command}` again, "
                                   "with the same answer, so that they record it.")
STOP_SIGNAL_READ_STEP_AFTER_REMOVAL = ("{item} has had no cold-read-fast-read of its text as it stands: then run "
                                       "`{command}` again, and present {item} only after it.")
STOP_SIGNAL_READ_AHEAD_AFTER_REMOVAL = ("The read step finds this read ended without an outcome, and runs the "
                                        "cold-read-fast-read itself.")
CHECK_MINUTES = ("{item}: the user answered {answered}{hashtag}{rating} ({date_and_time}){words}, which makes its change. "
                 "Fast reads:")
CHECK_NOT_ASKED_MINUTES = ("{item}: settled without asking the user, {answered}{rating} ({date_and_time}), which makes "
                           "its change. Fast reads:")
CHECK_DEFERRED_MINUTES = ("{item}: the user answered {answered}{rating} ({date_and_time}){words}, which makes no "
                          "change.")
USER_WORDS = ' in his words "{words}"'
CHECK_MOVED_ON_MINUTES = ("{item}: settled without asking the user, {answered}{rating} ({date_and_time}), which makes "
                          "no change.")
CHECK_MOVED_ON_SHOWN_PREFIX = "shown to the user,"
CHECK_MOVED_ON_SHOWN_MINUTES = ("{item}: " + CHECK_MOVED_ON_SHOWN_PREFIX + " {answered}{rating} ({date_and_time}), "
                                "which makes no change.")
CLOSE_TOOK_EFFECT_MINUTES = "{item}: {answered}; every text the change adds has had a fast read. {outcome}"
CLOSE_PARTS_TOOK_EFFECT_MINUTES = "{item}: {parts}; every text the change adds has had a fast read."
CLOSE_DEFERRED_MINUTES = "{item}: deferred; it moves to just before the summary item. <open>"
# No fast-read clause in these two: the one-time conversion of older walk-minutes writes them too, with no fast read.
CLOSE_ALREADY_DECIDED_MINUTES = "{item}: already decided by {ruling}; the walk does not come back to it. {outcome}"
CLOSE_MOVED_ON_MINUTES = ("{item}: moved on, no decision: {reason}; the walk does not come back to it. "
                          "<moved on, no decision>")
CLOSE_MOVED_ON_NO_DECISION_MINUTES = "{item}: moved on; the item asked for no decision. <moved on, no decision>"
CLOSE_DEFERRED_AGAIN_MINUTES = "{item}: deferred a second time, so it leaves the walk and stays open. <open>"
CLOSE_DEFERRED_JUST_BEFORE_SUMMARY_MINUTES = ("{item}: deferred while it stood just before the summary item, so it "
                                              "leaves the walk and stays open. <open>")
MORE_THAN_ONE_UNCLOSED_APPROVAL_WALK = (
    "nothing written: more than one approval-walk is open or paused in {directory}, so this program cannot tell "
    "which approval-walk the user's answer belongs to, and records it in none. A paused approval-walk is one "
    "whose walk-minutes hold an `#approval_walk_paused` line after their last `#next_to_present` line. Their "
    "walk-minutes:\n"
    "{minutes}\n"
    "An agent-seat keeps at most one approval-walk open: a new subject that needs the user's rulings joins the open "
    "approval-walk as one item just after the item waiting for his answer, with sub-items when it needs them.\n"
    "For each of these approval-walks that has no item the user has yet to answer: add the line "
    "`#next_to_present none, closed` as the last line of its walk-minutes.\n"
    "If after that more than one of them still has items the user has yet to answer: keep the approval-walk whose "
    "item your last message to him showed; in its walk-document, move each other approval-walk's unanswered items "
    "into it as items of their own, just after the kept approval-walk's waiting item: first the items that block "
    "work, each prerequisite before the item it blocks; related items next to each other; and older items before "
    "newer ones; and renumber the items after it that he has not yet seen; then close each other approval-walk: add "
    "the line `#next_to_present none, closed` as the last line of its walk-minutes, and run "
    "`nn-systems/skills/walk-me-through/walk-files-ship.py <its name>`.\n"
    "Then run the command you just ran again.\n"
    "From now on, add a new subject that needs the user's rulings to the open approval-walk instead of opening a "
    "second one.")
CHECK_SEVERAL_WAITING = (
    "nothing written: the `#next_to_present` line in {minutes} names more than one item waiting, {item}, "
    "and one check run records one answer for all of them.\n"
    "For each of those items the user has answered, in the order he gave the answers: add the line "
    "`{one_item_line}`, with that item's number, as the minutes' last line, then run check with the flag for "
    "his answer to it, then close.\n"
    "Present the item that `close` names only after the last of those answers is recorded.\n"
    "If he has not answered some of those items, ask him to answer them.")
CLOSE_ALREADY_RECORDED = (
    "nothing written: the last answer line in {minutes}, for {item}, is already recorded by an earlier close, "
    "so no check has run since then.\n"
    "Run `{command}` first, with the flag for the user's answer as `--help` lists it, then close.\n"
    "If check failed, fix what it printed before running close.")
CLOSE_HELD_MINUTES = "{item}: answer held: {new_item}, raised by a fast-read finding, waits for the user's answer. <open>"
# Every line close writes to record an answer; only these mark the answer closed.
CLOSE_RECORD_TEMPLATES = (CLOSE_TOOK_EFFECT_MINUTES, CLOSE_PARTS_TOOK_EFFECT_MINUTES, CLOSE_DEFERRED_MINUTES,
                          CLOSE_ALREADY_DECIDED_MINUTES, CLOSE_MOVED_ON_MINUTES, CLOSE_MOVED_ON_NO_DECISION_MINUTES,
                          CLOSE_DEFERRED_AGAIN_MINUTES, CLOSE_DEFERRED_JUST_BEFORE_SUMMARY_MINUTES,
                          CLOSE_HELD_MINUTES)
HELD_ANSWER_LINE = re.compile(r"^(items?\s[^:]*): answer held: (items?\s.+?), raised by a fast-read finding", re.I)
CLOSE_TOOK_EFFECT_LINES = (
    "{item}'s answer is recorded in the minutes, and its change may now be made.",
)
CLOSE_DEFERRED_LINES = (
    "{item} is deferred, and the minutes record it; it comes back just before the summary item.",
    "Your next message must include these lines, as they are:",
)
CLOSE_MOVED_ON_LINES = (
    "{item} asked for no decision, and the minutes record that the user moved on from it.",
)
CLOSE_MOVED_ON_SHOWN_LINES = (
    "{item} was shown to the user, and the minutes record that the walk moved on from it with no decision.",
)
CLOSE_DEFERRED_OUT_OF_THE_WALK_LINES = (
    "Add it to your task list if it is not already a task.",
    "If a commit on your branch already makes the change this item asks about, undo that change in a new commit "
    "before the pull request, and say in the task that it was undone.",
    "Your next message must include these lines, as they are:",
)
CLOSE_DEFERRED_AGAIN_LINES = (
    "{item} is deferred a second time, so the minutes record it as open and it leaves the walk.",
) + CLOSE_DEFERRED_OUT_OF_THE_WALK_LINES
CLOSE_DEFERRED_JUST_BEFORE_SUMMARY_LINES = (
    "{item} is deferred while it stands just before the summary item, so the minutes record it as open and it "
    "leaves the walk.",
) + CLOSE_DEFERRED_OUT_OF_THE_WALK_LINES
CLOSE_HELD_LINES = (
    "{item}'s answer does not take effect yet: {new_item}, which a fast-read finding raised, waits for the "
    "user's answer, and the minutes record {item}'s answer as held until he answers {new_item}.",
    "Your next message must include these lines, as they are:",
)
CLOSE_TOOK_EFFECT_NEXT = (
    "If the change needs nothing more from the user, such as a text he has not yet seen, start it as the "
    "walk-me-through skill's sentence on ready work says; if it edits a file that work you dispatched "
    "earlier is still editing, start it when that earlier work finishes.",
)
CLOSE_NO_NEXT_ITEM = ("No item is left to present, and the minutes' `#next_to_present` line now reads "
                      "`none, closed`: go on to the walk-me-through skill's closing.")
NEXT_MARKER_LINE = "#next_to_present {value}"
CLOSED_MARKER_VALUE = "none, closed"
PROGRAM_LINE_ITEMS = re.compile(r"^(items?\s[^:]*): ", re.I)


def minutes_time(moment):
    return moment.astimezone(datetime.timezone.utc).strftime("%Y-%m-%d %H:%MZ")


def _one_of(values):
    return "(?:" + "|".join(re.escape(str(value)) for value in values) + ")"


_PART_VALUE = r"part \d+ " + _one_of(f"{word} {outcome}" for word, outcome in OUTCOMES.items())
# The values close fills each placeholder with; {ruling} and {reason} carry the agent's own words, so any text.
PLACEHOLDER_VALUES = {
    "answered": _one_of([APPROVED, DISAPPROVED] + [f"{APPROVED} option {number}" for number in OPTION_NUMBERS]
                        + [f"not asked, {case.label}" for case in NO_ANSWER_CASES if case.flag == NOT_ASKED_FLAG]),
    "outcome": _one_of(OUTCOMES.values()),
    "parts": rf"{_PART_VALUE}(?:, {_PART_VALUE})*",
    "ruling": ".+",
    "reason": ".+",
}


def after_the_items_pattern(template):
    """The part of a minutes line this program writes from template after `{item}: `, as a regular
    expression in which each other placeholder stands only for the values close fills it with."""
    # re.split with a group alternates literal text (even indexes) and placeholder names (odd indexes).
    return re.compile("^" + "".join(PLACEHOLDER_VALUES[piece] if index % 2 else re.escape(piece)
                                    for index, piece in enumerate(re.split(r"\{(\w+)\}",
                                                                           template[len("{item}: "):])))
                      + "$")


DECIDING_LINES = tuple(after_the_items_pattern(template) for template in (
    CLOSE_TOOK_EFFECT_MINUTES, CLOSE_PARTS_TOOK_EFFECT_MINUTES, CLOSE_ALREADY_DECIDED_MINUTES, CLOSE_MOVED_ON_MINUTES,
    CLOSE_MOVED_ON_NO_DECISION_MINUTES))
# The `#ruling_given` word of each of DECIDING_LINES; None where the line's outcome tag gives it.
DECIDING_LINE_WORDS = (None, "part_answers", None, "moved_on", "moved_on")
DEFERRING_LINES = tuple(after_the_items_pattern(template)
                        for template in (CLOSE_DEFERRED_MINUTES, CLOSE_DEFERRED_AGAIN_MINUTES))
# One such line takes its items out of the walk, as two deferral lines do.
DEFERRING_OUT_OF_THE_WALK_LINE = after_the_items_pattern(CLOSE_DEFERRED_JUST_BEFORE_SUMMARY_MINUTES)
# A one-item count as it stands in the heading's own line, after its heading or bold marks.
HEADING_COUNT_IN_LINE = re.compile(r"items?\s+\d+(?:\.\d+)*\s+of\s+\d+\b", re.I)
CLOSE_DEFERRED_HEADING_NOT_NOTED = ("Its heading in {document} names other items too, so it is not given the "
                                    "note {note}.")
SUMMARY_HEADING = re.compile(r"\bof\s+\d+\b[*_\s:.\-\u2013\u2014]*summary\b|^\s*##\s+[*_\s]*summary\b", re.I)
NEWLINE = "\n"
UNNUMBERED_HEADING_PARTS = re.compile(r"^(\s*##[ \t]+)(.*?)(?:[ \t]+#+)?[ \t]*$")
SUB_STEP_HEADING_PARTS = re.compile(r"^(\s*###[ \t]+)(.*?)(?:[ \t]+#+)?[ \t]*$")
# The four categories of section 2 of
# docs/nedsnodes-wiki/queue/nedsnodes-goals-and-philosophy-founding-statement-and-agent-working-principles.md,
# in the order their items are shown.
WALK_CATEGORIES = ("must_fix_now", "fix_next", "fix_during_maintenance", "file_an_improvement_feature_or_change")
WALK_CATEGORY_TAG = "#approval_walk_item_in_category_"
WALK_WAITS_ON_TAG = "#approval_walk_item_waits_on"
WALK_FIRST_ENTERED_TAG = "#approval_walk_item_first_entered"
WALK_CATEGORY_LINE = re.compile(LINE_OPENING_MARKERS + re.escape(WALK_CATEGORY_TAG))
# Words joined by single underscores, so the closing `_` or `__` of underscore emphasis is not read into the tag.
WALK_CATEGORY_TAGS_IN_LINE = re.compile(re.escape(WALK_CATEGORY_TAG) + r"(?:[^\W_]+(?:_[^\W_]+)*)?")
WALK_WAITS_ON_LINE = re.compile(LINE_OPENING_MARKERS + re.escape(WALK_WAITS_ON_TAG) + MARKER_END
                                + r"[*_`]*[:\s]*(.*?)[*_`\s]*$")
WALK_FIRST_ENTERED_LINE = re.compile(LINE_OPENING_MARKERS + re.escape(WALK_FIRST_ENTERED_TAG) + MARKER_END
                                     + r"[*_`]*[:\s]*(.*?)[*_`\s]*$")
# A marked text ends above the first of these lines, because this program reads each on its own; a line opening
# with any other hashtag, such as a prose `#root_cause`, is part of the text.
MARKER_LINES_READ_ON_THEIR_OWN = (load_walk_finder().APPROVAL_WALK_ITEM_NEW_TEXT_MARK_LINE_PATTERN, CASE_AGAINST_LINE,
                                  EVIDENCE_LINE, WALK_CATEGORY_LINE, WALK_WAITS_ON_LINE, WALK_FIRST_ENTERED_LINE)
WALK_ORDER_REFUSED = (
    "nothing written: {problem}\n"
    "Every item of the walk-document not yet shown to the user, headed `## <the point>` with no number, needs "
    "exactly one category line, so that this program can choose which of them he sees next: the items each "
    "waits on first, then by category, then by the day each first entered a walk, earlier first, then in "
    "walk-document order. "
    "The categories are the four of section 2 of "
    "docs/nedsnodes-wiki/queue/nedsnodes-goals-and-philosophy-founding-statement-and-agent-working-principles.md, "
    "shown in this order:\n"
    + "\n".join(f"  `{WALK_CATEGORY_TAG}{category}`" for category in WALK_CATEGORIES) + "\n"
    "If an item has no category line, more than one category tag, or a tag not in this list: leave it exactly one "
    "tag from this list, the one for how soon its work must happen, on a line of its own under its heading.\n"
    f"If an item must not be shown before another item: give it a line `{WALK_WAITS_ON_TAG} <the other item's "
    "title>`, the other item's heading without its `##` and any `Item N of M: `, one line for each item it waits "
    "on; an item already decided counts as done. If items wait on each other in a circle, take out the waits-on "
    "line that is not a real prerequisite.\n"
    "Then run `{command}` again.\n"
    "From now on, write the category line, and a waits-on line for each item it waits on, into every item when you "
    "add it to a walk-document.")
CATEGORY_MISSING = "{item} has no `" + WALK_CATEGORY_TAG + "<category>` line."
CATEGORY_DOUBLED = "{item} has more than one category tag: {tags}."
CATEGORY_UNKNOWN = "{item} has the category tag `{tag}`, which is not one of the four categories."
WAITS_ON_UNKNOWN = "{item} waits on `{title}`, which is the title of no other item heading."
WAITS_ON_CIRCLE = "the items {items} wait on each other in a circle, so none of them can come first."
FIRST_ENTERED_UNREADABLE = (
    "{item} has the line `{line}`, whose date is not a date written YYYY-MM-DD. This program writes a line "
    f"`{WALK_FIRST_ENTERED_TAG} YYYY-MM-DD` on the day it first finds the item; write in it the day the item first "
    "entered an approval-walk, or delete the line, and this program writes today's date.")
NUMBERED_HEADING = "{marks}Item {number} of {total}: {title}"
NO_UNNUMBERED_ITEM_AFTER = (
    "nothing written: close was given " + HOLD_ANSWER_FLAG + ", but in {document} the heading right after "
    "{item}'s is {found}, not a new item's heading `## <the point>` with no number.\n"
    "If a fast-read finding would change what {item} decides, write that change as a new item right after "
    "{item}, headed `## <the point>`, then run close with " + HOLD_ANSWER_FLAG + " again.\n"
    "If no finding does, run close without " + HOLD_ANSWER_FLAG + ".")
HELD_NEW_ITEM_WAITS_ON_UNSHOWN = (
    "nothing written: close was given " + HOLD_ANSWER_FLAG + ", but in {document} the new item right after "
    "{item}, {new_item}, waits on {waited_on}, which the user has not ruled on yet. The new item is shown "
    "next, to settle {item}, so it cannot come after the item it waits on.\n"
    "Take the line `" + WALK_WAITS_ON_TAG + " <title>` that names {waited_on} out of {new_item}. If {new_item} "
    "depends on what {waited_on} would decide, add to {new_item} one sentence saying what {waited_on} proposes, "
    "as background, since the user rules on {new_item} first. "
    "Then run close with " + HOLD_ANSWER_FLAG + " again.")
GATHERING_WOULD_LOSE_AN_ITEM = (
    "walk-document not changed: close recorded the answer in {minutes}, but moving the items not yet shown "
    "together in {document} would have left fewer items than it found, so close wrote neither the walk-document "
    "nor a new `#next_to_present` line. This is a defect in this program.\n"
    "Tell the user this line, and send it to reboot-test with SendMessage, so that the program is fixed.\n"
    "Until then, show the user the next item yourself, and write its `#next_to_present` line into the minutes "
    "by hand.")
CLOSE_HELD_NEXT = ("Then run `{command}`, which gives {new_item} its cold-read-fast-read, do what it prints, and "
                   "present {new_item}. When the close step records the user's approval or disapproval of "
                   "{new_item}, it records the same outcome for {item}; after a deferral, a move on or answers to "
                   "parts, {item} stays waiting and the walk comes back to it.")
CLOSE_HELD_DECIDED = "{held}, whose answer was held for {item}, is recorded with {item}'s outcome."
HELD_RULING = "the user's answer to {new_item}, for which its answer was held"
CASE_AGAINST_MISSING = (
    "nothing written: {item} in {document} has no `#case_against` line, and every answer records the item's "
    "case-against rating beside it in the minutes, so the ratings can later be compared with the user's answers.\n"
    "Add one line to {item}, just before its recommendation, that opens with `#case_against` and your rating of "
    "its strongest case against, none, weak, medium, strong or very strong, as in "
    "`#case_against weak: the fix costs an hour of fast reads.` or `#case_against none.`; the rating is yours, so "
    "the user need not see the item again for it.\n"
    "Then run `{command}` again.\n"
    "From now on, write the `#case_against` line into each item before you show it.")
CASE_AGAINST_UNRATED = (
    "nothing written: the `#case_against` line of {item} in {document}, `{line}`, does not open with a rating, "
    "so no rating can be recorded beside the answer.\n"
    "Change that line so that `#case_against` is followed by one of none, weak, medium, strong or very strong, "
    "as in `#case_against weak: the fix costs an hour of fast reads.`, then run `{command}` again.")
USER_WORDS_MISSING = (
    "nothing written: check was given no --user-reply-as-typed, so the walk-minutes would record the answer "
    "without the reply it came from, and the walk-me-through skill records the user's own words beside the answer "
    "they count as.\n"
    "Run `{command} --user-reply-as-typed <his reply>` with the user's reply exactly as he "
    "typed it, quoted for the shell, as in `--user-reply-as-typed 'a but trivial'`.")
USER_WORDS_NOT_ASKED = (
    "nothing written: --user-reply-as-typed was given with {flag}, but an item settled without asking the "
    "user has no reply of his to record.\n"
    "If the user did answer the item, run check with the flag for his answer instead of {flag}.\n"
    "Otherwise run check again without --user-reply-as-typed.")
NAVIGATION_WORD_REFUSED = (
    "nothing written: the user's reply \"{words}\" is a navigation word alone, which does not approve, disapprove "
    "or defer {item}, so check does not record it as {answered}.\n"
    "If {item} ends with a recommendation, ask the user to answer it with A, AO, Aa, D or Z, because the "
    "walk-me-through skill lets a navigation word alone advance only when no recommendation is outstanding.\n"
    "If {item} asks for no decision, such as a summary item, run `{command}`, then close.")
MOVED_ON_NO_DECISION_REFUSED = (
    "nothing written: {item} recommends \"{recommendation}\", so it asks for a decision, and --moved-on-no-decision "
    "records only a move on from an item that asks for none.\n"
    "If the user's reply already answers {item}, do not ask him again: run check with the flag for his answer, "
    "as below.\n"
    "If it does not, ask him to answer {item}, because the walk-me-through skill lets the walk move on from an "
    "item only once its recommendation is answered.\n"
    "The check command for each answer, with REPLY replaced by his reply as he typed it:\n{commands}")
MOVED_ON_NO_DECISION_HIDDEN_RECOMMENDATION = (
    "nothing written: {item} in the walk-document {document} shows no recommendation as this program cuts HTML "
    "comments, but recommends \"{recommendation}\" once a `<!--` inside an HTML tag opens no comment, as when the "
    "`<!--` in an attribute, such as `<div title=\"<!--\">`, hides the text after it. So check "
    "cannot tell whether {item} asks for a decision.\n"
    "If the user is meant to see that recommendation: rewrite each `<!--` in {item} that opens no comment, such as "
    "one in an attribute, as `&lt;!--`, then ask him to answer {item}, because the walk-me-through skill lets "
    "the walk move on from an item only once its recommendation is answered.\n"
    "If the recommendation is a hidden note: put it inside a comment that opens with `<!--` outside any tag and "
    "closes with `-->`, then run `{command}` again.")
MOVED_ON_NO_DECISION_ANSWER_COMMANDS = (
    ("A", ()), ("AO", ("--obvious",)), ("Aa", ("--after-advisor",)), ("D", ("--disapproved",)),
    ("Z", ("--deferred",)))
MOVED_ON_NO_DECISION_ANSWER_LINE = "{answer}: {command} --user-reply-as-typed REPLY"
MOVED_ON_NO_DECISION_OPTION_LINE = ("O{number}, for an item with an \"Option {number}\" paragraph: {command} "
                                    "--user-reply-as-typed REPLY")
MOVED_ON_NO_DECISION_PART_LINE = ("An answer to each part of an item with parts, one flag per part: {command} "
                                  "--user-reply-as-typed REPLY")
MOVED_ON_NO_DECISION_PART_EXAMPLE = ("--part-answer", "1=A", "--part-answer", "2=D")
UNREADABLE_NEW_MARKS = (
    "nothing written: {item} in the walk-document {document} has `#new` or `#new_if_d` marks whose text this "
    "program would not read whole, so an answer that adds such a text would be recorded without that text's "
    "cold-read-fast-read. This program reads a mark's text only from the rest of the mark's own line, outside "
    "fenced or indented code. The marks:\n{problems}\n"
    "Fix the marks from the last listed to the first, so that the line numbers above stay right.\n"
    "For a mark inside fenced or indented code that marks a text an answer adds: delete it, and any lines of its "
    "text, from the code, and write on a line of its own just after the code the line its entry gives after "
    "\"joined onto it:\", or the mark followed by the text you meant.\n"
    "For a mark inside fenced or indented code that is only an example: rewrite that line of the code so that it "
    "does not open with the mark, as in `Example: #new \"<text>\"`.\n"
    "For a mark whose text runs onto the lines below it: write the line its entry gives after \"joined onto it:\" "
    "in place of the mark's line, or the mark followed by the text you meant, and delete the lines its text ran "
    "onto.\n"
    "For a mark whose line holds `<!--`: move any HTML comment on that line to a line of its own, and if the "
    "mark's text holds `<!--`, write it there in words, as in `an HTML comment opening`.\n"
    "For a mark with no text after it: if a text was meant, write it after the mark, on the mark's line, and "
    "delete any lines below that held it; if none was meant, delete the mark.\n"
    "Then run `{command}` again.\n"
    "From now on, write every `#new` or `#new_if_d` text on one line, after its mark, outside fenced or indented "
    "code.")
UNREADABLE_BARE = "- line {line}: `{mark}` has no text after it on its line."
UNREADABLE_FENCED = "- line {line}: `{mark}` is inside fenced or indented code, where no mark's text is read."
UNREADABLE_RUN_ON = "- line {line}: the text of `{mark}` runs onto {below} right below it, where it is not read."
UNREADABLE_COMMENT_CUT = ("- line {line}: the line of `{mark}` holds `<!--`, so this program cuts text from it as an "
                          "HTML comment, even inside a code span, and would not read the line as written.")
UNREADABLE_JOINED = " The mark's line with its text joined onto it: {mark} {text}"
NOT_ASKED_REFUSED = (
    "nothing written: {item} cannot be settled without asking the user as {label}, because:\n{problems}\n"
    "If the item does not fit {label}, or the case against names anything besides {grounds}, present {item} to the "
    "user as "
    "usual, then run check with the flag for his answer, as `--help` lists it.\n"
    "If the item fits and only its evidence lines are missing or wrong, fix them in {document} and run "
    "`{command}` again.")
NOT_ASKED_WEAK_GROUND_NOT_NAMED = (
    "nothing written: {item}'s `#case_against` line rates the case against weak, and `--not-asked none` is only for "
    "an item of no kind rated none; for one rated weak, the `--not-asked` value says which of the weak cases "
    "against that settle an item it is, so that the minutes record why the item settled.\n"
    "This is not a refusal of {item}; run check again with the value that fits:\n"
    "{weak_ground_choices}\n"
    "If the case against names anything else, present {item} to the user as usual, then run check with the flag "
    "for his answer, as `--help` lists it.\n"
    "From now on, give one of these values, not `none`, for an item of no kind rated weak.")
NOT_ASKED_WEAK_GROUND_CHOICE = "If the case against names only {ground}: `{command}`"
NOT_ASKED_WEAK_GROUND_FOR_RATED_NONE = (
    "nothing written: {item}'s `#case_against` line rates the case against none, and `--not-asked {kind}` is only "
    "for an item of no kind rated weak.\n"
    "This is not a refusal of {item}; run `{command}`, the value for an item of no "
    "kind rated none.")
NOT_ASKED_RATING_PROBLEM = ("- its `#case_against` line rates the case against {rating}; only an item rated none, "
                            "or " + NOT_ASKED_WEAK_CASE_AGAINST_THAT_SETTLES + ", settles without the user.")
NOT_ASKED_NO_LINE_PROBLEM = "- it has no `{marker}` line; {why}"
NOT_ASKED_KINDS_NAMED = f"none of the kinds {NOT_ASKED_KIND_RANGE} that `--help` lists under `--not-asked`"
NOT_ASKED_NOT_RATED_NONE_PROBLEM = ("- its `#case_against` line rates the case against {rating}; an item of "
                                    + NOT_ASKED_KINDS_NAMED + " settles without the user only when its case "
                                    "against is rated none, or " + NOT_ASKED_WEAK_CASE_AGAINST_THAT_SETTLES + ".")
NOT_ASKED_WEAK_GUARDED_MARKDOWN_PROBLEM = (
    "- `{marker}` names {path}, a Markdown file the instruction-file guard protects; this item is of "
    + NOT_ASKED_KINDS_NAMED + " and rated weak, and it changes such a file, so it is shown to the user.")
NOT_ASKED_GUARDED_FILE_PROBLEM = ("- `{marker}` names {path}, which the instruction-file guard protects; an item "
                                  "that adds words the user has not approved to such a file is shown to him, and "
                                  "one whose words a ruling of his gives settles as kind 1.")
NOT_ASKED_MISSING_PATH_PROBLEM = "- `{marker}` names {path}, which is not in the checkout {top}."
NOT_ASKED_NEW_FILE_PROBLEM = ("- `{marker}` names {path}, which is not in the checkout {top}; a code fix that "
                              "settles without the user adds no file but a test.")
NOT_ASKED_NOT_A_TEST_PROBLEM = "- `{marker}` names {path}, which is not a test file in the checkout {top}."
NOT_ASKED_NO_NEW_TEXT_PROBLEM = "- it has no `#new` line holding the changed text."
NOT_ASKED_STILL_USED_PROBLEM = ("- `{word}`, named on its `{marker}` line, is still named in {files}, which "
                                "its `{touches}` line does not list.")
NOT_ASKED_NOT_MARKDOWN_PROBLEM = ("- it has no `{marker}` line, and `{touches}` names {paths}, which are not "
                                  "Markdown standing instructions; name each thing removed on a `{marker}` line.")
NOT_ASKED_RENAME_SHAPE_PROBLEM = ("- its `{marker}` line `{value}` does not give the old name, then the new name, "
                                  "each in backquotes when it holds a space.")
NOT_ASKED_NOT_IN_GLOSSARY_PROBLEM = ("- the new name `{new}` is the term of no entry, a line opening `- **{new}**` "
                                     "or `- **{new} (aka ...)**`, in a glossary file ({pattern}) in the checkout.")
NOT_ASKED_NO_TERM_OR_MARKER_PROBLEM = ("- it has neither a `{term}` line nor a `{marker}` line; name on a `{term}` line "
                                       "each glossary term the change puts in, and on a `{marker}` line each hashtag "
                                       "marker it adds.")
NOT_ASKED_GLOSSARY_OR_NOT_MARKDOWN_PROBLEM = (
    "- `{touches}` names {path}, which is not Markdown prose outside a glossary; kind 6 changes no code and no "
    "glossary, because a glossary entry decides what a term means.")
NOT_ASKED_NOT_SYSTEM_GLOSSARY_PROBLEM = (
    "- `{touches}` names {path}, which is not a system glossary, a " + GLOSSARY_FILES + " file git tracks in the "
    "checkout {top} other than the project glossary {project_glossary}; kind 7 changes only entries of system "
    "glossaries.")
NOT_ASKED_TERM_NOT_IN_GLOSSARY_PROBLEM = ("- the term `{term}` is the term of no entry, a line opening `- **{term}**` "
                                          "or `- **{term} (aka ...)**`, in a glossary file ({pattern}) in the "
                                          "checkout.")
NOT_ASKED_MARKER_SHAPE_PROBLEM = ("- `{value}` on its `{marker}` line is not a hashtag marker, `#` then letters, "
                                  "digits, `_` or `-`.")
NOT_ASKED_MARKER_READ_PROBLEM = ("- the marker `{value}` is in {files}, which are not Markdown; a marker a program, "
                                 "a test or a setting reads changes what the program does, so the user sees it.")
NOT_ASKED_SEARCH_SHAPE_PROBLEM = ("- its `{marker}` line `{value}` is not the search's first and last day, as "
                                  "YYYY-MM-DD, the count of cases found, as in `0 cases`, and the places searched "
                                  "after `places:`, in the form `YYYY-MM-DD to YYYY-MM-DD, 0 cases, places: ...`.")
NOT_ASKED_SEARCH_WINDOW_SHORT_PROBLEM = ("- its `{marker}` line searched {first} to {last}, shorter than the {days} "
                                         "days the guard rule in CLAUDE.md asks for.")
NOT_ASKED_SEARCH_WINDOW_OLD_PROBLEM = ("- its `{marker}` line's search ended on {last}, before yesterday; search again "
                                       "up to today, since a case may have come since.")
NOT_ASKED_SEARCH_WINDOW_FUTURE_PROBLEM = ("- its `{marker}` line's search ends on {last}, after today (UTC); give "
                                          "the last day actually searched.")
NOT_ASKED_SEARCH_FOUND_CASES_PROBLEM = ("- its `{marker}` line found {count} cases; a case found is the failure that "
                                        "has happened, so the proposal is shown to the user with those cases cited.")
NOT_ASKED_ADDS_NOTHING_NEW_TEXT_PROBLEM = ("- it has a `#new` line, which A would add, so its recommendation adds "
                                          "something and it is shown.")
NOT_ASKED_DROPPED_PROPOSAL_NEW_TEXT_PROBLEM = ("- it has a `#new` line, which A would add; an item that drops a "
                                               "proposal adds no text, so it recommends something else and is shown.")
# Fixed fields, not prose: a tally phrase such as `0 cases in total; will look in ...` holds an `in` that names no
# place searched, so the places are only what follows `places:`.
SEARCH_LINE = re.compile(r"(\d{4}-\d{2}-\d{2}) to (\d{4}-\d{2}-\d{2}), (\d+) cases?, places: *(.*[A-Za-z].*)",
                         re.I)
SEARCH_WINDOW_DAYS = 30
NOT_ASKED_WHY = {
    TOUCHES: "list on it every file the change edits or deletes, separated by spaces.",
    TEST: "name on it the test that fails before the fix and passes after it.",
    SOURCE: "cite on it the ruling, the merged code or the command that shows the fact.",
    RENAME: "give on it the old name, then the new name, each in backquotes when it holds a space.",
    SEARCH: ("give on it the search's first and last day, the count of cases found and the places searched, as in "
             "`#not_asked_search 2026-10-26 to 2026-11-25, 0 cases, places: the log-store's session dialogs and user "
             "messages and the commits on main`."),
}
NOT_ASKED_JUDGEMENT_LINES = (
    "{item} is recorded as settled without asking the user, {label}; the program checked only what code can.",
    "Before you run close, ask the advisor whether a later ruling or another open item overtakes {item}, and judge "
    "what the program could not, such as {unchecked}.",
    "If the advisor objects, the advisor call fails, or your judgement is against settling, do not run close: "
    "present {item} to the user and run check with the flag for his answer, as `--help` lists it; that writes a new "
    "answer line, and close records only the last one, so this line is then set aside.",
)
# Code cannot see these in a change, so an item of no kind rated weak leaves them to the agent.
NOT_ASKED_UNCHECKED = "whether the case against names nothing besides {grounds}, and whether a fix matches its design"
# Code cannot tell from the item what was proposed, or where the problem would leave its trace.
NOT_ASKED_DROPPED_PROPOSAL_JUDGEMENT_LINE = (
    "Judge also whether {item} proposes a check, test, guard, refusal or hook and recommends dropping it, and whether "
    "the problem that check guards against would have left a trace in the places its `#not_asked_search` line names. "
    "If {item} drops no such proposal, or the problem would leave no trace there, as for code too new to have run, do "
    "not run close: present {item} to the user.")
NOT_ASKED_WEAK_JUDGEMENT_LINE = (
    "{item} is of " + NOT_ASKED_KINDS_NAMED + " and its case against is rated weak: if its change "
    "widens an agent's permissions, as a settings change can, or turns off a guard, do not run close: present {item} to the user.")
GIT_LS_FILES_GLOSSARIES_FAILED_REASON = (
    "{error}\nThe system glossaries git tracks could not be listed while checking {item}'s evidence.")
GIT_LS_FILES_GLOSSARIES_FAILED = (
    GIT_LS_FILES_GLOSSARIES_FAILED_REASON + "\n"
    "Run `{command}` again once; if it fails the same way, present {item} to the user "
    "and run check with the flag for his answer, as `--help` lists it.")
GIT_GREP_FAILED_REASON = "`git grep` failed with exit {code} in {top} while checking {item}'s evidence: {error}"
GIT_GREP_FAILED = (GIT_GREP_FAILED_REASON + "\n"
                   "Run `{command}` again once; if it fails the same way, "
                   "present {item} to the user and run check with the flag for his answer, as `--help` lists it.")
CLOSE_NOT_SHOWN_LINES = (
    "{item} is recorded in the minutes as settled without being shown to the user.",
)
CLOSE_ALREADY_DECIDED_CHANGE = "Its change may now be made."
CLOSE_ALREADY_DECIDED_AGAINST_CHANGE = ("It is recorded as disapproved: the change its alternative describes may now "
                                        "be made, and the change its recommendation describes may not.")
# Both line formats are agreed with merge-lane-2, whose hold command writes the first into its review and whose
# pull request intake reads the second; change neither without changing those programs.
HELD_ON_RULING_LINE = "#held_on_ruling {walk} item {number}"
RULING_GIVEN_LINE = "#ruling_given {walk} item {number} {word}"
RULING_GIVEN_WORDS = {OUTCOMES[APPROVED]: APPROVED, OUTCOMES[DISAPPROVED]: DISAPPROVED}
RULING_GIVEN_DEFERRED, RULING_GIVEN_MOVED_ON, RULING_GIVEN_PART_ANSWERS = "deferred", "moved_on", "part_answers"
GH_PROGRAM = "gh"
GH_TIMEOUT_SECONDS = 60  # pragma: no mutate, a limit a second longer or shorter behaves the same
HELD_PULL_REQUESTS_LIST = ("pr", "list", "--state", "open", "--limit", "1000", "--json", "number,reviews")
# Reads a review line as pull_requests_held_on does. `gh --jq` runs gojq, whose regular expressions lack some of
# jq's, such as lookahead.
HELD_PULL_REQUESTS_BY_HAND_JQ = ('.[] | select(any(.reviews[].body | split("\\n")[] | gsub("^\\\\s+|\\\\s+$"; ""); '
                                 '. == {line} or . == {closed_form_line})) | .number')
RULING_GIVEN_POSTED = "The ruling on item {number} is posted as `{ruling}` on pull request {pull_request}, held on it."
RULING_GIVEN_LOOKUP_FAILED = (
    "The minutes record the answer to item {number}, but the open pull requests merge-lane-2 holds until that item "
    "is answered could not be looked up, so none of them carries the ruling: `gh pr list` {error}.",
    "Run `{list_command}` once; for each pull request number it prints, run `{comment_command}` with that number in "
    "place of <number>, because merge-lane-2 releases or answers a hold only when it reads that comment.",
    "If that fails too, tell the user: \"merge-lane-2 was not told that item {number} of {walk} is {word}, so the "
    "pull requests held until that ruling stay held; gh failed.\" A subagent passes this to the agent that "
    "dispatched it.",
)
RULING_GIVEN_POST_FAILED = (
    "The minutes record the answer to item {number}, but pull request {pull_request}, which merge-lane-2 holds until "
    "that item is answered, did not get the ruling's comment: `gh pr comment` {error}.",
    "Run `{comment_command}` once, because merge-lane-2 releases or answers the hold only when it reads that comment.",
    "If that fails too, tell the user: \"merge-lane-2 was not told that item {number} of {walk} is {word}, so pull "
    "request {pull_request} stays held; gh failed.\" A subagent passes this to the agent that dispatched it.",
)

WAITING_ITEM_READ_STEP = "approval-walk-waiting-item-cold-read-fast-read"
READ_AHEAD_WORKER_STEP = "approval-walk-item-cold-read-fast-read-review-background-worker"
AFTER_FIXES_FLAG = "--after-fixes-reread-only-when-facts-change"
ITEM_READS_DIRECTORY_SUFFIX = "-item-cold-read-fast-read-review-status-per-text-hash"
READ_DONE, READ_FAILED = "done", "failed"
READ_POLL_SECONDS = 2
FACT_LABELS = ("Recommendation:", "The alternative:")
# Spelled as the short-answer hook's RECOMMENDATION, so the two programs agree on which items hold a recommendation.
AUTOLINK = r"<[A-Za-z][A-Za-z0-9+.-]*:[^>\s]*>"
# A backquoted span, a Markdown link, an autolink, or any other run of non-space characters.
FACT_TOKEN = re.compile(r"`[^`\n]+`|!?\[[^\]\n]*\]\([^)\s]*\)|" + AUTOLINK + r"|\S+")
FILE_EXTENSION_END = re.compile(r"\w\.[A-Za-z][A-Za-z0-9]{0,4}$")
LETTER_ABBREVIATION = re.compile(r"(?:[A-Za-z]\.)+[A-Za-z]?")
TOKEN_EDGE_PUNCTUATION = "\"'“”‘’()[]{}<>*_.,;:!?"
FACTS_LISTED = 8
CLOSE_READ_NEXT_ITEM = ("Then run `{command}`, which gives {next_item}, the item the minutes' `#next_to_present` "
                        "line now names, its cold-read-fast-read, and do what it prints before you present it.")
ITEM_READ_USED = "{item}: its cold-read-fast-read, of its text as it stands, {how}: {report}{notes}"
ITEM_READ_HOW_AHEAD = "was read ahead while the item before it was shown"
ITEM_READ_HOW_ALREADY = "was done earlier"
ITEM_READ_HOW_RUN = "had to be run now{why}"
ITEM_READ_RUN_AHEAD_FAILED = ", because the read started ahead of it failed: {line}"
ITEM_READ_RUN_AHEAD_ENDED = (", because the read started ahead of it ended without writing its outcome; its output "
                             "is in {log}")
ITEM_READ_RUN_FACTS = ", because your changes since its last cold-read-fast-read ({report}) touch {facts}"
ITEM_READ_NOT_RUN = ("{item}: no new cold-read-fast-read: your changes since its last one ({report}) touch no "
                     "number, path, file or program name, link, or line holding \"Recommendation:\", "
                     "\"The alternative:\" or `#case_against`.")
RULING_DAYS_APPLIED = 90
STANDING_DOCUMENT_PLACE_CITED = re.compile(
    r"(?:GHI-MD\s*\d+|[\w./-]*(?:CLAUDE|AGENTS|SKILL)\.md|docs/nedsnodes-wiki/[\w./&-]+|docs/issues/[\w./-]+"
    r"|[\w./-]*design\.md|[\w./-]+-instructions\.md)`?(?:'s)?,?\s+(?:at\s+)?(?:lines?\s+\d+|section\b)")
# A standing document named inside the user's quoted words is not what the citation cites.
QUOTATION = re.compile(r'"[^"]*"|“[^”]*”')
# A date glued to a hyphen, a letter or a slash is part of a name, such as a walk-minutes file's.
RULING_DATE = re.compile(r"(?<![\w./-])(\d{4}-\d\d-\d\d)(?=T\d|[^\w-]|$)")
RULING_TOO_OLD = (
    "nothing written: --already-decided was refused for {item}, because its citation {citation} names no standing "
    "document with a line or section in it, such as `GHI-MD 2118 line 63`, and the earliest date in it, {date}, is "
    "{days} days before today; the walk-me-through skill applies a ruling found only in walk-minutes or a "
    "handoff dialog for {limit} days.\n"
    "If the ruling bears on {item}, quote it in the item with its date, show the item to the user, ask whether the "
    "ruling still holds, and run check with the flag for his answer.\n"
    "If a standing document records the same ruling, run check again citing that document and the line or section "
    "that records it.")
RULING_UNDATED = (
    "nothing written: --already-decided was refused for {item}, because its citation {citation} names no standing "
    "document with a line or section in it, such as `GHI-MD 2118 line 63`, and holds no date written "
    "YYYY-MM-DD outside a name, so it is taken as too old; the walk-me-through skill applies a ruling found only in "
    "walk-minutes or a handoff dialog for {limit} days.\n"
    "If the walk-minutes line or session dialog line that records the ruling holds its date, add that date to the "
    "citation, as in \"(2026-11-20)\", and run check again.\n"
    "If the ruling has no date and bears on {item}, quote it in the item, show the item to the user, ask whether the "
    "ruling still holds, and run check with the flag for his answer.\n"
    "If a standing document records the same ruling, run check again citing that document and the line or section "
    "that records it.")
NOW_OVER_LATER_FLAG = "--now-over-later-already-decided"
NOW_OVER_LATER_USER_RULING_CITATION = (
    "the user-ruling at line 361 of nedlern@ned-box:/home/nedlern/agents/cold-read-improvement/docs/walk/"
    "walk-me-through-skill-refactor-approval-walk-2026-11-02-minutes.md, given with his answer to item 42 on "
    "2026-11-09: \"If the agents recommend now versus later, I'm always for now.\"")
OPTION_LINE = re.compile(LINE_OPENING_MARKERS + r"Option\s+\d")
NOW_OVER_LATER_REFUSED = (
    "nothing written: {item} in {document} was not recorded as already decided by the user-ruling that he is "
    "always for building now when the agents recommend now over later, because that user-ruling settles only an "
    "item whose one choice is now or later, and {item} holds other choices:\n{problems}\n"
    "Present {item} to the user, then run check with the flag for his answer, as `--help` lists it.")
ALREADY_DECIDED_REPEATED = ("--already-decided was given more than once; give it once, with the one ruling that "
                            "decides the item and the answer that ruling gives")
SETTLING_FLAGS = ("--not-asked", NOW_OVER_LATER_FLAG, "--already-decided")
SECOND_SETTLING_REFUSED = (
    "nothing written: {item} was not settled with `{flag}`, because the last answer in {minutes}, to {pending}, has "
    "no close after it, so a settling now could record an item twice, and could reverse what that answer recorded.\n"
    "If that answer settled {pending} without asking the user and {pending} was then shown to him, record his own "
    "answer with one of these, as `--help` lists them:\n{commands}\n"
    "Otherwise run `{close}` and do what it prints.")
NOW_OVER_LATER_PARTS = "- a `Part N.` paragraph, each part answered on its own, on line {lines}"
NOW_OVER_LATER_OPTIONS = "- a line opening `Option N`, another option he can pick, on line {lines}"
NOW_OVER_LATER_NEW_IF_D = "- a `#new_if_d` text, what his disapproval would do instead, on line {lines}"
SHORT_ANSWER_HOOK_FILE = HERE / ("walk-me-through-user-short-answer-to-approval-walk-item-expanded-into-instructions-"
                                 "user-prompt-submit-hook.py")
PRESENT_UNLESS_NOW_OVER_LATER_CLAUSE = (
    ", unless its only choice is whether to build something now or later and it recommends now: then run "
    "`{now_over_later_command}`, then the close command it prints.")
ITEM_READ_LINES = (
    "Read that report and apply each finding that holds to {item} in the walk-document {document}; a finding that "
    "would change what the item decides becomes a new item, numbered as the walk-me-through skill's Re-planning "
    "section says.",
    "If you change {item} after this, run `{command}` and do what it prints; it reads {item} again only when your "
    "changes touch a fact.",
    "Then present {item}{now_over_later_clause}",
)
ITEM_READ_NOT_RUN_NEXT = "Present {item}{now_over_later_clause}"
# The form scripts/agent-seat-due-task-raise-hook.py's parse_prerequisites reads.
WAITING_ON_ITEM_PREREQUISITE_LINE = ("If a task waits on the user's decision on {item}, append this entry to the "
                                     "task's metadata.prerequisites list and give TaskUpdate the whole list, every "
                                     "entry the list holds now kept, because TaskUpdate replaces "
                                     "metadata.prerequisites whole: {entry}")
ITEM_READ_FINDINGS_WITHOUT_OUTCOMES = (
    "{item} is not handed over to be presented yet: its cold-read-fast-read report {report} has findings with no "
    "recorded outcome, {missing} of {count}. The user is shown an item only once each finding of its latest "
    "cold-read-fast-read is recorded as applied or declined, so that how often each question's findings are "
    "applied can be counted. The findings:")
ITEM_READ_FINDING_OUTCOMES_COMMAND_LINES = (
    "After you revise {item}, run the command below, with `{applied}` or `{declined}: <your reason>` in place of each "
    "`{placeholder}`, keeping the single quotes; it refuses a list that leaves out a finding or names one the report "
    "does not have:",
    "{outcomes_command}",
    "Then run `{command}` and do what it prints: it hands {item} over once every finding has its outcome, and reads "
    "{item} again only when your changes touch a fact, in which case the new read's findings need outcomes too.",
)
ITEM_READ_FINDING_OUTCOMES_UNREADABLE = (
    "{item} is not handed over to be presented: whether each finding of its cold-read-fast-read report {report} has "
    "a recorded outcome could not be read ({error}).\n"
    "If {record} is gone: delete {outcome_file}, this program's record of that read, then run `{read_again}`, which "
    "gives {item} a new cold-read-fast-read, and do what it prints.\n"
    "Otherwise fix what the error names, then run `{command}` again.")
ITEM_READ_SUB_STEP_NAMED = (
    "{item} is split into numbered sub-steps, which the user is shown one at a time, so the step added the line "
    "`#next_to_present {sub_step}` to {minutes}, naming the first sub-step of {item} the walk-minutes record no answer "
    "to, and reads {sub_step} instead of {item}.")
WITHDRAWN_VERSION_HEADING = "#### Withdrawn version {version} of item {number}"
NUMBER_PREDICTED = "number_predicted"
# In a read's outcome: the heading its text was kept under, so the text is kept once, whatever is later written
# near that heading.
WALK_ITEM_READ_OUTCOME_WITHDRAWN_VERSION_HEADING_TEXT_KEPT_UNDER_KEY = (
    "walk_item_read_outcome_withdrawn_version_heading_text_kept_under")
# The same key as outcomes written before it was renamed spell it; read so that a text kept then is not kept twice.
WALK_ITEM_READ_OUTCOME_WITHDRAWN_VERSION_HEADING_TEXT_KEPT_UNDER_OLD_KEY = "kept_as_withdrawn_version"
ITEM_NUMBER_PREDICTED_FLAG = "--item-number-predicted"
EARLIER_TEXT_KEPT = ("{item}: its earlier text, which the cold-read-fast-read {report} read, is now kept below its "
                     "live version in {document}, under `{heading}`; leave it there.")
EARLIER_TEXT_KEPT_NOT_RECORDED = (
    "{item}: its earlier texts are kept below its live version in {document}, but {outcome} could not be written to "
    "record that ({error}), so a later read step may keep one again if the kept text is edited. Make {reads} "
    "writable, then run `{command}` again.")
FRESH_AGENT_REWRITE_REPLACED_TEXT_KEPT = ("{item}: its text before the fresh-agent's rewrite is now kept below its live "
                                          "version in {document}, under `{heading}`; leave it there.")
FRESH_AGENT_REWRITE_FLAG = "--approval-walk-item-fresh-agent-rewrite-file"
PROPOSED_TEXT_REVISIONS_BEFORE_FRESH_AGENT_REWRITE = 3
PROPOSED_TEXT_REVISIONS_FILE = "item-{number}-proposed-text-revisions.json"
FRESH_AGENT_REWRITE_FILE = "item-{number}-fresh-agent-rewrite.md"
USER_WORDS_IN_MINUTES_PHRASE = "his words"
MARKDOWN_LINK_TARGET = re.compile(r"\]\(\s*<?([^)\s>]+)>?(?:\s+\"[^\"]*\")?\s*\)|<([A-Za-z][A-Za-z0-9+.-]*:[^>\s]+)>")
PROPOSED_TEXT_REVISIONS_UNREADABLE = (
    "{item} is not read: {path}, this program's count of the revisions of the `#new` lines of item {whole_number} and its "
    "sub-steps, cannot be read ({error}).\n"
    "Delete {path}, which starts the count again from the text as it stands, then run `{command}` again.")
PROPOSED_TEXT_REVISIONS_NOT_WRITTEN = (
    "{item} is not read: {path}, this program's count of the revisions of the `#new` lines of item {whole_number} and "
    "its sub-steps, could not be written ({error}). Any fresh-agent rewrite this step put in the walk-document is "
    "there whole, with the text it replaced kept below as a withdrawn version.\n"
    "Make {reads} writable, then run `{command}` again.")
FRESH_AGENT_REWRITE_REFUSED = (
    "nothing written and no cold-read-fast-read run: {rewrite_file}, the fresh-agent's text for {item}, {problem}, "
    "so it cannot take the place of {item}'s text in {document}.\n"
    "If the fresh-agent wrote its text somewhere else, or in its reply, put that text in {rewrite_file}, with no "
    "Markdown heading line in it, then run `{command}` again.\n"
    "Otherwise run `{read_command}`, which prints the fresh-agent's brief again, and do what its lines say.")
FRESH_AGENT_REWRITE_MISSING = "does not exist or cannot be read ({error})"
FRESH_AGENT_REWRITE_EMPTY = "is empty"
FRESH_AGENT_REWRITE_SHARED_HEADING = (
    "would go under the heading `{heading}`, which {item} shares with other items, and this step replaces only an "
    "item under a heading of its own; give {item} a heading of its own in the walk-document first")
FRESH_AGENT_REWRITE_ITEMS_CHANGED = (
    "would change which items the walk-document holds, from {before} to {after}, as an unclosed code fence in the "
    "rewrite does by turning the headings below it into code, or a paragraph opening with a bold running count, such "
    "as `**Item 3 of 10 revised:**`, does by starting another version of an item; close or remove the fence, and "
    "remove the count")
FRESH_AGENT_REWRITE_ITEM_START_MOVED = (
    "would make the walk-document read {item} as starting at line {line}, not at its heading `{heading}`, as a "
    "paragraph opening with a bold running count, such as `**Item 3 of 10 revised:**`, does by starting another "
    "version of the item; remove the count")
FRESH_AGENT_REWRITE_WITHDRAWN_HEADING_NOT_READ = (
    "would leave `{heading}`, under which the replaced text is kept, read as something other than a heading, as an "
    "unclosed code fence in the rewrite does; close or remove the fence")
FRESH_AGENT_REWRITE_TAG_LINE = ("holds the line `{line}`; the item keeps its own `#approval_walk_item_` lines, so the "
                                "rewrite holds none")
FRESH_AGENT_REWRITE_HEADING = ("holds the Markdown heading `{heading}`, which the walk-document would read as the start "
                               "of another item or sub-step")
FRESH_AGENT_REWRITE_BRIEF_START = "----- brief for the fresh-agent: start -----"
FRESH_AGENT_REWRITE_BRIEF_END = "----- brief for the fresh-agent: end -----"
FRESH_AGENT_REWRITE_DUE_LINES = (
    "{item} is not read or handed over to be presented: its proposed text has been revised three times, {count} "
    "changes in all to the `#new` lines of item {whole_number} and its sub-steps since the count last started, and an item "
    "revised that often is rewritten by a fresh-agent from the user's words, not revised again.",
    "Dispatch a fresh subagent with the brief between the two delimiter lines below, unchanged; it sees none of "
    "this conversation, and the brief leaves out every earlier text of the item.",
)
FRESH_AGENT_REWRITE_BRIEF_LINES = (
    "Write afresh the text of one item of an approval-walk, the item {title}. Its earlier texts are left out of "
    "this brief on purpose: write it from the user's words and the files below, not from any earlier text.",
    "Read {skill} for how an item is written, and keep the item within the word limit it gives.",
    "The user's words on this item, and on the item whose held answer raised it, in the lines of the walk-minutes "
    "{minutes} that hold them:",
)
FRESH_AGENT_REWRITE_NO_USER_WORDS = ("- none: no line of the walk-minutes holds his words and names item {whole_number}, one of "
                                     "its sub-steps, its title, an item whose held answer raised it, or the item that waited when it "
                                     "was bumped.")
FRESH_AGENT_REWRITE_FILES_HEADER = "The files and pages the item links:"
FRESH_AGENT_REWRITE_NO_FILES = "- none."
FRESH_AGENT_REWRITE_ON_NED_BOX = "{link} (on ned-box: {path})"
FRESH_AGENT_REWRITE_BRIEF_CLOSING_LINES = (
    "Do not open {document} or {reads}: they hold the item's earlier texts.",
    "Write the item's text, from its first paragraph to its last line, to {rewrite_file}, replacing "
    "anything there: no heading line and no line opening `#approval_walk_item_`, since the item keeps its own. "
    "Give each text the item proposes a line of its own opening `#new`, and give the item its `#case_against` "
    "line, as the skill says.",
    "End your reply with the path {rewrite_file}.",
)
FRESH_AGENT_REWRITE_AFTER_LINES = (
    "When the fresh-agent has written {rewrite_file}, run `{command}`: it puts that file's text in place of "
    "{item}'s text in {document}, below the heading and its `#approval_walk_item_` lines, keeps the replaced text "
    "below as a withdrawn version, starts the count again, and reads the new text.",
    "If the fresh-agent ends without writing {rewrite_file}, dispatch it once more with the same brief; if it fails "
    "again, ask the user whether to present {item} as it stands, quoting what the fresh-agent said; a subagent puts "
    "that question to the agent that dispatched it.",
    "If the user says to present {item} as it stands, delete {count_file}, which starts the count again from the "
    "text as it stands, then run `{read_command}` and do what it prints.",
)
WALK_ME_THROUGH_SKILL_FILE = REPOSITORY_TOP / ".claude" / "skills" / "walk-me-through" / "SKILL.md"
EARLIER_TEXT_COPY_MISSING = (
    "nothing written and no cold-read-fast-read run: {item}'s earlier text, which the cold-read-fast-read {report} "
    "read, could not be kept below its live version in {document}, because {copy}, this program's copy of that "
    "text, is missing.\n"
    "Copy the one file under {target} to {copy}, then run `{command}` again; it then keeps that text below the "
    "live version itself.\n"
    "If {target} is gone too, do not present {item} yet: ask the user whether to go on without that text, and on "
    "his yes delete {outcome} and run `{command}` again; a subagent puts that question to the agent that "
    "dispatched it.")
RATED_NONE_NOT_SHOWN_LINES = (
    "{item} is not to be shown to the user: it asks a decision and its `#case_against` line rates the case against "
    "none, and the no-answer table settles such an item without asking him, so no cold-read-fast-read was "
    "run.",
    "If {item} has no `#not_asked_touches` line, add one to it in {document} listing every file its change edits or "
    "deletes, separated by spaces, or with nothing after the marker for a change that touches no file, such as "
    "closing a GitHub issue.",
    "Then run `{command}` and do what it prints.",
    "If the case against is in fact more than none, change the rating on its `#case_against` line, then run "
    "`{read_command}` again.",
)
APPROVAL_WALK_ITEM_TITLE_SEARCH_FAILED = (
    "nothing read: {item} was not given its cold-read-fast-read, because the search for what the user said in earlier "
    "agent-sessions that named its title failed (exit {exit}), and the user's earlier words may already decide "
    "the item. The search said:\n{said}\n"
    "Tell the user what each FAILED line above says, with any remedy the lines after it give, and do not show "
    "{item} until the command below runs without this refusal, since until then nobody has read his earlier words "
    "on it; a subagent tells the agent that dispatched it instead.\n"
    "Once the user says the cause is fixed, run `{command}` again.")
TITLE_SEARCH_CACHE_DIRECTORY_NAME = "title-search-cache"
TITLE_SEARCH_CACHE_FILE_NAME = "{walk}-item-{numbers}-{session}.md"
# Raised whenever what a search can print changes, so that a file saved by an older search is searched again.
TITLE_SEARCH_CACHE_FORMAT = 2
TITLE_SEARCH_CACHE_PRINTED_BEFORE = (
    "The user's words where {item}'s title was named before were printed in full by an earlier run of this step in "
    "this agent-session, and are saved in {path}; read that file when they are no longer in your context.")
TITLE_SEARCH_CACHE_NOT_SAVED = (
    "The search for the user's words above was not saved in {path}, so the next run of this step prints it in full "
    "again: {why}")
TITLE_SEARCH_CACHE_NO_AGENT_SESSION = "{variable} is not set, so the agent-session that ran the step is not known."
ITEM_READ_FAILED_LINES = (
    "{item} has had no cold-read-fast-read of its text as it stands, so do not present it yet: the user is shown an "
    "item only after its cold-read-fast-read.",
    "Run `{command}` again once.",
    "If it fails again, ask the user whether to present {item} without its cold-read-fast-read, quoting the FAILED "
    "line above and recommending that you run the command again later; a subagent puts that question to the agent "
    "that dispatched it.",
)
READ_AHEAD_NOT_STARTED = ("No cold-read-fast-read could be started ahead for the item after {item}; this needs nothing "
                          "from you now, since when that item waits its read step reads it or reports the problem "
                          "again. The problem: {problem}")
GIT_LS_FILES_FAILED = "every changed word, since `git ls-files` failed in {top} ({error}) and file names were not known"
APPROVAL_WALK_ITEM_WORD_LIMIT = 500
# The user has not decided whether the hashtag marker lines, such as `#new`, `#new_if_d` and `#case_against`, and
# the texts quoted on `#old` and `#new` lines count toward the limit; until he does, only a line opening with one
# of these, which the item page shows apart from the item's text, is left out of the count.
APPROVAL_WALK_ITEM_WORD_COUNT_LEFT_OUT_LINE_OPENINGS = ("#approval_walk_item_",)
APPROVAL_WALK_ITEM_WORD_COUNT_LEFT_OUT_LINE = re.compile(
    LINE_OPENING_MARKERS + "(?:" + "|".join(map(re.escape, APPROVAL_WALK_ITEM_WORD_COUNT_LEFT_OUT_LINE_OPENINGS)) + ")")
# A run of characters between spaces that holds a letter or a digit, so Markdown's `##`, `-`, `>` and `|` are no words.
APPROVAL_WALK_ITEM_WORD = re.compile(r"\S*[^\W_]\S*")
APPROVAL_WALK_ITEM_SUB_STEP_HEADING_MARKUP = "###"
APPROVAL_WALK_ITEM_OVER_WORD_LIMIT = (
    "nothing read: {item} was not given its cold-read-fast-read, because the text from line {line} of the "
    "walk-document {document}, `{heading}`, has {count} words, over the limit of {limit} words for an item or a "
    "sub-step, and the user is shown no item longer than that. A word here is a run of characters between spaces or line "
    "breaks that holds a letter or a digit; every line of the item counts, heading, code and hashtag marker lines "
    "included, except a line opening with {left_out}, and each `###` sub-step, numbered or not, counts on its own.\n"
    "Split that text into `###` sub-steps, each within {limit} words, headed and ended as the walk-me-through skill's "
    "paragraph opening \"Limit each item to {limit} words\" says; do not cut the text down to fit, since the user wants "
    "long material broken into steps, not compressed.\n"
    "Then run `{command}` again.\n"
    "From now on, write each item and each sub-step within {limit} words when you write it into the walk-document.")

SYSTEM_STATUS_CLAIM_PHRASES_FILE = (REPOSITORY_TOP / "nn-systems" / "general-tools"
                                    / "agent-text-possibly-stale-system-status-claim-phrases-match-common.py")
SYSTEM_STATUS_CLAIMS_RECHECKED_FLAG = "--possibly-stale-system-status-claims-rechecked"
SYSTEM_STATUS_CLAIM_PHRASES_SHOWN = 3
APPROVAL_WALK_ITEM_SYSTEM_STATUS_CLAIM_NOT_RECHECKED = (
    "nothing read: {item} was not given its cold-read-fast-read, on purpose, because its text in the walk-document "
    "{document} states the current status of something outside the walk ({matched}). A status changes without "
    "notice: an agent-seat comes back online, the user logs `claude` back in, a job is restarted. The user acts on "
    "what an item tells him, so a status that was true when the item was written can cost him a correction or a "
    "wrong decision.\n"
    "If the item states a status: check each one now with a command, such as `claude auth status` for the login on "
    "this machine, `tmux -L <agent-seat> ls` on the agent-seat's machine, `crontab -l` for a scheduled job, or the "
    "ListAgents tool for an agent-seat; correct the item where the status has changed, and write into the item the "
    "time you checked. When a check fails or cannot reach the machine, say in the item that the status is "
    "unchecked, and what the command printed. Then run `{command} " + SYSTEM_STATUS_CLAIMS_RECHECKED_FLAG
    + " '<each command you ran, the time and what it showed, as in: tmux -L cold-read-research ls at 14:02Z, "
    "session running>'`, naming in the value any matched phrase that states no status, and why.\n"
    "If none of the matched words states a current status, as in a quotation or a description of what a program "
    "does: run `{command} " + SYSTEM_STATUS_CLAIMS_RECHECKED_FLAG + " 'no current status stated: <why>'`.\n"
    "From now on, check each status an item states with a command just before you present the item, and say in "
    "the item when you checked.")
SYSTEM_STATUS_CLAIMS_RECHECKED_EMPTY = (
    "nothing read: " + SYSTEM_STATUS_CLAIMS_RECHECKED_FLAG + " was given an empty value, and the value is the record "
    "of how the item's status claims were checked.\n"
    "Run the step again with the value saying each command you ran and the time you ran it.")
SYSTEM_STATUS_CLAIMS_RECHECKED_LINE = "{item}: its status claims ({matched}) rechecked, as the agent says: {rechecked}"


class Failure(Exception):
    """A step that cannot go on; its argument is the line to print."""


class EvidenceCheckFailed(Failure):
    """An item's evidence could not be checked; reason says why, without the full message's rerun instruction,
    for a no-answer row that is not offered and so has no command to rerun."""

    def __init__(self, message, reason):
        super().__init__(message)
        self.reason = reason


class FastReadFailed(Exception):
    """A fast read failed; its argument is the FAILED line, printed as it is."""


def reachable_log_store_records(record_shipper=None, ned_box_home=None, mac_mount=None):
    """Return (the log-store's cold-read-records directory as this machine reaches it, or None, and the paths
    tried): the path ned-box names it by, then the same path under the Mac's mount of ned-box's home."""
    if record_shipper is None:
        record_shipper = load_module("cold_read_record_ship", RECORD_SHIPPER_FILE)
        constants = load_module("ned_box_home_directory_and_its_mac_mount_point_path_constants_common",
                                PATH_CONSTANTS_FILE)
        ned_box_home, mac_mount = constants.NED_BOX_HOME, constants.MAC_MOUNT_OF_NED_BOX_HOME
    _, path = record_shipper.split_destination(record_shipper.LOG_STORE_RECORDS_DESTINATION)
    candidates = [Path(str(path))]
    if str(path).startswith(ned_box_home + "/"):
        candidates.append(Path(mac_mount + str(path)[len(ned_box_home):]))
    return next((candidate for candidate in candidates if candidate.is_dir()), None), candidates


def is_walk_document_copy_name(name):
    """Only a name this program could give: a note or recovered file kept in the folder is never pruned. A name with
    non-ASCII digits, which `\\d` and strptime both accept, is not told apart from one the program wrote."""
    match = WALK_DOCUMENT_COPY_NAME.fullmatch(name)
    if match is None:
        return False
    try:
        datetime.datetime.strptime(match.group(1), WALK_DOCUMENT_COPY_STAMP_FORMAT)
    except ValueError:
        return False
    return True


def walk_me_through_walk_document_timestamped_copy_save_on_ned_box_and_oldest_copies_prune(arguments):
    """Save the open walk's walk-document; return what went wrong, or None. A walk this cannot find is the step's
    own refusal to report."""
    if arguments.walk_document_copies_directory is None and (arguments.cold_read_records or arguments.counts_log):
        return None  # A run pointed at other records or counts is a test's, and must not write to the real copies.
    walk_finder = load_walk_finder()
    top = walk_finder.checkout_top(Path(arguments.cwd))
    walk_directory = top / walk_finder.WALK_DIRECTORY if top else None
    if walk_directory is None or not walk_directory.is_dir():
        return None
    try:
        walk = walk_finder.the_one_unclosed_approval_walk_including_paused(walk_directory,
                                                                           walk_finder.markdown_parser())
    except walk_finder.MoreThanOneUnclosedApprovalWalk:
        return None
    if walk is None:
        return None
    minutes = walk[0]
    walk_name = minutes.name[:-len(walk_finder.MINUTES_SUFFIX)]
    document = minutes.with_name(walk_name + ".md")
    if not document.is_file():
        return None
    temporary = None
    written = False
    try:
        copies_root = arguments.walk_document_copies_directory
        if copies_root is None:
            log_store_records, tried = reachable_log_store_records()
            if log_store_records is None:
                raise OSError(LOG_STORE_UNREACHABLE.format(paths=" or ".join(str(path) for path in tried)))
            copies_root = log_store_records.parent / WALK_DOCUMENT_COPIES_DIRECTORY_IN_LOG_STORE
        copies = copies_root / walk_name
        copies.mkdir(parents=True, exist_ok=True)
        content = document.read_bytes()

        def saved_copies():
            return sorted(path for path in copies.iterdir() if is_walk_document_copy_name(path.name))

        existing = saved_copies()
        if not existing or existing[-1].read_bytes() != content:
            stamp = datetime.datetime.now(datetime.timezone.utc).strftime(WALK_DOCUMENT_COPY_STAMP_FORMAT)
            # The content hash keeps two versions saved with one stamp from replacing each other.
            final_name = f"{stamp}-{hashlib.sha256(content).hexdigest()[:16]}.md"
            handle, temporary = tempfile.mkstemp(suffix=".tmp", dir=copies)
            with os.fdopen(handle, "wb") as file:
                file.write(content)
            os.chmod(temporary, 0o644)  # mkstemp's 0600 would keep the copy from other users of the mount.
            os.replace(temporary, copies / final_name)
            temporary = None
            written = True
    except OSError as error:
        if temporary is not None:
            with contextlib.suppress(OSError):
                os.unlink(temporary)
        return WALK_DOCUMENT_COPY_NOT_SAVED.format(document=document, error=error)
    try:
        # Listed again here, not in the save's try: once the copy is published, a failure is a failed prune.
        if written:
            existing = saved_copies()
        # Pruned even when nothing was saved, so a prune that failed last run is finished once its error clears.
        for old in existing[:-WALK_DOCUMENT_COPIES_KEPT]:
            old.unlink(missing_ok=True)
    except OSError as error:
        return WALK_DOCUMENT_COPIES_NOT_PRUNED.format(document=document, error=error, kept=WALK_DOCUMENT_COPIES_KEPT)
    return None


def the_open_walk(walk_finder, cwd):
    """Return (checkout top, minutes path, #next_to_present value, parser)."""
    top = walk_finder.checkout_top(Path(cwd))
    if top is None:
        raise Failure(f"{cwd} is not in a git checkout, so no approval-walk can be open there.")
    parser = walk_finder.markdown_parser()
    walk_directory = top / walk_finder.WALK_DIRECTORY
    try:
        walk = (walk_finder.the_one_unclosed_approval_walk_including_paused(walk_directory, parser)
                if walk_directory.is_dir() else None)
    except walk_finder.MoreThanOneUnclosedApprovalWalk as several:
        raise Failure(MORE_THAN_ONE_UNCLOSED_APPROVAL_WALK.format(
            directory=walk_directory, minutes="\n".join(f"  {path}" for path in several.minutes_paths)))
    if walk is None:
        raise Failure(f"no approval-walk is open in {walk_directory}.")
    minutes, value, _, paused = walk
    if paused:
        raise Failure(f"the approval-walk whose minutes are {minutes} is paused: an `#approval_walk_paused` line "
                      f"comes after its last `#next_to_present` line, so the walk has no item to check or close.\n"
                      f"If the user has said to resume the walk, add the line below at the end of those minutes, "
                      f"after the `#approval_walk_paused` line, which stays, and then run the command you just ran "
                      f"again:\n"
                      f"#next_to_present {value}\n"
                      f"Until the user says to resume the walk, leave it paused, do not run this program for it, "
                      f"and go on with the rest of your work.")
    return top, minutes, value, parser


def waiting_items(walk_finder, value, minutes):
    """Return (running count such as `item 4.1 of 6`, item numbers, M or None) of the `#next_to_present` value."""
    match = walk_finder.VALUE_COUNT.match(value)
    if not match:
        raise Failure(f"the last `#next_to_present` line in {minutes}, `{value}`, names no item.")
    try:
        numbers, total = walk_finder.parse_items(value)
    except walk_finder.UnusableRange as problem:
        raise Failure(f"the last `#next_to_present` line in {minutes}, `{value}`, {problem}.")
    return match[0], numbers, total


def item_line_ranges(walk_finder, minutes, value, numbers, total, parser, named_by=None):
    """Return (walk-document path, its text, its tokens, the (first, end) line ranges of the items numbered, the
    units of the items numbered as waiting_item_units returns them), finding the items as close does, so check
    refuses a walk-document close would refuse. A Failure names named_by as what named the items, by default the
    walk-minutes' last `#next_to_present` line."""
    document = minutes.with_name(minutes.name[:-len(walk_finder.MINUTES_SUFFIX)] + ".md")
    try:
        _, spans = walk_finder.waiting_item_units(document, value, numbers, total, parser)
    except walk_finder.UnusableRange as problem:
        raise Failure(f"{named_by or f'the last `#next_to_present` line in {minutes}'}, `{value}`: {problem}")
    text = document.read_text(encoding="utf-8")
    tokens = parser.parse(text)
    openings = walk_finder.item_opening_lines(text, parser, tokens)
    lines = text.split("\n")
    ranges = []
    for unit in spans:
        if len(numbers) == 1 and len(unit[0]) > 1:
            own_first, _ = walk_finder.approval_walk_item_line_range_within_heading_shared_by_several_items(
                openings, unit[3], unit[4], numbers[0], unit[0], unit[1])
            # An item with no opening of its own starts at the shared opener, whose line can hold its recommendation;
            # the ranges below it are the ones the item copy the user is shown reads, a setext heading's further
            # lines included.
            ranges += [(unit[3], unit[3] + 1)] if own_first == unit[3] else []
            ranges += walk_finder.approval_walk_unit_heading_end_and_item_line_ranges_below_heading_line(
                text, parser, lines, unit, [openings], [numbers[0]])[1]
        else:
            ranges.append(unit[3:])
    return document, text, tokens, ranges, spans


# CommonMark's open tag, as the Markdown parser reads one; no `<!--` in it opens a comment.
HTML_OPEN_TAG = re.compile(r"""<[A-Za-z][A-Za-z0-9-]*(?:\s+[A-Za-z_:][A-Za-z0-9:._-]*"""
                           r"""(?:\s*=\s*(?:[^"'=<>`\x00-\x20]+|'[^']*'|"[^"]*"))?)*\s*/?>""")


def comment_openings_in_tags_escaped(text):
    """Return text with each `<!--` inside an HTML open tag, such as `<div title="<!--">`, written as `&lt;!--`."""
    return HTML_OPEN_TAG.sub(lambda tag: tag[0].replace("<!--", "&lt;!--"), text)


def item_lines(walk_finder, minutes, value, numbers, total, parser):
    """Return (walk-document path, the lines of the items numbered, outside fenced code, the items' marks as
    new_marks returns them, the problem line of each mark whose text would not be read whole, the same lines
    as the first read with no `<!--` inside an HTML open tag opening a comment)."""
    document, text, tokens, ranges, _ = item_line_ranges(walk_finder, minutes, value, numbers, total, parser)
    lines = walk_finder.prose_lines(text, parser, tokens)
    marks = new_marks(text, tokens, ranges, lines)
    tag_comments_kept = walk_finder.prose_lines(comment_openings_in_tags_escaped(text), parser)
    return (document, [line for first, end in ranges for line in lines[first:end]], marks,
            unreadable_new_marks(marks),
            [line for first, end in ranges for line in tag_comments_kept[first:end]])


def item_text(walk_finder, minutes, value, numbers, total, parser, named_by=None, refused_unless_marks_read=None):
    """Return (walk-document path, the items' text as the user is shown it, heading and fenced code included).
    With refused_unless_marks_read, (item, command), a Failure when a mark's text would not be read whole."""
    document, text, tokens, ranges, _ = item_line_ranges(walk_finder, minutes, value, numbers, total, parser, named_by)
    unreadable = (unreadable_new_marks(new_marks(text, tokens, ranges, walk_finder.prose_lines(text, parser, tokens)))
                  if refused_unless_marks_read else [])
    if unreadable:
        item, command = refused_unless_marks_read
        raise Failure(UNREADABLE_NEW_MARKS.format(item=item, document=document, problems="\n".join(unreadable),
                                                  command=command))
    lines = text.split("\n")
    return document, "\n".join(line for first, end in ranges for line in lines[first:end]).strip()


def approval_walk_item_word_counted_line_ranges(walk_finder, text, tokens, parser, spans, numbers):
    """Return the (first, end) line ranges counted for the items numbered, one per text the skill counts on its
    own: each numbered item's own lines, even under a heading it shares with other items; when several items
    are shown together, the lines of their shared heading above the first item's opening; and each of the
    item's numbered sub-steps, such as `### Item 3.1 of 9`, which item_unit_spans reads as units of their own,
    taken as approval_walk_item_sub_step_units_below_item_in_walk_document takes them, with the lines of a heading
    several sub-steps share above the first sub-step's opening."""
    openings = walk_finder.item_opening_lines(text, parser, tokens)
    all_units = walk_finder.item_unit_spans(text, parser)

    def own_range(unit, number):
        unit_numbers, unit_total, _, first, end = unit
        return walk_finder.approval_walk_item_line_range_within_heading_shared_by_several_items(
            openings, first, end, number, unit_numbers, unit_total)

    def shared_heading_text(unit):
        first_opening = min(own_range(unit, part)[0] for part in unit[0])
        return [(unit[3], first_opening)] if first_opening > unit[3] else []

    ranges = []
    for number in numbers:
        unit = next(unit for unit in spans if number in unit[0])
        ranges.append(own_range(unit, number))
        if len(numbers) > 1 and len(unit[0]) > 1:
            ranges += shared_heading_text(unit)
        for each in walk_finder.approval_walk_item_sub_step_units_below_item_in_walk_document(all_units, unit, [number]):
            parts =[part for part in each[0] if part.startswith(number + ".") and part not in numbers]
            ranges += [own_range(each, part) for part in parts]
            if parts and len(each[0]) > 1:
                ranges += shared_heading_text(each)
    return sorted(set(ranges))


def approval_walk_item_text_over_word_limit_refused(walk_finder, minutes, value, numbers, total, parser, item, command,
                                                    skipped_start=None):
    """Raise Failure when an item's text up to its first `###` sub-step, a sub-step, or the text of a heading
    several items or sub-steps share above the first of them, has more words than APPROVAL_WALK_ITEM_WORD_LIMIT,
    naming the first such text; the text starting at line skipped_start, such as a sub-step about to be rewritten,
    is not counted. A sub-step is a `###` heading, numbered or not; a deeper heading is part of the text it falls
    in."""
    document, text, tokens, _, spans = item_line_ranges(walk_finder, minutes, value, numbers, total, parser)
    lines = text.split("\n")
    sub_steps = {token.map[0] for token in tokens if token.type == "heading_open" and token.level == 0
                 and token.map is not None and token.markup == APPROVAL_WALK_ITEM_SUB_STEP_HEADING_MARKUP}
    for first, end in approval_walk_item_word_counted_line_ranges(walk_finder, text, tokens, parser, spans, numbers):
        starts = sorted({first} | {line for line in sub_steps if first < line < end})
        for start, stop in zip(starts, starts[1:] + [end]):
            if start == skipped_start:
                continue
            count = sum(len(APPROVAL_WALK_ITEM_WORD.findall(line)) for line in lines[start:stop]
                        if not APPROVAL_WALK_ITEM_WORD_COUNT_LEFT_OUT_LINE.match(line))
            if count > APPROVAL_WALK_ITEM_WORD_LIMIT:
                raise Failure(APPROVAL_WALK_ITEM_OVER_WORD_LIMIT.format(
                    item=item, line=start + 1, document=document, heading=lines[start].strip(), count=count,
                    limit=APPROVAL_WALK_ITEM_WORD_LIMIT, command=command,
                    left_out=" or ".join(f"`{opening}`" for opening in APPROVAL_WALK_ITEM_WORD_COUNT_LEFT_OUT_LINE_OPENINGS)))


def proposed_texts(marks_found, marks):
    """Return (mark, text) for each mark of new_marks' list that is one of marks, outside code and with a text,
    in the document's order. The text is every line new_marks gives the mark, so it is the text that
    unreadable_new_marks judged."""
    texts = []
    for mark in marks_found:
        if mark.mark not in marks or mark.in_code:
            continue
        text = unquoted(lines_joined(mark.text_lines))
        if text:
            texts.append((mark.mark, text))
    return texts


def unquoted(text):
    """Return text stripped, without one pair of surrounding quotation marks."""
    text = text.strip()
    for opening, closing in QUOTE_PAIRS:
        if len(text) >= 2 and text.startswith(opening) and text.endswith(closing):
            return text[1:-1].strip()
    return text


def lines_joined(lines):
    """Return lines as one line, whitespace runs squeezed."""
    return squeezed(" ".join(lines))


def unquoted_lines(lines):
    """Return lines below a mark without their quotation markers; the mark's own text keeps a leading `>`."""
    return [QUOTATION_MARKERS.sub("", line) for line in lines]


def lines_until_blank_or_fence(lines, first, end):
    """Return the lines from first up to end, without their quotation markers, stopping before a blank line or a
    fence delimiter."""
    taken = []
    for line in lines[first:end]:
        if not line.strip() or FENCE_DELIMITER.match(line):
            break
        taken.append(line)
    return unquoted_lines(taken)


def block_right_below(lines, first, end):
    """Return the lines a mark with no text on its line may have meant: the lines that run on right below it,
    or else the one fenced block or quotation after the blank lines below it; [] when there is neither."""
    if first < end and lines[first].strip() and not FENCE_DELIMITER.match(lines[first]):
        return lines_until_blank_or_fence(lines, first, end)
    while first < end and not lines[first].strip():
        first += 1
    if first < end and FENCE_DELIMITER.match(lines[first]):
        return lines_until_blank_or_fence(lines, first + 1, end)
    if first < end and QUOTATION_LINE.match(lines[first]):
        return lines_until_blank_or_fence(lines, first, end)
    return []


NewMark = collections.namedtuple("NewMark", "mark number in_code comment_cut text_lines below")
NewMark.__doc__ = """One `#new` or `#new_if_d` mark: mark, its 0-based line number, whether it is inside fenced or
indented code, whether text was cut from its line as an HTML comment, text_lines, the mark's own text as written followed by every line its text runs onto, and below,
for a mark in code or with no text, the lines it may have meant; lines below the mark's own line lose their
quotation markers."""


def new_marks(text, tokens, ranges, shown):
    """Return a NewMark for each `#new` or `#new_if_d` mark in the ranges outside an HTML comment, in order;
    shown are the walk finder's prose_lines of text, from which every HTML comment is cut.
    This is the one place that decides where a marked text ends, so that check reads the text
    unreadable_new_marks judged: at the end of its Markdown paragraph, or before the first line below it that
    this program reads on its own, such as the next `#new` or a `#case_against` line, even when Markdown keeps
    that line in the same paragraph. A `The new text:` label just after the mark is not part of its text, as the
    short-answer hook reads it, so a mark with only the label has no text on its line."""
    new_text_label = load_module("walk_me_through_user_short_answer_hook", SHORT_ANSWER_HOOK_FILE).NEW_TEXT_LABEL
    lines = text.split("\n")
    code, paragraphs = {}, []
    for token in tokens:
        if token.map is None:
            continue
        if token.type in ("fence", "code_block"):
            code.update((number, token.map[1]) for number in range(*token.map))
        elif token.type == "paragraph_open":
            paragraphs.append(token.map)
        elif token.type == "heading_open" and token.markup in ("=", "-"):
            # A setext heading's lines above its underline read as one paragraph, which the item copy shows them as.
            paragraphs.append([token.map[0], token.map[1] - 1])
    marks = []
    new_text_mark_line = load_walk_finder().APPROVAL_WALK_ITEM_NEW_TEXT_MARK_LINE_PATTERN
    for first, end in ranges:
        for number in range(first, end):
            match = new_text_mark_line.match(lines[number] if number in code else shown[number])
            if not match:
                continue
            if number in code:
                below = lines_until_blank_or_fence(lines, number + 1, min(code[number], end))
                marks.append(NewMark(match[1], number, True, False, [match[2]], below))
                continue
            comment_cut = shown[number] != lines[number]
            own_text = new_text_label.sub("", match[2])
            if not unquoted(own_text):
                marks.append(NewMark(match[1], number, False, comment_cut, [own_text],
                                     block_right_below(lines, number + 1, end)))
                continue
            paragraph_end = max((paragraph[1] for paragraph in paragraphs if paragraph[0] <= number < paragraph[1]),  # pragma: no mutate, paragraphs never overlap, so a paragraph starting above the one holding the line also ends above it and max picks the same end, and with no paragraph holding the line both give no line below it
                                default=number + 1)
            text_end = next((below for below in range(number + 1, paragraph_end)
                             if any(marker.match(lines[below]) for marker in MARKER_LINES_READ_ON_THEIR_OWN)),
                            paragraph_end)
            marks.append(NewMark(match[1], number, False, comment_cut,
                                 [own_text] + unquoted_lines(lines[number + 1:min(text_end, end)]), []))
    return marks


def unreadable_new_marks(marks):
    """Return one problem line for each of new_marks' marks whose text check would not read whole: one with no
    text on its line, one inside fenced or indented code, one with text cut from its line as an HTML comment, and
    one whose text runs onto the lines right below it."""
    problems = []
    for found in marks:
        mark, line = found.mark, found.number + 1
        if found.comment_cut:
            problems.append(UNREADABLE_COMMENT_CUT.format(line=line, mark=mark))
        elif found.in_code or not unquoted(found.text_lines[0]):
            problem = UNREADABLE_FENCED if found.in_code else UNREADABLE_BARE
            joined = lines_joined(([found.text_lines[0]] if found.in_code else []) + found.below)
            problems.append(problem.format(line=line, mark=mark)
                            + (UNREADABLE_JOINED.format(mark=mark, text=joined) if joined else ""))
        elif len(found.text_lines) > 1:
            last = found.number + len(found.text_lines)
            below = f"line {line + 1}" if last == line + 1 else f"lines {line + 1} to {last}"
            problems.append(UNREADABLE_RUN_ON.format(line=line, mark=mark, below=below)
                            + UNREADABLE_JOINED.format(mark=mark, text=lines_joined(found.text_lines)))
    return problems




def squeezed(text):
    return " ".join(text.split())


def as_written_key(text):
    """Return text as written, with only its line endings and its leading and trailing blank lines made uniform, so
    that two versions compare equal only when their Markdown source is the same."""
    return blank_lines_stripped(text.replace("\r\n", "\n").replace("\r", "\n"))


def walk_fast_read_name(walk_name, *parts):
    """The target name of a fast read this program runs for the walk, which starts its cold-read-record's name;
    fast_read_record_holding finds the walk's records by the walk_name- prefix this gives."""
    return "-".join([walk_name, *(file_name_part(str(part)) for part in parts)])


def fast_read_record_holding(text, record_directories, walk_name):
    """Return the walk's cold-read-record directory whose fast read read the text, or None."""
    wanted = squeezed(text)
    record_names = load_module("cold_read_record_names", RECORD_NAMES_FILE)
    prefix = walk_fast_read_name(walk_name) + "-"
    for directory in record_directories:
        if not directory.is_dir():
            continue
        for record in sorted(directory.iterdir()):
            if not record.name.startswith(prefix):
                continue
            report = record_names.cold_read_record_file_path_prefixed_name_else_name_before_prefix(
                record, record_names.COLD_READ_FAST_READ_REPORT_FILE_NAME)
            if not report.is_file() or not (record / "target").is_dir():
                continue
            for target in (record / "target").rglob("*"):
                if target.is_file() and wanted in squeezed(target.read_text(encoding="utf-8", errors="replace")):
                    return record
    return None


STOP_SIGNALS = (signal.SIGTERM, signal.SIGHUP)


@contextlib.contextmanager
def scratch_directory_removed_on_every_exit(after_removal):
    """Make a scratch directory and yield its path; remove it when the block ends, however the block ends. A
    SIGTERM or SIGHUP during the block removes it and then ends the program as that signal's default does; one
    the program was started with ignored, as under nohup, stays ignored. When that removal fails, the message
    ends with after_removal, the caller's sentence saying what to run next, since only the caller knows the
    command, its --cwd included, that redoes its step.

    The handler raises nothing: an exception raised inside subprocess's own code, between Popen._wait()'s lock
    acquire and its try, leaves the lock held, and the wait() that subprocess.run() then makes blocks forever.
    stop-signal-sigterm-or-sighup-raises-system-exit-so-cleanup-runs-common.py raises, so it does not fit here.
    """
    made = []

    def remove_then_end(number, _):
        for directory in made:
            try:
                shutil.rmtree(directory)
            except OSError as error:
                print(STOP_SIGNAL_SCRATCH_NOT_REMOVED_LINES.format(
                    program=PROGRAM, signal=signal.Signals(number).name, directory=directory,
                    quoted_directory=shlex.quote(directory), error=error, after_removal=after_removal),
                    file=sys.stderr)
        signal.signal(number, signal.SIG_DFL)
        os.kill(os.getpid(), number)

    previous = {number: signal.signal(number, remove_then_end)
                for number in STOP_SIGNALS if signal.getsignal(number) != signal.SIG_IGN}
    try:
        # Blocked until the path is in made, so a stop signal between the two cannot leave the directory behind.
        previous_mask = signal.pthread_sigmask(signal.SIG_BLOCK, STOP_SIGNALS)
        try:
            scratch = tempfile.mkdtemp(prefix=PROGRAM + "-")
            made.append(scratch)
        finally:
            signal.pthread_sigmask(signal.SIG_SETMASK, previous_mask)
        yield scratch
    finally:
        for directory in made:
            shutil.rmtree(directory)
        for number, handler in previous.items():
            signal.signal(number, handler)


def run_fast_read(text, name, fast_read_program, after_removal):
    """Fast-read the text from a scratch file; return (the report's directory, the lines the fast read printed
    on stderr about an unshipped record or a changed target), or raise FastReadFailed. after_removal is as
    scratch_directory_removed_on_every_exit takes it.

    The scratch directory is removed on every exit, SIGTERM and SIGHUP included: the fast read keeps its own copy
    of the text in its record's target/, which is where a later check looks for it."""
    with scratch_directory_removed_on_every_exit(after_removal) as scratch:
        target = Path(scratch) / f"{name}.md"
        target.write_text(text + "\n", encoding="utf-8")
        result = subprocess.run([sys.executable, str(fast_read_program), "--target", str(target),
                                 FAST_READ_WITHOUT_QUESTION_4_OPTION], capture_output=True, text=True)
    lines = result.stdout.strip().split("\n")
    failed = [line for line in lines if line.startswith("FAILED")]
    if failed:
        raise FastReadFailed(failed[0])
    notes = [line.strip() for line in result.stderr.split("\n")
             if any(marker in line for marker in FAST_READ_NOTE_MARKERS)]
    # Exit 1 means other failures too, so only the stderr line says the record was all that failed.
    only_the_record_not_shipped = result.returncode == 1 and any(
        note.startswith(FAST_READ_RECORD_NOT_SHIPPED_MARKERS) for note in notes)
    if (result.returncode != 0 and not only_the_record_not_shipped) or not lines[-1]:
        ran = shlex.join([str(fast_read_program), "--target", str(target), FAST_READ_WITHOUT_QUESTION_4_OPTION])
        raise FastReadFailed(f"FAILED: {ran} exited {result.returncode} "
                             f"without naming a report; its stderr: {result.stderr.strip()[-500:]}")
    return Path(lines[-1]).parent, notes


def excerpt(walk_finder, text):
    """The start of text, as a code span, so that no marker in it is read from the minutes."""
    return walk_finder.text_wrapped_as_markdown_code_span(text if len(text) <= 60 else text[:57].rstrip() + "...")


def file_name_part(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def append_to_minutes(minutes, lines):
    load_walk_finder().append_to_minutes(minutes, lines)


def part_answer(value):
    """Return (part number, A, AO or D) from a --part-answer value such as `2=ao`."""
    match = PART_ARGUMENT.match(value)
    if not match:
        raise argparse.ArgumentTypeError(PART_ARGUMENT_PROBLEM.format(value=value))
    return int(match[1]), match[2].upper()


def not_asked_kind(value):
    """Return the --not-asked value: a kind or a value for an item of no kind, each a row of NO_ANSWER_CASES."""
    if value.strip().lower() in NOT_ASKED_NO_KIND_VALUES:
        return value.strip().lower()
    if value.strip() in {str(kind) for kind in NOT_ASKED_KINDS}:
        return int(value)
    kinds = ", ".join(str(kind) for kind in NOT_ASKED_KINDS)
    no_kind = ", ".join(NOT_ASKED_NO_KIND_VALUES[:-1]) + " or " + NOT_ASKED_NO_KIND_VALUES[-1]
    raise argparse.ArgumentTypeError(f"`{value}` is not a kind: give {kinds}, or, for an item of no kind, {no_kind}")


def not_asked_label(kind):
    """How the minutes and messages name a --not-asked value: `kind 3`, `adds nothing`, `case against none`, or the
    label of a weak case against's ground, such as `case against weak, cost only`."""
    return no_answer_case(kind).label


def guarded_paths(top, paths):
    """Return the paths, relative to the checkout top, that instruction-file-guard.py protects."""
    guard = load_module("instruction_file_guard", INSTRUCTION_FILE_GUARD_FILE)
    return [path for path in paths if any(protects(str(top / path)) for protects in (
        guard.is_protected, guard.is_reusable_prompt, guard.is_reviewed_document))]


def answered_word(arguments, walk_finder):
    """The answer as the walk-minutes write it: approved, disapproved, approved option N, or each part's word,
    as in `part 1 approved #approved_obvious, part 2 disapproved`; for --already-decided, the answer its ruling gives
    before the citation, as in `disapproved, already decided by ...`, an approval left out."""
    if arguments.already_decided is not None:
        ruled = ALREADY_DECIDED_PREFIX + walk_finder.text_wrapped_as_markdown_code_span(arguments.already_decided)
        word = answered_word(argparse.Namespace(**dict(vars(arguments), already_decided=None)), walk_finder)
        return ruled if word == APPROVED else f"{word}, {ruled}"
    if arguments.part_answer:
        return ", ".join(f"part {number} {PART_WORDS[letter]}" for number, letter in sorted(arguments.part_answer))
    if arguments.disapproved:
        return DISAPPROVED
    if arguments.deferred:
        return DEFERRED
    if arguments.moved_on_no_decision:
        return MOVED_ON
    if arguments.option is not None:
        return f"{APPROVED} option {arguments.option}"
    if arguments.not_asked is not None:
        return f"not asked, {not_asked_label(arguments.not_asked)}"
    if arguments.moved_on is not None:
        return MOVED_ON_PREFIX + walk_finder.text_wrapped_as_markdown_code_span(arguments.moved_on)
    return APPROVED


def marks_the_answer_adds(arguments):
    """The marks of the texts the answer adds: `#new_if_d` for D, `#new` for any other answer, and for
    answers to parts, the marks of the parts' answers."""
    if arguments.part_answer:
        letters = {letter for _, letter in arguments.part_answer}
        return {mark for mark, adds in ((NEW_MARK, letters != {"D"}), (NEW_IF_D_MARK, "D" in letters)) if adds}
    return {NEW_IF_D_MARK} if arguments.disapproved else {NEW_MARK}


def answer_hashtag(arguments):
    """The hashtag the walk-minutes write right after an AO or Aa approval, or nothing."""
    if arguments.obvious:
        return OBVIOUS_HASHTAG
    if arguments.after_advisor:
        return AFTER_ADVISOR_HASHTAG
    return ""


def answer_check_commands(top):
    """The check command for each answer an item can take, to print where the agent chose the wrong flag."""
    commands = [MOVED_ON_NO_DECISION_ANSWER_LINE.format(answer=answer, command=check_command_with_cwd(top, *flags))
                for answer, flags in MOVED_ON_NO_DECISION_ANSWER_COMMANDS]
    commands += [MOVED_ON_NO_DECISION_OPTION_LINE.format(number=number,
                                                         command=check_command_with_cwd(top, "--option", str(number)))
                 for number in OPTION_NUMBERS]
    commands.append(MOVED_ON_NO_DECISION_PART_LINE.format(
        command=check_command_with_cwd(top, *MOVED_ON_NO_DECISION_PART_EXAMPLE)))
    return "\n".join(commands)


printed_command_path_override_words = []


def step_command_with_cwd(top, step, *words):
    """The command for one step of this program that it tells the agent to run. Every such command is built here,
    shell-quoted, because each must survive a path holding a space and must name the walk's checkout with --cwd:
    the agent may run it from another checkout, which it would otherwise act on instead. step may hold a flag, as
    `close --hold-answer-until-new-item-answered` does."""
    return shlex.join(["python3", str(Path(__file__).resolve()), *step.split(), *words, "--cwd", str(top),
                       *printed_command_path_override_words])


def explicit_path_override_words(arguments):
    """The path overrides this run was given, absolute because a printed command may run from another directory.
    Without them a printed command would run another reader, search other records or log counts elsewhere."""
    words = []
    for directory in arguments.cold_read_records or []:
        words += ["--cold-read-records", os.path.abspath(directory)]
    if arguments.fast_read_program != FAST_READ_PROGRAM:
        words += ["--fast-read-program", os.path.abspath(arguments.fast_read_program)]
    if arguments.counts_log:
        words += ["--counts-log", os.path.abspath(arguments.counts_log)]
    return words


def flag_and_value_words(flag, value):
    """The words for a flag and its value; argparse rejects a separate value that opens with a dash."""
    return [f"{flag}={value}"] if value.startswith("-") else [flag, value]


def check_command_with_cwd(top, *words):
    """The check command, with these flags and values, that this program tells the agent to run."""
    return step_command_with_cwd(top, "check", *words)


def read_step_command_with_cwd(top, *words):
    """The waiting item's read-step command, with these flags and values, that this program tells the agent to run."""
    return step_command_with_cwd(top, WAITING_ITEM_READ_STEP, *words)


def check_words(arguments):
    """The flags and values this check step was run with, to repeat in the command it tells the agent to rerun."""
    words = []
    if arguments.obvious:
        words.append("--obvious")
    if arguments.after_advisor:
        words.append("--after-advisor")
    # --already-decided carries its own D, which it set on these arguments.
    ruled = arguments.already_decided is not None
    if arguments.disapproved and not ruled:
        words.append("--disapproved")
    if arguments.deferred:
        words.append("--deferred")
    if arguments.moved_on_no_decision:
        words.append("--moved-on-no-decision")
    if arguments.moved_on is not None:
        words += flag_and_value_words("--moved-on", arguments.moved_on)
    if arguments.option is not None:
        words += ["--option", str(arguments.option)]
    if arguments.not_asked is not None:
        words += ["--not-asked", str(arguments.not_asked)]
    if arguments.now_over_later_already_decided:
        words.append(NOW_OVER_LATER_FLAG)
    elif ruled:
        words += [*flag_and_value_words("--already-decided", arguments.already_decided),
                  *arguments.already_decided_answers]
    for number, letter in arguments.part_answer or []:
        words += ["--part-answer", f"{number}={letter}"]
    if (arguments.user_reply_as_typed or "").strip():
        words += flag_and_value_words("--user-reply-as-typed", arguments.user_reply_as_typed)
    return words


def case_against_rating(lines, item, document, arguments, top):
    """Return the rating on the item's first `#case_against` line, as in `very strong`, or None when the item
    has none and the answer, O2, O3 or --moved-on-no-decision, does not need one; raise Failure when an answer that needs one finds
    none, or a line that opens with no rating."""
    for line in lines:
        match = CASE_AGAINST_LINE.match(line)
        if not match:
            continue
        rating = CASE_AGAINST_RATING.match(match[1])
        if rating is None:
            raise Failure(CASE_AGAINST_UNRATED.format(item=item, document=document, line=line.strip(),
                                                      command=check_command_with_cwd(top, *check_words(arguments))))
        return rating[1].lower()
    if (arguments.option is not None or arguments.moved_on_no_decision or arguments.already_decided is not None
            or arguments.moved_on is not None):
        return None
    raise Failure(CASE_AGAINST_MISSING.format(item=item, document=document,
                                              command=check_command_with_cwd(top, *check_words(arguments))))


def evidence(lines):
    """Return {marker: [the values of each of the item's lines opening with that `#not_asked_` marker]}."""
    found = collections.defaultdict(list)
    for line in lines:
        match = EVIDENCE_LINE.match(line)
        if match:
            found[match[1]].append(match[2].strip())
    return found


def words(values):
    """The paths or names on evidence lines, without code marks or separating commas."""
    return [word.strip("`,;") for value in values for word in value.split() if word.strip("`,;")]


def rename_names(value):
    """The names on a rename line: each name in backquotes, which may hold spaces, or else each word."""
    return [(quoted or word).strip(",;") for quoted, word in re.findall(r"`([^`]+)`|([^\s`]+)", value)
            if (quoted or word).strip(",;")]


def files_matching(top, options, pattern, item, kind, pathspec=None):
    """Return the checkout files, tracked or untracked, outside the walk directory, in which `git grep` with
    the options given finds the pattern."""
    command = ["git", "-C", str(top), "grep", "--untracked", "-l", *options, "-e", pattern]
    if pathspec:
        command += ["--", pathspec]
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode not in (0, 1):
        facts = dict(code=result.returncode, top=top, item=item, error=result.stderr.strip())
        raise EvidenceCheckFailed(
            GIT_GREP_FAILED.format(**facts, command=check_command_with_cwd(top, "--not-asked", str(kind))),
            GIT_GREP_FAILED_REASON.format(**facts))
    return {path for path in result.stdout.split("\n") if path and not path.startswith("docs/walk/")}


def spellings(name):
    """The name, lowercased, and, when it has two or more words, its words joined by hyphens, by underscores and
    by nothing; a digit run is split both ways, kept with the letters before it and as a word of its own, so
    `sha256_of` gives both `sha256-of` and `sha-256-of`."""
    found = {name.lower()}
    for pattern in (r"[A-Z]+[0-9]*(?![a-z])|[A-Z]?[a-z]+[0-9]*|[0-9]+", r"[A-Z]+(?![a-z])|[A-Z]?[a-z]+|[0-9]+"):
        parts = [part.lower() for part in re.findall(pattern, name)]
        if len(parts) > 1:
            found |= {separator.join(parts) for separator in ("-", "_", "")}
    return sorted(found)


def files_naming(top, name, item, kind):
    """Return the files outside the walk directory that hold one of the name's spellings, ignoring case,
    anywhere: a name written `poem-list` in prose is `poem_list_path` or `PoemList` in code."""
    found = set()
    for spelling in spellings(name):
        found |= files_matching(top, ["-i", "-F"], spelling, item, kind)
    return found


def glossary_entry_files(top, name, item, kind):
    """Return the glossary files with an entry whose term is the name, as in `- **poem-index** — ...` or
    `- **poem-index (aka PI)** — ...`; a name a glossary only mentions, such as an example of a bad name, is not one
    it lists."""
    escaped = re.sub(r"([.\[\]()*+?{}|^$\\])", r"\\\1", name)
    return files_matching(top, ["-i", "-E"], rf"^- \*\*{escaped}( \(aka [^)]*\))?\*\*", item, kind, GLOSSARY_FILES)


def not_asked_problems(kind, rating, lines, marks, top, item):
    """Return the lines saying why the item cannot be settled as the row given, from what code can check."""
    found = evidence(lines)
    # .get, because a read of the defaultdict would make a missing touches line look present.
    facts = NotAskedEvidence(kind, rating, found, words(found.get(TOUCHES, [])), words(found.get(TEST, [])), lines,
                             marks, top, item)
    return [problem for check in no_answer_case(kind).checks for problem in check(facts)]


def not_system_glossary_problems(touched, top, item):
    """Return a problem for each touched path that is not a system glossary git tracks in the checkout at top.

    Not handled: the hashtag glossary, which lists hashtags, not system-terms, is taken as a system glossary here, so an
    item touching only it can settle as kind 7."""
    glossaries_listed = load_module("system_glossaries_listed_on_the_project_glossary_test",
                                    SYSTEM_GLOSSARIES_LISTED_FILE)
    project_glossary = glossaries_listed.PROJECT_GLOSSARY_RELATIVE_PATH
    try:
        tracked = set(glossaries_listed.glossary_paths_git_tracks(top)) - {project_glossary}
    except glossaries_listed.CouldNotListGlossaries as error:
        raise EvidenceCheckFailed(
            GIT_LS_FILES_GLOSSARIES_FAILED.format(error=error, item=item,
                                                  command=check_command_with_cwd(top, "--not-asked", "7")),
            GIT_LS_FILES_GLOSSARIES_FAILED_REASON.format(error=error, item=item))
    root = Path(top).resolve()
    problems = []
    for path in touched:
        try:
            relative = (root / path).resolve().relative_to(root).as_posix()
        except ValueError:
            relative = None
        if relative not in tracked:
            problems.append(NOT_ASKED_NOT_SYSTEM_GLOSSARY_PROBLEM.format(touches=TOUCHES, path=path, top=top,
                                                                         project_glossary=project_glossary))
    return problems


def marker_reader_pattern(marker):
    """The `git grep -E` pattern for code that reads `marker`: the marker whole; or a part of it that ends just
    before a `-`, as `\\b` patterns read `#approval_walk_paused` in `#approval_walk_paused-note`; or a part that
    ends with `_` and is followed by no letter or digit, as `#case_against_[a-z_]+` reads `#case_against_strong`.
    A marker is otherwise found only whole: `#new` is not `#new_if_d`, nor `#newer`."""
    parts = [f"{marker}([^A-Za-z0-9_-]|$)"]
    for end, character in enumerate(marker):
        if character == "-":
            parts.append(f"{marker[:end]}([^A-Za-z0-9_-]|$)")
        elif character == "_":
            parts.append(f"{marker[:end + 1]}([^A-Za-z0-9]|$)")
    return "|".join(f"({part})" for part in parts)


def glossary_term_or_marker_problems(found, touched, top, item):
    """Return why a kind 6 item, a glossary term put in or a hashtag marker added to Markdown prose, cannot settle.

    Not handled: an item that adds a hashtag no page uses yet. The hashtag glossary test then needs the hashtag
    glossary to list it, and naming that glossary in `#not_asked_touches` is refused here, so such an item is asked."""
    problems = []
    terms = [name for value in found[GLOSSARY_TERM] for name in rename_names(value)]
    markers = [HASHTAG_MARKER_CLOSING_HASH.sub(r"\1", value) for value in words(found[ADDED_HASHTAG_MARKER])]
    if not terms and not markers:
        problems.append(MissingEvidenceLine(NOT_ASKED_NO_TERM_OR_MARKER_PROBLEM.format(term=GLOSSARY_TERM,
                                                                                       marker=ADDED_HASHTAG_MARKER)))
    for path in touched:
        if not path.endswith(".md") or fnmatch.fnmatch(Path(path).name, GLOSSARY_FILES):
            problems.append(NOT_ASKED_GLOSSARY_OR_NOT_MARKDOWN_PROBLEM.format(touches=TOUCHES, path=path))
    for term in terms:
        if not glossary_entry_files(top, term, item, 6):
            problems.append(NOT_ASKED_TERM_NOT_IN_GLOSSARY_PROBLEM.format(term=term, pattern=GLOSSARY_FILES))
    for value in markers:
        if not HASHTAG_MARKER.fullmatch(value):
            problems.append(NOT_ASKED_MARKER_SHAPE_PROBLEM.format(value=value, marker=ADDED_HASHTAG_MARKER))
            continue
        readers = sorted(files_matching(top, ["-E", "-i"], marker_reader_pattern(value), item, 6, NOT_MARKDOWN_FILES))
        if readers:
            problems.append(NOT_ASKED_MARKER_READ_PROBLEM.format(value=value, files=", ".join(readers)))
    return problems


def now_over_later_problems(walk_finder, minutes, value, numbers, total, parser):
    """Return (walk-document path, one line for each kind of choice besides now or later that the item holds:
    `Part N.` paragraphs, `Option N` lines and `#new_if_d` marks, each with its 1-based line numbers)."""
    document, text, tokens, ranges, _ = item_line_ranges(walk_finder, minutes, value, numbers, total, parser)
    lines = walk_finder.prose_lines(text, parser, tokens)
    hook = load_module("walk_me_through_user_short_answer_hook", SHORT_ANSWER_HOOK_FILE)
    found = {
        NOW_OVER_LATER_PARTS: [line for line, _ in hook.part_starts(tokens)
                               if any(first <= line < end for first, end in ranges)],
        NOW_OVER_LATER_OPTIONS: [number for first, end in ranges for number in range(first, end)
                                 if OPTION_LINE.match(lines[number])],
        NOW_OVER_LATER_NEW_IF_D: [mark.number for mark in new_marks(text, tokens, ranges, lines)
                                  if mark.mark == NEW_IF_D_MARK],
    }
    return document, [problem.format(lines=", ".join(str(number + 1) for number in sorted(set(numbers))))
                      for problem, numbers in found.items() if numbers]


def already_decided_answer_set(arguments):
    """Set the answer --already-decided gives after USER_RULING on the arguments, D as --disapproved does; raise
    Failure, writing nothing, for any other than nothing, A or D."""
    answers = arguments.already_decided_answers
    if len(answers) > 1 or any(answer.upper() not in ALREADY_DECIDED_WHOLE_ANSWERS for answer in answers):
        raise Failure(ALREADY_DECIDED_ANSWERS_PROBLEM.format(answers=" ".join(f"`{answer}`" for answer in answers)))
    arguments.disapproved = [answer.upper() for answer in answers] == ["D"]


def refuse_a_ruling_found_only_in_walk_minutes_or_a_handoff_dialog_and_too_old(citation, item, walk_finder):
    """Raise Failure for an --already-decided citation that cites no place in a standing document and whose ruling
    is older than RULING_DAYS_APPLIED days, or has no date this function can read."""
    if STANDING_DOCUMENT_PLACE_CITED.search(QUOTATION.sub("", citation)):
        return
    dates = []
    for text in RULING_DATE.findall(citation):
        with contextlib.suppress(ValueError):
            dates.append(datetime.date.fromisoformat(text))
    spanned = walk_finder.text_wrapped_as_markdown_code_span(citation)
    if not dates:
        raise Failure(RULING_UNDATED.format(item=item, citation=spanned, limit=RULING_DAYS_APPLIED))
    earliest = min(dates)
    days = (datetime.date.today() - earliest).days
    if days > RULING_DAYS_APPLIED:
        raise Failure(RULING_TOO_OLD.format(item=item, citation=spanned, date=earliest.isoformat(), days=days,
                                            limit=RULING_DAYS_APPLIED))


def check(arguments):
    if arguments.bump is not None:
        return bump(arguments)
    if arguments.now_over_later_already_decided:
        arguments.already_decided = NOW_OVER_LATER_USER_RULING_CITATION
    if arguments.already_decided is not None:
        already_decided_answer_set(arguments)
    part_numbers = [number for number, _ in arguments.part_answer or []]
    repeated = sorted({number for number in part_numbers if part_numbers.count(number) > 1})
    if repeated:
        raise Failure(PART_REPEATED.format(parts=", ".join(f"part {number}" for number in repeated)))
    walk_finder = load_walk_finder()
    top, minutes, value, parser = the_open_walk(walk_finder, arguments.cwd)
    item, numbers, total = waiting_items(walk_finder, value, minutes)
    if numbers[1:]:
        raise Failure(CHECK_SEVERAL_WAITING.format(minutes=minutes, item=item, one_item_line=NEXT_MARKER_LINE.format(
            value=f"item <number>{f' of {total}' if total else ''}")))
    words = " ".join((arguments.user_reply_as_typed or "").split())
    moved_on_no_decision_command = check_command_with_cwd(top, "--moved-on-no-decision", "--user-reply-as-typed",
                                                          words)
    not_shown_flag = ("--not-asked" if arguments.not_asked is not None
                      else NOW_OVER_LATER_FLAG if arguments.now_over_later_already_decided
                      else "--already-decided" if arguments.already_decided is not None
                      else "--moved-on" if arguments.moved_on is not None else None)
    if not_shown_flag and words:
        raise Failure(USER_WORDS_NOT_ASKED.format(flag=not_shown_flag))
    if not not_shown_flag and not words:
        raise Failure(USER_WORDS_MISSING.format(command=check_command_with_cwd(top, *check_words(arguments))))
    if NAVIGATION_WORD_ALONE.match(words) and not arguments.moved_on_no_decision:
        raise Failure(NAVIGATION_WORD_REFUSED.format(words=words, item=item,
                                                     answered=answered_word(arguments, walk_finder),
                                                     command=moved_on_no_decision_command))
    pending = unclosed_last_answer(walk_finder, minutes, parser) if not_shown_flag in SETTLING_FLAGS else None
    if pending:
        raise Failure(SECOND_SETTLING_REFUSED.format(item=item, flag=not_shown_flag, minutes=minutes,
                                                     pending=pending["item"],
                                                     close=step_command_with_cwd(top, "close"),
                                                     commands=answer_check_commands(top)))
    if arguments.already_decided is not None and not arguments.now_over_later_already_decided:
        refuse_a_ruling_found_only_in_walk_minutes_or_a_handoff_dialog_and_too_old(arguments.already_decided, item,
                                                                                    walk_finder)
    if arguments.now_over_later_already_decided:
        document, problems = now_over_later_problems(walk_finder, minutes, value, numbers, total, parser)
        if problems:
            raise Failure(NOW_OVER_LATER_REFUSED.format(item=item, document=document, problems="\n".join(problems)))
    in_his_words = USER_WORDS.format(words=walk_finder.text_wrapped_as_markdown_code_span(words)) if words else ""
    document, lines, marks, unreadable, tag_comments_kept = item_lines(walk_finder, minutes, value, numbers, total,
                                                                       parser)
    rating = case_against_rating(lines, item, document, arguments, top)
    rated = CASE_AGAINST_HASHTAG.format(rating=rating.replace(" ", "_")) if rating else ""
    recommendation = walk_finder.approval_walk_item_last_recommendation_text_from_item_lines(lines)
    if arguments.moved_on_no_decision and recommendation is not None:
        raise Failure(MOVED_ON_NO_DECISION_REFUSED.format(
            item=item, recommendation=recommendation,
            commands=answer_check_commands(top)))
    hidden = (walk_finder.approval_walk_item_last_recommendation_text_from_item_lines(tag_comments_kept)
              if arguments.moved_on_no_decision and recommendation is None else None)
    if hidden is not None:
        raise Failure(MOVED_ON_NO_DECISION_HIDDEN_RECOMMENDATION.format(
            item=item, document=document, recommendation=hidden, command=moved_on_no_decision_command))
    if arguments.deferred or arguments.moved_on_no_decision or arguments.moved_on is not None:
        now = datetime.datetime.now().astimezone()
        no_change = ((CHECK_MOVED_ON_SHOWN_MINUTES if items_shown_to_user(walk_finder, minutes, numbers, parser)
                      else CHECK_MOVED_ON_MINUTES) if arguments.moved_on is not None else CHECK_DEFERRED_MINUTES)
        append_to_minutes(minutes, [no_change.format(item=item, answered=answered_word(arguments, walk_finder),
                                                     rating=rated,
                                                     words=in_his_words, date_and_time=minutes_time(now))])
        print(CHECK_CLOSE_LINE.format(command=step_command_with_cwd(top, "close")))
        return 0
    if unreadable:
        raise Failure(UNREADABLE_NEW_MARKS.format(item=item, document=document, problems="\n".join(unreadable),
                                                  command=check_command_with_cwd(top, *check_words(arguments))))
    if arguments.not_asked is not None:
        if arguments.not_asked == NOT_ASKED_RATED_NONE and rating == NOT_ASKED_RATED_WEAK:  # pragma: no mutate, no rating sorts after "weak" ("very strong" sorts before it), so >= matches only weak
            raise Failure(NOT_ASKED_WEAK_GROUND_NOT_NAMED.format(item=item, weak_ground_choices="\n".join(
                NOT_ASKED_WEAK_GROUND_CHOICE.format(ground=ground,
                                                    command=check_command_with_cwd(top, "--not-asked", value))
                for value, ground in NOT_ASKED_GROUNDS.items())))
        if arguments.not_asked in NOT_ASKED_WEAK_GROUND_LABELS and rating == NOT_ASKED_RATED_NONE:
            raise Failure(NOT_ASKED_WEAK_GROUND_FOR_RATED_NONE.format(
                item=item, kind=arguments.not_asked,
                command=check_command_with_cwd(top, "--not-asked", NOT_ASKED_RATED_NONE)))
        problems = not_asked_problems(arguments.not_asked, rating, lines, marks, top, item)
        if problems:
            raise Failure(NOT_ASKED_REFUSED.format(item=item, kind=arguments.not_asked,
                                                   label=not_asked_label(arguments.not_asked),
                                                   grounds=not_asked_grounds(arguments.not_asked),
                                                   problems="\n".join(problems),
                                                   document=document,
                                                   command=check_command_with_cwd(top, "--not-asked",
                                                                                  str(arguments.not_asked))))
    texts = proposed_texts(marks, marks_the_answer_adds(arguments))
    log_store_records, tried = (None, []) if arguments.cold_read_records and arguments.counts_log \
        else reachable_log_store_records()
    record_directories = arguments.cold_read_records or (
        [top / RECORDS_DIRECTORY_NAME] + ([log_store_records] if log_store_records else []))
    walk_name = minutes.name[:-len(walk_finder.MINUTES_SUFFIX)]
    statuses, already_done, had_to_be_run, problems = [], 0, 0, []
    counted = collections.Counter()
    for mark, text in texts:
        counted[mark] += 1
        number = counted[mark]
        record = fast_read_record_holding(text, record_directories, walk_name)
        if record is not None:
            already_done += 1
            statuses.append(STATUS_ALREADY_DONE.format(mark=mark, number=number, excerpt=excerpt(walk_finder, text),
                                                       record=record))
            continue
        name = walk_fast_read_name(walk_name, item, mark, number)
        try:
            record, notes = run_fast_read(text, name, arguments.fast_read_program,
                                          STOP_SIGNAL_CHECK_AFTER_REMOVAL.format(
                                              command=check_command_with_cwd(top, *check_words(arguments))))
        except FastReadFailed as failure:
            print("\n".join([failure.args[0]] + [
                line.format(command=check_command_with_cwd(top, *check_words(arguments)))
                for line in FAST_READ_FAILED_LINES]))
            return 1
        had_to_be_run += 1
        statuses.append(STATUS_HAD_TO_BE_RUN.format(mark=mark, number=number, excerpt=excerpt(walk_finder, text),
                                                    record=record)
                        + "".join(STATUS_FAST_READ_NOTE.format(note=note) for note in notes))
        for note in notes:
            if note.startswith(FAST_READ_RECORD_NOT_SHIPPED_MARKERS):
                problems += [line.format(mark=mark, number=number, note=note, record=record,
                                         ship_command=shlex.join(["python3", str(RECORD_SHIPPER_FILE), str(record)]))
                             for line in RECORDS_NOT_SHIPPED]
    if not texts:
        statuses.append(NO_PROPOSED_TEXT)
    now = datetime.datetime.now().astimezone()
    not_asked = arguments.not_asked is not None or arguments.already_decided is not None
    answer_minutes = CHECK_NOT_ASKED_MINUTES if not_asked else CHECK_MINUTES
    append_to_minutes(minutes, [answer_minutes.format(item=item, answered=answered_word(arguments, walk_finder),
                                                      hashtag=answer_hashtag(arguments), rating=rated,
                                                      words=in_his_words, date_and_time=minutes_time(now))]
                      + [STATUS_LINE_PREFIX + status for status in statuses])
    output = list(statuses)
    if had_to_be_run:
        output += [line.format(document=document, item=item) for line in CHECK_JUDGEMENT_LINES]
    if arguments.not_asked is not None:
        unchecked = no_answer_case(arguments.not_asked).unchecked or NOT_ASKED_UNCHECKED.format(
            grounds=not_asked_grounds(arguments.not_asked))
        output += [line.format(item=item, label=not_asked_label(arguments.not_asked), unchecked=unchecked)
                   for line in NOT_ASKED_JUDGEMENT_LINES]
        if arguments.not_asked in NOT_ASKED_WEAK_GROUND_LABELS:
            output.append(NOT_ASKED_WEAK_JUDGEMENT_LINE.format(item=item))
        if arguments.not_asked == DROPPED_PROPOSAL_VALUE:
            output.append(NOT_ASKED_DROPPED_PROPOSAL_JUDGEMENT_LINE.format(item=item))
    output.append(CHECK_CLOSE_LINE.format(command=step_command_with_cwd(top, "close")))
    log = arguments.counts_log or (log_store_records.parent / COUNTS_LOG_FILE_NAME if log_store_records else None)
    try:
        if log is None:
            raise OSError(LOG_STORE_UNREACHABLE.format(paths=" or ".join(str(path) for path in tried)))
        with open(log, "a", encoding="utf-8") as file:
            file.write("\t".join([now.isoformat(timespec="seconds"), walk_name, item,
                                  f"texts={len(texts)}", f"already_done={already_done}",
                                  f"had_to_be_run={had_to_be_run}"]) + "\n")
    except OSError as error:
        problems += [line.format(log=log or "the log-store", error=error) for line in COUNTS_NOT_LOGGED]
    print("\n".join(output + problems))
    return 2 if problems else 0


def items_named(numbers, total):
    return f"item{'s' if numbers[1:] else ''} {' and '.join(numbers)} of {total}"


def item_reads_directory(walk_finder, minutes):
    return minutes.with_name(minutes.name[:-len(walk_finder.MINUTES_SUFFIX)] + ITEM_READS_DIRECTORY_SUFFIX)


def text_key(text):
    # Whitespace is kept: inside a code span or fenced code it changes what the user is shown.
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def write_json(path, value):
    """Write value to path whole: a reader sees the old file or the new one, never half of one."""
    temporary = path.with_name(path.name + ".writing")
    temporary.write_text(json.dumps(value), encoding="utf-8")
    os.replace(temporary, path)


def read_outcome(reads, key):
    """Return the outcome a read of the text keyed key wrote, or None while it has written none."""
    path = reads / f"{key}-outcome.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None


def worker_alive(reads, key):
    """Whether a read-ahead worker started for the text keyed key is still running."""
    started = reads / f"{key}-started.json"
    if not started.is_file():
        return False
    try:
        os.kill(json.loads(started.read_text(encoding="utf-8"))["pid"], 0)
    except ProcessLookupError:
        return False
    return True


def record_read(reads, key, item, text, outcome, number_predicted=False):
    """Keep the text read beside the read's outcome, for a later AFTER_FIXES_FLAG read to compare against.
    number_predicted marks a read ahead of an unnumbered item, whose number is only the one close expects to give it,
    until read_ahead_bound_to_item binds it to the item the read step uses it for."""
    (reads / f"{key}.md").write_text(text + "\n", encoding="utf-8")
    predicted = {NUMBER_PREDICTED: True} if number_predicted else {}
    write_json(reads / f"{key}-outcome.json", dict(outcome, item=item, finished=time.time(), **predicted))


def read_ahead_bound_to_item(reads, key, outcome, item):
    """Write and return the outcome of the read ahead at key as item's own read, NUMBER_PREDICTED false: the read
    step used it for item, so it stays item's read whatever title, text or number the item has later."""
    bound = dict(outcome, item=item, **{NUMBER_PREDICTED: False})
    write_json(reads / f"{key}-outcome.json", bound)
    return bound


def fast_read_outcome(text, name, fast_read_program, after_removal):
    """Fast-read the text and return the outcome a read-ahead worker writes: done with the report and the fast
    read's notes, or failed with its FAILED line. after_removal is as scratch_directory_removed_on_every_exit
    takes it."""
    try:
        record, notes = run_fast_read(text, name, fast_read_program, after_removal)
    except FastReadFailed as failure:
        return {"status": READ_FAILED, "failed": failure.args[0]}
    record_names = load_module("cold_read_record_names", RECORD_NAMES_FILE)
    report = record_names.cold_read_record_file_path_prefixed_name_else_name_before_prefix(
        record, record_names.COLD_READ_FAST_READ_REPORT_FILE_NAME)
    return {"status": READ_DONE, "report": str(report), "notes": notes}


def read_ahead_worker(arguments):
    """The detached process close starts: fast-read the text kept at --text-file and write its outcome."""
    reads, key = arguments.text_file.parent, arguments.text_file.stem
    text = arguments.text_file.read_text(encoding="utf-8").rstrip("\n")
    record_read(reads, key, arguments.item, text,
                fast_read_outcome(text, arguments.name, arguments.fast_read_program,
                                  STOP_SIGNAL_READ_AHEAD_AFTER_REMOVAL),
                arguments.item_number_predicted)
    return 0


def start_read_ahead(reads, item, text, name, fast_read_program, top, number_predicted=False):
    """Start a detached read-ahead worker on the text, unless a read of the same text was started or written
    before, whatever its outcome: a read ahead is never retried, so a failed one leaves the read to the read step."""
    key = text_key(text)
    if (reads / f"{key}-outcome.json").is_file() or (reads / f"{key}-started.json").is_file():
        return
    reads.mkdir(exist_ok=True)
    text_file = reads / f"{key}.md"
    text_file.write_text(text + "\n", encoding="utf-8")
    # Its own session, and no pipe to this process, so close returns at once and the read outlives it.
    with open(reads / f"{key}.log", "w", encoding="utf-8") as log:
        worker = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), READ_AHEAD_WORKER_STEP,
                                   "--text-file", str(text_file), "--item", item, "--name", name,
                                   "--fast-read-program", str(fast_read_program)]
                                  + ([ITEM_NUMBER_PREDICTED_FLAG] if number_predicted else []),
                                  stdin=subprocess.DEVNULL, stdout=log, stderr=log, cwd=top, start_new_session=True)
    write_json(reads / f"{key}-started.json", {"pid": worker.pid, "item": item})


def start_read_ahead_of_item_after(walk_finder, top, minutes, parser, numbers, total, fast_read_program):
    """Start the read ahead of the item the walk would present after the items numbered, if there is one.
    An unnumbered item is read as close will number it, with the number and M close would give it then.
    Return None, or a line saying why no read ahead could be started: the read ahead is a guess, so its
    failure never stops close or the read step."""
    named = items_named(numbers, total)
    try:
        count, order, summary, units, placing = walk_document_items(walk_finder, minutes, named, numbers, total,
                                                                    parser, WAITING_ITEM_READ_STEP, top)
        after = next_item(walk_finder, minutes, parser, order, summary, numbers, numbers, placing,
                          decided_now=numbers)
        if not after:
            return None
        number_predicted = isinstance(after[0], int)  # pragma: no mutate, next_item is given the same numbers as answered and waiting, so it names at most one item and after[-1] is after[0]
        if number_predicted:
            number = walk_finder.approval_walk_next_unnumbered_item_number(units)
            after_named = items_named([number], count)
            text = unnumbered_item_text_once_numbered(walk_finder, minutes, after[0], units, number, count)
        else:
            after_named = items_named(after, total)
            _, text = item_text(walk_finder, minutes, after_named, after, total, parser,
                                named_by=f"the item after {named}")
        walk_name = minutes.name[:-len(walk_finder.MINUTES_SUFFIX)]
        start_read_ahead(item_reads_directory(walk_finder, minutes), after_named, text,
                         walk_fast_read_name(walk_name, after_named), fast_read_program, top,
                         number_predicted=number_predicted)
    except Failure as problem:
        return READ_AHEAD_NOT_STARTED.format(item=named, problem=problem)
    return None


def tracked_names(top):
    """Return the paths `git ls-files` lists in top, their directories and their file names, or raise OSError."""
    result = subprocess.run(["git", "-C", str(top), "ls-files", "-z"], capture_output=True, text=True)
    if result.returncode != 0:
        raise OSError(f"exit {result.returncode}: {result.stderr.strip()}")
    names = set()
    for path in filter(None, result.stdout.split("\0")):
        parts = path.split("/")
        names.update("/".join(parts[:end]) for end in range(1, len(parts) + 1))
        names.add(parts[-1])
    return names


def is_fact(token, names):
    """Whether a changed token is a number, a path, a file or program name, or a link."""
    if re.search(r"\d", token) or "`" in token or "](" in token or "://" in token or re.search(AUTOLINK, token):
        return True
    core = token.strip(TOKEN_EDGE_PUNCTUATION).rstrip("/")
    return core in names or (bool(FILE_EXTENSION_END.search(core)) and not LETTER_ABBREVIATION.fullmatch(core))


def labelled_parts(text):
    """Return, for each fact label and the `#case_against` line, what the text holds from the label on."""
    lines = text.split("\n")
    parts = [squeezed(line[line.index(label):]) for label in FACT_LABELS for line in lines if label in line]
    return parts + [squeezed(line) for line in lines if CASE_AGAINST_LINE.match(line)]


def approval_walk_item_before_and_after_fixes_compare_for_changed_fact_words_needing_another_cold_read_fast_read(before, after, top):
    """Return the facts the change from before to after touches, as words to list; empty when it touches none.
    When `git ls-files` fails and any word changed, the list holds one line saying so instead of the names."""
    facts = [f"\"{part[:40]}\"" for part in
             sorted(set(labelled_parts(before)) ^ set(labelled_parts(after)))]
    old, new = FACT_TOKEN.findall(before), FACT_TOKEN.findall(after)
    changed = [token for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, old, new, autojunk=False).get_opcodes()
               if tag != "equal" for token in old[i1:i2] + new[j1:j2]]
    try:
        names = tracked_names(top)
    except OSError as error:
        return facts + [GIT_LS_FILES_FAILED.format(top=top, error=error)] if changed else facts
    return facts + [token for token in dict.fromkeys(changed) if is_fact(token, names)]


def waiting_on_item_prerequisite_lines(walk_finder, minutes, numbers, total, parser):
    """One WAITING_ON_ITEM_PREREQUISITE_LINE for each walk-document unit holding one of the items numbered, its
    heading read from the walk-document as it is on disk now."""
    document = minutes.with_name(minutes.name[:-len(walk_finder.MINUTES_SUFFIX)] + ".md")
    text = document.read_text(encoding="utf-8")
    lines = text.split("\n")
    return [WAITING_ON_ITEM_PREREQUISITE_LINE.format(
        item=items_named(unit[0], total), entry=json.dumps({"approval_walk_item_decided": {
            "approval_walk_minutes_file_path": str(minutes.resolve()),
            "approval_walk_item_heading": lines[unit[3]].strip()}}, ensure_ascii=False))
        for unit in walk_finder.item_unit_spans(text, parser) if set(unit[0]) & set(numbers)]


def latest_read(walk_finder, reads, numbers):
    """Return (key, outcome) of the latest read of the item numbered numbers that wrote its report, or None; a read
    ahead that no read step has used is no item's read. Matched by number, since a re-plan changes M in the label."""
    done = []
    for path in reads.glob("*-outcome.json") if reads.is_dir() else []:
        outcome = json.loads(path.read_text(encoding="utf-8"))
        if (walk_finder.parse_items(outcome["item"])[0] == numbers and outcome["status"] == READ_DONE
                and not outcome.get(NUMBER_PREDICTED)):
            done.append((outcome["finished"], path.name[:-len("-outcome.json")], outcome))
    return max(done)[1:] if done else None


def heading_body(walk_finder, text):
    """Return an item's text without its heading, which changes with M and the deferred note alone: a `#` heading
    line goes whole; a bold paragraph's first line keeps its text after the running count, which can hold the item's
    recommendation."""
    first, _, rest = text.partition("\n")
    if first.lstrip().startswith("#"):
        return blank_lines_stripped(rest)
    return blank_lines_stripped(item_title(walk_finder, first, with_text_after_title=True) + "\n" + rest)


def blank_lines_stripped(text):
    """The text without its leading and trailing blank lines; a first line's indentation stays, as an indented code
    block needs it to stay code."""
    lines = text.split("\n")
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    return "\n".join(lines)


def item_title(walk_finder, line, with_text_after_title=False):
    """The title an item's heading or opening line gives it: without its indentation, list or quotation mark, `#`
    marks, running count or the label item_opening_lines reads under a shared heading, deferred note, `revised`
    label and the emphasis delimiters around the count, which renumbering or revising the item does not change. A
    bold paragraph or list opening's title ends where its emphasis closes, as in `**Item 3 of 9: the first** More
    detail.`; with_text_after_title keeps the text after it, without the closing delimiter. A heading's text after
    the emphasis closes is its title's too, as in `## **Item 3 of 9: Keep this** (but not that)`."""
    line = walk_finder.approval_walk_item_heading_with_deferred_note_removed(line)
    line = re.sub(rf"^\s*{walk_finder.MARKDOWN_LINE_OPENING_LIST_OR_QUOTATION_MARK_PATTERN_TEXT}*", "", line)
    heading = line.startswith("#")
    line = line.lstrip("#").strip()
    count = walk_finder.HEADING_COUNT.match(line) or walk_finder.ITEM_LABEL.match(line)
    if not count:
        return line
    opener = re.match(r"[*_]*", line)[0]
    # One match reads the label at most once, through the finder's own label pieces; the emphasis can close before
    # the label, as in `**Item 3 of 9**: (revised) x`, or after it, as in `**Item 3 of 9 (revised):** x`.
    separators = r"[ :,.;]*"
    revised = walk_finder.APPROVAL_WALK_ITEM_HEADING_REVISED_LABEL_REGEX
    label = rf"(?:[\s,:;.\-\u2013\u2014]*{revised}[ :,.;\-\u2013\u2014]*)?"
    closer = re.escape(opener)
    opening = re.match(rf"{separators}(?:(?P<before>{closer}){separators}{label}|{label}(?P<after>{closer})"
                       rf"{separators}|{label})", line[count.end():], re.I)
    title = line[count.end() + opening.end():]
    closed = any(opening.groupdict().get(group) is not None for group in ("before", "after"))
    if closed or not opener:
        return title.rstrip()
    found = emphasis_closer(walk_finder, title, opener)
    if found is not None:
        after = title[found + len(opener):]
        title = title[:found] + (after if heading or with_text_after_title else "")
    return title.rstrip()


def emphasis_closer(walk_finder, text, opener):
    """The position in text of the delimiter run that closes the emphasis opener opened before it, or None, as
    markdown-it's delimiter scan reads each run, so `x ** 2` and `foo__bar` close nothing and `foo___` closes at its
    run's start; never a run inside a code span, which the scan does not see."""
    from markdown_it.rules_inline import StateInline
    code = [span.span() for span in walk_finder.CODE_SPAN.finditer(text)]
    state = StateInline(text, inline_delimiter_scan_parser(walk_finder), {}, [])
    for found in re.finditer(rf"{re.escape(opener[0])}+", text):
        at = found.start()
        if any(start <= at < end for start, end in code):
            continue
        scanned = state.scanDelims(at, opener[0] == "*")
        if scanned.can_close and scanned.length >= len(opener):
            return at
    return None


@functools.cache
def inline_delimiter_scan_parser(walk_finder):
    return walk_finder.markdown_parser()


def markdown_with_link_syntax_dropped(markdown, parser, hook):
    """The inline Markdown with each link's text kept, its link syntax gone and the rest's emphasis and code spans as
    written, as an earlier message quoting the title would give it; unlike the closing line's point, nothing is
    escaped. hook is the short-answer hook's module, whose markdown_it_code_inline_token_to_code_span_markdown_with_padding_restored rebuilds a code span."""
    pieces = []
    for token in parser.parseInline(markdown)[0].children:
        if token.type in ("link_open", "link_close"):
            continue
        if token.type == "code_inline":
            pieces.append(hook.markdown_it_code_inline_token_to_code_span_markdown_with_padding_restored(token))
        elif token.type in ("softbreak", "hardbreak"):
            pieces.append(" ")
        else:
            pieces.append(token.markup or token.content)
    return "".join(pieces)


def earlier_read_texts_of_item(walk_finder, minutes, value, numbers, total, parser, reads, command):
    """Return [(key, outcome, text)] for each text of the waiting item that a read wrote its report for, oldest read
    first. A read ahead of an unnumbered item that no read step has used, whatever number close expected to give
    it, counts only when its text's title is the item's title now and no other item's. An item that shares its
    heading with others, or several waiting items, have none. Raise Failure, before anything is written, when the
    copy of a text read under the item's number is missing."""
    if len(numbers) != 1 or not reads.is_dir():
        return []
    document = minutes.with_name(minutes.name[:-len(walk_finder.MINUTES_SUFFIX)] + ".md")
    # A walk-document missing, or without the item, is walk_document_items' refusal to give, naming the minutes'
    # `#next_to_present` line.
    try:
        text = document.read_text(encoding="utf-8")
        units = walk_finder.item_unit_spans(text, parser)
        unit = walk_finder.waiting_item_units(document, value, numbers, total, parser, units)[1][0]
    except (OSError, walk_finder.UnusableRange):
        return []
    if len(unit[0]) != 1:
        return []
    lines = text.split("\n")
    title = item_title(walk_finder, lines[unit[3]])
    title_unique = [item_title(walk_finder, lines[other[3]]) for other in units].count(title) == 1
    item = items_named(numbers, total or unit[1])
    earlier = []
    for path in reads.glob("*-outcome.json"):
        outcome = json.loads(path.read_text(encoding="utf-8"))
        predicted = outcome.get(NUMBER_PREDICTED)
        # Every outcome's item was written by items_named, so it always parses.
        numbered = walk_finder.parse_items(outcome["item"])[0] == numbers
        if outcome["status"] != READ_DONE or not (numbered or (predicted and title_unique)):
            continue
        key = path.name[:-len("-outcome.json")]
        copy = reads / f"{key}.md"
        if not copy.is_file():
            # Without its copy, a read ahead under another number cannot be told to be this item's.
            if not numbered:
                continue
            raise Failure(EARLIER_TEXT_COPY_MISSING.format(
                item=item, report=outcome["report"], document=document, copy=copy,
                outcome=reads / f"{key}-outcome.json", target=Path(outcome["report"]).parent / "target",
                command=command))
        copied = copy.read_text(encoding="utf-8")
        if predicted and not (title_unique and item_title(walk_finder, copied.split("\n", 1)[0]) == title):
            continue
        earlier.append((outcome["finished"], key, outcome, copied))
    return [entry[1:] for entry in sorted(earlier)]


def earlier_read_texts_kept_as_withdrawn_versions(walk_finder, minutes, value, numbers, total, parser, earlier, item,
                                                  live_text, command, kept_line=EARLIER_TEXT_KEPT):
    """Put each of earlier, as earlier_read_texts_of_item returns them, that is neither the live text nor already
    kept, under a WITHDRAWN_VERSION_HEADING after the item's live version, and record in its read's outcome the
    heading it is kept under, also for one found already kept; return kept_line for each one put there now. Raise
    Failure, naming command to run again, when an outcome cannot be written."""
    if not earlier:
        return []
    document = minutes.with_name(minutes.name[:-len(walk_finder.MINUTES_SUFFIX)] + ".md")
    text = document.read_text(encoding="utf-8")
    unit = walk_finder.waiting_item_units(document, value, numbers, total, parser)[1][0]
    lines = text.split("\n")
    kept = withdrawn_versions_inserted_below_live_version(walk_finder, parser, lines, unit[3], numbers[0], earlier,
                                                          item, live_text, document, kept_line)
    if any(line is not None for _, _, _, line in kept):
        document.write_text("\n".join(lines), encoding="utf-8")
    reads = item_reads_directory(walk_finder, minutes)
    for key, outcome, heading, _ in kept:
        path = reads / f"{key}-outcome.json"
        try:
            write_json(path, {**outcome, WALK_ITEM_READ_OUTCOME_WITHDRAWN_VERSION_HEADING_TEXT_KEPT_UNDER_KEY: heading})
        except OSError as error:
            raise Failure(EARLIER_TEXT_KEPT_NOT_RECORDED.format(
                item=item, document=document, outcome=path, error=error, reads=reads, command=command)) from error
    return [line for _, _, _, line in kept if line is not None]


def withdrawn_versions_inserted_below_live_version(walk_finder, parser, lines, first, number, earlier, item,
                                                   live_text, document, kept_line, inserted_heading_lines=None):
    """Insert into lines, a walk-document's, each of earlier, as (key, outcome, text), whose outcome records no
    keeping and whose body is neither live_text's nor the whole body of a version already kept below the live version
    of the unit whose heading is line first, under a WITHDRAWN_VERSION_HEADING for item number; return (key, outcome,
    heading, kept_line) for each, and append each inserted heading's line index to inserted_heading_lines when it is
    given. For one whose body is already kept there, return (key, outcome, that version's heading line, None), so
    that its keeping is recorded too, such as after a run whose outcome write failed.

    The versions kept below are the sections under the top-level Withdrawn headings that name item number or no item,
    such as `#### Withdrawn version 1 of this item`, from the live version's end to the next item or the next
    heading as high as the unit's own heading or higher, such as a `## Part 2` below a `### Item` heading, which also
    bounds where a version is inserted."""
    kept = []
    for key, outcome, copied in earlier:
        if (outcome.get(WALK_ITEM_READ_OUTCOME_WITHDRAWN_VERSION_HEADING_TEXT_KEPT_UNDER_KEY)
                or outcome.get(WALK_ITEM_READ_OUTCOME_WITHDRAWN_VERSION_HEADING_TEXT_KEPT_UNDER_OLD_KEY)):
            continue
        body = heading_body(walk_finder, copied)
        text = "\n".join(lines)
        spans = walk_finder.item_unit_spans(text, parser)
        start = next(other[4] for other in spans if other[3] == first)
        tokens = parser.parse(text)
        # (first line, line after the heading, level, text) of each top-level heading; a setext heading's underline
        # is inside it.
        headings = [(token.map[0], token.map[1], walk_finder.heading_level(token), tokens[index + 1].content)
                    for index, token in enumerate(tokens)
                    if token.type == "heading_open" and token.map is not None and token.level == 0]
        level = next((found[2] for found in headings if found[0] == first), 0)
        below = min([other[3] for other in spans if other[3] > first] + [len(lines)]
                    + [found[0] for found in headings if found[0] >= start and found[2] <= level
                       and not walk_finder.WITHDRAWN_HEADING.match(found[3])])
        withdrawn = [found for found in headings if start <= found[0] < below
                     and walk_finder.WITHDRAWN_HEADING.match(found[3])
                     and number in (walk_finder.withdrawn_heading_items(found[3]) or {number})]
        kept_bodies = {as_written_key("\n".join(lines[found[1]:end])):
                       lines[found[0]].strip()
                       for found, end in zip(withdrawn, [*(later[0] for later in withdrawn[1:]), below])}
        if squeezed(body) in (squeezed(heading_body(walk_finder, live_text)), ""):
            continue
        kept_heading = kept_bodies.get(as_written_key(body))
        if kept_heading is not None:
            kept.append((key, outcome, kept_heading, None))
            continue
        version = 1 + len(withdrawn)
        while below > 0 and not lines[below - 1].strip():
            below -= 1
        heading = WITHDRAWN_VERSION_HEADING.format(version=version, number=number)
        # One element per line: item_unit_spans counts lines, so a later span must see each of them.
        lines[below:below] = ["", heading, ""] + body.split("\n")
        if inserted_heading_lines is not None:
            inserted_heading_lines.append(below + 1)
        kept.append((key, outcome, heading, kept_line.format(item=item, report=outcome.get("report"),
                                                             document=document, heading=heading)))
    return kept


def approval_walk_item_new_texts(walk_finder, parser, text):
    """Return the `#new` texts of text, an item's lines, outside code and with a text, whitespace runs squeezed."""
    tokens = parser.parse(text)
    marks = new_marks(text, tokens, [(0, len(text.split("\n")))], walk_finder.prose_lines(text, parser, tokens))
    return [found for _, found in proposed_texts(marks, (NEW_MARK,))]


def approval_walk_item_and_sub_steps_live_units(walk_finder, parser, document, whole_number, total, waiting_unit):
    """Return (the walk-document's text, the units of the live versions of the whole item whole_number and its
    sub-steps, as waiting_item_units and approval_walk_item_sub_step_units_below_item_in_walk_document find them), so
    that a sub-step under a Withdrawn heading, or of an older version, is left out; a unit ends at the first Withdrawn
    heading below it. When no heading counts the whole item, the units are its sub-steps' that the same rule takes
    from the first of the run of sub-step units waiting_unit is in, whatever M each gives."""
    text = document.read_text(encoding="utf-8")
    units = walk_finder.item_unit_spans(text, parser)
    try:
        whole = walk_finder.waiting_item_units(document, f"item {whole_number}", [whole_number], total, parser,
                                               units)[1][0]
    except walk_finder.UnusableRange:
        # Under a heading with no running count, such as `## Item 3: the plan`, the sub-steps are taken from the
        # first of their run, so reading 3.1 and then 3.2 compares the same texts.
        position = start = units.index(waiting_unit)
        while position:
            position -= 1
            if any(number.startswith(whole_number + ".") for number in units[position][0]):
                start = position
            elif not walk_finder.approval_walk_unit_is_unnumbered_item(units[position]):
                break
        first = units[start]
        whole = ([whole_number], first[1], None, first[3] - 1, first[3])
        family = walk_finder.approval_walk_item_sub_step_units_below_item_in_walk_document(units, whole,
                                                                                           [whole_number])
        return text, family if waiting_unit in family else [*family, waiting_unit]
    return text, [whole, *walk_finder.approval_walk_item_sub_step_units_below_item_in_walk_document(
        units, whole, [whole_number])]


def approval_walk_item_and_sub_steps_live_versions_texts(walk_finder, parser, document, whole_number, total,
                                                         waiting_unit):
    """Return (the walk-document's lines, [(unit, its text)]) for each unit
    approval_walk_item_and_sub_steps_live_units returns: its heading line and, from a unit whose heading also names
    another item, such as `### Items 3.1 and 4.1 of 9`, only the lines of item whole_number and its sub-steps.

    Not handled: a `#new` line indented four spaces that continues a paragraph, such as one holding a bold running
    count, is prose in the walk-document, but own_lines_of_unit starts each run of lines after a blank line, so in
    the text returned it is an indented code block, and an edit to it is not counted as a revision."""
    text, units = approval_walk_item_and_sub_steps_live_units(walk_finder, parser, document, whole_number, total,
                                                              waiting_unit)
    lines = text.split("\n")
    openings = []
    texts = []
    for unit in units:
        own = [number for number in unit[0] if number == whole_number or number.startswith(whole_number + ".")]
        body = walk_finder.own_lines_of_unit(text, parser, lines, unit, openings,
                                             own if len(own) < len(unit[0]) else None, keep_setext_underline=True)
        texts.append((unit, "\n".join([lines[unit[3]], *body])))
    return lines, texts


def approval_walk_item_and_sub_steps_live_versions_proposed_new_texts_read_sorted(
        walk_finder, parser, document, whole_number, total, waiting_unit):
    """Return the `#new` texts of the live versions of item whole_number and its sub-steps, sorted, so that a text
    moved to another sub-step unchanged, as a split into sub-steps moves one, is the same list."""
    _, texts = approval_walk_item_and_sub_steps_live_versions_texts(walk_finder, parser, document, whole_number,
                                                                    total, waiting_unit)
    return sorted(found for _, text in texts for found in approval_walk_item_new_texts(walk_finder, parser, text))


def approval_walk_item_proposed_text_revisions_counted(reads, whole_number, new_texts, restart, item, command):
    """Return how many times the `#new` texts of item whole_number and its sub-steps have changed since the count
    started, counting this step's new_texts against those the last step saw, and record new_texts. A list with no text,
    as while an item's sub-step that proposes nothing is read, neither counts nor replaces the last list, so
    the first text an item proposes is no revision. restart starts the count again from new_texts. Raise Failure
    when the record cannot be read."""
    path = reads / PROPOSED_TEXT_REVISIONS_FILE.format(number=whole_number)
    seen = {"new_texts": [], "revisions": 0}
    if path.is_file() and not restart:
        try:
            seen = json.loads(path.read_text(encoding="utf-8"))
            if not (isinstance(seen, dict) and isinstance(seen.get("new_texts"), list)
                    and isinstance(seen.get("revisions"), int)):
                raise ValueError("it holds no `new_texts` list and `revisions` count")
        except (OSError, ValueError) as error:
            raise Failure(PROPOSED_TEXT_REVISIONS_UNREADABLE.format(
                item=item, path=path, whole_number=whole_number, error=error, command=command)) from error
    if new_texts and seen["new_texts"] and new_texts != seen["new_texts"]:
        seen["revisions"] += 1
    if new_texts:
        seen["new_texts"] = new_texts
    try:
        reads.mkdir(exist_ok=True)
        write_json(path, seen)
    except OSError as error:
        raise Failure(PROPOSED_TEXT_REVISIONS_NOT_WRITTEN.format(
            item=item, path=path, whole_number=whole_number, error=error, reads=reads, command=command)) from error
    return seen["revisions"]


def approval_walk_item_linked_files(text, ned_box_home, mac_mount):
    """Return a line for each link target in text, in order and once each; a link into the Mac's mount of ned-box's
    home also gives the path on ned-box."""
    lines = []
    for match in MARKDOWN_LINK_TARGET.finditer(text):
        link = match[1] or match[2]
        path = urllib.parse.unquote(link[len("file://"):]) if link.startswith("file://") else None
        line = (FRESH_AGENT_REWRITE_ON_NED_BOX.format(link=link, path=ned_box_home + path[len(mac_mount):])
                if path and path.startswith(mac_mount + "/") else link)
        if f"- {line}" not in lines:
            lines.append(f"- {line}")
    return lines


def approval_walk_item_user_words_in_minutes(walk_finder, parser, minutes_text, whole_number, titles):
    """Return each line of the walk-minutes that holds the user's words and names, before his words, item whole_number, one of its sub-steps, one of titles, or an
    item whose held answer raised item whole_number, or that waited when the user bumped it, or that raised an item
    that did, with its sub-steps: the user's reply on that item is what the raised item is about."""
    wholes = {whole_number}
    raisers = [({number.split(".")[0] for number in held}, {number.split(".")[0] for number in raised})
               for _, held, _, raised in held_answers(walk_finder, minutes_text, parser)]
    for line in walk_finder.prose_lines(minutes_text, parser):
        match = BUMP_MINUTES_LINE.match(line)
        with contextlib.suppress(walk_finder.UnusableRange):
            if match:
                raisers.append(({number.split(".")[0] for number in walk_finder.parse_items(match["waiting"])[0]},
                                {number.split(".")[0] for number in walk_finder.parse_items(match["bumped"])[0]}))
    while True:
        raising = {number for held, raised in raisers if raised & wholes for number in held} - wholes
        if not raising:
            break
        wholes |= raising
    found = []
    for line in minutes_text.split("\n"):
        # Only the item named ahead of his words counts: his words, or an agent's note quoting another walk, can
        # name any item number.
        naming = line.split(USER_WORDS_IN_MINUTES_PHRASE, 1)[0]
        if naming == line:
            continue
        named = set()
        for numbers in walk_finder.WITHDRAWN_HEADING_ITEMS.finditer(naming):
            with contextlib.suppress(walk_finder.UnusableRange):
                named.update(number.split(".")[0] for number in walk_finder.expand_numbers(numbers[1]))
        if named & wholes or any(title and title.lower() in naming.lower() for title in titles):
            found.append(line)
    return found


def approval_walk_item_fresh_agent_rewrite_brief_lines(walk_finder, parser, minutes, document, reads, whole_number,
                                                        total, unit, rewrite_file):
    """Return the lines of the fresh-agent's brief for rewriting the item in unit, built from the user's words in
    the walk-minutes and the links of the live versions of item whole_number and its sub-steps, with no text of the
    item."""
    lines, texts = approval_walk_item_and_sub_steps_live_versions_texts(walk_finder, parser, document, whole_number,
                                                                        total, unit)
    whole = texts[0][0]
    title, whole_title = item_title(walk_finder, lines[unit[3]]), item_title(walk_finder, lines[whole[3]])
    named = f'"{title}"' if whole[3] == unit[3] else f'"{title}", a sub-step of the item "{whole_title}"'
    constants = load_module("ned_box_home_directory_and_its_mac_mount_point_path_constants_common", PATH_CONSTANTS_FILE)
    links = approval_walk_item_linked_files("\n".join(text for _, text in texts),
                                            constants.NED_BOX_HOME, constants.MAC_MOUNT_OF_NED_BOX_HOME)
    words = approval_walk_item_user_words_in_minutes(walk_finder, parser, minutes.read_text(encoding="utf-8"),
                                                     whole_number, {title, whole_title})
    values = dict(title=named, skill=WALK_ME_THROUGH_SKILL_FILE, minutes=minutes, whole_number=whole_number,
                  document=document, reads=reads, rewrite_file=rewrite_file)
    return ([line.format(**values) for line in FRESH_AGENT_REWRITE_BRIEF_LINES]
            + ([f"- {line}" for line in words] or [FRESH_AGENT_REWRITE_NO_USER_WORDS.format(**values)])
            + [FRESH_AGENT_REWRITE_FILES_HEADER] + (links or [FRESH_AGENT_REWRITE_NO_FILES])
            + [line.format(**values) for line in FRESH_AGENT_REWRITE_BRIEF_CLOSING_LINES])


def approval_walk_item_text_replace_with_fresh_agent_rewrite_file(
        walk_finder, parser, document, unit, number, rewrite_file, item, command, read_command):
    """Put the text of rewrite_file in place of the text of unit, item number's own, below its heading, a setext
    heading's underline included, and the `#approval_walk_item_` lines right under it, and keep the replaced text
    below as a withdrawn version, in one write of the walk-document; return a line naming the withdrawn version's
    heading, or none when the replaced text is the rewrite. Raise Failure, writing nothing, when rewrite_file cannot
    be read, is empty, or holds a Markdown heading or an `#approval_walk_item_` line, when unit's heading names other
    items too, or when the walk-document so written would hold other items, or its withdrawn version's heading would
    not be read as one."""
    def refused(problem):
        return Failure(FRESH_AGENT_REWRITE_REFUSED.format(rewrite_file=rewrite_file, item=item, problem=problem,
                                                          document=document, command=command,
                                                          read_command=read_command))
    try:
        rewrite = blank_lines_stripped(rewrite_file.read_text(encoding="utf-8"))
    except OSError as error:
        raise refused(FRESH_AGENT_REWRITE_MISSING.format(error=error)) from error
    if not rewrite.strip():
        raise refused(FRESH_AGENT_REWRITE_EMPTY)
    headings = [token.map[0] for token in parser.parse(rewrite) if token.type == "heading_open" and token.map]
    if headings:
        raise refused(FRESH_AGENT_REWRITE_HEADING.format(heading=rewrite.split("\n")[headings[0]].strip()))
    tag_lines = [line for line in rewrite.split("\n") if walk_finder.APPROVAL_WALK_ITEM_TAG_LINE.match(line)]
    if tag_lines:
        raise refused(FRESH_AGENT_REWRITE_TAG_LINE.format(line=tag_lines[0].strip()))
    text = document.read_text(encoding="utf-8")
    lines = text.split("\n")
    if len(unit[0]) > 1:
        raise refused(FRESH_AGENT_REWRITE_SHARED_HEADING.format(heading=lines[unit[3]].strip(), item=item))
    heading_end, _ = walk_finder.approval_walk_unit_heading_end_and_item_line_ranges_below_heading_line(
        text, parser, lines, unit, [])
    kept_end = heading_end
    while kept_end < unit[4] and (not lines[kept_end].strip()
                                  or walk_finder.APPROVAL_WALK_ITEM_TAG_LINE.match(lines[kept_end])):
        kept_end += 1
    while kept_end > heading_end and not lines[kept_end - 1].strip():
        kept_end -= 1
    replaced = "\n".join([lines[unit[3]], *lines[kept_end:unit[4]]])
    written = [*lines[:kept_end], "", *rewrite.split("\n"), "", *lines[unit[4]:]]
    # The rewrite was checked alone; only the whole document shows a fence it leaves open running on below it, or a
    # bold count paragraph in it read as the item's newer version. Checked before the withdrawn version's lookup of
    # the item's unit, which such a rewrite leaves without one, and again after its insertion.
    spans_before = walk_finder.item_unit_spans(text, parser)
    before = [unit_found[:3] for unit_found in spans_before]
    # Units above the rewrite keep their lines, so the item's unit must still start at its heading; a bold count
    # paragraph with the same numbers and total moves that start and is caught only here.
    position = [unit_found[3] for unit_found in spans_before].index(unit[3])

    def refused_unless_items_unchanged():
        spans_after = walk_finder.item_unit_spans("\n".join(written), parser)
        after = [unit_found[:3] for unit_found in spans_after]
        if before != after:
            raise refused(FRESH_AGENT_REWRITE_ITEMS_CHANGED.format(before=[found[0] for found in before],
                                                                   after=[found[0] for found in after]))
        if spans_after[position][3] != unit[3]:
            raise refused(FRESH_AGENT_REWRITE_ITEM_START_MOVED.format(
                item=item, line=spans_after[position][3] + 1, heading=lines[unit[3]].strip()))
    refused_unless_items_unchanged()
    inserted = []
    kept = [line for _, _, _, line in withdrawn_versions_inserted_below_live_version(
        walk_finder, parser, written, unit[3], number, [(None, {}, replaced)], item,
        "\n".join([lines[unit[3]], rewrite]), document, FRESH_AGENT_REWRITE_REPLACED_TEXT_KEPT, inserted)
        if line is not None]
    refused_unless_items_unchanged()
    read_headings = {token.map[0] for token in parser.parse("\n".join(written))
                     if token.type == "heading_open" and token.map}
    unread = [index for index in inserted if index not in read_headings]
    if unread:
        raise refused(FRESH_AGENT_REWRITE_WITHDRAWN_HEADING_NOT_READ.format(heading=written[unread[0]]))
    document.write_text("\n".join(written), encoding="utf-8")
    return kept

def approval_walk_item_first_numbered_sub_step_without_answer(walk_finder, minutes, value, numbers, total, parser):
    """Return the sub-step, such as 3.1, of the one item numbers names, such as 3, that holds the sub-step
    next_item names first among the item's sub-steps and theirs, such as 3.1.1, taken from the walk-document as
    approval_walk_item_sub_step_units_below_item_in_walk_document takes them; next_item's rule decides, so the read step and the close step name the
    same sub-step. When the walk-document has no heading for that sub-step, such as no 3.1 above 3.1.1, the
    shortest of the named sub-step's levels below the item that has one, such as 3.1.1 for 3.1.1.1. None when
    numbers names several items or next_item names none."""
    if len(numbers) != 1:
        return None
    document = minutes.with_name(minutes.name[:-len(walk_finder.MINUTES_SUFFIX)] + ".md")
    all_units = walk_finder.item_unit_spans(document.read_text(encoding="utf-8"), parser)
    unit = walk_finder.waiting_item_units(document, value, numbers, total, parser, all_units)[1][0]
    sub_steps = [part for each in walk_finder.approval_walk_item_sub_step_units_below_item_in_walk_document(
                     all_units, unit, numbers) for part in each[0] if part.startswith(numbers[0] + ".")]
    named = next_item(walk_finder, minutes, parser, sub_steps, None, [], [])
    if not named:
        return None
    # A walk-document may give sub-sub-steps 2.1.1 to 2.1.3 no heading for 2.1: step into the next level that has one.
    parts = named[0][len(numbers[0]) + 1:].split(".")
    return next(level for level in (numbers[0] + "." + ".".join(parts[:depth]) for depth in range(1, len(parts) + 1))
                if level in sub_steps)


def approval_walk_item_unnumbered_sub_step_headings_numbered(walk_finder, minutes, value, numbers, total, parser):
    """Write `Item K.n of M: ` into each unnumbered `###` sub-step heading of the one `##` item numbers names, K
    the item's number, n counting from 1 in walk-document order and M its heading's, and return whether any was
    written. Only the headings inside the item's unit count, which item_unit_spans ends at the first Withdrawn
    heading, so a Withdrawn version's sub-step headings stay as they are. An item that already has a numbered
    sub-step, or names several items, is left as it is."""
    if len(numbers) != 1:
        return False
    document = minutes.with_name(minutes.name[:-len(walk_finder.MINUTES_SUFFIX)] + ".md")
    text = document.read_text(encoding="utf-8")
    all_units = walk_finder.item_unit_spans(text, parser)
    unit = walk_finder.waiting_item_units(document, value, numbers, total, parser, all_units)[1][0]
    tokens = parser.parse(text)
    heading = next((token for token in tokens if token.map is not None and token.map[0] == unit[3]
                    and token.type == "heading_open"), None)
    if (heading is None or heading.markup != walk_finder.UNNUMBERED_ITEM_HEADING_MARKUP or len(unit[0]) != 1
            or walk_finder.approval_walk_item_sub_step_units_below_item_in_walk_document(all_units, unit)):
        return False
    sub_steps = [token.map[0] for token in tokens
                 if token.type == "heading_open" and token.level == 0 and token.map is not None
                 and token.markup == APPROVAL_WALK_ITEM_SUB_STEP_HEADING_MARKUP and unit[3] < token.map[0] < unit[4]]
    if not sub_steps:
        return False
    lines = text.split("\n")
    for position, line in enumerate(sub_steps, start=1):
        marks, title = SUB_STEP_HEADING_PARTS.match(lines[line]).groups()
        lines[line] = NUMBERED_HEADING.format(marks=marks, number=f"{unit[0][0]}.{position}", total=unit[1] or total,
                                              title=title)
    document.write_text("\n".join(lines), encoding="utf-8")
    return True


def rated_none_item_not_to_be_shown(walk_finder, top, minutes, value, numbers, total, parser, named):
    """Return the waiting item's walk-document path when the item is one the no-answer table settles without
    showing it, as the step's docstring says, or None. named is the item as check names it."""
    if numbers[1:]:
        return None
    document, lines, marks, _, _ = item_lines(walk_finder, minutes, value, numbers, total, parser)
    ratings = [CASE_AGAINST_RATING.match(match[1]) for match in map(CASE_AGAINST_LINE.match, lines) if match]
    if not (ratings and ratings[0] and ratings[0][1].lower() == NOT_ASKED_RATED_NONE
            and any(FACT_LABELS[0] in line for line in lines)):
        return None
    # A missing touches line is left for the agent to add, as RATED_NONE_NOT_SHOWN_LINES says; any other refusal
    # of the settling command means the item is shown.
    if TOUCHES in evidence(lines) and not_asked_problems(NOT_ASKED_RATED_NONE, NOT_ASKED_RATED_NONE, lines, marks,
                                                         top, named):
        return None
    return None if unclosed_last_answer(walk_finder, minutes, parser) else document


def answer_is_already_decided(answered):
    """True when the walk-minutes answer was recorded by --already-decided, whatever answer its ruling gives."""
    return answered.startswith((ALREADY_DECIDED_PREFIX, f"{DISAPPROVED}, {ALREADY_DECIDED_PREFIX}"))


NO_ANSWER_ROWS_HEADING = ("Rows of the no-answer table {item} could settle by; if a row's meaning fits {item}, do "
                          "what its line says instead of presenting it; if none fits, present it:")
NO_ANSWER_ROW_PASSES = "- {label}: {meaning}. Its evidence passes: run `{command}` and do what it prints."
NO_ANSWER_ROW_LINE_MISSING = ("- {label}: {meaning}. Only evidence is missing: {missing} Add it to {document}, then "
                              "run `{command}` and do what it prints.")
NO_ANSWER_ROW_LINE_MALFORMED = ("- {label}: {meaning}. Its evidence line needs correcting: {malformed} Correct that line "
                                "in {document}, rather than adding another, then run `{command}` and do what it "
                                "prints.")
NO_ANSWER_ROW_NOT_CHECKED = ("- {label}: its evidence could not be checked, so it is not offered; present {item} "
                             "unless another row fits: {error}")


def no_answer_rows_for_waiting_item_lines(walk_finder, top, minutes, value, numbers, total, parser, named, item):
    """The no-answer table's rows the waiting item could settle by, as the docstring's read-step paragraph says."""
    if numbers[1:] or unclosed_last_answer(walk_finder, minutes, parser):
        return []
    document, lines, marks, _, _ = item_lines(walk_finder, minutes, value, numbers, total, parser)
    ratings = [CASE_AGAINST_RATING.match(match[1]) for match in map(CASE_AGAINST_LINE.match, lines) if match]
    if not (ratings and ratings[0] and any(FACT_LABELS[0] in line for line in lines)):
        return []
    rating = ratings[0][1].lower()
    rows = []
    for case in NO_ANSWER_CASES:
        if rating not in case.ratings:
            continue
        command = check_command_with_cwd(top, *no_answer_case_words(case))
        if case.flag == ALREADY_DECIDED_FLAG:
            if any(HANDOFF_INTERNALS_NAMED.search(line) for line in lines):
                rows.append(NO_ANSWER_ROW_PASSES.format(label=case.label, meaning=case.meaning, command=command))
            continue
        try:
            problems = not_asked_problems(case.value, rating, lines, marks, top, named)
        except Failure as failure:
            rows.append(NO_ANSWER_ROW_NOT_CHECKED.format(label=case.label, item=item,
                                                         error=getattr(failure, "reason", failure)))
            continue
        row = no_answer_table_row_text_or_none_from_evidence_check_problems(case, problems, document, command)
        if row:
            rows.append(row)
    return [NO_ANSWER_ROWS_HEADING.format(item=item), *rows] if rows else []


def no_answer_table_row_text_or_none_from_evidence_check_problems(case, problems, document, command):
    """The no-answer row offering `case` given its check's problems, or None when the row is not offered."""
    joined = " ".join(problem.removeprefix("- ") for problem in problems)
    if not problems:
        return NO_ANSWER_ROW_PASSES.format(label=case.label, meaning=case.meaning, command=command)
    if all(isinstance(problem, MalformedEvidenceLine) for problem in problems):
        return NO_ANSWER_ROW_LINE_MALFORMED.format(label=case.label, meaning=case.meaning, malformed=joined,
                                                   document=document, command=command)
    if all(isinstance(problem, MissingEvidenceLine) for problem in problems):
        return NO_ANSWER_ROW_LINE_MISSING.format(label=case.label, meaning=case.meaning, missing=joined,
                                                 document=document, command=command)
    return None


def close_record_line(item, line):
    """Whether line is one close writes to record item's answer, read from close's own templates: an agent's note
    that only opens with item's label, as in `item 25 of 39: the user's words, not an answer yet`, is not one."""
    return any(re.fullmatch(re.sub(r"\\\{[a-z_]+\\\}", ".*?",
                                   re.escape(template.rstrip()).replace(re.escape("{item}"), re.escape(item))),
                            line.rstrip())
               for template in CLOSE_RECORD_TEMPLATES)


def last_answer_line(walk_finder, minutes, parser):
    """Return (match, the lines after it, closed) for the walk-minutes' last answer line, or None when there is none.
    closed holds when a line close writes for that answer's label follows it."""
    lines = walk_finder.prose_lines(minutes.read_text(encoding="utf-8"), parser)
    for index in range(len(lines) - 1, -1, -1):
        match = ANSWER_LINE.match(lines[index])
        if match:
            after = lines[index + 1:]
            return match, after, any(close_record_line(match["item"], line) for line in after)
    return None


def unclosed_last_answer(walk_finder, minutes, parser):
    """Return the ANSWER_LINE match of the walk-minutes' last answer line when no close line follows it, else None:
    while it returns one, nothing may settle any item."""
    found = last_answer_line(walk_finder, minutes, parser)
    return found[0] if found and not found[2] else None


def item_read_findings_without_outcomes_lines(item, report, outcome_file, fast_read_program, command,
                                              command_reading_again):
    """The lines that withhold item from being presented while the report of its latest cold-read-fast-read has
    findings with no recorded outcome; empty when every finding has one or the report has none. Raise Failure when
    the report or its outcomes file cannot be read."""
    finding_outcomes = load_module("cold_read_fast_read_report_findings_parse_and_finding_outcomes_check_common", FINDING_OUTCOMES_COMMON_FILE)
    record = Path(report).parent
    try:
        missing = finding_outcomes.cold_read_fast_read_findings_without_outcomes(record)
    except (OSError, ValueError) as error:
        raise Failure(ITEM_READ_FINDING_OUTCOMES_UNREADABLE.format(
            item=item, report=report, error=error, record=record, outcome_file=outcome_file, command=command,
            read_again=command_reading_again))
    if not missing:
        return []
    findings = finding_outcomes.cold_read_fast_read_record_findings(record)
    return ([ITEM_READ_FINDINGS_WITHOUT_OUTCOMES.format(item=item, report=report, count=len(findings),
                                                       missing=len(missing))]
            + finding_outcomes.finding_list_lines(findings)
            + [line.format(item=item, command=command, applied=finding_outcomes.APPLIED,
                           declined=finding_outcomes.DECLINED,
                           placeholder=finding_outcomes.FINDING_OUTCOME_PLACEHOLDER,
                           outcomes_command=finding_outcomes.cold_read_fast_read_finding_outcomes_record_command(
                               Path(fast_read_program).resolve(), record, findings))
               for line in ITEM_READ_FINDING_OUTCOMES_COMMAND_LINES])


def approval_walk_item_system_status_claims_not_rechecked_refused(text, item, document, command, rechecked):
    """Raise Failure when the item's text states the current status of something outside the walk, as
    agent-text-possibly-stale-system-status-claim-phrases-match-common.py finds such claims, and the agent has not
    said, with SYSTEM_STATUS_CLAIMS_RECHECKED_FLAG, how it rechecked them; return the line recording that recheck,
    or None when the text states no such status."""
    claims = load_module("agent_text_possibly_stale_system_status_claim_phrases_match_common",
                         SYSTEM_STATUS_CLAIM_PHRASES_FILE)
    found = claims.possibly_stale_system_status_claim_phrases_find(text)
    if not found:
        return None
    matched = ", ".join(f'"{phrase}"' for _, phrase in found[:SYSTEM_STATUS_CLAIM_PHRASES_SHOWN])
    if rechecked is None:
        raise Failure(APPROVAL_WALK_ITEM_SYSTEM_STATUS_CLAIM_NOT_RECHECKED.format(
            item=item, document=document, matched=matched, command=command))
    return SYSTEM_STATUS_CLAIMS_RECHECKED_LINE.format(item=item, matched=matched, rechecked=rechecked)


def approval_walk_item_title_search_groups(walk_finder, document, value, numbers, total, parser, earlier):
    """Return [(titles, item numbers)], one group for each distinct set of waiting item numbers that a heading in
    document names or that a waiting item's own titled opening under a shared heading names, such as [3] and [4] for
    items 3 and 4 under one heading: the titles of those headings and openings, each in the closing line's form too
    when that differs, as when the title holds a link, so that a short title is matched only after its own numbers.
    Groups come in the order the `#next_to_present` line names the items, a heading's group before the groups of the
    openings under it, so items 4 and 3, named in that order, give [4] before [3] whichever opening comes first. A
    lone waiting item's titles also hold the title of each earlier read text of it, as earlier_read_texts_of_item
    returns them; a Withdrawn version heading carries no title, so those read texts are its only earlier titles the
    program can know."""
    text = document.read_text(encoding="utf-8")
    lines = text.split("\n")
    _, units = walk_finder.waiting_item_units(document, value, numbers, total, parser)
    hook = load_module("walk_me_through_user_short_answer_hook", SHORT_ANSWER_HOOK_FILE)
    openings = walk_finder.item_opening_lines(text, parser)

    def search_forms(line):
        title = item_title(walk_finder, line)
        if not title:
            return []
        # The closing line's point, as the hook shows it, so that `## Item 4 of 9 (revised): a [filter](url)` is
        # also searched as `a filter`; and the title with only its link syntax dropped, as an earlier message
        # quoting it would write it.
        forms = [title, hook.approval_walk_item_heading_point_without_links(line.strip(), parser),
                 markdown_with_link_syntax_dropped(title, parser, hook)]
        return list(dict.fromkeys(form for form in forms if form))

    groups = []
    for unit in units:
        headings = [lines[unit[3]]] + ([copied for _, _, copied in earlier] if len(units) == 1 else [])
        titles = []
        for heading in headings:
            for form in search_forms(heading.split("\n", 1)[0]):
                if form not in titles:
                    titles.append(form)
        waiting = [number for number in numbers if number in unit[0]]
        if titles:
            groups.append((titles, waiting))
        # Under a heading several items share, an item's own opening, such as `**Item 3 of 9: the first**`, names it
        # by its own title, which earlier messages may use instead of the heading's.
        for number in waiting:
            start, _ = walk_finder.approval_walk_item_line_range_within_heading_shared_by_several_items(
                openings, unit[3], unit[4], number, unit[0], unit[1])
            own = [form for form in search_forms(lines[start]) if form not in titles] if start != unit[3] else []
            if own:
                groups.append((own, [number]))
    # Groups with the same numbers search the same records, so each is searched once, with every title, or a
    # message naming two of its titles is printed twice.
    merged = {}
    for titles, waiting in groups:
        kept = merged.setdefault(tuple(waiting), [])
        kept.extend(title for title in titles if title not in kept)
    return [(titles, list(waiting)) for waiting, titles in merged.items()]


def approval_walk_item_title_user_messages_in_earlier_agent_sessions_lines(walk_finder, minutes, groups, numbers,
                                                                         item, command):
    """Return (the lines TITLE_SEARCH_PROGRAM prints for each of groups, as approval_walk_item_title_search_groups
    returns them, in one search, a function that saves them and returns the lines to print after them);
    raise Failure when a search failed.

    Print them with lines_printed_with_title_search_saved_after, which saves them only once they are printed: the
    lines are saved in the title search cache file for the item and this agent-session, and a later run for the
    same titles in the same agent-session prints only a line naming that file, since fix rounds rerun the step, so
    lines saved but never printed are never read."""
    if not groups:
        return [], lambda: []
    # The cache format and the groups' titles and numbers, as JSON lists, so a change to any of them searches again.
    titles = [TITLE_SEARCH_CACHE_FORMAT, [[group_titles, group_numbers] for group_titles, group_numbers in groups]]
    variable = load_module("cold_read_record_names", RECORD_NAMES_FILE).AGENT_SESSION_ID_ENVIRONMENT_VARIABLE
    session_id = os.environ.get(variable)
    cache = (minutes.parent / TITLE_SEARCH_CACHE_DIRECTORY_NAME
             / TITLE_SEARCH_CACHE_FILE_NAME.format(walk=minutes.name[:-len(walk_finder.MINUTES_SUFFIX)],
                                                   numbers="-and-".join(numbers), session=session_id))
    if session_id and title_search_cache_titles(cache) == titles:
        return [TITLE_SEARCH_CACHE_PRINTED_BEFORE.format(item=item, path=cache)], lambda: []
    lines = []
    # One search for every group, each title with its own numbers, so an agent-session or walk-minutes line naming
    # titles of two groups is printed once; in the `=` form, so that a title opening with `-` is not read as an option.
    words = [f"--title-of-items={','.join(group_numbers)}:{title}"
             for group_titles, group_numbers in groups for title in group_titles]
    result = subprocess.run([sys.executable, str(TITLE_SEARCH_PROGRAM), *words], capture_output=True, text=True,
                            stdin=subprocess.DEVNULL)
    try:
        exits = load_module("title_search", TITLE_SEARCH_PROGRAM)
    # Whatever a search that cannot load raises, it is a failed search, reported as the others are.
    except Exception as error:
        raise Failure(APPROVAL_WALK_ITEM_TITLE_SEARCH_FAILED.format(
            item=item, exit=result.returncode, command=command, said=title_search_failure_said(
                result.stderr, f"FAILED: loading the title search here raised {error!r}.")))
    if result.returncode not in (exits.EXIT_FOUND, exits.EXIT_NOTHING_FOUND):
        raise Failure(APPROVAL_WALK_ITEM_TITLE_SEARCH_FAILED.format(
            item=item, exit=result.returncode, command=command, said=title_search_failure_said(
                result.stderr, f"FAILED: the title search exited {result.returncode} without a FAILED line of "
                               f"its own, so it crashed or was stopped.")))
    lines += result.stdout.rstrip("\n").split("\n") if result.stdout.strip() else []
    if not session_id:
        return lines, lambda: [TITLE_SEARCH_CACHE_NOT_SAVED.format(
            path=minutes.parent / TITLE_SEARCH_CACHE_DIRECTORY_NAME,
            why=TITLE_SEARCH_CACHE_NO_AGENT_SESSION.format(variable=variable))]

    def saved_lines():
        try:
            cache.parent.mkdir(parents=True, exist_ok=True)
            temporary = cache.with_name(cache.name + ".writing")
            temporary.write_text("\n".join([json.dumps(titles)] + lines) + "\n", encoding="utf-8")
            os.replace(temporary, cache)
        except OSError as error:
            return [TITLE_SEARCH_CACHE_NOT_SAVED.format(path=cache, why=error)]
        return []
    return lines, saved_lines


def title_search_failure_said(stderr, summary):
    """Return what a failed title search said: its stderr, with the FAILED line summary added when the search
    printed no FAILED line itself, so that the agent always has a FAILED line to relay."""
    said = stderr.strip()
    if any(line.startswith("FAILED:") for line in said.split("\n")):
        return said
    return "\n".join(filter(None, [said, summary]))


def lines_printed_with_title_search_saved_after(first, past_words, rest):
    """Print first, then the title search's lines of past_words, as
    approval_walk_item_title_user_messages_in_earlier_agent_sessions_lines returns it, then rest; save the search
    only once its lines are written out, so a write that fails leaves no cache saying they were printed."""
    lines, save = past_words
    print("\n".join([first] + lines))
    sys.stdout.flush()
    after = save() + rest
    if after:
        print("\n".join(after))


def title_search_cache_titles(cache):
    """Return the titles on the first line of the title search cache file cache, or None when it is missing or
    cannot be read, so that the search runs again."""
    try:
        first = cache.read_text(encoding="utf-8").split("\n", 1)[0]
        return json.loads(first)
    except (OSError, ValueError):
        return None


def waiting_item_read(arguments, sub_step_of=None):
    """Give the item the `#next_to_present` line names its cold-read-fast-read, as its text stands.

    sub_step_of is (the sub-step's `#next_to_present` value, the item it is a sub-step of, the arguments of
    earlier_read_texts_kept_as_withdrawn_versions for that item and each item above it) when the line names an
    item split into numbered sub-steps: the sub-step is read in its place, and its line is added to the walk-minutes,
    and each such item's earlier read texts are kept as withdrawn versions, only once every refusal has passed, so a
    refused read leaves the walk-minutes and the walk-document as they were, except for the running counts
    approval_walk_item_unnumbered_sub_step_headings_numbered writes into the item's sub-step headings, which
    a sub-step those four words take over the word limit is refused with, and which a rerun keeps."""
    walk_finder = load_walk_finder()
    top, minutes, value, parser = the_open_walk(walk_finder, arguments.cwd)
    if sub_step_of:
        value = sub_step_of[0]
    named, numbers, total = waiting_items(walk_finder, value, minutes)
    reads = item_reads_directory(walk_finder, minutes)
    rechecked = arguments.possibly_stale_system_status_claims_rechecked
    if rechecked is not None and not rechecked.strip():
        raise Failure(SYSTEM_STATUS_CLAIMS_RECHECKED_EMPTY)
    # Repeated in every command the step prints, so a rerun it asks for is not refused again for the same claims.
    rechecked_words = flag_and_value_words(SYSTEM_STATUS_CLAIMS_RECHECKED_FLAG, rechecked) if rechecked else []
    rerun = read_step_command_with_cwd(
        top, *([AFTER_FIXES_FLAG] if arguments.after_fixes_reread_only_when_facts_change else []), *rechecked_words)
    # Before walk_document_items, which can write: a missing copy refuses with nothing written.
    earlier = earlier_read_texts_of_item(walk_finder, minutes, value, numbers, total, parser, reads, rerun)
    count, _, _, _, _ = walk_document_items(walk_finder, minutes, value, numbers, total, parser,
                                                WAITING_ITEM_READ_STEP, top)
    total = total or count
    item = items_named(numbers, total)
    command = read_step_command_with_cwd(top, AFTER_FIXES_FLAG, *rechecked_words)
    command_reading_again = read_step_command_with_cwd(top, *rechecked_words)
    document, text = item_text(walk_finder, minutes, value, numbers, total, parser,
                               refused_unless_marks_read=(item, command))
    rewrite_file = arguments.approval_walk_item_fresh_agent_rewrite_file
    # Before the kept versions are written, so a refused item's document is left as it was. With a rewrite, the
    # rewrite's own text is checked once it is in place: a rerun after an over-limit rewrite whose count reset failed
    # must reach the rewrite branch to finish that reset.
    if rewrite_file is None:
        approval_walk_item_text_over_word_limit_refused(walk_finder, minutes, value, numbers, total, parser, item,
                                                        command)
    # Unnumbered, the sub-steps are read as the item's own lines, so one answer would decide them all.
    if approval_walk_item_unnumbered_sub_step_headings_numbered(walk_finder, minutes, value, numbers, total, parser):
        return waiting_item_read(arguments, sub_step_of)
    sub_step = approval_walk_item_first_numbered_sub_step_without_answer(walk_finder, minutes, value, numbers, total,
                                                                         parser)
    keep = (walk_finder, minutes, value, numbers, total, parser, earlier, item, text, command_reading_again)
    if sub_step:
        return waiting_item_read(arguments, (items_named([sub_step], total), item,
                                             (sub_step_of[2] if sub_step_of else []) + [keep]))
    whole_number = numbers[0].split(".")[0]
    if rewrite_file is not None:
        unit = walk_finder.waiting_item_units(document, value, numbers, total, parser)[1][0]
        # A read that started from the whole item checks the whole item, as the read without a rewrite does before
        # it turns to the sub-step: the other sub-steps before anything is written, the rewrite once it is in place.
        for above in (sub_step_of[2] if sub_step_of else []):
            approval_walk_item_text_over_word_limit_refused(*above[:6], above[7], command, skipped_start=unit[3])
        # Run again, this command finds the rewrite already in place and only counts, so it is the one to repeat.
        rewrite_command = read_step_command_with_cwd(top, FRESH_AGENT_REWRITE_FLAG, str(rewrite_file),
                                                     *rechecked_words)
        for line in approval_walk_item_text_replace_with_fresh_agent_rewrite_file(
                walk_finder, parser, document, unit, numbers[0], rewrite_file, item, rewrite_command,
                command_reading_again):
            print(line)
        approval_walk_item_proposed_text_revisions_counted(
            reads, whole_number, approval_walk_item_and_sub_steps_live_versions_proposed_new_texts_read_sorted(
                walk_finder, parser, document, whole_number, total,
                walk_finder.waiting_item_units(document, value, numbers, total, parser)[1][0]), True, item,
            rewrite_command)
        # The rewrite stays in place when it is refused, as an agent's own revision does, and is fixed the same way.
        _, text = item_text(walk_finder, minutes, value, numbers, total, parser,
                            refused_unless_marks_read=(item, command))
        approval_walk_item_text_over_word_limit_refused(walk_finder, minutes, value, numbers, total, parser, item,
                                                        command)
    # Before anything is written, so a refused item leaves the walk-minutes and the walk-document as they were; an
    # item settled without being shown is not refused, since no status in it reaches the user.
    recheck_line, past_words = None, ([], lambda: [])
    if rated_none_item_not_to_be_shown(walk_finder, top, minutes, value, numbers, total, parser, named) is None:
        recheck_line = approval_walk_item_system_status_claims_not_rechecked_refused(
            text, item, document, rerun, rechecked)
        past_words = approval_walk_item_title_user_messages_in_earlier_agent_sessions_lines(
            walk_finder, minutes, approval_walk_item_title_search_groups(
                walk_finder, document, value, numbers, total, parser, earlier), numbers, item, rerun)
    if sub_step_of:
        # An item read before it was split keeps that text, as an item revised after its read does.
        for above in sub_step_of[2]:
            for line in earlier_read_texts_kept_as_withdrawn_versions(*above):
                print(line)
        append_to_minutes(minutes, [NEXT_MARKER_LINE.format(value=item)])
        print(ITEM_READ_SUB_STEP_NAMED.format(item=sub_step_of[1], sub_step=item, minutes=minutes))
    for line in earlier_read_texts_kept_as_withdrawn_versions(walk_finder, minutes, value, numbers, total, parser,
                                                              earlier, item, text, command_reading_again):
        print(line)
    if not numbers[1:]:
        unit = walk_finder.waiting_item_units(document, value, numbers, total, parser)[1][0]
        revisions = approval_walk_item_proposed_text_revisions_counted(
            reads, whole_number, approval_walk_item_and_sub_steps_live_versions_proposed_new_texts_read_sorted(
                walk_finder, parser, document, whole_number, total, unit), False, item, command_reading_again)
        if (revisions >= PROPOSED_TEXT_REVISIONS_BEFORE_FRESH_AGENT_REWRITE
                and approval_walk_item_new_texts(walk_finder, parser, text)):
            rewrite = reads / FRESH_AGENT_REWRITE_FILE.format(number=numbers[0])
            values = dict(item=item, count=revisions, whole_number=whole_number, rewrite_file=rewrite,
                          document=document, command=read_step_command_with_cwd(
                              top, FRESH_AGENT_REWRITE_FLAG, str(rewrite), *rechecked_words),
                          count_file=reads / PROPOSED_TEXT_REVISIONS_FILE.format(number=whole_number),
                          read_command=command_reading_again)
            brief = approval_walk_item_fresh_agent_rewrite_brief_lines(
                walk_finder, parser, minutes, document, reads, whole_number, total, unit, rewrite)
            print("\n".join([line.format(**values) for line in FRESH_AGENT_REWRITE_DUE_LINES]
                            + [FRESH_AGENT_REWRITE_BRIEF_START, *brief, FRESH_AGENT_REWRITE_BRIEF_END]
                            + [line.format(**values) for line in FRESH_AGENT_REWRITE_AFTER_LINES]))
            return 1
    not_started = start_read_ahead_of_item_after(walk_finder, top, minutes, parser, numbers, total,
                                                 arguments.fast_read_program)
    if not_started:
        print(not_started)
    # Printed after the step's first line, which names the report, and before the closing lines the agent acts on.
    no_answer_rows = no_answer_rows_for_waiting_item_lines(walk_finder, top, minutes, value, numbers, total, parser,
                                                           named, item)
    not_shown = rated_none_item_not_to_be_shown(walk_finder, top, minutes, value, numbers, total, parser, named)
    if not_shown is not None:
        settle = check_command_with_cwd(top, "--not-asked", NOT_ASKED_RATED_NONE)
        # The rows are already formatted, and may hold braces from a path or a title.
        print("\n".join([*(line.format(item=item, document=not_shown, command=settle,
                                        read_command=command_reading_again)
                            for line in RATED_NONE_NOT_SHOWN_LINES), *no_answer_rows]))
        return 0
    now_over_later_clause = ("." if unclosed_last_answer(walk_finder, minutes, parser)
                             else PRESENT_UNLESS_NOW_OVER_LATER_CLAUSE.format(
                                 now_over_later_command=check_command_with_cwd(top, NOW_OVER_LATER_FLAG)))
    key = text_key(text)
    while read_outcome(reads, key) is None and worker_alive(reads, key):
        time.sleep(READ_POLL_SECONDS)
    outcome, ahead = read_outcome(reads, key), (reads / f"{key}-started.json").is_file()
    if outcome and outcome["status"] == READ_DONE and outcome.get(NUMBER_PREDICTED):
        outcome = read_ahead_bound_to_item(reads, key, outcome, item)
    why = ""
    if outcome and outcome["status"] == READ_DONE:
        how = ITEM_READ_HOW_AHEAD if ahead else ITEM_READ_HOW_ALREADY
    else:
        if ahead:
            why = (ITEM_READ_RUN_AHEAD_FAILED.format(line=outcome["failed"]) if outcome
                   else ITEM_READ_RUN_AHEAD_ENDED.format(log=reads / f"{key}.log"))
        latest = (latest_read(walk_finder, reads, numbers) if arguments.after_fixes_reread_only_when_facts_change
                  else None)
        if latest is not None:
            last_text = (reads / f"{latest[0]}.md").read_text(encoding="utf-8").rstrip("\n")
            facts = approval_walk_item_before_and_after_fixes_compare_for_changed_fact_words_needing_another_cold_read_fast_read(last_text, text, top)
            if not facts:
                if recheck_line:
                    print(recheck_line)
                withheld = item_read_findings_without_outcomes_lines(
                    item, latest[1]["report"], reads / f"{latest[0]}-outcome.json", arguments.fast_read_program,
                    command, command_reading_again)
                rest = no_answer_rows + (withheld or [ITEM_READ_NOT_RUN_NEXT.format(
                    item=item, now_over_later_clause=now_over_later_clause)]
                    + waiting_on_item_prerequisite_lines(walk_finder, minutes, numbers, total, parser))
                lines_printed_with_title_search_saved_after(
                    ITEM_READ_NOT_RUN.format(item=item, report=latest[1]["report"]), past_words, rest)
                return 1 if withheld else 0
            why = ITEM_READ_RUN_FACTS.format(report=latest[1]["report"], facts=", ".join(facts[:FACTS_LISTED]))
        walk_name = minutes.name[:-len(walk_finder.MINUTES_SUFFIX)]
        outcome = fast_read_outcome(text, walk_fast_read_name(walk_name, item), arguments.fast_read_program,
                                    STOP_SIGNAL_READ_STEP_AFTER_REMOVAL.format(
                                        item=item, command=command_reading_again))
        reads.mkdir(exist_ok=True)
        (reads / f"{key}-started.json").unlink(missing_ok=True)
        record_read(reads, key, item, text, outcome)
        if outcome["status"] == READ_FAILED:
            print("\n".join([outcome["failed"]]
                            + [line.format(item=item, command=command_reading_again)
                               for line in ITEM_READ_FAILED_LINES]))
            return 1
        how = ITEM_READ_HOW_RUN.format(why=why)
    if recheck_line:
        print(recheck_line)
    notes = "".join(STATUS_FAST_READ_NOTE.format(note=note) for note in outcome["notes"])
    withheld = item_read_findings_without_outcomes_lines(item, outcome["report"], reads / f"{key}-outcome.json",
                                                         arguments.fast_read_program, command,
                                                         command_reading_again)
    rest = (no_answer_rows
            + [line.format(item=item, document=document, command=command,
                           now_over_later_clause=now_over_later_clause)
               for line in (ITEM_READ_LINES[:1] if withheld else ITEM_READ_LINES)]
            + (withheld or waiting_on_item_prerequisite_lines(walk_finder, minutes, numbers, total, parser)))
    lines_printed_with_title_search_saved_after(
        ITEM_READ_USED.format(item=item, how=how, report=outcome["report"], notes=notes), past_words, rest)
    return 1 if withheld else 0


def items_shown_to_user(walk_finder, minutes, numbers, parser):
    """Whether the walk-minutes hold an `#item_page` line, with a link or a failed publish, for any of numbers: the
    skill writes one before any message shows the item."""
    pages = walk_finder.newest_item_page_link_per_item_from_walk_minutes(minutes.read_text(encoding="utf-8"), parser)
    return any(number in pages for number in numbers)


def last_answer(walk_finder, minutes, parser, top):
    """Return (item, answered, status lines, how the line opens after the item, as in `shown to the user,`) of the
    walk-minutes' last answer line, or raise Failure when there is none or a close already recorded it."""
    found = last_answer_line(walk_finder, minutes, parser)
    if found:
        match, after, closed = found
        # Without this, a close after a check that failed reads the earlier, already closed answer as one held for
        # a new item.
        if closed:
            raise Failure(CLOSE_ALREADY_RECORDED.format(minutes=minutes, item=match["item"],
                                                        command=check_command_with_cwd(top)))
        statuses = []
        for line in after:
            if not line.startswith(STATUS_LINE_PREFIX):
                break
            statuses.append(line[len(STATUS_LINE_PREFIX):])
        return match["item"], match["answered"], statuses, match["settled"]
    raise Failure(f"{minutes} has no line recording the user's answer; run "
                  f"`{check_command_with_cwd(top)}` first, with the flag for the user's answer as "
                  f"`--help` lists it.")


def walk_document_items(walk_finder, minutes, value, numbers, total, parser, step, top, stamp=True):
    """Return (M as the walk finder counts it, the walk-document's items in order, the summary item or None, its
    units, the placing of the items not yet shown), an item being its number, or, for an unnumbered item, its
    heading's line index, an int, which unnumbered_item_numbered numbers when it is shown.

    The placing maps each unnumbered item but the summary item to (its sort key, the items it waits on), as
    unshown_items_placing reads them; first, with stamp, it writes the `#approval_walk_item_first_entered` line, with
    today's date, into each such item that has none. Raise Failure, writing nothing, when an item's lines do not let
    it be placed."""
    document = minutes.with_name(minutes.name[:-len(walk_finder.MINUTES_SUFFIX)] + ".md")
    text = document.read_text(encoding="utf-8") if document.is_file() else ""
    units = walk_finder.item_unit_spans(text, parser) if document.is_file() else None
    try:
        walk_finder.waiting_item_units(document, value, numbers, total, parser, units)
    except walk_finder.UnusableRange as problem:
        raise Failure(f"the last `#next_to_present` line in {minutes}, `{value}`: {problem}")
    today = datetime.date.today().isoformat()
    try:
        order, summary, placing = walk_document_order(walk_finder, text, units, parser, document, today)
        stamped = unshown_items_first_entered_stamped(walk_finder, text, units, parser, today) if stamp else text
        if stamped != text:
            # Placed before the write, so a stamped document that no longer places writes nothing.
            units = walk_finder.item_unit_spans(stamped, parser)
            order, summary, placing = walk_document_order(walk_finder, stamped, units, parser, document, today)
    except WalkOrderUnusable as problem:
        raise Failure(WALK_ORDER_REFUSED.format(problem=problem, command=step_command_with_cwd(top, step)))
    if stamped != text:
        document.write_text(stamped, encoding="utf-8")
    count = walk_finder.approval_walk_item_total_shown_and_waiting_counted_from_walk_document(units)
    return count, order, summary, units, placing


def walk_document_order(walk_finder, text, units, parser, document, today):
    """Return (the items of units in walk-document order, the summary item or None, the placing of the unshown
    items), as walk_document_items' docstring says. An unnumbered item written between the sub-steps of one item,
    as in 2.1, then the unnumbered item, then 2.2, comes after the last of them, as
    approval_walk_item_sub_step_units_below_item_in_walk_document passes over it, so that it does not split them."""
    lines = text.split("\n")
    order, summary = [], None
    for unit in approval_walk_unnumbered_items_moved_past_the_sub_steps_they_split(walk_finder, units):
        unit_numbers, first = unit[0], unit[3]
        keys = [first] if walk_finder.approval_walk_unit_is_unnumbered_item(unit) else unit_numbers
        order += [key for key in keys if key not in order]
        if keys and SUMMARY_HEADING.search(
                walk_finder.approval_walk_item_heading_with_deferred_note_removed(lines[first])):
            summary = keys[0]
    return order, summary, unshown_items_placing(walk_finder, text, units, parser, document, today)


def approval_walk_unnumbered_items_moved_past_the_sub_steps_they_split(walk_finder, units):
    """units, as item_unit_spans gives them, with each unnumbered item that stands between a numbered unit and the
    last of that unit's sub-steps, as approval_walk_item_sub_step_units_below_item_in_walk_document finds them, moved
    to just after that last sub-step, the latest one when several units' sub-steps reach past it, as in 2.1, the
    unnumbered item, then 2.2, or 3, 4, the unnumbered item, then 3.1; the units keep their line numbers."""
    after = {}
    for unit in units:
        if not unit[0]:
            continue
        found = walk_finder.approval_walk_item_sub_step_units_below_item_in_walk_document(units, unit)
        last = found[-1][3] if found else None
        for other in units:
            if (last is not None and walk_finder.approval_walk_unit_is_unnumbered_item(other)
                    and unit[3] < other[3] < last):
                after[other[3]] = max(after.get(other[3], last), last)
    moved = []
    for unit in units:
        if unit[3] in after:
            continue
        moved.append(unit)
        moved += [other for other in units if after.get(other[3]) == unit[3]]
    return moved


class WalkOrderUnusable(Exception):
    """An unshown item's category, waits-on or first-entered lines that do not let it be placed; its argument says
    which."""


def unshown_units(walk_finder, units, lines):
    """The unnumbered units of units, the summary item's left out."""
    return [unit for unit in units if walk_finder.approval_walk_unit_is_unnumbered_item(unit)
            and not SUMMARY_HEADING.search(walk_finder.approval_walk_item_heading_with_deferred_note_removed(
                lines[unit[3]]))]


def heading_title(walk_finder, line):
    """The title of an item heading: its text after the `##` marks and any running count, deferred note and
    backticks left out, with its spaces squeezed, in lower case; a `#approval_walk_item_waits_on` line's title is
    read the same way."""
    # Without backticks, since the waits-on line's reading drops a closing one along with closing emphasis marks.
    heading = walk_finder.approval_walk_item_heading_with_deferred_note_removed(line).replace("`", "")
    parts = UNNUMBERED_HEADING_PARTS.match(heading)
    title = parts[2] if parts else heading.lstrip("#")
    title = re.sub(r"^[*_\s]*items?\s+[\d.]+(?:\s*(?:,|&|\band\b|\bto\b|-|–)\s*[\d.]+)*\s+of\s+\d+\b"
                   r"[*_\s:.\-–—]*", "", title, flags=re.I)
    return squeezed(title.strip(" *_")).lower()


def unshown_items_first_entered_stamped(walk_finder, text, units, parser, today):
    """text with a line `#approval_walk_item_first_entered today` written right under the heading of each unshown item
    that has no such line."""
    lines = text.split("\n")
    prose = walk_finder.prose_lines(text, parser)
    unstamped = [unit[3] for unit in unshown_units(walk_finder, units, lines)
                 if not any(WALK_FIRST_ENTERED_LINE.match(line) for line in prose[unit[3] + 1:unit[4]])]
    for first in reversed(unstamped):
        # The blank line after it keeps a next line, such as indented code, from joining the tag's paragraph.
        after = [""] if first + 1 < len(lines) and lines[first + 1].strip() else []
        lines[first + 1:first + 1] = ["", f"{WALK_FIRST_ENTERED_TAG} {today}"] + after  # pragma: no mutate, an unshown item comes after a numbered one, so first is never 0 and a slice ending at first - 1 is as empty as one ending at first + 1
    return "\n".join(lines)


def unshown_items_placing(walk_finder, text, units, parser, document, today):
    """Return {heading line of an unshown item: ((category rank, first-entered date, heading line), {items it waits
    on})}, an item it waits on given as walk_document_items gives items; raise WalkOrderUnusable when an unshown
    item has no category tag, more than one, or one not in WALK_CATEGORIES, an unreadable first-entered date, or a
    `#approval_walk_item_waits_on` title that no other item heading has, or when unshown items wait on each other in
    a circle."""
    lines = text.split("\n")
    prose = walk_finder.prose_lines(text, parser)
    titles = {}
    for unit in units:
        key = unit[3] if walk_finder.approval_walk_unit_is_unnumbered_item(unit) else None
        for item in [key] if key is not None else unit[0]:
            titles.setdefault(heading_title(walk_finder, lines[unit[3]]), []).append(item)
    placing = {}
    for unit in unshown_units(walk_finder, units, lines):
        first, end = unit[3], unit[4]
        item = f"the item `{lines[first].strip()}` in {document}"
        tags = [tag for line in prose[first + 1:end] if WALK_CATEGORY_LINE.match(line)
                for tag in WALK_CATEGORY_TAGS_IN_LINE.findall(line)]
        if not tags:
            raise WalkOrderUnusable(CATEGORY_MISSING.format(item=item))
        if len(tags) > 1:
            raise WalkOrderUnusable(CATEGORY_DOUBLED.format(item=item, tags=", ".join(f"`{tag}`" for tag in tags)))
        category = tags[0][len(WALK_CATEGORY_TAG):]
        if category not in WALK_CATEGORIES:
            raise WalkOrderUnusable(CATEGORY_UNKNOWN.format(item=item, tag=tags[0]))
        entered = next((match for match in map(WALK_FIRST_ENTERED_LINE.match, prose[first + 1:end]) if match), None)
        try:
            date = datetime.date.fromisoformat(entered[1]).isoformat() if entered else today
        except ValueError:
            raise WalkOrderUnusable(FIRST_ENTERED_UNREADABLE.format(item=item, line=entered[0].strip()))
        waits_on = set()
        for match in filter(None, map(WALK_WAITS_ON_LINE.match, prose[first + 1:end])):
            title = heading_title(walk_finder, "## " + match[1].lstrip("# "))
            named = [other for other in titles.get(title, []) if other != first]
            if not named:
                raise WalkOrderUnusable(WAITS_ON_UNKNOWN.format(item=item, title=match[1]))
            waits_on.update(named)
        placing[first] = ((WALK_CATEGORIES.index(category), date, first), waits_on)
    circle = waiting_circle(placing)
    if circle:
        raise WalkOrderUnusable(WAITS_ON_CIRCLE.format(
            items=", ".join(f"`{lines[item].strip()}`" for item in circle) + f" in {document}"))
    return placing


def waiting_circle(placing):
    """The items of a circle of unshown items each waiting on the next, in walk-document order, or []."""
    state = {}

    def visit(item, path):
        state[item] = "visiting"
        for other in sorted(other for other in placing[item][1] if other in placing):
            if state.get(other) == "visiting":
                return path[path.index(other):]
            if other not in state:
                found = visit(other, path + [other])
                if found:
                    return found
        state[item] = "done"
        return []

    for item in sorted(placing):
        if item not in state:
            found = visit(item, [item])
            if found:
                return sorted(found)
    return []


def unshown_items_in_walk_order(items, placing):
    """items, unshown items of placing, in the order the walk shows them: an item after every one of items it
    waits on, and otherwise the item whose own sort key, or the key of an item waiting on it directly or through
    others, is lowest first, so an item that unblocks another comes as early as that other item would."""
    waiting_on = {item: placing[item][1] & set(items) for item in items}
    effective = {}

    def lowest_key(item, seen=()):
        if item not in effective:
            dependents = [other for other in items if item in waiting_on[other] and other not in seen]
            effective[item] = min([placing[item][0]] + [lowest_key(other, seen + (item,)) for other in dependents])
        return effective[item]

    ordered, remaining = [], list(items)
    while remaining:
        ready = [item for item in remaining if not waiting_on[item] & set(remaining)]
        chosen = min(ready, key=lambda item: (lowest_key(item), placing[item][0]))
        ordered.append(chosen)
        remaining.remove(chosen)
    return ordered


def unshown_items_gathered_behind_chosen(walk_finder, minutes, chosen, units, placing, parser, answered_numbers,
                                         total):
    """Rewrite the walk-document so that the unshown items placing holds stand together where the first of them
    stands, or after the whole item, sub-steps and withdrawn versions included, of the answered items,
    answered_numbers, when the first of them stands above it, their unit chosen by total, the `#next_to_present`
    line's M, as waiting_item_units chooses between two headings for one item, chosen first and the others in the
    order unshown_items_in_walk_order gives; return chosen's heading line and the units of the rewritten
    walk-document. A later close walks on from chosen, so the items still unshown
    come next, and items numbered later stand in the order they were shown."""
    document = minutes.with_name(minutes.name[:-len(walk_finder.MINUTES_SUFFIX)] + ".md")
    lines = document.read_text(encoding="utf-8").split("\n")
    spans = {unit[3]: (unit[3], unit[4]) for unit in units if unit[3] in placing}
    rest = unshown_items_in_walk_order([item for item in placing if item != chosen], placing)
    # close's walk_document_items already ran waiting_item_units on the waiting items, which hold answered_numbers,
    # with this total, so it cannot raise UnusableRange here.
    _, answered_units = walk_finder.waiting_item_units(document, None, answered_numbers, total, parser, units)
    insert_line = walk_finder.approval_walk_document_new_item_insert_line_number_past_whole_item_sub_steps_and_withdrawn_versions
    start = max([min(spans)] + [insert_line(units, unit, len(lines)) for unit in answered_units])
    kept = [(index, line) for index, line in enumerate(lines)
            if not any(first <= index < end for first, end in spans.values())]
    joined = []
    chosen_line = None
    # An item whose last line is not blank, moved above a `**Item N of M**` paragraph, would make that
    # paragraph a continuation of its own and so hide the numbered item; a blank line at every join keeps
    # each block a paragraph of its own.
    for item, block in ([(None, [line for index, line in kept if index < start])]
                        + [(item, lines[spans[item][0]:spans[item][1]]) for item in [chosen] + rest]
                        + [(None, [line for index, line in kept if index >= start])]):
        if joined and block and joined[-1].strip() and block[0].strip():
            joined.append("")
        if item == chosen:
            chosen_line = len(joined)
        joined.extend(block)
    text = "\n".join(joined)
    gathered_units = walk_finder.item_unit_spans(text, parser)
    if sorted(unit[0] for unit in gathered_units) != sorted(unit[0] for unit in units):
        raise Failure(GATHERING_WOULD_LOSE_AN_ITEM.format(document=document, minutes=minutes))
    document.write_text(text, encoding="utf-8")
    return chosen_line, gathered_units


def numbered_heading(heading, number, total):
    """The unnumbered item heading `## <title>` with the running count `Item number of total: ` before its title."""
    marks, title = UNNUMBERED_HEADING_PARTS.match(heading).groups()
    return NUMBERED_HEADING.format(marks=marks, number=number, total=total, title=title)


def unnumbered_item_numbered(walk_finder, minutes, first, units):
    """Write the running count `Item K of M: ` into the unnumbered item heading on line first of the walk-document,
    K and M as the walk finder's approval_walk_next_unnumbered_item_number and approval_walk_item_total_shown_and_waiting_counted_from_walk_document give them for
    units, the walk-document's units; return K."""
    document = minutes.with_name(minutes.name[:-len(walk_finder.MINUTES_SUFFIX)] + ".md")
    lines = document.read_text(encoding="utf-8").split("\n")
    number = walk_finder.approval_walk_next_unnumbered_item_number(units)
    lines[first] = numbered_heading(lines[first], number, walk_finder.approval_walk_item_total_shown_and_waiting_counted_from_walk_document(units))
    document.write_text("\n".join(lines), encoding="utf-8")
    return number


def unnumbered_item_text_once_numbered(walk_finder, minutes, first, units, number, total):
    """Return the text of the unnumbered item whose heading is on line first of the walk-document, as item_text
    will give it once unnumbered_item_numbered has written `Item number of total: ` into that heading."""
    document = minutes.with_name(minutes.name[:-len(walk_finder.MINUTES_SUFFIX)] + ".md")
    lines = document.read_text(encoding="utf-8").split("\n")
    end = next(unit[4] for unit in units if unit[3] == first)
    lines[first] = numbered_heading(lines[first], number, total)
    return "\n".join(lines[first:end]).strip()


def new_item_for_held_answer_numbered(walk_finder, minutes, value, answered_numbers, parser, placing, summary):
    """Number the unnumbered item right after the answered items' unit in the walk-document, as the close step's
    HOLD_ANSWER_FLAG asks, and return the `#next_to_present` value naming it; raise Failure, writing nothing, when
    the unit right after is not unnumbered, or when it waits on an item still to come: an unshown item of placing,
    the walk-document's placing of its unshown items, the summary item, or a numbered item that is neither answered
    now nor decided, as approval_walk_minutes_read_returning_decided_item_numbers says
    with the answered items decided now."""
    document = minutes.with_name(minutes.name[:-len(walk_finder.MINUTES_SUFFIX)] + ".md")
    text = document.read_text(encoding="utf-8")
    units = walk_finder.item_unit_spans(text, parser)
    try:
        _, answered_units = walk_finder.waiting_item_units(document, value, answered_numbers, None, parser, units)
    except walk_finder.UnusableRange as problem:
        raise Failure(f"the last `#next_to_present` line in {minutes}, `{value}`: {problem}")
    after = units.index(answered_units[-1]) + 1
    if after == len(units) or not walk_finder.approval_walk_unit_is_unnumbered_item(units[after]):
        found = (f"`{text.split(NEWLINE)[units[after][3]].strip()}`" if after < len(units)
                 else "none, since it is the last item")
        raise Failure(NO_UNNUMBERED_ITEM_AFTER.format(document=document, item=" and ".join(answered_numbers),
                                                      found=found))
    lines = text.split(NEWLINE)
    decided = approval_walk_minutes_read_returning_decided_item_numbers(walk_finder, minutes, parser, answered_numbers)
    # An unnumbered item is keyed by its heading's line index, an int; a numbered one by its number, a str.
    to_come = sorted((other for other in placing.get(units[after][3], (None, set()))[1]
                      if other in placing or other == summary
                      or (isinstance(other, str) and other not in decided)),
                     key=str)
    if to_come:
        raise Failure(HELD_NEW_ITEM_WAITS_ON_UNSHOWN.format(
            document=document, item=" and ".join(answered_numbers), new_item=f"`{lines[units[after][3]].strip()}`",
            waited_on=", ".join(f"`{lines[other].strip()}`" if isinstance(other, int) else f"item {other}"
                                for other in to_come)))
    number = unnumbered_item_numbered(walk_finder, minutes, units[after][3], units)
    return f"item {number} of {walk_finder.approval_walk_item_total_shown_and_waiting_counted_from_walk_document(units)}"


def deferred_item_heading_noted(walk_finder, minutes, numbers, total, parser, noted=True):
    """With noted, put the deferred note right after the running count of the walk-document heading that names
    exactly the items numbered, whatever M it gives, unless it already holds the note; return the lines to print
    when no such heading exists. Without noted, take the note out of that heading, if it holds it, and return no
    lines. Of two such headings, as in a walk-document renumbered before numbers were never reused, the one whose
    M is total, the `#next_to_present` line's, is taken, or the first when none or both are."""
    document = minutes.with_name(minutes.name[:-len(walk_finder.MINUTES_SUFFIX)] + ".md")
    text = document.read_text(encoding="utf-8")
    lines = text.split("\n")
    note = walk_finder.APPROVAL_WALK_DEFERRED_ITEM_HEADING_NOTE_AFTER_RUNNING_COUNT
    naming = [unit for unit in walk_finder.item_unit_spans(text, parser) if unit[0] == numbers]
    picked = [unit for unit in naming if unit[1] == total]
    for _, _, _, first, _ in (picked if len(picked) == 1 else naming)[:1]:
        heading = lines[first]
        if noted and note not in heading:
            end = HEADING_COUNT_IN_LINE.search(heading).end()
            lines[first] = f"{heading[:end]} {note}{heading[end:]}"
        elif not noted:
            lines[first] = walk_finder.approval_walk_item_heading_with_deferred_note_removed(heading)
        if lines[first] != heading:
            document.write_text("\n".join(lines), encoding="utf-8")
        return []
    return [CLOSE_DEFERRED_HEADING_NOT_NOTED.format(document=document, note=note)] if noted else []


def minutes_record(walk_finder, minutes_text, parser):
    """Return (the item numbers a line this program wrote decides, a Counter of how many lines this program
    wrote defer each item, a line for a deferral just before the summary item counting twice); every other
    line, an agent's note included, records nothing."""
    words, deferrals = minutes_ruling_words(walk_finder, minutes_text, parser)
    return set(words), deferrals


def minutes_ruling_words(walk_finder, minutes_text, parser):
    """Return ({each item number a line this program wrote decides: the `#ruling_given` word of the last such
    line}, a Counter of how many lines this program wrote defer each item), read as minutes_record reads."""
    words, deferrals = {}, collections.Counter()
    for line in walk_finder.prose_lines(minutes_text, parser):
        match = PROGRAM_LINE_ITEMS.match(line)
        if not match:
            continue
        rest = line[match.end():]
        decides = [index for index, pattern in enumerate(DECIDING_LINES) if pattern.match(rest)]
        out_of_the_walk = DEFERRING_OUT_OF_THE_WALK_LINE.match(rest)
        if not decides and not out_of_the_walk and not any(pattern.match(rest) for pattern in DEFERRING_LINES):
            continue
        try:
            items, _ = walk_finder.parse_items(match[1])
        except walk_finder.UnusableRange:
            continue
        if decides:
            word = DECIDING_LINE_WORDS[decides[0]] or RULING_GIVEN_WORDS[rest.rsplit(" ", 1)[-1]]
            words.update(dict.fromkeys(items, word))
        else:
            deferrals.update({item: 2 if out_of_the_walk else 1 for item in items})
    return words, deferrals


def held_answers(walk_finder, minutes_text, parser):
    """Return [(held items' text, their numbers, new items' text, their numbers)] for each held-answer line."""
    holds = []
    for line in walk_finder.prose_lines(minutes_text, parser):
        match = HELD_ANSWER_LINE.match(line)
        if not match:
            continue
        try:
            holds.append((match[1], set(walk_finder.parse_items(match[1])[0]), match[2],
                          set(walk_finder.parse_items(match[2])[0])))
        except walk_finder.UnusableRange:
            continue
    return holds


def held_answers_unresolved(walk_finder, minutes_text, parser):
    """Return the item numbers a held-answer line holds and no line this program wrote decides."""
    decided, _ = minutes_record(walk_finder, minutes_text, parser)
    return {number for _, held_numbers, _, _ in held_answers(walk_finder, minutes_text, parser)
            for number in held_numbers} - decided


def approval_walk_map_each_item_number_to_direct_sub_steps_found_by_walk_document_item_finder(walk_finder, units,
                                                                                               presented):
    """Return {item number: its direct sub-steps, such as 3.1 and 3.2 for 3, but not 3.1.1} for each item of units,
    as item_unit_spans gives them, taken from the sub-steps approval_walk_item_sub_step_units_below_item_in_walk_document
    gives the item's unit, and from that unit itself, as in `Items 3 and 3.1 of 9`. The item's unit is the one
    approval_walk_item_number_unit_within_presented_hierarchy gives it from presented, as
    approval_walk_minutes_unit_each_item_number_was_last_presented_in reads them, and a number it gives none gets no
    entry: so approving the 3.1.1 of `3.1 of 12` does not decide a `3.1 of 9` the minutes presented last."""
    sub_steps_of = {}
    for number in dict.fromkeys(number for unit in units for number in unit[0]):
        unit = approval_walk_item_number_unit_within_presented_hierarchy(walk_finder, units, presented, number)
        if unit is None:
            continue
        below = walk_finder.approval_walk_item_sub_step_units_below_item_in_walk_document(units, unit, [number])
        sub_steps_of[number] = list(dict.fromkeys(
            part for part in unit[0] + [part for each in below for part in each[0]]
            if part.rsplit(".", 1)[0] == number and part != number))
    return sub_steps_of


def approval_walk_unit_is_presented_unit_or_one_of_its_sub_steps(walk_finder, units, presented_unit, number, unit):
    """Return whether unit, of units as item_unit_spans gives them, is presented_unit or one of the sub-steps of its
    item number that approval_walk_item_sub_step_units_below_item_in_walk_document finds, such as `Item 3.1.1 of 12`
    below `Items 3 and 3.1 of 12` for number 3, or that shared unit itself for 3.1."""
    return unit == presented_unit or unit in walk_finder.approval_walk_item_sub_step_units_below_item_in_walk_document(
        units, presented_unit, [number])


def approval_walk_item_units_above_holding_sub_step_unit(walk_finder, units, unit, number):
    """Return {each number above number, such as 3.1 and 3 for 3.1.1: the last unit of units up to unit that names
    it and is unit or has unit among its sub-steps, as 3 for 3.1 of `Items 3 and 3.1 of 12`}, leaving out a number
    that has no such unit."""
    found, parts = {}, number.split(".")
    for depth in range(len(parts) - 1, 0, -1):
        above = ".".join(parts[:depth])
        holding = [each for each in units if above in each[0] and each[3] <= unit[3]
                   and approval_walk_unit_is_presented_unit_or_one_of_its_sub_steps(walk_finder, units, each, above,
                                                                                     unit)]
        if holding:
            found[above] = holding[-1]
    return found


def approval_walk_minutes_unit_each_item_number_was_last_presented_in(walk_finder, units, minutes_text, parser):
    """Return {item number: the unit of units, as item_unit_spans gives them, the walk last presented it in}, read
    from the `#next_to_present` lines of minutes_text outside code, in order. A line presents, for each number it
    names, the one unit naming it, or, when several do, the one whose M is the line's, and with that unit each unit
    above it that holds it, because the read step descends from `3 of 12` to `3.1.1 of 12` and writes a line for the
    leaf only; a number below a newly presented unit whose last unit is not
    approval_walk_unit_is_presented_unit_or_one_of_its_sub_steps of it is dropped."""
    presented = {}
    for line in walk_finder.prose_lines(minutes_text, parser):
        spans = [span.span() for span in walk_finder.CODE_SPAN.finditer(line)]
        for marker in walk_finder.NEXT_MARKER.finditer(line):
            if any(start <= marker.start() < end for start, end in spans):
                continue
            try:
                numbers, total = walk_finder.parse_items(marker[2].replace("`", "").strip())
            except walk_finder.UnusableRange:
                continue
            for number in numbers:
                naming = [unit for unit in units if number in unit[0]]
                if len(naming) > 1:
                    naming = [unit for unit in naming if unit[1] == total]
                if len(naming) != 1:
                    continue
                newly = {number: naming[0],
                         **approval_walk_item_units_above_holding_sub_step_unit(walk_finder, units, naming[0], number)}
                for above, unit in newly.items():
                    for other in [other for other in presented if other.startswith(above + ".")
                                  and not approval_walk_unit_is_presented_unit_or_one_of_its_sub_steps(
                                      walk_finder, units, unit, above, presented[other])]:
                        del presented[other]
                presented.update(newly)
    return presented


def approval_walk_item_number_unit_within_presented_hierarchy(walk_finder, units, presented, number):
    """Return the unit of units, as item_unit_spans gives them, that number names: the one unit naming it; else the
    unit presented gives it, as approval_walk_minutes_unit_each_item_number_was_last_presented_in reads them; else
    the one unit naming it that approval_walk_unit_is_presented_unit_or_one_of_its_sub_steps finds in the unit
    presented gives the nearest number above it, as `3.1 of 12` below a presented `3 of 12`, or the presented
    `Items 3 and 3.1 of 12` itself; else None."""
    naming = [unit for unit in units if number in unit[0]]
    if len(naming) == 1:
        return naming[0]
    if number in presented:
        return presented[number]
    parts = number.split(".")
    for depth in range(len(parts) - 1, 0, -1):
        above = ".".join(parts[:depth])
        if above in presented:
            within = [unit for unit in naming if approval_walk_unit_is_presented_unit_or_one_of_its_sub_steps(
                walk_finder, units, presented[above], above, unit)]
            return within[0] if len(within) == 1 else None
    return None


def items_decided_through_sub_steps(items, words, sub_steps_of, unresolved=frozenset()):
    """Return {item: its `#ruling_given` word} for each item of items, such as 3, not in words, the decided items
    with their words, nor in unresolved, the items whose held answer is unresolved, that has direct sub-steps in
    sub_steps_of, as
    approval_walk_map_each_item_number_to_direct_sub_steps_found_by_walk_document_item_finder
    gives them, among items, such as 3.1 and 3.2, every one of them in words or, deeper, decided through its own
    sub-steps; an item is never decided through its parent. Its word is its sub-steps' one word once moved_on is
    left out, moved_on when that leaves none, and part_answers when it leaves more than one."""
    words, inferred = dict(words), {}
    numbered = [item for item in items if isinstance(item, str)]
    # Deepest first, so a sub-step decided through its own sub-steps, as 5.2 through 5.2.1, counts for its parent.
    for item in sorted(numbered, key=lambda number: -number.count(".")):
        if item in words or item in unresolved:
            continue
        sub_steps = [other for other in sub_steps_of.get(item, []) if other in numbered]
        if sub_steps and all(other in words for other in sub_steps):
            ruled = {words[other] for other in sub_steps} - {RULING_GIVEN_MOVED_ON}
            words[item] = inferred[item] = (RULING_GIVEN_MOVED_ON if not ruled else ruled.pop() if len(ruled) == 1
                                            else RULING_GIVEN_PART_ANSWERS)
    return inferred


def approval_walk_minutes_read_returning_decided_item_numbers(walk_finder, minutes, parser, decided_now=()):
    """Return the item numbers minutes_record finds decided in the walk-minutes at minutes, with decided_now, items
    answered but not yet recorded, counted as decided, plus each item of the walk-document that
    items_decided_through_sub_steps finds decided through its sub-steps, unless held_answers_unresolved holds it."""
    document = minutes.with_name(minutes.name[:-len(walk_finder.MINUTES_SUFFIX)] + ".md")
    minutes_text = minutes.read_text(encoding="utf-8")
    units = walk_finder.item_unit_spans(document.read_text(encoding="utf-8"), parser)
    items = [number for unit in units for number in unit[0]]
    decided = minutes_record(walk_finder, minutes_text, parser)[0] | set(decided_now)
    return decided | set(items_decided_through_sub_steps(
        items, dict.fromkeys(decided), approval_walk_map_each_item_number_to_direct_sub_steps_found_by_walk_document_item_finder(
            walk_finder, units,
            approval_walk_minutes_unit_each_item_number_was_last_presented_in(walk_finder, units, minutes_text, parser)),
        held_answers_unresolved(walk_finder, minutes_text, parser)))


def walk_with_deferred_items_moved(order, summary, decided, deferrals):
    """Return (the walk-document's items in walk order, each item deferred once and not decided moved to just
    before the summary item, or to the end when there is none; the items the minutes record; the items so moved;
    the items left in place)."""
    recorded = {item for item in order if item in decided or deferrals[item] > 1}
    waiting_deferred = [item for item in order if item not in recorded and item in deferrals]
    in_place = [item for item in order if item not in waiting_deferred]
    cut = in_place.index(summary) if summary in in_place else len(in_place)
    return in_place[:cut] + waiting_deferred + in_place[cut:], recorded, waiting_deferred, in_place


def just_before_summary_item(order, summary, answered_numbers, decided, deferrals, placing):
    """Whether, in the walk, the next item after the answered items that the minutes do not record is the
    summary item, with no unshown item still to come."""
    walk, recorded, _, _ = walk_with_deferred_items_moved(order, summary, decided, deferrals)
    to_come = [item for item in walk if item not in recorded]
    answered = [index for index, item in enumerate(to_come) if item in answered_numbers]
    return (summary is not None and summary not in answered_numbers and bool(answered)
            and to_come[answered[-1] + 1:answered[-1] + 2] == [summary]
            and not any(item in placing for item in to_come))


def next_item(walk_finder, minutes, parser, order, summary, answered_numbers, waiting_numbers, placing=None,
              decided_now=()):
    """Return the item numbers the `#next_to_present` line must name next, or [] when the minutes record
    every item.

    Items shown with the answered one that the minutes do not record yet stay waiting. Otherwise the walk
    goes through the walk-document's items in order, as walk_document_items gives them, unnumbered ones
    included, an item deferred once and not decided moved to just
    before the summary item, or to the end when there is none, and names the first item the minutes do
    not record. It starts at the last answered item, or, when that item was just deferred, at the first
    item after it in the walk-document that is not deferred, and goes round once. The unshown items placing
    holds come together, in the order unshown_items_in_walk_order gives, where the first of them comes on that
    round, or just before the summary item or a deferred item when one of those comes sooner; an item is passed
    over while an item it waits on is still to come. An item is decided as
    approval_walk_minutes_read_returning_decided_item_numbers says, with decided_now decided too; the minutes at
    minutes give the deferrals.
    """
    placing = placing or {}
    decided = approval_walk_minutes_read_returning_decided_item_numbers(walk_finder, minutes, parser, decided_now)
    deferrals = minutes_record(walk_finder, minutes.read_text(encoding="utf-8"), parser)[1]
    walk, recorded, waiting_deferred, in_place = walk_with_deferred_items_moved(order, summary, decided, deferrals)
    still_waiting = [item for item in waiting_numbers if item not in recorded and item not in answered_numbers]
    if still_waiting:
        return still_waiting
    answered = [index for index, item in enumerate(order) if item in answered_numbers]
    anchors = [item for item in order[answered[-1]:] if item in in_place] if answered else []
    start = walk.index(anchors[0]) if anchors else 0
    to_come = [item for item in walk[start:] + walk[:start] if item not in recorded]
    unshown = [item for item in to_come if item in placing]
    if unshown:
        late = [index for index, item in enumerate(to_come) if item == summary or item in waiting_deferred]
        cut = min([to_come.index(unshown[0])] + late)
        shown = [item for item in to_come if item not in placing]
        before = len([item for item in to_come[:cut] if item not in placing])
        to_come = shown[:before] + unshown_items_in_walk_order(unshown, placing) + shown[before:]
    return [item for item in to_come if not placing.get(item, (None, set()))[1] & set(to_come)][:1]


def item_a_bump_suspended(walk_finder, minutes, parser, decided_numbers, order, summary):
    """Return the numbers of the item that waited when the user last bumped an item decided_numbers holds, the
    items this close decides, a parent decided through its last sub-step included, while that item is still among
    the walk-document's items in order, is not the summary item, and the minutes record it as neither decided nor
    deferred twice; else []."""
    text = minutes.read_text(encoding="utf-8")
    for line in reversed(walk_finder.prose_lines(text, parser)):
        match = BUMP_MINUTES_LINE.match(line)
        if match and set(walk_finder.parse_items(match["bumped"])[0]) <= set(decided_numbers):
            suspended = walk_finder.parse_items(match["waiting"])[0]
            decided = approval_walk_minutes_read_returning_decided_item_numbers(walk_finder, minutes, parser)
            deferrals = minutes_record(walk_finder, text, parser)[1]
            # The summary item stays last, so a suspended summary gives way to the walk order like any close.
            gone = any(number not in order or number == summary for number in suspended)
            return [] if gone or any(number in decided or deferrals[number] > 1 for number in suspended) else suspended
    return []


def held_items_decided_with(walk_finder, minutes, parser, answered_numbers, item, outcome, decided_through_sub_steps):
    """Return [(close line, the text of the item whose outcome it records)], one close line for each item whose answer the
    minutes hold, directly or through a chain of held items, and that no close line decides yet, giving it the
    outcome of what it was held for: outcome for answered_numbers, when outcome is given, and, for an item
    decided_through_sub_steps maps to approved or disapproved, as items_decided_through_sub_steps gives them, that
    item's outcome."""
    text = minutes.read_text(encoding="utf-8")
    decided, _ = minutes_record(walk_finder, text, parser)
    holds = held_answers(walk_finder, text, parser)
    # Each released number maps to (its outcome, the item whose outcome it carries), so a chain started by this
    # close's answer still names the answered item.
    released = {number: (outcome, item) for number in answered_numbers} if outcome else {}
    for number, word in decided_through_sub_steps.items():
        if word in RULING_GIVEN_WORDS.values():
            released.setdefault(number, (next(key for key, value in RULING_GIVEN_WORDS.items() if value == word),
                                         None))
    # An item held for an item this close decides is decided too, so it releases the items held for it in turn.
    lines, progress = [], True
    while progress:
        progress = False
        for held_text, held_numbers, new_text, new_numbers in holds:
            sources = {released.get(number) for number in new_numbers}
            if None in sources or len({held_outcome for held_outcome, _ in sources}) != 1 or held_numbers <= decided:
                continue
            held_outcome, source = sources.pop()
            source = source or new_text
            decided.update(held_numbers)
            released.update(dict.fromkeys(held_numbers, (held_outcome, source)))
            progress = True
            ruled_by = item if new_numbers <= set(answered_numbers) else new_text
            lines.append((CLOSE_ALREADY_DECIDED_MINUTES.format(
                item=held_text, ruling=HELD_RULING.format(new_item=ruled_by), outcome=held_outcome), source))
    return lines


def gh_failure(command, top, gh_program, timeout):
    """Run gh with command in top; return (its stdout, None), or (None, what went wrong) when it cannot be run,
    exits nonzero or outlasts timeout."""
    try:
        result = subprocess.run([gh_program, *command], cwd=top, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return None, f"did not end within {timeout} seconds"
    except OSError as error:
        return None, f"could not be run: {error}"
    if result.returncode != 0:
        return None, f"exited {result.returncode}: {squeezed(result.stderr.strip()) or 'it printed nothing on stderr'}"
    return result.stdout, None


def pull_request_review_held_on_ruling_hashtag_line_rewritten_with_closing_hash_after_the_hashtag(line):
    """line, a HELD_ON_RULING_LINE, with its hashtag in the closed form, as in `#held_on_ruling# w item 3`."""
    return line.replace(" ", "# ", 1)


def pull_requests_held_on(lines, top, gh_program, timeout):
    """Return ({held line: [the open pull requests whose review holds that line on a line of its own]}, None), or
    (None, what went wrong) when the open pull requests cannot be listed."""
    output, error = gh_failure(HELD_PULL_REQUESTS_LIST, top, gh_program, timeout)
    if error:
        return None, error
    try:
        pull_requests = json.loads(output)
        held = {line: [] for line in lines}
        closed_form = pull_request_review_held_on_ruling_hashtag_line_rewritten_with_closing_hash_after_the_hashtag
        for pull_request in pull_requests:
            found = {line.strip() for review in pull_request["reviews"] for line in (review["body"] or "").split("\n")}
            for line in lines:
                if line in found or closed_form(line) in found:
                    held[line].append(pull_request["number"])
    except (ValueError, TypeError, KeyError) as error:
        return None, f"printed what is not a list of pull requests with their reviews: {error!r}"
    return held, None


def ruling_given_comments_posted(walk_name, rulings, top, gh_program, timeout):
    """Post a `#ruling_given` comment on every open pull request held on the ruling of each item of rulings,
    [(item number, the word)]; return the lines to print, and whether any comment
    could not be posted."""
    lines = {HELD_ON_RULING_LINE.format(walk=walk_name, number=number): (number, word) for number, word in rulings}
    held, error = pull_requests_held_on(list(lines), top, gh_program, timeout)
    in_top = f"cd {shlex.quote(str(top))} && gh "
    closed_form = pull_request_review_held_on_ruling_hashtag_line_rewritten_with_closing_hash_after_the_hashtag
    output, failed = [], bool(error)
    for line, (number, word) in lines.items():
        body = RULING_GIVEN_LINE.format(walk=walk_name, number=number, word=word)
        values = {"number": number, "walk": walk_name, "word": word}
        if error:
            jq = HELD_PULL_REQUESTS_BY_HAND_JQ.format(line=json.dumps(line),
                                                      closed_form_line=json.dumps(closed_form(line)))
            list_command = in_top + shlex.join(HELD_PULL_REQUESTS_LIST) + " --jq " + shlex.quote(jq)
            output += [text.format(error=error, list_command=list_command, **values,
                                   comment_command=in_top + "pr comment <number> --body " + shlex.quote(body))
                       for text in RULING_GIVEN_LOOKUP_FAILED]
            continue
        for pull_request in held[line]:
            command = ("pr", "comment", str(pull_request), "--body", body)
            _, post_error = gh_failure(command, top, gh_program, timeout)
            if post_error:
                failed = True
                output += [text.format(error=post_error, pull_request=pull_request, **values,
                                       comment_command=in_top + shlex.join(command))
                           for text in RULING_GIVEN_POST_FAILED]
            else:
                output.append(RULING_GIVEN_POSTED.format(number=number, pull_request=pull_request, ruling=body))
    return output, failed


def bump(arguments):
    """Make the unshown item arguments.bump names the waiting item, standing right before the item that waited,
    as the docstring's --bump paragraph says."""
    walk_finder = load_walk_finder()
    top, minutes, value, parser = the_open_walk(walk_finder, arguments.cwd)
    pending = unclosed_last_answer(walk_finder, minutes, parser)
    if pending:
        bump_command = check_command_with_cwd(top, *flag_and_value_words("--bump", arguments.bump),
                                              *(flag_and_value_words("--user-reply-as-typed",
                                                                     arguments.user_reply_as_typed)
                                                if arguments.user_reply_as_typed else []))
        raise Failure(BUMP_ANSWER_NOT_CLOSED.format(minutes=minutes, item=pending["item"],
                                                    close_command=step_command_with_cwd(top, "close"),
                                                    bump_command=bump_command))
    waiting, numbers, total = waiting_items(walk_finder, value, minutes)
    _, _, _, units, placing = walk_document_items(walk_finder, minutes, value, numbers, total, parser,
                                                  "check --bump", top, stamp=False)
    document = minutes.with_name(minutes.name[:-len(walk_finder.MINUTES_SUFFIX)] + ".md")
    lines = document.read_text(encoding="utf-8").split("\n")
    title = heading_title(walk_finder, "## " + arguments.bump.strip().lstrip("# "))
    named = [unit for unit in units if heading_title(walk_finder, lines[unit[3]]) == title]
    unshown = [unit for unit in named if unit[3] in placing]
    if not unshown:
        if named:
            decided, _ = minutes_record(walk_finder, minutes.read_text(encoding="utf-8"), parser)
            state = (BUMP_ALREADY_SHOWN_DECIDED if named[0][0] and set(named[0][0]) <= decided
                     else BUMP_ALREADY_SHOWN_WAITING)
            raise Failure(BUMP_ALREADY_SHOWN.format(heading=lines[named[0][3]].strip(), document=document,
                                                    state=state))
        example = next((lines[first].strip().lstrip("#").strip() for first in placing), "the point of the item")
        raise Failure(BUMP_NOT_FOUND.format(document=document, title=arguments.bump.strip(),
                                            command=check_command_with_cwd(top, "--bump", example)))
    first, end = unshown[0][3], unshown[0][4]
    _, waiting_units = walk_finder.waiting_item_units(document, value, numbers, total, parser, units)
    before = waiting_units[0][3]
    number = walk_finder.approval_walk_next_unnumbered_item_number(units)
    count = walk_finder.approval_walk_item_total_shown_and_waiting_counted_from_walk_document(units)
    # Numbered before it moves: an unnumbered heading above the walk-document's first numbered item is no item.
    block = [numbered_heading(lines[first], number, count)] + lines[first + 1:end]
    while block and not block[-1].strip():
        block.pop()
    rest = lines[:first] + lines[end:]
    at = before if before < first else before - (end - first)
    text = "\n".join(rest[:at] + block + [""] + rest[at:])
    document.write_text(text, encoding="utf-8")
    bumped = items_named([str(number)], count)
    words = " ".join((arguments.user_reply_as_typed or "").split())
    append_to_minutes(minutes, [BUMP_MINUTES.format(bumped=bumped, waiting=waiting,
                                                    words=USER_WORDS.format(words=words) if words else ""),
                                NEXT_MARKER_LINE.format(value=bumped)])
    print(BUMP_DONE.format(bumped=bumped, waiting=waiting, command=read_step_command_with_cwd(top)))
    return 0


def close(arguments):
    walk_finder = load_walk_finder()
    top, minutes, value, parser = the_open_walk(walk_finder, arguments.cwd)
    item, answered, statuses, settled = last_answer(walk_finder, minutes, parser, top)
    waiting, waiting_numbers, total = waiting_items(walk_finder, value, minutes)
    try:
        answered_numbers, _ = walk_finder.parse_items(item)
    except walk_finder.UnusableRange as problem:
        raise Failure(f"the last answer line in {minutes}, `{item}`, {problem}.")
    if arguments.hold_answer_until_new_item_answered:
        # Placed first, unstamped, so an unplaceable walk-document, or a new item that waits on one not yet shown,
        # numbers nothing and writes nothing.
        _, _, summary, _, placing = walk_document_items(walk_finder, minutes, value, waiting_numbers, total, parser,
                                                        f"close {HOLD_ANSWER_FLAG}", top, stamp=False)
        value = new_item_for_held_answer_numbered(walk_finder, minutes, value, answered_numbers, parser, placing,
                                                  summary)
        waiting, waiting_numbers, total = waiting_items(walk_finder, value, minutes)
    if not set(answered_numbers) <= set(waiting_numbers):
        append_to_minutes(minutes, [CLOSE_HELD_MINUTES.format(item=item, new_item=waiting),
                                    NEXT_MARKER_LINE.format(value=value)])
        output = ([line.format(item=item, new_item=waiting) for line in CLOSE_HELD_LINES] + statuses
                  + [CLOSE_HELD_NEXT.format(item=item, new_item=waiting, command=read_step_command_with_cwd(top))])
        print("\n".join(output))
        return 0
    count, order, summary, units, placing = walk_document_items(walk_finder, minutes, value, waiting_numbers, total,
                                                                parser, "close", top)
    # Only a plain decision passes to the items held for this one; after a deferral, a move on or answers to parts
    # they stay waiting, so the walk shows them to the user.
    held_outcome = None
    if answered == MOVED_ON:
        recorded, word = CLOSE_MOVED_ON_NO_DECISION_MINUTES.format(item=item), RULING_GIVEN_MOVED_ON
        output = [line.format(item=item) for line in CLOSE_MOVED_ON_LINES]
    elif answered == DEFERRED:
        _, deferrals = minutes_record(walk_finder, minutes.read_text(encoding="utf-8"), parser)
        decided = approval_walk_minutes_read_returning_decided_item_numbers(walk_finder, minutes, parser)
        if any(deferrals[number] for number in answered_numbers):
            recorded, lines = CLOSE_DEFERRED_AGAIN_MINUTES, CLOSE_DEFERRED_AGAIN_LINES
        elif just_before_summary_item(order, summary, answered_numbers, decided, deferrals, placing):
            recorded, lines = CLOSE_DEFERRED_JUST_BEFORE_SUMMARY_MINUTES, CLOSE_DEFERRED_JUST_BEFORE_SUMMARY_LINES
        else:
            recorded, lines = CLOSE_DEFERRED_MINUTES, CLOSE_DEFERRED_LINES
        recorded = recorded.format(item=item)
        word = RULING_GIVEN_DEFERRED
        # A walk with no summary item puts a deferred item last, where it needs no note; an item that leaves the
        # walk takes out the note that says where it went.
        noted = lines is CLOSE_DEFERRED_LINES and summary is not None
        output = ([line.format(item=item) for line in lines]
                  + deferred_item_heading_noted(walk_finder, minutes, answered_numbers, total, parser, noted)
                  + statuses)
    elif answered.startswith(MOVED_ON_PREFIX):
        recorded = CLOSE_MOVED_ON_MINUTES.format(item=item, reason=answered[len(MOVED_ON_PREFIX):])
        word = RULING_GIVEN_MOVED_ON
        output = [line.format(item=item) for line in (CLOSE_MOVED_ON_SHOWN_LINES
                                                      if settled == CHECK_MOVED_ON_SHOWN_PREFIX
                                                      else CLOSE_NOT_SHOWN_LINES)]
    elif answer_is_already_decided(answered):
        # The ruling comes last and may hold any words, so the answer is read only from before it.
        ruled_answer, _, ruling = answered.partition(ALREADY_DECIDED_PREFIX)
        against = ruled_answer.startswith(DISAPPROVED)
        held_outcome = OUTCOMES[DISAPPROVED if against else APPROVED]
        recorded = CLOSE_ALREADY_DECIDED_MINUTES.format(item=item, ruling=ruling, outcome=held_outcome)
        change = CLOSE_ALREADY_DECIDED_AGAINST_CHANGE if against else CLOSE_ALREADY_DECIDED_CHANGE
        output = ([line.format(item=item) for line in CLOSE_NOT_SHOWN_LINES] + [change]
                  + list(CLOSE_TOOK_EFFECT_NEXT))
    else:
        parts = PART_IN_ANSWER.findall(answered)
        if parts:
            recorded = CLOSE_PARTS_TOOK_EFFECT_MINUTES.format(item=item, parts=", ".join(
                f"part {number} {word} {OUTCOMES[word]}" for number, word in parts))
            word = RULING_GIVEN_PART_ANSWERS
        else:
            held_outcome = OUTCOMES[DISAPPROVED if answered == DISAPPROVED else APPROVED]
            recorded = CLOSE_TOOK_EFFECT_MINUTES.format(item=item, answered=answered, outcome=held_outcome)
        output = [line.format(item=item) for line in CLOSE_TOOK_EFFECT_LINES] + list(CLOSE_TOOK_EFFECT_NEXT)
    if answered != DEFERRED:
        deferred_item_heading_noted(walk_finder, minutes, answered_numbers, total, parser, noted=False)
    before = minutes.read_text(encoding="utf-8")
    sub_steps_of = approval_walk_map_each_item_number_to_direct_sub_steps_found_by_walk_document_item_finder(
        walk_finder, units or [], approval_walk_minutes_unit_each_item_number_was_last_presented_in(
            walk_finder, units or [], before, parser))
    inferred_before = items_decided_through_sub_steps(order, minutes_ruling_words(walk_finder, before, parser)[0],
                                                      sub_steps_of, held_answers_unresolved(walk_finder, before, parser))
    append_to_minutes(minutes, [recorded])
    word = RULING_GIVEN_WORDS[held_outcome] if held_outcome else word
    rulings = [(number, word) for number in answered_numbers]
    # A held answer is released by its new item's own answer, or by the last of its sub-steps, at this close or,
    # for one an earlier close missed, at any close after it.
    words, _ = minutes_ruling_words(walk_finder, minutes.read_text(encoding="utf-8"), parser)
    held = held_items_decided_with(
        walk_finder, minutes, parser, answered_numbers, item, held_outcome,
        items_decided_through_sub_steps(order, words, sub_steps_of,
                                        held_answers_unresolved(walk_finder, minutes.read_text(encoding="utf-8"),
                                                                parser)))
    if held:
        append_to_minutes(minutes, [line for line, _ in held])
    for line, ruled_by in held:
        deferred_item_heading_noted(walk_finder, minutes, walk_finder.parse_items(line.split(": ")[0])[0], total,
                                    parser, noted=False)
        output.append(CLOSE_HELD_DECIDED.format(item=ruled_by, held=line.split(": ")[0]))
        rulings += [(number, RULING_GIVEN_WORDS[line.rsplit(" ", 1)[-1]])
                    for number in walk_finder.parse_items(line.split(": ")[0])[0]]
    after = minutes.read_text(encoding="utf-8")
    words, _ = minutes_ruling_words(walk_finder, after, parser)
    unresolved = held_answers_unresolved(walk_finder, after, parser)
    # An item this close decides through its last sub-step gets its ruling too, so a pull request held on it moves.
    rulings += [(number, inferred_word) for number, inferred_word
                in items_decided_through_sub_steps(order, words, sub_steps_of, unresolved).items()
                if number not in inferred_before]
    # The walk order alone can put another unshown item before the item a bump suspended, as when that item was
    # deferred once, so the bump's own record names the item that comes back.
    numbers = (item_a_bump_suspended(walk_finder, minutes, parser,
                                     set(answered_numbers) | {number for number, _ in rulings}, order, summary)
               or next_item(walk_finder, minutes, parser, order, summary, answered_numbers, waiting_numbers, placing))
    if numbers and isinstance(numbers[0], int):
        first = numbers[0]
        if first in placing:  # Not the summary item, which stays where it is.
            first, units = unshown_items_gathered_behind_chosen(walk_finder, minutes, first, units, placing, parser,
                                                                answered_numbers, total)
        numbers = [unnumbered_item_numbered(walk_finder, minutes, first, units)]
    # A number several headings name, such as 3 in `3 of 9` and `3 of 12`, takes its heading's M, so the read step
    # can tell which heading the line names.
    shown_total = count
    if numbers and len([unit for unit in units or [] if numbers[0] in unit[0]]) > 1:
        unit = approval_walk_item_number_unit_within_presented_hierarchy(
            walk_finder, units, approval_walk_minutes_unit_each_item_number_was_last_presented_in(
                walk_finder, units, minutes.read_text(encoding="utf-8"), parser), numbers[0])
        shown_total = unit[1] if unit is not None and unit[1] is not None else count
    named = items_named(numbers, shown_total)
    append_to_minutes(minutes, [NEXT_MARKER_LINE.format(value=named if numbers else CLOSED_MARKER_VALUE)])
    if numbers:
        not_started = start_read_ahead_of_item_after(walk_finder, top, minutes, parser, numbers, shown_total,
                                                     arguments.fast_read_program)
        output += [not_started] if not_started else []
    output.append(CLOSE_READ_NEXT_ITEM.format(next_item=named, command=read_step_command_with_cwd(top))
                  if numbers else CLOSE_NO_NEXT_ITEM)
    # After the lines the agent must pass on to the user, so it is not passed on.
    output += waiting_on_item_prerequisite_lines(walk_finder, minutes, numbers, count, parser) if numbers else []
    # Last, so a gh that fails or hangs cannot keep the answer or the next item out of the minutes.
    ruling_lines, ruling_failed = ruling_given_comments_posted(
        minutes.name[:-len(walk_finder.MINUTES_SUFFIX)], rulings, top, arguments.gh_program, arguments.gh_timeout)
    print("\n".join(output + ruling_lines))
    return 2 if ruling_failed else 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0], epilog=no_answer_table_text(),
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("step", choices=("check", "close", WAITING_ITEM_READ_STEP, READ_AHEAD_WORKER_STEP))
    answer = parser.add_mutually_exclusive_group()
    answer.add_argument("--obvious", action="store_true", help="check: the answer was AO, approve as obvious")
    answer.add_argument("--after-advisor", action="store_true",
                        help="check: the answer was Aa, approve after an advisor check")
    answer.add_argument("--disapproved", action="store_true", help="check: the answer was D, disapprove; reads only the `#new_if_d` texts")
    answer.add_argument("--deferred", action="store_true", help="check: the answer was Z, defer")
    answer.add_argument("--moved-on-no-decision", action="store_true",
                        help="check: the user's reply moved on from an item that asks no decision, such as a "
                             "summary item; records no decision")
    answer.add_argument("--option", type=int, choices=OPTION_NUMBERS,
                        help="check: the answer was O2 or O3, approving the item's \"Option N\" paragraph")
    answer.add_argument("--already-decided", nargs="+", action="append", metavar=("USER_RULING", "ANSWER"),
                        help="check: not shown, since an earlier user-ruling decides the item; USER_RULING cites "
                             "it, and ANSWER is the answer the ruling gives: none or A as the item recommends, or D "
                             "against its recommendation, for its alternative; refused when USER_RULING cites no "
                             "line or section of a standing document, such as a GHI-MD, and its earliest YYYY-MM-DD "
                             "date is missing or more than 90 days before today")
    answer.add_argument(NOW_OVER_LATER_FLAG, action="store_true",
                        help="check: not shown, since its only choice is whether to build something now or later "
                             "and it recommends now; records it as already decided by the user's answer to item 42 "
                             "of walk-me-through-skill-refactor-approval-walk-2026-11-02, \"If the agents recommend "
                             "now versus later, I'm always for now.\"; refused for an item with parts, Option "
                             "paragraphs or `#new_if_d` texts")
    answer.add_argument("--moved-on", metavar="REASON",
                        help="check: the walk moves on from the item with no decision, for REASON; recorded as "
                             "shown to the user when the minutes hold an `#item_page` line for it, else as not shown")
    answer.add_argument("--part-answer", type=part_answer, action="append", metavar="N=ANSWER",
                        help="check: part N of the item was answered ANSWER, A, AO or D; give it once for each part")
    answer.add_argument("--bump", metavar="ITEM",
                        help="check: the user said bump and named ITEM, an item not yet shown, by its heading's title; "
                             "show it next, before the waiting item")
    answer.add_argument("--not-asked", type=not_asked_kind, metavar="KIND",
                        help="check: the user is not asked; settle the item as the row KIND of the no-answer "
                             "table at the end of this help, if its evidence lines pass")
    parser.add_argument("--user-reply-as-typed", metavar="REPLY",
                        help="check: the user's reply exactly as he typed it, written into the minutes beside the "
                             "answer; needed for every answer but --not-asked, --already-decided, "
                             f"{NOW_OVER_LATER_FLAG} and --moved-on")
    parser.add_argument(HOLD_ANSWER_FLAG, action="store_true",
                        help="close: a fast-read finding raised the new item written right after the answered "
                             "one; number it and hold the answer until the user answers it")
    parser.add_argument(AFTER_FIXES_FLAG, action="store_true",
                        help=f"{WAITING_ITEM_READ_STEP}: you changed the item since its last cold-read-fast-read; "
                             "read it again only when the change touches a fact")
    parser.add_argument(SYSTEM_STATUS_CLAIMS_RECHECKED_FLAG, metavar="WHAT_YOU_RAN_AND_WHEN",
                        help=f"{WAITING_ITEM_READ_STEP}: the commands you ran, and when, to recheck each current "
                             "status the waiting item states, such as an agent-seat offline")
    parser.add_argument(FRESH_AGENT_REWRITE_FLAG, type=Path, metavar="FILE",
                        help=f"{WAITING_ITEM_READ_STEP}: the file a fresh-agent wrote the waiting item's new text to, "
                             "from the brief this step printed when the item's proposed text had been revised three "
                             "times; it takes the place of the item's text and starts the count again")
    parser.add_argument("--text-file", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--item", help=argparse.SUPPRESS)
    parser.add_argument("--name", help=argparse.SUPPRESS)
    parser.add_argument(ITEM_NUMBER_PREDICTED_FLAG, action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--cwd", default=os.getcwd(), help="a directory in the walk's checkout")
    parser.add_argument("--cold-read-records", type=Path, action="append",
                        help="a cold-read-records directory to search instead of the defaults; repeatable")
    parser.add_argument("--fast-read-program", type=Path, default=FAST_READ_PROGRAM)
    parser.add_argument("--counts-log", type=Path)
    parser.add_argument("--walk-document-copies-directory", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--gh-program", default=GH_PROGRAM, help=argparse.SUPPRESS)
    parser.add_argument("--gh-timeout", type=float, default=GH_TIMEOUT_SECONDS, help=argparse.SUPPRESS)
    arguments = parser.parse_args(argv)
    if len(arguments.already_decided or []) > 1:
        parser.error(ALREADY_DECIDED_REPEATED)
    arguments.already_decided, *arguments.already_decided_answers = (arguments.already_decided or [[None]])[0]
    printed_command_path_override_words[:] = explicit_path_override_words(arguments)
    copy_problem = None if arguments.step == READ_AHEAD_WORKER_STEP else walk_me_through_walk_document_timestamped_copy_save_on_ned_box_and_oldest_copies_prune(arguments)
    try:
        exit_code = {"check": check, "close": close, WAITING_ITEM_READ_STEP: waiting_item_read,
                     READ_AHEAD_WORKER_STEP: read_ahead_worker}[arguments.step](arguments)
    except Failure as failure:
        print(f"{PROGRAM} {arguments.step}: {failure.args[0]}", file=sys.stderr)
        exit_code = 1
    if copy_problem:
        print(f"{PROGRAM} {arguments.step}: {copy_problem}", file=sys.stderr)
        return exit_code or 2
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
