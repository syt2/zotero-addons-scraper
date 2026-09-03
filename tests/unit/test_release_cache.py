"""Tests for selecting and pruning releases from the persistent cache."""

import json
from unittest.mock import Mock, call, patch

import pytest

from zotero_scraper.cache.release_cache import CachedRelease, ReleaseCache, RepoCache
from zotero_scraper.clients.github import GitHubClient
from zotero_scraper.config.constants import GitHubAPI
from zotero_scraper.config.settings import CacheConfig, GitHubConfig, ScraperConfig
from zotero_scraper.services.cache_builder import ReleaseCacheBuilder
from zotero_scraper.services.cache_scraper import CacheScraper


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


def make_github_release(tag: str, asset_id: int) -> dict:
    """Create the GitHub release fields used for XPI asset comparisons."""
    return {
        "tag_name": tag,
        "published_at": "2026-09-03T04:37:42Z",
        "assets": [
            {
                "id": asset_id,
                "name": "addon.xpi",
                "browser_download_url": "https://example.com/addon.xpi",
                "content_type": "application/x-xpinstall",
                "updated_at": "2026-09-03T04:37:42Z",
            }
        ],
    }


def make_config(temp_dir) -> ScraperConfig:
    """Create a scraper config whose writable paths stay inside the test directory."""
    return ScraperConfig(
        cache=CacheConfig(
            cache_dir=temp_dir / "xpi_cache",
            runtime_xpi_dir=temp_dir / "runtime_xpi",
        )
    )


def make_builder(
    temp_dir, cache: ReleaseCache, releases: list[dict] | None
) -> ReleaseCacheBuilder:
    """Create a builder focused on release-list cleanup rather than XPI parsing."""
    builder = ReleaseCacheBuilder(make_config(temp_dir), cache)
    builder.github = Mock()
    builder.github.get_releases.return_value = releases
    builder._check_latest_release_update_url = Mock(return_value=False)
    cache.get_unchecked_tags = Mock(return_value=[])
    return builder


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


def test_builder_reprocesses_cached_tag_when_xpi_asset_changes(temp_dir):
    """Replacing an XPI under the same tag refreshes the cached release."""
    cache = ReleaseCache(temp_dir / "release_cache")
    cache.add_release(
        "owner/repo", make_release("v0.2", "0.2", "2026-08-30T16:34:41Z")
    )
    releases = [make_github_release("v0.2", asset_id=2)]
    builder = make_builder(temp_dir, cache, releases)
    refreshed = make_release("v0.2", "0.2", "2026-09-03T04:37:42Z")
    refreshed.xpi_asset_id = 2
    builder._parse_release = Mock(return_value=refreshed)

    result = builder._process_repo("owner/repo")

    builder._parse_release.assert_called_once_with("owner/repo", releases[0])
    assert result["new_releases"] == 0
    assert result["refreshed_releases"] == 1
    cached = cache.get_repo_cache("owner/repo").get_release_by_tag("v0.2")
    assert cached is refreshed


def test_builder_skips_cached_tag_when_xpi_asset_is_unchanged(temp_dir):
    """An unchanged asset ID must not cause another XPI download and parse."""
    cache = ReleaseCache(temp_dir / "release_cache")
    cache.add_release(
        "owner/repo", make_release("v0.2", "0.2", "2026-08-30T16:34:41Z")
    )
    releases = [make_github_release("v0.2", asset_id=1)]
    builder = make_builder(temp_dir, cache, releases)
    builder._parse_release = Mock()

    result = builder._process_repo("owner/repo")

    builder._parse_release.assert_not_called()
    assert result["new_releases"] == 0
    assert result["refreshed_releases"] == 0


def test_builder_replaces_cached_tag_when_xpi_asset_is_removed(temp_dir):
    """Removing the selected XPI must not leave its stale cache entry active."""
    cache = ReleaseCache(temp_dir / "release_cache")
    cache.add_release(
        "owner/repo", make_release("v0.2", "0.2", "2026-08-30T16:34:41Z")
    )
    release = make_github_release("v0.2", asset_id=1)
    release["assets"] = []
    builder = make_builder(temp_dir, cache, [release])
    builder._parse_release = Mock(return_value=None)

    result = builder._process_repo("owner/repo")

    builder._parse_release.assert_called_once_with("owner/repo", release)
    assert result["new_releases"] == 0
    assert result["refreshed_releases"] == 1
    cached = cache.get_repo_cache("owner/repo").get_release_by_tag("v0.2")
    assert cached is not None
    assert cached.xpi_asset_id == 0
    assert cached.parse_success is False


