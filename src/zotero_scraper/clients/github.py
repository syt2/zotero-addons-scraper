"""GitHub API client."""

import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Optional

from ..config.constants import GitHubAPI
from ..config.settings import GitHubConfig
from ..exceptions import GitHubError
from ..utils.logging import get_logger
from .base import BaseHTTPClient

logger = get_logger("clients.github")


@dataclass
class UserInfo:
    """GitHub user information."""

    name: str
    html_url: str
    avatar_url: Optional[str] = None


@dataclass
class RepoInfo:
    """GitHub repository information."""

    description: Optional[str]
    stargazers_count: int


@dataclass
class ReleaseAsset:
    """GitHub release asset information."""

    id: int
    name: str
    browser_download_url: str
    content_type: str
    updated_at: str


@dataclass
class ReleaseInfo:
    """GitHub release information."""

    tag_name: str
    prerelease: bool
    published_at: str
    assets: list[ReleaseAsset]


class GitHubClient(BaseHTTPClient):
    """GitHub API client with typed responses."""

    def __init__(self, config: GitHubConfig):
        """Initialize GitHub client.

        Args:
            config: GitHub configuration.
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
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": self.config.api_version,
        }
        if self.config.token:
            headers["Authorization"] = f"token {self.config.token}"
        return headers

    def get_user(self, username: str) -> Optional[UserInfo]:
        """Get user information.

        Args:
            username: GitHub username.

        Returns:
            UserInfo or None if failed.
        """
        url = GitHubAPI.user(username)
        try:
            response = self.get(url, headers=self._headers)
            data = response.json()
            return UserInfo(
                name=data.get("name") or username,
                html_url=data.get("html_url", ""),
                avatar_url=data.get("avatar_url"),
            )
        except Exception as e:
            logger.warning(f"Failed to get user {username}: {e}")
            return None

    def get_repo(self, owner: str, repo: str) -> Optional[RepoInfo]:
        """Get repository information.

        Args:
            owner: Repository owner.
            repo: Repository name.

        Returns:
            RepoInfo or None if failed.
        """
        url = GitHubAPI.repo(owner, repo)
        try:
            response = self.get(url, headers=self._headers)
            data = response.json()
            return RepoInfo(
                description=data.get("description"),
                stargazers_count=data.get("stargazers_count", 0),
            )
        except Exception as e:
            logger.warning(f"Failed to get repo {owner}/{repo}: {e}")
            return None

    def get_releases(
        self, owner: str, repo: str, per_page: int = 100, max_pages: int = 10
    ) -> list[dict[str, Any]]:
        """Get all releases for a repository with pagination.

        Args:
            owner: Repository owner.
            repo: Repository name.
            per_page: Number of releases per page (max 100).
            max_pages: Maximum number of pages to fetch.

        Returns:
            List of release data dictionaries.
        """
        url = GitHubAPI.releases(owner, repo)
        all_releases: list[dict[str, Any]] = []

        try:
            for page in range(1, max_pages + 1):
                response = self.get(
                    url,
                    headers=self._headers,
                    params={"per_page": per_page, "page": page},
                )
                releases = response.json()

                if not releases:
                    break

                all_releases.extend(releases)

                # If we got fewer than per_page, we've reached the end
                if len(releases) < per_page:
                    break

            logger.debug(f"Fetched {len(all_releases)} releases for {owner}/{repo}")
            return all_releases
        except Exception as e:
            logger.warning(f"Failed to get releases for {owner}/{repo}: {e}")
            return all_releases if all_releases else []

    def get_release(
        self, owner: str, repo: str, tag: str
    ) -> Optional[ReleaseInfo]:
        """Get release by tag.

        Args:
            owner: Repository owner.
            repo: Repository name.
            tag: Tag name ("latest", "pre", or specific tag).

        Returns:
            ReleaseInfo or None if not found.
        """
        try:
            if tag == "latest":
                url = GitHubAPI.release_latest(owner, repo)
                response = self.get(url, headers=self._headers)
                data = response.json()
            elif tag == "pre":
                # Find first prerelease
                releases = self.get_releases(owner, repo)
                prereleases = [r for r in releases if r.get("prerelease")]
                if not prereleases:
                    return None
                data = prereleases[0]
            else:
                url = GitHubAPI.release_by_tag(owner, repo, tag)
                response = self.get(url, headers=self._headers)
                data = response.json()

            assets = [
                ReleaseAsset(
                    id=a["id"],
                    name=a["name"],
                    browser_download_url=a["browser_download_url"],
                    content_type=a.get("content_type", ""),
                    updated_at=a.get("updated_at", ""),
                )
                for a in data.get("assets", [])
            ]

            return ReleaseInfo(
                tag_name=data.get("tag_name", tag),
                prerelease=data.get("prerelease", False),
                published_at=data.get("published_at", ""),
                assets=assets,
            )
        except Exception as e:
            logger.warning(f"Failed to get release {owner}/{repo}@{tag}: {e}")
            return None

    def create_release(
        self,
        owner: str,
        repo: str,
        tag_name: Optional[str] = None,
        target_commitish: str = "publish",
    ) -> Optional[int]:
        """Create a new release.

        Args:
            owner: Repository owner.
            repo: Repository name.
            tag_name: Tag name (defaults to current timestamp).
            target_commitish: Target branch/commit.

        Returns:
            Release ID or None if failed.
        """
        url = GitHubAPI.releases(owner, repo)
        cur_time = int(time.time())
        tag = tag_name or str(cur_time)

        payload = {
            "tag_name": tag,
            "target_commitish": target_commitish,
            "name": tag,
            "body": (
                f"![](https://img.shields.io/github/downloads/{owner}/{repo}"
                f"/{tag}/total?label=downloads)\npublish addon_infos.json"
            ),
            "draft": False,
            "prerelease": False,
            "generate_release_notes": False,
        }

        try:
            response = self.post(url, headers=self._headers, json=payload)
            if response.status_code == 201:
                release_id = response.json().get("id")
                logger.info(f"Created release {tag} with ID {release_id}")
                return release_id
            logger.error(f"Create release failed: {response.status_code}")
            return None
        except Exception as e:
            logger.error(f"Create release failed: {e}")
            return None

    def upload_release_asset(
        self,
        owner: str,
        repo: str,
        release_id: int,
        filename: str,
        filepath: str,
    ) -> bool:
        """Upload asset to release.

        Args:
            owner: Repository owner.
            repo: Repository name.
            release_id: Release ID.
            filename: Asset filename.
            filepath: Local file path.

        Returns:
            True if successful.
        """
        url = GitHubAPI.upload_asset(owner, repo, release_id, filename)
        headers = {**self._headers, "Content-Type": "application/octet-stream"}

        try:
            with open(filepath, "rb") as f:
                response = self.post(url, headers=headers, data=f)
            if response.status_code == 201:
                logger.info(f"Uploaded asset {filename}")
                return True
            logger.error(f"Upload asset failed: {response.status_code}")
            return False
        except Exception as e:
            logger.error(f"Upload asset failed: {e}")
            return False

    def create_issue(
        self,
        owner: str,
        repo: str,
        title: str,
        body: str,
        check_duplicate_id: Optional[str] = None,
    ) -> bool:
        """Create an issue with optional duplicate check.

        Args:
            owner: Repository owner.
            repo: Repository name.
            title: Issue title.
            body: Issue body.
            check_duplicate_id: Optional ID to check for duplicates.

        Returns:
            True if created (or skipped as duplicate).
        """
        if check_duplicate_id:
            body = f"{body}\n----{check_duplicate_id}"
            if self._issue_exists(owner, repo, check_duplicate_id):
                logger.debug(f"Issue already exists: {check_duplicate_id}")
                return True

        url = GitHubAPI.issues(owner, repo)
        try:
            response = self.post(
                url,
                headers=self._headers,
                json={"title": title, "body": body},
            )
            if response.status_code == 201:
                issue_url = response.json().get("html_url")
                logger.info(f"Issue created: {issue_url}")
                return True
            logger.error(f"Create issue failed: {response.status_code}")
            return False
        except Exception as e:
            logger.error(f"Create issue failed: {e}")
            return False

    def _issue_exists(self, owner: str, repo: str, check_id: str) -> bool:
        """Check if an issue with given ID already exists."""
        url = GitHubAPI.issues(owner, repo)
        try:
            since = (datetime.now(UTC) - timedelta(days=10)).isoformat() + "Z"
            response = self.get(
                url,
                headers=self._headers,
                params={"state": "open", "since": since, "per_page": 100},
            )
            issues = response.json()
            return any(
                issue.get("body", "").endswith(f"----{check_id}")
                for issue in issues
            )
        except Exception:
            return False

    def delete_old_releases(
        self, owner: str, repo: str, keep_count: int = 2
    ) -> None:
        """Delete old releases, keeping the most recent ones.

        Args:
            owner: Repository owner.
            repo: Repository name.
            keep_count: Number of releases to keep.
        """
        url = GitHubAPI.releases(owner, repo)
        try:
            response = self.get(
                url, headers=self._headers, params={"per_page": 100}
            )
            releases = response.json()
            if len(releases) <= keep_count:
                return

            # Sort by tag_name descending
            releases.sort(key=lambda r: r.get("tag_name", ""), reverse=True)

            for release in releases[keep_count:]:
                release_id = release.get("id")
                tag = release.get("tag_name")
                if release_id:
                    delete_url = f"{url}/{release_id}"
                    try:
                        resp = self.delete(delete_url, headers=self._headers)
                        if resp.status_code == 204:
                            logger.info(f"Deleted release: {tag}")
                        else:
                            logger.warning(
                                f"Failed to delete release {tag}: {resp.text}"
                            )
                    except Exception as e:
                        logger.warning(f"Failed to delete release {tag}: {e}")
        except Exception as e:
            logger.error(f"Delete old releases failed: {e}")

    def delete_old_tags(
        self, owner: str, repo: str, keep_count: int = 2
    ) -> None:
        """Delete old timestamp-based tags.

        Args:
            owner: Repository owner.
            repo: Repository name.
            keep_count: Number of tags to keep.
        """
        url = GitHubAPI.tags(owner, repo)
        try:
            response = self.get(url, headers=self._headers)
            tags = response.json()
            if len(tags) <= keep_count:
                return

            # Sort by ref descending
            tags.sort(key=lambda t: t.get("ref", ""), reverse=True)

            for tag in tags[keep_count:]:
                ref = tag.get("ref", "").replace("refs/tags/", "")
                # Only delete timestamp tags (numeric, >= 10 digits)
                if len(ref) < 10:
                    continue
                try:
                    int(ref)  # Verify it's a timestamp
                except ValueError:
                    continue

                delete_url = f"{url}/{ref}"
                try:
                    resp = self.delete(delete_url, headers=self._headers)
                    if resp.status_code == 204:
                        logger.info(f"Deleted tag: {ref}")
                    else:
                        logger.warning(f"Failed to delete tag {ref}: {resp.text}")
                except Exception as e:
                    logger.warning(f"Failed to delete tag {ref}: {e}")
        except Exception as e:
            logger.error(f"Delete old tags failed: {e}")

    def delete_old_caches(
        self, owner: str, repo: str, keep_count: int = 2
    ) -> None:
        """Delete old action caches.

        Args:
            owner: Repository owner.
            repo: Repository name.
            keep_count: Number of caches to keep.
        """
        url = GitHubAPI.caches(owner, repo)
        try:
            response = self.get(
                url,
                headers=self._headers,
                params={
                    "per_page": 100,
                    "sort": "last_accessed_at",
                    "direction": "desc",
                },
            )
            data = response.json()
            if data.get("total_count", 0) <= keep_count:
                return

            for cache in data.get("actions_caches", [])[keep_count:]:
                cache_id = cache.get("id")
                cache_key = cache.get("key")
                if cache_id:
                    delete_url = f"{url}/{cache_id}"
                    try:
                        resp = self.delete(delete_url, headers=self._headers)
                        if resp.status_code == 204:
                            logger.info(f"Deleted cache: {cache_key}")
                        else:
                            logger.warning(
                                f"Failed to delete cache {cache_key}: {resp.text}"
                            )
                    except Exception as e:
                        logger.warning(f"Failed to delete cache {cache_key}: {e}")
        except Exception as e:
            logger.error(f"Delete old caches failed: {e}")

    def get_rate_limit(self) -> Optional[dict[str, Any]]:
        """Get current rate limit status.

        Returns:
            Rate limit info or None if failed.
        """
        try:
            response = self.get(GitHubAPI.rate_limit(), headers=self._headers)
            rate = response.json().get("rate")
            logger.info(f"Rate limit: {rate}")
            return rate
        except Exception as e:
            logger.error(f"Get rate limit failed: {e}")
            return None
