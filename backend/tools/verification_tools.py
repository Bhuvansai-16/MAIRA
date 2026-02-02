"""
Verification Tools for Deep Reasoning Agent (Production-Hardened)
Includes citation validation, fact-checking, and content quality assessment
with Pydantic schemas for Gemini compatibility and async parallel processing.
"""
import os
import re
import asyncio
import aiohttp
from typing import Dict, List, Any, Optional
from concurrent.futures import ThreadPoolExecutor
from tavily import TavilyClient
from dotenv import load_dotenv
from langchain_core.tools import tool
from pydantic import BaseModel, Field
import requests
from urllib.parse import urlparse

load_dotenv()

# Initialize Tavily client with error handling
try:
    tavily_client = TavilyClient(api_key=os.environ.get("TAVILY_API_KEY", ""))
except Exception as e:
    print(f"⚠️ Tavily client initialization warning: {e}")
    tavily_client = None

# Thread pool for async operations
executor = ThreadPoolExecutor(max_workers=10)


# =============================================================================
# PYDANTIC SCHEMAS FOR GEMINI COMPATIBILITY
# =============================================================================

class CitationValidationInput(BaseModel):
    """Schema for citation validation input."""
    draft_content: str = Field(
        description="The draft text containing citations in [Source Name](URL) format"
    )


class FactCheckInput(BaseModel):
    """Schema for fact-checking input - Gemini-compatible list handling."""
    claims: List[str] = Field(
        description="A list of specific factual claims to verify (e.g., statistics, dates, technical specifications)",
        min_length=1,
        max_length=10
    )


class ContentQualityInput(BaseModel):
    """Schema for content quality assessment input."""
    draft_content: str = Field(
        description="The complete draft text to assess for quality"
    )


class SourceItem(BaseModel):
    """Schema for a single source item."""
    url: str = Field(description="The full URL of the source")
    title: str = Field(default="", description="The title of the paper or website")


class CrossRefInput(BaseModel):
    """Schema for cross-reference sources input - Gemini-compatible nested lists."""
    web_sources: List[SourceItem] = Field(
        default=[],
        description="Sources from the web search agent with url and title"
    )
    academic_sources: List[SourceItem] = Field(
        default=[],
        description="Sources from the academic agent with url and title"
    )
    draft_citations: List[str] = Field(
        default=[],
        description="List of URLs actually cited in the draft"
    )


class CompletenessInput(BaseModel):
    """Schema for draft completeness verification input."""
    draft_content: str = Field(
        description="The complete draft text"
    )
    research_query: str = Field(
        description="The original user research question/topic"
    )


# =============================================================================
# ASYNC HELPER FUNCTIONS
# =============================================================================

async def check_url_async(session: aiohttp.ClientSession, url: str, timeout: int = 5) -> Dict[str, Any]:
    """Asynchronously check if a URL is accessible."""
    try:
        async with session.head(url, timeout=aiohttp.ClientTimeout(total=timeout), allow_redirects=True) as response:
            return {
                "url": url,
                "accessible": response.status < 400,
                "status_code": response.status,
                "error": None
            }
    except asyncio.TimeoutError:
        return {"url": url, "accessible": False, "status_code": None, "error": "Timeout"}
    except Exception as e:
        return {"url": url, "accessible": False, "status_code": None, "error": str(e)[:100]}


async def fact_check_single_claim(claim: str) -> Dict[str, Any]:
    """Asynchronously fact-check a single claim using Tavily."""
    if not tavily_client:
        return {
            "claim": claim,
            "verified": False,
            "error": "Tavily client not initialized",
            "sources": []
        }
    
    try:
        loop = asyncio.get_event_loop()
        # Run the synchronous Tavily search in a thread pool
        search_result = await loop.run_in_executor(
            executor,
            lambda: tavily_client.search(
                query=claim,
                max_results=3,
                topic="general",
                include_answer=True,
                search_depth="advanced"
            )
        )
        
        answer = search_result.get("answer", "")
        sources = search_result.get("results", [])
        
        return {
            "claim": claim,
            "verified": bool(answer and len(sources) > 0),
            "answer": answer,
            "sources": [
                {
                    "title": s.get("title", "Unknown"),
                    "url": s.get("url", ""),
                    "snippet": s.get("content", "")[:200]
                }
                for s in sources[:3]
            ],
            "error": None
        }
    except Exception as e:
        return {
            "claim": claim,
            "verified": False,
            "error": str(e)[:200],
            "sources": []
        }


