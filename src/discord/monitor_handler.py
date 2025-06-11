import os
import sys
import time
import uuid
import threading
import json
from typing import Dict, List, Optional

# Add parent directory to path for imports
parent_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

def get_logger(name):
    """Get a logger with the given name."""
    return logging.getLogger(name)

logger = get_logger(__name__)

# Global variables
active_monitor_sessions = {}
tmdb_api = None

def initialize_handler():
    """Initialize the Discord monitor handler."""
    global tmdb_api
    
    try:
        # Initialize TMDB API for poster fetching
        from src.api.tmdb import TMDB
        tmdb_api = TMDB()
        
        # Register callbacks
        from src.discord.bot import register_callback, start_bot
        register_callback('on_option_selected', handle_option_selected)
        
        # Start the Discord bot
        if not start_bot():
            logger.warning("Failed to start Discord bot")
            return False
            
        logger.info("Discord monitor handler initialized")
        return True
    except Exception as e:
        logger.error(f"Error initializing Discord monitor handler: {e}")
        return False

def shutdown_handler():
    """Shutdown the Discord monitor handler."""
    try:
        # Clean up any active sessions
        active_monitor_sessions.clear()
        
        # Stop the Discord bot
        from src.discord.bot import stop_bot
        stop_bot()
        
        logger.info("Discord monitor handler shut down")
        return True
    except Exception as e:
        logger.error(f"Error shutting down Discord monitor handler: {e}")
        return False

def notify_new_media(directory_path, subfolder_name, file_paths=None):
    """
    Send a notification about newly detected media.
    
    Args:
        directory_path: Base directory path
        subfolder_name: Name of subfolder where media was detected
        file_paths: List of file paths detected
        
    Returns:
        str: Session ID if notification was sent successfully
    """
    try:
        # Check if Discord bot is enabled
        if os.environ.get('DISCORD_BOT_ENABLED', 'false').lower() != 'true':
            logger.info("Discord bot is disabled, skipping notification")
            return None
            
        # Extract title and year from folder name
        from src.main import DirectoryProcessor
        processor = DirectoryProcessor("")
        title, year = processor._extract_folder_metadata(subfolder_name)
        
        # Get poster URL from TMDB
        poster_url = None
        description = None
        if tmdb_api:
            try:
                # First try movie search
                results = tmdb_api.search_movie(f"{title} {year if year else ''}")
                if results and len(results) > 0:
                    movie_id = results[0].get('id')
                    if movie_id:
                        details = tmdb_api.get_movie_details(movie_id)
                        if details:
                            if 'poster_path' in details and details['poster_path']:
                                poster_url = f"https://image.tmdb.org/t/p/w500{details['poster_path']}"
                            if 'overview' in details:
                                description = details['overview']
                
                # If no movie results, try TV search
                if not results or len(results) == 0:
                    results = tmdb_api.search_tv(f"{title} {year if year else ''}")
                    if results and len(results) > 0:
                        tv_id = results[0].get('id')
                        if tv_id:
                            details = tmdb_api.get_tv_details(tv_id)
                            if details:
                                if 'poster_path' in details and details['poster_path']:
                                    poster_url = f"https://image.tmdb.org/t/p/w500{details['poster_path']}"
                                if 'overview' in details:
                                    description = details['overview']
            except Exception as e:
                logger.error(f"Error fetching TMDB data: {e}")
        
        # Prepare media info for notification
        media_info = {
            'title': title,
            'year': year if year else 'Unknown',
            'folder': subfolder_name,
            'files': len(file_paths) if file_paths else 'Unknown',
            'poster_url': poster_url
        }
        
        if description:
            media_info['description'] = description
        
        # Options for user selection - match the individual scan options
        options = [
            "Accept as is",
            "Change search term",
            "Change content type",
            "Skip (process later)"
        ]
        
        # Generate unique session ID
        session_id = str(uuid.uuid4())
        
        # Store session for tracking
        active_monitor_sessions[session_id] = {
            'directory_path': directory_path,
            'subfolder_name': subfolder_name,
            'file_paths': file_paths or [],
            'title': title,
            'year': year,
            'options': options,
            'timestamp': time.time()
        }
        
        # Send notification
        from src.discord.bot import send_notification
        notification_title = "New Media Detected"
        notification_message = f"New media detected in monitored directory: **{subfolder_name}**"
        
        success = send_notification(
            title=notification_title,
            message=notification_message,
            media_info=media_info,
            options=options,
            scan_id=session_id
        )
        
        if success:
            logger.info(f"Sent Discord notification for {subfolder_name} (Session ID: {session_id})")
            return session_id
        else:
            logger.error(f"Failed to send Discord notification for {subfolder_name}")
            # Clean up session on failure
            if session_id in active_monitor_sessions:
                del active_monitor_sessions[session_id]
            return None
            
    except Exception as e:
        logger.error(f"Error in notify_new_media: {e}")
        return None

