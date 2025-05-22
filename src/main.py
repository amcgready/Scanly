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
import requests

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
                    
                    # Interactive mode with options loop
                    while True:
                        print("\nOptions:")
                        print("1. Accept")
                        print("2. Change title/year")
                        print("3. Change content type") 
                        print("4. Skip (save for later review)")
                        print("5. Remove from review list")
                        print("0. Return to skipped items menu")
                        
                        choice = input("\nEnter choice (1-5, or press Enter for option 1): ")


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
                            break  # Exit the inner loop
                            
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
                            # Continue in the loop to allow more changes
                            
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
                            
                            # Update content type variables for current session
                            is_tv = item['is_tv']
                            is_anime = item['is_anime']
                            content_type = "TV Show" if is_tv else "Movie"
                            anime_label = " (Anime)" if is_anime else ""
                            
                            # Update registry
                            save_skipped_items(skipped_items_registry)
                            
                            print(f"\nContent type updated to: {content_type}{anime_label}")
                            # Continue in the loop to allow more changes
                            
                        elif choice == "4":
                            # Skip and keep in review list
                            print(f"\nSkipped: {subfolder_name}")
                            input("\nPress Enter to continue...")
                            break  # Exit the inner loop
                            
                        elif choice == "5":
                            # Remove from review list
                            skipped_items_registry.pop(item_index)
                            save_skipped_items(skipped_items_registry)
                            print(f"\nRemoved {subfolder_name} from review list.")
                            input("\nPress Enter to continue...")
                            break  # Exit the inner loop
                            
                        elif choice == "0":
                            # Return to skipped items menu
                            break  # Exit the inner loop
                            
                        else:
                            print("\nInvalid choice. Please try again.")
                            
                else:
                    print(f"\nError: Item path not found: {path}")
                    print("Would you like to remove this item from the review list? (y/n)")
                    if input("> ").strip().lower() == 'y':
                        skipped_items_registry.pop(item_index)
                        save_skipped_items(skipped_items_registry)
                        print(f"\nRemoved item from review list.")
                    input("\nPress Enter to continue...")
            else:
                print(f"\nInvalid item number.")
                input("\nPress Enter to continue...")
                
        elif choice == "2":
            # Clear all skipped items
            clear_skipped_items()
            break
            
        elif choice == "3" and total_pages > 1:
            # Next page
            current_page = current_page % total_pages + 1
            
        elif choice == "4" and total_pages > 1:
            # Previous page
            current_page = (current_page - 2) % total_pages + 1
            
        elif choice == "0":
            # Return to main menu
            break
            
        else:
            print("\nInvalid choice. Please try again.")
            input("\nPress Enter to continue...")

