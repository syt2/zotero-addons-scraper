"""Data models module."""

from .addon import AddonInfo, AddonRelease, Author, XpiDownloadUrls
from .xpi import XpiDetail

__all__ = [
    "AddonInfo",
    "AddonRelease",
    "Author",
    "XpiDownloadUrls",
    "XpiDetail",
]
