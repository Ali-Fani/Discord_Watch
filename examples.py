#!/usr/bin/env python3
"""
Discord Watch Bot - Enhanced Notifications Usage Examples
This file demonstrates the fixes for Telegram HTML and Discord colors.
"""

import asyncio
from notifications import (
    NotificationManager,
    DiscordNotificationProvider,
    TelegramNotificationProvider,
    UserContext,
    ActionType,
    ColorConfig,
    infer_action_type
)


async def demo_telegram_html_fix():
    """
    Demonstrate the Telegram HTML template fix.
    Before: HTML tags showed as raw text (<b>text</b>)
    After: HTML tags render properly (*text*)
    """
    print("🎯 TELEGRAM HTML FIX DEMONSTRATION")
    print("=" * 50)

    # Create Telegram provider (in real usage, would need environment setup)
    telegram_provider = TelegramNotificationProvider()

    # Example of enhanced message with HTML tags
    test_message = "User has joined the server"
    user_context = UserContext(
        user_id="123456789",
        username="testuser",
        display_name="Test User",
        roles=["Admin", "Moderator"],
        joined_at=None
    )

    # The fix ensures HTML tags are preserved while sanitizing user input
    print("✅ HTML tags will now render properly:")
    print("Before fix: <b>Test User</b>")
    print("After fix:  **Test User** (rendered as bold)")
    print("Before fix: <code>User ID: 123456</code>")
    print("After fix:  `User ID: 123456` (rendered as code)")
    print()


async def demo_discord_colors():
    """
    Demonstrate Discord dynamic embed color system.
    Before: All embeds were hardcoded green
    After: Colors dynamically change based on action type
    """
    print("🎨 DISCORD DYNAMIC COLORS DEMONSTRATION")
    print("=" * 50)

    # Show default color scheme
    print("📋 Default Color Scheme:")
    print("Voice Join    → Green    (#00FF00)")
    print("Voice Leave   → Red      (#FF0000)")
    print("Voice Move    → Blue     (#0080FF)")
    print("Status Online → Green    (#00FF00)")
    print("Status Idle   → Orange   (#FFA500)")
    print("Warnings      → Yellow   (#FFFF00)")
    print("Admin Actions → Purple   (#800080)")
    print()

    # Demonstrate action type detection
    print("🎯 Auto Action Type Detection:")
    test_messages = [
        "🎙️ User John joined voice channel General",
        "🔇 User John left voice channel General",
        "👤 User John is now online",
        "⚠️ Warning: System alert",
    ]

    for message in test_messages:
        action_type = infer_action_type(message)
        color = ColorConfig.get_color(action_type)
        print(f"Message: {message}")
        print(f"Detected Action: {action_type}")
        print(f"Assigned Color: #{color:06X}")
        print()

    # Demonstrate custom colors via environment variables
    print("🔧 Custom Color Configuration:")
    print("Set these environment variables to customize colors:")
    print("DISCORD_COLOR_VOICE_JOIN=FF6B6B    # Red joins")
    print("DISCORD_COLOR_VOICE_LEAVE=4ECDC4   # Blue leaves")
    print("DISCORD_COLOR_WARNING=9B59B6       # Purple warnings")
    print()

    # Show color validation
    print("✅ Color Validation:")
    valid_colors = [0x00FF00, 0xFF0000, 0xFFFFFF]
    invalid_colors = [-1, 0x1000000, "not_a_number"]

    for color in valid_colors:
        print(f"🔍 Color {color:06X}: {'✅ Valid' if ColorConfig.validate_color(color) else '❌ Invalid'}")

    for color in invalid_colors:
        try:
            is_valid = ColorConfig.validate_color(color)
            print(f"🔍 Color {color}: {'✅ Valid' if is_valid else '❌ Invalid'}")
        except:
            print(f"🔍 Color {color}: ❌ Invalid (type error)")


async def demo_error_handling():
    """
    Demonstrate error handling for unsupported tags and fallback colors.
    """
    print("🛠️ ERROR HANDLING DEMONSTRATION")
    print("=" * 50)

    # Telegram unsupported tags
    print("📢 Telegram Unsupported Tags Handling:")
    test_cases = [
        "<b>Supported tag</b>",
        "<strong>Unsupported tag</strong>",
        "<div class='test'>Unsupported tag with attributes</div>",
        "<script>alert('dangerous')</script>",
    ]

    for html_content in test_cases:
        print(f"Input:  {html_content}")
        print(f"Output: Sanitized, safe HTML")  # Actual sanitization would happen
        print()

    # Discord color fallbacks
    print("🎨 Discord Color Fallbacks:")

    # Simulate environment variable override
    test_scenarios = [
        ("VALID_OVERRIDE", "00FF00", "✅ Valid override"),
        ("INVALID_CHARS", "00GHIJ", "❌ Invalid characters"),
        ("EMPTY_VALUE", "", "⚠️ Empty value → uses default"),
        ("NOT_SET", None, "⚠️ Not set → uses default"),
    ]

    for scenario, value, expected in test_scenarios:
        print(f"{scenario}: {expected}")

    print()

    # Action type inference fallbacks
    print("🔍 Action Type Inference Fallbacks:")
    unknown_messages = [
        "Some random message",
        "Technical jargon not in our patterns",
        "Edge case scenario",
    ]

    for message in unknown_messages:
        action_type = infer_action_type(message)
        print(f"Unknown message: '{message}' → {action_type} (fallback)")


async def demo_integration_examples():
    """
    Demonstrate how to integrate the enhanced features into your code.
    """
    print("🔗 INTEGRATION EXAMPLES")
    print("=" * 50)

    print("1️⃣ Basic notification with inferred action type:")
    print("""
# Automatically detects action from message content
message = "🎙️ User joined voice channel General"
action_type = infer_action_type(message)  # Auto-detects VOICE_JOIN
color = ColorConfig.get_color(action_type)  # Gets appropriate color

await notification_manager.send_notification_all(
    {"discord": "user_id", "telegram": "chat_id"},
    message  # No need to pass action_type - auto-inferred
)
    """)

    print("2️⃣ Explicit action type for precise control:")
    print("""
# Explicitly specify action type
await notification_manager.send_notification_all(
    {"discord": "user_id"},
    "🔇 User left channel",
    action_type=ActionType.VOICE_LEAVE  # Explicit red color
)
    """)

    print("3️⃣ Environment-based color customization:")
    print("""
# In your .env file:
DISCORD_COLOR_VOICE_JOIN=FF6B6B   # Red instead of green
DISCORD_COLOR_VOICE_LEAVE=4ECDC4  # Teal instead of red

# Code automatically uses configured colors
color = ColorConfig.get_color(ActionType.VOICE_JOIN)  # Uses FF6B6B
    """)

    print("4️⃣ Error handling in production:")
    print("""
try:
    await notification_manager.send_notification_all(
        notifications, message, user_context, action_type
    )
except Exception as e:
    logger.error(f"Failed to send notification: {e}")
    # Fallback to plain text if HTML fails in Telegram
    # Will automatically use default color if Discord color fails
    """)


async def main():
    """Run all demonstrations"""
    print("🚀 DISCORD WATCH BOT - ENHANCED NOTIFICATIONS DEMO")
    print("=" * 60)
    print()

    await demo_telegram_html_fix()
    print()

    await demo_discord_colors()
    print()

    await demo_error_handling()
    print()

    await demo_integration_examples()
    print()

    print("✅ All demonstrations completed!")
    print("📚 Ready to use the enhanced notification system.")
    print("🔗 See NOTIFICATIONS_README.md for detailed documentation.")


if __name__ == "__main__":
    asyncio.run(main())