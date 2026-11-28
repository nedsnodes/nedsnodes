# Moving NedsNodes to nodes and state machines

This page is the project's overview and design document for turning the bulk of NedsNodes into nodes and state machines. It does not teach what a state machine is. It says how they relate to this project and its plans, and how the work will be done.

**Status.** Pending the user's review, in `docs/nedsnodes-wiki/queue/`: a wiki page needs the user's approval before it moves to `docs/nedsnodes-wiki/`. The work is filed as [GHI 5227, Move the whole project to nodes and state machines](https://github.com/nedsnodes/nedsnodes/issues/5227), and none of the work it plans is built; what already exists, such as the shared command-line prefix of section 8, is named as existing. It carries out the user-rulings of approval-walk nodes-design-forks-2026-11-21, whose items are in `nedlern@ned-box:/home/nedlern/nedsnodes-logs/walk/nodes-design-forks-2026-11-21.md` and whose walk-minutes are `nedlern@ned-box:/home/nedlern/nedsnodes-logs/walk/nodes-design-forks-2026-11-21-minutes.md`; an item number below, such as "item 4", is an item of that approval-walk unless the sentence names another. The approval page, `docs/nedsnodes-wiki/nedsnodes-which-changes-need-the-users-approval.md`, has on main an exception that covers this page: "An edit to a wiki page whose plan the user has approved, carrying out a general instruction he gave for that page, for each part of the edit that makes no decision he has not made; the commit message quotes his instruction, the agent brings him the other parts, and, unlike the other exceptions, the agent tells him in one line what changed." (user-ruling of 2026-11-24).

## 1. The goal

The user asked on 2026-11-21 to "organize as much as possible project into modules that get called from modules that are organized in a state machine like fashion", and for "a really clear design document" on how to turn "as much as possible of this Ned's Nodes project into actual nodes and state machines" that are "set up kind of like Unix modules, except strongly typed". A workflow such as an approval-walk, a cold read or a session-handoff becomes a set of nodes, most of them small programs, and a data file that says which node follows which. Code does the branching, counting, validation and storage. A model is called only for a judgment, except that plain steps stay in one prompt, as the fifth principle below says, and the user is one of the nodes.

Six principles follow from the user-rulings:

- **Every Python script is a strongly typed Unix tool.** A tool can fit into a machine without being one, and it never knows the machine or its next node (user's direction, 2026-11-23).
- **Modular.** Each node has a typed input, a typed output and a fixed list of output states, so that it can be tested alone and reused.
- **State-machine concepts define the structure.** Branches, loops, nesting, parallel work and user interaction are all written in the machine file, in the standard concepts of a state machine (user-ruling of 2026-11-23).
- **Interactive agents mostly talk with the user.** The user's hope, 2026-11-22: "the made agents are mostly just interacting with me, and a lot of tasks are being delegated into the state machine". The mix of long-lived, specialized and fresh agents is to be learned from use, and this design fixes no ratio.
- **Only where needed.** "We don't have to change everything just because it looks pretty." Plain programs stay plain, and a list of steps that neither branch, count nor fetch exact files or log lines stays in one prompt (item 6.2), as `CLAUDE.md`'s code-prompt-code bullet says on main.
- **One piece at a time.** "We don't need to turn this whole thing to a state machine all at once."

### 1.1 How this fits the project

The user's overview of NedsNodes, `README.md`, describes "many modular building blocks that fit together", each block "one documented step in a big state machine, assigned to the actor that handles that step best". Its four actors are code, AIs, code-prompt-code and humans. It estimates that a robust SDLC needs more than 1,000 nodes and that NedsNodes has about 100. This page is the plan for making those blocks real: today most of them are programs and skills whose order lives in prose or in each program's own if-chains.

### 1.2 Work already planned that this page must fit

- **[GHI 2505, Pull requests, their reviews and approval-walks held as one state machine over one schema and one store, so code tracks their state and agents are handed only the steps that need judgment](https://github.com/nedsnodes/nedsnodes/issues/2505).** The user asked for it on 2026-11-03 and said "it's going to affect almost everything. Well, it's going to affect a lot". It plans to hold these records in one store, move them with one machine in code, and make the Markdown walk-minutes generated views; its design is still to be written and approved. It is a large part of this plan already written down, with real failures as evidence: a review decision kept in prose that the fix-round program could not see, and ten programs parsing `#next_to_present`. This page supplies what GHI 2505 leaves generic, namely the node contract built on GHI 3065's tool contract (section 3), the machine format and the runner. GHI 2505 supplies the records for its domain. GHI 2505 is not the first slice: the tool contract and runner are built first, then background work, then GHI 2505's approval-walk half as the first large machine, and its pull-request half follows.
- **[GHI 972, A small HTTP service with SQLite on ned-box keeps one record of every agent-seat on both machines](https://github.com/nedsnodes/nedsnodes/issues/972).** Its nn-shared-database is GHI 2505's first candidate for that store.
- **[GHI 282, Build the design-to-main state machine: the Python machine, its per-state agent-instructions, and the nine items the design defers to the build](https://github.com/nedsnodes/nedsnodes/issues/282).** Deferred (section 12).

## 2. Terms

**cpc-node** and **cpc-tool**, the two kinds of code-prompt-code, are glossary terms on main, added by [PR 4325, Glossary: add cpc-node and cpc-tool as the two kinds of code-prompt-code](https://github.com/nedsnodes/nedsnodes/pull/4325). The term code-prompt-code stays, and `CLAUDE.md`'s code-prompt-code bullet does not name the two kinds: the glossary carries them. This design proposes the terms below for the glossary, in the pull request that builds each one:

- **machine**: a workflow's state machine, stored as one JSON file.
- **node**: one state's work in a machine. Its kind is code, cpc-node, user, machine or parallel (section 4).
- **output state**: the one name, from the node's fixed list, that a node ends in and that picks the next node.
- **runner**: the one program that starts, advances and records every machine.
- **state-machine-run**: one execution of a machine, from `start` to an end state.
- **state-machine-user-answer-node**: a node of kind `user`, whose work is the user's answer.

## 3. A program is a typed Unix tool, and a node when a machine calls it

Every Python script is treated as a tool in the Unix tradition, with typed input and output. Most stay plain tools. A tool is a node only in a machine's file: the tool reads its input, does its one job, reports its output state and exits. It does not name a next node, read a machine file or know that a machine called it, so the same tool also runs by hand or in a pipe.

The tool contract itself, typed arguments and JSON output checked against a schema, is the subject of [GHI 3065, Wiki page on designing in-house tools so agents can give them input and read their output, and on wrapping third-party tools](https://github.com/nedsnodes/nedsnodes/issues/3065), whose work the agent-seat unixify-tools carries out. This design sits on top of that contract and does not replace it.

A node of kind `code` runs a typed Python program, checked by `mypy --strict` in a test suite (item 1). Rust comes in only for a program where a measurement shows Python too slow. A shared module has a snake_case file name so that Python can import it and mypy can follow it (item 2; [PR 4599, Shared Python modules get snake_case file names keeping their common ending](https://github.com/nedsnodes/nedsnodes/pull/4599) carries the rename).

Each program a node runs follows one contract (item 3), built by one shared contract module from the program's dataclasses:

- `--schema` prints as JSON Schema the node's input, output and output states.
- `--help` states the one question the node answers.
- It reads JSON on stdin or from files named by flags, and takes subcommands as `git` and `gh` do.
- Under `--json`, which the runner always passes, it prints one JSON object on stdout, naming its output state in the field `output_state`; without `--json` it prints sentences on stdout, as the exit-code page says. Progress and errors go to stderr.
- Its exit code follows the exit-code page, `docs/nedsnodes-wiki/nedsnodes-how-a-program-reports-success-failure-and-findings-with-its-exit-code.md`: 0 yes, 1 no, 2 could not answer. On exit 0 or 1 the runner reads the one JSON object on stdout. On exit 2, or any other exit code, which the exit-code page says a caller reads as 2, or when stdout is not exactly one valid JSON object, as after a crash, the runner takes the output state `could-not-run`. The output state, not the exit code, picks the next node.

For example, `background-task-check` answers "Did the task finish?":

```json
{"output_state": "task-timed-out", "pid": 4182, "minutes_run": 47}
```

A model's answer that picks the next step gives one output state from a fixed list, so that a program can read it without interpreting prose. A missing or unlisted output state is a failure (item 6.3). A schema tests only the structure of an answer: a model can fill a required field with an invented value.

Unix conventions alone leave four things out, which the user asked this design to cover:

- **An output state richer than an exit code.** An exit code answers one yes-or-no question. The typed JSON object on stdout carries the output state and the data, and diagnostics stay on stderr.
- **Safe re-running after a crash.** A pipe has no record of what finished. Each tool's `--schema` declares `idempotent: true` or `false`, and the contract module defaults to `false`. A node of kind `code` declares `idempotent` in its program's `--schema`; any other node declares it in the machine file; a node that declares nothing is not idempotent; the lint fails when a node of kind `code` declares it in the machine file. The `--schema` test suite runs each tool declaring `true` twice in a sandbox and fails when the second invocation's output or files differ. When a state-machine-run's record shows a node started and never ended, the runner runs it again only if it is idempotent; otherwise the machine goes to that node's `interrupted` transition, which the lint requires for a non-idempotent node.
- **Waiting without blocking.** A tool that starts a long job does not sit and wait; a machine that needs the user enters a `user` node (section 6). The tool exits with an output state such as `running`, the runner holds the state in the state-machine-run's record, and a later `next`, called by the runner's process wrapper (section 5) when the job ends or is stopped at its `timeout_seconds`, continues. A waiting state-machine-run therefore survives a session-handoff.
- **Branching.** A pipe is a straight line. The runner does the branching, from the output state and the machine file.

A program becomes a node by a thin node wrapper, a program that gives it the contract, or by conversion, whether the program is ours, a Unix tool or a third-party tool, and only where a machine needs it (user's direction, 2026-11-22). For example, `scripts/code-review-codex-cell.py` exits 0 even when it reports defects, so a machine needs a node wrapper that gives it an output state.

## 4. What a machine is

A machine is one JSON file that lists its nodes and, for each output state, the next node (item 4). The user asked for standard state-machine concepts, and this format takes them from statecharts, the usual extension of state machines, as SCXML and XState use them:

| Concept | In the machine file |
|---|---|
| Node kinds | `code`, `cpc-node`, `user`, `machine` (a nested machine) and `parallel` |
| Transition | `next`, a map from each output state to a node or an end state |
| Counter and loop limit | `loop` on a transition: the counter, its limit and where to go at the limit |
| Nesting | a `machine` node, whose child's end states are the node's output states |
| Parallel work | a `parallel` node, whose branches run and then join |
| User interaction | a `user` node |
| End state | a name beginning `end:` |

A transition has no general guard; a loop limit is the only condition on it, and a node that must choose from data reports a different output state. A counter is data the state-machine-run keeps. No counter node is needed (item 12). This example is a writer's cold-read loop, with item 12's limit of two rounds:

```json
{
  "machine": "document-write-and-cold-read",
  "start": "write",
  "nodes": {
    "write": {
      "kind": "cpc-node",
      "agent": "writer",
      "prompt": "writer-prompt.md",
      "idempotent": false,
      "timeout_seconds": 3600,
      "next": {"written": "cold-read", "question-for-user": "ask-user", "interrupted": "ask-user", "timed-out": "ask-user", "could-not-run": "end:failed"}
    },
    "cold-read": {
      "kind": "code",
      "program": "cold-read-fast-read",
      "timeout_seconds": 2400,
      "next": {
        "reported": {
          "to": "write",
          "loop": {"counter": "cold-read-rounds", "limit": 2, "at_limit": "end:ready-for-review"}
        },
        "interrupted": "end:failed",
        "timed-out": "end:failed",
        "could-not-run": "end:failed"
      }
    },
    "ask-user": {
      "kind": "user",
      "conversation": "user-facing-agent-inside-state-machine-node",
      "next": {"answered": "write", "stop": "end:stopped", "interrupted": "end:stopped"}
    }
  }
}
```

The `agent` field names an agent that stays the same across the state-machine-run's rounds, so `write` resumes the same writer (section 7). The runner adds one to a loop's counter each time that output state occurs, and goes to `at_limit` when the count reaches the limit, so this example does at most two cold reads.

**Data between nodes.** `start` takes the state-machine-run's input as JSON. A node's input on stdin is the previous node's output, unless its `input` field names an earlier node's output. A `machine` node passes its input to the child and returns the child's last output. A `parallel` node's output is one JSON object keyed by branch name. Every node except a `user` node sets `timeout_seconds`, and the lint fails one that does not; a program lists each node whose limit is far above or close to its slowest logged runs; a node stopped at its limit gets a record of its last output and whether it had gone silent; and each node that sets `timeout_seconds` maps `timed-out` to its own next node, such as one retry under a loop limit, or to an end state that sends the agent-seat's interactive agent one message (user-ruling of 2026-11-24). For the build, the user's guidance is that a first limit is the writing agent's estimate times about 4 ("we'll have to start with defaults, which can be very generous"), and that a node reports progress rather than a timer heartbeat, so that silence means no progress ("it shouldn't just be a timer heartbeat, it should be like a progress thing, and if it's no progress, it should stop emitting").

A lint, run as a test, reads each machine and fails when a node is unreachable, an output state has no transition, a loop has no limit and is not the loop through a `user` node that the next paragraph allows, a transition names a node that does not exist, an output's schema does not fit the input schema of the node that receives it, a non-idempotent node has no `interrupted` transition, or a tool imports the runner or reads a machine file (item 4, and section 3's rule that a tool does not know its machine). The lint needs the machine as data, which is why the user approved JSON over python-statemachine. The machine stays a JSON file run by the Python runner; a run yields by saving its state and exiting, as section 3 says under "Waiting without blocking", and no Lua is used (user-ruling of 2026-11-25).

A loop needs no count limit when it passes through a `user` node whose output states other than `answered` all go to end states; the lint fails any other loop without a limit, including a branch of the loop that skips the `user` node.

## 5. The runner

One runner has three commands (item 4):

- `start <machine>` creates a state-machine-run and prints its id.
- `next <state-machine-run>` runs `code` and `cpc-node` nodes itself until the machine ends, a node waits, as a node holding `running` or a `parallel` node's join does, or a node needs the agent-seat's interactive agent or the user, then prints that step and returns. It is also what notices a crash: it reads the state-machine-run's record and finds a node started and never ended.
- `answer <state-machine-run>` takes that node's output state and output JSON, and refuses any other output state or output that fails the node's schema.

The runner validates each node's output against the input schema of the node that receives it, so no node repeats that validation. The runner's schema check rests on the user's approval of item 4; no node adds its own validation, and `CLAUDE.md`'s two conditions for a guard stay as they are. It counts every loop. The project uses one JSON Schema library, compared in section 5.1, which replaces the hand-written `answer_problems()` validator in `scripts/merge-lane-pull-request-claude-reviewer-headless-run-and-review-post.py`.

**Extraction.** Item 4 extracts the runner from the three existing step programs. Because the user deferred design-to-main on 2026-11-23, the runner is extracted from two: the approval-walk's check program, `nn-systems/skills/walk-me-through/walk-me-through-answer-added-texts-cold-read-fast-read-check-and-close.py`, and the `next-step` of `scripts/pull-request-follow-up-request-after-merge-finding-answers-and-next-step.py`.

**Many machines at once.** Each agent can run one or more machines, so every state-machine-run keeps its own record and shares no in-memory state with another.

**Parallel work.** The user described this as "Lua-like cooperative multi-threading". A `parallel` node starts its branches as child processes. No runner process waits at the join: `next` records the branches and returns, and a later `next` collects those that finished. A timeout on each branch catches a process that dies or never returns. The node ends in `all-succeeded`, `some-failed` or `timed-out`. For example, a cold-read-full-run starts its cold-read-cells this way. A state-machine-run that waits is resumed by the work it waits on: each process the runner starts runs inside the runner's process wrapper, which stops it at its time limit, records its result and calls `next`, `next` sends the agent-seat's interactive agent one message when the next node needs it, a `user` node is resumed when the agent hands the runner the user's reply, and no scheduled job polls state-machine-runs (user-ruling of 2026-11-24). How a machine treats a failed or late branch of its parallel node, such as whether five of seven cold-read reports are enough, is decided when that machine is designed, not by one rule for every parallel node.

**Handoff.** The handoff-system lists an agent-seat's unfinished state-machine-runs for its successor, which continues each one with `next` (item 4).

### 5.1 Choosing the JSON Schema library

The runner holds each node's schema as a JSON document, because a node is a separate process and can be a wrapped outside tool. So the library must validate data against a JSON Schema document. Facts below were read from PyPI and from a trial install on ned-box's Python 3.14 on 2026-11-23.

| | python-jsonschema | Pydantic |
|---|---|---|
| Latest release | [4.26.0](https://pypi.org/project/jsonschema/), 2026-01-07 | [2.14.4](https://pypi.org/project/pydantic/), 2026-11-19 |
| Standards support | [Full support for Draft 2020-12](https://python-jsonschema.readthedocs.io/en/stable/) and earlier drafts; validated a sample contract in the trial | [Generates JSON Schema from Python types](https://docs.pydantic.dev/latest/concepts/json_schema/); its documentation describes no validation against a schema document |
| Dependencies | 4 direct: `attrs`, `jsonschema-specifications`, `referencing`, `rpds-py` (compiled) | 4 direct: `annotated-types`, `pydantic-core` (compiled), `typing-extensions`, `typing-inspection` |
| License | MIT | MIT |
| Static typing | No `py.typed` in the package; needs the separate [`types-jsonschema`](https://pypi.org/project/types-jsonschema/) stubs for mypy | Ships `py.typed` |
| Builds a schema from a dataclass | No: the shared contract module needs a small generator | Yes |

Pydantic is the stronger choice inside one Python process, and it would save the small generator. It does not do the runner's job, which is validating a JSON document against a schema document, without a second library. The project's one JSON Schema library is python-jsonschema, the PyPI distribution `jsonschema`, at 4.26.0, to be pinned in `nn-systems/general-tools/python-libraries-pinned-requirements.txt` by the pull request whose program first imports it, with `types-jsonschema` for mypy.

**What is installed today.** ned-box's default `python3` has `jsonschema` 4.19.2 from the Ubuntu package `python3-jsonschema`, installed automatically as a dependency of `cloud-init-base`. No program in the repository imports it and the pinned requirements do not list it, so the project cannot rely on that copy. Whether the Mac has it is not known: ned-box's key on the Mac admits only a fixed set of requests, none of which reports this.

## 6. The user is a node

The user-ruling of 2026-11-23: "the user is a node. So the way nodes declare whether they need to talk to the user is by inserting a state which will trigger a user interaction". Where a machine needs the user, the machine enters a `user` node, and the user's answer is that node's output state. Whether a machine talks with the user is therefore visible in its file, and a lint can list every such place.

A state-machine-user-answer-node names who holds the conversation, in its `conversation` field:

- `user-facing-agent-inside-state-machine-node`, the default: an agent inside the node talks with the user, so the conversation does not "jump way outside the node".
- `agent-seat-interactive-agent`: the agent-seat's interactive agent holds the conversation, for a case where that agent has the context. The user's example is an approval-walk.

**A design conversation stays inside its node.** While a design is written, the user talks with an agent made for that design, which the runner launches (item 9.3, where the user chose the alternative, D).

**How the user reaches that agent.** The user works through Remote Control and expects that a `claude -p` agent-session will not appear there. The proposed mechanism starts the agent as `claude -p` with a known agent-session id. When it reaches a state-machine-user-answer-node, the runner opens the same conversation with `claude --resume <id>` in a tmux window, as the agent-seats run, so that it shows in Remote Control. When the user is done, the agent calls the runner's `answer` with the output state, and the runner closes the window. A window closed without an `answer` is the node's `interrupted` output state.

This mechanism is untested. The first build step for state-machine-user-answer-nodes is a test on ned-box of three things: the resumed agent keeps the whole conversation, it appears in Remote Control, and the runner receives its output state when the agent calls `answer`. If the first build step's test finds that a resumed `claude -p` agent does not appear in Remote Control, the runner starts an interactive `claude` in a tmux window when the machine reaches the `user` node, and closes it after that agent calls `answer` (user-ruling of 2026-11-24).

## 7. Who does each step

This section names the steps that need judgment, as `CLAUDE.md` requires. Everything else is code.

| Step | Needs judgment? | Who does it |
|---|---|---|
| Launch agents, order nodes, count rounds, validate output, store state, retry, time out | No | The runner |
| Talk with the user, decide what to ask | Yes | The agent the state-machine-user-answer-node names |
| Decide | Yes | The user |
| Write and revise a document | Yes | A writer agent |
| Review a document or code and report findings | Yes | A reviewing agent |
| Pick an output state where the choice is a judgment | Yes | The node's agent, from its fixed list |
| Say whether a program should become a node | Yes | The agent reviewing that program (section 11) |

Each writer and each reviewing agent starts as a fresh-agent and stays the same agent for later rounds on that document, up to the loop's limit, as design-to-main's rule that an agent lives through its design version already says (`docs/design-to-main/design-to-main-state-machine.system.design.md`, §1, user-ruled 2026-09-11); the writer's limit is item 12's. A writer revises its own text from the cold-read reports. A pull request's fix-round keeps its forked subagent, as `scripts/pull-request-fix-round-author-brief-from-blocking-findings-and-one-commit-every-finding-answered-check.py` dispatches it. The runner, not the writer, counts cold-read rounds, and after the second round the document moves on whatever that read reports (item 12).

The runner withholds the Agent tool from a writer it launches, so that the writer cannot hand its reports to a fresh-agent.

## 8. Plain step lists stay in one prompt

The test the user approved in item 8 compared one prompt listing every step with one `claude -p` turn per step in the same agent-session. It used plain steps and three test runs of each way at each length (report: `nedlern@ned-box:/home/nedlern/nedsnodes-logs/seats/MD-skills/nodes-design/prose-vs-session-turns-test-2026-11-22/report.md`):

| Steps | Cost, one turn per step against one prompt | Tokens | Wall time |
|---|---|---|---|
| 4 | 1.14× | 1.95× | 1.7× |
| 8 | 1.29× | 2.69× | 2.1× |
| 16 | 1.54× | 3.36× | 2.5× |

Ratios are of medians. Both ways did every step correctly in all 18 test runs, so these easy steps showed no difference in reliability. The test did not measure what code adds, such as validating each step's result, retrying one step or resuming after a crash. Plain steps that one agent does in order, and that neither branch, count nor fetch, stay in one agent prompt. A state machine ends that prompt, and starts a new cpc-node or a new turn, only after a step whose output code must check, or that code must be able to retry or resume after; the plain steps that follow go in the next prompt (user-ruling of 2026-11-25).

Every program that starts `claude -p` passes `--strict-mcp-config` through the shared command-line prefix, `nn-systems/general-tools/claude-code-headless-run-command-line-prefix-with-no-connectors-and-explicit-permission-mode-common.py`, which step 1 of section 12 renames. With the account's connectors on, one 8-step test run cost $3.86, against $0.10 to $0.13 with them off.

## 9. The record and the log

The user asked to log "the beginning and end of each state", what is passed in and out, and time and tokens, modelled on agent-session JSONL files. Item 4 asks for an append-only record of each state-machine-run. This design makes them one file, a JSONL file per state-machine-run, which is both the state the runner resumes from and the log for analysis.

Each line is one event: `state-machine-run-started`, `state-machine-node-started`, `state-machine-node-ended`, `state-machine-user-question-asked`, `state-machine-user-question-answered` or `state-machine-run-ended`. A `state-machine-node-ended` line carries the node, output state, exit code, duration, tokens, a hash and path of the input and output, and for a `cpc-node` node its agent-session id and JSONL path. Each state-machine-run's record is one JSONL file in the log-store on ned-box; a state-machine-run on the Mac waits while ned-box cannot be reached.

## 10. First use: background work across a session-handoff

The user approved this first use on 2026-11-21 (item 67 of approval-walk md-skills-questions-waiting-2026-11-05, walk-minutes `nedlern@ned-box:/home/nedlern/nedsnodes-logs/walk/md-skills-questions-waiting-2026-11-05-minutes.md`). Today a reincarnate-seat kills the agent-session's background work, so the handoff-deferral holds the session-handoff while the agent-session sits at high context.

- **Work that can detach.** A background Bash command on a list kept in code, such as the cold-read grid, is started detached by a hook that matches the list, so no agent has to remember to detach it and the command no longer holds the session-handoff. A test on ned-box on 2026-11-13 showed that such a command survives `claude` exiting. The handoff-supervisor passes each one to the successor as a state-machine-run whose first node is `background-task-check`.
- **Work that cannot detach.** A subagent or workflow keeps the handoff-deferral and the rerun of a killed task, which item 44.2 of that approval-walk approved.
- **Both at once.** The session-handoff waits only for the work that cannot detach. The successor receives the detached work as state-machine-runs and the rest through the existing fields.

Proposed transitions for `background-task-check`:

| Output state | Next |
|---|---|
| `finished` | End: the successor reads the output |
| `failed` | Rerun the task once under a loop limit, then bring it to the agent |
| `running` | The runner holds the state; the detached task runs as a node with its own `timeout_seconds`, inside the wrapper that stops it at that limit and calls `next` when it ends (section 5) |
| `task-timed-out` | Rerun the task once under a loop limit, then bring it to the agent |
| `timed-out` | `background-task-check` itself was stopped at its own `timeout_seconds`: report to the agent, without a rerun |
| `could-not-run` | Report to the agent |

Item 67 of that approval-walk also promised a report of how long session-handoffs were held at high context, from past records. That report is not yet written (section 12, step 5).

## 11. Reviewing every program

The user expects to "review pretty much every Python's and script we've got to see where it fits". The review records each program's one outcome in a ledger file, and a test lists every program without one:

- **Stays a plain program or cpc-tool.** Most programs that no machine calls.
- **Wrapped.** It keeps working as it is, and a thin wrapper makes it a node.
- **Converted.** It adopts the shared contract module.
- **Part of a machine.** Its step order moves into a machine file.

Every outcome but the first adopts the tool contract of section 3 when that program is next rewritten. Rewrites go one at a time.

The state-and-node inventory of 2026-11-22 (`nedlern@ned-box:/home/nedlern/nedsnodes-logs/seats/MD-skills/nodes-design/state-and-node-inventory-2026-11-22/reconciled-inventory.md`) is the starting list. It found that some states have no handler, that seven have conflicting handlers or definitions, and that the approval-walk, follow-up and fix-round are if-chain machines. These are the candidates the user named:

- where a new file goes, what its directory is, and whether a directory or file needs renaming;
- the name check, and the differing rules for different Markdown files;
- the sequences of cold reads and reviews, for prose and for code;
- the session-handoff's steps and states.

**Conflicts and states nothing acts on.** Each conflicting definition of a state is reduced to one, such as frozen-head's three definitions and the finding category's four spellings. Each state nothing acts on either gets a handler or is deleted, and the target is none left. The user expects these are "holes in our design", some obsolete.

**Proposed lint.** One registry file lists each state outside a machine: its name, the thing it sits on, its one defining file and its handler. For a state in a machine, the node's `--schema` and the machine file already hold those facts, and the lint reads them there. A test fails when a registered state has no handler or has a second definition, and when a state literal the lint recognizes is not registered. The inventory's current exceptions start in a list in that file, and the lint compares the list with the copy on `origin/main` and fails on an added entry, so the lint can merge before the cleanup ends and reaches zero exceptions when it does.

## 12. Proposed order

The user has no "strong opinions" on order beyond easy parts first. Each step is one or more pull requests, and each pull request leaves the project working:

1. Finish the shared-module rename.
2. Take the shared contract module and its `--schema` test suite from unixify-tools' work on GHI 3065, which builds them; the nodes work starts on them once they are on main.
3. Build one shared fresh-agent call on the shared command-line prefix. Ten programs now use that prefix, but each reads the agent's answer its own way.
4. Build the runner and lint, extracted from the two step programs, with the JSONL record.
5. Build the first use, background work, and write the report on session-handoffs held at high context.
6. Test the state-machine-user-answer-node mechanism of section 6.
7. Move approval-walks onto the runner, as GHI 2505's approval-walk half, then cold reads and reviews. The approval-walk's bookkeeping moves into code, and out of `/walk-me-through`, when approval-walks move onto the runner; the walk check program gains no step chain before then, and [GHI 3896, Move approval-walk bookkeeping from the walk-me-through skill into the walk check program](https://github.com/nedsnodes/nedsnodes/issues/3896) stays open, listing the steps proposed for the runner to take over; if the nodes design is not approved, GHI 3896 can still be built as it stands. Each approval-walk item gets a lasting id from its record when approval-walks move onto the runner, with no `#approval_walk_item_id` line before then.
8. Review the remaining programs a few at a time, as section 11 says.

**Deferred: design-to-main.** The user decided on 2026-11-23 to defer all continued work on design-to-main until other parts have stabilized, and to keep what this design raised about it in [GHI 282, Build the design-to-main state machine: the Python machine, its per-state agent-instructions, and the nine items the design defers to the build](https://github.com/nedsnodes/nedsnodes/issues/282). No step above changes or depends on it. Its code and design stay as they are.

**Testing.** Each step carries its tests. The runner's tests cover every output state, a loop reaching its limit, a nested machine, a parallel branch that fails and one that times out, resuming a state-machine-run from its record, and refused answers. Each failure path is caused in a test, as `CLAUDE.md` requires. One shared function prints a test file's last line and exits with its code: `END <UTC time> passed=<N> failed=<M> #nc_test_suite_pass`, `#nc_test_suite_fail` or `#nc_test_suite_could_not_run`, with exit 0, 1 or 2 to match, as in `END 2026-11-24T23:10:02Z passed=12 failed=0 #nc_test_suite_pass`. The lint is tested on one bad machine per rule.

## Deferred-decisions

Each line is a case the build or later evidence settles; whoever settles it removes the line and writes the decision into the section it belongs to.

- How the `agent` field binds to an agent-session id so that `write` resumes the same writer, and what happens when that agent-session is gone.
- How `next` delivers its one message to the agent-seat's interactive agent, which agent-seat that is when a subagent or a program started the state-machine-run, what happens when that agent-seat is mid-handoff, and how a machine file marks the end states that send it.
- Whether `could-not-run`, `interrupted` and `timed-out`, the output states the runner takes itself, count in every node's fixed list for the lint's rule that an output state has no transition.
- The output state the runner takes when a node's JSON names a missing or unlisted output state, fails the receiving node's input schema, or disagrees with the exit code, and how output sent to an end state is checked.
- How `next` tells a node that crashed from one still working, such as a node within its limit, a node holding `running`, an open `user` window or a parallel branch's sibling, and the limit on reruns of an idempotent node that crashes each time.
- How a node reports progress, on which stream and in what form, how long a silence counts as "gone silent", and which output a stopped node's record keeps.
- A loop counter's start value, its scope, and whether it resets when an outer loop enters its loop again.
- How a `machine` node's input reaches its child's first node, how the child's `end:` names become the parent's output states, and how a `machine` or `parallel` node's limit relates to the limits inside it.
- What a node receives after a node that ended in a state the runner took itself, how `input` names one occurrence of a node the run visited twice, and how one input schema covers several senders.
- Where machine files live and how they are named, how `program` and `prompt` resolve to files, which fields name a `machine` node's child and a `parallel` node's branches, and where a `cpc-node`'s and a `user` node's schemas come from.
- The `parallel` node's output state when its branches end in a mix of failure and timeout, what its output holds for a failed branch, and whether it stops running siblings once one fails.
- How two calls of `next` or `answer` on one state-machine-run at once are kept from interleaving.
- How `start` takes the state-machine-run's input, how `answer` takes its output state and output JSON and names the waiting node when two nodes wait, what `answer` does on a state-machine-run with no waiting node, and what `next` prints when the machine ends.
- The record's file name and layout in the log-store, each event's fields, where input and output payloads are kept, and how the runner reads a record whose last line was cut short.
- How a state-machine-run on the Mac writes its record to the log-store, and what resumes it once ned-box can be reached again.
- How the `--schema` test suite gives each idempotent tool its input, and what it compares, so that a tool whose output reports a changing subject, such as `background-task-check`'s `minutes_run`, still passes.
- The thresholds, schedule and reader of the program that lists nodes whose limit is far above or close to their slowest logged runs.
- How the hook that detaches a background command puts it under the runner's process wrapper, and who creates its state-machine-run.
- Which code the runner takes from the two step programs, and whether those programs move onto the runner at step 4 or later.
- The state registry file's path and row format, how the lint recognizes a state literal, and what the lint compares against before the file is on `origin/main`.
- The program ledger's path and row format, and which files count as programs.
- Which agent-session a `user` node resumes when the node before it is not a `cpc-node`, and what the fallback's interactive `claude` is told to ask.
- Which output states of a `user` node may continue a loop with no count limit, when the node has others besides `answered`.
- What `idempotent: true` means for a `cpc-node` or `user` node, and how it is tested.
- When the JSON Schema library replaces `answer_problems()` in `scripts/merge-lane-pull-request-claude-reviewer-headless-run-and-review-post.py`.
