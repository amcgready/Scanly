"""
Logging configuration for Scanly.

This module sets up and provides logging functionality.
"""

import logging
import os
import sys
from pathlib import Path
from typing import Optional

from src.config import LOG_LEVEL, LOG_FILE

# Create a logs directory if it doesn't exist
logs_dir = Path(__file__).parents[2] / 'logs'
logs_dir.mkdir(exist_ok=True)

# Configure the root logger
def setup_logging(log_file: Optional[str] = None, log_level: Optional[str] = None) -> None:
    """
    Set up logging for the application.
    
    Args:
        log_file: Path to the log file. If None, uses the value from settings.
        log_level: Logging level. If None, uses the value from settings.
    """
    level = getattr(logging, (log_level or LOG_LEVEL).upper(), logging.INFO)
    
    # Determine log file path
    if log_file is None:
        log_file = LOG_FILE
    
    if not os.path.isabs(log_file):
        log_file = logs_dir / log_file
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    
    # Clear any existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Create a console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s', 
                                        datefmt='%Y-%m-%d %H:%M:%S')
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)
    
    # Create a file handler
    file_handler = logging.FileHandler(log_file)
    file_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s', 
                                     datefmt='%Y-%m-%d %H:%M:%S')
    file_handler.setFormatter(file_formatter)
    root_logger.addHandler(file_handler)
    
    # Log startup information
    logging.info(f"Logging initialized (level: {logging.getLevelName(level)})")

def get_logger(name: str) -> logging.Logger:
    """
    Get a logger for a specific module.
    
    Args:
        name: Name of the module
        
    Returns:
        Logger instance
    """
    return logging.getLogger(name)