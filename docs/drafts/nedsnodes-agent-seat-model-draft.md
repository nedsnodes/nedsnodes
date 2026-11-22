# The agent-seat model

How work is divided among agent-seats, and why. Each agent-seat's agent-sessions read its seat-brief; this page is the shared background behind every seat-brief.

## The words this model uses

The project glossary, `docs/nedsnodes-wiki/nedsnodes-glossary.md`, defines this page's hyphenated terms, such as agent-seat, seat-brief, session-handoff and conversation-tail. The handoff-system's nn-architecture-overview, `docs/nedsnodes-wiki/nedsnodes-handoff-architecture-overview.md`, describes reincarnate-seat: the machinery that replaces an agent-session with a successor that continues from its session-handoff.

## The grouping rule

An agent-seat's work is the body of related work it owns: a subject area with shared context, not an ordered queue.

**Group tasks by shared context, not by workload.** The test for whether two tasks belong to one agent-seat: *does doing the first make the agent smarter about the second?* If yes, same agent-seat. If no, separate agent-seats — even when that leaves an agent-seat idle.

The user's reasoning, which this model serves:

- An agent with focused context is smarter than one carrying unrelated history. Confusion is the expensive failure.
- **An agent-seat with nothing to do costs almost nothing** — few tokens, no attention — so never give one agent-seat two unrelated subject areas to keep it busy. It is not literally free: an unretired agent-seat holds an agent-home, and retiring it later takes the steps below. That cost is small.
- The natural unit of work is a series of related tasks; when an agent-session's context runs low, the agent writes a session-handoff and a successor replaces the agent-session, starting from the session-handoff and the conversation-tail rather than the whole dialog.
- The user comes back to an agent-seat weeks later, so its name must say what the agent-seat is for without opening anything.

## Which agent-seats exist

Each agent-seat has an agent-home, `~/agents/<name>` on its machine, but not every entry under `~/agents` is one: a guide-agent's directory such as `~/agents/ghi-guide-agent`, the `<name>-worktrees` directories and loose files there are not. An agent-seat's seat-brief, the `CLAUDE.local.md` in its agent-home, says what it owns. The user chooses which agent-seats run.

An agent-seat's name is a multi-part name, such as `merge-lane-2` or `fleet-restart-at-login`, made only of letters, digits, `-` and `_`, which is all the launchers accept. The naming page `CLAUDE.md` points to, `docs/nedsnodes-wiki/nedsnodes-how-to-choose-a-name-for-files-code-and-glossary-terms.md`, applies to it, as `/start-agent-seat` step 1 says, and the name must be unused on both machines, because it is also the agent-home's directory name, the agent-seat's tmux server name, the prefix of its files in `~/.claude/handoffs/`, and the Remote Control address other agent-sessions send messages to.

## Pausing and retiring an agent-seat

They are different.

**Paused** — nobody is using the agent-seat for now. The user types `/exit` in its agent-session; the handoff-supervisor stops with it. The agent-home and the agent-seat's commits stay as they are; its session-handoff was already read, so the next launch, by its launcher as below, does not start from it. This is the ordinary way to leave an agent-seat, and it needs no cleanup.

**Retired** — the name is being freed or repurposed. Four steps, in order:

1. **Stop the handoff-supervisor first.** A running agent-seat writes a fresh handoff each time reincarnate-seat replaces its session, so archiving while its handoff-supervisor is alive only clears the file until the next one. Exit the session and confirm no handoff-supervisor process remains for the agent-seat.
2. **Archive the handoff.** Move it to `~/.claude/handoffs/retired/<seat>-handoff-YYYY-MM-DD.md`, creating the directory if needed; if that name exists, append `-2`, `-3` before `.md`; never move onto an existing archive.
3. **Archive the seat-brief.** Copy `~/agents/<seat>/CLAUDE.local.md` to `~/.claude/handoffs/retired/<seat>-seat-brief-YYYY-MM-DD.md`, under the same naming rule as the handoff. Git does not track the seat-brief, so the next step deletes it from the agent-home; the log-store keeps the transcript mirror's last copy.
4. **Release the worktree and the branch.** On the agent-seat's machine, `git -C ~/Projects/nedsnodes worktree remove ~/agents/<seat>` (not `rm` — the worktree stays registered otherwise, and `git worktree prune` is then needed), and then delete the branch, `git -C ~/Projects/nedsnodes branch -d <seat>`, since removing a worktree leaves its branch behind. An agent-seat launched but never used may have an empty directory and no worktree at all; `rmdir` is correct there.

