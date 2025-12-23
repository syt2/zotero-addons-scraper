"""Addon data models."""

from dataclasses import dataclass, field
from typing import Any, Optional, Union


@dataclass
class Author:
    """Addon author information."""

    name: Optional[str] = None
    url: Optional[str] = None
    avatar: Optional[str] = None

    def to_dict(self) -> dict[str, str]:
        """Convert to dictionary, excluding None values."""
        result: dict[str, str] = {}
        if self.name:
            result["name"] = self.name
        if self.url:
            result["url"] = self.url
        if self.avatar:
            result["avatar"] = self.avatar
        return result

    @classmethod
    def from_dict(cls, data: Optional[dict[str, Any]]) -> "Author":
        """Create Author from dictionary."""
        if not data:
            return cls()
        return cls(
            name=data.get("name"),
            url=data.get("url"),
            avatar=data.get("avatar"),
        )


@dataclass
class XpiDownloadUrls:
    """XPI download URLs from multiple sources."""

    github: str
    ghProxy: Optional[str] = None
    kgithub: Optional[str] = None

    def to_dict(self) -> dict[str, str]:
        """Convert to dictionary, excluding None values."""
        result: dict[str, str] = {"github": self.github}
        if self.ghProxy:
            result["ghProxy"] = self.ghProxy
        if self.kgithub:
            result["kgithub"] = self.kgithub
        return result

    @classmethod
    def from_dict(cls, data: Optional[dict[str, str]]) -> Optional["XpiDownloadUrls"]:
        """Create XpiDownloadUrls from dictionary."""
        if not data or "github" not in data:
            return None
        return cls(
            github=data["github"],
            ghProxy=data.get("ghProxy"),
            kgithub=data.get("kgithub"),
        )


@dataclass
class AddonRelease:
    """Addon release version information."""

    targetZoteroVersion: str
    tagName: str
    xpiDownloadUrl: Optional[XpiDownloadUrls] = None
    releaseDate: Optional[str] = None
    id: Optional[str] = None
    xpiVersion: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None
    minZoteroVersion: Optional[str] = None
    maxZoteroVersion: Optional[str] = None

    @property
    def zotero_check_version(self) -> str:
        """Get Zotero version check string.

        Returns:
            Version check string (e.g., "6.*" or "7.*").

        Raises:
            ValueError: If targetZoteroVersion is not valid.
        """
        if self.targetZoteroVersion == "6":
            return "6.*"
        elif self.targetZoteroVersion == "7":
            return "7.*"
        raise ValueError(
            f"Invalid targetZoteroVersion: {self.targetZoteroVersion}"
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary, excluding None values."""
        result: dict[str, Any] = {}
        if self.targetZoteroVersion:
            result["targetZoteroVersion"] = self.targetZoteroVersion
        if self.tagName:
            result["tagName"] = self.tagName
        if self.xpiDownloadUrl:
            result["xpiDownloadUrl"] = self.xpiDownloadUrl.to_dict()
        if self.releaseDate:
            result["releaseDate"] = self.releaseDate
        if self.id:
            result["id"] = self.id
        if self.xpiVersion:
            result["xpiVersion"] = self.xpiVersion
        if self.name:
            result["name"] = self.name
        if self.description:
            result["description"] = self.description
        if self.minZoteroVersion:
            result["minZoteroVersion"] = self.minZoteroVersion
        if self.maxZoteroVersion:
            result["maxZoteroVersion"] = self.maxZoteroVersion
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AddonRelease":
        """Create AddonRelease from dictionary."""
        xpi_url_data = data.get("xpiDownloadUrl")
        xpi_download_url = (
            XpiDownloadUrls.from_dict(xpi_url_data)
            if isinstance(xpi_url_data, dict)
            else None
        )
        return cls(
            targetZoteroVersion=data.get("targetZoteroVersion", ""),
            tagName=data.get("tagName", ""),
            xpiDownloadUrl=xpi_download_url,
            releaseDate=data.get("releaseDate"),
            id=data.get("id"),
            xpiVersion=data.get("xpiVersion"),
            name=data.get("name"),
            description=data.get("description"),
            minZoteroVersion=data.get("minZoteroVersion"),
            maxZoteroVersion=data.get("maxZoteroVersion"),
        )


@dataclass
class AddonInfo:
    """Complete addon information."""

    repo: str
    releases: list[AddonRelease] = field(default_factory=list)
    name: Optional[str] = None
    description: Optional[str] = None
    stars: Optional[int] = None
    author: Author = field(default_factory=Author)

    @property
    def owner(self) -> Optional[str]:
        """Get repository owner."""
        parts = self.repo.split("/")
        return parts[0] if len(parts) == 2 else None

    @property
    def repository(self) -> Optional[str]:
        """Get repository name."""
        parts = self.repo.split("/")
        return parts[1] if len(parts) == 2 else None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization.

        Maintains backward compatibility with existing output format.
        """
        result: dict[str, Any] = {}
        if self.repo:
            result["repo"] = self.repo
        if self.releases:
            result["releases"] = [release.to_dict() for release in self.releases]
        if self.name:
            result["name"] = self.name
        if self.description:
            result["description"] = self.description
        if self.stars:
            result["stars"] = self.stars
            # Backward compatibility: keep "star" field for older versions
            result["star"] = self.stars
        if self.author:
            author_dict = self.author.to_dict()
            if author_dict:
                result["author"] = author_dict
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AddonInfo":
        """Create AddonInfo from dictionary."""
        releases_data = data.get("releases", [])
        releases = [
            AddonRelease.from_dict(r) if isinstance(r, dict) else r
            for r in releases_data
        ]

        author_data = data.get("author")
        author = (
            Author.from_dict(author_data)
            if isinstance(author_data, dict)
            else Author()
        )

        return cls(
            repo=data.get("repo", ""),
            releases=releases,
            name=data.get("name"),
            description=data.get("description"),
            stars=data.get("stars"),
            author=author,
        )