@pytest.mark.parametrize("page_size", [2, 100])
def test_builder_checks_only_missing_tags_at_or_after_page_cutoff(
    temp_dir, page_size
):
    """Short and full pages use the same conservative cutoff and exact checks."""
    cutoff = "2026-08-29T00:00:00Z"
    releases = [
        {"tag_name": f"visible-{index}", "published_at": cutoff}
        for index in range(page_size)
    ]
    cache = ReleaseCache(temp_dir / "release_cache")
    for release in [
        make_release("older", "0.1", "2026-08-28T23:59:59Z"),
        make_release("at-cutoff", "0.2", cutoff),
        make_release("newer", "0.3", "2026-08-30T00:00:00Z"),
        make_release("visible-0", "0.4", cutoff),
    ]:
        cache.add_release("owner/repo", release)
    builder = make_builder(temp_dir, cache, releases)
    builder.github.release_exists.return_value = False

    builder._process_repo("owner/repo")

    assert builder.github.release_exists.call_args_list == [
        call("owner", "repo", "at-cutoff"),
        call("owner", "repo", "newer"),
    ]
    assert {
        release.tag for release in cache.get_repo_cache("owner/repo").checked_releases
    } == {"older", "visible-0"}


def test_builder_empty_page_checks_every_cached_tag_and_deletes_only_404(temp_dir):
    """An empty successful page is evidence to check all tags, not delete them."""
    cache = ReleaseCache(temp_dir / "release_cache")
    for tag in ["deleted", "exists", "unknown"]:
        cache.add_release(
            "owner/repo", make_release(tag, "0.2", "2026-08-30T00:00:00Z")
        )
    builder = make_builder(temp_dir, cache, [])
    results = {"deleted": False, "exists": True, "unknown": None}
    builder.github.release_exists.side_effect = (
        lambda owner, repo, tag: results[tag]
    )

    builder._process_repo("owner/repo")

    assert builder.github.release_exists.call_args_list == [
        call("owner", "repo", "deleted"),
        call("owner", "repo", "exists"),
        call("owner", "repo", "unknown"),
    ]
    assert {
        release.tag for release in cache.get_repo_cache("owner/repo").checked_releases
    } == {"exists", "unknown"}


def test_builder_preserves_cache_when_release_request_fails(temp_dir):
    """An unknown GitHub result must never be mistaken for an empty release list."""
    cache = ReleaseCache(temp_dir / "release_cache")
    cache.add_release(
        "owner/repo", make_release("keep", "0.2", "2026-08-30T00:00:00Z")
    )
    cache.set_observed_release_tags("owner/repo", {"stale-observation"})
    builder = make_builder(temp_dir, cache, None)

    builder._process_repo("owner/repo")

    assert [
        release.tag for release in cache.get_repo_cache("owner/repo").checked_releases
    ] == ["keep"]
    assert cache.get_observed_release_tags("owner/repo") is None
    builder.github.release_exists.assert_not_called()


def test_builder_skips_cleanup_without_a_string_publication_cutoff(temp_dir):
    """Malformed publication values cannot become an unsafe time boundary."""
    cache = ReleaseCache(temp_dir / "release_cache")
    cache.add_release(
        "owner/repo", make_release("keep", "0.2", "2026-08-30T00:00:00Z")
    )
    releases = [
        {"tag_name": "without-time", "published_at": None},
        {"tag_name": "numeric-time", "published_at": 123},
    ]
    builder = make_builder(temp_dir, cache, releases)

    builder._process_repo("owner/repo")

    builder.github.release_exists.assert_not_called()
    assert cache.get_repo_cache("owner/repo").get_release_by_tag("keep") is not None


