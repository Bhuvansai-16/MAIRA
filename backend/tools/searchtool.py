import os
import json
from typing import Literal
from tavily import TavilyClient
from dotenv import load_dotenv
from langchain.tools import tool, ToolRuntime
try:
    from redis_client import redis_client
except ImportError:
    import sys
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from redis_client import redis_client

load_dotenv()
tavily_client = TavilyClient(api_key=os.environ["TAVILY_API_KEY"])

@tool
def internet_search(
    query: str,
    runtime: ToolRuntime,
    max_results: int = 10,
    topic: Literal["general", "news"] = "general",
):
    """
    Run a web search to find real-time information, news, data, and relevant images.
    Returns search results including image URLs when available.
    For literature survey only search for research papers
    """
    # 1. Check Redis cache
    if redis_client:
        try:
            # Create a deterministic key
            cache_key = f"search:{query}:{topic}:{max_results}"
            cached_data = redis_client.get(cache_key)
            if cached_data:
                print(f"⚡ Cache HIT for search: {query}")
                try:
                    # Try to parse if it's JSON string, or just return if tool expects structure
                    # Tools usually return whatever Tavily client returns.
                    # Tavily .search returns a DICT.
                    # So we must parse it back to a dict.
                    return json.loads(cached_data)
                except json.JSONDecodeError:
                    return cached_data
        except Exception as e:
            print(f"⚠️ Redis cache error: {e}")

    # 2. Perform search
    print(f"Running internet search for: {query}")
    try:
        results = tavily_client.search(
            query,
            max_results=max_results,
            topic=topic,
            include_answer="advanced",
            search_depth="advanced",
            include_images=True,
            include_image_descriptions=True,
        )
        
        # 3. Cache results
        if redis_client:
            try:
                # Serialize dict to JSON string
                redis_client.setex(cache_key, 86400, json.dumps(results))
            except Exception as e:
                print(f"⚠️ Failed to cache search: {e}")
                
        return results
        
    except Exception as e:
        return f"Error executing search: {e}"