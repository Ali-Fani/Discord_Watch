from typing import Dict, List, Optional
from .base import NotificationProvider, UserContext
from .discord_provider import DiscordNotificationProvider
from .telegram_provider import TelegramNotificationProvider
import logging

logger = logging.getLogger("discord_bot")

class NotificationManager:
    def __init__(self):
        self.providers: Dict[str, NotificationProvider] = {}
        
    def register_provider(self, name: str, provider: NotificationProvider):
        """Register a new notification provider"""
        self.providers[name] = provider
        logger.info(f"Registered notification provider: {name}")
        
    async def initialize_providers(self):
        """Initialize all registered providers"""
        for name, provider in self.providers.items():
            try:
                await provider.initialize()
                logger.info(f"Initialized notification provider: {name}")
            except Exception as e:
                logger.error(f"Failed to initialize provider {name}: {str(e)}")
                
    async def send_notification(self, provider_name: str, user_id: str, message: str, user_context: Optional[UserContext] = None, action_type: Optional[str] = None, voice_channel_id: Optional[int] = None, server_id: Optional[int] = None) -> bool:
        """Send a notification using a specific provider"""
        provider = self.providers.get(provider_name)
        if not provider:
            logger.error(f"No provider found with name: {provider_name}")
            return False

        return await provider.send_notification(user_id, message, user_context, action_type, voice_channel_id, server_id)

    async def send_notification_all(self, user_notifications: Dict[str, str], message: str, user_context: Optional[UserContext] = None, action_type: Optional[str] = None, voice_channel_id: Optional[int] = None, server_id: Optional[int] = None) -> Dict[str, bool]:
        """Send notifications to a user through multiple providers

        Args:
            user_notifications: Dict mapping provider names to user IDs for that provider
            message: The message to send
            user_context: User context information for enhanced formatting
            action_type: The type of action that triggered this notification
            voice_channel_id: Optional voice channel ID for Discord voice channel links
            server_id: Optional server ID (required if voice_channel_id is provided)

        Returns:
            Dict mapping provider names to success status
        """
        results = {}
        for provider_name, user_id in user_notifications.items():
            results[provider_name] = await self.send_notification(provider_name, user_id, message, user_context, action_type, voice_channel_id, server_id)
        return results

    async def cleanup_provider_cache(self, provider_name: str) -> Optional[Dict[str, int]]:
        """Clean up cache for a specific provider if it has a cleanup method"""
        provider = self.providers.get(provider_name)
        if provider and hasattr(provider, 'profile_picture_manager') and provider.profile_picture_manager:
            if hasattr(provider.profile_picture_manager, 'cleanup_cache'):
                return await provider.profile_picture_manager.cleanup_cache()
        return None

    async def cleanup_all_provider_caches(self) -> Dict[str, Optional[Dict[str, int]]]:
        """Clean up caches for all providers"""
        results = {}
        for provider_name in self.providers.keys():
            results[provider_name] = await self.cleanup_provider_cache(provider_name)
        return results
