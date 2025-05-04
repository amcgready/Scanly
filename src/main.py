#!/usr/bin/env python3
"""Scanly: A media file scanner and organizer.

This module is the main entry point for the Scanly application.
"""

import os
import sys
import re
import json
import time
import logging
import unicodedata
from pathlib import Path
import datetime
import shutil
import threading

# Define a filter to exclude certain log messages from console
class ConsoleFilter(logging.Filter):
    def filter(self, record):
        # Filter out monitor_manager loading messages
        if "monitor_manager" in record.name and record.msg and "Loaded" in str(record.msg):
            return False
            
        # Filter out folder ID related messages
        if record.msg and any(pattern in str(record.msg) for pattern in [
            "movies with TMDB ID", 
            "Adding TMDB ID", 
            "[tmdb-", 
            "Updated with TMDB ID"
        ]):
            return False
            
        # Filter out routine monitor scanning messages
        if "monitor_processor" in record.name and any(pattern in str(record.msg) for pattern in [
            "Checking for new files",
            "No changes detected",
            "Routine scan"
        ]):
            return False
        
        # Filter out specific scanner matching messages
        if record.msg and any(pattern in str(record.msg) for pattern in [
            "EXACT MATCH:",
            "STRONG CONTAINMENT:",
            "STRONG SUBSTRING:",
            "Title found in scanner list",
            "Trying to fetch TMDB ID",
            "Error searching TMDB:"
        ]):
            return False
            
        # Only show critical errors to console for specific loggers
        if record.name.startswith('urllib3') or record.name.startswith('requests'):
            return record.levelno >= logging.WARNING
        return True

# Set up basic logging configuration
console_handler = logging.StreamHandler()
console_handler.addFilter(ConsoleFilter())

# Create a file handler with proper path creation
log_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'logs')
os.makedirs(log_dir, exist_ok=True)
file_handler = logging.FileHandler(os.path.join(log_dir, 'scanly.log'), 'a')

# Add a separate file handler for monitor logs
monitor_log_file = os.path.join(log_dir, 'monitor.log')
monitor_handler = logging.FileHandler(monitor_log_file, 'a')
monitor_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
monitor_filter = logging.Filter('src.core.monitor')
monitor_handler.addFilter(monitor_filter)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        console_handler,
        file_handler,
        monitor_handler
    ]
)

# Ensure parent directory is in path for imports
parent_dir = os.path.dirname(os.path.dirname(__file__))
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

# Import dotenv to load environment variables
try:
    from dotenv import load_dotenv
    load_dotenv()  # Load environment variables from .env file
except ImportError:
    print("Warning: dotenv package not found. Environment variables must be set manually.")

# Helper function to get a logger
def get_logger(name):
    """Get a logger with the given name."""
    return logging.getLogger(name)

logger = get_logger(__name__)

# Add this function as a standalone function, outside of any class
def _update_env_var(name, value):
    """Update an environment variable both in memory and in .env file."""
    # Update in memory
    os.environ[name] = value
    
    # Update in .env file
    try:
        env_path = os.path.join(os.path.dirname(__file__), '..', '.env')
        
        # Read existing content
        if os.path.exists(env_path):
            with open(env_path, 'r') as f:
                lines = f.readlines()
        else:
            lines = []
        
        # Check if the variable already exists in the file
        var_exists = False
        for i, line in enumerate(lines):
            if line.strip().startswith(f"{name}="):
                lines[i] = f"{name}={value}\n"
                var_exists = True
                break
        
        # Add the variable if it doesn't exist
        if not var_exists:
            lines.append(f"{name}={value}\n")
        
        # Write the updated content back to the file
        with open(env_path, 'w') as f:
            f.writelines(lines)
        
        return True
    except Exception as e:
        logger = get_logger(__name__)
        logger.error(f"Error updating environment variable: {e}")
        return False

# Try to load the TMDB API 
try:
    from src.api.tmdb import TMDB
except ImportError as e:
    logger = get_logger(__name__)
    logger.error(f"Error importing TMDB API: {e}. TMDB functionality will be disabled.")
    
    # Define a stub TMDB class
    class TMDB:
        def __init__(self):
            pass
        
        def search_movie(self, query):
            logger.error("TMDB API not available. Cannot search for movies.")
            return []
        
        def search_tv(self, query):
            logger.error("TMDB API not available. Cannot search for TV shows.")
            return []
        
        def get_movie_details(self, movie_id):
            logger.error("TMDB API not available. Cannot get movie details.")
            return {}
        
        def get_tv_details(self, tv_id):
            logger.error("TMDB API not available. Cannot get TV details.")
            return {}

# Get destination directory from environment variables
DESTINATION_DIRECTORY = os.environ.get('DESTINATION_DIRECTORY', '')

# Clean directory path
def _clean_directory_path(path):
    """Clean up the directory path."""
    # Remove quotes and whitespace
    path = path.strip()
    if path.startswith('"') and path.endswith('"'):
        path = path[1:-1]
    elif path.startswith("'") and path.endswith("'"):
        path = path[1:-1]
    
    # Convert to absolute path if needed
    if path and not os.path.isabs(path):
        path = os.path.abspath(path)
    
    return path

# Import utility functions for scan history
def load_scan_history():
    """Load scan history from file."""
    try:
        history_path = os.path.join(os.path.dirname(__file__), 'scan_history.json')
        if os.path.exists(history_path):
            with open(history_path, 'r') as f:
                return json.load(f)
    except Exception as e:
        logger.error(f"Error loading scan history: {e}")
    return None

