"""Publisher service for releasing addon information."""

from pathlib import Path
from typing import Optional

from ..clients.github import GitHubClient
from ..config.settings import GitHubConfig
from ..utils.logging import get_logger

logger = get_logger("services.publisher")


class PublisherService:
    """Service for publishing addon information to GitHub releases."""

    def __init__(self, github_client: GitHubClient, config: GitHubConfig):
        """Initialize publisher service.

        Args:
            github_client: GitHub API client.
            config: GitHub configuration.
        """
        self.github = github_client
        self.config = config

    def publish(self, output_file: Path) -> bool:
        """Publish addon info file to GitHub release.

        Args:
            output_file: Path to addon_infos.json file.

        Returns:
            True if successful.
        """
        if not self.config.owner or not self.config.repo_name:
            logger.error("GitHub repository not configured")
            return False

        if not output_file.exists():
            logger.error(f"Output file not found: {output_file}")
            return False

        owner = self.config.owner
        repo = self.config.repo_name

        # Clean up old releases and tags
        logger.info("Cleaning up old releases and tags...")
        self.github.delete_old_releases(owner, repo, keep_count=2)
        self.github.delete_old_tags(owner, repo, keep_count=2)

        # Create new release
        logger.info("Creating new release...")
        release_id = self.github.create_release(owner, repo)
        if not release_id:
            logger.error("Failed to create release")
            return False

        # Upload file
        logger.info(f"Uploading {output_file.name}...")
        success = self.github.upload_release_asset(
            owner=owner,
            repo=repo,
            release_id=release_id,
            filename="addon_infos.json",
            filepath=str(output_file),
        )

        if success:
            logger.info("Published successfully")
        else:
            logger.error("Failed to upload release asset")

        return success

    def cleanup_caches(self, keep_count: int = 1) -> None:
        """Clean up old GitHub Actions caches.

        Args:
            keep_count: Number of caches to keep.
        """
        if not self.config.owner or not self.config.repo_name:
            return

        logger.info("Cleaning up old caches...")
        self.github.delete_old_caches(
            self.config.owner,
            self.config.repo_name,
            keep_count=keep_count,
        )

    def report_issue(
        self,
        title: str,
        body: str,
        check_id: Optional[str] = None,
    ) -> bool:
        """Report an issue to GitHub.

        Args:
            title: Issue title.
            body: Issue body.
            check_id: Optional ID for duplicate checking.

        Returns:
            True if successful or skipped as duplicate.
        """
        if not self.config.owner or not self.config.repo_name:
            logger.warning("GitHub repository not configured for issue reporting")
            return False

        return self.github.create_issue(
            owner=self.config.owner,
            repo=self.config.repo_name,
            title=title,
            body=body,
            check_duplicate_id=check_id,
        )
