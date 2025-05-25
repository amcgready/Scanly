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
import datetime  # Add import for datetime to fix the skipped items functionality

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
    print("=" * 84)
    print("HELP INFO".center(84))
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

# Updated help function to use dynamic menu options
def display_help_dynamic(menu_options):
    """Display help information with dynamic menu options."""
    clear_screen()
    display_ascii_art()
    print("=" * 84)
    print("HELP INFO".center(84))
    print("=" * 84)
    print("\nScanly is a media file scanner and organizer.")
    
    print("\nOptions:")
    # Display the same dynamic menu options from the main menu without descriptions
    for i, option in enumerate(menu_options, 1):
        print(f"  {i}. {option}")
    
    print("  0. Quit")
    
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
        print("=" * 84)
        print("SKIPPED ITEMS")
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
            if idx.isdigit() and 1 <= int(idx) <= len(skipped_items_registry):
                item_index = int(idx) - 1
                item = skipped_items_registry[item_index]
                path = item.get('path', '')
                subfolder_name = item.get('subfolder', 'Unknown')
                
                if path and os.path.exists(path):
                    print(f"\nProcessing skipped item: {subfolder_name}")
                    processor = DirectoryProcessor(os.path.dirname(path))
                    # Process the skipped item
                    result = processor._process_subfolder(path, subfolder_name)
                    
                    # If processed successfully, remove from skipped items
                    if result != "skip":
                        skipped_items_registry.pop(item_index)
                        save_skipped_items(skipped_items_registry)
                else:
                    print(f"\nError: Path {path} does not exist or is not accessible.")
                    input("\nPress Enter to continue...")
            else:
                print(f"\nInvalid item number.")
                input("\nPress Enter to continue...")
                
        elif choice == "2":
            # Clear all skipped items
            clear_skipped_items()
            break
            
        elif total_pages > 1 and choice == "3":
            # Next page
            current_page = current_page % total_pages + 1
            
        elif total_pages > 1 and choice == "4":
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
        
        # Initialize detection state variables
        self._detected_content_type = None
        self._detected_tmdb_id = None
        
        # Initialize TMDB API if needed
        self.tmdb_api = None
        tmdb_api_key = os.environ.get('TMDB_API_KEY')
        if tmdb_api_key:
            try:
                self.tmdb_api = TMDB()
            except Exception as e:
                self.logger.error(f"Failed to initialize TMDB API: {e}")
    
    def process(self):
        """Process the directory."""
        try:
            print(f"\nProcessing directory: {self.directory_path}")
            if not os.path.isdir(self.directory_path):
                print(f"\nError: Directory does not exist: {self.directory_path}")
                return False
                
            self._process_media_files()
            return True
        except Exception as e:
            self.logger.error(f"Error processing directory {self.directory_path}: {e}", exc_info=True)
            print(f"Error: {e}")
            return False
    
    def _extract_folder_metadata(self, folder_name):
        """Extract title and year from a folder name."""
        # Extract existing media IDs if present
        tmdb_id = None
        imdb_id = None
        tvdb_id = None
        
        # Check for TMDB ID
        tmdb_match = re.search(r'\[tmdb-(\d+)\]', folder_name)
        if tmdb_match:
            tmdb_id = tmdb_match.group(1)
            
        # Check for IMDB ID
        imdb_match = re.search(r'\[imdb-(tt\d+)\]', folder_name)
        if imdb_match:
            imdb_id = imdb_match.group(1)
            
        # Check for TVDB ID
        tvdb_match = re.search(r'\[tvdb-(\d+)\]', folder_name)
        if tvdb_match:
            tvdb_id = tvdb_match.group(1)
        
        # Extract year using regex
        year_match = re.search(r'(?:^|[^0-9])(\d{4})(?:[^0-9]|$)', folder_name)
        year = year_match.group(1) if year_match else None
        
        # First level of cleaning - remove common patterns
        clean_title = folder_name
        
        # Remove the year
        if year:
            clean_title = re.sub(r'\.?' + year + r'\.?', ' ', clean_title)
        
        # Remove IDs from title (if they exist)
        if tmdb_id:
            clean_title = re.sub(r'\[tmdb-' + tmdb_id + r'\]', '', clean_title)
        if imdb_id:
            clean_title = re.sub(r'\[imdb-' + imdb_id + r'\]', '', clean_title)
        if tvdb_id:
            clean_title = re.sub(r'\[tvdb-' + tvdb_id + r'\]', '', clean_title)
        
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
        return clean_title, year, tmdb_id, imdb_id, tvdb_id
    
    def _detect_if_tv_show(self, folder_name):
        """Detect if a folder contains a TV show based on its name and content."""
        # Check for common TV show indicators in folder name
        folder_lower = folder_name.lower()
        
        # Common TV show patterns
        tv_patterns = [
            r'\bS\d+\b',            # S01, S02, etc.
            r'\bseason\s*\d+\b',    # Season 1, Season 2, etc.
            r'\bseries\b',          # "Series" in the name
            r'(?<!\d)(?:\d{1,2}x\d{2})(?!\d)',  # 1x01, 2x13, etc.
            r'\bepisodes?\b',       # "Episode" or "Episodes"
            r'\bcomplete\b',        # Often indicates complete series
            r'\btv series\b',       # "TV Series"
            r'\bminiseries\b',      # "Miniseries"
            r'\bshow\b',            # "Show" in the name
            r'\bseason\b',          # "Season" in the name
        ]
        
        # Check for TV show patterns in folder name
        for pattern in tv_patterns:
            if re.search(pattern, folder_lower, re.IGNORECASE):
                return True
        
        # Check file patterns inside the folder to detect TV shows
        subfolder_path = os.path.join(self.directory_path, folder_name)
        
        # Count media files and check for episode naming patterns
        episode_file_count = 0
        non_episode_file_count = 0
        
        # Common episode naming patterns
        ep_patterns = [
            r'\bS\d+E\d+\b',         # S01E01
            r'\bs\d+\s*e\d+\b',      # s01 e01
            r'(?<!\d)(?:\d{1,2}x\d{2})(?!\d)',  # 1x01
            r'\bE\d+\b',             # E01
            r'\bEP\d+\b',            # EP01
            r'\bEpisode\s*\d+\b',    # Episode 01
        ]
        
        # Check files for episode patterns
        for root, _, files in os.walk(subfolder_path):
            for file in files:
                if file.endswith(('.mp4', '.mkv', '.avi', '.mov', '.wmv', '.m4v')):
                    if any(re.search(pattern, file, re.IGNORECASE) for pattern in ep_patterns):
                        episode_file_count += 1
                    else:
                        non_episode_file_count += 1
        
        # If we have multiple episode files, it's likely a TV show
        if episode_file_count > 1:
            return True
        
        # If we have many media files in the folder, it might be a TV show
        if episode_file_count + non_episode_file_count > 3:
            # Check if the files have sequential numbering
            file_names = []
            for root, _, files in os.walk(subfolder_path):
                for file in files:
                    if file.endswith(('.mp4', '.mkv', '.avi', '.mov', '.wmv', '.m4v')):
                        file_names.append(file)
            
            # If there are many similarly named files, it might be a TV show
            if len(file_names) > 3:
                # This is a simplistic check - for a more robust solution,
                # we'd analyze naming patterns and numbering
                return True
        
        # For this example, assume it's a movie if we have no evidence it's a TV show
        return False
    
    def _detect_if_anime(self, folder_name):
        """Detect if a folder contains anime based on naming patterns."""
        # Common anime indicators in folder names
        anime_indicators = [
            'anime', 'manga', 'otaku', 'subs', 'dubbed', 
            'subbed', '[BD]', '[DVD]', '[TV]', '[MOVIE]',
            'cour', 'season', '1080p', '720p', '480p', 'HEVC',
            'x265', 'x264', 'WEB-DL', 'Blu-ray', 'BluRay',
            'FLAC', 'AAC', 'AC3', '5.1', '2.0'
        ]
        
        # Common anime titles/franchises
        common_anime_titles = [
            'pokemon', 'naruto', 'bleach', 'one piece', 'dragon ball',
            'sailor moon', 'detective conan', 'case closed', 'doraemon',
            'yugioh', 'yu-gi-oh', 'digimon', 'gundam', 'evangelion', 'ghibli',
            'totoro', 'miyazaki', 'demon slayer', 'attack on titan', 'jojo',
            'sword art online', 'my hero academia', 'fullmetal', 'death note',
            'hunter x hunter', 'fairy tail', 'fate', 'gintama', 'haikyuu',
            'your name', 'weathering with you', 'jujutsu', 'chainsaw'
        ]
        
        # Check for common terms
        lowercase_name = folder_name.lower()
        
        # Direct check for common anime titles
        for title in common_anime_titles:
            if title in lowercase_name:
                self.logger.debug(f"Anime detected by title match: '{title}' in '{folder_name}'")
                return True
        
        # Check for common anime indicators
        for indicator in anime_indicators:
            if indicator.lower() in lowercase_name:
                self.logger.debug(f"Anime detected by indicator: '{indicator}' in '{folder_name}'")
                return True
        
        # Additional pattern-based checks
        anime_patterns = [
            r'\[.*?\]',  # Anything in square brackets like [Anime]
            r'\(.*?\)',  # Anything in parentheses like (Subbed)
            r'S\d+',     # Season indicators like S01
            r'E\d+',     # Episode indicators like E01
        ]
        
        for pattern in anime_patterns:
            if re.search(pattern, folder_name):
                match = re.search(pattern, folder_name).group(0)
                self.logger.debug(f"Anime detected by pattern: '{match}' in '{folder_name}'")
                return True
    
        return False
    
    def _get_tmdb_id(self, title, year=None, is_tv=False):
        """Search for TMDB ID for the given title and year."""
        try:
            self.logger.info(f"Searching TMDB for '{title}'{' (' + year + ')' if year else ''}, type: {'TV' if is_tv else 'Movie'}")
            print(f"\nSearching TMDB for '{title}'{' (' + year + ')' if year else ''}, type: {'TV' if is_tv else 'Movie'}...")
            
            # Direct implementation of TMDB search to avoid dependency issues
            tmdb_api_key = os.environ.get('TMDB_API_KEY')
            if not tmdb_api_key:
                print("Error: TMDB API key not set. Please set it in the settings menu.")
                return None, None
            
            # Setup the API request parameters
            base_url = "https://api.themoviedb.org/3"
            endpoint = "/search/movie" if not is_tv else "/search/tv"
            
            params = {
                'api_key': tmdb_api_key,
                'query': title,
                'include_adult': 'false',
                'language': 'en-US',
            }
            
            if year and not is_tv:
                params['year'] = year
            
            # Make the API request
            try:
                url = f"{base_url}{endpoint}"
                response = requests.get(url, params=params, timeout=10)
                
                if response.status_code == 200:
                    results = response.json().get('results', [])
                    if results:
                        # Get the first result (most relevant)
                        first_result = results[0]
                        tmdb_id = first_result.get('id')
                        title = first_result.get('title' if not is_tv else 'name')
                        
                        # Extract other metadata
                        overview = first_result.get('overview', 'No overview available')
                        release_date = first_result.get('release_date' if not is_tv else 'first_air_date', '')
                        
                        if release_date and len(release_date) >= 4:
                            year = release_date[:4]
                        
                        print(f"Found match: {title} ({year if year else 'Unknown year'})")
                        print(f"TMDB ID: {tmdb_id}")
                        
                        # First 100 characters of overview
                        overview_preview = overview[:100] + "..." if len(overview) > 100 else overview
                        print(f"Overview: {overview_preview}")
                        
                        return tmdb_id, title
                    else:
                        print("No results found on TMDB")
                        return None, None
                else:
                    print(f"Error searching TMDB: Status code {response.status_code}")
                    if response.status_code == 401:
                        print("Invalid API key. Please check your TMDB API key in settings.")
                    return None, None
                    
            except requests.exceptions.RequestException as e:
                print(f"Network error when searching TMDB: {e}")
                return None, None
                
        except Exception as e:
            self.logger.error(f"Error searching for TMDB ID: {e}", exc_info=True)
            print(f"Error searching for TMDB ID: {str(e)}")
            return None, None
    
    def _fetch_media_ids(self, title, year, is_tv):
        """Fetch media IDs from online services."""
        tmdb_id = None
        imdb_id = None
        tvdb_id = None
        
        # Attempt to fetch TMDB ID if API is available
        if self.tmdb_api:
            try:
                query = title
                if year:
                    query += f" {year}"
                
                if is_tv:  # This line was missing the condition
                    results = self.tmdb_api.search_tv(query)
                else:
                    results = self.tmdb_api.search_movie(query)
                
                if results and len(results) > 0:
                    tmdb_id = results[0].get('id')
                    # Could also extract IMDB ID from TMDB API if needed
            except Exception as e:
                self.logger.error(f"Error fetching media IDs for {title}: {e}")
    
        return tmdb_id, imdb_id, tvdb_id
    
    def _create_symlinks(self, subfolder_path, title, year, is_tv, is_anime, tmdb_id=None, imdb_id=None, tvdb_id=None):
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
        
        # Create a folder name with title, year, and IDs based on settings
        title_folder = title
        if year:
            title_folder = f"{title} ({year})"
        
        # Add IDs to folder name if enabled in settings
        if tmdb_id and os.environ.get('TMDB_FOLDER_ID', 'false').lower() == 'true':
            title_folder = f"{title_folder} [tmdb-{tmdb_id}]"
            
        if imdb_id and os.environ.get('IMDB_FOLDER_ID', 'false').lower() == 'true':
            title_folder = f"{title_folder} [imdb-{imdb_id}]"
            
        if tvdb_id and os.environ.get('TVDB_FOLDER_ID', 'false').lower() == 'true':
            title_folder = f"{title_folder} [tvdb-{tvdb_id}]"
        
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
                    rel_path = os.path.relpath(source_file, subfolder_path)
                    target_file = os.path.join(target_folder, rel_path)
                    
                    # Create parent directories if needed
                    target_dir = os.path.dirname(target_file)
                    if not os.path.exists(target_dir):
                        os.makedirs(target_dir)
                    
                    try:
                        # Check if target already exists and remove it if it does
                        if os.path.exists(target_file):
                            if os.path.islink(target_file) or os.path.isfile(target_file):
                                os.remove(target_file)
                        
                        # Create symlink or copy file based on settings
                        if use_symlinks:
                            os.symlink(source_file, target_file)
                        else:
                            import shutil
                            shutil.copy2(source_file, target_file)
                            
                        symlink_count += 1
                    except Exception as e:
                        self.logger.error(f"Error creating link for {file}: {e}")
                        print(f"Error: Could not create link for {file}: {e}")
        
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
            total = len(subdirs)
            
            # Process each subfolder
            for subfolder_name in subdirs:
                subfolder_path = os.path.join(self.directory_path, subfolder_name)
                processed += 1
                
                try:
                    print(f"\n[{processed}/{total}] Processing: {subfolder_name}")
                    
                    # Process the subfolder
                    result = self._process_subfolder(subfolder_path, subfolder_name)
                    
                    # If the user wants to quit processing
                    if result == "quit":
                        print("\nQuitting processing as requested.")
                        break
                    
                    # If the item was skipped, add it to the registry
                    if result == "skip":
                        # Add to skipped items list
                        skipped_item = {
                            'path': subfolder_path,
                            'subfolder': subfolder_name,
                            'timestamp': datetime.datetime.now().isoformat()
                        }
                        skipped_items_registry.append(skipped_item)
                        save_skipped_items(skipped_items_registry)
                        print(f"Added {subfolder_name} to skipped items.")
                
                except Exception as e:
                    self.logger.error(f"Error processing subfolder {subfolder_name}: {e}", exc_info=True)
                    print(f"Error processing {subfolder_name}: {e}")
                    # Continue with the next subfolder instead of breaking
                    continue
            
            # Print the completion message
            print(f"\nFinished processing {processed} of {total} subdirectories.")
        except Exception as e:
            self.logger.error(f"Error processing directory {self.directory_path}: {e}", exc_info=True)
            print(f"Error: {e}")
    
    def _process_subfolder(self, subfolder_path, subfolder_name):
        """Process a single subfolder."""
        try:
            # Extract initial metadata from folder name
            title, year, existing_tmdb_id, existing_imdb_id, existing_tvdb_id = self._extract_folder_metadata(subfolder_name)
            
            # Detect content type (TV show vs. Movie)
            is_tv = self._detect_if_tv_show(subfolder_name)
            
            # Detect if content is anime
            is_anime = self._detect_if_anime(subfolder_name)
            
            # Use existing IDs if available
            tmdb_id = existing_tmdb_id
            imdb_id = existing_imdb_id
            tvdb_id = existing_tvdb_id
            
            # Flag to track if we found a match in scanner lists
            scanner_list_match_found = False
            
            # Check scanner lists FIRST - prioritize scanner lists over everything else
            print(f"\nChecking scanner lists for: '{title}'")
            scanner_match = None
            scanner_year = None

            try:
                # Map our internal content type to scanner list content type
                content_type = 'tv' if is_tv else 'movie'
                
                # Call our new helper method
                scanner_list_match_found, scanner_match = self._check_scanner_lists(title, content_type)
                
                if scanner_list_match_found:
                    if scanner_match:
                        content_type, scanner_is_anime, scanner_tmdb_id, scanner_title, scanner_year = scanner_match
                        
                        match_type = "exact" if scanner_title.lower() == title.lower() else "approximate"
                        self.logger.info(f"Scanner list {match_type} match: '{title}' -> '{scanner_title}', ID: {scanner_tmdb_id}, Year: {scanner_year}")
                        print(f"✓ Found {match_type} match in scanner list: '{scanner_title}' ({scanner_year or 'Unknown'}), TMDB ID: {scanner_tmdb_id or 'None'}")
                        scanner_list_match_found = True
                else:
                    print(f"No matches found in {content_type} scanner lists")
                
            except ImportError as e:
                self.logger.warning(f"Scanner utility module not available: {e}")
                print("Scanner lists check skipped - module not available")
            except Exception as e:
                self.logger.error(f"Error checking scanner lists: {e}", exc_info=True)
                print(f"Error checking scanner lists: {e}")
        
            # In manual mode, show the menu, but don't search TMDB if we have a scanner match
            if not self.auto_mode:
                # Pass the scanner_list_match_found flag to _manual_process_folder
                result = self._manual_process_folder(subfolder_path, subfolder_name, title, year, 
                                                  is_tv, is_anime, tmdb_id, imdb_id, tvdb_id,
                                                  scanner_list_match_found)
                return result
            else:
                # Auto mode - ONLY search TMDB if we have NO tmdb_id AND NO scanner list match
                if not tmdb_id and not scanner_list_match_found:
                    print("No TMDB ID from scanner lists, searching TMDB...")
                    tmdb_id, tmdb_title = self._get_tmdb_id(title, year, is_tv)
                    if tmdb_title and tmdb_title.lower() != title.lower():
                        title = tmdb_title
                elif scanner_list_match_found:
                    print("✓ Using data from scanner lists, skipping TMDB search")
            
            content_type = "TV Show" if is_tv else "Movie"
            anime_label = " (Anime)" if is_anime else ""
            print(f"Detected: {content_type}{anime_label} - {title} {f'({year})' if year else ''}")
            
            # Create symlinks
            result = self._create_symlinks(subfolder_path, title, year, is_tv, is_anime, 
                                         tmdb_id, imdb_id, tvdb_id)
            
            if result:
                print(f"Successfully processed {subfolder_name}")
                return "continue"
            else:
                print(f"Failed to process {subfolder_name}")
                return "skip"
        except Exception as e:
            self.logger.error(f"Error processing subfolder {subfolder_name}: {e}", exc_info=True)
            print(f"Error processing subfolder {subfolder_name}: {e}")
            return "skip"
            
    def _manual_process_folder(self, subfolder_path, subfolder_name, title, year, 
           is_tv, is_anime, tmdb_id, imdb_id, tvdb_id, scanner_list_match_found=False):
        """Manual processing for a folder, allowing user to adjust metadata."""
        try:
            while True:
                clear_screen()
                display_ascii_art()
                print("=" * 84)
                print(f"MANUAL PROCESSING: {subfolder_name}")
                print("=" * 84)
                
                # Display current detection
                content_type = "TV Show" if is_tv else "Movie"
                anime_label = " (Anime)" if is_anime else ""
                print(f"\nCurrent detection:")
                print(f"Content type: {content_type}{anime_label}")
                print(f"Title: {title}")
                print(f"Year: {year if year else 'Unknown'}")
                
                # Only display IDs if they were already available
                if tmdb_id:
                    print(f"TMDB ID: {tmdb_id}")
                if imdb_id:
                    print(f"IMDB ID: {imdb_id}")
                if tvdb_id:
                    print(f"TVDB ID: {tvdb_id}")

                # Show source of information
                if scanner_list_match_found:
                    print("\n✓ Data from scanner lists")
                
                # Count media files in the folder
                media_files = []
                for root, _, files in os.walk(subfolder_path):
                    for file in files:
                        if file.endswith(('.mp4', '.mkv', '.avi', '.mov', '.wmv', '.m4v')):
                            media_files.append(file)

                print(f"\nContains {len(media_files)} media files")
                
                # Make menu highly visible with clear formatting
                print("\n" + "=" * 84)
                print(" " * 30 + "MANUAL PROCESSING OPTIONS" + " " * 30 + " ")
                print("1. Accept")
                print("2. Change Type")
                print("3. New Search")
                print("4. Skip (For later review)")
                print("5. Quit")
                print("=" * 84)
                
                choice = input("\nEnter choice (1-5) [1]: ").strip()  # Added default option indicator [1]
                
                # If user just pressed Enter, default to option 1
                if choice == "":
                    choice = "1"
                    
                print(f"You selected: {choice}")
                
                if choice == "1":
                    # Accept current detection and process
                    print(f"\nProcessing {subfolder_name} with current detection...")
                    
                    # Only search TMDB if we don't have an ID AND didn't find a scanner match
                    if not tmdb_id and not scanner_list_match_found:
                        print("\nSearching for metadata...")
                        tmdb_id, tmdb_title = self._get_tmdb_id(title, year, is_tv)
                        if tmdb_title and tmdb_title.lower() != title.lower():
                            title = tmdb_title
                    elif scanner_list_match_found:
                        print("✓ Using data from scanner lists, skipping TMDB search")
                    
                    result = self._create_symlinks(subfolder_path, title, year, is_tv, is_anime, 
                                                 tmdb_id, imdb_id, tvdb_id)
                    if result:
                        print(f"Successfully processed {subfolder_name}")
                    else:
                        print(f"Failed to process {subfolder_name}")
                
                    input("\nPress Enter to continue to the next folder...")
                    return "continue"
                    
                elif choice == "2":
                    # Change content type (reordering to match the menu)
                    print("\nSelect content type:")
                    print("1. Movie")
                    print("2. TV Show")
                    print("3. Anime Movie")
                    print("4. Anime TV Show")
                    
                    type_choice = input("\nEnter choice (1-4): ").strip()
                    
                    previous_is_tv = is_tv
                    
                    if type_choice == "1":
                        is_tv = False
                        is_anime = False
                    elif type_choice == "2":
                        is_tv = True
                        is_anime = False
                    elif type_choice == "3":
                        is_tv = False
                        is_anime = True
                    elif type_choice == "4":
                        is_tv = True
                        is_anime = True

                    # If content type changed, check appropriate scanner lists
                    if previous_is_tv != is_tv:
                        # Reset IDs
                        tmdb_id = None
                        scanner_list_match_found = False
                        
                        # Check scanner lists with new content type
                        try:
                            from src.utils.scanner_utils import find_all_matches
                            new_content_type = 'tv' if is_tv else 'movie'
                            scanner_matches = find_all_matches(title, new_content_type)
                            
                            if scanner_matches and len(scanner_matches) > 0:
                                print(f"\n✓ Found {len(scanner_matches)} matches in {new_content_type} scanner lists")
                                # Use first match as default
                                scanner_match = scanner_matches[0]
                                content_type, scanner_is_anime, scanner_tmdb_id, scanner_title, scanner_year = scanner_match
                                
                                if scanner_tmdb_id:
                                    tmdb_id = scanner_tmdb_id
                                    print(f"✓ Using TMDB ID {tmdb_id} from scanner list")
                                
                                if scanner_year:
                                    year = scanner_year
                                    print(f"✓ Using year {year} from scanner list")
                                    
                                if scanner_title and scanner_title != title:
                                    title = scanner_title
                                    print(f"✓ Using title from scanner list: '{scanner_title}'")
                                
                                scanner_list_match_found = True
                            else:
                                print(f"\nNo matches found in {new_content_type} scanner lists")
                        except Exception as e:
                            print(f"Error checking scanner lists: {e}")
                
                elif choice == "3":
                    # Change search term
                    print("\nEnter new title (leave blank to keep current):")
                    new_title = input("> ").strip()
                    if new_title:
                        title = new_title
                
                    print("\nEnter year (leave blank to clear):")
                    new_year = input("> ").strip()
                    if new_year:
                        year = new_year
                    else:
                        year = None
                
                    # Reset IDs and scanner match flag when changing title
                    tmdb_id = None
                    scanner_list_match_found = False
            
                elif choice == "4":
                    # Skip for later review
                    print("\nSkipping this folder for later review.")
                    input("\nPress Enter to continue...")
                    return "skip"
                    
                elif choice == "5":
                    # Quit processing
                    if input("\nAre you sure you want to quit processing? (y/n): ").strip().lower() == 'y':
                        return "quit"
                    
                else:
                    print("\nInvalid choice. Please enter a number from 1-5.")
                    input("\nPress Enter to continue...")
            
        except Exception as e:
            print(f"\nError in manual processing: {str(e)}")
            traceback.print_exc()
            input("\nPress Enter to return 'skip' value...")
            return "skip"

