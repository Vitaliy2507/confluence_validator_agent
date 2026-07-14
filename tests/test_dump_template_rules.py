"""Tests for Orchestrator.dump_template_rules() and the corresponding
--dump-template-rules CLI flag.
"""

from __future__ import annotations

import io
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest.mock import MagicMock, patch

import main as main_module
from config.settings import (
    ConfluenceSettings,
    GigaChatSettings,
    LoggingSettings,
    RetrySettings,
    Settings,
    TemplateSettings,
)
from core.orchestrator import Orchestrator
from models.page import Page


def _fake_template_html() -> str:
    return (
        "<h1>1. Основные определения</h1>"
        "<p>Обязательный раздел</p>"
        "<h1>2. Связная документация</h1>"
        "<p>Опциональный раздел</p>"
    )


def _make_settings(cache_file: str) -> Settings:
    return Settings(
        confluence=ConfluenceSettings(url="https://example.atlassian.net/wiki", token="x", user="x"),
        gigachat=GigaChatSettings(
            url="https://gigachat.example.com/api/v1",
            auth_url="https://oauth.example.com/api/v2/oauth",
            client_id="cid",
            client_secret="secret",
            scope="GIGACHAT_API_PERS",
            model="GigaChat",
        ),
        template=TemplateSettings(page_id="999", cache_ttl=86400, cache_file=cache_file),
        retry=RetrySettings(max_attempts=1, delay=0, backoff=1),
        logging=LoggingSettings(level="INFO", file="validator.log"),
    )


class DumpTemplateRulesTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp_dir = tempfile.TemporaryDirectory()
        cache_file = os.path.join(self._tmp_dir.name, "template_rules.json")
        self.settings = _make_settings(cache_file)
        self.orchestrator = Orchestrator(self.settings)

        page = Page(page_id="999", title="Шаблон", raw_html=_fake_template_html(), version=1)
        self._get_page_patch = patch.object(
            self.orchestrator._confluence, "get_page", return_value=page
        )
        self._get_page_patch.start()

    def tearDown(self) -> None:
        self._get_page_patch.stop()
        self._tmp_dir.cleanup()

    def test_dump_includes_required_and_optional_sections(self) -> None:
        table = self.orchestrator.dump_template_rules()
        self.assertIn("Основные определения", table)
        self.assertIn("Связная документация", table)
        self.assertIn("Всего правил: 2", table)
        self.assertIn("Обязательных: 1", table)
        self.assertIn("Опциональных: 1", table)

    def test_dump_states_it_is_a_live_parse(self) -> None:
        table = self.orchestrator.dump_template_rules()
        self.assertIn("только что распарсены с живой страницы", table)

    def test_dump_does_not_post_any_comment(self) -> None:
        with patch.object(self.orchestrator._confluence, "post_comment") as mock_post:
            self.orchestrator.dump_template_rules()
        mock_post.assert_not_called()

    def test_dump_states_stale_fallback_when_live_parse_finds_nothing(self) -> None:
        # Prime the cache with a real result first.
        self.orchestrator.dump_template_rules()

        # Then simulate a template page with no recognizable headings.
        empty_page = Page(page_id="999", title="Шаблон", raw_html="<p>ничего</p>", version=2)
        self._get_page_patch.stop()
        with patch.object(self.orchestrator._confluence, "get_page", return_value=empty_page):
            table = self.orchestrator.dump_template_rules(refresh_template=True)
        self._get_page_patch.start()

        self.assertIn("ВНИМАНИЕ", table)
        self.assertIn("--dump-template-sections", table)


class DumpTemplateSectionsTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp_dir = tempfile.TemporaryDirectory()
        cache_file = os.path.join(self._tmp_dir.name, "template_rules.json")
        self.settings = _make_settings(cache_file)
        self.orchestrator = Orchestrator(self.settings)

    def tearDown(self) -> None:
        self._tmp_dir.cleanup()

    def test_dump_sections_lists_raw_headings_unfiltered(self) -> None:
        html = (
            "<h1>1. Основные определения</h1><p>Обязательно</p>"
            "<h3>Пример без номера</h3><p>Это пример, не пункт чек-листа.</p>"
        )
        page = Page(page_id="999", title="Шаблон", raw_html=html, version=1)
        with patch.object(self.orchestrator._confluence, "get_page", return_value=page):
            output = self.orchestrator.dump_template_sections()

        # Unlike dump_template_rules, this must show EVERY heading found,
        # including the unnumbered h3 example that the rule filters reject.
        self.assertIn("Основные определения", output)
        self.assertIn("Пример без номера", output)
        self.assertIn("h1", output)
        self.assertIn("h3", output)

    def test_dump_sections_warns_when_no_headings_found_at_all(self) -> None:
        page = Page(page_id="999", title="Шаблон", raw_html="<p>просто текст</p>", version=1)
        with patch.object(self.orchestrator._confluence, "get_page", return_value=page):
            output = self.orchestrator.dump_template_sections()
        self.assertIn("Ни одного реального заголовка", output)

    def test_dump_sections_does_not_post_any_comment(self) -> None:
        page = Page(page_id="999", title="Шаблон", raw_html="<h1>1. X</h1>", version=1)
        with patch.object(self.orchestrator._confluence, "get_page", return_value=page), \
             patch.object(self.orchestrator._confluence, "post_comment") as mock_post:
            self.orchestrator.dump_template_sections()
        mock_post.assert_not_called()


class DumpTemplateRulesCLITests(unittest.TestCase):
    """Verifies the --dump-template-rules flag wires through main()."""

    def test_dump_flag_does_not_require_page_id(self) -> None:
        fake_orchestrator = MagicMock()
        fake_orchestrator.dump_template_rules.return_value = "TABLE"

        with patch.object(main_module, "get_settings", return_value=MagicMock()), \
             patch.object(main_module, "setup_logging"), \
             patch.object(main_module, "Orchestrator", return_value=fake_orchestrator):
            buf = io.StringIO()
            with redirect_stdout(buf):
                exit_code = main_module.main(["--dump-template-rules"])

        self.assertEqual(exit_code, 0)
        self.assertIn("TABLE", buf.getvalue())
        fake_orchestrator.dump_template_rules.assert_called_once_with(refresh_template=False)

    def test_missing_page_id_without_dump_flag_fails_cleanly(self) -> None:
        fake_orchestrator = MagicMock()

        with patch.object(main_module, "get_settings", return_value=MagicMock()), \
             patch.object(main_module, "setup_logging"), \
             patch.object(main_module, "Orchestrator", return_value=fake_orchestrator):
            exit_code = main_module.main([])

        self.assertEqual(exit_code, 1)
        fake_orchestrator.run.assert_not_called()

    def test_dump_sections_flag_does_not_require_page_id(self) -> None:
        fake_orchestrator = MagicMock()
        fake_orchestrator.dump_template_sections.return_value = "SECTIONS"

        with patch.object(main_module, "get_settings", return_value=MagicMock()), \
             patch.object(main_module, "setup_logging"), \
             patch.object(main_module, "Orchestrator", return_value=fake_orchestrator):
            buf = io.StringIO()
            with redirect_stdout(buf):
                exit_code = main_module.main(["--dump-template-sections"])

        self.assertEqual(exit_code, 0)
        self.assertIn("SECTIONS", buf.getvalue())
        fake_orchestrator.dump_template_sections.assert_called_once_with()
        fake_orchestrator.dump_template_rules.assert_not_called()
        fake_orchestrator.run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
