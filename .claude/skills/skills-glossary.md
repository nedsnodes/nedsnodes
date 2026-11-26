# Skills glossary

This page defines the system-terms of this project's skills: the terms they alone use. Every project-term is defined in the project glossary, `docs/nedsnodes-wiki/nedsnodes-glossary.md`, and this page uses it as defined there.

- **cold-read-reviewer-test-case** — a document's first version, its corrected version, and the weighted list of the defects between them, kept frozen in `cold-read-reviewer-test-cases/` to score cold-read-cells.
- **key-term** — in a cold-read-target, a term that is a project-term or a system-term, or should be one.
- **sanity-check-adversarial-prompt** — one stance the /sanity-check instrument takes on a document, run as its own prompt: the cut-adversarial-prompt (what should be deleted), the mechanization-adversarial-prompt (which English instruction should be code), the fresh-eyes-adversarial-prompt (an independent design built from the problem alone).
- **sanity-check-cell** — one fresh-agent running one sanity-check-adversarial-prompt with `claude` or with `codex`; a run is six, the three adversarial prompts with `claude` and the three with `codex`.
- **sanity-check-record** — the directory one /sanity-check run leaves behind, holding its reports; kept as a log.
- **sanity-check-request** — the file the requesting agent writes for the fresh-eyes-adversarial-prompt: a problem statement plus off-limits and read-first lists.
- **walk-document** — the file `docs/walk/<name>.md`, the text of an approval-walk as presented to the user.
