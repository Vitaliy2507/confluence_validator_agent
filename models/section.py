"""Models describing a document's structural sections and the template rules
used to validate them.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Section:
    """A single heading-delimited section extracted from a Confluence page.

    Attributes:
        header: Heading text (e.g. "4.1 Цель").
        level: Heading level (1 for h1, 2 for h2, ...).
        content: Plain-text content of the section (tags stripped).
        raw_html: Raw HTML fragment for the section, including nested tags
            such as tables, useful for downstream extraction.
    """

    header: str
    level: int
    content: str
    raw_html: str


@dataclass
class TemplateRule:
    """A single rule describing an expected section in the template.

    Attributes:
        name: Canonical section name (e.g. "Бизнес-требования").
        keywords: Lowercased keywords/aliases used to match this rule
            against headers found on a real page.
        required: Whether the section is mandatory ("обязательно").
            Defaults to False (optional). A section only blocks
            validation if it was *explicitly* marked required on the
            template page or in the rules cache — the absence of a
            marker must never be silently treated as a hard requirement,
            since that would fail pages for reasons the author was never
            told about.
        level: Expected heading level (1 = top level, 2 = sub-section).
        order: Position of the rule within the template, used for stable
            reporting order.
        parent: Name of the parent section, if this is a sub-section.
    """

    name: str
    keywords: list[str] = field(default_factory=list)
    required: bool = False
    level: int = 1
    order: int = 0
    parent: str | None = None

    def matches(self, header_text: str) -> bool:
        """Check whether a given header text satisfies this rule.

        Args:
            header_text: Header text found on the page being validated.

        Returns:
            True if any of the rule's keywords appear in the header text.
        """
        normalized = header_text.strip().lower()
        return any(keyword.lower() in normalized for keyword in self.keywords)

    def to_dict(self) -> dict:
        """Serialize the rule to a plain dict (for JSON caching)."""
        return {
            "name": self.name,
            "keywords": self.keywords,
            "required": self.required,
            "level": self.level,
            "order": self.order,
            "parent": self.parent,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "TemplateRule":
        """Deserialize a rule from a plain dict (loaded from JSON cache).

        ``required`` defaults to False if absent from the cached payload,
        for the same reason as the dataclass default above: an
        unspecified requirement must never be silently upgraded to
        mandatory.
        """
        return cls(
            name=data["name"],
            keywords=list(data.get("keywords", [])),
            required=bool(data.get("required", False)),
            level=int(data.get("level", 1)),
            order=int(data.get("order", 0)),
            parent=data.get("parent"),
        )
