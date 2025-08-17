# This example requires the 'message_content' intent.

import discord
from dotenv import load_dotenv
import os
import datetime
from motor.motor_asyncio import AsyncIOMotorClient
import logging
from logging.handlers import QueueHandler, QueueListener
from queue import SimpleQueue
import asyncio
import uvicorn
from health import app, health_check

# Setup intents
intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True  # Enable voice state tracking
intents.members = True  # Enable member tracking
intents.presences = True  # Enable presence tracking
load_dotenv()
client = discord.Client(intents=intents)

# Setup asynchronous logging using QueueHandler
log_queue = SimpleQueue()
queue_handler = QueueHandler(log_queue)
logger = logging.getLogger("discord_bot")
logger.setLevel(logging.INFO)
logger.addHandler(queue_handler)

# Setup a listener to process log messages
console_handler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
console_handler.setFormatter(formatter)
listener = QueueListener(log_queue, console_handler)
listener.start()

# Database connection with connection pooling and lazy initialization
def get_database():
    try:
        # Get MongoDB Atlas connection string from environment variable
        mongo_url = os.getenv('MONGODB_URL')
        if not mongo_url:
            raise ValueError("MONGODB_URL environment variable is not set")
            
        # Configure MongoDB client with optimized options for Atlas
        mongo_client = AsyncIOMotorClient(
            mongo_url,
            serverSelectionTimeoutMS=5000,  # 5 second timeout
            connectTimeoutMS=10000,  # 10 second timeout
            maxPoolSize=50,  # Increase connection pool size
            minPoolSize=10,  # Keep minimum connections ready
            maxIdleTimeMS=30000,  # Close idle connections after 30 seconds
            retryWrites=True,
            # Add TLS/SSL options required by Atlas
            tls=True,
        )
        
        logger.info("Initializing MongoDB Atlas connection pool")
        return mongo_client, mongo_client.discord_watch
    except Exception as e:
        logger.error(f"Failed to connect to MongoDB Atlas: {str(e)}")
        raise

# Initialize database
async def setup_database():
    logger.info("Database setup complete")

# Initialize the bot and database
async def init():
    # Initialize MongoDB with connection pooling
    mongo_client, db = get_database()
    client.mongo_client = mongo_client
    client.db = db
    
    # Test the connection
    try:
        await client.db.command('ping')
        logger.info("Successfully connected to MongoDB Atlas")
        await setup_database()
        
        # Initialize notification system
        from notifications import NotificationManager, DiscordNotificationProvider, TelegramNotificationProvider
        
        client.notification_manager = NotificationManager()
        # Register Discord notification provider
        client.notification_manager.register_provider('discord', DiscordNotificationProvider(client))
        # Register Telegram notification provider if token is available
        if os.getenv('TELEGRAM_BOT_TOKEN'):
            client.notification_manager.register_provider('telegram', TelegramNotificationProvider())
        
        # Initialize all providers
        await client.notification_manager.initialize_providers()
        
        # Initialize health check service
        health_check.initialize(client, mongo_client, client.notification_manager)
        
    except Exception as e:
        logger.error(f"Failed to connect to MongoDB Atlas: {str(e)}")
        raise

@client.event
async def on_ready():
    logger.info(f'We have logged in as {client.user}')
    # Initial member scan for all servers
    for guild in client.guilds:
        await scan_guild_members(guild)

async def scan_guild_members(guild):
    """Scan and update all members in a guild"""
    now = datetime.datetime.now()
    for member in guild.members:
        roles = [role.name for role in member.roles]
        await client.db.members.update_one(
            {'user_id': member.id, 'server_id': guild.id},
            {
                '$set': {
                    'username': str(member),
                    'nickname': member.nick,
                    'roles': roles,
                    'joined_at': member.joined_at,
                    'last_updated': now
                }
            },
            upsert=True
        )

@client.event
async def on_member_join(member):
    """Track when a member joins the server"""
    now = datetime.datetime.now()
    roles = [role.name for role in member.roles]
    await client.db.members.insert_one({
        'user_id': member.id,
        'server_id': member.guild.id,
        'username': str(member),
        'nickname': member.nick,
        'roles': roles,
        'joined_at': now,
        'last_updated': now
    })
    logger.info(f'Member {member} joined server {member.guild.name}')

@client.event
async def on_member_remove(member):
    """Track when a member leaves the server"""
    await client.db.members.delete_one({
        'user_id': member.id,
        'server_id': member.guild.id
    })
    logger.info(f'Member {member} left server {member.guild.name}')

@client.event
async def on_member_update(before, after):
    """Track member updates (nickname, roles, etc.)"""
    if before.nick != after.nick or set(before.roles) != set(after.roles):
        now = datetime.datetime.now()
        roles = [role.name for role in after.roles]
        await client.db.members.update_one(
            {'user_id': after.id, 'server_id': after.guild.id},
            {
                '$set': {
                    'nickname': after.nick,
                    'roles': roles,
                    'last_updated': now
                }
            }
        )
        logger.info(f'Member {after} updated in server {after.guild.name}')

