"""Command-line interface for Zotero addons scraper."""

import argparse
import sys
from pathlib import Path

from .cache.file_cache import FileCache
from .config.settings import ScraperConfig
from .services.scraper import AddonScraper
from .utils.logging import setup_logging


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Scrape Zotero addon information from GitHub"
    )

    # Required arguments
    parser.add_argument(
        "--github_repository",
        type=str,
        required=True,
        help="GitHub repository (owner/repo)",
    )

    # Optional arguments
    parser.add_argument(
        "--github_token",
        type=str,
        default=None,
        help="GitHub API token",
    )
    parser.add_argument(
        "-i",
        "--input",
        type=str,
        default="addons",
        help="Input addon config directory (default: addons)",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=str,
        default="addon_infos.json",
        help="Output JSON file path (default: addon_infos.json)",
    )
    parser.add_argument(
        "--cache_directory",
        type=str,
        default="caches",
        help="Cache directory (default: caches)",
    )
    parser.add_argument(
        "--cache_lockfile",
        type=str,
        default="caches_lockfile",
        help="Cache lockfile name (default: caches_lockfile)",
    )
    parser.add_argument(
        "--runtime_xpi_directory",
        type=str,
        default="xpis",
        help="Runtime XPI directory (default: xpis)",
    )
    parser.add_argument(
        "--previous_info_urls",
        nargs="+",
        default=[],
        help="URLs to previous addon_infos.json for fallback",
    )
    parser.add_argument(
        "--create_release",
        type=lambda x: x.lower() in ("true", "1", "yes"),
        default=True,
        help="Create GitHub release (default: True)",
    )
    parser.add_argument(
        "--log_level",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level (default: INFO)",
    )

    return parser.parse_args()


def main() -> int:
    """Main entry point."""
    args = parse_args()

    # Setup logging
    import logging

    log_level = getattr(logging, args.log_level.upper())
    setup_logging(level=log_level)

    logger = logging.getLogger("zotero_scraper")

    # Validate arguments
    if not args.github_repository:
        logger.error("--github_repository is required")
        return 1

    # Create configuration
    config = ScraperConfig.from_args(args)

    # Ensure directories exist
    config.cache.cache_dir.mkdir(parents=True, exist_ok=True)
    config.cache.runtime_xpi_dir.mkdir(parents=True, exist_ok=True)

    # Initialize scraper
    scraper = AddonScraper(config)

    # Check rate limit
    if config.github.token:
        scraper.github.get_rate_limit()

    # Run scraper
    logger.info("Starting addon scraper...")
    addon_infos = scraper.scrape_all()
    logger.info(f"Scraped {len(addon_infos)} addons")

    # Publish if requested
    if args.create_release:
        logger.info("Publishing to GitHub release...")
        scraper.publisher.publish(config.output_file)

    # Update cache
    logger.info("Updating cache...")
    cache = FileCache(
        cache_dir=config.cache.cache_dir,
        runtime_dir=config.cache.runtime_xpi_dir,
        lockfile_name=config.cache.lockfile_name,
    )
    cache.update_cache()

    # Clean up old caches
    if config.github.token:
        scraper.publisher.cleanup_caches(keep_count=1)

    logger.info("Done!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