async def validate_citations_async(citations: List[tuple]) -> List[Dict[str, Any]]:
    """Validate multiple citations in parallel."""
    async with aiohttp.ClientSession() as session:
        tasks = [check_url_async(session, url) for _, url in citations]
        return await asyncio.gather(*tasks, return_exceptions=True)


async def fact_check_claims_async(claims: List[str]) -> List[Dict[str, Any]]:
    """Fact-check multiple claims in parallel."""
    tasks = [fact_check_single_claim(claim) for claim in claims]
    return await asyncio.gather(*tasks, return_exceptions=True)


# =============================================================================
# VERIFICATION TOOLS WITH PYDANTIC SCHEMAS
# =============================================================================

@tool(args_schema=CitationValidationInput)
def validate_citations(draft_content: str) -> Dict[str, Any]:
    """
    Validates citations in the draft by checking:
    1. Citation format correctness
    2. URL accessibility (parallel async checks)
    3. Citation completeness across sections
    
    Returns validation results including issues found and recommendations.
    """
    print("🔍 Validating citations in draft...")
    
    # Extract citations using regex pattern [text](url)
    citation_pattern = r'\[([^\]]+)\]\(([^\)]+)\)'
    citations = re.findall(citation_pattern, draft_content)
    
    results = {
        "total_citations": len(citations),
        "valid_citations": [],
        "invalid_citations": [],
        "broken_urls": [],
        "missing_citations_sections": [],
        "issues": [],
        "status": "valid",
        "score": 100
    }
    
    if len(citations) == 0:
        results["issues"].append("No citations found in the draft")
        results["status"] = "invalid"
        results["score"] = 0
        return results
    
    # Validate URL formats first (sync)
    valid_format_citations = []
    for citation_text, url in citations:
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            results["invalid_citations"].append({
                "text": citation_text,
                "url": url,
                "issue": "Invalid URL format"
            })
            results["issues"].append(f"Invalid URL format: [{citation_text}]({url})")
        else:
            valid_format_citations.append((citation_text, url))
    
    # Check URL accessibility in parallel (async)
    if valid_format_citations:
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            url_results = loop.run_until_complete(validate_citations_async(valid_format_citations))
            loop.close()
            
            for (citation_text, url), check_result in zip(valid_format_citations, url_results):
                if isinstance(check_result, Exception):
                    results["broken_urls"].append({
                        "text": citation_text,
                        "url": url,
                        "error": str(check_result)
                    })
                    results["issues"].append(f"URL check failed: [{citation_text}]({url})")
                elif check_result.get("accessible"):
                    results["valid_citations"].append({
                        "text": citation_text,
                        "url": url
                    })
                else:
                    results["broken_urls"].append({
                        "text": citation_text,
                        "url": url,
                        "status_code": check_result.get("status_code"),
                        "error": check_result.get("error")
                    })
                    error_detail = check_result.get("error") or f"HTTP {check_result.get('status_code')}"
                    results["issues"].append(f"Broken URL ({error_detail}): [{citation_text}]({url})")
        except Exception as e:
            # Fallback to sync if async fails
            print(f"⚠️ Async URL check failed, using sync fallback: {e}")
            for citation_text, url in valid_format_citations:
                try:
                    response = requests.head(url, timeout=5, allow_redirects=True)
                    if response.status_code < 400:
                        results["valid_citations"].append({"text": citation_text, "url": url})
                    else:
                        results["broken_urls"].append({
                            "text": citation_text, "url": url, "status_code": response.status_code
                        })
                        results["issues"].append(f"Broken URL (HTTP {response.status_code}): [{citation_text}]({url})")
                except Exception as req_e:
                    results["broken_urls"].append({"text": citation_text, "url": url, "error": str(req_e)})
    
    # Check for sections that should have citations but don't
    sections = re.split(r'\n##\s+', draft_content)
    for section in sections[1:]:
        section_name = section.split('\n')[0].strip()
        section_content = '\n'.join(section.split('\n')[1:])
        
        if section_name.lower() in ['references', 'conclusion', 'executive summary']:
            continue
            
        section_citations = re.findall(citation_pattern, section_content)
        if len(section_citations) == 0 and len(section_content) > 200:
            results["missing_citations_sections"].append(section_name)
            results["issues"].append(f"Section '{section_name}' lacks citations")
    
    # Calculate score
    valid_count = len(results["valid_citations"])
    total_count = len(citations)
    results["score"] = round((valid_count / total_count) * 100) if total_count > 0 else 0
    
    # Determine status based on score
    if results["score"] < 50 or len(results["broken_urls"]) > 3:
        results["status"] = "invalid"
    elif results["score"] < 80 or len(results["issues"]) > 2:
        results["status"] = "needs_revision"
    
    print(f"✅ Citation validation complete: {valid_count}/{total_count} valid (Score: {results['score']}/100)")
    return results


