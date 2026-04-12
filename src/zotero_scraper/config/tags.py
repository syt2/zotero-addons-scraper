"""Addon tag taxonomy shared by docs, validation, and AI review."""

from typing import Final

ADDON_TAGS: Final[dict[str, str]] = {
    "ai": "AI-powered features such as summarization, chat, or translation via LLMs.",
    "metadata": (
        "Metadata retrieval, citation counts, impact factor, formatting, "
        "or library enrichment."
    ),
    "reader": "PDF reading experience, annotation, and highlighting workflows.",
    "notes": "Note-taking, markdown export, and knowledge management workflows.",
    "attachment": "File management, attachment organization, OCR, and exports.",
    "interface": "UI enhancements, themes, columns, and layout customizations.",
    "integration": "Integration with external services such as Notion or Obsidian.",
    "utility": "General Zotero tools such as automation and plugin management.",
}

VALID_ADDON_TAGS: Final[tuple[str, ...]] = tuple(ADDON_TAGS.keys())
MAX_ADDON_TAGS: Final[int] = 3


def normalize_tags(tags: list[str]) -> list[str]:
    """Return tags in canonical taxonomy order without duplicates."""
    tag_set = set(tags)
    return [tag for tag in VALID_ADDON_TAGS if tag in tag_set]


def format_tag_catalog() -> str:
    """Render the tag taxonomy as prompt-friendly text."""
    return "\n".join(
        f"- {tag}: {description}" for tag, description in ADDON_TAGS.items()
    )
