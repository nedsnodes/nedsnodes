---
issue: "[The handoff stop-typing notice hook marks the notice shown before writing it to stdout, so a failed write hides it for good](https://github.com/nedsnodes/nedsnodes/issues/5069)"
---

# The handoff stop-typing notice hook marks the notice shown before writing it to stdout, so a failed write hides it for good

## Reproduction

The Codex review cell reproduced this while reviewing PR [Handoff stop-typing notice: print ASCII-safe JSON, test a failed record write](https://github.com/nedsnodes/nedsnodes/pull/4321), as its finding 6171fd86ffbd, recorded in `nedlern@ned-box:/home/nedlern/nedsnodes-logs/seats/merge-lane-2/merge-helpers/cx/pr4321-9e204864/codex-code-review-report.md`. A `python3 -` test harness called the hook's `main()` with its stdout pipe already closed, then called it again with an open stdout. It printed `exit=1, failure=BrokenPipeError, record='10\n', next exit=0, next stdout=''`. That invocation gave the same result at main's commit 9e204864f451 and at that pull request's nn-head-commit fb2fc7d0587f, so main has the defect, and the pull request neither causes nor fixes it.

## What is wrong

`nn-systems/handoff/handoff-asked-stop-typing-user-notice-user-prompt-submit-hook.py` is the UserPromptSubmit hook that shows the user a "handing off, stop typing" notice once for each handoff-asked marker file. In `main()` on main, it writes the shown record, the file `<marker file>-user-notice-shown` that holds the marker file's modification time, before it prints the notice's JSON to stdout:

```
shown_record.write_text(marker_modified + "\n", encoding="utf-8")
print(json.dumps({"systemMessage": notice}, ensure_ascii=False))
```

When the print fails, for example with BrokenPipeError on a closed stdout or with UnicodeEncodeError on an ASCII-only stdout, the hook reports the failure and exits 1. But the shown record is already written, so at the next prompt the hook finds the record, takes the notice as already shown and exits 0 with nothing on stdout. The user never sees the notice for that handoff: the step that failed, getting the notice to Claude Code, leaves a record saying it succeeded.

## What to do

Write the shown record only after the JSON has been printed and stdout flushed without error. Then a failed write to stdout leaves no shown record, and the hook tries the notice again at the next prompt. When the notice reached stdout but the shown record then cannot be written, the hook's failure message must say that the record was not written, not that the user was not shown the notice, because he was. Change the module docstring's sentence that says the hook writes the record before printing. In `nn-systems/handoff/tests/handoff-asked-stop-typing-user-notice-user-prompt-submit-hook-test.py`, add a test that closes the hook's stdout, checks that the run exits 1 and writes no shown record, and checks that the next run prints the notice.

## Owner

helper2 wrote this hook and owns this fix. GHI [The stop-typing notice names the agent-seat whose shell started a child agent-session, as if the child were that agent-seat](https://github.com/nedsnodes/nedsnodes/issues/4841), owned by ned-box-helper, also changes this hook, so whichever fix merges second merges main in first.
