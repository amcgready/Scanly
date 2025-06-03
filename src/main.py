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
import difflib
import argparse
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

def has_scan_history():
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

def has_skipped_items():
    """Check if there are skipped items."""
    global skipped_items_registry
    return len(skipped_items_registry) > 0

def clear_all_history():
    """Clear both scan history and skipped items."""
    clear_scan_history()
    clear_skipped_items()
    print("\nAll history has been cleared.")
    input("\nPress Enter to continue...")
    clear_screen()
    display_ascii_art()

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
    print("=" * 84)
    print("HELP".center(84))
    print("=" * 84)
    print("\nScanly is a media file scanner and organizer.")
    print("\nOptions:")
    print("  1. Individual Scan - Scan a single directory for media files")
    print("  2. Multi Scan     - Scan multiple directories")
    print("  3. Resume Scan    - Resume a previously interrupted scan")
    print("  4. Settings       - Configure application settings")
    print("  0. Quit           - Exit the application")
    print("\nPress Enter to continue...")
    input()
    clear_screen()  # Clear screen after leaving help
    display_ascii_art()  # Show ASCII art when returning to main menu

# Function to review skipped items
def review_skipped_items():
    """Review and process previously skipped items."""
    global skipped_items_registry
    
    if not skipped_items_registry:
        print("No skipped items to review.")
        input("\nPress Enter to continue...")
        clear_screen()  # Clear screen when returning to main menu
        display_ascii_art()  # Show ASCII art
        return
    
    while True:
        clear_screen()
        display_ascii_art()
        print("=" * 84)
        print("SKIPPED ITEMS".center(84))
        print("=" * 84)
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
                    clear_screen()  # Clear screen after processing
                    display_ascii_art()  # Show ASCII art
                else:
                    print("\nInvalid item number.")
                    input("\nPress Enter to continue...")
                    clear_screen()  # Clear screen after error
                    display_ascii_art()  # Show ASCII art
            except ValueError:
                print("\nInvalid input. Please enter a number.")
                input("\nPress Enter to continue...")
                clear_screen()  # Clear screen after error
                display_ascii_art()  # Show ASCII art
        elif choice == "2":
            # Confirm before clearing
            confirm = input("\nAre you sure you want to clear all skipped items? (y/n): ").strip().lower()
            if confirm == 'y':
                clear_skipped_items()
                clear_screen()  # Clear screen after clearing items
                display_ascii_art()  # Show ASCII art
                break
        elif choice == "3" and total_pages > 1:
            # Next page
            if current_page < total_pages:
                current_page += 1
            clear_screen()  # Clear screen when changing page
            display_ascii_art()  # Show ASCII art
        elif choice == "4" and total_pages > 1:
            # Previous page
            if current_page > 1:
                current_page -= 1
            clear_screen()  # Clear screen when changing page
            display_ascii_art()  # Show ASCII art
        elif choice == "0":
            clear_screen()  # Clear screen when returning to main menu
            display_ascii_art()  # Show ASCII art
            return
        else:
            print("\nInvalid option.")
            input("\nPress Enter to continue...")
            clear_screen()  # Clear screen after error
            display_ascii_art()  # Show ASCII art

