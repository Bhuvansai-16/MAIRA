"""
Enhanced PDF Export Tool with Multi-Level Support
Generates professional PDFs with level-appropriate formatting and styling
"""
import base64
import io
import re
import threading
import requests
from datetime import datetime
from pydantic import BaseModel, Field
from langchain.tools import tool
from langchain_core.runnables import RunnableConfig

# Thread-safe storage for pending downloads indexed by filename
_pending_downloads = {}
_download_lock = threading.Lock()

def _store_pending_download(data: dict):
    """Store download data globally (indexed by filename)."""
    global _pending_downloads
    with _download_lock:
        if filename := data.get('filename'):
            _pending_downloads[filename] = data
            print(f"  💾 [pdftool] Download stored in pending: {filename}")

def get_pending_download(filename: str = None) -> dict | None:
    """Retrieve and remove pending download data by filename."""
    global _pending_downloads
    with _download_lock:
        if filename:
            return _pending_downloads.pop(filename, None)
        # Fallback to latest for legacy calls (if any)
        if _pending_downloads:
            latest_key = list(_pending_downloads.keys())[-1]
            return _pending_downloads.pop(latest_key)
        return None
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY

class DocSection(BaseModel):
    heading: str = Field(description="Section title")
    content: str = Field(description="Section content (supports Markdown tables and line breaks)")

class PDFExportInput(BaseModel):
    sections: list[DocSection] = Field(description="List of report sections")
    filename: str = Field(default="MAIRA_Report.pdf", description="Output filename")
    report_title: str = Field(default="Research Report", description="Main title for cover")
    report_level: str = Field(
        default="student",
        description="Report level: 'student', 'professor', or 'researcher'"
    )


def get_level_colors(report_level: str) -> dict:
    """Get color scheme based on report level."""
    color_schemes = {
        "student": {
            "title": colors.HexColor('#2980b9'),      # Friendly blue
            "heading": colors.HexColor('#3498db'),    # Bright blue
            "accent": colors.HexColor('#52A4DB'),
            "table_header": colors.HexColor('#3498db'),
            "table_alt": colors.HexColor('#ebf5fb')
        },
        "professor": {
            "title": colors.HexColor('#2c3e50'),      # Professional dark
            "heading": colors.HexColor('#34495e'),    # Slate
            "accent": colors.HexColor('#455A64'),
            "table_header": colors.HexColor('#34495e'),
            "table_alt": colors.HexColor('#ecf0f1')
        },
        "researcher": {
            "title": colors.HexColor('#1a1a1a'),      # Academic dark
            "heading": colors.HexColor('#2d2d2d'),    # Almost black
            "accent": colors.HexColor('#424242'),
            "table_header": colors.HexColor('#2d2d2d'),
            "table_alt": colors.HexColor('#f5f5f5')
        }
    }
    return color_schemes.get(report_level, color_schemes["student"])


def setup_level_styles(styles, report_level: str):
    """Create level-specific paragraph styles."""
    level_colors = get_level_colors(report_level)
    
    # Title style for cover page
    styles.add(ParagraphStyle(
        'CoverTitle',
        parent=styles['Title'],
        fontSize=32 if report_level == "student" else 28,
        spaceAfter=30,
        textColor=level_colors["title"],
        alignment=TA_CENTER,
        fontName='Helvetica-Bold'
    ))
    
    # Subtitle style
    styles.add(ParagraphStyle(
        'CoverSubtitle',
        parent=styles['Normal'],
        fontSize=16,
        spaceAfter=20,
        textColor=level_colors["accent"],
        alignment=TA_CENTER,
        fontName='Helvetica-Oblique'
    ))
    
    # Section heading style
    styles.add(ParagraphStyle(
        'SectionHeading',
        parent=styles['Heading1'],
        fontSize=18,
        spaceBefore=24,
        spaceAfter=12,
        textColor=colors.HexColor("#1E1B4B"),
        fontName='Helvetica-Bold',
        keepWithNext=True
    ))
    
    # Body text style (Unified for premium feel)
    styles.add(ParagraphStyle(
        'LevelBody',
        parent=styles['BodyText'],
        fontSize=11,
        leading=16,
        alignment=TA_JUSTIFY,
        fontName='Helvetica'
    ))
    
    # Bullet style
    styles.add(ParagraphStyle(
        'LevelBullet',
        parent=styles['LevelBody'],
        leftIndent=20,
        bulletIndent=10,
        spaceAfter=6
    ))


