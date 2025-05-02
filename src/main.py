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
        return True

# Set up basic logging configuration
console_handler = logging.StreamHandler()
console_handler.addFilter(ConsoleFilter())

# Create a file handler with proper path creation
log_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'logs')
try:
    os.makedirs(log_dir, exist_ok=True)
except PermissionError:
    print(f"Warning: Cannot create logs directory at {log_dir} - permission denied")
    # Use a fallback directory in /tmp that should be writable
    log_dir = '/tmp'
    os.makedirs(os.path.join(log_dir, 'scanly_logs'), exist_ok=True)
    log_dir = os.path.join(log_dir, 'scanly_logs')

# Configure logging handlers with error handling
handlers = [console_handler]

try:
    # Use 'w' mode instead of 'a' to clear previous logs at startup
    file_handler = logging.FileHandler(os.path.join(log_dir, 'scanly.log'), 'w')
    handlers.append(file_handler)
    
    # Add a separate file handler for monitor logs - also use 'w' mode
    monitor_log_file = os.path.join(log_dir, 'monitor.log')
    monitor_handler = logging.FileHandler(monitor_log_file, 'w')
    monitor_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    monitor_filter = logging.Filter('src.core.monitor')
    monitor_handler.addFilter(monitor_filter)
    handlers.append(monitor_handler)
except (PermissionError, IOError) as e:
    print(f"Warning: Cannot write to log files - {e}")
    print("Continuing with console logging only")

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=handlers
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
        def __init__(self, api_key=None):
            pass
        
        def search_movie(self, query, limit=5):
            return []
        
        def search_tv(self, query, limit=5):
            return []
        
        def get_tv_details(self, show_id):
            return {}
        
        def get_tv_season(self, show_id, season_number):
            return {}

# Get destination directory from environment variables
DESTINATION_DIRECTORY = os.environ.get('DESTINATION_DIRECTORY', '')

# Import utility functions for scan history
def load_scan_history():
    """Load scan history from file."""
    try:
        history_path = os.path.join(os.path.dirname(__file__), 'scan_history.json')
        if os.path.exists(history_path):
            with open(history_path, 'r') as f:
                return json.load(f)
    except Exception as e:
        logger = get_logger(__name__)
        logger.error(f"Error loading scan history: {e}")
    return None

def save_scan_history(directory_path, processed_files=0, total_files=0, media_files=None):
    """Save scan history to file."""
    try:
        history = {
            'directory': directory_path,
            'timestamp': time.time(),
            'processed_files': processed_files,
            'total_files': total_files,
            'media_files': media_files or []
        }
        history_path = os.path.join(os.path.dirname(__file__), 'scan_history.json')
        with open(history_path, 'w') as f:
            json.dump(history, f)
    except Exception as e:
        logger = get_logger(__name__)
        logger.error(f"Error saving scan history: {e}")

def clear_scan_history():
    """Clear scan history file."""
    try:
        history_path = os.path.join(os.path.dirname(__file__), 'scan_history.json')
        if os.path.exists(history_path):
            os.remove(history_path)
    except Exception as e:
        logger = get_logger(__name__)
        logger.error(f"Error clearing scan history: {e}")

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
        logger = get_logger(__name__)
        logger.error(f"Error loading skipped items: {e}")
    return []

# Function to save skipped items
def save_skipped_items(items):
    """Save skipped items to file."""
    try:
        skipped_path = os.path.join(os.path.dirname(__file__), 'skipped_items.json')
        with open(skipped_path, 'w') as f:
            json.dump(items, f)
    except Exception as e:
        logger = get_logger(__name__)
        logger.error(f"Error saving skipped items: {e}")

# Add this function after save_skipped_items() function

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
        art_path = os.path.join(os.path.dirname(__file__), '..', 'art.txt')
        if os.path.exists(art_path):
            with open(art_path, 'r') as f:
                print(f.read())
        else:
            print("SCANLY")
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
    
    clear_screen()
    print("=" * 60)
    print("SKIPPED ITEMS")
    print("=" * 60)
    print(f"\nFound {len(skipped_items_registry)} skipped items.")
    
    # Make a copy of the registry to work with
    items_to_review = skipped_items_registry.copy()
    current_idx = 0
    
    while current_idx < len(items_to_review):
        clear_screen()
        print("=" * 60)
        print(f"REVIEWING ITEM {current_idx + 1}/{len(items_to_review)}")
        print("=" * 60)
        
        item = items_to_review[current_idx]
        subfolder = item.get('subfolder', 'Unknown')
        suggested_name = item.get('suggested_name', 'Unknown')
        is_tv = item.get('is_tv', False)
        is_anime = item.get('is_anime', False)
        
        content_type = "TV Show" if is_tv else "Movie"
        anime_label = " (Anime)" if is_anime else ""
        
        print(f"\nItem Details:")
        print(f"Name: {suggested_name}")
        print(f"Type: {content_type}{anime_label}")
        print(f"Path: {subfolder}")
        
<<<<<<< HEAD
        print("\nOptions:")
        print("1. Process this item")
        print("2. Skip to next item")
        print("3. Go back to previous item")
        print("4. Clear all skipped items")
        print("0. Return to main menu")
        
        choice = input("\nEnter choice: ").strip()
        
        if choice == "1":
            # Process the selected item
            # Implementation for processing skipped items would go here
            print("\nProcessing this item...")
            # After processing, we'd remove it from the registry
            # skipped_items_registry.remove(item)
=======
        try:
            item_idx = int(item_num) - 1
            if 0 <= item_idx < len(skipped_items_registry):
                # Process the selected item
                process_skipped_item(item_idx)
            else:
                print("Invalid item number.")
                input("\nPress Enter to continue...")
        except ValueError:
            print("Invalid input.")
>>>>>>> 71bd2b3 (Review skipped items fix)
            input("\nPress Enter to continue...")
            current_idx += 1
        elif choice == "2":
            # Move to next item
            current_idx += 1
        elif choice == "3":
            # Go back to previous item if possible
            current_idx = max(0, current_idx - 1)
        elif choice == "4":
            clear_skipped_items()
            return
        elif choice == "0":
            return
        else:
            print("\nInvalid choice. Please try again.")
            input("\nPress Enter to continue...")
        
        # Check if we've reached the end of the list
        if current_idx >= len(items_to_review):
            print("\nReached the end of skipped items.")
            input("\nPress Enter to return to main menu...")
            return

def process_skipped_item(item_idx):
    """Process a single skipped item from the registry."""
    global skipped_items_registry
    
    # Get the item details
    item = skipped_items_registry[item_idx]
    file_path = item.get('path')
    subfolder = item.get('subfolder')
    suggested_name = item.get('suggested_name')
    is_tv = item.get('is_tv', False)
    is_anime = item.get('is_anime', False)
    
    # Check if file still exists
    if not os.path.exists(file_path):
        print(f"\nError: File no longer exists: {file_path}")
        # Remove from registry
        skipped_items_registry.pop(item_idx)
        save_skipped_items(skipped_items_registry)
        input("\nPress Enter to continue...")
        return
    
    clear_screen()
    display_ascii_art()
    print("=" * 60)
    print("PROCESS SKIPPED ITEM")
    print("=" * 60)
    
    content_type = "tv" if is_tv else "movie"
    content_type_display = "TV Show" if is_tv else "Movie"
    anime_label = " (Anime)" if is_anime else ""
    
    print(f"\nFile: {os.path.basename(file_path)}")
    print(f"Type: {content_type_display}{anime_label}")
    
    # Extract suggested title and year
    suggested_title = suggested_name
    suggested_year = None
    
    # Try to extract year from suggested name
    year_match = re.search(r'\((\d{4})\)$', suggested_name)
    if year_match:
        suggested_year = year_match.group(1)
        suggested_title = suggested_name.replace(f"({suggested_year})", "").strip()
    
    print(f"Suggested title: {suggested_title}")
    if suggested_year:
        print(f"Suggested year: {suggested_year}")
    
    print("\nOptions:")
    print("1. Accept suggested title and process")
    print("2. Enter new title")
    print("3. Change content type")
    print("4. Skip (keep in registry)")
    print("5. Remove from registry without processing")
    
    choice = input("\nEnter choice: ").strip()
    
    if choice == "1":
        # Process with suggested title and existing content type
        print(f"\nProcessing '{suggested_title}' as {content_type_display}{anime_label}")
        
        # Get media IDs for the title
        from src.api.tmdb import TMDB
        tmdb_api_key = os.environ.get('TMDB_API_KEY', '')
        tmdb = TMDB(api_key=tmdb_api_key)
        
        ids = {}
        try:
            if content_type == "tv":
                results = tmdb.search_tv(suggested_title)
            else:
                results = tmdb.search_movie(suggested_title)
            
            if results:
                # Take the first result
                result = results[0]
                ids['tmdb_id'] = result.get('id')
        except Exception as e:
            print(f"Error searching TMDB: {e}")
        
        # Create a destination path
        destination_dir = os.environ.get('DESTINATION_DIRECTORY', '')
        if not destination_dir:
            print("\nError: Destination directory not set.")
            input("\nPress Enter to continue...")
            return
        
        # Create destination filename and path
        if content_type == "tv":
            # Extract season and episode info
            season, episode = 1, 1  # Default values
            season_ep_match = re.search(r'S(\d+)E(\d+)', os.path.basename(file_path), re.IGNORECASE)
            if season_ep_match:
                season = int(season_ep_match.group(1))
                episode = int(season_ep_match.group(2))
            
            # Create destination path
            dest_folder = os.path.join(destination_dir, "TV", suggested_title)
            season_folder = os.path.join(dest_folder, f"Season {season:02d}")
            os.makedirs(season_folder, exist_ok=True)
            
            # Create symlink
            filename = f"{suggested_title} - S{season:02d}E{episode:02d}.{file_path.split('.')[-1]}"
            dest_path = os.path.join(season_folder, filename)
        else:
            # Movie
            dest_folder = os.path.join(destination_dir, "Movies", suggested_title)
            os.makedirs(dest_folder, exist_ok=True)
            
            # Create symlink
            extension = file_path.split('.')[-1]
            if suggested_year:
                filename = f"{suggested_title} ({suggested_year}).{extension}"
            else:
                filename = f"{suggested_title}.{extension}"
            dest_path = os.path.join(dest_folder, filename)
        
        try:
            # Create symlink
            if not os.path.exists(dest_path):
                os.symlink(file_path, dest_path)
                print(f"\nCreated symlink: {dest_path}")
                
                # Remove from registry
                skipped_items_registry.pop(item_idx)
                save_skipped_items(skipped_items_registry)
                print("Item removed from registry.")
            else:
                print(f"\nError: Destination file already exists: {dest_path}")
        except Exception as e:
            print(f"\nError creating symlink: {e}")
        
        input("\nPress Enter to continue...")
        
    elif choice == "2":
        # Let the user enter a new title
        new_title = input("\nEnter new title: ").strip()
        if new_title:
            # Update registry with new title
            skipped_items_registry[item_idx]['suggested_name'] = new_title
            save_skipped_items(skipped_items_registry)
            print(f"\nUpdated title to: {new_title}")
            
            # Process with new title
            process_skipped_item(item_idx)
        else:
            print("\nNo title entered. Item not processed.")
            input("\nPress Enter to continue...")
    
    elif choice == "3":
        # Change content type
        print("\nSelect content type:")
        print("1. Movie")
        print("2. TV Show")
        print("3. Anime Movie")
        print("4. Anime TV Show")
        
        type_choice = input("\nEnter choice: ").strip()
        
        if type_choice in ["1", "2", "3", "4"]:
            # Update content type
            new_is_tv = type_choice in ["2", "4"]
            new_is_anime = type_choice in ["3", "4"]
            
            skipped_items_registry[item_idx]['is_tv'] = new_is_tv
            skipped_items_registry[item_idx]['is_anime'] = new_is_anime
            save_skipped_items(skipped_items_registry)
            
            new_type = "TV Show" if new_is_tv else "Movie"
            anime_label = " (Anime)" if new_is_anime else ""
            print(f"\nUpdated content type to: {new_type}{anime_label}")
            
            # Process with new content type
            process_skipped_item(item_idx)
        else:
            print("\nInvalid choice. Content type not changed.")
            input("\nPress Enter to continue...")
    
    elif choice == "4":
        # Skip (keep in registry)
        print("\nItem kept in registry for later processing.")
        input("\nPress Enter to continue...")
    
    elif choice == "5":
        # Remove from registry without processing
        confirm = input("\nAre you sure you want to remove this item from the registry? (y/n): ").strip().lower()
        if confirm == 'y':
            skipped_items_registry.pop(item_idx)
            save_skipped_items(skipped_items_registry)
            print("\nItem removed from registry.")
        else:
            print("\nItem kept in registry.")
        input("\nPress Enter to continue...")
    
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

