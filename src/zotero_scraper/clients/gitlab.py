"""GitLab API client.

The scraper pipeline is built around GitHub release payloads. This client
translates GitLab releases into the same shape so downstream services can
process both platforms unchanged.
"""

from typing import Any, Optional
from urllib.parse import quote

from ..config.constants import ContentTypes
from ..config.settings import GitLabConfig
from ..utils.logging import get_logger
from .base import BaseHTTPClient
from .github import RepoInfo, UserInfo

logger = get_logger("clients.gitlab")


class GitLabClient(BaseHTTPClient):
    """GitLab API client producing GitHub-shaped release data.

    Works with gitlab.com, Jihu GitLab (jihulab.com) and self-hosted
    instances. Authentication is optional for public projects.
    """

    def __init__(self, config: GitLabConfig):
        """Initialize GitLab client.

        Args:
            config: GitLab configuration.
        """
        super().__init__(
            timeout=config.timeout,
            max_retries=config.max_retries,
            backoff_factor=config.retry_delay,
        )
        self.config = config
        self._headers = self._build_headers()

    def _build_headers(self) -> dict[str, str]:
        """Build request headers."""
        headers = {"Accept": "application/json"}
        if self.config.token:
            headers["PRIVATE-TOKEN"] = self.config.token
        return headers

    @staticmethod
    def project_id(path: str) -> str:
        """URL-encode a project path for API requests."""
        return quote(path.strip("/"), safe="")

    def _api_url(self, host: str, path: str) -> str:
        return f"https://{host}/api/v4/{path}"

    def get_releases(
        self, host: str, path: str, per_page: int = 100
    ) -> Optional[list[dict[str, Any]]]:
        """Get releases for a GitLab project as GitHub-shaped dicts.

        Args:
            host: GitLab instance host, e.g. "jihulab.com".
            path: Project path, e.g. "group/project".
            per_page: Number of releases to fetch (max 100).

        Returns:
            List of release dictionaries in the GitHub API shape, an empty
            list when none exist, or None when the request or response
            validation fails.
        """
        url = self._api_url(host, f"projects/{self.project_id(path)}/releases")
        try:
            response = self.get(
                url, headers=self._headers, params={"per_page": per_page}
            )
            data: Any = response.json()
            if not isinstance(data, list):
                logger.warning(f"Invalid release response for {host}/{path}")
                return None

            releases: list[dict[str, Any]] = []
            for release in data:
                converted = self._convert_release(release)
                if converted is None:
                    logger.warning(f"Invalid release response for {host}/{path}")
                    return None
                releases.append(converted)
            return releases
        except Exception as e:
            logger.warning(f"Failed to get releases for {host}/{path}: {e}")
            return None

    def _convert_release(self, release: Any) -> Optional[dict[str, Any]]:
        """Convert a GitLab release payload to the GitHub release shape."""
        if not isinstance(release, dict):
            return None
        tag = release.get("tag_name")
        if not isinstance(tag, str) or not tag:
            return None
        released_at = release.get("released_at") or release.get("created_at") or ""

        assets_block = release.get("assets")
        links = (
            assets_block.get("links")
            if isinstance(assets_block, dict)
            else None
        )
        if not isinstance(links, list):
            links = []

        assets: list[dict[str, Any]] = []
        for link in links:
            if not isinstance(link, dict):
                return None
            url = link.get("direct_asset_url") or link.get("url")
            if not isinstance(url, str) or not url:
                return None
            name = link.get("name")
            if not isinstance(name, str) or not name:
                name = url.rsplit("/", 1)[-1]
            asset_id = link.get("id")
            assets.append(
                {
                    "id": asset_id if isinstance(asset_id, int) else 0,
                    "name": name,
                    "browser_download_url": url,
                    "content_type": self._content_type_for(name),
                    "updated_at": released_at,
                }
            )

        return {
            "tag_name": tag,
            "published_at": released_at,
            "assets": assets,
        }

    @staticmethod
    def _content_type_for(name: str) -> str:
        """Guess a content type from the asset filename."""
        if name.lower().endswith(".xpi"):
            return ContentTypes.XPI
        if name.lower().endswith(".zip"):
            return ContentTypes.ZIP
        return ContentTypes.OCTET_STREAM

    def get_namespace(self, host: str, name: str) -> Optional[UserInfo]:
        """Get namespace information (user or group).

        Args:
            host: GitLab instance host.
            name: Username or group path.

        Returns:
            UserInfo or None if failed.
        """
        try:
            url = self._api_url(host, "users")
            response = self.get(
                url, headers=self._headers, params={"username": name}
            )
            users = response.json()
            if isinstance(users, list) and users and isinstance(users[0], dict):
                user = users[0]
                return UserInfo(
                    name=user.get("name") or name,
                    html_url=user.get("web_url", ""),
                    avatar_url=user.get("avatar_url"),
                )

            url = self._api_url(host, f"groups/{quote(name, safe='')}")
            response = self.get(url, headers=self._headers, allowed_status_codes={404})
            if response.status_code == 404:
                return None
            group = response.json()
            if not isinstance(group, dict):
                return None
            return UserInfo(
                name=group.get("name") or name,
                html_url=group.get("web_url", ""),
                avatar_url=group.get("avatar_url"),
            )
        except Exception as e:
            logger.warning(f"Failed to get namespace {name} on {host}: {e}")
            return None

    def get_project(self, host: str, path: str) -> Optional[RepoInfo]:
        """Get project information.

        Args:
            host: GitLab instance host.
            path: Project path, e.g. "group/project".

        Returns:
            RepoInfo or None if failed.
        """
        url = self._api_url(host, f"projects/{self.project_id(path)}")
        try:
            response = self.get(url, headers=self._headers)
            data = response.json()
            if not isinstance(data, dict):
                return None
            return RepoInfo(
                description=data.get("description"),
                stargazers_count=data.get("star_count", 0),
            )
        except Exception as e:
            logger.warning(f"Failed to get project {host}/{path}: {e}")
            return None

    def release_exists(self, host: str, path: str, tag: str) -> Optional[bool]:
        """Return whether a release tag exists, preserving failures as unknown.

        A confirmed 404 means the release can be safely removed from the
        persistent cache. Other failures must not cause cache deletion.
        """
        url = self._api_url(
            host,
            f"projects/{self.project_id(path)}/releases/{quote(tag, safe='')}",
        )
        try:
            response = self.get(
                url,
                headers=self._headers,
                allowed_status_codes={404},
            )
            return response.status_code != 404
        except Exception as e:
            logger.warning(f"Failed to check release {host}/{path}@{tag}: {e}")
            return None
