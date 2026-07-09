"""SummarizerAgent: turns extracted technical content into a GigaChat summary."""

from __future__ import annotations

from clients.gigachat_client import GigaChatClient
from exceptions.api_errors import GigaChatAPIError
from models.summary import Summary
from utils.logger import get_logger

logger = get_logger(__name__)


class SummarizerAgent:
    """Wraps GigaChat to produce a categorized technical-change summary."""

    def __init__(
        self,
        client: GigaChatClient,
        system_prompt: str,
        user_prompt_template: str,
    ) -> None:
        """Initialize the summarizer.

        Args:
            client: Configured :class:`GigaChatClient`.
            system_prompt: System prompt text (from config.settings).
            user_prompt_template: User prompt template with
                ``{content_er}``, ``{content_integrations}``,
                ``{content_functional}`` placeholders.
        """
        self._client = client
        self._system_prompt = system_prompt
        self._user_prompt_template = user_prompt_template

    def summarize(self, extracted: dict[str, str]) -> Summary:
        """Produce a summary from previously extracted technical sections.

        If all extracted sections are empty ("Нет данных"), GigaChat is not
        called at all (nothing to summarize). If GigaChat is unreachable
        after all retries, a fallback :class:`Summary` is returned so the
        validation report can still be posted without the AI summary
        (SCENARIO_4 in the spec).

        Args:
            extracted: Mapping produced by
                :meth:`core.agents.extractor.ExtractorAgent.extract`.

        Returns:
            A :class:`Summary` instance (possibly empty on failure).
        """
        if all(v.strip() == "Нет данных" for v in extracted.values()):
            logger.info("No technical content to summarize; skipping GigaChat call.")
            return Summary(text="Нет данных для анализа технических изменений.")

        user_prompt = self._user_prompt_template.format(
            content_er=extracted.get("content_er", "Нет данных"),
            content_integrations=extracted.get("content_integrations", "Нет данных"),
            content_functional=extracted.get("content_functional", "Нет данных"),
        )

        try:
            text = self._client.chat(self._system_prompt, user_prompt)
            return Summary(text=text)
        except GigaChatAPIError as exc:
            logger.error("GigaChat summarization failed after retries: %s", exc)
            return Summary(text="")
