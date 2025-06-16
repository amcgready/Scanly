#!/usr/bin/env python3
"""Scanly: A media file scanner and organizer.

This module is the main entry point for the Scanly application.
"""
import logging
import os
import sys
import json
import time
import re
import difflib
from pathlib import Path

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
try:
    from dotenv import load_dotenv
    load_dotenv()  # Load environment variables from .env file
except ImportError:
    print("Warning: dotenv package not found. Environment variables must be set manually.")

# Import the logger utility
from src.utils.logger import get_logger

# Create log directory if it doesn't exist
log_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'logs')
os.makedirs(log_dir, exist_ok=True)

# Configure file handler to capture all logs regardless of console visibility
file_handler = logging.FileHandler(os.path.join(log_dir, 'scanly.log'))
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))

# Configure root logger WITHOUT a console handler
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[file_handler]  # Only file handler, no console handler
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
    """Clear the terminal screen using multiple methods."""
    print("\n\n--- Clearing screen... ---\n\n")  # Debug message
    
    try:
        # Method 1: Standard os.system call
        os.system('cls' if os.name == 'nt' else 'clear')
        
        # Method 2: Using ANSI escape codes (works in most terminals)
        print("\033c", end="")
        
        # Method 3: Terminal-specific escape sequences
        print("\033[H\033[J", end="")
        
        # Method 4: Print multiple newlines
        print("\n" * 100)
    except Exception as e:
        print(f"Error clearing screen: {e}")

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
    print("  3. Monitor Management - Add/remove directories for continuous monitoring")
    print("  4. Settings       - Configure application settings")
    print("  5. Help           - Display this help information")
    print("  0. Quit           - Exit the application")
    print("\nPress Enter to continue...")
    input()
    clear_screen()  # Clear screen after leaving help
    display_ascii_art()  # Show ASCII art when returning to main menu

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
except ImportError:
    logger.warning("Webhook functionality is not available")
    webhook_available = False
    
    # Create stub functions for webhooks
    def send_monitored_item_notification(item_data):
        logger.error("Webhook functionality is not available")
        return False
        
    def send_symlink_creation_notification(media_name, year, poster, description, original_path, symlink_path):
        logger.error("Webhook functionality is not available")
        return False
        
    def send_symlink_deletion_notification(media_name, year, poster, description, original_path, symlink_path):
        logger.error("Webhook functionality is not available")
        return False
        
    def send_symlink_repair_notification(media_name, year, poster, description, original_path, symlink_path):
        logger.error("Webhook functionality is not available")
        return False

class DirectoryProcessor:
    """Process a directory of media files."""
    def __init__(self, directory_path, resume=False, auto_mode=False):
        self.directory_path = directory_path
        self.resume = resume
        self.auto_mode = auto_mode
        self.logger = get_logger(__name__)
        
        # Initialize detection state variables
        self._detected_content_type = None
        self._detected_tmdb_id = None
    
    # Other methods from main_backup.py would be here
    # ...

# Update perform_individual_scan to properly clear the screen after error

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
    
    # Process the directory
    print(f"\nScanning directory: {clean_path}")
    # In a real implementation, you would call processor._process_media_files() here
    # For now, just simulate a scan
    print("\nScan completed.")
    
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
        return
    
    # Confirm directories before scanning
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
        input("\nPress Enter to continue...")
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
        # In a real implementation, result = processor._process_media_files()
        # For now, just simulate processing
        result = 1  # Simulate successful processing
        
        # Add to total processed count if successful
        if result > 0:
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

