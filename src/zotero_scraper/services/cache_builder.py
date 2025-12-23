"""Service for building and updating release cache."""

import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Optional

import requests

from ..cache.release_cache import CachedRelease, ReleaseCache
from ..clients.downloader import XPIDownloader
from ..clients.github import GitHubClient, ReleaseAsset
from ..config.constants import ContentTypes
from ..config.settings import ScraperConfig
from ..parsers.xpi_parser import XPIParser
from ..utils.logging import get_logger
from ..utils.version import compare_versions

logger = get_logger("services.cache_builder")


class ReleaseCacheBuilder:
    """Service for building release cache by parsing all releases."""

    def __init__(
        self,
        config: ScraperConfig,
        release_cache: ReleaseCache,
    ):
        """Initialize cache builder.

        Args:
            config: Scraper configuration.
            release_cache: Release cache instance.
        """
        self.config = config
        self.cache = release_cache
        self.github = GitHubClient(config.github)
        self.downloader = XPIDownloader(config.cache)
        self.xpi_parser = XPIParser()

    def build_cache(
        self,
        repos: Optional[list[str]] = None,
        full_rebuild: bool = False,
        max_releases_per_repo: Optional[int] = None,
    ) -> dict[str, Any]:
        """Build or update release cache for all repositories.

        Args:
            repos: Optional list of repos to process. If None, loads from input dir.
            full_rebuild: If True, ignore existing cache and rebuild everything.
            max_releases_per_repo: Limit releases to process per repo (for testing).

        Returns:
            Statistics about the build process.
        """
        if repos is None:
            repos = self._load_repos_from_input()

        logger.info(f"Building cache for {len(repos)} repositories")

        stats = {
            "repos_processed": 0,
            "repos_failed": 0,
            "new_releases_parsed": 0,
            "releases_deleted": 0,
            "errors": [],
        }

        for i, repo in enumerate(repos, 1):
            logger.info(f"[{i}/{len(repos)}] Processing {repo}")

            try:
                result = self._process_repo(
                    repo,
                    full_rebuild=full_rebuild,
                    max_releases=max_releases_per_repo,
                )
                stats["repos_processed"] += 1
                stats["new_releases_parsed"] += result.get("new_releases", 0)
                stats["releases_deleted"] += result.get("deleted_releases", 0)
            except Exception as e:
                logger.error(f"Failed to process {repo}: {e}")
                stats["repos_failed"] += 1
                stats["errors"].append({"repo": repo, "error": str(e)})

            # Save cache after each repo (immediate persistence)
            self.cache.save()

        # Final save
        self.cache.save()

        logger.info(
            f"Cache build complete: {stats['repos_processed']} repos, "
            f"{stats['new_releases_parsed']} new releases, "
            f"{stats['releases_deleted']} deleted releases"
        )

        return stats

    def build_cache_parallel(
        self,
        repos: Optional[list[str]] = None,
        full_rebuild: bool = False,
        max_releases_per_repo: Optional[int] = None,
        max_workers: int = 4,
    ) -> dict[str, Any]:
        """Build cache in parallel (faster but uses more resources).

        Args:
            repos: Optional list of repos to process.
            full_rebuild: If True, ignore existing cache.
            max_releases_per_repo: Limit releases per repo.
            max_workers: Number of parallel workers.

        Returns:
            Statistics about the build process.
        """
        if repos is None:
            repos = self._load_repos_from_input()

        logger.info(f"Building cache for {len(repos)} repos with {max_workers} workers")

        stats = {
            "repos_processed": 0,
            "repos_failed": 0,
            "new_releases_parsed": 0,
            "releases_deleted": 0,
            "errors": [],
        }

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(
                    self._process_repo,
                    repo,
                    full_rebuild=full_rebuild,
                    max_releases=max_releases_per_repo,
                ): repo
                for repo in repos
            }

            for future in as_completed(futures):
                repo = futures[future]
                try:
                    result = future.result()
                    stats["repos_processed"] += 1
                    stats["new_releases_parsed"] += result.get("new_releases", 0)
                    stats["releases_deleted"] += result.get("deleted_releases", 0)
                    logger.info(
                        f"[{stats['repos_processed']}/{len(repos)}] "
                        f"Completed {repo}: {result.get('new_releases', 0)} new releases"
                    )
                except Exception as e:
                    logger.error(f"Failed to process {repo}: {e}")
                    stats["repos_failed"] += 1
                    stats["errors"].append({"repo": repo, "error": str(e)})

        self.cache.save()

        logger.info(
            f"Cache build complete: {stats['repos_processed']} repos, "
            f"{stats['new_releases_parsed']} new releases"
        )

        return stats

    def _load_repos_from_input(self) -> list[str]:
        """Load repository list from input directory."""
        repos = []

        if not self.config.input_dir.exists():
            logger.error(f"Input directory not found: {self.config.input_dir}")
            return repos

        for config_file in self.config.input_dir.glob("*.json"):
            try:
                with open(config_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if repo := data.get("repo"):
                    repos.append(repo)
            except Exception as e:
                logger.error(f"Failed to load {config_file}: {e}")

        return repos

    def _process_repo(
        self,
        repo: str,
        full_rebuild: bool = False,
        max_releases: Optional[int] = None,
    ) -> dict[str, int]:
        """Process a single repository.

        Args:
            repo: Repository in "owner/name" format.
            full_rebuild: If True, reprocess all releases.
            max_releases: Limit number of releases to process.

        Returns:
            Statistics dict with new_releases and deleted_releases counts.
        """
        parts = repo.split("/")
        if len(parts) != 2:
            raise ValueError(f"Invalid repo format: {repo}")

        owner, name = parts

        # Get all releases from GitHub
        releases = self.github.get_releases(owner, name)
        if not releases:
            logger.warning(f"No releases found for {repo}")
            return {"new_releases": 0, "deleted_releases": 0}

        # Get current tags from GitHub
        current_tags = {r.get("tag_name") for r in releases if r.get("tag_name")}

        # Sync cache - remove deleted releases
        deleted_tags = self.cache.sync_with_github(repo, current_tags)
        if deleted_tags:
            logger.info(f"{repo}: Removed {len(deleted_tags)} deleted releases: {deleted_tags}")

        # Get tags to process
        if full_rebuild:
            tags_to_process = list(current_tags)
        else:
            tags_to_process = self.cache.get_unchecked_tags(repo, list(current_tags))

        if max_releases:
            tags_to_process = tags_to_process[:max_releases]

        if not tags_to_process:
            logger.debug(f"{repo}: No new releases to process")
            self.cache.update_repo_checked_time(repo)
            return {"new_releases": 0, "deleted_releases": len(deleted_tags)}

        logger.info(f"{repo}: Processing {len(tags_to_process)} new releases")

        # Process each new release
        new_count = 0
        for release_data in releases:
            tag = release_data.get("tag_name")
            if tag not in tags_to_process:
                continue

            cached = self._parse_release(repo, release_data)
            if cached:
                self.cache.add_release(repo, cached)
                new_count += 1
                logger.debug(f"{repo}@{tag}: Parsed successfully")
            else:
                # Still add to cache with parse_success=False to avoid re-parsing
                cached = CachedRelease(
                    tag=tag,
                    published_at=release_data.get("published_at", ""),
                    xpi_asset_id=0,
                    xpi_name="",
                    xpi_download_url="",
                    parse_success=False,
                    parse_error="No XPI found or parse failed",
                )
                self.cache.add_release(repo, cached)
                logger.debug(f"{repo}@{tag}: Parse failed, cached as failed")

        self.cache.update_repo_checked_time(repo)

        return {"new_releases": new_count, "deleted_releases": len(deleted_tags)}

    def _parse_release(
        self, repo: str, release_data: dict[str, Any]
    ) -> Optional[CachedRelease]:
        """Parse a single release and return CachedRelease.

        Args:
            repo: Repository in "owner/name" format.
            release_data: Release data from GitHub API.

        Returns:
            CachedRelease or None if no XPI found.
        """
        tag = release_data.get("tag_name", "")
        published_at = release_data.get("published_at", "")
        assets = release_data.get("assets", [])

        # Find XPI asset
        xpi_asset = self._find_xpi_asset(assets)
        if not xpi_asset:
            return None

        xpi_url = xpi_asset.get("browser_download_url", "")
        xpi_name = xpi_asset.get("name", "")
        xpi_id = xpi_asset.get("id", 0)

        # Download XPI
        owner, name = repo.split("/")
        filename = f"{owner}#{name}+{tag}@{xpi_id}.xpi"
        xpi_path = self.downloader.download(xpi_url, filename)

        if not xpi_path:
            return CachedRelease(
                tag=tag,
                published_at=published_at,
                xpi_asset_id=xpi_id,
                xpi_name=xpi_name,
                xpi_download_url=xpi_url,
                parse_success=False,
                parse_error="Download failed",
            )

        # Parse XPI
        details = self.xpi_parser.parse(xpi_path)

        if not details or not details.id:
            return CachedRelease(
                tag=tag,
                published_at=published_at,
                xpi_asset_id=xpi_id,
                xpi_name=xpi_name,
                xpi_download_url=xpi_url,
                parse_success=False,
                parse_error="Parse failed or no addon ID",
            )

        # Check for updates via update_url
        updated = self._check_for_updates(repo, details)
        if updated:
            details = updated["details"]
            xpi_url = updated["xpi_url"]

        return CachedRelease(
            tag=tag,
            published_at=published_at,
            xpi_asset_id=xpi_id,
            xpi_name=xpi_name,
            xpi_download_url=xpi_url,
            addon_id=details.id,
            addon_name=details.name,
            addon_version=details.version,
            addon_description=details.description,
            min_zotero_version=details.min_version,
            max_zotero_version=details.max_version,
            parse_success=True,
        )

    def _find_xpi_asset(self, assets: list[dict]) -> Optional[dict]:
        """Find XPI asset from release assets."""
        # Sort by updated_at descending
        sorted_assets = sorted(
            assets, key=lambda a: a.get("updated_at", ""), reverse=True
        )

        # First try XPI content type
        for asset in sorted_assets:
            if asset.get("content_type") == ContentTypes.XPI:
                return asset

        # Fallback to ZIP content type
        for asset in sorted_assets:
            if asset.get("content_type") == ContentTypes.ZIP:
                return asset

        # Fallback to .xpi extension
        for asset in sorted_assets:
            if asset.get("name", "").endswith(".xpi"):
                return asset

        return None

    def _check_for_updates(
        self, repo: str, details: Any
    ) -> Optional[dict[str, Any]]:
        """Check for updates via update_url.

        Args:
            repo: Repository in "owner/name" format.
            details: Parsed XPI details with update_url.

        Returns:
            Dict with 'details' and 'xpi_url' if update found, None otherwise.
        """
        if not details.update_url or not details.id or not details.version:
            return None

        try:
            response = requests.get(details.update_url, timeout=30)
            if response.status_code != 200:
                return None

            update_info = response.json()
            updates = (
                update_info.get("addons", {})
                .get(details.id, {})
                .get("updates", [])
            )

            # Find newer versions
            newer_versions = [
                u
                for u in updates
                if compare_versions(u.get("version", "0"), details.version) > 0
            ]

            for update in newer_versions:
                xpi_url = update.get("update_link")
                if not xpi_url:
                    continue

                owner, name = repo.split("/")
                update_filename = f"{owner}#{name}+update{details.version}.xpi"
                update_path = self.downloader.download(xpi_url, update_filename)

                if update_path:
                    update_details = self.xpi_parser.parse(update_path)
                    if update_details and update_details.id:
                        logger.info(
                            f"{repo}: Found update via update_url: "
                            f"{details.version} -> {update_details.version}"
                        )
                        return {
                            "details": update_details,
                            "xpi_url": xpi_url,
                        }

        except Exception as e:
            logger.debug(f"Failed to check updates for {repo}: {e}")

        return None
