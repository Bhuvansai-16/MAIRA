# Complete workflow: Generate LaTeX and convert to all formats
from langchain.tools import tool
from agent.backend.latexagent import latex_chain
from tools.latextoformate import convert_latex_to_all_formats

@tool
def generate_and_convert_document(topic: str, output_filename: str = "document") -> str:
    """Generates a LaTeX document about a topic and converts it to PDF, DOCX, and Markdown.
    
    Args:
        topic: The topic to write about
        output_filename: Base filename for outputs (default: 'document')
    
    Returns:
        Download marker for the PDF file (primary format)
    """
    # Step 1: Generate LaTeX
    print(f"📝 Generating LaTeX document about '{topic}'...")
    latex_code = latex_chain.invoke({"topic": topic}).content
    
    # Step 2: Convert to all formats (creates PDF, DOCX, and MD)
    print(f"🔄 Converting to PDF, DOCX, and Markdown...")
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