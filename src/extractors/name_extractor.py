"""
Name extraction functionality for Scanly.

This module contains functions for extracting show or movie names
from filenames and directory names.
"""

import os
import re
from typing import Optional


def extract_name(filename: str) -> str:
    """
    Extract the show or movie name from a filename or directory name.
    
    Args:
        filename: Name of the file or directory
        
    Returns:
        Extracted name, cleaned and formatted
    """
    # Remove file extension if present
    base_name = os.path.splitext(filename)[0]
    
    # Replace dots, underscores, and excess spaces with a single space
    cleaned_name = re.sub(r'[._]+', ' ', base_name)
    
    # Common patterns to remove from filenames
    patterns = [
        # Season and episode patterns
        r'S\d{1,2}E\d{1,2}',  # S01E01
        r'S\d{1,2}',          # S01
        r'E\d{1,2}',          # E01
        r'Season \d{1,2}',    # Season 01
        r'Episode \d{1,2}',   # Episode 01
        
        # Year patterns
        r'\(\d{4}\)',         # (2020)
        r'\[\d{4}\]',         # [2020]
        r'\d{4}',             # 2020
        
        # Resolution patterns
        r'\d{3,4}p',          # 720p, 1080p
        r'\d+x\d+',           # 1280x720
        r'HD|UHD|FHD|QHD|4K|8K',
        
        # Quality and encoding patterns
        r'HDTV|BluRay|WEB-DL|WEBRip|BRRip|DVDRip',
        r'x264|x265|HEVC|XviD|DivX|H264|H265',
        r'AC3|AAC|MP3|DTS|FLAC',
        
        # Source patterns
        r'AMZN|HULU|DSNP|NETFLIX|NF|HMAX',
        
        # Release group patterns (in brackets or after a hyphen)
        r'\[.+?\]',           # [GROUP]
        r'-.+?$',             # -GROUP
        
        # Other common patterns
        r'REPACK|PROPER|EXTENDED|UNRATED|THEATRICAL|DIRECTORS|CUT',
        r'COMPLETE|LIMITED|INTERNAL|DUBBED|SUBBED|REMUX',
    ]
    
    # Apply all patterns
    for pattern in patterns:
        cleaned_name = re.sub(pattern, '', cleaned_name, flags=re.IGNORECASE)
    
    # Remove leading/trailing punctuation and whitespace
    cleaned_name = re.sub(r'^[\s\-\.]+|[\s\-\.]+$', '', cleaned_name)
    
    # Remove extra spaces
    cleaned_name = re.sub(r'\s+', ' ', cleaned_name).strip()
    
    return cleaned_name


def extract_name_with_year(filename: str) -> tuple[str, Optional[str]]:
    """
    Extract the show or movie name along with its year from a filename.
    
    Args:
        filename: Name of the file or directory
        
    Returns:
        Tuple of (extracted name, year) where year can be None if not found
    """
    # Try to find year pattern like (2020) or [2020]
    year_match = re.search(r'[\(\[\s](\d{4})[\)\]\s]', filename)
    year = year_match.group(1) if year_match else None
    
    # Extract name
    name = extract_name(filename)
    
    return name, year