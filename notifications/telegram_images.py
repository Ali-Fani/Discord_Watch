"""
Telegram profile picture processing and caching module for Discord Watch Bot.

This module handles the fetching, processing, and caching of Telegram user profile pictures
with thumbnails for efficient notification delivery.
"""
import asyncio
import hashlib
import io
import os
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, Any
import aiofiles
import httpx
from PIL import Image
from telegram.error import TelegramError
from telegram import Bot

from .config import TelegramThumbnailConfig
import logging

logger = logging.getLogger("discord_bot")


class ImageProcessor:
    """Handles image processing operations for Telegram profile pictures"""

    @staticmethod
    def calculate_image_hash(image_data: bytes) -> str:
        """Calculate SHA-256 hash for image content to detect changes"""
        return hashlib.sha256(image_data).hexdigest()

    @staticmethod
    def create_thumbnail(image_data: bytes, width: int, height: int, quality: int = 85) -> bytes:
        """
        Create a thumbnail from image data

        Args:
            image_data: Raw image bytes
            width: Target width
            height: Target height
            quality: JPEG quality (1-95)

        Returns:
            Thumbnail image bytes in JPEG format

        Raises:
            ValueError: If image data is invalid
            Exception: For other processing errors
        """
        try:
            # Open image with PIL
            image = Image.open(io.BytesIO(image_data))

            # Convert to RGB if necessary (for RGBA/P images)
            if image.mode in ('RGBA', 'P'):
                # Create white background
                background = Image.new('RGB', image.size, (255, 255, 255))
                if image.mode == 'P':
                    image = image.convert('RGBA')
                background.paste(image, mask=image.split()[-1])  # Use alpha channel as mask
                image = background

            # Handle transparency
            if image.mode != 'RGB':
                image = image.convert('RGB')

            # Create thumbnail with aspect ratio preserved
            image.thumbnail((width, height), Image.Resampling.LANCZOS)

            # Create new image with exact dimensions to ensure consistency
            new_image = Image.new('RGB', (width, height), (255, 255, 255))
            x = (width - image.width) // 2
            y = (height - image.height) // 2
            new_image.paste(image, (x, y))

            # Save to bytes
            output = io.BytesIO()
            new_image.save(output, format='JPEG', quality=quality, optimize=True)
            return output.getvalue()

        except Exception as e:
            logger.error(f"Failed to create thumbnail: {str(e)}")
            raise

    @staticmethod
    def validate_image_data(image_data: bytes) -> bool:
        """Validate that the data is a readable image format"""
        try:
            image = Image.open(io.BytesIO(image_data))
            image.verify()  # Verify the image is not corrupted
            return True
        except Exception:
            return False


