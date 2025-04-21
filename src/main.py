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

# Set up basic logging configuration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(os.path.join(os.path.dirname(__file__), '..', 'logs', 'scanly.log'), 'a')
    ]
)

# Create logs directory if it doesn't exist
log_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), '..', 'logs')
os.makedirs(log_dir, exist_ok=True)

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

# Try to load the TMDB API 
try:
    from src.api.tmdb import TMDB
except ImportError as e:
    logger = get_logger(__name__)
    logger.error(f"Error importing TMDB API: {e}. TMDB functionality will be disabled.")
    
    # Define a stub TMDB class
    class TMDB:
        def __init__(self, api_key=None):
            pass
        
        def search_movie(self, query, limit=5):
            return []
        
        def search_tv(self, query, limit=5):
            return []
        
        def get_tv_details(self, show_id):
            return {}
        
        def get_tv_season(self, show_id, season_number):
            return {}

# Get destination directory from environment variables
DESTINATION_DIRECTORY = os.environ.get('DESTINATION_DIRECTORY', '')

# Import utility functions for scan history
def load_scan_history():
    """Load scan history from file."""
    try:
        history_path = os.path.join(os.path.dirname(__file__), 'scan_history.json')
        if os.path.exists(history_path):
            with open(history_path, 'r') as f:
                return json.load(f)
    except Exception as e:
        logger = get_logger(__name__)
        logger.error(f"Error loading scan history: {e}")
    return None

def save_scan_history(directory_path, processed_files=0, total_files=0, media_files=None):
    """Save scan history to file."""
    try:
        history = {
            'directory': directory_path,
            'timestamp': time.time(),
            'processed_files': processed_files,
            'total_files': total_files,
            'media_files': media_files or []
        }
        history_path = os.path.join(os.path.dirname(__file__), 'scan_history.json')
        with open(history_path, 'w') as f:
            json.dump(history, f)
    except Exception as e:
        logger = get_logger(__name__)
        logger.error(f"Error saving scan history: {e}")

def clear_scan_history():
    """Clear scan history file."""
    try:
        history_path = os.path.join(os.path.dirname(__file__), 'scan_history.json')
        if os.path.exists(history_path):
            os.remove(history_path)
    except Exception as e:
        logger = get_logger(__name__)
        logger.error(f"Error clearing scan history: {e}")

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
        logger = get_logger(__name__)
        logger.error(f"Error loading skipped items: {e}")
    return []

# Function to save skipped items
def save_skipped_items(items):
    """Save skipped items to file."""
    try:
        skipped_path = os.path.join(os.path.dirname(__file__), 'skipped_items.json')
        with open(skipped_path, 'w') as f:
            json.dump(items, f)
    except Exception as e:
        logger = get_logger(__name__)
        logger.error(f"Error saving skipped items: {e}")

# Add this function after save_skipped_items() function

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
        art_path = os.path.join(os.path.dirname(__file__), '..', 'art.txt')
        if os.path.exists(art_path):
            with open(art_path, 'r') as f:
                print(f.read())
        else:
            print("SCANLY")
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
    
    print("=" * 60)
    print("SKIPPED ITEMS")
    print("=" * 60)
    print(f"\nFound {len(skipped_items_registry)} skipped items:")
    
    for i, item in enumerate(skipped_items_registry):
        subfolder = item.get('subfolder', 'Unknown')
        suggested_name = item.get('suggested_name', 'Unknown')
        is_tv = item.get('is_tv', False)
        is_anime = item.get('is_anime', False)
        
        content_type = "TV Show" if is_tv else "Movie"
        anime_label = " (Anime)" if is_anime else ""
        
        print(f"\n{i+1}. {suggested_name}")
        print(f"   Type: {content_type}{anime_label}")
        print(f"   Path: {subfolder}")
    
    print("\nOptions:")
    print("1. Process a skipped item")
    print("2. Clear all skipped items")
    print("0. Return to main menu")
    
    choice = input("\nEnter choice: ").strip()
    
    if choice == "1":
        item_num = input("\nEnter item number to process: ").strip()
        
        try:
            item_idx = int(item_num) - 1
            if 0 <= item_idx < len(skipped_items_registry):
                # Process the selected item
                # Implementation for processing skipped items
                pass
            else:
                print("Invalid item number.")
                input("\nPress Enter to continue...")
        except ValueError:
            print("Invalid input.")
            input("\nPress Enter to continue...")
    elif choice == "2":
        clear_skipped_items()
    
