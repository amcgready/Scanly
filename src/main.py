#!/usr/bin/env python3
"""Scanly: A media file scanner and organizer.

This module is the main entry point for the Scanly application.
"""
import logging
import os
import sys
import json
import time
import re
import difflib
from pathlib import Path

# Ensure parent directory is in path for imports
parent_dir = os.path.dirname(os.path.dirname(__file__))
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

# ======================================================================
# CRITICAL FIX: Silence problematic loggers BEFORE any imports
# ======================================================================
for logger_name in ['discord_webhook', 'urllib3', 'requests', 'websocket']:
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.CRITICAL)
    logger.propagate = False

# Import dotenv to load environment variables
try:
    from dotenv import load_dotenv
    load_dotenv()  # Load environment variables from .env file
except ImportError:
    print("Warning: dotenv package not found. Environment variables must be set manually.")

# Import the logger utility
from src.utils.logger import get_logger

# Create log directory if it doesn't exist
log_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'logs')
os.makedirs(log_dir, exist_ok=True)

# Configure file handler to capture all logs regardless of console visibility
file_handler = logging.FileHandler(os.path.join(log_dir, 'scanly.log'))
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))

# Configure root logger WITHOUT a console handler
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[file_handler]  # Only file handler, no console handler
)

# Get logger for this module
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
        logger.error(f"Error updating environment variable: {e}")
        return False

# Try to load the TMDB API 
try:
    from src.api.tmdb import TMDB
except ImportError as e:
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

# Function to clear the screen - updating to remove excessive newlines
def clear_screen():
    """Clear the terminal screen using optimal methods."""
    # Remove the debug message that was adding lines
    # print("\n\n--- Clearing screen... ---\n\n")  # Remove this debug line
    
    try:
        # Method 1: Standard os.system call - this should be sufficient for most terminals
        os.system('cls' if os.name == 'nt' else 'clear')
        
        # Only use these backup methods if absolutely necessary:
        # We'll keep one ANSI method as backup, but remove the rest to avoid extra newlines
        print("\033[H\033[J", end="", flush=True)
        
        # Remove the excessive newlines
        # print("\n" * 100)  # Remove this - it adds a lot of blank space
    except Exception as e:
        logger.error(f"Error clearing screen: {e}")

# Function to display ASCII art
def display_ascii_art():
    """Display the program's ASCII art."""
    try:
        art_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'art.txt')
        if os.path.exists(art_path):
            with open(art_path, 'r') as f:
                print(f.read())
        else:
            print("SCANLY")  # Fallback if art file doesn't exist
    except Exception as e:
        print("SCANLY")  # Fallback if art file can't be loaded
    print()  # Add extra line after ASCII art

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
    print("  3. Monitor Management - Add/remove directories for continuous monitoring")
    print("  4. Settings       - Configure application settings")
    print("  5. Help           - Display this help information")
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
                print(f"{i + 1}. {item['path']}")
        
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
            # Logic for processing a skipped item
            item_num = input("\nEnter item number to process: ").strip()
            try:
                item_idx = int(item_num) - 1
                if 0 <= item_idx < len(skipped_items_registry):
                    # Process the item
                    print(f"\nProcessing item: {skipped_items_registry[item_idx]['path']}")
                    # Actual processing would happen here
                    
                    # Remove from skipped items after processing
                    skipped_items_registry.pop(item_idx)
                    save_skipped_items(skipped_items_registry)
                else:
                    print("\nInvalid item number.")
            except ValueError:
                print("\nPlease enter a valid number.")
            
            input("\nPress Enter to continue...")
            
        elif choice == "2":
            clear_skipped_items()
            break
            
        elif choice == "3" and total_pages > 1:
            current_page = min(current_page + 1, total_pages)
            
        elif choice == "4" and total_pages > 1:
            current_page = max(current_page - 1, 1)
            
        elif choice == "0":
            break
            
        else:
            print("\nInvalid option.")
            input("\nPress Enter to continue...")

