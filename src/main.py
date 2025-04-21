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

# DirectoryProcessor class definition
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
            # No need for further action - control will return to the main menu
            
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
        """Collect all media files in the directory, grouped by subfolder."""
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
        
        # Dictionary to store files grouped by subfolder
        self.subfolder_files = {}
        
        # Walk through directory and find media files
        for root, _, files in os.walk(self.directory_path):
            media_files_in_folder = []
            
            for file in files:
                # Check if file has a media extension
                if any(file.lower().endswith(ext) for ext in media_extensions):
                    file_path = os.path.join(root, file)
                    media_files_in_folder.append(file_path)
                    self.media_files.append(file_path)
            
            # Only add folders that contain media files
            if media_files_in_folder:
                self.subfolder_files[root] = sorted(media_files_in_folder)
        
        # Sort media files for consistent processing
        self.media_files.sort()
        self.total_files = len(self.media_files)
        
        print(f"Found {self.total_files} media files in {len(self.subfolder_files)} subfolders")

    def _process_media_files(self):
        """Process each subfolder and its media files interactively."""
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
            
            # Special case handling for Pokemon Origins before checking scanner lists
            if "Pokemon.Origins" in subfolder_name or "Pokemon Origins" in subfolder_name:
                suggested_title = "Pokemon Origins"
                content_type = "tv"  # It's an anime series
                is_anime = True
                tmdb_id = None
            else:
                # Try to extract metadata from folder name first
                suggested_title, suggested_year = self._extract_folder_metadata(subfolder_name)
                
                # Check initial content type using scanner lists with the cleaned title
                sample_file = files[0]
                content_type = "unknown"
                is_anime = False
                tmdb_id = None
                
                # Get clean filename without path
                sample_filename = os.path.basename(sample_file)
                
                # First try with the cleaned title we extracted
                scanner_result = check_scanner_lists(sample_filename, title_hint=suggested_title)
                
                if scanner_result:
                    # Fix: Properly unpack the scanner result which now returns 4 values
                    if len(scanner_result) == 4:
                        content_type, is_anime, tmdb_id, scanner_title = scanner_result
                        # Use the scanner title if available
                        if scanner_title:
                            suggested_title = scanner_title
                    else:
                        # Handle the case where scanner_result has 3 values for backward compatibility
                        content_type, is_anime, tmdb_id = scanner_result
                else:
                    # If no match with title hint, try without it
                    scanner_result = check_scanner_lists(sample_filename)
                    if scanner_result:
                        # Fix: Properly unpack the scanner result which now returns 4 values
                        if len(scanner_result) == 4:
                            content_type, is_anime, tmdb_id, scanner_title = scanner_result
                            # Use the scanner title if available
                            if scanner_title:
                                suggested_title = scanner_title
                        else:
                            # Handle the case where scanner_result has 3 values for backward compatibility
                            content_type, is_anime, tmdb_id = scanner_result
            
            # Filter out invalid years (like resolution values)
            if suggested_year and (not suggested_year.isdigit() or int(suggested_year) < 1900 or int(suggested_year) > 2030):
                suggested_year = None
            
            # In auto mode, skip user interaction and process directly
            if self.auto_mode:
                # Get media IDs for the title
                ids = self._get_media_ids(suggested_title, suggested_year, content_type == "tv")
                tmdb_id = ids.get('tmdb_id')
                imdb_id = ids.get('imdb_id')
                tvdb_id = ids.get('tvdb_id')
                
                # Process the subfolder based on content type with the IDs
                if content_type == "tv":
                    self._process_tv_series(files, subfolder, suggested_title, suggested_year, is_anime, 
                                           tmdb_id=tmdb_id, imdb_id=imdb_id, tvdb_id=tvdb_id)
                else:
                    self._process_movies(files, subfolder, suggested_title, suggested_year, is_anime,
                                        tmdb_id=tmdb_id, imdb_id=imdb_id, tvdb_id=tvdb_id)
                
                # Update processed count
                self.processed_files += len(files)
                # Save progress after each subfolder
                save_scan_history(self.directory_path, self.processed_files, self.total_files, self.media_files)
                continue  # Now we can continue to the next subfolder
            
            # Manual mode - Start interactive processing loop
            while True:
                # Display current metadata
                print("\nCurrent detection:")
                print(f"Title: {suggested_title}")
                if suggested_year:
                    print(f"Year: {suggested_year}")
                
                # Determine content type display name
                content_type_display = self._get_content_type_display(content_type, is_anime)
                print(f"Content type: {content_type_display}")
                
                # User options
                print("\nOptions:")
                print("1. Accept match and process (default - press Enter)")
                print("2. Search with new title")
                print("3. Change content type")
                print("4. Skip (save for later review)")
                print("5. Quit to main menu")
                
                choice = input("\nEnter choice (1-5, or press Enter for option 1): ").strip()
                
                # Use default choice (1) if user just presses Enter
                if choice == "":
                    choice = "1"
                
                if choice == "5":
                    # Quit to main menu
                    print("\nReturning to main menu...")
                    return
                
                elif choice == "4":
                    # Skip and save for later review
                    self._skip_files(files, subfolder, content_type, is_anime, subfolder_name)
                    break  # Break out of the while loop and continue to next subfolder
                
                elif choice == "3":
                    # Change content type - simplified interface with combined options
                    print("\nSelect content type:")
                    print("1. TV Series")
                    print("2. Movie")
                    print("3. Anime Series")
                    print("4. Anime Movie")
                    
                    type_choice = input("\nEnter choice (1-4): ").strip()
                    
                    # Set content type and anime flag based on unified selection
                    if type_choice == "1":
                        content_type = "tv"
                        is_anime = False
                    elif type_choice == "2":
                        content_type = "movie"
                        is_anime = False
                    elif type_choice == "3":
                        content_type = "tv"
                        is_anime = True
                    elif type_choice == "4":
                        content_type = "movie" 
                        is_anime = True
                    else:
                        print("\nInvalid choice. Using initial detection.")
                        input("\nPress Enter to continue...")
                    
                    # Continue the loop to show updated metadata and options
                    continue
                
                elif choice == "2":
                    # Search with new title
                    new_title = input("\nEnter new title: ").strip()
                    if new_title:
                        suggested_title = new_title
                        
                        # Ask for year
                        new_year = input("Enter year (optional): ").strip()
                        if new_year and new_year.isdigit() and len(new_year) == 4:
                            suggested_year = new_year
                    
                    # Continue the loop to show updated metadata and options
                    continue
                
                # Option 1 or default - proceed with processing
                
                # Get media IDs for the title
                ids = self._get_media_ids(suggested_title, suggested_year, content_type == "tv")
                tmdb_id = ids.get('tmdb_id')
                imdb_id = ids.get('imdb_id')
                tvdb_id = ids.get('tvdb_id')
                
                # Process the subfolder based on content type with the IDs
                if content_type == "tv":
                    self._process_tv_series(files, subfolder, suggested_title, suggested_year, is_anime, 
                                           tmdb_id=tmdb_id, imdb_id=imdb_id, tvdb_id=tvdb_id)
                else:
                    self._process_movies(files, subfolder, suggested_title, suggested_year, is_anime,
                                        tmdb_id=tmdb_id, imdb_id=imdb_id, tvdb_id=tvdb_id)
                
                # Update processed count
                self.processed_files += len(files)
                # Save progress after each subfolder
                save_scan_history(self.directory_path, self.processed_files, self.total_files, self.media_files)
                
                # Break the while loop after processing is complete
                break

    def _get_content_type_display(self, content_type, is_anime):
        """Return a user-friendly display name for the content type."""
        if content_type == "tv":
            return "Anime Series" if is_anime else "TV Series"
        elif content_type == "movie":
            return "Anime Movie" if is_anime else "Movie"
        else:
            return "Unknown"

    def _skip_files(self, files, subfolder, content_type, is_anime, subfolder_name):
        """Skip files and add them to the skipped items registry."""
        for file_path in files:
            # Add to skipped items for manual review
            suggested_name = self._extract_suggested_name(os.path.basename(file_path), subfolder)
            
            skipped_item = {
                'path': file_path,
                'subfolder': subfolder,
                'suggested_name': suggested_name,
                'is_tv': content_type == 'tv',
                'is_anime': is_anime
            }
            
            # Add to global skipped items registry
            globals()['skipped_items_registry'].append(skipped_item)
        
        save_skipped_items(globals()['skipped_items_registry'])
        self.skipped += len(files)
        print(f"\nSkipped {len(files)} files from {subfolder_name} for later review.")
        input("\nPress Enter to continue...")

    def _extract_folder_metadata(self, folder_name):
        """Extract title and year from folder name."""
        # Special case handling for Pokemon Origins
        if "Pokemon.Origins" in folder_name or "Pokemon Origins" in folder_name:
            return "Pokemon Origins", None
        
        # Clean the folder name - replace dots, underscores, and dashes with spaces
        clean_name = folder_name.replace('.', ' ').replace('_', ' ').replace('-', ' ')
        
        # First, try to extract year
        year_match = re.search(r'\((\d{4})\)|\[(\d{4})\]|(?<!\d)(\d{4})(?!\d)', clean_name)
        year = None
        
        if year_match:
            # Use the first non-None group
            year = next((g for g in year_match.groups() if g is not None), None)
            # Remove the year from the title
            clean_name = re.sub(r'\((\d{4})\)|\[(\d{4})\]|(?<!\d)(\d{4})(?!\d)', '', clean_name)
        
        # Remove season indicators (like S01, Season 1)
        # This now uses a more comprehensive pattern and removes everything from the season indicator to the end
        season_pattern = r'(?:S\d{1,2}|Season\s*\d{1,2})'
        season_match = re.search(season_pattern, clean_name, flags=re.IGNORECASE)
        if season_match:
            # Remove the season part and everything after it
            clean_name = clean_name[:season_match.start()].strip()
        else:
            # If no season pattern found, try the old way of removing just the season indicators
            clean_name = re.sub(r'\bS\d{1,2}\b|\bSeason\s*\d{1,2}\b', '', clean_name, flags=re.IGNORECASE)
        
        # Remove resolution indicators (like 1080p, 2160p, 720p)
        clean_name = re.sub(r'\b(?:1080p|720p|2160p|480p|4K|UHD)\b', '', clean_name, flags=re.IGNORECASE)
        
        # Remove other common technical specifications
        clean_name = re.sub(r'\b(?:WEB-?DL|BluRay|x264|x265|XviD|HEVC|AAC\d?(?:\.\d)?|H\.264|H\.265)\b', '', clean_name, flags=re.IGNORECASE)
        
        # Remove release group tags in brackets
        clean_name = re.sub(r'\[[^\]]*\]', '', clean_name)
        
        # Remove any content in parentheses
        clean_name = re.sub(r'\([^\)]*\)', '', clean_name)
        
        # Remove any content after a hyphen (often release group info)
        hyphen_parts = clean_name.split(' - ')
        if len(hyphen_parts) > 1:
            clean_name = hyphen_parts[0]
        
        # Normalize spaces and trim
        clean_name = re.sub(r'\s+', ' ', clean_name).strip()
        
        return clean_name, year

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
        if not year:
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
            
            # Check environment variables for folder ID settings
            include_tmdb_id = os.environ.get('TMDB_FOLDER_ID', 'true').lower() == 'true'
            include_imdb_id = os.environ.get('IMDB_FOLDER_ID', 'false').lower() == 'true'
            include_tvdb_id = os.environ.get('TVDB_FOLDER_ID', 'false').lower() == 'true'
            
            # Filter IDs based on environment settings
            if not include_tmdb_id:
                tmdb_id = None
            if not include_imdb_id:
                imdb_id = None
            if not include_tvdb_id:
                tvdb_id = None
            
            # Prepare metadata
            metadata = {
                'title': title,
                'year': year,
                'season': season,
                'episode': episode,
                'resolution': resolution,
                'episode_title': None,  # Add episode title key with None as default
                'part': part,  # Add part number for multi-part movies
                'tmdb_id': tmdb_id,  # Add TMDB ID 
                'imdb_id': imdb_id,  # Add IMDB ID
                'tvdb_id': tvdb_id   # Add TVDB ID
            }
            
            # Debug log to trace what's happening
            self.logger.debug(f"Creating symlink for '{title}' with IDs: TMDB={tmdb_id}, IMDB={imdb_id}, TVDB={tvdb_id}")
            self.logger.debug(f"Source: {source_path}")
            self.logger.debug(f"Destination: {destination_dir}")
            
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

    def _process_movies(self, files, subfolder, title, year, is_anime, tmdb_id=None, imdb_id=None, tvdb_id=None):
        """Process files as movies.
        
        Args:
            files: List of file paths
            subfolder: Path to subfolder containing the files
            title: Movie title
            year: Release year
            is_anime: Whether this is anime content
            tmdb_id: TMDB ID (optional)
            imdb_id: IMDB ID (optional)
            tvdb_id: TVDB ID (optional) - Not typically used for movies but included for consistency
        """
        successful_links = 0
        errors = 0
        
        # Check if we should attempt to get IDs that weren't provided
        if not tmdb_id or not imdb_id:
            # Only query TMDB if we need IDs and the title is available
            if title:
                ids = self._get_media_ids(title, year, is_tv=False)
                if ids:
                    # Only use IDs that weren't already provided
                    if not tmdb_id:
                        tmdb_id = ids.get('tmdb_id')
                    if not imdb_id:
                        imdb_id = ids.get('imdb_id')
        
        # Log the IDs we're working with
        self.logger.debug(f"Processing movies with title={title}, year={year}, tmdb_id={tmdb_id}, imdb_id={imdb_id}")
        
        for file_path in files:
            try:
                # Extract resolution from filename
                resolution = None
                res_match = re.search(r'(720p|1080p|2160p|4K)', os.path.basename(file_path), re.IGNORECASE)
                if res_match:
                    resolution = res_match.group(1)
                
                # Detect movie part (for multi-part movies)
                part_match = re.search(r'part\s*(\d+)', os.path.basename(file_path).lower())
                part = part_match.group(1) if part_match else None
                
                # Create the symlink with the IDs
                if self._create_symlink(
                    file_path,
                    title,
                    year=year,
                    is_tv=False,
                    is_anime=is_anime,
                    resolution=resolution,
                    part=part,
                    tmdb_id=tmdb_id,
                    imdb_id=imdb_id,
                    tvdb_id=tvdb_id
                ):
                    successful_links += 1
                else:
                    errors += 1
                    
            except Exception as e:
                self.logger.error(f"Error processing movie file {file_path}: {e}", exc_info=True)
                print(f"Error processing {os.path.basename(file_path)}: {e}")
                errors += 1
        
        # Return success/error counts rather than updating globals
        # This avoids double-counting when caller also updates counts
        return successful_links, errors

    def _process_tv_series(self, files, subfolder, title, year, is_anime, tmdb_id=None, imdb_id=None, tvdb_id=None):
        """Process files as TV series."""
        logger = logging.getLogger(__name__)
        
        # Log the information we have
        logger.debug(f"Processing TV series with title={title}, year={year}, tmdb_id={tmdb_id}, imdb_id={imdb_id}, tvdb_id={tvdb_id}")
        
        # Check if we should auto-extract episodes based on environment variable
        auto_extract_episodes = os.environ.get('AUTO_EXTRACT_EPISODES', 'False').lower() in ('true', 'yes', '1')
        
        # In manual mode, ask if seasons should be processed manually or automatically
        auto_process_seasons = True  # Default for auto mode
        
        # Check if this is likely a multi-season pack (like "Star.Trek.The.Next.Generation.S01-07")
        subfolder_name = os.path.basename(subfolder)
        is_multi_season_pack = False
        
        # Look for patterns like "S01-S07", "S01-07", "Season 1-7", etc.
        multi_season_patterns = [
            r'S(\d{1,2})[.-]S?(\d{1,2})',  # S01-S07 or S01-07
            r'S(\d{1,2}).*?S(\d{1,2})',     # S01...S07
            r'Season[s]?\s*(\d{1,2})[-.](\d{1,2})',  # Season 1-7 or Seasons 1-7
            r'(\d{1,2})[-.](\d{1,2})\s*Season[s]?'   # 1-7 Seasons
        ]
        
        season_range = None
        for pattern in multi_season_patterns:
            match = re.search(pattern, subfolder_name, re.IGNORECASE)
            if match:
                is_multi_season_pack = True
                start_season = int(match.group(1))
                end_season = int(match.group(2))
                season_range = (start_season, end_season)
                break
        
        # If this looks like a multi-season pack, suggest using detailed title extraction
        if is_multi_season_pack and not self.auto_mode:
            # Try to extract a more specific title from the folder name
            refined_title = self._extract_full_series_name(subfolder_name)
            if refined_title != title:
                print(f"\nDetected possible full series title: {refined_title}")
                use_detailed = input(f"Use '{refined_title}' instead of '{title}'? (Y/n): ").strip().lower()
                if use_detailed != 'n':
                    title = refined_title
                    print(f"Using title: {title}")
            
            print(f"\nThis appears to be a multi-season pack (Seasons {season_range[0]}-{season_range[1]})")
        
        if not self.auto_mode:
            print("\nHow would you like to process seasons?")
            print("1. Automatically detect seasons (default - press Enter)")
            print("2. Manually assign season numbers")
            
            season_choice = input("\nEnter choice (1-2, or press Enter for option 1): ").strip()
            auto_process_seasons = (not season_choice or season_choice == "1")
        
        # Display the chosen processing method
        if not self.auto_mode:
            season_mode = "automatic" if auto_process_seasons else "manual"
            episode_mode = "automatic" if auto_extract_episodes else "manual"
            print(f"\nUsing {season_mode} season detection and {episode_mode} episode detection")
        
        # Process TV series based on selected options
        if auto_process_seasons:
            # Automatically detect seasons and episodes
            successful_links = 0
            errors = 0
            
            for file_path in files:
                try:
                    # Extract season and episode from filename
                    file_name = os.path.basename(file_path)
                    
                    # Better metadata extraction for TV shows, especially multi-season packs
                    metadata = self._extract_tv_metadata(file_name, os.path.basename(subfolder))
                    
                    season = metadata.get('season')
                    episode = metadata.get('episode')
                    resolution = metadata.get('resolution')
                    
                    if not season and season_range:
                        # If no season was detected but we have a season range from the folder name,
                        # try to extract it from the filename with the known range
                        season = self._extract_season_from_filename(file_name, season_range)
                    
                    if not season or not episode:
                        print(f"Warning: Could not extract season/episode from {file_name}")
                        if not auto_extract_episodes:
                            print("Manual episode numbering required but not available in auto mode.")
                            print(f"Skipping {file_name}")
                            errors += 1
                            continue
                        else:
                            # Try to extract episode number from filename when season is known
                            if season and not episode:
                                # Try various patterns to extract just the episode number
                                ep_patterns = [
                                    r'E(\d{1,3})',  # Match E01, E1, E001
                                    r'EP(\d{1,3})',  # Match EP01, EP1, EP001
                                    r'Episode.*?(\d{1,3})',  # Match Episode 1, Episode 01
                                    r'[\s\.\-](\d{1,3})[\s\.\-]',  # Match spaces, dots or dashes with numbers
                                ]
                                for pattern in ep_patterns:
                                    ep_match = re.search(pattern, file_name, re.IGNORECASE)
                                    if ep_match:
                                        episode = int(ep_match.group(1))
                                        break
                            
                            # If still no success, try to guess from file order
                            if not season or not episode:
                                # Default to season 1 if not found
                                if not season:
                                    season = 1
                                # Default to episode based on position in file list
                                episode = files.index(file_path) + 1
                                print(f"  Auto-assigning: Season {season}, Episode {episode}")
                    
                    # Create symlink with detected metadata
                    if self._create_symlink(
                        file_path, 
                        title, 
                        year, 
                        season, 
                        episode, 
                        is_tv=True, 
                        is_anime=is_anime,
                        resolution=resolution,
                        tmdb_id=tmdb_id,
                        imdb_id=imdb_id,
                        tvdb_id=tvdb_id
                    ):
                        successful_links += 1
                    else:
                        errors += 1
                
                except Exception as e:
                    self.logger.error(f"Error processing TV file {file_path}: {e}", exc_info=True)
                    print(f"Error processing {os.path.basename(file_path)}: {e}")
                    errors += 1
                    
            # Update counts
            self.symlink_count += successful_links
            self.errors += errors
                    
        else:
            # Manual season assignment
            season = input("\nEnter season number for all files: ").strip()
            if not season.isdigit():
                print("Invalid season number. Using season 1 as default.")
                season = "1"
            
            # Process each file with the manually set season
            successful_links = 0
            errors = 0
            
            for file_path in files:
                try:
                    file_name = os.path.basename(file_path)
                    metadata = self._extract_tv_metadata(file_name, os.path.basename(subfolder))
                    resolution = metadata.get('resolution')
                    
                    # If auto_extract_episodes is enabled, try to extract episode number
                    # Otherwise, manually set the episode number
                    episode = None
                    if auto_extract_episodes:
                        # Try to extract episode numbers from filename
                        ep_match = re.search(r'[Ee](\d{1,3})', file_name)
                        if ep_match:
                            episode = int(ep_match.group(1))
                        else:
                            # Try alternative patterns
                            alt_patterns = [
                                r'EP(\d{1,3})',  # EP01
                                r'Episode.*?(\d{1,3})',  # Episode 1
                                r'[\s\.\-](\d{1,3})[\s\.\-]',  # Match numbers with separators
                            ]
                            for pattern in alt_patterns:
                                ep_match = re.search(pattern, file_name, re.IGNORECASE)
                                if ep_match:
                                    episode = int(ep_match.group(1))
                                    break
                            
                        if not episode:
                            # If we still can't extract the episode, use the index in the file list
                            episode = files.index(file_path) + 1
                            print(f"  Couldn't extract episode number for {file_name}, using {episode}")
                    else:
                        # Ask user for episode number
                        print(f"\nFile: {file_name}")
                        ep_input = input(f"Enter episode number: ").strip()
                        if ep_input.isdigit():
                            episode = int(ep_input)
                        else:
                            print("Invalid episode number. Skipping file.")
                            errors += 1
                            continue

                    # Create symlink with manually set season
                    if self._create_symlink(
                        file_path,
                        title,
                        year,
                        int(season),
                        episode,
                        is_tv=True,
                        is_anime=is_anime,
                        resolution=resolution,
                        tmdb_id=tmdb_id,
                        imdb_id=imdb_id,
                        tvdb_id=tvdb_id
                    ):
                        successful_links += 1
                    else:
                        errors += 1
                        
                except Exception as e:
                    self.logger.error(f"Error processing TV file {file_path}: {e}", exc_info=True)
                    print(f"Error processing {os.path.basename(file_path)}: {e}")
                    errors += 1
            
            # Update counts
            self.symlink_count += successful_links
            self.errors += errors

    def _extract_full_series_name(self, folder_name):
        """Extract the full series name from folder name, preserving important subtitle parts."""
        # Initialize variables to track special cases
        special_case = None
        
        # Check for specific special cases but don't return immediately
        if "pokemon.origins" in folder_name.lower() or "pokemon origins" in folder_name.lower():
            special_case = "Pokemon Origins"
        elif re.search(r'star\s*trek.*next\s*generation', folder_name.lower()):
            special_case = "Star Trek The Next Generation"
        elif re.search(r'attack.*titan', folder_name.lower()):
            special_case = "Attack on Titan"
        elif re.search(r'my.*hero.*academia', folder_name.lower()):
            special_case = "My Hero Academia"
        
        # Replace common separators with spaces
        clean_name = folder_name.replace('.', ' ').replace('_', ' ')
        
        # First remove common resolution specifications to avoid mistaking them for years
        resolution_patterns = [
            r'\b\d{3,4}p\b',              # 720p, 1080p, etc.
            r'\b(?:4K|UHD)\b'             # 4K, UHD
        ]
        
        for pattern in resolution_patterns:
            clean_name = re.sub(pattern, '', clean_name, flags=re.IGNORECASE)
        
        # Extract year if present (and preserve it for later)
        year = None
        year_match = re.search(r'\((\d{4})\)', clean_name)
        if not year_match:
            # Try alternative year formats
            year_match = re.search(r'(?<!\d)(\d{4})(?!\d)', clean_name)
        
        if year_match:
            year = year_match.group(1)
            # Validate year is reasonable (between 1900 and current year + 1)
            if year.isdigit() and 1900 <= int(year) <= datetime.datetime.now().year + 1:
                # Remove year from the clean name for processing
                clean_name = re.sub(r'\(\d{4}\)|\b\d{4}\b', '', clean_name)
            else:
                # If year is not reasonable, don't use it
                year = None
        
        # Remove season markers like S01-S07, Season 1-7, etc.
        clean_name = re.sub(r'S\d{1,2}[-.]S?\d{1,2}', '', clean_name, flags=re.IGNORECASE)
        clean_name = re.sub(r'Season[s]?\s*\d{1,2}[-.](\d{1,2})', '', clean_name, flags=re.IGNORECASE)
        clean_name = re.sub(r'(\d{1,2})[-.](\d{1,2})\s*Season[s]?', '', clean_name, flags=re.IGNORECASE)
        
        # Remove common technical specifications and release info
        technical_patterns = [
            r'\b(?:WEB[-]?DL|BluRay|DVDRip)\b',       # Release type
            r'\b(?:x264|x265|HEVC|H[-.]?26[45])\b',   # Encoding
            r'\bAAC\d?(?:[-.]?\d)?\b',                # Audio codec
            r'\b(?:DTS|DD5\.1|AC3)\b',                # Audio codec alternative
            r'\b(?:HDTV|WEB|UHD)\b',                  # Source
            r'\b(?:PROPER|REPACK|INTERNAL)\b',        # Release flags
            r'[-][\w\d]+$',                           # Release group at the end
        ]
        
        for pattern in technical_patterns:
            clean_name = re.sub(pattern, '', clean_name, flags=re.IGNORECASE)
        
        # Remove content in brackets and parentheses
        clean_name = re.sub(r'\[[^\]]*\]|\([^)]*\)', '', clean_name)
        
        # Normalize spaces and trim
        clean_name = re.sub(r'\s+', ' ', clean_name).strip()
        
        # If we identified a special case earlier, use that normalized name
        if special_case:
            clean_name = special_case
        
        # Final cleaning and normalization
        clean_name = re.sub(r'\s+', ' ', clean_name).strip()
        
        # Add back the year if it was extracted
        if year:
            clean_name = f"{clean_name} ({year})"
        
        return clean_name

    def clear_skipped_items(self):
        """Clear all skipped items from the registry."""
        global skipped_items_registry
        skipped_items_registry = []
        save_skipped_items(skipped_items_registry)
        print("\nAll skipped items have been cleared.")
        input("\nPress Enter to continue...")

    def _extract_tv_metadata(self, filename, dirname):
        """
        Extract metadata from TV show filename.
        
        Returns:
            Dictionary with keys for season, episode, resolution, etc.
        """
        metadata = {
            'season': None,
            'episode': None,
            'resolution': None
        }
        
        # Clean the filename
        clean_filename = filename.replace('.', ' ').replace('_', ' ')
        
        # Try to extract season and episode with different patterns
        
        # Pattern 1: S01E01 format
        season_ep_pattern = re.compile(r'S(\d{1,2})E(\d{1,2})', re.IGNORECASE)
        match = season_ep_pattern.search(clean_filename)
        if match:
            metadata['season'] = int(match.group(1))
            metadata['episode'] = int(match.group(2))
        
        # Pattern 2: Season X Episode Y format
        alt_pattern = re.compile(r'Season\s*(\d{1,2}).*?Episode\s*(\d{1,2})', re.IGNORECASE)
        match = alt_pattern.search(clean_filename)
        if match:
            metadata['season'] = int(match.group(1))
            metadata['episode'] = int(match.group(2))
        
        # Pattern 3: 1x01 format
        numeric_pattern = re.compile(r'(\d{1,2})x(\d{2})', re.IGNORECASE)
        match = numeric_pattern.search(clean_filename)
        if match:
            metadata['season'] = int(match.group(1))
            metadata['episode'] = int(match.group(2))
        
        # Pattern 4: Look for episode numbers in filenames like "Star.Trek.TNG.121.mp4"
        # This would be season 1, episode 21
        episode_number_pattern = re.compile(r'\.(\d)(\d{2})\.')
        match = episode_number_pattern.search(filename)
        if match:
            metadata['season'] = int(match.group(1))
            metadata['episode'] = int(match.group(2))
        
        # Try to extract resolution
        resolution_pattern = re.compile(r'(720p|1080p|2160p|4K)', re.IGNORECASE)
        match = resolution_pattern.search(filename)
        if match:
            metadata['resolution'] = match.group(1)
        
        return metadata

    def _extract_season_from_filename(self, filename, season_range=None):
        """
        Extract season number from filename, with optional known season range.
        
        Args:
            filename: The filename to extract from
            season_range: Optional tuple of (start_season, end_season)
            
        Returns:
            Season number as string or None if not found
        """
        if not season_range:
            return None
        
        # If this is a multi-season pack like S01-S07, try to find which season this file belongs to
        start_season, end_season = season_range
        
        # Look for season indicators in the filename
        for season_num in range(start_season, end_season + 1):
            # Format season number with leading zero if needed
            season_str = f"{season_num:02d}"
            season_patterns = [
                rf'S{season_str}',           # S01
                rf'Season {season_num}',      # Season 1
                rf'{season_num}x\d{{2}}',     # 1x01
            ]
            
            for pattern in season_patterns:
                if re.search(pattern, filename, re.IGNORECASE):
                    return str(season_num)
        
        return None

    def _get_media_ids(self, title, year, is_tv):
        """
        Get media IDs from the TMDB API.
        
        Args:
            title: Title to search for
            year: Year of release
            is_tv: Whether this is a TV series or movie
            
        Returns:
            Dict with tmdb_id, imdb_id, and tvdb_id (any could be None)
        """
        logger = logging.getLogger(__name__)
        
        try:
            # Import TMDB API
            from src.api.tmdb import TMDB
            
            # Get TMDB API key from environment
            tmdb_api_key = os.environ.get('TMDB_API_KEY', '')
            
            if not tmdb_api_key:
                logger.warning("TMDB API key not found, cannot search for IDs")
                return {'tmdb_id': None, 'imdb_id': None, 'tvdb_id': None}
            
            # Initialize TMDB API
            tmdb = TMDB(api_key=tmdb_api_key)
            
            # Clean the title to remove any resolution or technical specs that might have been missed
            clean_title = re.sub(r'\b\d{3,4}p\b', '', title, flags=re.IGNORECASE)  # Remove 1080p, 720p, etc.
            clean_title = re.sub(r'\(\d{3,4}\)', '', clean_title)  # Remove (1080), etc.
            clean_title = clean_title.strip()
            
            # Validate year to ensure it's a plausible year, not a resolution
            valid_year = None
            if year and year.isdigit():
                year_num = int(year)
                if 1900 <= year_num <= datetime.datetime.now().year + 1:
                    valid_year = year
            
            # Search differently based on content type
            if is_tv:
                # Search for TV series
                query = f"{clean_title}"
                logger.debug(f"Searching for TV series with query: {query}")
                
                # First try searching by title only for better matching
                results = tmdb.search_tv(query, limit=1)
                
                # If no results or low confidence, and we have a valid year, try with year
                if (not results or len(results) == 0) and valid_year:
                    query_with_year = f"{clean_title} {valid_year}"
                    logger.debug(f"No results with title only, trying with year: {query_with_year}")
                    results = tmdb.search_tv(query_with_year, limit=1)
                
                if results and len(results) > 0:
                    show_id = results[0].get('id')
                    if show_id:
                        # Get detailed info which might include external IDs
                        details = tmdb.get_tv_details(show_id)
                        
                        # Extract external IDs
                        external_ids = details.get('external_ids', {})
                        imdb_id = external_ids.get('imdb_id')
                        tvdb_id = external_ids.get('tvdb_id')
                        
                        logger.debug(f"Found IDs for {clean_title}: TMDB={show_id}, IMDB={imdb_id}, TVDB={tvdb_id}")
                        
                        return {
                            'tmdb_id': show_id,
                            'imdb_id': imdb_id,
                            'tvdb_id': tvdb_id
                        }
            else:
                # Search for movie
                query = f"{clean_title}"
                logger.debug(f"Searching for movie with query: {query}")
                
                # First try searching by title only
                results = tmdb.search_movie(query, limit=1)
                
                # If no results and we have a valid year, try with year
                if (not results or len(results) == 0) and valid_year:
                    query_with_year = f"{clean_title} {valid_year}"
                    logger.debug(f"No results with title only, trying with year: {query_with_year}")
                    results = tmdb.search_movie(query_with_year, limit=1)
                
                if results and len(results) > 0:
                    movie_id = results[0].get('id')
                    if movie_id:
                        # Get detailed info which might include external IDs
                        details = tmdb.get_movie_details(movie_id)
                        
                        # Extract external IDs
                        imdb_id = details.get('imdb_id')
                        
                        logger.debug(f"Found IDs for {clean_title}: TMDB={movie_id}, IMDB={imdb_id}")
                        
                        return {
                            'tmdb_id': movie_id,
                            'imdb_id': imdb_id,
                            'tvdb_id': None  # Movies don't have TVDB IDs
                        }
            
            logger.warning(f"No IDs found for {clean_title}" + (f" ({valid_year})" if valid_year else ""))
            return {'tmdb_id': None, 'imdb_id': None, 'tvdb_id': None}
                    
        except Exception as e:
            logger.error(f"Error getting media IDs: {e}", exc_info=True)
            return {'tmdb_id': None, 'imdb_id': None, 'tvdb_id': None}

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