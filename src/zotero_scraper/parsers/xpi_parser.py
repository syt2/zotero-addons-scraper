"""XPI file parser."""

import os
from pathlib import Path
from typing import Optional, Union

from ..exceptions import XPIParseError
from ..models.xpi import XpiDetail
from ..utils.logging import get_logger
from .manifest import JsonManifestParser, RdfManifestParser

logger = get_logger("parsers.xpi")


class XPIParser:
    """Parser for XPI addon files."""

    def __init__(self):
        """Initialize XPI parser with manifest parsers."""
        self.json_parser = JsonManifestParser()
        self.rdf_parser = RdfManifestParser()

    def parse(
        self,
        addon_path: Union[str, Path],
        priority_sources: Optional[list[str]] = None,
    ) -> Optional[XpiDetail]:
        """Parse XPI file and extract addon details.

        Args:
            addon_path: Path to XPI file or directory.
            priority_sources: List of sources to try, in order.
                             Options: "json", "rdf".
                             Default: ["json", "rdf"].

        Returns:
            XpiDetail with extracted information, or None if parsing failed.

        Raises:
            XPIParseError: If addon path doesn't exist.
        """
        addon_path = Path(addon_path)

        if not addon_path.exists():
            raise XPIParseError(f"Addon path does not exist: {addon_path}")

        if priority_sources is None:
            priority_sources = ["json", "rdf"]

        xpi_detail = XpiDetail()

        for source in priority_sources:
            if source == "json":
                self._parse_json(addon_path, xpi_detail)
            elif source == "rdf":
                self._parse_rdf(addon_path, xpi_detail)

        return xpi_detail if xpi_detail.is_valid() else None

    def _parse_json(self, addon_path: Path, xpi_detail: XpiDetail) -> None:
        """Parse manifest.json and update XpiDetail."""
        try:
            manifest = self.json_parser.parse(addon_path)
            if manifest:
                details = self.json_parser.extract_details(addon_path, manifest)
                if details:
                    xpi_detail.append_info(details)
        except Exception as e:
            logger.debug(f"JSON parsing failed for {addon_path}: {e}")

    def _parse_rdf(self, addon_path: Path, xpi_detail: XpiDetail) -> None:
        """Parse install.rdf and update XpiDetail."""
        try:
            manifest = self.rdf_parser.parse(addon_path)
            if manifest:
                details = self.rdf_parser.extract_details(addon_path, manifest)
                if details:
                    xpi_detail.append_info(details)
        except Exception as e:
            logger.debug(f"RDF parsing failed for {addon_path}: {e}")
