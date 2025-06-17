"""Discord webhook notification utility for Scanly.

This module handles sending notifications to Discord webhooks for various events.
"""
import os
import logging
import json
import requests
from datetime import datetime

# Get logger for this module
from src.utils.logger import get_logger
logger = get_logger(__name__)

def get_webhook_url(event_type=None):
    """Get the appropriate webhook URL based on event type.
    
    Args:
        event_type (str, optional): Type of event (MONITORED_ITEM, SYMLINK_CREATION, etc.)
            If None, returns the default webhook URL.
    
    Returns:
        str: The webhook URL for the specified event or default URL.
    """
    if event_type:
        specific_url_env = f"DISCORD_WEBHOOK_URL_{event_type.upper()}"
        specific_url = os.getenv(specific_url_env)
        
        if specific_url:
            return specific_url
    
    # Return default webhook URL if no event-specific URL is set
    return os.getenv("DEFAULT_DISCORD_WEBHOOK_URL")

def send_monitored_item_notification(item_data):
    """Send a notification for a monitored item event.
    
    Args:
        item_data (dict): Information about the monitored item
    
    Returns:
        bool: True if notification was sent successfully, False otherwise
    """
    webhook_url = get_webhook_url("MONITORED_ITEM")
    if not webhook_url:
        logger.debug("No webhook URL configured for monitored items")
        return False
    
    try:
        # Extract relevant information from item_data
        title = item_data.get('title', 'Unknown Title')
        year = item_data.get('year', 'Unknown Year')
        description = item_data.get('description', 'No description available')
        poster = item_data.get('poster_url')
        file_path = item_data.get('file_path', 'Unknown path')
        
        # Create Discord embed
        embed = {
            "title": f"Monitored Item Detected: {title} ({year})",
            "description": description,
            "color": 3447003,  # Blue color
            "timestamp": datetime.utcnow().isoformat(),
            "fields": [
                {
                    "name": "File Path",
                    "value": f"```{file_path}```",
                    "inline": False
                }
            ],
            "footer": {
                "text": "Scanly Monitor"
            }
        }
        
        # Add poster if available
        if poster:
            embed["thumbnail"] = {"url": poster}
        
        payload = {"embeds": [embed]}
        response = requests.post(webhook_url, json=payload)
        
        if response.status_code >= 400:
            logger.error(f"Discord webhook error: {response.status_code}, {response.text}")
            return False
            
        return True
    
    except Exception as e:
        logger.error(f"Error sending monitored item webhook: {e}")
        return False

def send_symlink_creation_notification(media_name, year, poster, description, original_path, symlink_path):
    """Send a notification for a symlink creation event.
    
    Args:
        media_name (str): Name of the media
        year (str): Year of the media
        poster (str): Poster URL
        description (str): Media description
        original_path (str): Path to the original file
        symlink_path (str): Path to the created symlink
        
    Returns:
        bool: True if notification was sent successfully, False otherwise
    """
    webhook_url = get_webhook_url("SYMLINK_CREATION")
    if not webhook_url:
        logger.debug("No webhook URL configured for symlink creation")
        return False
    
    try:
        embed = {
            "title": f"Symlink Created: {media_name} ({year})",
            "description": description,
            "color": 5763719,  # Green color
            "timestamp": datetime.utcnow().isoformat(),
            "fields": [
                {
                    "name": "Original Path",
                    "value": f"```{original_path}```",
                    "inline": False
                },
                {
                    "name": "Symlink Path",
                    "value": f"```{symlink_path}```",
                    "inline": False
                }
            ],
            "footer": {
                "text": "Scanly Symlinker"
            }
        }
        
        # Add poster if available
        if poster:
            embed["thumbnail"] = {"url": poster}
        
        payload = {"embeds": [embed]}
        response = requests.post(webhook_url, json=payload)
        
        if response.status_code >= 400:
            logger.error(f"Discord webhook error: {response.status_code}, {response.text}")
            return False
            
        return True
    
    except Exception as e:
        logger.error(f"Error sending symlink creation webhook: {e}")
        return False