# Function to check the monitor status
def _check_monitor_status():
    """Check the status of the monitor service."""
    try:
        from src.core.monitor import check_monitor_status
        check_monitor_status()
    except ImportError:
        print("\nMonitor module not available.")
        
    input("\nPress Enter to continue...")

# New method for DirectoryProcessor class

def _check_scanner_lists(self, title, content_type):
    """Check scanner lists for a title with specific content type.
    
    Args:
        title: Title to search for
        content_type: Content type ('tv' or 'movie')
        
    Returns:
        Tuple: (found_match, scanner_match_tuple)
    """
    try:
        from src.utils.scanner_utils import find_all_matches
        self.logger.debug(f"Checking {content_type} scanner lists for: '{title}'")
        
        # Get all potential matches for this content type
        scanner_matches = find_all_matches(title, content_type)
        
        if scanner_matches and len(scanner_matches) > 0:
            # Return the first match
            return True, scanner_matches[0]
        else:
            return False, None
    except ImportError:
        self.logger.warning(f"Scanner utility module not available")
        return False, None
    except Exception as e:
        self.logger.error(f"Error checking scanner lists: {e}", exc_info=True)
        return False, None

def main():
    """Main entry point for the Scanly application."""
    try:
        clear_screen()
        display_ascii_art()
        
        # Dynamic menu options
        menu_options = [
            "Individual Scan",    # Scan a single directory
            "Multi Scan",         # Scan multiple directories
            "Resume Scan",        # Resume a previously interrupted scan
            "Settings"            # Configure application settings
        ]
        
        # Add monitor option if available
        try:
            from src.core.monitor import check_monitor_status
            menu_options.append("Monitor Status")
        except ImportError:
            pass
        
        # Add skipped items review if we have any
        if skipped_items_registry:
            menu_options.append(f"Review Skipped Items ({len(skipped_items_registry)})")
        
        # Add help option
        menu_options.append("Help")
        
        while True:
            clear_screen()
            display_ascii_art()
            
            print("=" * 84)
            print("MAIN MENU".center(84))
            print("=" * 84)
            
            # Display menu options
            for i, option in enumerate(menu_options, 1):
                print(f"{i}. {option}")
            print("0. Quit")
            
            choice = input("\nSelect an option: ").strip()
            
            if choice == '0':
                print("\nExiting Scanly. Goodbye!")
                break
                
            # Convert to integer if possible
            try:
                choice = int(choice)
                if choice < 0 or choice > len(menu_options):
                    raise ValueError("Invalid option")
            except ValueError:
                print("\nInvalid selection. Please try again.")
                input("\nPress Enter to continue...")
                continue
            
            # Process the selected option
            if choice == 1:  # Individual Scan
                dir_path = input("\nEnter directory path to scan: ").strip()
                if dir_path:
                    dir_path = _clean_directory_path(dir_path)
                    processor = DirectoryProcessor(dir_path)
                    processor.process()
                    input("\nPress Enter to return to main menu...")
            
            elif choice == 2:  # Multi Scan
                while True:
                    dir_path = input("\nEnter directory path to scan (or 'done' to finish): ").strip()
                    if dir_path.lower() == 'done':
                        break
                    if dir_path:
                        dir_path = _clean_directory_path(dir_path)
                        processor = DirectoryProcessor(dir_path)
                        processor.process()
                
                input("\nAll directories processed. Press Enter to return to main menu...")
            
            elif choice == 3:  # Resume Scan
                history = load_scan_history()
                if history and 'path' in history:
                    dir_path = history['path']
                    print(f"\nResuming scan of: {dir_path}")
                    processor = DirectoryProcessor(dir_path, resume=True)
                    processor.process()
                else:
                    print("\nNo previous scan to resume.")
                
                input("\nPress Enter to return to main menu...")
            
            elif choice == 4:  # Settings
                # Implement settings menu
                while True:
                    clear_screen()
                    display_ascii_art()
                    print("=" * 84)
                    print("SETTINGS".center(84))
                    print("=" * 84)
                    
                    print("\n1. Set Destination Directory")
                    print("2. Set TMDB API Key")
                    print("3. Toggle ID Folder Options")
                    print("4. Toggle Symlinks/Copies")
                    print("5. Clear Skipped Items")
                    print("0. Back to Main Menu")
                    
                    settings_choice = input("\nSelect an option: ").strip()
                    
                    if settings_choice == '0':
                        break
                        
                    # Handle settings options
                    if settings_choice == '1':
                        new_path = input("\nEnter destination directory: ").strip()
                        if new_path:
                            _update_env_var('DESTINATION_DIRECTORY', _clean_directory_path(new_path))
                            print(f"\nDestination directory set to: {new_path}")
                            input("\nPress Enter to continue...")
                    
                    elif settings_choice == '2':
                        new_key = input("\nEnter TMDB API Key: ").strip()
                        if new_key:
                            _update_env_var('TMDB_API_KEY', new_key)
                            print("\nTMDB API Key updated.")
                            input("\nPress Enter to continue...")
                    
                    elif settings_choice == '3':
                        # Toggle ID folder options
                        while True:
                            clear_screen()
                            print("\nID Folder Options:")
                            print(f"1. TMDB ID in folder names: {os.environ.get('TMDB_FOLDER_ID', 'false')}")
                            print(f"2. IMDB ID in folder names: {os.environ.get('IMDB_FOLDER_ID', 'false')}")
                            print(f"3. TVDB ID in folder names: {os.environ.get('TVDB_FOLDER_ID', 'false')}")
                            print("0. Back to Settings")
                            
                            id_choice = input("\nSelect an option to toggle: ").strip()
                            
                            if id_choice == '0':
                                break
                            elif id_choice == '1':
                                current = os.environ.get('TMDB_FOLDER_ID', 'false').lower()
                                new_val = 'false' if current == 'true' else 'true'
                                _update_env_var('TMDB_FOLDER_ID', new_val)
                            elif id_choice == '2':
                                current = os.environ.get('IMDB_FOLDER_ID', 'false').lower()
                                new_val = 'false' if current == 'true' else 'true'
                                _update_env_var('IMDB_FOLDER_ID', new_val)
                            elif id_choice == '3':
                                current = os.environ.get('TVDB_FOLDER_ID', 'false').lower()
                                new_val = 'false' if current == 'true' else 'true'
                                _update_env_var('TVDB_FOLDER_ID', new_val)
                    
                    elif settings_choice == '4':
                        # Toggle symlinks/copies
                        current = os.environ.get('USE_SYMLINKS', 'true').lower()
                        new_val = 'false' if current == 'true' else 'true'
                        _update_env_var('USE_SYMLINKS', new_val)
                        print(f"\nSet to use {'symlinks' if new_val == 'true' else 'copies'}.")
                        input("\nPress Enter to continue...")
                    
                    elif settings_choice == '5':
                        # Clear skipped items
                        if input("\nAre you sure you want to clear all skipped items? (y/n): ").lower() == 'y':
                            clear_skipped_items()
            
            # Handle dynamic options at the end of the menu
            elif 4 < choice <= len(menu_options):
                option_text = menu_options[choice-1].lower()
                
                if "monitor status" in option_text:
                    _check_monitor_status()
                    
                elif "review skipped" in option_text:
                    review_skipped_items()
                    
                elif "help" in option_text:
                    display_help_dynamic(menu_options)
    
    except Exception as e:
        logger.error(f"Error in main application: {e}", exc_info=True)
        print(f"\nAn error occurred: {str(e)}")
        print("\nCheck the log file for details.")
        input("\nPress Enter to exit...")

# This ensures the script is executed when run directly
if __name__ == "__main__":
    main()
