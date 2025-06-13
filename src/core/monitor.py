#!/usr/bin/env python3
"""
Monitor module for Scanly to detect changes in directories.
"""
import os
import sys
import json
import time
import logging
import threading
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

logger = logging.getLogger(__name__)

class DirectoryChangeHandler(FileSystemEventHandler):
    """Event handler for directory changes that detects new folders."""
    def __init__(self, callback, directory_id):
        self.callback = callback
        self.directory_id = directory_id
        self.changes = set()
        self.last_notification_time = 0
        
    def on_created(self, event):
        """Handle file/directory creation events."""
        if event.is_directory:
            # Filter out common system directories
            path = event.src_path
            # Avoid hidden folders, git, __pycache__, etc.
            if os.path.basename(path).startswith('.'):
                return
            if any(excluded in path for excluded in ['.git', '__pycache__', 'node_modules']):
                return
                
            self.changes.add(path)
            self._schedule_notification()
    
    def _schedule_notification(self):
        """Throttle notifications to avoid spamming."""
        current_time = time.time()
        if current_time - self.last_notification_time > 5.0:  # 5 second cooldown
            self.last_notification_time = current_time
            changes = list(self.changes)
            self.changes.clear()
            if changes:  # Only notify if there are actual changes
                self.callback(changes, self.directory_id)


