"""
Episode extraction functionality for Scanly.

This module contains functions for extracting episode numbers
from filenames.
"""

import re
from typing import Optional, List


def extract_episode(filename: str) -> Optional[int]:
    """
    Extract the episode number from a filename.
    
    Args:
        filename: Name of the file
        
    Returns:
        Extracted episode number as int, or None if not found
    """
    # Common patterns for episode numbers
    patterns = [
        # S01E01, S1E1
        (r'S\d{1,2}E(\d{1,2})', lambda m: int(m.group(1))),
        
        # 1x01, 01x01
        (r'\d{1,2}x(\d{1,2})', lambda m: int(m.group(1))),
        
        # Episode 1, Episode 01
        (r'Episode[.\s_-]*(\d{1,2})', lambda m: int(m.group(1))),
        
        # episode 1, episode 01
        (r'episode[.\s_-]*(\d{1,2})', lambda m: int(m.group(1))),
        
        # ep1, ep01, ep 1, ep 01
        (r'ep[.\s_-]*(\d{1,2})', lambda m: int(m.group(1))),
        
        # e1, e01, E1, E01
        (r'e(\d{1,2})', lambda m: int(m.group(1))),
        (r'E(\d{1,2})', lambda m: int(m.group(1))),
        
        # Pattern like ".101." where 1 is season, 01 is episode
        (r'\.(\d)(\d{2})\.', lambda m: int(m.group(2))),
        
        # File names ending in episode number like "Show Name - 01"
        (r'[.\s_-](\d{1,2})$', lambda m: int(m.group(1))),
    ]
    
    # Try all patterns
    for pattern, extractor in patterns:
        match = re.search(pattern, filename)
        if match:
            try:
                episode_num = extractor(match)
                if 0 < episode_num <= 100:  # Reasonable range check
                    return episode_num
            except (ValueError, IndexError):
                continue
    
    return None


def extract_all_episodes(filename: str) -> List[int]:
    """
    Extract all potential episode numbers from a filename.
    
    Args:
        filename: Name of the file
        
    Returns:
        List of all potential episode numbers found
    """
    # Common patterns for episode numbers
    patterns = [
        # S01E01, S1E1
        r'S\d{1,2}E(\d{1,2})',
        
        # 1x01, 01x01
        r'\d{1,2}x(\d{1,2})',
        
        # Episode 1, Episode 01
        r'Episode[.\s_-]*(\d{1,2})',
        
        # episode 1, episode 01
        r'episode[.\s_-]*(\d{1,2})',
        
        # ep1, ep01, ep 1, ep 01
        r'ep[.\s_-]*(\d{1,2})',
        
        # e1, e01, E1, E01
        r'e(\d{1,2})',
        r'E(\d{1,2})',
        
        # Pattern like ".101." where 1 is season, 01 is episode
        r'\.(\d)(\d{2})\.',
        
        # File names ending in episode number like "Show Name - 01"
        r'[.\s_-](\d{1,2})$',
    ]
    
    episode_numbers = []
    
    # Try all patterns
    for pattern in patterns:
        for match in re.finditer(pattern, filename):
            try:
                if '.' in pattern and len(match.groups()) > 1:
                    # Handle the special case for patterns like .101. where we want group(2)
                    episode_num = int(match.group(2))
                else:
                    episode_num = int(match.group(1))
                
                if 0 < episode_num <= 100 and episode_num not in episode_numbers:  # Reasonable range check
                    episode_numbers.append(episode_num)
            except (ValueError, IndexError):
                continue
    
    return episode_numbers


def extract_multi_episode(filename: str) -> List[int]:
    """
    Extract multiple episode numbers for multi-episode files.
    
    Args:
        filename: Name of the file
        
    Returns:
        List of episode numbers for multi-episode files
    """
    # Patterns for multi-episode files
    patterns = [
        # S01E01E02, S01E01-E02
        r'S\d{1,2}E(\d{1,2})[-E]E?(\d{1,2})',
        
        # S01E01-02
        r'S\d{1,2}E(\d{1,2})-(\d{1,2})',
        
        # 1x01-02, 1x01x02
        r'\d{1,2}x(\d{1,2})[-x](\d{1,2})',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, filename)
        if match:
            try:
                start_ep = int(match.group(1))
                end_ep = int(match.group(2))
                
                # Ensure end episode is greater than start episode
                if end_ep > start_ep and start_ep > 0 and end_ep <= 100:
                    return list(range(start_ep, end_ep + 1))
            except (ValueError, IndexError):
                continue
    
    # If no multi-episode pattern found, try to get at least a single episode
    single_ep = extract_episode(filename)
    return [single_ep] if single_ep is not None else []