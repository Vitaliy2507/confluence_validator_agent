"""Unit tests for ValidatorAgent using the bundled sample_page.html fixture."""

from __future__ import annotations

import json
import os
import unittest

from core.agents.validator import ValidatorAgent
from models.section import TemplateRule
from parsers.html_parser import parse_sections

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")
TEMPLATE_RULES_PATH = os.path.join(
    os.path.dirname(__file__), "..", "config", "template_rules.json"
)


def _load_sample_sections():
    with open(os.path.join(FIXTURES_DIR, "sample_page.html"), "r", encoding="utf-8") as f:
        html = f.read()
    return parse_sections(html)


def _load_rules():
    with open(TEMPLATE_RULES_PATH, "r", encoding="utf-8") as f:
        payload = json.load(f)
    return [TemplateRule.from_dict(r) for r in payload["data"]]


class ValidatorAgentTests(unittest.TestCase):
    """Covers SCENARIO_1, SCENARIO_2 and SCENARIO_3 from the spec."""

    def setUp(self) -> None:
        self.validator = ValidatorAgent()
        self.rules = _load_rules()
        self.sections = _load_sample_sections()

    def test_full_page_is_valid(self) -> None:
        """SCENARIO_1: all mandatory sections present -> valid, no errors."""
        result = self.validator.validate(self.sections, self.rules)
        self.assertTrue(result.is_valid)
        self.assertEqual(result.errors, [])

    def test_missing_mandatory_section_fails_validation(self) -> None:
        """SCENARIO_2: missing 'Архитектура' -> invalid with an error."""
        sections_without_architecture = [
            s for s in self.sections if "архитектур" not in s.header.lower()
        ]
        result = self.validator.validate(sections_without_architecture, self.rules)
        self.assertFalse(result.is_valid)
        self.assertTrue(any("Архитектура" in e.section for e in result.errors))

    def test_missing_optional_section_gives_warning_not_error(self) -> None:
        """SCENARIO_3: missing optional 'Связная документация' -> still valid."""
        # The sample page never included section 2 in the first place.
        result = self.validator.validate(self.sections, self.rules)
        self.assertTrue(result.is_valid)
        self.assertTrue(
            any("Связная документация" in w for w in result.warnings),
            msg=result.warnings,
        )


if __name__ == "__main__":
    unittest.main()
