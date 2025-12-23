"""Core scraper service for fetching addon information."""

import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Optional

from ..clients.downloader import XPIDownloader
from ..clients.github import GitHubClient, ReleaseAsset
from ..config.constants import ContentTypes, XPIProxy
from ..config.settings import ScraperConfig
from ..models.addon import AddonInfo, AddonRelease, Author, XpiDownloadUrls
from ..parsers.xpi_parser import XPIParser
from ..utils.logging import get_logger
from ..utils.version import compare_versions
from .fallback import FallbackService
from .publisher import PublisherService

logger = get_logger("services.scraper")


class AddonScraper:
    """Core service for scraping Zotero addon information."""

    def __init__(self, config: ScraperConfig):
        """Initialize scraper service.

        Args:
            config: Scraper configuration.
        """
        self.config = config
        self.github = GitHubClient(config.github)
        self.downloader = XPIDownloader(config.cache)
        self.xpi_parser = XPIParser()
        self.fallback = FallbackService()
        self.publisher = PublisherService(self.github, config.github)

    def scrape_all(self) -> list[dict[str, Any]]:
        """Scrape all addon information.

        Returns:
            List of addon info dictionaries.
        """
        # Load input configs
        plugins = self._load_input_configs()
        logger.info(f"Loaded {len(plugins)} addon configs")

        # Scrape in parallel
        addon_infos: list[AddonInfo] = []
        with ThreadPoolExecutor(max_workers=self.config.max_workers) as executor:
            futures = {
                executor.submit(self._scrape_addon, plugin): plugin
                for plugin in plugins
            }

            for future in as_completed(futures):
                plugin = futures[future]
                try:
                    if result := future.result():
                        addon_infos.append(result)
                except Exception as e:
                    logger.error(f"Failed to scrape {plugin.repo}: {e}")

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

    def _load_input_configs(self) -> list[AddonInfo]:
        """Load addon configs from input directory."""
        plugins: list[AddonInfo] = []

        if not self.config.input_dir.exists():
            logger.error(f"Input directory not found: {self.config.input_dir}")
            return plugins

        for config_file in self.config.input_dir.glob("*.json"):
            try:
                with open(config_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                plugins.append(AddonInfo.from_dict(data))
            except Exception as e:
                logger.error(f"Failed to load {config_file}: {e}")

        return plugins

    def _scrape_addon(self, plugin: AddonInfo) -> Optional[AddonInfo]:
        """Scrape information for a single addon."""
        if not plugin.owner or not plugin.releases:
            logger.warning(f"Invalid plugin config: {plugin.repo}")
            return None

        plugin.name = plugin.repository

        # Fetch author info
        self._fetch_author_info(plugin)

        # Fetch repository info
        self._fetch_repo_info(plugin)

        # Process releases
        valid_releases: list[AddonRelease] = []
        invalid_releases: list[AddonRelease] = []

        for release in plugin.releases:
            processed = self._process_release(plugin, release)
            if processed:
                if processed.get("valid"):
                    valid_releases.append(release)
                else:
                    invalid_releases.append(release)

        # Report invalid releases
        for invalid_release in invalid_releases:
            logger.warning(
                f"{plugin.repo} invalid for Zotero {invalid_release.zotero_check_version}"
            )
            self.publisher.report_issue(
                title=f"Invalid {plugin.repo} xpi with zotero version {invalid_release.zotero_check_version}",
                body=(
                    f"xpi: https://github.com/{plugin.repo} @{invalid_release.tagName}\n"
                    f"min zotero Version: {invalid_release.minZoteroVersion}\n"
                    f"max Zotero version: {invalid_release.maxZoteroVersion}\n"
                    f"expect Zotero version: {invalid_release.zotero_check_version}\n"
                ),
                check_id=f"Target zotero version not match: {plugin.repo}+{invalid_release.tagName}@{invalid_release.targetZoteroVersion}",
            )

        plugin.releases = valid_releases
        return plugin if valid_releases else None

    def _fetch_author_info(self, plugin: AddonInfo) -> None:
        """Fetch author info from GitHub."""
        if user_info := self.github.get_user(plugin.owner):
            plugin.author = Author(
                name=user_info.name,
                url=user_info.html_url,
                avatar=user_info.avatar_url,
            )

    def _fetch_repo_info(self, plugin: AddonInfo) -> None:
        """Fetch repository info from GitHub."""
        if repo_info := self.github.get_repo(plugin.owner, plugin.repository):
            if not plugin.description and repo_info.description:
                plugin.description = repo_info.description
            plugin.stars = repo_info.stargazers_count

    def _process_release(
        self, plugin: AddonInfo, release: AddonRelease
    ) -> Optional[dict[str, Any]]:
        """Process a single release.

        Returns:
            Dict with 'valid' key indicating compatibility, or None if failed.
        """
        if not release.tagName:
            return None

        # Get release info from GitHub
        release_info = self.github.get_release(
            plugin.owner, plugin.repository, release.tagName
        )
        if not release_info:
            return None

        release.tagName = release_info.tag_name

        # Find XPI asset
        xpi_asset = self._find_xpi_asset(release_info.assets)
        if not xpi_asset:
            logger.warning(f"No XPI found for {plugin.repo}@{release.tagName}")
            return None

        # Set download URLs
        release.xpiDownloadUrl = XpiDownloadUrls(
            github=xpi_asset.browser_download_url,
            ghProxy=XPIProxy.ghproxy_url(xpi_asset.browser_download_url),
            kgithub=XPIProxy.kkgithub_url(xpi_asset.browser_download_url),
        )
        release.releaseDate = xpi_asset.updated_at

        # Download and parse XPI
        xpi_filename = (
            f"{plugin.owner}#{plugin.repository}+{release.tagName}@{xpi_asset.id}.xpi"
        )

        # Determine priority sources based on Zotero version
        priority_sources = ["rdf", "json"]
        if release.targetZoteroVersion == "6":
            priority_sources = ["json", "rdf"]

        xpi_path = self.downloader.download(
            xpi_asset.browser_download_url, xpi_filename
        )

        if not xpi_path:
            self.publisher.report_issue(
                title=f"Parse {plugin.repo} addon details failed",
                body=f"xpi: https://github.com/{plugin.repo} @{release.tagName} on {release.targetZoteroVersion}\n",
                check_id=f"Parse details failed: {plugin.repo}+{release.tagName}@{release.targetZoteroVersion}",
            )
            return None

        details = self.xpi_parser.parse(xpi_path, priority_sources)

        if details:
            # Update release with XPI details
            if details.id:
                release.id = details.id
            if details.name:
                release.name = details.name
            if details.version:
                release.xpiVersion = details.version
            if details.description:
                release.description = details.description
            release.minZoteroVersion = details.min_version
            release.maxZoteroVersion = details.max_version

            # Check for updates via update_url
            self._check_for_updates(plugin, release, details, priority_sources)

            # Validate compatibility
            if not details.check_compatible(release.zotero_check_version):
                return {"valid": False}

            # Report if version info is missing
            if (
                not release.minZoteroVersion
                or release.minZoteroVersion == "*"
            ) and (
                not release.maxZoteroVersion
                or release.maxZoteroVersion == "*"
            ):
                self.publisher.report_issue(
                    title=f"Parse {plugin.repo} of zotero version failed",
                    body=f"xpi: https://github.com/{plugin.repo} @{release.tagName} on {release.targetZoteroVersion}\n",
                    check_id=f"Parse min/max version failed: {plugin.repo}+{release.tagName}@{release.targetZoteroVersion}",
                )

            return {"valid": True}
        else:
            self.publisher.report_issue(
                title=f"Parse {plugin.repo} addon details failed",
                body=f"xpi: https://github.com/{plugin.repo} @{release.tagName} on {release.targetZoteroVersion}\n",
                check_id=f"Parse details failed: {plugin.repo}+{release.tagName}@{release.targetZoteroVersion}",
            )
            return None

    def _find_xpi_asset(
        self, assets: list[ReleaseAsset]
    ) -> Optional[ReleaseAsset]:
        """Find XPI asset from release assets."""
        # Sort by updated_at descending
        sorted_assets = sorted(
            assets, key=lambda a: a.updated_at, reverse=True
        )

        # First try XPI content type
        for asset in sorted_assets:
            if asset.content_type == ContentTypes.XPI:
                return asset

        # Fallback to ZIP content type
        for asset in sorted_assets:
            if asset.content_type == ContentTypes.ZIP:
                return asset

        return None

    def _check_for_updates(
        self,
        plugin: AddonInfo,
        release: AddonRelease,
        details: Any,
        priority_sources: list[str],
    ) -> None:
        """Check for updates via update_url."""
        if not details.update_url or not details.id or not details.version:
            return

        try:
            import requests

            response = requests.get(details.update_url, timeout=30)
            if response.status_code != 200:
                return

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

                update_filename = (
                    f"{plugin.owner}#{plugin.repository}+update{details.version}.xpi"
                )
                update_path = self.downloader.download(xpi_url, update_filename)

                if update_path:
                    update_details = self.xpi_parser.parse(
                        update_path, priority_sources
                    )
                    if (
                        update_details
                        and update_details.id
                        and update_details.check_compatible(
                            release.zotero_check_version
                        )
                    ):
                        # Update release with newer version
                        if update_details.id:
                            release.id = update_details.id
                        if update_details.name:
                            release.name = update_details.name
                        if update_details.version:
                            release.xpiVersion = update_details.version
                        if update_details.description:
                            release.description = update_details.description
                        release.minZoteroVersion = update_details.min_version
                        release.maxZoteroVersion = update_details.max_version
                        release.xpiDownloadUrl = XpiDownloadUrls(github=xpi_url)
                        break

        except Exception as e:
            logger.debug(f"Failed to check updates for {plugin.repo}: {e}")

    def _save_output(self, data: list[dict[str, Any]]) -> None:
        """Save output to file."""
        self.config.output_file.parent.mkdir(parents=True, exist_ok=True)

        with open(self.config.output_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)

        logger.info(f"Saved {len(data)} addons to {self.config.output_file}")
