"""Orchestrator: wires the validator/extractor/summarizer agents together
and builds the final Confluence comment.
"""

from __future__ import annotations

import datetime as _dt

from clients.confluence_client import ConfluenceClient
from clients.gigachat_client import GigaChatClient
from config.settings import Settings
from core.agents.extractor import ExtractorAgent
from core.agents.summarizer import SummarizerAgent
from core.agents.validator import ValidatorAgent
from core.template.loader import TemplateLoader
from exceptions.validation_errors import TemplateLoadError
from models.validation_result import ValidationResult
from parsers.html_parser import parse_sections
from utils.logger import get_logger

logger = get_logger(__name__)


class Orchestrator:
    """Coordinates the end-to-end validation pipeline for one page."""

    def __init__(self, settings: Settings) -> None:
        """Wire up all clients and agents from application settings.

        Args:
            settings: Fully populated :class:`config.settings.Settings`.
        """
        self._settings = settings
        self._confluence = ConfluenceClient(settings.confluence, settings.retry)
        self._gigachat = GigaChatClient(settings.gigachat, settings.retry)
        self._template_loader = TemplateLoader(
            confluence_client=self._confluence,
            template_page_id=settings.template.page_id,
            cache_file=settings.template.cache_file,
            cache_ttl=settings.template.cache_ttl,
        )
        self._validator = ValidatorAgent()
        self._extractor = ExtractorAgent(settings.technical_sections)
        self._summarizer = SummarizerAgent(
            client=self._gigachat,
            system_prompt=settings.gigachat_system_prompt,
            user_prompt_template=settings.gigachat_user_prompt_template,
        )

    def dump_template_rules(self, refresh_template: bool = False) -> str:
        """Load the template rule set and render it as a readable table.

        Pure inspection helper — makes no Confluence page request beyond
        the template page itself, and posts no comment. Meant for
        debugging what the template parser actually extracted, instead of
        having to eyeball screenshots of the live template page.

        Args:
            refresh_template: If True, force a fresh fetch + re-parse
                instead of using the cached rule set.

        Returns:
            A formatted, human-readable table of the current rule set.
        """
        rules = self._template_loader.load(force_refresh=refresh_template)
        rules = sorted(rules, key=lambda r: r.order)

        header = f"{'#':<4}{'req?':<6}{'lvl':<4}{'id/keywords':<28}{'name'}"
        lines = [header, "-" * len(header)]
        for rule in rules:
            req = "ДА" if rule.required else "нет"
            keywords_preview = ", ".join(rule.keywords[:3])
            parent_suffix = f"  (parent: {rule.parent})" if rule.parent else ""
            lines.append(
                f"{rule.order:<4}{req:<6}{rule.level:<4}{keywords_preview:<28}"
                f"{rule.name}{parent_suffix}"
            )
        lines.append("")
        lines.append(f"Всего правил: {len(rules)}")
        lines.append(f"Обязательных: {sum(1 for r in rules if r.required)}")
        lines.append(f"Опциональных: {sum(1 for r in rules if not r.required)}")
        return "\n".join(lines)

    def run(self, page_id: str, refresh_template: bool = False) -> str:
        """Run the full pipeline for a single Confluence page.

        Args:
            page_id: Confluence content id to validate.
            refresh_template: If True, force a fresh fetch + re-parse of
                the Confluence template page instead of using the cached
                rule set, even if the cache is still within its TTL.

        Returns:
            The final markdown report that was (or would be) posted as a
            comment, for logging/testing purposes.
        """
        page = self._confluence.get_page(page_id)
        sections = parse_sections(page.raw_html)

        try:
            rules = self._template_loader.load(force_refresh=refresh_template)
        except TemplateLoadError as exc:
            logger.error("Cannot validate page %s: %s", page_id, exc)
            raise

        result = self._validator.validate(sections, rules)

        if not result.is_valid:
            # SCENARIO_2: mandatory section missing -> GigaChat is skipped
            # entirely to save tokens.
            report = self._build_report(page.title, result, summary_text=None)
            self._confluence.post_comment(page_id, report)
            return report

        extracted = self._extractor.extract(sections)
        summary = self._summarizer.summarize(extracted)
        summary_text = summary.text if not summary.is_empty else None

        report = self._build_report(page.title, result, summary_text=summary_text)
        self._confluence.post_comment(page_id, report)
        return report

    def _build_report(
        self,
        page_title: str,
        result: ValidationResult,
        summary_text: str | None,
    ) -> str:
        """Assemble the final markdown report per the configured format.

        Args:
            page_title: Title of the validated page.
            result: Validation outcome.
            summary_text: GigaChat summary text, or None if it was skipped
                / unavailable.

        Returns:
            Full markdown report string.
        """
        icons = self._settings.status_icons

        if not result.is_valid:
            status_label = icons["error"]
        elif result.warnings:
            status_label = icons["partial"]
        else:
            status_label = icons["success"]

        mandatory_lines = []
        for name in result.found_sections:
            mandatory_lines.append(f"- ✅ {name}")
        for error in result.errors:
            mandatory_lines.append(f"- ❌ {error.section}: {error.message}")
        mandatory_check_results = "\n".join(mandatory_lines) if mandatory_lines else "—"

        warnings_text = (
            "\n".join(f"- ⚠️ {w}" for w in result.warnings) if result.warnings else "Нет замечаний."
        )

        if summary_text is None:
            gigachat_summary = (
                "Резюме недоступно (валидация не пройдена, либо сервис анализа "
                "временно недоступен)."
            )
        else:
            gigachat_summary = summary_text

        timestamp = _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        parts = [
            f"# Отчет по валидации страницы: {page_title}",
            f"**Статус:** {status_label}",
            (
                "## Проверка шаблона\n\n"
                "### Обязательные разделы:\n"
                f"{mandatory_check_results}\n\n"
                "### Предупреждения:\n"
                f"{warnings_text}"
            ),
            f"---\n\n## Сводка по изменениям\n\n{gigachat_summary}",
            f"---\n*Отчет сгенерирован автоматически. Время: {timestamp}*",
        ]
        return "\n\n".join(parts)
