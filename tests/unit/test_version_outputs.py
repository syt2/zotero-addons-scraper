"""Tests for Zotero-version-specific addon info outputs."""

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from zotero_scraper.config.settings import ScraperConfig
from zotero_scraper.services.cache_scraper import CacheScraper
from zotero_scraper.services.publisher import PublisherService
from zotero_scraper.services.version_outputs import (
    split_addon_infos_by_zotero_version,
    version_output_path,
)


def sample_addons() -> list[dict]:
    return [
        {
            "repo": "owner/multi-version",
            "name": "Multi Version",
            "stars": 100,
            "releases": [
                {"targetZoteroVersion": "6", "tagName": "v1"},
                {"targetZoteroVersion": "7", "tagName": "v2"},
            ],
        },
        {
            "repo": "owner/only-seven",
            "name": "Only Seven",
            "releases": [{"targetZoteroVersion": "7", "tagName": "v3"}],
        },
    ]


def test_version_output_path() -> None:
    """Version files should be next to the complete output file."""
    output = Path("published/addon_infos.json")
    assert version_output_path(output, "6") == Path("published/addon_infos_6.json")


def test_split_addon_infos_by_zotero_version() -> None:
    """Each output should retain metadata but only matching releases."""
    addons = sample_addons()

    split = split_addon_infos_by_zotero_version(addons, ["6", "7", "13"])

    assert list(split) == ["6", "7", "13"]
    assert [addon["repo"] for addon in split["6"]] == ["owner/multi-version"]
    assert split["6"][0]["name"] == "Multi Version"
    assert split["6"][0]["stars"] == 100
    assert [r["tagName"] for r in split["6"][0]["releases"]] == ["v1"]
    assert [addon["repo"] for addon in split["7"]] == [
        "owner/multi-version",
        "owner/only-seven",
    ]
    assert [r["tagName"] for r in split["7"][0]["releases"]] == ["v2"]
    assert split["13"] == []


def test_split_does_not_modify_input_and_deduplicates_versions() -> None:
    """Splitting should be a pure operation with one output per version."""
    addons = sample_addons()

    split = split_addon_infos_by_zotero_version(addons, ["7", "7", "6"])

    assert list(split) == ["7", "6"]
    assert len(addons[0]["releases"]) == 2


def test_cache_scraper_writes_dynamic_version_outputs(temp_dir: Path) -> None:
    """New target versions should automatically produce new output files."""
    output_file = temp_dir / "addon_infos.json"
    config = SimpleNamespace(output_file=output_file)
    scraper = CacheScraper.__new__(CacheScraper)
    scraper.config = config
    scraper.target_zotero_versions = ["13", "7", "6"]
    scraper.version_output_files = {}

    data = sample_addons()
    scraper._save_output(data)
    scraper._save_version_outputs(data)

    assert scraper.version_output_files == {
        "13": temp_dir / "addon_infos_13.json",
        "7": temp_dir / "addon_infos_7.json",
        "6": temp_dir / "addon_infos_6.json",
    }
    assert json.loads(output_file.read_text()) == data
    assert json.loads((temp_dir / "addon_infos_13.json").read_text()) == []
    assert json.loads((temp_dir / "addon_infos_7.json").read_text()) == [
        {**data[0], "releases": [data[0]["releases"][1]]},
        data[1],
    ]


def test_cache_scraper_deduplicates_target_versions() -> None:
    """Duplicate target versions must not duplicate releases in full output."""
    scraper = CacheScraper(
        ScraperConfig(),
        Mock(),
        target_zotero_versions=["7", "7", "6"],
    )

    assert scraper.target_zotero_versions == ["7", "6"]


def test_publisher_uploads_complete_and_version_files(temp_dir: Path) -> None:
    """Publisher should upload every generated file with its own name."""
    complete_file = temp_dir / "addon_infos.json"
    version_file = temp_dir / "addon_infos_13.json"
    complete_file.write_text("[]")
    version_file.write_text("[]")

    github = Mock()
    github.create_release.return_value = 42
    github.upload_release_asset.return_value = True
    config = SimpleNamespace(owner="owner", repo_name="repo")
    publisher = PublisherService(github, config)

    assert publisher.publish(complete_file, [version_file]) is True
    uploads = github.upload_release_asset.call_args_list
    assert [call.kwargs["filename"] for call in uploads] == [
        "addon_infos.json",
        "addon_infos_13.json",
    ]


def test_publisher_reports_partial_upload_failure(temp_dir: Path) -> None:
    """A failed version asset should make publishing fail."""
    complete_file = temp_dir / "addon_infos.json"
    version_file = temp_dir / "addon_infos_7.json"
    complete_file.write_text("[]")
    version_file.write_text("[]")

    github = Mock()
    github.create_release.return_value = 42
    github.upload_release_asset.side_effect = [True, False]
    config = SimpleNamespace(owner="owner", repo_name="repo")
    publisher = PublisherService(github, config)

    assert publisher.publish(complete_file, [version_file]) is False