# Import the monitor manager WITHOUT auto-starting it
try:
    from src.core.monitor import get_monitor_manager
except ImportError:
    logger.warning("Monitor module not available")
    # Create a dummy get_monitor_manager function
    def get_monitor_manager():
        logger.error("Monitor functionality is not available")
        return None

try:
    from src.utils.webhooks import (
        send_monitored_item_notification,
        send_symlink_creation_notification,
        send_symlink_deletion_notification,
        send_symlink_repair_notification
    )
    webhook_available = True
except ImportError:
    logger.warning("Webhook functionality is not available")
    webhook_available = False
    
    # Create stub functions for webhooks
    def send_monitored_item_notification(item_data):
        logger.error("Webhook functionality is not available")
        return False
        
    def send_symlink_creation_notification(media_name, year, poster, description, original_path, symlink_path):
        logger.error("Webhook functionality is not available")
        return False
        
    def send_symlink_deletion_notification(media_name, year, poster, description, original_path, symlink_path):
        logger.error("Webhook functionality is not available")
        return False
        
    def send_symlink_repair_notification(media_name, year, poster, description, original_path, symlink_path):
        logger.error("Webhook functionality is not available")
        return False

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
        """Check appropriate scanner lists for matches based on content type"""
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
        """Compare two titles to determine if they match."""
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
            # Look for 4-digit sequences that could be years
            import datetime
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
        
    def _prompt_for_content_type(self, current_is_tv, current_is_anime):
        """Helper method to prompt user for content type selection."""
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

    def _create_symlinks(self, subfolder_path, title, year, is_tv=False, is_anime=False, is_wrestling=False, tmdb_id=None):
        """Create symlinks from the source directory to the destination directory."""
        try:
            # Check if destination directory is configured
            if not DESTINATION_DIRECTORY:
                self.logger.error("Destination directory not configured")
                print("\nError: Destination directory not configured. Please configure in settings.")
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
                dest_subdir = os.path.join(DESTINATION_DIRECTORY, "Wrestling")
            elif is_anime and is_tv:
                dest_subdir = os.path.join(DESTINATION_DIRECTORY, "Anime Series")
            elif is_anime and not is_tv:
                dest_subdir = os.path.join(DESTINATION_DIRECTORY, "Anime Movies")
            elif not is_anime and is_tv:
                dest_subdir = os.path.join(DESTINATION_DIRECTORY, "TV Series")
            else:
                dest_subdir = os.path.join(DESTINATION_DIRECTORY, "Movies")
            
            # Create content type subdirectory if it doesn't exist
            if not os.path.exists(dest_subdir):
                os.makedirs(dest_subdir, exist_ok=True)
                self.logger.info(f"Created content subdirectory: {dest_subdir}")
            
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
                for file in files:
                    # Get the source file path
                    source_file_path = os.path.join(root, file)
                    
                    # Create the destination file path - use base_name without the (None) suffix
                    # Just use the original file extension instead of copying the entire filename
                    file_ext = os.path.splitext(file)[1]
                    if tmdb_id:
                        dest_file_name = f"{base_name}{file_ext}"
                    else:
                        dest_file_name = f"{base_name}{file_ext}"
                    
                    dest_file_path = os.path.join(target_dir_path, dest_file_name)
                    
                    # Create symlink or copy file
                    if use_symlinks:
                        # Remove existing symlink if it exists
                        if os.path.exists(dest_file_path):
                            os.remove(dest_file_path)
                        
                        # Create new symlink
                        os.symlink(source_file_path, dest_file_path)
                        self.logger.info(f"Created symlink: {dest_file_path} -> {source_file_path}")
                    else:
                        # Copy file if it doesn't exist
                        if not os.path.exists(dest_file_path):
                            shutil.copy2(source_file_path, dest_file_path)
                            self.logger.info(f"Copied file: {source_file_path} -> {dest_file_path}")
            
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
            return -1

# Update perform_individual_scan to properly clear the screen after error

