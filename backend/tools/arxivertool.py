import time
import arxiv
from typing import Optional
from langchain_core.tools import tool
from langchain_community.tools import ArxivQueryRun
from langchain_community.utilities import ArxivAPIWrapper


class RateLimitedArxivWrapper:
    """Custom arXiv wrapper with rate limiting and retry logic."""
    
    def __init__(
        self,
        top_k_results: int = 10,
        doc_content_chars_max: int = 2000,
        delay_seconds: float = 3.0,  # Delay between requests
        max_retries: int = 5,
        backoff_factor: float = 2.0
    ):
        self.top_k_results = top_k_results
        self.doc_content_chars_max = doc_content_chars_max
        self.delay_seconds = delay_seconds
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor
        self._last_request_time = 0
    
    def _wait_for_rate_limit(self):
        """Ensure we don't exceed rate limits."""
        elapsed = time.time() - self._last_request_time
        if elapsed < self.delay_seconds:
            time.sleep(self.delay_seconds - elapsed)
        self._last_request_time = time.time()
    
    def run(self, query: str) -> str:
        """Run arXiv search with retry logic and rate limiting."""
        self._wait_for_rate_limit()
        
        client = arxiv.Client(
            page_size=self.top_k_results,
            delay_seconds=self.delay_seconds,
            num_retries=self.max_retries
        )
        
        search = arxiv.Search(
            query=query,
            max_results=self.top_k_results,
            sort_by=arxiv.SortCriterion.Relevance
        )
        
        for attempt in range(self.max_retries):
            try:
                results = []
                for paper in client.results(search):
                    summary = paper.summary[:self.doc_content_chars_max] if paper.summary else "No summary available"
                    results.append(
                        f"Title: {paper.title}\n"
                        f"Authors: {', '.join(a.name for a in paper.authors[:5])}\n"
                        f"Published: {paper.published.strftime('%Y-%m-%d')}\n"
                        f"arXiv ID: {paper.entry_id}\n"
                        f"PDF: {paper.pdf_url}\n"
                        f"Summary: {summary}\n"
                        f"{'-' * 50}"
                    )
                
                if not results:
                    return "No papers found for the given query."
                
                return "\n\n".join(results)
                
            except arxiv.HTTPError as e:
                # Handle rate limits (429) and server errors (5xx)
                if e.status == 429 or (500 <= e.status < 600):
                    wait_time = self.delay_seconds * (self.backoff_factor ** attempt)
                    print(f"arXiv API Error ({e.status}). Waiting {wait_time:.1f}s before retry {attempt + 1}/{self.max_retries}")
                    time.sleep(wait_time)
                else:
                    return f"arXiv API returned error {e.status}: {str(e)}"
            except Exception as e:
                if attempt == self.max_retries - 1:
                    return f"Error searching arXiv after {self.max_retries} attempts: {str(e)}"
                wait_time = self.delay_seconds * (self.backoff_factor ** attempt)
                print(f"arXiv unknown error: {str(e)}. Retrying in {wait_time:.1f}s...")
                time.sleep(wait_time)
        
        return "Failed to retrieve papers from arXiv. The service might be temporarily unavailable."


@tool
def arxiv_search(query: str, max_results: int = 10) -> str:
    """
    Search arXiv for academic papers with rate limiting.
    
    Args:
        query: Search query for arXiv papers (e.g., "LLM multi-agent systems")
        max_results: Maximum number of papers to retrieve (default: 10, max recommended: 20)
    
    Returns:
        String containing paper titles, authors, summaries, and links
    """
    # Cap max_results to avoid rate limiting
    max_results = min(max_results, 20)
    
    wrapper = RateLimitedArxivWrapper(
        top_k_results=max_results,
        doc_content_chars_max=2000,
        delay_seconds=3.0,
        max_retries=5
    )
    return wrapper.run(query)


# Keep the old tool for compatibility but with safer defaults
arxiv_tool = ArxivQueryRun(
    api_wrapper=ArxivAPIWrapper(
        top_k_results=5,  # Reduced from higher values
        doc_content_chars_max=1000
    )
)