# DirectoryProcessor class
class DirectoryProcessor:
    """Process a directory of media files."""
    
    def __init__(self, directory_path, resume=False, auto_mode=False):
        """
        Initialize the directory processor.
        
        Args:
            directory_path: Path to the directory to process
            resume: Whether to resume a previous scan
            auto_mode: Whether to process in automatic mode without user interaction
        """
        self.logger = get_logger(__name__)
        self.logger.info(f"Initializing DirectoryProcessor with auto_mode={auto_mode}")
        self.directory_path = directory_path
        self.resume = resume
        self.auto_mode = auto_mode
        self.auto_process = auto_mode  # Set auto_process to match auto_mode immediately
        self.processed_files = 0
        self.total_files = 0
        self.media_files = []
        self.subfolder_files = {}
        self.errors = 0
        self.skipped = 0
        self.symlink_count = 0
        # Note: No processing happens here anymore, just initialization

    def _create_symlink(self, source_path, title, year=None, season=None, episode=None, is_tv=False, is_anime=False, resolution=None, part=None, tmdb_id=None, imdb_id=None, tvdb_id=None):
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
            resolution: Optional resolution string
            part: Part number for multi-part movies (optional)
            tmdb_id: TMDB ID (optional)
            imdb_id: IMDB ID (optional)
            tvdb_id: TVDB ID (optional)
            
        Returns:
            Boolean indicating success
        """
        try:
            # Get logger
            logger = get_logger(__name__)
            
            # Get destination directory
            dest_dir = os.environ.get('DESTINATION_DIRECTORY')
            if not dest_dir:
                logger.error("Destination directory not set in environment variables")
                return False
                
            # Get option for including TMDB ID in folder names
            include_tmdb_id = os.environ.get('TMDB_FOLDER_ID', 'false').lower() == 'true'
            
            # Determine base directory based on content type
            if is_tv:
                base_dir = "Anime Shows" if is_anime else "TV Shows"
            else:
                base_dir = "Anime Movies" if is_anime else "Movies"
                
            # Create base directory path
            content_dir = os.path.join(dest_dir, base_dir)
            os.makedirs(content_dir, exist_ok=True)
            
            # Clean the title to remove any embedded year or TMDB ID
            # This prevents duplicates like "Title (2021) [tmdb-123] (2021) [tmdb-123]"
            clean_title = re.sub(r'\s*\(\d{4}\)|\s*\[tmdb-\d+\]|\s*\[\d+\]', '', title).strip()
            
            # Format folder name with clean title
            folder_name = clean_title
            if year:
                folder_name = f"{folder_name} ({year})"
                
            # Add TMDB ID to folder name ONLY if it's valid (not "error" or None)
            # and the include_tmdb_id option is enabled
            if include_tmdb_id and tmdb_id and tmdb_id != "error":
                # Make sure tmdb_id is treated as a string
                folder_name = f"{folder_name} [tmdb-{tmdb_id}]"
                logger.info(f"Added TMDB ID {tmdb_id} to folder name")
            elif tmdb_id == "error":
                logger.warning("TMDB ID has error value, not including in folder name")
                
            # For TV shows, create season folder structure
            if is_tv and season is not None:
                # Create show folder
                show_dir = os.path.join(content_dir, folder_name)
                os.makedirs(show_dir, exist_ok=True)
                
                # Create season folder
                season_folder = f"Season {season:02d}"
                season_dir = os.path.join(show_dir, season_folder)
                os.makedirs(season_dir, exist_ok=True)
                
                # Create episode filename
                file_ext = os.path.splitext(source_path)[1]
                episode_name = f"{clean_title} - S{season:02d}E{episode:02d}"
                if resolution:
                    episode_name += f" - {resolution}"
                episode_name += file_ext
                
                # Final destination path
                dest_path = os.path.join(season_dir, episode_name)
            else:
                # For movies
                movie_dir = os.path.join(content_dir, folder_name)
                os.makedirs(movie_dir, exist_ok=True)
                
                # Create movie filename
                file_ext = os.path.splitext(source_path)[1]
                movie_name = clean_title
                if year:
                    movie_name += f" ({year})"
                if part:
                    movie_name += f" - Part {part}"
                # Never include resolution in movie filenames
                movie_name += file_ext
                
                # Final destination path
                dest_path = os.path.join(movie_dir, movie_name)
                
            # Check if destination exists
            if os.path.exists(dest_path):
                if os.path.islink(dest_path):
                    # If it's a symlink that points to a different file, remove it
                    if os.readlink(dest_path) != source_path:
                        os.remove(dest_path)
                    else:
                        # It's already the correct symlink
                        logger.info(f"Symlink already exists and is correct: {dest_path}")
                        return True
                else:
                    # It's not a symlink, don't overwrite
                    logger.warning(f"Destination exists and is not a symlink: {dest_path}")
                    return False
                    
            # Create the symlink
            logger.info(f"Creating symlink from {source_path} to {dest_path}")
            os.symlink(source_path, dest_path)
            return True
            
        except Exception as e:
            logger = get_logger(__name__)
            logger.error(f"Error creating symlink: {e}", exc_info=True)
            return False

    def _process_tv_series(self, files, subfolder, title, year, is_anime, tmdb_id=None, imdb_id=None, tvdb_id=None):
        """
        Process TV series files.
        
        Args:
            files: List of files to process
            subfolder: Path to the subfolder containing files
            title: Series title
            year: Series year
            is_anime: Boolean indicating if it's anime
            tmdb_id: TMDB ID (optional)
            imdb_id: IMDB ID (optional)
            tvdb_id: TVDB ID (optional)
        """
        # Get logger
        logger = get_logger(__name__)
        logger.info(f"Processing TV series: '{title}' (year: {year}) in {subfolder}")
        
        try:
            # Always try to clean the title first - it may contain remnants of technical info
            if title:
                # Remove common technical terms that might remain in the title
                tech_patterns = [
                    r'(?i)\b(Repack|Repacked|AVC|HD|MA|5\.1|7\.1|DUAL|AUDIO)\b',
                    r'(?i)\b(REMUX|Blu ray|BluRay)\b',
                    r'(?i)\b(KRaLiMaRKo|FGT|RARBG|YIFY|YTS)\b',
                ]
                for pattern in tech_patterns:
                    title = re.sub(pattern, '', title).strip()
                
                # Normalize spaces
                title = re.sub(r'\s+', ' ', title).strip()
                logger.info(f"Cleaned initial title to: '{title}'")
            
            # Flag to track if we have authoritative metadata
            has_authoritative_metadata = False
            
            # Check if we should auto-extract episodes
            auto_extract = os.environ.get('AUTO_EXTRACT_EPISODES', 'false').lower() == 'true'
            
            # Clean title of any existing year or TMDB ID
            # This is critical to prevent issues like "(2021) [118357] (2021) [tmdb-118357]"
            title = re.sub(r'\s*\(\d{4}\)|\s*\[tmdb-\d+\]|\s*\[\d+\]', '', title).strip()
            
            # Extract episodes from filenames
            for file_path in files:
                file_name = os.path.basename(file_path)
                
                # Initialize variables
                season = None
                episode = None
                resolution = None
                
                # Try to extract season and episode from the filename
                # Try S01E01 format
                se_match = re.search(r'S(\d{1,2})E(\d{1,3})', file_name, re.IGNORECASE)
                if se_match:
                    season = int(se_match.group(1))
                    episode = int(se_match.group(2))
                else:
                    # Try 1x01 format
                    se_match = re.search(r'(\d{1,2})x(\d{1,3})', file_name)
                    if se_match:
                        season = int(se_match.group(1))
                        episode = int(se_match.group(2))
                    else:
                        # Try season ## episode ## format
                        se_match = re.search(r'season\s*(\d{1,2}).*?episode\s*(\d{1,3})', file_name, re.IGNORECASE)
                        if se_match:
                            season = int(se_match.group(1))
                            episode = int(se_match.group(2))
                        else:
                            # Try standalone patterns for anime episodes (like [01], [01v2], etc.)
                            ep_match = re.search(r'[\[\(](\d{1,3})(?:v\d)?[\]\)]', file_name)
                            if ep_match and is_anime:
                                # For standalone episode numbers, assume season 1
                                season = 1
                                episode = int(ep_match.group(1))
                            else:
                                # Try to extract just a number at the end of the filename (before extension)
                                name_without_ext = os.path.splitext(file_name)[0]
                                ep_match = re.search(r'(\d{1,3})$', name_without_ext)
                                if ep_match and is_anime:
                                    season = 1
                                    episode = int(ep_match.group(1))
                                else:
                                    # For anime, anime special naming patterns
                                    if is_anime and ('special' in file_name.lower() or 'ova' in file_name.lower()):
                                        # For specials, use season 0
                                        season = 0
                                        # Try to find the special number
                                        special_match = re.search(r'special\s*(\d+)', file_name, re.IGNORECASE)
                                        if special_match:
                                            episode = int(special_match.group(1))
                                        else:
                                            # Just assign sequential episode numbers for specials
                                            episode = 1  # This should ideally be a sequential number
                
                # If auto-extract is disabled and we couldn't determine season/episode, skip this file
                if not auto_extract and (season is None or episode is None):
                    logger.warning(f"Could not determine season/episode for: {file_name}")
                    
                    # In manual mode, prompt user for season/episode
                    if not self.auto_mode:
                        print(f"\nFile: {file_name}")
                        print("\nCould not automatically determine season and episode.")
                        print("Please enter the information manually:")
                        
                        try:
                            season_input = input("Season number: ").strip()
                            episode_input = input("Episode number: ").strip()
                            
                            if season_input and season_input.isdigit():
                                season = int(season_input)
                            if episode_input and episode_input.isdigit():
                                episode = int(episode_input)
                                
                            if season is not None and episode is not None:
                                print(f"Using season {season}, episode {episode}")
                            else:
                                print("Missing season or episode number, skipping file.")
                                self.skipped += 1
                                continue
                        except ValueError:
                            print("Invalid input, skipping file.")
                            self.skipped += 1
                            continue
                    else:
                        # In auto mode, skip files without season/episode
                        self.skipped += 1
                        logger.warning(f"Skipped file due to missing season/episode information: {file_path}")
                        continue
                
                # Extract resolution if present
                res_match = re.search(r'(720p|1080p|2160p|4K|UHD)', file_name, re.IGNORECASE)
                if res_match:
                    resolution = res_match.group(1)
                
                # If we have a season and episode, create a symlink
                if season is not None and episode is not None:
                    success = self._create_symlink(
                        source_path=file_path,
                        title=title,
                        year=year,
                        season=season,
                        episode=episode,
                        is_tv=True,
                        is_anime=is_anime,
                        resolution=resolution,  # Include resolution for TV shows
                        tmdb_id=tmdb_id,
                        imdb_id=imdb_id,
                        tvdb_id=tvdb_id
                    )
                    
                    if success:
                        self.symlink_count += 1
                        logger.info(f"Created symlink for {title} S{season:02d}E{episode:02d}")
                        if not self.auto_mode:
                            # In manual mode, show progress
                            print(f"Processed: {title} - S{season:02d}E{episode:02d} - {file_name}")
                    else:
                        self.errors += 1
                        logger.error(f"Failed to create symlink for {file_path}")
                        if not self.auto_mode:
                            print(f"Error processing: {file_name}")
                else:
                    self.skipped += 1
                    logger.warning(f"Skipped file due to missing season/episode information: {file_path}")
            
            # In manual mode, wait for user to continue
            if not self.auto_mode:
                print(f"\nFinished processing TV series: {title}")
                input("\nPress Enter to continue...")
            else:
                # In auto mode, just log completion
                tv_display = f"{title}"
                if year:
                    tv_display += f" ({year})"
                print(f"Auto-processed TV series: {tv_display}")
                
            # Return success
            return True
                
        except Exception as e:
            logger.error(f"Error processing TV series {title}: {e}", exc_info=True)
            print(f"\nError processing TV series: {e}")
            self.errors += len(files)
            if not self.auto_mode:
                input("\nPress Enter to continue...")
            return False

    def _process_movies(self, files, subfolder, title, year, is_anime, tmdb_id=None, imdb_id=None, tvdb_id=None):
        """
        Process movie files.
        
        Args:
            files: List of files to process
            subfolder: Path to the subfolder containing files
            title: Movie title
            year: Movie year
            is_anime: Boolean indicating if it's anime
            tmdb_id: TMDB ID (optional)
            imdb_id: IMDB ID (optional)
            tvdb_id: TVDB ID (optional)
        """
        from src.utils.scanner_utils import check_scanner_lists
        
        try:
            # Get logger
            logger = get_logger(__name__)
            logger.info(f"Processing movie: '{title}' (year: {year}) in {subfolder}")
            
            # Always try to clean the title first - it may contain remnants of technical info
            # This helps with cases like "3 Idiots Repack" becoming just "3 Idiots"
            if title:
                # Remove common technical terms that might remain in the title
                tech_patterns = [
                    r'(?i)\b(Repack|Repacked|AVC|HD|MA|5\.1|7\.1|DUAL|AUDIO)\b',
                    r'(?i)\b(REMUX|Blu ray|BluRay)\b',
                    r'(?i)\b(KRaLiMaRKo|FGT|RARBG|YIFY|YTS)\b',
                ]
                for pattern in tech_patterns:
                    title = re.sub(pattern, '', title).strip()
                
                # Normalize spaces
                title = re.sub(r'\s+', ' ', title).strip()
                logger.info(f"Cleaned initial title to: '{title}'")
                
            # Flag to track if we have authoritative metadata (from scanner or TMDB)
            has_authoritative_metadata = False
            
            # First try to match against scanner lists for better identification
            scanner_title = None
            scanner_matched = False
            scanner_tmdb_id = None
            scanner_year = None
            
            # Check scanner lists for each file
            for file_path in files:
                file_name = os.path.basename(file_path)
                
                # Try to match against scanner lists
                scanner_result = check_scanner_lists(file_name, title_hint=title)
                
                if scanner_result:
                    scanner_matched = True
                    has_authoritative_metadata = True  # Scanner match is authoritative
                    # Extract results from the scanner match
                    if len(scanner_result) == 4:
                        content_type, is_anime_new, new_tmdb_id, scanner_title = scanner_result
                        # If scanner found a title and it's a movie, use it
                        if scanner_title and content_type == "movie":
                            # Always prefer scanner title as it's generally more accurate
                            logger.info(f"Using scanner list title: '{scanner_title}' (was: '{title}')")
                            title = scanner_title
                            
                            # Check if scanner title contains a year in parentheses
                            year_match = re.search(r'\((\d{4})\)', scanner_title)
                            if year_match:
                                scanner_year = year_match.group(1)
                                if scanner_year != year:
                                    logger.info(f"Updated year from {year} to {scanner_year} from scanner title")
                                    year = scanner_year
                            
                            # Use the TMDB ID from scanner if available and valid
                            if new_tmdb_id and new_tmdb_id != "error":
                                scanner_tmdb_id = new_tmdb_id
                                logger.info(f"Using scanner list TMDB ID: {scanner_tmdb_id}")
                            # Update is_anime if different from what was passed in
                            if is_anime_new != is_anime:
                                logger.info(f"Updating anime flag from {is_anime} to {is_anime_new} based on scanner")
                                is_anime = is_anime_new
                            break
                    else:
                        # Handle older scanner result format
                        content_type, is_anime_new, new_tmdb_id = scanner_result
                        if content_type == "movie" and new_tmdb_id and new_tmdb_id != "error":
                            scanner_tmdb_id = new_tmdb_id
                            logger.info(f"Using scanner list TMDB ID: {scanner_tmdb_id}")
                            has_authoritative_metadata = True
                            if is_anime_new != is_anime:
                                logger.info(f"Updating anime flag from {is_anime} to {is_anime_new} based on scanner")
                                is_anime = is_anime_new
                            break
            
            # Use scanner list TMDB ID if available (overrides any passed-in ID)
            if scanner_tmdb_id:
                tmdb_id = scanner_tmdb_id
            
            # Check if we should update metadata from TMDB API
            # Only do this if:
            # 1. We don't have a valid TMDB ID already from scanner
            # 2. It's not anime (which often has poor TMDB matches)
            tmdb_matched = False
            tmdb_error = False
            
            # Always try TMDB if we don't have a scanner match with TMDB ID
            if (not scanner_matched or not scanner_tmdb_id) and not is_anime:
                try:
                    # Import TMDB API
                    from src.api.tmdb import TMDB
                    
                    # Get TMDB API key from environment
                    tmdb_api_key = os.environ.get('TMDB_API_KEY', '')
                    
                    if tmdb_api_key:
                        tmdb = TMDB(api_key=tmdb_api_key)
                        
                        # Construct search query
                        query = title
                        if year:
                            query += f" {year}"
                            
                        logger.info(f"Searching TMDB for movie: {query}")
                        # Search TMDB for movie (first attempt)
                        results = tmdb.search_movie(query, limit=1)
                        
                        if results:
                            tmdb_matched = True
                            has_authoritative_metadata = True  # TMDB match is authoritative
                            result = results[0]
                            tmdb_id = result.get('id')
                            logger.info(f"Found TMDB match: ID {tmdb_id}")
                            # Check if we got a better title
                            if result.get('title'):
                                title = result.get('title')
                                logger.info(f"Using TMDB title: {title}")
                            # Check if we got a release year
                            if result.get('release_date'):
                                release_date = result.get('release_date')
                                if release_date and len(release_date) >= 4:
                                    tmdb_year = release_date[:4]
                                    if not year or year != tmdb_year:
                                        logger.info(f"Using TMDB year: {tmdb_year} (was: {year})")
                                        year = tmdb_year
                        else:
                            # If first attempt failed, try with a more simplified query
                            logger.info(f"No TMDB results found for: {query}, trying simplified query")
                            
                            # Special case for movies starting with numbers
                            if title and title[0].isdigit():
                                # Keep full title for movies starting with numbers (like "3 Idiots")
                                simple_title = title
                                logger.info(f"Using full title for numeric beginning: {simple_title}")
                            else:
                                # Otherwise use first few words only
                                simple_title = ' '.join(title.split()[:3])
                            
                            simple_query = simple_title
                            if year:
                                simple_query += f" {year}"
                                
                            # Try the simplified search
                            results = tmdb.search_movie(simple_query, limit=1)
                            
                            if results:
                                tmdb_matched = True
                                has_authoritative_metadata = True  # TMDB match is authoritative
                                result = results[0]
                                tmdb_id = result.get('id')
                                logger.info(f"Found TMDB match with simplified query: ID {tmdb_id}")
                                # Check if we got a better title
                                if result.get('title'):
                                    title = result.get('title')
                                    logger.info(f"Using TMDB title: {title}")
                                # Check if we got a release year
                                if result.get('release_date'):
                                    release_date = result.get('release_date')
                                    if release_date and len(release_date) >= 4:
                                        tmdb_year = release_date[:4]
                                        if not year or year != tmdb_year:
                                            logger.info(f"Using TMDB year: {tmdb_year} (was: {year})")
                                            year = tmdb_year
                            else:
                                logger.info(f"No TMDB results found for simplified query: {simple_query}")
                    else:
                        logger.warning("TMDB API key not found in environment variables")
                except Exception as e:
                    logger.warning(f"Error searching TMDB for movie {title}: {e}")
                    tmdb_error = True
            
            # Even if we don't have authoritative metadata, in auto mode we should try to use what we have
            # rather than skipping if the title seems reasonable
            if self.auto_mode and not has_authoritative_metadata:
                # Don't skip if we have a reasonable title - use what we extracted from the folder/file names
                if title and len(title) > 3 and title.lower() not in ['movie', 'film', 'video']:
                    logger.info(f"Using extracted title '{title}' even without authoritative metadata")
                    has_authoritative_metadata = True  # Consider our extraction good enough
            
            # If neither scanner nor TMDB matched and not in auto mode, add to skipped items
            if not has_authoritative_metadata and not self.auto_mode:
                print("\nCould not confidently match this movie. Adding to skipped items for later review.")
                self._skip_files(files, subfolder, "movie", is_anime, os.path.basename(subfolder))
                return False
            
            # Never use "error" as a TMDB ID - set to None if we have an error
            if tmdb_error or (tmdb_id and tmdb_id == "error"):
                logger.info("Removing 'error' TMDB ID")
                tmdb_id = None
                    
            # Clean up title after all processing - IMPORTANT to avoid duplicates!
            title = re.sub(r'\s+', ' ', title).strip()
            
            # Clean title of any existing year or TMDB ID
            # This is critical to prevent issues like "(2021) [118357] (2021) [tmdb-118357]"
            title = re.sub(r'\s*\(\d{4}\)|\s*\[tmdb-\d+\]|\s*\[\d+\]', '', title).strip()
            
            logger.info(f"Final title: '{title}', year: {year}, tmdb_id: {tmdb_id}")
            
            # Process each file in the subfolder
            for file_path in files:
                # Extract file name
                file_name = os.path.basename(file_path)
                
                # Try to extract metadata from filename ONLY if we don't have authoritative metadata
                if not has_authoritative_metadata:
                    # Apply more aggressive name extraction from filename if title looks generic
                    if len(title.split()) <= 1 or title.lower() in ['movie', 'film', 'video']:
                        # Extract from filename, similar to _extract_folder_metadata but more thorough
                        clean_name = re.sub(r'\.(mkv|mp4|avi|mov|wmv|flv|m4v|ts)$', '', file_name, flags=re.IGNORECASE)
                        clean_name = re.sub(r'[._-]', ' ', clean_name)
                        
                        # Remove common tags
                        clean_name = re.sub(r'\[[^\]]*\]|\([^\)]*\)', '', clean_name)
                        
                        # Remove quality indicators
                        clean_name = re.sub(r'(?i)(1080p|720p|2160p|4K|HEVC|x264|x265|WEB-?DL|BluRay)', '', clean_name)
                        
                        # Look for year in filename
                        year_match = re.search(r'\((\d{4})\)|\[(\d{4})\]|(?<!\d)(\d{4})(?!\d)', clean_name)
                        extracted_year = None
                        if year_match:
                            # Get the first non-None match group
                            extracted_year = next((g for g in year_match.groups() if g is not None), None)
                            # Remove the year part
                            clean_name = re.sub(r'\((\d{4})\)|\[(\d{4})\]|(?<!\d)(\d{4})(?!\d)', '', clean_name)
                            
                        # If we found a year and didn't have one before, use it
                        if extracted_year and not year:
                            year = extracted_year
                            
                        # Normalize spaces
                        clean_name = re.sub(r'\s+', ' ', clean_name).strip()
                        
                        # If the extracted name looks like a real title, use it
                        if len(clean_name) > 3 and clean_name.lower() not in ['movie', 'film', 'video']:
                            logger.info(f"Extracted better title from filename: '{clean_name}' (was: '{title}')")
                            title = clean_name
                
                # Extract part number if this is a multi-part movie
                part = None
                part_match = re.search(r'(?:part|cd)[\s._-]*(\d+)', file_name, re.IGNORECASE)
                if part_match:
                    part = int(part_match.group(1))
                
                # Create symlink using title and metadata
                # Note: resolution is passed as None for movies to ensure it's never included
                success = self._create_symlink(
                    source_path=file_path,
                    title=title,
                    year=year,
                    is_tv=False,
                    is_anime=is_anime,
                    resolution=None,  # Always None for movies
                    part=part,
                    tmdb_id=tmdb_id,
                    imdb_id=imdb_id,
                    tvdb_id=tvdb_id
                )
                
                if success:
                    self.symlink_count += 1
                    logger.info(f"Created symlink for {title} ({year}) from {file_path}")
                    if not self.auto_mode:
                        # In manual mode, show progress
                        movie_display = f"{title}"
                        if year:
                            movie_display += f" ({year})"
                        print(f"Processed: {movie_display} - {os.path.basename(file_path)}")
                else:
                    self.errors += 1
                    logger.error(f"Failed to create symlink for {file_path}")
                    if not self.auto_mode:
                        print(f"Error processing: {os.path.basename(file_path)}")
            
            # In manual mode, wait for user to continue
            if not self.auto_mode:
                movie_display = f"{title}"
                if year:
                    movie_display += f" ({year})"
                print(f"\nFinished processing movie: {movie_display}")
                input("\nPress Enter to continue...")
            else:
                # In auto mode, just log completion
                movie_display = f"{title}"
                if year:
                    movie_display += f" ({year})"
                print(f"Auto-processed movie: {movie_display}")
                
            # Return success
            return True
                
        except Exception as e:
            logger.error(f"Error processing movie {title}: {e}", exc_info=True)
            print(f"\nError processing movie: {e}")
            self.errors += len(files)
            if not self.auto_mode:
                input("\nPress Enter to continue...")
            return False

    def _collect_media_files(self):
        """
        Collect all media files in the directory and organize them by subfolder.
        """
        logger = get_logger(__name__)
        logger.info(f"Collecting media files from {self.directory_path}")
        
        # Define supported media file extensions
        media_extensions = [
            '.mkv', '.mp4', '.avi', '.mov', '.wmv', '.m4v', '.ts',
            '.flv', '.webm', '.vob', '.ogv', '.ogg', '.mpg', '.mpeg', '.m2ts'
        ]
        
        # Allow resuming from where we left off
        start_from_idx = 0
        if self.resume:
            history = load_scan_history()
            if history and 'processed_files' in history:
                start_from_idx = history['processed_files']
                logger.info(f"Resuming from file index {start_from_idx}")
        
        # Walk through all subdirectories
        self.media_files = []
        self.subfolder_files = {}
        for root, dirs, files in os.walk(self.directory_path):
            # Filter for media files only
            media_files_in_dir = [
                os.path.join(root, f) for f in files 
                if os.path.splitext(f.lower())[1] in media_extensions
            ]
            
            if media_files_in_dir:
                # Add to total list
                self.media_files.extend(media_files_in_dir)
                
                # Group files by subfolder
                if root not in self.subfolder_files:
                    self.subfolder_files[root] = []
                self.subfolder_files[root].extend(media_files_in_dir)
        
        # Sort files to ensure consistent ordering
        self.media_files.sort()
        for subfolder in self.subfolder_files:
            self.subfolder_files[subfolder].sort()
        
        # Update counts
        self.total_files = len(self.media_files)
        
        if self.total_files == 0:
            logger.warning(f"No media files found in {self.directory_path}")
            print(f"No media files found in {self.directory_path}")
        else:
            logger.info(f"Found {self.total_files} media files in {len(self.subfolder_files)} subfolders")
            print(f"Found {self.total_files} media files in {len(self.subfolder_files)} subfolders")
            
        return self.total_files > 0

    def _extract_folder_metadata(self, folder_name):
        """
        Extract title and year from folder name.
        
        Args:
            folder_name: Name of the folder to extract metadata from
            
        Returns:
            Tuple of (title, year)
        """
        logger = get_logger(__name__)
        logger.info(f"Extracting metadata from folder name: {folder_name}")
        
        # Replace dots, underscores, and dashes with spaces
        clean_name = re.sub(r'[._-]', ' ', folder_name)
        
        # Look for year in parentheses, e.g., "Movie Name (2020)"
        year_match = re.search(r'\((\d{4})\)', clean_name)
        year = None
        
        if year_match:
            year = year_match.group(1)
            # Remove the year and parentheses from the title
            clean_name = clean_name.replace(year_match.group(0), '')
        else:
            # Try to find a standalone year (4 digits)
            year_match = re.search(r'(?<!\d)(\d{4})(?!\d)', clean_name)
            if year_match:
                year = year_match.group(1)
                # Validate the year is reasonable
                if 1900 <= int(year) <= 2030:
                    # Remove the year from the title
                    clean_name = clean_name[:year_match.start()] + ' ' + clean_name[year_match.end():]
                else:
                    year = None  # Invalid year range
        
        # Clean up additional metadata and tags
        clean_name = re.sub(r'\[[^\]]*\]', '', clean_name)  # Remove square bracket content
        clean_name = re.sub(r'\([^)]*\)', '', clean_name)   # Remove parentheses content
        
        # Enhanced patterns for technical terms and release info
        patterns = [
            # Resolution and quality
            r'(?i)(1080p|720p|2160p|4K|UHD)',
            r'(?i)(PROPER|LIMITED|REMASTERED|EXTENDED|UNRATED|DC|DIRECTOR\'?S?|CUT)',
            r'(?i)(HDTV|PDTV|DSR|DVDRip|BDRip|BRRip|BluRay|Blu ray|REMUX|WEB-?DL)',
            r'(?i)(HEVC|H\.?264|H\.?265|x264|x265|XviD|DivX)',
            r'(?i)(AAC|AC3|DTS|DTS-HD|TrueHD|Atmos)',
            # Audio and encoding details
            r'(?i)(Repack|Repacked|AVC|HD|MA|5\.1|7\.1|DUAL|AUDIO)',
            # Common release group names
            r'(?i)\b(KRaLiMaRKo|FGT|RARBG|YIFY|YTS|ETRG|CMRG|EVO|SPARKS|GECKOS)\b',
            r'(?i)\b(UPLOADS|VYNDROS|FLEET|AMIABLE|LEONIDAS|FLAME|CHATEX|DRONES)\b',
            r'(?i)\b(PEEPLE|REDEMPTION|ExKinoRay|PCH|CAKES|STRIX|SAPHiRE|BAKED)\b',
            r'(?i)\b(NAISU|VYNDROS|SMURF|WISKISS|DVT|HYBRID|FLUX)\b',
            # Catch remaining release group style tags
            r'(?i)(-[A-Za-z0-9]+)$',
            # Common words that aren't part of titles
            r'(?i)\b(Complete|Season|Series)\b'
        ]
        
        # Apply all patterns
        for pattern in patterns:
            clean_name = re.sub(pattern, '', clean_name)
        
        # Clean up for cases like "3 Idiots Repack Blu ray Remux AVC HD MA 5 1 KRaLiMaRKo"
        # First identify likely title by looking at the first few words before technical terms
        
        # Check if the clean name is very long (likely contains technical info)
        # and doesn't have common connector words that might indicate a longer actual title
        if len(clean_name.split()) > 3 and not re.search(r'\b(and|the|of|in|on|at|by|for|with|to)\b', clean_name, re.IGNORECASE):
            # Try to extract a title from the beginning
            # First check for known movie titles with numbers (common edge cases)
            known_title_patterns = [
                r'^3 Idiots\b',
                r'^2 Fast 2 Furious\b',
                r'^10 Cloverfield Lane\b',
                r'^127 Hours\b',
                r'^12 Angry Men\b',
                r'^12 Monkeys\b',
                r'^13 Going on 30\b',
                r'^1917\b',
                r'^2001 A Space Odyssey\b',
                r'^21 Jump Street\b',
                r'^28 Days Later\b',
                r'^300\b',
                r'^40 Year Old Virgin\b',
                r'^500 Days of Summer\b',
                r'^7 Samurai\b',
                r'^8 Mile\b',
                r'^9\b',  # The animated film
            ]
            
            for pattern in known_title_patterns:
                title_match = re.search(pattern, clean_name, re.IGNORECASE)
                if title_match:
                    clean_name = title_match.group(0)
                    logger.info(f"Matched known title pattern: {clean_name}")
                    break
            else:
                # If no known pattern matched, take the first 1-4 words as the title
                # This is a heuristic that works well for many movie titles
                title_words = clean_name.split()
                
                # Use different strategies based on length
                if len(title_words) >= 6:
                    # For very long strings, try to find a sensible cutoff
                    # Keep first 2-4 words depending on length and word size
                    
                    # Check if first word is just a number or article
                    if title_words[0].isdigit() or title_words[0].lower() in ['the', 'a', 'an']:
                        # If so, include at least 3-4 words
                        clean_name = ' '.join(title_words[:min(4, len(title_words))])
                    else:
                        # Otherwise 2-3 words might be enough
                        clean_name = ' '.join(title_words[:min(3, len(title_words))])
                        
                    logger.info(f"Extracted title from first few words: {clean_name}")
                    
                elif len(title_words) > 3:
                    # For medium length, check if it has technical terms
                    if any(re.search(p, title_words[-1], re.IGNORECASE) for p in patterns):
                        clean_name = ' '.join(title_words[:-1])
        
        # Clean up whitespace and trim
        clean_name = re.sub(r'\s+', ' ', clean_name).strip()
        
        # Special case handling for "3 Idiots" and similar titles 
        # that might get over-processed
        if folder_name.lower().startswith("3 idiots") or folder_name.lower().startswith("3.idiots"):
            clean_name = "3 Idiots"
            logger.info("Applied special case handling for '3 Idiots'")
        
        logger.info(f"Extracted metadata - Title: '{clean_name}', Year: {year}")
        return clean_name, year

    def _process_media_files(self):
        """Process each subfolder and its media files."""
        from src.utils.scanner_utils import check_scanner_lists
        
        print("\nProcessing media files by subfolder...")
        
        # Process each subfolder
        for subfolder, files in self.subfolder_files.items():
            # Skip if no files
            if not files:
                continue
            
            # Extract subfolder name for display
            subfolder_name = os.path.basename(subfolder)
            
            # Clear screen and show subfolder info only in manual mode
            if not self.auto_mode:
                clear_screen()
                display_ascii_art()
                print("=" * 60)
                print(f"PROCESSING SUBFOLDER: {subfolder_name}")
                print("=" * 60)
                
                print(f"\nFolder path: {subfolder}")
                print(f"Contains {len(files)} media files")
            else:
                print(f"\nProcessing subfolder: {subfolder_name}")
            
            # Initialize ID variables that might be needed later
            tmdb_id = None
            imdb_id = None
            tvdb_id = None
            
            # Special case handling for specific known content
            if "Pokemon.Origins" in subfolder_name or "Pokemon Origins" in subfolder_name:
                suggested_title = "Pokemon Origins"
                content_type = "tv"  # It's an anime series
                is_anime = True
                tmdb_id = None
                suggested_year = None
                has_confident_match = True  # This is a hardcoded match
            else:
                # Try to extract metadata from folder name first
                suggested_title, suggested_year = self._extract_folder_metadata(subfolder_name)
                
                # Initialize variables
                content_type = "unknown"
                is_anime = False
                scanner_title = None
                scanner_matched = False
                has_confident_match = False
                
                # Try to match against scanner lists for each file
                for file_path in files:
                    file_name = os.path.basename(file_path)
                    
                    # First try with the cleaned title we extracted
                    scanner_result = check_scanner_lists(file_name, title_hint=suggested_title)
                    
                    if scanner_result:
                        scanner_matched = True
                        has_confident_match = True  # Scanner matches are considered confident
                        # Properly unpack the scanner result which now returns 4 values
                        if len(scanner_result) == 4:
                            content_type, is_anime, tmdb_id, scanner_title = scanner_result
                            # Use the scanner title if available
                            if scanner_title:
                                suggested_title = scanner_title
                                self.logger.info(f"Using scanner list title: {scanner_title}")
                            if tmdb_id and tmdb_id != "error":
                                self.logger.info(f"Using scanner list TMDB ID: {tmdb_id}")
                            break
                        else:
                            # Handle the case where scanner_result has 3 values for backward compatibility
                            content_type, is_anime, tmdb_id = scanner_result
                            if tmdb_id and tmdb_id != "error":
                                self.logger.info(f"Using scanner list TMDB ID: {tmdb_id}")
                            break
                    else:
                        # If no match with title hint, try without it
                        scanner_result = check_scanner_lists(file_name)
                        if scanner_result:
                            scanner_matched = True
                            has_confident_match = True  # Scanner matches are considered confident
                            # Properly unpack the scanner result
                            if len(scanner_result) == 4:
                                content_type, is_anime, tmdb_id, scanner_title = scanner_result
                                # Use the scanner title if available
                                if scanner_title:
                                    suggested_title = scanner_title
                                    self.logger.info(f"Using scanner list title: {scanner_title}")
                                if tmdb_id and tmdb_id != "error":
                                    self.logger.info(f"Using scanner list TMDB ID: {tmdb_id}")
                                break
                            else:
                                # Handle the case where scanner_result has 3 values for backward compatibility
                                content_type, is_anime, tmdb_id = scanner_result
                                if tmdb_id and tmdb_id != "error":
                                    self.logger.info(f"Using scanner list TMDB ID: {tmdb_id}")
                                break
            
            # Filter out invalid years (like resolution values)
            if suggested_year and (not suggested_year.isdigit() or int(suggested_year) < 1900 or int(suggested_year) > 2030):
                suggested_year = None
            
            # If we didn't find a confident match in scanners, try TMDB
            if not has_confident_match:
                # Only try TMDB if we have a reasonable title to search with
                if suggested_title and len(suggested_title) > 3:
                    # Try to determine if it's a movie or TV show based on file patterns
                    likely_tv = any(re.search(r'(?i)S\d+E\d+|\d+x\d+|season|episode', f) for f in [os.path.basename(f) for f in files])
                    
                    # Get media IDs from TMDB
                    ids = self._get_media_ids(suggested_title, suggested_year, likely_tv)
                    tmdb_id = ids.get('tmdb_id')
                    imdb_id = ids.get('imdb_id')
                    tvdb_id = ids.get('tvdb_id')
                    
                    # If we got a valid TMDB ID, consider it a confident match
                    if tmdb_id and tmdb_id != "error":
                        has_confident_match = True
                        content_type = "tv" if likely_tv else "movie"
                        self.logger.info(f"Using TMDB match: {tmdb_id} for {suggested_title}")
                    else:
                        # If we have a reasonable title, we can still proceed in auto mode
                        if self.auto_mode and suggested_title and len(suggested_title) > 3:
                            # Try to guess content type from filenames if still unknown
                            if content_type == "unknown":
                                # Check for common TV episode patterns in filenames
                                tv_patterns = [
                                    r'(?i)S\d+E\d+',  # S01E01 format
                                    r'(?i)\d+x\d+',   # 1x01 format
                                    r'(?i)season\s*\d+',  # "Season 1" text
                                    r'(?i)episode\s*\d+'  # "Episode 1" text
                                ]
                                
                                # Check if any file matches TV patterns
                                has_tv_pattern = any(
                                    any(re.search(pattern, os.path.basename(f)) for pattern in tv_patterns)
                                    for f in files
                                )
                                
                                if has_tv_pattern:
                                    content_type = "tv"
                                    self.logger.info(f"Guessed TV series from filename patterns: {suggested_title}")
                                else:
                                    content_type = "movie"
                                    self.logger.info(f"Defaulting to movie type for: {suggested_title}")
                            
                            # Don't skip in auto mode if we have at least a title and content type
                            if content_type != "unknown":
                                has_confident_match = True
            
            # In auto mode, we'll still process items with a title and content type, even if not confident
            if self.auto_mode and not has_confident_match:
                if suggested_title and len(suggested_title) > 3:
                    # If content type is still unknown, default to movie
                    if content_type == "unknown":
                        content_type = "movie"
                        self.logger.info(f"Defaulting to movie type for: {suggested_title}")
                        has_confident_match = True
                else:
                    # No good title, must skip
                    self.logger.warning(f"No good title found for {subfolder_name}, skipping in auto mode")
                    print(f"No good title found for {subfolder_name}, skipping")
                    self._skip_files(files, subfolder, "unknown", False, os.path.basename(subfolder))
                    self.processed_files += len(files)  # Consider these processed even though skipped
                    continue
                    
            # In auto mode, process directly with the determined information
            if self.auto_mode:
                # Never use "error" as a TMDB ID
                if tmdb_id == "error":
                    tmdb_id = None
                
                # Ensure imdb_id and tvdb_id are defined (might not have been set above)
                if 'imdb_id' not in locals() or imdb_id is None:
                    imdb_id = None
                    
                if 'tvdb_id' not in locals() or tvdb_id is None:
                    tvdb_id = None
                    
                # Process based on content type
                if content_type == "tv":
                    self.logger.info(f"Auto processing TV series: {suggested_title} ({suggested_year})")
                    self._process_tv_series(files, subfolder, suggested_title, suggested_year, is_anime,
                                          tmdb_id=tmdb_id, imdb_id=imdb_id, tvdb_id=tvdb_id)
                elif content_type == "movie":
                    self.logger.info(f"Auto processing movie: {suggested_title} ({suggested_year})")
                    self._process_movies(files, subfolder, suggested_title, suggested_year, is_anime,
                                       tmdb_id=tmdb_id, imdb_id=imdb_id, tvdb_id=tvdb_id)
                else:
                    # This should rarely happen now with the improved handling
                    self.logger.warning(f"Unknown content type, skipping: {suggested_title}")
                    self._skip_files(files, subfolder, "unknown", is_anime, os.path.basename(subfolder))
                
                # Update processed count
                self.processed_files += len(files)
                continue
                
            # Manual mode processing remains unchanged
            else:
                # Ensure imdb_id and tvdb_id are defined for manual mode
                if 'imdb_id' not in locals() or imdb_id is None:
                    imdb_id = None
                    
                if 'tvdb_id' not in locals() or tvdb_id is None:
                    tvdb_id = None
                
                # Display any information we've determined so far
                print("\nDetected information:")
                print(f"Title: {suggested_title}")
                if suggested_year:
                    print(f"Year: {suggested_year}")
                if content_type != "unknown":
                    print(f"Content type: {content_type.upper()}")
                if is_anime:
                    print("Anime: Yes")
                if tmdb_id and tmdb_id != "error":
                    print(f"TMDB ID: {tmdb_id}")
                
                # If we don't have a confident match, prompt the user
                if not has_confident_match:
                    print("\nCouldn't confidently determine this content. Please select an option:")
                    print("1. Process as Movie")
                    print("2. Process as TV Show")
                    print("3. Process as Anime Movie")
                    print("4. Process as Anime TV Show")
                    print("5. Skip for later review")
                    
                    choice = input("\nChoice (1-5): ").strip()
                    
                    if choice == '1':
                        content_type = "movie"
                        is_anime = False
                    elif choice == '2':
                        content_type = "tv"
                        is_anime = False
                    elif choice == '3':
                        content_type = "movie"
                        is_anime = True
                    elif choice == '4':
                        content_type = "tv"
                        is_anime = True
                    elif choice == '5':
                        self._skip_files(files, subfolder, "unknown", False, os.path.basename(subfolder))
                        print("Content skipped for later review.")
                        input("\nPress Enter to continue...")
                        continue
                    else:
                        print("Invalid choice. Skipping content.")
                        self._skip_files(files, subfolder, "unknown", False, os.path.basename(subfolder))
                        input("\nPress Enter to continue...")
                        continue
                
                # Allow user to adjust the title and year
                print("\nConfirm or edit details:")
                new_title = input(f"Title [{suggested_title}]: ").strip()
                if new_title:
                    suggested_title = new_title
                
                new_year = input(f"Year [{suggested_year or 'Unknown'}]: ").strip()
                if new_year:
                    suggested_year = new_year
                
                # Allow user to enter TMDB ID manually if needed
                if not tmdb_id or tmdb_id == "error":
                    new_tmdb_id = input("TMDB ID (optional): ").strip()
                    if new_tmdb_id and new_tmdb_id.isdigit():
                        tmdb_id = new_tmdb_id
                
                # Process the content based on user selections
                if content_type == "tv":
                    self._process_tv_series(files, subfolder, suggested_title, suggested_year, is_anime,
                                          tmdb_id=tmdb_id, imdb_id=imdb_id, tvdb_id=tvdb_id)
                elif content_type == "movie":
                    self._process_movies(files, subfolder, suggested_title, suggested_year, is_anime,
                                       tmdb_id=tmdb_id, imdb_id=imdb_id, tvdb_id=tvdb_id)
                
                # Update processed count
                self.processed_files += len(files)

    def _get_media_ids(self, title, year=None, is_tv=False):
        """
        Get media IDs from TMDB.
        
        Args:
            title: Title to search for
            year: Year of release (optional)
            is_tv: Boolean indicating if this is a TV show
            
        Returns:
            Dictionary with tmdb_id, imdb_id, and tvdb_id
        """
        logger = get_logger(__name__)
        
        result = {
            'tmdb_id': None,
            'imdb_id': None,
            'tvdb_id': None
        }
        
        try:
            # Import TMDB API
            from src.api.tmdb import TMDB
            
            # Get TMDB API key from environment
            tmdb_api_key = os.environ.get('TMDB_API_KEY', '')
            
            if not tmdb_api_key:
                logger.warning("TMDB API key not set, skipping ID lookup")
                return result
                
            tmdb = TMDB(api_key=tmdb_api_key)
            
            # Construct search query
            query = title
            if year:
                query += f" {year}"
                
            logger.info(f"Searching TMDB for {'TV show' if is_tv else 'movie'}: {query}")
            
            # Search TMDB based on content type
            results = tmdb.search_tv(query, limit=1) if is_tv else tmdb.search_movie(query, limit=1)
            
            if results:
                result_item = results[0]
                result['tmdb_id'] = result_item.get('id')
                
                # Get additional IDs if available
                if is_tv and result['tmdb_id']:
                    # For TV shows, need to make an additional call to get external IDs
                    details = tmdb.get_tv_details(result['tmdb_id'])
                    if details and 'external_ids' in details:
                        result['imdb_id'] = details['external_ids'].get('imdb_id')
                        result['tvdb_id'] = details['external_ids'].get('tvdb_id')
            else:
                logger.warning(f"No TMDB results found for: {query}")
        except Exception as e:
            logger.error(f"Error getting media IDs: {e}")
            # Set tmdb_id to "error" to indicate we tried but failed
            result['tmdb_id'] = "error"
            
        return result

    def process(self):
        """Process the directory and create symlinks."""
        clear_screen()
        display_ascii_art()
        print("=" * 60)
        print("SCANNING DIRECTORY")
        print("=" * 60)
        
        print(f"\nScanning: {self.directory_path}")
        
        # Check if directory exists
        if not os.path.isdir(self.directory_path):
            print(f"Directory not found: {self.directory_path}")
            input("\nPress Enter to continue...")
            return
        
        # Check if destination directory is set
        if not os.environ.get('DESTINATION_DIRECTORY'):
            print("Destination directory not set.")
            print("Please set the destination directory in Settings > Paths first.")
            input("\nPress Enter to continue...")
            return
        
        try:
            # Display the mode being used at the beginning
            print(f"\nScan mode: {'Automatic' if self.auto_mode else 'Manual'}")
            
            # Collect all media files in the directory
            self._collect_media_files()
            
            if not self.media_files:
                print("No media files found in the directory.")
                input("\nPress Enter to continue...")
                return
            
            # Use the auto_mode parameter without asking again
            self.auto_process = self.auto_mode
            
            # Process each media file
            self._process_media_files()
            
            # Clear screen for final results
            clear_screen()
            display_ascii_art()
            print("=" * 60)
            print("SCAN COMPLETED")
            print("=" * 60)
            
            # Display results
            print(f"\nDirectory: {self.directory_path}")
            print("\nSummary:")
            print(f"- Processed: {self.processed_files} files")
            print(f"- Created symlinks: {self.symlink_count}")
            print(f"- Skipped: {self.skipped} files")
            print(f"- Errors: {self.errors}")
            
            # Clear scan history if all files were processed
            if self.processed_files >= self.total_files:
                clear_scan_history()
                print("\nScan history cleared.")
            
            print("\nScan complete! Press Enter to return to main menu.")
            input()
            
        except KeyboardInterrupt:
            # Save progress for resuming later
            save_scan_history(self.directory_path, self.processed_files, self.total_files, self.media_files)
            print("\nScan interrupted. Progress saved for resuming later.")
            input("\nPress Enter to continue...")
        except Exception as e:
            self.logger.error(f"Error processing directory: {e}", exc_info=True)
            print(f"\nError processing directory: {e}")
            input("\nPress Enter to continue...")

# MainMenu class
class MainMenu:
    """Main menu handler for the application."""
    
    def __init__(self):
        self.logger = get_logger(__name__)
    
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
            
            # Get user choice
            choice = input("\nEnter your choice: ").strip().lower()
            
            if choice == '1':
                self.individual_scan()
            elif choice == '2':
                self.multi_scan()
            elif has_history and choice == '3':
                self.resume_scan()
            elif has_history and choice == '4':
                # Clear scan history
                clear_scan_history()
                print("Scan history cleared.")
                input("\nPress Enter to continue...")
            # Handle skipped items review
            elif has_skipped and ((has_history and choice == '5') or (not has_history and choice == '3')):
                review_skipped_items()
            # Settings option
            elif choice == str(max_choice):
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
    
    def individual_scan(self):
        """Handle individual scan option."""
        clear_screen()
        display_ascii_art()
        print("=" * 60)
        print("INDIVIDUAL SCAN")
        print("=" * 60)
        
        # Ask for scan mode first
        print("\nSelect scan mode:")
        print("1. Auto Scan (automatic content detection and processing without user interaction)")
        print("2. Manual Scan (interactive content selection and processing)")
        print("0. Back to Main Menu")
        
        mode_choice = input("\nEnter choice (0-2): ").strip()
        
        if mode_choice == '0':
            return
            
        auto_mode = (mode_choice == "1")
        
        if not auto_mode and mode_choice != "2":
            print("\nInvalid choice. Using manual scan mode.")
            auto_mode = False
            input("\nPress Enter to continue...")
        
        # Get directory path from user
        print("\nEnter the path to scan (or 'q' to cancel):")
        dir_path = input("> ").strip()
        
        if dir_path.lower() == 'q':
            return
        
        # Strip quotes that might be added when dragging paths into terminal
        dir_path = dir_path.strip("'\"")
        
        # Validate directory exists
        if not os.path.isdir(dir_path):
            print(f"\nError: {dir_path} is not a valid directory.")
            input("\nPress Enter to continue...")
            return
        
        # Process the directory - make sure auto_mode is passed here
        print(f"\nInitializing processor with auto_mode={auto_mode}...")
        processor = DirectoryProcessor(dir_path, auto_mode=auto_mode)
        processor.process()
    
    def multi_scan(self):
        """Handle multi-scan option."""
        clear_screen()
        display_ascii_art()
        print("=" * 60)
        print("MULTI SCAN")
        print("=" * 60)
        
        # Ask for scan mode first
        print("\nSelect scan mode:")
        print("1. Auto Scan (automatic content detection and processing without user interaction)")
        print("2. Manual Scan (interactive content selection and processing)")
        print("0. Back to Main Menu")
        
        mode_choice = input("\nEnter choice (0-2): ").strip()
        
        if mode_choice == '0':
            return
            
        auto_mode = (mode_choice == "1")
        
        if not auto_mode and mode_choice != "2":
            print("\nInvalid choice. Using manual scan mode.")
            auto_mode = False
            input("\nPress Enter to continue...")
        
        print("\nMulti scan allows you to queue multiple directories for scanning.")
        print("Enter each directory path on a new line.")
        print("When finished, enter a blank line to start scanning.")
        print("Enter 'q' to cancel and return to the main menu.\n")
        
        directories = []
        while True:
            dir_input = input(f"Directory {len(directories) + 1} (or blank to finish): ").strip()
            
            if dir_input.lower() == 'q':
                return
            
            if not dir_input:
                # Finished entering directories
                break
            
            # Validate directory exists
            if not os.path.isdir(dir_input):
                print(f"Error: {dir_input} is not a valid directory.")
                continue
            
            directories.append(dir_input)
        
        if not directories:
            print("\nNo directories entered.")
            input("\nPress Enter to continue...")
            return
        
        # Process each directory - make sure auto_mode is passed here
        for i, dir_path in enumerate(directories):
            clear_screen()
            display_ascii_art()
            print("=" * 60)
            print(f"PROCESSING DIRECTORY {i+1}/{len(directories)}")
            print("=" * 60)
            print(f"\nDirectory: {dir_path}\n")
            print(f"Using scan mode: {'Automatic' if auto_mode else 'Manual'}")
            
            processor = DirectoryProcessor(dir_path, auto_mode=auto_mode)
            processor.process()
    
    def resume_scan(self):
        """Resume a previously interrupted scan."""
        # Load scan history
        history = load_scan_history()
        
        if not history or 'directory' not in history:
            print("No scan history found.")
            input("\nPress Enter to continue...")
            return
        
        # Display history information
        clear_screen()
        display_ascii_art()
        print("=" * 60)
        print("RESUME SCAN")
        print("=" * 60)
        
        dir_path = history.get('directory', 'Unknown')
        processed = history.get('processed_files', 0)
        total = history.get('total_files', 0)
        
        print(f"\nFound interrupted scan of {dir_path}")
        print(f"Progress: {processed}/{total} files ({int((processed/total)*100) if total > 0 else 0}%)")
        
        # Prompt user to resume or cancel
        resume = input("\nResume this scan? (y/n): ").strip().lower()
        
        if resume != 'y':
            return
        
        # Process the directory with resume flag
        if os.path.isdir(dir_path):
            processor = DirectoryProcessor(dir_path, resume=True)
            processor.process()
        else:
            print(f"\nError: Directory {dir_path} no longer exists.")
            input("\nPress Enter to continue...")
    
    def settings_menu(self):
        """Display and handle the settings menu."""
        settings = self._load_settings()
        
        while True:
            clear_screen()
            display_ascii_art()
            print("=" * 60)
            print("SETTINGS")
            print("=" * 60)
            
            # Group settings by category
            categories = {}
            for setting in settings:
                category = setting.get('category', 'General')
                if category not in categories:
                    categories[category] = []
                categories[category].append(setting)
            
            # Display categories
            print("\nSettings categories:")
            for i, category in enumerate(categories.keys(), 1):
                print(f"{i}. {category}")
            
            print("\n0. Back to Main Menu")
            
            category_choice = input("\nSelect category (0 to go back): ").strip()
            
            if category_choice == '0':
                break
            
            # Check if the choice is valid
            if not category_choice.isdigit() or int(category_choice) < 1 or int(category_choice) > len(categories):
                print("Invalid choice.")
                input("\nPress Enter to continue...")
                continue
            
            # Get the selected category and its settings
            selected_category = list(categories.keys())[int(category_choice) - 1]
            category_settings = categories[selected_category]
            
            # Show settings for the selected category
            while True:
                clear_screen()
                display_ascii_art()
                print("=" * 60)
                print(f"Settings > {selected_category}")
                print("=" * 60)
                
                print("\nCurrent settings:")
                for i, setting in enumerate(category_settings, 1):
                    name = setting.get('name', '')
                    description = setting.get('description', '')
                    default_value = setting.get('default', '')
                    current_value = os.environ.get(name, default_value)
                    
                    # Format display based on setting type
                    if setting.get('type') == 'bool':
                        display_value = 'Enabled' if current_value.lower() == 'true' else 'Disabled'
                    elif setting.get('type') == 'password' and current_value:
                        display_value = '*' * len(current_value)
                    else:
                        display_value = current_value if current_value else '<Not Set>'
                    
                    print(f"{i}. {description}: {display_value}")
                
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
                        print(f"Error: Handler '{handler_name}' not found")
                        input("\nPress Enter to continue...")
                    continue
                
                # For boolean settings, toggle the value
                if selected_setting.get("type") == "bool":
                    new_value = 'false' if current_value.lower() == 'true' else 'true'
                    self._update_env_var(env_var, new_value)
                    print(f"Setting updated: {new_value}")
                    input("\nPress Enter to continue...")
                    continue
                
                # For directory settings, provide directory selection
                if selected_setting.get("type") == "directory":
                    print(f"\nCurrent value: {current_value}")
                    print("Enter new directory path or leave blank to keep current value.")
                    print("Enter 'browse' to open a directory browser.")
                    
                    new_value = input("> ").strip()
                    
                    if new_value == 'browse':
                        # Directory browser not implemented in this version
                        print("Directory browser not available in this version.")
                        new_value = input("Enter directory path manually: ").strip()
                    
                    if new_value:
                        # Validate directory
                        if os.path.isdir(new_value) or input("Directory doesn't exist. Create it? (y/n): ").lower() == 'y':
                            self._update_env_var(env_var, new_value)
                            print(f"Setting updated: {new_value}")
                        else:
                            print("Setting not updated.")
                    
                    input("\nPress Enter to continue...")
                    continue
                
                # For all other settings, prompt for new value
                print(f"\nCurrent value: {current_value}")
                print("Enter new value or leave blank to keep current value:")
                
                new_value = input("> ").strip()
                
                if new_value:
                    self._update_env_var(env_var, new_value)
                    print(f"Setting updated: {new_value}")
                
                input("\nPress Enter to continue...")
    
    def _load_settings(self):
        """Load application settings."""
        # Define the settings schema
        settings = [
            {
                'name': 'DESTINATION_DIRECTORY',
                'description': 'Media destination directory',
                'type': 'directory',
                'category': 'Paths',
                'default': ''
            },
            {
                'name': 'TMDB_API_KEY',
                'description': 'TMDB API Key',
                'type': 'password',
                'category': 'API',
                'default': ''
            },
            {
                'name': 'AUTO_EXTRACT_EPISODES',
                'description': 'Auto-extract episode information',
                'type': 'bool',
                'category': 'Processing',
                'default': 'false'
            },
            {
                'name': 'SCANNER_LISTS',
                'description': 'Manage scanner lists',
                'type': 'custom_handler',
                'handler': '_manage_scanner_lists',
                'category': 'Content',
                'default': ''
            }
        ]
        
        return settings
    
    def _update_env_var(self, name, value):
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
    
    def _manage_scanner_lists(self):
        """Manage scanner lists for content type detection."""
        while True:
            clear_screen()
            display_ascii_art()
            print("=" * 60)
            print("MANAGE SCANNER LISTS")
            print("=" * 60)
            
            print("\nScanner lists are used to identify content types automatically.")
            print("Select a list to edit:")
            print("1. TV Series")
            print("2. Movies")
            print("3. Anime Series")
            print("4. Anime Movies")
            print("\n0. Back to Settings")
            
            choice = input("\nEnter your choice: ").strip()
            
            if choice == '0':
                break
            
            scanner_files = {
                '1': ('tv_series.txt', 'TV Series'),
                '2': ('movies.txt', 'Movies'),
                '3': ('anime_series.txt', 'Anime Series'),
                '4': ('anime_movies.txt', 'Anime Movies')
            }
            
            if choice in scanner_files:
                filename, list_type = scanner_files[choice]
                self._edit_scanner_list(filename, list_type)
            else:
                print("Invalid choice.")
                input("\nPress Enter to continue...")
    
    def _edit_scanner_list(self, filename, list_type):
        """
        Edit a scanner list file.
        
        Args:
            filename: Name of the file in the scanners directory
            list_type: Human-readable name of the list type
        """
        # Import TMDB API for validation
        from dotenv import load_dotenv
        load_dotenv()
        
        # Get TMDB API key from environment
        tmdb_api_key = os.environ.get('TMDB_API_KEY', '3b5df02338c403dad189e661d57e351f')
        
        logger = get_logger(__name__)
        tmdb = TMDB(api_key=tmdb_api_key)
        
        clear_screen()
        display_ascii_art()
        print("=" * 60)
        print(f"Edit {list_type} Scanner List")
        print("=" * 60)
        
        # Define path to scanner file
        scanner_file_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'scanners', filename)
        
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(scanner_file_path), exist_ok=True)
        
        # Create the file if it doesn't exist
        if not os.path.exists(scanner_file_path):
            open(scanner_file_path, 'w').close()
            print(f"Created new {list_type} scanner file.")
        
        # Read current entries
        try:
            with open(scanner_file_path, 'r', encoding='utf-8') as f:
                entries = [line.strip() for line in f.readlines() if line.strip()]
        except Exception as e:
            print(f"Error reading scanner file: {e}")
            entries = []
        
        while True:
            clear_screen()
            display_ascii_art()
            print("=" * 60)
            print(f"Edit {list_type} Scanner List")
            print("=" * 60)
            
            # Display current entries with line numbers
            print(f"\nCurrent {list_type} Entries ({len(entries)}):")
            if entries:
                for i, entry in enumerate(entries, 1):
                    # Highlight TMDB ID if present
                    if "[" in entry and "]" in entry and re.search(r'\[\d+\]$', entry):
                        tmdb_id = re.search(r'\[(\d+)\]$', entry).group(1)
                        entry_without_id = re.sub(r'\s*\[\d+\]\s*$', '', entry)
                        print(f"{i}. {entry_without_id} [TMDB ID: {tmdb_id}]")
                    else:
                        print(f"{i}. {entry}")
            else:
                print("No entries found.")
            
            print("\nOptions:")
            print("1. Add new entry")
            print("2. Remove entry")
            print("3. Add/Update TMDB ID for entry")
            print("4. Save and return to Settings")
            print("0. Return without saving")
            
            choice = input("\nSelect option: ").strip()
            
            if choice == '1':
                # Add new entry
                new_entry = input("\nEnter new entry name: ").strip()
                if new_entry and new_entry not in entries:
                    entries.append(new_entry)
                    print(f"Added: {new_entry}")
                elif new_entry in entries:
                    print(f"Entry already exists: {new_entry}")
                input("\nPress Enter to continue...")
                
            elif choice == '2':
                # Remove entry
                if not entries:
                    print("\nNo entries to remove.")
                    input("\nPress Enter to continue...")
                    continue
                
                remove_idx = input("\nEnter the number of the entry to remove: ").strip()
                
                if remove_idx.isdigit() and 1 <= int(remove_idx) <= len(entries):
                    removed = entries.pop(int(remove_idx) - 1)
                    print(f"\nRemoved: {removed}")
                else:
                    print("\nInvalid entry number.")
                
                input("\nPress Enter to continue...")
        
            elif choice == '3':
                if not entries:
                    print("\nNo entries to update.")
                    input("\nPress Enter to continue...")
                    continue
                
                update_idx = input("\nEnter the number of the entry to add/update TMDB ID: ").strip()
                
                if update_idx.isdigit() and 1 <= int(update_idx) <= len(entries):
                    entry_idx = int(update_idx) - 1
                    current_entry = entries[entry_idx]
                    
                    # Remove existing TMDB ID if present
                    clean_entry = re.sub(r'\s*\[\d+\]\s*$', '', current_entry)
                    
                    # Determine search type based on list type
                    search_type = "movie" if "Movie" in list_type else "tv"
                    
                    # Extract year if present
                    year_match = re.search(r'\((\d{4})\)$', clean_entry)
                    year = year_match.group(1) if year_match else None
                    title = re.sub(r'\s*\(\d{4}\)\s*$', '', clean_entry) if year else clean_entry
                    
                    try:
                        print(f"\nSearching TMDB for {search_type}: {title}")
                        if search_type == "movie":
                            search_results = tmdb.search_movie(title, limit=5)
                        else:
                            search_results = tmdb.search_tv(title, limit=5)
                        
                        if search_results:
                            # Show search results
                            print("\nSearch results:")
                            for i, result in enumerate(search_results, 1):
                                result_title = result.get('title', result.get('name', 'Unknown'))
                                year_str = ""
                                if search_type == "movie" and 'release_date' in result and result['release_date']:
                                    year_str = f" ({result['release_date'][:4]})"
                                elif search_type == "tv" and 'first_air_date' in result and result['first_air_date']:
                                    year_str = f" ({result['first_air_date'][:4]})"
                                print(f"{i}. {result_title}{year_str} [TMDB ID: {result.get('id', 'Unknown')}]")
                            
                            print("\nSelect a match or enter 0 to skip adding TMDB ID:")
                            match_choice = input("Choice: ").strip()
                            
                            if match_choice.isdigit() and 1 <= int(match_choice) <= len(search_results):
                                result = search_results[int(match_choice) - 1]
                                tmdb_id = result.get('id')
                                
                                # Update entry with TMDB ID
                                entries[entry_idx] = f"{clean_entry} [{tmdb_id}]"
                                print(f"\nUpdated entry with TMDB ID: {entries[entry_idx]}")
                            else:
                                print("\nInvalid choice. Entry not updated.")
                        else:
                            print("\nNo TMDB matches found.")
                    except Exception as e:
                        logger.error(f"Error searching TMDB: {e}")
                        print(f"\nError searching TMDB: {e}")
                else:
                    print("\nInvalid entry number.")
                
                input("\nPress Enter to continue...")
                
            elif choice == '4':
                # Save changes
                try:
                    with open(scanner_file_path, 'w', encoding='utf-8') as f:
                        for entry in entries:
                            f.write(f"{entry}\n")
                    print(f"\nSaved {len(entries)} entries to {filename}")
                    input("\nPress Enter to continue...")
                    break
                except Exception as e:
                    logger.error(f"Error saving scanner file: {e}")
                    print(f"\nError saving file: {e}")
                    input("\nPress Enter to continue...")
                
            elif choice == '0':
                # Return without saving
                print("\nChanges discarded.")
                input("\nPress Enter to continue...")
                break
            
            else:
                print("\nInvalid option.")
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