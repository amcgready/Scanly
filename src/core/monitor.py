#!/usr/bin/env python3
"""
Monitor module for Scanly to detect changes in directories.
"""
import os
import json
import time
import logging
import threading
import uuid
import traceback
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import PatternMatchingEventHandler
from watchdog.observers.polling import PollingObserver

# Configure module logger
logger = logging.getLogger(__name__)

# Media file extensions to monitor
MEDIA_EXTENSIONS = ['.mkv', '.mp4', '.avi', '.mov', '.wmv', '.m4v', '.flv', '.webm']

class RcloneMount:
    """Properties for an rclone mounted directory."""
    def __init__(self, path):
        self.path = path
        self.is_rclone = self._check_if_rclone()
        
    def _check_if_rclone(self):
        """Check if the path is an rclone mount."""
        # Check common indicators of an rclone mount
        if self.path.startswith('/mnt/pd_zurg'):
            return True
            
        # We could check mount points but that requires elevated permissions
        # try:
        #     output = subprocess.check_output(['mount']).decode('utf-8')
        #     return f"{self.path} " in output and ("fuse" in output or "rclone" in output)
        # except:
        #     return False
            
        return False


class MediaFileHandler(PatternMatchingEventHandler):
    """Event handler for media file changes."""
    def __init__(self, callback, directory_id):
        """Initialize directory change handler."""
        # File patterns to match
        patterns = ["*.mkv", "*.mp4", "*.avi", "*.mov", "*.wmv", "*.m4v", "*.flv", "*.webm"]
        
        super().__init__(patterns=patterns, ignore_directories=True, case_sensitive=False)
        self.callback = callback
        self.directory_id = directory_id
        self.pending_events = []
        self.notification_timer = None
        
    def on_created(self, event):
        """Handle file creation event."""
        if not event.is_directory:
            logger.debug(f"File created event: {event.src_path}")
            self.pending_events.append(event.src_path)
            self._schedule_notification()
    
    def _schedule_notification(self):
        """Schedule notification with debouncing."""
        if self.notification_timer:
            self.notification_timer.cancel()
        
        self.notification_timer = threading.Timer(2.0, self._send_notifications)
        self.notification_timer.daemon = True
        self.notification_timer.start()
    
    def _send_notifications(self):
        """Send notifications for pending events."""
        for path in list(self.pending_events):
            if os.path.exists(path):
                try:
                    self.callback(self.directory_id, path)
                except Exception as e:
                    logger.error(f"Error processing {path}: {e}")
        
        self.pending_events = []


class RclonePoller:
    """Custom poller for rclone mounts that detects new files by scanning."""
    def __init__(self, directory_id, path, callback):
        """Initialize poller.
        
        Args:
            directory_id (str): Directory ID
            path (str): Path to monitor
            callback (function): Callback function for new files
        """
        self.directory_id = directory_id
        self.path = path
        self.callback = callback
        self.known_files = set()
        self.running = False
        self.thread = None
        self.poll_interval = 30  # seconds
        
    def start(self):
        """Start polling for changes."""
        if self.running:
            return
            
        self.running = True
        
        # Initial scan to populate known files
        self._scan_for_files()
        logger.info(f"RclonePoller started for {self.path} with {len(self.known_files)} known files")
        
        # Start polling thread
        self.thread = threading.Thread(target=self._polling_loop, daemon=True)
        self.thread.start()
        return True
        
    def stop(self):
        """Stop polling for changes."""
        self.running = False
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=2)
        logger.info(f"RclonePoller stopped for {self.path}")
        return True
        
    def _polling_loop(self):
        """Main polling loop."""
        while self.running:
            try:
                self._scan_for_files()
            except Exception as e:
                logger.error(f"Error scanning {self.path}: {e}")
            
            # Sleep for poll interval
            for _ in range(self.poll_interval):
                if not self.running:
                    break
                time.sleep(1)
    
    def _scan_for_files(self):
        """Scan for new files."""
        try:
            current_files = set()
            
            for root, _, files in os.walk(self.path):
                for file in files:
                    if any(file.lower().endswith(ext) for ext in MEDIA_EXTENSIONS):
                        full_path = os.path.join(root, file)
                        current_files.add(full_path)
                        
                        # If this is a new file, notify callback
                        if full_path not in self.known_files:
                            logger.info(f"New file detected by RclonePoller: {full_path}")
                            try:
                                self.callback(self.directory_id, full_path)
                            except Exception as e:
                                logger.error(f"Error processing new file {full_path}: {e}")
            
            # Update known files
            self.known_files = current_files
            
        except Exception as e:
            logger.error(f"Error scanning directory {self.path}: {e}")
            logger.debug(traceback.format_exc())


