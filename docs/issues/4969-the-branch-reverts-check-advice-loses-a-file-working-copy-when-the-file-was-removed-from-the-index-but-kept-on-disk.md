---
issue: "[The branch-reverts check's advice loses a file's working copy when the file was removed from the index but kept on disk](https://github.com/nedsnodes/nedsnodes/issues/4969)"
---

# The branch-reverts check's advice loses a file's working copy when the file was removed from the index but kept on disk

## Reproduction

On main at [c07c2ffb2](https://github.com/nedsnodes/nedsnodes/tree/c07c2ffb21e800d4886e90c8dc9790db00440716), `scripts/branch-reverts-a-file-to-an-older-main-version-check.py` reports a branch that sets a file back to a version main has since replaced. For each such file its advice says: if `git diff HEAD -- <path>` prints anything, save it with `git diff HEAD -- <path> > <a file outside this checkout>`; run `git checkout <base> -- <path>`; then put the branch's own changes to the file, and the saved ones, back on top. This reproduction, run in a scratch repository on ned-box on 2026-11-25, follows that advice for a file removed from the index with `git rm --cached` whose working copy was kept:

```
git init -q -b main
git commit -q --allow-empty -m root
echo base > f && git add f && git commit -q -m base
echo branch > f && git commit -qam branch
echo "uncommitted work" > f      # the working copy holds work not yet committed
git rm -q --cached f             # f leaves the index; the working copy stays on disk
git status --short               # prints "D  f" and "?? f"
git diff HEAD -- f               # prints only the deletion of the line "branch"; "uncommitted work" is not in it
git diff -- f | wc -c            # prints 0
git checkout HEAD~1 -- f         # the advice's git checkout, with the base commit
cat f                            # prints "base"
```

`git diff HEAD -- f` prints a diff, so the advice's condition holds and the agent saves that diff. But the diff records only the index's deletion of `f`, not the text of the working copy: once `f` is out of the index it is an untracked file, and no `git diff` command shows an untracked file's contents. The `git checkout` then overwrites the working copy. "uncommitted work" is gone, and the saved diff holds nothing to put it back. Open pull request [4915](https://github.com/nedsnodes/nedsnodes/pull/4915) changes the advice to save both `git diff --cached` and `git diff` instead; it neither causes this defect nor fixes it, because `git diff -- f` prints nothing in the case above, so both saved diffs miss the working copy too.

## Why it matters

The check runs from `scripts/git-client-side-hooks/pre-push`, so the agent reads the advice while its checkout may hold uncommitted work. In the case above, an agent that follows the advice word for word loses that work, and nothing tells it the work is lost. The advice was changed in pull request [4871](https://github.com/nedsnodes/nedsnodes/pull/4871) precisely to keep a file's uncommitted changes, and in this case it does not.

## What to do

cold-read-research, the Mac agent-seat that wrote pull requests 4871 and 4915, opens a pull request that keeps the working copy in this case; it may be the follow-up pull request to 4915 or a pull request of its own against main. The root cause is that the advice saves only diffs, and a diff cannot hold the contents of a working copy that is not in the index. Fix that root cause. What must survive is the working copy's text; the index's state needs no saving, because the branch's commit and the base still hold every committed version of the file. Two ways, of which the author chooses: have the advice tell the agent to copy the file itself to a place outside the checkout whenever the file exists on disk; or, better, since saving needs no judgment, have the check, or a small program its advice names, make that copy itself, check that the copy holds the working copy's bytes, run the `git checkout`, and print where the copy is, failing with a message if the copy does not match, so that only putting the changes back on top is left to the agent. The pull request adds a test to `scripts/branch-reverts-a-file-to-an-older-main-version-check-test.py` that builds the case above, runs the save and checkout commands the check itself prints or runs, rather than a copy of them typed into the test, and checks that the working copy's text "uncommitted work" can still be recovered afterwards.
