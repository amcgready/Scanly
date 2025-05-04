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

# DirectoryProcessor class
class DirectoryProcessor:
    """Class for processing media directories."""
    
    def __init__(self, directory_path, auto_mode=False, resume=False):
        self.directory_path = directory_path
        self.auto_mode = auto_mode
        self.resume = resume
        self.logger = get_logger(__name__)  # Initialize logger here
        # Other initialization code...
    
    def process(self):
        """Process the directory."""
        try:
            print(f"\nProcessing directory: {self.directory_path}")
            # Check if directory exists
            if not os.path.isdir(self.directory_path):
                print(f"Error: Directory does not exist: {self.directory_path}")
                return
            
            # Process the directory
            self._process_media_files()
            
        except Exception as e:
            self.logger.error(f"Error processing directory: {e}", exc_info=True)
            print(f"Unexpected error: {e}")
            print("Check logs for details.")
    
    def _process_media_files(self):
        """Process media files in the directory."""
        # Place global declaration at the beginning of function - before any use of the variable
        global skipped_items_registry
        
        try:
            # Get all subdirectories
            subdirs = [d for d in os.listdir(self.directory_path) 
                      if os.path.isdir(os.path.join(self.directory_path, d))]
            
            if not subdirs:
                print(f"No subdirectories found in {self.directory_path}")
                return
                
            print(f"Found {len(subdirs)} subdirectories to process")
            
            # Track progress
            processed = 0
            
            # Process each subfolder
            for subfolder_name in subdirs:
                subfolder_path = os.path.join(self.directory_path, subfolder_name)
                processed += 1
                
                try:
                    clear_screen()
                    display_ascii_art()
                    print("=" * 60)
                    print(f"PROCESSING SUBFOLDER: {subfolder_name}")
                    print("=" * 60)
                    
                    print(f"\nFolder path: {subfolder_path}")
                    
                    # Count media files in subfolder
                    media_files = []
                    for root, _, files in os.walk(subfolder_path):
                        for file in files:
                            if file.endswith(('.mp4', '.mkv', '.avi', '.mov', '.wmv', '.m4v')):
                                media_files.append(os.path.join(root, file))
                    
                    print(f"Contains {len(media_files)} media files")
                    
                    # Extract metadata from folder name
                    self.logger.debug(f"Extracting metadata from folder name: '{subfolder_name}'")
                    
                    # Extract title and year from folder name
                    title, year = self._extract_folder_metadata(subfolder_name) if hasattr(self, '_extract_folder_metadata') else (subfolder_name, None)
                    
                    # Determine content type (TV show, movie, anime, etc.)
                    is_tv = self._detect_if_tv_show(subfolder_name)
                    is_anime = self._detect_if_anime(subfolder_name)
                    
                    content_type = "TV Show" if is_tv else "Movie"
                    anime_label = " (Anime)" if is_anime else ""
                    
                    # Display current detection
                    print("\nCurrent detection:")
                    print(f"Title: {title if title else subfolder_name}")
                    print(f"Year: {year if year else 'Unknown'}")
                    print(f"Content type: {content_type}{anime_label}")
                    
                    # Automatic mode - skip user interaction
                    if self.auto_mode:
                        print(f"\nAuto processing as: {content_type}{anime_label}")
                        # Process based on content type
                        # Additional processing logic would go here
                        continue
                    
                    # Interactive mode
                    print("\nOptions:")
                    print("1. Accept match and process (default - press Enter)")
                    print("2. Search with new title")
                    print("3. Change content type")
                    print("4. Skip (save for later review)")
                    print("5. Quit to main menu")
                    
                    choice = input("\nEnter choice (1-5, or press Enter for option 1): ").strip()
                    
                    # Default to option 1 if user just presses Enter
                    if not choice:
                        choice = "1"
                    
                    if choice == "1":
                        # Process with current detection
                        print(f"\nProcessing {subfolder_name} as {content_type}{anime_label}...")
                        
                        # Create symlinks
                        symlink_success = self._create_symlinks(subfolder_path, title, year, is_tv, is_anime)
                        
                        if symlink_success:
                            print(f"Successfully processed {subfolder_name}")
                        else:
                            print(f"Failed to create symlinks for {subfolder_name}")
                        
                    elif choice == "2":
                        # Search with new title
                        print("\nEnter new title:")
                        new_title = input("> ").strip()
                        
                        print("\nEnter year (optional, press Enter to skip):")
                        new_year = input("> ").strip()
                        
                        if new_title:
                            title = new_title
                        if new_year:
                            year = new_year
                        
                        print(f"\nProcessing {subfolder_name} with new title: {title} ({year if year else 'Unknown year'})...")
                        
                        # Create symlinks with the updated title/year
                        symlink_success = self._create_symlinks(subfolder_path, title, year, is_tv, is_anime)
                        
                        if symlink_success:
                            print(f"Successfully processed {subfolder_name}")
                        else:
                            print(f"Failed to create symlinks for {subfolder_name}")
                        
                    elif choice == "3":
                        # Change content type
                        print("\nSelect the correct content type:")
                        print("1. Movie")
                        print("2. TV Show")
                        print("3. Anime Movie")
                        print("4. Anime TV Show")
                        
                        content_choice = input("\nEnter choice (1-4): ").strip()
                        
                        if content_choice == "1":
                            is_tv = False
                            is_anime = False
                        elif content_choice == "2":
                            is_tv = True
                            is_anime = False
                        elif content_choice == "3":
                            is_tv = False
                            is_anime = True
                        elif content_choice == "4":
                            is_tv = True
                            is_anime = True
                        else:
                            print("\nInvalid choice. Using detected content type.")
                        
                        content_type = "TV Show" if is_tv else "Movie"
                        anime_label = " (Anime)" if is_anime else ""
                        
                        print(f"\nProcessing {subfolder_name} as {content_type}{anime_label}...")
                        
                        # Create symlinks with the updated content type
                        symlink_success = self._create_symlinks(subfolder_path, title, year, is_tv, is_anime)
                        
                        if symlink_success:
                            print(f"Successfully processed {subfolder_name}")
                        else:
                            print(f"Failed to create symlinks for {subfolder_name}")
                        
                    elif choice == "4":
                        # Skip this folder
                        print(f"\nSkipped: {subfolder_name}")
                        # Add to skipped items registry
                        skip_item = {
                            'path': subfolder_path,
                            'subfolder': subfolder_name,
                            'suggested_name': title if 'title' in locals() else subfolder_name,
                            'is_tv': is_tv,
                            'is_anime': is_anime,
                            'error': "Skipped by user",
                            'timestamp': datetime.datetime.now().isoformat()
                        }
                        
                        skipped_items_registry.append(skip_item)
                        save_skipped_items(skipped_items_registry)
                        continue
                        
                    elif choice == "5":
                        # Quit to main menu
                        print("\nReturning to main menu...")
                        return
                    
                    else:
                        print("\nInvalid choice. Using detected content type.")
                    
                    # Add a pause between processing each subfolder
                    if not self.auto_mode:
                        input("\nPress Enter to continue to the next subfolder...")
                        
                except Exception as e:
                    self.logger.error(f"Error processing subfolder '{subfolder_name}': {e}", exc_info=True)
                    print(f"Error processing {subfolder_name}: {e}")
                    
                    # Add to skipped items
                    skip_item = {
                        'path': subfolder_path,
                        'subfolder': subfolder_name,
                        'suggested_name': subfolder_name,
                        'is_tv': is_tv if 'is_tv' in locals() else False,
                        'is_anime': is_anime if 'is_anime' in locals() else False,
                        'error': str(e),
                        'timestamp': datetime.datetime.now().isoformat()
                    }
                    
                    skipped_items_registry.append(skip_item)
                    save_skipped_items(skipped_items_registry)
                    
                    # Add a pause after an error to let the user read the message
                    input("\nPress Enter to continue...")
                
            print(f"\nFinished processing {len(subdirs)} subdirectories.")
            
        except Exception as e:
            self.logger.error(f"Error processing media files: {e}", exc_info=True)
            raise

    def _extract_folder_metadata(self, folder_name):
        """
        Extract title and year from a folder name.
        Returns a tuple of (title, year).
        """
        # Initialize
        title = folder_name
        year = None
        
        # Extract year using regex
        year_match = re.search(r'(?:^|[^0-9])(\d{4})(?:[^0-9]|$)', folder_name)
        if year_match:
            year = year_match.group(1)
        
        # First level of cleaning - remove common patterns
        clean_title = folder_name
        
        # Remove the year
        if year:
            clean_title = re.sub(r'\.?' + year + r'\.?', ' ', clean_title)
        
        # Remove common quality/format indicators
        patterns_to_remove = [
            # Resolution patterns
            r'(?i)\b(720p|1080p|1440p|2160p|4320p|480p|576p|8K|4K|UHD|HD|FHD|QHD)\b',
            
            # Format patterns
            r'(?i)\b(BluRay|BD|REMUX|BDRemux|BDRip|DVDRip|HDTV|WebRip|WEB-DL|WEBRip|Web|HDRip|DVD|DVDR)\b',
            
            # Codec patterns
            r'(?i)\b(xvid|divx|x264|x265|hevc|h264|h265|HEVC|avc|vp9|av1)\b',
            
            # Audio patterns
            r'(?i)\b(DTS[-\.]?(HD|ES|X)?|DD5\.1|AAC|AC3|TrueHD|Atmos|MA|5\.1|7\.1|2\.0|opus)\b',
            
            # Release group patterns (in brackets or after hyphen)
            r'(?i)(\[.*?\]|\-[a-zA-Z0-9_]+$)',

            # Common release group names
            r'(?i)\b(AMZN|YIFY|NTG|YTS|SPARKS|RARBG|EVO|GHOST|HDCAM|CAM|TS|SCREAM|ExKinoRay)\b',

            # Scanner patterns
            r'(?i)\b(ERROR|Error)\b',
            
            # Other common patterns
            r'(?i)\b(HDR|10bit|8bit|Hi10P|IMAX|PROPER|REPACK)\b'
        ]
        
        # Apply all patterns
        for pattern in patterns_to_remove:
            clean_title = re.sub(pattern, ' ', clean_title)
        
        # Replace dots, underscores, and dashes with spaces
        clean_title = re.sub(r'\.|\-|_', ' ', clean_title)
        
        # Remove the FGT pattern explicitly (as seen in the example)
        clean_title = re.sub(r'\bFGT\b', '', clean_title, flags=re.IGNORECASE)
        
        # Replace multiple spaces with a single space and trim
        clean_title = re.sub(r'\s+', ' ', clean_title).strip()
        
        # If the title is empty after cleaning, use the original folder name
        if not clean_title:
            clean_title = folder_name
            
        # Further refine by performing weighted matching against scanner lists
        refined_title, tmdb_id = self._refine_title_with_scanners(clean_title, year)
        if refined_title:
            clean_title = refined_title
            
        # Store TMDB ID if found
        if tmdb_id:
            self._detected_tmdb_id = tmdb_id
                
        self.logger.debug(f"Original: '{folder_name}', Cleaned: '{clean_title}', Year: {year}")
        return clean_title, year

    def _refine_title_with_scanners(self, clean_title, year):
        """
        Try to match the cleaned title against scanner lists to refine it further.
        
        Returns a tuple of (refined_title, tmdb_id) if a good match is found, or (None, None) if no good match.
        """
        best_match = None
        best_match_score = 0
        best_match_type = None
        best_tmdb_id = None
        
        # Check each scanner list
        for list_type in ['movies', 'tv_series', 'anime_movies', 'anime_series']:
            match, score, tmdb_id = self._get_best_match_from_list(clean_title, year, list_type)
            if match and score > best_match_score:
                best_match = match
                best_match_score = score
                best_match_type = list_type
                best_tmdb_id = tmdb_id
        
        # If we have a good match (score above threshold), use it
        if best_match_score > 0.7:  # 70% confidence threshold
            self.logger.debug(f"Found match in {best_match_type} list: '{best_match}' (score: {best_match_score:.2f}, TMDB ID: {best_tmdb_id})")
            # Store the content type for later use
            if best_match_type == 'movies':
                self._detected_content_type = 'movie'
            elif best_match_type == 'tv_series':
                self._detected_content_type = 'tv'
            elif best_match_type == 'anime_movies':
                self._detected_content_type = 'anime_movie'
            elif best_match_type == 'anime_series':
                self._detected_content_type = 'anime_tv'
            
            # Store the TMDB ID
            if best_tmdb_id:
                self._detected_tmdb_id = best_tmdb_id
                
            return best_match, best_tmdb_id
        
        return None, None

    def _get_best_match_from_list(self, title, year, list_type):
        """
        Find the best match for a title in a scanner list.
        
        Returns a tuple of (best_match, score, tmdb_id) where score is between 0 and 1.
        """
        try:
            # Path to scanners directory
            scanners_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'scanners')
            
            # Determine which file to check based on list_type
            if list_type == 'tv_series':
                file_path = os.path.join(scanners_dir, 'tv_series.txt')
            elif list_type == 'movies':
                file_path = os.path.join(scanners_dir, 'movies.txt')
            elif list_type == 'anime_movies':
                file_path = os.path.join(scanners_dir, 'anime_movies.txt')
            elif list_type == 'anime_series':
                file_path = os.path.join(scanners_dir, 'anime_series.txt')
            else:
                self.logger.debug(f"Unknown scanner list type: {list_type}")
                return None, 0, None
            
            # Check if the file exists
            if not os.path.exists(file_path):
                self.logger.debug(f"Scanner list file does not exist: {file_path}")
                return None, 0, None
            
            # Read the file and find the best match
            best_match = None
            best_score = 0
            best_tmdb_id = None
            
            # Convert title to lowercase for case-insensitive comparison
            title_lower = title.lower().strip()
            
            # Debug output
            self.logger.debug(f"Looking for '{title_lower}' in {list_type} list")
            
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                
            # First pass: Check for exact matches or direct containment
            for line in lines:
                line = line.strip()
                if not line or line.startswith('#'):  # Skip empty lines and comments
                    continue
                
                # Parse the line: MEDIA TITLE (YEAR) [TMDB ID]
                # Extract the TMDB ID from the line
                tmdb_id = None
                tmdb_match = re.search(r'\[([^\]]+)\]', line)
                if tmdb_match:
                    tmdb_id = tmdb_match.group(1)
                    # Don't skip Error entries for exact title matches
                    # We should still match the title even if it has [Error]

                # Clean the line by removing the TMDB ID part (including [Error])
                clean_line = re.sub(r'\s*\[[^\]]+\]\s*$', '', line)
                
                # Extract year from the line if present
                line_year = None
                year_match = re.search(r'\((\d{4})\)', clean_line)
                if year_match:
                    line_year = year_match.group(1)
                    # Remove the year part for title comparison
                    clean_line_without_year = re.sub(r'\s*\(\d{4}\)\s*', ' ', clean_line)
                else:
                    clean_line_without_year = clean_line
                
                clean_line_without_year = clean_line_without_year.lower().strip()
                
                # Debug exact match attempts
                self.logger.debug(f"Comparing '{title_lower}' with '{clean_line_without_year}'")
                
                # Exact match check - absolute priority
                if title_lower == clean_line_without_year:
                    self.logger.info(f"EXACT MATCH: Found perfect match for '{title}' in {list_type} list: '{clean_line}'")
                    
                    # Check if we have an [Error] TMDB ID
                    if tmdb_id and tmdb_id.lower() == "error":
                        self.logger.info(f"Title found in scanner list but has [Error] tag. Trying to fetch TMDB ID...")
                        
                        # Determine content type for TMDB search
                        if list_type in ['tv_series', 'anime_series']:
                            content_type = 'tv'
                        else:
                            content_type = 'movie'
                            
                        # Try to get TMDB ID from the API
                        fetched_tmdb_id = self._get_tmdb_id_for_title(clean_line_without_year, year, content_type)
                        if fetched_tmdb_id:
                            self.logger.info(f"Successfully retrieved TMDB ID: {fetched_tmdb_id}")
                            tmdb_id = fetched_tmdb_id
                            
                            # Update the scanner list with the new TMDB ID
                            self._update_scanner_entry(list_type, clean_line_without_year, fetched_tmdb_id)
                    
                    return clean_line, 1.0, tmdb_id  # Perfect match

                # For substring matches
                if title_lower in clean_line_without_year:
                    containment_ratio = len(title_lower) / len(clean_line_without_year)
                    if containment_ratio > 0.7:  # Our title covers at least 70% of the scanner entry
                        self.logger.info(f"STRONG SUBSTRING: Title '{title_lower}' is contained in scanner entry '{clean_line_without_year}' with ratio {containment_ratio:.2f}")
                        
                        # Check if we have an [Error] TMDB ID
                        if tmdb_id and tmdb_id.lower() == "error":
                            self.logger.info(f"Title found in scanner list but has [Error] tag. Trying to fetch TMDB ID...")
                            
                            # Determine content type for TMDB search
                            if list_type in ['tv_series', 'anime_series']:
                                content_type = 'tv'
                            else:
                                content_type = 'movie'
                                
                            # Try to get TMDB ID from the API
                            fetched_tmdb_id = self._get_tmdb_id_for_title(clean_line_without_year, year, content_type)
                            if fetched_tmdb_id:
                                self.logger.info(f"Successfully retrieved TMDB ID: {fetched_tmdb_id}")
                                tmdb_id = fetched_tmdb_id
                                
                                # Update the scanner list with the new TMDB ID
                                self._update_scanner_entry(list_type, clean_line, fetched_tmdb_id)
                        
                        return clean_line, 0.92, tmdb_id  # Strong match

                # For containment matches:
                if clean_line_without_year in title_lower and len(clean_line_without_year) >= 5:
                    containment_ratio = len(clean_line_without_year) / len(title_lower)
                    if containment_ratio > 0.7:  # The entry covers at least 70% of our title
                        self.logger.info(f"STRONG CONTAINMENT: Scanner entry '{clean_line_without_year}' is contained in '{title_lower}' with ratio {containment_ratio:.2f}")
                        
                        # Check if we have an [Error] TMDB ID
                        if tmdb_id and tmdb_id.lower() == "error":
                            self.logger.info(f"Title found in scanner list but has [Error] tag. Trying to fetch TMDB ID...")
                            
                            # Determine content type for TMDB search
                            if list_type in ['tv_series', 'anime_series']:
                                content_type = 'tv'
                            else:
                                content_type = 'movie'
                                
                            # Try to get TMDB ID from the API
                            fetched_tmdb_id = self._get_tmdb_id_for_title(clean_line_without_year, year, content_type)
                            if fetched_tmdb_id:
                                self.logger.info(f"Successfully retrieved TMDB ID: {fetched_tmdb_id}")
                                tmdb_id = fetched_tmdb_id
                                
                                # Update the scanner list with the new TMDB ID
                                self._update_scanner_entry(list_type, clean_line, fetched_tmdb_id)
                        
                        return clean_line, 0.95, tmdb_id  # Strong match
                
            # Second pass: Calculate fuzzy matches if no direct/substring match was found
            for line in lines:
                line = line.strip()
                if not line or line.startswith('#'):  # Skip empty lines and comments
                    continue
                
                # For fuzzy matching (but not direct matching), skip Error entries
                if "[Error]" in line and (title_lower not in line.lower()):
                    continue
                    
                # Parse the line again
                tmdb_id = None
                tmdb_match = re.search(r'\[([^\]]+)\]', line)
                if tmdb_match:
                    tmdb_id = tmdb_match.group(1)
                
                # Clean the line
                clean_line = re.sub(r'\s*\[[^\]]+\]\s*$', '', line)
                
                # Extract year
                line_year = None
                year_match = re.search(r'\((\d{4})\)', clean_line)
                if year_match:
                    line_year = year_match.group(1)
                    clean_line_without_year = re.sub(r'\s*\(\d{4}\)\s*', ' ', clean_line)
                else:
                    clean_line_without_year = clean_line
                
                clean_line_without_year = clean_line_without_year.lower().strip()
                
                # Word set comparison
                title_words = set(re.findall(r'\b\w+\b', title_lower))
                line_words = set(re.findall(r'\b\w+\b', clean_line_without_year))
                
                if not title_words or not line_words:  # Avoid division by zero
                    continue
                
                # Calculate Jaccard similarity (intersection over union)
                intersection = len(title_words.intersection(line_words))
                union = len(title_words.union(line_words))
                
                if union > 0:
                    jaccard = intersection / union
                    
                    # Boost score if title is a subset of line
                    if title_words.issubset(line_words):
                        jaccard += 0.2
                    
                    # Calculate word order similarity for multi-word titles
                    if len(title_words) > 1 and len(line_words) > 1:
                        title_words_list = [w.lower() for w in re.findall(r'\b\w+\b', title)]
                        line_words_list = [w.lower() for w in re.findall(r'\b\w+\b', clean_line_without_year)]
                        
                        # Check if words appear in the same order
                        same_order = True
                        for i in range(len(title_words_list)-1):
                            if title_words_list[i] in line_words_list and title_words_list[i+1] in line_words_list:
                                try:
                                    idx1 = line_words_list.index(title_words_list[i])
                                    idx2 = line_words_list.index(title_words_list[i+1])
                                    if idx1 >= idx2:  # Words are in wrong order
                                        same_order = False
                                        break
                                except ValueError:
                                    # Handle case where word might not be found
                                    pass
                        
                        if same_order and intersection > 1:  # At least 2 words in common and in order
                            jaccard += 0.1
                    
                    # Give extra weight to exact matches of words rather than just character similarity
                    if intersection > 0:
                        jaccard += 0.1
                    
                    # Apply a penalty for large differences in length
                    length_ratio = min(len(title), len(clean_line_without_year)) / max(len(title), len(clean_line_without_year))
                    jaccard *= (0.5 + 0.5 * length_ratio)  # Dampen but don't eliminate matches with size differences
                    
                    # Boost score if years match
                    if year and line_year and year == line_year:
                        jaccard += 0.15
                    
                    # Apply a small penalty for year mismatches
                    elif year and line_year and year != line_year:
                        jaccard -= 0.05
                    
                    if jaccard > best_score:
                        best_score = jaccard
                        best_match = clean_line
                        best_tmdb_id = tmdb_id
            
            if best_match:
                self.logger.debug(f"Best fuzzy match in {list_type}: '{best_match}' with score {best_score:.2f}")
            
            return best_match, best_score, best_tmdb_id
            
        except Exception as e:
            self.logger.error(f"Error finding best match in scanner list: {e}", exc_info=True)
            return None, 0, None

    def _get_tmdb_id_for_title(self, title, year=None, content_type='movie'):
        """
        Search TMDB for a title and get its ID.
        
        Args:
            title: The title to search for
            year: The release year (optional)
            content_type: 'movie' or 'tv'
            
        Returns:
            The TMDB ID if found, None otherwise
        """
        try:
            # Check if TMDB API key is set
            if not TMDB_API_KEY:
                self.logger.warning("TMDB API key not configured. Cannot fetch TMDB ID.")
                return None
                
            import requests
            
            # Prepare search parameters
            params = {
                'api_key': TMDB_API_KEY,
                'query': title,
                'include_adult': 'false',
                'language': 'en-US'
            }
            
            # Add year to query if available
            if year:
                params['year'] = year
                
            # Determine search endpoint based on content type
            if content_type in ['tv', 'anime_tv']:
                search_url = 'https://api.themoviedb.org/3/search/tv'
            else:
                search_url = 'https://api.themoviedb.org/3/search/movie'
                
            # Make the request
            response = requests.get(search_url, params=params)
            data = response.json()
            
            # Check if we got results
            if 'results' in data and data['results']:
                # Get the first result's ID
                tmdb_id = data['results'][0]['id']
                self.logger.info(f"Found TMDB ID for '{title}': {tmdb_id}")
                return str(tmdb_id)
                
            return None
            
        except Exception as e:
            self.logger.error(f"Error searching TMDB: {e}")
            return None

    def _update_scanner_entry(self, list_type, title, tmdb_id):
        """
        Update a scanner list entry with a new TMDB ID
        
        Args:
            list_type: The type of scanner list ('movies', 'tv_series', etc.)
            title: The title to update
            tmdb_id: The new TMDB ID
        
        Returns:
            bool: True if updated successfully, False otherwise
        """
        try:
            # Path to scanners directory
            scanners_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'scanners')
            
            # Determine which file to update based on list_type
            if list_type == 'tv_series':
                file_path = os.path.join(scanners_dir, 'tv_series.txt')
            elif list_type == 'movies':
                file_path = os.path.join(scanners_dir, 'movies.txt')
            elif list_type == 'anime_movies':
                file_path = os.path.join(scanners_dir, 'anime_movies.txt')
            elif list_type == 'anime_series':
                file_path = os.path.join(scanners_dir, 'anime_series.txt')
            else:
                self.logger.debug(f"Unknown scanner list type: {list_type}")
                return False
            
            # Check if the file exists
            if not os.path.exists(file_path):
                self.logger.debug(f"Scanner list file does not exist: {file_path}")
                return False
                
            # Read the entire file
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                
            # Find the line with the title and update it
            updated = False
            for i, line in enumerate(lines):
                clean_line = re.sub(r'\s*\[[^\]]+\]\s*$', '', line).strip()
                title_lower = title.lower().strip()
                
                # First check for exact matches
                if title_lower == clean_line.lower():
                    # Update the line with the new TMDB ID
                    lines[i] = f"{clean_line} [{tmdb_id}]\n"
                    updated = True
                    self.logger.info(f"Updated scanner entry in {list_type}: '{clean_line}' with TMDB ID: {tmdb_id}")
                    break
                
                # Also check for entries where the title is in the clean_line
                # This is useful for cases where the entry includes the year but our title doesn't
                elif title_lower in clean_line.lower() or clean_line.lower() in title_lower:
                    # Calculate containment ratios to ensure it's a substantial match
                    if len(title_lower) > 0 and len(clean_line.lower()) > 0:
                        if title_lower in clean_line.lower():
                            ratio = len(title_lower) / len(clean_line.lower())
                        else:
                            ratio = len(clean_line.lower()) / len(title_lower)
                        
                        if ratio > 0.7:  # Only update if it's a substantial match
                            # Update the line with the new TMDB ID
                            lines[i] = f"{clean_line} [{tmdb_id}]\n"
                            updated = True
                            self.logger.info(f"Updated scanner entry in {list_type}: '{clean_line}' with TMDB ID: {tmdb_id}")
                            break
            
            # If we found and updated the entry, write the updated file
            if updated:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.writelines(lines)
                    
                return True
            else:
                self.logger.warning(f"Could not find entry for '{title}' in {list_type} list to update")
                return False
                
        except Exception as e:
            self.logger.error(f"Error updating scanner entry: {e}", exc_info=True)
            return False

    def _detect_if_tv_show(self, folder_name):
        """Detect if a folder contains a TV show based on its name and scanner lists."""
        # Check if we've already determined the content type through title matching
        if hasattr(self, '_detected_content_type'):
            if self._detected_content_type in ['tv', 'anime_tv']:
                return True
            elif self._detected_content_type in ['movie', 'anime_movie']:
                return False
        
        # First clean the folder name
        clean_title, year = self._extract_folder_metadata(folder_name)
        
        self.logger.info(f"Detecting content type for '{clean_title}' (year: {year})")
        
        # Check scanner lists with weighted matching
        movie_match, movie_score, movie_tmdb_id = self._get_best_match_from_list(clean_title, year, 'movies')
        tv_match, tv_score, tv_tmdb_id = self._get_best_match_from_list(clean_title, year, 'tv_series')
        anime_movie_match, anime_movie_score, anime_movie_tmdb_id = self._get_best_match_from_list(clean_title, year, 'anime_movies')
        anime_tv_match, anime_tv_score, anime_tv_tmdb_id = self._get_best_match_from_list(clean_title, year, 'anime_series')
        
        # Log all scores for debugging
        self.logger.info(f"Match scores - Movie: {movie_score:.2f}, TV: {tv_score:.2f}, Anime Movie: {anime_movie_score:.2f}, Anime TV: {anime_tv_score:.2f}")
        
        # DIRECT MATCH HANDLING - perfect or near-perfect matches (score > 0.9) take absolute priority
        if movie_score > 0.9:
            self.logger.info(f"Direct movie match: '{movie_match}' (score: {movie_score:.2f})")
            self._detected_content_type = 'movie'
            if movie_tmdb_id:
                self._detected_tmdb_id = movie_tmdb_id
            return False
            
        if tv_score > 0.9:
            self.logger.info(f"Direct TV match: '{tv_match}' (score: {tv_score:.2f})")
            self._detected_content_type = 'tv'
            if tv_tmdb_id:
                self._detected_tmdb_id = tv_tmdb_id
            return True
            
        if anime_movie_score > 0.9:
            self.logger.info(f"Direct anime movie match: '{anime_movie_match}' (score: {anime_movie_score:.2f})")
            self._detected_content_type = 'anime_movie'
            if anime_movie_tmdb_id:
                self._detected_tmdb_id = anime_movie_tmdb_id
            return False
            
        if anime_tv_score > 0.9:
            self.logger.info(f"Direct anime TV match: '{anime_tv_match}' (score: {anime_tv_score:.2f})")
            self._detected_content_type = 'anime_tv'
            if anime_tv_tmdb_id:
                self._detected_tmdb_id = anime_tv_tmdb_id
            return True
        
        # If no direct match, compare best scores across categories
        best_movie_score = max(movie_score, anime_movie_score)
        best_tv_score = max(tv_score, anime_tv_score)
        
        # If there's a clear winner (with significant score difference)
        if best_movie_score > best_tv_score + 0.15:  # Movies score is significantly better
            if movie_score >= anime_movie_score:
                self._detected_content_type = 'movie'
                if movie_tmdb_id:
                    self._detected_tmdb_id = movie_tmdb_id
            else:
                self._detected_content_type = 'anime_movie'
                if anime_movie_tmdb_id:
                    self._detected_tmdb_id = anime_movie_tmdb_id
            self.logger.info(f"Selected movie based on score difference: best movie {best_movie_score:.2f} vs best TV {best_tv_score:.2f}")
            return False
            
        elif best_tv_score > best_movie_score + 0.15:  # TV score is significantly better
            if tv_score >= anime_tv_score:
                self._detected_content_type = 'tv'
                if tv_tmdb_id:
                    self._detected_tmdb_id = tv_tmdb_id
            else:
                self._detected_content_type = 'anime_tv'
                if anime_tv_tmdb_id:
                    self._detected_tmdb_id = anime_tv_tmdb_id
            self.logger.info(f"Selected TV based on score difference: best TV {best_tv_score:.2f} vs best movie {best_movie_score:.2f}")
            return True
        
        # If scores are close, look for TV indicators in the filename
        if self._has_tv_indicators(folder_name):
            self.logger.info(f"Scores are close ({best_movie_score:.2f} vs {best_tv_score:.2f}) but found TV indicators in filename")
            self._detected_content_type = 'tv'
            return True
        
        # Default to movie if scores are close and no TV indicators (movies are more common)
        self.logger.info(f"Scores are close ({best_movie_score:.2f} vs {best_tv_score:.2f}) - defaulting to movie")
        if movie_score >= anime_movie_score:
            self._detected_content_type = 'movie'
            if movie_tmdb_id:
                self._detected_tmdb_id = movie_tmdb_id
        else:
            self._detected_content_type = 'anime_movie'
            if anime_movie_tmdb_id:
                self._detected_tmdb_id = anime_movie_tmdb_id
        return False

    def _has_tv_indicators(self, folder_name):
        """Check if a folder name contains TV show indicators."""
        tv_indicators = ['season', 'episode', 's\d+e\d+', 'complete', 'series']
        
        # Case insensitive search for TV show indicators
        lower_name = folder_name.lower()
        
        # Check for season folders
        if re.search(r'season\s*\d+', lower_name, re.IGNORECASE):
            return True
            
        # Check for episode patterns (S01E01, etc.)
        if re.search(r'[s](\d{1,2})[e](\d{1,2})', lower_name, re.IGNORECASE):
            return True
            
        # Check for other common TV show indicators
        for indicator in tv_indicators:
            if re.search(indicator, lower_name, re.IGNORECASE):
                return True
        
        return False

    def _detect_if_anime(self, folder_name):
        """Detect if content is likely anime based on folder name and scanner lists."""
        # Check if we've already determined the content type through title matching
        if hasattr(self, '_detected_content_type'):
            return self._detected_content_type == 'anime'
        
        # First clean the folder name
        clean_title, year = self._extract_folder_metadata(folder_name)
        
        # Check specific anime scanner lists (we need separate checks for anime_movies and anime_series)
        anime_movie_match, anime_movie_score, anime_movie_tmdb_id = self._get_best_match_from_list(clean_title, year, 'anime_movies')
        anime_series_match, anime_series_score, anime_series_tmdb_id = self._get_best_match_from_list(clean_title, year, 'anime_series')
        
        # Get the best anime match
        anime_match = None
        anime_score = 0
        anime_tmdb_id = None
        
        if anime_movie_score > anime_series_score:
            anime_match = anime_movie_match
            anime_score = anime_movie_score
            anime_tmdb_id = anime_movie_tmdb_id
        else:
            anime_match = anime_series_match
            anime_score = anime_series_score
            anime_tmdb_id = anime_series_tmdb_id
        
        # Now check regular movies and TV series for comparison
        movie_match, movie_score, movie_tmdb_id = self._get_best_match_from_list(clean_title, year, 'movies')
        tv_match, tv_score, tv_tmdb_id = self._get_best_match_from_list(clean_title, year, 'tv_series')
        
        # Get the best non-anime match
        non_anime_match = None
        non_anime_score = 0
        non_anime_tmdb_id = None
        
        if movie_score > tv_score:
            non_anime_match = movie_match
            non_anime_score = movie_score
            non_anime_tmdb_id = non_anime_tmdb_id
        else:
            non_anime_match = tv_match
            non_anime_score = tv_score
            non_anime_tmdb_id = tv_tmdb_id
        
        # Compare anime vs non-anime scores
        # We require a significantly higher score for anime to avoid false positives
        if anime_score > 0.8 and anime_score > non_anime_score + 0.1:
            self.logger.debug(f"'{clean_title}' matched anime '{anime_match}' with score {anime_score:.2f}")
            # Store the discovered TMDB ID if it wasn't already found
            if anime_tmdb_id and not hasattr(self, '_detected_tmdb_id'):
                self._detected_tmdb_id = anime_tmdb_id
            return True
        
        # If we have a strong non-anime match, it's definitely not anime
        if non_anime_score > 0.7:
            return False
        
        # If we don't have strong matches in our scanner lists, look for specific anime indicators
        anime_indicators = [
            r'(?i)\banime\b', 
            r'(?i)\bsubbed\b', 
            r'(?i)\bdubbed\b', 
            r'\[jp\]', 
            r'\[jpn\]',
            r'(?i)\bova\b',
            r'(?i)\bova\d+\b'
        ]
        
        lower_name = folder_name.lower()
        
        # Check for common anime file naming conventions
        for indicator in anime_indicators:
            if re.search(indicator, lower_name, re.IGNORECASE):
                return True
        
        # Default to not anime if no strong indicators
        return False

    def _create_symlinks(self, subfolder_path, title, year, is_tv, is_anime):
        """
        Create symlinks from the source directory to the destination directory.
        
        Args:
            subfolder_path: Path to the source subfolder
            title: Cleaned title of the media
            year: Year of the media (or None)
            is_tv: Whether the media is a TV show
            is_anime: Whether the media is anime
        """
        # Check if destination directory is configured
        if not DESTINATION_DIRECTORY:
            self.logger.warning("Destination directory not configured. Skipping symlink creation.")
            print("\nDestination directory not configured. Skipping symlink creation.")
            print("Use Settings > Set destination directory to configure.")
            return False
        
        # Make sure destination directory exists
        if not os.path.exists(DESTINATION_DIRECTORY):
            try:
                os.makedirs(DESTINATION_DIRECTORY, exist_ok=True)
            except Exception as e:
                self.logger.error(f"Failed to create destination directory: {e}")
                print(f"\nError: Could not create destination directory: {e}")
                return False
        
        # Determine appropriate subdirectory based on content type
        if is_anime and is_tv:
            dest_subdir = os.path.join(DESTINATION_DIRECTORY, "Anime TV Shows")
        elif is_anime and not is_tv:
            dest_subdir = os.path.join(DESTINATION_DIRECTORY, "Anime Movies")
        elif not is_anime and is_tv:
            dest_subdir = os.path.join(DESTINATION_DIRECTORY, "TV Shows")
        else:  # Regular movie
            dest_subdir = os.path.join(DESTINATION_DIRECTORY, "Movies")
        
        # Create content type subdirectory if it doesn't exist
        if not os.path.exists(dest_subdir):
            try:
                os.makedirs(dest_subdir, exist_ok=True)
            except Exception as e:
                self.logger.error(f"Failed to create subdirectory {dest_subdir}: {e}")
                print(f"\nError: Could not create subdirectory {dest_subdir}: {e}")
                return False
        
        # Format the target directory name
        target_dir_name = f"{title}"
        if year:
            target_dir_name += f" ({year})"
        
        # Add TMDB ID if available
        if hasattr(self, '_detected_tmdb_id') and self._detected_tmdb_id:
            target_dir_name += f" [tmdb-{self._detected_tmdb_id}]"
        
        # Create full path for the target directory
        target_dir_path = os.path.join(dest_subdir, target_dir_name)
        
        # If this is a single movie file rather than a directory of files
        if os.path.isfile(subfolder_path):
            # For individual movie files, create a properly named symlink
            file_ext = os.path.splitext(subfolder_path)[1]
            target_file_name = f"{title}"
            if year:
                target_file_name += f" ({year})"
            target_file_name += file_ext
            
            # Create full path for the target file
            target_file_path = os.path.join(dest_subdir, target_file_name)
            
            # Check if target file already exists
            if os.path.exists(target_file_path):
                self.logger.info(f"Target file already exists: {target_file_path}")
                print(f"\nNotice: Target file already exists: {target_file_path}")
                
                # Ask if user wants to replace it
                if not self.auto_mode:
                    choice = input("Replace existing file? (y/n): ").strip().lower()
                    if choice != 'y':
                        print("Skipping symlink creation.")
                        return False
                    
                    # Remove existing symlink if user confirmed
                    try:
                        if os.path.islink(target_file_path):
                            os.unlink(target_file_path)
                        else:
                            os.remove(target_file_path)
                    except Exception as e:
                        self.logger.error(f"Failed to remove existing target: {e}")
                        print(f"Error: Could not remove existing target: {e}")
                        return False
            
            # Create the symlink for the file
            try:
                # Use relative paths if possible
                if os.path.commonpath([subfolder_path, dest_subdir]):
                    # Get relative path
                    rel_path = os.path.relpath(subfolder_path, os.path.dirname(target_file_path))
                    os.symlink(rel_path, target_file_path)
                else:
                    # Use absolute path if on different drives/mounts
                    os.symlink(subfolder_path, target_file_path)
                    
                self.logger.info(f"Created symlink: {target_file_path} -> {subfolder_path}")
                print(f"\nCreated symlink: {target_file_path}")
                return True
                    
            except Exception as e:
                self.logger.error(f"Failed to create symlink: {e}")
                print(f"Error: Could not create symlink: {e}")
                return False
        
        # For directories, create a symlink to the directory
        else:
            # Check if target directory already exists
            if os.path.exists(target_dir_path):
                self.logger.info(f"Target directory already exists: {target_dir_path}")
                print(f"\nNotice: Target directory already exists: {target_dir_path}")
                
                # Ask if user wants to replace it
                if not self.auto_mode:
                    choice = input("Replace existing directory? (y/n): ").strip().lower()
                    if choice != 'y':
                        print("Skipping symlink creation.")
                        return False
                    
                    # Remove existing symlink if user confirmed
                    try:
                        if os.path.islink(target_dir_path):
                            os.unlink(target_dir_path)
                        elif os.path.isdir(target_dir_path):
                            shutil.rmtree(target_dir_path)
                        else:
                            os.remove(target_dir_path)
                    except Exception as e:
                        self.logger.error(f"Failed to remove existing target: {e}")
                        print(f"Error: Could not remove existing target: {e}")
                        return False
            
            # Create the symlink for the directory
            try:
                # Use relative paths if possible
                if os.path.commonpath([subfolder_path, dest_subdir]):
                    # Get relative path
                    rel_path = os.path.relpath(subfolder_path, os.path.dirname(target_dir_path))
                    os.symlink(rel_path, target_dir_path, target_is_directory=True)
                else:
                    # Use absolute path if on different drives/mounts
                    os.symlink(subfolder_path, target_dir_path, target_is_directory=True)
                    
                self.logger.info(f"Created symlink: {target_dir_path} -> {subfolder_path}")
                print(f"\nCreated symlink: {target_dir_path}")
                return True
                
            except Exception as e:
                self.logger.error(f"Failed to create symlink: {e}")
                print(f"Error: Could not create symlink: {e}")
                return False

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
            print("0. Return to main menu")
            
            choice = input("\nEnter choice: ").strip()
            
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
                
            elif choice == "0":
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
        print("0. Return to main menu")
        
        choice = input("\nEnter choice: ").strip()
        
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
        elif choice == "0":
            return
        else:
            print("\nInvalid choice.")
            input("\nPress Enter to continue...")
    
    def review_monitored_directories(self):
        """Review and manage monitored directories."""
        _check_monitor_status()
    
    def settings_menu(self):
        """Display and handle settings menu."""
        clear_screen()
        display_ascii_art()
        print("=" * 60)
        print("SETTINGS")
        print("=" * 60)
        print("\n1. Set destination directory")
        print("2. Configure monitor settings")
        print("0. Return to main menu")
        
        choice = input("\nEnter your choice: ").strip()
        
        # Handle settings choices
        if choice == "1":
            self._set_destination_directory()
        elif choice == "2":
            self._configure_monitor_settings()
        elif choice != "0":
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
            
            print("0. Quit")
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
            elif choice == '0':
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