def _check_monitor_status():
    """Check and fix the monitor status if needed."""
    clear_screen()
    display_ascii_art()
    print("=" * 84)
    print("MONITOR STATUS".center(84))
    print("=" * 84)
    
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
        clear_screen()  # Clear screen after checking monitor status
        display_ascii_art()  # Show ASCII art
    except ImportError:
        print("\nMonitor module not found. Please check your installation.")
        input("\nPress Enter to continue...")
        clear_screen()  # Clear screen after error
        display_ascii_art()  # Show ASCII art
    except Exception as e:
        print(f"\nError checking monitor status: {e}")
        input("\nPress Enter to continue...")
        clear_screen()  # Clear screen after error
        display_ascii_art()  # Show ASCII art

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
    
    def _check_scanner_lists(self, title, year=None, is_tv=False, is_anime=False):
        """Check appropriate scanner lists for matches based on content type
        
        Args:
            title (str): Title to check
            year (str, optional): Year to check. If provided, filters matches by year.
            is_tv (bool): Whether the content is a TV series
            is_anime (bool): Whether the content is anime
            
        Returns:
            list: List of matching items from scanner lists.
        """
        # Determine which scanner list to use based on content type
        if is_anime and is_tv:
            scanner_file = "anime_series.txt"
        elif is_anime and not is_tv:
            scanner_file = "anime_movies.txt"
        elif is_tv and not is_anime:
            scanner_file = "tv_series.txt"
        else:
            scanner_file = "movies.txt"
        
        # Get the full path to the scanner file
        scanners_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'scanners')
        scanner_path = os.path.join(scanners_dir, scanner_file)
        
        # Log which scanner we're checking
        self.logger.info(f"Checking scanner list: {scanner_file} for title: '{title}' ({year if year else 'any year'})")
        
        # Check if scanner file exists
        if not os.path.exists(scanner_path):
            self.logger.warning(f"Scanner file not found: {scanner_path}")
            return []
        
        matches = []
        try:
            # Read the scanner file
            with open(scanner_path, 'r', encoding='utf-8') as file:
                for line in file:
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue  # Skip empty lines and comments
                    
                    # Parse the line (format: "Title (Year)" or just "Title")
                    match = re.match(r'(.+?)(?:\s+\((\d{4})\))?$', line)
                    if not match:
                        continue
                    
                    scan_title = match.group(1).strip()
                    scan_year = match.group(2) if match.group(2) else None
                    
                    # Check for match (normalized, case-insensitive)
                    if self._is_title_match(title, scan_title):
                        # If year is specified, check it too
                        if year and scan_year and year != scan_year:
                            continue
                        
                        # Add to matches
                        matches.append({
                            'title': scan_title,
                            'year': scan_year,
                            'source': scanner_file
                        })
            
            self.logger.info(f"Found {len(matches)} matches in {scanner_file}")
            return matches
            
        except Exception as e:
            self.logger.error(f"Error reading scanner file {scanner_path}: {e}")
            return []

    def _is_title_match(self, title1, title2):
        """Compare two titles to determine if they match.
        
        Uses several normalization techniques to improve matching:
        - Convert to lowercase
        - Remove punctuation
        - Normalize whitespace
        
        Args:
            title1 (str): First title
            title2 (str): Second title
            
        Returns:
            bool: True if titles match, False otherwise
        """
        # Normalize both titles
        def normalize(title):
            # Convert to lowercase
            title = title.lower()
            # Remove punctuation
            title = re.sub(r'[^\w\s]', '', title)
            # Normalize whitespace
            title = re.sub(r'\s+', ' ', title).strip()
            return title
        
        norm1 = normalize(title1)
        norm2 = normalize(title2)
        
        # Check for exact match after normalization
        if norm1 == norm2:
            return True
        
        # Check for substring match (one title contained in another)
        if norm1 in norm2 or norm2 in norm1:
            return True
        
        # Calculate similarity score
        similarity = difflib.SequenceMatcher(None, norm1, norm2).ratio()
        # Return True if similarity is above threshold
        return similarity > 0.8

    def _extract_folder_metadata(self, folder_name):
        """Extract title and year from a folder name."""
        title = folder_name
        year = None
        
        # Check for explicit year pattern with parentheses like "Movie Title (2021)"
        parentheses_year = re.search(r'\((\d{4})\)', folder_name)
        if parentheses_year:
            year = parentheses_year.group(1)
            # Remove the (year) from the title
            clean_title = re.sub(r'\s*\(\d{4}\)\s*', ' ', folder_name).strip()
        else:
            # Look for 4-digit sequences that could be years (between 1900 and current year + 5)
            current_year = datetime.datetime.now().year
            year_matches = re.findall(r'(?:^|[^0-9])(\d{4})(?:[^0-9]|$)', folder_name)
            
            clean_title = folder_name
            
            # If multiple 4-digit numbers found, determine which is likely the year
            if year_matches:
                for potential_year in year_matches:
                    year_int = int(potential_year)
                    # Valid years are between 1900 and current year + 5
                    if 1900 <= year_int <= current_year + 5:
                        # Treat the last valid year as the release year
                        year = potential_year
            
                # Special case: If the title starts with a 4-digit number that could be a year
                # (like "2001: A Space Odyssey"), keep it in the title
                if year_matches[0] == year and re.match(r'^' + year + r'[^0-9]', folder_name):
                    # This is likely a title that starts with a year, look for another year
                    if len(year_matches) > 1:
                        for potential_year in year_matches[1:]:
                            year_int = int(potential_year)
                            if 1900 <= year_int <= current_year + 5:
                                year = potential_year
                                break
                    else:
                        # Only one year found and it's at the start, consider it part of the title
                        year = None
    
        # First level of cleaning - remove common patterns
        clean_title = folder_name
    
        # Remove the year if found (but not if it's at the start of the title)
        if year and not re.match(r'^' + year + r'[^0-9]', folder_name):
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
        
        # Remove the FGT pattern explicitly
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

    def _create_symlinks(self, subfolder_path, title, year, is_tv=False, is_anime=False, is_wrestling=False, tmdb_id=None):
        """Create symlinks from the source directory to the destination directory."""
        try:
            # Check if destination directory is configured
            if not DESTINATION_DIRECTORY:
                self.logger.error("Destination directory not configured.")
                print("\nError: Destination directory not configured. Please set this in Settings.")
                return False
            
            # Make sure destination directory exists
            if not os.path.exists(DESTINATION_DIRECTORY):
                os.makedirs(DESTINATION_DIRECTORY, exist_ok=True)
                self.logger.info(f"Created destination directory: {DESTINATION_DIRECTORY}")
            
            # Format the base name with year for both folder and files
            base_name = title
            if year and not is_wrestling:
                base_name = f"{title} ({year})"
            
            # Add TMDB ID if available - same format for all media types: [tmdb-ID]
            folder_name = base_name
            if tmdb_id:
                folder_name = f"{base_name} [tmdb-{tmdb_id}]"
            
            # Determine appropriate subdirectory based on content type
            if is_wrestling:
                dest_subdir = os.path.join(DESTINATION_DIRECTORY, 'Wrestling')
            elif is_anime and is_tv:
                dest_subdir = os.path.join(DESTINATION_DIRECTORY, 'Anime Series')
            elif is_anime and not is_tv:
                dest_subdir = os.path.join(DESTINATION_DIRECTORY, 'Anime Movies')
            elif not is_anime and is_tv:
                dest_subdir = os.path.join(DESTINATION_DIRECTORY, 'TV Series')
            else:
                dest_subdir = os.path.join(DESTINATION_DIRECTORY, 'Movies')
        
            # Create content type subdirectory if it doesn't exist
            if not os.path.exists(dest_subdir):
                os.makedirs(dest_subdir, exist_ok=True)
                self.logger.info(f"Created subdirectory: {dest_subdir}")
        
            # Create full path for the target directory
            target_dir_path = os.path.join(dest_subdir, folder_name)
        
            # Create the target directory if it doesn't exist
            if not os.path.exists(target_dir_path):
                os.makedirs(target_dir_path, exist_ok=True)
                self.logger.info(f"Created target directory: {target_dir_path}")
        
            # Check if using symlinks or copies
            use_symlinks = os.environ.get('USE_SYMLINKS', 'true').lower() == 'true'
        
            # Process files in subfolder
            for root, dirs, files in os.walk(subfolder_path):
                # Calculate relative path from subfolder_path
                rel_path = os.path.relpath(root, subfolder_path)
                
                # Create season folders for TV shows
                if is_tv:
                    # Check if this is a season directory
                    season_match = re.search(r'season\s*(\d+)', rel_path, re.IGNORECASE)
                    if season_match:
                        season_num = int(season_match.group(1))
                        season_dir_name = f"Season {season_num:02d}"
                        season_dir_path = os.path.join(target_dir_path, season_dir_name)
                        
                        if not os.path.exists(season_dir_path):
                            os.makedirs(season_dir_path, exist_ok=True)
                            self.logger.debug(f"Created season directory: {season_dir_path}")
            
                # Process each file
                for file_name in files:
                    # Skip non-media files
                    if not file_name.lower().endswith(('.mkv', '.mp4', '.avi', '.mov', '.wmv', '.m4v', '.flv')):
                        continue
                    
                    source_file = os.path.join(root, file_name)
                    
                    # Determine target file based on content type
                    if is_tv:
                        # Extract season and episode numbers from filename
                        season_ep_match = re.search(r's(\d{1,2})e(\d{1,2})|season\s*(\d+).*?episode\s*(\d+)', 
                                                  file_name, re.IGNORECASE)
                        
                        if season_ep_match:
                            # Extract season/episode from standard pattern
                            if season_ep_match.group(1) and season_ep_match.group(2):
                                season_num = int(season_ep_match.group(1))
                                episode_num = int(season_ep_match.group(2))
                            # Extract from textual pattern
                            else:
                                season_num = int(season_ep_match.group(3))
                                episode_num = int(season_ep_match.group(4))
                        
                            # Format the episode filename according to spec
                            _, extension = os.path.splitext(file_name)
                            extension = extension[1:]  # Remove the dot
                            formatted_filename = f"{title} ({year}) - S{season_num:02d}E{episode_num:02d}.{extension}"
                            
                            # Create season folder if doesn't exist
                            season_dir_name = f"Season {season_num:02d}"
                            season_dir_path = os.path.join(target_dir_path, season_dir_name)
                            if not os.path.exists(season_dir_path):
                                os.makedirs(season_dir_path, exist_ok=True)
                                
                            # Set target path for the episode
                            target_file = os.path.join(season_dir_path, formatted_filename)
                        else:
                            # If no season/episode found, place in main folder with original name
                            target_file = os.path.join(target_dir_path, file_name)
                    else:  # Movies and other non-TV content
                        # For movies, format the filename as: "Title (Year).extension"
                        _, extension = os.path.splitext(file_name)
                        extension = extension[1:]  # Remove the dot
                        formatted_filename = f"{title} ({year}).{extension}"
                        target_file = os.path.join(target_dir_path, formatted_filename)
                
                    # Create the link or copy the file
                    if use_symlinks:
                        if os.path.exists(target_file) and not os.path.islink(target_file):
                            os.unlink(target_file)
                        if not os.path.exists(target_file):
                            os.symlink(source_file, target_file)
                            self.logger.debug(f"Created symlink: {target_file} -> {source_file}")
                    else:
                        if not os.path.exists(target_file):
                            shutil.copy2(source_file, target_file)
                            self.logger.debug(f"Copied file: {source_file} -> {target_file}")
        
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
                clear_screen()  # Clear screen when returning to main menu
                display_ascii_art()  # Show ASCII art
                return 0
                
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
                is_wrestling = False
                
                # Initialize search term and TMDB ID
                search_term = title
                tmdb_id = None
                
                # Loop for processing the current folder with different options
                while True:
                    clear_screen()  # Clear screen before displaying folder processing menu
                    display_ascii_art()  # Show ASCII art
                    print("=" * 84)
                    print("FOLDER PROCESSING".center(84))
                    print("=" * 84)
                    
                    print(f"\nProcessing: {subfolder_name}")
                    print(f"  Title: {title}")
                    print(f"  Year: {year if year else 'Unknown'}")
                    
                    # Display content type
                    content_type = "Movie"
                    if is_wrestling:
                        content_type = "Wrestling"
                    elif is_tv and is_anime:
                        content_type = "Anime Series"
                    elif not is_tv and is_anime:
                        content_type = "Anime Movie"
                    elif is_tv and not is_anime:
                        content_type = "TV Series"
                        
                    print(f"  Type: {content_type}")
                    print(f"  Search term: {search_term}")
                    if tmdb_id:
                        print(f"  TMDB ID: {tmdb_id}")
                    
                    # Check scanner lists for matches using current search term
                    scanner_matches = self._check_scanner_lists(search_term, year, is_tv, is_anime)
                    print(f"  Scanner Matches: {len(scanner_matches)}")
                    
                    # If multiple scanner matches found, ask user to select
                    selected_match = None
                    if len(scanner_matches) > 1:
                        print("\nSelect the correct match:")
                        for i, match in enumerate(scanner_matches):
                            match_title = match.get('title', 'Unknown')
                            year_str = f" ({match.get('year')})" if match.get('year') else ""
                            match_tmdb_id = match.get('tmdb_id', '')
                            id_str = f" [tmdb-{match_tmdb_id}]" if match_tmdb_id else ""
                            print(f"{i+1}. {match_title}{year_str}{id_str}")
                        print("0. Additional options")
                        
                        match_choice = input("\nSelect correct match: ").strip()
                        # Make Enter key select option 1 as default
                        if match_choice == "":
                            match_choice = "1"
                            
                        try:
                            match_idx = int(match_choice) - 1
                            if 0 <= match_idx < len(scanner_matches):
                                selected_match = scanner_matches[match_idx]
                                title = selected_match.get('title', title)
                                year = selected_match.get('year', year)
                                tmdb_id = selected_match.get('tmdb_id')
                                
                                # Display the selected match
                                year_str = f" ({year})" if year else ""
                                id_str = f" [tmdb-{tmdb_id}]" if tmdb_id else ""
                                print(f"\nSelected: {title}{year_str}{id_str}")
                                
                                # Process the file immediately with the selected match
                                if self._create_symlinks(subfolder_path, title, year, is_tv, is_anime, is_wrestling, tmdb_id):
                                    processed += 1
                                    input("\nPress Enter to continue...")
                                    clear_screen()  # Clear screen after successful processing
                                    display_ascii_art()  # Show ASCII art
                                    break  # Exit the loop for this subfolder

                            elif match_idx == -1:  # User selected "Additional options"
                                print("\nProceeding with manual identification...")
                                # Continue to manual options (existing flow)
                        except ValueError:
                            print("\nInvalid choice. Proceeding with manual options.")
                    elif len(scanner_matches) == 1:
                        selected_match = scanner_matches[0]
                        match_tmdb_id = selected_match.get('tmdb_id', '')
                        id_str = f" [tmdb-{match_tmdb_id}]" if match_tmdb_id else ""
                        print(f"\nScanner match: {selected_match.get('title', 'Unknown')} ({selected_match.get('year', 'Unknown')}){id_str}")
                        
                        # Instead of just confirming, show all options
                        print("\nOptions:")
                        print("1. Accept this match")
                        print("2. Change search term")
                        print("3. Change content type") 
                        print("4. Skip this folder")
                        print("0. Quit")
                        
                        action_choice = input("\nSelect option: ").strip()
                        if action_choice == "" or action_choice == "1":
                            title = selected_match.get('title', title)
                            year = selected_match.get('year', year)
                            tmdb_id = selected_match.get('tmdb_id', '')
                            if self._create_symlinks(subfolder_path, title, year, is_tv, is_anime, is_wrestling, tmdb_id):
                                processed += 1
                                input("\nPress Enter to continue...")
                                clear_screen()  # Clear screen after successful processing
                                display_ascii_art()  # Show ASCII art
                                break  # Exit the loop for this subfolder
                        elif action_choice == "4":
                            # Skip this folder
                            print(f"\nSkipping folder: {subfolder_name}")
                            skipped_items_registry.append({
                                'subfolder': subfolder_name,
                                'path': subfolder_path,
                                'skipped_date': datetime.datetime.now().isoformat()
                            })
                            save_skipped_items(skipped_items_registry)
                            input("\nPress Enter to continue...")
                            clear_screen()  # Clear screen after skipping
                            display_ascii_art()  # Show ASCII art
                            break  # Exit loop for this subfolder
                        elif action_choice == "0":
                            # Quit
                            if input("\nAre you sure you want to quit the scan? (y/n): ").strip().lower() == 'y':
                                print("\nScan cancelled.")
                                input("\nPress Enter to continue...")
                                clear_screen()  # Clear screen after quitting
                                display_ascii_art()  # Show ASCII art
                                return -1
                        # If other options selected, continue with the loop
                        
                    # Show options for this subfolder
                    print("\nOptions:")
                    print("1. Accept as is")
                    print("2. Change search term")
                    print("3. Change content type")
                    print("4. Manual TMDB ID")
                    print("5. Skip (save for later review)")
                    print("0. Quit")
                    
                    choice = input("\nSelect option: ").strip()
                    
                    # Make Enter key select option 1 as a default
                    if choice == "":
                        choice = "1"
                        
                    if choice == "1":
                        # Accept the extracted info
                        if self._create_symlinks(subfolder_path, title, year, is_tv, is_anime, is_wrestling, tmdb_id):
                            processed += 1
                            input("\nPress Enter to continue...")
                            clear_screen()  # Clear screen after successful processing
                            display_ascii_art()  # Show ASCII art
                        break  # Exit the loop for this subfolder
                        
                    elif choice == "2":
                        # Change search term
                        new_search = input(f"Enter new search term [{search_term}]: ").strip()
                        if new_search:
                            search_term = new_search
                        # Loop continues with new search term
                        clear_screen()  # Clear screen after changing search term
                        display_ascii_art()  # Show ASCII art
                        
                    elif choice == "3":
                        # Change content type using the helper method
                        is_tv, is_anime, is_wrestling = self._prompt_for_content_type(is_tv, is_anime)
                        # Loop continues with new content type settings
                        clear_screen()  # Clear screen after changing content type
                        display_ascii_art()  # Show ASCII art
                    
                    elif choice == "4":
                        # Manual TMDB ID entry
                        new_tmdb_id = input(f"Enter TMDB ID [{tmdb_id if tmdb_id else ''}]: ").strip()
                        if new_tmdb_id:
                            tmdb_id = new_tmdb_id
                        # Loop continues with new TMDB ID
                        clear_screen()  # Clear screen after changing TMDB ID
                        display_ascii_art()  # Show ASCII art
                        
                    elif choice == "5":
                        # Skip this subfolder
                        print(f"Skipping subfolder: {subfolder_name}")
                        skipped_items_registry.append({
                            'subfolder': subfolder_name,
                            'path': subfolder_path,
                            'skipped_date': datetime.datetime.now().isoformat()
                        })
                        save_skipped_items(skipped_items_registry)
                        input("\nPress Enter to continue...")
                        clear_screen()  # Clear screen after skipping
                        display_ascii_art()  # Show ASCII art
                        break  # Exit the loop for this subfolder
                        
                    elif choice == "0":
                        # Quit the scan
                        if input("Are you sure you want to quit the scan? (y/n): ").strip().lower() == 'y':
                            print("Scan cancelled.")
                            input("\nPress Enter to continue...")
                            clear_screen()  # Clear screen after quitting
                            display_ascii_art()  # Show ASCII art
                            return -1
                        clear_screen()  # Clear screen if user decides not to quit
                        display_ascii_art()  # Show ASCII art
                        
                    else:
                        print("Invalid option. Please try again.")
                        input("\nPress Enter to continue...")
                        clear_screen()  # Clear screen after invalid option
                        display_ascii_art()  # Show ASCII art
        
            print(f"\nFinished processing {len(subdirs)} subdirectories.")
            input("\nPress Enter to continue...")
            clear_screen()  # Clear screen after completing all processing
            display_ascii_art()  # Show ASCII art
            return processed
            
        except Exception as e:
            self.logger.error(f"Error processing media files: {e}")
            print(f"Error: {e}")
            input("\nPress Enter to continue...")
            clear_screen()  # Clear screen after error
            display_ascii_art()  # Show ASCII art

    def _prompt_for_content_type(self, current_is_tv, current_is_anime):
        """Helper method to prompt user for content type selection.
        
        Returns:
            Tuple: (is_tv, is_anime, is_wrestling) - Updated content type settings
        """
        clear_screen()  # Clear screen before showing content type menu
        display_ascii_art()  # Show ASCII art
        print("=" * 84)
        print("SELECT CONTENT TYPE".center(84))
        print("=" * 84)
        
        # Current content type
        current_type = "Wrestling"
        if current_is_tv and current_is_anime:
            current_type = "Anime Series"
        elif not current_is_tv and current_is_anime:
            current_type = "Anime Movies"
        elif current_is_tv and not current_is_anime:
            current_type = "TV Series"
        elif not current_is_tv and not current_is_anime:
            current_type = "Movies"
        
        # Display options with current selection highlighted
        print("\nSelect content type:")
        print(f"1. Movies{' (current)' if current_type == 'Movies' else ''}")
        print(f"2. TV Series{' (current)' if current_type == 'TV Series' else ''}")
        print(f"3. Anime Movies{' (current)' if current_type == 'Anime Movies' else ''}")
        print(f"4. Anime Series{' (current)' if current_type == 'Anime Series' else ''}")
        print(f"5. Wrestling{' (current)' if current_type == 'Wrestling' else ''}")
        
        # Get user selection
        choice = input("\nEnter choice [1-5]: ").strip()
        
        # Default to current selection if empty input
        if not choice:
            return current_is_tv, current_is_anime, current_type == "Wrestling"
        
        # Process choice
        is_tv = False
        is_anime = False
        is_wrestling = False
        
        if choice == "1":  # Movies
            is_tv = False
            is_anime = False
        elif choice == "2":  # TV Series
            is_tv = True
            is_anime = False
        elif choice == "3":  # Anime Movies
            is_tv = False
            is_anime = True
        elif choice == "4":  # Anime Series
            is_tv = True
            is_anime = True
        elif choice == "5":  # Wrestling
            is_wrestling = True
        
        return is_tv, is_anime, is_wrestling

    def _display_scanner_matches(self, matches, title, year):
        """Display scanner matches with proper formatting."""
        print("\n  Scanner Matches:", len(matches))
        print()
        
        for i, match in enumerate(matches, 1):
            # Extract the relevant fields from the match
            match_title = match.get('title', 'Unknown')
            match_year = match.get('year', 'Unknown')
            match_tmdb_id = match.get('tmdb_id', 'Unknown')
            
            # Format the match display string correctly - without the None at the end
            match_display = f"{match_title} ({match_year}) [tmdb-{match_tmdb_id}]"
            
            # Print the match
            print(f"Scanner match: {match_display}")
            print()
        
        # Display options after matches
        print("Options:")
        print("1. Accept this match")
        print("2. Change search term")
        print("3. Change content type")
        print("4. Skip this folder")
        print("0. Quit")
        print()

