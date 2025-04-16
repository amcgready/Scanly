import os
import re
import logging
import sys
from pathlib import Path
import shutil

def create_symlinks(source_path, destination_path, is_anime=False, content_type=None, metadata=None, force_overwrite=False):
    """
    Create symbolic links for the given source path at the destination path.
    
    Args:
        source_path: Path to the source file or directory
        destination_path: Base destination directory
        is_anime: Boolean indicating if the content is anime
        content_type: 'tv' or 'movie'
        metadata: Dict containing metadata about the content
        force_overwrite: Boolean to force overwrite existing files
        
    Returns:
        Tuple of (success, message)
    """
    logger = logging.getLogger(__name__)
    
    # Set default logging level if not already set
    if not logger.handlers:
        logger.setLevel(logging.DEBUG)
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
        logger.addHandler(handler)
    
    try:
        # Enhanced error checking and debug logging
        if not os.path.exists(source_path):
            logger.error(f"Source path does not exist: {source_path}")
            return False, f"Source path does not exist: {source_path}"
            
        if not destination_path:
            logger.error("Destination path is not set")
            return False, "Destination path is not set"
        
        # Extensive debug logging
        logger.debug(f"Creating symlink:")
        logger.debug(f"  Source path: {source_path}")
        logger.debug(f"  Destination path: {destination_path}")
        logger.debug(f"  Content type: {content_type}")
        logger.debug(f"  Is anime: {is_anime}")
        logger.debug(f"  Metadata: {metadata}")
        
        # Extract metadata
        title = metadata.get('title', 'Unknown') if metadata else 'Unknown'
        year = metadata.get('year', '') if metadata else ''
        season = metadata.get('season') if metadata else None
        episode = metadata.get('episode') if metadata else None
        episode_title = metadata.get('episode_title') if metadata else None
        
        # Clean the title for file system use
        title = clean_filename(title)
        
        # Determine the appropriate folder structure based on content type and anime flag
        # We use four distinct top-level content folders:
        if content_type == 'tv':
            if is_anime:
                # Anime Series
                content_dir = os.path.join(destination_path, "Anime Series", title)
            else:
                # TV Series
                content_dir = os.path.join(destination_path, "TV Series", title)
            
            # Add season folder for TV content
            if season is not None:
                season_dir = f"Season {season:02d}"
                content_dir = os.path.join(content_dir, season_dir)
        else:
            # Movie content
            if is_anime:
                # Anime Movies
                title_with_year = f"{title} ({year})" if year else title
                content_dir = os.path.join(destination_path, "Anime Movies", title_with_year)
            else:
                # Regular Movies
                title_with_year = f"{title} ({year})" if year else title
                content_dir = os.path.join(destination_path, "Movies", title_with_year)
        
        # Create the content directory if it doesn't exist
        logger.debug(f"Creating content directory: {content_dir}")
        try:
            os.makedirs(content_dir, exist_ok=True)
        except Exception as e:
            logger.error(f"Failed to create content directory: {e}")
            return False, f"Failed to create content directory: {str(e)}"
        
        # Handle the file differently based on whether it's a directory or a file
        if os.path.isdir(source_path):
            # Directory handling - link all files inside
            success = True
            messages = []
            
            # Get all files in the source directory (non-recursive)
            for filename in os.listdir(source_path):
                file_path = os.path.join(source_path, filename)
                
                # Skip if not a file
                if not os.path.isfile(file_path):
                    continue
                
                # For TV shows, format the filename if we have season/episode info
                if content_type == 'tv' and season is not None and episode is not None:
                    # Extract file extension
                    name, ext = os.path.splitext(filename)
                    
                    # Format as SxxExx - Original filename
                    if episode_title:
                        new_filename = f"S{season:02d}E{episode:02d} - {episode_title}{ext}"
                    else:
                        new_filename = f"S{season:02d}E{episode:02d} - {name}{ext}"
                else:
                    new_filename = filename
                
                # Create symlink for this file
                dest_file_path = os.path.join(content_dir, new_filename)
                
                # Check if destination already exists
                if os.path.exists(dest_file_path):
                    if force_overwrite:
                        try:
                            os.remove(dest_file_path)
                        except Exception as e:
                            logger.error(f"Failed to remove existing file: {e}")
                            success = False
                            messages.append(f"Failed to remove existing file: {dest_file_path}")
                            continue
                    else:
                        logger.warning(f"Destination file already exists: {dest_file_path}")
                        success = False
                        messages.append(f"File already exists: {dest_file_path}")
                        continue
                
                # Create symlink
                try:
                    # Use absolute paths for symlinks
                    abs_source = os.path.abspath(file_path)
                    logger.debug(f"Creating symlink: {abs_source} -> {dest_file_path}")
                    os.symlink(abs_source, dest_file_path)
                    logger.info(f"Created symlink: {abs_source} -> {dest_file_path}")
                    messages.append(f"Created symlink for: {filename}")
                except Exception as e:
                    logger.error(f"Error creating symlink for {filename}: {e}")
                    success = False
                    messages.append(f"Error creating symlink for {filename}: {str(e)}")
            
            if not messages:
                messages = ["No files processed"]
                
            return success, "\n".join(messages)
            
        else:
            # Single file handling
            filename = os.path.basename(source_path)
            
            # For TV shows, format the filename if we have season/episode info
            if content_type == 'tv' and season is not None and episode is not None:
                # Extract file extension
                name, ext = os.path.splitext(filename)
                
                # Format as SxxExx - Title.ext or SxxExx - Episode Title.ext
                if episode_title:
                    new_filename = f"S{season:02d}E{episode:02d} - {episode_title}{ext}"
                else:
                    new_filename = f"S{season:02d}E{episode:02d} - {name}{ext}"
            else:
                new_filename = filename
            
            # Create the destination path
            dest_file_path = os.path.join(content_dir, new_filename)
            
            # Check if destination already exists
            if os.path.exists(dest_file_path):
                if force_overwrite:
                    try:
                        os.remove(dest_file_path)
                    except Exception as e:
                        logger.error(f"Failed to remove existing file: {e}")
                        return False, f"Failed to remove existing file: {dest_file_path}"
                else:
                    logger.warning(f"Destination file already exists: {dest_file_path}")
                    return False, f"File already exists: {dest_file_path}"
            
            # Create symlink
            try:
                # Use absolute paths for symlinks
                abs_source = os.path.abspath(source_path)
                logger.debug(f"Creating symlink: {abs_source} -> {dest_file_path}")
                os.symlink(abs_source, dest_file_path)
                logger.info(f"Created symlink: {abs_source} -> {dest_file_path}")
                return True, f"Created symlink: {new_filename} in {content_dir}"
            except Exception as e:
                logger.error(f"Error creating symlink: {e}")
                
                # Check for common errors and provide helpful messages
                error_msg = str(e).lower()
                if "permission denied" in error_msg:
                    return False, f"Permission denied. Check that you have write permissions to {destination_path}"
                elif "no such file or directory" in error_msg:
                    return False, f"Could not create symlink. Directory {content_dir} may not exist or permissions issue."
                else:
                    return False, f"Error creating symlink: {str(e)}"
    
    except Exception as e:
        logger.error(f"Unexpected error in create_symlinks: {e}", exc_info=True)
        return False, f"Unexpected error: {str(e)}"

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