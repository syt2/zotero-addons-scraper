"""Resolve the hosting platform of a configured addon repository.

A repository entry opts into GitLab by setting "repo_url" in its
``addons/<owner>@<repo>`` config file to the project web URL, for example
``https://jihulab.com/cislunarspace/bibtex-clean``. Entries without
``repo_url`` (or with a github.com URL) keep using the GitHub pipeline.
"""

import json
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlsplit

from ..clients.github import GitHubClient, RepoInfo, UserInfo
from ..clients.gitlab import GitLabClient
from ..config.settings import ScraperConfig
from ..utils.logging import get_logger

logger = get_logger("services.source")

GITHUB_HOST = "github.com"


@dataclass(frozen=True)
class RepoSource:
    """Where a configured addon repository is hosted."""

    repo: str
    platform: str  # "github" or "gitlab"
    host: str = ""  # GitLab instance host, e.g. "jihulab.com"
    path: str = ""  # Project path on the platform, e.g. "group/project"

    @property
    def is_gitlab(self) -> bool:
        """Whether the repository is hosted on a GitLab instance."""
        return self.platform == "gitlab"

    @property
    def owner(self) -> str:
        """First path segment of the cache key."""
        return self.repo.split("/")[0]


class SourceClient:
    """Platform-agnostic client covering GitHub and GitLab repositories."""

    def __init__(self, config: ScraperConfig, github: GitHubClient):
        """Initialize source client.

        Args:
            config: Scraper configuration.
            github: Shared GitHub client (also used for publishing).
        """
        self.config = config
        self.github = github
        self.gitlab = GitLabClient(config.gitlab)
        self._sources: dict[str, RepoSource] = {}

    def get(self, repo: str) -> RepoSource:
        """Resolve the hosting source of a repository."""
        if repo not in self._sources:
            self._sources[repo] = self._resolve(repo)
        return self._sources[repo]

    def get_releases(self, source: RepoSource):
        """Fetch releases for a source in the GitHub API shape."""
        if source.is_gitlab:
            return self.gitlab.get_releases(source.host, source.path)
        owner, name = source.repo.split("/")
        return self.github.get_releases(owner, name)

    def release_exists(self, source: RepoSource, tag: str) -> Optional[bool]:
        """Check whether a release tag exists on the hosting platform."""
        if source.is_gitlab:
            return self.gitlab.release_exists(source.host, source.path, tag)
        owner, name = source.repo.split("/")
        return self.github.release_exists(owner, name, tag)

    def get_author(self, source: RepoSource) -> Optional[UserInfo]:
        """Fetch author (user or group) information for a source."""
        if source.is_gitlab:
            return self.gitlab.get_namespace(source.host, source.owner)
        return self.github.get_user(source.owner)

    def get_repo_info(self, source: RepoSource) -> Optional[RepoInfo]:
        """Fetch repository information for a source."""
        if source.is_gitlab:
            return self.gitlab.get_project(source.host, source.path)
        owner, name = source.repo.split("/")
        return self.github.get_repo(owner, name)

    def _resolve(self, repo: str) -> RepoSource:
        github_source = RepoSource(repo=repo, platform="github", path=repo)
        repo_url = self._load_repo_url(repo)
        if not repo_url:
            return github_source

        parts = urlsplit(repo_url)
        host = (parts.hostname or "").lower()
        project_path = parts.path.strip("/")
        if not host or not project_path:
            logger.warning(f"{repo}: invalid repo_url {repo_url!r}, using GitHub")
            return github_source
        if host == GITHUB_HOST:
            return github_source
        return RepoSource(
            repo=repo, platform="gitlab", host=host, path=project_path
        )

    def _load_repo_url(self, repo: str) -> Optional[str]:
        """Read the optional repo_url field from the addons config file."""
        filename = repo.replace("/", "@", 1)
        config_file = self.config.input_dir / filename
        if not config_file.exists():
            return None
        try:
            content = config_file.read_text(encoding="utf-8").strip()
            if not content:
                return None
            data = json.loads(content)
            repo_url = data.get("repo_url")
            return repo_url if isinstance(repo_url, str) and repo_url else None
        except Exception as e:
            logger.debug(f"Failed to parse config from {config_file}: {e}")
            return None
