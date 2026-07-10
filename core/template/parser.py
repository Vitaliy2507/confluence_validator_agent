"""Parse the Confluence template page into a list of :class:`TemplateRule`.

The template page marks each section's requirement level near its heading
— sometimes as the full phrase "Требование к ведению - обязательно",
sometimes as a short standalone label/badge (e.g. a colored Confluence
"status" macro reading just "ОБЯЗАТЕЛЬНО" or "Опционально", or an
adjective form like "Обязательный раздел") right after the heading. This
module recognizes all of these forms, using only the sections already
split out by ``parsers.html_parser``.

Default policy: a section is only mandatory if the template page
*explicitly* says so. Anything ambiguous (marker missing, misspelled,
using different wording than expected) is treated as optional rather than
mandatory — a false "optional" only produces a soft warning, while a
false "mandatory" would fail real pages for reasons nobody could see
coming. When in doubt, don't block.

Only headings numbered like "N" or "N.M" (matching the template's own
table of contents, e.g. "6.5 Функциональное требование") AND rendered as
a real heading tag (h1/h2, not nested deeper) become checklist rules.
Sections routinely embed an illustrative example under one of their
sub-sections — e.g. 6.5 shows a worked example of *one* functional
requirement, complete with its own "Запрос"/"Ответ"/"Статусная модель"
sub-headings, sometimes even restarting its own short numbering ("1.",
"2." ...) — to demonstrate how an author should structure their own
content. Those example sub-headings document *how to fill in* section
6.5; they are not themselves separate checklist items. Two independent
signals are used to filter them out: (1) they are virtually always
rendered as a deeper heading tag (h3+) than the real outline (h1/h2), and
(2) even when they happen to carry a shallow-looking number, that number
restarts from 1 rather than continuing the template's own N.M outline
depth. Either signal alone can be wrong for a given page's markup quirks,
so both are checked together.
"""

from __future__ import annotations

import re

from models.section import Section, TemplateRule
from parsers.text_cleaner import normalize
from utils.logger import get_logger

logger = get_logger(__name__)

# Full-phrase form: "Требование к ведению - обязательно/опционально".
_REQUIRED_PHRASE_PATTERN = re.compile(r"требование к ведению\s*-\s*обязательн")
_OPTIONAL_PHRASE_PATTERN = re.compile(r"требование к ведению\s*-\s*опциональн")

# Short badge/label form: just the word itself (e.g. a Confluence "status"
# macro rendered right after the heading, no surrounding sentence).
# Matches both the adverb ("обязательно") and adjective ("обязательный",
# "обязательная", ...) forms via the \w* stem. Only checked within the
# first _LABEL_WINDOW_CHARS of the section's content, since that's where
# a heading-adjacent label lives — searching the whole section body would
# risk matching the word used in unrelated prose further down the page.
# The negative lookbehind guards against "не обязательно" being read as a
# positive marker.
_REQUIRED_WORD_PATTERN = re.compile(r"(?<!не )\bобязательн(?:о|ый|ая|ое|ые|ым|ом|ых)\b")
_OPTIONAL_WORD_PATTERN = re.compile(r"\bопциональн(?:о|ый|ая|ое|ые|ым|ом|ых)\b")
_LABEL_WINDOW_CHARS = 200

_ID_PATTERN = re.compile(r"^\s*(\d+(?:\.\d+)*)")

# Only headings numbered "N" or "N.M" (at most one dot) are treated as
# checklist items. Deeper numbering (e.g. "6.5.1") or headings with no
# leading number at all are example/descriptive content nested inside a
# real section, not sections of their own.
_MAX_RULE_DEPTH = 2

# Only headings rendered as h1/h2 are treated as checklist items. The
# template's own outline never nests real sections past two heading
# levels; anything deeper is descriptive/example content, regardless of
# what number (if any) happens to be typed in front of it.
_MAX_HEADING_LEVEL = 2


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


def _detect_required(normalized_content: str, header: str) -> bool:
    """Determine whether a section's content marks it as mandatory.

    Recognizes both the full "Требование к ведению - обязательно" phrase
    (searched across the whole section) and a short standalone
    "обязательно"/"обязательный"/"опционально"/... label/badge (searched
    only in the text immediately following the heading, to avoid false
    positives from the word appearing later in unrelated prose).

    Args:
        normalized_content: Lowercased, whitespace-normalized section text.
        header: Original heading text, used only for debug logging.

    Returns:
        True if the section is explicitly marked mandatory, False
        otherwise (the safe default — see module docstring).
    """
    if _REQUIRED_PHRASE_PATTERN.search(normalized_content):
        return True
    if _OPTIONAL_PHRASE_PATTERN.search(normalized_content):
        return False

    label_window = normalized_content[:_LABEL_WINDOW_CHARS]
    if _REQUIRED_WORD_PATTERN.search(label_window):
        return True
    if _OPTIONAL_WORD_PATTERN.search(label_window):
        return False

    logger.debug(
        'No "обязательно/опционально" marker found for template section '
        '"%s"; defaulting to optional.',
        header.strip(),
    )
    return False


def parse_template_sections(sections: list[Section]) -> list[TemplateRule]:
    """Convert parsed template-page sections into template rules.

    Args:
        sections: Sections produced by ``parsers.html_parser.parse_sections``
            for the raw HTML of the Confluence template page.

    Returns:
        List of :class:`TemplateRule`, in document order. Only headings
        numbered "N" or "N.M" *and* rendered as h1/h2 become rules (see
        module docstring); a section is marked ``required`` only when the
        page explicitly says "обязательно" for it. A section explicitly
        marked "опционально", or with no marker at all, becomes
        ``required=False`` — unmarked sections are never upgraded to
        mandatory.
    """
    rules: list[TemplateRule] = []
    parent_by_level: dict[int, str] = {}
    order = 0

    for section in sections:
        if not section.header or section.level == 0:
            continue

        if section.level > _MAX_HEADING_LEVEL:
            logger.debug(
                'Skipping "%s" — rendered as h%d, deeper than the '
                "template's own h1/h2 outline; treated as example content.",
                section.header.strip(),
                section.level,
            )
            continue

        id_match = _ID_PATTERN.match(section.header.strip())
        section_id = id_match.group(1) if id_match else None

        if section_id is None:
            # No "N"/"N.M" numbering at all — descriptive/example content
            # nested inside a real checklist section, not a section of
            # its own. Skip, but don't touch parent_by_level: it isn't a
            # heading level that ever becomes a parent for anything else.
            logger.debug(
                'Skipping unnumbered heading "%s" — treated as example '
                "content, not a checklist section.",
                section.header.strip(),
            )
            continue

        depth = section_id.count(".") + 1
        if depth > _MAX_RULE_DEPTH:
            logger.debug(
                'Skipping "%s" (numbered %s) — deeper than the template\'s '
                "own N.M outline, treated as example content.",
                section.header.strip(),
                section_id,
            )
            continue

        normalized_content = normalize(section.content)
        required = _detect_required(normalized_content, section.header)

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
