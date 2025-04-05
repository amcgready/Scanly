"""
Configuration module for Scanly.

This module defines application-wide configuration settings.
"""

# Configuration module

# Import necessary modules
import os
import sys
import logging

from .settings import *

# Add to the existing settings loading code

# AniDB settings
ANIME_SCAN = os.getenv('ANIME_SCAN', 'true').lower() in ('true', 'yes', '1', 'y')
ANIME_SEPARATION = os.getenv('ANIME_SEPARATION', 'true').lower() in ('true', 'yes', '1', 'y')
ANIDB_CLIENT_NAME = os.getenv('ANIDB_CLIENT_NAME', 'scanly')
ANIDB_CLIENT_VERSION = os.getenv('ANIDB_CLIENT_VERSION', '1')
ANIDB_API_KEY = os.getenv('ANIDB_API_KEY', '')
ANIDB_API_ENABLED = os.getenv('ANIDB_API_ENABLED', 'false').lower() in ('true', 'yes', '1', 'y')

# Define variables that will be accessible via imports
DESTINATION_DIRECTORY = os.environ.get('DESTINATION_DIRECTORY', '')
CUSTOM_MOVIE_FOLDER = os.environ.get('CUSTOM_MOVIE_FOLDER', 'Movies')
CUSTOM_SHOW_FOLDER = os.environ.get('CUSTOM_SHOW_FOLDER', 'TV Shows')
CUSTOM_ANIME_MOVIE_FOLDER = os.environ.get('CUSTOM_ANIME_MOVIE_FOLDER', 'Anime Movies')
CUSTOM_ANIME_SHOW_FOLDER = os.environ.get('CUSTOM_ANIME_SHOW_FOLDER', 'Anime Shows')
RELATIVE_SYMLINK = os.environ.get('RELATIVE_SYMLINK', 'false').lower() == 'true'
MOVIE_RESOLUTION_STRUCTURE = os.environ.get('MOVIE_RESOLUTION_STRUCTURE', 'false').lower() == 'true'
SHOW_RESOLUTION_STRUCTURE = os.environ.get('SHOW_RESOLUTION_STRUCTURE', 'false').lower() == 'true'
TMDB_API_KEY = os.environ.get('TMDB_API_KEY', '3b5df02338c403dad189e661d57e351f')
AUTO_REPAIR_SYMLINKS = os.environ.get('AUTO_REPAIR_SYMLINKS', 'false').lower() == 'true'

def update_config_variable(name, value):
    """
    Update a configuration variable in this module.
    
    Args:
        name: Name of the variable to update
        value: New value for the variable
    """
    global AUTO_REPAIR_SYMLINKS
    
    if name == 'AUTO_REPAIR_SYMLINKS':
        if isinstance(value, str):
            AUTO_REPAIR_SYMLINKS = value.lower() == 'true'
        else:
            AUTO_REPAIR_SYMLINKS = bool(value)
        return AUTO_REPAIR_SYMLINKS
    
    if name and value is not None:
        globals()[name] = value
        if name == 'AUTO_REPAIR_SYMLINKS' and isinstance(value, str):
            # Handle boolean string conversion for this specific variable
            globals()[name] = value.lower() == 'true'
    
    # Update module-level variables to match environment variables
    # This ensures consistency across imports
    return globals()[name] if name in globals() else None

def get_settings():
    """Get all settings as a dictionary."""
    # Convert all module-level variables to a dictionary
    settings = {}
    for var in dir():
        if not var.startswith('__') and var.isupper():
            settings[var] = globals()[var]
    return settings