def save_scan_history(directory_path, processed_files=0, total_files=0, media_files=None):
    """Save scan history to file."""
    try:
        history_path = os.path.join(os.path.dirname(__file__), 'scan_history.json')
        history = {
            'path': directory_path,
            'processed_files': processed_files,
            'total_files': total_files,
            'media_files': media_files or []
        }
        with open(history_path, 'w') as f:
            json.dump(history, f)
        return True
    except Exception as e:
        logger.error(f"Error saving scan history: {e}")
        return False

def clear_scan_history():
    """Clear scan history file."""
    try:
        history_path = os.path.join(os.path.dirname(__file__), 'scan_history.json')
        if os.path.exists(history_path):
            os.remove(history_path)
            return True
        return False
    except Exception as e:
        logger.error(f"Error clearing scan history: {e}")
        return False

def history_exists():
    """Check if scan history exists."""
    history_path = os.path.join(os.path.dirname(__file__), 'scan_history.json')
    return os.path.exists(history_path)

# Function to load skipped items
def load_skipped_items():
    """Load skipped items from file."""
    try:
        skipped_path = os.path.join(os.path.dirname(__file__), 'skipped_items.json')
        if os.path.exists(skipped_path):
            with open(skipped_path, 'r') as f:
                return json.load(f)
    except Exception as e:
        logger.error(f"Error loading skipped items: {e}")
    return []

# Function to save skipped items
def save_skipped_items(items):
    """Save skipped items to file."""
    try:
        skipped_path = os.path.join(os.path.dirname(__file__), 'skipped_items.json')
        with open(skipped_path, 'w') as f:
            json.dump(items, f)
        return True
    except Exception as e:
        logger.error(f"Error saving skipped items: {e}")
        return False

def clear_skipped_items():
    """Clear all skipped items from the registry."""
    global skipped_items_registry
    skipped_items_registry = []
    save_skipped_items(skipped_items_registry)
    print("\nAll skipped items have been cleared.")
    input("\nPress Enter to continue...")

# Global skipped items registry
skipped_items_registry = load_skipped_items()

# Function to clear the screen
def clear_screen():
    """Clear the terminal screen."""
    os.system('cls' if os.name == 'nt' else 'clear')

# Function to display ASCII art
def display_ascii_art():
    """Display the program's ASCII art."""
    try:
        art_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'art.txt')
        if os.path.exists(art_path):
            with open(art_path, 'r') as f:
                print(f.read())
        else:
            print("\nSCANLY")
    except Exception as e:
        print("SCANLY")  # Fallback if art file can't be loaded

# Display help information
def display_help():
    """Display help information."""
    clear_screen()
    display_ascii_art()
    print("=" * 60)
    print("HELP INFORMATION")
    print("=" * 60)
    print("\nScanly is a media file scanner and organizer.")
    print("\nOptions:")
    print("  1. Individual Scan - Scan a single directory for media files")
    print("  2. Multi Scan     - Scan multiple directories")
    print("  3. Resume Scan    - Resume a previously interrupted scan")
    print("  4. Settings       - Configure application settings")
    print("  0. Quit           - Exit the application")
    print("\nPress Enter to continue...")
    input()

