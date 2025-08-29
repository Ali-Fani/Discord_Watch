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

# Import notification components
from notifications import (
    NotificationManager,
    DiscordNotificationProvider,
    TelegramNotificationProvider,
    UserContext,
    ActionType,
    infer_action_type,
)

# Presence state cache to prevent duplicate notifications
# Maps user_id -> last_known_status
presence_cache = {}

# Voice channel state cache to prevent duplicate notifications
# Maps user_id -> last_voice_state_signature (channel_id + timestamp)
voice_state_cache = {}

# Watched users currently in voice channels
# Maps channel_id -> Set[UserID] for quick lookup of watched users in channels
watched_channel_users = {}

# Setup asynchronous logging using QueueHandler
log_queue = SimpleQueue()
queue_handler = QueueHandler(log_queue)
logger = logging.getLogger("discord_bot")
logger.setLevel(logging.INFO)
logger.addHandler(queue_handler)

# Setup a listener to process log messages
console_handler = logging.StreamHandler()
formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
console_handler.setFormatter(formatter)
listener = QueueListener(log_queue, console_handler)
listener.start()


# Database connection with connection pooling and lazy initialization
def get_database():
    try:
        # Get MongoDB Atlas connection string from environment variable
        mongo_url = os.getenv("MONGODB_URL")
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


# Helper functions for user context
async def get_discord_user_context(user_id: int) -> UserContext:
    """Get user context for Discord notifications"""
    try:
        # Fetch Discord user
        discord_user = await client.fetch_user(user_id)
        if not discord_user:
            # Return basic context if user not found
            return UserContext(
                user_id=str(user_id),
                username=f"User {user_id}",
                display_name=f"User {user_id}"
            )

        # Get member data from database for guild-specific info
        member_data = None
        for guild in client.guilds:
            member_doc = await client.db.members.find_one(
                {"user_id": user_id, "server_id": guild.id}
            )
            if member_doc:
                member_data = member_doc
                break

        return UserContext.from_discord_user(discord_user, member_data)

    except Exception as e:
        logger.error(f"Failed to get Discord user context for {user_id}: {e}")
        # Return basic fallback context
        return UserContext(
            user_id=str(user_id),
            username=f"User {user_id}",
            display_name=f"User {user_id}"
        )

async def get_basic_user_context_for_telegram(user_id: str) -> UserContext:
    """Get basic user context for Telegram notifications

    Note: Telegram has limited user data access, so this is mostly
    for consistency with the interface. Full user info would require
    the user to have previously interacted with the bot.
    """
    return UserContext(
        user_id=user_id,
        username=f"User {user_id}",
        display_name=f"User {user_id}"
    )

# Initialize the bot and database
async def init():
    # Initialize MongoDB with connection pooling
    mongo_client, db = get_database()
    client.mongo_client = mongo_client
    client.db = db

    # Test the connection
    try:
        await client.db.command("ping")
        logger.info("Successfully connected to MongoDB Atlas")
        await setup_database()

        # Initialize notification system (imports already done at top)

        client.notification_manager = NotificationManager()
        # Register Discord notification provider
        client.notification_manager.register_provider(
            "discord", DiscordNotificationProvider(client)
        )
        # Register Telegram notification provider if token is available
        if os.getenv("TELEGRAM_BOT_TOKEN"):
            client.notification_manager.register_provider(
                "telegram", TelegramNotificationProvider()
            )

        # Initialize all providers
        await client.notification_manager.initialize_providers()

        # Initialize health check service
        health_check.initialize(client, mongo_client, client.notification_manager)

    except Exception as e:
        logger.error(f"Failed to connect to MongoDB Atlas: {str(e)}")
        raise


@client.event
async def on_ready():
    logger.info(f"We have logged in as {client.user}")
    # Initial member scan for all servers
    for guild in client.guilds:
        await scan_guild_members(guild)


async def scan_guild_members(guild):
    """Scan and update all members in a guild"""
    now = datetime.datetime.now()
    for member in guild.members:
        roles = [role.name for role in member.roles]
        await client.db.members.update_one(
            {"user_id": member.id, "server_id": guild.id},
            {
                "$set": {
                    "username": str(member),
                    "nickname": member.nick,
                    "roles": roles,
                    "joined_at": member.joined_at,
                    "last_updated": now,
                }
            },
            upsert=True,
        )


@client.event
async def on_member_join(member):
    """Track when a member joins the server"""
    now = datetime.datetime.now()
    roles = [role.name for role in member.roles]
    await client.db.members.insert_one(
        {
            "user_id": member.id,
            "server_id": member.guild.id,
            "username": str(member),
            "nickname": member.nick,
            "roles": roles,
            "joined_at": now,
            "last_updated": now,
        }
    )
    logger.info(f"Member {member} joined server {member.guild.name}")


