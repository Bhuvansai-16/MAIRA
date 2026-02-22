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
        redis_client = Redis(url=url, token=token)
        # Test connection
        redis_client.ping()
        print("✅ Redis connection established")
        return redis_client
    except Exception as e:
        print(f"❌ Failed to connect to Redis: {e}")
        return None

# Singleton instance
redis_client = get_redis_client()