def perform_individual_scan():
    """Perform an individual scan operation."""
    clear_screen()
    display_ascii_art()
    print("=" * 84)
    print("INDIVIDUAL SCAN".center(84))
    print("=" * 84)
    
    # Get directory to scan
    print("\nEnter the directory path to scan:")
    dir_input = input().strip()
    
    # Check if user wants to return to main menu
    if dir_input.lower() in ('exit', 'quit', 'back', 'return'):
        return
    
    # Validate directory path
    clean_path = _clean_directory_path(dir_input)
    if not os.path.isdir(clean_path):
        print(f"\nError: {clean_path} is not a valid directory.")
        input("\nPress Enter to continue...")
        clear_screen()  # Make sure we clear screen here before returning
        return
    
    # Create processor for this directory
    processor = DirectoryProcessor(clean_path)
    
    # Process the directory
    print(f"\nScanning directory: {clean_path}")
    result = processor._process_media_files()
    
    if result is not None and result >= 0:
        print(f"\nScan completed. Processed {result} items.")
    else:
        print("\nScan could not be completed due to an error.")
    
    input("\nPress Enter to continue...")
    clear_screen()  # Make sure we clear screen here before returning

def process_pending_files_multiscan(monitor_manager, pending_files):
    """Process pending files using multi-scan approach."""
    if not pending_files:
        print("\nNo pending files to process.")
        return 0
    
    # Extract directories from pending files
    directories = [file_info['path'] for file_info in pending_files]
    
    # Show confirmation with directories to scan
    clear_screen()
    display_ascii_art()
    print("=" * 84)
    print("PROCESS PENDING FILES".center(84))
    print("=" * 84)
    
    print(f"\nProcessing {len(directories)} pending items:")
    for i, directory in enumerate(directories, 1):
        print(f"  {i}. {os.path.basename(directory)}")
    
    # Process each directory
    total_processed = 0
    success_count = 0
    
    for i, directory in enumerate(directories, 1):
        clear_screen()
        display_ascii_art()
        print("=" * 84)
        print(f"PROCESSING ITEM {i} OF {len(directories)}".center(84))
        print("=" * 84)
        print(f"\nDirectory: {directory}")
        
        try:
            # Get the directory_id from the original pending_files list
            file_info = pending_files[i-1]
            dir_id = file_info.get('dir_id')
            
            # Check if directory still exists
            if not os.path.exists(directory):
                print(f"Directory no longer exists: {directory}")
                if dir_id:
                    monitor_manager.remove_pending_file(dir_id, directory)
                continue
            
            # Create processor for this directory
            processor = DirectoryProcessor(directory)
            result = processor._process_media_files()
            
            if result is not None and result >= 0:
                print(f"\nSuccessfully processed {result} items.")
                total_processed += result
                success_count += 1
                
                # Remove from pending files if successful
                if dir_id:
                    monitor_manager.remove_pending_file(dir_id, directory)
            else:
                print(f"\nFailed to process directory: {directory}")
        except Exception as e:
            logger.error(f"Error processing directory {directory}: {e}")
            print(f"Error: {str(e)}")
        
        input("\nPress Enter to continue to next item...")
    
    # Show summary after all directories processed
    clear_screen()
    display_ascii_art()
    print("=" * 84)
    print("PENDING FILES PROCESSING COMPLETE".center(84))
    print("=" * 84)
    print(f"\nSuccessfully processed {success_count} of {len(directories)} directories")
    print(f"Total items processed: {total_processed}")
    
    input("\nPress Enter to continue...")
    return success_count

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
            if directories:
                break
            else:
                print("You need to enter at least one directory.")
                continue
        
        # Check if user wants to return to main menu
        if dir_input.lower() in ('exit', 'quit', 'back', 'return'):
            if not directories:
                return
            else:
                break
        
        # Validate directory path
        clean_path = _clean_directory_path(dir_input)
        if os.path.isdir(clean_path):
            directories.append(clean_path)
            print(f"Added: {clean_path}")
        else:
            print(f"Error: '{clean_path}' is not a valid directory. Please try again.")
    
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
    for i, directory in enumerate(directories, 1):
        print(f"  {i}. {directory}")
    
    confirm = input("\nProceed with scan? (y/n): ").strip().lower()
    if confirm != 'y':
        print("\nScan cancelled.")
        input("\nPress Enter to continue...")
        clear_screen()
        display_ascii_art()
        return
    
    # Process each directory
    total_processed = 0
    for i, directory in enumerate(directories, 1):
        clear_screen()
        display_ascii_art()
        print("=" * 84)
        print(f"PROCESSING DIRECTORY {i} OF {len(directories)}".center(84))
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
        if result is not None and result > 0:
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
# Fix the handle_monitor_management function to properly handle pending files
def handle_monitor_management(monitor_manager):
    """Handle monitor management submenu."""
    if not monitor_manager:
        print("\nError: Monitor management is not available.")
        input("\nPress Enter to continue...")
        return
    
    while True:
        clear_screen()
        display_ascii_art()
        print("=" * 84)
        print("MONITOR MANAGEMENT".center(84))
        print("=" * 84)
        
        # Get status
        status = monitor_manager.get_monitoring_status()
        active_dirs = status.get('active_directories', [])
        is_active = status.get('active', False)
        
        # Show current status
        if is_active:
            print(f"\n✅ Monitoring is ACTIVE - {len(active_dirs)} directory(s) being monitored")
        else:
            print("\n❌ Monitoring is INACTIVE")
            
        # Get all directories
        directories = monitor_manager.get_monitored_directories()
        
        # Check pending files
        pending_files = monitor_manager.get_all_pending_files()
        pending_count = len(pending_files)
        
        # Check active directories
        if directories:
            print(f"\nMonitored Directories: {len(directories)}")
            i = 0
            for dir_id, info in directories.items():
                i += 1
                path = info.get('path', 'Unknown')
                name = info.get('name', os.path.basename(path))
                is_dir_active = info.get('active', False)
                status_icon = "🟢 " if is_dir_active else "⚪ "
                
                # Count pending files for this directory
                dir_pending = len(info.get('pending_files', []))
                pending_str = f" ({dir_pending} pending)" if dir_pending > 0 else ""
                
                print(f"{i}. {status_icon}{name}: {path}{pending_str}")
        else:
            print("\nNo directories are currently monitored.")
            
        # Show options
        print("\nOptions:")
        print("1. Add directory to monitor")
        print("2. Remove directory from monitoring")
        print("3. Toggle directory active state")
        print("4. Start all monitoring")
        if pending_count > 0:
            print(f"5. Check pending files ({pending_count})")
        else:
            print("5. Check pending files (0)")
        print("0. Return to main menu")
        
        choice = input("\nEnter choice: ").strip()
        
        if choice == "1":
            # Add directory
            print("\nEnter path to directory to monitor:")
            path = input().strip()
            if not path:
                continue
                
            path = _clean_directory_path(path)
            if not os.path.isdir(path):
                print(f"\nError: {path} is not a valid directory.")
                input("\nPress Enter to continue...")
                continue
                
            print("\nEnter a name for this directory (or leave blank to use the folder name):")
            name = input().strip()
            
            # Add the directory
            dir_id = monitor_manager.add_directory(path, name)
            if dir_id:
                print(f"\nDirectory added successfully with ID: {dir_id}")
            else:
                print("\nFailed to add directory.")
                
            input("\nPress Enter to continue...")
            
        elif choice == "2":
            # Remove directory
            if not directories:
                print("\nNo directories to remove.")
                input("\nPress Enter to continue...")
                continue
                
            print("\nEnter the number of the directory to remove:")
            dir_num = input().strip()
            
            try:
                dir_num = int(dir_num)
                if dir_num < 1 or dir_num > len(directories):
                    raise ValueError("Invalid directory number")
                    
                # Get the directory ID from its position
                dir_id = list(directories.keys())[dir_num - 1]
                
                if monitor_manager.remove_directory(dir_id):
                    print(f"\nDirectory {dir_num} removed successfully.")
                else:
                    print(f"\nFailed to remove directory {dir_num}.")
            except ValueError:
                print("\nPlease enter a valid directory number.")
                
            input("\nPress Enter to continue...")
            
        elif choice == "3":
            # Toggle active state
            if not directories:
                print("\nNo directories to toggle.")
                input("\nPress Enter to continue...")
                continue
                
            print("\nEnter the number of the directory to toggle:")
            dir_num = input().strip()
            
            try:
                dir_num = int(dir_num)
                if dir_num < 1 or dir_num > len(directories):
                    raise ValueError("Invalid directory number")
                    
                # Get the directory ID from its position
                dir_id = list(directories.keys())[dir_num - 1]
                
                new_state = monitor_manager.toggle_directory_active(dir_id)
                
                dir_info = directories[dir_id]
                name = dir_info.get('name', 'Unknown')
                print(f"\nDirectory '{name}' is now {'ACTIVE' if new_state else 'INACTIVE'}.")
            except ValueError:
                print("\nPlease enter a valid directory number.")
                
            input("\nPress Enter to continue...")
            
        elif choice == "4":
            # Start all monitoring
            count = monitor_manager.start_all()
            print(f"\nStarted monitoring {count} directories.")
            input("\nPress Enter to continue...")
            
        elif choice == "5":
            # Check pending files
            pending_files = monitor_manager.get_all_pending_files()
            
            if not pending_files:
                print("\nNo pending files found.")
                input("\nPress Enter to continue...")
                continue
            else:
                print(f"\nFound {len(pending_files)} pending files:")
                for i, file_info in enumerate(pending_files, 1):
                    print(f"  {i}. {file_info['name']} in {file_info['dir_name']}")
                
                print("\nDo you want to process these files now? (y/n)")
                if input().strip().lower() == 'y':
                    # Call the function to process pending files
                    success_count = process_pending_files_multiscan(monitor_manager, pending_files)
                    print(f"\nProcessed {success_count} out of {len(pending_files)} pending items.")
                    input("\nPress Enter to continue...")
            
        elif choice == "0":
            # Return to main menu
            return
            
        else:
            print("\nInvalid choice. Please try again.")
            time.sleep(1)
