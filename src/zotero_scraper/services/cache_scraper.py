"""Scraper service that uses release cache to generate output."""

import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Optional

from ..cache.release_cache import CachedRelease, ReleaseCache
from ..clients.github import GitHubClient
from ..config.constants import XPIProxy
from ..config.settings import ScraperConfig
from ..models.addon import AddonInfo, AddonRelease, Author, XpiDownloadUrls
from ..utils.logging import get_logger
from .fallback import FallbackService
from .publisher import PublisherService

logger = get_logger("services.cache_scraper")

# Target Zotero versions to generate releases for
TARGET_ZOTERO_VERSIONS = ["7", "6"]


class CacheScraper:
    """Scraper that uses release cache to generate addon information."""

    def __init__(
        self,
        config: ScraperConfig,
        release_cache: ReleaseCache,
    ):
        """Initialize cache-based scraper.

        Args:
            config: Scraper configuration.
            release_cache: Release cache instance.
        """
        self.config = config
        self.cache = release_cache
        self.github = GitHubClient(config.github)
        self.fallback = FallbackService()
        self.publisher = PublisherService(self.github, config.github)

    def scrape_all(self) -> list[dict[str, Any]]:
        """Generate addon information from cache.

        Returns:
            List of addon info dictionaries.
        """
        repos = self._load_repos_from_input()
        logger.info(f"Generating addon info for {len(repos)} repositories")

        addon_infos: list[AddonInfo] = []

        with ThreadPoolExecutor(max_workers=self.config.max_workers) as executor:
            futures = {
                executor.submit(self._process_repo, repo): repo
                for repo in repos
            }

            for future in as_completed(futures):
                repo = futures[future]
                try:
                    if result := future.result():
                        addon_infos.append(result)
                except Exception as e:
                    logger.error(f"Failed to process {repo}: {e}")

        # Convert to dict
        result = [info.to_dict() for info in addon_infos]

        # Apply fallback from previous versions
        for url in self.config.previous_info_urls:
            result = self.fallback.apply_fallback(result, url)

        # Sort by stars (descending)
        result.sort(key=lambda x: x.get("stars") or 0, reverse=True)

        # Save output
        self._save_output(result)

        return result

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

    def _process_repo(self, repo: str) -> Optional[AddonInfo]:
        """Process a single repository using cache.

        Args:
            repo: Repository in "owner/name" format.

        Returns:
            AddonInfo or None if no valid releases.
        """
        parts = repo.split("/")
        if len(parts) != 2:
            logger.warning(f"Invalid repo format: {repo}")
            return None

        owner, name = parts
        repo_cache = self.cache.get_repo_cache(repo)

        # Find best release for each Zotero version
        releases: list[AddonRelease] = []
        for zotero_version in TARGET_ZOTERO_VERSIONS:
            cached_release = repo_cache.get_best_release_for_zotero(zotero_version)
            if cached_release:
                release = self._cached_to_addon_release(cached_release, zotero_version)
                if release:
                    releases.append(release)

        if not releases:
            logger.debug(f"{repo}: No compatible releases found")
            return None

        # Create AddonInfo
        addon_info = AddonInfo(
            repo=repo,
            releases=releases,
            name=name,
        )

        # Fetch author info
        self._fetch_author_info(addon_info, owner)

        # Fetch repository info
        self._fetch_repo_info(addon_info, owner, name)

        # Use addon info from first release
        first_release = releases[0]
        if first_release.name:
            addon_info.name = first_release.name
        if first_release.description and not addon_info.description:
            addon_info.description = first_release.description

        return addon_info

    def _cached_to_addon_release(
        self, cached: CachedRelease, zotero_version: str
    ) -> Optional[AddonRelease]:
        """Convert CachedRelease to AddonRelease.

        Args:
            cached: Cached release data.
            zotero_version: Target Zotero version.

        Returns:
            AddonRelease or None.
        """
        if not cached.parse_success:
            return None

        xpi_download_url = XpiDownloadUrls(
            github=cached.xpi_download_url,
            ghProxy=XPIProxy.ghproxy_url(cached.xpi_download_url),
            kgithub=XPIProxy.kkgithub_url(cached.xpi_download_url),
        )

        return AddonRelease(
            targetZoteroVersion=zotero_version,
            tagName=cached.tag,
            xpiDownloadUrl=xpi_download_url,
            releaseDate=cached.published_at,
            id=cached.addon_id,
            xpiVersion=cached.addon_version,
            name=cached.addon_name,
            description=cached.addon_description,
            minZoteroVersion=cached.min_zotero_version,
            maxZoteroVersion=cached.max_zotero_version,
        )

    def _fetch_author_info(self, addon_info: AddonInfo, owner: str) -> None:
        """Fetch author info from GitHub."""
        if user_info := self.github.get_user(owner):
            addon_info.author = Author(
                name=user_info.name,
                url=user_info.html_url,
                avatar=user_info.avatar_url,
            )

    def _fetch_repo_info(
        self, addon_info: AddonInfo, owner: str, name: str
    ) -> None:
        """Fetch repository info from GitHub."""
        if repo_info := self.github.get_repo(owner, name):
            if not addon_info.description and repo_info.description:
                addon_info.description = repo_info.description
            addon_info.stars = repo_info.stargazers_count

    def _save_output(self, data: list[dict[str, Any]]) -> None:
        """Save output to file."""
        self.config.output_file.parent.mkdir(parents=True, exist_ok=True)

        with open(self.config.output_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)

        logger.info(f"Saved {len(data)} addons to {self.config.output_file}")
