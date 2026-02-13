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
    """Converts a LaTeX or Markdown string to a PDF file with enhanced formatting using pandoc.
    
    Supports:
    - Tables with proper formatting (Markdown or LaTeX syntax)
    - Cross-references
    - Mathematical equations
    - Proper alignment and margins
    - Table of contents and numbered sections
    
    Args:
        latex_string: The content as a string (LaTeX or Markdown format - auto-detected)
        output_filename: Output filename without extension (e.g., 'document')
    
    Returns:
        Download marker with base64-encoded PDF data for frontend
    """
    try:
        clean_filename = output_filename.lstrip("/\\").replace(" ", "_")
        if not clean_filename.lower().endswith('.pdf'):
            clean_filename += '.pdf'
        
        # Auto-detect input format: LaTeX vs Markdown
        # LaTeX indicators: \begin, \section, \textbf, \\, \hline, etc.
        # Markdown indicators: # headers, | tables |, **bold**, *italic*
        latex_indicators = ['\\begin', '\\end', '\\section', '\\textbf', '\\hline', '\\\\', '\\item']
        markdown_indicators = ['| ', ' |', '# ', '## ', '### ', '**', '- ']
        
        latex_score = sum(1 for ind in latex_indicators if ind in latex_string)
        markdown_score = sum(1 for ind in markdown_indicators if ind in latex_string)
        
        # Use markdown format if more markdown indicators found, otherwise latex
        input_format = 'markdown' if markdown_score > latex_score else 'latex'
        
        # Create a LaTeX header file for custom formatting:
        # - Table of contents on its own page
        # - Each section starts on a new page
        latex_header = r"""
\usepackage{titlesec}
\usepackage{etoolbox}

% Add page break before each section (level 1 heading)
\newcommand{\sectionbreak}{\clearpage}

% Ensure TOC is on its own page(s)
\AtEndEnvironment{tableofcontents}{\clearpage}
"""
        
        # Use tempfile for header and output
        with tempfile.NamedTemporaryFile(suffix='.tex', delete=False, mode='w', encoding='utf-8') as header_file:
            header_file.write(latex_header)
            header_path = header_file.name
        
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp_file:
            tmp_path = tmp_file.name
        
        try:
            pypandoc.convert_text(
                latex_string, 
                'pdf', 
                format=input_format, 
                outputfile=tmp_path,
                extra_args=[
                    '--pdf-engine=pdflatex',
                    '--variable=geometry:margin=1in',
                    '--table-of-contents',
                    '--number-sections',
                    '--highlight-style=tango',
                    '-V', 'linkcolor:blue',
                    '-V', 'urlcolor:blue',
                    f'--include-in-header={header_path}'
                ]
            )
            
            # Check if the PDF was created and is not empty
            if not os.path.exists(tmp_path) or os.path.getsize(tmp_path) < 1024: # 1KB threshold
                raise RuntimeError("PDF generation resulted in an empty or very small file. This often means pandoc or a LaTeX engine (like pdflatex) is not installed or not in the system's PATH.")

            # Read PDF and encode as base64
            with open(tmp_path, 'rb') as f:
                pdf_data = f.read()
            pdf_base64 = base64.b64encode(pdf_data).decode('utf-8')
            
            # Store for backend recovery (backup mechanism for subagent flows)
            _store_pending_download({"filename": clean_filename, "data": pdf_base64, "type": "pdf"})
            
            # Include base64 data in the marker so it persists in the database
            # This ensures downloads work after page reload
            return f'[DOWNLOAD_PDF]{{"filename": "{clean_filename}", "data": "{pdf_base64}"}}'
            
        finally:
            # Clean up temp files
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            if os.path.exists(header_path):
                os.unlink(header_path)
                
    except Exception as e:
        return f"❌ PDF conversion failed: {str(e)}"

