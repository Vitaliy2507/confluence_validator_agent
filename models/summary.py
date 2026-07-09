"""Model representing the GigaChat-generated summary of technical changes."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Summary:
    """Structured summary of technical changes produced by GigaChat.

    Attributes:
        text: Full markdown text returned by GigaChat (or a fallback
            message if GigaChat was unavailable).
        categories: Optional mapping of category name (БД / REST API /
            Kafka) to its markdown fragment, kept for callers that need
            per-category access.
    """

    text: str
    categories: dict[str, str] = field(default_factory=dict)

    @property
    def is_empty(self) -> bool:
        """Return True if there is effectively no summary content."""
        return not self.text or not self.text.strip()
