"""XPI parsers module."""

from .manifest import JsonManifestParser, RdfManifestParser
from .xpi_parser import XPIParser

__all__ = [
    "JsonManifestParser",
    "RdfManifestParser",
    "XPIParser",
]
