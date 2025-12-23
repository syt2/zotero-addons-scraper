"""Fallback service for merging addon data."""

from typing import Any, Optional

import requests

from ..utils.logging import get_logger

logger = get_logger("services.fallback")


# Constants for fallback association mapping
_UNIQUE_ID_KEY = "p_unique_associated_id##80502300-9DE6-4510-8768-EC42B0EF14E6"
_EXCLUDE_IDS_KEY = "p_exclude_associated_ids##073F5543-C70A-46AA-8529-E05168852D8F"

# Default association map for addon data structure
DEFAULT_ASSOCIATION_MAP: dict[str, Any] = {
    _UNIQUE_ID_KEY: "repo",
    _EXCLUDE_IDS_KEY: ["id"],
    "repo": {
        "releases": {
            _UNIQUE_ID_KEY: "tagName",
            _EXCLUDE_IDS_KEY: ["currentVersion"],
        }
    },
}


class FallbackService:
    """Service for falling back to previous addon data."""

    def __init__(self, association_map: Optional[dict[str, Any]] = None):
        """Initialize fallback service.

        Args:
            association_map: Custom association map for merging.
                           Defaults to DEFAULT_ASSOCIATION_MAP.
        """
        self.association_map = association_map or DEFAULT_ASSOCIATION_MAP

    def apply_fallback(
        self,
        current_data: list[dict[str, Any]],
        previous_url: str,
    ) -> list[dict[str, Any]]:
        """Apply fallback from previous data URL.

        Args:
            current_data: Current addon data list.
            previous_url: URL to fetch previous data from.

        Returns:
            Merged data list.
        """
        try:
            response = requests.get(previous_url, timeout=30)
            response.raise_for_status()
            previous_data = response.json()

            if isinstance(previous_data, list):
                return self._merge_lists(
                    current_data, previous_data, self.association_map
                )
            return current_data

        except Exception as e:
            logger.warning(f"Failed to fetch fallback data from {previous_url}: {e}")
            return current_data

    def _merge_if_needed(
        self,
        current: Any,
        previous: Any,
        association_map: Optional[dict[str, Any]] = None,
    ) -> Any:
        """Recursively merge previous data into current.

        Args:
            current: Current data (dict or list).
            previous: Previous data to merge from.
            association_map: Association mapping for this level.

        Returns:
            Merged data.
        """
        if association_map is None:
            association_map = self.association_map

        if not previous or not current:
            return current

        if not isinstance(previous, type(current)):
            return current

        if isinstance(current, dict):
            return self._merge_dicts(current, previous, association_map)
        elif isinstance(current, list):
            return self._merge_lists(current, previous, association_map)

        return current

    def _merge_dicts(
        self,
        current: dict[str, Any],
        previous: dict[str, Any],
        association_map: dict[str, Any],
    ) -> dict[str, Any]:
        """Merge two dictionaries.

        Args:
            current: Current dictionary.
            previous: Previous dictionary.
            association_map: Association mapping.

        Returns:
            Merged dictionary.
        """
        exclude_keys = association_map.get(_EXCLUDE_IDS_KEY, [])

        for key, value in previous.items():
            # Skip excluded keys
            if key in exclude_keys:
                continue

            if key in current:
                # If current value exists and is a container, recurse
                if isinstance(value, (list, dict)):
                    if current[key]:
                        nested_map = association_map.get(key, {})
                        self._merge_if_needed(current[key], value, nested_map)
                    else:
                        # Current is empty, use previous
                        logger.debug(f"Fallback: {key}")
                        current[key] = value
            else:
                # Key doesn't exist in current, add from previous
                logger.debug(f"Fallback: {key}")
                current[key] = value

        return current

    def _merge_lists(
        self,
        current: list[Any],
        previous: list[Any],
        association_map: dict[str, Any],
    ) -> list[Any]:
        """Merge two lists using unique ID matching.

        Args:
            current: Current list.
            previous: Previous list.
            association_map: Association mapping.

        Returns:
            Merged list.
        """
        unique_key = association_map.get(_UNIQUE_ID_KEY)
        if not unique_key:
            return current

        for prev_item in previous:
            if not isinstance(prev_item, dict):
                continue

            prev_id = prev_item.get(unique_key)
            if not prev_id:
                continue

            # Find matching item in current
            current_item = next(
                (
                    item
                    for item in current
                    if isinstance(item, dict) and item.get(unique_key) == prev_id
                ),
                None,
            )

            if current_item:
                # Merge matching items
                nested_map = association_map.get(unique_key, {})
                self._merge_if_needed(current_item, prev_item, nested_map)

        return current
