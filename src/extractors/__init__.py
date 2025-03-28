"""
Extractors module for Scanly.

This module contains functions for extracting metadata from filenames,
including show/movie names, season numbers, and episode numbers.
"""

from .name_extractor import extract_name
from .season_extractor import extract_season
from .episode_extractor import extract_episode