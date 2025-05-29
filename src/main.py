#!/usr/bin/env python3
"""Scanly: A media file scanner and organizer.

This module is the main entry point for the Scanly application.
"""
import logging
import os
import sys
import json
import re
import traceback
import requests
import datetime
from pathlib import Path

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
        
        # Filter out specific scanner matching messages EXCEPT our new visible checks with ✓
        if record.msg and "✓" not in str(record.msg) and any(pattern in str(record.msg) for pattern in [
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
            try:
                idx = int(idx) - 1
                if 0 <= idx < len(skipped_items_registry):
                    item = skipped_items_registry[idx]
                    # Process the item here
                    print(f"\nProcessing: {item.get('subfolder', 'Unknown')}")
                    # Implementation would go here
                    input("\nPress Enter to continue...")
                else:
                    print("\nInvalid item number.")
                    input("\nPress Enter to continue...")
            except ValueError:
                print("\nInvalid input. Please enter a number.")
                input("\nPress Enter to continue...")
        elif choice == "2":
            # Confirm before clearing
            confirm = input("\nAre you sure you want to clear all skipped items? (y/n): ").strip().lower()
            if confirm == 'y':
                clear_skipped_items()
                break
        elif choice == "3" and total_pages > 1:
            # Next page
            if current_page < total_pages:
                current_page += 1
        elif choice == "4" and total_pages > 1:
            # Previous page
            if current_page > 1:
                current_page -= 1
        elif choice == "0":
            return
        else:
            print("\nInvalid option.")
            input("\nPress Enter to continue...")

def _check_monitor_status():
    """Check and fix the monitor status if needed."""
    try:
        from src.core.monitor import MonitorManager
        
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
    except ImportError:
        print("\nMonitor module not found. Please check your installation.")
        input("\nPress Enter to continue...")
    except Exception as e:
        print(f"\nError checking monitor status: {e}")
        input("\nPress Enter to continue...")

class DirectoryProcessor:
    """Process a directory of media files."""
    def __init__(self, directory_path, resume=False, auto_mode=False):
        self.directory_path = directory_path
        self.resume = resume
        self.auto_mode = auto_mode
        self.logger = get_logger(__name__)
        
        # Initialize detection state variables
        self._detected_content_type = None
        self._detected_tmdb_id = None
    
    def _check_scanner_lists(self):
        """Check scanner lists for known titles."""
        return []
    
    def _extract_folder_metadata(self, folder_name):
        """Extract title and year from a folder name."""
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
            r'(?i)\b(BluRay|Blu Ray|Blu-ray|BD|REMUX|BDRemux|BDRip|DVDRip|HDTV|WebRip|WEB-DL|WEBRip|Web|HDRip|DVD|DVDR)\b',
            
            # Codec patterns
            r'(?i)\b(xvid|divx|x264|x265|hevc|h264|h265|HEVC|avc|vp9|av1)\b',
            
            # Audio patterns
            r'(?i)\b(DTS[-\.]?(HD|ES|X)?|DD5\.1|AAC|AC3|TrueHD|Atmos|MA|5\.1|7\.1|2\.0|opus)\b',
            
            # Release group patterns (in brackets or after hyphen)
            r'(?i)(\[.*?\]|\-[a-zA-Z0-9_]+$)',

            # Common release group names
            r'(?i)\b(AMZN|EfficientNeatChachalacaOfOpportunityTGx|SPRiNTER|KRaLiMaRKo|DVT|TheEqualizer|YIFY|NTG|YTS|SPARKS|RARBG|EVO|GHOST|HDCAM|CAM|TS|SCREAM|ExKinoRay)\b',
            
            # Other common patterns
            r'(?i)\b(HDR|VC|10bit|8bit|Hi10P|IMAX|PROPER|REPACK|HYBRID|DV)\b'
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
        
        self.logger.debug(f"Original: '{folder_name}', Cleaned: '{clean_title}', Year: {year}")
        return clean_title, year

    def _detect_if_tv_show(self, folder_name):
        """Detect if a folder contains a TV show based on its name and content."""
        # Simple TV show detection based on folder name patterns
        folder_lower = folder_name.lower()
        
        # Check for common TV show indicators
        if re.search(r'season|episode|s\d+e\d+|complete series|tv series', folder_lower):
            return True
            
        # Check for episode pattern like S01E01, s01e01, etc.
        if re.search(r'[s](\d{1,2})[e](\d{1,2})', folder_lower):
            return True
        
        return False

    def _detect_if_anime(self, folder_name):
        """Detect if content is likely anime based on folder name."""
        # Simple anime detection based on folder name
        folder_lower = folder_name.lower()
        
        # Check for common anime indicators
        anime_indicators = [
            r'anime', r'subbed', r'dubbed', r'\[jp\]', r'\[jpn\]', r'ova\b', 
            r'ova\d+', r'アニメ', r'japanese animation'
        ]
        
        for indicator in anime_indicators:
            if re.search(indicator, folder_lower, re.IGNORECASE):
                return True
        
        return False

    def _create_symlinks(self, subfolder_path, title, year, is_tv=False, is_anime=False):
        """Create symlinks from the source directory to the destination directory."""
        try:
            # Check if destination directory is configured
            if not DESTINATION_DIRECTORY:
                print("\nDestination directory not set. Please configure in Settings.")
                return False
            
            # Make sure destination directory exists
            if not os.path.exists(DESTINATION_DIRECTORY):
                os.makedirs(DESTINATION_DIRECTORY, exist_ok=True)
            
            # Format the base name with year for both folder and files
            base_name = title
            if year and not is_tv:
                base_name = f"{title} ({year})"
            
            # Determine appropriate subdirectory based on content type
            if is_anime and is_tv:
                dest_subdir = os.path.join(DESTINATION_DIRECTORY, "Anime Series")
            elif is_anime and not is_tv:
                dest_subdir = os.path.join(DESTINATION_DIRECTORY, "Anime Movies")
            elif not is_anime and is_tv:
                dest_subdir = os.path.join(DESTINATION_DIRECTORY, "TV Shows")
            else:
                dest_subdir = os.path.join(DESTINATION_DIRECTORY, "Movies")
            
            # Create content type subdirectory if it doesn't exist
            if not os.path.exists(dest_subdir):
                os.makedirs(dest_subdir, exist_ok=True)
            
            # Format the folder name
            folder_name = base_name
            
            # Create full path for the target directory
            target_dir_path = os.path.join(dest_subdir, folder_name)
            
            # Create the target directory if it doesn't exist
            if not os.path.exists(target_dir_path):
                os.makedirs(target_dir_path, exist_ok=True)
            
            # Check if using symlinks or copies
            use_symlinks = os.environ.get('USE_SYMLINKS', 'true').lower() == 'true'
            
            # Process files in subfolder
            for root, dirs, files in os.walk(subfolder_path):
                for file in files:
                    if file.lower().endswith(('.mkv', '.mp4', '.avi', '.mov')):
                        source_file = os.path.join(root, file)
                        target_file = os.path.join(target_dir_path, file)
                        
                        if use_symlinks:
                            if os.path.exists(target_file):
                                os.remove(target_file)
                            os.symlink(source_file, target_file)
                        else:
                            import shutil
                            shutil.copy2(source_file, target_file)
            
            self.logger.info(f"Successfully created links in: {target_dir_path}")
            print(f"\nSuccessfully created links in: {target_dir_path}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error creating symlinks: {e}")
            print(f"\nError creating links: {e}")
            return False
    
    def _process_media_files(self):
        """Process media files in the directory."""
        # Place global declaration at the beginning of function
        global skipped_items_registry
        
        try:
            # Get all subdirectories
            subdirs = [d for d in os.listdir(self.directory_path) 
                      if os.path.isdir(os.path.join(self.directory_path, d))]
            
            if not subdirs:
                print("\nNo subdirectories found to process.")
                input("\nPress Enter to continue...")
                return
                
            print(f"Found {len(subdirs)} subdirectories to process")
            
            # Track progress
            processed = 0
            
            # Process each subfolder
            for subfolder_name in subdirs:
                subfolder_path = os.path.join(self.directory_path, subfolder_name)
                
                # Extract metadata from folder name
                title, year = self._extract_folder_metadata(subfolder_name)
                
                # Detect if this is a TV show or anime
                is_tv = self._detect_if_tv_show(subfolder_name)
                is_anime = self._detect_if_anime(subfolder_name)
                
                print(f"\nProcessing: {subfolder_name}")
                print(f"  Title: {title}")
                print(f"  Year: {year if year else 'Unknown'}")
                print(f"  Type: {'TV Show' if is_tv else 'Movie'}")
                print(f"  Genre: {'Anime' if is_anime else 'Live Action'}")
                
                # Show options for this subfolder
                while True:
                    print("\nOptions:")
                    print("1. Use extracted info (auto-process)")
                    print("2. Edit title/year")
                    print("3. Skip this subfolder")
                    print("4. Skip all remaining subfolders")
                    print("0. Cancel scan")
                    
                    choice = input("\nSelect option: ").strip()
                    
                    if choice == "1":
                        # Use extracted info
                        if self._create_symlinks(subfolder_path, title, year, is_tv, is_anime):
                            processed += 1
                        break
                    elif choice == "2":
                        # Edit title/year
                        new_title = input(f"Enter title [{title}]: ").strip()
                        if new_title:
                            title = new_title
                        
                        new_year = input(f"Enter year [{year if year else 'Unknown'}]: ").strip()
                        if new_year and re.match(r'^(19|20)\d{2}$', new_year):
                            year = new_year
                        
                        # Type selection
                        print("\nSelect content type:")
                        print("1. Movie")
                        print("2. TV Show")
                        type_choice = input(f"Enter choice [{2 if is_tv else 1}]: ").strip()
                        is_tv = type_choice == "2" if type_choice in ["1", "2"] else is_tv
                        
                        # Genre selection
                        print("\nSelect genre:")
                        print("1. Live Action")
                        print("2. Anime")
                        genre_choice = input(f"Enter choice [{2 if is_anime else 1}]: ").strip()
                        is_anime = genre_choice == "2" if genre_choice in ["1", "2"] else is_anime
                        
                        print(f"\nUpdated info:")
                        print(f"  Title: {title}")
                        print(f"  Year: {year if year else 'Unknown'}")
                        print(f"  Type: {'TV Show' if is_tv else 'Movie'}")
                        print(f"  Genre: {'Anime' if is_anime else 'Live Action'}")
                        
                        confirm = input("\nUse this info? (y/n): ").strip().lower()
                        if confirm == 'y':
                            if self._create_symlinks(subfolder_path, title, year, is_tv, is_anime):
                                processed += 1
                            break
                    elif choice == "3":
                        # Skip this subfolder
                        print(f"Skipping subfolder: {subfolder_name}")
                        skipped_items_registry.append({
                            'subfolder': subfolder_name,
                            'path': subfolder_path,
                            'skipped_date': datetime.datetime.now().isoformat()
                        })
                        save_skipped_items(skipped_items_registry)
                        break
                    elif choice == "4":
                        # Skip all remaining subfolders
                        print("Skipping all remaining subfolders.")
                        return processed
                    elif choice == "0":
                        # Cancel scan
                        if input("Are you sure you want to cancel the scan? (y/n): ").strip().lower() == 'y':
                            print("Scan cancelled.")
                            return -1
                    else:
                        print("Invalid option. Please try again.")
            
            print(f"\nFinished processing {len(subdirs)} subdirectories.")
            return processed
            
        except Exception as e:
            self.logger.error(f"Error processing media files: {e}")
            print(f"Error: {e}")
            return -1
    
    def process(self):
        """Process the directory."""
        try:
            self.logger.info(f"Processing directory: {self.directory_path}")
            
            # Check if directory exists
            if not os.path.isdir(self.directory_path):
                print(f"Directory not found: {self.directory_path}")
                input("\nPress Enter to continue...")
                return False
            
            print(f"\nProcessing directory: {self.directory_path}")
            
            # Process media files in the directory
            result = self._process_media_files()
            
            if result == -1:
                print("\nScan was cancelled.")
            elif result is not None:
                print(f"\nProcessed {result} subfolders successfully.")
            
            print("\nPress Enter to continue...")
            input()
            
            return True
        except Exception as e:
            self.logger.error(f"Error processing directory {self.directory_path}: {e}")
            traceback.print_exc()
            print(f"\nError: {e}")
            print("\nPress Enter to continue...")
            input()
            return False

class SettingsMenu:
    """Settings menu handler for the application."""
    
    def __init__(self):
        self.logger = get_logger(__name__)
        self.env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')
    
    def display(self):
        """Display the settings menu."""
        while True:
            clear_screen()
            display_ascii_art()
            print("=" * 60)
            print("SETTINGS")
            print("=" * 60)
            
            print("\nSettings Categories:")
            print("1. Directory Settings")
            print("2. TMDB API Settings")
            print("3. File Management Settings")
            print("4. Monitoring Settings")
            print("5. Advanced Settings")
            print("6. View Current Configuration")
            print("q. Return to Main Menu")
            
            choice = input("\nSelect category (1-6, q): ").strip().lower()
            
            if choice == '1':
                self._directory_settings()
            elif choice == '2':
                self._tmdb_settings()
            elif choice == '3':
                self._file_management_settings()
            elif choice == '4':
                self._monitoring_settings()
            elif choice == '5':
                self._advanced_settings()
            elif choice == '6':
                self._view_all_settings()
            elif choice == 'q':
                return
            else:
                print("\nInvalid choice.")
                input("\nPress Enter to continue...")
    
    def _directory_settings(self):
        """Directory settings submenu."""
        while True:
            clear_screen()
            display_ascii_art()
            print("=" * 60)
            print("DIRECTORY SETTINGS")
            print("=" * 60)
            
            destination_dir = os.environ.get('DESTINATION_DIRECTORY', 'Not set')
            
            print(f"\nCurrent Destination Directory: {destination_dir}")
            print("\nOptions:")
            print("1. Change Destination Directory")
            print("q. Return to Settings Menu")
            
            choice = input("\nEnter choice: ").strip().lower()
            
            if choice == '1':
                new_dir = input("\nEnter new destination directory: ").strip()
                new_dir = _clean_directory_path(new_dir)
                if new_dir:
                    _update_env_var('DESTINATION_DIRECTORY', new_dir)
                    print(f"\nDestination directory set to: {new_dir}")
                    global DESTINATION_DIRECTORY
                    DESTINATION_DIRECTORY = new_dir
                    input("\nPress Enter to continue...")
            elif choice == 'q':
                return
            else:
                print("\nInvalid choice.")
                input("\nPress Enter to continue...")
    
    def _tmdb_settings(self):
        """TMDB API settings submenu."""
        while True:
            clear_screen()
            display_ascii_art()
            print("=" * 60)
            print("TMDB API SETTINGS")
            print("=" * 60)
            
            api_key = os.environ.get('TMDB_API_KEY', 'Not set')
            
            # Mask API key for display
            masked_key = "****" if api_key != 'Not set' else 'Not set'
            print(f"\nCurrent API Key: {masked_key}")
            
            print("\nOptions:")
            print("1. Set API Key")
            print("2. Test API Connection")
            print("q. Return to Settings Menu")
            
            choice = input("\nEnter choice: ").strip().lower()
            
            if choice == '1':
                new_key = input("\nEnter TMDB API key: ").strip()
                if new_key:
                    _update_env_var('TMDB_API_KEY', new_key)
                    print("\nAPI Key updated.")
                    input("\nPress Enter to continue...")
            elif choice == '2':
                # Test API connection
                if api_key == 'Not set':
                    print("\nAPI key not set. Please set an API key first.")
                else:
                    print("\nTesting API connection...")
                    try:
                        # Simple API test
                        url = f"https://api.themoviedb.org/3/movie/550?api_key={api_key}"
                        response = requests.get(url, timeout=10)
                        if response.status_code == 200:
                            print("\nAPI connection successful!")
                        else:
                            print(f"\nAPI test failed with status code: {response.status_code}")
                            print(f"Error: {response.text}")
                    except Exception as e:
                        print(f"\nError testing API: {e}")
                input("\nPress Enter to continue...")
            elif choice == 'q':
                return
            else:
                print("\nInvalid choice.")
                input("\nPress Enter to continue...")
    
    def _file_management_settings(self):
        """File management settings submenu."""
        while True:
            clear_screen()
            display_ascii_art()
            print("=" * 60)
            print("FILE MANAGEMENT SETTINGS")
            print("=" * 60)
            
            use_symlinks = os.environ.get('USE_SYMLINKS', 'true').lower() == 'true'
            
            print(f"\nUse Symlinks: {'Enabled' if use_symlinks else 'Disabled'}")
            print("\nOptions:")
            print("1. Toggle Symlinks")
            print("2. Configure Plex Integration")
            print("q. Return to Settings Menu")
            
            choice = input("\nEnter choice: ").strip().lower()
            
            if choice == '1':
                new_value = 'false' if use_symlinks else 'true'
                _update_env_var('USE_SYMLINKS', new_value)
                print(f"\nSymlinks are now {'Enabled' if new_value == 'true' else 'Disabled'}.")
                input("\nPress Enter to continue...")
            elif choice == '2':
                self._configure_plex_settings()
            elif choice == 'q':
                return
            else:
                print("\nInvalid choice.")
                input("\nPress Enter to continue...")
    
    def _configure_plex_settings(self):
        """Configure Plex connection settings."""
        clear_screen()
        display_ascii_art()
        print("=" * 60)
        print("PLEX CONNECTION SETTINGS")
        print("=" * 60)
        
        # Get current settings
        current_url = os.environ.get('PLEX_URL', '')
        current_token = os.environ.get('PLEX_TOKEN', '')
        movies_section = os.environ.get('PLEX_MOVIES_SECTION', '1')
        tv_section = os.environ.get('PLEX_TV_SECTION', '2')
        anime_movies_section = os.environ.get('PLEX_ANIME_MOVIES_SECTION', '3')
        anime_tv_section = os.environ.get('PLEX_ANIME_TV_SECTION', '4')
        
        # Mask token display for security
        masked_token = "****" if current_token else ""
        
        print("\nCurrent Plex Settings:")
        print(f"1. Plex Server URL: {current_url or 'Not Set'}")
        print(f"2. Plex Token: {masked_token or 'Not Set'}")
        print(f"3. Movies Library Section: {movies_section}")
        print(f"4. TV Shows Library Section: {tv_section}")
        print(f"5. Anime Movies Library Section: {anime_movies_section}")
        print(f"6. Anime TV Library Section: {anime_tv_section}")
        print("7. Test Plex Connection")
        print("q. Return to File Management Settings")
        
        choice = input("\nSelect option (1-7, q): ").strip().lower()
        
        if choice == '1':
            new_url = input("\nEnter Plex server URL (e.g., http://localhost:32400): ").strip()
            if new_url:
                _update_env_var('PLEX_URL', new_url)
                print("\nPlex server URL updated.")
            
        elif choice == '2':
            new_token = input("\nEnter Plex token: ").strip()
            if new_token:
                _update_env_var('PLEX_TOKEN', new_token)
                print("\nPlex token updated.")
            
        elif choice == '3':
            new_section = input("\nEnter Movies library section ID: ").strip()
            if new_section:
                _update_env_var('PLEX_MOVIES_SECTION', new_section)
                print("\nMovies section updated.")
            
        elif choice == '4':
            new_section = input("\nEnter TV Shows library section ID: ").strip()
            if new_section:
                _update_env_var('PLEX_TV_SECTION', new_section)
                print("\nTV Shows section updated.")
            
        elif choice == '5':
            new_section = input("\nEnter Anime Movies library section ID: ").strip()
            if new_section:
                _update_env_var('PLEX_ANIME_MOVIES_SECTION', new_section)
                print("\nAnime Movies section updated.")
            
        elif choice == '6':
            new_section = input("\nEnter Anime TV library section ID: ").strip()
            if new_section:
                _update_env_var('PLEX_ANIME_TV_SECTION', new_section)
                print("\nAnime TV section updated.")
            
        elif choice == '7':
            self._test_plex_connection()
            
        elif choice == 'q':
            return
            
        else:
            print("\nInvalid choice.")
            
        # Return to this same menu
        self._configure_plex_settings()

    def _test_plex_connection(self):
        """Test connection to Plex server."""
        print("\nTesting Plex connection...")
        
        # Get Plex configuration
        plex_url = os.environ.get('PLEX_URL', '')
        plex_token = os.environ.get('PLEX_TOKEN', '')
        
        # Check if Plex is configured
        if not plex_url or not plex_token:
            print("\nPlex connection not configured. Please set URL and token first.")
            input("\nPress Enter to continue...")
            return
        
        try:
            # Make a simple API call to check connection
            url = f"{plex_url}/library/sections?X-Plex-Token={plex_token}"
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                print("\nPlex connection successful!")
                
                # Parse the XML to show available libraries
                print("\nAvailable libraries:")
                # In a real implementation, you would parse the XML response
                print("(Would display library sections here)")
            else:
                print(f"\nConnection failed with status code: {response.status_code}")
                print(f"Error: {response.text}")
        
        except Exception as e:
            print(f"\nError connecting to Plex: {e}")
        
        input("\nPress Enter to continue...")

    def _monitoring_settings(self):
        """Directory monitoring settings."""
        while True:
            clear_screen()
            display_ascii_art()
            print("=" * 60)
            print("MONITORING SETTINGS")
            print("=" * 60)
            
            interval = os.environ.get('MONITOR_INTERVAL_MINUTES', '60')
            
            print(f"\nCurrent monitoring interval: {interval} minutes")
            print("\nOptions:")
            print("1. Change monitoring interval")
            print("2. View monitored directories")
            print("q. Return to Settings Menu")
            
            choice = input("\nEnter choice: ").strip().lower()
            
            if choice == '1':
                new_interval = input("\nEnter monitoring interval in minutes: ").strip()
                if new_interval.isdigit() and int(new_interval) > 0:
                    _update_env_var('MONITOR_INTERVAL_MINUTES', new_interval)
                    print(f"\nMonitoring interval set to {new_interval} minutes.")
                else:
                    print("\nInvalid interval. Please enter a positive number.")
                input("\nPress Enter to continue...")
            elif choice == '2':
                _check_monitor_status()
            elif choice == 'q':
                return
            else:
                print("\nInvalid choice.")
                input("\nPress Enter to continue...")
    
    def _advanced_settings(self):
        """Advanced settings submenu."""
        while True:
            clear_screen()
            display_ascii_art()
            print("=" * 60)
            print("ADVANCED SETTINGS")
            print("=" * 60)
            
            log_level = os.environ.get('LOG_LEVEL', 'INFO')
            
            print(f"\nCurrent log level: {log_level}")
            print("\nOptions:")
            print("1. Change log level")
            print("2. Clear logs")
            print("3. Toggle TMDB folder ID inclusion")
            print("q. Return to Settings Menu")
            
            choice = input("\nEnter choice: ").strip().lower()
            
            if choice == '1':
                print("\nAvailable log levels:")
                print("1. DEBUG")
                print("2. INFO")
                print("3. WARNING")
                print("4. ERROR")
                print("5. CRITICAL")
                
                level_choice = input("\nSelect log level (1-5): ").strip()
                
                log_levels = {
                    '1': 'DEBUG',
                    '2': 'INFO',
                    '3': 'WARNING',
                    '4': 'ERROR',
                    '5': 'CRITICAL'
                }
                
                if level_choice in log_levels:
                    _update_env_var('LOG_LEVEL', log_levels[level_choice])
                    print(f"\nLog level set to {log_levels[level_choice]}.")
                else:
                    print("\nInvalid choice.")
                
                input("\nPress Enter to continue...")
            elif choice == '2':
                confirm = input("\nAre you sure you want to clear all logs? (y/n): ").strip().lower()
                if confirm == 'y':
                    try:
                        # Clear main log file
                        with open(os.path.join(log_dir, 'scanly.log'), 'w') as f:
                            f.write("")
                        
                        # Clear monitor log file
                        with open(monitor_log_file, 'w') as f:
                            f.write("")
                            
                        print("\nLogs cleared successfully.")
                    except Exception as e:
                        print(f"\nError clearing logs: {e}")
                    
                    input("\nPress Enter to continue...")
            elif choice == '3':
                include_tmdb = os.environ.get('INCLUDE_TMDB_ID', 'true').lower() == 'true'
                new_value = 'false' if include_tmdb else 'true'
                _update_env_var('INCLUDE_TMDB_ID', new_value)
                print(f"\nTMDB ID inclusion is now {'enabled' if new_value == 'true' else 'disabled'}.")
                input("\nPress Enter to continue...")
            elif choice == 'q':
                return
            else:
                print("\nInvalid choice.")
                input("\nPress Enter to continue...")
    
    def _view_all_settings(self):
        """View all current configuration settings."""
        clear_screen()
        display_ascii_art()
        print("=" * 60)
        print("CURRENT CONFIGURATION")
        print("=" * 60)
        
        # Read all environment variables from .env file
        env_vars = {}
        if os.path.exists(self.env_path):
            with open(self.env_path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        key, value = line.split('=', 1)
                        env_vars[key] = value
        
        # Display in categories
        print("\nDirectory Settings:")
        print(f"  Destination Directory: {os.environ.get('DESTINATION_DIRECTORY', 'Not set')}")
        
        print("\nTMDB API Settings:")
        api_key = os.environ.get('TMDB_API_KEY', 'Not set')
        print(f"  API Key: {self._mask_sensitive_info(api_key) if api_key != 'Not set' else 'Not set'}")
        print(f"  Include TMDB ID: {'Enabled' if os.environ.get('INCLUDE_TMDB_ID', 'true').lower() == 'true' else 'Disabled'}")
        
        print("\nFile Management Settings:")
        print(f"  Use Symlinks: {'Enabled' if os.environ.get('USE_SYMLINKS', 'true').lower() == 'true' else 'Disabled'}")
        
        print("\nMonitoring Settings:")
        print(f"  Monitoring Interval: {os.environ.get('MONITOR_INTERVAL_MINUTES', '60')} minutes")
        
        print("\nOther Settings:")
        # Display any other environment variables that don't fit into the above categories
        other_keys = set(env_vars.keys()) - {'DESTINATION_DIRECTORY', 'TMDB_API_KEY', 'INCLUDE_TMDB_ID', 'USE_SYMLINKS', 'MONITOR_INTERVAL_MINUTES'}
        for key in sorted(other_keys):
            value = env_vars[key]
            if 'TOKEN' in key.upper():
                value = self._mask_sensitive_info(value)
            print(f"  {key}: {value}")
        
        input("\nPress Enter to return to Settings Menu...")
    
    def _mask_sensitive_info(self, text):
        """Mask sensitive information for display."""
        if not text or text == 'Not set':
            return text
        
        # Show first 4 and last 4 characters, mask the rest
        if len(text) <= 8:
            return "****"
        else:
            return text[:4] + "*" * (len(text) - 8) + text[-4:]

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
    
    def multi_scan(self):
        """Handle scanning of multiple directories."""
        clear_screen()
        display_ascii_art()
        print("=" * 60)
        print("MULTI SCAN")
        print("=" * 60)
        
        dirs_to_scan = []
        
        while True:
            print(f"\nEnter path {len(dirs_to_scan) + 1} to scan (or leave blank to finish): ")
            dir_path = input("> ").strip()
            
            if not dir_path:
                break
            
            # Clean up the directory path
            dir_path = _clean_directory_path(dir_path)
            
            if not os.path.isdir(dir_path):
                print(f"\nWarning: '{dir_path}' is not a valid directory. Skipping.")
                continue
                
            dirs_to_scan.append(dir_path)
        
        if not dirs_to_scan:
            print("\nNo directories specified for scanning.")
            input("\nPress Enter to continue...")
            return
            
        print(f"\nProcessing {len(dirs_to_scan)} directories...")
        
        for i, dir_path in enumerate(dirs_to_scan, 1):
            print(f"\n[{i}/{len(dirs_to_scan)}] Processing: {dir_path}")
            processor = DirectoryProcessor(dir_path)
            processor.process()
            
        print("\nMulti-scan complete.")
        input("\nPress Enter to continue...")
    
    def resume_scan(self):
        """Resume a previously interrupted scan."""
        # Load scan history
        history = load_scan_history()
        if not history:
            print("\nNo scan history found to resume.")
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
            print(f"\nError: Previously scanned directory '{dir_path}' no longer exists.")
            input("\nPress Enter to continue...")
            return
        
        print(f"\nFound scan history for: {dir_path}")
        print(f"Progress: {processed_files}/{total_files} files processed")
        print(f"Media files found: {len(media_files)}")
        
        print("\nOptions:")
        print("1. Resume scan from where it left off")
        print("2. Start a new scan of this directory")
        print("3. Clear scan history")
        print("q. Return to main menu")
        
        choice = input("\nEnter choice: ").strip().lower()
        
        if choice == "1":
            processor = DirectoryProcessor(dir_path, resume=True)
            processor.process()
        elif choice == "2":
            # Clear history first
            clear_scan_history()
            processor = DirectoryProcessor(dir_path)
            processor.process()
        elif choice == "3":
            clear_scan_history()
            print("\nScan history cleared.")
            input("\nPress Enter to continue...")
        elif choice == "q":
            return
        else:
            print("\nInvalid choice.")
            input("\nPress Enter to continue...")
    
    def review_monitored_directories(self):
        """Review and manage monitored directories."""
        try:
            from src.core.monitor import MonitorManager
            
            # Get monitor manager instance
            monitor_manager = MonitorManager()
            
            while True:
                clear_screen()
                display_ascii_art()
                print("=" * 60)
                print("MONITORED DIRECTORIES")
                print("=" * 60)
                
                # Get current status
                status = monitor_manager.check_status()
                
                if status.get('running', False):
                    print(f"\n✅ Monitor is running")
                    print(f"  Directory: {status.get('directory', 'Unknown')}")
                    print(f"  Since: {status.get('start_time', 'Unknown')}")
                    print(f"  Files processed: {status.get('files_processed', 0)}")
                    
                    print("\nOptions:")
                    print("1. Stop monitor")
                    print("2. View monitor logs")
                    print("q. Return to main menu")
                else:
                    print("\n❌ Monitor is not running")
                    
                    print("\nOptions:")
                    print("1. Start new monitor")
                    print("2. View monitor logs")
                    print("q. Return to main menu")
                    
                choice = input("\nEnter choice: ").strip().lower()
                
                if choice == '1':
                    if status.get('running', False):
                        # Stop monitor
                        if input("\nConfirm stopping monitor (y/n): ").strip().lower() == 'y':
                            monitor_manager.stop()
                            print("\nMonitor stopped.")
                            input("\nPress Enter to continue...")
                    else:
                        # Start monitor
                        print("\nEnter directory to monitor:")
                        dir_path = input("> ").strip()
                        dir_path = _clean_directory_path(dir_path)
                        
                        if not os.path.isdir(dir_path):
                            print(f"\nError: '{dir_path}' is not a valid directory.")
                            input("\nPress Enter to continue...")
                            continue
                        
                        monitor_manager.start(dir_path)
                        print(f"\nStarted monitoring: {dir_path}")
                        input("\nPress Enter to continue...")
                elif choice == '2':
                    # View logs
                    try:
                        with open(monitor_log_file, 'r') as f:
                            logs = f.readlines()
                            
                        print("\nMonitor logs (last 20 entries):")
                        for line in logs[-20:]:
                            print(line.strip())
                    except Exception as e:
                        print(f"\nError reading log file: {e}")
                    
                    input("\nPress Enter to continue...")
                elif choice == 'q':
                    break
                else:
                    print("\nInvalid choice.")
                    input("\nPress Enter to continue...")
                    
        except ImportError:
            print("\nMonitor module not found. Please check your installation.")
            input("\nPress Enter to continue...")
    
    def settings_menu(self):
        """Display the settings menu."""
        menu = SettingsMenu()
        menu.display()
    
    def show(self):
        """Show the main menu and handle user input."""
        while True:
            clear_screen()
            display_ascii_art()
            print("=" * 60)
            print("MAIN MENU")
            print("=" * 60)
            
            print("\nOptions:")
            print("1. Individual Scan")
            print("2. Multi Scan")
            print("3. Resume Scan")
            print("4. Settings")
            print("5. Review Skipped Items")
            print("6. Monitor Menu")
            print("7. Help")
            print("0. Quit")
            
            choice = input("\nEnter choice: ").strip()
            
            if choice == '1':
                self.individual_scan()
            elif choice == '2':
                self.multi_scan()
            elif choice == '3':
                self.resume_scan()
            elif choice == '4':
                self.settings_menu()
            elif choice == '5':
                review_skipped_items()
            elif choice == '6':
                self.review_monitored_directories()
            elif choice == '7':
                display_help()
            elif choice == '0':
                print("\nExiting Scanly.")
                return
            else:
                print("\nInvalid choice. Please try again.")
                input("\nPress Enter to continue...")

# Main entry point
def main():
    """Main entry point for the application."""
    try:
        # Initialize the application
        print("Starting Scanly...")
        
        # Create logs directory if it doesn't exist
        logs_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'logs')
        os.makedirs(logs_dir, exist_ok=True)
        
        # Create scanners directory if it doesn't exist
        scanners_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'scanners')
        os.makedirs(scanners_dir, exist_ok=True)
        
        # Create main menu and show it
        menu = MainMenu()
        menu.show()
    except KeyboardInterrupt:
        print("\nApplication terminated by user.")
    except Exception as e:
        logger.error(f"Unhandled exception: {e}")
        print(f"\nError: {e}")
        traceback.print_exc()
        input("\nPress Enter to exit...")

if __name__ == "__main__":
    main()
