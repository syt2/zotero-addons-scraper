"""Release cache service for storing parsed release information."""

import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Optional

from ..utils.logging import get_logger

logger = get_logger("cache.release_cache")


@dataclass
class CachedRelease:
    """Cached release information parsed from XPI."""

    tag: str
    published_at: str
    xpi_asset_id: int
    xpi_name: str
    xpi_download_url: str
    # Parsed from XPI manifest
    addon_id: Optional[str] = None
    addon_name: Optional[str] = None
    addon_version: Optional[str] = None
    addon_description: Optional[str] = None
    min_zotero_version: Optional[str] = None
    max_zotero_version: Optional[str] = None
    update_url: Optional[str] = None
    # Parse status
    parse_success: bool = True
    parse_error: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {k: v for k, v in asdict(self).items() if v is not None}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CachedRelease":
        """Create from dictionary."""
        return cls(
            tag=data.get("tag", ""),
            published_at=data.get("published_at", ""),
            xpi_asset_id=data.get("xpi_asset_id", 0),
            xpi_name=data.get("xpi_name", ""),
            xpi_download_url=data.get("xpi_download_url", ""),
            addon_id=data.get("addon_id"),
            addon_name=data.get("addon_name"),
            addon_version=data.get("addon_version"),
            addon_description=data.get("addon_description"),
            min_zotero_version=data.get("min_zotero_version"),
            max_zotero_version=data.get("max_zotero_version"),
            update_url=data.get("update_url"),
            parse_success=data.get("parse_success", True),
            parse_error=data.get("parse_error"),
        )

    def is_compatible_with(self, zotero_version: str) -> bool:
        """Check if this release is compatible with a Zotero version.

        Args:
            zotero_version: Target version like "6" or "7" or "8".

        Returns:
            True if compatible.
        """
        from ..utils.version import compare_versions

        if not self.parse_success or not self.min_zotero_version:
            return False

        # Normalize versions - replace * with appropriate values
        min_ver = self.min_zotero_version.replace("*", "0")
        max_ver = (self.max_zotero_version or "999").replace("*", "999")

        # Target version X.0 must be within [min_version, max_version]
        # e.g., for target "7", check if 7.0 >= min_ver and 7.0 <= max_ver
        target = f"{zotero_version}.*"

        return (
            compare_versions(target, min_ver) >= 0
            and compare_versions(target, max_ver) <= 0
        )


@dataclass
class RepoCache:
    """Cache for a single repository."""

    last_checked: str = ""
    checked_releases: list[CachedRelease] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "last_checked": self.last_checked,
            "checked_releases": [r.to_dict() for r in self.checked_releases],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RepoCache":
        """Create from dictionary."""
        releases = [
            CachedRelease.from_dict(r)
            for r in data.get("checked_releases", [])
        ]
        return cls(
            last_checked=data.get("last_checked", ""),
            checked_releases=releases,
        )

    def get_checked_tags(self) -> set[str]:
        """Get set of already checked tags."""
        return {r.tag for r in self.checked_releases}

    def get_release_by_tag(self, tag: str) -> Optional[CachedRelease]:
        """Get cached release by tag."""
        for release in self.checked_releases:
            if release.tag == tag:
                return release
        return None

    def add_release(self, release: CachedRelease) -> None:
        """Add or update a release in cache."""
        # Remove existing release with same tag
        self.checked_releases = [
            r for r in self.checked_releases if r.tag != release.tag
        ]
        self.checked_releases.append(release)

    def remove_deleted_releases(self, current_tags: set[str]) -> list[str]:
        """Remove releases that no longer exist on GitHub.

        Args:
            current_tags: Set of tags that currently exist on GitHub.

        Returns:
            List of removed tags.
        """
        removed = []
        new_releases = []
        for release in self.checked_releases:
            if release.tag in current_tags:
                new_releases.append(release)
            else:
                removed.append(release.tag)
        self.checked_releases = new_releases
        return removed

    def get_best_release_for_zotero(
        self, zotero_version: str
    ) -> Optional[CachedRelease]:
        """Get the best (latest compatible) release for a Zotero version.

        Args:
            zotero_version: Target version like "6" or "7".

        Returns:
            Best compatible release or None.
        """
        compatible = [
            r for r in self.checked_releases
            if r.is_compatible_with(zotero_version)
        ]

        if not compatible:
            return None

        # Sort by published_at descending to get latest
        compatible.sort(key=lambda r: r.published_at, reverse=True)
        return compatible[0]

    def get_latest_release(self) -> Optional[CachedRelease]:
        """Get the latest release by published_at.

        Returns:
            Latest release or None if no releases.
        """
        if not self.checked_releases:
            return None

        # Sort by published_at descending
        sorted_releases = sorted(
            self.checked_releases,
            key=lambda r: r.published_at,
            reverse=True
        )
        return sorted_releases[0]


