"""
Configuration module for Scanly.

This module handles loading environment variables and settings.
"""

import os
from typing import Dict, Any
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# API settings
TMDB_API_KEY = os.getenv('TMDB_API_KEY', '')
TMDB_BASE_URL = os.getenv('TMDB_BASE_URL', 'https://api.themoviedb.org/3')
MDBLIST_API_KEY = os.getenv('MDBLIST_API_KEY', '')

# File System Settings
DESTINATION_DIRECTORY = os.getenv('DESTINATION_DIRECTORY', '')

# Link settings
LINK_TYPE = os.getenv('LINK_TYPE', 'symlink')
RELATIVE_SYMLINK = os.getenv('RELATIVE_SYMLINK', 'false').lower() in ('true', 'yes', '1', 'y')

# Custom Folder Structure
CUSTOM_SHOW_FOLDER = os.getenv('CUSTOM_SHOW_FOLDER', 'TV Shows')
CUSTOM_4KSHOW_FOLDER = os.getenv('CUSTOM_4KSHOW_FOLDER', '')
CUSTOM_ANIME_SHOW_FOLDER = os.getenv('CUSTOM_ANIME_SHOW_FOLDER', 'Anime Shows')
CUSTOM_MOVIE_FOLDER = os.getenv('CUSTOM_MOVIE_FOLDER', 'Movies')
CUSTOM_4KMOVIE_FOLDER = os.getenv('CUSTOM_4KMOVIE_FOLDER', '')
CUSTOM_ANIME_MOVIE_FOLDER = os.getenv('CUSTOM_ANIME_MOVIE_FOLDER', 'Anime Movies')

# Resolution-based Organization
SHOW_RESOLUTION_STRUCTURE = os.getenv('SHOW_RESOLUTION_STRUCTURE', 'false').lower() in ('true', 'yes', '1', 'y')
MOVIE_RESOLUTION_STRUCTURE = os.getenv('MOVIE_RESOLUTION_STRUCTURE', 'false').lower() in ('true', 'yes', '1', 'y')

# Anime Settings
ANIME_SCAN = os.getenv('ANIME_SCAN', 'true').lower() in ('true', 'yes', '1', 'y')
ANIME_SEPARATION = os.getenv('ANIME_SEPARATION', 'true').lower() in ('true', 'yes', '1', 'y')

# Scanner Settings
SCANNER_ENABLED = os.getenv('SCANNER_ENABLED', 'true').lower() in ('true', 'yes', '1', 'y')
SCANNER_PRIORITY = os.getenv('SCANNER_PRIORITY', 'true').lower() in ('true', 'yes', '1', 'y')

# Folder ID Settings
TMDB_FOLDER_ID = os.getenv('TMDB_FOLDER_ID', 'true').lower() in ('true', 'yes', '1', 'y')
IMDB_FOLDER_ID = os.getenv('IMDB_FOLDER_ID', 'false').lower() in ('true', 'yes', '1', 'y')
TVDB_FOLDER_ID = os.getenv('TVDB_FOLDER_ID', 'false').lower() in ('true', 'yes', '1', 'y')

# Application Settings
AUTO_EXTRACT_EPISODES = os.getenv('AUTO_EXTRACT_EPISODES', 'true').lower() in ('true', 'yes', '1', 'y')
PROGRESS_FILE = os.getenv('PROGRESS_FILE', 'scanly_progress.json')

# Discord settings
DISCORD_WEBHOOK_URL = os.getenv('DISCORD_WEBHOOK_URL', '')
ENABLE_DISCORD_NOTIFICATIONS = os.getenv('ENABLE_DISCORD_NOTIFICATIONS', 'false').lower() in ('true', 'yes', '1', 'y')
MONITOR_SCAN_INTERVAL = int(os.getenv('MONITOR_SCAN_INTERVAL', '60'))

# Logging Settings
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
LOG_FILE = os.getenv('LOG_FILE', 'scanly.log')

def get_settings() -> Dict[str, Any]:
    """
    Get application settings from environment variables.
    
    Returns:
        Dictionary of settings
    """
    settings = {
        'TMDB_API_KEY': TMDB_API_KEY,
        'TMDB_BASE_URL': TMDB_BASE_URL,
        'MDBLIST_API_KEY': MDBLIST_API_KEY,
        
        'DESTINATION_DIRECTORY': DESTINATION_DIRECTORY,
        
        'LINK_TYPE': LINK_TYPE,
        'RELATIVE_SYMLINK': RELATIVE_SYMLINK,
        
        'CUSTOM_SHOW_FOLDER': CUSTOM_SHOW_FOLDER,
        'CUSTOM_4KSHOW_FOLDER': CUSTOM_4KSHOW_FOLDER,
        'CUSTOM_ANIME_SHOW_FOLDER': CUSTOM_ANIME_SHOW_FOLDER,
        'CUSTOM_MOVIE_FOLDER': CUSTOM_MOVIE_FOLDER,
        'CUSTOM_4KMOVIE_FOLDER': CUSTOM_4KMOVIE_FOLDER,
        'CUSTOM_ANIME_MOVIE_FOLDER': CUSTOM_ANIME_MOVIE_FOLDER,
        
        'SHOW_RESOLUTION_STRUCTURE': SHOW_RESOLUTION_STRUCTURE,
        'MOVIE_RESOLUTION_STRUCTURE': MOVIE_RESOLUTION_STRUCTURE,
        
        'ANIME_SCAN': ANIME_SCAN,
        'ANIME_SEPARATION': ANIME_SEPARATION,
        
        'SCANNER_ENABLED': SCANNER_ENABLED,
        'SCANNER_PRIORITY': SCANNER_PRIORITY,
        
        'TMDB_FOLDER_ID': TMDB_FOLDER_ID,
        'IMDB_FOLDER_ID': IMDB_FOLDER_ID,
        'TVDB_FOLDER_ID': TVDB_FOLDER_ID,
        
        'AUTO_EXTRACT_EPISODES': AUTO_EXTRACT_EPISODES,
        'PROGRESS_FILE': PROGRESS_FILE,
        
        'DISCORD_WEBHOOK_URL': DISCORD_WEBHOOK_URL,
        'ENABLE_DISCORD_NOTIFICATIONS': ENABLE_DISCORD_NOTIFICATIONS,
        'MONITOR_SCAN_INTERVAL': MONITOR_SCAN_INTERVAL,
        
        'LOG_LEVEL': LOG_LEVEL,
        'LOG_FILE': LOG_FILE
    }
    
    return settings