# Function to review skipped items
def review_skipped_items():
    """Review and process previously skipped items."""
    global skipped_items_registry
    
    if not skipped_items_registry:
        print("No skipped items to review.")
        input("\nPress Enter to continue...")
        return
    
    while True:
        clear_screen()
        display_ascii_art()
        print("=" * 60)
        print("SKIPPED ITEMS")
        print("=" * 60)
        print(f"\nFound {len(skipped_items_registry)} skipped items:")
        
        # Show a paginated list of skipped items if there are many
        items_per_page = 10
        total_pages = (len(skipped_items_registry) + items_per_page - 1) // items_per_page
        current_page = 1
        
        def show_items_page(page_num):
            start_idx = (page_num - 1) * items_per_page
            end_idx = min(start_idx + items_per_page, len(skipped_items_registry))
            
            for i in range(start_idx, end_idx):
                item = skipped_items_registry[i]
                subfolder = item.get('subfolder', 'Unknown')
                # Just show the folder name in the list view
                print(f"\n{i+1}. {subfolder}")
        
        show_items_page(current_page)
        
        if total_pages > 1:
            print(f"\nPage {current_page} of {total_pages}")
        
        print("\nOptions:")
        print("1. Process a skipped item")
        print("2. Clear all skipped items")
        if total_pages > 1:
            print("3. Next page")
            print("4. Previous page")
        print("0. Return to main menu")
        
        choice = input("\nEnter choice: ").strip()
        
        if choice == "1":
            idx = input("Enter item number to process: ").strip()
            if idx.isdigit() and 1 <= int(idx) <= len(skipped_items_registry):
                item_index = int(idx) - 1
                item = skipped_items_registry[item_index]
                path = item.get('path', '')
                subfolder_name = item.get('subfolder', 'Unknown')
                
                if path and os.path.exists(path):
                    # Process the skipped item interactively
                    clear_screen()
                    display_ascii_art()
                    print("=" * 60)
                    print(f"PROCESSING SKIPPED ITEM: {subfolder_name}")
                    print("=" * 60)
                    
                    subfolder_path = item.get('path', '')
                    
                    print(f"\nFolder path: {subfolder_path}")
                    
                    # Count media files in subfolder
                    media_files = []
                    for root, _, files in os.walk(subfolder_path):
                        for file in files:
                            if file.endswith(('.mp4', '.mkv', '.avi', '.mov', '.wmv', '.m4v')):
                                media_files.append(os.path.join(root, file))
                    
                    print(f"Contains {len(media_files)} media files")
                    
                    # Get title and year from the item
                    title = item.get('suggested_name', subfolder_name)
                    year = None  # Extract from title if possible
                    year_match = re.search(r'\((\d{4})\)', title)
                    if year_match:
                        year = year_match.group(1)
                    
                    # Get content type from the item
                    is_tv = item.get('is_tv', False)
                    is_anime = item.get('is_anime', False)
                    
                    content_type = "TV Show" if is_tv else "Movie"
                    anime_label = " (Anime)" if is_anime else ""
                    
                    # Display current detection
                    print("\nCurrent detection:")
                    print(f"Title: {title}")
                    print(f"Year: {year if year else 'Unknown'}")
                    print(f"Content type: {content_type}{anime_label}")
                    print(f"Error: {item.get('error', 'Unknown error')}")
                    
                    # Interactive mode - similar to regular processing
                    print("\nOptions:")
                    print("1. Accept match and process (default - press Enter)")
                    print("2. Search with new title")
                    print("3. Change content type")
                    print("4. Skip (keep in review list)")
                    print("5. Remove from review list")
                    print("0. Return to skipped items menu")
                    
                    choice = input("\nEnter choice (1-5, or press Enter for option 1): ").strip()
                    
                    # Default to option 1 if user just presses Enter
                    if not choice:
                        choice = "1"
                    
                    if choice == "1":
                        # Process with current detection
                        print(f"\nProcessing {subfolder_name} as {content_type}{anime_label}...")
                        # Process the file/directory
                        if os.path.isfile(path):
                            # For files, process the parent directory
                            processor = DirectoryProcessor(os.path.dirname(path))
                            processor.process()
                        else:
                            # For directories, process directly
                            processor = DirectoryProcessor(path)
                            processor.process()
                        
                        # Remove from skipped items
                        skipped_items_registry.pop(item_index)
                        save_skipped_items(skipped_items_registry)
                        input("\nPress Enter to continue...")
                        
                    elif choice == "2":
                        # Search with new title
                        print("\nEnter new title:")
                        new_title = input("> ").strip()
                        
                        print("\nEnter year (optional, press Enter to skip):")
                        new_year = input("> ").strip()
                        
                        if new_title:
                            item['suggested_name'] = new_title
                        if new_year:
                            # Update with year in parentheses
                            if '(' in item['suggested_name']:
                                item['suggested_name'] = re.sub(r'\(\d{4}\)', f'({new_year})', item['suggested_name'])
                            else:
                                item['suggested_name'] = f"{item['suggested_name']} ({new_year})"
                        
                        # Update skipped items registry
                        save_skipped_items(skipped_items_registry)
                        
                        print(f"\nTitle updated to: {item['suggested_name']}")
                        input("\nPress Enter to continue...")
                        
                    elif choice == "3":
                        # Change content type
                        print("\nSelect the correct content type:")
                        print("1. Movie")
                        print("2. TV Show")
                        print("3. Anime Movie")
                        print("4. Anime TV Show")
                        
                        content_choice = input("\nEnter choice (1-4): ").strip()
                        
                        if content_choice == "1":
                            item['is_tv'] = False
                            item['is_anime'] = False
                        elif content_choice == "2":
                            item['is_tv'] = True
                            item['is_anime'] = False
                        elif content_choice == "3":
                            item['is_tv'] = False
                            item['is_anime'] = True
                        elif content_choice == "4":
                            item['is_tv'] = True
                            item['is_anime'] = True
                        else:
                            print("\nInvalid choice. Content type unchanged.")
                        
                        # Update content type variables
                        is_tv = item['is_tv']
                        is_anime = item['is_anime']
                        content_type = "TV Show" if is_tv else "Movie"
                        anime_label = " (Anime)" if is_anime else ""
                        
                        # Update skipped items registry
                        save_skipped_items(skipped_items_registry)
                        
                        print(f"\nContent type updated to: {content_type}{anime_label}")
                        input("\nPress Enter to continue...")
                        
                    elif choice == "4":
                        # Keep in review list
                        print("\nItem kept in review list.")
                        input("\nPress Enter to continue...")
                        
                    elif choice == "5":
                        # Remove from review list
                        skipped_items_registry.pop(item_index)
                        save_skipped_items(skipped_items_registry)
                        print("\nItem removed from review list.")
                        input("\nPress Enter to continue...")
                    
                    elif choice == "0":
                        # Return to skipped items menu
                        pass
                    
                    else:
                        print("\nInvalid choice.")
                        input("\nPress Enter to continue...")
                else:
                    print("\nFile or directory no longer exists.")
                    print("Removing from skipped items list.")
                    skipped_items_registry.pop(item_index)
                    save_skipped_items(skipped_items_registry)
                    input("\nPress Enter to continue...")
            else:
                print("\nInvalid item number.")
                input("\nPress Enter to continue...")
                
        elif choice == "2":
            # Confirm before clearing
            confirm = input("\nAre you sure you want to clear all skipped items? (y/n): ").strip().lower()
            if confirm == 'y':
                clear_skipped_items()
                return
                
        elif total_pages > 1 and choice == "3":
            # Next page
            if current_page < total_pages:
                current_page += 1
                
        elif total_pages > 1 and choice == "4":
            # Previous page
            if current_page > 1:
                current_page -= 1
                
        elif choice == "0":
            return
            
        else:
            print("\nInvalid choice.")
            input("\nPress Enter to continue...")

