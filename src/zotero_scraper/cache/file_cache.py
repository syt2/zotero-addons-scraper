"""File cache management."""

import hashlib
import shutil
from pathlib import Path
from typing import Optional

from ..utils.logging import get_logger

logger = get_logger("cache")


class FileCache:
    """File cache manager for XPI files."""

    def __init__(
        self,
        cache_dir: Path,
        runtime_dir: Path,
        lockfile_name: str = "caches_lockfile",
    ):
        """Initialize file cache.

        Args:
            cache_dir: Directory for cached files.
            runtime_dir: Directory for runtime files.
            lockfile_name: Name of the hash lockfile.
        """
        self.cache_dir = cache_dir
        self.runtime_dir = runtime_dir
        self.lockfile_name = lockfile_name

    def folder_hash(self, directory: Path) -> str:
        """Calculate SHA256 hash of filenames in a directory.

        Args:
            directory: Directory to hash.

        Returns:
            Hex digest of the hash.
        """
        if not directory.exists():
            return ""

        filenames = sorted(f.name for f in directory.iterdir() if f.is_file())
        folder_hash = hashlib.sha256()

        for filename in filenames:
            file_hash = hashlib.sha256(filename.encode("utf-8")).hexdigest()
            folder_hash.update(file_hash.encode("utf-8"))

        return folder_hash.hexdigest()

    def update_cache(self) -> Optional[str]:
        """Update cache from runtime directory.

        Moves runtime directory to cache directory and generates hash.

        Returns:
            Hash of the cached files, or None if failed.
        """
        if not self.cache_dir or not self.runtime_dir:
            return None

        if self.cache_dir == self.runtime_dir:
            logger.warning("Cache and runtime directories are the same")
            return None

        try:
            # Remove old cache
            if self.cache_dir.exists():
                shutil.rmtree(self.cache_dir)

            # Move runtime to cache
            if self.runtime_dir.exists():
                shutil.move(str(self.runtime_dir), str(self.cache_dir))

            # Calculate and save hash
            folder_hash = self.folder_hash(self.cache_dir)
            lockfile_path = self.cache_dir / self.lockfile_name

            with open(lockfile_path, "w", encoding="utf-8") as f:
                f.write(folder_hash)

            logger.info(f"Cache updated: {folder_hash}")
            return folder_hash

        except Exception as e:
            logger.error(f"Update cache failed: {e}")
            return None

    def restore_from_cache(self) -> bool:
        """Restore runtime directory from cache.

        Returns:
            True if successful, False otherwise.
        """
        if not self.cache_dir.exists():
            return False

        try:
            if self.runtime_dir.exists():
                shutil.rmtree(self.runtime_dir)

            shutil.copytree(self.cache_dir, self.runtime_dir)
            logger.info("Restored from cache")
            return True

        except Exception as e:
            logger.error(f"Restore from cache failed: {e}")
            return False

    def clear_runtime(self) -> None:
        """Clear runtime directory."""
        if self.runtime_dir.exists():
            try:
                shutil.rmtree(self.runtime_dir)
                logger.info("Runtime directory cleared")
            except Exception as e:
                logger.error(f"Clear runtime failed: {e}")

    def clear_cache(self) -> None:
        """Clear cache directory."""
        if self.cache_dir.exists():
            try:
                shutil.rmtree(self.cache_dir)
                logger.info("Cache directory cleared")
            except Exception as e:
                logger.error(f"Clear cache failed: {e}")
