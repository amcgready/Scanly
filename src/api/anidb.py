"""
AniDB API client.

This module provides functionality for interacting with the AniDB API.
"""
import time
import re
import xml.etree.ElementTree as ET
import requests
from typing import Dict, List, Any, Optional, Union

from src.config import ANIDB_API_KEY, ANIDB_CLIENT_NAME, ANIDB_CLIENT_VERSION, ANIDB_API_ENABLED
from src.utils.logger import get_logger

logger = get_logger(__name__)

class AniDB:
    """Client for the AniDB API."""
    
    BASE_URL = "http://api.anidb.net:9001/httpapi"
    
    def __init__(self):
        """Initialize the AniDB API client."""
        self.api_key = ANIDB_API_KEY
        self.client = ANIDB_CLIENT_NAME
        self.clientver = ANIDB_CLIENT_VERSION
        self.enabled = ANIDB_API_ENABLED
        self.last_request_time = 0
        self.rate_limit = 2  # seconds between requests to avoid rate limiting
        
        if not self.enabled:
            logger.info("AniDB API is disabled in configuration")
        elif not self.api_key:
            logger.warning("AniDB API key not configured")
            self.enabled = False
    
    def search_anime(self, name: str, limit: int = 3) -> List[Dict[str, Any]]:
        """
        Search for anime by name.
        
        Args:
            name: The anime title to search for
            limit: Maximum number of results to return
            
        Returns:
            List of anime search results
        """
        if not self.enabled:
            logger.debug("AniDB API is disabled, skipping search")
            return []
            
        try:
            # Handle rate limiting
            self._respect_rate_limit()
            
            # Clean the search name
            search_term = self._clean_search_term(name)
            
            # Build the request
            params = {
                'client': self.client,
                'clientver': self.clientver,
                'protover': 1,
                'request': 'anime',
                'command': 'search',
                'query': search_term
            }
            
            # For AniDB API key, it's typically passed as a parameter
            if self.api_key:
                params['api_key'] = self.api_key
                
            response = requests.get(self.BASE_URL, params=params, timeout=10)
            
            # Update the last request time
            self.last_request_time = time.time()
            
            # Check if the response was successful
            if response.status_code != 200:
                logger.error(f"AniDB API error: {response.status_code} - {response.text}")
                return []
                
            # Parse the XML response
            root = ET.fromstring(response.text)
            
            results = []
            for anime in root.findall('.//anime'):
                anime_data = {
                    'id': anime.get('id'),
                    'name': anime.find('title').text if anime.find('title') is not None else 'Unknown',
                    'type': anime.find('type').text if anime.find('type') is not None else 'Unknown',
                    'episode_count': anime.find('episodecount').text if anime.find('episodecount') is not None else '0',
                    'start_date': anime.find('startdate').text if anime.find('startdate') is not None else None,
                    'end_date': anime.find('enddate').text if anime.find('enddate') is not None else None,
                    'rating': anime.find('ratings/permanent').text if anime.find('ratings/permanent') is not None else None,
                    'anidb_id': anime.get('id')
                }
                
                # Extract year from start date if available
                if anime_data['start_date'] and len(anime_data['start_date']) >= 4:
                    anime_data['year'] = anime_data['start_date'][:4]
                else:
                    anime_data['year'] = 'Unknown'
                    
                results.append(anime_data)
                
                # Limit the number of results
                if len(results) >= limit:
                    break
                    
            return results
            
        except Exception as e:
            logger.error(f"Error searching AniDB: {e}")
            return []
            
    def get_anime_details(self, anime_id: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed information about an anime by its ID.
        
        Args:
            anime_id: The AniDB anime ID
            
        Returns:
            Anime details dictionary or None if not found
        """
        if not self.enabled:
            logger.debug("AniDB API is disabled, skipping details lookup")
            return None
            
        try:
            # Handle rate limiting
            self._respect_rate_limit()
            
            # Build the request
            params = {
                'client': self.client,
                'clientver': self.clientver,
                'protover': 1,
                'request': 'anime',
                'aid': anime_id
            }
            
            # For AniDB API key, it's typically passed as a parameter
            if self.api_key:
                params['api_key'] = self.api_key
                
            response = requests.get(self.BASE_URL, params=params, timeout=10)
            
            # Update the last request time
            self.last_request_time = time.time()
            
            # Check if the response was successful
            if response.status_code != 200:
                logger.error(f"AniDB API error: {response.status_code} - {response.text}")
                return None
                
            # Parse the XML response
            root = ET.fromstring(response.text)
            anime = root.find('.//anime')
            
            if anime is None:
                return None
                
            # Extract titles in different languages
            titles = {}
            for title in anime.findall('.//title'):
                lang = title.get('xml:lang', 'en')
                type_attr = title.get('type', 'main')
                if lang not in titles:
                    titles[lang] = {}
                titles[lang][type_attr] = title.text
            
            # Prefer official English title if available
            official_title = None
            if 'en' in titles:
                if 'official' in titles['en']:
                    official_title = titles['en']['official']
                elif 'main' in titles['en']:
                    official_title = titles['en']['main']
            
            # Fall back to main Japanese title if no English
            if not official_title and 'ja' in titles and 'main' in titles['ja']:
                official_title = titles['ja']['main']
                
            # Finally, use any available title
            if not official_title and titles:
                # Just get the first title we find
                first_lang = next(iter(titles))
                first_type = next(iter(titles[first_lang]))
                official_title = titles[first_lang][first_type]
            
            # Extract episode information
            episodes = []
            for episode in anime.findall('.//episode'):
                ep_num = episode.find('epno').text if episode.find('epno') is not None else 'Unknown'
                ep_title = None
                
                # Try to find the English title first
                for title in episode.findall('title'):
                    if title.get('xml:lang') == 'en':
                        ep_title = title.text
                        break
                
                # If no English title, use the first one
                if ep_title is None and episode.find('title') is not None:
                    ep_title = episode.find('title').text
                    
                episodes.append({
                    'number': ep_num,
                    'title': ep_title
                })
                
            # Build the result dictionary
            result = {
                'id': anime.get('id'),
                'name': official_title or 'Unknown',
                'titles': titles,
                'type': anime.find('type').text if anime.find('type') is not None else 'Unknown',
                'episode_count': anime.find('episodecount').text if anime.find('episodecount') is not None else '0',
                'start_date': anime.find('startdate').text if anime.find('startdate') is not None else None,
                'end_date': anime.find('enddate').text if anime.find('enddate') is not None else None,
                'description': anime.find('description').text if anime.find('description') is not None else None,
                'rating': anime.find('ratings/permanent').text if anime.find('ratings/permanent') is not None else None,
                'episodes': episodes,
                'anidb_id': anime.get('id')
            }
            
            # Extract year from start date if available
            if result['start_date'] and len(result['start_date']) >= 4:
                result['year'] = result['start_date'][:4]
            else:
                result['year'] = 'Unknown'
                
            return result
            
        except Exception as e:
            logger.error(f"Error getting anime details from AniDB: {e}")
            return None
    
    def get_episode_title(self, anime_id: str, episode_number: int) -> Optional[str]:
        """
        Get the title of a specific episode.
        
        Args:
            anime_id: The AniDB anime ID
            episode_number: The episode number
            
        Returns:
            Episode title or None if not found
        """
        try:
            details = self.get_anime_details(anime_id)
            if not details or 'episodes' not in details:
                return None
                
            # Find the episode with the matching number
            for episode in details['episodes']:
                try:
                    ep_num = int(episode['number'])
                    if ep_num == episode_number:
                        return episode['title']
                except (ValueError, TypeError):
                    continue
                    
            return None
            
        except Exception as e:
            logger.error(f"Error getting episode title from AniDB: {e}")
            return None
    
    def _respect_rate_limit(self):
        """Ensure we respect the API rate limits."""

def format_anime_result(anime):
    """Format an anime result for display.
    
    This is a placeholder that will be implemented in the future.
    """
    if not anime:
        return "No result"
    
    # Basic formatting for now - enhance later
    title = anime.get('title', 'Unknown')
    year = anime.get('year', 'Unknown')
    return f"{title} ({year})"