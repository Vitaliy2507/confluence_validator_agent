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

    def test_unnumbered_heading_is_not_a_rule(self) -> None:
        """Illustrative sub-headings without a number (e.g. "Запрос" inside
        an example under 6.5) must not become checklist items.
        """
        sections = [
            Section(
                header="6.5 Функционально требование ХХХ",
                level=2,
                content="Требование к ведению - опционально",
                raw_html="",
            ),
            Section(
                header="Запрос",
                level=3,
                content="Пример запроса для топика.",
                raw_html="",
            ),
        ]
        rules = parse_template_sections(sections)
        names = [r.name for r in rules]
        self.assertIn("Функционально требование ХХХ", names)
        self.assertNotIn("Запрос", names)

    def test_deeply_numbered_heading_is_not_a_rule(self) -> None:
        """Numbering deeper than "N.M" (e.g. "6.5.1") is an example
        sub-step, not a top-level checklist section.
        """
        sections = [
            Section(
                header="6.5 Функционально требование ХХХ",
                level=2,
                content="Требование к ведению - опционально",
                raw_html="",
            ),
            Section(
                header="6.5.1 Создание нового топика",
                level=3,
                content="Пример.",
                raw_html="",
            ),
        ]
        rules = parse_template_sections(sections)
        names = [r.name for r in rules]
        self.assertIn("Функционально требование ХХХ", names)
        self.assertNotIn("Создание нового топика", names)

    def test_top_level_and_second_level_numbering_are_kept(self) -> None:
        sections = [
            Section(header="6. Функциональные требования", level=1, content="", raw_html=""),
            Section(
                header="6.1 Диаграмма последовательности",
                level=2,
                content="Требование к ведению - обязательно",
                raw_html="",
            ),
        ]
        rules = parse_template_sections(sections)
        names = [r.name for r in rules]
        self.assertIn("Функциональные требования", names)
        self.assertIn("Диаграмма последовательности", names)

    def test_shallow_numbered_but_deep_heading_level_is_not_a_rule(self) -> None:
        """An example step that restarts its own numbering ("1.", "2." ...)
        at a deep heading level (h3+) must still be excluded — shallow
        numbers alone aren't enough of a signal once they collide with the
        real N/N.M ids.
        """
        sections = [
            Section(
                header="6.5 Функционально требование ХХХ",
                level=2,
                content="Обязательный раздел",
                raw_html="",
            ),
            Section(
                header="1. Создание нового топика",
                level=3,
                content="Пример шага внутри примера.",
                raw_html="",
            ),
        ]
        rules = parse_template_sections(sections)
        names = [r.name for r in rules]
        self.assertIn("Функционально требование ХХХ", names)
        self.assertNotIn("Создание нового топика", names)

    def test_adjective_form_required_label_is_required(self) -> None:
        """'Обязательный раздел' (adjective) must be recognized, not just
        the adverb form 'обязательно'.
        """
        sections = [
            Section(header="8. Метки", level=1, content="Обязательный раздел", raw_html="")
        ]
        rules = parse_template_sections(sections)
        self.assertEqual(len(rules), 1)
        self.assertTrue(rules[0].required)

    def test_adjective_form_optional_label_is_optional(self) -> None:
        sections = [
            Section(
                header="2. Связная документация",
                level=1,
                content="Опциональный раздел",
                raw_html="",
            )
        ]
        rules = parse_template_sections(sections)
        self.assertEqual(len(rules), 1)
        self.assertFalse(rules[0].required)

    def test_short_required_label_is_required(self) -> None:
        """Short badge-style label ('Обязательно' right after the heading,
        no surrounding phrase) must also be recognized.
        """
        sections = [
            Section(header="8. Метки", level=1, content="Обязательно", raw_html="")
        ]
        rules = parse_template_sections(sections)
        self.assertEqual(len(rules), 1)
        self.assertTrue(rules[0].required)

    def test_short_optional_label_is_optional(self) -> None:
        sections = [
            Section(header="2. Связная документация", level=1, content="Опционально", raw_html="")
        ]
        rules = parse_template_sections(sections)
        self.assertEqual(len(rules), 1)
        self.assertFalse(rules[0].required)

    def test_negated_required_word_does_not_count_as_required(self) -> None:
        sections = [
            Section(
                header="8. Метки",
                level=1,
                content="Не обязательно для черновиков.",
                raw_html="",
            )
        ]
        rules = parse_template_sections(sections)
        self.assertEqual(len(rules), 1)
        self.assertFalse(rules[0].required)

    def test_required_word_far_into_body_is_not_treated_as_marker(self) -> None:
        """A mention of the word deep in unrelated prose (beyond the
        heading-adjacent label window) must not flip requirement status.
        """
        padding = "текст " * 60  # pushes well past the label window
        sections = [
            Section(
                header="8. Метки",
                level=1,
                content=f"{padding} где-то тут упоминается слово обязательно.",
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