def perform_multi_scan():
    """Perform a multi-scan operation on multiple directories."""
    clear_screen()
    display_ascii_art()
    print("=" * 84)
    print("MULTI SCAN".center(84))
    print("=" * 84)
    
    print("\nEnter directory paths to scan (one per line).")
    print("Press Enter on an empty line when done.\n")
    
    directories = []
    while True:
        dir_input = input(f"Directory {len(directories) + 1}: ").strip()
        
        # Handle empty input
        if not dir_input:
            if directories:  # Only break if we have at least one directory
                break
            else:
                print("Please enter at least one directory.")
                continue
        
        # Check if user wants to return to main menu
        if dir_input.lower() in ('exit', 'quit', 'back', 'return'):
            return_to_menu = input("\nReturn to main menu? (y/n): ").strip().lower()
            if return_to_menu == 'y':
                clear_screen()
                display_ascii_art()
                return
            continue
        
        # Validate directory path
        clean_path = _clean_directory_path(dir_input)
        if os.path.isdir(clean_path):
            directories.append(clean_path)
        else:
            print(f"Invalid directory path: {clean_path}")
            return_to_menu = input("Return to main menu? (y/n): ").strip().lower()
            if return_to_menu == 'y':
                clear_screen()
                display_ascii_art()
                return
    
    if not directories:
        print("\nNo valid directories to scan.")
        input("\nPress Enter to continue...")
        clear_screen()
        display_ascii_art()
        return
    
    # Confirm directories before scanning
    clear_screen()
    display_ascii_art()
    print("=" * 84)
    print("CONFIRM DIRECTORIES".center(84))
    print("=" * 84)
    
    print("\nYou've selected these directories to scan:")
    for i, directory in enumerate(directories):
        print(f"{i+1}. {directory}")
    
    confirm = input("\nProceed with scan? (y/n): ").strip().lower()
    if confirm != 'y':
        print("\nScan cancelled.")
        input("\nPress Enter to continue...")
        clear_screen()
        display_ascii_art()
        return
    
    # Process each directory
    total_processed = 0
    for i, directory in enumerate(directories):
        clear_screen()
        display_ascii_art()
        print("=" * 84)
        print(f"PROCESSING DIRECTORY {i+1} OF {len(directories)}".center(84))
        print("=" * 84)
        print(f"\nDirectory: {directory}")
        
        # Create processor for this directory
        processor = DirectoryProcessor(directory)
        result = processor._process_media_files()
        
        # Check if user cancelled the scan
        if result == -1:
            print("\nMulti-scan cancelled.")
            input("\nPress Enter to continue...")
            clear_screen()
            display_ascii_art()
            return
        
        # Add to total processed count if successful
        if result > 0:
            total_processed += result
    
    # Show summary after all directories processed
    clear_screen()
    display_ascii_art()
    print("=" * 84)
    print("MULTI SCAN COMPLETE".center(84))
    print("=" * 84)
    print(f"\nProcessed {len(directories)} directories")
    print(f"Total media processed: {total_processed} items")
    
    input("\nPress Enter to continue...")
    clear_screen()
    display_ascii_art()