@client.event
async def on_member_remove(member):
    """Track when a member leaves the server"""
    await client.db.members.delete_one(
        {"user_id": member.id, "server_id": member.guild.id}
    )
    logger.info(f"Member {member} left server {member.guild.name}")


@client.event
async def on_member_update(before, after):
    """Track member updates (nickname, roles, etc.)"""
    if before.nick != after.nick or set(before.roles) != set(after.roles):
        now = datetime.datetime.now()
        roles = [role.name for role in after.roles]
        await client.db.members.update_one(
            {"user_id": after.id, "server_id": after.guild.id},
            {"$set": {"nickname": after.nick, "roles": roles, "last_updated": now}},
        )
        logger.info(f"Member {after} updated in server {after.guild.name}")


# Helper function to get current watched users in a channel
async def get_watched_users_in_channel(channel_id: int) -> list:
    """Get list of watched users currently in a voice channel"""
    return list(watched_channel_users.get(channel_id, set()))

# Helper function to check if a user is being watched
async def is_user_watched(user_id: int) -> bool:
    """Check if a user is being watched in notification preferences"""
    try:
        pref = await client.db.notification_preferences.find_one(
            {"watched_users": str(user_id)}
        )
        return pref is not None
    except Exception as e:
        logger.error(f"Error checking if user {user_id} is watched: {str(e)}")
        return False

# Helper function to get other users in a voice channel (excluding the joining user)
async def get_other_users_in_channel(channel, exclude_user_id: int) -> tuple:
    """Get information about other users in a channel, including watched status"""
    if not channel:
        return [], []

    try:
        members = channel.members
        other_users = []
        watched_users_present = []

        for member in members:
            if member.id != exclude_user_id:
                other_users.append(str(member))

                # Check if this other user is being watched
                if await is_user_watched(member.id):
                    watched_users_present.append(str(member))

        return other_users, watched_users_present
    except Exception as e:
        logger.error(f"Error getting users in channel {channel.name}: {str(e)}")
        return [], []

# Helper function to create voice state signature for deduplication
def get_voice_state_signature(user_id: int, channel_id: int, event_type: str) -> str:
    """Create a signature for voice state changes to prevent duplicate notifications"""
    return f"{user_id}:{channel_id}:{event_type}:{int(datetime.datetime.now().timestamp())}"

# Helper function to manage watched users cache for channels
def update_channel_cache(user_id: int, channel_id: int, action: str):
    """Update the watched users cache for channels

    Args:
        user_id: The user ID
        channel_id: The channel ID (can be None for leaving)
        action: 'join', 'leave', or 'move'
    """
    try:
        if action == 'leave' and channel_id is not None:
            # Remove user from old channel
            if channel_id in watched_channel_users:
                watched_channel_users[channel_id].discard(user_id)
                # Clean up empty sets
                if not watched_channel_users[channel_id]:
                    del watched_channel_users[channel_id]

        elif action == 'join' and channel_id is not None:
            # Add user to new channel
            if channel_id not in watched_channel_users:
                watched_channel_users[channel_id] = set()
            watched_channel_users[channel_id].add(user_id)

        elif action == 'move' and channel_id is not None:
            # This should be handled by separate leave/join calls

            # But as a fallback, ensure user is in correct channel
            # We'll let the separate events handle this properly
            pass

        logger.debug(f"Updated channel cache for user {user_id}: action={action}, channel={channel_id}")
    except Exception as e:
        logger.error(f"Error updating channel cache for user {user_id}: {str(e)}")

# Helper function to send notifications about a watched user
async def send_watched_user_notification(user_id: int, message: str, action_type: str = None, voice_channel_id: int = None, server_id: int = None):
    try:
        # Find notification preferences for this user
        pref = await client.db.notification_preferences.find_one(
            {"watched_users": str(user_id)}
        )

        if pref:
            notifications = {}

            # Add Discord notifications if configured
            if "discord_id" in pref.get("notification_channels", {}):
                notifications["discord"] = pref["notification_channels"]["discord_id"]

            # Add Telegram notifications if configured
            if "telegram_id" in pref.get("notification_channels", {}):
                notifications["telegram"] = pref["notification_channels"]["telegram_id"]

            if notifications:
                # Get user context for enhanced notifications
                user_context = await get_discord_user_context(user_id)

                # Infer action type from message if not provided
                if action_type is None:
                    action_type = infer_action_type(message)

                await client.notification_manager.send_notification_all(
                    notifications, message, user_context, action_type, voice_channel_id, server_id
                )

    except Exception as e:
        logger.error(f"Failed to send notification for user {user_id}: {str(e)}")


