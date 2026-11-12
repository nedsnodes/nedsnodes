# How to change an agent's trained default by pairing a refusing hook with a correction

Agents are trained to do some things one way. When this project needs another way, a sentence in `CLAUDE.md` or a skill rarely wins: the agent read the sentence long before the moment it applies, and at that moment the trained habit takes over. What works is a pair: a block that stops the habit at that moment, and a correction that tells the agent what to do instead.

## The two halves

- **The block** is a hook that refuses the action as the agent takes it. A hook can refuse only the routes its code recognises, so the same action taken another way gets through.
- **The correction** is the instruction that says what to do instead. One copy goes in the block's refusal message, which the agent reads at the moment the block fires. Another goes where the agent will be when it takes a route the block cannot recognise, such as the step of the skill it is following.

Neither half works alone. The correction alone loses to the habit. The block alone teaches the agent a second route to the same mistake, one the block cannot recognise.

## Example: copying an old version over a GHI-MD

A GHI-MD is the Markdown file that holds a GitHub issue's text.

1. **The habit.** On 2026-10-27 an agent wrote a new version of a GHI-MD in a separate file, kept it for days while it was reviewed, then ran `cp` to put it over the GHI-MD. Main had changed the GHI-MD meanwhile, and the copy undid four of those changes. merge-lane-2 caught the loss in review.
2. **The block.** The same `cp` is now refused by `.claude/guard-hooks/ghi-md-whole-file-replacement-soft-block.py`, which refuses any whole-file replacement of an existing GHI-MD: `cp`, `mv`, `tee`, a `>` redirection, or the Write tool. Its refusal, with the GHI-MD's path and the marker file's path filled in:

   > Refused: this command replaces the whole GHI-MD {path}, which can undo changes merged into it on main after your copy was written.
   >
   > Change the GHI-MD with the Edit tool instead, one passage at a time, so main's other changes stay.
   >
   > If you mean to replace the whole file, write your reason into {marker_path} and run the command again.

3. **The corrected action.** The agent changes the GHI-MD with the Edit tool, and main's changes stay. The hook is a soft-block, as the [glossary](../nedschorus-glossary.md) defines it, because replacing the whole file is sometimes right.
4. **The route the block cannot recognise.** An agent could paste the old text in through the Edit tool, passage by passage, and undo main's changes the same way. So the "Edit:" step of the /ghi-write skill, which every agent follows to change a GHI-MD, carries the correction too:

   > When your new text was drafted in another file, carry over only your own changes, passage by passage, because main may have changed the GHI-MD since.

## When to use the pattern

- **When the habit has already cost work.** Build a block only for a failure that has happened, or will soon, under the guard rule in `CLAUDE.md`.
- **When code can tell the action is wrong nearly every time.** A block that often refuses the right action is soon ignored. Make it a soft-block when the action is sometimes right, and a hard-block only when the action is never right.
- **Show the correction at the right moment:**
  - not too early, because a rule read at the start of an agent-session has faded by the time it applies;
  - not too late, because after the action the damage may not be undoable;
  - not too often, because a message that appears on every action gets ignored, even when it matters.

  A refusal fires on every attempt, which is right, because every attempt it stops is a real mistake.

For how to word the refusal, read [How to write a tool-message-to-agent](../nedschorus-how-to-write-a-tool-message-to-agent-such-as-a-hook-refusal-or-script-error.md). For where a block sits among other ways of making an agent follow a rule, read [the enforcement ladder](../nedschorus-enforcement-ladder.md).
