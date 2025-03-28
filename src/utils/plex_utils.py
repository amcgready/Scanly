"""
Utility functions for interacting with Plex Media Server.

This module provides functions for triggering library scans
and interacting with Plex Media Server.
"""

import requests
from urllib.parse import urljoin
from typing import Optional

from src.config import ENABLE_PLEX_UPDATE, PLEX_URL, PLEX_TOKEN
from src.utils.logger import get_logger

logger = get_logger(__name__)


def trigger_plex_scan(section_id: Optional[int] = None) -> bool:
    """
    Trigger a Plex library scan.
    
    Args:
        section_id: Optional library section ID to scan. If None, scans all libraries.
        
    Returns:
        True if the scan was triggered successfully, False otherwise
    """
    if not ENABLE_PLEX_UPDATE:
        logger.debug("Plex updates are disabled")
        return True
    
    if not PLEX_TOKEN:
        logger.error("Plex token is not set")
        return False
    
    try:
        headers = {
            'X-Plex-Token': PLEX_TOKEN,
            'Accept': 'application/json'
        }
        
        if section_id is not None:
            endpoint = f"library/sections/{section_id}/refresh"
        else:
            endpoint = "library/refresh"
        
        url = urljoin(PLEX_URL, endpoint)
        
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            logger.info(f"Successfully triggered Plex scan for {'all libraries' if section_id is None else f'section {section_id}'}")
            return True
        else:
            logger.error(f"Failed to trigger Plex scan: {response.status_code} {response.text}")
            return False
            
    except Exception as e:
        logger.error(f"Error triggering Plex scan: {e}")
        return False


def get_plex_sections() -> list:
    """
    Get all library sections from Plex.
    
    Returns:
        List of library sections
    """
    if not ENABLE_PLEX_UPDATE or not PLEX_TOKEN:
        return []
    
    try:
        headers = {
            'X-Plex-Token': PLEX_TOKEN,
            'Accept': 'application/json'
        }
        
        url = urljoin(PLEX_URL, "library/sections")
        
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            sections = response.json().get('MediaContainer', {}).get('Directory', [])
            return sections
        else:
            logger.error(f"Failed to get Plex sections: {response.status_code} {response.text}")
            return []
            
    except Exception as e:
        logger.error(f"Error getting Plex sections: {e}")
        return []