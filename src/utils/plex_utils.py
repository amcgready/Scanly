"""
Plex utility functions for Scanly.

This module contains functions for interacting with Plex Media Server.
"""

import logging
from plexapi.server import PlexServer

def refresh_plex_library(base_url, token, library_name=None):
    """
    Refresh Plex libraries.
    
    Args:
        base_url: Plex server base URL (e.g., "http://localhost:32400")
        token: Plex authentication token
        library_name: Name of specific library to refresh (optional)
        
    Returns:
        Boolean indicating success
    """
    logger = logging.getLogger(__name__)
    
    try:
        # Connect to the Plex server
        logger.info(f"Connecting to Plex server at {base_url}")
        plex = PlexServer(base_url, token)
        
        if library_name:
            # Refresh a specific library
            try:
                library = plex.library.section(library_name)
                logger.info(f"Refreshing Plex library: {library_name}")
                library.refresh()
                logger.info(f"Successfully refreshed Plex library: {library_name}")
                return True
            except KeyError:
                logger.error(f"Library '{library_name}' not found on Plex server")
                return False
        else:
            # Refresh all libraries
            logger.info("Refreshing all Plex libraries")
            for section in plex.library.sections():
                logger.info(f"Refreshing Plex library: {section.title}")
                section.refresh()
            
            logger.info("Successfully refreshed all Plex libraries")
            return True
            
    except Exception as e:
        logger.error(f"Error refreshing Plex library: {str(e)}")
        return False

def get_plex_libraries(base_url, token):
    """
    Get a list of all libraries on a Plex server.
    
    Args:
        base_url: Plex server base URL
        token: Plex authentication token
        
    Returns:
        List of library names or None if an error occurred
    """
    logger = logging.getLogger(__name__)
    
    try:
        # Connect to the Plex server
        plex = PlexServer(base_url, token)
        
        # Get all library sections
        sections = plex.library.sections()
        
        # Return just the names
        return [section.title for section in sections]
            
    except Exception as e:
        logger.error(f"Error getting Plex libraries: {str(e)}")
        return None

def check_plex_connection(base_url, token):
    """
    Check if a connection to the Plex server can be established.
    
    Args:
        base_url: Plex server base URL
        token: Plex authentication token
        
    Returns:
        Boolean indicating if connection was successful
    """
    logger = logging.getLogger(__name__)
    
    try:
        # Attempt to connect to the Plex server
        plex = PlexServer(base_url, token)
        
        # If we get here, connection was successful
        return True
            
    except Exception as e:
        logger.error(f"Error connecting to Plex server: {str(e)}")
        return False