#!/usr/bin/env python3
"""Monitor menu for Scanly application."""
import os
import sys
import time
import logging
from pathlib import Path

# Ensure parent directory is in path for imports
parent_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

# Now this import should work with our added function
from src.config import get_settings
from src.core.monitor import get_monitor_manager

logger = logging.getLogger(__name__)

def clear_screen():
    """Clear the console screen."""
    os.system('cls' if os.name == 'nt' else 'clear')

def display_ascii_art():
    """Display ASCII art for the application."""
    print(r"""
 ░▒▓███████▓▒░░▒▓██████▓▒░ ░▒▓██████▓▒░░▒▓███████▓▒░░▒▓█▓▒░   ░▒▓█▓▒░░▒▓█▓▒░ 
░▒▓█▓▒░      ░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░   ░▒▓█▓▒░░▒▓█▓▒░ 
░▒▓█▓▒░      ░▒▓█▓▒░      ░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░   ░▒▓█▓▒░░▒▓█▓▒░ 
 ░▒▓██████▓▒░░▒▓█▓▒░      ░▒▓████████▓▒░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░    ░▒▓██████▓▒░  
       ░▒▓█▓▒░▒▓█▓▒░      ░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░      ░▒▓█▓▒░     
       ░▒▓█▓▒░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░      ░▒▓█▓▒░     
░▒▓███████▓▒░ ░▒▓██████▓▒░░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░░▒▓█▓▒░▒▓████████▓▒░▒▓█▓▒░     
                                                                             
                                    
    """)
    print("Welcome to Scanly Monitor")
    print("=======================")

def display_monitor_menu():
    """Display the monitor scan management menu."""
    monitor_manager = get_monitor_manager()
    
    while True:
        # Clear the screen
        clear_screen()
        display_ascii_art()
        print("\n===== Monitor Scan Management =====")
        
        # Get monitored directories
        monitored_dirs = monitor_manager.get_monitored_directories()
        
        if not monitored_dirs:
            print("\nNo directories currently being monitored.")
        else:
            print("\nCurrently monitored directories:")
            print(f"{'ID':<10} {'Name':<25} {'Status':<10} {'Pending':<10} {'Path'}")
            print("-" * 80)
            
            for dir_id, info in monitored_dirs.items():
                status = "ACTIVE" if info.get('active', False) else "INACTIVE"
                pending_count = len(info.get('pending_files', []))
                path = info.get('path', 'Unknown')
                name = info.get('name', os.path.basename(path))
                
                print(f"{dir_id:<10} {name[:25]:<25} {status:<10} {pending_count:<10} {path}")
        
        # Menu options
        print("\nOptions:")
        print("1. Add directory to monitor")
        print("2. Remove directory from monitoring")
        print("3. Toggle monitoring status (on/off)")
        print("4. View pending files")
        print("5. Back to main menu")
        
        choice = input("\nEnter your choice: ").strip()
        
        if choice == "1":
            # Add directory
            path = input("Enter directory path to monitor: ").strip()
            path = path.strip('"\'')  # Remove quotes if present
            
            if not path:
                print("No path entered.")
                input("Press Enter to continue...")
                continue
                
            if not os.path.isdir(path):
                print(f"Error: '{path}' is not a valid directory.")
                input("Press Enter to continue...")
                continue
            
            name = input("Enter a name for this directory (optional, press Enter to use folder name): ").strip()
            
            dir_id = monitor_manager.add_directory(path, name if name else None)
            if dir_id:
                print(f"Directory added successfully with ID: {dir_id}")
            else:
                print("Failed to add directory.")
            
            input("Press Enter to continue...")
            
        elif choice == "2":
            # Remove directory
            if not monitored_dirs:
                print("No directories to remove.")
                input("Press Enter to continue...")
                continue
                
            dir_id = input("Enter ID of directory to remove: ").strip()
            
            if dir_id in monitored_dirs:
                if monitor_manager.remove_directory(dir_id):
                    print(f"Directory with ID {dir_id} removed from monitoring.")
                else:
                    print(f"Failed to remove directory with ID {dir_id}.")
            else:
                print(f"Directory ID {dir_id} not found.")
                
            input("Press Enter to continue...")
            
        elif choice == "3":
            # Toggle monitoring status
            if not monitored_dirs:
                print("No directories to toggle.")
                input("Press Enter to continue...")
                continue
                
            dir_id = input("Enter ID of directory to toggle status: ").strip()
            
            if dir_id in monitored_dirs:
                is_active = monitor_manager.toggle_directory_active(dir_id)
                status = "active" if is_active else "inactive"
                print(f"Directory with ID {dir_id} is now {status}.")
            else:
                print(f"Directory ID {dir_id} not found.")
                
            input("Press Enter to continue...")
            
        elif choice == "4":
            # View pending files
            view_pending_files(monitor_manager)
            
        elif choice == "5":
            # Back to main menu
            break
            
        else:
            print("Invalid choice. Please try again.")
            input("Press Enter to continue...")


