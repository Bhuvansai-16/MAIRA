"""
Document Export Tool - Exports reports to DOCX format
"""
import os
from docx import Document
from langchain.tools import tool
from datetime import datetime


@tool
def export_to_docx(
    title: str,
    summary: str,
    sections: str,
    output_dir: str = "./reports"
) -> str:
    """
    Export a research report to DOCX format.
    
    Args:
        title: The report title
        summary: Executive summary paragraph
        sections: Section content in format "Heading1::Content1|||Heading2::Content2"
        output_dir: Directory to save the file (default: ./reports)
    
    Returns:
        Path to the generated DOCX file
    """
    # Ensure output directory exists
    os.makedirs(output_dir, exist_ok=True)
    
    # Create document
    doc = Document()
    doc.add_heading(title, level=0)
    
    # Add executive summary
    doc.add_heading("Executive Summary", level=1)
    doc.add_paragraph(summary)
    
    # Parse and add sections
    if sections:
        section_list = sections.split("|||")
        for section in section_list:
            if "::" in section:
                heading, content = section.split("::", 1)
                doc.add_heading(heading.strip(), level=1)
                doc.add_paragraph(content.strip())
    
    # Generate filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_')).strip()
    safe_title = safe_title[:50]  # Limit filename length
    filename = f"{safe_title}_{timestamp}.docx"
    output_path = os.path.join(output_dir, filename)
    
    # Save document
    doc.save(output_path)
    
    return f"Report saved to: {output_path}"