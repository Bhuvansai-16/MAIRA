import time
import arxiv
from langchain_core.tools import tool


@tool
def arxiv_search(query: str, max_results: int = 5) -> str:
    """
    Search arXiv for academic papers.

    Args:
        query: Search query for arXiv papers (e.g., "LLM multi-agent systems")
        max_results: Maximum number of papers to retrieve (default: 5, max: 10)

    Returns:
        String containing paper titles, authors, summaries, and links
    """
    max_results = min(max_results, 10)

    # arxiv.Client already handles retries + delay internally — no outer loop needed
    client = arxiv.Client(
        page_size=max_results,
        delay_seconds=4.0,   # Generous delay to avoid 429s
        num_retries=3        # Let the client handle retries itself
    )

    search = arxiv.Search(
        query=query,
        max_results=max_results,
        sort_by=arxiv.SortCriterion.Relevance
    )

    try:
        results = []
        for paper in client.results(search):
            summary = paper.summary[:2000] if paper.summary else "No summary available"
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
        return f"arXiv API error ({e.status}): The service is temporarily unavailable. Try a simpler query or try again later."
    except Exception as e:
        return f"Error searching arXiv: {str(e)}. Try a simpler query or try again later."