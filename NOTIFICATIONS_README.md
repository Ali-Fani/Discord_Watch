# Enhanced Notifications Documentation

This document provides comprehensive information about the enhanced notification system for the Discord Watch Bot, including the fixes for Telegram HTML formatting, Discord embed color customization, and clickable voice channel links.

## 🚀 Quick Start

### 1. Environment Setup
Copy the example configuration file and customize it for your needs:

```bash
cp notifications_config.example.env .env
# Edit .env with your bot tokens and color preferences
```

### 2. Key Features Implemented

#### ✅ Telegram HTML Template Fix
- **Problem Solved**: HTML tags were displaying as raw text instead of being rendered
- **Solution**: Selective HTML escaping with Telegram's supported tags preserved
- **Supported Tags**: `<b>`, `<i>`, `<u>`, `<s>`, `<code>`, `<pre>`, `<a>`

#### ✅ Discord Dynamic Embed Colors
- **Problem Solved**: All embeds used hardcoded green color
- **Solution**: Dynamic color system based on action types
- **Configuration**: Environment variables or runtime configuration

#### 🎙️ Clickable Voice Channel Links
- **Problem Solved**: No direct way to join voice channels from notifications
- **Solution**: Automatic voice channel link generation in Discord embeds
- **Features**: Clickable links that launch Discord and join specific voice channels

## 📋 Action Types and Colors

### Voice Channel Actions
| Action Type | Description | Default Color | Hex Value |
|------------|-------------|---------------|-----------|
| `VOICE_JOIN` | User joins voice channel | 🟢 Green | `#00FF00` |
| `VOICE_LEAVE` | User leaves voice channel | 🔴 Red | `#FF0000` |
| `VOICE_MOVE` | User moves between channels | 🔵 Blue | `#0080FF` |
| `VOICE_MUTE` | User mutes themselves | 🟡 Yellow | `#FFFF00` |
| `VOICE_UNMUTE` | User unmutes themselves | 🟢 Green | `#00FF00` |
| `VOICE_DEAFEN` | User deafens themselves | 🟠 Orange | `#FFA500` |
| `VOICE_UNDEAFEN` | User undeafens themselves | 🟢 Green | `#00FF00` |

### User Status Actions
| Action Type | Description | Default Color | Hex Value |
|------------|-------------|---------------|-----------|
| `STATUS_ONLINE` | User goes online | 🟢 Green | `#00FF00` |
| `STATUS_OFFLINE` | User goes offline | ⚫ Gray | `#808080` |
| `STATUS_IDLE` | User goes idle | 🟠 Orange | `#FFA500` |
| `STATUS_DND` | User goes DND | 🔴 Red | `#FF0000` |

### Server Actions
| Action Type | Description | Default Color | Hex Value |
|------------|-------------|---------------|-----------|
| `MEMBER_JOIN` | Member joins server | 🟢 LimeGreen | `#32CD32` |
| `MEMBER_LEAVE` | Member leaves server | 🔴 Crimson | `#DC143C` |
| `MEMBER_UPDATE` | Member info changes | 🔵 DodgerBlue | `#1E90FF` |

### Special Actions
| Action Type | Description | Default Color | Hex Value |
|------------|-------------|---------------|-----------|
| `WARNING` | Warning messages | 🟡 Yellow | `#FFFF00` |
| `ERROR` | Error messages | 🔴 Red | `#FF0000` |
| `ADMIN` | Administrative actions | 🟣 Purple | `#800080` |
| `DEFAULT` | Fallback action type | 🟢 Green | `#00FF00` |

## 🔧 Configuration

### Environment Variables

Configure Discord embed colors using environment variables:

```env
# Voice channel colors
DISCORD_COLOR_VOICE_JOIN=00FF00
DISCORD_COLOR_VOICE_LEAVE=FF0000
DISCORD_COLOR_VOICE_MOVE=0080FF

# Status colors
DISCORD_COLOR_STATUS_ONLINE=00FF00
DISCORD_COLOR_STATUS_OFFLINE=808080
DISCORD_COLOR_STATUS_IDLE=FFA500
DISCORD_COLOR_STATUS_DND=FF0000

# Default fallback
DISCORD_COLOR_DEFAULT=00FF00
```

### Programmatic Configuration

You can also configure colors programmatically:

```python
from notifications.config import ColorConfig, ActionType

# Get color for specific action
color = ColorConfig.get_color(ActionType.VOICE_JOIN)

# Get all colors as dictionary
all_colors = ColorConfig.get_all_colors()

# Validate color value
is_valid = ColorConfig.validate_color(0x00FF00)  # True
```

## 📝 Usage Examples