class DirectoryWatcher:
    """Watches a single directory for changes."""
    def __init__(self, directory_id, path, callback):
        """Initialize directory watcher."""
        self.directory_id = directory_id
        self.path = path
        self.callback = callback
        self.watcher = None
        
        # Check if this is an rclone mount
        self.rclone = RcloneMount(path)
        
    def start(self):
        """Start watching the directory."""
        try:
            if self.rclone.is_rclone:
                # Use custom rclone poller for rclone mounts
                logger.info(f"Using RclonePoller for {self.path} (rclone mount detected)")
                self.watcher = RclonePoller(self.directory_id, self.path, self.callback)
            else:
                # Use regular watchdog observer for local directories
                logger.info(f"Using regular Observer for {self.path}")
                handler = MediaFileHandler(self.callback, self.directory_id)
                observer = PollingObserver()  # Use PollingObserver which is more reliable
                observer.schedule(handler, self.path, recursive=True)
                observer.start()
                self.watcher = observer
            
            # Start the appropriate watcher
            if isinstance(self.watcher, RclonePoller):
                return self.watcher.start()
            return True
            
        except Exception as e:
            logger.error(f"Error starting watcher for {self.path}: {e}")
            logger.debug(traceback.format_exc())
            return False
    
    def stop(self):
        """Stop watching the directory."""
        if not self.watcher:
            return True
            
        try:
            if isinstance(self.watcher, RclonePoller):
                return self.watcher.stop()
            else:
                self.watcher.stop()
                self.watcher.join(timeout=2)
            return True
        except Exception as e:
            logger.error(f"Error stopping watcher for {self.path}: {e}")
            logger.debug(traceback.format_exc())
            return False