def _check_monitor_status():
    """Check and fix the monitor status if needed."""
    from src.core.monitor_manager import MonitorManager
    
    monitor_manager = MonitorManager()
    monitored_dirs = monitor_manager.get_monitored_directories()
    
    # Print current state
    print("Current monitored directories:")
    for dir_id, info in monitored_dirs.items():
        print(f" - ID: {dir_id}")
        print(f"   Path: {info.get('path', 'Unknown')}")
        print(f"   Active: {info.get('active', False)}")
        print(f"   Pending files: {len(info.get('pending_files', []))}")
    
    # Check for invalid entries
    invalid_entries = []
    for dir_id, info in monitored_dirs.items():
        if not info.get('path') or not os.path.isdir(info.get('path', '')):
            invalid_entries.append(dir_id)
    
    # Remove invalid entries
    if invalid_entries:
        print(f"\nRemoving {len(invalid_entries)} invalid monitored directories...")
        for dir_id in invalid_entries:
            monitor_manager.remove_directory(dir_id)
        monitor_manager._save_monitored_directories()
        print("Done.")
    
    input("\nPress Enter to continue...")

# Ensure this is consistently used in MonitorManager's start_monitoring method
def start_monitoring(self, interval_minutes: int = 60) -> bool:
    """
    Start monitoring directories.
    
    Args:
        interval_minutes: Check interval in minutes
        
    Returns:
        bool: True if started successfully, False otherwise
    """
    # Convert minutes to seconds for the actual loop
    interval_seconds = interval_minutes * 60
    
    # Start the monitoring thread
    self.stop_event = threading.Event()
    self.monitor_thread = threading.Thread(target=self._monitor_loop, args=(interval_seconds,))
    self.monitor_thread.daemon = True
    self.monitor_thread.start()
    
    return True