@tool(args_schema=FactCheckInput)
def fact_check_claims(claims: List[str]) -> Dict[str, Any]:
    """
    Fact-checks specific claims using PARALLEL web searches for maximum efficiency.
    Checks all claims simultaneously (~2s) instead of sequentially (~10s).
    
    Returns fact-check results for each claim with verification status.
    """
    print(f"🔎 Parallel fact-checking {len(claims)} claims...")
    
    results = {
        "total_claims": len(claims),
        "verified_claims": [],
        "unverified_claims": [],
        "contradicted_claims": [],
        "issues": [],
        "status": "valid",
        "score": 100,
        "verification_rate": 0
    }
    
    if not claims:
        results["issues"].append("No claims provided for verification")
        results["status"] = "invalid"
        results["score"] = 0
        return results
    
    # Run parallel fact-checking
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        check_results = loop.run_until_complete(fact_check_claims_async(claims))
        loop.close()
        
        for claim_result in check_results:
            if isinstance(claim_result, Exception):
                results["unverified_claims"].append({
                    "claim": "Unknown",
                    "error": str(claim_result)
                })
                results["issues"].append(f"Fact-check error: {str(claim_result)[:100]}")
            elif claim_result.get("error"):
                results["unverified_claims"].append(claim_result)
                results["issues"].append(f"Could not verify: {claim_result['claim'][:80]}...")
            elif claim_result.get("verified"):
                results["verified_claims"].append(claim_result)
            else:
                results["unverified_claims"].append(claim_result)
                results["issues"].append(f"Could not verify: {claim_result['claim'][:80]}...")
                
    except Exception as e:
        print(f"⚠️ Async fact-check failed, using sync fallback: {e}")
        # Fallback to synchronous checking
        for claim in claims:
            try:
                if tavily_client:
                    search_result = tavily_client.search(
                        query=claim, max_results=3, search_depth="basic"
                    )
                    answer = search_result.get("answer", "")
                    sources = search_result.get("results", [])
                    
                    if answer and len(sources) > 0:
                        results["verified_claims"].append({
                            "claim": claim,
                            "verified": True,
                            "sources": [{"title": s.get("title"), "url": s.get("url")} for s in sources[:2]]
                        })
                    else:
                        results["unverified_claims"].append({"claim": claim, "verified": False})
                        results["issues"].append(f"Could not verify: {claim[:80]}...")
                else:
                    results["unverified_claims"].append({"claim": claim, "error": "No Tavily client"})
            except Exception as inner_e:
                results["unverified_claims"].append({"claim": claim, "error": str(inner_e)})
    
    # Calculate metrics
    verified_count = len(results["verified_claims"])
    total_count = len(claims)
    results["verification_rate"] = round((verified_count / total_count) * 100) if total_count > 0 else 0
    results["score"] = results["verification_rate"]
    
    # Determine status
    if len(results["contradicted_claims"]) > 0:
        results["status"] = "invalid"
    elif results["verification_rate"] < 50:
        results["status"] = "needs_revision"
    elif results["verification_rate"] < 80:
        results["status"] = "needs_revision"
    
    print(f"✅ Fact-check complete: {verified_count}/{total_count} verified ({results['verification_rate']}%)")
    return results


