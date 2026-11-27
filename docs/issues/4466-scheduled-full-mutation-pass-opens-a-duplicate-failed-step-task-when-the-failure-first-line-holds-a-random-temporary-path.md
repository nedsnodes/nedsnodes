---
issue: "[Scheduled full mutation pass opens a duplicate failed-step task when the failure's first line holds a random temporary path](https://github.com/nedsnodes/nedsnodes/issues/4466)"
---

# Scheduled full mutation pass opens a duplicate failed-step task when the failure's first line holds a random temporary path

## Reproduction

This run used origin/main at `663c805a3cab39d9ff1d52f28c58c7a3bc1b390d`, in a detached worktree. The program under test is `scripts/scheduled-full-mutation-pass-of-merged-pull-requests-and-survivor-tasks-open.py`. The script below builds that program's own test fixture, so every log, task list and state file is in a scratch directory. For each merge it runs the program twice with a fake mutation program that exits 0 and writes no JSON result. To run it again, save the script printed below as `scheduled-full-mutation-pass-duplicate-failed-step-task-when-failure-line-holds-temporary-path-reproduction.py` in a scratch directory, make a detached worktree of the commit above, and put that worktree's path in place of `<worktree>`.

```
env -u TMP -u TEMP TMPDIR=/tmp/q9 PYTHONDONTWRITEBYTECODE=1 python3 -B scheduled-full-mutation-pass-duplicate-failed-step-task-when-failure-line-holds-temporary-path-reproduction.py <worktree>/scripts/scheduled-full-mutation-pass-of-merged-pull-requests-and-survivor-tasks-open-test.py
```

`/tmp/q9` was a symbolic link to a scratch directory, removed afterwards, so that the temporary path stayed short while its files stayed in scratch. Its name is 3 characters longer than `/tmp`, so the threshold in this output is 36 characters where it is 39 with `TMPDIR=/tmp`.

```
TMPDIR=/tmp/q9 random part starts at character 165 + subject length; kept: 200; subjects of 36 or more keep none of it
subject_len=10 exits=[4, 4] tasks=2
   subject tail: 'survivor-tasks-open-6pn4wzpx/6caef6a7f2e4159a9'
   subject tail: 'survivor-tasks-open-ujidwdlm/6caef6a7f2e4159a9'
subject_len=34 exits=[4, 4] tasks=2
   subject tail: 'erged-pull-requests-and-survivor-tasks-open-wv'
   subject tail: 'erged-pull-requests-and-survivor-tasks-open-ww'
subject_len=36 exits=[4, 4] tasks=1
   subject tail: '-merged-pull-requests-and-survivor-tasks-open-'
subject_len=101 exits=[4, 4] tasks=1
   subject tail: 'xited 0 but its JSON file /tmp/q9/scheduled-fu'
```

The script, `scheduled-full-mutation-pass-duplicate-failed-step-task-when-failure-line-holds-temporary-path-reproduction.py`:

```python
import importlib.util, sys, tempfile
from pathlib import Path
spec = importlib.util.spec_from_file_location("full_pass_test", Path(sys.argv[1]))
t = importlib.util.module_from_spec(spec); spec.loader.exec_module(t)
tmp = tempfile.gettempdir()
fixed = len(f"merge {'0'*12} (): the mutation testing program exited 0 but its JSON file {tmp}/{t.job.PROGRAM}-")
threshold = 200 - fixed
print(f"TMPDIR={tmp} random part starts at character {fixed + 1} + subject length; kept: 200; subjects of {threshold} or more keep none of it")
for length in (10, threshold - 2, threshold, 101):
    with tempfile.TemporaryDirectory() as scratch:
        f = t.Fixture(scratch); f.seat(t.job.JOB_FAILURE_TASK_AGENT_SEAT)
        f.set_last(t.git(f.work, "rev-parse", "HEAD"))
        (f.work / "scripts").mkdir(); (f.work / "scripts/thing.py").write_text("VALUE = 1\n")
        t.git(f.work, "add", "-A"); t.git(f.work, "commit", "-q", "-m", "s" * length); t.git(f.work, "push", "-q", "origin", "HEAD:main")
        merge = t.git(f.work, "rev-parse", "HEAD")
        exits = [f.run({merge: {"exit": 0}}).returncode for _ in range(2)]
        tasks = t.job_failure_tasks(f)
        print(f"subject_len={length} exits={exits} tasks={len(tasks)}")
        for task in tasks: print("   subject tail:", repr(task["subject"][-46:]))
```

## What is wrong

The program finds the open task for a failed step by the task's subject, which is the fixed text `Nightly full mutation pass stopped at a failed step: ` followed by the first 200 characters of the failure's first line. When the mutation program exits without writing its JSON result, that line names the JSON file, whose path holds the random part of a temporary directory's name. When the merge's commit subject is short enough for the random part to fall inside the 200 characters, each run's subject differs, so each failing night opens another task instead of matching the open one. The reproduction covers the missing JSON result only. The subject is cut the same way from all 13 `raise StepFailed` messages and from the text of any exception the program does not handle, so any of them that holds text varying between runs would do the same; this GHI-MD has not checked which do.

## Harm and how likely it is

The harm is small and repairable. Each extra task holds its own run's correct diagnosis and record, and every run exits 4, so no step reports success wrongly.

With `TMPDIR=/tmp`, only a merge whose commit subject is under 39 characters triggers the defect. The last 300 first-parent commit subjects on main, at `663c805a3`, run from 76 to 225 characters with a median of 127, so none would trigger it. A longer `TMPDIR` lowers the threshold. The running nightly job (process 1101946 on ned-box, started by cron on 2026-11-22 at 00:30) has no `TMPDIR`, `TEMP` or `TMP` in its environment, and its temporary directory is under `/tmp`, so the threshold on the live job is 39. The live task list `~/.claude/tasks/nedsnodes-fleet-restart-at-login-tasks/` on ned-box holds no task whose text contains `Nightly full mutation pass stopped at a failed step` (searched with `grep -l` on its `*.json` files on 2026-11-23), so there are no duplicates to clear up.

## Direction of the fix

Key the task on the failed step and the merge, and keep temporary paths in the description. One way is for `StepFailed` to take a required fixed step name and, when the step concerns a merge, that merge, with the subject built from those two fields so that no message text reaches it; a step that concerns no merge, such as reading the state file, is keyed on its step name alone. The assertions on failed-step subjects in `scripts/scheduled-full-mutation-pass-of-merged-pull-requests-and-survivor-tasks-open-test.py` change with it.

## Owner and next action

The owning agent-seat is most likely fleet-restart-at-login. fleet-restart-at-login is the git author of commit `1ba1ba640`, from [pull request 2774](https://github.com/nedsnodes/nedsnodes/pull/2774), which wrote the subject line, and of 56 commits to the program; the program also sends its job failure tasks to that agent-seat. The pull request's GitHub account, `ubuntu-claude`, is shared by several agent-seats, and its branch no longer has a worktree, so the git author is the evidence for this.

Next action: fleet-restart-at-login opens a pull request that gives the failed-step task a subject with no temporary path, with a test that runs a failing step twice for one merge and asserts one task with the exact expected subject. The test must assert the exact subject because the threshold moves with `TMPDIR`: under the test sandbox's `TMPDIR`, `/tmp/nn-test-sandbox-tmpdir-symlink`, it is 8 characters, so a test that only counts tasks would pass on the unfixed code with the fixture's usual 23-character subject.