# Helper function to send notifications about a watched user
async def send_watched_user_notification(user_id: int, message: str):
    try:
        # Find notification preferences for this user
        pref = await client.db.notification_preferences.find_one({'watched_users': str(user_id)})
        
        if pref:
            notifications = {}
            
            # Add Discord notifications if configured
            if 'discord_id' in pref.get('notification_channels', {}):
                notifications['discord'] = pref['notification_channels']['discord_id']
                
            # Add Telegram notifications if configured
            if 'telegram_id' in pref.get('notification_channels', {}):
                notifications['telegram'] = pref['notification_channels']['telegram_id']
                
            if notifications:
                await client.notification_manager.send_notification_all(notifications, message)
                
    except Exception as e:
        logger.error(f"Failed to send notification for user {user_id}: {str(e)}")

@client.event
async def on_presence_update(before, after):
    """Handle presence updates for watched users"""
    # Check if this user is being watched
    pref = await client.db.notification_preferences.find_one({'watched_users': str(after.id)})
    
    if pref:
        # Check for online status change
        if str(before.status) != str(after.status):
            message = f"🟢 User {after.name} is now {after.status}"
            await send_watched_user_notification(after.id, message)

# Enhance on_voice_state_update to track mute and deafen changes and notify about watched users
@client.event
async def on_voice_state_update(member, before, after):
    user_id = member.id
    username = str(member)
    now = datetime.datetime.now()

    # Helper function to get channel and server details
    def get_channel_and_server_info(channel):
        if channel:
            return channel.id, channel.name, channel.guild.id, channel.guild.name
        return None, None, None, None
    # Get details for before and after states
    before_channel_id, before_channel_name, before_server_id, before_server_name = get_channel_and_server_info(before.channel)
    after_channel_id, after_channel_name, after_server_id, after_server_name = get_channel_and_server_info(after.channel)

    # Create voice activity document
    async def log_voice_activity(channel_id, channel_name, server_id, server_name, event_type):
        await client.db.voice_activity.insert_one({
            'user_id': user_id,
            'username': username,
            'channel_id': channel_id,
            'channel_name': channel_name,
            'server_id': server_id,
            'server_name': server_name,
            'event_time': now,
            'event_type': event_type
        })

    if before.channel is None and after.channel is not None:
        logger.info(f"{member} joined {after.channel} at {now}")
        await log_voice_activity(after_channel_id, after_channel_name, after_server_id, after_server_name, 'join')
        
        # Check if this user is being watched
        pref = await client.db.notification_preferences.find_one({'watched_users': str(user_id)})
        if pref:
            message = f"🎙️ User {username} joined voice channel {after_channel_name} in server {after_server_name}"
            await send_watched_user_notification(user_id, message)

    elif before.channel is not None and after.channel is None:
        logger.info(f"{member} left channel {before.channel} at {now}")
        await log_voice_activity(before_channel_id, before_channel_name, before_server_id, before_server_name, 'leave')
        
        # Check if this user is being watched
        pref = await client.db.notification_preferences.find_one({'watched_users': str(user_id)})
        if pref:
            message = f"🔇 User {username} left voice channel {before_channel_name} in server {before_server_name}"
            await send_watched_user_notification(user_id, message)

    elif before.channel is not None and after.channel is not None and before.channel != after.channel:
        logger.info(f"{member} moved from {before.channel} to {after.channel} at {now}")
        await log_voice_activity(before_channel_id, before_channel_name, before_server_id, before_server_name, 'leave')
        await log_voice_activity(after_channel_id, after_channel_name, after_server_id, after_server_name, 'join')

    if before.self_mute != after.self_mute:
        logger.info(f"{member} {'muted' if after.self_mute else 'unmuted'} themselves at {now}")
        await log_voice_activity(after_channel_id, after_channel_name, after_server_id, after_server_name, 
                               'mute' if after.self_mute else 'unmute')

    if before.self_deaf != after.self_deaf:
        logger.info(f"{member} {'deafened' if after.self_deaf else 'undeafened'} themselves at {now}")
        await log_voice_activity(after_channel_id, after_channel_name, after_server_id, after_server_name,
                               'deafen' if after.self_deaf else 'undeafen')

# Run the bot and health check API
async def main():
    # Initialize bot and services
    await init()
    
    # Setup health check API
    config = uvicorn.Config(app, host="0.0.0.0", port=8000, log_level="info")
    server = uvicorn.Server(config)
    
    # Run both the Discord bot and the health check API
    await asyncio.gather(
        client.start(os.getenv('BOT_TOKEN')),
        server.serve()
    )

if __name__ == "__main__":
    asyncio.run(main())