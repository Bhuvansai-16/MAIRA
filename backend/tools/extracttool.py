import os
from tavily import TavilyClient
from dotenv import load_dotenv
from langchain.tools import tool

load_dotenv()
tavily_client = TavilyClient(api_key=os.environ["TAVILY_API_KEY"])

@tool
def extract_webpage(url: str):
    """
    Extract the full text content of a webpage. 
    Use this on specific URLs found via search to get detailed data.
    """
    print(f"Extracting content from: {url}")
    return tavily_client.extract(url)