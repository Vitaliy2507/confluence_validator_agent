"""Thin client around the GigaChat chat-completions endpoint."""

from __future__ import annotations

import requests

from config.settings import GigaChatSettings, RetrySettings
from exceptions.api_errors import GigaChatAPIError
from utils.logger import get_logger
from utils.retry import retry_with_backoff

logger = get_logger(__name__)


class GigaChatClient:
    """Wraps ``POST /api/v1/chat/completions`` for GigaChat."""

    def __init__(self, settings: GigaChatSettings, retry: RetrySettings) -> None:
        """Initialize the client.

        Args:
            settings: GigaChat connection settings and generation params.
            retry: Retry/backoff configuration applied to requests.
        """
        self._settings = settings
        self._retry = retry
        self._session = requests.Session()

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
        headers = {
            "Authorization": f"Bearer {self._settings.token}",
            "Content-Type": "application/json",
        }
        try:
            response = self._session.post(url, json=payload, headers=headers, timeout=60)
        except requests.RequestException as exc:
            raise GigaChatAPIError(f"Network error calling GigaChat: {exc}") from exc

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
