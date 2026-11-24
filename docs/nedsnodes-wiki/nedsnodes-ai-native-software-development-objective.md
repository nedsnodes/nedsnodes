# NedsNodes Notes

We want to structure as much of NedsNode as a state machine. This means we must carefully control how each nodes connects, in to ensure the next node in the machine  gets what it needs, but little else so it is safe and efficient. 

If something here seems wrong, stale, or at odds with what the repository actually does, report it by filing a GitHub issue through the ghi-write skill.

How to classify these reports, by type and severity, is not yet decided.

## Review and root-cause routing

A root-cause report says what was observed and with what evidence, the mechanism, which expectation was violated and which document defines it, the causal chain, what else was considered, the earliest unsupported assumption, where in the graph it should go, and what the human must decide if anything. Many diagnoses need no human decision at all, and forcing one wastes the scarcest thing in the system.

1. **A node attempts its task and reports what it could not do.** 
2. **Parallel work is optimistic.** Separate work items proceed in separate worktrees until an actual dependency or conflict appears. Git detects textual conflicts and resolves the ones it can; the rest go to an arbitrator or a human. Tests and reconciliation address semantic compatibility.
3. **Observability is valuable feature**
4. **Instead of relying on the sessions context we try to use durable storage**
5. **The human is a node unlike the others because he is often not available.** Therefore things to review need to be queued. 
6. **Nodes are defensive, checking both inputs and outputs**

## Project organization

The existing NedsNodes placement rule remains useful: GitHub Issues carry walkable state, Markdown carries substantive reasoning, and queues hold material whose disposition is undecided.

| Place | Holds |
| --- | --- |
| `docs/nedsnodes-wiki/` | Current standing knowledge that is difficult to reconstruct from code alone |
| `docs/issues/<n>-<slug>.md` | Substantive working material paired with a GitHub Issue, including its design, which is written here and refined in place until its code lands, then pinned to what landed; design-to-main adds the design-contract beside it, and both move into the component's directory when code starts |
|                                                        |                                                              |
| `nn-queue/` | Notes the user requested in July and August 2026, all walked; takes no new notes |
| `docs/nedsnodes-wiki/queue/` and `docs/issues/queue/` | Material with a known destination awaiting review |
| GitHub Issues and pull requests | Work state, decisions, reviews, and check-in path |
| Git | Code, current Markdown, history, hashes, and ordinary provenance |

Every output is either current at its canonical location or in a named queue with a queue-drain. A queue item is reviewed by the human and then promoted, edited in place, demoted to supporting evidence, or dropped with a recorded reason.

A substantial work item uses a GHI-MD: the issue carries current state and the Markdown file carries the detail needed by an independent reader. Clarifications edit the current body rather than stacking corrective comments; comments record genuinely new events. When an issue closes, its working document follows the repository's established archive, promotion, or deletion rule.

Logical output versions are immutable even when their repository file is revised in place. Git commit and content hash identify the accepted version; an edit creates a new logical version and `supersedes` edge. Reviews and descendants remain tied to the old hash until reconciliation accepts them against the new one.

## Hacks and Accepted residuals

An accepted residual records a review objection that the human has considered and chosen not to address. It states the objection, why it is acceptable for this project now, and the concrete evidence that would reopen it. Reviewers do not repeatedly re-file it without that new evidence.

- Nits are repaired and recorded without unnecessary interruption.
- Independent work proceeds concurrently; textual conflicts and whatever semantic conflicts the checks cover are detected at integration, and the rest are detected in production and routed back.
- A nonconverging repair stops after a bounded diagnostic ladder.
