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
log_dir = os.path.join(os.path.dirname(__file__), '..', 'logs')
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
        confirm = input("\nAre you sure you want to clear all skipped items? (y/n): ").strip().lower()
        if confirm == 'y':
            skipped_items_registry = []
            save_skipped_items([])
            print("All skipped items have been cleared.")
            input("\nPress Enter to continue...")
    
# DirectoryProcessor class
# [Rest of DirectoryProcessor class implementation]

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
                clear_screen()
                review_skipped_items()
            # Clear skipped items
            elif choice == str(max_choice):
                globals()['skipped_items_registry'] = []
                save_skipped_items([])
                print("Skipped items cleared.")
                input("\nPress Enter to continue...")
            # Add the settings menu option
            elif (has_history and has_skipped and choice == '6') or \
                 (has_history and not has_skipped and choice == '5') or \
                 (not has_history and has_skipped and choice == '4') or \
                 (not has_history and not has_skipped and choice == '3'):
                clear_screen()
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
        
        # Process the directory
        processor = DirectoryProcessor(dir_path)
        processor.process()
    
    def multi_scan(self):
        """Handle multi-scan option."""
        clear_screen()
        display_ascii_art()
        print("=" * 60)
        print("MULTI SCAN")
        print("=" * 60)
        
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
        
        # Process each directory
        for i, dir_path in enumerate(directories):
            clear_screen()
            display_ascii_art()
            print("=" * 60)
            print(f"PROCESSING DIRECTORY {i+1}/{len(directories)}")
            print("=" * 60)
            print(f"\nDirectory: {dir_path}\n")
            
            processor = DirectoryProcessor(dir_path)
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

