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
        """Format message for Telegram HTML parse mode and split into safe chunks.

        Telegram message limit is ~4096 characters; use a conservative limit.
        This method preserves HTML formatting tags while sanitizing user content.
        """
        SAFE_LIMIT = 4000

        # Escape the original message content (user input) for safety
        escaped_message = html.escape(message, quote=False)

        # Enhance message with user context if available (adds HTML formatting)
        enhanced_message = self._enhance_telegram_message(escaped_message, user_context)

        # Sanitize the final HTML to ensure it's valid
        sanitized_message = self._sanitize_telegram_html(enhanced_message)

        # Do NOT escape the final sanitized message - preserve our HTML tags
        if len(sanitized_message) <= SAFE_LIMIT:
            return [sanitized_message]

        chunks = []
        idx = 0
        while idx < len(sanitized_message):
            chunks.append(sanitized_message[idx : idx + SAFE_LIMIT])
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

    def _sanitize_telegram_html(self, html_content: str) -> str:
        """Sanitize HTML content for Telegram to remove unsupported tags and fix common issues.

        Telegram HTML supports: <b>, <i>, <u>, <s>, <code>, <pre>, <a>
        """
        import re

        # Define supported HTML tags for Telegram
        SUPPORTED_TAGS = {'b', 'i', 'u', 's', 'code', 'pre', 'a'}

        def is_supported_tag(tag: str) -> bool:
            """Check if a tag is supported by Telegram HTML"""
            clean_tag = tag.lower().strip('<>/')
            return clean_tag in SUPPORTED_TAGS

        def replace_unsupported_tag(match):
            """Replace unsupported HTML tags with plain text"""
            full_match = match.group(0)
            tag_content = match.group(2)

            if is_supported_tag(match.group(1)):
                # Supported tag - keep as is
                return full_match
            else:
                # Unsupported tag - remove tags but keep content
                logger.warning(f"Removing unsupported HTML tag '{match.group(1)}' in Telegram message")
                return tag_content

        # Remove unsupported tags while preserving content
        # Pattern matches <tag>content</tag> where tag is the tag name
        tag_pattern = r'<([^>]+)>(.*?)</\1>'
        sanitized = re.sub(tag_pattern, replace_unsupported_tag, html_content, flags=re.DOTALL | re.IGNORECASE)

        # Handle self-closing tags
        self_closing_pattern = r'<([^>]+) */?>'
        def replace_self_closing(match):
            tag = match.group(1).split()[0]  # Get just the tag name, ignore attributes
            if is_supported_tag(tag):
                return match.group(0)  # Keep supported self-closing tags
            else:
                logger.warning(f"Removing unsupported self-closing HTML tag '{tag}' in Telegram message")
                return ""  # Remove unsupported self-closing tags

        sanitized = re.sub(self_closing_pattern, replace_self_closing, sanitized)

        # Basic validation - ensure we don't have broken HTML structure
        # Check for unclosed tags (simple heuristic)
        open_count = sanitized.count('<') - sanitized.count('<a href=')  # <a> tags need special handling
        close_count = sanitized.count('>')
        if open_count * 2 != close_count:
            logger.warning(f"Potential HTML structure issue detected in Telegram message: open_tags={open_count}, close_tags={close_count}")

        return sanitized

    async def send_notification(self, user_id: str, message: str, user_context: Optional[UserContext] = None, action_type: Optional[str] = None, voice_channel_id: Optional[int] = None, server_id: Optional[int] = None) -> bool:
        """Send notification to Telegram user

        Note: voice_channel_id and server_id parameters are ignored for Telegram
        as it doesn't support clickable Discord voice channel links.
        """
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