def test_builder_ignores_non_string_times_when_a_valid_cutoff_exists(temp_dir):
    """A malformed time beside a valid one does not break candidate selection."""
    cache = ReleaseCache(temp_dir / "release_cache")
    cache.add_release(
        "owner/repo", make_release("deleted", "0.2", "2026-08-30T00:00:00Z")
    )
    releases = [
        {"tag_name": "valid", "published_at": "2026-08-29T00:00:00Z"},
        {"tag_name": "numeric-time", "published_at": 123},
    ]
    builder = make_builder(temp_dir, cache, releases)
    builder.github.release_exists.return_value = False

    builder._process_repo("owner/repo")

    builder.github.release_exists.assert_called_once_with("owner", "repo", "deleted")
    assert cache.get_repo_cache("owner/repo").checked_releases == []


def test_release_page_observation_is_transient(temp_dir):
    """Release-list evidence stays in memory and never enters published cache JSON."""
    cache_dir = temp_dir / "release_cache"
    cache = ReleaseCache(cache_dir)
    cache.add_release(
        "owner/repo", make_release("v0.2", "0.2", "2026-08-30T00:00:00Z")
    )
    cache.set_observed_release_tags("owner/repo", {"v0.2"})

    cache.save()

    data = json.loads((cache_dir / "owner#repo.json").read_text(encoding="utf-8"))
    assert "observed_release_tags" not in data
    assert cache.get_observed_release_tags("owner/repo") == {"v0.2"}


def test_save_failure_preserves_existing_cache_and_propagates(temp_dir):
    """A partial write cannot replace the last valid cache or look successful."""
    repo = "owner/repo"
    cache_dir = temp_dir / "release_cache"
    cache_file = cache_dir / "owner#repo.json"
    temp_file = cache_file.with_suffix(".json.tmp")
    cache = ReleaseCache(cache_dir)
    cache.add_release(
        repo, make_release("v0.1", "0.1", "2026-08-29T00:00:00Z")
    )
    cache.save()
    previous_contents = cache_file.read_text(encoding="utf-8")

    cache.add_release(
        repo, make_release("v0.2", "0.2", "2026-08-30T00:00:00Z")
    )

    def fail_after_partial_write(data, file, **kwargs):
        file.write("{")
        raise OSError("disk full")

    with patch(
        "zotero_scraper.cache.release_cache.json.dump",
        side_effect=fail_after_partial_write,
    ):
        with pytest.raises(OSError, match="disk full"):
            cache.save()

    assert cache_file.read_text(encoding="utf-8") == previous_contents
    assert not temp_file.exists()

    cache.save()
    reloaded = ReleaseCache(cache_dir).get_repo_cache(repo)
    assert {release.tag for release in reloaded.checked_releases} == {"v0.1", "v0.2"}


def test_selected_tag_absent_from_page_is_confirmed_before_output(temp_dir):
    """A selected deleted tag is removed so the next compatible release wins."""
    cache = ReleaseCache(temp_dir / "release_cache")
    cache.add_release(
        "owner/repo", make_release("deleted", "0.2", "2026-08-30T00:00:00Z")
    )
    cache.add_release("owner/repo", make_release("v0.1", "0.1", "2026-08-29T00:00:00Z"))
    cache.set_observed_release_tags("owner/repo", {"v0.1"})
    scraper = CacheScraper(make_config(temp_dir), cache)
    scraper.github = Mock()
    scraper.github.release_exists.return_value = False

    selected = scraper._get_available_release("owner/repo", "owner", "repo", "10")

    assert selected is not None
    assert selected.tag == "v0.1"
    scraper.github.release_exists.assert_called_once_with("owner", "repo", "deleted")


def test_selected_tag_is_not_checked_without_same_run_page_observation(temp_dir):
    """Skip-build and list failures cannot authorize persistent cache deletion."""
    cache = ReleaseCache(temp_dir / "release_cache")
    cache.add_release(
        "owner/repo", make_release("keep", "0.2", "2026-08-30T00:00:00Z")
    )
    scraper = CacheScraper(make_config(temp_dir), cache)
    scraper.github = Mock()
    scraper.github.release_exists.return_value = False

    selected = scraper._get_available_release("owner/repo", "owner", "repo", "10")

    assert selected is not None
    assert selected.tag == "keep"
    assert cache.get_repo_cache("owner/repo").get_release_by_tag("keep") is not None
    scraper.github.release_exists.assert_not_called()


