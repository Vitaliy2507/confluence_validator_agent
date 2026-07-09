"""ExtractorAgent: pulls the technical sections needed for the GigaChat prompt."""

from __future__ import annotations

import re

from models.section import Section
from parsers.text_cleaner import is_effectively_empty, normalize
from utils.logger import get_logger

logger = get_logger(__name__)

NO_DATA_PLACEHOLDER = "Нет данных"


def _keyword_matches(header_norm: str, keyword: str) -> bool:
    """Check whether ``keyword`` matches inside a normalized header.

    Purely numeric-looking keywords (e.g. "6.5") use a word-boundary match
    so that "6.5" does not falsely match a sub-section heading like
    "6.5.1 Создание нового топика". Textual keywords fall back to a plain
    substring match.
    """
    if re.fullmatch(r"\d+(\.\d+)*", keyword):
        pattern = r"(^|\s)" + re.escape(keyword) + r"(\s|$)"
        return re.search(pattern, header_norm) is not None
    return keyword.lower() in header_norm


class ExtractorAgent:
    """Extracts the raw text of the technical sections (ER model,
    integrations, functional requirements/Kafka) that feed the GigaChat
    summarization prompt.
    """

    def __init__(self, technical_sections: list[dict]) -> None:
        """Initialize the extractor.

        Args:
            technical_sections: Configuration list (from
                ``config.settings.TECHNICAL_SECTIONS``) describing which
                sections to pull and under which prompt template key.
        """
        self._technical_sections = technical_sections

    def extract(self, sections: list[Section]) -> dict[str, str]:
        """Extract text content for each configured technical section.

        Args:
            sections: Flat, ordered list of sections parsed from the page.

        Returns:
            Mapping of ``prompt_key`` -> extracted plain text (or the
            "Нет данных" placeholder if the section is missing/empty).
        """
        result: dict[str, str] = {}
        for spec in self._technical_sections:
            content = self._extract_one(sections, spec["keywords"])
            result[spec["prompt_key"]] = content
            logger.info(
                "Extracted section '%s': %s",
                spec["name"],
                "empty" if content == NO_DATA_PLACEHOLDER else f"{len(content)} chars",
            )
        return result

    @staticmethod
    def _find_index(sections: list[Section], keywords: list[str]) -> int | None:
        for idx, section in enumerate(sections):
            if not section.header:
                continue
            header_norm = normalize(section.header)
            if any(_keyword_matches(header_norm, keyword) for keyword in keywords):
                return idx
        return None

    def _extract_one(self, sections: list[Section], keywords: list[str]) -> str:
        idx = self._find_index(sections, keywords)
        if idx is None:
            return NO_DATA_PLACEHOLDER

        anchor_level = sections[idx].level or 1
        collected: list[str] = [sections[idx].content]

        for section in sections[idx + 1 :]:
            if section.level and section.level <= anchor_level:
                break
            if section.header:
                collected.append(f"{section.header}: {section.content}")
            else:
                collected.append(section.content)

        text = "\n".join(part for part in collected if part).strip()
        if is_effectively_empty(text):
            return NO_DATA_PLACEHOLDER
        return text