### Basic Notification with Inferred Action Type

```python
from notifications import NotificationManager, ActionType, infer_action_type

# Auto-infers action type from message content
message = "🎙️ User John joined voice channel General"
action_type = infer_action_type(message)
# Returns: ActionType.VOICE_JOIN

await notification_manager.send_notification_all(
    user_notifications={"discord": "123456789", "telegram": "987654321"},
    message=message
)
```

### Explicit Action Type Specification

```python
from notifications.config import ActionType

# Explicitly specify action type
await notification_manager.send_notification_all(
    user_notifications={"discord": "123456789"},
    message="🔇 User John left voice channel General",
    action_type=ActionType.VOICE_LEAVE
)
```

### Custom Color Configuration

```python
import os
# Override colors via environment variables
os.environ['DISCORD_COLOR_VOICE_JOIN'] = 'FF6B6B'  # Light red for join
os.environ['DISCORD_COLOR_VOICE_LEAVE'] = '4ECDC4'  # Light blue for leave

# Colors will be automatically picked up by ColorConfig.get_color()
```

## 🎙️ Clickable Voice Channel Links

The enhanced notification system now includes clickable voice channel links that allow users to instantly join voice channels from notifications.

### How It Works
- **URL Format**: `https://discord.com/channels/{server_id}/{channel_id}`
- **Compatibility**: Works with Discord desktop, web, and mobile clients
- **Automatic Join**: Clicking the link automatically navigates to and joins the voice channel

### Example Notification Structure

```python
# Voice channel join notification with clickable link
# Server ID: 123456789012345678
# Channel ID: 987654321098765432
# Generated URL: https://discord.com/channels/123456789012345678/987654321098765432

embed = discord.Embed(
    title="🎙️ Voice Channel Activity",
    description="User joined a voice channel",
    color=0x00FF00  # Green for join
)
embed.add_field(name="User", value="JohnDoe", inline=True)
embed.add_field(name="Channel", value="General", inline=True)
embed.add_field(
    name="🎙️ Voice Channel",
    value="[Join Voice Channel](https://discord.com/channels/123456789012345678/987654321098765432)",
    inline=False
)
```

### Implementation Details
The system automatically includes voice channel links when:

