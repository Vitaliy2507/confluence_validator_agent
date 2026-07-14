"""Tests for config.settings.validate_settings()."""

from __future__ import annotations

import unittest

from config.settings import (
    ConfluenceSettings,
    GigaChatSettings,
    LoggingSettings,
    RetrySettings,
    Settings,
    TemplateSettings,
    validate_settings,
)


def _make_settings(**overrides) -> Settings:
    confluence = overrides.get(
        "confluence",
        ConfluenceSettings(url="https://example.atlassian.net/wiki", token="tok", user="me"),
    )
    template = overrides.get(
        "template", TemplateSettings(page_id="123", cache_ttl=86400)
    )
    return Settings(
        confluence=confluence,
        gigachat=GigaChatSettings(
            url="https://gigachat.example.com/api/v1",
            auth_url="https://oauth.example.com/api/v2/oauth",
            client_id="",
            client_secret="",
            scope="GIGACHAT_API_PERS",
            model="GigaChat",
        ),
        template=template,
        retry=RetrySettings(),
        logging=LoggingSettings(),
    )


class ValidateSettingsTests(unittest.TestCase):
    def test_fully_configured_settings_have_no_problems(self) -> None:
        settings = _make_settings()
        self.assertEqual(validate_settings(settings), [])

    def test_missing_confluence_url_is_reported(self) -> None:
        settings = _make_settings(
            confluence=ConfluenceSettings(url="", token="tok", user="me")
        )
        problems = validate_settings(settings)
        self.assertTrue(any("CONFLUENCE_URL" in p for p in problems))

    def test_missing_confluence_token_is_reported(self) -> None:
        settings = _make_settings(
            confluence=ConfluenceSettings(url="https://x.atlassian.net", token="", user="me")
        )
        problems = validate_settings(settings)
        self.assertTrue(any("CONFLUENCE_TOKEN" in p for p in problems))

    def test_missing_confluence_user_is_reported(self) -> None:
        settings = _make_settings(
            confluence=ConfluenceSettings(url="https://x.atlassian.net", token="tok", user="")
        )
        problems = validate_settings(settings)
        self.assertTrue(any("CONFLUENCE_USER" in p for p in problems))

    def test_missing_template_page_id_is_reported(self) -> None:
        settings = _make_settings(template=TemplateSettings(page_id="", cache_ttl=86400))
        problems = validate_settings(settings)
        self.assertTrue(any("TEMPLATE_PAGE_ID" in p for p in problems))

    def test_missing_gigachat_credentials_are_not_reported(self) -> None:
        """GigaChat isn't needed for every code path (e.g.
        --dump-template-rules), so validate_settings must not require it —
        GigaChatTokenManager raises its own clear error when it's actually
        used without credentials.
        """
        settings = _make_settings()
        problems = validate_settings(settings)
        self.assertFalse(any("GIGACHAT" in p for p in problems))


if __name__ == "__main__":
    unittest.main()