class SettingsMenu:
    """Settings menu handler for the application."""
    
    def _create_custom_content_type(self, scanner_dir, all_content_types, custom_content_types):
        """Create a new custom content type."""
        clear_screen()
        display_ascii_art()
        print("=" * 84)
        print("CREATE CUSTOM CONTENT TYPE".center(84))
        print("=" * 84)
        
        # Get the name for the new content type
        content_type = input("\nEnter name for the new content type: ").strip()
        
        if not content_type:
            print("\nOperation cancelled.")
            input("\nPress Enter to continue...")
            return
        
        # Check if content type already exists
        if content_type in all_content_types:
            print(f"\nContent type '{content_type}' already exists.")
            input("\nPress Enter to continue...")
            return
        
        # Generate a slug for environment variable
        env_slug = content_type.upper().replace(' ', '_')
        env_var = f"SCANNER_{env_slug}"
        
        # Suggest a default file name
        default_file = content_type.lower().replace(' ', '_') + '.txt'
        
        # Ask if user wants to create the scanner file now
        create_file = input(f"\nCreate scanner file '{default_file}' now? (y/n): ").strip().lower()
        
        if create_file == 'y':
            file_path = os.path.join(scanner_dir, default_file)
            
            if os.path.exists(file_path):
                # File already exists, ask to use it
                use_existing = input(f"\nFile '{default_file}' already exists. Use it? (y/n): ").strip().lower()
                if use_existing != 'y':
                    # User doesn't want to use existing file, ask for new name
                    default_file = input("\nEnter new scanner file name (.txt will be added if missing): ").strip()
                    if not default_file:
                        print("\nOperation cancelled.")
                        input("\nPress Enter to continue...")
                        return
                    
                    # Add .txt extension if missing
                    if not default_file.endswith('.txt'):
                        default_file += '.txt'
                    
                    file_path = os.path.join(scanner_dir, default_file)
                    
                    # Check again if file exists
                    if os.path.exists(file_path):
                        print(f"\nFile '{default_file}' already exists.")
                        input("\nPress Enter to continue...")
                        return
            
            # Create the scanner file
            try:
                os.makedirs(os.path.dirname(file_path), exist_ok=True)
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(f"# Scanner file for {content_type}\n")
                    f.write("# Format: Title (Year) [tmdb-ID]\n")
                    f.write("# Example: The Matrix (1999) [tmdb-603]\n\n")
                print(f"\nCreated scanner file '{default_file}'.")
            except Exception as e:
                print(f"\nError creating scanner file: {e}")
                input("\nPress Enter to continue...")
                return
        
        # Add the new content type to custom types
        custom_content_types[content_type] = {
            "env_var": env_var,
            "default_file": default_file
        }
        
        # Save custom content types to environment
        _update_env_var('SCANNER_CUSTOM_TYPES', json.dumps(custom_content_types))
        
        # Set the scanner file for this content type
        _update_env_var(env_var, default_file)
        
        print(f"\nCreated new content type '{content_type}' with scanner file '{default_file}'.")
        input("\nPress Enter to continue...")
    
    def _delete_custom_content_type(self, all_content_types, custom_content_types):
        """Delete a custom content type."""
        clear_screen()
        display_ascii_art()
        print("=" * 84)
        print("DELETE CUSTOM CONTENT TYPE".center(84))
        print("=" * 84)
        
        # Check if there are any custom content types
        if not custom_content_types:
            print("\nNo custom content types found.")
            input("\nPress Enter to continue...")
            return
        
        # List custom content types
        print("\nAvailable custom content types:")
        custom_types = list(custom_content_types.keys())
        for i, content_type in enumerate(custom_types, 1):
            print(f"{i}. {content_type}")
        
        # Get user selection
        choice = input("\nSelect content type to delete (number) or 'q' to cancel: ").strip().lower()
        
        if choice == 'q':
            return
        
        try:
            index = int(choice) - 1
            if 0 <= index < len(custom_types):
                content_type = custom_types[index]
                
                # Confirm deletion
                confirm = input(f"\nAre you sure you want to delete '{content_type}'? (y/n): ").strip().lower()
                if confirm == 'y':
                    # Remove from environment
                    env_var = custom_content_types[content_type]["env_var"]
                    
                    # Remove the content type from custom types
                    del custom_content_types[content_type]
                    
                    # Update environment variable
                    _update_env_var('SCANNER_CUSTOM_TYPES', json.dumps(custom_content_types))
                    
                    print(f"\nDeleted content type '{content_type}'.")
                    
                    # Note: We deliberately don't delete the scanner file, just the mapping
                else:
                    print("\nDeletion cancelled.")
            else:
                print("\nInvalid selection.")
            input("\nPress Enter to continue...")
        except ValueError:
            print("\nInvalid input. Please enter a number.")
            input("\nPress Enter to continue...")
    def __init__(self):
        self.logger = get_logger(__name__)
        self.env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')
    
    def display(self):
        """Display the settings menu."""
        while True:
            clear_screen()
            display_ascii_art()
            print("=" * 84)
            print("SETTINGS".center(84))
            print("=" * 84)
            
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
                clear_screen()
                display_ascii_art()
                return
            else:
                print("\nInvalid option.")
                input("\nPress Enter to continue...")
    
    def _directory_settings(self):
        """Directory settings submenu."""
        while True:
            clear_screen()
            display_ascii_art()
            print("=" * 84)
            print("DIRECTORY SETTINGS".center(84))
            print("=" * 84)
            
            destination_dir = os.environ.get('DESTINATION_DIRECTORY', 'Not set')
            
            print(f"\nCurrent Destination Directory: {destination_dir}")
            print("\nOptions:")
            print("1. Change Destination Directory")
            print("q. Return to Settings Menu")
            
            choice = input("\nEnter choice: ").strip().lower()
            
            if choice == '1':
                new_dir = input("\nEnter new destination directory: ").strip()
                new_dir = _clean_directory_path(new_dir)
                
                if new_dir and os.path.isdir(new_dir):
                    _update_env_var('DESTINATION_DIRECTORY', new_dir)
                    print(f"\nDestination directory updated to: {new_dir}")
                else:
                    print("\nInvalid directory. Please enter a valid path.")
                input("\nPress Enter to continue...")
            elif choice == 'q':
                return
            else:
                print("\nInvalid option.")
                input("\nPress Enter to continue...")
    
    def _tmdb_settings(self):
        """TMDB API settings submenu."""
        while True:
            clear_screen()
            display_ascii_art()
            print("=" * 84)
            print("TMDB API SETTINGS".center(84))
            print("=" * 84)
            
            api_key = os.environ.get('TMDB_API_KEY', 'Not set')
            include_id = os.environ.get('INCLUDE_TMDB_ID', 'true').lower() == 'true'
            
            # Mask API key for display
            masked_key = "****" if api_key and api_key != 'Not set' else "Not set"
            
            print("\nCurrent TMDB Settings:")
            print(f"1. API Key: {masked_key}")
            print(f"2. Include TMDB ID in folder names: {'Enabled' if include_id else 'Disabled'}")
            print("3. Test TMDB API Connection")
            print("q. Return to Settings Menu")
            
            choice = input("\nSelect option: ").strip().lower()
            
            if choice == '1':
                new_key = input("\nEnter new TMDB API key (leave empty to keep current): ").strip()
                if new_key:
                    _update_env_var('TMDB_API_KEY', new_key)
                    print("\nTMDB API key updated.")
                input("\nPress Enter to continue...")
            elif choice == '2':
                new_setting = input("\nInclude TMDB ID in folder names? (y/n): ").strip().lower()
                if new_setting in ('y', 'n'):
                    _update_env_var('INCLUDE_TMDB_ID', 'true' if new_setting == 'y' else 'false')
                    print(f"\nInclude TMDB ID setting: {'Enabled' if new_setting == 'y' else 'Disabled'}")
                input("\nPress Enter to continue...")
            elif choice == '3':
                self._test_tmdb_api()
            elif choice == 'q':
                return
            else:
                print("\nInvalid option.")
                input("\nPress Enter to continue...")
    
    def _test_tmdb_api(self):
        """Test TMDB API connection."""
        api_key = os.environ.get('TMDB_API_KEY', '')
        
        if not api_key:
            print("\nTMDB API key not configured. Please set up your API key first.")
            input("\nPress Enter to continue...")
            return
        
        print("\nTesting TMDB API connection...")
        
        try:
            # Make a simple API request to test the connection
            url = f"https://api.themoviedb.org/3/configuration?api_key={api_key}"
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                print("\n✓ Connection successful! TMDB API is working correctly.")
            elif response.status_code == 401:
                print("\n✗ Authentication failed. Please check your API key.")
            else:
                print(f"\n✗ API request failed with status code: {response.status_code}")
                print(f"Error: {response.json().get('status_message', 'Unknown error')}")
        except requests.exceptions.RequestException as e:
            print(f"\n✗ Connection error: {e}")
        
        input("\nPress Enter to continue...")
    
    def _file_management_settings(self):
        """File management settings submenu."""
        while True:
            clear_screen()
            display_ascii_art()
            print("=" * 84)
            print("FILE MANAGEMENT SETTINGS".center(84))
            print("=" * 84)
            
            use_symlinks = os.environ.get('USE_SYMLINKS', 'true').lower() == 'true'
            refresh_plex = os.environ.get('REFRESH_PLEX', 'false').lower() == 'true'
            
            print("\nCurrent File Management Settings:")
            print(f"1. Use Symlinks: {'Enabled' if use_symlinks else 'Disabled (Copy files)'}")
            print(f"2. Refresh Plex after changes: {'Enabled' if refresh_plex else 'Disabled'}")
            print("3. Configure Plex Connection Settings")
            print("q. Return to Settings Menu")
            
            choice = input("\nSelect option: ").strip().lower()
            
            if choice == '1':
                new_setting = input("\nUse symlinks instead of copying files? (y/n): ").strip().lower()
                if new_setting in ('y', 'n'):
                    _update_env_var('USE_SYMLINKS', 'true' if new_setting == 'y' else 'false')
                    print(f"\nUse symlinks setting: {'Enabled' if new_setting == 'y' else 'Disabled'}")
                input("\nPress Enter to continue...")
            elif choice == '2':
                new_setting = input("\nRefresh Plex after changes? (y/n): ").strip().lower()
                if new_setting in ('y', 'n'):
                    _update_env_var('REFRESH_PLEX', 'true' if new_setting == 'y' else 'false')
                    print(f"\nRefresh Plex setting: {'Enabled' if new_setting == 'y' else 'Disabled'}")
                input("\nPress Enter to continue...")
            elif choice == '3':
                self._configure_plex_settings()
            elif choice == 'q':
                return
            else:
                print("\nInvalid option.")
                input("\nPress Enter to continue...")

    def _configure_plex_settings(self):
        """Configure Plex connection settings."""
        clear_screen()
        display_ascii_art()
        print("=" * 84)
        print("PLEX CONNECTION SETTINGS".center(84))
        print("=" * 84)
        
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
            input("\nPress Enter to continue...")
            
        elif choice == '2':
            new_token = input("\nEnter Plex auth token: ").strip()
            if new_token:
                _update_env_var('PLEX_TOKEN', new_token)
                print("\nPlex token updated.")
            input("\nPress Enter to continue...")
            
        elif choice == '3':
            new_section = input("\nEnter Movies library section ID: ").strip()
            if new_section.isdigit():
                _update_env_var('PLEX_MOVIES_SECTION', new_section)
                print("\nMovies section updated.")
            input("\nPress Enter to continue...")
            
        elif choice == '4':
            new_section = input("\nEnter TV Shows library section ID: ").strip()
            if new_section.isdigit():
                _update_env_var('PLEX_TV_SECTION', new_section)
                print("\nTV Shows section updated.")
            input("\nPress Enter to continue...")
            
        elif choice == '5':
            new_section = input("\nEnter Anime Movies library section ID: ").strip()
            if new_section.isdigit():
                _update_env_var('PLEX_ANIME_MOVIES_SECTION', new_section)
                print("\nAnime Movies section updated.")
            input("\nPress Enter to continue...")
            
        elif choice == '6':
            new_section = input("\nEnter Anime TV library section ID: ").strip()
            if new_section.isdigit():
                _update_env_var('PLEX_ANIME_TV_SECTION', new_section)
                print("\nAnime TV section updated.")
            input("\nPress Enter to continue...")
            
        elif choice == '7':
            self._test_plex_connection()
            
        elif choice == 'q':
            return
            
        else:
            print("\nInvalid option.")
            input("\nPress Enter to continue...")
        
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
            print("\nPlex server URL and token must be configured first.")
            input("\nPress Enter to continue...")
            return
        
        try:
            # Remove trailing slash if present
            if plex_url.endswith('/'):
                plex_url = plex_url[:-1]
            
            # Make a simple API request to test the connection
            url = f"{plex_url}/library/sections?X-Plex-Token={plex_token}"
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                print("\n✓ Connection successful! Plex server is reachable.")
                
                # Show available sections
                try:
                    import xml.etree.ElementTree as ET
                    root = ET.fromstring(response.text)
                    sections = root.findall(".//Directory")
                    
                    if sections:
                        print("\nAvailable library sections:")
                        for section in sections:
                            section_id = section.get('key')
                            section_title = section.get('title')
                            section_type = section.get('type')
                            print(f"  - ID: {section_id}, Title: {section_title}, Type: {section_type}")
                    else:
                        print("\nNo library sections found on this Plex server.")
                except Exception as e:
                    print(f"\nError parsing Plex server response: {e}")
            else:
                print(f"\n✗ Connection failed with status code: {response.status_code}")
                print("Please check your Plex URL and token.")
        
        except requests.exceptions.ConnectionError:
            print("\n✗ Connection error while connecting to Plex server.")
            print("Please check the server URL and ensure it is running.")
        except requests.exceptions.Timeout:
            print("\n✗ Connection to Plex server timed out.")
            print("Please check your network settings.")
        except Exception as e:
            print(f"\n✗ Error refreshing Plex library: {e}")
        
        input("\nPress Enter to continue...")

    def _monitoring_settings(self):
        """Directory monitoring settings."""
        while True:
            clear_screen()
            display_ascii_art()
            print("=" * 84)
            print("MONITORING SETTINGS".center(84))
            print("=" * 84)
            
            interval_minutes = os.environ.get('MONITOR_INTERVAL_MINUTES', '60')
            
            print("\nCurrent Monitoring Settings:")
            print(f"1. Monitoring Interval: {interval_minutes} minutes")
            print("2. Check Monitor Status")
            print("q. Return to Settings Menu")
            
            choice = input("\nSelect option: ").strip().lower()
            
            if choice == '1':
                new_interval = input("\nEnter monitoring interval in minutes (10-1440): ").strip()
                if new_interval.isdigit() and 10 <= int(new_interval) <= 1440:
                    _update_env_var('MONITOR_INTERVAL_MINUTES', new_interval)
                    print(f"\nMonitoring interval updated to {new_interval} minutes.")
                else:
                    print("\nInvalid interval. Please enter a number between 10 and 1440.")
                input("\nPress Enter to continue...")
            elif choice == '2':
                _check_monitor_status()
            elif choice == 'q':
                return
            else:
                print("\nInvalid option.")
                input("\nPress Enter to continue...")
    
    def _advanced_settings(self):
        """Advanced settings submenu."""
        while True:
            clear_screen()
            display_ascii_art()
            print("=" * 84)
            print("ADVANCED SETTINGS".center(84))
            print("=" * 84)
            
            debug_mode = os.environ.get('DEBUG_MODE', 'false').lower() == 'true'
            
            print("\nCurrent Advanced Settings:")
            print(f"1. Debug Mode: {'Enabled' if debug_mode else 'Disabled'}")
            print("2. Fix Scanner Files")
            print("3. Configure Scanner Lists")  # New option
            print("q. Return to Settings Menu")
            
            choice = input("\nSelect option: ").strip().lower()
            
            if choice == '1':
                new_setting = input("\nEnable debug mode? (y/n): ").strip().lower()
                if new_setting in ('y', 'n'):
                    _update_env_var('DEBUG_MODE', 'true' if new_setting == 'y' else 'false')
                    # Set the log level based on debug mode
                    if new_setting == 'y':
                        logging.getLogger().setLevel(logging.DEBUG)
                    else:
                        logging.getLogger().setLevel(logging.INFO)
                    print(f"\nDebug mode: {'Enabled' if new_setting == 'y' else 'Disabled'}")
                input("\nPress Enter to continue...")
            elif choice == '2':
                self._fix_scanner_files()
            elif choice == '3':
                self._configure_scanner_lists()
            elif choice == 'q':
                return
            else:
                print("\nInvalid option.")
                input("\nPress Enter to continue...")

    def _fix_scanner_files(self):
        """Run the scanner fix script to standardize ID formats."""
        clear_screen()
        display_ascii_art()
        print("=" * 84)
        print("FIX SCANNER FILES".center(84))
        print("=" * 84)
        
        print("\nThis will update all scanner files to use standardized TMDB ID format.")
        print("All IDs will be converted to [tmdb-XXXXX] format.")
        confirm = input("\nProceed? (y/n): ").strip().lower()
        
        if confirm == 'y':
            print("\nProcessing scanner files...")
            
            # Get the scanners directory
            scanner_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'scanners')
            scanner_files = [
                os.path.join(scanner_dir, 'movies.txt'),
                os.path.join(scanner_dir, 'tv_series.txt'),
                os.path.join(scanner_dir, 'anime_movies.txt'),
                os.path.join(scanner_dir, 'anime_series.txt')
            ]
            
            total_processed = 0
            total_fixed = 0
            
            for scanner_file in scanner_files:
                if os.path.exists(scanner_file):
                    print(f"Processing {os.path.basename(scanner_file)}...")
                    try:
                        # Call the fix_scanner_ids function
                        from src.main import fix_scanner_ids
                        processed, fixed = fix_scanner_ids(scanner_file)
                        total_processed += processed
                        total_fixed += fixed
                        print(f"  - Processed {processed} entries, fixed {fixed}")
                    except Exception as e:
                        print(f"  - Error: {e}")
            
            print(f"\nComplete! Processed {total_processed} total entries, fixed {total_fixed}")
        
        input("\nPress Enter to continue...")
    
    def _configure_scanner_lists(self):
        """Configure scanner lists for different content types."""
        clear_screen()
        display_ascii_art()
        print("=" * 84)
        print("SCANNER LISTS CONFIGURATION".center(84))
        print("=" * 84)
        
        # Get the scanners directory
        scanner_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'scanners')
        if not os.path.exists(scanner_dir):
            os.makedirs(scanner_dir, exist_ok=True)
        
        # Define standard content types with their display names and environment variable names
        standard_content_types = {
            "Movies": {
                "env_var": "SCANNER_MOVIES",
                "default_file": "movies.txt"
            },
            "TV Series": {
                               "env_var": "SCANNER_TV",
                "default_file": "tv_series.txt"
            },
            "Anime Movies": {
                "env_var": "SCANNER_ANIME_MOVIES",
                "default_file": "anime_movies.txt"
            },
            "Anime Series": {
                "env_var": "SCANNER_ANIME_TV",
                "default_file": "anime_series.txt"
            },
            "Wrestling": {
                "env_var": "SCANNER_WRESTLING",
                "default_file": "wrestling.txt"
            }
        }
        
        # Load custom content types from environment
        custom_types_json = os.environ.get('SCANNER_CUSTOM_TYPES', '{}')
        try:
            custom_content_types = json.loads(custom_types_json)
        except json.JSONDecodeError:
            custom_content_types = {}
        
        # Combine standard and custom content types
        all_content_types = {**standard_content_types, **custom_content_types}
        
        # Get available scanner files in the directory
        available_files = []
        if os.path.exists(scanner_dir):
            available_files = [f for f in os.listdir(scanner_dir) 
                              if os.path.isfile(os.path.join(scanner_dir, f)) and f.endswith('.txt')]
        
        # Show current scanner mappings
        print("\nCurrent Scanner Mappings:")
        print("-" * 84)
        print(f"{'Content Type':<20} | {'Scanner File':<30} | {'Status':<15}")
        print("-" * 84)
        
        for content_type, config in all_content_types.items():
            # Get current scanner file for this content type
            env_var = config["env_var"]
            default_file = config["default_file"]
            current_file = os.environ.get(env_var, default_file)
            
            # Check if the file exists
            file_path = os.path.join(scanner_dir, current_file)
            if os.path.exists(file_path):
                status = "Available"
            else:
                status = "Missing"
            
            print(f"{content_type:<20} | {current_file:<30} | {status:<15}")
        
        print("\nOptions:")
        print("1. Change scanner file for a content type")
        print("2. Create a new scanner file")
        print("3. View scanner file contents")
        print("4. Create new content type") # New option for custom content types
        print("5. Delete custom content type") # Option to remove custom types
        print("q. Return to Advanced Settings")
        
        choice = input("\nSelect option: ").strip().lower()
        
        if choice == '1':
            self._change_content_type_scanner(scanner_dir, all_content_types, available_files)
        elif choice == '2':
            self._create_new_scanner_file(scanner_dir, all_content_types)
        elif choice == '3':
            self._view_scanner_contents(scanner_dir, available_files)
        elif choice == '4':
            self._create_custom_content_type(scanner_dir, all_content_types, custom_content_types)
        elif choice == '5':
            self._delete_custom_content_type(all_content_types, custom_content_types)
        elif choice != 'q':
            print("\nInvalid option.")
            input("\nPress Enter to continue...")

    def _change_content_type_scanner(self, scanner_dir, content_types, available_files):
        """Change which scanner file is used for a content type."""
        clear_screen()
        display_ascii_art()
        print("=" * 84)
        print("CHANGE CONTENT TYPE SCANNER".center(84))
        print("=" * 84)
        
        # Display content types to choose from
        print("\nSelect content type to configure:")
        content_list = list(content_types.keys())
        for i, content_type in enumerate(content_list, 1):
            config = content_types[content_type]
            current_file = os.environ.get(config["env_var"], config["default_file"])
            print(f"{i}. {content_type:<15} (Current: {current_file})")
        
        # Get user selection for content type
        type_choice = input("\nSelect content type (number) or 'q' to return: ").strip().lower()
        
        if type_choice == 'q':
            return
        
        try:
            type_index = int(type_choice) - 1
            if 0 <= type_index < len(content_list):
                selected_type = content_list[type_index]
                config = content_types[selected_type]
                current_file = os.environ.get(config["env_var"], config["default_file"])
                
                # Show available scanner files
                print(f"\nSelect scanner file for {selected_type}:")
                print(f"Current: {current_file}")
                print("\nAvailable scanner files:")
                
                if not available_files:
                    print("No scanner files found.")
                    print("\nCreating a new scanner file...")
                    self._create_new_scanner_file(scanner_dir, content_types, selected_type)
                    return
                
                # Display available files with indices
                for i, file_name in enumerate(available_files, 1):
                    print(f"{i}. {file_name}")
                
                # Option to create a new file
                print(f"{len(available_files) + 1}. Create new scanner file")
                
                # Get user selection for scanner file
                file_choice = input("\nSelect scanner file (number) or 'q' to cancel: ").strip().lower()
                
                if file_choice == 'q':
                    return
                
                try:
                    choice_num = int(file_choice)
                    
                   
                    # Create new file option
                    if choice_num == len(available_files) + 1:
                        self._create_new_scanner_file(scanner_dir, content_types, selected_type)
                        return
                    
                    # Select existing file option
                    elif 1 <= choice_num <= len(available_files):
                        selected_file = available_files[choice_num - 1]
                        
                        # Update environment variable
                        _update_env_var(config["env_var"], selected_file)
                        print(f"\nUpdated {selected_type} to use '{selected_file}'.")
                        input("\nPress Enter to continue...")
                    else:
                        print("\nInvalid selection.")
                        input("\nPress Enter to continue...")
                except ValueError:
                    print("\nInvalid input. Please enter a number.")
                    input("\nPress Enter to continue...")
        except ValueError:
            print("\nInvalid input. Please enter a number.")
            input("\nPress Enter to continue...")

    def _create_new_scanner_file(self, scanner_dir, content_types, preset_type=None):
        """Create a new scanner file."""
        clear_screen()
        display_ascii_art()
        print("=" * 84)
        print("CREATE NEW SCANNER FILE".center(84))
        print("=" * 84)
        
        # Get file name
        file_name = input("\nEnter new scanner file name (.txt will be added if missing): ").strip()
        
        if not file_name:
            print("\nOperation cancelled.")
            input("\nPress Enter to continue...")
            return
        
        # Add .txt extension if missing
        if not file_name.endswith('.txt'):
            file_name += '.txt'
        
        # Create the file path
        file_path = os.path.join(scanner_dir, file_name)
        
        # Check if file already exists
        if os.path.exists(file_path):
            print(f"\nFile '{file_name}' already exists.")
            input("\nPress Enter to continue...")
            return
        
        # If content type is preset, use it, otherwise ask user
        selected_type = preset_type
        
        if not selected_type:
            # Show available content types
            print("\nSelect content type for this scanner:")
            content_list = list(content_types.keys())
            
            for i, content_type in enumerate(content_list, 1):
                print(f"{i}. {content_type}")
            
            # Get content type selection
            type_choice = input("\nSelect content type (number) or 'q' to cancel: ").strip().lower()
            
            if type_choice == 'q':
                return
            
            try:
                type_index = int(type_choice) - 1
                if 0 <= type_index < len(content_list):
                    selected_type = content_list[type_index]
                else:
                    print("\nInvalid selection.")
                    input("\nPress Enter to continue...")
                    return
            except ValueError:
                print("\nInvalid input. Please enter a number.")
                input("\nPress Enter to continue...")
                return
    
        # Create the file
        try:
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(f"# Scanner file for {selected_type}\n")
                f.write("# Format: Title (Year) [tmdb-ID]\n")
                f.write("# Example: The Matrix (1999) [tmdb-603]\n\n")
            
            # Ask if this should be the default scanner for this content type
            make_default = input(f"\nMake this the default scanner for {selected_type}? (y/n): ").strip().lower()
            
            if make_default == 'y':
                # Update environment variable
                config = content_types[selected_type]
                env_var = config["env_var"]
                _update_env_var(env_var, file_name)
                print(f"\nCreated new scanner file '{file_name}' and set as default for {selected_type}.")
            else:
                print(f"\nCreated new scanner file '{file_name}'.")
        
            input("\nPress Enter to continue...")
        except Exception as e:
            print(f"\nError creating scanner file: {e}")
            input("\nPress Enter to continue...")

    def _view_scanner_contents(self, scanner_dir, available_files):
        """View the contents of a scanner file."""
        clear_screen()
        display_ascii_art()
        print("=" * 84)
        print("VIEW SCANNER FILE CONTENTS".center(84))
        print("=" * 84)
        
        # Get available scanner files if not provided
        if not available_files and os.path.exists(scanner_dir):
            available_files = [f for f in os.listdir(scanner_dir) 
                              if os.path.isfile(os.path.join(scanner_dir, f)) and f.endswith('.txt')]
        
        # Display scanner files
        if not available_files:
            print("\nNo scanner files found.")
            input("\nPress Enter to continue...")
            return
        
        print("\nAvailable Scanner Files:")
        for i, file_name in enumerate(available_files, 1):
            print(f"{i}. {file_name}")
        
        # Get user selection
        file_choice = input("\nSelect a scanner file to view (number) or 'q' to return: ").strip().lower()
        
        if file_choice == 'q':
            return
        
        try:
            file_index = int(file_choice) - 1
            if 0 <= file_index < len(available_files):
                selected_file = available_files[file_index]
                file_path = os.path.join(scanner_dir, selected_file)
                
                # Read file contents
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        lines = [line for line in f if line.strip() and not line.strip().startswith('#')]
                        total_lines = len(lines)
                except Exception as e:
                    print(f"\nError reading file: {e}")
                    input("\nPress Enter to continue...")
                    return
            
                # Set up paging
                page_size = 20
                page = 0
                total_pages = (total_lines + page_size - 1) // page_size if total_lines > 0 else 1
            
                while True:
                    clear_screen()
                    display_ascii_art()
                    print("=" * 84)
                    print(f"VIEWING {selected_file}".center(84))
                    print("=" * 84)
                    
                    # Display content
                    if total_lines == 0:
                        print("\nFile is empty or contains only comments.")
                    else:
                        start_idx = page * page_size
                        end_idx = min(start_idx + page_size, total_lines)
                        
                        print(f"\nShowing entries {start_idx+1}-{end_idx} of {total_lines}")
                        print("-" * 84)
                        
                        for i in range(start_idx, end_idx):
                            print(f"{i+1}. {lines[i].strip()}")
                
                    # Navigation options
                    print("\nNavigation:")
                    if page > 0:
                        print("p - Previous page")
                    if page < total_pages - 1:
                        print("n - Next page")
                    print("q - Return to scanner configuration")
                    
                    nav_choice = input("\nEnter choice: ").strip().lower()
                    
                    if nav_choice == 'p' and page > 0:
                        page -= 1
                    elif nav_choice == 'n' and page < total_pages - 1:
                        page += 1
                    elif nav_choice == 'q':
                        break
            else:
                print("\nInvalid file selection.")
                input("\nPress Enter to continue...")
        except ValueError:
            print("\nInvalid input. Please enter a number.")
            input("\nPress Enter to continue...")