def handle_webhook_settings():
    """Handle webhook settings submenu."""
    while True:
        clear_screen()
        display_ascii_art()
        
        print("=" * 84)
        print("WEBHOOK SETTINGS".center(84))
        print("=" * 84)
        
        # Display current webhook settings
        default_webhook_url = os.environ.get('DEFAULT_DISCORD_WEBHOOK_URL', '')
        monitored_webhook_url = os.environ.get('DISCORD_WEBHOOK_URL_MONITORED_ITEM', '')
        creation_webhook_url = os.environ.get('DISCORD_WEBHOOK_URL_SYMLINK_CREATION', '')
        deletion_webhook_url = os.environ.get('DISCORD_WEBHOOK_URL_SYMLINK_DELETION', '')
        repair_webhook_url = os.environ.get('DISCORD_WEBHOOK_URL_SYMLINK_REPAIR', '')
        notifications_enabled = os.environ.get('ENABLE_DISCORD_NOTIFICATIONS', 'true').lower() == 'true'
        
        print("\nCurrent Webhook Settings:")
        print(f"  Discord Notifications Enabled: {'Yes' if notifications_enabled else 'No'}")
        print(f"  Default Webhook URL: {default_webhook_url or 'Not set'}")
        print(f"  Monitored Item Webhook URL: {monitored_webhook_url or 'Using default'}")
        print(f"  Symlink Creation Webhook URL: {creation_webhook_url or 'Using default'}")
        print(f"  Symlink Deletion Webhook URL: {deletion_webhook_url or 'Using default'}")
        print(f"  Symlink Repair Webhook URL: {repair_webhook_url or 'Using default'}")
        
        print("\nOptions:")
        print("  1. Set Default Webhook URL")
        print("  2. Set Monitored Item Webhook URL")
        print("  3. Set Symlink Creation Webhook URL")
        print("  4. Set Symlink Deletion Webhook URL")
        print("  5. Set Symlink Repair Webhook URL")
        print("  6. Toggle Discord Notifications")
        print("  7. Test Webhooks")
        print("  0. Return to Settings")
        
        choice = input("\nSelect option: ").strip()
        
        if choice == "1":
            print("\nEnter the default Discord webhook URL:")
            url = input().strip()
            if url:
                _update_env_var('DEFAULT_DISCORD_WEBHOOK_URL', url)
                # Also update DISCORD_WEBHOOK_URL for compatibility
                os.environ['DISCORD_WEBHOOK_URL'] = url
                print("\nDefault webhook URL updated.")
            else:
                print("\nWebhook URL not changed.")
        
        elif choice == "2":
            print("\nEnter the monitored item Discord webhook URL (leave blank to use default):")
            url = input().strip()
            if url:
                _update_env_var('DISCORD_WEBHOOK_URL_MONITORED_ITEM', url)
                print("\nMonitored item webhook URL updated.")
            else:
                print("\nMonitored item webhook URL set to use default.")
        
        elif choice == "3":
            print("\nEnter the symlink creation Discord webhook URL (leave blank to use default):")
            url = input().strip()
            if url:
                _update_env_var('DISCORD_WEBHOOK_URL_SYMLINK_CREATION', url)
                print("\nSymlink creation webhook URL updated.")
            else:
                print("\nSymlink creation webhook URL set to use default.")
        
        elif choice == "4":
            print("\nEnter the symlink deletion Discord webhook URL (leave blank to use default):")
            url = input().strip()
            if url:
                _update_env_var('DISCORD_WEBHOOK_URL_SYMLINK_DELETION', url)
                print("\nSymlink deletion webhook URL updated.")
            else:
                print("\nSymlink deletion webhook URL set to use default.")
        
        elif choice == "5":
            print("\nEnter the symlink repair Discord webhook URL (leave blank to use default):")
            url = input().strip()
            if url:
                _update_env_var('DISCORD_WEBHOOK_URL_SYMLINK_REPAIR', url)
                print("\nSymlink repair webhook URL updated.")
            else:
                print("\nSymlink repair webhook URL set to use default.")
        
        elif choice == "6":
            # Toggle Discord notifications
            new_state = 'false' if notifications_enabled else 'true'
            _update_env_var('ENABLE_DISCORD_NOTIFICATIONS', new_state)
            print(f"\nDiscord notifications {'enabled' if new_state == 'true' else 'disabled'}.")
            
        elif choice == "7":
            # Test webhooks
            print("\nTesting webhook...")
            try:
                from src.utils.webhooks import test_webhook
                test_webhook()
            except Exception as e:
                print(f"Error during webhook test: {str(e)}")
            
            input("\nPress Enter to continue...")
            
        elif choice == "0":
            return
        
        else:
            print("\nInvalid option. Please try again.")
        
        if choice != "7":  # Don't ask to press Enter again after webhook test
            print("\nPress Enter to continue...")
            input()

