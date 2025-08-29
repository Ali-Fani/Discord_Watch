# Discord Watch Bot - Enhanced Notifications Architecture

## Overview
This document outlines the architectural design for enhanced notification handling across Telegram and Discord platforms, addressing HTML formatting issues and implementing dynamic embed colors.

## Current Issues

### 1. Telegram HTML Template Fix
**Problem**: HTML tags in Telegram messages are being displayed as raw text instead of being rendered as formatting (bold, code, etc.).

**Root Cause**: The `_format_for_telegram` method in `telegram_provider.py` uses `html.escape()` on the entire enhanced message, including intentionally added HTML formatting tags.

**Solution**: Implement selective HTML escaping that preserves formatting tags while sanitizing user content.

### 2. Discord Embed Color Customization
**Problem**: All Discord embeds use a hardcoded green color (`0x00ff00`) regardless of action type.

**Root Cause**: Color is hardcoded in `_create_enhanced_embed` method without considering action context.

**Solution**: Implement dynamic color system based on action types with configurable color scheme.

## Proposed Architecture

### Action Type System
```python
class ActionType:
    # Voice Channel Actions
    VOICE_JOIN = "voice_join"
    VOICE_LEAVE = "voice_leave"
    VOICE_MOVE = "voice_move"
    VOICE_MUTE = "voice_mute"
    VOICE_UNMUTE = "voice_unmute"

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
    ADMIN = "admin"
```

### Color Configuration
```python
class ColorConfig:
    # Voice actions
    VOICE_JOIN: int = 0x00ff00  # Green
    VOICE_LEAVE: int = 0xff0000  # Red
    VOICE_MOVE: int = 0x0080ff   # Blue
    VOICE_MUTE: int = 0xffff00   # Yellow

    # User status
    STATUS_ONLINE: int = 0x00ff00  # Green
    STATUS_OFFLINE: int = 0x808080 # Gray
    STATUS_IDLE: int = 0xffa500   # Orange
    STATUS_DND: int = 0xff0000    # Red

    # Warnings and admin
    WARNING: int = 0xffff00       # Yellow
    ADMIN: int = 0x800080         # Purple
    ERROR: int = 0xff0000         # Red

    # Fallback
    DEFAULT: int = 0x00ff00       # Green
```

## Implementation Strategy

### Phase 1: Telegram HTML Fix
1. Modify `_format_for_telegram` method to selectively escape content
2. Preserve HTML formatting tags while sanitizing user input
3. Add error handling for malformed HTML tags

### Phase 2: Discord Dynamic Colors
1. Create action type detection system
2. Implement color configuration class
3. Modify Discord provider to accept action type parameter
4. Update notification sending functions to include action context

### Phase 3: Integration and Testing
1. Update main.py notification calls to include action types
2. Add fallback mechanisms for unsupported scenarios
3. Create comprehensive error handling

## Interface Changes

### Updated NotificationProvider Base
```python
class NotificationProvider(ABC):
    @abstractmethod
    async def send_notification(
        self,
        user_id: str,
        message: str,
        user_context: Optional[UserContext] = None,
        action_type: Optional[str] = None
    ) -> bool:
        pass
```

### Action Type Helper Functions
```python
def infer_action_type(message: str) -> str:
    """Infer action type from message content"""
    indicators = {
        "joined": ActionType.VOICE_JOIN,
        "left": ActionType.VOICE_LEAVE,
        "moved": ActionType.VOICE_MOVE,
        "muted": ActionType.VOICE_MUTE,
        "online": ActionType.STATUS_ONLINE,
        "offline": ActionType.STATUS_OFFLINE,
    }

    for indicator, action_type in indicators.items():
        if indicator in message.lower():
            return action_type

    return ActionType.DEFAULT
```

## Configuration Examples

### Color Configuration (config.json)
```json
{
  "discord_colors": {
    "voice_join": "#00ff00",
    "voice_leave": "#ff0000",
    "voice_move": "#0080ff",
    "status_online": "#00ff00",
    "status_offline": "#808080",
    "status_idle": "#ffa500",
    "warning": "#ffff00",
    "admin": "#800080",
    "error": "#ff0000"
  }
}
```

### Environment Variables (optional)
```env
DISCORD_COLOR_VOICE_JOIN=00ff00
DISCORD_COLOR_VOICE_LEAVE=ff0000
DISCORD_COLOR_DEFAULT=00ff00
```

## Error Handling Strategy

1. **Unsupported HTML Tags**: Strip unsupported tags with logging
2. **Invalid Colors**: Use fallback color with warning log
3. **Action Type Detection Failure**: Default to standard action type
4. **Rendering Errors**: Graceful degradation to plain text

## Testing Strategy

1. Unit tests for action type detection
2. Integration tests for HTML rendering
3. Color configuration validation
4. Error handling edge cases
5. Cross-platform compatibility

## Usage Examples

### Telegram Message with Proper HTML
```
<b>👤 User123</b> (@user123)
<code>User ID: 123456</code>
📅 Joined: 2025-01-15 14:30 UTC
🏷️ Roles: Admin, Moderator
```

### Discord Embed with Dynamic Colors
- Voice Join: Green embed
- Voice Leave: Red embed
- Status Change: Orange embed
- Warning: Yellow embed
- Admin Action: Purple embed

## Migration Plan

1. Deploy Telegram HTML fixes (non-breaking)
2. Add action type parameters (backward compatible)
3. Implement dynamic colors (backwards compatible)
4. Update calling code to provide action types
5. Remove hardcoded color references

## Benefits

1. **Better User Experience**: Properly formatted messages in Telegram
2. **Visual Clarity**: Color-coded embeds in Discord by action type
3. **Maintainability**: Centralized color configuration
4. **Extensibility**: Easy addition of new action types and colors
5. **Robustness**: Comprehensive error handling and fallbacks