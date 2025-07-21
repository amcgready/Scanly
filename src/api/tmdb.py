"""
TMDB API client.

This module provides functionality for interacting with The Movie Database API.
"""

import requests
from typing import List, Dict, Any, Optional

from src.config import TMDB_API_KEY, TMDB_BASE_URL
from src.utils.logger import get_logger

logger = get_logger(__name__)


class TMDB:
    """
    Client for The Movie Database API.
    """
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the TMDB client.
        
        Args:
            api_key: TMDB API key. If None, uses the value from settings.
        """
        self.api_key = api_key or TMDB_API_KEY
        self.base_url = TMDB_BASE_URL
        
        if not self.api_key:
            logger.warning("TMDB API key not set. API requests will fail.")
    
    def _request(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Make a request to the TMDB API.
        
        Args:
            endpoint: API endpoint
            params: Query parameters
            
        Returns:
            JSON response as a dictionary
        """
        url = f"{self.base_url}/{endpoint}"
        
        # Ensure params is a dictionary
        if params is None:
            params = {}
        
        # Add API key
        params['api_key'] = self.api_key
        
        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()  # Raise exception for non-200 status codes
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Error making TMDB API request to {endpoint}: {e}")
            return {"results": []}
    
    def search_movie(self, query: str, year: Optional[str] = None, limit: int = 3) -> List[Dict[str, Any]]:
        """
        Search for movies.
        
        Args:
            query: Search query
            year: Optional year to filter results
            limit: Maximum number of results to return
            
        Returns:
            List of movie results
        """
        params = {'query': query}
        if year:
            params['year'] = year
        results = self._request('search/movie', params)
        return results.get('results', [])[:limit]
    
    def search_tv(self, query: str, year: Optional[str] = None, limit: int = 3) -> List[Dict[str, Any]]:
        """
        Search for TV shows.
        
        Args:
            query: Search query
            year: Optional year to filter results (uses first_air_date_year)
            limit: Maximum number of results to return
            
        Returns:
            List of TV show results
        """
        params = {'query': query}
        if year:
            params['first_air_date_year'] = year
        results = self._request('search/tv', params)
        return results.get('results', [])[:limit]
    
    def get_movie_details(self, movie_id: int) -> Dict[str, Any]:
        """
        Get details for a movie.
        
        Args:
            movie_id: TMDB movie ID
            
        Returns:
            Movie details
        """
        return self._request(f'movie/{movie_id}')
    
    def get_tv_details(self, show_id: int) -> Dict[str, Any]:
        """
        Get details for a TV show.
        
        Args:
            show_id: TMDB show ID
            
        Returns:
            TV show details
        """
        return self._request(f'tv/{show_id}')
    
    def get_tv_season(self, show_id: int, season_number: int) -> Dict[str, Any]:
        """
        Get details for a TV season.
        
        Args:
            show_id: TMDB show ID
            season_number: Season number
            
        Returns:
            Season details
        """
        return self._request(f'tv/{show_id}/season/{season_number}')
    
    def get_movie_external_ids(self, movie_id: int) -> Dict[str, Any]:
        """
        Get external IDs for a movie.
        
        Args:
            movie_id: TMDB movie ID
            
        Returns:
            External IDs (IMDb, etc.)
        """
        return self._request(f'movie/{movie_id}/external_ids')
    
    def get_tv_external_ids(self, show_id: int) -> Dict[str, Any]:
        """
        Get external IDs for a TV show.
        
        Args:
            show_id: TMDB show ID
            
        Returns:
            External IDs (IMDb, TVDb, etc.)
        """
        return self._request(f'tv/{show_id}/external_ids')


def format_movie_result(movie: Dict[str, Any]) -> str:
    """
    Format a movie result for display to the user.
    
    Args:
        movie: Movie data from TMDB API
        
    Returns:
        Formatted string with movie information
    """
    title = movie.get("title", "Unknown Title")
    year = movie.get("release_date", "")[:4] if movie.get("release_date") else "Unknown Year"
    
    return f"{title} ({year})"


def format_tv_result(show: Dict[str, Any]) -> str:
    """
    Format a TV show result for display to the user.
    
    Args:
        show: TV show data from TMDB API
        
    Returns:
        Formatted string with TV show information
    """
    name = show.get("name", "Unknown Title")
    year = show.get("first_air_date", "")[:4] if show.get("first_air_date") else "Unknown Year"
    
    return f"{name} ({year})"