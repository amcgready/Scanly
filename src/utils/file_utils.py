"""
File utility functions for Scanly.

This module expands on the existing file_utils.py to add functionality for
creating directory structures, symlinks, and hardlinks.
"""

import os
import logging
import shutil
from pathlib import Path

def create_directory_structure(base_path, directory_structure=None, mode=0o755):
    """
    Create a directory structure for media organization.
    
    Args:
        base_path: Base directory where the structure will be created
        directory_structure: List of directories to create (defaults to standard media folders)
        mode: Permission mode for the directories (default: 0o755)
        
    Returns:
        Tuple of (success, message)
    """
    logger = logging.getLogger(__name__)
    
    # Default directory structure if none provided
    if directory_structure is None:
        directory_structure = [
            'Movies',
            'TV Shows',
            'Anime',
            'Anime Movies'
        ]
    
    try:
        # Create base directory if it doesn't exist
        os.makedirs(base_path, mode=mode, exist_ok=True)
        
        # Create each directory in the structure
        for directory in directory_structure:
            full_path = os.path.join(base_path, directory)
            os.makedirs(full_path, mode=mode, exist_ok=True)
            logger.info(f"Created directory: {full_path}")
        
        return True, "Directory structure created successfully"
    
    except Exception as e:
        logger.error(f"Error creating directory structure: {str(e)}")
        return False, f"Error creating directory structure: {str(e)}"

def create_symlinks(source_file, base_dest_dir, is_anime=False, content_type='tv', metadata=None, force_overwrite=False):
    """
    Create symbolic links for media files.
    
    Args:
        source_file: Path to source media file
        base_dest_dir: Base destination directory
        is_anime: Whether this is anime content
        content_type: 'tv' or 'movie'
        metadata: Dictionary with metadata (title, year, season, episode, etc.)
        force_overwrite: Whether to overwrite existing files
        
    Returns:
        Tuple of (success, message)
    """
    logger = logging.getLogger(__name__)
    
    if metadata is None:
        metadata = {}
    
    try:
        # Extract metadata
        title = metadata.get('title', 'Unknown')
        year = metadata.get('year')
        season = metadata.get('season')
        episode = metadata.get('episode')
        resolution = metadata.get('resolution')
        tmdb_id = metadata.get('tmdb_id')
        
        # Determine destination directory structure
        if content_type.lower() == 'tv':
            if is_anime:
                # Anime series
                content_dir = 'Anime'
            else:
                # TV series
                content_dir = 'TV Shows'
            
            # Create folder name with optional IDs
            folder_name = title
            if tmdb_id:
                folder_name += f" [tmdb-{tmdb_id}]"
            
            # Create destination directory structure
            show_dir = os.path.join(base_dest_dir, content_dir, folder_name)
            
            # Add season folder for TV shows
            if season is not None:
                season_dir = os.path.join(show_dir, f"Season {season:02d}")
                dest_dir = season_dir
            else:
                dest_dir = show_dir
            
            # Create filename for the episode
            if season is not None and episode is not None:
                dest_name = f"{title} - S{season:02d}E{episode:02d}"
            else:
                dest_name = title
            
        else:
            # Movie
            if is_anime:
                content_dir = 'Anime Movies'
            else:
                content_dir = 'Movies'
            
            # Create folder name with year and optional IDs
            folder_name = title
            if year:
                folder_name += f" ({year})"
            if tmdb_id:
                folder_name += f" [tmdb-{tmdb_id}]"
            
            dest_dir = os.path.join(base_dest_dir, content_dir, folder_name)
            dest_name = folder_name
        
        # Add resolution to filename if available
        if resolution:
            dest_name += f" - {resolution}"
        
        # Get file extension from source
        _, ext = os.path.splitext(source_file)
        
        # Full destination path
        dest_file = os.path.join(dest_dir, f"{dest_name}{ext}")
        
        # Create destination directory if it doesn't exist
        os.makedirs(dest_dir, exist_ok=True)
        
        # Check if destination file already exists
        if os.path.exists(dest_file):
            if force_overwrite:
                # Remove existing link
                os.unlink(dest_file)
            else:
                return False, f"Destination file already exists: {dest_file}"
        
        # Create symbolic link
        os.symlink(source_file, dest_file)
        logger.info(f"Created symlink: {dest_file} -> {source_file}")
        
        return True, f"Created symlink: {dest_file}"
        
    except Exception as e:
        logger.error(f"Error creating symlink: {str(e)}")
        return False, f"Error creating symlink: {str(e)}"

