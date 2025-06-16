#!/usr/bin/env python3
"""Scanly: A media file scanner and organizer.

This module is the main entry point for the Scanly application.
"""
import logging
import os
import sys
import json
from pathlib import Path

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

# Import the logger utility
from src.utils.logger import get_logger

# Define a strict filter to exclude monitor log messages from the console
class ConsoleFilter(logging.Filter):
    def filter(self, record):
        # Keep print statements (critical level) visible, but filter out INFO, DEBUG, etc.
        # Additionally, filter out any logs from monitor modules
        if record.levelno >= logging.CRITICAL:
            return True
        if 'monitor' in record.name.lower():
            return False
        # Filter out other logs below CRITICAL level
        return False

# Create log directory if it doesn't exist
log_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'logs')
os.makedirs(log_dir, exist_ok=True)

# Configure console handler with filter to block monitor logs
console_handler = logging.StreamHandler()
console_handler.addFilter(ConsoleFilter())
console_handler.setLevel(logging.INFO)  # Process all logs, but filter will block most

# Configure file handler to capture all logs
file_handler = logging.FileHandler(os.path.join(log_dir, 'scanly.log'))
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))

# Configure root logger
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[console_handler, file_handler]
)

# Set lower log levels for noisy libraries
logging.getLogger('urllib3').setLevel(logging.WARNING)
logging.getLogger('requests').setLevel(logging.WARNING)

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
            print("SCANLY")  # Fallback if art file doesn't exist
    except Exception as e:
        print("SCANLY")  # Fallback if art file can't be loaded

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
    print("  3. Resume Scan    - Resume a previously interrupted scan")
    print("  4. Settings       - Configure application settings")
    print("  0. Quit           - Exit the application")
    print("\nPress Enter to continue...")
    input()
    clear_screen()  # Clear screen after leaving help
    display_ascii_art()  # Show ASCII art when returning to main menu

# Import the monitor manager
try:
    from src.core.monitor import get_monitor_manager
except ImportError:
    logger.warning("Monitor module not available")
    # Create a dummy get_monitor_manager function
    def get_monitor_manager():
        logger.error("Monitor functionality is not available")
        return None

# Add this function to initialize monitoring on startup
def initialize_monitoring():
    """Initialize directory monitoring on application startup."""
    try:
        monitor_manager = get_monitor_manager()
        if monitor_manager:
            monitor_manager.start_all()
            logger.info("Directory monitoring initialized")
    except Exception as e:
        logger.error(f"Failed to initialize directory monitoring: {e}")

def main():
    """Main function to run the Scanly application."""
    # Initialize monitoring on startup
    try:
        initialize_monitoring()
    except Exception as e:
        logger.error(f"Failed to initialize monitoring: {e}")
    
    clear_screen()
    display_ascii_art()
    
    while True:
        print("=" * 84)
        print("MAIN MENU".center(84))
        print("=" * 84)
        
        # Always available options
        menu_options = {
            "1": ("Individual Scan", None),
            "2": ("Multi Scan", None),
        }
        
        # Conditionally available options
        next_option = 3
        
        # Resume scan - only if scan history exists
        if has_scan_history():
            menu_options[str(next_option)] = ("Resume Scan", None)
            next_option += 1
        
        # Review skipped items - only if skipped items exist
        if has_skipped_items():
            menu_options[str(next_option)] = ("Review Skipped Items", None)
            next_option += 1
        
        # Monitor Scan option - always available
        menu_options[str(next_option)] = ("Monitor Scan", None)
        next_option += 1
        
        # Review Monitored option - only if there are pending files
        try:
            monitor_manager = get_monitor_manager()
            if monitor_manager and monitor_manager.has_pending_files():
                menu_options[str(next_option)] = (f"Review Monitored ({monitor_manager.pending_count()})", None)
                next_option += 1
        except Exception as e:
            logger.error(f"Error checking monitor status: {e}")
        
        # Clear history - only if scan history or skipped items exist
        if has_scan_history() or has_skipped_items():
            menu_options[str(next_option)] = ("Clear History", None)
            next_option += 1
        
        # Standard options
        menu_options[str(next_option)] = ("Settings", None)
        next_option += 1
        
        menu_options[str(next_option)] = ("Help", None)
        next_option += 1
        
        menu_options["0"] = ("Quit", None)
        
        # Display menu options
        for key, (option_text, _) in menu_options.items():
            print(f"  {key}. {option_text}")
        
        choice = input("\nSelect option: ").strip()
        
        # Process the selected option
        if choice == "1":
            print("Individual scan selected")
            input("\nPress Enter to continue...")
        
        elif choice == "2":
            perform_multi_scan()
        
        elif choice in menu_options and menu_options[choice][0] == "Resume Scan":
            print("Resume scan selected")
            input("\nPress Enter to continue...")
        
        elif choice in menu_options and menu_options[choice][0] == "Review Skipped Items":
            review_skipped_items()
            
        elif choice in menu_options and menu_options[choice][0] == "Monitor Scan":
            print("Monitor scan selected")
            input("\nPress Enter to continue...")
            
        elif choice in menu_options and "Review Monitored" in menu_options[choice][0]:
            print("Review monitored selected")
            input("\nPress Enter to continue...")
            
        elif choice in menu_options and menu_options[choice][0] == "Clear History":
            clear_all_history()
        
        elif choice in menu_options and menu_options[choice][0] == "Settings":
            print("Settings selected")
            input("\nPress Enter to continue...")
        
        elif choice in menu_options and menu_options[choice][0] == "Help":
            display_help()
        
        elif choice == "0":
            print("Exiting Scanly. Goodbye!")
            break
            
        else:
            print(f"\nInvalid option: {choice}")
            input("\nPress Enter to continue...")
            clear_screen()
            display_ascii_art()

if __name__ == "__main__":
    main()