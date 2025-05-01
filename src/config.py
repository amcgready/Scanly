"""
Configuration module for Scanly.

This module handles configuration settings for the application.
"""

import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Set default destination directory
DEFAULT_DESTINATION = os.path.expanduser("~/Media")

# Get destination directory from environment or use default
DESTINATION_DIRECTORY = os.getenv('DESTINATION_DIRECTORY', DEFAULT_DESTINATION)

def get_settings():
    """Get application settings."""
    load_dotenv()
    
    settings = {
        # Media folder structure settings
        'CUSTOM_SHOW_FOLDER': os.getenv('CUSTOM_SHOW_FOLDER', 'Shows'),
        'CUSTOM_MOVIE_FOLDER': os.getenv('CUSTOM_MOVIE_FOLDER', 'Movies'),
        'CUSTOM_4KSHOW_FOLDER': os.getenv('CUSTOM_4KSHOW_FOLDER', '4K Shows'),
        'CUSTOM_4KMOVIE_FOLDER': os.getenv('CUSTOM_4KMOVIE_FOLDER', '4K Movies'),
        'CUSTOM_ANIME_SHOW_FOLDER': os.getenv('CUSTOM_ANIME_SHOW_FOLDER', 'Anime'),
        'CUSTOM_ANIME_MOVIE_FOLDER': os.getenv('CUSTOM_ANIME_MOVIE_FOLDER', 'Anime Movies'),
        
        # Anime Detection Settings
        'ANIME_SCAN': os.getenv('ANIME_SCAN', '').lower() not in ['false', '0', 'no', 'n', 'f'],
        'ANIME_SEPARATION': os.getenv('ANIME_SEPARATION', '').lower() not in ['false', '0', 'no', 'n', 'f']
    }
    
    # Process additional environment variables
    for key, value in os.environ.items():
        # Skip keys we've already processed
        if key in settings:
            continue
        
        # Skip AniDB-related keys
        if key.startswith('ANIDB_'):
            continue
            
        # Convert string boolean values to Python booleans
        if isinstance(value, str):
            if value.lower() in ('true', 'yes', 'y', 't', '1'):
                settings[key] = True
            elif value.lower() in ('false', 'no', 'n', 'f', '0'):
                settings[key] = False
            else:
                # Keep other values as strings
                settings[key] = value
        else:
            # Non-string values (shouldn't happen with os.environ but just in case)
            settings[key] = value
    
    # Add monitor settings
    monitor_settings = get_monitor_settings()
    settings.update(monitor_settings)
    
    return settings

def get_monitor_settings():
    """Get monitoring-related settings."""
    load_dotenv()
    
    # Define monitor settings
    MONITOR_SETTINGS = {
        'MONITOR_AUTO_PROCESS': {
            'name': 'MONITOR_AUTO_PROCESS',
            'description': 'Automatically process new files in monitored directories',
            'type': 'bool',
            'category': 'Monitoring',
            'default': 'false'
        },
        'MONITOR_SCAN_INTERVAL': {
            'name': 'MONITOR_SCAN_INTERVAL',
            'description': 'Interval in seconds between monitor scans',
            'type': 'number',
            'category': 'Monitoring',
            'default': '15'
        }
    }
    
    settings = {}
    for key, setting in MONITOR_SETTINGS.items():
        settings[key] = os.environ.get(key, setting['default'])
    
    return settings

def _update_env_var(name, value):
    """Update an environment variable both in memory and in .env file."""
    # Update in memory
    os.environ[name] = value
    
    # Update in .env file
    try:
        env_path = os.path.join(os.path.dirname(__file__), '..', '.env')
        
        # Read existing content
        if os.path.exists(env_path):
            with open(env_path, 'r') as f:
                lines = f.readlines()
        else:
            lines = []
        
        # Check if the variable already exists in the file
        var_exists = False
        for i, line in enumerate(lines):
            if line.strip().startswith(f"{name}="):
                lines[i] = f"{name}={value}\n"
                var_exists = True
                break
        
        # Add the variable if it doesn't exist
        if not var_exists:
            lines.append(f"{name}={value}\n")
        
        # Write the updated content back to the file
        with open(env_path, 'w') as f:
            f.writelines(lines)
        
        return True
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Error updating environment variable: {e}")
        return False