class MonitorManager:
    """Manages monitored directories and their state."""
    def __init__(self, config_path=None):
        if config_path is None:
            # Create path relative to the directory where this script is located
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            self.config_path = os.path.join(base_dir, 'config', 'monitored_directories.json')
        else:
            self.config_path = config_path
            
        self._observers = {}
        self._monitored_directories = {}
        self._ensure_config_dir()
        self._load_monitored_directories()
        
    def _ensure_config_dir(self):
        """Ensure the config directory exists."""
        config_dir = os.path.dirname(self.config_path)
        os.makedirs(config_dir, exist_ok=True)
        
    def _load_monitored_directories(self):
        """Load monitored directories from config file."""
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r') as f:
                    self._monitored_directories = json.load(f)
                logger.info(f"Loaded {len(self._monitored_directories)} monitored directories")
            except json.JSONDecodeError:
                logger.error(f"Error parsing monitored directories file: {self.config_path}")
                self._monitored_directories = {}
        else:
            logger.info("No monitored directories file found, creating a new one")
            self._monitored_directories = {}
            self._save_monitored_directories()
            
    def _save_monitored_directories(self):
        """Save monitored directories to config file."""
        try:
            with open(self.config_path, 'w') as f:
                json.dump(self._monitored_directories, f, indent=2)
            logger.info(f"Saved {len(self._monitored_directories)} monitored directories")
            return True
        except Exception as e:
            logger.error(f"Error saving monitored directories: {e}")
            return False
    
    def get_monitored_directories(self):
        """Get all monitored directories."""
        return self._monitored_directories
    
    def add_directory(self, path, name=None):
        """
        Add a directory to monitor.
        
        Args:
            path (str): Path to the directory
            name (str, optional): Name for the directory. Defaults to the directory name.
            
        Returns:
            str: ID of the added directory or None if failed
        """
        if not os.path.isdir(path):
            logger.error(f"Cannot add non-existent directory: {path}")
            return None
        
        # Clean the path
        path = os.path.abspath(path)
        
        # If this path is already monitored, return the existing ID
        for dir_id, info in self._monitored_directories.items():
            if info.get('path') == path:
                return dir_id
        
        # Generate a new ID
        dir_id = str(int(time.time()))
        
        # Set directory name if not provided
        if not name:
            name = os.path.basename(path)
        
        # Add to monitored directories
        self._monitored_directories[dir_id] = {
            'path': path,
            'name': name,
            'active': True,
            'added_time': time.time(),
            'pending_files': []
        }
        
        # Save changes
        self._save_monitored_directories()
        
        # Start monitoring this directory
        self._start_monitoring(dir_id)
        
        return dir_id
    
    def remove_directory(self, dir_id):
        """Remove a directory from monitoring."""
        if dir_id not in self._monitored_directories:
            logger.error(f"Directory ID not found: {dir_id}")
            return False
        
        # Stop monitoring
        self._stop_monitoring(dir_id)
        
        # Remove from monitored directories
        del self._monitored_directories[dir_id]
        
        # Save changes
        self._save_monitored_directories()
        
        return True
    
    def toggle_directory_active(self, dir_id):
        """Toggle the active state of a monitored directory."""
        if dir_id not in self._monitored_directories:
            logger.error(f"Directory ID not found: {dir_id}")
            return False
        
        # Toggle active state
        self._monitored_directories[dir_id]['active'] = not self._monitored_directories[dir_id]['active']
        
        # Start or stop monitoring based on new state
        if self._monitored_directories[dir_id]['active']:
            self._start_monitoring(dir_id)
        else:
            self._stop_monitoring(dir_id)
        
        # Save changes
        self._save_monitored_directories()
        
        return self._monitored_directories[dir_id]['active']
    
    def add_pending_file(self, dir_id, file_path):
        """Add a file to the pending list for a directory."""
        if dir_id not in self._monitored_directories:
            logger.error(f"Directory ID not found: {dir_id}")
            return False
        
        # Check if file already exists in pending list
        pending_files = self._monitored_directories[dir_id].get('pending_files', [])
        if file_path not in pending_files:
            pending_files.append(file_path)
            self._monitored_directories[dir_id]['pending_files'] = pending_files
            self._save_monitored_directories()
            logger.info(f"Added pending file: {file_path} to directory {dir_id}")
        
        return True
    
    def remove_pending_file(self, dir_id, file_path):
        """Remove a file from the pending list for a directory."""
        if dir_id not in self._monitored_directories:
            logger.error(f"Directory ID not found: {dir_id}")
            return False
        
        # Get pending files
        pending_files = self._monitored_directories[dir_id].get('pending_files', [])
        
        # Remove file if it exists
        if file_path in pending_files:
            pending_files.remove(file_path)
            self._monitored_directories[dir_id]['pending_files'] = pending_files
            self._save_monitored_directories()
            logger.info(f"Removed pending file: {file_path} from directory {dir_id}")
        
        return True
    
    def get_all_pending_files(self):
        """Get all pending files from all monitored directories."""
        result = []
        for dir_id, info in self._monitored_directories.items():
            dir_name = info.get('name', 'Unknown')
            dir_path = info.get('path', '')
            for file_path in info.get('pending_files', []):
                # Skip if file no longer exists
                if not os.path.exists(file_path):
                    continue
                    
                result.append({
                    'dir_id': dir_id,
                    'dir_name': dir_name,
                    'dir_path': dir_path,
                    'path': file_path,
                    'name': os.path.basename(file_path)
                })
        return result
    
    def _on_directory_change(self, changes, dir_id):
        """Handle changes in monitored directories."""
        if not changes:
            return
        
        if dir_id not in self._monitored_directories:
            logger.error(f"Directory ID not found: {dir_id}")
            return
            
        dir_info = self._monitored_directories[dir_id]
        dir_name = dir_info.get('name', 'Unknown')
        
        logger.info(f"Changes detected in {dir_name}: {len(changes)} new items")
        
        # Get discord webhook from environment variable
        webhook_url = os.environ.get('DISCORD_WEBHOOK_URL')
        
        for file_path in changes:
            # Add to pending files
            self.add_pending_file(dir_id, file_path)
            
            # Get the file name for notifications
            file_name = os.path.basename(file_path)
            
            # Send discord notification if webhook URL is configured
            if webhook_url:
                try:
                    from discord_webhook import DiscordWebhook
                    
                    webhook = DiscordWebhook(
                        url=webhook_url,
                        content=f"📁 New content detected: **{file_name}** in {dir_name}"
                    )
                    response = webhook.execute()
                    logger.info(f"Sent Discord notification for {file_name}")
                except ImportError:
                    logger.warning("discord_webhook package not installed, skipping notification")
                except Exception as e:
                    logger.error(f"Error sending Discord notification: {e}")
    
    def _start_monitoring(self, dir_id):
        """Start monitoring a directory."""
        if dir_id not in self._monitored_directories:
            logger.error(f"Directory ID not found: {dir_id}")
            return False
        
        # Get directory info
        dir_info = self._monitored_directories[dir_id]
        path = dir_info.get('path')
        
        if not path or not os.path.isdir(path):
            logger.error(f"Invalid directory path: {path}")
            return False
        
        # Stop existing observer if any
        self._stop_monitoring(dir_id)
        
        # Create a new observer
        observer = Observer()
        event_handler = DirectoryChangeHandler(
            callback=self._on_directory_change, 
            directory_id=dir_id
        )
        
        observer.schedule(event_handler, path, recursive=False)
        observer.daemon = True  # Ensure observer threads don't block program exit
        observer.start()
        self._observers[dir_id] = observer
        
        logger.info(f"Started monitoring directory: {path}")
        return True
    
    def _stop_monitoring(self, dir_id):
        """Stop monitoring a directory."""
        if dir_id in self._observers:
            try:
                self._observers[dir_id].stop()
                self._observers[dir_id].join(timeout=2.0)
                del self._observers[dir_id]
                logger.info(f"Stopped monitoring directory ID: {dir_id}")
                return True
            except Exception as e:
                logger.error(f"Error stopping directory monitoring: {e}")
                return False
        return True  # Return true if not monitoring (already stopped)
    
    def start_all(self):
        """Start monitoring all active directories."""
        count = 0
        for dir_id, info in self._monitored_directories.items():
            if info.get('active', True):
                if self._start_monitoring(dir_id):
                    count += 1
        logger.info(f"Started monitoring {count} active directories")
    
    def stop_all(self):
        """Stop monitoring all directories."""
        for dir_id in list(self._observers.keys()):
            self._stop_monitoring(dir_id)
        logger.info("Stopped all directory monitoring")

    # Add this method to the MonitorManager class
    def run_pending_scans(self):
        """Run scans for all pending files in monitored directories."""
        pending_files = self.get_all_pending_files()
        
        if not pending_files:
            logger.info("No pending files to scan")
            return 0
        
        logger.info(f"Running scan for {len(pending_files)} pending files")
        processed_count = 0
        
        try:
            from src.main import DirectoryProcessor
            
            for file_info in pending_files:
                dir_id = file_info['dir_id']
                file_path = file_info['path']
                
                # Skip if file no longer exists
                if not os.path.exists(file_path):
                    logger.warning(f"Skipping non-existent path: {file_path}")
                    self.remove_pending_file(dir_id, file_path)
                    continue
                
                logger.info(f"Processing pending file: {file_path}")
                
                # Create a processor for this specific path
                processor = DirectoryProcessor(file_path)
                result = processor._process_media_files()
                
                # Remove from pending list if processed successfully
                if result is not None and result >= 0:
                    self.remove_pending_file(dir_id, file_path)
                    processed_count += 1
                else:
                    logger.warning(f"Failed to process {file_path}")
    
        except ImportError:
            logger.error("Could not import DirectoryProcessor. Check your installation.")
        except Exception as e:
            logger.exception(f"Error processing pending files: {e}")
        
        return processed_count


# Global monitor manager instance for reuse
_monitor_manager = None

def get_monitor_manager():
    """Get a global instance of the MonitorManager."""
    global _monitor_manager
    if _monitor_manager is None:
        _monitor_manager = MonitorManager()
    return _monitor_manager