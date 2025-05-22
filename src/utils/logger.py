"""
Logging configuration for Scanly.

This module sets up and provides logging functionality.
"""

import logging
import os
import sys
import json
import datetime
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

class ActivityLogger:
    """Logger for tracking application activities in a structured format."""
    
    def __init__(self, log_file=None):
        """Initialize the activity logger."""
        if log_file is None:
            # Default log file in data directory
            base_dir = Path(__file__).parent.parent  # src directory
            data_dir = base_dir / "data"
            os.makedirs(data_dir, exist_ok=True)
            self.log_file = data_dir / "activity_log.txt"
        else:
            self.log_file = Path(log_file)
        
        # Ensure the directory exists
        os.makedirs(self.log_file.parent, exist_ok=True)
        
        # Set up standard logger
        self.logger = logging.getLogger("activity")
        
        # Create file handler if it doesn't exist
        if not any(isinstance(h, logging.FileHandler) for h in self.logger.handlers):
            file_handler = logging.FileHandler(self.log_file)
            formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
            file_handler.setFormatter(formatter)
            self.logger.addHandler(file_handler)

    def log_activity(self, content_type, name, path, status="Success"):
        """Log an activity in the structured format."""
        # Format: timestamp|content_type|name|path|status
        log_entry = {
            "timestamp": datetime.datetime.now().isoformat(),
            "content_type": content_type,
            "name": name,
            "path": path,
            "status": status
        }
        
        # Log in both text and JSON format
        log_message = f"{content_type}|{name}|{path}|{status}"
        self.logger.info(log_message)
        
        # Also write as JSON for structured data
        with open(self.log_file.with_suffix('.json'), 'a') as f:
            f.write(json.dumps(log_entry) + '\n')
        
        return log_entry
    
    def log_movie(self, name, path, status="Success"):
        """Log a movie processing activity."""
        return self.log_activity("Movie", name, path, status)
    
    def log_tv_show(self, name, path, status="Success"):
        """Log a TV show processing activity."""
        return self.log_activity("TV Series", name, path, status)
    
    def log_anime_series(self, name, path, status="Success"):
        """Log an anime series processing activity."""
        return self.log_activity("Anime Series", name, path, status)
    
    def log_anime_movie(self, name, path, status="Success"):
        """Log an anime movie processing activity."""
        return self.log_activity("Anime Movie", name, path, status)
    
    def log_symlink_created(self, name, path, target_path, status="Created"):
        """Log a symlink creation activity."""
        # Determine content type from paths
        if "/Movies/" in target_path:
            content_type = "Movie"
        elif "/TV Shows/" in target_path:
            content_type = "TV Series"
        elif "/Anime Series/" in target_path:
            content_type = "Anime Series"
        elif "/Anime Movies/" in target_path:
            content_type = "Anime Movie"
        else:
            content_type = "Unknown"
        
        log_entry = {
            "timestamp": datetime.datetime.now().isoformat(),
            "content_type": content_type,
            "name": name,
            "path": path,
            "symlink_path": target_path,
            "action": "symlink_create",
            "status": status
        }
        
        # Log in both text and JSON format
        log_message = f"{content_type}|{name}|{path}|{status}"
        self.logger.info(log_message)
        
        # Write as JSON for structured data
        with open(self.log_file.with_suffix('.json'), 'a') as f:
            f.write(json.dumps(log_entry) + '\n')
        
        return log_entry
    
    def log_symlink_removed(self, name, path, target_path, status="Removed"):
        """Log a symlink removal activity."""
        # Determine content type from paths - similar to created
        if "/Movies/" in target_path:
            content_type = "Movie"
        elif "/TV Shows/" in target_path:
            content_type = "TV Series"
        elif "/Anime Series/" in target_path:
            content_type = "Anime Series"
        elif "/Anime Movies/" in target_path:
            content_type = "Anime Movie"
        else:
            content_type = "Unknown"
        
        log_entry = {
            "timestamp": datetime.datetime.now().isoformat(),
            "content_type": content_type,
            "name": name,
            "path": path,
            "symlink_path": target_path,
            "action": "symlink_remove",
            "status": status
        }
        
        # Log message
        log_message = f"{content_type}|{name}|{path}|{status}"
        self.logger.info(log_message)
        
        # Write as JSON
        with open(self.log_file.with_suffix('.json'), 'a') as f:
            f.write(json.dumps(log_entry) + '\n')
        
        return log_entry
    
    def log_skipped(self, name, path, content_type, reason="User skipped"):
        """Log a skipped item."""
        log_entry = {
            "timestamp": datetime.datetime.now().isoformat(),
            "content_type": content_type,
            "name": name,
            "path": path,
            "status": "Skipped",
            "error": reason
        }
        
        # Log message
        log_message = f"{content_type}|{name}|{path}|Skipped"
        self.logger.warning(log_message)
        
        # Write as JSON
        with open(self.log_file.with_suffix('.json'), 'a') as f:
            f.write(json.dumps(log_entry) + '\n')
        
        return log_entry

# Create a singleton instance
activity_logger = ActivityLogger()

# Helper functions
def log_movie_process(name, path, status="Success"):
    return activity_logger.log_movie(name, path, status)

def log_tv_process(name, path, status="Success"):
    return activity_logger.log_tv_show(name, path, status)

def log_anime_process(name, path, is_movie=False, status="Success"):
    if is_movie:
        return activity_logger.log_anime_movie(name, path, status)
    else:
        return activity_logger.log_anime_series(name, path, status)

def log_symlink_create(name, path, target_path, status="Created"):
    return activity_logger.log_symlink_created(name, path, target_path, status)

def log_symlink_remove(name, path, target_path, status="Removed"):
    return activity_logger.log_symlink_removed(name, path, target_path, status)

def log_skipped_item(name, path, content_type, reason="User skipped"):
    return activity_logger.log_skipped(name, path, content_type, reason)