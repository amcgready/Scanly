"""
AniDB API client.

This module provides functionality for interacting with the AniDB API.
"""
import os
import requests
import time
import logging
import re

class AniDB:
    """AniDB API client."""
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # Read environment variables directly for more reliability
        self.client = os.environ.get('ANIDB_CLIENT_NAME', 'scanly')
        self.version = os.environ.get('ANIDB_CLIENT_VERSION', '1')
        self.api_key = os.environ.get('ANIDB_API_KEY', '').strip()
        
        # Convert string to boolean directly
        api_enabled_str = os.environ.get('ANIDB_API_ENABLED', 'false').lower()
        api_enabled = api_enabled_str in ('true', '1', 'yes', 'y', 't')
        
        # Debug output
        print(f"\nAniDB Configuration:")
        print(f"• Client: {self.client}")
        print(f"• Version: {self.version}")
        print(f"• API Key: {'Set' if self.api_key else 'Not set'}")
        print(f"• API Enabled Setting: {api_enabled_str} → {api_enabled}")
        
        # Set enabled status
        self.enabled = api_enabled and bool(self.api_key)
        
        print(f"• AniDB Integration: {'ENABLED' if self.enabled else 'DISABLED'}")
        print(f"  (Requires both ANIDB_API_ENABLED=true and a valid ANIDB_API_KEY)")
        
        # Rate limiting settings
        self.last_request_time = 0
        self.min_request_interval = 2  # seconds between requests
    
    def search_anime(self, title):
        """
        Search for anime by title.
        
        Args:
            title: The title to search for
            
        Returns:
            List of anime results
        """
        if not self.enabled:
            print("AniDB search called but integration is disabled")
            return []
        
        print(f"Searching AniDB for: {title}")
        
        # Implement mock AniDB search for demonstration/testing
        # In a real implementation, this would make an API request
        return self._get_mock_results(title)
    
    def _get_mock_results(self, title):
        """Generate mock anime results for testing purposes."""
        title_lower = title.lower()
        
        # Pokemon specific
        if 'pokemon' in title_lower or 'pokémon' in title_lower:
            results = []
            
            # Add different Pokemon results based on the query
            if 'origin' in title_lower:
                results.append({
                    'id': '9494',
                    'name': 'Pokemon Origins',
                    'year': '2013',
                    'type': 'OVA',
                    'description': 'Special based on Pokemon Red and Green games'
                })
            else:
                results.append({
                    'id': '230',
                    'name': 'Pokemon',
                    'year': '1997',
                    'type': 'TV Series',
                    'description': 'Pokémon anime series following Ash Ketchum'
                })
            
            # Also add movies if searching for Pokemon
            results.append({
                'id': '231',
                'name': 'Pokemon: The First Movie',
                'year': '1998',
                'type': 'Movie',
                'description': 'Mewtwo Strikes Back'
            })
            
            return results
            
        # Dragon Ball
        elif any(x in title_lower for x in ['dragon ball', 'dragonball']):
            return [{
                'id': '231',
                'name': 'Dragon Ball',
                'year': '1986',
                'type': 'TV Series',
                'description': 'Goku\'s adventures as a child'
            }, {
                'id': '232',
                'name': 'Dragon Ball Z',
                'year': '1989',
                'type': 'TV Series',
                'description': 'Continuation of Goku\'s adventures as an adult'
            }]
            
        # Naruto
        elif 'naruto' in title_lower:
            return [{
                'id': '239',
                'name': 'Naruto',
                'year': '2002',
                'type': 'TV Series',
                'description': 'Ninja adventures of Naruto Uzumaki'
            }, {
                'id': '240',
                'name': 'Naruto Shippuden',
                'year': '2007',
                'type': 'TV Series',
                'description': 'Continuation of Naruto\'s adventures'
            }]
            
        # Add more mock results as needed
        
        # Return empty list if no matches
        return []
    
    def get_anime_details(self, anime_id):
        """
        Get detailed information about an anime by its ID.
        
        Args:
            anime_id: The AniDB anime ID
            
        Returns:
            Anime details or None if an error occurs
        """
        if not self.enabled:
            print("AniDB is disabled, can't get anime details")
            return None
            
        print(f"Getting anime details for ID: {anime_id}")
        
        # In a real implementation, this would make an API request
        # For now, return mock data
        if anime_id == '9494':  # Pokemon Origins
            return {
                'id': '9494',
                'name': 'Pokemon Origins',
                'start_date': '2013-10-02',
                'end_date': '2013-10-02',
                'episode_count': 4,
                'type': 'OVA',
                'description': 'Special based on Pokemon Red and Green games featuring Red as the main character',
                'episodes': [
                    {'number': 1, 'title': 'File 1: Red'},
                    {'number': 2, 'title': 'File 2: Cubone'},
                    {'number': 3, 'title': 'File 3: Giovanni'},
                    {'number': 4, 'title': 'File 4: Charizard'}
                ]
            }
        elif anime_id == '230':  # Pokemon series
            return {
                'id': '230',
                'name': 'Pokemon',
                'start_date': '1997-04-01',
                'episode_count': 276,
                'type': 'TV Series',
                'description': 'Pokémon anime series following Ash Ketchum',
                'episodes': [
                    {'number': 1, 'title': 'Pokemon, I Choose You!'},
                    {'number': 2, 'title': 'Pokemon Emergency!'},
                    # More episodes would be here
                ]
            }
        
        # Return None for unknown IDs
        return None

# Helper function to format anime results for display
def format_anime_result(result):
    """Format an anime result for display."""
    name = result.get('name', 'Unknown')
    year = result.get('year', 'Unknown')
    type_str = result.get('type', 'Unknown')
    
    return f"{name} ({year}) - {type_str}"
