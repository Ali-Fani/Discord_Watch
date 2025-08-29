from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

@dataclass
class UserContext:
    """User context information for enhanced notifications"""
    user_id: str
    username: str
    display_name: Optional[str] = None
    avatar_url: Optional[str] = None
    joined_at: Optional[datetime] = None
    nickname: Optional[str] = None
    roles: Optional[list] = None

    @classmethod
    def from_discord_user(cls, user, member_data=None):
        """Create UserContext from Discord user and optional member data"""
        avatar_url = None
        if user.display_avatar:
            avatar_url = user.display_avatar.url

        ctx = cls(
            user_id=str(user.id),
            username=user.name,
            display_name=getattr(user, 'global_name', None) or user.name,
            avatar_url=avatar_url
        )

        if member_data:
            ctx.joined_at = member_data.get('joined_at')
            ctx.nickname = member_data.get('nickname')
            ctx.roles = member_data.get('roles', [])

        return ctx

    @classmethod
    def from_telegram_user(cls, user):
        """Create UserContext from Telegram user (if available)"""
        display_name = user.first_name
        if user.last_name:
            display_name += f" {user.last_name}"

        return cls(
            user_id=str(user.id),
            username=user.username,
            display_name=display_name
        )

    def get_display_name(self) -> str:
        """Get the best display name available"""
        return self.nickname or self.display_name or self.username or f"User {self.user_id}"

    def get_joined_date_formatted(self) -> str:
        """Get formatted joined date or fallback"""
        if self.joined_at:
            return self.joined_at.strftime("%Y-%m-%d %H:%M UTC")
        return "Unknown"

class NotificationProvider(ABC):
    """Base class for notification providers"""

    @abstractmethod
    async def initialize(self) -> None:
        """Initialize the notification provider"""
        pass

    @abstractmethod
    async def send_notification(self, user_id: str, message: str, user_context: Optional[UserContext] = None, action_type: Optional[str] = None) -> bool:
        """Send a notification to a user

        Args:
            user_id: The ID of the user to notify
            message: The message to send
            user_context: User context information for enhanced formatting
            action_type: The type of action that triggered this notification (for color coding)

        Returns:
            bool: True if notification was sent successfully, False otherwise
        """
        pass
