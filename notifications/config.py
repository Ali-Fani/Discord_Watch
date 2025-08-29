"""
Notification configuration module for Discord Watch Bot.

This module provides configurable color schemes for Discord embeds and action type constants
for categorizing different types of notifications.
"""
from typing import Dict, Optional
import os


class ActionType:
    """Constants for different action types that can trigger notifications"""

    # Voice Channel Actions
    VOICE_JOIN = "voice_join"
    VOICE_LEAVE = "voice_leave"
    VOICE_MOVE = "voice_move"
    VOICE_MUTE = "voice_mute"
    VOICE_UNMUTE = "voice_unmute"
    VOICE_DEAFEN = "voice_deafen"
    VOICE_UNDEAFEN = "voice_undeafen"

    # User Status Actions
    STATUS_ONLINE = "status_online"
    STATUS_OFFLINE = "status_offline"
    STATUS_IDLE = "status_idle"
    STATUS_DND = "status_dnd"

    # Server Actions
    MEMBER_JOIN = "member_join"
    MEMBER_LEAVE = "member_leave"
    MEMBER_UPDATE = "member_update"

    # Warning Actions
    WARNING = "warning"
    ERROR = "error"

    # Admin Actions
    ADMIN = "admin"
    DEFAULT = "default"


class ColorConfig:
    """
    Configuration class for Discord embed colors based on action types.

    Colors can be configured via environment variables for easy customization.
    Format: DISCORD_COLOR_<ACTION_TYPE> = hex_color (without #)
    Example: DISCORD_COLOR_VOICE_JOIN=00ff00
    """

    # Default color scheme - vibrant and distinct colors
    _DEFAULT_COLORS = {
        ActionType.VOICE_JOIN: 0x00ff00,     # Green - positive action
        ActionType.VOICE_LEAVE: 0xff0000,    # Red - negative action
        ActionType.VOICE_MOVE: 0x0080ff,     # Blue - informational
        ActionType.VOICE_MUTE: 0xffff00,     # Yellow - neutral/warning
        ActionType.VOICE_UNMUTE: 0x00ff00,   # Green - back to normal
        ActionType.VOICE_DEAFEN: 0xffa500,   # Orange - attention needed
        ActionType.VOICE_UNDEAFEN: 0x00ff00, # Green - back to normal

        ActionType.STATUS_ONLINE: 0x00ff00,   # Green - available
        ActionType.STATUS_OFFLINE: 0x808080,  # Gray - unavailable
        ActionType.STATUS_IDLE: 0xffa500,     # Orange - maybe available
        ActionType.STATUS_DND: 0xff0000,      # Red - do not disturb

        ActionType.MEMBER_JOIN: 0x32cd32,     # LimeGreen - welcome
        ActionType.MEMBER_LEAVE: 0xdc143c,    # Crimson - goodbye
        ActionType.MEMBER_UPDATE: 0x1e90ff,   # DodgerBlue - info change

        ActionType.WARNING: 0xffff00,         # Yellow - caution
        ActionType.ERROR: 0xff0000,          # Red - problem
        ActionType.ADMIN: 0x800080,          # Purple - authority

        ActionType.DEFAULT: 0x00ff00,        # Green - fallback
    }

    @classmethod
    def get_color(cls, action_type: Optional[str] = None) -> int:
        """
        Get the color value for a given action type, with fallback to DEFAULT.

        Args:
            action_type: The action type to get color for

        Returns:
            Integer color value for Discord embed
        """
        if not action_type:
            action_type = ActionType.DEFAULT

        # Try to get from environment variable first
        env_var = f"DISCORD_COLOR_{action_type.upper()}"
        env_color = os.getenv(env_var)

        if env_color:
            try:
                # Convert hex string to integer (handle both 0x and # prefixes)
                env_color = env_color.strip('#').strip('0x')
                return int(env_color, 16)
            except ValueError:
                # Log warning about invalid color format (would need logger)
                pass

        # Fall back to default color scheme
        return cls._DEFAULT_COLORS.get(action_type, cls._DEFAULT_COLORS[ActionType.DEFAULT])

    @classmethod
    def get_all_colors(cls) -> Dict[str, int]:
        """Get the complete color scheme dictionary, including environment overrides"""
        colors = {}
        for action_type in cls._DEFAULT_COLORS.keys():
            colors[action_type] = cls.get_color(action_type)
        return colors

    @classmethod
    def validate_color(cls, color: int) -> bool:
        """Validate that a color value is within Discord's valid range (0-16777215)"""
        return isinstance(color, int) and 0 <= color <= 0xffffff


def infer_action_type(message: str) -> str:
    """
    Attempt to infer the action type from message content.

    This is a heuristic-based approach that analyzes the message text
    to determine the most likely action type.

    Args:
        message: The notification message

    Returns:
        The inferred action type string
    """

    message_lower = message.lower()

    # Voice channel actions
    if any(word in message_lower for word in ["joined", "entering", "connecting"]) and "channel" in message_lower:
        return ActionType.VOICE_JOIN
    elif any(word in message_lower for word in ["left", "leaving", "disconnecting", "🔇"]) and "channel" in message_lower:
        return ActionType.VOICE_LEAVE
    elif any(word in message_lower for word in ["moved", "moved to", "switched"]) and "channel" in message_lower:
        return ActionType.VOICE_MOVE
    elif "muted" in message_lower or "🔇" in message_lower:
        return ActionType.VOICE_MUTE
    elif "unmuted" in message_lower:
        return ActionType.VOICE_UNMUTE
    elif "deafened" in message_lower:
        return ActionType.VOICE_DEAFEN
    elif "undeafened" in message_lower:
        return ActionType.VOICE_UNDEAFEN

    # Status changes
    elif "online" in message_lower:
        return ActionType.STATUS_ONLINE
    elif "offline" in message_lower:
        return ActionType.STATUS_OFFLINE
    elif "idle" in message_lower or "away" in message_lower:
        return ActionType.STATUS_IDLE
    elif "dnd" in message_lower or "disturb" in message_lower:
        return ActionType.STATUS_DND

    # Server member actions
    elif "joined server" in message_lower or "member joined" in message_lower:
        return ActionType.MEMBER_JOIN
    elif "left server" in message_lower or "member left" in message_lower:
        return ActionType.MEMBER_LEAVE

    # Warning/Error indicators
    elif any(word in message_lower for word in ["warning", "caution", "alert", "⚠️"]):
        return ActionType.WARNING
    elif any(word in message_lower for word in ["error", "failed", "problem", "issue", "❌"]):
        return ActionType.ERROR

    # Admin actions
    elif any(word in message_lower for word in ["admin", "administrator", "moderator", "staff"]):
        return ActionType.ADMIN

    # Default fallback
    else:
        return ActionType.DEFAULT