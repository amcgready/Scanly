"""
Discord utilities for Scanly.

This module handles sending notifications to Discord via webhooks.
"""

import os
import json
import requests
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime

def get_logger(name):
    """Get a logger with the given name."""
    return logging.getLogger(name)

logger = get_logger(__name__)

def send_discord_webhook_notification(
    webhook_url: str,
    title: str,
    message: str,
    fields: Optional[List[Dict[str, Any]]] = None,
    thumbnail_url: Optional[str] = None
) -> bool:
    """
    Send notification to Discord via webhook.
    
    Args:
        webhook_url: Discord webhook URL
        title: Notification title
        message: Notification message
        fields: Optional list of fields
        thumbnail_url: Optional URL for thumbnail image
        
    Returns:
        bool: Whether notification was sent successfully
    """
    try:
        # Create embed
        embed = {
            "title": title,
            "description": message,
            "color": 3447003,  # Blue
            "timestamp": datetime.utcnow().isoformat(),
            "footer": {
                "text": "Scanly Media Monitor"
            }
        }
        
        # Add thumbnail if provided
        if thumbnail_url:
            embed["thumbnail"] = {"url": thumbnail_url}
            
        # Add fields if provided
        if fields:
            embed["fields"] = fields
            
        # Create payload with embed
        payload = {
            "embeds": [embed]
        }
        
        # Send webhook request
        response = requests.post(
            webhook_url,
            data=json.dumps(payload),
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        
        if response.status_code == 204:
            logger.info(f"Discord webhook notification sent successfully")
            return True
        else:
            logger.error(f"Failed to send Discord webhook notification: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        logger.error(f"Error sending Discord webhook notification: {e}")
        return False