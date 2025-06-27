"""
Configuration module for Scanly.
"""

import os
import json

def get_settings(key=None, default=None):
    """Get settings from environment variables.
    
    Args:
        key (str, optional): Specific setting key to retrieve. If None, returns all settings.
        default (any, optional): Default value if setting is not found.
    
    Returns:
        dict or any: All settings or specific setting value
    """
    settings = {
        'destination_directory': os.environ.get('DESTINATION_DIRECTORY', ''),
        'tmdb_api_key': os.environ.get('TMDB_API_KEY', ''),
        'discord_webhook_url': os.environ.get('DISCORD_WEBHOOK_URL', ''),
        'scanner_movies': os.environ.get('SCANNER_MOVIES', 'movies.txt'),
        'scanner_tv_series': os.environ.get('SCANNER_TV_SERIES', 'tv_series.txt'),
        'scanner_anime_movies': os.environ.get('SCANNER_ANIME_MOVIES', 'anime_movies.txt'),
        'scanner_anime_series': os.environ.get('SCANNER_ANIME_SERIES', 'anime_series.txt'),
        'scanner_wrestling': os.environ.get('SCANNER_WRESTLING', 'wrestling.txt'),
        'create_missing_scanners': os.environ.get('CREATE_MISSING_SCANNERS', 'True').lower() == 'true',
        'symlink_mode': os.environ.get('SYMLINK_MODE', 'copy')
    }
    
    # Load custom content types
    custom_types_json = os.environ.get('SCANNER_CUSTOM_TYPES', '{}')
    try:
        custom_types = json.loads(custom_types_json)
        for content_type, info in custom_types.items():
            env_var = info.get('env_var')
            if env_var:
                settings[env_var.lower()] = os.environ.get(env_var, info.get('default_file', ''))
    except json.JSONDecodeError:
        pass
    
    if key is not None:
        return settings.get(key.lower(), default)
    
    return settings

TMDB_API_KEY = os.environ.get('TMDB_API_KEY', '')
TMDB_BASE_URL = "https://api.themoviedb.org/3"
