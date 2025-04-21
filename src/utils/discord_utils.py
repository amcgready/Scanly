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