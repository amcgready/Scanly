"""
Utility functions for anime detection and processing.

This module provides functions for detecting whether content is anime
and handling anime-specific processing.
"""

import os
import re
from typing import Optional

from src.config import ANIME_SCAN, ANIME_SEPARATION
from src.utils.logger import get_logger

logger = get_logger(__name__)

# Common anime keywords in filenames
ANIME_KEYWORDS = [
    'anime', 'manga', 'subbed', 'dubbed', 'sub', 'dub',
    'japanese', '日本', 'japan', 'jp', 'jap',
    '[bd]', 'bluray', 'bd', 'dvdrip', 'dvd', 'tv', 'hdtv',
    'x264', 'x265', 'h264', 'h265', 'hevc', 'avc',
    'crc', 'crc32',
    'webrip', 'web-dl', 'webhd', 'webdl',
    'season', 'episode', 'ep', 's01', 's02',
    'aac', 'ac3', 'flac', 'opus',
    'horriblesubs', 'subsplease', 'erai-raws', 'animejp'
]

# Common anime studios and publishers
ANIME_STUDIOS = [
    'toei', 'gainax', 'shaft', 'bones', 'trigger',
    'sunrise', 'madhouse', 'kyoto', 'ghibli', 'aniplex',
    'mappa', 'wit', 'cloverworks', 'a-1', 'jc staff',
    'production i.g', 'ufotable', 'p.a. works'
]


def is_anime(filename: str) -> bool:
    """
    Determine if a file is likely anime based on its filename.
    
    Args:
        filename: Name of the file to check
        
    Returns:
        True if the file appears to be anime, False otherwise
    """
    if not ANIME_SCAN:
        return False
    
    filename_lower = filename.lower()
    
    # Check for common anime release patterns
    if re.search(r'\[.*?\]', filename_lower):
        # Anime releases often have [Group] [Info] pattern
        if len(re.findall(r'\[.*?\]', filename_lower)) >= 2:
            return True
    
    # Check for common anime keywords
    for keyword in ANIME_KEYWORDS:
        if keyword.lower() in filename_lower:
            return True
    
    # Check for common anime studios
    for studio in ANIME_STUDIOS:
        if studio.lower() in filename_lower:
            return True
    
    return False


def get_anime_folder(is_tv: bool) -> Optional[str]:
    """
    Get the appropriate anime folder.
    
    Args:
        is_tv: Whether this is for TV shows or movies
        
    Returns:
        Appropriate folder name for anime content or None if anime separation is disabled
    """
    from src.config import CUSTOM_ANIME_SHOW_FOLDER, CUSTOM_ANIME_MOVIE_FOLDER
    
    if not ANIME_SEPARATION:
        return None
    
    return CUSTOM_ANIME_SHOW_FOLDER if is_tv else CUSTOM_ANIME_MOVIE_FOLDER