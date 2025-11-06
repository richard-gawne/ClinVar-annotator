# Imports
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

# Create a logger instance
def create_logger():
    current_directory = str(Path(__file__).resolve().parent)
    parent_directory = Path(current_directory).parent
    