class CacheManager:
    """Manages cached thumbnails with expiration and cleanup"""

    def __init__(self, db_collection=None):
        """
        Initialize cache manager

        Args:
            db_collection: MongoDB collection for cache metadata (optional)
        """
        self.db_collection = db_collection
        self.cache_dir = Path(TelegramThumbnailConfig.get_cache_dir())
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _get_cache_key(self, user_id: str, image_hash: str) -> str:
        """Generate cache key for a user and image hash"""
        return f"{user_id}_{image_hash}"

    def _get_cache_path(self, cache_key: str) -> Path:
        """Get filesystem path for cached image"""
        return self.cache_dir / f"{cache_key}.jpg"

    async def get_cached_thumbnail(self, user_id: str, image_hash: str) -> Optional[bytes]:
        """
        Retrieve cached thumbnail if it exists and is valid

        Args:
            user_id: Telegram user ID
            image_hash: SHA-256 hash of the original image

        Returns:
            Thumbnail bytes if cached and valid, None otherwise
        """
        try:
            cache_key = self._get_cache_key(user_id, image_hash)
            cache_path = self._get_cache_path(cache_key)

            # Check if file exists
            if not cache_path.exists():
                return None

            # Check expiration from database if available
            if self.db_collection:
                metadata = await self.db_collection.find_one(
                    {"user_id": user_id, "image_hash": image_hash}
                )
                if metadata:
                    created_at = metadata.get("created_at", datetime.utcnow())
                    ttl_hours = TelegramThumbnailConfig.get_cache_ttl_hours()
                    if datetime.utcnow() - created_at > timedelta(hours=ttl_hours):
                        # Expired, clean up
                        await self._remove_from_cache(user_id, image_hash)
                        return None
            else:
                # Simple file-based expiration check
                file_age_hours = (time.time() - cache_path.stat().st_mtime) / 3600
                if file_age_hours > TelegramThumbnailConfig.get_cache_ttl_hours():
                    cache_path.unlink(missing_ok=True)
                    return None

            # Read cached thumbnail
            async with aiofiles.open(cache_path, 'rb') as f:
                return await f.read()

        except Exception as e:
            logger.error(f"Failed to retrieve cached thumbnail for user {user_id}: {str(e)}")
            return None

    async def save_thumbnail(self, user_id: str, image_hash: str, thumbnail_data: bytes) -> bool:
        """
        Save thumbnail to cache

        Args:
            user_id: Telegram user ID
            image_hash: SHA-256 hash of the original image
            thumbnail_data: Processed thumbnail bytes

        Returns:
            True if saved successfully, False otherwise
        """
        try:
            cache_key = self._get_cache_key(user_id, image_hash)
            cache_path = self._get_cache_path(cache_key)

            # Write thumbnail to file
            async with aiofiles.open(cache_path, 'wb') as f:
                await f.write(thumbnail_data)

            # Save metadata to database if available
            if self.db_collection:
                await self.db_collection.update_one(
                    {"user_id": user_id, "image_hash": image_hash},
                    {
                        "$set": {
                            "cache_key": cache_key,
                            "cache_path": str(cache_path),
                            "created_at": datetime.utcnow(),
                            "file_size": len(thumbnail_data)
                        }
                    },
                    upsert=True
                )

            return True

        except Exception as e:
            logger.error(f"Failed to save thumbnail for user {user_id}: {str(e)}")
            return False

    async def _remove_from_cache(self, user_id: str, image_hash: str) -> bool:
        """Remove thumbnail from cache"""
        try:
            cache_key = self._get_cache_key(user_id, image_hash)
            cache_path = self._get_cache_path(cache_key)

            # Remove file
            if cache_path.exists():
                cache_path.unlink()

            # Remove metadata from database
            if self.db_collection:
                await self.db_collection.delete_one(
                    {"user_id": user_id, "image_hash": image_hash}
                )

            return True

        except Exception as e:
            logger.error(f"Failed to remove thumbnail from cache for user {user_id}: {str(e)}")
            return False

    async def cleanup_cache(self) -> Dict[str, int]:
        """
        Clean up expired cache entries and enforce size limits

        Returns:
            Dictionary with cleanup statistics
        """
        stats = {"expired_removed": 0, "size_limit_removed": 0}

        try:
            ttl_hours = TelegramThumbnailConfig.get_cache_ttl_hours()
            max_size_mb = TelegramThumbnailConfig.get_cache_max_size_mb()

            # Get all cache files
            if self.cache_dir.exists():
                cache_files = list(self.cache_dir.glob("*.jpg"))
            else:
                return stats

            # Sort by modification time (oldest first)
            cache_files.sort(key=lambda f: f.stat().st_mtime)

            # Remove expired files
            cutoff_time = time.time() - (ttl_hours * 3600)
            for cache_file in cache_files:
                if cache_file.stat().st_mtime < cutoff_time:
                    cache_file.unlink(missing_ok=True)
                    stats["expired_removed"] += 1

            # Check total size and remove oldest files if needed
            total_size = sum(f.stat().st_size for f in self.cache_dir.glob("*.jpg"))
            max_size_bytes = max_size_mb * 1024 * 1024

            while total_size > max_size_bytes and cache_files:
                oldest_file = cache_files.pop(0)
                if oldest_file.exists():
                    total_size -= oldest_file.stat().st_size
                    oldest_file.unlink(missing_ok=True)
                    stats["size_limit_removed"] += 1

            # Clean up database metadata for removed files if available
            if self.db_collection and (stats["expired_removed"] > 0 or stats["size_limit_removed"] > 0):
                await self._cleanup_orphaned_metadata()

        except Exception as e:
            logger.error(f"Cache cleanup failed: {str(e)}")

        return stats

    async def _cleanup_orphaned_metadata(self):
        """Remove database metadata for files that no longer exist"""
        try:
            if not self.db_collection:
                return

            # Find all metadata entries
            async for metadata in self.db_collection.find({}):
                cache_path = Path(metadata.get("cache_path", ""))
                if not cache_path.exists():
                    await self.db_collection.delete_one({"_id": metadata["_id"]})

        except Exception as e:
            logger.error(f"Failed to cleanup orphaned metadata: {str(e)}")