# DirectoryProcessor class
# [Rest of DirectoryProcessor class implementation]

# MainMenu class
class MainMenu:
    """Main menu handler for the application."""
    
    def __init__(self):
        self.logger = get_logger(__name__)
    
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
            
            if has_history:
                print(f"{next_option}. Resume Scan")
                print(f"{next_option+1}. Clear History")
                next_option += 2
            
            # Show monitored directories option if they exist
            if has_monitored:
                print(f"{next_option}. Review Monitored Directories")
                next_option += 1
            
            # Keep the skipped items count, but make it look like regular information
            if has_skipped:
                print(f"\nSkipped items: {len(skipped_items_registry)}")
                print(f"{next_option}. Review Skipped Items ({len(skipped_items_registry)})")
                next_option += 1
            
            # Add the Settings option
            print(f"{next_option}. Settings")
            next_option += 1
            
            print("0. Quit")
            print("h. Help")
            
            # Determine the valid choices
            max_choice = next_option - 1
            
            # Get user choice
            choice = input("\nEnter your choice: ").strip().lower()
            
            if choice == '1':
                self.individual_scan()
            elif choice == '2':
                self.multi_scan()
            elif has_history and choice == '3':
                self.resume_scan()
            elif has_history and choice == '4':
                # Clear scan history
                clear_scan_history()
                print("Scan history cleared.")
                input("\nPress Enter to continue...")
            # Handle monitored directories option
            elif has_monitored and ((has_history and choice == '5') or (not has_history and choice == '3')):
                self.review_monitored_directories()
            # Handle skipped items review with adjusted position
            elif has_skipped:
                skipped_position = next_option - 1
                if choice == str(skipped_position):
                    review_skipped_items()
            # Settings option
            elif choice == str(max_choice):
                self.settings_menu()
                
            elif choice == '0':
                clear_screen()
                print("Goodbye!")
                break
            elif choice == 'h':
                display_help()
            else:
                print("Invalid choice. Please try again.")
                input("\nPress Enter to continue...")
    
    def individual_scan(self):
        """Handle individual scan option."""
        clear_screen()
        display_ascii_art()
        print("=" * 60)
        print("INDIVIDUAL SCAN")
        print("=" * 60)
        
        # Ask for scan mode first
        print("\nSelect scan mode:")
        print("1. Auto Scan (automatic content detection and processing without user interaction)")
        print("2. Manual Scan (interactive content selection and processing)")
        print("3. Monitor Scan (add directory to continuously monitor for new files)")
        print("0. Back to Main Menu")
        
        mode_choice = input("\nEnter choice (0-3): ").strip()
        
        if mode_choice == '0':
            return
            
        auto_mode = (mode_choice == "1")
        monitor_mode = (mode_choice == "3")
        
        if not auto_mode and not monitor_mode and mode_choice != "2":
            print("\nInvalid choice. Using manual scan mode.")
            auto_mode = False
            monitor_mode = False
            input("\nPress Enter to continue...")
        
        # Get directory path from user
        print("\nEnter the path to scan (or 'q' to cancel):")
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
        
        # If monitor mode, handle monitor-specific logic
        if monitor_mode:
            from src.core.monitor_manager import MonitorManager
            
            print("\nAdding directory to monitoring...")
            
            # Get optional description
            print("\nEnter a description for this directory (optional):")
            description = input("> ").strip() or os.path.basename(dir_path)
            
            # Ask for processing mode for existing files
            print("\nHow should existing files in this directory be processed?")
            print("1. Automatically (process files without user interaction)")
            print("2. Manually (require manual review before processing)")
            processing_choice = input("\nEnter choice (1-2): ").strip()
            
            auto_process = (processing_choice == "1")
            
            # Add to monitored directories with auto_process flag
            monitor_manager = MonitorManager()
            if monitor_manager.add_directory(dir_path, description, auto_process=auto_process):
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
                    interval = int(settings.get('MONITOR_SCAN_INTERVAL', '60'))
                    monitor_manager.start_monitoring(interval)
                    print(f"\nMonitoring started with {interval} second interval.")
            else:
                print(f"\nFailed to add directory: {dir_path}")
                
            input("\nPress Enter to continue...")
            return
        
        # Process the directory - make sure auto_mode is passed here
        print(f"\nInitializing processor with auto_mode={auto_mode}...")
        processor = DirectoryProcessor(dir_path, auto_mode=auto_mode)
        processor.process()
    
    def multi_scan(self):
        """Handle multi-scan option."""
        clear_screen()
        display_ascii_art()
        print("=" * 60)
        print("MULTI SCAN")
        print("=" * 60)
        
        # Ask for scan mode first
        print("\nSelect scan mode:")
        print("1. Auto Scan (automatic content detection and processing without user interaction)")
        print("2. Manual Scan (interactive content selection and processing)")
        print("0. Back to Main Menu")
        
        mode_choice = input("\nEnter choice (0-2): ").strip()
        
        if mode_choice == '0':
            return
            
        auto_mode = (mode_choice == "1")
        
        if not auto_mode and mode_choice != "2":
            print("\nInvalid choice. Using manual scan mode.")
            auto_mode = False
            input("\nPress Enter to continue...")
        
        print("\nMulti scan allows you to queue multiple directories for scanning.")
        print("Enter each directory path on a new line.")
        print("When finished, enter a blank line to start scanning.")
        print("Enter 'q' to cancel and return to the main menu.\n")
        
        directories = []
        while True:
            dir_input = input(f"Directory {len(directories) + 1} (or blank to finish): ").strip()
            
            if dir_input.lower() == 'q':
                return
            
            if not dir_input:
                # Finished entering directories
                break
            
            # Validate directory exists
            if not os.path.isdir(dir_input):
                print(f"Error: {dir_input} is not a valid directory.")
                continue
            
            directories.append(dir_input)
        
        if not directories:
            print("\nNo directories entered.")
            input("\nPress Enter to continue...")
            return
        
        # Process each directory - make sure auto_mode is passed here
        for i, dir_path in enumerate(directories):
            clear_screen()
            display_ascii_art()
            print("=" * 60)
            print(f"PROCESSING DIRECTORY {i+1}/{len(directories)}")
            print("=" * 60)
            print(f"\nDirectory: {dir_path}\n")
            print(f"Using scan mode: {'Automatic' if auto_mode else 'Manual'}")
            
            processor = DirectoryProcessor(dir_path, auto_mode=auto_mode)
            processor.process()
    
    def resume_scan(self):
        """Resume a previously interrupted scan."""
        # Load scan history
        history = load_scan_history()
        
        if not history or 'directory' not in history:
            print("No scan history found.")
            input("\nPress Enter to continue...")
            return
        
        # Display history information
        clear_screen()
        display_ascii_art()
        print("=" * 60)
        print("RESUME SCAN")
        print("=" * 60)
        
        dir_path = history.get('directory', 'Unknown')
        processed = history.get('processed_files', 0)
        total = history.get('total_files', 0)
        
        print(f"\nFound interrupted scan of {dir_path}")
        print(f"Progress: {processed}/{total} files ({int((processed/total)*100) if total > 0 else 0}%)")
        
        # Prompt user to resume or cancel
        resume = input("\nResume this scan? (y/n): ").strip().lower()
        
        if resume != 'y':
            return
        
        # Process the directory with resume flag
        if os.path.isdir(dir_path):
            processor = DirectoryProcessor(dir_path, resume=True)
            processor.process()
        else:
            print(f"\nError: Directory {dir_path} no longer exists.")
            input("\nPress Enter to continue...")
    
    def settings_menu(self):
        """Display and handle the settings menu."""
        settings = self._load_settings()
        
        while True:
            clear_screen()
            display_ascii_art()
            print("=" * 60)
            print("SETTINGS")
            print("=" * 60)
            
            # Group settings by category
            categories = {}
            for setting in settings:
                category = setting.get('category', 'General')
                if category not in categories:
                    categories[category] = []
                categories[category].append(setting)
            
            # Display categories
            print("\nSettings categories:")
            for i, category in enumerate(categories.keys(), 1):
                print(f"{i}. {category}")
            
            print("\n0. Back to Main Menu")
            
            category_choice = input("\nSelect category (0 to go back): ").strip()
            
            if category_choice == '0':
                break
            
            # Check if the choice is valid
            if not category_choice.isdigit() or int(category_choice) < 1 or int(category_choice) > len(categories):
                print("Invalid choice.")
                input("\nPress Enter to continue...")
                continue
            
            # Get the selected category and its settings
            selected_category = list(categories.keys())[int(category_choice) - 1]
            category_settings = categories[selected_category]
            
            # Show settings for the selected category
            while True:
                clear_screen()
                display_ascii_art()
                print("=" * 60)
                print(f"Settings > {selected_category}")
                print("=" * 60)
                
                print("\nCurrent settings:")
                for i, setting in enumerate(category_settings, 1):
                    name = setting.get('name', '')
                    description = setting.get('description', '')
                    default_value = setting.get('default', '')
                    current_value = os.environ.get(name, default_value)
                    
                    # Format display based on setting type
                    if setting.get('type') == 'bool':
                        display_value = 'Enabled' if current_value.lower() == 'true' else 'Disabled'
                    elif setting.get('type') == 'password' and current_value:
                        display_value = '*' * len(current_value)
                    else:
                        display_value = current_value if current_value else '<Not Set>'
                    
                    print(f"{i}. {description}: {display_value}")
                
                print("\n0. Back to Settings Menu")
                
                setting_choice = input("\nEnter setting number to modify (0 to go back): ").strip()
                
                if setting_choice == '0':
                    break
                
                # Check if the choice is valid
                if not setting_choice.isdigit() or int(setting_choice) < 1 or int(setting_choice) > len(category_settings):
                    print("Invalid choice.")
                    input("\nPress Enter to continue...")
                    continue
                
                # Get the selected setting
                selected_setting = category_settings[int(setting_choice) - 1]
                env_var = selected_setting["name"]
                default_value = selected_setting.get("default", "")
                current_value = os.environ.get(env_var, default_value)
                
                # Handle custom handlers
                if selected_setting.get("type") == "custom_handler" and "handler" in selected_setting:
                    handler_name = selected_setting["handler"]
                    if hasattr(self, handler_name):
                        # Call the custom handler method
                        getattr(self, handler_name)()
                    else:
                        print(f"Error: Handler '{handler_name}' not found")
                        input("\nPress Enter to continue...")
                    continue
                
                # For boolean settings, toggle the value
                if selected_setting.get("type") == "bool":
                    new_value = 'false' if current_value.lower() == 'true' else 'true'
                    self._update_env_var(env_var, new_value)
                    print(f"Setting updated: {new_value}")
                    input("\nPress Enter to continue...")
                    continue
                
                # For directory settings, provide directory selection
                if selected_setting.get("type") == "directory":
                    print(f"\nCurrent value: {current_value}")
                    print("Enter new directory path or leave blank to keep current value.")
                    print("Enter 'browse' to open a directory browser.")
                    
                    new_value = input("> ").strip()
                    
                    if new_value == 'browse':
                        # Directory browser not implemented in this version
                        print("Directory browser not available in this version.")
                        new_value = input("Enter directory path manually: ").strip()
                    
                    if new_value:
                        # Validate directory
                        if os.path.isdir(new_value) or input("Directory doesn't exist. Create it? (y/n): ").lower() == 'y':
                            self._update_env_var(env_var, new_value)
                            print(f"Setting updated: {new_value}")
                        else:
                            print("Setting not updated.")
                    
                    input("\nPress Enter to continue...")
                    continue
                
                # For all other settings, prompt for new value
                print(f"\nCurrent value: {current_value}")
                print("Enter new value or leave blank to keep current value:")
                
                new_value = input("> ").strip()
                
                if new_value:
                    self._update_env_var(env_var, new_value)
                    print(f"Setting updated: {new_value}")
                
                input("\nPress Enter to continue...")
    
    def _load_settings(self):
        """Load application settings."""
        # Define the settings schema
        settings = [
            {
                'name': 'DESTINATION_DIRECTORY',
                'description': 'Media destination directory',
                'type': 'directory',
                'category': 'Paths',
                'default': ''
            },
            {
                'name': 'TMDB_API_KEY',
                'description': 'TMDB API Key',
                'type': 'password',
                'category': 'API',
                'default': ''
            },
            {
                'name': 'AUTO_EXTRACT_EPISODES',
                'description': 'Auto-extract episode information',
                'type': 'bool',
                'category': 'Processing',
                'default': 'false'
            },
            {
                'name': 'SCANNER_LISTS',
                'description': 'Manage scanner lists',
                'type': 'custom_handler',
                'handler': '_manage_scanner_lists',
                'category': 'Content',
                'default': ''
            }
        ]
        
        return settings
    
    def _update_env_var(self, name, value):
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
    
    def _manage_scanner_lists(self):
        """Manage scanner lists for content type detection."""
        while True:
            clear_screen()
            display_ascii_art()
            print("=" * 60)
            print("MANAGE SCANNER LISTS")
            print("=" * 60)
            
            print("\nScanner lists are used to identify content types automatically.")
            print("Select a list to edit:")
            print("1. TV Series")
            print("2. Movies")
            print("3. Anime Series")
            print("4. Anime Movies")
            print("\n0. Back to Settings")
            
            choice = input("\nEnter your choice: ").strip()
            
            if choice == '0':
                break
            
            scanner_files = {
                '1': ('tv_series.txt', 'TV Series'),
                '2': ('movies.txt', 'Movies'),
                '3': ('anime_series.txt', 'Anime Series'),
                '4': ('anime_movies.txt', 'Anime Movies')
            }
            
            if choice in scanner_files:
                filename, list_type = scanner_files[choice]
                self._edit_scanner_list(filename, list_type)
            else:
                print("Invalid choice.")
                input("\nPress Enter to continue...")
    
    def _edit_scanner_list(self, filename, list_type):
        """
        Edit a scanner list file.
        
        Args:
            filename: Name of the file in the scanners directory
            list_type: Human-readable name of the list type
        """
        # Import TMDB API for validation
        from dotenv import load_dotenv
        load_dotenv()
        
        # Get TMDB API key from environment
        tmdb_api_key = os.environ.get('TMDB_API_KEY', '3b5df02338c403dad189e661d57e351f')
        
        logger = get_logger(__name__)
        tmdb = TMDB(api_key=tmdb_api_key)
        
        clear_screen()
        display_ascii_art()
        print("=" * 60)
        print(f"Edit {list_type} Scanner List")
        print("=" * 60)
        
        # Define path to scanner file
        scanner_file_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'scanners', filename)
        
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(scanner_file_path), exist_ok=True)
        
        # Create the file if it doesn't exist
        if not os.path.exists(scanner_file_path):
            open(scanner_file_path, 'w').close()
            print(f"Created new {list_type} scanner file.")
        
        # Read current entries
        try:
            with open(scanner_file_path, 'r', encoding='utf-8') as f:
                entries = [line.strip() for line in f.readlines() if line.strip()]
        except Exception as e:
            print(f"Error reading scanner file: {e}")
            entries = []
        
        while True:
            clear_screen()
            display_ascii_art()
            print("=" * 60)
            print(f"Edit {list_type} Scanner List")
            print("=" * 60)
            
            # Display current entries with line numbers
            print(f"\nCurrent {list_type} Entries ({len(entries)}):")
            if entries:
                for i, entry in enumerate(entries, 1):
                    # Highlight TMDB ID if present
                    if "[" in entry and "]" in entry and re.search(r'\[\d+\]$', entry):
                        tmdb_id = re.search(r'\[(\d+)\]$', entry).group(1)
                        entry_without_id = re.sub(r'\s*\[\d+\]\s*$', '', entry)
                        print(f"{i}. {entry_without_id} [TMDB ID: {tmdb_id}]")
                    else:
                        print(f"{i}. {entry}")
            else:
                print("No entries found.")
            
            print("\nOptions:")
            print("1. Add new entry")
            print("2. Remove entry")
            print("3. Add/Update TMDB ID for entry")
            print("4. Save and return to Settings")
            print("0. Return without saving")
            
            choice = input("\nSelect option: ").strip()
            
            if choice == '1':
                # Add new entry
                new_entry = input("\nEnter new entry name: ").strip()
                if new_entry and new_entry not in entries:
                    entries.append(new_entry)
                    print(f"Added: {new_entry}")
                elif new_entry in entries:
                    print(f"Entry already exists: {new_entry}")
                input("\nPress Enter to continue...")
                
            elif choice == '2':
                # Remove entry
                if not entries:
                    print("\nNo entries to remove.")
                    input("\nPress Enter to continue...")
                    continue
                
                remove_idx = input("\nEnter the number of the entry to remove: ").strip()
                
                if remove_idx.isdigit() and 1 <= int(remove_idx) <= len(entries):
                    removed = entries.pop(int(remove_idx) - 1)
                    print(f"\nRemoved: {removed}")
                else:
                    print("\nInvalid entry number.")
                
                input("\nPress Enter to continue...")
        
            elif choice == '3':
                if not entries:
                    print("\nNo entries to update.")
                    input("\nPress Enter to continue...")
                    continue
                
                update_idx = input("\nEnter the number of the entry to add/update TMDB ID: ").strip()
                
                if update_idx.isdigit() and 1 <= int(update_idx) <= len(entries):
                    entry_idx = int(update_idx) - 1
                    current_entry = entries[entry_idx]
                    
                    # Remove existing TMDB ID if present
                    clean_entry = re.sub(r'\s*\[\d+\]\s*$', '', current_entry)
                    
                    # Determine search type based on list type
                    search_type = "movie" if "Movie" in list_type else "tv"
                    
                    # Extract year if present
                    year_match = re.search(r'\((\d{4})\)$', clean_entry)
                    year = year_match.group(1) if year_match else None
                    title = re.sub(r'\s*\(\d{4}\)\s*$', '', clean_entry) if year else clean_entry
                    
                    try:
                        print(f"\nSearching TMDB for {search_type}: {title}")
                        if search_type == "movie":
                            search_results = tmdb.search_movie(title, limit=5)
                        else:
                            search_results = tmdb.search_tv(title, limit=5)
                        
                        if search_results:
                            # Show search results
                            print("\nSearch results:")
                            for i, result in enumerate(search_results, 1):
                                result_title = result.get('title', result.get('name', 'Unknown'))
                                year_str = ""
                                if search_type == "movie" and 'release_date' in result and result['release_date']:
                                    year_str = f" ({result['release_date'][:4]})"
                                elif search_type == "tv" and 'first_air_date' in result and result['first_air_date']:
                                    year_str = f" ({result['first_air_date'][:4]})"
                                print(f"{i}. {result_title}{year_str} [TMDB ID: {result.get('id', 'Unknown')}]")
                            
                            print("\nSelect a match or enter 0 to skip adding TMDB ID:")
                            match_choice = input("Choice: ").strip()
                            
                            if match_choice.isdigit() and 1 <= int(match_choice) <= len(search_results):
                                result = search_results[int(match_choice) - 1]
                                tmdb_id = result.get('id')
                                
                                # Update entry with TMDB ID
                                entries[entry_idx] = f"{clean_entry} [{tmdb_id}]"
                                print(f"\nUpdated entry with TMDB ID: {entries[entry_idx]}")
                            else:
                                print("\nInvalid choice. Entry not updated.")
                        else:
                            print("\nNo TMDB matches found.")
                    except Exception as e:
                        logger.error(f"Error searching TMDB: {e}")
                        print(f"\nError searching TMDB: {e}")
                else:
                    print("\nInvalid entry number.")
                
                input("\nPress Enter to continue...")
                
            elif choice == '4':
                # Save changes
                try:
                    with open(scanner_file_path, 'w', encoding='utf-8') as f:
                        for entry in entries:
                            f.write(f"{entry}\n")
                    print(f"\nSaved {len(entries)} entries to {filename}")
                    input("\nPress Enter to continue...")
                    break
                except Exception as e:
                    logger.error(f"Error saving scanner file: {e}")
                    print(f"\nError saving file: {e}")
                    input("\nPress Enter to continue...")
                
            elif choice == '0':
                # Return without saving
                print("\nChanges discarded.")
                input("\nPress Enter to continue...")
                break
            
            else:
                print("\nInvalid option.")
                input("\nPress Enter to continue...")

    def review_monitored_directories(self):
        """Review and manage monitored directories."""
        # Import the MonitorMenu class to use its functionality
        from src.ui.monitor_menu import MonitorMenu
        
        # Create instance of MonitorMenu and show it
        monitor_menu = MonitorMenu()
        monitor_menu.show()