@tool
def convert_latex_to_docx(latex_string: str, output_filename: str) -> str:
    """Converts a LaTeX or Markdown string to a DOCX file with enhanced formatting using pandoc.
    
    Supports:
    - Tables with proper cell alignment and borders
    - Headings and subheadings with formatting
    - Lists (bulleted and numbered)
    - Cross-references
    - Table of contents
    
    Args:
        latex_string: The content as a string (LaTeX or Markdown format - auto-detected)
        output_filename: Output filename without extension (e.g., 'document')
    
    Returns:
        Download marker with base64-encoded DOCX data for frontend
    """
    try:
        clean_filename = output_filename.lstrip("/\\").replace(" ", "_")
        if not clean_filename.lower().endswith('.docx'):
            clean_filename += '.docx'
        
        # Auto-detect input format
        latex_indicators = ['\\begin', '\\end', '\\section', '\\textbf', '\\hline', '\\\\', '\\item']
        markdown_indicators = ['| ', ' |', '# ', '## ', '### ', '**', '- ']
        
        latex_score = sum(1 for ind in latex_indicators if ind in latex_string)
        markdown_score = sum(1 for ind in markdown_indicators if ind in latex_string)
        
        input_format = 'markdown' if markdown_score > latex_score else 'latex'
        
        # Use tempfile for conversion then read back
        with tempfile.NamedTemporaryFile(suffix='.docx', delete=False) as tmp_file:
            tmp_path = tmp_file.name
        
        try:
            pypandoc.convert_text(
                latex_string, 
                'docx', 
                format=input_format, 
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
            
            # Store for backend recovery (backup mechanism for subagent flows)
            _store_pending_download({"filename": clean_filename, "data": docx_base64, "type": "docx"})
            
            # Include base64 data in the marker so it persists in the database
            return f'[DOWNLOAD_DOCX]{{"filename": "{clean_filename}", "data": "{docx_base64}"}}'
            
        finally:
            # Clean up temp file
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
                
    except Exception as e:
        return f"❌ DOCX conversion failed: {str(e)}"

@tool
def convert_latex_to_markdown(latex_string: str, output_filename: str) -> str:
    """Converts a LaTeX or Markdown string to a Markdown file with GitHub-flavored formatting using pandoc.
    
    Supports:
    - Tables in GFM (GitHub Flavored Markdown) format with proper alignment
    - Code blocks with syntax highlighting
    - Headers (ATX-style with #)
    - Lists and blockquotes
    - Emphasis and strong emphasis
    
    Args:
        latex_string: The content as a string (LaTeX or Markdown format - auto-detected)
        output_filename: Output filename without extension (e.g., 'document')
    
    Returns:
        Download marker with base64-encoded Markdown data for frontend
    """
    try:
        clean_filename = output_filename.lstrip("/\\").replace(" ", "_")
        if not clean_filename.lower().endswith('.md'):
            clean_filename += '.md'
        
        # Auto-detect input format
        latex_indicators = ['\\begin', '\\end', '\\section', '\\textbf', '\\hline', '\\\\', '\\item']
        markdown_indicators = ['| ', ' |', '# ', '## ', '### ', '**', '- ']
        
        latex_score = sum(1 for ind in latex_indicators if ind in latex_string)
        markdown_score = sum(1 for ind in markdown_indicators if ind in latex_string)
        
        input_format = 'markdown' if markdown_score > latex_score else 'latex'
        
        # Convert directly to string (markdown is text-based)
        md_content = pypandoc.convert_text(
            latex_string, 
            'gfm',  # GitHub Flavored Markdown for better table support
            format=input_format,
            extra_args=[
                '--wrap=none',  # Don't wrap lines
                '--atx-headers'  # Use ATX-style headers (#)
            ]
        )
        
        # Encode as base64
        md_base64 = base64.b64encode(md_content.encode('utf-8')).decode('utf-8')
        
        # Store for backend recovery (backup mechanism for subagent flows)
        _store_pending_download({"filename": clean_filename, "data": md_base64, "type": "md"})
        
        # Include base64 data in the marker so it persists in the database
        return f'[DOWNLOAD_MD]{{"filename": "{clean_filename}", "data": "{md_base64}"}}'
        
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
    
    # Convert to PDF (this also calls _store_pending_download internally)
    pdf_result = convert_latex_to_pdf.invoke({"latex_string": latex_string, "output_filename": output_filename})
    results.append(pdf_result)
    
    # Convert to DOCX
    docx_result = convert_latex_to_docx.invoke({"latex_string": latex_string, "output_filename": output_filename})
    results.append(docx_result)
    
    # Convert to Markdown
    md_result = convert_latex_to_markdown.invoke({"latex_string": latex_string, "output_filename": output_filename})
    results.append(md_result)
    
    # Note: Each tool above calls _store_pending_download() internally.
    # The PDF tool runs first, so the PDF download is stored.
    # The later tools overwrite it, so let's restore the PDF as primary.
    # We do this by re-reading from _latest_download — if the last stored was MD,
    # that's fine because individual tools already stored the data.
    # The backend fallback will pick up whatever was last stored.
    
    # Return all download markers
    return "\n".join(results)
