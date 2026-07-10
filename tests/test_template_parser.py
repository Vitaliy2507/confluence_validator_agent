"""Unit tests for core.template.parser: default-to-optional requirement policy."""

from __future__ import annotations

import unittest

from core.template.parser import parse_template_sections
from models.section import Section, TemplateRule


class TemplateParserRequiredDefaultTests(unittest.TestCase):
    """Guards against the "unmarked sections become mandatory" regression."""

    def test_explicit_required_marker_is_required(self) -> None:
        sections = [
            Section(
                header="4.1 Цель",
                level=2,
                content="Требование к ведению - обязательно",
                raw_html="",
            )
        ]
        rules = parse_template_sections(sections)
        self.assertEqual(len(rules), 1)
        self.assertTrue(rules[0].required)

    def test_explicit_optional_marker_is_optional(self) -> None:
        sections = [
            Section(
                header="4.2 Процесс as-is",
                level=2,
                content="Требование к ведению - опционально",
                raw_html="",
            )
        ]
        rules = parse_template_sections(sections)
        self.assertEqual(len(rules), 1)
        self.assertFalse(rules[0].required)

    def test_missing_marker_defaults_to_optional_not_required(self) -> None:
        """This is the exact regression: no marker at all must NOT become
        required — it must default to optional.
        """
        sections = [
            Section(
                header="9. Раздел без явного маркера",
                level=1,
                content="Просто какой-то текст без пометки обязательности.",
                raw_html="",
            )
        ]
        rules = parse_template_sections(sections)
        self.assertEqual(len(rules), 1)
        self.assertFalse(rules[0].required)

    def test_template_rule_dataclass_default_is_optional(self) -> None:
        rule = TemplateRule(name="Без явного required")
        self.assertFalse(rule.required)

    def test_template_rule_from_dict_missing_required_defaults_to_optional(self) -> None:
        rule = TemplateRule.from_dict({"name": "Без поля required в кэше"})
        self.assertFalse(rule.required)


if __name__ == "__main__":
    unittest.main()
