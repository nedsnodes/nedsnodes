# Rename every file whose name ends in -test, -common or -hack to end in .test, .common or .hack

## What is wrong

The definition of a suffix that the user approved on 2026-11-25, in item 24 of 62 of ned-box-helper's approval-walk ned-box-helper-open-items-approval-walk-2026-11-22 (its walk-minutes, line 195, are `nedlern@ned-box:/home/nedlern/nedsnodes-logs/walk/ned-box-helper-open-items-approval-walk-2026-11-22-minutes.md`), makes the dot the rule for every suffix, as in `docs/design-to-main/design-to-main-state-machine.system.design.md`; open PR [Rename the 20 reusable-prompt files to .prompt.md and .instructions.md endings](https://github.com/nedsnodes/nedsnodes/pull/5222) writes it into the naming page, `docs/nedsnodes-wiki/nedsnodes-file-naming-and-location-standards.md`. The definition kept one exception: "a program keeps the hyphen of `-test` and `-hack`, as in `scripts/dangling-path-citation-check-test.py`", and the `-common` modules kept the hyphen too. That keeps two ways of writing a suffix alive, agents keep copying the hyphen into new names, and a hyphen suffix is hard to glob: `*-test.py` finds every nn-test-suite but also any program whose name happens to end in a word such as `pre-test.py`, while `*.test.py` finds the nn-test-suites and nothing else.

On 2026-11-27 at 06:52Z the user answered "A" to item 11 of 89 of approval-walk agent-instructions-editor-backlog-decisions-approval-walk-2026-11-26, a user-ruling that drops the exception: `-test`, `-common` and `-hack` take a dot like every other suffix, and this GHI renames the files. His reason, in his words: "Why not use dot for python or code types too? The idea is to make them easier to glob". The item is under "## Item 11 of 89" in `nedlern@ned-box:/home/nedlern/agents/agent-instructions-editor/docs/walk/agent-instructions-editor-backlog-decisions-approval-walk-2026-11-26.md`, and his answer is line 66 of its walk-minutes, `nedlern@ned-box:/home/nedlern/agents/agent-instructions-editor/docs/walk/agent-instructions-editor-backlog-decisions-approval-walk-2026-11-26-minutes.md`. The same user-ruling says that until this rename lands, existing and new files keep the hyphen, so the test runner still finds them.

Nothing in the code needs the hyphen. A program loads a `-common` module by its path, with `importlib.util.spec_from_file_location`, which accepts a file name holding a dot as well as one holding a hyphen; a plain `import` can load neither.

## What to rename

On main at commit aef6d2ef1, `git ls-files` lists 349 files to rename:

- 283 files ending `-test.py` and 1 ending `-test.sh`, each an nn-test-suite;
- 55 files ending `-common.py`;
- 10 files ending `-hack.py`.

Each suffix becomes its dot form before the extension, and a name with two suffixes changes both: `scripts/dangling-path-citation-check-test.py` becomes `scripts/dangling-path-citation-check.test.py`, `nn-systems/cold-read/tests/cold-read-cell-common-test.py` becomes `nn-systems/cold-read/tests/cold-read-cell.common.test.py`, and `scripts/seat-task-list-read-hack-test.py` becomes `scripts/seat-task-list-read.hack.test.py`.

Only a suffix at the end of a program's stem changes. Leave alone a word inside a name, such as the `common` in `nn-systems/general-tools/tests/claude-code-headless-run-every-launch-uses-common-command-line-prefix-test.py`, whose `-test` alone changes, and leave Markdown files alone, such as the GHI-MD `docs/issues/2990-cold-read-reviewer-sandboxes-deny-a-fixed-list-of-credential-directories-instead-of-scanning-the-home-directory-for-credential-files-in-nc-systems-cold-read-cold-read-cell-common.md`. One module, `scripts/merge-lane-pull-request-helpers-common-options-paths-and-token.py`, has `common` in the middle of its name, yet 14 tracked programs name it and it is a module several programs import, which is what the glossary's **-common** means; rename it to `scripts/merge-lane-pull-request-helpers-options-paths-and-token.common.py` with the others.

The list comes from `git ls-files | grep -E -- '-(test|common|hack)\.(py|sh)$'`; rerun it on main when the work starts, because the count grows.

The new names follow a fixed rule, so make the renames and the replacements of old names in other files with a one-off program, not by hand. It builds the map from old path to new path by turning each trailing `-test`, `-common` or `-hack` of the stem into its dot form, runs `git mv` for each pair, then replaces each old stem with its new one across the tracked files, longest stem first, because a stem such as `cold-read-cell-common` is the start of another, `cold-read-cell-common-test`. It prints each file it left alone, so the agent checks only those.

## What else must change in the same pull request

Each of these breaks if the files are renamed without it:

