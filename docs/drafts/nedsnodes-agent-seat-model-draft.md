# The agent-seat model

How work is divided among agent-seats, and why. Each agent-seat's agent-sessions read its seat-brief; this page is the shared background behind every seat-brief.

## The words this model uses

The project glossary, `docs/nedsnodes-wiki/nedsnodes-glossary.md`, defines this page's hyphenated terms, such as agent-seat, seat-brief, session-handoff and conversation-tail. The handoff-system's nn-architecture-overview, `docs/nedsnodes-wiki/nedsnodes-handoff-architecture-overview.md`, describes reincarnate-seat: the machinery that replaces an agent-session with a successor that continues from its session-handoff.

## The grouping rule

An agent-seat owns a subject area with shared context, which its seat-brief names. The tasks on its task list are work within that subject area, not a queue that defines the agent-seat.

**Group tasks by shared context, not by workload.** The test for whether a task belongs to an agent-seat: *would an agent that knows the agent-seat's subject area do the task better than one that does not, because the task needs the same files, code and decisions?* Judge a new task against the subject area as a whole, not against one task in it. If yes, the task goes to that agent-seat. If no, it goes to another agent-seat, even when that leaves an agent-seat with nothing to do.

The user's reasoning, which this model serves:

- An agent with focused context is smarter than one carrying unrelated history. Confusion is the expensive failure.
- **An agent-seat with nothing to do costs almost nothing**: its agent-session spends no tokens while it waits for a prompt, and it needs none of the user's attention, so never give one agent-seat two unrelated subject areas to keep it busy. It is not literally free: a running agent-seat is restarted after a reboot or a crash, and each restart spends tokens; an unretired agent-seat holds an agent-home; and retiring it later takes the steps below. Those costs are small.
- When an agent-session's context runs low, the agent writes a session-handoff and the handoff-supervisor replaces the agent-session with a successor that starts from the session-handoff and the conversation-tail, not from the whole dialog, so each successor carries the subject area forward without the rest of its predecessor's history.
- The user comes back to an agent-seat weeks later, so its name must say what the agent-seat is for without opening anything.

## Which agent-seats exist

An agent-seat on a machine is a directory `~/agents/<name>` there that is its agent-home and for which its handoff-supervisor has left a state file, `~/.claude/handoffs/<name>-supervisor-state.json`, or a session-handoff, `~/.claude/handoffs/<name>-handoff.md`; `scripts/recover-crashed-seats.py` finds the agent-seats of its machine this way. Other entries under `~/agents`, such as the `<name>-worktrees` directories, a guide-agent's directory such as `~/agents/ghi-guide-agent`, and loose files, are not agent-seats. An agent-seat's seat-brief, the `CLAUDE.local.md` in its agent-home, says what it owns. The user chooses which agent-seats run.

An agent-seat's name is a multi-part name, such as `merge-lane-2` or `fleet-restart-at-login`, made only of letters, digits, `-` and `_`, which is all the launchers accept. The naming page `CLAUDE.md` points to, `docs/nedsnodes-wiki/nedsnodes-how-to-choose-a-name-for-files-code-and-glossary-terms.md`, applies to it, as `/start-agent-seat` step 1 says, and the name must be unused on both machines, because it is also the agent-home's directory name, the agent-seat's tmux server name, the prefix of its files in `~/.claude/handoffs/`, and the Remote Control address other agent-sessions send messages to.

## Pausing and retiring an agent-seat

They are different.

**Paused** — nobody is using the agent-seat for now. The user types `/exit` in its agent-session, because an agent cannot exit itself; the handoff-supervisor records the clean exit and stops. The agent-home, the agent-seat's topic-worktrees and their commits stay as they are. The agent-seat's session-handoff was already read when the exited agent-session started, so the next launch does not start from it, and what the exited agent-session had not written to a commit, its task list or another file since that session-handoff is lost. This is the ordinary way to leave an agent-seat, and it needs no cleanup. To start a paused agent-seat again, run its launcher, as "Launching an agent-seat" below says.

**Retired** — the name is being freed or repurposed. Four steps, in order:

1. **Stop the handoff-supervisor first.** A running agent-seat writes a fresh handoff each time reincarnate-seat replaces its session, so archiving while its handoff-supervisor is alive only clears the file until the next one. Exit the session and confirm no handoff-supervisor process remains for the agent-seat.
2. **Archive the handoff.** Move it to `~/.claude/handoffs/retired/<seat>-handoff-YYYY-MM-DD.md`, creating the directory if needed; if that name exists, append `-2`, `-3` before `.md`; never move onto an existing archive.
3. **Archive the seat-brief.** Copy `~/agents/<seat>/CLAUDE.local.md` to `~/.claude/handoffs/retired/<seat>-seat-brief-YYYY-MM-DD.md`, under the same naming rule as the handoff. Git does not track the seat-brief, so the next step deletes it from the agent-home; the log-store keeps the transcript mirror's last copy.
4. **Release the worktree and the branch.** On the agent-seat's machine, `git -C ~/Projects/nedsnodes worktree remove ~/agents/<seat>` (not `rm` — the worktree stays registered otherwise, and `git worktree prune` is then needed), and then delete the branch, `git -C ~/Projects/nedsnodes branch -d <seat>`, since removing a worktree leaves its branch behind. An agent-seat launched but never used may have an empty directory and no worktree at all; `rmdir` is correct there.