def handle_option_selected(scan_id, option, option_idx):
    """
    Handle user option selection from Discord.
    
    Args:
        scan_id: Session ID of the scan
        option: Text of the selected option
        option_idx: Index of the selected option
    """
    try:
        # Check if this is a valid session
        if scan_id not in active_monitor_sessions:
            logger.warning(f"Invalid session ID: {scan_id}")
            return False
            
        # Get session data
        session = active_monitor_sessions[scan_id]
        directory_path = session.get('directory_path')
        subfolder_name = session.get('subfolder_name')
        title = session.get('title')
        year = session.get('year')
        
        logger.info(f"User selected '{option}' for {subfolder_name}")
        
        # Process based on selected option
        if option_idx == 0:  # Accept as is
            # Process folder with current settings
            process_media_folder(directory_path, subfolder_name, title, year)
            
            # Send confirmation
            from src.discord.bot import send_notification
            send_notification(
                title="Media Accepted",
                message=f"Processing '{subfolder_name}' with detected metadata",
                media_info={'folder': subfolder_name, 'title': title, 'year': year},
                scan_id=None
            )
            
        elif option_idx == 1:  # Change search term
            # For changing search term, we need manual interaction
            from src.discord.bot import send_notification
            send_notification(
                title="Manual Action Required",
                message=f"To change search term for '{subfolder_name}', please use Scanly's CLI interface",
                media_info={'folder': subfolder_name},
                scan_id=None
            )
            
        elif option_idx == 2:  # Change content type
            # For changing content type, we need manual interaction
            from src.discord.bot import send_notification
            send_notification(
                title="Manual Action Required",
                message=f"To change content type for '{subfolder_name}', please use Scanly's CLI interface",
                media_info={'folder': subfolder_name},
                scan_id=None
            )
            
        elif option_idx == 3:  # Skip
            # Add to skipped items
            import datetime
            from src.main import skipped_items_registry, save_skipped_items
            
            subfolder_path = os.path.join(directory_path, subfolder_name)
            skipped_items_registry.append({
                'subfolder': subfolder_name,
                'path': subfolder_path,
                'skipped_date': datetime.datetime.now().isoformat()
            })
            save_skipped_items(skipped_items_registry)
            
            # Send confirmation
            from src.discord.bot import send_notification
            send_notification(
                title="Media Skipped",
                message=f"'{subfolder_name}' has been added to skipped items for later processing",
                media_info=None,
                scan_id=None
            )
        
        # Remove from active sessions
        del active_monitor_sessions[scan_id]
        return True
        
    except Exception as e:
        logger.error(f"Error handling option selection: {e}")
        return False

def process_media_folder(directory_path, subfolder_name, title=None, year=None):
    """
    Process a media folder with DirectoryProcessor.
    
    Args:
        directory_path: Base directory path
        subfolder_name: Subfolder to process
        title: Media title (optional)
        year: Media year (optional)
    
    Returns:
        bool: True if processing was initiated successfully
    """
    try:
        # Access DirectoryProcessor from main module
        from src.main import DirectoryProcessor
        
        # Full path to the subfolder
        subfolder_path = os.path.join(directory_path, subfolder_name)
        
        # Create processor for just this subfolder
        processor = DirectoryProcessor(subfolder_path, auto_mode=True)
        
        # Process in background thread to avoid blocking
        def process_thread():
            try:
                processor._process_media_files()
                logger.info(f"Completed processing {subfolder_name}")
            except Exception as e:
                logger.error(f"Error in process thread: {e}")
                
        # Start processing thread
        thread = threading.Thread(target=process_thread)
        thread.daemon = True
        thread.start()
        
        logger.info(f"Started processing thread for {subfolder_name}")
        return True
        
    except Exception as e:
        logger.error(f"Error processing media folder: {e}")
        return False