def parse_markdown_table(table_text: str) -> list[list[str]]:
    """
    Parse a Markdown table into a 2D list.
    Handles tables with format:
    | Header1 | Header2 |
    |---------|---------|
    | Data1   | Data2   |
    """
    lines = [line.strip() for line in table_text.strip().split('\n') if line.strip()]
    table_data = []
    
    for line in lines:
        # Skip separator lines (|---|---| etc.) - include | in char class for multi-column tables
        if re.match(r'^\|[\s\-:|]+\|$', line.replace(' ', '')):
            continue
        
        # Parse data rows
        if line.startswith('|') and line.endswith('|'):
            cells = [cell.strip() for cell in line[1:-1].split('|')]
            if cells:
                table_data.append(cells)
    
    return table_data


def create_table_flowable(table_data: list[list[str]], styles, report_level: str) -> Table:
    """
    Create a styled ReportLab Table from parsed table data with level-appropriate formatting.
    """
    if not table_data:
        return None
    
    level_colors = get_level_colors(report_level)
    
    # Cell styles
    cell_style = ParagraphStyle(
        'TableCell',
        parent=styles['BodyText'],
        fontSize=9,
        leading=11,
    )
    
    header_style = ParagraphStyle(
        'TableHeader',
        parent=styles['BodyText'],
        fontSize=10 if report_level == "student" else 9,
        leading=12,
        textColor=colors.white,
        fontName='Helvetica-Bold'
    )
    
    # Calculate column widths
    num_cols = len(table_data[0]) if table_data else 1
    available_width = 6.5 * inch  # Account for margins
    col_width = available_width / num_cols
    
    # Format data with Paragraphs for text wrapping
    formatted_data = []
    for row_idx, row in enumerate(table_data):
        formatted_row = []
        for cell in row:
            style = header_style if row_idx == 0 else cell_style
            # Truncate very long cells
            cell_text = cell[:200] + '...' if len(cell) > 200 else cell
            # Handle line breaks in cells
            cell_text = cell_text.replace('\n', '<br/>')
            # Sanitize stray HTML tags that would break ReportLab's XML parser
            cell_text = process_markdown_formatting(cell_text)
            formatted_row.append(Paragraph(cell_text, style))
        formatted_data.append(formatted_row)
    
    table = Table(formatted_data, colWidths=[col_width] * num_cols, repeatRows=1)
    
    # Level-specific table styling
    table_style = TableStyle([
        # Header row styling
        ('BACKGROUND', (0, 0), (-1, 0), level_colors["table_header"]),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('TOPPADDING', (0, 0), (-1, 0), 12),
        
        # Data rows styling
        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
        ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
        ('TOPPADDING', (0, 1), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 8),
        
        # Alternating row colors
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, level_colors["table_alt"]]),
        
        # Grid and borders
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e0')),
        ('BOX', (0, 0), (-1, -1), 1, level_colors["table_header"]),
        
        # Alignment
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),

        # Prevent individual rows from breaking across page boundaries
        ('NOSPLIT', (0, 0), (-1, -1)),
    ])
    
    table.setStyle(table_style)
    return table


