from langchain_community.tools import ArxivQueryRun
from langchain_community.utilities import ArxivAPIWrapper

arxiv_tool = ArxivQueryRun(
    api_wrapper=ArxivAPIWrapper(
        top_k_results=3,
        doc_content_chars_max=1000,   # Max characters to extract from each paper
        load_max_docs=10,              # Global limit on docs to load
        load_all_available_meta=True
    )
)