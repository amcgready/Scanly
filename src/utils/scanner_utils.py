"""
Utility functions for scanner operations in Scanly.
"""

import logging
import os
import json
import re

def get_logger():
    """Get a logger for the scanner utils module."""
    return logging.getLogger(__name__)

logger = get_logger()

# Scanner lists cache
scanner_lists = {}

def load_scanner_lists():
    """Load all scanner lists from data directory."""
    global scanner_lists
    
    # Reset scanner lists
    scanner_lists = {
        'movie': [],
        'tv': []
    }
    
    try:
        # Get the directory containing scanner lists
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        data_dir = os.path.join(base_dir, 'data')
        
        if not os.path.exists(data_dir):
            logger.warning(f"Data directory not found: {data_dir}")
            return
        
        # Load movie scanner list
        movie_path = os.path.join(data_dir, 'movie_scanner.json')
        if os.path.exists(movie_path):
            with open(movie_path, 'r') as f:
                scanner_lists['movie'] = json.load(f)
            logger.info(f"Loaded {len(scanner_lists['movie'])} movies from scanner list")
        
        # Load TV scanner list
        tv_path = os.path.join(data_dir, 'tv_scanner.json')
        if os.path.exists(tv_path):
            with open(tv_path, 'r') as f:
                scanner_lists['tv'] = json.load(f)
            logger.info(f"Loaded {len(scanner_lists['tv'])} TV shows from scanner list")
    
    except Exception as e:
        logger.error(f"Error loading scanner lists: {e}", exc_info=True)

def normalize_title(title):
    """Normalize a title for comparison."""
    if not title:
        return ""
    
    # Convert to lowercase
    title = title.lower()
    
    # Remove special characters and extra spaces
    title = re.sub(r'[^\w\s]', ' ', title)
    title = re.sub(r'\s+', ' ', title).strip()
    
    return title

def find_all_matches(title, content_type=None):
    """Find all possible matches in scanner lists, optionally filtered by content type.
    
    Args:
        title: The title to search for
        content_type: Optional filter for content type ('movie', 'tv', or None for all)
    
    Returns:
        List of tuples with matches: (content_type, is_anime, tmdb_id, title, year)
    """
    matches = []
    
    # Ensure scanner lists are loaded
    if not scanner_lists:
        load_scanner_lists()
    
    # Get all potential matches from all scanner lists or just the specified content type
    normalized_search_title = normalize_title(title)
    
    # Define which list types to check
    list_types_to_check = ['movie', 'tv']
    if content_type == 'movie':
        list_types_to_check = ['movie']
    elif content_type == 'tv':
        list_types_to_check = ['tv']
    
    logger.debug(f"Checking {', '.join(list_types_to_check)} scanner lists for '{title}'")
    
    # Check each list type
    for list_type in list_types_to_check:
        if list_type not in scanner_lists:
            continue
            
        for item in scanner_lists[list_type]:
            scanner_title = item.get('title', '')
            normalized_scanner_title = normalize_title(scanner_title)
            
            # Extract item metadata
            year = item.get('year')
            tmdb_id = item.get('tmdb_id')
            is_anime = item.get('anime', False)
            
            # Exact match (highest priority)
            if normalized_scanner_title == normalized_search_title:
                logger.debug(f"EXACT MATCH: '{title}' -> '{scanner_title}'")
                matches.append((list_type, is_anime, tmdb_id, scanner_title, year))
                
            # Strong containment match (one title fully contains the other)
            elif (len(normalized_scanner_title) > 4 and normalized_scanner_title in normalized_search_title) or \
                 (len(normalized_search_title) > 4 and normalized_search_title in normalized_scanner_title):
                logger.debug(f"STRONG CONTAINMENT: '{title}' -> '{scanner_title}'")
                matches.append((list_type, is_anime, tmdb_id, scanner_title, year))
                
            # Check for direct substring match (with length requirements to avoid false positives)
            elif len(normalized_scanner_title) > 6 and len(normalized_search_title) > 6:
                # Split into words and check for significant word overlap
                scanner_words = set(normalized_scanner_title.split())
                search_words = set(normalized_search_title.split())
                
                # If titles share 2+ significant words (longer than 3 chars)
                significant_scanner_words = {w for w in scanner_words if len(w) > 3}
                significant_search_words = {w for w in search_words if len(w) > 3}
                
                common_words = significant_scanner_words.intersection(significant_search_words)
                
                if len(common_words) >= 2:
                    logger.debug(f"STRONG SUBSTRING: '{title}' -> '{scanner_title}'")
                    matches.append((list_type, is_anime, tmdb_id, scanner_title, year))
    
    # Log the results
    if matches:
        logger.info(f"Found {len(matches)} matches for '{title}'")
    else:
        logger.debug(f"No matches found for '{title}'")
    
    return matches

# Load scanner lists when the module is imported
load_scanner_lists()