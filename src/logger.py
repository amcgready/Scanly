import os
import logging
import json
import time
from datetime import datetime
from typing import Dict, Any, Optional, Union

# Setup logger
logger = logging.getLogger(__name__)

# Set up the main logger
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Main app logger
app_logger = logging.getLogger('scanly')

# Create file handler for the app logs
app_log_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'logs', 'scanly.log')
os.makedirs(os.path.dirname(app_log_path), exist_ok=True)
app_handler = logging.FileHandler(app_log_path)
app_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
app_logger.addHandler(app_handler)

# Create a specific structured activity logger for the UI
ACTIVITY_LOG_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'logs', 'activity.json')

def log_activity(
    action: str,
    item_name: str,
    status: str = "success",
    content_type: Optional[str] = None,
    path: Optional[str] = None,
    directory: Optional[str] = None,
    symlink_path: Optional[str] = None,
    message: Optional[str] = None,
    error: Optional[str] = None,
    is_movie: bool = False,
) -> Dict[str, Any]:
    """
    Log activity for the UI activity log in a structured format.
    
    Args:
        action: Type of action (scan, process, symlink_create, symlink_remove, monitor_add, etc.)
        item_name: Name of the item being processed
        status: Status of the operation (success, error, warning, skipped)
        content_type: Type of content (movie, tv, anime_series, anime_movie)
        path: Full path to the item
        directory: Directory path (for monitor operations)
        symlink_path: Path to symlink (for symlink operations)
        message: Additional message details
        error: Error details if applicable
        is_movie: For anime, whether it's a movie or series
        
    Returns:
        The logged activity entry as a dictionary
    """
    timestamp = datetime.now().isoformat()
    
    # Create the activity entry
    activity = {
        "timestamp": timestamp,
        "action": action,
        "name": item_name,
        "status": status,
    }
    
    # Add optional fields if provided
    if content_type:
        activity["content_type"] = content_type
    if path:
        activity["path"] = path
    if directory:
        activity["directory"] = directory
    if symlink_path:
        activity["symlink_path"] = symlink_path
    if message:
        activity["message"] = message
    if error:
        activity["error"] = error
    if is_movie:
        activity["is_movie"] = is_movie
        
    # Also log to the main app logger
    if status == "error":
        app_logger.error(f"{action}: {item_name} - {error or message or ''}")
    elif status == "warning" or status == "skipped":
        app_logger.warning(f"{action}: {item_name} - {message or error or ''}")
    else:
        app_logger.info(f"{action}: {item_name}")
    
    # Append to activity log file
    try:
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(ACTIVITY_LOG_PATH), exist_ok=True)
        
        # Read existing logs
        activities = []
        if os.path.exists(ACTIVITY_LOG_PATH):
            try:
                with open(ACTIVITY_LOG_PATH, 'r') as f:
                    activities = json.load(f)
            except json.JSONDecodeError:
                # Handle corrupted file
                activities = []
        
        # Add new activity
        activities.append(activity)
        
        # Limit log size (keep latest 10000 entries)
        if len(activities) > 10000:
            activities = activities[-10000:]
            
        # Write back to file
        with open(ACTIVITY_LOG_PATH, 'w') as f:
            json.dump(activities, f, indent=2)
            
        return activity
    except Exception as e:
        app_logger.error(f"Failed to log activity: {e}")
        return activity

# Function to extract just the relative path after root directory
def extract_relative_path(full_path):
    """Extract just the path after the root directory."""
    # Common root directories to check
    root_dirs = ["/mnt/", "/media/", "/home/", "/Volumes/"]
    
    for root in root_dirs:
        if root in full_path:
            parts = full_path.split(root, 1)
            if len(parts) > 1:
                # Get the part after the root, then the first directory
                path_parts = parts[1].split('/', 1)
                if len(path_parts) > 1:
                    return path_parts[1]  # Return everything after the root/first-dir
    
    # If no common root found, just return the basename
    return os.path.basename(full_path)

# Helper functions for common activity logs

def log_movie_process(name: str, path: str, status: str = "success", message: str = None, error: str = None):
    relative_path = extract_relative_path(path)
    status = "Success" if status == "success" else "Failed"
    
    logger.info(f"Movie|{name}|{relative_path}|{status}")
    return log_activity("process", name, status, "movie", path=path, message=message, error=error)

