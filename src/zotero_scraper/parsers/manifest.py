"""Manifest file parsers for XPI addons."""

import os
import re
import zipfile
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Optional, Union
from xml.dom import minidom

import commentjson as json

from ..config.constants import ZoteroApp
from ..utils.logging import get_logger
from ..utils.version import compare_versions

logger = get_logger("parsers.manifest")


class ManifestParser(ABC):
    """Abstract base class for manifest parsers."""

    @abstractmethod
    def parse(self, addon_path: Union[str, Path]) -> Optional[dict[str, Any]]:
        """Parse manifest from addon path.

        Args:
            addon_path: Path to XPI file or directory.

        Returns:
            Dictionary with manifest data or None if not found.
        """
        pass

    @abstractmethod
    def extract_details(
        self, addon_path: Union[str, Path], manifest: Any
    ) -> Optional[dict[str, Any]]:
        """Extract addon details from manifest.

        Args:
            addon_path: Path to XPI file or directory.
            manifest: Parsed manifest data.

        Returns:
            Dictionary with addon details.
        """
        pass


class JsonManifestParser(ManifestParser):
    """Parser for manifest.json (WebExtensions format)."""

    def parse(self, addon_path: Union[str, Path]) -> Optional[dict[str, Any]]:
        """Parse manifest.json from XPI file."""
        addon_path = Path(addon_path)

        try:
            if zipfile.is_zipfile(addon_path):
                with zipfile.ZipFile(addon_path, "r") as zf:
                    if "manifest.json" in zf.namelist():
                        content = zf.read("manifest.json").decode("utf-8")
                        return json.loads(content)
            elif addon_path.is_dir():
                manifest_path = addon_path / "manifest.json"
                if manifest_path.exists():
                    with open(manifest_path, "r", encoding="utf-8") as f:
                        return json.loads(f.read())
        except Exception as e:
            logger.warning(f"Failed to parse manifest.json from {addon_path}: {e}")

        return None

    def extract_details(
        self, addon_path: Union[str, Path], manifest: dict[str, Any]
    ) -> Optional[dict[str, Any]]:
        """Extract addon details from manifest.json."""
        details: dict[str, Any] = {
            "name": manifest.get("name"),
            "version": manifest.get("version"),
            "description": manifest.get("description"),
            "id": None,
            "min_version": None,
            "max_version": None,
            "update_url": None,
        }

        # Try to get addon info from applications/browser_specific_settings
        for location in ("applications", "browser_specific_settings"):
            if details["id"]:
                break
            for app in ("zotero", "gecko"):
                try:
                    app_settings = manifest[location][app]
                    details["id"] = app_settings.get("id")
                    details["min_version"] = app_settings.get("strict_min_version")
                    details["max_version"] = app_settings.get("strict_max_version")
                    details["update_url"] = app_settings.get("update_url")
                    break
                except (KeyError, TypeError):
                    continue

        # Handle __MSG_{}__ placeholders
        self._resolve_message_placeholders(addon_path, manifest, details)

        return details

    def _resolve_message_placeholders(
        self,
        addon_path: Union[str, Path],
        manifest: dict[str, Any],
        details: dict[str, Any],
    ) -> None:
        """Resolve __MSG_xxx__ placeholders from locale files."""
        locale_data: Optional[dict[str, Any]] = None

        for key, value in details.items():
            if not isinstance(value, str):
                continue

            match = re.search(r"__MSG_(.*?)__", value)
            if not match:
                continue

            placeholder = match.group(1)

            # Load locale data on first need
            if locale_data is None:
                locale_data = self._load_locale(addon_path, manifest)
                if locale_data is None:
                    break

            # Resolve placeholder
            msg = locale_data.get(placeholder, {}).get("message")
            if msg:
                details[key] = msg

    def _load_locale(
        self, addon_path: Union[str, Path], manifest: dict[str, Any]
    ) -> Optional[dict[str, Any]]:
        """Load locale messages file."""
        default_locale = manifest.get("default_locale")
        if not default_locale:
            return None

        locale_filename = f"_locales/{default_locale}/messages.json"
        addon_path = Path(addon_path)

        try:
            if zipfile.is_zipfile(addon_path):
                with zipfile.ZipFile(addon_path, "r") as zf:
                    if locale_filename in zf.namelist():
                        content = zf.read(locale_filename).decode("utf-8")
                        return json.loads(content)
            elif addon_path.is_dir():
                locale_path = addon_path / locale_filename
                if locale_path.exists():
                    with open(locale_path, "r", encoding="utf-8") as f:
                        return json.loads(f.read())
        except Exception as e:
            logger.warning(f"Failed to load locale file: {e}")

        return None


