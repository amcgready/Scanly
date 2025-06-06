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
        """Check appropriate scanner lists for matches based on content type.
        
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
                print("\nDestination directory not set. Please configure in Settings.")
                return False
            
            # Make sure destination directory exists
            if not os.path.exists(DESTINATION_DIRECTORY):
                os.makedirs(DESTINATION_DIRECTORY, exist_ok=True)
            
            # Format the base name with year for both folder and files
            base_name = title
            if year and not is_tv and not is_wrestling:
                base_name = f"{title} ({year})"
            
            # Add TMDB ID if available
            if tmdb_id:
                base_name = f"{base_name} [tmdb-{tmdb_id}]"
            
            # Determine appropriate subdirectory based on content type
            if is_wrestling:
                dest_subdir = os.path.join(DESTINATION_DIRECTORY, "Wrestling")
            elif is_anime and is_tv:
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
                        
                        # Get the file extension
                        _, file_ext = os.path.splitext(file)
                        
                        # Create the proper file name: 'Media Title (Year).extension'
                        if year and not is_tv and not is_wrestling:
                            target_filename = f"{title} ({year}){file_ext}"
                        else:
                            target_filename = f"{title}{file_ext}"
                            
                        target_file = os.path.join(target_dir_path, target_filename)
                        
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
                                tmdb_id = selected_match.get('tmdb_id', '')
                                
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
            else:
                print("\nInvalid directory path.")
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
                print("\nHistory clearing cancelled.")
                input("\nPress Enter to continue...")
                clear_screen()
                display_ascii_art()  # Show ASCII art
        
        elif choice in menu_options and menu_options[choice][0] == "Settings":
            # Settings
            clear_screen()
            display_ascii_art()
            print("=" * 84)
            print("SETTINGS".center(84))
            print("=" * 84)
            print("\nThis feature is not implemented yet.")
            input("\nPress Enter to continue...")
            clear_screen()
            display_ascii_art()  # Show ASCII art
        
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
"""
Fix movie IDs in scanner files.

This script converts ID formats in scanner files to the standard [tmdb-ID] format.
"""

import os
import re
import sys
from pathlib import Path

def fix_scanner_ids(scanner_file):
    """
    Fix IDs in a scanner file to use [tmdb-ID] format.
    
    Args:
        scanner_file: Path to the scanner file
    
    Returns:
        Tuple of (number of entries processed, number of entries modified)
    """
    if not os.path.exists(scanner_file):
        print(f"Scanner file not found: {scanner_file}")
        return 0, 0
    
    try:
        with open(scanner_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        total_entries = len(lines)
        modified_count = 0
        corrected_lines = []
        
        for line in lines:
            # Skip empty lines
            if not line.strip():
                corrected_lines.append(line)
                continue
            
            # Replace different ID formats with [tmdb-ID]
            # Case 1: [movie:ID]
            modified_line = re.sub(r'\[movie:(\d+)\]', r'[tmdb-\1]', line)
            
            # Case 2: [ID] (plain ID without prefix)
            modified_line = re.sub(r'\[(\d+)\](?!\])', r'[tmdb-\1]', modified_line)
            
            if modified_line != line:
                modified_count += 1
                
            corrected_lines.append(modified_line)
        
        # Write the modified content back to file
        with open(scanner_file, 'w', encoding='utf-8') as f:
            f.writelines(corrected_lines)
        
        return total_entries, modified_count
    
    except Exception as e:
        print(f"Error fixing scanner IDs: {e}")
        return 0, 0

def main():
    """Main entry point."""
    script_dir = Path(__file__).parent
    scanner_dir = script_dir / 'scanners'
    
    # Fix scanner files
    scanner_files = [
        'movies.txt',
        'anime_movies.txt',
        'tv_series.txt',
        'anime_series.txt'
    ]
    
    for scanner_file in scanner_files:
        file_path = scanner_dir / scanner_file
        if file_path.exists():
            print(f"Processing {scanner_file}...")
            total, fixed = fix_scanner_ids(str(file_path))
            print(f"  - Total entries: {total}")
            print(f"  - Fixed entries: {fixed}")
        else:
            print(f"Scanner file not found: {scanner_file}")

if __name__ == "__main__":
    main()