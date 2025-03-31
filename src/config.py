import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Set default destination directory
DEFAULT_DESTINATION = os.path.expanduser("~/Media")

# Get destination directory from environment or use default
DESTINATION_DIRECTORY = os.getenv('DESTINATION_DIRECTORY', DEFAULT_DESTINATION)

def get_settings():
    """Get all settings from environment variables."""
    settings = {}
    
    # Load all environment variables that should be accessible as settings
    # Media folder structure settings
    settings['CUSTOM_SHOW_FOLDER'] = os.getenv('CUSTOM_SHOW_FOLDER', 'Shows')
    settings['CUSTOM_MOVIE_FOLDER'] = os.getenv('CUSTOM_MOVIE_FOLDER', 'Movies')
    settings['CUSTOM_4KSHOW_FOLDER'] = os.getenv('CUSTOM_4KSHOW_FOLDER', '4K Shows')
    settings['CUSTOM_4KMOVIE_FOLDER'] = os.getenv('CUSTOM_4KMOVIE_FOLDER', '4K Movies')
    settings['CUSTOM_ANIME_SHOW_FOLDER'] = os.getenv('CUSTOM_ANIME_SHOW_FOLDER', 'Anime')
    settings['CUSTOM_ANIME_MOVIE_FOLDER'] = os.getenv('CUSTOM_ANIME_MOVIE_FOLDER', 'Anime Movies')
    
    # Anime Detection Settings
    settings['ANIME_SCAN'] = os.getenv('ANIME_SCAN', '').lower() not in ['false', '0', 'no', 'n', 'f']
    settings['ANIME_SEPARATION'] = os.getenv('ANIME_SEPARATION', '').lower() not in ['false', '0', 'no', 'n', 'f']
    
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
    
    return settings