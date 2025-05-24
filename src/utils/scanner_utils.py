"""
Utility functions for scanning and matching media titles against known databases.
"""
import os
import re
import logging
import json

# Get logger
logger = logging.getLogger(__name__)

# Global variables to hold scanner lists
scanner_lists = {
    'tv': [],
    'movie': [],
    'anime_tv': [],
    'anime_movie': []
}

def normalize_title(title):
    """Normalize a title for comparison."""
    if not title:
        return ""
    # Convert to lowercase and strip whitespace
    title = title.lower().strip()
    # Remove special characters, replace with spaces
    title = re.sub(r'[^\w\s]', ' ', title)
    # Replace multiple spaces with single space
    title = re.sub(r'\s+', ' ', title)
    return title.strip()

def load_scanner_lists():
    """Load all scanner lists from files."""
    try:
        # Determine the path to the scanners directory
        scanner_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'scanners')
        
        logger.info(f"Loading scanner lists from {scanner_dir}")
        
        # Define file paths
        movie_file = os.path.join(scanner_dir, 'movies.txt')
        tv_file = os.path.join(scanner_dir, 'tv_series.txt')
        anime_movie_file = os.path.join(scanner_dir, 'anime_movies.txt')
        anime_series_file = os.path.join(scanner_dir, 'anime_series.txt')
        
        # Load each list
        scanner_lists['movie'] = _load_list_file(movie_file, 'movie')
        scanner_lists['tv'] = _load_list_file(tv_file, 'tv')
        scanner_lists['anime_movie'] = _load_list_file(anime_movie_file, 'anime_movie')
        scanner_lists['anime_tv'] = _load_list_file(anime_series_file, 'anime_tv')
        
        logger.info(f"Loaded {len(scanner_lists['movie'])} movies, {len(scanner_lists['tv'])} TV shows, "
                   f"{len(scanner_lists['anime_movie'])} anime movies, {len(scanner_lists['anime_tv'])} anime series")
        
        return True
    except Exception as e:
        logger.error(f"Error loading scanner lists: {e}", exc_info=True)
        return False

def _load_list_file(file_path, list_type):
    """Load a single scanner list file."""
    items = []
    if not os.path.exists(file_path):
        logger.warning(f"Scanner list file not found: {file_path}")
        return items
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Parse the file content based on the format in your scanner files
        # Format appears to be: "Title (Year) [TMDB_ID]"
        is_anime = list_type.startswith('anime_')
        content_type = 'movie' if list_type.endswith('movie') else 'tv'
        
        # Process each line
        for line in content.splitlines():
            if not line.strip() or line.strip().startswith('//'):
                continue
                
            # Extract using regex pattern
            match = re.search(r'(.+?)\s*\((\d{4})\)\s*\[([^\]]+)\]', line.strip())
            if match:
                title = match.group(1).strip()
                year = match.group(2)
                id_value = match.group(3)
                
                # Handle IDs that might be prefixed with "movie:" or other tags
                if id_value.startswith('movie:'):
                    tmdb_id = id_value[6:]
                elif id_value.lower() == 'error':
                    tmdb_id = None
                else:
                    tmdb_id = id_value
                
                items.append({
                    'title': title,
                    'year': year,
                    'tmdb_id': tmdb_id,
                    'anime': is_anime
                })
            else:
                logger.debug(f"Could not parse line in {list_type} list: {line}")
        
        logger.info(f"Loaded {len(items)} items from {file_path}")
        return items
        
    except Exception as e:
        logger.error(f"Error loading {file_path}: {e}", exc_info=True)
        return []

def check_scanner_lists(title):
    """Check if a title exists in any of the scanner lists.
    Returns the best match as (content_type, is_anime, tmdb_id, title, year)
    """
    if not scanner_lists['movie'] and not scanner_lists['tv']:
        # Lists haven't been loaded yet
        load_scanner_lists()
    
    normalized_search_title = normalize_title(title)
    
    # First try for exact matches
    for list_type in scanner_lists:
        for item in scanner_lists[list_type]:
            scanner_title = item.get('title', '')
            normalized_scanner_title = normalize_title(scanner_title)
            
            # Exact match
            if normalized_scanner_title == normalized_search_title:
                content_type = 'movie' if list_type.endswith('movie') else 'tv'
                is_anime = list_type.startswith('anime_')
                return (content_type, is_anime, item.get('tmdb_id'), scanner_title, item.get('year'))
    
    # Try for strong containment matches
    for list_type in scanner_lists:
        for item in scanner_lists[list_type]:
            scanner_title = item.get('title', '')
            normalized_scanner_title = normalize_title(scanner_title)
            
            # Strong containment (one contains the other completely)
            if (normalized_scanner_title in normalized_search_title or 
                normalized_search_title in normalized_scanner_title):
                content_type = 'movie' if list_type.endswith('movie') else 'tv'
                is_anime = list_type.startswith('anime_')
                return (content_type, is_anime, item.get('tmdb_id'), scanner_title, item.get('year'))
    
    # No match found
    return None

def find_all_matches(title):
    """Find all possible matches in scanner lists."""
    if not scanner_lists['movie'] and not scanner_lists['tv']:
        # Lists haven't been loaded yet
        load_scanner_lists()
    
    matches = []
    normalized_search_title = normalize_title(title)
    
    # First collect exact matches
    for list_type in scanner_lists:
        for item in scanner_lists[list_type]:
            scanner_title = item.get('title', '')
            normalized_scanner_title = normalize_title(scanner_title)
            
            content_type = 'movie' if list_type.endswith('movie') else 'tv'
            is_anime = list_type.startswith('anime_')
            
            # Exact match (highest priority)
            if normalized_scanner_title == normalized_search_title:
                matches.append((content_type, is_anime, item.get('tmdb_id'), 
                               scanner_title, item.get('year')))
                
    # If no exact matches, try strong containment matches
    if not matches:
        for list_type in scanner_lists:
            for item in scanner_lists[list_type]:
                scanner_title = item.get('title', '')
                normalized_scanner_title = normalize_title(scanner_title)
                
                content_type = 'movie' if list_type.endswith('movie') else 'tv'
                is_anime = list_type.startswith('anime_')
                
                # Strong containment (one contains the other completely)
                if (normalized_scanner_title in normalized_search_title or 
                    normalized_search_title in normalized_scanner_title):
                    matches.append((content_type, is_anime, item.get('tmdb_id'), 
                                   scanner_title, item.get('year')))
    
    # If still no matches, try partial matches
    if not matches:
        # Consider more aggressive matching strategies here if needed
        pass
    
    return matches

# Load scanner lists when the module is imported
load_scanner_lists()