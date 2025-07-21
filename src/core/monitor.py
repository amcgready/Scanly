#!/usr/bin/env python3
"""
Monitor module for Scanly to detect changes in directories.
"""
import os
import sys
import json
import threading
import time
import logging
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from src.main import load_scan_history_set, is_any_media_file_in_scan_history

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
        logger.debug(f"Event detected: {event.src_path}, is_directory={event.is_directory}")
        if event.is_directory:
            if self._is_valid_directory(event.src_path):
                self.callback(self.directory_id, event.src_path)
        
    def _is_valid_directory(self, path):
        """Check if this is a valid directory we should notify about."""
        # Skip hidden directories
        name = os.path.basename(path)
        if name.startswith('.'):
            return False
        # Add more rules as needed
        return True

    def _schedule_notification(self):
        pass  # Placeholder for future notification scheduling logic


class MonitorManager:
    """Manages monitored directories and their state."""
    def __init__(self, config_path=None):
        self.config_path = config_path or os.path.join(
            os.path.dirname(os.path.dirname(__file__)), 'config', 'monitored_directories.json'
        )
        self._monitored_directories = {}
        self._observers = {}
        self._pending_files = {}
        self._initial_scan_thread = None
        self._initial_scan_running = False
        self.scan_history_set = load_scan_history_set()
        self._ensure_config_dir()
        self._load_monitored_directories()

    def _ensure_config_dir(self):
        config_dir = os.path.dirname(self.config_path)
        if not os.path.exists(config_dir):
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
                        logger.info(f"Activating monitoring for {dir_id} based on saved state")
                        if self._start_monitoring(dir_id):
                            active_count += 1
                        else:
                            info['active'] = False
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
        with open(self.config_path, 'w') as f:
            json.dump(self._monitored_directories, f, indent=2)

    def get_monitored_directories(self):
        return self._monitored_directories

    def add_directory(self, path, name=None):
        dir_id = str(abs(hash(path)))
        if dir_id in self._monitored_directories:
            logger.warning(f"Directory already monitored: {path}")
            return False
        self._monitored_directories[dir_id] = {
            'path': path,
            'name': name or os.path.basename(path),
            'active': False
        }
        self._save_monitored_directories()
        logger.info(f"Added directory to monitor: {path}")
        return dir_id

    def remove_directory(self, dir_id):
        if dir_id in self._monitored_directories:
            self._stop_monitoring(dir_id)
            del self._monitored_directories[dir_id]
            self._save_monitored_directories()
            logger.info(f"Removed monitored directory: {dir_id}")
            return True
        logger.warning(f"Tried to remove non-existent directory: {dir_id}")
        return False

    def toggle_directory_active(self, dir_id):
        """Toggle the active state of a monitored """
        if dir_id not in self._monitored_directories:
            logger.error(f"Directory ID not found: {dir_id}")
            return False

        current_state = self._monitored_directories[dir_id].get('active', False)
        new_state = not current_state

        logger.info(f"Toggling directory {dir_id} from {current_state} to {new_state}")

        if new_state:
            logger.info(f"Attempting to start monitoring for {dir_id}")
            success = self._start_monitoring(dir_id)
            if success:
                self._monitored_directories[dir_id]['active'] = True
                logger.info(f"Successfully started monitoring for directory {dir_id}")
                # Initial scan is now handled only in background thread
            else:
                logger.error(f"Failed to start monitoring for directory {dir_id}")
                new_state = False
        else:
            logger.info(f"Attempting to stop monitoring for {dir_id}")
            success = self._stop_monitoring(dir_id)
            self._monitored_directories[dir_id]['active'] = False
            logger.info(f"Stopped monitoring for directory {dir_id}")

        self._save_monitored_directories()
        return new_state

    def _start_monitoring(self, dir_id):
        """Start monitoring a directory."""
        if dir_id not in self._monitored_directories:
            logger.error(f"Directory ID not found: {dir_id}")
            return False
        dir_info = self._monitored_directories[dir_id]
        path = dir_info.get('path')
        if not path or not os.path.isdir(path):
            logger.error(f"Invalid directory path: {path}")
            return False
        if dir_id in self._observers:
            logger.info(f"Directory {dir_id} is already being monitored")
            return True
        logger.info(f"Starting monitoring for directory {dir_id} at path {path}")

        try:
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
                def poll_rclone():
                    logger.info(f"Starting rclone polling thread for {dir_id}")
                    while dir_id in self._observers:
                        try:
                            logger.debug(f"Periodic polling rclone directory {path}")
                            self._scan_rclone_directory(dir_id, path)
                        except Exception as e:
                            logger.error(f"Error in rclone polling: {e}")
                        time.sleep(300)
                    logger.info(f"Rclone polling thread exiting for {dir_id}")

                poll_thread = threading.Thread(target=poll_rclone, daemon=True, 
                                         name=f"rclone-poll-{dir_id}")
                poll_thread.start()
                self._observers[dir_id] = poll_thread
                logger.info(f"Started rclone polling thread for {dir_id}")
            else:
                logger.info(f"Using standard Observer for {path}")
                observer = Observer()
                event_handler = DirectoryChangeHandler(
                    callback=self._on_directory_detected,
                    directory_id=dir_id,
                    monitored_path=path
                )
                observer.schedule(event_handler, path, recursive=True)
                observer.daemon = True
                observer.start()
                self._observers[dir_id] = observer
                logger.info(f"Started standard observer for {dir_id}")

            return True
        except Exception as e:
            logger.error(f"Error starting monitoring for {path}: {str(e)}")
            if dir_id in self._observers:
                try:
                    del self._observers[dir_id]
                except:
                    pass
            return False

    def _scan_rclone_directory(self, dir_id, path):
        """Scan rclone-mounted directory for new folders."""
        try:
            for entry in os.scandir(path):
                if entry.is_dir() and not entry.name.startswith('.'):
                    self._on_directory_detected(dir_id, entry.path)
        except Exception as e:
            logger.error(f"Error scanning rclone directory: {e}")

    def _on_directory_detected(self, dir_id, dir_path):
        logger.debug(f"Triggered _on_directory_detected with dir_id={dir_id}, dir_path={dir_path}")
        logger.debug(f"Current monitored_directories keys: {list(self._monitored_directories.keys())}")

        if dir_id not in self._monitored_directories:
            logger.error(f"Unknown dir_id: {dir_id} for detected directory {dir_path}")
            logger.info(f"DEBUG: MONITOR AUTO-SKIPPING - unknown dir_id: {dir_id}")
            return

        dir_info = self._monitored_directories[dir_id]
        logger.debug(f"dir_info: {dir_info}")

        dir_name = dir_info.get('name', 'Unknown')
        monitored_path = dir_info.get('path', '')

        if not dir_name or not monitored_path:
            logger.error(f"Monitored directory config missing name or path for dir_id {dir_id}: {dir_info}")
            logger.info(f"DEBUG: MONITOR AUTO-SKIPPING - missing config: dir_name={dir_name}, monitored_path={monitored_path}")
            return

        # --- CRITICAL: Check if any media file in this folder is in scan history ---
        from src.main import load_scan_history_set, is_any_media_file_in_scan_history
        scan_history_set = load_scan_history_set()
        scan_history_check = is_any_media_file_in_scan_history(dir_path, scan_history_set)
        logger.info(f"DEBUG: Monitor scan history check for {dir_path}: {scan_history_check}")
        if scan_history_check:
            logger.info(f"DEBUG: MONITOR AUTO-SKIPPING due to scan history: {dir_path}")
            logger.info(f"Skipping notification for {dir_path} (already in scan history)")
            return

        folder_name = os.path.relpath(dir_path, monitored_path)
        self._send_directory_notification(dir_name, folder_name)

    def _send_directory_notification(self, dir_name, folder_name):
        logger.info(f"New directory detected: {dir_name} - {folder_name}")
        payload = {
            "directory": dir_name,
            "folder": folder_name,
            "message": f"New directory detected: {dir_name} - {folder_name}"
        }
        logger.debug(f"Webhook payload: {payload}")
        try:
            from src.utils.webhooks import send_monitored_item_notification
            webhook_url = os.environ.get('DISCORD_WEBHOOK_URL')
            if webhook_url:
                send_monitored_item_notification(payload)
        except Exception as e:
            logger.error(f"Failed to send directory notification webhook: {e}")

    def _stop_monitoring(self, dir_id):
        if dir_id in self._observers:
            observer = self._observers[dir_id]
            if isinstance(observer, Observer):
                observer.stop()
                observer.join(timeout=2)
            del self._observers[dir_id]
            logger.info(f"Stopped monitoring for {dir_id}")
            return True
        return False

    def start_all(self):
        for dir_id in self._monitored_directories:
            if self._monitored_directories[dir_id].get('active', False):
                self._start_monitoring(dir_id)

    def stop_all(self):
        for dir_id in list(self._observers.keys()):
            self._stop_monitoring(dir_id)

    def add_pending_file(self, dir_id, file_path):
        self._pending_files.setdefault(dir_id, set()).add(file_path)

    def remove_pending_file(self, dir_id, file_path):
        if dir_id in self._pending_files and file_path in self._pending_files[dir_id]:
            self._pending_files[dir_id].remove(file_path)

    def get_all_pending_files(self):
        return self._pending_files

    def run_pending_scans(self):
        # Placeholder for running pending scans
        pass

    def _scan_existing_subdirectories(self, dir_id, path):
        """Scan for existing subdirectories and trigger detection."""
        logger.info(f"Scanning for immediate subdirectories in {path}")
        try:
            for entry in os.scandir(path):
                if entry.is_dir() and not entry.name.startswith('.'):
                    logger.info(f"Found existing subdirectory: {entry.path}")
                    self._on_directory_detected(dir_id, entry.path)
        except Exception as e:
            logger.error(f"Error scanning immediate subdirectories: {e}")

    def start_monitoring(self, interval: int = 60) -> bool:
        self.start_all()
        return True

    def stop_monitoring(self) -> bool:
        self.stop_all()
        return True

    def is_monitoring(self) -> bool:
        return bool(self._observers)

    def _monitor_loop(self, interval: int) -> None:
        while self.is_monitoring():
            self.monitor_directories()
            time.sleep(interval)

    def get_monitoring_status(self):
        return {dir_id: dir_id in self._observers for dir_id in self._monitored_directories}

    def monitor_directories(self):
        # Placeholder for monitoring logic
        pass

    def detect_changes(self, dir_id):
        # Placeholder for change detection logic
        pass

    def handle_new_files(self, dir_id, new_files, auto_process=False):
        # Placeholder for handling new files
        pass

    def process_directory(self, dir_id, dir_path):
        # Placeholder for directory processing
        pass

    def process_file(self, dir_id, file_path):
        # Placeholder for file processing
        pass

    def start_initial_scan_in_background(self):
        if self._initial_scan_thread and self._initial_scan_thread.is_alive():
            return  # Already running
        self._initial_scan_thread = threading.Thread(target=self._initial_scan_all, daemon=True)
        self._initial_scan_thread.start()

    def _initial_scan_all(self):
        self._initial_scan_running = True
        try:
            for dir_id, info in self._monitored_directories.items():
                if info.get('active', False):
                    path = info.get('path')
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
        finally:
            self._initial_scan_running = False

    def is_initial_scan_running(self):
        return self._initial_scan_running


# Global monitor manager instance for reuse
_monitor_manager = None

def get_monitor_manager():
    """Get a global instance of the MonitorManager."""
    global _monitor_manager
    if _monitor_manager is None:
        _monitor_manager = MonitorManager()
    return _monitor_manager