def view_pending_files(monitor_manager):
    """View pending files for all monitored directories."""
    # Clear the screen
    clear_screen()
    display_ascii_art()
    print("\n===== Pending Files =====")
    
    pending_files = monitor_manager.get_all_pending_files()
    
    if not pending_files:
        print("\nNo pending files to display.")
        input("\nPress Enter to continue...")
        return
    
    print(f"\nFound {len(pending_files)} pending files:")
    print(f"{'#':<5} {'Directory':<25} {'File'}")
    print("-" * 80)
    
    for i, file_info in enumerate(pending_files, 1):
        dir_name = file_info['dir_name']
        file_name = file_info['name']
        print(f"{i:<5} {dir_name[:25]:<25} {file_name}")
    
    print("\nOptions:")
    print("1. Process specific file")
    print("2. Process all files")
    print("3. Remove file from pending list")
    print("4. Back to monitor menu")
    
    choice = input("\nEnter your choice: ").strip()
    
    if choice == "1":
        # Process specific file
        idx = input("Enter file number to process: ").strip()
        try:
            idx = int(idx) - 1
            if 0 <= idx < len(pending_files):
                file_info = pending_files[idx]
                process_pending_file(monitor_manager, file_info)
            else:
                print("Invalid file number.")
        except ValueError:
            print("Please enter a valid number.")
        
        input("Press Enter to continue...")
        
    elif choice == "2":
        # Process all files
        confirm = input("Are you sure you want to process all pending files? (y/n): ").strip().lower()
        if confirm == "y":
            for file_info in pending_files:
                process_pending_file(monitor_manager, file_info)
        
        input("Press Enter to continue...")
        
    elif choice == "3":
        # Remove file from pending list
        idx = input("Enter file number to remove: ").strip()
        try:
            idx = int(idx) - 1
            if 0 <= idx < len(pending_files):
                file_info = pending_files[idx]
                dir_id = file_info['dir_id']
                file_path = file_info['path']
                
                if monitor_manager.remove_pending_file(dir_id, file_path):
                    print(f"File removed from pending list: {file_info['name']}")
                else:
                    print("Failed to remove file from pending list.")
            else:
                print("Invalid file number.")
        except ValueError:
            print("Please enter a valid number.")
        
        input("Press Enter to continue...")


def process_pending_file(monitor_manager, file_info):
    """Process a pending file by running an individual scan on it."""
    try:
        # Import DirectoryProcessor here to avoid circular imports
        from src.main import DirectoryProcessor
        
        dir_id = file_info['dir_id']
        file_path = file_info['path']
        
        # Check if the path still exists
        if not os.path.exists(file_path):
            print(f"Path no longer exists: {file_path}")
            # Remove from pending list
            monitor_manager.remove_pending_file(dir_id, file_path)
            return
        
        print(f"Processing: {file_path}")
        
        # Create a processor for this specific path
        processor = DirectoryProcessor(file_path)
        result = processor._process_media_files()
        
        # Remove from pending list if processed successfully
        if result is not None and result >= 0:
            monitor_manager.remove_pending_file(dir_id, file_path)
            print(f"Processed {result} files from {file_info['name']}")
        else:
            print(f"Failed to process {file_info['name']}")
            
    except ImportError:
        print("Error: Could not import DirectoryProcessor. Check your installation.")
    except Exception as e:
        print(f"Error processing file: {e}")
        logger.exception("Error processing pending file")