@client.event
async def on_presence_update(before, after):
    """Handle presence updates for watched users - with deduplication"""
    user_id = after.id
    username = str(after)
    new_status = str(after.status)  # online, offline, idle, dnd

    # Check if this is actually a state change using our cache
    last_status = presence_cache.get(user_id)

    # Only proceed if there's an actual status change
    if last_status != new_status:
        # Update the cache with the new status
        presence_cache[user_id] = new_status

        # Log the status change
        logger.info(
            f"User {username} ({user_id}) status changed from {last_status} to {new_status}"
        )

        # Check if this user is being watched
        pref = await client.db.notification_preferences.find_one(
            {"watched_users": str(user_id)}
        )
        if pref:
            message = f"👤 User {username} is now {new_status}"
            # Determine action type based on status
            if new_status.lower() == "online":
                action_type = ActionType.STATUS_ONLINE
            elif new_status.lower() == "offline":
                action_type = ActionType.STATUS_OFFLINE
            elif new_status.lower() == "idle":
                action_type = ActionType.STATUS_IDLE
            elif new_status.lower() == "dnd":
                action_type = ActionType.STATUS_DND
            else:
                action_type = ActionType.STATUS_ONLINE  # fallback

            await send_watched_user_notification(user_id, message, action_type)
    else:
        # This is a duplicate event, log it but don't send notification
        logger.debug(
            f"Duplicate presence update ignored for user {username} ({user_id}): {new_status}"
        )


