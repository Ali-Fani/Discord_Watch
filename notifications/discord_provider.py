from .base import NotificationProvider, UserContext
from .config import ColorConfig, infer_action_type
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

    def _format_for_discord(self, message: str, user_context: Optional[UserContext] = None, action_type: Optional[str] = None) -> dict:
        """Return a dict describing how to send the message on Discord.

        We prefer to send a single embed when the message fits. If the
        message is very long, split into chunks of safe size and send as
        plain messages.

        Args:
            message: The notification message
            user_context: User context information for enhanced formatting
            action_type: The type of action that triggered this notification
        """
        # Discord embed description limit is 4096; keep margin
        EMBED_LIMIT = 4000
        # Discord message character limit is 2000 per message when not using embeds
        MESSAGE_LIMIT = 2000

        if len(message) <= EMBED_LIMIT:
            embed = self._create_enhanced_embed(message, user_context, action_type)
            return {"embed": embed}

        # If it's too long for an embed, split into message-sized chunks
        chunks: List[str] = []
        idx = 0
        while idx < len(message):
            chunks.append(message[idx : idx + MESSAGE_LIMIT])
            idx += MESSAGE_LIMIT
        return {"chunks": chunks}

    def _create_enhanced_embed(self, message: str, user_context: Optional[UserContext], action_type: Optional[str] = None) -> discord.Embed:
        """Create an enhanced embed with user information and dynamic coloring

        Args:
            message: The main notification message
            user_context: User context information for enhanced formatting
            action_type: The type of action that triggered this notification (for color coding)
        """
        # Get color based on action type, with fallback to auto-inference
        if action_type:
            color = ColorConfig.get_color(action_type)
        else:
            color = ColorConfig.get_color(infer_action_type(message))

        # Validate color and provide fallback if invalid
        if not ColorConfig.validate_color(color):
            logger.warning(f"Invalid color value {color} for action type {action_type}, using default")
            color = ColorConfig.get_color("default")

        embed = discord.Embed(
            description=message,
            color=color,
            timestamp=discord.utils.utcnow()
        )

        if user_context:
            # Set author with user info
            author_name = user_context.get_display_name()
            if user_context.username and user_context.username != author_name:
                author_name = f"{author_name} ({user_context.username})"

            if user_context.avatar_url:
                embed.set_thumbnail(url=user_context.avatar_url)
                embed.set_author(name=author_name, icon_url=user_context.avatar_url)
            else:
                embed.set_author(name=author_name)

            # Add user information fields
            embed.add_field(
                name="User ID",
                value=f"`{user_context.user_id}`",
                inline=True
            )

            if user_context.joined_at:
                join_date = user_context.get_joined_date_formatted()
                embed.add_field(
                    name="Member Since",
                    value=join_date,
                    inline=True
                )

            if user_context.roles and len(user_context.roles) > 0:
                roles_text = ", ".join(user_context.roles[:5])  # Limit to first 5 roles
                if len(user_context.roles) > 5:
                    roles_text += f" (+{len(user_context.roles) - 5} more)"
                embed.add_field(
                    name="Roles",
                    value=roles_text,
                    inline=False
                )

        return embed

    async def send_notification(self, user_id: str, message: str, user_context: Optional[UserContext] = None, action_type: Optional[str] = None) -> bool:
        try:
            # Convert string user_id to int since Discord uses integers for IDs
            discord_user_id = int(user_id)
            user = await self.client.fetch_user(discord_user_id)

            if not user:
                logger.warning(f"Could not find Discord user with ID {user_id}")
                return False

            formatted = self._format_for_discord(message, user_context, action_type)

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
