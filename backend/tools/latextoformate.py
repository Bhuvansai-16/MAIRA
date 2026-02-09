"""
LaTeX to Multiple Format Converter with Frontend Output Support
Converts LaTeX to PDF, DOCX, and Markdown with base64-encoded output for frontend download
"""
import pypandoc
import base64
import io
import json
import threading
import tempfile
import os
from langchain.tools import tool

# Thread-safe storage for download data from subagent tool calls
# Uses a global latest-download approach instead of thread IDs because
# LangGraph runs tools via asyncio.run_in_executor() in a thread pool,
# so the storing thread ID differs from the retrieving thread ID.
_latest_download = None
_download_lock = threading.Lock()

def _store_pending_download(data: dict):
    """Store download data globally (latest wins)."""
    global _latest_download
    with _download_lock:
        _latest_download = data
        print(f"  💾 Download stored in pending: {data.get('filename', 'unknown')}")

def get_pending_download() -> dict | None:
    """Retrieve and remove the latest pending download data."""
    global _latest_download
    with _download_lock:
        data = _latest_download
        _latest_download = None
        return data

@tool
def convert_latex_to_pdf(latex_string: str, output_filename: str) -> str:
    """Converts a LaTeX string to a PDF file with enhanced formatting using pandoc.
    
    Supports:
    - Tables with proper formatting
    - Cross-references
    - Mathematical equations
    - Proper alignment and margins
    - Table of contents and numbered sections
    
    Args:
        latex_string: The LaTeX code as a string
        output_filename: Output filename without extension (e.g., 'document')
    
    Returns:
        Download marker with base64-encoded PDF data for frontend
    """
    try:
        clean_filename = output_filename.lstrip("/\\").replace(" ", "_")
        if not clean_filename.lower().endswith('.pdf'):
            clean_filename += '.pdf'
        
        # Use tempfile for conversion then read back
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp_file:
            tmp_path = tmp_file.name
        
        try:
            pypandoc.convert_text(
                latex_string, 
                'pdf', 
                format='latex', 
                outputfile=tmp_path,
                extra_args=[
                    '--pdf-engine=pdflatex',
                    '--variable=geometry:margin=1in',
                    '--table-of-contents',
                    '--number-sections',
                    '--highlight-style=tango',
                    '-V', 'linkcolor:blue',
                    '-V', 'urlcolor:blue'
                ]
            )
            
            # Read PDF and encode as base64
            with open(tmp_path, 'rb') as f:
                pdf_data = f.read()
            pdf_base64 = base64.b64encode(pdf_data).decode('utf-8')
            
            # Store for backend recovery
            _store_pending_download({"filename": clean_filename, "data": pdf_base64, "type": "pdf"})
            
            # Return marker for frontend - use ensure_ascii for safety
            json_data = json.dumps({"filename": clean_filename, "data": pdf_base64}, ensure_ascii=True)
            return f'[DOWNLOAD_PDF]{json_data}'
            
        finally:
            # Clean up temp file
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
                
    except Exception as e:
        return f"❌ PDF conversion failed: {str(e)}"

@tool
def convert_latex_to_docx(latex_string: str, output_filename: str) -> str:
    """Converts a LaTeX string to a DOCX file with enhanced formatting using pandoc.
    
    Supports:
    - Tables with proper cell alignment and borders
    - Headings and subheadings with formatting
    - Lists (bulleted and numbered)
    - Cross-references
    - Table of contents
    
    Args:
        latex_string: The LaTeX code as a string
        output_filename: Output filename without extension (e.g., 'document')
    
    Returns:
        Download marker with base64-encoded DOCX data for frontend
    """
    try:
        clean_filename = output_filename.lstrip("/\\").replace(" ", "_")
        if not clean_filename.lower().endswith('.docx'):
            clean_filename += '.docx'
        
        # Use tempfile for conversion then read back
        with tempfile.NamedTemporaryFile(suffix='.docx', delete=False) as tmp_file:
            tmp_path = tmp_file.name
        
        try:
            pypandoc.convert_text(
                latex_string, 
                'docx', 
                format='latex', 
                outputfile=tmp_path,
                extra_args=[
                    '--table-of-contents',
                    '--number-sections',
                    '--highlight-style=tango'
                ]
            )
            
            # Read DOCX and encode as base64
            with open(tmp_path, 'rb') as f:
                docx_data = f.read()
            docx_base64 = base64.b64encode(docx_data).decode('utf-8')
            
            # Store for backend recovery
            _store_pending_download({"filename": clean_filename, "data": docx_base64, "type": "docx"})
            
            # Return marker for frontend - use ensure_ascii for safety
            json_data = json.dumps({"filename": clean_filename, "data": docx_base64}, ensure_ascii=True)
            return f'[DOWNLOAD_DOCX]{json_data}'
            
        finally:
            # Clean up temp file
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
                
    except Exception as e:
        return f"❌ DOCX conversion failed: {str(e)}"

