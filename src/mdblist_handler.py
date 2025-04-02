#!/usr/bin/env python3
"""
MDBlist Handler for Scanly.

This module provides functionality for parsing and using MDBlist data
to improve content type detection, particularly for anime identification.
"""
import os
import re
import json
import logging
import requests
import time
from pathlib import Path
from difflib import SequenceMatcher

# Initialize logger
logger = logging.getLogger(__name__)

class MDBListHandler:
    def __init__(self, cache_dir=None):
        """
        Initialize the MDBListHandler.
        
        Args:
            cache_dir: Directory to store cached list data (defaults to Scanly's data directory)
        """
        # Set up cache directory
        if cache_dir is None:
            # Use default cache directory in data folder
            self.cache_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'mdblist_cache')
        else:
            self.cache_dir = cache_dir
            
        # Create cache directory if it doesn't exist
        os.makedirs(self.cache_dir, exist_ok=True)
        
        # Cache of loaded lists
        self.lists = {}
        self.list_configs = {}
        
        # Load configured lists from settings
        self._load_list_configs()
    
    def _load_list_configs(self):
        """Load MDBlist configurations from environment variables or settings file."""
        # Check for MDBlist API key
        self.api_key = os.environ.get('MDBLIST_API_KEY', '')
        
        # Load list configurations
        config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'mdblist_config.json')
        
        try:
            if os.path.exists(config_path):
                with open(config_path, 'r') as f:
                    self.list_configs = json.load(f)
            else:
                self.list_configs = {}
                # Create the config file
                os.makedirs(os.path.dirname(config_path), exist_ok=True)
                with open(config_path, 'w') as f:
                    json.dump({}, f)
        except Exception as e:
            logger.error(f"Error loading MDBlist configurations: {e}")
            self.list_configs = {}
    
    def _save_list_configs(self):
        """Save the current list configurations to file."""
        config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'mdblist_config.json')
        
        try:
            os.makedirs(os.path.dirname(config_path), exist_ok=True)
            with open(config_path, 'w') as f:
                json.dump(self.list_configs, f, indent=4)
            logger.info("Saved MDBlist configurations")
        except Exception as e:
            logger.error(f"Error saving MDBlist configurations: {e}")
    
    def extract_list_id_from_url(self, url_or_id):
        """
        Extract a list ID from a URL or return the ID if already provided.
        
        Args:
            url_or_id: MDBlist URL or ID
            
        Returns:
            List ID or None if URL is invalid
        """
        # If it's already a simple ID (no slashes), return it
        if '/' not in url_or_id:
            return url_or_id
            
        # Extract from URL format: https://mdblist.com/lists/username/list-name
        # or format: https://mdblist.com/lists/list-id
        try:
            # Match pattern like: https://mdblist.com/lists/{username}/{list-name} or https://mdblist.com/lists/{list-id}
            match = re.search(r'mdblist\.com/lists/([^/]+)(?:/([^/]+))?', url_or_id)
            if match:
                if match.group(2):  # Username/list-name format
                    # For URLs like https://mdblist.com/lists/username/list-name
                    username = match.group(1)
                    list_slug = match.group(2)
                    
                    # Use the username/list-slug as the ID
                    return f"{username}/{list_slug}"
                else:
                    # For URLs like https://mdblist.com/lists/list-id
                    return match.group(1)
            return None
        except Exception as e:
            logger.error(f"Error extracting list ID from URL: {e}")
            return None
    
    def add_list(self, name, list_id, content_type, enabled=True):
        """
        Add a new MDBlist to the configuration.
        
        Args:
            name: Name for this list configuration
            list_id: MDBlist ID
            content_type: Content type this list identifies (anime_series, anime_movies, tv_shows, movies)
            enabled: Whether this list is enabled
            
        Returns:
            Boolean indicating success
        """
        try:
            self.list_configs[name] = {
                "list_id": list_id,
                "content_type": content_type,
                "enabled": enabled
            }
            self._save_list_configs()
            return True
        except Exception as e:
            logger.error(f"Error adding MDBlist configuration: {e}")
            return False
    
    def delete_list(self, name):
        """
        Delete a list configuration.
        
        Args:
            name: Name of the list to delete
            
        Returns:
            Boolean indicating success
        """
        if name in self.list_configs:
            del self.list_configs[name]
            self._save_list_configs()
            return True
        return False
    
    def get_list_configs(self):
        """Get all list configurations."""
        return self.list_configs
    
    def fetch_mdblist(self, list_id, force_refresh=False):
        """
        Fetch a MDBlist either from cache or from the API.
        
        Args:
            list_id: The MDBlist ID to fetch
            force_refresh: Whether to force refresh from the API
            
        Returns:
            List of titles from the MDBlist or None if failed
        """
        # Check if list is already loaded in memory
        if list_id in self.lists and not force_refresh:
            return self.lists[list_id]
        
        # Define the cache file path
        cache_file = os.path.join(self.cache_dir, f"{list_id.replace('/', '_')}.json")
        
        # Check if cache exists and is fresh (less than 24 hours old)
        cache_is_fresh = False
        if os.path.exists(cache_file) and not force_refresh:
            file_age = time.time() - os.path.getmtime(cache_file)
            if file_age < 86400:  # 24 hours
                cache_is_fresh = True
                try:
                    with open(cache_file, 'r') as f:
                        self.lists[list_id] = json.load(f)
                    return self.lists[list_id]
                except Exception as e:
                    logger.warning(f"Error loading cached list {list_id}: {e}")
        
        # If no API key, we can't fetch
        if not self.api_key:
            logger.error("Missing MDBlist API key")
            return None
        
        # Fetch from API
        try:
            url = f"https://mdblist.com/api/lists/{list_id}/items?apikey={self.api_key}"
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                items = data.get('items', [])
                
                # Extract titles and save to cache
                titles = [item.get('title', '') for item in items if item.get('title')]
                
                # Save to cache
                with open(cache_file, 'w') as f:
                    json.dump(titles, f)
                
                # Store in memory
                self.lists[list_id] = titles
                return titles
            else:
                logger.error(f"Error fetching list {list_id}: {response.status_code} {response.text}")
                return None
            
        except Exception as e:
            logger.error(f"Error fetching MDBlist {list_id}: {e}")
            return None
    
    def _normalize_title(self, title):
        """
        Normalize a title for comparison.
        
        Args:
            title: Title to normalize
            
        Returns:
            Normalized title
        """
        if not title:
            return ""
            
        # Convert to lowercase
        normalized = title.lower()
        
        # Remove special characters and extra spaces
        normalized = re.sub(r'[^\w\s]', '', normalized)
        normalized = re.sub(r'\s+', ' ', normalized).strip()
        
        return normalized
    
    def _title_similarity(self, title1, title2):
        """
        Calculate similarity between two titles.
        
        Args:
            title1: First title
            title2: Second title
            
        Returns:
            Similarity score (0-1)
        """
        norm1 = self._normalize_title(title1)
        norm2 = self._normalize_title(title2)
        
        if not norm1 or not norm2:
            return 0
        
        return SequenceMatcher(None, norm1, norm2).ratio()
    
    def check_title_in_list(self, title, year=None, list_id=None, similarity_threshold=0.85):
        """
        Check if a title exists in a specific MDBlist.
        
        Args:
            title: Title to check
            year: Optional release year to improve matching
            list_id: MDBlist ID to check. If None, checks all configured lists.
            similarity_threshold: Minimum similarity score for a match
            
        Returns:
            Tuple of (matched, content_type) or (False, None) if no match
        """
        if not title:
            return False, None
        
        # If list_id specified, only check that list
        if list_id:
            list_items = self.fetch_mdblist(list_id)
            if not list_items:
                return False, None
            
            for item in list_items:
                if self._title_similarity(title, item) >= similarity_threshold:
                    # Find which config this list belongs to
                    for name, config in self.list_configs.items():
                        if config['list_id'] == list_id and config['enabled']:
                            return True, config['content_type']
                    return True, None
            
            return False, None
        
        # Check all configured lists
        for name, config in self.list_configs.items():
            if not config['enabled']:
                continue
                
            list_items = self.fetch_mdblist(config['list_id'])
            if not list_items:
                continue
                
            for item in list_items:
                if self._title_similarity(title, item) >= similarity_threshold:
                    return True, config['content_type']
        
        return False, None


# Module-level instance
_mdblist_handler = None

def get_mdblist_handler():
    """
    Get the MDBlist handler instance.
    
    Returns:
        MDBListHandler instance
    """
    global _mdblist_handler
    if _mdblist_handler is None:
        _mdblist_handler = MDBListHandler()
    return _mdblist_handler