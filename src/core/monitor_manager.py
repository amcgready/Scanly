"""
Monitor manager functionality for Scanly.

This module provides the MonitorManager class for managing monitored directories.
"""

import os
import time
import json
import uuid
import threading
import logging
from pathlib import Path

def get_logger(name):
    """Get a logger with the given name."""
    return logging.getLogger(name)

class MonitorManager:
    """Manage directory monitoring for media files."""
    
    def __init__(self):
        self.logger = get_logger(__name__)
        self.monitored_directories = {}
        self.stop_event = threading.Event()
        self.monitoring_thread = None
        
        # Load existing monitored directories
        self._load_monitored_directories()
    
    def _load_monitored_directories(self):
        """Load monitored directories from the configuration file."""
        try:
            config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'config', 'monitored_dirs.json')
            os.makedirs(os.path.dirname(config_path), exist_ok=True)
            
            if os.path.exists(config_path):
                with open(config_path, 'r') as f:
                    self.monitored_directories = json.load(f)
                self.logger.info(f"Loaded {len(self.monitored_directories)} monitored directories")
            else:
                self.logger.info("No monitored directories configuration found")
                self.monitored_directories = {}
                
        except Exception as e:
            self.logger.error(f"Error loading monitored directories: {e}")
            self.monitored_directories = {}
    
    def _save_monitored_directories(self):
        """Save monitored directories to the configuration file."""
        try:
            config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'config', 'monitored_dirs.json')
            os.makedirs(os.path.dirname(config_path), exist_ok=True)
            
            with open(config_path, 'w') as f:
                json.dump(self.monitored_directories, f, indent=2)
            
            self.logger.info("Saved monitored directories configuration")
            return True
        except Exception as e:
            self.logger.error(f"Error saving monitored directories: {e}")
            return False
    
    def add_directory(self, path, description=None, auto_process=False):
        """
        Add a directory to the monitoring list.
        
        Args:
            path: Path to monitor
            description: Optional description
            auto_process: Whether to automatically process new files
            
        Returns:
            str: ID of the added directory if successful
        """
        try:
            # Check if directory exists
            if not os.path.isdir(path):
                self.logger.error(f"Directory does not exist: {path}")
                return False
            
            # Check if directory is already monitored
            for dir_id, info in self.monitored_directories.items():
                if os.path.samefile(info['path'], path):
                    self.logger.warning(f"Directory is already monitored: {path}")
                    return dir_id
            
            # Generate unique ID for this directory
            dir_id = str(uuid.uuid4())
            
            # Add to monitored directories
            self.monitored_directories[dir_id] = {
                'path': path,
                'description': description or os.path.basename(path),
                'active': True,
                'auto_process': auto_process,
                'known_files': [],
                'pending_files': [],
                'stats': {
                    'total_processed': 0,
                    'last_processed': 0
                },
                'added_time': time.time()
            }
            
            # Save changes
            self._save_monitored_directories()
            
            self.logger.info(f"Added directory to monitoring: {path}")
            return dir_id
            
        except Exception as e:
            self.logger.error(f"Error adding directory: {e}")
            return False
    
    def remove_directory(self, dir_id):
        """
        Remove a directory from monitoring.
        
        Args:
            dir_id: ID of directory to remove
            
        Returns:
            bool: True if removed, False otherwise
        """
        try:
            if dir_id in self.monitored_directories:
                path = self.monitored_directories[dir_id]['path']
                del self.monitored_directories[dir_id]
                self._save_monitored_directories()
                self.logger.info(f"Removed directory from monitoring: {path}")
                return True
            else:
                self.logger.warning(f"Directory ID not found: {dir_id}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error removing directory: {e}")
            return False
    
    def set_directory_status(self, dir_id, active):
        """
        Set the active status of a monitored directory.
        
        Args:
            dir_id: ID of directory to update
            active: Whether the directory should be actively monitored
            
        Returns:
            bool: True if updated, False otherwise
        """
        try:
            if dir_id in self.monitored_directories:
                self.monitored_directories[dir_id]['active'] = bool(active)
                self._save_monitored_directories()
                status = "active" if active else "inactive"
                self.logger.info(f"Set directory {dir_id} status to {status}")
                return True
            else:
                self.logger.warning(f"Directory ID not found: {dir_id}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error setting directory status: {e}")
            return False
    
    def get_monitored_directories(self):
        """
        Get all monitored directories.
        
        Returns:
            dict: Monitored directories information
        """
        return self.monitored_directories
    
    def _record_processing(self, dir_id, processed=0, errors=0, skipped=0):
        """
        Record processing statistics for a directory.
        
        Args:
            dir_id: ID of the directory
            processed: Number of files processed
            errors: Number of errors encountered
            skipped: Number of files skipped
            
        Returns:
            bool: True if updated, False otherwise
        """
        try:
            if dir_id in self.monitored_directories:
                # Update stats
                stats = self.monitored_directories[dir_id].get('stats', {})
                stats['total_processed'] = stats.get('total_processed', 0) + processed
                stats['last_processed'] = time.time()
                stats['last_errors'] = errors
                stats['last_skipped'] = skipped
                
                # Save the updated stats
                self.monitored_directories[dir_id]['stats'] = stats
                self._save_monitored_directories()
                
                return True
            else:
                self.logger.warning(f"Directory ID not found: {dir_id}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error recording processing stats: {e}")
            return False
    
    def clear_pending_files(self, dir_id):
        """
        Clear pending files for a directory.
        
        Args:
            dir_id: ID of the directory
            
        Returns:
            bool: True if cleared, False otherwise
        """
        try:
            if dir_id in self.monitored_directories:
                self.monitored_directories[dir_id]['pending_files'] = []
                self._save_monitored_directories()
                self.logger.info(f"Cleared pending files for directory {dir_id}")
                return True
            else:
                self.logger.warning(f"Directory ID not found: {dir_id}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error clearing pending files: {e}")
            return False
    
    def detect_changes(self, directory_id):
        """
        Check for new files in a monitored directory.
        
        Args:
            directory_id: ID of the monitored directory
            
        Returns:
            List of new file paths detected
        """
        if directory_id not in self.monitored_directories:
            self.logger.warning(f"Directory ID not found: {directory_id}")
            return []
        
        directory_info = self.monitored_directories[directory_id]
        directory_path = directory_info.get('path', '')
        
        # Check if directory exists
        if not os.path.isdir(directory_path):
            self.logger.warning(f"Directory does not exist: {directory_path}")
            return []
        
        try:
            # Get known files
            known_files = set(directory_info.get('known_files', []))
            
            # Get current files
            current_files = []
            allowed_extensions = os.environ.get('ALLOWED_EXTENSIONS', '.mp4,.mkv,.srt,.avi,.mov').split(',')
            
            for root, dirs, files in os.walk(directory_path):
                for file in files:
                    file_path = os.path.join(root, file)
                    file_ext = os.path.splitext(file)[1].lower()
                    
                    if not allowed_extensions or file_ext in allowed_extensions:
                        current_files.append(file_path)
            
            # Find new files
            current_files_set = set(current_files)
            new_files = list(current_files_set - known_files)
            
            # Update known files
            if new_files:
                self.logger.info(f"Found {len(new_files)} new files in {directory_path}")
                
                # Add new files to pending if not already there
                if 'pending_files' not in directory_info:
                    directory_info['pending_files'] = []
                    
                for file_path in new_files:
                    if file_path not in directory_info['pending_files']:
                        directory_info['pending_files'].append(file_path)
                
                # Update known files
                directory_info['known_files'] = list(current_files_set)
                
                # Save changes
                self._save_monitored_directories()
                
                # Send Discord notification if enabled
                self._notify_discord(directory_path, new_files, directory_id)
                
            return new_files
            
        except Exception as e:
            self.logger.error(f"Error detecting changes in {directory_path}: {e}")
            return []
    
    def _notify_discord(self, directory_path, new_files, directory_id):
        """
        Send Discord notification for new files if enabled.
        
        Args:
            directory_path: Path to the monitored directory
            new_files: List of new file paths
            directory_id: ID of the monitored directory
        """
        # Check if Discord is enabled
        if os.environ.get('DISCORD_BOT_ENABLED', 'false').lower() != 'true':
            return False
            
        try:
            # Group files by subfolder
            subfolder_files = {}
            for file_path in new_files:
                subfolder = os.path.dirname(file_path)
                subfolder_name = os.path.basename(subfolder)
                if subfolder not in subfolder_files:
                    subfolder_files[subfolder] = []
                subfolder_files[subfolder].append(file_path)
                
            # Send webhook notification first (simple notification)
            webhook_url = os.environ.get('DISCORD_WEBHOOK_URL', '')
            if webhook_url:
                try:
                    from src.utils.discord_utils import send_discord_webhook_notification
                    
                    fields = []
                    for subfolder, files in subfolder_files.items():
                        subfolder_name = os.path.basename(subfolder)
                        fields.append({
                            "name": subfolder_name,
                            "value": f"{len(files)} new file(s)",
                            "inline": True
                        })
                        
                    send_discord_webhook_notification(
                        webhook_url=webhook_url,
                        title="New Media Detected",
                        message=f"New media files detected in {directory_path}",
                        fields=fields
                    )
                except ImportError:
                    self.logger.warning("Discord utilities not available")
                except Exception as e:
                    self.logger.error(f"Error sending Discord webhook: {e}")
                
            # Send detailed bot notifications for each subfolder
            for subfolder, files in subfolder_files.items():
                subfolder_name = os.path.basename(subfolder)
                
                # Use the Discord monitor handler to send interactive notification
                try:
                    from src.discord.monitor_handler import notify_new_media
                    session_id = notify_new_media(
                        directory_path=directory_path,
                        subfolder_name=subfolder_name,
                        file_paths=files
                    )
                    
                    if session_id:
                        self.logger.info(f"Interactive Discord notification sent for {subfolder_name}")
                        
                except ImportError:
                    self.logger.warning("Discord monitor handler not available")
                    
            return True
        except Exception as e:
            self.logger.error(f"Error sending Discord notification: {e}")
            return False
    
    def _monitor_loop(self, interval):
        """
        Main monitoring loop that checks directories at the specified interval.
        
        Args:
            interval: How often to check for changes (in seconds)
        """
        self.logger.info(f"Starting monitor loop with {interval} second interval")
        
        while not self.stop_event.is_set():
            try:
                # Check each active directory
                for directory_id, info in self.monitored_directories.items():
                    # Skip inactive directories
                    if not info.get('active', True):
                        continue
                    
                    # Check for changes
                    self.logger.debug(f"Checking directory {info.get('path', '')}")
                    new_files = self.detect_changes(directory_id)
                    
                    # Process new files if auto-processing is enabled
                    if new_files and info.get('auto_process', False):
                        try:
                            from src.core.monitor_processor import MonitorProcessor
                            processor = MonitorProcessor(auto_mode=True)
                            
                            self.logger.info(f"Auto-processing {len(new_files)} files")
                            processed, errors, skipped = processor.process_new_files(
                                info.get('path', ''), 
                                new_files
                            )
                            
                            # Record the results
                            self._record_processing(directory_id, processed, errors, skipped)
                            
                            # Clear processed files from pending
                            if 'pending_files' in info:
                                for file in new_files:
                                    if file in info['pending_files']:
                                        info['pending_files'].remove(file)
                                
                                # Save changes
                                self._save_monitored_directories()
                        except Exception as e:
                            self.logger.error(f"Error auto-processing files: {e}", exc_info=True)
            
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

    def _notify_discord(self, directory_path, new_files, directory_id):
        """
        Send Discord notification for new files if enabled.
        
        Args:
            directory_path: Path to the monitored directory
            new_files: List of new file paths
            directory_id: ID of the monitored directory
        """
        # Check if Discord is enabled
        if os.environ.get('DISCORD_BOT_ENABLED', 'false').lower() != 'true':
            return False
            
        try:
            # Group files by subfolder
            subfolder_files = {}
            for file_path in new_files:
                subfolder = os.path.dirname(file_path)
                subfolder_name = os.path.basename(subfolder)
                if subfolder not in subfolder_files:
                    subfolder_files[subfolder] = []
                subfolder_files[subfolder].append(file_path)
                
            # Send webhook notification first (simple notification)
            webhook_url = os.environ.get('DISCORD_WEBHOOK_URL', '')
            if webhook_url:
                try:
                    from src.utils.discord_utils import send_discord_webhook_notification
                    
                    fields = []
                    for subfolder, files in subfolder_files.items():
                        subfolder_name = os.path.basename(subfolder)
                        fields.append({
                            "name": subfolder_name,
                            "value": f"{len(files)} new file(s)",
                            "inline": True
                        })
                        
                    send_discord_webhook_notification(
                        webhook_url=webhook_url,
                        title="New Media Detected",
                        message=f"New media files detected in {directory_path}",
                        fields=fields
                    )
                except ImportError:
                    self.logger.warning("Discord utilities not available")
                except Exception as e:
                    self.logger.error(f"Error sending Discord webhook: {e}")
                
            # Send detailed bot notifications for each subfolder
            for subfolder, files in subfolder_files.items():
                subfolder_name = os.path.basename(subfolder)
                
                # Use the Discord monitor handler to send interactive notification
                try:
                    from src.discord.monitor_handler import notify_new_media
                    session_id = notify_new_media(
                        directory_path=directory_path,
                        subfolder_name=subfolder_name,
                        file_paths=files
                    )
                    
                    if session_id:
                        self.logger.info(f"Interactive Discord notification sent for {subfolder_name}")
                        
                except ImportError:
                    self.logger.warning("Discord monitor handler not available")
                    
            return True
        except Exception as e:
            self.logger.error(f"Error sending Discord notification: {e}")
            return False

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
            
            # Send Discord notification if enabled
            self._notify_discord(directory_path, new_files, directory_id)
        
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