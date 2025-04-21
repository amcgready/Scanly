"""
Monitor menu for Scanly.

This module provides the menu for monitoring directories.
"""

import os
import time
from datetime import datetime

from src.utils.logger import get_logger
from src.core.monitor_manager import MonitorManager
from src.main import clear_screen, display_ascii_art, DirectoryProcessor

logger = get_logger(__name__)

class MonitorMenu:
    """
    Menu for managing monitored directories.
    """
    
    def __init__(self):
        """Initialize the monitor menu."""
        self.logger = get_logger(__name__)
        self.monitor_manager = MonitorManager()
    
    def show(self):
        """Show the monitor scan menu and handle user input."""
        while True:
            clear_screen()
            display_ascii_art()
            print("=" * 60)
            print("MONITOR SCAN\n")
            
            # Show monitoring status
            is_monitoring = self.monitor_manager.is_monitoring()
            status = "ACTIVE" if is_monitoring else "INACTIVE"
            print(f"Monitoring Status: {status}")
            
            # Get monitored directories
            directories = self.monitor_manager.get_monitored_directories()
            print(f"\nMonitored Directories: {len(directories)}")
            
            # Menu options
            print("\nOptions:")
            print("1. Add Directory to Monitor")
            print("2. Remove Directory from Monitoring")
            print("3. View Monitored Directories")
            print("4. Check for New Files")
            print(f"5. {'Stop' if is_monitoring else 'Start'} Monitoring")
            print("0. Back to Main Menu")
            
            choice = input("\nEnter choice: ").strip()
            
            if choice == "1":
                self._add_directory()
            elif choice == "2":
                self._remove_directory()
            elif choice == "3":
                self._view_directories()
            elif choice == "4":
                self._check_new_files()
            elif choice == "5":
                if is_monitoring:
                    self.monitor_manager.stop_monitoring()
                else:
                    from src.config import get_settings
                    settings = get_settings()
                    interval = int(settings.get('MONITOR_SCAN_INTERVAL', '60'))
                    self.monitor_manager.start_monitoring(interval)
                    print(f"\nMonitoring started with {interval} second interval.")
                    input("\nPress Enter to continue...")
            elif choice == "0":
                # Make sure to stop monitoring before exiting
                if self.monitor_manager.is_monitoring():
                    print("\nStopping monitoring...")
                    self.monitor_manager.stop_monitoring()
                return
            else:
                print("\nInvalid option.")
                input("\nPress Enter to continue...")
    
    def _add_directory(self):
        """Add a directory to monitor."""
        clear_screen()
        display_ascii_art()
        print("=" * 60)
        print("ADD MONITORED DIRECTORY\n")
        
        print("Enter the path to monitor (or 'q' to cancel):")
        directory = input("> ").strip()
        
        if directory.lower() == 'q':
            return
        
        # Clean up the path (remove quotes, etc.)
        directory = directory.strip("'\"")
        
        # Validate directory
        if not os.path.isdir(directory):
            print(f"\nError: {directory} is not a valid directory.")
            input("\nPress Enter to continue...")
            return
        
        # Get optional description
        print("\nEnter a description (optional):")
        description = input("> ").strip() or os.path.basename(directory)
        
        # Add to monitored directories
        if self.monitor_manager.add_directory(directory, description):
            print(f"\nDirectory added to monitoring: {directory}")
        else:
            print(f"\nFailed to add directory: {directory}")
        
        input("\nPress Enter to continue...")
    
    def _remove_directory(self):
        """Remove a directory from monitoring."""
        clear_screen()
        display_ascii_art()
        print("=" * 60)
        print("REMOVE MONITORED DIRECTORY\n")
        
        # Get monitored directories
        directories = self.monitor_manager.get_monitored_directories()
        
        if not directories:
            print("No directories are currently being monitored.")
            input("\nPress Enter to continue...")
            return
        
        # Display directories
        print("Monitored Directories:\n")
        dir_list = list(directories.keys())
        
        for i, directory in enumerate(dir_list, 1):
            info = directories[directory]
            description = info.get('description', os.path.basename(directory))
            print(f"{i}. {description} - {directory}")
        
        print("\nEnter the number of the directory to remove (or '0' to cancel):")
        choice = input("> ").strip()
        
        if choice == '0' or not choice:
            return
        
        # Validate choice
        try:
            index = int(choice) - 1
            if 0 <= index < len(dir_list):
                directory = dir_list[index]
                
                # Confirm removal
                print(f"\nAre you sure you want to remove '{directory}' from monitoring? (y/n)")
                confirm = input("> ").strip().lower()
                
                if confirm == 'y':
                    if self.monitor_manager.remove_directory(directory):
                        print(f"\nDirectory removed from monitoring: {directory}")
                    else:
                        print(f"\nFailed to remove directory: {directory}")
            else:
                print("\nInvalid selection.")
        except ValueError:
            print("\nInvalid input. Please enter a number.")
        
        input("\nPress Enter to continue...")
    
    def _view_directories(self):
        """View monitored directories and their status."""
        clear_screen()
        display_ascii_art()
        print("=" * 60)
        print("MONITORED DIRECTORIES\n")
        
        # Get monitored directories
        directories = self.monitor_manager.get_monitored_directories()
        
        if not directories:
            print("No directories are currently being monitored.")
            input("\nPress Enter to continue...")
            return
        
        # Display directories with details
        for directory, info in directories.items():
            description = info.get('description', os.path.basename(directory))
            last_checked = info.get('last_checked', 0)
            
            # Format last checked time
            if last_checked > 0:
                last_checked_str = datetime.fromtimestamp(last_checked).strftime("%Y-%m-%d %H:%M:%S")
            else:
                last_checked_str = "Never"
            
            # Count processed files
            processed_files = info.get('processed_files', [])
            if isinstance(processed_files, set):
                processed_count = len(processed_files)
            else:
                processed_count = len(processed_files)
            
            # Directory exists check
            exists = os.path.isdir(directory)
            status = "OK" if exists else "NOT FOUND"
            
            print(f"Directory: {directory}")
            print(f"Description: {description}")
            print(f"Status: {status}")
            print(f"Last Checked: {last_checked_str}")
            print(f"Processed Files: {processed_count}")
            print("-" * 60)
        
        input("\nPress Enter to continue...")
    
    def _check_new_files(self):
        """Check for new files in monitored directories."""
        clear_screen()
        display_ascii_art()
        print("=" * 60)
        print("CHECK FOR NEW FILES\n")
        
        # Get monitored directories
        directories = self.monitor_manager.get_monitored_directories()
        
        if not directories:
            print("No directories are currently being monitored.")
            input("\nPress Enter to continue...")
            return
        
        # Display directories
        print("Select a directory to check:\n")
        dir_list = list(directories.keys())
        
        for i, directory in enumerate(dir_list, 1):
            info = directories[directory]
            description = info.get('description', os.path.basename(directory))
            print(f"{i}. {description} - {directory}")
        
        print("\n0. Check All Directories")
        print("C. Cancel")
        
        choice = input("\nEnter choice: ").strip().lower()
        
        if choice == 'c':
            return
        
        dirs_to_check = []
        
        if choice == '0':
            dirs_to_check = dir_list
        else:
            try:
                index = int(choice) - 1
                if 0 <= index < len(dir_list):
                    dirs_to_check = [dir_list[index]]
                else:
                    print("\nInvalid selection.")
                    input("\nPress Enter to continue...")
                    return
            except ValueError:
                print("\nInvalid input. Please enter a number.")
                input("\nPress Enter to continue...")
                return
        
        # Check each directory for new files
        total_new_files = 0
        all_new_files = {}
        
        for directory in dirs_to_check:
            print(f"\nChecking {directory}...")
            
            if not os.path.isdir(directory):
                print(f"Directory does not exist: {directory}")
                continue
            
            new_files = self.monitor_manager.check_for_new_files(directory)
            
            if new_files:
                print(f"Found {len(new_files)} new files")
                total_new_files += len(new_files)
                all_new_files[directory] = new_files
                
                # Preview some files
                for i, file in enumerate(new_files[:5]):
                    print(f"  - {os.path.basename(file)}")
                
                if len(new_files) > 5:
                    print(f"  ... and {len(new_files) - 5} more files")
            else:
                print("No new files found")
        
        # If no new files in any directory, just return
        if total_new_files == 0:
            print("\nNo new files found in any monitored directories.")
            input("\nPress Enter to continue...")
            return
        
        # Ask if user wants to process any of these files
        print(f"\nFound {total_new_files} new files in total.")
        process_choice = input("Do you want to process these files now? (y/n): ").strip().lower()
        
        if process_choice == 'y':
            self._process_new_files(all_new_files)
        else:
            input("\nPress Enter to continue...")
    
    def _process_new_files(self, new_files_by_directory):
        """
        Process new files found in monitored directories.
        
        Args:
            new_files_by_directory: Dictionary mapping directories to lists of new files
        """
        from src.main import DirectoryProcessor
        
        for directory, files in new_files_by_directory.items():
            if not files:
                continue
                
            clear_screen()
            display_ascii_art()
            print("=" * 60)
            print(f"PROCESSING NEW FILES - {os.path.basename(directory)}\n")
            
            print(f"Directory: {directory}")
            print(f"Found {len(files)} new files")
            
            # Options for processing
            print("\nHow would you like to process these files?")
            print("1. Auto Scan (automatic content detection and processing)")
            print("2. Manual Scan (interactive content selection)")
            print("0. Skip this directory")
            
            choice = input("\nEnter choice: ").strip()
            
            if choice == '0':
                continue
                
            auto_mode = (choice == '1')
            
            if not auto_mode and choice != '2':
                print("\nInvalid choice. Using manual mode.")
                auto_mode = False
                input("\nPress Enter to continue...")
            
            # Process the directory
            try:
                processor = DirectoryProcessor(directory, auto_mode=auto_mode)
                processor.process()
                
                # Mark all files in this directory as processed
                self.monitor_manager.mark_files_processed(directory, files)
                
                print(f"\nProcessed {len(files)} files in {directory}")
            except Exception as e:
                self.logger.error(f"Error processing directory {directory}: {e}")
                print(f"\nError processing directory: {e}")
            
            input("\nPress Enter to continue...")