class TelegramProfilePictureManager:
    """Main manager for Telegram profile picture operations"""

    def __init__(self, bot: Bot, db_collection=None):
        """
        Initialize the profile picture manager

        Args:
            bot: Telegram Bot instance
            db_collection: MongoDB collection for cache metadata
        """
        self.bot = bot
        self.cache_manager = CacheManager(db_collection)
        self.http_client = httpx.AsyncClient(timeout=TelegramThumbnailConfig.get_api_timeout())

    async def get_thumbnail_for_user(self, user_id: str) -> Optional[bytes]:
        """
        Get profile picture thumbnail for a user, using cache if available

        Args:
            user_id: Telegram user ID

        Returns:
            Thumbnail bytes if available, None otherwise
        """
        try:
            # Fetch current profile photos
            profile_photos = await self.bot.get_user_profile_photos(user_id=user_id, limit=1)

            if not profile_photos.photos:
                # User has no profile picture
                return None

            # Get the largest available photo
            photo = profile_photos.photos[0][-1]  # Last item is largest

            # Get file information
            file_info = await self.bot.get_file(file_id=photo.file_id)
            file_url = file_info.file_path

            # Check if we need the full URL
            if not file_url.startswith('http'):
                file_url = f"https://api.telegram.org/file/bot{self.bot.token.split(':')[0]}/{file_url}"

            # Download the image
            response = await self.http_client.get(file_url)
            response.raise_for_status()
            image_data = response.content

            # Validate image data
            if not ImageProcessor.validate_image_data(image_data):
                logger.error(f"Invalid image data for user {user_id}")
                return None

            # Calculate hash for cache lookup
            image_hash = ImageProcessor.calculate_image_hash(image_data)

            # Check cache
            cached_thumbnail = await self.cache_manager.get_cached_thumbnail(user_id, image_hash)
            if cached_thumbnail:
                return cached_thumbnail

            # Generate new thumbnail
            thumbnail_data = ImageProcessor.create_thumbnail(
                image_data,
                width=TelegramThumbnailConfig.get_width(),
                height=TelegramThumbnailConfig.get_height(),
                quality=TelegramThumbnailConfig.get_quality()
            )

            # Cache the thumbnail
            await self.cache_manager.save_thumbnail(user_id, image_hash, thumbnail_data)

            return thumbnail_data

        except TelegramError as e:
            # Try to get cached thumbnail if API fails and feature is enabled
            if TelegramThumbnailConfig.should_send_thumbnail_on_error():
                logger.warning(f"Telegram API error for user {user_id}: {str(e)}, attempting to use cached thumbnail")
                # This would require additional metadata to find the most recent cached thumbnail
                # For now, we'll just return None and let the caller handle it
            else:
                logger.error(f"Failed to get profile picture for user {user_id}: {str(e)}")
            return None

        except Exception as e:
            logger.error(f"Unexpected error getting thumbnail for user {user_id}: {str(e)}")
            return None

    async def cleanup_cache(self) -> Dict[str, int]:
        """Clean up expired cache entries and enforce size limits"""
        return await self.cache_manager.cleanup_cache()

    async def close(self):
        """Clean up resources"""
        await self.http_client.aclose()

    async def get_configuration_report(self) -> dict:
        """Get a report of the current configuration for debugging"""
        from .config import TelegramThumbnailConfig

        cache_stats = await self.cache_manager.cleanup_cache()
        cache_dir_size = 0

        try:
            cache_path = Path(TelegramThumbnailConfig.get_cache_dir())
            if cache_path.exists():
                # Get total size of all jpg files in cache
                for jpg_file in cache_path.glob("*.jpg"):
                    cache_dir_size += jpg_file.stat().st_size
                cache_dir_size = cache_dir_size / (1024 * 1024)  # Convert to MB
        except Exception:
            pass

        return {
            "configuration": TelegramThumbnailConfig.get_config_report(),
            "cache_stats": {
                "current_size_mb": round(cache_dir_size, 2),
                "max_size_mb": TelegramThumbnailConfig.get_cache_max_size_mb(),
                "last_cleanup": cache_stats
            }
        }