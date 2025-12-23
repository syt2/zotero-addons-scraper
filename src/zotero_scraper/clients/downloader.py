"""XPI file downloader."""

import os
import shutil
from pathlib import Path
from typing import Optional

from ..config.settings import CacheConfig
from ..exceptions import DownloadError
from ..utils.logging import get_logger
from .base import BaseHTTPClient

logger = get_logger("clients.downloader")


class XPIDownloader(BaseHTTPClient):
    """XPI file downloader with caching support."""

    def __init__(
        self,
        cache_config: CacheConfig,
        timeout: int = 60,
        max_retries: int = 3,
    ):
        """Initialize XPI downloader.

        Args:
            cache_config: Cache configuration.
            timeout: Download timeout in seconds.
            max_retries: Maximum download retries.
        """
        super().__init__(
            timeout=timeout,
            max_retries=max_retries,
        )
        self.cache_dir = cache_config.cache_dir
        self.runtime_dir = cache_config.runtime_xpi_dir

        # Ensure directories exist
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.runtime_dir.mkdir(parents=True, exist_ok=True)

    def download(
        self,
        url: str,
        filename: str,
        force_download: bool = False,
    ) -> Optional[Path]:
        """Download XPI file with caching.

        First checks cache, then downloads if not found or force_download=True.

        Args:
            url: Download URL.
            filename: Target filename.
            force_download: Force download even if cached.

        Returns:
            Path to downloaded file or None if failed.
        """
        runtime_path = self.runtime_dir / filename
        cache_path = self.cache_dir / filename

        # Check if file exists in runtime directory
        if not force_download and runtime_path.exists():
            logger.debug(f"Using existing file: {filename}")
            return runtime_path

        # Check if file exists in cache
        if not force_download and cache_path.exists():
            try:
                shutil.copy2(cache_path, runtime_path)
                logger.debug(f"Copied from cache: {filename}")
                return runtime_path
            except Exception as e:
                logger.warning(f"Failed to copy from cache: {e}")

        # Download file
        try:
            return self._download_file(url, runtime_path, cache_path)
        except Exception as e:
            logger.error(f"Download failed for {filename}: {e}")

            # Try once more with force
            if not force_download:
                logger.info(f"Retrying download for {filename}")
                try:
                    return self._download_file(url, runtime_path, cache_path)
                except Exception as e2:
                    logger.error(f"Retry failed for {filename}: {e2}")

            return None

    def _download_file(
        self,
        url: str,
        runtime_path: Path,
        cache_path: Path,
    ) -> Path:
        """Download file from URL.

        Args:
            url: Download URL.
            runtime_path: Target path in runtime directory.
            cache_path: Target path in cache directory.

        Returns:
            Path to downloaded file.

        Raises:
            DownloadError: If download fails.
        """
        try:
            response = self.get(url, stream=True)
            response.raise_for_status()

            # Write to runtime directory
            with open(runtime_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)

            # Copy to cache
            try:
                shutil.copy2(runtime_path, cache_path)
            except Exception as e:
                logger.warning(f"Failed to cache file: {e}")

            logger.info(f"Downloaded: {runtime_path.name}")
            return runtime_path

        except Exception as e:
            # Clean up partial file
            if runtime_path.exists():
                try:
                    runtime_path.unlink()
                except Exception:
                    pass
            raise DownloadError(f"Download failed: {url}") from e

    def clear_runtime(self) -> None:
        """Clear runtime directory."""
        if self.runtime_dir.exists():
            for file in self.runtime_dir.iterdir():
                if file.is_file():
                    try:
                        file.unlink()
                    except Exception as e:
                        logger.warning(f"Failed to delete {file}: {e}")
