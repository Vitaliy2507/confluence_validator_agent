"""Exceptions raised during template loading and page validation."""


class TemplateLoadError(Exception):
    """Raised when the template rule set cannot be loaded from cache or Confluence."""


class ValidationFailedError(Exception):
    """Raised to short-circuit the pipeline when mandatory sections are missing.

    Catching this at the orchestrator level allows the pipeline to skip the
    (costly) GigaChat call, satisfying the "no GigaChat on validation error"
    acceptance criterion.
    """

    def __init__(self, message: str, errors: list | None = None) -> None:
        """Initialize the error.

        Args:
            message: Summary message for logging.
            errors: List of ValidationError objects describing what failed.
        """
        super().__init__(message)
        self.errors = errors or []