def send_symlink_deletion_notification(media_name, year, poster, description, original_path, symlink_path):
    """Send a notification for a symlink deletion event.
    
    Args:
        media_name (str): Name of the media
        year (str): Year of the media
        poster (str): Poster URL
        description (str): Media description
        original_path (str): Path to the original file
        symlink_path (str): Path to the deleted symlink
        
    Returns:
        bool: True if notification was sent successfully, False otherwise
    """
    webhook_url = get_webhook_url("SYMLINK_DELETION")
    if not webhook_url:
        logger.debug("No webhook URL configured for symlink deletion")
        return False
    
    try:
        embed = {
            "title": f"Symlink Deleted: {media_name} ({year})",
            "description": description,
            "color": 15548997,  # Red color
            "timestamp": datetime.utcnow().isoformat(),
            "fields": [
                {
                    "name": "Original Path",
                    "value": f"```{original_path}```",
                    "inline": False
                },
                {
                    "name": "Symlink Path",
                    "value": f"```{symlink_path}```",
                    "inline": False
                }
            ],
            "footer": {
                "text": "Scanly Symlinker"
            }
        }
        
        # Add poster if available
        if poster:
            embed["thumbnail"] = {"url": poster}
        
        payload = {"embeds": [embed]}
        response = requests.post(webhook_url, json=payload)
        
        if response.status_code >= 400:
            logger.error(f"Discord webhook error: {response.status_code}, {response.text}")
            return False
            
        return True
    
    except Exception as e:
        logger.error(f"Error sending symlink deletion webhook: {e}")
        return False

def send_symlink_repair_notification(media_name, year, poster, description, original_path, symlink_path):
    """Send a notification for a symlink repair event.
    
    Args:
        media_name (str): Name of the media
        year (str): Year of the media
        poster (str): Poster URL
        description (str): Media description
        original_path (str): Path to the original file
        symlink_path (str): Path to the repaired symlink
        
    Returns:
        bool: True if notification was sent successfully, False otherwise
    """
    webhook_url = get_webhook_url("SYMLINK_REPAIR")
    if not webhook_url:
        logger.debug("No webhook URL configured for symlink repair")
        return False
    
    try:
        embed = {
            "title": f"Symlink Repaired: {media_name} ({year})",
            "description": description,
            "color": 16776960,  # Yellow color
            "timestamp": datetime.utcnow().isoformat(),
            "fields": [
                {
                    "name": "Original Path",
                    "value": f"```{original_path}```",
                    "inline": False
                },
                {
                    "name": "Symlink Path",
                    "value": f"```{symlink_path}```",
                    "inline": False
                }
            ],
            "footer": {
                "text": "Scanly Symlinker"
            }
        }
        
        # Add poster if available
        if poster:
            embed["thumbnail"] = {"url": poster}
        
        payload = {"embeds": [embed]}
        response = requests.post(webhook_url, json=payload)
        
        if response.status_code >= 400:
            logger.error(f"Discord webhook error: {response.status_code}, {response.text}")
            return False
            
        return True
    
    except Exception as e:
        logger.error(f"Error sending symlink repair webhook: {e}")
        return False

def test_webhook():
    """Test if the webhook is working correctly."""
    import os
    from discord_webhook import DiscordWebhook
    import logging
    
    logger = logging.getLogger(__name__)
    
    # Get the webhook URLs
    default_webhook_url = os.environ.get('DEFAULT_DISCORD_WEBHOOK_URL')
    monitored_item_webhook_url = os.environ.get('DISCORD_WEBHOOK_URL_MONITORED_ITEM')
    webhook_url = monitored_item_webhook_url or default_webhook_url
    
    if not webhook_url:
        print("No webhook URL found in environment variables.")
        return False
    
    try:
        print(f"Testing webhook URL: {webhook_url[:30]}...")
        
        webhook = DiscordWebhook(
            url=webhook_url,
            content="🧪 Webhook Test: This is a test message from Scanly"
        )
        response = webhook.execute()
        
        # Discord webhooks return 204 for older API or 200 for newer API versions
        if response.status_code in [200, 204]:
            print(f"Webhook test successful! (Status code: {response.status_code})")
            return True
        else:
            print(f"Webhook test failed with status code: {response.status_code}")
            return False
    except Exception as e:
        print(f"Error testing webhook: {str(e)}")
        return False

if __name__ == "__main__":
    # This allows running this file directly to test webhooks
    test_webhook()