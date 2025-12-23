"""Custom exceptions for the Zotero addons scraper."""


class ScraperError(Exception):
    """Base exception for all scraper errors."""

    pass


class ConfigError(ScraperError):
    """Configuration error."""

    pass


class HTTPError(ScraperError):
    """HTTP request error."""

    pass


class RateLimitError(HTTPError):
    """API rate limit exceeded error."""

    pass


class GitHubError(ScraperError):
    """GitHub API error."""

    pass


class XPIParseError(ScraperError):
    """XPI file parsing error."""

    pass


class DownloadError(ScraperError):
    """File download error."""

    pass


class CacheError(ScraperError):
    """Cache operation error."""

    pass
