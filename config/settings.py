"""Application settings, loaded from environment variables / .env file.

Only ``python-dotenv`` and the standard library are used here; no
configuration framework (e.g. Pydantic) is involved, per project
constraints.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class ConfluenceSettings:
    """Connection settings for the Confluence REST API."""

    url: str
    token: str
    user: str


@dataclass(frozen=True)
class GigaChatSettings:
    """Connection settings and generation parameters for GigaChat."""

    url: str
    token: str
    model: str
    temperature: float = 0.1
    max_tokens: int = 3000


@dataclass(frozen=True)
class TemplateSettings:
    """Settings controlling how the template rule set is loaded/cached."""

    page_id: str
    cache_ttl: int
    cache_file: str = "config/template_rules.json"


@dataclass(frozen=True)
class RetrySettings:
    """Settings controlling retry/backoff behaviour for API calls."""

    max_attempts: int = 3
    delay: float = 1.0
    backoff: float = 2.0


@dataclass(frozen=True)
class LoggingSettings:
    """Settings controlling application-wide logging."""

    level: str = "INFO"
    file: str = "validator.log"


# --- Static prompt / technical-section configuration (from the spec) -------

GIGACHAT_SYSTEM_PROMPT = """\
Ты технический архитектор и аналитик брокерского бизнеса.
Твоя задача — анализировать изменения в технической документации.

Правила:
1. Анализируй ТОЛЬКО секции: Интеграции, Модель предметной области/ER-диаграмма, \
Функциональное требование (включая подразделы про топики Kafka).
2. Выделяй фактические изменения в терминах:
   - БД (таблицы, поля, типы данных, обязательность)
   - REST API (новые/измененные эндпоинты, сервисы)
   - Kafka (новые топики, форматы сообщений, consumer/producer)
3. Для каждого изменения укажи статус:
   [+] — добавлено
   [-] — удалено
   [~] — изменено
4. Группируй по категориям: БД, REST API, Kafka
5. Если в категории нет изменений — напиши "Нет изменений"
6. Не придумывай то, чего нет в тексте
7. Используй маркированный список без воды
"""

GIGACHAT_USER_PROMPT_TEMPLATE = """\
Проанализируй следующие секции документации и выдели технические изменения:

--Модель предметной области/ER-диаграмма (БД)--
{content_er}

--Интеграции (REST API)--
{content_integrations}

--Функциональное требование (Kafka, логика)--
{content_functional}

Если секция пуста или содержит только "Нет данных" — пропусти её.
Выведи только фактические изменения в структурированном виде.
"""

# Technical sections fed into the GigaChat prompt (extractor.py uses this
# to know which sections of the page to pull content from).
TECHNICAL_SECTIONS = [
    {
        "id": "6.3",
        "name": "Модель предметной области/ER-диаграмма",
        "category": "БД",
        "keywords": [
            "модель предметной области",
            "er-диаграмма",
            "er диаграмма",
            "6.3",
        ],
        "prompt_key": "content_er",
    },
    {
        "id": "6.2",
        "name": "Интеграции",
        "category": "REST API",
        "keywords": ["интеграции", "6.2"],
        "prompt_key": "content_integrations",
    },
    {
        "id": "6.5",
        "name": "Функциональное требование",
        "category": "Kafka",
        "keywords": ["функциональное требование", "6.5"],
        "prompt_key": "content_functional",
    },
]

STATUS_ICONS = {
    "success": "✅ Валидация пройдена",
    "error": "❌ Ошибки валидации",
    "partial": "⚠️ Валидация с предупреждениями",
}


@dataclass(frozen=True)
class Settings:
    """Top-level application settings, aggregating all sub-sections."""

    confluence: ConfluenceSettings
    gigachat: GigaChatSettings
    template: TemplateSettings
    retry: RetrySettings
    logging: LoggingSettings
    technical_sections: list = field(default_factory=lambda: TECHNICAL_SECTIONS)
    gigachat_system_prompt: str = GIGACHAT_SYSTEM_PROMPT
    gigachat_user_prompt_template: str = GIGACHAT_USER_PROMPT_TEMPLATE
    status_icons: dict = field(default_factory=lambda: dict(STATUS_ICONS))


def _env(name: str, default: str = "") -> str:
    """Read an environment variable, returning ``default`` if unset/empty."""
    return os.environ.get(name, default)


def get_settings() -> Settings:
    """Build a :class:`Settings` instance from the current environment.

    Returns:
        A fully populated, immutable :class:`Settings` object.
    """
    confluence = ConfluenceSettings(
        url=_env("CONFLUENCE_URL"),
        token=_env("CONFLUENCE_TOKEN"),
        user=_env("CONFLUENCE_USER"),
    )
    gigachat = GigaChatSettings(
        url=_env("GIGACHAT_URL"),
        token=_env("GIGACHAT_TOKEN"),
        model=_env("GIGACHAT_MODEL", "GigaChat"),
        temperature=0.1,
        max_tokens=3000,
    )
    template = TemplateSettings(
        page_id=_env("TEMPLATE_PAGE_ID"),
        cache_ttl=int(_env("TEMPLATE_CACHE_TTL", "86400") or "86400"),
    )
    retry = RetrySettings(
        max_attempts=int(_env("RETRY_MAX_ATTEMPTS", "3") or "3"),
        delay=float(_env("RETRY_DELAY", "1") or "1"),
        backoff=float(_env("RETRY_BACKOFF", "2") or "2"),
    )
    logging_settings = LoggingSettings(
        level=_env("LOG_LEVEL", "INFO"),
        file=_env("LOG_FILE", "validator.log"),
    )
    return Settings(
        confluence=confluence,
        gigachat=gigachat,
        template=template,
        retry=retry,
        logging=logging_settings,
    )
