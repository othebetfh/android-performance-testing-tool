"""Logging configuration for perftest."""

import logging
from pathlib import Path
from typing import Optional

from rich.logging import RichHandler
from rich.console import Console


console = Console()


def setup_logging(
    level: str = "INFO",
    log_file: Optional[Path] = None,
    format_string: Optional[str] = None
) -> None:
    """
    Set up logging with Rich handler for beautiful console output.

    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Optional path to log file
        format_string: Optional custom format string for file handler
    """
    # Convert string level to logging constant
    numeric_level = getattr(logging, level.upper(), logging.INFO)

    # Default format for file logging
    if format_string is None:
        format_string = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)

    # Remove existing handlers
    root_logger.handlers.clear()

    # Add Rich handler for console
    rich_handler = RichHandler(
        rich_tracebacks=True,
        tracebacks_show_locals=True,
        show_time=False,
        show_path=False,
    )
    rich_handler.setLevel(numeric_level)
    root_logger.addHandler(rich_handler)

    # Add file handler if log_file specified
    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(numeric_level)
        file_handler.setFormatter(logging.Formatter(format_string))
        root_logger.addHandler(file_handler)


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance with the given name.

    Args:
        name: Logger name (typically __name__)

    Returns:
        logging.Logger: Configured logger instance
    """
    return logging.getLogger(name)


def mask_secret(secret: str, visible_chars: int = 4) -> str:
    """
    Mask a secret string for safe logging.

    Args:
        secret: The secret string to mask
        visible_chars: Number of characters to show at start and end

    Returns:
        str: Masked string (e.g., "abcd...wxyz")
    """
    if not secret or len(secret) <= visible_chars * 2:
        return "***"

    return f"{secret[:visible_chars]}...{secret[-visible_chars:]}"