## Launching an agent-seat

`/start-agent-seat` gives the command that launches a new agent-seat on ned-box, and `docs/nedsnodes-wiki/nedsnodes-mac-and-ned-box-machine-setup.md` gives the command, run on the Mac, that reaches an agent-seat on either machine. Both launchers, `scripts/launch-claude-ubuntu` and `scripts/launch-claude-mac`, are attach-or-create: running an agent-seat's name again attaches to its tmux session, or to its leftover-shell, rather than starting a second one, and a `--first-prompt-file` given then does nothing. The leftover-shell prints how to start the agent-seat again: exit the leftover-shell, then run the launcher again. To pause an agent-seat, the user types `/exit` in its agent-session; to leave it running, he detaches from tmux (`Ctrl-b d`).

**An unconsumed session-handoff outranks the first-prompt file.** When `~/.claude/handoffs/<seat>-handoff.md` holds a session-handoff the handoff-supervisor has not yet consumed, the agent-session starts from it; otherwise, after a crash, the handoff-supervisor resumes the crashed agent-session's transcript when that transcript holds work beyond a successor's opening turns; otherwise the agent-session starts from `--first-prompt-file`, or, without one, the agent asks the user what to work on.

Each launcher makes the agent-home before the agent-session starts, on a detached HEAD at `origin/main`, when `~/agents/<seat>` is not already a git checkout, because project settings — the status line, the context-threshold handoff hook, the instruction-file guard — are read from `.claude/settings.json` in the working directory when an agent-session starts, and an agent-session started in a directory without that file runs without them; the user's own settings in `~/.claude/` still apply. When `~/agents/<seat>` is already a checkout, the launcher leaves it as it is. When the agent-home cannot be made, the launcher says so and starts the agent-session anyway.

## What separate branches do and do not protect

An agent-seat's agent-home holds no branch: it rests on a detached HEAD at `origin/main`, and git refuses commits in it. Its work is on nn-topic-branches, each in a worktree of its own, and git refuses to check one branch out in two worktrees. That keeps two agent-seats off one branch and nothing more: it is a check rather than a guarantee, since `git worktree add --force` overrides it and a separate clone is invisible to it, and two agent-seats editing the same file on different branches meet at the merge.

It protects nothing outside git. `~/.claude/handoffs/` and the agent-seat's tmux server, `tmux -L <seat>`, are per-machine state keyed by the agent-seat's name, so two agent-seats with one name on the same machine would share them. Across machines nothing on disk collides, but the name is also the agent-seat's Remote Control address, which agent-sessions on both machines send messages to, which is why one name means one agent-seat across both machines.

Some files are guarded outside git: the guarded-files, which the glossary lists, among them `CLAUDE.md`, every seat-brief, the repository's `.claude/` apart from `worktrees/`, `jobs/` and `handoffs/`, every wiki page, and `docs/agents/seat-first-prompt.md`. They change only with the approval `docs/nedsnodes-wiki/nedsnodes-which-changes-need-the-users-approval.md` asks for, enforced by the instruction-file guard.

**Keep nothing that matters only in an agent-session.** Work belongs in commits and pushes; decisions belong in the wiki, the designs and the GHIs. The session-handoff is never pushed: it lives on the agent-seat's machine only, as do the agent-seat's conversation-tails, its seat-brief and its task list under `~/.claude/tasks/`, and an agent-seat paused with `/exit` keeps its committed work, while what its agent-session had not written down since its last session-handoff stays only in that agent-session's transcript.
