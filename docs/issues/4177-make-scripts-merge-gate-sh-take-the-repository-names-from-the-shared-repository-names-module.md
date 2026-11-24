---
issue: "[Make `scripts/merge-gate.sh` take the repository's names from the shared repository-names module](https://github.com/nedsnodes/nedsnodes/issues/4177)"
---

# Make `scripts/merge-gate.sh` take the repository's names from the shared repository-names module

`scripts/merge-gate.sh` sets `REPO=nedsnodes/nedsnodes` and `OLD_REPOSITORY=nedschorus/nedschorus` itself. These duplicate `REPOSITORY` and `OLD_REPOSITORY` in `nn-systems/general-tools/github_repository_name_and_name_before_project_rename_common.py`, the module every reader of GitHub links is meant to take the names from. The gate uses `REPO` in every `gh` call it makes, and uses both names to decide whether a `#follow_up` link names this repository. A bash script cannot import the Python module, so the copy stayed when PR [md-drift-lint and the bare-number citation hook read the repository's names from the shared module](https://github.com/nedsnodes/nedsnodes/pull/4149) removed the other Python copies outside it; the one left in `scripts/project-rename-machine-state-move-hack.py` goes when that program is retired.

Why it matters: if either name changes in the module, the gate keeps the old value, and no test or lint notices the difference.

Next action: replace the two assignments in `scripts/merge-gate.sh` with one `python3` call at start-up that imports the module and prints `REPOSITORY` and `OLD_REPOSITORY` on one line, separated by a space, which the gate reads into `REPO` and `OLD_REPOSITORY`. When the call exits nonzero, or does not print two names, the gate stops through its existing `cannot` function, so it exits 2 (could not run), with a message that names the module. Add a test that runs the gate's `#follow_up` link check on a link under each name and shows both count as this repository.
