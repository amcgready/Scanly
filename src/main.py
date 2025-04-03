#!/usr/bin/env python3
"""
Main entry point for Scanly.

This module contains the main functionality for running Scanly,
including the application initialization and entry point.
"""

# Must be at the top - redirect stdout/stderr before any imports
if __name__ == "__main__":
    import io
    import sys
    
    class OutputFilter(io.TextIOBase):
        def __init__(self, target):
            self.target = target
            
        def write(self, s):
            # Filter or modify output here if needed
            return self.target.write(s)
            
        def flush(self):
            return self.target.flush()
    
    # Apply the filter
    sys.stdout = OutputFilter(sys.stdout)
    sys.stderr = OutputFilter(sys.stderr)

import os
import sys
import re
import json
import time
import logging
import requests
import io
from pathlib import Path
from datetime import datetime

try:
    from src.mdblist_handler import get_mdblist_handler
    mdblist_handler = get_mdblist_handler()
    mdblist_enabled = True
except ImportError:
    mdblist_enabled = False
    # Log that the feature is unavailable
    logging.getLogger(__name__).warning("MDBlist handler not available, related features will be disabled")

def load_env_file():
    """Load environment variables from .env file if it exists."""
    env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')
    if os.path.exists(env_path):
        from dotenv import load_dotenv
        load_dotenv(env_path)

# Call this function early in the script
load_env_file()

def get_logger(name):
    """
    Get a logger with the specified name.
    
    Args:
        name: The name of the logger
        
    Returns:
        A configured logger instance
    """
    logger = logging.getLogger(name)
    return logger

# Configure logging to discard messages before setup_logging is called
class NullHandler(logging.Handler):
    def emit(self, record):
        pass

# Apply NullHandler to root logger to suppress initial messages
logging.getLogger().addHandler(NullHandler())
logging.getLogger().setLevel(logging.WARNING)

# Add the parent directory to sys.path to ensure imports work correctly
parent_dir = str(Path(__file__).parent.parent)
if (parent_dir not in sys.path):
    sys.path.append(parent_dir)

# Define paths before they're used
HISTORY_FILE = os.path.join(os.path.dirname(__file__), 'scan_history.json')
ART_FILE = os.path.join(os.path.dirname(__file__), '../art.txt')
# Get destination directory from environment variable or use default
DESTINATION_DIRECTORY = os.environ.get('DESTINATION_DIRECTORY')
if not DESTINATION_DIRECTORY:
    print("DESTINATION_DIRECTORY environment variable not set!")
    print("Please set it before running the application:")
    print("export DESTINATION_DIRECTORY='/your/desired/media/path'")
    print("Or ensure it's defined in your .env file")
    sys.exit(1)

def setup_logging(log_level=logging.INFO, console_level=logging.WARNING):
    """
    Set up logging configuration with different levels for file and console.
    
    Args:
        log_level: The logging level to use for the file
        console_level: The logging level to use for the console (higher = less verbose)
    """
    # Create logs directory if it doesn't exist
    log_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'logs')
    os.makedirs(log_dir, exist_ok=True)
    
    # Define the main log file path
    log_file = os.path.join(log_dir, 'scanly.log')
    
    # Remove all existing handlers from the root logger
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Configure the root logger level
    root_logger.setLevel(log_level)
    
    # Create handlers with different levels
    file_handler = logging.FileHandler(log_file, mode='w')
    file_handler.setLevel(log_level)  # More verbose for file
    
    console_handler = logging.StreamHandler()
    console_handler.setLevel(console_level)  # Less verbose for console
    
    # Create a formatter and add it to the handlers
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                                 datefmt='%Y-%m-%d %H:%M:%S')
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    
    # Add the handlers to the root logger
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)
    
    # Log startup information
    logging.info("Scanly started")
    logging.info("Logging initialized (file level: %s, console level: %s)", 
                logging.getLevelName(log_level),
                logging.getLevelName(console_level))
    logging.info("Log file: %s", log_file)

def display_ascii_art():
    """Display ASCII art from art.txt with encoding error handling."""
    # List of encodings to try, in order of preference
    encodings = ['utf-8', 'latin-1', 'cp1252', 'ascii']
    art_displayed = False
    logger = logging.getLogger(__name__)
    
    try:
        # Clear any existing output first
        print("\033[H\033[J", end="")  # ANSI escape sequence to clear screen
        
        # Add exactly one line of space above everything
        print()
        
        # Try to read the art file with different encodings
        if os.path.exists(ART_FILE):
            for encoding in encodings:
                try:
                    with open(ART_FILE, 'r', encoding=encoding) as file:
                        art = file.read()
                        print(art, end="")  # No newline after art
                        art_displayed = True
                        logger.debug(f"Successfully displayed ASCII art using {encoding} encoding")
                        break  # Successfully read the file, exit the loop
                except UnicodeDecodeError:
                    continue  # Try the next encoding
                except Exception as e:
                    logger.warning(f"Error reading art file with {encoding} encoding: {e}")
                    continue
        
        # If we couldn't display the art with any encoding, use the fallback art
        if not art_displayed:
            logger.warning("Could not display ASCII art from file, using fallback")
            # Simple ASCII-only fallback that should work on any terminal
            print("""
   _____                   _       
  / ____|                 | |      
 | (___   ___ __ _ _ __   | |_   _ 
  \___ \ / __/ _` | '_ \  | | | | |
  ____) | (_| (_| | | | |_| | |_| |
 |_____/ \___\__,_|_| |_(_)_|\__, |
                              __/ |
                             |___/ 
            """)
    except Exception as e:
        logger.error(f"Unexpected error in display_ascii_art: {e}")
        # Emergency fallback - just add blank lines to keep layout consistent
        print("\n\n")

def clear_screen():
    """Clear the terminal screen."""
    # Check if OS is Windows
    if os.name == 'nt':
        os.system('cls')
    # For Mac and Linux
    else:
        os.system('clear')

def history_exists():
    """Check if a scan history file exists and has content."""
    return os.path.exists(HISTORY_FILE) and os.path.getsize(HISTORY_FILE) > 0

def save_scan_history(path, processed_files=None, total_files=None, media_files=None):
    """Save or update the scan history."""
    history = {
        'path': path,
        'processed_files': processed_files or 0,
        'total_files': total_files or 0,
        'completed': (processed_files == total_files) if processed_files and total_files else False,
        'media_files': media_files or [],
        'timestamp': time.time()
    }
    
    with open(HISTORY_FILE, 'w') as f:
        json.dump(history, f)

def load_scan_history():
    """Load the scan history if it exists."""
    if not history_exists():
        return None
    
    try:
        with open(HISTORY_FILE, 'r') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return None

def clear_scan_history():
    """Delete the scan history file."""
    if os.path.exists(HISTORY_FILE):
        os.remove(HISTORY_FILE)
        return True
    return False

# Add these functions before they're used
def load_skipped_items():
    """Load the previously skipped items from file."""
    skipped_file = os.path.join(os.path.dirname(__file__), 'skipped_items.json')
    try:
        if os.path.exists(skipped_file):
            with open(skipped_file, 'r') as f:
                return json.load(f)
        return []
    except (json.JSONDecodeError, IOError) as e:
        # Log error but return empty list
        logging.error(f"Error loading skipped items: {e}")
        return []

def save_skipped_items(items):
    """Save skipped items to file."""
    skipped_file = os.path.join(os.path.dirname(__file__), 'skipped_items.json')
    try:
        with open(skipped_file, 'w') as f:
            json.dump(items, f)
        return True
    except (IOError, TypeError) as e:
        logging.error(f"Error saving skipped items: {e}")
        return False

# Helper function to clean directory paths from drag & drop operations
def _clean_directory_path(path):
    """Clean directory paths from drag & drop operations."""
    if not path:
        return path
    
    # Don't print debug info - quietly clean the path
    
    try:
        # Strip whitespace
        path = path.strip()
        
        # Check for the specific pattern of double single-quotes
        if path.startswith("''") and path.endswith("''"):
            path = path[2:-2]
        # Regular quote handling
        elif path.startswith('"') and path.endswith('"'):
            path = path[1:-1]
        elif path.startswith("'") and path.endswith("'"):
            path = path[1:-1]
        
        # Replace escaped spaces if any
        path = path.replace("\\ ", " ")
        
        # Expand user directory if path starts with ~
        if path.startswith("~"):
            path = os.path.expanduser(path)
        
        # Convert to absolute path if needed
        if not os.path.isabs(path):
            path = os.path.abspath(path)
    except Exception as e:
        # Don't print the error, just log it
        logger = get_logger(__name__)
        logger.error(f"Error cleaning path: {e}")
        # Return the original path if cleaning fails
        return path
    
    return path

def display_help():
    """Display detailed help information about Scanly."""
    clear_screen()
    display_ascii_art()
    print("=" * 60)
    print("SCANLY HELP")
    print("=" * 60)
    
    print("\nBASIC USAGE:")
    print("  1. Individual Scan - Scan a single directory or file")
    print("  2. Multi Scan - Process multiple directories in one session")
    print("  3. Resume Scan - Continue a previously interrupted scan")
    print("  4. Review Skipped Items - Process items that were skipped during scanning")
    
    print("\nDIRECTORY STRUCTURE:")
    print("  Scanly can process various directory structures including:")
    print("  • Folders containing TV shows with common season/episode patterns")
    print("  • Movie folders with single or multiple video files")
    print("  • Mixed content folders")
    
    print("\nFILE PATTERN RECOGNITION:")
    print("  Scanly recognizes these common patterns for TV shows:")
    print("  • S01E01, s01e01 - Standard season/episode format")
    print("  • S01EP01 - Supernatural-style format")
    print("  • 1x01 - Alternative season/episode format")
    print("  • Season 1 Episode 1 - Text format")
    print("  • /Season 01/01 - Directory structure format")
    print("  • 101, 102 - Sequential numbering (interpreted as S01E01, S01E02)")
    
    print("\nMANUAL vs AUTOMATIC PROCESSING:")
    print("  When processing files, you can choose:")
    print("  • Automatic processing - Let Scanly identify all episodes")
    print("  • Manual processing - Confirm or edit each episode's information")
    print("  • If automatic processing fails to identify some files, you'll be")
    print("    given the option to manually process just those failed files.")
    
    print("\nPRESSING ENTER:")
    print("  Throughout the application, pressing Enter will select the default")
    print("  option (usually option 1) which is the most common choice.")
    print("  This makes navigation faster when processing many files.")
    
    print("\nSKIPPING ITEMS:")
    print("  Items you skip during scanning are saved and can be processed later")
    print("  using the 'Review Skipped Items' option from the main menu.")
    
    print("\nFILE ORGANIZATION:")
    print("  Scanly creates an organized library structure using symlinks that")
    print("  point to your original files. This preserves your original files while")
    print("  providing a clean, organized view of your media collection.")
    print("  The organized structure follows the Plex/Kodi/Jellyfin conventions:")
    print("  • TV Shows → Show Name (Year) → Season XX → Show S01E01 - Episode Title.ext")
    print("  • Movies → Movie Title (Year) → Movie Title.ext")
    
    print("\nNOTE: The year is included in folder names but is not used in")
    print("      search queries to improve matching with TMDB database.")
    
    input("\nPress Enter to return to the main menu...")
    clear_screen()

# Add this class before the DirectoryProcessor class
class TMDB:
    """Simple TMDB API client for movie and TV show metadata."""
    
    def __init__(self, api_key=None):
        """Initialize the TMDB client with an API key."""
        # Use a default API key or environment variable if not provided
        self.api_key = api_key or os.environ.get('TMDB_API_KEY', '3b5df02338c403dad189e661d57e351f')
        self.base_url = "https://api.themoviedb.org/3"
        self.logger = get_logger(__name__)
        
    def _make_request(self, endpoint, params=None):
        """Make a request to the TMDB API."""
        if params is None:
            params = {}
        
        # Add the API key to the parameters
        params['api_key'] = self.api_key
        
        try:
            url = f"{self.base_url}/{endpoint}"
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()  # Raise an exception for HTTP errors
            return response.json()
        except requests.exceptions.RequestException as e:
            self.logger.error(f"TMDB API request error: {e}")
            return None
    
    def search_movie(self, query, limit=5):
        """Search for movies by name."""
        try:
            params = {'query': query, 'include_adult': 'false', 'language': 'en-US'}
            results = self._make_request('search/movie', params)
            
            if results and 'results' in results:
                # Return the top results up to the limit
                return results['results'][:limit]
            return []
        except Exception as e:
            self.logger.error(f"Error searching for movie '{query}': {e}")
            return []
    
    def search_tv(self, query, limit=5):
        """Search for TV shows by name."""
        try:
            params = {'query': query, 'include_adult': 'false', 'language': 'en-US'}
            results = self._make_request('search/tv', params)
            
            if results and 'results' in results:
                # Return the top results up to the limit
                return results['results'][:limit]
            return []
        except Exception as e:
            self.logger.error(f"Error searching for TV show '{query}': {e}")
            return []
    
    def get_movie_details(self, movie_id):
        """Get detailed information about a specific movie."""
        try:
            return self._make_request(f'movie/{movie_id}')
        except Exception as e:
            self.logger.error(f"Error getting movie details for ID {movie_id}: {e}")
            return None
    
    def get_tv_details(self, tv_id):
        """Get detailed information about a specific TV show."""
        try:
            return self._make_request(f'tv/{tv_id}')
        except Exception as e:
            self.logger.error(f"Error getting TV show details for ID {tv_id}: {e}")
            return None
    
    def get_tv_season(self, tv_id, season_number):
        """Get information about a specific season of a TV show."""
        try:
            return self._make_request(f'tv/{tv_id}/season/{season_number}')
        except Exception as e:
            self.logger.error(f"Error getting season {season_number} for TV ID {tv_id}: {e}")
            return None

