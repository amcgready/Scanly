"""
Processes media files for organization.

This module provides base and specialized classes for processing
different types of media files.
"""

import os
from typing import Optional, List, Dict, Any

from src.api.tmdb import TMDB
from src.core.symlink_creator import SymlinkCreator
from src.utils.logger import get_logger
from src.config import DESTINATION_DIRECTORY, ALLOWED_EXTENSIONS

logger = get_logger(__name__)


class FileProcessor:
    """
    Base class for file processors.
    """
    
    def __init__(self):
        """Initialize the file processor."""
        self.tmdb = TMDB()
        self.symlink_creator = SymlinkCreator()
        
    def is_media_file(self, file_path: str) -> bool:
        """
        Check if a file is a media file based on its extension.
        
        Args:
            file_path: Path to the file
            
        Returns:
            True if the file is a media file, False otherwise
        """
        extension = os.path.splitext(file_path)[1].lower()
        return extension in ALLOWED_EXTENSIONS
    
    def process_file(self, file_path: str) -> bool:
        """
        Process a file (to be implemented by subclasses).
        
        Args:
            file_path: Path to the file to process
            
        Returns:
            True if processing was successful, False otherwise
        """
        raise NotImplementedError("Subclasses must implement process_file method")


class MovieProcessor(FileProcessor):
    """
    Processes movie files.
    """
    
    def __init__(self):
        """Initialize the movie processor."""
        super().__init__()
    
    def extract_movie_name(self, file_path: str) -> str:
        """
        Extract a movie name from a file path.
        
        Args:
            file_path: Path to the movie file
            
        Returns:
            Extracted movie name
        """
        # Simple extraction for now - can be enhanced
        basename = os.path.basename(file_path)
        name = os.path.splitext(basename)[0]
        
        # Remove common patterns
        patterns = [
            r'\(\d{4}\)',  # Remove year in parentheses
            r'\[\w+\]',    # Remove anything in square brackets
            r'\d{3,4}p',   # Remove resolution
            r'HDTV',       # Remove HDTV
            r'BluRay',     # Remove BluRay
            r'WEB-DL',     # Remove WEB-DL
            r'x264',       # Remove codec info
            r'HEVC',       # Remove codec info
        ]
        
        import re
        for pattern in patterns:
            name = re.sub(pattern, '', name, flags=re.IGNORECASE)
        
        # Clean up the result
        name = name.replace('.', ' ').replace('_', ' ')
        name = ' '.join(name.split())  # Normalize whitespace
        
        return name
    
    def search_movie(self, movie_name: str) -> List[Dict[str, Any]]:
        """
        Search for a movie on TMDB.
        
        Args:
            movie_name: Name of the movie to search for
            
        Returns:
            List of movie results
        """
        return self.tmdb.search_movie(movie_name)
    
    def process_file(self, file_path: str) -> bool:
        """
        Process a movie file.
        
        Args:
            file_path: Path to the movie file
            
        Returns:
            True if processing was successful, False otherwise
        """
        if not self.is_media_file(file_path):
            logger.info(f"Skipping non-media file: {file_path}")
            return False
        
        movie_name = self.extract_movie_name(file_path)
        
        # Search for the movie
        results = self.search_movie(movie_name)
        
        if not results:
            logger.warning(f"No results found for movie: {movie_name}")
            return False
        
        # For now, just use the first result
        movie = results[0]
        
        # Create symlink
        return self.symlink_creator.create_movie_symlink(
            movie_file=file_path,
            movie_name=movie['title'],
            tmdb_id=str(movie['id']),
            year=movie.get('release_date', '')[:4] if movie.get('release_date') else None
        )


