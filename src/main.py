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
                
                # Check scanner lists for matches
                scanner_matches = self._check_scanner_lists(title, year, is_tv, is_anime)
                
                print(f"\nProcessing: {subfolder_name}")
                print(f"  Title: {title}")
                print(f"  Year: {year if year else 'Unknown'}")
                print(f"  Type: {'TV Show' if is_tv else 'Movie'}")
                print(f"  Scanner Matches: {len(scanner_matches)}")
                
                # If multiple scanner matches found, ask user to select
                selected_match = None
                if len(scanner_matches) > 1:
                    print("\nSelect the correct match:")
                    for i, match in enumerate(scanner_matches):
                        title = match.get('title', 'Unknown')
                        year_str = f" ({match.get('year')})" if match.get('year') else ""
                        tmdb_id = match.get('tmdb_id', '')
                        id_str = f" [tmdb-{tmdb_id}]" if tmdb_id else ""
                        print(f"{i+1}. {title}{year_str}{id_str}")
                    print("0. None of these / Manual identification")
                    
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
                            
                            # Process the selected match directly and continue to next folder
                            self._create_symlinks(subfolder_path, title, year, is_tv, is_anime)
                            processed += 1
                            continue  # Skip to the next folder in the main loop
                        elif match_idx == -1:  # User selected "None of these"
                            print("\nProceeding with manual identification...")
                    except ValueError:
                        print("\nInvalid choice. Proceeding with extracted information.")
                elif len(scanner_matches) == 1:
                    selected_match = scanner_matches[0]
                    print(f"\nScanner match: {selected_match.get('title', 'Unknown')} ({selected_match.get('year', 'Unknown')})")
                    confirm = input("Use this match? (y/n): ").strip().lower()
                    if confirm == 'y':
                        title = selected_match.get('title', title)
                        year = selected_match.get('year', year)
    
                # Show options for this subfolder
                while True:
                    print("\nOptions:")
                    print("1. Accept (default - press Enter)")
                    print("2. New Search")
                    print("3. Change content type")
                    print("4. Skip (save for later review)")
                    print("5. Quit")
                    
                    choice = input("\nSelect option: ").strip()
                    
                    # Make Enter key select option 1 as default
                    if choice == "":
                        choice = "1"
                        
                    if choice == "1":
                        # Accept the extracted info
                        if self._create_symlinks(subfolder_path, title, year, is_tv, is_anime):
                            processed += 1
                        break
                    elif choice == "2":
                        # New Search (edit title/year)
                        new_title = input(f"Enter title [{title}]: ").strip()
                        if new_title:
                            title = new_title
                    
                        new_year = input(f"Enter year [{year if year else 'Unknown'}]: ").strip()
                        if new_year and re.match(r'^(19|20)\d{2}$', new_year):
                            year = new_year
                    
                        print(f"\nUpdated info:")
                        print(f"  Title: {title}")
                        print(f"  Year: {year if year else 'Unknown'}")
                        print(f"  Type: {'TV Show' if is_tv else 'Movie'}")
                        
                        confirm = input("\nUse this info? (y/n): ").strip().lower()
                        if confirm == 'y':
                            if self._create_symlinks(subfolder_path, title, year, is_tv, is_anime):
                                processed += 1
                            break
                    elif choice == "3":
                        # Change content type
                        print("\nSelect content type:")
                        print("1. Movie")
                        print("2. TV Show")
                        type_choice = input(f"Enter choice [{2 if is_tv else 1}]: ").strip()
                        is_tv = type_choice == "2" if type_choice in ["1", "2"] else is_tv
                        
                        # Anime selection
                        print("\nIs this anime?")
                        print("1. No")
                        print("2. Yes")
                        anime_choice = input(f"Enter choice [{2 if is_anime else 1}]: ").strip()
                        is_anime = anime_choice == "2" if anime_choice in ["1", "2"] else is_anime
                        
                        print(f"\nUpdated info:")
                        print(f"  Title: {title}")
                        print(f"  Year: {year if year else 'Unknown'}")
                        print(f"  Type: {'TV Show' if is_tv else 'Movie'}")
                        
                        confirm = input("\nUse this info? (y/n): ").strip().lower()
                        if confirm == 'y':
                            if self._create_symlinks(subfolder_path, title, year, is_tv, is_anime):
                                processed += 1
                            break
                    elif choice == "4":
                        # Skip this subfolder
                        print(f"Skipping subfolder: {subfolder_name}")
                        skipped_items_registry.append({
                            'subfolder': subfolder_name,
                            'path': subfolder_path,
                            'skipped_date': datetime.datetime.now().isoformat()
                        })
                        save_skipped_items(skipped_items_registry)
                        break
                    elif choice == "5":
                        # Quit the scan
                        if input("Are you sure you want to quit the scan? (y/n): ").strip().lower() == 'y':
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

def main():
    """Main function to run the Scanly application."""
    clear_screen()
    display_ascii_art()
    
    print("=" * 60)
    print("WELCOME TO SCANLY")
    print("=" * 60)
    
    while True:
        print("\nMAIN MENU")
        print("1. Individual Scan")
        print("2. Multi Scan")
        print("3. Resume Scan")
        print("4. Review Skipped Items")
        print("5. Settings")
        print("6. Help")
        print("0. Quit")
        
        choice = input("\nSelect option: ").strip()
        
        if choice == "1":
            # Individual scan
            directory = input("\nEnter directory path to scan: ").strip()
            directory = _clean_directory_path(directory)
            
            if os.path.isdir(directory):
                processor = DirectoryProcessor(directory)
                processor._process_media_files()
            else:
                print("\nInvalid directory path.")
                input("\nPress Enter to continue...")
        
        elif choice == "4":
            # Review skipped items
            review_skipped_items()
        
        elif choice == "6":
            # Help
            display_help()
            
        elif choice == "0":
            # Quit
            print("\nThank you for using Scanly!")
            break
            
        else:
            print("\nOption not implemented yet.")
            input("\nPress Enter to continue...")

if __name__ == "__main__":
    main()