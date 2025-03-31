"""
Utility functions for extracting media information.

This module provides functions for detecting video resolution,
codecs, and other media properties.
"""

import os
import re
from pathlib import Path
from typing import Optional, Tuple

from src.utils.logger import get_logger

logger = get_logger(__name__)


def detect_resolution(file_path: str) -> Optional[str]:
    """
    Detect the resolution from a filename.
    
    Args:
        file_path: Path to the media file
        
    Returns:
        Resolution identifier or None if resolution can't be determined
    """
    filename = os.path.basename(file_path).lower()
    
    # Common resolution patterns in filenames
    if any(x in filename for x in ['2160p', '4k', 'uhd', '4kuhd', 'ultrahd']):
        return '2160p'
    elif any(x in filename for x in ['1080p', 'fullhd', 'fhd']):
        return '1080p'
    elif any(x in filename for x in ['720p', 'hd']):
        return '720p'
    elif any(x in filename for x in ['480p', 'sdtv', 'sd']):
        return '480p'
    elif any(x in filename for x in ['dvd', 'ntsc', 'pal']):
        return 'dvd'
    
    # No resolution info found
    return None


def detect_remux(file_path: str) -> bool:
    """
    Detect if a file is a remux.
    
    Args:
        file_path: Path to the media file
        
    Returns:
        True if the file appears to be a remux, False otherwise
    """
    filename = os.path.basename(file_path).lower()
    
    return bool(re.search(r'\bremux\b', filename))


def get_resolution_folder(file_path: str, is_tv: bool = False) -> str:
    """
    Get the appropriate resolution-based folder for a file.
    
    Args:
        file_path: Path to the media file
        is_tv: Whether the file is a TV show or movie
        
    Returns:
        The appropriate folder name based on resolution
    """
    from src.config import (
        SHOW_RESOLUTION_STRUCTURE, MOVIE_RESOLUTION_STRUCTURE,
        SHOW_RESOLUTION_FOLDER_REMUX_4K, SHOW_RESOLUTION_FOLDER_REMUX_1080P,
        SHOW_RESOLUTION_FOLDER_REMUX_DEFAULT, SHOW_RESOLUTION_FOLDER_2160P,
        SHOW_RESOLUTION_FOLDER_1080P, SHOW_RESOLUTION_FOLDER_720P,
        SHOW_RESOLUTION_FOLDER_480P, SHOW_RESOLUTION_FOLDER_DVD,
        SHOW_RESOLUTION_FOLDER_DEFAULT, MOVIE_RESOLUTION_FOLDER_REMUX_4K,
        MOVIE_RESOLUTION_FOLDER_REMUX_1080P, MOVIE_RESOLUTION_FOLDER_REMUX_DEFAULT,
        MOVIE_RESOLUTION_FOLDER_2160P, MOVIE_RESOLUTION_FOLDER_1080P,
        MOVIE_RESOLUTION_FOLDER_720P, MOVIE_RESOLUTION_FOLDER_480P,
        MOVIE_RESOLUTION_FOLDER_DVD, MOVIE_RESOLUTION_FOLDER_DEFAULT,
        CUSTOM_SHOW_FOLDER, CUSTOM_MOVIE_FOLDER
    )
    
    # If resolution-based structure is disabled, return the default folder
    if (is_tv and not SHOW_RESOLUTION_STRUCTURE) or (not is_tv and not MOVIE_RESOLUTION_STRUCTURE):
        return CUSTOM_SHOW_FOLDER if is_tv else CUSTOM_MOVIE_FOLDER
    
    is_remux = detect_remux(file_path)
    resolution = detect_resolution(file_path)
    
    if is_tv:
        # TV Show resolution folders
        if is_remux:
            if resolution == '2160p':
                return SHOW_RESOLUTION_FOLDER_REMUX_4K
            elif resolution == '1080p':
                return SHOW_RESOLUTION_FOLDER_REMUX_1080P
            else:
                return SHOW_RESOLUTION_FOLDER_REMUX_DEFAULT
        
        if resolution == '2160p':
            return SHOW_RESOLUTION_FOLDER_2160P
        elif resolution == '1080p':
            return SHOW_RESOLUTION_FOLDER_1080P
        elif resolution == '720p':
            return SHOW_RESOLUTION_FOLDER_720P
        elif resolution == '480p':
            return SHOW_RESOLUTION_FOLDER_480P
        elif resolution == 'dvd':
            return SHOW_RESOLUTION_FOLDER_DVD
        else:
            return SHOW_RESOLUTION_FOLDER_DEFAULT
    else:
        # Movie resolution folders
        if is_remux:
            if resolution == '2160p':
                return MOVIE_RESOLUTION_FOLDER_REMUX_4K
            elif resolution == '1080p':
                return MOVIE_RESOLUTION_FOLDER_REMUX_1080P
            else:
                return MOVIE_RESOLUTION_FOLDER_REMUX_DEFAULT
        
        if resolution == '2160p':
            return MOVIE_RESOLUTION_FOLDER_2160P
        elif resolution == '1080p':
            return MOVIE_RESOLUTION_FOLDER_1080P
        elif resolution == '720p':
            return MOVIE_RESOLUTION_FOLDER_720P
        elif resolution == '480p':
            return MOVIE_RESOLUTION_FOLDER_480P
        elif resolution == 'dvd':
            return MOVIE_RESOLUTION_FOLDER_DVD
        else:
            return MOVIE_RESOLUTION_FOLDER_DEFAULT