class TVProcessor(FileProcessor):
    """
    Processes TV show files.
    """
    
    def __init__(self):
        """Initialize the TV processor."""
        super().__init__()
    
    def extract_show_info(self, file_path: str) -> Dict[str, Any]:
        """
        Extract show name, season, and episode from a file path.
        
        Args:
            file_path: Path to the episode file
            
        Returns:
            Dictionary containing show_name, season, and episode
        """
        # Simple extraction - can be enhanced
        basename = os.path.basename(file_path)
        
        # Try to extract season and episode using common patterns
        import re
        
        # Pattern like S01E01 or s01e01
        se_match = re.search(r'[Ss](\d{1,2})[Ee](\d{1,2})', basename)
        if se_match:
            season = se_match.group(1).lstrip('0') or '1'  # Default to season 1 if '00'
            episode = se_match.group(2).lstrip('0') or '1'  # Default to episode 1 if '00'
            
            # Extract show name (everything before the pattern)
            show_part = basename[:se_match.start()]
            show_name = show_part.replace('.', ' ').replace('_', ' ').strip()
            
            return {
                'show_name': show_name,
                'season': season,
                'episode': episode
            }
        
        # Pattern like 1x01 or 01x01
        se_match = re.search(r'(\d{1,2})x(\d{1,2})', basename)
        if se_match:
            season = se_match.group(1).lstrip('0') or '1'
            episode = se_match.group(2).lstrip('0') or '1'
            
            # Extract show name
            show_part = basename[:se_match.start()]
            show_name = show_part.replace('.', ' ').replace('_', ' ').strip()
            
            return {
                'show_name': show_name,
                'season': season,
                'episode': episode
            }
        
        # Fallback - assume season 1, episode 1
        name = os.path.splitext(basename)[0]
        name = name.replace('.', ' ').replace('_', ' ')
        name = ' '.join(name.split())  # Normalize whitespace
        
        return {
            'show_name': name,
            'season': '1',
            'episode': '1'
        }
    
    def search_show(self, show_name: str) -> List[Dict[str, Any]]:
        """
        Search for a TV show on TMDB.
        
        Args:
            show_name: Name of the show to search for
            
        Returns:
            List of show results
        """
        return self.tmdb.search_tv(show_name)
    
    def process_file(self, file_path: str) -> bool:
        """
        Process a TV episode file.
        
        Args:
            file_path: Path to the episode file
            
        Returns:
            True if processing was successful, False otherwise
        """
        if not self.is_media_file(file_path):
            logger.info(f"Skipping non-media file: {file_path}")
            return False
        
        info = self.extract_show_info(file_path)
        
        # Search for the show
        results = self.search_show(info['show_name'])
        
        if not results:
            logger.warning(f"No results found for show: {info['show_name']}")
            return False
        
        # For now, just use the first result
        show = results[0]
        
        # Create symlink
        return self.symlink_creator.create_tv_symlink(
            episode_file=file_path,
            show_name=show['name'],
            season_num=info['season'],
            episode_num=info['episode'],
            tmdb_id=str(show['id']),
            year=show.get('first_air_date', '')[:4] if show.get('first_air_date') else None
        )


class DirectoryProcessor(FileProcessor):
    """
    Processes directories containing media files.
    """
    
    def __init__(self, is_tv=False):
        """
        Initialize the directory processor.
        
        Args:
            is_tv: Whether to process as TV shows (True) or movies (False)
        """
        super().__init__()
        self.is_tv = is_tv
        self.processor = TVProcessor() if is_tv else MovieProcessor()
    
    def process_directory(self, directory_path: str) -> bool:
        """
        Process all media files in a directory.
        
        Args:
            directory_path: Path to the directory to process
            
        Returns:
            True if all files were processed successfully, False otherwise
        """
        success = True
        
        for root, _, files in os.walk(directory_path):
            for file in files:
                file_path = os.path.join(root, file)
                if self.is_media_file(file_path):
                    logger.info(f"Processing file: {file_path}")
                    if not self.processor.process_file(file_path):
                        success = False
        
        return success
    
    def process_file(self, file_path: str) -> bool:
        """
        Process a single file.
        
        Args:
            file_path: Path to the file to process
            
        Returns:
            True if processing was successful, False otherwise
        """
        return self.processor.process_file(file_path)