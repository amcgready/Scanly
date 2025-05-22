"""
Configuration module for Scanly.
Contains constants and configuration variables used throughout the application.
"""

import os
from pathlib import Path

# Base directories
BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = os.path.join(BASE_DIR, 'data')
LOG_DIR = os.path.join(BASE_DIR, 'logs')

# Ensure directories exist
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)

# TMDB API Configuration
TMDB_BASE_URL = "https://api.themoviedb.org/3"
TMDB_API_KEY = "dummy_key_for_setup"

# Logging Configuration
LOG_LEVEL = "DEBUG"
LOG_FILE = os.path.join(LOG_DIR, 'scanly.log')

# File paths
PROGRESS_FILE = os.path.join(DATA_DIR, 'progress.json')
SKIPPED_ITEMS_FILE = os.path.join(BASE_DIR, 'skipped_items.json')
ACTIVITY_LOG_FILE = os.path.join(LOG_DIR, 'activity.log')

# Default settings
DEFAULT_MONITOR_INTERVAL = 60  # Minutes
