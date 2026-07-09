#!/usr/bin/env python3
"""CLI entry point for the Confluence Validator Agent.

Usage:
    python main.py <page_id>

If no page_id is supplied, ``TEMPLATE_PAGE_ID`` semantics do not apply here;
the page id to validate must always be given explicitly (the template page
id is a separate, dedicated setting used only to load validation rules).
"""

from __future__ import annotations

import sys

from config.settings import get_settings
from core.orchestrator import Orchestrator
from exceptions.api_errors import APIError
from exceptions.validation_errors import TemplateLoadError
from utils.logger import get_logger, setup_logging


def main(argv: list[str]) -> int:
    """Run the validator agent for a single page id.

    Args:
        argv: Command-line arguments (excluding the program name).

    Returns:
        Process exit code: 0 on success, 1 on any handled failure.
    """
    settings = get_settings()
    setup_logging(level=settings.logging.level, log_file=settings.logging.file)
    logger = get_logger(__name__)

    if len(argv) < 1:
        logger.error("Usage: python main.py <confluence_page_id>")
        return 1

    page_id = argv[0]
    orchestrator = Orchestrator(settings)

    try:
        report = orchestrator.run(page_id)
        logger.info("Validation pipeline finished successfully for page %s", page_id)
        print(report)
        return 0
    except TemplateLoadError as exc:
        logger.error("Template could not be loaded: %s", exc, exc_info=True)
        return 1
    except APIError as exc:
        logger.error("External API error: %s", exc, exc_info=True)
        return 1
    except Exception:  # noqa: BLE001 - top-level safety net, full stacktrace logged
        logger.exception("Unhandled error while validating page %s", page_id)
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
