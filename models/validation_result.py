"""Models describing the outcome of the template validation step."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ValidationError:
    """A single validation failure (missing mandatory section).

    Attributes:
        section: Name of the section that failed validation.
        message: Human readable explanation.
    """

    section: str
    message: str


@dataclass
class ValidationResult:
    """Aggregated result of validating a page against the template.

    Attributes:
        is_valid: True if all mandatory sections were found.
        errors: List of :class:`ValidationError` for missing mandatory
            sections.
        warnings: List of human readable warnings for missing optional
            sections.
        found_sections: Names of template sections that were located on
            the page.
    """

    is_valid: bool
    errors: list[ValidationError] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    found_sections: list[str] = field(default_factory=list)
