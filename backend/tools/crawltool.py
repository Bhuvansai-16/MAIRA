# To install: pip install tavily-python
from tavily import TavilyClient
client = TavilyClient("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")
response = client.crawl(
    url="",
    extract_depth="advanced"
)
print(response)