import re

def clean_latex_text(text: str) -> str:
    """Convert basic LaTeX formatting to Markdown for tools."""
    if not text:
        return ""
        
    # Bold
    text = re.sub(r'\\textbf\{([^}]+)\}', r'**\1**', text)
    # Italic
    text = re.sub(r'\\textit\{([^}]+)\}', r'*\1*', text)
    text = re.sub(r'\\emph\{([^}]+)\}', r'*\1*', text)
    
    # Lists
    text = re.sub(r'\\begin\{itemize\}', '', text)
    text = re.sub(r'\\end\{itemize\}', '', text)
    text = re.sub(r'\\begin\{enumerate\}', '', text)
    text = re.sub(r'\\end\{enumerate\}', '', text)
    text = re.sub(r'\\item\s+', '- ', text)
    
    # Citations and Links
    text = re.sub(r'\\cite\{([^}]+)\}', r'[\1]', text)
    text = re.sub(r'\\href\{([^}]+)\}\{([^}]+)\}', r'[\2](\1)', text)
    text = re.sub(r'\\url\{([^}]+)\}', r'[\1](\1)', text)
    
    # Section references
    text = re.sub(r'\\ref\{([^}]+)\}', r'\1', text)
    
    # Layout commands (remove)
    # Remove commands that take no args or {} args that we want to ignore
    # This is tricky. We'll just remove common ones.
    text = re.sub(r'\\(maketitle|tableofcontents|newpage|clearpage|centering)', '', text)
    
    # Braces preservation? LaTeX often uses { } for grouping. 
    # Tools expects text.
    
    # Clean up multiple newlines
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    return text.strip()

def parse_latex_to_structure(latex: str) -> list[dict]:
    """
    Parse LaTeX into a list of dictionaries {"heading": str, "content": str}.
    """
    sections = []
    
    # Extract Title (metadata, not section?)
    # For now, we rely on the caller to extract title if needed for the tool args.
    
    # Handle Abstract
    # We look for \begin{abstract}...\end{abstract}
    abstract_match = re.search(r'\\begin\{abstract\}([\s\S]*?)\\end\{abstract\}', latex)
    if abstract_match:
        sections.append({
            "heading": "Abstract",
            "content": clean_latex_text(abstract_match.group(1))
        })
        # Remove abstract from latex to avoid duplication if it appears in intro?
        # Actually, split logic below handles body.
        
    # Isolate Body
    body = latex
    if '\\begin{document}' in body:
        parts = body.split('\\begin{document}')
        body = parts[1]
    if '\\end{document}' in body:
        body = body.split('\\end{document}')[0]
        
    # Remove Abstract from body if present
    body = re.sub(r'\\begin\{abstract\}[\s\S]*?\\end\{abstract\}', '', body)
    
    # Split by \section
    # Use capturing group to keep the headings
    parts = re.split(r'\\section\*?\{([^}]+)\}', body)
    
    # parts[0] is pre-section content
    pre_content = clean_latex_text(parts[0])
    if pre_content and len(pre_content) > 50:
         sections.append({"heading": "Introduction", "content": pre_content})
         
    # Iterate pairs
    for i in range(1, len(parts), 2):
        heading = parts[i].strip()
        content = parts[i+1]
        
        # Subsections?
        # For simplicity, we currently treat subsections as part of the content,
        # but we could convert \subsection{...} to Markdown `### ...`
        content = re.sub(r'\\subsection\*?\{([^}]+)\}', r'\n### \1\n', content)
        content = re.sub(r'\\subsubsection\*?\{([^}]+)\}', r'\n#### \1\n', content)
        
        cleaned_content = clean_latex_text(content)
        sections.append({
            "heading": heading,
            "content": cleaned_content
        })
        
    if not sections:
        # Fallback
        sections.append({"heading": "Document", "content": clean_latex_text(body)})
        
    return sections
