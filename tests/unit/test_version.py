"""Unit tests for version utilities."""

import pytest

from zotero_scraper.utils.version import compare_versions, version_in_range


class TestCompareVersions:
    """Tests for compare_versions function."""

    @pytest.mark.parametrize(
        "v1,v2,expected",
        [
            # Equal versions
            ("1.0.0", "1.0.0", 0),
            ("2.0", "2.0", 0),
            ("1", "1", 0),
            # v1 > v2
            ("2.0.0", "1.0.0", 1),
            ("1.1.0", "1.0.0", 1),
            ("1.0.1", "1.0.0", 1),
            ("10.0.0", "9.0.0", 1),
            ("1.0.0", "0.9.9", 1),
            # v1 < v2
            ("1.0.0", "2.0.0", -1),
            ("1.0.0", "1.1.0", -1),
            ("1.0.0", "1.0.1", -1),
            ("9.0.0", "10.0.0", -1),
            # Different length versions
            ("1.0", "1.0.0", 0),
            ("1.0.0", "1.0", 0),
            ("1.0.1", "1.0", 1),
            # Pre-release versions (using - separator)
            ("1.0.0-beta", "1.0.0-alpha", 1),
            ("1.0.0-alpha", "1.0.0-beta", -1),
            # Wildcard versions
            ("7.*", "6.*", 1),
            ("6.*", "7.*", -1),
            ("7.*", "7.*", 0),
        ],
    )
    def test_compare_versions(self, v1: str, v2: str, expected: int):
        """Test version comparison."""
        assert compare_versions(v1, v2) == expected

    def test_compare_versions_with_int(self):
        """Test version comparison with integer input."""
        assert compare_versions(1, "1.0.0") == 0
        assert compare_versions("1.0.0", 1) == 0


class TestVersionInRange:
    """Tests for version_in_range function."""

    @pytest.mark.parametrize(
        "version,min_ver,max_ver,expected",
        [
            ("7.0", "6.0", "8.0", True),
            ("6.0", "6.0", "7.0", True),
            ("7.0", "6.0", "7.0", True),
            ("5.0", "6.0", "7.0", False),
            ("8.0", "6.0", "7.0", False),
            ("7.*", "6.*", "7.*", True),
            ("6.5", "6.*", "7.*", True),
        ],
    )
    def test_version_in_range(
        self, version: str, min_ver: str, max_ver: str, expected: bool
    ):
        """Test version range checking."""
        assert version_in_range(version, min_ver, max_ver) == expected
