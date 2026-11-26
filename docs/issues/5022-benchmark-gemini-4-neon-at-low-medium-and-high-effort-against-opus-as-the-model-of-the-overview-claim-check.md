---
issue: "[Benchmark Gemini 4 Neon at low, medium and high effort against Opus as the model of the overview claim check](https://github.com/nedsnodes/nedsnodes/issues/5022)"
---

# Benchmark Gemini 4 Neon at low, medium and high effort against Opus as the model of the overview claim check

## Why

The overview claim check, `nn-systems/skills/overview-write/overview-write-architecture-overview-claim-check-by-fresh-agent.py`, has a fresh-agent check every claim of an nn-architecture-overview against the code. It runs on `claude-opus-5-5` at effort `high` (the constants `FRESH_AGENT_MODEL` and `FRESH_AGENT_EFFORT`). `scripts/pull-request-review-plan.py` refuses a pull request that changes an overview until a claim-check report shows no claim ranked must fix, so the claim check's running time delays every such merge, and its cost is paid on every round. In the 24 hours to 2026-11-21 20:33Z it ran 9 times on the handoff overview at about $12 an invocation.

On 2026-11-26 the user kept Opus for the claim check rather than switch to Sonnet (item 51 of approval-walk archive-review-ghi-3836-archived-task-list-dispositions-and-mutation-hold-approval-walk-2026-11-20, walk-minutes `nedlern@ned-box:/home/nedlern/agents/fleet-restart-at-login/docs/walk/archive-review-ghi-3836-archived-task-list-dispositions-and-mutation-hold-approval-walk-2026-11-20-minutes.md`). He then asked for this comparison: "If claim check is a speed critical thing, we should at least try Neon, maybe even Neon High, or Neon High, and compare it to Opus. So I guess maybe do a GHI for that."

No model has been measured on the claim check. None of the 9 reports of 2026-11-21 shows a claim ranked must fix, so the past reports cannot show how many real errors a model catches.

## What to do

1. Build an answer key. Copy two or three real overviews whose newest claim-check report says every claim is supported, such as `docs/nedsnodes-wiki/nedsnodes-handoff-architecture-overview.md` and `docs/nedsnodes-wiki/nedsnodes-project-architecture-overview.md`, each as it stood at the commit that report checked. Change about ten sentences in each copy so that each one states something the code at that commit contradicts, and record in the key each changed sentence's exact text. Keep the copies and the key in the log-store on ned-box, not in the repository.
2. Write a benchmark runner, a program kept beside the key in the log-store, that for each copy makes a detached worktree at the copy's commit with the copy in the overview's place, fills in the claim check's `FRESH_AGENT_PROMPT_TEMPLATE`, and runs only that first judgment, not the rest of the claim check's pipeline, three times for each of `claude-opus-5-5` at effort `high`, `gemini-4-neon-low`, `gemini-4-neon-medium` and `gemini-4-neon-high`. `nn-systems/general-tools/agy-print-prompt-run-in-empty-home-sandbox.py` runs `agy` in an empty directory that cannot see a checkout, so the runner gives the Gemini models read access to the worktree another way. It records each invocation's wall-clock time, and for Claude its `total_cost_usd`; `agy` runs on the user's Google login and reports no cost, which the score table says.
3. Write a scorer, a program beside the runner, that parses each report with the claim check's own patterns and counts, per invocation, the changed sentences ranked must fix (caught) and the unchanged sentences ranked must fix (wrongly flagged), matching by the key's exact text. Must fix is the rank that blocks a merge. A failed or malformed invocation counts as catching nothing. Each model's score is its worst invocation of the three.
4. Bring the user the score table in an approval-walk item. Recommend the fastest model that catches at least as many changed sentences as Opus with no more wrong flags; when none does, recommend keeping Opus.

## What this waits on

[GHI 4653, "Replace every architecture overview with a guide-agent for each system under `nn-systems/`, and remove the overviews and everything that writes, checks or refreshes them"](https://github.com/nedsnodes/nedsnodes/issues/4653) is open, and its design goes to the user before anything is removed. If he approves it, the claim check is removed and this benchmark is not needed. Start step 1 only after the user rules on that design and keeps the claim check. If he approves GHI 4653, close this issue as not planned. [GHI 2532, "Overview claim check: judge again only new, changed or flagged claims, and keep a supported claim's verdict while its wording and cited files are unchanged"](https://github.com/nedsnodes/nedsnodes/issues/2532), approved and not yet built, changes which claims go to the model again; the benchmark gives each model the whole overview and does not depend on it.
