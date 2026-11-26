---
issue: "[Reviewer brief quotes the follow-up program's reprint, not the follow-up request block the author received](https://github.com/nedsnodes/nedsnodes/issues/4990)"
---

# Reviewer brief quotes the follow-up program's reprint, not the follow-up request block the author received

## Reproduction

On main at e09a80ba0, `follow_up_request_blocks_text` in `scripts/merge-lane-pull-request-reviewer-brief-compose-with-facts.py` gives the reviewer the block that `scripts/pull-request-follow-up-request-after-merge-finding-answers-and-next-step.py <number> print-follow-up-request-block-from-merge-lane-2-reviews` prints at review time. It never reads the block the author's hook, `nn-systems/general-tools/pull-request-follow-up-request-from-merge-lane-2-message-save-and-forked-subagent-brief-hand-over-user-prompt-submit-hook.py`, saved when the author received merge-lane-2's message, even when that saved block is in the git common directory the review tools worktree shares.

This script, run as `python3 reproduce.py <a worktree of origin/main>`, makes a temporary git repository with a second worktree standing in for the review tools worktree. It saves a two-finding block for pull request 4000 with the follow-up program's own `save_follow_up_request_and_clear_answers_when_its_findings_changed`, as the hook does, puts a fake follow-up program in the review tools worktree that prints a different, one-finding block and exits 0, and calls the composer's `follow_up_request_blocks_text` on a description holding `#follow_up_request pull request 4000`:

```python
import importlib.util, subprocess, sys, tempfile
from pathlib import Path

main_wt = Path(sys.argv[1])
def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module); return module
composer = load("composer", main_wt / "scripts/merge-lane-pull-request-reviewer-brief-compose-with-facts.py")
follow_up = load("follow_up", main_wt / "scripts/pull-request-follow-up-request-after-merge-finding-answers-and-next-step.py")

tmp = Path(tempfile.mkdtemp())
author, tools = tmp / "author-checkout", tmp / "tools-worktree-at-main"
subprocess.run(["git", "init", "-q", str(author)], check=True)
subprocess.run(["git", "-C", str(author), "-c", "user.name=x", "-c", "user.email=x@x", "commit", "-q", "--allow-empty", "-m", "init"], check=True)
subprocess.run(["git", "-C", str(author), "worktree", "add", "-q", "--detach", str(tools)], check=True)

received = ("#follow_up_request pull request 4000\n"
            "1. fix-next: `scripts/a.py:10`: the block the author received, finding one\n"
            "2. file-for-later: `scripts/b.py:20`: the block the author received, finding two\n")
reprint = ("#follow_up_request pull request 4000\n"
           "1. fix-in-maintenance: `scripts/c.py:30`: a reprint whose findings and numbering differ\n")
[request] = follow_up.parse_follow_up_request_blocks_from_message_text(received)
follow_up.save_follow_up_request_and_clear_answers_when_its_findings_changed(request, str(author))

fake = tools / "scripts" / composer.FOLLOW_UP_REQUEST_PROGRAM_FILE_NAME
fake.parent.mkdir(parents=True)
fake.write_text("import sys\nsys.stdout.write(" + repr(reprint) + ")\n")

brief = "\n".join(composer.follow_up_request_blocks_text("#follow_up_request pull request 4000\n", tools, None))
print(brief)
print("brief quotes the received block:", "the block the author received" in brief)
print("brief quotes the reprint:", "a reprint whose findings" in brief)
```

It prints:

```
- merge-lane-2's follow-up request for pull request #4000, which the description names, as `scripts/pull-request-follow-up-request-after-merge-finding-answers-and-next-step.py 4000 print-follow-up-request-block-from-merge-lane-2-reviews` prints it from merge-lane-2's reviews:

> #follow_up_request pull request 4000
> 1. fix-in-maintenance: `scripts/c.py:30`: a reprint whose findings and numbering differ

brief quotes the received block: False
brief quotes the reprint: True
```

The saved block the author answered is in the shared git common directory, at `.git/pull-request-follow-up-requests/pull-request-4000-non-blocking-findings.md`, and the brief does not show it.

## Why it matters

The author answers the numbered findings of the block they received; the follow-up program's `open-pull-request` subcommand records the answers against those numbers. The reviewer checks the answers against the block the brief quotes. When the reprint differs from the block sent, the reviewer checks the answers against the wrong findings or the wrong numbering, and can pass a follow-up that left a real finding unanswered, or fault one that answered every finding it was given.

The reprint differs whenever the follow-up program's `print-follow-up-request-block-from-merge-lane-2-reviews` subcommand (the printer, below), or merge-lane-2's reviews, change between the send and the review. The printer changes often: the three latest commits to the follow-up program on main, f378ba0a3, f7f0a7c92 and 27643144a, each change which comments it pairs as one finding, and open pull request [#4936](https://github.com/nedsnodes/nedsnodes/pull/4936) changes which categories it prints. A block merge-lane-2 wrote by hand, because the printer refused, differs from any reprint.

Codex found this as finding 665375011206 in merge-lane-1's review 6068478897 of pull request [#4921](https://github.com/nedsnodes/nedsnodes/pull/4921), and reproduced it on that pull request's merge base and its head (report `nedlern@ned-box:/home/nedlern/nedsnodes-logs/seats/merge-lane-2/merge-helpers/cx/pr4921-b75d917c/codex-code-review-report.md`). Pull request #4921 makes the composer read the saved block only when the printer refuses, so the defect stays at its head; it does not cause it.

## What to do

The owner, the agent-seat overall-cleanup, which wrote the composer's follow-up request facts and pull request #4921, fixes the root cause, and may do it in the follow-up pull request it opens for #4921's non-blocking findings. It chooses between two fixes, or does both:

- In the composer: whenever a saved block can be read, quote it as the block the author received. Parse it and the reprint with `parse_follow_up_request_blocks_from_message_text`, and when their findings differ, quote the reprint beside it and state each difference, such as a finding of the saved block the reprint lacks. When the printer refuses or fails and a saved block can be read, quote the saved block and the refusal. When no saved block can be read, such as for an author whose hook ran on the Mac, whose git common directory ned-box cannot read, state that as a fact in the brief beside the reprint, so the reviewer knows the quoted block may not be the one the author received.
- In the design: the record of what merge-lane-2 sent is kept only on the author's side. Have the program merge-lane-2 runs to send the message save the sent block, hand-written blocks included, on ned-box, keyed by pull request number, so the composer reads one copy for every author, Mac authors included (Codex's suggestion).

Either way, add tests that cause each case the composer handles: a saved block that differs from the reprint, one that matches it, and no saved block.
