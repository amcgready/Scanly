"""
Configuration settings for Scanly.

This module loads configuration from the .env file and
defines constants used throughout the application.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
env_path = Path(__file__).parents[2] / '.env'
load_dotenv(dotenv_path=env_path)

# API Settings
TMDB_API_KEY = os.getenv('TMDB_API_KEY', '')
TMDB_BASE_URL = os.getenv('TMDB_BASE_URL', 'https://api.themoviedb.org/3')

# File System Settings
ORIGIN_DIRECTORY = os.getenv('ORIGIN_DIRECTORY', str(Path.home() / 'media'))
DESTINATION_DIRECTORY = os.getenv('DESTINATION_DIRECTORY', str(Path.home() / 'library'))

# Custom Folder Structure
CUSTOM_SHOW_FOLDER = os.getenv('CUSTOM_SHOW_FOLDER', 'TV Shows')
CUSTOM_4KSHOW_FOLDER = os.getenv('CUSTOM_4KSHOW_FOLDER', '')
CUSTOM_ANIME_SHOW_FOLDER = os.getenv('CUSTOM_ANIME_SHOW_FOLDER', 'Anime Shows')
CUSTOM_MOVIE_FOLDER = os.getenv('CUSTOM_MOVIE_FOLDER', 'Movies')
CUSTOM_4KMOVIE_FOLDER = os.getenv('CUSTOM_4KMOVIE_FOLDER', '')
CUSTOM_ANIME_MOVIE_FOLDER = os.getenv('CUSTOM_ANIME_MOVIE_FOLDER', 'Anime Movies')

# Resolution-based Organization
SHOW_RESOLUTION_STRUCTURE = os.getenv('SHOW_RESOLUTION_STRUCTURE', 'false').lower() == 'true'
MOVIE_RESOLUTION_STRUCTURE = os.getenv('MOVIE_RESOLUTION_STRUCTURE', 'false').lower() == 'true'

# Show Resolution Folder Mappings
SHOW_RESOLUTION_FOLDER_REMUX_4K = os.getenv('SHOW_RESOLUTION_FOLDER_REMUX_4K', 'UltraHDRemuxShows')
SHOW_RESOLUTION_FOLDER_REMUX_1080P = os.getenv('SHOW_RESOLUTION_FOLDER_REMUX_1080P', '1080pRemuxLibrary')
SHOW_RESOLUTION_FOLDER_REMUX_DEFAULT = os.getenv('SHOW_RESOLUTION_FOLDER_REMUX_DEFAULT', 'RemuxShows')
SHOW_RESOLUTION_FOLDER_2160P = os.getenv('SHOW_RESOLUTION_FOLDER_2160P', 'UltraHD')
SHOW_RESOLUTION_FOLDER_1080P = os.getenv('SHOW_RESOLUTION_FOLDER_1080P', 'FullHD')
SHOW_RESOLUTION_FOLDER_720P = os.getenv('SHOW_RESOLUTION_FOLDER_720P', 'SDClassics')
SHOW_RESOLUTION_FOLDER_480P = os.getenv('SHOW_RESOLUTION_FOLDER_480P', 'Retro480p')
SHOW_RESOLUTION_FOLDER_DVD = os.getenv('SHOW_RESOLUTION_FOLDER_DVD', 'RetroDVD')
SHOW_RESOLUTION_FOLDER_DEFAULT = os.getenv('SHOW_RESOLUTION_FOLDER_DEFAULT', 'Shows')

# Movie Resolution Folder Mappings
MOVIE_RESOLUTION_FOLDER_REMUX_4K = os.getenv('MOVIE_RESOLUTION_FOLDER_REMUX_4K', '4KRemux')
MOVIE_RESOLUTION_FOLDER_REMUX_1080P = os.getenv('MOVIE_RESOLUTION_FOLDER_REMUX_1080P', '1080pRemux')
MOVIE_RESOLUTION_FOLDER_REMUX_DEFAULT = os.getenv('MOVIE_RESOLUTION_FOLDER_REMUX_DEFAULT', 'MoviesRemux')
MOVIE_RESOLUTION_FOLDER_2160P = os.getenv('MOVIE_RESOLUTION_FOLDER_2160P', 'UltraHD')
MOVIE_RESOLUTION_FOLDER_1080P = os.getenv('MOVIE_RESOLUTION_FOLDER_1080P', 'FullHD')
MOVIE_RESOLUTION_FOLDER_720P = os.getenv('MOVIE_RESOLUTION_FOLDER_720P', 'SDMovies')
MOVIE_RESOLUTION_FOLDER_480P = os.getenv('MOVIE_RESOLUTION_FOLDER_480P', 'Retro480p')
MOVIE_RESOLUTION_FOLDER_DVD = os.getenv('MOVIE_RESOLUTION_FOLDER_DVD', 'DVDClassics')
MOVIE_RESOLUTION_FOLDER_DEFAULT = os.getenv('MOVIE_RESOLUTION_FOLDER_DEFAULT', 'Movies')

# Anime Settings
ANIME_SCAN = os.getenv('ANIME_SCAN', 'true').lower() == 'true'
ANIME_SEPARATION = os.getenv('ANIME_SEPARATION', 'true').lower() == 'true'

# Folder ID Settings
TMDB_FOLDER_ID = os.getenv('TMDB_FOLDER_ID', 'true').lower() == 'true'
IMDB_FOLDER_ID = os.getenv('IMDB_FOLDER_ID', 'false').lower() == 'true'
TVDB_FOLDER_ID = os.getenv('TVDB_FOLDER_ID', 'false').lower() == 'true'

# Renaming Settings
RENAME_ENABLED = os.getenv('RENAME_ENABLED', 'true').lower() == 'true'
RENAME_TAGS = os.getenv('RENAME_TAGS', '')

# Collection Settings
MOVIE_COLLECTION_ENABLED = os.getenv('MOVIE_COLLECTION_ENABLED', 'false').lower() == 'true'

# System Settings
MAX_PROCESSES = int(os.getenv('MAX_PROCESSES', '1'))
RELATIVE_SYMLINK = os.getenv('RELATIVE_SYMLINK', 'false').lower() == 'true'
ALLOWED_EXTENSIONS = os.getenv('ALLOWED_EXTENSIONS', '.mp4,.mkv,.srt,.avi,.mov,.divx').split(',')
SKIP_ADULT_PATTERNS = os.getenv('SKIP_ADULT_PATTERNS', 'true').lower() == 'true'
SKIP_EXTRAS_FOLDER = os.getenv('SKIP_EXTRAS_FOLDER', 'true').lower() == 'true'
EXTRAS_MAX_SIZE_MB = int(os.getenv('EXTRAS_MAX_SIZE_MB', '30'))

# Rclone Settings
RCLONE_MOUNT = os.getenv('RCLONE_MOUNT', 'false').lower() == 'true'
MOUNT_CHECK_INTERVAL = int(os.getenv('MOUNT_CHECK_INTERVAL', '30'))

# Monitoring Settings
SLEEP_TIME = int(os.getenv('SLEEP_TIME', '1'))
SYMLINK_CLEANUP_INTERVAL = int(os.getenv('SYMLINK_CLEANUP_INTERVAL', '30'))

# Plex Integration
ENABLE_PLEX_UPDATE = os.getenv('ENABLE_PLEX_UPDATE', 'false').lower() == 'true'
PLEX_URL = os.getenv('PLEX_URL', 'http://localhost:32400')
PLEX_TOKEN = os.getenv('PLEX_TOKEN', '')

# Database Settings
DB_THROTTLE_RATE = int(os.getenv('DB_THROTTLE_RATE', '100'))
DB_MAX_RETRIES = int(os.getenv('DB_MAX_RETRIES', '10'))
DB_RETRY_DELAY = float(os.getenv('DB_RETRY_DELAY', '1.0'))
DB_BATCH_SIZE = int(os.getenv('DB_BATCH_SIZE', '1000'))
DB_MAX_WORKERS = int(os.getenv('DB_MAX_WORKERS', '4'))

# Logging Settings
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
LOG_FILE = os.getenv('LOG_FILE', 'scanly.log')

# Application Settings
AUTO_EXTRACT_EPISODES = os.getenv('AUTO_EXTRACT_EPISODES', 'True').lower() == 'true'
PROGRESS_FILE = os.getenv('PROGRESS_FILE', 'scanly_progress.json')