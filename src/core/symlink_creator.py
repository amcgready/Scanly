"""
Creates symlinks for media files.

This module provides functionality for creating organized symlinks
to media files in the destination directory.
"""

import os
import shutil
from pathlib import Path
from typing import Optional

from src.config import DESTINATION_DIRECTORY, RELATIVE_SYMLINK
from src.utils.logger import get_logger

logger = get_logger(__name__)

class SymlinkCreator:
    """
    Creates organized symlinks for media files.
    """
    
    def __init__(self, destination_directory: Optional[str] = None):
        """
        Initialize a SymlinkCreator.
        
        Args:
            destination_directory: Directory where symlinks will be created.
                                  If None, uses the value from settings.
        """
        self.destination_dir = destination_directory or DESTINATION_DIRECTORY
        logger.debug(f"SymlinkCreator initialized with destination directory: {self.destination_dir}")
    
    def ensure_directory_exists(self, directory_path: str) -> bool:
        """
        Ensure a directory exists, creating it if necessary.
        
        Args:
            directory_path: Path to the directory
            
        Returns:
            True if the directory exists or was created, False otherwise
        """
        if os.path.exists(directory_path):
            if not os.path.isdir(directory_path):
                logger.error(f"Path exists but is not a directory: {directory_path}")
                return False
            return True
        
        try:
            os.makedirs(directory_path, exist_ok=True)
            logger.debug(f"Created directory: {directory_path}")
            return True
        except PermissionError:
            logger.error(f"Permission denied when creating directory: {directory_path}")
            return False
        except OSError as e:
            logger.error(f"Failed to create directory {directory_path}: {e}")
            return False
    
    def create_symlink(self, source_path: str, rel_destination_path: str) -> bool:
        """
        Create a symlink from source_path to destination_path.
        
        Args:
            source_path: Path to the source file
            rel_destination_path: Relative path within destination directory
            
        Returns:
            True if symlink was created successfully, False otherwise
        """
        source_path = os.path.abspath(source_path)
        full_dest_path = os.path.join(self.destination_dir, rel_destination_path)
        dest_dir = os.path.dirname(full_dest_path)
        
        # First make sure destination directory exists
        if not self.ensure_directory_exists(dest_dir):
            logger.error(f"Cannot create symlink because destination directory could not be created: {dest_dir}")
            print(f"\nError: Cannot create destination directory: {dest_dir}")
            print("Check permissions or update the destination directory in your configuration.")
            return False
        
        try:
            # Remove existing symlink if it exists
            if os.path.exists(full_dest_path):
                if os.path.islink(full_dest_path):
                    os.unlink(full_dest_path)
                else:
                    logger.warning(f"Destination exists and is not a symlink: {full_dest_path}")
                    return False
            
            # Create the symlink
            if RELATIVE_SYMLINK:
                # Create a relative symlink
                source_rel_path = os.path.relpath(source_path, os.path.dirname(full_dest_path))
                os.symlink(source_rel_path, full_dest_path)
            else:
                # Create an absolute symlink
                os.symlink(source_path, full_dest_path)
                
            logger.info(f"Created symlink: {source_path} -> {full_dest_path}")
            return True
            
        except PermissionError:
            logger.error(f"Permission denied creating symlink to {full_dest_path}")
            print(f"\nError: Permission denied creating symlink to {full_dest_path}")
            print("You may need to run the application with elevated permissions or choose a different destination directory.")
            return False
        except Exception as e:
            logger.error(f"Error creating symlink from {source_path} to {full_dest_path}: {e}")
            return False
    
    def create_movie_symlink(self, movie_file: str, movie_name: str, 
                            tmdb_id: Optional[str] = None,
                            imdb_id: Optional[str] = None,
                            year: Optional[str] = None,
                            collection: Optional[str] = None,
                            is_anime: bool = False) -> bool:
        """
        Create a symlink for a movie file.
        
        Args:
            movie_file: Path to the movie file
            movie_name: Name of the movie
            tmdb_id: TMDB ID of the movie
            imdb_id: IMDB ID of the movie
            year: Release year of the movie
            collection: Collection the movie belongs to
            is_anime: Whether the movie is anime
            
        Returns:
            True if symlink was created successfully, False otherwise
        """
        from src.utils.media_info import get_resolution_folder
        from src.utils.anime_utils import get_anime_folder
        from src.config import (CUSTOM_MOVIE_FOLDER, MOVIE_COLLECTION_ENABLED,
                               TMDB_FOLDER_ID, IMDB_FOLDER_ID)
        
        # Determine the base folder (anime or regular)
        base_folder = get_anime_folder(is_tv=False) if is_anime else None
        if not base_folder:
            base_folder = get_resolution_folder(movie_file, is_tv=False)
        
        # Clean movie name for file system
        clean_name = self._clean_filename(movie_name)
        
        # Add year if available
        if year:
            folder_name = f"{clean_name} ({year})"
        else:
            folder_name = clean_name
            
        # Add IDs if enabled
        if TMDB_FOLDER_ID and tmdb_id:
            folder_name += f" [tmdb-{tmdb_id}]"
        if IMDB_FOLDER_ID and imdb_id:
            folder_name += f" [imdb-{imdb_id}]"
        
        # Handle collections
        if MOVIE_COLLECTION_ENABLED and collection:
            clean_collection = self._clean_filename(collection)
            rel_path = os.path.join(base_folder, clean_collection, folder_name, os.path.basename(movie_file))
        else:
            rel_path = os.path.join(base_folder, folder_name, os.path.basename(movie_file))
        
        return self.create_symlink(movie_file, rel_path)
    
    def create_tv_symlink(self, episode_file: str, show_name: str, 
                         season_num: str, episode_num: str,
                         tmdb_id: Optional[str] = None,
                         tvdb_id: Optional[str] = None,
                         year: Optional[str] = None,
                         is_anime: bool = False) -> bool:
        """
        Create a symlink for a TV episode file.
        
        Args:
            episode_file: Path to the episode file
            show_name: Name of the TV show
            season_num: Season number
            episode_num: Episode number
            tmdb_id: TMDB ID of the show
            tvdb_id: TVDB ID of the show
            year: Air year of the show
            is_anime: Whether the show is anime
            
        Returns:
            True if symlink was created successfully, False otherwise
        """
        from src.utils.media_info import get_resolution_folder
        from src.utils.anime_utils import get_anime_folder
        from src.config import CUSTOM_SHOW_FOLDER, TMDB_FOLDER_ID, TVDB_FOLDER_ID
        
        # Determine the base folder (anime or regular)
        base_folder = get_anime_folder(is_tv=True) if is_anime else None
        if not base_folder:
            base_folder = get_resolution_folder(episode_file, is_tv=True)
        
        # Clean show name for file system
        clean_name = self._clean_filename(show_name)
        
        # Add year if available
        if year:
            folder_name = f"{clean_name} ({year})"
        else:
            folder_name = clean_name
            
        # Add IDs if enabled
        if TMDB_FOLDER_ID and tmdb_id:
            folder_name += f" [tmdb-{tmdb_id}]"
        if TVDB_FOLDER_ID and tvdb_id:
            folder_name += f" [tvdb-{tvdb_id}]"
        
        # Format the season folder
        season_folder = f"Season {season_num}"
        
        # Format the episode filename
        episode_filename = f"S{season_num.zfill(2)}E{episode_num.zfill(2)} - {os.path.basename(episode_file)}"
        
        rel_path = os.path.join(base_folder, folder_name, season_folder, episode_filename)
        
        return self.create_symlink(episode_file, rel_path)
    
    def _clean_filename(self, name: str) -> str:
        """
        Clean a name for use as a filename.
        
        Args:
            name: Name to clean
            
        Returns:
            Cleaned name
        """
        # Replace invalid filename characters
        invalid_chars = ['<', '>', ':', '"', '/', '\\', '|', '?', '*']
        result = name
        
        for char in invalid_chars:
            result = result.replace(char, '_')
            
        # Remove leading/trailing whitespace and dots
        result = result.strip().strip('.')
        
        # Replace multiple spaces with a single space
        result = ' '.join(result.split())
        
        return result