def test_release_existence_memo_is_reset_for_each_scrape(temp_dir):
    """A prior scrape's exact-tag result cannot leak into the next scrape."""
    cache = ReleaseCache(temp_dir / "release_cache")
    scraper = CacheScraper(make_config(temp_dir), cache)
    scraper._load_repos_from_input = Mock(return_value=[])
    scraper._save_output = Mock()

    scraper._release_existence[("owner/repo", "v0.2")] = False
    scraper.scrape_all()
    assert scraper._release_existence == {}

    scraper._release_existence[("owner/repo", "v0.2")] = True
    scraper.scrape_all()
    assert scraper._release_existence == {}


@pytest.mark.parametrize("bad_release", [None, {}, {"tag_name": ""}])
def test_get_releases_rejects_an_entire_malformed_page(
    requests_mock, bad_release
):
    """A malformed 100-item page cannot be mistaken for 99 authoritative tags."""
    client = GitHubClient(GitHubConfig())
    releases = [
        {"tag_name": f"v{index}", "assets": []} for index in range(99)
    ]
    releases.append(bad_release)
    requests_mock.get(GitHubAPI.releases("owner", "repo"), json=releases)

    assert client.get_releases("owner", "repo") is None


@pytest.mark.parametrize("bad_assets", [None, {}, [None], [{}]])
def test_get_releases_rejects_malformed_assets(requests_mock, bad_assets):
    """Malformed assets make the page unknown rather than emptying valid cache."""
    client = GitHubClient(GitHubConfig())
    releases = [{"tag_name": "v0.2", "assets": bad_assets}]
    requests_mock.get(GitHubAPI.releases("owner", "repo"), json=releases)

    assert client.get_releases("owner", "repo") is None


def test_get_releases_accepts_well_formed_asset_fields(requests_mock):
    """A complete GitHub asset remains valid after boundary validation."""
    client = GitHubClient(GitHubConfig())
    releases = [make_github_release("v0.2", asset_id=1)]
    requests_mock.get(GitHubAPI.releases("owner", "repo"), json=releases)

    assert client.get_releases("owner", "repo") == releases


@pytest.mark.parametrize(
    ("field", "bad_value"),
    [
        ("id", None),
        ("id", True),
        ("name", 42),
        ("browser_download_url", {}),
        ("content_type", []),
        ("updated_at", None),
    ],
)
def test_get_releases_rejects_malformed_asset_fields(
    requests_mock, field, bad_value
):
    """Asset fields consumed downstream must have their documented JSON types."""
    client = GitHubClient(GitHubConfig())
    releases = [make_github_release("v0.2", asset_id=1)]
    releases[0]["assets"][0][field] = bad_value
    requests_mock.get(GitHubAPI.releases("owner", "repo"), json=releases)

    assert client.get_releases("owner", "repo") is None


@pytest.mark.parametrize(
    ("tag", "encoded"),
    [
        ("v1#build", "v1%23build"),
        ("release/0.2", "release%2F0.2"),
        ("literal%2Ftag", "literal%252Ftag"),
    ],
)
def test_release_by_tag_encodes_the_complete_tag_path(tag, encoded):
    """Exact release checks preserve special characters as one path segment."""
    assert GitHubAPI.release_by_tag("owner", "repo", tag) == (
        f"https://api.github.com/repos/owner/repo/releases/tags/{encoded}"
    )


def test_release_exists_distinguishes_404_from_other_responses(requests_mock):
    """Only a GitHub 404 can authorize cache removal."""
    client = GitHubClient(GitHubConfig())
    url = "https://api.github.com/repos/owner/repo/releases/tags/deleted"
    requests_mock.get(url, status_code=404)

    assert client.release_exists("owner", "repo", "deleted") is False

    requests_mock.get(url, status_code=500)

    assert client.release_exists("owner", "repo", "deleted") is None
