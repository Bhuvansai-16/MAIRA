from langchain_text_splitters import RecursiveCharacterTextSplitter, Language
from langchain.tools import tool

# Create LaTeX-aware text splitter
latex_splitter = RecursiveCharacterTextSplitter.from_language(
    language=Language.LATEX,
    chunk_size=1000,  # Adjust based on your needs
    chunk_overlap=100
)

@tool
def split_latex_document(latex_string: str, chunk_size: int = 1000) -> str:
    """Splits a LaTeX document into smaller chunks while respecting LaTeX structure.
    
    Useful for:
    - Processing large LaTeX documents
    - Creating chunks for RAG systems
    - Managing long documents in LLM context windows
    
    Args:
        latex_string: The complete LaTeX document as a string
        chunk_size: Maximum size of each chunk (default: 1000)
    
    Returns:
        Summary of how many chunks were created
    """
    # Create splitter with specified chunk size
    splitter = RecursiveCharacterTextSplitter.from_language(
        language=Language.LATEX,
        chunk_size=chunk_size,
        chunk_overlap=min(100, chunk_size // 10)  # 10% overlap
    )
    
    # Split the document
    chunks = splitter.create_documents([latex_string])
    
    # Summary
    summary = [
        f"✅ Split LaTeX document into {len(chunks)} chunks",
        f"   Chunk size: {chunk_size} characters",
        f"   Total length: {len(latex_string)} characters"
    ]
    
    # Show first few chunks as preview
    if chunks:
        summary.append(f"\n📄 First chunk preview:")
        summary.append(f"   {chunks[0].page_content[:150]}...")
    
    return "\n".join(summary)