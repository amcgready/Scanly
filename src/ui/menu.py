"""
Main menu for Scanly application.
"""

import os
import sys
import traceback
from pathlib import Path

# Add the project root directory to the Python path
project_root = str(Path(__file__).parent.parent.parent)
if project_root not in sys.path:
    sys.path.append(project_root)

# Import utility functions first to avoid circular imports
from src.utils.logger import get_logger
from src.config import get_settings

class MainMenu:
    """Main menu class for Scanly application."""
    
    def __init__(self):
        """Initialize the main menu."""
        self.logger = get_logger(__name__)
        
        # Check if we're in debug mode based on LOG_LEVEL environment setting
        settings = get_settings()
        self.debug_mode = settings.get('LOG_LEVEL', '').upper() == 'DEBUG'
    
    def show(self):
        """Display the main menu and handle user input."""
        # Import here to avoid circular imports
        from src.main import (
            clear_screen, display_ascii_art, history_exists,
            DirectoryProcessor, load_scan_history, clear_scan_history,
            _clean_directory_path, review_skipped_items, test_anidb_connection,
            skipped_items_registry
        )
        
        while True:
            clear_screen()
            display_ascii_art()
            print("=" * 60)
            
            # Regular menu options always shown
            print("MAIN MENU\n")
            
            # Create a dynamic menu with proper numbering
            menu_options = []
            
            # Always show these options
            menu_options.append(("Directory Scan", self._directory_scan))
            menu_options.append(("Individual Scan", self._individual_scan))
            
            # Conditional menu options
            if history_exists():
                menu_options.append(("Resume Scan", self._resume_scan))
                menu_options.append(("Clear History", self._clear_history))
            
            # Only show Review Skipped if there are skipped items
            if skipped_items_registry:
                menu_options.append(("Review Skipped", review_skipped_items))
            
            # Always show quit and help
            menu_options.append(("Quit", self._quit))
            
            # Display numbered menu options
            for i, (label, _) in enumerate(menu_options, 1):
                if label != "Quit":  # Quit is always option 0
                    print(f"{i}. {label}")
            
            # Quit is always 0
            print("0. Quit")
            print("h. Help")
            
            # Debug menu options if enabled
            if self.debug_mode:
                print("\n--- DEBUG OPTIONS ---")
                print("d1. Test AniDB API Connection")
                print("d2. Test TMDB API Connection")
            
            print("\n" + "=" * 60)
            
            choice = input("\nSelect an option: ").strip().lower()
            
            # Handle numbered menu options dynamically
            if choice.isdigit():
                choice_num = int(choice)
                if choice_num == 0:
                    self._quit()
                elif 1 <= choice_num <= len(menu_options):
                    # Get the function for this menu option and call it
                    _, func = menu_options[choice_num - 1]
                    func()
                else:
                    print("\nInvalid option. Please try again.")
                    input("\nPress Enter to continue...")
            # Handle letter options
            elif choice == 'h':
                self._show_help(menu_options)
            elif self.debug_mode and choice == 'd1':
                test_anidb_connection()
            elif self.debug_mode and choice == 'd2':
                self._test_tmdb_connection()
            else:
                print("\nInvalid option. Please try again.")
                input("\nPress Enter to continue...")
    
    def _directory_scan(self):
        """Start a directory scan."""
        # Import here to avoid circular imports
        from src.main import clear_screen, display_ascii_art, DirectoryProcessor, _clean_directory_path
        
        clear_screen()
        display_ascii_art()
        print("=" * 60)
        print("DIRECTORY SCAN\n")
        
        print("Please enter the directory path to scan.")
        print("You can drag & drop a folder into the terminal window.\n")
        
        path = input("Directory path: ").strip()
        path = _clean_directory_path(path)
        
        if path and os.path.isdir(path):
            processor = DirectoryProcessor(path)
            processor.process()
        else:
            print("\nInvalid directory path.")
            input("\nPress Enter to continue...")
    
    def _individual_scan(self):
        """Start an individual scan."""
        # Import here to avoid circular imports
        from src.main import clear_screen, display_ascii_art, DirectoryProcessor, _clean_directory_path
        
        clear_screen()
        display_ascii_art()
        print("=" * 60)
        print("INDIVIDUAL SCAN\n")
        
        print("Please enter the file or folder path.")
        print("You can drag & drop into the terminal window.\n")
        
        path = input("Path: ").strip()
        path = _clean_directory_path(path)
        
        if path and (os.path.isdir(path) or os.path.isfile(path)):
            # For simplicity, handle both files and directories using DirectoryProcessor
            # If it's a file, its parent directory will be processed
            if os.path.isfile(path):
                path = os.path.dirname(path)
            
            processor = DirectoryProcessor(path)
            processor.process()
        else:
            print("\nInvalid path.")
            input("\nPress Enter to continue...")
    
    def _resume_scan(self):
        """Resume a previous scan."""
        # Import here to avoid circular imports
        from src.main import clear_screen, display_ascii_art, DirectoryProcessor, load_scan_history
        
        clear_screen()
        display_ascii_art()
        print("=" * 60)
        print("RESUME SCAN\n")
        
        history = load_scan_history()
        
        if not history:
            print("No valid scan history found.")
            input("\nPress Enter to continue...")
            return
        
        path = history.get('path', '')
        processed_files = history.get('processed_files', 0)
        total_files = history.get('total_files', 0)
        
        print(f"Found previous scan of: {path}")
        print(f"Progress: {processed_files}/{total_files} files processed")
        
        confirm = input("\nDo you want to resume this scan? (Y/n): ").strip().lower()
        if confirm == 'n':
            print("Resuming cancelled.")
            input("\nPress Enter to continue...")
            return
        
        if os.path.isdir(path):
            processor = DirectoryProcessor(path, resume=True)
            processor.process()
        else:
            print("\nDirectory no longer exists.")
            print("Cannot resume scan.")
            input("\nPress Enter to continue...")
    
    def _clear_history(self):
        """Clear scan history."""
        # Import here to avoid circular imports
        from src.main import clear_screen, display_ascii_art, clear_scan_history
        
        clear_screen()
        display_ascii_art()
        print("=" * 60)
        print("CLEAR HISTORY\n")
        
        confirm = input("Are you sure you want to clear scan history? (y/N): ").strip().lower()
        if confirm == 'y':
            if clear_scan_history():
                print("History cleared successfully.")
            else:
                print("No history file to clear.")
        else:
            print("Operation cancelled.")
        
        input("\nPress Enter to continue...")
    
    def _show_help(self, menu_options):
        """Show help information based on current menu options."""
        # Import here to avoid circular imports
        from src.main import clear_screen, display_ascii_art, history_exists, skipped_items_registry
        
        clear_screen()
        display_ascii_art()
        print("=" * 60)
        print("HELP\n")
        
        # Generate help for each menu option
        help_texts = {
            "Directory Scan": "Used to scan larger directories that contain multiple sub-folders and files\nBest for processing entire media libraries or disk drives",
            "Individual Scan": "Used to scan either a single folder or file that does not have\nadditional nested sub-folders\nBest for processing a single TV episode or movie file",
            "Resume Scan": "Continues processing from where a previous scan was interrupted",
            "Clear History": "Removes the saved progress from an interrupted scan",
            "Review Skipped": "Process items that were skipped during previous scans",
            "Quit": "Exit the application"
        }
        
        # Display help for each menu option in the current menu
        for i, (label, _) in enumerate(menu_options, 1):
            if label != "Quit":  # Quit is always option 0
                print(f"{i}. {label}")
                if label in help_texts:
                    print(f"   {help_texts[label]}")
                print()
        
        # Quit is always 0
        print("0. Quit")
        print(f"   {help_texts['Quit']}")
        print()
        
        print("h. Help")
        print("   Display this help information")
        
        if self.debug_mode:
            print("\n--- DEBUG OPTIONS ---")
            print("d1. Test AniDB API Connection")
            print("   Tests the connection to AniDB and verifies API access")
            
            print("\nd2. Test TMDB API Connection")
            print("   Tests the connection to TMDb and verifies API access")
        
        print("=" * 60)
        
        input("\nPress Enter to return to the main menu...")
    
    def _quit(self):
        """Quit the application."""
        # Import here to avoid circular imports
        from src.main import clear_screen
        
        clear_screen()
        print("\nExiting Scanly. Goodbye!")
        exit(0)
    
    def _test_tmdb_connection(self):
        """Test the TMDB API connection."""
        # Import here to avoid circular imports
        from src.main import clear_screen, display_ascii_art
        
        clear_screen()
        display_ascii_art()
        print("=" * 60)
        print("TMDB CONNECTION TEST\n")
        
        try:
            from src.api.tmdb import TMDB
            tmdb = TMDB()
            
            print("Testing TMDB API connection...")
            print("\nPerforming test search for 'Inception'...")
            
            # Test movie search
            movie_results = tmdb.search_movie("Inception")
            if movie_results:
                print(f"✓ Movie search successful! Found {len(movie_results)} results.")
                for i, result in enumerate(movie_results[:3], 1):
                    title = result.get('title', 'Unknown')
                    year = result.get('release_date', '')[:4] if result.get('release_date') else 'Unknown year'
                    print(f"{i}. {title} ({year})")
                
                # Test getting movie details
                if movie_results and 'id' in movie_results[0]:
                    movie_id = movie_results[0]['id']
                    print(f"\nFetching details for movie ID {movie_id}...")
                    details = tmdb.get_movie_details(movie_id)
                    if details:
                        print(f"✓ Successfully retrieved movie details for '{details.get('title')}'")
                        print(f"   Runtime: {details.get('runtime')} minutes")
                        print(f"   Genres: {', '.join([g['name'] for g in details.get('genres', [])])}")
                    else:
                        print("✗ Failed to retrieve movie details")
            else:
                print("✗ Movie search failed - no results returned")
            
            print("\nTesting TV show search for 'Breaking Bad'...")
            tv_results = tmdb.search_tv("Breaking Bad")
            if tv_results:
                print(f"✓ TV search successful! Found {len(tv_results)} results.")
                for i, result in enumerate(tv_results[:3], 1):
                    title = result.get('name', 'Unknown')
                    year = result.get('first_air_date', '')[:4] if result.get('first_air_date') else 'Unknown year'
                    print(f"{i}. {title} ({year})")
            else:
                print("✗ TV search failed - no results returned")
            
            print("\n✓ TMDB API connection tests completed successfully!")
        except Exception as e:
            print(f"\nError testing TMDB API: {e}")
            print(traceback.format_exc())
        
        input("\nPress Enter to continue...")

# Add this code to make the module executable
if __name__ == "__main__":
    try:
        menu = MainMenu()
        menu.show()
    except KeyboardInterrupt:
        from src.main import clear_screen
        clear_screen()
        print("\nExiting Scanly. Goodbye!")
    except Exception as e:
        print(f"\nAn error occurred: {e}")
        print("Check the log for more details.")
        traceback.print_exc()
