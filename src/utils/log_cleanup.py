#!/usr/bin/env python3
"""
Log Cleanup Utility for Scanly

This script cleans up the scanly.log file, removing entries older than
the LOG_INTERVAL setting from the environment.
"""

import os
import re
import sys
from datetime import datetime, timedelta
import logging
from pathlib import Path
from dotenv import load_dotenv

# Ensure we can access the project modules
parent_dir = Path(__file__).resolve().parent.parent.parent
if str(parent_dir) not in sys.path:
    sys.path.append(str(parent_dir))

# Load environment variables from .env file
load_dotenv(os.path.join(parent_dir, '.env'))

def get_log_path():
    """Get the path to the scanly.log file."""
    log_dir = os.path.join(parent_dir, 'logs')
    os.makedirs(log_dir, exist_ok=True)
    return os.path.join(log_dir, 'scanly.log')

def get_log_interval():
    """Get the LOG_INTERVAL from environment variables (in minutes)."""
    try:
        interval = int(os.getenv('LOG_INTERVAL', '1440'))  # Default to 24 hours (1440 minutes)
        return interval
    except ValueError:
        logging.error("Invalid LOG_INTERVAL value, using default of 1440 minutes (24 hours)")
        return 1440

def clean_old_log_entries():
    """Clean log entries older than LOG_INTERVAL."""
    log_path = get_log_path()
    log_interval = get_log_interval()
    
    # If log file doesn't exist, there's nothing to clean
    if not os.path.exists(log_path):
        return
    
    # Calculate cutoff time
    cutoff_time = datetime.now() - timedelta(minutes=log_interval)
    
    # Regex pattern to extract timestamp from log entries
    # Matches standard logging format like "2023-08-15 14:30:45,123"
    timestamp_pattern = re.compile(r'^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3})')
    
    # Read all log entries
    with open(log_path, 'r') as file:
        log_lines = file.readlines()
    
    # Filter log entries
    filtered_lines = []
    current_entry_lines = []
    keep_current_entry = False
    
    for line in log_lines:
        match = timestamp_pattern.match(line)
        
        # If this line starts a new log entry
        if match:
            # Process the previous entry if we have one
            if current_entry_lines:
                if keep_current_entry:
                    filtered_lines.extend(current_entry_lines)
                current_entry_lines = []
            
            # Check if the new entry is recent enough to keep
            try:
                timestamp_str = match.group(1)
                # Convert to datetime (handling milliseconds)
                entry_time = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S,%f")
                keep_current_entry = entry_time >= cutoff_time
            except ValueError:
                # If we can't parse the timestamp, keep the entry to be safe
                keep_current_entry = True
            
            # Add the current line to the entry buffer
            current_entry_lines.append(line)
        else:
            # This is a continuation of the current entry
            current_entry_lines.append(line)
    
    # Don't forget to process the last entry
    if current_entry_lines and keep_current_entry:
        filtered_lines.extend(current_entry_lines)
    
    # Write filtered logs back to file
    with open(log_path, 'w') as file:
        file.writelines(filtered_lines)
    
    return len(log_lines) - len(filtered_lines)  # Return number of removed lines

if __name__ == "__main__":
    removed_count = clean_old_log_entries()
    print(f"Log cleanup complete. Removed {removed_count} old log entries.")