class ReleaseCache:
    """Service for managing release cache.

    Uses a directory structure where each repo has its own JSON file:
        release_cache/
        ├── windingwind#zotero-pdf-translate.json
        ├── MuiseDestiny#zotero-gpt.json
        └── ...
    """

    def __init__(self, cache_dir: Path):
        """Initialize release cache.

        Args:
            cache_dir: Directory to store cache files.
        """
        self.cache_dir = cache_dir
        self._cache: dict[str, RepoCache] = {}
        self._dirty: set[str] = set()  # Track which repos need saving

    def _repo_to_filename(self, repo: str) -> str:
        """Convert repo name to filename."""
        # owner/name -> owner#name.json
        return repo.replace("/", "#") + ".json"

    def _filename_to_repo(self, filename: str) -> str:
        """Convert filename to repo name."""
        # owner#name.json -> owner/name
        return filename.replace(".json", "").replace("#", "/")

    def _get_repo_file(self, repo: str) -> Path:
        """Get the cache file path for a repo."""
        return self.cache_dir / self._repo_to_filename(repo)

    def _load_repo(self, repo: str) -> RepoCache:
        """Load cache for a single repo."""
        cache_file = self._get_repo_file(repo)

        if not cache_file.exists():
            return RepoCache()

        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            return RepoCache.from_dict(data)
        except Exception as e:
            logger.warning(f"Failed to load cache for {repo}: {e}")
            return RepoCache()

    def _save_repo(self, repo: str) -> None:
        """Save cache for a single repo."""
        if repo not in self._cache:
            return

        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            cache_file = self._get_repo_file(repo)

            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(self._cache[repo].to_dict(), f, ensure_ascii=False, indent=2)

            self._dirty.discard(repo)
        except Exception as e:
            logger.error(f"Failed to save cache for {repo}: {e}")

    def save(self) -> None:
        """Save all dirty (modified) repos."""
        saved_count = 0
        for repo in list(self._dirty):
            self._save_repo(repo)
            saved_count += 1

        if saved_count > 0:
            logger.info(f"Saved cache for {saved_count} repos")

    def save_all(self) -> None:
        """Save all repos in memory (regardless of dirty state)."""
        for repo in self._cache:
            self._save_repo(repo)
        logger.info(f"Saved cache for {len(self._cache)} repos")

    def get_repo_cache(self, repo: str) -> RepoCache:
        """Get cache for a repository.

        Args:
            repo: Repository in "owner/name" format.

        Returns:
            RepoCache instance (loads from file or creates empty one).
        """
        if repo not in self._cache:
            self._cache[repo] = self._load_repo(repo)
        return self._cache[repo]

    def update_repo_checked_time(self, repo: str) -> None:
        """Update the last checked time for a repository.

        Args:
            repo: Repository in "owner/name" format.
        """
        cache = self.get_repo_cache(repo)
        cache.last_checked = datetime.now(UTC).isoformat()
        self._dirty.add(repo)

    def get_unchecked_tags(
        self, repo: str, all_tags: list[str]
    ) -> list[str]:
        """Get tags that haven't been checked yet.

        Args:
            repo: Repository in "owner/name" format.
            all_tags: List of all tags from GitHub.

        Returns:
            List of unchecked tags.
        """
        cache = self.get_repo_cache(repo)
        checked = cache.get_checked_tags()
        return [tag for tag in all_tags if tag not in checked]

    def add_release(self, repo: str, release: CachedRelease) -> None:
        """Add a release to cache.

        Args:
            repo: Repository in "owner/name" format.
            release: CachedRelease instance.
        """
        cache = self.get_repo_cache(repo)
        cache.add_release(release)
        self._dirty.add(repo)

    def sync_with_github(
        self, repo: str, current_tags: set[str]
    ) -> list[str]:
        """Sync cache with GitHub, removing deleted releases.

        Args:
            repo: Repository in "owner/name" format.
            current_tags: Set of tags that currently exist on GitHub.

        Returns:
            List of removed tags.
        """
        cache = self.get_repo_cache(repo)
        removed = cache.remove_deleted_releases(current_tags)
        if removed:
            self._dirty.add(repo)
        return removed

    def get_repos(self) -> list[str]:
        """Get all cached repository names from directory."""
        if not self.cache_dir.exists():
            return []

        repos = []
        for cache_file in self.cache_dir.glob("*.json"):
            repo = self._filename_to_repo(cache_file.name)
            repos.append(repo)
        return repos

    def get_stats(self) -> dict[str, Any]:
        """Get cache statistics."""
        repos = self.get_repos()
        total_releases = 0

        for repo in repos:
            cache = self.get_repo_cache(repo)
            total_releases += len(cache.checked_releases)

        return {
            "repos": len(repos),
            "total_releases": total_releases,
        }
