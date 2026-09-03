"""Service for building and updating release cache."""

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
            "refreshed_releases": 0,
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
                stats["refreshed_releases"] += result.get(
                    "refreshed_releases", 0
                )
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
            f"{stats['refreshed_releases']} refreshed releases"
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
            "refreshed_releases": 0,
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
                    new_count = result.get("new_releases", 0)
                    refreshed_count = result.get("refreshed_releases", 0)
                    stats["repos_processed"] += 1
                    stats["new_releases_parsed"] += new_count
                    stats["refreshed_releases"] += refreshed_count
                    logger.info(
                        f"[{stats['repos_processed']}/{len(repos)}] "
                        f"Completed {repo}: {new_count} new, "
                        f"{refreshed_count} refreshed releases"
                    )
                except Exception as e:
                    logger.error(f"Failed to process {repo}: {e}")
                    stats["repos_failed"] += 1
                    stats["errors"].append({"repo": repo, "error": str(e)})

        self.cache.save()

        logger.info(
            f"Cache build complete: {stats['repos_processed']} repos, "
            f"{stats['new_releases_parsed']} new releases, "
            f"{stats['refreshed_releases']} refreshed releases"
        )

        return stats

    def _load_repos_from_input(self) -> list[str]:
        """Load repository list from input directory.

        Reads repo names from filenames in format: owner@repo
        Converts to owner/repo format.
        """
        repos = []

        if not self.config.input_dir.exists():
            logger.error(f"Input directory not found: {self.config.input_dir}")
            return repos

        for config_file in self.config.input_dir.iterdir():
            if config_file.is_file():
                # Parse repo from filename: owner@repo -> owner/repo
                filename = config_file.name
                if "@" in filename:
                    repo = filename.replace("@", "/")
                    repos.append(repo)

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
            Statistics dict with new and refreshed release counts.
        """
        parts = repo.split("/")
        if len(parts) != 2:
            raise ValueError(f"Invalid repo format: {repo}")

        owner, name = parts

        # Get all releases from GitHub
        self.cache.clear_observed_release_tags(repo)
        releases = self.github.get_releases(owner, name)
        if releases is None:
            logger.warning(f"Failed to retrieve releases for {repo}")
            return {"new_releases": 0, "refreshed_releases": 0}

        # GitHub returns at most one release page. Remember those tags so output
        # generation can verify a selected cached tag only when it was not seen.
        current_tags: set[str] = {
            release["tag_name"] for release in releases
        }
        self.cache.set_observed_release_tags(repo, current_tags)
        self._remove_missing_releases(repo, owner, name, current_tags, releases)

        # Get tags to process
        tags_to_process: list[str]
        if full_rebuild:
            tags_to_process = list(current_tags)
        else:
            tags_to_process = self.cache.get_unchecked_tags(repo, list(current_tags))
            changed_asset_tags = self._get_changed_asset_tags(repo, releases)
            tags_to_process.extend(
                tag for tag in changed_asset_tags if tag not in tags_to_process
            )

        if max_releases:
            tags_to_process = tags_to_process[:max_releases]

        if not tags_to_process:
            logger.debug(f"{repo}: No new or changed releases to process")
            # Check latest release's update_url for updates
            update_found = self._check_latest_release_update_url(repo)
            if update_found:
                self.cache.update_repo_checked_time(repo)
            return {
                "new_releases": 0,
                "refreshed_releases": 0,
                "update_url_updated": update_found,
            }

        logger.info(f"{repo}: Processing {len(tags_to_process)} releases")

        # Process each new or changed release
        new_count = 0
        refreshed_count = 0
        repo_cache = self.cache.get_repo_cache(repo)
        for release_data in releases:
            tag = release_data.get("tag_name")
            if not isinstance(tag, str) or tag not in tags_to_process:
                continue

            was_cached = repo_cache.get_release_by_tag(tag) is not None
            cached = self._parse_release(repo, release_data)
            if cached:
                self.cache.add_release(repo, cached)
                if was_cached:
                    refreshed_count += 1
                else:
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
                if was_cached:
                    refreshed_count += 1
                logger.debug(f"{repo}@{tag}: Parse failed, cached as failed")

        # Check latest release's update_url for updates
        update_found = self._check_latest_release_update_url(repo)

        # Only update last_checked if there were actual changes
        if new_count > 0 or refreshed_count > 0 or update_found:
            self.cache.update_repo_checked_time(repo)

        return {
            "new_releases": new_count,
            "refreshed_releases": refreshed_count,
            "update_url_updated": update_found,
        }

    def _get_changed_asset_tags(
        self,
        repo: str,
        releases: list[dict[str, Any]],
    ) -> list[str]:
        """Return cached tags whose selected XPI asset has changed."""
        repo_cache = self.cache.get_repo_cache(repo)
        changed_tags = []

        for release_data in releases:
            tag = release_data.get("tag_name")
            if not isinstance(tag, str):
                continue

            cached = repo_cache.get_release_by_tag(tag)
            if cached is None:
                continue

            xpi_asset = self._find_xpi_asset(release_data.get("assets", []))
            current_asset_id = xpi_asset.get("id", 0) if xpi_asset else 0
            if current_asset_id != cached.xpi_asset_id:
                changed_tags.append(tag)
                logger.info(
                    f"{repo}@{tag}: XPI asset changed "
                    f"({cached.xpi_asset_id} -> {current_asset_id})"
                )

        return changed_tags

    def _remove_missing_releases(
        self,
        repo: str,
        owner: str,
        name: str,
        current_tags: set[str],
        releases: list[dict[str, Any]],
    ) -> None:
        """Confirm missing cached tags that could belong to the observed page.

        For a non-empty page, its oldest valid publication time bounds the
        candidates. An empty page has no boundary, so every cached tag is
        checked. Only an exact tag endpoint's 404 authorizes removal.
        """
        repo_cache = self.cache.get_repo_cache(repo)
        if not releases:
            candidates = {
                cached.tag
                for cached in repo_cache.checked_releases
                if isinstance(cached.tag, str) and cached.tag
            }
            self._remove_confirmed_deleted_releases(repo, owner, name, candidates)
            return

        published_times = []
        for release in releases:
            published_at = release.get("published_at")
            if isinstance(published_at, str) and published_at:
                published_times.append(published_at)
        if not published_times:
            return

        cutoff = min(published_times)
        candidates = {
            cached.tag
            for cached in repo_cache.checked_releases
            if cached.tag not in current_tags
            and isinstance(cached.published_at, str)
            and cached.published_at >= cutoff
        }
        self._remove_confirmed_deleted_releases(repo, owner, name, candidates)

    def _remove_confirmed_deleted_releases(
        self,
        repo: str,
        owner: str,
        name: str,
        tags: set[str],
    ) -> list[str]:
        """Remove tags only after their individual GitHub endpoint returns 404."""
        deleted_tags = set()
        for tag in sorted(tags):
            if self.github.release_exists(owner, name, tag) is False:
                deleted_tags.add(tag)
        if not deleted_tags:
            return []

        removed = self.cache.remove_releases(repo, deleted_tags)
        logger.info(f"{repo}: Removed {len(removed)} confirmed deleted releases")
        return removed

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
        safe_tag = tag.replace("/", "_")
        filename = f"{owner}#{name}+{safe_tag}@{xpi_id}.xpi"
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
            update_url=details.update_url,
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

    def _check_latest_release_update_url(self, repo: str) -> bool:
        """Check latest cached release's update_url for newer versions.

        Args:
            repo: Repository in "owner/name" format.

        Returns:
            True if an update was found and cache was updated.
        """
        repo_cache = self.cache.get_repo_cache(repo)
        latest = repo_cache.get_latest_release()

        if not latest or not latest.parse_success:
            return False

        if not latest.update_url or not latest.addon_id or not latest.addon_version:
            return False

        try:
            response = requests.get(latest.update_url, timeout=30)
            if response.status_code != 200:
                return False

            update_info = response.json()
            updates = (
                update_info.get("addons", {})
                .get(latest.addon_id, {})
                .get("updates", [])
            )

            # Find newer versions
            newer_versions = [
                u
                for u in updates
                if compare_versions(u.get("version", "0"), latest.addon_version) > 0
            ]

            if not newer_versions:
                return False

            owner, name = repo.split("/")

            for update in newer_versions:
                xpi_url = update.get("update_link")
                if not xpi_url:
                    continue

                update_filename = f"{owner}#{name}+update_check_{latest.addon_version}.xpi"
                update_path = self.downloader.download(xpi_url, update_filename)

                if update_path:
                    update_details = self.xpi_parser.parse(update_path)
                    if update_details and update_details.id:
                        logger.info(
                            f"{repo}: Found update via update_url: "
                            f"{latest.addon_version} -> {update_details.version}"
                        )

                        # Update the cached release with new info
                        latest.addon_version = update_details.version
                        latest.addon_name = update_details.name or latest.addon_name
                        latest.addon_description = update_details.description or latest.addon_description
                        latest.min_zotero_version = update_details.min_version
                        latest.max_zotero_version = update_details.max_version
                        latest.xpi_download_url = xpi_url
                        latest.update_url = update_details.update_url or latest.update_url

                        # Mark repo as dirty
                        self.cache.add_release(repo, latest)
                        return True

        except Exception as e:
            logger.debug(f"Failed to check update_url for {repo}: {e}")

        return False
