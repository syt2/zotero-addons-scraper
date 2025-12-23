"""Version comparison utilities."""

from typing import Union


def compare_versions(version1: Union[str, int], version2: Union[str, int]) -> int:
    """Compare two version strings.

    Supports version formats like:
    - "1.0.0", "1.2.3"
    - "1.0.0-beta", "1.0.0-alpha"
    - "7.*", "6.*"

    Args:
        version1: First version string.
        version2: Second version string.

    Returns:
        -1 if version1 < version2
         0 if version1 == version2
         1 if version1 > version2
    """
    v1 = str(version1)
    v2 = str(version2)

    # Normalize: replace '-' with '.' for comparison
    parts1 = v1.replace("-", ".").split(".")
    parts2 = v2.replace("-", ".").split(".")

    # Pad shorter list with zeros
    max_len = max(len(parts1), len(parts2))
    parts1.extend(["0"] * (max_len - len(parts1)))
    parts2.extend(["0"] * (max_len - len(parts2)))

    for p1, p2 in zip(parts1, parts2):
        # Handle wildcard
        if p1 == "*" or p2 == "*":
            continue

        # Try numeric comparison
        try:
            n1, n2 = int(p1), int(p2)
            if n1 < n2:
                return -1
            elif n1 > n2:
                return 1
        except ValueError:
            # Fall back to string comparison for non-numeric parts
            if p1 < p2:
                return -1
            elif p1 > p2:
                return 1

    return 0


def version_in_range(
    version: str,
    min_version: str,
    max_version: str,
) -> bool:
    """Check if a version is within a given range.

    Args:
        version: Version to check.
        min_version: Minimum version (inclusive).
        max_version: Maximum version (inclusive).

    Returns:
        True if version is within [min_version, max_version].
    """
    return (
        compare_versions(version, min_version) >= 0
        and compare_versions(version, max_version) <= 0
    )