def main():
    """Main function to run the Scanly application."""
    clear_screen()
    display_ascii_art()
    
    print("=" * 84)
    print("MAIN MENU".center(84))
    print("=" * 84)
    
    while True:
        
        # Always available options
        menu_options = {
            "1": ("Individual Scan", None),
            "2": ("Multi Scan", None),
        }
        
        # Conditionally available options
        next_option = 3
        
        # Resume scan - only if scan history exists
        if has_scan_history():
            menu_options[str(next_option)] = ("Resume Scan", None)
            next_option += 1
        
        # Review skipped items - only if skipped items exist
        if has_skipped_items():
            menu_options[str(next_option)] = ("Review Skipped Items", None)
            next_option += 1
            
        # Clear history - only if scan history or skipped items exist
        if has_scan_history() or has_skipped_items():
            menu_options[str(next_option)] = ("Clear History", None)
            next_option += 1
        
        # Standard options
        menu_options[str(next_option)] = ("Settings", None)
        next_option += 1
        
        menu_options[str(next_option)] = ("Help", None)
        next_option += 1
        
        menu_options["0"] = ("Quit", None)
        
        # Display menu options
        for key, (option_text, _) in menu_options.items():
            print(f"{key}. {option_text}")
        
        choice = input("\nSelect option: ").strip()
        
        # Process the selected option
        if choice == "1":
            # Individual scan
            clear_screen()
            display_ascii_art()
            print("=" * 84)
            print("INDIVIDUAL SCAN".center(84))
            print("=" * 84)
            directory = input("\nEnter directory path to scan: ").strip()
            directory = _clean_directory_path(directory)
            
            if os.path.isdir(directory):
                processor = DirectoryProcessor(directory)
                processor._process_media_files()
                clear_screen()
                display_ascii_art()
            else:
                print("\nInvalid directory path. Please enter a valid path.")
                input("\nPress Enter to continue...")
                clear_screen()
                display_ascii_art()  # Show ASCII art
        
        elif choice == "2":
            # Multi scan
            clear_screen()
            display_ascii_art()  # Show ASCII art
            print("=" * 84)
            print("MULTI SCAN".center(84))
            print("=" * 84)
            perform_multi_scan()
            clear_screen()
            display_ascii_art()  # Show ASCII art
        
        elif choice in menu_options and menu_options[choice][0] == "Resume Scan":
            # Resume scan
            clear_screen()
            display_ascii_art()
            print("=" * 84)
            print("RESUME SCAN".center(84))
            print("=" * 84)
            print("\nThis feature is not implemented yet.")
            input("\nPress Enter to continue...")
            clear_screen()
            display_ascii_art()  # Show ASCII art
        
        elif choice in menu_options and menu_options[choice][0] == "Review Skipped Items":
            # Review skipped items
            clear_screen()
            review_skipped_items()
        
        elif choice in menu_options and menu_options[choice][0] == "Clear History":
            # Clear history
            clear_screen()
            display_ascii_art()
            print("=" * 84)
            print("CLEAR HISTORY".center(84))
            print("=" * 84)
            confirm = input("\nAre you sure you want to clear all history? (y/n): ").strip().lower()
            if confirm == 'y':
                clear_all_history()
            else:
                print("\nOperation cancelled.")
                input("\nPress Enter to continue...")
                clear_screen()
                display_ascii_art()
        
        elif choice in menu_options and menu_options[choice][0] == "Settings":
            # Settings
            settings_menu = SettingsMenu()
            settings_menu.display()
            clear_screen()
            display_ascii_art()
        
        elif choice in menu_options and menu_options[choice][0] == "Help":
            # Help
            display_help()
            
        elif choice == "0":
            # Quit
            clear_screen()
            print("\nThank you for using Scanly!")
            break
            
        else:
            print("\nInvalid option. Please try again.")
            input("\nPress Enter to continue...")
            clear_screen()
            display_ascii_art()  # Show ASCII art

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
# filepath: media_organizer.py

