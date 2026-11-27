# nedsnodes

A system in which one human and a small number of AI agents build and improve the software-development system they themselves run on.

## Founding principles

1. **Re-derive from the requirement; never inherit machinery by default.** Ask what is needed and no more.
2. **Complexity is earned, step by step:** manual → script the human runs → automation. Each step admitted on evidence, by the human.
3. **Behavior belongs in code wherever it can be expressed there** — testable, versionable, inert until called. Prose is for judgment only. When it is a choice between python and a prompt, python; between bash and python, python — bash only for one-liners not worth a file.
4. **Durable artifacts are written for a fresh reader** — an agent with repository access, the project instructions, and the document itself, but no conversation history — and tested by handing them to exactly such an agent.
5. **Present-tense truth.** Documents state what is; git history holds what was. The built system is the source of truth — a design page carries the date on which it described that truth, and newer code and open issues may have advanced past it.

## Where things live

| Place | Holds |
|---|---|
| `docs/nedsnodes-wiki/` | Standing knowledge, kept current (Obsidian vault). |
| `docs/issues/<n>-<slug>.md` | Working documents, one per GitHub issue, disposed when the issue closes. |
| `~/.claude/handoffs/` | Session handoffs, one file per agent-seat, on each machine only and never committed. |
| `nn-queue/` | Notes the user requested in July and August 2026, all walked; takes no new notes |
| `docs/nedsnodes-wiki/queue/`, `docs/issues/queue/` | Destination-rooted queues: wiki-bound doctrine and GHI-MD-bound documents awaiting the user's drain (promote / edit / demote / drop). |
| `nn-systems/` | The project's built systems, one directory each: `cold-read/` (the programs that run a cold-read-fast-read and a cold-read-full-run), `handoff/` (session reincarnation, the handoff-supervisor and the handoff writer), `main-gatekeeper/` (the program meant to be the only way a change reaches main, dormant until activated), `nn-shared-database/` (the service of the nn-shared-database) and `skills/` (programs that some of the skills run); beside them, `general-tools/`, which is not a system, as the glossary's nn-system entry says. |
| Issues labeled `queue-drain-candidate` | Issues awaiting the user's drain — same format as every issue, walkable; no work ever waits on one, and nothing requiring the user's admission takes effect without it. |
