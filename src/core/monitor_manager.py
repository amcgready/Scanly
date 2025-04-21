"""
Monitor manager functionality for Scanly.

This module provides the MonitorManager class for managing monitored directories.
"""

import os
import json
import time
from pathlib import Path
from typing import Dict, List, Set, Optional
import threading

from src.core.file_monitor import FileMonitor
from src.utils.discord_utils import send_discord_notification
from src.utils.logger import get_logger

logger = get_logger(__name__)

class MonitorManager:
    """
    Manages directories to monitor and processes new files.
    """
    
    def __init__(self):
        """Initialize the monitor manager."""
        self.logger = get_logger(__name__)
        self.monitors: Dict[str, Dict] = {}
        self.monitoring_thread = None
        self.stop_event = threading.Event()
        
        # Load existing monitored directories
        self._load_monitors()
    
    def _get_monitors_file(self) -> str:
        """Get the path to the monitors JSON file."""
        return os.path.join(os.path.dirname(os.path.dirname(__file__)), 'monitored_directories.json')
    
    def _load_monitors(self) -> None:
        """Load monitored directories from file."""
        try:
            monitors_file = self._get_monitors_file()
            if os.path.exists(monitors_file):
                with open(monitors_file, 'r') as f:
                    data = json.load(f)
                    # Convert processed_files from lists to sets for faster lookups
                    for dir_path, info in data.items():
                        if 'processed_files' in info and isinstance(info['processed_files'], list):
                            info['processed_files'] = set(info['processed_files'])
                    self.monitors = data
                self.logger.info(f"Loaded {len(self.monitors)} monitored directories")
        except Exception as e:
            self.logger.error(f"Error loading monitored directories: {e}")
            self.monitors = {}
    
    def _save_monitors(self) -> None:
        """Save monitored directories to file."""
        try:
            # Convert sets to lists for JSON serialization
            json_monitors = {}
            for dir_path, info in self.monitors.items():
                json_info = info.copy()
                if 'processed_files' in json_info and isinstance(json_info['processed_files'], set):
                    json_info['processed_files'] = list(json_info['processed_files'])
                json_monitors[dir_path] = json_info
            
            monitors_file = self._get_monitors_file()
            with open(monitors_file, 'w') as f:
                json.dump(json_monitors, f, indent=4)
            self.logger.info(f"Saved {len(self.monitors)} monitored directories")
        except Exception as e:
            self.logger.error(f"Error saving monitored directories: {e}")
    
    def add_directory(self, directory: str, description: Optional[str] = None) -> bool:
        """
        Add a directory to monitor.
        
        Args:
            directory: Directory path to monitor
            description: Optional description of the directory
            
        Returns:
            True if the directory was added, False otherwise
        """
        if not os.path.isdir(directory):
            self.logger.error(f"Cannot add '{directory}' - not a valid directory")
            return False
        
        directory = os.path.abspath(directory)
        
        # Check if already monitoring this directory
        if directory in self.monitors:
            self.logger.warning(f"Already monitoring {directory}")
            return False
        
        # Add to monitored directories
        self.monitors[directory] = {
            "description": description or os.path.basename(directory),
            "last_checked": 0,
            "processed_files": set(),
            "added_timestamp": time.time()
        }
        
        # Save to file
        self._save_monitors()
        self.logger.info(f"Added {directory} to monitored directories")
        return True
    
    def remove_directory(self, directory: str) -> bool:
        """
        Remove a directory from monitoring.
        
        Args:
            directory: Directory path to stop monitoring
            
        Returns:
            True if the directory was removed, False otherwise
        """
        directory = os.path.abspath(directory)
        
        if directory not in self.monitors:
            self.logger.warning(f"Not monitoring {directory}")
            return False
        
        # Remove from monitored directories
        del self.monitors[directory]
        self._save_monitors()
        self.logger.info(f"Removed {directory} from monitored directories")
        return True
    
    def get_monitored_directories(self) -> Dict[str, Dict]:
        """
        Get all monitored directories.
        
        Returns:
            Dictionary of monitored directories and their info
        """
        # Return a copy to avoid modifying the original data
        result = {}
        for dir_path, info in self.monitors.items():
            # Create a copy of the info dictionary
            info_copy = info.copy()
            # If processed_files is a set, convert to list for display
            if 'processed_files' in info_copy and isinstance(info_copy['processed_files'], set):
                info_copy['processed_files'] = list(info_copy['processed_files'])
            result[dir_path] = info_copy
        
        return result
    
    def check_for_new_files(self, directory: str) -> List[str]:
        """
        Check for new files in a monitored directory.
        
        Args:
            directory: Directory path to check
            
        Returns:
            List of new files found
        """
        if directory not in self.monitors:
            self.logger.warning(f"Not monitoring {directory}")
            return []
        
        try:
            monitor = FileMonitor(directory)
            all_files = monitor.scan_directory()
            
            # Filter out already processed files
            if 'processed_files' not in self.monitors[directory]:
                self.monitors[directory]['processed_files'] = set()
            
            processed_files = self.monitors[directory]['processed_files']
            new_files = [f for f in all_files if f not in processed_files]
            
            self.monitors[directory]["last_checked"] = time.time()
            self._save_monitors()
            
            # Return the new files found
            return new_files
        except Exception as e:
            self.logger.error(f"Error checking for new files in {directory}: {e}")
            return []
    
    def mark_files_processed(self, directory: str, files: List[str]) -> None:
        """
        Mark files as processed.
        
        Args:
            directory: Directory path where files were processed
            files: List of processed files
        """
        if directory not in self.monitors:
            self.logger.warning(f"Not monitoring {directory}")
            return
        
        # Update processed files
        if "processed_files" not in self.monitors[directory]:
            self.monitors[directory]["processed_files"] = set()
            
        for file in files:
            self.monitors[directory]["processed_files"].add(file)
        
        # Save changes
        self._save_monitors()
    
    def start_monitoring(self, interval: int = 60) -> bool:
        """
        Start monitoring all directories in a background thread.
        
        Args:
            interval: Check interval in seconds
            
        Returns:
            True if monitoring started, False if already monitoring
        """
        if self.monitoring_thread and self.monitoring_thread.is_alive():
            self.logger.warning("Already monitoring")
            return False
        
        self.stop_event.clear()
        self.monitoring_thread = threading.Thread(
            target=self._monitor_loop, 
            args=(interval,),
            daemon=True
        )
        self.monitoring_thread.start()
        self.logger.info(f"Started monitoring {len(self.monitors)} directories every {interval} seconds")
        return True
    
    def stop_monitoring(self) -> bool:
        """
        Stop the monitoring thread.
        
        Returns:
            True if monitoring was stopped, False if not monitoring
        """
        if not self.monitoring_thread or not self.monitoring_thread.is_alive():
            self.logger.warning("Not currently monitoring")
            return False
        
        self.logger.info("Stopping monitoring...")
        self.stop_event.set()
        self.monitoring_thread.join(timeout=10)
        self.logger.info("Monitoring stopped")
        return True
    
    def is_monitoring(self) -> bool:
        """
        Check if the monitoring thread is active.
        
        Returns:
            True if monitoring, False otherwise
        """
        return self.monitoring_thread is not None and self.monitoring_thread.is_alive()
    
    def _monitor_loop(self, interval: int) -> None:
        """
        Main monitoring loop.
        
        Args:
            interval: Check interval in seconds
        """
        self.logger.info(f"Monitor loop started with {interval} second interval")
        
        while not self.stop_event.is_set():
            for directory in list(self.monitors.keys()):
                if not os.path.isdir(directory):
                    self.logger.warning(f"Directory {directory} no longer exists")
                    continue
                
                # Check for new files
                new_files = self.check_for_new_files(directory)
                
                # If new files found, send notification
                if new_files:
                    self.logger.info(f"Found {len(new_files)} new files in {directory}")
                    
                    # Get Discord webhook URL from environment variable
                    webhook_url = os.environ.get('DISCORD_WEBHOOK_URL', '')
                    discord_enabled = os.environ.get('ENABLE_DISCORD_NOTIFICATIONS', 'false').lower() == 'true'
                    
                    if webhook_url and discord_enabled:
                        description = self.monitors[directory].get("description", os.path.basename(directory))
                        title = f"New Files Detected: {description}"
                        message = f"Scanly found {len(new_files)} new files in a monitored directory."
                        
                        send_discord_notification(
                            webhook_url=webhook_url,
                            title=title,
                            message=message,
                            files=new_files,
                            directory=directory
                        )
            
            # Sleep for the specified interval
            self.stop_event.wait(interval)