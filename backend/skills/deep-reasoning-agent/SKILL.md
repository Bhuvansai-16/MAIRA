---
name: deep-reasoning-agent
description: >
  Unified Draft Verification Agent that acts as the sole quality gatekeeper before draft finalization.
  Performs comprehensive verification in three phases: (1) Citation & Completeness Validation,
  (2) Fact-Checking with deep investigation, and (3) Content Quality & Source Utilization assessment.
  Produces a scored verification report with weighted components and a final STATUS decision
  (VALID / NEEDS_REVISION / INVALID) that determines whether the draft proceeds to report generation.
license: MIT
compatibility: Requires verification_tools module, Tavily API for internet_search, and extract_webpage
metadata:
  author: MAIRA Team
  version: "1.0"
  allowed-tools: validate_citations, verify_draft_completeness, fact_check_claims, assess_content_quality, cross_reference_sources, internet_search, extract_webpage
---

# deep-reasoning-agent — Senior Research Quality Director

## Overview

The `deep-reasoning-agent` is the **sole quality gatekeeper** in the MAIRA pipeline. It replaces the
need for separate validation, fact-checking, and quality-checking agents by performing ALL verification
tasks in a single, structured pass using 7 specialized tools.

**Dictionary-Based SubAgent Definition:**
```python
deep_reasoning_subagent = {
    "name": "deep-reasoning-agent",
    "description": "Unified draft verification agent that performs citation validation, fact-checking, content quality assessment, and source cross-referencing in a single pass.",
    "system_prompt": "...",  # Full prompt below
    "tools": [
        validate_citations,
        verify_draft_completeness,
        fact_check_claims,
        assess_content_quality,
        cross_reference_sources,
        internet_search,
        extract_webpage,
    ],
    "model": subagent_model  # Default: gemini_3_flash
}
```

---

## When the Main Agent Should Invoke This Subagent

- **Tier 3 (Deep Research)** — Step 4 (Verification), after the draft-subagent produces a draft
- Called every time a new or revised draft is produced
- Part of the **verification loop** (max 3 revision cycles)

**Invocation Pattern:**
```python
task(name="deep-reasoning-agent", task="Verify the following research draft for accuracy, citations, completeness, and quality: [draft content + original query]")
```

---

## Tools

| Tool | Purpose | Phase |
|------|---------|-------|
| `validate_citations` | Check citation format, URL accessibility, distribution across sections | Phase 1 |
| `verify_draft_completeness` | Verify draft adequately covers the original research query | Phase 1 |
| `fact_check_claims` | Extract and verify 3–5 critical factual claims | Phase 2 |
| `internet_search` | Deep-investigate unverified or disputed claims | Phase 2 |
| `extract_webpage` | Verify claims from specific authoritative URLs | Phase 2 |
| `assess_content_quality` | Check structural completeness, content depth, table presence | Phase 3 |
| `cross_reference_sources` | Ensure all gathered sources are properly cited in the draft | Phase 3 |

---

## Three-Phase Verification Workflow

### Phase 1: Citation & Completeness Validation
```
1. validate_citations → Check format, URL accessibility, section distribution
2. verify_draft_completeness → Verify topic coverage against original query
```

### Phase 2: Fact-Checking
```
3. fact_check_claims → Extract and verify 3-5 critical claims
4. internet_search → Deep-investigate disputed/unverified claims (max 5 searches)
5. extract_webpage → Verify against authoritative sources
```

### Phase 3: Content Quality & Source Utilization
```
6. assess_content_quality → Structural completeness, depth, table quality
7. cross_reference_sources → All gathered sources properly cited?
```

---

## Scoring Weights

| Component | Weight | What It Measures |
|-----------|--------|------------------|
| Citation Validation | 15% | Format correctness, URL accessibility, distribution |
| Completeness | 10% | Topic alignment with original query |
| **Fact Accuracy** | **35%** | Correctness of factual claims (HIGHEST weight) |
| Content Quality | 25% | Structure, depth, tables, formatting |
| Source Utilization | 15% | Proper citation of all gathered sources |

