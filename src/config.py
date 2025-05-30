"""
Configuration module for Scanly.

This module handles configuration settings for the application.
"""

import os
from dotenv import load_dotenv

# Ensure .env file is loaded
load_dotenv()

def get_settings():
    """Get all application settings."""
    settings = {
        # Default settings
        'LOG_LEVEL': os.environ.get('LOG_LEVEL', 'INFO'),
        'DESTINATION_DIRECTORY': os.environ.get('DESTINATION_DIRECTORY', ''),
        'TMDB_API_KEY': os.environ.get('TMDB_API_KEY', ''),
        'MONITOR_SCAN_INTERVAL': os.environ.get('MONITOR_SCAN_INTERVAL', '60'),
        'MONITOR_AUTO_PROCESS': os.environ.get('MONITOR_AUTO_PROCESS', 'false'),
    }
    
    return settings

def get_monitor_settings():
    """Get monitoring-specific settings."""
    settings = get_settings()
    
    # Extract only monitor-related settings
    monitor_settings = {k: v for k, v in settings.items() if k.startswith('MONITOR_')}
    
    return monitor_settings

def _update_env_var(name, value):
    """Update an environment variable both in memory and in .env file."""
    # Update in memory
    os.environ[name] = value
    
    # Update in .env file
    try:
        env_path = os.path.join(os.path.dirname(__file__), '..', '.env')
        
        # Read existing content
        if os.path.exists(env_path):
            with open(env_path, 'r') as f:
                lines = f.readlines()
        else:
            lines = []
        
        # Check if the variable already exists in the file
        var_exists = False
        for i, line in enumerate(lines):
            if line.strip().startswith(f"{name}="):
                lines[i] = f"{name}={value}\n"
                var_exists = True
                break
        
        # Add the variable if it doesn't exist
        if not var_exists:
            lines.append(f"{name}={value}\n")
        
        # Write the updated content back to the file
        with open(env_path, 'w') as f:
            f.writelines(lines)
        
        return True
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Error updating environment variable: {e}")
        return False