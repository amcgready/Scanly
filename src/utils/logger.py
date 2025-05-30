"""
Logger utility for Scanly.

This module provides centralized logging for the application.
"""

import logging
import os
from pathlib import Path

def get_logger(name):
    """Get a logger with the given name."""
    # This function simply returns a logger with the given name
    # The actual configuration is done in main.py
    return logging.getLogger(name)

def setup_logging(log_level=None):
    """Set up logging configuration."""
    # Create logs directory if it doesn't exist
    log_dir = os.path.join(Path(__file__).parents[2], 'logs')
    os.makedirs(log_dir, exist_ok=True)
    
    # Set log level
    level = getattr(logging, log_level.upper()) if log_level else logging.INFO
    
    # Configure root logger
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(os.path.join(log_dir, 'scanly.log'))
        ]
    )
    
    # Reduce verbosity of some common modules
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('requests').setLevel(logging.WARNING)