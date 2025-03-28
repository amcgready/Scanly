#!/usr/bin/env python3
"""
Main entry point for Scanly.

This module contains the main functionality for running Scanly,
including the application initialization and entry point.
"""

# Must be at the top - redirect stdout/stderr before any imports
if __name__ == "__main__":
    import sys
    import io
    
    # Create a filter for stdout to capture and filter the output
    class OutputFilter(io.TextIOBase):
        def __init__(self, original):
            self.original = original
            self.suppress_next = False
            self.suppress_patterns = [
                # Python interpreter path
                "/home/adam/.pyenv/versions/",
                # Logger initialization message
                "- root - INFO - Logging initialized"
            ]
    
        def write(self, s):
            # Skip lines matching our patterns
            if any(pattern in s for pattern in self.suppress_patterns):
                return 0
            return self.original.write(s)
            
        def flush(self):
            self.original.flush()
    
    # Apply the filter
    sys.stdout = OutputFilter(sys.stdout)
    sys.stderr = OutputFilter(sys.stderr)

import os
import sys
import logging
import json
import subprocess
import time
import re
from pathlib import Path

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

def display_ascii_art():
    """Display ASCII art from file."""
    try:
        # Clear any existing output first
        print("\033[H\033[J", end="")  # ANSI escape sequence to clear screen
        
        # Add exactly one line of space above everything
        print()
        
        # Open and display the ASCII art
        with open(ART_FILE, 'r') as file:
            art = file.read()
            print(art, end="")  # No newline after art
            
    except Exception as e:
        # Just add a blank line if art can't be displayed
        print("\n")

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
    """Display help information about menu options."""
    clear_screen()
    print("   Used to scan larger directories that contain multiple sub-folders and files")
    print("   Best for processing entire media libraries or disk drives")
    print("\n2. Individual Scan")
    print("   Used to scan either a single folder or file that does not have")
    print("   additional nested sub-folders")
    print("   Best for processing a single TV episode or movie file")
    
    if history_exists():
        print("\n3. Resume Scan")
        print("   Continues processing from where a previous scan was interrupted")
        print("\n4. Clear History")
        print("   Removes the saved progress from an interrupted scan")
    
    print("\n0. Quit")
    print("   Exit the application")
    
    print("\nh. Help")
    print("   Display this help information")
    print("=" * 60)
    
    input("\nPress Enter to return to the main menu...")
    clear_screen()

# Now, import modules from the current project
from src.utils.logger import setup_logging, get_logger
from src.config import DESTINATION_DIRECTORY
from src.ui.menu import MainMenu
from src.api.tmdb import TMDB, format_tv_result, format_movie_result
import os
import json

# Define path for skipped items registry file
SKIPPED_ITEMS_FILE = os.path.join(os.path.dirname(__file__), 'skipped_items.json')