def process_markdown_formatting(text: str) -> str:
    """Convert Markdown & LaTeX formatting to ReportLab HTML."""
    
    # --- Step 0: Clean LaTeX Math & Code Blocks BEFORE escaping ---
    # 1. Strip math delimiters like $ and $$
    text = text.replace('$$', '')
    text = re.sub(r'(?<!\\)\$([^\$]+)\$', r'\1', text)  # Removes inline $...$
    text = text.replace(r'\$', '')
    
    # 2. Convert common LaTeX symbols to Unicode so they render in standard PDF
    math_replacements = {
        r'\rightarrow': '→', r'\leftarrow': '←',
        r'\Rightarrow': '⇒', r'\Leftarrow': '⇐',
        r'\Lambda': 'Λ', r'\sigma': 'σ', r'\pm': '±',
        r'\approx': '≈', r'\mu': 'μ', r'\pi': 'π',
        r'\Delta': 'Δ', r'\times': '×', r'\leq': '≤',
        r'\geq': '≥', r'\infty': '∞',
        r'H_0': 'H₀', r'r_s': 'rₛ'
    }
    for old, new in math_replacements.items():
        text = text.replace(old, new)

    # --- Step 1: Preserve <br> tags via placeholder, then escape all < > ---
    text = re.sub(r'<br\s*/?>', '\x00BR\x00', text, flags=re.IGNORECASE)
    text = text.replace('<', '&lt;').replace('>', '&gt;')
    text = text.replace('\x00BR\x00', '<br/>')
    
    # --- Step 2: Escape bare & that aren't already part of an HTML entity ---
    text = re.sub(r'&(?!amp;|lt;|gt;|quot;|apos;|#)', '&amp;', text)
    
    # --- Step 3: Convert Markdown formatting to ReportLab XML tags ---
    # Handle multi-line and single-line code blocks: ```text something ```
    text = re.sub(r'```[a-zA-Z]*\s*(.+?)```', r'<font name="Courier">\1</font>', text, flags=re.DOTALL)
    # Handle Inline code: `something`
    text = re.sub(r'`([^`]+)`', r'<font name="Courier">\1</font>', text)
    
    # **bold** → <b>bold</b> (non-greedy)
    text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)
    # *italic* → <i>italic</i> (non-greedy, exclude asterisks in content)
    text = re.sub(r'\*([^*]+?)\*', r'<i>\1</i>', text)
    # [text](url) → <link href="url">text</link>
    text = re.sub(r'\[([^\]]+)\]\(([^\)]+)\)', r'<link href="\2" color="blue">\1</link>', text)
    
    return text


