"""Split Confluence storage-format HTML into a flat list of Section objects.

Implemented purely with the standard library's :mod:`html.parser` module —
no BeautifulSoup or other third-party HTML libraries are used, per the
project constraints.
"""

from __future__ import annotations

from html.parser import HTMLParser

from models.section import Section
from parsers.text_cleaner import strip_html

_HEADING_TAGS = {"h1": 1, "h2": 2, "h3": 3, "h4": 4, "h5": 5, "h6": 6}


class _SectioningParser(HTMLParser):
    """Walks the HTML tree, cutting a new section every time a heading tag
    is encountered. Everything between one heading and the next (including
    nested tags/tables) becomes that section's raw HTML.
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._sections: list[dict] = []
        self._current_heading_text: list[str] = []
        self._in_heading = False
        self._current_level = 0
        self._current_raw: list[str] = []
        self._tag_stack: list[str] = []

    # -- tag handling ---------------------------------------------------
    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in _HEADING_TAGS:
            self._flush_section()
            self._in_heading = True
            self._current_level = _HEADING_TAGS[tag]
            self._current_heading_text = []
            return
        self._tag_stack.append(tag)
        self._current_raw.append(self._render_starttag(tag, attrs))

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._current_raw.append(self._render_starttag(tag, attrs, self_closing=True))

    def handle_endtag(self, tag: str) -> None:
        if tag in _HEADING_TAGS:
            self._in_heading = False
            return
        if self._tag_stack and self._tag_stack[-1] == tag:
            self._tag_stack.pop()
        self._current_raw.append(f"</{tag}>")

    def handle_data(self, data: str) -> None:
        if self._in_heading:
            self._current_heading_text.append(data)
        else:
            self._current_raw.append(data)

    # -- helpers ----------------------------------------------------------
    @staticmethod
    def _render_starttag(
        tag: str, attrs: list[tuple[str, str | None]], self_closing: bool = False
    ) -> str:
        attr_str = "".join(
            f' {name}="{value}"' if value is not None else f" {name}" for name, value in attrs
        )
        return f"<{tag}{attr_str}{'/' if self_closing else ''}>"

    def _flush_section(self) -> None:
        if self._current_heading_text or self._current_raw:
            header_text = "".join(self._current_heading_text).strip()
            raw_html = "".join(self._current_raw)
            if header_text or raw_html.strip():
                self._sections.append(
                    {
                        "header": header_text,
                        "level": self._current_level or 0,
                        "raw_html": raw_html,
                    }
                )
        self._current_raw = []

    def get_sections(self) -> list[dict]:
        self._flush_section()
        return self._sections


def parse_sections(html: str) -> list[Section]:
    """Parse Confluence storage HTML into an ordered list of sections.

    Content that appears before the first heading is captured as a
    level-0 "preamble" section so no content is silently dropped.

    Args:
        html: Raw HTML body (``body.storage.value``) of a Confluence page.

    Returns:
        List of :class:`Section` objects in document order.
    """
    parser = _SectioningParser()
    parser.feed(html)
    parser.close()

    sections: list[Section] = []
    for raw in parser.get_sections():
        content = strip_html(raw["raw_html"])
        sections.append(
            Section(
                header=raw["header"],
                level=raw["level"],
                content=content,
                raw_html=raw["raw_html"],
            )
        )
    return sections
