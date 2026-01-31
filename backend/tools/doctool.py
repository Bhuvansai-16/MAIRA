import base64
import io
from pydantic import BaseModel, Field
from langchain.tools import tool
from docx import Document

class DocSection(BaseModel):
    """Represents a single section of the report."""
    heading: str = Field(description="The section title (e.g., 'Introduction')")
    content: str = Field(description="The full text content for this section")

class ExportInput(BaseModel):
    """Input schema for the DOCX export tool."""
    sections: list[DocSection] = Field(description="A list of section objects")
    filename: str = Field(description="The output filename, e.g., 'report.docx'")

@tool(args_schema=ExportInput)
def export_to_docx(sections: list[DocSection], filename: str) -> str:
    """Exports structured report sections to a professional .docx file."""
    # Strip leading slashes to prevent issues
    clean_filename = filename.lstrip("/\\")
    
    doc = Document()
    for section in sections:
        doc.add_heading(section.heading, level=1)
        doc.add_paragraph(section.content)
    
    # Save to in-memory buffer instead of disk
    buffer = io.BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    
    # Encode as base64 for transmission to frontend
    doc_base64 = base64.b64encode(buffer.read()).decode('utf-8')
    
    # Return marker with JSON data that frontend can parse
    return f'[DOWNLOAD_DOCX]{{"filename": "{clean_filename}", "data": "{doc_base64}"}}'