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
    def _create_symlinks(self, subfolder_path, title, year, is_tv, is_anime, is_wrestling=False, tmdb_id=None, imdb_id=None, tvdb_id=None):
        """Create symbolic links to the media files."""
        # Get destination directory from environment
        dest_dir = os.environ.get('DESTINATION_DIRECTORY', '')
        if not dest_dir:
            print("\nError: Destination directory not set.")
            print("Please set the DESTINATION_DIRECTORY in the settings menu.")
            return False
        
        # Determine the target subdirectory based on content type
        if is_wrestling:
            target_subdir = os.path.join(dest_dir, "Wrestling")
        elif is_tv:
            if is_anime:
                target_subdir = os.path.join(dest_dir, "Anime Series")
            else:
                target_subdir = os.path.join(dest_dir, "TV Series")
        else:
            if is_anime:
                target_subdir = os.path.join(dest_dir, "Anime Movies")
            else:
                target_subdir = os.path.join(dest_dir, "Movies")
        
        # Create the target subdirectory if it doesn't exist
        if not os.path.exists(target_subdir):
            os.makedirs(target_subdir)
            
        # Format the media folder name with title, year, and IDs
        media_folder_name = title
        if year:
            media_folder_name += f" ({year})"
        
        # Debug log to check environment variable
        self.logger.debug(f"TMDB_FOLDER_ID setting: {os.environ.get('TMDB_FOLDER_ID', 'not set')}")
        
        # Add IDs to folder name if configured to do so
        if tmdb_id:
            self.logger.debug(f"Found TMDB ID: {tmdb_id}")
            if os.environ.get('TMDB_FOLDER_ID', 'false').lower() == 'true':
                self.logger.info(f"Adding TMDB ID {tmdb_id} to folder name")
                media_folder_name += f" [tmdb-{tmdb_id}]"
            else:
                self.logger.debug("TMDB_FOLDER_ID is not set to 'true', not adding ID to folder name")
        else:
            self.logger.debug("No TMDB ID available for this folder")
        
        if imdb_id and os.environ.get('IMDB_FOLDER_ID', 'false').lower() == 'true':
            media_folder_name += f" [imdb-{imdb_id}]"
        if tvdb_id and os.environ.get('TVDB_FOLDER_ID', 'false').lower() == 'true':
            media_folder_name += f" [tvdb-{tvdb_id}]"
        
        # Create the full path for the media folder
        media_folder_path = os.path.join(target_subdir, media_folder_name)
        
        # Create the media folder if it doesn't exist
        if not os.path.exists(media_folder_path):
            os.makedirs(media_folder_path)
            self.logger.info(f"Created media folder: {media_folder_path}")
            print(f"\nCreated folder: {media_folder_path}")
        else:
            self.logger.info(f"Using existing media folder: {media_folder_path}")
            print(f"\nUsing existing folder: {media_folder_path}")
        
        # Check if we should use symlinks or copies
        use_symlinks = os.environ.get('USE_SYMLINKS', 'true').lower() == 'true'
        
        # Track results
        total_files = 0
        created_links = 0
        skipped_links = 0
        
        # Process all files in the source directory
        for root, _, files in os.walk(subfolder_path):
            for file in files:
                # Skip hidden files and small files that are likely not media
                if file.startswith('.'):
                    continue
                    
                # Calculate relative path from the source subfolder root
                rel_path = os.path.relpath(root, subfolder_path)
                if rel_path == '.':
                    rel_path = ''
                
                # Create corresponding subdirectory in the target
                target_file_dir = os.path.join(media_folder_path, rel_path)
                if rel_path and not os.path.exists(target_file_dir):
                    os.makedirs(target_file_dir)
                
                # Get file extension
                file_ext = os.path.splitext(file)[1].lower()
                
                # Generate proper file name based on media title and year
                # For main media files, use the title and year
                if file_ext in ['.mp4', '.mkv', '.avi', '.mov', '.wmv', '.m4v']:
                    proper_file_name = f"{title}"
                    if year:
                        proper_file_name += f" ({year})"
                    proper_file_name += file_ext
                else:
                    # For subtitle files and other supporting files, keep original name
                    proper_file_name = file
                
                # Full paths for source and target files
                source_file = os.path.join(root, file)
                target_file = os.path.join(target_file_dir, proper_file_name)
                
                # Skip non-media files under a certain size (e.g., NFOs, thumbnails)
                if os.path.getsize(source_file) < 1024 * 1024:  # Skip files smaller than 1MB
                    # Only keep media files regardless of size
                    if file_ext not in ['.mp4', '.mkv', '.avi', '.mov', '.wmv', '.m4v', '.srt', '.sub', '.idx', '.ass']:
                        continue
            
                # Count total files being processed
                total_files += 1
                
                try:
                    # Check if target already exists
                    if os.path.exists(target_file):
                        # If it's already a link to our source, skip
                        if os.path.islink(target_file) and os.path.realpath(target_file) == os.path.realpath(source_file):
                            self.logger.debug(f"Skipping existing link: {target_file}")
                            print(f"Skipping (already linked): {proper_file_name}")
                            skipped_links += 1
                            continue
                        else:
                            self.logger.warning(f"Target file exists but is not linked to our source: {target_file}")
                            print(f"Warning: {proper_file_name} exists but points elsewhere")
                    
                    # Create symlink or copy
                    if use_symlinks:
                        os.symlink(source_file, target_file)
                        self.logger.info(f"Created symlink: {target_file} -> {source_file}")
                        print(f"Created link: {proper_file_name}")
                        created_links += 1
                    else:
                        shutil.copy2(source_file, target_file)
                        self.logger.info(f"Copied file: {source_file} to {target_file}")
                        print(f"Copied file: {proper_file_name}")
                        created_links += 1
                
                except Exception as e:
                    self.logger.error(f"Error creating link for {file}: {e}")
                    print(f"Error processing {file}: {e}")
            
        # Print summary
        if created_links > 0:
            print(f"\n✓ Created {created_links} {'symlinks' if use_symlinks else 'copies'} in {media_folder_path}")
        if skipped_links > 0:
            print(f"ℹ️ Skipped {skipped_links} files (already linked)")
        
        if created_links == 0 and skipped_links == 0:
            print("\n⚠️ No files were processed. Check that the source folder contains media files.")
            return False
        
        return True

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
        
        # Extract year using regex - more specific to avoid matching resolutions
        # Look for 4-digit years between 1900 and current year + 5
        current_year = datetime.datetime.now().year
        year_pattern = r'(?:^|[^0-9])(?:19\d{2}|20[0-2]\d)(?:[^0-9]|$)'
        year_match = re.search(year_pattern, folder_name)
        year = None
        if year_match:
            # Extract just the 4 digits
            year_str = year_match.group(0)
            year_digits = re.search(r'(19\d{2}|20[0-2]\d)', year_str)
            if year_digits:
                year_candidate = year_digits.group(1)
                # Only accept years between 1900 and current year + 5
                if 1900 <= int(year_candidate) <= current_year + 5:
                    year = year_candidate
        
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
        
        # Special handling for titles with season indicators
        # Remove season indicators like S01, Season 1, etc.
        clean_title = re.sub(r'\bS\d+\b|\bSeason\s*\d+\b', '', clean_title, flags=re.IGNORECASE)
        
        # Remove common quality/format indicators
        patterns_to_remove = [
            # Resolution patterns - make this more comprehensive
            r'(?i)\b(720p|1080p|1440p|2160p|4320p|480p|576p|8K|4K|UHD|HD|FHD|QHD)\b',
            r'(?i)\b(720|1080|1440|2160|4320|480|576)\b',  # Numbers only, without p
            
            # Format patterns
            r'(?i)\b(BluRay|Blu Ray|Blu-ray|BD|REMUX|BDRemux|BDRip|DVDRip|HDTV|WebRip|WEB-DL|WEBRip|Web|HDRip|DVD|DVDR)\b',
            
            # Codec patterns - expanded
            r'(?i)\b(xvid|divx|x264|x265|hevc|h264|h265|HEVC|avc|vp9|av1)\b',
            r'(?i)\bH\s*26[45]\b',  # H 264 or H 265 with space
            r'(?i)\b0\s*H\s*26[45]\b',  # 0 H 264 pattern (specifically for Pokemon Origins)
            
            # Audio patterns
            r'(?i)\b(DTS[-\.]?(HD|ES|X)?|DD5\.1|AAC|AC3|TrueHD|Atmos|MA|5\.1|7\.1|2\.0|opus)\b',
            
            # Release group patterns (in brackets or after hyphen)
            r'(?i)(\[.*?\]|\-[a-zA-Z0-9_]+$)',
    
            # Common release group names
            r'(?i)\b(AMZN|EfficientNeatChachalacaOfOpportunityTGx|SPRiNTER|KRaLiMaRKo|DVT|TheEqualizer|YIFY|NTG|YTS|SPARKS|RARBG|EVO|GHOST|HDCAM|CAM|TS|SCREAM|ExKinoRay)\b',
            
            # Other common patterns
            r'(?i)\b(HDR|VC|10bit|8bit|Hi10P|IMAX|PROPER|REPACK|HYBRID|DV|p|AAC\d|Pikanet\d+)\b'
        ]
        
        # Apply all patterns
        for pattern in patterns_to_remove:
            clean_title = re.sub(pattern, ' ', clean_title)
        
        # Replace dots, underscores, and dashes with spaces
        clean_title = re.sub(r'\.|\-|_', ' ', clean_title)
        
        # Remove the FGT pattern explicitly (as seen in the example)
        clean_title = re.sub(r'\bFGT\b', '', clean_title, flags=re.IGNORECASE)
        
        # Remove empty parentheses
        clean_title = re.sub(r'\(\s*\)', '', clean_title)
        
        # Replace multiple spaces with a single space and trim
        clean_title = re.sub(r'\s+', ' ', clean_title).strip()
        
        # If the title is empty after cleaning, use the original folder name
        if not clean_title:
            clean_title = folder_name
        
        # Log the results
        self.logger.debug(f"Original: '{folder_name}', Cleaned: '{clean_title}', Year: {year}")
        return clean_title, year, tmdb_id, imdb_id, tvdb_id

    def _detect_if_wrestling(self, folder_name):
        """Detect if a folder contains wrestling content based on naming patterns."""
        # Common wrestling indicators
        wrestling_indicators = [
            'wwe', 'aew', 'nxt', 'raw', 'smackdown', 'wrestlemania', 
            'summerslam', 'royal rumble', 'survivor series', 'tna', 'impact',
            'njpw', 'roh', 'ring of honor', 'dynamite', 'rampage', 'collision',
            'wrestle', 'wrestling', 'ppv', 'pay-per-view'
        ]
        
        # Check for common terms
        lowercase_name = folder_name.lower()
        
        # Check for common wrestling indicators
        for indicator in wrestling_indicators:
            if indicator in lowercase_name:
                self.logger.debug(f"Wrestling detected by indicator: '{indicator}' in '{folder_name}'")
                return True
        
        # Additional pattern checks for wrestling
        wrestling_patterns = [
            r'\d{2}\.\d{2}\.\d{2,4}',  # Date formats often used in wrestling releases
            r'\d{2}-\d{2}-\d{2,4}',    # Another date format
            r'S\d{2}E\d{2}',           # Season/Episode format for weekly shows
            r'Week\s*\d+',              # Weekly show indicators
            r'Day\s*\d+',               # Event days
        ]
        
        for pattern in wrestling_patterns:
            if re.search(pattern, folder_name):
                match = re.search(pattern, folder_name).group(0)
                self.logger.debug(f"Wrestling detected by pattern: '{match}' in '{folder_name}'")
                return True

        return False

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
            'cour'
        ]
        
        # Common anime studios and terminology
        anime_studios = [
            'ghibli', 'toei', 'madhouse', 'kyoani', 'shaft',
            'gainax', 'mappa', 'wit', 'bones', 'ufotable',
            'crunchyroll', 'funimation'
        ]
        
        # Common anime titles/franchises - should be specific enough to avoid false positives
        common_anime_titles = [
            'pokemon', 'naruto', 'bleach', 'one piece', 'dragon ball',
            'sailor moon', 'detective conan', 'case closed', 'doraemon',
            'yugioh', 'yu-gi-oh', 'digimon', 'gundam', 'evangelion',
            'totoro', 'miyazaki', 'demon slayer', 'attack on titan', 'jojo',
            'sword art online', 'my hero academia', 'fullmetal', 'death note',
            'hunter x hunter', 'fairy tail', 'fate', 'gintama', 'haikyuu',
            'your name', 'weathering with you', 'jujutsu', 'chainsaw'
        ]
        
        # Check for common terms
        lowercase_name = folder_name.lower()
        
        # Direct check for common anime titles - these are reliable indicators
        for title in common_anime_titles:
            if title in lowercase_name:
                self.logger.debug(f"Anime detected by title match: '{title}' in '{folder_name}'")
                return True
        
        # Check for common anime studios - these are reliable indicators
        for studio in anime_studios:
            if studio in lowercase_name:
                self.logger.debug(f"Anime detected by studio: '{studio}' in '{folder_name}'")
                return True
        
        # Check for specific anime format indicators - these are likely but not guaranteed
        anime_format_indicators = [
            '[dual audio]', '[bd]', '[bluray]', '[jp]', '[jpn]', 
            '[eng]', '[english]', '[1080]', '[720]', '[subs]',
            '[multi subs]', '[raw]', 'uncensored', 'season'
        ]
        
        # Check for Japanese text which is a strong indicator of anime
        if re.search(r'[\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\uff66-\uff9f]', folder_name):
            self.logger.debug(f"Anime detected by Japanese characters in '{folder_name}'")
            return True
        
        # Check if the title contains common anime title patterns
        anime_title_patterns = [
            r'S\d+\s*-\s*S\d+',  # Range of seasons, like S1-S3
            r'\[\s*\d{1,2}\s*of\s*\d{1,2}\s*\]',  # [1 of 12], etc.
            r'\s+OVA\s*\d*\s*$',  # OVA, OVA2, etc at the end
            r'\s+OAV\s*\d*\s*$',  # OAV, OAV2, etc at the end
            r'cour\s*\d+',  # cour 1, cour 2, etc.
            r'\bova\b|\boav\b',  # OVA/OAV terms
        ]
        
        for pattern in anime_title_patterns:
            if re.search(pattern, lowercase_name, re.IGNORECASE):
                self.logger.debug(f"Anime detected by title pattern: '{pattern}' in '{folder_name}'")
                return True
        
        # For generic terms like 'season', 'bluray', etc., require at least 2 matches
        # to avoid false positives like with "12 Angry Men"
        matches = 0
        for indicator in anime_indicators + anime_format_indicators:
            if indicator.lower() in lowercase_name:
                matches += 1
                if matches >= 2:  # Require at least 2 matches for generic terms
                    self.logger.debug(f"Anime detected by multiple indicators ({matches}) in '{folder_name}'")
                    return True
        
        # Additional check: if 'jp', 'jpn', or 'japan' is in the folder name AND 
        # it contains typical media format indicators, it's likely anime
        if any(jp_term in lowercase_name for jp_term in ['jp', 'jpn', 'japan']):
            if any(fmt in lowercase_name for fmt in ['1080', '720', 'x264', 'x265', 'h264', 'h265']):
                self.logger.debug(f"Anime detected by Japanese language + format indicators in '{folder_name}'")
                return True
        
        # Not enough evidence to classify as anime
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
            
            # Also detect if content is wrestling - this was missing!
            is_wrestling = self._detect_if_wrestling(subfolder_name)
            
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
                content_type_for_scanner = 'tv' if is_tv else 'movie'
                
                # Call our new helper method
                scanner_list_match_found, scanner_match = self._check_scanner_lists(title, content_type_for_scanner)
                
                if scanner_list_match_found:
                    if scanner_match:
                        content_type, scanner_is_anime, scanner_tmdb_id, scanner_title, scanner_year = scanner_match
                        
                        match_type = "exact" if scanner_title.lower() == title.lower() else "approximate"
                        self.logger.info(f"Scanner list {match_type} match: '{title}' -> '{scanner_title}', ID: {scanner_tmdb_id}, Year: {scanner_year}")
                        print(f"✓ Found {match_type} match in scanner list: '{scanner_title}' ({scanner_year or 'Unknown'}), TMDB ID: {scanner_tmdb_id or 'None'}")
                        scanner_list_match_found = True
                else:
                    print(f"No matches found in {content_type_for_scanner} scanner lists")
                
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
            
            # Display content type correctly
            content_type = "TV Show" if is_tv else "Movie"
            if is_anime:
                content_type = f"Anime {content_type}"
            elif is_wrestling:  # Add this check to show wrestling content type
                content_type = "Wrestling"
            print(f"Detected: {content_type} - {title} {f'({year})' if year else ''}")
            
            # Debug statement to show detection values
            print(f"DEBUG - is_tv: {is_tv}, is_anime: {is_anime}, is_wrestling: {is_wrestling}")
            
            # Create symlinks - pass is_wrestling parameter
            result = self._create_symlinks(subfolder_path, title, year, is_tv, is_anime, 
                                         is_wrestling, tmdb_id, imdb_id, tvdb_id)
            
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
            # Add is_wrestling detection
            is_wrestling = self._detect_if_wrestling(subfolder_name)
            
            while True:
                clear_screen()
                display_ascii_art()
                print("=" * 84)
                print(f"MANUAL PROCESSING: {subfolder_name}")
                print("=" * 84)
                
                # Display current detection
                content_type = "TV Show" if is_tv else "Movie"
                if is_anime:
                    content_type = f"Anime {content_type}"
                elif is_wrestling:  # Add wrestling type display
                    content_type = "Wrestling"
                print(f"\nCurrent detection:")
                print(f"Content type: {content_type}")
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
                
                # Show simplified menu options
                print("\nOptions:")
                print("1. Accept and process")
                print("2. Change content type")
                print("3. New search (Title/Year)")
                print("4. Skip this item")
                print("0. Quit processing")
                print("\nPress Enter to accept")
                
                choice = input("\nEnter choice: ").strip()
                
                # Treat empty input as option 1 (Accept)
                if choice == "":
                    choice = "1"
                    
                if choice == "0":
                    return "quit"
                    
                elif choice == "1":
                    # Accept current detection and process
                    print(f"\nProcessing {subfolder_name} with current detection...")
                    
                    # Debug info after selection
                    print(f"DEBUG - Using: is_tv={is_tv}, is_anime={is_anime}, is_wrestling={is_wrestling}")
                    
                    # Create symlinks with is_wrestling parameter
                    result = self._create_symlinks(subfolder_path, title, year, is_tv, is_anime, 
                                                 is_wrestling, tmdb_id, imdb_id, tvdb_id)
                    
                    if result:
                        print(f"Successfully processed {subfolder_name}")
                        return "continue"
                    else:
                        print(f"Failed to process {subfolder_name}")
                        return "skip"
                
                elif choice == "2":
                    # Change content type (reordering to match the menu)
                    print("\nSelect content type:")
                    print("1. Movie")
                    print("2. TV Show")
                    print("3. Anime Movie")
                    print("4. Anime TV Show")
                    print("5. Wrestling")
                    
                    type_choice = input("\nEnter choice (1-5): ").strip()
                    
                    # Reset all type flags first
                    is_tv = False
                    is_anime = False
                    is_wrestling = False
                    
                    # Set the appropriate flags based on user choice
                    if type_choice == "1":  # Movie
                        is_tv = False
                        is_anime = False
                        is_wrestling = False
                    elif type_choice == "2":  # TV Show
                        is_tv = True
                        is_anime = False
                        is_wrestling = False
                    elif type_choice == "3":  # Anime Movie
                        is_tv = False
                        is_anime = True
                        is_wrestling = False
                    elif type_choice == "4":  # Anime TV Show
                        is_tv = True
                        is_anime = True
                        is_wrestling = False
                    elif type_choice == "5":  # Wrestling
                        is_wrestling = True
                        is_tv = False
                        is_anime = False
                    
                    # Show a confirmation message
                    content_type = "TV Show" if is_tv else "Movie"
                    if is_anime:
                        content_type = f"Anime {content_type}"
                    elif is_wrestling:
                        content_type = "Wrestling"
                        
                    print(f"\nContent type changed to: {content_type}")
                    input("\nPress Enter to continue...")
                    
                elif choice == "3":
                    # New search (Title/Year)
                    new_title = input(f"\nCurrent title: {title}\nEnter new title (or press Enter to keep current): ").strip()
                    new_year = input(f"\nCurrent year: {year or 'Unknown'}\nEnter new year (or press Enter to keep current): ").strip()
                    
                    if new_title:
                        title = new_title
                    
                    if new_year and new_year.isdigit() and len(new_year) == 4:
                        year = new_year
                    elif new_year == "":
                        # Keep current year
                        pass
                    elif new_year.lower() == "none":
                        year = None
                    else:
                        print("Invalid year format. Year should be a 4-digit number.")
                        input("\nPress Enter to continue...")
                        continue
                    
                    # If title or year changed, try to get new TMDB ID
                    if new_title or (new_year and new_year != year):
                        print(f"\nSearching for new metadata with title: {title} {f'({year})' if year else ''}")
                        tmdb_id, new_title_from_search = self._get_tmdb_id(title, year, is_tv)
                        
                        if tmdb_id:
                            if new_title_from_search and new_title_from_search != title:
                                title = new_title_from_search
                            print(f"\nFound new TMDB ID: {tmdb_id}")
                        else:
                            print("\nNo TMDB match found. Using manual entry.")
    
                    print(f"\nTitle set to: {title}")
                    print(f"Year set to: {year or 'None'}")
                    input("\nPress Enter to continue...")
                
                elif choice == "4":
                    # Skip this item
                    print(f"\nSkipping {subfolder_name}")
                    return "skip"
                
                else:
                    print("\nInvalid choice. Please try again.")
                    input("\nPress Enter to continue...")
        except Exception as e:
            self.logger.error(f"Error in manual processing: {e}", exc_info=True)
            print(f"Error: {e}")
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
