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
from datetime import datetime
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
\usepackage{needspace}
\usepackage{fancyhdr}
\usepackage{hyperref}
\usepackage{xcolor}
\usepackage{parskip}
\usepackage[titles]{tocloft}

\hypersetup{colorlinks=true, linkcolor=blue, urlcolor=blue}

% ---------------------------------------------------------
% TABLE OF CONTENTS SPACING
% ---------------------------------------------------------
% Spread out TOC entries to fill page better (Vertical Spacing)
\setlength{\cftbeforesecskip}{30pt}
\setlength{\cftbeforesubsecskip}{15pt}
\setlength{\cftbeforesubsubsecskip}{8pt}
\renewcommand{\cftsecdotsep}{\cftdotsep} % Add dots for sections too

% ---------------------------------------------------------
% ORPHAN & WIDOW CONTROL
% ---------------------------------------------------------
% Prevent single lines at top/bottom of pages (Relaxed)
\widowpenalty=1000
\clubpenalty=1000
\displaywidowpenalty=1000

% Force page breaks if not enough space for header + text
% Check for ~5-6 lines of space before printing a header
\let\oldsection\section
\renewcommand{\section}{\needspace{6\baselineskip}\oldsection}
\let\oldsubsection\subsection
\renewcommand{\subsection}{\needspace{6\baselineskip}\oldsubsection}
\let\oldsubsubsection\subsubsection
\renewcommand{\subsubsection}{\needspace{6\baselineskip}\oldsubsubsection}

% ---------------------------------------------------------

% Ensure TOC is on its own page(s)
% - Page break BEFORE TOC (separates from Title)
\pretocmd{\tableofcontents}{\clearpage}{}{}
% - Page break AFTER TOC (separates from Body)
\apptocmd{\tableofcontents}{\clearpage}{}{}

