"""
API module for Scanly.

This module contains connections to external APIs used by Scanly
for media information retrieval.
"""

from src.api.tmdb import TMDB, format_movie_result, format_tv_result

# Either implement these functions in anidb.py or modify the import to match what's available
# Option 1: If AniDB class exists but not format_anime_result:
try:
    from src.api.anidb import AniDB
    __all__ = ['TMDB', 'format_movie_result', 'format_tv_result', 'AniDB']
except ImportError:
    __all__ = ['TMDB', 'format_movie_result', 'format_tv_result']

# Option 2: If neither AniDB nor format_anime_result exist yet:
# __all__ = ['TMDB', 'format_movie_result', 'format_tv_result']