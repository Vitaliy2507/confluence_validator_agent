"""Unit tests for GigaChatTokenManager: caching, expiry, and auto-refresh."""

from __future__ import annotations

import time
import unittest
from unittest.mock import MagicMock, patch

from clients.gigachat_auth import GigaChatTokenManager
from config.settings import GigaChatSettings, RetrySettings
from exceptions.api_errors import GigaChatAuthError


def _make_settings(**overrides) -> GigaChatSettings:
    defaults = dict(
        url="https://gigachat.example.com/api/v1",
        auth_url="https://oauth.example.com/api/v2/oauth",
        client_id="test-client-id",
        client_secret="test-client-secret",
        scope="GIGACHAT_API_PERS",
        model="GigaChat",
        verify_ssl=True,
    )
    defaults.update(overrides)
    return GigaChatSettings(**defaults)


def _make_response(status_code=200, json_data=None, text=""):
    response = MagicMock()
    response.status_code = status_code
    response.ok = 200 <= status_code < 300
    response.json.return_value = json_data or {}
    response.text = text
    return response


class GigaChatTokenManagerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.settings = _make_settings()
        self.retry = RetrySettings(max_attempts=2, delay=0, backoff=1)

    def test_fetches_token_on_first_call(self) -> None:
        manager = GigaChatTokenManager(self.settings, self.retry)
        response = _make_response(
            json_data={
                "access_token": "token-1",
                "expires_at": int((time.time() + 1800) * 1000),
            }
        )
        with patch.object(manager._session, "post", return_value=response) as mock_post:
            token = manager.get_token()
        self.assertEqual(token, "token-1")
        self.assertEqual(mock_post.call_count, 1)

    def test_caches_token_until_near_expiry(self) -> None:
        manager = GigaChatTokenManager(self.settings, self.retry)
        response = _make_response(
            json_data={
                "access_token": "token-1",
                "expires_at": int((time.time() + 1800) * 1000),
            }
        )
        with patch.object(manager._session, "post", return_value=response) as mock_post:
            token1 = manager.get_token()
            token2 = manager.get_token()
        self.assertEqual(token1, token2)
        self.assertEqual(mock_post.call_count, 1, "should not refetch a still-fresh token")

    def test_refreshes_when_close_to_expiry(self) -> None:
        manager = GigaChatTokenManager(self.settings, self.retry)
        # Token "expires" 10 seconds from now, well within the 60s margin.
        almost_expired = _make_response(
            json_data={
                "access_token": "token-1",
                "expires_at": int((time.time() + 10) * 1000),
            }
        )
        fresh = _make_response(
            json_data={
                "access_token": "token-2",
                "expires_at": int((time.time() + 1800) * 1000),
            }
        )
        with patch.object(manager._session, "post", side_effect=[almost_expired, fresh]):
            token1 = manager.get_token()
            token2 = manager.get_token()
        self.assertEqual(token1, "token-1")
        self.assertEqual(token2, "token-2")

    def test_force_refresh_after_401(self) -> None:
        manager = GigaChatTokenManager(self.settings, self.retry)
        first = _make_response(
            json_data={
                "access_token": "token-1",
                "expires_at": int((time.time() + 1800) * 1000),
            }
        )
        second = _make_response(
            json_data={
                "access_token": "token-2",
                "expires_at": int((time.time() + 1800) * 1000),
            }
        )
        with patch.object(manager._session, "post", side_effect=[first, second]):
            token1 = manager.get_token()
            token2 = manager.get_token(force_refresh=True)
        self.assertEqual(token1, "token-1")
        self.assertEqual(token2, "token-2")

    def test_missing_credentials_raises_auth_error(self) -> None:
        settings = _make_settings(client_id="", client_secret="")
        manager = GigaChatTokenManager(settings, self.retry)
        with self.assertRaises(GigaChatAuthError):
            manager.get_token()

    def test_auth_endpoint_error_raises_after_retries(self) -> None:
        manager = GigaChatTokenManager(self.settings, self.retry)
        error_response = _make_response(status_code=401, text="bad credentials")
        with patch.object(manager._session, "post", return_value=error_response) as mock_post:
            with self.assertRaises(GigaChatAuthError):
                manager.get_token()
        self.assertEqual(mock_post.call_count, self.retry.max_attempts)


if __name__ == "__main__":
    unittest.main()
