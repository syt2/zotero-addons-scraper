"""Publisher service for releasing addon information."""

from collections.abc import Iterable
from pathlib import Path

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

    def publish(
        self,
        output_file: Path,
        version_output_files: Iterable[Path] | None = None,
    ) -> bool:
        """Publish addon info files to a GitHub release.

        Args:
            output_file: Path to the complete addon_infos.json file.
            version_output_files: Additional per-Zotero-version info files.

        Returns:
            True if every file was uploaded successfully.
        """
        if not self.config.owner or not self.config.repo_name:
            logger.error("GitHub repository not configured")
            return False

        output_files = [output_file, *(version_output_files or [])]
        missing_files = [path for path in output_files if not path.exists()]
        if missing_files:
            for path in missing_files:
                logger.error(f"Output file not found: {path}")
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

        # Upload complete and per-version files
        success = True
        for path in output_files:
            logger.info(f"Uploading {path.name}...")
            uploaded = self.github.upload_release_asset(
                owner=owner,
                repo=repo,
                release_id=release_id,
                filename=path.name,
                filepath=str(path),
            )
            if not uploaded:
                logger.error(f"Failed to upload release asset {path.name}")
                success = False

        if success:
            logger.info("Published successfully")

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
        check_id: str | None = None,
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