# Now, import modules from the current project
skipped_items_registry = load_skipped_items()

class DirectoryProcessor:
    def __init__(self, directory_path, resume=False):
        self.directory_path = directory_path
        self.resume = resume
        self.media_extensions = {
            'video': ['.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.m4v', '.mpg', '.mpeg', '.ts'],
            'subtitles': ['.srt', '.sub', '.idx', '.ass', '.ssa'],
            'info': ['.nfo', '.txt', '.jpg', '.png', '.tbn']
        }
        self.logger = get_logger(__name__)
        self.symlink_count = 0
        self.errors = 0
        self.tmdb = TMDB()  # Initialize the real TMDB API client
        
        # Load global skipped items registry
        self.skipped_items_registry = load_skipped_items()
        
        # Check if destination directory exists and is writable
        try:
            # FIX: Use a proper configuration source rather than hardcoding
            self.can_create_symlinks = True
            
            # If DESTINATION_DIRECTORY isn't defined or doesn't exist, offer to create it
            if not os.path.exists(DESTINATION_DIRECTORY):
                print(f"Destination directory does not exist: {DESTINATION_DIRECTORY}")
                print(f"Tip: You can set SCANLY_DEST_DIR environment variable to change this location.")
                choice = input("Would you like to create it now? (Y/n): ").strip().lower()
                if choice == 'n':
                    print("Will continue without creating symlinks.")
                    self.can_create_symlinks = False
                else:
                    try:
                        os.makedirs(DESTINATION_DIRECTORY, exist_ok=True)
                        print(f"Created destination directory: {DESTINATION_DIRECTORY}")
                    except (PermissionError, OSError) as e:
                        print(f"ERROR: Could not create destination directory: {e}")
                        print("Will continue without creating symlinks.")
                        self.can_create_symlinks = False
            
            # Check write permissions if the directory exists
            elif not os.access(DESTINATION_DIRECTORY, os.W_OK):
                print(f"WARNING: No write permissions to destination directory: {DESTINATION_DIRECTORY}")
                print("Will continue without creating symlinks.")
                self.can_create_symlinks = False
                
        except Exception as e:
            self.logger.error(f"Error checking destination directory: {e}")
            print(f"WARNING: Error checking destination directory: {e}")
            print("Will continue without creating symlinks.")
            self.can_create_symlinks = False
        
        # Track processed files for resume functionality
        self.processed_files = []
        if resume:
            history = load_scan_history()
            if history and 'media_files' in history:
                self.processed_files = [item['path'] for item in history.get('media_files', [])]
        
        # Track skipped items
        self.skipped_subfolders = []
        
    def is_media_file(self, filename):
        """Check if a file is a recognized media file based on extension."""
        ext = os.path.splitext(filename.lower())[1]
        for category, extensions in self.media_extensions.items():
            if ext in extensions:
                return True, category
        return False, None
        
    def process(self):
        """Process the directory by finding media files and organizing them."""
        print("Scanning for media files...")
        
        try:
            # Get all files from directory recursively
            all_files = []
            for root, dirs, files in os.walk(self.directory_path):
                for file in files:
                    file_path = os.path.join(root, file)
                    all_files.append(file_path)
            
            total_files = len(all_files)
            print(f"Found {total_files} total files in directory structure.")
            
            # Update history with total file count
            media_files = []
            save_scan_history(self.directory_path, processed_files=0, total_files=total_files, media_files=media_files)
            
            # Process media files
            processed_count = 0
            
            print("\nIdentifying media files:")
            for file_path in all_files:
                # Skip already processed files if resuming
                if self.resume and file_path in self.processed_files:
                    processed_count += 1
                    continue
                
                # Update progress every 100 files
                if processed_count % 100 == 0:
                    self._update_progress(processed_count, total_files)
                    save_scan_history(self.directory_path, processed_files=processed_count, total_files=total_files, 
                                     media_files=media_files)
                
                # Process file
                try:
                    is_media, category = self.is_media_file(file_path)
                    if is_media:
                        rel_path = os.path.relpath(file_path, self.directory_path)
                        media_file_info = {
                            'path': file_path,
                            'relative_path': rel_path,
                            'filename': os.path.basename(file_path),
                            'type': category,
                            'size': os.path.getsize(file_path)
                        }
                        
                        media_files.append(media_file_info)
                        
                        # For video files, try to extract more metadata
                        if category == 'video':
                            self._extract_media_metadata(media_file_info)
                except Exception as e:
                    # Log error but continue processing
                    self.logger.error(f"Error processing file {file_path}: {e}")
                
                processed_count += 1
            
            # Final progress update
            self._update_progress(total_files, total_files)
            save_scan_history(self.directory_path, processed_files=total_files, total_files=total_files, 
                             media_files=media_files)
            
            # Summary of findings
            video_files = [f for f in media_files if f['type'] == 'video']
            subtitle_files = [f for f in media_files if f['type'] == 'subtitles']
            info_files = [f for f in media_files if f['type'] == 'info']
            
            print(f"\n\nScan complete. Found:")
            print(f"  • {len(video_files)} video files")
            print(f"  • {len(subtitle_files)} subtitle files")
            print(f"  • {len(info_files)} metadata/info files")
            
            # Press Enter to continue to interactive matching
            input("\nPress Enter to start matching files to TMDB...")
            
            # Clear screen and show ASCII art before starting to match files
            clear_screen()
            display_ascii_art()
            print("=" * 60)
            print(f"Processing {len(video_files)} media files from {self.directory_path}")
            print("=" * 60)
            
            if video_files:
                # Group files by subfolder for interactive processing
                self.process_by_subfolder(video_files)
                
                # Clear history since we're done
                global skipped_items_registry
                if hasattr(self, 'skipped_subfolders') and self.skipped_subfolders:
                    skipped_items_registry.extend(self.skipped_subfolders)
                    print(f"\nNote: {len(self.skipped_subfolders)} subfolders were skipped.")
                    print("You can review them later using the 'Review Skipped' option from the main menu.")
                
                # Save skipped items to file
                save_skipped_items(skipped_items_registry)
                
                clear_scan_history()
            else:
                print("\nNo video files found to process.")
            
        except Exception as e:
            self.logger.error(f"Error processing directory {self.directory_path}: {e}", exc_info=True)
            print(f"\nError processing directory: {e}")
        
        input("\nPress Enter to continue...")

    def process_by_subfolder(self, video_files):
        """Process files organized by subfolder."""
        # Initialize the subfolders dictionary
        subfolders = {}
        
        # Group files by subfolder
        for file in video_files:
            rel_path = file['relative_path']
            subfolder = os.path.dirname(rel_path)
            
            # If it's directly in the root, use a special key
            if not subfolder:
                subfolder = '.'
                
            if subfolder not in subfolders:
                subfolders[subfolder] = []
                
            subfolders[subfolder].append(file)
        
        # Sort subfolders alphabetically for consistent processing
        sorted_subfolders = sorted(subfolders.keys())
        total_subfolders = len(sorted_subfolders)
        processed_count = 0
        
        self.logger.info(f"Found {len(subfolders)} subfolders with media files")
        
        # Process each subfolder interactively
        for subfolder in sorted_subfolders:
            # Clear screen and display ASCII art at the start of each subfolder
            clear_screen()
            display_ascii_art()
            print("=" * 60)
            
            processed_count += 1
            files = subfolders[subfolder]
            
            print(f"Processing subfolder {processed_count}/{total_subfolders}")
            print(f"Path: {os.path.join(self.directory_path, subfolder)}")
            print(f"Contains {len(files)} media files")
            print("=" * 60)
            
            # Try to auto-detect content type from directory path
            full_subfolder_path = os.path.join(self.directory_path, subfolder)
            auto_content_type, is_anime = self._detect_content_type_from_directory(full_subfolder_path)
            
            # Auto-detection of content type based on file analysis if needed
            if auto_content_type is None:
                # Count files with TV and movie indicators
                tv_count = sum(1 for f in files if f.get('media_type') == 'tv')
                movie_count = sum(1 for f in files if f.get('media_type') == 'movie')
                
                # Check for episode numbers in filenames
                episode_pattern = r'[Ss]\d{1,2}[Ee]\d{1,3}|[Ee]pisode\s+\d+|\d+x\d+|/[Ss]eason\s*\d+/'
                has_episode_patterns = any(re.search(episode_pattern, f['path']) for f in files)
                
                # The key change: if we have multiple files OR it's anime with multiple files, likely a TV show
                if len(files) > 1 or has_episode_patterns or (is_anime and len(files) > 1):
                    auto_content_type = "tv"
                    if is_anime and len(files) > 1:
                        self.logger.info(f"Auto-detected as Anime Series due to multiple files ({len(files)} files) and anime content")
                    else:
                        self.logger.info(f"Auto-detected as TV due to multiple files ({len(files)} files) or episode patterns")
                else:
                    # For single file, assume it's a movie unless we have strong TV indicators
                    auto_content_type = "movie"
                    self.logger.info(f"Auto-detected as {('Anime ' if is_anime else '')}Movie due to single file")
            
            # Improved debug output
            self.logger.info(f"Auto-detected content type '{auto_content_type}' (anime={is_anime}) from path: {full_subfolder_path}")
            
            # Convert auto_content_type to a display name for the user with more info
            if auto_content_type == "tv" and not is_anime:
                content_type_display = "TV Series"
                detection_reason = "detected TV show patterns"
            elif auto_content_type == "tv" and is_anime:
                content_type_display = "Anime Series"
                detection_reason = "detected anime content with multiple files"
            elif auto_content_type == "movie" and is_anime:
                content_type_display = "Anime Movie"
                detection_reason = "detected anime content with single file"
            else:  # Movie
                content_type_display = "Movie"
                detection_reason = "single video file detected"
            
            # Clean folder name for search
            raw_name = os.path.basename(subfolder)
            
            # If subfolder is root ('.'), extract name from the original directory path or files
            if raw_name == '.':
                # Try to extract from directory path first
                raw_name = os.path.basename(self.directory_path)
                
                # If that doesn't work, try using filenames
                if not raw_name or raw_name in ['/', '.']:
                    # Try to get a name from the first video file
                    if files:
                        raw_name = os.path.basename(files[0]['path'])
                        # Remove extension
                        raw_name = os.path.splitext(raw_name)[0]
            
            clean_name = self._clean_name_for_search(raw_name)
            self.logger.info(f"Cleaned name for search: '{clean_name}' (from '{raw_name}')")
            
            # Display detected name along with content type and reason - MOVED AFTER clean_name is defined
            print(f"\nDetected title: {clean_name}")
            print(f"Detected type: {content_type_display} ({detection_reason})")
            
            # Allow user to modify the search term if needed
            search_term = clean_name
            
            # Convert auto_content_type to a display name for the user
            content_type_display = "TV Series" if auto_content_type == "tv" and not is_anime else \
                                  "Anime Series" if auto_content_type == "tv" and is_anime else \
                                  "Anime Movie" if auto_content_type == "movie" and is_anime else \
                                  "Movie"
            
            # Use MainMenu's helper to show content type selection, passing the detected name
            main_menu = MainMenu()
            
            while True:
                content_type_result = main_menu._show_content_type_menu(content_type_display, 
                                                                      auto_content_type == "tv", 
                                                                      is_anime,
                                                                      detected_name=search_term,
                                                                      file_count=len(files))  # Add file count here
                
                # Check if user chose to change search term
                if content_type_result == "CHANGE_SEARCH":
                    # Clear screen and show ASCII art
                    clear_screen()
                    display_ascii_art()
                    print("=" * 60)
                    print("Change Search Term")
                    print("=" * 60)
                    
                    # Show current search term and allow user to change it
                    print(f"\nCurrent search term: {search_term}")
                    new_term = input("Enter new search term (or press Enter to keep current): ").strip()
                    
                    if new_term:
                        search_term = new_term
                        print(f"Search term updated to: {search_term}")
                        time.sleep(1)  # Brief pause to show message
                        
                    # Go back to content type menu with updated search term
                    clear_screen()
                    display_ascii_art()
                    print("=" * 60)
                    continue
                else:
                    # User made a content type choice or chose to skip/quit
                    break
                
            # Check if user chose to skip or quit
            if content_type_result is None:
                self.skipped_subfolders.append({
                    'subfolder': subfolder,
                    'files': files,
                    'is_tv': auto_content_type == "tv",
                    'is_anime': is_anime,  # Make sure we store the anime flag
                    'suggested_name': search_term,  # Use potentially updated search term
                    'timestamp': time.time()
                })
                print("Skipping this item.")
                continue
            elif content_type_result == "QUIT":
                return
                
            # Update content type based on user selection
            is_tv, is_anime = content_type_result
            auto_content_type = "tv" if is_tv else "movie"
            
            # Clear screen and show ASCII art before searching TMDB
            clear_screen()
            display_ascii_art()
            print("=" * 60)
            print(f"Searching for: {search_term}")
            print("=" * 60)
            
            # Search TMDB and let user select the correct match
            tmdb_item = self._match_title_to_tmdb(search_term, is_tv=is_tv, is_anime=is_anime)
            
            # If the user chose to exit, exit the entire function
            if tmdb_item == "EXIT":
                print("\nExiting to main menu...")
                break
                
            # Skip this subfolder if user chose to skip
            if tmdb_item is None:
                skipped_item = {
                    'subfolder': subfolder,
                    'files': files,
                    'is_tv': is_tv,
                    'is_anime': is_anime,
                    'suggested_name': search_term,
                    'timestamp': time.time()
                }
                self.skipped_subfolders.append(skipped_item)
                self.logger.info(f"Skipped subfolder: {subfolder}")
                continue
                
            # Clear screen and show ASCII art before processing
            clear_screen()
            display_ascii_art()
            print("=" * 60)
            
            # Process the folder based on content type
            if auto_content_type == "tv":
                self.logger.info(f"Processing as TV show: {subfolder}")
                # Call the process_tv_show method
                self.process_tv_show(subfolder, files, tmdb_item)
            else:
                self.logger.info(f"Processing as movie: {subfolder}")
                # Call the process_movie method
                self.process_movie(subfolder, files, tmdb_item)

    def process_tv_show(self, subfolder, files, tmdb_item):
        """
        Process a TV show folder.
        
        Args:
            subfolder: Path to the subfolder relative to main directory
            files: List of files in the subfolder
            tmdb_item: TMDB item data for the TV show
        """
        try:
            # Get TV show metadata
            show_id = tmdb_item.get('id')
            show_name = tmdb_item.get('name', 'Unknown')
            first_air_date = tmdb_item.get('first_air_date', '').split('-')[0] if tmdb_item.get('first_air_date') else ''
            
            # IMPORTANT: Make sure we capture the is_anime flag from tmdb_item
            is_anime = tmdb_item.get('is_anime', False)
            
            print(f"\nProcessing TV show: {show_name} ({first_air_date})")
            
            # Get additional TV show details from TMDB
            try:
                show_details = self.tmdb.get_tv_details(show_id)
                seasons = show_details.get('seasons', []) if show_details else []
                
                # Filter out specials (season 0)
                regular_seasons = [s for s in seasons if s.get('season_number', 0) > 0]
                
                if regular_seasons:
                    # Get the type flag for this content (for directory structure)
                    is_tv = True  # Since this is a TV show
                    
                    # For each video file, try to determine its season and episode
                    for file_info in files:
                        # Set the anime flag in the file_info for use in manual processing if needed
                        file_info['is_anime'] = is_anime
                        
                        # Extract episode info
                        file_path = file_info['path']
                        file_name = file_info['filename']
                        
                        season_num, episode_num = self._extract_episode_info(file_path, file_name)
                        
                        if season_num is not None and episode_num is not None:
                            # Create appropriate symlink with season/episode info
                            self._create_symlink(
                                file_path, 
                                show_name, 
                                year=first_air_date,
                                season=season_num, 
                                episode=episode_num,
                                is_tv=is_tv,
                                is_anime=is_anime  # Pass the anime flag here
                            )
                            print(f"  ✓ Processed S{season_num:02d}E{episode_num:02d}: {file_name}")
                        else:
                            # Cannot determine season/episode, ask user
                            print(f"\nCould not determine season/episode for: {file_name}")
                            # Call manual process method
                            self._manually_process_tv_files([file_info], show_id, show_name, first_air_date)
                
                else:
                    # No season information from TMDB, handle manually
                    print("\nNo season information available. Processing files manually...")
                    self._manually_process_tv_files(files, show_id, show_name, first_air_date)
                    
            except Exception as e:
                self.logger.error(f"Error getting TV show details: {e}", exc_info=True)
                print(f"Error getting TV show details: {e}")
                print("Processing files manually...")
                self._manually_process_tv_files(files, show_id, show_name, first_air_date)
            
            print("\nTV show processing complete")
            
        except Exception as e:
            self.logger.error(f"Error processing TV show folder: {e}", exc_info=True)
            print(f"Error processing TV show folder: {e}")

    def _manually_process_tv_files(self, video_files, show_id, show_name, first_air_date):
        """Method to manually process TV files."""
        # Implementation for manually processing TV files
        try:
            print(f"\nManually processing {len(video_files)} files for {show_name}")
            
            # Get the type flag for this content
            # Check if any flags were already set in the video_files metadata
            is_anime = video_files[0].get('is_anime', False) if video_files else False
            
            # Process each video file
            for i, file_info in enumerate(video_files):
                file_path = file_info['path']
                file_name = file_info['filename']
                
                print(f"\n[{i+1}/{len(video_files)}] Processing: {file_name}")
                
                # Try to extract season and episode from filename if available
                season_num, episode_num = self._extract_episode_info(file_path, file_name)
                
                # Let user confirm or override
                print("\nEnter season and episode information:")
                
                # Show detected info if available
                if season_num is not None:
                    season_input = input(f"Season number [{season_num}]: ").strip()
                    if season_input:
                        try:
                            season_num = int(season_input)
                        except ValueError:
                            print("Invalid input, using detected season number.")
                else:
                    season_input = input("Season number: ").strip()
                    try:
                        season_num = int(season_input)
                    except ValueError:
                        print("Invalid season number. Skipping this file.")
                        continue
                
                if episode_num is not None:
                    episode_input = input(f"Episode number [{episode_num}]: ").strip()
                    if episode_input:
                        try:
                            episode_num = int(episode_input)
                        except ValueError:
                            print("Invalid input, using detected episode number.")
                else:
                    episode_input = input("Episode number: ").strip()
                    try:
                        episode_num = int(episode_input)
                    except ValueError:
                        print("Invalid episode number. Skipping this file.")
                        continue
                
                # Try to get episode title from TMDB
                episode_title = self._get_episode_title_from_tmdb(show_id, season_num, episode_num)
                
                # Create the symlink with the gathered information
                success = self._create_symlink(
                    file_path, 
                    show_name, 
                    year=first_air_date,
                    season=season_num, 
                    episode=episode_num,
                    is_tv=True,
                    is_anime=is_anime  # Pass through the anime flag
                )
                
                if success:
                    print(f"  ✓ Processed S{season_num:02d}E{episode_num:02d}: {file_name}")
                else:
                    print(f"  ✗ Failed to process: {file_name}")
            
        except Exception as e:
            self.logger.error(f"Error in manual processing: {e}", exc_info=True)
            print(f"Error in manual processing: {e}")

    def process_movie(self, subfolder, files, tmdb_item):
        """
        Process a movie folder.
        
        Args:
            subfolder: Path to the subfolder relative to main directory
            files: List of files in the subfolder
            tmdb_item: TMDB item data for the movie
        """
        try:
            # Get movie metadata
            movie_id = tmdb_item.get('id')
            movie_title = tmdb_item.get('title', 'Unknown')
            release_date = tmdb_item.get('release_date', '').split('-')[0] if tmdb_item.get('release_date') else ''
            
            # IMPORTANT: Make sure we capture the is_anime flag from tmdb_item
            is_anime = tmdb_item.get('is_anime', False)
            
            print(f"\nProcessing movie: {movie_title} ({release_date})")
            print(f"Is anime: {'Yes' if is_anime else 'No'}")  # Add debug output
            
            # Get the type flag for this content (for directory structure)
            is_tv = False  # Since this is a movie
            
            # Process each video file
            for file_info in files:
                file_path = file_info['path']
                file_name = file_info['filename']
                
                # Create symbolic link for the movie
                success = self._create_symlink(
                    file_path, 
                    movie_title, 
                    year=release_date,
                    is_tv=is_tv,
                    is_anime=is_anime  # Pass the anime flag here
                )
                
                if success:
                    print(f"  ✓ Processed: {file_name}")
                else:
                    print(f"  ✗ Failed to process: {file_name}")
            
            print("\nMovie processing complete")
            
        except Exception as e:
            self.logger.error(f"Error processing movie folder: {e}", exc_info=True)
            print(f"Error processing movie folder: {e}")

    def _extract_media_metadata(self, media_file):
        """Extract metadata from a media file."""
        try:
            filename = media_file['filename']
            
            # FIX: Create simple placeholders for extractors to avoid import errors
            def extract_name(filename):
                # Simple extraction - remove extension, replace separators with spaces
                base_name = os.path.splitext(filename)[0]
                return re.sub(r'[._-]', ' ', base_name)
            
            def extract_season(filename):
                # Look for patterns like S01, Season 1, etc.
                season_match = re.search(r'[Ss](\d{1,2})', filename)
                if season_match:
                    return int(season_match.group(1))
                return None
            
            def extract_episode(filename):
                # Look for patterns like E01, Episode 1, etc.
                episode_match = re.search(r'[Ee](\d{1,3})', filename)
                if episode_match:
                    return int(episode_match.group(1))
                return None
            
            # Try to extract metadata
            media_file['extracted_name'] = extract_name(filename)
            media_file['season'] = extract_season(filename)
            media_file['episode'] = extract_episode(filename)
            
            # Determine if it's likely a TV show or movie
            media_file['media_type'] = 'tv' if media_file['season'] is not None else 'movie'
            
            # Try to get year from filename (e.g., "Movie (2020).mkv")
            year_match = re.search(r'\((\d{4})\)', filename)
            if year_match:
                media_file['year'] = year_match.group(1)
            
        except Exception as e:
            self.logger.error(f"Error extracting metadata from {filename}: {e}")
            media_file['extracted_name'] = os.path.splitext(filename)[0]
            media_file['media_type'] = 'unknown'
    
    def _update_progress(self, current, total):
        """
        Update progress display in the console.
        
        Args:
            current: Current number of files processed
            total: Total number of files to process
        """
        try:
            # Handle edge case of zero total
            if total == 0:
                percentage = 100
            else:
                percentage = int((current / total) * 100)
            
            # Create a progress bar
            bar_length = 30
            filled_length = int(bar_length * current // total) if total > 0 else 30
            bar = '█' * filled_length + '░' * (bar_length - filled_length)
            
            # Print progress information (using \r to stay on the same line)
            print(f"\rProgress: |{bar}| {percentage}% ({current}/{total} files)", end='', flush=True)
            
            # Add a newline when we reach 100%
            if current >= total:
                print()
        except Exception as e:
            # Fail gracefully if there's an error in the progress display
            self.logger.error(f"Error updating progress: {e}")
            print(f"\rProcessed {current} of {total} files ({percentage}%)", end='', flush=True)

    def _clean_name_for_search(self, name):
        """
        Clean a folder or file name for TMDB search.
        
        Args:
            name: Original name to clean
        
        Returns:
            Cleaned name suitable for searching
        """
        try:
            # First, try to extract a year if present
            extracted_title = name
            extracted_year = None
            
            # Look for year patterns like "2009", "(2009)", "[2009]"
            year_pattern = r'(?:\(|\[|\s|^)(\d{4})(?:\)|\]|\s|$)'
            year_match = re.search(year_pattern, name)
            
            if year_match:
                # Extract the year
                extracted_year = year_match.group(1)
                
                # Find the position of the year in the string
                year_pos = name.find(extracted_year)
                
                # If year is not at the beginning, assume everything before it is the title
                if year_pos > 0:
                    # Get the text before the year (accounting for possible brackets)
                    bracket_start = max(0, year_pos - 1)
                    while bracket_start > 0 and name[bracket_start] in '([':
                        bracket_start -= 1
                    
                    if bracket_start > 0:
                        extracted_title = name[:bracket_start].strip()
            
            # Replace common separators with spaces
            cleaned_name = re.sub(r'[._-]', ' ', extracted_title)
            
            # Remove common patterns in media files - add more aggressive patterns
            patterns_to_remove = [
                # Resolutions and quality indicators
                r'\b\d{3,4}p\b',           # Resolution (e.g., 720p, 1080p)
                r'\b\d+x\d+\b',            # Resolution format like 1920x1080
                
                # Web download variations - more comprehensive to catch partial matches
                r'\bWEB[ \-]?DL\b',        # WEB-DL, WEB DL, WEBDL
                r'\bWEBDL\b',
                r'\bWEB\b',                # Standalone WEB
                r'\bDL\b',                 # Standalone DL
                
                r'\bHDTV\b', 
                r'\bWEBRip\b',
                r'\b[0-9]+bit\b',          # Bit depth
                
                # Encodings - more thorough patterns
                r'\bx264\b', r'\bx265\b', r'\bHEVC\b', r'\bHDR\b', r'\bHDR10\b', r'\bDolbyVision\b',
                r'\bH[ .\-]?264\b',        # Catch H.264, H-264, H 264
                r'\bH[ .\-]?265\b',        # Catch H.265, H-265, H 265
                r'\bVP9\b', r'\bAV1\b', r'\bXviD\b', r'\bDivX\b',
                
                # Audio formats
                r'\bAAC\b', r'\bAC3\b', r'\bMP3\b', r'\bFLAC\b',
                r'\bAAC[0-9][\.]?[0-9]?\b',  # Catch formats like AAC2.0 or AAC5.1
                r'\bDTS\b', r'\bDTS-HD\b', r'\bTrueHD\b', r'\bAtmos\b',
                r'\b[0-9][\.]?[0-9]ch\b',    # Catch formats like 5.1ch or 7.1ch
                r'\bMA\b', r'\bDD\b', r'\bDD\+\b',  # More audio format abbreviations
                
                # Source indicators
                r'\bBluRay\b', r'\bDVDRip\b', r'\bWEB-DL\b', r'\bWEBRip\b', r'\bHDRip\b',
                r'\bXviD\b', r'\bDivX\b', r'\bBRRip\b', r'\bDVD\b', r'\bBDRip\b',
                r'\bBDRemux\b', r'\bRemux\b', r'\bBlu ray\b', r'\bAVC\b',  
                
                # Release attributes
                r'\brepack\b', r'\bproper\b', r'\bremux\b', r'\bunrated\b',
                r'\bdual[ .]?audio\b', r'\bmulti[ .]?subs\b',
                
                # Collection/Complete indicators
                r'\bcomplete\b', r'\bcollection\b', r'\bseason[s]?\b', r'\ball\b',
                r'\bfull\b', r'\bentire\b', r'\bPack\b', r'\bBox Set\b',
                
                # Season/Episode markers
                r'\bS\d{1,2}\b',           # Season markers like S01
                r'\bE\d{1,3}\b',           # Episode markers like E01
                r'\bSeason\s+\d{1,2}\b',   # "Season 1"
                r'\bEpisode\s+\d{1,3}\b',  # "Episode 1"
                
                # Content in brackets and parentheses
                r'\(.*?\)',  # Content in parentheses
                r'\[.*?\]',  # Content in brackets
                r'\{.*?\}',  # Content in braces
                
                # Years (remove years from the title for better searching)
                r'\b\d{4}\b'  # Stand-alone 4-digit numbers (likely years)
            ]
            
            # Apply each pattern separately to better see what's being removed
            for pattern in patterns_to_remove:
                before = cleaned_name
                cleaned_name = re.sub(pattern, '', cleaned_name, flags=re.IGNORECASE)
            
            # Remove common scene group names and release info
            scene_groups = [
                r'\bRARBG\b', r'\bETRG\b', r'\bYIFY\b', r'\bYTS\b',
                r'\bOZC\b', r'\bSPARKS\b', r'\bGECKOS\b', r'\bCMRG\b',
                r'\bAMIABLE\b', r'\bEVO\b', r'\bFLEET\b', r'\bSHAaNiG\b',
                r'\bPikanet128\b', r'\brartv\b', r'\bKRaLiMaRKo\b'  # Added more release groups
            ]
            
            for group in scene_groups:
                cleaned_name = re.sub(group, '', cleaned_name, flags=re.IGNORECASE)
            
            # Remove season/episode patterns - extended for different formats
            cleaned_name = re.sub(r'S\d{1,2}E\d{1,3}', '', cleaned_name, flags=re.IGNORECASE)
            cleaned_name = re.sub(r'\d{1,2}x\d{1,2}', '', cleaned_name, flags=re.IGNORECASE)  # Format like 1x01
            cleaned_name = re.sub(r'Season\s+\d{1,2}\s+Episode\s+\d{1,3}', '', cleaned_name, flags=re.IGNORECASE)
            
            # Remove trailing periods and underscores often found in anime filenames
            cleaned_name = re.sub(r'\.{2,}', ' ', cleaned_name)  # Replace multiple dots with space
            
            # Remove standalone numbers that may be episode numbers
            cleaned_name = re.sub(r'\b\d+\b', '', cleaned_name)
            
            # Remove multi-spaces and trim
            cleaned_name = re.sub(r'\s+', ' ', cleaned_name).strip()
            
            # Add debug logging to see what happened
            self.logger.debug(f"Original: '{name}' -> Cleaned: '{cleaned_name}'")
            
            return cleaned_name
        except Exception as e:
            self.logger.error(f"Error cleaning name '{name}': {e}")
            return name  # Return original name if cleaning fails

    def _extract_episode_info(self, file_path, filename):
        """
        Extract season and episode information from a file path and name.
        
        Args:
            file_path: The full path to the file
            filename: The name of the file
        
        Returns:
            Tuple of (season_number, episode_number) or (None, None) if not found
        """
        patterns = [
            # S01EP01 pattern (notice the EP variation)
            r'[Ss](\d{1,2})EP(\d{1,3})',
            
            # S01E01 pattern
            r'[Ss](\d{1,2})[Ee](\d{1,3})',
            
            # Season 1 Episode 1 pattern
            r'[Ss]eason\s*(\d{1,2}).*?[Ee]pisode\s*(\d{1,3})',
            
            # 1x01 pattern
            r'(\d{1,2})x(\d{2,3})',
            
            # Folder structure pattern - look for season number and episode number in path
            r'/[Ss]eason\s*(\d{1,2})/.*?(\d{1,3})',
            
            # Simple numbers sequence - like s01e01 or S1E1 without the S or E
            r'(\d{1,2})(\d{2})(?:\D|$)'
        ]
        
        # First check the filename for common patterns
        for pattern in patterns:
            match = re.search(pattern, filename)
            if match:
                return int(match.group(1)), int(match.group(2))
        
        # Then check the file path
        for pattern in patterns:
            match = re.search(pattern, file_path)
            if match:
                return int(match.group(1)), int(match.group(2))
        
        # If still not found, try to extract just the season number
        season_patterns = [
            r'[Ss]eason\s*(\d{1,2})',
            r'[Ss](\d{1,2})[^Ee]',
            r'/[Ss](\d{1,2})/'  # Look for season folder pattern like /S01/
        ]
        
        for pattern in season_patterns:
            match = re.search(pattern, file_path) or re.search(pattern, filename)
            if match:
                # Found season but not episode
                return int(match.group(1)), None
        
        # Look for episode number in filename if we have a known season structure
        if "season" in file_path.lower() or "/s0" in file_path.lower() or "/s1" in file_path.lower():
            # Extract season from path
            season_match = re.search(r'season\s*(\d{1,2})|/[Ss](\d{1,2})/', file_path)
            if season_match:
                season_num = int(season_match.group(1) if season_match.group(1) else season_match.group(2))
                
                # Now look for just episode number in filename
                episode_match = re.search(r'(\d{1,3})', filename)
                if episode_match:
                    return season_num, int(episode_match.group(1))
        
        # Could not find season or episode
        return None, None

    def _detect_content_type_from_directory(self, directory_path):
        """
        Detect if a directory contains a TV show or movie.
        
        Args:
            directory_path: Path to the directory
            
        Returns:
            Tuple of (content_type, is_anime)
            where content_type is 'tv' or 'movie'
        """
        # Default to unknown
        is_anime = False
        content_type = None  # Default content type to None
        
        # Extract clean name for MDBlist check and other detection methods
        directory_name = os.path.basename(directory_path)
        clean_name = re.sub(r'\([^)]*\)', '', directory_name)  # Remove content in parentheses
        clean_name = re.sub(r'^\s*|\s*$', '', clean_name)  # Trim whitespace
                
        # Look for year in the directory name - will help with matching
        year_match = re.search(r'\((\d{4})\)', directory_name)
        year = year_match.group(1) if year_match else None
        
        # Check if this title is in any configured MDBlist
        if mdblist_enabled:
            try:
                # Call MDBlist handler's method to check content type
                matched, mdb_content_type = mdblist_handler.get_content_type_from_list(clean_name, year)
                if matched and mdb_content_type:
                    if mdb_content_type in ['anime_series', 'anime_movies']:
                        is_anime = True
                        
                    if mdb_content_type in ['anime_series', 'tv_shows']:
                        content_type = 'tv'
                    elif mdb_content_type in ['anime_movies', 'movies']:
                        content_type = 'movie'
                    
                    self.logger.debug(f"MDBlist identified '{directory_name}' as {mdb_content_type}")
                    return content_type, is_anime
            except Exception as e:
                self.logger.error(f"Error checking MDBlist: {e}")
        
        # Continue with current detection logic if MDBlist didn't match
        # First, check for anime indicators (regardless of TV or movie)
        anime_indicators = ['anime', 'animation', 'animated', 'japanese', 'japan', 
                           'jp', 'jdrama', 'j-drama', 'dorama', 'donghua']
                           
        for indicator in anime_indicators:
            if indicator in directory_name.lower() or indicator in directory_path.lower():
                is_anime = True
                break
        
        # Check for TV show indicators
        tv_indicators = ['season', 's01', 's02', 's1', 's2', 'episode', 'series', 
                         'tv', 'complete', 'collection', 'pack']
        
        # Check for movie indicators
        movie_indicators = ['movie', 'film', 'feature', 'bluray', 'dvdrip', 
                            'bdrip', 'brrip', 'webdl', 'web-dl']
        
        # Count indicators
        tv_count = 0
        movie_count = 0
        
        for indicator in tv_indicators:
            if indicator in directory_name.lower() or indicator in directory_path.lower():
                tv_count += 1
        
        for indicator in movie_indicators:
            if indicator in directory_name.lower() or indicator in directory_path.lower():
                movie_count += 1
        
        # Determine content type based on indicators
        if tv_count > movie_count:
            content_type = 'tv'
        elif movie_count > 0:
            content_type = 'movie'
        else:
            # If we can't determine, default to movie
            content_type = 'movie'
        
        # Return the detected content type and anime flag
        return content_type, is_anime

    def _get_episode_title_from_tmdb(self, show_id, season_num, episode_num):
        """
        Get episode title from TMDB.
        
        Args:
            show_id: TMDB ID of the TV show
            season_num: Season number
            episode_num: Episode number
        
        Returns:
            Episode title or None if not found
        """
        try:
            # Get episode details from TMDB
            season_details = self.tmdb.get_tv_season(show_id, season_num)
            
            if season_details and 'episodes' in season_details:
                episodes = season_details['episodes']
                
                # Find the matching episode
                for episode in episodes:
                    if episode.get('episode_number') == episode_num:
                        return episode.get('name')
            
            return None
        except Exception as e:
            self.logger.error(f"Error getting episode title: {e}")
            return None

    def _match_title_to_tmdb(self, search_term, is_tv, is_anime=False):
        """
        Search TMDB for a title and let the user select the correct match.
        
        Args:
            search_term: The cleaned name to search for
            is_tv: Whether we're searching for TV shows or movies
            is_anime: Whether content is anime (for specialized searching)
            
        Returns:
            Selected TMDB item or None if skipped or "EXIT" if user chose to exit
        """
        try:
            content_type = "TV show" if is_tv else "movie"
            anime_label = " (anime)" if is_anime else ""
            print(f"Searching TMDB for {content_type}{anime_label}: {search_term}")
            
            # Perform initial search
            if is_tv:
                results = self.tmdb.search_tv(search_term, limit=5)
            else:
                results = self.tmdb.search_movie(search_term, limit=5)
                
            if not results:
                print("No results found. Try a different search term.")
                new_search = input("Enter new search term (or press Enter to skip, 'q' to quit): ").strip()
                
                if new_search.lower() == 'q':
                    return "EXIT"
                elif not new_search:
                    return None
                
                # Clear screen and show ASCII art before searching again
                clear_screen()
                display_ascii_art()
                print("=" * 60)
                print(f"Searching for: {new_search}")
                print("=" * 60)
                
                # Try again with new search term
                if is_tv:
                    results = self.tmdb.search_tv(new_search, limit=5)
                else:
                    results = self.tmdb.search_movie(new_search, limit=5)
                    
                if not results:
                    print("Still no results found. Skipping this item.")
                    return None
            
            # Display results
            print("\nSearch results:")
            for i, result in enumerate(results, 1):
                if is_tv:
                    title = result.get('name', 'Unknown')
                    year = result.get('first_air_date', '')[:4] if result.get('first_air_date') else 'Unknown'
                    print(f"{i}. {title} ({year})")
                else:
                    title = result.get('title', 'Unknown')
                    year = result.get('release_date', '')[:4] if result.get('release_date') else 'Unknown'
                    print(f"{i}. {title} ({year})")
                    
            # Additional search option
            print("\nOptions:")
            print(f"1-{len(results)}: Select matching title")
            print("s: Search for a different term")
            print("k: Skip this item")
            print("q: Quit to main menu")
            
            while True:
                choice = input("\nEnter choice (or press Enter for option 1): ").strip().lower()
                
                # Handle empty input as option 1
                if not choice:
                    choice = "1"
                    
                # Process the choice
                if choice.isdigit() and 1 <= int(choice) <= len(results):
                    selected_item = results[int(choice)-1]
                    # IMPORTANT: Add the is_anime flag to the selected item
                    selected_item['is_anime'] = is_anime
                    return selected_item
                elif choice == 's':
                    # Recursive call to search again
                    return self._match_title_to_tmdb(
                        input("Enter new search term: ").strip(), 
                        is_tv, 
                        is_anime
                    )
                elif choice == 'k':
                    return None
                elif choice == 'q':
                    return "EXIT"
                else:
                    print("Invalid choice. Please try again.")
        
        except Exception as e:
            self.logger.error(f"Error matching title to TMDB: {e}", exc_info=True)
            print(f"Error searching TMDB: {e}")
            
            # Let the user decide what to do
            choice = input("\nPress Enter to skip, or 'q' to quit: ").strip().lower()
            return "EXIT" if choice == 'q' else None

    def _sanitize_filename(self, filename):
        """
        Sanitize a filename to be safe for filesystem use.
        
        Args:
            filename: The filename to sanitize
        
        Returns:
            A sanitized filename
        """
        try:
            # Replace characters that are invalid in filenames
            invalid_chars = ['<', '>', ':', '"', '/', '\\', '|', '?', '*']
            for char in invalid_chars:
                filename = filename.replace(char, '_')
            
            # Limit filename length (max 255 bytes on most filesystems)
            max_length = 200  # Add some buffer for extensions
            
            if len(filename.encode('utf-8')) > max_length:
                # Truncate by bytes, not characters to ensure it fits
                byte_filename = filename.encode('utf-8')[:max_length]
                # Convert back to string, ensuring we don't cut in the middle of a multibyte character
                filename = byte_filename.decode('utf-8', errors='ignore')
            
            return filename
        except Exception as e:
            self.logger.error(f"Error sanitizing filename '{filename}': {e}")
            # Return a safe fallback if sanitization fails
            return re.sub(r'[^\w\-\. ]', '_', filename)[:200]

    def _get_destination_folder(self, is_tv, is_anime, resolution=None):
        """
        Get the appropriate destination folder based on content type and resolution.
        
        Args:
            is_tv: Boolean indicating if content is a TV series
            is_anime: Boolean indicating if content is anime
            resolution: Optional resolution string (e.g., '2160p', '1080p')
            
        Returns:
            Path to the destination folder
        """
        # Load environment variables if not already available
        from dotenv import load_dotenv
        load_dotenv()
        
        base_dir = os.getenv('DESTINATION_DIRECTORY', '')
        
        # Determine folder based on content type
        if is_tv and is_anime:
            folder_name = os.getenv('CUSTOM_ANIME_SHOW_FOLDER', 'Anime Shows')
        elif is_tv and not is_anime:
            folder_name = os.getenv('CUSTOM_SHOW_FOLDER', 'TV Shows')
        elif not is_tv and is_anime:
            folder_name = os.getenv('CUSTOM_ANIME_MOVIE_FOLDER', 'Anime Movies')
        else:  # Movie
            folder_name = os.getenv('CUSTOM_MOVIE_FOLDER', 'Movies')
        
        # Check if resolution-based organization is enabled
        use_resolution_structure = False
        if is_tv:
            use_resolution_structure = os.getenv('SHOW_RESOLUTION_STRUCTURE', 'false').lower() == 'true'
        else:
            use_resolution_structure = os.getenv('MOVIE_RESOLUTION_STRUCTURE', 'false').lower() == 'true'
        
        # If resolution structure is enabled and resolution is provided, get the appropriate subfolder
        if use_resolution_structure and resolution:
            # Implementation for resolution-based organization
            pass
        
        # Return full path
        return os.path.join(base_dir, folder_name)

    def _create_symlink(self, source_path, title, year=None, season=None, episode=None, is_tv=False, is_anime=False):
        """
        Create a symlink from the source file to the appropriate destination.
        
        Args:
            source_path: Path to the source file
            title: Title of the movie or TV show
            year: Year of release (optional)
            season: Season number for TV shows (optional)
            episode: Episode number for TV shows (optional)
            is_tv: Boolean indicating if content is a TV series
            is_anime: Boolean indicating if content is anime
            
        Returns:
            Boolean indicating success
        """
        try:
            # Get the base destination directory based on content type
            base_dest_dir = self._get_destination_folder(is_tv, is_anime)
            
            # Create the destination directory if it doesn't exist
            if not os.path.exists(base_dest_dir):
                os.makedirs(base_dest_dir, exist_ok=True)
                
            # Build the destination path based on content type
            if is_tv:
                # For TV shows
                show_folder = f"{title} ({year})" if year else title
                show_dir = os.path.join(base_dest_dir, show_folder)
                
                if not os.path.exists(show_dir):
                    os.makedirs(show_dir, exist_ok=True)
                
                if season is not None:
                    season_folder = f"Season {season}"
                    season_dir = os.path.join(show_dir, season_folder)
                    
                    if not os.path.exists(season_dir):
                        os.makedirs(season_dir, exist_ok=True)
                    
                    dest_dir = season_dir
                else:
                    dest_dir = show_dir
            else:
                # For movies
                movie_folder = f"{title} ({year})" if year else title
                movie_dir = os.path.join(base_dest_dir, movie_folder)
                
                if not os.path.exists(movie_dir):
                    os.makedirs(movie_dir, exist_ok=True)
                
                dest_dir = movie_dir
            
            # Get filename for destination
            filename = os.path.basename(source_path)
            dest_path = os.path.join(dest_dir, filename)
            
            # Create the symlink
            if os.path.exists(dest_path):
                self.logger.info(f"Symlink already exists: {dest_path}")
                return True
            
            relative_symlink = os.getenv('RELATIVE_SYMLINK', 'false').lower() == 'true'
            
            if relative_symlink:
                # Calculate relative path from destination to source
                source_rel_path = os.path.relpath(source_path, dest_dir)
                os.symlink(source_rel_path, dest_path)
            else:
                # Use absolute path
                os.symlink(source_path, dest_path)
            
            self.symlink_count += 1
            self.logger.info(f"Created symlink from {source_path} to {dest_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error creating symlink: {e}", exc_info=True)
            self.errors += 1
            return False

def get_input(prompt, default=None, cancel_value=None):
    """
    Get user input with universal exit command handling.
    
    Args:
        prompt: The prompt to display to the user
        default: Default value if user presses Enter
        cancel_value: Value to return if user types "exit"
        
    Returns:
        User input, or default if Enter was pressed (empty input), or cancel_value if "exit" was typed
    """
    user_input = input(prompt).strip()
    
    # Check for exit command
    if user_input.lower() == "exit":
        print("Returning to main menu...")
        return cancel_value
    
    # Return default value if Enter was pressed (empty input)
    if user_input == "" and default is not None:
        return default
        
    return user_input

def review_skipped_items():
    """Allow the user to review previously skipped items."""
    global skipped_items_registry
    
    if not skipped_items_registry:
        print("\nNo skipped items to review.")
        input("\nPress Enter to return to the main menu...")
        return
    
    while skipped_items_registry:
        # Clear screen
        clear_screen()
        display_ascii_art()
        print("=" * 60)
        print(f"Review Skipped Items ({len(skipped_items_registry)} remaining)")
        print("=" * 60)
        
        # Get the first skipped item
        item = skipped_items_registry[0]
        subfolder = item['subfolder']
        files = item['files']
        is_tv = item.get('is_tv', False)
        is_anime = item.get('is_anime', False)  # Make sure we get the anime flag if it exists
        suggested_name = item.get('suggested_name', os.path.basename(subfolder))
        
        # Convert content type flags to display string
        content_type_display = "TV Series" if is_tv and not is_anime else \
                              "Anime Series" if is_tv and is_anime else \
                              "Anime Movie" if not is_tv and is_anime else \
                              "Movie"
        
        print(f"\nSkipped subfolder: {subfolder}")
        print(f"Contains {len(files)} media files")
        print(f"Type: {content_type_display}")
        print(f"Suggested title: {suggested_name}")
        print("Type 'exit' at any prompt to return to main menu")
        
        choice = get_input("\nChoose action: (p)rocess, (s)kip again, (q)uit reviewing, (c)hange content type (default=p): ", 
                         default="p", cancel_value="q")
        
        if choice == "q":
            # User chose to exit/quit
            break
        
        if choice == 'c':
            # Allow changing content type before processing
            main_menu = MainMenu()
            content_type_result = main_menu._show_content_type_menu(
                content_type_display, 
                is_tv, 
                is_anime, 
                detected_name=suggested_name,
                file_count=len(files))  # Add file count here
            
            if content_type_result is None or content_type_result == "QUIT":
                # User chose to skip or quit
                continue  # Skip to the next iteration of the loop
            
            # Update content type flags in the item
            is_tv, is_anime = content_type_result
            item['is_tv'] = is_tv
        
        if choice == 'p':
            # Process this item
            processor = DirectoryProcessor('.')  # Create a temporary processor for handling this item
            
            # Clear screen and show ASCII art before searching TMDB
            clear_screen()
            display_ascii_art()
            print("=" * 60)
            print(f"Searching for: {suggested_name}")
            print("=" * 60)
            
            if is_tv:
                # Search TMDB for TV show
                search_term = get_input(f"\nEnter search term for TV show (default='{suggested_name}'): ", 
                                     default=suggested_name, cancel_value="")
                
                if search_term == "":
                    # User chose to exit
                    break
                
                # Search TMDB with proper flags
                tmdb_item = processor._match_title_to_tmdb(search_term, is_tv=True, is_anime=is_anime)
                
                if tmdb_item == "EXIT":
                    break
                    
                if tmdb_item:
                    # Clear screen and show ASCII art before processing
                    clear_screen()
                    display_ascii_art()
                    print("=" * 60)
                    
                    # Process the TV show with the correct content type flags
                    processor.process_tv_show(subfolder, files, tmdb_item)
                    skipped_items_registry.pop(0)  # Remove this item from registry
                    save_skipped_items(skipped_items_registry)  # Save the updated registry
                    
                    input("\nPress Enter to continue...")
                    continue
                else:
                    print("No results found. Keeping item in skipped registry.")
                    time.sleep(2)
            else:
                # Process movie with proper flags
                search_term = get_input(f"\nEnter search term for movie (default='{suggested_name}'): ", 
                                     default=suggested_name, cancel_value="")
                
                if search_term == "":
                    # User chose to exit
                    break
                
                # Search TMDB with proper flags
                tmdb_item = processor._match_title_to_tmdb(search_term, is_tv=False, is_anime=is_anime)
                
                if tmdb_item == "EXIT":
                    break
                    
                if tmdb_item:
                    # Make sure the is_anime flag is set in the TMDB item
                    tmdb_item['is_anime'] = is_anime
                    
                    # Clear screen and show ASCII art before processing
                    clear_screen()
                    display_ascii_art()
                    print("=" * 60)
                    
                    # Process the movie with the correct content type flags
                    processor.process_movie(subfolder, files, tmdb_item)
                    skipped_items_registry.pop(0)  # Remove this item from registry
                    save_skipped_items(skipped_items_registry)  # Save the updated registry
                    
                    input("\nPress Enter to continue...")
                    continue
                else:
                    print("No results found. Keeping item in skipped registry.")
                    time.sleep(2)
        
        elif choice == 's':
            # Skip again - move to the end of the list without confirmation
            skipped_item = skipped_items_registry.pop(0)
            skipped_items_registry.append(skipped_item)
            print("Item moved to the end of the list.")
            time.sleep(1)
        
        elif choice == 'q':
            # Quit reviewing without confirmation
            break
        
        else:
            print("Invalid choice.")
            time.sleep(1)
    
    # Save any changes to the registry
    save_skipped_items(skipped_items_registry)

class MainMenu:
    def __init__(self):
        # Initialize menu class
        self.logger = get_logger(__name__)
        
    def individual_scan(self):
        """Scan a directory or file for media processing."""
        # Clear screen first
        clear_screen()
        
        # Display ASCII art at the top
        display_ascii_art()
        
        # Add only a separator line
        print("=" * 60)
        
        # Just show the prompt directly
        while True:
            path = input("Enter or drag/drop a file/directory to scan (or 'c' to cancel): ")
            if path.lower() == 'c':
                return
            
            # Clean the path without showing output
            cleaned_path = _clean_directory_path(path)
            
            if os.path.exists(cleaned_path):
                try:
                    if os.path.isdir(cleaned_path):
                        # Process as a directory
                        print(f"\nProcessing directory: {cleaned_path}")
                        
                        # Save the initial scan info
                        save_scan_history(cleaned_path)
                        
                        # Create and use our DirectoryProcessor
                        processor = DirectoryProcessor(cleaned_path)
                        processor.process()
                    else:
                        # Process as a single file - just show filename
                        file_name = os.path.basename(cleaned_path)
                        file_dir = os.path.dirname(cleaned_path)
                        
                        # Create a temporary processor to use its methods
                        processor = DirectoryProcessor(file_dir)
                        
                        # Check if this is a media file
                        is_media, category = processor.is_media_file(file_name)
                        
                        if is_media and category == 'video':
                            # Create file info dictionary
                            rel_path = os.path.basename(cleaned_path)
                            file_info = {
                                'path': cleaned_path,
                                'relative_path': rel_path,
                                'filename': file_name,
                                'type': category,
                                'size': os.path.getsize(cleaned_path)
                            }
                            
                            # Extract any possible metadata
                            processor._extract_media_metadata(file_info)
                            
                            # Clean the filename for search
                            clean_name = processor._clean_name_for_search(os.path.splitext(file_name)[0])
                            search_term = clean_name  # Store in a variable that can be updated

                            print(f"\nDetected media file: {file_name}")
                            print(f"Extracted title: {search_term}")

                            # Auto-detect content type based on improved logic
                            # First check if the containing directory has indicators
                            auto_content_type, is_anime = processor._detect_content_type_from_directory(file_dir)

                            # If not determined from directory, check the file itself
                            if auto_content_type is None:
                                # Check if file_info has media_type from extraction
                                if file_info.get('media_type') == 'tv':
                                    auto_content_type = 'tv'
                                else:
                                    auto_content_type = 'movie'
                                
                                # Default to movie for single files if we can't determine
                                if auto_content_type is None:
                                    auto_content_type = 'movie'
                            
                            # Convert auto_content_type to boolean flag
                            is_tv = auto_content_type == 'tv'
                            
                            # Content type display string
                            content_type_display = "TV Series" if is_tv and not is_anime else \
                                                 "Anime Series" if is_tv and is_anime else \
                                                 "Anime Movie" if not is_tv and is_anime else \
                                                 "Movie"

                            # Show content type selection menu with ability to change search term
                            while True:
                                content_type_result = self._show_content_type_menu(content_type_display, 
                                                                                   is_tv, 
                                                                                   is_anime, 
                                                                                   detected_name=search_term,
                                                                                   file_count=1)  # Always 1 for individual files
                                
                                # Check if user chose to change search term
                                if content_type_result == "CHANGE_SEARCH":
                                    # Clear screen and show ASCII art
                                    clear_screen()
                                    display_ascii_art()
                                    print("=" * 60)
                                    print("Change Search Term")
                                    print("=" * 60)
                                    
                                    # Show current search term and allow user to change it
                                    print(f"\nCurrent search term: {search_term}")
                                    new_term = input("Enter new search term (or press Enter to keep current): ").strip()
                                    
                                    if new_term:
                                        search_term = new_term
                                        print(f"Search term updated to: {search_term}")
                                        time.sleep(1)  # Brief pause to show message
                                        
                                    # Go back to content type menu with updated search term
                                    clear_screen()
                                    display_ascii_art()
                                    print("=" * 60)
                                    continue
                                else:
                                    # User made a content type choice or chose to skip/quit
                                    break

                            # Check if user chose to skip or quit
                            if content_type_result is None:
                                print("Skipping this item.")
                                input("\nPress Enter to continue...")
                                return
                            elif content_type_result == "QUIT":
                                return
                                
                            # Update content type based on user selection
                            is_tv, is_anime = content_type_result

                            # Clear screen and show ASCII art before searching TMDB
                            clear_screen()
                            display_ascii_art()
                            print("=" * 60)
                            print(f"Searching for: {search_term}")  # Use potentially updated search term
                            print("=" * 60)

                            # Search TMDB with updated flags, using potentially updated search term
                            tmdb_item = processor._match_title_to_tmdb(search_term, is_tv=is_tv, is_anime=is_anime)
                            
                            if tmdb_item == "EXIT":
                                return
                            
                            if tmdb_item is None:
                                print("Processing cancelled.")
                                input("\nPress Enter to continue...")
                                return
                            
                            # Make sure the anime flag is explicitly set in the TMDB item
                            tmdb_item['is_anime'] = is_anime
                            
                            # Clear screen and show ASCII art before processing
                            clear_screen()
                            display_ascii_art()
                            print("=" * 60)
                            
                            # Process based on selected content type
                            content_type = "tv" if "first_air_date" in tmdb_item else "movie"
                            
                            if content_type == "tv":
                                # For TV shows, we need to manually process since we only have one file
                                show_id = tmdb_item.get('id')
                                show_name = tmdb_item.get('name', 'Unknown')
                                first_air_date = tmdb_item.get('first_air_date', '').split('-')[0] if tmdb_item.get('first_air_date') else ''
                                
                                print(f"\nProcessing as TV show: {show_name} ({first_air_date})")
                                
                                processor._manually_process_tv_files([file_info], show_id, show_name, first_air_date)
                            else:
                                # For movies, we can reuse the process_movie method
                                print(f"\nProcessing as movie")
                                processor.process_movie('', [file_info], tmdb_item)
                        else:
                            print("This doesn't appear to be a supported media file.")
                            print("Supported extensions: " + ", ".join(processor.media_extensions['video']))
                        
                        break
                except Exception as e:
                    print(f"Error processing path: {e}")
                    self.logger.error(f"Error in new scan: {e}", exc_info=True)
                    input("\nPress Enter to try again...")
            else:
                try:
                    print(f"Invalid path: '{cleaned_path}'")
                    
                    # Second check - maybe there was a network issue or drive not mounted?
                    print("\nChecking if the path is a network mount or external drive...")
                    try:
                        # If it's a mount point that's not mounted
                        if os.path.ismount(os.path.dirname(cleaned_path)):
                            print(f"The parent path is a mount point. Please make sure it's properly mounted.")
                    except:
                        pass
                    
                    # Give helpful suggestions
                    print("\nPlease make sure:")
                    print("1. The path is entered correctly (case-sensitive)")
                    print("2. You have permission to access this location")
                    print("3. Network drives are properly mounted (if applicable)")
                    
                    # Allow manual entry as a fallback
                    retry = input("\nWould you like to retry with a different path? (y/N): ").strip().lower()
                    if retry != 'y':
                        break
                except Exception as e:
                    print(f"Error checking path: {e}")
                    self.logger.error(f"Error checking path: {e}", exc_info=True)
                    input("\nPress Enter to try again...")

    def multi_scan(self):
        """Scan multiple directories for media processing."""
        # Clear screen first
        clear_screen()
        
        # Display ASCII art at the top
        display_ascii_art()
        print("=" * 60)
        print("Multi Scan")
        print("=" * 60)
        
        print("\nThis feature allows you to scan multiple directories at once.")
        print("Enter one directory per line. When finished, enter a blank line.")
        print("Type 'c' to cancel at any time.")
        
        scan_paths = []
        
        # Collect multiple paths
        print("\nEnter directories to scan:")
        while True:
            path_input = input(f"{len(scan_paths) + 1}> ").strip()
            
            if path_input.lower() == 'c':
                return
            
            if not path_input:
                if scan_paths:  # If we have at least one path, break to start processing
                    break
                else:  # Otherwise, remind the user we need at least one path
                    print("Please enter at least one directory, or 'c' to cancel.")
                    continue
            
            # Clean the path
            cleaned_path = _clean_directory_path(path_input)
            
            # Validate the path
            if not os.path.exists(cleaned_path):
                print(f"Invalid path: '{cleaned_path}'")
                continue
                
            if not os.path.isdir(cleaned_path):
                print(f"Not a directory: '{cleaned_path}'")
                print("Only directories are supported in Multi Scan mode.")
                continue
                
            # Add valid path to our list
            scan_paths.append(cleaned_path)
            print(f"Added: {cleaned_path}")
        
        # If we have paths to process
        if scan_paths:
            # Show summary and confirm
            clear_screen()
            display_ascii_art()
            print("=" * 60)
            print(f"Ready to scan {len(scan_paths)} directories:")
            print("=" * 60)
            
            for i, path in enumerate(scan_paths, 1):
                print(f"{i}. {path}")
            
            # Ask if they want to use multiple destinations
            print("\nCurrent destination directory:")
            print(DESTINATION_DIRECTORY)
            use_multiple_destinations = input("\nUse multiple destinations? (y/N): ").strip().lower() == 'y'
            
            destination_dirs = []
            if use_multiple_destinations:
                # Get multiple destination directories
                clear_screen()
                display_ascii_art()
                print("=" * 60)
                print("Multiple Destinations")
                print("=" * 60)
                print("\nEnter destination directories (one per line).")
                print("When finished, enter a blank line.")
                
                # Collect destination paths, with the default as the first one
                destination_dirs.append(DESTINATION_DIRECTORY)
                print(f"1> {DESTINATION_DIRECTORY} (default)")
                
                while True:
                    dest_input = input(f"{len(destination_dirs) + 1}> ").strip()
                    
                    if not dest_input:
                        break
                    
                    # Clean and validate the destination path
                    dest_path = _clean_directory_path(dest_input)
                    
                    # Check if the directory exists, if not offer to create it
                    if not os.path.exists(dest_path):
                        create_dir = input(f"Directory doesn't exist: {dest_path}. Create it? (y/N): ").strip().lower()
                        if create_dir == 'y':
                            try:
                                os.makedirs(dest_path, exist_ok=True)
                                print(f"Created directory: {dest_path}")
                            except Exception as e:
                                print(f"Error creating directory: {e}")
                                continue
                        else:
                            print("Skipping this destination.")
                            continue
                    
                    # Test if we can write to this directory
                    if not os.access(dest_path, os.W_OK):
                        print(f"Warning: No write permissions to {dest_path}")
                        use_anyway = input("Use this destination anyway? (y/N): ").strip().lower()
                        if use_anyway != 'y':
                            continue
                    
                    destination_dirs.append(dest_path)
                    print(f"Added destination: {dest_path}")
                
                # If no additional destinations were added, use the default
                if len(destination_dirs) == 1:
                    print("\nNo additional destinations added. Using the default.")
                    use_multiple_destinations = False
            
            # Confirm final setup
            if use_multiple_destinations:
                clear_screen()
                display_ascii_art()
                print("=" * 60)
                print("Multi Scan Configuration")
                print("=" * 60)
                
                print("\nSources:")
                for i, path in enumerate(scan_paths, 1):
                    print(f"{i}. {path}")
                
                print("\nDestinations:")
                for i, path in enumerate(destination_dirs, 1):
                    print(f"{i}. {path}")
                
                confirm = input("\nProceed with scanning? (Y/n): ").strip().lower()
                if confirm == 'n':
                    return
            else:
                confirm = input("\nProceed with scanning? (Y/n): ").strip().lower()
                if confirm == 'n':
                    return
            
            # Process each path
            total_paths = len(scan_paths)
            for i, path in enumerate(scan_paths, 1):
                clear_screen()
                display_ascii_art()
                print("=" * 60)
                print(f"Processing directory {i}/{total_paths}: {path}")
                print("=" * 60)
                
                try:
                    # Save the initial scan info
                    save_scan_history(path)
                    
                    # If using multiple destinations, select one for this source
                    if use_multiple_destinations and len(destination_dirs) > 1:
                        print("\nSelect destination for this source:")
                        for j, dest in enumerate(destination_dirs, 1):
                            print(f"{j}. {dest}")
                        
                        while True:
                            dest_choice = input(f"\nSelect destination (1-{len(destination_dirs)}): ").strip()
                            if dest_choice.isdigit() and 1 <= int(dest_choice) <= len(destination_dirs):
                                selected_dest = destination_dirs[int(dest_choice) - 1]
                                # Temporarily override the global destination directory
                                original_dest = os.environ.get('DESTINATION_DIRECTORY')
                                os.environ['DESTINATION_DIRECTORY'] = selected_dest
                                print(f"\nUsing destination: {selected_dest}")
                                break
                            else:
                                print("Invalid choice.")
                    
                    # Create and use our DirectoryProcessor
                    processor = DirectoryProcessor(path)
                    processor.process()
                    
                    # Restore the original destination if we changed it
                    if use_multiple_destinations and len(destination_dirs) > 1:
                        os.environ['DESTINATION_DIRECTORY'] = original_dest
                    
                except Exception as e:
                    print(f"Error processing {path}: {e}")
                    self.logger.error(f"Error in multi scan for {path}: {e}", exc_info=True)
                    
                    # Ask if user wants to continue with next path
                    if i < total_paths:  # Only ask if there are more paths to process
                        choice = input("\nContinue with next directory? (Y/n): ").strip().lower()
                        if choice == 'n':
                            break
            
            # Final message
            print("\nMulti scan complete.")
            input("Press Enter to return to the main menu...")

    def _show_content_type_menu(self, detected_type, is_tv, is_anime, detected_name=None, file_count=None):
        """
        Show content type selection menu and return updated is_tv and is_anime values.
        
        Args:
            detected_type: The detected content type string
            is_tv: Current TV flag
            is_anime: Current anime flag
            detected_name: The detected/cleaned name of the content (optional)
            file_count: Number of media files (optional)
            
        Returns:
            Tuple of (is_tv, is_anime) potentially updated based on user selection,
            or None if the user wants to skip or quit
        """
        while True:  # Add a loop so we can show updated info after content type changes
            # Clear screen and redisplay content type info
            clear_screen()
            display_ascii_art()
            print("=" * 60)
            
            # Get the current content type display string
            content_type_display = "TV Series" if is_tv and not is_anime else \
                                  "Anime Series" if is_tv and is_anime else \
                                  "Anime Movie" if not is_tv and is_anime else \
                                  "Movie"
            
            print(f"Detected content type: {content_type_display}")
            
            # Show the detected name if provided
            if detected_name:
                print(f"Detected title: {detected_name}")
            
            # Show file count if provided
            if file_count is not None:
                print(f"Media files: {file_count}")
            
            # Show destination folder based on content type
            from dotenv import load_dotenv
            load_dotenv()
            
            # Get destination folder paths from environment variables
            if is_tv and is_anime:
                folder_name = os.getenv('CUSTOM_ANIME_SHOW_FOLDER', 'Anime Shows')
            elif is_tv and not is_anime:
                folder_name = os.getenv('CUSTOM_SHOW_FOLDER', 'TV Shows')
            elif not is_tv and is_anime:
                folder_name = os.getenv('CUSTOM_ANIME_MOVIE_FOLDER', 'Anime Movies')
            else:  # Movie
                folder_name = os.getenv('CUSTOM_MOVIE_FOLDER', 'Movies')
            
            # Show destination directory
            dest_dir = os.path.join(os.getenv('DESTINATION_DIRECTORY', ''), folder_name)
            print(f"Will be organized in: {dest_dir}")
            
            # Enhanced menu options
            print("\nOptions:")
            print("1. Continue with current content type (or press Enter)")
            print("2. Change content type")
            print("3. Change search term")
            print("s: Skip this item")
            print("q: Quit to main menu")
            
            choice = input("\nSelect option (1-3, 's' to skip, or 'q' to quit): ").strip().lower()
            
            # Default to option 1 (continue with current selection)
            if choice == "":
                choice = "1"
            
            if choice == "1":
                # Continue with current content type
                return (is_tv, is_anime)
            elif choice == "2":
                # Clear screen and show ASCII art before showing content type options
                clear_screen()
                display_ascii_art()
                print("=" * 60)
                print("Select Content Type")
                print("=" * 60)
                
                # Show content type options with destination paths
                print("\nSelect content type:")
                movie_folder = os.getenv('CUSTOM_MOVIE_FOLDER', 'Movies')
                tv_folder = os.getenv('CUSTOM_SHOW_FOLDER', 'TV Shows')
                anime_movie_folder = os.getenv('CUSTOM_ANIME_MOVIE_FOLDER', 'Anime Movies')
                anime_show_folder = os.getenv('CUSTOM_ANIME_SHOW_FOLDER', 'Anime Shows')
                
                print(f"1. Movie (→ {movie_folder})")
                print(f"2. TV Series (→ {tv_folder})")
                print(f"3. Anime Movie (→ {anime_movie_folder})")
                print(f"4. Anime Series (→ {anime_show_folder})")
                
                type_choice = input("\nSelect content type (1-4): ").strip()
                
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
                else:
                    print("\nInvalid choice. Keeping original content type.")
                
                # Don't return here - continue the loop to show updated info
                continue
            elif choice == "3":
                return "CHANGE_SEARCH"
            elif choice == "s":
                return None  # Special case for skip
            elif choice == "q":
                return "QUIT"  # Special case for quit
            else:
                # Invalid choice, keep original settings but stay in the loop
                print("\nInvalid choice. Keeping original content type.")
                time.sleep(1)
                continue

    def resume_scan(self):
        """Resume a previously interrupted scan."""
        # Clear screen first
        clear_screen()
        
        # Display ASCII art at the top
        display_ascii_art()
        
        # Add only a separator line
        print("=" * 60)
        
        history = load_scan_history()
        if not history:
            print("No valid scan history found.")
            input("\nPress Enter to continue...")
            return
        
        print(f"Resuming scan of {history['path']}")
        print(f"Previously processed {history.get('processed_files', 0)} of {history.get('total_files', 'unknown')} files\n")
        
        # Check if the directory still exists
        if not os.path.isdir(history['path']):
            print(f"Directory no longer exists: {history['path']}")
            input("\nPress Enter to continue...")
            return
            
        # Create a DirectoryProcessor with resume flag and process
        processor = DirectoryProcessor(history['path'], resume=True)
        processor.process()

    def settings_menu(self):
        """Display and modify application settings."""
        # Clear screen first
        clear_screen()
        
        # Display ASCII art at the top
        display_ascii_art()
        print("=" * 60)
        print("Settings")
        print("=" * 60)
        
        # Get current environment variables
        from dotenv import load_dotenv, set_key
        load_dotenv()
        
        # Define the path to the .env file
        env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')
        
        # Create the .env file if it doesn't exist
        if not os.path.exists(env_path):
            with open(env_path, 'w') as f:
                f.write("# Scanly Environment Configuration\n")
            print(f"Created new configuration file: {env_path}")
        
        # Dictionary of settings categories and their settings
        settings = {
            "Directory Settings": [
                {"name": "DESTINATION_DIRECTORY", "display": "Main Library Destination", 
                 "description": "Root directory where organized media will be placed"},
                {"name": "CUSTOM_MOVIE_FOLDER", "display": "Movies Folder Name", 
                 "description": "Folder name for regular movies", "default": "Movies"},
                {"name": "CUSTOM_SHOW_FOLDER", "display": "TV Shows Folder Name", 
                 "description": "Folder name for TV series", "default": "TV Shows"},
                {"name": "CUSTOM_ANIME_MOVIE_FOLDER", "display": "Anime Movies Folder Name", 
                 "description": "Folder name for anime movies", "default": "Anime Movies"},
                {"name": "CUSTOM_ANIME_SHOW_FOLDER", "display": "Anime Shows Folder Name", 
                 "description": "Folder name for anime series", "default": "Anime Shows"}
            ],
            "Linking Options": [
                {"name": "RELATIVE_SYMLINK", "display": "Use Relative Symlinks", 
                 "description": "Use relative instead of absolute paths in symlinks (useful for portable drives)",
                 "default": "false", "type": "boolean"}
            ],
            "Organization Options": [
                {"name": "MOVIE_RESOLUTION_STRUCTURE", "display": "Organize Movies by Resolution", 
                 "description": "Create subfolders for different video resolutions in Movies",
                 "default": "false", "type": "boolean"},
                {"name": "SHOW_RESOLUTION_STRUCTURE", "display": "Organize Shows by Resolution", 
                 "description": "Create subfolders for different video resolutions in TV Shows",
                 "default": "false", "type": "boolean"}
            ],
            "API Settings": [
                {"name": "TMDB_API_KEY", "display": "TMDB API Key", 
                 "description": "API key for The Movie Database",
                 "default": "3b5df02338c403dad189e661d57e351f"},
                {"name": "MDBLIST_API_KEY", "display": "MDBlist API Key", 
                 "description": "API key for MDBlist (used for content type detection)",
                 "default": ""}
            ],
            "MDBlist Settings": [
                {"name": "MDBLIST_ENABLED", "display": "Enable MDBlist Integration",
                 "description": "Use MDBlist for content type detection",
                 "default": "true", "type": "boolean"},
                {"name": "_MDBLIST_MANAGER", "display": "Manage MDBlist Configurations",
                 "description": "Add, edit, or remove MDBlist configurations",
                 "type": "custom_handler", "handler": "_manage_mdblist_configs"}
            ]
        }
        
        while True:
            # Clear screen for each view of the menu
            clear_screen()
            display_ascii_art()
            print("=" * 60)
            print("Settings")
            print("=" * 60)
            
            # Display settings categories
            print("\nSelect a settings category:")
            categories = list(settings.keys())
            for i, category in enumerate(categories, 1):
                print(f"{i}. {category}")
            
            print("\n0. Return to Main Menu")
            
            category_choice = input("\nEnter choice (0-{}): ".format(len(categories))).strip()
            
            if category_choice == '0':
                return
            
            # Check if the choice is valid
            if not category_choice.isdigit() or int(category_choice) < 1 or int(category_choice) > len(categories):
                print("Invalid choice.")
                input("\nPress Enter to continue...")
                continue
            
            # Get the selected category
            selected_category = categories[int(category_choice) - 1]
            category_settings = settings[selected_category]
            
            # Show settings for the selected category
            while True:
                clear_screen()
                display_ascii_art()
                print("=" * 60)
                print(f"Settings > {selected_category}")
                print("=" * 60)
                
                print("\nCurrent settings:")
                for i, setting in enumerate(category_settings, 1):
                    env_var = setting["name"]
                    default_value = setting.get("default", "")
                    current_value = os.environ.get(env_var, default_value)
                    
                    # Show a placeholder if the value is empty
                    display_value = current_value if current_value else "(not set)"
                    
                    # For boolean settings, make the display clearer
                    if setting.get("type") == "boolean":
                        display_value = "Enabled" if current_value.lower() == "true" else "Disabled"
                    
                    print(f"{i}. {setting['display']}: {display_value}")
                    print(f"   {setting['description']}")
                
                print("\n0. Back to Settings Menu")
                
                setting_choice = input("\nEnter setting number to modify (0 to go back): ").strip()
                
                if setting_choice == '0':
                    break
                
                # Check if the choice is valid
                if not setting_choice.isdigit() or int(setting_choice) < 1 or int(setting_choice) > len(category_settings):
                    print("Invalid choice.")
                    input("\nPress Enter to continue...")
                    continue
                
                # Get the selected setting
                selected_setting = category_settings[int(setting_choice) - 1]
                env_var = selected_setting["name"]
                default_value = selected_setting.get("default", "")
                current_value = os.environ.get(env_var, default_value)
                
                # Handle custom handlers
                if selected_setting.get("type") == "custom_handler" and "handler" in selected_setting:
                    handler_name = selected_setting["handler"]
                    if hasattr(self, handler_name):
                        # Call the custom handler method
                        getattr(self, handler_name)()
                    else:
                        print(f"\nError: Handler {handler_name} not found.")
                        input("\nPress Enter to continue...")
                    continue  # Skip the regular setting handling
                
                # Handle different types of settings
                if selected_setting.get("type") == "boolean":
                    # For boolean settings, toggle between true and false
                    new_value = "false" if current_value.lower() == "true" else "true"
                    print(f"\nToggling {selected_setting['display']} to: {new_value}")
                else:
                    # For directory settings, offer path selection
                    if "DIRECTORY" in env_var and env_var != "DESTINATION_DIRECTORY":
                        print("\nCurrent value: " + (current_value if current_value else "(not set)"))
                        new_value = input(f"Enter new value for {selected_setting['display']} (or press Enter to keep current): ").strip()
                        if not new_value:
                            new_value = current_value
                    elif env_var == "DESTINATION_DIRECTORY":
                        # For the main destination directory, offer more options
                        print("\nCurrent value: " + (current_value if current_value else "(not set)"))
                        print("\nOptions:")
                        print("1. Enter path manually")
                        print("2. Browse for folder")
                        print("3. Keep current value")
                        
                        browse_choice = input("\nEnter choice (1-3): ").strip()
                        
                        if browse_choice == '1':
                            new_value = input("Enter new path: ").strip()
                            new_value = _clean_directory_path(new_value)
                            
                            # Validate the path
                            if not os.path.exists(new_value):
                                create_dir = input(f"Directory doesn't exist: {new_value}. Create it? (y/N): ").strip().lower()
                                if create_dir == 'y':
                                    try:
                                        os.makedirs(new_value, exist_ok=True)
                                        print(f"Created directory: {new_value}")
                                    except Exception as e:
                                        print(f"Error creating directory: {e}")
                                        input("\nPress Enter to continue...")
                                        continue
                        elif browse_choice == '2':
                            print("\nNOTE: In terminal mode, you'll need to enter the path manually.")
                            print("For GUI environments, a file dialog would normally appear.")
                            
                            # Simplified directory selection for terminal interface
                            current_dir = current_value if current_value and os.path.exists(current_value) else os.path.expanduser("~")
                            
                            print(f"\nNavigating from: {current_dir}")
                            while True:
                                print("\nContents of current directory:")
                                dirs = [d for d in os.listdir(current_dir) if os.path.isdir(os.path.join(current_dir, d))]
                                
                                # Show parent directory option
                                print("0. Select this directory")
                                print("00. Go up to parent directory")
                                
                                # Show subdirectories
                                for i, d in enumerate(dirs, 1):
                                    print(f"{i}. {d}/")
                                
                                dir_choice = input("\nEnter choice (0=select current, 00=parent): ").strip()
                                
                                if dir_choice == '0':
                                    new_value = current_dir
                                    break
                                elif dir_choice == '00':
                                    current_dir = os.path.dirname(current_dir)
                                    continue
                                
                                if dir_choice.isdigit() and 1 <= int(dir_choice) <= len(dirs):
                                    current_dir = os.path.join(current_dir, dirs[int(dir_choice) - 1])
                                else:
                                    print("Invalid choice.")
                                    input("\nPress Enter to continue...")
                        else:
                            new_value = current_value
                    else:
                        # For other settings, simply prompt for a new value
                        print("\nCurrent value: " + (current_value if current_value else "(not set)"))
                        new_value = input(f"Enter new value for {selected_setting['display']} (or press Enter to keep current): ").strip()
                        if not new_value:
                            new_value = current_value
                
                # Save the updated setting to the .env file
                try:
                    if env_var and new_value is not None:
                        set_key(env_path, env_var, new_value)
                        os.environ[env_var] = new_value
                        print(f"\nSetting updated successfully.")
                        
                        # Special handling for DESTINATION_DIRECTORY
                        if env_var == "DESTINATION_DIRECTORY" and not os.path.exists(new_value):
                            try:
                                os.makedirs(new_value, exist_ok=True)
                                print(f"Created directory: {new_value}")
                            except Exception as e:
                                print(f"Warning: Could not create directory: {e}")
                except Exception as e:
                    print(f"\nError saving setting: {e}")
                
                input("\nPress Enter to continue...")

    def _manage_mdblist_configs(self):
        """Manage MDBlist configurations"""
        try:
            # Import the mdblist_handler
            from src.mdblist_handler import get_mdblist_handler
            mdblist_handler = get_mdblist_handler()
        except ImportError:
            print("\nMDBlist integration is not available.")
            print("Please ensure the mdblist_handler.py file is properly installed.\n")
            input("Press Enter to continue...")
            return
        
        # Create the data directory if it doesn't exist
        data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')
        os.makedirs(data_dir, exist_ok=True)
        
        while True:
            clear_screen()
            print("=" * 60)
            print("MDBlist Configuration Manager".center(60))
            print("=" * 60)
            
            # Get current API key
            api_key = os.environ.get('MDBLIST_API_KEY', '')
            if api_key:
                print(f"MDBlist API Key: {'*' * (len(api_key) - 4) + api_key[-4:]}")
            else:
                print("MDBlist API Key: Not set")
            
            # Display all list configs
            configs = mdblist_handler.get_list_configs()
            print("\nConfigured Lists:")
            if not configs:
                print("No lists configured yet.")
            else:
                for i, (name, config) in enumerate(configs.items(), 1):
                    status = "Enabled" if config.get('enabled', True) else "Disabled"
                    
                    # Map content type to readable format
                    content_type = config.get('content_type', 'unknown')
                    if content_type == 'anime_series':
                        content_type_display = "Anime Series"
                    elif content_type == 'anime_movies':
                        content_type_display = "Anime Movies"
                    elif content_type == 'tv_shows':
                        content_type_display = "TV Shows"
                    elif content_type == 'movies':
                        content_type_display = "Movies"
                    else:
                        content_type_display = content_type
                    
                    print(f"{i}. {name} - [{content_type_display}] - {status}")
                    print(f"   ID: {config.get('list_id', 'unknown')}")
            
            print("\nOptions:")
            print("1. Add new list")
            print("2. Remove list")
            print("3. Set MDBlist API Key")
            print("0. Back to settings")
            
            choice = input("\nEnter your choice: ")
            
            if choice == '0':
                break
            elif choice == '1':
                # Add new configuration
                clear_screen()
                print("=" * 60)
                print("Add MDBlist Configuration".center(60))
                print("=" * 60)
                
                name = input("\nEnter name for this configuration (e.g., 'Anime List'): ").strip()
                if not name:
                    print("Name cannot be empty")
                    input("\nPress Enter to continue...")
                    continue
                    
                list_id_or_url = input("Enter MDBlist URL or ID: ").strip()
                if not list_id_or_url:
                    print("MDBlist URL or ID cannot be empty")
                    input("\nPress Enter to continue...")
                    continue
                
                # Try to extract list ID from URL if needed
                list_id = mdblist_handler.extract_list_id_from_url(list_id_or_url)
                if not list_id:
                    print("Invalid MDBlist URL or ID")
                    input("\nPress Enter to continue...")
                    continue
                
                # Choose content type
                print("\nContent type this list identifies:")
                print("1. Anime Series")
                print("2. Anime Movies")
                print("3. TV Shows")
                print("4. Movies")
                
                type_choice = input("\nEnter choice (1-4): ").strip()
                
                if type_choice == "1":
                    content_type = "anime_series"
                elif type_choice == "2":
                    content_type = "anime_movies"
                elif type_choice == "3":
                    content_type = "tv_shows"
                elif type_choice == "4":
                    content_type = "movies"
                else:
                    print("Invalid choice")
                    input("\nPress Enter to continue...")
                    continue
                    
                enabled = input("Enable this configuration? (Y/n): ").strip().lower() != "n"
                
                # Add the configuration
                success = mdblist_handler.add_list(name, list_id, content_type, enabled)
                
                if success:
                    print(f"\nSuccessfully added configuration '{name}'")
                else:
                    print("\nFailed to add configuration")
                
                input("\nPress Enter to continue...")
                
            elif choice == '2':
                # Remove list
                if not configs:
                    print("No lists to remove.")
                    input("Press Enter to continue...")
                    continue
                    
                print("\nSelect a list to remove:")
                for i, name in enumerate(configs.keys(), 1):
                    print(f"{i}. {name}")
                
                remove_choice = input("\nEnter number (or 0 to cancel): ").strip()
                
                if remove_choice == '0':
                    continue
                    
                try:
                    remove_index = int(remove_choice) - 1
                    if 0 <= remove_index < len(configs):
                        list_name = list(configs.keys())[remove_index]
                        
                        # Confirm deletion
                        confirm = input(f"Are you sure you want to remove '{list_name}'? (y/N): ").strip().lower() == 'y'
                        
                        if confirm:
                            if mdblist_handler.delete_list(list_name):
                                print(f"Successfully removed list '{list_name}'")
                            else:
                                print(f"Failed to remove list '{list_name}'")
                    else:
                        print("Invalid selection")
                except ValueError:
                    print("Please enter a valid number")
                
                input("Press Enter to continue...")
                
            elif choice == '3':
                # Set API key
                new_api_key = input("Enter your MDBlist API key: ")
                if not new_api_key:
                    print("API key cannot be empty")
                    input("Press Enter to continue...")
                    continue
                    
                # Update the .env file
                env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')
                if os.path.exists(env_path):
                    with open(env_path, 'r') as f:
                        lines = f.readlines()
                    
                    # Check if MDBLIST_API_KEY is already in the file
                    api_key_found = False
                    with open(env_path, 'w') as f:
                        for line in lines:
                            if line.strip().startswith('MDBLIST_API_KEY='):
                                f.write(f'MDBLIST_API_KEY={new_api_key}\n')
                                api_key_found = True
                            else:
                                f.write(line)
                        
                        # Add the key if it wasn't found
                        if not api_key_found:
                            f.write(f'\nMDBLIST_API_KEY={new_api_key}\n')
                    
                    # Update the environment variable in the current process
                    os.environ['MDBLIST_API_KEY'] = new_api_key
                    mdblist_handler.api_key = new_api_key
                    
                    print("API key updated successfully")
                else:
                    print("Error: .env file not found")
                input("Press Enter to continue...")

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
            
            next_option = 3  # Start at 3 since we added Multi Scan as option 2
            
            if has_history:
                print(f"{next_option}. Resume Scan")
                print(f"{next_option+1}. Clear History")
                next_option += 2
            
            # Keep the skipped items count, but make it look like regular information
            if has_skipped:
                print(f"\nSkipped items: {len(skipped_items_registry)}")
                print(f"{next_option}. Review Skipped Items ({len(skipped_items_registry)})")
                next_option += 1
            
            # Add the Settings option
            print(f"{next_option}. Settings")
            next_option += 1
            
            print("0. Quit")
            print("h. Help")
            
            # Determine the valid choices
            max_choice = next_option - 1
            
            choice = input(f"\nEnter choice (0-{max_choice}, h): ").strip().lower()
            
            # Handle menu choices
            if choice == '1':
                clear_screen()
                self.individual_scan()  # Renamed from new_scan
            elif choice == '2':
                clear_screen()
                self.multi_scan()  # New multi scan function
            elif choice == '3' and has_history:
                clear_screen()
                self.resume_scan()
            elif choice == '4' and has_history:
                # Clear both scan history and skipped items registry
                clear_scan_history()
                
                # We already declared global above, no need to repeat
                globals()['skipped_items_registry'] = []
                save_skipped_items([])
                
                print("Scan history and skipped items cleared.")
                input("\nPress Enter to continue...")
            # Fix the condition to properly check skipped items
            elif (has_skipped and ((has_history and choice == '5') or (not has_history and choice == '3'))):
                clear_screen()
                review_skipped_items()
            # Add the settings menu option
            elif (has_history and has_skipped and choice == '6') or \
                 (has_history and not has_skipped and choice == '5') or \
                 (not has_history and has_skipped and choice == '4') or \
                 (not has_history and not has_skipped and choice == '3'):
                clear_screen()
                self.settings_menu()
            elif choice == '0':
                clear_screen()
                break
            elif choice == 'h':
                display_help()
            else:
                print("Invalid choice. Please try again.")
                input("\nPress Enter to continue...")

def main():
    """Main entry point for the application."""
    # Set up logging with file level INFO, but console level WARNING
    setup_logging(log_level=logging.INFO, console_level=logging.WARNING)
    
    # Get logger only after setup
    logger = logging.getLogger(__name__)
    logger.info("Starting Scanly")  # This will be logged to file but not shown in console
    
    try:
        if not os.path.exists(DESTINATION_DIRECTORY):
            logger.warning(f"Destination directory doesn't exist: {DESTINATION_DIRECTORY}")
            print(f"Warning: Destination directory doesn't exist: {DESTINATION_DIRECTORY}")
            print("Symlinks will not be created during this session.")

        # Clear screen before showing welcome message
        clear_screen()
        display_ascii_art()
        print("=" * 60)

        try:
            MainMenu().show()
        except KeyboardInterrupt:
            logger.info("Operation cancelled by user (KeyboardInterrupt)")
            print("\nOperation cancelled by user.")
        except Exception as e:
            logger.exception(f"Unexpected error in main menu: {e}")
            print(f"\nAn unexpected error occurred: {e}")
        
        logger.info("Scanly shutdown normally")
        
    except Exception as e:
        # Logging setup failed
        print(f"Error setting up application: {e}")
        # Try to log to stderr if logging setup failed
        import sys
        import traceback
        traceback.print_exc(file=sys.stderr)

if __name__ == "__main__":
    main()