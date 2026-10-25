"""Helpers for creating Zotero-version-specific addon info files."""

from collections.abc import Iterable
from copy import deepcopy
from pathlib import Path
from typing import Any


def version_output_path(output_file: Path, zotero_version: str) -> Path:
    """Build the output path for a Zotero-version-specific info file.

    For example, ``addon_infos.json`` and ``6`` produce
    ``addon_infos_6.json``.
    """
    return output_file.with_name(
        f"{output_file.stem}_{zotero_version}{output_file.suffix}"
    )


def split_addon_infos_by_zotero_version(
    addon_infos: Iterable[dict[str, Any]],
    zotero_versions: Iterable[str],
) -> dict[str, list[dict[str, Any]]]:
    """Split addon info records into one list per target Zotero version.

    Each addon keeps its metadata but only contains releases whose
    ``targetZoteroVersion`` exactly matches the requested version. Addons with
    no matching release are omitted. The input data is not modified.
    """
    addon_list = list(addon_infos)
    result: dict[str, list[dict[str, Any]]] = {}

    for zotero_version in dict.fromkeys(zotero_versions):
        filtered_addons: list[dict[str, Any]] = []
        for addon in addon_list:
            matching_releases = [
                deepcopy(release)
                for release in addon.get("releases", [])
                if isinstance(release, dict)
                and release.get("targetZoteroVersion") == zotero_version
            ]
            if not matching_releases:
                continue

            filtered_addon = deepcopy(addon)
            filtered_addon["releases"] = matching_releases
            filtered_addons.append(filtered_addon)

        result[zotero_version] = filtered_addons

    return result