def process_content_with_tables(content: str, styles, report_level: str) -> list:
    """
    Process content with proper paragraph grouping and Markdown support.
    Consecutive regular text lines are joined into flowing paragraphs for
    proper justification, while bullets, headings, tables and images remain
    as separate flowables.
    """
    flowables = []

    # Normalize line breaks
    content = re.sub(r'\r\n', '\n', content)
    content = re.sub(r'<br\s*/?>', '\n', content, flags=re.IGNORECASE)
    lines = content.split('\n')

    i = 0
    current_para_lines = []  # Accumulate regular text lines for proper paragraphs

    def flush_paragraph():
        """Join accumulated lines into a single justified paragraph."""
        if current_para_lines:
            para_text = ' '.join(current_para_lines).strip()
            if para_text:
                para_text = process_markdown_formatting(para_text)
                flowables.append(Paragraph(para_text, styles['LevelBody']))
                flowables.append(Spacer(1, 6))
            current_para_lines.clear()

    while i < len(lines):
        line = lines[i].strip()
        raw_line = lines[i]  # Keep original for indentation-aware detection

        # ── Table detection ──
        if (line.startswith('|') and line.endswith('|') and line.count('|') >= 2 
            and i + 1 < len(lines) 
            and re.match(r'^\|[\s\-:|]+\|$', lines[i + 1].strip().replace(' ', ''))):
            flush_paragraph()
            next_line = lines[i + 1].strip()
            table_lines = [line, next_line]
            j = i + 2
            while j < len(lines):
                row_line = lines[j].strip()
                if row_line.startswith('|'):
                    if not row_line.endswith('|'):
                        row_line += ' |'
                    table_lines.append(row_line)
                    j += 1
                elif row_line == '':
                    j += 1
                else:
                    break

            table_text = '\n'.join(table_lines)
            table_data = parse_markdown_table(table_text)
            if table_data and len(table_data) > 1:
                table = create_table_flowable(table_data, styles, report_level)
                if table:
                    flowables.append(Spacer(1, 12))
                    flowables.append(table)
                    flowables.append(Spacer(1, 12))

            i = j
            continue

        # ── Image markdown: ![caption](url) ──
        img_match = re.match(r'^!\[([^\]]*)\]\(([^\)]+)\)$', line)
        if img_match:
            flush_paragraph()
            caption = img_match.group(1)
            img_url = img_match.group(2)
            try:
                response = requests.get(img_url, timeout=5, headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                })
                if response.status_code == 200:
                    img_data = io.BytesIO(response.content)
                    try:
                        img = Image(img_data, width=5*inch, height=3.5*inch, kind='proportional')
                        flowables.append(Spacer(1, 12))
                        flowables.append(img)
                        if caption:
                            flowables.append(Spacer(1, 6))
                            flowables.append(Paragraph(f"<i>Fig: {caption}</i>", styles['Italic']))
                        flowables.append(Spacer(1, 12))
                    except Exception as img_err:
                        print(f"Failed to create image flowable: {img_err}")
                else:
                    print(f"Failed to download image (HTTP {response.status_code}): {img_url}")
            except Exception as e:
                print(f"Failed to include image {img_url}: {e}")
            i += 1
            continue

        # ── Headings ──
        if line.startswith('#'):
            flush_paragraph()
            heading_match = re.match(r'^(#+)\s*(.*)', line)
            if heading_match:
                text = heading_match.group(2).strip()
                flowables.append(Paragraph(text, styles['SectionHeading']))
                # Removed manual spacer - rely on style.spaceAfter
            i += 1
            continue

        # ── Bullet / numbered lists ──
        stripped = raw_line.lstrip()
        if stripped.startswith(('- ', '• ', '* ')) or re.match(r'^\d+\.\s', stripped):
            flush_paragraph()
            if stripped.startswith(('- ', '• ', '* ')):
                bullet_text = stripped[2:].strip()
                bullet_text = process_markdown_formatting(bullet_text)
                flowables.append(Paragraph('• ' + bullet_text, styles['LevelBullet']))
            elif re.match(r'^\d+\.\s', stripped):
                match = re.match(r'^(\d+)\.\s+(.*)', stripped)
                if match:
                    num = match.group(1)
                    text = process_markdown_formatting(match.group(2))
                    flowables.append(Paragraph(f'{num}. {text}', styles['LevelBullet']))
            # Minimized spacing between list items for compact look
            flowables.append(Spacer(1, 1))
            i += 1
            continue

        # ── Empty line → flush current paragraph, add spacing ──
        if not line:
            flush_paragraph()
            # COALESCE: Only add spacer if we haven't just added one (avoid huge gaps)
            if flowables and not isinstance(flowables[-1], Spacer):
                flowables.append(Spacer(1, 8))
            i += 1
            continue

        # ── Regular text → accumulate for paragraph grouping ──
        current_para_lines.append(line)
        i += 1

    flush_paragraph()  # Final flush
    return flowables


def create_cover_page(report_title: str, report_level: str, styles) -> list:
    """Create a professional cover page with better title wrapping."""
    import os
    cover = []
    
    # --- INJECT MAIRA LOGO ---
    # logo_path is relative to the backend root or absolute
    logo_path = os.path.join(os.path.dirname(__file__), "logo", "DarkLogo.png")
    
    if os.path.exists(logo_path):
        try:
            # Increase logo size for better visibility
            logo = Image(logo_path, width=3.5*inch, height=1.8*inch, kind='proportional')
            logo.hAlign = 'CENTER' # Centers it beautifully on the page
            cover.append(Spacer(1, 1.5 * inch))
            cover.append(logo)
            cover.append(Spacer(1, 0.5 * inch)) # Adds breathing room below the logo
        except Exception as e:
            print(f"⚠️ Could not load logo into PDF: {e}")
            cover.append(Spacer(1, 2.5 * inch))
    else:
        # Fallback spacing if the logo file is accidentally deleted
        cover.append(Spacer(1, 2.5 * inch))
    # ------------------------------

    # Split long titles at colon for better wrapping
    if ':' in report_title:
        parts = report_title.split(':', 1)
        main_title = parts[0].strip() + ':'
        sub_title_text = parts[1].strip()

        cover.append(Paragraph(main_title, styles['CoverTitle']))
        cover.append(Spacer(1, 0.3 * inch))

        sub_style = ParagraphStyle(
            'CoverTitleSub',
            parent=styles['CoverTitle'],
            fontSize=28 if report_level == "student" else 24,
            leading=32 if report_level == "student" else 28,
            alignment=TA_CENTER
        )
        cover.append(Paragraph(sub_title_text, sub_style))
    else:
        cover.append(Paragraph(report_title, styles['CoverTitle']))

    cover.append(Spacer(1, 1.2 * inch))

    # Remove level subtitles for premium feel
    date_text = datetime.now().strftime('%B %d, %Y')
    cover.append(Paragraph(date_text, styles['Italic']))
    cover.append(Spacer(1, 12))
    cover.append(Paragraph("MAIRA Research Agent", styles['Italic']))

    cover.append(PageBreak())
    return cover


