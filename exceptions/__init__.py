"""Custom exception hierarchy for the Confluence Validator Agent."""

from exceptions.api_errors import (
    APIError,
    ConfluenceAPIError,
    GigaChatAPIError,
    GigaChatAuthError,
)
from exceptions.validation_errors import (
    TemplateLoadError,
    ValidationFailedError,
)

__all__ = [
    "APIError",
    "ConfluenceAPIError",
    "GigaChatAPIError",
    "GigaChatAuthError",
    "TemplateLoadError",
    "ValidationFailedError",
]
