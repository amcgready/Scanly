"""
Command-line interface for Scanly.

This module provides the command-line interface for interacting with Scanly.
"""

import os
import sys
import argparse
from typing import List, Optional

from src.core.file_processor import MovieProcessor, TVProcessor
from src.utils.logger import get_logger

logger = get_logger(__name__)


class CLI:
    """
    Command-line interface for Scanly.
    """
    
    def __init__(self):
        """Initialize the CLI."""
        self.parser = self._create_parser()
    
    def _create_parser(self) -> argparse.ArgumentParser:
        """
        Create the argument parser.
        
        Returns:
            Configured argument parser
        """
        parser = argparse.ArgumentParser(
            description="Scanly - Media File Organizer",
            epilog="Organize your media files with symlinks."
        )
        
        # Add arguments
        parser.add_argument(
            "path", 
            nargs="?", 
            help="Path to file or directory to process (optional)"
        )
        
        parser.add_argument(
            "--movie", "-m",
            action="store_true",
            help="Process as movie"
        )
        
        parser.add_argument(
            "--tv", "-t",
            action="store_true",
            help="Process as TV show"
        )
        
        parser.add_argument(
            "--scan-dir", "-s",
            action="store_true",
            help="Perform a directory scan"
        )
        
        parser.add_argument(
            "--gui", "-g",
            action="store_true",
            help="Launch the GUI (if available)"
        )
        
        parser.add_argument(
            "--version", "-v",
            action="store_true",
            help="Show version information"
        )
        
        return parser
    
    def parse_args(self, args: Optional[List[str]] = None) -> argparse.Namespace:
        """
        Parse command-line arguments.
        
        Args:
            args: Command-line arguments to parse (defaults to sys.argv)
            
        Returns:
            Parsed arguments
        """
        return self.parser.parse_args(args)
    
    def process_args(self, args: argparse.Namespace):
        """
        Process the parsed arguments.
        
        Args:
            args: Parsed arguments
        """
        # Show version if requested
        if args.version:
            self._show_version()
            return
        
        # Launch GUI if requested
        if args.gui:
            self._launch_gui()
            return
        
        # If a path is provided, process it
        if args.path:
            if args.movie:
                self._process_movie(args.path)
            elif args.tv:
                self._process_tv(args.path)
            elif args.scan_dir:
                self._process_directory(args.path)
            else:
                # Try to guess the media type
                self._guess_and_process(args.path)
        else:
            # No path provided, show menu
            from .menu import MainMenu
            MainMenu().show()
    
    def _show_version(self):
        """Show version information."""
        print("Scanly v0.1.0")
        print("Media File Organizer")
        print("Copyright (c) 2025")
    
    def _launch_gui(self):
        """Launch the GUI if available."""
        try:
            from src.ui.gui import launch_gui
            launch_gui()
        except ImportError:
            print("GUI not available. Using command-line interface.")
            from .menu import MainMenu
            MainMenu().show()
    
    def _process_movie(self, path: str):
        """
        Process a path as a movie.
        
        Args:
            path: Path to process
        """
        processor = MovieProcessor()
        
        if os.path.isdir(path):
            print(f"Processing directory as movie: {path}")
            processor.process_directory(path)
        else:
            print(f"Processing file as movie: {path}")
            processor.process_file(path)
    
    def _process_tv(self, path: str):
        """
        Process a path as a TV show.
        
        Args:
            path: Path to process
        """
        processor = TVProcessor()
        
        if os.path.isdir(path):
            print(f"Processing directory as TV show: {path}")
            processor.process_directory(path)
        else:
            print(f"Processing file as TV episode: {path}")
            processor.process_file(path)
    
    def _process_directory(self, path: str):
        """
        Process a directory scan.
        
        Args:
            path: Path to the directory to scan
        """
        if not os.path.isdir(path):
            print(f"Error: {path} is not a directory.")
            return
        
        from .menu import DirectoryScanMenu
        DirectoryScanMenu().process_directory(path)
    
    def _guess_and_process(self, path: str):
        """
        Try to guess the media type and process accordingly.
        
        Args:
            path: Path to process
        """
        # Check if the path exists
        if not os.path.exists(path):
            print(f"Error: Path does not exist: {path}")
            return
        
        # Try to guess based on directory/file name
        name_lower = os.path.basename(path).lower()
        
        # Check for TV show indicators
        tv_indicators = ['tv', 'show', 'series', 'season', 'episode', 's01', 's02', 'complete']
        
        # Check for movie indicators
        movie_indicators = ['movie', 'film', '1080p', '720p', 'bluray', 'brrip', 'dvdrip']
        
        # Count matches
        tv_matches = sum(1 for indicator in tv_indicators if indicator in name_lower)
        movie_matches = sum(1 for indicator in movie_indicators if indicator in name_lower)
        
        # Process based on best guess
        if tv_matches > movie_matches:
            print(f"Guessing as TV show: {path}")
            self._process_tv(path)
        elif movie_matches > tv_matches:
            print(f"Guessing as movie: {path}")
            self._process_movie(path)
        else:
            # If we can't guess, ask the user
            from .menu import GuessTypeMenu
            GuessTypeMenu().process_path(path)


def main():
    """Main entry point for the CLI."""
    try:
        cli = CLI()
        args = cli.parse_args()
        cli.process_args(args)
    except KeyboardInterrupt:
        print("\nOperation cancelled by user.")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        logger.exception("Unhandled exception")
        sys.exit(1)


if __name__ == "__main__":
    main()