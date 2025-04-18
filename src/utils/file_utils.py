import os
import re
import logging
import sys
from pathlib import Path
import shutil

def create_symlinks(source_path, destination_path, is_anime=False, content_type=None, metadata=None, force_overwrite=False):
    """
    Create symbolic links for the given source file at the destination path.
    
    Args:
        source_path: Path to the source file
        destination_path: Base destination directory
        is_anime: Boolean indicating if the content is anime
        content_type: 'tv' or 'movie'
        metadata: Dict containing metadata about the content
        force_overwrite: Boolean to force overwrite existing files
        
    Returns:
        Tuple of (success, message)
    """
    logger = logging.getLogger(__name__)
    
    try:
        # Extract metadata
        title = metadata.get('title', 'Unknown')
        year = metadata.get('year')
        season = metadata.get('season')
        episode = metadata.get('episode')
        tmdb_id = metadata.get('tmdb_id')
        imdb_id = metadata.get('imdb_id')
        tvdb_id = metadata.get('tvdb_id')
        
        # Print all metadata for debugging
        logger.debug(f"Processing file with metadata: {metadata}")
        
        # Clean the title for filesystem use
        clean_title = clean_filename(title)
        
        # Read environment variables directly from os.environ
        tmdb_folder_id = os.environ.get('TMDB_FOLDER_ID', '').lower()
        imdb_folder_id = os.environ.get('IMDB_FOLDER_ID', '').lower()
        tvdb_folder_id = os.environ.get('TVDB_FOLDER_ID', '').lower()
        
        # Debug environment variables
        logger.debug(f"Environment variables: TMDB_FOLDER_ID={tmdb_folder_id}, IMDB_FOLDER_ID={imdb_folder_id}, TVDB_FOLDER_ID={tvdb_folder_id}")
        logger.debug(f"IDs available: TMDB={tmdb_id}, IMDB={imdb_id}, TVDB={tvdb_id}")
        
        # Check which IDs should be included in the folder name
        include_tmdb_id = tmdb_folder_id == 'true' and tmdb_id is not None
        include_imdb_id = imdb_folder_id == 'true' and imdb_id is not None
        include_tvdb_id = tvdb_folder_id == 'true' and tvdb_id is not None
        
        # Log the inclusion decisions
        logger.debug(f"ID inclusion decisions: TMDB={include_tmdb_id}, IMDB={include_imdb_id}, TVDB={include_tvdb_id}")
        
        # Determine content type subfolder based on environment variables
        if content_type == 'tv':
            if is_anime:
                content_subdir = os.environ.get('CUSTOM_ANIME_SHOW_FOLDER', 'Anime Shows').strip('"\'')
            else:
                content_subdir = os.environ.get('CUSTOM_SHOW_FOLDER', 'TV Shows').strip('"\'')
        else:  # movie
            if is_anime:
                content_subdir = os.environ.get('CUSTOM_ANIME_MOVIE_FOLDER', 'Anime Movies').strip('"\'')
            else:
                content_subdir = os.environ.get('CUSTOM_MOVIE_FOLDER', 'Movies').strip('"\'')
        
        # Create base path for the content type
        content_base = os.path.join(destination_path, content_subdir)
        os.makedirs(content_base, exist_ok=True)
        
        # Format the media folder name - title is required
        media_folder = clean_title
        
        # ALWAYS add year if available - this is mandatory for both TV shows and movies
        if year:
            media_folder += f" ({year})"
        else:
            logger.warning(f"No year available for {title}, folder name will not include year")
            
        # Add IDs in correct format - only for folder names, not file names
        if include_tmdb_id:
            media_folder += f" [tmdb-{tmdb_id}]"
        if include_imdb_id:
            media_folder += f" [imdb-{imdb_id}]"
        if include_tvdb_id and content_type == 'tv':
            media_folder += f" [tvdb-{tvdb_id}]"
            
        logger.debug(f"Final media folder name: {media_folder}")
        
        # For TV shows
        if content_type == 'tv':
            # Create the full series path
            series_path = os.path.join(content_base, media_folder)
            os.makedirs(series_path, exist_ok=True)
            
            # Create season folder in the format "Season XX"
            if season:
                season_folder = f"Season {int(season):02d}"
                season_path = os.path.join(series_path, season_folder)
                os.makedirs(season_path, exist_ok=True)
                
                # Format the episode filename
                if episode:
                    # Get file extension
                    _, ext = os.path.splitext(source_path)
                    
                    # Format the episode filename as "Title - SXXEXX.ext" - no IDs in filenames
                    # Use clean_title instead of media_folder to avoid IDs in filenames
                    base_title = clean_title
                    if year:  # Include year in episode filename if available
                        base_title += f" ({year})"
                        
                    episode_filename = f"{base_title} - S{int(season):02d}E{int(episode):02d}"
                    
                    # Add episode title if available
                    episode_title = metadata.get('episode_title')
                    if episode_title:
                        episode_filename += f" - {clean_filename(episode_title)}"
                    
                    # Add extension
                    episode_filename += ext
                    
                    # Full path for the symlink
                    link_path = os.path.join(season_path, episode_filename)
                else:
                    # If no episode number, use original filename
                    link_path = os.path.join(season_path, os.path.basename(source_path))
            else:
                # If no season number, link directly to series folder
                link_path = os.path.join(series_path, os.path.basename(source_path))
        
        # For movies
        else:
            # Format the movie filename - place in media folder directory
            _, ext = os.path.splitext(source_path)
            
            # Base movie filename - no IDs in filenames
            # Use clean_title instead of media_folder to avoid IDs in filenames
            movie_filename = clean_title
            if year:
                movie_filename += f" ({year})"
                
            # Handle multi-part movies
            part = metadata.get('part')
            if part:
                movie_filename += f" - Part {part}"
                
            # Add extension
            movie_filename += ext
            
            # Create the movie folder path
            movie_path = os.path.join(content_base, media_folder)
            os.makedirs(movie_path, exist_ok=True)
            
            # Full path for the symlink
            link_path = os.path.join(movie_path, movie_filename)
        
        # Log the final paths
        logger.debug(f"Content base: {content_base}")
        logger.debug(f"Media folder: {media_folder}")
        logger.debug(f"Link path: {link_path}")
        
        # Check if target link already exists
        if os.path.exists(link_path) and not force_overwrite:
            return False, f"Destination already exists: {link_path}"
        
        # Create the symlink
        logger.info(f"Creating symlink: {os.path.abspath(source_path)} -> {link_path}")
        os.symlink(os.path.abspath(source_path), link_path)
        
        return True, f"Created symlink to {link_path}"
        
    except Exception as e:
        logger.error(f"Error creating symlink: {e}", exc_info=True)
        return False, f"Error creating symlink: {str(e)}"

def clean_filename(filename):
    """
    Clean a filename to be safe for file system use.
    
    Args:
        filename: The filename to clean
        
    Returns:
        A cleaned filename
    """
    if not filename:
        return "unnamed"
        
    # Replace illegal characters
    cleaned = re.sub(r'[\\/*?:"<>|]', '', filename)
    # Replace multiple spaces with a single space
    cleaned = re.sub(r'\s+', ' ', cleaned)
    # Trim spaces from beginning and end
    cleaned = cleaned.strip()
    
    # Ensure we have something left after cleaning
    if not cleaned:
        return "unnamed"
        
    return cleaned

def ensure_directory_exists(path):
    """
    Ensure a directory exists, creating it if necessary.
    
    Args:
        path: Directory path to ensure
        
    Returns:
        Boolean indicating success
    """
    try:
        if not os.path.exists(path):
            os.makedirs(path, exist_ok=True)
        return True
    except Exception as e:
        logging.error(f"Failed to create directory {path}: {e}")
        return False