@tool(args_schema=ContentQualityInput)
def assess_content_quality(draft_content: str) -> Dict[str, Any]:
    """
    Assesses the overall quality of the draft content by checking:
    1. Structure completeness (required sections)
    2. Content depth (paragraph lengths, detail level)
    3. Table presence and formatting
    
    Returns quality assessment results with scores and recommendations.
    """
    print("📊 Assessing content quality...")
    
    results = {
        "structure_score": 0,
        "content_depth_score": 0,
        "table_score": 0,
        "overall_score": 0,
        "found_sections": [],
        "missing_sections": [],
        "short_sections": [],
        "issues": [],
        "recommendations": [],
        "status": "valid"
    }
    
    # Required sections check
    required_sections = [
        "Executive Summary",
        "Introduction", 
        "Literature Review",
        "Comparative Analysis",
        "Future Directions",
        "Conclusion",
        "References"
    ]
    
    for section in required_sections:
        pattern = rf'##\s+{re.escape(section)}'
        if re.search(pattern, draft_content, re.IGNORECASE):
            results["found_sections"].append(section)
        else:
            results["missing_sections"].append(section)
    
    results["structure_score"] = round((len(results["found_sections"]) / len(required_sections)) * 100)
    
    if results["missing_sections"]:
        results["issues"].append(f"Missing sections: {', '.join(results['missing_sections'])}")
    
    # Content depth check
    sections = re.split(r'\n##\s+', draft_content)
    total_section_score = 0
    section_count = 0
    
    for section in sections[1:]:
        section_name = section.split('\n')[0].strip()
        section_content = '\n'.join(section.split('\n')[1:])
        
        if 'reference' in section_name.lower():
            continue
        
        word_count = len(section_content.split())
        section_count += 1
        
        # Score based on word count
        if section_name.lower() == 'executive summary':
            if word_count >= 50:
                total_section_score += 100
            else:
                total_section_score += (word_count / 50) * 100
        else:
            if word_count >= 150:
                total_section_score += 100
            elif word_count >= 100:
                total_section_score += 80
            elif word_count >= 50:
                total_section_score += 50
                results["short_sections"].append(f"{section_name} ({word_count} words)")
            else:
                total_section_score += 20
                results["short_sections"].append(f"{section_name} ({word_count} words)")
    
    results["content_depth_score"] = round(total_section_score / max(section_count, 1))
    
    if results["short_sections"]:
        results["issues"].append(f"Sections need more detail: {', '.join(results['short_sections'])}")
    
    # Table presence check
    table_pattern = r'\|[^\n]+\|[^\n]+\n\|[-:\s\|]+\|'
    tables = re.findall(table_pattern, draft_content)
    
    if len(tables) == 0:
        results["table_score"] = 0
        results["issues"].append("No comparison tables found in draft")
    else:
        results["table_score"] = 100
        
        # Check if table is in Comparative Analysis section
        comp_pattern = r'##\s+Comparative Analysis.*?(?=\n##|\Z)'
        comp_section = re.search(comp_pattern, draft_content, re.IGNORECASE | re.DOTALL)
        
        if comp_section and not re.search(table_pattern, comp_section.group(0)):
            results["issues"].append("Comparative Analysis section lacks a table")
            results["table_score"] = 50
    
    # Calculate overall score
    results["overall_score"] = round(
        (results["structure_score"] * 0.3 + 
         results["content_depth_score"] * 0.4 + 
         results["table_score"] * 0.3)
    )
    
    # Generate recommendations
    if results["overall_score"] >= 85:
        results["status"] = "valid"
        results["recommendations"].append("Draft meets quality standards - ready for final report")
    elif results["overall_score"] >= 60:
        results["status"] = "needs_revision"
        results["recommendations"].append("Draft requires targeted improvements before finalization")
        if results["structure_score"] < 80:
            results["recommendations"].append(f"Add missing sections: {', '.join(results['missing_sections'])}")
        if results["content_depth_score"] < 80:
            results["recommendations"].append("Expand short sections with more detail")
        if results["table_score"] < 80:
            results["recommendations"].append("Add comparison table to Comparative Analysis section")
    else:
        results["status"] = "invalid"
        results["recommendations"].append("Draft needs significant revision - consider restarting research")
    
    print(f"✅ Quality assessment complete: Score {results['overall_score']}/100 ({results['status'].upper()})")
    return results


