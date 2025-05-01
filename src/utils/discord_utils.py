"""
Discord notification utilities for Scanly.

This module handles sending notifications to Discord via webhooks.
"""

import json
import requests
import os
from typing import List, Optional
from datetime import datetime

from src.utils.logger import get_logger

logger = get_logger(__name__)

def send_discord_notification(
    webhook_url: str, 
    title: str, 
    message: str, 
    files: Optional[List[str]] = None,
    directory: Optional[str] = None
) -> bool:
    """
    Send a notification to Discord via webhook.
    
    Args:
        webhook_url: Discord webhook URL
        title: Title of the notification
        message: Message content
        files: List of files found (optional)
        directory: Directory being monitored (optional)
        
    Returns:
        True if the notification was sent successfully, False otherwise
    """
    if not webhook_url:
        logger.warning("Discord webhook URL not provided, notification not sent")
        return False
    
    try:
        # Create embed with more detailed information
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        embed = {
            "title": title,
            "description": message,
            "color": 3447003,  # Blue color
            "timestamp": datetime.utcnow().isoformat(),
            "footer": {
                "text": "Scanly Media Monitor"
            },
            "fields": []
        }
        
        # Add directory field if provided
        if directory:
            embed["fields"].append({
                "name": "Directory",
                "value": directory,
                "inline": False
            })
        
        # Add files if provided
        if files and len(files) > 0:
            # List up to 10 files, then summarize if there are more
            file_list = files[:10]
            file_text = "\n".join([f"• `{os.path.basename(f)}`" for f in file_list])
            
            if len(files) > 10:
                file_text += f"\n\n*...and {len(files) - 10} more files*"
                
            embed["fields"].append({
                "name": f"Files Found ({len(files)} total)",
                "value": file_text,
                "inline": False
            })
            
        # Prepare payload
        payload = {
            "username": "Scanly Monitor",
            "embeds": [embed]
        }
        
        # Send notification
        response = requests.post(
            webhook_url,
            data=json.dumps(payload),
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code == 204:
            logger.info(f"Discord notification sent successfully")
            return True
        else:
            logger.error(f"Failed to send Discord notification: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        logger.error(f"Error sending Discord notification: {e}")
        return False

def notify_new_files(directory_name, file_paths, auto_process=False):
    """
    Send a notification about new files detected in a monitored directory.
    
    This is a convenience wrapper around send_discord_notification that
    automatically checks if notifications are enabled and gets the webhook URL.
    
    Args:
        directory_name: Name of the monitored directory
        file_paths: List of file paths that were detected
        auto_process: Whether the files will be auto-processed
        
    Returns:
        True if notification was sent, False otherwise
    """
    # Check if Discord notifications are enabled
    from src.config import get_monitor_settings
    monitor_settings = get_monitor_settings()
    
    notifications_enabled = monitor_settings.get('ENABLE_DISCORD_NOTIFICATIONS', 'false').lower() == 'true'
    webhook_url = monitor_settings.get('DISCORD_WEBHOOK_URL', '')
    
    if not notifications_enabled or not webhook_url:
        logger.debug("Discord notifications disabled or webhook URL not configured")
        return False
    
    # Prepare message
    title = f"New Files Detected: {directory_name}"
    message = f"Scanly has detected {len(file_paths)} new file(s)."
    
    if auto_process:
        message += "\n\nThese files will be processed automatically."
    else:
        message += "\n\nThese files are queued for manual processing."
    
    # Send notification
    return send_discord_notification(
        webhook_url=webhook_url,
        title=title,
        message=message,
        files=file_paths,
        directory=directory_name
    )