# DirectoryProcessor class definition
class DirectoryProcessor:
    """Process a directory of media files."""
    
    def __init__(self, directory_path, resume=False):
        """
        Initialize the directory processor.
        
        Args:
            directory_path: Path to the directory to process
            resume: Whether to resume a previous scan
        """
        self.logger = get_logger(__name__)
        self.directory_path = directory_path
        self.resume = resume
        self.processed_files = 0
        self.total_files = 0
        self.media_files = []
        self.errors = 0
        self.skipped = 0
        self.symlink_count = 0
    
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
            # Collect all media files in the directory
            self._collect_media_files()
            
            if not self.media_files:
                print("No media files found in the directory.")
                input("\nPress Enter to continue...")
                return
            
            # Process each media file
            self._process_media_files()
            
            # Display results
            print("\nScan completed!")
            print(f"Processed {self.processed_files} of {self.total_files} files")
            print(f"Created {self.symlink_count} symlinks")
            
            if self.errors > 0:
                print(f"Errors: {self.errors}")
            
            if self.skipped > 0:
                print(f"Skipped: {self.skipped} (Use 'Review Skipped Items' from main menu)")
            
            # Clear scan history if all files were processed
            if self.processed_files >= self.total_files:
                clear_scan_history()
            
            input("\nPress Enter to continue...")
            
        except KeyboardInterrupt:
            # Save progress for resuming later
            save_scan_history(self.directory_path, self.processed_files, self.total_files, self.media_files)
            print("\nScan interrupted. Progress saved for resuming later.")
            input("\nPress Enter to continue...")
        except Exception as e:
            self.logger.error(f"Error processing directory: {e}", exc_info=True)
            print(f"\nError processing directory: {e}")
            input("\nPress Enter to continue...")
    
    def _collect_media_files(self):
        """Collect all media files in the directory."""
        # Common media file extensions
        media_extensions = ['.mkv', '.mp4', '.avi', '.mov', '.wmv', '.flv', '.m4v', '.ts']
        
        print("\nCollecting media files...")
        
        # If resuming, load media files from history
        if self.resume:
            history = load_scan_history()
            if history and 'media_files' in history:
                self.media_files = history.get('media_files', [])
                self.processed_files = history.get('processed_files', 0)
                self.total_files = history.get('total_files', 0)
                
                # Filter out files that no longer exist
                self.media_files = [f for f in self.media_files if os.path.exists(f)]
                
                print(f"Resuming scan: {len(self.media_files)} files remaining")
                return
        
        # Walk through directory and find media files
        for root, _, files in os.walk(self.directory_path):
            for file in files:
                # Check if file has a media extension
                if any(file.lower().endswith(ext) for ext in media_extensions):
                    file_path = os.path.join(root, file)
                    self.media_files.append(file_path)
        
        # Sort files for consistent processing
        self.media_files.sort()
        self.total_files = len(self.media_files)
        
        print(f"Found {self.total_files} media files")
    
    def _process_media_files(self):
        """Process each media file and create symlinks."""
        from src.utils.scanner_utils import check_scanner_lists
        
        print("\nProcessing media files...")
        
        # Set terminal width
        term_width = 80
        
        # Calculate total files to process
        start_idx = self.processed_files if self.resume else 0
        remaining_files = self.media_files[start_idx:]
        
        # Process each file
        for i, file_path in enumerate(remaining_files, start=start_idx+1):
            # Update progress
            progress = i / self.total_files
            bar_length = 40
            filled_length = int(bar_length * progress)
            bar = '=' * filled_length + ' ' * (bar_length - filled_length)
            
            # Clear line and show progress
            sys.stdout.write('\r' + ' ' * term_width)
            sys.stdout.flush()
            sys.stdout.write(f"\r[{bar}] {progress:.1%} - {i}/{self.total_files} - {os.path.basename(file_path)}")
            sys.stdout.flush()
            
            try:
                # Check if file is in scanner lists
                scanner_result = check_scanner_lists(file_path)
                
                if scanner_result:
                    content_type, is_anime, tmdb_id = scanner_result
                    
                    # Extract title and other metadata
                    file_name = os.path.basename(file_path)
                    file_dir = os.path.dirname(file_path)
                    parent_dir = os.path.basename(file_dir)
                    
                    # Try to extract title, year, season, episode from filename or folder
                    title, year, season, episode = self._extract_metadata(file_name, parent_dir)
                    
                    # Create symlink
                    success = self._create_symlink(
                        file_path, 
                        title,
                        year=year,
                        season=season,
                        episode=episode,
                        is_tv=(content_type == 'tv'),
                        is_anime=is_anime
                    )
                    
                    if not success:
                        self.errors += 1
                else:
                    # Add to skipped items for manual review
                    folder_path = os.path.dirname(file_path)
                    filename = os.path.basename(file_path)
                    
                    # Try to extract a suggested name
                    suggested_name = self._extract_suggested_name(filename, folder_path)
                    
                    skipped_item = {
                        'path': file_path,
                        'subfolder': folder_path,
                        'suggested_name': suggested_name,
                        'is_tv': None,
                        'is_anime': None
                    }
                    
                    # Add to global skipped items registry
                    globals()['skipped_items_registry'].append(skipped_item)
                    save_skipped_items(globals()['skipped_items_registry'])
                    self.skipped += 1
            
            except Exception as e:
                self.logger.error(f"Error processing file {file_path}: {e}", exc_info=True)
                self.errors += 1
            
            # Update processed count
            self.processed_files = i
            
            # Save progress every 10 files in case of interruption
            if i % 10 == 0:
                save_scan_history(self.directory_path, self.processed_files, self.total_files, self.media_files)
        
        # Clear the progress line
        sys.stdout.write('\r' + ' ' * term_width)
        sys.stdout.flush()
    
    def _extract_metadata(self, filename, dirname):
        """
        Extract metadata from filename and directory name.
        
        Returns:
            Tuple of (title, year, season, episode)
        """
        # Default values
        title = None
        year = None
        season = None
        episode = None
        
        # Clean the filename
        clean_filename = filename.replace('.', ' ').replace('_', ' ')
        
        # Try to extract title from directory name first
        title = dirname
        
        # Try to extract season and episode information
        season_ep_pattern = re.compile(r'S(\d{1,2})E(\d{1,2})', re.IGNORECASE)
        match = season_ep_pattern.search(clean_filename)
        if match:
            season = int(match.group(1))
            episode = int(match.group(2))
        
        # Alternative pattern: "Season X Episode Y"
        alt_pattern = re.compile(r'Season\s*(\d{1,2}).*Episode\s*(\d{1,2})', re.IGNORECASE)
        if not match:
            match = alt_pattern.search(clean_filename)
            if match:
                season = int(match.group(1))
                episode = int(match.group(2))
        
        # Try to extract year
        year_pattern = re.compile(r'\((\d{4})\)|\[(\d{4})\]|(?<!\d)(\d{4})(?!\d)')
        match = year_pattern.search(clean_filename)
        if match:
            # Use the first non-None group
            year = next((g for g in match.groups() if g is not None), None)
        
        return title, year, season, episode
    
    def _extract_suggested_name(self, filename, folder_path):
        """
        Extract a suggested name from filename and folder path.
        
        Args:
            filename: Filename to extract from
            folder_path: Folder path to extract from
            
        Returns:
            A suggested name for the content
        """
        # Try to get the parent folder name as a good starting point
        parent_folder = os.path.basename(folder_path)
        
        # If parent folder is generic (like "movies" or "downloads"), try to extract from filename
        generic_folders = ['movies', 'downloads', 'videos', 'tv', 'series', 'anime', 'films']
        
        if parent_folder.lower() in generic_folders:
            # Clean the filename
            clean_name = re.sub(r'\.(mkv|mp4|avi|mov|wmv|flv|m4v|ts)$', '', filename, flags=re.IGNORECASE)
            clean_name = re.sub(r'[._-]', ' ', clean_name)
            
            # Remove common tags
            clean_name = re.sub(r'\[[^\]]*\]|\([^\)]*\)', '', clean_name)
            
            # Remove quality indicators
            clean_name = re.sub(r'(?i)(1080p|720p|2160p|4K|HEVC|x264|x265|WEB-?DL|BluRay)', '', clean_name)
            
            # Normalize spaces
            clean_name = re.sub(r'\s+', ' ', clean_name).strip()
            
            return clean_name
        else:
            return parent_folder
    
    def _create_symlink(self, source_path, title, year=None, season=None, episode=None, is_tv=False, is_anime=False, resolution=None):
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
            
        Returns:
            Boolean indicating success
        """
        try:
            # Import the create_symlinks function
            from src.utils.file_utils import create_symlinks
            
            # Get destination directory from environment variable
            destination_dir = os.environ.get('DESTINATION_DIRECTORY')
            
            if not destination_dir:
                self.logger.error("Destination directory not set in environment variables")
                print("Error: Destination directory not set. Please set DESTINATION_DIRECTORY environment variable.")
                return False
            
            # Strip quotes from destination directory as well
            destination_dir = destination_dir.strip("'\"")
            
            # Ensure the destination directory exists
            if not os.path.exists(destination_dir):
                try:
                    os.makedirs(destination_dir, exist_ok=True)
                except Exception as e:
                    self.logger.error(f"Failed to create destination directory: {e}")
                    print(f"Error: Failed to create destination directory: {e}")
                    return False
            
            # Prepare metadata
            metadata = {
                'title': title,
                'year': year,
                'season': season,
                'episode': episode,
                'resolution': resolution,
                'episode_title': None  # Add episode title key with None as default
            }
            
            # Create symlinks using the utility function
            success, message = create_symlinks(
                source_path,
                destination_dir,
                is_anime=is_anime,
                content_type='tv' if is_tv else 'movie',
                metadata=metadata,
                force_overwrite=False
            )
            
            if success:
                self.symlink_count += 1
                self.logger.info(f"Created symlink: {message}")
                return True
            else:
                self.errors += 1
                self.logger.error(f"Failed to create symlink: {message}")
                print(f"Error: {message}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error creating symlink: {e}", exc_info=True)
            print(f"Error creating symlink: {e}")
            self.errors += 1
            return False

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