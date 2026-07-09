"""ValidatorAgent: checks a page's sections against the template rule set."""

from __future__ import annotations

from models.section import Section, TemplateRule
from models.validation_result import ValidationError, ValidationResult
from utils.logger import get_logger

logger = get_logger(__name__)


class ValidatorAgent:
    """Matches template rules against the headings found on a real page."""

    def validate(self, sections: list[Section], rules: list[TemplateRule]) -> ValidationResult:
        """Validate a page's sections against the template rule set.

        Args:
            sections: Sections extracted from the page under review.
            rules: Template rules (mandatory + optional) to check against.

        Returns:
            A :class:`ValidationResult` summarizing found sections, missing
            mandatory sections (errors) and missing optional sections
            (warnings).
        """
        errors: list[ValidationError] = []
        warnings: list[str] = []
        found_sections: list[str] = []

        for rule in sorted(rules, key=lambda r: r.order):
            matching_section = self._find_matching_section(rule, sections)
            if matching_section is not None:
                found_sections.append(rule.name)
                continue

            if rule.required:
                errors.append(
                    ValidationError(
                        section=rule.name,
                        message=f'Обязательный раздел "{rule.name}" не найден на странице.',
                    )
                )
            else:
                warnings.append(f'Опциональный раздел "{rule.name}" отсутствует.')

        is_valid = len(errors) == 0
        logger.info(
            "Validation complete: valid=%s, errors=%d, warnings=%d",
            is_valid,
            len(errors),
            len(warnings),
        )
        return ValidationResult(
            is_valid=is_valid,
            errors=errors,
            warnings=warnings,
            found_sections=found_sections,
        )

    @staticmethod
    def _find_matching_section(rule: TemplateRule, sections: list[Section]) -> Section | None:
        """Find the first section whose header satisfies the given rule."""
        for section in sections:
            if not section.header:
                continue
            if rule.matches(section.header):
                return section
        return None
