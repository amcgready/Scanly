"""
Configuration module for Scanly.

This module defines application-wide configuration settings.
"""

from .settings import *

# Add these lines to import AniDB settings

# AniDB API settings
ANIDB_CLIENT_NAME = os.getenv('ANIDB_CLIENT_NAME', 'scanly')
ANIDB_CLIENT_VERSION = os.getenv('ANIDB_CLIENT_VERSION', '1')
ANIDB_API_KEY = os.getenv('ANIDB_API_KEY', '')
ANIDB_API_ENABLED = os.getenv('ANIDB_API_ENABLED', 'false').lower() in ('true', 'yes', '1', 'y', 't')