"""Command-line interface for Zotero addons scraper."""

import argparse
import sys
from pathlib import Path

from .cache.release_cache import ReleaseCache
from .config.settings import ScraperConfig
from .services.cache_builder import ReleaseCacheBuilder
from .services.cache_scraper import CacheScraper
from .utils.logging import setup_logging


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Scrape Zotero addon information from GitHub"
    )

    # Mode options
    parser.add_argument(
        "--build-cache-only",
        action="store_true",
        help="Only build/update release cache, don't generate output",
    )
    parser.add_argument(
        "--skip-build-cache",
        action="store_true",
        help="Skip building cache, only generate output from existing cache",
    )

    # Release cache options
    parser.add_argument(
        "--release-cache-dir",
        type=str,
        default="release_cache",
        help="Release cache directory (default: release_cache)",
    )
    parser.add_argument(
        "--full-rebuild",
        action="store_true",
        help="Rebuild cache from scratch, ignoring existing cache",
    )
    parser.add_argument(
        "--parallel",
        action="store_true",
        help="Build cache in parallel (faster but uses more resources)",
    )
    parser.add_argument(
        "--max-workers",
        type=int,
        default=4,
        help="Max parallel workers for cache building (default: 4)",
    )

    # GitHub options
    parser.add_argument(
        "--github_repository",
        type=str,
        default=None,
        help="GitHub repository (owner/repo) for publishing",
    )
    parser.add_argument(
        "--github_token",
        type=str,
        default=None,
        help="GitHub API token",
    )

    # Input/Output options
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

    # Cache options
    parser.add_argument(
        "--cache_directory",
        type=str,
        default="caches",
        help="XPI download cache directory (default: caches)",
    )
    parser.add_argument(
        "--runtime_xpi_directory",
        type=str,
        default="xpis",
        help="Runtime XPI directory (default: xpis)",
    )

    # Fallback options
    parser.add_argument(
        "--previous_info_urls",
        nargs="+",
        default=[],
        help="URLs to previous addon_infos.json for fallback",
    )

    # Publish options
    parser.add_argument(
        "--create_release",
        type=lambda x: x.lower() in ("true", "1", "yes"),
        default=True,
        help="Create GitHub release (default: True)",
    )

    # Logging
    parser.add_argument(
        "--log_level",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level (default: INFO)",
    )

    return parser.parse_args()


def main() -> int:
    """Main entry point.

    Default flow:
    1. Build/update release cache (parse new releases)
    2. Generate addon_infos.json from cache
    3. Publish to GitHub release (if --create_release)
    """
    args = parse_args()

    # Setup logging
    import logging

    log_level = getattr(logging, args.log_level.upper())
    setup_logging(level=log_level)

    logger = logging.getLogger("zotero_scraper")

    # Validate arguments
    if args.create_release and not args.github_repository:
        logger.error("--github_repository is required when --create_release is True")
        return 1

    # Create configuration
    config = ScraperConfig.from_args(args)

    # Ensure directories exist
    config.cache.cache_dir.mkdir(parents=True, exist_ok=True)
    config.cache.runtime_xpi_dir.mkdir(parents=True, exist_ok=True)

    # Initialize release cache
    release_cache_dir = Path(args.release_cache_dir)
    release_cache = ReleaseCache(release_cache_dir)

    # Step 1: Build/update cache (unless skipped)
    if not args.skip_build_cache:
        logger.info("Step 1: Building/updating release cache...")

        builder = ReleaseCacheBuilder(config, release_cache)

        if config.github.token:
            builder.github.get_rate_limit()

        if args.parallel:
            stats = builder.build_cache_parallel(
                full_rebuild=args.full_rebuild,
                max_workers=args.max_workers,
            )
        else:
            stats = builder.build_cache(
                full_rebuild=args.full_rebuild,
            )

        logger.info(f"Cache build stats: {stats}")

        if args.build_cache_only:
            logger.info("Done! (build-cache-only mode)")
            return 0
    else:
        if not release_cache_dir.exists():
            logger.error(
                f"Release cache directory not found: {release_cache_dir}. "
                "Cannot use --skip-build-cache without existing cache."
            )
            return 1
        logger.info("Step 1: Skipped (using existing cache)")

    # Step 2: Generate addon_infos.json from cache
    logger.info("Step 2: Generating addon_infos.json from cache...")

    scraper = CacheScraper(config, release_cache)

    if config.github.token:
        scraper.github.get_rate_limit()

    addon_infos = scraper.scrape_all()
    logger.info(f"Generated info for {len(addon_infos)} addons")

    # Step 3: Publish to GitHub release (if requested)
    if args.create_release and args.github_repository:
        logger.info("Step 3: Publishing to GitHub release...")
        scraper.publisher.publish(config.output_file)
        scraper.publisher.cleanup_caches(keep_count=1)
    else:
        logger.info("Step 3: Skipped (--create_release is False or no repository)")

    logger.info("Done!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
