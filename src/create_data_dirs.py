#!/usr/bin/env python3
"""
Create necessary data directories for Scanly.
"""

import os
import sys
from pathlib import Path

def create_data_directories():
    """Create all necessary data directories for Scanly."""
    # Get the base directory (parent of src)
    base_dir = Path(__file__).parent.parent
    
    # Define directories to create
    directories = [
        os.path.join(base_dir, 'data'),
        os.path.join(base_dir, 'data', 'mdblist_cache'),
        os.path.join(base_dir, 'logs')
    ]
    
    for directory in directories:
        try:
            os.makedirs(directory, exist_ok=True)
            print(f"Created directory: {directory}")
        except Exception as e:
            print(f"Error creating directory {directory}: {e}", file=sys.stderr)
    
    # Create empty config file if it doesn't exist
    config_file = os.path.join(base_dir, 'data', 'mdblist_config.json')
    if not os.path.exists(config_file):
        try:
            with open(config_file, 'w') as f:
                f.write('{}')
            print(f"Created config file: {config_file}")
        except Exception as e:
            print(f"Error creating config file {config_file}: {e}", file=sys.stderr)

if __name__ == "__main__":
    create_data_directories()