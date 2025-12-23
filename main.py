#!/usr/bin/env python3
"""
Backward compatible entry point for Zotero addons scraper.

This file maintains backward compatibility with existing CI/CD pipelines
and command-line usage. It delegates to the new modular implementation.

Usage:
    python main.py -i addons -o addon_infos.json \\
        --github_repository owner/repo \\
        --github_token TOKEN \\
        --cache_directory caches \\
        --runtime_xpi_directory xpis \\
        --previous_info_urls URL1 URL2 \\
        --create_release True
"""

import sys

# Add src to path for development
from pathlib import Path

src_path = Path(__file__).parent / "src"
if src_path.exists():
    sys.path.insert(0, str(src_path))

from zotero_scraper.__main__ import main

if __name__ == "__main__":
    sys.exit(main())