class DirectoryProcessor:
    """Process a directory of media files."""
    
    def __init__(self, directory_path, resume=False, auto_mode=False):
        """Initialize the directory processor."""
        self.directory_path = directory_path
        self.resume = resume
        self.auto_mode = auto_mode
        self.logger = get_logger(__name__)
    
    def process(self):
        """Process the directory."""
        try:
            print(f"\nProcessing directory: {self.directory_path}")
            self._process_media_files()
            return True
        except Exception as e:
            self.logger.error(f"Error processing directory {self.directory_path}: {e}", exc_info=True)
            print(f"Error: {e}")
            return False
    
    def _extract_folder_metadata(self, folder_name):
        """Extract title and year from folder name."""
        # Check for year in parentheses
        year_match = re.search(r'\((\d{4})\)', folder_name)
        year = year_match.group(1) if year_match else None
        
        # Extract title by removing year and cleaning up
        title = folder_name
        if year_match:
            title = folder_name[:year_match.start()].strip()
        
        # Clean up title (remove brackets, dots, underscores, etc.)
        title = re.sub(r'[._\[\]]', ' ', title)
        title = re.sub(r'\s+', ' ', title).strip()
        
        return title, year
    
    def _detect_if_tv_show(self, folder_name):
        """Detect if the folder contains a TV show."""
        tv_patterns = [
            r'\bS\d+\b',            # S01, S02, etc.
            r'\bseason\s*\d+\b',    # Season 1, Season 2, etc.
            r'\bseries\b',          # "Series" in the name
            r'(?<!\d)(?:\d{1,2}x\d{2})(?!\d)',  # 1x01, 2x13, etc.
            r'\bepisodes?\b',       # "Episode" or "Episodes"
            r'\bcomplete\b',        # Often indicates complete series
        ]
        
        # Case-insensitive check for TV patterns
        folder_lower = folder_name.lower()
        for pattern in tv_patterns:
            if re.search(pattern, folder_lower, re.IGNORECASE):
                return True
        
        # Check if folder contains files with episode naming patterns
        for root, _, files in os.walk(os.path.join(self.directory_path, folder_name)):
            for file in files:
                if file.endswith(('.mp4', '.mkv', '.avi', '.mov', '.wmv', '.m4v')):
                    # Common episode naming patterns: S01E01, 1x01, E01, etc.
                    ep_patterns = [
                        r'\bS\d+E\d+\b',         # S01E01
                        r'\bs\d+\s*e\d+\b',      # s01 e01
                        r'(?<!\d)(?:\d{1,2}x\d{2})(?!\d)',  # 1x01
                        r'\bE\d+\b',             # E01
                        r'\bEP\d+\b',            # EP01
                        r'\bEpisode\s*\d+\b',    # Episode 01
                    ]
                    
                    file_lower = file.lower()
                    for pattern in ep_patterns:
                        if re.search(pattern, file_lower, re.IGNORECASE):
                            return True
        
        return False
    
    def _detect_if_anime(self, folder_name):
        """Detect if the folder contains anime."""
        anime_patterns = [
            r'\banime\b',
            r'\bjapanese\b',
            r'\bsub(bed|titled)?\b',
            r'\braw\b',
            r'\bsenpai\b',
            r'\botaku\b',
            r'\bnekonime\b',
            r'\bcr\b',  # Common in anime release groups
            r'\bhorriblesubs\b',
            r'\bnyaa\b',
            r'\bfansub\b'
        ]
        
        # Case-insensitive check for anime patterns
        folder_lower = folder_name.lower()
        for pattern in anime_patterns:
            if re.search(pattern, folder_lower, re.IGNORECASE):
                return True
        
        return False
    
    def _create_symlinks(self, subfolder_path, title, year, is_tv, is_anime):
        """Create symbolic links to the media files."""
        # Get destination directory from environment
        dest_dir = os.environ.get('DESTINATION_DIRECTORY', '')
        if not dest_dir:
            print("\nError: Destination directory not set.")
            print("Please set the DESTINATION_DIRECTORY in the settings menu.")
            return False
        
        # Determine the target subdirectory based on content type
        if is_tv:
            if is_anime:
                target_subdir = os.path.join(dest_dir, "TV Shows", "Anime")
            else:
                target_subdir = os.path.join(dest_dir, "TV Shows")
        else:
            if is_anime:
                target_subdir = os.path.join(dest_dir, "Movies", "Anime")
            else:
                target_subdir = os.path.join(dest_dir, "Movies")
        
        # Create the target subdirectory if it doesn't exist
        if not os.path.exists(target_subdir):
            os.makedirs(target_subdir)
        
        # Create a folder for the title in the target subdirectory
        title_folder = title
        if year:
            title_folder = f"{title} ({year})"
        
        target_folder = os.path.join(target_subdir, title_folder)
        
        # Create the title folder if it doesn't exist
        if not os.path.exists(target_folder):
            os.makedirs(target_folder)
        
        # Create symbolic links for all media files in the subfolder
        symlink_count = 0
        
        # Use symlinks by default, but can be overridden to use copies
        use_symlinks = os.environ.get('USE_SYMLINKS', 'true').lower() == 'true'
        
        for root, _, files in os.walk(subfolder_path):
            for file in files:
                if file.endswith(('.mp4', '.mkv', '.avi', '.mov', '.wmv', '.m4v')):
                    source_file = os.path.join(root, file)
                    target_file = os.path.join(target_folder, file)
                    
                    # Skip if target already exists
                    if os.path.exists(target_file):
                        continue
                    
                    try:
                        if use_symlinks:
                            # Create symbolic link
                            os.symlink(source_file, target_file)
                        else:
                            # Copy the file
                            shutil.copy2(source_file, target_file)
                        
                        symlink_count += 1
                    except Exception as e:
                        self.logger.error(f"Error creating link for {file}: {e}")
                        print(f"Error linking {file}: {e}")
        
        print(f"\nCreated {symlink_count} links in {target_folder}")
        return symlink_count > 0
    
    def _process_media_files(self):
        """Process media files in the directory."""
        # Place global declaration at the beginning of function
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
                    print(f"\n[{processed}/{len(subdirs)}] Processing: {subfolder_name}")
                    
                    # Extract title and year from folder name
                    title, year = self._extract_folder_metadata(subfolder_name)
                    
                    # Detect if it's a TV show or movie
                    is_tv = self._detect_if_tv_show(subfolder_name)
                    
                    # Detect if it's anime
                    is_anime = self._detect_if_anime(subfolder_name)
                    
                    # Set the content type string for display
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
                        symlink_success = self._create_symlinks(subfolder_path, title, year, is_tv, is_anime)
                        continue
                    
                    # Interactive mode with options loop
                    while True:
                        print("\nOptions:")
                        print("1. Accept")
                        print("2. Change title/year")
                        print("3. Change content type") 
                        print("4. Skip (save for later review)")
                        print("5. Quit to main menu")
                        
                        choice = input("\nEnter choice (1-5): ").strip()
                        
                        if choice == "1":
                            # Process with current detection
                            print(f"\nProcessing {subfolder_name} as {content_type}{anime_label}...")
                            
                            # Create symlinks
                            symlink_success = self._create_symlinks(subfolder_path, title, year, is_tv, is_anime)
                            
                            if symlink_success:
                                print(f"Successfully processed {subfolder_name}")
                            else:
                                print(f"Failed to create symlinks for {subfolder_name}")
                            
                            # Break the loop to move to next subfolder
                            break
                            
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
                            
                            print(f"\nUpdated to: {title} ({year if year else 'Unknown year'})")
                            # Continue the loop to show options again
                            
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
                                print("\nInvalid choice. Content type unchanged.")
                            
                            content_type = "TV Show" if is_tv else "Movie"
                            anime_label = " (Anime)" if is_anime else ""
                            
                            print(f"\nContent type updated to: {content_type}{anime_label}")
                            # Continue the loop to show options again
                            
                        elif choice == "4":
                            # Skip this folder
                            print(f"\nSkipped: {subfolder_name}")
                            # Add to skipped items registry
                            skip_item = {
                                'path': subfolder_path,
                                'subfolder': subfolder_name,
                                'suggested_name': title,
                                'is_tv': is_tv,
                                'is_anime': is_anime,
                                'error': "Skipped by user",
                                'timestamp': datetime.datetime.now().isoformat()
                            }
                            
                            skipped_items_registry.append(skip_item)
                            save_skipped_items(skipped_items_registry)
                            break  # Move to next subfolder
                            
                        elif choice == "5":
                            # Quit to main menu
                            print("\nReturning to main menu...")
                            return
                        
                        else:
                            print("\nInvalid choice. Please try again.")
                    
                except Exception as e:
                    self.logger.error(f"Error processing subfolder {subfolder_name}: {e}", exc_info=True)
                    print(f"Error processing {subfolder_name}: {e}")
                    
                    # Ask if user wants to skip this folder
                    print("\nDo you want to skip this folder? (y/n)")
                    if input("> ").strip().lower() == 'y':
                        # Add to skipped items registry with error information
                        skip_item = {
                            'path': subfolder_path,
                            'subfolder': subfolder_name,
                            'error': str(e),
                            'timestamp': datetime.datetime.now().isoformat()
                        }
                        skipped_items_registry.append(skip_item)
                        save_skipped_items(skipped_items_registry)
                        print(f"Added {subfolder_name} to skipped items.")
                    else:
                        # Re-raise the exception to stop processing
                        raise
            
            # Print the completion message INSIDE the try block
            print(f"\nFinished processing {len(subdirs)} subdirectories.")
            
        except Exception as e:
            self.logger.error(f"Error processing media files: {e}", exc_info=True)
            raise