def log_tv_process(name: str, path: str, status: str = "success", message: str = None, error: str = None):
    relative_path = extract_relative_path(path)
    status = "Success" if status == "success" else "Failed"
    
    logger.info(f"TV Series|{name}|{relative_path}|{status}")
    return log_activity("process", name, status, "tv", path=path, message=message, error=error)

def log_anime_process(name: str, path: str, is_movie: bool = False, status: str = "success", message: str = None, error: str = None):
    content_type = "anime_movie" if is_movie else "anime_series"
    relative_path = extract_relative_path(path)
    status = "Success" if status == "success" else "Failed"
    
    logger.info(f"{'Anime Movie' if is_movie else 'Anime Series'}|{name}|{relative_path}|{status}")
    return log_activity("process", name, status, content_type, path=path, message=message, error=error, is_movie=is_movie)

def log_symlink_create(name: str, path: str, symlink_path: str, status: str = "success", error: str = None):
    relative_path = extract_relative_path(path)
    
    # Determine content type from target path structure
    if "TV Shows" in symlink_path:
        content_type = "TV Series"
    elif "Anime Series" in symlink_path:
        content_type = "Anime Series"
    elif "Anime Movies" in symlink_path:
        content_type = "Anime Movie"
    else:
        content_type = "Movie"
    
    logger.info(f"{content_type}|{name}|{relative_path}|Created")
    return log_activity("symlink_create", name, status, path=path, symlink_path=symlink_path, error=error)

def log_symlink_remove(name: str, path: str, symlink_path: str, status: str = "success", error: str = None):
    relative_path = extract_relative_path(path)
    
    # Determine content type from target path structure
    if "TV Shows" in symlink_path:
        content_type = "TV Series"
    elif "Anime Series" in symlink_path:
        content_type = "Anime Series"
    elif "Anime Movies" in symlink_path:
        content_type = "Anime Movie"
    else:
        content_type = "Movie"
    
    logger.info(f"{content_type}|{name}|{relative_path}|Removed")
    return log_activity("symlink_remove", name, status, path=path, symlink_path=symlink_path, error=error)

def log_symlink_repair(name: str, path: str, symlink_path: str, status: str = "success", error: str = None):
    relative_path = extract_relative_path(path)
    
    # Determine content type from target path structure
    if "TV Shows" in symlink_path:
        content_type = "TV Series"
    elif "Anime Series" in symlink_path:
        content_type = "Anime Series"
    elif "Anime Movies" in symlink_path:
        content_type = "Anime Movie"
    else:
        content_type = "Movie"
    
    logger.info(f"{content_type}|{name}|{relative_path}|Repaired")
    return log_activity("symlink_repair", name, status, path=path, symlink_path=symlink_path, error=error)

def log_skipped_item(name: str, path: str, content_type: str, error: str = "User skipped"):
    relative_path = extract_relative_path(path)
    logger.info(f"Skipped|{name}|{relative_path}|{error}")
    return log_activity("skipped", name, "skipped", content_type, path=path, error=error)

def log_monitor_add(directory: str, status: str = "success", error: str = None):
    name = os.path.basename(directory.rstrip('/'))
    relative_path = extract_relative_path(directory)
    logger.info(f"Monitor|{os.path.basename(directory)}|{relative_path}|Added")
    return log_activity("monitor_add", name, status, directory=directory, error=error)

def log_monitor_remove(directory: str, status: str = "success", error: str = None):
    name = os.path.basename(directory.rstrip('/'))
    relative_path = extract_relative_path(directory)
    logger.info(f"Monitor|{os.path.basename(directory)}|{relative_path}|Removed")
    return log_activity("monitor_remove", name, status, directory=directory, error=error)

def log_monitor_pause(directory: str, status: str = "success", error: str = None):
    name = os.path.basename(directory.rstrip('/'))
    relative_path = extract_relative_path(directory)
    logger.info(f"Monitor|{os.path.basename(directory)}|{relative_path}|Paused")
    return log_activity("monitor_pause", name, status, directory=directory, error=error)

def log_monitor_resume(directory: str, status: str = "success", error: str = None):
    name = os.path.basename(directory.rstrip('/'))
    relative_path = extract_relative_path(directory)
    logger.info(f"Monitor|{os.path.basename(directory)}|{relative_path}|Resumed")
    return log_activity("monitor_resume", name, status, directory=directory, error=error)