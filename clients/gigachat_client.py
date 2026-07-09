"""Thin client around the GigaChat chat-completions endpoint.

Authentication is handled transparently by :class:`GigaChatTokenManager`:
the client never holds a static bearer token — it asks the token manager
for a currently-valid one on every call, and the manager refreshes it in
the background (ahead of expiry, or reactively on a 401) using the
configured ``client_id`` / ``client_secret``.
"""

from __future__ import annotations

import requests

from clients.gigachat_auth import GigaChatTokenManager
from config.settings import GigaChatSettings, RetrySettings
from exceptions.api_errors import GigaChatAPIError
from utils.logger import get_logger
from utils.retry import retry_with_backoff

logger = get_logger(__name__)


class GigaChatClient:
    """Wraps ``POST /api/v1/chat/completions`` for GigaChat."""

    def __init__(
        self,
        settings: GigaChatSettings,
        retry: RetrySettings,
        token_manager: GigaChatTokenManager | None = None,
    ) -> None:
        """Initialize the client.

        Args:
            settings: GigaChat connection settings and generation params.
            retry: Retry/backoff configuration applied to requests.
            token_manager: Optional pre-built token manager (mainly for
                tests); a new one is created from ``settings``/``retry`` if
                omitted.
        """
        self._settings = settings
        self._retry = retry
        self._session = requests.Session()
        self._token_manager = token_manager or GigaChatTokenManager(settings, retry)

    def chat(self, system_prompt: str, user_prompt: str) -> str:
        """Request a chat completion from GigaChat.

        Args:
            system_prompt: System role instructions.
            user_prompt: User role message (the actual content to analyze).

        Returns:
            The assistant's response text.

        Raises:
            GigaChatAPIError: If the request fails after all retry attempts.
        """
        call = retry_with_backoff(
            max_attempts=self._retry.max_attempts,
            delay=self._retry.delay,
            backoff=self._retry.backoff,
            exceptions=(requests.RequestException, GigaChatAPIError),
        )(self._chat_once)
        return call(system_prompt, user_prompt)

    def _chat_once(self, system_prompt: str, user_prompt: str) -> str:
        url = f"{self._settings.url.rstrip('/')}/chat/completions"
        payload = {
            "model": self._settings.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": self._settings.temperature,
            "max_tokens": self._settings.max_tokens,
        }

        token = self._token_manager.get_token()
        response = self._post(url, payload, token)

        if response.status_code == 401:
            # Cached token was rejected (expired early / revoked) — force a
            # fresh one and retry exactly once before giving up to the
            # outer retry_with_backoff wrapper.
            logger.warning("GigaChat returned 401; forcing token refresh and retrying once.")
            token = self._token_manager.get_token(force_refresh=True)
            response = self._post(url, payload, token)

        if not response.ok:
            raise GigaChatAPIError(
                f"GigaChat returned {response.status_code}: {response.text[:500]}",
                status_code=response.status_code,
            )

        data = response.json()
        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise GigaChatAPIError(f"Unexpected GigaChat response shape: {data}") from exc

        logger.info("GigaChat completion received (%d chars)", len(content))
        return content

    def _post(self, url: str, payload: dict, token: str) -> requests.Response:
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        try:
            return self._session.post(
                url,
                json=payload,
                headers=headers,
                timeout=60,
                verify=self._settings.verify_ssl,
            )
        except requests.RequestException as exc:
            raise GigaChatAPIError(f"Network error calling GigaChat: {exc}") from exc
