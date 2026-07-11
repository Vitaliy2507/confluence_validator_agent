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

    def test_dump_does_not_post_any_comment(self) -> None:
        with patch.object(self.orchestrator._confluence, "post_comment") as mock_post:
            self.orchestrator.dump_template_rules()
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


if __name__ == "__main__":
    unittest.main()
