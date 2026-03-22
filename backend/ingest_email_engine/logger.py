"""Logging utilities for the ingest pipeline."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Final


_LOG_FILE_NAME: Final[str] = "ingest_pipeline.log"
_DEFAULT_LOGGER_NAME: Final[str] = "ingest_email_engine"


def get_logger(name: str = _DEFAULT_LOGGER_NAME) -> logging.Logger:
    """Return a configured logger.

    The logger writes to both stdout and a rotating file `ingest_pipeline.log`.
    This function is idempotent: handlers are added only once.
    """

    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    if logger.handlers:
        return logger

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(logging.INFO)
    stream_handler.setFormatter(formatter)

    log_path = Path.cwd() / _LOG_FILE_NAME
    file_handler = RotatingFileHandler(
        filename=str(log_path),
        maxBytes=2 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(formatter)

    logger.addHandler(stream_handler)
    logger.addHandler(file_handler)
    logger.propagate = False

    return logger