class MonitorManager:
    """Manages monitored directories and their state."""
    def __init__(self, config_path=None):
        """Initialize monitor manager."""
        self.watchers = {}  # maps directory_id to its DirectoryWatcher
        
        # Set up config path
        if config_path is None:
            self.config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'config')
        else:
            self.config_path = config_path
            
        self.monitored_file = os.path.join(self.config_path, 'monitored_directories.json')
        
        # Create config directory if it doesn't exist
        self._ensure_config_dir()
        
        # Load monitored directories
        self.monitored_directories = self._load_monitored_directories()
        
    def _ensure_config_dir(self):
        """Create config directory if it doesn't exist."""
        if not os.path.exists(self.config_path):
            os.makedirs(self.config_path)
            logger.info(f"Created config directory: {self.config_path}")
        
    def _load_monitored_directories(self):
        """Load monitored directories from file."""
        if not os.path.exists(self.monitored_file):
            logger.info("No monitored directories file found, creating a new one")
            return {}
            
        try:
            with open(self.monitored_file, 'r') as f:
                dirs = json.load(f)
                logger.info(f"Loaded {len(dirs)} monitored directories")
                return dirs
        except (json.JSONDecodeError, FileNotFoundError) as e:
            logger.error(f"Error loading monitored directories: {e}")
            return {}
            
    def _save_monitored_directories(self):
        """Save monitored directories to file."""
        try:
            with open(self.monitored_file, 'w') as f:
                json.dump(self.monitored_directories, f, indent=2)
                logger.info(f"Saved {len(self.monitored_directories)} monitored directories")
        except Exception as e:
            logger.error(f"Error saving monitored directories: {e}")
    
    def get_monitored_directories(self):
        """Get all monitored directories."""
        return self.monitored_directories
    
    def add_directory(self, path, name=None):
        """Add a directory to be monitored."""
        # Validate path
        if not os.path.isdir(path):
            logger.error(f"Path is not a directory: {path}")
            return None
            
        # Generate unique ID
        dir_id = str(uuid.uuid4())[:8]
        
        # Use folder name if no name provided
        if not name:
            name = os.path.basename(path)
            
        # Store directory info
        self.monitored_directories[dir_id] = {
            'path': path,
            'name': name,
            'active': True,
            'pending_files': []
        }
        
        # Save
        self._save_monitored_directories()
        
        # Start monitoring
        self.start_monitoring(dir_id)
        
        return dir_id
    
    def remove_directory(self, directory_id):
        """Remove a monitored directory."""
        if directory_id not in self.monitored_directories:
            logger.error(f"Directory ID not found: {directory_id}")
            return False
            
        # Stop monitoring
        self.stop_monitoring(directory_id)
        
        # Remove from monitored directories
        del self.monitored_directories[directory_id]
        
        # Save
        self._save_monitored_directories()
        
        return True
    
    def toggle_directory_active(self, directory_id):
        """Toggle active status of monitored directory."""
        if directory_id not in self.monitored_directories:
            logger.error(f"Directory ID not found: {directory_id}")
            return None
            
        current_state = self.monitored_directories[directory_id]['active']
        new_state = not current_state
        
        # Update state
        self.monitored_directories[directory_id]['active'] = new_state
        
        # Start or stop monitoring based on new state
        if new_state:
            self.start_monitoring(directory_id)
        else:
            self.stop_monitoring(directory_id)
        
        # Save
        self._save_monitored_directories()
        
        return new_state
    
    def start_monitoring(self, directory_id):
        """Start monitoring a directory."""
        if directory_id not in self.monitored_directories:
            logger.error(f"Directory ID not found: {directory_id}")
            return False
            
        # Skip if already monitoring
        if directory_id in self.watchers:
            return True
            
        directory_info = self.monitored_directories[directory_id]
        
        # Skip if not active
        if not directory_info['active']:
            return False
            
        path = directory_info['path']
        
        # Check if directory exists
        if not os.path.isdir(path):
            logger.error(f"Directory does not exist: {path}")
            return False
            
        # Create and start watcher
        watcher = DirectoryWatcher(directory_id, path, self._on_directory_change)
        if watcher.start():
            self.watchers[directory_id] = watcher
            logger.info(f"Started monitoring directory: {path}")
            return True
        else:
            logger.error(f"Failed to start monitoring directory: {path}")
            return False
    
    def stop_monitoring(self, directory_id):
        """Stop monitoring a directory."""
        if directory_id not in self.watchers:
            return True
            
        # Stop and remove watcher
        watcher = self.watchers[directory_id]
        if watcher.stop():
            del self.watchers[directory_id]
            logger.info(f"Stopped monitoring directory: {self.monitored_directories[directory_id]['path']}")
            return True
        else:
            logger.error(f"Failed to stop monitoring directory: {self.monitored_directories[directory_id]['path']}")
            return False
    
    def start_all(self):
        """Start monitoring all active directories."""
        started = 0
        for dir_id, info in self.monitored_directories.items():
            if info['active']:
                if self.start_monitoring(dir_id):
                    started += 1
        
        logger.info(f"Started monitoring {started} active directories")
        return started
    
    def stop_all(self):
        """Stop monitoring all directories."""
        stopped = 0
        for dir_id in list(self.watchers.keys()):
            if self.stop_monitoring(dir_id):
                stopped += 1
        
        logger.info(f"Stopped monitoring {stopped} directories")
        return stopped
    
    def _on_directory_change(self, directory_id, file_path):
        """Callback for directory change handler."""
        if directory_id not in self.monitored_directories:
            logger.warning(f"Change detected for unknown directory ID: {directory_id}")
            return
            
        # Get directory info
        directory_info = self.monitored_directories[directory_id]
        
        # Skip if file doesn't exist
        if not os.path.exists(file_path):
            logger.debug(f"File no longer exists: {file_path}")
            return
            
        # Skip if already in pending files
        for existing in directory_info.get('pending_files', []):
            if existing['path'] == file_path:
                logger.debug(f"File already in pending list: {file_path}")
                return
                
        # Add to pending files
        file_name = os.path.basename(file_path)
        logger.info(f"Adding file to pending list: {file_name} in directory {directory_info['name']}")
        
        pending_file = {
            'path': file_path,
            'name': file_name,
            'added_at': time.time()
        }
        
        if 'pending_files' not in directory_info:
            directory_info['pending_files'] = []
            
        directory_info['pending_files'].append(pending_file)
        
        # Save changes
        self._save_monitored_directories()
        
        # Send webhook notification if configured
        self._send_webhook_notification(directory_info['name'], file_name)
    
    def _send_webhook_notification(self, dir_name, file_name):
        """Send webhook notification for new file."""
        webhook_url = os.environ.get('DISCORD_WEBHOOK_URL')
        if not webhook_url:
            return
            
        try:
            from discord_webhook import DiscordWebhook
            
            message = f"📁 New media file detected in **{dir_name}**:\n`{file_name}`"
            webhook = DiscordWebhook(url=webhook_url, content=message)
            response = webhook.execute()
            
            if response and response.status_code == 200:
                logger.info(f"Webhook notification sent for {file_name}")
            else:
                logger.warning(f"Failed to send webhook notification: {response.status_code if response else 'No response'}")
        except ImportError:
            logger.warning("discord_webhook package not installed, notification not sent")
        except Exception as e:
            logger.error(f"Error sending webhook notification: {e}")
    
    def get_pending_files(self, directory_id):
        """Get pending files for a directory."""
        if directory_id not in self.monitored_directories:
            logger.error(f"Directory ID not found: {directory_id}")
            return []
            
        return self.monitored_directories[directory_id].get('pending_files', [])
    
    def get_all_pending_files(self):
        """Get all pending files across all directories."""
        all_files = []
        
        for dir_id, info in self.monitored_directories.items():
            dir_name = info.get('name', 'Unknown')
            
            for file_info in info.get('pending_files', []):
                # Copy file info and add directory details
                file_with_dir = file_info.copy()
                file_with_dir['dir_id'] = dir_id
                file_with_dir['dir_name'] = dir_name
                file_with_dir['dir_path'] = info.get('path', '')
                
                all_files.append(file_with_dir)
                
        # Sort by added time, newest first
        all_files.sort(key=lambda x: x.get('added_at', 0), reverse=True)
        
        return all_files
    
    def remove_pending_file(self, directory_id, file_path):
        """Remove a file from the pending list."""
        if directory_id not in self.monitored_directories:
            logger.error(f"Directory ID not found: {directory_id}")
            return False
            
        directory_info = self.monitored_directories[directory_id]
        
        if 'pending_files' not in directory_info:
            return False
            
        # Find file in pending list
        for i, file_info in enumerate(directory_info['pending_files']):
            if file_info['path'] == file_path:
                # Remove file
                directory_info['pending_files'].pop(i)
                
                # Save changes
                self._save_monitored_directories()
                
                logger.info(f"Removed file from pending list: {file_path}")
                return True
                
        return False
    
    def run_pending_scans(self):
        """Process all pending files."""
        processed = 0
        pending_files = self.get_all_pending_files()
        
        logger.info(f"Running pending scans for {len(pending_files)} files")
        
        for file_info in pending_files:
            dir_id = file_info['dir_id']
            file_path = file_info['path']
            
            # Skip if file no longer exists
            if not os.path.exists(file_path):
                self.remove_pending_file(dir_id, file_path)
                continue
                
            try:
                logger.info(f"Processing pending file: {file_path}")
                
                # Process file
                from src.main import DirectoryProcessor
                processor = DirectoryProcessor(file_path, auto_mode=True)
                result = processor._process_media_files()
                
                # Remove from pending list if processed successfully
                if result is not None and result >= 0:
                    self.remove_pending_file(dir_id, file_path)
                    processed += 1
                    
            except Exception as e:
                logger.error(f"Error processing {file_path}: {e}")
                
        return processed


# Global monitor manager instance for reuse
_monitor_manager = None

def get_monitor_manager():
    """Get or create a MonitorManager instance."""
    global _monitor_manager
    
    if _monitor_manager is None:
        _monitor_manager = MonitorManager()
    
    return _monitor_manager


def initialize_monitoring():
    """Initialize monitoring on application startup."""
    try:
        manager = get_monitor_manager()
        manager.start_all()
    except Exception as e:
        logger.error(f"Error initializing monitoring: {e}")