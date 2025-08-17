from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse, HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
import pathlib
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import logging
from motor.motor_asyncio import AsyncIOMotorClient

app = FastAPI()
logger = logging.getLogger("discord_bot")

# Mount static files directory
static_dir = pathlib.Path(__file__).parent / "static"
static_dir.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

class HealthCheck:
    def __init__(self):
        self.discord_client = None
        self.mongo_client = None
        self.notification_manager = None

    def initialize(self, discord_client, mongo_client, notification_manager):
        self.discord_client = discord_client
        self.mongo_client = mongo_client
        self.notification_manager = notification_manager

health_check = HealthCheck()

async def check_mongodb() -> Dict[str, bool]:
    """Check MongoDB connection health"""
    try:
        await health_check.mongo_client.admin.command('ping')
        return {"status": True}
    except Exception as e:
        logger.error(f"MongoDB health check failed: {str(e)}")
        return {"status": False, "error": str(e)}

async def check_discord() -> Dict[str, bool]:
    """Check Discord connection health"""
    if not health_check.discord_client:
        return {"status": False, "error": "Discord client not initialized"}
    
    try:
        return {"status": health_check.discord_client.is_ready()}
    except Exception as e:
        logger.error(f"Discord health check failed: {str(e)}")
        return {"status": False, "error": str(e)}

async def check_notification_providers() -> Dict[str, Dict[str, bool]]:
    """Check health of notification providers"""
    if not health_check.notification_manager:
        return {"status": False, "error": "Notification manager not initialized"}
    
    results = {}
    for name, provider in health_check.notification_manager.providers.items():
        try:
            # Basic check - just verify the provider exists and is initialized
            results[name] = {"status": bool(provider)}
        except Exception as e:
            logger.error(f"{name} provider health check failed: {str(e)}")
            results[name] = {"status": False, "error": str(e)}
    
    return results

@app.get("/health")
async def health():
    """Get health status of all components"""
    health_status = {
        "mongodb": await check_mongodb(),
        "discord": await check_discord(),
        "notification_providers": await check_notification_providers(),
    }
    
    # Overall status is True only if all critical components are healthy
    overall_status = all([
        health_status["mongodb"]["status"],
        health_status["discord"]["status"]
    ])
    
    health_status["status"] = overall_status
    
    return JSONResponse(
        content=health_status,
        status_code=200 if overall_status else 503
    )

@app.get("/", response_class=FileResponse)
async def root():
    """Serve the health check dashboard"""
    return FileResponse(
        str(static_dir / "health.html"),
        media_type="text/html"
    )

@app.get("/voice")
async def voice_activity_page():
    """Serve the voice activity dashboard"""
    return FileResponse(
        str(static_dir / "voice-activity.html"),
        media_type="text/html"
    )

