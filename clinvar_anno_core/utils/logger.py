# Imports
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

# Create a logger instance
def create_logger():
    current_directory = str(Path(__file__).resolve().parent)
    parent_directory = Path(current_directory).parent.parent

    logger = logging.getLogger('ClinVar_annotator_logger')
    logger.setLevel(logging.DEBUG)

    # Set stream handler to DEBUG
    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(logging.DEBUG)
    # Create a formatter for stream handler
    stream_formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    stream_handler.setFormatter(stream_formatter)

    # Set rotating file handler to DEBUG
    file_handler = RotatingFileHandler(str(parent_directory) + '/logs/ClinVar_annotator.log',
                                       maxBytes=500000,  # 500 KB
                                       backupCount=2)
    file_handler.setLevel(logging.DEBUG)
    # Create a formatter for file handler
    file_formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    file_handler.setFormatter(file_formatter)

    # Add stream and file handlers to the logger
    logger.addHandler(stream_handler)
    logger.addHandler(file_handler)

    return logger

# Initialise the logger
logger = create_logger()
