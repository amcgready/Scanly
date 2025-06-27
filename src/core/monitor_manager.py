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
import sys
import re

# Fix import path issues - add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

try:
    from src.core.file_monitor import FileMonitor
    from src.utils.discord_utils import send_discord_notification
    from src.utils.logger import get_logger
    from src.utils.scan_history_utils import is_path_in_scan_history
except ImportError:
    # Define fallback logger if imports fail
    import logging
    def get_logger(name):
        return logging.getLogger(name)

logger = get_logger(__name__)

class MonitorManager:
    """
    Manages directories to monitor and processes new files.
    """
    
    def __init__(self):
        """Initialize the monitor manager."""
        self.logger = get_logger(__name__)
        self.monitored_directories = {}  # Fix: Use consistent variable name
        self.monitoring_thread = None
        self.stop_event = threading.Event()
        
        # Load existing monitored directories
        self._load_monitored_directories()  # Fix: Use consistent method name
    
    def _get_monitored_directories_file(self) -> str:
        """Get the path to the monitored directories JSON file."""
        return os.path.join(os.path.dirname(os.path.dirname(__file__)), 'monitored_directories.json')
    
    def _load_monitored_directories(self) -> None:
        """Load monitored directories from file."""
        try:
            monitors_file = self._get_monitored_directories_file()
            if os.path.exists(monitors_file):
                with open(monitors_file, 'r') as f:
                    self.monitored_directories = json.load(f)
                self.logger.info(f"Loaded {len(self.monitored_directories)} monitored directories")
        except Exception as e:
            self.logger.error(f"Error loading monitored directories: {e}")
            self.monitored_directories = {}
    
    def _save_monitored_directories(self) -> None:
        """Save monitored directories to file."""
        try:
            monitors_file = self._get_monitored_directories_file()
            with open(monitors_file, 'w') as f:
                json.dump(self.monitored_directories, f, indent=4)
            self.logger.info(f"Saved {len(self.monitored_directories)} monitored directories")
        except Exception as e:
            self.logger.error(f"Error saving monitored directories: {e}")
    
    def _scan_directory(self, directory_path):
        """
        Scan a directory recursively and return a list of all files.
        
        Args:
            directory_path: Path to scan
        
        Returns:
            List of file paths
        """
        file_list = []
        
        # Only scan for media files
        media_extensions = ['.mkv', '.mp4', '.avi', '.mov', '.wmv', '.flv', '.m4v', '.ts']
        
        try:
            for root, _, files in os.walk(directory_path):
                for file in files:
                    if any(file.lower().endswith(ext) for ext in media_extensions):
                        file_list.append(os.path.join(root, file))
        except Exception as e:
            self.logger.error(f"Error scanning directory {directory_path}: {e}")
        
        return file_list

    def get_directory_by_id(self, directory_id):
        """
        Get directory info by directory ID.
        
        Args:
            directory_id: ID of the directory to retrieve
        
        Returns:
            Directory info dictionary or None if not found
        """
        return self.monitored_directories.get(directory_id)

    def add_directory(self, directory_path, description="", auto_process=False):
        """
        Add a directory to the monitoring list.
        
        Args:
            directory_path: Path to the directory to monitor
            description: Optional description
            auto_process: Whether to process files automatically when detected
        
        Returns:
            bool: True if successful
        """
        # Check if directory exists
        if not os.path.isdir(directory_path):
            self.logger.error(f"Directory does not exist: {directory_path}")
            return False
        
        # Generate a unique ID for the directory
        import uuid
        directory_id = str(uuid.uuid4())
        
        # Scan all existing files in the directory
        existing_files = self._scan_directory(directory_path)
        
        # Check for TMDB IDs in folder names
        folders_with_ids = {}
        for file_path in existing_files:
            subfolder = os.path.dirname(file_path)
            subfolder_name = os.path.basename(subfolder)
            
            # Look for TMDB ID in folder name
            tmdb_id_match = re.search(r'\[(\d+)\]', subfolder_name)
            if tmdb_id_match:
                tmdb_id = tmdb_id_match.group(1)
                folders_with_ids[subfolder] = tmdb_id
        
        if folders_with_ids:
            self.logger.info(f"Found {len(folders_with_ids)} folders with TMDB IDs")
        
        # Add to monitoring list
        self.monitored_directories[directory_id] = {
            'path': directory_path,
            'description': description or os.path.basename(directory_path),
            'added': time.time(),
            'active': True,
            'known_files': existing_files.copy(),  # Initialize with current files
            'pending_files': existing_files.copy(),  # Add all existing files as pending for processing
            'auto_process': auto_process,  # Store this setting for future reference
            'tmdb_folders': folders_with_ids,  # Store folders with TMDB IDs
            'stats': {
                'total_processed': 0,
                'total_errors': 0,
                'total_skipped': 0,
                'last_processed': 0
            }
        }
        
        # If auto-process is requested, process all existing files immediately
        if auto_process and existing_files:
            try:
                from src.core.monitor_processor import MonitorProcessor
                processor = MonitorProcessor(auto_mode=True)  # Force auto-mode for auto-processing
                processed, errors, skipped = processor.process_new_files(directory_path, existing_files)
                
                # Clear pending files that were processed
                self.monitored_directories[directory_id]['pending_files'] = []
                
                # Update stats
                self._record_processing(directory_id, processed, errors, skipped)
                
                self.logger.info(f"Auto-processed {len(existing_files)} existing files in {directory_path}: "
                                f"{processed} processed, {errors} errors, {skipped} skipped")
            except Exception as e:
                self.logger.error(f"Error auto-processing existing files: {e}", exc_info=True)
        
        # Save changes
        self._save_monitored_directories()
        
        self.logger.info(f"Added directory to monitoring: {directory_path}")
        return True

    def remove_directory(self, directory_id):
        """
        Remove a directory from monitoring.
        
        Args:
            directory_id: ID of the directory to remove
            
        Returns:
            True if the directory was removed, False otherwise
        """
        if directory_id not in self.monitored_directories:
            self.logger.warning(f"No directory with ID {directory_id} found")
            return False
        
        # Get directory path for logging
        directory_path = self.monitored_directories[directory_id].get('path', 'Unknown path')
        
        # Remove from monitored directories
        del self.monitored_directories[directory_id]
        self._save_monitored_directories()
        self.logger.info(f"Removed {directory_path} from monitored directories")
        return True
    
    def get_monitored_directories(self):
        """
        Get all monitored directories.
        
        Returns:
            Dictionary of monitored directories and their info
        """
        # Return a copy to avoid modifying the original data
        return self.monitored_directories.copy()
    
    def check_for_new_files(self, directory_id):
        """
        Check for new files in a monitored directory.
        
        Args:
            directory_id: ID of the directory to check
            
        Returns:
            List of new files found
        """
        directory_info = self.get_directory_by_id(directory_id)
        if not directory_info:
            self.logger.warning(f"No directory with ID {directory_id} found")
            return []
        
        directory_path = directory_info.get('path')
        if not os.path.isdir(directory_path):
            self.logger.warning(f"Directory {directory_path} no longer exists")
            return []
        
        # Use detect_changes instead
        return self.detect_changes(directory_id)
    
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
        self.logger.info(f"Started monitoring {len(self.monitored_directories)} directories every {interval} seconds")
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
            try:
                # Use monitor_directories method to handle all directories
                self.monitor_directories()
            except Exception as e:
                self.logger.error(f"Error in monitor loop: {e}", exc_info=True)
            
            # Sleep for the specified interval
            self.stop_event.wait(interval)

    def handle_new_files(self, directory_id, new_files, auto_process=None):
        """
        Handle newly detected files in a monitored directory.
        
        Args:
            directory_id: ID of the monitored directory
            new_files: List of new file paths detected
            auto_process: Override the directory's auto_process setting if provided
        
        Returns:
            Tuple of (processed_count, error_count, skipped_count)
        """
        # Get directory info
        directory_info = self.get_directory_by_id(directory_id)
        if not directory_info:
            self.logger.error(f"Cannot find directory with ID {directory_id}")
            return 0, 0, 0
        
        directory_path = directory_info.get('path')
        if not os.path.exists(directory_path):
            self.logger.error(f"Directory no longer exists: {directory_path}")
            return 0, 0, 0
        
        # Use the directory's auto_process setting if not explicitly overridden
        should_auto_process = auto_process if auto_process is not None else directory_info.get('auto_process', False)
        
        # If auto-process is enabled, process the files immediately
        if should_auto_process:
            try:
                from src.core.monitor_processor import MonitorProcessor
                processor = MonitorProcessor(auto_mode=True)  # Force auto-mode for auto-processing
                processed, errors, skipped = processor.process_new_files(directory_path, new_files)
                
                # Log the results
                self.logger.info(f"Auto-processing completed for {directory_path}: "
                                 f"{processed} processed, {errors} errors, {skipped} skipped")
                
                # Record the processing in the monitor history
                self._record_processing(directory_id, processed, errors, skipped)
                
                # Only remove the successfully processed files from pending files
                # Keep skipped files and error files in the pending queue for manual processing later
                if 'pending_files' in directory_info and processed > 0:
                    # We don't know exactly which files were processed vs. skipped/errored
                    # So let's update the known_files list but keep all files in pending for now
                    directory_info['known_files'] = list(set(directory_info.get('known_files', []) + new_files))
                    
                    # Let's update this to track which files were skipped
                    try:
                        from src.main import load_skipped_items
                        skipped_items = load_skipped_items()
                        skipped_paths = [item.get('path') for item in skipped_items]
                        
                        # Keep only skipped files in pending_files
                        pending = directory_info['pending_files']
                        pending = [f for f in pending if f in skipped_paths]
                        pending.extend([f for f in new_files if f in skipped_paths])
                        directory_info['pending_files'] = pending
                    except Exception as e:
                        self.logger.error(f"Error updating pending files: {e}")
                    
                    self._save_monitored_directories()
                
                return processed, errors, skipped
            except Exception as e:
                self.logger.error(f"Error in auto-processing: {e}", exc_info=True)
                return 0, 0, 0
        else:
            # Store files for manual processing later
            if 'pending_files' not in directory_info:
                directory_info['pending_files'] = []
                
            # Add new files to pending list if they're not already there
            for file_path in new_files:
                if file_path not in directory_info['pending_files']:
                    directory_info['pending_files'].append(file_path)
            
            # Save the updated information
            self._save_monitored_directories()
            
            # Log that files were added to pending
            self.logger.info(f"Added {len(new_files)} files to pending queue for {directory_path}")
            
            return 0, 0, len(new_files)

    def clear_pending_files(self, directory_id):
        """
        Clear pending files from a monitored directory.
        
        Args:
            directory_id: ID of the monitored directory
        
        Returns:
            bool: True if successful
        """
        directory_info = self.get_directory_by_id(directory_id)
        if not directory_info:
            return False
        
        # Clear pending files
        directory_info['pending_files'] = []
        
        # Save the updated information
        self._save_monitored_directories()
        
        return True

    def _record_processing(self, directory_id, processed_count, error_count, skipped_count):
        """
        Record processing statistics in the monitor history.
        
        Args:
            directory_id: ID of the monitored directory
            processed_count: Number of files processed
            error_count: Number of errors encountered
            skipped_count: Number of files skipped
        """
        directory_info = self.get_directory_by_id(directory_id)
        if not directory_info:
            return
        
        # Update directory stats
        if 'stats' not in directory_info:
            directory_info['stats'] = {}
        
        stats = directory_info['stats']
        stats['last_processed'] = time.time()
        stats['total_processed'] = stats.get('total_processed', 0) + processed_count
        stats['total_errors'] = stats.get('total_errors', 0) + error_count
        stats['total_skipped'] = stats.get('total_skipped', 0) + skipped_count
        
        # Save the updated information
        self._save_monitored_directories()

    def detect_changes(self, directory_id):
        """
        Check for new files in a monitored directory.
        
        Args:
            directory_id: ID of the monitored directory
        
        Returns:
            List of new file paths detected
        """
        # Get directory info
        directory_info = self.get_directory_by_id(directory_id)
        if not directory_info:
            self.logger.error(f"Cannot find directory with ID {directory_id}")
            return []
        
        directory_path = directory_info.get('path')
        if not os.path.exists(directory_path):
            self.logger.error(f"Directory no longer exists: {directory_path}")
            return []
        
        # Get current file list
        current_files = self._scan_directory(directory_path)
        
        # Get known files for this directory
        known_files = set(directory_info.get('known_files', []))
        
        # Find new files - files in current scan but not in known files
        new_files = [f for f in current_files if f not in known_files]
        
        if new_files:
            self.logger.info(f"Found {len(new_files)} new files in {directory_path}")
            
            # Add new files to pending if not already there
            if 'pending_files' not in directory_info:
                directory_info['pending_files'] = []
                
            for file_path in new_files:
                if file_path not in directory_info['pending_files']:
                    directory_info['pending_files'].append(file_path)
            
            # Update known files
            directory_info['known_files'] = list(known_files.union(set(new_files)))
            
            # Save changes
            self._save_monitored_directories()
            
        return new_files

    def monitor_directories(self):
        """
        Monitor all directories for changes.
        """
        self.logger.debug(f"Checking monitored directories...")
        
        for dir_id in list(self.monitored_directories.keys()):
            # Skip directories that are not active
            if not self.monitored_directories[dir_id].get('active', True):
                continue
            
            directory_info = self.monitored_directories[dir_id]
            auto_process = directory_info.get('auto_process', False)
                    
            # Check for new files
            new_files = self.detect_changes(dir_id)
            
            if new_files:
                # Process according to the directory's auto_process setting
                self.handle_new_files(dir_id, new_files, auto_process=auto_process)

    def get_pending_files_count(self):
        """
        Get the total number of pending files across all monitored directories.
        
        Returns:
            int: Total number of pending files
        """
        count = 0
        for dir_info in self.monitored_directories.values():
            if 'pending_files' in dir_info:
                count += len(dir_info['pending_files'])
        return count

    def set_directory_status(self, directory_id, active_status):
        """
        Set the active status for a monitored directory.
        
        Args:
            directory_id: ID of the monitored directory
            active_status: Boolean indicating whether the directory should be actively monitored
        
        Returns:
            bool: True if successful, False otherwise
        """
        # Get directory info
        directory_info = self.get_directory_by_id(directory_id)
        if not directory_info:
            self.logger.error(f"Cannot find directory with ID {directory_id}")
            return False
        
        # Update active status
        directory_info['active'] = bool(active_status)
        
        # Start or stop monitoring as needed
        if active_status:
            # Start monitoring for this directory if not already monitored
            if hasattr(self, 'start_monitoring_for_directory'):
                self.start_monitoring_for_directory(directory_id)
            else:
                self.logger.warning("start_monitoring_for_directory method not implemented.")
        else:
            # Stop monitoring for this directory if currently monitored
            if hasattr(self, 'stop_monitoring_for_directory'):
                self.stop_monitoring_for_directory(directory_id)
            else:
                self.logger.warning("stop_monitoring_for_directory method not implemented.")

        # Save the updated information
        self._save_monitored_directories()
        
        # Log the status change
        status_str = "active" if active_status else "paused"
        self.logger.info(f"Directory {directory_id} monitoring status set to {status_str}")
        
        return True

# Add this for direct testing
if __name__ == "__main__":
    # Setup basic logging
    import logging
    logging.basicConfig(level=logging.INFO, 
                       format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # Test the manager
    manager = MonitorManager()
    print(f"Loaded {len(manager.monitored_directories)} monitored directories")