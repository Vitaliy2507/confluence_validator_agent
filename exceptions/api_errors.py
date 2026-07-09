"""Exceptions raised when communicating with external APIs (Confluence, GigaChat)."""


class APIError(Exception):
    """Base exception for any external API failure."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        """Initialize the API error.

        Args:
            message: Human readable description of the failure.
            status_code: Optional HTTP status code returned by the API.
        """
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class ConfluenceAPIError(APIError):
    """Raised when a Confluence REST API call fails (auth, network, 4xx/5xx)."""


class GigaChatAPIError(APIError):
    """Raised when a GigaChat completion request fails after all retries."""
