import base64
import io
import re
from datetime import datetime
from pydantic import BaseModel, Field
from langchain.tools import tool
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import inch

class DocSection(BaseModel):
    heading: str = Field(description="Section title")
    content: str = Field(description="Section content (supports Markdown tables and line breaks)")

class PDFExportInput(BaseModel):
    sections: list[DocSection] = Field(description="List of report sections")
    filename: str = Field(default="MAIRA_Report.pdf", description="Output filename")
    report_title: str = Field(default="Research Report", description="Main title for cover")


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
        # Skip separator lines (|---|---|)
        if re.match(r'^\|[\s\-:]+\|$', line.replace(' ', '')):
            continue
        
        # Parse data rows
        if line.startswith('|') and line.endswith('|'):
            cells = [cell.strip() for cell in line[1:-1].split('|')]
            if cells:
                table_data.append(cells)
    
    return table_data


def create_table_flowable(table_data: list[list[str]], styles) -> Table:
    """
    Create a styled ReportLab Table from parsed table data.
    """
    if not table_data:
        return None
    
    # Wrap cell content in Paragraphs for text wrapping
    cell_style = ParagraphStyle(
        'TableCell',
        parent=styles['BodyText'],
        fontSize=9,
        leading=11,
    )
    
    header_style = ParagraphStyle(
        'TableHeader',
        parent=styles['BodyText'],
        fontSize=9,
        leading=11,
        textColor=colors.white,
        fontName='Helvetica-Bold'
    )
    
    # Calculate column widths based on page width
    num_cols = len(table_data[0]) if table_data else 1
    available_width = 6.5 * inch  # Account for margins
    col_width = available_width / num_cols
    
    formatted_data = []
    for row_idx, row in enumerate(table_data):
        formatted_row = []
        for cell in row:
            # Use header style for first row, body style for rest
            style = header_style if row_idx == 0 else cell_style
            # Truncate very long cells to prevent overflow
            cell_text = cell[:200] + '...' if len(cell) > 200 else cell
            formatted_row.append(Paragraph(cell_text, style))
        formatted_data.append(formatted_row)
    
    table = Table(formatted_data, colWidths=[col_width] * num_cols)
    
    # Professional table styling
    table_style = TableStyle([
        # Header row styling
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a365d')),  # Dark blue header
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
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f0f4f8')]),
        
        # Grid and borders
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e0')),
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#1a365d')),
        
        # Alignment
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ])
    
    table.setStyle(table_style)
    return table


def process_content_with_tables(content: str, styles) -> list:
    """
    Process content that may contain Markdown tables.
    Returns a list of flowables (Paragraphs and Tables).
    """
    flowables = []
    
    # Regex to find Markdown tables
    # Matches tables that start with | and have at least a header row and separator
    table_pattern = r'(\|[^\n]+\|\n\|[\s\-:]+\|(?:\n\|[^\n]+\|)*)'
    
    # Split content by tables
    parts = re.split(table_pattern, content, flags=re.MULTILINE)
    
    for part in parts:
        part = part.strip()
        if not part:
            continue
        
        # Check if this part is a Markdown table
        if part.startswith('|') and '|' in part and '\n' in part:
            # Check for separator line (indicates it's a proper table)
            if re.search(r'\|[\s\-:]+\|', part):
                table_data = parse_markdown_table(part)
                if table_data and len(table_data) > 1:  # At least header + 1 row
                    table = create_table_flowable(table_data, styles)
                    if table:
                        flowables.append(Spacer(1, 12))
                        flowables.append(table)
                        flowables.append(Spacer(1, 12))
                        continue
        
        # Regular paragraph content
        paragraphs = [p.strip() for p in part.split('\n\n') if p.strip()]
        for para in paragraphs:
            # Clean up any remaining table-like syntax that wasn't matched
            para = re.sub(r'\|', '', para)
            formatted = para.replace('\n', '<br/>')
            flowables.append(Paragraph(formatted, styles['BodyText']))
            flowables.append(Spacer(1, 8))
    
    return flowables


@tool(args_schema=PDFExportInput)
def export_to_pdf(
    sections: list[DocSection],
    filename: str = "MAIRA_Report.pdf",
    report_title: str = "Research Report"
) -> str:
    """Generates a professional PDF with Markdown table support and returns base64 for download."""
    clean_filename = filename.lstrip("/\\").replace(" ", "_")
    if not clean_filename.lower().endswith(".pdf"):
        clean_filename += ".pdf"

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=72, bottomMargin=72)
    story = []
    styles = getSampleStyleSheet()
    
    # Custom styles
    styles.add(ParagraphStyle(
        'CustomTitle',
        parent=styles['Title'],
        fontSize=28,
        spaceAfter=20,
        textColor=colors.HexColor('#1a365d')
    ))
    
    styles.add(ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading1'],
        fontSize=16,
        spaceBefore=20,
        spaceAfter=12,
        textColor=colors.HexColor('#2d3748')
    ))

    # Title Page
    story.append(Spacer(1, 2 * inch))
    story.append(Paragraph(report_title, styles['CustomTitle']))
    story.append(Spacer(1, 48))
    story.append(Paragraph(f"Generated: {datetime.now().strftime('%B %d, %Y')}", styles['Italic']))
    story.append(Paragraph("MAIRA Research Agent", styles['Italic']))
    story.append(PageBreak())

    for section in sections:
        # Section Heading
        story.append(Paragraph(section.heading, styles['CustomHeading']))
        story.append(Spacer(1, 12))

        # Process content with table support
        content_flowables = process_content_with_tables(section.content, styles)
        story.extend(content_flowables)
        
        story.append(Spacer(1, 20))  # Section spacing

    try:
        doc.build(story)
        buffer.seek(0)
        pdf_base64 = base64.b64encode(buffer.read()).decode('utf-8')
        return f'[DOWNLOAD_PDF]{{"filename": "{clean_filename}", "data": "{pdf_base64}"}}'
    except Exception as e:
        return f"PDF generation error: {str(e)}"