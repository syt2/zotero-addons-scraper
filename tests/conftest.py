"""Pytest fixtures for Zotero addons scraper tests."""

import json
import tempfile
from pathlib import Path
from typing import Any

import pytest


@pytest.fixture
def fixtures_dir() -> Path:
    """Return path to fixtures directory."""
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def temp_dir():
    """Create a temporary directory for tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_manifest_json() -> dict[str, Any]:
    """Return sample manifest.json data."""
    return {
        "name": "Test Addon",
        "version": "1.0.0",
        "description": "A test addon for Zotero",
        "browser_specific_settings": {
            "zotero": {
                "id": "test@addon.com",
                "strict_min_version": "6.0",
                "strict_max_version": "7.*",
            }
        },
    }


@pytest.fixture
def sample_addon_config() -> dict[str, Any]:
    """Return sample addon configuration."""
    return {
        "repo": "owner/repo",
        "releases": [
            {"targetZoteroVersion": "7", "tagName": "latest"},
            {"targetZoteroVersion": "6", "tagName": "v1.0"},
        ],
    }


@pytest.fixture
def sample_addon_info_output() -> dict[str, Any]:
    """Return sample output addon info."""
    return {
        "repo": "owner/repo",
        "releases": [
            {
                "targetZoteroVersion": "7",
                "tagName": "v2.0.0",
                "xpiDownloadUrl": {
                    "github": "https://github.com/owner/repo/releases/download/v2.0.0/addon.xpi",
                    "ghProxy": "https://gh-proxy.com/?q=https%3A//github.com/owner/repo/releases/download/v2.0.0/addon.xpi",
                    "kgithub": "https://kkgithub.com/owner/repo/releases/download/v2.0.0/addon.xpi",
                },
                "releaseDate": "2024-01-01T00:00:00Z",
                "id": "test@addon.com",
                "xpiVersion": "2.0.0",
                "name": "Test Addon",
                "description": "A test addon",
                "minZoteroVersion": "7.0",
                "maxZoteroVersion": "7.*",
            }
        ],
        "name": "repo",
        "description": "Test repository",
        "stars": 100,
        "star": 100,
        "author": {
            "name": "Test Author",
            "url": "https://github.com/owner",
            "avatar": "https://avatars.githubusercontent.com/owner",
        },
    }


@pytest.fixture
def github_user_response() -> dict[str, Any]:
    """Return sample GitHub user API response."""
    return {
        "login": "owner",
        "name": "Test Owner",
        "html_url": "https://github.com/owner",
        "avatar_url": "https://avatars.githubusercontent.com/owner",
    }


@pytest.fixture
def github_repo_response() -> dict[str, Any]:
    """Return sample GitHub repo API response."""
    return {
        "name": "repo",
        "full_name": "owner/repo",
        "description": "Test repository description",
        "stargazers_count": 100,
    }


@pytest.fixture
def github_release_response() -> dict[str, Any]:
    """Return sample GitHub release API response."""
    return {
        "tag_name": "v2.0.0",
        "prerelease": False,
        "published_at": "2024-01-01T00:00:00Z",
        "assets": [
            {
                "id": 12345,
                "name": "addon.xpi",
                "browser_download_url": "https://github.com/owner/repo/releases/download/v2.0.0/addon.xpi",
                "content_type": "application/x-xpinstall",
                "updated_at": "2024-01-01T00:00:00Z",
            }
        ],
    }
