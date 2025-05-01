#!/usr/bin/env python3
"""Monitor menu for Scanly application."""

import os
import time
from pathlib import Path
import sys

# Ensure parent directory is in path for imports
parent_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

from src.main import get_logger, clear_screen, display_ascii_art
from src.core.monitor_processor import MonitorProcessor
from src.core.monitor_manager import MonitorManager

class MonitorMenu:
    """Menu for monitoring functionality."""
    
    def __init__(self):
        """Initialize the monitor menu."""
        self.logger = get_logger(__name__)
        
        # Initialize the MonitorManager
        try:
            from src.core.monitor_manager import MonitorManager
            self.monitor_manager = MonitorManager()
        except ImportError as e:
            self.logger.error(f"Error importing MonitorManager: {e}")
            raise
        
        # Fix invalid entries in monitored directories
        self._fix_invalid_entries()
    
    def _fix_invalid_entries(self):
        """Fix invalid entries in monitored directories."""
        monitored_dirs = self.monitor_manager.get_monitored_directories()
        
        # Check for invalid entries
        invalid_entries = []
        for dir_id, info in monitored_dirs.items():
            if not info.get('path') or info.get('path') == 'Unknown' or not os.path.isdir(info.get('path', '')):
                invalid_entries.append(dir_id)
        
        # Remove invalid entries
        if invalid_entries:
            self.logger.info(f"Removing {len(invalid_entries)} invalid monitored directories")
            for dir_id in invalid_entries:
                self.monitor_manager.remove_directory(dir_id)
            self.monitor_manager._save_monitored_directories()
    
    def show(self):
        """Show the monitor menu."""
        while True:
            # Get monitored directories
            monitored_dirs = self.monitor_manager.get_monitored_directories()
            
            # Check if monitoring is active
            is_monitoring = self.monitor_manager.is_monitoring()
            
            clear_screen()
            display_ascii_art()
            print("=" * 15)
            print("MONITORED DIRECTORIES")
            print("=" * 15)
            
            # Display all monitored directories
            print("\nCurrently monitoring:")
            
            if not monitored_dirs:
                print("\nNo directories are currently being monitored.")
            else:
                for i, (dir_id, dir_info) in enumerate(monitored_dirs.items(), 1):
                    path = dir_info.get('path', 'Unknown')
                    description = dir_info.get('description', os.path.basename(path))
                    status = "Active" if dir_info.get('active', True) else "Paused"
                    auto_process = "Automatic" if dir_info.get('auto_process', False) else "Manual"
                    
                    # Get stats
                    stats = dir_info.get('stats', {})
                    total_processed = stats.get('total_processed', 0)
                    last_processed = stats.get('last_processed', 0)
                    last_processed_str = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(last_processed)) if last_processed else 'Never'
                    
                    # Check for pending files
                    pending_files = dir_info.get('pending_files', [])
                    pending_count = len(pending_files)
                    
                    print(f"\n{i}. {description}")
                    print(f"   Path: {path}")
                    print(f"   Status: {status}")
                    print(f"   Processing Mode: {auto_process}")
                    print(f"   Total Files Processed: {total_processed}")
                    print(f"   Last Activity: {last_processed_str}")
                    
                    if pending_count > 0:
                        print(f"   Pending Files: {pending_count} (awaiting processing)")
            
            print("\nOptions:")
            print("1. Process pending files")
            print("2. Add new directory to monitor")
            print("3. Remove directory from monitoring")
            print("4. Pause/Resume monitoring")
            print(f"5. {'Stop' if is_monitoring else 'Start'} Monitoring Process")
            print("6. Configure monitoring settings")
            print("0. Back to main menu")
            
            choice = input("\nEnter your choice: ").strip()
            
            if choice == '0':
                break
            elif choice == '1':
                self.process_pending_files()
            elif choice == '2':
                self.add_monitored_directory()
            elif choice == '3':
                self.remove_monitored_directory()
            elif choice == '4':
                self.toggle_monitoring_status()
            elif choice == '5':
                self.toggle_monitoring_process(is_monitoring)
            elif choice == '6':
                self.configure_monitoring()
            else:
                print("Invalid choice.")
                input("\nPress Enter to continue...")
    
    def toggle_monitoring_process(self, is_active):
        """Start or stop the monitoring process."""
        if is_active:
            # Stop monitoring
            if self.monitor_manager.stop_monitoring():
                print("\nMonitoring process stopped.")
            else:
                print("\nFailed to stop monitoring process.")
        else:
            # Start monitoring
            from src.config import get_settings
            settings = get_settings()
            interval = int(settings.get('MONITOR_SCAN_INTERVAL', '15'))  # Changed from 60 to 15
            if self.monitor_manager.start_monitoring(interval):
                print(f"\nMonitoring started with {interval} second interval.")
            else:
                print("\nFailed to start monitoring process.")
                
        input("\nPress Enter to continue...")
    
    def process_pending_files(self):
        """Process pending files in monitored directories."""
        # Get directories with pending files
        pending_dirs = {}
        for dir_id, dir_info in self.monitor_manager.get_monitored_directories().items():
            pending_files = dir_info.get('pending_files', [])
            if pending_files:
                pending_dirs[dir_id] = {
                    'path': dir_info.get('path', ''),
                    'description': dir_info.get('description', ''),
                    'pending_files': pending_files,
                    'count': len(pending_files)
                }
        
        if not pending_dirs:
            print("\nNo pending files found in monitored directories.")
            input("\nPress Enter to continue...")
            return
        
        # Display directories with pending files
        clear_screen()
        display_ascii_art()
        print("=" * 60)
        print("PROCESS PENDING FILES")
        print("=" * 60)
        
        print("\nDirectories with pending files:")
        options = []
        for i, (dir_id, dir_info) in enumerate(pending_dirs.items(), 1):
            description = dir_info['description'] or os.path.basename(dir_info['path'])
            print(f"{i}. {description} ({dir_info['count']} files)")
            options.append(dir_id)
        
        print("\n0. Back to monitor menu")
        
        choice = input("\nSelect directory to process (0 to go back): ").strip()
        
        if choice == '0':
            return
        
        try:
            idx = int(choice) - 1
            if idx < 0 or idx >= len(options):
                raise ValueError("Invalid choice")
            
            selected_dir_id = options[idx]
            directory_info = pending_dirs[selected_dir_id]
            
            # Ask for processing mode
            clear_screen()
            display_ascii_art()
            print("=" * 60)
            print("PROCESS PENDING FILES")
            print("=" * 60)
            
            print(f"\nDirectory: {directory_info['description']}")
            print(f"Path: {directory_info['path']}")
            print(f"Number of pending files: {directory_info['count']}")
            
            print("\nSelect processing mode:")
            print("1. Auto Process (automatic content detection and processing)")
            print("2. Manual Process (interactive content selection and processing)")
            print("0. Cancel")
            
            mode_choice = input("\nEnter choice (0-2): ").strip()
            
            if mode_choice == '0':
                return
                
            auto_mode = (mode_choice == '1')
            
            if not auto_mode and mode_choice != '2':
                print("\nInvalid choice. Using manual processing mode.")
                auto_mode = False
                input("\nPress Enter to continue...")
            
            # Process the files
            print(f"\nProcessing {directory_info['count']} files from {directory_info['description']}...")
            
            from src.core.monitor_processor import MonitorProcessor
            processor = MonitorProcessor(auto_mode=auto_mode)
            
            try:
                processed, errors, skipped = processor.process_new_files(
                    directory_info['path'], 
                    directory_info['pending_files']
                )
                
                # Record the results
                self.monitor_manager._record_processing(
                    selected_dir_id, processed, errors, skipped
                )
                
                # Clear pending files that were processed
                self.monitor_manager.clear_pending_files(selected_dir_id)
                
                print(f"\nProcessing completed:")
                print(f"- Processed: {processed} files")
                print(f"- Skipped: {skipped} files")
                print(f"- Errors: {errors} files")
                
            except Exception as e:
                self.logger.error(f"Error processing files: {e}", exc_info=True)
                print(f"\nError processing files: {e}")
            
            input("\nPress Enter to continue...")
            
        except (ValueError, IndexError):
            print("Invalid choice.")
            input("\nPress Enter to continue...")
    
    def add_monitored_directory(self):
        """Add a new directory to monitoring."""
        clear_screen()
        display_ascii_art()
        print("=" * 60)
        print("ADD MONITORED DIRECTORY")
        print("=" * 60)
        
        print("\nEnter the path of the directory to monitor (or 'q' to cancel):")
        dir_path = input("> ").strip()
        
        if dir_path.lower() == 'q':
            return
        
        # Strip quotes that might be added when dragging paths into terminal
        dir_path = dir_path.strip("'\"")
        
        # Validate directory exists
        if not os.path.isdir(dir_path):
            print(f"\nError: {dir_path} is not a valid directory.")
            input("\nPress Enter to continue...")
            return
        
        # Get description
        print("\nEnter a description for this directory (optional):")
        description = input("> ").strip() or os.path.basename(dir_path)
        
        # Ask for processing mode for existing files
        print("\nHow should existing files in this directory be processed?")
        print("1. Automatically (process files without user interaction)")
        print("2. Manually (require manual review before processing)")
        processing_choice = input("\nEnter choice (1-2): ").strip()
        
        auto_process = (processing_choice == "1")
        
        # Add to monitored directories with auto_process flag
        if self.monitor_manager.add_directory(dir_path, description, auto_process=auto_process):
            print(f"\nDirectory added to monitoring: {dir_path}")
            if auto_process:
                print("Existing files will be processed automatically.")
            else:
                print("Existing files queued for manual processing.")
            
            # Ask if user wants to start monitoring now
            print("\nDo you want to start monitoring now? (y/n)")
            start_now = input("> ").strip().lower()
            
            if start_now == 'y':
                from src.config import get_settings
                settings = get_settings()
                interval = int(settings.get('MONITOR_SCAN_INTERVAL', '15'))  # Changed from 60 to 15
                self.monitor_manager.start_monitoring(interval)
                print(f"\nMonitoring started with {interval} second interval.")
        else:
            print(f"\nFailed to add directory: {dir_path}")
        
        input("\nPress Enter to continue...")
    
    def remove_monitored_directory(self):
        """Remove a directory from monitoring."""
        monitored_dirs = self.monitor_manager.get_monitored_directories()
        
        if not monitored_dirs:
            print("No monitored directories found.")
            input("\nPress Enter to continue...")
            return
        
        clear_screen()
        display_ascii_art()
        print("=" * 60)
        print("REMOVE MONITORED DIRECTORY")
        print("=" * 60)
        
        print("\nSelect a directory to remove from monitoring:")
        options = []
        for i, (dir_id, dir_info) in enumerate(monitored_dirs.items(), 1):
            path = dir_info.get('path', 'Unknown')
            description = dir_info.get('description', os.path.basename(path))
            print(f"{i}. {description} ({path})")
            options.append(dir_id)
        
        print("\n0. Cancel")
        
        choice = input("\nEnter choice (0 to cancel): ").strip()
        
        if choice == '0':
            return
        
        try:
            idx = int(choice) - 1
            if idx < 0 or idx >= len(options):
                raise ValueError("Invalid choice")
            
            selected_dir_id = options[idx]
            directory_info = monitored_dirs[selected_dir_id]
            
            # Confirm removal
            print(f"\nAre you sure you want to remove {directory_info.get('description', selected_dir_id)}? (y/n)")
            confirm = input("> ").strip().lower()
            
            if confirm == 'y':
                if self.monitor_manager.remove_directory(selected_dir_id):
                    print("\nDirectory removed from monitoring.")
                else:
                    print("\nFailed to remove directory.")
            else:
                print("\nRemoval cancelled.")
                
        except (ValueError, IndexError):
            print("Invalid choice.")
            
        input("\nPress Enter to continue...")
    
    def toggle_monitoring_status(self):
        """Toggle active status for a monitored directory."""
        monitored_dirs = self.monitor_manager.get_monitored_directories()
        
        if not monitored_dirs:
            print("No monitored directories found.")
            input("\nPress Enter to continue...")
            return
        
        clear_screen()
        display_ascii_art()
        print("=" * 60)
        print("TOGGLE MONITORING STATUS")
        print("=" * 60)
        
        print("\nSelect a directory to toggle monitoring status:")
        options = []
        for i, (dir_id, dir_info) in enumerate(monitored_dirs.items(), 1):
            path = dir_info.get('path', 'Unknown')
            description = dir_info.get('description', os.path.basename(path))
            status = "Active" if dir_info.get('active', True) else "Paused"
            print(f"{i}. {description} ({path}) - Status: {status}")
            options.append(dir_id)
        
        print("\n0. Cancel")
        
        choice = input("\nEnter choice (0 to cancel): ").strip()
        
        if choice == '0':
            return
        
        try:
            idx = int(choice) - 1
            if idx < 0 or idx >= len(options):
                raise ValueError("Invalid choice")
            
            selected_dir_id = options[idx]
            directory_info = monitored_dirs[selected_dir_id]
            current_status = directory_info.get('active', True)
            
            # Toggle status
            if self.monitor_manager.set_directory_status(selected_dir_id, not current_status):
                new_status = "paused" if current_status else "active"
                print(f"\nDirectory monitoring is now {new_status}.")
            else:
                print("\nFailed to update directory status.")
                
        except (ValueError, IndexError):
            print("Invalid choice.")
            
        input("\nPress Enter to continue...")
    
    def configure_monitoring(self):
        """Configure monitoring settings."""
        from src.config import get_settings, get_monitor_settings
        
        clear_screen()
        display_ascii_art()
        print("=" * 60)
        print("MONITORING SETTINGS")
        print("=" * 60)
        
        # Get current settings
        settings = get_settings()
        monitor_settings = get_monitor_settings()
        
        auto_process = monitor_settings.get('MONITOR_AUTO_PROCESS', 'false').lower() == 'true'
        scan_interval = int(monitor_settings.get('MONITOR_SCAN_INTERVAL', '15'))
        enable_realtime = monitor_settings.get('MONITOR_ENABLE_REALTIME', 'false').lower() == 'true'
        
        # Discord notification settings
        discord_enabled = monitor_settings.get('ENABLE_DISCORD_NOTIFICATIONS', 'false').lower() == 'true'
        webhook_url = monitor_settings.get('DISCORD_WEBHOOK_URL', '')
        webhook_configured = bool(webhook_url and webhook_url != "\"\"" and webhook_url != "''")
        
        print("\nMonitoring Settings:")
        print(f"1. Auto-process new files: {'Enabled' if auto_process else 'Disabled'}")
        print(f"2. Scan interval: {scan_interval} seconds")
        print(f"3. Real-time monitoring: {'Enabled' if enable_realtime else 'Disabled'}")
        
        print("\nNotification Settings:")
        print(f"4. Discord notifications: {'Enabled' if discord_enabled else 'Disabled'}")
        print(f"5. Discord webhook URL: {webhook_url[:20] + '...' if webhook_configured else 'Not configured'}")
        
        print("\n0. Back to monitor menu")
        
        choice = input("\nSelect setting to modify (0 to go back): ").strip()
        
        if choice == '0':
            return
        elif choice == '1':
            # Toggle auto-processing
            new_value = 'false' if auto_process else 'true'
            self._update_monitor_setting('MONITOR_AUTO_PROCESS', new_value)
            print(f"\nAuto-processing is now {'enabled' if new_value == 'true' else 'disabled'}.")
        elif choice == '2':
            # Change scan interval
            print("\nEnter new scan interval in seconds (15-3600):")
            try:
                new_interval = input("> ").strip()
                new_interval_int = int(new_interval)
                
                if 15 <= new_interval_int <= 3600:
                    self._update_monitor_setting('MONITOR_SCAN_INTERVAL', str(new_interval_int))
                    print(f"\nScan interval updated to {new_interval_int} seconds.")
                    
                    # Update active monitor if running
                    if self.monitor_manager.is_monitoring():
                        self.monitor_manager.stop_monitoring()
                        self.monitor_manager.start_monitoring(new_interval_int)
                        print("Applied new interval to active monitoring.")
                else:
                    print("Interval must be between 15 and 3600 seconds.")
            except ValueError:
                print("Invalid input. Please enter a number.")
        elif choice == '3':
            # Toggle real-time monitoring
            new_value = 'false' if enable_realtime else 'true'
            self._update_monitor_setting('MONITOR_ENABLE_REALTIME', new_value)
            print(f"\nReal-time monitoring is now {'enabled' if new_value == 'true' else 'disabled'}.")
        elif choice == '4':
            # Toggle Discord notifications
            new_value = 'false' if discord_enabled else 'true'
            self._update_monitor_setting('ENABLE_DISCORD_NOTIFICATIONS', new_value)
            print(f"\nDiscord notifications are now {'enabled' if new_value == 'true' else 'disabled'}.")
            
            # If enabling but webhook not configured, prompt for webhook URL
            if new_value == 'true' and not webhook_configured:
                print("\nDiscord webhook URL is not configured.")
                print("Would you like to configure it now? (y/n)")
                if input("> ").strip().lower() == 'y':
                    self._configure_discord_webhook()
        elif choice == '5':
            # Configure Discord webhook URL
            self._configure_discord_webhook()
        else:
            print("Invalid choice.")
        
        input("\nPress Enter to continue...")
    
    def _configure_discord_webhook(self):
        """Configure Discord webhook URL."""
        print("\nEnter Discord webhook URL:")
        print("(You can get this from Discord by right-clicking a channel → Integrations → Webhooks)")
        webhook_url = input("> ").strip()
        
        if webhook_url:
            # Test the webhook
            print("\nTesting webhook connection...")
            try:
                from src.utils.discord_utils import send_discord_notification
                result = send_discord_notification(
                    webhook_url=webhook_url,
                    title="Scanly Test Notification",
                    message="This is a test notification from Scanly. If you can see this, Discord notifications are working correctly!",
                )
                
                if result:
                    print("\nWebhook test successful! Discord notifications will now work.")
                    self._update_monitor_setting('DISCORD_WEBHOOK_URL', webhook_url)
                else:
                    print("\nWebhook test failed. Please check the URL and try again.")
                    print("Would you like to save this webhook URL anyway? (y/n)")
                    if input("> ").strip().lower() == 'y':
                        self._update_monitor_setting('DISCORD_WEBHOOK_URL', webhook_url)
            except Exception as e:
                print(f"\nError testing webhook: {e}")
                print("Would you like to save this webhook URL anyway? (y/n)")
                if input("> ").strip().lower() == 'y':
                    self._update_monitor_setting('DISCORD_WEBHOOK_URL', webhook_url)
        else:
            print("\nWebhook URL not provided. Discord notifications will not work.")
    
    def _update_monitor_setting(self, name, value):
        """Update a monitor setting."""
        from src.main import _update_env_var
        _update_env_var(name, value)