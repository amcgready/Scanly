
import os
import sys
import asyncio
import logging
import signal

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger('discord_bot')

# Remove any path that ends with 'src' to avoid project conflicts
sys.path = [p for p in sys.path if not p.endswith('src')]

try:
    import discord
    from discord.ext import commands
    
    # Bot token from environment
    token = os.environ.get('DISCORD_BOT_TOKEN', '')
    if not token:
        logger.error("Discord bot token not set")
        sys.exit(1)
    
    # Set up intents
    intents = discord.Intents.default()
    intents.message_content = True
    
    # Create bot
    bot = commands.Bot(command_prefix='!', intents=intents)
    
    @bot.event
    async def on_ready():
        logger.info(f'Logged in as {bot.user} (ID: {bot.user.id})')
        logger.info(f'Bot version: 1.0.0')
        await bot.sync_commands()  # Sync any slash commands
        logger.info('Application commands synced')

    # Some basic commands
    @bot.command(name='ping')
    async def ping(ctx):
        await ctx.send('Pong! Bot is running.')
        
    @bot.command(name='status')
    async def status(ctx):
        await ctx.send(f'Bot is online and working! Connected to {len(bot.guilds)} servers.')
    
    # Define cleanup for graceful shutdown
    def signal_handler(sig, frame):
        logger.info("Shutdown signal received")
        loop = asyncio.get_event_loop()
        loop.create_task(bot.close())
        sys.exit(0)
    
    # Register the signal handler
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Run the bot
    logger.info("Starting bot...")
    bot.run(token)
    
except Exception as e:
    logger.error(f"Error starting bot: {e}")
    sys.exit(1)
