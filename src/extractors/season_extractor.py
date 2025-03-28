"""
Season extraction functionality for Scanly.

This module contains functions for extracting season numbers
from filenames and directory names.
"""

import re
from typing import Optional


def extract_season(filename: str) -> Optional[int]:
    """
    Extract the season number from a filename or directory name.
    
    Args:
        filename: Name of the file or directory
        
    Returns:
        Extracted season number as int, or None if not found
    """
    # Common patterns for season numbers
    patterns = [
        # S01, S01E01
        (r'S(\d{1,2})(?:E\d{1,2})?', lambda m: int(m.group(1))),
        
        # Season 1, Season 01
        (r'Season[.\s_-]*(\d{1,2})', lambda m: int(m.group(1))),
        
        # season 1, season 01
        (r'season[.\s_-]*(\d{1,2})', lambda m: int(m.group(1))),
        
        # Seasonx1, Seasonx01
        (r'Season[.\s_-]*x(\d{1,2})', lambda m: int(m.group(1))),
        
        # Directory patterns like "The Show - Season 1" or "The Show/Season 1"
        (r'[/\\-][.\s_]*Season[.\s_-]*(\d{1,2})', lambda m: int(m.group(1))),
        
        # Explicit naming like "S1" or "s01"
        (r'\bS(\d{1,2})\b', lambda m: int(m.group(1))),
        
        # Pattern like "1x01" where 1 is season, 01 is episode
        (r'(\d{1,2})x\d{2}', lambda m: int(m.group(1))),
        
        # Pattern for season directories like "Season 1" or just "1"
        (r'^Season[.\s_-]*(\d{1,2})$', lambda m: int(m.group(1))),
        (r'^(\d{1,2})$', lambda m: int(m.group(1))),
    ]
    
    # Try all patterns
    for pattern, extractor in patterns:
        match = re.search(pattern, filename, re.IGNORECASE)
        if match:
            try:
                season_num = extractor(match)
                if 0 <= season_num <= 100:  # Reasonable range check
                    return season_num
            except (ValueError, IndexError):
                continue
    
    return None


def extract_all_seasons(filename: str) -> list[int]:
    """
    Extract all potential season numbers from a filename.
    
    Args:
        filename: Name of the file or directory
        
    Returns:
        List of all potential season numbers found
    """
    # Common patterns for season numbers
    patterns = [
        # S01, S01E01
        r'S(\d{1,2})(?:E\d{1,2})?',
        
        # Season 1, Season 01
        r'Season[.\s_-]*(\d{1,2})',
        
        # season 1, season 01
        r'season[.\s_-]*(\d{1,2})',
        
        # Seasonx1, Seasonx01
        r'Season[.\s_-]*x(\d{1,2})',
        
        # Directory patterns like "The Show - Season 1" or "The Show/Season 1"
        r'[/\\-][.\s_]*Season[.\s_-]*(\d{1,2})',
        
        # Explicit naming like "S1" or "s01"
        r'\bS(\d{1,2})\b',
        
        # Pattern like "1x01" where 1 is season, 01 is episode
        r'(\d{1,2})x\d{2}',
    ]
    
    season_numbers = []
    
    # Try all patterns
    for pattern in patterns:
        for match in re.finditer(pattern, filename, re.IGNORECASE):
            try:
                season_num = int(match.group(1))
                if 0 <= season_num <= 100 and season_num not in season_numbers:  # Reasonable range check
                    season_numbers.append(season_num)
            except (ValueError, IndexError):
                continue
    
    return season_numbers