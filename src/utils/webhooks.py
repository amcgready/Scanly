"""Discord webhook notification utility for Scanly.

This module handles sending notifications to Discord webhooks for various events.
"""
import os
import requests
from datetime import datetime
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

def _symlink_embed(event, title, year, poster, description, symlink_path):
    embed = {
        "title": f"{event}: {title} ({year or 'Unknown'})",
        "description": description or "No description.",
        "color": {
            "CREATED": 0x00ff00,
            "DELETED": 0xff0000,
            "REPAIRED": 0x0000ff
        }.get(event.upper(), 0xcccccc),
        "timestamp": datetime.utcnow().isoformat(),
        "fields": [
            {
                "name": "Symlink Path",
                "value": f"```{symlink_path}```",
                "inline": False
            }
        ],
        "footer": {
            "text": "Scanly Symlink Event"
        }
    }
    if poster:
        embed["thumbnail"] = {"url": poster}
    return embed

def send_symlink_creation_notification(title, year, poster, description, symlink_path):
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
    embed = _symlink_embed("Created", title, year, poster, description, symlink_path)
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
    response = requests.post(webhook_url, json=payload)
    if response.status_code >= 400:
        logger.error(f"Discord webhook error: {response.status_code}, {response.text}")
        return False
    return True

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
    response = requests.post(webhook_url, json=payload)
    if response.status_code >= 400:
        logger.error(f"Discord webhook error: {response.status_code}, {response.text}")
        return False
    return True

def send_monitored_item_notification(item_data):
    """Send a notification for a monitored item event (stub implementation)."""
    # You can implement this as needed, or just log for now
    logger.info("Monitored item notification: %s", item_data)
    return True

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