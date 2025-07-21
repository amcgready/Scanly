"""
File utility functions for Scanly.

This module expands on the existing file_utils.py to add functionality for
creating directory structures, symlinks, and hardlinks.
"""

import os
import logging
import shutil
from pathlib import Path
from src.utils.webhooks import send_symlink_creation_notification

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

def create_symlinks(source_path, destination_base, is_anime=False, content_type='movie', metadata=None, force_overwrite=False):
    """
    Create symlinks from source file to destination using the appropriate naming convention.
    
    Args:
        source_path: Source file path
        destination_base: Base destination directory
        is_anime: Whether this is anime content
        content_type: Content type ('movie' or 'tv')
        metadata: Dictionary containing title, year, season, episode, etc.
        force_overwrite: Whether to overwrite existing files
        
    Returns:
        Tuple of (success, message)
    """
    if metadata is None:
        metadata = {}
    
    # Extract metadata
    title = metadata.get('title', '')
    year = metadata.get('year')
    season = metadata.get('season')
    episode = metadata.get('episode')
    resolution = metadata.get('resolution')
    part = metadata.get('part')
    episode_title = metadata.get('episode_title')
    tmdb_id = metadata.get('tmdb_id')
    imdb_id = metadata.get('imdb_id')
    tvdb_id = metadata.get('tvdb_id')
    
    # Validate title
    if not title:
        return False, "Title is required"
    
    # Get file extension
    _, ext = os.path.splitext(source_path)
    
    # Determine content folder based on content type and anime status
    content_folder = ""
    if content_type == 'tv':
        if is_anime:
            content_folder = os.environ.get('CUSTOM_ANIME_SHOW_FOLDER', 'Anime Shows')
        else:
            content_folder = os.environ.get('CUSTOM_SHOW_FOLDER', 'TV Shows')
    else:  # movie
        if is_anime:
            content_folder = os.environ.get('CUSTOM_ANIME_MOVIE_FOLDER', 'Anime Movies')
        else:
            content_folder = os.environ.get('CUSTOM_MOVIE_FOLDER', 'Movies')
    
    # Add resolution subfolder if enabled
    if content_type == 'tv' and os.environ.get('SHOW_RESOLUTION_STRUCTURE', 'false').lower() in ('true', 'yes', '1'):
        if resolution:
            content_folder = os.path.join(content_folder, resolution)
    
    if content_type == 'movie' and os.environ.get('MOVIE_RESOLUTION_STRUCTURE', 'false').lower() in ('true', 'yes', '1'):
        if resolution:
            content_folder = os.path.join(content_folder, resolution)
    
    # Create content path (Movies/TV Shows)
    content_path = os.path.join(destination_base, content_folder)
    
    # Create title string with year if available
    title_with_year = title
    if year:
        title_with_year = f"{title} ({year})"
    
    # Add IDs to folder name based on environment settings
    folder_suffix = ""
    if tmdb_id and os.environ.get('TMDB_FOLDER_ID', 'true').lower() in ('true', 'yes', '1'):
        folder_suffix += f" {{tmdb-{tmdb_id}}}"
    
    if imdb_id and os.environ.get('IMDB_FOLDER_ID', 'false').lower() in ('true', 'yes', '1'):
        folder_suffix += f" [imdb-{imdb_id}]"
    
    if tvdb_id and os.environ.get('TVDB_FOLDER_ID', 'false').lower() in ('true', 'yes', '1'):
        folder_suffix += f" [tvdb-{tvdb_id}]"
    
    # Create title folder with IDs
    title_folder = f"{title_with_year}{folder_suffix}"
    title_path = os.path.join(content_path, title_folder)
    
    # For TV shows, include season folder
    if content_type == 'tv' and season is not None:
        # Create season folder name (Season 01, Season 02, etc.)
        season_folder = f"Season {season:02d}"
        season_path = os.path.join(title_path, season_folder)
        
        # Create episode filename
        if episode is not None:
            # Format: ShowName - S01E01 - Episode Title.ext
            episode_name = f"{title} - S{season:02d}E{episode:02d}"
            
            # Add episode title if available
            if episode_title:
                episode_name += f" - {episode_title}"
            
            # Add extension
            dest_filename = f"{episode_name}{ext}"
            dest_path = os.path.join(season_path, dest_filename)
        else:
            # Fallback if episode number is missing
            # Use original filename
            dest_filename = os.path.basename(source_path)
            dest_path = os.path.join(season_path, dest_filename)
    else:
        # For movies, put directly in title folder
        # Format: MovieName (Year).ext or MovieName (Year) - Part X.ext
        movie_name = title_with_year
        
        # Add part number if available
        if part:
            movie_name += f" - Part {part}"
        
        # Add extension
        dest_filename = f"{movie_name}{ext}"
        dest_path = os.path.join(title_path, dest_filename)
    
    # Create parent directories
    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
    
    # Check if symlink already exists
    if os.path.exists(dest_path):
        if os.path.islink(dest_path):
            # Check if symlink points to the same file
            if os.path.realpath(dest_path) == os.path.realpath(source_path):
                # Symlink already exists and points to the same file
                return True, f"Symlink already exists: {dest_path}"
            elif force_overwrite:
                # Remove existing symlink
                os.remove(dest_path)
            else:
                # Symlink exists but points to a different file
                return False, f"Symlink already exists and points to different file: {dest_path}"
        elif force_overwrite:
            # Remove existing file
            os.remove(dest_path)
        else:
            # File exists but is not a symlink
            return False, f"File already exists: {dest_path}"
    
    # Get symlink type and relative setting
    link_type = os.environ.get('LINK_TYPE', 'symlink').lower()
    relative = os.environ.get('RELATIVE_SYMLINK', 'false').lower() in ('true', 'yes', '1')
    
    try:
        # Create symlink or hardlink
        if link_type == 'hardlink':
            os.link(source_path, dest_path)
            return True, f"Created hardlink: {dest_path}"
        else:  # Default to symlink
            # Make relative if requested
            if relative:
                # Calculate relative path
                source_path = os.path.relpath(source_path, os.path.dirname(dest_path))
            
            # Create symlink
            os.symlink(source_path, dest_path)
            
            send_symlink_creation_notification(
                title=metadata.get('title', ''),
                year=metadata.get('year', ''),
                poster=metadata.get('poster', ''),
                description=metadata.get('description', ''),
                symlink_path=dest_path
            )
            
            return True, f"Created symlink: {dest_path}"
    except Exception as e:
        return False, f"Error creating link: {e}"

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
                folder_name += f" {{tmdb-{tmdb_id}}}"
            
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
                folder_name += f" {{tmdb-{tmdb_id}}}"
            
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