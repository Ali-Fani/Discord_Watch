import os
import html
from .base import NotificationProvider, UserContext
import logging
from telegram.ext import ApplicationBuilder
from telegram import Bot
from telegram.error import TelegramError
from typing import Optional

logger = logging.getLogger("discord_bot")


class TelegramNotificationProvider(NotificationProvider):
    def __init__(self):
        self.bot: Bot = None

    async def initialize(self) -> None:
        token = os.getenv("TELEGRAM_BOT_TOKEN")
        if not token:
            raise ValueError("TELEGRAM_BOT_TOKEN environment variable is not set")

        application = ApplicationBuilder().token(token).build()
        self.bot = application.bot
        logger.info("Telegram notification provider initialized")

    def _format_for_telegram(self, message: str, user_context: Optional[UserContext] = None) -> list:
        """Escape message for HTML parse mode and split into safe chunks.

        Telegram message limit is ~4096 characters; use a conservative limit.
        """
        SAFE_LIMIT = 4000

        # Enhance message with user context if available
        enhanced_message = self._enhance_telegram_message(message, user_context)
        escaped = html.escape(enhanced_message, quote=False)  # Don't escape HTML we add

        if len(escaped) <= SAFE_LIMIT:
            return [escaped]

        chunks = []
        idx = 0
        while idx < len(escaped):
            chunks.append(escaped[idx : idx + SAFE_LIMIT])
            idx += SAFE_LIMIT
        return chunks

    def _enhance_telegram_message(self, message: str, user_context: Optional[UserContext]) -> str:
        """Add user information to the message for Telegram"""
        if not user_context:
            return message

        # Create user info section
        user_info_parts = []

        # Add display name with username if available
        display_name = user_context.get_display_name()
        if user_context.username and user_context.username != display_name:
            user_info_parts.append(f"<b>👤 {display_name}</b> (@{user_context.username})")
        else:
            user_info_parts.append(f"<b>👤 {display_name}</b>")

        # Add user ID
        user_info_parts.append(f"<code>User ID: {user_context.user_id}</code>")

        # Add joined date if available
        if user_context.joined_at:
            joined_date = user_context.get_joined_date_formatted()
            user_info_parts.append(f"📅 Joined: {joined_date}")

        # Add roles if available
        if user_context.roles and len(user_context.roles) > 0:
            roles_text = ", ".join(user_context.roles[:3])  # Limit to first 3 roles for Telegram
            if len(user_context.roles) > 3:
                roles_text += f" (+{len(user_context.roles) - 3} more)"
            user_info_parts.append(f"🏷️ Roles: {roles_text}")

        # Add profile picture note if available
        if user_context.avatar_url:
            user_info_parts.append(f"🖼️ Profile picture available")

        # Combine user info with main message
        user_info_section = "\n".join(user_info_parts)
        enhanced_message = f"{user_info_section}\n\n{message}"

        return enhanced_message

    async def send_notification(self, user_id: str, message: str, user_context: Optional[UserContext] = None) -> bool:
        if not self.bot:
            logger.error("Telegram bot not initialized")
            return False

        try:
            # In this case, user_id should be the Telegram chat ID
            chunks = self._format_for_telegram(message, user_context)
            for chunk in chunks:
                await self.bot.send_message(chat_id=user_id, text=chunk, parse_mode="HTML")

            logger.info(f"Sent Telegram message to user {user_id}")
            return True

        except TelegramError as e:
            logger.error(f"Failed to send Telegram message to user {user_id}: {str(e)}")
            return False
