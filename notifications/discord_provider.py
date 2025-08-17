from .base import NotificationProvider
import discord
import logging

logger = logging.getLogger("discord_bot")

class DiscordNotificationProvider(NotificationProvider):
    def __init__(self, client: discord.Client):
        self.client = client
    
    async def initialize(self) -> None:
        # No initialization needed for Discord as we're using the existing client
        pass
    
    async def send_notification(self, user_id: str, message: str) -> bool:
        try:
            # Convert string user_id to int since Discord uses integers for IDs
            discord_user_id = int(user_id)
            user = await self.client.fetch_user(discord_user_id)
            
            if user:
                await user.send(message)
                logger.info(f"Sent Discord DM to user {user_id}")
                return True
            else:
                logger.warning(f"Could not find Discord user with ID {user_id}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to send Discord DM to user {user_id}: {str(e)}")
            return False
