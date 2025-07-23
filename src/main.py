#!/usr/bin/env python3
"""Scanly: A media file scanner and organizer.

This module is the main entry point for the Scanly application.
"""
import argparse
import datetime
import logging
import os
import sys
import json
import time
import re
import difflib
import subprocess
import csv
import sqlite3
from pathlib import Path
from utils.plex_utils import refresh_selected_plex_libraries
from utils.cleaning_patterns import patterns_to_remove, case_sensitive_patterns
from utils.scan_logic import normalize_title, normalize_unicode

# --- Add this helper function for consistent cleaning ---
def clean_title_with_patterns(title):
    for pattern in patterns_to_remove:
        title = re.sub(pattern, ' ', title, flags=re.IGNORECASE)
    for pattern in case_sensitive_patterns:
        title = re.sub(pattern, ' ', title)  # No IGNORECASE here!
    title = re.sub(r'\s+', ' ', title).strip()
    return title

TMDB_FOLDER_ID = os.getenv("TMDB_FOLDER_ID", "false").lower() == "true"
RESUME_TEMP_FILE = "/tmp/scanly_resume_path.txt"

def deduplicate_phrases(title):
    """Remove repeated phrases from a title string, preserving order."""
    words = title.split()
    seen = set()
    result = []
    phrase = ""
    for i, word in enumerate(words):
        # Build up phrases of length 2 and 3 for better detection
        if i < len(words) - 1:
            two_word = f"{words[i]} {words[i+1]}"
            if two_word.lower() not in seen:
                seen.add(two_word.lower())
                result.append(words[i])
            else:
                continue
        elif word.lower() not in seen:
            seen.add(word.lower())
            result.append(word)
    # Fallback: remove any single repeated words
    final = []
    seen_words = set()
    for word in result:
        if word.lower() not in seen_words:
            final.append(word)
            seen_words.add(word.lower())
    return ' '.join(final)

def save_resume_path(path):
    """Save the resume path to a temp file."""
    with open(RESUME_TEMP_FILE, "w") as f:
        f.write(path)

def load_resume_path():
    """Load and clear the resume path from the temp file."""
    if os.path.exists(RESUME_TEMP_FILE):
        with open(RESUME_TEMP_FILE, "r") as f:
            path = f.read().strip()
        os.remove(RESUME_TEMP_FILE)
        return path
    return None

def sanitize_filename(name):
    """Replace problematic characters for cross-platform compatibility."""
    return re.sub(r'[:/\\]', '-', name)

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
from dotenv import load_dotenv
load_dotenv()  # Load environment variables from .env file

# Import the logger utility
from src.utils.logger import get_logger
# IMPORTANT: All scan logic (title/year/content type extraction, etc.) must be imported from src/utils/scan_logic.py.
# Do not duplicate or modify scan logic in this file.

# Create log directory if it doesn't exist
log_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'logs')
os.makedirs(log_dir, exist_ok=True)

# Configure file handler to capture all logs regardless of console visibility
file_handler = logging.FileHandler(os.path.join(log_dir, 'scanly.log'), mode='w')  # Overwrite log each session
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))

# Configure root logger WITHOUT a console handler
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[file_handler],
    force=True  # <--- Add this line
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
    from src.config import TMDB_API_KEY, TMDB_BASE_URL
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
SCAN_HISTORY_FILE = os.path.join(os.path.dirname(__file__), 'scan_history.txt')
SCAN_HISTORY_DB = os.path.join(os.path.dirname(__file__), 'scan_history.db')