@tool
def convert_latex_to_markdown(latex_string: str, output_filename: str) -> str:
    """Converts a LaTeX string to a Markdown file with GitHub-flavored formatting using pandoc.
    
    Supports:
    - Tables in GFM (GitHub Flavored Markdown) format with proper alignment
    - Code blocks with syntax highlighting
    - Headers (ATX-style with #)
    - Lists and blockquotes
    - Emphasis and strong emphasis
    
    Args:
        latex_string: The LaTeX code as a string
        output_filename: Output filename without extension (e.g., 'document')
    
    Returns:
        Download marker with base64-encoded Markdown data for frontend
    """
    try:
        clean_filename = output_filename.lstrip("/\\").replace(" ", "_")
        if not clean_filename.lower().endswith('.md'):
            clean_filename += '.md'
        
        # Convert directly to string (markdown is text-based)
        md_content = pypandoc.convert_text(
            latex_string, 
            'gfm',  # GitHub Flavored Markdown for better table support
            format='latex',
            extra_args=[
                '--wrap=none',  # Don't wrap lines
                '--atx-headers'  # Use ATX-style headers (#)
            ]
        )
        
        # Encode as base64
        md_base64 = base64.b64encode(md_content.encode('utf-8')).decode('utf-8')
        
        # Store for backend recovery
        _store_pending_download({"filename": clean_filename, "data": md_base64, "type": "md"})
        
        # Return marker for frontend - use ensure_ascii for safety
        json_data = json.dumps({"filename": clean_filename, "data": md_base64}, ensure_ascii=True)
        return f'[DOWNLOAD_MD]{json_data}'
        
    except Exception as e:
        return f"❌ Markdown conversion failed: {str(e)}"

@tool
def convert_latex_to_all_formats(latex_string: str, output_filename: str) -> str:
    """Converts a LaTeX string to PDF, DOCX, and Markdown files with enhanced formatting.
    
    All formats include:
    - Proper table formatting
    - Cross-references
    - Consistent heading structure
    - Professional formatting
    
    Args:
        latex_string: The LaTeX code as a string
        output_filename: Base filename without extension (e.g., 'document')
    
    Returns:
        Download markers for all formats (PDF, DOCX, MD) for frontend
    """
    results = []
    all_downloads = []
    
    # Convert to PDF
    pdf_result = convert_latex_to_pdf.invoke({"latex_string": latex_string, "output_filename": output_filename})
    results.append(pdf_result)
    
    # Extract download data if successful
    if pdf_result.startswith('[DOWNLOAD_PDF]'):
        try:
            pdf_json = json.loads(pdf_result[14:])  # Skip '[DOWNLOAD_PDF]'
            all_downloads.append({"type": "pdf", **pdf_json})
        except:
            pass
    
    # Convert to DOCX
    docx_result = convert_latex_to_docx.invoke({"latex_string": latex_string, "output_filename": output_filename})
    results.append(docx_result)
    
    # Extract download data if successful
    if docx_result.startswith('[DOWNLOAD_DOCX]'):
        try:
            docx_json = json.loads(docx_result[15:])  # Skip '[DOWNLOAD_DOCX]'
            all_downloads.append({"type": "docx", **docx_json})
        except:
            pass
    
    # Convert to Markdown
    md_result = convert_latex_to_markdown.invoke({"latex_string": latex_string, "output_filename": output_filename})
    results.append(md_result)
    
    # Extract download data if successful
    if md_result.startswith('[DOWNLOAD_MD]'):
        try:
            md_json = json.loads(md_result[13:])  # Skip '[DOWNLOAD_MD]'
            all_downloads.append({"type": "md", **md_json})
        except:
            pass
    
    # Store all downloads for backend recovery (use the first one as primary)
    if all_downloads:
        # Store the PDF as the primary download (most commonly requested)
        for dl in all_downloads:
            if dl.get("type") == "pdf":
                _store_pending_download({"filename": dl["filename"], "data": dl["data"]})
                break
        else:
            # Fallback to first available
            _store_pending_download({"filename": all_downloads[0]["filename"], "data": all_downloads[0]["data"]})
    
    # Return all download markers
    return "\n".join(results)