- `scripts/run-all-test-suites.py`: `TEST_SUITE_PATHSPEC = "*-test.py"` and `SHELL_TEST_SUITE_PATHSPEC = "*-test.sh"` become `*.test.py` and `*.test.sh`, and its docstring and `--help` text change with them.
- Every other program that recognises a file by its suffix. A `git grep -nE` of main at aef6d2ef1 for `-test`, `-common` and `-hack` in string literals, globs and `endswith` calls, in `*.py`, `*.sh` and `*.json` files other than nn-test-suites, found these: `scripts/pull-request-review-plan.py` (lines 918 to 928, which pair a program with its `-test.py`), `scripts/mutation-testing-changed-lines-quick-or-full-pass-survivors.py` (lines 529 and 537), `scripts/dangling-path-citation-check.py` (`PROJECT_TEST_FILE_STEM_ENDING = "-test"`), `scripts/handoff-context-threshold-hook.py` (line 254, which recognises a test run by `-test\.py`), and `nn-systems/general-tools/python-source-tool-message-to-agent-string-collector-common.py` (line 120). That search can miss a pattern built another way, so search again and run the whole test runner before opening the pull request. 13 nn-test-suites also glob or match these suffixes, among them `scripts/run-all-test-suites-test.py`, `scripts/mutation-testing-changed-lines-quick-or-full-pass-survivors-test.py` and `scripts/no-sandbox-test-suites-run-on-main-in-a-quiet-gap-test.py`.
- Every program that names a renamed file by its path, such as each `spec_from_file_location` call that loads a `-common` module. In all, 638 tracked files name at least one of the 349 file stems, counted with `git grep -lF` over the stems.
- The two hook commands in `.claude/settings.json` that run `scripts/markdown-edit-hard-wrapped-paragraph-reminder-hook-hack.py` and `scripts/style-guide-word-checker-markdown-edit-hook-hack.py`, and the scheduled job in `nn-systems/general-tools/scheduled-jobs-on-each-machine.json` that runs `scripts/log-store-session-dialogs-refresh-hack.py`. ned-box's installed crontab names that job's old path, which the last step under "What to do next" corrects.
- The project glossary, `docs/nedsnodes-wiki/nedsnodes-glossary.md`: its entries **-common**, **-hack** and **nn-test-suite** name the hyphen forms. Change them, and every other glossary entry or page that cites a renamed file or a hyphen suffix, among them the naming page's sentences on `-hack` and every page under `docs/nedsnodes-wiki/` that cites a `-test.py`, `-common.py` or `-hack.py` file.
- The naming page's exception: in this same pull request, remove the sentence that says a program keeps the hyphen. PR 5222 writes that sentence into the page, so this pull request waits until PR 5222 has merged; until then the sentence is true and nothing else changes it.
- A new nn-test-suite that fails when any tracked file's name ends in `-test`, `-common` or `-hack` before `.py` or `.sh`. After the rename the test runner finds only `*.test.py` and `*.test.sh`, so a suite an agent later names `foo-test.py` would never run and no run would show it; this suite makes that name fail instead.

Some of the renamed files, such as the `-common.py` modules under `.claude/guard-hooks/`, and many of the files that name them are files the instruction-file guard protects. Rename a guarded-file the way PR 5222 renamed its own: create the new path with the Write tool, byte-identical to the old file, then remove the old path with `git rm`. The user approved that method, and PR 5222's changes to guarded-files, for PR 5222 only, in item 2 of the same approval-walk. Before starting, ask him in an approval-walk to approve this pull request's renames and its changes to guarded-files, and write his approving words into `.walk-approved` before each Edit or Write call on a guarded-file, as the instruction-file guard requires.

## When to do it

Renaming 349 files touches almost every open pull request, so do it in a quiet window, when few pull requests are open, as PR 5222's rename to `.prompt.md` was. Put the renames alone in the first commit, so git records them as renames and a reviewer can check them apart from the edits; `git diff --name-status -M100% <first commit>^ <first commit>` must then show every entry as `R100`, each pair matching the program's map.

## Related issues

- GHI [A program that rewrites each Markdown citation of a renamed file to the file's new path, taking the new path from git's rename history](https://github.com/nedsnodes/nedsnodes/issues/3054), open, designs the program that would rewrite the Markdown citations; if it has landed, use it rather than a one-off rewriter.
- GHI [Genre-suffix naming for non-reviewable documents (-log, -report, -capture), and mechanical exclusion from the review instruments](https://github.com/nedsnodes/nedsnodes/issues/152), open, rules the hyphen genre suffixes of documents; this rename does not change them.

## What to do next

On main, rerun the file list above, then open one pull request that renames every listed file and makes every change under "What else must change in the same pull request", with `scripts/run-all-test-suites.py` passing on its head, and with `scripts/dangling-path-citation-check.py --only-citations-of-removed-paths` reporting no citation of a renamed path. Ask merge-lane-2 for a quiet window before marking it ready. After it merges, run `nn-systems/general-tools/install-scheduled-jobs-on-this-machine.py --check` on ned-box and on the Mac, and `--install` on a machine whose check reports a difference.
