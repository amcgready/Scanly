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
    def __init__(self, callback, directory_id, monitored_path):
        self.callback = callback
        self.directory_id = directory_id
        self.monitored_path = monitored_path  # Store the monitored path
        self.changes = set()
        self.last_notification_time = 0
        logger.info(f"DirectoryChangeHandler initialized for path: {monitored_path}")
        
    def on_created(self, event):
        """Handle file/directory creation events."""
        # Debug log to see all events
        logger.debug(f"Event detected: {event.src_path}, is_directory={event.is_directory}")
        
        # Only handle directory events
        if event.is_directory:
            path = event.src_path
            parent_dir = os.path.dirname(path)
            
            # More debug info to understand what's happening
            logger.debug(f"Directory event: {path}")
            logger.debug(f"Parent dir: {parent_dir}")
            logger.debug(f"Monitored path: {self.monitored_path}")
            
            # Check if this is an immediate subdirectory of the monitored path
            # Use normpath to handle paths with or without trailing slashes
            norm_parent = os.path.normpath(parent_dir)
            norm_monitored = os.path.normpath(self.monitored_path)
            
            if norm_parent == norm_monitored and self._is_valid_directory(path):
                logger.info(f"New top-level directory detected: {path}")
                self.changes.add(path)
                self._schedule_notification()
                return
            
            logger.debug(f"Directory {path} is not an immediate child of {self.monitored_path} - ignoring")
        
    def _is_valid_directory(self, path):
        """Check if this is a valid directory we should notify about."""
        # Skip hidden directories
        if os.path.basename(path).startswith('.'):
            logger.debug(f"Skipping hidden directory: {path}")
            return False
            
        # Skip common system/development directories
        if any(excluded in path for excluded in ['.git', '__pycache__', 'node_modules', '.venv']):
            logger.debug(f"Skipping system directory: {path}")
            return False
            
        return True
    
    def _schedule_notification(self):
        """Throttle notifications to avoid spamming."""
        current_time = time.time()
        if current_time - self.last_notification_time > 5.0:  # 5 second cooldown
            self.last_notification_time = current_time
            changes = list(self.changes)
            self.changes.clear()
            if changes:  # Only notify if there are actual changes
                logger.info(f"Scheduling notification for {len(changes)} changes")
                self.callback(changes, self.directory_id)
                # Check if callback worked
                logger.debug("Notification callback executed")
            else:
                logger.debug("No changes to notify about")


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
                            logger.info(f"Scanning for existing subdirectories in {path}")
                            
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
                                self._scan_existing_subdirectories(dir_id, path)
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
                
                # IMPORTANT FIX: Immediately scan the directory for existing subdirectories
                path = self._monitored_directories[dir_id].get('path')
                logger.info(f"Performing initial scan of existing subdirectories in {path}")
                
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
                    # Scan for immediate subdirectories
                    self._scan_existing_subdirectories(dir_id, path)
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
            logger.debug("No changes to process in _on_directory_change")
            return
        
        if dir_id not in self._monitored_directories:
            logger.error(f"Directory ID not found: {dir_id}")
            return
            
        dir_info = self._monitored_directories[dir_id]
        dir_name = dir_info.get('name', 'Unknown')
        
        logger.info(f"Changes detected in {dir_name}: {len(changes)} new subdirectories")
        
        # Process each directory change
        for dir_path in changes:
            # Only add items that are actual directories
            if os.path.isdir(dir_path):
                logger.debug(f"Processing directory change: {dir_path}")
                # Use the central detection method for consistent handling
                self._on_directory_detected(dir_id, dir_path)
            else:
                logger.debug(f"Skipping non-directory: {dir_path}")
    
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
                    directory_id=dir_id,
                    monitored_path=path  # Pass the monitored path to the handler
                )
                
                observer.schedule(event_handler, path, recursive=True)
                observer.daemon = True
                observer.start()
                self._observers[dir_id] = observer
                logger.info(f"Started standard observer for {dir_id}")
                
                # IMPORTANT: Force an immediate scan for existing directories 
                # This ensures we find preexisting directories even if no new event fires
                self._scan_existing_subdirectories(dir_id, path)
        
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
        """Scan an rclone directory for new top-level subdirectories only."""
        try:
            logger.info(f"Scanning rclone directory: {path}")
            detected_count = 0
            
            # Only scan for immediate subdirectories directly under the monitored path
            for item in os.listdir(path):
                item_path = os.path.join(path, item)
                # Only process items that are directories
                if os.path.isdir(item_path) and not item.startswith('.'):
                    if not any(excluded in item_path for excluded in ['.git', '__pycache__', 'node_modules']):
                        logger.info(f"Found subdirectory in rclone mount: {item_path}")
                        self._on_directory_detected(dir_id, item_path)
                        detected_count += 1
            
            logger.info(f"Rclone scan complete. Found {detected_count} subdirectories.")
        except Exception as e:
            logger.error(f"Error scanning rclone directory {path}: {e}")

    def _on_directory_detected(self, dir_id, dir_path):
        """Handle a newly detected directory under a monitored path."""
        if dir_id not in self._monitored_directories:
            logger.warning(f"Cannot process directory for unknown dir_id: {dir_id}")
            return
            
        dir_info = self._monitored_directories[dir_id]
        dir_name = dir_info.get('name', 'Unknown')
        monitored_path = dir_info.get('path', '')
        
        # Only process directories that are direct subdirectories of the monitored path
        # Use normpath to handle paths with or without trailing slashes
        norm_parent = os.path.normpath(os.path.dirname(dir_path))
        norm_monitored = os.path.normpath(monitored_path)
        
        if norm_parent != norm_monitored:
            logger.debug(f"Ignoring non-immediate subdirectory: {dir_path}")
            return
        
        # Get the folder name for notifications
        folder_name = os.path.basename(dir_path)
        
        # Debug info to track the process
        logger.debug(f"Processing detected directory: {dir_path}")
        logger.debug(f"Parent directory: {os.path.dirname(dir_path)}")
        logger.debug(f"Monitored path: {monitored_path}")
        
        # Add to pending directories (if not already there)
        pending_files = dir_info.get('pending_files', [])
        if dir_path not in pending_files:
            # Only add to pending files and send notification for new directories
            pending_files.append(dir_path)
            dir_info['pending_files'] = pending_files
            logger.info(f"Added pending directory: {folder_name} to monitor {dir_name}")
            self._save_monitored_directories()
            
            # Always try to send notification for directories - this is key
            self._send_directory_notification(dir_name, folder_name)
    
    def _send_directory_notification(self, dir_name, folder_name):
        """Send a notification for a newly detected directory."""
        logger.info(f"Sending notification for folder: {folder_name} in {dir_name}")
        
        # Check if Discord notifications are enabled
        notifications_enabled = os.environ.get('ENABLE_DISCORD_NOTIFICATIONS', 'true').lower() == 'true'
        
        if not notifications_enabled:
            logger.info("Notifications disabled in environment settings")
            return False
            
        # Try webhook URLs in this order: specific event URL, default URL, legacy URL
        webhook_url = (os.environ.get('DISCORD_WEBHOOK_URL_MONITORED_ITEM') or 
                       os.environ.get('DEFAULT_DISCORD_WEBHOOK_URL') or 
                       os.environ.get('DISCORD_WEBHOOK_URL'))
        
        if not webhook_url:
            logger.warning("No Discord webhook URL configured, skipping notification")
            return False
            
        # If we have a webhook URL, send notification
        try:
            from discord_webhook import DiscordWebhook
            
            # Log which webhook URL we're using (truncated for security)
            webhook_prefix = webhook_url[:30] + "..." if len(webhook_url) > 30 else webhook_url
            logger.info(f"Sending notification to webhook: {webhook_prefix}")
            
            # Create a notification message for the new folder
            message = f"📁 New folder detected: **{folder_name}** in {dir_name}"
            
            # Create and send webhook
            webhook = DiscordWebhook(
                url=webhook_url,
                content=message
            )
            response = webhook.execute()
            
            # Check response status
            if response and hasattr(response, 'status_code'):
                # Discord webhooks return 204 for older API or 200 for newer API versions
                if response.status_code in [200, 204]:
                    logger.info(f"Webhook notification sent successfully for {folder_name} (Status: {response.status_code})")
                    return True
                else:
                    logger.error(f"Webhook notification failed with status code: {response.status_code}")
                    # Try to log response content for debugging
                    try:
                        logger.error(f"Response content: {response.content}")
                    except:
                        pass
            else:
                logger.error("Webhook response object is invalid")
                
        except ImportError:
            logger.warning("discord_webhook package not installed, skipping notification")
        except Exception as e:
            logger.error(f"Failed to send webhook notification: {str(e)}")
            
        return False
    
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
                    'name': os.path.basename(file_path),
                    'is_directory': os.path.isdir(file_path)
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

    def _scan_existing_subdirectories(self, dir_id, path):
        """Scan directory for existing immediate subdirectories only."""
        try:
            logger.info(f"Scanning for immediate subdirectories in {path}")
            detected_count = 0
            
            # Only scan for immediate subdirectories directly under the monitored path
            try:
                for item in os.listdir(path):
                    item_path = os.path.join(path, item)
                    # Only process items that are directories
                    if os.path.isdir(item_path):
                        # Filter using _is_valid_directory logic
                        if not item.startswith('.') and not any(
                            excluded in item_path for excluded in ['.git', '__pycache__', 'node_modules', '.venv']):
                            logger.info(f"Found existing subdirectory: {item_path}")
                            self._on_directory_detected(dir_id, item_path)
                            detected_count += 1
            except Exception as e:
                logger.error(f"Error scanning immediate subdirectories: {e}")
                
            logger.info(f"Initial subdirectory scan complete for {path}. Found {detected_count} subdirectories.")
    
        except Exception as e:
            logger.error(f"Error scanning existing subdirectories in {path}: {e}")
    
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
      
    # DIAGNOSTICS: Add a method to manually send test notifications for debugging
    def send_test_notification(self, dir_id):
        """Send a test notification for a monitored directory."""
        if dir_id not in self._monitored_directories:
            logger.error(f"Directory ID not found: {dir_id}")
            return False
            
        dir_info = self._monitored_directories[dir_id]
        dir_name = dir_info.get('name', 'Unknown') 
        
        logger.info(f"Sending test notification for {dir_name}")
        return self._send_directory_notification(dir_name, "TEST_FOLDER")
    
    def get_pending_files_and_folders(self):
        """Get pending files and folders separately."""
        files = []
        folders = []
        
        for dir_id, info in self._monitored_directories.items():
            dir_name = info.get('name', 'Unknown')
            dir_path = info.get('path', '')
            
            for item_path in info.get('pending_files', []):
                # Skip if path no longer exists
                if not os.path.exists(item_path):
                    continue
                    
                is_directory = os.path.isdir(item_path)
                item_info = {
                    'dir_id': dir_id,
                    'dir_name': dir_name,
                    'dir_path': dir_path,
                    'path': item_path,
                    'name': os.path.basename(item_path),
                    'is_directory': is_directory
                }
                
                if is_directory:
                    folders.append(item_info)
                else:
                    files.append(item_info)
                    
        return files, folders

    def get_pending_files_only(self):
        """Get only pending media files (not folders)."""
        files, _ = self.get_pending_files_and_folders()
        return files
    
    def get_pending_folders_only(self):
        """Get only pending folders (not media files)."""
        _, folders = self.get_pending_files_and_folders()
        return folders

    def process_pending_files(self):
        """Process only pending files using DirectoryProcessor."""
        pending_files = self.get_pending_files_only()
        
        if not pending_files:
            logger.info("No pending files to process")
            return 0
        
        logger.info(f"Processing {len(pending_files)} pending files")
        processed_count = 0
        
        try:
            from src.main import DirectoryProcessor
            
            for file_info in pending_files:
                dir_id = file_info['dir_id']
                file_path = file_info['path']
                
                if not os.path.exists(file_path):
                    logger.warning(f"Skipping non-existent path: {file_path}")
                    self.remove_pending_file(dir_id, file_path)
                    continue
                
                logger.info(f"Processing pending file: {file_path}")
                
                processor = DirectoryProcessor(file_path)
                result = processor._process_media_files()
                
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

    def process_pending_folders(self):
        """Process pending folders by running an individual scan on each."""
        pending_folders = self.get_pending_folders_only()
        
        if not pending_folders:
            logger.info("No pending folders to process")
            return 0
        
        logger.info(f"Processing {len(pending_folders)} pending folders")
        processed_count = 0
        
        try:
            from src.main import DirectoryProcessor
            
            for folder_info in pending_folders:
                dir_id = folder_info['dir_id']
                folder_path = folder_info['path']
                
                if not os.path.exists(folder_path) or not os.path.isdir(folder_path):
                    logger.warning(f"Skipping non-existent folder: {folder_path}")
                    self.remove_pending_file(dir_id, folder_path)
                    continue
                
                logger.info(f"Processing pending folder: {folder_path}")
                
                # Create a processor specifically for this folder
                processor = DirectoryProcessor(folder_path)
                result = processor._process_media_files()
                
                if result is not None:
                    self.remove_pending_file(dir_id, folder_path)
                    processed_count += 1
                else:
                    logger.warning(f"Failed to process folder {folder_path}")

        except ImportError:
            logger.error("Could not import DirectoryProcessor. Check your installation.")
        except Exception as e:
            logger.exception(f"Error processing pending folders: {e}")
        
        return processed_count
        

# Global monitor manager instance for reuse
_monitor_manager = None

def get_monitor_manager():
    """Get a global instance of the MonitorManager."""
    global _monitor_manager
    if _monitor_manager is None:
        _monitor_manager = MonitorManager()
    return _monitor_manager