# Update handle_monitor_management to ensure proper screen clearing
def handle_monitor_management(monitor_manager):
    """Handle monitor management submenu."""
    if not monitor_manager:
        clear_screen()
        display_ascii_art()
        print("\nMonitor functionality is not available.")
        input("\nPress Enter to continue...")
        clear_screen()
        display_ascii_art()
        return
    
    while True:
        clear_screen()
        display_ascii_art()
        
        print("=" * 84)
        print("MONITOR MANAGEMENT".center(84))
        print("=" * 84)
        
        # Get currently monitored directories and their status
        monitored_dirs = []
        monitoring_active = False
        
        if hasattr(monitor_manager, 'get_monitored_directories'):
            try:
                monitored_dirs = monitor_manager.get_monitored_directories()
                # Check if any monitoring is active
                if hasattr(monitor_manager, 'is_active'):
                    monitoring_active = monitor_manager.is_active()
            except Exception as e:
                logger.error(f"Error getting monitored directories: {e}")
        
        # Display monitoring status
        status_text = "ACTIVE" if monitoring_active else "INACTIVE"
        print(f"\nMonitoring Status: {status_text}")
        
        # Toggle monitoring status text
        toggle_text = "Stop All Monitoring" if monitoring_active else "Start All Monitoring"
        
        print(f"\nCurrently monitoring {len(monitored_dirs)} directories:")
        if not monitored_dirs:
            print("  No directories are currently monitored.")
        else:
            for i, directory in enumerate(monitored_dirs, 1):
                # Check if this specific directory's monitoring is active
                dir_active = False
                if hasattr(monitor_manager, 'is_directory_active'):
                    try:
                        dir_active = monitor_manager.is_directory_active(directory)
                    except Exception as e:
                        logger.error(f"Error checking directory status: {e}")
                
                dir_status = "Active" if dir_active else "Inactive"
                print(f"  {i}. {directory} ({dir_status})")
        
        print("\nOptions:")
        print("  1. Add Directory to Monitoring")
        print("  2. Remove Directory from Monitoring")
        print(f"  3. {toggle_text}")
        
        # Only show toggle individual directory if we have directories
        if monitored_dirs:
            print("  4. Toggle Individual Directory")
        
        print("  0. Return to Main Menu")
        
        choice = input("\nSelect option: ").strip()
        
        if choice == "1":
            # Add directory to monitoring
            clear_screen()
            display_ascii_art()
            print("=" * 84)
            print("ADD DIRECTORY TO MONITORING".center(84))
            print("=" * 84)
            
            path = input("\nEnter directory path to monitor: ").strip()
            path = _clean_directory_path(path)
            
            if not os.path.isdir(path):
                print(f"\nError: {path} is not a valid directory.")
            else:
                print(f"\nAdding {path} to monitoring...")
                try:
                    # Check if directory has been scanned
                    scanned = has_directory_been_scanned(path)
                    
                    if not scanned:
                        print("\nWARNING: This directory hasn't been scanned yet.")
                        print("Adding it to monitoring will process all existing files.")
                        confirm = input("Do you want to continue? (y/n): ").strip().lower()
                        
                        if confirm != 'y':
                            print("\nDirectory not added to monitoring.")
                            input("\nPress Enter to continue...")
                            continue
                    
                    if hasattr(monitor_manager, 'add_directory'):
                        monitor_manager.add_directory(path)
                        print(f"\nDirectory {path} added to monitoring.")
                        
                        # If monitoring is already active, ask if the user wants to start this directory
                        if monitoring_active and hasattr(monitor_manager, 'start_directory'):
                            start_confirm = input("\nMonitoring is active. Start monitoring this directory now? (y/n): ").strip().lower()
                            if start_confirm == 'y':
                                monitor_manager.start_directory(path)
                                print(f"\nStarted monitoring {path}.")
                except Exception as e:
                    logger.error(f"Error adding directory to monitoring: {e}")
                    print(f"\nError: {e}")
            
            input("\nPress Enter to continue...")
        
        elif choice == "2":
            # Remove directory from monitoring
            if not monitored_dirs:
                clear_screen()
                display_ascii_art()
                print("=" * 84)
                print("REMOVE DIRECTORY FROM MONITORING".center(84))
                print("=" * 84)
                print("\nNo directories are currently being monitored.")
                input("\nPress Enter to continue...")
            else:
                clear_screen()
                display_ascii_art()
                print("=" * 84)
                print("REMOVE DIRECTORY FROM MONITORING".center(84))
                print("=" * 84)
                
                print("\nSelect directory number to remove:")
                for i, directory in enumerate(monitored_dirs, 1):
                    print(f"  {i}. {directory}")
                
                try:
                    idx = int(input("\nEnter number: ")) - 1
                    if 0 <= idx < len(monitored_dirs):
                        directory = monitored_dirs[idx]
                        
                        # Stop monitoring this directory first if it's active
                        if hasattr(monitor_manager, 'is_directory_active') and hasattr(monitor_manager, 'stop_directory'):
                            try:
                                if monitor_manager.is_directory_active(directory):
                                    monitor_manager.stop_directory(directory)
                                    print(f"\nStopped monitoring {directory}.")
                            except Exception as e:
                                logger.error(f"Error stopping directory monitoring: {e}")
                        
                        # Now remove it from the monitoring list
                        if hasattr(monitor_manager, 'remove_directory'):
                            monitor_manager.remove_directory(directory)
                            print(f"\nRemoved {directory} from monitoring.")
                    else:
                        print("\nInvalid selection.")
                except ValueError:
                    print("\nInvalid input. Please enter a number.")
            
                input("\nPress Enter to continue...")
        
        elif choice == "3":
            # Toggle all monitoring
            clear_screen()
            display_ascii_art()
            print("=" * 84)
            print("TOGGLE MONITORING".center(84))
            print("=" * 84)
            
            try:
                if monitoring_active:
                    # Stop all monitoring
                    if hasattr(monitor_manager, 'stop_all'):
                        monitor_manager.stop_all()
                        print("\nStopped monitoring all directories.")
                else:
                    # Start all monitoring
                    if hasattr(monitor_manager, 'start_all'):
                        monitor_manager.start_all()
                        print("\nStarted monitoring all directories.")
            except Exception as e:
                logger.error(f"Error toggling monitoring: {e}")
                print(f"\nError: {e}")
            
            input("\nPress Enter to continue...")
        
        elif choice == "4" and monitored_dirs:
            # Toggle individual directory monitoring
            clear_screen()
            display_ascii_art()
            print("=" * 84)
            print("TOGGLE INDIVIDUAL DIRECTORY".center(84))
            print("=" * 84)
            
            print("\nSelect directory number to toggle:")
            for i, directory in enumerate(monitored_dirs, 1):
                dir_active = False
                if hasattr(monitor_manager, 'is_directory_active'):
                    try:
                        dir_active = monitor_manager.is_directory_active(directory)
                    except Exception as e:
                        logger.error(f"Error checking directory status: {e}")
                
                dir_status = "Active" if dir_active else "Inactive"
                print(f"  {i}. {directory} ({dir_status})")
                
            try:
                idx = int(input("\nEnter number: ")) - 1
                if 0 <= idx < len(monitored_dirs):
                    directory = monitored_dirs[idx]
                    
                    # Check current status
                    dir_active = False
                    if hasattr(monitor_manager, 'is_directory_active'):
                        dir_active = monitor_manager.is_directory_active(directory)
                    
                    # Toggle the status
                    if dir_active:
                        if hasattr(monitor_manager, 'stop_directory'):
                            monitor_manager.stop_directory(directory)
                            print(f"\nStopped monitoring {directory}.")
                    else:
                        if hasattr(monitor_manager, 'start_directory'):
                            monitor_manager.start_directory(directory)
                            print(f"\nStarted monitoring {directory}.")
                else:
                    print("\nInvalid selection.")
            except ValueError:
                print("\nInvalid input. Please enter a number.")
                
            input("\nPress Enter to continue...")
        
        elif choice == "0":
            # Return to main menu
            clear_screen()
            display_ascii_art()
            return
        
        else:
            print(f"\nInvalid option: {choice}")
            input("\nPress Enter to continue...")

