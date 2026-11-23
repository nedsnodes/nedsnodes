---
issue: "[The surviving-mutant-test release program records an agent-seat as released without checking that the message sent was the go-ahead](https://github.com/nedsnodes/nedsnodes/issues/4099)"
---

# The surviving-mutant-test release program records an agent-seat as released without checking that the message sent was the go-ahead

## Reproduction

The program is `scripts/merge-lane-unreviewed-prs-count-then-next-agent-seat-go-ahead-to-open-surviving-mutant-test-prs.py` on main at commit 45fd905ec; another pull request is renaming it on 2026-11-21. When that name is gone from main, `git log --follow --name-status -M 45fd905ec..origin/main -- scripts/merge-lane-unreviewed-prs-count-then-next-agent-seat-go-ahead-to-open-surviving-mutant-test-prs.py` prints its new path. Make a worktree of main at commit 45fd905ec, such as with `git worktree add --detach /tmp/release-45fd905ec 45fd905ec`, save the script below as `release-unchecked-text-repro.py` in a directory of its own, and run `python3 release-unchecked-text-repro.py /tmp/release-45fd905ec`. The script stands in for the headless sender: its one SendMessage, to the agent-seat `mutant-seat`, succeeds but carries the text `hello` instead of the go-ahead.

```python
"""Finding 2: the sender's SendMessage succeeds with a text other than the
go-ahead; the release program still records RELEASED."""
import importlib.util, sys, tempfile
from pathlib import Path
root = Path(sys.argv[1])
spec = importlib.util.spec_from_file_location("rel", root / "scripts/merge-lane-unreviewed-prs-count-then-next-agent-seat-go-ahead-to-open-surviving-mutant-test-prs.py")
rel = importlib.util.module_from_spec(spec); spec.loader.exec_module(rel)
state = Path(tempfile.mkdtemp())
(state / rel.AGENT_SEATS_FILE_NAME).write_text("mutant-seat\n")
rel.unreviewed_open_pull_requests_count = lambda: 3
def fake_headless(*a, **k):
    o = rel.idle_sweep.HeadlessOutcome()
    o.sends = [{"to": "mutant-seat", "message": "hello", "succeeded": True, "result": "ok"}]
    return o
rel.idle_sweep.run_headless = fake_headless
code = rel.main(["--state-directory", str(state)])
print("exit", code)
print("released file:", (state / rel.RELEASED_FILE_NAME).read_text().strip())
```

It printed, on 2026-11-21:

```
RELEASED mutant-seat
3 open pull requests, not drafts, have no review from ned-review-merge on their head commit. mutant-seat was sent this message, and is recorded as released in /tmp/tmp0pz1lygb/agent-seats-given-surviving-mutant-test-prs-go-ahead.jsonl:
merge-lane-2's review queue is quiet: 3 open pull requests, not drafts, wait for a review from merge-lane-2. You may now open your pull requests that only add tests for surviving mutants: one per source file, with at most 5 open at a time.
exit 0
released file: {"agent_seat": "mutant-seat", "released_at": "2026-11-21T21:37:31Z"}
```

`mutant-seat` received only `hello`, yet the program prints that it was sent the go-ahead, records it as released, and exits 0. Every later run skips it, so it is never told it may open its mutant-test pull requests.

## What is wrong

`release_message_send_problems` checks the send with the idle sweep's `send_problems`, in `scripts/agent-seat-idle-sweep-headless-judge-wake-messages-send-and-user-alerts-write.py` at line 584, which checks only that each send went to the agent-seat and succeeded. The idle sweep itself also runs `sent_texts_other_than_code_wrote`, line 595, to catch a sender that changed the text; the release program does not. The program came from pull request [4008](https://github.com/nedsnodes/nedsnodes/pull/4008). The defect was found by the Codex review cell, `scripts/code-review-codex-cell.py`, while reviewing pull request [4021](https://github.com/nedsnodes/nedsnodes/pull/4021), which does not change this program.

## What to do next

The owner, merge-lane-2, fixes the root cause: a send counts as passed only when the text sent is the text code wrote, the go-ahead with the do-not-reply sentence the program appends, compared as `sent_texts_other_than_code_wrote` compares. Otherwise the program records nothing, prints the text that was sent, and exits as it does for a failed send, so the next merge tries again. The root cause is that a caller of `send_problems` can check where a message went without checking what it said; the owner considers giving `send_problems` the expected text, so that every caller checks both. The fix carries a test with the case above.