@app.get("/api/voice-activity")
async def get_voice_activity(
    server: str = Query(None),
    user: str = Query(None),
    event: str = Query(None),
    start: str = Query(None),
    end: str = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100)
):
    """Get filtered voice activity logs"""
    try:
        # Build the query
        query = {}
        if server:
            # Handle both string and integer server IDs
            try:
                query["server_id"] = int(server)
            except ValueError:
                query["server_id"] = server
                
        if user:
            # Handle both string and integer user IDs
            try:
                query["user_id"] = int(user)
            except ValueError:
                query["user_id"] = user
                
        if event:
            query["event_type"] = event
            
        # Add date range filter if provided
        if start:
            try:
                start_date = datetime.fromisoformat(start.replace('Z', '+00:00'))
                if not query.get("event_time"):
                    query["event_time"] = {}
                query["event_time"]["$gte"] = start_date
            except ValueError:
                logger.error(f"Invalid start date format: {start}")
                
        if end:
            try:
                end_date = datetime.fromisoformat(end.replace('Z', '+00:00'))
                if not query.get("event_time"):
                    query["event_time"] = {}
                query["event_time"]["$lte"] = end_date
            except ValueError:
                logger.error(f"Invalid end date format: {end}")
                
        logger.info(f"Final query: {query}")
            
        # For debugging, let's log some sample documents first
        sample_doc = await health_check.mongo_client.discord_watch.voice_activity.find_one()
        if sample_doc:
            logger.info(f"Sample document format: {sample_doc}")
            
        # Remove date filtering temporarily to debug
        logger.info(f"Initial query without date filter: {query}")
        # Get all documents matching without date filter
        total_matching = await health_check.mongo_client.discord_watch.voice_activity.count_documents(query)
        logger.info(f"Documents matching without date filter: {total_matching}")

        # Get paginated results
        skip = (page - 1) * limit
        collection = health_check.mongo_client.discord_watch.voice_activity

        # First check if we have any documents
        total_docs = await collection.count_documents({})
        logger.info(f"Total voice activity documents: {total_docs}")

        cursor = collection.find(
            query,
            sort=[("event_time", -1)]  # Sort by most recent first
        ).skip(skip).limit(limit)
        
        activities = []
        async for doc in cursor:
            # Convert ObjectId and datetime to string for JSON serialization
            doc["_id"] = str(doc["_id"])
            doc["event_time"] = doc["event_time"].isoformat() if doc.get("event_time") else None
            # Ensure all fields are present
            doc.setdefault("username", "Unknown User")
            doc.setdefault("channel_name", "Unknown Channel")
            doc.setdefault("server_name", "Unknown Server")
            activities.append(doc)

        logger.info(f"Found {len(activities)} activities for current page")

        # Get statistics
        base_time = datetime.now() - timedelta(days=1)
        
        # Get total unique users
        total_users = await collection.distinct("user_id", query)
        total_users_count = len(total_users)

        # Get total sessions today
        total_sessions = await collection.count_documents({
            **query,
            "event_type": "join",
            "event_time": {"$gte": base_time}
        })

        # Get currently active users (joined but not left)
        active_now = await collection.count_documents({
            "event_type": "join",
            "user_id": {
                "$nin": await collection.distinct(
                    "user_id",
                    {
                        "event_type": "leave",
                        "event_time": {"$gt": base_time}
                    }
                )
            }
        })

        stats = {
            "totalUsers": total_users_count,
            "totalSessions": total_sessions,
            "activeNow": active_now
        }

        logger.info(f"Stats: {stats}")

        return {
            "activities": activities,
            "stats": stats
        }

    except Exception as e:
        logger.error(f"Failed to fetch voice activity: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/voice-activity/filters")
async def get_voice_activity_filters():
    """Get available filter options for voice activity"""
    try:
        logger.info("Fetching voice activity filters...")
        
        # Get unique servers with valid names
        servers = []
        server_pipeline = [
            {
                "$match": {
                    "server_name": {"$ne": None}  # Only include documents with non-null server names
                }
            },
            {
                "$group": {
                    "_id": "$server_id",
                    "name": {"$first": "$server_name"}
                }
            }
        ]
        logger.info("Running server aggregation pipeline...")
        async for doc in health_check.mongo_client.discord_watch.voice_activity.aggregate(server_pipeline):
            if doc["_id"] is not None and doc["name"]:  # Only add if both id and name are valid
                servers.append({"id": doc["_id"], "name": doc["name"]})
        logger.info(f"Found {len(servers)} unique servers")

        # Get unique users with valid names
        users = []
        user_pipeline = [
            {
                "$match": {
                    "username": {"$ne": None}  # Only include documents with non-null usernames
                }
            },
            {
                "$group": {
                    "_id": "$user_id",
                    "name": {"$first": "$username"}
                }
            }
        ]
        logger.info("Running user aggregation pipeline...")
        async for doc in health_check.mongo_client.discord_watch.voice_activity.aggregate(user_pipeline):
            if doc["_id"] is not None and doc["name"]:  # Only add if both id and name are valid
                users.append({"id": doc["_id"], "name": doc["name"]})
        logger.info(f"Found {len(users)} unique users")

        # Handle None values in sorting
        def safe_sort_key(x):
            return x.get("name") or ""  # Return empty string if name is None
            
        response = {
            "servers": sorted(servers, key=safe_sort_key),
            "users": sorted(users, key=safe_sort_key)
        }
        
        logger.info(f"Returning filters: {response}")
        return response

    except Exception as e:
        logger.error(f"Failed to fetch voice activity filters: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
