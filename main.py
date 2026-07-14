#!/usr/bin/env python3
"""CLI entry point for the Confluence Validator Agent.

Usage:
    python main.py <page_id> [--refresh-template]
    python main.py --dump-template-rules [--refresh-template]

If no page_id is supplied, ``TEMPLATE_PAGE_ID`` semantics do not apply here;
the page id to validate must always be given explicitly (the template page
id is a separate, dedicated setting used only to load validation rules).

By default the template rule set is only re-parsed from the live
Confluence template page when the on-disk cache is missing or older than
``TEMPLATE_CACHE_TTL`` seconds. Pass ``--refresh-template`` to force a
fresh fetch + re-parse right now, regardless of cache age (e.g. right
after editing the template page).

Use ``--dump-template-rules`` to inspect exactly what the template parser
extracted (name, required/optional, level, parent) as a plain-text table,
without validating any page or posting a comment — the fastest way to
check whether a template-parsing fix actually worked, instead of
eyeballing screenshots of the live template page.
"""

from __future__ import annotations

import argparse
import sys

from config.settings import get_settings, validate_settings
from core.orchestrator import Orchestrator
from exceptions.api_errors import APIError
from exceptions.validation_errors import TemplateLoadError
from utils.logger import get_logger, setup_logging


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="main.py",
        description="Validate a Confluence page against the analytical page template.",
    )
    parser.add_argument(
        "page_id",
        nargs="?",
        default=None,
        help=(
            "Confluence content id of the page to validate. Not required "
            "when using --dump-template-rules."
        ),
    )
    parser.add_argument(
        "--refresh-template",
        action="store_true",
        help=(
            "Force a fresh fetch + re-parse of the Confluence template page "
            "instead of using the cached rule set, even if the cache is "
            "still fresh (TEMPLATE_CACHE_TTL)."
        ),
    )
    parser.add_argument(
        "--dump-template-rules",
        action="store_true",
        help=(
            "Print the parsed template rule set as a table and exit. Does "
            "not require a page_id, validates nothing, and posts no "
            "comment — pure inspection of what the template parser sees."
        ),
    )
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    """Run the validator agent for a single page id, or dump template rules.

    Args:
        argv: Command-line arguments (excluding the program name).

    Returns:
        Process exit code: 0 on success, 1 on any handled failure.
    """
    settings = get_settings()
    setup_logging(level=settings.logging.level, log_file=settings.logging.file)
    logger = get_logger(__name__)

    args = _parse_args(argv)

    problems = validate_settings(settings)
    if problems:
        for problem in problems:
            logger.error("Missing configuration: %s", problem)
        logger.error(
            "Fix the values above in your .env file (see .env.example), then try again."
        )
        return 1

    orchestrator = Orchestrator(settings)

    if args.dump_template_rules:
        try:
            table = orchestrator.dump_template_rules(refresh_template=args.refresh_template)
            print(table)
            return 0
        except TemplateLoadError as exc:
            logger.error("Template could not be loaded: %s", exc, exc_info=True)
            return 1
        except APIError as exc:
            logger.error("External API error: %s", exc, exc_info=True)
            return 1

    if not args.page_id:
        logger.error(
            "page_id is required unless --dump-template-rules is used. "
            "Usage: python main.py <confluence_page_id>"
        )
        return 1

    try:
        report = orchestrator.run(args.page_id, refresh_template=args.refresh_template)
        logger.info("Validation pipeline finished successfully for page %s", args.page_id)
        print(report)
        return 0
    except TemplateLoadError as exc:
        logger.error("Template could not be loaded: %s", exc, exc_info=True)
        return 1
    except APIError as exc:
        logger.error("External API error: %s", exc, exc_info=True)
        return 1
    except Exception:  # noqa: BLE001 - top-level safety net, full stacktrace logged
        logger.exception("Unhandled error while validating page %s", args.page_id)
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
