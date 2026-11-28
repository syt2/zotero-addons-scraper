"""Unit tests for the GitLab client and source resolution."""

import json

import pytest

from zotero_scraper.clients.gitlab import GitLabClient
from zotero_scraper.config.constants import XPIProxy
from zotero_scraper.config.settings import GitLabConfig, ScraperConfig
from zotero_scraper.services.source import SourceClient


@pytest.fixture
def client():
    return GitLabClient(GitLabConfig())


def gitlab_release(tag="v1.0.0", link_id=7, name="addon-v1.0.0.xpi"):
    return {
        "tag_name": tag,
        "released_at": "2026-01-02T03:04:05Z",
        "assets": {
            "links": [
                {
                    "id": link_id,
                    "name": name,
                    "url": f"https://example.com/{name}",
                    "direct_asset_url": f"https://example.com/-/releases/{tag}/downloads/{name}",
                }
            ]
        },
    }


class TestGetReleases:
    """Tests for get_releases conversion."""

    def test_converts_to_github_shape(self, client, requests_mock):
        requests_mock.get(
            "https://jihulab.com/api/v4/projects/cislunarspace%2Fbibtex-clean/releases",
            json=[gitlab_release()],
        )

        releases = client.get_releases("jihulab.com", "cislunarspace/bibtex-clean")

        assert releases == [
            {
                "tag_name": "v1.0.0",
                "published_at": "2026-01-02T03:04:05Z",
                "assets": [
                    {
                        "id": 7,
                        "name": "addon-v1.0.0.xpi",
                        "browser_download_url": (
                            "https://example.com/-/releases/v1.0.0"
                            "/downloads/addon-v1.0.0.xpi"
                        ),
                        "content_type": "application/x-xpinstall",
                        "updated_at": "2026-01-02T03:04:05Z",
                    }
                ],
            }
        ]

    def test_empty_releases(self, client, requests_mock):
        requests_mock.get(
            "https://jihulab.com/api/v4/projects/g%2Fp/releases", json=[]
        )
        assert client.get_releases("jihulab.com", "g/p") == []

    def test_non_list_response_returns_none(self, client, requests_mock):
        requests_mock.get(
            "https://jihulab.com/api/v4/projects/g%2Fp/releases", json={"error": 404}
        )
        assert client.get_releases("jihulab.com", "g/p") is None

    def test_missing_tag_returns_none(self, client, requests_mock):
        payload = gitlab_release()
        payload["tag_name"] = ""
        requests_mock.get(
            "https://jihulab.com/api/v4/projects/g%2Fp/releases", json=[payload]
        )
        assert client.get_releases("jihulab.com", "g/p") is None

    def test_zip_content_type(self, client):
        release = client._convert_release(gitlab_release(name="addon.zip"))
        assert release["assets"][0]["content_type"] == "application/x-zip-compressed"

    def test_unnamed_link_falls_back_to_url_basename(self, client):
        payload = gitlab_release()
        payload["assets"]["links"][0]["name"] = None
        release = client._convert_release(payload)
        assert release["assets"][0]["name"] == "addon-v1.0.0.xpi"

    def test_request_failure_returns_none(self, client, requests_mock):
        requests_mock.get(
            "https://jihulab.com/api/v4/projects/g%2Fp/releases", status_code=500
        )
        assert client.get_releases("jihulab.com", "g/p") is None


class TestNamespace:
    """Tests for get_namespace."""

    def test_user(self, client, requests_mock):
        requests_mock.get(
            "https://jihulab.com/api/v4/users",
            json=[{"name": "Someone", "web_url": "https://jihulab.com/someone"}],
        )
        info = client.get_namespace("jihulab.com", "someone")
        assert info.name == "Someone"
        assert info.html_url == "https://jihulab.com/someone"

    def test_group_fallback(self, client, requests_mock):
        requests_mock.get("https://jihulab.com/api/v4/users", json=[])
        requests_mock.get(
            "https://jihulab.com/api/v4/groups/cislunarspace",
            json={
                "name": "cislunarspace",
                "web_url": "https://jihulab.com/groups/cislunarspace",
            },
        )
        info = client.get_namespace("jihulab.com", "cislunarspace")
        assert info.name == "cislunarspace"
        assert info.html_url == "https://jihulab.com/groups/cislunarspace"

    def test_missing_returns_none(self, client, requests_mock):
        requests_mock.get("https://jihulab.com/api/v4/users", json=[])
        requests_mock.get(
            "https://jihulab.com/api/v4/groups/nobody", status_code=404
        )
        assert client.get_namespace("jihulab.com", "nobody") is None