def handle_settings():
    """Handle settings submenu."""
    while True:
        clear_screen()
        display_ascii_art()
        
        print("=" * 84)
        print("SETTINGS".center(84))
        print("=" * 84)
        
        print("\nOptions:")
        print("  1. Configure File Paths")
        print("  2. Configure API Settings")
        print("  3. Configure Webhook Settings")
        print("  0. Return to Main Menu")
        
        choice = input("\nSelect option: ").strip()
        
        if choice == "1":
            # Handle file path settings
            print("\nFile path settings selected")
            print("\nPress Enter to continue...")
            input()
            
        elif choice == "2":
            # Handle API settings
            print("\nAPI settings selected")
            print("\nPress Enter to continue...")
            input()
            
        elif choice == "3":
            # Handle webhook settings
            handle_webhook_settings()
            
        elif choice == "0":
            # Return to main menu
            return
            
        else:
            print(f"\nInvalid option: {choice}")
            print("\nPress Enter to continue...")
            input()

def has_directory_been_scanned(directory):
    """Check if a directory has been previously scanned."""
    # This is a stub - in a real implementation, you would check scan history
    # to see if this directory has been processed before
    history = load_scan_history()
    if history and 'path' in history:
        # Simple check if this directory is in the scan history
        return directory in history['path']
    return False