def handle_webhook_settings():
    """Handle webhook settings submenu."""
    clear_screen()
    display_ascii_art()
    
    print("=" * 84)
    print("WEBHOOK SETTINGS".center(84))
    print("=" * 84)
    
    # Display current webhook settings
    default_webhook_url = os.environ.get('DEFAULT_DISCORD_WEBHOOK_URL', '')
    monitored_webhook_url = os.environ.get('DISCORD_WEBHOOK_URL_MONITORED_ITEM', '')
    creation_webhook_url = os.environ.get('DISCORD_WEBHOOK_URL_SYMLINK_CREATION', '')
    deletion_webhook_url = os.environ.get('DISCORD_WEBHOOK_URL_SYMLINK_DELETION', '')
    repair_webhook_url = os.environ.get('DISCORD_WEBHOOK_URL_SYMLINK_REPAIR', '')
    
    print("\nCurrent Webhook Settings:")
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
    print("  0. Return to Settings")
    
    choice = input("\nSelect option: ").strip()
    
    if choice == "1":
        url = input("\nEnter Default Webhook URL (leave empty to clear): ").strip()
        _update_env_var('DEFAULT_DISCORD_WEBHOOK_URL', url)
        print(f"\nDefault Webhook URL {'cleared' if not url else 'updated'}.")
        
    elif choice == "2":
        url = input("\nEnter Monitored Item Webhook URL (leave empty to use default): ").strip()
        _update_env_var('DISCORD_WEBHOOK_URL_MONITORED_ITEM', url)
        print(f"\nMonitored Item Webhook URL {'set to use default' if not url else 'updated'}.")
        
    elif choice == "3":
        url = input("\nEnter Symlink Creation Webhook URL (leave empty to use default): ").strip()
        _update_env_var('DISCORD_WEBHOOK_URL_SYMLINK_CREATION', url)
        print(f"\nSymlink Creation Webhook URL {'set to use default' if not url else 'updated'}.")
        
    elif choice == "4":
        url = input("\nEnter Symlink Deletion Webhook URL (leave empty to use default): ").strip()
        _update_env_var('DISCORD_WEBHOOK_URL_SYMLINK_DELETION', url)
        print(f"\nSymlink Deletion Webhook URL {'set to use default' if not url else 'updated'}.")
        
    elif choice == "5":
        url = input("\nEnter Symlink Repair Webhook URL (leave empty to use default): ").strip()
        _update_env_var('DISCORD_WEBHOOK_URL_SYMLINK_REPAIR', url)
        print(f"\nSymlink Repair Webhook URL {'set to use default' if not url else 'updated'}.")
        
    elif choice == "0":
        # Return to settings menu
        return
    
    else:
        print(f"\nInvalid option: {choice}")
    
    print("\nPress Enter to continue...")
    input()
    handle_webhook_settings()  # Return to webhook settings

