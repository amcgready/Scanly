import os
import sys
import asyncio
import threading
import logging
import json
import re
import time
import uuid
import traceback
from typing import Dict, Optional, List, Union, Any, Callable

# Add parent directory to path for imports
parent_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

from src.main import get_logger

logger = get_logger(__name__)

# Global variables
bot_instance = None
bot_thread = None
is_bot_running = False
active_scans = {}
command_callbacks = {}

# Import discord properly
try:
    import discord
    from discord.ext import commands
except ImportError as e:
    logger.error(f"Failed to import discord: {e}")

class ScanlyBot(commands.Bot):
    """Discord bot for Scanly media scanner."""
    
    def __init__(self, channel_id=None):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.reactions = True
        super().__init__(command_prefix="!", intents=intents)
        self.channel_id = channel_id
        self.target_channel = None
        self.ready_event = asyncio.Event()
        
    async def on_ready(self):
        """Called when the bot is connected to Discord."""
        logger.info(f'Logged in as {self.user} (ID: {self.user.id})')
        
        # Set up target channel for notifications
        if self.channel_id:
            try:
                self.target_channel = self.get_channel(int(self.channel_id))
                if not self.target_channel:
                    logger.warning(f"Could not find channel with ID {self.channel_id}")
            except Exception as e:
                logger.error(f"Error finding target channel: {e}")
        
        # Set ready event to signal bot is ready
        self.ready_event.set()
        global is_bot_running
        is_bot_running = True
        
    async def on_reaction_add(self, reaction, user):
        """Handle reactions to bot messages."""
        # Ignore bot's own reactions
        if user.id == self.user.id:
            return
        
        try:
            # Check if this is one of our active scan messages
            message_id = reaction.message.id
            scan_id = None
            
            # Find which scan this reaction belongs to
            for sid, scan_info in active_scans.items():
                if scan_info.get('message_id') == message_id:
                    scan_id = sid
                    break
                    
            if not scan_id:
                return  # Not one of our messages
                
            # Parse emoji to get option
            emoji = str(reaction.emoji)
            option_idx = None
            
            if emoji == "1️⃣": 
                option_idx = 0  # Accept
            elif emoji == "2️⃣":
                option_idx = 1  # Change search term
            elif emoji == "3️⃣":
                option_idx = 2  # Change content type
            elif emoji == "4️⃣":
                option_idx = 3  # Skip
                
            if option_idx is not None:
                # Get options for this scan
                options = active_scans[scan_id].get('options', [])
                if 0 <= option_idx < len(options):
                    selected_option = options[option_idx]
                    logger.info(f"User {user.name} selected option: {selected_option} for scan {scan_id}")
                    
                    # Execute callback if one is registered
                    callback = command_callbacks.get('on_option_selected')
                    if callback:
                        callback(scan_id=scan_id, option=selected_option, option_idx=option_idx)
                    
                    # Update message to show processed state
                    embed = reaction.message.embeds[0]
                    embed.color = discord.Color.green()
                    embed.set_footer(text=f"Processed: {selected_option} selected by {user.name}")
                    await reaction.message.edit(embed=embed)
                    
                    # Clear reactions to prevent further selections
                    await reaction.message.clear_reactions()
                    
                    # Remove from active scans
                    if scan_id in active_scans:
                        del active_scans[scan_id]
                        
        except Exception as e:
            logger.error(f"Error processing reaction: {e}")
            logger.error(traceback.format_exc())
            
    async def send_media_notification(self, title, message, media_info=None, options=None, scan_id=None):
        """
        Send a notification about media content to the configured channel
        
        Args:
            title: Notification title
            message: Notification message
            media_info: Dict with media details (poster_url, year, etc)
            options: List of option strings for user to select
            scan_id: ID of the scan to track responses
            
        Returns:
            bool: Whether notification was sent successfully
        """
        if not self.target_channel:
            logger.error("No target channel configured")
            return False
            
        try:
            # Create rich embed
            embed = discord.Embed(
                title=title,
                description=message,
                color=discord.Color.blue()
            )
            
            # Add media info if available
            if media_info:
                if 'poster_url' in media_info and media_info['poster_url']:
                    embed.set_thumbnail(url=media_info['poster_url'])
                
                # Add other media info fields
                for key, value in media_info.items():
                    if key != 'poster_url' and value:
                        embed.add_field(name=key.capitalize(), value=value, inline=True)
            
            # Add footer
            embed.set_footer(text="Scanly Media Monitor")
            
            # Send the message
            message = await self.target_channel.send(embed=embed)
            
            # If options are provided, add reaction options
            if options and scan_id:
                # Store in active scans
                active_scans[scan_id] = {
                    'message_id': message.id,
                    'options': options
                }
                
                # Add reactions for each option
                option_emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣"]
                for i, _ in enumerate(options[:4]):  # Limit to 4 options
                    await message.add_reaction(option_emojis[i])
                    
            return True
        except Exception as e:
            logger.error(f"Error sending media notification: {e}")
            logger.error(traceback.format_exc())
            return False

