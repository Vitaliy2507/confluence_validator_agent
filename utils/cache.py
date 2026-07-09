"""Simple JSON-file based cache with a time-to-live (TTL)."""

from __future__ import annotations

import json
import os
import time
from typing import Any

from utils.logger import get_logger

logger = get_logger(__name__)


class JSONCache:
    """A tiny file-backed cache storing a single JSON payload plus a
    timestamp, used to avoid re-fetching the Confluence template page on
    every run.
    """

    def __init__(self, path: str, ttl_seconds: int) -> None:
        """Initialize the cache.

        Args:
            path: Path to the JSON cache file on disk.
            ttl_seconds: Number of seconds the cached payload stays fresh.
        """
        self.path = path
        self.ttl_seconds = ttl_seconds

    def is_fresh(self) -> bool:
        """Return True if a cache file exists and has not expired."""
        if not os.path.exists(self.path):
            return False
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                payload = json.load(f)
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Cache file %s is unreadable: %s", self.path, exc)
            return False

        cached_at = payload.get("_cached_at", 0)
        age = time.time() - cached_at
        return age < self.ttl_seconds

    def load(self) -> Any:
        """Load and return the cached payload's ``data`` field.

        Returns:
            The cached data, or None if the cache is missing/corrupt.
        """
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                payload = json.load(f)
            return payload.get("data")
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Failed to load cache %s: %s", self.path, exc)
            return None

    def save(self, data: Any) -> None:
        """Persist ``data`` to the cache file, stamped with the current time.

        Args:
            data: JSON-serializable payload to store.
        """
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        payload = {"_cached_at": time.time(), "data": data}
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        logger.info("Cache written to %s", self.path)
