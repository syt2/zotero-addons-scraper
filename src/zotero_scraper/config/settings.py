"""Configuration settings for the Zotero addons scraper."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional


@dataclass(frozen=True)
class GitHubConfig:
    """GitHub API configuration."""

    token: Optional[str] = None
    repository: str = ""
    api_version: str = "2022-11-28"
    timeout: int = 30
    max_retries: int = 3
    retry_delay: float = 1.0

    @property
    def owner(self) -> Optional[str]:
        """Get repository owner."""
        parts = self.repository.split("/")
        return parts[0] if len(parts) == 2 else None

    @property
    def repo_name(self) -> Optional[str]:
        """Get repository name."""
        parts = self.repository.split("/")
        return parts[1] if len(parts) == 2 else None


@dataclass(frozen=True)
class CacheConfig:
    """Cache configuration."""

    cache_dir: Path = field(default_factory=lambda: Path("caches"))
    runtime_xpi_dir: Path = field(default_factory=lambda: Path("xpis"))
    lockfile_name: str = "caches_lockfile"


@dataclass(frozen=True)
class ScraperConfig:
    """Main scraper configuration."""

    input_dir: Path = field(default_factory=lambda: Path("addons"))
    output_file: Path = field(default_factory=lambda: Path("addon_infos.json"))
    github: GitHubConfig = field(default_factory=GitHubConfig)
    cache: CacheConfig = field(default_factory=CacheConfig)
    previous_info_urls: list[str] = field(default_factory=list)
    create_release: bool = True
    max_workers: int = 10

    @classmethod
    def from_args(cls, args: Any) -> "ScraperConfig":
        """Create configuration from argparse namespace.

        Args:
            args: Parsed command line arguments.

        Returns:
            ScraperConfig instance.
        """
        return cls(
            input_dir=Path(args.input),
            output_file=Path(args.output),
            github=GitHubConfig(
                token=args.github_token,
                repository=args.github_repository or "",
            ),
            cache=CacheConfig(
                cache_dir=Path(args.cache_directory),
                runtime_xpi_dir=Path(args.runtime_xpi_directory),
                lockfile_name=args.cache_lockfile,
            ),
            previous_info_urls=args.previous_info_urls or [],
            create_release=args.create_release,
        )
