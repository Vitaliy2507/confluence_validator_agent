"""Model representing a Confluence page fetched via the REST API."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Page:
    """Represents a single Confluence page.

    Attributes:
        page_id: Confluence content id.
        title: Page title.
        raw_html: Raw storage-format HTML body (``body.storage.value``).
        version: Current version number of the page.
        raw_response: Full raw JSON payload returned by Confluence, kept for
            debugging and for any future field extraction needs.
    """

    page_id: str
    title: str
    raw_html: str
    version: int
    raw_response: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_confluence_json(cls, data: dict[str, Any]) -> "Page":
        """Build a :class:`Page` from a raw Confluence ``get_page`` response.

        Args:
            data: JSON payload returned by ``GET /rest/api/content/{page_id}``.

        Returns:
            A populated :class:`Page` instance.
        """
        body = data.get("body", {}).get("storage", {}).get("value", "")
        version = data.get("version", {}).get("number", 0)
        return cls(
            page_id=str(data.get("id", "")),
            title=data.get("title", ""),
            raw_html=body,
            version=int(version) if version else 0,
            raw_response=data,
        )
