"""Thin client around the Confluence REST API (``requests``-based)."""

from __future__ import annotations

import requests

from config.settings import ConfluenceSettings, RetrySettings
from exceptions.api_errors import ConfluenceAPIError
from models.page import Page
from utils.logger import get_logger
from utils.retry import retry_with_backoff

logger = get_logger(__name__)


class ConfluenceClient:
    """Wraps the two Confluence endpoints the agent needs: fetching a page
    and posting a comment back to it.
    """

    def __init__(self, settings: ConfluenceSettings, retry: RetrySettings) -> None:
        """Initialize the client.

        Args:
            settings: Confluence connection settings (url, token, user).
            retry: Retry/backoff configuration applied to all requests.
        """
        self._settings = settings
        self._retry = retry
        self._session = requests.Session()
        self._session.auth = (settings.user, settings.token)

    def get_page(self, page_id: str) -> Page:
        """Fetch a Confluence page including its storage-format body.

        Args:
            page_id: Confluence content id.

        Returns:
            A populated :class:`Page` model.

        Raises:
            ConfluenceAPIError: If the request fails after all retries.
        """
        fetch = retry_with_backoff(
            max_attempts=self._retry.max_attempts,
            delay=self._retry.delay,
            backoff=self._retry.backoff,
            exceptions=(requests.RequestException, ConfluenceAPIError),
        )(self._get_page_once)
        return fetch(page_id)

    def _get_page_once(self, page_id: str) -> Page:
        url = f"{self._settings.url.rstrip('/')}/rest/api/content/{page_id}"
        try:
            response = self._session.get(
                url, params={"expand": "body.storage,version"}, timeout=30
            )
        except requests.RequestException as exc:
            raise ConfluenceAPIError(f"Network error fetching page {page_id}: {exc}") from exc

        if not response.ok:
            raise ConfluenceAPIError(
                f"Confluence returned {response.status_code} for page {page_id}: "
                f"{response.text[:500]}",
                status_code=response.status_code,
            )

        logger.info("Fetched Confluence page %s", page_id)
        return Page.from_confluence_json(response.json())

    def post_comment(self, page_id: str, markdown_comment: str) -> None:
        """Post a comment (rendered as simple storage-format HTML) to a page.

        Args:
            page_id: Confluence content id to attach the comment to.
            markdown_comment: Markdown text produced by the report builder;
                converted to a minimal storage-format representation.

        Raises:
            ConfluenceAPIError: If the request fails after all retries.
        """
        post = retry_with_backoff(
            max_attempts=self._retry.max_attempts,
            delay=self._retry.delay,
            backoff=self._retry.backoff,
            exceptions=(requests.RequestException, ConfluenceAPIError),
        )(self._post_comment_once)
        post(page_id, markdown_comment)

    def _post_comment_once(self, page_id: str, markdown_comment: str) -> None:
        url = f"{self._settings.url.rstrip('/')}/rest/api/content/{page_id}/child/comment"
        storage_value = self._markdown_to_storage(markdown_comment)
        payload = {
            "type": "comment",
            "body": {
                "storage": {
                    "value": storage_value,
                    "representation": "storage",
                }
            },
            "container": {"id": page_id, "type": "page"},
        }
        try:
            response = self._session.post(
                url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=30,
            )
        except requests.RequestException as exc:
            raise ConfluenceAPIError(
                f"Network error posting comment to page {page_id}: {exc}"
            ) from exc

        if not response.ok:
            raise ConfluenceAPIError(
                f"Confluence returned {response.status_code} posting comment to "
                f"page {page_id}: {response.text[:500]}",
                status_code=response.status_code,
            )
        logger.info("Posted validation comment to page %s", page_id)

    @staticmethod
    def _markdown_to_storage(markdown_text: str) -> str:
        """Minimal Markdown -> Confluence storage-format HTML conversion.

        Only handles the constructs the report builder actually produces
        (headings, bold, bullet lists, horizontal rules, plain paragraphs) —
        intentionally not a general-purpose Markdown renderer, per the
        "no extra frameworks" constraint.

        Args:
            markdown_text: Markdown text to convert.

        Returns:
            Confluence storage-format HTML string.
        """
        lines = markdown_text.split("\n")
        html_lines: list[str] = []
        in_list = False

        def close_list() -> None:
            nonlocal in_list
            if in_list:
                html_lines.append("</ul>")
                in_list = False

        for line in lines:
            stripped = line.strip()
            if not stripped:
                close_list()
                continue
            if stripped == "---":
                close_list()
                html_lines.append("<hr/>")
            elif stripped.startswith("### "):
                close_list()
                html_lines.append(f"<h3>{stripped[4:]}</h3>")
            elif stripped.startswith("## "):
                close_list()
                html_lines.append(f"<h2>{stripped[3:]}</h2>")
            elif stripped.startswith("# "):
                close_list()
                html_lines.append(f"<h1>{stripped[2:]}</h1>")
            elif stripped.startswith("- "):
                if not in_list:
                    html_lines.append("<ul>")
                    in_list = True
                html_lines.append(f"<li>{stripped[2:]}</li>")
            else:
                close_list()
                # Bold: **text** -> <strong>text</strong>
                import re

                rendered = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", stripped)
                html_lines.append(f"<p>{rendered}</p>")

        close_list()
        return "".join(html_lines)
