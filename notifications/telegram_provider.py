import os
from .base import NotificationProvider
import logging
from telegram.ext import ApplicationBuilder
from telegram import Bot
from telegram.error import TelegramError

logger = logging.getLogger("discord_bot")

class TelegramNotificationProvider(NotificationProvider):
    def __init__(self):
        self.bot: Bot = None
        
    async def initialize(self) -> None:
        token = os.getenv('TELEGRAM_BOT_TOKEN')
        if not token:
            raise ValueError("TELEGRAM_BOT_TOKEN environment variable is not set")
        
        application = ApplicationBuilder().token(token).build()
        self.bot = application.bot
        logger.info("Telegram notification provider initialized")
    
    async def send_notification(self, user_id: str, message: str) -> bool:
        if not self.bot:
            logger.error("Telegram bot not initialized")
            return False
            
        try:
            # In this case, user_id should be the Telegram chat ID
            await self.bot.send_message(chat_id=user_id, text=message)
            logger.info(f"Sent Telegram message to user {user_id}")
            return True
            
        except TelegramError as e:
            logger.error(f"Failed to send Telegram message to user {user_id}: {str(e)}")
            return False
