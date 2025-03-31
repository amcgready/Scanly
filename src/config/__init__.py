"""
Configuration module for Scanly.

This module defines application-wide configuration settings.
"""

from .settings import *

# Add to the existing settings loading code

# AniDB settings
ANIME_SCAN = os.getenv('ANIME_SCAN', 'true').lower() in ('true', 'yes', '1', 'y')
ANIME_SEPARATION = os.getenv('ANIME_SEPARATION', 'true').lower() in ('true', 'yes', '1', 'y')
ANIDB_CLIENT_NAME = os.getenv('ANIDB_CLIENT_NAME', 'scanly')
ANIDB_CLIENT_VERSION = os.getenv('ANIDB_CLIENT_VERSION', '1')
ANIDB_API_KEY = os.getenv('ANIDB_API_KEY', '')
ANIDB_API_ENABLED = os.getenv('ANIDB_API_ENABLED', 'false').lower() in ('true', 'yes', '1', 'y')

def get_settings():
    """Get all settings as a dictionary."""
    # Convert all module-level variables to a dictionary
    settings = {}
    for var in dir():
        if not var.startswith('__') and var.isupper():
            settings[var] = globals()[var]
    return settings