def start_bot():
    """Start the Discord bot."""
    global bot_instance, bot_thread, is_bot_running
    
    try:
        # Get the token from environment
        token = os.environ.get('DISCORD_BOT_TOKEN', '')
        
        if not token:
            logger.error("No Discord token provided in environment variables")
            return False
            
        # Create bot instance using commands.Bot 
        intents = discord.Intents.default()
        intents.message_content = True  # Enable message content intent if needed
        bot_instance = ScanlyBot(channel_id=None)
        
        # Start the bot in a separate thread
        bot_thread = threading.Thread(target=lambda: asyncio.run(bot_instance.start(token)), daemon=True)
        bot_thread.start()
        
        logger.info("Discord bot started successfully")
        return True
        
    except Exception as e:
        logger.error(f"Failed to start Discord bot: {e}")
        logger.error(traceback.format_exc())
        return False

def stop_bot():
    """Stop the Discord bot if running."""
    global bot_instance, bot_thread, is_bot_running
    
    if not is_bot_running or not bot_instance:
        logger.info("No bot is running")
        return True
        
    try:
        # Create a new event loop for clean shutdown
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # Schedule the bot to close and run it
        loop.run_until_complete(bot_instance.close())
        
        # Clean up
        is_bot_running = False
        bot_instance = None
        
        # Don't wait for thread to join - let it terminate naturally
        logger.info("Discord bot stopped successfully")
        return True
    except Exception as e:
        logger.error(f"Error stopping Discord bot: {e}")
        return False

def register_callback(event_name, callback_func):
    """Register a callback function for a specific event."""
    global command_callbacks
    command_callbacks[event_name] = callback_func
    logger.info(f"Registered callback for {event_name}")

def send_notification(title, message, media_info=None, options=None, scan_id=None):
    """Send a notification via the Discord bot."""
    global bot_instance
    
    if not is_bot_running or not bot_instance:
        logger.error("Discord bot is not running")
        return False
        
    try:
        # Create a new event loop for sending notification
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # Wait for bot to be ready
        loop.run_until_complete(asyncio.wait_for(bot_instance.ready_event.wait(), timeout=10))
        
        # Send the notification
        result = loop.run_until_complete(
            bot_instance.send_media_notification(title, message, media_info, options, scan_id)
        )
        
        loop.close()
        return result
    except Exception as e:
        logger.error(f"Error sending notification: {e}")
        return False

def test_bot_connection():
    """Test the Discord bot connection."""
    token = os.environ.get('DISCORD_BOT_TOKEN', '')
    
    if not token:
        logger.error("Discord bot token not configured")
        return False
        
    try:
        # Create minimal client just for testing connection
        intents = discord.Intents.default()
        test_client = commands.Bot(command_prefix="!", intents=intents)
        
        # Define async function for test
        async def test_connect():
            try:
                await test_client.login(token)
                await test_client.close()
                return True
            except discord.LoginFailure:
                logger.error("Invalid Discord token")
                return False
            except Exception as e:
                logger.error(f"Error testing Discord connection: {e}")
                return False
                
        # Run connection test
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(test_connect())
        loop.close()
        
        return result
    except Exception as e:
        logger.error(f"Error running connection test: {e}")
        return False

# For testing the module directly
if __name__ == "__main__":
    # Set up basic logging
    logging.basicConfig(level=logging.INFO,
                       format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # Start the bot
    if start_bot():
        print("Bot started successfully")
    else:
        print("Failed to start bot")