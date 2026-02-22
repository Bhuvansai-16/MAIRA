import os
import json
from tavily import TavilyClient
from dotenv import load_dotenv
from langchain.tools import tool
try:
    from redis_client import redis_client
except ImportError:
    # Handle cases where sys.path isn't set up perfectly (e.g. running tool directly)
    import sys
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from redis_client import redis_client

load_dotenv()
tavily_client = TavilyClient(api_key=os.environ["TAVILY_API_KEY"])

@tool
def extract_webpage(url: str):
    """
    Extract the full text content of a webpage. 
    Use this on specific URLs found via search to get detailed data.
    """
    # 1. Check Redis cache
    if redis_client:
        try:
            cache_key = f"web:{url}"
            cached_data = redis_client.get(cache_key)
            if cached_data:
                print(f"⚡ Cache HIT for extracting: {url}")
                # Redis returns bytes or string depending on client config. 
                # Upstash REST often returns raw string if simple get.
                # Just return it.
                return cached_data
        except Exception as e:
            print(f"⚠️ Redis cache error: {e}")

    # 2. Scrape if not cached
    print(f"Extracting content from: {url}")
    try:
        data = tavily_client.extract(url)
        # Tavily extract returns a dict usually { 'results': [...] } or raw text?
        # Standard .extract returns simple dict.
        # Let's stringify it for storage if it's a dict, or store raw.
        # But wait, the tool typically returns a string for the agent.
        # Tavily .extract returns {'results': [{'url':..., 'content':...}]}
        # We should return the specific content string or the whole JSON.
        # The original code returned 'tavily_client.extract(url)' directly.
        # So we should cache the result of that call (which is a dict/object).
        
        # Serialization for Redis
        if isinstance(data, (dict, list)):
            data_str = json.dumps(data)
        else:
            data_str = str(data)
            
        # 3. Save to Redis
        if redis_client:
            try:
                redis_client.setex(cache_key, 86400, data_str) # 24h cache
            except Exception as e:
                print(f"⚠️ Failed to cache extraction: {e}")
                
        # Truncate to 50k chars to prevent state bloat
        final_data = data_str[:50000] if len(data_str) > 50000 else data_str
        return final_data
        
    except Exception as e:
        return f"Error extracting {url}: {e}"