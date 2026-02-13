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
        print(f"  💾 [pdftool] Download stored in pending: {data.get('filename', 'unknown')}")

def get_pending_download() -> dict | None:
    """Retrieve and remove the latest pending download data."""
    global _latest_download
    with _download_lock:
        data = _latest_download
        _latest_download = None
        return data
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
        fontSize=16,
        spaceBefore=24,
        spaceAfter=12,
        textColor=level_colors["heading"],
        fontName='Helvetica-Bold'
    ))
    
    # Body text style (level-appropriate)
    if report_level == "student":
        body_leading = 16  # More line spacing for readability
        body_size = 11
    elif report_level == "professor":
        body_leading = 15
        body_size = 11
    else:  # researcher
        body_leading = 14
        body_size = 10
    
    styles.add(ParagraphStyle(
        'LevelBody',
        parent=styles['BodyText'],
        fontSize=body_size,
        leading=body_leading,
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
            formatted_row.append(Paragraph(cell_text, style))
        formatted_data.append(formatted_row)
    
    table = Table(formatted_data, colWidths=[col_width] * num_cols)
    
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
    ])
    
    table.setStyle(table_style)
    return table


def process_markdown_formatting(text: str) -> str:
    """Convert Markdown formatting to ReportLab HTML.
    
    Uses non-greedy matching for better handling of multiple formatting markers.
    """
    # **bold** → <b>bold</b> (non-greedy)
    text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)
    # *italic* → <i>italic</i> (non-greedy, exclude asterisks in content)
    text = re.sub(r'\*([^*]+?)\*', r'<i>\1</i>', text)
    # [text](url) → <link href="url">text</link>
    text = re.sub(r'\[([^\]]+)\]\(([^\)]+)\)', r'<link href="\2" color="blue">\1</link>', text)
    return text


def process_content_with_tables(content: str, styles, report_level: str) -> list:
    """
    Process content that may contain Markdown tables and formatting.
    Returns a list of flowables (Paragraphs and Tables).
    """
    flowables = []
    
    # More robust table detection: find tables by looking for header + separator pattern
    # then greedily consume all following lines that look like table rows
    lines = content.split('\n')
    i = 0
    
    while i < len(lines):
        line = lines[i].strip()
        
        # Check if this could be the start of a table (line with | characters)
        if line.startswith('|') and line.endswith('|') and line.count('|') >= 2:
            # Look ahead for separator line
            if i + 1 < len(lines):
                next_line = lines[i + 1].strip()
                # Check if it's a separator (|---|---|)
                if re.match(r'^\|[\s\-:|]+\|$', next_line.replace(' ', '')):
                    # Found a table! Collect all table rows
                    table_lines = [line, next_line]
                    j = i + 2
                    while j < len(lines):
                        row_line = lines[j].strip()
                        # Continue if line starts with | (table row)
                        if row_line.startswith('|'):
                            # Ensure it ends with | or add it
                            if not row_line.endswith('|'):
                                row_line += ' |'
                            table_lines.append(row_line)
                            j += 1
                        elif row_line == '':
                            # Empty line might be part of table, check next
                            j += 1
                        else:
                            # Non-table line, stop
                            break
                    
                    # Parse and render the table
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
        
        # Not a table - process as regular content
        if line:
            # Check for image markdown: ![caption](url)
            img_match = re.match(r'^!\[([^\]]*)\]\(([^\)]+)\)$', line)
            if img_match:
                caption = img_match.group(1)
                img_url = img_match.group(2)
                try:
                    # Download image from URL
                    response = requests.get(img_url, timeout=10, headers={
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                    })
                    if response.status_code == 200:
                        img_data = io.BytesIO(response.content)
                        # Create ReportLab Image (scaled to fit page width, max 5x3.5 inches)
                        try:
                            img = Image(img_data, width=5*inch, height=3.5*inch, kind='proportional')
                            flowables.append(Spacer(1, 12))
                            flowables.append(img)
                            if caption:
                                # Add caption below image
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
            
            # Handle bullet points
            if line.startswith('- ') or line.startswith('• '):
                para_text = line[2:]
                para_text = process_markdown_formatting(para_text)
                flowables.append(Paragraph('• ' + para_text, styles['LevelBullet']))
            elif re.match(r'^\d+\.\s', line):
                # Numbered list item
                num_match = re.match(r'^(\d+)\.\s+(.*)', line)
                if num_match:
                    num = num_match.group(1)
                    text = process_markdown_formatting(num_match.group(2))
                    flowables.append(Paragraph(f'{num}. {text}', styles['LevelBullet']))
            elif line.startswith('#'):
                # Heading
                heading_match = re.match(r'^(#+)\s*(.*)', line)
                if heading_match:
                    level = len(heading_match.group(1))
                    text = heading_match.group(2)
                    flowables.append(Paragraph(text, styles['SectionHeading']))
            else:
                # Regular paragraph
                para_text = process_markdown_formatting(line)
                flowables.append(Paragraph(para_text, styles['LevelBody']))
            
            flowables.append(Spacer(1, 4))
        
        i += 1
    
    return flowables


def create_cover_page(report_title: str, report_level: str, styles) -> list:
    """Create a professional cover page based on report level."""
    cover = []
    
    # Vertical spacing
    cover.append(Spacer(1, 2 * inch))
    
    # Title
    cover.append(Paragraph(report_title, styles['CoverTitle']))
    cover.append(Spacer(1, 0.5 * inch))
    
    # Subtitle based on level
    level_subtitles = {
        "student": "An Educational Guide",
        "professor": "A Teaching Resource",
        "researcher": "A Research Report"
    }
    subtitle = level_subtitles.get(report_level, "Report")
    cover.append(Paragraph(subtitle, styles['CoverSubtitle']))
    cover.append(Spacer(1, 0.3 * inch))
    
    # Date and generator
    date_text = f"Generated: {datetime.now().strftime('%B %d, %Y')}"
    cover.append(Paragraph(date_text, styles['Italic']))
    cover.append(Spacer(1, 6))
    cover.append(Paragraph("MAIRA Research Agent", styles['Italic']))
    
    # Page break
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

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        topMargin=72,
        bottomMargin=72,
        leftMargin=72,
        rightMargin=72
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
        story.append(Spacer(1, 12))

        # Process content with table and formatting support
        # This supports inline images via ![caption](url) markdown syntax
        content_flowables = process_content_with_tables(section.content, styles, report_level)
        story.extend(content_flowables)
        
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
        
        return f'[DOWNLOAD_PDF]{{"filename": "{clean_filename}", "data": "{pdf_base64}"}}'
    except Exception as e:
        return f"PDF generation error: {str(e)}"