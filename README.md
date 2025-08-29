# Enhanced Discord & Telegram Notification Templates

This document describes the enhanced message templates for Discord and Telegram notification bots that include additional user information.

## Overview

The notification system now supports enhanced message templates that include:
- User profile picture/avatar URL
- Username and display name
- User ID
- Join date (for Discord)
- Roles (for Discord)
- Error handling for missing information

## Template Formats

### Discord Format (Rich Embeds)

Discord notifications now use rich embeds with:
- **Avatar Thumbnail**: User's profile picture in the embed thumbnail
- **Author Section**: Username with discriminator and avatar
- **User Information Fields**:
  - User ID (as inline code)
  - Member Since date (when available)
  - Roles (up to first 5 roles)

**Example Embed:**
```
┌─ Embed ──────────────────────────────┐
│ 👤 Username#1234 [Avatar Thumbnail]  │
├─────────────────────────────────────┤
│ Main notification message here...    │
├─────────────────────────────────────┤
│ 💳 User ID: `123456789012345678`     │
│ 📅 Member Since: 2023-06-15 14:30 UTC│
│ 🏷️  Roles: Admin, Moderator          │
└─────────────────────────────────────┘
```

### Telegram Format (HTML Text)

Telegram notifications use HTML formatting with:
- **Bold username** with optional @username
- **Code-formatted User ID**
- **Join date** (when available)
- **Roles list** (when available)
- **Profile picture note** (when available)

**Example Message:**
```
👤 Username (@username)
```User ID: 1234567890```
📅 Joined: 2023-06-15 14:30 UTC
🏷️ Roles: Admin, Moderator
🖼️ Profile picture available

🎙️ User Username joined voice channel General in server MyServer
```

## Data Sources

### Discord Platform
- **User Data**: Fetched via `client.fetch_user(user_id)`
- **Member Data**: Retrieved from MongoDB `members` collection
- **Avatar URL**: `user.display_avatar.url`
- **Join Date**: `member.joined_at` from database

### Telegram Platform
- **User Data**: Limited access (requires prior user interaction)
- **Fallback**: Basic ID-only context when user data unavailable
- **Profile Pictures**: Available via `get_user_profile_photos()` if user has interacted with bot

## Error Handling

### Missing User Data
- **Discord**: Falls back to basic user info if API call fails
- **Telegram**: Uses generic "User {ID}" format when user data unavailable
- **Avatar/Profile Picture**: Skipped gracefully if not available
- **Member Data**: Optional fields only included if available

### API Failures
- **Network Issues**: Logged but don't prevent notification delivery
- **Invalid User IDs**: Logged and marked as failed notification
- **Rate Limits**: Respects Discord/Telegram rate limits

## Usage Example

```python
# Enhanced notification with user context
user_context = await get_discord_user_context(user_id)
await client.notification_manager.send_notification_all(
    notifications={"discord": discord_user_id, "telegram": telegram_chat_id},
    message="User status changed",
    user_context=user_context
)
```

## Backwards Compatibility

The enhanced notification system maintains full backwards compatibility:
- Old notification calls without user_context still work
- Enhanced features are opt-in
- Fallback to basic templates when context unavailable

## Configuration

No additional configuration required. The system automatically:
- Detects available user data
- Formats appropriately for each platform
- Handles missing data gracefully
- Maintains performance with cached user lookups

## Future Enhancements

- User status indicators (online/offline/idle/dnd)
- Activity information
- Server-specific user information
- Custom profile fields
- Rich media attachments (for supported platforms)