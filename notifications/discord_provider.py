from .base import NotificationProvider
import discord
import logging
from typing import List, Optional

logger = logging.getLogger("discord_bot")


class DiscordNotificationProvider(NotificationProvider):
    def __init__(self, client: discord.Client):
        self.client = client

    async def initialize(self) -> None:
        # No initialization needed for Discord as we're using the existing client
        pass

    def _format_for_discord(self, message: str) -> dict:
        """Return a dict describing how to send the message on Discord.

        We prefer to send a single embed when the message fits. If the
        message is very long, split into chunks of safe size and send as
        plain messages.
        """
        # Discord embed description limit is 4096; keep margin
        EMBED_LIMIT = 4000
        # Discord message character limit is 2000 per message when not using embeds
        MESSAGE_LIMIT = 2000

        if len(message) <= EMBED_LIMIT:
            embed = discord.Embed(description=message)
            return {"embed": embed}

        # If it's too long for an embed, split into message-sized chunks
        chunks: List[str] = []
        idx = 0
        while idx < len(message):
            chunks.append(message[idx : idx + MESSAGE_LIMIT])
            idx += MESSAGE_LIMIT
        return {"chunks": chunks}

    async def send_notification(self, user_id: str, message: str) -> bool:
        try:
            # Convert string user_id to int since Discord uses integers for IDs
            discord_user_id = int(user_id)
            user = await self.client.fetch_user(discord_user_id)

            if not user:
                logger.warning(f"Could not find Discord user with ID {user_id}")
                return False

            formatted = self._format_for_discord(message)

            # Send as embed when available
            if "embed" in formatted and formatted["embed"] is not None:
                await user.send(embed=formatted["embed"])
            else:
                # Send any chunks sequentially
                for chunk in formatted.get("chunks", [message]):
                    await user.send(chunk)

            logger.info(f"Sent Discord DM to user {user_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to send Discord DM to user {user_id}: {str(e)}")
            return False