@tool(args_schema=CrossRefInput)
def cross_reference_sources(
    web_sources: List[SourceItem],
    academic_sources: List[SourceItem],
    draft_citations: List[str]
) -> Dict[str, Any]:
    """
    Cross-references sources from different agents to ensure all gathered sources are cited.
    Uses explicit Pydantic schemas for Gemini compatibility.
    
    Returns cross-reference results with coverage metrics.
    """
    print("🔗 Cross-referencing sources...")
    
    # Extract URLs from source items
    all_source_urls = set()
    for source in web_sources:
        if isinstance(source, dict):
            url = source.get('url', '')
        else:
            url = source.url if hasattr(source, 'url') else ''
        if url:
            all_source_urls.add(url)
    
    for source in academic_sources:
        if isinstance(source, dict):
            url = source.get('url', '')
        else:
            url = source.url if hasattr(source, 'url') else ''
        if url:
            all_source_urls.add(url)
    
    draft_citation_urls = set(draft_citations) if draft_citations else set()
    
    results = {
        "total_sources_gathered": len(all_source_urls),
        "total_citations_in_draft": len(draft_citation_urls),
        "sources_cited": len(draft_citation_urls.intersection(all_source_urls)),
        "unused_sources": list(all_source_urls - draft_citation_urls),
        "external_citations": list(draft_citation_urls - all_source_urls),
        "coverage_percentage": 0,
        "issues": [],
        "status": "valid",
        "score": 100
    }
    
    # Calculate coverage
    if len(all_source_urls) > 0:
        results["coverage_percentage"] = round(
            (results["sources_cited"] / len(all_source_urls)) * 100, 2
        )
    
    results["score"] = min(100, results["coverage_percentage"])
    
    # Generate issues
    if len(results["unused_sources"]) > 0:
        results["issues"].append(
            f"{len(results['unused_sources'])} gathered sources not cited in draft"
        )
    
    if len(results["external_citations"]) > 5:
        results["issues"].append(
            f"{len(results['external_citations'])} citations from unknown sources"
        )
    
    # Determine status
    if results["coverage_percentage"] < 30:
        results["status"] = "invalid"
        results["issues"].append(f"Critical: Only {results['coverage_percentage']}% source coverage")
    elif results["coverage_percentage"] < 60:
        results["status"] = "needs_revision"
        results["issues"].append(f"Low source coverage: {results['coverage_percentage']}%")
    
    print(f"✅ Cross-reference complete: {results['coverage_percentage']}% coverage")
    return results


@tool(args_schema=CompletenessInput)
def verify_draft_completeness(draft_content: str, research_query: str) -> Dict[str, Any]:
    """
    Verifies if the draft adequately addresses the original research query.
    Uses keyword analysis and topic alignment scoring.
    
    Returns completeness verification results with alignment score.
    """
    print("📋 Verifying draft completeness...")
    
    results = {
        "query_keywords_coverage": [],
        "missing_keywords": [],
        "topic_alignment_score": 0,
        "word_count": 0,
        "issues": [],
        "status": "valid",
        "score": 100
    }
    
    # Calculate word count
    results["word_count"] = len(draft_content.split())
    
    # Extract key terms from research query
    query_words = set(re.findall(r'\b\w{4,}\b', research_query.lower()))
    stop_words = {
        'what', 'when', 'where', 'which', 'how', 'why', 'about', 'with', 
        'from', 'this', 'that', 'these', 'those', 'have', 'been', 'would',
        'could', 'should', 'their', 'them', 'they', 'will', 'your', 'more'
    }
    query_keywords = query_words - stop_words
    
    draft_lower = draft_content.lower()
    
    for keyword in query_keywords:
        if keyword in draft_lower:
            results["query_keywords_coverage"].append(keyword)
        else:
            results["missing_keywords"].append(keyword)
    
    # Calculate alignment score
    if len(query_keywords) > 0:
        results["topic_alignment_score"] = round(
            (len(results["query_keywords_coverage"]) / len(query_keywords)) * 100, 2
        )
    else:
        results["topic_alignment_score"] = 100  # No keywords to check
    
    results["score"] = results["topic_alignment_score"]
    
    # Check word count minimums
    if results["word_count"] < 500:
        results["issues"].append(f"Draft too short: {results['word_count']} words (minimum 500)")
        results["score"] = min(results["score"], 50)
    
    # Determine status
    if results["topic_alignment_score"] < 40:
        results["status"] = "invalid"
        results["issues"].append(
            f"Critical: Draft only {results['topic_alignment_score']}% aligned with research query"
        )
        if results["missing_keywords"]:
            results["issues"].append(f"Missing key terms: {', '.join(results['missing_keywords'][:5])}")
    elif results["topic_alignment_score"] < 70:
        results["status"] = "needs_revision"
        results["issues"].append(
            f"Draft has moderate alignment ({results['topic_alignment_score']}%) with research query"
        )
    
    print(f"✅ Completeness check: {results['topic_alignment_score']}% topic alignment")
    return results


