"""
API module for Scanly.

This module contains connections to external APIs used by Scanly
for media information retrieval.
"""

from src.api.tmdb import TMDB, format_movie_result, format_tv_result

# Import AniDB, but handle if it's not fully implemented yet
try:
    from src.api.anidb import AniDB, format_anime_result
    __all__ = ['TMDB', 'format_movie_result', 'format_tv_result', 'AniDB', 'format_anime_result']
except ImportError:
    __all__ = ['TMDB', 'format_movie_result', 'format_tv_result']