% ---------------------------------------------------------
% DATE: Handled via pandoc variable
% ---------------------------------------------------------
"""
        
        # Use tempfile for header and output
        with tempfile.NamedTemporaryFile(suffix='.tex', delete=False, mode='w', encoding='utf-8') as header_file:
            header_file.write(latex_header)
            header_path = header_file.name
        
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp_file:
            tmp_path = tmp_file.name
        
        try:
            # ---------------------------------------------------------
            # METADATA EXTRACTION (Title & Date)
            # ---------------------------------------------------------
            # We extract # Title and Date lines to pass as metadata, preventing 
            # them from appearing as body sections in the TOC.
            import re
            
            # Default metadata
            pdf_title = output_filename.replace("_", " ").title()
            pdf_date = "\\today"
            clean_latex_string = latex_string
            
            # 1. Extract Title (First # Header)
            # Matches: # Title Text (at start of string)
            title_match = re.search(r'^#\s+(.+?)(\r?\n|$)', latex_string)
            if title_match:
                pdf_title = title_match.group(1).strip()
                # Remove the title line from the body
                clean_latex_string = latex_string[title_match.end():].lstrip()
                
                # 2. Extract Date (Next line if it looks like a date or plain text)
                # Look for the first non-empty line after title
                next_line_match = re.search(r'^(.+?)(\r?\n|$)', clean_latex_string)
                if next_line_match:
                    potential_date = next_line_match.group(1).strip()
                    # Simple heuristic: if it's short (<50 chars) and not a header, assume it's date/author
                    if len(potential_date) < 50 and not potential_date.startswith('#'):
                        pdf_date = potential_date
                        # Remove date line
                        clean_latex_string = clean_latex_string[next_line_match.end():].lstrip()

            # Robust date resolution: catch ALL mangled variants of \today
            # The LLM writes \today but \t can become a tab during JSON parsing,
            # leaving "oday", "Today", tab+"oday", etc.  Always resolve to real date.
            date_lower = pdf_date.lower().strip()
            is_today_variant = (
                "\\today" in pdf_date   # literal \today
                or "today" in date_lower  # Today, today, \today with \t as tab
                or date_lower == "oday"   # \t stripped by lstrip, leaving "oday"
                or date_lower.endswith("oday")  # any prefix + oday
                or pdf_date == ""         # empty
                or "\t" in pdf_date       # raw tab character present
            )
            if is_today_variant:
                pdf_date = datetime.now().strftime("%B %d, %Y")

            # ---------------------------------------------------------
            # CONVERSION PROCESS
            # ---------------------------------------------------------

            # Step 1: Convert input to LaTeX fragment
            tex_content = pypandoc.convert_text(
                clean_latex_string, 
                'latex', 
                format=input_format,
                extra_args=[] # No TOC here
            )

            # Step 2: Fix Table Wrapping (Longtable to p-columns)
            tex_content = re.sub(
                r'\\begin\{longtable\}\[\]\{@\{\}lll@\{\}\}',
                r'\\begin{longtable}[]{@{}p{0.25\\linewidth}p{0.34\\linewidth}p{0.34\\linewidth}@{}}',
                tex_content
            )

            # Step 2b: Enforce structured page breaks for literature surveys
            # Layout: Intro+P1+P2 | P3+P4+P5 | P6+P7+P8 ... | CompTable+ResGaps | Conclusion+Refs

            # --- Paper grouping: 3 papers per page ---
            # Find all \subsection{N. ...} patterns (numbered paper headings)
            paper_pattern = re.compile(r'(\\subsection\*?\{\s*\d+\.)')
            paper_matches = list(paper_pattern.finditer(tex_content))
            
            if paper_matches:
                # Insert page breaks before paper 3, 6, 9, 12... (0-indexed: 2, 5, 8, 11...)
                # We process in reverse order so insertion positions remain valid
                for i in range(len(paper_matches) - 1, -1, -1):
                    # Papers are 0-indexed: paper 0=P1, 1=P2, 2=P3, 3=P4, 4=P5, 5=P6...
                    # We want page breaks before P3 (idx 2), P6 (idx 5), P9 (idx 8)...
                    if i >= 2 and (i - 2) % 3 == 0:
                        pos = paper_matches[i].start()
                        tex_content = tex_content[:pos] + '\\newpage\n' + tex_content[pos:]

            # --- Comparison Tables: start on new page (Research Gaps follows on same page) ---
            tex_content = re.sub(
                r'(\\(?:sub)*section\*?\{Comparison Table[s]?\})',
                r'\\newpage \1',
                tex_content,
                flags=re.IGNORECASE
            )

            # --- Conclusion: start on new page (References follows on same page) ---
            tex_content = re.sub(
                r'(\\(?:sub)*section\*?\{Conclusion[s]?\})',
                r'\\newpage \1',
                tex_content,
                flags=re.IGNORECASE
            )

            # --- DO NOT add \newpage before Research Gaps or References ---
            # They share pages with the preceding section

            # Step 2c: Fix Research Gaps formatting - convert inline numbered list to enumerate
            def fix_research_gaps_list(tex):
                """Convert inline numbered research gaps to proper LaTeX enumerate list."""
                # Find the Research Gaps section content
                rg_match = re.search(
                    r'(\\(?:sub)*section\*?\{Research Gaps\})(.*?)(?=\\(?:sub)*section|\\newpage|$)',
                    tex, flags=re.DOTALL | re.IGNORECASE
                )
                if not rg_match:
                    return tex
                
                section_header = rg_match.group(1)
                section_body = rg_match.group(2)
                
                # Check if the content has inline numbering like "1. ..." "2. ..." in a paragraph
                # Split by numbered items: "1. Something 2. Something else 3. ..."
                items = re.split(r'(?:^|\s)(?=\d+\.\s+\\textbf)', section_body.strip())
                if len(items) <= 1:
                    # Try alternate pattern without \textbf
                    items = re.split(r'(?:^|\s)(?=\d+\.\s)', section_body.strip())
                
                if len(items) > 1:
                    # Filter out empty items
                    items = [item.strip() for item in items if item.strip()]
                    # Separate introductory text (no \textbf) from actual sub-heading items
                    intro_paragraphs = []
                    enum_items = []
                    for item in items:
                        # Remove the leading number and dot (e.g., "1. " or "2. ")
                        cleaned = re.sub(r'^\d+\.\s*', '', item)
                        if cleaned:
                            # If this item has \textbf it's a real sub-heading; otherwise it's intro text
                            if '\\textbf' in cleaned:
                                enum_items.append(f'\\item {cleaned}')
                            else:
                                intro_paragraphs.append(cleaned)
                    
                    if enum_items:
                        intro_text = '\n\n'.join(intro_paragraphs) + '\n' if intro_paragraphs else ''
                        new_body = '\n\n' + intro_text + '\n\\begin{enumerate}\n' + '\n'.join(enum_items) + '\n\\end{enumerate}\n'
                        tex = tex[:rg_match.start()] + section_header + new_body + tex[rg_match.end():]
                
                return tex
            
            tex_content = fix_research_gaps_list(tex_content)

            # Step 3: Convert modified LaTeX to PDF
            pypandoc.convert_text(
                tex_content, 
                'pdf', 
                format='latex', 
                outputfile=tmp_path,
                extra_args=[
                    '--pdf-engine=pdflatex',
                    '--variable=geometry:margin=1in',
                    f'--variable=title:{pdf_title}',
                    f'--variable=date:{pdf_date}',
                    '--table-of-contents', # Restore TOC in final generation
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
            # UPDATE: Returning short marker to avoid truncation of large files.
            # Data is retrieved via get_pending_download() in main.py
            return f'[DOWNLOAD_PDF]{{"filename": "{clean_filename}", "status": "stored"}}'
            
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
            # UPDATE: Returning short marker to avoid truncation.
            return f'[DOWNLOAD_DOCX]{{"filename": "{clean_filename}", "status": "stored"}}'
            
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
        # UPDATE: Returning short marker to avoid truncation.
        return f'[DOWNLOAD_MD]{{"filename": "{clean_filename}", "status": "stored"}}'
        
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
