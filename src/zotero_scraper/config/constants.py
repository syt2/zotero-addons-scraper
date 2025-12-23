"""Constants and API endpoints for the Zotero addons scraper."""

from urllib.parse import quote


class GitHubAPI:
    """GitHub API endpoints."""

    BASE = "https://api.github.com"
    UPLOADS_BASE = "https://uploads.github.com"
    DEFAULT_API_VERSION = "2022-11-28"

    @staticmethod
    def user(username: str) -> str:
        """Get user info endpoint."""
        return f"{GitHubAPI.BASE}/users/{username}"

    @staticmethod
    def repo(owner: str, repo: str) -> str:
        """Get repository info endpoint."""
        return f"{GitHubAPI.BASE}/repos/{owner}/{repo}"

    @staticmethod
    def releases(owner: str, repo: str) -> str:
        """Get releases list endpoint."""
        return f"{GitHubAPI.BASE}/repos/{owner}/{repo}/releases"

    @staticmethod
    def release_latest(owner: str, repo: str) -> str:
        """Get latest release endpoint."""
        return f"{GitHubAPI.releases(owner, repo)}/latest"

    @staticmethod
    def release_by_tag(owner: str, repo: str, tag: str) -> str:
        """Get release by tag endpoint."""
        return f"{GitHubAPI.releases(owner, repo)}/tags/{tag}"

    @staticmethod
    def issues(owner: str, repo: str) -> str:
        """Get issues endpoint."""
        return f"{GitHubAPI.BASE}/repos/{owner}/{repo}/issues"

    @staticmethod
    def caches(owner: str, repo: str) -> str:
        """Get actions caches endpoint."""
        return f"{GitHubAPI.BASE}/repos/{owner}/{repo}/actions/caches"

    @staticmethod
    def tags(owner: str, repo: str) -> str:
        """Get git tags endpoint."""
        return f"{GitHubAPI.BASE}/repos/{owner}/{repo}/git/refs/tags"

    @staticmethod
    def upload_asset(owner: str, repo: str, release_id: int, name: str) -> str:
        """Get upload asset endpoint."""
        return (
            f"{GitHubAPI.UPLOADS_BASE}/repos/{owner}/{repo}"
            f"/releases/{release_id}/assets?name={name}"
        )

    @staticmethod
    def rate_limit() -> str:
        """Get rate limit endpoint."""
        return f"{GitHubAPI.BASE}/rate_limit"


class XPIProxy:
    """XPI download proxy URLs."""

    GHPROXY_BASE = "https://gh-proxy.com/"
    KKGITHUB_DOMAIN = "kkgithub.com"

    @staticmethod
    def ghproxy_url(github_url: str) -> str:
        """Get ghProxy URL for a GitHub download URL."""
        return f"{XPIProxy.GHPROXY_BASE}?q={quote(github_url, safe='')}"

    @staticmethod
    def kkgithub_url(github_url: str) -> str:
        """Get kkgithub URL for a GitHub download URL."""
        return github_url.replace("github.com", XPIProxy.KKGITHUB_DOMAIN)


class ZoteroApp:
    """Zotero application constants."""

    APP_ID = "zotero@chnm.gmu.edu"
    SUPPORTED_VERSIONS = ("6", "7")

    @staticmethod
    def check_version(target_version: str) -> str:
        """Get Zotero version check string.

        Args:
            target_version: Target Zotero version ("6" or "7").

        Returns:
            Version check string (e.g., "6.*" or "7.*").

        Raises:
            ValueError: If target_version is not supported.
        """
        if target_version not in ZoteroApp.SUPPORTED_VERSIONS:
            raise ValueError(f"Unsupported Zotero version: {target_version}")
        return f"{target_version}.*"


class ContentTypes:
    """MIME content types."""

    XPI = "application/x-xpinstall"
    ZIP = "application/x-zip-compressed"
    OCTET_STREAM = "application/octet-stream"