class RdfManifestParser(ManifestParser):
    """Parser for install.rdf (legacy XUL format)."""

    def parse(self, addon_path: Union[str, Path]) -> Optional[bytes]:
        """Parse install.rdf from XPI file."""
        addon_path = Path(addon_path)

        try:
            if zipfile.is_zipfile(addon_path):
                with zipfile.ZipFile(addon_path, "r") as zf:
                    if "install.rdf" in zf.namelist():
                        return zf.read("install.rdf")
            elif addon_path.is_dir():
                rdf_path = addon_path / "install.rdf"
                if rdf_path.exists():
                    with open(rdf_path, "rb") as f:
                        return f.read()
        except Exception as e:
            logger.warning(f"Failed to parse install.rdf from {addon_path}: {e}")

        return None

    def extract_details(
        self, addon_path: Union[str, Path], manifest: bytes
    ) -> Optional[dict[str, Any]]:
        """Extract addon details from install.rdf."""
        details: dict[str, Any] = {
            "id": None,
            "name": None,
            "version": None,
            "description": None,
            "min_version": None,
            "max_version": None,
            "update_url": None,
        }

        try:
            doc = minidom.parseString(manifest)

            # Get namespace prefixes
            em = self._get_namespace_id(doc, "http://www.mozilla.org/2004/em-rdf#")
            rdf = self._get_namespace_id(doc, "http://www.w3.org/1999/02/22-rdf-syntax-ns#")

            # Find the main Description element
            description = self._find_main_description(doc, rdf, em)
            if description is None:
                return None

            # Extract basic info
            self._extract_info(description, details, em)

            # Validate ID
            addon_id = details.get("id")
            if not addon_id or (addon_id.startswith("__") and addon_id.endswith("__")):
                return None

            # Extract version info from targetApplication
            self._extract_target_application_info(description, details, em)

            # Handle updateURL
            if update_url := details.get("updateURL"):
                details["update_url"] = update_url

            return details

        except Exception as e:
            logger.warning(f"Failed to extract details from install.rdf: {e}")
            return None

    def _get_namespace_id(self, doc: minidom.Document, url: str) -> str:
        """Get namespace prefix for a given URL."""
        attributes = doc.documentElement.attributes
        for i in range(attributes.length):
            attr = attributes.item(i)
            if attr.value == url and ":" in attr.name:
                return attr.name.split(":")[1] + ":"
        return ""

    def _find_main_description(
        self, doc: minidom.Document, rdf: str, em: str
    ) -> Optional[minidom.Element]:
        """Find the main Description element."""
        descriptions = doc.getElementsByTagName(rdf + "Description")
        if not descriptions:
            return None

        # Try to find description with targetApplication
        for desc in descriptions:
            if desc.getElementsByTagName(em + "targetApplication"):
                return desc

        return descriptions.item(0)

    def _extract_info(
        self,
        node: minidom.Element,
        result: dict[str, Any],
        em: str,
    ) -> None:
        """Extract info from node attributes and children."""
        try:
            # From attributes
            for entry, value in node.attributes.items():
                entry = entry.replace(em, "")
                if entry in result:
                    result[entry] = value

            # From child nodes
            for child in node.childNodes:
                if child.nodeType != child.ELEMENT_NODE:
                    continue
                entry = child.nodeName.replace(em, "")
                if entry in result:
                    result[entry] = self._get_text(child)
        except Exception:
            pass

    def _get_text(self, element: minidom.Element) -> str:
        """Get text content of an element."""
        rc = []
        for node in element.childNodes:
            if node.nodeType == node.TEXT_NODE:
                rc.append(node.data)
        return "".join(rc).strip()

    def _extract_target_application_info(
        self,
        description: minidom.Element,
        details: dict[str, Any],
        em: str,
    ) -> None:
        """Extract version info from targetApplication elements."""
        for target_app in description.getElementsByTagName(em + "targetApplication"):
            version_info = {"id": None, "minVersion": None, "maxVersion": None}
            self._extract_info(target_app, version_info, em)
            self._update_version_from_target(details, version_info)

            # Check child nodes as well
            for child in target_app.childNodes:
                if child.nodeType != child.ELEMENT_NODE:
                    continue
                version_info = {"id": None, "minVersion": None, "maxVersion": None}
                self._extract_info(child, version_info, em)
                self._update_version_from_target(details, version_info)

    def _update_version_from_target(
        self,
        details: dict[str, Any],
        version_info: dict[str, Any],
    ) -> None:
        """Update version range from targetApplication info."""
        # Only process Zotero application
        if version_info.get("id") != ZoteroApp.APP_ID:
            return

        min_ver = version_info.get("minVersion")
        max_ver = version_info.get("maxVersion")

        if not min_ver or not max_ver:
            return

        # Update min version (take smaller)
        existing_min = details.get("min_version")
        if existing_min:
            min_normalized = min_ver.replace("*", "0")
            existing_normalized = existing_min.replace("*", "999")
            if compare_versions(min_normalized, existing_normalized) <= 0:
                details["min_version"] = min_ver
        else:
            details["min_version"] = min_ver

        # Update max version (take larger, but cap at 6.* for RDF)
        # RDF format doesn't support Zotero 7
        if compare_versions(max_ver.replace("*", "999"), "6.*") > 0:
            max_ver = "6.*"

        existing_max = details.get("max_version")
        if existing_max:
            max_normalized = max_ver.replace("*", "999")
            existing_normalized = existing_max.replace("*", "0")
            if compare_versions(max_normalized, existing_normalized) >= 0:
                details["max_version"] = max_ver
        else:
            details["max_version"] = max_ver
