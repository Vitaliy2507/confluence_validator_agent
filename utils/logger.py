"""Centralized logging configuration for the Confluence Validator Agent."""

from __future__ import annotations

import logging
import sys

_CONFIGURED = False


def setup_logging(level: str = "INFO", log_file: str = "validator.log") -> None:
    """Configure the root logger once for the whole application.

    Sets up two handlers: a console handler (stdout) and a rotating-free
    file handler that appends to ``log_file``. Safe to call multiple times;
    only the first call takes effect.

    Args:
        level: Logging level name (e.g. "INFO", "DEBUG").
        log_file: Path to the log file that all log records are appended to.
    """
    global _CONFIGURED
    if _CONFIGURED:
        return

    numeric_level = getattr(logging, level.upper(), logging.INFO)
    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    root = logging.getLogger()
    root.setLevel(numeric_level)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    root.addHandler(console_handler)

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)

    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    """Return a module-level logger.

    Args:
        name: Usually ``__name__`` of the calling module.

    Returns:
        A configured :class:`logging.Logger` instance.
    """
    return logging.getLogger(name)