class TestProjectAndReleaseExists:
    """Tests for project info and release existence."""

    def test_get_project(self, client, requests_mock):
        requests_mock.get(
            "https://jihulab.com/api/v4/projects/g%2Fp",
            json={"description": "desc", "star_count": 3},
        )
        info = client.get_project("jihulab.com", "g/p")
        assert info.description == "desc"
        assert info.stargazers_count == 3

    def test_release_exists_true(self, client, requests_mock):
        requests_mock.get(
            "https://jihulab.com/api/v4/projects/g%2Fp/releases/v1.0.0", json={}
        )
        assert client.release_exists("jihulab.com", "g/p", "v1.0.0") is True

    def test_release_exists_404(self, client, requests_mock):
        requests_mock.get(
            "https://jihulab.com/api/v4/projects/g%2Fp/releases/v1.0.0",
            status_code=404,
        )
        assert client.release_exists("jihulab.com", "g/p", "v1.0.0") is False


class TestSourceResolution:
    """Tests for SourceClient repo_url resolution."""

    def _make_client(self, tmp_path, entries):
        for repo, data in entries.items():
            (tmp_path / repo).write_text(json.dumps(data), encoding="utf-8")
        config = ScraperConfig(input_dir=tmp_path)
        return SourceClient(config, github=object())

    def test_no_config_defaults_to_github(self, tmp_path):
        sources = self._make_client(tmp_path, {})
        source = sources.get("octocat/hello")
        assert not source.is_gitlab
        assert source.path == "octocat/hello"

    def test_gitlab_repo_url(self, tmp_path):
        sources = self._make_client(
            tmp_path,
            {"cislunarspace@bibtex-clean": {"repo_url": "https://jihulab.com/cislunarspace/bibtex-clean"}},
        )
        source = sources.get("cislunarspace/bibtex-clean")
        assert source.is_gitlab
        assert source.host == "jihulab.com"
        assert source.path == "cislunarspace/bibtex-clean"

    def test_github_repo_url_stays_github(self, tmp_path):
        sources = self._make_client(
            tmp_path, {"a@b": {"repo_url": "https://github.com/a/b"}}
        )
        assert not sources.get("a/b").is_gitlab

    def test_invalid_repo_url_falls_back_to_github(self, tmp_path):
        sources = self._make_client(tmp_path, {"a@b": {"repo_url": "not a url"}})
        assert not sources.get("a/b").is_gitlab

    def test_routes_calls_to_gitlab_client(self, tmp_path, requests_mock):
        sources = self._make_client(
            tmp_path,
            {"cislunarspace@bibtex-clean": {"repo_url": "https://jihulab.com/cislunarspace/bibtex-clean"}},
        )
        requests_mock.get(
            "https://jihulab.com/api/v4/projects/cislunarspace%2Fbibtex-clean/releases",
            json=[gitlab_release()],
        )
        source = sources.get("cislunarspace/bibtex-clean")
        assert sources.get_releases(source)[0]["tag_name"] == "v1.0.0"


class TestXpiProxy:
    """Tests for proxy generation with non-GitHub URLs."""

    def test_github_url_gets_proxies(self):
        urls = XPIProxy.urls_for(
            "https://github.com/o/r/releases/download/v1/a.xpi"
        )
        assert "ghProxy" in urls

    def test_gitlab_url_has_no_proxies(self):
        urls = XPIProxy.urls_for(
            "https://jihulab.com/g/p/-/releases/v1.0.0/downloads/a.xpi"
        )
        assert urls == {}