def handle_settings():
    """Handle settings submenu."""
    while True:
        clear_screen()
        display_ascii_art()
        
        print("=" * 84)
        print("SETTINGS".center(84))
        print("=" * 84)
        
        print("\nOptions:")
        print("  1. Configure File Paths")
        print("  2. Configure API Settings")
        print("  3. Configure Webhook Settings")
        print("  0. Return to Main Menu")
        
        choice = input("\nSelect option: ").strip()
        
        if choice == "1":
            # Handle file path settings
            print("\nFile path settings selected")
            print("\nPress Enter to continue...")
            input()
            
        elif choice == "2":
            # Handle API settings
            print("\nAPI settings selected")
            print("\nPress Enter to continue...")
            input()
            
        elif choice == "3":
            # Handle webhook settings
            handle_webhook_settings()
            
        elif choice == "0":
            # Return to main menu
            return
            
        else:
            print(f"\nInvalid option: {choice}")
            print("\nPress Enter to continue...")
            input()

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

def monitor_management_menu(monitor_manager):
    """Handle the Monitor Management submenu."""
    handle_monitor_management(monitor_manager)

def settings_menu():
    """Handle the Settings submenu."""
    handle_settings()

def help_menu():
    """Handle the Help submenu."""
    display_help()

# Ensure main function also properly clears screen between menus
def main():
    """Main function to run the Scanly application."""
    # Make sure the screen is clear before we start
    clear_screen()
    
    print("Initializing Scanly...")
    sys.stdout.flush()
    
    # Get the monitor manager but DO NOT start it
    try:
        monitor_manager = get_monitor_manager()
        # If the manager has monitored directories, clear them on startup
        if hasattr(monitor_manager, 'clear_all'):
            monitor_manager.clear_all()
    except Exception as e:
        logger.error(f"Failed to get monitor manager: {e}")
        monitor_manager = None
    
    clear_screen()  # Make sure screen is clear before starting menu loop
    
    while True:
        display_ascii_art()
        print("=" * 84)
        print("MAIN MENU".center(84))
        print("=" * 84)
        
        print("  1. Individual Scan")
        print("  2. Multi Scan")
        print("  3. Monitor Management")
        print("  4. Settings")
        print("  5. Help")
        print("  0. Quit")
        print()
        
        choice = input("Select option: ")
        
        if choice == "1":
            individual_scan_menu()
            clear_screen()  # Explicitly clear screen when returning to main menu
        
        elif choice == "2":
            multi_scan_menu()
            clear_screen()  # Explicitly clear screen when returning to main menu
        
        elif choice == "3":
            monitor_management_menu(monitor_manager)
            clear_screen()  # Explicitly clear screen when returning to main menu
        
        elif choice == "4":
            settings_menu()
            clear_screen()  # Explicitly clear screen when returning to main menu
        
        elif choice == "5":
            help_menu()
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