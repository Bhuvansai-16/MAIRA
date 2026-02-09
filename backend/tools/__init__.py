"""Tools package for MAIRA research agent (Production-Hardened)"""

from .searchtool import internet_search
from .extracttool import extract_webpage
from .arxivertool import arxiv_tool
from .pdftool import export_to_pdf
from .doctool import export_to_docx
from .latextoformate import convert_latex_to_all_formats

# Verification tools with Pydantic schemas for Gemini compatibility
from .verification_tools import (
    # Tools
    validate_citations,
    fact_check_claims,
    assess_content_quality,
    cross_reference_sources,
    verify_draft_completeness,
    # Pydantic Schemas (for Gemini strict validation)
    CitationValidationInput,
    FactCheckInput,
    ContentQualityInput,
    CrossRefInput,
    CompletenessInput,
    SourceItem,
    # Aggregate helper
    run_full_verification
)

__all__ = [
    # Core tools
    'internet_search',
    'extract_webpage',
    'arxiv_tool',
    'export_to_pdf',
    'export_to_docx',
    # Verification tools
    'validate_citations',
    'fact_check_claims',
    'assess_content_quality',
    'cross_reference_sources',
    'verify_draft_completeness',
    # Schemas
    'CitationValidationInput',
    'FactCheckInput',
    'ContentQualityInput',
    'CrossRefInput',
    'CompletenessInput',
    'SourceItem',
    # Helper
    'run_full_verification'
    'convert_latex_to_all_formats'
]
