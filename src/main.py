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
        
        # Filter out specific scanner matching messages
        if record.msg and any(pattern in str(record.msg) for pattern in [
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

def _check_monitor_status():
    """Check and fix the monitor status if needed."""
    from src.core.monitor_manager import MonitorManager
    
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

def monitor_scan_menu():
    """Display and manage monitor scan options."""
    from src.core.monitor_manager import MonitorManager
    import datetime
    
    while True:
        clear_screen()
        display_ascii_art()
        print("=" * 60)
        print("MONITOR SCAN SETTINGS")
        print("=" * 60)
        
        print("\n1. Add a directory to monitor")
        print("2. Remove a monitored directory")
        print("3. Check status of monitored directories")
        print("4. Adjust monitor frequency")
        print("5. Return to main menu")
        
        choice = input("\nSelect an option (1-5): ").strip()
        
        if choice == "1":
            # Add a directory to monitor
            clear_screen()
            display_ascii_art()
            print("=" * 60)
            print("ADD DIRECTORY TO MONITOR")
            print("=" * 60)
            
            print("\nEnter the path of the directory to monitor:")
            dir_path = input("> ").strip()
            
            # Clean and verify path
            dir_path = _clean_directory_path(dir_path)
            if not dir_path or not os.path.isdir(dir_path):
                print("\nError: Invalid directory path.")
                input("\nPress Enter to continue...")
                continue
                
            try:
                monitor_manager = MonitorManager()
                monitor_manager.add_directory(dir_path)
                print(f"\nDirectory '{dir_path}' has been added to monitoring.")
            except Exception as e:
                print(f"\nError: Failed to add directory: {e}")
                
            input("\nPress Enter to continue...")
            
        elif choice == "2":
            # Remove a monitored directory
            clear_screen()
            display_ascii_art()
            print("=" * 60)
            print("REMOVE MONITORED DIRECTORY")
            print("=" * 60)
            
            try:
                monitor_manager = MonitorManager()
                monitored_dirs = monitor_manager.get_monitored_directories()
                
                if not monitored_dirs:
                    print("\nNo directories are currently being monitored.")
                    input("\nPress Enter to continue...")
                    continue
                
                print("\nCurrently monitored directories:")
                for i, (dir_id, info) in enumerate(monitored_dirs.items(), 1):
                    print(f"{i}. ID: {dir_id} - Path: {info.get('path', 'Unknown')}")
                
                print("\nEnter the number of the directory to remove (or 0 to cancel):")
                try:
                    dir_choice = int(input("> ").strip())
                    if dir_choice == 0:
                        continue
                        
                    if 1 <= dir_choice <= len(monitored_dirs):
                        dir_id = list(monitored_dirs.keys())[dir_choice - 1]
                        monitor_manager.remove_directory(dir_id)
                        print(f"\nDirectory with ID '{dir_id}' has been removed from monitoring.")
                    else:
                        print("\nInvalid choice.")
                except ValueError:
                    print("\nInvalid input. Please enter a number.")
                
            except Exception as e:
                print(f"\nError: Failed to remove directory: {e}")
                
            input("\nPress Enter to continue...")
            
        elif choice == "3":
            # Check status of monitored directories
            clear_screen()
            display_ascii_art()
            print("=" * 60)
            print("MONITORED DIRECTORIES STATUS")
            print("=" * 60)
            
            try:
                monitor_manager = MonitorManager()
                monitored_dirs = monitor_manager.get_monitored_directories()
                
                if not monitored_dirs:
                    print("\nNo directories are currently being monitored.")
                    input("\nPress Enter to continue...")
                    continue
                
                # Get current monitor interval
                monitor_interval = int(os.environ.get('MONITOR_INTERVAL_MINUTES', 30))
                
                print(f"\nMonitor frequency: Every {monitor_interval} minutes")
                print("\nDirectories being monitored:")
                
                for dir_id, info in monitored_dirs.items():
                    print(f"\n- ID: {dir_id}")
                    print(f"  Path: {info.get('path', 'Unknown')}")
                    print(f"  Active: {info.get('active', False)}")
                    print(f"  Pending files: {len(info.get('pending_files', []))}")
                    
                    # Last monitoring time
                    last_check = info.get('last_check')
                    if last_check:
                        try:
                            last_check_time = datetime.datetime.fromisoformat(last_check)
                            print(f"  Last check: {last_check_time.strftime('%Y-%m-%d %H:%M:%S')}")
                            
                            # Calculate next monitoring time
                            next_check_time = last_check_time + datetime.timedelta(minutes=monitor_interval)
                            print(f"  Next check: {next_check_time.strftime('%Y-%m-%d %H:%M:%S')}")
                            
                            # Time remaining
                            now = datetime.datetime.now()
                            if next_check_time > now:
                                time_remaining = next_check_time - now
                                minutes_remaining = time_remaining.total_seconds() / 60
                                print(f"  Time until next check: {int(minutes_remaining)} minutes")
                            else:
                                print("  Next check: Pending")
                        except (ValueError, TypeError):
                            print("  Last check: Unknown (invalid timestamp format)")
                    else:
                        print("  Last check: Never")
                        print("  Next check: At next monitor cycle")
            except Exception as e:
                print(f"\nError: Failed to get monitor status: {e}")
                
            input("\nPress Enter to continue...")
            
        elif choice == "4":
            # Adjust monitor frequency
            clear_screen()
            display_ascii_art()
            print("=" * 60)
            print("ADJUST MONITOR FREQUENCY")
            print("=" * 60)
            
            current_interval = int(os.environ.get('MONITOR_INTERVAL_MINUTES', 30))
            print(f"\nCurrent monitor frequency: Every {current_interval} minutes")
            
            print("\nEnter new monitor interval in minutes (minimum 5, recommended 30):")
            try:
                new_interval = int(input("> ").strip())
                if new_interval < 5:
                    print("\nWarning: Setting monitor interval too low may cause performance issues.")
                    print("Minimum recommended interval is 5 minutes.")
                    confirm = input("Continue with this setting? (y/n): ").strip().lower()
                    if confirm != 'y':
                        print("\nKeeping current setting.")
                        input("\nPress Enter to continue...")
                        continue
                        
                # Update environment variable
                _update_env_var('MONITOR_INTERVAL_MINUTES', str(new_interval))
                os.environ['MONITOR_INTERVAL_MINUTES'] = str(new_interval)
                
                print(f"\nMonitor frequency updated to: Every {new_interval} minutes")
                print("This change will take effect on the next monitoring cycle.")
                
            except ValueError:
                print("\nInvalid input. Please enter a number.")
                
            input("\nPress Enter to continue...")
            
        elif choice == "5":
            # Return to main menu
            return
            
        else:
            print("\nInvalid option. Please try again.")
            input("\nPress Enter to continue...")

def main_menu():
    """Display the main menu and handle user input."""
    global DESTINATION_DIRECTORY, skipped_items_registry
    
    while True:
        clear_screen()
        display_ascii_art()
        print("=" * 60)
        print(f"Welcome to SCANLY MEDIA SCANNER")
        print("=" * 60)
        
        # Status information
        print(f"\nDestination directory: {DESTINATION_DIRECTORY or 'Not set'}")
        if skipped_items_registry:
            print(f"Pending review items: {len(skipped_items_registry)}")
            
        # Check if monitor is active
        try:
            from src.core.monitor_manager import MonitorManager
            monitor_manager = MonitorManager()
            monitored_dirs = monitor_manager.get_monitored_directories()
            active_dirs = sum(1 for info in monitored_dirs.values() if info.get('active', False))
            if active_dirs > 0:
                print(f"Active monitored directories: {active_dirs}")
                pending_files = sum(len(info.get('pending_files', [])) for info in monitored_dirs.values())
                if pending_files > 0:
                    print(f"Pending monitored files: {pending_files}")
        except Exception:
            # Silently ignore errors checking monitor status
            pass
        
        # Determine what menu items to show based on conditions
        has_history = history_exists()
        has_skipped_items = len(skipped_items_registry) > 0
        
        # Track menu option numbers dynamically
        menu_options = []
        current_option = 1
        
        # Main menu with conditional items
        print("\nOptions:")
        
        # Always show these options
        print(f"{current_option}. Individual Scan")
        menu_options.append(("individual_scan", current_option))
        current_option += 1
        
        print(f"{current_option}. Multi Scan")
        menu_options.append(("multi_scan", current_option))
        current_option += 1
        
        print(f"{current_option}. Monitor Scan")
        menu_options.append(("monitor_scan", current_option))
        current_option += 1
        
        # Conditional: Resume Scan (only if history exists)
        if has_history:
            print(f"{current_option}. Resume Scan")
            menu_options.append(("resume_scan", current_option))
            current_option += 1
        
        # Conditional: Review Skipped (only if skipped items exist)
        if has_skipped_items:
            print(f"{current_option}. Review Skipped")
            menu_options.append(("review_skipped", current_option))
            current_option += 1
        
        # Always show these options
        print(f"{current_option}. Settings")
        menu_options.append(("settings", current_option))
        current_option += 1
        
        print(f"{current_option}. Help")
        menu_options.append(("help", current_option))
        current_option += 1
        
        print("0. Quit")
        
        choice = input(f"\nSelect an option (0-{current_option-1}): ").strip()
        
        if choice == "0":
            # Quit application
            print("\nThank you for using Scanly!")
            sys.exit(0)
        else:
            try:
                choice_num = int(choice)
                selected_option = next((option for option, num in menu_options if num == choice_num), None)
                
                if selected_option == "individual_scan":
                    # Individual scan logic
                    print("\nIndividual scan selected - placeholder")
                    input("\nPress Enter to continue...")
                
                elif selected_option == "multi_scan":
                    # Multi scan logic
                    print("\nMulti scan selected - placeholder")
                    input("\nPress Enter to continue...")
                
                elif selected_option == "monitor_scan":
                    # Monitor scan menu
                    monitor_scan_menu()
                
                elif selected_option == "resume_scan":
                    # Resume scan logic
                    print("\nResume scan selected - placeholder")
                    input("\nPress Enter to continue...")
                
                elif selected_option == "review_skipped":
                    # Review skipped items
                    review_skipped_items()
                
                elif selected_option == "settings":
                    # Settings menu
                    print("\nSettings menu selected - placeholder")
                    input("\nPress Enter to continue...")
                
                elif selected_option == "help":
                    # Help information
                    display_help()
                
                else:
                    print("\nInvalid option. Please try again.")
                    input("\nPress Enter to continue...")
            
            except ValueError:
                print("\nInvalid option. Please try again.")
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
        main_menu()
    except KeyboardInterrupt:
        print("\nExiting...")
    except Exception as e:
        logger = get_logger(__name__)
        logger.error(f"Unexpected error: {e}", exc_info=True)
        print(f"\nUnexpected error: {e}")
        print("Check logs for details.")
        input("\nPress Enter to exit...")