## Launching an agent-seat

`/start-agent-seat` gives the command that launches a new agent-seat on ned-box, and `docs/nedsnodes-wiki/nedsnodes-mac-and-ned-box-machine-setup.md` gives the command, run on the Mac, that reaches an agent-seat on either machine. Both launchers, `scripts/launch-claude-ubuntu` and `scripts/launch-claude-mac`, are attach-or-create: running an agent-seat's name again attaches to its tmux session, or to the shell left behind when its handoff-supervisor stopped, rather than starting a second one, and a `--first-prompt-file` given then does nothing. That shell prints how to start the agent-seat again: exit the shell, then run the launcher again. To pause an agent-seat, the user types `/exit` in its agent-session; to leave it running, he detaches from tmux (`Ctrl-b d`).

A launch that starts a handoff-supervisor starts the agent-session from the first of these that applies:

1. **A session-handoff not yet consumed.** When `~/.claude/handoffs/<seat>-handoff.md` holds a session-handoff whose `session-handoff-sequence-number` is above the last one the handoff-supervisor consumed, the agent-session starts from it. When that session-handoff carries `ask-user-before-restart`, the handoff-supervisor first asks "restart? y/n" and stops unless the answer is y.
2. **A crashed agent-session's transcript.** When no session-handoff waits and the handoff-supervisor recorded no exit, it resumes the agent-seat's newest transcript and ignores any first prompt, unless the launch also gives `--first-prompt-file-wins-over-crashed-transcript`.
3. **The first prompt.** Otherwise the agent-session starts from the `--first-prompt-file` given, or, without one, from the handoff-supervisor's own first prompt, "You are <seat>. No handoff exists yet; ask what to work on.", so the agent asks the user what to work on.

So an agent-session that crashes keeps what it was doing through its transcript, and one the user ends with `/exit` loses what it had not written down since its last session-handoff, as "Paused" above says.

Each launcher makes the agent-home before the agent-session starts, on a detached HEAD at `origin/main`, when `~/agents/<seat>` is not already a git checkout, because project settings — the status line, the context-threshold handoff hook, the instruction-file guard — are read from `.claude/settings.json` in the working directory when an agent-session starts, and an agent-session started in a directory without that file runs without them, with only the user's own settings in `~/.claude/`. When `~/agents/<seat>` is already a checkout, the launcher leaves it as it is. When the agent-home cannot be made, the launcher says so and starts the agent-session anyway.

## What separate branches do and do not protect

An agent-seat's agent-home holds no branch: it rests on a detached HEAD at `origin/main`, and git refuses commits in it. Its work is on nn-topic-branches, each in a worktree of its own, and git refuses to check one branch out in two worktrees. That keeps two agent-seats off one branch and nothing more: it is a check rather than a guarantee, since `git worktree add --force` overrides it and a separate clone is invisible to it, and two agent-seats editing the same file on different branches meet at the merge.

It protects nothing outside git. `~/.claude/handoffs/` and the agent-seat's tmux server, `tmux -L <seat>`, are per-machine state keyed by the agent-seat's name, so two agent-seats with one name on the same machine would share them. Across machines nothing on disk collides, but the name is also the agent-seat's Remote Control address, which agent-sessions on both machines send messages to, which is why one name means one agent-seat across both machines.

Some files are guarded outside git: the guarded-files, which the glossary lists, among them `CLAUDE.md`, every seat-brief, everything under the repository's `.claude/` apart from `worktrees/`, `jobs/` and `handoffs/`, every wiki page, and `docs/agents/seat-first-prompt.md`. The instruction-file guard, `.claude/guard-hooks/instruction-file-guard.py`, refuses an Edit, Write or NotebookEdit of a guarded-file until the change has the approval `docs/nedsnodes-wiki/nedsnodes-which-changes-need-the-users-approval.md` asks for, and `.claude/guard-hooks/guarded-file-unapproved-change-afterward-backup-and-ask-hook.py` notices a guarded-file changed any other way, such as by a shell command, keeps every version, and has the agent ask the user.

**Keep nothing that matters only in an agent-session.** Work belongs in commits and pushes; decisions belong in the wiki, the designs and the GHIs. The session-handoff is never pushed: it lives on the agent-seat's machine only, as do the agent-seat's conversation-tails, its seat-brief and its task list under `~/.claude/tasks/`, and an agent-seat paused with `/exit` keeps its committed work and loses what its agent-session had not written down since its last session-handoff.
