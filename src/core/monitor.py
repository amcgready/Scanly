#!/usr/bin/env python3
"""
Monitor module for Scanly to detect changes in directories.
"""
import os
import sys
import json
import time
import uuid
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
        # Check if it's a media file
        if not event.is_directory and self._is_media_file(event.src_path):
            path = event.src_path
            logger.info(f"New file detected: {path}")
            self.changes.add(path)
            self._schedule_notification()
        # Also handle new directories
        elif event.is_directory:
            # Filter out common system directories
            path = event.src_path
            # Avoid hidden folders, git, __pycache__, etc.
            if os.path.basename(path).startswith('.'):
                return
            if any(excluded in path for excluded in ['.git', '__pycache__', 'node_modules']):
                return
                
            self.changes.add(path)
            self._schedule_notification()
    
    def _is_media_file(self, path):
        """Check if the file is a media file."""
        return path.lower().endswith(('.mkv', '.mp4', '.avi', '.m4v', '.mov'))
    
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
            
        self._observers = {}  # Critical: This dictionary tracks actual monitor observers
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
                
                # Start monitoring for directories that should be active
                active_count = 0
                for dir_id, info in self._monitored_directories.items():
                    if info.get('active', False):
                        # Start monitoring for active directories
                        logger.info(f"Activating monitoring for {dir_id} based on saved state")
                        if self._start_monitoring(dir_id):
                            active_count += 1
                            
                            # Scan for existing files
                            path = info.get('path')
                            logger.info(f"Scanning for existing files in {path}")
                            
                            # Check if this is an rclone mount
                            is_rclone = False
                            try:
                                if os.path.ismount(path):
                                    mount_info = os.popen(f"findmnt -n -o SOURCE {path}").read().lower()
                                    is_rclone = "rclone" in mount_info
                            except Exception as e:
                                logger.warning(f"Error checking mount type: {e}")
                                
                            if is_rclone:
                                self._scan_rclone_directory(dir_id, path)
                            else:
                                self._scan_existing_files(dir_id, path)
                        else:
                            # If monitoring failed to start, update the state
                            info['active'] = False
            
                # Save state after updating active flags
                self._save_monitored_directories()
                logger.info(f"Started monitoring {active_count} active directories")
                
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
        
        # Get current state
        current_state = self._monitored_directories[dir_id].get('active', False)
        new_state = not current_state
        
        logger.info(f"Toggling directory {dir_id} from {current_state} to {new_state}")
        
        # Start or stop monitoring based on new state
        if new_state:
            # We want to activate monitoring
            logger.info(f"Attempting to start monitoring for {dir_id}")
            success = self._start_monitoring(dir_id)
            if success:
                # Update directory state only if monitoring started successfully
                self._monitored_directories[dir_id]['active'] = True
                logger.info(f"Successfully started monitoring for directory {dir_id}")
                
                # IMPORTANT FIX: Immediately scan the directory for existing files
                # This ensures we detect files that are already present
                path = self._monitored_directories[dir_id].get('path')
                logger.info(f"Performing initial scan of existing files in {path}")
                
                # For rclone mounts, use the rclone scanner
                is_rclone = False
                try:
                    if os.path.ismount(path):
                        mount_info = os.popen(f"findmnt -n -o SOURCE {path}").read().lower()
                        is_rclone = "rclone" in mount_info
                except Exception as e:
                    logger.warning(f"Error checking if mount is rclone: {e}")
                
                if is_rclone:
                    logger.info(f"Initial scan using RclonePoller for {path}")
                    self._scan_rclone_directory(dir_id, path)
                else:
                    # Scan for standard directories
                    self._scan_existing_files(dir_id, path)
            else:
                # If monitoring failed to start, don't update the state
                logger.error(f"Failed to start monitoring for directory {dir_id}")
                new_state = False  # Keep state unchanged since it failed
        else:
            # We want to deactivate monitoring
            logger.info(f"Attempting to stop monitoring for {dir_id}")
            success = self._stop_monitoring(dir_id)
            # Always update the state to inactive, even if stopping failed
            self._monitored_directories[dir_id]['active'] = False
            logger.info(f"Stopped monitoring for directory {dir_id}")
    
        # Save changes to disk
        self._save_monitored_directories()
        
        # Return the actual new state
        return new_state
    
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
        
        # Process each file change individually
        for file_path in changes:
            # Use the central file detection method for consistent handling
            self._on_file_detected(dir_id, file_path)
    
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
        
        # Check if already being monitored
        if dir_id in self._observers:
            logger.info(f"Directory {dir_id} is already being monitored")
            return True
        
        logger.info(f"Starting monitoring for directory {dir_id} at path {path}")
        
        try:
            # Check if this is an rclone mount
            is_rclone = False
            if os.path.ismount(path):
                try:
                    mount_info = os.popen(f"findmnt -n -o SOURCE {path}").read().lower()
                    is_rclone = "rclone" in mount_info
                    logger.info(f"Mount info for {path}: {mount_info}")
                except Exception as e:
                    logger.warning(f"Error checking if mount is rclone: {e}")
            
            if is_rclone:
                logger.info(f"Using RclonePoller for {path} (rclone mount detected)")
                
                # Create polling thread for ongoing monitoring
                def poll_rclone():
                    logger.info(f"Starting rclone polling thread for {dir_id}")
                    
                    # Immediately scan once at startup
                    try:
                        logger.info(f"Initial rclone scan for {path}")
                        self._scan_rclone_directory(dir_id, path)
                    except Exception as e:
                        logger.error(f"Error in initial rclone scan: {e}")
                    
                    # Then continue periodic polling
                    while dir_id in self._observers:
                        try:
                            logger.debug(f"Periodic polling rclone directory {path}")
                            self._scan_rclone_directory(dir_id, path)
                        except Exception as e:
                            logger.error(f"Error in rclone polling: {e}")
                        # Sleep for polling interval
                        time.sleep(300)  # 5 minutes
                    logger.info(f"Rclone polling thread exiting for {dir_id}")
            
                # Start a thread to poll the directory
                poll_thread = threading.Thread(target=poll_rclone, daemon=True, 
                                         name=f"rclone-poll-{dir_id}")
                poll_thread.start()
                self._observers[dir_id] = poll_thread
                logger.info(f"Started rclone polling thread for {dir_id}")
            else:
                # Standard file system monitoring
                logger.info(f"Using standard Observer for {path}")
                observer = Observer()
                event_handler = DirectoryChangeHandler(
                    callback=self._on_directory_change,
                    directory_id=dir_id
                )
                
                observer.schedule(event_handler, path, recursive=True)
                observer.daemon = True
                observer.start()
                self._observers[dir_id] = observer
                logger.info(f"Started standard observer for {dir_id}")
                
                # Also scan existing files immediately for standard directories
                logger.info(f"Scanning existing files in {path}")
                threading.Thread(
                    target=self._scan_existing_files,
                    args=(dir_id, path),
                    daemon=True,
                    name=f"initial-scan-{dir_id}"
                ).start()
        
            return True
        except Exception as e:
            logger.error(f"Error starting monitoring for {path}: {str(e)}")
            # If there was an exception, make sure we don't have a partial observer
            if dir_id in self._observers:
                try:
                    del self._observers[dir_id]
                except:
                    pass
            return False
    
    def _scan_rclone_directory(self, dir_id, path):
        """Scan an rclone directory for new files."""
        try:
            # Check for media files directly in the directory
            for root, _, files in os.walk(path):
                for file in files:
                    # Only process media files
                    if not file.lower().endswith(('.mkv', '.mp4', '.avi', '.m4v', '.mov')):
                        continue
                    
                    file_path = os.path.join(root, file)
                    
                    # Check if already in pending files
                    dir_info = self._monitored_directories[dir_id]
                    pending_files = dir_info.get('pending_files', [])
                    
                    if file_path not in pending_files:
                        # Log the new file
                        logger.info(f"New file detected by RclonePoller: {file_path}")
                        
                        # Handle as a change event
                        self._on_file_detected(dir_id, file_path)
        except Exception as e:
            logger.error(f"Error scanning rclone directory {path}: {e}")

    def _on_file_detected(self, dir_id, file_path):
        """Handle a newly detected file."""
        if dir_id not in self._monitored_directories:
            return
            
        dir_info = self._monitored_directories[dir_id]
        dir_name = dir_info.get('name', 'Unknown')
        
        # Get the file name for notifications
        file_name = os.path.basename(file_path)
        
        # Add to pending files (if not already there)
        pending_files = dir_info.get('pending_files', [])
        if file_path not in pending_files:
            # Only add to pending files and send notification for new files
            pending_files.append(file_path)
            dir_info['pending_files'] = pending_files
            logger.info(f"Added pending file: {file_name} to directory {dir_name}")
            self._save_monitored_directories()
            
            # Check if Discord notifications are enabled
            notifications_enabled = os.environ.get('ENABLE_DISCORD_NOTIFICATIONS', 'true').lower() == 'true'
            
            if notifications_enabled:
                # Try webhook URLs in this order: specific event URL, default URL, legacy URL
                webhook_url = (os.environ.get('DISCORD_WEBHOOK_URL_MONITORED_ITEM') or 
                              os.environ.get('DEFAULT_DISCORD_WEBHOOK_URL') or 
                              os.environ.get('DISCORD_WEBHOOK_URL'))
                
                # If we have a webhook URL, send notification
                if webhook_url:
                    try:
                        from discord_webhook import DiscordWebhook
                        
                        # Log which webhook URL we're using (truncated for security)
                        webhook_prefix = webhook_url[:30] + "..." if len(webhook_url) > 30 else webhook_url
                        logger.info(f"Sending notification to webhook: {webhook_prefix}")
                        
                        webhook = DiscordWebhook(
                            url=webhook_url,
                            content=f"📁 New content detected: **{file_name}** in {dir_name}"
                        )
                        response = webhook.execute()
                        
                        # Discord webhooks return 204 for older API or 200 for newer API versions
                        if response.status_code in [200, 204]:
                            logger.info(f"Webhook notification sent successfully for {file_name} (Status: {response.status_code})")
                        else:
                            logger.error(f"Webhook notification failed with status code: {response.status_code}")
                    except ImportError:
                        logger.warning("discord_webhook package not installed, skipping notification")
                    except Exception as e:
                        logger.error(f"Failed to send webhook notification: {str(e)}")
                else:
                    logger.warning("No Discord webhook URL configured, skipping notification")
    
    def _stop_monitoring(self, dir_id):
        """Stop monitoring a directory."""
        if dir_id in self._observers:
            try:
                observer = self._observers[dir_id]
                
                # Check if it's a watchdog Observer or a threading.Thread for rclone polling
                if isinstance(observer, Observer):
                    observer.stop()
                    observer.join(timeout=2.0)
                elif isinstance(observer, threading.Thread):
                    # For custom polling threads, we can't join directly
                    # Just remove from the dictionary, and the thread's while loop will exit
                    pass
                
                del self._observers[dir_id]
                
                # Update active status in directory info
                if dir_id in self._monitored_directories:
                    self._monitored_directories[dir_id]['active'] = False
                    self._save_monitored_directories()
                    
                logger.info(f"Stopped monitoring directory ID: {dir_id}")
                return True
            except Exception as e:
                logger.error(f"Error stopping directory monitoring: {e}")
                return False
    
        # Still update the active status even if no observer was found
        if dir_id in self._monitored_directories:
            self._monitored_directories[dir_id]['active'] = False
            self._save_monitored_directories()
    
        return True  # Return true if not monitoring (already stopped)
    
    def start_all(self):
        """Start monitoring all directories."""
        count = 0
        active_dirs = []
        
        # First, stop any existing monitors to ensure a clean state
        for dir_id in list(self._observers.keys()):
            self._stop_monitoring(dir_id)
        
        # Now start monitoring for all directories
        for dir_id, info in self._monitored_directories.items():
            # Mark as active
            self._monitored_directories[dir_id]['active'] = True
            
            # Start actual monitoring
            if self._start_monitoring(dir_id):
                count += 1
                active_dirs.append(dir_id)
                
                # IMPORTANT FIX: Perform initial scan for each directory
                path = info.get('path')
                logger.info(f"Performing initial scan of existing files in {path}")
                
                # For rclone mounts, use the rclone scanner
                is_rclone = False
                try:
                    if os.path.ismount(path):
                        mount_info = os.popen(f"findmnt -n -o SOURCE {path}").read().lower()
                        is_rclone = "rclone" in mount_info
                except Exception as e:
                    logger.warning(f"Error checking if mount is rclone: {e}")
                
                if is_rclone:
                    logger.info(f"Initial scan using RclonePoller for {path}")
                    self._scan_rclone_directory(dir_id, path)
                else:
                    # Scan for standard directories
                    self._scan_existing_files(dir_id, path)
            else:
                # If monitoring failed to start, mark as inactive
                self._monitored_directories[dir_id]['active'] = False
    
        # Save the updated active states
        self._save_monitored_directories()
        
        logger.info(f"Started monitoring {count} active directories")
        return count
    
    def stop_all(self):
        """Stop monitoring all directories."""
        for dir_id in list(self._observers.keys()):
            self._stop_monitoring(dir_id)
            # Update the active state in the directory info
            if dir_id in self._monitored_directories:
                self._monitored_directories[dir_id]['active'] = False
        
        # Save the updated active states
        self._save_monitored_directories()
        logger.info("Stopped all directory monitoring")

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

    def _scan_existing_files(self, dir_id, path):
        """Scan directory for existing media files upon monitor activation."""
        try:
            logger.info(f"Scanning existing files in {path}")
            file_count = 0
            
            # Use os.walk to find all files in the directory
            for root, _, files in os.walk(path, followlinks=True):
                for file in files:
                    # Only process media files
                    if file.lower().endswith(('.mkv', '.mp4', '.avi', '.m4v', '.mov')):
                        file_path = os.path.join(root, file)
                        
                        # Get directory info and check if file is already pending
                        dir_info = self._monitored_directories[dir_id]
                        pending_files = dir_info.get('pending_files', [])
                        
                        if file_path not in pending_files:
                            # Log the existing file
                            logger.info(f"Existing file found during initial scan: {file_path}")
                            
                            # Handle as a detected file
                            self._on_file_detected(dir_id, file_path)
                            file_count += 1
                            
                            # Limit number of files to avoid huge batches
                            if file_count >= 50:
                                logger.info(f"Reached scan limit of 50 files, will continue on next scan")
                                break
            
                # Break out of outer loop too if we hit the limit
                if file_count >= 50:
                    break
                    
            logger.info(f"Initial scan complete, found {file_count} files in {path}")
    
        except Exception as e:
            logger.error(f"Error scanning existing files in {path}: {e}")
    
    def is_monitoring_active(self):
        """Check if any directory is currently being monitored."""
        return bool(self._observers)

    def get_monitoring_status(self):
        """Get the status of monitoring."""
        is_active = self.is_monitoring_active()
        active_dirs = []
        
        # Collect information about actively monitored directories
        for dir_id, observer in self._observers.items():
            if dir_id in self._monitored_directories:
                dir_info = self._monitored_directories[dir_id]
                active_dirs.append({
                    'id': dir_id,
                    'name': dir_info.get('name', 'Unknown'),
                    'path': dir_info.get('path', 'Unknown')
                })
        
        return {
            'active': is_active,
            'directory_count': len(self._monitored_directories),
            'active_count': len(active_dirs),
            'active_directories': active_dirs
        }
# Global monitor manager instance for reuse
_monitor_manager = None

def get_monitor_manager():
    """Get a global instance of the MonitorManager."""
    global _monitor_manager
    if _monitor_manager is None:
        _monitor_manager = MonitorManager()
    return _monitor_manager