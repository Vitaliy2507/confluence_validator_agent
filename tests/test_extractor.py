"""Unit tests for ExtractorAgent using the bundled sample_page.html fixture."""

from __future__ import annotations

import os
import unittest

from config.settings import TECHNICAL_SECTIONS
from core.agents.extractor import NO_DATA_PLACEHOLDER, ExtractorAgent
from parsers.html_parser import parse_sections

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


def _load_sample_sections():
    with open(os.path.join(FIXTURES_DIR, "sample_page.html"), "r", encoding="utf-8") as f:
        html = f.read()
    return parse_sections(html)


class ExtractorAgentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.extractor = ExtractorAgent(TECHNICAL_SECTIONS)
        self.sections = _load_sample_sections()

    def test_extracts_er_diagram_table_content(self) -> None:
        result = self.extractor.extract(self.sections)
        self.assertIn("is_verified", result["content_er"])
        self.assertIn("BOOLEAN", result["content_er"])

    def test_extracts_integrations_content(self) -> None:
        result = self.extractor.extract(self.sections)
        self.assertIn("UserService", result["content_integrations"])

    def test_extracts_functional_kafka_subsections(self) -> None:
        result = self.extractor.extract(self.sections)
        self.assertIn("user.verified", result["content_functional"])
        self.assertIn("Создание нового топика", result["content_functional"])
        self.assertIn("Запрос", result["content_functional"])

    def test_missing_section_returns_placeholder(self) -> None:
        """SCENARIO_5: technical section absent -> 'Нет данных' placeholder."""
        sections_without_tech = [
            s
            for s in self.sections
            if "интеграции" not in s.header.lower()
            and "модель предметной области" not in s.header.lower()
            and "функциональное требование" not in s.header.lower()
        ]
        result = self.extractor.extract(sections_without_tech)
        self.assertEqual(result["content_er"], NO_DATA_PLACEHOLDER)
        self.assertEqual(result["content_integrations"], NO_DATA_PLACEHOLDER)
        self.assertEqual(result["content_functional"], NO_DATA_PLACEHOLDER)


if __name__ == "__main__":
    unittest.main()
