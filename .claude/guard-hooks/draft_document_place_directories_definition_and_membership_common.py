"""The draft places of docs/nedsnodes-wiki/nedsnodes-file-naming-and-location-standards.md.

The instruction-file guard skips its reusable-prompt check there and nothing else, so a file its
separate protected-file rule covers keeps that rule's answer, and the log audit test lets a `-draft` or `-candidate` log be tracked by git there; both read this one
definition, so the two cannot drift apart."""

DRAFT_DOCUMENT_PLACE_DIRECTORY_NAMES = ("queue",)
DRAFT_DOCUMENT_PLACE_DIRECTORY_PREFIXES = (("docs", "drafts"),)


def directory_is_a_draft_document_place(directory_parts) -> bool:
    """Return True when `directory_parts`, the directories below the checkout root, are in a draft place."""
    directory_parts = tuple(directory_parts)
    if any(part in DRAFT_DOCUMENT_PLACE_DIRECTORY_NAMES for part in directory_parts):
        return True
    return any(directory_parts[:len(prefix)] == prefix for prefix in DRAFT_DOCUMENT_PLACE_DIRECTORY_PREFIXES)