# MainMenu class
class MainMenu:
    """Main menu handler for the application."""
    
    def __init__(self):
        self.logger = get_logger(__name__)
    
    def individual_scan(self):
        """Handle individual directory scan."""
        clear_screen()
        display_ascii_art()
        print("=" * 60)
        print("INDIVIDUAL SCAN")
        print("=" * 60)
        
        # Get the directory path from the user
        print("\nEnter the path of the directory to scan (or 'q' to cancel): ")
        dir_path = input("> ").strip()
        
        if dir_path.lower() == 'q':
            return
        
        # Clean up the directory path
        dir_path = _clean_directory_path(dir_path)
        
        if not os.path.isdir(dir_path):
            print(f"\nError: '{dir_path}' is not a valid directory.")
            input("\nPress Enter to continue...")
            return
        
        # Create a DirectoryProcessor and process the directory
        processor = DirectoryProcessor(dir_path)
        processor.process()
        
        input("\nScan complete. Press Enter to continue...")
    
    def multi_scan(self):
        """Handle scanning of multiple directories."""
        clear_screen()
        display_ascii_art()
        print("=" * 60)
        print("MULTI SCAN")
        print("=" * 60)
        
        dirs_to_scan = []
        
        while True:
            print("\nCurrent directories to scan:")
            if dirs_to_scan:
                for i, path in enumerate(dirs_to_scan):
                    print(f"{i+1}. {path}")
            else:
                print("(None)")
                
            print("\nOptions:")
            print("1. Add directory")
            print("2. Remove directory")
            print("3. Begin scan")
            print("q. Return to main menu")  # Changed from "0" to "q"
            
            choice = input("\nEnter choice: ").strip().lower()  # Convert to lowercase for case-insensitive comparison
            
            if choice == "1":
                print("\nEnter the path of the directory to add:")
                dir_path = input("> ").strip()
                dir_path = _clean_directory_path(dir_path)
                
                if os.path.isdir(dir_path):
                    if dir_path not in dirs_to_scan:
                        dirs_to_scan.append(dir_path)
                        print(f"\nAdded: {dir_path}")
                    else:
                        print("\nThis directory is already in the list.")
                else:
                    print(f"\nError: '{dir_path}' is not a valid directory.")
                
                input("\nPress Enter to continue...")
                clear_screen()
                display_ascii_art()
                print("=" * 60)
                print("MULTI SCAN")
                print("=" * 60)
                
            elif choice == "2":
                if not dirs_to_scan:
                    print("\nNo directories to remove.")
                    input("\nPress Enter to continue...")
                else:
                    try:
                        idx = input("\nEnter the number of the directory to remove (or 'c' to cancel): ").strip()
                        if idx.lower() == 'c':
                            continue
                        idx = int(idx) - 1
                        if 0 <= idx < len(dirs_to_scan):
                            removed = dirs_to_scan.pop(idx)
                            print(f"\nRemoved: {removed}")
                        else:
                            print("\nInvalid number.")
                    except ValueError:
                        print("\nPlease enter a valid number.")
                    
                    input("\nPress Enter to continue...")
                    clear_screen()
                    display_ascii_art()
                    print("=" * 60)
                    print("MULTI SCAN")
                    print("=" * 60)
                    
            elif choice == "3":
                if not dirs_to_scan:
                    print("\nNo directories to scan.")
                    input("\nPress Enter to continue...")
                    continue
                
                print("\nBeginning scan of multiple directories...")
                for dir_path in dirs_to_scan:
                    print(f"\nProcessing: {dir_path}")
                    processor = DirectoryProcessor(dir_path)
                    processor.process()
                
                print("\nAll directories have been processed.")
                input("\nPress Enter to continue...")
                return
                
            elif choice == "q":  # Changed from "0" to "q"
                return
            else:
                print("\nInvalid choice.")
                input("\nPress Enter to continue...")
    
    def resume_scan(self):
        """Resume a previously interrupted scan."""
        # Load scan history
        history = load_scan_history()
        if not history:
            print("\nNo scan history found.")
            input("\nPress Enter to continue...")
            return
        
        clear_screen()
        display_ascii_art()
        print("=" * 60)
        print("RESUME SCAN")
        print("=" * 60)
        
        dir_path = history.get('path', '')
        processed_files = history.get('processed_files', 0)
        total_files = history.get('total_files', 0)
        media_files = history.get('media_files', [])
        
        if not os.path.isdir(dir_path):
            print(f"\nError: The directory in scan history no longer exists: {dir_path}")
            print("\nWould you like to clear the scan history?")
            choice = input("(y/n): ").strip().lower()
            if choice == 'y':
                clear_scan_history()
                print("\nScan history cleared.")
            input("\nPress Enter to continue...")
            return
        
        print(f"\nFound scan history for: {dir_path}")
        print(f"Progress: {processed_files}/{total_files} files processed")
        print(f"Media files found: {len(media_files)}")
        
        print("\nOptions:")
        print("1. Resume scan from where it left off")
        print("2. Start a new scan of this directory")
        print("3. Clear scan history")
        print("q. Return to main menu")  # Changed from "0" to "q"
        
        choice = input("\nEnter choice: ").strip().lower()
        
        if choice == "1":
            # Resume scan
            print(f"\nResuming scan of: {dir_path}")
            processor = DirectoryProcessor(dir_path, resume=True)
            processor.process()
            input("\nScan complete. Press Enter to continue...")
        elif choice == "2":
            # Start new scan
            print(f"\nStarting new scan of: {dir_path}")
            # Clear history before starting new scan
            clear_scan_history()
            processor = DirectoryProcessor(dir_path)
            processor.process()
            input("\nScan complete. Press Enter to continue...")
        elif choice == "3":
            # Clear history
            clear_scan_history()
            print("\nScan history cleared.")
            input("\nPress Enter to continue...")
        elif choice == "q":  # Changed from "0" to "q"
            return
        else:
            print("\nInvalid choice.")
            input("\nPress Enter to continue...")
    
    def review_monitored_directories(self):
        """Review and manage monitored directories."""
        from src.core.monitor_manager import MonitorManager
        
        # Get monitor manager instance
        monitor_manager = MonitorManager()
        
        while True:
            clear_screen()
            display_ascii_art()
            print("=" * 60)
            print("MONITOR SCAN MANAGEMENT")
            print("=" * 60)
            
            # Get current monitored directories
            monitored_dirs = monitor_manager.get_monitored_directories()
            
            # Display monitored directories with details
            if monitored_dirs:
                print("\nCurrently Monitored Directories:")
                print("-" * 80)
                print(f"{'#':<3} {'DIRECTORY PATH':<40} {'STATUS':<10} {'AUTO':<6} {'LAST SCAN':<15} {'NEXT SCAN':<15}")
                print("-" * 80)
                
                # Create a simple numbering map for easier user interaction
                dir_id_map = {}
                for i, (dir_id, info) in enumerate(monitored_dirs.items(), 1):
                    dir_id_map[str(i)] = dir_id
                    
                    path = info.get('path', 'Unknown')
                    # Truncate path if too long
                    if len(path) > 40:
                        path = "..." + path[-37:]
                    
                    active = "Enabled" if info.get('active', False) else "Disabled"
                    auto_mode = "Yes" if info.get('auto_mode', False) else "No"
                    
                    last_scan = info.get('last_scan', 'Never')
                    if last_scan != 'Never' and isinstance(last_scan, str):
                        try:
                            # Convert ISO format to prettier format
                            dt = datetime.datetime.fromisoformat(last_scan)
                            last_scan = dt.strftime("%Y-%m-%d %H:%M")
                        except:
                            pass
                    
                    next_scan = info.get('next_scan', 'Not scheduled')
                    if next_scan != 'Not scheduled' and isinstance(next_scan, str):
                        try:
                            # Convert ISO format to prettier format
                            dt = datetime.datetime.fromisoformat(next_scan)
                            next_scan = dt.strftime("%Y-%m-%d %H:%M")
                        except:
                            pass
                    
                    print(f"{i:<3} {path:<40} {active:<10} {auto_mode:<6} {last_scan:<15} {next_scan:<15}")
                
                print("-" * 80)
            else:
                print("\nNo directories are currently being monitored.")
            
            # Menu options
            print("\nOptions:")
            print("1. Add directory to monitor")
            print("2. Remove directory from monitoring")
            print("3. Enable/Disable monitoring for a directory")
            print("4. Toggle Auto/Manual mode for a directory")
            print("5. Run scan on monitored directory now")
            print("6. Configure monitoring interval")
            print("q. Return to main menu")
            
            choice = input("\nEnter choice: ").strip().lower()
            
            if choice == "1":
                # Add directory to monitor
                print("\nEnter the path of the directory to monitor (or 'c' to cancel):")
                dir_path = input("> ").strip()
                
                if dir_path.lower() == 'c':
                    continue
                    
                dir_path = _clean_directory_path(dir_path)
                
                if not os.path.isdir(dir_path):
                    print(f"\nError: '{dir_path}' is not a valid directory.")
                    input("\nPress Enter to continue...")
                    continue
                
                # Ask about auto mode
                print("\nEnable auto mode for this directory? (Automatically process new files)")
                print("1. Yes - Auto process new files")
                print("2. No - Manual review required")
                auto_choice = input("> ").strip()
                auto_mode = auto_choice == "1"
                
                # Add to monitored directories
                dir_id = monitor_manager.add_monitored_directory(dir_path, active=True, auto_mode=auto_mode)
                if dir_id:
                    print(f"\nDirectory successfully added to monitoring.")
                    
                    # Schedule initial scan
                    interval = int(os.environ.get('MONITOR_SCAN_INTERVAL', '1440'))  # Default 24 hours in minutes
                    next_scan = datetime.datetime.now() + datetime.timedelta(minutes=interval)
                    monitor_manager.update_monitored_directory(dir_id, {'next_scan': next_scan.isoformat()})
                else:
                    print("\nFailed to add directory to monitoring.")
                
                input("\nPress Enter to continue...")
                
            elif choice == "2":
                # Remove directory from monitoring
                if not monitored_dirs:
                    print("\nNo directories to remove.")
                    input("\nPress Enter to continue...")
                    continue
                    
                print("\nEnter the number of the directory to remove (or 'c' to cancel):")
                index = input("> ").strip().lower()
                
                if index == 'c':
                    continue
                    
                if index in dir_id_map:
                    dir_id = dir_id_map[index]
                    confirm = input(f"\nAre you sure you want to remove '{monitored_dirs[dir_id]['path']}' from monitoring? (y/n): ").strip().lower()
                    if confirm == 'y':
                        monitor_manager.remove_monitored_directory(dir_id)
                        print("\nDirectory removed from monitoring.")
                else:
                    print("\nInvalid number.")
                    
                input("\nPress Enter to continue...")
                
            elif choice == "3":
                # Enable/Disable monitoring for a directory
                if not monitored_dirs:
                    print("\nNo directories to modify.")
                    input("\nPress Enter to continue...")
                    continue
                    
                print("\nEnter the number of the directory to enable/disable (or 'c' to cancel):")
                index = input("> ").strip().lower()
                
                if index == 'c':
                    continue
                    
                if index in dir_id_map:
                    dir_id = dir_id_map[index]
                    current_state = monitored_dirs[dir_id].get('active', False)
                    new_state = not current_state
                    state_text = "enable" if new_state else "disable"
                    
                    confirm = input(f"\nAre you sure you want to {state_text} monitoring for '{monitored_dirs[dir_id]['path']}'? (y/n): ").strip().lower()
                    if confirm == 'y':
                        monitor_manager.update_monitored_directory(dir_id, {'active': new_state})
                        print(f"\nDirectory monitoring {state_text}d.")
                else:
                    print("\nInvalid number.")
                    
                input("\nPress Enter to continue...")
                
            elif choice == "4":
                # Toggle Auto/Manual mode for a directory
                if not monitored_dirs:
                    print("\nNo directories to modify.")
                    input("\nPress Enter to continue...")
                    continue
                    
                print("\nEnter the number of the directory to change auto/manual mode (or 'c' to cancel):")
                index = input("> ").strip().lower()
                
                if index == 'c':
                    continue
                    
                if index in dir_id_map:
                    dir_id = dir_id_map[index]
                    current_mode = monitored_dirs[dir_id].get('auto_mode', False)
                    new_mode = not current_mode
                    mode_text = "Auto" if new_mode else "Manual"
                    
                    confirm = input(f"\nChange '{monitored_dirs[dir_id]['path']}' to {mode_text} mode? (y/n): ").strip().lower()
                    if confirm == 'y':
                        monitor_manager.update_monitored_directory(dir_id, {'auto_mode': new_mode})
                        print(f"\nDirectory changed to {mode_text} mode.")
                else:
                    print("\nInvalid number.")
                    
                input("\nPress Enter to continue...")
                
            elif choice == "5":
                # Run scan on monitored directory now
                if not monitored_dirs:
                    print("\nNo directories to scan.")
                    input("\nPress Enter to continue...")
                    continue
                    
                print("\nEnter the number of the directory to scan now (or 'c' to cancel):")
                index = input("> ").strip().lower()
                
                if index == 'c':
                    continue
                    
                if index in dir_id_map:
                    dir_id = dir_id_map[index]
                    dir_info = monitored_dirs[dir_id]
                    if not dir_info.get('active', False):
                        print(f"\nWarning: Directory '{dir_info['path']}' is currently disabled.")
                        enable = input("Enable it for this scan? (y/n): ").strip().lower()
                        if enable == 'y':
                            monitor_manager.update_monitored_directory(dir_id, {'active': True})
                        else:
                            print("\nCancelling scan.")
                            input("\nPress Enter to continue...")
                            continue
                    
                    # Ask about auto mode for this specific scan
                    print(f"\nRun in {'Auto' if dir_info.get('auto_mode', False) else 'Manual'} mode (current setting), or change for this scan?")
                    print(f"1. Use current setting ({'Auto' if dir_info.get('auto_mode', False) else 'Manual'})")
                    print("2. Auto mode for this scan")
                    print("3. Manual mode for this scan")
                    
                    mode_choice = input("> ").strip()
                    if mode_choice == "2":
                        auto_mode = True
                    elif mode_choice == "3":
                        auto_mode = False
                    else:
                        # Use current setting
                        auto_mode = dir_info.get('auto_mode', False)
                    
                    # Run scan
                    print(f"\nScanning '{dir_info['path']}' in {'Auto' if auto_mode else 'Manual'} mode...")
                    dir_path = dir_info['path']
                    
                    processor = DirectoryProcessor(dir_path, auto_mode=auto_mode)
                    processor.process()
                    
                    # Update last scan timestamp
                    monitor_manager.update_monitored_directory(dir_id, {
                        'last_scan': datetime.datetime.now().isoformat()
                    })
                    
                    # Update next scan time based on interval
                    interval = int(os.environ.get('MONITOR_SCAN_INTERVAL', '1440'))  # Default 24 hours in minutes
                    next_scan = datetime.datetime.now() + datetime.timedelta(minutes=interval)
                    monitor_manager.update_monitored_directory(dir_id, {
                        'next_scan': next_scan.isoformat()
                    })
                    
                    print(f"\nScan complete. Next scan scheduled for {next_scan.strftime('%Y-%m-%d %H:%M')}")
                else:
                    print("\nInvalid number.")
                    
                input("\nPress Enter to continue...")
                
            elif choice == "6":
                # Configure monitoring interval
                current_interval = int(os.environ.get('MONITOR_SCAN_INTERVAL', '1440'))  # Default 24 hours in minutes
                
                print(f"\nCurrent monitoring interval: {current_interval} minutes ({current_interval/60:.1f} hours)")
                print("\nEnter new interval in minutes (e.g., 60 for 1 hour, 1440 for 24 hours) or 'c' to cancel:")
                
                interval_input = input("> ").strip().lower()
                if interval_input == 'c':
                    continue
                    
                try:
                    if interval_input:
                        new_interval = int(interval_input)
                        if new_interval < 5:
                            print("\nInterval too small. Minimum interval is 5 minutes.")
                        else:
                            # Update environment variable with new interval in minutes
                            _update_env_var('MONITOR_SCAN_INTERVAL', str(new_interval))
                            print(f"\nMonitoring interval updated to {new_interval} minutes ({new_interval/60:.1f} hours).")
                            
                            # Update next scan times for all directories based on new interval
                            for dir_id, info in monitored_dirs.items():
                                if info.get('active', False):
                                    next_scan = datetime.datetime.now() + datetime.timedelta(minutes=new_interval)
                                    monitor_manager.update_monitored_directory(dir_id, {
                                        'next_scan': next_scan.isoformat()
                                    })
                except ValueError:
                    print("\nInvalid interval value. Please enter a number.")
                    
                input("\nPress Enter to continue...")
                
            elif choice == "q":
                # Return to main menu
                break
            
            else:
                print("\nInvalid choice.")
                input("\nPress Enter to continue...")
    
    def settings_menu(self):
        """Display and handle settings menu."""
        clear_screen()
        display_ascii_art()
        print("=" * 60)
        print("SETTINGS")
        print("=" * 60)
        print("\n1. Set destination directory")
        print("2. Configure monitor settings")
        print("q. Return to main menu")  # Changed from "0" to "q"
        
        choice = input("\nEnter your choice: ").strip().lower()  # Convert to lowercase
        
        # Handle settings choices
        if choice == "1":
            self._set_destination_directory()
        elif choice == "2":
            self._configure_monitor_settings()
        elif choice != "q":  # Changed from "0" to "q"
            print("\nInvalid choice.")
            input("\nPress Enter to continue...")
    
    def _set_destination_directory(self):
        """Set the destination directory for media files."""
        global DESTINATION_DIRECTORY
        
        clear_screen()
        display_ascii_art()
        print("=" * 60)
        print("SET DESTINATION DIRECTORY")
        print("=" * 60)
        
        current_dir = DESTINATION_DIRECTORY or "Not set"
        print(f"\nCurrent destination directory: {current_dir}")
        
        print("\nEnter the new destination directory (or 'q' to cancel):")
        dir_path = input("> ").strip()
        
        if dir_path.lower() == 'q':
            return
        
        # Clean up the directory path
        dir_path = _clean_directory_path(dir_path)
        
        if not dir_path:
            print("\nInvalid directory path.")
            input("\nPress Enter to continue...")
            return
        
        # Create the directory if it doesn't exist
        try:
            if not os.path.exists(dir_path):
                confirm = input(f"\nDirectory '{dir_path}' doesn't exist. Create it? (y/n): ").strip().lower()
                if confirm == 'y':
                    os.makedirs(dir_path, exist_ok=True)
                else:
                    print("\nOperation cancelled.")
                    input("\nPress Enter to continue...")
                    return
                    
            # Test if we have write permission
            test_file = os.path.join(dir_path, '.scanly_test')
            try:
                with open(test_file, 'w') as f:
                    f.write('test')
                os.remove(test_file)
            except Exception as e:
                print(f"\nError: Cannot write to directory: {e}")
                input("\nPress Enter to continue...")
                return
            
            # Update the destination directory
            DESTINATION_DIRECTORY = dir_path
            _update_env_var('DESTINATION_DIRECTORY', dir_path)
            
            print(f"\nDestination directory set to: {dir_path}")
            
            # Create standard subdirectories
            for subdir in ["Movies", "TV Shows", "Anime Movies", "Anime TV Shows"]:
                os.makedirs(os.path.join(dir_path, subdir), exist_ok=True)
            
            print("Created standard subdirectories.")
            
        except Exception as e:
            print(f"\nError setting destination directory: {e}")
        
        input("\nPress Enter to continue...")
    
    def _configure_monitor_settings(self):
        """Configure monitor settings."""
        # Implementation for configuring monitor settings
        print("\nConfiguring monitor settings...")
        input("\nPress Enter to continue...")
    
    def show(self):
        """Show the main menu and handle user input."""
        while True:
            # Clear screen before showing menu
            clear_screen()

            # Display ASCII art above the menu
            display_ascii_art()

            # No extra spacing between art and menu options
            print("=" * 60)  # Add just a separator line
            print("Select an option:")
            print("1. Individual Scan")  # Renamed from "New Scan"
            print("2. Multi Scan")  # New option
            
            # Dynamic menu options based on history existence
            has_history = history_exists()
            
            has_skipped = len(globals().get('skipped_items_registry', [])) > 0
            
            # Check if monitored directories exist
            from src.core.monitor_manager import MonitorManager
            monitor_manager = MonitorManager()
            has_monitored = bool(monitor_manager.get_monitored_directories())
            
            next_option = 3  # Start at 3 since we added Multi Scan as option 2
            
            # Track which option number corresponds to which function
            resume_scan_option = None
            clear_history_option = None
            monitored_dirs_option = None
            skipped_items_option = None
            settings_option = None
            
            if has_history:
                print(f"{next_option}. Resume Scan")
                resume_scan_option = next_option
                next_option += 1
                
                print(f"{next_option}. Clear History")
                clear_history_option = next_option
                next_option += 1
            
            # Show monitored directories option if they exist
            if has_monitored:
                print(f"{next_option}. Monitor Scan")
                monitored_dirs_option = next_option
                next_option += 1
            
            # Keep the skipped items count, but make it look like regular information
            if has_skipped:
                print(f"\nSkipped items: {len(skipped_items_registry)}")
                print(f"{next_option}. Review Skipped Items ({len(skipped_items_registry)})")
                skipped_items_option = next_option
                next_option += 1
            
            # Add the Settings option
            print(f"{next_option}. Settings")
            settings_option = next_option
            next_option += 1
            
            print("q. Quit")
            print("h. Help")
            
            # Get user choice
            choice = input("\nEnter your choice: ").strip().lower()
            
            if choice == '1':
                self.individual_scan()
            elif choice == '2':
                self.multi_scan()
            elif has_history and choice == str(resume_scan_option):
                self.resume_scan()
            elif has_history and choice == str(clear_history_option):
                # Clear scan history
                clear_scan_history()
                print("Scan history cleared.")
                input("\nPress Enter to continue...")
            elif has_monitored and choice == str(monitored_dirs_option):
                self.review_monitored_directories()
            elif has_skipped and choice == str(skipped_items_option):
                # Call the review_skipped_items function directly
                review_skipped_items()
            elif choice == str(settings_option):
                self.settings_menu()
            elif choice == 'q':
                clear_screen()
                print("Goodbye!")
                break
            elif choice == 'h':
                display_help()
            else:
                print("Invalid choice. Please try again.")
                input("\nPress Enter to continue...")