def _init_scan_history_db():
    """Initialize the scan history database if it doesn't exist."""
    conn = sqlite3.connect(SCAN_HISTORY_DB)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS archived_scan_history (
            path TEXT PRIMARY KEY,
            archived_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

def archive_scan_history_txt_to_db():
    """Move all items from scan_history.txt to the database if there are 100 or more, then clear the file."""
    if not os.path.exists(SCAN_HISTORY_FILE):
        return

    with open(SCAN_HISTORY_FILE, 'r') as f:
        lines = [line.strip() for line in f if line.strip()]

    if len(lines) < 100:
        return

    _init_scan_history_db()
    conn = sqlite3.connect(SCAN_HISTORY_DB)
    c = conn.cursor()
    for path in lines:
        try:
            c.execute('INSERT OR IGNORE INTO archived_scan_history (path) VALUES (?)', (path,))
        except Exception:
            pass
    conn.commit()
    conn.close()

    # Clear the txt file after archiving
    with open(SCAN_HISTORY_FILE, 'w') as f:
        pass

def is_path_in_archived_history(path):
    """Check if a path is in the archived scan history database."""
    _init_scan_history_db()
    conn = sqlite3.connect(SCAN_HISTORY_DB)
    c = conn.cursor()
    c.execute('SELECT 1 FROM archived_scan_history WHERE path=?', (path,))
    result = c.fetchone()
    conn.close()
    return result is not None

# Update load_scan_history_set to check both txt and db
def load_scan_history_set():
    """Load processed file paths from scan_history.txt and archived DB as a set."""
    paths = set()
    if os.path.exists(SCAN_HISTORY_FILE):
        with open(SCAN_HISTORY_FILE, 'r') as f:
            paths.update(line.strip() for line in f if line.strip())
    # Add archived paths from DB
    _init_scan_history_db()
    conn = sqlite3.connect(SCAN_HISTORY_DB)
    c = conn.cursor()
    c.execute('SELECT path FROM archived_scan_history')
    db_paths = c.fetchall()
    conn.close()
    paths.update(row[0] for row in db_paths)
    return paths

def is_any_media_file_in_scan_history(folder_path, scan_history_set):
    """
    Returns True if any media file in the given folder (recursively) is present in scan_history_set.
    """
    media_exts = ('.mkv', '.mp4', '.avi', '.mov', '.wmv', '.flv')
    for root, dirs, files in os.walk(folder_path):
        for file in files:
            if file.lower().endswith(media_exts):
                full_path = os.path.join(root, file)
                if full_path in scan_history_set:
                    return True
    return False

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
SCAN_HISTORY_FILE = os.path.join(os.path.dirname(__file__), 'scan_history.txt')

def append_to_scan_history(path):
    """Append a processed file path to scan_history.txt and update global set."""
    with open(SCAN_HISTORY_FILE, 'a') as f:
        f.write(f"{path}\n")
    GLOBAL_SCAN_HISTORY_SET.add(path)
    archive_scan_history_txt_to_db()  # <-- Add this line

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

# --- GLOBAL: Load scan history set at startup ---
GLOBAL_SCAN_HISTORY_SET = set()
def reload_global_scan_history():
    global GLOBAL_SCAN_HISTORY_SET
    GLOBAL_SCAN_HISTORY_SET = load_scan_history_set()
reload_global_scan_history()

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
except Exception as e:
    logger.error(f"Webhook import failed: {e}", exc_info=True)
    webhook_available = False
    
    # Create stub functions for webhooks
    def send_monitored_item_notification(item_data):
        logger.error("Webhook functionality is not available")
        return False
        
    def send_symlink_creation_notification(title, year, poster, description, symlink_path):
        logger.error("Webhook functionality is not available")
        return False
        
    def send_symlink_deletion_notification(media_name, year, poster, description, original_path, symlink_path):
        logger.error("Webhook functionality is not available")
        return False
        
    def send_symlink_repair_notification(media_name, year, poster, description, original_path, symlink_path):
        logger.error("Webhook functionality is not available")
        return False

FLAGGED_CSV = os.path.join(os.path.dirname(__file__), "flagged_paths.csv")
FLAGGED_HEADER = ["File Path", "Cleaned Title", "Year", "Content Type"]

def write_flag_to_csv(flagged_row):
    file_exists = os.path.isfile(FLAGGED_CSV)
    with open(FLAGGED_CSV, 'a', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=FLAGGED_HEADER)
        if not file_exists:
            writer.writeheader()
        writer.writerow(flagged_row)

def get_default_content_type_for_path(path):
    """
    Return (is_tv, is_anime, is_wrestling) defaults based on parent directory.
    """
    path = os.path.abspath(path).lower()
    mapping = {
        '/movies':      (False, False, False),  # Movies
        '/shows':       (True,  False, False),  # TV Series
        '/anime':       (True,  True,  False),  # Anime Series
        '/wrestling':   (False, False, True),   # Wrestling
    }
    for key, flags in mapping.items():
        if path.endswith(key):
            return flags
    return None  # No default

class DirectoryProcessor:
    """Process a directory of media files."""
    def __init__(self, directory_path, resume=False, auto_mode=False):
        self.directory_path = directory_path
        self.resume = resume
        self.auto_mode = auto_mode
        self.logger = get_logger(__name__)
        # Use the global scan history set
        self.processed_paths = GLOBAL_SCAN_HISTORY_SET
        
        # Initialize detection state variables
        self._detected_content_type = None
        self._detected_tmdb_id = None
    
    def _check_scanner_lists(self, title, year=None, is_tv=False, is_anime=False, is_wrestling=False):
        """
        Check if the given title (and optionally year) exists in the scanner lists.
        Returns a list of matching entries.
        """
        from src.utils.scan_logic import normalize_title
        import re

        # Normalize year: treat None, "", "Unknown", "unknown" as no year
        if not year or str(year).lower() == "unknown":
            year = None

        matches = []
        scanner_files = []

        # Decide which scanner lists to check based on content type
        if is_wrestling:
            scanner_files.append(os.path.join(os.path.dirname(__file__), '../scanners/wrestling.txt'))
        elif is_tv and is_anime:
            scanner_files.append(os.path.join(os.path.dirname(__file__), '../scanners/anime_series.txt'))
        elif is_tv:
            scanner_files.append(os.path.join(os.path.dirname(__file__), '../scanners/tv_series.txt'))
        elif is_anime:
            scanner_files.append(os.path.join(os.path.dirname(__file__), '../scanners/anime_movies.txt'))
        else:
            scanner_files.append(os.path.join(os.path.dirname(__file__), '../scanners/movies.txt'))

        normalized_input_title = normalize_title(title)

        for scanner_file in scanner_files:
            if not os.path.exists(scanner_file):
                continue
            with open(scanner_file, 'r', encoding='utf-8') as file:
                for line in file:
                    entry = line.strip()
                    if not entry or entry.startswith('#'):
                        continue

                    # Remove TMDB ID
                    entry_wo_tmdb = re.sub(r'\s*\{tmdb-\d+\}', '', entry)
                    # Extract title and year
                    m = re.match(r'^(.*?)\s+\((\d{4})\)$', entry_wo_tmdb)
                    if m:
                        scanner_title = m.group(1)
                        scanner_year = m.group(2)
                    else:
                        scanner_title = entry_wo_tmdb.strip()
                        scanner_year = None

                    normalized_scanner_title = normalize_title(scanner_title)
                    if normalized_input_title == normalized_scanner_title:
                        if not year or not scanner_year or str(year) == str(scanner_year):
                            matches.append(entry)

        return matches
    
    def _is_title_match(self, title1, title2):
        from src.utils.scan_logic import normalize_title
        # Normalize and compare
        return normalize_title(title1) == normalize_title(title2)

    def _extract_folder_metadata(self, folder_name):
        # Find the first 4-digit year (1900-2099) anywhere in the folder name
        year_match = re.search(r'(19\d{2}|20\d{2})', folder_name)
        year = None
        clean_title = folder_name
        if year_match:
            year = year_match.group(1)
            # Remove the year and any separators around it from the title
            clean_title = re.sub(r'[\.\s\-\_\(\)\[\]]*' + re.escape(year) + r'[\.\s\-\_\(\)\[\]]*', ' ', folder_name, count=1)
        # Remove patterns to clean up the title
        clean_title = clean_title_with_patterns(clean_title)
        # --- Deduplicate repeated words/phrases ---
        clean_title = deduplicate_phrases(clean_title)
        # --- PATCH: Restore titles like "9-1-1 Lone Star" if original matches ---
        if re.match(r'9-1-1(\.| )?Lone\.?Star', folder_name, re.IGNORECASE):
            clean_title = "9-1-1 Lone Star"
        if not clean_title.strip():
            # Fallback: use the folder name (minus year) if cleaning wipes everything
            clean_title = re.sub(r'[\.\s\-\_\(\)\[\]]*' + re.escape(year) + r'[\.\s\-\_\(\)\[\]]*', ' ', folder_name, count=1) if year else folder_name
            clean_title = clean_title.strip()
        self.logger.debug(f"Original: '{folder_name}', Cleaned: '{clean_title}', Year: {year}")
        
        # Remove trailing season/volume number if year is unknown and title ends with a number
        if (year is None or str(year).lower() == "unknown") and re.search(r'\b\d+$', clean_title):
            known_numbered = [
                r'^24$', r'^9-1-1(\s|$)', r'^60\s?Minutes', r'^90\s?Day\s?Fianc[eé]'
            ]
            if not any(re.match(pat, clean_title, re.IGNORECASE) for pat in known_numbered):
                clean_title = re.sub(r'\b\d+$', '', clean_title).strip()
        
        # Always remove trailing season/volume number if title ends with a number and not a known numbered show
        if re.search(r'\b\d+$', clean_title):
            known_numbered = [
                r'^24$', r'^9-1-1(\s|$)', r'^60\s?Minutes', r'^90\s?Day\s?Fianc[eé]'
            ]
            if not any(re.match(pat, clean_title, re.IGNORECASE) for pat in known_numbered):
                clean_title = re.sub(r'\b\d+$', '', clean_title).strip()
        
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

    def _prompt_for_season_episode_info(self, is_tv=False, is_anime=False, is_wrestling=False):
        """Helper method to prompt user for season and episode information when manual processing is enabled."""
        if is_wrestling or not is_tv:
            return None, None, None  # No season/episode info for non-TV content
        
        # Check if manual processing is enabled
        manual_season = os.environ.get('MANUAL_SEASON_PROCESSING', 'false').lower() == 'true'
        manual_episode = os.environ.get('MANUAL_EPISODE_PROCESSING', 'false').lower() == 'true'
        
        if not manual_season and not manual_episode:
            return None, None, None  # Both disabled, use automatic detection
        
        # Don't clear screen - preserve context from previous screen
        print("\n" + "=" * 84)
        content_type = "Anime Series" if is_anime else "TV Series"
        print(f"MANUAL {content_type.upper()} PROCESSING".center(84))
        print("=" * 84)
        
        season_number = None
        episode_number = None
        episode_name = None
        
        if manual_season:
            print("\nSeason Information:")
            while True:
                season_input = input("Enter season number (0 for extras/specials, 1, 2, 3...) or press Enter to skip: ").strip()
                if not season_input:
                    season_number = None
                    break
                try:
                    season_number = int(season_input)
                    if season_number >= 0:  # Allow 0 for extras/specials
                        break
                    else:
                        print("Please enter a number 0 or greater (0 = extras/specials).")
                except ValueError:
                    print("Please enter a valid number.")
        
        if manual_episode:
            print("\nEpisode Information:")
            episode_input = input("Enter episode number/identifier (1, 2, S01, Extra, etc.) or press Enter to skip: ").strip()
            if episode_input:
                # Try to parse as integer first, otherwise keep as string for special episodes
                try:
                    episode_number = int(episode_input)
                except ValueError:
                    episode_number = episode_input  # Keep as string for special episodes
            
            # Optional episode name
            episode_name_input = input("Enter episode name (optional) or press Enter to skip: ").strip()
            if episode_name_input:
                episode_name = episode_name_input
        
        return season_number, episode_number, episode_name

    def _display_folder_header(self, subfolder_name, title, year, content_type, search_term, tmdb_id_for_search, media_files_count, scanner_matches_count, current_index, total_items):
        """Helper method to display consistent folder processing header without clearing screen."""
        print("=" * 84)
        print("FOLDER PROCESSING".center(84))
        print("=" * 84)
        print(f"\nProcessing: {subfolder_name}")
        print(f"  Title: {title}")
        print(f"  Year: {year if year else 'Unknown'}")
        print(f"  Type: {content_type}")
        print(f"  Search term: {search_term}")
        
        if tmdb_id_for_search:
            print(f"  TMDB ID for search term: {tmdb_id_for_search}")
        else:
            print(f"  TMDB ID for search term: Not found")
            
        print(f"  Media files detected: {media_files_count}")
        print(f"  Scanner Matches: {scanner_matches_count}")
        
        # Show current item count and progress bar
        bar_len = 30
        filled_len = int(bar_len * current_index // total_items)
        bar = '=' * filled_len + '-' * (bar_len - filled_len)
        percent = int(100 * current_index / total_items)
        print(f"\nItem {current_index} of {total_items} [{bar}] {percent}%")
        print("=" * 84)

    def _create_symlinks(self, subfolder_path, title, year, is_tv=False, is_anime=False, is_wrestling=False, tmdb_id=None, season_number=None, episode_number=None, episode_name=None):
        """
        Create symlinks from the source directory to the destination directory.
        For TV/Anime Series, creates a symlink for each episode in the format:
        'MEDIA TITLE (YEAR) {tmdb-TMDB_ID}' / 'Season X' / 'MEDIA TITLE (YEAR) - SXXEXX.ext'
        Sends one webhook per subfolder processed.

        CRITICAL FIX: Only process files that are NOT in scan history.
        """
        try:
            if not DESTINATION_DIRECTORY:
                self.logger.error("Destination directory not configured")
                print("\nError: Destination directory not configured. Please configure in settings.")
                return False

            if not os.path.exists(DESTINATION_DIRECTORY):
                os.makedirs(DESTINATION_DIRECTORY, exist_ok=True)
                self.logger.info(f"Created destination directory: {DESTINATION_DIRECTORY}")

            base_name = f"{title} ({year})" if year and not is_wrestling else title
            folder_name = f"{base_name} {{tmdb-{tmdb_id}}}" if tmdb_id else base_name
            
            # Sanitize for filesystem safety
            safe_base_name = sanitize_filename(base_name)
            safe_folder_name = sanitize_filename(folder_name)
            
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

            target_dir_path = os.path.join(dest_subdir, safe_folder_name)
            os.makedirs(target_dir_path, exist_ok=True)

            use_symlinks = os.environ.get('USE_SYMLINKS', 'true').lower() == 'true'

            episode_symlinks = []

            # --- CRITICAL FIX: Only process files not in scan history ---
            processed_any = False
            
            self.logger.info(f"DEBUG: Starting symlink creation for {subfolder_path}")
            self.logger.info(f"DEBUG: is_tv={is_tv}, is_wrestling={is_wrestling}, season_number={season_number}, episode_number={episode_number}, episode_name={episode_name}")

            if is_tv and not is_wrestling:
                self.logger.info(f"DEBUG: Processing TV show files in {subfolder_path}")
                for root, dirs, files in os.walk(subfolder_path):
                    media_files = [f for f in files if f.lower().endswith(('.mkv', '.mp4', '.avi', '.mov', '.wmv', '.flv'))]
                    self.logger.info(f"DEBUG: Found {len(media_files)} media files: {media_files}")
                    for idx, file in enumerate(sorted(media_files), 1):
                        source_file_path = os.path.join(root, file)
                        self.logger.info(f"DEBUG: Processing file {idx}: {source_file_path}")
                        
                        # SKIP if already in scan history
                        if source_file_path in GLOBAL_SCAN_HISTORY_SET:
                            self.logger.info(f"DEBUG: SKIPPING {file} - already in scan history")
                            continue

                        # Use provided season/episode info if available (from CSV import)
                        if season_number is not None:
                            self.logger.info(f"DEBUG: Using provided season_number={season_number}, episode_number={episode_number}, episode_name={episode_name}")
                            s_num = season_number
                            if episode_name:
                                # Special episode with name (like "Concept Art")
                                e_num = None
                                episode_label = episode_name
                                self.logger.info(f"DEBUG: Special episode with name: {episode_name}")
                            elif episode_number is not None:
                                # Check if episode_number is a string (special episode) or integer (regular episode)
                                if isinstance(episode_number, str) and not episode_number.isdigit():
                                    # String episode identifier like "The Road West"
                                    e_num = None
                                    episode_label = episode_number
                                    self.logger.info(f"DEBUG: Special episode with string identifier: {episode_number}")
                                else:
                                    # Numeric episode number
                                    e_num = int(episode_number) if isinstance(episode_number, str) else episode_number
                                    episode_label = f"E{e_num:02d}"
                                    self.logger.info(f"DEBUG: Regular episode with number: S{s_num:02d}E{e_num:02d}")
                            else:
                                e_num = idx
                                episode_label = f"E{e_num:02d}"
                                self.logger.info(f"DEBUG: Fallback to file index: S{s_num:02d}E{e_num:02d}")
                        else:
                            # Fallback to regex extraction from filename
                            ep_match = re.search(r'(?:[sS](\d{1,2}))?[\. _-]*[eE](\d{1,2})', file)
                            if ep_match:
                                s_num = int(ep_match.group(1)) if ep_match.group(1) else 1
                                e_num = int(ep_match.group(2))
                                episode_label = f"E{e_num:02d}"
                            else:
                                s_num = 1
                                e_num = idx  # fallback to file index for uniqueness
                                episode_label = f"E{e_num:02d}"

                        ext = os.path.splitext(file)[1]
                        
                        # Create episode symlink name based on season and episode type
                        if season_number is not None and episode_name:
                            # Special episode with name: "The X-Files (1993) - Concept Art.mkv"
                            ep_symlink_name = f"{base_name} - {episode_name}{ext}"
                        elif s_num == 0:
                            # Season 0 episodes: "SHOW NAME (YEAR) - INDICATOR.extension" (no S00 prefix)
                            if episode_label and episode_label != "E01":
                                # Use the episode identifier as the indicator
                                if episode_label.startswith('E'):
                                    # Remove E prefix for Season 0
                                    indicator = episode_label[1:] if len(episode_label) > 1 else episode_label
                                else:
                                    indicator = episode_label
                                ep_symlink_name = f"{base_name} - {indicator}{ext}"
                            else:
                                # Fallback for Season 0 without specific episode label
                                ep_symlink_name = f"{base_name} - Extra{ext}"
                        else:
                            # Regular season episodes: "The X-Files (1993) - S01E01.mkv"
                            ep_symlink_name = f"{base_name} - S{s_num:02d}{episode_label}{ext}"
                        
                        self.logger.info(f"DEBUG: Episode symlink name: {ep_symlink_name}")
                            
                        season_folder = f"Season {s_num}"
                        season_dir = os.path.join(target_dir_path, season_folder)
                        self.logger.info(f"DEBUG: Season directory: {season_dir}")
                        os.makedirs(season_dir, exist_ok=True)
                        dest_file_path = os.path.join(season_dir, ep_symlink_name)
                        self.logger.info(f"DEBUG: Destination file path: {dest_file_path}")

                        if os.path.islink(dest_file_path) or os.path.exists(dest_file_path):
                            self.logger.info(f"DEBUG: Removing existing file/symlink: {dest_file_path}")
                            os.remove(dest_file_path)
                        if use_symlinks:
                            self.logger.info(f"DEBUG: Creating symlink from {source_file_path} to {dest_file_path}")
                            os.symlink(source_file_path, dest_file_path)
                            self.logger.info(f"Created symlink: {dest_file_path} -> {source_file_path}")
                            print(f"📺 Created TV symlink: {dest_file_path}")
                        else:
                            import shutil
                            shutil.copy2(source_file_path, dest_file_path)
                            self.logger.info(f"Copied file: {source_file_path} -> {dest_file_path}")
                            print(f"📁 Copied TV file: {dest_file_path}")

                        episode_symlinks.append(dest_file_path)
                        append_to_scan_history(source_file_path)
                        processed_any = True

                # Send one webhook for the whole subfolder (first symlink as reference)
                if processed_any and episode_symlinks:
                    metadata = {}
                    try:
                        tmdb = TMDB()
                        details = {}
                        if tmdb_id:
                            details = tmdb.get_tv_details(tmdb_id)
                        else:
                            results = tmdb.search_tv(title)
                            details = results[0] if results else {}
                        metadata['title'] = details.get('name') or title
                        metadata['year'] = (details.get('first_air_date') or str(year or ""))[:4]
                        metadata['description'] = details.get('overview', '')
                        poster_path = details.get('poster_path')
                        if poster_path:
                            metadata['poster'] = f"https://image.tmdb.org/t/p/w500{poster_path}"
                        else:
                            metadata['poster'] = None
                        metadata['tmdb_id'] = details.get('id') or tmdb_id
                    except Exception as e:
                        self.logger.warning(f"Could not fetch TMDB metadata: {e}")
                        metadata = {
                            'title': title,
                            'year': year,
                            'description': '',
                            'poster': None,
                            'tmdb_id': tmdb_id
                        }
                    symlink_path = episode_symlinks[0] if episode_symlinks else target_dir_path
                    send_symlink_creation_notification(
                        metadata['title'],
                        metadata['year'],
                        metadata['poster'],
                        metadata['description'],
                        symlink_path,
                        metadata['tmdb_id']
                    )

            else:
                # Movie/Anime Movie/Wrestling logic
                for root, dirs, files in os.walk(subfolder_path):
                    for file in files:
                        source_file_path = os.path.join(root, file)
                        # SKIP if already in scan history
                        if source_file_path in GLOBAL_SCAN_HISTORY_SET:
                            continue

                        file_ext = os.path.splitext(file)[1]
                        dest_file_name = f"{safe_base_name}{file_ext}"
                        dest_file_path = os.path.join(target_dir_path, dest_file_name)
                        if os.path.islink(dest_file_path) or os.path.exists(dest_file_path):
                            os.remove(dest_file_path)
                        if use_symlinks:
                            os.symlink(source_file_path, dest_file_path)
                            self.logger.info(f"Created symlink: {dest_file_path} -> {source_file_path}")
                        else:
                            shutil.copy2(source_file_path, dest_file_path)
                            self.logger.info(f"Copied file: {source_file_path} -> {dest_file_path}")

                        append_to_scan_history(source_file_path)
                        processed_any = True

                # Send one webhook for the movie folder
                if processed_any:
                    metadata = {}
                    try:
                        tmdb = TMDB()
                        details = {}
                        if tmdb_id:
                            details = tmdb.get_movie_details(tmdb_id)
                        else:
                            results = tmdb.search_movie(title)
                            details = results[0] if results else {}
                        metadata['title'] = details.get('title') or title
                        metadata['year'] = (details.get('release_date') or str(year or ""))[:4]
                        metadata['description'] = details.get('overview', '')
                        poster_path = details.get('poster_path')
                        if poster_path:
                            metadata['poster'] = f"https://image.tmdb.org/t/p/w500{poster_path}"
                        else:
                            metadata['poster'] = None
                        metadata['tmdb_id'] = details.get('id') or tmdb_id
                    except Exception as e:
                        self.logger.warning(f"Could not fetch TMDB metadata: {e}")
                        metadata = {
                            'title': title,
                            'year': year,
                            'description': '',
                            'poster': None,
                            'tmdb_id': tmdb_id
                        }
                    send_symlink_creation_notification(
                        metadata['title'],
                        metadata['year'],
                        metadata['poster'],
                        metadata['description'],
                        target_dir_path,
                        metadata['tmdb_id']
                    )

            if processed_any:
                self.logger.info(f"Successfully created links in: {target_dir_path}")
                print(f"\nSuccessfully created links in: {target_dir_path}")
            else:
                self.logger.info(f"No new files to process in: {subfolder_path}")
                print(f"\nNo new files to process in: {subfolder_path}")
            return processed_any

        except Exception as e:
            self.logger.error(f"Error creating symlinks: {e}")
            print(f"\nError creating links: {e}")
            return False

    def _create_symlink_for_single_file(self, file_path, title, year, is_tv=False, is_anime=False, is_wrestling=False, tmdb_id=None, season_number=None, episode_number=None, episode_name=None, ignore_scan_history=False):
        """
        Create a symlink for a single specific file (used in CSV import).
        This is different from _create_symlinks which processes all files in a directory.
        """
        try:
            if not DESTINATION_DIRECTORY:
                self.logger.error("Destination directory not configured")
                print("\nError: Destination directory not configured. Please configure in settings.")
                return False

            if not os.path.exists(DESTINATION_DIRECTORY):
                os.makedirs(DESTINATION_DIRECTORY, exist_ok=True)
                self.logger.info(f"Created destination directory: {DESTINATION_DIRECTORY}")

            # Check if file exists
            if not os.path.exists(file_path):
                self.logger.error(f"File does not exist: {file_path}")
                print(f"\nError: File does not exist: {file_path}")
                return False

            # Skip if already in scan history (unless user chose to ignore scan history)
            if not ignore_scan_history and file_path in GLOBAL_SCAN_HISTORY_SET:
                self.logger.info(f"File already in scan history, skipping: {file_path}")
                print(f"\n⚠️  File already processed (in scan history): {os.path.basename(file_path)}")
                return False
            elif ignore_scan_history and file_path in GLOBAL_SCAN_HISTORY_SET:
                self.logger.info(f"File in scan history but ignoring per user choice: {file_path}")
                print(f"\n🔄 File already processed but processing anyway (ignoring scan history): {os.path.basename(file_path)}")

            # Get file info
            filename = os.path.basename(file_path)
            file_ext = os.path.splitext(filename)[1]

            # Verify it's a media file
            if not file_ext.lower() in ('.mkv', '.mp4', '.avi', '.mov', '.wmv', '.flv'):
                self.logger.warning(f"Not a supported media file: {file_path}")
                print(f"\n⚠️  Not a supported media file: {filename}")
                return False

            # Setup directory structure
            base_name = f"{title} ({year})" if year and not is_wrestling else title
            folder_name = f"{base_name} {{tmdb-{tmdb_id}}}" if tmdb_id else base_name
            
            # Sanitize for filesystem safety
            safe_base_name = sanitize_filename(base_name)
            safe_folder_name = sanitize_filename(folder_name)
            
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

            target_dir_path = os.path.join(dest_subdir, safe_folder_name)
            os.makedirs(target_dir_path, exist_ok=True)

            use_symlinks = os.environ.get('USE_SYMLINKS', 'true').lower() == 'true'

            if is_tv and not is_wrestling:
                # TV Series processing
                if season_number is not None:
                    s_num = season_number
                    if episode_name:
                        # Special episode with name (like "Concept Art")
                        episode_label = episode_name
                        ep_symlink_name = f"{base_name} - {episode_name}{file_ext}"
                    elif episode_number is not None:
                        if s_num == 0:
                            # Season 0 episodes: "SHOW NAME (YEAR) - INDICATOR.extension" (no S00 prefix)
                            if isinstance(episode_number, str):
                                # String episode identifier
                                ep_symlink_name = f"{base_name} - {episode_number}{file_ext}"
                            else:
                                # Numeric episode number for Season 0
                                ep_symlink_name = f"{base_name} - {episode_number:02d}{file_ext}"
                        else:
                            # Regular season episodes
                            episode_label = f"E{episode_number:02d}"
                            ep_symlink_name = f"{base_name} - S{s_num:02d}E{episode_number:02d}{file_ext}"
                    else:
                        if s_num == 0:
                            # Season 0 without specific episode number
                            ep_symlink_name = f"{base_name} - Extra{file_ext}"
                        else:
                            episode_label = "E01"
                            ep_symlink_name = f"{base_name} - S{s_num:02d}E01{file_ext}"
                else:
                    # Fallback to regex extraction from filename
                    ep_match = re.search(r'(?:[sS](\d{1,2}))?[\. _-]*[eE](\d{1,2})', filename)
                    if ep_match:
                        s_num = int(ep_match.group(1)) if ep_match.group(1) else 1
                        e_num = int(ep_match.group(2))
                        if s_num == 0:
                            # Season 0 episodes: "SHOW NAME (YEAR) - EPISODE_NUM.extension" (no S00 prefix)
                            ep_symlink_name = f"{base_name} - {e_num:02d}{file_ext}"
                        else:
                            # Regular season episodes
                            episode_label = f"E{e_num:02d}"
                            ep_symlink_name = f"{base_name} - S{s_num:02d}E{e_num:02d}{file_ext}"
                    else:
                        s_num = 1
                        episode_label = "E01"
                        ep_symlink_name = f"{base_name} - S{s_num:02d}E01{file_ext}"

                season_folder = f"Season {s_num}"
                season_dir = os.path.join(target_dir_path, season_folder)
                os.makedirs(season_dir, exist_ok=True)
                dest_file_path = os.path.join(season_dir, ep_symlink_name)
            else:
                # Movie processing
                movie_symlink_name = f"{base_name}{file_ext}"
                dest_file_path = os.path.join(target_dir_path, movie_symlink_name)

            # Remove existing file/symlink if it exists
            if os.path.islink(dest_file_path) or os.path.exists(dest_file_path):
                os.remove(dest_file_path)

            # Create symlink or copy
            if use_symlinks:
                os.symlink(file_path, dest_file_path)
                self.logger.info(f"Created symlink: {dest_file_path} -> {file_path}")
                if is_tv:
                    print(f"📺 Created TV symlink: {os.path.basename(dest_file_path)}")
                else:
                    print(f"🎬 Created movie symlink: {os.path.basename(dest_file_path)}")
            else:
                import shutil
                shutil.copy2(file_path, dest_file_path)
                self.logger.info(f"Copied file: {file_path} -> {dest_file_path}")
                if is_tv:
                    print(f"📁 Copied TV file: {os.path.basename(dest_file_path)}")
                else:
                    print(f"📁 Copied movie file: {os.path.basename(dest_file_path)}")

            # Add to scan history
            append_to_scan_history(file_path)

            # Send notification
            try:
                from src.utils.webhooks import send_symlink_creation_notification
                from src.api.tmdb import TMDB
                
                metadata = {}
                try:
                    tmdb = TMDB()
                    details = {}
                    if tmdb_id:
                        if is_tv:
                            details = tmdb.get_tv_details(tmdb_id)
                        else:
                            details = tmdb.get_movie_details(tmdb_id)
                    else:
                        if is_tv:
                            results = tmdb.search_tv(title)
                        else:
                            results = tmdb.search_movie(title)
                        details = results[0] if results else {}
                    
                    if is_tv:
                        metadata['title'] = details.get('name') or title
                        metadata['year'] = (details.get('first_air_date') or str(year or ""))[:4]
                    else:
                        metadata['title'] = details.get('title') or title
                        metadata['year'] = (details.get('release_date') or str(year or ""))[:4]
                    
                    metadata['description'] = details.get('overview', '')
                    poster_path = details.get('poster_path')
                    if poster_path:
                        metadata['poster'] = f"https://image.tmdb.org/t/p/w500{poster_path}"
                    else:
                        metadata['poster'] = None
                    metadata['tmdb_id'] = details.get('id') or tmdb_id
                except Exception as e:
                    self.logger.warning(f"Could not fetch TMDB metadata: {e}")
                    metadata = {
                        'title': title,
                        'year': year,
                        'description': '',
                        'poster': None,
                        'tmdb_id': tmdb_id
                    }
                
                send_symlink_creation_notification(
                    metadata['title'],
                    metadata['year'],
                    metadata['poster'],
                    metadata['description'],
                    target_dir_path,
                    metadata['tmdb_id']
                )
            except Exception as e:
                self.logger.warning(f"Could not send notification: {e}")

            return True

        except Exception as e:
            self.logger.error(f"Error creating symlink for single file: {e}")
            print(f"\nError creating symlink: {e}")
            return False
    
    def _process_media_files(self):
        """Process media files in the directory."""
        global skipped_items_registry

        # --- Archive scan_history.txt if needed ---
        archive_scan_history_txt_to_db()

        # --- Use the global scan history set ---
        processed_paths = self.processed_paths

        try:
            # Get allowed extensions from environment
            allowed_extensions = os.environ.get('ALLOWED_EXTENSIONS', '.mp4,.mkv,.srt,.avi,.mov,.divx').lower().split(',')
            allowed_extensions = [ext.strip() for ext in allowed_extensions if ext.strip()]
            
            # Get all subdirectories that contain valid media files
            all_subdirs = []
            for d in os.listdir(self.directory_path):
                dir_path = os.path.join(self.directory_path, d)
                if os.path.isdir(dir_path):
                    # Check if directory contains any valid media files
                    has_media = False
                    try:
                        for file in os.listdir(dir_path):
                            if os.path.isfile(os.path.join(dir_path, file)):
                                file_ext = os.path.splitext(file)[1].lower()
                                if file_ext in allowed_extensions and file_ext != '.srt':  # Exclude subtitle files
                                    has_media = True
                                    break
                    except Exception as e:
                        self.logger.warning(f"Error checking directory {d}: {e}")
                        continue
                    
                    if has_media:
                        all_subdirs.append(d)
                    else:
                        self.logger.info(f"Skipping directory {d} - no valid media files found (allowed: {allowed_extensions})")
            
            if not all_subdirs:
                print("\nNo subdirectories found to process.")
                input("\nPress Enter to continue...")
                clear_screen()  # Clear screen when returning to main menu
                display_ascii_art()  # Show ASCII art
                return 0

            print(f"Found {len(all_subdirs)} total subdirectories")
            self.logger.info(f"Directory scan found {len(all_subdirs)} total subdirectories in {self.directory_path}")
            
            # Log some sample directory names for debugging
            if len(all_subdirs) > 0:
                sample_count = min(10, len(all_subdirs))
                self.logger.info(f"Sample directories: {all_subdirs[:sample_count]}")
                if len(all_subdirs) > 100:
                    self.logger.warning(f"Very high directory count ({len(all_subdirs)}) - this might indicate individual files being treated as directories")
            
            # Check SKIP_SYMLINKED setting to determine if we should pre-filter
            skip_symlinked = os.environ.get('SKIP_SYMLINKED', 'false').lower() == 'true'
            
            if skip_symlinked:
                print("Pre-filtering directories that already have symlinks...")
                print("⚠️  This may take some time for large directories (4000+ items)")
                print("    Building symlink cache for faster processing...")
                
                # Build a cache of all existing symlinks in destination (ONE-TIME OPERATION)
                symlink_cache = {}
                if DESTINATION_DIRECTORY and os.path.exists(DESTINATION_DIRECTORY):
                    cache_start = time.time()
                    print("Building symlink cache from destination directory...")
                    try:
                        for root, dirs, files in os.walk(DESTINATION_DIRECTORY):
                            # Cache directory symlinks
                            for d in dirs:
                                dest_dir_path = os.path.join(root, d)
                                if os.path.islink(dest_dir_path):
                                    try:
                                        real_path = os.path.realpath(dest_dir_path)
                                        symlink_cache[real_path] = dest_dir_path
                                    except Exception:
                                        pass
                            
                            # Cache file symlinks
                            for f in files:
                                dest_file_path = os.path.join(root, f)
                                if os.path.islink(dest_file_path):
                                    try:
                                        real_target = os.path.realpath(dest_file_path)
                                        # Store parent directory of the target file
                                        parent_dir = os.path.dirname(real_target)
                                        if parent_dir not in symlink_cache:
                                            symlink_cache[parent_dir] = []
                                        if isinstance(symlink_cache[parent_dir], list):
                                            symlink_cache[parent_dir].append(dest_file_path)
                                        else:
                                            symlink_cache[parent_dir] = [dest_file_path]
                                    except Exception:
                                        pass
                    except Exception as e:
                        print(f"Warning: Error building symlink cache: {e}")
                    
                    cache_time = time.time() - cache_start
                    print(f"Symlink cache built in {cache_time:.1f}s ({len(symlink_cache)} entries)")
                
                subdirs_to_process = []
                symlinked_count = 0
                total_dirs = len(all_subdirs)
                start_time = time.time()
                
                for i, subfolder_name in enumerate(all_subdirs):
                    # Calculate time estimates
                    if i > 0:
                        elapsed_time = time.time() - start_time
                        avg_time_per_dir = elapsed_time / i
                        remaining_dirs = total_dirs - i
                        estimated_remaining = avg_time_per_dir * remaining_dirs
                        
                        # Format time estimates
                        def format_time(seconds):
                            if seconds < 60:
                                return f"{int(seconds)}s"
                            elif seconds < 3600:
                                return f"{int(seconds/60)}m {int(seconds%60)}s"
                            else:
                                return f"{int(seconds/3600)}h {int((seconds%3600)/60)}m"
                        
                        eta_str = format_time(estimated_remaining)
                    else:
                        eta_str = "calculating..."
                    
                    # Show progress every 10 directories or at the end
                    if i % 50 == 0 or i == total_dirs - 1:
                        progress_percent = int((i + 1) / total_dirs * 100)
                        bar_length = 40
                        filled_length = int(bar_length * (i + 1) // total_dirs)
                        bar = '█' * filled_length + '░' * (bar_length - filled_length)
                        print(f"\rProgress: [{bar}] {progress_percent}% ({i + 1}/{total_dirs}) - Found {symlinked_count} with symlinks - ETA: {eta_str}", end='', flush=True)
                    
                    subfolder_path = os.path.join(self.directory_path, subfolder_name)
                    
                    # Fast symlink check using cache
                    has_symlink = False
                    real_subfolder_path = os.path.realpath(subfolder_path)
                    
                    # Check if directory itself is symlinked
                    if real_subfolder_path in symlink_cache:
                        has_symlink = True
                    
                    # Check if any files in this directory are symlinked
                    if not has_symlink and real_subfolder_path in symlink_cache:
                        cache_entry = symlink_cache[real_subfolder_path]
                        if isinstance(cache_entry, list) and cache_entry:
                            has_symlink = True
                    
                    if has_symlink:
                        symlinked_count += 1
                        self.logger.info(f"Pre-filtering: Skipping {subfolder_name} - symlinks already exist")
                    else:
                        subdirs_to_process.append(subfolder_name)
                
                total_time = time.time() - start_time
                print(f"\nFiltering completed in {int(total_time/60)}m {int(total_time%60)}s")
                print(f"After filtering: {len(subdirs_to_process)} directories to process, {symlinked_count} already have symlinks")
                subdirs = subdirs_to_process
            else:
                print("Symlink pre-filtering disabled")
                subdirs = all_subdirs

            if not subdirs:
                print("\nNo directories need processing (all already have symlinks).")
                input("\nPress Enter to continue...")
                clear_screen()
                display_ascii_art()
                return 0

            print(f"Will process {len(subdirs)} subdirectories")

            # Track progress
            processed = 0

            for subfolder_name in subdirs:
                subfolder_path = os.path.join(self.directory_path, subfolder_name)
                
                self.logger.info(f"DEBUG: Starting to process subfolder: {subfolder_name}")
                print(f"DEBUG: Processing folder: {subfolder_name}")

                # Initialize variables early to avoid scope issues
                title, year = self._extract_folder_metadata(subfolder_name)
                is_tv = self._detect_if_tv_show(subfolder_name)
                is_anime = self._detect_if_anime(subfolder_name)
                is_wrestling = False
                tmdb_id = None
                
                # Initialize season/episode variables
                season_number = None
                episode_number = None
                episode_name = None
                
                # Apply default content type logic based on parent directory
                default_flags = get_default_content_type_for_path(self.directory_path)
                if default_flags:
                    is_tv, is_anime, is_wrestling = default_flags

                # --- CHECK if any media file in subfolder is in scan history ---
                scan_history_check = is_any_media_file_in_scan_history(subfolder_path, processed_paths)
                self.logger.info(f"DEBUG: Scan history check for {subfolder_name}: {scan_history_check}")
                if scan_history_check:
                    print(f"\nWarning: Some files in '{subfolder_name}' appear to be already processed (in scan history).")
                    skip_choice = input("Skip this folder? (y/n): ").strip().lower()
                    self.logger.info(f"DEBUG: User choice for scan history skip: '{skip_choice}'")
                    if skip_choice == 'y':
                        self.logger.info(f"User chose to skip already processed (scan_history): {subfolder_path}")
                        print(f"DEBUG: SKIPPING due to user choice (scan history): {subfolder_name}")
                        continue
                    else:
                        print("Proceeding with processing...")
                        self.logger.info(f"DEBUG: User chose to proceed despite scan history")

                # --- SKIP LOGIC START ---
                # --- CHECK if subfolder is a symlink ---
                symlink_check = os.path.islink(subfolder_path)
                self.logger.info(f"DEBUG: Symlink check for {subfolder_name}: {symlink_check}")
                if symlink_check:
                    print(f"\nWarning: '{subfolder_name}' is a symlink.")
                    skip_choice = input("Skip this symlink folder? (y/n): ").strip().lower()
                    self.logger.info(f"DEBUG: User choice for symlink skip: '{skip_choice}'")
                    if skip_choice == 'y':
                        self.logger.info(f"User chose to skip symlink: {subfolder_path}")
                        print(f"DEBUG: SKIPPING due to user choice (symlink): {subfolder_name}")
                        continue
                    else:
                        print("Proceeding with processing symlink...")
                        self.logger.info(f"DEBUG: User chose to proceed with symlink")

                # 2. Check if already processed (symlink exists in destination)
                # For TV shows, check if this episode already exists, regardless of source quality
                already_processed = False
                self.logger.info(f"DEBUG: Checking for existing symlinks in destination for {subfolder_name}")
                if DESTINATION_DIRECTORY and os.path.exists(DESTINATION_DIRECTORY):
                    # Extract episode info from folder name to check for existing episodes
                    is_tv_episode = is_tv and re.search(r'[sS](\d+)[eE](\d+)', subfolder_name)
                    if is_tv_episode:
                        # For TV episodes, check if this episode already exists
                        season_match = re.search(r'[sS](\d+)[eE](\d+)', subfolder_name)
                        if season_match:
                            season_num = int(season_match.group(1))
                            episode_num = int(season_match.group(2))
                            
                            # Check for existing episode in destination using cleaned title
                            tv_series_dir = os.path.join(DESTINATION_DIRECTORY, "TV Series")
                            if os.path.exists(tv_series_dir):
                                for show_folder in os.listdir(tv_series_dir):
                                    show_path = os.path.join(tv_series_dir, show_folder)
                                    if os.path.isdir(show_path):
                                        # Check if this could be the same show (basic title matching)
                                        if any(word.lower() in show_folder.lower() for word in title.split() if len(word) > 3):
                                            season_folder = f"Season {season_num}"
                                            season_path = os.path.join(show_path, season_folder)
                                            if os.path.exists(season_path):
                                                # Look for existing episode file
                                                for episode_file in os.listdir(season_path):
                                                    episode_match = re.search(rf'[sS]{season_num:02d}[eE]{episode_num:02d}', episode_file)
                                                    if episode_match:
                                                        already_processed = True
                                                        self.logger.info(f"DEBUG: Found existing episode S{season_num:02d}E{episode_num:02d}: {episode_file}")
                                                        break
                                            if already_processed:
                                                break
                                    if already_processed:
                                        break
                    else:
                        # For non-TV or non-episode content, check if any media files are symlinked
                        for root, dirs, files in os.walk(subfolder_path):
                            for file in files:
                                if file.lower().endswith(('.mkv', '.mp4', '.avi', '.mov', '.wmv', '.flv')):
                                    source_file_path = os.path.join(root, file)
                                    
                                    # Quick check if this exact file is already in scan history
                                    if source_file_path in GLOBAL_SCAN_HISTORY_SET:
                                        already_processed = True
                                        self.logger.info(f"DEBUG: File {file} already in scan history")
                                        break
                            if already_processed:
                                break
                else:
                    self.logger.info(f"DEBUG: No destination directory configured, skipping symlink check")
                
                self.logger.info(f"DEBUG: Already processed check for {subfolder_name}: {already_processed}")
                
                # Check SKIP_SYMLINKED setting
                skip_symlinked = os.environ.get('SKIP_SYMLINKED', 'false').lower() == 'true'
                
                if already_processed:
                    if skip_symlinked:
                        # Automatically skip if setting is enabled
                        self.logger.info(f"Automatically skipping already processed (symlink exists) due to SKIP_SYMLINKED setting: {subfolder_path}")
                        print(f"Skipping '{subfolder_name}' - symlink already exists (auto-skip enabled)")
                        continue
                    else:
                        # Ask user if setting is disabled
                        print(f"\nWarning: '{subfolder_name}' appears to have already been processed (symlink exists in destination).")
                        skip_choice = input("Skip this already processed folder? (y/n): ").strip().lower()
                        self.logger.info(f"DEBUG: User choice for already processed skip: '{skip_choice}'")
                        if skip_choice == 'y':
                            self.logger.info(f"User chose to skip already processed (symlink exists): {subfolder_path}")
                            print(f"DEBUG: SKIPPING due to user choice (already processed): {subfolder_name}")
                            continue
                        else:
                            print("Proceeding with processing...")
                            self.logger.info(f"DEBUG: User chose to proceed despite already processed")
                # --- SKIP LOGIC END ---

                # --- NEW: Skip if any symlinked file for this subfolder exists in destination ---
                # Initialize search_term before using it
                search_term = title

                # Loop for processing the current folder with different options
                while True:
                    clear_screen()  # Clear screen before displaying folder processing menu
                    display_ascii_art()  # Show ASCII art
                    
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

                    # --- NEW: Display TMDB ID for search term ---
                    tmdb_id_for_search = None
                    try:
                        tmdb = TMDB()
                        if content_type in ("TV Series", "Anime Series"):
                            if year:
                                tmdb_results = tmdb.search_tv(search_term, year=year)
                            else:
                                tmdb_results = tmdb.search_tv(search_term)
                            if tmdb_results:
                                tmdb_id_for_search = tmdb_results[0].get('id')
                                tmdb_title = tmdb_results[0].get('name')
                                tmdb_year = (tmdb_results[0].get('first_air_date') or '')[:4]
                        else:
                            if year:
                                tmdb_results = tmdb.search_movie(search_term, year=year)
                            else:
                                tmdb_results = tmdb.search_movie(search_term)
                            if tmdb_results:
                                tmdb_id_for_search = tmdb_results[0].get('id')
                                tmdb_title = tmdb_results[0].get('title')
                                tmdb_year = (tmdb_results[0].get('release_date') or '')[:4]
                    except Exception as e:
                        tmdb_id_for_search = None

                    # ADD THIS BLOCK HERE:
                    media_exts = ('.mkv', '.mp4', '.avi', '.mov', '.wmv', '.flv')
                    media_files = [
                        f for f in os.listdir(subfolder_path)
                        if os.path.isfile(os.path.join(subfolder_path, f)) and f.lower().endswith(media_exts)
                    ]
                    
                    if year == "Unknown":
                        year = None
                    scanner_matches = self._check_scanner_lists(search_term, year, is_tv, is_anime)
                    
                    # Show current item count and progress
                    current_index = subdirs.index(subfolder_name) + 1
                    total_items = len(subdirs)
                    
                    # Use the new header function
                    self._display_folder_header(
                        subfolder_name, title, year, content_type, search_term, 
                        tmdb_id_for_search, len(media_files), len(scanner_matches),
                        current_index, total_items
                    )

                    # Prompt user if multiple scanner matches
                    selected_match = None
                    if len(scanner_matches) > 1:
                        # Limit to top 3 matches
                        limited_matches = scanner_matches[:3]
                        print("\nMultiple scanner matches found. Please select the correct one:")
                        for idx, entry in enumerate(limited_matches, 1):  # <-- Use limited_matches here
                            match = re.match(r'^(.+?)\s+\((\d{4})\)', entry)
                            if match:
                                display_title = match.group(1)
                                display_year = match.group(2)
                            else:
                                display_title = entry
                                display_year = "Unknown"
                            # Try to extract TMDB ID
                            tmdb_id_match = re.search(r'\{tmdb-(\d+)\}', entry)
                            display_tmdb_id = tmdb_id_match.group(1) if tmdb_id_match else ""
                            id_str = f" {{tmdb-{display_tmdb_id}}}" if display_tmdb_id else ""
                            print(f"{idx}. {display_title} ({display_year}){id_str}")
                        print("0. Additional options")
                        while True:
                            match_choice = input(f"\nSelect [1-{len(limited_matches)}] or 0 for options: ").strip()
                            if match_choice == "":
                                print("Please select an option.")
                                continue
                            if match_choice.isdigit():
                                match_idx = int(match_choice)
                                if 1 <= match_idx <= len(limited_matches):
                                    selected_entry = limited_matches[match_idx - 1]  # <-- Use limited_matches here
                                    # Parse title, year, tmdb_id from entry
                                    match = re.match(r'^(.+?)\s+\((\d{4})\)', selected_entry)
                                    if match:
                                        title = match.group(1)
                                        year = match.group(2)
                                    tmdb_id_match = re.search(r'\{tmdb-(\d+)\}', selected_entry)
                                    tmdb_id = tmdb_id_match.group(1) if tmdb_id_match else None
                                    print(f"\nSelected: {title} ({year}) {{tmdb-{tmdb_id}}}")
                                    # DON'T auto-process, let user confirm via main menu
                                    break  # Return to main processing menu
                                elif match_idx == 0:
                                    print("\nProceeding with manual identification...")
                                    break
                                else:
                                    print("Invalid selection. Please try again.")
                        # Continue to main menu regardless of selection
                        self.logger.info(f"DEBUG: Multi-scanner match processed for {subfolder_name}, continuing to main menu")
                        print(f"DEBUG: Multi-scanner match break for {subfolder_name}")
                        break
                    elif len(scanner_matches) == 1:
                        selected_entry = scanner_matches[0]
                        match = re.match(r'^(.+?)\s+\((\d{4})\)', selected_entry)
                        if match:
                            match_title = match.group(1)
                            match_year = match.group(2)
                        else:
                            match_title = selected_entry
                            match_year = year
                        tmdb_id_match = re.search(r'\{tmdb-(\d+)\}', selected_entry)
                        match_tmdb_id = tmdb_id_match.group(1) if tmdb_id_match else None

                        # --- TMDB search for the current search term (top 5 results, title only) ---
                        tmdb_results = []
                        try:
                            tmdb = TMDB()
                            if content_type in ("TV Series", "Anime Series"):
                                tmdb_results = tmdb.search_tv(search_term)
                            else:
                                tmdb_results = tmdb.search_movie(search_term)
                        except Exception:
                            tmdb_results = []

                        print(f"\nScanner match: {match_title} ({match_year}) {{tmdb-{match_tmdb_id}}}")

                        # Show TMDB top 5 results
                        tmdb_choices = []
                        if tmdb_results:
                            print("\nTMDB Search Results:")
                            for idx, result in enumerate(tmdb_results[:5], 1):
                                t_title = result.get('name') or result.get('title')
                                t_year = (result.get('first_air_date') or result.get('release_date') or '')[:4]
                                t_id = result.get('id')
                                print(f"{idx}. {t_title} ({t_year}) {{tmdb-{t_id}}}")
                                tmdb_choices.append({
                                    'title': t_title,
                                    'year': t_year,
                                    'tmdb_id': str(t_id)
                                })
                            print("0. None of these / Manual entry")
                        else:
                            print("\nTMDB Search Results: None found.")

                        print("\nOptions:")
                        print("1. Accept Scanner match")
                        if tmdb_choices:
                            print("2. Select a TMDB match")
                            print("3. Change search term")
                            print("4. Change content type")
                            print("5. Manual TMDB ID")
                            print("6. Flag this item")
                            print("7. Skip this folder")
                            print("8. Refresh Script (keep directory)")  # <-- Add here
                            print("0. Quit")
                        else:
                            print("2. Change search term")
                            print("3. Change content type")
                            print("4. Manual TMDB ID")
                            print("5. Flag this item")
                            print("6. Skip this folder")
                            print("7. Refresh Script (keep directory)")  # <-- Add here
                            print("0. Quit")

                        action_choice = input("\nSelect option: ").strip()
                        if action_choice == "":
                            print("Please select an option.")
                            continue
                        if action_choice == "1":
                            # Accept Scanner match - create symlinks automatically
                            title = match_title
                            year = match_year
                            tmdb_id = match_tmdb_id
                            print(f"\n✅ Scanner match accepted: {title} ({year}) {{tmdb-{tmdb_id}}}")
                            
                            # Get season/episode info if TV series and not already set
                            if is_tv and not is_wrestling and season_number is None:
                                season_number, episode_number, episode_name = self._prompt_for_season_episode_info(is_tv, is_anime, is_wrestling)
                            
                            # Automatically create symlinks after scanner match selection
                            print(f"\n🔗 Creating symlinks for {title} ({year})...")
                            if self._create_symlinks(subfolder_path, title, year, is_tv, is_anime, is_wrestling, tmdb_id, season_number, episode_number, episode_name):
                                processed += 1
                                append_to_scan_history(subfolder_path)
                                trigger_plex_refresh()
                                print(f"\n✅ Successfully processed: {title} ({year})")
                                input("\nPress Enter to continue...")
                                clear_screen()
                                display_ascii_art()
                            else:
                                print(f"\n❌ Failed to create symlinks for: {title} ({year})")
                                input("\nPress Enter to continue...")
                            break  # Exit the folder processing
    
                        elif tmdb_choices and action_choice == "2":
                            # Let user pick from TMDB results
                            while True:
                                tmdb_pick = input("\nSelect TMDB result [1-5] or 0 to cancel: ").strip()
                                if tmdb_pick == "0":
                                    break
                                if tmdb_pick.isdigit() and 1 <= int(tmdb_pick) <= len(tmdb_choices):
                                    pick = tmdb_choices[int(tmdb_pick)-1]
                                    title = pick['title']
                                    year = pick['year']
                                    tmdb_id = pick['tmdb_id']
                                    print(f"\n✅ TMDB result selected: {title} ({year}) {{tmdb-{tmdb_id}}}")
                                    
                                    # Get season/episode info if TV series and not already set
                                    if is_tv and not is_wrestling and season_number is None:
                                        season_number, episode_number, episode_name = self._prompt_for_season_episode_info(is_tv, is_anime, is_wrestling)
                                    
                                    # Automatically create symlinks after TMDB selection
                                    print(f"\n🔗 Creating symlinks for {title} ({year})...")
                                    if self._create_symlinks(subfolder_path, title, year, is_tv, is_anime, is_wrestling, tmdb_id, season_number, episode_number, episode_name):
                                        processed += 1
                                        append_to_scan_history(subfolder_path)
                                        trigger_plex_refresh()
                                        print(f"\n✅ Successfully processed: {title} ({year})")
                                        input("\nPress Enter to continue...")
                                        clear_screen()
                                        display_ascii_art()
                                    else:
                                        print(f"\n❌ Failed to create symlinks for: {title} ({year})")
                                        input("\nPress Enter to continue...")
                                    break  # Exit the folder processing
                                else:
                                    print("Invalid selection. Please try again.")
                            self.logger.info(f"DEBUG: Single scanner match - TMDB selection processed and symlinks created for {subfolder_name}")
                            break  # Break out of main processing loop for this folder
                        elif (tmdb_choices and action_choice == "3") or (not tmdb_choices and action_choice == "2"):
                            # Change search term and re-run TMDB search
                            while True:
                                new_search = input(f"Enter new search term [{search_term}]: ").strip()
                                if new_search:
                                    search_term = new_search  # Do NOT clean user-entered search term
                                else:
                                    # If user presses enter, keep previous term
                                    new_search = clean_title_with_patterns(search_term)

                                # Run new TMDB search
                                try:
                                    tmdb = TMDB()
                                    if content_type in ("TV Series", "Anime Series"):
                                        tmdb_results = tmdb.search_tv(search_term)
                                    else:
                                        tmdb_results = tmdb.search_movie(search_term)
                                except Exception:
                                    tmdb_results = []

                                if tmdb_results:
                                    print(f"\nTMDB Search Results for '{search_term}':")
                                    tmdb_choices = []
                                    for idx, result in enumerate(tmdb_results[:5], 1):
                                        t_title = result.get('name') or result.get('title')
                                        t_year = (result.get('first_air_date') or result.get('release_date') or '')[:4]
                                        t_id = result.get('id')
                                        print(f"{idx}. {t_title} ({t_year}) {{tmdb-{t_id}}}")
                                        tmdb_choices.append({
                                            'title': t_title,
                                            'year': t_year,
                                            'tmdb_id': str(t_id)
                                        })
                                    print("0. Enter a new search term")
                                    print("9. Skip and return to previous menu")
                                    while True:
                                        tmdb_pick = input("\nSelect TMDB result [1-5], 0 for new search, 9 to skip: ").strip()
                                        if tmdb_pick == "0":
                                            # Prompt for new search term and re-run TMDB search
                                            new_search = input(f"Enter new search term [{search_term}]: ").strip()
                                            if new_search:
                                                search_term = new_search
                                            # Re-run TMDB search with the new term
                                            try:
                                                tmdb = TMDB()
                                                if content_type in ("TV Series", "Anime Series"):
                                                    tmdb_results = tmdb.search_tv(search_term)
                                                else:
                                                    tmdb_results = tmdb.search_movie(search_term)
                                            except Exception:
                                                tmdb_results = []
                                            # Redisplay results
                                            if tmdb_results:
                                                print(f"\nTMDB Search Results for '{search_term}':")
                                                tmdb_choices = []
                                                for idx, result in enumerate(tmdb_results[:5], 1):
                                                    t_title = result.get('name') or result.get('title')
                                                    t_year = (result.get('first_air_date') or result.get('release_date') or '')[:4]
                                                    t_id = result.get('id')
                                                    print(f"{idx}. {t_title} ({t_year}) {{tmdb-{t_id}}}")
                                                    tmdb_choices.append({
                                                        'title': t_title,
                                                        'year': t_year,
                                                        'tmdb_id': str(t_id)
                                                    })
                                                print("0. Enter a new search term")
                                                print("9. Skip and return to previous menu")
                                            else:
                                                print("\nNo TMDB results found. Try another search term or skip.")
                                                print("0. Enter a new search term")
                                                print("9. Skip and return to previous menu")
                                            continue
                                        elif tmdb_pick == "9":
                                            break  # Return to previous menu
                                        elif tmdb_pick.isdigit() and 1 <= int(tmdb_pick) <= len(tmdb_choices):
                                            pick = tmdb_choices[int(tmdb_pick)-1]
                                            title = pick['title']
                                            year = pick['year']
                                            tmdb_id = pick['tmdb_id']
                                            print(f"\n✅ TMDB result selected: {title} ({year}) {{tmdb-{tmdb_id}}}")
                                            
                                            # Get season/episode info if TV series and not already set
                                            if is_tv and not is_wrestling and season_number is None:
                                                season_number, episode_number, episode_name = self._prompt_for_season_episode_info(is_tv, is_anime, is_wrestling)
                                            
                                            # Automatically create symlinks after TMDB selection
                                            print(f"\n🔗 Creating symlinks for {title} ({year})...")
                                            if self._create_symlinks(subfolder_path, title, year, is_tv, is_anime, is_wrestling, tmdb_id, season_number, episode_number, episode_name):
                                                processed += 1
                                                append_to_scan_history(subfolder_path)
                                                trigger_plex_refresh()
                                                print(f"\n✅ Successfully processed: {title} ({year})")
                                                input("\nPress Enter to continue...")
                                                clear_screen()
                                                display_ascii_art()
                                            else:
                                                print(f"\n❌ Failed to create symlinks for: {title} ({year})")
                                                input("\nPress Enter to continue...")
                                            break  # Exit the folder processing
    
                                        else:
                                            print("Invalid selection. Please try again.")
                            self.logger.info(f"DEBUG: Change search term - TMDB selection processed and symlinks created for {subfolder_name}")
                            break  # Break out of main processing loop for this folder
                        elif action_choice == "4":
                            # Change content type - show options without clearing screen
                            print("\n" + "=" * 50)
                            print("CHANGE CONTENT TYPE".center(50))
                            print("=" * 50)
                            print("Select new content type:")
                            print("1. Movie")
                            print("2. TV Series")
                            print("3. Anime Movie")
                            print("4. Anime Series")
                            print("5. Wrestling")
                            print("0. Cancel")
                            type_choice = input("\nSelect type: ").strip()
                            if type_choice == "1":
                                is_tv = False
                                is_anime = False
                                is_wrestling = False
                                print("✅ Content type changed to Movie")
                            elif type_choice == "2":
                                is_tv = True
                                is_anime = False
                                is_wrestling = False
                                print("✅ Content type changed to TV Series")
                            elif type_choice == "3":
                                is_tv = False
                                is_anime = True
                                is_wrestling = False
                                print("✅ Content type changed to Anime Movie")
                            elif type_choice == "4":
                                is_tv = True
                                is_anime = True
                                is_wrestling = False
                                print("✅ Content type changed to Anime Series")
                            elif type_choice == "5":
                                is_tv = False
                                is_anime = False
                                is_wrestling = True
                                print("✅ Content type changed to Wrestling")
                            elif type_choice == "0":
                                print("Content type change cancelled")
                                continue  # Go back to previous menu
                            else:
                                print("Invalid type. Returning to previous menu.")
                                continue
                            
                            # Prompt for season/episode info if TV content and manual processing is enabled
                            if is_tv and not is_wrestling:
                                season_number, episode_number, episode_name = self._prompt_for_season_episode_info(is_tv, is_anime, is_wrestling)
                            else:
                                season_number, episode_number, episode_name = None, None, None
                            continue  # <--- THIS LINE ENSURES THE LOOP RESTARTS WITH NEW CONTENT TYPE
                        elif (tmdb_choices and action_choice == "5") or (not tmdb_choices and action_choice == "4"):
                            # Manual TMDB ID
                            new_tmdb_id = input(f"Enter TMDB ID [{tmdb_id if tmdb_id else ''}]: ").strip()
                            if new_tmdb_id:
                                tmdb_id = new_tmdb_id
                                try:
                                    tmdb = TMDB()
                                    if content_type in ("TV Series", "Anime Series"):
                                        details = tmdb.get_tv_details(tmdb_id)
                                        title = details.get('name', title)
                                        year = (details.get('first_air_date') or str(year or ""))[:4]
                                    else:
                                        details = tmdb.get_movie_details(tmdb_id)
                                        title = details.get('title', title)
                                        year = (details.get('release_date') or str(year or ""))[:4]
                                    print(f"\nTMDB lookup successful: {title} ({year}) {{tmdb-{tmdb_id}}}")
                                    # Proceed to symlink creation or next step
                                    if self._create_symlinks(subfolder_path, title, year, is_tv, is_anime, is_wrestling, tmdb_id, season_number, episode_number, episode_name):
                                        processed += 1
                                        append_to_scan_history(subfolder_path)
                                        trigger_plex_refresh()
                                        input("\nPress Enter to continue...")
                                        clear_screen()
                                        display_ascii_art()
                                except Exception as e:
                                    print(f"\nError fetching TMDB details: {e}")
                            continue
                        elif (tmdb_choices and action_choice == "6") or (not tmdb_choices and action_choice == "5"):
                            # Flag this item
                            write_flag_to_csv({
                                "File Path": subfolder_path,
                                "Cleaned Title": title,
                                "Year": year if year else "",
                                "Content Type": content_type
                            })
                            append_to_scan_history(subfolder_path)
                            print(f"\nItem flagged and saved to {FLAGGED_CSV}.")
                            clear_screen()
                            display_ascii_art()
                            break
                        elif (tmdb_choices and action_choice == "7") or (not tmdb_choices and action_choice == "6"):
                            # Skip this folder
                            print(f"\nSkipping folder: {subfolder_name}")
                            skipped_items_registry.append({
                                'subfolder': subfolder_name,
                                'path': subfolder_path,
                                'skipped_date': datetime.datetime.now().isoformat()
                            })
                            save_skipped_items(skipped_items_registry)
                            input("\nPress Enter to continue...")
                            clear_screen()
                            display_ascii_art()
                            break
                        elif (tmdb_choices and action_choice == "8") or (not tmdb_choices and action_choice == "7"):
                            save_resume_path(self.directory_path)
                            print("\nRefreshing script and resuming scan...")
                            sys.stdout.flush()
                            python = sys.executable
                            os.execv(python, [python] + sys.argv)
                        elif action_choice == "0":
                            if input("\nAre you sure you want to quit the scan? (y/n): ").strip().lower() == 'y':
                                print("\nScan cancelled.")
                                input("\nPress Enter to continue...")
                                clear_screen()
                                display_ascii_art()
                                return -1
                        else:
                            print("Invalid option. Please try again.")
                            input("\nPress Enter to continue...")
                            clear_screen()
                            display_ascii_art()
                    # Show options for this subfolder (if no scanner match or user chose manual)
                    print("\nOptions:")
                    print("1. Accept as is")
                    print("2. Change search term")
                    print("3. Change content type")
                    print("4. Manual TMDB ID")
                    print("5. Skip (save for later review)")
                    print("6. Flag this item")
                    print("7. Refresh Script (keep directory)")
                    print("0. Quit")

                    choice = input("\nSelect option: ").strip()
                    if choice == "":
                        print("Please select an option.")
                        continue

                    self.logger.info(f"DEBUG: User selected main menu option: '{choice}' for {subfolder_name}")

                    if choice == "1":
                        self.logger.info(f"DEBUG: User chose 'Accept as is' - calling _create_symlinks for {subfolder_name}")
                        if self._create_symlinks(subfolder_path, title, year, is_tv, is_anime, is_wrestling, tmdb_id, season_number, episode_number, episode_name):
                            processed += 1
                            append_to_scan_history(subfolder_path)
                            trigger_plex_refresh()
                            clear_screen()
                            display_ascii_art()
                        break
                    elif choice == "2":
                        # Prompt for new search term and year
                        new_search = input(f"Enter new search term [{search_term}]: ").strip()
                        if new_search:
                            search_term = new_search  # Do NOT clean user-entered search term
                        # Immediately run TMDB search and present results
                        try:
                            tmdb = TMDB()
                            if content_type in ("TV Series", "Anime Series"):
                                tmdb_results = tmdb.search_tv(search_term)
                            else:
                                tmdb_results = tmdb.search_movie(search_term)
                        except Exception:
                            tmdb_results = []

                        if tmdb_results:
                            print(f"\nTMDB Search Results for '{search_term}':")
                            tmdb_choices = []
                            for idx, result in enumerate(tmdb_results[:5], 1):
                                t_title = result.get('name') or result.get('title')
                                t_year = (result.get('first_air_date') or result.get('release_date') or '')[:4]
                                t_id = result.get('id')
                                print(f"{idx}. {t_title} ({t_year}) {{tmdb-{t_id}}}")
                                tmdb_choices.append({
                                    'title': t_title,
                                    'year': t_year,
                                    'tmdb_id': str(t_id)
                                })
                            print("0. Enter a new search term")
                            print("9. Skip and return to previous menu")
                            while True:
                                tmdb_pick = input("\nSelect TMDB result [1-5], 0 for new search, 9 to skip: ").strip()
                                if tmdb_pick == "0":
                                    # Prompt for new search term and re-run TMDB search
                                    new_search = input(f"Enter new search term [{search_term}]: ").strip()
                                    if new_search:
                                        search_term = new_search
                                    # Re-run TMDB search with the new term
                                    try:
                                        tmdb = TMDB()
                                        if content_type in ("TV Series", "Anime Series"):
                                            tmdb_results = tmdb.search_tv(search_term)
                                        else:
                                            tmdb_results = tmdb.search_movie(search_term)
                                    except Exception:
                                        tmdb_results = []
                                    # Redisplay results
                                    if tmdb_results:
                                        print(f"\nTMDB Search Results for '{search_term}':")
                                        tmdb_choices = []
                                        for idx, result in enumerate(tmdb_results[:5], 1):
                                            t_title = result.get('name') or result.get('title')
                                            t_year = (result.get('first_air_date') or result.get('release_date') or '')[:4]
                                            t_id = result.get('id')
                                            print(f"{idx}. {t_title} ({t_year}) {{tmdb-{t_id}}}")
                                            tmdb_choices.append({
                                                'title': t_title,
                                                'year': t_year,
                                                'tmdb_id': str(t_id)
                                            })
                                        print("0. Enter a new search term")
                                        print("9. Skip and return to previous menu")
                                    else:
                                        print("\nNo TMDB results found. Try another search term or skip.")
                                        print("0. Enter a new search term")
                                        print("9. Skip and return to previous menu")
                                    continue
                                elif tmdb_pick == "9":
                                    break  # Return to previous menu
                                elif tmdb_pick.isdigit() and 1 <= int(tmdb_pick) <= len(tmdb_choices):
                                    pick = tmdb_choices[int(tmdb_pick)-1]
                                    title = pick['title']
                                    year = pick['year']
                                    tmdb_id = pick['tmdb_id']
                                    print(f"\n✅ TMDB result selected: {title} ({year}) {{tmdb-{tmdb_id}}}")
                                    
                                    # Get season/episode info if TV series and not already set
                                    if is_tv and not is_wrestling and season_number is None:
                                        season_number, episode_number, episode_name = self._prompt_for_season_episode_info(is_tv, is_anime, is_wrestling)
                                    
                                    # Automatically create symlinks after TMDB selection
                                    print(f"\n🔗 Creating symlinks for {title} ({year})...")
                                    if self._create_symlinks(subfolder_path, title, year, is_tv, is_anime, is_wrestling, tmdb_id, season_number, episode_number, episode_name):
                                        processed += 1
                                        append_to_scan_history(subfolder_path)
                                        trigger_plex_refresh()
                                        print(f"\n✅ Successfully processed: {title} ({year})")
                                        input("\nPress Enter to continue...")
                                        clear_screen()
                                        display_ascii_art()
                                    else:
                                        print(f"\n❌ Failed to create symlinks for: {title} ({year})")
                                        input("\nPress Enter to continue...")
                                    break  # Exit the folder processing
    
                                else:
                                    print("Invalid selection. Please try again.")
                            self.logger.info(f"DEBUG: Main menu option 2 - TMDB selection processed and symlinks created for {subfolder_name}")
                            break  # Break out of main processing loop for this folder
                        else:
                            print("\nNo TMDB results found. Try another search term or skip.")
                            print("0. Enter a new search term")
                            print("9. Skip and return to previous menu")
                            tmdb_pick = input("\nSelect option: ").strip()
                            if tmdb_pick == "0":
                                continue  # Prompt for new search term again
                            elif tmdb_pick == "9":
                                break  # Return to previous menu
                            else:
                                print("Invalid selection. Please try again.")
                        continue  # After handling search term, return to main folder menu
                    elif choice == "3":
                        # Prompt for new content type and update variables
                        print("\nSelect new content type:")
                        print("1. Movie")
                        print("2. TV Series")
                        print("3. Anime Movie")
                        print("4. Anime Series")
                        print("5. Wrestling")
                        print("0. Cancel")
                        type_choice = input("Select type: ").strip()
                        if type_choice == "1":
                            is_tv = False
                            is_anime = False
                            is_wrestling = False
                        elif type_choice == "2":
                            is_tv = True
                            is_anime = False
                            is_wrestling = False
                        elif type_choice == "3":
                            is_tv = False
                            is_anime = True
                            is_wrestling = False
                        elif type_choice == "4":
                            is_tv = True
                            is_anime = True
                            is_wrestling = False
                        elif type_choice == "5":
                            is_tv = False
                            is_anime = False
                            is_wrestling = True
                        elif type_choice == "0":
                            continue  # Go back to previous menu
                        else:
                            print("Invalid type. Returning to previous menu.")
                            continue
                        
                        # Prompt for season/episode info if TV content and manual processing is enabled
                        if is_tv and not is_wrestling:
                            season_number, episode_number, episode_name = self._prompt_for_season_episode_info(is_tv, is_anime, is_wrestling)
                        else:
                            season_number, episode_number, episode_name = None, None, None
                        
                        continue  # <--- THIS LINE ENSURES THE LOOP RESTARTS WITH NEW CONTENT TYPE
                    elif choice == "4":
                        new_tmdb_id = input(f"Enter TMDB ID [{tmdb_id if tmdb_id else ''}]: ").strip()
                        if new_tmdb_id:
                            tmdb_id = new_tmdb_id
                            try:
                                tmdb = TMDB()
                                if content_type in ("TV Series", "Anime Series"):
                                    details = tmdb.get_tv_details(tmdb_id)
                                    title = details.get('name', title)
                                    year = (details.get('first_air_date') or str(year or ""))[:4]
                                else:
                                    details = tmdb.get_movie_details(tmdb_id)
                                    title = details.get('title', title)
                                    year = (details.get('release_date') or str(year or ""))[:4]
                                print(f"\nTMDB lookup successful: {title} ({year}) {{tmdb-{tmdb_id}}}")
                                # DON'T auto-process, break to return to menu for user confirmation
                                break
                            except Exception as e:
                                print(f"\nError fetching TMDB details: {e}")
                        continue
                    elif choice == "5":
                        # Skip this folder
                        self.logger.info(f"DEBUG: User selected option 5 - Skip folder: {subfolder_name}")
                        print(f"DEBUG: User manually skipping folder: {subfolder_name}")
                        print(f"\nSkipping folder: {subfolder_name}")
                        skipped_items_registry.append({
                            'subfolder': subfolder_name,
                            'path': subfolder_path,
                            'skipped_date': datetime.datetime.now().isoformat()
                        })
                        save_skipped_items(skipped_items_registry)
                        input("\nPress Enter to continue...")
                        clear_screen()
                        display_ascii_art()
                        break
                    elif choice == "6":
                        # FLAGGING LOGIC
                        self.logger.info(f"DEBUG: User selected option 6 - Flag item: {subfolder_name}")
                        print(f"DEBUG: User manually flagging folder: {subfolder_name}")
                        write_flag_to_csv({
                            "File Path": subfolder_path,
                            "Cleaned Title": title,
                            "Year": year if year else "",
                            "Content Type": content_type
                        })
                        append_to_scan_history(subfolder_path) # <-- Add this line to save flagged path
                        print(f"\nItem flagged and saved to {FLAGGED_CSV}.")
                        clear_screen()
                        display_ascii_art()
                        break  # Move to next item, do NOT process
                    elif choice == "7":
                        save_resume_path(self.directory_path)
                        print("\nRefreshing scan script...")
                        sys.stdout.flush()
                        python = sys.executable
                        os.execv(python, [python] + sys.argv)
                    elif choice == "0":
                        if input("Are you sure you want to quit the scan? (y/n): ").strip().lower() == 'y':
                            print("Scan cancelled.")
                            input("\nPress Enter to continue...")
                            clear_screen()
                            display_ascii_art()
                            return -1
                    else:
                        print("Invalid option. Please try again.")
                        input("\nPress Enter to continue...")
                        clear_screen()
                        display_ascii_art()
                
                # Add debug at end of each folder processing
                self.logger.info(f"DEBUG: Completed processing subfolder: {subfolder_name}")
                print(f"DEBUG: Finished with folder: {subfolder_name}")
                
            print(f"\nFinished processing {len(subdirs)} subdirectories.")
            self.logger.info(f"DEBUG: Finished processing all {len(subdirs)} subdirectories")
            input("\nPress Enter to continue...")
            clear_screen()
            display_ascii_art()
            return processed
        except Exception as e:
            self.logger.error(f"Error processing media files: {e}")
            print(f"Error: {e}")
            input("\nPress Enter to continue...")
            clear_screen()
            display_ascii_art()

    def _has_existing_symlink(self, subfolder_path, title, year, is_tv=False, is_anime=False, is_wrestling=False, tmdb_id=None):
        """
        Check if a symlink for the main media file(s) in this subfolder already exists in the destination directory.
        Uses comprehensive checking similar to individual scan logic.
        """
        if not DESTINATION_DIRECTORY:
            return False
            
        # Method 1: Check if any symlink in destination points to this subfolder (like individual scan)
        try:
            for root, dirs, files in os.walk(DESTINATION_DIRECTORY):
                # Check directory symlinks
                for d in dirs:
                    dest_dir_path = os.path.join(root, d)
                    if os.path.islink(dest_dir_path):
                        try:
                            if os.path.realpath(dest_dir_path) == os.path.realpath(subfolder_path):
                                self.logger.info(f"Found existing directory symlink pointing to {subfolder_path}: {dest_dir_path}")
                                return True
                        except Exception as e:
                            self.logger.warning(f"Error checking directory symlink: {dest_dir_path} -> {e}")
                
                # Check file symlinks that might point to files in this subfolder
                for f in files:
                    dest_file_path = os.path.join(root, f)
                    if os.path.islink(dest_file_path):
                        try:
                            real_target = os.path.realpath(dest_file_path)
                            # Check if the symlink points to any file in our subfolder
                            if real_target.startswith(os.path.realpath(subfolder_path)):
                                self.logger.info(f"Found existing file symlink pointing to file in {subfolder_path}: {dest_file_path} -> {real_target}")
                                return True
                        except Exception as e:
                            self.logger.warning(f"Error checking file symlink: {dest_file_path} -> {e}")
        except Exception as e:
            self.logger.warning(f"Error during comprehensive symlink check: {e}")
        
        # Method 2: Check expected destination path (original logic, but improved)
        try:
            # Format the base name with year for both folder and files
            base_name = title
            if year and not is_wrestling:
                base_name = f"{title} ({year})"
            folder_name = base_name
            if tmdb_id:
                folder_name = f"{base_name} {{tmdb-{tmdb_id}}}"
            
            # Sanitize for filesystem safety
            safe_base_name = sanitize_filename(base_name)
            safe_folder_name = sanitize_filename(folder_name)

            # Determine appropriate subdirectory based on content type
            if is_wrestling:
                dest_subdir = os.path.join(DESTINATION_DIRECTORY, "Wrestling")
            elif is_anime and is_tv:
                dest_subdir = os.path.join(DESTINATION_DIRECTORY, "Anime Series")
            elif is_anime and not is_tv:
                dest_subdir = os.path.join(DESTINATION_DIRECTORY, "Anime Movies")
            elif is_tv and not is_anime:
                dest_subdir = os.path.join(DESTINATION_DIRECTORY, "TV Series")
            else:
                dest_subdir = os.path.join(DESTINATION_DIRECTORY, "Movies")

            target_dir_path = os.path.join(dest_subdir, safe_folder_name)
            if os.path.exists(target_dir_path):
                # Check for any symlinked files in the target directory
                try:
                    for file in os.listdir(subfolder_path):
                        file_ext = os.path.splitext(file)[1]
                        dest_file_name = f"{safe_base_name}{file_ext}"
                        dest_file_path = os.path.join(target_dir_path, dest_file_name)
                        if os.path.islink(dest_file_path):
                            self.logger.info(f"Found existing symlink in expected location: {dest_file_path}")
                            return True
                except Exception as e:
                    self.logger.warning(f"Error checking expected destination files: {e}")
        except Exception as e:
            self.logger.warning(f"Error during expected path symlink check: {e}")
        
        return False

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
    # Process the directory using the full scan logic
    print(f"\nScanning directory: {clean_path}")
    result = processor._process_media_files()
    if result is not None and result >= 0:
        print(f"\nScan completed. Processed {result} items.")
        trigger_plex_refresh()  # <-- Add this line
    else:
        print("\nScan did not complete successfully.")
    input("\nPress Enter to continue...")
    clear_screen()  # Make sure we clear screen here before returning

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
            break
        # Check if user wants to return to main menu
        if dir_input.lower() in ('exit', 'quit', 'back', 'return'):
            if not directories:  # If no directories were added, return to main menu
                return
            break
        # Validate directory path
        clean_path = _clean_directory_path(dir_input)
        if os.path.isdir(clean_path):
            directories.append(clean_path)
        else:
            print(f"Error: {clean_path} is not a valid directory.")
    if not directories:
        print("\nNo valid directories to scan.")
        input("\nPress Enter to continue...")
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
        # Call the real scan logic
        result = processor._process_media_files()
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

# Fix the handle_monitor_management function to properly handle directories
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
        # status is {dir_id: True/False, ...}
        is_active = any(status.values())
        # Show current status
        if is_active:
            print("\n✅ Monitoring is ACTIVE")
        else:
            print("\n❌ Monitoring is INACTIVE")
            
        # Get all directories - this might be a dictionary with timestamp keys
        monitor_dirs = monitor_manager.get_monitored_directories()
        
        
        # Convert to a list of tuples for easier enumeration
        if isinstance(monitor_dirs, dict):
            # If it's a dictionary, create a list of (key, value) pairs
            directories = list(monitor_dirs.items())
        else:
            # If it's already a list or other iterable, use as is
            directories = list(enumerate(monitor_dirs))
        
        # Check pending files - this will be a list of file paths
        pending_files = monitor_manager.get_all_pending_files()
        pending_count = len(pending_files)
        
        # Build a map of directories to their pending files count
        dir_pending_map = {}
        for file in pending_files:
            if isinstance(file, dict) and 'directory_path' in file:
                dir_path = file['directory_path']
            elif isinstance(file, str):
                # Try to extract directory path from file path:
                dir_path = os.path.dirname(file)
            else:
                continue
                
            if dir_path in dir_pending_map:
                dir_pending_map[dir_path] += 1
            else:
                dir_pending_map[dir_path] = 1
        
        # Check active directories
        if directories:
            print(f"\nMonitored Directories: {len(directories)}")
            for i, (key, directory_info) in enumerate(directories, 1):
                # Extract directory information
                if isinstance(directory_info, dict):
                    dir_path = directory_info.get('path', '')
                    dir_name = directory_info.get('name', 'Unnamed')
                    
                    # If we still don't have a good name, try to extract from path
                    if not dir_name or dir_name == 'Unnamed':
                        if dir_path:
                            dir_name = os.path.basename(dir_path)
                        else:
                            dir_name = f"Directory {i}"
                elif isinstance(directory_info, str):
                    dir_path = directory_info
                    dir_name = os.path.basename(dir_path)
                else:
                    # Fallback
                    dir_path = str(directory_info) if directory_info else "Unknown"
                    dir_name = "Unknown Directory"
                
                # Status indicator
                is_active_dir = status.get(key, False)
                status_icon = "🟢" if is_active_dir else "🔴"
                
                # Get pending count
                pending_for_dir = dir_pending_map.get(dir_path, 0)
                
                # Display with pending count only if there are pending files
                pending_display = f" ({pending_for_dir} pending)" if pending_for_dir > 0 else ""
                print(f"{i}. {status_icon} {dir_name}: {dir_path}{pending_display}")
        else:
            print("\nNo directories being monitored.")
            
        # Show options
        print("\nOptions:")
        print("1. Add directory to monitor")
        print("2. Remove directory from monitoring")
        print("3. Toggle directory active state")
        print("4. Start all monitoring")
        print(f"5. Check pending files")
        print("0. Return to main menu")
        
        choice = input("\nEnter choice: ").strip()
        
        if choice == "1":
            # Add directory handling
            new_dir = input("\nEnter directory path to monitor: ").strip()
            new_dir = _clean_directory_path(new_dir)
            
            if not os.path.exists(new_dir):
                print(f"\nDirectory {new_dir} does not exist.")
                input("\nPress Enter to continue...")
                continue

            try:
                monitor_manager.add_directory(new_dir)
                print(f"\nDirectory {new_dir} added to monitoring.")
            except Exception as e:
                print(f"\nFailed to add directory: {e}")
            input("\nPress Enter to continue...")
            continue

        elif choice == "2":
            # Remove directory handling
            if not directories:
                print("\nNo directories to remove.")
                input("\nPress Enter to continue...")
                continue
            print("\nSelect a directory to remove:")
            for i, (key, directory_info) in enumerate(directories, 1):
                if isinstance(directory_info, dict):
                    dir_path = directory_info.get('path', '')
                    dir_name = directory_info.get('name', 'Unnamed')
                    if not dir_name or dir_name == 'Unnamed':
                        dir_name = os.path.basename(dir_path) if dir_path else f"Directory {i}"
                elif isinstance(directory_info, str):
                    dir_path = directory_info
                    dir_name = os.path.basename(dir_path)
                else:
                    dir_path = str(directory_info) if directory_info else "Unknown"
                    dir_name = "Unknown Directory"
                print(f"{i}. {dir_name}: {dir_path}")
            print("0. Cancel")
            sel = input("\nEnter number: ").strip()
            if sel == "0":
                continue
            try:
                sel_idx = int(sel) - 1
                if 0 <= sel_idx < len(directories):
                    key, _ = directories[sel_idx]
                    monitor_manager.remove_directory(key)
                    print("\nDirectory removed from monitoring.")
                else:
                    print("\nInvalid selection.")
            except Exception as e:
                print(f"\nError: {e}")
            input("\nPress Enter to continue...")
            continue

        elif choice == "3":
            dir_num = input("\nEnter number of directory to toggle: ").strip()
            try:
                dir_num = int(dir_num)
                if 1 <= dir_num <= len(directories):
                    # Get the key and directory info
                    key, directory_info = directories[dir_num-1]
                    try:
                        monitor_manager.toggle_directory_active(key)
                    except Exception as e:
                        print(f"\nError toggling directory state: {e}")
                        input("\nPress Enter to continue...")
                        continue
                    print(f"\nToggled active state for directory.")
                else:
                    print("\nInvalid directory number.")
            except ValueError:
                print("\nInvalid input. Please enter a number.")
            except Exception as e:
                print(f"\nError: {e}")
            input("\nPress Enter to continue...")
            
        elif choice == "4":
            # Start monitoring
            try:
                monitor_manager.start_monitoring()
                print("\nStarted monitoring for all active directories.")
            except Exception as e:
                print(f"\nError starting monitoring: {e}")
            
            input("\nPress Enter to continue...")
            
        elif choice == "5":
            # --- NEW: Check pending files implementation ---
            # Gather pending files per directory, filter out already scanned
            pending_files = monitor_manager.get_all_pending_files()
            scan_history = load_scan_history_set()
            # Build a map: dir_path -> [pending files]
            dir_pending_map = {}
            for file in pending_files:
                if isinstance(file, dict) and 'directory_path' in file:
                    dir_path = file['directory_path']
                    file_path = file.get('path') or file.get('file_path')
                elif isinstance(file, str):
                    file_path = file
                    dir_path = os.path.dirname(file)
                else:
                    continue
                # Only include if not in scan history
                if file_path and file_path not in scan_history:
                    dir_pending_map.setdefault(dir_path, []).append(file_path)
            if not dir_pending_map:
                print("\nNo new pending files to process.")
                input("\nPress Enter to continue...")
                continue
            # Show directories with pending files
            print("\nSelect a directory to process pending files:")
            dir_list = list(dir_pending_map.items())
            for idx, (dir_path, files) in enumerate(dir_list, 1):
                print(f"{idx}. {dir_path} ({len(files)} new)")
            print("0. Return to Monitor Management")
            sel = input("\nEnter number: ").strip()
            if sel == "0":
                continue
            try:
                sel_idx = int(sel) - 1
                if 0 <= sel_idx < len(dir_list):
                    selected_dir, files = dir_list[sel_idx]
                    print(f"\nPending files in {selected_dir}:")
                    for i, f in enumerate(files, 1):
                        print(f"  {i}. {os.path.basename(f)}")
                    confirm = input("\nProcess all new files in this directory? (y/n): ").strip().lower()
                    if confirm == "y":
                        # Process as individual scan (reuse your scan logic)
                        processor = DirectoryProcessor(selected_dir)
                        result = processor._process_media_files()
                        if result is not None and result >= 0:
                            print(f"\nScan completed. Processed {result} items.")
                        else:
                            print("\nScan did not complete successfully.")
                        input("\nPress Enter to continue...")
                else:
                    print("\nInvalid selection.")
                    input("\nPress Enter to continue...")
            except ValueError:
                print("\nInvalid input.")
                input("\nPress Enter to continue...")
            
        elif choice == "0":
            return
            
        else:
            print("\nInvalid option.")
            input("\nPress Enter to continue...")
def process_pending_files_multiscan(monitor_manager, pending_files):
    """Process each pending file as an individual scan, showing progress and scan info."""
    if not pending_files:
        print("\nNo pending files to process.")
        input("\nPress Enter to continue...")
        return
    total = len(pending_files)
    for idx, file_info in enumerate(pending_files, 1):
        clear_screen()
        display_ascii_art()
        print("=" * 84)
        print(f"PROCESSING PENDING FILE {idx} OF {total}".center(84))
        print("=" * 84)
        # Extract file path and directory
        if isinstance(file_info, dict):
            file_path = file_info.get('path') or file_info.get('file_path')
        else:
            file_path = str(file_info)
        print(f"\nFile: {file_path}")
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
                os.environ['DISCORD_WEBHOOK_URL'] = url
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
            new_state = 'false' if notifications_enabled else 'true'
            _update_env_var('ENABLE_DISCORD_NOTIFICATIONS', new_state)
            print(f"\nDiscord notifications {'enabled' if new_state == 'true' else 'disabled'}.")
        elif choice == "7":
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
        if choice != "7":
            print("\nPress Enter to continue...")
            input()

def handle_settings():
    while True:
        clear_screen()
        display_ascii_art()
        print("=" * 84)
        print("SETTINGS".center(84))
        print("=" * 84)
        
        # Get current skip symlinked setting
        skip_symlinked = os.environ.get('SKIP_SYMLINKED', 'false').lower() == 'true'
        
        print("\nOptions:")
        print("  1. Configure File Paths")
        print("  2. Configure API Settings")
        print("  3. Configure Webhook Settings")
        print("  4. Test TMDB Integration")
        print(f"  5. Skip Symlinked Items: {'Enabled' if skip_symlinked else 'Disabled'}")
        print("  0. Return to Main Menu")
        choice = input("\nSelect option: ").strip()
        if choice == "1":
            print("\nFile path settings selected")
            print("\nPress Enter to continue...")
            input()
        elif choice == "2":
            print("\nAPI settings selected")
            print("\nPress Enter to continue...")
            input()
        elif choice == "3":
            handle_webhook_settings()
        elif choice == "4":
            handle_tmdb_test()
        elif choice == "5":
            # Toggle skip symlinked setting
            new_state = 'false' if skip_symlinked else 'true'
            _update_env_var('SKIP_SYMLINKED', new_state)
            print(f"\nSkip symlinked items {'enabled' if new_state == 'true' else 'disabled'}.")
            print("This setting will automatically skip items that already have symlinks")
            print("in the destination directory across all scan types.")
            input("\nPress Enter to continue...")
        elif choice == "0":
            return
        else:
            print(f"\nInvalid option: {choice}")

def handle_tmdb_test():
    clear_screen()
    display_ascii_art()
    print("=" * 84)

    print("TMDB INTEGRATION TEST".center(84))
    print("=" * 84)
    print("\nEnter a movie title to test TMDB integration:")
    query = input("Title: ").strip()
    if not query:
        print("\nNo title entered. Returning to settings.")
        input("\nPress Enter to continue...")
        return
    try:
        tmdb = TMDB()
        results = tmdb.search_movie(query)
        if not results:
            print("\nNo results found from TMDB.")
        else:
            print(f"\nResults for '{query}':")
            for movie in results[:5]:
                print(f"- {movie.get('title', 'Unknown')} ({movie.get('release_date', 'N/A')[:4]}) {{tmdb-{movie.get('id', 'N/A')}}}")
    except Exception as e:
        print(f"\nError testing TMDB: {e}")
    input("\nPress Enter to continue...")

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

def csv_import_menu():
    """Handle the CSV Import submenu."""
    perform_csv_import()

def perform_csv_import():
    """Perform CSV import operation."""
    import csv
    import shutil
    import unicodedata
    import datetime
    from src.utils.scan_logic import normalize_title, normalize_unicode
    global skipped_items_registry
    
    # Add logging for CSV import start
    logger.info("CSV Processing: Starting CSV import operation")
    
    clear_screen()
    display_ascii_art()
    print("=" * 84)
    print("CSV IMPORT".center(84))
    print("=" * 84)
    
    # Check if DESTINATION_DIRECTORY is configured
    if not DESTINATION_DIRECTORY:
        print("\n❌ Error: Destination directory not configured.")
        print("\nTo configure the destination directory:")
        print("1. Copy .env.template to .env")
        print("2. Set DESTINATION_DIRECTORY in the .env file")
        print("3. Restart Scanly")
        print("\nExample: DESTINATION_DIRECTORY=/mnt/Scanly")
        input("\nPress Enter to return to main menu...")
        return
    
    # Get CSV file path
    print("\nEnter the CSV file path:")
    csv_input = input().strip()
    
    # Check if user wants to return to main menu
    if csv_input.lower() in ('exit', 'quit', 'back', 'return'):
        return
    
    # Clean and validate CSV file path
    csv_path = _clean_directory_path(csv_input)
    if not os.path.isfile(csv_path) or not csv_path.lower().endswith('.csv'):
        logger.error(f"CSV Processing: Invalid CSV file path: {csv_path}")
        print(f"\nError: {csv_path} is not a valid CSV file.")
        input("\nPress Enter to continue...")
        return
    
    # Log CSV file being processed
    logger.info(f"CSV Processing: Processing CSV file: {csv_path}")
    
    # Load scan history to avoid re-processing
    scan_history = load_scan_history_set()
    
    try:
        # Read and count items in CSV
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            file_paths = [row[0].strip() for row in reader if row and row[0].strip()]
        
        logger.info(f"CSV Processing: Read {len(file_paths)} file paths from CSV")
        
        if not file_paths:
            logger.warning("CSV Processing: No file paths found in CSV")
            print("\nNo file paths found in CSV.")
            input("\nPress Enter to continue...")
            return
        
        print(f"\nDetected {len(file_paths)} items in CSV file")
        
        # Check for already processed items but let user decide
        already_processed = [path for path in file_paths if path not in scan_history]
        new_items = [path for path in file_paths if path not in scan_history]
        already_processed_items = [path for path in file_paths if path in scan_history]
        
        logger.info(f"CSV Processing: Found {len(already_processed_items)} already processed, {len(new_items)} new items")
        already_processed_items = [path for path in file_paths if path in scan_history]
        
        # Track whether user wants to ignore scan history
        ignore_scan_history = False
        
        if already_processed_items:
            print(f"\nFound {len(already_processed_items)} items that appear to be already processed (in scan history)")
            print(f"Found {len(new_items)} items that appear to be new")
            
            # Let user decide what to do with already processed items
            print("\nOptions for already processed items:")
            skip_symlinked = os.environ.get('SKIP_SYMLINKED', 'false').lower() == 'true'
            symlink_note = " - Also checks for existing symlinks" if skip_symlinked else ""
            print(f"1. Skip them (only process new items){symlink_note}")
            print("2. Process them anyway (ignore scan history)")
            print("3. Show me the items and let me decide")
            
            choice = input("\nSelect option [1-3]: ").strip()
            if choice == "":
                print("Please select an option.")
                # Don't auto-default, ask again
                while choice == "":
                    choice = input("Select option [1-3]: ").strip()
            
            if choice == "1":
                # Check SKIP_SYMLINKED setting to determine if we should check for symlinks
                skip_symlinked = os.environ.get('SKIP_SYMLINKED', 'false').lower() == 'true'
                
                if skip_symlinked:
                    # Check for existing symlinks in addition to scan history
                    print("\nChecking for existing symlinks...")
                    items_with_symlinks = []
                    items_to_process = []
                    
                    for file_path in new_items:
                        try:
                            # Extract metadata to check for existing symlinks
                            parent_dir = os.path.dirname(file_path)
                            filename = os.path.basename(file_path)
                            title_part = os.path.splitext(filename)[0]
                            
                            # Extract year
                            year_match = re.search(r'(19\d{2}|20\d{2})', title_part)
                            year = year_match.group(1) if year_match else None
                            
                            # Clean title
                            clean_title = title_part
                            if year:
                                clean_title = clean_title.replace(year, '').strip()
                            clean_title = clean_title_with_patterns(clean_title)
                            clean_title = normalize_unicode(clean_title)
                            
                            # Detect content type
                            default_flags = get_default_content_type_for_path(parent_dir)
                            if default_flags:
                                is_tv, is_anime, is_wrestling = default_flags
                            else:
                                is_tv = re.search(r'[sS]\d+[eE]\d+|Season|Episode', filename, re.IGNORECASE) is not None
                                is_anime = re.search(r'anime|subbed|dubbed|\[jp\]', filename, re.IGNORECASE) is not None
                                is_wrestling = re.search(r'wrestling|wwe|aew|njpw', filename, re.IGNORECASE) is not None
                            
                            # Check for existing symlinks using DirectoryProcessor method
                            temp_processor = DirectoryProcessor(parent_dir)
                            logger.info(f"CSV Processing: Checking symlinks for '{clean_title}' ({year}) - Type: {'TV' if is_tv else 'Movie'}, Anime: {is_anime}, Wrestling: {is_wrestling}")
                            has_symlink = temp_processor._has_existing_symlink(
                                parent_dir, clean_title, year, is_tv, is_anime, is_wrestling
                            )
                            
                            if has_symlink:
                                items_with_symlinks.append(file_path)
                                logger.info(f"CSV Processing: Skipping {file_path} - existing symlink found for '{clean_title}' ({year})")
                            else:
                                items_to_process.append(file_path)
                                
                        except Exception as e:
                            # If we can't check for symlinks, include the item to be safe
                            logger.warning(f"CSV Processing: Could not check symlinks for {file_path}: {e}")
                            items_to_process.append(file_path)
                    
                    logger.info(f"CSV Processing: User selected option 1 - Processing {len(items_to_process)} new items, skipping {len(already_processed_items)} in scan history and {len(items_with_symlinks)} with existing symlinks")
                    
                    print(f"Will process {len(items_to_process)} new items")
                    if len(items_with_symlinks) > 0:
                        print(f"Skipping {len(items_with_symlinks)} items with existing symlinks")
                else:
                    # Don't check for symlinks, just process new items
                    items_to_process = new_items
                    logger.info(f"CSV Processing: User selected option 1 - Processing {len(items_to_process)} new items, skipping {len(already_processed_items)} in scan history (symlink checking disabled)")
                    print(f"Will process {len(items_to_process)} new items")
                
                print(f"Skipping {len(already_processed_items)} items already in scan history")
                ignore_scan_history = False
            elif choice == "2":
                # Process all items
                items_to_process = file_paths
                ignore_scan_history = True
                logger.info(f"CSV Processing: User selected to process all {len(items_to_process)} items (including already processed)")
                print(f"Will process all {len(items_to_process)} items (including already processed)")
            elif choice == "3":
                # Show detailed list and let user choose each one
                print(f"\nAlready processed items ({len(already_processed_items)}):")
                for idx, item in enumerate(already_processed_items[:10], 1):  # Show first 10
                    print(f"  {idx}. {item}")
                if len(already_processed_items) > 10:
                    print(f"  ... and {len(already_processed_items) - 10} more")
                
                include_processed = input(f"\nInclude these {len(already_processed_items)} already processed items? (y/n): ").strip().lower()
                if include_processed == 'y':
                    items_to_process = file_paths
                    ignore_scan_history = True
                    print(f"Will process all {len(items_to_process)} items")
                else:
                    items_to_process = new_items
                    ignore_scan_history = False
                    print(f"Will process {len(items_to_process)} new items only")
            else:
                print("Invalid option, defaulting to processing new items only")
                items_to_process = new_items
                ignore_scan_history = False
        else:
            print(f"All {len(file_paths)} items appear to be new")
            # Check SKIP_SYMLINKED setting to determine if we should check for symlinks
            skip_symlinked = os.environ.get('SKIP_SYMLINKED', 'false').lower() == 'true'
            
            if skip_symlinked:
                # Check for existing symlinks even when all items are new
                print("Checking for existing symlinks...")
                items_with_symlinks = []
                items_to_process = []
                
                for file_path in file_paths:
                    try:
                        # Extract metadata to check for existing symlinks
                        parent_dir = os.path.dirname(file_path)
                        filename = os.path.basename(file_path)
                        title_part = os.path.splitext(filename)[0]
                        
                        # Extract year
                        year_match = re.search(r'(19\d{2}|20\d{2})', title_part)
                        year = year_match.group(1) if year_match else None
                        
                        # Clean title
                        clean_title = title_part
                        if year:
                            clean_title = clean_title.replace(year, '').strip()
                        clean_title = clean_title_with_patterns(clean_title)
                        clean_title = normalize_unicode(clean_title)
                        
                        # Detect content type
                        default_flags = get_default_content_type_for_path(parent_dir)
                        if default_flags:
                            is_tv, is_anime, is_wrestling = default_flags
                        else:
                            is_tv = re.search(r'[sS]\d+[eE]\d+|Season|Episode', filename, re.IGNORECASE) is not None
                            is_anime = re.search(r'anime|subbed|dubbed|\[jp\]', filename, re.IGNORECASE) is not None
                            is_wrestling = re.search(r'wrestling|wwe|aew|njpw', filename, re.IGNORECASE) is not None
                        
                        # Check for existing symlinks using DirectoryProcessor method
                        temp_processor = DirectoryProcessor(parent_dir)
                        logger.info(f"CSV Processing: Checking symlinks for '{clean_title}' ({year}) - Type: {'TV' if is_tv else 'Movie'}, Anime: {is_anime}, Wrestling: {is_wrestling}")
                        has_symlink = temp_processor._has_existing_symlink(
                            parent_dir, clean_title, year, is_tv, is_anime, is_wrestling
                        )
                        
                        if has_symlink:
                            items_with_symlinks.append(file_path)
                            logger.info(f"CSV Processing: Skipping {file_path} - existing symlink found for '{clean_title}' ({year})")
                        else:
                            items_to_process.append(file_path)
                            
                    except Exception as e:
                        # If we can't check for symlinks, include the item to be safe
                        logger.warning(f"CSV Processing: Could not check symlinks for {file_path}: {e}")
                        items_to_process.append(file_path)
                
                logger.info(f"CSV Processing: All items new - Processing {len(items_to_process)} items, skipping {len(items_with_symlinks)} with existing symlinks")
                
                print(f"Will process {len(items_to_process)} items")
                if len(items_with_symlinks) > 0:
                    print(f"Skipping {len(items_with_symlinks)} items with existing symlinks")
            else:
                # Don't check for symlinks, process all items
                items_to_process = file_paths
                logger.info(f"CSV Processing: All items new - Processing {len(items_to_process)} items (symlink checking disabled)")
                print(f"Will process {len(items_to_process)} items")
            
            ignore_scan_history = False
        
        if not items_to_process:
            print("\nNo items selected for processing.")
            input("\nPress Enter to continue...")
            return
        
        # Confirm processing
        confirm = input(f"\nProceed with processing {len(items_to_process)} items? (y/n): ").strip().lower()
        if confirm != 'y':
            print("\nCSV import cancelled.")
            input("\nPress Enter to continue...")
            return
        
        # Process each file
        processed_count = 0
        skipped_count = 0
        
        for i, file_path in enumerate(items_to_process, 1):
            clear_screen()
            display_ascii_art()
            print("=" * 84)
            print(f"PROCESSING CSV ITEM {i} OF {len(items_to_process)}".center(84))
            print("=" * 84)
            print(f"\nFile: {file_path}")
            
            # Add logging for CSV processing start
            logger.info(f"CSV Processing: Starting item {i}/{len(items_to_process)}: {file_path}")
            
            # Validate file exists
            if not os.path.exists(file_path):
                logger.warning(f"CSV Processing: File does not exist, skipping: {file_path}")
                print(f"Warning: File does not exist, skipping: {file_path}")
                skipped_count += 1
                continue
            
            # Skip sample files
            filename = os.path.basename(file_path)
            if "sample" in filename.lower():
                logger.info(f"CSV Processing: Skipping sample file: {file_path}")
                print(f"Skipping sample file: {filename}")
                skipped_count += 1
                continue
            
            # Extract directory and filename
            parent_dir = os.path.dirname(file_path)
            filename = os.path.basename(file_path)
            
            # Extract metadata from filename
            # Remove file extension for title extraction
            title_part = os.path.splitext(filename)[0]
            
            # Extract year
            year_match = re.search(r'(19\d{2}|20\d{2})', title_part)
            year = year_match.group(1) if year_match else None
            
            # Clean title
            clean_title = title_part
            if year:
                clean_title = clean_title.replace(year, '').strip()
            
            # Apply cleaning patterns
            clean_title = clean_title_with_patterns(clean_title)
            clean_title = normalize_unicode(clean_title)
            
            if not clean_title.strip():
                clean_title = filename
            
            # Detect content type based on parent directory
            default_flags = get_default_content_type_for_path(parent_dir)
            if default_flags:
                is_tv, is_anime, is_wrestling = default_flags
            else:
                # Default detection logic
                is_tv = False
                is_anime = False  
                is_wrestling = False
                
                # Simple detection based on filename patterns
                if re.search(r'[sS]\d+[eE]\d+|Season|Episode', filename, re.IGNORECASE):
                    is_tv = True
                
                if re.search(r'anime|subbed|dubbed|\[jp\]', filename, re.IGNORECASE):
                    is_anime = True
                
                if re.search(r'wrestling|wwe|aew|njpw', filename, re.IGNORECASE):
                    is_wrestling = True
            
            print(f"Title: {clean_title}")
            print(f"Year: {year or 'Unknown'}")
            
            content_type = "Wrestling" if is_wrestling else \
                          "Anime Series" if is_tv and is_anime else \
                          "Anime Movie" if is_anime else \
                          "TV Series" if is_tv else "Movie"
            print(f"Content Type: {content_type}")
            
            # Initialize variables for the interactive loop
            tmdb_id = None
            season_number = 1
            episode_number = 1
            episode_name = None
            
            # Auto-detect season and episode for TV content
            if is_tv:
                # Try to extract season from filename
                season_match = re.search(r'[sS](\d{1,2})', filename)
                if season_match:
                    season_number = int(season_match.group(1))
                
                # Try to extract episode from filename  
                episode_match = re.search(r'[eE](\d{1,2})', filename)
                if episode_match:
                    episode_number = int(episode_match.group(1))
                else:
                    # Check for special episode names
                    if re.search(r'(extra|special|behind|making|deleted|bonus)', filename, re.IGNORECASE):
                        episode_name = "Special"
                        episode_number = None
            
            # Check scanner lists for matches
            scanner_matches = []
            try:
                # Use DirectoryProcessor to check scanner lists
                temp_processor = DirectoryProcessor(parent_dir)
                scanner_matches = temp_processor._check_scanner_lists(clean_title, year, is_tv, is_anime, is_wrestling)
            except Exception as e:
                print(f"Warning: Could not check scanner lists: {e}")
            
            if scanner_matches:
                print(f"\n📋 Found {len(scanner_matches)} scanner list matches:")
                for i, match in enumerate(scanner_matches[:5], 1):
                    # Handle both dictionary and string formats
                    if isinstance(match, dict):
                        match_title = match.get('title', 'Unknown')
                        match_year = match.get('year', '')
                        match_tmdb = match.get('tmdb_id', '')
                    else:
                        # If match is a string, use it as the title
                        match_title = str(match)
                        match_year = ''
                        match_tmdb = ''
                    print(f"  {i}. {match_title} ({match_year}) {{tmdb-{match_tmdb}}}")
                
                print("💡 Scanner matches available - use option 8 or 9 to select")
            
            # Interactive processing loop like individual scan
            while True:
                print("\nOptions:")
                print("1. Accept as is")
                print("2. Change search term")
                print("3. Change content type")
                print("4. Change year")
                print("5. Manual TMDB ID")
                print("6. Skip (save for later review)")
                print("7. Flag this item")
                if is_tv:
                    print("8. Set season/episode info")
                    if scanner_matches:
                        print("9. Show scanner matches")
                        print("0. Skip to next CSV item")
                    else:
                        print("0. Skip to next CSV item")
                elif scanner_matches:
                    print("8. Show scanner matches")
                    print("0. Skip to next CSV item")
                else:
                    print("0. Skip to next CSV item")
                
                # Show current item info
                print(f"\nCurrent: {clean_title}")
                if year:
                    print(f"Year: {year}")
                if tmdb_id:
                    print(f"TMDB ID: {tmdb_id}")
                print(f"Content Type: {content_type}")
                
                # Show current season/episode info for TV content
                if is_tv:
                    if episode_name:
                        print(f"Season {season_number}, Episode '{episode_name}'")
                    else:
                        print(f"Season {season_number}, Episode {episode_number}")

                choice = input("\nSelect option: ").strip()
                # DON'T auto-default to choice 1 - require explicit user input
                if choice == "":
                    print("Please select an option.")
                    continue

                if choice == "1":
                    # Process with current settings
                    print(f"\n🔄 Processing: {clean_title}")
                    if year:
                        print(f"   Year: {year}")
                    if tmdb_id:
                        print(f"   TMDB ID: {tmdb_id}")
                    print(f"   Content Type: {content_type}")
                    if is_tv:
                        if episode_name:
                            print(f"   Season {season_number}, Episode '{episode_name}'")
                        else:
                            print(f"   Season {season_number}, Episode {episode_number}")
                    
                    try:
                        processor = DirectoryProcessor(parent_dir)
                        
                        # Add logging before processing
                        logger.info(f"CSV Processing: Attempting to process {file_path} as '{clean_title}' ({content_type})")
                        
                        # For CSV import, use the single-file processing method
                        if is_tv:
                            # For TV content, pass season and episode info
                            symlink_result = processor._create_symlink_for_single_file(
                                file_path, clean_title, year, is_tv, is_anime, is_wrestling, tmdb_id,
                                season_number, episode_number, episode_name, ignore_scan_history
                            )
                        else:
                            # For movies
                            symlink_result = processor._create_symlink_for_single_file(
                                file_path, clean_title, year, is_tv, is_anime, is_wrestling, tmdb_id,
                                None, None, None, ignore_scan_history
                            )
                        
                        if symlink_result:
                            processed_count += 1
                            logger.info(f"CSV Processing: Successfully processed {file_path}")
                            print(f"✅ Successfully processed: {clean_title}")
                            if is_tv:
                                if episode_name:
                                    print(f"   Season {season_number}, Episode '{episode_name}'")
                                else:
                                    print(f"   Season {season_number}, Episode {episode_number}")
                        else:
                            logger.warning(f"CSV Processing: Failed to process {file_path} - symlink creation returned False")
                            print(f"⚠️  Failed to process: {clean_title}")
                            print("   Check logs for more details.")
                    except Exception as e:
                        logger.error(f"CSV Processing: Exception processing {file_path}: {e}")
                        print(f"❌ Error processing {file_path}: {e}")
                        import traceback
                        traceback.print_exc()
                    break
                    
                elif choice == "2":
                    # Change search term with full TMDB search like individual scan
                    while True:
                        new_search = input(f"Enter new search term [{clean_title}]: ").strip()
                        if new_search:
                            clean_title = new_search  # Do NOT clean user-entered search term
                            
                        # Immediately run TMDB search and present results
                        try:
                            tmdb = TMDB()
                            if is_tv:  # TV Series or Anime Series
                                tmdb_results = tmdb.search_tv(clean_title)
                            else:  # Movies, Anime Movies, Wrestling
                                tmdb_results = tmdb.search_movie(clean_title)
                        except Exception:
                            tmdb_results = []

                        if tmdb_results:
                            print(f"\nTMDB Search Results for '{clean_title}':")
                            tmdb_choices = []
                            for idx, result in enumerate(tmdb_results[:5], 1):
                                if is_tv:  # TV Series or Anime Series
                                    t_title = result.get('name')
                                    t_date = result.get('first_air_date', '')
                                else:  # Movies, Anime Movies, Wrestling
                                    t_title = result.get('title')
                                    t_date = result.get('release_date', '')
                                
                                # Safely extract year
                                if t_date and isinstance(t_date, str) and len(t_date) >= 4:
                                    t_year = t_date[:4]
                                else:
                                    t_year = 'N/A'
                                t_id = result.get('id')
                                print(f"{idx}. {t_title} ({t_year}) {{tmdb-{t_id}}}")
                                tmdb_choices.append({
                                    'title': t_title,
                                    'year': t_year if t_year != 'N/A' else '',
                                    'tmdb_id': str(t_id)
                                })
                            print("0. Enter a new search term")
                            print("8. Enter TMDB ID manually")
                            print("9. Skip and return to previous menu")
                            
                            while True:
                                tmdb_pick = input("\nSelect TMDB result [1-5], 0 for new search, 8 for manual ID, 9 to skip: ").strip()
                                if tmdb_pick == "":
                                    tmdb_pick = "1"  # Default to first result
                                if tmdb_pick == "0":
                                    # Prompt for new search term and re-run TMDB search
                                    break  # Break inner loop to get new search term
                                elif tmdb_pick == "8":
                                    # Manual TMDB ID entry
                                    manual_id = input("Enter TMDB ID: ").strip()
                                    if manual_id and manual_id.isdigit():
                                        tmdb_id = manual_id
                                        print(f"\n✅ Manual TMDB ID set: {tmdb_id}")
                                        # Exit both loops to return to main menu
                                        tmdb_pick = "manual_id_set"
                                        break
                                    else:
                                        print("Invalid TMDB ID. Please enter a numeric ID.")
                                        continue
                                elif tmdb_pick == "9":
                                    # Skip and return to main menu
                                    break
                                elif tmdb_pick.isdigit() and 1 <= int(tmdb_pick) <= len(tmdb_choices):
                                    pick = tmdb_choices[int(tmdb_pick)-1]
                                    clean_title = pick['title']
                                    # Only update year if TMDB has a valid year, otherwise keep original
                                    if pick['year']:
                                        year = pick['year']
                                    # Always update TMDB ID from the selection
                                    tmdb_id = pick['tmdb_id']
                                    
                                    # Log the updated values
                                    logger.info(f"CSV Processing: TMDB selection updated values - Title: '{clean_title}', Year: '{year}', TMDB ID: '{tmdb_id}'")
                                    print(f"\n✅ TMDB result selected: {clean_title} ({year}) {{tmdb-{tmdb_id}}}")
                                    
                                    # Process the item immediately after selection
                                    print(f"\n🔄 Processing: {clean_title}")
                                    if year:
                                        print(f"   Year: {year}")
                                    if tmdb_id:
                                        print(f"   TMDB ID: {tmdb_id}")
                                    print(f"   Content Type: {content_type}")
                                    if is_tv:
                                        if episode_name:
                                            print(f"   Season {season_number}, Episode '{episode_name}'")
                                        else:
                                            print(f"   Season {season_number}, Episode {episode_number}")
                                    
                                    try:
                                        processor = DirectoryProcessor(parent_dir)
                                        
                                        # Add logging with the updated values
                                        logger.info(f"CSV Processing: Processing with TMDB selection - {file_path} as '{clean_title}' (Year: {year}, TMDB: {tmdb_id}, Type: {content_type})")
                                        
                                        # For CSV import, use the single-file processing method
                                        if is_tv:
                                            # For TV content, pass season and episode info
                                            symlink_result = processor._create_symlink_for_single_file(
                                                file_path, clean_title, year, is_tv, is_anime, is_wrestling, tmdb_id,
                                                season_number, episode_number, episode_name, ignore_scan_history
                                            )
                                        else:
                                            # For movies
                                            symlink_result = processor._create_symlink_for_single_file(
                                                file_path, clean_title, year, is_tv, is_anime, is_wrestling, tmdb_id,
                                                None, None, None, ignore_scan_history
                                            )
                                        
                                        if symlink_result:
                                            processed_count += 1
                                            logger.info(f"CSV Processing: Successfully processed {file_path} with TMDB selection")
                                            print(f"✅ Successfully processed: {clean_title}")
                                            if is_tv:
                                                if episode_name:
                                                    print(f"   Season {season_number}, Episode '{episode_name}'")
                                                else:
                                                    print(f"   Season {season_number}, Episode {episode_number}")
                                        else:
                                            logger.warning(f"CSV Processing: Failed to process {file_path} with TMDB selection - symlink creation returned False")
                                            print(f"⚠️  Failed to process: {clean_title}")
                                            print("   Check logs for more details.")
                                    except Exception as e:
                                        logger.error(f"CSV Processing: Exception processing {file_path} with TMDB selection: {e}")
                                        print(f"❌ Error processing {file_path}: {e}")
                                        import traceback
                                        traceback.print_exc()
                                    
                                    # Set flags to exit all loops and move to next item
                                    tmdb_pick = "processed_and_break"
                                    break  # Break inner loop
                                else:
                                    print("Invalid selection. Please try again.")
                            
                            # If user entered manual ID, selected option 9 (skip), processed an item, or made a selection, exit outer loop
                            if tmdb_pick == "manual_id_set" or tmdb_pick == "9" or tmdb_pick == "processed_and_break" or (tmdb_pick.isdigit() and 1 <= int(tmdb_pick) <= len(tmdb_choices)):
                                break
                            # If user selected option 0, continue outer loop for new search term
                        else:
                            print(f"\nNo TMDB results found for '{clean_title}'. Try another search term or skip.")
                            print("0. Enter a new search term")
                            print("8. Enter TMDB ID manually")
                            print("9. Skip and return to previous menu")
                            tmdb_pick = input("\nSelect option: ").strip()
                            if tmdb_pick == "":
                                tmdb_pick = "0"  # Default to new search term when no results
                            if tmdb_pick == "0":
                                continue  # Continue outer loop for new search term
                            elif tmdb_pick == "8":
                                # Manual TMDB ID entry
                                manual_id = input("Enter TMDB ID: ").strip()
                                if manual_id and manual_id.isdigit():
                                    tmdb_id = manual_id
                                    print(f"\n✅ Manual TMDB ID set: {tmdb_id}")
                                    break  # Exit outer loop and return to main menu
                                else:
                                    print("Invalid TMDB ID. Please enter a numeric ID.")
                                    continue
                            elif tmdb_pick == "9":
                                break  # Exit outer loop and return to main menu
                            else:
                                print("Invalid selection. Please try again.")
                                continue
                    
                    # Check if we processed an item and should move to next CSV item
                    if tmdb_pick == "processed_and_break":
                        break  # Break out of main choice loop to move to next CSV item
                    
                    continue
                    
                elif choice == "3":
                    # Change content type
                    print("\nSelect new content type:")
                    print("1. Movie")
                    print("2. TV Series")
                    print("3. Anime Movie")
                    print("4. Anime Series")
                    print("5. Wrestling")
                    print("0. Cancel")
                    type_choice = input("Select type: ").strip()
                    if type_choice == "1":
                        is_tv = False
                        is_anime = False
                        is_wrestling = False
                        content_type = "Movie"
                    elif type_choice == "2":
                        is_tv = True
                        is_anime = False
                        is_wrestling = False
                        content_type = "TV Series"
                    elif type_choice == "3":
                        is_tv = False
                        is_anime = True
                        is_wrestling = False
                        content_type = "Anime Movie"
                    elif type_choice == "4":
                        is_tv = True
                        is_anime = True
                        is_wrestling = False
                        content_type = "Anime Series"
                    elif type_choice == "5":
                        is_tv = False
                        is_anime = False
                        is_wrestling = True
                        content_type = "Wrestling"
                    elif type_choice == "0":
                        continue
                    
                    # If TV Series or Anime Series, prompt for season and episode
                    if is_tv:
                        # Prompt for season number
                        try:
                            # Try to extract season from filename first
                            season_match = re.search(r'[sS](\d{1,2})', filename)
                            detected_season = season_match.group(1) if season_match else "1"
                            
                            season_input = input(f"Enter season number [{detected_season}]: ").strip()
                            if not season_input:
                                season_input = detected_season
                            season_number = int(season_input) if season_input.isdigit() else 1
                        except ValueError:
                            season_number = 1
                        
                        # Prompt for episode number or name
                        try:
                            # Try to extract episode from filename first
                            episode_match = re.search(r'[eE](\d{1,2})', filename)
                            detected_episode = episode_match.group(1) if episode_match else "1"
                            
                            print(f"\nEnter episode number or name (for Extras/Specials):")
                            print(f"Examples: '1', '01', 'Extra', 'Special', 'Behind the Scenes'")
                            episode_input = input(f"Episode [{detected_episode}]: ").strip()
                            if not episode_input:
                                episode_input = detected_episode
                            
                            # Check if it's a number or a name
                            if episode_input.isdigit():
                                episode_number = int(episode_input)
                                episode_name = None
                            else:
                                episode_number = None
                                episode_name = episode_input
                                
                        except Exception:
                            episode_number = 1
                            episode_name = None
                        
                        print(f"Season: {season_number}")
                        if episode_name:
                            print(f"Episode: {episode_name}")
                        else:
                            print(f"Episode: {episode_number}")
                    
                    print(f"Content type changed to: {content_type}")
                    continue
                    
                elif choice == "4":
                    # Change year
                    current_year_display = year or "None"
                    new_year = input(f"Enter new year [{current_year_display}]: ").strip()
                    if new_year:
                        if new_year.isdigit() and len(new_year) == 4:
                            year = new_year
                            print(f"Year set to: {year}")
                        else:
                            print("Invalid year format. Please enter a 4-digit year.")
                    elif new_year == "":
                        # If user just pressed Enter, keep current year
                        pass
                    else:
                        year = None
                        print("Year cleared.")
                    continue
                    
                elif choice == "5":
                    # Manual TMDB ID
                    tmdb_id = input("Enter TMDB ID: ").strip()
                    if tmdb_id:
                        print(f"TMDB ID set to: {tmdb_id}")
                        # DON'T auto-process, just set the ID and continue to menu
                        continue
                    else:
                        print("No TMDB ID entered.")
                        continue
                    
                elif choice == "6":
                    # Skip and save for later review
                    logger.info(f"CSV Processing: User skipped file for later review: {file_path}")
                    print(f"Skipping: {clean_title}")
                    skipped_items_registry.append({
                        'file_path': file_path,
                        'title': clean_title,
                        'year': year,
                        'content_type': content_type,
                        'skipped_date': datetime.datetime.now().isoformat()
                    })
                    save_skipped_items(skipped_items_registry)
                    skipped_count += 1
                    break
                    
                elif choice == "7":
                    # Flag this item
                    logger.info(f"CSV Processing: User flagged file: {file_path}")
                    write_flag_to_csv({
                        "File Path": file_path,
                        "Cleaned Title": clean_title,
                        "Year": year if year else "",
                        "Content Type": content_type
                    })
                    append_to_scan_history(file_path)
                    print(f"Item flagged and saved to {FLAGGED_CSV}.")
                    skipped_count += 1
                    break
                
                elif choice == "8":
                    if is_tv:
                        # Set season/episode info for TV content
                        print(f"\nCurrent season: {season_number}")
                        season_input = input(f"Enter new season number [{season_number}]: ").strip()
                        if season_input and season_input.isdigit():
                            season_number = int(season_input)
                        
                        if episode_name:
                            current_ep = f"'{episode_name}'"
                        else:
                            current_ep = str(episode_number)
                        
                        print(f"Current episode: {current_ep}")
                        print("Enter episode number or name (for Extras/Specials):")
                        print("Examples: '1', '01', 'Extra', 'Special', 'Behind the Scenes'")
                        episode_input = input(f"Episode [{current_ep}]: ").strip()
                        
                        if episode_input:
                            if episode_input.isdigit():
                                episode_number = int(episode_input)
                                episode_name = None
                            else:
                                episode_name = episode_input
                                episode_number = None
                        
                        if episode_name:
                            print(f"\n✅ Updated: Season {season_number}, Episode '{episode_name}'")
                        else:
                            print(f"\n✅ Updated: Season {season_number}, Episode {episode_number}")
                        continue
                    elif scanner_matches:
                        # Show and select scanner matches (original option 7)
                        print(f"\nScanner List Matches ({len(scanner_matches)}):")
                        for i, match in enumerate(scanner_matches, 1):
                            match_title = match.get('title', 'Unknown')
                            match_year = match.get('year', '')
                            match_tmdb = match.get('tmdb_id', '')
                            print(f"{i}. {match_title} ({match_year}) {{tmdb-{match_tmdb}}}")
                        
                        print("0. Use current settings")
                        
                        try:
                            scanner_choice = input("\nSelect scanner match: ").strip()
                            if scanner_choice == "0":
                                continue
                            
                            scanner_idx = int(scanner_choice) - 1
                            if 0 <= scanner_idx < len(scanner_matches):
                                selected_match = scanner_matches[scanner_idx]
                                # Handle both dictionary and string formats
                                if isinstance(selected_match, dict):
                                    clean_title = selected_match.get('title', clean_title)
                                    year = selected_match.get('year', year)
                                    tmdb_id = selected_match.get('tmdb_id', tmdb_id)
                                else:
                                    # If match is a string, use it as the title
                                    clean_title = str(selected_match)
                                    # Keep existing year and tmdb_id
                                print(f"\n✅ Selected: {clean_title} ({year}) {{tmdb-{tmdb_id}}}")
                            else:
                                print("Invalid selection.")
                        except ValueError:
                            print("Invalid selection.")
                        continue
                
                elif choice == "9" and is_tv and scanner_matches:
                    # Show scanner matches when TV content has both season/episode and scanner options
                    print(f"\nScanner List Matches ({len(scanner_matches)}):")
                    for i, match in enumerate(scanner_matches, 1):
                        match_title = match.get('title', 'Unknown')
                        match_year = match.get('year', '')
                        match_tmdb = match.get('tmdb_id', '')
                        print(f"{i}. {match_title} ({match_year}) {{tmdb-{match_tmdb}}}")
                    
                    print("0. Use current settings")
                    
                    try:
                        scanner_choice = input("\nSelect scanner match: ").strip()
                        if scanner_choice == "0":
                            continue
                        
                        scanner_idx = int(scanner_choice) - 1
                        if 0 <= scanner_idx < len(scanner_matches):
                            selected_match = scanner_matches[scanner_idx]
                            # Handle both dictionary and string formats
                            if isinstance(selected_match, dict):
                                clean_title = selected_match.get('title', clean_title)
                                year = selected_match.get('year', year)
                                tmdb_id = selected_match.get('tmdb_id', tmdb_id)
                            else:
                                # If match is a string, use it as the title
                                clean_title = str(selected_match)
                                # Keep existing year and tmdb_id
                            print(f"\n✅ Selected: {clean_title} ({year}) {{tmdb-{tmdb_id}}}")
                        else:
                            print("Invalid selection.")
                    except ValueError:
                        print("Invalid selection.")
                    continue
                    
                elif choice == "0":
                    # Skip to next CSV item
                    logger.info(f"CSV Processing: User skipped to next item: {file_path}")
                    print("Skipping to next item...")
                    skipped_count += 1
                    break
                    
                else:
                    print("Invalid option. Please try again.")
                    continue
            
            # Brief pause before next item
            input("\nPress Enter to continue to next item...")
        
        # Show final summary
        clear_screen()
        display_ascii_art()
        print("=" * 84)
        print("CSV IMPORT COMPLETE".center(84))
        print("=" * 84)
        print(f"\nProcessed: {processed_count} / {len(items_to_process)} items")
        print(f"Skipped: {skipped_count} items")
        
        # Add comprehensive logging for CSV completion
        logger.info(f"CSV Processing: Complete - Processed: {processed_count}, Skipped: {skipped_count}, Total: {len(items_to_process)}")
        
        # Trigger Plex refresh if any items were processed
        if processed_count > 0:
            trigger_plex_refresh()
        
        input("\nPress Enter to continue...")
        
    except Exception as e:
        print(f"\nError reading CSV file: {e}")
        input("\nPress Enter to continue...")
    
    clear_screen()
    display_ascii_art()

def monitor_management_menu(monitor_manager):
    """Handle the Monitor Management submenu."""
    handle_monitor_management(monitor_manager)

def settings_menu():
    handle_settings()

def trigger_plex_refresh():
    """Refresh only the applicable Plex libraries after a scan."""
    PLEX_URL = os.getenv("PLEX_URL")
    PLEX_TOKEN = os.getenv("PLEX_TOKEN")
    LIBRARIES = [
        os.getenv("PLEX_MOVIES_LIBRARY"),
        os.getenv("PLEX_TV_LIBRARY"),
        os.getenv("PLEX_ANIME_TV_LIBRARY"),
        os.getenv("PLEX_ANIME_MOVIES_LIBRARY"),
    ]
    LIBRARIES = [lib for lib in LIBRARIES if lib]
    if PLEX_URL and PLEX_TOKEN and LIBRARIES:
        result = refresh_selected_plex_libraries(PLEX_URL, PLEX_TOKEN, LIBRARIES)
        print("Plex refresh results:", result)
    else:
        print("Plex refresh skipped: missing configuration.")

# Ensure main function also properly clears screen between menus
def main():
    parser = argparse.ArgumentParser(description="Scanly Media Scanner")
    parser.add_argument('--monitor', action='store_true', help='Run monitor scan only (no menu)')
    args = parser.parse_args()

    # --- ADD THIS BLOCK: Resume scan if temp file exists ---
    resume_path = load_resume_path()
    if resume_path and os.path.isdir(resume_path):
        clear_screen()
        display_ascii_art()
        print("=" * 84)
        print("RESUMING INDIVIDUAL SCAN".center(84))
        print("=" * 84)
        print(f"\nResuming scan at: {resume_path}\n")
        processor = DirectoryProcessor(resume_path)
        result = processor._process_media_files()
        if result is not None and result >= 0:
            print(f"\nScan completed. Processed {result} items.")
            trigger_plex_refresh()
        else:
            print("\nScan did not complete successfully.")
        input("\nPress Enter to continue...")
        clear_screen()

    if args.monitor:
        # Start monitor manager directly, no menu or input
        monitor_manager = get_monitor_manager()
        monitor_manager.start_monitoring()  # <-- Use the correct method
        # Optionally, keep the process alive if needed:
        try:
            while True:
                time.sleep(60)
        except KeyboardInterrupt:
            pass
        return

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
    
    # Start the initial scan in the background
    monitor_manager.start_initial_scan_in_background()

    while True:
        display_ascii_art()
        print("=" * 84)
        print("MAIN MENU".center(84))
        print("=" * 84)
        
        print("  1. Individual Scan")
        print("  2. Multi Scan")
        print("  3. CSV Import")
        print("  4. Monitor Management")
        print("  5. Settings")
        print("  0. Quit")
        choice = input("Select option: ").strip()
            
        if choice == "1":
            individual_scan_menu()
            clear_screen()  # Explicitly clear screen when returning to main menu
        
        elif choice == "2":
            multi_scan_menu()
            clear_screen()  # Explicitly clear screen when returning to main menu
        
        elif choice == "3":
            csv_import_menu()
            clear_screen()  # Explicitly clear screen when returning to main menu
        
        elif choice == "4":
            monitor_management_menu(monitor_manager)
            clear_screen()  # Explicitly clear screen when returning to main menu
        
        elif choice == "5":
            settings_menu()
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
