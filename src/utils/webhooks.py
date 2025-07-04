"""Discord webhook notification utility for Scanly.

This module handles sending notifications to Discord webhooks for various events.
"""
import os
import requests
from datetime import datetime
from discord_webhook import DiscordWebhook
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

def _symlink_embed(event, title, year, poster, description, symlink_path, tmdb_id=None):
    # Format title with TMDB ID if available
    if tmdb_id:
        display_title = f"{title} [tmdb-{tmdb_id}]"
    else:
        display_title = title

    embed = {
        "title": f"{event}: {display_title}",
        "fields": [
            {"name": "Year", "value": year or "Unknown", "inline": True},
            {"name": "Description", "value": description or "No description.", "inline": False},
            {"name": "Symlink Path", "value": f"```{symlink_path}```", "inline": False}
        ],
        "color": {
            "CREATED": 0x00ff00,
            "DELETED": 0xff0000,
            "REPAIRED": 0x0000ff
        }.get(event.upper(), 0xcccccc),
        "timestamp": datetime.utcnow().isoformat(),
        "footer": {"text": "Scanly Symlink Event"}
    }
    if poster:
        embed["thumbnail"] = {"url": poster}
    return embed

def send_symlink_creation_notification(title, year, poster, description, symlink_path, tmdb_id=None):
    """Send a notification for a symlink creation event.
    
    Args:
        title (str): Title of the media
        year (str): Year of the media
        poster (str): Poster URL
        description (str): Media description
        symlink_path (str): Path to the created symlink
        
    Returns:
        bool: True if notification was sent successfully, False otherwise
    """
    webhook_url = get_webhook_url("SYMLINK_CREATION")
    if not webhook_url:
        logger.warning("No webhook URL configured for symlink creation")
        return False
    embed = _symlink_embed("Created", title, year, poster, description, symlink_path, tmdb_id)
    payload = {"embeds": [embed]}
    response = requests.post(webhook_url, json=payload)
    if response.status_code >= 400:
        logger.error(f"Discord webhook error: {response.status_code}, {response.text}")
        return False
    return True

def send_symlink_deletion_notification(title, year, poster, description, symlink_path):
    """Send a notification for a symlink deletion event.
    
    Args:
        title (str): Title of the media
        year (str): Year of the media
        poster (str): Poster URL
        description (str): Media description
        symlink_path (str): Path to the deleted symlink
        
    Returns:
        bool: True if notification was sent successfully, False otherwise
    """
    webhook_url = get_webhook_url("SYMLINK_DELETION")
    if not webhook_url:
        logger.warning("No webhook URL configured for symlink deletion")
        return False
    embed = _symlink_embed("Deleted", title, year, poster, description, symlink_path)
    payload = {"embeds": [embed]}
    try:
        response = requests.post(webhook_url, json=payload)
        response.raise_for_status()
        logger.info("Sent symlink deletion webhook for %s", title)
        return True
    except Exception as e:
        logger.error("Failed to send deletion webhook: %s", e)
        return False

def send_symlink_repair_notification(title, year, poster, description, symlink_path):
    """Send a notification for a symlink repair event.
    
    Args:
        title (str): Title of the media
        year (str): Year of the media
        poster (str): Poster URL
        description (str): Media description
        symlink_path (str): Path to the repaired symlink
        
    Returns:
        bool: True if notification was sent successfully, False otherwise
    """
    webhook_url = get_webhook_url("SYMLINK_REPAIR")
    if not webhook_url:
        logger.warning("No webhook URL configured for symlink repair")
        return False
    embed = _symlink_embed("Repaired", title, year, poster, description, symlink_path)
    payload = {"embeds": [embed]}
    try:
        response = requests.post(webhook_url, json=payload)
        response.raise_for_status()
        logger.info("Sent symlink repair webhook for %s", title)
        return True
    except Exception as e:
        logger.error("Failed to send repair webhook: %s", e)
        return False

def send_monitored_item_notification(data):
    """Send a notification for a monitored item event.
    
    Args:
        data (dict): Dictionary containing item details (title, description, path, poster)
        
    Returns:
        bool: True if notification was sent successfully, False otherwise
    """
    webhook_url = get_webhook_url("MONITORED_ITEM")
    if not webhook_url:
        logger.warning("No webhook URL configured for monitored item")
        return False

    directory = data.get("directory", "Unknown")
    folder = data.get("folder", "Unknown")
    message = data.get("message", f"New folder detected: {directory} in {folder}")

    try:
        webhook = DiscordWebhook(
            url=webhook_url,
            content=message
        )
        response = webhook.execute()
        if response and hasattr(response, 'status_code') and response.status_code in [200, 204]:
            logger.info(f"Monitored item webhook sent for {directory} in {folder}")
            return True
        else:
            logger.error(f"Webhook notification failed with status code: {getattr(response, 'status_code', 'unknown')}")
            return False
    except Exception as e:
        logger.error(f"Failed to send monitored item webhook: {e}")
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