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
    def __init__(self, log_file=None):
        """Initialize the activity logger."""
        if log_file is None:
            # Default log file in data directory
            base_dir = Path(__file__).parent.parent  # Move up to src directory
            data_dir = base_dir / "data"
            os.makedirs(data_dir, exist_ok=True)  # Create data directory if it doesn't exist
            self.log_file = data_dir / "activity_log.txt"
        else:
            self.log_file = Path(log_file)
            
        # Create parent directory if it doesn't exist
        os.makedirs(self.log_file.parent, exist_ok=True)
        
        # Touch the file to make sure it exists
        if not self.log_file.exists():
            with open(self.log_file, 'a'):
                pass
                
        print(f"Activity logger initialized. Log file: {self.log_file}")
    
    def log_activity(self, activity_type, action=None, content_type=None, name=None, path=None, 
                     status="info", message=None, error=None, directory=None, symlink_path=None,
                     additional_data=None):
        """
        Log an activity to the activity log file.
        """
        entry = {
            "timestamp": datetime.datetime.now().isoformat(),
            "type": activity_type,
            "action": action,
            "status": status
        }
        
        # Add optional fields if provided
        if content_type is not None:
            entry["content_type"] = content_type
        if name is not None:
            entry["content_name"] = name
        if path is not None:
            entry["path"] = path
        if message is not None:
            entry["message"] = message
        if error is not None:
            entry["error"] = error
        if directory is not None:
            entry["directory"] = directory
        if symlink_path is not None:
            entry["symlink_path"] = symlink_path
        
        # Add any additional data
        if additional_data and isinstance(additional_data, dict):
            entry.update(additional_data)
        
        # Write to log file
        try:
            with open(self.log_file, "a", encoding='utf-8') as f:
                f.write(json.dumps(entry) + "\n")
            print(f"Activity logged: {action} - {name or path}")
            return True
        except Exception as e:
            print(f"Error logging activity: {e}")
            return False
    
    def log_movie_processed(self, movie_name, file_path, status="success", message=None):
        """Convenience method for logging movie processing."""
        self.log_activity(
            activity_type="media_process",
            action="process",
            content_type="movie",
            name=movie_name,
            path=file_path,
            status=status,
            message=message
        )
    
    def log_tv_processed(self, show_name, episode_info, file_path, status="success", message=None):
        """Convenience method for logging TV show processing."""
        self.log_activity(
            activity_type="media_process",
            action="process",
            content_type="tv",
            name=f"{show_name} - {episode_info}",
            path=file_path,
            status=status,
            message=message
        )
    
    def log_anime_processed(self, anime_name, episode_info, file_path, status="success", message=None):
        """Convenience method for logging anime processing."""
        self.log_activity(
            activity_type="media_process",
            action="process",
            content_type="anime",
            name=f"{anime_name} - {episode_info}",
            path=file_path,
            status=status,
            message=message
        )
    
    def log_skipped_item(self, file_path, reason, content_name=None):
        """Convenience method for logging skipped items."""
        self.log_activity(
            activity_type="media_process",
            action="skipped",
            path=file_path,
            name=content_name,
            status="skipped",
            message=reason
        )
    
    def log_symlink_created(self, source_path, symlink_path, content_name=None, content_type=None):
        """Convenience method for logging symlink creation."""
        self.log_activity(
            activity_type="file_operation",
            action="symlink_create",
            path=source_path,
            symlink_path=symlink_path,
            name=content_name,
            content_type=content_type,
            status="success",
            message=f"Created symlink: {symlink_path} -> {source_path}"
        )
    
    def log_symlink_removed(self, symlink_path, content_name=None):
        """Convenience method for logging symlink removal."""
        self.log_activity(
            activity_type="file_operation",
            action="symlink_remove",
            symlink_path=symlink_path,
            name=content_name,
            status="success",
            message=f"Removed symlink: {symlink_path}"
        )
    
    def log_monitor_directory_added(self, directory_path):
        """Convenience method for logging addition of monitored directory."""
        self.log_activity(
            activity_type="monitor",
            action="monitor_add",
            directory=directory_path,
            status="success",
            message=f"Directory added to monitoring: {directory_path}"
        )
    
    def log_monitor_directory_removed(self, directory_path):
        """Convenience method for logging removal of monitored directory."""
        self.log_activity(
            activity_type="monitor",
            action="monitor_remove",
            directory=directory_path,
            status="success",
            message=f"Directory removed from monitoring: {directory_path}"
        )
    
    def log_monitor_directory_paused(self, directory_path):
        """Convenience method for logging pausing of monitored directory."""
        self.log_activity(
            activity_type="monitor",
            action="monitor_pause",
            directory=directory_path,
            status="success",
            message=f"Directory monitoring paused: {directory_path}"
        )
    
    def log_monitor_directory_resumed(self, directory_path):
        """Convenience method for logging resuming of monitored directory."""
        self.log_activity(
            activity_type="monitor",
            action="monitor_resume",
            directory=directory_path,
            status="success",
            message=f"Directory monitoring resumed: {directory_path}"
        )