"""Tests for selecting releases from the persistent release cache."""

from zotero_scraper.cache.release_cache import CachedRelease, RepoCache


def make_release(tag: str, version: str, published_at: str | None) -> CachedRelease:
    """Create a compatible cached release for selection tests."""
    return CachedRelease(
        tag=tag,
        published_at=published_at,
        xpi_asset_id=1,
        xpi_name="addon.xpi",
        xpi_download_url="https://example.com/addon.xpi",
        addon_id="addon@example.com",
        addon_version=version,
        min_zotero_version="7.0",
        max_zotero_version="10.9.9",
    )


def test_best_release_prefers_newer_published_at_for_same_addon_version():
    """Duplicate add-on versions use publication time instead of cache order."""
    cache = RepoCache(
        checked_releases=[
            make_release("deleted-tag", "0.2", "2026-08-29T05:45:14Z"),
            make_release("v0.2", "0.2", "2026-08-30T16:34:41Z"),
            make_release("v0.1", "0.1", "2026-08-18T11:08:35Z"),
        ]
    )

    assert cache.get_best_release_for_zotero("10").tag == "v0.2"


def test_best_release_treats_missing_published_at_as_oldest():
    """Draft-like cache entries without a publication time cannot break selection."""
    cache = RepoCache(
        checked_releases=[
            make_release("draft", "0.2", None),
            make_release("published", "0.2", "2026-08-30T16:34:41Z"),
        ]
    )

    assert cache.get_best_release_for_zotero("10").tag == "published"
