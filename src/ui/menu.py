"""
Menu system for Scanly CLI.

This module provides menu classes for the command-line interface.
"""

import os
import sys
from typing import List, Dict, Any, Optional, Callable

from src.core.file_processor import MovieProcessor, TVProcessor, DirectoryProcessor
from src.utils.logger import get_logger

logger = get_logger(__name__)


class Menu:
    """Base class for menus."""
    
    def __init__(self, title: str = "Scanly Menu"):
        """
        Initialize a menu.
        
        Args:
            title: Title of the menu
        """
        self.title = title
        self.options = []
        self.should_exit = False
    
    def add_option(self, key: str, description: str, action: Callable) -> None:
        """
        Add an option to the menu.
        
        Args:
            key: Key to select this option
            description: Description of the option
            action: Function to call when option is selected
        """
        self.options.append({
            'key': key,
            'description': description,
            'action': action
        })
    
    def show(self) -> None:
        """Display the menu and process user input."""
        while not self.should_exit:
            print(f"\n{self.title}")
            print("=" * len(self.title))
            
            for option in self.options:
                print(f"{option['key']}: {option['description']}")
            
            choice = input("\nEnter your choice: ").strip().lower()
            
            # Find the matching option
            selected = next((o for o in self.options if o['key'] == choice), None)
            
            if selected:
                try:
                    selected['action']()
                except Exception as e:
                    logger.error(f"Error executing action: {e}", exc_info=True)
            else:
                print("Invalid option. Please try again.")
    
    def exit(self) -> None:
        """Exit the menu."""
        self.should_exit = True


class MainMenu(Menu):
    """Main menu for Scanly."""
    
    def __init__(self):
        """Initialize the main menu."""
        super().__init__("Scanly Main Menu")
        # Changed from letters to numbers for main menu options
        self.add_option("1", "Directory Scan", self.directory_scan)
        self.add_option("2", "TV Show Scan", self.tv_scan)
        self.add_option("3", "Movie Scan", self.movie_scan)
        self.add_option("0", "Quit", self.exit)
    
    def directory_scan(self) -> None:
        """Handle directory scan option."""
        DirectoryScanMenu().show()
    
    def tv_scan(self) -> None:
        """Handle TV show scan option."""
        TVScanMenu().show()
    
    def movie_scan(self) -> None:
        """Handle movie scan option."""
        MovieScanMenu().show()


class DirectoryScanMenu(Menu):
    """Menu for directory scanning."""
    
    def __init__(self):
        """Initialize the directory scan menu."""
        super().__init__("Directory Scan")
        
    def show(self) -> None:
        """Display the directory scan menu and process input."""
        directory = self._get_directory()
        if directory:
            self.process_directory(directory)
        else:
            print("Directory scan cancelled.")
    
    def _get_directory(self) -> Optional[str]:
        """
        Get a directory from the user.
        
        Returns:
            Directory path or None if cancelled
        """
        # Updated prompt message for drag-and-drop support
        directory = input("Enter or drag/drop directory to scan (or 'c' to cancel): ").strip()
        
        if directory.lower() == 'c':
            return None
        
        # Clean the directory path by removing quotes from drag and drop
        directory = self._clean_directory_path(directory)
        
        if not os.path.isdir(directory):
            print(f"Error: {directory} is not a valid directory.")
            return self._get_directory()
        
        return directory
    
    def _clean_directory_path(self, path: str) -> str:
        """
        Clean directory path by removing quotes that might be added during drag and drop.
        
        Args:
            path: Path to clean
            
        Returns:
            Cleaned path
        """
        if path:
            # Strip leading/trailing whitespace
            path = path.strip()
            # Remove surrounding quotes (both single and double)
            if (path.startswith('"') and path.endswith('"')) or (path.startswith("'") and path.endswith("'")):
                path = path[1:-1]
        return path
    
    def process_directory(self, directory: str) -> None:
        """
        Process a directory.
        
        Args:
            directory: Directory to process
        """
        print(f"Scanning directory: {directory}")
        
        # Ask if it's a TV show or movie directory
        content_type = input("Is this primarily a TV show or movie directory? (t/m/b for both): ").strip().lower()
        
        if content_type == 't':
            print("Processing as TV show directory...")
            processor = DirectoryProcessor(is_tv=True)
            processor.process_directory(directory)
        elif content_type == 'm':
            print("Processing as movie directory...")
            processor = DirectoryProcessor(is_tv=False)
            processor.process_directory(directory)
        elif content_type == 'b':
            print("Processing as mixed content directory...")
            # Process as both TV and movies
            tv_processor = DirectoryProcessor(is_tv=True)
            movie_processor = DirectoryProcessor(is_tv=False)
            
            # Process the directory twice with different processors
            tv_processor.process_directory(directory)
            movie_processor.process_directory(directory)
        else:
            print("Invalid option. Please try again.")
            self.process_directory(directory)


