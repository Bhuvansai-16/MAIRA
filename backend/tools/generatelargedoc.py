from langchain.tools import tool
from agent.backend.latexagent import latex_chain
from tools.splittool import split_latex_document
from tools.latextoformate import convert_latex_to_all_formats
@tool
def generate_large_document_with_chunks(topic: str, output_filename: str = "document", max_chunk_size: int = 2000) -> str:
    """Generates a large LaTeX document, splits it into manageable chunks, then converts to all formats.
    
    Useful for generating comprehensive documents that might be too large for single-pass processing.
    
    Args:
        topic: The topic to write about
        output_filename: Base filename for outputs (default: 'document')
        max_chunk_size: Maximum size of each LaTeX chunk (default: 2000)
    
    Returns:
        Download marker for the PDF file (primary format)
    """
    # Step 1: Generate LaTeX
    print(f"📝 Generating LaTeX document about '{topic}'...")
    latex_code = latex_chain.invoke({"topic": topic}).content
    
    # Step 2: Split into chunks (for analysis/processing - internal only)
    print(f"✂️  Splitting document into chunks...")
    split_result = split_latex_document.invoke({
        "latex_string": latex_code,
        "chunk_size": max_chunk_size
    })
    print(f"Split complete: {split_result}")
    
    # Step 3: Convert complete document to all formats (creates PDF, DOCX, and MD)
    print(f"🔄 Converting complete document to PDF, DOCX, and Markdown...")
    conversion_results = convert_latex_to_all_formats.invoke({
        "latex_string": latex_code,
        "output_filename": output_filename
    })
    
    # Extract and return only the PDF marker (primary format for download)
    # The conversion creates all 3 formats, but we return PDF as the main deliverable
    lines = conversion_results.split('\n')
    for line in lines:
        if line.startswith('[DOWNLOAD_PDF]'):
            return line
    
    # Fallback if no PDF marker found
    return conversion_results