"""Plain-text extraction/normalization helpers built on ``html.parser``."""

from __future__ import annotations

import re
from html.parser import HTMLParser


class _TextExtractor(HTMLParser):
    """Internal HTMLParser subclass that collects visible text content."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._chunks: list[str] = []

    def handle_data(self, data: str) -> None:
        if data.strip():
            self._chunks.append(data.strip())

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        # Insert separators so table cells / list items / paragraphs don't
        # run together without whitespace.
        if tag in ("br", "p", "tr", "li", "h1", "h2", "h3", "h4", "h5", "h6"):
            self._chunks.append("\n")
        elif tag == "td" or tag == "th":
            self._chunks.append(" | ")

    def get_text(self) -> str:
        return " ".join(self._chunks)


def strip_html(html: str) -> str:
    """Convert an HTML fragment to normalized plain text.

    Args:
        html: Raw HTML (Confluence storage format or plain HTML).

    Returns:
        Plain text with tags removed and whitespace collapsed.
    """
    extractor = _TextExtractor()
    extractor.feed(html)
    extractor.close()
    text = extractor.get_text()
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n", text)
    text = re.sub(r"\s*\|\s*\|\s*", " | ", text)
    return text.strip()


def normalize(text: str) -> str:
    """Lowercase and collapse whitespace for keyword matching purposes.

    Args:
        text: Arbitrary text (e.g. a heading).

    Returns:
        Normalized text suitable for substring/keyword comparisons.
    """
    return re.sub(r"\s+", " ", text).strip().lower()


def is_effectively_empty(text: str) -> bool:
    """Return True if plain text content is empty or only placeholder noise.

    Used to detect sections that only contain empty tags like ``<p></p>``
    (SCENARIO_5 in the spec's test scenarios).

    Args:
        text: Plain text already extracted via :func:`strip_html`.

    Returns:
        True if the text carries no real content.
    """
    cleaned = text.strip().strip("|").strip()
    return len(cleaned) == 0