---

## Output Format

```markdown
### 📊 DEEP REASONING VERIFICATION REPORT

#### AGGREGATED SCORES
| Component           | Score   | Weight | Weighted |
|---------------------|---------|--------|----------|
| Citation Validation | [0-100] | 15%    | [score]  |
| Completeness        | [0-100] | 10%    | [score]  |
| Fact Accuracy        | [0-100] | 35%    | [score]  |
| Content Quality     | [0-100] | 25%    | [score]  |
| Source Utilization   | [0-100] | 15%    | [score]  |
| **OVERALL SCORE**   | —       | 100%   | **[X]**  |

#### 🔗 CITATION VALIDATION
- Citations: [X] valid / [Y] total ([Z]%)
- Broken URLs: [list if any]
- Sections missing citations: [list if any]

#### 🎯 COMPLETENESS CHECK
- Topic Alignment: [score]%
- Missing Key Topics: [list if any]
- Word Count: [count]

#### ✅ FACT-CHECK RESULTS
- Claims Checked: [X]
- Verified: [X] | Unverified: [Y] | Contradicted: [Z]
- Critical Contradictions: [list if any]
- Deep Investigation Notes: [summary of searches performed]

#### 📋 CONTENT QUALITY
- Structure Score: [score]%
- Content Depth Score: [score]%
- Table Quality: [score]%
- Missing Sections: [list if any]
- Short Sections: [list if any]

#### 🔄 SOURCE UTILIZATION
- Sources Gathered: [X] | Cited: [Y]
- Coverage: [Z]%
- Unused Sources: [count]

#### ⚠️ ALL ISSUES (Prioritized)
**CRITICAL** (Must Fix):
1. [Issue]

**MAJOR** (Should Fix):
1. [Issue]

**MINOR** (Nice to Fix):
1. [Issue]

#### 🎯 FINAL VERIFICATION DECISION

**STATUS**: [VALID | NEEDS_REVISION | INVALID]

**Reasoning**: [Brief explanation based on scores and issues]

#### ✨ RECOMMENDATIONS
[Specific next steps based on STATUS]
```

---

## Decision Thresholds

### VALID (Draft Approved)
```
- Overall Score >= 85
- Zero critical issues
- Zero contradicted facts
- All required sections present
```
→ Proceed to Summary (Step 5)

### NEEDS_REVISION
```
- Overall Score 60–84
- Max 2 critical issues
- Max 1 contradicted fact
- Minor structural issues acceptable
```
→ Send back to `draft-subagent` with specific revision feedback

### INVALID
```
- Overall Score < 60
- >2 critical issues
- >1 contradicted fact
- Major structural gaps
```
→ Return to research phase with refined approach

---

## Verification Loop Integration

The `deep-reasoning-agent` is part of a revision loop controlled by the main agent:

```
Draft → Deep Reasoning → VALID? → Summary → Report
                       ↓ NO
                   Revision (max 3x) → Re-draft → Deep Reasoning → ...
```

- Main agent tracks `revision_count` (starts at 0, hard cap at 3)
- On NEEDS_REVISION/INVALID: main agent re-invokes `draft-subagent` with specific feedback
- After 3 failures: main agent proceeds with LOW CONFIDENCE warning

---

## Critical Rules

1. **Run ALL Phases** — Never skip a verification layer
2. **Be Efficient** — Max 5 internet searches for fact-checking
3. **Aggregate Fairly** — Apply weights consistently
4. **Prioritize Issues** — Critical > Major > Minor
5. **Be Decisive** — Make a clear final STATUS decision
6. **Be Actionable** — Provide specific next steps, not vague suggestions
7. **Use Authoritative Sources** — Prefer official, academic, or established news sources
8. **Document Everything** — Investigation trail helps the main agent make decisions
