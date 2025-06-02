"""Utility module for logging setup."""

import logging
import sys


def setup_logging() -> None:
    """Configure basic logging settings with console handler."""
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