class TVScanMenu(Menu):
    """Menu for TV show scanning."""
    
    def __init__(self):
        """Initialize the TV scan menu."""
        super().__init__("TV Show Scan")
        
    def show(self) -> None:
        """Display the TV show scan menu and process input."""
        file_path = self._get_file_or_directory()
        if file_path:
            self.process_tv_item(file_path)
        else:
            print("TV scan cancelled.")
    
    def _get_file_or_directory(self) -> Optional[str]:
        """
        Get a file or directory from the user.
        
        Returns:
            File or directory path, or None if cancelled
        """
        path = input("Enter or drag/drop TV show file or directory (or 'c' to cancel): ").strip()
        
        if path.lower() == 'c':
            return None
        
        # Clean the path by removing quotes from drag and drop
        path = self._clean_directory_path(path)
        
        if not os.path.exists(path):
            print(f"Error: {path} does not exist.")
            return self._get_file_or_directory()
        
        return path
    
    def _clean_directory_path(self, path: str) -> str:
        """
        Clean path by removing quotes that might be added during drag and drop.
        
        Args:
            path: Path to clean
            
        Returns:
            Cleaned path
        """
        if path:
            # Strip leading/trailing whitespace
            path = path.strip()
            # Remove surrounding quotes (both single and double)
            if (path.startswith('"') and path.endswith('"')) or (path.startswith("'") and path.endswith("'")):
                path = path[1:-1]
        return path
    
    def process_tv_item(self, path: str) -> None:
        """
        Process a TV show file or directory.
        
        Args:
            path: Path to process
        """
        processor = TVProcessor()
        
        if os.path.isdir(path):
            print(f"Processing TV show directory: {path}")
            # For directories, we need to process each media file
            for root, _, files in os.walk(path):
                for file in files:
                    file_path = os.path.join(root, file)
                    if processor.is_media_file(file_path):
                        print(f"Processing file: {file_path}")
                        processor.process_file(file_path)
        else:
            print(f"Processing TV show file: {path}")
            processor.process_file(path)


class MovieScanMenu(Menu):
    """Menu for movie scanning."""
    
    def __init__(self):
        """Initialize the movie scan menu."""
        super().__init__("Movie Scan")
        
    def show(self) -> None:
        """Display the movie scan menu and process input."""
        file_path = self._get_file_or_directory()
        if file_path:
            self.process_movie_item(file_path)
        else:
            print("Movie scan cancelled.")
    
    def _get_file_or_directory(self) -> Optional[str]:
        """
        Get a file or directory from the user.
        
        Returns:
            File or directory path, or None if cancelled
        """
        path = input("Enter or drag/drop movie file or directory (or 'c' to cancel): ").strip()
        
        if path.lower() == 'c':
            return None
        
        # Clean the path by removing quotes from drag and drop
        path = self._clean_directory_path(path)
        
        if not os.path.exists(path):
            print(f"Error: {path} does not exist.")
            return self._get_file_or_directory()
        
        return path
    
    def _clean_directory_path(self, path: str) -> str:
        """
        Clean path by removing quotes that might be added during drag and drop.
        
        Args:
            path: Path to clean
            
        Returns:
            Cleaned path
        """
        if path:
            # Strip leading/trailing whitespace
            path = path.strip()
            # Remove surrounding quotes (both single and double)
            if (path.startswith('"') and path.endswith('"')) or (path.startswith("'") and path.endswith("'")):
                path = path[1:-1]
        return path
    
    def process_movie_item(self, path: str) -> None:
        """
        Process a movie file or directory.
        
        Args:
            path: Path to process
        """
        processor = MovieProcessor()
        
        if os.path.isdir(path):
            print(f"Processing movie directory: {path}")
            # For directories, we need to process each media file
            for root, _, files in os.walk(path):
                for file in files:
                    file_path = os.path.join(root, file)
                    if processor.is_media_file(file_path):
                        print(f"Processing file: {file_path}")
                        processor.process_file(file_path)
        else:
            print(f"Processing movie file: {path}")
            processor.process_file(path)