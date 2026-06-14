"""Unit tests for addon tag review."""

from pathlib import Path

from zotero_scraper.tag_review import (
    AddonConfigEntry,
    AddonTagReviewer,
    _parse_json_object,
)


def write_addon_file(path: Path, content: str) -> Path:
    """Write addon config content to a test file."""
    path.write_text(content, encoding="utf-8")
    return path


def test_addon_config_entry_loads_empty_file(temp_dir):
    """Empty addon entries should load as an empty config object."""
    path = write_addon_file(temp_dir / "owner@repo", "")

    entry = AddonConfigEntry.load(path)

    assert entry.repo == "owner/repo"
    assert entry.tags == []


def test_review_allows_missing_tags(temp_dir):
    """Empty addon files should pass when tags are omitted."""
    path = write_addon_file(temp_dir / "owner@repo", "")
    reviewer = AddonTagReviewer()

    result = reviewer.review_file(path)

    assert result.status == "ok"
    assert result.current_tags == []


def test_review_rejects_unknown_tags(temp_dir):
    """Unknown taxonomy values should fail validation."""
    path = write_addon_file(temp_dir / "owner@repo", '{"tags": ["unknown"]}\n')
    reviewer = AddonTagReviewer()

    result = reviewer.review_file(path)

    assert result.status == "failed"
    assert "Unknown tags" in result.messages[0]


def test_review_rejects_non_canonical_order(temp_dir):
    """Tags should follow the configured canonical order."""
    path = write_addon_file(
        temp_dir / "owner@repo",
        '{"tags": ["reader", "ai"]}\n',
    )
    reviewer = AddonTagReviewer()

    result = reviewer.review_file(path)

    assert result.status == "failed"
    assert "canonical order" in result.messages[0]


def test_review_accepts_valid_tags(temp_dir):
    """A valid addon config should pass validation."""
    path = write_addon_file(
        temp_dir / "owner@repo",
        '{"tags": ["ai", "notes"], "recommended": true}\n',
    )
    reviewer = AddonTagReviewer()

    result = reviewer.review_file(path)

    assert result.status == "ok"
    assert result.current_tags == ["ai", "notes"]


def test_review_rejects_too_many_tags(temp_dir):
    """Addon entries should use at most two tags."""
    path = write_addon_file(
        temp_dir / "owner@repo",
        '{"tags": ["ai", "notes", "utility"]}\n',
    )
    reviewer = AddonTagReviewer()

    result = reviewer.review_file(path)

    assert result.status == "failed"
    assert "At most 2 tags" in result.messages[0]


def test_parse_json_object_allows_fenced_model_output():
    """Model JSON output may be wrapped in a markdown fence."""
    parsed = _parse_json_object(
        '```json\n{"tags": ["ai"], "confidence": "high", "reason": "LLM"}\n```'
    )

    assert parsed["tags"] == ["ai"]