import os
import re
import argparse
import shutil
from pathlib import Path

def extract_info_from_filename(filename):
    """Extract title, year, season, and episode from filename."""
    # Try to match movie pattern: could be various formats
    movie_patterns = [
        r'(.+?)[\.\s]\((\d{4})\)\.([a-zA-Z0-9]+)$',  # Title (Year).ext
        r'(.+?)\.(\d{4})\..*\.([a-zA-Z0-9]+)$',      # Title.Year.anything.ext
        r'(.+?)\.(\d{4})\.([a-zA-Z0-9]+)$',          # Title.Year.ext
    ]
    
    for pattern in movie_patterns:
        movie_match = re.search(pattern, filename)
        if movie_match:
            title = movie_match.group(1).replace('.', ' ').strip()
            year = movie_match.group(2)
            extension = movie_match.group(3)
            return {
                'type': 'movie',
                'title': title,
                'year': year,
                'extension': extension
            }
    
    # Try to match TV show pattern: Title.S01E01.ext or similar
    tv_pattern = r'(.+?)[\.\s]S(\d{1,2})E(\d{1,2})(?:\.|\s).*\.([a-zA-Z0-9]+)$'
    tv_match = re.search(tv_pattern, filename, re.IGNORECASE)
    
    if tv_match:
        title = tv_match.group(1).replace('.', ' ').strip()
        season = tv_match.group(2).zfill(2)
        episode = tv_match.group(3).zfill(2)
        extension = tv_match.group(4)
        
        # Try to extract year from title if present
        year_pattern = r'(.+?)[\.\s]\((\d{4})\)'
        year_match = re.search(year_pattern, title)
        if year_match:
            title = year_match.group(1).strip()
            year = year_match.group(2)
        else:
            year = "YEAR"  # Placeholder
            
        return {
            'type': 'tv',
            'title': title,
            'year': year,
            'season': season,
            'episode': episode,
            'extension': extension
        }
    
    return None