# Initialize skipped_items_registry from file or as empty list
def load_skipped_items():
    """Load skipped items from file if it exists, otherwise return empty list."""
    if os.path.exists(SKIPPED_ITEMS_FILE) and os.path.getsize(SKIPPED_ITEMS_FILE) > 0:
        try:
            with open(SKIPPED_ITEMS_FILE, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            logger = get_logger(__name__)
            logger.error(f"Error loading skipped items: {e}")
            return []
    return []

def save_skipped_items(skipped_items):
    """Save skipped items to file."""
    try:
        with open(SKIPPED_ITEMS_FILE, 'w') as f:
            json.dump(skipped_items, f)
        return True
    except (IOError, TypeError) as e:
        logger = get_logger(__name__)
        logger.error(f"Error saving skipped items: {e}")
        return False

# Initialize registry from file
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
        print(f"\nProcessing directory: {self.directory_path}")
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
            
            # Group files by subfolder for interactive processing
            self._process_by_subfolder(video_files)
            
            # Clear history since we're done
            global skipped_items_registry
            if self.skipped_subfolders:
                skipped_items_registry.extend(self.skipped_subfolders)
                print(f"\nNote: {len(self.skipped_subfolders)} subfolders were skipped.")
                print("You can review them later using the 'Review Skipped' option from the main menu.")
            
            clear_scan_history()
            
        except Exception as e:
            self.logger.error(f"Error processing directory {self.directory_path}: {e}", exc_info=True)
            print(f"\nError processing directory: {e}")
            
        input("\nPress Enter to continue...")
    
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
    
    def _extract_episode_info(self, file_path, filename):
        """Extract episode information from a filename."""
        # Try common patterns for episode extraction
        patterns = [
            # S01E01 pattern
            r'[Ss](\d{1,2})[Ee](\d{1,3})',
            # 1x01 pattern
            r'(\d{1,2})x(\d{1,3})',
            # Season 1 Episode 1 pattern
            r'[Ss]eason\s*(\d{1,2})\s*[Ee]pisode\s*(\d{1,3})',
            # Episode 1 (assuming season 1)
            r'[Ee]pisode\s*(\d{1,3})',
            # Just numbers (like 101 for S01E01)
            r'(\d)(\d{2})(?:\D|$)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, filename)
            if match:
                if len(match.groups()) == 2:
                    season = int(match.group(1))
                    episode = int(match.group(2))
                    return season, episode
                elif len(match.groups()) == 1:
                    # For patterns that only capture episode number
                    return 1, int(match.group(1))
        
        # Try to extract from path if not found in filename
        if file_path:
            path_parts = file_path.split(os.sep)
            for part in path_parts:
                for pattern in patterns:
                    match = re.search(pattern, part)
                    if match:
                        if len(match.groups()) == 2:
                            season = int(match.group(1))
                            episode = int(match.group(2))
                            return season, episode
                        elif len(match.groups()) == 1:
                            # For patterns that only capture episode number
                            return 1, int(match.group(1))
        
        # Try to extract just the season from the filename or path
        season_patterns = [
            r'[Ss]eason\s*(\d{1,2})',
            r'[Ss](\d{1,2})',
        ]
        
        for pattern in season_patterns:
            match = re.search(pattern, filename)
            if match:
                return int(match.group(1)), None
        
        # If all else fails
        return None, None

    def _get_episode_title_from_tmdb(self, show_id, season, episode):
        """Try to get the episode title from TMDB."""
        try:
            # If TMDB API supports this
            episode_details = self.tmdb.get_episode_details(show_id, season, episode)
            if episode_details and 'name' in episode_details:
                return episode_details['name']
        except:
            # Silently fail if API doesn't support this or other errors
            pass
        return None

    def _sanitize_filename_part(self, text):
        """Sanitize a portion of a filename."""
        if not text:
            return ""
        
        # Replace problematic characters
        replacements = {
            '/': '-', '\\': '-', ':': '-', '*': '', '?': '', '"': "'",
            '<': '[', '>': ']', '|': '-', '\t': ' ', '\n': ' ', '\r': ' '
        }
        
        result = text
        for char, replacement in replacements.items():
            result = result.replace(char, replacement)
        
        # Remove consecutive spaces
        result = re.sub(r'\s+', ' ', result).strip()
        
        return result

    # The rest of the class methods remain the same...
    def _process_by_subfolder(self, video_files):
        """Process files by subfolder with improved TMDB matching."""
        # Group files by subfolder
        subfolders = {}
        for file in video_files:
            # Get the subfolder path relative to the main directory
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
        
        # Process each subfolder interactively
        for subfolder in sorted_subfolders:
            files = subfolders[subfolder]
            
            # Skip empty subfolders
            if not files:
                continue
            
            processed_count += 1
            
            # Clear screen for new subfolder
            clear_screen()
            display_ascii_art()
            print("=" * 60)
                
            # Display subfolder info
            print(f"Processing subfolder {processed_count}/{total_subfolders}: {subfolder}")
            print(f"Contains {len(files)} media files")
            
            # Try to extract a name from the subfolder
            if subfolder == '.':
                subfolder_name = os.path.basename(self.directory_path)
            else:
                subfolder_name = os.path.basename(subfolder)
                
            # Clean the name for searching - our improved version will do a better job
            clean_name = self._clean_name_for_search(subfolder_name)
            
            # Detect if it's likely a TV show or movie based on the files
            tv_count = sum(1 for f in files if f.get('media_type') == 'tv')
            movie_count = sum(1 for f in files if f.get('media_type') == 'movie')
            
            is_tv = tv_count > movie_count
            media_type = "TV show" if is_tv else "movie"
            
            print(f"\nBased on file analysis, this appears to be a {media_type}.")
            print(f"Suggested title: {clean_name}")
            
            # Process TMDB search and present options
            tmdb_item = self._match_title_to_tmdb(clean_name, is_tv)
            
            # Check if user wants to exit to main menu
            if tmdb_item == "EXIT":
                print("Exiting to main menu...")
                return
            
            # Set skip_this_folder based on the return value from _match_title_to_tmdb
            # If tmdb_item is None, the user chose to skip
            skip_this_folder = (tmdb_item is None)
            
            if skip_this_folder:
                # Add to skipped items registry
                skipped_item = {
                    'subfolder': subfolder,
                    'path': os.path.join(self.directory_path, subfolder) if subfolder != '.' else self.directory_path,
                    'files': [{'filename': f['filename'], 'path': f['path']} for f in files],
                    'is_tv': is_tv,
                    'suggested_name': clean_name,
                    'timestamp': time.time()
                }
                
                self.skipped_subfolders.append(skipped_item)
                self.skipped_items_registry.append(skipped_item)
                
                # Save updated registry to file
                save_skipped_items(self.skipped_items_registry)
                
                print(f"\nFolder has been skipped and added to review list.")
                print(f"Skipped items count: {len(self.skipped_items_registry)}")
                time.sleep(1)
                continue
            
            # If not skipped and we have a valid match, process the folder
            if tmdb_item:
                try:
                    if is_tv:
                        self._process_tv_show_folder(subfolder, files, tmdb_item)
                    else:
                        self._process_movie_folder(subfolder, files, tmdb_item)
                except Exception as e:
                    self.logger.error(f"Error processing {subfolder}: {e}")
                    print(f"Error processing folder: {e}")
                    input("\nPress Enter to continue...")
            
            # Show confirmation after processing
            print("\n" + "=" * 60)
            print(f"✓ Completed processing: {subfolder}")
            print(f"  Processed {len(files)} files")
            time.sleep(1.5)

        # After processing all subfolders, update the global registry
        if self.skipped_subfolders:
            print(f"\nNote: {len(self.skipped_subfolders)} subfolders were skipped.")
            print("You can review them later using the 'Review Skipped' option from the main menu.")
            
            # Save updated registry to file
            save_skipped_items(self.skipped_items_registry)

    def _clean_name_for_search(self, name):
        """Clean a folder name for TMDB search with improved title extraction."""
        # Check for empty name
        if not name:
            return ""
        
        # Special handling for known shows with numbers in the title
        number_show_patterns = {
            r'9\W*1\W*1': '911',  # Matches 9-1-1, 9.1.1, 9 1 1, etc.
            r'9\W*1\W*1\s+Lone\s+Star': '911 Lone Star'  # Specific handling for 911 Lone Star
        }
        
        for pattern, replacement in number_show_patterns.items():
            if re.search(pattern, name, re.IGNORECASE):
                return replacement
        
        # Look for English title patterns specifically
        english_patterns = [
            # Look for "The Next Generation" pattern
            r'(?:Star Trek)?\s*The Next Generation',
            r'(?:Star Trek)?\s*Deep Space Nine',
            r'(?:Star Trek)?\s*Voyager',
            r'(?:Star Trek)?\s*Enterprise',
            r'(?:Star Trek)?\s*Discovery',
            r'(?:Star Trek)?\s*Picard',
            r'(?:Star Trek)?\s*Strange New Worlds',
        ]
        
        for pattern in english_patterns:
            match = re.search(pattern, name, re.IGNORECASE)
            if match:
                # For Star Trek series, prepend "Star Trek" if it's not already there
                matched_title = match.group(0)
                if "star trek" not in matched_title.lower() and any(trek_show in matched_title.lower() for trek_show in 
                    ["next generation", "deep space", "voyager", "enterprise", "discovery", "picard", "strange new worlds"]):
                    return f"Star Trek {matched_title}"
                return matched_title
        
        # Try to find English title among multiple languages
        # Look for sequences like: "Original Title - English Title" or "Original Title / English Title"
        
        # First check for "Original - English" pattern with known English words
        english_indicators = r'\b(the|and|of|in|on|at|by|for|with|a|an)\b'
        multi_lang_patterns = [
            # Match "Original - English" where English contains English words
            r'(.+?)\s*[\|\-/~:]\s*(.+?' + english_indicators + r'.+)',
            # Match "Original aka English"  
            r'(.+?)\s+aka\s+(.+)',
            # Match "Name (YEAR)" pattern which usually indicates the main title
            r'(.+?)\s*\(\d{4}\)',
        ]
        
        for pattern in multi_lang_patterns:
            match = re.search(pattern, name, re.IGNORECASE)
            if match:
                if len(match.groups()) == 2:
                    # Take the second part, which is often the English title
                    first_part = match.group(1).strip()
                    second_part = match.group(2).strip()
                    
                    # Check which part looks more like English
                    english_words_first = len(re.findall(english_indicators, first_part.lower()))
                    english_words_second = len(re.findall(english_indicators, second_part.lower()))
                    
                    # Take the part with more English words, with minimum length requirement
                    if english_words_second > english_words_first and len(second_part) > 5:
                        return self._clean_extracted_name(second_part)
                    elif len(first_part) > 5:
                        return self._clean_extracted_name(first_part)
                else:
                    # Single group pattern (like year pattern)
                    return self._clean_extracted_name(match.group(1))
        
        # Strip leading numbers followed by space (to handle "2 Star Trek...")
        name = re.sub(r'^\d+\s+', '', name)
        
        # First, attempt to extract just the TV show name using common patterns
        # Pattern 1: Show.Name.S01.stuff - extract everything before season identifier
        show_match = re.search(r'^(.*?)[Ss]\d{2}', name)
        if show_match:
            extracted_name = show_match.group(1).strip()
            if extracted_name:
                return self._clean_extracted_name(extracted_name)
        
        # Pattern 2: Show.Name.1080p.stuff - extract everything before resolution
        resolution_match = re.search(r'^(.*?)\d{3,4}[pP]', name)
        if resolution_match:
            extracted_name = resolution_match.group(1).strip()
            if extracted_name:
                return self._clean_extracted_name(extracted_name)
        
        # Pattern 3: Show.Name.2019.stuff - extract everything before year
        year_match = re.search(r'^(.*?)(?:19|20)\d{2}', name)
        if year_match:
            extracted_name = year_match.group(1).strip()
            if extracted_name:
                return self._clean_extracted_name(extracted_name)
        
        # If no patterns matched, fallback to general cleaning
        return self._clean_general_name(name)

    def _clean_extracted_name(self, name):
        """Clean an extracted name for use as a search term."""
        # Remove leading/trailing spaces and dots
        name = name.strip().strip('.')
        
        # Remove dots between words and numbers
        name = re.sub(r'(\d)\.(\d)', r'\1\2', name)  # 9.1.1 -> 911
        name = re.sub(r'(\w)\.(\w)', r'\1 \2', name)  # S.W.A.T -> S W A T
        
        # Replace dots with spaces
        name = name.replace('.', ' ')
        
        # Replace multiple spaces with a single space
        name = re.sub(r'\s+', ' ', name)
        
        return name

    def _clean_general_name(self, name):
        """General cleaning for names that don't match specific patterns."""
        # Remove leading/trailing spaces and dots
        name = name.strip().strip('.')
        
        # Remove dots between words and numbers
        name = re.sub(r'(\d)\.(\d)', r'\1\2', name)  # 9.1.1 -> 911
        name = re.sub(r'(\w)\.(\w)', r'\1 \2', name)  # S.W.A.T -> S W A T
        
        # Replace dots with spaces
        name = name.replace('.', ' ')
        
        # Replace multiple spaces with a single space
        name = re.sub(r'\s+', ' ', name)
        
        # Replace common separators
        name = re.sub(r'[_-]', ' ', name)
        
        return name

    def _match_title_to_tmdb(self, title, is_tv):
        """Match a title to TMDB with user interaction."""
        # Use the TMDB methods directly - they're already correctly implemented in the imported class
        search_function = self.tmdb.search_tv if is_tv else self.tmdb.search_movie
        # Use the imported format functions
        format_function = format_tv_result if is_tv else format_movie_result
        
        while True:
            print("\nSearching TMDB...")
            results = search_function(title, limit=3)
            
            if not results:
                print("No results found.")
                choice = get_input("\nEnter a new search term (or 's' to skip): ", cancel_value="s")
                
                # If exit or skip was chosen
                if choice == "s":
                    # Skip directly without confirmation
                    print("Skipping this folder.")
                    return None
                    
                # If not 's', use as new search term
                title = choice if choice else title  # Use original title if empty input
                continue
                    
            print("\nTop matches:")
            for i, result in enumerate(results, 1):
                # Format the result using the imported format functions
                overview = result.get('overview', '')
                if overview and len(overview) > 100:
                    overview = overview[:100] + "..."
                
                if is_tv:
                    name = result.get('name', 'Unknown')
                    year = result.get('first_air_date', '')[:4] if result.get('first_air_date') else 'Unknown'
                    print(f"{i}. {name} ({year}) - {overview}")
                else:
                    title = result.get('title', 'Unknown')
                    year = result.get('release_date', '')[:4] if result.get('release_date') else 'Unknown'
                    print(f"{i}. {title} ({year}) - {overview}")
                
            print("\n4. Enter a new search term")
            print("s. Skip this folder")
            print("Type 'exit' at any prompt to return to main menu")
            
            choice = get_input("\nSelect a match (1-4 or 's', default=1): ", default="1", cancel_value="exit_to_menu")
            
            # Check if user wants to exit
            if choice == "exit_to_menu":
                return "EXIT"  # Special return value to indicate exit
                
            if choice == 's':
                # Skip directly without confirmation
                print("Skipping this folder.")
                return None
            elif choice == '4':
                title = get_input("Enter a new search term: ", cancel_value="")
                
                # Check if user wants to exit
                if title == "":
                    return "EXIT"  # Special return value to indicate exit
                    
                continue
            elif choice in ['1', '2', '3']:
                index = int(choice) - 1
                if index < len(results):
                    return results[index]
            else:
                print("Invalid choice. Please try again.")
    
    def _process_tv_show_folder(self, subfolder, files, tmdb_show):
        """Process a TV show folder with user interaction."""
        # Get details from the TMDB API
        show_id = tmdb_show.get('id')
        try:
            # Try to get more detailed information from the API
            show_details = self.tmdb.get_tv_details(show_id)
            show_name = show_details.get('name', tmdb_show.get('name', 'Unknown Show'))
            first_air_date = show_details.get('first_air_date', tmdb_show.get('first_air_date', ''))[:4] if show_details.get('first_air_date', tmdb_show.get('first_air_date', '')) else None
            
            # Get additional IDs if needed
            imdb_id = None
            tvdb_id = None
            
            # Retrieve external IDs if folder ID settings require them
            settings = self._get_folder_structure_settings()
            if settings['imdb_folder_id'] or settings['tvdb_folder_id']:
                try:
                    external_ids = self.tmdb.get_tv_external_ids(show_id)
                    if settings['imdb_folder_id']:
                        imdb_id = external_ids.get('imdb_id')
                    if settings['tvdb_folder_id']:
                        tvdb_id = external_ids.get('tvdb_id')
                except Exception as e:
                    self.logger.error(f"Failed to fetch external IDs: {e}")
                    # Continue without external IDs
                    
        except Exception as e:
            # Fall back to basic info if API call fails
            self.logger.error(f"Error getting TV show details: {e}")
            show_name = tmdb_show.get('name', 'Unknown Show')
            first_air_date = tmdb_show.get('first_air_date', '')[:4] if tmdb_show.get('first_air_date') else None
            imdb_id = None
            tvdb_id = None
        
        print(f"\nProcessing TV show: {show_name}")
        
        # Try to detect seasons from file metadata
        seasons = set()
        for file in files:
            if file.get('season') is not None:
                seasons.add(file.get('season'))
        
        # If seasons were detected, ask user
        if seasons:
            print(f"\nDetected seasons: {', '.join(str(s) for s in sorted(seasons))}")
            season_choice = get_input(f"Use detected seasons? (Y/n): ", default="y", cancel_value="EXIT")
            
            if season_choice == "EXIT":
                return
                
            if season_choice.lower() != 'n':  # Default to yes if Enter is pressed
                # Use the detected seasons
                pass
            else:
                season_input = get_input("Enter season number (or multiple seasons separated by commas): ", 
                                         default="1", cancel_value="EXIT")
                
                if season_input == "EXIT":
                    return
                    
                try:
                    seasons = {int(s.strip()) for s in season_input.split(",")}
                except ValueError:
                    print("Invalid season numbers. Using detected seasons.")
        else:
            # Default to season 1
            print("\nNo seasons detected.")
            season_input = input("Enter season number (default: 1): ").strip()
            try:
                seasons = {int(season_input)} if season_input else {1}
            except ValueError:
                print("Invalid season number. Using season 1.")
                seasons = {1}
        
        # Get folder structure settings
        settings = self._get_folder_structure_settings()
        
        # Use the environment setting for renaming - no prompt
        rename_episodes = settings.get('rename_episodes', False)
        
        # Check for AUTO_EXTRACT_EPISODES from settings
        # Import this directly from the config to ensure we have the latest value
        from src.config import AUTO_EXTRACT_EPISODES
        
        # Use the value directly without prompting if AUTO_EXTRACT_EPISODES is True
        if AUTO_EXTRACT_EPISODES:
            auto_process = True
            print("\nAutomatically processing episodes (AUTO_EXTRACT_EPISODES=True)")
        else:
            auto_process = input("\nProcess episodes automatically? (Y/n): ").strip().lower()
            auto_process = auto_process != 'n'  # Default to yes if Enter is pressed

        # Determine if this is a 4K show based on file resolution
        is_4k = self._detect_4k_content(files)
        
        # Determine if this is an anime show
        settings = self._get_folder_structure_settings()
        is_anime_show = settings['anime_separation'] and any(self._is_anime(f['filename']) for f in files if f['type'] == 'video')
        
        # Choose the appropriate base folder
        if is_anime_show:
            show_base_folder = settings['custom_anime_show_folder']
        elif is_4k and settings['custom_4kshow_folder']:
            show_base_folder = settings['custom_4kshow_folder']
        else:
            show_base_folder = settings['custom_show_folder']
        
        # Build folder name with proper IDs and year
        folder_name_parts = [show_name]
        
        # Add year if available
        if first_air_date:
            folder_name_parts.append(f"({first_air_date})")
        
        # Add IDs based on settings
        id_parts = []
        if settings['tmdb_folder_id'] and show_id:
            id_parts.append(f"tmdb-{show_id}")
        if settings['imdb_folder_id'] and imdb_id:
            id_parts.append(f"imdb-{imdb_id}")
        if settings['tvdb_folder_id'] and tvdb_id:
            id_parts.append(f"tvdb-{tvdb_id}")
        
        if id_parts:
            folder_name_parts.append(f"[{' '.join(id_parts)}]")
        
        # Combine all parts and clean
        clean_show_name = self._clean_filename(" ".join(folder_name_parts))

        # Continue with symlink creation
        print(f"\nCreating symlinks in folder: {clean_show_name}")

        # Create a dictionary to track episodes processed per season
        processed_episodes = {season: set() for season in seasons}

        # Track how many files we've processed
        successful_files = 0
        skipped_files = 0
        error_files = 0

        # Process each file
        for file in files:
            try:
                # Skip non-video files for auto-processing
                if file['type'] != 'video' and auto_process:
                    continue
                    
                filename = file['filename']
                file_path = file['path']
                
                # Try to extract season and episode information
                if auto_process:
                    # If auto_process is True, try to extract season/episode from filename
                    extracted_season, extracted_episode = self._extract_episode_info(file_path, filename)
                    
                    # Skip files with no episode number if auto-processing
                    if extracted_episode is None:
                        print(f"  ⚠ Skipping (no episode number): {filename}")
                        skipped_files += 1
                        continue
                        
                    # Use extracted season number if available, otherwise fallback to the season we're processing
                    season_to_use = extracted_season if extracted_season is not None else seasons[0]
                    
                    # Skip if this episode was already processed for this season
                    if extracted_episode in processed_episodes.get(season_to_use, set()):
                        print(f"  ⚠ Skipping duplicate: S{season_to_use:02d}E{extracted_episode:02d} - {filename}")
                        skipped_files += 1
                        continue
                        
                    # Mark this episode as processed
                    if season_to_use not in processed_episodes:
                        processed_episodes[season_to_use] = set()
                    processed_episodes[season_to_use].add(extracted_episode)
                    
                    # Create the symlink
                    file_info = {
                        'path': file_path,
                        'filename': filename,
                        'show_name': show_name,
                        'season': season_to_use,
                        'episode': extracted_episode,
                        'folder_name': clean_show_name,
                        'is_anime': is_anime_show,
                        'is_4k': is_4k
                    }
                    
                    # Try to get episode title from TMDB for enhanced naming
                    if rename_episodes:
                        episode_title = self._get_episode_title_from_tmdb(show_id, season_to_use, extracted_episode)
                        if episode_title:
                            file_info['episode_title'] = episode_title
                    
                    # Create the symlink
                    success = self._create_tv_symlink(file_info)
                    
                    if success:
                        print(f"  ✓ S{season_to_use:02d}E{extracted_episode:02d} - {filename}")
                        successful_files += 1
                    else:
                        print(f"  ✗ Error: S{season_to_use:02d}E{extracted_episode:02d} - {filename}")
                        error_files += 1
                        
                else:
                    # Manual processing mode - show each file and ask user
                    print(f"\nFile: {filename}")
                    use_file = input("Process this file? (Y/n/skip): ").strip().lower()
                    
                    if use_file == 'skip':
                        print("Skipping rest of files in this folder.")
                        break
                    elif use_file == 'n':
                        print("Skipping this file.")
                        skipped_files += 1
                        continue
                        
                    # Ask for season/episode if needed
                    season_to_use = None
                    episode_to_use = None
                    
                    # Try auto extraction first
                    extracted_season, extracted_episode = self._extract_episode_info(file_path, filename)
                    
                    if extracted_season is not None and extracted_episode is not None:
                        print(f"Detected: Season {extracted_season}, Episode {extracted_episode}")
                        use_detected = input("Use these values? (Y/n): ").strip().lower()
                        
                        if use_detected != 'n':
                            season_to_use = extracted_season
                            episode_to_use = extracted_episode
                    
                    # If auto-extraction failed or user rejected, ask manually
                    if season_to_use is None:
                        try:
                            season_input = input("Enter season number (default: 1): ").strip()
                            season_to_use = int(season_input) if season_input else 1
                        except ValueError:
                            print("Invalid season number. Using season 1.")
                            season_to_use = 1
                            
                    if episode_to_use is None:
                        try:
                            episode_input = input("Enter episode number: ").strip()
                            episode_to_use = int(episode_input) if episode_input else None
                            
                            if episode_to_use is None:
                                print("Episode number is required. Skipping this file.")
                                skipped_files += 1
                                continue
                        except ValueError:
                            print("Invalid episode number. Skipping this file.")
                            skipped_files += 1
                            continue
                    
                    # Create the symlink
                    file_info = {
                        'path': file_path,
                        'filename': filename,
                        'show_name': show_name,
                        'season': season_to_use,
                        'episode': episode_to_use,
                        'folder_name': clean_show_name,
                        'is_anime': is_anime_show,
                        'is_4k': is_4k
                    }
                    
                    # Try to get episode title from TMDB for enhanced naming
                    if rename_episodes:
                        episode_title = self._get_episode_title_from_tmdb(show_id, season_to_use, episode_to_use)
                        if episode_title:
                            file_info['episode_title'] = episode_title
                    
                    # Create the symlink
                    success = self._create_tv_symlink(file_info)
                    
                    if success:
                        print(f"  ✓ Created symlink for S{season_to_use:02d}E{episode_to_use:02d} - {filename}")
                        successful_files += 1
                    else:
                        print(f"  ✗ Error creating symlink for {filename}")
                        error_files += 1
        
            except Exception as e:
                print(f"  ✗ Error processing {filename}: {e}")
                self.logger.error(f"Error processing file {filename}: {e}")
                error_files += 1

        # Show summary
        print(f"\nSummary: {successful_files} files processed, {skipped_files} skipped, {error_files} errors")

    def _create_tv_symlink(self, file_info):
        """Create symlink for TV show file."""
        try:
            # Get settings
            settings = self._get_folder_structure_settings()
            
            # Choose the appropriate base folder
            if file_info.get('is_anime'):
                base_folder = settings['custom_anime_show_folder']
            elif file_info.get('is_4k') and settings['custom_4kshow_folder']:
                base_folder = settings['custom_4kshow_folder']
            else:
                base_folder = settings['custom_show_folder']
            
            # Determine destination folder structure
            destination_dir = os.path.join(DESTINATION_DIRECTORY, base_folder)
            
            # Add show folder with name
            show_folder = file_info['folder_name']
            destination_dir = os.path.join(destination_dir, show_folder)
            
            # Add season folder
            season_folder = f"Season {file_info['season']:02d}"
            destination_dir = os.path.join(destination_dir, season_folder)
            
            # Create destination directory if it doesn't exist
            os.makedirs(destination_dir, exist_ok=True)
            
            # Determine destination filename
            file_ext = os.path.splitext(file_info['filename'])[1]
            
            # Construct episode filename
            if settings.get('rename_episodes', False) and 'episode_title' in file_info:
                # Use formatted name with episode title
                dest_filename = f"S{file_info['season']:02d}E{file_info['episode']:02d} - {file_info['episode_title']}{file_ext}"
            else:
                # Use simple episode numbering
                dest_filename = f"S{file_info['season']:02d}E{file_info['episode']:02d}{file_ext}"
            
            # Clean the filename to ensure it's valid
            dest_filename = self._clean_filename(dest_filename)
            
            # Full destination path
            dest_path = os.path.join(destination_dir, dest_filename)
            
            # Create the symlink
            return self._create_symlink(file_info['path'], dest_path)
            
        except Exception as e:
            self.logger.error(f"Error creating TV symlink: {e}")
            return False

    def _create_movie_symlink(self, file_info):
        """Create a symlink for a movie file."""
        try:
            # Get stored settings for this file
            settings = self._get_folder_structure_settings()
            os.makedirs(dest_dir, exist_ok=True)
            
            # Create the symlink
            source_path = file_info['path']
            self._create_symlink(source_path, dest_path)
            self.symlink_count += 1
            return True
            
        except Exception as e:
            self.logger.error(f"Error creating movie symlink for {file_info['path']}: {e}")
            self.errors += 1
            return False

    def _create_symlink(self, source_path, dest_path):
        """Create a symlink from source to destination."""
        try:
            # Check if the symlink already exists
            if os.path.exists(dest_path):
                # If it's already a symlink to the same source, nothing to do
                if os.path.islink(dest_path) and os.readlink(dest_path) == source_path:
                    return
                else:
                    # Remove existing file or symlink
                    os.remove(dest_path)
            
            # Create the symlink
            os.symlink(source_path, dest_path)
                
        except PermissionError as e:
            self.logger.error(f"Permission error creating symlink: {e}")
            raise
        except FileNotFoundError as e:
            self.logger.error(f"File not found error creating symlink: {e}")
            raise
        except Exception as e:
            self.logger.error(f"Error creating symlink: {e}")
            raise
    
    def _is_anime(self, filename):
        """Enhanced check if a file is likely to be anime using filename patterns."""
        try:
            # Common anime keywords and patterns
            anime_keywords = [
                'anime', 'jp', 'jpn', 'japanese', 'subs', 'subbed', 'raw',
                '[horriblesubs]', '[subsplease]', '[erai-raws]', '[golumpa]',
                '[judas]', '[anime time]', '[anime-time]', '[animetime]',
                '[ohys-raws]', '[yameii]', '[neoggukttae]', '[ember]',
                'bakemonogatari', 'monogatari', 'naruto', 'one piece', 'gintama',
                'gundam', 'fullmetal', 'attack on titan', 'shingeki', 'evangelion',
                'dragonball', 'dragon ball', 'bleach', 'hunter x hunter',
                'jojo', 'jujutsu', 'demon slayer', 'kimetsu', 'my hero academia',
                'boku no hero', 'fairy tail', 'fate/', 'sword art online', 'sao',
                'persona', 'danmachi', 'konosuba', 'rezero', 're:zero', 'steins;gate'
            ]
            
            # Common tokusatsu shows that might be misidentified
            tokusatsu_keywords = [
                'kamen rider', 'super sentai', 'ultraman', 'garo',
                'power rangers', 'metal heroes'
            ]
            
            filename_lower = filename.lower()
            return any(keyword in filename_lower for keyword in anime_keywords) and not any(keyword in filename_lower for keyword in tokusatsu_keywords)
        except Exception as e:
            self.logger.error(f"Error checking if file is anime: {e}")
            return False
    
    def _clean_filename(self, name):
        """Clean a name for use as a filename or directory name."""
        # Replace invalid characters
        invalid_chars = ['<', '>', ':', '"', '/', '\\', '|', '?', '*']
        result = name
        
        for char in invalid_chars:
            result = result.replace(char, '_')
        
        # Remove leading/trailing spaces and dots
        result = result.strip().strip('.')
        
        return result
    
    def _update_progress(self, current, total):
        """Display a progress bar."""
        bar_length = 50
        if total == 0:
            progress = 1
        else:
            progress = current / total
            
        arrow = '█' * int(round(progress * bar_length))
        spaces = ' ' * (bar_length - len(arrow))
        
        percent = round(progress * 100, 1)
        
        # Use carriage return and clear the line before updating
        print(f"\r\033[K", end="")  # \033[K clears from cursor to end of line
        print(f"\rProgress: [{arrow}{spaces}] {percent}% ({current}/{total})", end='', flush=True)

    def _get_folder_structure_settings(self):
        """Get folder structure settings from environment variables."""
        from src.config import (
            # Custom folder names
            CUSTOM_SHOW_FOLDER, CUSTOM_4KSHOW_FOLDER, CUSTOM_ANIME_SHOW_FOLDER,
            CUSTOM_MOVIE_FOLDER, CUSTOM_4KMOVIE_FOLDER, CUSTOM_ANIME_MOVIE_FOLDER,
            
            # Feature flags
            ANIME_SEPARATION, TMDB_FOLDER_ID, IMDB_FOLDER_ID, TVDB_FOLDER_ID,
            
            # Resolution structure
            SHOW_RESOLUTION_STRUCTURE, MOVIE_RESOLUTION_STRUCTURE,
            
            # Show resolution folder mappings
            SHOW_RESOLUTION_FOLDER_REMUX_4K, SHOW_RESOLUTION_FOLDER_REMUX_1080P,
            SHOW_RESOLUTION_FOLDER_REMUX_DEFAULT, SHOW_RESOLUTION_FOLDER_2160P,
            SHOW_RESOLUTION_FOLDER_1080P, SHOW_RESOLUTION_FOLDER_720P,
            SHOW_RESOLUTION_FOLDER_480P, SHOW_RESOLUTION_FOLDER_DVD,
            SHOW_RESOLUTION_FOLDER_DEFAULT,
            
            # Movie resolution folder mappings
            MOVIE_RESOLUTION_FOLDER_REMUX_4K, MOVIE_RESOLUTION_FOLDER_REMUX_1080P,
            MOVIE_RESOLUTION_FOLDER_REMUX_DEFAULT, MOVIE_RESOLUTION_FOLDER_2160P,
            MOVIE_RESOLUTION_FOLDER_1080P, MOVIE_RESOLUTION_FOLDER_720P,
            MOVIE_RESOLUTION_FOLDER_480P, MOVIE_RESOLUTION_FOLDER_DVD,
            MOVIE_RESOLUTION_FOLDER_DEFAULT
        )
        
        # Create a settings dictionary
        settings = {
            # Custom folder names with fallbacks
            'custom_show_folder': CUSTOM_SHOW_FOLDER or "TV Shows",
            'custom_4kshow_folder': CUSTOM_4KSHOW_FOLDER or "4K TV Shows",
            'custom_anime_show_folder': CUSTOM_ANIME_SHOW_FOLDER or "Anime Shows",
            'custom_movie_folder': CUSTOM_MOVIE_FOLDER or "Movies",
            'custom_4kmovie_folder': CUSTOM_4KMOVIE_FOLDER or "4K Movies",
            'custom_anime_movie_folder': CUSTOM_ANIME_MOVIE_FOLDER or "Anime Movies",
            
            # Feature flags
            'anime_separation': self._parse_bool(ANIME_SEPARATION, True),
            'tmdb_folder_id': self._parse_bool(TMDB_FOLDER_ID, False),
            'imdb_folder_id': self._parse_bool(IMDB_FOLDER_ID, False),
            'tvdb_folder_id': self._parse_bool(TVDB_FOLDER_ID, False),
            
            # Resolution structure flags
            'show_resolution_structure': self._parse_bool(SHOW_RESOLUTION_STRUCTURE, False),
            'movie_resolution_structure': self._parse_bool(MOVIE_RESOLUTION_STRUCTURE, False),
            
            # Show resolution folder mappings
            'show_resolution_folders': {
                'remux_4k': SHOW_RESOLUTION_FOLDER_REMUX_4K or "UltraHDRemuxShows",
                'remux_1080p': SHOW_RESOLUTION_FOLDER_REMUX_1080P or "1080pRemuxLibrary",
                'remux_default': SHOW_RESOLUTION_FOLDER_REMUX_DEFAULT or "RemuxShows",
                '2160p': SHOW_RESOLUTION_FOLDER_2160P or "UltraHD",
                '1080p': SHOW_RESOLUTION_FOLDER_1080P or "FullHD",
                '720p': SHOW_RESOLUTION_FOLDER_720P or "SDClassics",
                '480p': SHOW_RESOLUTION_FOLDER_480P or "Retro480p",
                'dvd': SHOW_RESOLUTION_FOLDER_DVD or "RetroDVD",
                'default': SHOW_RESOLUTION_FOLDER_DEFAULT or "Shows"
            },
            
            # Movie resolution folder mappings
            'movie_resolution_folders': {
                'remux_4k': MOVIE_RESOLUTION_FOLDER_REMUX_4K or "4KRemux",
                'remux_1080p': MOVIE_RESOLUTION_FOLDER_REMUX_1080P or "1080pRemux",
                'remux_default': MOVIE_RESOLUTION_FOLDER_REMUX_DEFAULT or "MoviesRemux",
                '2160p': MOVIE_RESOLUTION_FOLDER_2160P or "UltraHD",
                '1080p': MOVIE_RESOLUTION_FOLDER_1080P or "FullHD",
                '720p': MOVIE_RESOLUTION_FOLDER_720P or "SDMovies",
                '480p': MOVIE_RESOLUTION_FOLDER_480P or "Retro480p",
                'dvd': MOVIE_RESOLUTION_FOLDER_DVD or "DVDClassics",
                'default': MOVIE_RESOLUTION_FOLDER_DEFAULT or "Movies"
            }
        }
        
        return settings

    def _parse_bool(self, value, default=False):
        """Parse a string boolean value from environment variables."""
        if value is None:
            return default
            
        if isinstance(value, bool):
            return value
            
        true_values = ('true', 'yes', '1', 'y', 't')
        false_values = ('false', 'no', '0', 'n', 'f')
        
        if isinstance(value, str):
            if value.lower() in true_values:
                return True
            if value.lower() in false_values:
                return False
        
        return default

    def _detect_4k_content(self, files):
        """Detect if files are likely 4K content based on filename patterns."""
        for file in files:
            filename = file.get('filename', '').lower()
            
            # Common 4K indicators in filenames
            if any(pattern in filename for pattern in [
                '2160p', '4k', 'uhd', 'ultrahd', '4320p', '8k'
            ]):
                return True
                
            # Look for resolution indicators in the file path
            file_path = file.get('path', '').lower()
            if any(pattern in file_path for pattern in [
                '2160p', '4k', 'uhd', 'ultrahd', '4320p', '8k'
            ]):
                return True
        
        return False

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
        is_tv = item['is_tv']
        suggested_name = item.get('suggested_name', os.path.basename(subfolder))
        
        print(f"\nSkipped subfolder: {subfolder}")
        print(f"Contains {len(files)} media files")
        print(f"Type: {'TV Show' if is_tv else 'Movie'}")
        print(f"Suggested title: {suggested_name}")
        print("Type 'exit' at any prompt to return to main menu")
        
        choice = get_input("\nChoose action: (p)rocess, (s)kip again, (q)uit reviewing (default=p): ", 
                         default="p", cancel_value="q")
        
        if choice == "q":
            # User chose to exit/quit
            break
        
        if choice == 'p':
            # Process this item
            processor = DirectoryProcessor('.')  # Create a temporary processor for handling this item
            
            if is_tv:
                # Search TMDB for TV show
                search_term = get_input(f"\nEnter search term for TV show (default='{suggested_name}'): ", 
                                     default=suggested_name, cancel_value="")
                
                if search_term == "":
                    # User chose to exit
                    break
                    
                results = processor.tmdb.search_tv(search_term, limit=3)
                
                if results:
                    print("\nSearch results:")
                    for i, result in enumerate(results, 1):
                        name = result.get('name', 'Unknown')
                        year = result.get('first_air_date', '')[:4] if result.get('first_air_date') else 'Unknown'
                        print(f"{i}. {name} ({year})")
                    
                    match_choice = get_input("\nSelect a match (1-3 or 's' to skip, default=1): ", 
                                          default="1", cancel_value="s")
                    
                    if match_choice in ['1', '2', '3']:
                        index = int(match_choice) - 1
                        if index < len(results):
                            matched_item = results[index]
                            processor._process_tv_show_folder(subfolder, files, matched_item)
                            skipped_items_registry.pop(0)  # Remove this item from registry
                            continue
                    else:  # User chose to skip or exit
                        print("Keeping item in skipped registry.")
                        continue
                
                # If we get here, either no results or user chose to skip
                print("Keeping item in skipped registry.")
                
            else:
                # Similar modifications for movie processing
                # ...
                search_term = get_input(f"\nEnter search term for movie (default='{suggested_name}'): ", 
                                     default=suggested_name, cancel_value="")
                
                if search_term == "":
                    # User chose to exit
                    break
                    
                results = processor.tmdb.search_movie(search_term, limit=3)
                
                if results:
                    print("\nSearch results:")
                    for i, result in enumerate(results, 1):
                        title = result.get('title', 'Unknown')
                        year = result.get('release_date', '')[:4] if result.get('release_date') else 'Unknown'
                        print(f"{i}. {title} ({year})")
                    
                    match_choice = get_input("\nSelect a match (1-3 or 's' to skip, default=1): ", 
                                          default="1", cancel_value="s")
                    
                    if match_choice in ['1', '2', '3']:
                        index = int(match_choice) - 1
                        if index < len(results):
                            matched_item = results[index]
                            processor._process_movie_folder(subfolder, files, matched_item)
                            skipped_items_registry.pop(0)  # Remove this item from registry
                            continue
                    else:  # User chose to skip or exit
                        print("Keeping item in skipped registry.")
                        continue
                
                # If we get here, either no results or user chose to skip
                print("Keeping item in skipped registry.")
        
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

def process_skipped_items():
    """Process previously skipped items."""
    skipped_items = load_skipped_items()
    
    if not skipped_items:
        print("No skipped items to process.")
        input("Press Enter to continue...")
        return
    
    clear_screen()
    display_ascii_art()
    print("=" * 60)
    print(f"Found {len(skipped_items)} previously skipped items.")
    
    # List all skipped items with index
    for i, item in enumerate(skipped_items, 1):
        subfolder = item.get('subfolder', 'Unknown')
        name = item.get('suggested_name', 'Unknown')
        timestamp = item.get('timestamp', 0)
        skipped_time = datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M') if timestamp else 'Unknown'
        
        print(f"{i}. {name} - {subfolder} (Skipped: {skipped_time})")
    
    print("\nEnter the number of the item to process, 'a' to process all, or 'q' to quit:")
    choice = input("> ").strip().lower()
    
    if choice == 'q':
        return
    elif choice == 'a':
        # Process all skipped items
        print("Processing all skipped items...")
        # Implementation would go here
    elif choice.isdigit() and 1 <= int(choice) <= len(skipped_items):
        # Process the selected skipped item
        idx = int(choice) - 1
        item = skipped_items[idx]
        print(f"Processing: {item.get('suggested_name', 'Unknown')}")
        # Implementation would go here
        
        # If successfully processed, remove from registry
        skipped_items.pop(idx)
        save_skipped_items(skipped_items)
    else:
        print("Invalid choice.")
    
    input("Press Enter to continue...")

class MainMenu:
    def __init__(self):
        # Initialize menu class
        self.logger = get_logger(__name__)
        
    def directory_scan(self):
        """Scan a directory for media files."""
        # Clear screen first
        clear_screen()
        
        # Display ASCII art at the top
        display_ascii_art()
        
        # Add only a separator line
        print("=" * 60)
        
        # Just show the prompt directly
        while True:
            path = input("Enter or drag/drop directory to scan (or 'c' to cancel): ")
            if path.lower() == 'c':
                return
            
            # Clean the path without showing output
            cleaned_path = _clean_directory_path(path)
            
            # First check - path exists and is a directory
            if os.path.isdir(cleaned_path):
                try:
                    # Save the initial scan info
                    save_scan_history(cleaned_path)
                    
                    # Create and use our DirectoryProcessor with real implementation
                    processor = DirectoryProcessor(cleaned_path)
                    processor.process()
                    break
                except Exception as e:
                    print(f"Error processing directory: {e}")
                    self.logger.error(f"Error in directory scan: {e}", exc_info=True)
                    input("\nPress Enter to try again...")
            else:
                print(f"Invalid directory: '{cleaned_path}'")
                
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

    def individual_scan(self):
        """Scan an individual file or folder."""
        # Clear screen first
        clear_screen()
        
        # Display ASCII art at the top
        display_ascii_art()
        
        # Add only a separator line
        print("=" * 60)
        
        # No extra text headers, just show the prompt directly
        while True:
            path = input("Enter or drag/drop file or folder to scan (or 'c' to cancel): ")
            if path.lower() == 'c':
                return
                
            # Clean the path (remove quotes from drag and drop) - no output
            path = _clean_directory_path(path)
            
            if os.path.exists(path):
                if os.path.isdir(path):
                    # Process as a single folder
                    print(f"\nProcessing folder: {path}")
                    try:
                        # Create a DirectoryProcessor for this single folder
                        processor = DirectoryProcessor(path)
                        processor.process()
                    except Exception as e:
                        print(f"Error processing folder: {e}")
                        self.logger.error(f"Error in individual scan: {e}", exc_info=True)
                else:
                    # Process as a single file
                    print(f"\nProcessing file: {path}")
                    print("Individual file processing not yet implemented.")
                    # Future implementation would go here
                    
                input("\nPress Enter to continue...")
                break
            else:
                print(f"Invalid path: '{path}'")
                
                # Give helpful suggestions
                print("\nPlease make sure:")
                print("1. The path is entered correctly (case-sensitive)")
                print("2. You have permission to access this location")
                print("3. Network drives are properly mounted (if applicable)")
                
                input("\nPress Enter to try again...")
    
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
            print("1. Directory Scan")
            print("2. Individual Scan")
            
            # Dynamic menu options based on history existence
            has_history = history_exists()
            
            # Declare the global variable before using it
            global skipped_items_registry
            has_skipped = len(skipped_items_registry) > 0
            
            next_option = 3
            
            if has_history:
                print(f"{next_option}. Resume Scan")
                print(f"{next_option+1}. Clear History")
                next_option += 2
            
            # Debug output to verify skipped items are detected
            print(f"\nDebug: Skipped items count: {len(skipped_items_registry)}")
            
            if has_skipped:
                print(f"{next_option}. Review Skipped Items ({len(skipped_items_registry)})")
                next_option += 1
            
            print("0. Quit")
            print("h. Help")
            
            # Determine the valid choices
            max_choice = next_option - 1
            
            choice = input(f"\nEnter choice (0-{max_choice}, h): ").strip().lower()
            
            # Handle menu choices
            if choice == '1':
                clear_screen()
                self.directory_scan()
            elif choice == '2':
                clear_screen()
                self.individual_scan()
            elif choice == '3' and has_history:
                clear_screen()
                self.resume_scan()
            elif choice == '4' and has_history:
                # Clear both scan history and skipped items registry
                clear_scan_history()
                
                # We already declared global above, no need to repeat
                skipped_items_registry = []
                save_skipped_items([])
                
                print("Scan history and skipped items cleared.")
                input("\nPress Enter to continue...")
            # Fix the condition to properly check skipped items
            elif (has_skipped and choice == str(next_option - 1)):
                clear_screen()
                review_skipped_items()
            elif choice == '0':
                clear_screen()
                break
            elif choice == 'h':
                display_help()
            else:
                print("Invalid choice. Please try again.")
                input("\nPress Enter to continue...")

def get_input(prompt, default=None, cancel_value=None):
    """
    Get user input with universal exit command handling.
    
    Args:
        prompt: The prompt to display to the user
        default: Default value if user presses Enter
        cancel_value: Value to return if user types "exit"
        
    Returns:
        User input, or default if Enter was pressed, or cancel_value if "exit" was typed
    """
    user_input = input(prompt).strip()
    
    # Check for exit command
    if user_input.lower() == "exit":
        print("Returning to main menu...")
        return cancel_value
    
    # Return default value if Enter was pressed
    if not user_input and default is not None:
        return default
        
    return user_input

def main():
    """Main entry point for the application."""
    # Set up logging first
    setup_logging()
    
    # Then set console handler level to WARNING to suppress INFO messages
    for handler in logging.getLogger().handlers:
        if isinstance(handler, logging.StreamHandler):
            handler.setLevel(logging.WARNING)
    
    # Get logger only after setup
    logger = get_logger(__name__)
    logger.info("Starting Scanly")  # This will be logged to file but not shown in console
    
    if not os.path.exists(DESTINATION_DIRECTORY):
        logger.warning(f"Destination directory does not exist: {DESTINATION_DIRECTORY}")
        logger.warning("Directories will be created when files are processed")

    # Clear screen before showing welcome message
    clear_screen()

    # Display ASCII art 
    display_ascii_art()

    # Just keep a separator below the art
    print("=" * 60)

    try:
        # Create and show the main menu
        menu = MainMenu()
        menu.show()
    except KeyboardInterrupt:
        clear_screen()
        print("\nExiting Scanly. Goodbye!")
    except Exception as e:
        logger.error(f"Unhandled exception: {e}", exc_info=True)
        print(f"\nAn error occurred: {e}")
        print("Check the log for more details.")
        input("\nPress Enter to exit...")
    
    logger.info("Scanly shutdown")

if __name__ == "__main__":
    main()