# =============================================================================
# AGGREGATE VERIFICATION FUNCTION
# =============================================================================

def run_full_verification(
    draft_content: str,
    research_query: str,
    web_sources: List[Dict] = None,
    academic_sources: List[Dict] = None,
    claims_to_verify: List[str] = None
) -> Dict[str, Any]:
    """
    Runs all verification checks and returns an aggregate result.
    This is a helper function for programmatic use (not a tool).
    """
    print("\n" + "="*60)
    print("🔬 RUNNING FULL VERIFICATION SUITE")
    print("="*60 + "\n")
    
    aggregate = {
        "overall_status": "valid",
        "overall_score": 100,
        "checks": {},
        "critical_issues": [],
        "recommendations": [],
        "next_action": "proceed_to_report"
    }
    
    # 1. Citation Validation
    citation_result = validate_citations.invoke({"draft_content": draft_content})
    aggregate["checks"]["citations"] = citation_result
    
    # 2. Content Quality
    quality_result = assess_content_quality.invoke({"draft_content": draft_content})
    aggregate["checks"]["quality"] = quality_result
    
    # 3. Completeness
    completeness_result = verify_draft_completeness.invoke({
        "draft_content": draft_content,
        "research_query": research_query
    })
    aggregate["checks"]["completeness"] = completeness_result
    
    # 4. Fact-checking (if claims provided)
    if claims_to_verify:
        fact_result = fact_check_claims.invoke({"claims": claims_to_verify[:5]})  # Limit to 5
        aggregate["checks"]["fact_check"] = fact_result
    
    # 5. Cross-reference (if sources provided)
    if web_sources or academic_sources:
        # Extract citations from draft
        citation_pattern = r'\[([^\]]+)\]\(([^\)]+)\)'
        draft_citations = [url for _, url in re.findall(citation_pattern, draft_content)]
        
        cross_result = cross_reference_sources.invoke({
            "web_sources": web_sources or [],
            "academic_sources": academic_sources or [],
            "draft_citations": draft_citations
        })
        aggregate["checks"]["cross_reference"] = cross_result
    
    # Calculate aggregate score
    scores = []
    for check_name, check_result in aggregate["checks"].items():
        if "score" in check_result:
            scores.append(check_result["score"])
        if check_result.get("status") == "invalid":
            aggregate["critical_issues"].extend(check_result.get("issues", []))
        elif check_result.get("status") == "needs_revision":
            aggregate["recommendations"].extend(check_result.get("issues", []))
    
    aggregate["overall_score"] = round(sum(scores) / len(scores)) if scores else 0
    
    # Determine overall status and next action
    if len(aggregate["critical_issues"]) > 0 or aggregate["overall_score"] < 50:
        aggregate["overall_status"] = "invalid"
        aggregate["next_action"] = "restart_research"
    elif aggregate["overall_score"] < 75:
        aggregate["overall_status"] = "needs_revision"
        aggregate["next_action"] = "revise_draft"
    else:
        aggregate["overall_status"] = "valid"
        aggregate["next_action"] = "proceed_to_report"
    
    print("\n" + "="*60)
    print(f"📊 VERIFICATION COMPLETE: {aggregate['overall_status'].upper()}")
    print(f"   Overall Score: {aggregate['overall_score']}/100")
    print(f"   Next Action: {aggregate['next_action']}")
    print("="*60 + "\n")
    
    return aggregate