def individual_scan_menu():
    """Handle the Individual Scan submenu."""
    perform_individual_scan()

def multi_scan_menu():
    """Handle the Multi Scan submenu."""
    perform_multi_scan()

def monitor_management_menu(monitor_manager):
    """Handle the Monitor Management submenu."""
    handle_monitor_management(monitor_manager)

def settings_menu():
    """Handle the Settings submenu."""
    handle_settings()

def help_menu():
    """Handle the Help submenu."""
    display_help()

# Ensure main function also properly clears screen between menus
def main():
    """Main function to run the Scanly application."""
    # Make sure the screen is clear before we start
    clear_screen()
    
    print("Initializing Scanly...")
    sys.stdout.flush()
    
    # Ensure Discord webhook environment variables are properly set
    # If DEFAULT_DISCORD_WEBHOOK_URL exists but DISCORD_WEBHOOK_URL doesn't, 
    # copy it over for compatibility with old code
    default_webhook = os.environ.get('DEFAULT_DISCORD_WEBHOOK_URL')
    if default_webhook and not os.environ.get('DISCORD_WEBHOOK_URL'):
        os.environ['DISCORD_WEBHOOK_URL'] = default_webhook
        logger.info("Set DISCORD_WEBHOOK_URL from DEFAULT_DISCORD_WEBHOOK_URL for compatibility")
    
    # Get the monitor manager but DO NOT start it
    try:
        monitor_manager = get_monitor_manager()
    except Exception as e:
        logger.error(f"Error initializing monitor manager: {e}")
        monitor_manager = None
    
    clear_screen()  # Make sure screen is clear before starting menu loop
    
    while True:
        display_ascii_art()
        print("=" * 84)
        print("MAIN MENU".center(84))
        print("=" * 84)
        
        print("  1. Individual Scan")
        print("  2. Multi Scan")
        print("  3. Monitor Management")
        print("  4. Settings")
        print("  5. Help")
        print("  0. Quit")
        print()
        
        choice = input("Select option: ")
        
        if choice == "1":
            individual_scan_menu()
            clear_screen()  # Explicitly clear screen when returning to main menu
        
        elif choice == "2":
            multi_scan_menu()
            clear_screen()  # Explicitly clear screen when returning to main menu
        
        elif choice == "3":
            monitor_management_menu(monitor_manager)
            clear_screen()  # Explicitly clear screen when returning to main menu
        
        elif choice == "4":
            settings_menu()
            clear_screen()  # Explicitly clear screen when returning to main menu
        
        elif choice == "5":
            help_menu()
            clear_screen()  # Explicitly clear screen when returning to main menu
        
        elif choice == "0":
            # Clean shutdown - stop monitoring if active
            if monitor_manager and hasattr(monitor_manager, 'stop_all'):
                try:
                    monitor_manager.stop_all()
                    print("\nMonitoring stopped.")
                except Exception as e:
                    logger.error(f"Error stopping monitors: {e}")
            
            print("\nExiting Scanly. Goodbye!")
            break
            
        else:
            print(f"\nInvalid option: {choice}")
            input("\nPress Enter to continue...")
            clear_screen()  # Explicitly clear screen on invalid option

if __name__ == "__main__":
    main()