def format_movie(info, tmdb_id=None):
    """Format movie according to 'MEDIA TITLE (YEAR).extension' in 'MEDIA TITLE (YEAR) [tmdb-TMDB ID]'"""
    if not tmdb_id:
        tmdb_id = "TMDBID"  # Placeholder
        
    folder_name = f"{info['title']} ({info['year']}) [tmdb-{tmdb_id}]"
    file_name = f"{info['title']} ({info['year']}).{info['extension']}"
    
    return {
        'folder': folder_name,
        'file': file_name
    }

def format_tv_show(info, tmdb_id=None):
    """Format TV show according to specified pattern"""
    if not tmdb_id:
        tmdb_id = "TMDBID"  # Placeholder
        
    folder_name = f"{info['title']} ({info['year']}) [tmdb-{tmdb_id}]"
    season_folder = f"Season {info['season']}"
    file_name = f"{info['title']} ({info['year']}) - S{info['season']}E{info['episode']}.{info['extension']}"
    
    return {
        'folder': folder_name,
        'season_folder': season_folder,
        'file': file_name
    }

def organize_file(source_path, dest_base_path, tmdb_id=None, dry_run=True):
    """Organize a single file according to naming schema"""
    filename = os.path.basename(source_path)
    info = extract_info_from_filename(filename)
    
    if not info:
        print(f"Could not parse information from {filename}")
        return False
    
    if info['type'] == 'movie':
        output = format_movie(info, tmdb_id)
        dest_folder = os.path.join(dest_base_path, output['folder'])
        dest_file = os.path.join(dest_folder, output['file'])
        
        if dry_run:
            print(f"Would create folder: {dest_folder}")
            print(f"Would save file as: {os.path.basename(dest_file)}")
            print(f"Would move {source_path} to {dest_file}")
        else:
            os.makedirs(dest_folder, exist_ok=True)
            shutil.copy2(source_path, dest_file)
            print(f"Moved {source_path} to {dest_file}")
            
    elif info['type'] == 'tv':
        output = format_tv_show(info, tmdb_id)
        dest_folder = os.path.join(dest_base_path, output['folder'], output['season_folder'])
        dest_file = os.path.join(dest_folder, output['file'])
        
        if dry_run:
            print(f"Would create folder: {dest_folder}")
            print(f"Would save file as: {os.path.basename(dest_file)}")
            print(f"Would move {source_path} to {dest_file}")
        else:
            os.makedirs(dest_folder, exist_ok=True)
            shutil.copy2(source_path, dest_file)
            print(f"Moved {source_path} to {dest_file}")
    
    return True