@tool(args_schema=PDFExportInput)
def export_to_pdf(
    sections: list[DocSection],
    filename: str = "MAIRA_Report.pdf",
    report_title: str = "Research Report",
    report_level: str = "student",
    config: RunnableConfig = None,
) -> str:
    """
    Generates a professional PDF with level-appropriate formatting and Markdown support.
    
    Report Levels:
    - student: Educational, readable, friendly (blue theme, clear spacing)
    - professor: Professional, organized, balanced (slate theme, structured)
    - researcher: Formal, academic, publication-ready (dark theme, compact)
    
    Supports:
    - Markdown tables with proper rendering
    - **bold** and *italic* formatting
    - [links](url) with clickable hyperlinks
    - Bullet points and lists
    - Images via ![caption](url) markdown syntax
    - Level-specific color schemes and spacing
    """
    
    clean_filename = filename.lstrip("/\\").replace(" ", "_")
    if not clean_filename.lower().endswith(".pdf"):
        clean_filename += ".pdf"
    # If still using the generic default, generate a descriptive filename from the title
    if clean_filename == "MAIRA_Report.pdf":
        slug = re.sub(r'[^\w\s-]', '', report_title).strip()
        slug = re.sub(r'[\s]+', '_', slug)[:80]  # Limit length
        clean_filename = f"{slug}_Report.pdf" if slug else clean_filename

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        topMargin=72,
        bottomMargin=72,
        leftMargin=72,
        rightMargin=72,
        title=report_title,
        author="MAIRA Research Agent",
    )
    
    story = []
    styles = getSampleStyleSheet()
    
    # Setup level-specific styles
    setup_level_styles(styles, report_level)
    
    # Add cover page
    story.extend(create_cover_page(report_title, report_level, styles))
    
    # Add sections
    for section in sections:
        # Section Heading
        story.append(Paragraph(section.heading, styles['SectionHeading']))
        # Spacer removed - handled by SectionHeading.spaceAfter

        # Process content with table and formatting support
        # This supports inline images via ![caption](url) markdown syntax
        content_flowables = process_content_with_tables(section.content, styles, report_level)
        story.extend(content_flowables)
        
        # Only add spacing if not the last section to avoid extra blank page
        if section != sections[-1]:
            story.append(Spacer(1, 20))  # Section spacing

    try:
        doc.build(story)
        buffer.seek(0)
        pdf_data = buffer.read()
        pdf_base64 = base64.b64encode(pdf_data).decode('utf-8')
        pdf_size_kb = len(pdf_data) / 1024
        
        # Store download data for backend recovery
        download_data = {"filename": clean_filename, "data": pdf_base64}
        _store_pending_download(download_data)
        
        print(f"  📄 PDF generated: {clean_filename} ({pdf_size_kb:.1f} KB)")
        
        return f'[DOWNLOAD_PDF]{{"filename": "{clean_filename}", "status": "stored"}}'
    except Exception as e:
        return f"PDF generation error: {str(e)}"