# Enhanced on_voice_state_update with comprehensive voice channel monitoring and notifications
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
    before_channel_id, before_channel_name, before_server_id, before_server_name = (
        get_channel_and_server_info(before.channel)
    )
    after_channel_id, after_channel_name, after_server_id, after_server_name = (
        get_channel_and_server_info(after.channel)
    )

    # Create voice state signature for deduplication
    voice_signature = None
    if after_channel_id:
        voice_signature = get_voice_state_signature(user_id, after_channel_id, "join")
    elif before_channel_id:
        voice_signature = get_voice_state_signature(user_id, before_channel_id, "leave")

    # Check for duplicate events using cache
    if voice_signature and voice_signature == voice_state_cache.get(user_id):
        logger.debug(f"Duplicate voice state update ignored for user {username} ({user_id})")
        return

    # Update cache with new signature
    if voice_signature:
        voice_state_cache[user_id] = voice_signature

    # Create voice activity document
    async def log_voice_activity(
        channel_id, channel_name, server_id, server_name, event_type
    ):
        await client.db.voice_activity.insert_one(
            {
                "user_id": user_id,
                "username": username,
                "channel_id": channel_id,
                "channel_name": channel_name,
                "server_id": server_id,
                "server_name": server_name,
                "event_time": now,
                "event_type": event_type,
            }
        )

    # Helper function to send notifications to all watchers of a specific watched user
    async def send_notification_to_watchers(watched_user_id: int, message: str):
        try:
            pref = await client.db.notification_preferences.find_one(
                {"watched_users": str(watched_user_id)}
            )
            if pref:
                notifications = {}

                # Add Discord notifications if configured
                if "discord_id" in pref.get("notification_channels", {}):
                    notifications["discord"] = pref["notification_channels"]["discord_id"]

                # Add Telegram notifications if configured
                if "telegram_id" in pref.get("notification_channels", {}):
                    notifications["telegram"] = pref["notification_channels"]["telegram_id"]

                if notifications:
                    # Get user context for enhanced notifications
                    user_context = await get_discord_user_context(watched_user_id)
                    await client.notification_manager.send_notification_all(
                        notifications, message, user_context
                    )
        except Exception as e:
            logger.error(f"Failed to send notification for watched user {watched_user_id}: {str(e)}")

    # Handle user joining a voice channel
    if before.channel is None and after.channel is not None:
        logger.info(f"{member} joined {after.channel} at {now}")
        await log_voice_activity(
            after_channel_id,
            after_channel_name,
            after_server_id,
            after_server_name,
            "join",
        )

        # Get information about other users already in the channel
        other_users, watched_users_present = await get_other_users_in_channel(after.channel, user_id)
        watched_users_in_channel = len(watched_users_present)

        # Check if this user is being watched
        user_is_watched = await is_user_watched(user_id)

        if user_is_watched:
            # This is a watched user joining - check for others present
            if watched_users_present:
                others_text = ", ".join(watched_users_present)
                message = f"👥 User {username} joined voice channel {after_channel_name} in server {after_server_name}. In the same voice channel: {others_text}"
            else:
                message = f"🎙️ User {username} joined voice channel {after_channel_name} in server {after_server_name}"

            await send_watched_user_notification(user_id, message, ActionType.VOICE_JOIN, after_channel_id, after_server_id)

        # Check if there are already watched users in this channel
        if watched_users_in_channel > 0 and not user_is_watched:
            # This is a non-watched user joining a channel with watched users
            # Send notification to all watchers about this non-watched user joining
            for watched_user_in_channel in await get_watched_users_in_channel(after_channel_id):
                try:
                    watched_pref = await client.db.notification_preferences.find_one(
                        {"watched_users": str(watched_user_in_channel)}
                    )
                    if watched_pref:
                        message = f"👤 User {username} joined voice channel {after_channel_name} in server {after_server_name}, where watched user is already present"
                        await send_notification_to_watchers(watched_user_in_channel, message)
                except Exception as e:
                    logger.error(f"Error sending notification to watcher {watched_user_in_channel}: {str(e)}")

        # Update channel cache if this is a watched user
        if user_is_watched:
            update_channel_cache(user_id, after_channel_id, 'join')

    # Handle user leaving a voice channel
    elif before.channel is not None and after.channel is None:
        logger.info(f"{member} left channel {before.channel} at {now}")
        await log_voice_activity(
            before_channel_id,
            before_channel_name,
            before_server_id,
            before_server_name,
            "leave",
        )

        # Check if this user is being watched
        pref = await client.db.notification_preferences.find_one(
            {"watched_users": str(user_id)}
        )
        if pref:
            message = f"🔇 User {username} left voice channel {before_channel_name} in server {before_server_name}"
            await send_watched_user_notification(user_id, message, ActionType.VOICE_LEAVE, before_channel_id, before_server_id)

        # Update channel cache if this was a watched user
        user_is_watched = await is_user_watched(user_id)
        if user_is_watched:
            update_channel_cache(user_id, before_channel_id, 'leave')

    # Handle user moving between voice channels
    elif (
        before.channel is not None
        and after.channel is not None
        and before.channel != after.channel
    ):
        logger.info(f"{member} moved from {before.channel} to {after.channel} at {now}")

        # Log leave from old channel
        await log_voice_activity(
            before_channel_id,
            before_channel_name,
            before_server_id,
            before_server_name,
            "leave",
        )
        # Log join to new channel
        await log_voice_activity(
            after_channel_id,
            after_channel_name,
            after_server_id,
            after_server_name,
            "join",
        )

        # Check if this user is being watched
        pref = await client.db.notification_preferences.find_one(
            {"watched_users": str(user_id)}
        )
        if pref:
            message = f"🔄 User {username} moved from voice channel {before_channel_name} to {after_channel_name} in server {after_server_name}"
            await send_watched_user_notification(user_id, message, ActionType.VOICE_MOVE, after_channel_id, after_server_id)

        # Update channel cache for watched users
        user_is_watched = await is_user_watched(user_id)
        if user_is_watched:
            update_channel_cache(user_id, before_channel_id, 'leave')
            update_channel_cache(user_id, after_channel_id, 'join')

            # Check if the new channel has other watched users
            other_users, watched_users_present = await get_other_users_in_channel(after.channel, user_id)
            if watched_users_present:
                others_text = ", ".join(watched_users_present)
                message = f"👥 User {username} moved to voice channel {after_channel_name} in server {after_server_name}. In the same voice channel: {others_text}"
                await send_watched_user_notification(user_id, message, ActionType.VOICE_MOVE, after_channel_id, after_server_id)

    # Handle mute status changes
    if before.self_mute != after.self_mute:
        logger.info(
            f"{member} {'muted' if after.self_mute else 'unmuted'} themselves at {now}"
        )
        await log_voice_activity(
            after_channel_id,
            after_channel_name,
            after_server_id,
            after_server_name,
            "mute" if after.self_mute else "unmute",
        )

    # Handle deafen status changes
    if before.self_deaf != after.self_deaf:
        logger.info(
            f"{member} {'deafened' if after.self_deaf else 'undeafened'} themselves at {now}"
        )
        await log_voice_activity(
            after_channel_id,
            after_channel_name,
            after_server_id,
            after_server_name,
            "deafen" if after.self_deaf else "undeafen",
        )


# Run the bot and health check API
async def main():
    # Initialize bot and services
    await init()

    # Setup health check API
    config = uvicorn.Config(app, host="0.0.0.0", port=8000, log_level="info")
    server = uvicorn.Server(config)

    # Run both the Discord bot and the health check API
    await asyncio.gather(client.start(os.getenv("BOT_TOKEN")), server.serve())


if __name__ == "__main__":
    asyncio.run(main())
