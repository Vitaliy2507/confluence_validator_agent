"""Automatic OAuth2 client-credentials token manager for GigaChat.

GigaChat authenticates via ``client_id`` / ``client_secret`` exchanged for a
short-lived ``access_token`` (typically ~30 minutes). This module fetches
that token on first use and transparently refreshes it — ahead of expiry,
and also reactively if the API ever rejects a token with 401 — so nothing
needs to be pasted in by hand.
"""

from __future__ import annotations

import base64
import threading
import time
import uuid

import requests

from config.settings import GigaChatSettings, RetrySettings
from exceptions.api_errors import GigaChatAuthError
from utils.logger import get_logger
from utils.retry import retry_with_backoff

logger = get_logger(__name__)

# Refresh this many seconds before the token's actual expiry, so an
# in-flight request never races a token that dies mid-call.
_EXPIRY_MARGIN_SECONDS = 60

# Fallback validity window used only if the token endpoint doesn't return
# an explicit ``expires_at`` (GigaChat access tokens are normally valid for
# about 30 minutes).
_DEFAULT_TTL_SECONDS = 1800


class GigaChatTokenManager:
    """Fetches, caches, and automatically refreshes a GigaChat access token.

    Thread-safe: concurrent callers share a single in-flight refresh via an
    internal lock instead of each firing their own token request.
    """

    def __init__(self, settings: GigaChatSettings, retry: RetrySettings) -> None:
        """Initialize the token manager.

        Args:
            settings: GigaChat settings, including ``auth_url``,
                ``client_id``, ``client_secret``, and ``scope``.
            retry: Retry/backoff configuration applied to the token request.
        """
        self._settings = settings
        self._retry = retry
        self._session = requests.Session()
        self._lock = threading.Lock()
        self._access_token: str | None = None
        self._expires_at: float = 0.0

    def get_token(self, force_refresh: bool = False) -> str:
        """Return a currently-valid access token, refreshing if necessary.

        Args:
            force_refresh: If True, always fetch a brand new token — used
                after the API rejects the cached token with a 401, in case
                it was revoked or expired earlier than predicted.

        Returns:
            A valid GigaChat OAuth access token.

        Raises:
            GigaChatAuthError: If the token endpoint cannot be reached or
                returns an error, after all retry attempts.
        """
        with self._lock:
            if force_refresh or self._is_expired():
                self._refresh()
            assert self._access_token is not None
            return self._access_token

    def _is_expired(self) -> bool:
        return self._access_token is None or time.time() >= (
            self._expires_at - _EXPIRY_MARGIN_SECONDS
        )

    def _refresh(self) -> None:
        fetch = retry_with_backoff(
            max_attempts=self._retry.max_attempts,
            delay=self._retry.delay,
            backoff=self._retry.backoff,
            exceptions=(requests.RequestException, GigaChatAuthError),
        )(self._fetch_token_once)
        access_token, expires_at = fetch()
        self._access_token = access_token
        self._expires_at = expires_at
        logger.info(
            "GigaChat access token refreshed; valid for ~%d more seconds.",
            int(expires_at - time.time()),
        )

    def _fetch_token_once(self) -> tuple[str, float]:
        if not self._settings.client_id or not self._settings.client_secret:
            raise GigaChatAuthError(
                "GIGACHAT_CLIENT_ID / GIGACHAT_CLIENT_SECRET are not configured."
            )

        credentials = f"{self._settings.client_id}:{self._settings.client_secret}"
        authorization_key = base64.b64encode(credentials.encode("utf-8")).decode("ascii")

        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
            "RqUID": str(uuid.uuid4()),
            "Authorization": f"Basic {authorization_key}",
        }
        data = {"scope": self._settings.scope}

        try:
            response = self._session.post(
                self._settings.auth_url,
                headers=headers,
                data=data,
                timeout=30,
                verify=self._settings.verify_ssl,
            )
        except requests.RequestException as exc:
            raise GigaChatAuthError(f"Network error fetching GigaChat token: {exc}") from exc

        if not response.ok:
            raise GigaChatAuthError(
                f"GigaChat token endpoint returned {response.status_code}: "
                f"{response.text[:500]}",
                status_code=response.status_code,
            )

        try:
            payload = response.json()
        except ValueError as exc:
            raise GigaChatAuthError(f"GigaChat token response was not JSON: {exc}") from exc

        access_token = payload.get("access_token")
        if not access_token:
            raise GigaChatAuthError(f"GigaChat token response missing access_token: {payload}")

        expires_at_ms = payload.get("expires_at")
        if expires_at_ms:
            expires_at = float(expires_at_ms) / 1000.0
        else:
            expires_at = time.time() + _DEFAULT_TTL_SECONDS

        return access_token, expires_at