# Function to check the monitor status
def _check_monitor_status():
    """Check the status of the monitor service."""
    try:
        from src.core.monitor import check_monitor_status
        check_monitor_status()
    except ImportError:
        print("\nMonitor module not available.")

# Main entry point
if __name__ == "__main__":
    try:
        # Initialize application
        clear_screen()
        display_ascii_art()
        
        # Display main menu
        while True:
            clear_screen()
            display_ascii_art()
            print("=" * 60)
            print("MAIN MENU")
            print("=" * 60)
            print("\nOptions:")
            print("1. Individual Scan")
            print("2. Multi Scan")
            
            # Check if there's a scan history to resume
            has_history = history_exists() and load_scan_history() and load_scan_history().get('path')
            if has_history:
                print("3. Resume Scan    - Resume a previously interrupted scan")
                print("   Clear History  - Delete scan history")

            # Check if there are skipped items to review
            has_skipped = skipped_items_registry and len(skipped_items_registry) > 0
            if has_skipped:
                print(f"4. Review Skipped - Review previously skipped items ({len(skipped_items_registry)})")
                print("   Clear Skipped  - Delete all skipped items")
            
            print("5. Settings")
            print("6. Help")
            print("0. Quit")
            
            choice = input("\nEnter choice (0-6): ").strip()
            
            if choice == "1":
                # Individual scan
                clear_screen()
                display_ascii_art()
                print("=" * 60)
                print("INDIVIDUAL SCAN")
                print("=" * 60)
                
                # Prompt for directory path
                print("\nEnter the path to scan (or press Enter to return to main menu):")
                dir_path = input("> ").strip()
                
                if not dir_path:
                    continue
                
                # Clean and validate the path
                dir_path = _clean_directory_path(dir_path)
                
                if not os.path.isdir(dir_path):
                    print(f"\nError: Invalid directory path: {dir_path}")
                    input("\nPress Enter to continue...")
                    continue
                
                # Process the directory
                processor = DirectoryProcessor(dir_path)
                processor.process()
                
                input("\nPress Enter to return to main menu...")
                
            elif choice == "2":
                # Multi scan
                clear_screen()
                display_ascii_art()
                print("=" * 60)
                print("MULTI SCAN")
                print("=" * 60)
                print("\nScan multiple directories (one per line)")
                print("Enter a blank line when finished")
                
                dirs_to_scan = []
                while True:
                    dir_path = input("> ").strip()
                    if not dir_path:
                        break
                    
                    # Clean and validate path
                    dir_path = _clean_directory_path(dir_path)
                    
                    if os.path.isdir(dir_path):
                        dirs_to_scan.append(dir_path)
                    else:
                        print(f"Warning: Invalid directory: {dir_path}")
                
                if not dirs_to_scan:
                    print("\nNo valid directories entered.")
                    input("\nPress Enter to continue...")
                    continue
                
                # Process each directory
                for dir_path in dirs_to_scan:
                    print(f"\nProcessing directory: {dir_path}")
                    processor = DirectoryProcessor(dir_path)
                    processor.process()
                
                input("\nAll directories processed. Press Enter to return to main menu...")
                
            elif choice == "3" and has_history:
                # Check if user wants to resume or clear history
                print("\nDo you want to resume the scan or clear the history?")
                print("1. Resume Scan")
                print("2. Clear History")
                sub_choice = input("\nEnter choice (1-2): ").strip()
                
                if sub_choice == "1":
                    # Resume scan logic
                    history = load_scan_history()
                    if not history or not history.get('path'):
                        print("\nInvalid scan history. Cannot resume.")
                        input("\nPress Enter to continue...")
                        continue
                    
                    resume_path = history.get('path')
                    if not os.path.isdir(resume_path):
                        print(f"\nPrevious scan directory no longer exists: {resume_path}")
                        input("\nPress Enter to continue...")
                        continue
                    
                    print(f"\nResuming scan of: {resume_path}")
                    processor = DirectoryProcessor(resume_path, resume=True)
                    processor.process()
                    
                    # Clear history after resuming
                    clear_scan_history()
                    
                    input("\nPress Enter to return to main menu...")
                
                elif sub_choice == "2":
                    # Clear history
                    clear_scan_history()
                    print("\nScan history cleared.")
                    input("\nPress Enter to return to main menu...")
            
            elif choice == "4" and has_skipped:
                # Check if user wants to review or clear skipped items
                print("\nDo you want to review skipped items or clear them?")
                print("1. Review Skipped Items")
                print("2. Clear Skipped Items")
                sub_choice = input("\nEnter choice (1-2): ").strip()
                
                if sub_choice == "1":
                    # Review skipped items
                    review_skipped_items()
                
                elif sub_choice == "2":
                    # Clear skipped items
                    clear_skipped_items()
            
            elif choice == "5":
                # Settings
                clear_screen()
                display_ascii_art()
                print("=" * 60)
                print("SETTINGS")
                print("=" * 60)
                print("\nCurrent settings:")
                
                dest_dir = os.environ.get('DESTINATION_DIRECTORY', '')
                print(f"1. Destination directory: {dest_dir if dest_dir else 'Not set'}")
                
                use_symlinks = os.environ.get('USE_SYMLINKS', 'true').lower() == 'true'
                print(f"2. Use symlinks: {'Yes' if use_symlinks else 'No (copy files)'}")
                
                include_tmdb = os.environ.get('INCLUDE_TMDB_ID', 'true').lower() == 'true'
                print(f"3. Include TMDB IDs: {'Yes' if include_tmdb else 'No'}")
                
                tmdb_api_key = os.environ.get('TMDB_API_KEY', '')
                print(f"4. TMDB API Key: {tmdb_api_key[:5] + '...' if tmdb_api_key else 'Not set'}")
                
                refresh_plex = os.environ.get('REFRESH_PLEX', 'true').lower() == 'true'
                print(f"5. Refresh Plex: {'Yes' if refresh_plex else 'No'}")
                
                print("\n6. Check monitor status")
                
                print("\n0. Return to main menu")
                
                setting_choice = input("\nEnter setting to change (0-6): ").strip()
                
                if setting_choice == "1":
                    print("\nEnter destination directory path:")
                    new_dest = input("> ").strip()
                    if new_dest:
                        new_dest = _clean_directory_path(new_dest)
                        _update_env_var('DESTINATION_DIRECTORY', new_dest)
                        print(f"\nDestination directory updated to: {new_dest}")
                        
                elif setting_choice == "2":
                    print("\nUse symlinks? (y/n):")
                    use_sym = input("> ").strip().lower()
                    _update_env_var('USE_SYMLINKS', 'true' if use_sym == 'y' else 'false')
                    print(f"\nUse symlinks set to: {'Yes' if use_sym == 'y' else 'No'}")
                    
                elif setting_choice == "3":
                    print("\nInclude TMDB IDs? (y/n):")
                    inc_tmdb = input("> ").strip().lower()
                    _update_env_var('INCLUDE_TMDB_ID', 'true' if inc_tmdb == 'y' else 'false')
                    print(f"\nInclude TMDB IDs set to: {'Yes' if inc_tmdb == 'y' else 'No'}")
                    
                elif setting_choice == "4":
                    print("\nEnter TMDB API Key (leave blank to keep current):")
                    api_key = input("> ").strip()
                    if api_key:
                        _update_env_var('TMDB_API_KEY', api_key)
                        print("\nTMDB API Key updated.")
                        
                elif setting_choice == "5":
                    print("\nRefresh Plex after processing? (y/n):")
                    ref_plex = input("> ").strip().lower()
                    _update_env_var('REFRESH_PLEX', 'true' if ref_plex == 'y' else 'false')
                    print(f"\nRefresh Plex set to: {'Yes' if ref_plex == 'y' else 'No'}")
                    
                elif setting_choice == "6":
                    _check_monitor_status()
                
                input("\nPress Enter to continue...")
                
            elif choice == "6":
                # Help information
                display_help()
                
            elif choice == "0":
                # Quit
                print("\nExiting Scanly. Goodbye!")
                break
                
            else:
                print("\nInvalid choice. Please enter a number from 0 to 6.")
                input("\nPress Enter to continue...")
    
    except Exception as e:
        logger.error(f"Unhandled exception in main: {e}", exc_info=True)
        print(f"\nError: {e}")
        print("\nAn unexpected error occurred. Check the logs for details.")
        input("\nPress Enter to exit...")