import os
import redis
from upstash_redis import Redis
from dotenv import load_dotenv

load_dotenv()

# Initialize Redis client using Upstash REST API
# This is preferred for HTTP-based serverless environments
# but works fine here too.
def get_redis_client():
    url = os.environ.get("UPSTASH_REDIS_REST_URL")
    token = os.environ.get("UPSTASH_REDIS_REST_TOKEN")
    
    if not url or not token:
        print("⚠️ Redis credentials not found in environment variables.")
        return None

    try:
        client = Redis(url=url, token=token)
        # Test connection
        client.ping()
        print("✅ Redis connection established")
        return client
    except Exception as e:
        print(f"❌ Failed to connect to Redis: {e}")
        return None

# Singleton instance (may be None if credentials are missing or connection failed)
redis_client = get_redis_client()


# Fix #13: Lazy reconnect — if redis_client dropped, re-initialize on next call.
# This prevents a one-time Redis blip from permanently disabling caching.
def get_redis():
    """Return the active Redis client, reconnecting if needed."""
    global redis_client
    if redis_client is None:
        redis_client = get_redis_client()
    return redis_client
