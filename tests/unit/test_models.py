"""Unit tests for data models."""

import pytest

from zotero_scraper.models.addon import (
    AddonInfo,
    AddonRelease,
    Author,
    XpiDownloadUrls,
)


class TestAuthor:
    """Tests for Author model."""

    def test_to_dict_full(self):
        """Test to_dict with all fields."""
        author = Author(
            name="Test Author",
            url="https://github.com/test",
            avatar="https://avatars.githubusercontent.com/test",
        )
        result = author.to_dict()
        assert result == {
            "name": "Test Author",
            "url": "https://github.com/test",
            "avatar": "https://avatars.githubusercontent.com/test",
        }

    def test_to_dict_excludes_none(self):
        """Test to_dict excludes None values."""
        author = Author(name="Test", url=None, avatar=None)
        result = author.to_dict()
        assert result == {"name": "Test"}

    def test_from_dict(self):
        """Test from_dict factory method."""
        data = {"name": "Test", "url": "https://example.com"}
        author = Author.from_dict(data)
        assert author.name == "Test"
        assert author.url == "https://example.com"
        assert author.avatar is None

    def test_from_dict_none(self):
        """Test from_dict with None input."""
        author = Author.from_dict(None)
        assert author.name is None
        assert author.url is None
        assert author.avatar is None


class TestXpiDownloadUrls:
    """Tests for XpiDownloadUrls model."""

    def test_to_dict_full(self):
        """Test to_dict with all fields."""
        urls = XpiDownloadUrls(
            github="https://github.com/example.xpi",
            ghProxy="https://gh-proxy.com/example.xpi",
            kgithub="https://kkgithub.com/example.xpi",
        )
        result = urls.to_dict()
        assert result == {
            "github": "https://github.com/example.xpi",
            "ghProxy": "https://gh-proxy.com/example.xpi",
            "kgithub": "https://kkgithub.com/example.xpi",
        }

    def test_to_dict_minimal(self):
        """Test to_dict with only required fields."""
        urls = XpiDownloadUrls(github="https://github.com/example.xpi")
        result = urls.to_dict()
        assert result == {"github": "https://github.com/example.xpi"}

    def test_from_dict_valid(self):
        """Test from_dict with valid data."""
        data = {"github": "https://github.com/example.xpi"}
        urls = XpiDownloadUrls.from_dict(data)
        assert urls is not None
        assert urls.github == "https://github.com/example.xpi"

    def test_from_dict_missing_github(self):
        """Test from_dict returns None if github is missing."""
        data = {"ghProxy": "https://gh-proxy.com/example.xpi"}
        urls = XpiDownloadUrls.from_dict(data)
        assert urls is None


class TestAddonRelease:
    """Tests for AddonRelease model."""

    def test_zotero_check_version_7(self):
        """Test zotero_check_version for Zotero 7."""
        release = AddonRelease(targetZoteroVersion="7", tagName="latest")
        assert release.zotero_check_version == "7.*"

    def test_zotero_check_version_6(self):
        """Test zotero_check_version for Zotero 6."""
        release = AddonRelease(targetZoteroVersion="6", tagName="v1.0")
        assert release.zotero_check_version == "6.*"

    def test_zotero_check_version_invalid(self):
        """Test zotero_check_version raises for invalid version."""
        release = AddonRelease(targetZoteroVersion="5", tagName="v1.0")
        with pytest.raises(ValueError, match="Invalid targetZoteroVersion"):
            _ = release.zotero_check_version

    def test_to_dict_minimal(self):
        """Test to_dict with minimal fields."""
        release = AddonRelease(targetZoteroVersion="7", tagName="latest")
        result = release.to_dict()
        assert result == {"targetZoteroVersion": "7", "tagName": "latest"}

    def test_to_dict_full(self):
        """Test to_dict with all fields."""
        release = AddonRelease(
            targetZoteroVersion="7",
            tagName="v1.0.0",
            xpiDownloadUrl=XpiDownloadUrls(github="https://example.com"),
            releaseDate="2024-01-01T00:00:00Z",
            id="test@addon.com",
            xpiVersion="1.0.0",
            name="Test Addon",
            description="Test description",
            minZoteroVersion="7.0",
            maxZoteroVersion="7.*",
        )
        result = release.to_dict()
        assert result["targetZoteroVersion"] == "7"
        assert result["tagName"] == "v1.0.0"
        assert result["xpiDownloadUrl"] == {"github": "https://example.com"}
        assert result["id"] == "test@addon.com"

    def test_from_dict(self, sample_addon_config):
        """Test from_dict factory method."""
        release_data = sample_addon_config["releases"][0]
        release = AddonRelease.from_dict(release_data)
        assert release.targetZoteroVersion == "7"
        assert release.tagName == "latest"


class TestAddonInfo:
    """Tests for AddonInfo model."""

    def test_owner_valid(self):
        """Test owner property with valid repo."""
        addon = AddonInfo(repo="owner/repo", releases=[])
        assert addon.owner == "owner"

    def test_owner_invalid(self):
        """Test owner property with invalid repo."""
        addon = AddonInfo(repo="invalid", releases=[])
        assert addon.owner is None

    def test_repository_valid(self):
        """Test repository property with valid repo."""
        addon = AddonInfo(repo="owner/repo", releases=[])
        assert addon.repository == "repo"

    def test_repository_invalid(self):
        """Test repository property with invalid repo."""
        addon = AddonInfo(repo="invalid", releases=[])
        assert addon.repository is None

    def test_to_dict_backward_compatible(self):
        """Test to_dict maintains backward compatibility."""
        addon = AddonInfo(
            repo="owner/repo",
            releases=[AddonRelease(targetZoteroVersion="7", tagName="v1.0")],
            name="Test",
            stars=100,
            author=Author(name="Author"),
        )
        result = addon.to_dict()

        # Check backward compatibility: both "stars" and "star" should exist
        assert result["stars"] == 100
        assert result["star"] == 100
        assert result["repo"] == "owner/repo"
        assert result["name"] == "Test"
        assert result["author"] == {"name": "Author"}

    def test_from_dict(self, sample_addon_config):
        """Test from_dict factory method."""
        addon = AddonInfo.from_dict(sample_addon_config)
        assert addon.repo == "owner/repo"
        assert len(addon.releases) == 2
        assert addon.releases[0].targetZoteroVersion == "7"
        assert addon.releases[1].tagName == "v1.0"
