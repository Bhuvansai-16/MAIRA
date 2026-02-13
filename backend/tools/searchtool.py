import os
from typing import Literal
from tavily import TavilyClient
from dotenv import load_dotenv
from langchain.tools import tool, ToolRuntime

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
    """
    print(f"Running internet search for: {query}")
    return tavily_client.search(
        query,
        max_results=max_results,
        topic=topic,
        include_answer="advanced",
        search_depth="advanced",
    )