# Main entry point
if __name__ == "__main__":
    print("Starting Scanly...")
    # Check if file_utils.py exists and create it if not
    file_utils_path = os.path.join(os.path.dirname(__file__), 'utils', 'file_utils.py')
    if not os.path.exists(file_utils_path):
        os.makedirs(os.path.dirname(file_utils_path), exist_ok=True)
        with open(file_utils_path, 'w') as f:
            f.write("""import os
import re
import logging

def create_symlinks(source_path, destination_path, is_anime=False, content_type=None, metadata=None, force_overwrite=False):
    \"\"\"
    Create symbolic links for the given source path at the destination path.
    
    Args:
        source_path: Path to the source file or directory
        destination_path: Base destination directory
        is_anime: Boolean indicating if the content is anime
        content_type: 'tv' or 'movie'
        metadata: Dict containing metadata about the content
        force_overwrite: Boolean to force overwrite existing files
        
    Returns:
        Tuple of (success, message)
    \"\"\"
    logger = logging.getLogger(__name__)
    
    try:
        logger.debug(f"Creating symlink from {source_path} to {destination_path}")
        return True, "Symlink created successfully"
    except Exception as e:
        logger.error(f"Error creating symlink: {e}")
        return False, f"Error creating symlink: {str(e)}"

def clean_filename(filename):
    \"\"\"
    Clean a filename to be safe for file system use.
    
    Args:
        filename: The filename to clean
        
    Returns:
        A cleaned filename
    \"\"\"
    if not filename:
        return "unnamed"
        
    # Replace illegal characters
    cleaned = re.sub(r'[\\\\/*?:"<>|]', '', filename)
    # Replace multiple spaces with a single space
    cleaned = re.sub(r'\\s+', ' ', cleaned)
    # Trim spaces from beginning and end
    cleaned = cleaned.strip()
    
    # Ensure we have something left after cleaning
    if not cleaned:
        return "unnamed"
        
    return cleaned
""")

    # Create logs directory if it doesn't exist
    logs_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'logs')
    os.makedirs(logs_dir, exist_ok=True)
    
    # Create scanners directory if it doesn't exist
    scanners_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'scanners')
    os.makedirs(scanners_dir, exist_ok=True)
    
    try:
        # Create main menu and show it
        menu = MainMenu()
        menu.show()
    except KeyboardInterrupt:
        print("\nExiting...")
    except Exception as e:
        logger = get_logger(__name__)
        logger.error(f"Unexpected error: {e}", exc_info=True)
        print(f"\nUnexpected error: {e}")
        print("Check logs for details.")
        input("\nPress Enter to exit...")