def validate_output_format():
    """Test function to validate output formats"""
    print("=== Testing Movie Format ===")
    movie_info = {
        'title': '12 Angry Men',
        'year': '1957',
        'extension': 'mkv'
    }
    output = format_movie(movie_info, '389')
    print(f"Folder: {output['folder']}")
    print(f"File: {output['file']}")
    
    print("\n=== Testing TV Show Format ===")
    tv_info = {
        'title': 'Breaking Bad',
        'year': '2008',
        'season': '01',
        'episode': '05',
        'extension': 'mp4'
    }
    output = format_tv_show(tv_info, '1396')
    print(f"Folder: {output['folder']}")
    print(f"Season: {output['season_folder']}")
    print(f"File: {output['file']}")

def main():
    parser = argparse.ArgumentParser(description='Organize media files according to naming schema')
    parser.add_argument('source', help='Source file or directory')
    parser.add_argument('destination', help='Destination directory')
    parser.add_argument('--tmdb', help='TMDB ID (optional)')
    parser.add_argument('--recursive', action='store_true', help='Process directories recursively')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be done without making changes')
    parser.add_argument('--test', action='store_true', help='Test output format')
    
    args = parser.parse_args()
    
    if args.test:
        validate_output_format()
        return
    
    source_path = os.path.abspath(args.source)
    dest_path = os.path.abspath(args.destination)
    
    if not os.path.exists(source_path):
        print(f"Source path {source_path} does not exist")
        return
    
    if not os.path.exists(dest_path):
        if args.dry_run:
            print(f"Would create destination directory: {dest_path}")
        else:
            os.makedirs(dest_path, exist_ok=True)
            
    if os.path.isfile(source_path):
        organize_file(source_path, dest_path, args.tmdb, args.dry_run)
    elif os.path.isdir(source_path) and args.recursive:
        for root, _, files in os.walk(source_path):
            for file in files:
                file_path = os.path.join(root, file)
                organize_file(file_path, dest_path, args.tmdb, args.dry_run)
    elif os.path.isdir(source_path):
        for item in os.listdir(source_path):
            item_path = os.path.join(source_path, item)
            if os.path.isfile(item_path):
                organize_file(item_path, dest_path, args.tmdb, args.dry_run)

if __name__ == "__main__":
    main()