def create_hardlinks(source_file, base_dest_dir, is_anime=False, content_type='tv', metadata=None, force_overwrite=False):
    """
    Create hard links for media files.
    
    Args:
        source_file: Path to source media file
        base_dest_dir: Base destination directory
        is_anime: Whether this is anime content
        content_type: 'tv' or 'movie'
        metadata: Dictionary with metadata (title, year, season, episode, etc.)
        force_overwrite: Whether to overwrite existing files
        
    Returns:
        Tuple of (success, message)
    """
    logger = logging.getLogger(__name__)
    
    if metadata is None:
        metadata = {}
    
    try:
        # Extract metadata
        title = metadata.get('title', 'Unknown')
        year = metadata.get('year')
        season = metadata.get('season')
        episode = metadata.get('episode')
        resolution = metadata.get('resolution')
        tmdb_id = metadata.get('tmdb_id')
        
        # Determine destination directory structure
        if content_type.lower() == 'tv':
            if is_anime:
                # Anime series
                content_dir = 'Anime'
            else:
                # TV series
                content_dir = 'TV Shows'
            
            # Create folder name with optional IDs
            folder_name = title
            if tmdb_id:
                folder_name += f" [tmdb-{tmdb_id}]"
            
            # Create destination directory structure
            show_dir = os.path.join(base_dest_dir, content_dir, folder_name)
            
            # Add season folder for TV shows
            if season is not None:
                season_dir = os.path.join(show_dir, f"Season {season:02d}")
                dest_dir = season_dir
            else:
                dest_dir = show_dir
            
            # Create filename for the episode
            if season is not None and episode is not None:
                dest_name = f"{title} - S{season:02d}E{episode:02d}"
            else:
                dest_name = title
            
        else:
            # Movie
            if is_anime:
                content_dir = 'Anime Movies'
            else:
                content_dir = 'Movies'
            
            # Create folder name with year and optional IDs
            folder_name = title
            if year:
                folder_name += f" ({year})"
            if tmdb_id:
                folder_name += f" [tmdb-{tmdb_id}]"
            
            dest_dir = os.path.join(base_dest_dir, content_dir, folder_name)
            dest_name = folder_name
        
        # Add resolution to filename if available
        if resolution:
            dest_name += f" - {resolution}"
        
        # Get file extension from source
        _, ext = os.path.splitext(source_file)
        
        # Full destination path
        dest_file = os.path.join(dest_dir, f"{dest_name}{ext}")
        
        # Create destination directory if it doesn't exist
        os.makedirs(dest_dir, exist_ok=True)
        
        # Check if destination file already exists
        if os.path.exists(dest_file):
            if force_overwrite:
                # Remove existing link
                os.unlink(dest_file)
            else:
                return False, f"Destination file already exists: {dest_file}"
        
        # Create hard link
        os.link(source_file, dest_file)
        logger.info(f"Created hardlink: {dest_file} -> {source_file}")
        
        return True, f"Created hardlink: {dest_file}"
        
    except Exception as e:
        logger.error(f"Error creating hardlink: {str(e)}")
        return False, f"Error creating hardlink: {str(e)}"

def get_media_files(directory, extensions=None):
    """
    Get all media files in a directory matching specified extensions.
    
    Args:
        directory: Directory to search
        extensions: List of file extensions to include (default: common media extensions)
        
    Returns:
        List of file paths
    """
    if extensions is None:
        extensions = ['.mkv', '.mp4', '.avi', '.mov', '.wmv', '.flv', '.m4v', '.ts']
    
    media_files = []
    
    try:
        for root, _, files in os.walk(directory):
            for file in files:
                if any(file.lower().endswith(ext) for ext in extensions):
                    media_files.append(os.path.join(root, file))
        
        return sorted(media_files)
    
    except Exception as e:
        logging.error(f"Error finding media files: {str(e)}")
        return []