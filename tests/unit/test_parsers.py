"""Unit tests for parsers."""

import json
import tempfile
import zipfile
from pathlib import Path

import pytest

from zotero_scraper.models.xpi import XpiDetail
from zotero_scraper.parsers.manifest import JsonManifestParser, RdfManifestParser
from zotero_scraper.parsers.xpi_parser import XPIParser


class TestJsonManifestParser:
    """Tests for JsonManifestParser."""

    @pytest.fixture
    def parser(self):
        return JsonManifestParser()

    @pytest.fixture
    def sample_xpi(self, sample_manifest_json, temp_dir):
        """Create a sample XPI file with manifest.json."""
        xpi_path = temp_dir / "test.xpi"
        with zipfile.ZipFile(xpi_path, "w") as zf:
            zf.writestr("manifest.json", json.dumps(sample_manifest_json))
        return xpi_path

    def test_parse_from_xpi(self, parser, sample_xpi, sample_manifest_json):
        """Test parsing manifest.json from XPI file."""
        manifest = parser.parse(sample_xpi)
        assert manifest is not None
        assert manifest["name"] == sample_manifest_json["name"]
        assert manifest["version"] == sample_manifest_json["version"]

    def test_parse_from_directory(self, parser, sample_manifest_json, temp_dir):
        """Test parsing manifest.json from directory."""
        manifest_path = temp_dir / "manifest.json"
        with open(manifest_path, "w") as f:
            json.dump(sample_manifest_json, f)

        manifest = parser.parse(temp_dir)
        assert manifest is not None
        assert manifest["name"] == sample_manifest_json["name"]

    def test_parse_nonexistent(self, parser, temp_dir):
        """Test parsing from nonexistent path."""
        manifest = parser.parse(temp_dir / "nonexistent.xpi")
        assert manifest is None

    def test_extract_details(self, parser, sample_xpi, sample_manifest_json):
        """Test extracting details from manifest."""
        manifest = parser.parse(sample_xpi)
        details = parser.extract_details(sample_xpi, manifest)

        assert details["name"] == "Test Addon"
        assert details["version"] == "1.0.0"
        assert details["id"] == "test@addon.com"
        assert details["min_version"] == "6.0"
        assert details["max_version"] == "7.*"


class TestXpiDetail:
    """Tests for XpiDetail model."""

    def test_append_info(self):
        """Test appending info to XpiDetail."""
        detail = XpiDetail()
        detail.append_info({
            "id": "test@addon.com",
            "name": "Test Addon",
            "version": "1.0.0",
            "min_version": "6.0",
            "max_version": "7.*",
        })

        assert detail.id == "test@addon.com"
        assert detail.name == "Test Addon"
        assert detail.version == "1.0.0"
        assert detail.min_version == "6.0"
        assert detail.max_version == "7.*"

    def test_check_compatible_zotero7(self):
        """Test compatibility check for Zotero 7."""
        detail = XpiDetail()
        detail.min_version = "7.0"
        detail.max_version = "7.*"

        assert detail.check_compatible("7.*") is True
        assert detail.check_compatible("6.*") is False

    def test_check_compatible_both_versions(self):
        """Test compatibility check for both Zotero versions."""
        detail = XpiDetail()
        detail.min_version = "6.0"
        detail.max_version = "7.*"

        assert detail.check_compatible("7.*") is True
        assert detail.check_compatible("6.*") is True

    def test_is_valid(self):
        """Test validity check."""
        detail = XpiDetail()
        assert detail.is_valid() is False

        detail.id = "test@addon.com"
        assert detail.is_valid() is True


class TestXPIParser:
    """Tests for XPIParser."""

    @pytest.fixture
    def parser(self):
        return XPIParser()

    def test_parse_json_manifest(self, parser, sample_manifest_json, temp_dir):
        """Test parsing XPI with JSON manifest."""
        xpi_path = temp_dir / "test.xpi"
        with zipfile.ZipFile(xpi_path, "w") as zf:
            zf.writestr("manifest.json", json.dumps(sample_manifest_json))

        details = parser.parse(xpi_path)
        assert details is not None
        assert details.id == "test@addon.com"
        assert details.name == "Test Addon"

    def test_parse_nonexistent_raises(self, parser, temp_dir):
        """Test parsing nonexistent file raises error."""
        from zotero_scraper.exceptions import XPIParseError

        with pytest.raises(XPIParseError):
            parser.parse(temp_dir / "nonexistent.xpi")

    def test_parse_priority_sources(self, parser, sample_manifest_json, temp_dir):
        """Test priority sources parameter."""
        xpi_path = temp_dir / "test.xpi"
        with zipfile.ZipFile(xpi_path, "w") as zf:
            zf.writestr("manifest.json", json.dumps(sample_manifest_json))

        # Should work with json priority
        details = parser.parse(xpi_path, priority_sources=["json"])
        assert details is not None
        assert details.id == "test@addon.com"

        # Should return None with only rdf priority (no install.rdf)
        details = parser.parse(xpi_path, priority_sources=["rdf"])
        assert details is None
