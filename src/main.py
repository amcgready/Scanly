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
os.makedirs(log_dir, exist_ok=True)

# Use 'w' mode instead of 'a' to clear previous logs at startup
file_handler = logging.FileHandler(os.path.join(log_dir, 'scanly.log'), 'w')

# Add a separate file handler for monitor logs - also use 'w' mode
monitor_log_file = os.path.join(log_dir, 'monitor.log')
monitor_handler = logging.FileHandler(monitor_log_file, 'w')
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
    def __init__(self):
        self.logger = get_logger(__name__)

    def show(self):
        """Display the main menu and handle user input."""
        while True:
            clear_screen()
            display_ascii_art()
            print("=" * 60)
            print("MAIN MENU")
            print("=" * 60)
            
            # Display menu options
            print("\n1. Scan Media")
            print("2. Resume Scan")
            print("3. Settings")
            
            # Conditionally show "Review Skipped Items" and "Clear Skipped Items" options
            skipped_count = len(skipped_items_registry)
            if skipped_count > 0:
                print(f"4. Review Skipped Items ({skipped_count})")
                print("5. Clear Skipped Items")
                print("0. Quit")
            else:
                print("0. Quit")
            
            # Get user choice
            choice = input("\nEnter your choice: ").strip()
            
            # Process user choice
            if choice == "1":
                self.scan_media()
            elif choice == "2":
                self.resume_scan()
            elif choice == "3":
                self.settings()
            elif choice == "4" and skipped_count > 0:
                self.review_skipped_items()
            elif choice == "5" and skipped_count > 0:
                # Call the clear_skipped_items method
                dp = DirectoryProcessor("", auto_mode=False)
                dp.clear_skipped_items()
            elif choice == "0":
                print("\nExiting Scanly...")
                break
            else:
                print("\nInvalid choice. Please try again.")
                input("\nPress Enter to continue...")

    def scan_media(self):
        """Placeholder for scan media functionality."""
        print("\nScan Media functionality is not implemented yet.")
        input("\nPress Enter to continue...")

    def resume_scan(self):
        """Placeholder for resume scan functionality."""
        print("\nResume Scan functionality is not implemented yet.")
        input("\nPress Enter to continue...")

    def settings(self):
        """Placeholder for settings functionality."""
        print("\nSettings functionality is not implemented yet.")
        input("\nPress Enter to continue...")

    def review_skipped_items(self):
        """Review skipped items."""
        review_skipped_items()

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

    def clear_skipped_items(self):
        """Clear all skipped items from the registry."""
        global skipped_items_registry
        skipped_items_registry = []
        save_skipped_items(skipped_items_registry)
        print("\nAll skipped items have been cleared.")
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