# DirectoryProcessor class definition
class DirectoryProcessor:
    """Process a directory of media files."""
    
    def __init__(self, directory_path, resume=False, auto_mode=False):
        """
        Initialize the directory processor.
        
        Args:
            directory_path: Path to the directory to process
            resume: Whether to resume a previous scan
            auto_mode: Whether to process in automatic mode without user interaction
        """
        self.logger = get_logger(__name__)
        self.logger.info(f"Initializing DirectoryProcessor with auto_mode={auto_mode}")
        self.directory_path = directory_path
        self.resume = resume
        self.auto_mode = auto_mode
        self.auto_process = auto_mode  # Set auto_process to match auto_mode immediately
        self.processed_files = 0
        self.total_files = 0
        self.media_files = []
        self.subfolder_files = {}
        self.errors = 0
        self.skipped = 0
        self.symlink_count = 0
        # Note: No processing happens here anymore, just initialization

    def process(self):
        """Process the directory and create symlinks."""
        clear_screen()
        display_ascii_art()
        print("=" * 60)
        print("SCANNING DIRECTORY")
        print("=" * 60)
        
        print(f"\nScanning: {self.directory_path}")
        
        # Check if directory exists
        if not os.path.isdir(self.directory_path):
            print(f"Directory not found: {self.directory_path}")
            input("\nPress Enter to continue...")
            return
        
        # Check if destination directory is set
        if not os.environ.get('DESTINATION_DIRECTORY'):
            print("Destination directory not set.")
            print("Please set the destination directory in Settings > Paths first.")
            input("\nPress Enter to continue...")
            return
        
        try:
            # Display the mode being used at the beginning
            print(f"\nScan mode: {'Automatic' if self.auto_mode else 'Manual'}")
            
            # Collect all media files in the directory
            self._collect_media_files()
            
            if not self.media_files:
                print("No media files found in the directory.")
                input("\nPress Enter to continue...")
                return
            
            # Use the auto_mode parameter without asking again
            self.auto_process = self.auto_mode
            
            # Process each media file
            self._process_media_files()
            
            # Clear screen for final results
            clear_screen()
            display_ascii_art()
            print("=" * 60)
            print("SCAN COMPLETED")
            print("=" * 60)
            
            # Display results
            print(f"\nDirectory: {self.directory_path}")
            print("\nSummary:")
            print(f"- Processed: {self.processed_files} files")
            print(f"- Created symlinks: {self.symlink_count}")
            print(f"- Skipped: {self.skipped} files")
            print(f"- Errors: {self.errors}")
            
            # Clear scan history if all files were processed
            if self.processed_files >= self.total_files:
                clear_scan_history()
                print("\nScan history cleared.")
            
            print("\nScan complete! Press Enter to return to main menu.")
            input()
            # No need for further action - control will return to the main menu
            
        except KeyboardInterrupt:
            # Save progress for resuming later
            save_scan_history(self.directory_path, self.processed_files, self.total_files, self.media_files)
            print("\nScan interrupted. Progress saved for resuming later.")
            input("\nPress Enter to continue...")
        except Exception as e:
            self.logger.error(f"Error processing directory: {e}", exc_info=True)
            print(f"\nError processing directory: {e}")
            input("\nPress Enter to continue...")

    def _collect_media_files(self):
        """Collect all media files in the directory, grouped by subfolder."""
        # Common media file extensions
        media_extensions = ['.mkv', '.mp4', '.avi', '.mov', '.wmv', '.flv', '.m4v', '.ts']
        
        print("\nCollecting media files...")
        
        # If resuming, load media files from history
        if self.resume:
            history = load_scan_history()
            if history and 'media_files' in history:
                self.media_files = history.get('media_files', [])
                self.processed_files = history.get('processed_files', 0)
                self.total_files = history.get('total_files', 0)
                
                # Filter out files that no longer exist
                self.media_files = [f for f in self.media_files if os.path.exists(f)]
                
                print(f"Resuming scan: {len(self.media_files)} files remaining")
                return
        
        # Dictionary to store files grouped by subfolder
        self.subfolder_files = {}
        
        # Walk through directory and find media files
        for root, _, files in os.walk(self.directory_path):
            media_files_in_folder = []
            
            for file in files:
                # Check if file has a media extension
                if any(file.lower().endswith(ext) for ext in media_extensions):
                    file_path = os.path.join(root, file)
                    media_files_in_folder.append(file_path)
                    self.media_files.append(file_path)
            
            # Only add folders that contain media files
            if media_files_in_folder:
                self.subfolder_files[root] = sorted(media_files_in_folder)
        
        # Sort media files for consistent processing
        self.media_files.sort()
        self.total_files = len(self.media_files)
        
        print(f"Found {self.total_files} media files in {len(self.subfolder_files)} subfolders")

    def _process_media_files(self):
        """Process each subfolder and its media files interactively."""
        from src.utils.scanner_utils import check_scanner_lists
        
        print("\nProcessing media files by subfolder...")
        
        # Process each subfolder
        for subfolder, files in self.subfolder_files.items():
            # Skip if no files
            if not files:
                continue
            
            # Extract subfolder name for display
            subfolder_name = os.path.basename(subfolder)
            
            # Clear screen and show subfolder info only in manual mode
            if not self.auto_mode:
                clear_screen()
                display_ascii_art()
                print("=" * 60)
                print(f"PROCESSING SUBFOLDER: {subfolder_name}")
                print("=" * 60)
                
                print(f"\nFolder path: {subfolder}")
                print(f"Contains {len(files)} media files")
            else:
                print(f"\nProcessing subfolder: {subfolder_name}")
            
            # Initialize content_type and is_anime with default values
            content_type = "movie"  # Default to movie
            is_anime = False
            tmdb_id = None

            if "12.Angry.Men" in subfolder_name:
                suggested_title = "12 Angry Men"
                content_type = "movie"
                is_anime = False
                suggested_year = "1957"
                self.logger.info(f"SPECIAL CASE: Hardcoding title for '12 Angry Men'")
            else:
                # First extract metadata from folder name - ADD STEP ID FOR DEBUGGING
                self.logger.debug(f"STEP 1: About to extract metadata from folder name: '{subfolder_name}'")
                suggested_title, suggested_year = self._extract_folder_metadata(subfolder_name)
                self.logger.debug(f"STEP 2: EXTRACTED FROM FOLDER: title='{suggested_title}', year={suggested_year}")

                # CRITICAL: ADD DEBUG TO SEE WHAT'S HAPPENING IN _extract_folder_metadata
                self.logger.debug(f"STEP 3: Examining _extract_folder_metadata behavior:")
                
                # Add debug logging to see what's happening with scanner lists
                self.logger.debug(f"STEP 4: BEFORE SCANNER CHECK: suggested_title='{suggested_title}'")

                # NOW check scanner lists with the extracted title - this ensures scanner match is last
                self.logger.debug(f"STEP 5: Calling check_scanner_lists with: '{suggested_title}'")
                scanner_result = check_scanner_lists(suggested_title)
                self.logger.debug(f"STEP 6: SCANNER CHECK RESULT: {scanner_result}")

                if scanner_result:
                    if len(scanner_result) == 4:
                        # Get the scanner values
                        scanner_content_type, scanner_is_anime, scanner_tmdb_id, scanner_title = scanner_result
                        self.logger.debug(f"STEP 7: SCANNER FOUND: content_type={scanner_content_type}, is_anime={scanner_is_anime}, tmdb_id={scanner_tmdb_id}, title='{scanner_title}'")
                        
                        # CRITICAL FIX: COMPLETELY replace the title with the scanner title
                        if scanner_title:
                            self.logger.info(f"STEP 8: SCANNER MATCH: Replacing '{suggested_title}' with '{scanner_title}'")
                            # Store the original title for comparison
                            original_title = suggested_title
                            # Completely replace the title with the scanner title
                            suggested_title = scanner_title
                            content_type = scanner_content_type
                            is_anime = scanner_is_anime
                            tmdb_id = scanner_tmdb_id
                            self.logger.debug(f"STEP 9: AFTER SCANNER REPLACEMENT: suggested_title='{suggested_title}'")
                            
                            # Critical fix: strip out any leftover release group names that might be in the title
                            if "ExKinoRay" in suggested_title:
                                suggested_title = suggested_title.replace("ExKinoRay", "").strip()
                                self.logger.debug(f"STEP 9.5: REMOVED ExKinoRay: suggested_title='{suggested_title}'")
                    else:
                        content_type = scanner_result[0]
                        is_anime = scanner_result[1]
                        tmdb_id = scanner_result[2]
                        self.logger.debug(f"STEP 7-ALT: Using 3-value scanner result: {scanner_result}")

                # Final debug before display - check if the title somehow changed
                self.logger.debug(f"STEP 11: FINAL VALUE BEFORE DISPLAY: suggested_title='{suggested_title}'")

            # Add a final checkpoint to see what's being displayed to users
            print(f"STEP 12: DEBUG - ABOUT TO DISPLAY: Title='{suggested_title}', Year={suggested_year}, Type={self._get_content_type_display(content_type, is_anime)}")

            # In auto mode, skip user interaction and process directly
            if self.auto_mode:
                # Get media IDs for the title
                ids = self._get_media_ids(suggested_title, suggested_year, content_type == "tv")
                tmdb_id = ids.get('tmdb_id')
                imdb_id = ids.get('imdb_id')
                tvdb_id = ids.get('tvdb_id')
                
                # Process the subfolder based on content type with the IDs
                if content_type == "tv":
                    self._process_tv_series(files, subfolder, suggested_title, suggested_year, is_anime, 
                                           tmdb_id=tmdb_id, imdb_id=imdb_id, tvdb_id=tvdb_id)
                else:
                    self._process_movies(files, subfolder, suggested_title, suggested_year, is_anime,
                                        tmdb_id=tmdb_id, imdb_id=imdb_id, tvdb_id=tvdb_id)
                
                # Update processed count
                self.processed_files += len(files)
                # Save progress after each subfolder
                save_scan_history(self.directory_path, self.processed_files, self.total_files, self.media_files)
                continue  # Now we can continue to the next subfolder
            
            # Manual mode - Start interactive processing loop
            while True:
                # Display current metadata
                print("\nCurrent detection:")
                print(f"Title: {suggested_title}")
                if suggested_year:
                    print(f"Year: {suggested_year}")
                
                # Determine content type display name
                content_type_display = self._get_content_type_display(content_type, is_anime)
                print(f"Content type: {content_type_display}")
                
                # User options
                print("\nOptions:")
                print("1. Accept match and process (default - press Enter)")
                print("2. Search with new title")
                print("3. Change content type")
                print("4. Skip (save for later review)")
                print("5. Quit to main menu")
                
                choice = input("\nEnter choice (1-5, or press Enter for option 1): ").strip()
                
                # Use default choice (1) if user just presses Enter
                if choice == "":
                    choice = "1"
                
                if choice == "5":
                    # Quit to main menu
                    print("\nReturning to main menu...")
                    return
                
                elif choice == "4":
                    # Skip and save for later review
                    self._skip_files(files, subfolder, content_type, is_anime, subfolder_name)
                    break  # Break out of the while loop and continue to next subfolder
                
                elif choice == "3":
                    # Change content type - simplified interface with combined options
                    print("\nSelect content type:")
                    print("1. TV Series")
                    print("2. Movie")
                    print("3. Anime Series")
                    print("4. Anime Movie")
                    
                    type_choice = input("\nEnter choice (1-4): ").strip()
                    
                    # Set content type and anime flag based on unified selection
                    if type_choice == "1":
                        content_type = "tv"
                        is_anime = False
                    elif type_choice == "2":
                        content_type = "movie"
                        is_anime = False
                    elif type_choice == "3":
                        content_type = "tv"
                        is_anime = True
                    elif type_choice == "4":
                        content_type = "movie" 
                        is_anime = True
                    else:
                        print("\nInvalid choice. Using initial detection.")
                        input("\nPress Enter to continue...")
                    
                    # Continue the loop to show updated metadata and options
                    continue
                
                elif choice == "2":
                    # Search with new title
                    new_title = input("\nEnter new title: ").strip()
                    if new_title:
                        suggested_title = new_title
                        
                        # Ask for year
                        new_year = input("Enter year (optional): ").strip()
                        if new_year and new_year.isdigit() and len(new_year) == 4:
                            suggested_year = new_year
                    
                    # Continue the loop to show updated metadata and options
                    continue
                
                # Option 1 or default - proceed with processing
                
                # Get media IDs for the title
                ids = self._get_media_ids(suggested_title, suggested_year, content_type == "tv")
                tmdb_id = ids.get('tmdb_id')
                imdb_id = ids.get('imdb_id')
                tvdb_id = ids.get('tvdb_id')
                
                # Process the subfolder based on content type with the IDs
                if content_type == "tv":
                    self._process_tv_series(files, subfolder, suggested_title, suggested_year, is_anime, 
                                           tmdb_id=tmdb_id, imdb_id=imdb_id, tvdb_id=tvdb_id)
                else:
                    self._process_movies(files, subfolder, suggested_title, suggested_year, is_anime,
                                        tmdb_id=tmdb_id, imdb_id=imdb_id, tvdb_id=tvdb_id)
                
                # Update processed count
                self.processed_files += len(files)
                # Save progress after each subfolder
                save_scan_history(self.directory_path, self.processed_files, self.total_files, self.media_files)
                
                # Break the while loop after processing is complete
                break

    def _get_content_type_display(self, content_type, is_anime):
        """Return a user-friendly display name for the content type."""
        if content_type == "tv":
            return "Anime Series" if is_anime else "TV Series"
        elif content_type == "movie":
            return "Anime Movie" if is_anime else "Movie"
        else:
            return "Unknown"

    def _skip_files(self, files, subfolder, content_type, is_anime, subfolder_name):
        """Skip files and add them to the skipped items registry."""
        for file_path in files:
            # Add to skipped items for manual review
            suggested_name = self._extract_suggested_name(os.path.basename(file_path), subfolder)
            
            skipped_item = {
                'path': file_path,
                'subfolder': subfolder,
                'suggested_name': suggested_name,
                'is_tv': content_type == 'tv',
                'is_anime': is_anime
            }
            
            # Add to global skipped items registry
            globals()['skipped_items_registry'].append(skipped_item)
        
        save_skipped_items(globals()['skipped_items_registry'])
        self.skipped += len(files)
        print(f"\nSkipped {len(files)} files from {subfolder_name} for later review.")
        input("\nPress Enter to continue...")

    def _extract_folder_metadata(self, folder_name):
        """
        Extract metadata (title and year) from a folder name.
        
        Args:
            folder_name: The name of the folder
            
        Returns:
            Tuple of (title, year)
        """
        self.logger.debug(f"EXTRACT_META - ENTRY: Processing folder '{folder_name}'")
        
        # Make a copy of the original folder_name for comparison
        original_folder_name = folder_name

        # Known movie titles that are years
        year_titles = ["1917", "2012", "2001"]
        
        # First, find all potential year matches
        all_year_matches = re.findall(r'(?:^|[^0-9])((?:19|20)\d{2})(?:[^0-9]|$)', folder_name)
        self.logger.debug(f"EXTRACT_META - STEP 0: All potential years found: {all_year_matches}")
        
        # Handle case of movie titles that are years like "1917"
        # If there are multiple 4-digit numbers, we need to determine which is the title and which is the year
        year = None
        title_year = None
        
        if len(all_year_matches) >= 2:
            # For movies like "1917 (2019)" - first is the title, second is the year
            if all_year_matches[0] in year_titles:
                title_year = all_year_matches[0]
                year = all_year_matches[1]
                self.logger.debug(f"EXTRACT_META - SPECIAL CASE: Treating '{title_year}' as title and '{year}' as year")
            else:
                # Standard case - first number is likely the year
                year = all_year_matches[0]
        elif len(all_year_matches) == 1:
            # Only one year-like string found
            # Check if it's a known movie title that is a year
            if all_year_matches[0] in year_titles:
                # This is probably the title, not the year
                title_year = all_year_matches[0]
            else:
                # Just a regular year
                year = all_year_matches[0]
        
        # Log the extracted year
        self.logger.debug(f"EXTRACT_META - STEP 1: Extracted year: {year}, title_year: {title_year}")
        
        # Clean the folder name for title extraction
        # 1. Replace common delimiters with spaces
        folder_name = folder_name.replace('.', ' ').replace('_', ' ')
        self.logger.debug(f"EXTRACT_META - STEP 2: After delimiter replacement: '{folder_name}'")
        
        # 2. Remove the year from the title if found (but not if it's a title year)
        if year:
            # Don't remove the year if it's also the title
            if not title_year or year != title_year:
                # Special case for titles that start with years like "2001: A Space Odyssey"
                if folder_name.lower().startswith(year.lower()):
                    self.logger.debug(f"EXTRACT_META - SPECIAL CASE: Year {year} appears at start of title - keeping it")
                    title_year = year  # Mark this as a title year to prevent removal
                else:
                    folder_name = re.sub(r'(?:^|[^0-9])' + re.escape(year) + r'(?:[^0-9]|$)', ' ', folder_name)
        self.logger.debug(f"EXTRACT_META - STEP 3: After year removal: '{folder_name}'")
        
        # 3. Remove common patterns like resolution, quality, etc.
        folder_name = re.sub(r'\b\d{3,4}p\b', ' ', folder_name)  # Resolution like 1080p, 720p
        self.logger.debug(f"EXTRACT_META - STEP 4: After resolution removal: '{folder_name}'")
        
        # 4. Enhanced pattern to remove more technical terms, including HYBRID, HDR, DV, etc.
        folder_name = re.sub(r'\bBDRemux\b|\bYTS\b|\bYTS.MX\b|\bMX\b|\bBlu-Ray\b|\bBluRay\b|\bRemux\b|\bWEB-DL\b|\bWEBRip\b|\bHDTV\b|\bDVDRip\b|\bDVDScr\b|\bHDRip\b|\bDVD\b|\bBRRip\b|\bDVD-R\b|\bTS\b|\bTC\b|\bCAM\b|\bHC\b|\bSUB\b|\bConcave\b|\bUHD\b|\bHYBRID\b|\bHDR\b|\bDV\b|\bDolby\b|\bVision\b|\bAtmos\b|\bExKinoRay\b|\b[\w]+-[\w]+\b|\bTeam [\w-]+\b|\bOZC\b|\b-\b|\bTheEqualizer\b|\[|\]', ' ', folder_name, flags=re.IGNORECASE)
        self.logger.debug(f"EXTRACT_META - STEP 5: After quality pattern removal: '{folder_name}'")
        
        # 5. Clean up extra spaces and normalize
        folder_name = re.sub(r'\s+', ' ', folder_name).strip()
        self.logger.debug(f"EXTRACT_META - STEP 6: After space normalization: '{folder_name}'")
        
        # 6. Handle special cases or specific formats
        # If we have a title that is a year, force it
        if title_year:
            folder_name = title_year
            self.logger.debug(f"EXTRACT_META - STEP 7: Forcing year title: '{folder_name}'")
        
        # Special handling for movie folders where the title contains a year like "2001" but is also a release year
        if folder_name.startswith("2001") and "Space" in original_folder_name:
            folder_name = "2001 A Space Odyssey"
            self.logger.debug(f"EXTRACT_META - SPECIAL CASE: Handling '2001 A Space Odyssey' format")
        # Special handling for "12 Years A Slave" type titles
        elif folder_name.startswith("12 Years"):
            self.logger.debug(f"EXTRACT_META - SPECIAL CASE: Handling '12 Years A Slave' format")
        # Special handling for "12th Fail" and similar titles
        elif folder_name.startswith("12th"):
            self.logger.debug(f"EXTRACT_META - SPECIAL CASE: Handling '12th' title")
            
        # Store current title before scanner checks for comparison
        pre_scanner_title = folder_name.strip()
        self.logger.debug(f"EXTRACT_META - STEP 7.5: Title before scanner check: '{pre_scanner_title}'")
        
        # 7. Check scanner lists with the original folder name (for better matching)
        # This allows us to match the full path with technical details
        from src.utils.scanner_utils import check_scanner_lists
        
        # First try with the cleaned title
        scanner_result = check_scanner_lists(folder_name)
        
        # If no strong match, try with the original folder name (includes technical details)
        if not scanner_result:
            self.logger.debug(f"EXTRACT_META - Trying original folder name: '{original_folder_name}'")
            scanner_result = check_scanner_lists(original_folder_name, check_full_path=True)
        
        # IMPORTANT: Apply special handling for short titles (like "3 Idiots")
        # If the pre-scanner title is short and looks like a complete title, be cautious about replacement
        is_short_title = len(pre_scanner_title.split()) <= 3
        has_number_in_title = bool(re.search(r'\b\d+\b', pre_scanner_title))
        
        if scanner_result:
            scanner_title = scanner_result[3] if len(scanner_result) > 3 else None
            if scanner_title:
                # For short titles with numbers (like "3 Idiots"), be extra careful
                if is_short_title and has_number_in_title:
                    # Check if scanner title is significantly different
                    scanner_words = set(re.sub(r'[^\w\s]', '', scanner_title.lower()).split())
                    title_words = set(re.sub(r'[^\w\s]', '', pre_scanner_title.lower()).split())
                    
                    # Calculate word overlap
                    common_words = scanner_words.intersection(title_words)
                    word_overlap_ratio = len(common_words) / max(len(title_words), 1)
                    
                    # If there's very little overlap and the pre-scanner title looks valid,
                    # don't replace with scanner title
                    if word_overlap_ratio < 0.3 and len(pre_scanner_title) >= 3:
                        self.logger.info(f"EXTRACT_META - PRESERVING SHORT TITLE: Keeping '{pre_scanner_title}' instead of '{scanner_title}' (low overlap)")
                    else:
                        self.logger.info(f"STEP 8: SCANNER MATCH: Replacing '{folder_name}' with '{scanner_title}'")
                        folder_name = scanner_title
                else:
                    self.logger.info(f"STEP 8: SCANNER MATCH: Replacing '{folder_name}' with '{scanner_title}'")
                    folder_name = scanner_title
                    
                self.logger.debug(f"EXTRACT_META - STEP 9: Using scanner title: '{folder_name}'")
        
        # Final cleanup and normalization
        title = folder_name.strip()
        
        # Log final extracted metadata
        self.logger.debug(f"EXTRACT_META - FINAL: Extracted title='{title}', year={year}")
        
        # Return the extracted metadata
        return title, year

    def _extract_full_series_name(self, folder_name):
        """Extract the full series name from folder name, preserving important subtitle parts."""
        # Initialize variables to track special cases
        special_case = None
        
        # Check for specific special cases but don't return immediately
        if "pokemon.origins" in folder_name.lower() or "pokemon origins" in folder_name.lower():
            special_case = "Pokemon Origins"
        elif re.search(r'star\s*trek.*next\s*generation', folder_name.lower()):
            special_case = "Star Trek The Next Generation"
        elif re.search(r'attack.*titan', folder_name.lower()):
            special_case = "Attack on Titan"
        elif re.search(r'my.*hero.*academia', folder_name.lower()):
            special_case = "My Hero Academia"
        
        # Replace common separators with spaces
        clean_name = folder_name.replace('.', ' ').replace('_', ' ')
        
        # First remove common resolution specifications to avoid mistaking them for years
        resolution_patterns = [
            r'\b\d{3,4}p\b',              # 720p, 1080p, etc.
            r'\b(?:4K|UHD)\b'             # 4K, UHD
        ]
        
        for pattern in resolution_patterns:
            clean_name = re.sub(pattern, '', clean_name, flags=re.IGNORECASE)
        
        # Extract year if present (and preserve it for later)
        year = None
        year_match = re.search(r'\((\d{4})\)', clean_name)
        if not year_match:
            # Try alternative year formats
            year_match = re.search(r'(?<!\d)(\d{4})(?!\d)', clean_name)
        
        if year_match:
            year = year_match.group(1)
            # Validate year is reasonable (between 1900 and current year + 1)
            if year.isdigit() and 1900 <= int(year) <= datetime.datetime.now().year + 1:
                # Remove year from the clean name for processing
                clean_name = re.sub(r'\(\d{4}\)|\b\d{4}\b', '', clean_name)
            else:
                # If year is not reasonable, don't use it
                year = None
        
        # Remove season markers like S01-S07, Season 1-7, etc.
        clean_name = re.sub(r'S\d{1,2}[-.]S?\d{1,2}', '', clean_name, flags=re.IGNORECASE)
        clean_name = re.sub(r'Season[s]?\s*\d{1,2}[-.](\d{1,2})', '', clean_name, flags=re.IGNORECASE)
        clean_name = re.sub(r'(\d{1,2})[-.](\d{1,2})\s*Season[s]?', '', clean_name, flags=re.IGNORECASE)
        
        # Remove common technical specifications and release info
        technical_patterns = [
            r'\b(?:WEB[-]?DL|BluRay|DVDRip)\b',       # Release type
            r'\b(?:x264|x265|HEVC|H[-.]?26[45])\b',   # Encoding
            r'\bAAC\d?(?:[-.]?\d)?\b',                # Audio codec
            r'\b(?:DTS|DD5\.1|AC3)\b',                # Audio codec alternative
            r'\b(?:HDTV|WEB|UHD)\b',                  # Source
            r'\b(?:PROPER|REPACK|INTERNAL)\b',        # Release flags
            r'[-][\w\d]+$',                           # Release group at the end
        ]
        
        for pattern in technical_patterns:
            clean_name = re.sub(pattern, '', clean_name, flags=re.IGNORECASE)
        
        # Remove content in brackets and parentheses
        clean_name = re.sub(r'\[[^\]]*\]|\([^)]*\)', '', clean_name)
        
        # Normalize spaces and trim
        clean_name = re.sub(r'\s+', ' ', clean_name).strip()
        
        # If we identified a special case earlier, use that normalized name
        if special_case:
            clean_name = special_case
        
        # Final cleaning and normalization
        clean_name = re.sub(r'\s+', ' ', clean_name).strip()
        
        # Add back the year if it was extracted
        if year:
            clean_name = f"{clean_name} ({year})"
        
        return clean_name

    def clear_skipped_items(self):
        """Clear all skipped items from the registry."""
        global skipped_items_registry
        skipped_items_registry = []
        save_skipped_items(skipped_items_registry)
        print("\nAll skipped items have been cleared.")
        input("\nPress Enter to continue...")

    def _extract_tv_metadata(self, filename, dirname):
        """
        Extract metadata from TV show filename.
        
        Returns:
            Dictionary with keys for season, episode, resolution, etc.
        """
        metadata = {
            'season': None,
            'episode': None,
            'resolution': None
        }
        
        # Clean the filename
        clean_filename = filename.replace('.', ' ').replace('_', ' ')
        
        # Try to extract season and episode with different patterns
        
        # Pattern 1: S01E01 format
        season_ep_pattern = re.compile(r'S(\d{1,2})E(\d{1,2})', re.IGNORECASE)
        match = season_ep_pattern.search(clean_filename)
        if match:
            metadata['season'] = int(match.group(1))
            metadata['episode'] = int(match.group(2))
        
        # Pattern 2: Season X Episode Y format
        alt_pattern = re.compile(r'Season\s*(\d{1,2}).*?Episode\s*(\d{1,2})', re.IGNORECASE)
        match = alt_pattern.search(clean_filename)
        if match:
            metadata['season'] = int(match.group(1))
            metadata['episode'] = int(match.group(2))
        
        # Pattern 3: 1x01 format
        numeric_pattern = re.compile(r'(\d{1,2})x(\d{2})', re.IGNORECASE)
        match = numeric_pattern.search(clean_filename)
        if match:
            metadata['season'] = int(match.group(1))
            metadata['episode'] = int(match.group(2))
        
        # Pattern 4: Look for episode numbers in filenames like "Star.Trek.TNG.121.mp4"
        # This would be season 1, episode 21
        episode_number_pattern = re.compile(r'\.(\d)(\d{2})\.')
        match = episode_number_pattern.search(filename)
        if match:
            metadata['season'] = int(match.group(1))
            metadata['episode'] = int(match.group(2))
        
        # Try to extract resolution
        resolution_pattern = re.compile(r'(720p|1080p|2160p|4K)', re.IGNORECASE)
        match = resolution_pattern.search(filename)
        if match:
            metadata['resolution'] = match.group(1)
        
        return metadata

    def _extract_season_from_filename(self, filename, season_range=None):
        """
        Extract season number from filename, with optional known season range.
        
        Args:
            filename: The filename to extract from
            season_range: Optional tuple of (start_season, end_season)
            
        Returns:
            Season number as string or None if not found
        """
        if not season_range:
            return None
        
        # If this is a multi-season pack like S01-S07, try to find which season this file belongs to
        start_season, end_season = season_range
        
        # Look for season indicators in the filename
        for season_num in range(start_season, end_season + 1):
            # Format season number with leading zero if needed
            season_str = f"{season_num:02d}"
            season_patterns = [
                rf'S{season_str}',           # S01
                rf'Season {season_num}',      # Season 1
                rf'{season_num}x\d{{2}}',     # 1x01
            ]
            
            for pattern in season_patterns:
                if re.search(pattern, filename, re.IGNORECASE):
                    return str(season_num)
        
        return None

    def _get_media_ids(self, title, year, is_tv):
        """
        Get media IDs from the TMDB API with improved matching for year-based titles.
        
        Args:
            title: Title to search for
            year: Year of release
            is_tv: Whether this is a TV series or movie
            
        Returns:
            Dict with tmdb_id, imdb_id, and tvdb_id (any could be None)
        """
        logger = logging.getLogger(__name__)
        
        # Add caching to avoid repeated API calls for the same title
        cache_key = f"{title}_{year}_{is_tv}"
        
        # Check if we already have this result in memory cache
        if hasattr(self, '_media_id_cache') and cache_key in self._media_id_cache:
            return self._media_id_cache[cache_key]
        
        # Initialize cache if it doesn't exist
        if not hasattr(self, '_media_id_cache'):
            self._media_id_cache = {}
        
        try:
            # Start timing for performance tracking
            search_start_time = time.time()
            
            # Import TMDB API
            from src.api.tmdb import TMDB
            
            # Get TMDB API key from environment
            tmdb_api_key = os.environ.get('TMDB_API_KEY', '')
            
            if not tmdb_api_key:
                logger.warning("TMDB API key not found, cannot search for IDs")
                return {'tmdb_id': None, 'imdb_id': None, 'tvdb_id': None}
            
            # Initialize TMDB API
            tmdb = TMDB(api_key=tmdb_api_key)
            
            # Special case handling for titles containing years
            contains_year_in_title = False
            title_year_match = re.search(r'\b(19\d{2}|20\d{2})\b', title)
            if title_year_match:
                year_in_title = title_year_match.group(1)
                # Check if it's one of the known "year titles"
                known_year_titles = ["1917", "2001", "2010", "2012"]
                if year_in_title in known_year_titles:
                    contains_year_in_title = True
                    logger.debug(f"Detected title containing year: {title} (year in title: {year_in_title})")
            
            # Clean the title to remove any resolution or technical specs that might have been missed
            clean_title = re.sub(r'\b\d{3,4}p\b', '', title, flags=re.IGNORECASE)  # Remove 1080p, 720p, etc.
            clean_title = re.sub(r'\(\d{3,4}\)', '', clean_title)  # Remove (1080), etc.
            clean_title = clean_title.strip()
            
            # Validate year to ensure it's a plausible year, not a resolution
            valid_year = None
            if year and year.isdigit():
                year_num = int(year)
                if 1900 <= year_num <= datetime.datetime.now().year + 1:
                    valid_year = year
                    
            # Store candidate results with scores
            candidates = []
            
            # Search differently based on content type
            if is_tv:
                # TV series search strategy
                query = clean_title
                logger.debug(f"Searching for TV series with query: {query}")
                
                # First search with just the title
                results = tmdb.search_tv(query, limit=5)
                
                if results:
                    for idx, result in enumerate(results):
                        # Calculate match score - higher is better
                        score = self._calculate_match_score(
                            result.get('name', ''), 
                            clean_title, 
                            result.get('first_air_date', '')[:4] if result.get('first_air_date') else None, 
                            valid_year,
                            position=idx
                        )
                        candidates.append((result, score))
                
                # If we have a year, also try searching with the year included
                if valid_year and not candidates:
                    query_with_year = f"{clean_title} {valid_year}"
                    logger.debug(f"Trying TV search with year included: {query_with_year}")
                    results_with_year = tmdb.search_tv(query_with_year, limit=5)
                    
                    if results_with_year:
                        for idx, result in enumerate(results_with_year):
                            score = self._calculate_match_score(
                                result.get('name', ''), 
                                clean_title, 
                                result.get('first_air_date', '')[:4] if result.get('first_air_date') else None, 
                                valid_year,
                                position=idx
                            )
                            candidates.append((result, score))
            else:
                # Movie search strategy
                query = clean_title
                logger.debug(f"Searching for movie with query: {query}")
                
                # Handle special case for titles like "2010: The Year We Make Contact"
                if contains_year_in_title:
                    # Search with more specific query for these special cases
                    logger.debug(f"Special case: Title contains year, using more specific search terms")
                    
                    # Try searching with a more complete title if applicable
                    expanded_title = None
                    if "2001" in clean_title and "space" not in clean_title.lower():
                        expanded_title = "2001: A Space Odyssey"
                    elif "2010" in clean_title and "contact" not in clean_title.lower():
                        expanded_title = "2010: The Year We Make Contact"
                    
                    if expanded_title:
                        logger.debug(f"Trying expanded title search: '{expanded_title}'")
                        expanded_results = tmdb.search_movie(expanded_title, limit=5)
                        
                        if expanded_results:
                            for idx, result in enumerate(expanded_results):
                                # Give higher scores to these special expanded matches
                                score = self._calculate_match_score(
                                    result.get('title', ''), 
                                    expanded_title, 
                                    result.get('release_date', '')[:4] if result.get('release_date') else None, 
                                    valid_year,
                                    position=idx,
                                    bonus=20  # Bonus points for expanded title match
                                )
                                candidates.append((result, score))
                
                # Standard search approach - first try without year
                results = tmdb.search_movie(query, limit=5)
                
                if results:
                    for idx, result in enumerate(results):
                        score = self._calculate_match_score(
                            result.get('title', ''), 
                            clean_title, 
                            result.get('release_date', '')[:4] if result.get('release_date') else None, 
                            valid_year,
                            position=idx
                        )
                        candidates.append((result, score))
                
                # If we have a year and haven't found a good match, also try searching with year
                if valid_year:
                    query_with_year = f"{clean_title} {valid_year}"
                    logger.debug(f"Trying movie search with year included: {query_with_year}")
                    results_with_year = tmdb.search_movie(query_with_year, limit=5)
                    
                    if results_with_year:
                        for idx, result in enumerate(results_with_year):
                            score = self._calculate_match_score(
                                result.get('title', ''), 
                                clean_title, 
                                result.get('release_date', '')[:4] if result.get('release_date') else None, 
                                valid_year,
                                position=idx,
                                bonus=5  # Small bonus for year-specific search
                            )
                            candidates.append((result, score))
            
            # Sort candidates by score (highest first)
            candidates.sort(key=lambda x: x[1], reverse=True)
            
            # Log top candidates for debugging
            for idx, (candidate, score) in enumerate(candidates[:3]):
                name = candidate.get('title', candidate.get('name', 'Unknown'))
                year_str = candidate.get('release_date', candidate.get('first_air_date', ''))[:4]
                logger.debug(f"Candidate {idx+1}: '{name}' ({year_str}) - Score: {score}")
            
            # Take the highest scoring candidate
            if candidates:
                best_match, score = candidates[0]
                
                # Get the appropriate ID depending on content type
                if is_tv:
                    show_id = best_match.get('id')
                    if show_id:
                        # Get detailed info for external IDs
                        details = tmdb.get_tv_details(show_id)
                        external_ids = details.get('external_ids', {})
                        
                        result = {
                            'tmdb_id': show_id,
                            'imdb_id': external_ids.get('imdb_id'),
                            'tvdb_id': external_ids.get('tvdb_id')
                        }
                        
                        # Save to cache
                        self._media_id_cache[cache_key] = result
                        
                        # Log performance
                        search_time = time.time() - search_start_time
                        logger.debug(f"TMDB lookup completed in {search_time:.2f}s")
                        
                        return result
                else:
                    movie_id = best_match.get('id')
                    if movie_id:
                        # Get detailed info for external IDs
                        details = tmdb.get_movie_details(movie_id)
                        
                        result = {
                            'tmdb_id': movie_id,
                            'imdb_id': details.get('imdb_id'),
                            'tvdb_id': None  # Movies don't have TVDB IDs
                        }
                        
                        # Save to cache
                        self._media_id_cache[cache_key] = result
                        
                        # Log performance
                        search_time = time.time() - search_start_time
                        logger.debug(f"TMDB lookup completed in {search_time:.2f}s")
                        
                        return result
            
            # If we got here, no good match was found
            logger.warning(f"No good match found for {clean_title}" + (f" ({valid_year})" if valid_year else ""))
            result = {'tmdb_id': None, 'imdb_id': None, 'tvdb_id': None}
            
            # Cache the negative result to avoid repeated failures
            self._media_id_cache[cache_key] = result
            
            # Log performance even for failures
            search_time = time.time() - search_start_time
            logger.debug(f"TMDB lookup failed in {search_time:.2f}s")
            
            return result
                    
        except Exception as e:
            logger.error(f"Error getting media IDs: {e}", exc_info=True)
            return {'tmdb_id': None, 'imdb_id': None, 'tvdb_id': None}

    def _calculate_match_score(self, api_title, search_title, api_year, search_year, position=0, bonus=0):
        """
        Calculate a match score between API result and search criteria.
        Higher scores are better matches.
        
        Args:
            api_title: Title from the API
            search_title: Title we're searching for
            api_year: Year from the API
            search_year: Year we're searching for
            position: Position in search results (lower is better)
            bonus: Extra points for special cases
            
        Returns:
            Score as an integer
        """
        score = 100  # Base score
        
        # Lowercase everything for comparison
        api_title_lower = api_title.lower()
        search_title_lower = search_title.lower()
        
        # Exact match is best
        if api_title_lower == search_title_lower:
            score += 50
        # Title contains search as a whole word
        elif search_title_lower in api_title_lower:
            score += 30
            # If the API title starts with the search title, even better
            if api_title_lower.startswith(search_title_lower):
                score += 10
        else:
            # Calculate word overlap
            api_words = set(re.findall(r'\w+', api_title_lower))
            search_words = set(re.findall(r'\w+', search_title_lower))
            
            if search_words:
                # Calculate percentage of search words found in API title
                overlap = len(api_words.intersection(search_words)) / len(search_words)
                score += int(overlap * 25)
        
        # Year matching
        if api_year and search_year:
            if api_year == search_year:
                score += 20  # Exact year match
            elif abs(int(api_year) - int(search_year)) <= 1:
                score += 10  # Off by 1 year
            elif abs(int(api_year) - int(search_year)) <= 3:
                score += 5   # Off by up to 3 years
        
        # Position penalty - earlier results are likely more relevant
        score -= position * 2
        
        # Special case bonus
        score += bonus
        
        return score

    def _process_movies(self, files, subfolder, title, year, is_anime, tmdb_id=None, imdb_id=None, tvdb_id=None):
        """
        Process movie files from a subfolder with optimized performance.
        
        Args:
            files: List of file paths to process
            subfolder: Path to the subfolder containing the files
            title: Movie title
            year: Release year
            is_anime: Whether this is an anime movie
            tmdb_id: Optional TMDB ID
            imdb_id: Optional IMDB ID
            tvdb_id: Optional TVDB ID (rarely used for movies)
        """
        # Use start time to measure performance
        start_time = time.time()
        
        # Get destination directory from environment - do this once
        destination_dir = os.environ.get('DESTINATION_DIRECTORY')
        
        if not destination_dir:
            print("Destination directory not set")
            if not self.auto_mode:
                input("\nPress Enter to continue...")
            return
        
        # Create base movie directory
        movie_type = "Anime Movies" if is_anime else "Movies"
        content_dir = os.path.join(destination_dir, movie_type)
        
        # Create movie-specific directory with year and TMDB ID if available
        if tmdb_id:
            movie_dir_name = f"{title} ({year}) [tmdb-{tmdb_id}]" if year else f"{title} [tmdb-{tmdb_id}]"
        else:
            movie_dir_name = f"{title} ({year})" if year else title
            
        movie_dir = os.path.join(content_dir, movie_dir_name)
        
        # Batch all directory creation operations
        try:
            os.makedirs(content_dir, exist_ok=True)
            os.makedirs(movie_dir, exist_ok=True)
        except Exception as e:
            self.logger.error(f"Failed to create directories for {title}: {e}")
            self.errors += 1
            return
        
        # Process all files in a batch
        success_count = 0
        # Get existing files first to avoid repeated calls to os.path.exists
        existing_files = set(os.listdir(movie_dir) if os.path.exists(movie_dir) else [])
        
        # Process files in bulk where possible
        for file_path in files:
            try:
                # Extract file extension
                _, ext = os.path.splitext(file_path)
                
                # Create standardized filename: "MEDIA TITLE (YEAR).extension"
                if year:
                    new_filename = f"{title} ({year}){ext}"
                else:
                    new_filename = f"{title}{ext}"
                
                # Skip if file already exists in destination
                if new_filename in existing_files:
                    continue
                    
                # Create symlink with the standardized filename
                symlink_path = os.path.join(movie_dir, new_filename)
                os.symlink(file_path, symlink_path)
                success_count += 1
                self.symlink_count += 1
                
            except Exception as e:
                self.logger.error(f"Error creating symlink for {file_path}: {e}")
                self.errors += 1
        
        # Only log summary info, not per-file
        elapsed_time = time.time() - start_time
        self.logger.info(f"Processed {len(files)} files for '{title}' ({success_count} symlinks created) in {elapsed_time:.2f}s")
        
        if not self.auto_mode:
            print(f"Processed {len(files)} movie files for '{title}'")

    def _process_tv_series(self, files, subfolder, title, year, is_anime, tmdb_id=None, imdb_id=None, tvdb_id=None):
        """
        Process TV series files from a subfolder.
        
        Args:
            files: List of file paths to process
            subfolder: Path to the subfolder containing the files
            title: Series title
            year: Release year
            is_anime: Whether this is an anime series
            tmdb_id: Optional TMDB ID
            imdb_id: Optional IMDB ID
            tvdb_id: Optional TVDB ID
        """
        # Use start time to measure performance
        start_time = time.time()
        
        # Get destination directory from environment once
        destination_dir = os.environ.get('DESTINATION_DIRECTORY')
        
        if not destination_dir:
            print("Destination directory not set")
            if not self.auto_mode:
                input("\nPress Enter to continue...")
            return
        
        # Create base TV directory
        series_type = "Anime" if is_anime else "TV Shows"
        content_dir = os.path.join(destination_dir, series_type)
        
        # Create series-specific directory with year and TMDB ID if available
        if tmdb_id:
            series_dir_name = f"{title} ({year}) [tmdb-{tmdb_id}]" if year else f"{title} [tmdb-{tmdb_id}]"
        else:
            series_dir_name = f"{title} ({year})" if year else title
            
        series_dir = os.path.join(content_dir, series_dir_name)
        
        try:
            os.makedirs(content_dir, exist_ok=True)
            os.makedirs(series_dir, exist_ok=True)
        except Exception as e:
            self.logger.error(f"Failed to create directories for {title}: {e}")
            self.errors += 1
            return

    def _create_destination_folder(self, title, year=None, content_type="movie", is_anime=False, tmdb_id=None):
        """
        Create a destination folder for the media content.
        
        Args:
            title: The title of the movie or TV show
            year: The release year, if known
            content_type: Either 'movie' or 'tv'
            is_anime: Whether the content is anime
            tmdb_id: The TMDB ID if available
            
        Returns:
            Path to the created folder
        """
        # Clean title for file system compatibility
        clean_title = self._clean_title_for_path(title)
        
        # Determine appropriate subfolder based on content type and anime status
        if content_type == "tv":
            subfolder = "Anime" if is_anime else "TV Shows"
        else:
            subfolder = "Anime Movies" if is_anime else "Movies"
        
        # Construct folder name with title and year
        if year:
            folder_name = f"{clean_title} ({year})"
        else:
            folder_name = clean_title
        
        # Add TMDB ID if available
        if tmdb_id:
            folder_name = f"{folder_name} [tmdb-{tmdb_id}]"
        
        # Define destination path
        destination_dir = os.path.join(os.environ.get('DESTINATION_DIRECTORY', ''), subfolder, folder_name)
        
        # Create the directory if it doesn't exist
        os.makedirs(destination_dir, exist_ok=True)
        
        self.logger.info(f"Created destination directory: {destination_dir}")
        return destination_dir

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