1. **Voice Channel Events**: User joins, leaves, or moves between voice channels
2. **Server & Channel IDs Available**: Both server and channel IDs are provided
3. **Discord Notifications**: Only affects Discord embeds (Telegram doesn't support voice channel links)

### Privacy & Security
- **Permission Required**: The bot only uses server/channel IDs it already has access to
- **No Additional Permissions**: No new Discord permissions required
- **Opt-in**: Only included when both server_id and channel_id are provided

### Code Integration

```python
# Automated - the system handles this automatically
await notification_manager.send_notification_all(
    notifications={"discord": "user_id"},
    message="🎙️ User joined voice channel General",
    voice_channel_id=987654321098765432,  # Channel ID
    server_id=123456789012345678         # Server ID
)

# The embed will automatically include a clickable voice channel link!
```

### Troubleshooting Voice Channel Links

**Links not appearing?**
- Ensure both `voice_channel_id` and `server_id` are provided
- Only Discord notifications support voice channel links
- Check that the server/channel IDs are valid

**Links not working?**
- Verify the bot has permission to see the channel
- Check if the user has permission to join the channel
- Ensure the server ID matches the channel's server

### Backward Compatibility
- **Fully Backward Compatible**: Existing code continues to work unchanged
- **Optional Feature**: Voice channel links are added automatically when possible
- **No Breaking Changes**: All existing functionality remains intact

## 🔍 Troubleshooting

### Telegram HTML Issues

**Problem**: HTML tags still show as raw text
```bash
# Check logs for warnings about unsupported tags
tail -f bot.log | grep -i telegram
```

**Solution**: Verify supported tags are used:
- ✅ `<b>bold text</b>` works
- ❌ `<strong>bold text</strong>` → removes tag, keeps text
- ✅ `<code>inline code</code>` works
- ❌ `<span>text</span>` → removes tag, keeps text

### Discord Color Issues

**Problem**: Wrong colors or default fallback used
```bash
# Check if environment variables are set correctly
env | grep DISCORD_COLOR
```

**Problem**: Invalid color values
```bash
# Check logs for color validation warnings
tail -f bot.log | grep -i color
```

**Solution**: Use valid hex color values (000000-FFFFFF):
```env
DISCORD_COLOR_VOICE_JOIN=00FF00  # ✅ Valid
DISCORD_COLOR_VOICE_JOIN=00GHIJ  # ❌ Invalid characters
```

## 🧪 Testing

### Test HTML Rendering

Create a test notification to verify Telegram HTML formatting:

```python
test_message = """
<b>Test User</b> joined a channel
<code>User ID: 12345</code>
📅 Joined: 2025-01-15 10:30 UTC
"""

await notification_manager.send_notification_all(
    {"telegram": "your_telegram_id"},
    test_message
)
```

### Test Color Schemes

Test different action types to verify color coding:

```python
test_cases = [
    (ActionType.VOICE_JOIN, "🎙️ User joined voice channel"),
    (ActionType.VOICE_LEAVE, "🔇 User left voice channel"),
    (ActionType.STATUS_ONLINE, "👤 User is now online"),
    (ActionType.WARNING, "⚠️ Warning: Something happened"),
]

for action_type, message in test_cases:
    await notification_manager.send_notification_all(
        {"discord": "your_discord_id"},
        message,
        action_type=action_type
    )
```

## 📊 Message Examples

### Telegram Messages (Before/After Fix)

**Before**: Raw HTML tags displayed
```
<b>User123</b> (@user123)
<code>User ID: 123456</code>
```

**After**: Properly formatted HTML
```
**User123** (@user123)
`User ID: 123456`
```

### Discord Embeds (Color-Coded by Action)

```python
# Voice join → Green embed
embed = discord.Embed(color=0x00FF00, description="🎙️ User joined voice channel General")

# Voice leave → Red embed
embed = discord.Embed(color=0xFF0000, description="🔇 User left voice channel General")

# Status change → Appropriate color embed
embed = discord.Embed(color=0xFFA500, description="👤 User went idle")
```

### Voice Channel Links (Enhanced Clicking)

With the new voice channel links feature, notifications now include clickable buttons or links that automatically:
- Launch the Discord app (or open web Discord)
- Navigate to the specific server
- Join the exact voice channel mentioned

```python
# Previous: Just text description
embed.add_field(name="Channel", value="General", inline=True)

# Enhanced: Clickable voice channel link
embed.add_field(
    name="🎙️ Voice Channel",
    value="[Join Voice Channel](https://discord.com/channels/123456789/987654321)",
    inline=False
)
```

## 🔧 Advanced Configuration

### Custom Action Type Detection

Extend the `infer_action_type` function for custom message patterns:

```python
def custom_infer_action_type(message: str) -> str:
    """Custom action type inference logic"""
    if "custom_event" in message.lower():
        return "CUSTOM_EVENT"
    return infer_action_type(message)  # Fall back to default logic
```

### Custom Color Schemes

Create custom color schemes programmatically:

```python
from notifications.config import ColorConfig, ActionType

# Define custom color scheme
custom_colors = {
    ActionType.VOICE_JOIN: 0xFF6B6B,   # Red join
    ActionType.VOICE_LEAVE: 0x4ECDC4,  # Teal leave
    ActionType.DEFAULT: 0x95A5A6       # Gray default
}

# Apply custom colors
for action_type, color in custom_colors.items():
    os.environ[f"DISCORD_COLOR_{action_type.upper()}"] = f"{color:06X}"
```

## 🤝 Contributing

### Adding New Action Types

1. Add constant to `ActionType` class in `config.py`
2. Add default color to `ColorConfig._DEFAULT_COLORS`
3. Update inference logic in `infer_action_type` function
4. Update documentation

### Adding New Color Configuration Options

1. Document new environment variable pattern
2. Add validation if needed
3. Update example configuration file
4. Test edge cases

## 📈 Performance Notes

- **Environment Variable Caching**: Colors from environment are cached after first access
- **Action Type Inference**: Lightweight string matching, minimal performance impact
- **HTML Sanitization**: Only runs when necessary, efficient regex patterns
- **Fallback Handling**: Robust error handling prevents notification failures

## 🔗 Related Files

- [`notifications/config.py`](notifications/config.py) - Color and action type configuration
- [`notifications/discord_provider.py`](notifications/discord_provider.py) - Discord embed formatting and voice channel links
- [`notifications/telegram_provider.py`](notifications/telegram_provider.py) - Telegram HTML handling
- [`notifications/manager.py`](notifications/manager.py) - Notification orchestration and voice channel support
- [`main.py`](main.py) - Main bot logic with voice channel link integration
- [`examples.py`](examples.py) - Usage examples including voice channel links demo
- [`notifications_config.example.env`](notifications_config.example.env) - Configuration template
- [`ARCHITECTURE_DESIGN.md`](ARCHITECTURE_DESIGN.md) - Technical design document
- [`NOTIFICATIONS_README.md`](NOTIFICATIONS_README.md) - This documentation with voice channel links

---

For support or questions, please check the bot logs or create an issue in the project repository.