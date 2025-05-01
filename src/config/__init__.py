"""
Configuration module for Scanly.

This module handles configuration settings for the application.
"""

import os
from dotenv import load_dotenv

# Add logging config defaults
LOG_LEVEL = 'INFO'
LOG_FILE = 'scanly.log'

# Add missing progress file configuration
PROGRESS_FILE = 'scanly_progress.json'

def get_settings():
    """Get application settings."""
    load_dotenv()
    
    settings = {
        # Add your application settings here
        'LOG_LEVEL': os.environ.get('LOG_LEVEL', LOG_LEVEL),
        'LOG_FILE': os.environ.get('LOG_FILE', LOG_FILE),
        'PROGRESS_FILE': os.environ.get('PROGRESS_FILE', PROGRESS_FILE)
    }
    
    # Add monitor settings
    monitor_settings = get_monitor_settings()
    settings.update(monitor_settings)
    
    return settings

def get_monitor_settings():
    """Get monitoring-related settings."""
    load_dotenv()
    
    # Define monitor settings
    MONITOR_SETTINGS = {
        'MONITOR_AUTO_PROCESS': {
            'name': 'MONITOR_AUTO_PROCESS',
            'description': 'Automatically process new files in monitored directories',
            'type': 'bool',
            'category': 'Monitoring',
            'default': 'false'
        },
        'MONITOR_SCAN_INTERVAL': {
            'name': 'MONITOR_SCAN_INTERVAL',
            'description': 'Interval in seconds between monitor scans',
            'type': 'number',
            'category': 'Monitoring',
            'default': '15'
        },
        'ENABLE_DISCORD_NOTIFICATIONS': {
            'name': 'ENABLE_DISCORD_NOTIFICATIONS',
            'description': 'Send notifications to Discord webhook',
            'type': 'bool',
            'category': 'Notifications',
            'default': 'false'
        },
        'DISCORD_WEBHOOK_URL': {
            'name': 'DISCORD_WEBHOOK_URL',
            'description': 'Discord webhook URL for notifications',
            'type': 'string',
            'category': 'Notifications',
            'default': ''
        }
    }
    
    settings = {}
    for key, setting in MONITOR_SETTINGS.items():
        settings[key] = os.environ.get(key, setting['default'])
    
    return settings

def _update_env_var(name, value):
    """Update an environment variable both in memory and in .env file."""
    # Update in memory
    os.environ[name] = value
    
    # Update in .env file
    try:
        env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '..', '.env')
        
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
