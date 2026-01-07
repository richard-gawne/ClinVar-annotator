""" This module provides a configurable logging utility for applications. """

# Imports
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

# Create a logger instance
def create_logger():
    """
    Create and configure a logger.
    Logger is configured to log messages at DEBUG level during development.

    Returns:
        - logger: configured logger instance with stream and rotating file handler
    """
    current_directory = Path(__file__).resolve().parent
    parent_directory = current_directory.parent.parent

    # Create logs directory if it doesn't exist
    log_dir = parent_directory / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    log_file = log_dir / "clinvar_anno.log"

    logger = logging.getLogger('clinvar_anno_logger')
    logger.setLevel(logging.DEBUG)

    # Prevent duplicate handlers if create_logger is called multiple times
    if not logger.handlers:
        # Set stream handler to DEBUG
        stream_handler = logging.StreamHandler()
        stream_handler.setLevel(logging.DEBUG)
        stream_formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(message)s"
        )
        stream_handler.setFormatter(stream_formatter)

        # Set rotating file handler to DEBUG
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=500_000,  # 500 KB
            backupCount=2
        )
        file_handler.setLevel(logging.DEBUG)
        file_formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(message)s"
        )
        file_handler.setFormatter(file_formatter)

        # Add handlers
        logger.addHandler(stream_handler)
        logger.addHandler(file_handler)

    return logger

# Initialise the logger
logger = create_logger()
