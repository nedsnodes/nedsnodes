---
issue: "[Fix-round brief rerun loses an answer saved while it rewrites the answers file](https://github.com/nedsnodes/nedsnodes/issues/4496)"
---

# Fix-round brief rerun loses an answer saved while it rewrites the answers file

## Reproduction

The program `scripts/pull-request-fix-round-author-brief-from-blocking-findings-and-one-commit-every-finding-answered-check.py` writes an answers file, `fix-round-answers-pull-request-<number>.md`, in which a fix-round's author answers each review finding. Each run of the brief rewrites that file with one empty numbered line per finding.

On main at commit dc70497da1d8, `answers_file_with_one_line_per_finding_write`, at line 833, does this with `path.write_text` at line 837. It keeps nothing, so any answer already in the file is lost, with no copy and no warning.

The open pull request [Fix-round brief copies non-blank answers before writing the answers file](https://github.com/nedsnodes/nedsnodes/pull/4468) fixes the ordinary rerun: it reads the file, copies non-blank text, then replaces the file with `os.replace`. An answer saved after that read and before `os.replace` is still lost. The pull request's review reproduced this at its head, 18fee9f0ee2d, by injecting a save just before `os.replace`. The saved answer was in neither the file nor a copy, whether the file had held placeholders or text.

The reproduction and its counts are in `nedlern@ned-box:/home/nedlern/nedsnodes-logs/seats/merge-lane-2/merge-helpers/claude-reviews/pr4468-18fee9f0ee2d3940c9bf3101fa0b3f8883fad743/codex-findings-answer.txt`, under finding 1.

## How likely it is

No occurrence is known. The time between the read and the replace was about 0.4 milliseconds, the median of 20 runs. Of 436 brief runs in the ned-box and Mac transcripts, none came within 10 seconds of another agent's write to an answers file, and none started within 120 seconds after one.

## How this differs from the move-finish step

[Fix-round move-finish step replaces an answers file written while the move is pushing](https://github.com/nedsnodes/nedsnodes/issues/4464) covers `shutil.move` in `--move-change-to-own-pull-request-finish`. This GitHub issue covers the brief's own rewrite, a different step with a different fix.

## Options

1. Change the rewrite so that it copies the version it actually replaces, and exits nonzero, leaving the file as it is, when it cannot.
2. Do nothing, because the case has not happened, and close this GitHub issue as not planned.

## Next action

The agent-seat reboot-test wrote this code, in [Fix-round brief prints the .walk-approved path, reads a stopped round and writes the answers file](https://github.com/nedsnodes/nedsnodes/pull/3933), and wrote the open pull request named above, so it decides this GitHub issue. If that pull request merges, take option 2 unless a transcript by then shows an answer lost this way, because CLAUDE.md allows a guard only for a failure that has happened or is foreseeable within 30 days. If it closes without merging, the ordinary rerun still loses answers on main, so fix that loss first, as option 1 does.

## Outcome

Closed as not planned, by option 2. [Fix-round brief copies non-blank answers before writing the answers file](https://github.com/nedsnodes/nedsnodes/pull/4468) merged on 2026-11-24, so the ordinary rerun no longer loses answers, and no transcript shows an answer lost between the brief's read and its `os.replace`. The search behind that claim was `scripts/log-store-past-discussions-regex-search-newest-first.py --since 2026-11-20 --kind session-dialogs 'answer[s]? (was|were) lost|lost (an|my|the) answer|answers file.{0,40}(lost|overwrit|wiped|empt)'`, on ned-box: none of its 12 hits reports such a loss. The open pull request [Fix-round brief keys each answer by its finding's comment ID and puts it back on a rerun](https://github.com/nedsnodes/nedsnodes/pull/4531) does not change this: keying answers by comment ID leaves the window between the read and `os.replace` as it is. If a transcript later shows an answer lost this way, reopen this GitHub issue and take option 1.
