"""Unit tests for TemplateLoader: caching, TTL, and force_refresh."""

from __future__ import annotations

import os
import tempfile
import unittest
from unittest.mock import MagicMock

from config.settings import RetrySettings
from core.template.loader import TemplateLoader
from models.page import Page
from models.section import TemplateRule
from parsers.html_parser import parse_sections


def _fake_template_html() -> str:
    return (
        "<h1>1. Раздел А</h1>"
        "<p>Требование к ведению - обязательно</p>"
        "<h1>2. Раздел Б</h1>"
        "<p>Требование к ведению - опционально</p>"
    )


class TemplateLoaderTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp_dir = tempfile.TemporaryDirectory()
        self.cache_file = os.path.join(self._tmp_dir.name, "template_rules.json")
        self.retry = RetrySettings(max_attempts=1, delay=0, backoff=1)

        self.client = MagicMock()
        page = Page(
            page_id="999",
            title="Шаблон",
            raw_html=_fake_template_html(),
            version=1,
        )
        self.client.get_page.return_value = page

    def tearDown(self) -> None:
        self._tmp_dir.cleanup()

    def _make_loader(self, ttl: int) -> TemplateLoader:
        return TemplateLoader(
            confluence_client=self.client,
            template_page_id="999",
            cache_file=self.cache_file,
            cache_ttl=ttl,
        )

    def test_first_load_fetches_from_confluence(self) -> None:
        loader = self._make_loader(ttl=86400)
        rules = loader.load()
        self.assertEqual(self.client.get_page.call_count, 1)
        self.assertTrue(any(r.required for r in rules))

    def test_second_load_within_ttl_uses_cache_not_confluence(self) -> None:
        loader = self._make_loader(ttl=86400)
        loader.load()
        loader.load()
        self.assertEqual(
            self.client.get_page.call_count,
            1,
            "second call within TTL should not hit Confluence again",
        )

    def test_force_refresh_bypasses_fresh_cache(self) -> None:
        loader = self._make_loader(ttl=86400)
        loader.load()
        loader.load(force_refresh=True)
        self.assertEqual(
            self.client.get_page.call_count,
            2,
            "force_refresh=True must re-fetch even when cache is still fresh",
        )

    def test_expired_ttl_triggers_refetch_without_force(self) -> None:
        loader = self._make_loader(ttl=0)
        loader.load()
        loader.load()
        self.assertEqual(
            self.client.get_page.call_count,
            2,
            "a TTL of 0 means the cache is immediately stale on the next call",
        )


if __name__ == "__main__":
    unittest.main()
