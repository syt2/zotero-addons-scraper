"""XPI detail model."""

from dataclasses import dataclass, field
from typing import Optional

from ..utils.logging import get_logger
from ..utils.version import compare_versions

logger = get_logger("models.xpi")


@dataclass
class XpiDetail:
    """XPI addon details extracted from manifest files."""

    id: Optional[str] = None
    name: Optional[str] = None
    version: Optional[str] = None
    description: Optional[str] = None
    update_url: Optional[str] = None
    min_version: str = "*"
    max_version: str = "*"

    def append_info(self, details: dict) -> None:
        """Append information from parsed manifest details.

        Args:
            details: Dictionary containing parsed manifest data.
        """
        # Check ID consistency
        if addon_id := details.get("id"):
            if self.id and self.id != addon_id:
                logger.warning(f"XPI ID mismatch: {self.id} != {addon_id}")
                return
            self.id = addon_id

        # Update basic info
        if name := details.get("name"):
            self.name = name
        if version := details.get("version"):
            self.version = version
        if description := details.get("description"):
            self.description = description

        # Update URL (support both keys)
        if update_url := details.get("updateURL") or details.get("update_url"):
            self.update_url = update_url

        # Update version range (take the widest range)
        min_ver = details.get("min_version")
        max_ver = details.get("max_version")
        if min_ver and max_ver:
            self._update_version_range(min_ver, max_ver)

    def _update_version_range(self, min_ver: str, max_ver: str) -> None:
        """Update version range to include the new range.

        Takes the widest range between existing and new values.

        Args:
            min_ver: New minimum version.
            max_ver: New maximum version.
        """
        # For min_version, take the smaller one
        min_normalized = min_ver.replace("*", "0")
        existing_min_normalized = self.min_version.replace("*", "999")
        if compare_versions(min_normalized, existing_min_normalized) <= 0:
            self.min_version = min_ver

        # For max_version, take the larger one
        max_normalized = max_ver.replace("*", "999")
        existing_max_normalized = self.max_version.replace("*", "0")
        if compare_versions(max_normalized, existing_max_normalized) >= 0:
            self.max_version = max_ver

    def check_compatible(self, version: str) -> bool:
        """Check if addon is compatible with a Zotero version.

        Args:
            version: Zotero version string (e.g., "7.*" or "6.*").

        Returns:
            True if compatible, False otherwise.
        """
        # Normalize versions for comparison
        min_normalized = self.min_version.replace("*", "0")
        max_normalized = self.max_version.replace("*", "999")
        version_normalized = version.replace("*", "999")
        version_base = version.replace("*", "0")

        # Check if version is within range
        return (
            compare_versions(min_normalized, version_normalized) <= 0
            and compare_versions(max_normalized, version_base) >= 0
        )

    def is_valid(self) -> bool:
        """Check if XPI detail has minimum required information.

        Returns:
            True if has at least ID, False otherwise.
        """
        return bool(self.id)
