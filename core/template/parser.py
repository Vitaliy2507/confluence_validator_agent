"""Parse the Confluence template page into a list of :class:`TemplateRule`.

The template page marks each section with a line such as "Требование к
ведению - обязательно" or "Требование к ведению - опционально" near the
heading. This module derives the mandatory/optional rule set generically
from that pattern, using only the sections already split out by
``parsers.html_parser``.

Default policy: a section is only mandatory if the template page
*explicitly* says so. Anything ambiguous (marker missing, misspelled,
using different wording than expected) is treated as optional rather than
mandatory — a false "optional" only produces a soft warning, while a
false "mandatory" would fail real pages for reasons nobody could see
coming. When in doubt, don't block.
"""

from __future__ import annotations

import re

from models.section import Section, TemplateRule
from parsers.text_cleaner import normalize
from utils.logger import get_logger

logger = get_logger(__name__)

_REQUIRED_PATTERN = re.compile(r"требование к ведению\s*-\s*обязательно")
_OPTIONAL_PATTERN = re.compile(r"требование к ведению\s*-\s*опционально")
_ID_PATTERN = re.compile(r"^\s*(\d+(?:\.\d+)*)")


def _extract_keywords(header: str, section_id: str | None) -> list[str]:
    """Derive simple keyword aliases from a heading's text.

    Args:
        header: Raw heading text, e.g. "4.1 Цель".
        section_id: Extracted numeric id, e.g. "4.1", if present.

    Returns:
        A small list of lowercase keywords usable for fuzzy matching.
    """
    text = normalize(header)
    text_no_id = _ID_PATTERN.sub("", text).strip()
    keywords = [k for k in {text_no_id, text} if k]
    if section_id:
        keywords.append(section_id)
    return keywords


def parse_template_sections(sections: list[Section]) -> list[TemplateRule]:
    """Convert parsed template-page sections into template rules.

    Args:
        sections: Sections produced by ``parsers.html_parser.parse_sections``
            for the raw HTML of the Confluence template page.

    Returns:
        List of :class:`TemplateRule`, in document order. Every heading on
        the template page becomes a rule; a section is marked ``required``
        only when the page explicitly says "обязательно" for it. A
        section explicitly marked "опционально", or with no marker at
        all, becomes ``required=False`` — unmarked sections are never
        upgraded to mandatory.
    """
    rules: list[TemplateRule] = []
    parent_by_level: dict[int, str] = {}
    order = 0

    for section in sections:
        if not section.header or section.level == 0:
            continue

        normalized_content = normalize(section.content)
        if _REQUIRED_PATTERN.search(normalized_content):
            required = True
        else:
            # Either explicitly "опционально", or no marker at all — both
            # cases default to optional. We don't distinguish them here
            # because an unrecognized marker should degrade safely, not
            # silently become a hard requirement.
            required = False
            if not _OPTIONAL_PATTERN.search(normalized_content):
                logger.debug(
                    'No "обязательно/опционально" marker found for template '
                    'section "%s"; defaulting to optional.',
                    section.header.strip(),
                )

        id_match = _ID_PATTERN.match(section.header.strip())
        section_id = id_match.group(1) if id_match else None
        name = _ID_PATTERN.sub("", section.header).strip(" .-:") or section.header.strip()

        parent = parent_by_level.get(section.level - 1)
        parent_by_level[section.level] = name

        order += 1
        rules.append(
            TemplateRule(
                name=name,
                keywords=_extract_keywords(section.header, section_id),
                required=required,
                level=section.level,
                order=order,
                parent=parent,
            )
        )

    return rules
