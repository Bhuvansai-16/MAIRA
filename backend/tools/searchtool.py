import os
from typing import Literal
from tavily import TavilyClient
from dotenv import load_dotenv
load_dotenv()
tavily_client = TavilyClient(api_key=os.environ["TAVILY_API_KEY"])
from langchain.tools import tool
@tool
def internet_search(
    query: str,
    max_results: int = 5,
    topic: Literal["general", "news", "finance"] = "general",
    include_raw_content: bool = False,
):
    """Run a web search"""
    print("Running internet search tool...")
    return tavily_client.search(
        query,
        max_results=max_results,
        include_raw_content=include_raw_content,
        topic=topic,
    )
